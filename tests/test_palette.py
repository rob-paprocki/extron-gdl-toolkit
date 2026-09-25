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


if __name__ == '__main__':
    unittest.main()
