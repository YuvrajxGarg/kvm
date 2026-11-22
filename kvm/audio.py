"""Sound between computers: hear the other computer, and use this microphone on it.

Everything here is 48 kHz stereo, 16-bit, in 20 ms blocks (960 frames, 3840 bytes). A backend
owns one Audio object (on Windows it lives in the helper, in the signed-in session) and talks
to the agent with the same plain events as the rest of the backend:

  capture("output", on)   what this computer is playing (Windows: WASAPI loopback of the
                          default speakers; Mac: kvm-audiotap, a tiny ScreenCaptureKit tool)
  capture("mic", on)      this computer's default microphone
      -> {"t": "audio", "src": "output"|"mic", "pcm": base64}
  play("speaker", pcm)    out of this computer's speakers
  play("mic", pcm)        into a virtual microphone (VB-CABLE on Windows, BlackHole on a Mac),
                          so apps here (Zoom, Discord, ...) hear the other computer's mic
      -> {"t": "audio_err", "src"|"sink", "why": "nocable"|"unsupported"|"failed", "error"}
"""

import base64
import collections
import os
import subprocess
import sys
import threading
import time

RATE = 48000
CH = 2
BLOCK = 960
BLOCK_BYTES = BLOCK * CH * 2
MAX_QUEUE = 12          # blocks (240 ms) before old sound is dropped to catch up
START_QUEUE = 3         # blocks (60 ms) gathered before playing starts
IDLE_CLOSE = 3.0        # seconds without sound before a player lets go of its device
VIRTUAL_MICS = ("cable input", "blackhole", "vb-audio", "voicemeeter input", "loopback audio")

_sc_mod = None
_sc_err = None


def _sc():
    """The soundcard module, imported once (it's heavy, and absent on some systems)."""
    global _sc_mod, _sc_err
    if _sc_mod is None and _sc_err is None:
        try:
            import warnings

            import soundcard
            warnings.filterwarnings("ignore", module="soundcard")
            _sc_mod = soundcard
        except Exception as e:  # no audio library, no audio server, ...
            _sc_err = e
    if _sc_mod is None:
        raise RuntimeError("Sound isn't available on this computer (%s)." % _sc_err)
    return _sc_mod


def available():
    try:
        _sc()
        return True
    except Exception:
        return False


def to_pcm(frames):
    """float32 frames x channels -> interleaved stereo int16 bytes."""
    import numpy as np
    a = np.asarray(frames, dtype=np.float32)
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    if a.shape[1] == 1:
        a = np.repeat(a, 2, axis=1)
    elif a.shape[1] > 2:
        a = a[:, :2]
    return (np.clip(a, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def from_pcm(data):
    """Interleaved stereo int16 bytes -> float32 frames x 2."""
    import numpy as np
    n = len(data) // 4 * 4
    return (np.frombuffer(data[:n], dtype="<i2").astype(np.float32) / 32768.0).reshape(-1, 2)


def is_silent(pcm):
    import numpy as np
    return not np.any(np.frombuffer(pcm, dtype="<i2"))


def find_virtual_mic(speakers):
    """The playback side of a virtual microphone cable ("CABLE Input", "BlackHole 2ch"), by name."""
    for s in speakers:
        n = (getattr(s, "name", "") or "").lower()
        if any(v in n for v in VIRTUAL_MICS):
            return s
    return None


def tap_path():
    """The macOS system-sound tool, next to the app's other files or in a source checkout."""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = []
    if getattr(sys, "_MEIPASS", None):
        cands.append(os.path.join(sys._MEIPASS, "kvm-audiotap"))
    if getattr(sys, "frozen", False):
        exe = os.path.dirname(sys.executable)
        cands += [os.path.join(exe, "kvm-audiotap"), os.path.join(exe, "..", "Frameworks", "kvm-audiotap"),
                  os.path.join(exe, "..", "Resources", "kvm-audiotap")]
    cands += [os.path.join(here, "..", "native-build", "kvm-audiotap")]
    for c in cands:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return os.path.abspath(c)
    return None


def _mac_version():
    try:
        import platform
        return tuple(int(x) for x in platform.mac_ver()[0].split(".")[:2])
    except Exception:
        return (0, 0)


class Audio(object):
    def __init__(self, sink):
        self.sink = sink
        self._gen = {"output": 0, "mic": 0}
        self._on = {"output": False, "mic": False}
        self._players = {}
        self._lock = threading.Lock()
        self._procs = {}

    # ---- capture --------------------------------------------------------------
    def capture(self, src, on):
        if src not in self._gen:
            return
        with self._lock:
            if bool(on) == self._on[src]:
                return
            self._on[src] = bool(on)
            self._gen[src] += 1
            gen = self._gen[src]
            proc = self._procs.pop(src, None)
        if proc:
            _stop_proc(proc)
        if on:
            threading.Thread(target=self._capture_loop, args=(src, gen), name="kvm-audio-" + src, daemon=True).start()

    def _live(self, src, gen):
        return self._on[src] and self._gen[src] == gen

    def _emit(self, src, pcm):
        if pcm and not is_silent(pcm):
            self.sink({"t": "audio", "src": src, "pcm": base64.b64encode(pcm).decode("ascii")})

    def _fail(self, src, why, error):
        with self._lock:
            self._on[src] = False
        self.sink({"t": "audio_err", "src": src, "why": why, "error": error})

    def _capture_loop(self, src, gen):
        failures = 0
        while self._live(src, gen):
            started = time.time()
            try:
                if src == "output" and sys.platform == "darwin":
                    self._tap_loop(gen)
                else:
                    self._record_loop(src, gen)
                return
            except _Unsupported as e:
                self._fail(src, "unsupported", str(e))
                return
            except Exception as e:
                # A device went away (headphones unplugged, default changed): start again on the new one.
                failures = 0 if time.time() - started > 10 else failures + 1
                if failures >= 4:
                    self._fail(src, "failed", "Couldn't %s: %s" % ("hear this computer" if src == "output"
                                                                    else "use the microphone", e))
                    return
                time.sleep(0.5)

    def _record_loop(self, src, gen):
        sc = _sc()
        if src == "output":
            spk = sc.default_speaker()
            dev = sc.get_microphone(id=str(spk.name), include_loopback=True)
            channels = CH
        else:
            dev = sc.default_microphone()
            channels = 1
        name = getattr(dev, "name", "")
        with dev.recorder(samplerate=RATE, channels=channels, blocksize=BLOCK) as rec:
            n = 0
            while self._live(src, gen):
                self._emit(src, to_pcm(rec.record(numframes=BLOCK)))
                n += 1
                if n % 250 == 0:  # every 5 s: follow a new default device
                    now = sc.default_speaker().name if src == "output" else sc.default_microphone().name
                    if src == "output" and now != spk.name or src == "mic" and now != name:
                        raise RuntimeError("default device changed")

    def _tap_loop(self, gen):
        if _mac_version() < (13, 0):
            raise _Unsupported("Hearing a Mac needs macOS 13 or later.")
        path = tap_path()
        if not path:
            raise _Unsupported("This copy of Kvm can't hear the Mac's sound (kvm-audiotap is missing).")
        proc = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with self._lock:
            if not self._live("output", gen):
                _stop_proc(proc)
                return
            self._procs["output"] = proc
        size = BLOCK * CH * 4  # float32 from the tool
        import numpy as np
        while self._live("output", gen):
            data = _read_exact(proc.stdout, size)
            if data is None:
                err = (proc.stderr.read() or b"").decode("utf-8", "replace").strip()
                if not self._live("output", gen):
                    return
                if "permission" in err.lower() or "declined" in err.lower() or "not authorized" in err.lower():
                    raise _Unsupported("Allow Kvm in System Settings > Privacy & Security > Screen & System "
                                       "Audio Recording, then try again.")
                raise RuntimeError(err or "kvm-audiotap stopped")
            self._emit("output", to_pcm(np.frombuffer(data, dtype="<f4").reshape(-1, CH)))
        _stop_proc(proc)

    # ---- playback -------------------------------------------------------------
    def play(self, sink, pcm):
        if sink not in ("speaker", "mic") or not pcm:
            return
        with self._lock:
            p = self._players.get(sink)
            if p is None or not p.alive:
                if p is not None and p.failed and time.time() - p.failed < 10:
                    return  # don't retry a missing device 50 times a second
                p = self._players[sink] = _Player(self, sink)
        p.feed(pcm)

    def stop(self):
        for src in list(self._gen):
            self.capture(src, False)
        for p in list(self._players.values()):
            p.close()


class _Unsupported(Exception):
    pass


class _Player(object):
    def __init__(self, audio, sink):
        self.audio = audio
        self.sink = sink
        self.q = collections.deque()
        self.cond = threading.Condition()
        self.alive = True
        self.failed = 0
        threading.Thread(target=self._run, name="kvm-play-" + self.sink, daemon=True).start()

    def feed(self, pcm):
        with self.cond:
            self.q.append(pcm)
            while len(self.q) > MAX_QUEUE:
                self.q.popleft()
            self.cond.notify()

    def close(self):
        self.alive = False
        with self.cond:
            self.cond.notify()

    def _device(self):
        sc = _sc()
        if self.sink == "speaker":
            return sc.default_speaker()
        dev = find_virtual_mic(sc.all_speakers())
        if dev is None:
            raise _NoCable()
        return dev

    def _run(self):
        try:
            dev = self._device()
            with dev.player(samplerate=RATE, channels=CH, blocksize=BLOCK) as pl:
                waiting = True
                last = time.time()
                while self.alive:
                    with self.cond:
                        need = START_QUEUE if waiting else 1
                        if len(self.q) < need:
                            self.cond.wait(0.1)
                        if len(self.q) < need:
                            if not self.q:
                                waiting = True  # ran dry: gather a little again before playing on
                            if time.time() - last > IDLE_CLOSE:
                                break
                            continue
                        waiting = False
                        chunk = b"".join(self.q)
                        self.q.clear()
                    last = time.time()
                    pl.play(from_pcm(chunk))
        except _NoCable:
            self.failed = time.time()
            self.audio.sink({"t": "audio_err", "sink": "mic", "why": "nocable",
                             "error": "No virtual microphone here. Install %s, then try again."
                                      % ("BlackHole (existential.audio/blackhole)" if sys.platform == "darwin"
                                         else "VB-CABLE (vb-audio.com/Cable)")})
        except Exception as e:
            self.failed = time.time()
            self.audio.sink({"t": "audio_err", "sink": self.sink, "why": "failed", "error": "Couldn't play sound: %s" % e})
        finally:
            self.alive = False


class _NoCable(Exception):
    pass


def _read_exact(f, n):
    buf = b""
    while len(buf) < n:
        part = f.read(n - len(buf))
        if not part:
            return None
        buf += part
    return buf


def _stop_proc(proc):
    try:
        proc.stdin.close()
    except Exception:
        pass
    try:
        proc.terminate()
        proc.wait(2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
