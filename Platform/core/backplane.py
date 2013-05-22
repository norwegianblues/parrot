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

import socket
import select
import uuid
import binascii
import comm_chan
import default_backplane.bp_network as bp_network
import default_backplane.bp_node as bp_node
import default_backplane.bp_serial as bp_serial
import default_backplane.bp_interface as bp_interface

class Backplane:

    from accessors import configure, get, set
    
    def __init__(self, port, config, ctrl):
        self.urn = 'urn:backplane'
        self.config = config
        self.server_port = port
        self.conn = None  # No use of conn until server is up and running.
        self.__ctrl = ctrl     # Store ctrl channel here until free for all to use.
        self.links = None
        self.networks = {}
        self.nodes = {}
        self.state = {'capabilities': { 'logging': { 'type': 'boolean' }}}
        self.state.update({'logging':False})

        self.weblink_update = True

        self.setup()

    def description(self):
        for nw in self.networks.values():
            nw.description()

    def log(self, data, sender=None):
        if not self.state['logging']:
            return
        
        if sender:
            urn = sender.urn()
        else:
            urn = self.urn

        msg = binascii.b2a_qp(data)
            
        print "[%s] %s" % (urn, msg)
        request = {'dest':'urn:hodcp:core', 'sender':urn, 'action':'set', 'key':'log', 'value':msg}
        self.conn.send(request)

    def setup(self):
        # Create networks
        for network_urn, network_config in self.config.get('networks', {}).iteritems():
            self.networks[network_urn] = bp_network.Network(network_urn, network_config)
        # Create serial link handler
        self.links = bp_serial.Serial(self.config.get('links', {}))
        # Create nodes and interfaces
        for node_urn, node_config in self.config['nodes'].iteritems():
            node = bp_node.Node(node_urn, node_config)
            for if_name, if_conf in node_config['interfaces'].iteritems():
                interface = bp_interface.Interface(if_name, if_conf, node)
                node.interfaces[if_name] = interface
                if if_name[0:3] == 'eth':
                    nw = self.networks[if_conf['network']]
                    interface.relay_handler = nw.relay_handler
                elif if_name[0:3] == 'ser':
                    interface.relay_handler = self.links.relay_handler
                interface.log = self.log
                if_urn = interface.urn() 
                self.state['capabilities'].update({if_urn:{'type': 'boolean'}})
                self.state.update({if_urn:False})
            self.nodes[node_urn] = node
        # Map serial links
        for src, dst in self.config.get('links', {}).iteritems():
            src_urn, _, src_if_name = src.rpartition(':')
            src_if = self.nodes[src_urn].interfaces[src_if_name]
            dst_urn, _, dst_if_name = dst.rpartition(':')
            dst_if = self.nodes[dst_urn].interfaces[dst_if_name]
            self.links.map(src_if, dst_if)

            # node.description()

    def shutdown(self):
        """Last chance to shut down sub-processes and clean up."""
        print "[Backplane] FIXME: Huge cleanup machen bitte!"
        server.close()

    def handle_control_message(self, msg):
        """Can be overridden by subclass to handle control messages.
        Return a boolean to indicate that the backplane should
        continue to run ('True') or stop ('False').
        The default implementation just returns 'True'."""
        if msg['action'] == 'get':
            val = self.get(msg['key'])
            # Return the requested value to original sender
            request = {'dest':msg['sender'], 'sender':self.urn, 'action':'set', 'key': msg['key'], 'value':val}                
            self.conn.send(request)
        elif msg['action'] == 'set':
            self.set( msg['key'], msg['value'])

        return True

    def closed_comm_channel(self, s):
        """Time to cleanup after backplane just closed communication channel for socket s."""
        print "[Backplane] FIXME: Just closed socket %s, remove any mappings etc." % s

    def handle_recv(self, data, sender):
        urn = sender.urn
        bp_node = self.nodes[urn]
        bp_node.relay(data)

    def handle_handshake(self, data, sender):
        urn = sender.handshake(data, self)
        bp_node = self.nodes[urn]
        bp_node.cc = sender
        
    def serve(self):
        host = ''
        backlog = 5
        size = 512

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, self.server_port))
        server.listen(backlog)

        # Acknowledge to core that server is up:
        ack = {'dest':'urn:hodcp:core', 'sender':self.urn, 'action':'ACK', 'key':"backplane running", 'value': 'OK'}
        self.__ctrl.send(ack)
        # Now conn can be used by anyone.
        self.conn = self.__ctrl
        self.__ctrl = None
        self.log("Started.")
        # Track input sources
        ctrl = self.conn
        inputs = [ctrl, server]

        running = True
        while running:
            inputready, _, _ = select.select(inputs,[],[])

            for s in inputready:

                if s == server:
                    # handle the server socket
                    client, address = server.accept()
                    # print "[Backplane] Accepted:", (client, address)
                    cc = comm_chan.CommChanBack(client)
                    cc.register_handler_for_interface(cc.name, self.handle_handshake)
                    cc.default_handler = self.handle_recv
                    inputs.append(cc)

                elif s == ctrl:
                    msg = s.recv()

                    if not msg:
                        running = False

                    else:
                        # print "[Backplane] Control message: ", msg
                        running = self.parse_control(msg)

                    if not running:
                        self.shutdown()

                else:
                    # handle all other (comm_chan.EndPoint)
                    s.recv_cmd()


    def parse_control(self, msg):
        if msg['action'] == 'set' and msg['key'] == 'running':
            running = msg['value']
        else:
            running = self.handle_control_message(msg)
        return running
        
def create_backplane(port, config, ctrl):
    bp = Backplane(port, config, ctrl)
    bp.serve()



