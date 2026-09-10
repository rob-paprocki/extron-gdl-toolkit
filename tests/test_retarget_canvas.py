"""A retarget must scale every page's CANVAS, not just its controls.

The bug this pins: `retarget --scale` scaled the controls and emitted no page
size at all, and `Apply-GdlEdits.ps1` made up the difference by setting every
page AND popup to the new screen size. That is right for a full-canvas popup
and wrong for any other, and it went unnoticed for two reasons:

  * the only project it was ever run against - the Liberty Bank fixture - has
    every popup authored full-canvas, so the two rules agree there;
  * `check()`'s overflow test, the one whose docstring calls it "the check that
    makes retargeting safe to offer", skipped popups outright
    (`if pg['kind'] != 'page': continue`). Popups are the only place a canvas
    and the screen are allowed to disagree, so that is the only place the check
    could ever have fired.

Extron's own Afterburn template settles what a popup's authored size means:
10 of its 29 popups are authored at 880x525, and the BUILT layout.json reports
880x525 for them. The authored size is the popup size. Forcing it to the screen
size turns a modal card into a full-screen page in the shipped file.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.edit import Edits
from gdl.project import Project

FIXTURE = os.path.join('fixtures', 'gdl',
                       'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
RETARGET = {'edits': [{'op': 'retarget', 'model': 'TLP1535M', 'scale': True}]}


def plan_for(spec, path):
    ed = Edits(spec, path)
    plan, errors, warnings = ed.check()
    return ed, plan, errors, warnings


class TestCanvasScales(unittest.TestCase):
    def setUp(self):
        self.ed, self.plan, self.errors, _ = plan_for(RETARGET, FIXTURE)

    def test_every_page_gets_a_size(self):
        """No page may be left for the applier to guess at."""
        got = {p['page'] for p in self.plan['pages']}
        want = {pg['id'] for pg in self.ed.pages if None not in pg['size']}
        self.assertTrue(want, 'fixture has no sized pages - test is vacuous')
        self.assertEqual(want, got)

    def test_popups_are_included(self):
        kinds = {p['kind'] for p in self.plan['pages']}
        self.assertIn('popup', kinds,
                      'popups left out of the page ops is the original bug')

    def test_canvas_scales_by_the_same_factor_as_its_controls(self):
        """The invariant. Canvas and contents move together or a control that
        fit before stops fitting, and Build relocates it to 0,0 in silence."""
        old, new = self.ed._resize
        sx, sy = new[0] / old[0], new[1] / old[1]
        for p in self.plan['pages']:
            w, h = p['was']
            self.assertEqual(p['size'], [round(w * sx), round(h * sy)],
                             f"{p['name']} canvas did not scale with its controls")

    def test_a_full_canvas_page_lands_exactly_on_the_screen_size(self):
        """Scaling by the same factor must not drift off the target for the
        pages that ARE the canvas, or the project disagrees with itself."""
        _, new = self.ed._resize
        std = [p for p in self.plan['pages'] if p['kind'] == 'page']
        self.assertTrue(std)
        for p in std:
            self.assertEqual(p['size'], list(new))

    def test_no_control_overflows_its_new_canvas(self):
        self.assertEqual(self.errors, [])


class TestSmallPopupsSurvive(unittest.TestCase):
    """The case the fixture cannot show, built from Extron's own numbers.

    Rather than depend on a seed that is not in the repo, this drives the same
    code path with a hand-made project stub whose popup is authored smaller
    than the screen - which is what `Afterburn 1035.gdl` demonstrated is legal
    and what the built payload confirms is preserved.
    """

    def setUp(self):
        self.ed, self.plan, self.errors, _ = plan_for(RETARGET, FIXTURE)
        # Splice in a small popup alongside the real pages, so the op walk and
        # the overflow check both see it exactly as they would a real one.
        self.ed.pages = list(self.ed.pages) + [{
            'kind': 'popup', 'id': 999999, 'name': 'Small Card', 'modal': True,
            'size': (880, 525),
            'controls': [{'obj_id': 1, 'id': 1, 'name': 'Body', 'type': 'PBButton',
                          'caption': None, 'caption_in': None, 'rect': (0, 0, 880, 525)}],
        }]
        self.plan, self.errors, _ = self.ed.check()
        self.small = next(p for p in self.plan['pages'] if p['name'] == 'Small Card')

    def test_a_small_popup_is_not_promoted_to_full_screen(self):
        _, new = self.ed._resize
        self.assertNotEqual(self.small['size'], list(new),
                            'an 880x525 modal card was resized to the whole screen')

    def test_it_keeps_its_proportions(self):
        old, new = self.ed._resize
        sx, sy = new[0] / old[0], new[1] / old[1]
        self.assertEqual(self.small['size'], [round(880 * sx), round(525 * sy)])

    def test_its_contents_still_fit(self):
        self.assertEqual(
            [e for e in self.errors if 'Small Card' in e], [],
            'a control that filled the old popup must still fill the new one')


class TestOverflowIsCaughtOnPopups(unittest.TestCase):
    """The check has to be able to fail, or passing it means nothing."""

    def test_a_control_outside_a_popup_is_reported(self):
        ed, _, _, _ = plan_for(RETARGET, FIXTURE)
        ed.pages = list(ed.pages) + [{
            'kind': 'popup', 'id': 999998, 'name': 'Bad Card', 'modal': True,
            'size': (880, 525),
            'controls': [{'obj_id': 1, 'id': 1, 'name': 'Overhang',
                          'type': 'PBButton', 'caption': None, 'caption_in': None,
                          # Deliberately outside: scaling cannot bring it back in,
                          # because the canvas scales by the same factor.
                          'rect': (800, 500, 400, 400)}],
        }]
        _, errors, _ = ed.check()
        self.assertTrue([e for e in errors if 'Overhang' in e],
                        'popup overflow went unreported - the blind spot is back')


class TestExtronsOwnTemplateIfPresent(unittest.TestCase):
    """Ground truth, skipped when the seeds are not installed.

    The seeds live outside the repo (they are Extron's, not ours) so this can
    only run on a machine that has GUI Designer. It is the test that actually
    proves the premise, so it is worth having even though CI skips it.
    """

    SEED = ('C:/Users/Public/Documents/Extron/GUI Designer/Afterburn 1035.gdl')

    def setUp(self):
        if not os.path.exists(self.SEED):
            self.skipTest('Afterburn seed not installed')

    def test_authored_popup_sizes_are_not_all_full_canvas(self):
        proj = Project.open(self.SEED)
        sizes = {p['size'] for p in proj.pages() if p['kind'] == 'popup'}
        self.assertGreater(len(sizes), 1,
                           'if every popup were full-canvas the old rule was fine')

    def test_the_built_payload_agrees_with_the_authored_canvas(self):
        """What makes the authored size authoritative rather than a hint."""
        from gdl.container import open_payload
        lay = json.loads(open_payload(self.SEED).read('layout.json')
                         .decode('utf-8-sig'))
        authored = {p['name']: tuple(p['size'])
                    for p in Project.open(self.SEED).pages() if p['kind'] == 'popup'}
        checked = 0
        for p in lay['PopupPages']:
            want = authored.get(p['Name'])
            if want is None:
                continue
            checked += 1
            self.assertEqual((p['Width'], p['Height']), want,
                             f"{p['Name']}: built size differs from authored")
        self.assertGreater(checked, 20)


if __name__ == '__main__':
    unittest.main(verbosity=2)
