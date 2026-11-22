"""Launcher: double-click / `python Kvm.py` opens the window.
Pass arguments for the command line, e.g.  python Kvm.py status
"""
from kvm.__main__ import run

if __name__ == "__main__":
    run()
