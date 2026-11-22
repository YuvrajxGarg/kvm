"""Kvm's cryptography.

Pairing   SPAKE2 over a 6-digit code shown on one computer and typed on the other (same scheme
          as Hop). Someone on the Wi-Fi sees only the SPAKE2 messages, which don't let them test
          guesses offline, and each code allows a single guess. The result is a 32-byte pair key.
Sessions  Every connection makes fresh keys from the pair key and two random nonces, one per
          direction, and seals each frame with ChaCha20-Poly1305 using a counter nonce, so frames
          can't be replayed, reordered or moved to the other direction.
"""

import hashlib
import hmac
import os
import secrets
import struct

from nacl import bindings as _nb
from spake2 import SPAKE2_A, SPAKE2_B

KEY_BYTES = 32
TAG_BYTES = 16


class CryptoError(Exception):
    pass


def new_code():
    """Six digits, shown as 123 456."""
    return "%06d" % secrets.randbelow(1000000)


def normalize_code(code):
    return "".join(ch for ch in str(code) if ch.isdigit())


def random_id(n=8):
    return os.urandom(n).hex()


# ---- pairing ---------------------------------------------------------------

def _derive(raw):
    key = hashlib.blake2b(raw, digest_size=32, person=b"kvm-pair-key").digest()
    ca = hashlib.blake2b(raw, digest_size=32, person=b"kvm-confirm-A").digest()
    cb = hashlib.blake2b(raw, digest_size=32, person=b"kvm-confirm-B").digest()
    return key, ca, cb


class PairResponder(object):
    """The computer that shows the code: answers one guess."""

    def __init__(self, code, initiator_id, responder_id):
        self.code = code
        self.s = SPAKE2_B(code.encode(), idA=initiator_id.encode(), idB=responder_id.encode())
        self.msg_b = self.s.start()

    def finish(self, msg_a, confirm_a):
        try:
            raw = self.s.finish(msg_a)
        except Exception:
            raise CryptoError("bad pairing message")
        key, ca, cb = _derive(raw)
        if not hmac.compare_digest(ca, confirm_a):
            raise CryptoError("wrong code")
        return key, cb


def pair_initiate(code, initiator_id, responder_id, msg_b):
    """The computer where the code is typed. Returns (msg_a, confirm_a, key, expected_confirm_b)."""
    s = SPAKE2_A(normalize_code(code).encode(), idA=initiator_id.encode(), idB=responder_id.encode())
    msg_a = s.start()
    try:
        raw = s.finish(msg_b)
    except Exception:
        raise CryptoError("bad pairing message")
    key, ca, cb = _derive(raw)
    return msg_a, ca, key, cb


# ---- sessions --------------------------------------------------------------

def session_keys(pair_key, dialer_nonce, listener_nonce):
    """(dialer->listener key, listener->dialer key, proof) for one connection."""
    salt = dialer_nonce + listener_nonce
    d2l = hashlib.blake2b(salt, key=pair_key, digest_size=32, person=b"kvm-d2l").digest()
    l2d = hashlib.blake2b(salt, key=pair_key, digest_size=32, person=b"kvm-l2d").digest()
    return d2l, l2d


class Sealer(object):
    def __init__(self, key):
        self.key = key
        self.n = 0

    def seal(self, data):
        self.n += 1
        nonce = b"\0\0\0\0" + struct.pack(">Q", self.n)
        return _nb.crypto_aead_chacha20poly1305_ietf_encrypt(bytes(data), None, nonce, self.key)


class Opener(object):
    def __init__(self, key):
        self.key = key
        self.n = 0

    def open(self, blob):
        self.n += 1
        nonce = b"\0\0\0\0" + struct.pack(">Q", self.n)
        try:
            return _nb.crypto_aead_chacha20poly1305_ietf_decrypt(bytes(blob), None, nonce, self.key)
        except Exception:
            raise CryptoError("frame failed authentication")


# ---- phones: pairing by QR code ---------------------------------------------
# The computer shows a QR code holding a fresh 32-byte secret (good for one phone, for a few
# minutes). Seeing the screen is the proof: the phone answers with an HMAC of its id under the
# secret, the computer answers with one of its own id, and both keep a pair key made from the
# secret. Sessions then work exactly like between two computers.

def qr_proof(secret, who, ident):
    """who is b"phone" or b"desktop"."""
    return hmac.new(bytes(secret), who + b":" + ident.encode("utf-8"), hashlib.sha256).digest()


def qr_pair_key(secret):
    return hashlib.blake2b(bytes(secret), digest_size=32, person=b"kvm-qr-key").digest()
