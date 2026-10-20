"""gdl.sfnt reads a font's own tables. These pin what a spec's icons stand on:
an icon font's glyph names.

The rules run on a face built here, so they need no font at all; what
Extron-Afterburn itself names runs wherever the face is - recovered into
gdl/fonts/, or in seeds/Afterburn 1035.gdl.

    python tests/test_sfnt.py
"""
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from gdl.sfnt import Advances  # noqa: E402


def face(glyphs, post=2):
    """A minimal TrueType face, as bytes: glyph 0, then one glyph per
    (codepoint, name) - a name of None takes the Mac standard set's 'space',
    index 3 - mapped by a format 4 cmap and named by a `post` table of the
    version given."""
    n = 1 + len(glyphs)
    head = bytearray(54)
    head[18:20] = struct.pack('>H', 1000)
    hhea = bytearray(36)
    hhea[4:8] = struct.pack('>hh', 800, -200)
    hhea[34:36] = struct.pack('>H', n)
    hmtx = struct.pack(f'>{2 * n}H', *([500, 0] * n))
    pairs = sorted((cp, gid) for gid, (cp, _) in enumerate(glyphs, 1))
    seg = len(pairs) + 1
    ends = [cp for cp, _ in pairs] + [0xFFFF]
    deltas = [(gid - cp) & 0xFFFF for cp, gid in pairs] + [1]
    body = (struct.pack(f'>{seg}H', *ends) + b'\0\0' + struct.pack(f'>{seg}H', *ends)
            + struct.pack(f'>{seg}H', *deltas) + bytes(2 * seg))
    sub = struct.pack('>7H', 4, 14 + len(body), 0, 2 * seg, 0, 0, 0) + body
    cmap = struct.pack('>HHHHI', 0, 1, 3, 1, 12) + sub
    if post == 2:
        index, own = [0], []
        for _, name in glyphs:
            index.append(3 if name is None else 258 + len(own))
            if name is not None:
                own.append(name)
        names = b''.join(bytes([len(s)]) + s.encode('latin-1') for s in own)
        post_t = struct.pack('>I', 0x00020000) + bytes(28) + struct.pack(f'>{n + 1}H', n, *index) + names
    else:
        post_t = struct.pack('>I', post << 16) + bytes(28)
    tables = sorted({b'cmap': cmap, b'head': bytes(head), b'hhea': bytes(hhea),
                     b'hmtx': hmtx, b'post': post_t}.items())
    out, data = struct.pack('>IHHHH', 0x00010000, len(tables), 0, 0, 0), b''
    for tag, t in tables:
        out += struct.pack('>4sIII', tag, 0, 12 + 16 * len(tables) + len(data), len(t))
        data += t + bytes(-len(t) % 4)
    return out + data


class TestGlyphNameRules(unittest.TestCase):

    def test_a_glyph_is_named_by_the_codepoint_that_draws_it(self):
        names = Advances(face([(0xE908, 'cable_tv'), (0xE907, 'bluray')])).glyph_names()
        self.assertEqual(names, {'cable_tv': 0xE908, 'bluray': 0xE907})

    def test_a_mac_standard_name_names_no_icon(self):
        names = Advances(face([(0x20, None), (0xE926, 'home')])).glyph_names()
        self.assertEqual(names, {'home': 0xE926})

    def test_an_empty_name_is_no_name(self):
        """The Extron GUIC Video Conference 1 the Turbulence seed carries names
        one glyph ''."""
        names = Advances(face([(0xF021, ''), (0xF023, 'Pound')])).glyph_names()
        self.assertEqual(names, {'Pound': 0xF023})

    def test_a_control_character_is_not_an_icon(self):
        """Extron-Afterburn names U+0000 'null' and U+0001 'start_of_heading'."""
        names = Advances(face([(0x01, 'start_of_heading'), (0xE926, 'home')])).glyph_names()
        self.assertEqual(names, {'home': 0xE926})

    def test_a_face_that_names_nothing(self):
        """post version 3, as the Extron-Lift a Mach seed carries and
        Extron-Shockwave."""
        self.assertEqual(Advances(face([(0xE900, None)], post=3)).glyph_names(), {})


class TestExtronAfterburn(unittest.TestCase):
    """Extron-Afterburn names its icons; the other Extron icon faces in the
    seeds name theirs uniE900, or not at all."""

    def setUp(self):
        from gdl.fonts import icon_face
        self.face = icon_face('Extron-Afterburn')[0]
        if not self.face:
            self.skipTest('no Extron-Afterburn here: neither recovered into gdl/fonts/ '
                          'nor in seeds/Afterburn 1035.gdl')

    def test_its_icons_are_named(self):
        names = Advances(self.face).glyph_names()
        self.assertEqual(names['cable_tv'], 0xE908)
        self.assertEqual(names['bluray'], 0xE907)
        self.assertEqual(names['home'], 0xE926)

    def test_every_name_is_an_icon(self):
        names = Advances(self.face).glyph_names()
        self.assertTrue(all(0xE000 <= cp <= 0xF8FF for cp in names.values()), names)


if __name__ == '__main__':
    unittest.main()
