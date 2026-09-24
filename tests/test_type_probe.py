"""The type probe's measuring half, on synthetic artwork."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw  # noqa: E402

import type_probe  # noqa: E402


def _png(rows):
    """A black 40x60 button with white ink on the given (top, bottom) rows."""
    im = Image.new('RGB', (40, 60), (0, 0, 0))
    d = ImageDraw.Draw(im)
    for top, bottom in rows:
        d.rectangle([5, top, 30, bottom], fill=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return buf.getvalue()


class TestCapHeight(unittest.TestCase):
    def test_measures_the_inked_rows(self):
        self.assertEqual(type_probe.cap_height(_png([(20, 39)])), 20)

    def test_no_ink_is_none_not_zero(self):
        """A caption that did not bake must not read as a 0 px measurement."""
        self.assertIsNone(type_probe.cap_height(_png([])))

    def test_antialiased_edges_count_only_when_mostly_ink(self):
        im = Image.new('RGB', (40, 60), (0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rectangle([5, 20, 30, 39], fill=(255, 255, 255))
        d.line([5, 19, 30, 19], fill=(60, 60, 60))      # faint anti-alias row
        buf = io.BytesIO()
        im.save(buf, 'PNG')
        self.assertEqual(type_probe.cap_height(buf.getvalue()), 20)


class TestProbeSpec(unittest.TestCase):
    def test_every_probe_button_meets_the_panels_touch_minimum(self):
        from gdl.spec import Panel, touch_minimums
        for model, size in (('TLP1035T', (1280, 800)), ('TLP300M', (320, 480)),
                            ('TLP1230WTG', (1920, 720))):
            spec = type_probe.probe_spec(model, size)
            self.assertEqual(Panel(spec).check(), [], model)
            target, _ = touch_minimums(model)
            for c in spec['pages'][0]['controls']:
                self.assertGreaterEqual(c['rect'][3], target, model)
                self.assertTrue(c['flatten'])


if __name__ == '__main__':
    unittest.main()
