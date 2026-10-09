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
