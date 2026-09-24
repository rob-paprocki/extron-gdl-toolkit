"""Button feedback states: Off/On, named states, and the trap that hid them.

A button that looks the same in both states is inert - the control system sets
it On and nothing on the panel changes. Every generated button was exactly that
until 2026-09-10, for two independent reasons:

  1. `gdl/spec.py` had no vocabulary for a second appearance, so the plan
     carried one fill and the applier wrote it to every state.
  2. `PBStates` has no `Count`, and PowerShell 5.1 answers 1 for `.Count` on
     any object without one - so every `for ($i = 0; $i -lt $states.Count;
     $i++)` loop in both appliers visited state 0 and stopped.

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
from gdl.spec import BORDERS, Panel

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


PRESS = '<TLPPressFeedbackStateID>k__BackingField'
DEFAULT = '<TLPDefaultStateID>k__BackingField'

MUTE = dict(BTN, name='Mute', text='Mute', states=[
    {'name': 'Muted', 'fill': '#B00020', 'text': 'Muted'},
    'Level 1',
    {'name': 'Level 2', 'fill': 'accent'},
    {'name': 'Level 3', 'fill': 'surface', 'text': 'Max'},
])


class TestNamedStates(unittest.TestCase):
    """More than Off/On. Extron's own templates carry 4-state volume mutes
    ('Muted', 'Level 1', 'Level 2', 'Level 3') and 3-state call buttons
    ('Unavailable', 'Ready', 'Connected'); a spec names them with `states`."""

    def test_states_are_planned_in_order_with_their_names(self):
        st = ops(spec_with([MUTE]))['Mute']['states']
        self.assertEqual([s['name'] for s in st], ['Muted', 'Level 1', 'Level 2', 'Level 3'])

    def test_a_state_inherits_what_it_does_not_name(self):
        """A bare name is the button's own look, the way `on` inherits."""
        op = ops(spec_with([MUTE]))['Mute']
        base = ops(spec_with([dict(BTN)]))['B']
        self.assertEqual(op['states'][1]['fill'], base['fill'])
        self.assertEqual(op['states'][1]['text'], 'Mute')
        self.assertEqual(op['states'][1]['border'], base['border'])

    def test_each_state_can_carry_its_own_caption_and_fill(self):
        st = ops(spec_with([MUTE]))['Mute']['states']
        self.assertEqual([s['text'] for s in st], ['Muted', 'Mute', 'Mute', 'Max'])
        self.assertEqual(len({s['fill'] for s in st}), 4)

    def test_the_control_looks_like_its_first_state(self):
        """Build renders a button from TLPDefaultStateID, which is 0, so the
        control-level look the verifier checks is state 0's."""
        op = ops(spec_with([MUTE]))['Mute']
        self.assertEqual(op['fill'], op['states'][0]['fill'])
        self.assertEqual(op['fields']['textField'], 'Muted')
        self.assertEqual(op['fields'][DEFAULT], 0)

    def test_press_shows_state_one_unless_told(self):
        """Off/On buttons show On while pressed: all 7518 in the seeds and
        fixtures. It is set, not inherited, because the donor's pointer may
        name a state the clone no longer has."""
        self.assertEqual(ops(spec_with([MUTE]))['Mute']['fields'][PRESS], 1)
        self.assertEqual(ops(spec_with([dict(BTN, on='accent')]))['B']['fields'][PRESS], 1)

    def test_press_names_a_state(self):
        op = ops(spec_with([dict(MUTE, press='Level 3')]))['Mute']
        self.assertEqual(op['fields'][PRESS], 3)

    def test_a_one_state_button_presses_to_itself(self):
        op = ops(spec_with([dict(BTN, states=['Idle'])]))['B']
        self.assertEqual([s['name'] for s in op['states']], ['Idle'])
        self.assertEqual(op['fields'][PRESS], 0)

    def test_a_button_without_feedback_keeps_the_donors_pointer(self):
        self.assertNotIn(PRESS, ops(spec_with([dict(BTN)]))['B']['fields'])

    def test_states_pass_through_a_grid(self):
        sp = spec_with([{'grid': {'rect': [0, 0, 600, 80], 'cols': 3, 'gap': 20,
                                  'kind': 'button', 'fill': 'raised',
                                  'states': ['Unavailable', {'name': 'Ready', 'fill': 'accent'},
                                             {'name': 'Connected', 'fill': 'surface'}],
                                  'items': [{'name': 'S1', 'text': 'One'},
                                            {'name': 'S2', 'text': 'Two'},
                                            {'name': 'S3', 'text': 'Three'}]}}])
        for n in ('S1', 'S2', 'S3'):
            self.assertEqual(len(ops(sp)[n]['states']), 3, n)

    def test_the_preview_draws_the_first_state(self):
        model, fills = spec_with([MUTE]).layout()
        c = model['Pages'][0]['Controls'][0]
        self.assertEqual(c['Text'], 'Muted')
        self.assertEqual(fills[(1000, 0)]['fill'], {'A': 255, 'R': 0xB0, 'G': 0x00, 'B': 0x20})

    def test_a_state_border_needs_a_donor_resource(self):
        """`donors` checks every border the spec names against the donor, and a
        state's border is one of them."""
        sp = spec_with([dict(BTN, states=['A', {'name': 'B', 'border': 'capsule'}])])
        self.assertIn(BORDERS['capsule'], sp.needs_borders())

    def test_state_colors_count_toward_the_palette(self):
        self.assertGreater(len(spec_with([MUTE]).palette()),
                           len(spec_with([dict(BTN)]).palette()))

    def test_a_valid_spec_has_no_state_problems(self):
        self.assertEqual([p for p in spec_with([MUTE]).check() if 'state' in p], [])


class TestStateChecks(unittest.TestCase):
    def problems(self, c, **kw):
        return [p for p in spec_with([c], **kw).check()
                if 'state' in p or 'press' in p or '`on`' in p]

    def test_only_a_button_has_states(self):
        self.assertTrue(self.problems({'kind': 'label', 'name': 'L', 'text': 'L',
                                       'rect': [0, 0, 100, 40], 'states': ['A', 'B']}))

    def test_on_and_states_together(self):
        self.assertTrue(self.problems(dict(MUTE, on='accent')))

    def test_an_empty_list(self):
        self.assertTrue(self.problems(dict(BTN, states=[])))

    def test_more_than_gui_designer_allows(self):
        self.assertTrue(self.problems(dict(BTN, states=[f'S{i}' for i in range(257)])))

    def test_a_nameless_state(self):
        self.assertTrue(self.problems(dict(BTN, states=['A', {'fill': 'accent'}])))

    def test_an_unknown_key_in_a_state(self):
        self.assertTrue(self.problems(dict(BTN, states=['A', {'name': 'B', 'fil': 'accent'}])))

    def test_duplicate_names(self):
        self.assertTrue(self.problems(dict(BTN, states=['A', {'name': 'A', 'fill': 'accent'}])))

    def test_two_states_that_look_the_same(self):
        """The control system sets one or the other and the panel shows no
        difference - the same inert button, one state further along."""
        found = self.problems(dict(BTN, states=['Off', {'name': 'On', 'fill': 'accent'},
                                                'Also Off']))
        self.assertTrue([p for p in found if 'identical' in p], found)

    def test_press_must_name_a_state(self):
        self.assertTrue(self.problems(dict(MUTE, press='Level 9')))

    def test_press_without_states(self):
        self.assertTrue(self.problems(dict(BTN, press='On')))

    def test_a_null_in_a_state(self):
        """Null is not 'transparent' or 'no caption' - the applier would skip
        the write and the state would keep whatever the donor had. Leave the
        key out, or say '#00000000' or ''."""
        for key in ('fill', 'stroke', 'color', 'text_color', 'border', 'text'):
            self.assertTrue(self.problems(dict(BTN, states=['A', {'name': 'B', key: None}])),
                            key)

    def test_on_true_with_no_accent_to_use(self):
        """`"on": true` means 'you pick', and the pick is the theme accent -
        without one the button would silently get no feedback at all."""
        found = self.problems(dict(BTN, on=True), theme={'accent': None})
        self.assertTrue([p for p in found if 'accent' in p], found)

    def test_an_unknown_border_in_a_state(self):
        found = [p for p in spec_with([dict(BTN, states=['A', {'name': 'B', 'border': 'Nope'}])])
                 .check() if 'border' in p]
        self.assertTrue(found)


class TestDonorGate(unittest.TestCase):
    """The applier now gives the cloned button exactly the states the spec
    names - growing by cloning its last state, trimming from the end. The one
    thing that stops it is PBStates.statusField, PBState.StatusFlags on the
    donor (PreventAddState and friends): 0 on every button in the corpus."""

    def test_the_fixture_can_supply_any_number_of_states(self):
        sp = spec_with([MUTE])
        problems = [p for p in sp.check_donor(FIXTURE) if 'state' in p]
        self.assertEqual(problems, [])

    def test_a_flagged_donor_button_is_refused(self):
        from unittest import mock
        real = Project.control

        def flagged(self, obj):
            out = real(self, obj)
            if out['type'] == 'PBButton':
                out['state_flags'] = 1          # PreventAddState
            return out
        with mock.patch.object(Project, 'control', flagged):
            problems = [p for p in spec_with([MUTE]).check_donor(FIXTURE) if 'state' in p]
        self.assertTrue(problems)


class TestReaderCountsStates(unittest.TestCase):
    """`n_states` has to be the real count - the length of `mItems` - and
    not the 1 PowerShell reports for `$states.Count`."""

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
        self.assertTrue([p for p in problems if 'planned 2 states' in p],
                        f'expected a missing-state problem, got {problems}')

    def test_a_surplus_state_is_a_problem(self):
        """A clone that kept a donor state the spec never named - 'Level 3' on
        an Off/On button - is a state the program can set and nobody drew."""
        plan, table = self._plan_and_layout(90, 91)
        table['P1']['Controls'][0]['States'].append({'Name': 'Level 3', 'TLPImageID': 92})
        assets = {90: self.png((0x37, 0x39, 0x4E)), 91: self.png((0x3D, 0x8B, 0xFD)),
                  92: self.png((1, 2, 3))}
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertTrue([p for p in problems if "'Level 3'" in p], problems)

    def _four(self, tids, **op_extra):
        names = ['Muted', 'Level 1', 'Level 2', 'Level 3']
        fills = [0xFFB00020, 0xFF1E4D2B, 0xFF2E7D32, 0xFF66BB6A]
        plan = [{'name': 'P1', 'controls': [dict({
            'fields': {'nameField': 'M', PRESS: 3, DEFAULT: 0},
            'states': [{'name': n, 'fill': f, 'text': n} for n, f in zip(names, fills)],
        }, **op_extra)]}]
        table = {'P1': {'Name': 'P1', 'Controls': [{
            'Name': 'M', 'TLPImageID': tids[0], 'TLPDefaultStateID': 0,
            'TLPPressFeedbackStateID': 3,
            'States': [{'Name': n, 'Text': n, 'TLPImageID': t} for n, t in zip(names, tids)],
        }]}}
        assets = {t: self.png(((f >> 16) & 255, (f >> 8) & 255, f & 255))
                  for t, f in zip(tids, fills)}
        return plan, table, assets

    def test_four_distinct_states_pass(self):
        plan, table, assets = self._four([90, 91, 92, 93])
        problems, _, checked = self.vb.check_states(plan, table, assets, 'page')
        self.assertEqual(problems, [])
        self.assertEqual(checked, 4)

    def test_two_planned_states_sharing_artwork_is_a_problem(self):
        """Build dedupes identical rasterizations to one TLPImageID, so two
        states planned differently but built as one image are one state."""
        plan, table, assets = self._four([90, 91, 92, 93])
        table['P1']['Controls'][0]['States'][3]['TLPImageID'] = 92
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertTrue([p for p in problems if "'Level 2'" in p and "'Level 3'" in p],
                        problems)

    def test_states_differing_only_in_words_may_share_artwork(self):
        """Captions are drawn live from layout.json, not baked into the art, so
        'Warming Up' and 'Cooling Down' on the same fill are one image and two
        states - found on the first four-state build."""
        plan, table, assets = self._four([90, 91, 92, 93])
        plan[0]['controls'][0]['states'][3]['fill'] = plan[0]['controls'][0]['states'][2]['fill']
        table['P1']['Controls'][0]['States'][3]['TLPImageID'] = 92
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertEqual([p for p in problems if 'same artwork' in p], [])

    def test_a_per_state_text_color_is_checked(self):
        plan, table, assets = self._four([90, 91, 92, 93])
        plan[0]['controls'][0]['states'][1]['text_color'] = 0xFFBABCCE
        table['P1']['Controls'][0]['States'][1]['TextColor'] = {'A': 255, 'R': 255, 'G': 255,
                                                                'B': 255}
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertTrue([p for p in problems if 'text color' in p], problems)

    def test_a_missing_text_color_is_a_problem(self):
        plan, table, assets = self._four([90, 91, 92, 93])
        plan[0]['controls'][0]['states'][1]['text_color'] = 0xFFBABCCE
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertTrue([p for p in problems if 'text color' in p], problems)

    def test_a_per_state_caption_is_checked(self):
        plan, table, assets = self._four([90, 91, 92, 93])
        table['P1']['Controls'][0]['States'][2]['Text'] = 'Level 1'
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertTrue([p for p in problems if 'caption' in p], problems)

    def test_the_press_state_is_checked(self):
        plan, table, assets = self._four([90, 91, 92, 93])
        table['P1']['Controls'][0]['TLPPressFeedbackStateID'] = 1
        problems, _, _ = self.vb.check_states(plan, table, assets, 'page')
        self.assertTrue([p for p in problems if 'press' in p], problems)


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
