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

# Known constants
POLLIN = 1
POLLOUT = 2


def check_inputs(inputs):
    """
    Like select() below, but with one difference:
    when no data is available, the function does not block, but rather
    returns an empty set.
    """

    pending = []
    for i in inputs:
        if i.data_available():
            pending.append(i)
    return pending

def select(inputs):
    """Return a list of devices/sockets ready for reading.

    This is similar to the built-in `select.select() <http://docs.python.org/library/select.html?highlight=select.select#select.select>`_
    but with several limitations. Pass a list of :py:class:`parrot.Socket` and/or :py:class:`parrot.Device` objects as input, and it will block until at least one of
    the potential sources have input available.
    """

    # All sockets/devices within a node share a single communication channel
    cond = inputs[0].node.comm_chan.available_cond

    cond.acquire()
    pending = check_inputs(inputs)
    while not pending:
        cond.wait()
        pending = check_inputs(inputs)
    cond.release()

    return pending

class poll():
    """ Return a poll object.

    The poll object, similar to `select.poll() <http://docs.python.org/library/select.html?highlight=select.select#select.poll>`_,
    supports registering and unregistering file descriptors, and then polling them for I/O events.
    """

    def __init__(self):
        self.registry = {}

    def register(self, sock, evt_mask=(POLLIN + POLLOUT)):
        """Register a file descriptor with the polling object.

        :param sock: is a :py:class:`parrot.Socket` .
        :param eventmask: is an optional bitmask describing the type of events you want to check for, and can be a combination of the constants POLLIN, and POLLOUT, described in the table below. If not specified, the default value used will check for both types of events.

        Future calls to the poll() method will check whether the file descriptor has any pending I/O events.

        Registering a file descriptor thats already registered is not an error, and has the same effect as registering the descriptor exactly once.

        *N.B. when checking for POLLOUT, all devices will be assumed to be always writable. This might turn out not to be true.*
        """
        ## FIXME: Hackish, doesn't work for devices.
        sock._become_active_listener()
        self.registry[sock] = evt_mask

    def poll(self, timeout=None):
        """ Return a list of (fd, evt) tuples.

        Polls the set of registered file descriptors, and returns a possibly-empty list containing (fd, event) 2-tuples for the descriptors that have events or errors to report. 
        fd is the file descriptor, and event is a bitmask with bits set for the reported events for that descriptor  POLLIN for waiting input, POLLOUT to indicate that the descriptor can be written to. 
        An empty list indicates that the call timed out and no file descriptors had any events to report. 
        If timeout is given, it specifies the length of time in milliseconds which the system will wait for events before returning. 
        If timeout is omitted, negative, or None, the call will block until there is an event for this poll object.
        """
        inputs = [i for i in self.registry if (self.registry[i] & POLLIN) == POLLIN]
        outputs = [i for i in self.registry if (self.registry[i] & POLLOUT) == POLLOUT]
        # timeout  omitted     negative    None      0     > 0
        # Poll   : BLOCK       BLOCK       BLOCK     POLL  WAIT [ms]
        # select : BLOCK       ILLEGAL     ILLEGAL   POLL  WAIT [s]
        if (outputs == []):
            if timeout is not None:
                # Convert milliseconds to seconds
                timeout = timeout/1000
            # All sockets/devices within a node share a single communication channel
            cond = inputs[0].node.comm_chan.available_cond
            cond.acquire()
            rd = check_inputs(inputs)
            if not rd:
                cond.wait(timeout)
                rd = check_inputs(inputs)
            cond.release()
        else:
            rd = check_inputs(inputs)
        wr = outputs
        # Stitch together a list of (fd, evt) tuples expected by the caller
        # FIXME: merge (x, POLLIN) and (y, POLLOUT) to (x, POLLIN+POLLOUT) if x == y
        rdlist = [(i.fileno(), POLLIN) for i in rd]
        wrlist = [(i.fileno(), POLLOUT) for i in wr]
        result = wrlist+rdlist

        return result