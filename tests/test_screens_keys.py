import unittest

from kvm import keys
from kvm.screens import Screens


class ScreensTest(unittest.TestCase):
    def setUp(self):
        # A laptop (1920x1080) with a bigger monitor to its right, top-aligned.
        self.s = Screens([(0, 0, 1920, 1080), (1920, 0, 2560, 1440)])

    def test_edges(self):
        self.assertTrue(self.s.on_edge(0, 500, "left"))
        self.assertFalse(self.s.on_edge(1919, 500, "right"))   # the monitor continues there
        self.assertTrue(self.s.on_edge(4479, 500, "right"))
        self.assertTrue(self.s.on_edge(100, 1079, "bottom"))
        self.assertTrue(self.s.on_edge(3000, 1439, "bottom"))
        self.assertFalse(self.s.on_edge(3000, 1079, "bottom"))

    def test_entry_and_frac(self):
        x, y = self.s.entry("left", 0.5, inset=2)
        self.assertEqual(x, 2)
        self.assertAlmostEqual(y, 720)
        # Below the laptop, only the big monitor reaches the left at that height... it starts at 1920.
        x, y = self.s.entry("left", 0.95, inset=2)
        self.assertEqual(x, 1922)
        self.assertAlmostEqual(self.s.frac(0, 0, "left"), 0.0)
        self.assertAlmostEqual(self.s.frac(0, 1439, "left"), 1.0)

    def test_step_slides_and_exits(self):
        nx, ny, side, _ = self.s.step(100, 100, 50, 10, ["left"])
        self.assertEqual((nx, ny, side), (150, 110, None))
        nx, ny, side, _ = self.s.step(100, 1070, 0, 50, ["left"])   # slides along the bottom
        self.assertEqual(side, None)
        self.assertEqual(ny, 1079)
        _, _, side, frac = self.s.step(1, 540, -5, 0, ["left"])
        self.assertEqual(side, "left")
        self.assertAlmostEqual(frac, 540 / 1439.0, places=3)
        _, _, side, _ = self.s.step(1, 540, -5, 0, [])               # cursor lock: no way out
        self.assertIsNone(side)
        _, _, side, _ = self.s.step(4470, 300, 50, 0, ["left"])      # right edge isn't the way home
        self.assertIsNone(side)


class KeysTest(unittest.TestCase):
    def test_round_trips(self):
        for hid, (name, mac, scan, vk) in keys.KEYS.items():
            if mac is not None and name not in ("printscreen", "scrolllock", "pause", "numlock", "f13", "f14", "f15"):
                self.assertEqual(keys.from_mac(mac), hid, name)
            s, ext, _ = keys.to_win(hid)
            self.assertEqual(keys.from_win(s, ext, vk), hid, name)

    def test_combo(self):
        g = keys.parse_combo("ctrl+alt+esc")
        held = {keys.BY_NAME["rctrl"], keys.BY_NAME["lalt"], keys.BY_NAME["esc"]}
        self.assertTrue(keys.combo_down(g, held))
        self.assertFalse(keys.combo_down(g, held - {keys.BY_NAME["esc"]}))


if __name__ == "__main__":
    unittest.main()
