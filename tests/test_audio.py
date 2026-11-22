"""kvm/audio.py with a stand-in sound library: recording, playback, the virtual microphone."""

import base64
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

from kvm import audio


def wait(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


class FakeDev(object):
    def __init__(self, lib, name):
        self.lib, self.name = lib, name

    def recorder(self, samplerate, channels=None, blocksize=None):
        self.lib.opened.append(("rec", self.name, samplerate, channels))
        return FakeRec(channels)

    def player(self, samplerate, channels=None, blocksize=None):
        self.lib.opened.append(("play", self.name, samplerate, channels))
        return FakePlayer(self.lib, self.name)


class FakeRec(object):
    def __init__(self, ch):
        self.ch = ch
        self.n = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def record(self, numframes):
        time.sleep(0.005)
        self.n += 1
        if self.n % 2:
            return np.zeros((numframes, self.ch), dtype=np.float32)  # silence: not sent
        return np.full((numframes, self.ch), 0.5, dtype=np.float32)


class FakePlayer(object):
    def __init__(self, lib, name):
        self.lib, self.name = lib, name

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def play(self, data):
        self.lib.played.append((self.name, data.shape))


class FakeLib(object):
    def __init__(self, speakers=("Speakers",)):
        self.opened, self.played = [], []
        self.speakers = [FakeDev(self, n) for n in speakers]

    def default_speaker(self):
        return self.speakers[0]

    def all_speakers(self):
        return self.speakers

    def default_microphone(self):
        return FakeDev(self, "Mic")

    def get_microphone(self, id, include_loopback=False):
        return FakeDev(self, "loopback:" + id)


@unittest.skipIf(np is None, "numpy not installed")
class AudioTest(unittest.TestCase):
    def setUp(self):
        self._old = audio._sc_mod
        self.events = []
        self.lock = threading.Lock()

    def tearDown(self):
        audio._sc_mod = self._old

    def sink(self, ev):
        with self.lock:
            self.events.append(ev)

    def test_pcm_round_trip(self):
        f = np.array([[0.5, -0.5], [1.5, -1.5]], dtype=np.float32)
        pcm = audio.to_pcm(f)
        self.assertEqual(len(pcm), 8)
        back = audio.from_pcm(pcm)
        self.assertAlmostEqual(float(back[0, 0]), 0.5, places=3)
        self.assertAlmostEqual(float(back[1, 1]), -1.0, places=3)  # clipped
        self.assertEqual(len(audio.to_pcm(np.zeros((audio.BLOCK, 1), dtype=np.float32))), audio.BLOCK_BYTES)  # mono -> stereo
        self.assertTrue(audio.is_silent(b"\0" * 16))

    def test_virtual_mic_by_name(self):
        lib = FakeLib(("Speakers (Realtek)", "CABLE Input (VB-Audio Virtual Cable)"))
        self.assertEqual(audio.find_virtual_mic(lib.all_speakers()).name, "CABLE Input (VB-Audio Virtual Cable)")
        self.assertEqual(audio.find_virtual_mic(FakeLib(("MacBook Speakers", "BlackHole 2ch")).all_speakers()).name,
                         "BlackHole 2ch")
        self.assertIsNone(audio.find_virtual_mic(FakeLib(("Speakers",)).all_speakers()))

    @unittest.skipIf(sys.platform == "darwin", "the Mac records its own sound with kvm-audiotap")
    def test_record_output_and_mic(self):
        lib = audio._sc_mod = FakeLib()
        a = audio.Audio(self.sink)
        a.capture("output", True)
        a.capture("mic", True)
        self.assertTrue(wait(lambda: {e.get("src") for e in list(self.events)} >= {"output", "mic"}))
        a.stop()
        ev = [e for e in self.events if e["t"] == "audio"][0]
        self.assertEqual(len(base64.b64decode(ev["pcm"])), audio.BLOCK_BYTES)
        self.assertIn(("rec", "loopback:Speakers", 48000, 2), lib.opened)
        self.assertIn(("rec", "Mic", 48000, 1), lib.opened)

    def test_play_and_missing_virtual_mic(self):
        lib = audio._sc_mod = FakeLib()
        a = audio.Audio(self.sink)
        block = audio.to_pcm(np.full((audio.BLOCK, 2), 0.25, dtype=np.float32))
        for _ in range(4):
            a.play("speaker", block)
        self.assertTrue(wait(lambda: lib.played))
        self.assertEqual(lib.played[0][0], "Speakers")
        a.play("mic", block)
        self.assertTrue(wait(lambda: any(e.get("why") == "nocable" for e in self.events)))
        a.stop()


if __name__ == "__main__":
    unittest.main()
