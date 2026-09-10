"""Button feedback states: Off/On, and the trap that hid their absence.

A button that looks the same in both states is inert - the control system sets
it On and nothing on the panel changes. Every generated button was exactly that
until 2026-09-10, for two independent reasons:

  1. `gdl/spec.py` had no vocabulary for a second appearance, so the plan
     carried one fill and the applier wrote it to every state.
  2. `PBStates.Count` is a LOGICAL count, not the number of PBState objects.
     It reports 1 for a two-state Off/On button, so every `for ($i = 0; $i -lt
     $states.Count; $i++)` loop in both appliers visited state 0 and stopped.

The second is the interesting one, because it is invisible: `TLPDefaultStateID`
is 0, so a button whose state 1 was never written renders perfectly and only
misbehaves once a control system switches it. It also means `rename` was
leaving the old caption on state 1 of every button it touched.

Off/On is measured, not assumed. Across Extron's six theme templates plus the
Liberty Bank project, PBState `nameField` gives ('Off', 'On') for 3475 of 3668
buttons (94.7%); 60% of those give the two states different fills and 68%
different artwork.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.project import Project
from gdl.spec import Panel

FIXTURE = os.path.join('fixtures', 'gdl',
                       'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')

THEME = {'raised': '#37394E', 'accent': '#3D8BFD', 'surface': '#242634',
         'text': '#FFFFFF', 'muted': '#BABCCE', 'font': 'Open Sans', 'size': 16}


def spec_with(controls, theme=None, **kw):
    return Panel({
        'name': 'States Test', 'model': 'TLP1035M', 'size': [1280, 800],
        'theme': dict(THEME, **(theme or {})),
        'pages': [{'name': 'P1', 'number': 1000, 'controls': controls}],
        **kw,
    })


def ops(sp):
    return {op['fields']['nameField']: op
            for op in sp.plan()['pages'][0]['controls']}


BTN = {'kind': 'button', 'name': 'B', 'text': 'B', 'rect': [0, 0, 200, 80],
       'fill': 'raised'}


class TestVocabulary(unittest.TestCase):
    def test_a_button_with_no_feedback_carries_no_states(self):
        """The default must stay exactly what it was, or every existing spec
        changes meaning."""
        self.assertIsNone(ops(spec_with([dict(BTN)]))['B']['states'])

    def test_a_bare_color_sets_the_on_fill(self):
        st = ops(spec_with([dict(BTN, on='accent')]))['B']['states']
        self.assertEqual([s['name'] for s in st], ['Off', 'On'])
        self.assertNotEqual(st[0]['fill'], st[1]['fill'])

    def test_on_inherits_everything_it_does_not_name(self):
        """`"on": "accent"` must change the fill and nothing else, or a one-word
        request quietly restyles the whole button."""
        st = ops(spec_with([dict(BTN, on='accent', stroke='muted',
                                 color='text')]))['B']['states']
        self.assertEqual(st[0]['stroke'], st[1]['stroke'])
        self.assertEqual(st[0]['text_color'], st[1]['text_color'])
        self.assertEqual(st[0]['border'], st[1]['border'])

    def test_a_dict_can_override_each_part(self):
        st = ops(spec_with([dict(BTN, on={'fill': 'surface', 'color': 'muted',
                                          'stroke': 'accent'})]))['B']['states']
        self.assertNotEqual(st[0]['fill'], st[1]['fill'])
        self.assertNotEqual(st[0]['text_color'], st[1]['text_color'])
        self.assertNotEqual(st[0]['stroke'], st[1]['stroke'])

    def test_a_theme_default_reaches_every_button(self):
        """The point of the theme key: prose in, feedback out, without the
        author having to know the format has states at all."""
        sp = spec_with([dict(BTN), dict(BTN, name='C', text='C')],
                       theme={'on': 'accent'})
        for name in ('B', 'C'):
            self.assertIsNotNone(ops(sp)[name]['states'], name)

    def test_a_control_overrides_the_theme_default(self):
        sp = spec_with([dict(BTN, on={'fill': 'surface'})], theme={'on': 'accent'})
        st = ops(sp)['B']['states']
        self.assertEqual(st[1]['fill'], ops(spec_with([dict(BTN, fill='surface')]))['B']['fill'])

    def test_only_buttons_get_states(self):
        """A label has no states collection; asking for one would make the
        applier report a problem on every caption in the panel."""
        sp = spec_with([{'kind': 'label', 'name': 'L', 'text': 'L',
                         'rect': [0, 0, 100, 40]}], theme={'on': 'accent'})
        self.assertIsNone(ops(sp)['L']['states'])


class TestDonorGate(unittest.TestCase):
    """A donor whose buttons have one state cannot express Off/On, and the
    applier cannot create the missing one - a PBState would have to be
    CONSTRUCTED. Catching it here costs a second; missing it costs a build."""

    def test_the_fixture_can_supply_two_states(self):
        sp = spec_with([dict(BTN, on='accent')])
        problems = [p for p in sp.check_donor(FIXTURE) if 'states' in p]
        self.assertEqual(problems, [])

    def test_needs_states_is_one_when_nothing_asks(self):
        self.assertEqual(spec_with([dict(BTN)]).needs_states(), 1)

    def test_needs_states_is_two_when_a_button_asks(self):
        self.assertEqual(spec_with([dict(BTN, on='accent')]).needs_states(), 2)

    def test_needs_states_sees_the_theme_default(self):
        self.assertEqual(
            spec_with([dict(BTN)], theme={'on': 'accent'}).needs_states(), 2)


class TestReaderCountsStates(unittest.TestCase):
    """`n_states` is what the donor gate reads, so it has to be the real count
    and not PBStates' logical one."""

    def setUp(self):
        self.proj = Project.open(FIXTURE)

    def test_buttons_report_more_than_one_state(self):
        counts = [c['n_states'] for pg in self.proj.pages()
                  for c in pg['controls'] if c['type'] == 'PBButton']
        self.assertTrue(counts)
        self.assertGreater(max(counts), 1,
                           'if every button reported <=1 state the reader is '
                           'making the same mistake PBStates.Count makes')

    def test_off_on_is_the_dominant_idiom(self):
        pairs = [tuple(c['state_names']) for pg in self.proj.pages()
                 for c in pg['controls']
                 if c['type'] == 'PBButton' and c['n_states'] == 2]
        self.assertTrue(pairs)
        offon = sum(p == ('Off', 'On') for p in pairs)
        self.assertGreater(offon / len(pairs), 0.8,
                           f'Off/On was {offon}/{len(pairs)} - if that has '
                           f'changed, the names this spec emits should change too')


class TestVerifierCatchesInertButtons(unittest.TestCase):
    """The check that would have caught the original bug. It has to fail on a
    button whose states are identical, or shipping one is silent again."""

    def setUp(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            from PIL import Image           # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; the artwork checks need it')
        import verify_built
        self.vb = verify_built

    @staticmethod
    def png(rgb):
        """A solid 8x8 PNG, so _shares runs its real decode path."""
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGBA', (8, 8), rgb + (255,)).save(buf, 'PNG')
        return buf.getvalue()

    def _plan_and_layout(self, off_img, on_img):
        plan_items = [{'name': 'P1', 'controls': [{
            'fields': {'nameField': 'B'},
            'states': [{'name': 'Off', 'fill': 0xFF37394E},
                       {'name': 'On', 'fill': 0xFF3D8BFD}],
        }]}]
        table = {'P1': {'Name': 'P1', 'Controls': [{
            'Name': 'B', 'TLPImageID': off_img,
            'States': [{'Name': 'Off', 'TLPImageID': off_img},
                       {'Name': 'On', 'TLPImageID': on_img}],
        }]}}
        return plan_items, table

    def test_identical_artwork_is_a_problem(self):
        plan, table = self._plan_and_layout(90, 90)
        assets = {90: self.png((0x37, 0x39, 0x4E))}
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertTrue([p for p in problems if 'same pixels' in p],
                        f'expected an inert-button problem, got {problems}')

    def test_same_color_from_different_images_is_a_problem(self):
        plan, table = self._plan_and_layout(90, 91)
        assets = {90: self.png((0x37, 0x39, 0x4E)),
                  91: self.png((0x37, 0x39, 0x4E))}
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertTrue([p for p in problems if 'no visible feedback' in p
                         or 'mostly' in p],
                        f'expected a feedback problem, got {problems}')

    def test_genuinely_different_states_pass(self):
        plan, table = self._plan_and_layout(90, 91)
        assets = {90: self.png((0x37, 0x39, 0x4E)),
                  91: self.png((0x3D, 0x8B, 0xFD))}
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertEqual(problems, [])

    def test_a_missing_state_is_a_problem(self):
        plan, table = self._plan_and_layout(90, 91)
        table['P1']['Controls'][0]['States'] = [{'Name': 'Off', 'TLPImageID': 90}]
        problems, _, _ = self.vb.check_states(plan, table,
                                              {90: self.png((1, 2, 3))}, 'page')
        self.assertTrue([p for p in problems if 'shows no feedback' in p],
                        f'expected a missing-state problem, got {problems}')


class TestWorkedExample(unittest.TestCase):
    def test_clean_room_asks_for_feedback_and_plans_it(self):
        with open(os.path.join('examples', 'clean-room.json'),
                  encoding='utf-8') as fh:
            sp = Panel(json.load(fh))
        plan = sp.plan()
        withstates = [op for pg in plan['pages'] for op in pg['controls']
                      if op.get('states')]
        self.assertTrue(withstates, 'the worked example lost its feedback states')
        for op in withstates:
            st = op['states']
            self.assertEqual([s['name'] for s in st], ['Off', 'On'])
            self.assertNotEqual(st[0]['fill'], st[1]['fill'],
                                f"{op['fields']['nameField']} would build inert")


if __name__ == '__main__':
    unittest.main(verbosity=2)
