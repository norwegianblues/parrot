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

"""Protocol handler for socket connections."""

LISTEN = 'LISTEN'
CONNECT = 'CONNECT'
ACCEPTED = 'ACCEPTED'
NEW_CONN = 'NEW_CONN'
SEND = 'SEND'
RECEIVED = 'RECEIVED'
DISCONN = 'DISCONN'
RECDFROM = 'RECDFROM'
ACCEPT = 'ACCEPT'
SENDTO = 'SENDTO'
RECVFROM = 'RECVFROM'

_op_table = {
    LISTEN:  {'arglist':['id', 'ip', 'port']}, 
    CONNECT: {'arglist':['id', 'ip', 'port']}, 
    ACCEPTED:{'arglist':['id']}, 
    NEW_CONN:{'arglist':['id', 'new_id']}, 
    SEND:    {'arglist':['id', 'payload']},  
    RECEIVED:{'arglist':['id', 'payload']}, 
    DISCONN: {'arglist':['id']}, 
    RECDFROM:{'arglist':['id', 'dst_port', 'src_ip', 'src_port', 'payload']}, 
    RECVFROM:{'arglist':['id', 'ip', 'port']},
    ACCEPT:  {'arglist':['id']}, 
    SENDTO:  {'arglist':['id', 'src_port', 'dst_ip', 'dst_port', 'payload']}
    }

def build_message(op, **params):
    info = _op_table[op]
    msg = bytearray(op)

    for argname in info['arglist']:
        arg = params[argname]
        if type(arg) == str:
            msg += b' '+arg
        elif type(arg) == unicode:
            msg += b' '+bytearray(arg, 'utf-8')
        elif type(arg) == int:
            msg += b' '+str(arg)
        elif type(arg) == memoryview:
            msg += b' '+bytearray(arg)
        else:
            raise Exception('Unknown type: %s' % type(arg))
    return msg
    

def parse_message(msg):
    op, args = tuple(msg.split(' ', 1))
    info = _op_table[op]
    nargs = len(info['arglist']) 
    values = args.split(' ', nargs-1)
    keys = info['arglist']
    params = dict(zip(keys, values))
    # For convenience, store op in params too
    params['cmd'] = op

    return (op, params)
