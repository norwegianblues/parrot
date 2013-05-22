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

# communication proxy (communication channel <==> serial/tcp/udp)

import sys
import threading
import serial
import socket
import select
from hodcp import Node
import parrot

class comm_proxy(Node, threading.Thread):
    def __init__(self, urn, conn):
        Node.__init__(self, urn, conn)
        threading.Thread.__init__(self)

    def connect_to_serial(self, params):
        ser = serial.Serial()
        ser.port = params['serial_port']
        ser.baudrate = params['baudrate']
        ser.parity = serial.PARITY_NONE
        ser.stopbits = serial.STOPBITS_ONE
        ser.bytessize = serial.EIGHTBITS
        ser.open()
        ser.isOpen()

        return ser

    def connect_to_udp(self, params):
        if 'udp_server_port' in params:
            port = params['udp_server_port']
            listen = ("",port)
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.bind(listen)
        else:
            s = params['udp_client']
            addr, port = s.split(':')
            self.host = socket.gethostbyname(addr)
            self.port = int(port)
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return udp

    def connect_to_tcp(self, params):
        if 'tcp_server_port' in params:
            port = params['tcp_server_port']
            listen = ("",port)
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp.bind(listen)
            tcp.listen(5)
        else:
            s = params['tcp_client']
            addr, port = s.split(':')
            self.host = socket.gethostbyname(addr)
            self.port = int(port)
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        return tcp

    def configure(self, params):
        self.log("comm_proxy.configure()")

        if not 'config' in params:
            self.log('No config specifies')
            return False

        devname = params['interfaces'].keys()[0]
        if devname[0:3] != 'ser':
            self.log("Missing serial link")
            return False

        self.devname = devname

        param = params['config']

        self.size = 512

        if 'serial_port' in param:
            self.serial = self.connect_to_serial(param)
        else:
            self.serial = False

        if 'udp_client' in param:
            self.udp_client = self.connect_to_udp(param)
        else:
            self.udp_client = False

        if 'udp_server_port' in param:
            self.udp_server = self.connect_to_udp(param)
        else:
            self.udp_server = False

        if 'tcp_client' in param:
            self.tcp_client = self.connect_to_tcp(param)
        else:
            self.tcp_client = False

        if 'tcp_server_port' in param:
            self.tcp_server = self.connect_to_tcp(param)
        else:
            self.tcp_server = False

        return True

    def activate(self):
        self.log("comm_proxy.activate()")
        self.start()

    def deactivate(self):
        self.log("comm_proxy.deactivate()")
        self.done = True

    def run_tcp_client(self):
        dev = parrot.Device(self, self.devname)
        dev.open()
        self.tcp_client.connect((self.host,self.port))
        while not self.done:
            rlist, wlist, xlist = select.select( [self.tcp_client] + [self.comm_chan._socket], [], [] )
            for i in rlist:
                if i is self.tcp_client:
                    data = i.recv(self.size)
                    if data:
                        dev.write(data)
                elif i is self.comm_chan._socket:
                    data = dev.read(self.size)
                    if data:
                        print('Sendto(%s:%d): %s'%(self.host,self.port,data))
                        self.tcp_client.send(data)
        dev.close()
        self.tcp_client.close()

    # Limited to one connection only for now
    def run_tcp_server(self):
        dev = parrot.Device(self, self.devname)
        dev.open()
        self.writers = []
        self.readers = [self.tcp_server, self.comm_chan._socket]
        addr = None
        while not self.done:
            rlist, wlist, xlist = select.select( self.readers, self.writers, [] )
            for i in rlist:
                if self.tcp_server in rlist[:]:
                    new_sock, addr = self.tcp_server.accept()
                    self.readers.append(new_sock)
                    rlist.remove(self.tcp_server)
                    print('connected by',addr)
                elif i is self.comm_chan._socket:
                    data = dev.read(self.size)
                    if data and addr:
                        print('Sendto',addr,data)
                        new_sock.send(data)
                elif i is new_sock:
                    data = i.recv(self.size)
                    if data:
                        dev.write(data)
        dev.close()
        new_sock.close()
        self.tcp_server.close()

    def run_udp_server(self):
        dev = parrot.Device(self, self.devname)
        dev.open()
        addr = None;
        while not self.done:
            rlist, wlist, xlist = select.select( [self.udp_server] + [self.comm_chan._socket], [], [] )
            for i in rlist:
                if i is self.udp_server:
                    data, addr = i.recvfrom(self.size)
                    if data:
                        print('Received',addr,data)
                        dev.write(data)
                elif i is self.comm_chan._socket:
                    data = dev.read(self.size)
                    if data and addr:
                        print('Sendto',addr,data)
                        self.udp_client.sendto(data,addr)
        dev.close()
        self.udp_server.close()

    def run_udp_client(self):
        dev = parrot.Device(self, self.devname)
        dev.open()
        while not self.done:
            rlist, wlist, xlist = select.select( [self.udp_client] + [self.comm_chan._socket], [], [] )
            for i in rlist:
                if i is self.udp_client:
                    data, addr = i.recvfrom(self.size)
                    if data:
                        print('Received',addr,data)
                        dev.write(data)
                elif i is self.comm_chan._socket:
                    data = dev.read(self.size)
                    if data:
                        print('Sendto(%s:%d): %s'%(self.host,self.port,data))
                        self.udp_client.sendto(data,(self.host, self.port))
        dev.close()
        self.udp_client.close()

    def run_serial(self):
        buf = b''
        dev = parrot.Device(self, self.devname)
        dev.open()
        while not self.done:
            rlist, wlist, xlist = select.select( [self.serial] + [dev.comm_chan._socket], [], [] )
            for i in rlist:
                if i is self.serial:
                    val = i.read(1)
                    buf += val;
                    if val == b'\n':
                        print('Read: %s'%buf)
                        dev.write(buf)
                        buf = b''
                elif i is self.comm_chan._socket:
                    data = dev.read(self.size)
                    if data:
                        print('Write: %s'%data)
                        self.serial.write(data)
        dev.close()
        self.serial.close()

    def run(self):
        if self.serial:
            self.run_serial()
        if self.udp_client:
            self.run_udp_client()
        if self.udp_server:
            self.run_udp_server()
        if self.tcp_client:
            self.run_tcp_client()
        if self.tcp_server:
            self.run_tcp_server()
