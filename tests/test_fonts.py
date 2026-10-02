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


class TestASystemFaceIsSaidAloud(unittest.TestCase):
    """Without the recovered faces the compositor falls back to the host's
    Arial for every one, and the render scores 2.81% instead of the baseline's
    2.19% - a checkout that skipped `python -m gdl.fonts` scored every page
    worse and nothing said so. compose records each fallback, and
    tests/score.py refuses to record over one."""

    def test_a_fallback_is_recorded(self):
        import tempfile
        from gdl import compose
        saved = compose.FONTDIR, dict(compose._cache), set(compose.FALLBACKS)
        try:
            compose.FONTDIR = tempfile.mkdtemp()
            compose._cache.clear()
            compose.FALLBACKS.clear()
            try:
                compose.face('Arial', 0, 0, 14)
            except LookupError:
                self.skipTest('no system Arial on this host either')
            self.assertEqual(compose.FALLBACKS, {"Arial as the host's arial.ttf"})
        finally:
            compose.FONTDIR = saved[0]
            compose._cache.clear()
            compose._cache.update(saved[1])
            compose.FALLBACKS.clear()
            compose.FALLBACKS.update(saved[2])

    def test_a_face_drawn_in_the_recovered_arial_is_recorded(self):
        """A partial recovery - `gdl.fonts` run over one fixture, which carries
        Arial but not every face - drew each missing face in that Arial, and
        nothing recorded it. Arial itself, drawn in Arial, is no fallback."""
        import shutil
        import tempfile
        from gdl import compose
        src = next((p for p in (os.path.join(compose.FONTDIR, 'arial.ttf'),
                                'C:/Windows/Fonts/arial.ttf', '/Library/Fonts/Arial.ttf')
                    if os.path.exists(p)), None)
        if not src:
            self.skipTest('no Arial to recover from on this host')
        saved = compose.FONTDIR, dict(compose._cache), set(compose.FALLBACKS)
        try:
            compose.FONTDIR = tempfile.mkdtemp()
            shutil.copy(src, os.path.join(compose.FONTDIR, 'arial.ttf'))
            compose._cache.clear()
            compose.FALLBACKS.clear()
            compose.face('Arial', 0, 0, 14)
            self.assertEqual(compose.FALLBACKS, set())
            compose.face('Open Sans', 0, 0, 14)
            self.assertEqual(compose.FALLBACKS, {'Open Sans as arial.ttf'})
        finally:
            compose.FONTDIR = saved[0]
            compose._cache.clear()
            compose._cache.update(saved[1])
            compose.FALLBACKS.clear()
            compose.FALLBACKS.update(saved[2])


class TestScanIsUnchanged(unittest.TestCase):
    def test_scan_still_finds_every_recovered_face(self):
        """`extract` anchors on `scan`, so an anchor for each face must exist."""
        for path in FIXTURES:
            gcp = open_gdl(path).read('ProjectGCP')
            declared, found = faces(path)
            self.assertLessEqual(len(found), len(scan(gcp)))


if __name__ == '__main__':
    unittest.main()
