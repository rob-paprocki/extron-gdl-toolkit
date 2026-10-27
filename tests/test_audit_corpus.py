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
         'fonts_not_carried': None, 'fonts_not_declared': None, 'built': True,
         'n_modal': 0, 'fullcanvas_refs': [],
         'popup_mismatch': [], 'unrasterized': 0}
    f.update(kw)
    return f


class TestDeclaredIsNotCarried(unittest.TestCase):
    """A seed can declare a face it carries nothing for - Arial Black, whose
    resource a build adds only sometimes - and that is the seed, not a fault to
    fail on.
    A face it carries and the toolkit cannot recover is."""

    def test_a_declaration_carried_by_nothing_is_said_not_failed(self):
        F = [fact('seed.gdl', fonts_missing=[], fonts_not_carried=['ariblk.ttf (119,904 B)']),
             fact('f.gdl', fonts_missing=[], fonts_not_carried=[])]
        self.assertEqual(audit_corpus.inv_fonts(F), ('PASS', ['2 project(s) checked']))
        self.assertEqual(audit_corpus.inv_fonts_not_carried(F),
                         ('INFO', ['1 of 2 project(s)', 'seed.gdl: ariblk.ttf (119,904 B)']))

    def test_none_is_said_plainly(self):
        F = [fact('f.gdl', fonts_missing=[], fonts_not_carried=[])]
        self.assertEqual(audit_corpus.inv_fonts_not_carried(F), ('PASS', ['1 project(s) checked']))

    def test_all_three_are_on_the_list(self):
        names = [n for n, _ in audit_corpus.INVARIANTS]
        self.assertIn('every face a project declares and carries is recovered', names)
        self.assertIn('faces declared and not carried', names)
        self.assertIn('faces carried and not declared', names)

    def test_a_face_carried_under_no_declaration_is_said_not_failed(self):
        F = [fact('Turbulence 1035.gdl', fonts_missing=[], fonts_not_carried=[],
                  fonts_not_declared=['Arial Regular (1,016,724 B)'])]
        self.assertEqual(audit_corpus.inv_fonts(F), ('PASS', ['1 project(s) checked']))
        self.assertEqual(audit_corpus.inv_fonts_not_declared(F),
                         ('INFO', ['1 of 1 project(s)',
                                   'Turbulence 1035.gdl: Arial Regular (1,016,724 B)']))


class TestTheFactsOfARealSeed(unittest.TestCase):
    """facts() itself, on the one seed CI pulls: the verdicts above are only as
    good as the pairing that reduces a project to these lists."""

    def test_the_seed_ci_has(self):
        from _corpus import seed, usable
        path = seed('Afterburn 1035.gdl')
        if not usable(path):
            self.skipTest('seeds/Afterburn 1035.gdl is not here (an LFS pull fetches it)')
        f = audit_corpus.facts(path)
        self.assertIsNone(f['fonts_error'])
        self.assertEqual(f['fonts_not_carried'], ['ariblk.ttf (119,904 B)'])
        self.assertEqual(f['fonts_missing'], [])
        self.assertEqual(f['fonts_not_declared'], [])


class TestReferenceCounts(unittest.TestCase):
    """A popup group's referenceCountField is kept by Build as written and
    reaches nothing it builds (the format probe, docs/gdl-format.md §6), so
    the corpus's counts are said, not judged: how many are the group's
    popups, its references, or neither."""

    def test_each_group_is_counted_by_what_its_count_matches(self):
        F = [fact('client.gdl', group_counts=[('Presentation', 46, 11, 3), ('Volume', 2, 2, 2),
                                              ('Tech', 1, 1, 4)]),
             fact('seed.gdl', group_counts=[('Main', 8, 1, 5), ('Doc Cam', 5, 2, 5)]),
             fact('template.glt', group_counts=[])]
        verdict, lines = audit_corpus.inv_reference_counts(F)
        self.assertEqual(verdict, 'INFO')
        self.assertEqual(lines, [
            '5 group(s) in 2 project(s): the count is its popups in 2, its references alone '
            'in 1, neither in 2',
            "client.gdl 'Presentation': 46 against 11 popup(s), 3 reference(s)",
            "seed.gdl 'Main': 8 against 1 popup(s), 5 reference(s)"])

    def test_a_corpus_with_no_group_says_so(self):
        self.assertEqual(audit_corpus.inv_reference_counts([fact('t.glt', group_counts=[])]),
                         ('INFO', ['no built project with a popup group']))

    def test_it_is_on_the_list(self):
        self.assertIn('popup group reference counts', [n for n, _ in audit_corpus.INVARIANTS])

    def test_facts_read_the_registry_off_a_seed(self):
        from _corpus import seed, usable
        path = seed('Afterburn 1035.gdl')
        if not usable(path):
            self.skipTest('seeds/Afterburn 1035.gdl is not here (an LFS pull fetches it)')
        rows = audit_corpus.facts(path)['group_counts']
        self.assertTrue(rows)
        for name, count, popups, refs in rows:
            self.assertIsInstance(name, str)
            self.assertTrue(all(isinstance(v, int) for v in (count, popups, refs)), rows)
        self.assertTrue(any(popups and refs for _, _, popups, refs in rows), rows)


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
