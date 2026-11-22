import io
import os
import unittest

from kvm import png


class PngTest(unittest.TestCase):
    def test_round_trip_through_dib(self):
        w, h = 37, 11
        rgba = os.urandom(w * h * 4)
        data = png.encode(w, h, rgba)
        self.assertEqual(png.decode(data), (w, h, rgba))
        self.assertEqual(png.decode(png.dib_to_png(png.png_to_dib(data))), (w, h, rgba))

    def test_decodes_other_encoders(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        for mode in ("RGB", "RGBA", "L", "P", "LA"):
            im = Image.frombytes("RGBA", (23, 9), os.urandom(23 * 9 * 4)).convert(mode)
            buf = io.BytesIO()
            im.save(buf, "PNG")
            w, h, rgba = png.decode(buf.getvalue())
            self.assertEqual(rgba, im.convert("RGBA").tobytes(), mode)


if __name__ == "__main__":
    unittest.main()
