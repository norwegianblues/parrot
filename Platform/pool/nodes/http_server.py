# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4


import sys
import threading
import hodcp
import parrot
import SimpleHTTPServer
import ParrotSocketServer

class http_server(hodcp.Node, threading.Thread):
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

        self.server = ParrotSocketServer.TCPServer(self, ("", self.port), 
                                             SimpleHTTPServer.SimpleHTTPRequestHandler)
        self.log("serving at port %d" % self.port)
        self.server.serve_forever()

