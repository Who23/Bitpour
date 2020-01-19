#!/usr/bin/env python3.8
import sys
import bencode
import hashlib
from random import randint

# port to listen on
PORT = 6881
ID = bytes('(BU0000)' + chr(randint(0, 255)), "latin1")

## helper function to write to stderr and quit
def error_quit(error):
    sys.stderr.write("Error: " + error + "\n")
    sys.exit(1)


# def construct_request(metafile):
#     params = {
#         "info_hash"  : metafile["info_hash"]
#         "peer_id"    : ID
#         "port"       :
#         "uploaded"   :
#         "downloaded" :
#         "compact"    :
#         "left"       :
#     }

def main():
    print(ID)

    # make sure a file name is provided
    if len(sys.argv) < 2:
        error_quit("File name not provided")

    # attempt to open file
    metafile = {}
    try:
        with open(sys.argv[1], 'rb') as f:
            metafile = bencode.decode(f.read())

    except OSError as e:
        error_quit(f"Could not open torrent file - {e}")

    except bencode.BEncodeDecodeError as e:
        error_quit(f"Could not decode torrent file - {e}")

    # calculate the infohash nessecary for the announce request and put it in the metafile dict
    info_hash = hashlib.sha1(bencode.encode(metafile["info"])).hexdigest()
    metafile["info_hash"] = info_hash


if __name__ == "__main__":
    main()