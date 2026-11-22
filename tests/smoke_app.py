"""Smoke-test a built app: its self-test loads every part it bundles (crypto, discovery, the
window, the platform's input layer, the Windows service bits) and pairs two agents and types a
key between them over the real network stack.
    python tests/smoke_app.py <path to Kvm executable>
"""
import json
import os
import subprocess
import sys
import tempfile

exe = sys.argv[1]
d = tempfile.mkdtemp()
out = os.path.join(d, "selftest.json")
r = subprocess.run([exe, "selftest", out], timeout=180)
assert os.path.isfile(out), "app wrote no self-test (exit %s)" % r.returncode
with open(out, encoding="utf-8") as f:
    st = json.load(f)
print(json.dumps(st, indent=2))
missing = [k for k, v in st.items() if v is False]
assert not missing, "missing from the build: %s" % missing
assert st["loopback"] is True, st
print("smoke test passed: %s %s" % (exe, st["version"]))
