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

import Queue
import collections

class Device:
    """Create a new Parrot device.

    Pass a reference to the node that owns the socket, and the device name.
    
    :param node: must be a subclass of :py:class:`hodcp.Node`
    :param devicename: is currently limited to 'ser<N>', where N is in the range 0-9.
    """

    def __init__(self, node, devicename):
        self.node = node
        self.comm_chan = node.comm_chan
        self.name = devicename
        self.queue = Queue.Queue()
        self.fifo = collections.deque()
        # FIXME: In open() instead?
        self.comm_chan.register_handler_for_interface(self.name, self._set_data)

    def _set_data(self, data, sender=None):
        # print '[ParrotDevice] _set_data: %s' % data
        self.queue.put(data)

    def open(self):
        """Open the device for reading and writing."""
        pass

    def close(self):
        """Close the device for reading and writing."""
        pass

    def data_available(self):
        try:
            while True:
                if len(self.fifo):
                    return True
                data = self.queue.get_nowait()
                self.fifo.extend(data)
        except Queue.Empty:
            pass

        return False


    def read(self, size=1):
        """Return at least one byte, and no more than `size` bytes. Block if no data available."""
        read_chars = ""

        # first, read as much as possible from the fifo
        try:
            while len(read_chars) < size:
                read_chars += self.fifo.popleft()
        except IndexError:
            pass

        # see if there are more pending bytes in the queue
        try:
            while len(read_chars) < size:
                data = self.queue.get_nowait()
                self.fifo.extend(data)
                try:
                    while len(read_chars) < size:
                        read_chars += self.fifo.popleft()
                except IndexError:
                    pass
        except Queue.Empty:
            pass

        # Queue was empty. Unless we got at least one byte, block for more.
        while len(read_chars) == 0:
            data = self.queue.get() # blocks
            self.fifo.extend(data)
            try:
                while len(read_chars) < size:
                    read_chars += self.fifo.popleft()
            except IndexError:
                pass

        return read_chars

    # Return one byte/char or fail (return None)
    def _read1_nowait(self):
        try:
            return self.fifo.popleft()
        except IndexError:
            # FIFO empty, check queue
            if self.queue.empty():
               return None

        try:
            data = self.queue.get_nowait()
            self.fifo.extend(data)
            return self.fifo.popleft()
        except:
            return None


    # Return at most size bytes/char
    def _read_nowait(self, size=1):
        result = ''
        for i in range(size):
            c = self._read1_nowait()
            if not c:
                break
            result = result + c

        # if len(result):
        #     print '[%s:%s] _read_nowait: Returning "%s"' % (self.node.urn, self.name, str(result))

        return result


    def write(self, bytes):
        """Write `bytes` data to device.""" 
        # print '[%s:%s] write: Sending "%s"' % (self.node.urn, self.name, str(bytes))
        self.comm_chan.send_cmd(str(bytes), self)
