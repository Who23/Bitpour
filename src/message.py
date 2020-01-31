import struct

class MessageParseError(Exception):
    pass

class Message:
    def construct(self):
        pass

    # the raw bytes does not include the length prefix
    @classmethod
    def deconstruct(self, raw_bytes):
        pass

        #     self.msg_type = MSG_TYPE[raw_message[0]]

        #     if self.msg_type in ["HAVE", "BITFIELD"]:
        #         self.payload.append(raw_message[1:])

        #     elif self.msg_type in ["REQUEST", "CANCEL"]:
        #         raw_payloaod = raw_message[1:]
        #         self.payload = [raw_payloaod[x : x + 4] for x in range(0, 12, 4)]

        #     elif self.msg_type == "PIECE":
        #         self.payload.append(raw_message[1:5])
        #         self.payload.append(raw_message[5:9])
        #         self.payload.append(raw_message[9:])
        # except Exception as e:
        #     raise MessageParseError(e)

class KeepAlive(Message):
    length = 0

    def __init__(self):
        pass

    def construct(self):
        return struct.pack(">I", self.length)

    @classmethod
    def deconstruct(self, raw_bytes):
        if len(raw_bytes) != self.length:
            raise ValueError

        return KeepAlive()

class Choke(Message):
    id = 0
    length = 1

    def __init__(self):
        pass

    def construct(self):
        return struct.pack(">Ib", self.length, self.id)

    @classmethod
    def deconstruct(self, raw_bytes):
        if len(raw_bytes) != self.length or raw_bytes[0] != self.id:
            raise ValueError

        return Choke()
    
class Unchoke(Message):
    id = 1
    length = 1

    def __init__(self):
        pass

    def construct(self):
        return struct.pack(">Ib", self.length, self.id)

    @classmethod
    def deconstruct(self, raw_bytes):
        if len(raw_bytes) != self.length or raw_bytes[0] != self.id:
            raise ValueError

        return Unchoke()

class Interested(Message):
    id = 2
    length = 1

    def __init__(self):
        pass

    def construct(self):
        return struct.pack(">Ib", self.length, self.id)

    @classmethod
    def deconstruct(self, raw_bytes):
        if len(raw_bytes) != self.length or raw_bytes[0] != self.id:
            raise ValueError

        return Interested()

class Uninterested(Message):
    id = 3
    length = 1

    def __init__(self):
        pass

    def construct(self):
        return struct.pack(">Ib", self.length, self.id)

    @classmethod
    def deconstruct(self, raw_bytes):
        if len(raw_bytes) != self.length or raw_bytes[0] != self.id:
            raise ValueError

        return Uninterested()

class Have(Message):
    id = 4
    payload_length = 4
    length = 5

    def __init__(self, piece_index):
        self.piece_index = piece_index

    def construct(self):
        return struct.pack(">IbI", self.length, self.id, self.piece_index)

    @classmethod
    def deconstruct(self, raw_bytes):
        if len(raw_bytes) != self.length or raw_bytes[0] != self.id:
            raise ValueError

        payload = struct.unpack(">I", raw_bytes[1:])

        return Have(*payload)

class Bitfield(Message):
    id = 5
    payload_length = -1
    length = -1

    def __init__(self, bitfield):
        self.length = 1 + len(bitfield)
        self.payload_length = len(bitfield)
        self.bitfield = bitfield

    def construct(self):
        return struct.pack(f">Ib{self.payload_length}s", self.length, self.id, self.bitfield)

    @classmethod
    def deconstruct(self, raw_bytes):
        if raw_bytes[0] != self.id:
            raise ValueError

        payload = struct.unpack(f">{len(raw_bytes)-1}s", raw_bytes[1:])

        return Bitfield(*payload)

class Request(Message):
    id = 6
    payload_length = 12
    length = 13

    def __init__(self, index, begin, request_length):
        self.index = index
        self.begin = begin
        self.request_length = request_length

    def construct(self):
        return struct.pack(">IbIII", self.length, self.id, self.index, self.begin, self.request_length)

    @classmethod
    def deconstruct(self, raw_bytes):
        if len(raw_bytes) != self.length or raw_bytes[0] != self.id:
            raise ValueError

        payload = struct.unpack(f">III", raw_bytes[1:])

        return Request(*payload)

class Piece(Message):
    id = 7
    payload_length = -1
    length = -1

    def __init__(self, index, begin, block):
        self.payload_length = len(block)
        self.length = 9 + self.payload_length

        self.index = index
        self.begin = begin
        self.block = block

    def construct(self):
        return struct.pack(f">IbII{self.payload_length}s", self.length, self.id, self.index, self.begin, self.block)

    @classmethod
    def deconstruct(self, raw_bytes):
        if raw_bytes[0] != self.id:
            raise ValueError

        payload = struct.unpack(f">II{len(raw_bytes)-9}s", raw_bytes[1:])

        return Piece(*payload)

class Cancel(Message):
    id = 8
    payload_length = 12
    length = 13

    def __init__(self, index, begin, request_length):
        self.index = index
        self.begin = begin
        self.request_length = request_length

    def construct(self):
        return struct.pack(">IbIII", self.length, self.id, self.index, self.begin, self.request_length)

    @classmethod
    def deconstruct(self, raw_bytes):
        if len(raw_bytes) != self.length or raw_bytes[0] != self.id:
            raise ValueError

        payload = struct.unpack(f">III", raw_bytes[1:])

        return Cancel(*payload)

_MSG_TYPE = {
    0 : Choke,
    1 : Unchoke,
    2 : Interested,
    3 : Uninterested,
    4 : Have,
    5 : Bitfield,
    6 : Request,
    7 : Piece,
    8 : Cancel
}

def parse_message(raw_bytes):
    if len(raw_bytes) == 0:
        return KeepAlive.deconstruct(raw_bytes)

    return _MSG_TYPE[raw_bytes[0]].deconstruct(raw_bytes)