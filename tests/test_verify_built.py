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
