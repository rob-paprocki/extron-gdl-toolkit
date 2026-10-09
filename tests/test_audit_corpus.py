"""The corpus audit's verdicts, on facts rather than on the corpus.

The full audit takes minutes and reads the install's templates, so its checks
are pinned here on the small fact dicts it reduces each project to.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import audit_corpus  # noqa: E402


def fact(name, **kw):
    f = {'name': name, 'canvas': None, 'fonts_missing': None, 'fonts_error': None,
         'built': True, 'n_modal': 0, 'fullcanvas_refs': [], 'popup_mismatch': [],
         'unrasterized': 0}
    f.update(kw)
    return f


class TestCanvas(unittest.TestCase):
    def test_a_panel_turned_the_other_way_up_is_known(self):
        # The 300M builds at 320x480 and 480x320; the landscape seed is one.
        verdict, lines = audit_corpus.inv_canvas([fact('Afterburn 300M Landscape.gdl',
                                                       canvas=(480, 320))])
        self.assertEqual((verdict, lines), ('PASS', []))

    def test_a_canvas_no_model_has_fails(self):
        verdict, lines = audit_corpus.inv_canvas([fact('Teams.glt', canvas=(1920, 1200))])
        self.assertEqual(verdict, 'FAIL')
        self.assertEqual(lines, ['Teams.glt: (1920, 1200)'])


class TestNothingHidesBehindTheCap(unittest.TestCase):
    def test_the_font_fail_says_how_many_of_how_many(self):
        F = [fact(f'seed {i}.gdl', fonts_missing=['ariblk.ttf']) for i in range(15)]
        F += [fact(f'fixture {i}.gdl', fonts_missing=[]) for i in range(14)]
        verdict, lines = audit_corpus.inv_fonts(F)
        self.assertEqual(verdict, 'FAIL')
        self.assertEqual(lines[0], '15 of 29 project(s)')
        self.assertEqual(lines[-1], '  ... and 3 more')

    def test_a_project_whose_faces_could_not_be_read_is_counted_in_both(self):
        verdict, lines = audit_corpus.inv_fonts([fact('broken.gdl', fonts_error='boom')])
        self.assertEqual((verdict, lines[0]), ('FAIL', '1 of 1 project(s)'))

    def test_the_modal_check_counts_what_it_checked_and_says_what_it_cut(self):
        F = [fact(f'p{i}.gdl', n_modal=2, fullcanvas_refs=[(2, 5)]) for i in range(17)]
        F.append(fact('odd.gdl', n_modal=2, fullcanvas_refs=[(1, 5)]))
        F.append(fact('none.gdl'))
        verdict, lines = audit_corpus.inv_modal_refs(F)
        self.assertEqual(verdict, 'FAIL')
        self.assertEqual(lines[0], '18 built project(s) with a modal popup')
        self.assertEqual(lines[-1], '  ... and 2 more')

    def test_unrasterized_controls_are_summed_up_before_the_list(self):
        F = [fact(f'p{i}.gdl', unrasterized=i + 2) for i in range(18)] + [fact('clean.gdl')]
        verdict, lines = audit_corpus.inv_unrasterized(F)
        self.assertEqual(lines[0], '18 project(s), 2 to 19 each')
        self.assertEqual(lines[-1], '  ... and 2 more')

    def test_a_long_popup_size_fail_says_what_it_cut(self):
        F = [fact(f'p{i}.gdl', popup_mismatch=[('Pop', (10, 10), (20, 20))]) for i in range(14)]
        verdict, lines = audit_corpus.inv_popup_size(F)
        self.assertEqual((verdict, len(lines), lines[-1]), ('FAIL', 13, '  ... and 2 more'))

    def test_a_short_list_is_not_said_to_have_more(self):
        F = [fact('seed.gdl', fonts_missing=['ariblk.ttf']), fact('f.gdl', fonts_missing=[])]
        self.assertEqual(audit_corpus.inv_fonts(F),
                         ('FAIL', ['1 of 2 project(s)', "seed.gdl: not recovered ['ariblk.ttf']"]))


if __name__ == '__main__':
    unittest.main()
