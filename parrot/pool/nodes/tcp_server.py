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

import sys
import threading
from parrot.core import node
from parrot.core import ParrotSocketServer


class MyTCPHandler(ParrotSocketServer.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        self.data = self.request.recv(1024).strip()
        print "{} wrote:".format(self.client_address[0])
        print self.data
        # just send back the same data, but upper-cased
        # self.request.sendall(self.data.upper())
        self.request.send(self.data.upper())


class tcp_server(node.Node, threading.Thread):

    from parrot.core.accessors import set, get, configure as default_configure

    def __init__(self, urn, conn):
        node.Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def configure(self, params):
        self.default_configure(params)
        config = params.get('config', {})
        self.port = int(config.get('port', 81))

    def activate(self):
        self.start()

    def deactivate(self):
        self.server.shutdown()
        self.done = True

    def run(self):
        self.server = ParrotSocketServer.TCPServer(self, ("0.0.0.0", self.port), MyTCPHandler)
        self.server.serve_forever()



