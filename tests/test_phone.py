"""A phone pairs by scanning the QR code, then talks over the same sealed link as a computer.

FakePhone does in Python what the Android app does in Kotlin (android/core), so this test is
the reference for that code: the QR, the pairing proofs, the session keys and the messages.
"""

import base64
import hashlib
import json
import os
import shutil
import socket
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlparse

from kvm import crypto
from kvm.agent import Agent
from kvm.link import Link, decode, read_json, write_json
from kvm.platform.base import FakeBackend
from kvm.store import Store


def wait(cond, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def unb64url(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class FakePhone(object):
    def __init__(self, uri):
        q = {k: v[0] for k, v in parse_qs(urlparse(uri).query).items()}
        self.desk_id, self.port, self.secret = q["id"], int(q["p"]), unb64url(q["s"])
        self.hosts = q["h"].split(",")
        self.id = os.urandom(8).hex()
        self.got = []
        self.links = {}

    def pair(self, proof=None):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        write_json(s, {"t": "hello", "v": 1, "purpose": "pair_qr", "id": self.id, "name": "Pixel 9",
                       "platform": "android", "version": "1.0.0",
                       "proof": base64.b64encode(proof or crypto.qr_proof(self.secret, b"phone", self.id)).decode()})
        m = read_json(s)
        s.close()
        if m.get("t") == "paired":
            assert base64.b64decode(m["proof"]) == crypto.qr_proof(self.secret, b"desktop", m["id"])
            self.key = crypto.qr_pair_key(self.secret)
        return m

    def dial(self, purpose="main"):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        nonce = os.urandom(16)
        write_json(s, {"t": "hello", "v": 1, "purpose": purpose, "id": self.id, "name": "Pixel 9",
                       "platform": "android", "version": "1.0.0", "nonce": base64.b64encode(nonce).decode()})
        m = read_json(s)
        assert m["t"] == "hello" and m["id"] == self.desk_id, m
        d2l, l2d = crypto.session_keys(self.key, nonce, base64.b64decode(m["nonce"]))
        s.settimeout(None)
        link = Link(s, d2l, l2d, self.desk_id, purpose, self.id, lambda l, t, b: self.got.append(decode(t, b)), None)
        link.start()
        self.links[purpose] = link
        return link

    def msgs(self, t):
        return [m for m in self.got if m and m.get("t") == t]


class PhonePairing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.be = FakeBackend([(0, 0, 1440, 900)])
        self.mac = Agent(self.be, Store(os.path.join(self.tmp, "mac")), port=0, discover=False,
                         home_dir=os.path.join(self.tmp, "home")).start()

    def tearDown(self):
        for l in getattr(self, "phone", None) and self.phone.links.values() or []:
            l.close()
        self.mac.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def paired_phone(self):
        qr = self.mac.pair_phone()
        self.assertIn("<svg", qr["svg"])
        self.assertTrue(qr["uri"].startswith("kvm://pair?"))
        self.assertTrue(self.mac.status()["qr"])
        self.phone = FakePhone(qr["uri"])
        self.assertEqual(self.phone.pair()["t"], "paired")
        self.assertFalse(self.mac.status()["qr"])
        return self.phone

    def test_wrong_or_reused_code_is_refused(self):
        qr = self.mac.pair_phone()
        ph = FakePhone(qr["uri"])
        self.assertEqual(ph.pair(proof=b"x" * 32)["t"], "pair_err")
        self.assertEqual(ph.pair()["t"], "paired")
        other = FakePhone(qr["uri"])
        self.assertEqual(other.pair()["t"], "pair_err")  # one phone per code
        self.mac.pair_phone_cancel()

    def test_phone_link_notifications_clipboard_ring_and_files(self):
        ph = self.paired_phone()
        main = ph.dial("main")
        ph.dial("bulk")
        self.assertTrue(wait(lambda: any(p["connected"] for p in self.mac.status()["peers"])))
        peer = [p for p in self.mac.status()["peers"] if p["id"] == ph.id][0]
        self.assertEqual(peer["platform"], "android")
        self.assertEqual(peer["phone"]["notifs"], [])
        self.assertTrue(wait(lambda: ph.msgs("ready")))

        # Notifications show up here, and once only.
        main.msg({"t": "phone", "battery": 81, "charging": True, "model": "Pixel 9"})
        main.msg({"t": "notif", "key": "k1", "app": "WhatsApp", "title": "Mum", "text": "Dinner?", "ts": 1})
        main.msg({"t": "notif", "key": "k1", "app": "WhatsApp", "title": "Mum", "text": "Dinner? (2)", "ts": 2})
        # Wait for the second (updated) one: the messages arrive on the link's own thread.
        self.assertTrue(wait(lambda: [n["text"] for n in self.mac.status()["peers"][0]["phone"]["notifs"]] == ["Dinner? (2)"]
                             and self.mac.status()["peers"][0]["phone"]["battery"] == 81))
        self.assertEqual(self.be.posted.count(("action", "notify")), 1)
        main.msg({"t": "notif_gone", "key": "k1"})
        self.assertTrue(wait(lambda: not self.mac.status()["peers"][0]["phone"]["notifs"]))
        main.msg({"t": "notif", "key": "k2", "app": "Gmail", "title": "Hi", "text": "", "ts": 3})
        self.assertTrue(wait(lambda: self.mac.status()["peers"][0]["phone"]["notifs"]))
        self.mac.notif_dismiss(ph.id, "k2")
        self.assertTrue(wait(lambda: ph.msgs("notif_dismiss")))
        self.assertEqual(ph.msgs("notif_dismiss")[0]["key"], "k2")

        # Clipboard both ways, ring the phone.
        main.msg({"t": "clip", "kind": "text", "data": "from the phone"})
        self.assertTrue(wait(lambda: ("clip", "text") in self.be.posted))
        self.be.sink({"t": "clip", "kind": "text", "data": "from the mac"})
        self.assertTrue(wait(lambda: any(m.get("data") == "from the mac" for m in ph.msgs("clip"))))
        self.assertTrue(self.mac.action(ph.id, "ring"))
        self.assertTrue(wait(lambda: any(m.get("a") == "ring" for m in ph.msgs("action"))))

        # A photo from the phone.
        data = os.urandom(300000)
        bulk = ph.links["bulk"]
        bulk.msg({"t": "files", "tid": "t1", "from": "Pixel 9", "label": "IMG_1.jpg",
                  "items": [{"i": 0, "rel": "IMG_1.jpg", "size": len(data)}]})
        bulk.blob({"t": "piece", "tid": "t1", "i": 0}, data[:200000])
        bulk.blob({"t": "piece", "tid": "t1", "i": 0}, data[200000:])
        bulk.msg({"t": "file_done", "tid": "t1", "i": 0, "sha": hashlib.sha256(data).hexdigest()})
        bulk.msg({"t": "files_done", "tid": "t1"})
        self.assertTrue(wait(lambda: any(t["phase"] == "received" for t in self.mac.status()["transfers"])),
                        self.mac.status()["transfers"])
        path = os.path.join(self.mac.status()["receive_dir"], "IMG_1.jpg")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), data)

        # Forgetting the phone tells it.
        self.mac.forget(ph.id)
        self.assertTrue(wait(lambda: ph.msgs("unpair")))


class Vectors(unittest.TestCase):
    """The numbers android/core's tests check, so Kotlin and Python can't drift apart."""

    def test_vectors(self):
        path = os.path.join(os.path.dirname(__file__), "..", "android", "core", "src", "test", "resources", "vectors.json")
        with open(path) as f:
            v = json.load(f)
        secret = bytes.fromhex(v["secret"])
        self.assertEqual(crypto.qr_proof(secret, b"phone", v["phone_id"]).hex(), v["phone_proof"])
        self.assertEqual(crypto.qr_proof(secret, b"desktop", v["desk_id"]).hex(), v["desk_proof"])
        key = crypto.qr_pair_key(secret)
        self.assertEqual(key.hex(), v["pair_key"])
        d2l, l2d = crypto.session_keys(key, bytes.fromhex(v["dialer_nonce"]), bytes.fromhex(v["listener_nonce"]))
        self.assertEqual(d2l.hex(), v["d2l"])
        self.assertEqual(l2d.hex(), v["l2d"])
        s = crypto.Sealer(d2l)
        s.seal(b"first")
        self.assertEqual(s.seal(bytes.fromhex(v["plain"])).hex(), v["sealed_2"])


if __name__ == "__main__":
    unittest.main()
