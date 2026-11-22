"""The "Kvm Camera" webcam on Windows 11: shows the other computer's camera to every app here.

KvmCam.dll (native/win/kvmcam.cpp) is the camera's media source, loaded by Windows' Frame Server.
This side creates the camera (KvmCamStart) and hands it each picture as 1280x720 BGRA (KvmCamWrite).
"""

import ctypes
import io
import os
import sys
import threading

W, H = 1280, 720


def dll_path():
    name = "KvmCam.dll"
    here = os.path.dirname(os.path.abspath(__file__))
    for c in ([os.path.join(sys._MEIPASS, name)] if getattr(sys, "_MEIPASS", None) else []) + \
            [os.path.join(os.path.dirname(sys.executable), name), os.path.join(here, "..", "native-build", name)]:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None


def available():
    """Windows 11 (MFCreateVirtualCamera) with KvmCam.dll next to Kvm."""
    if os.name != "nt":
        return False
    try:
        if sys.getwindowsversion().build < 22000:
            return False
    except Exception:
        return False
    return dll_path() is not None


def letterbox(jpeg):
    """A JPEG -> 1280x720 BGRA bytes, scaled to fit with black bars."""
    from PIL import Image
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    k = min(W / img.size[0], H / img.size[1])
    size = (max(1, int(img.size[0] * k)), max(1, int(img.size[1] * k)))
    if size != img.size:
        img = img.resize(size, Image.BILINEAR)
    out = Image.new("RGB", (W, H), (0, 0, 0))
    out.paste(img, ((W - size[0]) // 2, (H - size[1]) // 2))
    return out.tobytes("raw", "BGRX")


class VirtualCamera(object):
    def __init__(self, sink, all_users=False):
        self.sink = sink
        self.all_users = all_users
        self._latest = None
        self._event = threading.Event()
        self._on = False
        self._thread = None

    def frame(self, jpeg):
        self._latest = jpeg
        if not self._on:
            self._on = True
            self._thread = threading.Thread(target=self._run, name="kvm-vcam", daemon=True)
            self._thread.start()
        self._event.set()

    def stop(self):
        self._on = False
        self._event.set()

    def _run(self):
        # One thread owns the camera: it's created here, fed here, and removed here.
        try:
            dll = ctypes.WinDLL(dll_path())
            dll.KvmCamStart.restype = ctypes.c_long
            dll.KvmCamWrite.restype = ctypes.c_long
            dll.KvmCamWrite.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
            hr = dll.KvmCamStart(1 if self.all_users else 0) & 0xFFFFFFFF
            if hr >= 0x80000000:
                self.sink({"t": "log", "text": "Kvm Camera couldn't start (0x%08X)" % hr})
                self.sink({"t": "vcam", "on": False, "error": "The Kvm Camera webcam couldn't start (0x%08X)." % hr})
                self._on = False
                return
            self.sink({"t": "vcam", "on": True})
            while self._on:
                self._event.wait(5)
                self._event.clear()
                jpeg, self._latest = self._latest, None
                if jpeg and self._on:
                    try:
                        dll.KvmCamWrite(letterbox(jpeg), W, H)
                    except Exception as e:
                        self.sink({"t": "log", "text": "Kvm Camera picture: %r" % e})
            dll.KvmCamStop()
            self.sink({"t": "vcam", "on": False})
        except Exception as e:
            self._on = False
            self.sink({"t": "vcam", "on": False, "error": "The Kvm Camera webcam couldn't start (%s)." % e})
