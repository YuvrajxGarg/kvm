"""What every platform's input layer does, written once.

A backend watches this computer's pointer and keys, and puts input from another computer onto
this one. The agent drives it with commands (dicts with a "c" key) and hears back through
`sink(event)`. The same commands travel over a pipe to the Windows helper (platform/winhelper.py),
which is why everything here is plain data.

Events a backend sends:
  {"t": "cross", "side", "frac"}            the pointer pushed past an edge with a computer on it
  {"t": "move", "dx", "dy"} / "button" / "wheel" / "key"   captured input while grabbed
  {"t": "home_hotkey"}                      the return hotkey was pressed while grabbed
  {"t": "lock", "on"}                       cursor lock toggled
  {"t": "exit", "side", "frac"}             (being driven) the pointer pushed past the edge home
  {"t": "clip", "kind": "text"|"png", "data"}   this computer's clipboard changed
  {"t": "screens", "rects"}                 the monitor layout changed
  {"t": "frame", "jpeg", "w", "h", "seq", "cursor"}   (sharing the screen) a new picture of it
  {"t": "audio", "src", "pcm"} / {"t": "audio_err", ...}   sound (see kvm/audio.py)
  {"t": "vdisplay", "on", "rect", "error"}  the extra (virtual) display for extending onto another computer
  {"t": "camframe", "jpeg", "w", "h"} / {"t": "camera", "on", "error"}   this computer's camera
  {"t": "log", "text"}
"""

import base64
import hashlib
import io
import queue
import threading
import time

from .. import keys
from ..screens import Screens

BUTTONS = (1, 2, 3, 4, 5)
CLIP_TEXT_MAX = 4 << 20
CLIP_PNG_MAX = 24 << 20


class Backend(object):
    name = "base"
    can_capture = False
    can_inject = False

    @property
    def can_audio(self):
        from .. import audio
        return audio.available()

    def __init__(self):
        self.sink = lambda ev: None
        self.watch_sides = []
        self.cross_mod = ""
        self.return_combo = keys.parse_combo("ctrl+alt+esc")
        self.lock_key = keys.BY_NAME.get("scrolllock")
        self.grabbed = False
        self.locked = False
        self.exits = []
        self.held_local = set()      # keys physically down here (for hold-to-cross, hotkeys)
        self.buttons_local = set()
        self.held_inj = set()        # keys we injected and haven't released
        self.buttons_inj = set()
        self.edge_hits = {}
        self.pos = None              # where we think the injected pointer is
        self.screens = Screens(self._screens())
        self.clip_watch = False
        self.clip_images = True
        self._clip_last = None
        self._lock = threading.RLock()
        self._cap = None             # screen sharing settings while someone is watching
        self._cap_gen = 0
        self._audio = None

    # ---- lifecycle -----------------------------------------------------------
    def start(self, sink):
        # Capture callbacks must return at once (macOS turns off a slow event tap, Windows drops a
        # slow hook, and then keys land on the wrong computer), so events go out on their own thread.
        self._real_sink = sink
        self._q = queue.Queue()
        self.sink = self._q.put
        threading.Thread(target=self._sink_loop, name="kvm-sink", daemon=True).start()
        self.sink({"t": "screens", "rects": self.screens.public()})
        threading.Thread(target=self._poll_loop, name="kvm-poll", daemon=True).start()

    def _sink_loop(self):
        while True:
            ev = self._q.get()
            try:
                self._real_sink(ev)
            except Exception:
                import traceback

                traceback.print_exc()

    def stop(self):
        self.grab(False)
        self.release()
        if self._audio:
            self._audio.stop()

    def _poll_loop(self):
        n = 0
        while True:
            time.sleep(0.4)
            n += 1
            try:
                if self.clip_watch:
                    self._check_clipboard()
                if n % 5 == 0:
                    rects = self._screens()
                    if rects and [list(map(float, r)) for r in rects] != self.screens.public():
                        self.screens = Screens(rects)
                        self.sink({"t": "screens", "rects": self.screens.public()})
            except Exception as e:  # never let polling die
                self.sink({"t": "log", "text": "poll: %s" % e})

    # ---- commands ------------------------------------------------------------
    def handle(self, cmd):
        c = cmd.get("c")
        if c == "config":
            self.watch_sides = [s for s in cmd.get("sides", []) if s in ("left", "right", "top", "bottom")]
            self.cross_mod = cmd.get("cross_mod") or ""
            self.return_combo = keys.parse_combo(cmd.get("return_hotkey") or "ctrl+alt+esc")
            self.lock_key = keys.BY_NAME.get(cmd.get("lock_key") or "scrolllock")
            self.clip_watch = bool(cmd.get("clipboard"))
            self.clip_images = bool(cmd.get("clipboard_images", True))
        elif c == "grab":
            self.grab(bool(cmd.get("on")))
        elif c == "place":
            self.place(cmd["side"], cmd.get("frac", 0.5))
        elif c == "driven":
            self.exits = list(cmd.get("exits") or [])
            if cmd.get("side"):
                self.place(cmd["side"], cmd.get("frac", 0.5))
        elif c == "lock":
            self.locked = bool(cmd.get("on"))
        elif c == "move":
            self.inject_move(cmd["dx"], cmd["dy"])
        elif c == "button":
            self.inject_button(cmd["b"], cmd["d"])
        elif c == "wheel":
            self.inject_wheel(cmd["dx"], cmd["dy"])
        elif c == "key":
            self.inject_key(cmd["k"], cmd["d"])
        elif c == "release":
            self.release()
        elif c == "clip_set":
            self.clip_set(cmd.get("kind"), cmd.get("data"))
        elif c == "action":
            self.action(cmd.get("a"), cmd)
        elif c == "sas":
            self.sas()
        elif c == "capture":
            self.capture(cmd)
        elif c == "abs":
            self.inject_abs(cmd["x"], cmd["y"], cmd.get("rect"))
        elif c == "vdisplay":
            self.vdisplay(cmd)
        elif c == "camera":
            self.camera(cmd)
        elif c == "vcam_frame":
            self.vcam().frame(base64.b64decode(cmd.get("jpeg") or ""))
        elif c == "vcam_stop":
            if getattr(self, "_vcam", None):
                self._vcam.stop()
        elif c == "audio_capture":
            self.audio().capture(cmd.get("src"), bool(cmd.get("on")))
        elif c == "audio_play":
            self.audio().play(cmd.get("sink"), base64.b64decode(cmd.get("pcm") or ""))

    def audio(self):
        if self._audio is None:
            from ..audio import Audio
            self._audio = Audio(self.sink)
        return self._audio

    # ---- driving: what the platform capture calls -----------------------------
    def on_local_move(self, x, y, dx, dy):
        """Pointer moved here while not grabbed. Returns True to swallow the event."""
        if self.grabbed or not self.watch_sides or self.locked or self.buttons_local:
            self.edge_hits = {}
            return False
        if self.cross_mod and not (self.held_local & _mod_set(self.cross_mod)):
            return False
        for side in self.watch_sides:
            if self.screens.on_edge(x, y, side):
                pushing = (side == "right" and dx > 0) or (side == "left" and dx < 0) or \
                          (side == "bottom" and dy > 0) or (side == "top" and dy < 0)
                self.edge_hits[side] = self.edge_hits.get(side, 0) + 1
                if pushing or self.edge_hits[side] >= 3:
                    self.edge_hits = {}
                    self.grab(True)
                    self.sink({"t": "cross", "side": side, "frac": self.screens.frac(x, y, side), "x": x, "y": y})
                    return True
            else:
                self.edge_hits.pop(side, None)
        return False

    def on_local_key(self, hid, down):
        """A key here. Returns True to swallow it (it's going to the other computer)."""
        if hid is None:
            return self.grabbed
        if down:
            self.held_local.add(hid)
        else:
            self.held_local.discard(hid)
        if down and hid == self.lock_key:
            self.locked = not self.locked
            self.sink({"t": "lock", "on": self.locked})
            return self.grabbed
        if self.grabbed:
            if down and keys.combo_down(self.return_combo, self.held_local):
                self.sink({"t": "home_hotkey"})
                return True
            self.sink({"t": "key", "k": hid, "d": bool(down)})
            return True
        return False

    def on_local_button(self, b, down):
        if down:
            self.buttons_local.add(b)
        else:
            self.buttons_local.discard(b)
        if self.grabbed:
            self.sink({"t": "button", "b": b, "d": bool(down)})
            return True
        return False

    def on_local_wheel(self, dx, dy):
        if self.grabbed:
            self.sink({"t": "wheel", "dx": dx, "dy": dy})
            return True
        return False

    def on_grabbed_move(self, dx, dy):
        if dx or dy:
            self.sink({"t": "move", "dx": dx, "dy": dy})

    def grab(self, on):
        with self._lock:
            if on == self.grabbed:
                return
            self.grabbed = on
            self.buttons_local = set()
            self._set_grab(on)

    def place(self, side, frac):
        """Put this computer's pointer on its `side` edge at `frac`, just inside."""
        self.screens = Screens(self._screens() or self.screens.public())
        x, y = self.screens.entry(side, frac, inset=2.0)
        self.pos = (x, y)
        self._warp(x, y)

    # ---- being driven ----------------------------------------------------------
    def inject_move(self, dx, dy):
        cur = self._cursor()
        if cur is None:
            cur = self.pos or (self.screens.left + 10, self.screens.top + 10)
        nx, ny, exit_side, frac = self.screens.step(cur[0], cur[1], dx, dy, () if self.locked else self.exits)
        if exit_side:
            self.release()
            self.exits = []
            self.sink({"t": "exit", "side": exit_side, "frac": frac})
            return
        self.pos = (nx, ny)
        self._post_move(nx, ny, set(self.buttons_inj))

    def inject_button(self, b, down):
        if b not in BUTTONS:
            return
        if down:
            self.buttons_inj.add(b)
        else:
            if b not in self.buttons_inj:
                return
            self.buttons_inj.discard(b)
        cur = self._cursor() or self.pos or (0, 0)
        self._post_button(b, down, cur[0], cur[1])

    def inject_wheel(self, dx, dy):
        self._post_wheel(dx, dy)

    def inject_key(self, hid, down):
        if down:
            if hid in (keys.BY_NAME["delete"], keys.BY_NAME["backspace"]) and \
                    (self.held_inj & keys.CTRL) and (self.held_inj & keys.ALT):
                self.sas()  # Ctrl+Alt+Del can't be typed by software; ask Windows for it instead
                return
            self.held_inj.add(hid)
        else:
            if hid not in self.held_inj:
                return
            self.held_inj.discard(hid)
        self._post_key(hid, down)

    def release(self):
        """Let go of every key and button we pressed (the other computer went away or home)."""
        for hid in list(self.held_inj):
            try:
                self._post_key(hid, False)
            except Exception:
                pass
        self.held_inj = set()
        cur = self._cursor() or self.pos or (0, 0)
        for b in list(self.buttons_inj):
            try:
                self._post_button(b, False, cur[0], cur[1])
            except Exception:
                pass
        self.buttons_inj = set()

    def inject_abs(self, fx, fy, rect=None):
        """Put the pointer at a point given as fractions of the whole desktop, or of `rect` (x, y, w, h),
        from a screen viewer."""
        sc = self.screens
        left, top, w, h = rect if rect else (sc.left, sc.top, sc.right - sc.left, sc.bottom - sc.top)
        x = left + max(0.0, min(1.0, float(fx))) * w
        y = top + max(0.0, min(1.0, float(fy))) * h
        x, y = sc.clamp(x, y)
        self.pos = (x, y)
        self._post_move(x, y, set(self.buttons_inj))

    # ---- screen sharing ------------------------------------------------------------
    def capture(self, cmd):
        """Start (or retune, or stop) sending pictures of this computer's screen."""
        with self._lock:
            self._cap_gen += 1
            if not cmd.get("on"):
                self._cap = None
                return
            rect = cmd.get("rect")
            self._cap = {"fps": max(1.0, min(30.0, float(cmd.get("fps") or 12))),
                         "maxw": int(cmd.get("maxw") or 1600), "q": int(cmd.get("q") or 70),
                         "rect": [float(v) for v in rect] if rect else None}
            gen = self._cap_gen
        threading.Thread(target=self._capture_loop, args=(gen,), name="kvm-capture", daemon=True).start()

    def _capture_loop(self, gen):
        seq, last, last_sent, fails = 0, None, 0.0, 0
        self._capture_thread_init()
        while True:
            with self._lock:
                if gen != self._cap_gen or not self._cap:
                    return
                cap = dict(self._cap)
            t0 = time.time()
            try:
                img = self._grab_region(cap["rect"]) if cap["rect"] else self._grab_screen()
                fails = 0
            except Exception as e:
                img = None
                fails += 1
                if fails in (1, 10, 100):
                    self.sink({"t": "log", "text": "screen capture: %r" % e})
            if img is not None:
                cur = self._cursor_frac(cap["rect"])
                if cur:
                    draw_pointer(img, cur[0] * img.size[0], cur[1] * img.size[1])
                jpeg, w, h = encode_jpeg(img, cap["maxw"], cap["q"])
                digest = hashlib.sha1(jpeg).digest()
                # An unchanged screen is sent again now and then, so a viewer that joined late gets it.
                if digest != last or t0 - last_sent > 2.0:
                    last, last_sent = digest, t0
                    seq += 1
                    self.sink({"t": "frame", "jpeg": base64.b64encode(jpeg).decode("ascii"), "w": w, "h": h,
                               "seq": seq, "cursor": cur})
            time.sleep(max(0.005, 1.0 / cap["fps"] - (time.time() - t0)))

    def _cursor_frac(self, rect=None):
        cur = self._cursor()
        sc = self.screens
        left, top, w, h = rect if rect else (sc.left, sc.top, sc.right - sc.left, sc.bottom - sc.top)
        if cur is None or w <= 0 or h <= 0:
            return None
        fx, fy = (cur[0] - left) / w, (cur[1] - top) / h
        if rect and not (0 <= fx <= 1 and 0 <= fy <= 1):
            return None  # the pointer is on another display
        return [fx, fy]

    def _grab_region(self, rect):
        """A PIL image of part of the desktop, (x, y, w, h) in desktop coordinates."""
        img = self._grab_screen()
        if img is None:
            return None
        sc = self.screens
        k = img.size[0] / max(1.0, sc.right - sc.left)  # pixels per point (2 on a Retina Mac)
        x, y, w, h = rect
        box = (int((x - sc.left) * k), int((y - sc.top) * k), int((x - sc.left + w) * k), int((y - sc.top + h) * k))
        return img.crop(box)

    # ---- this computer's camera, for another computer -----------------------------------
    can_camera = False
    can_vcam = False          # a virtual webcam here shows the other computer's camera to apps

    def vcam(self):
        if getattr(self, "_vcam", None) is None:
            from ..vcam import VirtualCamera
            self._vcam = VirtualCamera(self.sink, all_users=bool(getattr(self, "_secure", False)))
        return self._vcam

    def camera(self, cmd):
        if cmd.get("on"):
            self.sink({"t": "camera", "on": False, "error": "This computer can't share its camera yet."})

    # ---- extending this computer onto another (an extra, virtual display) ---------------
    def vdisplay(self, cmd):
        if cmd.get("on"):
            self.sink({"t": "vdisplay", "on": False, "error": "This computer can't add an extra display yet."})

    def _capture_thread_init(self):
        pass

    def _grab_screen(self):
        """A PIL image of the whole desktop (every monitor), or None."""
        return None

    # ---- clipboard ---------------------------------------------------------------
    def _check_clipboard(self):
        got = self._clip_get(self.clip_images)
        if not got:
            return
        kind, data = got
        h = hashlib.sha256((kind + ":").encode() + (data.encode("utf-8") if kind == "text" else data)).hexdigest()
        if self._clip_last is None:
            self._clip_last = h  # what's there when Kvm starts isn't news
            return
        if h == self._clip_last:
            return
        self._clip_last = h
        if kind == "text" and len(data) <= CLIP_TEXT_MAX:
            self.sink({"t": "clip", "kind": "text", "data": data})
        elif kind == "png" and len(data) <= CLIP_PNG_MAX:
            self.sink({"t": "clip", "kind": "png", "data": base64.b64encode(data).decode("ascii")})

    def clip_set(self, kind, data):
        if kind == "png":
            raw = base64.b64decode(data)
            self._clip_last = hashlib.sha256(b"png:" + raw).hexdigest()
            self._clip_put("png", raw)
        elif kind == "text":
            self._clip_last = hashlib.sha256(("text:" + data).encode("utf-8")).hexdigest()
            self._clip_put("text", data)

    # ---- actions -------------------------------------------------------------------
    def action(self, what, cmd):
        pass

    def sas(self):
        pass

    def permissions(self):
        return {}

    # ---- the platform fills these in -----------------------------------------------
    def _screens(self):
        return [(0, 0, 1920, 1080)]

    def _cursor(self):
        return None

    def _warp(self, x, y):
        pass

    def _set_grab(self, on):
        pass

    def _post_move(self, x, y, buttons):
        pass

    def _post_button(self, b, down, x, y):
        pass

    def _post_wheel(self, dx, dy):
        pass

    def _post_key(self, hid, down):
        pass

    def _clip_get(self, images):
        return None

    def _clip_put(self, kind, data):
        pass


def draw_pointer(img, x, y):
    """Screen pictures don't include the pointer, so draw one where it is (scaled for the picture)."""
    from PIL import ImageDraw
    k = max(1.0, img.size[0] / 2400.0) * 1.4
    pts = [(0, 0), (0, 17), (4.5, 13), (7.5, 20), (10.5, 18.6), (7.6, 12), (13, 12)]
    poly = [(x + px * k, y + py * k) for px, py in pts]
    d = ImageDraw.Draw(img)
    d.polygon(poly, fill=(255, 255, 255), outline=(0, 0, 0))


def encode_jpeg(img, maxw, quality):
    """PIL image -> (JPEG bytes, width, height), scaled down to at most maxw wide."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if maxw and w > maxw:
        h = max(1, int(round(h * maxw / float(w))))
        w = maxw
        img = img.resize((w, h), 2)  # bilinear: quick, and fine for a live view
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue(), w, h


def _mod_set(name):
    return {"ctrl": keys.CTRL, "alt": keys.ALT, "shift": keys.SHIFT, "meta": keys.META}.get(name, set())


class FakeBackend(Backend):
    """For tests and Linux development: records what it would do."""
    name = "fake"
    can_capture = True
    can_inject = True
    can_vdisplay = True
    can_camera = True

    def camera(self, cmd):
        self.posted.append(("camera", bool(cmd.get("on"))))

    def __init__(self, rects=((0, 0, 1920, 1080),)):
        self.rects = [tuple(r) for r in rects]
        self.cursor = (100.0, 100.0)
        self.posted = []
        self.clip = None
        self.sound = []           # ("capture", src, on) / ("play", sink, pcm bytes)
        self.audio_ok = True
        Backend.__init__(self)

    @property
    def can_audio(self):
        return self.audio_ok

    def audio(self):
        be = self

        class _A(object):
            def capture(self, src, on):
                be.posted.append(("audio_capture", src, on))

            def play(self, sink, pcm):
                be.sound.append((sink, pcm))

            def stop(self):
                pass
        return _A()

    def _screens(self):
        return self.rects

    def _cursor(self):
        return self.cursor

    def _warp(self, x, y):
        self.cursor = (x, y)
        self.posted.append(("warp", x, y))

    def _set_grab(self, on):
        self.posted.append(("grab", on))

    def _post_move(self, x, y, buttons):
        self.cursor = (x, y)
        self.posted.append(("move", x, y))

    def _post_button(self, b, down, x, y):
        self.posted.append(("button", b, down))

    def _post_wheel(self, dx, dy):
        self.posted.append(("wheel", dx, dy))

    def _post_key(self, hid, down):
        self.posted.append(("key", hid, down))

    def _clip_get(self, images):
        return self.clip

    def _clip_put(self, kind, data):
        self.clip = (kind, data)
        self.posted.append(("clip", kind))

    def sas(self):
        self.posted.append(("sas",))

    def vdisplay(self, cmd):
        base = [r for r in self.rects if not getattr(self, "_vrect", None) or tuple(r) != self._vrect]
        if cmd.get("on"):
            right = max(r[0] + r[2] for r in base)
            self._vrect = (right, 0.0, float(cmd.get("w") or 1920), float(cmd.get("h") or 1080))
            self.rects = base + [self._vrect]
        else:
            self._vrect = None
            self.rects = base
        self.screens = Screens(self.rects)
        self.posted.append(("vdisplay", bool(cmd.get("on"))))
        self.sink({"t": "screens", "rects": self.screens.public()})
        self.sink({"t": "vdisplay", "on": bool(cmd.get("on")), "rect": list(self._vrect) if self._vrect else None})

    def _grab_screen(self):
        from PIL import Image
        sc = self.screens
        w, h = int(sc.right - sc.left), int(sc.bottom - sc.top)
        x, y = self.cursor
        return Image.new("RGB", (max(1, w), max(1, h)), (int(x) % 256, int(y) % 256, 90))

    def action(self, what, cmd):
        self.posted.append(("action", what))
