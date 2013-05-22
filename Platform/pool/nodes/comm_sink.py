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

# Dummy communication channel (prints data to stdout)

import sys
import threading
from hodcp import Node
import parrot # for parrot.Device

class comm_sink(Node, threading.Thread):
    def __init__(self, urn, conn):
        Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def configure(self, params):
        self.log("comm_sink.configure()")

        if 'buffering' in params:
            self.buffering = params['buffering']
        else:
            self.buffering = False
        if self.buffering and 'eol' in params:
            self.eol = params['eol']
        else:
            self.eol = '\n'

        self.size = 512

        return True

    def activate(self):
        self.log("comm_sink.activate()")
        self.start()

    def deactivate(self):
        self.log("comm_sink.deactivate()")
        self.done = True

    def prettify(self, str):
        return ''.join(s for s in str if s not in "\r\n")
        
        
    def run(self):
        dev = parrot.Device(self, 'ser0')
        dev.open()
        if self.buffering:
            outbuf = ''
            while not self.done:
                outbuf += dev.open.read(1)
                if outbuf[-1] == self.eol:
                    self.log("\033[32m"+self.prettify(outbuf)+"\033[0m")
                    outbuf = ''
        else:
            while not self.done:
                outbuf = dev.read(self.size)
                self.log("\033[32m"+self.prettify(outbuf)+"\033[0m")
        dev.close()

