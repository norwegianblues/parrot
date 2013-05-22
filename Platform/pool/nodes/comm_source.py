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

# Dummy communication source

import sys
import threading
import time
import datetime
from hodcp import Node
import parrot # for arrot.Device

class comm_source(Node, threading.Thread):
    def __init__(self, urn, conn):
        Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def configure(self, params):
        self.log("comm_source.configure()")

        self.size = 512

        return True

    def activate(self):
        self.log("comm_source.activate()")
        self.start()

    def deactivate(self):
        self.log("comm_source.deactivate()")
        self.done = True

    def run(self):
        dev = parrot.Device(self, 'ser0')
        dev.open()
        while not self.done:
            time.sleep(2)
            dev.write(str(datetime.datetime.now()))
        dev.close()
        # self.comm_chan.close()

