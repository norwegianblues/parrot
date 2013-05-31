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

import parrot
import SocketServer

# Parrot monkey-patch workaround:
# Override socket.getfqdn() used by HTTPServer
import socket
def _override_getfqdn(name=''):
    return "not.support.ed"
socket.getfqdn = _override_getfqdn


class TCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    
    def __init__(self, node, server_address, RequestHandlerClass, bind_and_activate=True):
        SocketServer.BaseServer.__init__(self, server_address, RequestHandlerClass)
        self.socket = parrot.Socket(node)
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
        return (self.socket.accept(), (None, None))


class BaseRequestHandler(SocketServer.BaseRequestHandler): pass
class StreamRequestHandler(SocketServer.BaseRequestHandler): pass
class DatagramRequestHandler(SocketServer.BaseRequestHandler): pass