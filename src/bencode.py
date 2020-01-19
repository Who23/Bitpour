# functions to deocde a BEncoded string to a python object
# also a exception

class BEncodeDecodeError(Exception):
    pass

## tokenize raw bencode bytestring
def tokenize_bencode(bencode):
    index = 0
    number = ""
    while index < len(bencode):
        # d, l, i
        # return the character as a bytestring
        if bencode[index] in [100, 108, 105]:
            yield bytes(chr(bencode[index]), "utf8")

        # 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -
        # store the number in a string to be decoded
        elif (48 <= bencode[index] <= 57) or bencode[index] == 45:
            number += chr(bencode[index])

        # :
        # colon means number has the length of the bytestring 
        # return the bytestring between "s" and "e" tokens for future ease
        elif bencode[index] == 58:
            index += 1
            byte_string_length = int(number)
            byte_string =  bencode[(index):(byte_string_length + index)]

            index += byte_string_length - 1
            number = ""

            yield b"s"
            yield byte_string
            yield b"e"

        # e
        # if number has any value in it, it must be of an int
        # return the number and the e token
        elif bencode[index] == 101:
            if number:
                yield bytes(number, "utf8")
                number = ""

            yield b"e"

        # there are no other valid tokens. quit with an error.
        else:
            raise BEncodeDecodeError("Invalid BEncode")

        index += 1

## parse bencode tokens into an object
def parse_token(token, gen):
    
    # parse int
    if token == b'i':
        number = int(next(gen))
        if next(gen) != b"e":
            raise BEncodeDecodeError("Invalid BEncode")

        return number

    # parse string - why the s token was added earlier
    elif token == b's':
        string = next(gen)
        if next(gen) != b"e":
            raise BEncodeDecodeError("this shouldn't be possible unless the tokenize function has been messed with :P")

        # It may not be able to be parsed as a string - as in the hashes of the pieces
        try:
            return string.decode()
        except UnicodeDecodeError:
            return string

    # parse list via recursively calling parse_token
    elif token == b'l':
        array = []
        while (next_token := next(gen)) != b"e":
            array.append(parse_token(next_token, gen))

        return array

     # parse dict via recursively calling parse_token
    elif token == b'd':
        items = []
        while (next_token := next(gen)) != b"e":
            items.append(parse_token(next_token, gen))
        
        return dict(zip(items[0::2], items[1::2]))

## encode an object into a bencode bytestring
def encode(obj):

    # parse dict by recursively encoding keys and values
    if isinstance(obj, dict):
        bencode = b"d"
        for (key, value) in obj.items():
            bencode += encode(key)
            bencode += encode(value)
        bencode += b"e"

        return bencode

    # parse list by recursively encoding keys and values
    elif isinstance(obj, list):
        bencode = "l"
        for item in obj:
            bencode += encode(item)
        bencode += "e"

        return bencode

    # concatenate length and bytes - bytestrings usually for pieces hash blob
    elif isinstance(obj, bytes):
        bencode = bytes(str(len(obj)) + ":", "utf8")
        bencode += obj
        return bencode

    # concatenate length and str
    elif isinstance(obj, str):
        bencode = bytes(str(len(obj)) + ":" + obj, "utf8")
        return bencode

    elif isinstance(obj, int):
        return bytes("i" + str(obj) + "e", "utf8")

## take a raw bencode string and return a python object
def decode(bencode):
    tokens = tokenize_bencode(bencode)
    obj = parse_token(next(tokens), tokens)
    for _ in tokens:
        raise BEncodeDecodeError("Invalid Bencode - trailing tokens")

    return obj