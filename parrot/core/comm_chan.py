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
import threading

def recv_socket_fixed_size(sock, sz):
    "Receive a fixed number of bytes from the socket"
    buf = ""
    received = 0
    while received < sz:
        buf += sock.recv(sz - received)
        received = len(buf)
    return buf

def recv_socket_msg(sock):
    "Receive a message (with an embedded size) from the socket"
    sz_str   = recv_socket_fixed_size(sock, 4)
    data_str = recv_socket_fixed_size(sock, int(sz_str))
    return sz_str + data_str

class EndPoint:
    """
    Communication channel of all nodes in system.

    Proxy object of socket that implements the protocol of communication channel.
    """

    def __init__(self):
        self._socket = None
        self.urn = None        
        # condition indicating data now avilable for reading in at least one
        # socket/device
        self.available_cond = threading.Condition()
        self.interfaces = {}
        self.name = 'cchn'
        self.option_raw = False
                
    def fileno(self):
        return self._socket.fileno()        
            
    def register_handler_for_interface(self, interface_name, interface_handler):
        # Interface is (currently) either ParrotSocket or ParrotDevice
        self.interfaces[interface_name] = interface_handler
        # print "[%s] Comm channel registered interface: %s" % (self.urn, interface_name)

    def unregister_handler_for_interface(self, interface_name):
        if interface_name in self.interfaces:
            del self.interfaces[interface_name]
            # print "registered:", self.interfaces.keys()

    def has_registered_handler(self, interface_name):
        return interface_name in self.interfaces

    def default_handler(self, data, sender):
        if data[0:7]=='DISCONN':
            # This is OK
            return
        
        self.available_cond.release()
        print self
        print data
        raise Exception("[%s] Comm channel interface handler not registered" % (self.urn))
            
    def recv_cmd(self):
        """
        Should receive string of format: <length[4]><if[4]><data[N]>
        and pass <data[N]> on to correct interface.
        """
        self.available_cond.acquire()
        msg = recv_socket_msg(self._socket)

        # FIXME: Split off this inner part
        if_name = msg[4:8]
        if self.option_raw:
            data = msg[4:]
        else:
            data = msg[8:]
        if if_name[0:3] == 'eth':
            # We need socket id to find mapping
            parts = data.split(' ', 2)
            if_name = parts[1]
        iface_handler = self.interfaces.get(if_name, self.default_handler)
        iface_handler(data, self)
        
        self.available_cond.notify()
        self.available_cond.release()

    def send_cmd(self, msg, sender):
        msg = bytearray(sender.name, 'utf-8') + bytearray(msg)
        size_str = "%4d" % len(msg)
        # print "Sending: %s" % size_str + msg
        self._socket.send(size_str + msg)

class CommChan(EndPoint):
    def __init__(self, host, port, urn):
        EndPoint.__init__(self)
    
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.connect((host, port)) # FIXME: Handle failure gracefully
        self._socket = sock
        self.urn = urn 
        # Initialize handshake
        self.register_handler_for_interface(self.name, self.finalize_handshake)
        self.send_cmd(bytearray(self.urn, 'utf-8'), self)
        
    def finalize_handshake(self, reply, sender):
        if not reply == 'OK':
            print '[CommChan] Error connecting "%s" to backplane' % self.urn
            self._socket.close()
            self._socket = None
        self.unregister_handler_for_interface(self.name)

class CommChanBack(EndPoint):
    def __init__(self, sock, option_raw=True):
        EndPoint.__init__(self)
        self._socket = sock
        self.option_raw = option_raw
        
    def handshake(self, data, sender):
        """The magical procedure by which the client establishes
        a relation with the backplane. Thus it maps a node urn to a socket.
        N.B. This is the node URN, not the interface URN, see setup_serial_link.
        Return URN on success. """

        if self.option_raw:
            urn = data[4:]
        else:
            urn = data
        if urn[:4] == 'urn:':
            self.urn = urn
            self.send_cmd(bytearray('OK', 'utf-8'), self)
        else:
            print "Not setting URN: '%s'" % urn
            urn = None

        self.unregister_handler_for_interface(self.name)
        return urn
