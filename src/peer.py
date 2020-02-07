import ipaddress

class Peer:
    def __init__(self, raw_ip_bytes):
        self.host = ipaddress.ip_address(raw_ip_bytes[:4])
        self.port = int.from_bytes(raw_ip_bytes[4:], byteorder="big")

