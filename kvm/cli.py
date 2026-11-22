"""Command line:  Kvm status | run | selftest FILE | version"""

import argparse
import json
import sys
import time

from . import __version__


def _selftest(out):
    """For CI: which parts this build can load, and a pairing + typing round trip between two
    agents on this machine (fake input, real network and crypto)."""
    import importlib
    import os
    import shutil
    import tempfile

    res = {"version": __version__}
    mods = ["webview", "nacl", "spake2", "zeroconf", "certifi", "PIL.Image", "PIL.ImageDraw", "PIL.JpegImagePlugin",
            "numpy", "kvm.audio"]
    if sys.platform == "darwin":
        mods += ["Quartz", "AppKit", "ApplicationServices"]
    if os.name == "nt":
        mods += ["win32service", "win32serviceutil", "servicemanager", "win32ts", "win32profile", "win32process"]
    for mod in mods:
        try:
            importlib.import_module(mod)
            res[mod] = True
        except Exception as e:
            res[mod] = False
            res[mod + "_error"] = str(e)
    try:
        importlib.import_module("kvm.platform.mac" if sys.platform == "darwin" else
                                "kvm.platform.win" if os.name == "nt" else "kvm.platform.base")
        res["backend"] = True
    except Exception as e:
        res["backend"] = False
        res["backend_error"] = repr(e)
    # A real picture of this screen (not required: a CI runner may have no screen to take).
    try:
        from .platform import native_backend
        be = native_backend()
        be._capture_thread_init()
        img = be._grab_screen()
        res["screen_grab"] = "%dx%d" % img.size if img is not None else "none"
    except Exception as e:
        res["screen_grab"] = "error: %r" % e
    # Sound devices (informational: a CI runner may have none). The Mac's sound tool must be bundled.
    try:
        from . import audio
        sc = audio._sc()
        res["sound"] = "speakers: %d, mics: %d" % (len(sc.all_speakers()), len(sc.all_microphones()))
    except Exception as e:
        res["sound"] = "error: %r" % e
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        from .audio import native_tool, tap_path
        res["audiotap"] = bool(tap_path())
        res["vdisplay_tool"] = bool(native_tool("kvm-vdisplay"))
        res["camera_tool"] = bool(native_tool("kvm-camera"))
    if os.name == "nt" and getattr(sys, "frozen", False):
        import ctypes

        from .vcam import dll_path
        try:  # it must load (mfsensorgroup is delay-loaded, so it does on Windows 10 too) and export its calls
            d = ctypes.WinDLL(dll_path())
            res["kvmcam_dll"] = all(hasattr(d, f) for f in ("KvmCamStart", "KvmCamStop", "KvmCamWrite", "DllGetClassObject"))
        except Exception as e:
            res["kvmcam_dll"] = False
            res["kvmcam_dll_error"] = repr(e)
    tmp = tempfile.mkdtemp()
    try:
        res["loopback"] = _loopback(tmp)
    except Exception as e:
        res["loopback"] = False
        res["loopback_error"] = repr(e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f)
    return 0


def _loopback(tmp):
    import os

    from . import keys
    from .agent import Agent
    from .platform.base import FakeBackend
    from .store import Store

    def wait(cond, t=10):
        end = time.time() + t
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.05)
        return False

    a_be, b_be = FakeBackend(), FakeBackend()
    a = Agent(a_be, Store(os.path.join(tmp, "a")), port=0, discover=False).start()
    b = Agent(b_be, Store(os.path.join(tmp, "b")), port=0, discover=False).start()
    try:
        a.pair(a.add_address("127.0.0.1:%d" % b.port))
        assert wait(lambda: (a.status()["pairing"] or {}).get("phase") == "code")
        a.pair_code(b.status()["pairing"]["code"])
        assert wait(lambda: any(p["connected"] for p in a.status()["peers"]))
        a.set_side(b._store.id, "right")
        assert wait(lambda: a_be.watch_sides == ["right"])
        a_be.on_local_move(1919, 500, 4, 0)
        assert wait(lambda: b.status()["mode"] == "driven")
        a_be.on_local_key(keys.BY_NAME["k"], True)
        assert wait(lambda: ("key", keys.BY_NAME["k"], True) in b_be.posted)
        a.view_start(b._store.id)  # the screen viewer: pictures arrive, JPEG-encoded by this build's Pillow
        assert wait(lambda: a.status()["views"][b._store.id]["seq"] > 0)
        return True
    finally:
        a.stop()
        b.stop()


def _run():
    """No window: share this computer's keyboard and mouse with paired computers."""
    from .agent import Agent
    from .platform import native_backend

    agent = Agent(native_backend()).start()
    print("Kvm %s running as %s on port %d. Ctrl+C to stop." % (__version__, agent.status()["me"]["name"], agent.port))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop()
    return 0


def _status(out=None):
    import os
    text = "Kvm %s. Open the app to see paired computers." % __version__
    code = 0
    if os.name == "nt":
        from .winservice import service_installed
        if service_installed():
            from .control import RemoteAgent
            try:
                text = json.dumps(RemoteAgent().status(), indent=2, default=str)
            except Exception as e:
                text, code = "The Kvm service didn't answer: %s" % e, 1
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return code


def main(argv=None):
    p = argparse.ArgumentParser(prog="kvm", description="One keyboard and mouse for your computers.")
    p.add_argument("--version", action="version", version="Kvm " + __version__)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("run", help="share without opening the window")
    stp = sub.add_parser("status", help="show what the Kvm service sees (Windows)")
    stp.add_argument("--out", metavar="FILE", help="also write it to FILE")
    sub.add_parser("version")
    st = sub.add_parser("selftest", help=argparse.SUPPRESS)
    st.add_argument("out")
    args = p.parse_args(argv)
    if args.cmd in (None, "version"):
        print("Kvm " + __version__)
        return 0
    if args.cmd == "selftest":
        return _selftest(args.out)
    if args.cmd == "run":
        return _run()
    if args.cmd == "status":
        return _status(args.out)
    return 0
