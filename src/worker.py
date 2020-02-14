from peer import Peer
from download_state import *
from message import *
import struct
from hashlib import sha1
import asyncio

import logging
logging.basicConfig(level=logging.INFO)

class Worker:
    def __init__(self, name, torrent, peer_id, peer_q, pieces_q, downloaded_q):
        self.info_hash = torrent.info_hash
        self.peer_id = peer_id

        self.BLOCK_SIZE = 16384
        self.NUM_REQUESTS = 10

        self.state = DownloadState(0, b"", 0)

        self.peers = peer_q
        self.pieces = pieces_q
        self.downloaded_q = downloaded_q
        self.name = name

    async def run(self):
        logging.info(f"{self.name}: start!")
        while self.pieces.qsize() > 0:
            self.peer = await self.peers.get()

            # attempt to connect to a peeer
            try:
                self.stream = await self.connect(self.peer)
            except Exception as e:
                logging.error(f"{self.name}: {e}")
                self.peers.task_done()
                continue

            logging.info(f"{self.name}: Connected to {self.peer.host.exploded}:{self.peer.port}")

            # attempt to exchange handshakes with a peer, with a limit of 30 seconds
            try:
                handshake = await self.construct_handshake()
                await asyncio.wait_for(self.exchange_handshakes(handshake), timeout=30)
            except Exception as e:
                logging.error(f"{self.name}: {e}")
                self.peers.task_done()
                if not self.stream.is_closed(): await self.stream.close()
                continue

            try:
                # while there are pieces to download, we want to also keep trying to download pieces from a peer
                while self.pieces.qsize() > 0:

                    if not self.peer.peer_choking:

                        # get a valid piece -> update the state
                        await self.get_valid_piece()
                        logging.info(f"{self.name} processing {self.state.piece.index}")
                        logging.debug("got piece")

                        try:

                            # download a piece
                            logging.debug("downloading piece")
                            await self.download_piece()

                            # if the piece does not match the given hash, put it back into the work queue and continue
                            if not self.verify_piece(bytes(self.state.piece_buf)):
                                await self.pieces.put((self.state.piece.index, self.state.piece.hash, self.state.piece.length))
                                self.pieces.task_done()
                                continue

                            # put the downloaded piece in the finished queue
                            await self.downloaded_q.put((self.state.piece.index, bytes(self.state.piece_buf)))
                            self.pieces.task_done()

                            logging.debug("doned")
                            logging.info(f"{self.name} downloaded {self.state.piece.index}")

                        except Exception as e:
                            await self.pieces.put((self.state.piece.index, self.state.piece.hash, self.state.piece.length))
                            self.pieces.task_done()
                            logging.debug("put")
                            logging.info(f"{self.name} Error!: {e}")
                            if self.stream.is_closed(): break
                            continue

                    else:

                        # if we are not unchoked, just wait for the next message
                        await asyncio.create_task(self.handle_message())

                        # make sure we are interested and not choking
                        if self.peer.client_choking and not self.peer.peer_choking:
                            self.stream.write(Unchoke().construct())
                            self.stream.write(Interested().construct())

                            self.peer.client_choking = False
                            self.peer.client_interested = True

            except Exception as e:
                # close the connection on an error
                logging.error(f"{self.name} super Error!: {e}")
                if not self.stream.is_closed(): await self.stream.close()
                self.peers.task_done()
                continue

            logging.debug(f"Current: {self.pieces.qsize()}")
            if not self.stream.is_closed(): await self.stream.close()

        logging.info(f"{self.name}: Finished")


    # download a piece from a peer
    async def download_piece(self):
        # calculate the number of blocks needed
        blocks_needed = self.state.piece.length/self.BLOCK_SIZE

        while blocks_needed > self.state.downloaded_blocks:

            # this blocks pipelines requests for blocks
            while self.state.pipelined_requests < self.NUM_REQUESTS and self.state.block_num < blocks_needed:
                request_length = self.BLOCK_SIZE
                
                # if the length left to download in the piece is less than the BLOCK_SIZE, set it to how much ever we need to download
                if (remaining_length := self.state.piece.length - self.state.block_num * self.BLOCK_SIZE) < self.BLOCK_SIZE:
                    request_length = remaining_length

                request_msg = Request(self.state.piece.index, 
                                        self.state.block_num * self.BLOCK_SIZE, 
                                        request_length)

                self.stream.write(request_msg.construct())
                await self.stream.drain()
                logging.debug("sent request")

                self.state.block_num += 1
                self.state.pipelined_requests += 1

            # handle a message, this will usually be a block
            await asyncio.wait_for(self.handle_message(), timeout=45)

    
    # get a valid piece from the queue
    async def get_valid_piece(self):
        while True:
            (piece_index, piece_hash, piece_length) = await self.pieces.get()
            
            try:
                # if the peer does not have the piece, then put it back on the queue
                if not self.peer.has_bit(piece_index):
                    logging.info("Peer does not have piece")
                    await self.pieces.put((piece_index, piece_hash, piece_length))
                    self.pieces.task_done()
                    continue

                # update the state
                self.state = DownloadState(piece_index, piece_hash, piece_length)
                return

            except:
                await self.pieces.put((piece_index, piece_hash, piece_length))
                self.pieces.task_done()
                # print("put")
                continue


    # verify whether a piece is legitimate
    def verify_piece(self, piece):
        piece = bytes(piece)
        piece_hash = self.state.piece.hash
        if sha1(piece).digest() != self.state.piece.hash:
            return False

        return True


    # attempt to read and handle a message
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
            # get the message length (part of the protocol)
            msg_length = int.from_bytes(await self.stream.read(4), byteorder="big")

            # read the message and parse it
            raw_message = await self.stream.read(msg_length)
            msg = parse_message(raw_message)

            # if it is a KeepAlive, re-read until we get a get an actual message
            if isinstance(msg, KeepAlive): 
                # print("KeepAlive")
                continue

            # otherwise handle the message and return
            MSG_TYPE[msg.id](msg)
            break

    ## create a connection with a peer
    async def connect(self, peer):
        logging.info(f"{self.name}: Attempting {peer.host.exploded}:{peer.port}...")
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
        logging.info(f"{self.name} exchanged handshake")

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
        logging.debug(f"{self.name} Choked")
        self.peer.peer_choking = True

    def handle_unchoke(self, msg):
        logging.debug(f"{self.name} Unchoked")
        self.peer.peer_choking = False

    def handle_interested(self, msg):
        logging.debug(f"{self.name} Interested")
        self.peer.peer_interested = True

    def handle_uninterested(self, msg):
        logging.debug(f"{self.name} Uninterested")
        self.peer.peer_interested = False

    def handle_have(self, msg):
        logging.debug(f"{self.name} Have")
        self.peer.set_bit(msg.piece_index, 1)

    def handle_bitfield(self, msg):
        logging.debug(f"{self.name} Bitfield")
        self.peer.bitfield = bytearray(msg.bitfield)

    def handle_request(self, msg):
        logging.debug(f"{self.name} Request")

    def handle_piece(self, msg):
        logging.debug(f"{self.name} Piece")
        if msg.index != self.state.piece.index:
            raise ValueError

        block_length = len(msg.block)

        self.state.piece_buf[msg.begin:msg.begin+block_length] = msg.block
        self.state.pipelined_requests -= 1
        self.state.downloaded_blocks += 1

    def handle_cancel(self, msg):
        logging.debug(f"{self.name} Cancel")



class InvalidHandshake(Exception):
    pass

class AsyncConnectionError(Exception):
    pass

class AsyncStream:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def read(self, nbytes: int):
        a = await asyncio.wait_for(asyncio.create_task(self.read_internal(nbytes)), timeout=130)
        return a

    async def read_internal(self, nbytes: int):
        response = b""
        counter = 0
        while nbytes != 0:
            try:
                recieved_data = await asyncio.wait_for(self.reader.read(nbytes), 5)
            except asyncio.TimeoutError:
                recieved_data = b""


            if recieved_data:
                nbytes -= len(recieved_data)
                response += recieved_data

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