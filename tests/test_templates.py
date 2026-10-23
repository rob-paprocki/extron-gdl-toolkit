"""Extron's series templates, indexed from GUI Designer's own table.

A panel-aware design system takes each panel's layout regions and background
art from the template Extron ships for that panel's series. The series is
chosen by model, never by resolution alone: the 520 and 720 series are both
800x480, one a 5" hub and the other a 7" full layout.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl import templates  # noqa: E402

TABLE = templates.table()


@unittest.skipUnless(TABLE, 'no TemplateInfoTable.config - GUI Designer not installed and vendor/ empty')
class TestTable(unittest.TestCase):
    def row(self, stem):
        return next(r for r in TABLE if r['series'] == stem)

    def test_a_series_is_its_file_name_on_any_machine(self):
        """The table holds each template's Windows path. Read on Linux - the
        translator and the tests on a box without GUI Designer - os.path took
        the whole path for the file name, and every series failed to match."""
        self.assertTrue(TABLE)
        for r in TABLE:
            self.assertNotIn('\\', r['file'], r)
            self.assertTrue(r['file'].endswith('.glt') and r['series'] + '.glt' == r['file'], r)

    def test_the_1230w_row(self):
        """The row Phase 0 corrected the model table from: the 1230WTG's
        platform falls through to 800x480 at 0 DPI, its template does not."""
        r = self.row('Afterburn 1230 Series')
        self.assertEqual((r['size'], r['dpi'], r['soft']), ((1920, 720), 166.0, False))

    def test_a_725_takes_the_1020_series(self):
        """No template is authored at the 725's 169.55 DPI; the 1024x600 one is
        the 1020's, and both are tier A."""
        self.assertEqual(templates.template_for('Afterburn', 'TLP725T')['series'],
                         'Afterburn 1020 Series')

    def test_a_525_takes_the_520_series(self):
        self.assertEqual(templates.template_for('Afterburn', 'TLP525T')['series'],
                         'Afterburn 520 Series')

    def test_a_535_takes_the_535_series(self):
        self.assertEqual(templates.template_for('Afterburn', 'TLP535M')['series'],
                         'Afterburn 535 Series')

    def test_a_720_has_no_afterburn_series(self):
        """Afterburn has no 720 template. The only 800x480 one is the 520, a
        tier B hub for a 5" screen - the wrong layout for a 7" one."""
        self.assertIsNone(templates.template_for('Afterburn', 'TLP720T'))

    def test_ecp_rows_are_soft_and_never_matched(self):
        self.assertTrue(self.row('Afterburn ECP 16-10 Series')['soft'])
        self.assertIsNone(templates.template_for('Afterburn', 'VTLPEcp'))

    def test_a_portrait_300m_takes_the_portrait_series(self):
        """'300 Series' and '300 Portrait Series' share a size and DPI; the seed
        the wizard makes is the portrait one."""
        self.assertEqual(templates.template_for('Afterburn', 'TLP300M')['series'],
                         'Afterburn 300 Portrait Series')

    def test_a_landscape_300m_takes_the_landscape_series(self):
        """Asked for the 300M the other way up, the series drawn that way up -
        the one GUI Designer's wizard seeds when its Resolution is 480x320."""
        self.assertEqual(templates.template_for('Afterburn', 'TLP300M', (480, 320))['series'],
                         'Afterburn 300 Landscape Series')

    def test_the_default_canvas_is_the_one_asked_for_without_a_size(self):
        self.assertEqual(templates.template_for('Afterburn', 'TLP300M', (320, 480)),
                         templates.template_for('Afterburn', 'TLP300M'))

    def test_a_theme_with_no_landscape_300_has_none(self):
        """Mach's 300 Series is portrait; the wizard offers a landscape 300M
        Afterburn alone."""
        self.assertIsNotNone(templates.template_for('Mach', 'TLP300M'))
        self.assertIsNone(templates.template_for('Mach', 'TLP300M', (480, 320)))

    def test_a_portrait_1035_or_835_has_no_series(self):
        """Their series, the 1220, is drawn at 1280x800 only: the wizard offers
        them Blank alone when turned portrait."""
        for model in ('TLP1035M', 'TLP835M'):
            self.assertIsNone(templates.template_for('Afterburn', model, (800, 1280)), model)

    def test_a_canvas_the_model_does_not_run_at_has_no_series(self):
        """The 1035T does not rotate: 800x1280 is not its canvas, whatever a
        1220 Series template is drawn at."""
        self.assertIsNone(templates.template_for('Afterburn', 'TLP1035T', (800, 1280)))
        self.assertIsNone(templates.template_for('Afterburn', 'TLP725T', (1280, 800)))

    def test_the_command_line_takes_a_canvas(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = templates.main(['templates', 'Afterburn', 'TLP300M', '480x320'])
        self.assertEqual((rc, out.getvalue().strip()), (0, 'Afterburn 300 Landscape Series'))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = templates.main(['templates', 'Afterburn', 'TLP1035M', '800x1280'])
        self.assertEqual(rc, 1)
        self.assertIn('800x1280', out.getvalue())

    def test_series_lists_one_theme_without_soft_clients(self):
        rows = templates.series('Afterburn')
        self.assertTrue(rows)
        self.assertTrue(all(r['theme'] == 'Afterburn' and not r['soft'] for r in rows))
        self.assertIn('Afterburn 1220 Series', [r['series'] for r in rows])


class TestNoTable(unittest.TestCase):
    def test_no_table_reads_empty(self):
        self.assertEqual(templates.table('C:/nowhere/TemplateInfoTable.config'), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
