"""The built-file verifier's layout checks: start page, modal popups, type names.

Each of these was a silent failure before it was checked. A generated panel
booted into the donor's start page, and a spec's modal confirmation built as a
standard popup that nothing could show. Both builds reported 0 errors.

    python tests/test_verify_built.py
"""
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

    def test_a_modal_is_not_checked(self):
        # Build draws a modal under its scrim and ignores its fill.
        self.assertEqual(self._check(_png((0, 0, 0)), modal=True), [])

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
                                 (0x26000000, (0, 0, 0, 128), True)):        # another alpha
            op = {'fields': {'nameField': 'Card'}, 'fill': fill}
            problems, notes, n = self.vb.check_fills([{'name': 'Home', 'controls': [op]}],
                                                     table, {7: art(built)}, 'page')
            self.assertEqual(n, 1, (hex(fill), built))
            self.assertEqual(bool(problems), bad, (hex(fill), built, problems))
            self.assertFalse(any('not checked' in x for x in notes), notes)

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
        right = {1: art(self.vb.rail_image(files['track.png'], 60, 391, 24, 52, True)),
                 2: art(self.vb.rail_image(files['fill.png'], 60, 391, 24, 52, True))}
        wide = {1: art(self.vb.stretch_image(files['track.png'], 60, 391)), 2: right[2]}
        long = {1: art(self.vb.rail_image(files['track.png'], 60, 391, 24, 0, True)), 2: right[2]}
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
