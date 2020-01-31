from peer import Peer
from message import *
import struct
from hashlib import sha1
import asyncio

class Worker:
    def __init__(self, name, torrent, peer_id, peer_q, pieces_q, downloaded_q):
        self.info_hash = torrent.info_hash
        self.peer_id = peer_id

        self.BLOCK_SIZE = 16384
        self.NUM_REQUESTS = 10

        self.state = {
            "piplined_requests": 0,
            "piece_buf": bytearray(b""),
            "block_num": 0
        }

        self.peers = peer_q
        self.pieces = pieces_q
        self.downloaded_q = downloaded_q
        self.name = name

    async def run(self):
        while True:
            self.peer = await self.peers.get()

            try:
                self.stream = await self.connect(self.peer)
            except Exception as e:
                print(f"{self.name}: {e}")
                self.peers.task_done()
                continue

            print(f"{self.name}: Connected to {self.peer.host.exploded}:{self.peer.port}")

            try:
                handshake = await self.construct_handshake()
                await self.exchange_handshakes(handshake)
            except Exception as e:
                print(f"{self.name}: {e}")
                self.peers.task_done()
                await self.stream.close()
                continue


            while True:
                if not self.peer.peer_choking:
                    (piece_index, piece_hash, piece_length) = await self.pieces.get()
                    print(f"{piece_index}: {piece_hash} ({piece_length})")

                    if not self.peer.has_bit(piece_index):
                        print("Peer does not have piece")
                        await self.pieces.put((piece_index, piece_hash, piece_length))
                        continue




                    self.state = {
                        "pipelined_requests": 0,
                        "piece_buf": bytearray(b""),
                        "block_num": 0
                    }

                    while len(self.state["piece_buf"]) != piece_length:
                        while self.state["pipelined_requests"] < self.NUM_REQUESTS:
                            request_msg = Request(piece_index, 
                                                  self.state["block_num"] * self.BLOCK_SIZE, 
                                                  self.BLOCK_SIZE)

                            self.stream.write(request_msg.construct())
                            await self.stream.drain()

                            self.state["block_num"] += 1
                            self.state["pipelined_requests"] += 1

                            print("Wrote request")

                        print("awaiting pieces")
                        await self.handle_message()


                else:
                    print("awaiting message")
                    await self.handle_message()

                    if self.peer.client_choking and not self.peer.peer_choking:
                        print("wrote interested")
                        self.stream.write(Unchoke().construct())
                        self.stream.write(Interested().construct())

                        self.peer.client_choking = False
                        self.peer.client_interested = True
            


            await self.stream.close()
            break

        print(f"{self.name}: Finished")

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
            print(f"Message Length: {msg_length}")
            raw_message = await self.stream.read(msg_length)
            msg = parse_message(raw_message)

            if isinstance(msg, KeepAlive): 
                print("KeepAlive")
                continue
            
            MSG_TYPE[msg.id](msg)
            break
            

    ## create a connection with a peer
    async def connect(self, peer):
        print(f"{self.name}: Attempting {peer.host.exploded}:{peer.port}...")
        conn = asyncio.open_connection(host=peer.host.exploded, port=peer.port)
        
        try:
            reader, writer = await asyncio.wait_for(conn, timeout=3)
        except asyncio.TimeoutError:
            raise AsyncConnectionError(f"{peer} connection attempt timed out")
        except ConnectionRefusedError:
            raise AsyncConnectionError(f"peer {peer} refused to connect")
        except Exception as e:
            raise AsyncConnectionError(f"error - {e}")

        return AsyncStream(reader, writer)

    ## exchange a handshake with a peer
    async def exchange_handshakes(self, handshake):
        handshake = await self.construct_handshake()
        self.stream.write(handshake)
        await self.stream.drain()

        response = await self.stream.read(68)
        print("Recieved handshake")
        print(f"Handshake: {response}")

        if not await self.valid_handshake(response):
            raise InvalidHandshake

    ## constructs a handshake to send to peers
    async def construct_handshake(self):
        handshake = b"\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00"
        handshake += self.info_hash
        handshake += self.peer_id

        return handshake

    ## check if the given handshake is valid
    async def valid_handshake(self, handshake):
        # make sure the protocol is correct
        if handshake[:20] != b"\x13BitTorrent protocol" : return False

        # make sure it is the correct file
        if handshake[28:48] != self.info_hash : return False

        return True

    def handle_choke(self, msg):
        print("Choked")
        self.peer.peer_choking = True

    def handle_unchoke(self, msg):
        print("Unchoked")
        self.peer.peer_choking = False

    def handle_interested(self, msg):
        print("Interested")
        self.peer.peer_interested = True

    def handle_uninterested(self, msg):
        print("Uninterested")
        self.peer.peer_interested = False

    def handle_have(self, msg):
        print("Have")
        self.peer.set_bit(msg.piece_index, 1)

    def handle_bitfield(self, msg):
        print("Bitfield")
        self.peer.bitfield = bytearray(msg.bitfield)

    def handle_request(self, msg):
        print("Request")

    def handle_piece(self, msg):
        print("Piece")

    def handle_cancel(self, msg):
        print("Cancel")



class InvalidHandshake(Exception):
    pass

class AsyncConnectionError(Exception):
    pass

class AsyncStream:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def read(self, nbytes: int):
        read_bytes = b""
        read_bytes_num = 0
        while read_bytes_num < nbytes:
            read_bytes += await self.reader.read(nbytes - read_bytes_num)
            read_bytes_num = len(read_bytes)

        return read_bytes

    def write(self, bytestring: bytes):
        self.writer.write(bytestring)

    async def drain(self):
        await self.writer.drain()

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()

    