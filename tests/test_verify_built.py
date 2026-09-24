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
                       'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')


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

    def test_a_page_built_without_it_is_reported(self):
        problems = self._check(_png((36, 38, 52)))
        self.assertTrue(any('not the planned image' in p for p in problems), problems)
        problems = self._check(_png((36, 38, 52)), file=False)
        self.assertTrue(any('single flat color' in p for p in problems), problems)


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
