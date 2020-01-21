#!/usr/bin/env python3.8
import sys
import asyncio
import socket

from random import randint
from enum import Enum

from bencode import BEncodeDecodeError
from urllib.request import URLError

from torrent import Torrent
from tracker import Tracker, TrackerParseError
from peer import Peer


# Peer ID that identifies the client.
ID = bytes('-BU0000-' + ''.join([chr(randint(0, 255)) for _ in range(12)]), "latin1")

# Port # we are listening on
PORT = 6881

## helper function to write to stderr and quit
def error_quit(error):
    sys.stderr.write("Error: " + error + "\n")
    sys.exit(1)

def main():
    # make sure a file name is provided
    if len(sys.argv) < 2:
        error_quit("File name not provided")


    ## attempt to decode torrent
    torrent = None
    try:
        torrent = Torrent(sys.argv[1])

    except OSError as e:
        error_quit(f"Could not open torrent file - {e}")

    except BEncodeDecodeError as e:
        error_quit(f"Could not decode torrent file - {e}")

    except Exception as e:
        error_quit(f"Unexpected error! - {e}")
        


    ## attempt to contact tracker
    tracker = Tracker(torrent, ID, PORT)
    try:
        response = tracker.request()

    except TrackerParseError as e:
        error_quit(f"Tracker Parsing error - {e}")

    except URLError as e:
        error_quit(f"Could not connect to tracker: {e}")

    except BEncodeDecodeError as e:
        error_quit(f"Malformed tracker response: {e}")

    except Exception as e:
        error_quit(f"Unexpected error! - {e}")



    # make sure the peers blob is correct
    if len(response["peers"]) % 6 != 0 or len(response["peers6"]) % 8 != 0:
        error_quit("Malformed peers list")

    raw_peers = [response["peers"][i:i+6]  for i in range(0, len(response["peers"]), 6)]

    # peers we are attempting to request pieces from
    seed_peers = []
    for peer_bytes in raw_peers:
        try:
            seed_peers.append(Peer(peer_bytes))
        except ValueError as e:
            print(f"Could not parse {peer_bytes}'s ip: {e}")


    asyncio.run(do_connect(seed_peers, torrent))

    
## async function to connect and download from peers
async def do_connect(peers, torrent):
    peer_queue = asyncio.Queue()
    pieces_queue = asyncio.Queue()

    [peer_queue.put_nowait(peer) for peer in peers]
    [pieces_queue.put_nowait(piece) for piece in torrent.pieces]

    handlers = [asyncio.create_task(handle_peer(f"thread {x}", peer_queue, pieces_queue, ID, torrent.info_hash)) for x in range(1)]
    print("handlers finished")
    await pieces_queue.join()
    [handler.cancel() for handler in handlers]


## constructs a handshake to send to peers
async def construct_handshake(peer_id, info_hash):
    handshake = b"\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00"
    handshake += info_hash
    handshake += peer_id

    return handshake


## check if the given handshake is valid
async def valid_handshake(handshake, info_hash):

    # make sure the protocol is correct
    if handshake[:20] != b"\x13BitTorrent protocol" : return False

    # make sure it is the correct file
    if handshake[28:48] != info_hash : return False

    return True

class InvalidHandshake(Exception):
    pass

async def exchange_handshakes(reader, writer, peer_id, info_hash):
    
    handshake = await construct_handshake(peer_id, info_hash)
    writer.write(handshake)
    await writer.drain()

    response = await reader.read(68)
    print("Recieved handshake")
    print(f"Handshake: {response}")
    if not await valid_handshake(response, info_hash):
        writer.close()
        await writer.wait_closed()
        raise InvalidHandshake


MSG_TYPE = {
    0 : "CHOKE",
    1 : "UNCHOKE",
    2 : "INTERESTED",
    3 : "UNINTERESTED",
    4 : "HAVE",
    5 : "BITFIELD",
    6 : "REQUEST",
    7 : "PIECE",
    8 : "CANCEL"
}

class MessageParseError(Exception):
    pass
class Message:
    def __init__(self, raw_message):
        try:
            self.payload = []
            self.msg_type = MSG_TYPE[raw_message[0]]

            if self.msg_type in ["HAVE", "BITFIELD"]:
                self.payload.append(raw_message[1:])

            elif self.msg_type in ["REQUEST", "CANCEL"]:
                raw_payloaod = raw_message[1:]
                self.payload = [raw_payloaod[x : x + 4] for x in range(0, 12, 4)]

            elif self.msg_type == "PIECE":
                self.payload.append(raw_message[1:5])
                self.payload.append(raw_message[5:9])
                self.payload.append(raw_message[9:])
        except Exception as e:
            raise MessageParseError(e)


        


async def handle_peer(name, peer_queue, pieces_queue, peer_id, info_hash):
    while True:
        peer = await peer_queue.get()
        print(f"{name}: Attempting {peer.host.exploded}:{peer.port}...")
        conn = asyncio.open_connection(host=peer.host.exploded, port=peer.port)
        
        try:
            reader, writer = await asyncio.wait_for(conn, timeout=3)
        except asyncio.TimeoutError:
            print(f"{name}: {peer} connection attempt timed out")
            peer_queue.task_done()
            continue
        except ConnectionRefusedError:
            print(f"{name}: peer {peer} refused to connect")
            peer_queue.task_done()
            continue
        except Exception as e:
            print(f"{name}: error - {e}")
            peer_queue.task_done()
            continue

        print(f"{name}: Connected to {peer.host.exploded}:{peer.port}")
        ## Exchange handshakes
        try:
            await exchange_handshakes(reader, writer, peer_id, info_hash)
        except InvalidHandshake:
            print("{name}: Invalid handshake")
            peer_queue.task_done()
            continue
        except Exception as e:
            print(e)

        ## Process Messages
        print("Awaiting messages")

        length = int.from_bytes(await reader.read(4), byteorder="big")
        print(f"Message len: {length}")
        msg = await reader.read(length)

        try:
            msg = Message(msg)
        except MessageParseError as e:
            writer.close()
            await writer.wait_closed()
            peer_queue.task_done()
            continue
        
        print(f"Type: {msg.msg_type}")
        print(f"Payload: {msg.payload}")

        break



if __name__ == "__main__":
    main()