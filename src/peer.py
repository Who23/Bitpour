import ipaddress

class Peer:
    def __init__(self, raw_ip_bytes):
        self.host = ipaddress.ip_address(raw_ip_bytes[:4])
        self.port = int.from_bytes(raw_ip_bytes[4:], byteorder="big")

        # are we choking/interested in the peer
        self.client_choking = True
        self.client_interested = False

        # is the peer choking/interested in us
        self.peer_choking = True
        self.peer_interested = False


class ConnectedPeer()