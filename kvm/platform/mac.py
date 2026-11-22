"""macOS input: one Quartz event tap for the mouse, trackpad and keyboard together, and CGEvents
to put input from another computer on this one.

Needs Accessibility (to post events) and Input Monitoring (to read them), asked for once.

Why one tap for everything: the pointer and the keyboard must always be on the same computer. If
macOS turns the tap off (it does when a callback is slow), both come home together, and a watchdog
turns it back on and re-hides the pointer within half a second. Moves are read from the event's
delta fields and, when a device reports none (some mice, tablets and remote tools post absolute
positions), from how far the pointer would have gone, so every pointing device crosses the same way.
"""

import ctypes
import ctypes.util
import io
import subprocess
import threading
import time

import Quartz
from AppKit import NSBitmapImageRep, NSEvent, NSPasteboard, NSPasteboardTypePNG, NSPasteboardTypeString, NSPasteboardTypeTIFF
from Foundation import NSURL, NSData

from .. import keys
from .base import Backend

MARK = 0x4B564D21  # "KVM!" in kCGEventSourceUserData: our own injected events
F_USERDATA = 42
F_CLICK_STATE = 1
F_DELTA_X, F_DELTA_Y = 4, 5
F_BUTTON = 3
F_KEYCODE = 9
F_AUTOREPEAT = 8
F_SCROLL_Y, F_SCROLL_X = 11, 12
F_SCROLL_PT_Y, F_SCROLL_PT_X = 96, 97
F_SCROLL_CONT = 88
SYSTEM_DEFINED = 14
# Trackpad touches: NSEventTypeGesture, BeginGesture, EndGesture. A mouse never sends these, so a
# move right after one came from the trackpad.
TOUCH_TYPES = (29, 19, 20)
TOUCH_RECENT = 0.25
TAP_DISABLED = (0xFFFFFFFE, 0xFFFFFFFF)

# Media keys (NX_KEYTYPE_*) <-> HID
_NX_TO_HID = {0: keys.BY_NAME["volume_up"], 1: keys.BY_NAME["volume_down"], 7: keys.BY_NAME["mute"],
              16: keys.BY_NAME["media_play"], 17: keys.BY_NAME["media_next"], 18: keys.BY_NAME["media_prev"],
              19: keys.BY_NAME["media_next"], 20: keys.BY_NAME["media_prev"]}
_HID_TO_NX = {keys.BY_NAME["volume_up"]: 0, keys.BY_NAME["volume_down"]: 1, keys.BY_NAME["mute"]: 7,
              keys.BY_NAME["media_play"]: 16, keys.BY_NAME["media_next"]: 17, keys.BY_NAME["media_prev"]: 18}

_MAC_BUTTON = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}           # CG button number -> ours
_BUTTON_MAC = {v: k for k, v in _MAC_BUTTON.items()}
_DOWN = {1: Quartz.kCGEventLeftMouseDown, 2: Quartz.kCGEventRightMouseDown}
_UP = {1: Quartz.kCGEventLeftMouseUp, 2: Quartz.kCGEventRightMouseUp}

# Generic modifier flags for injected keys.
_FLAG = {keys.BY_NAME["lshift"]: 0x20000 | 0x02, keys.BY_NAME["rshift"]: 0x20000 | 0x04,
         keys.BY_NAME["lctrl"]: 0x40000 | 0x01, keys.BY_NAME["rctrl"]: 0x40000 | 0x2000,
         keys.BY_NAME["lalt"]: 0x80000 | 0x20, keys.BY_NAME["ralt"]: 0x80000 | 0x40,
         keys.BY_NAME["lmeta"]: 0x100000 | 0x08, keys.BY_NAME["rmeta"]: 0x100000 | 0x10}

WHEEL_PX = 40.0  # pixels in one wheel notch, both ways


def _cg():
    return ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")


class MacBackend(Backend):
    name = "mac"
    shortcut_mod = "lmeta"
    can_capture = True
    can_inject = True
    can_vdisplay = True  # CGVirtualDisplay, through kvm-vdisplay
    can_camera = True    # AVFoundation, through kvm-camera

    def __init__(self):
        self._tap = None
        self._src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)
        try:
            Quartz.CGEventSourceSetLocalEventsSuppressionInterval(self._src, 0.0)
        except Exception:
            pass
        self._park = None
        self._hidden = False
        self._last_loc = None
        self._clicks = (0, 0.0, None, 0)  # button, time, (x, y), count
        self._wheel_acc = [0.0, 0.0]
        self._pb = NSPasteboard.generalPasteboard()
        self._pb_count = None
        self._pb_cache = None
        self._tap_error = None
        self._touch_ts = 0.0
        Backend.__init__(self)

    # ---- lifecycle ---------------------------------------------------------
    def start(self, sink):
        Backend.start(self, sink)
        threading.Thread(target=self._tap_thread, name="kvm-tap", daemon=True).start()
        threading.Thread(target=self._watchdog, name="kvm-watchdog", daemon=True).start()

    def _tap_thread(self):
        mask = 0
        for t in (Quartz.kCGEventMouseMoved, Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp,
                  Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGEventOtherMouseDown,
                  Quartz.kCGEventOtherMouseUp, Quartz.kCGEventLeftMouseDragged, Quartz.kCGEventRightMouseDragged,
                  Quartz.kCGEventOtherMouseDragged, Quartz.kCGEventScrollWheel, Quartz.kCGEventKeyDown,
                  Quartz.kCGEventKeyUp, Quartz.kCGEventFlagsChanged, SYSTEM_DEFINED) + TOUCH_TYPES:
            mask |= 1 << t
        while self._tap is None:
            tap = Quartz.CGEventTapCreate(Quartz.kCGHIDEventTap, Quartz.kCGHeadInsertEventTap,
                                          Quartz.kCGEventTapOptionDefault, mask, self._callback, None)
            if tap is None:
                self._tap_error = "Kvm needs Input Monitoring and Accessibility"
                time.sleep(2.0)  # asked for in the window; keep trying until it's allowed
                continue
            self._tap = tap
            self._tap_error = None
        src = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), src, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)
        Quartz.CFRunLoopRun()

    def _watchdog(self):
        while True:
            time.sleep(0.5)
            try:
                if self._tap is not None and not Quartz.CGEventTapIsEnabled(self._tap):
                    Quartz.CGEventTapEnable(self._tap, True)
                if self.grabbed:
                    Quartz.CGAssociateMouseAndMouseCursorPosition(False)
                    if not self._hidden:
                        self._hide(True)
            except Exception:
                pass

    def _from_trackpad(self):
        return time.time() - self._touch_ts < TOUCH_RECENT

    # ---- the tap ---------------------------------------------------------------
    def _callback(self, proxy, etype, event, refcon):
        try:
            if etype in TAP_DISABLED:
                Quartz.CGEventTapEnable(self._tap, True)
                return event
            if etype in TOUCH_TYPES:
                self._touch_ts = time.time()
                return event
            if Quartz.CGEventGetIntegerValueField(event, F_USERDATA) == MARK:
                return event
            if etype in (Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp):
                kc = Quartz.CGEventGetIntegerValueField(event, F_KEYCODE)
                swallow = self.on_local_key(keys.from_mac(kc), etype == Quartz.kCGEventKeyDown)
                return None if swallow else event
            if etype == Quartz.kCGEventFlagsChanged:
                return None if self._on_flags(event) else event
            if etype == SYSTEM_DEFINED:
                return None if self._on_system(event) else event
            if etype == Quartz.kCGEventScrollWheel:
                if not self.grabbed:
                    return event
                if Quartz.CGEventGetIntegerValueField(event, F_SCROLL_CONT):
                    dy = Quartz.CGEventGetDoubleValueField(event, F_SCROLL_PT_Y) / WHEEL_PX
                    dx = -Quartz.CGEventGetDoubleValueField(event, F_SCROLL_PT_X) / WHEEL_PX
                else:
                    dy = float(Quartz.CGEventGetIntegerValueField(event, F_SCROLL_Y))
                    dx = -float(Quartz.CGEventGetIntegerValueField(event, F_SCROLL_X))
                return None if self.on_local_wheel(dx, dy) else event
            if etype in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventRightMouseDown, Quartz.kCGEventOtherMouseDown,
                         Quartz.kCGEventLeftMouseUp, Quartz.kCGEventRightMouseUp, Quartz.kCGEventOtherMouseUp):
                b = _MAC_BUTTON.get(Quartz.CGEventGetIntegerValueField(event, F_BUTTON))
                down = etype in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventRightMouseDown, Quartz.kCGEventOtherMouseDown)
                if b is None:
                    return None if self.grabbed else event
                return None if self.on_local_button(b, down) else event
            # moves and drags
            loc = Quartz.CGEventGetLocation(event)
            dx = Quartz.CGEventGetDoubleValueField(event, F_DELTA_X)
            dy = Quartz.CGEventGetDoubleValueField(event, F_DELTA_Y)
            if self.grabbed:
                if not dx and not dy and self._park is not None:
                    # A device that reports where the pointer is rather than how far it moved.
                    dx, dy = loc.x - self._park[0], loc.y - self._park[1]
                    if dx or dy:
                        Quartz.CGWarpMouseCursorPosition(self._park)
                self.on_grabbed_move(int(round(dx)), int(round(dy)))
                return None
            if not dx and not dy and self._last_loc is not None:
                dx, dy = loc.x - self._last_loc[0], loc.y - self._last_loc[1]
            self._last_loc = (loc.x, loc.y)
            return None if self.on_local_move(loc.x, loc.y, dx, dy) else event
        except Exception as e:
            self.sink({"t": "log", "text": "tap: %r" % e})
            return event

    def _on_flags(self, event):
        kc = Quartz.CGEventGetIntegerValueField(event, F_KEYCODE)
        flags = Quartz.CGEventGetFlags(event)
        if kc == 0x39:  # Caps Lock: one event per press; the other computer wants a tap
            hid = keys.BY_NAME["capslock"]
            a = self.on_local_key(hid, True)
            self.on_local_key(hid, False)
            return a
        bit = keys.MAC_MOD_BITS.get(kc)
        if bit is None:
            return self.grabbed  # fn and friends stay here
        return self.on_local_key(keys.from_mac(kc), bool(flags & bit))

    def _on_system(self, event):
        try:
            ns = NSEvent.eventWithCGEvent_(event)
            if ns is None or ns.subtype() != 8:
                return False
            data1 = ns.data1()
        except Exception:
            return False
        nx = (data1 & 0xFFFF0000) >> 16
        state = (data1 & 0xFF00) >> 8
        hid = _NX_TO_HID.get(nx)
        if hid is None or not self.grabbed:
            return False
        if data1 & 0x1:  # auto-repeat
            down = True
        else:
            down = state == 0xA
        self.sink({"t": "key", "k": hid, "d": down})
        return True

    # ---- grab ------------------------------------------------------------------
    def _set_grab(self, on):
        if on:
            c = self._cursor()
            self._park = c
            Quartz.CGAssociateMouseAndMouseCursorPosition(False)
            self._hide(True)
        else:
            Quartz.CGAssociateMouseAndMouseCursorPosition(True)
            self._hide(False)
            self._park = None
            self._last_loc = None

    def _hide(self, hide):
        if hide == self._hidden:
            return
        try:
            if hide:
                _background_cursor()
                Quartz.CGDisplayHideCursor(Quartz.CGMainDisplayID())
            else:
                Quartz.CGDisplayShowCursor(Quartz.CGMainDisplayID())
            self._hidden = hide
        except Exception:
            pass

    # ---- geometry ----------------------------------------------------------------
    def _screens(self):
        err, ids, n = Quartz.CGGetActiveDisplayList(16, None, None)
        out = []
        for d in (ids or [])[:n]:
            r = Quartz.CGDisplayBounds(d)
            out.append((r.origin.x, r.origin.y, r.size.width, r.size.height))
        return out

    def _cursor(self):
        e = Quartz.CGEventCreate(None)
        p = Quartz.CGEventGetLocation(e)
        return (p.x, p.y)

    def _warp(self, x, y):
        Quartz.CGWarpMouseCursorPosition((x, y))
        Quartz.CGAssociateMouseAndMouseCursorPosition(True)
        self._last_loc = (x, y)

    # ---- injection -----------------------------------------------------------------
    def _post(self, e):
        Quartz.CGEventSetIntegerValueField(e, F_USERDATA, MARK)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)

    def _post_move(self, x, y, buttons):
        prev = self._last_loc or (x, y)
        if 1 in buttons:
            t, b = Quartz.kCGEventLeftMouseDragged, Quartz.kCGMouseButtonLeft
        elif 2 in buttons:
            t, b = Quartz.kCGEventRightMouseDragged, Quartz.kCGMouseButtonRight
        elif buttons:
            t, b = Quartz.kCGEventOtherMouseDragged, _BUTTON_MAC.get(min(buttons), 2)
        else:
            t, b = Quartz.kCGEventMouseMoved, Quartz.kCGMouseButtonLeft
        e = Quartz.CGEventCreateMouseEvent(self._src, t, (x, y), b)
        Quartz.CGEventSetIntegerValueField(e, F_DELTA_X, int(round(x - prev[0])))
        Quartz.CGEventSetIntegerValueField(e, F_DELTA_Y, int(round(y - prev[1])))
        self._last_loc = (x, y)
        self._post(e)

    def _post_button(self, b, down, x, y):
        mb = _BUTTON_MAC.get(b, 2)
        if b in _DOWN:
            t = _DOWN[b] if down else _UP[b]
        else:
            t = Quartz.kCGEventOtherMouseDown if down else Quartz.kCGEventOtherMouseUp
        e = Quartz.CGEventCreateMouseEvent(self._src, t, (x, y), mb)
        if down:
            pb, pt, ppos, n = self._clicks
            now = time.time()
            if pb == b and now - pt < 0.45 and ppos and abs(ppos[0] - x) < 5 and abs(ppos[1] - y) < 5:
                n += 1
            else:
                n = 1
            self._clicks = (b, now, (x, y), n)
        Quartz.CGEventSetIntegerValueField(e, F_CLICK_STATE, self._clicks[3] or 1)
        Quartz.CGEventSetIntegerValueField(e, F_BUTTON, mb)
        self._post(e)

    def _post_wheel(self, dx, dy):
        self._wheel_acc[0] += dx * WHEEL_PX
        self._wheel_acc[1] += dy * WHEEL_PX
        px, py = int(self._wheel_acc[0]), int(self._wheel_acc[1])
        if not px and not py:
            return
        self._wheel_acc[0] -= px
        self._wheel_acc[1] -= py
        e = Quartz.CGEventCreateScrollWheelEvent(self._src, Quartz.kCGScrollEventUnitPixel, 2, py, -px)
        self._post(e)

    def _post_key(self, hid, down):
        if hid == keys.BY_NAME["capslock"]:
            if down:
                self._toggle_caps()
            return
        if hid in _HID_TO_NX:
            self._post_media(_HID_TO_NX[hid], down)
            return
        kc = keys.to_mac(hid)
        if kc is None:
            return
        e = Quartz.CGEventCreateKeyboardEvent(self._src, kc, bool(down))
        flags = 0
        for h in self.held_inj:
            flags |= _FLAG.get(h, 0)
        Quartz.CGEventSetFlags(e, flags)
        self._post(e)

    def _post_media(self, nx, down):
        data1 = (nx << 16) | ((0xA if down else 0xB) << 8)
        ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            SYSTEM_DEFINED, (0, 0), 0xA00 if down else 0xB00, 0, 0, None, 8, data1, -1)
        self._post(ev.CGEvent())

    def _toggle_caps(self):
        # Caps Lock state can't be typed; flip it through IOKit's HID system.
        try:
            iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
            libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("c"))
            task = ctypes.c_uint.in_dll(libc, "mach_task_self_").value
            iokit.IOServiceMatching.restype = ctypes.c_void_p
            iokit.IOServiceGetMatchingService.restype = ctypes.c_uint
            iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            svc = iokit.IOServiceGetMatchingService(0, iokit.IOServiceMatching(b"IOHIDSystem"))
            conn = ctypes.c_uint()
            iokit.IOServiceOpen.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]
            iokit.IOServiceOpen(svc, task, 1, ctypes.byref(conn))
            state = ctypes.c_bool()
            iokit.IOHIDGetModifierLockState(conn, 1, ctypes.byref(state))
            iokit.IOHIDSetModifierLockState(conn, 1, not state.value)
            iokit.IOServiceClose(conn)
        except Exception as e:
            self.sink({"t": "log", "text": "caps lock: %s" % e})

    # ---- clipboard -------------------------------------------------------------------
    def _clip_get(self, images):
        n = self._pb.changeCount()
        if n == self._pb_count:
            return self._pb_cache
        self._pb_count = n
        got = None
        types = self._pb.types() or []
        if "org.nspasteboard.ConcealedType" in types and NSPasteboardTypeString in types:
            # Password managers mark what they copy (nspasteboard.org).
            s = self._pb.stringForType_(NSPasteboardTypeString)
            got = ("secret", str(s or ""))
            self._pb_cache = got
            return got
        if NSPasteboardTypeString in types:
            s = self._pb.stringForType_(NSPasteboardTypeString)
            if s is not None:
                got = ("text", str(s))
        if got is None and images:
            data = self._pb.dataForType_(NSPasteboardTypePNG)
            if data is None and NSPasteboardTypeTIFF in types:
                tiff = self._pb.dataForType_(NSPasteboardTypeTIFF)
                rep = NSBitmapImageRep.imageRepWithData_(tiff) if tiff is not None else None
                data = rep.representationUsingType_properties_(4, None) if rep is not None else None
            if data is not None:
                got = ("png", bytes(data))
        self._pb_cache = got
        return got

    def _clip_put(self, kind, data):
        self._pb.clearContents()
        if kind == "text":
            self._pb.setString_forType_(data, NSPasteboardTypeString)
        else:
            self._pb.setData_forType_(NSData.dataWithBytes_length_(data, len(data)), NSPasteboardTypePNG)
        self._pb_count = self._pb.changeCount()
        self._pb_cache = (kind, data)

    def _clip_files_get(self):
        out = []
        for item in self._pb.pasteboardItems() or []:
            s = item.stringForType_("public.file-url")
            if s:
                u = NSURL.URLWithString_(s)
                path = u.filePathURL().path() if u is not None and u.filePathURL() is not None else None
                if path:
                    out.append(str(path))
        return out

    def _clip_files_put(self, paths):
        self._pb.clearContents()
        self._pb.writeObjects_([NSURL.fileURLWithPath_(p) for p in paths])
        self._pb_count = self._pb.changeCount()
        self._pb_cache = None

    # ---- actions ----------------------------------------------------------------------
    def action(self, what, cmd):
        if what == "ring":
            subprocess.Popen(["/bin/sh", "-c", "for i in 1 2 3; do afplay /System/Library/Sounds/Glass.aiff; done"])
            _notify("Kvm", "%s is looking for this Mac" % (cmd.get("from") or "Another computer"))
        elif what == "lock":
            try:
                login = ctypes.cdll.LoadLibrary("/System/Library/PrivateFrameworks/login.framework/Versions/Current/login")
                login.SACLockScreenImmediate()
            except Exception:
                subprocess.Popen(["pmset", "displaysleepnow"])
        elif what == "sleep":
            subprocess.Popen(["pmset", "sleepnow"])
        elif what == "notify":
            _notify(cmd.get("title") or "Kvm", cmd.get("text") or "")

    def permissions(self):
        return mac_permissions(self._tap is not None)

    # ---- screen sharing ------------------------------------------------------------------
    def _capture_thread_init(self):
        self._cap_tool = False
        try:
            cg = _cg()
            cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
            if not cg.CGPreflightScreenCaptureAccess():
                cg.CGRequestScreenCaptureAccess()  # macOS asks once; then System Settings › Screen Recording
                self.sink({"t": "log", "text": "screen recording permission needed"})
        except Exception:
            pass

    def _grab_screen(self):
        from PIL import Image
        if not self._cap_tool:
            try:
                img = Quartz.CGWindowListCreateImage(Quartz.CGRectInfinite, Quartz.kCGWindowListOptionOnScreenOnly,
                                                     Quartz.kCGNullWindowID, Quartz.kCGWindowImageDefault)
                if img is not None:
                    w, h = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)
                    bpr = Quartz.CGImageGetBytesPerRow(img)
                    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
                    return Image.frombuffer("RGB", (w, h), bytes(data), "raw", "BGRX", bpr, 1)
            except Exception:
                pass
            self._cap_tool = True  # this macOS has no CGWindowListCreateImage: use the screencapture tool
        import os
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            subprocess.run(["screencapture", "-x", "-C", "-t", "jpg", path], capture_output=True, timeout=5)
            with open(path, "rb") as f:
                img = Image.open(io.BytesIO(f.read()))
                img.load()
                return img
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


    def _grab_region(self, rect):
        """Only the given part of the desktop (the extra display while extending)."""
        from PIL import Image
        try:
            x, y, w, h = rect
            img = Quartz.CGWindowListCreateImage(Quartz.CGRectMake(x, y, w, h), Quartz.kCGWindowListOptionOnScreenOnly,
                                                 Quartz.kCGNullWindowID, Quartz.kCGWindowImageDefault)
            if img is not None:
                iw, ih = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)
                bpr = Quartz.CGImageGetBytesPerRow(img)
                data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
                return Image.frombuffer("RGB", (iw, ih), bytes(data), "raw", "BGRX", bpr, 1)
        except Exception:
            pass
        return Backend._grab_region(self, rect)

    # ---- extending this Mac onto another computer --------------------------------------
    def vdisplay(self, cmd):
        threading.Thread(target=self._vdisplay, args=(dict(cmd),), name="kvm-vdisplay", daemon=True).start()

    def _vdisplay(self, cmd):
        from ..audio import native_tool
        old = getattr(self, "_vproc", None)
        self._vproc = None
        if old:
            try:
                old.stdin.close()
                old.wait(3)
            except Exception:
                old.kill()
        if not cmd.get("on"):
            self.sink({"t": "vdisplay", "on": False, "rect": None})
            return
        tool = native_tool("kvm-vdisplay")
        if not tool:
            self.sink({"t": "vdisplay", "on": False, "error": "This copy of Kvm can't add a display (kvm-vdisplay is missing)."})
            return
        w, h = int(cmd.get("w") or 1920), int(cmd.get("h") or 1080)
        proc = subprocess.Popen([tool, str(w), str(h), "1" if cmd.get("hidpi") else "0"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        line = proc.stdout.readline().decode("ascii", "replace").split()
        if len(line) != 2 or line[0] != "id":
            err = (proc.stderr.read() or b"").decode("utf-8", "replace").strip()
            self.sink({"t": "vdisplay", "on": False, "error": "Couldn't add a display to this Mac (%s)." % (err or "no reply")})
            return
        self._vproc = proc
        did = int(line[1])
        rect = None
        for _ in range(40):  # macOS takes a moment to place the new display
            b = Quartz.CGDisplayBounds(did)
            if b.size.width > 0:
                rect = [b.origin.x, b.origin.y, b.size.width, b.size.height]
                break
            time.sleep(0.05)
        self.sink({"t": "vdisplay", "on": True, "rect": rect, "id": did})

        def watch():
            proc.wait()
            if self._vproc is proc:
                self._vproc = None
                self.sink({"t": "vdisplay", "on": False, "rect": None, "error": "The extra display went away."})
        threading.Thread(target=watch, daemon=True).start()


    # ---- the camera, for another computer ----------------------------------------------
    def camera(self, cmd):
        threading.Thread(target=self._camera, args=(dict(cmd),), name="kvm-camera", daemon=True).start()

    def _camera(self, cmd):
        import base64
        import struct

        from PIL import Image

        from ..audio import native_tool
        old = getattr(self, "_camproc", None)
        self._camproc = None
        if old:
            try:
                old.stdin.close()
                old.wait(3)
            except Exception:
                old.kill()
        if not cmd.get("on"):
            return
        tool = native_tool("kvm-camera")
        if not tool:
            self.sink({"t": "camera", "on": False, "error": "This copy of Kvm can't use the camera (kvm-camera is missing)."})
            return
        proc = subprocess.Popen([tool, str(int(cmd.get("w") or 1280)), str(int(cmd.get("h") or 720)),
                                 str(int(cmd.get("fps") or 30))],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._camproc = proc
        self.sink({"t": "camera", "on": True})
        while self._camproc is proc:
            head = proc.stdout.read(4)
            if len(head) < 4:
                break
            n = struct.unpack(">I", head)[0]
            data = proc.stdout.read(n)
            if len(data) < n:
                break
            try:
                w, h = Image.open(io.BytesIO(data)).size
            except Exception:
                continue
            self.sink({"t": "camframe", "jpeg": base64.b64encode(data).decode("ascii"), "w": w, "h": h})
        if self._camproc is proc:
            self._camproc = None
            err = (proc.stderr.read() or b"").decode("utf-8", "replace").strip()
            if "permission" in err:
                err = "Allow Kvm to use the camera in System Settings › Privacy & Security › Camera, then try again."
            self.sink({"t": "camera", "on": False, "error": err or "The camera stopped."})


def mac_permissions(tap_ok=None):
    out = {"needs": [], "tap": tap_ok}
    try:
        cg = _cg()
        cg.CGPreflightListenEventAccess.restype = ctypes.c_bool
        cg.CGPreflightPostEventAccess.restype = ctypes.c_bool
        out["input_monitoring"] = bool(cg.CGPreflightListenEventAccess())
        out["accessibility"] = bool(cg.CGPreflightPostEventAccess())
    except Exception:
        out["input_monitoring"] = out["accessibility"] = None
    try:
        from ApplicationServices import AXIsProcessTrusted

        out["accessibility"] = bool(AXIsProcessTrusted())
    except Exception:
        pass
    # An event tap opens with Accessibility alone, but then gets only the mouse: keys need Input
    # Monitoring too. So the open tap proves nothing about the keyboard; trust the preflight.
    if tap_ok and out.get("accessibility") is False:
        out["accessibility"] = True
    try:
        hit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Carbon.framework/Frameworks/HIToolbox.framework/HIToolbox")
        hit.IsSecureEventInputEnabled.restype = ctypes.c_bool
        out["secure_input"] = bool(hit.IsSecureEventInputEnabled())
    except Exception:
        out["secure_input"] = None
    if out.get("input_monitoring") is False:
        out["needs"].append("input_monitoring")
    if out.get("accessibility") is False:
        out["needs"].append("accessibility")
    return out


def request_permissions():
    """Shows macOS's own prompts (each only once; after that the Settings pane is the way)."""
    try:
        cg = _cg()
        cg.CGRequestListenEventAccess()
        cg.CGRequestPostEventAccess()
    except Exception:
        pass
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt

        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
    except Exception:
        pass


_bg_done = False


def _background_cursor():
    """Lets a background app hide the pointer (macOS otherwise only lets the front app)."""
    global _bg_done
    if _bg_done:
        return
    _bg_done = True
    try:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        key = cf.CFStringCreateWithCString(None, b"SetsCursorInBackground", 0x08000100)
        true = ctypes.c_void_p.in_dll(cf, "kCFBooleanTrue")
        conn = cg._CGSDefaultConnection()
        cg.CGSSetConnectionProperty.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
        cg.CGSSetConnectionProperty(conn, conn, key, true)
    except Exception:
        pass


def _notify(title, text):
    def q(s):
        return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
    try:
        subprocess.Popen(["osascript", "-e", "display notification %s with title %s" % (q(text), q(title))],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
