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

import socket
import uuid
import random
import Queue
import networking

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
