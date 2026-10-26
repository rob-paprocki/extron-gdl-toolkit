"""A retarget must scale every page's CANVAS, not just its controls.

The bug this pins: `retarget --scale` scaled the controls and emitted no page
size at all, and `Apply-GdlEdits.ps1` made up the difference by setting every
page AND popup to the new screen size. That is right for a full-canvas popup
and wrong for any other, and it went unnoticed for two reasons:

  * a standard popup blown up to the screen still holds its scaled controls,
    so nothing overflowed, and the build was verified by where its controls
    landed - no popup's size was compared. The client fixture's 16 standard
    popups, 136x496 to 995x800, were every one resized;
  * `check()`'s overflow test, the one whose docstring calls it "the check that
    makes retargeting safe to offer", skipped popups outright
    (`if pg['kind'] != 'page': continue`). Popups are the only place a canvas
    and the screen are allowed to disagree, so that is the only place the check
    could ever have fired.

What a popup's authored size means is settled by the corpus: every built
layout.json reports each popup at its authored size, every modal is the
screen, and no standard popup is - 10 of Afterburn 1035's are 880x525. Forcing
a standard popup to the screen size turns it into a full-screen page in the
shipped file.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import MAIN_CLIENT, needs_client  # noqa: E402

from gdl.edit import Edits
from gdl.project import Project

FIXTURE = os.path.join('fixtures', 'gdl',
                       'client-boardroom-2.0.0.gdl')
RETARGET = {'edits': [{'op': 'retarget', 'model': 'TLP1535M', 'scale': True}]}


def plan_for(spec, path):
    ed = Edits(spec, path)
    plan, errors, warnings = ed.check()
    return ed, plan, errors, warnings


@needs_client(MAIN_CLIENT)
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


@needs_client(MAIN_CLIENT)
class TestSmallPopupsSurvive(unittest.TestCase):
    """A standard popup smaller than the screen, at Extron's own numbers.

    The fixture's own standard popups are smaller than the screen too; this
    splices in one at Afterburn 1035's 880x525, so the numbers the tests assert
    are fixed whatever the fixture holds.
    """

    def setUp(self):
        self.ed, self.plan, self.errors, _ = plan_for(RETARGET, FIXTURE)
        # Splice in a small popup alongside the real pages, so the op walk and
        # the overflow check both see it exactly as they would a real one.
        self.ed.pages = list(self.ed.pages) + [{
            'kind': 'popup', 'id': 999999, 'name': 'Small Card', 'modal': False,
            'size': (880, 525),
            'controls': [{'obj_id': 1, 'id': 1, 'name': 'Body', 'type': 'PBButton',
                          'caption': None, 'caption_in': None, 'rect': (0, 0, 880, 525)}],
        }]
        self.plan, self.errors, _ = self.ed.check()
        self.small = next(p for p in self.plan['pages'] if p['name'] == 'Small Card')

    def test_a_small_popup_is_not_promoted_to_full_screen(self):
        _, new = self.ed._resize
        self.assertNotEqual(self.small['size'], list(new),
                            'an 880x525 standard popup was resized to the whole screen')

    def test_it_keeps_its_proportions(self):
        old, new = self.ed._resize
        sx, sy = new[0] / old[0], new[1] / old[1]
        self.assertEqual(self.small['size'], [round(880 * sx), round(525 * sy)])

    def test_its_contents_still_fit(self):
        self.assertEqual(
            [e for e in self.errors if 'Small Card' in e], [],
            'a control that filled the old popup must still fill the new one')


@needs_client(MAIN_CLIENT)
class TestOverflowIsCaughtOnPopups(unittest.TestCase):
    """The check has to be able to fail, or passing it means nothing."""

    def test_a_control_outside_a_popup_is_reported(self):
        ed, _, _, _ = plan_for(RETARGET, FIXTURE)
        ed.pages = list(ed.pages) + [{
            'kind': 'popup', 'id': 999998, 'name': 'Bad Card', 'modal': False,
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


GREENROOM = 'client-greenroom-1.1.0.gdl'


@needs_client(GREENROOM)
class TestTheOldCanvasIsTheScreen(unittest.TestCase):
    """The factors come from the panel's screen, not from its largest control.

    The old size was taken as the largest control on a standard page, on the
    reading that something always fills the screen. On this fixture the
    largest is 1185x269 on a 1280x800 screen, so a retarget to a 1535 scaled
    by 1.62 and 4.01, put controls at y=2863 on a 1080-high panel, grew every
    canvas by the same wrong factors - and the overflow check, measuring
    against those canvases, reported nothing.
    """

    def setUp(self):
        from _corpus import client
        self.ed, self.plan, self.errors, _ = plan_for(RETARGET, client(GREENROOM))

    def test_the_factors_are_new_screen_over_old_screen(self):
        self.assertEqual(self.ed._resize, ((1280, 800), (1920, 1080)))
        self.assertEqual(self.ed._scale, (1.5, 1.35))

    def test_every_standard_page_lands_on_the_new_screen(self):
        std = [p for p in self.plan['pages'] if p['kind'] == 'page']
        self.assertTrue(std)
        self.assertEqual({tuple(p['size']) for p in std}, {(1920, 1080)})

    def test_every_scaled_control_is_on_the_new_screen(self):
        for o in self.plan['controls']:
            f = o['fields']
            self.assertLessEqual(f['topField'] + f['heightField'], 1080, o)
        self.assertEqual(self.errors, [])

    def test_a_page_canvas_that_misses_the_screen_is_an_error(self):
        """The guard that would have caught it: a standard page IS the panel,
        so one planned at any other size than the new screen means the factors
        are wrong, whatever the overflow check says."""
        self.ed._screen_size = lambda: (1185, 269)
        _, errors, _ = self.ed.check()
        self.assertTrue([e for e in errors if '1920x1080' in e and 'screen' in e], errors)


@needs_client(MAIN_CLIENT)
class TestAnUnscaledRetargetSizesEveryPage(unittest.TestCase):
    """Without `scale` the controls stay put, but the pages still change size:
    a page that was the screen becomes the new one, and a popup authored at its
    own size keeps it. Planned explicitly, or the applier falls back to
    setting every page AND popup to the screen - the rule that turned a
    standard popup into a full-screen page - and check() measured popups
    against a canvas the applier was not going to give them."""

    def setUp(self):
        self.ed, self.plan, self.errors, _ = plan_for(
            {'edits': [{'op': 'retarget', 'model': 'TLP1535M'}]}, FIXTURE)

    def test_every_sized_page_gets_a_size(self):
        want = {pg['id'] for pg in self.ed.pages if None not in pg['size']}
        self.assertEqual({p['page'] for p in self.plan['pages']}, want)

    def test_a_screen_sized_canvas_becomes_the_new_screen_and_any_other_stays(self):
        for p in self.plan['pages']:
            want = [1920, 1080] if p['was'] == [1280, 800] else p['was']
            self.assertEqual(p['size'], want, p['name'])
        self.assertTrue([p for p in self.plan['pages'] if p['size'] == p['was']],
                        'the fixture has no standard popup - the test is vacuous')


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import seed, usable  # noqa: E402


class TestExtronsOwnTemplateIfPresent(unittest.TestCase):
    """Ground truth, skipped when the seed is not available.

    The seed is in the repo under seeds/, through Git LFS, so this runs on any
    clone that has pulled LFS objects - no GUI Designer install needed. It is
    the test that actually proves the premise.
    """

    SEED = seed('Afterburn 1035.gdl')

    def setUp(self):
        if not usable(self.SEED):
            self.skipTest(f'Afterburn seed not available at {self.SEED} '
                          f'(run `git lfs pull`)')

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
