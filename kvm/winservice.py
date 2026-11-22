"""The Kvm service on Windows: what lets a Mac's keyboard and mouse reach admin prompts (UAC) and
the sign-in and lock screens.

Windows keeps those on a separate, protected desktop that ordinary apps can't type into. Only a
process running as SYSTEM inside the signed-in session can follow input there. So the setup
installs a service ("Kvm", runs as LocalSystem, starts with Windows) which:

  - runs the agent (agent.py): finds and pairs with computers, keeps the encrypted links. It runs
    before anyone signs in, so after a restart the Mac can drive the sign-in screen straight away;
  - starts a helper (`Kvm.exe helper`) in the active console session as SYSTEM, and restarts it
    when the session changes (sign-in, sign-out, switch user). The helper does the input work
    (platform/win.py with secure_desktop=True) and talks to the service over two anonymous pipes;
  - answers Ctrl+Alt+Del itself (SendSAS only works from a service);
  - serves the app window on 127.0.0.1 (control.py) so the window shows the same state.

Command lines:  Kvm.exe service-run   (what the service manager starts)
                Kvm.exe helper        (started by the service, never by hand)
"""

import json
import os
import sys
import threading
import time

from .platform.base import Backend
from .screens import Screens

SERVICE_NAME = "Kvm"
DISPLAY_NAME = "Kvm (keyboard and mouse sharing)"


# ==== the helper (runs in the user's session) ======================================

def helper_main():
    import msvcrt

    from .platform.win import WinBackend

    import ctypes
    k32 = ctypes.windll.kernel32
    fin = os.fdopen(msvcrt.open_osfhandle(k32.GetStdHandle(-10), os.O_RDONLY), "r", encoding="utf-8", newline="\n")
    fout = os.fdopen(msvcrt.open_osfhandle(k32.GetStdHandle(-11), 0), "w", encoding="utf-8", newline="\n")
    lock = threading.Lock()

    def emit(ev):
        with lock:
            try:
                fout.write(json.dumps(ev) + "\n")
                fout.flush()
            except Exception:
                os._exit(0)  # the service went away

    be = WinBackend(secure_desktop=True)
    be.start(emit)
    emit({"t": "helper_ready", "pid": os.getpid()})
    perm_last = None
    for line in fin:
        try:
            cmd = json.loads(line)
        except ValueError:
            continue
        if cmd.get("c") == "quit":
            break
        be.handle(cmd)
        p = be.permissions()
        if p != perm_last:
            perm_last = p
            emit({"t": "permissions", "p": p})
    be.stop()
    os._exit(0)


# ==== the service side ===============================================================

class HelperProxy(Backend):
    """A Backend whose work happens in the helper process; the agent can't tell the difference."""
    name = "windows-service"
    can_capture = True
    can_inject = True
    can_audio = True  # the helper plays and records in the signed-in session

    def __init__(self):
        self._proc = None
        self._fin = None
        self._fout = None
        self._session = None
        self._wlock = threading.Lock()
        self._state = {}          # last config / lock, re-sent to a new helper
        self._perm = {"needs": [], "secure_desktop": True}
        Backend.__init__(self)
        self.screens = Screens([(0, 0, 1920, 1080)])

    def start(self, sink):
        self._real = sink
        self.sink = sink
        threading.Thread(target=self._supervise, name="kvm-helper", daemon=True).start()

    def stop(self):
        self._send({"c": "quit"})

    def _screens(self):
        # Backend.__init__ asks before the helper has reported the real screens.
        s = getattr(self, "screens", None)
        return s.public() if s else [(0, 0, 1920, 1080)]

    def permissions(self):
        return dict(self._perm, helper=bool(self._proc), session=self._session)

    def handle(self, cmd):
        c = cmd.get("c")
        if c == "sas":
            send_sas()
            return
        if c in ("config", "lock", "driven", "capture"):
            self._state[c] = cmd
        if c == "audio_capture":
            self._state["audio_capture:%s" % cmd.get("src")] = cmd
        if c == "action" and cmd.get("a") == "lock":
            lock_session()
            return
        if c == "action" and cmd.get("a") == "sleep":
            threading.Thread(target=sleep_now, daemon=True).start()
            return
        self._send(cmd)

    def _send(self, cmd):
        with self._wlock:
            if not self._fout:
                return
            try:
                self._fout.write(json.dumps(cmd) + "\n")
                self._fout.flush()
            except Exception:
                self._fout = None

    def _supervise(self):
        while True:
            try:
                session = active_session()
                alive = self._proc is not None and _alive(self._proc)
                if session is not None and (session != self._session or not alive):
                    self._kill()
                    self._session = session
                    self._spawn(session)
            except Exception as e:
                self.sink({"t": "log", "text": "helper: %r" % e})
            time.sleep(1.0)

    def _spawn(self, session):
        proc, fin, fout = launch_in_session(session, [_exe(), "helper"])
        self._proc = proc
        with self._wlock:
            self._fout = fout
        self._fin = fin
        threading.Thread(target=self._reader, args=(fin, proc), daemon=True).start()
        # A new helper (sign-in, switch user) picks up where the last one was.
        for k in ("config", "lock", "capture", "audio_capture:output", "audio_capture:mic"):
            if k in self._state:
                self._send(self._state[k])

    def _reader(self, fin, proc):
        for line in fin:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            t = ev.get("t")
            if t == "screens":
                self.screens = Screens(ev.get("rects") or [])
            elif t == "permissions":
                self._perm = ev.get("p") or self._perm
                continue
            elif t == "helper_ready":
                continue
            elif t == "sas_request":
                send_sas()  # Ctrl+Alt+Del typed on the other computer
                continue
            self.sink(ev)
        if self._proc is proc:
            self._proc = None
            # The helper is gone (sign-out, crash): send the pointer home so nothing stays stuck.
            if (self._state.get("driven") or {}).get("exits"):
                self._state.pop("driven", None)
                self.sink({"t": "exit", "side": None, "frac": 0.5})

    def _kill(self):
        if self._proc is not None:
            try:
                self._send({"c": "quit"})
                import win32api
                win32api.TerminateProcess(self._proc, 0)
            except Exception:
                pass
        self._proc = None
        with self._wlock:
            self._fout = None


def _exe():
    return sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])


def _alive(proc):
    import win32event
    return win32event.WaitForSingleObject(proc, 0) == win32event.WAIT_TIMEOUT


def active_session():
    import ctypes
    s = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
    return None if s == 0xFFFFFFFF else s


def launch_in_session(session, argv):
    """Start `argv` as SYSTEM in `session` on winsta0\\default, with pipes for stdin and stdout."""
    import msvcrt
    import subprocess

    import pywintypes
    import win32api
    import win32con
    import win32pipe
    import win32process
    import win32security

    sa = pywintypes.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = True
    child_in_r, child_in_w = win32pipe.CreatePipe(sa, 0)
    child_out_r, child_out_w = win32pipe.CreatePipe(sa, 0)
    win32api.SetHandleInformation(child_in_w, win32con.HANDLE_FLAG_INHERIT, 0)
    win32api.SetHandleInformation(child_out_r, win32con.HANDLE_FLAG_INHERIT, 0)

    tok = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_ALL_ACCESS)
    dup = win32security.DuplicateTokenEx(tok, win32security.SecurityImpersonation, win32security.TOKEN_ALL_ACCESS,
                                         win32security.TokenPrimary)
    win32security.SetTokenInformation(dup, win32security.TokenSessionId, session)

    si = win32process.STARTUPINFO()
    si.lpDesktop = "winsta0\\default"
    si.dwFlags = win32process.STARTF_USESTDHANDLES | win32con.STARTF_USESHOWWINDOW
    si.wShowWindow = win32con.SW_HIDE
    si.hStdInput = child_in_r
    si.hStdOutput = child_out_w
    si.hStdError = child_out_w
    cmd = subprocess.list2cmdline(argv)
    hproc, hthread, pid, tid = win32process.CreateProcessAsUser(
        dup, None, cmd, None, None, True, win32con.CREATE_NO_WINDOW | win32con.NORMAL_PRIORITY_CLASS,
        None, os.path.dirname(argv[0]), si)
    win32api.CloseHandle(hthread)
    child_in_r.Close()
    child_out_w.Close()
    fout = os.fdopen(msvcrt.open_osfhandle(child_in_w.Detach(), 0), "w", encoding="utf-8", newline="\n")
    fin = os.fdopen(msvcrt.open_osfhandle(child_out_r.Detach(), os.O_RDONLY), "r", encoding="utf-8", newline="\n")
    return hproc, fin, fout


def send_sas():
    """Ctrl+Alt+Del (the setup allows services to send it: SoftwareSASGeneration)."""
    try:
        import ctypes
        ctypes.WinDLL("sas").SendSAS(False)
    except Exception:
        pass


def lock_session():
    try:
        import win32ts
        s = active_session()
        if s is not None:
            win32ts.WTSDisconnectSession(None, s, False)  # the console shows the lock screen
    except Exception:
        pass


def sleep_now():
    try:
        import ctypes
        import win32api
        import win32security
        tok = win32security.OpenProcessToken(win32api.GetCurrentProcess(),
                                             win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY)
        luid = win32security.LookupPrivilegeValue(None, "SeShutdownPrivilege")
        win32security.AdjustTokenPrivileges(tok, False, [(luid, win32security.SE_PRIVILEGE_ENABLED)])
        ctypes.windll.powrprof.SetSuspendState(False, False, False)
    except Exception:
        pass


def user_home():
    """The signed-in user's profile folder (received files go to their Downloads)."""
    try:
        import win32profile
        import win32ts
        s = active_session()
        tok = win32ts.WTSQueryUserToken(s)
        return win32profile.GetUserProfileDirectory(tok)
    except Exception:
        return None


def service_log_path():
    from .store import service_data_dir
    return os.path.join(service_data_dir(), "service.log")


def slog(msg):
    """The service's own log (%ProgramData%\\PXLVZN\\Kvm\\service.log): it has no console, and a
    service that won't start is otherwise silent."""
    try:
        path = service_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > 512 * 1024:
            os.replace(path, path + ".old")
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def run_agent_forever(stop_event):
    from . import control
    from .store import Store, service_data_dir

    folder = service_data_dir()
    os.makedirs(folder, exist_ok=True)
    _lock_down(folder)
    slog("starting the agent")
    agent = ServiceAgent(HelperProxy(), Store(folder)).start()
    slog("agent listening on %s" % agent.port)
    srv = control.serve(agent, folder)
    slog("control endpoint up")
    stop_event.wait()
    slog("stopping")
    srv.shutdown()
    agent.stop()


def _service_agent_class():
    from .agent import Agent

    class _SA(Agent):
        @property
        def _home_dir(self):
            return user_home()

        @_home_dir.setter
        def _home_dir(self, v):
            pass

    return _SA


def ServiceAgent(backend, store):
    return _service_agent_class()(backend, store)


def _lock_down(folder):
    """Pair keys live here: SYSTEM and administrators only."""
    try:
        import subprocess
        subprocess.run(["icacls", folder, "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"],
                       capture_output=True, timeout=20, creationflags=0x08000000)
    except Exception:
        pass


# ==== the Windows service wrapper (pywin32) ===========================================

def service_main():
    import servicemanager
    import win32service
    import win32serviceutil

    class KvmService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = DISPLAY_NAME
        _svc_description_ = "Lets paired computers use this PC's keyboard and mouse, including on admin prompts and the sign-in screen."

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = threading.Event()

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.stop_event.set()

        def SvcDoRun(self):
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            try:
                run_agent_forever(self.stop_event)
            except Exception as e:
                import traceback
                slog("service stopped:\n" + traceback.format_exc())
                servicemanager.LogErrorMsg("Kvm service stopped: %r" % e)
                raise

    slog("service-run (Kvm %s, pid %d)" % (_version(), os.getpid()))
    try:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(KvmService)
        servicemanager.StartServiceCtrlDispatcher()
    except Exception:
        import traceback
        slog("service dispatcher failed:\n" + traceback.format_exc())
        raise


def _version():
    from . import __version__
    return __version__


def service_installed():
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\%s" % SERVICE_NAME):
            return True
    except OSError:
        return False


# ==== install / remove (run by the setup, as administrator) =============================

def install_service(exe=None):
    """Registers and starts the service, opens the firewall for it and lets it send Ctrl+Alt+Del."""
    import subprocess

    import win32service
    import win32serviceutil

    exe = exe or _exe()
    remove_service(quiet=True)
    hscm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
    try:
        hs = win32service.CreateService(
            hscm, SERVICE_NAME, DISPLAY_NAME, win32service.SERVICE_ALL_ACCESS, win32service.SERVICE_WIN32_OWN_PROCESS,
            win32service.SERVICE_AUTO_START, win32service.SERVICE_ERROR_NORMAL, '"%s" service-run' % exe,
            None, 0, None, None, None)
        try:
            win32service.ChangeServiceConfig2(hs, win32service.SERVICE_CONFIG_DESCRIPTION,
                                              "Lets paired computers use this PC's keyboard and mouse, including on admin prompts and the sign-in screen.")
            # Restart it if it ever stops unexpectedly: 2 s, 5 s, then every 30 s.
            try:
                win32service.ChangeServiceConfig2(hs, win32service.SERVICE_CONFIG_FAILURE_ACTIONS, {
                    "ResetPeriod": 3600, "RebootMsg": None, "Command": None,
                    "Actions": [(win32service.SC_ACTION_RESTART, 2000), (win32service.SC_ACTION_RESTART, 5000),
                                (win32service.SC_ACTION_RESTART, 30000)]})
            except Exception:
                pass
        finally:
            win32service.CloseServiceHandle(hs)
    finally:
        win32service.CloseServiceHandle(hscm)
    flags = 0x08000000
    subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule", "name=Kvm"], capture_output=True, creationflags=flags)
    subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule", "name=Kvm", "dir=in", "action=allow",
                    "program=%s" % exe, "enable=yes", "profile=any"], capture_output=True, creationflags=flags)
    _allow_sas(True)
    win32serviceutil.StartService(SERVICE_NAME)
    return 0


def remove_service(quiet=False):
    import subprocess

    import win32service
    import win32serviceutil
    try:
        win32serviceutil.StopService(SERVICE_NAME)
        for _ in range(40):
            if win32serviceutil.QueryServiceStatus(SERVICE_NAME)[1] == win32service.SERVICE_STOPPED:
                break
            time.sleep(0.25)
    except Exception:
        pass
    try:
        win32serviceutil.RemoveService(SERVICE_NAME)
    except Exception:
        if not quiet:
            pass
    subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule", "name=Kvm"], capture_output=True,
                   creationflags=0x08000000)
    if not quiet:
        _allow_sas(False)
    return 0


def _allow_sas(on):
    """SoftwareSASGeneration: 1 = services may send Ctrl+Alt+Del (keeps a stricter existing value)."""
    import winreg
    path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
    try:
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            try:
                cur = winreg.QueryValueEx(k, "SoftwareSASGeneration")[0]
            except OSError:
                cur = None
            if on and cur in (None, 0):
                winreg.SetValueEx(k, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(k, "KvmSetSAS", 0, winreg.REG_DWORD, 1)
            elif not on:
                try:
                    if winreg.QueryValueEx(k, "KvmSetSAS")[0]:
                        winreg.DeleteValue(k, "SoftwareSASGeneration")
                        winreg.DeleteValue(k, "KvmSetSAS")
                except OSError:
                    pass
    except OSError:
        pass
