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

from multiprocessing import Process, Pipe
import os
import socket
import select
import time
import imp
import threading
from comm_chan import CommChan

def create_node(config, urn, conn):
    """Dynamically instantiate a node by name.

    Arguments:
    config -- node config containing at least the name of the module to load
    urn -- the Uniform Resource Name assigned to the node
    conn -- a pipe to communicate with the platform Core

    """

    node_class_name = config.get('class', "NodeClassNameNotProvided")

    try:
        file, filename, description = imp.find_module(node_class_name)
    except ImportError:
        print '[Core] Cannot find module <', node_class_name, '>\n'
    try:
        module = imp.load_module(node_class_name, file, filename, description)
    except ImportError:
        print '[Core] Cannot load module <', node_class_name, '>\n'
    finally:
        if file:
            file.close()

    # Dynamically instantiate the node by name
    try:
        klass = getattr(module, node_class_name)
    except AttributeError:
        print '[Core] Cannot find class <', node_class_name, '>\n'
    else:
        node = klass(urn, conn)
        node.configure(config)
        node.configure_interfaces(config)
        node.connect_to_backplane(1111)
        node.startControlChannel() ## Main event loop

def locate_firmware(fw):
    # We know that HODCP_ROOT exist
    HODCP_ROOT = os.environ['HODCP_ROOT']
    extra_path = ""
    if 'EXTRA_FIRMWAREPATH' in os.environ:
        extra_path=os.environ['EXTRA_FIRMWAREPATH']
    firmware_paths = os.path.abspath(HODCP_ROOT+'/Platform/pool/firmware')+":"+extra_path

    return search_file(fw, firmware_paths)

def search_file(filename, search_path):
    file_found = 0
    paths = search_path.split(':')
    for path in paths:
        full = os.path.join(path, filename)
        if os.path.exists(full):
            file_found = True
            break
    if file_found:
        return os.path.abspath(full)
    else:
        return None

class Node:
    """Base class for all nodes in system.

    :param urn: the URN assigned to the node instance
    :param conn: the control channel (pipe) to the platform core

    All nodes inherit from this class, and should override the following methods:
    activate(), deactivate(), configure()
    Optionally, the following methods could be overridden in the subclass:
    set(), get(), control_message()
    
    N.B. In general, :py:class:`hodcp.Node()` should not be called directly, 
    it will be called by the platform during startup based on the config script."""

    def __init__(self, urn, conn):
        """
        urn -- the URN assigned to the node instance
        conn -- the control channel (pipe) to the platform core

        """
        self.urn = urn
        self.conn = conn
        self.done = False
        self.comm_chan = None
        self.inputs = []
        self.state = {'capabilities': { 'logging': { 'type': 'boolean' }}}
        self.state['logging'] = True
        
    def log(self, msg):
        """Add a log entry of the form <timestamp> <urn> <msg> to the log database."""

        if self.state['logging']:
            # Since msg may be binary, take some precautions:
            emsg = msg.decode('raw_unicode_escape')
            print("[%s] %s" % (self.urn, emsg))
            # Log msg format: {category.subcat.subsubcat (message)}
            response = {'dest':'urn:hodcp:core', 'sender':self.urn, 'action':'set', 'key':'log', 'value':emsg}
            self.conn.send(response)
        else:
            pass

    def deactivate(self):
        """Called when the node should stop. Implement in subclass if needed."""
        pass

    def activate(self):
        """Called when the node should start. Implement in subclass if needed."""
        pass

    def configure(self, params):
        """Called with configuration information before :py:func:`activate()` is called.

        :param params: a dictionary with node properties

        Implement in subclass if needed."""
        pass

    def configure_interfaces(self, params):
        """
        Configure network interfaces: the node needs to know mask & base address
        for socket connections to work. If this method is overridden -- which
        is neither expected nor required -- then the subclasses' method must
        invoke this implementation too.
        """
        self.interfaces = params['interfaces']

    def set(self, key, value, sender = None):
        """Setter for runtime data, e.g. sensor state. Implement in subclass if needed."""
        pass

    def get(self, key):
        """Getter for runtime data, e.g. sensor state. Implement in subclass if needed."""
        return None

    def control_message(self, msg):
        """Node-specific runtime control information, i.e. not set/get. Implement in subclass if needed."""
        print("Node.control_message() should be implemented by subclass.\nmsg = ", msg)

    def control(self, params):
        op, key= params['action'], params['key']

        if op == 'set':
            if key == 'running':
                if params['value']:
                    self.activate()
                else:
                    self.deactivate()
                    self.done = True
            else:
                self.set(key, params['value'], params['sender'])

        elif op == 'get':
            value = self.get(key)
            if value == None:
                return
            response = {'dest':params['sender'], 'sender':self.urn, 'action':'set', 'key':key, 'value':value}
            self.conn.send(response)
        else:
            self.control_message(params)

    # REVISION: 1) Why is comm channel socket in this select? 
    #           2) Shouldn't self.comm_chan.recv_cmd() be a callback from CommChan?      
    def startControlChannel(self):
        ctrl = self.conn
        self.inputs.append(ctrl)
        running = True
        while running:
            inputready, _, _ = select.select(self.inputs,[],[])

            for s in inputready:

                if s == ctrl:
                    msg = s.recv()
                    if not msg:
                        running = False
                    else:
                        self.control(msg)
                elif s == self.comm_chan:
                    self.comm_chan.recv_cmd()
                else:
                    self.log("Unknown socket: %s" % s)

    # REVISION: Shouldn't have to expose comm chan internals
    def connect_to_backplane(self, port):
        host = ''
        cc = CommChan(host, port, self.urn)
        self.comm_chan = cc
        # Add comm_chan to select list
        self.inputs.append(cc)

        return cc
