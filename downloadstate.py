from message import *



class DownloadState:
    def __init__(self, stream, piece_hash, piece_index, piece_length):
        self.pipelined_requests = 0
        self.block_num = 0
        self.downloaded_block = 0

        self.stream = stream

        self.p_hash = piece_hash
        self.p_index = piece_index
        self.p_length = piece_length
        self.piece_buf = bytearray(piece_length)

        

        

    
    async def handle_message(self):
        MSG_TYPE = {
                0 : self.handle_choke,
                1 : self.handle_unchoke,
                2 : self.handle_interested,
                3 : self.handle_uninterested,
                4 : self.handle_have,
                5 : self.handle_bitfield,
                6 : self.handle_request,
                7 : self.handle_piece,
                8 : self.handle_cancel,
            }
        
        while True:
            msg_length = int.from_bytes(await self.stream.read(4), byteorder="big")
            raw_message = await self.stream.read(msg_length)
            msg = parse_message(raw_message)

            if isinstance(msg, KeepAlive): 
                # print("KeepAlive")
                continue
            
            MSG_TYPE[msg.id](msg)
            break

    def handle_choke(self, msg):
        # print(f"{self.name} Choked")
        self.is_choked = True

    def handle_unchoke(self, msg):
        # print(f"{self.name} Unchoked")
        self.is_choked = False

    def handle_interested(self, msg):
        # print(f"{self.name} Interested")
        self.is_interested = True

    def handle_uninterested(self, msg):
        # print(f"{self.name} Uninterested")
        self.is_interested = False

    def handle_have(self, msg):
        # print(f"{self.name} Have")
        self.set_bit(msg.piece_index, 1)

    def handle_bitfield(self, msg):
        # print(f"{self.name} Bitfield")
        self.bitfield = bytearray(msg.bitfield)

    def handle_request(self, msg):
        # print(f"{self.name} Request")
        pass

    def handle_piece(self, msg):
        # print(f"{self.name} Piece")
        if msg.index != self.p_index:
            raise ValueError

        block_length = len(msg.block)

        self.piece_buf[msg.begin:msg.begin+block_length] = msg.block
        self.pipelined_requests -= 1
        self.downloaded_block += 1

    def handle_cancel(self, msg):
        # print(f"{self.name} Cancel")
        pass

     