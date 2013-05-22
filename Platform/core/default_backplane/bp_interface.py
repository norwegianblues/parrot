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

class Interface:
    def __init__(self, name, config, node):
        self.node = node
        self.name = name
        self.properties = config
        self.relay_handler = self._stub_relay_handler
        self.log = self._stub_log

    def description(self):
        print '%s' % self.urn()

    def urn(self):
        return '%s:%s' % (self.node.urn, self.name)
        
    def _stub_log(self, msg, sender):
        print '[%s] Logger not set. msg = ' % self.urn()

    def _stub_relay_handler(self, data, sender):
        print '%s is not connected' % self.urn()
        print 'dropping: %s' % data
        print 'from sender: %s' % sender

    def relay(self, data):
        self.log(data, self)
        self.relay_handler(data, self)

    def send(self, data):
        self.log(data, self)
        self.node.send(data, self)
