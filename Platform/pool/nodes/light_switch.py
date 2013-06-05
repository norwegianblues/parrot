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

from hodcp import Node

class light_switch(Node):
    """Simple light switch."""

    # methods get/set for reading/writing capabilities + thread for socket
    # access over port 1234
    from accessors import configure, get, set, activate, deactivate, access_socket_main
    
    def __init__(self, urn, conn):
        Node.__init__(self, urn, conn)
        self.state['capabilities'].update({ 'on': { 'type': 'boolean', 'access':'rw'}, 'manufacturer': { 'type': 'string'}})
        self.state.update({'on': True, 'manufacturer': 'Bulbs, inc.'})
