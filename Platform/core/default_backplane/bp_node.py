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

import bp_interface

class Node:
    def __init__(self, urn, config):
        self.urn = urn
        self.interfaces = {} # dictionary of handlers for each interface
        self.cc = None
        for if_name, if_conf in config['interfaces'].iteritems():
            self.interfaces[if_name] = bp_interface.Interface(if_name, if_conf, self)

    def description(self):
        print '[%s] ' % self.urn
        print '   interfaces:',
        for if_name in self.interfaces:
            print '%s ' % if_name,
        print

    def relay(self, data):
        """From Parrot node via backplane server"""
        if_name = data[0:4]
        message = data[4:]
        self.interfaces[if_name].relay(message)

    def send(self, data, sender):
        """To Parrot node via CommChan socket"""
        self.cc.send_cmd(data, sender)

