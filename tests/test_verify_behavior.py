"""The program verifier has to FAIL on the things Build can do to a program.

A verifier that has only ever passed proves nothing, so each test here builds
a layout.json the way Build would - then breaks one thing it has been seen to
break, and expects exactly that reported.

    python tests/test_verify_behavior.py
"""
import copy
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import verify_behavior as vb  # noqa: E402
from gdl.behavior import CLASS_OF, load  # noqa: E402

EXAMPLE = os.path.join(os.path.dirname(HERE), 'examples', 'huddle-program.json')
TYPE_NUM = {'button': 7, 'label': 11, 'slider': 27, 'level': 9, 'panel': 13}


def built_layout(prog):
    """What Build makes of the spec: new page IDs, the spec's control IDs and
    names, and one full-canvas reference per modal popup on every page."""
    pages, popups = [], []
    next_id = 9202
    ids = {}
    for ct in prog.containers:
        ids[ct['name']] = next_id
        next_id += 1
    for ct in prog.containers:
        controls = [{'Name': r['name'], 'UserId': r['id'], 'Type': TYPE_NUM.get(r['kind'], 13),
                     '__type': 'PB' + (CLASS_OF.get(r['kind']) or 'Shape'),
                     'States': [{}, {}] if r['kind'] == 'button' else []}
                    for r in ct['controls']]
        box = {'Name': ct['name'], 'ID': ids[ct['name']], 'Controls': controls}
        if ct['kind'] == 'page':
            for m in prog.containers:
                if m['modal']:
                    controls.append({'Name': 'Popup Page Reference', 'UserId': 0, 'Type': 6,
                                     '__type': 'PBPopupPageReference',
                                     'PopupPageID': {'IsPopupPageIdValid': True,
                                                     'PopupID': ids[m['name']],
                                                     'IsPopupGroupIdValid': False,
                                                     'GroupID': 0}})
            pages.append(box)
        else:
            box.update(Modal=ct['modal'], GroupID=0 if ct['modal'] else 1)
            popups.append(box)
    return {'DefaultPage': ids[prog.start_page], 'Pages': pages, 'PopupPages': popups}


class TestVerifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.prog = load(EXAMPLE)
        cls.prog.generate(cls.dir)
        cls.good = built_layout(cls.prog)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def run_on(self, j):
        return vb.check_layout(self.dir, j)

    def box(self, j, name):
        return next(b for b in j['Pages'] + j['PopupPages'] if b['Name'] == name)

    def test_a_faithful_build_passes(self):
        problems, _, checked = self.run_on(self.good)
        self.assertEqual(problems, [])
        self.assertGreater(checked, 20)

    def test_a_page_missing_from_the_build_is_reported(self):
        j = copy.deepcopy(self.good)
        self.box(j, 'Huddle Help')['Name'] = 'Help'
        problems, _, _ = self.run_on(j)
        self.assertTrue(any("ShowPage('Huddle Help')" in p for p in problems), problems)

    def test_a_control_whose_id_changed_is_reported(self):
        j = copy.deepcopy(self.good)
        c = next(x for x in self.box(j, 'Huddle Home')['Controls'] if x['Name'] == 'Mute')
        c['UserId'] = 4242
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Mute' in p and '4242' in p for p in problems), problems)

    def test_a_control_built_as_another_type_is_reported(self):
        j = copy.deepcopy(self.good)
        c = next(x for x in self.box(j, 'Huddle Home')['Controls'] if x['Name'] == 'Laptop')
        c['__type'] = 'PBLabel'
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Laptop' in p and 'PBLabel' in p for p in problems), problems)

    def test_a_selectable_button_with_one_state_is_reported(self):
        j = copy.deepcopy(self.good)
        c = next(x for x in self.box(j, 'Huddle Home')['Controls'] if x['Name'] == 'Wireless')
        c['States'] = [{}]
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Wireless' in p and 'state' in p for p in problems), problems)

    def test_a_modal_with_no_reference_on_its_page_is_reported(self):
        j = copy.deepcopy(self.good)
        home = self.box(j, 'Huddle Home')
        home['Controls'] = [c for c in home['Controls'] if c['Type'] != 6]
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Confirm End Call' in p and 'reference' in p for p in problems),
                        problems)

    def test_another_control_sharing_an_addressed_id_is_reported(self):
        j = copy.deepcopy(self.good)
        help_page = self.box(j, 'Huddle Help')
        mute_id = next(c['id'] for c in self.prog.handoff('x')['controls']
                       if c['at'][0]['name'] == 'Mute')
        help_page['Controls'].append({'Name': 'Stray', 'UserId': mute_id, 'Type': 7,
                                      '__type': 'PBButton', 'States': [{}, {}]})
        problems, _, _ = self.run_on(j)
        self.assertTrue(any('Stray' in p for p in problems), problems)

    def test_a_donor_page_sharing_an_id_is_only_a_note(self):
        j = copy.deepcopy(self.good)
        mute_id = next(c['id'] for c in self.prog.handoff('x')['controls']
                       if c['at'][0]['name'] == 'Mute')
        j['Pages'].append({'Name': 'Start', 'ID': 0, 'Controls': [
            {'Name': 'Donor', 'UserId': mute_id, 'Type': 7, '__type': 'PBButton',
             'States': [{}, {}]}]})
        problems, notes, _ = self.run_on(j)
        self.assertEqual(problems, [])
        self.assertTrue(any('Start' in n for n in notes), notes)

    def test_a_hand_edited_program_is_reported(self):
        d = tempfile.mkdtemp()
        try:
            self.prog.generate(d)
            path = os.path.join(d, 'ui_events.py')
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(src.replace('# spec_sha256: ', '# spec_sha256: 00'))
            problems, _, _ = vb.check_layout(d, self.good)
            self.assertTrue(any('regenerate' in p for p in problems), problems)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
