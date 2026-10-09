"""The Claude Design canvas -> spec translator (gdl/design.py).

Most of these feed the translator what the in-browser probe reports, so they
run anywhere. The last class lays a real canvas out in headless Chrome with
the Design type's runtime: it needs Chrome and the runtime file, named by
$GDL_DC_RUNTIME (the type's artifact-type/dc-runtime.js, fetched with the
Artifact tool), and skips without them.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from gdl import design, designsys, seeds  # noqa: E402
from gdl.spec import Panel, resolve_image  # noqa: E402

CANVAS = os.path.join(HERE, 'data', 'design-huddle')


def page(name, kind='page', **kw):
    return json.dumps(dict({'kind': kind, 'name': name, 'template': 'Afterburn',
                            'scheme': 'orange', 'background': 'page'}, **kw))


def ctl(rect, **g):
    return {'gdl': json.dumps(g), 'rect': rect, 'href': None}


def out(pg, *controls, stray=()):
    return {'pages': 1, 'page': {'gdl': pg, 'rect': [0, 0, 1280, 800]},
            'controls': list(controls), 'stray': list(stray), 'errors': []}


class Fake(design.Canvas):
    def __init__(self, boards):
        self.folder, self.chrome = None, None
        self.problems, self.notes = [], []
        self.index = {'title': 'T', 'order': list(boards),
                      'boards': {b: {'w': 1280, 'h': 800} for b in boards}}


def translate(rendered):
    return Fake(rendered).translate(rendered)


HOME = page('Home', start=True)
HELP = page('Help')
BTN = dict(kind='button', name='HelpBtn', text='Help', fill='raised', stroke='text-secondary',
           border='afterburn', color='text', size=14,
           states=[{'name': 'Off'}, {'name': 'On', 'fill': 'pressed', 'stroke': 'text'}])


class TestTranslate(unittest.TestCase):
    def test_a_page_background_is_laid_out_as_its_template_lays_it(self):
        """Mach stretches its 3:2 photo over the page; Afterburn fits its own."""
        for template, want in (('Mach', 'stretch'), ('Afterburn', None)):
            pg = json.dumps({'kind': 'page', 'name': 'Home', 'template': template,
                             'scheme': 'default' if template == 'Mach' else 'orange',
                             'background': 'page', 'background_image': 'x.png', 'start': True})
            spec, _, _ = translate({'Home.dc.html': out(pg)})
            self.assertEqual(spec['pages'][0].get('background_layout'), want, template)

    def test_boards_become_pages_with_their_controls(self):
        spec, problems, _ = translate({
            'Home.dc.html': out(HOME, ctl([1040.2, 24, 199.6, 64], **dict(BTN, nav='Help'))),
            'Help.dc.html': out(HELP, ctl([40, 640, 280, 100], **dict(BTN, name='Back', nav='Home'))),
        })
        self.assertEqual(problems, [])
        self.assertEqual([p['name'] for p in spec['pages']], ['Home', 'Help'])
        self.assertEqual(spec['start_page'], 'Home')
        c = spec['pages'][0]['controls'][0]
        self.assertEqual(c['rect'], [1040, 24, 200, 64])
        self.assertEqual(c['nav'], 'Help')
        self.assertEqual(spec['model'], 'TLP1035T')
        self.assertEqual(spec['_seed'], 'seeds/Afterburn 1035.gdl')

    def test_nav_names_the_artboard_and_becomes_its_page_name(self):
        spec, problems, _ = translate({
            'Home.dc.html': out(HOME, ctl([0, 0, 100, 64], **dict(BTN, nav='HelpPage'))),
            'HelpPage.dc.html': out(page('Huddle Help')),
        })
        self.assertEqual(problems, [])
        self.assertEqual(spec['pages'][0]['controls'][0]['nav'], 'Huddle Help')

    def test_a_nav_to_nowhere_is_a_problem(self):
        _, problems, _ = translate({'Home.dc.html': out(HOME, ctl([0, 0, 100, 64],
                                                                  **dict(BTN, nav='Nope')))})
        self.assertTrue(any("nav 'Nope' names no artboard" in p for p in problems), problems)

    def test_anything_painted_outside_a_component_is_refused(self):
        _, problems, _ = translate({'Home.dc.html': out(
            HOME, stray=[{'tag': 'div', 'rect': [10, 10, 200, 40], 'why': 'text "Welcome"'}])})
        self.assertTrue(any('not a component' in p and 'Welcome' in p for p in problems),
                        problems)

    def test_popups_carry_kind_group_and_size(self):
        spec, problems, _ = translate({
            'Home.dc.html': out(HOME),
            'Confirm.dc.html': out(page('Confirm', kind='popup', modal=True)),
            'Laptop.dc.html': out(page('Laptop', kind='popup', group='Sources',
                                       size=[880, 525])),
        })
        self.assertEqual(problems, [])
        confirm, laptop = spec['popups']
        self.assertTrue(confirm['modal'])
        self.assertNotIn('size', confirm)
        self.assertEqual((laptop['group'], laptop['size']), ('Sources', [880, 525]))

    def test_the_theme_holds_exactly_the_tokens_used(self):
        spec, _, _ = translate({'Home.dc.html': out(HOME, ctl([0, 0, 100, 64], **BTN))})
        self.assertEqual(spec['theme']['raised'], '#37394E')
        self.assertEqual(spec['theme']['pressed'], '#242634')   # an alias, resolved
        self.assertNotIn('alert', spec['theme'])

    def test_a_translucent_token_reaches_the_spec_alpha_first(self):
        """CSS writes alpha last, the spec first: Afterburn's scrim is black at
        alpha 166 - #000000A6 in CSS, #A6000000 in the spec."""
        card = page('Card', kind='popup', group='G', size=[880, 525], background='scrim')
        spec, _, _ = translate({'Home.dc.html': out(HOME), 'Card.dc.html': out(card)})
        self.assertEqual(spec['theme']['scrim'], '#A6000000')
        self.assertEqual(design.css_to_argb('#37394E'), '#37394E')

    def test_a_modal_carries_no_background(self):
        """Build draws every modal as the page beneath under black at alpha
        166, whatever background it was given."""
        modal = page('Confirm', kind='popup', modal=True, background='page')
        spec, _, _ = translate({'Home.dc.html': out(HOME), 'Confirm.dc.html': out(modal)})
        self.assertNotIn('background', spec['popups'][0])

    def test_the_scheme_picks_the_accent(self):
        home = page('Home', scheme='gold')
        spec, _, _ = translate({'Home.dc.html': out(
            home, ctl([0, 0, 100, 64], **dict(BTN, fill='accent')))})
        self.assertEqual(spec['theme']['accent'], '#D6B961')

    def test_one_template_and_one_scheme_per_panel(self):
        _, problems, _ = translate({'Home.dc.html': out(HOME),
                                    'Help.dc.html': out(page('Help', scheme='gold'))})
        self.assertTrue(any('one scheme per panel' in p for p in problems), problems)

    def test_two_start_pages_is_a_problem(self):
        _, problems, _ = translate({'A.dc.html': out(page('A', start=True)),
                                    'B.dc.html': out(page('B', start=True))})
        self.assertTrue(any('second start page' in p for p in problems), problems)

    def test_an_artboard_without_one_page_is_a_problem(self):
        _, problems, _ = translate({'Home.dc.html': out(HOME),
                                    'Loose.dc.html': {'pages': 0, 'controls': [], 'stray': [],
                                                      'errors': []}})
        self.assertTrue(any('exactly one Page' in p for p in problems), problems)

    def test_an_icon_the_kit_lacks_is_refused(self):
        _, problems, _ = translate({'Home.dc.html': out(
            HOME, ctl([0, 0, 100, 64], **dict(BTN, missing_icon=['440x440 rocket'])))})
        self.assertTrue(any("icon 'rocket' is not in Afterburn's 440x440 kit" in p
                            for p in problems), problems)

    def test_a_slider_with_no_kit_thumb_is_noted(self):
        """Without the kit the slider would keep its donor's thumb, in the
        donor's scheme - so say so rather than translate clean."""
        slider = ctl([1166, 210, 54, 380], kind='slider', name='Volume', fill='raised')
        real = design.designsys.slider_thumb
        design.designsys.slider_thumb = lambda p, s: None
        try:
            _, _, notes = translate({'Home.dc.html': out(HOME, slider)})
        finally:
            design.designsys.slider_thumb = real
        self.assertTrue(any('kit thumb' in n for n in notes), notes)

    def test_a_state_image_brings_its_kit_file_and_no_border_stays(self):
        if not designsys.kit_root(designsys.load('afterburn')):
            self.skipTest("Extron's Afterburn kit is not installed here")
        states = [{'name': 'Off', 'image': '440x440_help_nsel.png'},
                  {'name': 'On', 'image': '440x440_help-orange_sel.png', 'fill': 'pressed',
                   'border': 'afterburn-ellipse'}]
        spec, problems, _ = translate({'Home.dc.html': out(HOME, ctl(
            [0, 0, 64, 64], **dict(BTN, border='none', fill='none', stroke='none',
                                   states=states)))})
        self.assertEqual(problems, [])
        c = spec['pages'][0]['controls'][0]
        self.assertEqual(c['border'], 'none')
        self.assertEqual(c['states'][1]['border'], 'afterburn-ellipse')
        self.assertEqual(spec['images']['440x440_help_nsel.png'],
                         'Afterburn/Buttons/PNG/440x440/Help/440x440_help_nsel.png')

    def test_states_keep_only_their_looks(self):
        states = [{'name': 'Off'}, {'name': 'Live', 'fill': 'accent', 'color': 'page'}]
        spec, _, _ = translate({'Home.dc.html': out(
            HOME, ctl([0, 0, 100, 64], **dict(BTN, states=states, press='Live')))})
        c = spec['pages'][0]['controls'][0]
        self.assertEqual(c['states'], ['Off', {'name': 'Live', 'fill': 'accent', 'color': 'page'}])
        self.assertEqual(c['press'], 'Live')

    def test_the_spec_it_writes_checks_clean(self):
        spec, problems, _ = translate({
            'Home.dc.html': out(HOME, ctl([1040, 24, 200, 64], **dict(BTN, nav='Help'))),
            'Help.dc.html': out(HELP, ctl([40, 640, 280, 100], **dict(BTN, name='Back', nav='Home'))),
        })
        self.assertEqual(problems, [])
        self.assertEqual(Panel(spec).check(), [])


PANELS = ['TLP1035T', 'TLP725T']
SEEDS = {'TLP1035T': 'seeds/Afterburn 1035.gdl', 'TLP725T': 'seeds/Afterburn 725.gdl'}
ART = {'TLP1035T': ('6400x4000_bg1.png', 'Afterburn/Backgrounds/6400x4000/TLP 1025 & 1220/6400x4000_bg1-default.png'),
       'TLP725T': ('5120x3000_bg1-default.png', 'Afterburn/Backgrounds/5120x3000/TLP 725/5120x3000_bg1-default.png')}
SIZES = {'TLP1035T': [1280, 800], 'TLP725T': [1024, 600]}

# What translating a canvas of panels reads from disk: each panel's seed (Git LFS - a
# clone that skipped `git lfs pull` holds pointers, which the translator refuses) and
# its template's background art (Extron's kit, in vendor/ or the install, never in git).
needs_panel_files = unittest.skipUnless(
    all(seeds.usable(s) for s in SEEDS.values()) and all(resolve_image(f) for _, f in ART.values()),
    "needs the Afterburn 1035 and 725 seeds (git lfs pull) and Extron's Afterburn "
    'background art (vendor/ or the install)')


# A button as a panel's layout draws it: at the 725's 16 pt floor.
BTN16 = dict(BTN, size=16)


def panel_page(name, model, panels=PANELS, seed=None, **kw):
    """A derived Page's data-gdl, as the bundle writes it for `model`."""
    image, file = ART[model]
    return page(name, panel=model, panels=panels, tier='A', derived=True, size=SIZES[model],
                seed=SEEDS[model] if seed is None else seed, background_image=image,
                background_file=file, theme='default', **kw)


def part(gdl, rect):
    return {'gdl': json.dumps(gdl), 'rect': rect}


def translate_panels(rendered):
    boards = next(iter(rendered.values()))
    return Fake(boards).translate_panels(rendered)


class TestPanels(unittest.TestCase):
    """One canvas, one spec per panel it lists - fed what the probe reports."""

    def home(self, model, *controls, parts=(), seed=None):
        o = out(panel_page('Home', model, start=True, seed=seed), *controls)
        o['parts'], o['problems'] = list(parts), []
        return o

    @needs_panel_files
    def test_each_panel_gets_its_own_spec(self):
        specs, problems, _ = translate_panels({m: {'Home.dc.html': self.home(m, ctl([40, 40, 200, 64], **BTN16))}
                                               for m in PANELS})
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
        for m in PANELS:
            spec = specs[m]
            self.assertEqual((spec['model'], spec['size'], spec['_seed']), (m, SIZES[m], SEEDS[m]))
            self.assertEqual(spec['pages'][0]['background_image'], ART[m][0])
            self.assertEqual(spec['images'][ART[m][0]], ART[m][1])
            self.assertEqual(Panel(json.loads(json.dumps(spec))).check(), [])

    def test_a_missing_seed_refuses_every_panel(self):
        rendered = {m: {'Home.dc.html': self.home(m, ctl([40, 40, 200, 64], **BTN),
                                                  seed='seeds/Afterburn 999.gdl' if m == 'TLP725T' else None)}
                    for m in PANELS}
        specs, problems, _ = translate_panels(rendered)
        self.assertIsNone(specs)
        self.assertTrue(any('New-GdlSeed.ps1 -PanelType' in p and "'TLP Pro 725T'" in p
                            for p in problems['TLP725T']), problems)

    def test_a_panel_with_no_seed_says_how_to_make_one(self):
        rendered = {m: {'Home.dc.html': self.home(m, ctl([40, 40, 200, 64], **BTN), seed='' if m == 'TLP725T' else None)}
                    for m in PANELS}
        specs, problems, _ = translate_panels(rendered)
        self.assertIsNone(specs)
        self.assertTrue(any('no seed' in p and 'New-GdlSeed.ps1' in p for p in problems['TLP725T']), problems)
        # under the name seeds/ already gives that size, and with the step after
        # it: a made seed is not used until its theme's profile lists it
        self.assertTrue(any("-Output 'seeds\\Afterburn 725.gdl'" in p for p in problems['TLP725T']), problems)
        self.assertTrue(any('gdl/designsys/afterburn.json' in p for p in problems['TLP725T']), problems)

    @needs_panel_files
    def test_parts_become_popups_and_pages(self):
        pop = {'kind': 'popup', 'name': 'Home Sources', 'group': 'Home Sources', 'size': [400, 120]}
        pg = {'kind': 'page', 'name': 'Home Cameras', 'host': 'Home', 'size': [1024, 600],
              'background': 'page', 'background_image': ART['TLP725T'][0], 'background_file': ART['TLP725T'][1]}
        laptop = dict(ctl([10, 10, 100, 100], kind='button', name='Laptop', text='Laptop'), part=0)
        cam = dict(ctl([20, 20, 100, 100], kind='button', name='Cam', text='Cam'), part=1)
        back = dict(ctl([10, 540, 80, 60], kind='button', name='Cameras Back', text='Back', derived=True,
                        nav='Home'), part=1)
        region = ctl([300, 200, 400, 120], kind='popup_ref', name='Sources Region', group='Home Sources')
        rendered = {m: {'Home.dc.html': self.home(m, region, laptop, cam, back,
                                                  parts=[part(pop, [300, 200, 400, 120]),
                                                         part(pg, [0, 0, 1024, 600])])}
                    for m in ['TLP725T']}
        specs, problems, _ = Fake(['Home.dc.html']).translate_panels(rendered)
        self.assertEqual(problems, {'TLP725T': []})
        spec = specs['TLP725T']
        self.assertEqual([(p['name'], p.get('group'), p.get('size')) for p in spec['popups']],
                         [('Home Sources', 'Home Sources', [400, 120])])
        self.assertEqual([c['name'] for c in spec['popups'][0]['controls']], ['Laptop'])
        self.assertEqual(spec['popups'][0]['controls'][0]['rect'], [10, 10, 100, 100])
        cams = next(p for p in spec['pages'] if p['name'] == 'Home Cameras')
        self.assertEqual(cams['background_image'], ART['TLP725T'][0])
        self.assertEqual({c['name'] for c in cams['controls']}, {'Cam', 'Cameras Back'})
        back = next(c for c in cams['controls'] if c['name'] == 'Cameras Back')
        self.assertEqual((back['nav'], back['derived']), ('Home', True))
        home = next(p for p in spec['pages'] if p['name'] == 'Home')
        self.assertEqual([c['name'] for c in home['controls']], ['Sources Region'])
        self.assertEqual(Panel(json.loads(json.dumps(spec))).check(), [])

    @needs_panel_files
    def test_derived_nav_names_a_part_not_an_artboard(self):
        nxt = dict(ctl([300, 260, 80, 60], kind='button', name='Sources Next', text='Next', derived=True,
                       nav='Home Sources 2'), part=0)
        pops = [part({'kind': 'popup', 'name': 'Home Sources', 'group': 'Home Sources', 'size': [400, 320]},
                     [0, 0, 400, 320]),
                part({'kind': 'popup', 'name': 'Home Sources 2', 'group': 'Home Sources', 'size': [400, 320]},
                     [0, 0, 400, 320])]
        region = ctl([300, 200, 400, 320], kind='popup_ref', name='Sources Region', group='Home Sources')
        specs, problems, _ = Fake(['Home.dc.html']).translate_panels(
            {'TLP725T': {'Home.dc.html': self.home('TLP725T', region, nxt, parts=pops)}})
        self.assertEqual(problems, {'TLP725T': []})
        c = specs['TLP725T']['popups'][0]['controls'][0]
        self.assertEqual(c['nav'], 'Home Sources 2')

    def test_a_derived_name_colliding_with_the_canvas_is_a_problem(self):
        pg = {'kind': 'page', 'name': 'Help', 'host': 'Home', 'size': [1024, 600], 'background': 'page'}
        rendered = {'TLP725T': {'Home.dc.html': self.home('TLP725T', parts=[part(pg, [0, 0, 1024, 600])]),
                                'Help.dc.html': dict(out(panel_page('Help', 'TLP725T')), parts=[], problems=[])}}
        specs, problems, _ = Fake(['Home.dc.html', 'Help.dc.html']).translate_panels(rendered)
        self.assertIsNone(specs)
        self.assertTrue(any("'Help'" in p and 'twice' in p for p in problems['TLP725T']), problems)

    def test_pages_must_agree_on_their_panels(self):
        rendered = {m: {'Home.dc.html': self.home(m),
                        'Help.dc.html': dict(out(panel_page('Help', m, panels=['TLP1035T'])), parts=[], problems=[])}
                    for m in PANELS}
        specs, problems, _ = Fake(['Home.dc.html', 'Help.dc.html']).translate_panels(rendered)
        self.assertIsNone(specs)
        self.assertTrue(any('panels' in p for p in problems['TLP1035T']), problems)

    def test_what_a_component_could_not_lay_out_is_a_problem(self):
        o = self.home('TLP725T')
        o['problems'] = ["the main area needs 223 px of a TLP725T's 190 - it does not fit"]
        specs, problems, _ = Fake(['Home.dc.html']).translate_panels({'TLP725T': {'Home.dc.html': o}})
        self.assertIsNone(specs)
        self.assertTrue(any('does not fit' in p for p in problems['TLP725T']), problems)

    @needs_panel_files
    def test_a_border_the_seed_lacks_is_its_own_of_that_thickness(self):
        """The 320's seed has no 'Afterburn - 10 Radius 2 Thick'; the model
        table maps the profile's `afterburn` to its own 7 Radius 2 Thick."""
        o = out(panel_page('Home', 'TLP725T', start=True,
                           borders={'afterburn': 'Afterburn - 7 Radius 2 Thick'}),
                ctl([40, 40, 200, 64], **BTN16))
        o['parts'], o['problems'] = [], []
        specs, problems, _ = Fake(['Home.dc.html']).translate_panels({'TLP725T': {'Home.dc.html': o}})
        self.assertEqual(problems, {'TLP725T': []})
        c = specs['TLP725T']['pages'][0]['controls'][0]
        self.assertEqual(c['border'], 'Afterburn - 7 Radius 2 Thick')
        self.assertEqual(Panel(json.loads(json.dumps(specs['TLP725T']))).check(), [])

    @needs_panel_files
    def test_the_same_control_has_one_id_on_every_panel(self):
        """A program drives every panel with one set of IDs, so a canvas control
        keeps its ID on every panel - even where the layout added a control
        ahead of it - and what the layout added gets its own, the same on
        every panel it is on."""
        laptop = dict(BTN16, name='Laptop', text='Laptop')
        prev = dict(BTN16, name='Sources Previous', text='Previous', derived=True, nav='Home')
        rendered = {'TLP1035T': {'Home.dc.html': self.home('TLP1035T', ctl([40, 40, 200, 64], **laptop))},
                    'TLP725T': {'Home.dc.html': self.home('TLP725T', ctl([10, 10, 80, 60], **prev),
                                                          ctl([40, 140, 200, 64], **laptop))}}
        specs, problems, _ = translate_panels(rendered)
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
        ids = {m: {c['name']: c['id'] for c in specs[m]['pages'][0]['controls']} for m in PANELS}
        self.assertEqual(ids['TLP1035T']['Laptop'], ids['TLP725T']['Laptop'])
        self.assertEqual(ids['TLP1035T']['Laptop'], 1001)
        self.assertGreaterEqual(ids['TLP725T']['Sources Previous'], 50001)

    @needs_panel_files
    def test_an_unnamed_button_on_a_canvas_of_panels_is_a_problem(self):
        nameless = {k: v for k, v in BTN.items() if k != 'name'}
        specs, problems, _ = translate_panels({m: {'Home.dc.html': self.home(m, ctl([40, 40, 200, 64], **nameless))}
                                               for m in PANELS})
        self.assertIsNone(specs)
        self.assertTrue(any('name it' in q for q in problems['TLP1035T']), problems)

    @needs_panel_files
    def test_the_first_popup_of_a_derived_group_is_shown_by_the_program(self):
        pops = [part({'kind': 'popup', 'name': 'Home Sources', 'group': 'Home Sources', 'size': [400, 320]},
                     [0, 0, 400, 320]),
                part({'kind': 'popup', 'name': 'Home Sources 2', 'group': 'Home Sources', 'size': [400, 320]},
                     [0, 0, 400, 320])]
        region = ctl([300, 200, 400, 320], kind='popup_ref', name='Sources Region', group='Home Sources',
                     derived=True)
        specs, problems, _ = Fake(['Home.dc.html']).translate_panels(
            {'TLP725T': {'Home.dc.html': self.home('TLP725T', region, parts=pops)}})
        self.assertEqual(problems, {'TLP725T': []})
        by = {p['name']: p for p in specs['TLP725T']['popups']}
        self.assertEqual(by['Home Sources'].get('reached_by'), 'program')
        self.assertIsNone(by['Home Sources 2'].get('reached_by'))

    def test_a_spec_filed_under_another_panel_is_refused(self):
        """A `preview` left on the Pages drew the first panel's render as the
        preview panel, and its spec was filed under the first panel: the 1035's
        folder held a 725, built twice, with no problem raised."""
        rendered = {'TLP1035T': {'Home.dc.html': self.home('TLP725T', ctl([40, 40, 200, 64], **BTN16))},
                    'TLP725T': {'Home.dc.html': self.home('TLP725T', ctl([40, 40, 200, 64], **BTN16))}}
        specs, problems, _ = translate_panels(rendered)
        self.assertIsNone(specs)
        self.assertTrue(any('TLP725T' in p and 'preview' in p for p in problems['TLP1035T']), problems)

    @needs_panel_files
    def test_a_levels_bar_reaches_the_plan(self):
        """A level's filled part is the scheme's; a clone's is its donor's
        scheme-1 #626ACF. The 525's volume built in it under a gold scheme."""
        lv = ctl([700, 96, 66, 45], kind='level', name='Volume', fill='raised', track=15,
                 orientation='up', bar='accent-2')
        specs, problems, _ = Fake(['Home.dc.html']).translate_panels(
            {'TLP725T': {'Home.dc.html': self.home('TLP725T', lv)}})
        self.assertEqual(problems, {'TLP725T': []})
        c = specs['TLP725T']['pages'][0]['controls'][0]
        self.assertEqual(c['bar'], 'accent-2')
        op = Panel(json.loads(json.dumps(specs['TLP725T']))).plan()['pages'][0]['controls'][0]
        self.assertIsNotNone(op['gauge_fill'])

    @needs_panel_files
    def test_a_derived_popup_shows_the_page_through_it(self):
        """A Group's cells are drawn over the page, so its popup has no page
        fill of its own - as the seed's own group popups have none. Given
        none, a spec popup takes black, and the 525's sources built as a
        black box over the page."""
        pop = part({'kind': 'popup', 'name': 'Home Sources', 'group': 'Home Sources', 'size': [400, 120]},
                   [300, 200, 400, 120])
        region = ctl([300, 200, 400, 120], kind='popup_ref', name='Sources Region', group='Home Sources',
                     derived=True)
        specs, problems, _ = Fake(['Home.dc.html']).translate_panels(
            {'TLP725T': {'Home.dc.html': self.home('TLP725T', region, parts=[pop])}})
        self.assertEqual(problems, {'TLP725T': []})
        op = Panel(json.loads(json.dumps(specs['TLP725T']))).plan()['popups'][0]
        self.assertEqual(op['name'], 'Home Sources')
        self.assertEqual(op['background'] >> 24, 0, hex(op['background']))

    @needs_panel_files
    def test_a_panels_spec_must_check_clean(self):
        """Two buttons a panel's layout grew into each other are refused when
        the canvas is translated, not when its build is started."""
        a = ctl([40, 40, 200, 64], **dict(BTN16, name='A'))
        b = ctl([200, 50, 200, 64], **dict(BTN16, name='B'))
        specs, problems, _ = translate_panels({m: {'Home.dc.html': self.home(m, a, b)} for m in PANELS})
        self.assertIsNone(specs)
        self.assertTrue(any('overlap' in p for p in problems['TLP725T']), problems)

    def test_text_that_overflows_its_box_is_a_problem(self):
        """The probe saw the caption spill past its control at this panel's
        type: built so, it would be clipped."""
        o = self.home('TLP725T', dict(ctl([40, 40, 200, 64], **BTN), overflow=True))
        specs, problems, _ = Fake(['Home.dc.html']).translate_panels({'TLP725T': {'Home.dc.html': o}})
        self.assertIsNone(specs)
        self.assertTrue(any('does not fit' in p and 'HelpBtn' in p for p in problems['TLP725T']), problems)

    @needs_panel_files
    def test_specs_are_written_one_folder_a_panel(self):
        specs, _, _ = translate_panels({m: {'Home.dc.html': self.home(m)} for m in PANELS})
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        written = design.write_panels(specs, d)
        self.assertEqual(sorted(os.path.relpath(w, d).replace(os.sep, '/') for w in written),
                         ['TLP1035T/spec.json', 'TLP725T/spec.json'])
        with open(os.path.join(d, 'TLP725T', 'spec.json'), encoding='utf-8') as fh:
            self.assertEqual(json.load(fh)['model'], 'TLP725T')

    @needs_panel_files
    def test_a_panel_no_longer_listed_leaves_no_spec(self):
        """A spec an earlier translate wrote for a panel the canvas has since
        dropped was picked up by the map and built - minutes a panel - and
        took over the panel order. Its built files stay; its spec goes."""
        specs, _, _ = translate_panels({m: {'Home.dc.html': self.home(m)} for m in PANELS})
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, 'TLP320M'))
        for f in ('spec.json', 'Huddle.gdl'):
            open(os.path.join(d, 'TLP320M', f), 'w').close()
        design.write_panels(specs, d)
        self.assertFalse(os.path.exists(os.path.join(d, 'TLP320M', 'spec.json')))
        self.assertTrue(os.path.exists(os.path.join(d, 'TLP320M', 'Huddle.gdl')))
        design.clear_panels(d)
        self.assertEqual([m for m in PANELS if os.path.exists(os.path.join(d, m, 'spec.json'))], [])


class TestCompare(unittest.TestCase):
    """The sign-off page for a canvas of panels: a section per panel, each
    artboard and each derived page or popup as designed beside it as built.
    Chrome is stood in for; the built side is a real built file (a seed)."""

    def setUp(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; compare renders the built panel with it')
        from _corpus import usable
        self.seeds = {'TLP1035T': os.path.join(HERE, '..', 'seeds', 'Afterburn 1035.gdl'),
                      'TLP725T': os.path.join(HERE, '..', 'seeds', 'Afterburn 725.gdl')}
        if not all(usable(p) for p in self.seeds.values()):
            self.skipTest('seeds not present (git lfs pull)')

    def test_a_section_per_panel_naming_each_part(self):
        from PIL import Image
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        canvas = os.path.join(d, 'canvas')
        os.makedirs(canvas)
        with open(os.path.join(canvas, 'canvas.json'), 'w', encoding='utf-8') as fh:
            json.dump({'title': 'T', 'order': ['Home.dc.html'],
                       'boards': {'Home.dc.html': {'w': 1280, 'h': 800}}}, fh)
        with open(os.path.join(canvas, 'Home.dc.html'), 'w', encoding='utf-8') as fh:
            fh.write('<html><head></head><body></body></html>')
        built = os.path.join(d, 'built')
        for m, seed in self.seeds.items():
            os.makedirs(os.path.join(built, m))
            shutil.copy(seed, os.path.join(built, m, 'Huddle.gdl'))
        part = {'kind': 'popup', 'name': 'Main Select Source Sources', 'group': 'X', 'size': [400, 200]}

        def fake_render(path, chrome, size, timeout=90, panel=None):
            o = out(panel_page('Main Select Source', panel or 'TLP1035T'))
            o['parts'] = [{'gdl': json.dumps(part), 'rect': [0, 0, 400, 200]}] if panel == 'TLP725T' else []
            o['problems'] = []
            return o

        def fake_shot(path, chrome, size, png, timeout=90):
            Image.new('RGB', tuple(size), (20, 20, 20)).save(png)

        saved = design.render, design.screenshot, design.find_chrome
        design.render, design.screenshot = fake_render, fake_shot
        design.find_chrome = lambda given=None: 'chrome'
        try:
            scores = design.compare(canvas, built, os.path.join(d, 'signoff'))
        finally:
            design.render, design.screenshot, design.find_chrome = saved
        with open(os.path.join(d, 'signoff', 'index.html'), encoding='utf-8') as fh:
            page = fh.read()
        self.assertEqual(page.count('<section class="panel">'), 2)
        self.assertIn('TLP725T', page)
        self.assertIn('Main Select Source Sources', page)
        self.assertTrue(scores)


class TestSeeds(unittest.TestCase):
    def test_an_lfs_pointer_is_not_a_seed(self):
        from gdl import seeds
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        f = os.path.join(d, 'x.gdl')
        with open(f, 'wb') as fh:
            fh.write(b'version https://git-lfs.github.com/spec/v1\noid sha256:00\nsize 1\n')
        self.assertFalse(seeds.usable(f))
        self.assertFalse(seeds.usable(os.path.join(d, 'missing.gdl')))

    def test_the_command_that_makes_one(self):
        from gdl import seeds
        self.assertEqual(seeds.command('Afterburn', 'TLP725T', 'seeds/Afterburn 725.gdl'),
                         "powershell\\New-GdlSeed.ps1 -PanelType 'TLP Pro 725T' -Model TLP725T "
                         "-Theme 'Afterburn' -Output 'seeds\\Afterburn 725.gdl'")
        self.assertIn("-PanelType 'TLC Pro 726M'", seeds.command('Afterburn', 'TLC726M', None))

    # Each seed here whose name follows seeds/'s convention, '<Theme> <size>.gdl',
    # by a model it was made for. Not in it: 835's '(Project1)' (the wizard's own
    # default, kept), the ECP seeds (named for their preset) and the Zoom Rooms
    # pair (named by hand).
    MADE = [('Afterburn', 'TLP1035T', '1035'), ('Afterburn', 'TLP1035M', '1035'),
            ('Afterburn', 'TLP1230WTG', '1230W'), ('Afterburn', 'TLP1535M', '1535'),
            ('Afterburn', 'TLP300M', '300M Portrait'), ('Afterburn', 'TLP320M', '320'),
            ('Afterburn', 'TLP525T', '525'), ('Afterburn', 'TLP725T', '725'),
            ('Mach', 'TLP1035T', '1035'), ('Mach', 'TLP1535M', '1535'), ('Mach', 'TLP300M', '300M Portrait'),
            ('Shockwave', 'TLP1035T', '1035'), ('Shockwave', 'TLP1535M', '1535'),
            ('Turbulence', 'TLP1035T', '1035')]

    def test_a_new_seed_is_named_as_the_ones_here_are(self):
        """'Afterburn 725.gdl', not 'Afterburn TLP725T.gdl': the file a seed is
        made as is the one a later seed of the same size is found beside."""
        from gdl import seeds
        for theme, model, size in self.MADE:
            self.assertTrue(os.path.isfile(os.path.join(HERE, '..', 'seeds', f'{theme} {size}.gdl')),
                            f'{theme} {size}.gdl is not in seeds/ - the table above has drifted')
            out = 'seeds\\' + f'{theme} {size}.gdl'
            self.assertIn(f"-Output '{out}'", seeds.command(theme, model, None), (theme, model))

    def test_the_nine_seeds_still_to_make(self):
        from gdl import seeds
        for theme in ('Mach', 'Shockwave', 'Turbulence'):
            for model, size in (('TLP725T', '725'), ('TLP525T', '525'), ('TLP320M', '320')):
                out = 'seeds\\' + f'{theme} {size}.gdl'
                self.assertIn(f"-Output '{out}'", seeds.command(theme, model, None), (theme, model))


RUNTIME = os.environ.get('GDL_DC_RUNTIME')


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestInChrome(unittest.TestCase):
    """The checked-in canvas, laid out by the real runtime."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        shutil.copytree(CANVAS, self.dir, dirs_exist_ok=True)
        shutil.copy(RUNTIME, os.path.join(self.dir, 'support.js'))
        comps = os.path.join(self.dir, 'ds', 'extronafterburn', 'components')
        os.makedirs(comps)
        p = designsys.load('afterburn')
        with open(os.path.join(comps, 'bundle.js'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.bundle(p))
        with open(os.path.join(comps, 'bundle.css'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.BUNDLE_CSS)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_the_huddle_canvas_translates_and_checks_clean(self):
        # Its buttons name kit icons, which the translator refuses without the kit.
        if not designsys.kit_root(designsys.load('afterburn')):
            self.skipTest("Extron's Afterburn kit is not installed here")
        spec, problems, _ = design.Canvas(self.dir).translate()
        self.assertEqual(problems, [])
        self.assertEqual([p['name'] for p in spec['pages']], ['Huddle Home'])
        # Help is a modal, as Extron's own templates draw it: a card over the
        # dimmed page, not a page flip.
        modals = {p['name'] for p in spec['popups'] if p.get('modal')}
        self.assertEqual(modals, {'Huddle Help', 'Confirm Room Off'})
        home = {c['name']: c for c in spec['pages'][0]['controls']}
        self.assertEqual(home['HelpBtn']['nav'], 'Huddle Help')
        # A flex cell inside the MainArea, measured after layout: three 110 px
        # sources spread across 440 at 238,330, offset by the squircle's 183,24.
        self.assertEqual(home['Wireless']['rect'], [586, 354, 110, 110])
        self.assertEqual(spec['images']['6400x4000_bg4-grape.png'],
                         'Afterburn/Backgrounds/6400x4000/TLP 1025 & 1220/6400x4000_bg4-grape.png')
        self.assertEqual(home['RoomOff']['nav'], 'Confirm Room Off')
        if designsys.kit_root(designsys.load('afterburn')):
            # Grape pairs with the medium-blue scheme, so a selected source
            # draws the kit's med-blue image; the unselected ones, no accent.
            self.assertEqual([s['image'] for s in home['Laptop']['states']],
                             ['756x756_laptop_nsel.png', '756x756_laptop_nsel.png',
                              '756x756_laptop-med-blue_sel.png'])
            self.assertIn('756x756_laptop-med-blue_sel.png', spec['images'])
            # Its slider thumb is the scheme's secondary accent: gold.
            slider = home['VolumeSlider']
            self.assertEqual(slider['thumb_image'], '440x440_thumb-1-gold_sel.png')
            self.assertIn(slider['thumb_image'], spec['images'])
        # A left clock says so: the spec's own default is center.
        self.assertEqual(home['Date']['align'], 'left')
        self.assertEqual(Panel(spec).check(), [])

    def _translate(self, template, data):
        """A checked-in canvas laid out with `template`'s current bundle."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copytree(os.path.join(HERE, 'data', data), d, dirs_exist_ok=True)
        shutil.copy(RUNTIME, os.path.join(d, 'support.js'))
        p = designsys.load(template)
        comps = os.path.join(d, 'ds', p['namespace'].lower(), 'components')
        os.makedirs(comps)
        with open(os.path.join(comps, 'bundle.js'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.bundle(p, art=False))
        with open(os.path.join(comps, 'bundle.css'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.BUNDLE_CSS)
        return p, design.Canvas(d).translate()

    def test_mach_source_tiles_carry_their_names(self):
        """The kit's 440x440 source art sits high in the tile to leave the
        caption room below it, so the name goes on the tile: a Label under a
        captionless tile leaves the icon off-center (owner's review)."""
        p, (spec, problems, _) = self._translate('mach', 'design-huddle-mach')
        if not designsys.kit_root(p):
            self.skipTest("Extron's Mach kit is not installed here")
        self.assertEqual(problems, [])
        home = {c['name']: c for c in spec['pages'][0]['controls']}
        # Three line breaks down, as the seed's 150x150 Camera 1 reaches its caption.
        self.assertEqual([home[n].get('text') for n in ('Laptop', 'Wireless', 'RoomPC')],
                         ['\r\n\r\n\r\nLaptop', '\r\n\r\n\r\nWireless', '\r\n\r\n\r\nRoom PC'])
        self.assertFalse({'LaptopLabel', 'WirelessLabel', 'PCLabel'} & set(home))
        self.assertEqual(Panel(spec).check(), [])

    def test_the_shockwave_canvas_translates_and_checks_clean(self):
        """Shockwave's buttons are its kit's images, one per state."""
        p, (spec, problems, _) = self._translate('shockwave', 'design-huddle-shockwave')
        if not designsys.kit_root(p):
            self.skipTest("Extron's Shockwave kit is not installed here")
        self.assertEqual(problems, [])
        home = {c['name']: c for c in spec['pages'][0]['controls']}
        # The source tabs are centered on the page (owner's review).
        left, right = home['Laptop']['rect'], home['RoomPC']['rect']
        self.assertEqual(left[0] + (right[0] + right[2]), 1280)
        # At rest a button is its color's ring, lit its color's fill.
        self.assertEqual([s['image'] for s in home['RoomOff']['states']],
                         ['960x440_red_outline_nsel.png', '960x440_red_sel.png'])
        # A state can change color: Warming lights yellow.
        self.assertEqual([s['image'] for s in home['Display']['states']],
                         ['712x440_gray_nsel.png', '712x440_yellow_sel.png',
                          '712x440_gray_sel.png', '712x440_yellow_outline_nsel.png'])
        # The kit's icon sits at the left and the caption is centered past it,
        # pushed right by leading spaces, as the seed's Accept Call is.
        self.assertEqual(home['EndCall'].get('align', 'center'), 'center')  # the spec's default
        self.assertEqual(home['EndCall']['text'], ' ' * 11 + 'End Call')
        # The thumb is 52 across and 34 along the rail, as the kit draws it.
        self.assertEqual((home['VolumeSlider']['thumb'], home['VolumeSlider']['thumb_height']), (52, 34))
        # The rail is the kit's art too, and reaches the build with its files.
        rail = (home['VolumeSlider'].get('track_image'), home['VolumeSlider'].get('fill_image'))
        self.assertEqual(rail, ('156x1026_sw_track_bg.png', '156x1026_sw_fill.png'))
        self.assertEqual(spec['images']['156x1026_sw_fill.png'], 'Shockwave/Slider/156x1026_sw_fill.png')
        close = {c['name']: c for c in spec['popups'][0]['controls']}['Close']
        self.assertEqual([s['image'] for s in close['states']], ['black_close.png', 'white_close.png'])
        self.assertEqual(spec['images']['white_close.png'], 'Shockwave/icons/440x440 White/white_close.png')
        self.assertEqual(Panel(spec).check(), [])

    def test_the_turbulence_canvas_translates_and_checks_clean(self):
        """Turbulence's art lives only in its seed and templates, and Extron
        named a fifth of its pairs apart - each state must still get its own."""
        p, (spec, problems, _) = self._translate('turbulence', 'design-huddle-turbulence')
        if not designsys.kit_root(p):
            self.skipTest("Turbulence's art is not extracted here (python -m gdl.designsys extract turbulence)")
        self.assertEqual(problems, [])
        home = {c['name']: c for c in spec['pages'][0]['controls']}

        def images(c):
            return [s['image'] for s in c['states']]

        # Pairs the file names do not make: a ring that rests white and lights
        # green, a source tile that rests solid.
        self.assertEqual(images(home['Mute']), ['440x440_volume_mute_white_nsel.png',
                                                '440x440_volume_mute_sel.png'])
        self.assertEqual(images(home['Laptop']), ['504x504_input_laptop_solid_text_nsel.png',
                                                  '504x504_input_laptop_text_sel.png'])
        # The seed's captions: two breaks under a source's glyph, one under a call's.
        self.assertEqual(home['Laptop']['text'], '\r\n\r\nLaptop')
        self.assertEqual(home['EndCall']['text'], '\r\nEnd Call')
        # The confirmation's Power Down rests green, as the seed's does.
        confirm = {c['name']: c for c in spec['popups'][1]['controls']}
        self.assertEqual(images(confirm['ShutDown']), ['440x440_vc_power-dn_green_nsel.png',
                                                       '440x440_vc_power-dn_sel.png'])
        # The rail is art: it reaches the spec with its files, from vendor/.
        slider = home['VolumeSlider']
        self.assertEqual((slider['track_image'], slider['fill_image'], slider['thumb_image']),
                         ('52x535_turb_slider_bg.png', '52x535_turb_slider_fill.png',
                          '102x102_thumb_turb_sq.png'))
        self.assertEqual(spec['images']['52x535_turb_slider_bg.png'],
                         'Turbulence/52x535_turb_slider_bg.png')
        self.assertEqual(Panel(spec).check(), [])

    def test_a_held_button_draws_its_press_state(self):
        """The panel shows a button's press state while it is held, so the
        canvas does: Help shows the kit's selected icon on its round fill."""
        import re
        import subprocess
        probe = """<script>
setTimeout(async function () {
  var art = window.ExtronAfterburn.profile.kit.art, byUri = {};
  Object.keys(art).forEach(function (f) { byUri[art[f]] = f; });
  function look(el) { var m = (el.style.background || '').match(/url\\("([^"]+)"\\)/);
                      return m ? byUri[m[1]] : 'none'; }
  function tick() { return new Promise(function (r) { setTimeout(r, 60); }); }
  var el = Array.prototype.find.call(document.querySelectorAll('.xgdl-button'), function (e) {
    return JSON.parse(e.getAttribute('data-gdl')).name === 'HelpBtn'; });
  var out = [look(el)];
  el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); await tick();
  out.push(look(el));
  el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true })); await tick();
  out.push(look(el));
  var pre = document.createElement('pre'); pre.id = 'out'; pre.textContent = out.join(' ');
  document.body.appendChild(pre);
}, 2500);
</script>"""
        if not designsys.kit_root(designsys.load('afterburn')):
            self.skipTest("Extron's Afterburn kit is not installed here")
        path = os.path.join(self.dir, 'Home.dc.html')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(src.replace('</body>', probe + '</body>'))
        r = subprocess.run([design.find_chrome(), '--headless=new', '--disable-gpu',
                            '--allow-file-access-from-files', '--virtual-time-budget=8000',
                            '--dump-dom', 'file:///' + path.replace(os.sep, '/')],
                           capture_output=True, text=True, encoding='utf-8', timeout=120)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout, re.S)
        self.assertIsNotNone(m, r.stderr[-500:])
        self.assertEqual(m.group(1).split(), ['440x440_help_nsel.png',
                                              '440x440_help-med-blue_sel.png',
                                              '440x440_help_nsel.png'])

    def test_a_stray_painted_element_is_refused(self):
        path = os.path.join(self.dir, 'Help.dc.html')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        src = src.replace('</x-import>\n</div>\n</x-dc>',
                          '<div style="position: absolute; left: 900px; top: 40px; '
                          'background: #ff0000; width: 80px; height: 40px"></div>\n'
                          '</x-import>\n</div>\n</x-dc>', 1)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(src)
        _, problems, _ = design.Canvas(self.dir).translate()
        self.assertTrue(any('Help.dc.html' in p and 'not a component' in p for p in problems),
                        problems)


PANELS_CANVAS = os.path.join(HERE, 'data', 'design-panels')


def _inside(rect, box, slack=1):
    x, y, w, h = rect
    bx, by, bw, bh = box
    return x >= bx - slack and y >= by - slack and x + w <= bx + bw + slack and y + h <= by + bh + slack


class _Probe:
    """A checked-in canvas with the current Afterburn bundle, each board laid
    out once per panel and the probe's output kept."""

    CANVAS = None

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        shutil.copytree(cls.CANVAS, cls.dir, dirs_exist_ok=True)
        shutil.copy(RUNTIME, os.path.join(cls.dir, 'support.js'))
        comps = os.path.join(cls.dir, 'ds', 'extronafterburn', 'components')
        os.makedirs(comps)
        with open(os.path.join(comps, 'bundle.js'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.bundle(designsys.load('afterburn'), art=False))
        with open(os.path.join(comps, 'bundle.css'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.BUNDLE_CSS)
        cls.seen = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def probe(self, board, panel=None, edit=None):
        """{name: (data-gdl, rect)} and the page's data-gdl, as `panel` draws it."""
        key = (board, panel, edit)
        if key not in self.seen:
            path = os.path.join(self.dir, board)
            if edit:
                with open(path, encoding='utf-8') as fh:
                    src = fh.read()
                path = os.path.join(self.dir, 'edited-' + board)
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(src.replace(*edit))
            out = design.render(path, design.find_chrome(), (1280, 800), panel=panel)
            ctl = {}
            for c in out['controls']:
                g = json.loads(c['gdl'])
                ctl[g.get('name')] = (g, [round(v) for v in c['rect']], c.get('overflow'))
            self.seen[key] = (json.loads(out['page']['gdl']), ctl, out)
        return self.seen[key]


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestPanelsInChrome(_Probe, unittest.TestCase):
    """One canvas, drawn for each of its panels by the components themselves:
    the huddle, panel-aware, laid out for the 1035 it was drawn on and for the
    725, 525 and 320 it also lists."""

    CANVAS = PANELS_CANVAS
    MAIN = ('RoomName', 'CallState', 'Display', 'EndCall', 'Date', 'Time')
    SOURCES = ('Laptop', 'Wireless', 'RoomPC')
    RAIL = ('VolumeSlider', 'Mute', 'HelpBtn', 'RoomOff')

    def test_the_design_panel_is_drawn_as_designed(self):
        """Listing panels changes nothing on the panel the canvas was drawn on."""
        page, ctl, out = self.probe('Home.dc.html')
        self.assertEqual(page['size'], [1280, 800])
        self.assertEqual(page['panel'], 'TLP1035T')
        self.assertEqual(page['panels'], ['TLP1035T', 'TLP725T', 'TLP525T', 'TLP320M'])
        # The Sources group's cells, centred in its 916x250 box at 0,210.
        self.assertEqual(ctl['Wireless'][1], [183 + 403, 24 + 280, 110, 110])
        self.assertEqual(ctl['EndCall'][1], [183 + 560, 24 + 560, 154, 64])
        self.assertEqual(out.get('problems', []), [])

    def test_the_725_home_sits_in_the_1020_squircle(self):
        page, ctl, _ = self.probe('Home.dc.html', 'TLP725T')
        self.assertEqual(page['size'], [1024, 600])
        self.assertEqual(page['background_image'], '5120x3000_bg4-grape.png')
        self.assertIn('5120x3000', page['background_file'])
        for name in self.MAIN + self.SOURCES:
            self.assertTrue(_inside(ctl[name][1], [145, 10, 733, 581]), (name, ctl[name][1]))
        x, _, w, _ = ctl['RoomName'][1]
        self.assertAlmostEqual(x + w / 2, 145 + 733 / 2, delta=2)

    def test_a_button_meets_the_panels_touch_minimum(self):
        """The 835 shares the 1035's series and canvas but is denser: 9 mm is
        67 px on it. The 1220 is sparser - 44 px - and keeps the design's 64."""
        _, ctl, _ = self.probe('Home.dc.html', 'TLP835M')
        for name, (g, r, _) in ctl.items():
            if g['kind'] == 'button':
                self.assertGreaterEqual(min(r[2], r[3]), 67, (name, r))
        _, ctl, _ = self.probe('Home.dc.html', 'TLP1220MG')
        self.assertEqual(ctl['EndCall'][1][2:], [154, 64])

    def test_text_never_falls_under_the_floor(self):
        for panel, floor in (('TLP725T', 16), ('TLP525T', 18), ('TLP320M', 14)):
            for board in ('Home.dc.html', 'Help.dc.html'):
                _, ctl, _ = self.probe(board, panel)
                for name, (g, _, _) in ctl.items():
                    if g['kind'] in ('label', 'button', 'datetime') and g.get('size'):
                        self.assertGreaterEqual(g['size'], floor, (panel, board, name))

    def test_the_rail_stacks_down_on_a_725_and_across_on_a_320(self):
        _, ctl, _ = self.probe('Home.dc.html', 'TLP725T')
        rects = [ctl[n][1] for n in self.RAIL]
        for r in rects:
            self.assertTrue(_inside(r, [878, 0, 146, 600]), r)
        centres = {round(r[0] + r[2] / 2) for r in rects}
        self.assertLessEqual(max(centres) - min(centres), 1, rects)
        self.assertEqual([r[1] for r in rects], sorted(r[1] for r in rects))
        _, ctl, _ = self.probe('Home.dc.html', 'TLP320M')
        names = ('VolumeSlider Down', 'VolumeSlider', 'VolumeSlider Up', 'Mute', 'HelpBtn', 'RoomOff')
        rects = [ctl[n][1] for n in names]
        for r in rects:
            self.assertTrue(_inside(r, [0, 190, 320, 50]), r)
        self.assertEqual([r[0] for r in rects], sorted(r[0] for r in rects))
        self.assertEqual(ctl['VolumeSlider'][0]['orientation'], 'right')

    def test_a_slider_becomes_a_level_where_the_seed_has_no_slider(self):
        """The 525's and 320's seeds carry levels and no slider, and a slider
        cannot be cloned from them. Extron's own 520 does it this way."""
        _, ctl, _ = self.probe('Home.dc.html', 'TLP525T')
        self.assertEqual(ctl['VolumeSlider'][0]['kind'], 'level')
        for n in ('VolumeSlider Up', 'VolumeSlider Down'):
            self.assertEqual(ctl[n][0]['kind'], 'button')
            self.assertTrue(ctl[n][0]['derived'], n)
            self.assertGreaterEqual(min(ctl[n][1][2:]), 66, n)
        self.assertNotIn('slider', {g['kind'] for g, _, _ in ctl.values()})

    def test_the_320_home_reflows_into_rows(self):
        """Tier C: scaled by a quarter, 14 pt lines would overlap; the controls
        reflow instead, in rows in design order, touch targets 2 mm apart."""
        _, ctl, out = self.probe('Home.dc.html', 'TLP320M')
        self.assertEqual(ctl['Date'][1][1], ctl['Time'][1][1])
        ys = [ctl[n][1][1] for n in ('RoomName', 'CallState', 'Sources', 'Display', 'Date')]
        self.assertEqual(ys, sorted(ys))
        touch = [ctl[n][1] for n in self.MAIN if ctl[n][0]['kind'] == 'button']
        for a in touch:
            for b in touch:
                if a is b:
                    continue
                apart = max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]), b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]))
                self.assertGreaterEqual(apart, 9, (a, b))

    def test_the_320_home_fits(self):
        """The hub page holds what is not in a group; the sources are a page of
        their own, opened from the hub and left by Back."""
        _, ctl, out = self.probe('Home.dc.html', 'TLP320M')
        self.assertEqual(out['problems'], [])
        for name in self.MAIN + ('Sources',):
            self.assertTrue(_inside(ctl[name][1], [0, 0, 320, 190]), (name, ctl[name][1]))
        parts = [json.loads(p['gdl']) for p in out['parts']]
        self.assertEqual([p['name'] for p in parts], ['Huddle Home Sources'])
        for name in self.SOURCES + ('Sources Back',):
            self.assertTrue(_inside(ctl[name][1], [0, 0, 320, 240]), (name, ctl[name][1]))
        self.assertEqual(ctl['Sources'][0]['nav'], 'Huddle Home Sources')
        self.assertEqual(ctl['Sources Back'][0]['nav'], 'Huddle Home')

    def test_the_525_sources_are_a_popup_in_their_region(self):
        _, ctl, out = self.probe('Home.dc.html', 'TLP525T')
        self.assertEqual(out['problems'], [])
        parts = [json.loads(p['gdl']) for p in out['parts']]
        self.assertEqual([(p['kind'], p['name'], p['group']) for p in parts],
                         [('popup', 'Huddle Home Sources', 'Huddle Home Sources')])
        self.assertEqual(ctl['Sources Region'][0]['group'], 'Huddle Home Sources')
        self.assertEqual(ctl['Sources Region'][1][2:], parts[0]['size'])

    def test_one_extra_line_is_an_overflow(self):
        """A label one line on the 1035 that wraps to two on the 525. A label
        centres its text, so it overflows both ways and scrollHeight saw only
        half of it: an extra line went unnamed and would build clipped."""
        edit = ('width: 916px; height: 40px">No call in progress',
                'width: 300px; height: 60px">Plug in your laptop first')
        _, ctl, _ = self.probe('Home.dc.html', 'TLP1035T', edit=edit)
        self.assertFalse(ctl['CallState'][2], 'one line on the 1035')
        _, ctl, _ = self.probe('Home.dc.html', 'TLP525T', edit=edit)
        self.assertTrue(ctl['CallState'][2], 'two lines in a one-line box on the 525')

    def test_a_plain_container_scales_with_its_frame(self):
        """The runtime draws a plain div from its markup and ignores a style
        cloned onto it, so a flex row of buttons stayed at design size on the
        725 - and a label in it drew its type scaled down."""
        edit = ('<x-import component-from-global-scope="ExtronAfterburn.Label" name="CallState"',
                '<div style="position: absolute; left: 0px; top: 300px; width: 600px; height: 200px">'
                '<x-import component-from-global-scope="ExtronAfterburn.Label" name="InBox" type="body" '
                'style="position:absolute; left:0px; top:0px; width:330px; height:30px">Plug in your laptop</x-import>'
                '</div><x-import component-from-global-scope="ExtronAfterburn.Label" name="CallState"')
        _, ctl, _ = self.probe('Home.dc.html', 'TLP725T', edit=edit)
        g, r = ctl['InBox'][0], ctl['InBox'][1]
        k = 1024 / 1280
        self.assertLess(r[2], 330 * k + 2, r)
        self.assertGreaterEqual(r[3], 26, (r, g['size']))   # a 16 pt line on the 725

    def test_a_pages_own_children_are_measured_at_its_scale(self):
        """Children placed straight on a Page - a modal's - were measured at the
        canvas's own type: on the 320 a 38 pt title asked for a 65 px line and
        a modal that fits was refused."""
        edit = ('type="subheading" align="center"', 'type="title" align="center"')
        _, ctl, out = self.probe('Help.dc.html', 'TLP320M', edit=edit)
        self.assertEqual(out['problems'], [])
        self.assertLess(ctl['HelpTitle'][1][3], 40, ctl['HelpTitle'])

    def test_a_group_member_that_is_not_a_component_is_named_not_wiped(self):
        """A Group lays out components as cells. Anything else - a wrapper div,
        an sc-for - had its children replaced with nothing: three looped
        buttons vanished from every panel with no problem raised."""
        edit = ('<x-import component-from-global-scope="ExtronAfterburn.Button" name="RoomPC"',
                '<div><x-import component-from-global-scope="ExtronAfterburn.Button" name="RoomPC"')
        edit2 = ('Room PC</x-import>', 'Room PC</x-import></div>')
        with open(os.path.join(self.dir, 'Home.dc.html'), encoding='utf-8') as fh:
            src = fh.read()
        self.assertTrue(edit[0] in src and edit2[0] in src)
        p2 = os.path.join(self.dir, 'wrapped-Home.dc.html')
        with open(p2, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(*edit).replace(*edit2))
        for m in ('TLP1035T', 'TLP725T'):
            out = design.render(p2, design.find_chrome(), (1280, 800), panel=m)
            names = {json.loads(c['gdl']).get('name') for c in out['controls']}
            self.assertIn('RoomPC', names, m)
            self.assertTrue(any('Sources' in p and 'component' in p for p in out['problems']), (m, out['problems']))

    def test_percent_sizes_and_far_anchors_are_read_against_the_frame(self):
        """`width: 100%` read as 100 px, and a box held by left and right with
        no width had no rect at all and stayed at its design place, unscaled.
        Either way it must land where the same box in pixels does."""
        px = 'left: 0px; top: 130px; width: 916px; height: 40px">No call'
        for m in ('TLP725T', 'TLP320M'):
            _, plain, _ = self.probe('Home.dc.html', m)
            for alt in ('left: 0px; top: 130px; width: 100%; height: 40px">No call',
                        'left: 0px; right: 0px; top: 130px; height: 40px">No call',
                        'right: 0px; top: 130px; width: 916px; height: 40px">No call'):
                _, ctl, _ = self.probe('Home.dc.html', m, edit=(px, alt))
                for a, b in zip(ctl['CallState'][1], plain['CallState'][1]):
                    self.assertLessEqual(abs(a - b), 1, (m, alt, ctl['CallState'][1], plain['CallState'][1]))

    def test_what_does_not_fit_is_named(self):
        """Nothing is dropped: a main area that cannot hold its controls on a
        panel says so, with the panel and the room it needed."""
        extra = ('<x-import component-from-global-scope="ExtronAfterburn.Clock" name="Date"',
                 '<x-import component-from-global-scope="ExtronAfterburn.Label" name="Extra1" type="title" '
                 'style="position: absolute; left: 0px; top: 630px; width: 916px; height: 30px">More</x-import>\n'
                 '<x-import component-from-global-scope="ExtronAfterburn.Label" name="Extra2" type="title" '
                 'style="position: absolute; left: 0px; top: 662px; width: 916px; height: 30px">More</x-import>\n'
                 '<x-import component-from-global-scope="ExtronAfterburn.Clock" name="Date"')
        _, _, out = self.probe('Home.dc.html', 'TLP320M', edit=extra)
        self.assertTrue(any('main area' in p and 'TLP320M' in p for p in out['problems']), out['problems'])

    def test_the_modals_fit_every_panel(self):
        for panel in ('TLP725T', 'TLP525T', 'TLP320M'):
            for board in ('Help.dc.html', 'ConfirmRoomOff.dc.html'):
                page, ctl, out = self.probe(board, panel)
                self.assertEqual(page['size'], {'TLP725T': [1024, 600], 'TLP525T': [800, 480],
                                                'TLP320M': [320, 240]}[panel])
                self.assertEqual(out.get('problems', []), [], (panel, board))
                for name, (g, r, _) in ctl.items():
                    self.assertTrue(_inside(r, [0, 0] + page['size']), (panel, board, name, r))

    def test_a_preview_page_draws_at_its_panel(self):
        """In Claude Design nothing is injected: `preview` picks the panel."""
        page, ctl, _ = self.probe('Home.dc.html', edit=('start="true"', 'start="true" preview="TLP725T"'))
        self.assertEqual((page['panel'], page['size']), ('TLP725T', [1024, 600]))

    def test_a_panel_the_profile_lacks_is_named(self):
        """Afterburn has no 720 template, so no TLP720T row: a problem, never a
        guess at its layout."""
        _, _, out = self.probe('Home.dc.html', edit=('TLP320M"', 'TLP720T"'))
        self.assertTrue(any('TLP720T' in p for p in out.get('problems', [])), out.get('problems'))


GROUPS_CANVAS = os.path.join(HERE, 'data', 'design-groups')


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestGroupsInChrome(_Probe, unittest.TestCase):
    """A Group pages by tier: in place on a large panel, as popups in its own
    box on a mid-size one, as pages of their own on a small one - every
    control kept, with its name; what still cannot fit named."""

    CANVAS = GROUPS_CANVAS
    SOURCES = ['S%d' % i for i in range(1, 9)]

    def parts(self, out):
        return [json.loads(p['gdl']) for p in out['parts']]

    def test_eight_sources_fit_on_a_1035(self):
        _, ctl, out = self.probe('Groups.dc.html')
        self.assertEqual(out['parts'], [])
        rows = sorted({ctl[n][1][1] for n in self.SOURCES})
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(ctl[n][1][1] for n in self.SOURCES).count(rows[0]), 4)
        self.assertEqual(out['problems'], [])

    def test_on_a_725_they_page_in_place(self):
        page, ctl, out = self.probe('Groups.dc.html', 'TLP725T')
        parts = self.parts(out)
        sources = [p for p in parts if p.get('group') == 'Group Test Sources']
        self.assertGreaterEqual(len(sources), 2)
        self.assertTrue(all(p['kind'] == 'popup' for p in sources))
        self.assertEqual(sources[0]['name'], 'Group Test Sources')
        self.assertEqual(sources[1]['name'], 'Group Test Sources 2')
        # Every source on exactly one of its pages.
        at = {}
        for c in out['controls']:
            g = json.loads(c['gdl'])
            if g.get('name') in self.SOURCES:
                at.setdefault(g['name'], []).append(c.get('part'))
        self.assertEqual(sorted(at), sorted(self.SOURCES))
        self.assertTrue(all(len(v) == 1 and v[0] is not None for v in at.values()), at)
        # The region on the page, bound to the group.
        refs = [json.loads(c['gdl']) for c in out['controls'] if json.loads(c['gdl'])['kind'] == 'popup_ref']
        self.assertIn('Group Test Sources', [r['group'] for r in refs])
        # Each page has its own Previous and Next: the first only Next, the last
        # only Previous, each naming the page it shows.
        index = {p['name']: i for i, p in enumerate(parts)}
        first, second = index['Group Test Sources'], index['Group Test Sources 2']
        last = index[sources[-1]['name']]
        on = {}
        for c in out['controls']:
            g = json.loads(c['gdl'])
            on.setdefault(c.get('part'), {})[g.get('name')] = g
        self.assertEqual(on[first]['Sources Next']['nav'], 'Group Test Sources 2')
        self.assertNotIn('Sources Previous', on[first])
        self.assertEqual(on[second]['Sources Previous']['nav'], 'Group Test Sources')
        self.assertNotIn('Sources Next', on[last])
        self.assertTrue(on[first]['Sources Next']['derived'])
        self.assertEqual(out['problems'], [])

    def test_on_a_525_they_become_a_popup_even_when_they_fit(self):
        _, ctl, out = self.probe('Groups.dc.html', 'TLP525T')
        inputs = [p for p in self.parts(out) if p.get('group') == 'Group Test Inputs']
        self.assertEqual([p['name'] for p in inputs], ['Group Test Inputs'])
        self.assertNotIn('Inputs Next', ctl)
        for n in ('InA', 'InB', 'InC'):
            self.assertTrue(_inside(ctl[n][1], [0, 0] + inputs[0]['size']), (n, ctl[n][1]))

    def test_on_a_320_they_become_pages(self):
        _, ctl, out = self.probe('Groups.dc.html', 'TLP320M')
        opener = ctl['Sources'][0]
        self.assertEqual((opener['kind'], opener['nav'], opener['derived']), ('button', 'Group Test Sources', True))
        pages = [p for p in self.parts(out) if p['kind'] == 'page' and p['name'].startswith('Group Test Sources')]
        self.assertTrue(pages)
        self.assertEqual(pages[0]['size'], [320, 240])
        self.assertEqual(pages[0]['host'], 'Group Test')
        back = ctl['Sources Back'][0]
        self.assertEqual((back['nav'], back['derived']), ('Group Test', True))
        for n in self.SOURCES:
            self.assertTrue(_inside(ctl[n][1], [0, 0, 320, 240]), (n, ctl[n][1]))
        self.assertEqual(out['problems'], [])

    def test_a_group_that_cannot_fit_is_refused_by_name(self):
        _, _, out = self.probe('Tiny.dc.html', 'TLP525T')
        self.assertTrue(any('Tiny' in p and 'TLP525T' in p for p in out['problems']), out['problems'])

    def test_a_joined_group_butts_its_cells(self):
        """A segmented control: its segments touch, and each says which
        control it belongs to, so the spacing check lets them."""
        _, ctl, _ = self.probe('Groups.dc.html')
        r = [ctl[n][1] for n in ('M1', 'M2', 'M3')]
        self.assertEqual([r[0][0] + r[0][2], r[1][0] + r[1][2]], [r[1][0], r[2][0]])
        self.assertEqual({ctl[n][0].get('joined') for n in ('M1', 'M2', 'M3')}, {'Modes'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
