# PyInstaller build recipe for macOS (.app) and Windows (folder with .exe).
#   pyinstaller --noconfirm Kvm.spec
import os
import sys

from PyInstaller.utils.hooks import collect_all

root = SPECPATH
version = open(os.path.join(root, "VERSION")).read().strip()

datas, binaries, hiddenimports = [], [], []
datas += [
    (os.path.join(root, "kvm", "ui"), os.path.join("kvm", "ui")),
    (os.path.join(root, "VERSION"), "."),
]
hiddenimports += ["certifi", "kvm.platform.base"]
for pkg in ("nacl", "spake2", "zeroconf"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
if sys.platform == "darwin":
    hiddenimports += ["kvm.platform.mac", "Quartz", "AppKit", "Foundation", "ApplicationServices", "PyObjCTools.AppHelper"]
elif sys.platform == "win32":
    hiddenimports += ["kvm.platform.win", "kvm.winservice", "kvm.control", "win32timezone", "servicemanager", "win32service",
                      "win32serviceutil", "win32event", "win32ts", "win32profile", "win32process", "win32security",
                      "win32pipe", "win32api", "win32con", "pywintypes"]
excludes = ["tkinter", "_tkinter", "matplotlib", "scipy", "numpy", "PIL"]

a = Analysis(
    [os.path.join(root, "Kvm.py")],
    pathex=[root],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=excludes,
)
pyz = PYZ(a.pure)
icon = os.path.join(root, "assets", "AppIcon.icns" if sys.platform == "darwin" else "icon.ico")

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Kvm",
    console=False,
    icon=icon,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Kvm")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Kvm.app",
        icon=icon,
        bundle_identifier="com.yuvrajgarg.kvm",
        version=version,
        info_plist={
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "CFBundleDisplayName": "Kvm",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSRequiresAquaSystemAppearance": False,
            # Finding the other computer on the Wi-Fi (Bonjour) and connecting to it.
            "NSLocalNetworkUsageDescription": "Kvm finds and connects to your other computers on this network.",
            "NSBonjourServices": ["_pxlkvm._tcp"],
        },
    )
