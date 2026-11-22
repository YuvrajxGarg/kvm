"""Where Kvm keeps this computer's identity, its paired computers and its sharing settings.

The app window keeps its own window/update settings (settings.py). This store belongs to the
part that talks to other computers: the app itself on a Mac, and the Kvm service on Windows
when it's installed (then the folder is %ProgramData%\\PXLVZN\\Kvm, readable only by the system
and administrators, because it holds the pair keys).
"""

import json
import os
import platform
import socket
import sys
import threading

from . import crypto

DEFAULTS = {
    "clipboard": True,            # share the clipboard with paired computers
    "clipboard_images": True,     # ... pictures too
    "swap_cmd_ctrl": True,        # Mac Command works as Ctrl on a PC (and the other way round)
    "cross_modifier": "",         # "", "ctrl", "alt", "shift", "meta": hold it to cross an edge
    "return_hotkey": "ctrl+alt+esc",  # brings the pointer home from anywhere
    "lock_key": "scrolllock",     # toggles cursor lock (F14 on a Mac keyboard)
    "speed": 1.0,                 # pointer speed on the other computer
    "receive_dir": None,          # None: Downloads/Kvm
    "files": True,                # accept files from paired computers
    "remote_actions": True,       # paired computers may Ring, Lock and Sleep this one
    "screen_share": True,         # paired computers may see this screen
    "screen_control": True,       # ... and use it with their mouse and keyboard from the viewer
    "sound_share": True,          # paired computers may hear this computer's sound
    "mic_accept": True,           # paired computers may send their microphone to this one's virtual mic
    "display_accept": True,       # paired computers may use this screen as an extra display
}
SETTING_TYPES = {"clipboard": bool, "clipboard_images": bool, "swap_cmd_ctrl": bool, "cross_modifier": str,
                 "return_hotkey": str, "lock_key": str, "speed": float, "receive_dir": str, "files": bool,
                 "remote_actions": bool, "screen_share": bool, "screen_control": bool,
                 "sound_share": bool, "mic_accept": bool, "display_accept": bool}


def user_data_dir():
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "Kvm")


def service_data_dir():
    return os.path.join(os.environ.get("ProgramData") or "C:\\ProgramData", "PXLVZN", "Kvm")


def this_platform():
    if sys.platform == "darwin":
        return "mac"
    if os.name == "nt":
        return "windows"
    return "linux"


def default_name():
    if sys.platform == "darwin":
        try:
            import subprocess

            n = subprocess.run(["scutil", "--get", "ComputerName"], capture_output=True, text=True, timeout=3).stdout.strip()
            if n:
                return n
        except Exception:
            pass
    n = (os.environ.get("COMPUTERNAME") or platform.node() or socket.gethostname() or "Computer").split(".")[0]
    return n[:1].upper() + n[1:].lower() if n.isupper() else n


class Store(object):
    def __init__(self, folder=None):
        self.dir = folder or os.environ.get("KVM_HOME") or user_data_dir()
        os.makedirs(self.dir, exist_ok=True)
        self.path = os.path.join(self.dir, "kvm.json")
        self.lock = threading.RLock()
        self.data = {"id": None, "name": None, "pairs": {}, "settings": {}}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass
        if not self.data.get("id"):
            self.data["id"] = crypto.random_id(8)
            self.save()

    @property
    def id(self):
        return self.data["id"]

    @property
    def name(self):
        return self.data.get("name") or default_name()

    def rename(self, name):
        with self.lock:
            self.data["name"] = (name or "").strip()[:40] or None
            self.save()

    def save(self):
        with self.lock:
            tmp = self.path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2)
                os.replace(tmp, self.path)
            except OSError:
                pass

    # ---- settings ----------------------------------------------------------
    def get(self, key):
        return self.data["settings"].get(key, DEFAULTS.get(key))

    def set(self, key, value):
        if key not in SETTING_TYPES:
            raise KeyError(key)
        if value is not None:
            value = SETTING_TYPES[key](value)
        if key == "speed":
            value = min(4.0, max(0.25, value))
        with self.lock:
            self.data["settings"][key] = value
            self.save()

    def settings(self):
        return {k: self.get(k) for k in DEFAULTS}

    # ---- pairs -------------------------------------------------------------
    def pairs(self):
        with self.lock:
            return {k: dict(v) for k, v in self.data["pairs"].items()}

    def pair(self, pid):
        with self.lock:
            p = self.data["pairs"].get(pid)
            return dict(p) if p else None

    def pair_key(self, pid):
        p = self.pair(pid)
        return bytes.fromhex(p["key"]) if p and p.get("key") else None

    def add_pair(self, pid, name, platform_, key):
        with self.lock:
            old = self.data["pairs"].get(pid) or {}
            self.data["pairs"][pid] = dict(old, name=name, platform=platform_, key=key.hex())
            self.save()

    def update_pair(self, pid, **kw):
        with self.lock:
            p = self.data["pairs"].get(pid)
            if not p:
                return
            changed = False
            for k, v in kw.items():
                if p.get(k) != v:
                    p[k] = v
                    changed = True
            if changed:
                self.save()

    def forget(self, pid):
        with self.lock:
            if self.data["pairs"].pop(pid, None) is not None:
                self.save()

    def receive_dir(self, home=None):
        d = self.get("receive_dir")
        if d:
            return d
        return os.path.join(home or os.path.expanduser("~"), "Downloads", "Kvm")
