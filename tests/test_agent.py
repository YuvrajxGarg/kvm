"""Two agents with fake input layers, talking over localhost: pairing, crossing, typing, coming
home, clipboard, files and actions."""

import os
import shutil
import tempfile
import time
import unittest

from kvm import keys
from kvm.agent import Agent
from kvm.platform.base import FakeBackend
from kvm.store import Store, this_platform


def wait(cond, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


class TwoComputers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mac_be = FakeBackend([(0, 0, 1440, 900)])
        self.pc_be = FakeBackend([(0, 0, 1920, 1080), (1920, 0, 2560, 1440)])
        self.mac = Agent(self.mac_be, Store(os.path.join(self.tmp, "mac")), port=0, discover=False).start()
        self.pc = Agent(self.pc_be, Store(os.path.join(self.tmp, "pc")), port=0, discover=False,
                        home_dir=os.path.join(self.tmp, "pchome")).start()
        self.mac._store.data["pairs"] = {}
        # Pair: the Mac types the code the PC shows.
        rid = self.mac.add_address("127.0.0.1:%d" % self.pc.port)
        self.assertTrue(self.mac.pair(rid))
        self.assertTrue(wait(lambda: (self.pc.status()["pairing"] or {}).get("phase") == "showing"))
        self.assertTrue(wait(lambda: (self.mac.status()["pairing"] or {}).get("phase") == "code"))
        code = self.pc.status()["pairing"]["code"]
        self.mac.pair_code(code)
        self.assertTrue(wait(lambda: (self.mac.status()["pairing"] or {}).get("phase") == "done"), self.mac.status()["pairing"])
        self.pc_id = self.pc._store.id
        self.mac_id = self.mac._store.id
        self.assertTrue(wait(lambda: any(p["connected"] for p in self.mac.status()["peers"])))
        self.assertTrue(wait(lambda: any(p["connected"] for p in self.pc.status()["peers"])))
        self.mac.set_side(self.pc_id, "right")
        self.assertTrue(wait(lambda: (self.pc._store.pair(self.mac_id) or {}).get("side") == "left"))
        self.assertTrue(wait(lambda: self.mac_be.watch_sides == ["right"]))

    def tearDown(self):
        self.mac.stop()
        self.pc.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cross(self):
        # Push into the Mac's right edge.
        self.assertTrue(self.mac_be.on_local_move(1439, 450, 5, 0))
        self.assertTrue(wait(lambda: self.pc.status()["mode"] == "driven"))
        self.assertEqual(self.mac.status()["mode"], "driving")

    def test_mouse_drift_after_crossing_stays_put(self):
        # A mouse settling after the push (a pixel or two back toward the Mac) must not send
        # the pointer home: typing then lands on the Mac, the MX Master bug.
        self.cross()
        for _ in range(6):
            self.mac_be.on_grabbed_move(-1, 0)
        time.sleep(0.35)
        for _ in range(5):
            self.mac_be.on_grabbed_move(-1, 0)
        self.mac_be.on_grabbed_move(3, 0)   # moved away: the push starts over
        for _ in range(5):
            self.mac_be.on_grabbed_move(-1, 0)
        time.sleep(0.3)
        self.assertEqual(self.pc.status()["mode"], "driven")
        self.assertEqual(self.mac.status()["mode"], "driving")
        self.mac_be.on_grabbed_move(-30, 0)  # a real push goes home
        self.assertTrue(wait(lambda: self.mac.status()["mode"] == "home"))

    def test_arrangement_edges(self):
        # His desk: the PC's monitor sits above the Mac, the PC's laptop to the right and lower.
        layout = [{"r": [0, 0, 1920, 1080], "at": [-240, -1080]},
                  {"r": [1920, 0, 2560, 1440], "at": [1440, 100]}]
        self.assertTrue(self.mac.set_layout(self.pc_id, layout))
        st = [p for p in self.mac.status()["peers"] if p["id"] == self.pc_id][0]
        self.assertEqual([i["at"] for i in st["layout"]], [[-240, -1080], [1440, 100]])
        self.assertTrue(wait(lambda: len(self.mac_be.targets) == 2))
        # The PC learns where the Mac sits on its side.
        self.assertTrue(wait(lambda: (self.pc._store.pair(self.mac_id) or {}).get("layout")))
        back = self.pc._store.pair(self.mac_id)["layout"]
        self.assertEqual(back[0]["r"], [0.0, 0.0, 1440.0, 900.0])
        self.assertEqual(back[0]["at"], [240, 1080])  # just under the monitor
        # Right edge above the laptop's top: nothing there, no crossing.
        self.assertFalse(self.mac_be.on_local_move(1439, 50, 5, 0))
        # Right edge beside the laptop: lands on the laptop at the same height.
        self.assertTrue(self.mac_be.on_local_move(1439, 450, 5, 0))
        self.assertTrue(wait(lambda: self.pc.status()["mode"] == "driven"))
        self.assertTrue(wait(lambda: any(p[0] == "warp" for p in self.pc_be.posted)))
        self.assertEqual([p for p in self.pc_be.posted if p[0] == "warp"][-1], ("warp", 1922.0, 350.0))
        self.mac.go_home()
        self.assertTrue(wait(lambda: self.pc.status()["mode"] == "home"))
        # Top edge, anywhere along it: lands on the bottom of the monitor, straight above.
        self.mac_be.cursor = (700, 0)
        self.assertTrue(self.mac_be.on_local_move(700, 0, 0, -5))
        self.assertTrue(wait(lambda: self.pc.status()["mode"] == "driven"))
        self.assertTrue(wait(lambda: [p for p in self.pc_be.posted if p[0] == "warp"][-1] == ("warp", 940.0, 1077.0)))
        # Coming down the monitor's bottom edge where the Mac isn't under it: stays on the PC.
        time.sleep(0.3)
        self.mac_be.on_grabbed_move(-900, 0)
        self.mac_be.on_grabbed_move(0, 60)
        time.sleep(0.3)
        self.assertEqual(self.pc.status()["mode"], "driven")
        # Above the Mac: comes home straight below.
        self.mac_be.on_grabbed_move(800, 0)
        self.mac_be.on_grabbed_move(0, 60)
        self.assertTrue(wait(lambda: self.mac.status()["mode"] == "home"))
        self.assertTrue(wait(lambda: self.mac_be.cursor == (600.0, 2.0)), self.mac_be.cursor)
        # Reset puts the whole arrangement back, centred on its side.
        self.mac.reset_layout(self.pc_id)
        st = [p for p in self.mac.status()["peers"] if p["id"] == self.pc_id][0]
        self.assertNotEqual([i["at"] for i in st["layout"]], [[-240, -1080], [1440, 100]])

    def test_sharing_hotkey_resistance_and_reverse_scroll(self):
        rs = keys.BY_NAME["rshift"]
        for _ in range(2):  # double-tap Right Shift: sharing off
            self.mac_be.on_local_key(rs, True)
            self.mac_be.on_local_key(rs, False)
        self.assertTrue(wait(lambda: self.mac._store.get("share_out") is False))
        self.assertTrue(wait(lambda: self.mac_be.share_out is False))
        self.assertFalse(self.mac_be.on_local_move(1439, 450, 5, 0))
        for _ in range(2):
            self.mac_be.on_local_key(rs, True)
            self.mac_be.on_local_key(rs, False)
        self.assertTrue(wait(lambda: self.mac_be.share_out is True))
        # Shift held for typing isn't a tap.
        self.mac_be.on_local_key(rs, True)
        self.mac_be.on_local_key(keys.BY_NAME["a"], True)
        self.mac_be.on_local_key(keys.BY_NAME["a"], False)
        self.mac_be.on_local_key(rs, False)
        self.mac_be.on_local_key(rs, True)
        self.mac_be.on_local_key(rs, False)
        time.sleep(0.2)
        self.assertTrue(self.mac._store.get("share_out"))
        # Edge resistance: 30 px of push before crossing.
        self.mac.set_setting("edge_resistance", 30)
        self.assertTrue(wait(lambda: self.mac_be.edge_resistance == 30))
        self.assertFalse(self.mac_be.on_local_move(1439, 450, 10, 0))
        self.assertFalse(self.mac_be.on_local_move(1439, 450, 10, 0))
        self.assertTrue(self.mac_be.on_local_move(1439, 450, 10, 0))
        self.assertTrue(wait(lambda: self.pc.status()["mode"] == "driven"))
        # Scrolling from the Mac, reversed on the PC.
        self.pc.set_setting("reverse_scroll", True)
        self.assertTrue(wait(lambda: self.pc_be.reverse_scroll))
        self.mac_be.on_local_wheel(0, 3)
        self.assertTrue(wait(lambda: ("wheel", 0, -3) in self.pc_be.posted), self.pc_be.posted[-5:])

    def test_refuse_incoming_and_shake_home(self):
        self.pc.set_setting("accept_in", False)
        self.assertTrue(self.mac_be.on_local_move(1439, 450, 5, 0))
        self.assertTrue(wait(lambda: not self.mac_be.grabbed))  # the PC said no: the pointer stays
        self.assertEqual(self.mac.status()["mode"], "home")
        self.assertEqual(self.pc.status()["mode"], "home")
        self.pc.set_setting("accept_in", True)
        self.mac.set_setting("shake_home", True)
        self.cross()
        for dx in (40, -40, 40, -40, 40):
            self.mac_be.on_grabbed_move(dx, 0)
        self.assertTrue(wait(lambda: self.mac.status()["mode"] == "home"))

    def test_clipboard_when_you_switch_recent_and_secrets(self):
        self.mac._store.set("clip_mode", "switch")
        self.mac_be.clip = ("text", "before")
        self.assertTrue(wait(lambda: self.mac_be._clip_last is not None))
        self.mac_be.clip = ("text", "waits for the switch")
        self.assertTrue(wait(lambda: any(c["data"] == "waits for the switch" for c in self.mac.status()["clips"])))
        time.sleep(0.6)
        self.assertNotEqual(self.pc_be.clip, ("text", "waits for the switch"))
        self.cross()
        self.assertTrue(wait(lambda: self.pc_be.clip == ("text", "waits for the switch")))
        self.assertEqual(self.pc.status()["clips"][0]["from"], self.mac._store.name)
        # A password manager's copy stays here.
        self.mac.go_home()
        self.mac._store.set("clip_mode", "instant")
        self.mac_be.clip = ("secret", "hunter2")
        time.sleep(1.0)
        self.assertNotEqual(self.pc_be.clip, ("text", "hunter2"))
        self.assertFalse(any(c["data"] == "hunter2" for c in self.mac.status()["clips"]))
        self.assertTrue(self.mac.clip_use(0))
        self.assertTrue(self.mac.clip_clear())

    def test_copy_and_paste_files_with_keys(self):
        src = os.path.join(self.tmp, "pick")
        os.makedirs(src)
        f = os.path.join(src, "photo.jpg")
        with open(f, "wb") as fh:
            fh.write(os.urandom(5000))
        self.mac_be.files_clip = [f]
        self.cross()
        self.mac.go_home()
        self.assertTrue(wait(lambda: self.mac.status()["mode"] == "home"))
        ctrl, alt, c, v = (keys.BY_NAME[k] for k in ("lctrl", "lalt", "c", "v"))
        self.mac_be.on_local_key(ctrl, True)
        self.mac_be.on_local_key(alt, True)
        self.assertTrue(self.mac_be.on_local_key(c, True))   # swallowed here
        self.assertTrue(self.mac_be.on_local_key(c, False))
        self.mac_be.on_local_key(alt, False)
        self.mac_be.on_local_key(ctrl, False)
        # The PC gets the file and has it on its clipboard, ready to paste.
        self.assertTrue(wait(lambda: self.pc_be.files_clip and os.path.basename(self.pc_be.files_clip[0]) == "photo.jpg", 10),
                        self.pc.status()["transfers"])
        with open(self.pc_be.files_clip[0], "rb") as a, open(f, "rb") as b:
            self.assertEqual(a.read(), b.read())
        # Ctrl+Alt+V while driving the PC pastes there.
        self.mac_be.on_local_move(1439, 450, 5, 0)
        self.assertTrue(wait(lambda: self.pc.status()["mode"] == "driven"))
        n = len(self.pc_be.posted)
        self.mac_be.on_local_key(ctrl, True)
        self.mac_be.on_local_key(alt, True)
        self.mac_be.on_local_key(v, True)
        self.mac_be.on_local_key(v, False)
        self.mac_be.on_local_key(alt, False)
        self.mac_be.on_local_key(ctrl, False)
        self.assertTrue(wait(lambda: ("key", v, True) in self.pc_be.posted[n:]))

    def test_wrong_code_is_refused(self):
        other = Agent(FakeBackend(), Store(os.path.join(self.tmp, "x")), port=0, discover=False).start()
        try:
            rid = other.add_address("127.0.0.1:%d" % self.pc.port)
            other.pair(rid)
            self.assertTrue(wait(lambda: (other.status()["pairing"] or {}).get("phase") == "code"))
            good = self.pc.status()["pairing"]["code"]
            other.pair_code("000000" if good != "000000" else "111111")
            self.assertTrue(wait(lambda: (other.status()["pairing"] or {}).get("phase") == "failed"))
            self.assertIsNone(self.pc._store.pair(other._store.id))
        finally:
            other.stop()

    def test_cross_type_and_come_back(self):
        self.cross()
        # Enters on the PC's left edge, halfway down the arrangement.
        warp = [p for p in self.pc_be.posted if p[0] == "warp"][-1]
        self.assertAlmostEqual(warp[1], 2.0)
        self.assertTrue(0 < warp[2] < 1440)
        # Keys: the Mac's keyboard types on the PC (this is the MX Master bug: any device that
        # crosses must take the keyboard with it).
        a = keys.BY_NAME["a"]
        self.assertTrue(self.mac_be.on_local_key(a, True))
        self.assertTrue(self.mac_be.on_local_key(a, False))
        self.assertTrue(wait(lambda: ("key", a, False) in self.pc_be.posted))
        # Command+C on the Mac arrives as Ctrl+C on Windows.
        self.mac._store.update_pair(self.pc_id, platform="mac" if this_platform() != "mac" else "windows")
        self.mac_be.on_local_key(keys.BY_NAME["lmeta"], True)
        self.assertTrue(wait(lambda: ("key", keys.BY_NAME["lctrl"], True) in self.pc_be.posted))
        self.mac_be.on_local_key(keys.BY_NAME["lmeta"], False)
        # Moves arrive; pushing back past the PC's left edge brings the pointer home.
        self.mac_be.on_grabbed_move(40, 0)
        self.assertTrue(wait(lambda: any(p[0] == "move" for p in self.pc_be.posted)))
        time.sleep(0.3)  # the edge home stays shut for a moment after crossing
        self.mac_be.on_grabbed_move(-400, 0)
        self.assertTrue(wait(lambda: self.mac.status()["mode"] == "home"))
        self.assertEqual(self.pc.status()["mode"], "home")
        self.assertFalse(self.mac_be.grabbed)
        self.assertTrue(self.mac_be.cursor[0] > 1400)  # back on the Mac's right edge

    def test_return_hotkey_and_release(self):
        self.cross()
        self.mac_be.on_local_key(keys.BY_NAME["lshift"], True)
        self.assertTrue(wait(lambda: keys.BY_NAME["lshift"] in self.pc_be.held_inj))
        for k in ("lctrl", "lalt", "esc"):
            self.mac_be.on_local_key(keys.BY_NAME[k], True)
        self.assertTrue(wait(lambda: self.pc.status()["mode"] == "home"))
        self.assertEqual(self.mac.status()["mode"], "home")
        self.assertEqual(self.pc_be.held_inj, set())  # nothing left held down on the PC

    def test_link_drop_ungrabs(self):
        self.cross()
        self.pc._peers[self.mac_id].main.close()
        self.assertTrue(wait(lambda: self.mac.status()["mode"] == "home"))
        self.assertFalse(self.mac_be.grabbed)

    def test_ctrl_alt_del_asks_windows(self):
        self.cross()
        for k in ("lctrl", "lalt"):
            self.mac_be.on_local_key(keys.BY_NAME[k], True)
        self.mac._store.set("swap_cmd_ctrl", False)
        self.mac_be.on_local_key(keys.BY_NAME["delete"], True)
        self.assertTrue(wait(lambda: ("sas",) in self.pc_be.posted))

    def test_clipboard_text_and_picture(self):
        self.mac_be.clip = ("text", "before")
        self.assertTrue(wait(lambda: self.mac_be._clip_last is not None))
        self.mac_be.clip = ("text", "hello from the mac")
        self.assertTrue(wait(lambda: self.pc_be.clip == ("text", "hello from the mac")))
        png = b"\x89PNG\r\n\x1a\n" + os.urandom(300000)
        self.pc_be.clip = ("png", png)
        self.assertTrue(wait(lambda: self.mac_be.clip == ("png", png)))
        time.sleep(1.0)  # no echo back
        self.assertEqual(self.pc_be.clip, ("png", png))

    def test_send_files(self):
        src = os.path.join(self.tmp, "src")
        os.makedirs(os.path.join(src, "folder", "sub"))
        with open(os.path.join(src, "big.bin"), "wb") as f:
            f.write(os.urandom(1500000))
        with open(os.path.join(src, "folder", "sub", "note.txt"), "w") as f:
            f.write("hi")
        open(os.path.join(src, "folder", "empty.txt"), "w").close()
        tid = self.mac.send_files(self.pc_id, [os.path.join(src, "big.bin"), os.path.join(src, "folder")])
        self.assertTrue(tid)
        self.assertTrue(wait(lambda: self.pc._transfers.get(tid, {}).get("phase") == "received", 15),
                        self.pc._transfers.get(tid))
        dest = os.path.join(self.tmp, "pchome", "Downloads", "Kvm")
        with open(os.path.join(src, "big.bin"), "rb") as a, open(os.path.join(dest, "big.bin"), "rb") as b:
            self.assertEqual(a.read(), b.read())
        self.assertTrue(os.path.isfile(os.path.join(dest, "folder", "sub", "note.txt")))
        self.assertTrue(os.path.isfile(os.path.join(dest, "folder", "empty.txt")))
        self.assertEqual(self.mac._transfers[tid]["phase"], "sent")
        # Sending again doesn't overwrite.
        tid2 = self.mac.send_files(self.pc_id, [os.path.join(src, "big.bin")])
        self.assertTrue(wait(lambda: self.pc._transfers.get(tid2, {}).get("phase") == "received", 15))
        self.assertTrue(os.path.isfile(os.path.join(dest, "big (2).bin")))

    def test_actions(self):
        self.mac.action(self.pc_id, "ring")
        self.assertTrue(wait(lambda: ("action", "ring") in self.pc_be.posted))
        self.pc._store.set("remote_actions", False)
        self.mac.action(self.pc_id, "lock")
        time.sleep(0.5)
        self.assertNotIn(("action", "lock"), self.pc_be.posted)

    def test_view_and_control_the_screen(self):
        import urllib.request
        url = self.mac.view_start(self.pc_id, fps=20)
        self.assertTrue(wait(lambda: self.mac.status()["views"][self.pc_id]["phase"] == "live"))
        self.assertTrue(wait(lambda: self.mac.status()["views"][self.pc_id]["seq"] > 0))
        self.assertEqual(self.pc.status()["watchers"][0]["id"], self.mac_id)
        v = self.mac.status()["views"][self.pc_id]
        self.assertEqual((v["w"], v["h"]), (1600, 514))  # a 4480x1440 desktop, scaled to 1600 wide
        self.assertTrue(v["control"])
        self.assertTrue(wait(lambda: self.mac._media_ok(self.pc_id) and self.pc._media_ok(self.mac_id)))
        # The picture stream serves JPEGs on 127.0.0.1 with the token, and nothing without it.
        frame = url.replace("/view/", "/frame/") + "&after=0"
        with urllib.request.urlopen(frame, timeout=5) as r:
            self.assertEqual(r.read(2), b"\xff\xd8")
        with self.assertRaises(Exception):
            urllib.request.urlopen(frame.replace("k=", "k=x"), timeout=5)
        # Click in the middle of the PC's second monitor from the viewer, and type.
        self.mac.view_input(self.pc_id, {"k": "abs", "x": 0.75, "y": 0.5})
        self.assertTrue(wait(lambda: any(e[0] == "move" and abs(e[1] - 3360) < 1 and abs(e[2] - 720) < 1
                                         for e in self.pc_be.posted)))
        self.mac.view_input(self.pc_id, {"k": "button", "b": 1, "d": True})
        self.mac.view_input(self.pc_id, {"k": "button", "b": 1, "d": False})
        self.mac.view_input(self.pc_id, {"k": "key", "code": "KeyA", "d": True})
        self.mac.view_input(self.pc_id, {"k": "key", "code": "KeyA", "d": False})
        self.assertTrue(wait(lambda: ("key", keys.BY_NAME["a"], False) in self.pc_be.posted))
        self.assertIn(("button", 1, True), self.pc_be.posted)
        # Stopping ends the pictures; turning sharing off refuses the next viewer.
        self.mac.view_stop(self.pc_id)
        self.assertTrue(wait(lambda: not self.pc.status()["watchers"]))
        self.pc._store.set("screen_share", False)
        self.mac.view_start(self.pc_id)
        self.assertTrue(wait(lambda: self.mac.status()["views"][self.pc_id]["phase"] == "refused"))

    def test_hear_the_other_computer_and_use_this_mic_there(self):
        import base64
        block = bytes(range(256)) * 15  # one 20 ms block of 16-bit stereo
        # Hear the PC on the Mac: the PC records its sound, the Mac plays it.
        self.mac.listen_start(self.pc_id)
        self.assertTrue(wait(lambda: self.mac.status()["sound"]["hear"][self.pc_id]["phase"] == "live"))
        self.assertTrue(wait(lambda: ("audio_capture", "output", True) in self.pc_be.posted))
        self.assertEqual(self.pc.status()["sound"]["listeners"][0]["id"], self.mac_id)
        self.pc._on_backend({"t": "audio", "src": "output", "pcm": base64.b64encode(block).decode()})
        self.assertTrue(wait(lambda: ("speaker", block) in self.mac_be.sound))
        # Mac's mic into the PC's virtual microphone.
        self.mac.mic_start(self.pc_id)
        self.assertTrue(wait(lambda: self.mac.status()["sound"]["mic"][self.pc_id]["phase"] == "live"))
        self.assertTrue(wait(lambda: ("audio_capture", "mic", True) in self.mac_be.posted))
        self.mac._on_backend({"t": "audio", "src": "mic", "pcm": base64.b64encode(block).decode()})
        self.assertTrue(wait(lambda: ("mic", block) in self.pc_be.sound))
        # No virtual mic on the PC: the Mac is told why and stops recording.
        self.pc._on_backend({"t": "audio_err", "sink": "mic", "why": "nocable", "error": "Install VB-CABLE."})
        self.assertTrue(wait(lambda: self.mac.status()["sound"]["mic"][self.pc_id]["phase"] == "refused"))
        self.assertIn("VB-CABLE", self.mac.status()["sound"]["mic"][self.pc_id]["error"])
        self.assertTrue(wait(lambda: ("audio_capture", "mic", False) in self.mac_be.posted))
        # Stopping and refusing.
        self.mac.listen_stop(self.pc_id)
        self.assertTrue(wait(lambda: ("audio_capture", "output", False) in self.pc_be.posted))
        self.assertTrue(wait(lambda: not self.pc.status()["sound"]["listeners"]))
        self.pc.set_setting("sound_share", False)
        self.mac.listen_start(self.pc_id)
        self.assertTrue(wait(lambda: self.mac.status()["sound"]["hear"][self.pc_id]["phase"] == "refused"))
        self.assertIn("doesn't share its sound", self.mac.status()["sound"]["hear"][self.pc_id]["error"])

    def test_extend_the_mac_onto_the_pc(self):
        self.assertTrue(wait(lambda: any(p.get("screens") for p in self.mac.status()["peers"])))
        self.mac.extend_start(self.pc_id)
        # The Mac gets an extra display the size of the PC's biggest monitor, to the right of its own.
        self.assertTrue(wait(lambda: self.mac.status()["extend"]["out"][self.pc_id]["phase"] == "live"))
        self.assertIn(("vdisplay", True), self.mac_be.posted)
        self.assertEqual(self.mac_be._vrect, (1440.0, 0.0, 2560.0, 1440.0))
        # The PC shows just that display, full size.
        self.assertTrue(wait(lambda: self.pc.status()["extend"]["in"] and self.pc.status()["extend"]["in"][0]["id"] == self.mac_id))
        self.assertTrue(wait(lambda: (self.pc.status()["views"].get(self.mac_id) or {}).get("seq", 0) > 0))
        v = self.pc.status()["views"][self.mac_id]
        self.assertEqual((v["w"], v["h"]), (2560, 1440))
        # A click in the middle of it lands in the middle of the extra display.
        self.pc.view_input(self.mac_id, {"k": "abs", "x": 0.5, "y": 0.5})
        self.assertTrue(wait(lambda: any(e[0] == "move" and abs(e[1] - 2720) < 1 and abs(e[2] - 720) < 1
                                         for e in self.mac_be.posted)))
        # It carries on through a dropped connection.
        self.mac._peers[self.pc_id].main.close()
        self.assertTrue(wait(lambda: any(p["connected"] for p in self.mac.status()["peers"] if p["id"] == self.pc_id), 15))
        seq = self.pc.status()["views"][self.mac_id]["seq"]
        self.assertTrue(wait(lambda: self.pc.status()["views"][self.mac_id]["seq"] > seq + 2, 15))
        self.assertEqual(self.mac.status()["extend"]["out"][self.pc_id]["phase"], "live")
        self.assertTrue(self.pc.status()["extend"]["in"])
        # Closing it on the PC removes the Mac's extra display.
        self.pc.extend_end(self.mac_id)
        self.assertTrue(wait(lambda: ("vdisplay", False) in self.mac_be.posted))
        self.assertTrue(wait(lambda: not self.mac.status()["extend"]["out"]))
        self.assertFalse(self.pc.status()["extend"]["in"])

    def test_use_the_other_computers_camera(self):
        import base64
        import io
        import urllib.request
        from PIL import Image
        url = self.pc.camera_start(self.mac_id)
        self.assertTrue(wait(lambda: ("camera", True) in self.mac_be.posted))
        self.assertTrue(wait(lambda: self.pc.status()["views"]["cam-" + self.mac_id]["phase"] == "live"))
        self.assertEqual(self.mac.status()["camera"]["watchers"][0]["id"], self.pc_id)
        buf = io.BytesIO()
        Image.new("RGB", (1280, 720), (200, 40, 40)).save(buf, "JPEG")
        self.mac._on_backend({"t": "camframe", "jpeg": base64.b64encode(buf.getvalue()).decode(), "w": 1280, "h": 720})
        self.assertTrue(wait(lambda: self.pc.status()["views"]["cam-" + self.mac_id]["seq"] > 0))
        with urllib.request.urlopen(url.replace("/view/", "/frame/") + "&after=0", timeout=5) as r:
            self.assertEqual(r.read(), buf.getvalue())
        # The camera can fail on the Mac (permission): the PC is told why.
        self.mac._on_backend({"t": "camera", "on": False, "error": "Allow Kvm to use the camera."})
        self.assertTrue(wait(lambda: self.pc.status()["views"]["cam-" + self.mac_id]["phase"] == "refused"))
        self.assertIn("Allow Kvm", self.pc.status()["views"]["cam-" + self.mac_id]["error"])
        self.assertTrue(wait(lambda: ("camera", False) in self.mac_be.posted))
        # Sharing off refuses.
        self.mac.set_setting("camera_share", False)
        self.pc.camera_stop(self.mac_id)
        self.pc.camera_start(self.mac_id)
        self.assertTrue(wait(lambda: self.pc.status()["views"]["cam-" + self.mac_id]["phase"] == "refused"))
        self.assertIn("doesn't share its camera", self.pc.status()["views"]["cam-" + self.mac_id]["error"])

    def test_reconnects_after_restart(self):
        self.pc.stop()
        self.assertTrue(wait(lambda: not any(p["connected"] for p in self.mac.status()["peers"])))
        port = self.pc.port
        self.pc = Agent(self.pc_be.__class__([(0, 0, 1920, 1080)]), self.pc._store, port=port, discover=False).start()
        self.assertTrue(wait(lambda: any(p["connected"] for p in self.mac.status()["peers"]), 15))


if __name__ == "__main__":
    unittest.main()
