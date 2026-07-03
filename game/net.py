"""UDP networking: host (authoritative relay) and client.

Datagrams are JSON, zlib-compressed when large ('Z' prefix) or plain ('J').
UDP keeps latency minimal; everything important is either resent continuously
(snapshots are idempotent) or client-authoritative (your own player), so a
lost packet never blocks the game.
"""
import json
import socket
import time
import zlib

from .constants import NET_PORT, NET_TIMEOUT, MAX_PLAYERS, PROTOCOL_VERSION


def encode(msg):
    raw = json.dumps(msg, separators=(",", ":")).encode()
    if len(raw) > 900:
        return b"Z" + zlib.compress(raw, 1)
    return b"J" + raw


def decode(data):
    try:
        if data[:1] == b"Z":
            return json.loads(zlib.decompress(data[1:]))
        return json.loads(data[1:])
    except (ValueError, zlib.error):
        return None


def local_ip():
    """Best-effort LAN IP for displaying to the host player."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


class Host:
    """Listens for clients; player id 0 is always the host's own player."""

    def __init__(self, port=NET_PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.bind(("0.0.0.0", port))
        self.port = port
        self.peers = {}                     # addr -> peer dict
        self.by_pid = {}                    # pid -> addr
        self.next_pid = 1

    def poll(self):
        """Returns list of (pid, msg). Handles join/ping/leave internally."""
        out = []
        now = time.time()
        while True:
            try:
                data, addr = self.sock.recvfrom(65536)
            except BlockingIOError:
                break
            except OSError:
                break
            msg = decode(data)
            if msg is None:
                continue
            t = msg.get("t")
            if t == "join":
                self._handle_join(addr, msg)
                continue
            peer = self.peers.get(addr)
            if peer is None:
                continue
            peer["last"] = now
            if t == "ping":
                self._send(addr, {"t": "pong", "ts": msg["ts"]})
            elif t == "leave":
                self._drop(addr)
            else:
                out.append((peer["pid"], msg))
        # timeouts
        for addr in [a for a, p in self.peers.items()
                     if now - p["last"] > NET_TIMEOUT]:
            self._drop(addr)
        return out

    def _handle_join(self, addr, msg):
        if msg.get("v") != PROTOCOL_VERSION:
            self._send(addr, {"t": "reject", "why": "version mismatch"})
            return
        if addr in self.peers:
            peer = self.peers[addr]           # re-send welcome (dup join)
        elif len(self.peers) + 1 >= MAX_PLAYERS:
            self._send(addr, {"t": "reject", "why": "game is full"})
            return
        else:
            peer = {"pid": self.next_pid, "name": msg.get("name", "P?")[:10],
                    "char": msg.get("char", 0), "last": time.time()}
            self.peers[addr] = peer
            self.by_pid[peer["pid"]] = addr
            self.next_pid += 1
        self._send(addr, {"t": "welcome", "pid": peer["pid"]})

    def _drop(self, addr):
        peer = self.peers.pop(addr, None)
        if peer:
            self.by_pid.pop(peer["pid"], None)

    def _send(self, addr, msg):
        try:
            self.sock.sendto(encode(msg), addr)
        except OSError:
            pass

    def send_all(self, msg):
        data = encode(msg)
        for addr in list(self.peers):
            try:
                self.sock.sendto(data, addr)
            except OSError:
                pass

    def player_ids(self):
        return [0] + sorted(self.by_pid)

    def close(self):
        self.send_all({"t": "end"})
        self.sock.close()


class Client:
    def __init__(self, host_ip, port=NET_PORT):
        self.addr = (host_ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.pid = None
        self.rtt = 0.0
        self.last_recv = time.time()
        self._last_ping = 0.0

    def join(self, name, char):
        self.send({"t": "join", "v": PROTOCOL_VERSION, "name": name, "char": char})

    def send(self, msg):
        try:
            self.sock.sendto(encode(msg), self.addr)
        except OSError:
            pass

    def poll(self):
        """Returns list of msgs; handles welcome/pong internally too
        (welcome and reject are passed through so the UI can react)."""
        out = []
        now = time.time()
        if now - self._last_ping > 1.0:
            self._last_ping = now
            self.send({"t": "ping", "ts": now})
        while True:
            try:
                data, addr = self.sock.recvfrom(65536)
            except BlockingIOError:
                break
            except OSError:
                break
            if addr[0] != self.addr[0]:
                continue
            msg = decode(data)
            if msg is None:
                continue
            self.last_recv = now
            t = msg.get("t")
            if t == "welcome":
                self.pid = msg["pid"]
            elif t == "pong":
                self.rtt = now - msg["ts"]
                continue
            out.append(msg)
        return out

    @property
    def timed_out(self):
        return time.time() - self.last_recv > NET_TIMEOUT

    def close(self):
        self.send({"t": "leave"})
        self.sock.close()
