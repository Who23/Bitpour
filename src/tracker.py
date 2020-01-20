import urllib.parse, urllib.request
import bencode

class TrackerParseError(Exception):
    pass

class Tracker:
    def __init__(self, torrent, peer_id, port):

        # bytes uploaded
        self.uploaded = 0

        # bytes downloaded
        self.downloaded = 0

        self.peer_id = peer_id
        self.port = port
        self.url = torrent.announce
        self.info_hash = torrent.info_hash
        self.file_size = torrent.length


    ## Construct a request to the tracker
    def construct_request(self):
        params = {
            "info_hash"  : self.info_hash,
            "peer_id"    : self.peer_id,
            "port"       : self.port,
            "uploaded"   : self.uploaded,
            "downloaded" : self.downloaded,
            "compact"    : 1,
            "left"       : self.file_size - self.downloaded,
        }

        ## parse url, encode and set params, and re-form url.
        try:
            request = urllib.parse.urlparse(self.url)
            params = urllib.parse.urlencode(params)
            request = request._replace(query=params)
            request = urllib.parse.urlunparse(request)
        except Exception as e:
            raise TrackerParseError(e)

        return request

    ## Send a request to the tracker and return a parsed response
    def request(self):
        tracker_request = self.construct_request()

        ## attempt to request tracker and decode the response
        with urllib.request.urlopen(tracker_request) as response:
            decoded_response = bencode.decode(response.read())

        return decoded_response

        