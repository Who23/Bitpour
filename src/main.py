#!/usr/bin/env python3.8
import sys
import bencode

## helper function to write to stderr and quit
def error_quit(error):
    sys.stderr.write("Error: " + error + "\n")
    sys.exit(1)

def main():
    # make sure a file name is provided
    if len(sys.argv) < 2:
        error_quit("File name not provided")

    # attempt to open file
    try:
        with open(sys.argv[1], 'rb') as f:
            bencode.decode(f.read())

    except OSError as e:
        error_quit(f"Could not open torrent file - {e}")

    except bencode.BEncodeDecodeError as e:
        error_quit(f"Could not decode torrent file - {e}")


if __name__ == "__main__":
    main()