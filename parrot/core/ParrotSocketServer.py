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

"""Parrot SocketServer

    This module implements SocketServer for use in Parrot.
    For documentation see Python's built in SocketServer module.

    Notable differences:
    * The server constructor(s) takes an extra parameter (node) as the first argument.
    * ForkingMixIn cannot be used.
    * No UDPServer until a bug in parrot.socket/parrot.select for UDP has been fixed.
"""

import parrot
import SocketServer

# Parrot monkey-patch workaround:
# Override socket.getfqdn() used by HTTPServer
import socket
def _override_getfqdn(name=''):
    return "not.support.ed"
socket.getfqdn = _override_getfqdn


class TCPServer(SocketServer.TCPServer):
    """Base class for various socket-based server classes.

    Methods for the caller:

    - __init__(node, server_address, RequestHandlerClass, bind_and_activate=True)
    - serve_forever(poll_interval=0.5)
    - shutdown()
    - handle_request()  # if you don't use serve_forever()
    """

    socket_type = parrot.SOCK_STREAM

    def __init__(self, node, server_address, RequestHandlerClass, bind_and_activate=True):
        SocketServer.BaseServer.__init__(self, server_address, RequestHandlerClass)
        self.socket = parrot.Socket(node, type=self.socket_type)
        if bind_and_activate:
            self.server_bind()
            self.server_activate()

    def serve_forever(self, poll_interval=0.5):
        # FIXME: parrot.select doesn't respect timeout
        self._BaseServer__is_shut_down.clear()
        try:
            while not self._BaseServer__shutdown_request:
                r = parrot.select([self.socket])
                if self.socket in r:
                    self._handle_request_noblock()
        finally:
            self._BaseServer__shutdown_request = False
            self._BaseServer__is_shut_down.set()

    def _handle_request_noblock(self):
        request, client_address = self.get_request()

        if self.verify_request(request, client_address):
            try:
                self.process_request(request, client_address)
            except:
                self.handle_error(request, client_address)
                self.shutdown_request(request)

    def handle_request(self):
        fd_sets = parrot.select([self.socket])
        # FIXME: parrot.select should gain a timeout at some future time, 
        #        when that happens, this call should respect self.timeout:        
        # fd_sets = parrot.select([self.socket], [], [], self.timeout)
        # if not fd_sets[0]:
        #     self.handle_timeout()
        #     return
        self._handle_request_noblock()

    def get_request(self):
        # FIXME: Fix parrot.socket return semantics, then scrap this method
        return (self.socket.accept(), (None, None))

class UDPServer(TCPServer):

    """UDP server class."""

    allow_reuse_address = False

    socket_type = parrot.SOCK_DGRAM

    max_packet_size = 8192

    def get_request(self):
        data, client_addr = self.socket.recvfrom(self.max_packet_size)
        return (data, self.socket), client_addr

    def server_activate(self):
        pass

    def shutdown_request(self, request):
        self.close_request(request)

    def close_request(self, request):
        pass

ThreadingMixIn = SocketServer.ThreadingMixIn

class ThreadingTCPServer(ThreadingMixIn, TCPServer): pass
class ThreadingUDPServer(ThreadingMixIn, UDPServer): pass

class BaseRequestHandler(SocketServer.BaseRequestHandler): pass
class StreamRequestHandler(SocketServer.StreamRequestHandler): pass
class DatagramRequestHandler(SocketServer.DatagramRequestHandler): pass

