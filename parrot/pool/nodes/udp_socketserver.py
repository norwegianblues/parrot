# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4


import sys
import threading
from parrot.core.node import Node
import parrot
from parrot.core import ParrotSocketServer

class MyUDPHandler(ParrotSocketServer.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        print "{} wrote:".format(self.client_address[0]), data
        print "echoing"
        socket.sendto(data, self.client_address)

class udp_socketserver(Node, threading.Thread):
    
    from parrot.core.accessors import set, get, configure as default_configure
    
    def __init__(self, urn, conn):
        Node.__init__(self, urn, conn)
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

        self.server = ParrotSocketServer.UDPServer(self, ("", self.port), MyUDPHandler)
        self.log("serving at port %d" % self.port)
        self.server.serve_forever()

