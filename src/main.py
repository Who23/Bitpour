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
from worker import Worker

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
    if len(response["peers"]) % 6 != 0:
        error_quit("Malformed peers list")


    # list of raw peer IPs and port
    raw_peers = [response["peers"][i:i+6] for i in range(0, len(response["peers"]), 6)]

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
    downloaded_queue = asyncio.Queue()

    [peer_queue.put_nowait(peer) for peer in peers]
    [pieces_queue.put_nowait((index, piece, torrent.get_piece_length(index))) for index, piece in enumerate(torrent.pieces)]

    handlers = [Worker(f"thread {x}", torrent, ID, peer_queue, pieces_queue, downloaded_queue) for x in range(15)]
    [asyncio.create_task(worker.run()) for worker in handlers]
    await asyncio.gather(handlers)
    print("handlers finished")

    await pieces_queue.join()
    [handler.cancel() for handler in handlers]

    downloaded_pieces = []
    for x in range(downloaded_queue.qsize):
        downloaded_pieces.append(await downloaded_queue.get())

    downloaded_pieces.sort(key=sort_index)

    with open(torrent.filename, "wb+") as f:
        for (piece_index, piece) in downloaded_pieces:
            f.write(piece)



def sort_index(q_item):
    return q_item[0]




# async def handle_peer(name, peer_queue, pieces_queue, peer_id, info_hash):
#     while True:


#         ## Exchange handshakes
#         try:
#             await exchange_handshakes(reader, writer, peer_id, info_hash)
#         except InvalidHandshake:
#             print("{name}: Invalid handshake")
#             peer_queue.task_done()
#             continue
#         except Exception as e:
#             print(e)


#         ## Process Messages
#         print("Awaiting messages")

#         length = int.from_bytes(await reader.read(4), byteorder="big")
#         print(f"Message len: {length}")
#         msg = await reader.read(length)

#         try:
#             msg = Message(msg)
#         except MessageParseError as e:
#             writer.close()
#             await writer.wait_closed()
#             peer_queue.task_done()
#             continue
        
#         print(f"Type: {msg.msg_type}")
#         print(f"Payload: {msg.payload}")

#         break


if __name__ == "__main__":
    main()
