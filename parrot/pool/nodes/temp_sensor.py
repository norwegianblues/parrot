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

from parrot.core.node import Node

class temp_sensor(Node):
    """Simple temperature sensor."""
    
    from parrot.core.accessors import configure, get, set, activate, deactivate, access_socket_main
    
    def __init__(self, urn, conn):
        Node.__init__(self, urn, conn)
        self.state['capabilities'].update({ 't': { 'type': 'float' }})
        self.state.update({'t': 25.0})
