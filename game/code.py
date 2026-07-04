"""Game codes: a short friendly code that encodes the host's address.

`99.242.69.229:26501` becomes something like `35QM-8YKF` — friends type the
code instead of an IP. Codes are pure encoding (Crockford base32 of the
IP/port bytes), so no matchmaking server is needed and nothing can go down.
"""
from .constants import NET_PORT

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # Crockford base32
_FIX = str.maketrans({"I": "1", "L": "1", "O": "0", "U": "V"})


def encode_addr(ip, port=NET_PORT):
    """4-byte IP (default port) -> 7 chars; custom port -> 10 chars."""
    try:
        data = bytes(int(x) for x in ip.split("."))
    except ValueError:
        raise ValueError("not an IPv4 address") from None
    if len(data) != 4:
        raise ValueError("not an IPv4 address")
    if port != NET_PORT:
        data += int(port).to_bytes(2, "big")
    length = 7 if len(data) == 4 else 10
    n = int.from_bytes(data, "big")
    chars = []
    for _ in range(length):
        chars.append(ALPHABET[n & 31])
        n >>= 5
    s = "".join(reversed(chars))
    return f"{s[:4]}-{s[4:]}"


def decode_code(text):
    """Returns (ip, port). Tolerates dashes/spaces/lowercase and the usual
    lookalike characters (O->0, I/L->1). Raises ValueError if invalid."""
    s = text.strip().upper().replace("-", "").replace(" ", "").translate(_FIX)
    if len(s) not in (7, 10):
        raise ValueError("game codes are 7 or 10 characters")
    n = 0
    for ch in s:
        if ch not in ALPHABET:
            raise ValueError(f"invalid character {ch!r}")
        n = n * 32 + ALPHABET.index(ch)
    nbytes = 4 if len(s) == 7 else 6
    try:
        data = n.to_bytes(nbytes, "big")
    except OverflowError:
        raise ValueError("invalid game code") from None
    ip = ".".join(str(b) for b in data[:4])
    port = NET_PORT if nbytes == 4 else int.from_bytes(data[4:], "big")
    return ip, port


def parse_join_target(text):
    """Accepts a game code OR a raw ip[:port]; returns (ip, port)."""
    t = text.strip()
    if "." in t:                            # raw address
        ip, _, p = t.partition(":")
        return ip, int(p) if p.isdigit() else NET_PORT
    return decode_code(t)
