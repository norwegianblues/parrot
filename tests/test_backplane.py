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

import mock
from .context import parrot
from parrot.core import backplane
from parrot.core.default_backplane import bp_interface
from parrot.core.default_backplane import bp_network
from parrot.core.default_backplane import bp_node


sample_network_config = {
    "IPv4Base": "10.1.2.0",
    "IPv4Mask": "255.255.255.0"
}

sampleconfig = {
    "version": 1,
    "description": "sample config",
    "nodes": {
        "urn:parrot:node:sample_client": {
            "config": {},
            "interfaces": {
                "eth0": {
                    "ip": "10.1.2.1",
                    "network": "urn:backplane:subnet:sample_network"
                }
            },
            "class": "sample_module"
        }
    },
    "networks": {
        "urn:backplane:subnet:sample_network": sample_network_config
    }
}


## integration - backplane setup
def test_setup_backplane_networks():
    bp = backplane.Backplane(1111, sampleconfig, None)
    assert "urn:backplane:subnet:sample_network" in bp.networks


def test_setup_backplane_nodes():
    bp = backplane.Backplane(1111, sampleconfig, None)
    assert "urn:parrot:node:sample_client" in bp.nodes


## TODO integration node to node
def test_node_to_node_communication_via_backplane():
    pass


# bp_network tests
def test_add_listener():
    sender = mock.MagicMock()
    sender.properties['ip'] = '10.10.10.10'
    params = {'id': 'test', 'port': 8080}
    nw = bp_network.Network("urn:backplane:subnet:sample_network", sample_network_config)
    assert nw.listen(sender, **params)
    assert nw.listeners[params['id']] == {'interface': sender,
                                          'ip': sender.properties['ip'],
                                          'port': 8080}


def test_listener_lookup():
    nw = bp_network.Network("urn:backplane:subnet:sample_network", sample_network_config)
    sender = mock.MagicMock()
    listener = {'interface': sender, 'ip': '10.10.10.10', 'port': 8080}
    nw.listeners['test'] = listener
    assert nw.lookup('10.10.10.10', 8080) == ['test']


def test_connect_fail_when_no_server_listening():
    nw = bp_network.Network("urn:backplane:subnet:sample_network", sample_network_config)
    sender = mock.MagicMock()
    params = {'id': 'test', 'ip': '10.10.10.10', 'port': 8080}
    assert not nw.connect(sender, **params)


def test_connect_success():
    nw = bp_network.Network("urn:backplane:subnet:sample_network", sample_network_config)
    # setup mock client
    sender = mock.MagicMock()
    params = {'id': 'client', 'ip': '10.10.10.10', 'port': 8080}

    # setup mock server
    server = mock.MagicMock()
    nw.listeners['server'] = {'interface': server,
                              'ip': params['ip'],
                              'port': params['port']}

    assert nw.connect(sender, **params)

    # check that server got information about connection
    assert server.send.called

    # check that mappings are created and connection established
    assert nw.mapping[params['id']] == server
    assert sender in nw.mapping.values()
    server_conn_cid = nw.connections[params['id']]
    assert nw.connections[server_conn_cid] == params['id']


def test_sendto_without_listener():
    nw = bp_network.Network("urn:backplane:subnet:sample_network", sample_network_config)
    sender = mock.MagicMock()
    sender.properties['ip'] = '10.10.10.10'

    params = {'id': 'client', 'src_port': 65000, 'dst_ip': '10.10.10.10',
             'dst_port': 65000, 'payload': 'this is a test'}
    assert nw.sendto(sender, **params)

def test_sendto_with_listener():
    nw = bp_network.Network("urn:backplane:subnet:sample_network", sample_network_config)
    sender = mock.MagicMock()

    sender.properties = {}
    sender.properties['ip'] = '10.10.10.11'

    dst_port = 65000
    params = {'id': 'client', 'src_port': 65000, 'dst_ip': '10.10.10.10',
             'dst_port': dst_port, 'payload': 'this is a test'}

    receiver = mock.MagicMock()
    listener = {'interface': receiver, 'ip': '10.10.10.10', 'port': dst_port}
    nw.listeners['receiver'] = listener

    assert nw.sendto(sender, **params)
    assert receiver.send















