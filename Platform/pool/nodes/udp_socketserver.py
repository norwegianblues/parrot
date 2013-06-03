# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4


import sys
import threading
import hodcp
import parrot
import SimpleHTTPServer
import ParrotSocketServer

class MyUDPHandler(ParrotSocketServer.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    #def handle(self):
    #    # self.request is the TCP socket connected to the client
    #    self.data = self.request.recv(1024).strip()
    #    print "{} wrote:".format(self.client_address[0])
    #    print self.data
    #    # just send back the same data, but upper-cased
    #    # self.request.sendall(self.data.upper())
    #    self.request.send(self.data.upper())

    def handle(self):
        print self.request
        data = self.request[0].strip()
        socket = self.request[1]
        print "{} wrote:".format(self.client_address[0])
        print data
        socket.sendto(data.upper(), self.client_address)



class udp_socketserver(hodcp.Node, threading.Thread):
    ### N.B. HTML-files are served relative to HODCP_ROOT
    ###      e.g. $HODCP_ROOT/index.html would be served by default.
    
    from accessors import set, get, configure as default_configure
    
    def __init__(self, urn, conn):
        hodcp.Node.__init__(self, urn, conn)
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

