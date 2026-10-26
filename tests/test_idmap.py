"""Tests for the ID map: every addressable control, where it is, what it does.

The navigation checks each stand in for something that would otherwise show up
on a panel in a room - a button that flips to a page that does not exist, a
popup that cannot appear where it is shown, a page nothing reaches. Nothing
here needs Windows or GUI Designer.

    python tests/test_idmap.py
"""
import csv
import io
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
    # 18 pt: no panel's type floor here is above the 525's.
    return dict({'kind': 'button', 'name': name, 'text': name, 'rect': [x, 700, 100, 80],
                 'fill': 'raised', 'on': 'accent', 'size': 18}, **kw)


def ref(group, x=0):
    return {'kind': 'popup_ref', 'name': 'Ref ' + group, 'rect': [x, 0, 300, 200],
            'group': group}


def page(name, *controls, number=1000, **kw):
    return dict({'name': name, 'number': number, 'controls': list(controls)}, **kw)


def popup(name, *controls, group=None, modal=False, number=9100, **kw):
    p = dict({'name': name, 'number': number, 'controls': list(controls)}, **kw)
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

    def test_an_icons_caption_is_its_name_not_its_glyph(self):
        """An icon's caption is a private-use character, which a spreadsheet
        shows blank: the map says which icon it is."""
        spec = {'name': 'T', 'size': [1280, 800], 'family': 'Afterburn',
                'theme': {'text': '#FFFFFF'}, 'pages': [{'name': 'P', 'number': 1000, 'controls': [
                    {'kind': 'button', 'name': 'Tv', 'id': 11, 'rect': [0, 0, 160, 160],
                     'icon': 'U+E908'},
                    {'kind': 'button', 'name': 'Mic', 'id': 12, 'rect': [200, 0, 160, 160],
                     'states': [{'name': 'Off', 'icon': 'U+E92F'}, {'name': 'On', 'icon': 'U+E930'}]}]}]}
        d = IdMap(Panel(spec)).data()
        self.assertEqual({c['at'][0]['name']: c['at'][0]['caption'] for c in d['controls']},
                         {'Tv': 'icon: U+E908', 'Mic': 'icon: U+E92F'})

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
            self.assertIn(len(re.split(r'(?<!\\)\|', row)[1:-1]), (4, 6), row)

    def test_the_csv_flattens_a_captions_line_breaks(self):
        """A caption broken over two lines is one cell a spreadsheet shows on
        one row; the JSON keeps the break, which is what the panel draws."""
        load_spec = idmap([page('Home', btn('Laptop', text='Lap\ntop'))])
        load_spec.write(self.dir)
        with open(os.path.join(self.dir, 'idmap.csv'), encoding='utf-8', newline='') as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[0]['Caption'], 'Lap top')
        with open(os.path.join(self.dir, 'idmap.json'), encoding='utf-8') as fh:
            self.assertEqual(json.load(fh)['controls'][0]['at'][0]['caption'], 'Lap\ntop')


class TestAPagesPurpose(unittest.TestCase):
    """A Page's `does` says what the page is for - the confirm window's
    question, a source's page - and the map carries it beside the page, where
    the programmer reads how the page is shown."""

    def test_a_page_and_a_popup_say_what_they_are_for(self):
        m = idmap([page('Home', btn('Go', does='Starts.'), does='Where every meeting starts.')],
                  [popup('Confirm', btn('Yes', does='Powers off.'), modal=True,
                         does='Asks before the room powers off.')])
        self.assertEqual(problems(m), [])
        d = m.data()
        self.assertEqual(d['pages'][0]['does'], 'Where every meeting starts.')
        self.assertEqual(d['popups'][0]['does'], 'Asks before the room powers off.')
        md = m._markdown(d)
        self.assertTrue(any(l.startswith('| Home |') and l.rstrip().endswith('| Where every meeting starts. |')
                            for l in md.splitlines()), md)

    def test_a_page_that_says_nothing_has_no_purpose(self):
        d = idmap([page('Home', btn('Go'))]).data()
        self.assertIsNone(d['pages'][0]['does'])

    def test_a_pages_purpose_is_a_sentence(self):
        for bad in ('', 5):
            with self.subTest(does=bad):
                self.assertTrue(has(problems(idmap([page('Home', btn('Go'), does=bad)])), 'Home', 'does'))

    def test_every_panels_map_carries_it_per_panel(self):
        from gdl.idmap import IdMap as M, combine
        big = panel_spec('TLP1035T', [1280, 800], [page('Home', btn('Go', id=1001, does='Starts.'),
                                                             does='Where it starts.')])
        small = panel_spec('TLP725T', [1024, 600], [page('Home', btn('Go', id=1001, does='Starts.'),
                                                              does='Where it starts.')])
        m = combine({'TLP1035T': M(Panel(big)), 'TLP725T': M(Panel(small))})
        self.assertEqual([p['pages'][0]['does'] for p in m['panels']], ['Where it starts.'] * 2)


class TestRetiredIds(unittest.TestCase):
    """An ID an earlier delivery gave a control that is gone stays out of use,
    so a program still addressing it reaches nothing rather than another
    control (`_retired`, which translate writes from the previous map)."""

    RETIRED = [{'id': 1001, 'was': 'Home / Display'}]

    def test_no_control_is_numbered_into_a_retired_id(self):
        spec = {'name': 'T', 'size': [1280, 800], 'theme': THEME, '_retired': self.RETIRED,
                'pages': [page('Home', btn('Laptop'), btn('Camera', x=200))]}
        self.assertEqual([c['id'] for c in Panel(spec).pages[0]['controls']], [1002, 1003])

    def test_the_map_lists_them_and_says_why(self):
        m = idmap([page('Home', btn('Laptop'))], _retired=self.RETIRED)
        d = m.data()
        self.assertEqual(d['retired'], self.RETIRED)
        md = m._markdown(d)
        self.assertIn('## Retired IDs', md)
        self.assertIn('| 1001 | Home / Display |', md)

    def test_a_map_with_none_lists_none(self):
        m = idmap([page('Home', btn('Laptop'))])
        self.assertEqual(m.data()['retired'], [])
        self.assertNotIn('Retired', m._markdown(m.data()))



def panel_spec(model, size, pages, popups=()):
    return {'name': 'T', 'model': model, 'size': size, 'theme': THEME, 'pages': list(pages),
            'popups': list(popups), 'start_page': 'Home'}


class TestPanels(unittest.TestCase):
    """One ID map for every panel a canvas builds: a row per ID, and where the
    control is on each panel."""

    def maps(self, drop=None, rename=None):
        from gdl.idmap import IdMap as M
        def at(x):
            return [x, 400, 100, 80]
        big = panel_spec('TLP1035T', [1280, 800], [page('Home', btn('Laptop', id=1001, does='Routes it.'),
                                                             btn('Help', x=200, id=1002, does='Helps.'))])
        small_controls = [btn('Help', rect=at(200), id=1002, does='Helps.'),
                          ref('Home Sources'),
                          btn('Sources Next', rect=at(400), id=50001, derived=True, nav='Home Sources')]
        laptop = btn(rename or 'Laptop', rect=[0, 0, 100, 80], id=1001, does='Routes it.')
        small = panel_spec('TLP725T', [1024, 600],
                           [page('Home', *small_controls)],
                           [] if drop else [popup('Home Sources', laptop, group='Home Sources')])
        small['popups'] and small['popups'][0].update(reached_by='program')
        return {'TLP1035T': M(Panel(big)), 'TLP725T': M(Panel(small))}

    def test_one_map_has_a_column_per_panel(self):
        from gdl.idmap import write_panels
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        write_panels(self.maps(), d)
        with open(os.path.join(d, 'idmap.json'), encoding='utf-8') as fh:
            m = json.load(fh)
        self.assertEqual([p['model'] for p in m['panels']], ['TLP1035T', 'TLP725T'])
        laptop = next(c for c in m['controls'] if c['id'] == 1001)
        self.assertEqual(laptop['panels']['TLP1035T'][0]['container'], 'Home')
        self.assertEqual(laptop['panels']['TLP725T'][0]['container'], 'Home Sources')
        with open(os.path.join(d, 'idmap.csv'), encoding='utf-8') as fh:
            header = next(csv.reader(fh))
        self.assertIn('TLP1035T', header)
        self.assertIn('TLP725T', header)

    def test_derived_navigation_is_mapped_and_marked(self):
        """Previous, Next, Back and a group's opener are buttons the program
        must handle - a .gdl carries no behaviour - so they are in the map,
        marked, on the panels that have them."""
        from gdl.idmap import combine
        m = combine(self.maps())
        nxt = next(c for c in m['controls'] if c['id'] == 50001)
        self.assertTrue(nxt['derived'])
        self.assertEqual(sorted(nxt['panels']), ['TLP725T'])

    def test_what_a_control_does_differently_is_said_per_panel(self):
        """A Group's Next shows a popup on a mid-size panel and a page on a
        small one, under one ID; the row read 'Shows popup' for both."""
        from gdl.idmap import IdMap as M, combine
        nxt = btn('Sources Next', rect=[400, 400, 100, 80], id=50001, derived=True, nav='Home Sources 2')
        mid = panel_spec('TLP525T', [800, 480], [page('Home', ref('Home Sources'), nxt)],
                         [popup('Home Sources', btn('Laptop', id=1001, does='Routes it.'), group='Home Sources'),
                          popup('Home Sources 2', btn('PC', id=1002, does='Routes it.'), group='Home Sources')])
        small = panel_spec('TLP320M', [320, 240], [page('Home', dict(nxt, rect=[200, 150, 80, 60])),
                                                   page('Home Sources 2', btn('PC', id=1002, does='Routes it.'))])
        row = next(c for c in combine({'TLP525T': M(Panel(mid)), 'TLP320M': M(Panel(small))})['controls']
                   if c['id'] == 50001)
        self.assertIn('TLP525T', row['function'])
        self.assertIn('TLP320M', row['function'])
        self.assertNotEqual(row['functions']['TLP525T'], row['functions']['TLP320M'])

    def test_a_listed_panel_with_no_spec_is_refused(self):
        """The specs list every panel; one missing was dropped from the map
        silently, and the build then claimed every panel."""
        from gdl.idmap import load_panels
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        spec = panel_spec('TLP725T', [1024, 600], [page('Home', btn('Help', id=1002, does='Helps.'))])
        spec['_panels'] = ['TLP1035T', 'TLP725T']
        os.makedirs(os.path.join(d, 'TLP725T'))
        with open(os.path.join(d, 'TLP725T', 'spec.json'), 'w', encoding='utf-8') as fh:
            json.dump(spec, fh)
        with self.assertRaises(ValueError) as e:
            load_panels(d)
        self.assertIn('TLP1035T', str(e.exception))

    def test_a_canvas_control_missing_on_one_panel_is_a_problem(self):
        from gdl.idmap import check_panels
        probs = check_panels(self.maps(drop=True))
        self.assertTrue(any('1001' in p and 'TLP725T' in p for p in probs), probs)

    def test_a_control_a_panels_layout_left_off_by_name_may_be_absent(self):
        """A page's `left` names what that panel's layout has no place for (a
        hub's footer clock) - named on the canvas, so not dropped silently:
        absent there, it is no problem. Not listed, it still is one."""
        from gdl.idmap import IdMap as M, check_panels
        big = panel_spec('TLP1035T', [1280, 800], [page('Home', btn('Clock', id=1001, does='Tells the time.'),
                                                             btn('Help', x=200, id=1002, does='Helps.'))])
        for left, clean in ((['Clock'], True), (['Date Time'], False)):
            with self.subTest(left=left):
                hub = panel_spec('TLP525T', [800, 480], [page('Home', btn('Help', rect=[200, 300, 100, 80], id=1002,
                                                                           does='Helps.'), left=left)])
                probs = check_panels({'TLP1035T': M(Panel(big)), 'TLP525T': M(Panel(hub))})
                if clean:
                    self.assertEqual(probs, [])
                else:
                    self.assertTrue(any('1001' in p and 'TLP525T' in p for p in probs), probs)

    def test_one_id_is_one_control_on_every_panel(self):
        from gdl.idmap import check_panels
        probs = check_panels(self.maps(rename='Notebook'))
        self.assertTrue(any('1001' in p and 'Notebook' in p for p in probs), probs)

    def test_one_control_names_its_states_alike_on_every_panel(self):
        """The map numbers a control's states once. Mach's PC tab on the
        1035 called its second state Selected and its Select a Source tile on
        the 525 called it On: both built, and the ID map's check of the 525's
        build failed on the names."""
        from gdl.idmap import IdMap as M, check_panels

        def pc(second, **kw):
            c = btn('PC', id=1001, does='Shows the PC.',
                    states=[{'name': 'Off'}, {'name': second, 'fill': '#FFFFFF'}], **kw)
            del c['on']
            return c
        big = panel_spec('TLP1035T', [1280, 800], [page('Home', pc('Selected'))])
        for second, clean in (('Selected', True), ('On', False)):
            with self.subTest(second=second):
                hub = panel_spec('TLP525T', [800, 480], [page('Home', pc(second, rect=[200, 300, 100, 80]))])
                probs = check_panels({'TLP1035T': M(Panel(big)), 'TLP525T': M(Panel(hub))})
                if clean:
                    self.assertEqual(probs, [])
                else:
                    self.assertTrue(any('1001' in p and 'states' in p for p in probs), probs)

    def test_a_slider_may_be_a_level_on_a_panel_that_cannot_build_one(self):
        """The 525's and 320's seeds have no slider, so volume is a level there
        with Up and Down (plan ruling 6). It keeps the slider's ID - the program
        sets it the same way - and the map says what it is on each panel."""
        from gdl.idmap import IdMap as M, check_panels, combine
        slider = {'kind': 'slider', 'name': 'Volume', 'rect': [0, 0, 60, 300], 'id': 1010,
                  'does': 'Sets volume.'}
        level = dict(slider, kind='level')
        maps = {'TLP1035T': M(Panel(panel_spec('TLP1035T', [1280, 800], [page('Home', slider)]))),
                'TLP525T': M(Panel(panel_spec('TLP525T', [800, 480], [page('Home', level)])))}
        self.assertEqual(check_panels(maps), [])
        row = next(c for c in combine(maps)['controls'] if c['id'] == 1010)
        self.assertEqual(row['types'], {'TLP1035T': 'Slider', 'TLP525T': 'Level'})

    def mirrored(self, on_725=True):
        """Shockwave's tab and the caption mirror the 1035's layout draws
        under its glyph with its ID (its frame's `twin`); the 725 draws the
        tab alone."""
        from gdl.idmap import IdMap as M

        def tab(**kw):
            c = btn('PC', id=1001, nav='Home', does='Routes the PC.',
                    states=[{'name': 'Off'}, {'name': 'On', 'fill': '#FFFFFF'}], **kw)
            del c['on']
            return c
        twin = btn('PC Caption', rect=[0, 755, 100, 25], id=1001, nav='Home', does='Routes the PC.',
                   derived=True, states=[{'name': 'Off', 'fill': 'none'}, {'name': 'On', 'fill': 'none'}])
        del twin['on']
        helpb = btn('Help', rect=[200, 500, 100, 80], id=1002, does='Helps.')
        big = panel_spec('TLP1035T', [1280, 800], [page('Home', tab(), twin, helpb)])
        small = panel_spec('TLP725T', [1024, 600], [page('Home', *([tab(rect=[0, 500, 100, 80])] if on_725 else []),
                                                         helpb)])
        return {'TLP1035T': M(Panel(big)), 'TLP725T': M(Panel(small))}

    def test_a_mirror_is_listed_with_its_control(self):
        """One row, the control's: not derived, where the 725 has only the
        tab; the mirror one of its places on the 1035, marked a mirror."""
        from gdl.idmap import check_panels, combine, write_panels
        maps = self.mirrored()
        self.assertEqual(check_panels(maps), [])
        row = next(c for c in combine(maps)['controls'] if c['id'] == 1001)
        self.assertNotIn('derived', row)
        self.assertEqual([(a['name'], a.get('mirror', False)) for a in row['panels']['TLP1035T']],
                         [('PC', False), ('PC Caption', True)])
        self.assertEqual([a['name'] for a in row['panels']['TLP725T']], ['PC'])
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        write_panels(maps, d)
        with open(os.path.join(d, 'idmap.md'), encoding='utf-8') as fh:
            self.assertIn('Home (mirror: PC Caption)', fh.read())

    def test_a_control_with_a_mirror_is_still_on_every_panel(self):
        """A mirror the layout derived does not make its control one: the tab
        missing on the 725 is still named."""
        from gdl.idmap import check_panels
        probs = check_panels(self.mirrored(on_725=False))
        self.assertTrue(any('1001' in p and 'TLP725T' in p for p in probs), probs)

    def test_the_maps_agree_and_check_clean(self):
        from gdl.idmap import check_panels
        self.assertEqual(check_panels(self.maps()), [])

    def test_rows_are_in_id_order(self):
        """A programmer looks a control up by its ID: the rows were in the
        order first met, a page's controls in drawing order and each panel's
        derived ones after the first panel's."""
        from gdl.idmap import IdMap as M, combine
        big = panel_spec('TLP1035T', [1280, 800], [page('Home', btn('Help', id=1002, does='Helps.'),
                                                             btn('Laptop', x=200, id=1001, does='Routes it.'))])
        small = panel_spec('TLP725T', [1024, 600], [page('Home', btn('Help', id=1002, does='Helps.'),
                                                              btn('Laptop', x=200, id=1001, does='Routes it.'),
                                                              btn('Home Back', x=400, id=50001, derived=True,
                                                                  does='Goes back.'))])
        rows = combine({'TLP1035T': M(Panel(big)), 'TLP725T': M(Panel(small))})['controls']
        self.assertEqual([c['id'] for c in rows], [1001, 1002, 50001])

    def test_a_copy_named_otherwise_is_named_in_its_panels_column(self):
        """Copies of one ID may carry other names - the client's Room Off
        confirm is mirrored onto a second popup - and the Control column
        showed the first panel's first copy only."""
        from gdl.idmap import IdMap as M, write_panels
        off = dict(does='Powers the room off.', id=81)
        big = panel_spec('TLP1035T', [1280, 800], [page('Home', btn('Room Off', **off))],
                         [popup('Settings', btn('Power Off', **off), modal=True, reached_by='program')])
        small = panel_spec('TLP725T', [1024, 600], [page('Home', btn('Room Off', **off))])
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        write_panels({'TLP1035T': M(Panel(big)), 'TLP725T': M(Panel(small))}, d)
        with open(os.path.join(d, 'idmap.csv'), encoding='utf-8', newline='') as fh:
            row = next(r for r in csv.DictReader(fh) if r['ID'] == '81')
        self.assertEqual((row['Control'], row['TLP1035T'], row['TLP725T']),
                         ('Room Off', 'Home; Settings (Power Off)', 'Home'))
        with open(os.path.join(d, 'idmap.md'), encoding='utf-8') as fh:
            self.assertIn('Home; Settings (Power Off)', fh.read())

    def test_every_panels_csv_flattens_a_captions_line_breaks(self):
        from gdl.idmap import IdMap as M, write_panels
        lap = btn('Laptop', id=1001, text='Lap\ntop', does='Routes it.')
        maps = {m: M(Panel(panel_spec(m, size, [page('Home', lap)])))
                for m, size in (('TLP1035T', [1280, 800]), ('TLP725T', [1024, 600]))}
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        write_panels(maps, d)
        with open(os.path.join(d, 'idmap.csv'), encoding='utf-8', newline='') as fh:
            self.assertEqual(next(csv.DictReader(fh))['Caption'], 'Lap top')


def mapped(pages, popups=(), **top):
    """The map data() of a spec of these pages and popups."""
    return idmap(pages, popups, **top).data()


class TestDiff(unittest.TestCase):
    """What changed between two deliveries' maps, as a program written against
    the first meets it (`python -m gdl.idmap diff`, and changes.md)."""

    def old(self, **swap):
        """Home holds Laptop, Display (Off/On), and Help, which shows Help."""
        ctl = {'Laptop': btn('Laptop', id=1001, does='Routes the laptop.'),
               'Display': stateful('Display', ['Off', 'On'], x=200, id=1002, does='Powers the display.'),
               'Help': btn('Help', x=400, id=1003, nav='Help')}
        ctl.update(swap)
        home = [c for c in ctl.values() if c is not None]
        close = btn('Close', id=2001, nav='Home')
        return [page('Home', *home), page('Help', close, number=2000)]

    def diff(self, old_pages, new_pages, old_popups=(), new_popups=()):
        from gdl.idmap import diff
        return diff(mapped(old_pages, old_popups), mapped(new_pages, new_popups))

    def test_the_same_map_needs_no_change(self):
        ch = self.diff(self.old(), self.old())
        self.assertFalse(ch['needs_change'])
        self.assertEqual(ch['verdict'], 'A program written against the previous map needs no change.')

    def test_a_caption_needs_no_change(self):
        ch = self.diff(self.old(), self.old(Laptop=btn('Laptop', id=1001, text='Notebook',
                                                       does='Routes the laptop.')))
        self.assertFalse(ch['needs_change'])
        self.assertEqual([c['id'] for c in ch['controls']['captions']], [1001])

    def test_an_added_control_is_named(self):
        ch = self.diff(self.old(), self.old(Camera=btn('Camera', x=600, id=1004, does='Shows the camera.')))
        self.assertTrue(ch['needs_change'])
        self.assertEqual([c['id'] for c in ch['controls']['added']], [1004])
        self.assertIn('1004', ch['verdict'])

    def test_a_removed_control_is_named(self):
        ch = self.diff(self.old(), self.old(Display=None))
        self.assertEqual([(c['id'], c['name']) for c in ch['controls']['removed']], [(1002, 'Display')])
        self.assertTrue(ch['needs_change'])

    def test_a_control_given_another_id_is_renumbered(self):
        ch = self.diff(self.old(), self.old(Laptop=btn('Laptop', id=1005, does='Routes the laptop.')))
        self.assertEqual([(c['name'], c['from'], c['to']) for c in ch['controls']['renumbered']],
                         [('Laptop', 1001, 1005)])
        self.assertEqual(ch['controls']['added'] + ch['controls']['removed'], [])

    def test_a_control_moved_to_another_page_is_said_so(self):
        new = self.old(Laptop=None)
        new[1]['controls'].append(btn('Laptop', x=200, id=2002, does='Routes the laptop.'))
        ch = self.diff(self.old(), new)
        moved = ch['controls']['moved']
        self.assertEqual([(m['name'], m['from']['id'], m['to']['id'], m['from']['at'], m['to']['at'])
                          for m in moved], [('Laptop', 1001, 2002, 'Home', 'Help')])
        self.assertTrue(ch['needs_change'])

    def test_the_verdict_counts_what_it_cannot_list_on_one_line(self):
        """A page renamed moves every control on it; the verdict stays one
        line, and changes.md has each."""
        new = self.old(Laptop=None, Display=None, Help=None)
        new[1]['controls'] += [btn('Laptop', x=200, id=2002, does='Routes the laptop.'),
                               stateful('Display', ['Off', 'On'], x=400, id=2003, does='Powers the display.'),
                               btn('Help', x=600, id=2004, nav='Help')]
        ch = self.diff(self.old(), new)
        self.assertEqual(len(ch['controls']['moved']), 3)
        self.assertIn('3 control(s) moved to another page, under new IDs (2002, 2003, 2004)', ch['verdict'])
        self.assertEqual(len(ch['verdict'].splitlines()), 1)

    def test_a_kept_id_on_another_page_needs_a_change(self):
        """Addressed by the same ID, but up only while another page is: a
        program shows the control by showing its page."""
        new = self.old(Laptop=None)
        new[1]['controls'].append(btn('Laptop', x=200, id=1001, does='Routes the laptop.'))
        ch = self.diff(self.old(), new)
        self.assertTrue(ch['needs_change'], ch['verdict'])
        self.assertEqual([(c['id'], c['from'], c['to']) for c in ch['controls']['relocated']],
                         [(1001, 'Home', 'Help')])
        self.assertIn('Laptop (1001) on Help, not Home', ch['verdict'])

    def test_a_kept_id_moved_onto_a_popup_needs_a_change(self):
        """On a popup it is up only while the program shows that popup."""
        def pops(*more):
            return [popup('Sources', btn('PC', id=9001, does='Routes the PC.'), *more, modal=True,
                          reached_by='program')]
        ch = self.diff(self.old(), self.old(Laptop=None), old_popups=pops(),
                       new_popups=pops(btn('Laptop', x=200, id=1001, does='Routes the laptop.')))
        self.assertTrue(ch['needs_change'], ch['verdict'])
        self.assertEqual([(c['id'], c['from'], c['to']) for c in ch['controls']['relocated']],
                         [(1001, 'Home', 'Sources')])
        from gdl.idmap import changes_markdown
        md = changes_markdown(ch, 'T')
        self.assertRegex(md.split('## Controls a program must change for')[1].split('## Also')[0],
                         r'\| relocated \| 1001 \| Laptop \| - \| Home \| Sources \|')

    def test_a_popup_in_another_group_or_made_modal_needs_a_change(self):
        """ShowPopup puts a standard popup in its group's region on the page,
        in place of the group's other popups; a modal one goes over
        everything. A program written for one is wrong for the other."""
        def pops(**how):
            return [popup('Sources', btn('PC', id=9001, does='Routes the PC.'), reached_by='program', **how)]
        for how, said in (({'group': 'Other'}, 'group Other'), ({'modal': True}, 'modal')):
            with self.subTest(said):
                ch = self.diff(self.old(), self.old(), old_popups=pops(group='Sources'), new_popups=pops(**how))
                self.assertTrue(ch['needs_change'])
                self.assertEqual([(r['name'], r['from'], r['to']) for r in ch['pages']['shown']],
                                 [('Sources', 'group Sources', said)])
                self.assertIn(f"popup 'Sources' {said}, not group Sources", ch['verdict'])

    def test_a_page_only_the_program_shows_now_needs_a_change(self):
        """Marked reached_by program, a page is one no button leads to: the
        program shows it or nobody does. The other way round the program may
        still show it, and needs no change."""
        shown = self.old()
        shown[1]['reached_by'] = 'program'
        ch = self.diff(self.old(), shown)
        self.assertTrue(ch['needs_change'], ch['verdict'])
        self.assertEqual([(r['name'], r['kind'], r['to']) for r in ch['pages']['reached']],
                         [('Help', 'page', 'program')])
        self.assertIn("page 'Help' shown by the program", ch['verdict'])
        ch = self.diff(shown, self.old())
        self.assertFalse(ch['needs_change'], ch['verdict'])
        self.assertEqual([(r['name'], r['from'], r['to']) for r in ch['pages']['reached']],
                         [('Help', 'program', None)])
        # A build does not say which pages the program shows: a map read off
        # one names none, which is not a page no longer shown by it.
        from gdl.idmap import diff
        built = dict(mapped(self.old()), built='panel.gdl')
        self.assertEqual(diff(built, mapped(shown))['pages']['reached'], [])

    def test_a_control_renamed_under_a_new_id_is_said_so(self):
        """Known by its page and name, a renamed control is new to the
        program: one gone and one come on the same page, the same type doing
        the same thing, is said to be that control renamed."""
        new = self.old(Laptop=None, Notebook=btn('Notebook', x=600, id=1004, does='Routes the laptop.'))
        ch = self.diff(self.old(), new)
        self.assertEqual([(r['from']['name'], r['from']['id'], r['to']['name'], r['to']['id'])
                          for r in ch['controls']['renamed']], [('Laptop', 1001, 'Notebook', 1004)])
        self.assertEqual(ch['controls']['added'] + ch['controls']['removed'], [])
        self.assertTrue(ch['needs_change'])

    def test_a_control_renamed_under_its_id_needs_no_change(self):
        new = self.old(Laptop=btn('Notebook', id=1001, does='Routes the laptop.'))
        ch = self.diff(self.old(), new)
        self.assertEqual([(r['id'], r['from'], r['to']) for r in ch['controls']['names']],
                         [(1001, 'Laptop', 'Notebook')])
        self.assertFalse(ch['needs_change'], ch['verdict'])

    def test_an_id_now_on_another_control_on_its_page_is_reassigned(self):
        """Translated without the previous map, a revision that moved Camera
        Privacy off the Call page gave its ID to the Share button drawn where it
        was: same page, another name doing another thing - another control,
        which a program addressing that ID now reaches."""
        new = self.old(Laptop=btn('Share', id=1001, does='Shares the screen.'),
                       Moved=btn('Laptop', x=600, id=1004, does='Routes the laptop.'))
        ch = self.diff(self.old(), new)
        self.assertEqual([(r['id'], r['from']['name'], r['to']['name']) for r in ch['controls']['reassigned']],
                         [(1001, 'Laptop', 'Share')])
        self.assertEqual(ch['controls']['names'], [])
        self.assertTrue(ch['needs_change'])

    def test_a_state_list_change_is_named(self):
        """A program sets a button's feedback by index: Warming in front of On
        moves On from 1 to 2."""
        ch = self.diff(self.old(), self.old(Display=stateful('Display', ['Off', 'Warming', 'On'], x=200,
                                                             id=1002, does='Powers the display.')))
        self.assertEqual([(c['id'], c['states']) for c in ch['controls']['changed']],
                         [(1002, [['Off', 'On'], ['Off', 'Warming', 'On']])])
        self.assertTrue(ch['needs_change'])

    def test_a_type_change_is_named(self):
        label = {'kind': 'label', 'name': 'Display', 'text': 'Display', 'rect': [200, 700, 100, 80],
                 'id': 1002, 'does': 'Powers the display.'}
        ch = self.diff(self.old(), self.old(Display=label))
        self.assertEqual([(c['id'], c['type']) for c in ch['controls']['changed']],
                         [(1002, ['Button', 'Label'])])

    def test_a_function_change_is_named(self):
        ch = self.diff(self.old(), self.old(Laptop=btn('Laptop', id=1001, does='Routes the laptop to both.')))
        self.assertEqual([(c['id'], c['function']) for c in ch['controls']['changed']],
                         [(1001, ['Routes the laptop.', 'Routes the laptop to both.'])])
        self.assertTrue(ch['needs_change'])

    def test_a_renamed_page_is_reported_not_mapped(self):
        new = self.old()
        new[1]['name'] = 'Support'
        new[0]['controls'][2]['nav'] = 'Support'
        new[1]['controls'][0]['id'] = 2002
        ch = self.diff(self.old(), new)
        self.assertEqual([(r['from'], r['to'], r['kind']) for r in ch['pages']['renamed']],
                         [('Help', 'Support', 'page')])
        self.assertEqual(ch['pages']['added'] + ch['pages']['removed'], [])
        self.assertTrue(ch['needs_change'])
        self.assertIn("'Help'", ch['verdict'])

    def test_pages_and_popups_added_and_removed(self):
        conf = popup('Confirm', btn('Yes', id=9001, does='Powers off.'), modal=True)
        ch = self.diff(self.old(), self.old(), new_popups=[conf])
        self.assertEqual([(p['name'], p['kind']) for p in ch['pages']['added']], [('Confirm', 'popup')])
        ch = self.diff(self.old(), self.old(), old_popups=[conf])
        self.assertEqual([(p['name'], p['kind']) for p in ch['pages']['removed']], [('Confirm', 'popup')])

    def test_a_page_that_became_a_popup_is_named(self):
        """Shown by name either way, but ShowPage is not ShowPopup."""
        old = self.old()
        new = [old[0]]
        ch = self.diff(old, new, new_popups=[popup('Help', btn('Close', id=2001, nav='Home'), modal=True)])
        self.assertEqual([(p['name'], p['from'], p['to']) for p in ch['pages']['kind']],
                         [('Help', 'page', 'popup')])
        self.assertTrue(ch['needs_change'])

    def test_the_markdown_says_the_verdict_and_each_change(self):
        from gdl.idmap import changes_markdown
        ch = self.diff(self.old(), self.old(Display=None, Camera=btn('Camera', x=600, id=1004, does='Shows.')))
        md = changes_markdown(ch, 'T')
        self.assertIn(ch['verdict'], md)
        self.assertRegex(md, r'\| added \| 1004 \| Camera \|')
        self.assertRegex(md, r'\| removed \| 1002 \| Display \|')

    def test_maps_of_every_panel_are_compared_panel_by_panel(self):
        """A control a small panel's layout adds is on that panel only, and a
        page renamed on one panel is that panel's."""
        from gdl.idmap import IdMap as M, combine, diff

        def maps(back):
            big = panel_spec('TLP1035T', [1280, 800], [page('Home', btn('Laptop', id=1001, does='Routes it.'))])
            ctl = [btn('Laptop', id=1001, does='Routes it.')]
            if back:
                ctl.append(btn('Home Back', x=200, id=50001, derived=True, does='Goes back.'))
            small = panel_spec('TLP320M', [320, 240], [page('Home', *ctl)])
            return combine({'TLP1035T': M(Panel(big)), 'TLP320M': M(Panel(small))})
        ch = diff(maps(False), maps(True))
        self.assertEqual([(c['id'], c['panels']) for c in ch['controls']['added']], [(50001, ['TLP320M'])])
        self.assertEqual(diff(maps(True), maps(True))['needs_change'], False)

    def test_a_panel_added_is_named(self):
        from gdl.idmap import IdMap as M, combine, diff

        def maps(*models):
            return combine({m: M(Panel(panel_spec(m, [1280, 800], [page('Home', btn('Go', id=1001, does='Go.'))])))
                            for m in models})
        ch = diff(maps('TLP1035T'), maps('TLP1035T', 'TLP725T'))
        self.assertEqual(ch['panels']['added'], ['TLP725T'])
        self.assertTrue(ch['needs_change'])

    def per_panel(self, *models, pc='Routes it.'):
        """A Group's Next shows a popup on the 525 and a page on the 320: its
        function is said per panel."""
        from gdl.idmap import IdMap as M, combine
        nxt = btn('Sources Next', rect=[400, 400, 100, 80], id=50001, derived=True, nav='Home Sources 2')
        specs = {'TLP525T': panel_spec('TLP525T', [800, 480], [page('Home', ref('Home Sources'), nxt)],
                                       [popup('Home Sources', btn('Laptop', id=1001, does='Routes it.'),
                                              group='Home Sources'),
                                        popup('Home Sources 2', btn('PC', id=1002, does='Routes it.'),
                                              group='Home Sources')]),
                 'TLP320M': panel_spec('TLP320M', [320, 240],
                                       [page('Home', btn('Laptop', id=1001, does='Routes it.'),
                                             dict(nxt, rect=[200, 150, 80, 60])),
                                        page('Home Sources 2', btn('PC', id=1002, does=pc))])}
        return combine({m: M(Panel(specs[m])) for m in models})

    def test_a_panel_dropped_or_added_is_said_once(self):
        """A function said per panel was compared as one string naming every
        panel, so dropping the 320 changed the function of every control whose
        function differs there."""
        from gdl.idmap import diff
        both, one = self.per_panel('TLP525T', 'TLP320M'), self.per_panel('TLP525T')
        ch = diff(both, one)
        self.assertEqual((ch['panels']['removed'], ch['controls']['changed']), (['TLP320M'], []))
        self.assertEqual(ch['verdict'], 'A program written against the previous map needs changing: '
                                        'a panel gone (TLP320M).')
        ch = diff(one, both)
        self.assertEqual((ch['panels']['added'], ch['controls']['changed']), (['TLP320M'], []))

    def test_a_function_changed_on_one_panel_names_it(self):
        from gdl.idmap import diff
        ch = diff(self.per_panel('TLP525T', 'TLP320M'), self.per_panel('TLP525T', 'TLP320M', pc='Routes the PC.'))
        self.assertEqual([(c['id'], c['function']) for c in ch['controls']['changed']],
                         [(1002, ['TLP320M: Routes it.', 'TLP320M: Routes the PC.'])])

    def test_one_panels_map_is_compared_on_its_own_panel(self):
        """New-GdlPanel.ps1 -IdMap -Previous maps one panel of a canvas of
        several. It was compared with the previous map's first panel, so the
        others were gone and what that panel's layout derived was new."""
        from gdl.idmap import IdMap as M, changes_markdown, combine, diff

        def spec(m, size):
            ctl = [btn('Laptop', id=1001, does='Routes it.')]
            if m == 'TLP725T':
                ctl.append(btn('Home Back', x=200, id=50001, derived=True, does='Goes back.'))
            return panel_spec(m, size, [page('Home', *ctl)])
        sizes = {'TLP1035T': [1280, 800], 'TLP725T': [1024, 600], 'TLP320M': [320, 240]}
        old = combine({m: M(Panel(spec(m, s))) for m, s in sizes.items()})
        one = M(Panel(spec('TLP725T', sizes['TLP725T']))).data()
        self.assertEqual(one['model'], 'TLP725T')
        self.assertNotIn('model', old)
        ch = diff(old, one)
        self.assertEqual(ch['panels'], {'added': [], 'removed': [], 'only': 'TLP725T'})
        self.assertEqual(ch['controls']['added'] + ch['controls']['removed'], [])
        self.assertFalse(ch['needs_change'], ch['verdict'])
        self.assertIn('the TLP725T only', changes_markdown(ch, 'T'))
        # A map of one panel that names none - one written before maps named
        # their panel - is taken as the panel the canvas is drawn on.
        del one['model']
        self.assertEqual(diff(old, one)['panels']['only'], 'TLP1035T')

    def test_a_move_on_one_panel_names_that_panel(self):
        """The rows read the same on both sides where the control moved on a
        panel other than the first."""
        from gdl.idmap import IdMap as M, combine, diff

        def maps(pop):
            laptop = btn('Laptop', id=1001, does='Routes it.')
            big = panel_spec('TLP1035T', [1280, 800], [page('Home', laptop)])
            small = panel_spec('TLP725T', [1024, 600], [page('Home', ref(pop))],
                               [popup(pop, laptop, group=pop, reached_by='program')])
            return combine({'TLP1035T': M(Panel(big)), 'TLP725T': M(Panel(small))})
        ch = diff(maps('Home Sources'), maps('Sources'))
        self.assertEqual([(r['id'], r['from'], r['to'], r['panels']) for r in ch['controls']['relocated']],
                         [(1001, 'Home Sources', 'Sources', ['TLP725T'])])

    def test_the_command_exits_by_its_verdict(self):
        from gdl.idmap import main
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        for name, pages in (('a', self.old()), ('b', self.old()),
                            ('c', self.old(Display=None))):
            idmap(pages).write(os.path.join(d, name))
        self.assertEqual(main(['x', 'diff', os.path.join(d, 'a'), os.path.join(d, 'b')]), 0)
        self.assertEqual(main(['x', 'diff', os.path.join(d, 'a'), os.path.join(d, 'c', 'idmap.json')]), 1)
        self.assertEqual(main(['x', 'diff', os.path.join(d, 'a'), os.path.join(d, 'nowhere')]), 2)


class TestChangesBesideTheMap(unittest.TestCase):
    """With the previous delivery's map, writing the map writes changes.md
    and changes.json beside it."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.prev = os.path.join(self.dir, 'prev')
        idmap([page('Home', btn('Laptop', id=1001, does='Routes it.'))]).write(self.prev)

    def spec_file(self, previous=None, **extra):
        spec = {'name': 'T', 'size': [1280, 800], 'theme': THEME,
                'pages': [page('Home', btn('Laptop', id=1001, does='Routes it.'), *extra.values())]}
        if previous:
            spec['_previous'] = previous
        f = os.path.join(self.dir, 'spec.json')
        with open(f, 'w', encoding='utf-8') as fh:
            json.dump(spec, fh)
        return f

    def sha(self):
        from gdl.idmap import load_previous
        return load_previous(self.prev)['_sha256']

    def run_main(self, *argv):
        import contextlib
        from gdl.idmap import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = main(['x', *argv])
        return got, buf.getvalue()

    def test_a_map_that_travelled_through_windows_is_the_same_map(self):
        """Re-saved with CRLF line ends or a BOM, a delivered idmap.json is the
        map the specs kept IDs against. Hashed byte for byte it was refused,
        with a message telling the user to pass the map they had passed."""
        with open(os.path.join(self.prev, 'idmap.json'), 'rb') as fh:
            raw = fh.read()
        for name, data in (('crlf', raw.replace(b'\n', b'\r\n')), ('bom', b'\xef\xbb\xbf' + raw),
                           ('both', b'\xef\xbb\xbf' + raw.replace(b'\n', b'\r\n'))):
            with self.subTest(name):
                f = os.path.join(self.dir, name + '.json')
                with open(f, 'wb') as fh:
                    fh.write(data)
                out = os.path.join(self.dir, 'out-' + name)
                got, said = self.run_main('write', self.spec_file(self.sha()), out, '--previous', f)
                self.assertEqual(got, 0, said)
                self.assertTrue(os.path.exists(os.path.join(out, 'changes.md')))

    def test_check_refuses_another_map_as_write_does(self):
        got, said = self.run_main('check', self.spec_file('0' * 64), '--previous', self.prev)
        self.assertEqual(got, 1)
        self.assertIn('sha256 000000000000', said)
        got, said = self.run_main('check', self.spec_file(self.sha()), '--previous', self.prev)
        self.assertEqual(got, 0, said)

    def test_one_panels_map_written_against_every_panels_map(self):
        """`write <one panel's spec> --previous <the map of every panel>`, as
        New-GdlPanel.ps1 -IdMap -Previous runs it: compared on that panel."""
        from gdl.idmap import IdMap as M, write_panels
        sizes = {'TLP1035T': [1280, 800], 'TLP725T': [1024, 600]}
        every = os.path.join(self.dir, 'every')
        laptop = btn('Laptop', rect=[0, 400, 100, 80], id=1001, does='Routes it.')
        write_panels({m: M(Panel(panel_spec(m, s, [page('Home', laptop)]))) for m, s in sizes.items()}, every)
        f = os.path.join(self.dir, 'one.json')
        with open(f, 'w', encoding='utf-8') as fh:
            json.dump(panel_spec('TLP725T', sizes['TLP725T'], [page('Home', laptop)]), fh)
        out = os.path.join(self.dir, 'one')
        got, said = self.run_main('write', f, out, '--previous', every)
        self.assertEqual(got, 0, said)
        with open(os.path.join(out, 'changes.json'), encoding='utf-8') as fh:
            ch = json.load(fh)
        self.assertEqual(ch['panels'], {'added': [], 'removed': [], 'only': 'TLP725T'})
        self.assertFalse(ch['needs_change'], ch['verdict'])

    def test_write_with_the_previous_map_writes_the_changes(self):
        from gdl.idmap import main
        out = os.path.join(self.dir, 'out')
        f = self.spec_file(self.sha(), cam=btn('Camera', x=200, id=1002, does='Shows it.'))
        self.assertEqual(main(['x', 'write', f, out, '--previous', self.prev]), 0)
        with open(os.path.join(out, 'changes.json'), encoding='utf-8') as fh:
            ch = json.load(fh)
        self.assertEqual([c['id'] for c in ch['controls']['added']], [1002])
        with open(os.path.join(out, 'changes.md'), encoding='utf-8') as fh:
            self.assertIn(ch['verdict'], fh.read())

    def test_specs_kept_against_another_map_are_refused(self):
        from gdl.idmap import main
        out = os.path.join(self.dir, 'out')
        self.assertEqual(main(['x', 'write', self.spec_file('0' * 64), out, '--previous', self.prev]), 1)
        self.assertFalse(os.path.exists(os.path.join(out, 'idmap.json')))

    def test_specs_kept_against_a_map_say_so_without_it(self):
        import contextlib
        from gdl.idmap import main
        out = os.path.join(self.dir, 'out')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(['x', 'write', self.spec_file(self.sha()), out]), 0)
        self.assertIn('--previous', buf.getvalue())
        self.assertFalse(os.path.exists(os.path.join(out, 'changes.md')))

    def test_every_panels_map_writes_them_too(self):
        from gdl.idmap import IdMap as M, write_panels
        maps = {m: M(Panel(panel_spec(m, size, [page('Home', btn('Laptop', id=1001, does='Routes it.'))])))
                for m, size in (('TLP1035T', [1280, 800]), ('TLP725T', [1024, 600]))}
        out = os.path.join(self.dir, 'panels')
        from gdl.idmap import load_previous
        written = write_panels(maps, out, previous=load_previous(self.prev))
        self.assertIn(os.path.join(out, 'changes.md'), written)
        with open(os.path.join(out, 'changes.json'), encoding='utf-8') as fh:
            # A map of one panel was drawn for the first of them.
            self.assertEqual(json.load(fh)['panels']['added'], ['TLP725T'])


class TestTheRealSizeExample(unittest.TestCase):
    """examples/boardroom-full.json is a panel the size of a real one - the
    client project has 27 pages; nothing generated before had more than three.
    It stays clean so its build stays repeatable (docs/from-scratch.md §5c, *A
    real-size panel*)."""
    PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'examples', 'boardroom-full.json')

    def test_it_checks_clean_with_its_one_dead_end(self):
        problems, notes = load(self.PATH).check()
        self.assertEqual(problems, [])
        # Shutting Down has no way out on the panel: the program returns to
        # Welcome when the room is off.
        self.assertEqual(len(notes), 1)
        self.assertIn("'Shutting Down' is a dead end", notes[0])

    def test_it_is_the_size_it_says(self):
        p = Panel.load(self.PATH)
        self.assertGreaterEqual(len(p.pages), 20)
        volume = [pg['name'] for pg in p.pages
                  if any(c.get('kind') == 'popup_ref' and c.get('group') == 'Volume'
                         for c in pg['controls'])]
        self.assertGreaterEqual(len(volume), 7, volume)
        keypads = {tuple(c['rect']) for pg in p.pages for c in pg['controls']
                   if c.get('kind') == 'popup_ref' and c.get('group') == 'Keypad'}
        self.assertEqual(len(keypads), 2, 'one Keypad reference per page, each in its own place')

    def test_its_chrome_is_one_control_to_the_program(self):
        p = Panel.load(self.PATH)
        on = [pg['name'] for pg in p.pages if any(c['id'] == 41 for c in pg['controls'])]
        self.assertGreaterEqual(len(on), 20)
        rows = [c for c in load(self.PATH).data()['controls'] if c['id'] == 41]
        self.assertEqual(len(rows), 1, 'a mirror is listed once')


class TestABuiltPanelsUnnumberedControls(unittest.TestCase):
    def test_a_control_with_no_id_is_left_out_and_counted(self):
        """GUI Designer leaves 0 on a control nobody numbered - 98 controls in
        the client fixture, 59 of them buttons - and nothing can address one."""
        from gdl.idmap import BuiltMap
        layout = {'DefaultPage': 1, 'PopupPages': [], 'Pages': [{'ID': 1, 'Name': 'Home', 'Controls': [
            {'Type': 11, 'UserId': 0, 'Name': 'Static', 'Text': 'Welcome'},
            {'Type': 7, 'UserId': 5, 'Name': 'Go', 'States': [{'Name': 'Off', 'Text': 'Go'}]}]}]}
        m = BuiltMap(layout)
        d = m.data()
        self.assertEqual([c['id'] for c in d['controls']], [5])
        self.assertEqual(d['unnumbered'], 1)
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        m.write(out)
        with open(os.path.join(out, 'idmap.md'), encoding='utf-8') as fh:
            self.assertIn('1 control carries no ID', fh.read())


class TestABuiltPanelsGlyphCaptions(unittest.TestCase):
    """A glyph caption is a private-use character - or, in Extron-Shockwave,
    a Latin-1 one standing for an icon - which a spreadsheet shows blank or as
    the wrong thing. The map names the glyph, as a spec's map names its icon."""

    @staticmethod
    def _map(text, font):
        from gdl.idmap import BuiltMap
        layout = {'DefaultPage': 1, 'PopupPages': [], 'Pages': [{'ID': 1, 'Name': 'Home', 'Controls': [
            {'Type': 7, 'UserId': 5, 'Name': 'B', 'Font': {'Name': font},
             'States': [{'Name': 'Off', 'Text': text}]}]}]}
        return BuiltMap(layout).data()['controls'][0]['at'][0]['caption']

    def test_a_glyph_is_named_by_its_codepoint_where_its_face_names_none(self):
        self.assertEqual(self._map(chr(0xE926), 'Some Icon Face'), 'icon: U+E926')
        self.assertEqual(self._map(chr(0xB1), 'Extron-Shockwave'), 'icon: U+00B1')

    def test_words_are_words(self):
        self.assertEqual(self._map('Laptop', 'Open Sans'), 'Laptop')
        self.assertEqual(self._map(chr(0xB1) + '5', 'Open Sans'), chr(0xB1) + '5')

    def test_the_seeds_own_glyph_captions_are_named(self):
        from gdl.container import open_payload
        from gdl.fonts import icon_face
        from gdl.idmap import BuiltMap
        seed = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'seeds', 'Afterburn 1035.gdl')
        with open(seed, 'rb') as fh:
            if fh.read(40).startswith(b'version https://git-lfs'):
                self.skipTest('seeds/Afterburn 1035.gdl is not pulled from Git LFS here')
        if not icon_face('Extron-Afterburn')[0]:
            self.skipTest('no Extron-Afterburn face here to read its glyph names from')
        d = BuiltMap(json.loads(open_payload(seed).read('layout.json'))).data()
        captions = [a['caption'] for c in d['controls'] for a in c['at']]
        self.assertFalse([x for x in captions if any(0xE000 <= ord(ch) <= 0xF8FF for ch in x)])
        self.assertIn('icon: close', captions)
        self.assertIn('icon: fast_forward', captions)


class TestAPanelThatWasNeverASpec(unittest.TestCase):
    """A client project that was never a spec has no map, though its built
    layout.json holds every ID, type, page and caption one needs. Read off the
    23-page panel's own build, the map must agree with the one its spec wrote -
    everything but what controls do, which no .gdl carries."""

    BUILD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'archive', 'job-2419a20b', 'item4', 'build6')

    def setUp(self):
        gdl = os.path.join(self.BUILD, 'BoardroomFull.gdl')
        if not os.path.isfile(gdl):
            self.skipTest('the archived real-size build is not here')
        with open(gdl, 'rb') as fh:
            if fh.read(40).startswith(b'version https://git-lfs'):
                self.skipTest('the archived real-size build is not pulled from Git LFS here')
        from gdl.idmap import BuiltMap
        self.built = BuiltMap.open(gdl).data()
        with open(os.path.join(self.BUILD, 'idmap', 'idmap.json'), encoding='utf-8') as fh:
            self.spec = json.load(fh)

    def test_it_boots_where_the_spec_said(self):
        self.assertEqual(self.built['start_page'], self.spec['start_page'])

    def test_every_page_and_popup_as_the_spec_named_them(self):
        self.assertEqual(sorted(p['name'] for p in self.built['pages']),
                         sorted(p['name'] for p in self.spec['pages']))
        self.assertEqual(sorted((p['name'], p['modal'], p['group']) for p in self.built['popups']),
                         sorted((p['name'], p['modal'], p['group']) for p in self.spec['popups']))

    def test_every_id_its_type_places_and_captions(self):
        def rows(d):
            return {c['id']: (c['type'], sorted((a['container'], a['name'], a['caption']) for a in c['at']))
                    for c in d['controls']}
        self.assertEqual(rows(self.built), rows(self.spec))

    def test_a_buttons_states_as_the_program_sets_them(self):
        want = {c['id']: (c.get('states'), c.get('press')) for c in self.spec['controls']
                if c['type'] == 'Button' and c.get('states')}
        got = {c['id']: (c.get('states'), c.get('press')) for c in self.built['controls']
               if c['id'] in want}
        self.assertEqual(got, want)

    def test_what_a_control_does_is_left_to_the_programmer(self):
        self.assertTrue(all(c['function'] == '' and c['nav'] is None for c in self.built['controls']))
        self.assertEqual(self.built['navigation'], [])

    def test_the_command_writes_all_three(self):
        import contextlib
        import io
        from gdl.idmap import main
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(['idmap', 'from-built', os.path.join(self.BUILD, 'BoardroomFull.gdl'), out])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(out)), ['idmap.csv', 'idmap.json', 'idmap.md'])
        with open(os.path.join(out, 'idmap.md'), encoding='utf-8') as fh:
            self.assertIn('BoardroomFull.gdl', fh.read())


def _pulled(path):
    """`path` is here and not a Git LFS pointer."""
    if not os.path.isfile(path):
        return False
    with open(path, 'rb') as fh:
        return not fh.read(40).startswith(b'version https://git-lfs')


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestASeedReadOffItsBuild(unittest.TestCase):
    """The Afterburn 1035 seed - the one seed CI pulls - read as a panel that
    was never a spec: what layout.json says, and what only the project does."""

    SEED = os.path.join(ROOT, 'seeds', 'Afterburn 1035.gdl')

    @classmethod
    def setUpClass(cls):
        if not _pulled(cls.SEED):
            raise unittest.SkipTest('seeds/Afterburn 1035.gdl is not pulled from Git LFS here')
        from gdl.idmap import BuiltMap
        cls.d = BuiltMap.open(cls.SEED).data()

    def _row(self, uid):
        return next(c for c in self.d['controls'] if c['id'] == uid)

    def test_a_flattened_caption_is_read_off_the_project(self):
        """Build bakes a FlattenText caption into the control's artwork and
        leaves its layout.json text empty - 71 of the seed's 365 IDs."""
        self.assertEqual(self._row(8231)['at'][0]['caption'], 'Preset 1')
        self.assertEqual(self._row(8020)['at'][0]['caption'], 'Audio')

    def test_its_popups_and_their_groups_without_the_offline_page(self):
        popups = {p['name']: p for p in self.d['popups']}
        self.assertNotIn('Offline Page', popups)
        self.assertEqual((popups['PC']['modal'], popups['PC']['group']), (False, 'Controls'))
        self.assertEqual((popups['Help']['modal'], popups['Help']['group']), (True, None))
        self.assertEqual(self.d['start_page'], 'Start')

    def test_the_command_writes_all_three(self):
        import contextlib
        import io
        from gdl.idmap import main
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(['idmap', 'from-built', self.SEED, out])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(out)), ['idmap.csv', 'idmap.json', 'idmap.md'])
        with open(os.path.join(out, 'idmap.csv'), encoding='utf-8') as fh:
            self.assertIn('Preset 1', fh.read())


class TestWhatABuildDoesNotSay(unittest.TestCase):
    @staticmethod
    def _md(layout):
        from gdl.idmap import BuiltMap
        out = tempfile.mkdtemp()
        try:
            BuiltMap(layout).write(out)
            with open(os.path.join(out, 'idmap.md'), encoding='utf-8') as fh:
                return fh.read()
        finally:
            shutil.rmtree(out, True)

    def test_an_ungrouped_popup_and_an_unknown_start_say_so(self):
        md = self._md({'DefaultPage': 99, 'Pages': [{'ID': 1, 'Name': 'Home', 'Controls': []}],
                       'PopupPages': [{'ID': 2, 'Name': 'Volume Level', 'Modal': False,
                                       'IsGroupValid': False, 'GroupID': 0, 'Controls': []}]})
        self.assertNotIn('None', md)
        self.assertIn('popup, no group', md)

    def test_a_built_map_lists_every_buttons_states(self):
        """'A button with none listed keeps the states of the button it was
        cloned from' is a spec's: off a build, every button lists its own."""
        md = self._md({'DefaultPage': 1, 'PopupPages': [], 'Pages': [{'ID': 1, 'Name': 'Home', 'Controls': [
            {'Type': 7, 'UserId': 5, 'Name': 'Go', 'States': [{'Name': 'Off', 'Text': 'Go'}]}]}]})
        self.assertNotIn('cloned from', md)

    def test_copies_of_one_id_that_differ_are_noted(self):
        """The map lists an ID once, from its first copy; a program setting a
        state by index needs to know where another copy numbers them otherwise."""
        from gdl.idmap import BuiltMap

        def mute(*states, press=None):
            return {'Type': 7, 'UserId': 171, 'Name': 'Mute', 'TLPPressFeedbackStateID': press,
                    'States': [{'Name': s} for s in states]}
        layout = {'DefaultPage': 1, 'PopupPages': [], 'Pages': [
            {'ID': 1, 'Name': 'Home', 'Controls': [mute('Muted', 'Level 3_1', press=0)]},
            {'ID': 2, 'Name': 'Room', 'Controls': [mute('Muted', 'Level 1', press=0)]},
            {'ID': 3, 'Name': 'Desk', 'Controls': [mute('Muted', 'Level 3_1', press=0)]}]}
        notes = [x for x in BuiltMap(layout).data()['panel'] if '171' in x]
        self.assertEqual(len(notes), 1, notes)
        self.assertIn('Room / Mute', notes[0])
        self.assertIn('Level 1', notes[0])
        self.assertNotIn('Desk', notes[0])
        self.assertIn('ID 171', self._md(layout))

    def test_a_file_that_is_not_a_build_is_refused_not_raised(self):
        import contextlib
        import io
        from gdl.idmap import main
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        pointer = os.path.join(d, 'Panel.gdl')
        with open(pointer, 'wb') as fh:
            fh.write(b'version https://git-lfs.github.com/spec/v1\noid sha256:0\nsize 1\n')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(['idmap', 'from-built', pointer, os.path.join(d, 'out')])
        self.assertEqual(code, 1)
        self.assertIn('git lfs pull', out.getvalue())
        self.assertFalse(os.path.exists(os.path.join(d, 'out')))


class TestAPanelBuiltFromBareButtons(unittest.TestCase):
    """examples/huddle.json leaves 7 of its 13 buttons' states to the clone:
    off its build, the map agrees with the spec's on the type, places and
    caption of every ID the spec numbers, and names the states the spec's map
    could not. The build is from before the applier dropped the donor's own
    pages, so it holds theirs too."""

    BUILT = os.path.join(ROOT, 'archive', 'gdlwork', 'out', 'Huddle.gdl')

    def setUp(self):
        if not _pulled(self.BUILT):
            self.skipTest('archive/gdlwork/out/Huddle.gdl is not pulled from Git LFS here')

    def test_it_agrees_and_names_the_clones_states(self):
        from gdl.idmap import BuiltMap
        built = BuiltMap.open(self.BUILT).data()
        spec = load(os.path.join(ROOT, 'examples', 'huddle.json')).data()

        def rows(d):
            return {c['id']: (c['type'], sorted((a['container'], a['name'], a['caption']) for a in c['at']))
                    for c in d['controls']}
        want = rows(spec)
        self.assertEqual({k: v for k, v in rows(built).items() if k in want}, want)
        bare = [c['id'] for c in spec['controls'] if c['type'] == 'Button' and not c.get('states')]
        self.assertTrue(bare)
        got = {c['id']: c.get('states') for c in built['controls'] if c['id'] in bare}
        self.assertTrue(all(got.values()), got)


if __name__ == '__main__':
    unittest.main(verbosity=2)
