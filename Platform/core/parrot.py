# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

########################################################################
# Copyright (c) 2013 Ericsson AB
# 
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v1.0
# which accompanies this distribution, and is available at
# http://www.eclipse.org/legal/epl-v10.html
# 
# Contributors:
#    Ericsson Research - initial implementation
#
########################################################################

import uuid
import time
import random
import collections
import Queue
import networking
import socket

# Known constants
POLLIN = 1
POLLOUT = 2


def check_inputs(inputs):
    """
    Like select() below, but with one difference:
    when no data is available, the function does not block, but rather
    returns an empty set.
    """

    pending = []
    for i in inputs:
        if i.data_available():
            pending.append(i)
    return pending

def select(inputs):
    """Return a list of devices/sockets ready for reading.

    This is similar to the built-in `select.select() <http://docs.python.org/library/select.html?highlight=select.select#select.select>`_
    but with several limitations. Pass a list of :py:class:`parrot.Socket` and/or :py:class:`parrot.Device` objects as input, and it will block until at least one of
    the potential sources have input available.
    """

    # All sockets/devices within a node share a single communication channel
    cond = inputs[0].node.comm_chan.available_cond

    cond.acquire()
    pending = check_inputs(inputs)
    while not pending:
        cond.wait()
        pending = check_inputs(inputs)
    cond.release()

    return pending

class poll():
    """ Return a poll object.

    The poll object, similar to `select.poll() <http://docs.python.org/library/select.html?highlight=select.select#select.poll>`_,
    supports registering and unregistering file descriptors, and then polling them for I/O events.
    """

    def __init__(self):
        self.registry = {}

    def register(self, sock, evt_mask=(POLLIN + POLLOUT)):
        """Register a file descriptor with the polling object.

        :param sock: is a :py:class:`parrot.Socket` .
        :param eventmask: is an optional bitmask describing the type of events you want to check for, and can be a combination of the constants POLLIN, and POLLOUT, described in the table below. If not specified, the default value used will check for both types of events.

        Future calls to the poll() method will check whether the file descriptor has any pending I/O events.

        Registering a file descriptor thats already registered is not an error, and has the same effect as registering the descriptor exactly once.

        *N.B. when checking for POLLOUT, all devices will be assumed to be always writable. This might turn out not to be true.*
        """
        ## FIXME: Hackish, doesn't work for devices.
        sock._become_active_listener()
        self.registry[sock] = evt_mask

    def poll(self, timeout=None):
        """ Return a list of (fd, evt) tuples.

        Polls the set of registered file descriptors, and returns a possibly-empty list containing (fd, event) 2-tuples for the descriptors that have events or errors to report. 
        fd is the file descriptor, and event is a bitmask with bits set for the reported events for that descriptor  POLLIN for waiting input, POLLOUT to indicate that the descriptor can be written to. 
        An empty list indicates that the call timed out and no file descriptors had any events to report. 
        If timeout is given, it specifies the length of time in milliseconds which the system will wait for events before returning. 
        If timeout is omitted, negative, or None, the call will block until there is an event for this poll object.
        """
        inputs = [i for i in self.registry if (self.registry[i] & POLLIN) == POLLIN]
        outputs = [i for i in self.registry if (self.registry[i] & POLLOUT) == POLLOUT]
        # timeout  omitted     negative    None      0     > 0
        # Poll   : BLOCK       BLOCK       BLOCK     POLL  WAIT [ms]
        # select : BLOCK       ILLEGAL     ILLEGAL   POLL  WAIT [s]
        if (outputs == []):
            if timeout is not None:
                # Convert milliseconds to seconds
                timeout = timeout/1000
            # All sockets/devices within a node share a single communication channel
            cond = inputs[0].node.comm_chan.available_cond
            cond.acquire()
            rd = check_inputs(inputs)
            if not rd:
                cond.wait(timeout)
                rd = check_inputs(inputs)
            cond.release()
        else:
            rd = check_inputs(inputs)
        wr = outputs
        # Stitch together a list of (fd, evt) tuples expected by the caller
        # FIXME: merge (x, POLLIN) and (y, POLLOUT) to (x, POLLIN+POLLOUT) if x == y
        rdlist = [(i.fileno(), POLLIN) for i in rd]
        wrlist = [(i.fileno(), POLLOUT) for i in wr]
        result = wrlist+rdlist

        return result

class Device:
    """Create a new Parrot device.

    Pass a reference to the node that owns the socket, and the device name.
    
    :param node: must be a subclass of :py:class:`hodcp.Node`
    :param devicename: is currently limited to 'ser<N>', where N is in the range 0-9.
    """

    def __init__(self, node, devicename):
        self.node = node
        self.comm_chan = node.comm_chan
        self.name = devicename
        self.queue = Queue.Queue()
        self.fifo = collections.deque()
        # FIXME: In open() instead?
        self.comm_chan.register_handler_for_interface(self.name, self._set_data)

    def _set_data(self, data, sender=None):
        # print '[ParrotDevice] _set_data: %s' % data
        self.queue.put(data)

    def open(self):
        """Open the device for reading and writing."""
        pass

    def close(self):
        """Close the device for reading and writing."""
        pass

    def data_available(self):
        try:
            while True:
                if len(self.fifo):
                    return True
                data = self.queue.get_nowait()
                self.fifo.extend(data)
        except Queue.Empty:
            pass

        return False


    def read(self, size=1):
        """Return at least one byte, and no more than `size` bytes. Block if no data available."""
        read_chars = ""

        # first, read as much as possible from the fifo
        try:
            while len(read_chars) < size:
                read_chars += self.fifo.popleft()
        except IndexError:
            pass

        # see if there are more pending bytes in the queue
        try:
            while len(read_chars) < size:
                data = self.queue.get_nowait()
                self.fifo.extend(data)
                try:
                    while len(read_chars) < size:
                        read_chars += self.fifo.popleft()
                except IndexError:
                    pass
        except Queue.Empty:
            pass

        # Queue was empty. Unless we got at least one byte, block for more.
        while len(read_chars) == 0:
            data = self.queue.get() # blocks
            self.fifo.extend(data)
            try:
                while len(read_chars) < size:
                    read_chars += self.fifo.popleft()
            except IndexError:
                pass

        return read_chars

    # Return one byte/char or fail (return None)
    def _read1_nowait(self):
        try:
            return self.fifo.popleft()
        except IndexError:
            # FIFO empty, check queue
            if self.queue.empty():
               return None

        try:
            data = self.queue.get_nowait()
            self.fifo.extend(data)
            return self.fifo.popleft()
        except:
            return None


    # Return at most size bytes/char
    def _read_nowait(self, size=1):
        result = ''
        for i in range(size):
            c = self._read1_nowait()
            if not c:
                break
            result = result + c

        # if len(result):
        #     print '[%s:%s] _read_nowait: Returning "%s"' % (self.node.urn, self.name, str(result))

        return result


    def write(self, bytes):
        """Write `bytes` data to device.""" 
        # print '[%s:%s] write: Sending "%s"' % (self.node.urn, self.name, str(bytes))
        self.comm_chan.send_cmd(str(bytes), self)


class SocketException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


# Supported commands:
# See netwroking.py
#   FIXME: BIND ?

AF_INET = socket.AF_INET
# AF_UNIX = socket.AF_UNIX

SOCK_STREAM = socket.SOCK_STREAM
SOCK_DGRAM = socket.SOCK_DGRAM
SOCK_RAW = socket.SOCK_RAW

SOL_SOCKET = socket.SOL_SOCKET
SO_REUSEADDR = socket.SO_REUSEADDR

class Socket:
    """Create a new Parrot socket.

    Pass a reference to the node that owns the socket. 
    The node must be a subclass of :py:class:`hodcp.Node`.
    """

    # Socket-like object and APIs provided from communication channel
    # The id and iface_name are normally not passed here. These arguments
    # are passed internally when a new socket is created in accept().
    def __init__(self, node, id=None, iface_name='UNASSIGNED'):
        """
        Create a ParrotSocket
        node -- node for which this socket is simulated (caller)
        id -- unique id to this socket, generated if not provided
        """
        self.node = node
        self.comm_chan = node.comm_chan
        self.ip = "0.0.0.0"
        self.port = None
        if id == None:
            self.id = str(uuid.uuid4())
        else:
            self.id = id
        self.pending_op = None
        self.pending_params = None
        self.queue = Queue.Queue()
        self.name = iface_name
        # NB. While it's OK to register a serial device as ser0, ser1, etc.,
        #     that is NOT possible for sockets, so we use the id instead.
        self.comm_chan.register_handler_for_interface(self.id, self._set_data)
        if id is not None:
            # This means this socket was created in response to a CONNECT
            msg = networking.build_message(networking.ACCEPT, id=self.id)
            self.comm_chan.send_cmd(msg, self)
        # print '[ParrotSocket %s] __init__: ' % (self.id)

    def _dump_queue(self):
        """DEBUG. Print the contents of the internal data queue. Destroys queue"""
        if self.queue.empty():
            return
        done = False
        name = self.node.urn
        print "**** Start of queue [%s] ****" % name
        while not done:
            try:
                s = self.queue.get(False)
                s = "\\n".join(s.split("\n"))
                s = "\\r".join(s.split("\r"))
                print s
            except:
                done = True
                print "**** End of queue [%s] ****" % name

    def getsockname(self):
        address = (self.ip, self.port) 
        # print "getsockname(%s, %d)"%address
        return address

    def setsockopt(self, foo, bar, baz):
        pass
                
    def makefile(self, mode='r', bufsize=-1):
        """makefile([mode[, bufsize]]) -> file object

        Return a regular file object corresponding to the socket.  The mode
        and bufsize arguments are as for the built-in open() function."""

        from socket import _fileobject
        return _fileobject(self, mode, bufsize)
                
    def fileno(self):
        """Return an integer unique to each socket."""
        return uuid.UUID(self.id).int

    def _assign_port(self):
        port = random.randint(1024, 65535)
        self.bind(('', port))

    def _set_data(self, data, sender=None):
        # print '[ParrotSocket %s] _set_data: %s' % (self.id, data)
        self.queue.put(data)

    def bind(self, address):
        """Bind the socket to address. 

        The socket must not already be bound. 
        :param address: is a tuple of (ip, port).
        """
        ip = address[0]
        if ip == "":
            ip = "0.0.0.0"
        port = address[1]
        if ip == "0.0.0.0":
            iface_names = self.node.interfaces.keys()
            self.name = iface_names[0]
            # TODO: support server sockets listening to multiple interfaces
            if len(iface_names) > 1:
                print '[ParrotSocket %s] warning: binding to multiple interfaces currently unsupported; binding to ' % (self.id, self.name)
        else:
            self.name = self.interface_lookup(ip)
        self.ip = ip
        self.port = port
        # print '[ParrotSocket %s] bind: ' % (self.id)

    def listen(self, backlog=5):
        """Listen for connections made to the socket. The `backlog` argument is currently unused."""
        # FIXME: backlog
        msg = networking.build_message(networking.LISTEN, id=self.id, ip=self.ip, port=self.port)
        self.comm_chan.send_cmd(msg, self)

    def accept(self):
        """Accept a connection. 

        The socket must be bound to an address and listening for connections. 
        The return value is a new socket object usable to send and receive data on the connection.
        """
        message = self.queue.get()
        op, params = networking.parse_message(message)
        if not op == networking.NEW_CONN:
            # print '[ParrotSocket %s] accept: Expected NEW_CONN, got: %s' % (self.id, message)
            return None

        return Socket(self.node, params['new_id'], self.name)

    def connect(self, address):
        """Connect to an address where `address` is a tuple of (ip, port)."""
        self.name = self.interface_lookup(address[0]);
        message = networking.build_message(networking.CONNECT, id=self.id, ip=address[0], port=address[1])
        # print '[ParrotSocket %s] connect: %s (%s)' % (self.id, message, self.name)
        self.comm_chan.send_cmd(message, self)
        # Block here waiting for ACCEPT from server
        message = self.queue.get()

        op, params = networking.parse_message(message)        
        if op != networking.ACCEPTED or params['id'] != self.id:
            raise SocketException("Failed in connecting")

    def send(self, msg):
        """Send message (TCP)."""
        message = networking.build_message(networking.SEND, id=self.id, payload=msg)
        # print '[ParrotSocket %s] send: %s' % (self.id, message)
        self.comm_chan.send_cmd(message, self)

    def sendall(self, msg):
        # FIXME
        self.send(msg)
        # MSGLEN=len(msg)
        # totalsent = 0
        # while totalsent < MSGLEN:
        #     sent = self.send(msg[totalsent:])
        #     ^^^^
        #     if sent == 0:
        #         raise RuntimeError("socket connection broken")
        #     totalsent = totalsent + sent    
        
    def sendto(self, data, address):
        """Send `data` (UDP) to an `address` which is a tuple of (ip, port)."""
        if not self.port:
            self._assign_port()
        message = networking.build_message(networking.SENDTO, id=self.id, src_port=self.port, dst_ip=address[0], dst_port=address[1], payload=data)
        # print '[ParrotSocket %s] send: %s' % (self.id, message)
        self.comm_chan.send_cmd(message, self)

    def data_available(self):
        return not self.queue.empty()

    def recv(self, n=1):
        """Receive data from the socket. The return value is a string representing the data received."""
        message = self.queue.get()
        op, params = networking.parse_message(message) 
        if not op == 'RECEIVED':
            if op == 'DISCONN':
                self.close()
            else:
                print '[ParrotSocket %s] Unexpected message in recv(), got: %s' % (self.id, message)
            return None
        return params['payload']

    def _become_active_listener(self, assign_port = True):
        ## Inform BP that we are listening.
        if not self.port:
            if not assign_port:
                raise SocketException("Parrot UDP socket has no assigned port")
            else:
                self._assign_port()
        message = networking.build_message(networking.RECVFROM, id=self.id, ip=self.ip, port=self.port)
        self.comm_chan.send_cmd(message, self)

    def recvfrom(self, dummy):
        """Receive data from the socket.
        
        The return value is a pair (data, address) where data is data received and
        address is the tuple of (ip, port) of the socket sending the data.

        The parameter `dummy` is currently unused.
        """

        self._become_active_listener()

        message = self.queue.get()
        op, params = networking.parse_message(message) 
        if not op == 'RECDFROM':
            if op == 'DISCONN':
                self.comm_chan.unregister_handler_for_interface(self.id)
            else:
                print '[ParrotSocket %s] Unexpected message in recv(), got: %s' % (self.id, message)
            return None
        return params['payload'], (params['src_ip'], params['src_port'])

    def close(self):
        """Close the socket."""
        if self.comm_chan.has_registered_handler(self.id): 
            # self._dump_queue()
            message = networking.build_message(networking.DISCONN, id=self.id)
            self.comm_chan.send_cmd(message, self)
            self.comm_chan.unregister_handler_for_interface(self.id)

    def shutdown(self, dummy=None):
        # FIXME
        self.close()

    def interface_lookup(self, ip_address):
        # TODO: this is IPv4 specific -- IPv6 not supported
        dest_address = Socket.ip_address_to_int(ip_address)
        for iface, descr in self.node.interfaces.iteritems():
            # if IP base & mask are missing, any interface will do
            conf = descr.get('config')
            if not conf: # serial interfaces have no config
                continue
            nw_address_str = conf.get('IPv4Base')
            nw_mask_str = conf.get('IPv4Mask')
            if not (nw_address_str and nw_mask_str):
                print '[ParrotSocket %s] IPv4 mask and/or address missing, selecting %s' % (self.id, iface)
                return iface

            nw_address = Socket.ip_address_to_int(nw_address_str)
            nw_mask    = Socket.ip_address_to_int(nw_mask_str)
            if (dest_address & nw_mask) == (nw_address & nw_mask):
                # print '[ParrotSocket %s] associated with interface %s' % (self.id, iface)
                return iface
        print '[ParrotSocket %s] cannot find interface for address %s, defaulting to eth0' % (self.id, ip_address)
        return "eth0"

    @staticmethod
    def ip_address_to_int(ip_address):
        """
        Convert a numerical IP address a.b.c.d to a 32-bit integer representation.
        For our purposes, the endian-ness of the result doesn't matter.
        """
        sum = 0
        for octet in ip_address.split('.'):
            sum = sum * 256 + int(octet)
        return sum
