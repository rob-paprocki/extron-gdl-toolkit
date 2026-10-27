"""The built-file verifier's layout checks: start page, modal popups, type names.

Each of these was a silent failure before it was checked. A generated panel
booted into the donor's start page, and a spec's modal confirmation built as a
standard popup that nothing could show. Both builds reported 0 errors.

    python tests/test_verify_built.py
"""
import io
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from _corpus import usable  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(HERE), 'fixtures', 'gdl',
                       'client-boardroom-2.0.0.gdl')


def _vb(test):
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        test.skipTest('Pillow not installed; verify_built imports the compositor')
    import verify_built
    return verify_built


def _ref(popup_id):
    return {'Type': 6, 'Name': 'Popup Page Reference',
            'PopupPageID': {'GroupID': 0, 'IsPopupGroupIdValid': False,
                            'IsPopupPageIdValid': True, 'PopupID': popup_id}}


class TestStartPage(unittest.TestCase):
    LAYOUT = {'DefaultPage': 21,
              'Pages': [{'ID': 21, 'Name': '1000 - Home', 'Controls': []},
                        {'ID': 51, 'Name': 'Home', 'Controls': []}],
              'PopupPages': []}

    def test_booting_into_the_donors_page_is_reported(self):
        vb = _vb(self)
        problems = vb.check_start_page({'default_page': 'Home'}, self.LAYOUT)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('1000 - Home', problems[0])

    def test_the_planned_start_page_passes(self):
        vb = _vb(self)
        layout = dict(self.LAYOUT, DefaultPage=51)
        self.assertEqual(vb.check_start_page({'default_page': 'Home'}, layout), [])

    def test_a_plan_without_a_start_page_is_not_checked(self):
        # Plans written before start pages existed must still verify.
        vb = _vb(self)
        self.assertEqual(vb.check_start_page({}, self.LAYOUT), [])


class TestNothingButThePlan(unittest.TestCase):
    """A generated panel is its spec's pages and popups. The donor's own stayed
    in the built file - a seed's whole demo beside the spec's - unreachable,
    and some of their controls on the spec's own IDs (docs/from-scratch.md
    section 5c)."""
    LAYOUT = {'OfflinePageID': 65535,
              'Pages': [{'ID': 51, 'Name': 'Home', 'Controls': []},
                        {'ID': 3, 'Name': 'Main VC', 'Controls': []}],
              'PopupPages': [{'ID': 52, 'Name': 'Confirm', 'Modal': True},
                             {'ID': 65535, 'Name': 'Offline Page', 'Modal': True},
                             {'ID': 9, 'Name': 'Recording Controls', 'Modal': True}]}
    PLAN = {'pages': [{'name': 'Home'}], 'popups': [{'name': 'Confirm', 'modal': True}]}

    def test_a_donor_page_or_popup_left_in_is_reported(self):
        vb = _vb(self)
        problems = vb.check_only_planned(self.PLAN, self.LAYOUT)
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any("'Main VC'" in p for p in problems), problems)
        self.assertTrue(any("'Recording Controls'" in p for p in problems), problems)

    def test_the_offline_page_is_gui_designers_own(self):
        vb = _vb(self)
        layout = dict(self.LAYOUT, Pages=self.LAYOUT['Pages'][:1],
                      PopupPages=self.LAYOUT['PopupPages'][:2])
        self.assertEqual(vb.check_only_planned(self.PLAN, layout), [])

    def test_a_plan_that_keeps_the_donor_is_not_held_to_it(self):
        vb = _vb(self)
        self.assertEqual(vb.check_only_planned(dict(self.PLAN, keep_donor_pages=True),
                                               self.LAYOUT), [])


class TestModalPopups(unittest.TestCase):
    def _layout(self, modal, refs=True):
        page = {'ID': 51, 'Name': 'Home', 'Controls': [_ref(52)] if refs else []}
        return {'Pages': [page],
                'PopupPages': [{'ID': 52, 'Name': 'Confirm', 'Modal': modal, 'GroupID': 0}]}

    PLAN = {'pages': [{'name': 'Home'}], 'popups': [{'name': 'Confirm', 'modal': True}]}

    def test_a_modal_that_built_standard_is_reported(self):
        vb = _vb(self)
        problems = vb.check_modal(self.PLAN, self._layout(modal=False))
        self.assertTrue(any('standard' in p for p in problems), problems)

    def test_a_modal_with_no_reference_on_a_page_is_reported(self):
        vb = _vb(self)
        problems = vb.check_modal(self.PLAN, self._layout(modal=True, refs=False))
        self.assertTrue(any('reference' in p for p in problems), problems)

    def test_a_modal_built_as_asked_passes(self):
        vb = _vb(self)
        self.assertEqual(vb.check_modal(self.PLAN, self._layout(modal=True)), [])

    def test_a_standard_popup_that_built_modal_is_reported(self):
        vb = _vb(self)
        plan = {'pages': [], 'popups': [{'name': 'Confirm', 'modal': False}]}
        problems = vb.check_modal(plan, self._layout(modal=True))
        self.assertTrue(any('modal' in p for p in problems), problems)


class TestPopupSize(unittest.TestCase):
    """A popup's built size is its authored size (docs/gdl-format.md section 5):
    the applier writes the plan's, and the built page says it."""
    PLAN = {'pages': [], 'popups': [{'name': 'Sources', 'size': [800, 400]},
                                    {'name': 'Confirm', 'modal': True, 'size': None}]}

    def _layout(self, w, h):
        return {'PopupPages': [{'ID': 52, 'Name': 'Sources', 'Width': w, 'Height': h},
                               {'ID': 53, 'Name': 'Confirm', 'Width': 1, 'Height': 1}]}

    def test_a_popup_built_at_another_size_is_reported(self):
        vb = _vb(self)
        problems = vb.check_popup_size(self.PLAN, self._layout(995, 549))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("'Sources'", problems[0])
        self.assertIn('995x549', problems[0])
        self.assertIn('800x400', problems[0])

    def test_a_popup_built_as_planned_passes(self):
        vb = _vb(self)
        self.assertEqual(vb.check_popup_size(self.PLAN, self._layout(800, 400)), [])

    def test_check_runs_it(self):
        self.assertIn('check_popup_size(plan, j)', open(_vb(self).__file__, encoding='utf-8').read())


class TestClockPattern(unittest.TestCase):
    def _check(self, pattern):
        vb = _vb(self)
        plan = {'pages': [{'name': 'Home', 'controls': [{'fields': {
            'nameField': 'Date', 'textField': 'September 28', 'patternField': 'MMMM d'}}]}]}
        pages = {'Home': {'ID': 51, 'Name': 'Home', 'Controls': [
            {'ID': 1, 'Type': 8, 'Name': 'Date', 'Left': 0, 'Top': 0, 'Width': 1,
             'Height': 1, 'Text': 'September 28', 'Pattern': pattern}]}}
        return vb.check_placed(plan, pages, {})[0]

    def test_a_clock_that_kept_the_donors_pattern_is_reported(self):
        problems = self._check('MMMM d, h:mm tt')
        self.assertTrue(any('clock pattern' in p for p in problems), problems)

    def test_the_planned_pattern_passes(self):
        self.assertEqual(self._check('MMMM d'), [])


class TestPressFeedback(unittest.TestCase):
    def test_a_button_built_with_its_press_feedback_hidden_is_reported(self):
        vb = _vb(self)
        plan = {'pages': [{'name': 'Home', 'controls': [{'fields': {
            'nameField': 'Help', '<HidePressFeedback>k__BackingField': False,
            '<HideVisualFeedback>k__BackingField': False}}]}]}
        for hidden, bad in ((False, False), (True, True)):
            pages = {'Home': {'ID': 51, 'Name': 'Home', 'Controls': [
                {'ID': 1, 'Type': 7, 'Name': 'Help', 'Left': 0, 'Top': 0, 'Width': 1,
                 'Height': 1, 'HidePressFeedback': hidden, 'HideVisualFeedback': False}]}}
            problems = vb.check_placed(plan, pages, {})[0]
            self.assertEqual(any('HidePressFeedback' in p for p in problems), bad, problems)


class TestAlignment(unittest.TestCase):
    """The applier writes each control's text alignment and a clone keeps its
    donor's: a left-aligned label built centred reads off by half its width.
    Nothing checked it once the panel was built."""

    def _check(self, built):
        vb = _vb(self)
        plan = {'pages': [{'name': 'Home', 'controls': [
            {'alignment': 4, 'fields': {'nameField': 'Title'}}]}]}
        pages = {'Home': {'ID': 51, 'Name': 'Home', 'Width': 1280, 'Height': 800, 'Controls': [
            {'ID': 1, 'Type': 11, 'Name': 'Title', 'Left': 0, 'Top': 0, 'Width': 1,
             'Height': 1, 'TextAlignment': built}]}}
        return vb.check_placed(plan, pages, {})[0]

    def test_a_label_built_with_another_alignment_is_reported(self):
        problems = self._check(3)
        self.assertTrue(any('alignment' in p and "'left'" in p and "'center'" in p
                            for p in problems), problems)

    def test_the_planned_alignment_passes(self):
        self.assertEqual(self._check(4), [])

    def test_states_that_disagree_are_named_not_numbered(self):
        """9 is no alignment: GUI Designer writes it on a control whose states
        disagree - every such button in the archived builds, and none of the
        seed and fixture buttons whose states agree."""
        vb = _vb(self)
        plan = {'pages': [{'name': 'Home', 'controls': [
            {'alignment': 3, 'fields': {'nameField': 'Laptop'}}]}]}
        pages = {'Home': {'ID': 51, 'Name': 'Home', 'Width': 1280, 'Height': 800, 'Controls': [
            {'ID': 1, 'Type': 7, 'Name': 'Laptop', 'Left': 0, 'Top': 0, 'Width': 1, 'Height': 1,
             'TextAlignment': 9, 'States': [{'Name': 'Off', 'TextAlignment': 3},
                                            {'Name': 'On', 'TextAlignment': 4}]}]}}
        problems = [p for p in vb.check_placed(plan, pages, {})[0] if 'alignment' in p]
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("'Off' 'center', 'On' 'left'", problems[0])
        self.assertNotIn('alignment 9', problems[0])


class TestNothingUnplannedOnAPage(unittest.TestCase):
    """A generated page is cloned from a donor page and cleared; a control of
    the donor's left on it ships unasked. Build adds one full-canvas popup
    reference per modal to every page, and those are its own."""
    PLAN = {'pages': [{'name': 'Home', 'controls': [{'fields': {'nameField': 'Help'}}]}]}

    def _pages(self, *extra):
        return {'Home': {'ID': 51, 'Name': 'Home', 'Width': 1280, 'Height': 800, 'Controls': [
            {'ID': 1, 'Type': 7, 'Name': 'Help', 'Left': 10, 'Top': 10, 'Width': 100,
             'Height': 60}] + list(extra)}}

    def test_a_control_the_plan_did_not_make_is_reported(self):
        vb = _vb(self)
        stray = {'ID': 2, 'Type': 7, 'Name': 'Record', 'Left': 200, 'Top': 10, 'Width': 100,
                 'Height': 60}
        problems = vb.check_placed(self.PLAN, self._pages(stray), {})[0]
        self.assertTrue(any("'Record'" in p and 'not in the plan' in p for p in problems),
                        problems)

    def test_builds_own_modal_references_are_not(self):
        vb = _vb(self)
        ref = {'ID': 3, 'Type': 6, 'Name': 'Popup Page Reference', 'Left': 0, 'Top': 0,
               'Width': 1280, 'Height': 800}
        self.assertEqual(vb.check_placed(self.PLAN, self._pages(ref), {})[0], [])


class TestBorders(unittest.TestCase):
    """layout.json keeps no border's name - Build rasterizes it - so a plan
    that names one the donor lacks (`plan` run without --donor) left the
    clone's own border, the applier only warning, and every gate green. The
    built project still names each control's and state's border."""

    REPO = os.path.dirname(HERE)

    def _seed(self):
        seed = os.path.join(self.REPO, 'seeds', 'Afterburn 1035.gdl')
        if not usable(seed):
            self.skipTest('seeds/Afterburn 1035.gdl is not pulled from Git LFS here')
        return seed

    @staticmethod
    def _plan(border):
        return {'pages': [{'name': 'Start', 'controls': [
            {'fields': {'nameField': 'Main Volume Slider'}, 'border': border}]}]}

    def test_a_built_border_is_the_planned_one(self):
        vb = _vb(self)
        problems, checked = vb.check_borders(self._plan('Afterburn - 14 Radius 0 Thick'), self._seed())
        self.assertEqual((problems, checked), ([], 1))

    def test_a_border_the_plan_names_and_the_build_lacks_is_a_problem(self):
        vb = _vb(self)
        problems, _ = vb.check_borders(self._plan('Afterburn - 10 Radius 0 Thick'), self._seed())
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("'Afterburn - 14 Radius 0 Thick', planned 'Afterburn - 10 Radius 0 Thick'", problems[0])

    def test_each_states_border_is_checked(self):
        vb = _vb(self)
        build = os.path.join(self.REPO, 'archive', 'job-2419a20b', 'borders')
        if not usable(os.path.join(build, 'Borders320.gdl')):
            self.skipTest('the archived 320 border build is not pulled from Git LFS here')
        with open(os.path.join(build, 'plan.json'), encoding='utf-8') as fh:
            plan = json.load(fh)
        built = os.path.join(build, 'Borders320.gdl')
        self.assertEqual(vb.check_borders(plan, built)[0], [])
        laptop = next(op for op in plan['pages'][0]['controls']
                      if op['fields'].get('nameField') == 'Laptop')
        laptop['states'][1]['border'] = 'Afterburn - 10 Radius 0 Thick'
        problems = vb.check_borders(plan, built)[0]
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("state 'On'", problems[0])


class TestEditIds(unittest.TestCase):
    """A renumber is verified by comparing the built control's ID - which the
    verifier looked up as 'UserID', a key layout.json never writes, so the
    comparison was skipped every time."""

    def test_a_renumber_that_did_not_take_is_reported(self):
        vb = _vb(self)
        plan = {'controls': [{'page': 51, 'control': 3,
                              'fields': {'userIdField': 2001}}]}
        j = {'Pages': [{'ID': 51, 'Name': 'Home', 'Controls': [
            {'ID': 3, 'Name': 'Mute', 'UserId': 1011, 'States': []}]}],
             'PopupPages': []}
        problems, _ = vb.check_edits(plan, j)
        self.assertTrue(any('UserId' in p and '2001' in p for p in problems), problems)


def _placed(test, fields, built, op=None):
    """check_placed's problems for one planned control on page 'P' and the
    built control `built`, both at 0,0 10x10."""
    vb = _vb(test)
    f = dict({'nameField': 'C', 'leftField': 0, 'topField': 0, 'widthField': 10,
              'heightField': 10}, **fields)
    plan = {'pages': [{'name': 'P', 'controls': [dict(op or {}, fields=f)]}]}
    c = dict({'Name': 'C', 'Left': 0, 'Top': 0, 'Width': 10, 'Height': 10}, **built)
    return vb.check_placed(plan, {'P': {'Name': 'P', 'Controls': [c]}}, {})[0]


class TestControlIds(unittest.TestCase):
    """The program addresses a control by its ID alone, and a clone keeps its
    donor's when the write does not take - two controls then answer to one.
    Only verify_idmap read the IDs back, and New-GdlPanel runs it only with
    -IdMap."""

    def test_a_control_that_kept_another_id_is_reported(self):
        problems = _placed(self, {'userIdField': 2001}, {'Type': 7, 'UserId': 777})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('ID 777, planned 2001', problems[0])

    def test_the_planned_id_passes(self):
        self.assertEqual(_placed(self, {'userIdField': 2001}, {'Type': 7, 'UserId': 2001}), [])


class TestTextColor(unittest.TestCase):
    """A label's or a clock's text color is in the model, not the artwork, and
    only a button's planned states were read back - so a label that kept its
    donor's color, dark on a dark page, verified clean."""

    WHITE, BLACK = {'A': 255, 'R': 255, 'G': 255, 'B': 255}, {'A': 255, 'R': 0, 'G': 0, 'B': 0}

    def _check(self, built, fields=None, **op):
        fields = dict({'textField': 'Room 101'}, **(fields or {}))
        built = dict({'Type': 11, 'Text': fields['textField'],
                      'Pattern': fields.get('patternField')}, **built)
        for s in built.get('States') or []:
            s.setdefault('Text', fields['textField'])
        return _placed(self, fields, built, dict({'text_color': 0xFFFFFFFF}, **op))

    def test_a_label_that_kept_its_donors_color_is_reported(self):
        problems = self._check({'TextColor': self.BLACK})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('text color #000000, planned #FFFFFF', problems[0])

    def test_the_planned_color_passes(self):
        self.assertEqual(self._check({'TextColor': self.WHITE}), [])

    def test_a_clock_is_held_to_it(self):
        problems = self._check({'Type': 8, 'TextColor': self.BLACK},
                               {'textField': 'September 28', 'patternField': 'MMMM d'})
        self.assertEqual(len(problems), 1, problems)

    def test_a_button_with_no_planned_states_is_read_state_by_state(self):
        """The applier writes the one color to every donor state, and the
        panel draws a button's caption from its state."""
        built = {'Type': 7, 'TextColor': self.WHITE,
                 'States': [{'Name': 'Off', 'TextColor': self.WHITE},
                            {'Name': 'On', 'TextColor': self.BLACK}]}
        problems = self._check(built)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("state 'On'", problems[0])

    def test_a_wrong_color_on_a_control_and_its_states_is_reported_once(self):
        built = {'Type': 7, 'TextColor': self.BLACK,
                 'States': [{'Name': 'Off', 'TextColor': self.BLACK},
                            {'Name': 'On', 'TextColor': self.BLACK}]}
        problems = self._check(built)
        self.assertEqual(len(problems), 1, problems)

    def test_planned_states_are_check_states_own(self):
        built = {'Type': 7, 'States': [{'Name': 'Off', 'TextColor': self.BLACK}]}
        self.assertEqual(self._check(built, states=[{'name': 'Off', 'text_color': 0xFF000000}]), [])

    def test_a_control_with_no_caption_is_not_held_to_one(self):
        self.assertEqual(self._check({'Type': 13, 'TextColor': self.BLACK},
                                     {'textField': ''}), [])


class TestSliderGeometry(unittest.TestCase):
    """A slider's orientation, track width and thumb size are fields a clone
    keeps from its donor - every seed's slider stands up - and the rail check
    drew its expected art from the built values, so a donor's passed as
    itself. layout.json carries the authoring fields under its own names:
    orientationField as Orientation, sliderTrackWidth as SliderTrackWidth and
    sliderThumbWidth and sliderThumbHeight as SliderIndicatorWidth and
    SliderIndicatorHeight, on every slider and level of the Afterburn 1035 and
    525, Shockwave 725 and 320 and Zoom Rooms seeds."""

    FIELDS = {'orientationField': 0, 'sliderTrackWidth': 9, 'sliderThumbWidth': 7,
              'sliderThumbHeight': 25}
    BUILT = {'Type': 27, 'Orientation': 0, 'SliderTrackWidth': 9, 'SliderIndicatorWidth': 7,
             'SliderIndicatorHeight': 25}

    def test_a_slider_as_planned_passes(self):
        self.assertEqual(_placed(self, self.FIELDS, self.BUILT), [])

    def test_the_donors_orientation_is_reported(self):
        problems = _placed(self, self.FIELDS, dict(self.BUILT, Orientation=2))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("orientation 'up', planned 'right'", problems[0])

    def test_the_donors_track_and_thumb_are_reported(self):
        problems = _placed(self, self.FIELDS, dict(self.BUILT, SliderTrackWidth=10,
                                                   SliderIndicatorWidth=50,
                                                   SliderIndicatorHeight=50))
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any('track 10 wide, planned 9' in p for p in problems), problems)
        self.assertTrue(any('thumb 50x50, planned 7x25' in p for p in problems), problems)

    def test_a_levels_orientation_is_checked(self):
        problems = _placed(self, {'orientationField': 3}, {'Type': 9, 'Orientation': 2})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("planned 'down'", problems[0])


class TestNoArtwork(unittest.TestCase):
    """A page or popup that built with no artwork shows the panel's default
    behind its controls, and its fill check stepped over it - quieter as the
    build got worse. Every built page and every referenced standard popup in
    the 47 corpus projects has artwork; the only ones without are GUI
    Designer's 35 Offline Pages and an unreferenced popup in two archived
    client projects."""

    def setUp(self):
        self.vb = _vb(self)

    def test_a_page_with_none_is_reported(self):
        for tid in (-1, None, 5):
            problems = self.vb.check_page_background(
                [{'name': 'P', 'background': 0xFF112233}], {'P': {'TLPImageID': tid}}, {})
            self.assertEqual(len(problems), 1, (tid, problems))
            self.assertIn('no artwork', problems[0])

    def test_a_popup_with_none_is_reported(self):
        for background in (0xFF112233, 0x00000000):
            problems = self.vb.check_popup_background(
                [{'name': 'P', 'background': background}], {'P': {'TLPImageID': -1}}, {})
            self.assertEqual(len(problems), 1, (background, problems))
            self.assertIn('no artwork', problems[0])

    def test_a_modal_with_none_is_reported(self):
        problems = self.vb.check_popup_background(
            [{'name': 'M', 'modal': True, 'background': 0xFF000000, 'transparency': 35.0}],
            {'M': {'TLPImageID': -1}}, {})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('no artwork', problems[0])


@unittest.skipUnless(usable(FIXTURE), 'the client fixture is not here')
class TestPopupGroupBinding(unittest.TestCase):
    """A reference bound to the wrong group, or to none, reads 'Unassigned' or
    opens the wrong popup, and is invisible in every other field. The check
    read a `PopupGroups` key no layout.json has - none of the corpus's 47 - so
    it never fired. The built file records the binding on the reference
    (PopupPageID.GroupID, IsPopupGroupIdValid), on each popup (GroupID) and in
    the project's group registry, which names each group."""

    PAGE, REF, GROUP = '2000 - Main - Presentation', 'Volume Popup Page Reference', 'Volume Popups'
    PLAN = {'generated_by': 'gdl.spec', 'popup_groups': [GROUP],
            'pages': [{'name': PAGE, 'controls': [
                {'donor_type': 'PBPopupPageReference', 'group': GROUP,
                 'fields': {'nameField': REF}}]}],
            'popups': [{'name': '2210 - Conference Volume', 'group': GROUP, 'modal': False},
                       {'name': '2220 - CATV Volume', 'group': GROUP, 'modal': False}]}

    def setUp(self):
        self.vb = _vb(self)
        from gdl.compose import load
        self.j, _ = load(FIXTURE)
        self.registry = self.vb.popup_group_registry(FIXTURE)

    def _ref(self):
        page = next(p for p in self.j['Pages'] if p['Name'] == self.PAGE)
        return next(c for c in page['Controls'] if c['Name'] == self.REF)['PopupPageID']

    def _check(self, plan=None, registry=None):
        return self.vb.check_popup_groups(plan or self.PLAN, self.j,
                                          self.registry if registry is None else registry)

    def test_the_registry_is_read_off_the_built_project(self):
        self.assertEqual(self.registry, {1: 'Volume Popups', 2: 'Tech Popups',
                                         3: 'Presentation Popups', 5: 'Keyboards'})

    def test_a_binding_as_planned_passes(self):
        self.assertEqual(self._check(), [])

    def test_a_reference_bound_to_another_group_is_reported(self):
        self._ref()['GroupID'] = 3
        problems = self._check()
        self.assertTrue(any(self.REF in p and 'group 3' in p and "'Volume Popups'" in p
                            for p in problems), problems)

    def test_a_reference_bound_to_nothing_is_reported(self):
        self._ref().update(GroupID=0, IsPopupGroupIdValid=False)
        problems = self._check()
        self.assertTrue(any(self.REF in p and 'Unassigned' in p for p in problems), problems)

    def test_a_group_registered_under_another_name_is_reported(self):
        problems = self._check(registry={1: 'Volume', 2: 'Tech Popups',
                                         3: 'Presentation Popups', 5: 'Keyboards'})
        self.assertTrue(any("'Volume'" in p and "'Volume Popups'" in p for p in problems), problems)

    def test_an_unregistered_group_is_reported(self):
        problems = self._check(registry={2: 'Tech Popups', 3: 'Presentation Popups',
                                         5: 'Keyboards'})
        self.assertTrue(any('registry' in p and 'Unassigned' in p for p in problems), problems)

    def test_a_planned_popup_built_in_no_group_is_reported(self):
        next(p for p in self.j['PopupPages']
             if p['Name'] == '2210 - Conference Volume').update(GroupID=0, IsGroupValid=False)
        problems = self._check()
        self.assertTrue(any("'2210 - Conference Volume' in no group" in p for p in problems),
                        problems)
        plan = dict(self.PLAN, popups=self.PLAN['popups'][:1])
        problems = self._check(plan)
        self.assertTrue(any('2210 - Conference Volume' in p and 'built in no group' in p
                            for p in problems), problems)

    def test_a_planned_group_split_across_two_built_groups_is_reported(self):
        next(p for p in self.j['PopupPages'] if p['Name'] == '2220 - CATV Volume')['GroupID'] = 2
        problems = self._check()
        self.assertTrue(any("'Volume Popups'" in p and '2220 - CATV Volume' in p
                            for p in problems), problems)

    def test_the_hunts_repro_every_group_reference_rebound_to_999(self):
        """No plan reference at all - a donor's kept pages - and still caught:
        a group no popup is in shows nothing."""
        n = 0
        for page in self.j['Pages']:
            for c in page.get('Controls') or []:
                pp = c.get('PopupPageID')
                if isinstance(pp, dict) and pp.get('IsPopupGroupIdValid'):
                    pp['GroupID'] = 999
                    n += 1
        problems = self._check(plan={'pages': [], 'popups': [], 'keep_donor_pages': True})
        self.assertEqual(n, 4)
        self.assertEqual(len([p for p in problems if 'group 999' in p]), 4, problems)

    def test_a_kept_reference_bound_to_nothing_is_reported(self):
        self._ref().update(GroupID=0, IsPopupGroupIdValid=False)
        problems = self._check(plan={'pages': [], 'popups': [], 'keep_donor_pages': True})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('Unassigned', problems[0])

    def test_a_planned_reference_bound_to_nothing_is_reported_once(self):
        self._ref().update(GroupID=0, IsPopupGroupIdValid=False)
        self.assertEqual(len([p for p in self._check() if self.REF in p]), 1)

    def test_a_reference_to_a_popup_that_is_not_there_is_reported(self):
        self._ref().update(GroupID=0, IsPopupGroupIdValid=False, IsPopupPageIdValid=True,
                           PopupID=4242)
        problems = self._check(plan={'pages': [], 'popups': [], 'keep_donor_pages': True})
        self.assertTrue(any('4242' in p for p in problems), problems)

    def test_a_direct_reference_to_one_popup_is_not_a_group_binding(self):
        """Extron's 525s bind Volume Level by its PopupID, at GroupID 0."""
        self._ref().update(GroupID=0, IsPopupGroupIdValid=False, IsPopupPageIdValid=True,
                           PopupID=2)
        problems = self._check(plan={'pages': [], 'popups': [], 'keep_donor_pages': True})
        self.assertEqual(problems, [])


class TestRetarget(unittest.TestCase):
    """An edit plan's `project` ops set the panel model and screen, and its
    `pages` ops each page's and popup's own canvas. None of that is a control,
    and check_edits walked only plan['controls'] - so a retarget without
    `scale`, which plans no control at all, verified against a file that was
    never retargeted with 0 checks and exit 0."""

    PLAN = {'generated_by': 'gdl.edit',
            'project': [{'why': 'retarget to TLP1535M (1920x1080)', 'model': 'TLP1535M',
                         'size': [1920, 1080]}],
            'pages': [{'page': 1, 'name': 'Home', 'kind': 'page', 'was': [1280, 800],
                       'size': [1920, 1080]},
                      {'page': 2, 'name': 'Volume', 'kind': 'popup', 'was': [136, 496],
                       'size': [204, 670]}],
            'controls': []}

    @staticmethod
    def _layout(screen=(1920, 1080), part='60-2000-02', home=(1920, 1080), volume=(204, 670)):
        return {'ScreenSize': {'width': screen[0], 'height': screen[1]},
                'PartNumber': part,
                'Platform': {'HorizontalResolution': screen[0], 'VerticalResolution': screen[1],
                             'PartNumber': part},
                'Pages': [{'ID': 1, 'Name': 'Home', 'Width': home[0], 'Height': home[1],
                           'Controls': []}],
                'PopupPages': [{'ID': 2, 'Name': 'Volume', 'Width': volume[0],
                                'Height': volume[1], 'Controls': []}]}

    def test_a_retarget_built_as_planned_passes(self):
        vb = _vb(self)
        problems, checked = vb.check_edits(self.PLAN, self._layout())
        self.assertEqual(problems, [])
        self.assertEqual(checked, 3)

    def test_a_screen_left_at_the_old_size_is_reported(self):
        vb = _vb(self)
        problems, _ = vb.check_edits(self.PLAN, self._layout(screen=(1280, 800)))
        self.assertTrue(any('1280x800' in p and '1920x1080' in p and 'screen' in p
                            for p in problems), problems)

    def test_another_models_part_number_is_reported(self):
        vb = _vb(self)
        problems, _ = vb.check_edits(self.PLAN, self._layout(part='60-1999-02'))
        self.assertTrue(any('60-1999-02' in p and 'TLP1535M' in p for p in problems), problems)

    def test_a_page_or_popup_at_another_size_is_reported(self):
        vb = _vb(self)
        problems, _ = vb.check_edits(self.PLAN, self._layout(home=(1280, 800),
                                                             volume=(1920, 1080)))
        self.assertTrue(any("'Home'" in p and '1280x800' in p for p in problems), problems)
        self.assertTrue(any("'Volume'" in p and '1920x1080' in p for p in problems), problems)

    def test_an_unretargeted_seed_fails_its_retarget_plan(self):
        """The hunt's own repro: a scaled TLP1020M plan, its control ops
        dropped, against the Mach 1035 seed it was planned from."""
        vb = _vb(self)
        seed = os.path.join(os.path.dirname(HERE), 'seeds', 'Mach 1035.gdl')
        if not usable(seed):
            self.skipTest('seeds/Mach 1035.gdl is not pulled from Git LFS here')
        from gdl.edit import Edits
        plan, errors = Edits({'edits': [{'op': 'retarget', 'model': 'TLP1020M',
                                         'scale': True}]}, seed).plan()
        self.assertEqual(errors, [])
        plan['controls'] = []
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'plan.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(plan, fh)
            problems, checked = vb.check(path, seed)
        self.assertTrue(any('screen' in p for p in problems), problems)
        self.assertTrue(any('TLP1020M' in p for p in problems), problems)
        self.assertGreater(len(problems), len(plan['pages']) // 2, problems)
        self.assertGreater(checked, 0)


def _png(rgb):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGBA', (8, 8), rgb + (255,)).save(buf, 'PNG')
    return buf.getvalue()


WHITE = {'A': 255, 'R': 255, 'G': 255, 'B': 255}


def _built(*states, **kw):
    c = dict({'ID': 3, 'Name': 'Display', 'States': list(states)}, **kw)
    return {'Pages': [{'ID': 51, 'Name': 'Home', 'Controls': [c]}], 'PopupPages': []}


def _bst(name, text, tid, color=WHITE):
    return {'Name': name, 'Text': text, 'TLPImageID': tid, 'TextColor': color}


class TestLevelFill(unittest.TestCase):
    """A Level's fill is its track - its empty art. Build names a Level's full
    bar as its TLPImageID (every Level in the seeds and fixtures; a Slider's
    is its track), so reading TLPImageID failed a Level built exactly as
    planned: the 525's and 320's volume, the slider those seeds lack."""

    TRACK, BAR = (0x37, 0x39, 0x4E), (0x62, 0x6A, 0xCF)

    def _check(self, track):
        vb = _vb(self)
        plan = [{'name': 'Home', 'controls': [
            {'fields': {'nameField': 'Volume'}, 'fill': 0xFF37394E}]}]
        table = {'Home': {'ID': 51, 'Name': 'Home', 'Controls': [
            {'ID': 8, 'Type': 9, 'Name': 'Volume', 'TLPImageID': 36,
             'TLPMinValueImageID': 35, 'TLPMaxValueImageID': 36}]}}
        return vb.check_fills(plan, table, {35: _png(track), 36: _png(self.BAR)}, 'page')

    def test_a_level_built_as_planned_passes(self):
        problems, _, checked = self._check(self.TRACK)
        self.assertEqual(problems, [])
        self.assertEqual(checked, 1)

    def test_a_level_whose_track_is_another_color_is_reported(self):
        problems, _, _ = self._check((0xFF, 0x00, 0x00))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('#37394E', problems[0])

    def test_a_levels_bar_is_read_off_its_full_art(self):
        """Its filled part is gaugeFillColorField, drawn as its full asset; a
        clone kept the donor's scheme-1 #626ACF under a gold scheme."""
        vb = _vb(self)
        plan = [{'name': 'Home', 'controls': [
            {'fields': {'nameField': 'Volume'}, 'gauge_fill': 0xFFD6B961}]}]
        table = {'Home': {'ID': 51, 'Name': 'Home', 'Controls': [
            {'ID': 8, 'Type': 9, 'Name': 'Volume', 'TLPImageID': 36,
             'TLPMinValueImageID': 35, 'TLPMaxValueImageID': 36}]}}
        for bar, bad in (((0xD6, 0xB9, 0x61), False), (self.BAR, True)):
            problems, checked = vb.check_level_bars(plan, table, {35: _png(self.TRACK), 36: _png(bar)}, 'page')
            self.assertEqual(bool(problems), bad, problems)
            self.assertEqual(checked, 1)

    def test_a_level_drawn_from_art_shows_a_value(self):
        """A level whose donor draws it from art keeps that art (keep_art),
        and is planned no bar color to hold it to - but its empty and full art
        must both be built, and differ, or it shows no value."""
        vb = _vb(self)
        plan = [{'name': 'Home', 'controls': [
            {'fields': {'nameField': 'Volume'}, 'gauge_fill': None, 'keep_art': True}]}]
        table = {'Home': {'ID': 51, 'Name': 'Home', 'Controls': [
            {'ID': 8, 'Type': 9, 'Name': 'Volume', 'TLPImageID': 36,
             'TLPMinValueImageID': 35, 'TLPMaxValueImageID': 36}]}}
        for empty, full, bad in ((self.TRACK, self.BAR, False), (self.BAR, self.BAR, True)):
            problems, checked = vb.check_level_bars(plan, table, {35: _png(empty), 36: _png(full)}, 'page')
            self.assertEqual(bool(problems), bad, problems)
            self.assertEqual(checked, 1)
        problems, _ = vb.check_level_bars(plan, table, {35: _png(self.TRACK)}, 'page')
        self.assertTrue(problems)


class TestFontResourceReference(unittest.TestCase):
    """A control draws through a named font resource as well as a font name,
    and the applier wrote the name only: a label asked to be Arial Black kept its
    donor's resource with every field the verifier read correct. In every PBFont
    read, the reference is the name plus ' Regular Bold Italic'."""

    def _check(self, ref):
        vb = _vb(self)
        plan = [{'name': 'Home', 'controls': [
            {'fields': {'nameField': 'Title'}, 'font': {'name': 'Arial Black', 'size': 20}}]}]
        font = {'Name': 'Arial Black', 'PointSize': 20}
        if ref is not None:
            font['FontResourceReference'] = {'ResourceName': ref}
        table = {'Home': {'ID': 51, 'Name': 'Home', 'Controls': [
            {'ID': 3, 'Type': 11, 'Name': 'Title', 'Font': font}]}}
        return vb.check_fonts(plan, table, 'page')[0]

    def test_the_donors_resource_under_the_planned_name_is_reported(self):
        problems = self._check('Open Sans Regular Bold Italic')
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('Open Sans Regular Bold Italic', problems[0])

    def test_the_planned_resource_passes(self):
        self.assertEqual(self._check('Arial Black Regular Bold Italic'), [])

    def test_a_layout_without_the_reference_is_not_failed(self):
        self.assertEqual(self._check(None), [])


class TestPopupBackground(unittest.TestCase):
    """A popup's own page fill is artwork too. A Group's popup planned with
    no fill built as an opaque black box over its page on the 525, and no
    check read a popup's page asset."""

    def setUp(self):
        # Before the art: each test draws its popup with Pillow as it calls _check.
        _vb(self)

    def _check(self, art, modal=False, background=0x00000000):
        vb = _vb(self)
        plan = [{'name': 'Sources', 'modal': modal, 'background': background}]
        popups = {'Sources': {'Name': 'Sources', 'TLPImageID': 7}}
        return vb.check_popup_background(plan, popups, {7: art})

    def test_a_transparent_popup_built_opaque_is_reported(self):
        problems = self._check(_png((0, 0, 0)))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('Sources', problems[0])

    def test_a_transparent_popup_built_clear_passes(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGBA', (8, 8), (0, 0, 0, 0)).save(buf, 'PNG')
        self.assertEqual(self._check(buf.getvalue()), [])

    def test_a_modal_from_a_plan_without_its_transparency_is_not_checked(self):
        # Its scrim is the donor modal's, which such a plan does not say.
        self.assertEqual(self._check(_png((0, 0, 0)), modal=True), [])

    @staticmethod
    def _rgba(rgba):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGBA', (8, 8), rgba).save(buf, 'PNG')
        return buf.getvalue()

    def _modal(self, art):
        vb = _vb(self)
        plan = [{'name': 'Confirm', 'modal': True, 'background': 0xFF000000, 'transparency': 35.0}]
        return vb.check_popup_background(plan, {'Confirm': {'Name': 'Confirm', 'TLPImageID': 7}},
                                          {7: art})

    def test_a_modal_is_black_at_its_planned_transparency(self):
        """35% is alpha 166, as every template modal builds."""
        self.assertEqual(self._modal(self._rgba((0, 0, 0, 166))), [])

    def test_a_modal_built_opaque_is_reported(self):
        """A donor modal authored at 0 - the client's archived Incoming ones -
        builds opaque, and the page beneath is gone."""
        problems = self._modal(self._rgba((0, 0, 0, 255)))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('166', problems[0])

    def test_a_modal_in_another_color_is_reported(self):
        self.assertEqual(len(self._modal(self._rgba((36, 38, 52, 166)))), 1)

    def test_an_opaque_popup_must_be_its_color(self):
        self.assertEqual(self._check(_png((36, 38, 52)), background=0xFF242634), [])
        self.assertEqual(len(self._check(_png((200, 0, 0)), background=0xFF242634)), 1)

    def test_a_translucent_popup_must_be_its_color_and_alpha(self):
        # Turbulence's hub Volume Level strip: black at 166 over the page.
        # It has no opaque pixel, and read as built clear before it was read
        # at its own alpha.
        def art(rgba):
            import io
            from PIL import Image
            buf = io.BytesIO()
            Image.new('RGBA', (8, 8), rgba).save(buf, 'PNG')
            return buf.getvalue()
        self.assertEqual(self._check(art((0, 0, 0, 166)), background=0xA6000000), [])
        self.assertEqual(len(self._check(art((0, 0, 0, 0)), background=0xA6000000)), 1)
        self.assertEqual(len(self._check(art((0, 0, 0, 255)), background=0xA6000000)), 1)
        self.assertEqual(len(self._check(art((90, 0, 0, 166)), background=0xA6000000)), 1)


class TestBackgroundImage(unittest.TestCase):
    """layout.json does not name a page's background image, so the page's
    artwork is checked against the planned image over the planned fill."""

    def setUp(self):
        self.vb = _vb(self)
        import tempfile
        from PIL import Image
        self.dir = tempfile.mkdtemp()
        self.file = os.path.join(self.dir, 'card.png')
        card = Image.new('RGBA', (40, 20), (0, 0, 0, 0))
        card.paste((90, 80, 120, 255), (8, 4, 32, 16))
        card.save(self.file)
        want = Image.new('RGBA', (40, 20), (36, 38, 52, 255))
        want.alpha_composite(card)
        buf = __import__('io').BytesIO()
        want.convert('RGB').save(buf, 'PNG')
        self.good = buf.getvalue()

    def _check(self, art, file=True):
        plan = [{'name': 'Home', 'background': 0xFF242634,
                 'background_image': {'name': 'card.png', 'file': self.file if file else None}}]
        pages = {'Home': {'Name': 'Home', 'TLPImageID': 5}}
        return self.vb.check_page_background(plan, pages, {5: art})

    def test_the_planned_image_passes(self):
        self.assertEqual(self._check(self.good), [])

    def test_it_is_fitted_not_stretched(self):
        """The page lays its image out Fill: an image of another shape leaves
        bands of fill, and a stretched composite would call that wrong."""
        from PIL import Image
        wide = os.path.join(self.dir, 'wide.png')
        Image.new('RGBA', (80, 20), (90, 80, 120, 255)).save(wide)
        built = Image.new('RGBA', (40, 20), (36, 38, 52, 255))
        built.paste((90, 80, 120, 255), (0, 5, 40, 15))
        buf = __import__('io').BytesIO()
        built.convert('RGB').save(buf, 'PNG')
        plan = [{'name': 'Home', 'background': 0xFF242634,
                 'background_image': {'name': 'wide.png', 'file': wide}}]
        pages = {'Home': {'Name': 'Home', 'TLPImageID': 5}}
        self.assertEqual(self.vb.check_page_background(plan, pages, {5: buf.getvalue()}), [])

    def test_a_stretched_page_is_checked_stretched(self):
        """Mach's pages stretch their photo; checked as if fitted, a correctly
        built page reads as the wrong image."""
        from PIL import Image
        wide = os.path.join(self.dir, 'wide.png')
        src = Image.new('RGBA', (80, 20), (90, 80, 120, 255))
        src.paste((200, 20, 20, 255), (0, 0, 40, 20))
        src.save(wide)
        built = src.resize((40, 20)).convert('RGB')
        buf = __import__('io').BytesIO()
        built.save(buf, 'PNG')
        pages = {'Home': {'Name': 'Home', 'TLPImageID': 5}}
        for layout, bad in ((1, False), (0, True)):
            plan = [{'name': 'Home', 'background': 0xFF242634, 'background_layout': layout,
                     'background_image': {'name': 'wide.png', 'file': wide}}]
            problems = self.vb.check_page_background(plan, pages, {5: buf.getvalue()})
            self.assertEqual(bool(problems), bad, (layout, problems))

    def test_a_page_built_without_it_is_reported(self):
        # A page's artwork is page-sized, as the planned image is here.
        from PIL import Image
        buf = __import__('io').BytesIO()
        Image.new('RGB', (40, 20), (36, 38, 52)).save(buf, 'PNG')
        problems = self._check(buf.getvalue())
        self.assertTrue(any('not the planned image' in p for p in problems), problems)
        problems = self._check(_png((36, 38, 52)), file=False)
        self.assertTrue(any('single flat color' in p for p in problems), problems)


class TestPopupPhoto(unittest.TestCase):
    """A hub popup on the page's photo (Shockwave's and Turbulence's) is
    checked as a page's image is - and a popup planned with no fill of its
    own is not then taken for one built opaque."""

    def setUp(self):
        self.vb = _vb(self)
        import io
        import tempfile
        from PIL import Image
        self.file = os.path.join(tempfile.mkdtemp(), 'photo.png')
        src = Image.new('RGBA', (80, 20), (90, 80, 120, 255))
        src.paste((200, 20, 20, 255), (0, 0, 40, 20))
        src.save(self.file)
        buf = io.BytesIO()
        src.resize((40, 20)).convert('RGB').save(buf, 'PNG')
        self.good = buf.getvalue()

    def _check(self, art):
        plan = [{'name': 'Laptop', 'modal': False, 'background': 0x00000000, 'background_layout': 1,
                 'background_image': {'name': 'photo.png', 'file': self.file}}]
        return self.vb.check_popup_background(plan, {'Laptop': {'Name': 'Laptop', 'TLPImageID': 7}}, {7: art})

    def test_its_photo_stretched_passes(self):
        self.assertEqual(self._check(self.good), [])

    def test_one_built_without_it_is_reported(self):
        problems = self._check(_png((0, 0, 0)))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("popup 'Laptop'", problems[0])


class TestImageArt(unittest.TestCase):
    """layout.json names no image, so an image control's artwork is checked
    against its planned art laid out as planned: stretched (the Turbulence
    seeds' bars) or fitted (their device pictures)."""

    def setUp(self):
        self.vb = _vb(self)
        import tempfile
        from PIL import Image
        self.dir = tempfile.mkdtemp()
        self.bar = os.path.join(self.dir, 'bar.png')
        im = Image.new('RGBA', (80, 20), (20, 30, 120, 255))
        im.paste((200, 200, 200, 255), (0, 16, 80, 20))
        im.save(self.bar)
        self.other = os.path.join(self.dir, 'other.png')
        Image.new('RGBA', (80, 20), (200, 20, 20, 255)).save(self.other)

    def _art(self, file, layout):
        import io
        buf = io.BytesIO()
        (self.vb.stretch_image(file, 40, 20) if layout == 1 else self.vb.fit_image(file, 40, 20)).save(buf, 'PNG')
        return buf.getvalue()

    def _check(self, art, layout=1, file=None):
        plan = [{'name': 'Home', 'controls': [{
            'donor_type': 'PBImage', 'fields': {'nameField': 'Top bar'}, 'fill': None,
            'image': {'name': 'bar.png', 'file': file or self.bar}, 'image_layout': layout, 'image_align': 3}]}]
        table = {'Home': {'Name': 'Home', 'Controls': [
            {'Name': 'Top bar', 'Type': 10, 'Width': 40, 'Height': 20, 'TLPImageID': 7}]}}
        return self.vb.check_images(plan, table, {7: art} if art else {}, 'page')

    def test_its_art_as_planned_passes(self):
        self.assertEqual(self._check(self._art(self.bar, 1)), ([], 1))

    def test_the_state_check_leaves_an_image_to_its_own_layout(self):
        """check_states fits every planned image, as a button's icon lies; an
        image control's art is stretched where it is planned so, and is this
        check's. The Turbulence 1035's header, its seed's own art stretched,
        read there as 26% off - it is not that image."""
        import copy
        plan = [{'name': 'Home', 'controls': [{
            'donor_type': 'PBImage', 'fields': {'nameField': 'Top bar'}, 'fill': None,
            'image': {'name': 'bar.png', 'file': self.bar}, 'image_layout': 1, 'image_align': 3}]}]
        table = {'Home': {'Name': 'Home', 'Controls': [
            {'Name': 'Top bar', 'Type': 10, 'Width': 40, 'Height': 20, 'TLPImageID': 7,
             'States': [{'Name': 'Top bar', 'TLPImageID': 7}]}]}}
        assets = {7: self._art(self.bar, 1)}
        problems, _, _ = self.vb.check_states(copy.deepcopy(plan), table, assets, 'page')
        self.assertEqual(problems, [])

    def test_another_image_is_reported(self):
        problems, _ = self._check(self._art(self.other, 1))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("'Top bar'", problems[0])

    def test_it_is_held_to_its_own_layout(self):
        problems, _ = self._check(self._art(self.bar, 1), layout=0)
        self.assertEqual(len(problems), 1, problems)

    def test_one_built_with_no_artwork_is_reported(self):
        problems, _ = self._check(None)
        self.assertTrue(any('no artwork' in p for p in problems), problems)

    def test_a_file_this_machine_lacks_is_reported(self):
        problems, _ = self._check(self._art(self.bar, 1), file=os.path.join(self.dir, 'gone.png'))
        self.assertTrue(any('not at' in p for p in problems), problems)


class TestImageArtOnTheSeed(unittest.TestCase):
    """The check on Build's own artwork: the Turbulence 1035 seed's header
    and footer bars and its device pictures against the art extracted from
    it (vendor/README.md) - each its own file, laid out as the seed lays it,
    0% off, and another's 10% and up."""
    SEED = os.path.join(os.path.dirname(HERE), 'seeds', 'Turbulence 1035.gdl')
    ART = {'Top bar': ('2047x151_header.png', 1), 'Bottom bar': ('1648x134_footer.png', 1),
           'Laptop Image': ('1152x1152_laptop.png', 0), 'PC Image': ('1152x1152_pc.png', 0)}

    def test_each_is_its_own_art_and_not_another(self):
        vb = _vb(self)
        from gdl.spec import resolve_image
        if not usable(self.SEED):
            self.skipTest('seeds/Turbulence 1035.gdl is not here (git lfs pull)')
        files = {n: resolve_image('Turbulence/' + f) for n, (f, _) in self.ART.items()}
        if not all(files.values()):
            self.skipTest("Turbulence's art is not extracted here (python -m gdl.designsys extract turbulence)")
        from gdl.compose import load
        layout, assets = load(self.SEED)
        built = {}
        for pg in layout['Pages'] + layout['PopupPages']:
            for c in pg.get('Controls') or []:
                built.setdefault(c.get('Name'), (pg['Name'], c))
        swap = {'Laptop Image': 'PC Image', 'PC Image': 'Laptop Image', 'Top bar': 'Laptop Image',
                'Bottom bar': 'PC Image'}
        for name, (f, layout_) in self.ART.items():
            page, c = built[name]
            table = {page: {'Name': page, 'Controls': [c]}}
            for art, bad in ((name, False), (swap[name], True)):
                plan = [{'name': page, 'controls': [{
                    'donor_type': 'PBImage', 'fields': {'nameField': name}, 'fill': None,
                    'image': {'name': self.ART[art][0], 'file': files[art]}, 'image_layout': layout_}]}]
                problems, _ = vb.check_images(plan, table, assets, 'page')
                self.assertEqual(bool(problems), bad, (name, art, problems))


class TestStateImage(unittest.TestCase):
    """layout.json names no image once built, so a state's kit image is
    checked against its artwork."""

    def setUp(self):
        self.vb = _vb(self)
        import io
        import tempfile
        from PIL import Image, ImageDraw
        self.dir = tempfile.mkdtemp()
        self.files = {}
        # A 'speaker' and the same with a wave - the subset case.
        for name, wave in (('one.png', False), ('two.png', True)):
            im = Image.new('RGBA', (440, 440), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rectangle((60, 150, 200, 290), fill=(186, 188, 206, 255))
            if wave:
                d.rectangle((260, 80, 380, 360), fill=(98, 106, 207, 255))
            self.files[name] = os.path.join(self.dir, name)
            im.save(self.files[name])
        self.art = {}
        for name, f in self.files.items():
            buf = io.BytesIO()
            self.vb.fit_image(f, 64, 64).save(buf, 'PNG')
            self.art[name] = buf.getvalue()

    def _check(self, planned, built):
        c = {'Width': 64, 'Height': 64}
        bs = {'Name': 'On', 'TLPImageID': 7}
        img = {'name': planned, 'file': self.files[planned]}
        return self.vb._state_image('page Home Mute', 1, bs, c, img, None,
                                    {7: self.art[built]} if built else {})

    def test_a_near_twin_built_in_its_place_is_caught_by_the_other_states(self):
        """Two volume levels a step apart differ by one thin wave - a few per
        cent of the inked pixels at 64 px, under what one image is allowed
        alone. Against the button's other states' images it is caught: the
        artwork is nearer another state's image than its own."""
        import io
        from PIL import Image, ImageDraw
        files = {}
        for name, waves in (('vol2.png', 2), ('vol3.png', 3)):
            im = Image.new('RGBA', (440, 440), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rectangle((60, 150, 200, 290), fill=(186, 188, 206, 255))
            for k in range(waves):
                x = 230 + k * 60
                d.rectangle((x, 150 - k * 30, x + 16, 290 + k * 30), fill=(186, 188, 206, 255))
            files[name] = os.path.join(self.dir, name)
            im.save(files[name])

        def art(name):
            buf = io.BytesIO()
            self.vb.fit_image(files[name], 64, 64).save(buf, 'PNG')
            return buf.getvalue()

        c = {'Width': 64, 'Height': 64}
        bs = {'Name': 'Level 2', 'TLPImageID': 7}
        own = {'name': 'vol2.png', 'file': files['vol2.png']}
        other = {'name': 'vol3.png', 'file': files['vol3.png']}
        swapped = {7: art('vol3.png')}
        self.assertEqual(self.vb._state_image('page Audio Vol', 2, bs, c, own, None, swapped), [],
                         'the case this is for: alone, the near twin passes')
        problems = self.vb._state_image('page Audio Vol', 2, bs, c, own, None, swapped, [other])
        self.assertTrue(any("nearer 'vol3.png'" in p for p in problems), problems)
        self.assertEqual(self.vb._state_image('page Audio Vol', 2, bs, c, own, None,
                                              {7: art('vol2.png')}, [other]), [])

    def test_the_nearest_of_the_other_states_is_the_one_named(self):
        """Level 2 built where level 3 was planned: level 1 is nearer than the
        planned image too, and comes first, but level 2 is the one there."""
        import io
        from PIL import Image, ImageDraw
        files = {}
        for waves in (1, 2, 3):
            im = Image.new('RGBA', (440, 440), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rectangle((60, 150, 200, 290), fill=(186, 188, 206, 255))
            for k in range(waves):
                x = 230 + k * 60
                d.rectangle((x, 150 - k * 30, x + 16, 290 + k * 30), fill=(186, 188, 206, 255))
            files[waves] = os.path.join(self.dir, f'vol{waves}.png')
            im.save(files[waves])
        buf = io.BytesIO()
        self.vb.fit_image(files[2], 64, 64).save(buf, 'PNG')
        c = {'Width': 64, 'Height': 64}
        bs = {'Name': 'Level 3', 'TLPImageID': 7}
        img = {w: {'name': f'vol{w}.png', 'file': f} for w, f in files.items()}
        off = {w: self.vb.image_mismatch(f, buf.getvalue(), 64, 64, None) for w, f in files.items()}
        self.assertLess(off[1], off[3], 'the case: the first sibling is nearer than the plan too')
        problems = self.vb._state_image('page Audio Vol', 3, bs, c, img[3], None,
                                        {7: buf.getvalue()}, [img[1], img[2]])
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("nearer 'vol2.png' (0% differs)", problems[0])

    def test_the_planned_image_passes(self):
        self.assertEqual(self._check('two.png', 'two.png'), [])

    def test_another_image_is_reported_both_ways(self):
        for planned, built in (('two.png', 'one.png'), ('one.png', 'two.png')):
            problems = self._check(planned, built)
            self.assertTrue(any('not that image' in p for p in problems), problems)

    def test_a_planned_file_this_machine_lacks_is_a_problem(self):
        """A plan carries its kit files' absolute paths. Verified elsewhere, or
        after vendor/ moved, every image comparison was skipped and the control
        still counted as verified - Mach's black-block rail passed so."""
        gone = {'name': 'two.png', 'file': os.path.join(self.dir, 'moved', 'two.png')}
        bs = {'Name': 'On', 'TLPImageID': 7}
        problems = self.vb._state_image('page Home Mute', 1, bs, {'Width': 64, 'Height': 64},
                                        gone, None, {7: self.art['two.png']})
        self.assertTrue(any('not at' in p and 'on this machine' in p for p in problems),
                        problems)
        table = {'Home': {'Name': 'Home', 'Controls': [
            {'ID': 1, 'Name': 'Volume', 'Width': 60, 'Height': 391, 'Orientation': 2,
             'SliderIndicatorImageID': 7, 'TLPMinValueImageID': 7, 'TLPMaxValueImageID': 7}]}}
        op = {'fields': {'nameField': 'Volume'}, 'thumb_image': gone,
              'track_image': gone, 'fill_image': gone}
        for fn in (self.vb.check_thumbs, self.vb.check_rails):
            problems, _ = fn([{'name': 'Home', 'controls': [op]}], table,
                             {7: self.art['two.png']}, 'page')
            self.assertTrue(problems and all('on this machine' in p for p in problems),
                            (fn.__name__, problems))

    def test_a_state_with_no_artwork_is_reported(self):
        problems = self._check('one.png', None)
        self.assertTrue(any('no artwork' in p for p in problems), problems)

    def test_a_control_with_no_states_is_checked_off_its_own_artwork(self):
        op = {'fields': {'nameField': 'Deco'},
              'image': {'name': 'two.png', 'file': self.files['two.png']}}
        table = {'Home': {'Name': 'Home', 'Controls': [
            {'ID': 1, 'Name': 'Deco', 'Width': 64, 'Height': 64, 'TLPImageID': -1,
             'States': []}]}}
        problems, _, n = self.vb.check_states([{'name': 'Home', 'controls': [op]}], table,
                                              {}, 'page')
        self.assertEqual(n, 1)
        self.assertTrue(any('no artwork' in p for p in problems), problems)

    def test_an_icon_past_the_gate_passes_as_the_nearest_of_its_family(self):
        """Mach's 1376x440 tab art fitted into the 725's 152x60 tab comes out
        21 to 25% off its own file at that scale - ShareLink's 25.1%, past the
        gate measured on Afterburn's 64 px icons - and 38% and up off every
        other icon of its family. Past the gate, the planned file nearer than
        any other of its folder's same-size files by a clear margin is the
        image there; the artwork nearer another, or no family to hold it
        against, is not."""
        import io
        import tempfile
        from PIL import Image, ImageDraw
        d = tempfile.mkdtemp()

        def icon(name, draw):
            im = Image.new('RGBA', (80, 40), (0, 0, 0, 0))
            draw(ImageDraw.Draw(im))
            path = os.path.join(d, name)
            im.save(path)
            return {'name': name, 'file': path}

        own = icon('80x40_share.png', lambda g: g.rectangle((10, 8, 30, 30), outline=(255, 255, 255, 255), width=2))
        other = icon('80x40_disc.png', lambda g: g.ellipse((44, 6, 70, 34), outline=(255, 255, 255, 255), width=2))
        icon('80x40_tv.png', lambda g: g.line((5, 35, 75, 35), fill=(255, 255, 255, 255), width=3))
        c = {'Width': 80, 'Height': 40}
        bs = {'Name': 'Off', 'TLPImageID': 7}

        def art(im):
            buf = io.BytesIO()
            im.save(buf, 'PNG')
            return {7: buf.getvalue()}
        # Its own art with a stroke lost, as a thin line downscaled ninefold
        # loses one: past the gate, nearest its own file by far.
        drift = Image.open(own['file']).copy()
        ImageDraw.Draw(drift).rectangle((6, 6, 34, 11), fill=(0, 0, 0, 0))
        ImageDraw.Draw(drift).rectangle((6, 6, 13, 12), fill=(0, 0, 0, 0))
        off = self.vb.image_mismatch(own['file'], art(drift)[7], 80, 40)
        self.assertTrue(self.vb.IMAGE_OFF < off <= self.vb.IMAGE_FAMILY_OFF, off)
        self.assertEqual(self.vb._state_image('page Home Share', 0, bs, c, own, None, art(drift)), [])
        # Another of its family's art: refused.
        swapped = Image.open(other['file'])
        self.assertTrue(self.vb._state_image('page Home Share', 0, bs, c, own, None, art(swapped)))
        # No family beside it: the gate alone decides.
        lone = icon('lone.png', lambda g: g.rectangle((10, 8, 30, 30), outline=(255, 255, 255, 255), width=2))
        os.makedirs(os.path.join(d, 'alone'))
        os.replace(lone['file'], os.path.join(d, 'alone', 'lone.png'))
        lone['file'] = os.path.join(d, 'alone', 'lone.png')
        self.assertTrue(self.vb._state_image('page Home Share', 0, bs, c, lone, None, art(drift)))

    def test_a_translucent_fill_is_checked_at_its_own_alpha(self):
        """Build writes a translucent fill's alpha exactly and its color to
        within premultiplying's rounding - Turbulence's shade, #020D1A at 128,
        built as (1, 13, 25, 128), and its rail, black at 38, as (0, 0, 0, 38).
        Read off the opaque pixels alone, it has none, and nothing was checked."""
        import io
        from PIL import Image

        def art(rgba):
            buf = io.BytesIO()
            Image.new('RGBA', (8, 8), rgba).save(buf, 'PNG')
            return buf.getvalue()

        table = {'Home': {'Name': 'Home', 'Controls': [
            {'ID': 1, 'Name': 'Card', 'TLPImageID': 7}]}}
        for fill, built, bad in ((0x80020D1A, (1, 13, 25, 128), False),
                                 (0x26000000, (0, 0, 0, 38), False),
                                 (0x80020D1A, (1, 13, 25, 255), True),       # alpha lost
                                 (0x80020D1A, (255, 255, 255, 128), True),   # the donor's
                                 (0x26000000, (0, 0, 0, 128), True),         # another alpha
                                 # Mach's Make Call, #659945 at 220, bare: two of
                                 # Build's round trips, 2 off.
                                 (0xDC659945, (99, 151, 69, 220), False)):
            op = {'fields': {'nameField': 'Card'}, 'fill': fill}
            problems, notes, n = self.vb.check_fills([{'name': 'Home', 'controls': [op]}],
                                                     table, {7: art(built)}, 'page')
            self.assertEqual(n, 1, (hex(fill), built))
            self.assertEqual(bool(problems), bad, (hex(fill), built, problems))
            self.assertFalse(any('not checked' in x for x in notes), notes)

    @staticmethod
    def _make_call(under, edge=(99, 151, 69, 220)):
        """Mach's Make Call Off as Build drew it on the 1035, 103 x 60: its
        fill #659945 at 220 built `under` inside the 755x440 call icon's
        fitted rect, `edge` in the last column and row past it, and the
        glyph's 75 white pixels."""
        import io
        from PIL import Image
        im = Image.new('RGBA', (103, 60), edge)
        im.paste(under, (0, 0, 102, 59))
        im.paste((255, 255, 255, 255), (44, 9, 49, 24))
        buf = io.BytesIO()
        im.save(buf, 'PNG')
        return buf.getvalue()

    def test_a_translucent_fill_under_an_image_takes_one_more_rounding(self):
        """Build draws an image over a translucent fill with one more round
        trip through premultiplied form, inside the image's rect: Mach's Make
        Call under its call icon built (98, 150, 69) where its bare key builds
        (99, 151, 69), and failed a tolerance of one rounding on the 1035, 725
        and 525. The Mach 1035 seed's own Initiate Call is the same bytes
        (TestTranslucentFillUnderAnImageOnTheSeed)."""
        table = {'Call': {'Name': 'Call', 'Controls': [
            {'ID': 1, 'Name': 'Make Call', 'Type': 7, 'Width': 103, 'Height': 60,
             'TLPImageID': 7, 'States': [{'Name': 'Off', 'TLPImageID': 7},
                                         {'Name': 'On', 'TLPImageID': 8}]}]}}
        # No file: the image comparison is _state_image's, tested on its own.
        icon = {'name': '755x440_call.png'}
        on = self._make_call((134, 209, 97, 255), (134, 209, 97, 255))

        def check(under, image):
            op = {'fields': {'nameField': 'Make Call'}, 'fill': 0xDC659945, 'image': image,
                  'states': [{'name': 'Off', 'fill': 0xDC659945, 'image': image},
                             {'name': 'On', 'fill': 0xFF86D161, 'image': image}]}
            plan = [{'name': 'Call', 'controls': [op]}]
            assets = {7: self._make_call(under), 8: on}
            fills, _, n = self.vb.check_fills(plan, table, assets, 'page')
            states, _, m = self.vb.check_states(plan, table, assets, 'page')
            self.assertEqual((n, m), (1, 2))
            return fills + states

        self.assertEqual(check((98, 150, 69, 220), icon), [])
        # Bare, the third round trip has nothing to come from.
        self.assertEqual(len(check((98, 150, 69, 220), None)), 2)
        # Under the icon, one further is another color, and the donor's is.
        for under in ((97, 149, 69, 220), (255, 255, 255, 220), (98, 150, 69, 255)):
            self.assertEqual(len(check(under, icon)), 2, under)

    def test_the_fill_tolerance_holds_every_color_builds_round_trips_leave(self):
        """The model _fill_tolerance() documents, measured off every
        translucent fill in Mach's call builds and seeds: rounding in,
        truncating out through a 16.16 reciprocal, twice bare and three times
        under an image. Every channel at every alpha stays within it, and
        the third pass is what needs the one more."""
        def trip(c, a, n):
            for _ in range(n):
                c = min(255, ((c * a + 127) // 255) * ((255 << 16) // a) >> 16)
            return c
        self.assertEqual([trip(c, 220, 2) for c in (0x65, 0x99, 0x45)], [99, 151, 69])
        self.assertEqual([trip(c, 220, 3) for c in (0x65, 0x99, 0x45)], [98, 150, 69])
        past_one = 0
        for a in range(1, 255):
            for c in range(256):
                self.assertLessEqual(abs(trip(c, a, 2) - c), self.vb._fill_tolerance(a), (a, c))
                self.assertLessEqual(abs(trip(c, a, 3) - c), self.vb._fill_tolerance(a, True),
                                     (a, c))
                past_one += abs(trip(c, a, 3) - c) > self.vb._fill_tolerance(a)
        self.assertTrue(past_one)

    def test_a_label_planned_clear_built_on_a_fill_is_reported(self):
        """Turbulence 320's empty state: labels planned with no fill built on
        their donor label's opaque black, bands across the photo - and no
        check read a clear label's artwork. Its words alone are fine."""
        import io
        from PIL import Image

        def art(band):
            im = Image.new('RGBA', (40, 10), (0, 0, 0, 255) if band else (0, 0, 0, 0))
            im.paste((255, 255, 255, 255), (10, 3, 30, 7))      # the words
            buf = io.BytesIO()
            im.save(buf, 'PNG')
            return buf.getvalue()

        table = {'Laptop': {'Name': 'Laptop', 'Controls': [
            {'ID': 1, 'Name': 'Laptop Empty', 'Type': 11, 'TLPImageID': 7}]}}
        op = {'op': 'clone-control', 'donor_type': 'PBLabel',
              'fields': {'nameField': 'Laptop Empty'}, 'fill': 0}
        for band, bad in ((True, True), (False, False)):
            problems, _, _ = self.vb.check_fills([{'name': 'Laptop', 'controls': [op]}],
                                                 table, {7: art(band)}, 'page')
            self.assertEqual(bool(problems), bad, (band, problems))

    def test_a_shape_line_or_clock_planned_clear_built_on_a_fill_is_reported(self):
        """A panel planned with no fill kept its donor shape's opaque slab,
        and only a clear label's artwork was read."""
        import io
        from PIL import Image

        def art(slab):
            im = Image.new('RGBA', (40, 10), (55, 57, 78, 255) if slab else (0, 0, 0, 0))
            buf = io.BytesIO()
            im.save(buf, 'PNG')
            return buf.getvalue()

        for donor, typ in (('PBShape', 13), ('PBLine', 12), ('PBDateTime', 8)):
            table = {'Home': {'Name': 'Home', 'Controls': [
                {'ID': 1, 'Name': 'Ghost', 'Type': typ, 'TLPImageID': 7}]}}
            op = {'op': 'clone-control', 'donor_type': donor,
                  'fields': {'nameField': 'Ghost'}, 'fill': 0}
            for slab, bad in ((True, True), (False, False)):
                with self.subTest(donor=donor, slab=slab):
                    problems, _, _ = self.vb.check_fills([{'name': 'Home', 'controls': [op]}],
                                                         table, {7: art(slab)}, 'page')
                    self.assertEqual(bool(problems), bad, problems)
                    if bad:
                        self.assertIn('#37394E', problems[0])

    def test_a_small_clear_shape_with_its_own_outline_is_not_a_slab(self):
        """A 20 x 20 panel with a 5 px outline is 75% opaque and has no fill:
        the outline is most of its artwork. A donor's slab fills the middle."""
        import io
        from PIL import Image

        def art(slab):
            im = Image.new('RGBA', (20, 20), (110, 110, 140, 255))
            if not slab:
                im.paste((0, 0, 0, 0), (5, 5, 15, 15))
            buf = io.BytesIO()
            im.save(buf, 'PNG')
            return buf.getvalue()

        table = {'Home': {'Name': 'Home', 'Controls': [
            {'ID': 1, 'Name': 'Ring', 'Type': 13, 'TLPImageID': 7}]}}
        op = {'op': 'clone-control', 'donor_type': 'PBShape',
              'fields': {'nameField': 'Ring'}, 'fill': 0, 'stroke': 0xFF6E6E8C,
              'border': '2D Rounded Rectangle'}
        for slab, bad in ((False, False), (True, True)):
            problems, _, _ = self.vb.check_fills([{'name': 'Home', 'controls': [op]}],
                                                 table, {7: art(slab)}, 'page')
            self.assertEqual(bool(problems), bad, (slab, problems))

    def test_an_opaque_fill_built_translucent_says_so(self):
        """Not 'missing or fully transparent' - the panel draws it, see-through."""
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGBA', (8, 8), (1, 13, 25, 128)).save(buf, 'PNG')
        op = {'fields': {'nameField': 'Card'}, 'fill': 0xFF020D1A}
        table = {'Home': {'Name': 'Home', 'Controls': [
            {'ID': 1, 'Name': 'Card', 'TLPImageID': 7}]}}
        problems, _, _ = self.vb.check_fills([{'name': 'Home', 'controls': [op]}], table,
                                             {7: buf.getvalue()}, 'page')
        self.assertTrue(any('no opaque pixel' in p for p in problems), problems)

    def test_a_translucent_state_fill_is_checked_at_its_own_alpha(self):
        """Mach's tiles: black at 70% idle. A state that came back opaque, or
        at another alpha, is not the state planned."""
        import io
        from PIL import Image
        art = {}
        for i, rgba in ((1, (0, 0, 0, 180)), (2, (31, 41, 46, 160)), (3, (31, 41, 46, 255))):
            buf = io.BytesIO()
            Image.new('RGBA', (8, 8), rgba).save(buf, 'PNG')
            art[i] = buf.getvalue()
        op = {'fields': {'nameField': 'Tile'}, 'states': [
            {'name': 'Off', 'fill': 0xB4000000}, {'name': 'On', 'fill': 0xA01F292E}]}
        for on, bad in ((2, False), (3, True)):
            table = {'Home': {'Name': 'Home', 'Controls': [
                {'ID': 1, 'Name': 'Tile', 'States': [
                    {'Name': 'Off', 'TLPImageID': 1}, {'Name': 'On', 'TLPImageID': on}]}]}}
            problems, _, _ = self.vb.check_states([{'name': 'Home', 'controls': [op]}], table,
                                                  art, 'page')
            self.assertEqual(any("state On: planned fill #1F292E at alpha 160" in p
                                 for p in problems), bad, problems)

    def test_a_fill_under_an_opaque_image_is_not_asked_for(self):
        """Shockwave's Teams tab: lit, the kit's 744x456_microsoft-teams_sel is
        an opaque light tile over the whole button, so the On state's planned
        fill, white at 60, cannot show - the image is the state's look, and
        its own check holds it. An icon over a fill that went missing is
        still a problem."""
        import io
        import tempfile
        from PIL import Image, ImageDraw
        d = tempfile.mkdtemp()
        tile = os.path.join(d, '80x40_teams_sel.png')
        im = Image.new('RGBA', (80, 40), (207, 207, 207, 255))
        ImageDraw.Draw(im).rectangle((30, 10, 50, 30), fill=(80, 80, 80, 255))
        im.save(tile)
        glyph = os.path.join(d, '80x40_teams_white.png')
        g = Image.new('RGBA', (80, 40), (0, 0, 0, 0))
        ImageDraw.Draw(g).rectangle((30, 10, 50, 30), fill=(255, 255, 255, 255))
        g.save(glyph)

        def png(img):
            buf = io.BytesIO()
            img.save(buf, 'PNG')
            return buf.getvalue()
        art = {1: png(Image.new('RGBA', (80, 40), (59, 47, 42, 255))), 2: png(Image.open(tile)),
               3: png(Image.open(glyph))}
        for on_image, built, bad in ((tile, 2, False), (glyph, 3, True)):
            op = {'fields': {'nameField': 'Teams'}, 'states': [
                {'name': 'Off', 'fill': 0xFF3B2F2A},
                {'name': 'On', 'fill': 0x3CFFFFFF,
                 'image': {'name': os.path.basename(on_image), 'file': on_image}}]}
            table = {'Home': {'Name': 'Home', 'Controls': [
                {'ID': 1, 'Name': 'Teams', 'Width': 80, 'Height': 40, 'States': [
                    {'Name': 'Off', 'TLPImageID': 1}, {'Name': 'On', 'TLPImageID': built}]}]}}
            problems, _, _ = self.vb.check_states([{'name': 'Home', 'controls': [op]}], table,
                                                  art, 'page')
            self.assertEqual(any('planned fill #FFFFFF at alpha 60' in p for p in problems), bad,
                             (os.path.basename(on_image), problems))

    def test_states_in_translucent_fills_are_not_called_alike(self):
        """Mach's buttons: black at 70% idle, a dark gray at 63% pressed. Their
        artwork has no opaque pixel, so every state's plurality color is none -
        which read as 'all built the same', then crashed naming it."""
        import io
        from PIL import Image
        art = {}
        for i, rgba in ((1, (0, 0, 0, 180)), (2, (31, 41, 46, 160))):
            buf = io.BytesIO()
            Image.new('RGBA', (8, 8), rgba).save(buf, 'PNG')
            art[i] = buf.getvalue()
        op = {'fields': {'nameField': 'Tile'}, 'states': [
            {'name': 'Off', 'fill': 0xB4000000}, {'name': 'On', 'fill': 0xA01F292E}]}
        table = {'Home': {'Name': 'Home', 'Controls': [
            {'ID': 1, 'Name': 'Tile', 'States': [
                {'Name': 'Off', 'TLPImageID': 1}, {'Name': 'On', 'TLPImageID': 2}]}]}}
        problems, _, _ = self.vb.check_states([{'name': 'Home', 'controls': [op]}], table, art,
                                              'page')
        self.assertEqual(problems, [])

    def test_a_slider_thumb_is_checked_off_its_own_asset(self):
        """A clone keeps its donor's thumb image: the seed's periwinkle under
        a scheme that asked for gold."""
        op = {'fields': {'nameField': 'Volume'},
              'thumb_image': {'name': 'two.png', 'file': self.files['two.png']}}
        for built, bad in (('two.png', False), ('one.png', True)):
            table = {'Home': {'Name': 'Home', 'Controls': [
                {'ID': 1, 'Name': 'Volume', 'SliderIndicatorImageID': 7}]}}
            problems, n = self.vb.check_thumbs([{'name': 'Home', 'controls': [op]}], table,
                                               {7: self.art[built]}, 'page')
            self.assertEqual((n, bool(problems)), (1, bad), problems)

    def test_a_slider_rail_is_checked_off_its_own_assets(self):
        """A slider's rail is art in the image-drawn templates - its track when
        empty, its fill when full - and Build draws them as the empty and full
        assets. The applier cleared a clone's track, and Shockwave's slider
        built an opaque black block where its seed's own draw the rail."""
        import io
        from PIL import Image, ImageDraw
        files = {}
        for name, bar in (('track.png', (56, 56, 56, 255)), ('fill.png', (255, 255, 255, 255))):
            # Turbulence's: bars 10 px on, 5 off - a rail drawn the wrong
            # length puts every stripe somewhere else.
            im = Image.new('RGBA', (52, 535), (0, 0, 0, 0))
            for y in range(0, 535, 15):
                ImageDraw.Draw(im).rectangle((14, y, 38, y + 9), fill=bar)
            files[name] = os.path.join(self.dir, name)
            im.save(files[name])

        def art(im):
            buf = io.BytesIO()
            im.save(buf, 'PNG')
            return buf.getvalue()

        # Build draws a rail the track's width across and the slider's length
        # less the thumb along, centered - see rail_image.
        right = {1: art(self.vb.rail_image(files['track.png'], 60, 391, 24, 52, 2)),
                 2: art(self.vb.rail_image(files['fill.png'], 60, 391, 24, 52, 2))}
        wide = {1: art(self.vb.stretch_image(files['track.png'], 60, 391)), 2: right[2]}
        long = {1: art(self.vb.rail_image(files['track.png'], 60, 391, 24, 0, 2)), 2: right[2]}
        black = {1: art(Image.new('RGBA', (60, 391), (0, 0, 0, 255))), 2: right[2]}
        op = {'fields': {'nameField': 'Volume'},
              'track_image': {'name': 'track.png', 'file': files['track.png']},
              'fill_image': {'name': 'fill.png', 'file': files['fill.png']}}
        table = {'Home': {'Name': 'Home', 'Controls': [
            {'ID': 1, 'Name': 'Volume', 'Width': 60, 'Height': 391, 'SliderTrackWidth': 24,
             'SliderIndicatorWidth': 52, 'SliderIndicatorHeight': 52, 'Orientation': 2,
             'TLPMinValueImageID': 1, 'TLPMaxValueImageID': 2}]}}
        for assets, bad in ((right, False), (wide, True), (long, True), (black, True)):
            problems, n = self.vb.check_rails([{'name': 'Home', 'controls': [op]}], table,
                                              assets, 'page')
            self.assertEqual((n, bool(problems)), (2, bad), problems)
        self.assertIn('track', problems[0])

    def test_a_sliders_full_art_is_its_fill_over_its_track(self):
        """Build draws a slider's full asset as its fill over its track, and
        each at SliderTrackWidth even where that is wider than the control -
        centred, and cut to it. So drawn, every seed slider of the three
        image-drawn themes is 0% off; the fill alone left Shockwave's 6 to 9%,
        its track's rim showing round its narrower fill, and the Shockwave 720's - a
        47 px slider given the 1035's 52 px track - 25%, failing a panel that
        was right. The built art here is drawn by hand."""
        import io
        from PIL import Image, ImageDraw
        dark, light = (26, 25, 25, 160), (230, 230, 230, 255)
        files = {}
        for name, (x0, x1), color in (('track.png', (20, 79), dark), ('fill.png', (30, 69), light)):
            im = Image.new('RGBA', (100, 600), (0, 0, 0, 0))
            ImageDraw.Draw(im).rectangle((x0, 0, x1, 599), fill=color)
            files[name] = os.path.join(self.dir, name)
            im.save(files[name])

        def art(w, h, *bars):
            im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            for x0, x1, color in bars:
                layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
                ImageDraw.Draw(layer).rectangle((x0, 0, x1, h - 1), fill=color)
                im.alpha_composite(layer)
            buf = io.BytesIO()
            im.save(buf, 'PNG')
            return buf.getvalue()

        op = {'fields': {'nameField': 'Volume'},
              'track_image': {'name': 'track.png', 'file': files['track.png']},
              'fill_image': {'name': 'fill.png', 'file': files['fill.png']}}

        def check(w, track, assets):
            table = {'Home': {'Name': 'Home', 'Controls': [
                {'ID': 1, 'Name': 'Volume', 'Width': w, 'Height': 300, 'SliderTrackWidth': track,
                 'SliderIndicatorWidth': w, 'SliderIndicatorHeight': 0, 'Orientation': 2,
                 'TLPMinValueImageID': 1, 'TLPMaxValueImageID': 2}]}}
            return self.vb.check_rails([{'name': 'Home', 'controls': [op]}], table, assets, 'page')[0]

        # A 60 px control, its track 60: the track's bar is x 12-47, the fill's 18-41.
        full = art(60, 300, (12, 47, dark), (18, 41, light))
        self.assertEqual(check(60, 60, {1: art(60, 300, (12, 47, dark)), 2: full}), [])
        self.assertTrue(check(60, 60, {1: art(60, 300, (12, 47, dark)), 2: art(60, 300, (18, 41, light))}))
        # A 30 px control given a 60 px track: Build draws the track 60 wide,
        # its bar the control's whole 30 - not 15, as a track cut to 30 would.
        whole = art(30, 300, (0, 29, dark), (3, 26, light))
        self.assertEqual(check(30, 60, {1: art(30, 300, (0, 29, dark)), 2: whole}), [])
        self.assertTrue(check(30, 60, {1: art(30, 300, (7, 22, dark)), 2: whole}))

    def test_two_icons_on_one_ground_are_not_called_alike(self):
        """Afterburn's mute: both speaker icons are mostly their #414459
        ground, so their artwork has one plurality color and still differs."""
        import io
        from PIL import Image, ImageDraw
        files, art = {}, {}
        for i, (name, mark) in enumerate((('a.png', (20, 20, 40, 40)),
                                          ('b.png', (60, 60, 80, 80))), 1):
            im = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rectangle((0, 0, 99, 99), fill=(65, 68, 89, 255))
            d.rectangle(mark, fill=(186, 188, 206, 255))
            files[name] = os.path.join(self.dir, name)
            im.save(files[name])
            buf = io.BytesIO()
            self.vb.fit_image(files[name], 64, 64).save(buf, 'PNG')
            art[i] = buf.getvalue()
        op = {'fields': {'nameField': 'Mute'}, 'states': [
            {'name': 'Unmuted', 'fill': 0, 'image': {'name': 'a.png', 'file': files['a.png']}},
            {'name': 'Muted', 'fill': 0, 'image': {'name': 'b.png', 'file': files['b.png']}}]}
        table = {'Home': {'Name': 'Home', 'Controls': [
            {'ID': 1, 'Name': 'Mute', 'Width': 64, 'Height': 64, 'States': [
                {'Name': 'Unmuted', 'TLPImageID': 1}, {'Name': 'Muted', 'TLPImageID': 2}]}]}}
        problems, _, _ = self.vb.check_states([{'name': 'Home', 'controls': [op]}], table, art,
                                              'page')
        self.assertEqual(problems, [])


class TestStateImageOnTheSeed(unittest.TestCase):
    """The near-twin margin on real Build artwork: the Afterburn seed's 'Main
    Volume Mute' on Audio Settings, a mute image and volume levels a wave
    apart, against Extron's own kit files. A level built with the level
    before's art passes the image gate alone; held against the button's other
    states it is caught, and the one it is named as is the one there."""
    SEED = os.path.join(os.path.dirname(HERE), 'seeds', 'Afterburn 1035.gdl')

    def setUp(self):
        self.vb = _vb(self)
        import glob
        from gdl.spec import RESOURCE_ROOTS
        if not usable(self.SEED):
            self.skipTest('seeds/Afterburn 1035.gdl is not here (git lfs pull)')
        kit = {}
        for root in RESOURCE_ROOTS:
            for f in glob.glob(os.path.join(root, 'Afterburn', '**', '*.png'), recursive=True):
                kit.setdefault(os.path.basename(f), f)
        from gdl.compose import load
        from gdl.project import Project
        layout, self.assets = load(self.SEED)
        p = Project.open(self.SEED)
        page = next(o for o in p.o.values() if isinstance(o, dict)
                    and p.kind(o).split('.')[-1] in ('PBPage', 'PBPopupPage')
                    and p.field(o, 'nameField') == 'Audio Settings')
        btn = next(c for c in map(p.deref, p.items(p.field(page, 'controlsField')))
                   if isinstance(c, dict) and p.field(c, 'nameField') == 'Main Volume Mute')
        names = [p.field(p.field(s, 'buttonImageField'), 'resourceNameField') for s in p.states(btn)]
        built = next(pg for pg in layout['Pages'] + layout['PopupPages']
                     if pg['Name'] == 'Audio Settings')
        self.c = next(c for c in built['Controls'] if c['ID'] == p.field(btn, 'idField'))
        if not names or any(n not in kit for n in names):
            self.skipTest("Extron's Afterburn kit is not here (vendor/README.md)")
        self.imgs = [{'name': n, 'file': kit[n]} for n in names]

    def _check(self, i, built_state):
        others = [x for j, x in enumerate(self.imgs) if j != i]
        return self.vb._state_image('page Audio Settings', i, self.c['States'][built_state],
                                    self.c, self.imgs[i], None, self.assets, others)

    def test_every_state_as_built_passes_against_its_siblings(self):
        for i in range(len(self.imgs)):
            self.assertEqual(self._check(i, i), [], self.imgs[i]['name'])

    def test_a_level_built_with_the_one_befores_art_is_caught_and_named(self):
        i = len(self.imgs) - 1
        alone = self.vb._state_image('page Audio Settings', i, self.c['States'][i - 1], self.c,
                                     self.imgs[i], None, self.assets)
        self.assertEqual(alone, [], 'the case: alone, the near twin passes')
        problems = self._check(i, i - 1)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(f"nearer {self.imgs[i - 1]['name']!r}", problems[0])


class TestTranslucentFillUnderAnImageOnTheSeed(unittest.TestCase):
    """Extron's own build of a translucent fill under an icon: the Mach 1035
    seed's Main VC 'Initiate Call', #659945 at 220 Off and #86D161 On under
    755x440_call.png, built as (98, 150, 69, 220) - the very bytes the call
    mode's Make Call built on the 1035, which a tolerance of one rounding
    failed. Planned as the spec plans that key, it verifies."""
    SEED = os.path.join(os.path.dirname(HERE), 'seeds', 'Mach 1035.gdl')

    def test_the_seeds_call_key_verifies_as_planned(self):
        vb = _vb(self)
        from gdl.spec import resolve_image
        if not usable(self.SEED):
            self.skipTest('seeds/Mach 1035.gdl is not here (git lfs pull)')
        f = resolve_image('Mach/Extracted/755x440_call.png')
        if not f:
            self.skipTest("Mach's call icon is not extracted here (python -m gdl.designsys extract mach)")
        from gdl.compose import load
        layout, assets = load(self.SEED)
        page = next(pg for pg in layout['Pages'] if pg['Name'] == 'Main VC')
        c = next(c for c in page['Controls'] if c.get('Name') == 'Initiate Call')
        table = {'Main VC': {'Name': 'Main VC', 'Controls': [c]}}

        def check(image):
            op = {'fields': {'nameField': 'Initiate Call'}, 'fill': 0xDC659945, 'image': image,
                  'states': [{'name': 'Off', 'fill': 0xDC659945, 'image': image},
                             {'name': 'On', 'fill': 0xFF86D161, 'image': image}]}
            plan = [{'name': 'Main VC', 'controls': [op]}]
            return (vb.check_fills(plan, table, assets, 'page')[0]
                    + vb.check_states(plan, table, assets, 'page')[0])

        self.assertEqual(check({'name': '755x440_call.png', 'file': f}), [])
        # Planned bare, the same artwork is one rounding too far.
        bare = check(None)
        self.assertTrue(bare and all('#629645 at alpha 220' in p for p in bare), bare)


def _png_of(im):
    import io
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return buf.getvalue()


def _mean_off(a, b):
    """Mean difference per channel, 0-255, of two same-size RGBA images, each
    over one opaque key color so a transparent pixel compares as itself."""
    from PIL import Image, ImageChops, ImageStat

    def keyed(im):
        k = Image.new('RGBA', im.size, (255, 0, 255, 255))
        k.alpha_composite(im.convert('RGBA'))
        return k.convert('RGB')
    return sum(ImageStat.Stat(ImageChops.difference(keyed(a), keyed(b))).mean) / 3


class TestHorizontalSliderOnTheProbe(unittest.TestCase):
    """What Build does with a horizontal slider's kit art, off GUI Designer's
    own build: crops of the format probe's Shockwave sliders lying right and
    left - each rail's two ends, empty and full, and a thumb - cut from the
    built file (tests/data/probe-hslider-128, crops.json says which). Build
    turns the rail art, drawn standing up, a quarter turn so its top is the
    slider's full end, and lays it as it lays a vertical one; the thumb it
    stretches into its box unturned. The verifier drew the standing art on
    its side, and failed every horizontal slider the probe built, 45 to 82%
    off, on a panel that was right."""
    DATA = os.path.join(HERE, 'data', 'probe-hslider-128')

    def setUp(self):
        self.vb = _vb(self)
        from PIL import Image
        from gdl.spec import resolve_image
        with open(os.path.join(self.DATA, 'crops.json'), encoding='utf-8') as fh:
            self.meta = json.load(fh)
        self.kit = {k: resolve_image(v) for k, v in self.meta['kit'].items()}
        if not all(self.kit.values()):
            self.skipTest("Shockwave's slider art is not here (vendor/README.md)")
        self.sheet = Image.open(os.path.join(self.DATA, 'crops.png')).convert('RGBA')
        self.crops = [(r, self.sheet.crop(tuple(r['at']))) for r in self.meta['crops']]

    def rail(self, r, orientation, turned=True):
        """The rail the verifier expects for crop `r`, drawn at the asset's
        whole size and cut as the crop was; `turned=False` the standing art
        stretched on its side, as the verifier drew it."""
        from PIL import Image
        w, h = r['asset_size']
        under = self.kit['track'] if r['part'] == 'fill' else None
        if turned:
            im = self.vb.rail_image(self.kit[r['part']], w, h, r['track'], r['thumb'][0],
                                    orientation, under)
        else:
            im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            for f in ([under] if under else []) + [self.kit[r['part']]]:
                art = self.vb.stretch_image(f, w - r['thumb'][0], r['track'])
                im.alpha_composite(art, (r['thumb'][0] // 2, (h - r['track']) // 2))
        return im.crop(tuple(r['crop']))

    def test_a_rail_lying_down_is_its_art_turned(self):
        n = 0
        for r, built in self.crops:
            if r['part'] == 'thumb':
                continue
            n += 1
            where = (r['control'], r['part'], r['crop'])
            want = self.rail(r, r['orientation'])
            off = self.vb.image_mismatch(self.kit[r['part']], _png_of(built), *built.size,
                                         draw=lambda f, w, h, want=want: want)
            self.assertLess(off, 0.02, where)
            # Within a level of Build's own pixels, and an order of magnitude
            # nearer than the standing art laid on its side.
            near = _mean_off(want, built)
            self.assertLess(near, 1.0, where)
            self.assertGreater(_mean_off(self.rail(r, r['orientation'], turned=False), built),
                               10 * near, where)
        self.assertEqual(n, 8)

    def test_the_turn_puts_the_arts_top_at_the_full_end(self):
        """Lying right, a quarter turn clockwise; lying left, anticlockwise.
        The gate cannot tell them apart on Shockwave's near-symmetric rail,
        so this is measured: the other turn is over twice as far off on every
        crop, the full rail's ends the nearest (2.8 times)."""
        for r, built in self.crops:
            if r['part'] == 'thumb':
                continue
            own = _mean_off(self.rail(r, r['orientation']), built)
            other = _mean_off(self.rail(r, 1 - r['orientation']), built)
            self.assertLess(2 * own, other, (r['control'], r['part'], r['crop'], own, other))

    def test_a_thumb_is_its_art_stretched_unturned(self):
        """The probe's 34x52 thumb is the kit's 156x102 landscape art squeezed
        into it, as it lies on a vertical slider: 0% off. Fitted, as a
        button's image is, 58%."""
        r, built = next((r, im) for r, im in self.crops if r['part'] == 'thumb')
        art = _png_of(built)
        op = {'fields': {'nameField': r['control']},
              'thumb_image': {'name': os.path.basename(self.kit['thumb']), 'file': self.kit['thumb']}}
        table = {'Slider Probe': {'Name': 'Slider Probe', 'Controls': [
            {'ID': 1, 'Name': r['control'], 'Orientation': r['orientation'],
             'SliderIndicatorWidth': r['thumb'][0], 'SliderIndicatorHeight': r['thumb'][1],
             'SliderIndicatorImageID': 7}]}}
        problems, n = self.vb.check_thumbs([{'name': 'Slider Probe', 'controls': [op]}], table,
                                           {7: art}, 'page')
        self.assertEqual((n, problems), (1, []))
        self.assertGreater(self.vb.image_mismatch(self.kit['thumb'], art, *built.size),
                           self.vb.IMAGE_OFF)

    def test_check_rails_draws_a_horizontal_rail_turned(self):
        """check_rails hands the slider's orientation to the model: a built
        rail turned as Build turns it passes, the standing art on its side
        fails. Drawn whole here from the probe's sizes."""
        r = next(r for r, _ in self.crops if r['control'] == 'H Right 700' and r['part'] == 'track')
        w, h = r['asset_size']
        op = {'fields': {'nameField': 'H Right 700'},
              'track_image': {'name': 'track.png', 'file': self.kit['track']},
              'fill_image': {'name': 'fill.png', 'file': self.kit['fill']}}
        c = {'ID': 1, 'Name': 'H Right 700', 'Width': w, 'Height': h, 'Orientation': 0,
             'SliderTrackWidth': r['track'], 'SliderIndicatorWidth': r['thumb'][0],
             'SliderIndicatorHeight': r['thumb'][1], 'TLPMinValueImageID': 1,
             'TLPMaxValueImageID': 2}
        table = {'Slider Probe': {'Name': 'Slider Probe', 'Controls': [c]}}
        whole = dict(r, crop=[0, 0, w, h])
        turned = {1: _png_of(self.rail(whole, 0)), 2: _png_of(self.rail(dict(whole, part='fill'), 0))}
        flat = {1: _png_of(self.rail(whole, 0, turned=False)),
                2: _png_of(self.rail(dict(whole, part='fill'), 0, turned=False))}
        plan = [{'name': 'Slider Probe', 'controls': [op]}]
        self.assertEqual(self.vb.check_rails(plan, table, turned, 'page'), ([], 2))
        problems, _ = self.vb.check_rails(plan, table, flat, 'page')
        self.assertEqual(len(problems), 2, problems)


class TestSliderThumbOnTheSeed(unittest.TestCase):
    """Build stretches a thumb's kit art into its asset, whatever the art's
    shape: the Afterburn 1035 Portrait seed's 31 px wide sliders built their
    square 440x440 thumb as a 30x50 asset - 0% off stretched, 38% fitted, which
    failed the seed's own slider."""
    SEED = os.path.join(os.path.dirname(HERE), 'seeds', 'Afterburn 1035 Portrait.gdl')

    def test_the_seeds_narrow_thumb_verifies(self):
        vb = _vb(self)
        from PIL import Image
        import io
        from gdl.spec import resolve_image
        if not usable(self.SEED):
            self.skipTest('seeds/Afterburn 1035 Portrait.gdl is not here (git lfs pull)')
        f = resolve_image('Afterburn/Sliders & Toggles/440x440_thumb-1-periwinkle_sel.png')
        if not f:
            self.skipTest("Afterburn's slider art is not here (vendor/README.md)")
        from gdl.compose import load
        layout, assets = load(self.SEED)
        page = next(pg for pg in layout['PopupPages'] if pg['Name'] == 'Audio Settings')
        c = next(c for c in page['Controls'] if c.get('Name') == 'Mic Slider')
        self.assertEqual(Image.open(io.BytesIO(assets[c['SliderIndicatorImageID']])).size, (30, 50))
        op = {'fields': {'nameField': 'Mic Slider'},
              'thumb_image': {'name': os.path.basename(f), 'file': f}}
        table = {'Audio Settings': {'Name': 'Audio Settings', 'Controls': [c]}}
        self.assertEqual(vb.check_thumbs([{'name': 'Audio Settings', 'controls': [op]}], table,
                                         assets, 'page'), ([], 1))


class TestEditStates(unittest.TestCase):
    """An edit writes each state by index, so each is verified by index -
    captions and names off the model, fills off that state's own artwork."""

    def setUp(self):
        self.vb = _vb(self)
        self.assets = {90: _png((0x37, 0x39, 0x4E)), 91: _png((0x3D, 0x8B, 0xFD)),
                       92: _png((0x5A, 0x5C, 0x70))}

    def _check(self, op, j):
        op = dict({'page': 51, 'control': 3, 'why': 'test'}, **op)
        return self.vb.check_edits({'controls': [op]}, j, self.assets)[0]

    def test_a_state_caption_that_did_not_take_is_reported(self):
        op = {'per_state': [{'index': 1, 'fields': {'textField': 'Screen On'}}]}
        j = _built(_bst('Off', 'Display Off', 90), _bst('On', 'Display On', 91))
        problems = self._check(op, j)
        self.assertTrue(any("state 1 'On'" in p and 'Screen On' in p for p in problems),
                        problems)

    def test_only_the_written_state_is_checked(self):
        op = {'per_state': [{'index': 1, 'fields': {'textField': 'Screen On'}}]}
        j = _built(_bst('Off', 'Display Off', 90), _bst('On', 'Screen On', 91))
        self.assertEqual(self._check(op, j), [])

    def test_a_state_fill_is_read_off_that_states_artwork(self):
        op = {'per_state': [{'index': 1, 'colors': {'borderFillColorField': '#FF3D8BFD'}}]}
        self.assertEqual(self._check(op, _built(_bst('Off', '', 90), _bst('On', '', 91))), [])
        problems = self._check(op, _built(_bst('Off', '', 90), _bst('On', '', 90)))
        self.assertTrue(any('mostly #37394E' in p for p in problems), problems)

    def test_a_translucent_state_fill_is_read_at_its_own_alpha(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGBA', (8, 8), (36, 38, 52, 128)).save(buf, 'PNG')
        self.assets[93] = buf.getvalue()
        op = {'per_state': [{'index': 1, 'colors': {'borderFillColorField': '#80242634'}}]}
        self.assertEqual(self._check(op, _built(_bst('Off', '', 90), _bst('On', '', 93))), [])
        problems = self._check(op, _built(_bst('Off', '', 90), _bst('On', '', 90)))
        self.assertTrue(any('#242634 at alpha 128' in p and 'mostly #37394E' in p
                            for p in problems), problems)

    def test_a_state_text_color_is_read_off_the_model(self):
        op = {'per_state': [{'index': 0, 'colors': {'textColorField': '#FFF0F0F0'}}]}
        problems = self._check(op, _built(_bst('Off', 'x', 90)))
        self.assertTrue(any('text color is #FFFFFF' in p for p in problems), problems)

    def test_a_states_op_that_built_the_wrong_count_is_reported(self):
        op = {'state_count': 3, 'per_state': [], 'expect_states': []}
        problems = self._check(op, _built(_bst('Off', '', 90), _bst('On', '', 91)))
        self.assertTrue(any('2 states built' in p and 'asked for 3' in p for p in problems),
                        problems)

    def test_a_states_op_is_checked_state_by_state(self):
        op = {'state_count': 3,
              'fields': {'<TLPPressFeedbackStateID>k__BackingField': 2},
              'per_state': [{'index': i, 'fields': {'nameField': n}}
                            for i, n in enumerate(('Off', 'Warming', 'On'))],
              'expect_states': [
                  {'name': 'Off', 'text': 'Display Off', 'fill': '#FF37394E'},
                  {'name': 'Warming', 'text': 'Warming Up', 'fill': '#FF5A5C70'},
                  {'name': 'On', 'text': 'Display On', 'fill': '#FF3D8BFD'}]}
        good = _built(_bst('Off', 'Display Off', 90), _bst('Warming', 'Warming Up', 92),
                      _bst('On', 'Display On', 91), TLPPressFeedbackStateID=2)
        self.assertEqual(self._check(op, good), [])
        bad = _built(_bst('Off', 'Display Off', 90), _bst('On_1', 'Display On', 91),
                     _bst('On', 'Display On', 91), TLPPressFeedbackStateID=1)
        problems = self._check(op, bad)
        for needle in ("named 'On_1'", "caption is 'Display On'", 'press state is 1',
                       "'Warming' and 'On' were meant to look different"):
            self.assertTrue(any(needle in p for p in problems), (needle, problems))

    def test_a_plan_that_writes_every_state_alike_is_refused(self):
        problems = self._check({'states': {'textField': 'x'}},
                               _built(_bst('Off', 'x', 90)))
        self.assertTrue(any('re-plan' in p for p in problems), problems)


class TestBakedCaption(unittest.TestCase):
    """A renamed formatted caption is baked into its state's art and reads back
    as '' from layout.json, so verify_built looked nothing up and called it not
    verifiable. It is looked for in the art instead: each line the edit wrote,
    drawn by gdl.compose in the state's face, where it best fits."""

    FONT = {'Name': 'Arial', 'PointSize': 13, 'Style': {'Bold': False, 'Italic': False}}

    def setUp(self):
        self.vb = _vb(self)

    def _baked(self, ftext, size=(160, 62), ground=(0x37, 0x39, 0x4E), ink=(255, 255, 255)):
        """Art with `ftext` drawn into it as Build bakes a left-aligned
        caption: dark ground, white words, two tabs of indent."""
        import io
        from PIL import Image
        from gdl import compose
        img = Image.new('RGBA', size, ground + (255,))
        fnt = compose.face('Arial', 0, 0, 13 * compose.PT)
        compose.draw_text(img, (74, 0, size[0] - 74, size[1]), ftext.replace('\t', ''), fnt,
                          ink + (255,), 4)
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        return buf.getvalue()

    def _state(self, ink=(255, 255, 255)):
        return dict(_bst('Off', '', 90, {'A': 255, 'R': ink[0], 'G': ink[1], 'B': ink[2]}),
                    Font=self.FONT, TextAlignment=4)

    def test_a_caption_as_light_as_its_fill_is_not_verifiable_not_failed(self):
        """A pixel within CAPTION_TOLERANCE of the text color is text, so on a
        fill that close to it the whole fill is - white on (200, 200, 200) and
        black on (60, 60, 60) failed a correct build. The art cannot tell the
        caption from its fill there: not verifiable, as with a stand-in face."""
        for ground, ink in (((200, 200, 200), (255, 255, 255)), ((60, 60, 60), (0, 0, 0))):
            with self.subTest(ground=ground, ink=ink):
                art = self._baked('\t\tScreens', ground=ground, ink=ink)
                problem, note = self.vb.check_baked_caption('x', '\t\tScreens', self._state(ink), {90: art})
                self.assertIsNone(problem)
                self.assertIn('cannot tell its caption from its fill', note)
        # Outside the tolerance it is still looked for, and a wrong one found.
        art = self._baked('\t\tAudio', ground=(120, 120, 120), ink=(255, 255, 255))
        problem, note = self.vb.check_baked_caption('x', '\t\tScreens', self._state(), {90: art})
        self.assertIn("'Screens' is not in the art", problem or '')

    def test_an_icon_line_is_not_verifiable_not_failed(self):
        """The `states` op can write an icon glyph ('\\ue94e'), a private-use
        code point the state's own face does not draw - Build draws it in the
        icon face of its run - so a line holding one cannot be drawn to look
        for: not verifiable. The lines of words beside it still are."""
        art = self._baked('\t\tScreens')
        problem, note = self.vb.check_baked_caption('x', '', self._state(), {90: art})
        self.assertIsNone(problem)
        self.assertIn('private-use', note)
        problem, note = self.vb.check_baked_caption('x', '\r\n\t\tAudio', self._state(), {90: art})
        self.assertIn("'Audio' is not in the art", problem or '')
        problem, note = self.vb.check_baked_caption('x', '\r\n\t\tScreens', self._state(), {90: art})
        self.assertIsNone(problem)
        self.assertIn('private-use', note)

    def _check(self, ftext, art, built=None):
        op = {'page': 51, 'control': 3, 'why': 'test',
              'per_state': [{'index': 0, 'was': 'Displays', 'ftext': ftext, 'flattened': True}]}
        st = dict(_bst('Off', '', 90), Font=self.FONT, TextAlignment=4)
        return self.vb.check_edits({'controls': [op]}, _built(st, FlattenText=True), {90: art},
                                   {(51, 3): [built]} if built else None)[0]

    def test_a_caption_in_its_art_passes(self):
        self.assertEqual(self._check('Screens', self._baked('\t\tScreens'), '\t\tScreens'), [])

    def test_words_that_did_not_take_are_read_off_the_built_project(self):
        """The art cannot tell one letter from another - 'Diaplays' scores
        0.96 in Displays' - so the words are read where Build read them."""
        problems = self._check('Screens', self._baked('\t\tDisplays'), '\t\tDisplays')
        self.assertTrue(any("is 'Displays' in the built project" in p for p in problems), problems)

    def test_a_caption_not_in_its_art_is_reported(self):
        problems = self._check('\t\tScreens', self._baked('\t\tAudio'))
        self.assertTrue(any("'Screens' is not in the art" in p for p in problems), problems)

    def test_with_no_art_it_is_not_verifiable_not_a_problem(self):
        op = {'page': 51, 'control': 3, 'why': 'test',
              'per_state': [{'index': 0, 'was': 'Displays', 'ftext': 'Screens', 'flattened': True}]}
        st = dict(_bst('Off', '', 90), Font=self.FONT, TextAlignment=4)
        self.assertEqual(self.vb.check_edits({'controls': [op]}, _built(st))[0], [])

    def test_a_caption_that_wrapped_is_said_to_have(self):
        """Cameras -> Camera Control came out as 'Camera' over 'Control',
        the second line unindented (docs/editing.md)."""
        problems = self._check('\t\tCamera Control', self._baked('\t\tCamera\r\nControl'))
        self.assertTrue(any("wrapped after 'Camera'" in p for p in problems), problems)

    def test_each_line_of_a_two_line_caption_is_found(self):
        self.assertEqual(self._check('\t\tDevice\r\n\t\tComms', self._baked('\t\tDevice\r\n\t\tComms')), [])
        problems = self._check('\t\tDevice\r\n\t\tRouting', self._baked('\t\tDevice\r\n\t\tComms'))
        self.assertTrue(any("'Routing' is not in the art" in p for p in problems), problems)


class TestBakedCaptionInAStandIn(unittest.TestCase):
    """A face drawn in a stand-in leaves every caption in it unverifiable, not
    just the first: the face is cached, so only its first draw in a run adds
    its entry to compose.FALLBACKS."""

    def test_every_caption_in_a_stand_in_face_is_a_note(self):
        vb = _vb(self)
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow is not here')
        buf = io.BytesIO()
        Image.new('RGBA', (120, 40), (40, 40, 40, 255)).save(buf, 'PNG')
        bs = {'TLPImageID': 1, 'TextColor': '#FFFFFFFF',
              'Font': {'Name': 'No Face By This Name', 'PointSize': 13, 'Style': {}}}
        for word in ('Audio', 'Video'):
            problem, note = vb.check_baked_caption('x', word, bs, {1: buf.getvalue()})
            self.assertIsNone(problem, word)
            self.assertIn('stand-in', note or '', word)


@unittest.skipUnless(usable(FIXTURE), 'client fixture not present')
class TestBakedCaptionOnTheFixture(unittest.TestCase):
    """Against GUI Designer's own baking: the client fixture's formatted
    captions, every one found in its art in the fixture's own face, and none
    found where another caption was baked."""

    def setUp(self):
        self.vb = _vb(self)
        from gdl import compose
        from gdl.compose import load
        from gdl.project import Project
        from gdl.fonts import FILES
        if not os.path.exists(os.path.join(compose.FONTDIR, FILES[('Forma DJR Display', 0, 0)])):
            # The fixture's face comes out of the fixtures by `python -m
            # gdl.fonts` (CI recovers it before this file runs); drawn in a
            # stand-in, every caption is only 'not verifiable'.
            self.skipTest("the fixture's face is not recovered into gdl/fonts/")
        self.j, self.assets = load(FIXTURE)
        P = Project.open(FIXTURE)
        built = {(pg['ID'], c['ID']): c for pg in self.j['Pages'] + self.j['PopupPages']
                 for c in pg.get('Controls') or []}
        self.baked, self.icons = [], []
        proj = next(P.instances('PBProject'))
        for field in ('pagesField', 'popupPagesField'):
            for pg in P.items(P.field(proj, field)):
                for co in P.items(P.field(pg, 'controlsField')):
                    c = built.get((P.field(pg, 'idField'), P.field(co, 'idField')))
                    for i, st in enumerate(P.states(co)):
                        ft = P.deref(st.get('ftextField'))
                        # The formatted glyphs (U+E9xx) are icons, not words.
                        if c and ft:
                            (self.icons if any(0xE000 <= ord(ch) <= 0xF8FF for ch in ft) else
                             self.baked).append((ft, c['States'][i]))

    def test_an_icon_caption_is_never_failed(self):
        """Half the fixture's icon-bearing states failed as 'not in the art':
        their glyph drawn in the state's own face, which has none. Each is not
        verifiable here, none a problem - some for their icon, the rest for
        their grey text (#767789) on a fill (#37394E) within the tolerance."""
        self.assertTrue(self.icons)
        for ft, bs in self.icons:
            problem, note = self.vb.check_baked_caption('x', ft, bs, self.assets)
            self.assertIsNone(problem, ft)
            self.assertRegex(note or '', 'private-use|cannot tell its caption from its fill', ft)

    def test_every_formatted_caption_is_found_in_its_own_art(self):
        self.assertTrue(self.baked)
        for ft, bs in self.baked:
            problem, note = self.vb.check_baked_caption('x', ft, bs, self.assets)
            self.assertEqual((problem, note), (None, None), ft)

    def test_a_rename_checked_against_a_build_that_never_had_it(self):
        """The whole path: gdl.edit plans Displays -> Screens on the fixture,
        and the fixture itself, unedited, is the 'build' - its project says
        Displays, and so does its art."""
        import tempfile
        from gdl.edit import Edits
        plan, errors, _ = Edits({'edits': [{'op': 'rename', 'map': {'Displays': 'Screens'}}]},
                                FIXTURE).check()
        self.assertEqual(errors, [])
        self.assertTrue(any(ps.get('flattened') for op in plan['controls']
                            for ps in op.get('per_state') or []), plan['controls'])
        path = os.path.join(tempfile.mkdtemp(), 'plan.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(plan, fh)
        problems, _ = self.vb.check(path, FIXTURE)
        self.assertTrue(any("is 'Displays' in the built project, the edit asked for 'Screens'" in p
                            for p in problems), problems)

    def test_another_caption_is_never_found_in_it(self):
        words = sorted({ln.replace('\t', '').strip() for ft, _ in self.baked for ln in ft.split('\r\n')})
        for ft, bs in self.baked[::4]:
            own = {ln.replace('\t', '').strip() for ln in ft.split('\r\n')}
            for w in words:
                if w in own:
                    continue
                problem, note = self.vb.check_baked_caption('x', '\t\t' + w, bs, self.assets)
                self.assertFalse(problem is None and note is None, (w, ft))


class TestOfflinePage(unittest.TestCase):
    """The Offline Page as the plan says it: EnableOfflinePage, the full-canvas
    reference Build gives every page while it is on, and the words on it."""

    OLD, NEW = 'XXX.XXX.XXXX', '555.010.4567'
    PLAN = {'pages': [{'name': 'Home'}, {'name': 'Second'}],
            'offline': {'enabled': True, 'replace': [{'old': OLD, 'new': NEW}]}}

    def _layout(self, on=True, refs=('Home', 'Second'), words=None):
        words = words or ['It looks like this touchpanel has lost connection.',
                          '\n\nPlease call 555.010.4567 immediately.']
        return {'EnableOfflinePage': on, 'OfflinePageID': 65535,
                'Pages': [{'ID': 51 + i, 'Name': n, 'Controls': [_ref(65535)] if n in refs else []}
                          for i, n in enumerate(('Home', 'Second'))],
                'PopupPages': [{'ID': 65535, 'Name': 'Offline Page', 'Modal': True,
                                'TLPImageID': 4 if on else -1,
                                'Controls': [{'Type': 11, 'Name': f'Label {i}', 'Text': w}
                                             for i, w in enumerate(words)]}]}

    def test_built_as_planned_passes(self):
        self.assertEqual(_vb(self).check_offline(self.PLAN, self._layout()), [])

    def test_a_plan_that_says_nothing_is_not_held(self):
        vb = _vb(self)
        self.assertEqual(vb.check_offline({'pages': [{'name': 'Home'}], 'offline': None},
                                          self._layout(on=False, words=['XXX.XXX.XXXX'])), [])

    def test_switched_the_other_way_is_reported(self):
        problems = _vb(self).check_offline(self.PLAN, self._layout(on=False, refs=()))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('built off, and the plan has it on', problems[0])

    def test_a_page_with_no_reference_while_it_is_on_is_reported(self):
        problems = _vb(self).check_offline(self.PLAN, self._layout(refs=('Home',)))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("'Second' has no reference to the Offline Page", problems[0])
        plan = dict(self.PLAN, offline={'enabled': False, 'replace': []})
        problems = _vb(self).check_offline(plan, self._layout(on=False, refs=('Home',)))
        self.assertTrue(any("'Home' has a reference" in p for p in problems), problems)

    def test_on_with_no_artwork_is_reported(self):
        """Build draws it only while it is on: TLPImageID -1 on every seed
        with it off, an asset on every one with it on."""
        j = self._layout()
        j['PopupPages'][0]['TLPImageID'] = -1
        problems = _vb(self).check_offline(self.PLAN, j)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('no artwork', problems[0])

    def test_words_not_replaced_are_reported(self):
        problems = _vb(self).check_offline(self.PLAN, self._layout(
            words=['\n\nPlease call XXX.XXX.XXXX immediately.']))
        self.assertTrue(any("does not say '555.010.4567'" in p for p in problems), problems)
        self.assertTrue(any("still says 'XXX.XXX.XXXX'" in p for p in problems), problems)

    def test_check_runs_it(self):
        src = open(_vb(self).__file__, encoding='utf-8').read()
        self.assertIn('check_offline(plan, j)', src)


class TestPopupBoundById(unittest.TestCase):
    """A reference bound to one popup by its ID, as nine seeds show their
    ungrouped Volume Level: PopupID the built popup's own, IsPopupPageIdValid
    true, GroupID 0 - and the popup in no group, with its references."""

    PLAN = {'pages': [{'name': 'Home', 'controls': [
        {'donor_type': 'PBPopupPageReference', 'popup': 'Volume Level', 'group': None,
         'fields': {'nameField': 'Volume'}}]}],
            'popups': [{'name': 'Volume Level', 'group': None, 'modal': False}]}

    def _layout(self, **pp):
        ref = dict(_ref(24), Name='Volume')
        ref['PopupPageID'] = dict(ref['PopupPageID'], **pp)
        return {'Pages': [{'ID': 51, 'Name': 'Home', 'Controls': [ref]}],
                'PopupPages': [{'ID': 24, 'Name': 'Volume Level', 'Modal': False, 'GroupID': 0,
                                'IsGroupValid': False, 'HasReferences': True},
                               {'ID': 25, 'Name': 'Other', 'Modal': False, 'GroupID': 0,
                                'IsGroupValid': False, 'HasReferences': True}]}

    def test_built_as_planned_passes(self):
        self.assertEqual(_vb(self).check_popup_ids(self.PLAN, self._layout()), [])

    def test_bound_to_another_popup_is_reported(self):
        problems = _vb(self).check_popup_ids(self.PLAN, self._layout(PopupID=25))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("bound to popup 25, and the plan binds it to 'Volume Level', popup 24",
                      problems[0])
        problems = _vb(self).check_popup_ids(self.PLAN, self._layout(
            PopupID=18446744073709551615, IsPopupPageIdValid=False))
        self.assertEqual(len(problems), 1, problems)

    def test_bound_to_a_group_as_well_is_reported(self):
        problems = _vb(self).check_popup_ids(self.PLAN, self._layout(GroupID=3,
                                                                     IsPopupGroupIdValid=True))
        self.assertTrue(any('bound to group 3 as well' in p for p in problems), problems)

    def test_the_popup_built_in_a_group_or_unreferenced_is_reported(self):
        j = self._layout()
        j['PopupPages'][0].update(GroupID=2, IsGroupValid=True, HasReferences=False)
        problems = _vb(self).check_popup_ids(self.PLAN, j)
        self.assertTrue(any("'Volume Level' built in group 2" in p for p in problems), problems)
        self.assertTrue(any('HasReferences false' in p for p in problems), problems)

    def test_check_runs_it(self):
        self.assertIn('check_popup_ids(plan, j)', open(_vb(self).__file__, encoding='utf-8').read())


class TestPopupTimeout(unittest.TestCase):
    """PBPopupPage.timeoutField is in the authoring graph only - layout.json
    has no timeout - so the built project is what is held to the plan."""

    def _seed(self):
        from _corpus import seed
        path = seed('Afterburn 320.gdl')
        if not usable(path):
            self.skipTest('seeds/Afterburn 320.gdl is not here (an LFS pull fetches it)')
        return path

    def test_the_built_projects_field_is_held_to_the_plan(self):
        vb, path = _vb(self), self._seed()
        # 0 on every seed popup.
        self.assertEqual(vb.check_timeouts({'popups': [{'name': 'Volume Level', 'timeout': 0}]},
                                           path), [])
        problems = vb.check_timeouts({'popups': [{'name': 'Volume Level', 'timeout': 30}]}, path)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("'Volume Level' built with timeout 0 in the project, and the plan has 30",
                      problems[0])

    def test_a_plan_from_before_the_key_is_not_held(self):
        self.assertEqual(_vb(self).check_timeouts({'popups': [{'name': 'Volume Level'}]},
                                                  'no-such-file.gdl'), [])

    def test_check_runs_it(self):
        self.assertIn('check_timeouts(plan, built_path)',
                      open(_vb(self).__file__, encoding='utf-8').read())


class TestTypeNames(unittest.TestCase):
    """TYPE_NAME once said Line 9, DateTime 12, Slider 14 and Level 15. Every
    message naming one of those types was wrong."""

    def test_every_type_number_matches_the_built_type(self):
        vb = _vb(self)
        if not usable(FIXTURE):
            self.skipTest('fixture not present')
        from gdl.container import open_payload
        j = json.loads(open_payload(FIXTURE).read('layout.json'))
        seen = {}
        for pg in j['Pages'] + j['PopupPages']:
            for c in pg.get('Controls') or []:
                seen[c.get('Type')] = c.get('__type')
        for num, name in seen.items():
            if num in vb.TYPE_NAME:
                self.assertEqual('PB' + vb.TYPE_NAME[num], name, f'Type {num}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
