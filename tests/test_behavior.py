"""Tests for the behavior vocabulary: what a spec says its controls DO.

Every check here stands in for a failure that would otherwise surface on a
panel in a room - a button that shows a page that does not exist, a
confirmation with no way out, a device call that runs without being
confirmed. Nothing here needs Windows or GUI Designer.

    python tests/test_behavior.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.behavior import Program  # noqa: E402
from gdl.spec import Panel  # noqa: E402

THEME = {'text': '#FFFFFF', 'raised': '#2E3142', 'accent': '#3D8BFD'}


def btn(name, x=0, **kw):
    return dict({'kind': 'button', 'name': name, 'text': name, 'rect': [x, 700, 100, 80],
                 'fill': 'raised', 'on': 'accent'}, **kw)


def program(pages, popups=(), behavior=None, **top):
    spec = {'name': 'T', 'size': [1280, 800], 'theme': THEME,
            'pages': list(pages), 'popups': list(popups)}
    if behavior is not None:
        spec['behavior'] = behavior
    spec.update(top)
    return Program(Panel(spec))


def page(name, *controls, number=None, **kw):
    return dict({'name': name, 'number': number or 1000, 'controls': list(controls)}, **kw)


def modal(name, *controls, **kw):
    return dict({'name': name, 'number': 9100, 'modal': True, 'controls': list(controls)}, **kw)


DEVICES = {'devices': {'codec': 'video codec', 'dsp': 'audio DSP'}}


def problems(p):
    return p.check()[0]


def notes(p):
    return p.check()[1]


def has(msgs, *words):
    return any(all(w in m for w in words) for m in msgs)


class TestVocabulary(unittest.TestCase):
    def test_a_clean_nav_spec_has_no_problems(self):
        p = program([page('Home', btn('Go', nav='Settings'), number=1000),
                     page('Settings', btn('Back', nav='Home'), number=1100)])
        self.assertEqual(problems(p), [])

    def test_nav_to_a_page_shows_the_page(self):
        p = program([page('Home', btn('Go', nav='Settings'), number=1000),
                     page('Settings', btn('Back', nav='Home'), number=1100)])
        self.assertIn(('Home', 'Settings'), p.nav_edges())

    def test_nav_to_a_popup_shows_the_popup(self):
        p = program([page('Home', btn('Ask', nav='Confirm'))],
                    [modal('Confirm', btn('Close', x=200, press={'do': 'hide_popup',
                                                                 'target': 'Confirm'}))])
        ev = p.control(1001)['events']['Pressed']
        self.assertEqual(ev, [{'do': 'show_popup', 'target': 'Confirm', 'duration': 0}])

    def test_nav_and_press_together_is_a_problem(self):
        p = program([page('Home', btn('Go', nav='Home', press={'do': 'hide_all_popups'}))])
        self.assertTrue(has(problems(p), 'nav', 'press'), problems(p))

    def test_an_unknown_action_is_a_problem(self):
        p = program([page('Home', btn('Go', press={'do': 'launch_missiles'}))])
        self.assertTrue(has(problems(p), 'launch_missiles'), problems(p))

    def test_an_action_must_be_an_object(self):
        p = program([page('Home', btn('Go', press='show_page'))])
        self.assertTrue(has(problems(p), 'action'), problems(p))

    def test_an_event_a_kind_cannot_raise_is_a_problem(self):
        p = program([page('Home', {'kind': 'label', 'name': 'L', 'rect': [0, 0, 100, 40],
                                   'press': {'do': 'hide_all_popups'}})])
        self.assertTrue(has(problems(p), 'label', 'press'), problems(p))

    def test_behavior_on_a_shape_is_a_problem(self):
        p = program([page('Home', {'kind': 'panel', 'name': 'Bg', 'rect': [0, 0, 100, 40],
                                   'fill': 'raised', 'nav': 'Home'})])
        self.assertTrue(has(problems(p), 'panel'), problems(p))


class TestTargets(unittest.TestCase):
    def test_show_page_of_an_unknown_page_is_a_problem(self):
        p = program([page('Home', btn('Go', press={'do': 'show_page', 'target': 'Nowhere'}))])
        self.assertTrue(has(problems(p), 'Nowhere'), problems(p))

    def test_show_page_of_a_popup_is_a_problem(self):
        p = program([page('Home', btn('Go', press={'do': 'show_page', 'target': 'Confirm'}))],
                    [modal('Confirm', btn('Close', x=200,
                                          press={'do': 'hide_popup', 'target': 'Confirm'}))])
        self.assertTrue(has(problems(p), 'Confirm', 'not a page'), problems(p))

    def test_show_popup_of_a_page_is_a_problem(self):
        p = program([page('Home', btn('Go', press={'do': 'show_popup', 'target': 'Home'}))])
        self.assertTrue(has(problems(p), 'Home', 'not a popup'), problems(p))

    def test_nav_to_an_unknown_name_is_a_problem(self):
        p = program([page('Home', btn('Go', nav='Nowhere'))])
        self.assertTrue(has(problems(p), 'Nowhere'), problems(p))

    def test_a_grouped_popup_shown_from_a_page_without_its_reference_is_a_problem(self):
        p = program(
            [page('Home', btn('Src', nav='Laptop'), number=1000),
             page('Other', {'kind': 'popup_ref', 'name': 'Ref', 'rect': [0, 0, 400, 300],
                            'group': 'Sources'}, btn('Back', x=200, nav='Home'), number=1100)],
            [{'name': 'Laptop', 'number': 9200, 'group': 'Sources', 'size': [400, 300],
              'controls': []}],
            start_page='Home')
        self.assertTrue(has(problems(p), 'Laptop', 'Home', 'reference'), problems(p))


class TestCalls(unittest.TestCase):
    def test_a_call_to_an_undeclared_device_is_a_problem(self):
        p = program([page('Home', btn('Go', press={'do': 'call', 'device': 'projector',
                                                   'op': 'power_on'}))], behavior=DEVICES)
        self.assertTrue(has(problems(p), 'projector'), problems(p))

    def test_an_op_must_be_an_identifier(self):
        p = program([page('Home', btn('Go', press={'do': 'call', 'device': 'dsp',
                                                   'op': 'mute now'}))], behavior=DEVICES)
        self.assertTrue(has(problems(p), 'mute now'), problems(p))

    def test_an_argument_name_may_not_be_a_keyword(self):
        p = program([page('Home', btn('Go', press={'do': 'call', 'device': 'dsp', 'op': 'mute',
                                                   'args': {'class': 1}}))], behavior=DEVICES)
        self.assertTrue(has(problems(p), 'class'), problems(p))

    def test_a_device_name_must_be_an_identifier(self):
        p = program([page('Home', btn('Go'))], behavior={'devices': {'room dsp': 'x'}})
        self.assertTrue(has(problems(p), 'room dsp'), problems(p))

    def test_a_slider_call_may_not_name_an_argument_value(self):
        p = program([page('Home', {'kind': 'slider', 'name': 'Vol', 'rect': [0, 0, 90, 300],
                                   'change': {'do': 'call', 'device': 'dsp', 'op': 'level',
                                              'args': {'value': 3}}})], behavior=DEVICES)
        self.assertTrue(has(problems(p), 'value'), problems(p))


class TestTiming(unittest.TestCase):
    def test_hold_needs_a_hold_time(self):
        p = program([page('Home', btn('Go', hold={'do': 'hide_all_popups'}))])
        self.assertTrue(has(problems(p), 'hold_time'), problems(p))

    def test_repeat_needs_both_times(self):
        p = program([page('Home', btn('Go', hold_time=0.5, repeat={'do': 'hide_all_popups'}))])
        self.assertTrue(has(problems(p), 'repeat_time'), problems(p))

    def test_times_must_be_positive(self):
        p = program([page('Home', btn('Go', hold_time=0, hold={'do': 'hide_all_popups'}))])
        self.assertTrue(has(problems(p), 'hold_time'), problems(p))

    def test_times_belong_to_buttons(self):
        p = program([page('Home', {'kind': 'slider', 'name': 'S', 'rect': [0, 0, 90, 300],
                                   'hold_time': 0.5})])
        self.assertTrue(has(problems(p), 'hold_time'), problems(p))

    def test_duration_only_on_show_popup(self):
        p = program([page('Home', btn('Go', press={'do': 'show_page', 'target': 'Home',
                                                   'duration': 5}))])
        self.assertTrue(has(problems(p), 'duration'), problems(p))

    def test_negative_duration_is_a_problem(self):
        p = program([page('Home', btn('Go', press={'do': 'show_popup', 'target': 'Confirm',
                                                   'duration': -1}))],
                    [modal('Confirm')])
        self.assertTrue(has(problems(p), 'duration'), problems(p))


class TestFeedback(unittest.TestCase):
    def test_a_bound_button_needs_an_on_state(self):
        b = btn('Mute', bind='audio.muted')
        del b['on']
        p = program([page('Home', b)], theme={'text': '#FFFFFF', 'raised': '#2E3142'})
        self.assertTrue(has(problems(p), 'on'), problems(p))

    def test_a_bind_path_must_be_dotted_identifiers(self):
        p = program([page('Home', btn('Mute', bind='audio muted'))])
        self.assertTrue(has(problems(p), 'audio muted'), problems(p))

    def test_one_path_bound_to_two_value_types_is_a_problem(self):
        p = program([page('Home', btn('Mute', bind='audio.muted'),
                          {'kind': 'label', 'name': 'L', 'rect': [0, 0, 100, 40],
                           'bind': 'audio.muted'})])
        self.assertTrue(has(problems(p), 'audio.muted'), problems(p))

    def test_bind_and_select_group_on_one_button_is_a_problem(self):
        p = program([page('Home', btn('A', bind='x.a', select_group='S'),
                          btn('B', x=200, select_group='S'))])
        self.assertTrue(has(problems(p), 'select_group', 'bind'), problems(p))

    def test_select_group_members_are_buttons_with_an_on_state(self):
        p = program([page('Home', {'kind': 'label', 'name': 'L', 'rect': [0, 0, 100, 40],
                                   'select_group': 'S'}, btn('B', x=200, select_group='S'))])
        self.assertTrue(has(problems(p), 'select_group'), problems(p))

    def test_select_group_member_without_on_state_is_a_problem(self):
        a = btn('A', select_group='S')
        del a['on']
        p = program([page('Home', a, btn('B', x=200, select_group='S'))],
                    theme={'text': '#FFFFFF', 'raised': '#2E3142'})
        self.assertTrue(has(problems(p), 'select_group', 'on'), problems(p))

    def test_two_paths_that_collide_as_python_names_is_a_problem(self):
        p = program([page('Home', btn('A', bind='audio.muted'),
                          btn('B', x=200, bind='audio_muted'))])
        self.assertTrue(has(problems(p), 'audio'), problems(p))


class TestMirrors(unittest.TestCase):
    def test_identical_mirrors_are_fine(self):
        p = program([page('Home', btn('Go', id=500, nav='Settings'), number=1000),
                     page('Settings', btn('Go', id=500, nav='Settings'),
                          btn('Back', x=200, nav='Home'), number=1100)])
        self.assertEqual(problems(p), [])

    def test_mirrors_with_different_behavior_are_a_problem(self):
        p = program([page('Home', btn('Go', id=500, nav='Settings'), number=1000),
                     page('Settings', btn('Go', id=500, nav='Home'), number=1100)])
        self.assertTrue(has(problems(p), '500'), problems(p))

    def test_mirrors_of_different_kinds_are_a_problem(self):
        p = program([page('Home', btn('Go', id=500, nav='Settings'), number=1000),
                     page('Settings', {'kind': 'label', 'name': 'L', 'id': 500,
                                       'rect': [0, 0, 100, 40]},
                          btn('Back', x=200, nav='Home'), number=1100)])
        self.assertTrue(has(problems(p), '500'), problems(p))


class TestConfirmation(unittest.TestCase):
    CALL = {'do': 'call', 'device': 'codec', 'op': 'hang_up', 'costly': True}

    def test_a_costly_call_outside_a_modal_is_a_problem(self):
        p = program([page('Home', btn('End', press=self.CALL))], behavior=DEVICES)
        self.assertTrue(has(problems(p), 'costly', 'modal'), problems(p))

    def test_costly_belongs_to_calls(self):
        p = program([page('Home', btn('Go', press={'do': 'show_page', 'target': 'Home',
                                                   'costly': True}))])
        self.assertTrue(has(problems(p), 'costly'), problems(p))

    def test_a_confirmation_without_a_cancel_is_a_problem(self):
        p = program([page('Home', btn('End', nav='Confirm'))],
                    [modal('Confirm', btn('Yes', x=200, press=[
                        self.CALL, {'do': 'hide_popup', 'target': 'Confirm'}]))],
                    behavior=DEVICES)
        self.assertTrue(has(problems(p), 'cancel'), problems(p))

    def test_a_confirmation_with_a_cancel_is_clean(self):
        p = program([page('Home', btn('End', nav='Confirm'))],
                    [modal('Confirm',
                           btn('Yes', x=200, press=[self.CALL,
                                                    {'do': 'hide_popup', 'target': 'Confirm'}]),
                           btn('No', x=400, press={'do': 'hide_popup', 'target': 'Confirm'}))],
                    behavior=DEVICES)
        self.assertEqual(problems(p), [])


class TestNavigationGraph(unittest.TestCase):
    def test_an_unreachable_page_is_a_problem(self):
        p = program([page('Home', btn('Go', nav='Home'), number=1000),
                     page('Orphan', btn('Back', nav='Home'), number=1100)])
        self.assertTrue(has(problems(p), 'Orphan'), problems(p))

    def test_reached_by_program_excuses_it(self):
        p = program([page('Home', btn('Go', nav='Home'), number=1000),
                     page('Orphan', btn('Back', nav='Home'), number=1100,
                          reached_by='program')])
        self.assertEqual(problems(p), [])

    def test_an_unknown_reached_by_is_a_problem(self):
        p = program([page('Home', btn('Go', nav='Home'), reached_by='magic')])
        self.assertTrue(has(problems(p), 'reached_by'), problems(p))

    def test_an_inactivity_target_is_reachable(self):
        p = program([page('Home', btn('Go', nav='Home'), number=1000),
                     page('Idle', btn('Back', nav='Home'), number=1100)],
                    behavior={'inactivity': {'seconds': 300,
                                             'do': {'do': 'show_page', 'target': 'Idle'}}})
        self.assertEqual(problems(p), [])

    def test_a_layout_only_spec_is_not_graph_checked(self):
        # A spec with no behavior at all still gets a handoff; three unlinked
        # pages there are a layout, not a broken program.
        p = program([page('A', btn('x'), number=1000), page('B', btn('y'), number=1100)])
        self.assertEqual(problems(p), [])
        self.assertTrue(has(notes(p), 'no behavior'), notes(p))

    def test_a_modal_with_no_way_out_is_a_problem(self):
        p = program([page('Home', btn('Ask', nav='Trap'))],
                    [modal('Trap', btn('Nothing', x=200, press={'do': 'show_page',
                                                                'target': 'Home'}))])
        self.assertTrue(has(problems(p), 'Trap', 'close'), problems(p))

    def test_a_timed_modal_closes_itself(self):
        p = program([page('Home', btn('Ask', press={'do': 'show_popup', 'target': 'Toast',
                                                    'duration': 3}))],
                    [modal('Toast')])
        self.assertEqual(problems(p), [])

    def test_a_dead_end_page_is_a_note(self):
        p = program([page('Home', btn('Go', nav='End'), number=1000),
                     page('End', btn('Stay', nav='End'), number=1100)])
        self.assertTrue(has(notes(p), 'End', 'dead end'), notes(p))


class TestNotes(unittest.TestCase):
    def test_a_button_that_does_nothing_is_noted(self):
        p = program([page('Home', btn('Go', nav='Home'), btn('Idle', x=200))])
        self.assertTrue(has(notes(p), 'Idle'), notes(p))

    def test_an_unused_device_is_noted(self):
        p = program([page('Home', btn('Go', nav='Home'))], behavior=DEVICES)
        self.assertTrue(has(notes(p), 'codec'), notes(p))

    def test_a_one_member_select_group_is_noted(self):
        p = program([page('Home', btn('Go', select_group='S', nav='Home'))])
        self.assertTrue(has(notes(p), "'S'"), notes(p))

    def test_the_default_alias_is_noted(self):
        p = program([page('Home', btn('Go', nav='Home'))])
        self.assertTrue(has(notes(p), 'TLP1'), notes(p))

    def test_layout_problems_come_first(self):
        # behavior check runs Panel.check() too: a spec that cannot be built
        # cannot be programmed.
        p = program([page('Home', btn('Go', nav='Home', rect=[1270, 0, 100, 80]))])
        self.assertTrue(has(problems(p), 'leaves the'), problems(p))


if __name__ == '__main__':
    unittest.main(verbosity=2)
