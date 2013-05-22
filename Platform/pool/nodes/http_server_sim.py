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

# Dummy http server

import sys
import threading
import hodcp
import parrot
from pprint import pprint
import time

try:
    bytes = bytearray
    # We have Python 2
except:
    bytes = bytes
    # We have Python 3

class http_server_sim(hodcp.Node, threading.Thread):

    def __init__(self, urn, conn):
        hodcp.Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def configure(self, params):
        self.log("http_server_sim.configure()")

        return True

    def activate(self):
        self.log("http_server_sim.activate()")
        self.start()

    def deactivate(self):
        self.log("http_server_sim.deactivate()")
        self.done = True

    def run(self):
        server = parrot.Socket(self)
        server.bind(("0.0.0.0", 80))
        server.listen()
        self.log("listening 0.0.0.0:80")
        inputs = [server]
        #time.sleep(5)
        while not self.done:
            inputs_ready = parrot.select(inputs)
            for s in inputs_ready:
                if s == server:
                    client = server.accept()
                    self.log("client %s accepted" % client)
                    inputs.append(client)
                else:
                    content = s.recv()
                    if content:
                        self.log("receiving from client: %s" % str(content))
                        s.send("<html>Hello World!</html>")
                        s.close()
                    else:
                        self.log("Client closed down!")
                        inputs.remove(s)
                        # s.close()
                        
    def get(self, key):
        if key =='description':
            return 'A simple HTTP server'
        elif key == 'capabilities':
            return {}
        else:
            return None

