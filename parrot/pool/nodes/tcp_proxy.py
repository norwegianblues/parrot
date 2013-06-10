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

import sys
import threading
import thread
import socket
from parrot.core import node
import parrot

class tcp_proxy(node.Node, threading.Thread):

    from parrot.core.accessors import set, get, configure as default_configure

    def __init__(self, urn, conn):
        node.Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def configure(self, params):
        self.default_configure(params)
        conf = params.get('config', dict())
        self.server_ip=conf.get('server', "127.0.0.1")
        self.server_port=conf.get('port', 80)
        self.proxy_port=conf.get('proxy_port', self.server_port)
        self.outbound=conf.get('outbound', True)
        pcap = conf.get('proxy_caps', None)
        if type(pcap) is dict and len(pcap)>0:
            key = pcap.keys()[0]
            self.state['capabilities'].update({ key : pcap[key] })
            self.state.update({key : pcap[key].get('default', 0)})

    def activate(self):
        self.start()

    def deactivate(self):
        self.done = True

    def run(self):
        if self.outbound:
            proxy = parrot.Socket(self)
            self.log("Creating outbound proxy mapping from %s:%d --> %s:%d" % (
                self.interfaces["eth0"]["ip"], self.proxy_port, 
                self.server_ip, self.server_port))
        else:
            proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.log("Creating inbound proxy mapping from localhost:%d --> %s:%d" % (self.proxy_port, self.server_ip, self.server_port))
        proxy.bind(('', self.proxy_port))
        proxy.listen(5)

        while not self.done:
            if self.outbound:
                client_socket = proxy.accept()
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            else:
                client_socket = proxy.accept()[0]
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket = parrot.Socket(self)
            server_socket.connect((self.server_ip, self.server_port))
            thread.start_new_thread(self.forward, (client_socket, server_socket))
            thread.start_new_thread(self.forward, (server_socket, client_socket))

    def forward(self, source, destination):
        string = ' '
        while string:
            string = source.recv(1024)
            if string:
                destination.sendall(string)
            else:
                try:
                    source.shutdown(socket.SHUT_RD)
                except:
                    # This will always fail on OS X?
                    # print "FAIL: shutdown source: ", source
                    pass
                try:
                    destination.shutdown(socket.SHUT_WR)
                except:
                    print "FAIL: shutdown destination: ", destination


