import os
import sys


def native_backend():
    """This computer's input layer: Quartz on macOS, hooks and SendInput on Windows."""
    if sys.platform == "darwin":
        from .mac import MacBackend

        return MacBackend()
    if os.name == "nt":
        from .win import WinBackend

        return WinBackend()
    from .base import FakeBackend

    return FakeBackend()
