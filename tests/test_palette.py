"""A PBColor can name an entry of the project's palette instead of a value.

`paletteIndexField` >= 0 means the color is `PBProject.paletteField`'s entry at
that index - 1 is Black, 9 is White - and its own `valueField` is empty. Build
draws the entry. Every color in the Afterburn seed is custom (index -1), so
nothing noticed until Shockwave: its On captions are palette Black, and a clone
whose value was rewritten to white still built black (docs/gdl-format.md §2).
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from _corpus import usable  # noqa: E402
from gdl.project import Project  # noqa: E402

SEED = os.path.join(os.path.dirname(HERE), 'seeds', 'Shockwave 1035.gdl')


@unittest.skipUnless(usable(SEED), 'seed not present (git lfs pull)')
class TestPaletteColors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = Project.open(SEED)

    def _by_index(self, i):
        return next(c for c in self.p.instances('PBColor') if self.p.field(c, 'paletteIndexField') == i)

    def test_a_palette_color_reads_as_its_entry(self):
        self.assertEqual(self.p.color(self._by_index(1)), {'A': 255, 'R': 0, 'G': 0, 'B': 0})
        self.assertEqual(self.p.color(self._by_index(9)), {'A': 255, 'R': 255, 'G': 255, 'B': 255})

    def test_the_transparent_entry_reads_as_none(self):
        # Mach's seed uses entry 0, 'Transparent' (alpha 0); Shockwave's none,
        # so this reads the palette entry itself.
        self.assertIsNone(self.p.palette_color(0))


class TestNamedColors(unittest.TestCase):
    """A System.Drawing.Color can be stored by name - state 1 and a KnownColor,
    its value 0 - and every seed does it: Shockwave's has 211 White and 206
    Black so, Turbulence's labels are all named White. Reading only the value
    read each as no color at all."""

    def _color(self, **value):
        p = Project.__new__(Project)
        p.o, p._palette = {}, None
        return p, {'paletteIndexField': -1,
                   'valueField': dict({'name': None, 'value': 0, 'knownColor': 0, 'state': 2}, **value)}

    def test_a_named_color_reads_as_its_value(self):
        p, white = self._color(state=1, knownColor=164)
        self.assertEqual(p.color(white), {'A': 255, 'R': 255, 'G': 255, 'B': 255})
        p, lime = self._color(state=1, knownColor=105)
        self.assertEqual(p.color(lime), {'A': 255, 'R': 0x32, 'G': 0xCD, 'B': 0x32})

    def test_transparent_and_empty_read_as_none(self):
        for value in ({'state': 1, 'knownColor': 27}, {'state': 0}):
            p, c = self._color(**value)
            self.assertIsNone(p.color(c), value)

    def test_a_value_still_reads_as_itself(self):
        p, c = self._color(value=0xFF184E80)
        self.assertEqual(p.color(c), {'A': 255, 'R': 0x18, 'G': 0x4E, 'B': 0x80})


if __name__ == '__main__':
    unittest.main()
