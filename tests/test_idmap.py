"""Tests for the ID map: every addressable control, where it is, what it does.

The navigation checks each stand in for something that would otherwise show up
on a panel in a room - a button that flips to a page that does not exist, a
popup that cannot appear where it is shown, a page nothing reaches. Nothing
here needs Windows or GUI Designer.

    python tests/test_idmap.py
"""
import csv
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.idmap import IdMap, load  # noqa: E402
from gdl.spec import Panel  # noqa: E402

EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'examples', 'huddle-functions.json')
THEME = {'text': '#FFFFFF', 'raised': '#2E3142', 'accent': '#3D8BFD'}


def btn(name, x=0, **kw):
    return dict({'kind': 'button', 'name': name, 'text': name, 'rect': [x, 700, 100, 80],
                 'fill': 'raised', 'on': 'accent'}, **kw)


def ref(group, x=0):
    return {'kind': 'popup_ref', 'name': 'Ref ' + group, 'rect': [x, 0, 300, 200],
            'group': group}


def page(name, *controls, number=1000, **kw):
    return dict({'name': name, 'number': number, 'controls': list(controls)}, **kw)


def popup(name, *controls, group=None, modal=False, number=9100):
    p = {'name': name, 'number': number, 'controls': list(controls)}
    if modal:
        p['modal'] = True
    else:
        p.update(group=group, size=[300, 200])
    return p


def idmap(pages, popups=(), **top):
    spec = {'name': 'T', 'size': [1280, 800], 'theme': THEME,
            'pages': list(pages), 'popups': list(popups)}
    spec.update(top)
    return IdMap(Panel(spec))


def problems(m):
    return m.check()[0]


def notes(m):
    return m.check()[1]


def has(msgs, *words):
    return any(all(w in m for w in words) for m in msgs)


class TestVocabulary(unittest.TestCase):
    def test_a_clean_nav_spec_has_no_problems(self):
        m = idmap([page('Home', btn('Go', nav='Settings')),
                   page('Settings', btn('Back', nav='Home'), number=1100)])
        self.assertEqual(problems(m), [])
        self.assertEqual(m.nav_edges(), {('Home', 'Settings'), ('Settings', 'Home')})

    def test_nav_resolves_to_a_page_or_a_popup(self):
        m = idmap([page('Home', btn('Ask', nav='Confirm'), btn('Me', x=200, nav='Home'))],
                  [popup('Confirm', btn('Close', x=10, rect=[10, 10, 100, 80],
                                        does='Closes this popup.'), modal=True)])
        kinds = {r['name']: r['nav'] for r in m.controls if r['nav']}
        self.assertEqual(kinds, {'Ask': ('popup', 'Confirm'), 'Me': ('page', 'Home')})

    def test_nav_to_an_unknown_name_is_a_problem(self):
        m = idmap([page('Home', btn('Go', nav='Nowhere'))])
        self.assertTrue(has(problems(m), 'Nowhere'), problems(m))

    def test_nav_belongs_on_a_button(self):
        m = idmap([page('Home', {'kind': 'label', 'name': 'L', 'rect': [0, 0, 100, 40],
                                 'nav': 'Home'})])
        self.assertTrue(has(problems(m), 'nav', 'label'), problems(m))

    def test_does_must_be_a_sentence(self):
        m = idmap([page('Home', btn('Go', does=['mute']))])
        self.assertTrue(has(problems(m), 'does'), problems(m))

    def test_a_shape_has_no_id_to_map(self):
        m = idmap([page('Home', {'kind': 'panel', 'name': 'Bg', 'rect': [0, 0, 100, 40],
                                 'fill': 'raised', 'does': 'Looks nice.'})])
        self.assertTrue(has(problems(m), 'panel'), problems(m))

    def test_any_addressable_kind_may_say_what_it_does(self):
        m = idmap([page('Home', {'kind': 'label', 'name': 'L', 'rect': [0, 0, 100, 40],
                                 'does': 'Shows the call status.'},
                        {'kind': 'slider', 'name': 'S', 'rect': [200, 0, 100, 400],
                         'does': 'Sets volume.'})])
        self.assertEqual(problems(m), [])

    def test_panel_wide_functions_are_sentences(self):
        self.assertTrue(has(problems(idmap([page('Home', btn('Go'))], does=[3])), 'does'))
        self.assertEqual(problems(idmap([page('Home', btn('Go'))], does='Idle returns home.')),
                         [])

    def test_layout_problems_come_first(self):
        m = idmap([page('Home', btn('Go', rect=[1270, 0, 100, 80]))])
        self.assertTrue(has(problems(m), 'leaves the'), problems(m))


class TestShowability(unittest.TestCase):
    def test_a_grouped_popup_shown_from_a_page_without_its_reference(self):
        m = idmap([page('Home', btn('Open', nav='A')),
                   page('Other', ref('g1'), btn('Back', x=400, nav='Home'), number=1100,
                        reached_by='program')],
                  [popup('A', group='g1')])
        self.assertTrue(has(problems(m), "'A'", "'Home'"), problems(m))

    def test_a_popup_shown_from_a_popup_needs_the_reference_on_the_page_beneath(self):
        m = idmap([page('Home', ref('g1'), btn('Open', nav='A')),
                   page('Elsewhere', ref('g2'), btn('Back', x=400, nav='Home'), number=1100,
                        reached_by='program')],
                  [popup('A', btn('ShowB', rect=[10, 10, 100, 80], nav='B'), group='g1'),
                   popup('B', group='g2', number=9200)])
        self.assertTrue(has(problems(m), "'B'", "'Home'"), problems(m))

    def test_with_the_reference_beneath_it_is_clean(self):
        m = idmap([page('Home', ref('g1'), ref('g2', x=400), btn('Open', nav='A'))],
                  [popup('A', btn('ShowB', rect=[10, 10, 100, 80], nav='B'), group='g1'),
                   popup('B', group='g2', number=9200)])
        self.assertEqual(problems(m), [])


class TestMirrors(unittest.TestCase):
    def test_identical_mirrors_are_fine(self):
        m = idmap([page('Home', btn('Go', id=500, nav='Settings')),
                   page('Settings', btn('Go', id=500, nav='Settings'),
                        btn('Back', x=200, nav='Home'), number=1100)])
        self.assertEqual(problems(m), [])
        rows = m.data()['controls']
        self.assertEqual([len(c['at']) for c in rows if c['id'] == 500], [2])

    def test_mirrors_that_do_different_things_are_a_problem(self):
        m = idmap([page('Home', btn('Go', id=500, nav='Settings')),
                   page('Settings', btn('Go', id=500, nav='Home'), number=1100)])
        self.assertTrue(has(problems(m), '500'), problems(m))

    def test_mirrors_of_different_kinds_are_a_problem(self):
        m = idmap([page('Home', btn('Go', id=500, nav='Settings')),
                   page('Settings', {'kind': 'label', 'name': 'L', 'id': 500,
                                     'rect': [0, 0, 100, 40]},
                        btn('Back', x=200, nav='Home'), number=1100)])
        self.assertTrue(has(problems(m), '500'), problems(m))


def stateful(name, states, x=0, **kw):
    b = btn(name, x, states=states, **kw)
    del b['on']
    return b


FOUR = ['Off', {'name': 'Warming', 'fill': '#242634'},
        {'name': 'On', 'fill': 'accent'}, {'name': 'Cooling', 'fill': '#242634', 'text': 'Cool'}]


class TestStates(unittest.TestCase):
    """A program sets a button's feedback by state INDEX, so the map lists
    every state in order - the index is the position."""

    def test_named_states_are_listed_in_order(self):
        m = idmap([page('Home', stateful('Display', FOUR, press='On'))])
        row = m.data()['controls'][0]
        self.assertEqual(row['states'], ['Off', 'Warming', 'On', 'Cooling'])
        self.assertEqual(row['press'], 'On')

    def test_on_is_off_and_on(self):
        row = idmap([page('Home', btn('Go'))]).data()['controls'][0]
        self.assertEqual(row['states'], ['Off', 'On'])
        self.assertEqual(row['press'], 'On')

    def test_a_button_without_feedback_lists_none(self):
        """Its states are whatever the donor button had, which the spec never
        named - so the map does not claim to know them."""
        b = btn('Go')
        del b['on']
        row = idmap([page('Home', b)]).data()['controls'][0]
        self.assertIsNone(row['states'])

    def test_only_buttons_carry_states(self):
        m = idmap([page('Home', {'kind': 'label', 'name': 'L', 'text': 'L',
                                 'rect': [0, 0, 200, 40]})])
        self.assertNotIn('states', m.data()['controls'][0])

    def test_mirrors_with_different_states_are_a_problem(self):
        """GUI Designer gives every control sharing an ID the same states."""
        m = idmap([page('Home', stateful('D', FOUR, id=500), btn('Go', x=200, nav='S')),
                   page('S', stateful('D', FOUR[:3], id=500), btn('Back', x=200, nav='Home'),
                        number=1100)])
        self.assertTrue(has(problems(m), '500', 'states'), problems(m))

    def test_a_mirror_differing_in_both_function_and_states_reports_both(self):
        m = idmap([page('Home', stateful('D', FOUR, id=500, does='Powers it.'),
                        btn('Go', x=200, nav='S')),
                   page('S', stateful('D', FOUR[:3], id=500, does='Something else.'),
                        btn('Back', x=200, nav='Home'), number=1100)])
        self.assertTrue(has(problems(m), '500', 'functions'), problems(m))
        self.assertTrue(has(problems(m), '500', 'states'), problems(m))

    def test_the_tables_show_the_states(self):
        d = tempfile.mkdtemp()
        try:
            idmap([page('Home', stateful('Display', FOUR, press='On'))]).write(d)
            with open(os.path.join(d, 'idmap.csv'), encoding='utf-8', newline='') as fh:
                row = next(csv.DictReader(fh))
            self.assertEqual(row['States'], '0 Off, 1 Warming, 2 On, 3 Cooling')
            self.assertEqual(row['Press'], 'On')
            with open(os.path.join(d, 'idmap.md'), encoding='utf-8') as fh:
                self.assertIn('0 Off, 1 Warming, 2 On, 3 Cooling', fh.read())
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_the_caption_is_the_first_states(self):
        s = [{'name': 'Idle', 'text': 'Start'}, {'name': 'Busy', 'fill': 'accent'}]
        row = idmap([page('Home', stateful('Go', s))]).data()['controls'][0]
        self.assertEqual(row['at'][0]['caption'], 'Start')


class TestNavigationGraph(unittest.TestCase):
    def test_an_unreachable_page_is_a_problem(self):
        m = idmap([page('Home', btn('Go', nav='Home')),
                   page('Orphan', btn('Back', nav='Home'), number=1100)])
        self.assertTrue(has(problems(m), 'Orphan'), problems(m))

    def test_reached_by_program_excuses_it(self):
        m = idmap([page('Home', btn('Go', nav='Home')),
                   page('Orphan', btn('Back', nav='Home'), number=1100,
                        reached_by='program')])
        self.assertEqual(problems(m), [])

    def test_an_unknown_reached_by_is_a_problem(self):
        m = idmap([page('Home', btn('Go', nav='Home'), reached_by='magic')])
        self.assertTrue(has(problems(m), 'reached_by'), problems(m))

    def test_a_spec_with_no_navigation_is_not_graph_checked(self):
        m = idmap([page('A', btn('x')), page('B', btn('y'), number=1100)])
        self.assertEqual(problems(m), [])

    def test_a_dead_end_page_is_a_note(self):
        m = idmap([page('Home', btn('Go', nav='End')),
                   page('End', btn('Stay', nav='End'), number=1100)])
        self.assertTrue(has(notes(m), 'End', 'dead end'), notes(m))

    def test_an_undescribed_button_is_noted_once_any_function_is(self):
        m = idmap([page('Home', btn('Go', nav='Home'), btn('Idle', x=200))])
        self.assertTrue(has(notes(m), 'Idle', 'not described'), notes(m))
        self.assertEqual(notes(idmap([page('Home', btn('Go'), btn('Idle', x=200))])), [])


class TestOutput(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_the_example_maps_every_addressable_control_once(self):
        m = load(EXAMPLE)
        self.assertEqual(m.check()[0], [])
        m.write(self.dir)
        with open(os.path.join(self.dir, 'idmap.json'), encoding='utf-8') as fh:
            d = json.load(fh)
        ids = [c['id'] for c in d['controls']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 24)
        end = next(c for c in d['controls'] if c['at'][0]['name'] == 'EndCall')
        self.assertEqual(end['function'], 'Ends the call.')
        help_btn = next(c for c in d['controls'] if c['at'][0]['name'] == 'HelpBtn')
        self.assertEqual(help_btn['function'], "Shows page 'Huddle Help'")

    def test_pages_carry_no_number(self):
        # Build does not keep a page's number, so a map that listed one would
        # hand the programmer an address that does not exist.
        load(EXAMPLE).write(self.dir)
        with open(os.path.join(self.dir, 'idmap.json'), encoding='utf-8') as fh:
            d = json.load(fh)
        for pg in d['pages'] + d['popups']:
            self.assertNotIn('number', pg)

    def test_the_csv_is_one_row_per_id(self):
        load(EXAMPLE).write(self.dir)
        with open(os.path.join(self.dir, 'idmap.csv'), encoding='utf-8', newline='') as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 24)
        vol = next(r for r in rows if r['Control'] == 'VolumeSlider')
        self.assertEqual((vol['Type'], vol['Page']), ('Slider', 'Huddle Home'))

    def test_a_pipe_in_a_name_does_not_break_the_tables(self):
        m = idmap([page('Home | Main', btn('Go | Now', nav='Home | Main'))])
        m.write(self.dir)
        with open(os.path.join(self.dir, 'idmap.md'), encoding='utf-8') as fh:
            rows = [l for l in fh.read().splitlines() if l.startswith('| ')]
        for row in rows:
            self.assertIn(len(re.split(r'(?<!\\)\|', row)[1:-1]), (3, 6), row)


if __name__ == '__main__':
    unittest.main(verbosity=2)
