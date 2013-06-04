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

import threading
import parrot

# ----------------------------------------------------------------------------------
# Accessors for reading/writing typed capabilities
# ----------------------------------------------------------------------------------

def configure(self, params):
    self.weblink_update = params.get('weblink_update')

def set(self, key, value, sender = None):
    # Example of logging is put here. Remove when fed up with seeing set log-messages
    self.log("set(%s, %s)" % (key, str(value)))
    if key in self.state:
        # look up the actual type, carefully
        attr_desc = self.state['capabilities'].get(key)
        if not attr_desc:
            self.log("Error in set(%s, %s): Missing key (%s)" % (key, str(value), key))
            return False
        type_desc = attr_desc.get('type')
        if not type_desc:
            self.log("Error in set(%s, %s): Missing attribute description for key (%s)" % (key, str(value), key))
            return False

        if type_desc == 'boolean':
            if value in [True, 'true', 'True', 'TRUE', 'yes', 'Yes', 'YES', 'y', 1, '1', 'on', 'On', 'ON']:
                self.state[key] = True
            else:
                self.state[key] = False
        elif type_desc == 'integer':
            self.state[key] = int(value)
        elif type_desc == 'float':
            self.state[key] = float(value)
        elif type_desc == 'string':
            self.state[key] = str(value)
        else:
            self.log("Error in set(%s, %s): Unknown type (%s)" % (key, str(value), type_desc))
            return False

        if self.weblink_update:
            self.conn.send({'dest':'urn:weblink', 'sender':self.urn, 'action':'set', 'key':key, 'value':value})
        return True

def get(self, key):
    return self.state.get(key, None)

def access_rights(self, key):
    # Access rights is specified in capabilities[key]['access']
    # If key not present, return None
    # If access not stated, default to 'r'(ead)
    attr_desc = self.state['capabilities'].get(key)
    if not attr_desc:
        return None
    return attr_desc.get('access', 'r')




# ----------------------------------------------------------------------------------
# Provides read/write access to named capabilities, over a socket on port 1234, in
# the following format:
#     read <capability>
#     write <capability> <new-value>
# These requests are mapped to set()/get() method calls, which the concrete node is
# expected to implement. Responses are of the format
#     ok <optional-value>
#     error <explanation>
# where the <optional-value> is only valid for read requests.
# N.B To simplify for simple hardware devices all lines MUST end with '\n' (newline)
# ----------------------------------------------------------------------------------

def activate(self):
    self.socket_thread = threading.Thread(target = self.access_socket_main)
    self.socket_thread.start()

def deactivate(self):
    self.done = True

def access_socket_main(self):
    server = parrot.Socket(self)
    server.bind(("0.0.0.0", 1234))
    server.listen()
    inputs = [server]
    while not self.done:
        inputs_ready = parrot.select(inputs)
        for s in inputs_ready:
            if s == server:
                client = server.accept()
                # self.log("client %s accepted" % client)
                inputs.append(client)
            else:
                # self.log("receiving client request...")
                data = s.recv()
                if not data:
                    s.close()
                    inputs.remove(s)
                    continue

                data = data.rstrip(None) # Remove trailing whitespace
                content = data.split(' ', 2)
                # Check availability and access rights of property

                if content[0] == 'read':
                    if len(content) != 2:
                        s.send("error malformed command '%s'\n" % data)
                        continue
                    key = content[1]
                    access  = access_rights(self, key)
                    if (access and 'r' in access) or (key == 'capabilities'):
                        s.send("ok %s\n" % self.get(key))
                    else:
                        s.send("error read access denied for '%s'\n" % key)
                elif content[0] == 'write':
                    if len(content) != 3:
                        s.send("error malformed command '%s'\n" % data)
                        continue
                    key = content[1]
                    access  = access_rights(self, key)
                    if not access or not 'w' in access:
                        s.send("error write access denied for '%s'\n" % key)
                        continue
                    if not self.set(key, content[2]):
                        s.send("error setting value failed for '%s'\n" % key)
                    else:
                        s.send("ok\n")
                else:
                    s.send("error unexpected command '%s'\n" % content[0])
    self.comm_chan.close()
