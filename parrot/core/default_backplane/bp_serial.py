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

class Serial:
    def __init__(self, config):
        """This is a mapping from interface to interface, e.g.:
        urn:hodcp:node:1:ser0   <--> urn:hodcp:node:2:ser1"""
        self.link_mapping = {}

    def map(self, src, dst):
        self.link_mapping[src] = dst
        self.link_mapping[dst] = src

    def description(self):
        print '[Serial] Mapping: %s' % self.link_mapping

    def relay_handler(self, data, sender):
        """sender is an Interface."""
        dest = self.link_mapping[sender]
        dest.send(data)
