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

# Every profile on disk, registered or not: a draft that cannot build must fail
# here rather than first at a build.
PROFILES = sorted(f[:-5] for f in os.listdir(os.path.join(REPO, 'gdl', 'designsys'))
                  if f.endswith('.json'))


def _each(case, test):
    for t in PROFILES:
        with case.subTest(template=t):
            test(designsys.load(t))


class TestTokens(unittest.TestCase):
    def test_every_family_but_type_is_a_list(self):
        def check(p):
            for fam, v in designsys.tokens(p).items():
                if fam in ('name', 'version', 'type'):
                    continue
                self.assertIsInstance(v['tokens'], list, fam)
        _each(self, check)

    def test_names_are_legal_and_used_once(self):
        def check(p):
            seen = []
            for fam, v in designsys.tokens(p).items():
                if fam in ('name', 'version', 'type'):
                    continue
                for tok in v['tokens']:
                    self.assertRegex(tok['name'], designsys.NAME)
                    self.assertTrue(tok.get('usage'), f"{tok['name']} has no usage note")
                    seen.append(tok['name'])
            self.assertEqual(len(seen), len(set(seen)), 'a duplicate name drops')
        _each(self, check)

    def test_colors_parse_in_every_scheme(self):
        def check(p):
            t = designsys.tokens(p)
            names = {c['name'] for c in t['color']['tokens']}
            ids = [th['id'] for th in t['color']['themes']]
            for c in t['color']['tokens']:
                values = c['value'].values() if isinstance(c['value'], dict) else [c['value']]
                for v in values:
                    self.assertRegex(v, COLOR, c['name'])
                    if v.startswith('{'):
                        self.assertIn(v[1:-1], names, f"{c['name']} aliases a missing token")
                if isinstance(c['value'], dict):
                    self.assertEqual(set(c['value']), set(ids), f"{c['name']} misses a scheme")
        _each(self, check)

    def test_type_styles_are_legal(self):
        def check(p):
            t = designsys.tokens(p)
            for g in t['type']['groups']:
                self.assertIn(g['family'], t['type']['families'])
                for s in g['styles']:
                    self.assertRegex(s['name'], designsys.NAME)
                    self.assertRegex(s['fontSize'], r'^\d+(\.\d+)?px$')
        _each(self, check)


class TestEveryProfile(unittest.TestCase):
    """What the components carry has to be something the spec can build - for
    every template, not only the one that happens to be finished."""

    def test_every_border_is_one_the_spec_knows(self):
        def check(p):
            for key, b in p['borders'].items():
                self.assertIn(key, BORDERS)
                self.assertEqual(BORDERS[key], b['resource'], key)
        _each(self, check)

    def test_everything_a_look_names_exists(self):
        def check(p):
            colors = {c['name'] for c in p['colors']}
            for name, v in p['buttons'].items():
                for look in [v['look']] + v['states']:
                    for k in ('fill', 'stroke', 'color'):
                        if k in look and look[k] != 'none':
                            self.assertIn(look[k], colors, f'{name}.{k}')
                    if 'border' in look:
                        self.assertIn(look['border'], p['borders'], name)
            types = {t['name'] for t in p['type']}
            for kind, d in p['defaults'].items():
                for k, v in d.items():
                    if k in ('fill', 'stroke', 'color', 'value', 'thumb_color', 'background'):
                        self.assertIn(v, colors, f'defaults.{kind}.{k}')
                    if k == 'border':
                        self.assertIn(v, p['borders'], f'defaults.{kind}')
                    if k == 'type':
                        self.assertIn(v, types, f'defaults.{kind}')
                    if k in ('thumb', 'track'):
                        self.assertIsInstance(v, (int, float), f'defaults.{kind}.{k} is a size')
        _each(self, check)

    def test_no_type_style_is_under_the_checked_minimum(self):
        """gdl.spec check refuses text under 14 pt, so offering it would design
        panels that cannot be built. Afterburn's own small buttons are 13."""
        def check(p):
            for t in p['type']:
                self.assertGreaterEqual(t['pt'], MIN_BODY_POINT_SIZE, t['name'])
        _each(self, check)

    def test_button_variants_give_feedback(self):
        def check(p):
            for name, v in p['buttons'].items():
                looks = [json.dumps({k: s[k] for k in s if k != 'name'}, sort_keys=True)
                         for s in v['states']]
                self.assertEqual(len(looks), len(set(looks)), f'{name} states look alike')
        _each(self, check)

    def test_the_seed_can_author_the_font(self):
        from gdl.project import Project

        def check(p):
            seed = os.path.join(REPO, p['seed'])
            if not usable(seed):
                self.skipTest('seed not present (git lfs pull)')
            self.assertIn(p['font']['family'], Project.open(seed).font_resource_names())
        _each(self, check)

    def test_the_readme_names_only_what_the_profile_has(self):
        """Mach's README once told designers to use Afterburn's `icon`, `list`
        and `toggle` variants, and to read its icon anatomy off tokens Mach
        does not have."""
        def check(p):
            docs = designsys.component_docs(p)
            previews = designsys.previews(p)
            text = '\n'.join([designsys.readme(p)] + list(docs.values()) + list(previews.values()))
            for v in re.findall(r'variant(?:="|: ")([^"]+)"', text):
                self.assertIn(v, p['buttons'], f'the docs name variant {v!r}')
            for t in re.findall(r'type(?:="|: ")([^"]+)"', text):
                self.assertIn(t, {s['name'] for s in p['type']}, f'the docs name type {t!r}')
            self.assertNotIn('(?)', text, 'the README reads a token the profile lacks')
            names = designsys.icon_names(p)
            for v, icon in re.findall(r'variant="([^"]+)" icon="([^"]+)"', text):
                # Without the kit a variant that claims icon families still has a key,
                # with an empty list, so `if names` is true and every icon reads missing.
                if any(names.values()):
                    self.assertIn(icon, names.get(v, []), f'{v} icon {icon!r}')
            # The icon prop's own line names this template's image variants.
            line = next(ln for ln in docs['Button'].splitlines() if ln.startswith('- `icon`'))
            line = re.sub(r'\(default `[^`]+`\)', '', line)
            for v in re.findall(r'`([a-z-]+)`', line):
                if v not in ('icon',):
                    self.assertIn(v, p['buttons'], f'the icon line names variant {v!r}')
        _each(self, check)

    def test_the_example_puts_a_header_source_on_the_page(self):
        """Shockwave's sources are tabs in the header, not in its video well:
        placed inside MainArea, its example tab landed 168,120 down and right."""
        text = designsys.readme(designsys.load('shockwave'))
        main = re.search(r'ExtronShockwave\.MainArea">(.*?)</x-import>\n  </x-import>', text, re.S)
        self.assertNotIn('name="Laptop"', main.group(1))
        self.assertIn('name="Laptop"', text)

    def test_every_profile_builds_a_system(self):
        def check(p):
            with tempfile.TemporaryDirectory() as d:
                written = designsys.build(p['template'].lower(), d, '2026-09-25T00:00:00Z')
            self.assertIn('project/README.md', written)
        _each(self, check)


class TestProfile(unittest.TestCase):
    """Afterburn's own facts."""

    def setUp(self):
        self.p = designsys.load('afterburn')

    def test_afterburn_matches_the_published_guide(self):
        # docs/design-rules.md section 4.
        v = {c['name']: c['value'] for c in self.p['colors']}
        self.assertEqual(v['page'], '#242634')
        self.assertEqual(v['raised'], '#37394E')
        self.assertEqual(v['text-secondary'], '#BABCCE')
        self.assertEqual(v['accent']['orange'], '#D69B61')
        self.assertEqual(v['accent-2']['orange'], '#626ACF')

    def test_a_level_is_as_wide_as_the_seeds_levels(self):
        """Build draws a Level over its whole box, so its `track` is its width
        across - and every Afterburn seed's Level is 15 px across, with the
        scheme's secondary accent (#626ACF, scheme 1) as its fill."""
        import glob
        from gdl.project import Project
        seeds = [f for f in glob.glob(os.path.join(HERE, '..', 'seeds', 'Afterburn*.gdl')) if usable(f)]
        # Only the 300M pair, the 320 and the 525 have a Level - the rest have
        # sliders - so a clone that pulled some seeds may have none to measure.
        if not any(usable(os.path.join(HERE, '..', 'seeds', f'Afterburn {s}.gdl'))
                   for s in ('300M Landscape', '300M Portrait', '320', '525')):
            self.skipTest('no Afterburn seed with a Level is here (git lfs pull)')
        across, bars = set(), set()
        for f in seeds:
            p = Project.open(f)
            for o in p.instances('PBLevel'):
                w, h = p.field(o, 'widthField'), p.field(o, 'heightField')
                across.add(min(w, h))
                c = p.color(p.field(o, 'gaugeFillColorField'))
                bars.add('#%02X%02X%02X' % (c['R'], c['G'], c['B']))
        self.assertTrue(across, 'no Level in any Afterburn seed')
        self.assertEqual(across, {self.p['defaults']['level']['track']})
        v = {c['name']: c['value'] for c in self.p['colors']}
        self.assertEqual(bars, {v[self.p['defaults']['level']['value']]['orange']})


class TestModels(unittest.TestCase):
    """The per-panel table the bundle carries: every model a profile's series
    serve, with its size, minimums, regions, art and seed."""

    def setUp(self):
        self.p = designsys.load('afterburn')
        self.m = designsys.models(self.p)

    def test_every_afterburn_model_resolves(self):
        from gdl.spec import panel_of, tier, touch_minimums, type_floor
        self.assertIn('TLP725T', self.m)
        for pid, row in self.m.items():
            with self.subTest(panel=pid):
                model, size = panel_of(pid)
                self.assertEqual(row['size'], list(size))
                self.assertEqual(row['tier'], tier(model))
                self.assertEqual((row['touch'], row['gap']), touch_minimums(model))
                self.assertEqual(row['floor'], type_floor(model))
                self.assertEqual(len(row['main']), 4)

    def test_a_panel_turned_from_its_models_canvas_is_a_row_of_its_own(self):
        """A canvas lists the 300M either way up, and Afterburn draws both: its
        300 Landscape series is the TLP300M-Landscape, on its own seed. Keyed
        by model, the table had room for one, and the Landscape row listed no
        model and no seed."""
        row = self.m['TLP300M-Landscape']
        self.assertEqual((row['series'], row['size'], row['rail_axis']),
                         ('Afterburn 300 Landscape Series', [480, 320], 'column'))
        self.assertEqual(row['seed'], 'seeds/Afterburn 300M Landscape.gdl')
        self.assertIn('kinds', self.p['panels']['Afterburn 300 Landscape Series'])
        self.assertEqual(self.m['TLP300M']['series'], 'Afterburn 300 Portrait Series')
        self.assertEqual(self.m['TLP300M']['seed'], 'seeds/Afterburn 300M Portrait.gdl')

    def test_the_design_panel_agrees_with_the_profile(self):
        """The profile's touch, spacing, size, popup and main area state the
        design panel; the table is not allowed a second opinion."""
        d = self.m[self.p['model']]
        self.assertEqual((d['touch'], d['gap']), (self.p['touch'], self.p['spacing']))
        self.assertEqual(d['size'], self.p['size'])
        self.assertEqual(d['popup'], self.p['popup'])
        self.assertEqual(d['main'], self.p['layout']['main'])
        self.assertEqual(d['seed'], self.p['seed'])

    def test_the_725_and_1230w_have_their_own_backgrounds(self):
        self.assertIn('5120x3000', self.m['TLP725T']['backgrounds']['grape']['file'])
        self.assertIn('9600x3600', self.m['TLP1230WTG']['backgrounds']['grape']['file'])
        self.assertEqual(self.m['TLP725T']['fit'], 'stretch')

    def test_no_two_series_claim_one_panel(self):
        """A model one series serves either way up is two panels; a model
        two series served on one canvas would be one row hiding another."""
        from gdl.spec import panel_id
        seen = {}
        for series, row in self.p['panels'].items():
            if series.startswith('_'):
                continue
            for m in row['models']:
                pid = panel_id(m, row['size'])
                self.assertNotIn(pid, seen, f'{pid} in {series} and {seen.get(pid)}')
                seen[pid] = series

    def test_no_720_row(self):
        """Afterburn has no 720 template; its only 800x480 one is a 5in hub."""
        self.assertNotIn('TLP720T', self.m)

    def test_the_table_agrees_with_the_install(self):
        """A row is the series the install draws its panel with - or, turned,
        the one it draws the panel's other way up with, where it draws none."""
        from gdl import templates
        if not templates.table():
            self.skipTest('no TemplateInfoTable.config')
        from gdl.spec import panel_of
        for pid, row in self.m.items():
            model, size = panel_of(pid)
            here = templates.template_for('Afterburn', model, size)
            if row.get('turned'):
                self.assertIsNone(here, pid)
                self.assertEqual(templates.template_for('Afterburn', model)['series'], row['series'], pid)
            else:
                self.assertEqual(here['series'], row['series'], pid)

    def test_a_seed_named_is_that_models_seed(self):
        from gdl.spec import panel_of
        from verify_seed import check_seed
        here = [m for m in ('TLP1035T', 'TLP725T', 'TLP525T', 'TLP320M', 'TLP300M', 'TLP300M-Landscape')
                if usable(os.path.join(REPO, self.m[m]['seed']))]
        if not here:
            self.skipTest('seeds not present (git lfs pull)')
        for pid in here:
            path = os.path.join(REPO, self.m[pid]['seed'])
            self.assertEqual(check_seed(path, panel_of(pid)[0], theme='Afterburn'), [], pid)

    def test_the_small_seeds_say_what_they_cannot_clone(self):
        self.assertFalse(self.m['TLP525T']['kinds']['slider'])
        self.assertTrue(self.m['TLP725T']['kinds']['slider'])
        self.assertFalse(self.m['TLP320M']['kinds']['popup'])
        self.assertEqual(self.m['TLP320M']['borders']['afterburn'], 'Afterburn - 7 Radius 2 Thick')


class TestATurnedPanelWithNoTemplate(unittest.TestCase):
    """The 520M, 521M, 535M, 835M and 1035M run either way up, and Extron draws
    none of them turned (docs/design-rules.md section 1). Each is its own
    series turned: Extron draws one panel both ways, the 300M, and its
    Landscape layout is its Portrait one transposed."""

    TURNED = ('TLP1035M-Portrait', 'TLP835M-Portrait', 'TLP535M-Portrait',
              'TLP520M-Portrait', 'TLC521M-Portrait')

    def setUp(self):
        self.m = designsys.models(designsys.load('afterburn'))

    @staticmethod
    def _turn(r):
        return None if r is None else [r[1], r[0], r[3], r[2]]

    def test_each_is_a_row_of_its_own_and_no_other_is(self):
        self.assertEqual(sorted(p for p, r in self.m.items() if r.get('turned')), sorted(self.TURNED))

    def test_its_regions_are_its_series_transposed(self):
        for pid in self.TURNED:
            own, row = self.m[pid.split('-')[0]], self.m[pid]
            with self.subTest(panel=pid):
                self.assertEqual(row['series'], own['series'])
                self.assertEqual(row['size'], own['size'][::-1])
                self.assertEqual(row['main'], self._turn(own['main']))
                self.assertEqual(row['rail'], self._turn(own['rail']))
                self.assertEqual(row['rail_axis'], {'column': 'row', 'row': 'column'}[own['rail_axis']])
                self.assertEqual(row['popup'], own['popup'][::-1] if own['popup'] else None)
                self.assertEqual((row['kinds'], row['borders']), (own['kinds'], own['borders']))
                self.assertEqual((row['dpi'], row['touch'], row['floor']), (own['dpi'], own['touch'], own['floor']))

    def test_the_rule_is_how_extron_draws_the_300m_both_ways(self):
        port, land = self.m['TLP300M'], self.m['TLP300M-Landscape']
        self.assertEqual(land['main'], self._turn(port['main']))
        self.assertEqual(land['rail'], self._turn(port['rail']))
        self.assertEqual((port['rail_axis'], land['rail_axis']), ('row', 'column'))
        self.assertEqual((port['popup'], land['popup']), (None, None))
        self.assertFalse(land.get('turned'))

    def test_it_has_no_art(self):
        """Extron draws none that way up; its 300M's landscape art is the
        portrait's shape transposed with the paint redrawn, which a rotation
        would not be."""
        for pid in self.TURNED:
            self.assertEqual(self.m[pid]['backgrounds'], {}, pid)

    def test_what_claude_design_reads_says_which_have_no_art(self):
        text = designsys._panels_props(designsys.load('afterburn'))
        self.assertIn('`TLP300M-Landscape`', text)
        plain = text[text.index('no template'):]
        self.assertIn('`TLP1035M-Portrait`', plain)
        self.assertNotIn('TLP300M-Landscape', plain)

    def test_a_series_with_no_rail_turns_to_none(self):
        """measure_series writes no rail band for a series whose main region
        fills its canvas, and the bundle draws such a panel; turned, it has
        none either."""
        import copy
        p = copy.deepcopy(designsys.load('afterburn'))
        s = p['panels']['Afterburn 535 Series']
        s['rail'], s['rail_axis'] = None, None
        row = designsys.models(p)['TLP535M-Portrait']
        self.assertEqual((row['rail'], row['rail_axis']), (None, None))

    def test_a_turned_seed_is_found_under_its_panel(self):
        import copy
        p = copy.deepcopy(designsys.load('afterburn'))
        p['panels']['Afterburn 1220 Series']['seeds']['TLP1035M-Portrait'] = 'seeds/X.gdl'
        m = designsys.models(p)
        self.assertEqual(m['TLP1035M-Portrait']['seed'], 'seeds/X.gdl')
        self.assertEqual(m['TLP1035M']['seed'], 'seeds/Afterburn 1035.gdl')
        self.assertIsNone(m['TLP835M-Portrait']['seed'])


class TestWhatTheRailSays(unittest.TestCase):
    """The Rail's README names, from the profile's own table, the series whose
    rail runs below the main region, those whose template draws none, and those
    whose seed builds no slider - so a theme's says what is true of its own."""

    def test_afterburns(self):
        text = designsys._panels_rail(designsys.load('afterburn'))
        self.assertIn('or below it, running across, on a panel too small to have one beside it '
                      '(the 320 and 300 Portrait Series).', text)
        self.assertIn('whose seed cannot build a slider - the 520, 320, 300 Portrait and 300 Landscape '
                      'Series -', text)
        self.assertNotIn('no rail band', text)

    def test_a_series_whose_template_draws_no_rail_band_is_named(self):
        import copy
        p = copy.deepcopy(designsys.load('afterburn'))
        for s in ('Afterburn 320 Series', 'Afterburn 535 Series'):
            p['panels'][s]['rail'], p['panels'][s]['rail_axis'] = None, None
        text = designsys._panels_rail(p)
        self.assertIn('(the 300 Portrait Series)', text)
        self.assertIn('The 535 and 320 Series draw no rail band - their templates keep', text)

    def test_machs(self):
        """Mach's 320 keeps nothing on screen from page to page; its 300 runs
        its rail along the bottom, and its seed builds a level, not a slider."""
        text = designsys._panels_rail(designsys.load('mach'))
        self.assertIn('The 320 Series draws no rail band - its template keeps', text)
        self.assertIn('beside it (the 300 Series).', text)
        self.assertIn('cannot build a slider - the 535, 520, 320 and 300 Series -', text)


class TestWhatTheLevelSays(unittest.TestCase):
    """The Level's README names, from the profile's own table, the series whose
    seeds carry no level to clone - where the canvas names a Level."""

    def test_afterburns(self):
        text = designsys._level_where(designsys.load('afterburn'))
        self.assertIn('on the 1220, 1020, 1720 and 1230 Series the seed carries a slider and no level - '
                      'the panel the canvas is drawn on among them - so a Level drawn for one of those panels '
                      'is named on the canvas: use a Slider there.', text)

    def test_machs(self):
        self.assertIn('on the 1220, 1020, 1520, 1720 and 720 Series the seed carries',
                      designsys._level_where(designsys.load('mach')))

    def test_nothing_without_a_table_or_a_seed_lacking_one(self):
        import copy
        p = copy.deepcopy(designsys.load('mach'))
        self.assertIn('Level', designsys.component_docs(p)['Level'])
        for s in p['panels'].values():
            if isinstance(s, dict) and s.get('kinds'):
                s['kinds']['level'] = True
        self.assertEqual(designsys._level_where(p), '')
        del p['panels']
        self.assertEqual(designsys._level_where(p), '')


class TestWhatThePageSays(unittest.TestCase):
    """The Page README says how a Page's own bars carry to other panels only
    for a system that draws them as controls; Afterburn's chrome is its
    background art."""

    def test_a_system_whose_bars_are_controls(self):
        text = designsys._panels_props(designsys.load('mach'))
        self.assertIn('On a large or mid-size panel other than the one drawn', text)
        self.assertIn('get bands of their own carved from main', text)

    def test_each_names_its_own_hubs(self):
        """Read off each table: Turbulence has a 520 hub and no 535."""
        self.assertIn('(the 520 and 535 Series)', designsys._panels_props(designsys.load('mach')))
        self.assertIn('(the 520 Series)', designsys._panels_props(designsys.load('turbulence')))

    def test_afterburns_says_nothing_of_bars(self):
        self.assertNotIn('edge to edge', designsys._panels_props(designsys.load('afterburn')))


class TestEveryThemesPanels(unittest.TestCase):
    """Every theme's per-panel table, measured by tests/measure_series.py: each
    panel resolves, the design panel agrees with the profile, no two series
    claim one panel, and the table agrees with the install."""
    THEMES = ('afterburn', 'mach', 'shockwave', 'turbulence')

    def test_every_profile_has_one(self):
        for t in self.THEMES:
            self.assertTrue(designsys.models(designsys.load(t)), t)

    def test_every_panel_resolves(self):
        from gdl.spec import panel_of, tier, touch_minimums, type_floor
        for t in self.THEMES:
            for pid, row in designsys.models(designsys.load(t)).items():
                with self.subTest(theme=t, panel=pid):
                    model, size = panel_of(pid)
                    self.assertEqual(row['size'], list(size))
                    self.assertEqual(row['tier'], tier(model))
                    self.assertEqual((row['touch'], row['gap']), touch_minimums(model))
                    self.assertEqual(row['floor'], type_floor(model))
                    self.assertEqual(len(row['main']), 4)

    def test_the_design_panel_agrees_with_the_profile(self):
        for t in self.THEMES:
            p = designsys.load(t)
            d = designsys.models(p)[p['model']]
            with self.subTest(theme=t):
                self.assertEqual((d['touch'], d['gap']), (p['touch'], p['spacing']))
                self.assertEqual(d['size'], p['size'])
                self.assertEqual(d['popup'], p['popup'])
                self.assertEqual(d['main'], p['layout']['main'])
                self.assertEqual(d['seed'], p['seed'])

    def test_no_two_series_claim_one_panel(self):
        from gdl.spec import panel_id
        for t in self.THEMES:
            seen = {}
            for series, row in designsys.load(t)['panels'].items():
                if series.startswith('_'):
                    continue
                for m in row['models']:
                    pid = panel_id(m, row['size'])
                    self.assertNotIn(pid, seen, f'{t}: {pid} in {series} and {seen.get(pid)}')
                    seen[pid] = series

    def test_the_table_agrees_with_the_install(self):
        from gdl import templates
        if not templates.table():
            self.skipTest('no TemplateInfoTable.config')
        from gdl.spec import panel_of
        for t in self.THEMES:
            p = designsys.load(t)
            for pid, row in designsys.models(p).items():
                model, size = panel_of(pid)
                here = templates.template_for(p['template'], model, size)
                with self.subTest(theme=t, panel=pid):
                    if row.get('turned'):
                        self.assertIsNone(here)
                        self.assertEqual(templates.template_for(p['template'], model)['series'], row['series'])
                    else:
                        self.assertEqual(here['series'], row['series'])

    def test_a_seed_named_is_that_models_seed(self):
        from gdl.spec import panel_of
        from verify_seed import check_seed
        checked = 0
        for t in ('mach', 'shockwave', 'turbulence'):
            p = designsys.load(t)
            for pid, row in designsys.models(p).items():
                if not row['seed'] or not usable(os.path.join(REPO, row['seed'])):
                    continue
                checked += 1
                with self.subTest(theme=t, panel=pid):
                    self.assertEqual(check_seed(os.path.join(REPO, row['seed']), panel_of(pid)[0],
                                                theme=p['template']), [])
        if not checked:
            self.skipTest('seeds not present (git lfs pull)')

    def test_a_profile_with_no_table_has_no_panels(self):
        """A theme whose profile has no `panels` yet - the next one Extron ships
        - draws its design panel alone, and its README says nothing of panels."""
        import copy
        p = copy.deepcopy(designsys.load('mach'))
        del p['panels']
        self.assertEqual(designsys.models(p), {})
        self.assertEqual(designsys._panels_props(p), '')
        self.assertEqual(designsys._panels_main(p), '')
        self.assertEqual(designsys._panels_group(p), '')
        self.assertEqual(designsys._panels_rail(p), ' Give it a position and size with its own style.')


class TestTheOtherThemesTables(unittest.TestCase):
    """What Mach's, Shockwave's and Turbulence's tables say that Afterburn's
    could not teach: art by its own name, wells, no rail at all."""

    def test_machs_300_fills_its_own_art_and_the_others_stretch_the_photographs(self):
        m = designsys.models(designsys.load('mach'))
        self.assertEqual((m['TLP300M']['fit'], m['TLP300M']['backgrounds']['sunset']),
                         ('fill', {'image': 'mach_bg_02.png', 'file': 'Mach/Backgrounds/320x480/320x480_mach-bg-02.png'}))
        self.assertEqual(m['TLP1035T']['backgrounds']['dome']['file'],
                         'Mach/Backgrounds/5472x3648/5472x3648_mach-bg-01.png')
        self.assertEqual(m['TLP1035T']['fit'], 'stretch')

    def test_the_320s_have_no_rail_and_machs_300_runs_its_along_the_bottom(self):
        for t in ('mach', 'shockwave', 'turbulence'):
            row = designsys.models(designsys.load(t))['TLP320M']
            self.assertEqual((row['rail'], row['rail_axis']), (None, None), t)
        m = designsys.models(designsys.load('mach'))
        self.assertEqual((m['TLP300M']['rail_axis'], m['TLP300M-Landscape']['rail_axis']), ('row', 'column'))
        self.assertTrue(m['TLP300M-Landscape']['turned'])

    def test_shockwaves_main_is_its_well_and_its_haze_is_at_each_size(self):
        m = designsys.models(designsys.load('shockwave'))
        self.assertEqual(m['TLP725T']['main'], [133, 90, 739, 430])
        self.assertEqual(m['TLP725T']['backgrounds']['haze']['file'], 'Shockwave/backgrounds/1024x600_bkgd.png')
        # The 535 stretches its template's own 800x480 haze, which the kit
        # has, under the name its seed carries; the 320's own 320x240 the kit
        # lacks, and the nearest shape it builds goes by its own name.
        self.assertEqual(m['TLP535M']['backgrounds']['haze'],
                         {'image': '800x480 bkgd.png', 'file': 'Shockwave/backgrounds/800x480 bkgd.png'})
        self.assertEqual(m['TLP320M']['backgrounds']['haze'],
                         {'image': '1280x800 bkgd.png', 'file': 'Shockwave/backgrounds/1280x800 bkgd.png'})

    def test_turbulences_art_is_one_size(self):
        m = designsys.models(designsys.load('turbulence'))
        self.assertEqual(m['TLP725T']['backgrounds']['corridor'], {'image': 'bkgd_pc.png', 'file': 'Turbulence/bkgd_pc.png'})


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

    def test_an_extracted_kit_names_its_extract_step(self):
        """Turbulence's art and Mach's slider are in neither the install nor a
        fresh vendor/ until `extract` has run, so saying only where kits live
        sends a builder looking in the wrong place."""
        import contextlib
        import io
        p = designsys.load('turbulence')
        p['kit'] = dict(p['kit'], root='No Such Kit', thumbs='No Such Kit')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            designsys.bundle(p, art=False)
        self.assertIn('python -m gdl.designsys extract turbulence', out.getvalue())

    def test_slider_art_the_machine_lacks_is_said(self):
        """With the buttons installed but not the slider's part of the kit, the
        system published with no rail or thumb art and said nothing - its
        sliders drawn plain on every canvas."""
        import contextlib
        import io
        p = designsys.load('mach')
        if not designsys.kit_root(p):
            self.skipTest("Extron's Mach kit is not installed here")
        p['kit'] = dict(p['kit'], thumbs='No Such Kit')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            designsys.bundle(p, art=False)
        self.assertIn('slider art', out.getvalue())
        self.assertIn('8x500_mach_track_bg@3x.png', out.getvalue())

    def test_a_toggle_offers_only_toggles(self):
        p = designsys.load('afterburn')
        if not designsys.kit_root(p):
            self.skipTest("Extron's Afterburn kit is not installed here")
        names = designsys.icon_names(p)
        self.assertEqual(names['toggle'], ['toggle-1', 'toggle-2'])
        self.assertNotIn('toggle-1', names['list'])
        self.assertIn('call_connected', names['icon'])

    def test_a_default_icon_does_not_narrow_the_offer(self):
        """Shockwave's `button` draws gray unless told otherwise; red, yellow
        and the rest are still its to offer."""
        p = designsys.load('shockwave')
        if not designsys.kit_root(p):
            self.skipTest("Extron's Shockwave kit is not installed here")
        names = designsys.icon_names(p)
        self.assertLessEqual({'gray', 'red', 'yellow', 'green', 'blue'}, set(names['button']))
        self.assertIn('laptop_white', names['source'])
        self.assertEqual(names['close'], ['close'])
        self.assertNotIn('close', names['square'])


class TestKitFiles(unittest.TestCase):
    def test_a_name_with_a_space_before_png_is_still_kit(self):
        """23 of Shockwave's kit files are named '... _sel .png'; the pattern
        that dropped them silently dropped real art."""
        m = designsys._KIT_FILE.match('440x440_help_yellow_sel .png')
        self.assertIsNotNone(m)
        self.assertEqual(m.groups(), ('440x440', 'help_yellow_sel'))

    def test_a_partial_kit_in_one_root_does_not_hide_the_rest(self):
        """Extracting Mach's slider art into vendor/ made vendor/.../Mach exist,
        and the kit then read only those 71 files and none of the install's."""
        import gdl.spec
        png = b'\x89PNG\r\n\x1a\n'
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            os.makedirs(os.path.join(a, 'Theme', 'Extracted'))
            os.makedirs(os.path.join(b, 'Theme', 'Icons'))
            for d, f in ((os.path.join(a, 'Theme', 'Extracted'), '440x440_thumb.png'),
                         (os.path.join(b, 'Theme', 'Icons'), '440x440_laptop.png'),
                         (os.path.join(b, 'Theme', 'Icons'), '440x440_thumb.png')):
                with open(os.path.join(d, f), 'wb') as fh:
                    fh.write(png)
            old = gdl.spec.RESOURCE_ROOTS
            gdl.spec.RESOURCE_ROOTS = (a, b)
            try:
                index = designsys.kit_index({'kit': {'root': 'Theme'}})
            finally:
                gdl.spec.RESOURCE_ROOTS = old
        self.assertEqual(sorted(index['files']['440x440']), ['laptop', 'thumb'])
        # The first root wins a name both have.
        self.assertEqual(index['paths']['440x440_thumb.png'], 'Theme/Extracted/440x440_thumb.png')

    def test_a_kit_can_draw_off_from_its_outlined_art(self):
        """Shockwave's pills rest dark with a colored ring (red_outline_nsel)
        and light when selected (red_sel); its plain red_nsel is a saturated
        solid no seed button rests in. Icon pills name it mid-stem
        (r_power_outline_red_nsel) and round ones before it
        (red_round_outline_nsel)."""
        import gdl.spec
        png = b'\x89PNG\r\n\x1a\n'
        names = ('1248x440_red_nsel.png', '1248x440_red_outline_nsel.png', '1248x440_red_sel.png',
                 '1248x440_red_round_outline_nsel.png', '1248x440_red_round_sel.png',
                 '1248x440_r_power_outline_red_nsel.png', '1248x440_r_power_red_sel.png',
                 '1248x440_gray_nsel.png', '1248x440_gray_sel.png',
                 '1248x440_outline_share-1b_blue_nsel.png', '1248x440_share-1b_blue_sel.png')
        with tempfile.TemporaryDirectory() as a:
            os.makedirs(os.path.join(a, 'Theme'))
            for f in names:
                with open(os.path.join(a, 'Theme', f), 'wb') as fh:
                    fh.write(png)
            old = gdl.spec.RESOURCE_ROOTS
            gdl.spec.RESOURCE_ROOTS = (a,)
            try:
                files = designsys.kit_index({'kit': {'root': 'Theme', 'outline_off': True}})['files']
            finally:
                gdl.spec.RESOURCE_ROOTS = old
        pills = files['1248x440']
        self.assertEqual(pills['red'], {'off': '1248x440_red_outline_nsel.png',
                                        'sel': '1248x440_red_sel.png'})
        self.assertEqual(pills['red_round']['off'], '1248x440_red_round_outline_nsel.png')
        self.assertEqual(pills['r_power_red']['off'], '1248x440_r_power_outline_red_nsel.png')
        self.assertEqual(pills['gray']['off'], '1248x440_gray_nsel.png')
        # 504x440's share buttons put it first.
        self.assertEqual(pills['share-1b_blue']['off'], '1248x440_outline_share-1b_blue_nsel.png')
        self.assertNotIn('outline_share-1b_blue', pills)

    def _index(self, kit, names):
        import gdl.spec
        png = b'\x89PNG\r\n\x1a\n'
        with tempfile.TemporaryDirectory() as a:
            for f in names:
                path = os.path.join(a, 'Theme', *f.split('/'))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'wb') as fh:
                    fh.write(png)
            old = gdl.spec.RESOURCE_ROOTS
            gdl.spec.RESOURCE_ROOTS = (a,)
            try:
                return designsys.kit_index({'kit': dict(kit, root='Theme')})
            finally:
                gdl.spec.RESOURCE_ROOTS = old

    def test_a_doubled_underscore_reads_as_one(self):
        """Shockwave's 1248x440_blue__round_outline_nsel.png is blue_round's."""
        files = self._index({'outline_off': True},
                            ['1248x440_blue__round_outline_nsel.png', '1248x440_blue_round_sel.png'])['files']
        self.assertEqual(files['1248x440'], {'blue_round': {
            'off': '1248x440_blue__round_outline_nsel.png', 'sel': '1248x440_blue_round_sel.png'}})

    def test_a_kit_can_name_a_file_its_pattern_misses(self):
        """Shockwave's modal Close is icons/440x440 White/white_close.png - no
        size prefix, so only a name in the profile reaches it."""
        index = self._index({'named': {'440x440': {'close': 'white_close.png'}}},
                            ['icons/440x440 White/white_close.png', '440x440_gray_nsel.png'])
        self.assertEqual(index['files']['440x440']['close'], {'plain': 'white_close.png'})
        self.assertEqual(index['paths']['white_close.png'], 'Theme/icons/440x440 White/white_close.png')

    def test_a_named_icon_can_have_a_file_per_look(self):
        """The seed's Close is a dark X at rest and a white one pressed."""
        index = self._index({'named': {'440x440': {'close': {'off': 'black_close.png',
                                                             'sel': 'white_close.png'}}}},
                            ['icons/440x440 Black/black_close.png', 'icons/440x440 White/white_close.png'])
        self.assertEqual(index['files']['440x440']['close'],
                         {'off': 'black_close.png', 'sel': 'white_close.png'})
        self.assertEqual(index['paths']['black_close.png'], 'Theme/icons/440x440 Black/black_close.png')

    def test_a_named_pair_leaves_no_half_behind(self):
        """Turbulence's rings rest as 440x440_outline_01_nsel and light as
        440x440_round_01_sel - names the pattern files as two icons, one with
        only a rest look and one with only a lit one. Named as one pair, the
        stray half must go too: offered, it draws its one file in both states."""
        index = self._index({'named': {'440x440': {'round_01': {
            'off': '440x440_outline_01_nsel.png', 'sel': '440x440_round_01_sel.png'}}}},
            ['440x440_outline_01_nsel.png', '440x440_round_01_sel.png',
             '440x440_home_nsel.png', '440x440_home_sel.png'])
        self.assertEqual(index['files']['440x440'], {
            'round_01': {'off': '440x440_outline_01_nsel.png', 'sel': '440x440_round_01_sel.png'},
            'home': {'off': '440x440_home_nsel.png', 'sel': '440x440_home_sel.png'}})

    def test_a_variant_can_claim_several_families(self):
        """Turbulence's rings are round_NN, display_*, on, off and volume_* -
        one prefix cannot claim them from the tiles that share their size."""
        import gdl.spec
        png = b'\x89PNG\r\n\x1a\n'
        names = ['440x440_round_01_nsel.png', '440x440_on_nsel.png', '440x440_home_nsel.png']
        p = {'kit': {'root': 'Theme'},
             'buttons': {'ring': {'kit': '440x440', 'icons': ['round_', 'on']},
                         'button': {'kit': '440x440'}}}
        with tempfile.TemporaryDirectory() as a:
            for f in names:
                os.makedirs(os.path.join(a, 'Theme'), exist_ok=True)
                with open(os.path.join(a, 'Theme', f), 'wb') as fh:
                    fh.write(png)
            old = gdl.spec.RESOURCE_ROOTS
            gdl.spec.RESOURCE_ROOTS = (a,)
            try:
                offered = designsys.icon_names(p)
            finally:
                gdl.spec.RESOURCE_ROOTS = old
        self.assertEqual(offered, {'ring': ['on', 'round_01'], 'button': ['home']})

    def test_a_claim_holds_only_at_its_own_size(self):
        """Turbulence's source tabs (504x504) claim input_laptop; its scene
        pictures (900x648) have an input_laptop of their own, which the claim
        hid - and the wide bar lost its blank to the dock's, at 712x440."""
        import gdl.spec
        png = b'\x89PNG\r\n\x1a\n'
        names = ['504x504_input_laptop_nsel.png', '900x648_input_laptop_nsel.png']
        p = {'kit': {'root': 'Theme'},
             'buttons': {'source': {'kit': '504x504', 'icons': 'input_'},
                         'scene': {'kit': '900x648'}}}
        with tempfile.TemporaryDirectory() as a:
            os.makedirs(os.path.join(a, 'Theme'))
            for f in names:
                with open(os.path.join(a, 'Theme', f), 'wb') as fh:
                    fh.write(png)
            old = gdl.spec.RESOURCE_ROOTS
            gdl.spec.RESOURCE_ROOTS = (a,)
            try:
                offered = designsys.icon_names(p)
            finally:
                gdl.spec.RESOURCE_ROOTS = old
        self.assertEqual(offered, {'source': ['input_laptop'], 'scene': ['input_laptop']})

    def test_a_named_file_the_kit_lacks_is_left_out(self):
        index = self._index({'named': {'440x440': {'close': 'white_close.png'}}},
                            ['440x440_gray_nsel.png'])
        self.assertNotIn('close', index['files']['440x440'])

    def _shockwave_like(self):
        p = designsys.load('afterburn')
        p['kit'] = dict(p['kit'], thumbs='Shockwave/Slider')
        p['defaults'] = dict(p['defaults'], slider=dict(
            p['defaults']['slider'], thumb_image='156x102_sw_thumb.png',
            track_image='156x1026_sw_track_bg.png', fill_image='156x1026_sw_fill.png'))
        if not designsys.kit_root(p, 'thumbs'):
            self.skipTest("Extron's Shockwave kit is not installed here")
        return p

    def test_a_thumb_can_be_one_file_for_every_scheme(self):
        """Shockwave, Mach and Turbulence draw one thumb whatever the accent;
        only Afterburn's comes in the scheme's secondary color."""
        p = self._shockwave_like()
        for s in p['schemes']:
            self.assertEqual(designsys.slider_thumb(p, s['id']),
                             ('156x102_sw_thumb.png', 'Shockwave/Slider/156x102_sw_thumb.png'))

    def test_a_rail_can_be_drawn_from_images(self):
        p = self._shockwave_like()
        art = designsys.rail_art(p)
        self.assertEqual(sorted(art), ['fill', 'track'])
        self.assertTrue(all(v.startswith('data:image/webp;base64,') for v in art.values()))


class TestExtract(unittest.TestCase):
    """Turbulence ships no Resources folder: its images live only inside its
    templates, and Mach's slider art only inside its seed. Extracted to disk,
    they are a kit like any other."""

    def test_a_projects_images_come_out_as_png_files(self):
        seed = os.path.join(REPO, 'seeds', 'Turbulence 1035.gdl')
        if not usable(seed):
            self.skipTest('seed not present (git lfs pull)')
        with tempfile.TemporaryDirectory() as d:
            written = designsys.extract_images([seed], d)
            names = set(os.listdir(d))
            self.assertIn('440x440_close_nsel.png', names)
            self.assertEqual(len(written), len(names))
            # Only named image files: the project's own defaults
            # ('Button', 'Slider Thumb') are not kit art.
            self.assertTrue(all(n.endswith('.png') for n in names))
            with open(os.path.join(d, '440x440_close_nsel.png'), 'rb') as fh:
                self.assertEqual(fh.read(8), b'\x89PNG\r\n\x1a\n')

    def test_a_profile_names_where_its_images_come_from(self):
        """A seed by its repo path; Extron's templates by a name pattern,
        wherever this machine keeps them."""
        p = {'kit': {'extract': {'from': ['seeds/Turbulence 1035.gdl',
                                          'Turbulence * Series.glt'],
                                 'to': 'Turbulence/Extracted'}}}
        found = designsys.extract_sources(p)
        self.assertIn(os.path.join(REPO, 'seeds', 'Turbulence 1035.gdl'), found)
        glts = [f for f in found if f.endswith('.glt')]
        if not glts:
            self.skipTest("Extron's TouchLink templates are not installed here")
        self.assertTrue(all(os.path.basename(f).startswith('Turbulence ') for f in glts))

    def test_extracting_again_writes_nothing_new(self):
        seed = os.path.join(REPO, 'seeds', 'Turbulence 1035.gdl')
        if not usable(seed):
            self.skipTest('seed not present (git lfs pull)')
        with tempfile.TemporaryDirectory() as d:
            designsys.extract_images([seed], d)
            self.assertEqual(designsys.extract_images([seed], d), [])


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

    def test_the_readme_says_to_list_every_panel_the_room_has(self):
        """A designer reads the README first, and it called every artboard one
        page of a TLP1035T: `panels` was in the Page card alone, so a room's
        door panel was never asked for and only the 1035 was built."""
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                text = designsys.readme(p)
                line = next((ln for ln in text.splitlines() if ln.startswith('- **Every panel the room has.**')), '')
                self.assertIn('`panels=', line)
                self.assertIn('on every Page', line)
                self.assertNotIn(f"one page or popup of an Extron {p['model']}", text)

    def test_the_readme_gives_every_panels_room(self):
        """Every designer of a two-panel room drew the 1035 snug and the 525
        failed: positions scale there, controls grow to its touch minimum and
        words to its type floor, and no doc said by how much. One read the
        bundle to find out, and its room built on both. The README says, per
        panel, how far apart two controls' centres must be on the canvas, how
        much room words need there, and what a hub's rail holds. A review of
        #38 found a hub's row read off its uncut main: Mach's 525 promised 0.7
        and three buttons beside the volume where a page has 0.51 and one."""
        # Mach's 525 cuts the canvas's header, footer and left column from its
        # main - [84, 66, 618, 348], a button in each bar - and scales it by
        # 0.511 (348/681); its rail keeps to the same 348 px, which holds the
        # level, Down, Up and one button. Afterburn's chrome is art, so its
        # main is whole and scales by 0.638 (480/752). 66 px and 15 px there
        # are these here.
        for theme, here, words, rail in (('mach', '130 px, 30 px', '2.5', '1 button'),
                                         ('afterburn', '104 px, 24 px', '2.0', '3 buttons')):
            with self.subTest(theme=theme):
                text = designsys.readme(designsys.load(theme))
                section = text.split('## Every panel the room has', 1)[1].split('\n## ', 1)[0]
                rows = [ln for ln in section.splitlines() if ln.startswith('| ') and ' px' in ln]
                hub = next(ln for ln in rows if 'TLP525' in ln)
                self.assertIn(f'| {here} |', hub)
                self.assertIn(f'| {words}x |', hub)
                self.assertIn(f'the volume and {rail} |', hub)
                drawn = next(ln for ln in rows if 'TLP1035M/T' in ln)
                self.assertIn('| 53 px, 12 px |', drawn)
                self.assertIn('| 1x |', drawn)
                # Each model once, its variants together.
                self.assertIn('TLP525C/M/T', hub)
                # The 320 lays its controls out again: no distance to keep.
                self.assertTrue(next(ln for ln in rows if 'TLP320' in ln).endswith('| - | - |'))

    def test_the_readme_ends_with_how_to_load_the_system(self):
        """The Design type looks for the bundle, its global and the stylesheet
        in the README's "Consuming this system" end; all four designers found
        none and guessed the bundle from a file listing."""
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                text = designsys.readme(p)
                end = text.split('\n## Consuming this system\n', 1)[1]
                self.assertNotIn('\n## ', end)
                for want in (f"`window.{p['namespace']}`", '`components/bundle.css`',
                             '`components/bundle.js`', 'components/<Name>/README.md', p['font']['google']):
                    self.assertIn(want, end)
                self.assertLess(end.index('bundle.css'), end.index('bundle.js'))

    def test_the_readme_names_the_start_page_main(self):
        """The Design type names a canvas's entry `Main.dc.html`; the README
        said `Home.dc.html`, and every designer had to choose."""
        text = designsys.readme(designsys.load('mach'))
        line = next(ln for ln in text.splitlines() if ln.startswith('- **One artboard per page or popup.**'))
        self.assertIn('`Main.dc.html`', line)
        self.assertNotIn('Home.dc.html', line)

    def test_the_states_example_draws_every_state_differently(self):
        """The Button README says every state must look different, and
        Turbulence's own example drew Warming exactly as On."""
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                states = json.loads(designsys.load(theme)['examples']['states'])
                looks = [json.dumps({k: v for k, v in s.items() if k != 'name'}, sort_keys=True)
                         if isinstance(s, dict) else '{}' for s in states]
                self.assertEqual(len(set(looks)), len(looks), looks)

    def test_a_line_and_a_clock_name_their_real_default(self):
        """Line's and Clock's READMEs said `text-secondary` for every theme;
        Shockwave's defaults are `text` and `raised`, and Turbulence has no
        `text-secondary` at all."""
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                docs = designsys.component_docs(p)
                names = {t['name'] for t in designsys.tokens(p)['color']['tokens']}
                for comp in ('Line', 'Clock'):
                    want = p['defaults'][comp.lower()]['color']
                    self.assertIn(want, names, comp)
                    self.assertIn(f'(default `{want}`)', docs[comp])

    def test_the_example_keeps_inside_its_main_region(self):
        """The Example's Clock sat 696 px down its MainArea - inside
        Afterburn's 752, below Mach's 681, Shockwave's 574 and Turbulence's
        549."""
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                main = p['layout']['main']
                example = designsys.readme(p).split('## Example', 1)[1]
                inside = example.split('MainArea"', 1)[1].split('\n  </x-import>', 1)[0]
                for top, h in re.findall(r'top: (\d+)px; width: [\d%]+(?:px)?; height: (\d+)px', inside):
                    self.assertLessEqual(int(top) + int(h), main[3])

    def test_the_readme_answers_what_every_designer_asked(self):
        """Four fresh designers asked the same three things. A `nav` reaches
        the programmer, not the panel - the ID map says "Shows page 'Main'" -
        so a modal opened from two pages and closed with nav="Main" sent the
        call page home. A program page may also be led to. And a control on
        two pages is two controls unless it shares an `id`."""
        text = designsys.readme(designsys.load('mach'))
        popups = next(ln for ln in text.splitlines() if ln.startswith('- **Popups.**'))
        self.assertIn('does="Closes this popup."', popups)
        self.assertIn('more than one page', popups)
        program = next(ln for ln in text.splitlines() if ln.startswith('- **A page the program opens'))
        self.assertIn('may lead to it as well', program)
        several = next(ln for ln in text.splitlines() if ln.startswith('- **A control on several pages**'))
        self.assertIn('the same `id`', several)
        # A JoinCall that opens the call page on Home and joins on Call shared
        # an id, and the ID map refused it: a mirror is one function.
        self.assertIn('`nav`', several)

    def test_the_layout_keeps_to_the_gates(self):
        """Each Layout described its seed's geometry, and a designer who
        followed it failed the spec check on the design panel: Shockwave's
        source tabs flush, Mach's rail buttons stacked with no gap, sliders
        under the touch minimum. Where the seed breaks a gate, the Layout
        says what to draw."""
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                layout = designsys.readme(designsys.load(theme)).split('## Layout', 1)[1].split('\n## ', 1)[0]
                for gone in ('stacked with no gap', 'four pixels apart', 'about 30 wide centered',
                             'about 108 apart,', 'slider 52 wide centered', 'slider 52x315 centered',
                             'flush with the bottom'):
                    self.assertNotIn(gone, layout)
        shockwave = designsys.readme(designsys.load('shockwave')).splitlines()
        header = next(ln for ln in shockwave if ln.startswith('- **The header'))
        self.assertIn('`Group joined="true"`', header)

    def test_machs_buttons_take_the_border_its_seed_draws_them_on(self):
        """Mach's buttons are on the border most of its seed's button states
        use - 2D Rounded Rectangle, 554 of 662, which the seed defines square
        and strokeless. A review caught them moved to `mach`, its 10 px rounded
        border, on the word of a README line the seed contradicts: rounder than
        Extron's own Mach."""
        import collections
        from gdl import seeds
        from gdl.project import Project
        if not seeds.usable('seeds/Mach 1035.gdl'):
            self.skipTest('seeds/Mach 1035.gdl is not here (git lfs pull)')
        p = designsys.load('mach')
        proj = Project.open(seeds.path('seeds/Mach 1035.gdl'))
        used = collections.Counter((proj.border(st) or {}).get('resource')
                                   for b in proj.instances('PBButton') for st in proj.states(b))
        most = used.most_common(1)[0][0]
        for v in ('ghost', 'solid', 'highlight'):
            self.assertEqual(p['borders'][p['buttons'][v]['look']['border']]['resource'], most, v)

    def test_a_built_in_border_draws_as_its_seed_defines_it(self):
        """A built-in border's geometry is the seed's, not GUI Designer's:
        Mach's 1035 defines 2D Rounded Rectangle at radius 1 and thickness 0,
        and the profile's radius 10 and thickness 3 drew a rounded outline in
        the preview that the panel built square and strokeless - a designer
        told two states apart by it. Each built-in a profile offers draws as
        its design panel's seed defines it."""
        from gdl import seeds
        from gdl.project import Project
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                seed = designsys.models(p)[p['model']]['seed']
                if not seeds.usable(seed):
                    self.skipTest(f'{seed} is not here (git lfs pull)')
                own = Project.open(seeds.path(seed)).border_geometry()
                for key, b in p['borders'].items():
                    g = own.get(b['resource'])
                    if g is None or not b['resource'].startswith('2D '):
                        continue
                    self.assertEqual(b['thickness'], g['thickness'], key)
                    if b['resource'] == '2D Rounded Rectangle':
                        self.assertEqual(b['radius'], g['radius'], key)
                    if not g['thickness']:
                        self.assertIn('no stroke', b['usage'], key)

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


class TestPreviews(unittest.TestCase):
    """What the published system shows a designer, for every template."""

    def test_no_template_names_a_color_it_lacks(self):
        """A color name the template does not have paints #FF00FF, on purpose,
        so it is seen. Turbulence's Panel preview filled with `pressed` and its
        PopupRegion drew in `text-secondary` - neither is Turbulence's."""
        js = designsys._read('bundle.js')
        literal = set(re.findall(r"paint\([^,()]+,\s*'([a-z][a-z-]*)'\)", js))
        for t in designsys.TEMPLATES:
            p = designsys.load(t)
            have = {c['name'] for c in p['colors']}
            used = set(literal)
            for src in designsys.previews(p).values():
                used |= set(re.findall(r'\b(?:fill|stroke|color): "([a-z][a-z-]*)"', src))
            self.assertEqual(used - have - {'none'}, set(), t)

    def test_a_panel_preview_shows_its_fills_over_the_templates_page(self):
        """Turbulence's panel is `page`, so drawn on the page's own color it was
        not there at all."""
        src = designsys.previews(designsys.load('turbulence'))['Panel']
        self.assertIn('N.Page', src)
        self.assertEqual(re.findall(r'fill: "([a-z-]+)"', src), ['page', 'shade', 'raised'])

    def test_an_image_variant_previews_at_its_seeds_size(self):
        """Turbulence's square tile is 87 by 90 in its seed and its ring 100;
        the preview drew both 64 tall with captions at full size, so 'Button'
        spilled past its tile - and a designer copying it would too."""
        p = designsys.load('turbulence')
        sizes = {x[0]: (x[2], x[3]) for x in designsys._preview_images(p)}
        self.assertEqual((sizes['button'], sizes['ring'], sizes['source']),
                         ((87, 90), (100, 100), (127, 133)))
        self.assertIn('The seed draws it 87x90.', designsys.component_docs(p)['Button'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
