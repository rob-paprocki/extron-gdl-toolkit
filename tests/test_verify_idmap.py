"""The ID map verifier has to FAIL on the things Build can do to a panel.

A verifier that has only ever passed proves nothing, so each test here builds
a layout.json the way Build would, breaks one thing it has been seen to break,
and expects exactly that reported.

    python tests/test_verify_idmap.py
"""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import verify_idmap as vi  # noqa: E402
from gdl.idmap import CLASS_OF, load  # noqa: E402

EXAMPLE = os.path.join(os.path.dirname(HERE), 'examples', 'huddle-functions.json')
TYPE_NUM = {'button': 7, 'label': 11, 'slider': 27, 'level': 9, 'panel': 13}


def built_layout(m):
    """What Build makes of a spec: new page IDs, the spec's control IDs and
    names, a group reference wherever the spec placed a popup_ref, and one
    full-canvas reference per modal popup on every page."""
    ids = {ct['name']: 9202 + i for i, ct in enumerate(m.containers)}
    groups = {g: i + 1 for i, g in enumerate(sorted(
        {ct['group'] for ct in m.containers if ct['group']}))}
    pages, popups = [], []
    for ct in m.containers:
        controls = [{'Name': r['name'], 'UserId': r['id'], 'Type': TYPE_NUM.get(r['kind'], 13),
                     '__type': 'PB' + (CLASS_OF.get(r['kind']) or 'Shape')}
                    for r in ct['controls'] if r['kind'] != 'popup_ref']
        for x, r in zip(controls, [r for r in ct['controls'] if r['kind'] != 'popup_ref']):
            if r['states']:
                x['States'] = [{'ID': i, 'Name': n} for i, n in enumerate(r['states'])]
                x['TLPDefaultStateID'] = 0
                x['TLPPressFeedbackStateID'] = r['states'].index(r['press'])
        for g in sorted(ct['refs']):
            controls.append({'Name': 'Ref ' + g, 'UserId': 0, 'Type': 6,
                             'PopupPageID': {'IsPopupGroupIdValid': True,
                                             'GroupID': groups.get(g, 99)}})
        box = {'Name': ct['name'], 'ID': ids[ct['name']], 'Controls': controls}
        if ct['kind'] == 'page':
            for p in m.containers:
                if p['modal']:
                    controls.append({'Name': 'Popup Page Reference', 'UserId': 0, 'Type': 6,
                                     'PopupPageID': {'IsPopupPageIdValid': True,
                                                     'PopupID': ids[p['name']]}})
            pages.append(box)
        else:
            box.update(Modal=ct['modal'], GroupID=0 if ct['modal'] else groups[ct['group']])
            popups.append(box)
    return {'Pages': pages, 'PopupPages': popups}


class TestVerifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.m = load(EXAMPLE)
        cls.m.write(cls.dir)
        cls.good = built_layout(cls.m)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def run_on(self, j):
        return vi.check_layout(self.dir, j)

    def box(self, j, name):
        return next(b for b in j['Pages'] + j['PopupPages'] if b['Name'] == name)

    def control(self, j, page, name):
        return next(x for x in self.box(j, page)['Controls'] if x['Name'] == name)

    def test_a_faithful_build_passes(self):
        problems, _, checked = self.run_on(self.good)
        self.assertEqual(problems, [])
        self.assertGreater(checked, 20)

    def test_a_page_missing_from_the_build_is_reported(self):
        j = copy.deepcopy(self.good)
        self.box(j, 'Huddle Help')['Name'] = 'Help'
        problems, _, _ = self.run_on(j)
        self.assertTrue(any("'Huddle Help'" in p for p in problems), problems)

    def test_a_popup_that_built_the_wrong_kind_is_reported(self):
        j = copy.deepcopy(self.good)
        self.box(j, 'Confirm Room Off')['Modal'] = False
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Confirm Room Off' in p and 'standard' in p for p in problems),
                        problems)

    def test_a_control_whose_id_changed_is_reported(self):
        j = copy.deepcopy(self.good)
        self.control(j, 'Huddle Home', 'Mute')['UserId'] = 4242
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Mute' in p and '4242' in p for p in problems), problems)

    def test_a_control_built_as_another_type_is_reported(self):
        j = copy.deepcopy(self.good)
        self.control(j, 'Huddle Home', 'Laptop')['__type'] = 'PBLabel'
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Laptop' in p and 'PBLabel' in p for p in problems), problems)

    def test_a_second_control_of_the_same_name_is_checked_too(self):
        j = copy.deepcopy(self.good)
        home = self.box(j, 'Huddle Home')
        home['Controls'].append(dict(self.control(j, 'Huddle Home', 'Mute'),
                                     __type='PBLabel', Type=11))
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Mute' in p for p in problems), problems)

    def test_a_modal_with_no_reference_on_its_page_is_reported(self):
        j = copy.deepcopy(self.good)
        home = self.box(j, 'Huddle Home')
        home['Controls'] = [c for c in home['Controls'] if c['Type'] != 6]
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Confirm Room Off' in p and 'reference' in p for p in problems),
                        problems)

    def test_another_control_sharing_a_mapped_id_is_reported(self):
        j = copy.deepcopy(self.good)
        mute = self.control(j, 'Huddle Home', 'Mute')['UserId']
        self.box(j, 'Huddle Help')['Controls'].append(
            {'Name': 'Stray', 'UserId': mute, 'Type': 7, '__type': 'PBButton'})
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Stray' in p for p in problems), problems)

    def test_a_donor_page_sharing_an_id_is_a_note(self):
        j = copy.deepcopy(self.good)
        mute = self.control(j, 'Huddle Home', 'Mute')['UserId']
        j['Pages'].append({'Name': 'Start', 'ID': 0, 'Controls': [
            {'Name': 'Donor', 'UserId': mute, 'Type': 7, '__type': 'PBButton'}]})
        problems, notes, _ = self.run_on(j)
        self.assertEqual(problems, [])
        self.assertTrue(any('Start' in n for n in notes), notes)

    def test_a_duplicate_built_name_is_reported(self):
        j = copy.deepcopy(self.good)
        j['PopupPages'].insert(0, {'Name': 'Confirm Room Off', 'ID': 7777, 'Modal': True,
                                   'Controls': []})
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('twice' in p for p in problems), problems)


class TestStates(unittest.TestCase):
    """The map numbers each button's states as the program sets them, so the
    built button must have exactly those, in that order."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.m = load(EXAMPLE)
        cls.m.write(cls.dir)
        cls.good = built_layout(cls.m)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def display(self, j):
        page = next(b for b in j['Pages'] if b['Name'] == 'Huddle Home')
        return next(x for x in page['Controls'] if x['Name'] == 'Display')

    def test_the_example_has_a_four_state_button(self):
        self.assertEqual([s['Name'] for s in self.display(self.good)['States']],
                         ['Off', 'Warming', 'On', 'Cooling'])
        self.assertEqual(vi.check_layout(self.dir, self.good)[0], [])

    def test_a_state_in_the_wrong_place_is_reported(self):
        j = copy.deepcopy(self.good)
        st = self.display(j)['States']
        st[1]['Name'], st[3]['Name'] = st[3]['Name'], st[1]['Name']
        problems = vi.check_layout(self.dir, j)[0]
        self.assertTrue([p for p in problems if "'Display'" in p and 'Warming' in p], problems)

    def test_a_missing_state_is_reported(self):
        j = copy.deepcopy(self.good)
        self.display(j)['States'].pop()
        problems = vi.check_layout(self.dir, j)[0]
        self.assertTrue([p for p in problems if "'Display'" in p and 'Cooling' in p], problems)

    def test_the_press_state_is_checked(self):
        j = copy.deepcopy(self.good)
        self.display(j)['TLPPressFeedbackStateID'] = 1
        problems = vi.check_layout(self.dir, j)[0]
        self.assertTrue([p for p in problems if "'Display'" in p and 'press' in p], problems)


class TestPopupFromPopup(unittest.TestCase):
    """A standard popup shown from a button on another popup appears through
    the PAGE beneath, so that page needs a reference to its group."""

    SPEC = {
        'name': 'T', 'size': [1280, 800],
        'theme': {'text': '#FFFFFF', 'raised': '#2E3142', 'accent': '#3D8BFD', 'on': 'accent'},
        'pages': [{'name': 'Home', 'number': 1000, 'controls': [
            {'kind': 'popup_ref', 'name': 'R1', 'rect': [0, 0, 300, 200], 'group': 'g1'},
            {'kind': 'popup_ref', 'name': 'R2', 'rect': [400, 0, 300, 200], 'group': 'g2'},
            {'kind': 'button', 'name': 'Open', 'rect': [0, 700, 100, 80], 'nav': 'A'}]}],
        'popups': [
            {'name': 'A', 'number': 9100, 'group': 'g1', 'size': [300, 200], 'controls': [
                {'kind': 'button', 'name': 'ShowB', 'rect': [10, 10, 100, 80], 'nav': 'B'}]},
            {'name': 'B', 'number': 9200, 'group': 'g2', 'size': [300, 200], 'controls': [
                {'kind': 'button', 'name': 'CloseB', 'rect': [10, 10, 100, 80],
                 'does': 'Closes this popup.'}]}],
    }

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        path = os.path.join(self.dir, 'spec.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(self.SPEC, fh)
        self.m = load(path)
        self.assertEqual(self.m.check()[0], [])
        self.out = os.path.join(self.dir, 'map')
        self.m.write(self.out)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_the_page_beneath_has_the_reference(self):
        problems, _, _ = vi.check_layout(self.out, built_layout(self.m))
        self.assertEqual(problems, [])

    def test_losing_that_reference_is_reported(self):
        j = built_layout(self.m)
        home = j['Pages'][0]
        home['Controls'] = [c for c in home['Controls'] if c.get('Name') != 'Ref g2']
        problems, _, _ = vi.check_layout(self.out, j)
        self.assertTrue(any("'B'" in p and 'Home' in p for p in problems), problems)


if __name__ == '__main__':
    unittest.main(verbosity=2)
