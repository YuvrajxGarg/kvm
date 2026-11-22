"""One encrypted connection to a paired computer.

Wire format: every frame is a 4-byte big-endian length and then the bytes. Before the session
keys exist frames are plain JSON (pairing and the handshake). After that every frame is sealed
(crypto.Sealer) and its plaintext starts with a type byte:

  0x01 MOVE    int16 dx, int16 dy
  0x02 BUTTON  u8 button (1 left, 2 right, 3 middle, 4 back, 5 forward), u8 down
  0x03 WHEEL   f32 dx, f32 dy          (notches; positive dy scrolls up, positive dx right)
  0x04 KEY     u16 HID usage, u8 down
  0x10 JSON    a control message
  0x11 BLOB    u32 header length, JSON header, raw bytes (file pieces, clipboard pictures)

Each computer keeps two connections to a peer: "main" for input and control, which stays
short and quick, and "bulk" for files and pictures so they never hold the pointer back.
"""

import json
import os
import socket
import struct
import threading

from . import crypto

T_MOVE, T_BUTTON, T_WHEEL, T_KEY, T_JSON, T_BLOB = 0x01, 0x02, 0x03, 0x04, 0x10, 0x11
MAX_FRAME = 4 << 20


class LinkClosed(Exception):
    pass


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        b = sock.recv(n - len(buf))
        if not b:
            raise LinkClosed("connection closed")
        buf += b
    return bytes(buf)


def read_frame(sock):
    (n,) = struct.unpack(">I", _recv_exact(sock, 4))
    if n > MAX_FRAME:
        raise LinkClosed("frame too large")
    return _recv_exact(sock, n)


def write_frame(sock, data):
    sock.sendall(struct.pack(">I", len(data)) + data)


def read_json(sock):
    try:
        return json.loads(read_frame(sock).decode("utf-8"))
    except ValueError:
        raise LinkClosed("bad message")


def write_json(sock, obj):
    write_frame(sock, json.dumps(obj).encode("utf-8"))


def tune(sock):
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except OSError:
        pass


class Link(object):
    """A sealed connection. `on_frame(link, type, body)` runs on the reader thread."""

    def __init__(self, sock, send_key, recv_key, peer_id, purpose, dialer, on_frame, on_close):
        self.sock = sock
        self.peer_id = peer_id
        self.purpose = purpose
        self.dialer = dialer
        self.sealer = crypto.Sealer(send_key)
        self.opener = crypto.Opener(recv_key)
        self.on_frame = on_frame
        self.on_close = on_close
        self.lock = threading.Lock()
        self.closed = False
        self.id = os.urandom(4).hex()
        try:
            self.addr = sock.getpeername()[0]
        except OSError:
            self.addr = None

    def start(self):
        threading.Thread(target=self._reader, name="kvm-link-%s" % self.purpose, daemon=True).start()

    def _reader(self):
        try:
            while True:
                plain = self.opener.open(read_frame(self.sock))
                if not plain:
                    continue
                self.on_frame(self, plain[0], plain[1:])
        except (LinkClosed, OSError, crypto.CryptoError):
            pass
        except Exception:
            import traceback

            traceback.print_exc()
        self.close()

    def send(self, ftype, body=b""):
        if self.closed:
            return False
        try:
            with self.lock:
                write_frame(self.sock, self.sealer.seal(bytes([ftype]) + body))
            return True
        except OSError:
            self.close()
            return False

    # ---- typed helpers -----------------------------------------------------
    def move(self, dx, dy):
        return self.send(T_MOVE, struct.pack("<hh", max(-32768, min(32767, dx)), max(-32768, min(32767, dy))))

    def button(self, b, down):
        return self.send(T_BUTTON, struct.pack("<BB", b, 1 if down else 0))

    def wheel(self, dx, dy):
        return self.send(T_WHEEL, struct.pack("<ff", dx, dy))

    def key(self, hid, down):
        return self.send(T_KEY, struct.pack("<HB", hid, 1 if down else 0))

    def msg(self, obj):
        return self.send(T_JSON, json.dumps(obj).encode("utf-8"))

    def blob(self, header, data):
        h = json.dumps(header).encode("utf-8")
        return self.send(T_BLOB, struct.pack(">I", len(h)) + h + bytes(data))

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        if self.on_close:
            self.on_close(self)


def decode(ftype, body):
    """Frame body -> a dict like the backend's events."""
    if ftype == T_MOVE:
        dx, dy = struct.unpack("<hh", body[:4])
        return {"t": "move", "dx": dx, "dy": dy}
    if ftype == T_BUTTON:
        b, d = struct.unpack("<BB", body[:2])
        return {"t": "button", "b": b, "d": bool(d)}
    if ftype == T_WHEEL:
        dx, dy = struct.unpack("<ff", body[:8])
        return {"t": "wheel", "dx": dx, "dy": dy}
    if ftype == T_KEY:
        k, d = struct.unpack("<HB", body[:3])
        return {"t": "key", "k": k, "d": bool(d)}
    if ftype == T_JSON:
        return json.loads(body.decode("utf-8"))
    if ftype == T_BLOB:
        (n,) = struct.unpack(">I", body[:4])
        hdr = json.loads(body[4:4 + n].decode("utf-8"))
        hdr["_data"] = body[4 + n:]
        return hdr
    return None
