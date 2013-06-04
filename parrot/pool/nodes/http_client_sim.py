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

# Dummy http client

import sys
import threading
import time
import parrot
from parrot.core import node

try:
    bytes = bytearray
    # We have Python 2
except:
    bytes = bytes
    # We have Python 3

class http_client_sim(node.Node, threading.Thread):
    def __init__(self, urn, conn):
        node.Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def configure(self, params):
        self.log("http_client_sim.configure()")
        conf = params.get('config', {})
        self.server = conf.get('server', "10.1.2.2")
        self.port = conf.get('port', 80)
        return True

    def activate(self):
        self.log("http_client_sim.activate()")
        self.start()

    def deactivate(self):
        self.log("http_client_sim.deactivate()")
        self.done = True

    def run(self):
        time.sleep(1)
        sock = parrot.Socket(self)
        sock.connect((self.server, self.port))
        self.log("connecting the server")
        sock.send("GET / HTTP/1.0\r\n\r\n")
        content = sock.recv()
        self.log("receiving: \n%s" % content)
        sock.close()

    def get(self, key):
        if key =='description':
            return 'A simple HTTP client'
        elif key == 'capabilities':
            return {}
        else:
            return None

