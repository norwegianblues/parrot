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

# UDP client

import threading
from parrot.core import node
import parrot
import time

class udp_client(node.Node, threading.Thread):

    from parrot.core.accessors import get, set

    def __init__(self, urn, conn):
        node.Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def activate(self):
        self.start()

    def deactivate(self):
        self.done = True

    def run(self):
        time.sleep(2) # Wait for server to start
        messout = 'Hello over UDP'
        address = ("10.1.2.2", 4321)

        sock = parrot.Socket(self, type=parrot.SOCK_DGRAM)

        # sock.bind(("0.0.0.0", 2137))
        sock.sendto(messout, address)
        messin, peer = sock.recvfrom(256) # <=256 byte datagram

        if messin != messout:
            self.log("Failed to receive identical message")
        self.log("Received: %s" % messin)
        # sock.close()
        self.done = True

