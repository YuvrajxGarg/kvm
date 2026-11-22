"""Windows input: low-level hooks to capture this PC's mouse and keyboard, SendInput to put another
computer's input on it, and the clipboard.

Runs either inside the app (installed without the service: works on the normal desktop), or in the
helper process the Kvm service starts in the signed-in session as SYSTEM (winservice.py). From
there injection follows Windows to whichever desktop has input, so admin prompts (UAC) and the
sign-in and lock screens take the mouse and keyboard too.
"""

import os
import ctypes
import queue
import threading
import time
from ctypes import wintypes

from .. import keys, png
from .base import Backend

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

MARK = 0x4B564D21  # dwExtraInfo on our own injected input
ULONG_PTR = ctypes.c_size_t

WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_MOUSEMOVE = 0x200
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP = 0x201, 0x202, 0x204, 0x205
WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MOUSEWHEEL, WM_XBUTTONDOWN, WM_XBUTTONUP, WM_MOUSEHWHEEL = 0x207, 0x208, 0x20A, 0x20B, 0x20C, 0x20E
LLKHF_EXTENDED, LLKHF_INJECTED = 0x01, 0x10

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_VIRTUALDESK = 0x1, 0x8000, 0x4000
MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL = 0x800, 0x1000
_BTN_FLAGS = {1: (0x2, 0x4, 0), 2: (0x8, 0x10, 0), 3: (0x20, 0x40, 0), 4: (0x80, 0x100, 1), 5: (0x80, 0x100, 2)}
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x1, 0x2, 0x8

CF_UNICODETEXT, CF_DIB, CF_DIBV5 = 13, 8, 17
GMEM_MOVEABLE = 0x2


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.OpenInputDesktop.restype = wintypes.HANDLE
user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.CopyImage.restype = wintypes.HANDLE
user32.LoadCursorW.restype = wintypes.HANDLE
user32.CreateCursor.restype = wintypes.HANDLE
user32.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HDC,
                         ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                            ctypes.c_void_p, wintypes.UINT]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]

_OCR = (32512, 32513, 32514, 32515, 32516, 32642, 32643, 32644, 32645, 32646, 32648, 32649, 32650, 32651)


def dpi_aware():
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2: real pixels
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


class WinBackend(Backend):
    name = "windows"
    can_capture = True
    can_inject = True

    @property
    def can_vcam(self):
        from ..vcam import available
        return available()

    def __init__(self, secure_desktop=False):
        dpi_aware()
        self._secure = secure_desktop       # running as SYSTEM: follow the input desktop
        self._desk_name = None
        self._desk_checked = 0.0
        self._park = None
        self._last = None
        self._hidden = False
        self._wheel_acc = [0.0, 0.0]
        self._clip_seq = None
        self._clip_cache = None
        self._png_fmt = user32.RegisterClipboardFormatW("PNG")
        self._cmds = queue.Queue()
        self._hooks = []
        self._procs = []
        Backend.__init__(self)
        restore_cursors()  # in case a crash left them hidden

    def start(self, sink):
        Backend.start(self, sink)
        threading.Thread(target=self._inject_thread, name="kvm-inject", daemon=True).start()
        threading.Thread(target=self._hook_thread, name="kvm-hooks", daemon=True).start()

    def stop(self):
        Backend.stop(self)
        restore_cursors()

    # Commands run on one thread that owns no windows, so it may switch desktops (sign-in, UAC).
    def handle(self, cmd):
        self._cmds.put(cmd)

    def _inject_thread(self):
        while True:
            cmd = self._cmds.get()
            try:
                if self._secure:
                    self._follow_desktop()
                Backend.handle(self, cmd)
            except Exception as e:
                self.sink({"t": "log", "text": "inject %s: %r" % (cmd.get("c"), e)})

    def _follow_desktop(self, force=False):
        now = time.time()
        if not force and now - self._desk_checked < 0.15:
            return
        self._desk_checked = now
        h = user32.OpenInputDesktop(0, False, 0x10000000)  # GENERIC_ALL
        if not h:
            return
        name = _desktop_name(h)
        if name != self._desk_name:
            if user32.SetThreadDesktop(h):
                self._desk_name = name
                self.sink({"t": "desktop", "name": name})
                return  # keep this handle open: the thread now uses it
        user32.CloseDesktop(h)

    # ---- hooks ---------------------------------------------------------------
    def _hook_thread(self):
        hmod = kernel32.GetModuleHandleW(None)
        mproc = HOOKPROC(self._mouse_proc)
        kproc = HOOKPROC(self._key_proc)
        self._procs = [mproc, kproc]
        self._hooks = [user32.SetWindowsHookExW(WH_MOUSE_LL, mproc, hmod, 0),
                       user32.SetWindowsHookExW(WH_KEYBOARD_LL, kproc, hmod, 0)]
        if not all(self._hooks):
            self.sink({"t": "log", "text": "hooks failed: %d" % ctypes.get_last_error()})
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _mouse_proc(self, code, wparam, lparam):
        if code >= 0:
            try:
                m = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if m.dwExtraInfo != MARK and self._on_mouse(wparam, m):
                    return 1
            except Exception:
                pass
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _on_mouse(self, msg, m):
        x, y = m.pt.x, m.pt.y
        if msg == WM_MOUSEMOVE:
            if self.grabbed:
                if self._park:
                    dx, dy = x - self._park[0], y - self._park[1]
                    self.on_grabbed_move(dx, dy)
                return True
            dx, dy = (x - self._last[0], y - self._last[1]) if self._last else (0, 0)
            self._last = (x, y)
            return self.on_local_move(float(x), float(y), dx, dy)
        if msg in (WM_MOUSEWHEEL, WM_MOUSEHWHEEL):
            delta = ctypes.c_short(m.mouseData >> 16).value / 120.0
            return self.on_local_wheel(delta, 0.0) if msg == WM_MOUSEHWHEEL else self.on_local_wheel(0.0, delta)
        b = {WM_LBUTTONDOWN: (1, True), WM_LBUTTONUP: (1, False), WM_RBUTTONDOWN: (2, True), WM_RBUTTONUP: (2, False),
             WM_MBUTTONDOWN: (3, True), WM_MBUTTONUP: (3, False)}.get(msg)
        if msg in (WM_XBUTTONDOWN, WM_XBUTTONUP):
            b = (4 if (m.mouseData >> 16) == 1 else 5, msg == WM_XBUTTONDOWN)
        if b:
            return self.on_local_button(b[0], b[1])
        return self.grabbed

    def _key_proc(self, code, wparam, lparam):
        if code >= 0:
            try:
                k = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if k.dwExtraInfo != MARK:
                    down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    hid = keys.from_win(k.scanCode, bool(k.flags & LLKHF_EXTENDED), k.vkCode)
                    if self.on_local_key(hid, down):
                        return 1
            except Exception:
                pass
        return user32.CallNextHookEx(None, code, wparam, lparam)

    # ---- grab ------------------------------------------------------------------
    def _set_grab(self, on):
        if on:
            r = self.screens.rects[0]
            for rr in self.screens.rects:
                if rr[0] == 0 and rr[1] == 0:
                    r = rr
            self._park = (int(r[0] + r[2] / 2), int(r[1] + r[3] / 2))
            user32.SetCursorPos(*self._park)
            hide_cursors()
        else:
            restore_cursors()
            self._park = None
            self._last = None

    # ---- geometry ------------------------------------------------------------------
    def _screens(self):
        out = []

        def cb(hmon, hdc, rect, data):
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcMonitor
                out.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return True

        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
        return out

    def _cursor(self):
        p = POINT()
        if user32.GetCursorPos(ctypes.byref(p)):
            return (float(p.x), float(p.y))
        return None

    def _warp(self, x, y):
        self._send_mouse(x, y, MOUSEEVENTF_MOVE)
        user32.SetCursorPos(int(x), int(y))
        self._last = (int(x), int(y))

    # ---- injection -------------------------------------------------------------------
    def _send(self, inp):
        n = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if n == 0 and self._secure:
            self._follow_desktop(force=True)  # the desktop changed under us: retry there
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _send_mouse(self, x, y, flags, data=0):
        vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
        vw, vh = max(2, user32.GetSystemMetrics(78)), max(2, user32.GetSystemMetrics(79))
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi = MOUSEINPUT(int(round((x - vx) * 65535.0 / (vw - 1))), int(round((y - vy) * 65535.0 / (vh - 1))),
                              data, flags | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, 0, MARK)
        self._send(inp)

    def _post_move(self, x, y, buttons):
        self._send_mouse(x, y, MOUSEEVENTF_MOVE)

    def _post_button(self, b, down, x, y):
        f = _BTN_FLAGS.get(b)
        if not f:
            return
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi = MOUSEINPUT(0, 0, f[2], f[0] if down else f[1], 0, MARK)
        self._send(inp)

    def _post_wheel(self, dx, dy):
        for axis, val, flag in ((1, dy, MOUSEEVENTF_WHEEL), (0, dx, MOUSEEVENTF_HWHEEL)):
            if not val:
                continue
            self._wheel_acc[axis] += val * 120.0
            n = int(self._wheel_acc[axis])
            if not n:
                continue
            self._wheel_acc[axis] -= n
            inp = INPUT(type=INPUT_MOUSE)
            inp.u.mi = MOUSEINPUT(0, 0, ctypes.c_uint32(n).value, flag, 0, MARK)
            self._send(inp)

    def _post_key(self, hid, down):
        w = keys.to_win(hid)
        if not w:
            return
        scan, ext, vk = w
        inp = INPUT(type=INPUT_KEYBOARD)
        if vk:
            flags = (0 if down else KEYEVENTF_KEYUP) | (KEYEVENTF_EXTENDEDKEY if ext else 0)
            inp.u.ki = KEYBDINPUT(vk, scan, flags, 0, MARK)
        else:
            flags = KEYEVENTF_SCANCODE | (0 if down else KEYEVENTF_KEYUP) | (KEYEVENTF_EXTENDEDKEY if ext else 0)
            inp.u.ki = KEYBDINPUT(0, scan, flags, 0, MARK)
        self._send(inp)

    # ---- clipboard ---------------------------------------------------------------------
    def _clip_get(self, images):
        seq = user32.GetClipboardSequenceNumber()
        if seq == self._clip_seq:
            return self._clip_cache
        if not _open_clipboard():
            return self._clip_cache
        got = None
        try:
            if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                h = user32.GetClipboardData(CF_UNICODETEXT)
                p = kernel32.GlobalLock(h) if h else None
                if p:
                    try:
                        got = ("text", ctypes.wstring_at(p))
                    finally:
                        kernel32.GlobalUnlock(h)
            if got is None and images:
                raw = None
                if user32.IsClipboardFormatAvailable(self._png_fmt):
                    raw = _global_bytes(user32.GetClipboardData(self._png_fmt))
                elif user32.IsClipboardFormatAvailable(CF_DIB):
                    dib = _global_bytes(user32.GetClipboardData(CF_DIB))
                    if dib:
                        try:
                            raw = png.dib_to_png(dib)
                        except Exception:
                            raw = None
                if raw:
                    got = ("png", raw)
        finally:
            user32.CloseClipboard()
        self._clip_seq = seq
        self._clip_cache = got
        return got

    def _clip_put(self, kind, data):
        if not _open_clipboard():
            return
        try:
            user32.EmptyClipboard()
            if kind == "text":
                buf = ctypes.create_unicode_buffer(data)
                _set_global(CF_UNICODETEXT, ctypes.string_at(ctypes.addressof(buf), ctypes.sizeof(buf)))
            else:
                _set_global(self._png_fmt, data)
                try:
                    _set_global(CF_DIB, png.png_to_dib(data))
                except Exception:
                    pass
        finally:
            user32.CloseClipboard()
        self._clip_seq = user32.GetClipboardSequenceNumber()
        self._clip_cache = (kind, data)

    # ---- actions -------------------------------------------------------------------------
    def action(self, what, cmd):
        if what == "ring":
            import winsound

            def ring():
                for _ in range(3):
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                    time.sleep(0.3)
            threading.Thread(target=ring, daemon=True).start()
        elif what == "lock":
            user32.LockWorkStation()
        elif what == "sleep":
            ctypes.windll.powrprof.SetSuspendState(False, False, False)
        elif what == "notify":
            _toast(cmd.get("title") or "Kvm", cmd.get("text") or "")

    def sas(self):
        if self._secure:
            self.sink({"t": "sas_request"})  # only the service may send Ctrl+Alt+Del
        else:
            try:
                ctypes.WinDLL("sas").SendSAS(False)
            except Exception:
                pass

    def permissions(self):
        return {"needs": [], "secure_desktop": self._secure, "desktop": self._desk_name}

    # ---- screen sharing ------------------------------------------------------------------
    def _capture_thread_init(self):
        self._cap_desk = None
        self._cap_checked = 0.0

    def _cap_follow(self):
        """The capture thread follows the input desktop too, so admin prompts and the sign-in
        screen show up in the viewer (each thread has its own desktop)."""
        now = time.time()
        if now - self._cap_checked < 0.5:
            return
        self._cap_checked = now
        h = user32.OpenInputDesktop(0, False, 0x10000000)
        if not h:
            return
        name = _desktop_name(h)
        if name != self._cap_desk and user32.SetThreadDesktop(h):
            self._cap_desk = name
            return
        user32.CloseDesktop(h)

    def _grab_screen(self):
        from PIL import Image
        if self._secure:
            self._cap_follow()
        vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
        vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        if vw <= 0 or vh <= 0:
            return None
        hdc = user32.GetDC(None)
        mdc = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, vw, vh)
        old = gdi32.SelectObject(mdc, bmp)
        try:
            if not gdi32.BitBlt(mdc, 0, 0, vw, vh, hdc, vx, vy, 0x00CC0020 | 0x40000000):  # SRCCOPY | CAPTUREBLT
                return None
            bi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=vw, biHeight=-vh, biPlanes=1,
                                  biBitCount=32, biCompression=0)
            buf = ctypes.create_string_buffer(vw * vh * 4)
            if not gdi32.GetDIBits(mdc, bmp, 0, vh, buf, ctypes.byref(bi), 0):
                return None
            return Image.frombuffer("RGB", (vw, vh), buf.raw, "raw", "BGRX", 0, 1)
        finally:
            gdi32.SelectObject(mdc, old)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mdc)
            user32.ReleaseDC(None, hdc)


# ---- helpers ------------------------------------------------------------------------------

def _desktop_name(h):
    buf = ctypes.create_unicode_buffer(256)
    n = wintypes.DWORD()
    if user32.GetUserObjectInformationW(h, 2, buf, ctypes.sizeof(buf), ctypes.byref(n)):  # UOI_NAME
        return buf.value
    return None


def _open_clipboard():
    for _ in range(10):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def _global_bytes(h):
    if not h:
        return None
    p = kernel32.GlobalLock(h)
    if not p:
        return None
    try:
        return ctypes.string_at(p, kernel32.GlobalSize(h))
    finally:
        kernel32.GlobalUnlock(h)


def _set_global(fmt, data):
    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    p = kernel32.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    kernel32.GlobalUnlock(h)
    user32.SetClipboardData(fmt, h)


_cursors_hidden = False


def hide_cursors():
    """While the pointer is on another computer, hide this PC's pointer (blank system cursors)."""
    global _cursors_hidden
    if _cursors_hidden:
        return
    and_mask = (ctypes.c_ubyte * 128)(*([0xFF] * 128))
    xor_mask = (ctypes.c_ubyte * 128)(*([0x00] * 128))
    for ocr in _OCR:
        cur = user32.CreateCursor(None, 0, 0, 32, 32, and_mask, xor_mask)
        if cur:
            user32.SetSystemCursor(cur, ocr)
    _cursors_hidden = True


def restore_cursors():
    global _cursors_hidden
    user32.SystemParametersInfoW(0x57, 0, None, 0)  # SPI_SETCURSORS: reload the user's cursors
    _cursors_hidden = False


_TOAST_PS = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:KVM_T))
$b = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:KVM_B))
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml('<toast><visual><binding template="ToastGeneric"><text></text><text></text></binding></visual></toast>')
$n = $x.GetElementsByTagName('text'); $n.Item(0).InnerText = $t; $n.Item(1).InnerText = $b
$id = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id).Show([Windows.UI.Notifications.ToastNotification]::new($x))
"""


def _toast(title, text):
    """A Windows notification (a phone's notification, a file that arrived). Text goes through the
    environment, never the command line, so nothing in it can run."""
    import base64
    import subprocess
    env = dict(os.environ, KVM_T=base64.b64encode(title.encode("utf-8")).decode(),
               KVM_B=base64.b64encode(text.encode("utf-8")).decode())
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _TOAST_PS],
                         env=env, creationflags=0x08000000, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass
