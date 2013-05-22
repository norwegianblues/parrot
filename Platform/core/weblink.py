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
import web_socket
import json

def create_weblink(port, ctrl):
    host = ''
    backlog = 5
    size = 512

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    server.bind((host,port))
    server.listen(backlog)

    # Track input sources
    inputs = [ctrl, server]
    clients = {}
    handshake_needed = None

    running = 1
    while running:
        inputready, outputready, exceptready = select.select(inputs,[],[])

        for s in inputready:

            if s == server:
                # handle the server (listening) socket
                sock, address = server.accept()
                # print "[Weblink] Accepted:", (sock, address)
                inputs.append(sock)
                clients[sock] = web_socket.wsclient(sock)
                handshake_needed = sock

            elif s == ctrl:
                # Control channel message from core
                msg = s.recv()

                if msg['action'] == 'set' and msg['key'] == 'running' and msg['value'] == False:
                    running = 0

                else:
                    # FIXME: This is broken - don't send to ALL!
                    # print "\033[34m[Weblink] FIXME: ctrl msg dispatch \033[0m"
                    for c in clients.values():
                        # Encode message and pass on to browser
                        # print "[Weblink:page] >>> "+json.dumps(msg)
                        c.send_message(json.dumps(msg))

            else:
                # handle all other sockets
                client = clients[s]
                if handshake_needed == s:
                    client.do_handshake()
                    handshake_needed = None
                else:
                    msg = client.receive_message()
                    if not msg:
                        print "[Weblink] \033[31m client termination \033[0m"
                        client.close()
                        # Remove references to this client
                        del clients[s]
                        inputs.remove(s)
                    else:
                        # print "[Weblink:page] <<< "+msg
                        # Decode and pass to core for dispatch
                        ctrl.send(json.loads(msg))
    server.close()
