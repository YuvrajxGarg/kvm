"""Kvm's window: an HTML/CSS interface (kvm/ui) in a native window via pywebview.

On a Mac (and on Windows without the setup's service) the window runs the agent itself. On
Windows with the Kvm service installed, the service runs it and the window is only a view of it
(control.RemoteAgent), so closing the window changes nothing.
"""

import json
import os
import subprocess
import sys
import threading
import time

import webview

from . import __version__
from .settings import Settings
from .updater import Updater, setup_mode

UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    UI_DIR = os.path.join(sys._MEIPASS, "kvm", "ui")

BG = "#0b0b0c"
SITE = "https://kvm.pxlvzn.in"
LAUNCH_AGENT = os.path.expanduser("~/Library/LaunchAgents/in.pxlvzn.kvm.plist")


def make_agent():
    """(agent, mode): 'service' on Windows with the service, otherwise 'app'."""
    if os.name == "nt":
        from .winservice import service_installed
        if service_installed():
            from .control import RemoteAgent
            for _ in range(40):  # the service may still be starting (just installed, just booted)
                try:
                    ra = RemoteAgent()
                    if ra.alive():
                        return ra, "service"
                except OSError:
                    pass
                time.sleep(0.25)
            return None, "service-down"
    from .agent import Agent
    from .platform import native_backend
    return Agent(native_backend()).start(), "app"


class Api(object):
    def __init__(self):
        self._window = None
        self._settings = Settings()
        self._updater = Updater(self._settings, lambda st: self._emit("update", st))
        self._agent = None
        self._mode = "starting"
        self._error = None
        self._viewers = {}   # pid -> viewer window

    def _emit(self, event, payload):
        if self._window:
            try:
                self._window.evaluate_js("window.App && App.on(%s, %s)" % (json.dumps(event), json.dumps(payload, default=str)))
            except Exception:
                pass

    def _start_agent(self):
        try:
            self._agent, self._mode = make_agent()
        except Exception as e:
            self._mode = "failed"
            self._error = str(e)

    def _call(self, name, *args):
        if not self._agent:
            return None
        try:
            return getattr(self._agent, name)(*args)
        except Exception as e:
            self._emit("toast", {"text": str(e), "err": True})
            return None

    # ---- called from JS ------------------------------------------------------
    def info(self):
        return {"version": __version__, "platform": sys.platform, "settings": self._settings.public(),
                "update": self._updater.state(), "site": SITE, "login": self.login_state()}

    def state(self):
        st = None
        if self._agent:
            try:
                st = self._agent.status()
            except Exception as e:
                st = None
                self._error = str(e)
        return {"mode": self._mode, "error": self._error, "agent": st}

    # sharing (the agent)
    def rename(self, name):
        return self._call("rename", name)

    def set_share(self, key, value):
        return self._call("set_setting", key, value)

    def set_side(self, pid, side):
        return self._call("set_side", pid, side)

    def forget(self, pid):
        return self._call("forget", pid)

    def add_address(self, text):
        ref = self._call("add_address", text)
        return self._call("pair", ref) if ref else False

    def pair(self, ref):
        return self._call("pair", ref)

    def pair_code(self, code):
        return self._call("pair_code", code)

    def pair_cancel(self):
        return self._call("pair_cancel")

    def remote_action(self, pid, what):
        return self._call("action", pid, what)

    def go_home(self):
        return self._call("go_home")

    def set_locked(self, on):
        return self._call("set_locked", bool(on))

    def send_files(self, pid, folder=False):
        if folder:
            res = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        else:
            res = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True)
        paths = list(res) if isinstance(res, (list, tuple)) else ([res] if res else [])
        return self._call("send_files", pid, paths) if paths else None

    def send_paths(self, pid, paths):
        return self._call("send_files", pid, [p for p in paths or [] if p])

    # the other computer's screen
    def open_viewer(self, pid):
        w = self._viewers.get(pid)
        if w:
            try:
                w.restore()
                w.show()
                return {"ok": True}
            except Exception:
                self._viewers.pop(pid, None)
        if not self._agent:
            return {"error": "Kvm is still starting."}
        try:
            self._agent.view_start(pid)
        except Exception as e:
            return {"error": str(e)}
        name = "the other computer"
        try:
            for p in (self._agent.status() or {}).get("peers", []):
                if p.get("id") == pid:
                    name = p.get("name") or name
        except Exception:
            pass
        win = webview.create_window("%s · Kvm" % name, url=os.path.join(UI_DIR, "viewer.html") + "?pid=" + pid,
                                    js_api=self, width=1280, height=800, min_size=(480, 320), background_color="#000000")
        self._viewers[pid] = win

        def closed():
            self._viewers.pop(pid, None)
            self._call("view_stop", pid)
        win.events.closed += closed
        return {"ok": True}

    def viewer_state(self, pid):
        try:
            st = self._agent.status() if self._agent else None
        except Exception:
            st = None
        v = ((st or {}).get("views") or {}).get(pid)
        name = next((p.get("name") for p in (st or {}).get("peers", []) if p.get("id") == pid), None)
        plat = next((p.get("platform") for p in (st or {}).get("peers", []) if p.get("id") == pid), None)
        return {"view": v, "name": name, "platform": plat, "me": sys.platform}

    def view_input(self, pid, ev):
        if not self._agent:
            return False
        try:
            return self._agent.view_input(pid, ev)
        except Exception:
            return False

    def view_again(self, pid):
        return self._call("view_start", pid)

    def stop_sharing(self):
        return self._call("stop_sharing")

    def listen(self, pid, on):
        """Hear that computer's sound here (on=True), or stop."""
        return self._call("listen_start" if on else "listen_stop", pid)

    def stop_sound(self):
        return self._call("stop_sound")

    def mic(self, pid, on):
        """Use this computer's microphone on that one (on=True), or stop."""
        return self._call("mic_start" if on else "mic_stop", pid)

    def cancel_transfer(self, tid):
        return self._call("cancel_transfer", tid)

    def clear_transfers(self):
        return self._call("clear_transfers")

    def pick_receive_dir(self):
        res = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        p = res[0] if isinstance(res, (list, tuple)) and res else res
        if p:
            return self._call("set_setting", "receive_dir", p)
        return None

    def reveal(self, path):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path] if os.path.isfile(path) else ["open", path])
            elif os.name == "nt":
                if os.path.isfile(path):
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
                else:
                    os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            pass

    # the app
    def set_setting(self, key, value):
        if key in ("auto_check", "auto_install", "welcomed"):
            self._settings.set(key, value)
            if key == "auto_install" and value and self._updater.phase == "available" and not setup_mode():
                threading.Thread(target=self._updater.stage_newest, daemon=True).start()
        return self._settings.public()

    def check_updates(self):
        return self._updater.check(manual=True)

    def download_update(self):
        threading.Thread(target=self._updater.stage_newest, daemon=True).start()

    def install_update(self):
        def go():
            if self._updater.install() == "open_page":
                self.open_url(self._updater.state()["page"])
        threading.Thread(target=go, daemon=True).start()

    def open_url(self, url):
        if not url.startswith(("https://github.com/", SITE, "x-apple.systempreferences:")):
            return
        if url.startswith("x-apple.systempreferences:"):
            subprocess.Popen(["open", url])
            return
        import webbrowser
        webbrowser.open(url)

    def request_permissions(self):
        if sys.platform != "darwin":
            return
        from .platform.mac import request_permissions
        request_permissions()

    def open_privacy(self, which):
        pane = {"accessibility": "Privacy_Accessibility", "input_monitoring": "Privacy_ListenEvent"}.get(which, "Privacy")
        self.open_url("x-apple.systempreferences:com.apple.preference.security?" + pane)

    def login_state(self):
        if sys.platform == "darwin":
            return {"supported": True, "on": os.path.exists(LAUNCH_AGENT)}
        if os.name == "nt" and self._mode != "service":
            return {"supported": True, "on": _win_run_key() is not None}
        return {"supported": False, "on": False}

    def set_login(self, on):
        exe = sys.executable if getattr(sys, "frozen", False) else None
        if not exe:
            return self.login_state()
        try:
            if sys.platform == "darwin":
                if on:
                    import plistlib
                    os.makedirs(os.path.dirname(LAUNCH_AGENT), exist_ok=True)
                    with open(LAUNCH_AGENT, "wb") as f:
                        plistlib.dump({"Label": "in.pxlvzn.kvm", "ProgramArguments": [exe, "--background"],
                                       "RunAtLoad": True, "ProcessType": "Interactive"}, f)
                elif os.path.exists(LAUNCH_AGENT):
                    os.remove(LAUNCH_AGENT)
            elif os.name == "nt":
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                    winreg.KEY_SET_VALUE) as k:
                    if on:
                        winreg.SetValueEx(k, "Kvm", 0, winreg.REG_SZ, '"%s" --background' % exe)
                    else:
                        try:
                            winreg.DeleteValue(k, "Kvm")
                        except OSError:
                            pass
        except Exception as e:
            self._emit("toast", {"text": "Couldn't change that: %s" % e, "err": True})
        return self.login_state()

    def quit(self):
        threading.Thread(target=lambda: (time.sleep(0.1), self._window.destroy()), daemon=True).start()


def _win_run_key():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
            return winreg.QueryValueEx(k, "Kvm")[0]
    except OSError:
        return None


# ---- native window chrome -------------------------------------------------

def _style_mac(window):
    try:
        import AppKit
        from PyObjCTools import AppHelper

        def apply():
            w = window.native
            w.setStyleMask_(w.styleMask() | AppKit.NSWindowStyleMaskFullSizeContentView)
            w.setTitlebarAppearsTransparent_(True)
            w.setTitleVisibility_(AppKit.NSWindowTitleHidden)
            w.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameDarkAqua))
            w.setBackgroundColor_(AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(0.043, 0.043, 0.047, 1.0))
            w.setMovableByWindowBackground_(False)
            if hasattr(w, "setToolbarStyle_"):
                w.setToolbarStyle_(AppKit.NSWindowToolbarStyleUnifiedCompact)

        AppHelper.callAfter(apply)
    except Exception:
        pass


def _style_windows(window):
    try:
        import ctypes

        hwnd = window.native.Handle.ToInt32()
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        for attr in (20, 19):
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), 4) == 0:
                break
        caption = ctypes.c_int(0x000C0B0B)
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), 4)
    except Exception:
        pass


def _on_drop(api):
    """Files dropped on the window: the page says which computer they were dropped on."""
    def handler(e):
        try:
            files = e.get("dataTransfer", {}).get("files", [])
            paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
            if paths:
                api._emit("dropped", {"paths": paths})
        except Exception:
            pass
    return handler


def main(background=False):
    api = Api()
    threading.Thread(target=api._start_agent, daemon=True).start()
    webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True
    window = webview.create_window(
        "Kvm", url=os.path.join(UI_DIR, "index.html"), js_api=api,
        width=980, height=760, min_size=(760, 600), background_color=BG, easy_drag=False, minimized=background,
    )
    api._window = window

    def quit_for_install():
        try:
            window.destroy()
        finally:
            t = threading.Timer(3.0, lambda: os._exit(0))
            t.daemon = True
            t.start()

    api._updater.on_quit_for_install = quit_for_install
    window.events.closing += lambda: api._updater.install_on_quit()

    def loaded():
        api._updater.start()
        try:
            from webview.dom import DOMEventHandler
            window.dom.document.events.drop += DOMEventHandler(_on_drop(api), True, True)
        except Exception:
            pass

    window.events.loaded += loaded
    if sys.platform == "darwin":
        window.events.before_show += lambda: _style_mac(window)
    elif os.name == "nt":
        window.events.shown += lambda: _style_windows(window)
    webview.start(debug=bool(os.environ.get("KVM_DEBUG")))
    if api._agent is not None and api._mode == "app":
        try:
            api._agent.stop()
        except Exception:
            pass
    if os.name == "nt":
        os._exit(0)


if __name__ == "__main__":
    main()
