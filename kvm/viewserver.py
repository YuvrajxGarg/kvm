"""Serves the screens this computer is watching to the viewer window, as a live JPEG stream
(multipart/x-mixed-replace, which an <img> plays by itself) on 127.0.0.1 only.

Every address carries a random token that only the Kvm window learns (through the agent), so
other programs and web pages on this computer can't watch.
"""

import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BOUNDARY = "kvmframe"


class ViewServer(object):
    def __init__(self, agent, port=0):
        self._agent = agent
        self._port = port
        self.token = secrets.token_urlsafe(24)
        self._srv = None

    def start(self):
        server = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if q.get("k", [""])[0] != server.token:
                    self.send_error(403)
                    return
                parts = u.path.strip("/").split("/")
                if len(parts) != 2 or parts[0] not in ("view", "frame"):
                    self.send_error(404)
                    return
                pid = parts[1]
                if parts[0] == "frame":
                    after = int((q.get("after") or ["0"])[0] or 0)
                    jpeg, seq = server._agent.view_frame(pid, after, timeout=float((q.get("wait") or ["5"])[0]))
                    if jpeg is None:
                        self.send_error(404 if seq < 0 else 204)
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(jpeg)))
                    self.send_header("X-Seq", str(seq))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(jpeg)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=" + BOUNDARY)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                seq = 0
                try:
                    while True:
                        jpeg, seq2 = server._agent.view_frame(pid, seq)
                        if seq2 < 0:
                            return
                        if jpeg is None or seq2 == seq:
                            continue
                        seq = seq2
                        self.wfile.write(("--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
                                          % (BOUNDARY, len(jpeg))).encode("ascii") + jpeg + b"\r\n")
                        self.wfile.flush()
                except (OSError, ValueError):
                    return

        self._srv = ThreadingHTTPServer(("127.0.0.1", self._port), H)
        self._srv.daemon_threads = True
        threading.Thread(target=self._srv.serve_forever, name="kvm-view-http", daemon=True).start()
        return self

    @property
    def port(self):
        return self._srv.server_address[1] if self._srv else None

    def url(self, pid, kind="view"):
        return "http://127.0.0.1:%d/%s/%s?k=%s" % (self.port, kind, pid, self.token)

    def stop(self):
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()
