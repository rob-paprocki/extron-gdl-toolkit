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
from gdl.spec import MODELS_FULL, PRESS_FIELD as PRESS  # noqa: E402

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
        # Both of its states say it, so both are written - each by index.
        self.assertEqual([(ps['index'], ps['fields']) for ps in op['per_state']],
                         [(0, {'textField': 'Laptop'}), (1, {'textField': 'Laptop'})])
        self.assertNotIn('fields', op)

    def test_rename_writes_ftext_for_a_formatted_caption(self):
        plan, _ = self._plan([{'op': 'rename', 'select': {'text': 'Cameras'},
                               'text': 'Camera Control'}])
        op = plan['controls'][0]
        self.assertTrue(op['per_state'])
        for ps in op['per_state']:
            self.assertEqual(ps['ftext'], 'Camera Control')
            self.assertTrue(ps['flattened'])
            self.assertNotIn('fields', ps)

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

    def test_cci700_is_gone(self):
        """GUI Designer 1.28 dropped CCI700 from PlatformProTypeEnum.

        It has to be absent from MODELS too, or `check()` passes a retarget the
        applier cannot perform - and because the control-geometry ops are a
        separate pass from the project ops, a half-applied retarget writes a
        file whose controls are scaled for one panel on another panel's canvas.
        """
        self.assertNotIn('CCI700', MODELS_FULL)
        _, errors, _ = _edits([{'op': 'retarget', 'model': 'CCI700'}]).check()
        self.assertTrue(errors, 'a CCI700 retarget must not pass check()')

    def test_ecp_is_a_known_model(self):
        """Extron Control Pro, new in 1.28. Read out of the assemblies:
        CreatePlatform -> PBVTLPEcpPlatform, 1920x1080 @ 220 DPI, 60-sVTLPEcp."""
        self.assertEqual(MODELS_FULL['VTLPEcp'], (1920, 1080, 220.0, '60-sVTLPEcp'))

    def test_a_real_model_sets_all_three_fields(self):
        plan, errors, _ = _edits([{'op': 'retarget', 'model': 'TLP1535M',
                                   'scale': True}]).check()
        self.assertEqual(errors, [], 'scaling up should not overflow')
        self.assertEqual(len(plan['project']), 1)
        self.assertEqual(plan['project'][0]['size'], [1920, 1080])
        self.assertEqual(plan['project'][0]['model'], 'TLP1535M')
        # The plan names the MODEL, never a platform class. The applier gets the
        # class from Enum.Parse + CreatePlatform; a guessed class name was wrong
        # for 9 of the 55 models and read by nothing.
        self.assertNotIn('platform_class', plan['project'][0])

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


# -- a button's states are not one thing --------------------------------------
#
# The fixture has no button whose states say different things, so those cases
# use a synthetic page shaped exactly like Project.pages() output. Colors come
# from the fixture, where they genuinely differ by state.

def _st(name, caption=None, fill=None, where='state', text_color=None, stroke=None):
    return {'name': name, 'caption': caption, 'caption_in': where if caption else None,
            'fill': fill, 'stroke': stroke, 'text_color': text_color}


def _button(name, states, **kw):
    first = next((s for s in states if s['caption']), None)
    c = {'type': 'PBButton', 'name': name, 'id': 11, 'rect': (0, 0, 200, 80),
         'text': None, 'caption': first['caption'] if first else None,
         'caption_in': first['caption_in'] if first else None, 'tlp_image': -1,
         'fill': None, 'stroke': None, 'text_color': None, 'border': None,
         'n_states': len(states), 'state_names': [s['name'] for s in states],
         'states': states, 'press': 1, 'default_state': 0, 'state_flags': 0,
         'obj_id': 7}
    c.update(kw)
    return c


def _synthetic(edits, *controls):
    ed = Edits.__new__(Edits)
    ed.spec, ed.path, ed.project, ed.edits = {'edits': edits}, 'synthetic', None, edits
    ed.pages = [{'kind': 'page', 'id': 51, 'name': 'Home', 'modal': None,
                 'size': (1280, 800), 'controls': list(controls)}]
    return ed


GREY, NAVY, BLUE = ({'A': 255, 'R': 0x37, 'G': 0x39, 'B': 0x4E},
                    {'A': 255, 'R': 0x24, 'G': 0x26, 'B': 0x34},
                    {'A': 255, 'R': 0x3D, 'G': 0x8B, 'B': 0xFD})
DISPLAY = _button('Display', [_st('Off', 'Display Off', GREY),
                              _st('On', 'Display On', BLUE)])


class TestRenameByState(unittest.TestCase):
    def test_the_selector_finds_a_caption_in_any_state(self):
        ed = _synthetic([], DISPLAY)
        self.assertEqual(len(ed.select({'text': 'Display On'})), 1)
        self.assertEqual(len(ed.select({'text_matches': 'On$'})), 1)

    def test_map_renames_only_the_state_that_says_it(self):
        plan, problems = _synthetic([{'op': 'rename', 'map': {'Display On': 'Screen On'}}],
                                    DISPLAY).plan()
        self.assertEqual(problems, [])
        (op,) = plan['controls']
        self.assertEqual(op['per_state'], [{'index': 1, 'was': 'Display On',
                                            'fields': {'textField': 'Screen On'}}])

    def test_one_caption_over_different_ones_is_refused(self):
        """Writing 'Screen' to every state would erase the feedback wording,
        silently - the old behavior."""
        _, problems = _synthetic([{'op': 'rename', 'select': {'name': 'Display'},
                                   'text': 'Screen'}], DISPLAY).plan()
        self.assertTrue(any('different in each state' in p and "'Display Off'" in p
                            for p in problems), problems)

    def test_state_narrows_a_rename(self):
        plan, problems = _synthetic([{'op': 'rename', 'select': {'name': 'Display'},
                                      'text': 'Screen Off', 'state': 'Off'}],
                                    DISPLAY).plan()
        self.assertEqual(problems, [])
        self.assertEqual([ps['index'] for ps in plan['controls'][0]['per_state']], [0])

    def test_an_unknown_state_is_an_error(self):
        _, problems = _synthetic([{'op': 'rename', 'select': {'name': 'Display'},
                                   'text': 'x', 'state': 'Standby'}], DISPLAY).plan()
        self.assertTrue(any("no state 'Standby'" in p for p in problems), problems)

    def test_state_with_map_is_an_error(self):
        _, problems = _synthetic([{'op': 'rename', 'map': {'Display On': 'x'},
                                   'state': 'On'}], DISPLAY).plan()
        self.assertTrue(any('`state` goes with `text`' in p for p in problems), problems)

    def test_each_state_is_written_where_its_own_caption_lives(self):
        mixed = _button('M', [_st('Off', 'Cams', where='fstate'), _st('On', 'Cams')])
        plan, _ = _synthetic([{'op': 'rename', 'map': {'Cams': 'Cameras'}}], mixed).plan()
        a, b = plan['controls'][0]['per_state']
        self.assertEqual((a.get('ftext'), a.get('flattened')), ('Cameras', True))
        self.assertEqual(b['fields'], {'textField': 'Cameras'})


class TestRestyleByState(unittest.TestCase):
    def test_a_fill_that_lives_only_on_a_state_is_restyled(self):
        """Table Input 1 has no fill of its own: Off is transparent and On is
        #242634. Matching the control's colors found nothing to restyle on 288
        of the fixture's 442 buttons."""
        plan, problems = _edits([{'op': 'restyle', 'select': {'text': 'Table Input 1'},
                                  'map': {'#242634': '#101826'}}]).plan()
        self.assertEqual(problems, [])
        (op,) = plan['controls']
        self.assertNotIn('colors', op)
        self.assertEqual(op['per_state'], [{'index': 1, 'colors': {
            'borderFillColorField': '#FF101826'}}])

    def test_each_state_is_remapped_from_its_own_color(self):
        """The old op wrote the control's new color to every state, so an On
        state came out in the Off color."""
        plan, _ = _synthetic([{'op': 'restyle', 'map': {'#37394E': '#111111',
                                                        '#3D8BFD': '#2266EE'}}],
                             DISPLAY).plan()
        per = plan['controls'][0]['per_state']
        self.assertEqual([(ps['index'], ps['colors']['borderFillColorField']) for ps in per],
                         [(0, '#FF111111'), (1, '#FF2266EE')])

    def test_text_color_is_remapped(self):
        white = {'A': 255, 'R': 255, 'G': 255, 'B': 255}
        b = _button('T', [_st('Off', 'x', GREY, text_color=white),
                          _st('On', 'x', BLUE, text_color=white)])
        plan, _ = _synthetic([{'op': 'restyle', 'map': {'#FFFFFF': '#F0F0F0'}}], b).plan()
        per = plan['controls'][0]['per_state']
        self.assertEqual([ps['colors'] for ps in per],
                         [{'textColorField': '#FFF0F0F0'}] * 2)


class TestStatesOp(unittest.TestCase):
    FOUR = ['Off', {'name': 'Warming', 'fill': '#5A5C70', 'text': 'Warming Up'},
            {'name': 'On', 'text': 'Display On'},
            {'name': 'Cooling', 'fill': '#2E3040', 'text': 'Cooling Down'}]

    def _op(self, states, *controls, **kw):
        plan, problems = _synthetic([dict({'op': 'states', 'select': {'name': 'Display'},
                                           'states': states}, **kw)],
                                    *(controls or (DISPLAY,))).plan()
        return (plan['controls'][0] if plan['controls'] else None), problems

    def test_growing_names_writes_and_expects_every_state(self):
        op, problems = self._op(self.FOUR)
        self.assertEqual(problems, [])
        self.assertEqual(op['state_count'], 4)
        self.assertEqual([ps['fields']['nameField'] for ps in op['per_state']],
                         ['Off', 'Warming', 'On', 'Cooling'])
        # State 1 keeps On's look; state 3 starts as a copy of it.
        exp = op['expect_states']
        self.assertEqual(exp[2]['fill'], '#FF3D8BFD')
        self.assertEqual(exp[2]['text'], 'Display On')
        self.assertEqual(exp[3]['fill'], '#FF2E3040')
        self.assertEqual(exp[0]['text'], 'Display Off')

    def test_the_press_state_is_kept_or_named(self):
        op, _ = self._op(self.FOUR)
        self.assertEqual(op['fields'][PRESS], 1)
        op, _ = self._op(self.FOUR, press='On')
        self.assertEqual(op['fields'][PRESS], 2)
        op, _ = self._op(['Only'])
        self.assertEqual(op['fields'][PRESS], 0)

    def test_a_new_state_that_copies_the_last_unchanged_is_an_error(self):
        _, problems = self._op(['Off', 'On', 'Standby'])
        self.assertTrue(any("'On' and 'Standby' would look identical" in p
                            for p in problems), problems)

    def test_existing_states_are_not_compared(self):
        """Two existing states can differ in things this cannot see - an icon,
        a border - so only a copy is compared with what it was copied from."""
        same = _button('Display', [_st('Off', 'x', GREY), _st('On', 'x', GREY)])
        _, problems = self._op(['Off', 'On'], same)
        self.assertEqual(problems, [])

    def test_only_a_button_has_states(self):
        label = dict(DISPLAY, type='PBLabel')
        _, problems = self._op(['Off', 'On'], label)
        self.assertTrue(any('only a button' in p for p in problems), problems)

    def test_flagged_states_are_not_resized(self):
        _, problems = self._op(self.FOUR, dict(DISPLAY, state_flags=1))
        self.assertTrue(any('status flags' in p for p in problems), problems)

    def test_bad_states_are_refused_before_any_control(self):
        for states, needle in ((['Off', 'Off'], 'used twice'),
                               ([{'name': 'Off', 'border': 'x'}], 'unknown key'),
                               ([{'name': 'Off', 'fill': 'blue'}], 'not #RRGGBB'),
                               ([{'name': 'Off', 'text': None}], 'is null'),
                               ([{'fill': '#000000'}], 'has no name'),
                               ([], 'at least one')):
            _, problems = self._op(states)
            self.assertTrue(any(needle in p for p in problems), (states, problems))
        _, problems = self._op(['Off', 'On'], press='Standby')
        self.assertTrue(any('press' in p for p in problems), problems)

    def test_another_op_on_the_same_buttons_states_is_an_error(self):
        """Each op is planned against the file on disk, so a rename before a
        `states` op would make its expected captions wrong."""
        _, errors, _ = _synthetic([
            {'op': 'rename', 'map': {'Display On': 'Screen On'}},
            {'op': 'states', 'select': {'name': 'Display'}, 'states': self.FOUR}],
            DISPLAY).check()
        self.assertTrue(any('rename and states both change' in e for e in errors), errors)
        _, errors, _ = _synthetic([
            {'op': 'rename', 'map': {'Display On': 'Screen On'}},
            {'op': 'restyle', 'map': {'#3D8BFD': '#2266EE'}}], DISPLAY).check()
        self.assertEqual(errors, [])

    def test_on_the_fixture(self):
        """Grow a real two-state button to three; the new state starts as On."""
        plan, problems = _edits([{'op': 'states', 'select': {'text': 'Table Input 1'},
                                  'states': ['Off', 'On', {'name': 'Fault',
                                                           'fill': '#8B1E1E'}]}]).plan()
        self.assertEqual(problems, [])
        (op,) = plan['controls']
        self.assertEqual(op['was'], ['Off', 'On'])
        self.assertEqual(op['expect_states'][1]['fill'], '#FF242634')
        self.assertEqual(op['expect_states'][2]['fill'], '#FF8B1E1E')
        self.assertEqual(op['expect_states'][2]['text'], 'Table Input 1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
