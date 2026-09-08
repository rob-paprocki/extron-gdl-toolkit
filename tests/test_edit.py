"""Tests for the edit vocabulary.

These run against the REAL Liberty Bank fixture rather than a synthetic project,
on purpose. Every bug this vocabulary has had came from the difference between
what a panel file looks like in the abstract and what a real one contains: a
button whose caption is not in `textField`, a caption that is formatted text
with hand-placed tabs, a page whose controls do not fit a smaller panel. A
hand-built fixture would have had none of those.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.edit import Edits, _norm  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(
    HERE, 'fixtures', 'gdl',
    'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
MAIN = '2000 - Main - Presentation'


def _edits(edits):
    return Edits({'edits': edits}, FIXTURE)


class TestSelection(unittest.TestCase):
    def test_an_empty_selector_matches_everything(self):
        self.assertGreater(len(_edits([]).select({})), 600)

    def test_page_narrows_by_name(self):
        ed = _edits([])
        hits = ed.select({'page': MAIN})
        self.assertTrue(hits)
        self.assertTrue(all(pg['name'] == MAIN for pg, _ in hits))

    def test_type_and_page_are_anded(self):
        ed = _edits([])
        hits = ed.select({'page': MAIN, 'type': 'PBSlider'})
        self.assertTrue(all(c['type'] == 'PBSlider' for _, c in hits))

    def test_text_matches_the_caption_not_the_text_field(self):
        """The trap this vocabulary was built around.

        A button's wording usually lives on its first STATE, so a selector that
        compared `textField` matched nothing on a real project and the edit
        silently did nothing.
        """
        ed = _edits([])
        hits = ed.select({'text': 'Cameras'})
        self.assertTrue(hits, 'no control captioned Cameras - caption lookup is broken')
        for _, c in hits:
            self.assertEqual(c['caption'], 'Cameras')
            self.assertFalse(c['text'], 'this fixture holds it on the state, not the control')

    def test_regex_selection(self):
        hits = _edits([]).select({'text_matches': r'^Table Input \d$'})
        self.assertEqual(len(hits), 9)


class TestRename(unittest.TestCase):
    def _plan(self, edits):
        return _edits(edits).plan()

    def test_rename_writes_to_the_state_for_a_state_caption(self):
        plan, problems = self._plan([{'op': 'rename',
                                      'select': {'text': 'Table Input 1'},
                                      'text': 'Laptop'}])
        self.assertEqual(problems, [])
        op = plan['controls'][0]
        self.assertEqual(op['states'], {'textField': 'Laptop'})
        self.assertNotIn('fields', op)

    def test_rename_writes_ftext_for_a_formatted_caption(self):
        plan, _ = self._plan([{'op': 'rename', 'select': {'text': 'Cameras'},
                               'text': 'Camera Control'}])
        op = plan['controls'][0]
        self.assertEqual(op['states_ftext'], 'Camera Control')
        self.assertTrue(op['flattened'])

    def test_a_selector_matching_nothing_is_an_error(self):
        _, problems = self._plan([{'op': 'rename',
                                   'select': {'text': 'No Such Caption'},
                                   'text': 'x'}])
        self.assertTrue(any('matched nothing' in p or 'nothing has the caption' in p
                            for p in problems))

    def test_map_form_renames_several_at_once(self):
        plan, problems = self._plan([{'op': 'rename', 'select': {'page': MAIN},
                                      'map': {'Cameras': 'A', 'Displays': 'B'}}])
        self.assertEqual(problems, [])
        self.assertEqual(len(plan['controls']), 2)

    def test_growing_a_formatted_caption_warns(self):
        """Measured against the real build: 'Cameras' -> 'Camera Control'
        rasterizes as two lines with the second unindented over the icon."""
        _, _, warnings = _edits([{'op': 'rename', 'select': {'text': 'Cameras'},
                                  'text': 'Camera Control'}]).check()
        self.assertTrue(any('FORMATTED text' in w for w in warnings))

    def test_a_same_length_formatted_rename_does_not_warn(self):
        """'Displays' -> 'Screens' built correctly, so warning on it would be
        crying wolf on the one case that works."""
        _, errors, warnings = _edits([{'op': 'rename', 'select': {'text': 'Displays'},
                                       'text': 'Screens'}]).check()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class TestRenumber(unittest.TestCase):
    def test_ids_are_handed_out_in_order(self):
        plan, problems = _edits([{'op': 'renumber',
                                  'select': {'page': '1000 - Home', 'type': 'PBLabel'},
                                  'start': 1100}]).plan()
        self.assertEqual(problems, [])
        got = [o['fields']['userIdField'] for o in plan['controls']]
        self.assertEqual(got, [1100, 1101])

    def test_step_is_honoured(self):
        plan, _ = _edits([{'op': 'renumber',
                           'select': {'page': '1000 - Home', 'type': 'PBLabel'},
                           'start': 200, 'step': 10}]).plan()
        self.assertEqual([o['fields']['userIdField'] for o in plan['controls']],
                         [200, 210])

    def test_colliding_with_an_untouched_control_is_an_error(self):
        """Duplicate IDs are legal in the format - Extron uses them for feedback
        mirrors - so nothing downstream would complain. It is still never what a
        renumber means."""
        ed = _edits([])
        home = [p for p in ed.pages if p['name'] == '1000 - Home'][0]
        taken = next(c['id'] for c in home['controls']
                     if c['id'] and c['type'] != 'PBLabel')
        _, errors, _ = _edits([{'op': 'renumber',
                                'select': {'page': '1000 - Home', 'type': 'PBLabel'},
                                'start': taken}]).check()
        self.assertTrue(any('already has it' in e for e in errors))


class TestRestyle(unittest.TestCase):
    def test_colors_are_remapped(self):
        plan, problems = _edits([{'op': 'restyle', 'select': {'type': 'PBSlider'},
                                  'map': {'#242634': '#1B2233'}}]).plan()
        self.assertEqual(problems, [])
        self.assertTrue(plan['controls'])
        for o in plan['controls']:
            self.assertEqual(o['colors']['borderFillColorField'], '#FF1B2233')

    def test_short_hex_means_opaque(self):
        self.assertEqual(_norm('#242634'), '#FF242634')
        self.assertEqual(_norm('#FF242634'), '#FF242634')

    def test_an_unused_color_is_a_warning_not_an_error(self):
        """A theme map legitimately covers colors a given project happens not
        to use, so this must not block the edit."""
        ed = _edits([{'op': 'restyle', 'map': {'#010203': '#040506'}}])
        _, errors, _ = ed.check()
        self.assertEqual(errors, [])
        self.assertIn('#FF010203', ed._unused_colors)


class TestRetarget(unittest.TestCase):
    def test_an_unknown_model_is_an_error_with_a_suggestion(self):
        _, errors, _ = _edits([{'op': 'retarget', 'model': 'TLP1720'}]).check()
        self.assertTrue(errors)
        self.assertIn('TLP1720MG', errors[0])

    def test_a_real_model_sets_all_three_fields(self):
        plan, errors, _ = _edits([{'op': 'retarget', 'model': 'TLP1535M',
                                   'scale': True}]).check()
        self.assertEqual(errors, [], 'scaling up should not overflow')
        self.assertEqual(len(plan['project']), 1)
        self.assertEqual(plan['project'][0]['size'], [1920, 1080])
        self.assertEqual(plan['project'][0]['platform_class'],
                         'Extron.GUICPro.PBTLP1535MPlatform')

    def test_scaling_moves_every_control(self):
        plan, _, _ = _edits([{'op': 'retarget', 'model': 'TLP1535M',
                              'scale': True}]).check()
        self.assertGreater(len(plan['controls']), 600)
        for o in plan['controls']:
            self.assertIn('leftField', o['fields'])

    def test_shrinking_without_scaling_is_an_error(self):
        """The whole point of the check. Build moves a control that no longer
        fits to 0,0 - silently, reporting 0 errors - so an unscaled retarget to
        a smaller panel destroys the layout and nothing says so."""
        _, errors, _ = _edits([{'op': 'retarget', 'model': 'TLP725M'}]).check()
        self.assertTrue(errors)
        self.assertTrue(any('falls outside' in e and '0,0' in e for e in errors))

    def test_a_pre_existing_touch_violation_says_so(self):
        _, _, warnings = _edits([{'op': 'retarget', 'model': 'TLP1535M',
                                  'scale': True}]).check()
        self.assertTrue(any('already under the old' in w for w in warnings))


class TestSeverity(unittest.TestCase):
    def test_warnings_never_block_a_plan(self):
        """A retarget of a real project always surfaces touch-target warnings.
        If those blocked, the tool would refuse the job it was asked to do."""
        plan, errors, warnings = _edits([{'op': 'retarget', 'model': 'TLP1535M',
                                          'scale': True}]).check()
        self.assertTrue(warnings)
        self.assertEqual(errors, [])
        self.assertTrue(plan['controls'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
