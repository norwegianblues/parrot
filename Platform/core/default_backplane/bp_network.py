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

import uuid
import networking

class Network:
    def __init__(self, network_urn, config):
        self.urn = network_urn
        self.properties = config
        self.listeners = {}         # Registered listeners (TCP & UDP)
        self.mapping = {}           # Mapping from connection_id to interface (TCP) 
        self.connections = {}       # Mapping connection_id to peer connection_id (TCP)

    def description(self):
        print '[%s] ' % self.urn, self.properties

    def lookup(self, ip, port):
        server_cids = [cid for cid in self.listeners if (self.listeners[cid]['ip'] == ip and 
                                                         self.listeners[cid]['port'] == port)]    
        return server_cids

    def remove_from_map(self, src_cid):
        if src_cid in self.mapping:
            del self.mapping[src_cid]
        if src_cid in self.connections:
            del self.connections[src_cid]
        if src_cid in self.listeners:
            del self.listeners[src_cid]
        
    def relay_handler(self, data, sender):
        """sender is an Interface."""
        cmd, params = networking.parse_message(data)

        handlers = {
            networking.LISTEN: self.listen,
            networking.CONNECT: self.connect,
            networking.ACCEPT: self.accept,
            networking.SEND: self.send,
            networking.SENDTO: self.sendto,
            networking.RECVFROM: self.recvfrom,
            networking.DISCONN: self.disconnect
        }
        status = handlers.get(cmd, self.bad_command)(sender, **params)
        
    def bad_command(self, sender, **params):            
        print 'BAD COMMAND'
        print '  sender = ', sender
        print '  params = ', params 
        return False
    
    def listen(self, sender, **params):
        # Create new listener
        cid, port = (params['id'], params['port'])
        server_ip = sender.properties['ip']
        self.listeners[cid] = {'interface':sender, 'ip':server_ip, 'port':port}
        # print self.listeners
        return True
        
    def connect(self, sender, **params):
        # Incoming client connection request
        client_cid, server_ip, server_port = (params['id'], params['ip'], params['port'])
        server_cids =self.lookup(server_ip, server_port)

        if not server_cids:
            print "\033[31m"
            print "NO MATCHING SERVER"
            print "  Message: ", params
            print "  Network: ",
            self.description()
            print "  Sender: ",
            sender.description()
            print "-------------\033[0m"
            return False
        
        # Inform the server
        server_cid = server_cids[0]
        server_connection_cid = str(uuid.uuid4())
        server_interface = self.listeners[server_cid]['interface']
        msg = networking.build_message(networking.NEW_CONN, id=server_cid, new_id=server_connection_cid)
        server_interface.send(msg)
        
        # Mapping from connection_id to interface
        self.mapping[client_cid] = server_interface
        self.mapping[server_connection_cid] = sender
        self.connections[client_cid] = server_connection_cid
        self.connections[server_connection_cid] = client_cid
        return True
        
    def send(self, sender, **params):
        # Relay to other end of connection
        src_cid, payload = (params['id'], params['payload'])
        dst = self.mapping[src_cid]
        msg = networking.build_message(networking.RECEIVED, id=self.connections[src_cid], payload=payload)
        dst.send(msg)
        return True

    def accept(self, sender, **params):            
        # Acknowledge to other end of connection
        src_cid = params['id']
        dst = self.mapping[src_cid]
        msg = networking.build_message(networking.ACCEPTED, id=self.connections[src_cid])
        dst.send(msg)
        return True

    def sendto(self, sender, **params):       
        # e.g. SENDTO 79c1fb86-3c97-4c19-80ae-92e9e02251c1 2137 10.1.2.2 4321 Hello over UDP
        (src_cid, src_port, dest_ip, dest_port, payload) = (params['id'], params['src_port'], params['dst_ip'], params['dst_port'], params['payload'])
        src_ip = sender.properties['ip']
        dest_ids = self.lookup(dest_ip, dest_port)
        if not dest_ids:
            return True # This is UDP, no guarantees!

        dst_id = dest_ids[0]    
        dst = self.listeners[dst_id]['interface']
        msg = networking.build_message(networking.RECDFROM, id=dst_id, dst_port=dest_port, src_ip=src_ip, src_port=src_port, payload=payload)        
        dst.send(msg)
        return True
           
    def recvfrom(self, sender, **params):  
        # e.g. RECVFROM a8a232d3-f90a-44f6-847c-9efe8e185d21 0.0.0.0 4321
        # This UDP socket is now actively listening.
        (cid, port) = (params['id'], params['port'])
        server_ip = sender.properties['ip']
        sender.properties['port'] = port
        self.listeners[cid] = {'interface':sender, 'ip':server_ip, 'port':port}
        return True
    
    def disconnect(self, sender, **params):      
        src_cid = params['id']

        # If source is TCP inform other end of connection that we're closing
        if src_cid in self.mapping:
            dst = self.mapping[src_cid]
            msg = networking.build_message(networking.DISCONN, id=self.connections[src_cid])
            dst.send(msg)

        self.remove_from_map(src_cid)
        return True
