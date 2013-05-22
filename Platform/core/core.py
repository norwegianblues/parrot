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
import imp
import signal
import hodcp
import os
import json
import select
import logger
from multiprocessing import Process, Pipe
from weblink import create_weblink

HODCP_ROOT="."

class Core:
    """The fundamental part of the platform.

    Core reads a config file and instantiates all nodes as separate processes.
    It sets up the communication backplane and links the nodes in the backplane.
    Additionally, it keeps a control channel (pipe) to each node and dispatches messages
    between nodes and tools, servers, world simulation etc.

    """

    def __init__(self):
        self.nodes = {}
        self.config = {}
        self.logger = logger.Logger()
        self.log_filter_params = [u'', u'', u'', u''] # FIXME: Hack
        self.logger.setlog('urn:hodcp:core', 'Core instantiated', 'Core.init')

    def shutdown(self):
        self.stop_nodes()
        self.logger.close()

    def dispatch(self, fcn, timeout=0, params=()):
        """Start a new subrocess.

        This function will detach 'fcn' as a process of its own,
        passing params AND a pipe as arguments to 'fcn'.
        If 'timeout' > 0 this function will block, waiting for the
        detached process to send some data over the pipe.
        If data i written to pipe in time, the pipe will be returned to the calling process.
        On timeout, the pipe will be closed and 'None' will be returned to the calling process.

        """
        conn, child_conn = Pipe()
        p = Process(target=fcn, args=params + (child_conn,))
        p.start()
        if timeout > 0:
            poll_status = conn.poll(timeout)
            if poll_status == False:
                print "Dispatched function %s did not send anything within the specified timeout (%d s)" % (fcn, timeout)
                # FIXME: How to properly handle this case?
                # - p.terminate() doesn't terminate any subprocesses the p might have spawned
                # - conn.close(), i.e. closing the control channel, is probably better. Make sure p detects and handle it.
                # - send a proper control message (set running to False) should work too.
                # The proper way to implement a client is to handle connection.close() and stop running control message in the same way.
                conn.close()
                conn = None
        return conn

    def load_config(self, config_file, required_version=1):
        if not os.path.isabs(config_file) and not os.path.isfile(config_file):
            config_file = HODCP_ROOT+'/Configs/'+config_file
        if not os.path.isfile(config_file):
            return False

        self.config = json.load(open(config_file))

        ## FIXME: Check version and preprocess if needed/possible
        version = self.config.get('version', 0)
        if version == required_version:
            return True
        #self.config = pcpp.preprocess_config(self.config)
        print '[Core] Config file format version (%d) does not match required version (%d)' % (version, required_version)
        return False


    def setup_platform(self, config_file):
        # Config file
        if not self.load_config(config_file):
            print '[Core] Cannot load config file: '+config_file
            sys.exit(1)

        if 'description' in self.config.keys():
            formatted_description = (
            "========================================\n"+
            self.config['description']+
            "\n========================================"
            )
            print formatted_description

        # Network backplane. Use default unless supplied by user in env var BACKPLANE
        bp_module = os.environ.get('BACKPLANE', 'backplane')
        file = None
        try:
            file, filename, description = imp.find_module(bp_module)
            module = imp.load_module(bp_module, file, filename, description)
        except ImportError:
            print '[Core] Cannot find or load module <', bp_module, '>\n'
        finally:
            if file:
                file.close()
            
        self.nodes['urn:backplane'] = self.dispatch(module.create_backplane, timeout=30, params=(1111, self.config, ))

        # Create weblink
        self.nodes['urn:weblink'] = self.dispatch(create_weblink, timeout=0, params=(1112,))

        # Create nodes
        urns = self.config['nodes'].keys()
        for urn in urns:
            node_config = self.config['nodes'][urn]
            self.setup_node(urn, node_config)

    def setup_node(self, urn, node_config):
        # augment the node's interfaces with the corresponding network configs
        networks = self.config.get('networks')
        if networks:
            for iface in node_config['interfaces'].keys():
                nw_urn = node_config['interfaces'][iface].get('network')
                if nw_urn:
                    node_config['interfaces'][iface]['config'] = networks[nw_urn]
        self.nodes[urn] = self.dispatch(hodcp.create_node, timeout=0, params=(node_config, urn,))        

    def control_message(self, msg):
        # print "[Core::send_control_msg] msg = '%s'" % msg
        if msg['action'] == 'get' and msg['key'] == 'config':
            reply = {'dest':msg['sender'], 'sender':msg['dest'], 'action':'set', 'key':'config', 'value':self.config}
            self.send_control_msg(reply)

        elif msg['action'] == 'set' and msg['key'] == 'log':
            self.logger.setlog(msg['sender'], msg['value'])

        elif msg['action'] == 'set' and msg['key'] == 'log_filter':
            self.log_filter_params = msg['value']

        elif msg['action'] == 'get' and msg['key'] == 'log':
            log = self.logger.getlog(*self.log_filter_params)
            reply = {'dest':msg['sender'], 'sender':msg['dest'], 'action':'set', 'key':'log', 'value':log}
            self.send_control_msg(reply)

        else:
            print "[Core] Unknown message: %s" % msg

    def send_control_msg(self, msg):
        if msg['action'] == 'ACK':
            # print "[Core] Ignoring %s" % str(msg)
            pass

        elif msg['dest'] in self.nodes:
            # print "\033[34m [Core::send_control_msg] dispatching to node : \033[0m  msg = '%s'" % msg
            conn = self.nodes[msg['dest']]
            conn.send(msg)

        elif msg['dest'] == 'urn:hodcp:core':
            # Message for us
            self.control_message(msg)

        else:
            print "[Core] Unknown destination URN: %s" % msg['dest']

    def broadcast(self, msg):
        for urn in self.nodes.keys():
            msg['dest'] = urn
            self.send_control_msg(msg)

    def start_nodes(self):
        start = {'action':'set', 'key':'running', 'value':True}
        self.broadcast(start)

    def stop_nodes(self):
        stop = {'action':'set', 'key':'running', 'value':False}
        self.broadcast(stop)

    def set_node_property(self, urn, key, value):
        msg = {'dest':urn, 'action':'set', 'key':key, 'value':value}
        self.send_control_msg(msg)

    def request_node_property(self, urn, key, dest_urn):
        msg = {'dest':urn, 'sender':dest_urn, 'action':'get', 'key':key}
        self.send_control_msg(msg)

    def serve(self):
        # FIXME: Should be possible to attach tools when running, much like e.g. weblink
        print "[Core] Platform running."
        running = 1
        while running:
            inputready, _, _ = select.select(self.nodes.values(),[],[])
            for s in inputready:
                msg = s.recv()
                if not msg:
                    print "[Core] input source closed down..."
                    # FIXME: Handle
                    # s.close()
                    # inputs.remove(s)
                else:
                    # Dispatch to destination
                    self.send_control_msg(msg)



def cleanup(signal, frame):
    sys.exit(0)


if __name__ == '__main__':

    if len(sys.argv) < 3:
        print("Usage: %s <HODCP_ROOT> <config_file.json>" % sys.argv[0])
        sys.exit(0)

    HODCP_ROOT = sys.argv[1]
    config_file = sys.argv[2]

    # Define this for sub-processes to read
    os.environ['HODCP_ROOT']=HODCP_ROOT

    core = Core()

    # catch Ctrl-C interrupt and do cleanup (http://stackoverflow.com/q/1112343/1007047)
    signal.signal(signal.SIGINT, cleanup)

    try:
        core.setup_platform(config_file)
        core.start_nodes()
        core.serve()
    except SystemExit:
        print("\n[Core] User stopped simulation, attempting cleanup")
    finally:
        core.shutdown()
