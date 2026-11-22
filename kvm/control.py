"""How the app window reaches the Kvm service on Windows.

The service serves the agent's window methods as JSON over HTTP on 127.0.0.1 only. Every request
must carry the token from %ProgramData%\\PXLVZN\\KvmControl\\token (readable by people who use this
PC, not by web pages), and requests a browser would send (with an Origin header) are refused.
"""

import json
import os
import secrets
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 47611
METHODS = {"status", "rename", "set_setting", "set_side", "forget", "add_address", "pair", "pair_code", "pair_cancel",
           "action", "go_home", "set_locked", "send_files", "cancel_transfer", "clear_transfers",
           "view_start", "view_stop", "view_input", "stop_sharing",
           "listen_start", "listen_stop", "mic_start", "mic_stop", "stop_sound",
           "extend_start", "extend_stop", "extend_end"}


def token_dir():
    return os.path.join(os.environ.get("ProgramData") or "C:\\ProgramData", "PXLVZN", "KvmControl")


def serve(agent, _data_dir=None, port=PORT, log=None):
    log = log or (lambda m: None)
    folder = token_dir()
    os.makedirs(folder, exist_ok=True)
    token = secrets.token_hex(24)
    path = os.path.join(folder, "token")
    with open(path, "w") as f:
        f.write(token)
    log("control token written")
    # Only the system, administrators and signed-in users may read the token. Done on its own
    # thread: icacls has been seen to stall in a just-started service, and the window must not
    # wait for it (ProgramData already keeps other accounts' files read-only).
    threading.Thread(target=_restrict, args=(folder, log), name="kvm-control-acl", daemon=True).start()
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            if self.headers.get("Origin") or self.headers.get("X-Kvm-Token") != token:
                self.send_error(403)
                return
            name = self.path.strip("/")
            if name not in METHODS:
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                args = json.loads(self.rfile.read(n) or b"[]")
                res = getattr(agent, name)(*args)
                body = json.dumps({"ok": True, "result": res}, default=str).encode()
            except Exception as e:
                body = json.dumps({"ok": False, "error": str(e)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _restrict(folder, log):
    import subprocess
    import time
    t = time.time()
    try:
        r = subprocess.run(["icacls", folder, "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F",
                            "*S-1-5-32-544:(OI)(CI)F", "*S-1-5-4:(OI)(CI)R"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=60, creationflags=0x08000000)
        log("control folder locked down (icacls %s, %.1f s)" % (r.returncode, time.time() - t))
    except Exception as e:
        log("control folder lock-down failed after %.1f s: %r" % (time.time() - t, e))


class RemoteAgent(object):
    """The window's view of the service's agent: same methods, over HTTP."""

    def __init__(self, port=PORT):
        self._port = port
        with open(os.path.join(token_dir(), "token")) as f:
            self._token = f.read().strip()

    def _call(self, name, *args):
        req = urllib.request.Request("http://127.0.0.1:%d/%s" % (self._port, name), data=json.dumps(list(args)).encode(),
                                     headers={"X-Kvm-Token": self._token, "Content-Type": "application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=10) as r:
            obj = json.loads(r.read().decode())
        if not obj.get("ok"):
            raise RuntimeError(obj.get("error"))
        return obj["result"]

    def __getattr__(self, name):
        if name not in METHODS:
            raise AttributeError(name)
        return lambda *a: self._call(name, *a)

    def alive(self):
        try:
            self._call("status")
            return True
        except Exception:
            return False
