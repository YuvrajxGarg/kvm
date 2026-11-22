"""The part of Kvm that talks to other computers.

It finds them (discovery.py), pairs with a 6-digit code, keeps an encrypted link to each paired
computer (link.py), and runs the one-pointer state machine:

  home     this computer's mouse and keyboard work here; the backend watches the edges
  driving  the pointer went over an edge: our input is captured and sent to `active`
  driven   another computer's input arrives and the backend puts it on this screen

On a Mac it runs inside the app. On Windows with the setup installed it runs in the Kvm service
(winservice.py), so it also works on the sign-in screen and on admin prompts, and the window
talks to it through control.py. All its public methods are what the window can call.
"""

import hashlib
import os
import socket
import threading
import time

from . import __version__, crypto, keys
from .link import (Link, LinkClosed, decode, read_json, tune, write_json)
from .screens import OPPOSITE, SIDES
from .store import Store, this_platform

PORT = 47610
PIECE = 512 * 1024
PAIR_TIMEOUT = 120
PING_EVERY = 1.0
DEAD_AFTER = 6.0


def b64e(b):
    import base64
    return base64.b64encode(b).decode("ascii")


def b64d(s):
    import base64
    return base64.b64decode(s)


class Peer(object):
    def __init__(self, pid):
        self.id = pid
        self.main = None
        self.bulk = None
        self.media = None                  # screen pictures (and later sound), so they never queue behind files
        self.version = None
        self.screens = None
        self.last_seen = 0.0
        self.connecting = False


class Agent(object):
    def __init__(self, backend, store=None, port=None, discover=True, home_dir=None):
        self._backend = backend
        self._store = store or Store()
        self._port = port if port is not None else int(os.environ.get("KVM_PORT") or PORT)
        self._discover = discover
        self._home_dir = home_dir          # the signed-in user's home (the service finds it)
        self._lock = threading.RLock()
        self._peers = {}                   # pid -> Peer (paired ones with links)
        self._nearby = {}                  # pid -> discovery record
        self._manual = {}                  # "host:port" added by hand -> record
        self._mode = "home"
        self._active = None
        self._side = None
        self._locked = False
        self._acc = [0.0, 0.0]
        self._pairing = None               # dict describing the pairing in progress
        self._pair_code_event = threading.Event()
        self._transfers = {}               # tid -> dict
        self._incoming = {}                # tid -> receive state
        self._notices = []
        self._notice_n = 0
        self._server = None
        self._disc = None
        self._stopped = False
        self._screens = []
        self._permissions = {}
        self._views = {}                   # pid -> the other computer's screen we're watching
        self._watchers = {}                # pid -> a computer watching our screen
        self._view_server = None
        self._hear = {}                    # pid -> {"phase", "error"}: we're hearing that computer
        self._listeners = set()            # pids hearing this computer
        self._mic_out = {}                 # pid -> {"phase", "error"}: our mic goes to that computer
        self._mic_in = set()               # pids whose mic plays into our virtual mic
        self._extend_out = {}              # pid -> {"phase", "error", "w", "h"}: our extra display shows there
        self._extend_in = {}               # pid -> {"w", "h"}: that computer's extra display shows here
        self._vrect = None                 # where our extra display is on our desktop
        self._cam_watchers = set()         # pids using our camera

    # ==== lifecycle ==============================================================
    def start(self):
        self._backend.start(self._on_backend)
        self._screens = self._backend.screens.public()
        self._listen()
        self._configure_backend()
        if self._discover:
            threading.Thread(target=self._start_discovery, daemon=True).start()
        threading.Thread(target=self._maintain, name="kvm-maintain", daemon=True).start()
        return self

    def stop(self):
        self._stopped = True
        try:
            self._backend.stop()
        except Exception:
            pass
        with self._lock:
            links = [l for p in self._peers.values() for l in (p.main, p.bulk, p.media) if l]
        for l in links:
            l.close()
        if self._server:
            try:
                self._server.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._server.close()
            except OSError:
                pass
        if self._disc:
            self._disc.stop()
        if self._view_server:
            self._view_server.stop()

    @property
    def port(self):
        return self._port

    def _start_discovery(self):
        from .discovery import Discovery
        try:
            self._disc = Discovery(self._store.id, self._store.name, self._port, __version__, this_platform(),
                                   self._on_discovery)
            self._disc.start(_lan_addresses())
        except Exception as e:
            self._log("discovery: %s" % e)

    def _on_discovery(self):
        if not self._disc:
            return
        found = {p["id"]: p for p in self._disc.peers()}
        with self._lock:
            self._nearby = found
        for pid, rec in found.items():
            if self._store.pair(pid):
                self._store.update_pair(pid, host=rec["host"], port=rec["port"], name=rec["name"])

    # ==== window API (also served by control.py) ===================================
    def status(self):
        with self._lock:
            pairs = self._store.pairs()
            peers = []
            seen = set()
            for pid, rec in pairs.items():
                p = self._peers.get(pid)
                connected = bool(p and p.main and not p.main.closed)
                peers.append({
                    "id": pid, "name": rec.get("name") or "Computer", "platform": rec.get("platform"),
                    "paired": True, "connected": connected, "online": connected or pid in self._nearby,
                    "side": rec.get("side"), "host": rec.get("host"), "version": p.version if p else None,
                    "screens": p.screens if p else None,
                })
                seen.add(pid)
            for pid, rec in list(self._nearby.items()) + list(self._manual.items()):
                if pid in seen:
                    continue
                seen.add(pid)
                peers.append({"id": pid, "name": rec.get("name") or rec.get("host"), "platform": rec.get("platform"),
                              "paired": False, "connected": False, "online": True, "side": None,
                              "host": rec.get("host"), "port": rec.get("port")})
            pairing = dict(self._pairing) if self._pairing else None
            if pairing:
                pairing.pop("responder", None)
            return {
                "me": {"id": self._store.id, "name": self._store.name, "platform": this_platform(),
                       "version": __version__, "screens": self._screens, "port": self._port,
                       "addresses": _cached_addresses()},
                "mode": self._mode, "active": self._active, "side": self._side, "locked": self._locked,
                "peers": peers, "pairing": pairing,
                "transfers": sorted(self._transfers.values(), key=lambda t: -t["started"])[:20],
                "settings": self._store.settings(), "receive_dir": self._store.receive_dir(self._home_dir),
                "notices": list(self._notices[-10:]), "permissions": self._backend.permissions(),
                "backend": self._backend.name, "capture": self._backend.can_capture,
                "discovery": bool(self._disc and self._disc.available),
                "views": {pid: {k: v[k] for k in ("phase", "error", "w", "h", "seq", "control", "url")}
                          for pid, v in self._views.items()},
                "watchers": [{"id": pid, "name": self._peer_name(pid)} for pid in self._watchers],
                "sound": {"hear": {pid: dict(v) for pid, v in self._hear.items()},
                          "mic": {pid: dict(v) for pid, v in self._mic_out.items()},
                          "listeners": [{"id": pid, "name": self._peer_name(pid)} for pid in self._listeners],
                          "mic_in": [{"id": pid, "name": self._peer_name(pid)} for pid in self._mic_in],
                          "available": bool(self._backend.can_audio)},
                "camera": {"can": bool(self._backend.can_camera), "webcam": bool(getattr(self._backend, "can_vcam", False)),
                           "watchers": [{"id": pid, "name": self._peer_name(pid)} for pid in self._cam_watchers]},
                "extend": {"out": {pid: dict(v) for pid, v in self._extend_out.items()},
                           "in": [dict(v, id=pid, name=self._peer_name(pid)) for pid, v in self._extend_in.items()],
                           "can": bool(getattr(self._backend, "can_vdisplay", False))},
            }

    def rename(self, name):
        self._store.rename(name)
        if self._disc:
            self._disc.rename(self._store.name)
        return True

    def set_setting(self, key, value):
        self._store.set(key, value)
        if key == "screen_share" and not value:
            self.stop_sharing()
        if key == "sound_share" and not value:
            for pid in list(self._listeners):
                self._drop_listener(pid, why="stopped")
        if key == "camera_share" and not value:
            self.stop_camera()
        if key == "mic_accept" and not value:
            for pid in list(self._mic_in):
                self._drop_mic_in(pid, why="stopped")
        self._configure_backend()
        return self._store.settings()

    def set_side(self, pid, side):
        if side not in SIDES and side is not None:
            return False
        with self._lock:
            # One computer per side: move whoever was there off it.
            for other, rec in self._store.pairs().items():
                if other != pid and side and rec.get("side") == side:
                    self._store.update_pair(other, side=None)
            self._store.update_pair(pid, side=side)
            p = self._peers.get(pid)
        if p and p.main:
            p.main.msg({"t": "layout", "side": OPPOSITE.get(side) if side else None})
        self._configure_backend()
        return True

    def forget(self, pid):
        with self._lock:
            p = self._peers.pop(pid, None)
            self._store.forget(pid)
        if p:
            for l in (p.main, p.bulk, p.media):
                if l:
                    try:
                        l.msg({"t": "unpair"})
                    except Exception:
                        pass
                    l.close()
        self._configure_backend()
        return True

    def add_address(self, text):
        """Pair with a computer by its address when it doesn't show up by itself."""
        host, _, port = (text or "").strip().partition(":")
        if not host:
            return None
        rec = {"id": "addr:%s:%s" % (host, port or PORT), "host": host, "port": int(port or PORT), "name": host}
        with self._lock:
            self._manual[rec["id"]] = rec
        return rec["id"]

    # ---- pairing ---------------------------------------------------------------
    def pair(self, ref):
        """Start pairing with a nearby computer; it shows a code to type here."""
        with self._lock:
            if self._pairing and self._pairing.get("phase") in ("connecting", "code", "checking", "showing"):
                return False
            rec = self._nearby.get(ref) or self._manual.get(ref)
            if not rec:
                p = self._store.pair(ref)
                rec = {"host": p.get("host"), "port": p.get("port") or PORT, "name": p.get("name")} if p and p.get("host") else None
            if not rec:
                return False
            self._pairing = {"phase": "connecting", "role": "initiator", "peer": rec.get("name"), "ref": ref}
            self._pair_code_event.clear()
        threading.Thread(target=self._pair_initiator, args=(rec,), daemon=True).start()
        return True

    def pair_code(self, code):
        with self._lock:
            if not self._pairing or self._pairing.get("phase") != "code":
                return False
            self._pairing["code"] = crypto.normalize_code(code)
            self._pairing["phase"] = "checking"
        self._pair_code_event.set()
        return True

    def pair_cancel(self):
        with self._lock:
            self._pairing = None
        self._pair_code_event.set()
        return True

    def _pair_initiator(self, rec):
        sock = None
        try:
            sock = socket.create_connection((rec["host"], int(rec.get("port") or PORT)), timeout=10)
            tune(sock)
            sock.settimeout(PAIR_TIMEOUT + 10)
            write_json(sock, {"t": "hello", "v": 1, "purpose": "pair", "id": self._store.id, "name": self._store.name,
                              "platform": this_platform(), "version": __version__})
            m = read_json(sock)
            if m.get("t") != "pair_b":
                raise PairError(_why(m.get("why")))
            rid, rname, rplat = m["id"], m.get("name") or rec.get("name"), m.get("platform")
            with self._lock:
                if not self._pairing:
                    return
                self._pairing.update(phase="code", peer=rname, platform=rplat)
            if not self._pair_code_event.wait(PAIR_TIMEOUT):
                raise PairError("Pairing timed out. Try again.")
            with self._lock:
                if not self._pairing:
                    write_json(sock, {"t": "pair_cancel"})
                    return
                code = self._pairing.get("code") or ""
            msg_a, confirm_a, key, expect_b = crypto.pair_initiate(code, self._store.id, rid, b64d(m["msg_b"]))
            write_json(sock, {"t": "pair_a", "msg_a": b64e(msg_a), "confirm_a": b64e(confirm_a)})
            r = read_json(sock)
            if r.get("t") != "pair_ok" or b64d(r.get("confirm_b", "")) != expect_b:
                raise PairError("That code didn't match. Check it and try again." if r.get("why") == "wrong_code"
                                else _why(r.get("why")))
            self._store.add_pair(rid, rname, rplat, key)
            self._store.update_pair(rid, host=rec["host"], port=int(rec.get("port") or PORT))
            with self._lock:
                self._pairing = {"phase": "done", "role": "initiator", "peer": rname, "peer_id": rid}
                self._manual.pop(rec.get("id"), None)
            self._notice("Paired with %s" % rname)
            self._ensure_link(rid)
        except (PairError, crypto.CryptoError) as e:
            self._pair_failed(str(e))
        except (OSError, LinkClosed, ValueError, KeyError) as e:
            self._pair_failed("Couldn't reach that computer (%s). Is Kvm open there?" % e)
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    def _pair_failed(self, why):
        with self._lock:
            if self._pairing is not None:
                self._pairing = {"phase": "failed", "error": why, "peer": self._pairing.get("peer")}

    def _pair_responder(self, sock, hello):
        with self._lock:
            if self._pairing and self._pairing.get("phase") in ("showing", "connecting", "code", "checking"):
                write_json(sock, {"t": "pair_err", "why": "busy"})
                return
            code = crypto.new_code()
            iid = hello["id"]
            resp = crypto.PairResponder(code, iid, self._store.id)
            self._pairing = {"phase": "showing", "role": "responder", "code": code, "peer": hello.get("name") or "A computer",
                             "platform": hello.get("platform"), "since": time.time()}
        self._notice("%s wants to pair. Type %s %s there." % (hello.get("name") or "A computer", code[:3], code[3:]))
        try:
            write_json(sock, {"t": "pair_b", "msg_b": b64e(resp.msg_b), "id": self._store.id, "name": self._store.name,
                              "platform": this_platform(), "version": __version__})
            sock.settimeout(PAIR_TIMEOUT + 5)
            m = read_json(sock)
            if m.get("t") != "pair_a":
                raise PairError("The other computer stopped pairing.")
            try:
                key, confirm_b = resp.finish(b64d(m["msg_a"]), b64d(m["confirm_a"]))
            except crypto.CryptoError:
                write_json(sock, {"t": "pair_err", "why": "wrong_code"})
                raise PairError("The code typed on %s didn't match." % (hello.get("name") or "the other computer"))
            write_json(sock, {"t": "pair_ok", "confirm_b": b64e(confirm_b)})
            self._store.add_pair(iid, hello.get("name") or "Computer", hello.get("platform"), key)
            try:
                self._store.update_pair(iid, host=sock.getpeername()[0])
            except OSError:
                pass
            with self._lock:
                self._pairing = {"phase": "done", "role": "responder", "peer": hello.get("name"), "peer_id": iid}
            self._notice("Paired with %s" % (hello.get("name") or "a computer"))
        except (PairError, OSError, LinkClosed, ValueError, KeyError) as e:
            self._pair_failed(str(e) if isinstance(e, PairError) else "Pairing stopped: %s" % e)

    # ---- the other computer ------------------------------------------------------
    def action(self, pid, what):
        """Ring, lock or sleep a paired computer."""
        if what not in ("ring", "lock", "sleep"):
            return False
        p = self._peers.get(pid)
        if not (p and p.main):
            return False
        return p.main.msg({"t": "action", "a": what})

    def go_home(self):
        """Bring the pointer back to this computer (same as the return hotkey)."""
        with self._lock:
            if self._mode == "driving":
                self._leave_driving(recall=True)
                return True
            if self._mode == "driven":
                p = self._peers.get(self._active)
                if p and p.main:
                    p.main.msg({"t": "release"})
                self._backend.handle({"c": "release"})
                self._set_mode("home")
                return True
        return False

    def set_locked(self, on):
        self._on_backend({"t": "lock", "on": bool(on)}, forced=True)
        return self._locked

    # ---- files -------------------------------------------------------------------
    def send_files(self, pid, paths):
        p = self._peers.get(pid)
        if not (p and p.main and not p.main.closed):
            return None
        items = []
        for path in paths or []:
            path = os.path.abspath(path)
            if os.path.isdir(path):
                base = os.path.dirname(path.rstrip("\\/"))
                for root, dirs, files in os.walk(path):
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    for f in files:
                        if f.startswith(".") and f in (".DS_Store",):
                            continue
                        full = os.path.join(root, f)
                        try:
                            items.append({"path": full, "rel": os.path.relpath(full, base).replace("\\", "/"),
                                          "size": os.path.getsize(full)})
                        except OSError:
                            pass
            elif os.path.isfile(path):
                items.append({"path": path, "rel": os.path.basename(path), "size": os.path.getsize(path)})
        if not items:
            return None
        tid = crypto.random_id(6)
        total = sum(i["size"] for i in items)
        names = sorted({i["rel"].split("/")[0] for i in items})
        t = {"id": tid, "dir": "out", "peer": pid, "peer_name": self._peer_name(pid), "count": len(items),
             "total": total, "done": 0, "phase": "sending", "started": time.time(), "error": None,
             "label": names[0] if len(names) == 1 else "%d items" % len(names)}
        with self._lock:
            self._transfers[tid] = t
        threading.Thread(target=self._send_files, args=(p, tid, items), daemon=True).start()
        return tid

    def cancel_transfer(self, tid):
        with self._lock:
            t = self._transfers.get(tid)
            if not t:
                return False
            if t["phase"] in ("sending", "receiving"):
                t["phase"] = "cancelled"
                p = self._peers.get(t["peer"])
                link = p and (p.bulk or p.main)
                if link:
                    link.msg({"t": "files_cancel", "tid": tid})
            return True

    def clear_transfers(self):
        with self._lock:
            for tid in [k for k, t in self._transfers.items() if t["phase"] not in ("sending", "receiving")]:
                self._transfers.pop(tid, None)
        return True

    def _send_files(self, p, tid, items):
        t = self._transfers[tid]
        link = p.bulk if (p.bulk and not p.bulk.closed) else p.main
        try:
            link.msg({"t": "files", "tid": tid, "from": self._store.name, "label": t["label"],
                      "items": [{"i": n, "rel": it["rel"], "size": it["size"]} for n, it in enumerate(items)]})
            for n, it in enumerate(items):
                h = hashlib.sha256()
                with open(it["path"], "rb") as f:
                    while True:
                        if t["phase"] == "cancelled" or link.closed:
                            raise _Stop()
                        chunk = f.read(PIECE)
                        if not chunk:
                            break
                        h.update(chunk)
                        if not link.blob({"t": "piece", "tid": tid, "i": n}, chunk):
                            raise _Stop()
                        t["done"] += len(chunk)
                link.msg({"t": "file_done", "tid": tid, "i": n, "sha": h.hexdigest()})
            link.msg({"t": "files_done", "tid": tid})
            t["phase"] = "sent"
        except _Stop:
            if t["phase"] != "cancelled":
                t.update(phase="failed", error="The connection dropped.")
        except OSError as e:
            t.update(phase="failed", error=str(e))
            link.msg({"t": "files_cancel", "tid": tid})

    def _on_files(self, pid, m):
        if not self._store.get("files"):
            p = self._peers.get(pid)
            if p and p.main:
                p.main.msg({"t": "files_refused", "tid": m.get("tid")})
            return
        tid = m["tid"]
        dest = self._store.receive_dir(self._home_dir)
        top = sorted({it["rel"].split("/")[0] for it in m["items"]})
        taken = {}
        for name in top:
            taken[name] = _unique(dest, name)
        state = {"dest": dest, "items": {}, "top": taken}
        for it in m["items"]:
            parts = [x for x in it["rel"].split("/") if x not in ("", ".", "..")]
            if not parts:
                continue
            parts[0] = taken.get(it["rel"].split("/")[0], parts[0])
            final = os.path.join(dest, *parts)
            state["items"][it["i"]] = {"final": final, "part": final + ".kvmpart", "size": it["size"], "h": hashlib.sha256(),
                                       "f": None, "got": 0}
        t = {"id": tid, "dir": "in", "peer": pid, "peer_name": self._peer_name(pid), "count": len(m["items"]),
             "total": sum(it["size"] for it in m["items"]), "done": 0, "phase": "receiving", "started": time.time(),
             "error": None, "label": m.get("label") or "files", "dest": dest,
             "open": os.path.join(dest, taken[top[0]]) if len(top) == 1 else dest}
        with self._lock:
            self._incoming[tid] = state
            self._transfers[tid] = t

    def _on_piece(self, m):
        st = self._incoming.get(m.get("tid"))
        t = self._transfers.get(m.get("tid"))
        if not st or not t or t["phase"] != "receiving":
            return
        it = st["items"].get(m.get("i"))
        if not it:
            return
        data = m["_data"]
        if it["got"] + len(data) > it["size"]:
            self._recv_fail(m["tid"], "A file came in bigger than offered.")
            return
        try:
            if it["f"] is None:
                os.makedirs(os.path.dirname(it["part"]), exist_ok=True)
                it["f"] = open(it["part"], "wb")
            it["f"].write(data)
        except OSError as e:
            self._recv_fail(m["tid"], "Couldn't save: %s" % e)
            return
        it["h"].update(data)
        it["got"] += len(data)
        t["done"] += len(data)

    def _on_file_done(self, m):
        st = self._incoming.get(m.get("tid"))
        if not st:
            return
        it = st["items"].get(m.get("i"))
        if not it:
            return
        try:
            if it["f"] is None:  # an empty file
                os.makedirs(os.path.dirname(it["part"]), exist_ok=True)
                open(it["part"], "wb").close()
            else:
                it["f"].close()
            if it["h"].hexdigest() != m.get("sha") or it["got"] != it["size"]:
                os.remove(it["part"])
                self._recv_fail(m["tid"], "A file didn't arrive intact.")
                return
            os.replace(it["part"], _unique_path(it["final"]))
        except OSError as e:
            self._recv_fail(m["tid"], "Couldn't save: %s" % e)

    def _on_files_done(self, m):
        t = self._transfers.get(m.get("tid"))
        self._incoming.pop(m.get("tid"), None)
        if t and t["phase"] == "receiving":
            t["phase"] = "received"
            self._notice("%s sent %s" % (t["peer_name"], t["label"]))
            self._backend.handle({"c": "action", "a": "notify", "title": "Kvm",
                                  "text": "%s sent %s" % (t["peer_name"], t["label"])})

    def _recv_fail(self, tid, why, phase="failed"):
        st = self._incoming.pop(tid, None)
        t = self._transfers.get(tid)
        if t and t["phase"] == "receiving":
            t.update(phase=phase, error=why)
        if st:
            for it in st["items"].values():
                try:
                    if it["f"]:
                        it["f"].close()
                    if os.path.exists(it["part"]):
                        os.remove(it["part"])
                except OSError:
                    pass
        if t:
            p = self._peers.get(t["peer"])
            if p and p.main and phase == "failed":
                p.main.msg({"t": "files_cancel", "tid": tid})


    # ==== the other computer's screen ===============================================
    # The watcher asks ("view"); the computer being watched has its backend take pictures of
    # its screen and sends each one over the "media" link. Only the newest picture is ever
    # queued, so a slow network shows fewer frames, never old ones. Input from the viewer
    # window arrives as "vin" and is put on the screen like any other.
    def view_start(self, pid, fps=12, maxw=1600, quality=65, region=None):
        """Start watching a paired computer's screen. Returns the local address of its picture stream."""
        with self._lock:
            p = self._peers.get(pid)
            if not (p and p.main and not p.main.closed):
                raise RuntimeError("%s isn't connected." % self._peer_name(pid))
            if not self._view_server:
                from .viewserver import ViewServer
                self._view_server = ViewServer(self).start()
            v = self._views.get(pid)
            if not v:
                v = self._views[pid] = {"phase": "asking", "error": None, "w": 0, "h": 0, "seq": 0, "control": False,
                                        "jpeg": None, "cond": threading.Condition(), "since": time.time()}
            v["url"] = self._view_server.url(pid)
            v["req"] = {"t": "view", "on": True, "fps": fps, "maxw": maxw, "q": quality}
            if region:
                v["req"]["region"] = region
        p.main.msg(v["req"])
        return v["url"]

    def view_stop(self, pid):
        with self._lock:
            v = self._views.pop(pid, None)
            p = self._peers.get(pid)
        if v:
            with v["cond"]:
                v["phase"] = "stopped"
                v["cond"].notify_all()
        if p and p.main and not p.main.closed:
            p.main.msg({"t": "view", "on": False})
        return True

    def stop_sharing(self):
        """Stop everyone watching this screen (they can ask again)."""
        for pid in list(self._watchers):
            self._drop_watcher(pid)
            p = self._peers.get(pid)
            if p and p.main and not p.main.closed:
                p.main.msg({"t": "view_refused", "why": "stopped"})
        return True

    def view_input(self, pid, ev):
        """Mouse and keys from the viewer window: {"k": "abs", x, y} (fractions of the picture),
        {"k": "button", b, d}, {"k": "wheel", dx, dy}, {"k": "key", code|hid, d}."""
        v = self._views.get(pid)
        p = self._peers.get(pid)
        if not (v and v.get("control") and p and p.main and not p.main.closed):
            return False
        k = ev.get("k")
        if k == "key":
            hid = ev.get("hid") or keys.DOM_CODES.get(ev.get("code") or "")
            if not hid:
                return False
            ev = {"k": "key", "hid": self._translate(int(hid), pid), "d": bool(ev.get("d"))}
        p.main.msg(dict(ev, t="vin"))
        return True

    def view_frame(self, pid, after=0, timeout=10.0):
        """The newest picture (jpeg bytes, seq) once one newer than `after` exists (the view server)."""
        v = self._views.get(pid)
        if not v:
            return None, -1
        with v["cond"]:
            if v["seq"] <= after and v["phase"] != "stopped":
                v["cond"].wait(timeout)
            if v["phase"] == "stopped":
                return None, -1
            return v["jpeg"], v["seq"]

    def _on_view_msg(self, pid, link, m):
        t = m.get("t")
        if t == "view":
            if not m.get("on"):
                self._drop_watcher(pid)
                return
            if not self._store.get("screen_share") or not self._backend.can_capture:
                link.msg({"t": "view_refused", "why": "off" if self._backend.can_capture else "unsupported"})
                return
            with self._lock:
                w = self._watchers.get(pid)
                if not w:
                    w = self._watchers[pid] = {"latest": None, "event": threading.Event(), "on": True}
                    threading.Thread(target=self._watcher_sender, args=(pid, w), name="kvm-view-send", daemon=True).start()
                    self._notice("%s is looking at this screen." % self._peer_name(pid))
                w["req"] = {"fps": m.get("fps") or 12, "maxw": m.get("maxw") or 1600, "q": m.get("q") or 65,
                            "region": m.get("region")}
            link.msg({"t": "view_ok", "control": bool(self._store.get("screen_control") and self._backend.can_inject)})
            self._retune_capture()
            if not self._media_ok(pid) and link.dialer == self._store.id:  # whoever dialled main dials media
                threading.Thread(target=self._dial, args=(pid, "media"), daemon=True).start()
            return
        if t == "vin":
            if pid not in self._watchers or not self._store.get("screen_control"):
                return
            k = m.get("k")
            if k == "abs":
                req = self._watchers[pid].get("req") or {}
                rect = self._vrect if req.get("region") == "extend" else None
                self._backend.handle({"c": "abs", "x": float(m.get("x", 0)), "y": float(m.get("y", 0)), "rect": rect})
            elif k == "button":
                self._backend.handle({"c": "button", "b": int(m.get("b", 1)), "d": bool(m.get("d"))})
            elif k == "wheel":
                self._backend.handle({"c": "wheel", "dx": float(m.get("dx", 0)), "dy": float(m.get("dy", 0))})
            elif k == "key":
                self._backend.handle({"c": "key", "k": int(m.get("hid", 0)), "d": bool(m.get("d"))})
            elif k == "release":
                self._backend.handle({"c": "release"})
            return
        v = self._views.get(pid)
        if not v:
            return
        if t == "view_ok":
            v.update(phase="live", control=bool(m.get("control")), error=None)
            if not self._media_ok(pid) and link.dialer == self._store.id:
                threading.Thread(target=self._dial, args=(pid, "media"), daemon=True).start()
        elif t == "view_refused":
            v.update(phase="refused", error={"off": "%s doesn't share its screen. Turn it on in Kvm settings there."
                                             % self._peer_name(pid),
                                             "stopped": "%s stopped sharing its screen." % self._peer_name(pid)}.get(m.get("why"),
                                             "%s can't share its screen yet." % self._peer_name(pid)))
        elif t == "frame" and "_data" in m:
            with v["cond"]:
                v.update(jpeg=m["_data"], w=m.get("w", 0), h=m.get("h", 0), seq=v["seq"] + 1, phase="live")
                v["cond"].notify_all()

    def _media_ok(self, pid):
        p = self._peers.get(pid)
        return bool(p and p.media and not p.media.closed)

    def _retune_capture(self):
        with self._lock:
            reqs = [w["req"] for w in self._watchers.values() if w.get("req")]
        if not reqs:
            self._backend.handle({"c": "capture", "on": False})
            return
        # While extending, the extra display is what's sent (to everyone watching).
        rect = self._vrect if any(r.get("region") == "extend" for r in reqs) else None
        self._backend.handle({"c": "capture", "on": True, "fps": max(r["fps"] for r in reqs),
                              "maxw": max(r["maxw"] for r in reqs), "q": max(r["q"] for r in reqs), "rect": rect})

    def _drop_watcher(self, pid):
        with self._lock:
            w = self._watchers.pop(pid, None)
        if w:
            w["on"] = False
            w["event"].set()
            self._backend.handle({"c": "release"})  # nothing stays pressed from the viewer
            self._retune_capture()

    def _on_local_frame(self, ev):
        with self._lock:
            watchers = list(self._watchers.values())
        if not watchers:
            return
        frame = ({"t": "frame", "w": ev.get("w"), "h": ev.get("h"), "cursor": ev.get("cursor")}, b64d(ev["jpeg"]))
        for w in watchers:
            w["latest"] = frame
            w["event"].set()

    def _watcher_sender(self, pid, w):
        while w["on"]:
            w["event"].wait(5)
            w["event"].clear()
            frame, w["latest"] = w["latest"], None
            if not (frame and w["on"]):
                continue
            p = self._peers.get(pid)
            link = None
            if p:
                for l in (p.media, p.bulk, p.main):
                    if l and not l.closed:
                        link = l
                        break
            if link:
                link.blob(frame[0], frame[1])

    # ==== the other computer's camera ===============================================
    # We ask ("cam"); it turns its camera on and sends each picture ("camframe", a JPEG) over
    # the media link. Here it shows in a Kvm window (the view server, under "cam-<pid>"), and on
    # a computer with a virtual camera, apps can use it as a webcam.
    def camera_start(self, pid):
        """Use a paired computer's camera here. Returns the local address of its picture stream."""
        p = self._connected(pid)
        key = "cam-" + pid
        with self._lock:
            if not self._view_server:
                from .viewserver import ViewServer
                self._view_server = ViewServer(self).start()
            v = self._views.get(key)
            if not v:
                v = self._views[key] = {"phase": "asking", "error": None, "w": 0, "h": 0, "seq": 0, "control": False,
                                        "jpeg": None, "cond": threading.Condition(), "since": time.time(), "camera": True}
            v["url"] = self._view_server.url(key)
            v["req"] = {"t": "cam", "on": True}
        p.main.msg(v["req"])
        return v["url"]

    def camera_stop(self, pid):
        self.view_stop("cam-" + pid)
        if getattr(self._backend, "can_vcam", False):
            self._backend.handle({"c": "vcam_stop"})
        p = self._peers.get(pid)
        if p and p.main and not p.main.closed:
            p.main.msg({"t": "cam", "on": False})
        return True

    def _on_cam_msg(self, pid, link, m):
        t = m.get("t")
        if t == "cam":
            if not m.get("on"):
                self._drop_cam_watcher(pid)
                return
            if not self._store.get("camera_share") or not self._backend.can_camera:
                link.msg({"t": "cam_refused", "why": "off" if self._backend.can_camera else "unsupported"})
                return
            with self._lock:
                new = pid not in self._cam_watchers
                self._cam_watchers.add(pid)
            if new:
                self._notice("%s is using this computer's camera." % self._peer_name(pid))
                self._backend.handle({"c": "camera", "on": True, "w": 1280, "h": 720, "fps": 30})
            link.msg({"t": "cam_ok"})
            self._ensure_media(pid, link)
            return
        v = self._views.get("cam-" + pid)
        if not v:
            return
        name = self._peer_name(pid)
        if t == "cam_ok":
            v.update(phase="live", error=None)
            self._ensure_media(pid, link)
        elif t == "cam_refused":
            v.update(phase="refused", error=m.get("error") or {
                "off": "%s doesn't share its camera. Turn it on in Kvm settings there." % name,
                "stopped": "%s stopped sharing its camera." % name}.get(
                m.get("why"), "%s can't share its camera yet." % name))
            with v["cond"]:
                v["cond"].notify_all()
        elif t == "camframe" and "_data" in m:
            with v["cond"]:
                v.update(jpeg=m["_data"], w=m.get("w", 0), h=m.get("h", 0), seq=v["seq"] + 1, phase="live")
                v["cond"].notify_all()
            if getattr(self._backend, "can_vcam", False):
                self._backend.handle({"c": "vcam_frame", "jpeg": b64e(m["_data"]), "w": m.get("w"), "h": m.get("h")})

    def _drop_cam_watcher(self, pid, why=None, error=None):
        with self._lock:
            if pid not in self._cam_watchers:
                return
            self._cam_watchers.discard(pid)
            left = bool(self._cam_watchers)
        if not left:
            self._backend.handle({"c": "camera", "on": False})
        if why:
            p = self._peers.get(pid)
            if p and p.main and not p.main.closed:
                p.main.msg({"t": "cam_refused", "why": why, "error": error})

    def stop_camera(self):
        """Stop everyone using this computer's camera."""
        for pid in list(self._cam_watchers):
            self._drop_cam_watcher(pid, why="stopped")
        return True

    def _on_local_camframe(self, ev):
        with self._lock:
            pids = list(self._cam_watchers)
        if not pids:
            return
        data = b64d(ev["jpeg"])
        for pid in pids:
            link = self._sound_link(pid)  # media if it's up, else main
            if link:
                link.blob({"t": "camframe", "w": ev.get("w"), "h": ev.get("h")}, data)

    # ==== extending this computer onto another ======================================
    # This computer adds an extra display (a virtual one, on a Mac) and the other computer shows
    # it full screen, like a monitor plugged in over the network. It's a screen view of just that
    # display ("region": "extend"), so the picture, the pointer and clicks from there all work the
    # same way. Our keyboard and mouse simply move onto the extra display like any other.
    def extend_start(self, pid, w=None, h=None):
        """Use that computer's screen as an extra display for this one."""
        p = self._connected(pid)
        if not getattr(self._backend, "can_vdisplay", False):
            raise RuntimeError("Only a Mac can extend onto another computer for now.")
        if not (w and h):
            rects = sorted(p.screens or [], key=lambda r: -r[2] * r[3])
            w, h = (int(rects[0][2]), int(rects[0][3])) if rects else (1920, 1080)
        with self._lock:
            for other in list(self._extend_out):
                if other != pid:
                    self.extend_stop(other)
            self._extend_out[pid] = {"phase": "starting", "error": None, "w": int(w), "h": int(h)}
        self._backend.handle({"c": "vdisplay", "on": True, "w": int(w), "h": int(h)})
        return True

    def extend_stop(self, pid):
        with self._lock:
            had = self._extend_out.pop(pid, None)
            left = bool(self._extend_out)
        if had:
            p = self._peers.get(pid)
            if p and p.main and not p.main.closed:
                p.main.msg({"t": "extend", "on": False})
            if not left:
                self._backend.handle({"c": "vdisplay", "on": False})
        return True

    def extend_end(self, pid):
        """(Showing another computer's display) close it: that computer removes its extra display."""
        with self._lock:
            self._extend_in.pop(pid, None)
        self.view_stop(pid)
        p = self._peers.get(pid)
        if p and p.main and not p.main.closed:  # even if a reconnect forgot it here: that computer still has it
            p.main.msg({"t": "extend_refused", "why": "closed"})
        return True

    def _on_vdisplay(self, ev):
        with self._lock:
            self._vrect = ev.get("rect") if ev.get("on") else None
            out = list(self._extend_out.items())
        for pid, v in out:
            p = self._peers.get(pid)
            if ev.get("on") and self._vrect:
                if v.get("phase") == "reconnecting" and not (p and p.main and not p.main.closed):
                    continue
                v.update(phase="live", error=None)
                if p and p.main and not p.main.closed:
                    p.main.msg({"t": "extend", "on": True, "w": v["w"], "h": v["h"]})
            elif ev.get("error"):
                v.update(phase="failed", error=ev["error"])
                if p and p.main and not p.main.closed:
                    p.main.msg({"t": "extend", "on": False})
        self._retune_capture()

    def _on_extend_msg(self, pid, link, m):
        t = m.get("t")
        if t == "extend_refused":
            v = self._extend_out.get(pid)
            if m.get("why") == "closed":
                self.extend_stop(pid)
            elif v:
                v.update(phase="refused", error="%s doesn't take an extra display. Turn it on in Kvm settings there."
                         % self._peer_name(pid))
                self._backend.handle({"c": "vdisplay", "on": False})
            return
        if not m.get("on"):
            with self._lock:
                had = self._extend_in.pop(pid, None)
            if had:
                self.view_stop(pid)
            return
        if not self._store.get("display_accept"):
            link.msg({"t": "extend_refused", "why": "off"})
            return
        w, h = int(m.get("w") or 1920), int(m.get("h") or 1080)
        with self._lock:
            new = pid not in self._extend_in
            self._extend_in[pid] = {"w": w, "h": h}
        if new:
            self._notice("%s is using this screen as a display." % self._peer_name(pid))
        self.view_start(pid, fps=30, maxw=w, quality=75, region="extend")

    # ==== sound ====================================================================
    # Hearing a computer: we ask ("listen"); it records what it plays and sends 20 ms blocks of
    # PCM ("pcm", src "output") over the media link; we play them out of our speakers.
    # Our mic on a computer: we ask ("mic"); once it says yes we record our microphone and send
    # it ("pcm", src "mic"); it plays them into its virtual microphone (VB-CABLE / BlackHole).
    def listen_start(self, pid):
        """Hear what a paired computer is playing, on this computer's speakers."""
        p = self._connected(pid)
        with self._lock:
            self._hear[pid] = {"phase": "asking", "error": None}
        p.main.msg({"t": "listen", "on": True})
        return True

    def listen_stop(self, pid):
        with self._lock:
            had = self._hear.pop(pid, None)
        p = self._peers.get(pid)
        if had and p and p.main and not p.main.closed:
            p.main.msg({"t": "listen", "on": False})
        return True

    def mic_start(self, pid):
        """Send this computer's microphone to a paired computer's virtual microphone."""
        p = self._connected(pid)
        with self._lock:
            self._mic_out[pid] = {"phase": "asking", "error": None}
        p.main.msg({"t": "mic", "on": True})
        return True

    def mic_stop(self, pid):
        with self._lock:
            had = self._mic_out.pop(pid, None)
        p = self._peers.get(pid)
        if had and p and p.main and not p.main.closed:
            p.main.msg({"t": "mic", "on": False})
        self._retune_mic()
        return True

    def stop_sound(self):
        """Stop everyone hearing this computer (they can ask again)."""
        for pid in list(self._listeners):
            self._drop_listener(pid, why="stopped")
        return True

    def _connected(self, pid):
        p = self._peers.get(pid)
        if not (p and p.main and not p.main.closed):
            raise RuntimeError("%s isn't connected." % self._peer_name(pid))
        return p

    def _on_sound_msg(self, pid, link, m):
        t = m.get("t")
        name = self._peer_name(pid)
        if t == "listen":
            if not m.get("on"):
                self._drop_listener(pid)
                return
            if not self._store.get("sound_share") or not self._backend.can_audio:
                link.msg({"t": "listen_refused", "why": "off" if self._backend.can_audio else "unsupported"})
                return
            with self._lock:
                new = pid not in self._listeners
                self._listeners.add(pid)
            if new:
                self._notice("%s is listening to this computer." % name)
            link.msg({"t": "listen_ok"})
            self._backend.handle({"c": "audio_capture", "src": "output", "on": True})
            self._ensure_media(pid, link)
        elif t == "mic":
            if not m.get("on"):
                self._drop_mic_in(pid)
                return
            if not self._store.get("mic_accept") or not self._backend.can_audio:
                link.msg({"t": "mic_refused", "why": "off" if self._backend.can_audio else "unsupported"})
                return
            with self._lock:
                self._mic_in.add(pid)
            link.msg({"t": "mic_ok"})
            self._ensure_media(pid, link)
        elif t == "pcm":
            data = m.get("_data")
            if not data:
                return
            if m.get("src") == "output" and pid in self._hear:
                self._hear[pid].update(phase="live", error=None)
                self._backend.handle({"c": "audio_play", "sink": "speaker", "pcm": b64e(data)})
            elif m.get("src") == "mic" and pid in self._mic_in:
                self._backend.handle({"c": "audio_play", "sink": "mic", "pcm": b64e(data)})
        elif t in ("listen_ok", "listen_refused"):
            v = self._hear.get(pid)
            if not v:
                return
            if t == "listen_ok":
                v.update(phase="live", error=None)
                self._ensure_media(pid, link)
            else:
                v.update(phase="refused", error=_sound_why(m, name, "hear"))
        elif t in ("mic_ok", "mic_refused"):
            v = self._mic_out.get(pid)
            if not v:
                return
            if t == "mic_ok":
                v.update(phase="live", error=None)
                self._ensure_media(pid, link)
            else:
                v.update(phase="refused", error=_sound_why(m, name, "mic"))
            self._retune_mic()

    def _ensure_media(self, pid, link):
        if not self._media_ok(pid) and link.dialer == self._store.id:  # whoever dialled main dials media
            threading.Thread(target=self._dial, args=(pid, "media"), daemon=True).start()

    def _drop_listener(self, pid, why=None):
        with self._lock:
            if pid not in self._listeners:
                return
            self._listeners.discard(pid)
            left = bool(self._listeners)
        if not left:
            self._backend.handle({"c": "audio_capture", "src": "output", "on": False})
        if why:
            p = self._peers.get(pid)
            if p and p.main and not p.main.closed:
                p.main.msg({"t": "listen_refused", "why": why})

    def _drop_mic_in(self, pid, why=None, error=None):
        with self._lock:
            if pid not in self._mic_in:
                return
            self._mic_in.discard(pid)
        if why:
            p = self._peers.get(pid)
            if p and p.main and not p.main.closed:
                p.main.msg({"t": "mic_refused", "why": why, "error": error})

    def _retune_mic(self):
        with self._lock:
            on = any(v.get("phase") == "live" for v in self._mic_out.values())
        self._backend.handle({"c": "audio_capture", "src": "mic", "on": on})

    def _sound_link(self, pid):
        p = self._peers.get(pid)
        if p:
            for l in (p.media, p.main):
                if l and not l.closed:
                    return l
        return None

    def _on_local_audio(self, ev):
        src = ev.get("src")
        with self._lock:
            if src == "output":
                pids = list(self._listeners)
            else:
                pids = [pid for pid, v in self._mic_out.items() if v.get("phase") == "live"]
        if not pids:
            return
        pcm = b64d(ev["pcm"])
        for pid in pids:
            link = self._sound_link(pid)
            if link:
                link.blob({"t": "pcm", "src": src}, pcm)

    def _on_audio_err(self, ev):
        why, err = ev.get("why") or "failed", ev.get("error")
        if ev.get("src") == "output":
            for pid in list(self._listeners):
                self._drop_listener(pid)
                p = self._peers.get(pid)
                if p and p.main and not p.main.closed:
                    p.main.msg({"t": "listen_refused", "why": why, "error": err})
        elif ev.get("src") == "mic":
            with self._lock:
                for v in self._mic_out.values():
                    v.update(phase="failed", error=err)
            self._notice(err or "Couldn't use the microphone.")
        elif ev.get("sink") == "mic":
            for pid in list(self._mic_in):
                self._drop_mic_in(pid, why=why, error=err)
        elif ev.get("sink") == "speaker":
            with self._lock:
                for v in self._hear.values():
                    v.update(error=err)


    # ==== networking ===============================================================
    def _listen(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name != "nt":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", self._port))
        except OSError:
            if os.environ.get("KVM_PORT") is None and self._port == PORT:
                s.bind(("0.0.0.0", 0))  # another copy has the port; still usable by address
            else:
                raise
        self._port = s.getsockname()[1]
        s.listen(16)
        self._server = s
        threading.Thread(target=self._accept_loop, name="kvm-accept", daemon=True).start()

    def _accept_loop(self):
        while not self._stopped:
            try:
                sock, _ = self._server.accept()
            except OSError:
                if self._stopped:
                    return
                time.sleep(0.2)
                continue
            threading.Thread(target=self._handshake_in, args=(sock,), daemon=True).start()

    def _handshake_in(self, sock):
        try:
            tune(sock)
            sock.settimeout(15)
            hello = read_json(sock)
            if hello.get("t") != "hello" or not hello.get("id"):
                sock.close()
                return
            if hello.get("purpose") == "pair":
                self._pair_responder(sock, hello)
                sock.close()
                return
            pid = hello["id"]
            key = self._store.pair_key(pid)
            if not key:
                write_json(sock, {"t": "err", "why": "unpaired"})
                sock.close()
                return
            nonce = os.urandom(16)
            write_json(sock, {"t": "hello", "id": self._store.id, "name": self._store.name, "platform": this_platform(),
                              "version": __version__, "nonce": b64e(nonce)})
            d2l, l2d = crypto.session_keys(key, b64d(hello["nonce"]), nonce)
            sock.settimeout(None)
            link = Link(sock, l2d, d2l, pid, hello.get("purpose") or "main", pid, self._on_frame, self._on_link_closed)
            self._adopt(link, hello)
        except (OSError, LinkClosed, ValueError, KeyError):
            try:
                sock.close()
            except OSError:
                pass

    def _dial(self, pid, purpose):
        rec = self._store.pair(pid)
        if not rec:
            return None
        hosts = []
        near = self._nearby.get(pid)
        if near:
            hosts.append((near["host"], near["port"]))
        if rec.get("host"):
            hosts.append((rec["host"], rec.get("port") or PORT))
        key = bytes.fromhex(rec["key"])
        for host, port in hosts:
            sock = None
            try:
                sock = socket.create_connection((host, int(port)), timeout=4)
                tune(sock)
                sock.settimeout(10)
                nonce = os.urandom(16)
                write_json(sock, {"t": "hello", "v": 1, "purpose": purpose, "id": self._store.id, "name": self._store.name,
                                  "platform": this_platform(), "version": __version__, "nonce": b64e(nonce)})
                m = read_json(sock)
                if m.get("t") == "err" and m.get("why") == "unpaired":
                    self._notice("%s no longer knows this computer. Pair again." % rec.get("name"))
                    self._store.update_pair(pid, stale=True)
                    sock.close()
                    return None
                if m.get("t") != "hello" or m.get("id") != pid:
                    sock.close()
                    continue
                d2l, l2d = crypto.session_keys(key, nonce, b64d(m["nonce"]))
                sock.settimeout(None)
                link = Link(sock, d2l, l2d, pid, purpose, self._store.id, self._on_frame, self._on_link_closed)
                self._store.update_pair(pid, host=host, port=int(port), stale=False)
                self._adopt(link, m)
                return link
            except (OSError, LinkClosed, ValueError, KeyError):
                if sock:
                    try:
                        sock.close()
                    except OSError:
                        pass
        return None

    def _adopt(self, link, hello):
        pid = link.peer_id
        with self._lock:
            p = self._peers.setdefault(pid, Peer(pid))
            slot = link.purpose if link.purpose in ("main", "bulk", "media") else "bulk"
            old = getattr(p, slot)
            if old and not old.closed:
                # Both computers dialled at once: keep the link the lower id dialled.
                keep_new = link.dialer == min(self._store.id, pid)
                if not keep_new and old.dialer == min(self._store.id, pid):
                    link.on_close = None
                    link.close()
                    return
                old.on_close = None
                old.close()
            setattr(p, slot, link)
            p.last_seen = time.time()
            if hello.get("name"):
                self._store.update_pair(pid, name=hello["name"], platform=hello.get("platform"))
        link.start()
        if link.purpose == "main":
            link.msg({"t": "ready", "version": __version__, "screens": self._screens,
                      "side": OPPOSITE.get((self._store.pair(pid) or {}).get("side"))})
            self._configure_backend()
            if link.dialer == self._store.id:
                threading.Thread(target=self._dial, args=(pid, "bulk"), daemon=True).start()
            self._resume_asks(pid, link)

    def _resume_asks(self, pid, link):
        with self._lock:
            v = self._views.get(pid)
            asks = [v["req"]] if v and v.get("req") and v.get("phase") != "refused" else []
            if self._hear.get(pid, {}).get("phase") in ("asking", "live", "reconnecting"):
                asks.append({"t": "listen", "on": True})
            if self._mic_out.get(pid, {}).get("phase") in ("asking", "live", "reconnecting"):
                asks.append({"t": "mic", "on": True})
            c = self._views.get("cam-" + pid)
            if c and c.get("phase") != "refused":
                asks.append({"t": "cam", "on": True})
            e = self._extend_out.get(pid)
            if e and e.get("phase") in ("live", "reconnecting") and self._vrect:
                e.update(phase="live")
                asks.append({"t": "extend", "on": True, "w": e["w"], "h": e["h"]})
        for m in asks:
            link.msg(m)

    def _ensure_link(self, pid):
        with self._lock:
            p = self._peers.setdefault(pid, Peer(pid))
            if (p.main and not p.main.closed) or p.connecting:
                return
            p.connecting = True

        def go():
            try:
                self._dial(pid, "main")
            finally:
                p.connecting = False
        threading.Thread(target=go, daemon=True).start()

    def _maintain(self):
        n = 0
        while not self._stopped:
            time.sleep(PING_EVERY)
            n += 1
            now = time.time()
            for pid in list(self._store.pairs().keys()):
                p = self._peers.get(pid)
                if p and p.main and not p.main.closed:
                    p.main.msg({"t": "ping"})
                    if now - p.last_seen > DEAD_AFTER:
                        self._log("link to %s went quiet" % pid)
                        p.main.close()
                elif n % 3 == 0 and not (self._store.pair(pid) or {}).get("stale"):
                    self._ensure_link(pid)
            with self._lock:
                if self._pairing and self._pairing.get("phase") in ("done", "failed") and \
                        now - self._pairing.get("since", now) > 30:
                    self._pairing = None
                if self._pairing and "since" not in self._pairing:
                    self._pairing["since"] = now

    def _on_link_closed(self, link):
        with self._lock:
            p = self._peers.get(link.peer_id)
            if not p:
                return
            if link.purpose == "main" and p.main is link:
                p.main = None
                for other in (p.bulk, p.media):
                    if other:
                        other.close()
                # What we asked of that computer (its screen, its sound, our mic there) is asked
                # again when it reconnects; what it asked of us, it asks again itself.
                for d, key in ((self._views, link.peer_id), (self._views, "cam-" + link.peer_id),
                               (self._hear, link.peer_id), (self._mic_out, link.peer_id),
                               (self._extend_out, link.peer_id)):
                    v = d.get(key)
                    if v and v.get("phase") != "refused":
                        v.update(phase="reconnecting")
                self._drop_watcher(link.peer_id)
                self._drop_listener(link.peer_id)
                self._drop_cam_watcher(link.peer_id)
                # _extend_in stays: the display window waits through a reconnect, and the other
                # computer asks again (or says it stopped).
                self._drop_mic_in(link.peer_id)
                self._retune_mic()
                if self._active == link.peer_id:
                    if self._mode == "driving":
                        self._backend.handle({"c": "grab", "on": False})
                    elif self._mode == "driven":
                        self._backend.handle({"c": "release"})
                        self._backend.handle({"c": "driven", "exits": []})
                    self._set_mode("home")
            elif p.bulk is link:
                p.bulk = None
            elif p.media is link:
                p.media = None
            for tid, t in list(self._transfers.items()):
                if t["peer"] == link.peer_id and t["phase"] == "receiving":
                    self._recv_fail(tid, "The connection dropped.")
        self._configure_backend()

    # ==== frames from a peer ========================================================
    def _on_frame(self, link, ftype, body):
        pid = link.peer_id
        p = self._peers.get(pid)
        if p:
            p.last_seen = time.time()
        m = decode(ftype, body)
        if m is None:
            return
        t = m.get("t")
        if t in ("move", "button", "wheel", "key"):
            if self._mode == "driven" and self._active == pid:
                if t == "move":
                    self._backend.handle({"c": "move", "dx": m["dx"], "dy": m["dy"]})
                elif t == "button":
                    self._backend.handle({"c": "button", "b": m["b"], "d": m["d"]})
                elif t == "wheel":
                    self._backend.handle({"c": "wheel", "dx": m["dx"], "dy": m["dy"]})
                else:
                    self._backend.handle({"c": "key", "k": m["k"], "d": m["d"]})
            return
        if t == "ping":
            return
        if t == "ready":
            if p:
                p.version = m.get("version")
                p.screens = m.get("screens")
            mine = (self._store.pair(pid) or {}).get("side")
            if not mine and m.get("side") in SIDES and not self._side_taken(m["side"], pid):
                self._store.update_pair(pid, side=m["side"])
                self._configure_backend()
            return
        if t == "screens":
            if p:
                p.screens = m.get("rects")
            return
        if t == "layout":
            side = m.get("side")
            if side is None or side in SIDES:
                if side and self._side_taken(side, pid):
                    for other, rec in self._store.pairs().items():
                        if other != pid and rec.get("side") == side:
                            self._store.update_pair(other, side=None)
                self._store.update_pair(pid, side=side)
                self._configure_backend()
            return
        if t == "enter":
            with self._lock:
                if self._mode == "driving":
                    link.msg({"t": "busy"})
                    return
                side = m.get("side")
                self._set_mode("driven", pid, side)
                self._backend.handle({"c": "lock", "on": bool(m.get("locked"))})
                self._backend.handle({"c": "driven", "exits": [side] if side in SIDES else [], "side": side,
                                      "frac": float(m.get("frac", 0.5))})
            return
        if t == "busy":
            with self._lock:
                if self._mode == "driving" and self._active == pid:
                    self._backend.handle({"c": "grab", "on": False})
                    self._set_mode("home")
            return
        if t == "leave":
            with self._lock:
                if self._mode == "driving" and self._active == pid:
                    side = self._side
                    self._backend.handle({"c": "grab", "on": False})
                    if side:
                        self._backend.handle({"c": "place", "side": side, "frac": float(m.get("frac", 0.5))})
                    self._set_mode("home")
            return
        if t == "release":
            with self._lock:
                if self._mode == "driven" and self._active == pid:
                    self._backend.handle({"c": "release"})
                    self._backend.handle({"c": "driven", "exits": []})
                    self._set_mode("home")
                elif self._mode == "driving" and self._active == pid:
                    self._backend.handle({"c": "grab", "on": False})
                    self._set_mode("home")
            return
        if t == "lock":
            if self._mode == "driven" and self._active == pid:
                self._backend.handle({"c": "lock", "on": bool(m.get("on"))})
            return
        if t == "clip":
            if self._store.get("clipboard") and (m.get("kind") == "text" or self._store.get("clipboard_images")):
                data = m.get("data")
                if m.get("kind") == "png" and "_data" in m:
                    data = b64e(m["_data"])
                if data is not None:
                    self._backend.handle({"c": "clip_set", "kind": m.get("kind"), "data": data})
            return
        if t == "action":
            a = m.get("a")
            if not self._store.get("remote_actions"):
                return
            if a == "ring":
                self._notice("%s is ringing this computer" % self._peer_name(pid))
            self._backend.handle({"c": "action", "a": a, "from": self._peer_name(pid)})
            return
        if t in ("view", "vin", "view_ok", "view_refused", "frame"):
            self._on_view_msg(pid, link, m)
            return
        if t in ("cam", "cam_ok", "cam_refused", "camframe"):
            self._on_cam_msg(pid, link, m)
            return
        if t in ("extend", "extend_refused"):
            self._on_extend_msg(pid, link, m)
            return
        if t in ("listen", "listen_ok", "listen_refused", "mic", "mic_ok", "mic_refused", "pcm"):
            self._on_sound_msg(pid, link, m)
            return
        if t == "files":
            self._on_files(pid, m)
        elif t == "piece":
            self._on_piece(m)
        elif t == "file_done":
            self._on_file_done(m)
        elif t == "files_done":
            self._on_files_done(m)
        elif t == "files_cancel":
            tr = self._transfers.get(m.get("tid"))
            if tr and tr["dir"] == "out" and tr["phase"] == "sending":
                tr.update(phase="cancelled")
            elif tr:
                self._recv_fail(m.get("tid"), "Cancelled on the other computer.", phase="cancelled")
        elif t == "files_refused":
            tr = self._transfers.get(m.get("tid"))
            if tr:
                tr.update(phase="failed", error="%s isn't accepting files." % tr["peer_name"])
        elif t == "unpair":
            self._notice("%s unpaired from this computer." % self._peer_name(pid))
            self._store.forget(pid)
            link.close()

    # ==== backend events ===========================================================
    def _on_backend(self, ev, forced=False):
        t = ev.get("t")
        if t == "move":
            with self._lock:
                if self._mode != "driving":
                    return
                link = self._active_link()
                speed = float(self._store.get("speed") or 1.0)
                self._acc[0] += ev["dx"] * speed
                self._acc[1] += ev["dy"] * speed
                dx, dy = int(self._acc[0]), int(self._acc[1])
                self._acc[0] -= dx
                self._acc[1] -= dy
            if link and (dx or dy):
                link.move(dx, dy)
            return
        if t in ("button", "wheel", "key"):
            link = self._active_link() if self._mode == "driving" else None
            if not link:
                return
            if t == "button":
                link.button(ev["b"], ev["d"])
            elif t == "wheel":
                link.wheel(ev["dx"], ev["dy"])
            else:
                link.key(self._translate(ev["k"]), ev["d"])
            return
        if t == "cross":
            self._on_cross(ev["side"], ev.get("frac", 0.5))
            return
        if t == "exit":
            with self._lock:
                if self._mode == "driven":
                    link = self._active_link()
                    if link:
                        link.msg({"t": "leave", "side": ev.get("side"), "frac": ev.get("frac", 0.5)})
                    self._set_mode("home")
            return
        if t == "home_hotkey":
            self.go_home()
            return
        if t == "lock":
            with self._lock:
                self._locked = bool(ev.get("on"))
                if forced:
                    self._backend.handle({"c": "lock", "on": self._locked})
                link = self._active_link() if self._mode == "driving" else None
            if link:
                link.msg({"t": "lock", "on": self._locked})
            return
        if t == "clip":
            if not self._store.get("clipboard"):
                return
            if ev["kind"] == "png" and not self._store.get("clipboard_images"):
                return
            for p in list(self._peers.values()):
                if not (p.main and not p.main.closed):
                    continue
                if ev["kind"] == "text" and len(ev["data"]) < 200000:
                    p.main.msg({"t": "clip", "kind": "text", "data": ev["data"]})
                else:
                    link = p.bulk if (p.bulk and not p.bulk.closed) else p.main
                    if ev["kind"] == "png":
                        link.blob({"t": "clip", "kind": "png"}, b64d(ev["data"]))
                    else:
                        link.msg({"t": "clip", "kind": "text", "data": ev["data"]})
            return
        if t == "screens":
            self._screens = ev.get("rects") or []
            for p in list(self._peers.values()):
                if p.main:
                    p.main.msg({"t": "screens", "rects": self._screens})
            return
        if t == "permissions":
            self._permissions = ev.get("p") or {}
            return
        if t == "frame":
            self._on_local_frame(ev)
            return
        if t == "audio":
            self._on_local_audio(ev)
            return
        if t == "audio_err":
            self._on_audio_err(ev)
            return
        if t == "vdisplay":
            self._on_vdisplay(ev)
            return
        if t == "camframe":
            self._on_local_camframe(ev)
            return
        if t == "vcam":
            if ev.get("error"):
                self._notice(ev["error"])
            elif ev.get("on"):
                self._notice("“Kvm Camera” is ready: pick it as the camera in any app here.")
            return
        if t == "camera":
            if not ev.get("on") and ev.get("error"):
                for pid in list(self._cam_watchers):
                    self._drop_cam_watcher(pid, why="failed", error=ev["error"])
            return
        if t == "log":
            self._log(ev.get("text"))

    def _on_cross(self, side, frac):
        with self._lock:
            pid = self._peer_at(side)
            p = self._peers.get(pid) if pid else None
            if self._mode != "home" or not (p and p.main and not p.main.closed):
                self._backend.handle({"c": "grab", "on": False})
                return
            self._acc = [0.0, 0.0]
            self._set_mode("driving", pid, side)
            p.main.msg({"t": "enter", "side": OPPOSITE[side], "frac": frac, "locked": self._locked})

    def _leave_driving(self, recall):
        link = self._active_link()
        if link and recall:
            link.msg({"t": "release"})
        self._backend.handle({"c": "grab", "on": False})
        self._set_mode("home")

    def _translate(self, hid, pid=None):
        if not self._store.get("swap_cmd_ctrl"):
            return hid
        rec = self._store.pair(pid or self._active) or {}
        mine, theirs = this_platform(), rec.get("platform")
        if theirs and mine != theirs and "mac" in (mine, theirs):
            return keys.SWAP_CMD_CTRL.get(hid, hid)
        return hid

    # ==== helpers ====================================================================
    def _set_mode(self, mode, pid=None, side=None):
        self._mode = mode
        self._active = pid if mode != "home" else None
        self._side = side if mode != "home" else None

    def _active_link(self):
        p = self._peers.get(self._active) if self._active else None
        return p.main if (p and p.main and not p.main.closed) else None

    def _peer_at(self, side):
        for pid, rec in self._store.pairs().items():
            if rec.get("side") == side:
                return pid
        return None

    def _side_taken(self, side, pid):
        other = self._peer_at(side)
        return other is not None and other != pid

    def _peer_name(self, pid):
        rec = self._store.pair(pid) or {}
        return rec.get("name") or "the other computer"

    def _configure_backend(self):
        sides = []
        for pid, rec in self._store.pairs().items():
            p = self._peers.get(pid)
            if rec.get("side") and p and p.main and not p.main.closed:
                sides.append(rec["side"])
        s = self._store
        self._backend.handle({"c": "config", "sides": sides, "cross_mod": s.get("cross_modifier"),
                              "return_hotkey": s.get("return_hotkey"), "lock_key": s.get("lock_key"),
                              "clipboard": bool(s.get("clipboard") and any(p.main for p in self._peers.values())),
                              "clipboard_images": bool(s.get("clipboard_images"))})

    def _notice(self, text):
        with self._lock:
            self._notice_n += 1
            self._notices.append({"id": self._notice_n, "text": text, "ts": time.time()})
            self._notices = self._notices[-30:]

    def _log(self, text):
        if os.environ.get("KVM_DEBUG"):
            print("kvm:", text)


class PairError(Exception):
    pass


class _Stop(Exception):
    pass


def _sound_why(m, name, what):
    why = m.get("why")
    if m.get("error"):
        return m["error"] if why != "nocable" else "%s: %s" % (name, m["error"])
    if why == "off":
        return ("%s doesn't share its sound. Turn it on in Kvm settings there." if what == "hear"
                else "%s doesn't accept a microphone. Turn it on in Kvm settings there.") % name
    if why == "stopped":
        return ("%s stopped sharing its sound." if what == "hear" else "%s stopped taking your microphone.") % name
    return "%s can't do sound yet." % name


def _why(code):
    return {"busy": "That computer is already pairing with another one. Try again in a moment.",
            "wrong_code": "That code didn't match. Check it and try again."}.get(code, "Pairing didn't finish. Try again.")


def _unique(folder, name):
    base, ext = os.path.splitext(name)
    n, cand = 1, name
    while os.path.exists(os.path.join(folder, cand)):
        n += 1
        cand = "%s (%d)%s" % (base, n, ext)
    return cand


def _unique_path(path):
    if not os.path.exists(path):
        return path
    return os.path.join(os.path.dirname(path), _unique(os.path.dirname(path), os.path.basename(path)))


_ADDR = {"at": 0.0, "list": [], "busy": False}
_ADDR_LOCK = threading.Lock()


def _cached_addresses(max_age=30.0):
    """This computer's addresses for status(), which the window polls several times a second.
    Looking them up can take seconds (the hostname lookup goes through mDNS on a Mac), so they're
    refreshed in the background and status() never waits for it."""
    with _ADDR_LOCK:
        stale = time.time() - _ADDR["at"] > max_age
        if stale and not _ADDR["busy"]:
            _ADDR["busy"] = True
            threading.Thread(target=_refresh_addresses, daemon=True).start()
        return list(_ADDR["list"])


def _refresh_addresses():
    try:
        found = _lan_addresses()
    finally:
        with _ADDR_LOCK:
            _ADDR["busy"] = False
    with _ADDR_LOCK:
        _ADDR["list"], _ADDR["at"] = found, time.time()


def _lan_addresses():
    out = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        out.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            a = info[4][0]
            if a not in out and not a.startswith("127."):
                out.append(a)
    except OSError:
        pass
    return out
