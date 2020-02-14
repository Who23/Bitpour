class DownloadState:
    def __init__(self, piece_index, piece_hash, piece_length):
        self.piece = PieceInfo(piece_index, piece_hash, piece_length)

        self.pipelined_requests = 0
        self.block_num = 0
        self.downloaded_blocks = 0
        self.piece_buf = bytearray(piece_length)


class PieceInfo:
    def __init__(self, index, hash, length):
        self.index = index
        self.hash = hash
        self.length = length