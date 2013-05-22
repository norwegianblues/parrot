# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

# Copyright 2013, Ericsson AB
# Copyright 2012, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Handshake and send/receive messages using websocket
# Specifications conformation: http://tools.ietf.org/html/rfc6455
# The rfc6455 frame operation code is based on code from pywebsocket (http://code.google.com/p/pywebsocket/)

import array, struct
from base64 import b64encode
from hashlib import sha1
from mimetools import Message
from StringIO import StringIO
from collections import deque

HANDSHAKE_RESPONSE_RFC6455 = """HTTP/1.1 101 Switching Protocols\r
Upgrade: websocket\r
Connection: Upgrade\r
Sec-WebSocket-Accept: %s\r
Sec-WebSocket-Protocol: base64\r
\r
"""

MAGICAL_STRING = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Frame opcodes defined in the spec.
OPCODE_CONTINUATION = 0x0
OPCODE_TEXT = 0x1
OPCODE_BINARY = 0x2
OPCODE_CLOSE = 0x8
OPCODE_PING = 0x9
OPCODE_PONG = 0xa
# Not really defined in the spec. For abrupt termination from the client
# during page refresh or tab/browser close in Chrome
OPCODE_ABRUPT = 0xf
# Status codes
# Code STATUS_NO_STATUS_RECEIVED, STATUS_ABNORMAL_CLOSURE, and
# STATUS_TLS_HANDSHAKE are pseudo codes to indicate specific error cases.
# Could not be used for codes in actual closing frames.
# Application level errors must use codes in the range
# STATUS_USER_REGISTERED_BASE to STATUS_USER_PRIVATE_MAX. The codes in the
# range STATUS_USER_REGISTERED_BASE to STATUS_USER_REGISTERED_MAX are managed
# by IANA. Usually application must define user protocol level errors in the
# range STATUS_USER_PRIVATE_BASE to STATUS_USER_PRIVATE_MAX.
STATUS_NORMAL_CLOSURE = 1000
STATUS_GOING_AWAY = 1001
STATUS_PROTOCOL_ERROR = 1002
STATUS_UNSUPPORTED_DATA = 1003
STATUS_NO_STATUS_RECEIVED = 1005
STATUS_ABNORMAL_CLOSURE = 1006
STATUS_INVALID_FRAME_PAYLOAD_DATA = 1007
STATUS_POLICY_VIOLATION = 1008
STATUS_MESSAGE_TOO_BIG = 1009
STATUS_MANDATORY_EXTENSION = 1010
STATUS_INTERNAL_SERVER_ERROR = 1011
STATUS_TLS_HANDSHAKE = 1015
STATUS_USER_REGISTERED_BASE = 3000
STATUS_USER_REGISTERED_MAX = 3999
STATUS_USER_PRIVATE_BASE = 4000
STATUS_USER_PRIVATE_MAX = 4999

# Helpers

class NoopMasker(object):
    """A masking object that has the same interface as RepeatedXorMasker but
    just returns the string passed in without making any change.
    """

    def __init__(self):
        pass

    def mask(self, s):
        return s

class RepeatedXorMasker(object):
    """A masking object that applies XOR on the string given to mask method
    with the masking bytes given to the constructor repeatedly. This object
    remembers the position in the masking bytes the last mask method call
    ended and resumes from that point on the next mask method call.
    """

    def __init__(self, mask):
        self._mask = map(ord, mask)
        self._mask_size = len(self._mask)
        self._count = 0

    def mask(self, s):
        result = array.array('B')
        result.fromstring(s)
        # Use temporary local variables to eliminate the cost to access
        # attributes
        count = self._count
        mask = self._mask
        mask_size = self._mask_size
        for i in xrange(len(result)):
            result[i] ^= mask[count]
            count = (count + 1) % mask_size
        self._count = count

        return result.tostring()

class Frame(object):

    def __init__(self, fin=1, rsv1=0, rsv2=0, rsv3=0,
                 opcode=None, payload=''):
        self.fin = fin
        self.rsv1 = rsv1
        self.rsv2 = rsv2
        self.rsv3 = rsv3
        self.opcode = opcode
        self.payload = payload

def create_length_header(length, mask):
    """Creates a length header.

    Args:
        length: Frame length. Must be less than 2^63.
        mask: Mask bit. Must be boolean.

    Raises:
        ValueError: when bad data is given.
    """

    if mask:
        mask_bit = 1 << 7
    else:
        mask_bit = 0

    if length < 0:
        raise ValueError('length must be non negative integer')
    elif length <= 125:
        return chr(mask_bit | length)
    elif length < (1 << 16):
        return chr(mask_bit | 126) + struct.pack('!H', length)
    elif length < (1 << 63):
        return chr(mask_bit | 127) + struct.pack('!Q', length)
    else:
        raise ValueError('Payload is too big for one frame')

def create_header(opcode, payload_length, fin, rsv1, rsv2, rsv3, mask):
    """Creates a frame header.

    Raises:
        Exception: when bad data is given.
    """

    if opcode < 0 or 0xf < opcode:
        raise ValueError('Opcode out of range')

    if payload_length < 0 or (1 << 63) <= payload_length:
        raise ValueError('payload_length out of range')

    if (fin | rsv1 | rsv2 | rsv3) & ~1:
        raise ValueError('FIN bit and Reserved bit parameter must be 0 or 1')

    header = ''

    first_byte = ((fin << 7)
                  | (rsv1 << 6) | (rsv2 << 5) | (rsv3 << 4)
                  | opcode)
    header += chr(first_byte)
    header += create_length_header(payload_length, mask)

    return header

def _build_frame(header, body, mask):
    if not mask:
        return header + body

    masking_nonce = os.urandom(4)
    masker = RepeatedXorMasker(masking_nonce)

    return header + masking_nonce + masker.mask(body)

def _format_frame_object(frame, mask):

    header = create_header(
        frame.opcode, len(frame.payload), frame.fin,
        frame.rsv1, frame.rsv2, frame.rsv3, mask)
    return _build_frame(header, frame.payload, mask)

def create_binary_frame(
    message, opcode=OPCODE_BINARY, fin=1, mask=False):
    """Creates a simple binary frame with no extension, reserved bit."""

    frame = Frame(fin=fin, opcode=opcode, payload=message)
    return _format_frame_object(frame, mask)

def create_text_frame(
    message, opcode=OPCODE_TEXT, fin=1, mask=False):
    """Creates a simple text frame with no extension, reserved bit."""

    encoded_message = message.encode('utf-8')
    return create_binary_frame(encoded_message, opcode, fin, mask)

class FragmentedFrameBuilder(object):
    """A stateful class to send a message as fragments."""

    def __init__(self, mask):
        """Constructs an instance."""

        self._mask = mask
        self._started = False

        # Hold opcode of the first frame in messages to verify types of other
        # frames in the message are all the same.
        self._opcode = OPCODE_TEXT

    def build(self, message, end, binary):
        if binary:
            frame_type = OPCODE_BINARY
        else:
            frame_type = OPCODE_TEXT
        if self._started:
            if self._opcode != frame_type:
                raise ValueError('Message types are different in frames for '
                                 'the same message')
            opcode = OPCODE_CONTINUATION
        else:
            opcode = frame_type
            self._opcode = frame_type

        if end:
            self._started = False
            fin = 1
        else:
            self._started = True
            fin = 0

        if binary:
            return create_binary_frame(
                message, opcode, fin, self._mask)
        else:
            return create_text_frame(
                message, opcode, fin, self._mask)

def _create_control_frame(opcode, body, mask):
    frame = Frame(opcode=opcode, payload=body)

    if len(frame.payload) > 125:
        raise BadOperationException(
            'Payload data size of control frames must be 125 bytes or less')

    header = create_header(
        frame.opcode, len(frame.payload), frame.fin,
        frame.rsv1, frame.rsv2, frame.rsv3, mask)
    return _build_frame(header, frame.payload, mask)

def create_ping_frame(body, mask=False):
    return _create_control_frame(OPCODE_PING, body, mask)

def create_pong_frame(body, mask=False):
    return _create_control_frame(OPCODE_PONG, body, mask)

def create_close_frame(body, mask=False):
    return _create_control_frame(
        OPCODE_CLOSE, body, mask)

def _is_control_opcode(opcode):
    return (opcode >> 3) == 1

# Exceptions

class ConnectionTerminatedException(Exception):
    """This exception will be raised when a connection is terminated
    unexpectedly.
    """

    pass

class InvalidFrameException(ConnectionTerminatedException):
    """This exception will be raised when we received an invalid frame we
    cannot parse.
    """

    pass

class BadOperationException(Exception):
    """This exception will be raised when send_message() is called on
    server-terminated connection or receive_message() is called on
    client-terminated connection.
    """

    pass

class UnsupportedFrameException(Exception):
    """This exception will be raised when we receive a frame with flag, opcode
    we cannot handle. Handlers can just catch and ignore this exception and
    call receive_message() again to continue processing the next frame.
    """

    pass

class wsclient:

    def __init__(self, sock):
        self._sock = sock

        self._send_parts = []
        self._recv_part = None
        self.buffer_size = 65536

        # options
        self.mask_send = False
        self.unmask_receive = True
        # Holds body of received fragments.
        self._received_fragments = []
        # Holds the opcode of the first fragment.
        self._original_opcode = None
        self._writer = FragmentedFrameBuilder(
            self.mask_send)
        self._ping_queue = deque()
        self._client_terminated = False
        self._server_terminated = False

    def _receive_frame(self):
        received = self._sock.recv(2)

        # Client close abruptly
        if len(received) == 0:
            return OPCODE_ABRUPT, [], 1, 0, 0, 0

        first_byte = ord(received[0])
        fin = (first_byte >> 7) & 1
        rsv1 = (first_byte >> 6) & 1
        rsv2 = (first_byte >> 5) & 1
        rsv3 = (first_byte >> 4) & 1
        opcode = first_byte & 0xf

        second_byte = ord(received[1])
        mask = (second_byte >> 7) & 1
        payload_length = second_byte & 0x7f

        if mask == 1:
            masking_nonce = self._sock.recv(4)
            masker = RepeatedXorMasker(masking_nonce)
        else:
            masker = NoopMasker()
        raw_payload_bytes = self._sock.recv(payload_length)
        bytes = masker.mask(raw_payload_bytes)

        return opcode, bytes, fin, rsv1, rsv2, rsv3

    def _receive_frame_as_frame_object(self):
        opcode, bytes, fin, rsv1, rsv2, rsv3 = self._receive_frame()

        return Frame(fin=fin, rsv1=rsv1, rsv2=rsv2, rsv3=rsv3,
                     opcode=opcode, payload=bytes)

    def send_message(self, message, end=True, binary=False):
        """Send message.

        Args:
            message: text in unicode or binary in str to send.
            binary: send message as binary frame.

        Raises:
            BadOperationException: when called on a server-terminated
                connection or called with inconsistent message type or
                binary parameter.
        """

        if self._server_terminated:
            raise BadOperationException(
                'Requested send_message after sending out a closing handshake')

        if binary and isinstance(message, unicode):
            raise BadOperationException(
                'Message for binary frame must be instance of str')

        try:
            self._sock.send(self._writer.build(message, end, binary))
        except ValueError, e:
            raise BadOperationException(e)

    def receive_message(self):
        """Receive a WebSocket frame and return its payload as a text in
        unicode or a binary in str.

        Returns:
            payload data of the frame
            - as unicode instance if received text frame
            - as str instance if received binary frame
            or None if received closing handshake.
        Raises:
            BadOperationException: when called on a client-terminated
                connection.
            ConnectionTerminatedException: when read returns empty
                string.
            InvalidFrameException: when the frame contains invalid
                data.
            UnsupportedFrameException: when the received frame has
                flags, opcode we cannot handle. You can ignore this
                exception and continue receiving the next frame.
        """

        if self._client_terminated:
            raise BadOperationException(
                'Requested receive_message after receiving a closing '
                'handshake')

        while True:
            # mp_conn.read will block if no bytes are available.
            # Timeout is controlled by TimeOut directive of Apache.

            frame = self._receive_frame_as_frame_object()

            # Check the constraint on the payload size for control frames
            # before extension processes the frame.
            # See also http://tools.ietf.org/html/rfc6455#section-5.5
            if (_is_control_opcode(frame.opcode) and
                len(frame.payload) > 125):
                raise InvalidFrameException(
                    'Payload data size of control frames must be 125 bytes or '
                    'less')

            if frame.rsv1 or frame.rsv2 or frame.rsv3:
                raise UnsupportedFrameException(
                    'Unsupported flag is set (rsv = %d%d%d)' %
                    (frame.rsv1, frame.rsv2, frame.rsv3))

            if frame.opcode == OPCODE_CONTINUATION:
                if not self._received_fragments:
                    if frame.fin:
                        raise InvalidFrameException(
                            'Received a termination frame but fragmentation '
                            'not started')
                    else:
                        raise InvalidFrameException(
                            'Received an intermediate frame but '
                            'fragmentation not started')

                if frame.fin:
                    # End of fragmentation frame
                    self._received_fragments.append(frame.payload)
                    message = ''.join(self._received_fragments)
                    self._received_fragments = []
                else:
                    # Intermediate frame
                    self._received_fragments.append(frame.payload)
                    continue
            else:
                if self._received_fragments:
                    if frame.fin:
                        raise InvalidFrameException(
                            'Received an unfragmented frame without '
                            'terminating existing fragmentation')
                    else:
                        raise InvalidFrameException(
                            'New fragmentation started without terminating '
                            'existing fragmentation')

                if frame.fin:
                    # Unfragmented frame

                    self._original_opcode = frame.opcode
                    message = frame.payload
                else:
                    # Start of fragmentation frame

                    if _is_control_opcode(frame.opcode):
                        raise InvalidFrameException(
                            'Control frames must not be fragmented')

                    self._original_opcode = frame.opcode
                    self._received_fragments.append(frame.payload)
                    continue

            if self._original_opcode == OPCODE_TEXT:
                # The WebSocket protocol section 4.4 specifies that invalid
                # characters must be replaced with U+fffd REPLACEMENT
                # CHARACTER.
                try:
                    return message.decode('utf-8')
                except UnicodeDecodeError, e:
                    raise InvalidUTF8Exception(e)
            elif self._original_opcode == OPCODE_BINARY:
                return message
            elif self._original_opcode == OPCODE_ABRUPT:
                self._client_terminated = True
                return None
            elif self._original_opcode == OPCODE_CLOSE:
                self._client_terminated = True

                # Status code is optional. We can have status reason only if we
                # have status code. Status reason can be empty string. So,
                # allowed cases are
                # - no application data: no code no reason
                # - 2 octet of application data: has code but no reason
                # - 3 or more octet of application data: both code and reason
                if len(message) == 0:
                    self._ws_close_code = (
                        STATUS_NO_STATUS_RECEIVED)
                elif len(message) == 1:
                    raise InvalidFrameException(
                        'If a close frame has status code, the length of '
                        'status code must be 2 octet')
                elif len(message) >= 2:
                    self._ws_close_code = struct.unpack(
                        '!H', message[0:2])[0]
                    self._ws_close_reason = message[2:].decode(
                        'utf-8', 'replace')

                if self._server_terminated:
                    return None

                code = STATUS_NORMAL_CLOSURE
                reason = ''
                self._send_closing_handshake(code, reason)
                return None
            elif self._original_opcode == OPCODE_PING:
                self._send_pong(message)
            elif self._original_opcode == OPCODE_PONG:
                inflight_pings = deque()

                while True:
                    try:
                        expected_body = self._ping_queue.popleft()
                        if expected_body == message:
                            # inflight_pings contains pings ignored by the
                            # other peer. Just forget them.
                            break
                        else:
                            inflight_pings.append(expected_body)
                    except IndexError, e:
                        # The received pong was unsolicited pong. Keep the
                        # ping queue as is.
                        self._ping_queue = inflight_pings
                        break
                continue
            else:
                raise UnsupportedFrameException(
                    'Opcode %d is not supported' % self._original_opcode)

    def _send_closing_handshake(self, code, reason):
        body = ''
        if code is not None:
            if (code > STATUS_USER_PRIVATE_MAX or
                code < STATUS_NORMAL_CLOSURE):
                raise BadOperationException('Status code is out of range')
            if (code == STATUS_NO_STATUS_RECEIVED or
                code == STATUS_ABNORMAL_CLOSURE or
                code == STATUS_TLS_HANDSHAKE):
                raise BadOperationException('Status code is reserved pseudo '
                    'code')
            encoded_reason = reason.encode('utf-8')
            body = struct.pack('!H', code) + encoded_reason

        frame = create_close_frame(
            body,
            self._mask_send)

        self._server_terminated = True

        self._sock.send(frame)

    def send_close(self, code=STATUS_NORMAL_CLOSURE, reason=''):
        """Closes a WebSocket connection.

        Args:
            code: Status code for close frame. If code is None, a close
                frame with empty body will be sent.
            reason: string representing close reason.
        Raises:
            BadOperationException: when reason is specified with code None
            or reason is not an instance of both str and unicode.
        """

        if self._server_terminated:
            return

        if code is None:
            if reason is not None and len(reason) > 0:
                raise BadOperationException(
                    'close reason must not be specified if code is None')
            reason = ''
        else:
            if not isinstance(reason, str) and not isinstance(reason, unicode):
                raise BadOperationException(
                    'close reason must be an instance of str or unicode')

        self._send_closing_handshake(code, reason)

        if (code == STATUS_GOING_AWAY or
            code == STATUS_PROTOCOL_ERROR):
            # It doesn't make sense to wait for a close frame if the reason is
            # protocol error or that the server is going away. For some of
            # other reasons, it might not make sense to wait for a close frame,
            # but it's not clear, yet.
            return

        # For now, we expect receiving closing handshake right after sending
        # out closing handshake.
        message = self.receive_message()
        if message is not None:
            raise ConnectionTerminatedException(
                'Didn\'t receive valid ack for closing handshake')

        self._sock.close()

    def close(self):
        self._sock.close()

    def send_ping(self, body=''):
        frame = create_ping_frame(
            body,
            self._mask_send)
        self._sock.send(frame)

        self._ping_queue.append(body)

    def _send_pong(self, body):
        frame = create_pong_frame(
            body,
            self._options.mask_send)
        self._sock.send(frame)

    def do_handshake(self):
        request = self._sock.recv(1024)
        # print("[Weblink] Received handshake:", request)
        request_line, header_lines = request.split('\r\n', 1)
        headers = Message(StringIO(header_lines))
        key = headers['Sec-WebSocket-Key']

        # Generate the hash value for the accept header
        accept = b64encode(sha1(key + MAGICAL_STRING).digest())
        response = HANDSHAKE_RESPONSE_RFC6455 % accept
        # print("[Weblink] Completed handshake:", response)
        self._sock.send(response)
        return
