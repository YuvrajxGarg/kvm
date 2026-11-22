import time
import unittest

from kvm.platform.base import FakeBackend


class DeskLayoutTest(unittest.TestCase):
    """Windows arranges its laptop below its monitor, but on the desk (Kvm's layout) the laptop
    sits to the right of the monitor and the Mac sits below it. Going down from the monitor
    must reach the Mac, not the laptop."""

    def setUp(self):
        self.be = FakeBackend(rects=[(0, 0, 2560, 1440), (0, 1440, 2560, 1600)])
        self.events = []
        self.be.start(self.events.append)
        self.be.handle({"c": "driven", "exits": [],
                        "map": [{"r": [0, 0, 2560, 1440], "at": [-500, -1440]},
                                {"r": [0, 1440, 2560, 1600], "at": [2060, -1200]}],
                        "home": [[0, 0, 1470, 956]], "pt": [800, 1400]})
        self.be.entered = time.time() - 1

    def test_down_from_monitor_goes_home_not_to_laptop(self):
        for _ in range(10):
            self.be.inject_move(0, 20)
            if not self.be.home:   # left for the Mac
                break
        time.sleep(0.2)
        exits = [e for e in self.events if e.get("t") == "exit"]
        self.assertTrue(exits, "pointer never left for the Mac")
        self.assertEqual(exits[0]["side"], "bottom")
        self.assertLess(self.be.pos[1], 1440)   # never went onto the laptop
        self.assertEqual(exits[0]["pt"][0], 300.0)
        # Left a little inside the edge, and it can't cross back out by itself for a moment.
        self.assertLessEqual(self.be.pos[1], 1440 - 1 - 6)
        self.assertGreater(self.be.quiet_until, time.time())

    def test_no_crossing_right_after_coming_home(self):
        be = FakeBackend(rects=[(0, 0, 2560, 1440)])
        be.start(lambda e: None)
        be.targets = [[0.0, 1440.0, 1470.0, 956.0]]   # a computer below
        be.place_at(800, 1439)
        for _ in range(4):
            self.assertFalse(be.on_local_move(800, 1439, 0, 0))
        be.quiet_until = 0
        self.assertTrue(be.on_local_move(800, 1439, 0, 5))

    def test_down_where_nothing_is_below_stays_on_monitor(self):
        self.be.place_at(2300, 1400)   # desk x 1800: past the Mac's right edge
        for _ in range(10):
            self.be.inject_move(0, 20)
        time.sleep(0.2)
        self.assertFalse([e for e in self.events if e.get("t") == "exit"])
        self.assertLess(self.be.pos[1], 1440)

    def test_right_from_monitor_reaches_laptop(self):
        self.be.place_at(2550, 700)    # desk (2050, -740): the laptop starts at desk x 2060
        self.be.inject_move(30, 0)
        time.sleep(0.2)
        self.assertGreaterEqual(self.be.pos[1], 1440)   # on the laptop, in Windows' coordinates
        self.assertFalse([e for e in self.events if e.get("t") == "exit"])


if __name__ == "__main__":
    unittest.main()
