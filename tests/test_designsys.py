"""The design systems published as Design System artifacts (gdl/designsys).

Two contracts. The Design System page silently DROPS what it cannot read - a
token name with a space, a color it does not parse, a family written as a map -
so the tokens are checked against its grammar here, where a drop is a failure.
And the components carry spec fields for gdl.design, so every token, border
and type style a profile names has to be one the spec and the seed can build.
"""
import json
import math
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
        placed inside MainArea, its example tab landed 168,120 down and right.
        Its README's working page is drawn in regions: the tab is the Header's."""
        text = _section(designsys.readme(designsys.load('shockwave')), 'The working page')
        header = re.search(r'ExtronShockwave\.Header">(.*?)</x-import>\n  </x-import>', text, re.S)
        self.assertIn('slot="source" name="Laptop"', header.group(1))
        self.assertNotIn('MainArea', text)

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


# A frame's page records: the measured page's five bands, and the pages a
# 300 or a 320 lends it (home, second), which turn as the frame does.
_SWAP = {'top': 'left', 'left': 'top', 'bottom': 'right', 'right': 'bottom'}
_PAGES = ('home', 'second')
# What models() adds to a frame for its panel: where a slot is under the
# panel's touch minimum, the rect that meets it and why.
_DERIVED = ('legal', 'reason')


def _turned(v, top=True):
    """A frame's value the other way up: every rect transposed, as turn()
    transposes main and rail, and its bands' names swapped where they name
    bands - in the frame and in each page record it carries."""
    if isinstance(v, list) and len(v) == 4 and all(type(x) is int for x in v):
        return [v[1], v[0], v[3], v[2]]
    if isinstance(v, list):
        return [_turned(x, False) for x in v]
    if isinstance(v, dict):
        return {(_SWAP.get(k, k) if top else k): _turned(x, top and k in _PAGES) for k, x in v.items()}
    return v


def _measured(v):
    """A model's frame less what models() derives for its panel."""
    if isinstance(v, list):
        return [_measured(x) for x in v]
    if isinstance(v, dict):
        return {k: _measured(x) for k, x in v.items() if k not in _DERIVED}
    return v


def _items(band, role):
    return [it for it in (band or {}).get('items', []) if it['role'] == role]


def _rects(band, role):
    return [it['rect'] for it in _items(band, role)]


def _inside(a, b, tol=4):
    return (a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[0] + a[2] <= b[0] + b[2] + tol
            and a[1] + a[3] <= b[1] + b[3] + tol)


class TestTheFrame(unittest.TestCase):
    """Each series' working page in its template's own grammar, measured off
    its seed (tests/measure_series.py frame_of; tests/test_measure_series.py
    checks each profile's against its seed where Git LFS has pulled it). These
    read the checked-in frames, so they hold with no seed here: the five bands,
    their surfaces and slots, the windows, and the values the template draws."""
    THEMES = ('afterburn', 'mach', 'shockwave', 'turbulence')
    BANDS = ('top', 'left', 'right', 'bottom', 'center')

    def series(self):
        for t in self.THEMES:
            p = designsys.load(t)
            for series, row in p['panels'].items():
                if not series.startswith('_'):
                    yield t, p, series, row

    def frame(self, theme, series):
        return designsys.load(theme)['panels'][series]['frame']

    def records(self, f):
        """The frame's page records: its own, and those it carries."""
        return [f] + [f[k] for k in _PAGES if f.get(k)]

    def test_every_series_with_a_seed_has_a_frame(self):
        for t, p, series, row in self.series():
            with self.subTest(series=series):
                if not set(row['models']) & set(row.get('seeds') or {}):
                    self.assertNotIn('frame', row)
                    continue
                f = row['frame']
                self.assertTrue(set(self.BANDS) | {'page', 'ids', 'note', 'windows'} <= set(f))
                for rec in self.records(f):
                    self.assertTrue(rec['page'])
                    self.assertEqual(len(rec['center']['rect']), 4)
                    for b in self.BANDS:
                        if rec[b] is not None:
                            self.assertEqual(len(rec[b]['rect']), 4, b)
                            self.assertIsInstance(rec[b]['items'], list, b)
                            self.assertIsInstance(rec[b]['surfaces'], list, b)

    def test_a_bands_surfaces_and_region_lie_inside_it(self):
        # The bands are where the template draws its bars, so what draws a
        # bar - and the centre's popup region - lies inside its band.
        for t, p, series, row in self.series():
            for rec in self.records(row.get('frame') or {'page': None}):
                for b in self.BANDS:
                    band = rec.get(b)
                    if not band:
                        continue
                    with self.subTest(series=series, page=rec['page'], band=b):
                        for s in band['surfaces']:
                            self.assertTrue(_inside(s['rect'], band['rect']), (s['name'], s['rect'], band['rect']))
                        if band.get('region'):
                            self.assertTrue(_inside(band['region'], band['rect']), (band['region'], band['rect']))
                        if band.get('well'):
                            self.assertTrue(_inside(band['well'], band['rect']), (band['well'], band['rect']))

    def test_no_two_slots_of_a_band_share_a_rect(self):
        for t, p, series, row in self.series():
            for rec in self.records(row.get('frame') or {'page': None}):
                for b in self.BANDS:
                    if not rec.get(b):
                        continue
                    with self.subTest(series=series, page=rec['page'], band=b):
                        rects = [tuple(it['rect']) for it in rec[b]['items']]
                        self.assertEqual(len(rects), len(set(rects)), rec[b]['items'])

    def test_a_bar_themes_working_page_has_all_five_bands(self):
        for t, p, series, row in self.series():
            if t == 'afterburn' or row['tier'] != 'A':
                continue
            with self.subTest(series=series):
                self.assertTrue(all(row['frame'][b] for b in self.BANDS))
                self.assertTrue(row['frame']['top']['tabs']['count'] >= 2)
                self.assertTrue(row['frame']['left']['groups'])
                self.assertEqual(set(row['frame']['ids']), {'help', 'power', 'volume', 'mute', 'mode'})

    def test_the_tabs_hold_each_tabs_own_rect(self):
        # Extron's steps are uneven - the Turbulence 1220's run 141, 141, 140,
        # 142, 141 - so a first rect and a pitch cannot give them back.
        for t, p, series, row in self.series():
            f = row.get('frame') or {}
            for b in ('top', 'center'):
                tabs = (f.get(b) or {}).get('tabs')
                if not tabs:
                    continue
                with self.subTest(series=series):
                    self.assertEqual(len(tabs['items']), tabs['count'])
                    self.assertEqual(tabs['items'][0]['rect'], tabs['first'])
                    self.assertEqual({tuple(it['rect'][1:]) for it in tabs['items']}, {tuple(tabs['first'][1:])})
        xs = lambda t, s, b='top': [it['rect'][0] for it in self.frame(t, s)[b]['tabs']['items']]
        self.assertEqual(xs('turbulence', 'Turbulence 1220 Series'), [141, 282, 423, 563, 705, 846])
        self.assertEqual(xs('turbulence', 'Turbulence 1520 Series'), [150, 300, 451, 600, 752, 902])
        self.assertEqual(xs('turbulence', 'Turbulence 1020 Series')[-3:], [451, 564, 677])
        self.assertEqual(xs('shockwave', 'Shockwave 1020 Series')[-2:], [618, 740])
        self.assertEqual(xs('afterburn', 'Afterburn 1720 Series', 'center'), [540, 763, 987, 1210])
        self.assertEqual(xs('afterburn', 'Afterburn 1230 Series', 'center'), [1100, 1228, 1355, 1482])

    def test_machs_1035(self):
        f = self.frame('mach', 'Mach 1220 Series')
        self.assertEqual(f['page'], 'Main SD')
        self.assertEqual(f['top']['rect'], [0, 0, 1280, 64])
        tabs = f['top']['tabs']
        self.assertEqual((tabs['first'], tabs['pitch'], tabs['count']), ([258, 0, 190, 64], 191, 4))
        self.assertEqual([it['rect'][0] for it in tabs['items']], [258, 449, 640, 831])
        self.assertEqual(tabs['look']['off']['fill'], '#000000B4')
        self.assertEqual([s['rect'] for s in f['top']['start']], [[0, 0, 257, 64]])
        self.assertEqual(f['bottom']['rect'], [0, 745, 1280, 55])
        self.assertEqual(_rects(f['bottom'], 'help'), [[1069, 745, 70, 55]])
        self.assertEqual(_rects(f['bottom'], 'power'), [[1140, 745, 140, 55]])
        self.assertEqual(_rects(f['bottom'], 'mode'), [[0, 745, 140, 55]])
        self.assertEqual(_rects(f['bottom'], 'clock'), [[398, 751, 483, 42]])
        self.assertEqual(f['left']['rect'], [0, 64, 140, 681])
        display, settings = f['left']['groups']
        self.assertEqual((display['heading']['text'], display['heading']['rect'], display['pitch']),
                         ('Display', [17, 149, 103, 37], 61))
        self.assertEqual([b['rect'] for b in display['buttons']],
                         [[17, 186, 103, 60], [17, 247, 103, 60], [17, 308, 103, 60]])
        self.assertEqual(settings['heading']['text'], 'Settings')
        self.assertEqual([it['role'] for it in f['right']['items']], ['heading', 'volume', 'mute'])
        self.assertEqual(f['center']['region'], [140, 137, 995, 549])
        self.assertEqual(f['center']['well'], [250, 185, 778, 435])
        self.assertEqual(f['center']['title'], [265, 185, 755, 58])
        # The well is the Laptop popup's title bar and body, 1 px apart.
        self.assertEqual([(s['rect'], s['fill'], s['popup']) for s in f['center']['surfaces']],
                         [([250, 185, 778, 58], '#000000B4', 'Laptop'), ([250, 244, 778, 376], '#000000B4', 'Laptop')])
        self.assertEqual(f['ids'], {'help': 8117, 'power': 8022, 'volume': 8024, 'mute': 8021, 'mode': 8118})

    def test_shockwaves_1035(self):
        f = self.frame('shockwave', 'Shockwave 1220 Series')
        self.assertEqual(f['top']['rect'], [0, 0, 1280, 91])
        tabs = f['top']['tabs']
        self.assertEqual((tabs['first'], tabs['pitch'], tabs['count']), ([169, 0, 152, 91], 153, 6))
        self.assertEqual([it['rect'][0] for it in tabs['items']], [169, 322, 475, 628, 781, 934])
        # Each tab's name is a caption-only button under it sharing its ID;
        # the tab draws no caption of its own.
        twin = tabs['twin']
        self.assertEqual([it['rect'] for it in twin['items']],
                         [[x, 55, 152, 36] for x in (169, 322, 475, 628, 781, 934)])
        self.assertEqual([it['id'] for it in twin['items']], [it['id'] for it in tabs['items']])
        self.assertEqual(twin['look']['off'], {'fill': None, 'border': None, 'art': None, 'text': '#FFFFFFFF'})
        self.assertEqual(twin['look']['on'], twin['look']['off'])
        self.assertEqual((tabs['look']['off']['text'], tabs['look']['on']['text']), (None, None))
        self.assertNotIn('underline', f['note'])
        # The well is main: the rails stand outside it and the footer runs
        # between them, wider than the header's tab span.
        self.assertEqual(f['center']['rect'], [168, 91, 926, 627])
        self.assertEqual(f['center']['region'], [172, 124, 921, 574])
        self.assertEqual(f['center']['well'], [168, 120, 926, 574])
        self.assertEqual(f['right']['rect'], [1094, 91, 186, 709])
        self.assertEqual(f['bottom']['rect'], [168, 718, 926, 82])
        self.assertIn([166, 718, 928, 62], [s['rect'] for s in f['bottom']['surfaces']])
        self.assertEqual(_rects(f['bottom'], 'help'), [[956, 720, 143, 59]])
        # Power stands outside the capsule, at the foot of the right rail.
        self.assertEqual(_rects(f['right'], 'power'), [[1115, 720, 143, 59]])
        f = self.frame('shockwave', 'Shockwave 1720 Series')
        self.assertEqual((f['left']['rect'], f['right']['rect']), ([0, 127, 265, 953], [1652, 127, 268, 953]))
        self.assertEqual(f['bottom']['rect'], [265, 967, 1387, 113])
        for series, right in (('Shockwave 1020 Series', 872), ('Shockwave 1520 Series', 1177),
                              ('Shockwave 720 Series', 682)):
            with self.subTest(series=series):
                self.assertEqual(self.frame('shockwave', series)['right']['rect'][0], right)

    def test_turbulences_1035(self):
        f = self.frame('turbulence', 'Turbulence 1220 Series')
        self.assertEqual(f['top']['rect'], [0, 0, 1280, 133])
        self.assertEqual(f['bottom']['rect'], [140, 688, 997, 110])
        self.assertEqual(f['left']['rect'], [0, 133, 140, 666])
        self.assertEqual([(s['kind'], s['art']) for s in f['top']['surfaces']], [('image', '2047x151_header.png')])
        self.assertEqual(f['center']['region'], [140, 137, 995, 549])

    def test_turbulences_device_pictures(self):
        """Each source's popup pins its device's picture at a size of its
        own, so the frame records one per device - the kit family its art
        names - in page coordinates: on the 1035 every one at the popup's
        top left, the Doc Cam's 326x288 where the Laptop's is 293x257; on the
        525 each under the title where that device's own picture stands.
        The 525's settings popups (Audio, Display and Lighting Control, and
        Dual Display Select) picture a speaker, a monitor and a lightbulb
        for no source, and are not among them."""
        f = self.frame('turbulence', 'Turbulence 1220 Series')
        self.assertEqual(f['center']['pictures'], {
            'apple-tv': [140, 137, 293, 257], 'bluray': [140, 137, 352, 310], 'doc-cam': [140, 137, 326, 288],
            'ipod': [140, 137, 293, 257], 'laptop': [140, 137, 293, 257], 'pc': [140, 137, 293, 257],
            'tuner': [140, 137, 526, 329], 'vc-1': [140, 137, 200, 209]})
        f = self.frame('turbulence', 'Turbulence 520 Series')
        self.assertEqual(f['center']['pictures'], {
            'apple-tv': [217, 40, 268, 250], 'bluray': [234, 59, 233, 219], 'doc-cam': [212, 57, 278, 252],
            'ipod': [218, 58, 265, 202], 'laptop': [196, 45, 310, 241], 'pc': [219, 38, 264, 260],
            'tuner': [182, 35, 338, 265]})
        # The Laptop's, which a device no source pictures takes, is still
        # the measured popup's own surface.
        laptop = next(s for s in f['center']['surfaces'] if s['kind'] == 'image')
        self.assertEqual(laptop['rect'], f['center']['pictures']['laptop'])
        # A template that pins no picture records none.
        self.assertNotIn('pictures', self.frame('mach', 'Mach 1220 Series')['center'])

    def test_the_windows_between_the_bars(self):
        f = self.frame('mach', 'Mach 1220 Series')
        w = f['windows']
        # Mach's window is a #303030 band between the header and the footer.
        self.assertEqual((w['help']['rect'], w['help']['surfaces'][0]['fill']), ([0, 64, 1280, 681], '#303030FF'))
        self.assertEqual((w['help']['title'], w['help']['close']['rect'], w['help']['message']),
                         ([27, 82, 958, 52], [1186, 82, 72, 52], [320, 290, 637, 220]))
        self.assertEqual(w['confirm']['message'], [357, 280, 565, 106])
        self.assertEqual([(b['role'], b['rect']) for b in w['confirm']['buttons']],
                         [('power', [372, 432, 258, 60]), ('cancel', [650, 432, 258, 60])])
        self.assertEqual(w['wait']['message'], [270, 324, 739, 152])
        display = next(s for s in w['settings'] if 'Display Settings' in s['popups'])
        self.assertEqual((display['rect'], display['title'], display['close']['rect']),
                         ([0, 64, 1280, 681], [27, 82, 958, 52], [1186, 82, 72, 52]))
        # Shockwave's are #999999 cards, two widths for its settings.
        w = self.frame('shockwave', 'Shockwave 1220 Series')['windows']
        self.assertEqual((w['help']['rect'], w['help']['surfaces'][0]['fill'], w['help']['close']['rect']),
                         ([288, 173, 703, 453], '#999999FF', [933, 180, 50, 50]))
        self.assertEqual(w['help']['title'], [448, 203, 383, 80])
        self.assertEqual(w['confirm']['rect'], [288, 205, 703, 389])
        self.assertEqual([(b['role'], b['rect']) for b in w['confirm']['buttons']],
                         [('cancel', [348, 449, 272, 110]), ('power', [659, 449, 272, 110])])
        display = next(s for s in w['settings'] if 'Display Control' in s['popups'])
        self.assertEqual((display['rect'], display['close']['rect']), ([224, 74, 832, 651], [999, 81, 50, 50]))
        audio = next(s for s in w['settings'] if 'Audio Control' in s['popups'])
        self.assertEqual((audio['rect'], audio['close']['rect']), ([126, 74, 1028, 651], [1096, 81, 50, 50]))
        # Turbulence's settings window fills between its bars.
        w = self.frame('turbulence', 'Turbulence 1220 Series')['windows']
        self.assertEqual(w['help']['rect'], [258, 149, 761, 500])
        lighting = next(s for s in w['settings'] if 'Lighting Control' in s['popups'])
        self.assertEqual((lighting['rect'], lighting['surfaces'][0]['fill'], lighting['close']['rect']),
                         ([80, 56, 1120, 684], '#184E80FF', [1133, 61, 60, 60]))
        # Afterburn's redraws the whole screen with its art.
        w = self.frame('afterburn', 'Afterburn 1220 Series')['windows']
        self.assertEqual((w['help']['rect'], w['help']['title'], w['help']['close']['rect']),
                         ([0, 0, 1280, 800], [485, 36, 310, 50], [1026, 25, 64, 64]))
        # A hub's settings window is the popup its settings opener names, in
        # the popup region; Mach's hub modals draw no window of their own.
        w = self.frame('mach', 'Mach 520 Series')['windows']
        self.assertEqual((w['help']['rect'], w['help']['title'], w['help']['close']['rect']),
                         (None, [243, 0, 321, 66], [739, 0, 61, 66]))
        self.assertEqual([(s['popups'], s['rect'], s['title'], s['close']['rect']) for s in w['settings']],
                         [(['Settings'], [0, 0, 702, 480], [81, 15, 540, 66], [625, 15, 61, 66])])
        w = self.frame('shockwave', 'Shockwave 520 Series')['windows']
        self.assertEqual([(s['popups'], s['title']) for s in w['settings']], [(['More Options'], [80, 0, 541, 72])])
        # Afterburn's hub opens Help in the region too, and closes it with Back.
        w = self.frame('afterburn', 'Afterburn 520 Series')['windows']
        self.assertEqual((w['help']['rect'], w['help']['close']['role'], w['help']['close']['rect']),
                         ([0, 0, 686, 480], 'back', [0, 13, 66, 66]))
        self.assertEqual([(s['popups'], s['close']['rect']) for s in w['settings']], [(['Settings'], [0, 13, 66, 66])])

    def test_the_type_the_center_and_the_windows_set(self):
        """Each panel's own sizes, off its own seed - the 725's from the 725's,
        not the 1035's scaled: a source's title, its empty state and
        Shockwave's status; each window's title and message, Help's apart
        from the confirmation's."""
        F = lambda t, s: self.frame(t, f'{t.capitalize()} {s} Series')
        self.assertEqual(F('mach', 1220)['center']['pt'], {'title': 24, 'empty': 16})
        self.assertEqual(F('mach', 1020)['center']['pt'], {'title': 20, 'empty': 14})
        self.assertEqual(F('shockwave', 1220)['center']['pt'], {'title': 40, 'empty': 22, 'status': 16})
        self.assertEqual(F('shockwave', 1020)['center']['pt'], {'title': 30, 'empty': 20, 'status': 14})
        self.assertEqual(F('turbulence', 1220)['center']['pt'], {'title': 36, 'empty': 16})
        self.assertEqual(F('turbulence', 1020)['center']['pt'], {'title': 36, 'empty': 16})
        # Shockwave's status, the program's Disconnected, under its request.
        self.assertEqual(F('shockwave', 1220)['center']['status'], [536, 516, 192, 102])
        self.assertEqual(F('shockwave', 1020)['center']['status'], [428, 385, 152, 75])
        self.assertNotIn('status', F('mach', 1220)['center'])
        win = lambda t, s, k: F(t, s)['windows'][k]
        for t, s, help_, confirm in (('mach', 1220, (24, 20), 20), ('mach', 1020, (20, 16), 18),
                                     ('shockwave', 1220, (40, 20), 26), ('shockwave', 1020, (30, 16), 20),
                                     ('turbulence', 1220, (36, 16), 20), ('turbulence', 1020, (30, 14), 20)):
            with self.subTest(theme=t, series=s):
                self.assertEqual(win(t, s, 'help')['pt'], dict(zip(('title', 'message'), help_)))
                self.assertEqual(win(t, s, 'confirm')['pt'], {'message': confirm})
        self.assertEqual([r['pt'] for r in win('mach', 1020, 'settings') if r['title']], [{'title': 20}] * 2)

    def test_a_source_with_controls_is_titled_where_its_template_titles_it(self):
        """Turbulence titles a source with controls at the popup's top (its
        Doc Cam at y 0) and an empty one 40 px lower; Mach and Shockwave at
        one place."""
        F = lambda t, s: self.frame(t, f'{t.capitalize()} {s} Series')['center']
        self.assertEqual((F('turbulence', 1220)['title'], F('turbulence', 1220)['title_controls']),
                         ([250, 177, 770, 96], [250, 137, 770, 96]))
        self.assertEqual(F('turbulence', 1020)['title_controls'], [200, 103, 616, 72])
        self.assertEqual(F('mach', 1220)['title_controls'], F('mach', 1220)['title'])
        self.assertEqual(F('shockwave', 1020)['title_controls'], F('shockwave', 1020)['title'])

    def test_a_message_keeps_the_lines_its_template_sets_it_in(self):
        """How many lines the template's message takes in its box, in its own
        face: Turbulence's power-down question one on the 1035, two on the 725."""
        w = lambda s: self.frame('turbulence', f'Turbulence {s} Series')['windows']
        self.assertEqual((w(1220)['confirm']['lines'], w(1020)['confirm']['lines']), (1, 2))
        self.assertEqual(w(1220)['help']['lines'], 1)
        self.assertEqual(self.frame('mach', 'Mach 1220 Series')['windows']['help']['lines'], 3)
        self.assertEqual(self.frame('shockwave', 'Shockwave 1220 Series')['windows']['confirm']['lines'], 2)

    def test_the_320s_strip(self):
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                f = self.frame(theme, f'{theme.capitalize()} 320 Series')
                self.assertEqual((f['page'], f['top']['rect']), ('Doc Cam 1', [0, 0, 320, 36]))
                self.assertEqual(f['center']['rect'], [0, 36, 320, 204])
                self.assertTrue(_items(f['top'], 'title'))
                self.assertEqual(len([it for b in self.BANDS for it in _items(f[b], 'more')]), 1)
                self.assertFalse([it for b in self.BANDS for it in _items(f[b], 'back')])
                self.assertEqual(f['second']['page'], 'Doc Cam 2')
                self.assertEqual(len([it for b in self.BANDS for it in _items(f['second'][b], 'back')]), 1)
                # Its empty state is a source page's with no controls.
                self.assertEqual((f['center']['empty'], f['center']['empty_page']), ([0, 80, 320, 102], 'Laptop'))
        f = self.frame('mach', 'Mach 320 Series')
        self.assertEqual(f['center']['row'], [[61, 65, 74, 50], [185, 65, 74, 50]])
        # The second page's strip is a shape short of the edge and Back.
        self.assertEqual(_rects(f['second']['top'], 'back'), [[263, 0, 57, 36]])
        self.assertEqual([s['rect'] for s in f['second']['top']['surfaces']], [[0, 0, 262, 36]])
        self.assertEqual(_rects(self.frame('shockwave', 'Shockwave 320 Series')['second']['center'], 'back'),
                         [[232, 179, 59, 59]])
        # Afterburn's 320 titles its pages in the row along the foot.
        f = self.frame('afterburn', 'Afterburn 320 Series')
        self.assertEqual((f['top'], f['bottom']['rect']), (None, [0, 190, 320, 50]))
        self.assertEqual((_rects(f['bottom'], 'more'), _rects(f['bottom'], 'title')),
                         ([[270, 190, 50, 50]], [[12, 197, 120, 36]]))
        self.assertEqual((_rects(f['second']['bottom'], 'back'), _rects(f['second']['bottom'], 'title')),
                         ([[0, 190, 50, 50]], [[50, 197, 135, 36]]))
        self.assertEqual(f['center']['empty'], [35, 44, 250, 102])

    def test_the_320s_columns_sizes_volume_and_window_grounds(self):
        """The 320's page per source: the steps its columns stand at, the
        sizes it sets its title, headings and empty state in, the Volume modal
        the program shows - its strip, level and Cancel where the template
        draws them (Mach's has no Cancel) - and whether the question and the
        wait stand on the photo (Mach's on the page's own #303030)."""
        want = {'mach': ([124, 60], {'title': 16, 'heading': 11, 'empty': 14}, [[278, 0, 42, 240]], [292, 32, 15, 175],
                         None, False),
                'shockwave': ([103, 61], {'title': 14.25, 'heading': 12, 'empty': 12}, [], [292, 32, 15, 175],
                              ([0, 0, 277, 240], 8001), True),
                'turbulence': ([103, 61], {'title': 14.25, 'heading': 12, 'empty': 12}, [], [292, 32, 12, 179],
                               ([0, 0, 277, 240], 8001), True)}
        for theme, (pitch, pt, strips, level, cancel, art) in want.items():
            with self.subTest(theme=theme):
                f = self.frame(theme, f'{theme.capitalize()} 320 Series')
                self.assertEqual((f['center']['pitch'], f['center']['pt']), (pitch, pt))
                V = f['volume']
                self.assertEqual((V['popup'], [s['rect'] for s in V['surfaces']], V['level']['rect']),
                                 ('Volume', strips, level))
                self.assertEqual(V['cancel'] and (V['cancel']['rect'], V['cancel']['id']), cancel)
                self.assertEqual((f['windows']['confirm']['art'], f['windows']['wait']['art']), (art, art))
                self.assertEqual([b['id'] for b in f['windows']['confirm']['buttons']].count(9028), 1)

    def test_the_320s_volume_glyphs_empty_lines_and_question(self):
        """What the 320 draws apart from its bigger panels: the Volume
        modal's glyphs over and under its level, each with its seed ID and
        size; the empty state one label a line (Laptop Label 1-3), the first
        sentence a paragraph apart from the other two; and the question's own
        words, in one run on every 320 (Shockwave's 1035 breaks its line)."""
        glyphs = {'mach': ([[283, 0, 36, 32], [283, 211, 36, 29]], 18),
                  'shockwave': ([[277, 0, 43, 32], [277, 211, 43, 29]], 16),
                  'turbulence': ([[277, 0, 43, 32], [277, 211, 43, 29]], 16)}
        for theme, (rects, pt) in glyphs.items():
            with self.subTest(theme=theme):
                f = self.frame(theme, f'{theme.capitalize()} 320 Series')
                self.assertEqual(f['volume']['labels'], [{'rect': rects[0], 'id': 7023, 'pt': pt},
                                                         {'rect': rects[1], 'id': 7026, 'pt': pt}])
                self.assertEqual(f['center']['empty_lines'],
                                 [{'rect': [0, 80, 320, 29], 'id': 6060}, {'rect': [0, 123, 320, 35], 'id': 6061},
                                  {'rect': [0, 153, 320, 29], 'id': 6062}])
                self.assertEqual(f['windows']['confirm']['text'], 'Do you want to power down the system?')

    def test_the_300s_source_page_and_its_home(self):
        # The source page's bands hold its own controls; the home page's
        # menu bar is a record of its own.
        f = self.frame('mach', 'Mach 300 Series')
        self.assertEqual((f['page'], f['bottom']['rect']), ('Computer', [0, 400, 320, 80]))
        self.assertEqual([(it['role'], it['rect']) for it in f['bottom']['items']], [('back', [8, 404, 96, 72])])
        self.assertEqual(_rects(f['center'], 'title'), [[0, 15, 320, 40]])
        self.assertEqual(f['center']['empty'], [0, 151, 320, 138])
        self.assertEqual(f['home']['page'], 'Main')
        self.assertEqual([(it['role'], it['rect']) for it in f['home']['bottom']['items']],
                         [('settings', [8, 404, 96, 72]), ('help', [112, 404, 96, 72]), ('power', [216, 404, 96, 72])])
        self.assertEqual(f['ids'], {'help': 9103, 'power': 8022, 'settings': 8040})
        # Afterburn's Landscape source page draws its own art: the column is
        # on the left, with Back and the title, and the home page's on the right.
        f = self.frame('afterburn', 'Afterburn 300 Landscape Series')
        self.assertEqual((f['left']['rect'], f['center']['rect'], f['right']),
                         ([0, 0, 88, 320], [88, 0, 392, 320], None))
        self.assertEqual((_rects(f['left'], 'back'), _rects(f['left'], 'title')),
                         ([[10, 18, 66, 66]], [[5, 270, 79, 50]]))
        self.assertEqual(f['center']['empty'], [120, 91, 320, 138])
        self.assertEqual(f['home']['right']['rect'], [392, 0, 88, 320])
        self.assertEqual([it['role'] for it in f['home']['right']['items']], ['settings', 'help', 'power'])
        f = self.frame('afterburn', 'Afterburn 300 Portrait Series')
        self.assertEqual(f['bottom']['rect'], [0, 392, 320, 88])
        self.assertEqual([(it['role'], it['rect']) for it in f['bottom']['items']],
                         [('back', [0, 405, 66, 66]), ('title', [66, 413, 231, 50])])
        self.assertEqual(f['center']['empty'], [0, 79, 320, 138])
        self.assertEqual([(it['role'], it['rect']) for it in f['home']['bottom']['items']],
                         [('settings', [23, 402, 66, 66]), ('help', [130, 402, 66, 66]), ('power', [231, 402, 66, 66])])

    def test_a_hubs_menu_bar(self):
        f = self.frame('mach', 'Mach 520 Series')
        self.assertEqual(f['page'], 'Main Page')
        self.assertEqual(f['right']['rect'], [702, 0, 98, 480])
        self.assertEqual([it['role'] for it in f['right']['items']],
                         ['heading', 'volume-up', 'volume-down', 'mute', 'settings', 'power'])
        self.assertEqual(f['center']['region'], [0, 0, 702, 480])
        self.assertEqual((f['left'], f['bottom']), (None, None))
        f = self.frame('shockwave', 'Shockwave 520 Series')
        self.assertEqual(f['top']['rect'], [0, 0, 700, 72])
        self.assertEqual(f['right']['rect'], [700, 0, 100, 480])
        # Every hub's settings opener is 8040, More on Shockwave's and
        # Turbulence's, which opens their Choose an Option.
        self.assertEqual([(it['name'], it['id']) for it in _items(f['right'], 'settings')], [('More', 8040)])
        for t, p, series, row in self.series():
            if row.get('frame') and row['frame']['page'] in ('Main Page', 'Main') and row['frame']['right']:
                with self.subTest(series=series):
                    self.assertEqual(row['frame']['ids'].get('settings'), 8040)

    def test_afterburns_art_draws_no_top_or_bottom_bar(self):
        for t, p, series, row in self.series():
            if t != 'afterburn' or row['tier'] != 'A' or 'frame' not in row:
                continue
            with self.subTest(series=series):
                f = row['frame']
                self.assertEqual((f['top'], f['bottom']), (None, None))
                self.assertTrue(f['left'] and f['right'])
                self.assertEqual(f['center']['rect'], row['main'])
                self.assertTrue(f['note'])
        f = self.frame('afterburn', 'Afterburn 1220 Series')
        self.assertEqual(f['center']['region'], [200, 175, 880, 525])
        self.assertEqual(f['center']['tabs']['first'], [342, 37, 110, 110])
        # The 1230's Full Screen is the video's, not the projection screen's.
        f = self.frame('afterburn', 'Afterburn 1230 Series')
        self.assertEqual(len(_items(f['center'], 'fullscreen')), 2)
        self.assertFalse(_items(f['center'], 'screen'))

    def test_every_model_carries_its_series_frame(self):
        for t in self.THEMES:
            p = designsys.load(t)
            for pid, row in designsys.models(p).items():
                if not row.get('turned'):
                    with self.subTest(panel=pid):
                        self.assertEqual(_measured(row['frame']), p['panels'][row['series']].get('frame'))

    def test_a_slot_under_a_panels_touch_minimum_has_a_legal_rect(self):
        # The touch gate is each panel's own: the 1220 series' tabs are legal
        # on a 1035 (53 px) and short on an 835 (67 px), so models() gives
        # each panel's frame the rect that meets its own, about the slot's
        # centre and inside its band where the band can hold it.
        m = designsys.models(designsys.load('mach'))
        f = m['TLP1035T']['frame']
        self.assertNotIn('legal', _items(f['bottom'], 'help')[0])
        self.assertNotIn('legal', f['top']['tabs']['items'][0])
        slider = _items(f['right'], 'volume')[0]
        self.assertEqual((slider['rect'], slider['legal']), ([1198, 178, 30, 363], [1187, 178, 53, 363]))
        self.assertEqual(slider['reason'], '30x363 is under the 53 px touch minimum (9 mm at 149 DPI)')
        tab = m['TLP835T']['frame']['top']['tabs']['items'][0]
        self.assertEqual((tab['legal'], tab['reason']),
                         ([258, 0, 190, 67], '190x64 is under the 67 px touch minimum (9 mm at 188.68 DPI)'))
        # The 725's footer is shallower than its touch minimum, so Help grows
        # out of it, kept on the canvas.
        hlp = _items(m['TLP725T']['frame']['bottom'], 'help')[0]
        self.assertEqual((hlp['rect'], hlp['legal']), ([843, 543, 57, 57], [842, 540, 60, 60]))
        close = m['TLP1035T']['frame']['windows']['help']['close']
        self.assertEqual((close['rect'], close['legal']), ([1186, 82, 72, 52], [1186, 82, 72, 53]))

    def test_a_turned_panel_has_its_series_frame_transposed(self):
        turned = 0
        for t in self.THEMES:
            p = designsys.load(t)
            for pid, row in designsys.models(p).items():
                if not row.get('turned'):
                    continue
                own = p['panels'][row['series']].get('frame')
                turned += own is not None
                with self.subTest(panel=pid):
                    if own is None:
                        self.assertIsNone(row['frame'])
                        continue
                    want = _turned(own)
                    # Its note describes the series' own page, upright.
                    want['note'] = row['frame']['note']
                    self.assertEqual(_measured(row['frame']), want)
                    self.assertTrue(row['frame']['note'].endswith(own['note']), row['frame']['note'])
                    self.assertIn('upright', row['frame']['note'])
        self.assertTrue(turned)
        m = designsys.models(designsys.load('mach'))
        own = m['TLP1035M']['frame']
        self.assertEqual(m['TLP1035M-Portrait']['frame']['left']['rect'], [0, 0, 64, 1280])
        self.assertEqual(m['TLP1035M-Portrait']['frame']['top']['rect'], _turned(own['left']['rect']))
        self.assertEqual(m['TLP1035M-Portrait']['frame']['center']['region'], _turned(own['center']['region']))
        # Turned, the slider is wide and short, and grows down to the touch minimum.
        slider = _items(m['TLP1035M-Portrait']['frame']['bottom'], 'volume')[0]
        self.assertEqual((slider['rect'], slider['legal']), ([178, 1198, 363, 30], [178, 1187, 363, 53]))


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


def _section(text, heading):
    """A README section's body: from `## heading` to the next `## `."""
    marker = f'\n## {heading}\n'
    if marker not in text:
        return ''
    return text.split(marker, 1)[1].split('\n## ', 1)[0]


class TestWhatThePageSays(unittest.TestCase):
    """What the README's grammar says a page becomes on each family of the
    room's panels - the bar panels, the hubs and the 320 - read off each
    theme's own table and frames; and the Page README's word on a Page that
    draws its own bars, which only a system whose bars are controls has
    (Afterburn's chrome is its background art)."""

    def test_the_grammar_names_each_family_off_its_own_table(self):
        """Read off each table: Turbulence has a 520 hub and no 535."""
        for theme, hubs in (('mach', 'the 520 and 535 Series'), ('shockwave', 'the 520 and 535 Series'),
                            ('turbulence', 'the 520 Series')):
            with self.subTest(theme=theme):
                grammar = _section(designsys.readme(designsys.load(theme)), "The template's grammar")
                self.assertIn(f'### The hubs ({hubs})', grammar)
                self.assertIn('### The 320 (the 320 Series)', grammar)
                self.assertIn('### The bar panels (the ', grammar)

    def test_a_hub_and_the_320_say_what_they_do_with_the_page(self):
        """Round three's designers drew one page and asked what the 525 and
        320 would make of it: the hub's menu bar, Select a Source and its
        options, the 320's pages under the strip with More and Back - each
        in the template's own words, off its frame."""
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                grammar = _section(designsys.readme(p), "The template's grammar")
                hub = designsys.models(p)['TLP525T']['frame']
                self.assertIn(f"'{hub['select']['text']}'", grammar)
                self.assertIn(f"'{hub['options']['text']}'", grammar)
                self.assertIn('menu bar', grammar)
                small = designsys.models(p)['TLP320M']['frame']
                self.assertIn(f"'{small['home']['top']['items'][0]['text']}'", grammar)
                self.assertIn('More', grammar)
                self.assertIn('Back', grammar)

    def test_the_bar_panels_regions_are_the_frames(self):
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                ns = p['namespace']
                grammar = _section(designsys.readme(p), "The template's grammar")
                for comp in ('Header', 'LeftRail', 'RightRail', 'Footer', 'Center'):
                    self.assertIn(f'**{comp}**', grammar)
                F = designsys._design_frame(p)
                self.assertIn(f"{F['top']['tabs']['count']} source tabs", grammar)
                for g in F['left']['groups']:
                    if (g.get('heading') or {}).get('text'):
                        self.assertIn(f"'{g['heading']['text']}'", grammar)
                self.assertIn(f'`{ns}.Header`', grammar)

    def test_afterburns_grammar_is_its_art(self):
        grammar = _section(designsys.readme(designsys.load('afterburn')), "The template's grammar")
        self.assertIn('background art', grammar)
        self.assertNotIn('Header`', grammar)

    def test_a_system_whose_bars_are_controls(self):
        text = designsys._panels_props(designsys.load('mach'))
        self.assertIn('On a large or mid-size panel other than the one drawn', text)
        self.assertIn('get bands of their own carved from main', text)

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


REGIONS = ('Header', 'LeftRail', 'Section', 'RightRail', 'Footer', 'Center')


class TestTheImageComponent(unittest.TestCase):
    """The template's own art as an Image (a PBImage): offered where the
    profile says what its template draws with one and the design panel's
    seed can clone a PBImage - Turbulence's. No Shockwave seed has one."""

    def test_only_turbulence_offers_it(self):
        for t in designsys.TEMPLATES:
            p = designsys.load(t)
            names = [n for n, _, _ in designsys.components(p)]
            self.assertEqual('Image' in names, t == 'turbulence', t)
            self.assertEqual('Image' in designsys.index_dts(p), t == 'turbulence', t)
            self.assertEqual('"image_kind":true' in designsys.bundle(p, art=False), t == 'turbulence', t)

    def test_every_series_says_whether_its_seed_can_build_one(self):
        """The bundle names an Image on a panel whose seed has no PBImage,
        as it does a Level: measured off each seed (measure_series)."""
        for t in designsys.TEMPLATES:
            p = designsys.load(t)
            for series, row in p['panels'].items():
                if not series.startswith('_') and row.get('kinds'):
                    self.assertIn('image', row['kinds'], (t, series))
                    if t == 'shockwave':
                        self.assertFalse(row['kinds']['image'], series)

    def test_its_readme_names_the_templates_art_and_the_device(self):
        p = designsys.load('turbulence')
        doc = designsys.component_docs(p)['Image']
        self.assertIn('`stretch`', doc)
        self.assertIn('1152x1152_lightbulb.png', doc)
        self.assertIn('h(N.Image, ', designsys.previews(p)['Image'])
        page = designsys.component_docs(p)['Page']
        if designsys.kit_index(p)['files'].get('1152x1152'):
            self.assertIn('`device`', page)
            self.assertIn('`laptop`', page)
        self.assertNotIn('`device`', designsys.component_docs(designsys.load('mach'))['Page'])

    def test_the_readme_tells_a_designer_where_the_art_is(self):
        """The README's own sections, not only the Page's and the Image's
        READMEs, say what the region components draw as the template's art
        and where the designer places it: the bars, a source's picture and
        `device`, a hub's popups on the photo and a settings window's
        Image. Without the kit the bars and pictures are drawn flat or not
        at all, and the README says no more than the canvas draws."""
        p = designsys.load('turbulence')
        text = designsys.readme(p)
        grammar, center, windows = (_section(text, h) for h in ("The template's grammar", 'The center', 'Windows'))
        self.assertIn("the page's photo, stretched to the popup", grammar)
        self.assertIn("On a hub** it fills main under the hub's own title, with a Close back to Select a Source, on "
                      "the page's photo", center)
        self.assertIn('`ExtronTurbulence.Image`', windows)
        self.assertIn("Select a Source, on the page's photo", windows)
        docs = designsys.component_docs(p)
        if designsys.kit_index(p)['paths'].get('2047x151_header.png'):
            self.assertIn('`2047x151_header.png` and `1648x134_footer.png`', grammar)
            self.assertIn('`2047x151_header.png`), an Image of it stretched', docs['Header'])
            self.assertIn('`1648x134_footer.png`), an Image of it stretched', docs['Footer'])
        if designsys.kit_index(p)['files'].get('1152x1152'):
            self.assertIn('**Its picture**', center)
            self.assertIn('`device` names the device it pictures', center)
        # Mach draws its bars flat and pins no picture; Shockwave's hubs
        # stand their popups on the photo too, and it offers no Image.
        mach = designsys.readme(designsys.load('mach'))
        self.assertNotIn('its own art -', _section(mach, "The template's grammar"))
        self.assertNotIn('**Its picture**', _section(mach, 'The center'))
        self.assertNotIn("the page's photo", _section(mach, 'Windows'))
        shock = designsys.readme(designsys.load('shockwave'))
        self.assertIn("Select a Source, on the page's photo", _section(shock, 'Windows'))
        self.assertNotIn('.Image`', _section(shock, 'Windows'))


class TestTheRegionComponents(unittest.TestCase):
    """The region frame's components (docs/claude-design.md section 3) are a
    bar theme's: Mach, Shockwave and Turbulence draw their working page in
    bars; Afterburn's system is unchanged."""

    def test_a_bar_theme_has_them_and_afterburn_does_not(self):
        for t in ('mach', 'shockwave', 'turbulence'):
            names = [n for n, _, _ in designsys.components(designsys.load(t))]
            self.assertEqual(names[:len(designsys.COMPONENTS)], [n for n, _, _ in designsys.COMPONENTS], t)
            self.assertEqual([n for n in names[len(designsys.COMPONENTS):] if n != 'Image'], list(REGIONS), t)
        self.assertEqual(designsys.components(designsys.load('afterburn')), designsys.COMPONENTS)

    def test_each_has_a_readme_a_preview_and_a_type(self):
        p = designsys.load('mach')
        docs, cards, dts = designsys.component_docs(p), designsys.previews(p), designsys.index_dts(p)
        for n in REGIONS:
            self.assertIn(f'# {n}\n', docs[n])
            self.assertIn(f'{p["namespace"]}.{n}', docs[n])
            self.assertTrue(cards[n].startswith('<!-- @dsCard group="Regions"'), n)
            self.assertIn(f'N.{n}', cards[n])
            self.assertIn(f'export declare function {n}(', dts)
            self.assertIn(f'{n}: typeof {n}', dts)
        afterburn = designsys.load('afterburn')
        self.assertFalse(set(REGIONS) & set(designsys.component_docs(afterburn)))
        self.assertNotIn('Header', designsys.index_dts(afterburn))

    def test_the_types_carry_what_a_region_reads(self):
        """A region places a control by its `slot`, and a splash page says so:
        a designer working from the types meets both as props, not unknowns."""
        for t in ('mach', 'shockwave', 'turbulence'):
            dts = designsys.index_dts(designsys.load(t))
            for props in ('ButtonProps', 'LabelProps', 'TrackProps', 'ClockProps'):
                decl = re.search(r'export interface ' + props + r' \{([^\n]*)\}', dts)
                self.assertIsNotNone(decl, (t, props))
                self.assertIn('slot?: string', decl.group(1), (t, props))
            page = re.search(r'export interface PageProps \{([^\n]*)\}', dts).group(1)
            self.assertIn('splash?: boolean | string', page, t)
        dts = designsys.index_dts(designsys.load('afterburn'))
        self.assertNotIn('slot?:', dts)
        self.assertNotIn('splash?:', dts)

    def test_the_header_names_them(self):
        js = designsys.bundle(designsys.load('mach'), art=False)
        head = json.loads(re.match(r'/\* @ds-bundle: (\{.*?\}) \*/', js).group(1))
        self.assertEqual([c['name'] for c in head['components']][-len(REGIONS):], list(REGIONS))

    def test_the_frame_is_in_the_bundle_once_per_series(self):
        """Keyed by series, not repeated on every model row (190-320 KB a
        theme), and only the series the regions draw - the bar series of tier
        A, with all five bands, the hubs
        (test_the_hubs_frames_are_in_the_bundle) and the 320s
        (test_the_320s_frames_are_in_the_bundle) - so the bundle stays small
        without its art, with the kit's index in it where the kit is here
        (about 390 KB for Mach, its windows slimmed to their rects and looks,
        about 1.7 KB a series; a hub's whole frame about 3 KB)."""
        for t in ('mach', 'shockwave', 'turbulence'):
            p = designsys.load(t)
            js = designsys.bundle(p, art=False)
            prof = json.loads(re.search(r'var P = (\{.*?\});\n', js).group(1))
            tiers = {}
            for row in designsys.models(p).values():
                tiers.setdefault(row['series'], set()).add(row['tier'])
            series = {s for s, v in p['panels'].items() if not s.startswith('_') and v.get('frame')
                      and all(v['frame'].get(b) for b in ('top', 'left', 'right', 'bottom', 'center'))
                      and 'C' not in tiers.get(s, {'C'})}
            self.assertTrue(series, t)
            self.assertEqual({s for s, f in prof['frames'].items() if not f.get('hub') and not f.get('pages')},
                             series, t)
            # What the regions read of each: the bars, the center's popup
            # region, well, titles (an empty source's and one with controls),
            # empty state, status, type sizes, surfaces and each device's
            # picture, and the windows.
            for s, f in prof['frames'].items():
                if f.get('hub') or f.get('pages'):
                    continue
                own = p['panels'][s]['frame']
                self.assertEqual(sorted(f), ['bottom', 'center', 'left', 'right', 'top', 'windows'], s)
                self.assertEqual(f['center'], {k: own['center'].get(k) for k in
                                               ('region', 'well', 'title', 'title_controls', 'empty',
                                                'status', 'pt', 'surfaces', 'pictures')}, s)
                # Each window's rects, surfaces and its Close's and buttons' roles.
                self.assertEqual(f['windows'], designsys._slim_windows(own['windows']), s)
                self.assertEqual(f['windows']['confirm']['rect'], own['windows']['confirm']['rect'], s)
                self.assertEqual(f['top'], own['top'], s)
            self.assertFalse(any('frame' in row for row in prof['models'].values()), t)
            # A backstop, not a limit of the Design type's: a frame repeated
            # on every model row doubled the bundle. Mach's is about 431 KB
            # with the 320's pages (PR7), round four's layout (the 320's
            # words and windows, the 725's audio place) and the 320's capitals.
            self.assertLess(len(js.encode('utf-8')), 435_000, t)
        # Afterburn draws no bars: no frame in its bundle.
        js = designsys.bundle(designsys.load('afterburn'), art=False)
        self.assertEqual(json.loads(re.search(r'var P = (\{.*?\});\n', js).group(1))['frames'], {})

    def test_the_hubs_frames_are_in_the_bundle(self):
        """Each hub series' frame, as its region page, source popups and
        windows draw it (bundle.js planHub): its menu bar and header strip,
        the popup region with what a source's popup draws and the Volume
        Level strip, its Select a Source and options grids, and its windows.
        Not a 320's."""
        for t in ('mach', 'shockwave', 'turbulence'):
            p = designsys.load(t)
            js = designsys.bundle(p, art=False)
            prof = json.loads(re.search(r'var P = (\{.*?\});\n', js).group(1))
            hubs = {s for s, f in prof['frames'].items() if f.get('hub')}
            want = {s for s, v in p['panels'].items() if not s.startswith('_') and (v.get('frame') or {}).get('select')}
            self.assertEqual(hubs, want, t)
            self.assertTrue(hubs, t)
            for s in hubs:
                f, own = prof['frames'][s], p['panels'][s]['frame']
                self.assertEqual(sorted(f), ['center', 'hub', 'options', 'right', 'select', 'top', 'windows'], s)
                self.assertEqual((f['right'], f['top'], f['select'], f['options']),
                                 (own['right'], own['top'], own['select'], own['options']), s)
                strip = next(it['rect'] for it in own['center']['items'] if it['role'] == 'popup')
                self.assertEqual((f['center']['region'], f['center']['strip'], f['center']['close'],
                                  f['center']['pictures']),
                                 (own['center']['region'], strip, own['center']['close'],
                                  own['center'].get('pictures')), s)
                self.assertEqual(f['windows'], designsys._slim_windows(own['windows']), s)

    def test_the_320s_frames_are_in_the_bundle(self):
        """Each 320 series' frame, as its region page, source pages and
        windows draw it (bundle.js planPages, pagePart): its strip, its home's
        and its second page's, the centre's row, headings, steps, sizes,
        empty state and More, its windows with their buttons' seed IDs, and
        its Volume modal. Not a 300's, whose menu bar is not drawn yet."""
        for t in ('mach', 'shockwave', 'turbulence'):
            p = designsys.load(t)
            prof = json.loads(re.search(r'var P = (\{.*?\});\n', designsys.bundle(p, art=False)).group(1))
            pages = {s for s, f in prof['frames'].items() if f.get('pages')}
            self.assertEqual(pages, {f'{t.title()} 320 Series'}, t)
            for s in pages:
                f, own = prof['frames'][s], p['panels'][s]['frame']
                self.assertEqual(sorted(f), ['center', 'home', 'pages', 'second', 'top', 'volume', 'windows'], s)
                self.assertEqual((f['top'], f['home']['top'], f['second']['top'], f['volume']),
                                 (own['top'], own['home']['top'], own['second']['top'], own['volume']), s)
                self.assertEqual(f['center'], {k: own['center'].get(k) for k in
                                               ('rect', 'row', 'headings', 'pitch', 'pt', 'empty', 'empty_lines',
                                                'items')}, s)
                # The question's own words, and the empty state's lines.
                self.assertEqual(f['windows']['confirm']['text'], own['windows']['confirm']['text'], s)
                self.assertEqual(len(f['center']['empty_lines']), 3, s)
                self.assertEqual(f['windows'], designsys._slim_windows(own['windows'], ids=True), s)
                self.assertEqual([b['id'] for b in f['windows']['confirm']['buttons']],
                                 [b['id'] for b in own['windows']['confirm']['buttons']], s)

    def test_the_320s_page_looks_exist(self):
        """`regions.page` names only the profile's own variants, colors and
        kit icons, and widens a key only to a variant with art."""
        for t in ('mach', 'shockwave', 'turbulence'):
            p = designsys.load(t)
            colors, page = {c['name'] for c in p['colors']}, p['regions']['page']
            files = designsys.kit_index(p)['files']
            for key, look in page.items():
                if key.startswith('_') or not isinstance(look, dict):
                    continue
                with self.subTest(theme=t, key=key):
                    if 'variant' in look:
                        self.assertIn(look['variant'], p['buttons'])
                    if 'color' in look:
                        self.assertIn(look['color'], colors)
                    if look.get('icon') and files:
                        V = p['buttons'][look['variant']]
                        size = V.get('kit') or (V.get('with_icon') or {}).get('bare')
                        self.assertIn(look['icon'], files[size])
            for v in page.get('wider', []):
                self.assertTrue(p['buttons'][v].get('kit'), (t, v))

    def test_a_panel_draws_its_own_seeds_corners(self):
        """Every project carries its own copy of the built-in borders, and
        Build draws the panel's: Shockwave's hubs and 320 round 2D Rounded
        Rectangle at 10 px where its 1035 and 725 do at 2, so a hub's cards
        came out near-square on the canvas and round on the panel. The model
        row carries the seed's (`radii`), measured where the seeds are."""
        p = designsys.load('shockwave')
        rows = designsys.models(p)
        self.assertEqual([rows[m]['radii'] for m in ('TLP525T', 'TLP535T', 'TLP320M', 'TLP1035T', 'TLP725T')],
                         [{'rounded': 10}] * 3 + [{}] * 2)
        js = designsys.bundle(p, art=False)
        prof = json.loads(re.search(r'var P = (\{.*?\});\n', js).group(1))
        self.assertEqual(prof['models']['TLP525T']['radii'], {'rounded': 10})
        sys.path.insert(0, os.path.join(REPO, 'tests'))
        import measure_series
        from gdl import seeds
        from gdl.project import Project
        for series, row in p['panels'].items():
            if series.startswith('_') or not any(m in ('TLP525T', 'TLP535T', 'TLP320M', 'TLP1035T', 'TLP725T')
                                                 for m in row['models']):
                continue
            seed = measure_series.series_seed(row)
            if not seeds.usable(seed):
                continue
            with self.subTest(series=series):
                got = measure_series.seed_radii(Project.open(seeds.path(seed)), p['borders'])
                self.assertEqual(got, row.get('radii') or {})

    def test_the_hubs_looks_exist(self):
        """`regions.hub` names only the profile's own variants and colors."""
        for t in ('mach', 'shockwave', 'turbulence'):
            p = designsys.load(t)
            colors = {c['name'] for c in p['colors']}
            hub = p['regions']['hub']
            looks = dict(hub, **{'options ' + k: v for k, v in hub['options'].items() if isinstance(v, dict)})
            for key, look in looks.items():
                with self.subTest(theme=t, key=key):
                    if 'variant' in look:
                        self.assertIn(look['variant'], p['buttons'])
                    for k in ('color', 'background'):
                        if k in look:
                            self.assertIn(look[k], colors)

    def test_the_writing_is_in_the_bundle(self):
        """The template's own words, which the center and the windows draw."""
        for t in ('mach', 'shockwave', 'turbulence'):
            p = designsys.load(t)
            prof = json.loads(re.search(r'var P = (\{.*?\});\n', designsys.bundle(p, art=False)).group(1))
            # Not its voice, which is the README's and the caption lint's, not the canvas's.
            self.assertEqual(prof['writing'], {k: v for k, v in p['writing'].items()
                                               if not k.startswith('_') and k != 'voice'}, t)

    def test_the_page_props_carry_a_role(self):
        """A source popup and a window say what they are (`role`, `topic`,
        `title`): a designer working from the types meets them as props."""
        for t in ('mach', 'shockwave', 'turbulence'):
            page = re.search(r'export interface PageProps \{([^\n]*)\}', designsys.index_dts(designsys.load(t))).group(1)
            for prop in ("role?: 'source' | 'settings' | 'help' | 'confirm' | 'wait'", 'topic?: string', 'title?: string'):
                self.assertIn(prop, page, t)
        page = re.search(r'export interface PageProps \{([^\n]*)\}',
                         designsys.index_dts(designsys.load('afterburn'))).group(1)
        self.assertNotIn('role?:', page)


class TestTheWriting(unittest.TestCase):
    """Each bar theme's profile holds its template's own words (`writing`),
    measured off its seeds' source popups and windows: the empty state of a
    source with no controls, the power-down question, the waits, the Help
    message and the buttons' words. The center and the windows draw them."""

    WORDS = {
        'mach': ('{name} is currently selected.\nThere are no controls for this device.',
                 'Do you want to power down the system?',
                 'Please wait while the system is powering down.'),
        'shockwave': ('Please connect your {noun}.', 'Do you want to\npower down the system?',
                      'Please wait while the\nsystem is powering down.'),
        'turbulence': ('{name} is currently selected.\nThere are no controls for this device.',
                       'Do you want to power down the system?',
                       'Please wait while the system is\npowering down.'),
    }

    def test_each_bar_theme_has_its_templates_words(self):
        for t, (empty, confirm, down) in self.WORDS.items():
            with self.subTest(theme=t):
                w = designsys.load(t)['writing']
                self.assertTrue(w['_source'])
                self.assertEqual(w['empty'], empty)
                self.assertEqual(w['confirm'], {'power': confirm})
                self.assertEqual(w['wait']['down'], down)
                self.assertIn('starts up.', w['wait']['up'])
                self.assertEqual(w['buttons'], {'power': 'Power Down', 'cancel': 'Cancel', 'close': 'Close'})
                self.assertTrue(w['help'].startswith('For assistance, please call the help desk at:'))
        # The 320 breaks the empty state over three lines.
        for t in self.WORDS:
            self.assertEqual(designsys.load(t)['writing']['page_empty'],
                             '{name} is currently selected.\nThere are no controls\nfor this device.', t)
        # Shockwave's empty source also shows a status the program sets.
        self.assertEqual(designsys.load('shockwave')['writing']['status'], 'Disconnected')
        # Afterburn's are the words a designer writes: its system draws no region to say them.
        w = designsys.load('afterburn')['writing']
        self.assertEqual(w['confirm'], {'power': 'Do you want to power down the system?'})
        self.assertNotIn('page_empty', w)

    def test_every_theme_has_its_voice(self):
        """How the template words a caption (`writing.voice`), which the
        README's Writing says and the caption lint holds it to."""
        for t in designsys.TEMPLATES:
            with self.subTest(theme=t):
                v = designsys.load(t)['writing']['voice']
                self.assertIn('seeds/', v['_source'])
                self.assertTrue(v['rules'] and v['launchers'] and v['instead'])
                for ours, theirs in v['instead'].items():
                    self.assertNotIn(theirs, v['instead'], (ours, theirs))

    def test_the_looks_the_center_and_windows_give_exist(self):
        """`regions.source` and `regions.window` name only the profile's own
        variants, colors, type and borders."""
        for t in ('mach', 'shockwave', 'turbulence'):
            p = designsys.load(t)
            colors = {c['name'] for c in p['colors']}
            for part in ('source', 'window'):
                looks = p['regions'][part]
                self.assertIn('title', looks, (t, part))
                for key, look in looks.items():
                    with self.subTest(theme=t, part=part, key=key):
                        if 'variant' in look:
                            self.assertIn(look['variant'], p['buttons'])
                        if 'color' in look:
                            self.assertIn(look['color'], colors)
                        if 'size' in look:
                            self.assertGreaterEqual(look['size'], MIN_BODY_POINT_SIZE)


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

    SECTIONS = ('Designing a panel', "The template's grammar", 'The working page', 'The center', 'Windows',
                'Writing', 'Before you hand it over', 'Pages without regions', 'Differences', 'Layout',
                'Every panel the room has', 'Themes', 'Visual foundations', 'Iconography',
                'Consuming this system')

    def test_the_readme_is_written_around_the_templates_grammar(self):
        """What a designer reads first is the template's grammar - its five
        regions, the working page drawn in them, its center, its windows and
        its words - then what to check before handing over, the pages that
        are not working pages, and where we differ; the measured Layout and
        each panel's room follow. Afterburn draws its chrome as art and has
        no regions, so no section on pages without them."""
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                heads = re.findall(r'^## (.+)$', designsys.readme(p), re.M)
                want = [s for s in self.SECTIONS if not (theme == 'afterburn' and s == 'Pages without regions')]
                self.assertEqual(heads, want)

    def test_the_grammar_shows_the_templates_own_working_page(self):
        """A render of each family's working page off its seed - the bar
        panel's, the hub's and the 320's - is a file of the system, shown
        beside the grammar (the owner's call 3: private only)."""
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                grammar = _section(designsys.readme(p), "The template's grammar")
                plan = designsys.template_renders(p)
                pages = [r for r in plan if not r.get('window')]
                self.assertEqual([r['family'] for r in pages], ['bar', 'hub', 'pages'])
                for r in pages:
                    self.assertIn(f"]({r['file']})", grammar)
                    self.assertIn(r['page'], grammar)
                # And the bar panel's question and a settings window, over its
                # working page, beside the Windows they show.
                wins = _section(designsys.readme(p), 'Windows')
                shown = [r for r in plan if r.get('window')]
                self.assertEqual([r['window'] for r in shown], ['confirm', 'settings'])
                for r in shown:
                    self.assertIn(f"]({r['file']})", wins)
                    self.assertEqual(r['base'], pages[0]['page'])
                # Only what a build wrote is shown.
                none = designsys.readme(p, renders=[])
                self.assertNotIn('](templates/', none)

    def test_the_working_page_is_a_complete_example(self):
        """The working page in its regions, and every artboard it leads to: a
        source with no controls and one with them, a settings window, Help,
        the power-down question and its wait - each a Page whose `nav` names
        an artboard the example draws."""
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                ns = p['namespace']
                section = _section(designsys.readme(p), 'The working page')
                blocks = re.findall(r'```html\n(.*?)```', section, re.S)
                self.assertGreaterEqual(len(blocks), 6)
                code = '\n'.join(blocks)
                # Start, then the working page in its regions.
                self.assertIn('start="true"', blocks[0])
                main = next(b for b in blocks if f'"{ns}.Header"' in b)
                for comp in ('Header', 'LeftRail', 'Section', 'RightRail', 'Footer', 'Center'):
                    self.assertIn(f'"{ns}.{comp}"', main)
                self.assertNotIn('MainArea', main)
                for role in ('role="source"', 'role="settings"', 'role="help"', 'role="confirm" topic="power"',
                             'role="wait" topic="down"'):
                    self.assertIn(role, code)
                stems = set(_boards(section))
                for target in re.findall(r'(?:nav|help|power)="([^"]+)"', code):
                    self.assertIn(target, stems)
                first = designsys._design_frame(p)['left']['groups'][0]
                self.assertIn(f'title="{first["heading"]["text"]}"', main)
                # The launchers say what the template's say.
                for word in p['writing']['voice']['launchers']:
                    self.assertIn(f'>{word}</x-import>', main)
        section = _section(designsys.readme(designsys.load('afterburn')), 'The working page')
        self.assertIn('MainArea"', section)
        self.assertIn('PopupRegion"', section)

    def test_the_center_says_how_a_source_shows_its_controls(self):
        """Round three's designers asked where a source's controls go: in a
        popup of the Center's group, `role="source"`, which draws the
        template's well, title and empty state in the template's words."""
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                center = _section(designsys.readme(p), 'The center')
                self.assertIn('role="source"', center)
                self.assertIn('kind="popup"', center)
                w = p['writing']
                self.assertIn(' '.join(w['empty'].split()).format(name='Laptop', noun='laptop'), center)
                if w.get('status'):
                    self.assertIn(w['status'], center)
                self.assertIn('On a hub', center)
                self.assertIn('On a 320', center)
        center = _section(designsys.readme(designsys.load('afterburn')), 'The center')
        self.assertIn('PopupRegion', center)
        self.assertIn('PC is currently selected.', center)

    def test_the_windows_are_drawn_by_role(self):
        """Help, the question, the waits and settings are the template's
        windows, drawn from the frame - the owner's rule unchanged: nothing
        forces a confirmation."""
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                wins = _section(designsys.readme(p), 'Windows')
                for role in ('settings', 'help', 'confirm', 'wait'):
                    self.assertIn(f'`role="{role}"`', wins)
                w = p['writing']
                self.assertIn(' '.join(w['confirm']['power'].split()), wins)
                self.assertIn(' '.join(w['wait']['down'].split()), wins)
                self.assertIn(w['buttons']['power'], wins)
                self.assertIn('not a rule', wins)
        wins = _section(designsys.readme(designsys.load('afterburn')), 'Windows')
        self.assertIn('kind="modal"', wins)
        self.assertIn('Help', wins)
        self.assertIn('not a rule', wins)

    def test_the_writing_is_the_templates_own(self):
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                writing = _section(designsys.readme(p), 'Writing')
                w = p['writing']
                for said in (w['confirm']['power'], w['wait']['up'], w['wait']['down'], w['help']):
                    self.assertIn(' '.join(said.split()), writing)
                for rule in w['voice']['rules']:
                    self.assertIn(rule, writing)
                for ours, theirs in w['voice']['instead'].items():
                    self.assertRegex(writing, re.escape(theirs) + r', not [^;]*?\b' + re.escape(ours) + r'\b')

    def test_before_you_hand_it_over_is_a_checklist(self):
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                section = _section(designsys.readme(designsys.load(theme)), 'Before you hand it over')
                items = [ln for ln in section.splitlines() if ln.startswith('- [ ] ')]
                self.assertGreaterEqual(len(items), 6)
                for want in ('`panels`', 'translate', 'compare', '--template', '`id`', 'Writing'):
                    self.assertIn(want, section)

    def test_the_differences_are_the_ledgers_deviations(self):
        """Written from the ledger's `deviation` entries, so they cannot
        drift from it."""
        from gdl.designsys import audit
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                section = _section(designsys.readme(designsys.load(theme)), 'Differences')
                devs = [e for e in audit.load_ledger(theme)['entries'] if e['status'] == 'deviation']
                self.assertTrue(devs)
                for e in devs:
                    self.assertIn(e['here'], section)
                self.assertEqual(len([ln for ln in section.splitlines() if ln.startswith('- ')]), len(devs))

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

    def test_turbulences_hub_room_is_read_with_its_own_source_tabs(self):
        """Turbulence's Layout puts six source tabs across its header, and on a
        hub a band is as deep as a Group it holds - 118 px on the 525 with the
        seed's captions (`layout.hub_header`, measured) where the table took a
        button's 66, and promised a button beside the volume that the tabs
        leave no room for (review of #39)."""
        text = designsys.readme(designsys.load('turbulence'))
        section = text.split('## Every panel the room has', 1)[1].split('\n## ', 1)[0]
        hub = next(ln for ln in section.splitlines() if ln.startswith('| ') and 'TLP525' in ln)
        self.assertIn('| hub: its rail holds a heading and the volume |', hub)
        self.assertIn('| 124 px, 29 px |', hub)
        self.assertIn("the Layout's own source tabs", section)

    def test_a_measured_hub_header_covers_every_hub(self):
        """A hub with no measured depth would read a button's again, silently
        (review of #40)."""
        for theme in ('shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                hubs = {m for m, T in designsys.models(p).items() if T['tier'] == 'B'}
                self.assertEqual(set(p['layout']['hub_header']['depth']), hubs)

    def test_a_hubs_rail_count_keeps_room_for_its_heading(self):
        """Mach's, Shockwave's and Turbulence's Layouts head their volume rail
        ("Volume"), a line at the hub's type and a gap - 47 px on the 525 -
        and the count left it out: the round-three Shockwave room's rail of a
        heading, the volume and Mute needed 344 px of its 320. Mach's 525 has
        room for one button under it; Afterburn's rail has no heading."""
        for theme, kind in (('shockwave', 'a heading and the volume'),
                            ('mach', 'a heading, the volume and 1 button'),
                            ('afterburn', 'the volume and 3 buttons')):
            with self.subTest(theme=theme):
                text = designsys.readme(designsys.load(theme))
                section = text.split('## Every panel the room has', 1)[1].split('\n## ', 1)[0]
                hub = next(ln for ln in section.splitlines() if ln.startswith('| ') and 'TLP525' in ln)
                self.assertIn(f'| hub: its rail holds {kind} |', hub)

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

    def test_no_example_file_name_or_nav_has_a_space(self):
        """The Design type forbids spaces in a file name and a nav resolves by
        file stem only, so the README's examples printed `Main SD.dc.html` and
        `nav="Main SD"` that every designer had to rewrite. A Page's `name`
        may have spaces; a stem may not."""
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                texts = [designsys.readme(p)] + list(designsys.component_docs(p).values())
                stems = [m for t in texts for m in re.findall(r'`([^`\n]*)\.dc\.html`', t)]
                navs = [m for t in texts for m in re.findall(r'\b(?:nav|help|power)="([^"]*)"', t)]
                self.assertTrue(stems and navs)
                for s in stems + navs:
                    self.assertNotRegex(s, r'\s', s)

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

    def test_afterburns_example_keeps_inside_its_main_region(self):
        """Afterburn's Example is its Start page, placed in the squircle; its
        Clock sat 696 px down a MainArea 752 deep and below every bar
        theme's. The bar themes show their working page in regions instead,
        with no MainArea (test_the_working_page_is_a_complete_example)."""
        p = designsys.load('afterburn')
        section = _section(designsys.readme(p), 'The working page')
        inside = section.split('MainArea"', 1)[1].split('\n  </x-import>', 1)[0]
        tops = re.findall(r'top: (\d+)px; width: [\d%]+(?:px)?; height: (\d+)px', inside)
        self.assertTrue(tops)
        for top, h in tops:
            self.assertLessEqual(int(top) + int(h), p['layout']['main'][3])

    def test_the_readme_answers_what_every_designer_asked(self):
        """What the fresh designers asked, round by round. Rounds one to
        three (archive/job-2419a20b/prose-in/README.md): a `nav` reaches the
        programmer, not the panel - the ID map says "Shows page 'Main'" - so
        a modal opened from two pages and closed with nav="Main" sent the
        call page home; a program page may also be led to; a control on two
        pages is two controls unless it shares an `id`. And what the owner
        found the round-three rooms lacked, which their designers had to
        guess: where Help goes, how a source shows its controls, what a
        window looks like, which words the template uses, and what a hub
        and the 320 make of the page."""
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                text = designsys.readme(p)
                wins = _section(text, 'Windows')
                self.assertIn('does="Closes this popup."', wins)
                self.assertIn('more than one page', wins)
                program = next(ln for ln in text.splitlines() if ln.startswith('- **A page or popup the program opens'))
                self.assertIn('may lead to it as well', program)
                several = next(ln for ln in text.splitlines() if ln.startswith('- **A control on several pages**'))
                self.assertIn('the same `id`', several)
                self.assertIn('`nav`', several)
                # Where does Help go? The footer's, on a hub Select a Source's, on the 320 a page of Main's own.
                grammar = _section(text, "The template's grammar")
                self.assertIn('Help', next(ln for ln in grammar.splitlines() if ln.startswith('- **Footer**')
                                           or ln.startswith('- **RightRail**') and 'Help' in ln))
                self.assertIn('**Where Help goes.**', text)
                # How does a source show its controls?
                self.assertIn('**How a source shows its controls.**', _section(text, 'The center'))
                # What does a window look like? Its band or card, off the frame, in the template's colour.
                look = next(ln for ln in wins.splitlines() if ln.startswith('- **What a window looks like.**'))
                F = designsys._design_frame(p)
                fill = next(s['fill'] for s in F['windows']['confirm']['surfaces'] if s.get('fill'))
                self.assertIn(fill[:7], look)
                # Which words? The template's own, and how it says them.
                self.assertIn(' '.join(p['writing']['confirm']['power'].split()), _section(text, 'Writing'))
                # What does a hub or the 320 do with my page?
                self.assertIn('**What a hub makes of your page.**', text)
                self.assertIn('**What the 320 makes of your page.**', text)

    def test_the_readme_answers_what_round_four_got_wrong(self):
        """Round four's designers (tests/data/round4-<theme>) drew Help as a
        stack of one-line Labels, as 'break help into short lines' told them,
        and it overflowed at the 525's 18 pt; captioned the 320's keys and
        headed its columns in words wider than they are; drew a Display
        Control the hub derives, and two working pages; and put Mic Mute in
        the RightRail's audio place, which Shockwave's 725 keeps in its left
        rail. Each README now says it."""
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                text = designsys.readme(p)
                ms = designsys.models(p)
                self.assertNotIn('break help into short lines', text)
                words = next(ln for ln in text.splitlines() if ln.startswith('- **Words.**'))
                self.assertIn('one Label', words)
                self.assertIn("a state's own `text`", words)
                self.assertIn('one Label', next(ln for ln in text.splitlines() if ln.startswith('- `role="help"`')))
                grammar = _section(text, "The template's grammar")
                hub = ms['TLP525T']['frame']
                drawn = grammar.split('**What it draws by itself, and what you may draw.**', 1)[1].split('\n\n', 1)[0]
                for name in ((hub.get('select') or {}).get('popup') or 'Select Source',
                             (hub.get('options') or {}).get('popup') or 'More Options', 'Volume Level'):
                    self.assertIn(f"'{name}'", drawn)
                self.assertIn('the same `id`s', drawn)
                # A revision drawn in another order renamed those windows and
                # retired their IDs (docs/idmap.md §9).
                self.assertIn('order of the working pages', drawn)
                small = grammar.split('**Words on the 320.**', 1)[1].split('\n\n', 1)[0]
                key = ms['TLP320M']['frame']['center']['row'][0]
                self.assertIn(f'{key[2]}x{key[3]}', small)
                self.assertIn("`Group`'s `title`", small)
                self.assertIn('**What it draws by itself.**', grammar)
                rail = next(ln for ln in grammar.splitlines() if ln.startswith('- **RightRail**'))
                if theme == 'shockwave':
                    self.assertIn('1020', rail)
                    self.assertIn("left rail's second group", rail)
                for doc, needle in (('Group', 'Words on the 320'), ('RightRail', 'left rail instead')):
                    if needle == 'left rail instead' and theme == 'mach':
                        continue
                    self.assertIn(needle, designsys.component_docs(p)[doc], (theme, doc))

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
        # Shockwave's tabs are a set the template stands 1 px apart, which the
        # Layout says as the frame measures it - not flush, and no hand-written
        # header line to drift from it (the truth ledger, shockwave-00).
        layout = designsys.readme(designsys.load('shockwave')).split('## Layout', 1)[1].split('\n## ', 1)[0]
        self.assertIn('one every 153 px (1 px apart)', layout)
        self.assertNotIn('flush', layout)

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


def _boards(section):
    """{file stem: markup} of a README section's artboards, each given as
    `` `<stem>.dc.html`: `` over its code block."""
    return dict(re.findall(r'`([^`]+)\.dc\.html`:\n\n```html\n(.*?)```', section, re.S))


def _bullet(section, name):
    return next((ln for ln in section.splitlines() if ln.startswith(f'- **{name}**')), '')


BAR = ('mach', 'shockwave', 'turbulence')


class TestWhatAFreshDesignerFound(unittest.TestCase):
    """What a designer who read only the built READMEs found contradictory or
    missing (the PR8 review): each README says one thing once, its examples
    are what it tells a designer to draw, and every artboard they lead to is
    shown."""

    def test_the_rightrail_names_nothing_the_footer_takes(self):
        """planRightRail leaves Power and Help to the Footer wherever the
        template stands them; Shockwave's grammar put Power in the RightRail's
        bullet and its working page in the Footer's."""
        for theme in BAR:
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                grammar = _section(designsys.readme(p), "The template's grammar")
                right, footer = _bullet(grammar, 'RightRail'), _bullet(grammar, 'Footer')
                self.assertNotIn('Power', right)
                self.assertNotIn('Help', right)
                for word in ('Help', 'Power', 'the date and time', 'only where you give it one'):
                    self.assertIn(word, footer)
        footer = _bullet(_section(designsys.readme(designsys.load('shockwave')), "The template's grammar"), 'Footer')
        self.assertIn('at the foot of the right rail', footer)

    def test_the_power_key_says_what_the_template_captions_it(self):
        """Shockwave's power key says Off, Mach's and Turbulence's are their
        icon alone; the question they open answers Power Down."""
        for theme, said in (('shockwave', "captioned 'Off'"), ('mach', 'its icon alone'),
                            ('turbulence', 'its icon alone')):
            with self.subTest(theme=theme):
                footer = _bullet(_section(designsys.readme(designsys.load(theme)), "The template's grammar"),
                                 'Footer')
                self.assertIn(said, footer)
                self.assertIn('answers Power Down', footer)

    def test_help_is_a_window_on_its_own_artboard_and_a_page_on_the_320(self):
        for theme in designsys.TEMPLATES:
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                text = designsys.readme(p)
                self.assertNotIn('never a page', text)
                where = next(ln for ln in text.splitlines() if ln.startswith('**Where Help goes.**'))
                self.assertIn('320', where)
                hub = designsys.models(p)['TLP525T']['frame']
                if (hub.get('select') or {}).get('help'):
                    self.assertIn("at the top of 'Select a Source'", where)
                else:
                    self.assertNotIn("on 'Select a Source'", where)
                    self.assertIn('in its rail', where)
                if theme != 'afterburn':
                    self.assertIn('`role="help"`', where)
                    self.assertIn('page under the strip', where)

    def test_the_example_boots_to_main_dc_html(self):
        """The README names the start page's file Main.dc.html, and its
        complete example was a working page of that name with no `start`,
        leading from a Start it never showed. Every Page carries `panels`
        and, where the system has themes, `theme`."""
        for theme in designsys.TEMPLATES:
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                boards = _boards(_section(designsys.readme(p), 'The working page'))
                start = boards.get('Main', '')
                self.assertIn('start="true"', start)
                if theme != 'afterburn':
                    self.assertIn('splash="true"', start)
                led = re.findall(r'nav="([^"]+)"', start)
                self.assertTrue(led)
                self.assertTrue(all(n in boards for n in led), led)
                self.assertEqual(sum('start="true"' in b for b in boards.values()), 1)
                for name, code in boards.items():
                    page = re.search(r'\.Page"([^>]*)>', code).group(1)
                    self.assertIn('panels="', page, name)
                    if p.get('themes'):
                        self.assertIn('theme="', page, name)

    def test_every_example_tab_draws_its_own_glyph(self):
        """Shockwave's PC and Doc Cam tabs named no icon, so the source look
        drew its default laptop on them."""
        for theme in BAR:
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                names = designsys.icon_names(p).get(p['regions']['tab']['variant']) or []
                if not names:
                    self.skipTest('the kit is not here')
                section = _section(designsys.readme(p), 'The working page')
                tabs = re.findall(r'<x-import [^>]*slot="source"[^>]*>', section)
                self.assertGreaterEqual(len(tabs), 3)
                for tab in tabs:
                    icon = re.search(r'icon="([^"]+)"', tab)
                    self.assertTrue(icon, tab)
                    self.assertIn(icon.group(1), names)
                self.assertIn('Streaming', section)

    def test_the_word_rules_are_for_buttons_and_window_titles_keep_theirs(self):
        """'Lighting, not Lighting Settings' was unscoped, against the
        README's own rule and example that title the window Lighting
        Settings; the caption lint applies it to captions alone."""
        for theme in designsys.TEMPLATES:
            with self.subTest(theme=theme):
                writing = _section(designsys.readme(designsys.load(theme)), 'Writing')
                line = next(ln for ln in writing.splitlines() if 'not Power Off' in ln)
                self.assertTrue(line.startswith('- On a button, say what'), line)
                self.assertIn("A window's title", line)

    def test_machs_capitals_are_its_seeds(self):
        """Mach's 320 heads its camera keys ZOOM and FOCUS, its 525 DISPLAYS
        and SCREENS; the README said Mach sets none in capitals."""
        p = designsys.load('mach')
        for word in ('ZOOM', 'FOCUS', 'INPUTS', 'IRIS', 'DISPLAYS', 'SCREENS', 'TITLE'):
            self.assertIn(word, p['writing']['voice']['caps'])
        for theme in designsys.TEMPLATES:
            self.assertNotIn('sets none in capitals', designsys.readme(designsys.load(theme)))
        # An empty list says nothing of capitals, rather than that there are none.
        q = json.loads(json.dumps(p))
        q['writing']['voice']['caps'] = []
        line = next(ln for ln in _section(designsys.readme(q), 'Writing').splitlines() if 'Title Case' in ln
                    and ln.startswith('- Captions'))
        self.assertNotIn('capitals', line)

    def test_the_section_and_leftrail_examples_are_in_the_themes_words(self):
        """Shockwave's and Turbulence's Section README showed Mach's Settings
        heading over a Lighting Settings launcher captioned Lighting."""
        for theme in BAR:
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                docs = designsys.component_docs(p)
                voice = p['writing']['voice']
                groups = designsys._design_frame(p)['left']['groups']
                second = (groups[1].get('heading') or {}).get('text') if len(groups) > 1 else None
                launcher = voice['launchers'][-1]
                self.assertIn(f'>{launcher}</x-import>', docs['Section'])
                self.assertIn(f'name="{launcher}"', docs['Section'])
                if second:
                    self.assertIn(f'title="{second}"', docs['Section'])
                    self.assertIn(f'({second})', docs['LeftRail'])
                else:
                    self.assertNotIn('title="Settings"', docs['Section'])
                    self.assertNotIn('(Settings)', docs['LeftRail'])
                from gdl.designsys import audit
                self.assertEqual([c for c in audit.caption_lint(p, docs['Section']) if c[0] == 'README'], [])

    def test_the_empty_state_names_its_source(self):
        """Shockwave's empty state takes the source's name ('Please connect
        your PC.') over a status the program sets."""
        center = _section(designsys.readme(designsys.load('shockwave')), 'The center')
        self.assertIn("'Please connect your PC.'", center)
        self.assertIn('the program sets', center)

    def test_a_window_says_which_frame_and_which_answer_where(self):
        """Shockwave draws its Screen and Audio Control windows wider than the
        rest, and its question puts Cancel at the left; Turbulence's Power
        Down rests green there."""
        wins = _section(designsys.readme(designsys.load('shockwave')), 'Windows')
        look = _bullet(wins, 'What a window looks like.')
        self.assertIn('832x651 at 224,74', look)
        self.assertIn('1028x651 at 126,74', look)
        self.assertIn('Screen Control', look)
        self.assertIn('Cancel at the left and Power Down at the right', look)
        look = _bullet(_section(designsys.readme(designsys.load('turbulence')), 'Windows'), 'What a window looks like.')
        self.assertIn('Power Down at the left and Cancel at the right', look)
        self.assertIn('`green`', look)

    def test_the_example_keys_keep_their_looks_shape_and_the_grid(self):
        """Shockwave's 103x80 keys stood against `key`'s 1.1:1 art, and the
        examples' own places were off GUI Designer's 10 px nudge."""
        for theme in BAR:
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                section = _section(designsys.readme(p), 'The working page')
                for left, top, w, h in re.findall(
                        r'left: (-?\d+)px; top: (-?\d+)px; width: (\d+)px; height: (\d+)px', section):
                    for v in (left, top, w, h):
                        self.assertEqual(int(v) % 10, 0, (left, top, w, h))
        # The keys are a Group's cells, at the in-well look's own shape.
        p = designsys.load('shockwave')
        doc = _boards(_section(designsys.readme(p), 'The working page'))['DocCam']
        w, h = map(int, re.search(r'Group" title="Zoom" cell="(\d+)x(\d+)"', doc).groups())
        self.assertAlmostEqual(w / h, 504 / 440, delta=0.1)

    def test_a_camera_is_drawn_as_the_template_draws_one(self):
        """A heading over its keys, the kit's glyph on them where the in-well
        look has one; the 1035's own headings are Title Case."""
        for theme, icon in (('mach', 'plus'), ('turbulence', 'vc_plus'), ('shockwave', None)):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                doc = _boards(_section(designsys.readme(p), 'The working page'))['DocCam']
                self.assertIn('>Zoom</x-import>', doc)
                if icon and designsys.kit_root(p):
                    self.assertIn(f'icon="{icon}"', doc)

    def test_the_hubs_settings_opener_is_named_as_it_is_captioned(self):
        text = designsys.readme(designsys.load('shockwave'))
        hub = next(ln for ln in text.splitlines() if ln.startswith('**What a hub makes of your page.**'))
        self.assertIn("More", hub)
        self.assertIn("not the 320's", hub)

    def test_the_differences_list_the_floor_and_the_gap(self):
        diffs = _section(designsys.readme(designsys.load('shockwave')), 'Differences')
        self.assertIn('14 pt', diffs)
        self.assertIn('2 mm apart', diffs)
        # Turbulence's device pictures and bars are drawn as its art now
        # (turbulence-34 and -02 are the frame's), so they are no difference.
        diffs = _section(designsys.readme(designsys.load('turbulence')), 'Differences')
        self.assertNotIn('device picture', diffs)
        self.assertNotIn('drawn flat', diffs)

    def test_the_handover_says_who_checks_what(self):
        """The designer cannot run translate or compare: those are Claude
        Code's, after the handover."""
        for theme in designsys.TEMPLATES:
            with self.subTest(theme=theme):
                section = _section(designsys.readme(designsys.load(theme)), 'Before you hand it over')
                mine, theirs = section.split('**Claude Code checks after the handover:**', 1)
                self.assertIn('`panels`', mine)
                self.assertNotIn('translate', mine)
                self.assertNotIn('compare', mine)
                self.assertIn('translate', theirs)
                self.assertIn('--template', theirs)

    def test_the_doc_cam_title_says_what_each_panel_says(self):
        for theme in BAR:
            with self.subTest(theme=theme):
                center = _section(designsys.readme(designsys.load(theme)), 'The center')
                self.assertIn('Document Camera', center)
                self.assertIn("320's own Doc Cam page", center)


class TestAfterburnsReadme(unittest.TestCase):
    """Afterburn has no region components, so its README says how to place
    a working page's controls itself - one rule for the right column - and
    shows every artboard of the room, its windows drawn on a Panel card."""

    def setUp(self):
        self.p = designsys.load('afterburn')
        self.text = designsys.readme(self.p)
        self.working = _section(self.text, 'The working page')
        self.boards = _boards(self.working)

    def test_the_right_column_is_a_rail_said_once(self):
        main = self.boards['MainSD']
        rail = main.split('ExtronAfterburn.Rail">', 1)[1]
        for name in ('Volume', 'Mute', 'Help', 'Power'):
            self.assertIn(f'name="{name}"', rail)
        self.assertIn('ExtronAfterburn.Slider', rail)
        # Its children need no positions, and nothing else says to place them by hand.
        self.assertNotIn('left:', rail.split('</x-import>\n</x-import>', 1)[0])
        for gone in ('place the column as the Layout gives it', 'place those controls as the Layout gives them',
                     'make it 54 wide at 1166'):
            self.assertNotIn(gone, self.text + designsys.component_docs(self.p)['Rail'])
        self.assertIn('the drawn one too', self.working)

    def test_the_working_page_is_the_templates(self):
        main = self.boards['MainSD']
        F = designsys._design_frame(self.p)
        # Four sources in a Group where the frame stands its row, each its own
        # glyph - a Doc Cam where the template's TV stands, to show a source
        # with controls.
        tabs = F['center']['tabs']
        group = re.search(r'ExtronAfterburn\.Group"( title="Sources"[^>]*)>', main).group(1)
        self.assertIn(f'cell="110x110" gap="{tabs["pitch"] - tabs["first"][2]}"', group)
        main_r = self.p['layout']['main']
        self.assertIn(f'left: {tabs["first"][0] - main_r[0]}px; top: {tabs["first"][1] - main_r[1]}px', group)
        self.assertEqual(len(re.findall(r'variant="source"', main)), len(tabs['items']))
        if designsys.kit_root(self.p):
            for icon in ('pc', 'laptop', 'doc-cam', 'streaming'):
                self.assertIn(f'icon="{icon}"', main)
        # The left rail one Group of its toggle and list buttons, under its
        # heading, in cells that carry to the room's 725, 525 and 320 (round
        # four: loose, at the template's spacing, they did not).
        rail = re.search(r'ExtronAfterburn\.Group"( title="(\w+)"[^>]*cap="1"[^>]*)>', main)
        self.assertIn(f'>{rail.group(2)}</x-import>', main)
        self.assertIn(f'cell="178x{designsys.RAIL_CELL[0]}" gap="{designsys.RAIL_CELL[1]}"', rail.group(1))
        self.assertIn('variant="toggle"', main)
        self.assertIn('variant="list"', main)
        # The divider as the frame draws it; no date and time, which the 525
        # refused in the template's own boxes; the popup region the
        # template's, as deep as its popups - the 320, where it was too
        # shallow for a source's words, makes each source a page.
        self.assertIn('width: 760px', main)
        self.assertNotIn('format="date"', main)
        deep = F['center']['region'][3]
        self.assertEqual(deep, self.p['popup'][1])
        self.assertIn(f'height: {deep}px', main.split('PopupRegion', 1)[1].split('</x-import>', 1)[0])
        self.assertIn(f'height="{deep}"', self.boards['PC'])
        self.assertIn('The 320 gives each source a page of its own and leaves the region off', self.working)
        self.assertNotIn('Volume Heading', main)
        self.assertIn('panels="TLP1035T TLP725T TLP525T TLP320M"', main)
        for nav in re.findall(r'nav="([^"]+)"', main):
            self.assertIn(nav, self.boards)

    def test_every_window_and_source_popup_is_shown(self):
        for name in ('PC', 'DocCam', 'Help', 'PowerDown', 'PoweringDown', 'LightingSettings'):
            self.assertIn(name, self.boards)
        empty = self.boards['PC']
        self.assertIn('PC is currently selected.', empty)
        self.assertIn('kind="popup" group="Sources"', empty)
        for name in ('Help', 'PowerDown', 'PoweringDown', 'LightingSettings'):
            code = self.boards[name]
            self.assertIn('kind="modal"', code)
            # The card: a Panel the squircle's size, where it stands.
            self.assertIn('ExtronAfterburn.Panel" name="Card"', code)
            self.assertIn('left: 183px; top: 24px; width: 916px; height: 752px', code)
        self.assertIn('Do you want to power down the system?', self.boards['PowerDown'])
        self.assertIn('>Close</x-import>', self.boards['Help'])
        self.assertIn('reached-by="program"', self.boards['PoweringDown'])
        q = self.boards['PowerDown']
        self.assertLess(q.index('>Power Down</x-import>'), q.index('>Cancel</x-import>'))

    def test_it_says_what_the_designer_writes(self):
        writing = _section(self.text, 'Writing')
        self.assertNotIn('say them for you', writing)
        self.assertIn('you write', writing)
        wins = _section(self.text, 'Windows')
        self.assertIn('916x752 at 183,24', wins)
        center = _section(self.text, 'The center')
        self.assertIn('write it', center)

    def test_the_320s_rows_are_said(self):
        """Round four's designer revised three times guessing what the README
        left out about the 320 - the order its rows take a page's controls in,
        how many rows its screen holds, how tall a heading is, where Start's
        button may stand (tests/data/round4-afterburn-revised): each is said,
        its numbers off the 320's own row in models() and the example's popup
        region, as bundle.js flowRows and rowsPage lay them."""
        panels = _section(self.text, 'Every panel the room has')
        T = designsys.models(self.p)['TLP320M']
        deep, across = T['main'][3] - 4, T['main'][2] - 2 * T['gap']
        self.assertIn(f'| TLP320C/M | 320x240 | rows: {deep} px of them, {across} across |', panels)
        rows = next(ln for ln in panels.splitlines() if ln.startswith('- **Rows**'))
        line = math.ceil(T['floor'] * self.p['pt'] * 1.2) + 2
        for said in (f'({line} px on the 320)', "the main area's first, then the Page's own column by column",
                     "Start's button stands where the Layout puts it", f"within {self.p['spacing']} px",
                     "stands at that Group's left, in its row", 'between the rows it was drawn between, 2 px clear',
                     'a row of a side column stands beside the first earlier row',
                     'one under another and, where a row moved, beside', 'does not go on over pages of its own',
                     # The 320's seed has no standard popup: each source is a
                     # page there, with Back, and a region is left off.
                     'On the TLP320C/M, whose seed has no standard popup, a popup is a page of its own',
                     "a Back at the foot's left", 'A `PopupRegion` has nothing to show there, and is left off'):
            self.assertIn(said, rows)
        grammar = _section(self.text, "The template's grammar")
        self.assertIn('draws each source popup as a page of its own too', grammar)
        self.assertIn("its heading at its left", self.working)
        group = designsys.component_docs(self.p)['Group']
        self.assertIn("stands at that button's left, in its row", group)
        # The bar themes' rows go on, and say how much a page that does holds.
        mach = designsys.load('mach')
        M = designsys.models(mach)['TLP320M']
        self.assertIn(f"- {M['main'][3] - 4 - M['touch'] - M['gap']} on a page that goes on |",
                      _section(designsys.readme(mach), 'Every panel the room has'))

    def test_the_320_strip_is_at_the_foot(self):
        grammar = _section(self.text, "The template's grammar")
        small = next(ln for ln in grammar.splitlines() if ln.startswith('**What the 320 makes of your page.**'))
        self.assertIn('foot', small)
        self.assertNotIn('under a title strip', small)

    def test_preview_and_the_mode_button_are_the_rooms_own(self):
        regions = ' '.join(self.p['layout']['regions'])
        self.assertIn('only where the room has', regions)

    def test_a_source_popup_is_of_the_sources_group(self):
        wins = _section(self.text, 'Windows')
        self.assertNotIn('a standard popup of group 1 in', wins)
        self.assertIn('`Sources`', wins)


class TestCanvasIds(unittest.TestCase):
    """A control's `id` reaches the spec as the designer wrote it, for gdl.spec
    check to hold to a UInt16. Number() made 'abc' NaN, which JSON writes as
    null - the control quietly took an allocated ID - and an empty one 0."""

    def test_every_control_reads_its_id_one_way(self):
        js = designsys._read('bundle.js')
        self.assertNotIn('Number(props.id)', js)
        self.assertEqual(js.count('id: idOf(props.id)'), 3)

    def test_a_whole_number_is_the_id_and_anything_else_goes_through(self):
        import shutil
        import subprocess
        if not shutil.which('node'):
            self.skipTest('node is not installed')
        fn = re.search(r'function idOf\(v\) \{.*?\n  \}', designsys._read('bundle.js'), re.S).group(0)
        cases = ['1001', ' 7 ', 70000, '70000', 12.5, 'abc', '', None, 0]
        out = subprocess.run(
            ['node', '-e', f'{fn}\nconsole.log(JSON.stringify({json.dumps(cases)}.map(idOf)))'],
            capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), [1001, 7, 70000, 70000, 12.5, 'abc', None, None, 0])


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


class TestTheLedger(unittest.TestCase):
    """The truth ledger (gdl/designsys/truth/<theme>.json): every claim our
    profile or README made that the template's own pages contradict, with
    what the template does and how it is resolved. The audit reports what is
    not, so a theme at zero is done (the region frame spec's *Truth*)."""

    def setUp(self):
        from gdl.designsys import audit
        self.audit = audit
        self.p = designsys.load('mach')
        self.ledger = audit.load_ledger('mach')

    def _entry(self, **kw):
        e = {'id': 'mach-99', 'claim': 'A claim.', 'where': ['type.header.usage'],
             'template': {'does': 'What it does.', 'seed': 'seeds/Mach 1035.gdl', 'pages': ['Main SD']},
             'status': 'fixed', 'fix': [{'key': 'type.header.usage', 'says': 'Main Select Source'}],
             'evidence': 'Read off the page.'}
        e.update(kw)
        return {k: v for k, v in e.items() if v is not None}

    def _findings(self, *entries):
        ledger = dict(self.ledger, entries=list(entries))
        return self.audit.audit_ledger(self.p, ledger)

    def test_a_differences_number_is_its_entrys_own(self):
        """Differences is each deviation's `here`, which the claim lint
        leaves to its entry: a number there the entry's template, reason and
        evidence never say is a drift no other check sees (PR8 review)."""
        dev = dict(status='deviation', fix=None, reason='The 53 px touch minimum.',
                   template={'does': 'The slider is 30 wide.', 'seed': 'seeds/Mach 1035.gdl', 'pages': ['Main SD']})
        ok = self._entry(here='The slider is drawn 53 px wide where the template draws 30.', **dev)
        self.assertEqual(self._findings(ok), [])
        drift = self._entry(here='The slider is drawn 54 px wide where the template draws 30.', **dev)
        self.assertEqual(self._findings(drift), ["mach-99: its `here` says 54, which its template, reason and "
                                                 "evidence do not"])
        # A number inside a word or a name is not one of its claims.
        named = self._entry(here='The slider is drawn 53 px wide on the TLP1035T, past its 2D border.', **dev)
        self.assertEqual(self._findings(named), [])

    def test_a_number_with_a_unit_a_size_or_a_full_stop_is_one_too(self):
        """The number pattern stepped over any number a letter or a period
        followed, so '99px', both sides of '880x525' and a sentence's last
        number passed unbacked."""
        dev = dict(status='deviation', fix=None, reason='The 53 px touch minimum.',
                   template={'does': 'The slider is 30 wide, its well 880x525.', 'seed': 'seeds/Mach 1035.gdl',
                             'pages': ['Main SD']})
        for here, unbacked in (('The slider is 99px wide.', ['99']), ('Its well is 880x524.', ['524']),
                               ('Its well is 881x525.', ['881']), ('The slider ends at 42.', ['42']),
                               ('It is 14pt and 9mm.', ['9', '14']),
                               ('The slider is 53px wide in an 880x525 well, as the template draws 30.', [])):
            with self.subTest(here=here):
                self.assertEqual(self._findings(self._entry(here=here, **dev)),
                                 [f"mach-99: its `here` says {n}, which its template, reason and evidence do not"
                                  for n in unbacked])

    def test_every_ledger_is_one_its_schema_takes(self):
        for name in sorted(os.listdir(self.audit.TRUTH)):
            if name.endswith('.json') and name != 'schema.json':
                with self.subTest(ledger=name):
                    led = self.audit.load_ledger(name[:-5])
                    self.assertEqual(self.audit.validate(led), [])
                    self.assertEqual(led['theme'], name[:-5])

    def test_machs_ledger_has_an_entry_per_disagreement(self):
        """The grammar measurement found 43 claims of Mach's profile and README
        that its pages contradict: one entry each, in its order."""
        ids = [e['id'] for e in self.ledger['entries']]
        self.assertEqual(ids, [f'mach-{i:02d}' for i in range(43)])

    def test_mach_is_done(self):
        self.assertEqual(self.audit.audit('mach'), [])
        self.assertEqual(designsys.main(['gdl.designsys', 'audit', 'mach']), 0)

    def test_a_resolved_entry_passes(self):
        self.assertEqual(self._findings(self._entry()), [])

    def test_an_entry_with_no_status_is_unresolved(self):
        out = self._findings(self._entry(status=None))
        self.assertTrue(any('has no `status`' in f for f in out), out)

    def test_a_fix_must_name_a_key_the_profile_has_and_say_what_it_says(self):
        out = self._findings(self._entry(fix=[{'key': 'type.nothing.usage', 'says': 'x'}]))
        self.assertTrue(any('which the profile does not have' in f for f in out), out)
        out = self._findings(self._entry(fix=[{'key': 'type.header.usage', 'says': 'every Mach 1035 page'}]))
        self.assertTrue(any('does not say' in f for f in out), out)
        out = self._findings(self._entry(fix=[{'readme': 'Words no README holds.'}]))
        self.assertTrue(any('the README does not say' in f for f in out), out)
        out = self._findings(self._entry(fix=[]))
        self.assertTrue(any('names no key or README words' in f for f in out), out)

    def test_a_deviation_needs_its_reason(self):
        out = self._findings(self._entry(status='deviation', fix=None, here='Nothing under 14 pt.'))
        self.assertTrue(any('without a reason' in f for f in out), out)
        self.assertEqual(self._findings(self._entry(status='deviation', fix=None, here='Nothing under 14 pt.',
                                                    reason='The 14 pt floor.')), [])

    def test_a_deviation_says_what_we_do_instead(self):
        """The README's Differences is written from each deviation's `here`:
        one without it would leave a difference unsaid to the designer."""
        out = self._findings(self._entry(status='deviation', fix=None, reason='The 14 pt floor.'))
        self.assertTrue(any('says nothing to the designer' in f for f in out), out)

    def test_a_frame_entry_names_a_frame_key_that_is_there(self):
        ok = self._entry(status='frame', fix=None, frame=[{'series': 'Mach 1220 Series', 'key': 'top.tabs'}])
        self.assertEqual(self._findings(ok), [])
        out = self._findings(dict(ok, frame=[{'series': 'Mach 1220 Series', 'key': 'top.nothing'}]))
        self.assertTrue(any('frame has `top.nothing`' in f for f in out), out)
        out = self._findings(dict(ok, frame=[{'key': 'left.groups'}]))
        self.assertEqual(out, [])

    def test_a_claim_said_to_be_gone_must_be(self):
        out = self._findings(self._entry(gone=['Every artboard on a canvas']))
        self.assertTrue(any('still says' in f for f in out), out)

    def test_evidence_names_a_seed_and_its_pages(self):
        bad = self._entry()
        bad['template'] = dict(bad['template'], seed='Mach 1035', pages=[])
        out = self._findings(bad)
        self.assertTrue(any('does not match' in f for f in out), out)
        self.assertTrue(any('needs at least 1' in f for f in out), out)

    def test_a_theme_with_no_ledger_is_not_done(self):
        out = self.audit.audit_ledger(designsys.load('afterburn'), None)
        self.assertTrue(out and 'no ledger' in out[0], out)
        import contextlib
        import io
        from unittest import mock
        with mock.patch.object(self.audit, 'load_ledger', return_value=None), \
                contextlib.redirect_stdout(io.StringIO()) as said:
            self.assertEqual(designsys.main(['gdl.designsys', 'audit', 'mach']), 1)
        self.assertIn('no ledger', said.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(designsys.main(['gdl.designsys', 'audit', 'nothing']), 2)


class TestTheColumnLabelsOfTheSmallestPanel(unittest.TestCase):
    """`writing.column_labels_320` against the four 320 seeds: Mach's,
    Shockwave's and Afterburn's camera column labels (ZOOM, FOCUS, INPUTS,
    IRIS) are capitals, Turbulence's are Title Case. The profile key is set on
    exactly the themes whose own 320 draws a Group's heading (Afterburn's draws
    none, so it has no use for the key). The seeds show it on those four
    labels only; applying it to every Group title is extrapolated."""

    LABELS = ('zoom', 'focus', 'input', 'inputs', 'iris')

    def test_the_key_is_set_where_the_seed_capitalises_and_a_heading_is_drawn(self):
        from gdl import seeds
        from gdl.project import Project
        for theme in ('mach', 'shockwave', 'turbulence', 'afterburn'):
            with self.subTest(theme=theme):
                path = seeds.path(f'seeds/{theme.title()} 320.gdl')
                if not seeds.usable(f'seeds/{theme.title()} 320.gdl'):
                    self.skipTest(f'seeds/{theme.title()} 320.gdl is not here (git lfs pull)')
                found = {c['text'] for pg in Project.open(path).pages() for c in pg['controls']
                         if c['type'] == 'PBLabel' and (c.get('text') or '').strip().lower() in self.LABELS}
                self.assertEqual(len(found), 4, found)
                caps = all(t == t.upper() for t in found)
                self.assertEqual(caps, theme != 'turbulence', found)
                key = designsys.load(theme)['writing'].get('column_labels_320')
                # Afterburn's 320 draws no heading of a Group's, so its key is unset.
                self.assertEqual(key == 'caps', caps and theme != 'afterburn', (theme, key))

    def test_the_extrapolation_is_said(self):
        for theme in ('mach', 'shockwave'):
            src = designsys.load(theme)['writing']['voice']['_source']
            self.assertIn('extrapolated', src.lower(), theme)


class TestMachsWordsAgainstTheSeed(unittest.TestCase):
    """What Mach's profile counts and names off seeds/Mach 1035.gdl, read off
    the seed again: the claim lint reads phrasing, not numbers, so a count or
    a page a usage states is checked here (mach-10, -11, -15, -31)."""

    @classmethod
    def setUpClass(cls):
        from _corpus import seed
        path = seed('Mach 1035.gdl')
        if not usable(path):
            raise unittest.SkipTest('seeds/Mach 1035.gdl is not here (git lfs pull)')
        import measure_series
        from gdl.project import Project
        cls.pages = measure_series.seed_pages(Project.open(path))
        cls.p = designsys.load('mach')
        cls.colors = {c['name']: c['usage'] for c in cls.p['colors']}

    def ctl(self, name, cid):
        return next(c for pg in self.pages for c in pg['controls'] if c['name'] == name and c['id'] == cid)

    def test_the_button_looks_are_counted_as_the_seed_has_them(self):
        pairs = [tuple(lk['fill'] for lk in c['looks'][:2]) for pg in self.pages for c in pg['controls']
                 if c['type'] == 'PBButton' and len(c['looks']) >= 2]
        ghost = pairs.count(('#FFFFFF32', '#FFFFFF78'))
        shade = pairs.count(('#000000B4', '#1F292EA0'))
        self.assertIn(f"({ghost} of Mach 1035's {len(pairs)} authored button-state pairs)",
                      self.p['buttons']['ghost']['usage'])
        self.assertIn(f"({ghost} of Mach 1035's {len(pairs)} authored button-state pairs)",
                      self.colors['raised'])
        self.assertIn(f'the same {ghost} button-state pairs', self.colors['pressed'])
        self.assertIn(f'({shade} of {len(pairs)} pairs)', self.p['buttons']['solid']['usage'])
        self.assertIn(f'the same {shade} button-state pairs', self.colors['shade-on'])

    def test_the_rounded_border_is_on_the_shapes_the_seed_draws_it_on(self):
        shapes = [c for pg in self.pages for c in pg['controls']
                  if c['type'] == 'PBShape' and (c['border'] or {}).get('resource') == '2D Rounded Rectangle']
        self.assertIn(f'on {len(shapes)} shapes', self.p['borders']['rounded']['usage'])

    def test_the_grey_labels_are_the_recording_controls_windows(self):
        held = {pg['name'] for pg in self.pages for c in pg['controls']
                if c['type'] == 'PBLabel' and c['text_color'] == {'A': 255, 'R': 145, 'G': 145, 'B': 145}}
        self.assertEqual(held, {'Recording Controls'})
        self.assertIn("the Recording Controls window's ALL CAPS status labels", self.colors['text-secondary'])
        self.assertNotIn("Main Recording's", self.colors['text-secondary'])

    def test_red_is_a_consequential_action_and_share_content_is_never_solid(self):
        """Record starts a recording, and its confirmation says so; Share
        Content's live state is the dim red on no border."""
        record = self.ctl('Record', 9244)
        self.assertEqual([lk['fill'] for lk in record['looks']], ['#A829258C', '#E23636FF'])
        share = self.ctl('Share Content', 8090)
        self.assertEqual([(lk['fill'], lk['border']) for lk in share['looks']],
                         [('#000000B4', None), ('#A82925DC', None)])
        for usage in (self.colors['alert'], self.p['buttons']['alert']['usage']):
            self.assertIn('starts what attendees must be told of', usage)
            self.assertNotIn('Share Content', usage)
        self.assertIn("Share Content's On", self.colors['alert-dim'])
        self.assertIn('no border', self.colors['alert-dim'])


class TestTheSliderDefaultsAgainstTheSeeds(unittest.TestCase):
    """A profile's slider defaults are its design panel's seed's, and the
    Slider docs say so: Shockwave's note said every seed's slider was the
    1035's 52 track and 52x34 thumb, and only the 1035 and ECP 16-10 draw
    that (U61). Read off each seed's layout.json, where Build keeps the
    authoring fields as SliderTrackWidth and SliderIndicatorWidth/Height."""

    @staticmethod
    def _sliders(path):
        from gdl.container import open_payload
        j = json.loads(open_payload(path).read('layout.json'))
        return {(c['SliderTrackWidth'], c['SliderIndicatorWidth'], c['SliderIndicatorHeight'])
                for pg in (j.get('Pages') or []) + (j.get('PopupPages') or [])
                for c in pg.get('Controls') or [] if c.get('Type') == 27}

    def test_each_profiles_defaults_are_its_design_panels_seeds(self):
        from gdl import seeds
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            p = designsys.load(theme)
            path = os.path.join(REPO, seeds.default_path(p['template'], p['model']))
            with self.subTest(theme=theme):
                if not usable(path):
                    self.skipTest(f'{os.path.relpath(path, REPO)} is not here (git lfs pull)')
                sl = p['defaults']['slider']
                self.assertEqual(self._sliders(path), {(sl['track'], sl['thumb'], sl.get('thumb_height') or sl['thumb'])})
                self.assertIn(f"default {sl['track']}, the {p['model']}'s", designsys.component_docs(p)['Slider'])

    def test_shockwaves_note_gives_every_seeds_own(self):
        import glob
        note = next(s for s in designsys.load('shockwave')['_source'] if s.startswith('Slider:'))
        said = {tuple(map(int, m)) for m in re.findall(r'(\d+)(?: wide)? and (?:thumb )?(\d+)x(\d+)', note)}
        paths = sorted(glob.glob(os.path.join(REPO, 'seeds', 'Shockwave *.gdl')))
        if not paths or not all(usable(p) for p in paths):
            self.skipTest("Shockwave's seeds are not here (git lfs pull)")
        self.assertEqual(said, set().union(*map(self._sliders, paths)))


class TestTheClaimLint(unittest.TestCase):
    """A sentence in a profile or its README that says what the template
    does must be backed - by the ledger, by the frame (the README's Layout)
    or by a `_source` over it that names the seed and a page."""

    def setUp(self):
        from gdl.designsys import audit
        self.audit = audit

    def test_what_reads_as_a_claim(self):
        for s in ("Help and Power, as the seed draws them.",
                  "Lighting and audio are modals, as Mach's own templates draw them.",
                  "The volume on the right, as Mach's own pages put it.",
                  "26 pt, as every Mach 1035 page's own header label.",
                  "The template's tabs stand 1 px apart.",
                  "The seed's are 110x110 in a row."):
            with self.subTest(s=s):
                self.assertIsNotNone(self.audit.claim(s))
        for s in ("Every other page must be reachable by `nav` from the start page.",
                  "Built into the panel as the page's background image.",
                  "Nothing under 14 pt.",
                  "The tabs stand at the frame's places, 1 px apart."):
            with self.subTest(s=s):
                self.assertIsNone(self.audit.claim(s))

    def _profile(self, usage, source=None):
        p = designsys.load('mach')
        p = json.loads(json.dumps(p))
        p['type'][0]['usage'] = usage
        p['_source'] = [x for x in p['_source'] if not x.startswith('Type:')] + (
            [source] if source else [])
        return p

    def _flagged(self, p, ledger=None):
        return [w for w, _, _ in self.audit.lint(p, ledger) if w == 'type.title.usage']

    def test_an_unbacked_claim_is_flagged(self):
        p = self._profile("A title, as every Mach 1035 page's own title label.")
        self.assertEqual(self._flagged(p), ['type.title.usage'])

    def test_a_source_naming_the_seed_and_a_page_backs_it(self):
        p = self._profile("A title, as every Mach 1035 page's own title label.",
                          "Type: seeds/Mach 1035.gdl's Main SD, read with gdl.project.")
        self.assertEqual(self._flagged(p), [])
        # The seed alone, or a page alone, does not.
        p = self._profile("A title, as every Mach 1035 page's own title label.",
                          "Type: seeds/Mach 1035.gdl's labels.")
        self.assertEqual(self._flagged(p), ['type.title.usage'])

    def test_a_function_named_pages_is_no_survey_of_every_page(self):
        """`pages()` in a source names the function it was read with, not a
        page of the seed, so it backs no claim; a source that read every page
        says so in words."""
        claim = "A title, as every Mach 1035 page's own title label."
        p = self._profile(claim, "Type: seeds/Mach 1035.gdl's labels, read with Project.pages() "
                                 'from gdl/project.py.')
        self.assertEqual(self._flagged(p), ['type.title.usage'])
        p = self._profile(claim, "Type: seeds/Mach 1035.gdl's labels on every page.")
        self.assertEqual(self._flagged(p), [])

    def test_a_ledger_fix_backs_its_own_words(self):
        p = self._profile("A title, as every Mach 1035 page's own title label.")
        ledger = {'entries': [{'fix': [{'key': 'type.title.usage', 'says': "every Mach 1035 page's own title"}]}]}
        self.assertEqual(self._flagged(p, ledger), [])

    def test_the_layout_is_the_frames(self):
        """Every number in the README's Layout is a frame value, so none of
        its sentences is a claim to back."""
        p = designsys.load('shockwave')
        layout = designsys.frame_layout(p)
        self.assertTrue(layout)
        flagged = [s for w, s, _ in self.audit.lint(p) if w == 'README']
        self.assertFalse([s for s in flagged if s in layout], flagged)


class TestTheCaptionLint(unittest.TestCase):
    """The README's and the profile's caption examples say what the template
    says, in its case and voice (`writing.voice`): Title Case, no capitals
    where it writes none, no generic verb where it names the action, and its
    own word where it has one ("Lighting", not "Lighting Settings", on Mach's
    rail)."""

    def setUp(self):
        from gdl.designsys import audit
        self.audit = audit

    def _readme(self, theme, *buttons, title=None):
        p = designsys.load(theme)
        ns = p['namespace']
        code = ''.join(f'<x-import component-from-global-scope="{ns}.Button" name="B{i}">{b}</x-import>\n'
                       for i, b in enumerate(buttons))
        if title:
            code += f'<x-import component-from-global-scope="{ns}.Section" title="{title}"></x-import>\n'
        return p, f'## Example\n\n```html\n{code}```\n'

    def _why(self, theme, *buttons, title=None):
        p, text = self._readme(theme, *buttons, title=title)
        return [(c, why) for _, c, why in self.audit.caption_lint(p, text)]

    def test_a_generic_verb_is_flagged(self):
        for word in ('Submit', 'OK', 'Yes'):
            with self.subTest(word=word):
                out = self._why('mach', word)
                self.assertEqual([c for c, _ in out], [word])
                self.assertIn('names the action', out[0][1])

    def test_capitals_where_the_template_writes_title_case(self):
        out = self._why('mach', 'LIGHTING', 'HELP')
        self.assertEqual([c for c, _ in out], ['LIGHTING', 'HELP'])
        self.assertIn('Title Case', out[0][1])
        # Shockwave sets its Help's title in capitals itself; an acronym is no shout.
        self.assertEqual(self._why('shockwave', 'HELP', 'PC', 'AUX'), [])

    def test_a_caption_the_template_words_otherwise(self):
        out = self._why('mach', 'Lighting Settings')
        self.assertEqual(out[0][0], 'Lighting Settings')
        self.assertIn("Mach says 'Lighting'", out[0][1])
        out = self._why('shockwave', 'Make Call', 'Lighting Control')
        self.assertEqual([c for c, _ in out], ['Make Call'])
        self.assertIn("Shockwave says 'Call'", out[0][1])

    def test_a_caption_not_in_title_case(self):
        out = self._why('mach', 'Room mode', 'Press to begin', 'Select a Source')
        self.assertEqual([c for c, _ in out], ['Room mode'])
        out = self._why('mach', title='display controls')
        self.assertEqual([c for c, _ in out], ['display controls'])

    def test_the_profiles_caption_examples_are_linted_too(self):
        p = json.loads(json.dumps(designsys.load('mach')))
        p['writing']['buttons']['power'] = 'Shut Down'
        out = self.audit.caption_lint(p, '')
        self.assertEqual([(w, c) for w, c, _ in out], [('writing.buttons.power', 'Shut Down')])

    def test_every_system_says_its_captions_in_its_templates_voice(self):
        for theme in designsys.TEMPLATES:
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                self.assertEqual(self.audit.caption_lint(p), [])

    def test_the_audit_reports_it(self):
        p, text = self._readme('mach', 'Submit')
        out = self.audit.audit('mach', profile=p, text=text)
        self.assertTrue(any(f.startswith("caption 'Submit'") for f in out), out)


class TestTheTemplateRenders(unittest.TestCase):
    """Each theme's own working page, rendered off its seed (gdl.compose) and
    downscaled: the bar panel's, the hub's and the 320's, a file of the
    private design system the README shows beside its grammar (the owner's
    call 3 of 2026-10-22: private only, never the public copy)."""

    def test_the_plan_is_each_familys_frame_page_off_its_own_seed(self):
        for theme in designsys.TEMPLATES:
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                ms = designsys.models(p)
                plan = [r for r in designsys.template_renders(p) if not r.get('window')]
                for r, model in zip(plan, (p['model'], 'TLP525T', 'TLP320M')):
                    self.assertEqual(r['seed'], ms[model]['seed'])
                    self.assertEqual(r['page'], ms[model]['frame']['page'])
                    self.assertTrue(r['file'].startswith('templates/') and r['file'].endswith('.webp'), r)
                    self.assertLessEqual(r['size'][0], 640)

    def test_the_panels_rule_blends_where_the_snapshots_does_not(self):
        """compose.BINARY: GUI Designer's snapshots write any pixel with alpha
        at full strength, and that stays paste()'s default; off, paste()
        blends it, as the panel shows a translucent bar over its photo."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow not installed')
        import io
        from gdl import compose
        buf = io.BytesIO()
        Image.new('RGBA', (4, 4), (0, 0, 0, 128)).save(buf, 'PNG')
        assets = {1: buf.getvalue()}

        def pixel(rule):
            c = Image.new('RGBA', (4, 4), (200, 200, 200, 255))
            was, compose.BINARY = compose.BINARY, rule
            try:
                compose.paste(c, assets, 1, 0, 0)
            finally:
                compose.BINARY = was
            return c.getpixel((1, 1))[:3]
        self.assertIs(compose.BINARY, True)
        self.assertEqual(pixel(True), (0, 0, 0))
        for v in pixel(False):
            self.assertAlmostEqual(v, 200 * (255 - 128) / 255, delta=2)

    def test_a_render_shows_the_photo_through_translucent_chrome(self):
        """Mach's header is #000000B4 over its photo: the render shows the
        photo through it, where the snapshot rule paints it black."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow not installed')
        import io
        from gdl import seeds
        p = designsys.load('mach')
        plan = [r for r in designsys.template_renders(p) if r['family'] == 'bar' and not r.get('window')]
        if not seeds.usable(plan[0]['seed']):
            self.skipTest(f"{plan[0]['seed']} is not here (git lfs pull)")
        got = designsys.render_templates(p, plan)
        im = Image.open(io.BytesIO(got[plan[0]['file']])).convert('RGB')
        k = plan[0]['size'][0] / plan[0]['screen'][0]
        # The header band left of its tabs (Mach's 1280x64 at 0,0, tabs from 258).
        self.assertGreater(max(im.getpixel((int(100 * k), int(32 * k)))), 30)

    def test_rendering_puts_the_compositing_rule_back(self):
        """render_templates blends, then puts compose.BINARY back as the
        caller had it - after a page that does not draw, and after one that
        raises - where it was written True whatever the caller had."""
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest('Pillow is not here: renders need gdl.compose')
        import contextlib
        import io
        from gdl import compose, seeds
        p = designsys.load('mach')
        plan = [r for r in designsys.template_renders(p) if r['family'] == 'bar' and not r.get('window')]
        if not seeds.usable(plan[0]['seed']):
            self.skipTest(f"{plan[0]['seed']} is not here (git lfs pull)")
        seen = []
        saved = compose.render_snapshot, compose.BINARY

        def fails(err):
            def render(*a, **k):
                seen.append(compose.BINARY)
                raise err
            return render
        try:
            compose.BINARY = 'the callers'
            compose.render_snapshot = fails(ValueError('no page'))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(designsys.render_templates(p, plan), {})
            self.assertEqual(compose.BINARY, 'the callers')
            compose.render_snapshot = fails(RuntimeError('boom'))
            with self.assertRaises(RuntimeError):
                designsys.render_templates(p, plan)
            self.assertEqual(compose.BINARY, 'the callers')
        finally:
            compose.render_snapshot, compose.BINARY = saved
        self.assertEqual(seen, [False, False])

    def test_a_build_without_the_seeds_says_so(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest('Pillow is not here: renders need gdl.compose')
        import contextlib
        import io
        from gdl import seeds
        saved = seeds.usable
        seeds.usable = lambda path: False
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                got = designsys.render_templates(designsys.load('mach'))
        finally:
            seeds.usable = saved
        self.assertEqual(got, {})
        self.assertIn('git lfs pull', out.getvalue())
        self.assertIn('seeds/Mach 1035.gdl', out.getvalue())

    def test_a_build_writes_them_and_shows_them(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow not installed')
        from gdl import seeds
        p = designsys.load('mach')
        plan = designsys.template_renders(p)
        if not all(seeds.usable(r['seed']) for r in plan):
            self.skipTest("Mach's seeds are not here (git lfs pull)")
        with tempfile.TemporaryDirectory() as d:
            written = designsys.build('mach', d, '2026-10-24T00:00:00Z')
            with open(os.path.join(d, 'project', 'README.md'), encoding='utf-8') as fh:
                readme = fh.read()
            for r in plan:
                self.assertIn('project/' + r['file'], written)
                path = os.path.join(d, 'project', *r['file'].split('/'))
                with Image.open(path) as im:
                    self.assertEqual(im.size, tuple(r['size']))
                self.assertLess(os.path.getsize(path), 150_000)
                self.assertIn(f"]({r['file']})", readme)
            self.assertIn('project/components/Template/preview.html', written)
            with open(os.path.join(d, 'project', 'components', 'Template', 'preview.html'), encoding='utf-8') as fh:
                card = fh.read()
            self.assertTrue(card.startswith('<!-- @dsCard'))
            self.assertEqual(card.count('data:image/webp;base64,'), len(plan))


class TestTheLayoutIsTheFrames(unittest.TestCase):
    """The README's Layout states each series' bands and the design panel's
    regions, sets and rects from `panels[series].frame`: hand-written, it
    told designers Mach's header held a title and its rail buttons stood
    12 px apart, neither of which its working page does."""

    def _layout(self, p):
        return designsys.readme(p).split('## Layout', 1)[1].split('\n## ', 1)[0]

    def test_every_series_bands_are_its_frames(self):
        for theme in designsys.TEMPLATES:
            p = designsys.load(theme)
            layout = self._layout(p)
            for name, s in p['panels'].items():
                f = s.get('frame') if isinstance(s, dict) else None
                if name.startswith('_') or not f:
                    continue
                row = next(ln for ln in layout.splitlines()
                           if ln.startswith(f"| {name[len(p['template']):].strip().removesuffix(' Series')} |"))
                for k in ('top', 'left', 'right', 'bottom', 'center'):
                    with self.subTest(theme=theme, series=name, band=k):
                        b = f.get(k)
                        want = designsys._rect(b['rect']) if isinstance(b, dict) else '-'
                        self.assertIn(f' {want} |', row)

    def test_the_design_panels_regions_are_drawn_from_its_frame(self):
        p = designsys.load('mach')
        layout = self._layout(p)
        for want in ('**Header** 1280x64 at 0,0', '190x64 from 258,0, one every 191 px (1 px apart)',
                     "'Display' heading 103x37 at 17,149", '103x60 from 17,186, one every 61 px (1 px apart)',
                     '`SD Volume Slider` 30x363 at 1198,178', '`Help` 70x55 at 1069,745',
                     'the popup region the sources fill 995x549 at 140,137'):
            self.assertIn(want, layout)
        for gone in ('with the page\'s title centered on it', '12 px apart', 'Lighting Preset',
                     'Sources sit in the middle of the photo'):
            self.assertNotIn(gone, layout)

    def test_it_cannot_drift_from_the_frame(self):
        p = json.loads(json.dumps(designsys.load('mach')))
        p['panels']['Mach 1220 Series']['frame']['top']['tabs']['items'][0]['rect'] = [300, 0, 180, 64]
        p['panels']['Mach 1020 Series']['frame']['bottom']['rect'] = [0, 540, 1024, 60]
        layout = self._layout(p)
        self.assertIn('180x64 from 300,0', layout)
        self.assertIn('| 1024x60 at 0,540 |', layout)


class TestTurbulencesTruth(unittest.TestCase):
    """Turbulence's ledger (gdl/designsys/truth/turbulence.json): the claims
    its profile and README made that its own pages contradict, resolved - and
    what that changed in the shared READMEs and in what builds."""

    def setUp(self):
        from gdl.designsys import audit
        self.audit = audit
        self.p = designsys.load('turbulence')
        self.docs = designsys.component_docs(self.p)

    def test_it_has_an_entry_per_disagreement(self):
        """The grammar measurement found 34, the PR8 review one more (the
        device picture, missing from Differences), and measuring every source
        popup's picture one more (turbulence-35: each device is its own size):
        one entry each, in order."""
        ids = [e['id'] for e in self.audit.load_ledger('turbulence')['entries']]
        self.assertEqual(ids, [f'turbulence-{i:02d}' for i in range(36)])

    def test_turbulence_is_done(self):
        self.assertEqual(self.audit.audit('turbulence'), [])
        self.assertEqual(designsys.main(['gdl.designsys', 'audit', 'turbulence']), 0)

    def test_a_lit_dock_call_tile_and_help_are_lime(self):
        """The seed's lit captions are LimeGreen on the tabs, keys, rings and
        wide bars and Lime on the docks, Help and the Initiate Call and End
        Call tiles; the profile said `accent` for every one."""
        on = lambda states: next(s for s in states if s['name'] == 'On')['color']
        for variant in ('dock', 'call'):
            self.assertEqual(on(self.p['buttons'][variant]['states']), 'lime', variant)
        self.assertEqual(on(self.p['regions']['help']['states']), 'lime')
        for variant in ('button', 'ring', 'source', 'wide'):
            self.assertEqual(on(self.p['buttons'][variant]['states']), 'accent', variant)
        tokens = {c['name']: c['value'] for c in self.p['colors']}
        self.assertEqual((tokens['lime'], tokens['alert'], tokens['veil']), ('#00FF00', '#FF0000', '#00000087'))
        # Room Mode's card is black at transparencyField 47: alpha 135.
        self.assertEqual(int(tokens['veil'][-2:], 16), round(255 * (100 - 47) / 100))

    def test_the_header_and_footer_are_art_not_a_panel(self):
        text = designsys.readme(self.p)
        for gone in ('`shade` Panel', 'invisible at rest', 'centered on the page', '112 apart'):
            self.assertNotIn(gone, text + self.docs['Button'])
        self.assertIn('with a 3-row light rule', next(c for c in self.p['colors'] if c['name'] == 'shade')['usage'])

    def test_a_set_is_not_said_to_touch_where_its_template_leaves_a_gap(self):
        """Turbulence's tabs stand 14 px apart, its rings 8 and its docks 2:
        the Header and Section READMEs said 'touch, 1 px apart', which only
        Mach's and Shockwave's sets do."""
        tabs = self.p['panels']['Turbulence 1220 Series']['frame']['top']['tabs']
        self.assertEqual(tabs['pitch'] - tabs['first'][2], 14)
        for theme in ('mach', 'shockwave', 'turbulence'):
            docs = designsys.component_docs(designsys.load(theme))
            for name in ('Header', 'Section', 'RightRail', 'Footer'):
                with self.subTest(theme=theme, doc=name):
                    self.assertNotIn('touch, 1 px apart', docs[name])
                    self.assertNotIn('touch as it draws', docs[name])
        self.assertIn('one every 141 px (14 px apart)', designsys.frame_layout(self.p))

    def test_a_slider_drawn_from_art_is_not_called_a_rounded_rail(self):
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                doc = designsys.component_docs(designsys.load(theme))['Slider']
                self.assertIn("its kit's rail art", doc)
                self.assertNotIn('a rounded rail', doc)
        doc = designsys.component_docs(designsys.load('turbulence'))['Slider']
        self.assertIn('`52x535_turb_slider_bg.png` for the empty rail', doc)
        self.assertIn('`52x535_turb_slider_fill.png` over it as far as the value', doc)
        # Afterburn's is two colors.
        self.assertIn('a rounded rail', designsys.component_docs(designsys.load('afterburn'))['Slider'])

    def test_the_examples_are_what_the_template_draws(self):
        """The Group example is the tab row (127x133, 14 apart), the MainArea
        example a Select a Source tile inside main, the Panel example a card,
        and the working page's PC tab draws its own glyph."""
        group = self.docs['Group']
        self.assertIn('cell="127x133" gap="14"', group)
        self.assertNotIn('cell="110x110"', group)
        m = re.search(r'left: (-?\d+)px; top: (-?\d+)px; width: (\d+)px; height: (\d+)px', self.docs['MainArea'])
        x, y, w, h = map(int, m.groups())
        main = self.p['layout']['main']
        self.assertTrue(0 <= x and 0 <= y and x + w <= main[2] and y + h <= main[3], (x, y, w, h))
        self.assertIn('name="Card" fill="page" border="rounded"', self.docs['Panel'])
        self.assertNotIn('name="TopBar"', self.docs['Panel'])
        # The example names an icon only where Extron's kit lists it, so the
        # glyph is checked where the kit is; the rest holds without it.
        if designsys.kit_root(self.p):
            self.assertIn('name="PC" icon="input_pc"', designsys.readme(self.p))
        self.assertEqual(self.p['examples']['source']['rect'][:2], [282, 0])

    def test_the_themes_are_set_by_page_role(self):
        text = designsys.readme(self.p)
        self.assertNotIn('The image is drawn on every page', text)
        self.assertIn('Set on each Page to the photograph Turbulence draws for its role', text)
        self.assertNotIn('the same on every artboard', self.docs['Page'])
        self.assertIn("Turbulence's working pages are composed the same way", text)
        self.assertIn('Its other pages are not composed so', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
