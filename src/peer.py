import ipaddress

class BitfieldNotSetError(Exception):
    pass

class Peer:
    def __init__(self, raw_ip_bytes):
        self.host = ipaddress.ip_address(raw_ip_bytes[:4])
        self.port = int.from_bytes(raw_ip_bytes[4:], byteorder="big")

        self.bitfield = bytearray(b"")

        self.peer_choking = True
        self.peer_interested = False
        self.client_choking = True
        self.client_interested = False


    def has_bit(self, index):
        if self.bitfield:
            # get the byte by dividing by 8
            bf_byte = self.bitfield[index >> 3]

            # index & 7 to get index in that byte. subtract from 7 so it it left to right.
            return (bf_byte >> (7 - (index & 7))) & 1
        else:
            raise BitfieldNotSetError

    def set_bit(self, index, bit):
        if not isinstance(bit, int):
            raise TypeError

        if self.bitfield:
            # get the byte by dividing by 8
            # index & 7 to get index in that byte. subtract from 7 so it it left to right.
            if bit == 1:
                self.bitfield[index >> 3] = self.bitfield[index >> 3] | (1 << (7 - (index & 7)))
            elif bit == 0:
               self.bitfield[index >> 3] = self.bitfield[index >> 3] & ~(1 << (7 - (index & 7))) 
            else:
                raise ValueError
        else:
            raise BitfieldNotSetError

