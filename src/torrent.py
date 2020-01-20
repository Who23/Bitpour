import bencode
from hashlib import sha1

# A class that represents the decoded torrent file/metafile
class Torrent:
    def __init__(self, torrent_path):

        ## open and decode torrent file
        with open(torrent_path, "rb") as f:
            metafile = bencode.decode(f.read())

        ## set variables for easier access
        self.announce = metafile["announce"]
        self.piece_length = metafile["info"]["piece length"]

        # split the concatenated sha hashes into a list of hashes
        self.pieces = [metafile["info"]["pieces"][i:i+20] for i in range(0, len(metafile["info"]["pieces"]), 20)]

        self.filename = metafile["info"]["name"]
        self.length = metafile["info"]["length"]
        self.info_hash = sha1(bencode.encode(metafile["info"])).digest()
