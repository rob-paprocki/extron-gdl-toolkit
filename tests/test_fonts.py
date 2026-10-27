"""Every face a fixture declares must come back out of it, byte for byte.

This is the gate that was missing. `extract` used to require the declared size
to equal `sfnt_length` exactly; Arial and Arial Black declare a size past their
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import MAIN_CLIENT, needs_client  # noqa: E402

from gdl.container import open_gdl, open_payload  # noqa: E402
from gdl.fonts import extract, scan  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import seed, usable  # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(
    os.path.dirname(__file__), '..', 'fixtures', 'gdl', '*.gdl')))

SFNT_MAGIC = (b'\x00\x01\x00\x00', b'OTTO', b'true', b'ttcf')


def faces(path):
    gcp = open_gdl(path).read('ProjectGCP')
    layout = json.loads(open_payload(path).read('layout.json'))
    declared = layout.get('NonDefaultFontResources') or []
    return declared, extract(gcp, declared)


@needs_client(MAIN_CLIENT)
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

    def setUp(self):
        # compose is the one module that needs Pillow, and CI's `test` job has
        # none; its `fidelity` job runs these, after recovering the faces.
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; compose draws with it')

    def test_a_fallback_is_recorded(self):
        """Nothing recovered, and no seed to read Arial from."""
        import tempfile
        from unittest import mock
        from gdl import compose
        saved = compose.FONTDIR, dict(compose._cache), set(compose.FALLBACKS)
        try:
            compose.FONTDIR = tempfile.mkdtemp()
            compose._cache.clear()
            compose.FALLBACKS.clear()
            try:
                with mock.patch.object(compose, 'seed_face', lambda font: (None, None)):
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
        from unittest import mock
        saved = compose.FONTDIR, dict(compose._cache), set(compose.FALLBACKS)
        try:
            compose.FONTDIR = tempfile.mkdtemp()
            shutil.copy(src, os.path.join(compose.FONTDIR, 'arial.ttf'))
            compose._cache.clear()
            compose.FALLBACKS.clear()
            compose.face('Arial', 0, 0, 14)
            self.assertEqual(compose.FALLBACKS, set())
            # No seed here carries it either (a public checkout without LFS).
            with mock.patch.object(compose, 'seed_face', lambda font: (None, None)):
                compose.face('Open Sans', 0, 0, 14)
            self.assertEqual(compose.FALLBACKS, {'Open Sans as arial.ttf'})
        finally:
            compose.FONTDIR = saved[0]
            compose._cache.clear()
            compose._cache.update(saved[1])
            compose.FALLBACKS.clear()
            compose.FALLBACKS.update(saved[2])


class TestAnIconFaceIsReadFromItsSeed(unittest.TestCase):
    """No fixture embeds Extron-Lift, so a Mach spec's preview drew every icon
    in the recovered Arial - and recovering the face from a Mach seed would
    replace that Arial with the seed's own. The renderer reads an icon face
    straight out of its family's seed instead, before anything stands in."""

    def test_an_icon_face_not_recovered_is_drawn_from_its_seed(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; compose draws with it')
        from gdl.seeds import usable
        if not usable('seeds/Mach 1035.gdl'):
            self.skipTest('seeds/Mach 1035.gdl is not pulled from Git LFS here')
        import tempfile
        from gdl import compose
        saved = compose.FONTDIR, dict(compose._cache), set(compose.FALLBACKS)
        try:
            compose.FONTDIR = tempfile.mkdtemp()
            compose._cache.clear()
            compose.FALLBACKS.clear()
            f = compose.face('Extron-Lift', 0, 0, 40)
            self.assertEqual(compose.FALLBACKS, set())
            self.assertEqual(f.getname()[0], 'Extron-Lift')
            # Measured off its own advance table, as a recovered face is: read
            # from memory, it measured by Pillow's whole pixels instead.
            self.assertIsNotNone(compose.advances(f))
        finally:
            compose.FONTDIR = saved[0]
            compose._cache.clear()
            compose._cache.update(saved[1])
            compose.FALLBACKS.clear()
            compose.FALLBACKS.update(saved[2])


class TestAnyFaceIsReadFromTheSeedThatCarriesIt(unittest.TestCase):
    """No fixture carries Roboto (the Shockwave Start clock), Extron GUI
    Configurator or Extron GUIC Video Conference 1a, so a spec's preview drew
    each in Arial and said so. A seed carries each: the renderer reads one
    from the first seed that does (gdl.fonts.find_face), as it reads an icon
    face from its family's - and names a stand-in only for a face no seed
    carries either."""

    def setUp(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; compose draws with it')
        import tempfile
        from gdl import compose
        saved = compose.FONTDIR, dict(compose._cache), set(compose.FALLBACKS)

        def restore():
            compose.FONTDIR = saved[0]
            compose._cache.clear()
            compose._cache.update(saved[1])
            compose.FALLBACKS.clear()
            compose.FALLBACKS.update(saved[2])
        self.addCleanup(restore)
        compose.FONTDIR = tempfile.mkdtemp()
        compose._cache.clear()
        compose.FALLBACKS.clear()
        self.compose = compose

    def test_a_face_no_fixture_carries_is_drawn_from_a_seed(self):
        from gdl.seeds import usable
        if not usable('seeds/Shockwave 1035.gdl'):
            self.skipTest('seeds/Shockwave 1035.gdl is not pulled from Git LFS here')
        for family in ('Roboto', 'Extron GUIC Video Conference 1a'):
            f = self.compose.face(family, 0, 0, 30)
            self.assertEqual(f.getname()[0], family)
            self.assertIsNotNone(self.compose.advances(f))
        self.assertEqual(self.compose.FALLBACKS, set())

    def test_a_face_no_seed_carries_is_named_as_its_stand_in(self):
        import shutil
        from unittest import mock
        src = os.path.join(self.saved_fontdir(), 'arial.ttf')
        if not os.path.exists(src):
            self.skipTest('the faces are not recovered here')
        shutil.copy(src, os.path.join(self.compose.FONTDIR, 'arial.ttf'))
        with mock.patch.object(self.compose, 'seed_face', lambda font: (None, None)):
            self.compose.face('Segoe UI', 0, 0, 14)
        self.assertEqual(self.compose.FALLBACKS, {'Segoe UI as arial.ttf'})

    def test_a_family_recovered_here_is_never_looked_for_in_a_seed(self):
        """Arial's bold has no file anywhere here, and stands in as the
        recovered Arial, as before: parsing a seed for the Arial already here
        would cost seconds for the same face."""
        import shutil
        from unittest import mock
        src = os.path.join(self.saved_fontdir(), 'arial.ttf')
        if not os.path.exists(src):
            self.skipTest('the faces are not recovered here')
        shutil.copy(src, os.path.join(self.compose.FONTDIR, 'arial.ttf'))

        def seed_face(font):
            raise AssertionError(f'looked for {font} in a seed')
        with mock.patch.object(self.compose, 'seed_face', seed_face):
            self.compose.face('Arial', 1, 0, 14)
        self.assertEqual(self.compose.FALLBACKS, {'Arial as arial.ttf'})

    @staticmethod
    def saved_fontdir():
        from gdl import fonts
        return fonts.FONTDIR


class TestASeedFace(unittest.TestCase):
    """gdl.fonts.seed_face, which needs no Pillow: an icon face from its
    family's 1035 seed, any other from the first seed that carries it."""

    def test_a_face_that_is_no_icon_face_comes_from_the_seed_that_carries_it(self):
        from gdl import fonts
        from gdl.seeds import usable
        if not usable('seeds/Mach 1035.gdl'):
            self.skipTest('seeds/Mach 1035.gdl is not pulled from Git LFS here')
        data, where = fonts.seed_face('Extron GUI Configurator')
        self.assertEqual(where, 'seeds/Mach 1035.gdl')
        self.assertIn(data[:4], SFNT_MAGIC)

    def test_a_face_no_seed_carries_is_none(self):
        from gdl import fonts
        self.assertEqual(fonts.seed_face('No Such Face'), (None, None))


class TestASmallFaceIsRecovered(unittest.TestCase):
    SEED = seed('Shockwave 1035.gdl')

    @unittest.skipUnless(usable(SEED), 'seed not present (git lfs pull)')
    def test_the_extron_shockwave_face_is_recovered(self):
        """Extron-Shockwave is 3,736 bytes, the smallest face in the corpus and
        embedded in every Shockwave seed; a scan floor above that size reported it
        declared but missing."""
        declared, found = faces(self.SEED)
        self.assertIn('extron_shockwave.ttf', {r['EmbeddedFileName'] for r in declared})
        self.assertIn('extron_shockwave.ttf', sorted(found))
        self.assertEqual(len(found['extron_shockwave.ttf']['bytes']), 3736)


class TestCarried(unittest.TestCase):
    """What a project carries is its PBFontResources' own data, not what its
    layout.json declares: the two disagree, and only the first is the face."""
    MACH = seed('Mach 1035.gdl')

    def setUp(self):
        if not usable(self.MACH):
            self.skipTest('seeds/Mach 1035.gdl is not here (git lfs pull)')

    def test_a_face_with_no_file_name_is_still_carried(self):
        """The Mach 1035 seed's Arial Black resource names no embedded file,
        and carries the face all the same - 28 bytes under its declared size,
        as Arial Black always is."""
        from gdl.fonts import carried
        black = [f for f in carried(self.MACH) if f['family'] == 'Arial Black']
        self.assertEqual(len(black), 1)
        self.assertIsNone(black[0]['file'])
        self.assertEqual(len(black[0]['bytes']), 119876)
        self.assertIn(black[0]['bytes'][:4], SFNT_MAGIC)

    def test_each_declaration_is_matched_on_its_own(self):
        """It declares arial.ttf twice, 778,580 and 1,016,724 bytes, and carries
        only the second; keyed by file name the first hid behind it."""
        from gdl.fonts import carried, match
        layout = json.loads(open_payload(self.MACH).read('layout.json'))
        declared = layout['NonDefaultFontResources']
        pairs = dict()
        for r, face in zip(declared, match(declared, carried(self.MACH))):
            pairs.setdefault(r['EmbeddedFileName'], []).append((r['Size'], face is not None))
        self.assertEqual(sorted(pairs['arial.ttf']), [(778580, False), (1016724, True)])
        self.assertEqual(pairs['ariblk.ttf'], [(119904, True)])

    def test_what_is_carried_is_what_extract_recovers(self):
        """Two readings of one project: the resource's own bytes, and the sfnt
        found in the stream at the declared size. Wherever both answer, they
        are the same face; extract's is the declared length, its last bytes the
        stream's next records."""
        from gdl.fonts import carried, match
        declared, found = faces(self.MACH)
        compared = 0
        for r, face in zip(declared, match(declared, carried(self.MACH))):
            got = found.get(r['EmbeddedFileName'])
            if face is None or got is None or len(got['bytes']) != r['Size']:
                continue
            self.assertEqual(got['bytes'][:len(face['bytes'])], face['bytes'], r['EmbeddedFileName'])
            compared += 1
        # Every declaration but the twice-declared Arial's first is read both ways.
        self.assertEqual(compared, len(declared) - 1)


class TestTheCommandLineSaysBothWays(unittest.TestCase):
    TURB = seed('Turbulence 1035.gdl')

    def test_a_face_carried_under_no_declaration_is_named(self):
        """Turbulence declares the Monotype arial.ttf, 778,580 bytes, and
        carries a Windows Arial under a resource with no file name: neither
        side of that is silent."""
        if not usable(self.TURB):
            self.skipTest('seeds/Turbulence 1035.gdl is not here (git lfs pull)')
        import contextlib
        import io
        from gdl import fonts
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            fonts.main(['fonts', self.TURB])
        said = out.getvalue()
        # It defines no Arial Black resource either, so that line names both.
        self.assertRegex(said, r'DECLARED, NOT CARRIED: .*arial\.ttf \(778,580 B\)')
        self.assertRegex(said, r'CARRIED, NOT DECLARED: .*Arial Regular \(1,016,724 B\)')


class TestTheCommandLineWithNothingToRead(unittest.TestCase):
    def test_it_says_how_to_call_it(self):
        """No project named: the usage line and exit 2, not a traceback - and
        not read off a docstring, which `python -OO` strips."""
        import contextlib
        import io
        from gdl import fonts
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = fonts.main(['fonts'])
        self.assertEqual(rc, 2)
        self.assertIn('python -m gdl.fonts <project.gdl or template.glt>', out.getvalue())


class TestATemplatesFaces(unittest.TestCase):
    """A .glt has no layout.json, so nothing declares its faces; it carries them."""

    def setUp(self):
        from _corpus import template
        self.glt = template('Afterburn 1020 Series.glt')
        if not usable(self.glt):
            self.skipTest('no installed templates and vendor/ empty')

    def test_a_template_carries_its_faces(self):
        from gdl.fonts import carried
        families = {f['family'] for f in carried(self.glt)}
        self.assertIn('Open Sans', families)
        self.assertIn('Extron-Afterburn', families)

    def test_the_command_line_recovers_them(self):
        import contextlib
        import io
        import tempfile
        from gdl import fonts
        with tempfile.TemporaryDirectory() as out:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = fonts.main(['fonts', self.glt, out])
            self.assertEqual(rc, 0)
            names = sorted(os.listdir(out))
            self.assertIn('opensans-regular.ttf', names)
            with open(os.path.join(out, 'opensans-regular.ttf'), 'rb') as fh:
                self.assertIn(fh.read(4), SFNT_MAGIC)

    def test_the_system_faces_keep_gui_designers_names(self):
        """A template's Arial and Arial Black resources name no file; a built
        project declares them arial.ttf and ariblk.ttf, which is what the
        renderer looks them up by."""
        import contextlib
        import io
        import tempfile
        from _corpus import template
        from gdl import fonts
        glt = template('Shockwave 1020 Series.glt')
        if not usable(glt):
            self.skipTest('no Shockwave 1020 template here')
        with tempfile.TemporaryDirectory() as out:
            with contextlib.redirect_stdout(io.StringIO()):
                fonts.main(['fonts', glt, out])
            names = set(os.listdir(out))
        self.assertTrue({'arial.ttf', 'ariblk.ttf'} <= names, sorted(names))


class TestTheSeedCIHas(unittest.TestCase):
    """seeds/Afterburn 1035.gdl is the one seed CI pulls, so what is carried
    and what is declared is pinned on it too, not only on the seeds a full
    checkout has. It declares Arial Black and carries no resource for it, and
    carries its Arial under a resource that names no file."""
    SEED = seed('Afterburn 1035.gdl')

    def setUp(self):
        if not usable(self.SEED):
            self.skipTest('seeds/Afterburn 1035.gdl is not here (git lfs pull)')

    def _declared(self):
        layout = json.loads(open_payload(self.SEED).read('layout.json'))
        return [r for r in layout['NonDefaultFontResources'] if r.get('EmbeddedFileName')]

    def test_its_arial_is_carried_under_no_file_name(self):
        from gdl.fonts import carried
        arial = [f for f in carried(self.SEED) if f['family'] == 'Arial']
        self.assertEqual(len(arial), 1)
        self.assertFalse(arial[0]['file'])
        # 28 bytes under the 778,580 its layout.json declares, as Arial always is.
        self.assertEqual(len(arial[0]['bytes']), 778552)

    def test_the_stream_counts_the_faces_carried_without_a_parse(self):
        """What lets the command skip the parse: read off the stream's own byte
        arrays, the faces are carried()'s, length for length."""
        from gdl.fonts import _face_arrays, carried
        arrays = _face_arrays(open_gdl(self.SEED).read('ProjectGCP'))
        self.assertEqual(sorted(arrays.values()),
                         sorted(len(f['bytes']) for f in carried(self.SEED)))

    def test_a_path_object_is_a_path(self):
        import pathlib
        from gdl.fonts import carried
        self.assertEqual(len(carried(pathlib.Path(self.SEED))), len(carried(self.SEED)))

    def test_only_arial_black_is_declared_and_not_carried(self):
        from gdl.fonts import carried, match
        declared = self._declared()
        pairs = match(declared, carried(self.SEED))
        self.assertEqual([r['EmbeddedFileName'] for r, f in zip(declared, pairs) if f is None],
                         ['ariblk.ttf'])

    def test_each_declaration_is_found_or_not_on_its_own(self):
        from gdl.fonts import extract_each
        declared = self._declared()
        each = extract_each(open_gdl(self.SEED).read('ProjectGCP'), declared)
        self.assertEqual(len(each), len(declared))
        self.assertEqual([r['EmbeddedFileName'] for r, d in zip(declared, each) if d is None],
                         ['ariblk.ttf'])
        for r, d in zip(declared, each):
            if d is not None:
                self.assertEqual(len(d), r['Size'], r['EmbeddedFileName'])

    def test_the_command_line_says_what_is_not_carried(self):
        import contextlib
        import io
        from gdl import fonts
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = fonts.main(['fonts', self.SEED])
        self.assertEqual(rc, 0)
        self.assertIn('DECLARED, NOT CARRIED: ariblk.ttf (119,904 B)', out.getvalue())
        self.assertNotIn('CARRIED, NOT DECLARED', out.getvalue())

    def test_a_face_the_scan_misses_comes_from_its_resource_and_is_said(self):
        """A face declared and carried that the stream scan cannot find - one
        under scan()'s floor, say - was neither written nor named."""
        import contextlib
        import io
        import tempfile
        from unittest import mock
        from gdl import fonts
        real = fonts._locate

        def blind(gcp, resources):
            return [None if r.get('EmbeddedFileName') == 'opensans-regular.ttf' else off
                    for r, off in zip(resources, real(gcp, resources))]

        out = io.StringIO()
        with tempfile.TemporaryDirectory() as dest:
            with mock.patch.object(fonts, '_locate', blind), contextlib.redirect_stdout(out):
                rc = fonts.main(['fonts', self.SEED, dest])
            with open(os.path.join(dest, 'opensans-regular.ttf'), 'rb') as fh:
                written = fh.read()
        self.assertEqual(rc, 0)
        self.assertRegex(out.getvalue(), r'opensans-regular\.ttf - from its resource')
        self.assertIn(written[:4], SFNT_MAGIC)
        self.assertEqual(len(written), 217360)


@needs_client(MAIN_CLIENT)
class TestNothingToSayNeedsNoParse(unittest.TestCase):
    def test_a_project_that_carries_all_it_declares_is_not_parsed(self):
        """Every fixture declares what it carries and carries what it declares,
        and the stream scan says so on its own: parsing the whole project to
        say nothing made the command 20 times slower over them."""
        import contextlib
        import io
        from unittest import mock
        from _corpus import client
        from gdl import fonts

        def parse(*a, **k):
            raise AssertionError('parsed the whole project')

        with mock.patch.object(fonts, 'carried', parse), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fonts.main(['fonts', client(MAIN_CLIENT)]), 0)


class TestWhereAFaceIsRecovered(unittest.TestCase):
    """The file each family is recovered as: one table, which the renderer
    draws from and a spec's icons read their glyph names from - so it is here,
    where it needs no Pillow."""

    def _found(self, family, *files):
        import tempfile
        from gdl import fonts
        d = tempfile.mkdtemp()
        for f in files:
            open(os.path.join(d, f), 'wb').close()
        got = fonts.face_path(family, fontdir=d)
        return got and os.path.basename(got)

    def test_an_icon_face_is_found_as_its_seeds_embed_it(self):
        self.assertEqual(self._found('Extron-Afterburn', 'afterburn_modified.ttf'), 'afterburn_modified.ttf')
        self.assertEqual(self._found('Extron-Lift', 'extron-lift_8.ttf'), 'extron-lift_8.ttf')
        self.assertEqual(self._found('Extron-Shockwave', 'extron_shockwave.ttf'), 'extron_shockwave.ttf')

    def test_a_face_is_found_under_another_name_it_is_embedded_as(self):
        """The client fixtures embed Extron-Afterburn as
        extron_-_afterburn_1a.ttf, and the Afterburn 320 seed as afterburn.ttf."""
        self.assertEqual(self._found('Extron-Afterburn', 'extron_-_afterburn_1a.ttf'), 'extron_-_afterburn_1a.ttf')
        self.assertEqual(self._found('Extron-Afterburn', 'afterburn.ttf'), 'afterburn.ttf')

    def test_a_face_not_recovered_is_none(self):
        self.assertIsNone(self._found('Extron-Lift'))
        self.assertIsNone(self._found('No Such Face', 'arial.ttf'))

    def test_the_renderer_draws_from_the_same_table(self):
        try:
            from gdl import compose
        except ImportError:
            self.skipTest('Pillow not installed; compose draws with it')
        from gdl import fonts
        self.assertIs(compose.FILES, fonts.FILES)
        self.assertIs(compose.ALIASES, fonts.ALIASES)


class TestScanIsUnchanged(unittest.TestCase):
    def test_scan_still_finds_every_recovered_face(self):
        """`extract` anchors on `scan`, so an anchor for each face must exist."""
        for path in FIXTURES:
            gcp = open_gdl(path).read('ProjectGCP')
            declared, found = faces(path)
            self.assertLessEqual(len(found), len(scan(gcp)))


if __name__ == '__main__':
    unittest.main()
