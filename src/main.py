#!/usr/bin/env python3.8
import sys
from torrent import Torrent
from tracker import Tracker, TrackerParseError
from random import randint

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

    except bencode.BEncodeDecodeError as e:
        error_quit(f"Could not decode torrent file - {e}")

    except Exception as e:
        error_quit(f"Unexpected error! - {e}")
        

    ## attempt to contact tracker
    tracker = Tracker(torrent, ID, PORT)
    try:
        response = tracker.request()

    except TrackerParseError as e:
        error_quit(f"Tracker Parsing error - {e}")

    except Exception as e:
        error_quit(f"Unexpected error! - {e}")

    

    print(response)


if __name__ == "__main__":
    main()