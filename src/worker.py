from peer import Peer
from downloadstate import DownloadState
from message import *
import struct
from hashlib import sha1
import asyncio

class Worker:
    def __init__(self, name, torrent, peer_id, peer_q, pieces_q, downloaded_q):
        self.info_hash = torrent.info_hash
        self.peer_id = peer_id

        # the request size and the number of unfulfilled requests we should have
        self.BLOCK_SIZE = 16384
        self.NUM_REQUESTS = 10

        self.state = None

        self.peers = peer_q
        self.pieces = pieces_q
        self.downloaded_q = downloaded_q
        self.name = name

    async def run(self):
        while self.pieces.qsize() > 0:
            self.peer = await self.peers.get()

            try:
                self.stream = await self.connect(self.peer)
            except Exception as e:
                print(f"{self.name}: {e}")
                self.peers.task_done()
                continue

            try:
                handshake = await self.construct_handshake()
                await self.exchange_handshakes(handshake)
            except Exception as e:
                print(f"{self.name}: {e}")
                self.peers.task_done()
                if not self.stream.is_closed(): await self.stream.close()
                continue

            try:
                while self.pieces.qsize() > 0:
                    if not self.state.is_choked:
                        self.state = await self.get_valid_piece()

                        try:
                            await self.download_piece()

                            if not self.verify_piece(bytes(self.state.piece_buf)):
                                await self.pieces.put((self.state.p_index, self.state.p_hash, self.state.p_length))
                                self.pieces.task_done()
                                continue

                            await self.downloaded_q.put((self.state.p_index, bytes(self.state.piece_buf)))
                            self.pieces.task_done()
                            print(f"{self.name} downloaded {self.state.p_index}")
                        except Exception as e:
                            await self.pieces.put((self.state.p_index, self.state.p_hash, self.state.p_length))
                            self.pieces.task_done()
                            print("put")
                            raise e

                    else:
                        # print(f"{self.name} awaiting message")
                        await asyncio.create_task(self.state.handle_message())

                        if self.peer.client_choking and not self.peer.peer_choking:
                            # print("{self.name} wrote interested")
                            self.stream.write(Unchoke().construct())
                            self.stream.write(Interested().construct())

                            self.peer.client_choking = False
                            self.peer.client_interested = True

            except Exception as e:
                print(f"{self.name} super Error!: {e}")
                if not self.stream.is_closed(): await self.stream.close()
                self.peers.task_done()
                continue

            await self.stream.close()

        print(f"{self.name}: Finished")

    async def download_piece(self):
        blocks_needed = self.state["piece"]["length"]/self.BLOCK_SIZE

        while blocks_needed > self.state["downloaded_blocks"]:
            while self.state["pipelined_requests"] < self.NUM_REQUESTS and self.state["block_num"] < blocks_needed:
                request_length = self.BLOCK_SIZE
                
                if (remaining_length := self.state["piece"]["length"] - self.state["block_num"] * self.BLOCK_SIZE) < self.BLOCK_SIZE:
                    request_length = remaining_length

                request_msg = Request(self.state["piece"]["index"], 
                                        self.state["block_num"] * self.BLOCK_SIZE, 
                                        request_length)

                self.stream.write(request_msg.construct())
                await self.stream.drain()

                self.state["block_num"] += 1
                self.state["pipelined_requests"] += 1


            await asyncio.create_task(self.handle_message())

    async def get_valid_piece(self):
        while True:
            (piece_index, piece_hash, piece_length) = await self.pieces.get()
            try:
                if not self.peer.has_bit(piece_index):
                    # print("Peer does not have piece")
                    await self.pieces.put((piece_index, piece_hash, piece_length))
                    self.pieces.task_done()
                    print("put")
                    continue

                return DownloadState(self.stream, piece_hash, piece_index, piece_length)
            except:
                await self.pieces.put((piece_index, piece_hash, piece_length))
                self.pieces.task_done()
                print("put")
                continue

    def verify_piece(self, piece):
        piece = bytes(piece)
        piece_hash = self.state["piece"]["hash"]
        if sha1(piece).digest() != self.state["piece"]["hash"]:
            return False

        return True

    ## create a connection with a peer
    async def connect(self, peer):
        conn = asyncio.open_connection(host=peer.host.exploded, port=peer.port)
        
        try:
            reader, writer = await asyncio.wait_for(conn, timeout=3)
        except asyncio.TimeoutError:
            raise AsyncConnectionError(f"{self.name} {peer} connection attempt timed out")
        except ConnectionRefusedError:
            raise AsyncConnectionError(f"{self.name} peer {peer} refused to connect")
        except Exception as e:
            raise AsyncConnectionError(f"{self.name} error - {e}")

        return AsyncStream(reader, writer)

    ## exchange a handshake with a peer
    async def exchange_handshakes(self, handshake):
        handshake = await self.construct_handshake()
        self.stream.write(handshake)
        await self.stream.drain()

        response = await self.stream.read(68)
        # print(f"{self.name} exchanged handshake")

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

class InvalidHandshake(Exception):
    pass

class AsyncConnectionError(Exception):
    pass

class AsyncStream:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def read(self, nbytes: int):
        a = await asyncio.wait_for(asyncio.create_task(self.read_internal(nbytes)), timeout=150)
        return a

    async def read_internal(self, nbytes: int):
        response = b""
        counter = 0
        while nbytes != 0:
            recieved_data = await asyncio.wait_for(self.reader.read(nbytes), 2)

            if recieved_data:
                nbytes -= len(recieved_data)
                response += recieved_data
            # if len(recieved_data) != 0:
            #     print(f"Recieved {len(recieved_data)} bytes")

        # print(f"response length: {len(response)}")
        return response

    def write(self, bytestring: bytes):
        self.writer.write(bytestring)

    async def drain(self):
        await self.writer.drain()

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()

    def is_closed(self):
        return self.writer.is_closing()