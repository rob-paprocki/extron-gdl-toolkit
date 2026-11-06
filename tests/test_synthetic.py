"""The synthetic fixture: its spec, its build, its snapshots and their pins.

tests/data/synthetic/ is the render baseline's project
(tests/data/synthetic/README.md). These hold its parts to one another: the
spec to the script that writes it, the build to the spec, each page and popup
of the build to the snapshot GUI Designer exported of it, and every picture to
the hash the public copy's check pins it by.
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from _corpus import (SYNTHETIC, SYNTHETIC_DIR, SYNTHETIC_SNAPSHOTS, SYNTHETIC_SPEC,  # noqa: E402
                     needs_synthetic, seed, usable)

ID_RE = re.compile(r'_Id(\d+)\.png$')


class TestTheSpec(unittest.TestCase):
    def test_it_is_what_its_script_writes(self):
        """synthetic.json is built and committed; make_synthetic.py is how it
        was written. One edited without the other is a fixture nobody can
        rebuild."""
        sys.path.insert(0, SYNTHETIC_DIR)
        try:
            import make_synthetic
        finally:
            sys.path.remove(SYNTHETIC_DIR)
        with open(SYNTHETIC_SPEC, encoding='utf-8') as fh:
            self.assertEqual(json.load(fh), json.loads(json.dumps(make_synthetic.spec())))

    def test_it_checks_clean_with_no_kit_here(self):
        """Its art is its own, beside it ('./art/...'), so it checks on a host
        with no Extron kit and no GUI Designer."""
        from gdl.spec import Panel
        p = Panel.load(SYNTHETIC_SPEC)
        self.assertEqual(p.check(), [])
        for name, f in p.images.items():
            self.assertTrue(f.startswith(SYNTHETIC_DIR) and os.path.exists(f), (name, f))

    def test_the_captions_it_cuts_are_the_two_its_snapshots_show_cut(self):
        """Its Type Sizes and Wrapping pages set captions near their boxes'
        edges - the bold ones on Wrapping a few px inside them, by design -
        and GUI Designer cuts two: Italic40 to 'Type 40 Itali', and LongWord
        split over three lines. With its `caption_fit` off taken away, the
        check names those two and none of the rest."""
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; a caption is measured with gdl.compose')
        from gdl.spec import Panel
        with open(SYNTHETIC_SPEC, encoding='utf-8') as fh:
            spec = json.load(fh)
        self.assertEqual(spec.pop('caption_fit'), 'off')
        p = Panel.load(SYNTHETIC_SPEC)
        p = Panel(dict(spec, images=p.images))
        said = p.check()
        self.assertEqual(len(said), 2, said)
        self.assertTrue(said[0].startswith("page 'Type Sizes' Italic40: GUI Designer shows 'Type 40 Itali'"), said)
        self.assertTrue(said[1].startswith("page 'Wrapping' LongWord: GUI Designer breaks "
                                           "'Abcdefghijklmnopqrstuvwxyz' across lines"), said)

    def test_its_words_are_generic(self):
        """No client name, room or job: the fixture exists to carry none."""
        from gdl.spec import Panel
        p = Panel.load(SYNTHETIC_SPEC)
        names = {pg['name'] for pg in p.pages + p.popups}
        self.assertIn('Start', names)
        self.assertNotIn('client', json.dumps(p.spec).lower())


@needs_synthetic()
class TestTheBuild(unittest.TestCase):
    def setUp(self):
        from gdl.container import open_payload
        self.j = json.loads(open_payload(SYNTHETIC).read('layout.json'))

    def test_every_page_and_popup_the_spec_names_is_built(self):
        from gdl.spec import Panel
        p = Panel.load(SYNTHETIC_SPEC)
        built = {pg['Name'] for pg in self.j['Pages'] + self.j['PopupPages']}
        self.assertEqual({pg['name'] for pg in p.pages + p.popups} - built, set())
        # And nothing of the seed's but GUI Designer's own Offline Page.
        self.assertEqual(built - {pg['name'] for pg in p.pages + p.popups}, {'Offline Page'})

    def test_every_control_type_the_renderer_draws_is_in_it(self):
        kinds = {c['__type'].split(':')[0] for pg in self.j['Pages'] + self.j['PopupPages']
                 for c in pg.get('Controls') or []}
        for k in ('PBButton', 'PBLabel', 'PBShape', 'PBLine', 'PBImage', 'PBSlider',
                  'PBDateTime', 'PBPopupPageReference'):
            self.assertIn(k, kinds)

    def test_it_verifies_against_its_spec(self):
        """New-GdlPanel.ps1 built it only because verify_built passed; it must
        go on passing, or the verifier has changed under a known-good build.
        Planned against the seed it was built on, as the build was."""
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; verify_built imports the compositor')
        donor = seed('Afterburn 1035.gdl')
        if not usable(donor):
            self.skipTest('seeds/Afterburn 1035.gdl is not pulled from Git LFS here')
        import subprocess
        d = tempfile.mkdtemp()
        plan = os.path.join(d, 'plan.json')
        r = subprocess.run([sys.executable, '-m', 'gdl.spec', 'plan', SYNTHETIC_SPEC, plan,
                            '--donor', donor], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = subprocess.run([sys.executable, os.path.join(HERE, 'verify_built.py'), plan, SYNTHETIC],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-4000:] + r.stderr[-2000:])
        # Its two cut captions, said as its spec's caption_fit off asks.
        cut = [ln for ln in r.stdout.splitlines() if 'CAPTION CUT' in ln]
        self.assertEqual(len(cut), 2, r.stdout[-4000:])

    def test_the_build_cuts_the_captions_its_spec_check_names(self):
        """verify_built reads the built layout.json in the faces the built
        file carries, as the spec check reads the spec: the same two, refused
        where the plan does not turn the rule off."""
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; verify_built imports the compositor')
        sys.path.insert(0, HERE)
        try:
            import verify_built
        finally:
            sys.path.remove(HERE)
        from gdl.spec import Panel
        plan = Panel.load(SYNTHETIC_SPEC).plan()
        self.assertEqual(plan.pop('caption_fit'), 'off')
        pages = {p['Name']: p for p in self.j['Pages']}
        popups = {p['Name']: p for p in self.j['PopupPages']}
        problems, notes, n = verify_built.check_captions(plan, plan['pages'], pages, 'page', SYNTHETIC)
        self.assertEqual([m.split(':')[0] for m in problems], ["page 'Type Sizes' 'Italic40'", "page 'Wrapping' 'LongWord'"])
        self.assertIn("shows 'Type 40 Itali'", problems[0])
        self.assertGreater(n, 100)
        problems, notes, n = verify_built.check_captions(plan, plan['popups'], popups, 'popup', SYNTHETIC)
        self.assertEqual(problems, [])
        plan['caption_fit'] = 'off'
        problems, notes, _ = verify_built.check_captions(plan, plan['pages'], pages, 'page', SYNTHETIC)
        self.assertEqual(problems, [])
        self.assertEqual(len(notes), 2, notes)


@needs_synthetic()
class TestTheSnapshots(unittest.TestCase):
    def test_each_page_and_popup_has_one_under_its_own_name(self):
        """What tests/score.py matches on: '<page name>_Id<page ID>.png'."""
        from gdl.container import open_payload
        j = json.loads(open_payload(SYNTHETIC).read('layout.json'))
        pages = {pg['ID']: pg['Name'] for pg in j['Pages'] + j['PopupPages']}
        shots = {}
        for fn in os.listdir(SYNTHETIC_SNAPSHOTS):
            m = ID_RE.search(fn)
            self.assertTrue(m, fn)
            shots[int(m.group(1))] = fn[:m.start()]
        self.assertEqual(shots, pages)

    def test_the_baseline_names_every_snapshot(self):
        with open(os.path.join(ROOT, 'tests', 'baseline-synthetic.json'), encoding='utf-8') as fh:
            baseline = json.load(fh)
        self.assertEqual(set(baseline), set(os.listdir(SYNTHETIC_SNAPSHOTS)))


class TestThePublicCopysPins(unittest.TestCase):
    """Every picture here reaches the public copy only pinned by the hash of
    the bytes a person looked at (tools/public_sync.py BINARY_OK): a snapshot
    re-exported, or art re-drawn, is refused there until someone looks again."""

    def test_every_png_is_pinned_at_its_hash(self):
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        try:
            import public_sync
        finally:
            sys.path.pop(0)
        found = 0
        for base, _, files in os.walk(SYNTHETIC_DIR):
            for f in files:
                if not f.endswith('.png'):
                    continue
                path = os.path.relpath(os.path.join(base, f), ROOT).replace(os.sep, '/')
                with open(os.path.join(base, f), 'rb') as fh:
                    digest = hashlib.sha256(fh.read()).hexdigest()
                want = public_sync.BINARY_OK.get(path)
                self.assertIsNotNone(want, f'{path} is not in BINARY_OK')
                self.assertIn(digest, (want,) if isinstance(want, str) else want, path)
                found += 1
        self.assertTrue(found)


if __name__ == '__main__':
    unittest.main(verbosity=2)
