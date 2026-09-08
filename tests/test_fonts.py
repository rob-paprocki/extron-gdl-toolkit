"""Every face a project declares must come back out of it, byte for byte.

This is the gate that was missing. `extract` used to require the declared size
to equal `sfnt_length` exactly; Arial and Arial Black carry bytes past their
last table, so they never matched and were written off as system faces that
GUI Designer referenced without embedding. That inference reached the docs, the
CI config and the render path, where it became a hard `LookupError` on any host
without Arial installed. Nothing failed, because nothing checked.
"""
import glob
import json
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.container import open_gdl, open_payload  # noqa: E402
from gdl.fonts import extract, scan  # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(
    os.path.dirname(__file__), '..', 'fixtures', 'gdl', '*.gdl')))

SFNT_MAGIC = (b'\x00\x01\x00\x00', b'OTTO', b'true', b'ttcf')


def faces(path):
    gcp = open_gdl(path).read('ProjectGCP')
    layout = json.loads(open_payload(path).read('layout.json'))
    declared = layout.get('NonDefaultFontResources') or []
    return declared, extract(gcp, declared)


class TestEveryDeclaredFaceIsRecovered(unittest.TestCase):
    def test_fixtures_exist(self):
        self.assertTrue(FIXTURES, 'no fixtures found to check')

    def test_nothing_is_declared_but_missing(self):
        for path in FIXTURES:
            declared, found = faces(path)
            missing = [r['EmbeddedFileName'] for r in declared
                       if r['EmbeddedFileName'] not in found]
            self.assertEqual(missing, [], f'{os.path.basename(path)} declares '
                                          f'{missing} but extract() lost them')

    def test_arial_is_embedded_not_a_system_face(self):
        """The specific claim that was wrong, pinned so it cannot come back."""
        for path in FIXTURES:
            _, found = faces(path)
            self.assertIn('arial.ttf', found, os.path.basename(path))
            self.assertIn('ariblk.ttf', found, os.path.basename(path))

    def test_recovered_bytes_are_the_declared_length_and_a_real_sfnt(self):
        for path in FIXTURES:
            declared, found = faces(path)
            sizes = {r['EmbeddedFileName']: r['Size'] for r in declared}
            for name, face in found.items():
                blob = face['bytes']
                self.assertEqual(len(blob), sizes[name], f'{name} in {path}')
                self.assertIn(blob[:4], SFNT_MAGIC, f'{name} is not an sfnt')

    def test_the_table_directory_fits_inside_the_recovered_bytes(self):
        """A short slice would still start with the magic but truncate a table."""
        for path in FIXTURES:
            _, found = faces(path)
            for name, face in found.items():
                blob = face['bytes']
                num = struct.unpack('>H', blob[4:6])[0]
                for i in range(num):
                    rec = 12 + i * 16
                    off, ln = struct.unpack('>II', blob[rec + 8:rec + 16])
                    self.assertLessEqual(off + ln, len(blob),
                                         f'{name} table {i} runs past the end')

    def test_two_faces_never_resolve_to_the_same_blob(self):
        for path in FIXTURES:
            _, found = faces(path)
            starts = [face['bytes'][:64] for face in found.values()]
            self.assertEqual(len(starts), len({bytes(s) for s in starts}),
                             f'{os.path.basename(path)} mapped two names to one face')


class TestScanIsUnchanged(unittest.TestCase):
    def test_scan_still_finds_every_recovered_face(self):
        """`extract` anchors on `scan`, so an anchor for each face must exist."""
        for path in FIXTURES:
            gcp = open_gdl(path).read('ProjectGCP')
            declared, found = faces(path)
            self.assertLessEqual(len(found), len(scan(gcp)))


if __name__ == '__main__':
    unittest.main()
