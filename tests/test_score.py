"""The render harness refuses snapshots that are not of the .gdl it is given.

Snapshots were matched to pages by number alone, and refused only when more
than half matched nothing. The TLP1035-1.1.0 fixture matched 14 of the 27
`_alt 2_0_0` snapshots - two of them pages since renamed - and scored 5.86%, a
figure that stood in the ROADMAP for a month as an unexplained render residual.
A snapshot's file is named for its page, so the name is checked too.
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import MAIN_CLIENT, needs_client  # noqa: E402
sys.path.insert(0, os.path.dirname(HERE))

FIXTURE = os.path.join(os.path.dirname(HERE), 'fixtures', 'gdl',
                       'client-boardroom-2.0.0.gdl')
SNAPS = os.path.join(os.path.dirname(HERE), 'fixtures', 'snapshots', 'Individual')
HOME = '1000 - Home_Id21.png'


@needs_client(MAIN_CLIENT)
class TestTheWrongFixtureIsRefused(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; the harness renders with it')
        import score
        self.score = score
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_a_snapshot_of_a_page_by_another_name_is_refused(self):
        shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, '1000 - Lobby_Id21.png'))
        with self.assertRaises(SystemExit) as e:
            self.score.record(FIXTURE, self.dir)
        self.assertIn('1000 - Lobby', str(e.exception))

    def test_the_snapshots_own_fixture_is_scored(self):
        shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, HOME))
        self.assertEqual(list(self.score.record(FIXTURE, self.dir)), [HOME])

    def test_the_per_page_harness_refuses_it_too_and_counts_every_snapshot(self):
        """compare_snapshots.py left a renamed snapshot out of both counts, so
        the 1.1.0 fixture was refused as '13 of 25' missing - of 27 files -
        before the names were ever compared. One page scored, one renamed and
        two that match nothing is the same mix, smaller."""
        import subprocess
        shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, HOME))
        shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, '1000 - Lobby_Id21.png'))
        for n in (9998, 9999):
            shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, f'Gone_Id{n}.png'))
        r = subprocess.run([sys.executable, os.path.join(HERE, 'compare_snapshots.py'), FIXTURE, self.dir],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('1000 - Lobby', r.stdout)
        self.assertNotIn(' of 3 ', r.stdout)


class TestAFaceReadFromASeedIsNotScored(unittest.TestCase):
    """The render baseline is scored in the faces the fixture embeds,
    recovered into gdl/fonts/. A face with no file there is read from a seed
    that carries it (gdl.fonts.seed_face), which is right for a preview and
    wrong for the score: Arial Black comes out of seeds/Afterburn 1035
    Portrait.gdl as Windows', not the Monotype 5.06 the fixtures embed, so the
    score would depend on which seeds are pulled. It is named
    (compose.FROM_SEED), and score.py records over it no more than over a
    stand-in."""

    def setUp(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; the harness renders with it')
        from gdl import compose, fonts
        if not os.path.exists(os.path.join(fonts.FONTDIR, 'ariblk.ttf')):
            self.skipTest('the faces are not recovered here')
        saved = compose.FONTDIR, dict(compose._cache), set(compose.FALLBACKS), set(compose.FROM_SEED)

        def restore():
            compose.FONTDIR = saved[0]
            compose._cache.clear()
            compose._cache.update(saved[1])
            for live, was in ((compose.FALLBACKS, saved[2]), (compose.FROM_SEED, saved[3])):
                live.clear()
                live.update(was)
        self.addCleanup(restore)
        # Every recovered face but Arial Black and Open Sans.
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        for fn in os.listdir(fonts.FONTDIR):
            if fn != 'ariblk.ttf' and not fn.startswith('opensans') and \
                    os.path.isfile(os.path.join(fonts.FONTDIR, fn)):
                shutil.copy(os.path.join(fonts.FONTDIR, fn), d)
        compose.FONTDIR = d
        compose._cache.clear()
        compose.FALLBACKS.clear()
        compose.FROM_SEED.clear()
        self.compose = compose

    def _draw(self):
        for family in ('Arial Black', 'Open Sans'):
            self.compose.face(family, 0, 0, 14 * self.compose.PT)

    def test_a_face_with_no_file_here_is_said_wherever_it_is_drawn_from(self):
        from gdl.seeds import usable
        self._draw()
        said = sorted(self.compose.FROM_SEED | self.compose.FALLBACKS)
        self.assertEqual([s.split(' ')[0] for s in said], ['Arial', 'Open'], said)
        if usable('seeds/Afterburn 1035 Portrait.gdl'):
            self.assertIn('Arial Black from seeds/Afterburn 1035 Portrait.gdl', self.compose.FROM_SEED)

    def test_record_writes_nothing_scored_on_one(self):
        import contextlib
        import io
        from unittest import mock
        import score
        out = os.path.join(tempfile.mkdtemp(), 'after.json')
        self.addCleanup(shutil.rmtree, os.path.dirname(out), True)

        def record(gdl, snaps):
            self._draw()
            return {HOME: 1.0}
        buf = io.StringIO()
        with mock.patch.object(score, 'record', record), \
                mock.patch.object(sys, 'argv', ['score.py', 'record', 'x.gdl', 'snaps', '-o', out]), \
                contextlib.redirect_stdout(buf):
            code = score.main()
        self.assertEqual(code, 2, buf.getvalue())
        self.assertFalse(os.path.exists(out))
        self.assertIn('Arial Black', buf.getvalue())
        self.assertIn('nothing written', buf.getvalue())


# Three controls on a fully synthetic Afterburn 320 page - fills, a stroke, and
# borders the donor builds as its nearest resource - and the panel built from
# them on 1.28.0.7.
PROBE = os.path.join(os.path.dirname(HERE), 'archive', 'job-2419a20b', 'borders')


class TestThePreviewAgainstItsBuild(unittest.TestCase):
    """The spec preview is measured against what Build made of the spec: each
    page drawn by gdl.spec beside the same page drawn from the built file's own
    artwork (docs/from-scratch.md section 6)."""

    def setUp(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; the harness renders with it')
        from _corpus import usable
        if not usable(os.path.join(PROBE, 'Borders320.gdl')):
            self.skipTest('archive/job-2419a20b/borders is not pulled from Git LFS here')
        import score
        self.score = score

    def test_each_page_is_scored_against_its_build(self):
        rows = self.score.preview(os.path.join(PROBE, 'ab320.json'), os.path.join(PROBE, 'Borders320.gdl'))
        self.assertEqual([(r[0], r[1]) for r in rows], [('Home', 'page')])
        name, kind, pct, rest = rows[0]
        # Measured 0.20%: the borders' corners, built as the donor's nearest.
        self.assertLess(pct, 1.0)
        self.assertEqual(rest, pct)          # no level or slider to set aside

    def test_both_sides_are_drawn_in_the_built_files_faces(self):
        """The panel draws its captions at runtime, in the faces the built file
        embeds. The preview alone knows no donor and draws a seed's Roboto Thin
        where a 320's embeds Light, and the recovered Monotype Arial where a
        Mach build embeds Windows': scored so, that difference would be
        counted against the preview's art. Its side is drawn in the built
        file's faces too."""
        from unittest import mock
        from gdl import compose
        from gdl.spec import Panel
        built = os.path.join(PROBE, 'Borders320.gdl')
        render, seen = Panel.render, []

        def spy(panel, page=0):
            seen.append(compose._carried_tag)
            return render(panel, page)
        with mock.patch.object(Panel, 'render', spy):
            self.score.preview(os.path.join(PROBE, 'ab320.json'), built)
        self.assertEqual(seen, [compose._project_key(built)])

    def test_a_page_the_build_lacks_is_said(self):
        import json
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(PROBE, 'ab320.json'), encoding='utf-8') as fh:
            spec = json.load(fh)
        spec['pages'].append({'name': 'Lobby', 'number': 1001, 'controls': []})
        path = os.path.join(d, 'spec.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(spec, fh)
        rows = self.score.preview(path, os.path.join(PROBE, 'Borders320.gdl'))
        self.assertEqual(rows[1], ('Lobby', 'page', None, None))

    def test_the_command_line_prints_each_page_and_the_figure(self):
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(HERE, 'score.py'), 'preview',
                            os.path.join(PROBE, 'ab320.json'), os.path.join(PROBE, 'Borders320.gdl')],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r'page\s+Home\s+0\.\d\d%')
        self.assertIn('1 page(s) and popup(s)', r.stdout)


if __name__ == '__main__':
    unittest.main()
