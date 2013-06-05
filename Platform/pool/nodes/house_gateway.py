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

import threading
import parrot
import time
import ParrotSocketServer

from hodcp import Node

# Avoid complaints about address in use (set REUSEADDR flag)
ParrotSocketServer.TCPServer.allow_reuse_address = True

class house_gateway(Node, threading.Thread):
    """Gateway, dispatching read/write requests to individual nodes.
    Assumes light switches have addresses 192.168.0.(N+10), where N >= 0.
    Assumes temperature sensors have addresses 192.168.0.(M+20), where M >= 0.
    Assumes door sensors have addresses 192.168.0.(S+30), where S >= 0.
        
    Accesses take the form
        read light/2/on
        write temp_sensor/1/temp 39.3
        read door/0/open
    etc.
        """

    AddressMap = { 'light': 10, 'temp_sensor': 20, 'door': 30 }

    NODE_BASE_ADDRESS = "192.168.0.%d"
    NODE_PORT         = 1234
    
    
    from accessors import get, set, configure as default_configure

    def __init__(self, urn, conn):
        Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def configure(self, params):
        self.default_configure(params)
        config = params.get('config', {})
        self.SERVER_ADDRESS = (params['interfaces']['eth0']['ip'], int(config.get('port', 80)))           

    def path_to_address(self, path):
        """Parses the attribute path, and returns the tuple(addr, key)
        where addr is a dotted IP address of the target node, and key
        is the unqualified attribute key."""
        components = path.split('/')
        address_base = house_gateway.AddressMap[components[0]]
        address_base += int(components[1])
        return (house_gateway.NODE_BASE_ADDRESS % address_base, components[2])
    
    def relay_set(self, full_key, value):
        addr, key = self.path_to_address(full_key)
        sock = parrot.Socket(self)
        sock.connect((addr, house_gateway.NODE_PORT))
        sock.send('write %s %s' % (key, value))
        response = sock.recv().strip()
        msg = response.split(' ', 1)
        if msg[0] != 'ok':
            self.log("error in relay_set: %s" % response)
    
    def relay_get(self, full_key):
        addr, key = self.path_to_address(full_key)
        sock = parrot.Socket(self)
        sock.connect((addr, house_gateway.NODE_PORT))
        sock.send('read %s' % key)
        response = sock.recv().strip()
        msg = response.split(' ', 1)
        if msg[0] == 'ok':
            return msg[1]
        else:
            self.log("error in relay_get: %s" % response)
            return None

    def activate(self):
        self.start()

    def deactivate(self):
        self.done = True

    def run(self):
        server = ParrotSocketServer.TCPServer(self, self.SERVER_ADDRESS, GatewayRequestHandler)
        server.house_gateway = self
        server.serve_forever()

class GatewayRequestHandler(ParrotSocketServer.StreamRequestHandler):
    
    def handle(self):
        try:
            while True:
                content = self.rfile.readline().strip().split(' ', 3)
                
                # print "from client: received '%s'" % content, 5
                if content[0] == 'read':
                    self.wfile.write("ok %s\n" % self.server.house_gateway.relay_get(content[1]))
                elif content[0] == 'write':
                    self.server.house_gateway.relay_set(content[1], content[2])
                    self.wfile.write("ok\n")
                elif content[0] == 'list':
                    self.wfile.write("ok ")
                    for node_type in ['light', 'temp_sensor', 'door']:
                        for node_nbr in [0, 1, 2]:
                            self.wfile.write("%s/%d " % (node_type, node_nbr))
                    self.wfile.write("\n")
                elif content != "":
                    self.wfile.write("error unexpected command '%s'\n" % content[0])
        except:
            print "D'oh!"
            pass
