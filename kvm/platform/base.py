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
  {"t": "log", "text"}
"""

import base64
import hashlib
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


def _mod_set(name):
    return {"ctrl": keys.CTRL, "alt": keys.ALT, "shift": keys.SHIFT, "meta": keys.META}.get(name, set())


class FakeBackend(Backend):
    """For tests and Linux development: records what it would do."""
    name = "fake"
    can_capture = True
    can_inject = True

    def __init__(self, rects=((0, 0, 1920, 1080),)):
        self.rects = [tuple(r) for r in rects]
        self.cursor = (100.0, 100.0)
        self.posted = []
        self.clip = None
        Backend.__init__(self)

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

    def action(self, what, cmd):
        self.posted.append(("action", what))
