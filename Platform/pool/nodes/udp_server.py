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

# UDP echo server

import threading
import hodcp
import parrot



class udp_server(hodcp.Node, threading.Thread):

    from accessors import get, set
    
    def __init__(self, urn, conn):
        hodcp.Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def activate(self):
        self.start()

    def deactivate(self):
        self.done = True

    def run(self):
        server = parrot.Socket(self, type=parrot.SOCK_DGRAM)
        server.bind(("0.0.0.0", 4321))
        #while not self.done:    # Run until cancelled
        fd_set = parrot.select([server])
        message, client = server.recvfrom(256) # <=256 byte datagram
        self.log("Client connected: %s" % str(client))
        self.log("Echoing message")
        server.sendto(message, client)
        # server.close()


