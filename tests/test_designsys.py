"""The design systems published to Claude Design (gdl/designsys).

Two contracts. The Design System page silently DROPS what it cannot read - a
token name with a space, a color it does not parse, a family written as a map -
so the tokens are checked against its grammar here, where a drop is a failure.
And the components carry spec fields for gdl.design, so every token, border
and type style a profile names has to be one the spec and the seed can build.
"""
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from _corpus import usable  # noqa: E402
from gdl import designsys  # noqa: E402
from gdl.spec import BORDERS, KIND_TYPE, MIN_BODY_POINT_SIZE  # noqa: E402

REPO = os.path.dirname(HERE)
COLOR = re.compile(r'^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$|^\{[A-Za-z0-9][A-Za-z0-9_.-]*\}$')


class TestTokens(unittest.TestCase):
    def setUp(self):
        self.p = designsys.load('afterburn')
        self.t = designsys.tokens(self.p)

    def test_every_family_but_type_is_a_list(self):
        for fam, v in self.t.items():
            if fam in ('name', 'version', 'type'):
                continue
            self.assertIsInstance(v['tokens'], list, fam)

    def test_names_are_legal_and_used_once(self):
        seen = []
        for fam, v in self.t.items():
            if fam in ('name', 'version', 'type'):
                continue
            for tok in v['tokens']:
                self.assertRegex(tok['name'], designsys.NAME)
                self.assertTrue(tok.get('usage'), f"{tok['name']} has no usage note")
                seen.append(tok['name'])
        self.assertEqual(len(seen), len(set(seen)), 'a duplicate name drops')

    def test_colors_parse_in_every_scheme(self):
        names = {c['name'] for c in self.t['color']['tokens']}
        ids = [th['id'] for th in self.t['color']['themes']]
        for c in self.t['color']['tokens']:
            values = c['value'].values() if isinstance(c['value'], dict) else [c['value']]
            for v in values:
                self.assertRegex(v, COLOR, c['name'])
                if v.startswith('{'):
                    self.assertIn(v[1:-1], names, f"{c['name']} aliases a missing token")
            if isinstance(c['value'], dict):
                self.assertEqual(set(c['value']), set(ids), f"{c['name']} misses a scheme")

    def test_type_styles_are_legal(self):
        for g in self.t['type']['groups']:
            self.assertIn(g['family'], self.t['type']['families'])
            for s in g['styles']:
                self.assertRegex(s['name'], designsys.NAME)
                self.assertRegex(s['fontSize'], r'^\d+(\.\d+)?px$')


class TestProfile(unittest.TestCase):
    """What the components carry has to be something the spec can build."""

    def setUp(self):
        self.p = designsys.load('afterburn')
        self.colors = {c['name'] for c in self.p['colors']}

    def test_afterburn_matches_the_published_guide(self):
        # docs/design-rules.md section 4.
        v = {c['name']: c['value'] for c in self.p['colors']}
        self.assertEqual(v['page'], '#242634')
        self.assertEqual(v['raised'], '#37394E')
        self.assertEqual(v['text-secondary'], '#BABCCE')
        self.assertEqual(v['accent']['orange'], '#D69B61')
        self.assertEqual(v['accent-2']['orange'], '#626ACF')

    def test_every_border_is_one_the_spec_knows(self):
        for key, b in self.p['borders'].items():
            self.assertIn(key, BORDERS)
            self.assertEqual(BORDERS[key], b['resource'], key)

    def test_everything_a_look_names_exists(self):
        for name, v in self.p['buttons'].items():
            for look in [v['look']] + v['states']:
                for k in ('fill', 'stroke', 'color'):
                    if k in look:
                        self.assertIn(look[k], self.colors, f'{name}.{k}')
                if 'border' in look:
                    self.assertIn(look['border'], self.p['borders'], name)
        types = {t['name'] for t in self.p['type']}
        for kind, d in self.p['defaults'].items():
            for k, v in d.items():
                if k in ('fill', 'stroke', 'color', 'value', 'thumb_color', 'background'):
                    self.assertIn(v, self.colors, f'defaults.{kind}.{k}')
                if k == 'border':
                    self.assertIn(v, self.p['borders'], f'defaults.{kind}')
                if k == 'type':
                    self.assertIn(v, types, f'defaults.{kind}')

    def test_no_type_style_is_under_the_checked_minimum(self):
        """gdl.spec check refuses text under 14 pt, so offering it would design
        panels that cannot be built. Afterburn's own small buttons are 13."""
        for t in self.p['type']:
            self.assertGreaterEqual(t['pt'], MIN_BODY_POINT_SIZE, t['name'])

    def test_button_variants_give_feedback(self):
        for name, v in self.p['buttons'].items():
            looks = [json.dumps({k: s[k] for k in s if k != 'name'}, sort_keys=True)
                     for s in v['states']]
            self.assertEqual(len(looks), len(set(looks)), f'{name} states look alike')

    def test_the_seed_can_author_the_font(self):
        seed = os.path.join(REPO, self.p['seed'])
        if not usable(seed):
            self.skipTest('seed not present (git lfs pull)')
        from gdl.project import Project
        self.assertIn(self.p['font']['family'], Project.open(seed).font_resource_names())


class TestKit(unittest.TestCase):
    """Extron's resource-kit names, read into an icon and a look. The kit
    spells them several ways, and a few wrongly."""

    def test_kit_file_names_parse_to_icon_and_look(self):
        for stem, want in (
                ('laptop_nsel', ('laptop', 'off')),
                ('laptop-orange_sel', ('laptop', 'orange')),
                ('help-orange-sel', ('help', 'orange')),
                ('speaker-volume-periwinkle_3', ('speaker-volume_3', 'periwinkle')),
                ('power', ('power', 'plain')),
                ('stop_sel', ('stop', 'sel')),
                ('record_red_sel', ('record', 'red')),
                ('make-call-orange_connected', ('make-call_connected', 'orange')),
                # Selected, though the suffix says otherwise; and misspelled.
                ('dual-display-1-gold_nsel', ('dual-display-1', 'gold')),
                ('disc-ligh-blue_sel', ('disc', 'light-blue'))):
            self.assertEqual(designsys.kit_look(stem), want, stem)

    def test_two_files_that_read_alike_keep_the_selected_one(self):
        p = designsys.load('afterburn')
        if not designsys.kit_root(p):
            self.skipTest("Extron's Afterburn kit is not installed here")
        # 1224x344_record_red.png and 1224x344_record_red_sel.png both read
        # as record/red; a state asks for the selected one.
        looks = designsys.kit_index(p)['files']['1224x344']['record']
        self.assertEqual(looks['red'], '1224x344_record_red_sel.png')

    def test_every_scheme_has_its_slider_thumb(self):
        """Drawn from the kit, not as a circle the size of its box: the kit's
        circle is 65% of it, and a full-box one was half as wide again as the
        panel's."""
        p = designsys.load('afterburn')
        if not designsys.kit_root(p, 'thumbs'):
            self.skipTest("Extron's Afterburn kit is not installed here")
        art = designsys.thumb_art(p)
        self.assertEqual(sorted(art), sorted(s['id'] for s in p['schemes']))
        self.assertTrue(all(v.startswith('data:image/webp;base64,') for v in art.values()))

    def test_a_build_without_the_kit_says_so(self):
        """Otherwise it looks like any other build, and publishes a system
        with no icons."""
        import contextlib
        import io
        p = designsys.load('afterburn')
        p['kit'] = dict(p['kit'], root='No Such Kit', thumbs='No Such Kit')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            designsys.bundle(p, art=False)
        self.assertIn('kit is not installed here', out.getvalue())

    def test_a_toggle_offers_only_toggles(self):
        p = designsys.load('afterburn')
        if not designsys.kit_root(p):
            self.skipTest("Extron's Afterburn kit is not installed here")
        names = designsys.icon_names(p)
        self.assertEqual(names['toggle'], ['toggle-1', 'toggle-2'])
        self.assertNotIn('toggle-1', names['list'])
        self.assertIn('call_connected', names['icon'])


class TestBundle(unittest.TestCase):
    def setUp(self):
        self.p = designsys.load('afterburn')
        self.js = designsys.bundle(self.p)

    def test_header_names_every_component(self):
        head = json.loads(re.match(r'/\* @ds-bundle: (\{.*?\}) \*/', self.js).group(1))
        self.assertEqual(head['namespace'], self.p['namespace'])
        self.assertEqual([c['name'] for c in head['components']],
                         [n for n, _, _ in designsys.COMPONENTS])

    def test_it_is_a_classic_script_that_can_be_inlined(self):
        self.assertNotRegex(self.js, re.compile(r'</script|<!--', re.I))
        self.assertIsNone(re.search(r'^\s*(import|export)\s', self.js, re.M))
        self.assertNotIn('eval(', self.js)

    def test_the_profile_is_in_the_code_not_a_comment(self):
        self.assertIn('var P = {"template":', self.js)

    def test_every_kind_it_emits_is_a_spec_kind(self):
        kinds = set(re.findall(r"kind: '([a-z_]+)'", self.js))
        kinds |= set(re.findall(r"track\('([a-z]+)'", self.js))
        self.assertIn('slider', kinds)
        for k in kinds - {'page', 'popup'}:
            self.assertIn(k, KIND_TYPE, k)


class TestBuild(unittest.TestCase):
    def test_a_new_system_is_complete(self):
        with tempfile.TemporaryDirectory() as d:
            written = designsys.build('afterburn', d, '2026-09-24T10:00:00Z')
            self.assertIn('project/README.md', written)
            self.assertIn('project/components/Cover/preview.html', written)
            with open(os.path.join(d, 'project', 'design-system.json'), encoding='utf-8') as fh:
                idx = json.load(fh)
            self.assertEqual(idx['createdOnFiles'], {'v': 1, 'at': '2026-09-24T10:00:00Z'})
            self.assertEqual(idx['namespace'], 'ExtronAfterburn')
            for n, _, _ in designsys.COMPONENTS:
                self.assertIn(f'project/components/{n}/README.md', written)
                with open(os.path.join(d, 'project', 'components', n, 'preview.html'),
                          encoding='utf-8') as fh:
                    self.assertTrue(fh.readline().startswith('<!-- @dsCard'), n)

    def test_the_readme_says_help_is_a_modal(self):
        """Extron's own templates draw Help, confirmations and a room's control
        subsets as full-screen modals over the page; a page flip is for a mode
        of the room. Left unsaid, Claude Design drew Help as a page."""
        text = designsys.readme(designsys.load('afterburn'))
        popups = next(line for line in text.splitlines() if line.startswith('- **Popups.**'))
        self.assertIn('Help', popups)
        self.assertIn('modal', popups)
        # The owner's rule, unchanged: nothing forces a confirmation.
        self.assertIn('not a rule', popups)

    def test_a_revision_keeps_the_pages_keys(self):
        with tempfile.TemporaryDirectory() as d:
            old = {'createdOnFiles': {'v': 1, 'at': 'then'}, 'sections': {'x': 'y'},
                   'assetGroups': {'Logos': {}}, 'title': 'Renamed by someone'}
            designsys.build('afterburn', d, 'now', existing=old)
            with open(os.path.join(d, 'project', 'design-system.json'), encoding='utf-8') as fh:
                idx = json.load(fh)
            self.assertEqual(idx['createdOnFiles']['at'], 'then')
            self.assertEqual(idx['sections'], {'x': 'y'})
            self.assertEqual(idx['lastChange']['at'], 'now')


if __name__ == '__main__':
    unittest.main(verbosity=2)
