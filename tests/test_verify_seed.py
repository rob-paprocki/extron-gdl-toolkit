"""A seed is a themed project for the model it claims - never a Blank one."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import verify_seed  # noqa: E402
from gdl import templates  # noqa: E402

SEEDS = os.path.join(os.path.dirname(HERE), 'seeds')
try:
    TABLE = templates.table()
except Exception:  # noqa: BLE001 - one unreadable table must not stop the session
    TABLE = []


def _seed(name):
    path = os.path.join(SEEDS, name)
    if not os.path.exists(path) or os.path.getsize(path) < 1024:
        raise unittest.SkipTest(f'{name} is not pulled from Git LFS here')
    return path


class TestVerifySeed(unittest.TestCase):
    def test_a_real_seed_passes(self):
        self.assertEqual(verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP1035T'), [])

    def test_a_small_panels_themed_seed_passes(self):
        """The 320M's themed project is twelve single-purpose pages of 86
        controls - a floor of 100, set on the bigger panels, called it Blank."""
        seed = _seed('Afterburn 320.gdl')
        self.assertEqual(verify_seed.check_seed(seed, 'TLP320M'), [])
        self.assertTrue(any('Blank' in p for p in
                            verify_seed.check_seed(seed, 'TLP320M', min_controls=100)))

    def test_the_wrong_model_is_refused(self):
        probs = verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP725T')
        self.assertTrue(any('part number' in p for p in probs), probs)

    def test_a_blank_project_is_refused(self):
        """What the wizard makes when Blank is still the selected radio: one page
        and a handful of controls, and it reads as a seed by every other test."""
        probs = verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP1035T',
                                       min_pages=99)
        self.assertTrue(any('Blank' in p for p in probs), probs)

    def test_the_wrong_theme_is_refused(self):
        """A Mach seed that is really an Afterburn project: its part number,
        pages and controls are all fine."""
        seed = _seed('Afterburn 1035.gdl')
        self.assertEqual(verify_seed.check_seed(seed, 'TLP1035T', theme='Afterburn'), [])
        probs = verify_seed.check_seed(seed, 'TLP1035T', theme='Mach')
        self.assertTrue(any('theme' in p and "'Afterburn'" in p and "'Mach'" in p for p in probs), probs)


class TestATurnedSeed(unittest.TestCase):
    """Where no template is drawn that way up - the 1035M portrait - a seed is
    its model's own turned by gdl.edit retarget (New-GdlTurnedSeed.ps1), so it
    is compared with its series template turned the same way: every canvas and
    control scaled per axis, each rounded."""

    def setUp(self):
        if not TABLE:
            self.skipTest("Extron's template table is not here (vendor/README.md)")
        self.seed = _seed('Afterburn 1035.gdl')

    @staticmethod
    def _turned(seed, model, size):
        """The seed's pages as gdl.edit's own retarget plan turns them."""
        from gdl.edit import Edits
        e = Edits({'edits': [{'op': 'retarget', 'model': model, 'size': list(size), 'scale': True}]}, seed)
        plan, problems = e.plan()
        assert problems == [], problems
        sizes = {(p['kind'], p['page']): p['size'] for p in plan['pages']}
        rects = {(o['page'], o['control']): o['fields'] for o in plan['controls']}
        out = []
        for pg in e.pages:
            ctrls = []
            for c in pg['controls']:
                f = rects.get((pg['id'], c['obj_id']))
                ctrls.append(dict(c, rect=(f['leftField'], f['topField'], f['widthField'], f['heightField'])
                                  if f else c['rect']))
            out.append(dict(pg, size=sizes.get((pg['kind'], pg['id']), pg['size']), controls=ctrls))
        return out

    def test_a_seed_turned_is_its_template_turned(self):
        pages = self._turned(self.seed, 'TLP1035M', (800, 1280))
        self.assertEqual(verify_seed.series_problems(pages, (800, 1280), 'TLP1035M', 'Afterburn'), [])

    def test_a_seed_not_turned_is_refused_at_the_turned_canvas(self):
        from gdl.project import Project
        pages = list(Project.open(self.seed).pages())
        probs = verify_seed.series_problems(pages, (800, 1280), 'TLP1035M', 'Afterburn')
        self.assertEqual(len(probs), 1)
        self.assertIn('turned', probs[0])


class TestAChecksumIsNoted(unittest.TestCase):
    """Feature-flag mode's Gd Generate Checksum writes a CRC-64 of a project's
    metadata on Save and Build (docs/from-scratch.md section 7). A seed made
    with it on is still a seed - the applier clears it in every panel built on
    one - but no other seed carries one, so the verifier says so."""

    def _say(self, seed, model, theme=None):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            probs = verify_seed.check_seed(seed, model, theme=theme)
        return probs, out.getvalue()

    def test_a_seed_built_with_it_on_is_noted_not_refused(self):
        probs, said = self._say(_seed('Mach 725.gdl'), 'TLP725T', 'Mach')
        self.assertEqual(probs, [])
        self.assertIn('Gd Generate Checksum', said)

    def test_a_seed_without_one_says_nothing_of_it(self):
        probs, said = self._say(_seed('Afterburn 1035.gdl'), 'TLP1035T')
        self.assertEqual(probs, [])
        self.assertNotIn('checksum', said.lower())


class TestWhatTheScriptRelies(unittest.TestCase):
    """New-GdlSeed.ps1 deletes the seed it built when this refuses it, so a
    refusal must be the seed's fault - not the case of a theme the wizard
    matched, nor a template table this cannot read."""

    def test_the_theme_is_matched_as_the_wizard_matches_it(self):
        """The wizard's combo takes 'afterburn' for Afterburn."""
        self.assertEqual(verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP1035T',
                                                theme='afterburn'), [])

    def test_an_unreadable_table_compares_no_series_and_refuses_nothing(self):
        def unreadable(path=None):
            raise ValueError('not a TemplateInfoTable.config this reads')
        saved = verify_seed.templates.table
        verify_seed.templates.table = unreadable
        try:
            seed = _seed('Afterburn 1035.gdl')
            self.assertEqual(verify_seed.check_seed(seed, 'TLP1035T', theme='Afterburn'), [])
            self.assertEqual(verify_seed.main(['verify_seed.py', seed, 'TLP1035T', 'Afterburn']), 0)
        finally:
            verify_seed.templates.table = saved

    def test_without_the_templates_it_says_nothing_and_still_checks_the_rest(self):
        saved = verify_seed.templates.table
        verify_seed.templates.table = lambda path=None: []
        try:
            seed = _seed('Afterburn 1035.gdl')
            self.assertEqual(verify_seed.check_seed(seed, 'TLP1035T'), [])
            probs = verify_seed.check_seed(seed, 'TLP725T')
            self.assertTrue(any('part number' in p for p in probs), probs)
        finally:
            verify_seed.templates.table = saved

    def test_the_command_the_script_runs_refuses_the_wrong_theme(self):
        """New-GdlSeed.ps1 runs `verify_seed.py <seed> <model> <theme>`."""
        seed = _seed('Afterburn 1035.gdl')
        self.assertEqual(verify_seed.main(['verify_seed.py', seed, 'TLP1035T', 'Afterburn']), 0)
        self.assertEqual(verify_seed.main(['verify_seed.py', seed, 'TLP1035T', 'Mach']), 1)
        self.assertEqual(verify_seed.main(['verify_seed.py', seed, 'TLP1035T', 'Mach', 'x']), 2)


@unittest.skipUnless(TABLE, 'no readable TemplateInfoTable.config - GUI Designer not installed and vendor/ empty')
class TestSeriesOfASeed(unittest.TestCase):
    """A built seed names no series, so its pages are compared with the series
    template GUI Designer takes for the model. The case: a 525T seed made from
    the 720 series - the same 800x480 canvas, the other layout, and every
    other gate green."""

    @staticmethod
    def pages(stem):
        """A series template's own pages: what a seed made from it holds, less
        the popup references Build adds."""
        row = next(r for r in TABLE if r['series'] == stem)
        return list(verify_seed.template_pages(templates.path_of(row)))

    def test_a_525_seed_made_from_the_720_series_is_refused(self):
        probs = verify_seed.series_problems(self.pages('Mach 720 Series'), (800, 480), 'TLP525T', 'Mach')
        self.assertEqual(len(probs), 1, probs)
        self.assertIn('Mach 520 Series', probs[0])
        self.assertIn("Mach 720 Series's", probs[0])

    def test_a_525_seed_made_from_the_520_series_passes(self):
        self.assertEqual(verify_seed.series_problems(self.pages('Mach 520 Series'), (800, 480),
                                                     'TLP525T', 'Mach'), [])

    def test_a_720_seed_is_the_other_way_about(self):
        probs = verify_seed.series_problems(self.pages('Mach 520 Series'), (800, 480), 'TLP720T', 'Mach')
        self.assertIn('Mach 720 Series', probs[0])
        self.assertIn("Mach 520 Series's", probs[0])

    def test_a_300m_seed_made_from_the_other_300_template_is_refused(self):
        """'300 Series' and '300 Portrait Series' are one series at one DPI and
        size, and share only some of their pages - the closest two templates."""
        probs = verify_seed.series_problems(self.pages('Afterburn 300 Series'), (320, 480),
                                            'TLP300M', 'Afterburn')
        self.assertTrue(probs and 'Afterburn 300 Portrait Series' in probs[0], probs)

    def test_a_300m_seed_made_landscape_passes(self):
        """The model is the portrait canvas; its landscape seed is the same
        series at the other size."""
        self.assertEqual(verify_seed.series_problems(self.pages('Afterburn 300 Landscape Series'),
                                                     (480, 320), 'TLP300M', 'Afterburn'), [])

    def test_a_canvas_no_template_of_the_theme_draws_is_refused(self):
        """Mach's 300 Series is portrait, so no wizard makes a landscape Mach
        300M; a seed at 480x320 calling itself one is something else."""
        probs = verify_seed.series_problems(self.pages('Mach 300 Series'), (480, 320), 'TLP300M', 'Mach')
        self.assertEqual(len(probs), 1, probs)
        self.assertIn('480x320', probs[0])
        self.assertIn('Mach 300 Series', probs[0])

    def test_a_portrait_1035_is_refused_as_no_series_draws_it(self):
        """The 1220 Series is 1280x800 only; a 1035M seed at 800x1280 is a
        Blank project or a retarget, not a series template's clone."""
        probs = verify_seed.series_problems(self.pages('Afterburn 1220 Series'), (800, 1280),
                                            'TLP1035M', 'Afterburn')
        self.assertEqual(len(probs), 1, probs)
        self.assertIn('800x1280', probs[0])

    def test_a_model_the_theme_has_no_series_for_has_nothing_to_compare(self):
        """Afterburn has no 720 template, so a 720 seed of its theme is not
        refused here."""
        self.assertEqual(verify_seed.series_problems(self.pages('Afterburn 520 Series'), (800, 480),
                                                     'TLP720T', 'Afterburn'), [])

    def test_every_real_small_seed_is_its_series(self):
        for name, model in (('Afterburn 725.gdl', 'TLP725T'), ('Afterburn 320.gdl', 'TLP320M')):
            self.assertEqual(verify_seed.check_seed(_seed(name), model, theme='Afterburn'), [], name)

    def test_a_table_without_its_templates_beside_it_says_nothing(self):
        """A verifier that raises makes New-GdlSeed.ps1 delete the seed it was
        asked about."""
        pages = self.pages('Mach 720 Series')
        saved = verify_seed.templates.path_of
        verify_seed.templates.path_of = lambda row, path=None: 'C:/nowhere/' + row['file']
        try:
            self.assertEqual(verify_seed.series_problems(pages, (800, 480), 'TLP525T', 'Mach'), [])
        finally:
            verify_seed.templates.path_of = saved

    def test_a_template_that_cannot_be_read_refuses_nothing(self):
        def unreadable(path):
            raise OSError('a template this cannot open')
        saved = verify_seed.template_pages
        verify_seed.template_pages = unreadable
        try:
            seed = _seed('Afterburn 1035.gdl')
            self.assertEqual(verify_seed.check_seed(seed, 'TLP1035T', theme='Afterburn'), [])
        finally:
            verify_seed.template_pages = saved


if __name__ == '__main__':
    unittest.main()
