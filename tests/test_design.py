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

    def test_a_line_is_a_shape_where_the_seed_has_none(self):
        """Most of Mach's, Shockwave's and Turbulence's seeds have no PBLine
        to clone, and a designer's divider stopped Turbulence's build at the
        donor check. A design-system Line is level or upright and its box is
        the band it draws, so a filled shape of that box draws it exactly."""
        spec = {'pages': [{'name': 'Home', 'controls': [
            {'kind': 'line', 'name': 'Divider', 'rect': [100, 200, 600, 2], 'fill': '#FFFFFF',
             'thickness': 2, 'from': 'MiddleLeft', 'to': 'MiddleRight'}]}], 'popups': []}
        notes = design.lines_as_shapes(spec)
        # No border resource: on 2D Rectangle a 2 px band built fully
        # transparent (Turbulence 1035, verify_built).
        self.assertEqual(spec['pages'][0]['controls'][0],
                         {'kind': 'panel', 'name': 'Divider', 'rect': [100, 200, 600, 2],
                          'fill': '#FFFFFF', 'border': 'none'})
        self.assertEqual(len(notes), 1)
        self.assertIn('Divider', notes[0])

    def test_a_canvas_builds_its_lines_one_way_on_every_panel(self):
        """Mach's 1035 seed has no PBLine and its 525 one: decided panel by
        panel, an unnamed Line was a shape on the one and a line on the other,
        the unnamed controls numbered apart, and the ID map refused the canvas
        (review of #38). If any panel's seed has none, every panel's is a shape;
        an unnamed one is said to be a Line, not None."""
        def spec():
            return {'pages': [{'name': 'Help', 'controls': [
                {'kind': 'line', 'rect': [0, 0, 600, 2], 'fill': '#FFFFFF', 'thickness': 2}]}],
                'popups': []}
        specs = {'TLP1035T': spec(), 'TLP525T': spec()}
        notes = design.lines_everywhere(specs, lambda s: s is specs['TLP525T'])
        for m in specs:
            c = specs[m]['pages'][0]['controls'][0]
            self.assertEqual((c['kind'], 'name' in c), ('panel', False), m)
            self.assertEqual(notes[m], ["'Help': a Line, built as a filled shape - a panel's seed has "
                                        "no line to clone"], m)
        kept = {'TLP1035T': spec(), 'TLP525T': spec()}
        self.assertEqual(design.lines_everywhere(kept, lambda s: True), {})
        self.assertEqual(kept['TLP1035T']['pages'][0]['controls'][0]['kind'], 'line')

    def test_the_design_panel_alone_is_held_to_the_spec_check(self):
        """Translated for its design panel alone (a spec file), a canvas was
        never checked as a spec: a stroke its seed's border cannot draw passed
        translate, and verify_built refused it after the build. A button under
        the touch minimum is the spec check's own, whatever the seed."""
        _, problems, _ = translate({'Home.dc.html': out(HOME, ctl([0, 0, 40, 40], **BTN))})
        self.assertTrue(any('touch target' in p for p in problems), problems)

    def test_a_color_no_token_names_is_a_problem_not_a_crash(self):
        """The spec check now runs whatever else is wrong, and it cannot read a
        colour no token names: translate raised ValueError instead of naming it
        (review of #38)."""
        _, problems, _ = translate({'Home.dc.html': out(HOME, ctl([0, 0, 240, 64],
                                                                  **dict(BTN, fill='brand-blue')))})
        self.assertTrue(any("'brand-blue' is not an Afterburn token" in p for p in problems), problems)

    def test_a_stroke_its_seed_cannot_draw_is_named_at_translate(self):
        """Mach's 1035 seed defines 2D Rounded Rectangle with no thickness: a
        designer's Warming Up, an accent outline on Off's fill, built as Off."""
        if not seeds.usable('seeds/Mach 1035.gdl'):
            self.skipTest('seeds/Mach 1035.gdl is not here (git lfs pull)')
        pg = json.dumps({'kind': 'page', 'name': 'Home', 'template': 'Mach', 'scheme': 'default',
                         'background': 'page', 'start': True})
        btn = dict(BTN, border='rounded', states=[{'name': 'Off'},
                                                  {'name': 'Warming', 'stroke': 'accent'}])
        _, problems, _ = translate({'Home.dc.html': out(pg, ctl([100, 100, 240, 64], **btn))})
        self.assertTrue(any("'Warming'" in p and 'stroke is not drawn' in p for p in problems), problems)

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
        # A group's popups show in a page's region for the group; without one
        # the spec check, which translate now runs, says they never can.
        region = ctl([200, 100, 880, 525], kind='popup_ref', name='SourceRegion', group='Sources')
        spec, problems, _ = translate({
            'Home.dc.html': out(HOME, region),
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

    @staticmethod
    def label_at(rect, text_rect, name='Status', em=21.7, part=None, text='No call in progress'):
        """A label as the probe reports it: its box, its words' own box (the
        face's content area round each line) and their em on screen."""
        c = dict(ctl(rect, kind='label', name=name, text=text, color='text', size=16),
                 text_rect=text_rect, text_em=em)
        if part is not None:
            c['part'] = part
        return c

    @needs_panel_files
    def test_words_a_layout_runs_into_a_button_are_named(self):
        """Laid out for another panel, a label whose words reach a button they
        cleared as drawn is refused by name. Its box may overlap the button -
        a label's box is often bigger than its words - its words may not."""
        go = ctl([40, 120, 200, 64], **dict(BTN16, name='Go'))
        rendered = {'TLP1035T': {'Home.dc.html': self.home('TLP1035T', self.label_at([40, 40, 400, 60], [80, 57, 320, 26]), go)},
                    'TLP725T': {'Home.dc.html': self.home('TLP725T', self.label_at([40, 80, 400, 60], [80, 106, 320, 26]), go)}}
        specs, problems, _ = translate_panels(rendered)
        self.assertIsNone(specs)
        self.assertEqual(problems['TLP1035T'], [])
        self.assertTrue(any("'Home' Status" in p and "Go" in p for p in problems['TLP725T']), problems)

    @needs_panel_files
    def test_words_drawn_over_a_button_are_the_designers(self):
        """A label drawn over a button - a caption on a tile - stays as drawn."""
        go = ctl([40, 40, 200, 64], **dict(BTN16, name='Go'))
        rendered = {m: {'Home.dc.html': self.home(m, self.label_at([40, 40, 200, 64], [60, 59, 160, 26]), go)}
                    for m in PANELS}
        specs, problems, _ = translate_panels(rendered)
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})

    @needs_panel_files
    def test_words_a_layout_runs_into_other_words_are_named(self):
        """Two labels whose words meet on another panel, though not as drawn.
        A line's box keeps a quarter em above its tallest glyph, so two whose
        boxes share 4 px at a 22 px em do not touch, and are not named; 7 px
        do. At 28 pt on a 535 that quarter em is 10 px, and two labels' boxes
        5 px over each other left their words clear."""
        title = self.label_at([40, 40, 400, 40], [100, 47, 280, 26], name='Title')
        for top, named in ((69, False), (66, True)):
            with self.subTest(top=top):
                rendered = {'TLP1035T': {'Home.dc.html': self.home(
                                'TLP1035T', title, self.label_at([40, 90, 400, 40], [100, 97, 280, 26]))},
                            'TLP725T': {'Home.dc.html': self.home(
                                'TLP725T', title, self.label_at([40, top - 7, 400, 40], [100, top, 280, 26]))}}
                _, problems, _ = translate_panels(rendered)
                self.assertEqual(any("'Home' Title" in p and 'Status' in p for p in problems['TLP725T']), named,
                                 problems)

    @needs_panel_files
    def test_words_with_nothing_below_the_line_stop_at_it(self):
        """A label's box runs a quarter em below its baseline for descenders;
        words with none - 'Volume' - stop at the line. On the hubs Mach's
        Volume label's box met its level's Up 5 px deep, its word 6 px clear;
        'Volume up' would have met it."""
        up = ctl([700, 160, 104, 104], **dict(BTN16, name='VolumeSlider Up', text='+'))
        for text, named in (('Volume', False), ('Volume up', True)):
            with self.subTest(text=text):
                lbl = lambda r, t: self.label_at(r, t, name='VolumeLabel', em=38.5, text=text)
                rendered = {'TLP1035T': {'Home.dc.html': self.home(
                                'TLP1035T', lbl([700, 60, 157, 49], [730, 58, 97, 52.4]), up)},
                            'TLP725T': {'Home.dc.html': self.home(
                                'TLP725T', lbl([700, 113, 157, 49], [730, 111, 97, 52.4]), up)}}
                _, problems, _ = translate_panels(rendered)
                self.assertEqual(any("'Home' VolumeLabel" in p and 'Up' in p for p in problems['TLP725T']),
                                 named, problems)

    @needs_panel_files
    def test_an_unnamed_clocks_words_are_held_too(self):
        """A Clock need not be named, and one whose words ran into a button on
        another panel went unchecked: an unnamed control is held by its kind
        and its place among its kind."""
        go = ctl([40, 120, 200, 64], **dict(BTN16, name='Go'))

        def clock(r, t):
            return dict(ctl(r, kind='datetime', color='text', size=16, format='time'), text_rect=t, text_em=21.7)
        rendered = {'TLP1035T': {'Home.dc.html': self.home('TLP1035T', clock([40, 40, 400, 60], [80, 57, 320, 30]), go)},
                    'TLP725T': {'Home.dc.html': self.home('TLP725T', clock([40, 80, 400, 60], [80, 106, 320, 30]), go)}}
        _, problems, _ = translate_panels(rendered)
        self.assertTrue(any("'Home' datetime 1" in p and 'Go' in p for p in problems['TLP725T']), problems)

    @needs_panel_files
    def test_words_that_met_a_button_as_drawn_may_not_go_further(self):
        """A pair that met as drawn is the designer's - as deep as it was drawn.
        Words 3 px into a button as drawn and 20 px into it on another panel
        are named."""
        go = ctl([40, 120, 200, 64], **dict(BTN16, name='Go'))
        for top, named in ((95, False), (113, True)):
            with self.subTest(top=top):
                rendered = {'TLP1035T': {'Home.dc.html': self.home(
                                'TLP1035T', self.label_at([40, 80, 400, 60], [80, 92, 320, 30]), go)},
                            'TLP725T': {'Home.dc.html': self.home(
                                'TLP725T', self.label_at([40, 80, 400, 60], [80, top, 320, 30]), go)}}
                _, problems, _ = translate_panels(rendered)
                self.assertEqual(any("'Home' Status" in p and 'Go' in p for p in problems['TLP725T']), named,
                                 problems)

    def group_part(self, model, *controls):
        """A Home whose Group's cells are a popup in a region at 0,100."""
        pop = {'kind': 'popup', 'name': 'Home Sources', 'group': 'Home Sources', 'size': [600, 200]}
        return self.home(model, *controls, parts=[part(pop, [0, 100, 600, 200]), part(pop, [0, 100, 600, 200])])

    @needs_panel_files
    def test_words_a_layout_runs_into_a_cell_of_a_group_are_named(self):
        """A Group's cells are a popup shown over the page in its region, so a
        page's words that reach one are named - in the page's own coordinates:
        a cell is reported in its popup's. Laid out for the hubs, Mach's Share
        label ran 12 px into its sources' region."""
        go = dict(ctl([40, 20, 200, 64], **dict(BTN16, name='Go')), part=0)
        rendered = {'TLP1035T': {'Home.dc.html': self.home(
                        'TLP1035T', self.label_at([40, 40, 400, 60], [80, 57, 320, 26]),
                        ctl([40, 120, 200, 64], **dict(BTN16, name='Go')))},
                    'TLP725T': {'Home.dc.html': self.group_part(
                        'TLP725T', self.label_at([40, 80, 400, 60], [80, 106, 320, 26]), go)}}
        _, problems, _ = translate_panels(rendered)
        self.assertTrue(any("'Home' Status" in p and 'Go' in p for p in problems['TLP725T']), problems)

    @needs_panel_files
    def test_two_pages_of_a_group_never_meet(self):
        """A Group's popups show one at a time, so what is in one is never held
        against what is in another."""
        rendered = {'TLP1035T': {'Home.dc.html': self.home(
                        'TLP1035T', self.label_at([40, 0, 400, 40], [80, 7, 320, 26]),
                        ctl([40, 300, 200, 64], **dict(BTN16, name='Go')))},
                    'TLP725T': {'Home.dc.html': self.group_part(
                        'TLP725T', self.label_at([40, 30, 400, 40], [80, 37, 320, 26], part=0),
                        dict(ctl([40, 40, 200, 64], **dict(BTN16, name='Go')), part=1))}}
        _, problems, _ = translate_panels(rendered)
        self.assertFalse(any("'Home' Status" in p and 'Go' in p for p in problems['TLP725T']), problems)

    def test_a_panel_turned_from_its_models_canvas_is_that_model_at_that_canvas(self):
        """A canvas may list the 300M either way up: TLP300M-Landscape is the
        TLP300M at 480x320, on the seed made that way up."""
        pid, seed = 'TLP300M-Landscape', 'seeds/Afterburn 300M Landscape.gdl'
        art = ('2400x1600_bg1-default.png',
               'Afterburn/Backgrounds/2400x1600/TLP 300M Landscape/2400x1600_bg1-default.png')
        if not (seeds.usable(seed) and resolve_image(art[1])):
            self.skipTest("needs the Afterburn 300M Landscape seed and Extron's Afterburn art")
        o = out(page('Home', panel=pid, panels=[pid], tier='C', derived=True, size=[480, 320],
                     seed=seed, background_image=art[0], background_file=art[1], theme='default',
                     start=True), ctl([40, 40, 200, 80], **dict(BTN, size=16)))
        o['parts'], o['problems'] = [], []
        specs, problems, _ = translate_panels({pid: {'Home.dc.html': o}})
        self.assertEqual(problems, {pid: []})
        self.assertEqual((specs[pid]['model'], specs[pid]['size'], specs[pid]['_seed']),
                         ('TLP300M', [480, 320], seed))

    def test_a_turned_panel_with_no_seed_is_told_the_canvas_it_is(self):
        rendered = {'TLP300M-Landscape': {'Home.dc.html': self.home_turned(seed='')}}
        specs, problems, _ = translate_panels(rendered)
        self.assertIsNone(specs)
        got = problems['TLP300M-Landscape']
        self.assertTrue(any("-Model TLP300M " in p and "-Resolution '480x320'" in p for p in got), got)

    def home_turned(self, seed):
        o = out(page('Home', panel='TLP300M-Landscape', panels=['TLP300M-Landscape'], tier='C',
                     derived=True, size=[480, 320], seed=seed, theme='default', start=True),
                ctl([40, 40, 200, 80], **dict(BTN, size=16)))
        o['parts'], o['problems'] = [], []
        return o

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

    def _named(self, name):
        rendered = {'TLP1035T': {
            'Home.dc.html': self.home('TLP1035T', ctl([40, 40, 200, 64], **BTN16)),
            'Other.dc.html': dict(out(panel_page(name, 'TLP1035T'),
                                      ctl([40, 40, 200, 64], **dict(BTN16, name='Back'))),
                                  parts=[], problems=[])}}
        return Fake(['Home.dc.html', 'Other.dc.html']).translate_panels(rendered)

    @needs_panel_files
    def test_a_page_may_take_a_name_the_seed_drops(self):
        """The applier drops the seed's own pages and popups, so a board named
        like one - Help is a popup in the Afterburn seeds - is no clash."""
        specs, problems, _ = self._named('Help')
        self.assertEqual(problems, {'TLP1035T': []})
        self.assertIn('Help', [pg['name'] for pg in specs['TLP1035T']['pages']])

    @needs_panel_files
    def test_a_page_named_like_the_offline_page_is_refused(self):
        """The one the applier keeps: Build refuses a second Offline Page."""
        specs, problems, _ = self._named('Offline Page')
        self.assertIsNone(specs)
        self.assertTrue(any("'Offline Page'" in p and 'keeps' in p for p in problems['TLP1035T']),
                        problems)

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

    PART = {'kind': 'popup', 'name': 'Main Select Source Sources', 'group': 'X', 'size': [400, 200]}

    def _compare(self, built_panels):
        """The sign-off page for a one-board canvas, `built_panels` {panel:
        built file} its built folders, and compare()'s scores."""
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
        for m, seed in built_panels.items():
            os.makedirs(os.path.join(built, m))
            shutil.copy(seed, os.path.join(built, m, 'Huddle.gdl'))

        def fake_render(path, chrome, size, timeout=90, panel=None):
            o = out(panel_page('Main Select Source', panel if panel in SIZES else 'TLP1035T'))
            o['parts'] = ([{'gdl': json.dumps(self.PART), 'rect': [0, 0, 400, 200]}]
                          if panel == 'TLP725T' else [])
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
            return fh.read(), scores

    def test_a_section_per_panel_naming_each_part(self):
        page, scores = self._compare(self.seeds)
        self.assertEqual(page.count('<section class="panel">'), 2)
        self.assertIn('TLP725T', page)
        self.assertIn('Main Select Source Sources', page)
        self.assertTrue(scores)

    def test_a_turned_panels_section_is_headed_with_its_own_canvas(self):
        """A built folder is named for its panel, and TLP300M-Landscape is
        480x320 - which the model table, keyed by model, cannot say. A seed
        stands in for its build."""
        page, _ = self._compare({'TLP300M-Landscape': self.seeds['TLP1035T']})
        self.assertIn('TLP300M-Landscape &middot; 480x320</h2>', page)


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
            ('Mach', 'TLP725T', '725'), ('Mach', 'TLP525T', '525'), ('Mach', 'TLP320M', '320'),
            ('Mach', 'TLP720T', '720'), ('Mach', 'TLP535T', '535'), ('Mach', 'TLP1525TG', '1525'),
            ('Shockwave', 'TLP1035T', '1035'), ('Shockwave', 'TLP1535M', '1535'),
            ('Shockwave', 'TLP725T', '725'), ('Shockwave', 'TLP525T', '525'), ('Shockwave', 'TLP320M', '320'),
            ('Shockwave', 'TLP720T', '720'), ('Shockwave', 'TLP535T', '535'), ('Shockwave', 'TLP1525TG', '1525'),
            ('Turbulence', 'TLP1035T', '1035'), ('Turbulence', 'TLP725T', '725'),
            ('Turbulence', 'TLP525T', '525'), ('Turbulence', 'TLP320M', '320'),
            ('Turbulence', 'TLP720T', '720'), ('Turbulence', 'TLP1525TG', '1525')]

    def test_a_new_seed_is_named_as_the_ones_here_are(self):
        """'Afterburn 725.gdl', not 'Afterburn TLP725T.gdl': the file a seed is
        made as is the one a later seed of the same size is found beside."""
        from gdl import seeds
        for theme, model, size in self.MADE:
            self.assertTrue(os.path.isfile(os.path.join(HERE, '..', 'seeds', f'{theme} {size}.gdl')),
                            f'{theme} {size}.gdl is not in seeds/ - the table above has drifted')
            out = 'seeds\\' + f'{theme} {size}.gdl'
            self.assertIn(f"-Output '{out}'", seeds.command(theme, model, None), (theme, model))

    def test_the_landscape_300m_seed_is_named_for_its_way_up(self):
        """The seed here, 'Afterburn 300M Landscape.gdl', was named by hand;
        the 300M's other way up now names itself, and the wizard is told it."""
        from gdl import seeds
        self.assertTrue(os.path.isfile(os.path.join(HERE, '..', 'seeds', 'Afterburn 300M Landscape.gdl')))
        self.assertEqual(seeds.default_path('Afterburn', 'TLP300M', (480, 320)),
                         'seeds/Afterburn 300M Landscape.gdl')
        cmd = seeds.command('Afterburn', 'TLP300M', None, (480, 320))
        self.assertIn("-Output 'seeds\\Afterburn 300M Landscape.gdl'", cmd)
        self.assertIn("-Resolution '480x320'", cmd)

    def test_a_rotating_panels_default_way_up_keeps_its_name_and_command(self):
        from gdl import seeds
        self.assertEqual(seeds.default_path('Afterburn', 'TLP1035M', (1280, 800)), 'seeds/Afterburn 1035.gdl')
        self.assertNotIn('-Resolution', seeds.command('Afterburn', 'TLP1035M', None, (1280, 800)))
        self.assertEqual(seeds.default_path('Afterburn', 'TLP300M'), 'seeds/Afterburn 300M Portrait.gdl')

    def test_a_portrait_1035_seed_is_named_portrait(self):
        from gdl import seeds
        self.assertEqual(seeds.default_path('Mach', 'TLP1035M', (800, 1280)), 'seeds/Mach 1035 Portrait.gdl')
        self.assertIn("-Resolution '800x1280'", seeds.command('Mach', 'TLP1035M', None, (800, 1280)))

    def test_a_spec_finds_its_seed_by_family_model_and_canvas(self):
        """The order a seed is looked for in: the family's profile, which knows
        seeds named any way (the 835's '(Project1)'), then the name seeds/ gives
        a new one. A canvas turned from the profile's row is the name alone."""
        from gdl import seeds
        self.assertEqual(seeds.candidates('Afterburn', 'TLP835M'),
                         ['seeds/Afterburn 835 (Project1).gdl', 'seeds/Afterburn 835.gdl'])
        self.assertEqual(seeds.candidates('Mach', 'TLP1035T'), ['seeds/Mach 1035.gdl'])
        self.assertEqual(seeds.candidates('Afterburn', 'TLP300M', (480, 320)),
                         ['seeds/Afterburn 300M Landscape.gdl'])
        # The family as a person might type it.
        self.assertEqual(seeds.candidates('afterburn', 'TLP1035T'), ['seeds/Afterburn 1035.gdl'])

    def test_a_turned_panel_looks_first_for_its_own_rows_seed(self):
        """The profile lists the 300M's seed each way up under its own panel,
        whatever the seed is called; keyed by model, the turned one was never
        found there."""
        from unittest import mock
        real = designsys.models

        def models(p):
            out = real(p)
            if 'TLP300M-Landscape' in out:
                out['TLP300M-Landscape'] = dict(out['TLP300M-Landscape'], seed='seeds/Afterburn 300 L.gdl')
            return out
        with mock.patch.object(designsys, 'models', models):
            self.assertEqual(seeds.candidates('Afterburn', 'TLP300M', (480, 320)),
                             ['seeds/Afterburn 300 L.gdl', 'seeds/Afterburn 300M Landscape.gdl'])

    def test_the_seed_ci_has_is_picked(self):
        from gdl import seeds
        if not seeds.usable('seeds/Afterburn 1035.gdl'):
            self.skipTest('seeds/Afterburn 1035.gdl is not here (an LFS pull fetches it)')
        self.assertEqual(seeds.pick('Afterburn', 'TLP1035T'), 'seeds/Afterburn 1035.gdl')

    def _repo(self, pointers=(), real=()):
        """seeds.REPO at a folder with no seeds - or only Git LFS pointer files,
        or the `real` seeds named, linked from this checkout's - so a refusal
        does not depend on which seeds this checkout has (ROADMAP's *Claude
        Design as the front end: every panel* makes the missing ones)."""
        from unittest import mock
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, 'seeds'))
        for name in pointers:
            with open(os.path.join(d, 'seeds', name), 'wb') as fh:
                fh.write(b'version https://git-lfs.github.com/spec/v1\n'
                         b'oid sha256:' + b'0' * 64 + b'\nsize 1\n')
        for name in real:
            src, dst = seeds.path(f'seeds/{name}'), os.path.join(d, 'seeds', name)
            try:
                os.link(src, dst)
            except OSError:
                shutil.copyfile(src, dst)
        patch = mock.patch.object(seeds, 'REPO', d)
        patch.start()
        self.addCleanup(patch.stop)
        return d

    def _real(self, *names):
        for n in names:
            if not seeds.usable(n):
                self.skipTest(f'{n} is not here (an LFS pull fetches it)')

    def _templates(self):
        from gdl import templates
        if not templates.table():
            self.skipTest("Extron's template table is not here (vendor/README.md)")

    def test_no_seed_is_none(self):
        self._repo()
        self.assertIsNone(seeds.pick('Shockwave', 'TLP725T'))
        self.assertIsNone(seeds.pick('Nonesuch', 'TLP1035T'))

    def test_a_spec_that_names_no_family_is_told_to(self):
        seed, why = seeds.for_spec({'model': 'TLP1035T'})
        self.assertIsNone(seed)
        self.assertIn('"family"', why)

    def test_a_spec_with_no_seed_is_told_how_to_make_one(self):
        self._repo()
        seed, why = seeds.for_spec({'family': 'shockwave', 'model': 'TLP725T'})
        self.assertIsNone(seed)
        self.assertIn("New-GdlSeed.ps1 -PanelType 'TLP Pro 725T' -Model TLP725T -Theme 'Shockwave'", why)

    def test_a_seed_is_picked_for_what_it_is_not_what_it_is_called(self):
        """seeds/ names a seed for its size, so 'Afterburn 725.gdl' is a TLP725T
        and a TLP725M - the same size, another part number - is not built on
        it. The 1035T and 1035M share a part number, so they share the seed."""
        self._real('seeds/Afterburn 725.gdl', 'seeds/Afterburn 1535.gdl', 'seeds/Afterburn 1035.gdl')
        self.assertEqual(seeds.pick('Afterburn', 'TLP725T'), 'seeds/Afterburn 725.gdl')
        self.assertIsNone(seeds.pick('Afterburn', 'TLP725M'))
        self.assertIsNone(seeds.pick('Afterburn', 'TLP725C'))
        self.assertEqual(seeds.pick('Afterburn', 'TLP1535M'), 'seeds/Afterburn 1535.gdl')
        self.assertIsNone(seeds.pick('Afterburn', 'TLP1535T'))
        self.assertEqual(seeds.pick('Afterburn', 'TLP1035M'), 'seeds/Afterburn 1035.gdl')

    def test_a_seed_named_for_its_preset_is_picked_too(self):
        self._real('seeds/Afterburn ECP 16-9.gdl')
        self.assertEqual(seeds.pick('Afterburn', 'VTLPEcp'), 'seeds/Afterburn ECP 16-9.gdl')

    def test_a_sibling_form_is_told_what_the_seed_is_and_a_name_free_to_make(self):
        self._real('seeds/Afterburn 725.gdl')
        self._templates()
        seed, why = seeds.for_spec({'family': 'Afterburn', 'model': 'TLP725M'})
        self.assertIsNone(seed)
        why = why.replace(chr(92), '/')
        self.assertIn('seeds/Afterburn 725.gdl is a TLP725T', why)
        self.assertIn("-Model TLP725M -Theme 'Afterburn' -Output 'seeds/Afterburn TLP725M.gdl'", why)
        self.assertIn("-Output 'seeds/Afterburn TLP725M.gdl'",
                      seeds.command('Afterburn', 'TLP725M', None).replace(chr(92), '/'))

    def test_a_seed_left_a_pointer_is_one_to_pull_not_to_make(self):
        self._repo(pointers=('Afterburn 1035.gdl',))
        seed, why = seeds.for_spec({'family': 'Afterburn', 'model': 'TLP1035T'})
        self.assertIsNone(seed)
        self.assertIn('git lfs pull', why)
        self.assertNotIn('New-GdlSeed', why)

    def test_no_make_line_where_no_template_is_drawn(self):
        """The wizard offers a panel Blank alone where its theme draws no
        template for it either way up - Turbulence at 1920x1080 - so no themed
        seed can be made, and the way is a seed retargeted."""
        self._repo()
        self._templates()
        seed, why = seeds.for_spec({'family': 'Turbulence', 'model': 'TLP1535M'})
        self.assertIsNone(seed)
        self.assertNotIn('New-Gdl', why)
        self.assertIn('docs/editing.md', why)

    def test_a_panel_turned_where_no_template_is_drawn_is_turned_from_its_own_seed(self):
        """Afterburn draws the 1035M landscape only, and its wizard offers the
        portrait Blank: the portrait seed is the landscape one turned."""
        self._real('seeds/Afterburn 1035.gdl')
        self._templates()
        self._repo(real=('Afterburn 1035.gdl',))
        seed, why = seeds.for_spec({'family': 'Afterburn', 'model': 'TLP1035M', 'size': [800, 1280]})
        self.assertIsNone(seed)
        self.assertIn("New-GdlTurnedSeed.ps1 -From 'seeds/Afterburn 1035.gdl' -Model TLP1035M "
                      "-Resolution '800x1280' -Output 'seeds/Afterburn 1035 Portrait.gdl'",
                      why.replace(chr(92), '/'))
        self.assertNotIn('New-GdlSeed', why)

    def test_a_turned_panel_with_no_seed_either_way_up_is_told_both_lines(self):
        """Afterburn has no 535 seed: its own is made first, then turned."""
        self._repo()
        self._templates()
        line = seeds.command('Afterburn', 'TLP535M', None, (720, 1280)).replace(chr(92), '/')
        made = ("New-GdlSeed.ps1 -PanelType 'TLP Pro 535M' -Model TLP535M -Theme 'Afterburn' "
                "-Output 'seeds/Afterburn 535.gdl'")
        turned = ("New-GdlTurnedSeed.ps1 -From 'seeds/Afterburn 535.gdl' -Model TLP535M "
                  "-Resolution '720x1280' -Output 'seeds/Afterburn 535 Portrait.gdl'")
        self.assertIn(made, line)
        self.assertIn(turned, line)
        self.assertLess(line.index(made), line.index(turned))

    def test_machs_300m_landscape_is_turned_from_its_portrait_seed(self):
        """Mach draws its 300 portrait alone (docs/design-rules.md section 1),
        so its landscape seed is its portrait one turned."""
        self._real('seeds/Mach 300M Portrait.gdl')
        self._templates()
        self._repo(real=('Mach 300M Portrait.gdl',))
        line = seeds.command('Mach', 'TLP300M', None, (480, 320)).replace(chr(92), '/')
        self.assertIn("New-GdlTurnedSeed.ps1 -From 'seeds/Mach 300M Portrait.gdl' -Model TLP300M "
                      "-Resolution '480x320' -Output 'seeds/Mach 300M Landscape.gdl'", line)

    def test_afterburns_300m_is_made_by_the_wizard_either_way_up(self):
        self._repo()
        self._templates()
        line = seeds.command('Afterburn', 'TLP300M', None, (480, 320))
        self.assertIn("New-GdlSeed.ps1 -PanelType 'TLP Pro 300M'", line)
        self.assertIn("-Resolution '480x320'", line)
        self.assertNotIn('Turned', line)

    def test_a_canvas_the_model_does_not_run_at_is_said(self):
        seed, why = seeds.for_spec({'family': 'Afterburn', 'model': 'TLP1035T', 'size': [1024, 600]})
        self.assertIsNone(seed)
        self.assertIn('1280x800', why)
        self.assertNotIn('New-GdlSeed', why)

    def test_a_family_that_is_no_theme_is_said(self):
        for family in ('Nonesuch', 5, ['Afterburn']):
            seed, why = seeds.for_spec({'family': family, 'model': 'TLP1035T'})
            self.assertIsNone(seed)
            self.assertIn('Afterburn, Mach, Shockwave or Turbulence', why, family)
            self.assertNotIn('New-GdlSeed', why, family)

    def test_a_family_as_typed_with_a_space_is_the_family(self):
        self._real('seeds/Afterburn 1035.gdl')
        self.assertEqual(seeds.for_spec({'family': 'Afterburn ', 'model': 'TLP1035T'}),
                         ('seeds/Afterburn 1035.gdl', None))

    def test_a_soft_panel_is_given_no_wizard_line(self):
        self._repo()
        seed, why = seeds.for_spec({'family': 'Turbulence', 'model': 'VTLPEcp'})
        self.assertIsNone(seed)
        self.assertNotIn('New-GdlSeed', why)
        self.assertIn('-Donor', why)

    def test_the_command_lines_pick_it(self):
        """`gdl.spec donors <spec> --auto` checks the seed it picks, and
        `gdl.seeds pick <spec>` prints it for New-GdlPanel.ps1 to build on."""
        import contextlib
        import io
        import json as _json
        from gdl import seeds
        from gdl import spec as gdlspec
        if not seeds.usable('seeds/Afterburn 1035.gdl'):
            self.skipTest('seeds/Afterburn 1035.gdl is not here (an LFS pull fetches it)')
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        f = os.path.join(d, 'spec.json')
        with open(f, 'w', encoding='utf-8') as fh:
            _json.dump({'name': 'T', 'family': 'Afterburn', 'model': 'TLP1035T', 'size': [1280, 800],
                        'theme': {'text': '#FFFFFF', 'font': 'Open Sans'},
                        'pages': [{'name': 'P', 'number': 1000, 'controls': [
                            {'kind': 'label', 'rect': [0, 0, 400, 80], 'text': 'Hello'}]}]}, fh)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(seeds.main(['seeds', 'pick', f]), 0)
        self.assertEqual(out.getvalue().strip(), 'seeds/Afterburn 1035.gdl')
        for args in (['spec', 'donors', f, '--auto'], ['spec', 'donors', f]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = gdlspec.main(args)
            self.assertIn('donor: seeds/Afterburn 1035.gdl', out.getvalue(), args)
            self.assertEqual(rc, 0, out.getvalue())

    def test_a_themes_small_seeds_are_made_under_their_size(self):
        """The line that makes a theme's 525 and 320 seed names each as seeds/
        names a seed (TestSeeds.MADE has the ones made)."""
        from gdl import seeds
        for theme in ('Mach', 'Shockwave', 'Turbulence'):
            for model, size in (('TLP525T', '525'), ('TLP320M', '320')):
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

    def test_a_level_on_a_page_that_lists_no_panels_is_named_too(self):
        """Without `panels` a canvas builds the system's own panel, whose seed
        builds no level."""
        path = os.path.join(self.dir, 'Home.dc.html')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(src.replace('ExtronAfterburn.Slider" name="VolumeSlider"',
                                 'ExtronAfterburn.Level" name="VolumeSlider"'))
        out = design.render(path, design.find_chrome(), (1280, 800))
        model = designsys.load('afterburn')['model']
        self.assertIn(f"VolumeSlider is a Level, which the {model}'s seed cannot build - a Slider can",
                      out['problems'])

    def test_a_level_outside_a_page_is_not_named(self):
        """The design system's own card for Level draws one on no Page, and
        nothing there builds."""
        with open(os.path.join(self.dir, 'Help.dc.html'), encoding='utf-8') as fh:
            src = fh.read()
        card = (src[:src.index('<div style="width: 1280px')]
                + '<div style="width: 400px; height: 300px; position: relative">'
                  '<x-import component-from-global-scope="ExtronAfterburn.Level" name="Meter" '
                  'style="position: absolute; left: 0px; top: 0px; width: 40px; height: 240px"></x-import>'
                  '</div>\n</x-dc>\n</body>\n</html>\n')
        path = os.path.join(self.dir, 'Card.dc.html')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(card)
        out = design.render(path, design.find_chrome(), (1280, 800))
        self.assertEqual(out['pages'], 0)
        self.assertEqual(out['problems'], [])

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

    def _translate_panels(self, template, data, edit=None):
        """As _translate, one spec per panel the canvas lists. `edit`:
        (board, old, new), applied to that board first."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copytree(os.path.join(HERE, 'data', data), d, dirs_exist_ok=True)
        if edit:
            path = os.path.join(d, edit[0])
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            self.assertEqual(src.count(edit[1]), 1)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(src.replace(edit[1], edit[2]))
        shutil.copy(RUNTIME, os.path.join(d, 'support.js'))
        p = designsys.load(template)
        comps = os.path.join(d, 'ds', p['namespace'].lower(), 'components')
        os.makedirs(comps)
        with open(os.path.join(comps, 'bundle.js'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.bundle(p, art=False))
        with open(os.path.join(comps, 'bundle.css'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.BUNDLE_CSS)
        return design.Canvas(d).translate_panels()

    def test_a_canvas_hears_its_layout_and_its_spec_problems_at_once(self):
        """With a layout problem on any panel the spec check never ran, so a
        designer who revised a canvas for what it was told met a new list in
        the next read - the gaps between Shockwave's source tabs, on the very
        panel it was drawn on. Both come at once."""
        main = '<x-import component-from-global-scope="ExtronAfterburn.MainArea">'
        extra = ''.join(
            f'<x-import component-from-global-scope="ExtronAfterburn.Button" name="{n}" variant="ghost" '
            f'does="Tests." style="position: absolute; left: {x}px; top: 600px; width: 60px; height: 60px">'
            f'{n}</x-import>' for n, x in (('GapA', 20), ('GapB', 80)))
        extra += ('<x-import component-from-global-scope="ExtronAfterburn.Label" name="Overflowing" '
                  'style="position: absolute; left: 20px; top: 470px; width: 60px; height: 30px">'
                  'These words cannot fit</x-import>')
        specs, problems, _ = self._translate_panels('afterburn', 'design-panels',
                                                    edit=('Home.dc.html', main, main + extra))
        self.assertIsNone(specs)
        drawn = problems['TLP1035T']
        self.assertTrue(any('Overflowing' in p and 'does not fit' in p for p in drawn), drawn)
        # The spec check's word for two touch targets that meet (`page N A / B`).
        self.assertTrue(any('GapA / GapB' in p for p in drawn), drawn)

    def test_each_themes_huddle_translates_for_every_panel_but_the_320(self):
        """Mach's, Shockwave's and Turbulence's huddles, drawn on the 1035 and
        listing the 725, the 1525, the 720 and their hubs - the 525 in all three,
        the 535 in Mach and Shockwave - translate clean for each: every panel on
        its theme's own seed for it, with its series' background, their tables,
        art and bars end to end in the translator."""
        art = {'mach': 'mach-bg-02.png', 'shockwave': '1024x600_bkgd.png', 'turbulence': 'bkgd_pc.png'}
        for theme in ('mach', 'shockwave', 'turbulence'):
            sizes = {'TLP1035T': ([1280, 800], '1035'), 'TLP725T': ([1024, 600], '725'),
                     'TLP1525TG': ([1366, 768], '1525'), 'TLP720T': ([800, 480], '720'),
                     'TLP525T': ([800, 480], '525')}
            if theme != 'turbulence':
                sizes['TLP535T'] = ([1280, 720], '535')
            with self.subTest(theme=theme):
                # The translator refuses a panel whose seed is not here and an
                # icon the kit lacks, so without them this skips.
                if not all(seeds.usable(f'seeds/{theme.title()} {s}.gdl') for _, s in sizes.values()):
                    self.skipTest(f'the {theme} seeds are not here (git lfs pull)')
                if not designsys.kit_root(designsys.load(theme)):
                    self.skipTest(f"Extron's {theme} kit is not here")
                specs, problems, _ = self._translate_panels(theme, f'design-panels-{theme}')
                self.assertEqual({m: p for m, p in problems.items() if p}, {})
                self.assertEqual(sorted(specs), sorted(sizes))
                for m, (size, s) in sizes.items():
                    self.assertEqual((specs[m]['size'], specs[m]['_seed']), (size, f'seeds/{theme.title()} {s}.gdl'))
                small = specs['TLP725T']
                self.assertEqual(small['pages'][0]['background_image'], art[theme])
                self.assertIn(art[theme], small['images'])
                captions = {c['name']: c.get('text') for c in small['pages'][0]['controls']}
                if theme == 'mach':
                    # The 725's 113 px cells keep two of the three breaks the
                    # 1035's 150 px tiles take to reach their captions.
                    self.assertEqual(captions['Laptop'], '\r\n\r\nLaptop')
                    big = {c['name']: c.get('text') for c in specs['TLP1035T']['pages'][0]['controls']}
                    self.assertEqual(big['Laptop'], '\r\n\r\n\r\nLaptop')

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


class TestACaptionBelowItsIcon(unittest.TestCase):
    """The template's own tiles reach a caption below the icon with leading
    line breaks. On a panel smaller than the one drawn, the tile shrinks and
    the caption stops at the panel's type floor: three breaks put the Mach
    725's 106 px source tiles' 16 pt captions past their bottom edge, and
    GUI Designer clipped them. A caption keeps as many as fit."""

    def _fit(self, text, size, h, states=None):
        c = {'kind': 'button', 'text': text, 'size': size, 'rect': [0, 0, h, h]}
        if states:
            c['states'] = states
        design._fit_breaks(c, 1.375, 'Open Sans')
        return c

    def test_the_breaks_that_fit_are_kept(self):
        self.assertEqual(self._fit('\r\n\r\n\r\nLaptop', 14, 150)['text'], '\r\n\r\n\r\nLaptop')
        self.assertEqual(self._fit('\r\n\r\n\r\nLaptop', 16, 106)['text'], '\r\n\r\nLaptop')

    def test_a_line_is_as_the_panel_lays_it_out(self):
        """GUI Designer lays a caption line out at the face's usWinAscent +
        usWinDescent - 29.96 px for Open Sans at 16 pt, where the canvas's line
        box is 27 - so four lines need 120 px, not 108: in a 113 px tile the
        third break goes too."""
        self.assertEqual(self._fit('\r\n\r\n\r\nLaptop', 16, 113)['text'], '\r\n\r\nLaptop')

    def test_a_button_with_no_caption_is_left_without_one(self):
        c = {'kind': 'button', 'size': 16, 'rect': [0, 0, 100, 100]}
        design._fit_breaks(c, 1.375, 'Open Sans')
        self.assertNotIn('text', c)

    def test_a_caption_of_two_lines_counts_both(self):
        self.assertEqual(self._fit('\r\n\r\n\r\nRoom\r\nPC', 16, 106)['text'], '\r\nRoom\r\nPC')

    def test_a_caption_with_no_breaks_or_no_room_is_left(self):
        self.assertEqual(self._fit('Laptop', 16, 20)['text'], 'Laptop')
        self.assertEqual(self._fit('\r\n\r\nLaptop', 16, 20)['text'], 'Laptop')

    def test_a_states_own_caption_too(self):
        c = self._fit('\r\n\r\n\r\nLaptop', 16, 106, states=[{'name': 'On', 'text': '\r\n\r\n\r\nLive'}, 'Off'])
        self.assertEqual(c['states'], [{'name': 'On', 'text': '\r\n\r\nLive'}, 'Off'])


PANELS_CANVAS = os.path.join(HERE, 'data', 'design-panels')


def _inside(rect, box, slack=1):
    x, y, w, h = rect
    bx, by, bw, bh = box
    return x >= bx - slack and y >= by - slack and x + w <= bx + bw + slack and y + h <= by + bh + slack


def _level_beside(test, theme, panel, probe):
    """Up and Down stand beside the level a slider becomes, one at each of its
    ends - Extron's own 520 and 535 stand theirs beside it, the level the
    length of the column (Mach 525: a 14 x 309 level beside 66 px Up, Down and
    Mute) - so the level keeps the slider's whole length. Between Up and Down,
    the hubs' levels came out 15 to 42 px long."""
    p = designsys.load(theme)
    if not designsys.kit_root(p):
        test.skipTest(f"Extron's {theme} kit is not here")
    m = designsys.models(p)[panel]
    t, g = m['touch'], m['gap']
    page, ctl, out = probe('Home.dc.html', panel)
    test.assertEqual(out['problems'], [])
    test.assertEqual(ctl['VolumeSlider'][0]['kind'], 'level')
    lv, up, dn = (ctl[n][1] for n in ('VolumeSlider', 'VolumeSlider Up', 'VolumeSlider Down'))
    test.assertGreaterEqual(lv[3], 2 * t + g, lv)
    test.assertAlmostEqual(up[1], lv[1], delta=1)
    test.assertAlmostEqual(dn[1] + dn[3], lv[1] + lv[3], delta=1)
    for b in (up, dn):
        test.assertGreaterEqual(min(b[2:]), t, b)
        test.assertEqual(b[0], up[0])
        test.assertTrue(b[0] >= lv[0] + lv[2] + 2 or b[0] + b[2] + 2 <= lv[0], (lv, b))
    # In the menu bar, with as much room each side of it as between the level
    # and its buttons: none of them against the screen's edge.
    rail = m['rail']
    left, right = min(lv[0], up[0]), max(lv[0] + lv[2], up[0] + up[2])
    inner = up[0] - (lv[0] + lv[2]) if up[0] > lv[0] else lv[0] - (up[0] + up[2])
    test.assertGreaterEqual(left - rail[0], 2, (rail, lv, up))
    test.assertAlmostEqual(left - rail[0], inner, delta=1)
    test.assertAlmostEqual(rail[0] + rail[2] - right, inner, delta=1)
    # In the look of the Mute below the slider where that look can draw them -
    # one drawn without the kit, or with the theme's volume icons at its kit
    # size - as Extron draws its volume Up, Down and Mute alike; else in the
    # theme's default button. In the default look, Mach's showed as two faint
    # tiles on its photo beside a solid Mute.
    mute = ctl['Mute'][0]['variant']
    V, steps = p['buttons'][mute], p['defaults']['level'].get('steps')
    want = mute if not V.get('kit') or steps else p['defaults']['button']['variant']
    for n in ('VolumeSlider Up', 'VolumeSlider Down'):
        test.assertEqual(ctl[n][0]['variant'], want, n)
        test.assertIsNone(ctl[n][0].get('missing_icon'), n)
    return ctl


class _Probe:
    """A checked-in canvas with the current bundle of its theme, each board
    laid out once per panel and the probe's output kept."""

    CANVAS = None
    THEME = 'afterburn'

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        shutil.copytree(cls.CANVAS, cls.dir, dirs_exist_ok=True)
        shutil.copy(RUNTIME, os.path.join(cls.dir, 'support.js'))
        p = designsys.load(cls.THEME)
        comps = os.path.join(cls.dir, 'ds', p['namespace'].lower(), 'components')
        os.makedirs(comps)
        with open(os.path.join(comps, 'bundle.js'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.bundle(p, art=False))
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
class TestAPagesOwnBars(_Probe, unittest.TestCase):
    """Mach draws its header and footer bars, the footer's end buttons and its
    modals' window as the page's own controls. On a panel other than the one
    drawn they keep to that panel's own bands - the 725's header 60 deep
    across its 1024, its footer 57, its end caps 123 wide, its series'
    measured regions - where one scale for the whole page stopped a bar 32 px
    short of each side of a screen of another shape."""

    CANVAS = os.path.join(HERE, 'data', 'design-panels-mach')
    THEME = 'mach'
    MAIN = (123, 60, 778, 483)

    def test_the_design_panel_is_drawn_as_designed(self):
        page, ctl, out = self.probe('Home.dc.html')
        self.assertEqual((page['panel'], page['size']), ('TLP1035T', [1280, 800]))
        self.assertEqual(ctl['Header'][1], [0, 0, 1280, 64])
        self.assertEqual(ctl['Footer'][1], [0, 745, 1280, 55])
        self.assertEqual(ctl['RoomOff'][1], [1140, 745, 140, 55])
        self.assertEqual(out.get('problems', []), [])

    def test_a_labels_words_are_boxed_on_their_own(self):
        """The probe boxes a label's words apart from the label, which the
        translator holds against the buttons around it (gdl.design
        _collisions): the box is often far bigger than its words."""
        _, _, out = self.probe('Home.dc.html')
        raw = {json.loads(c['gdl']).get('name'): c for c in out['controls']}
        box, words = raw['Status']['rect'], raw['Status'].get('text_rect')
        self.assertIsNotNone(words)
        self.assertTrue(_inside(words, box), (words, box))
        self.assertLess(words[2], box[2] / 2)
        # One line: the face's ascent and descent, a little over the 1.2 em
        # line it sits on (1.36 em for Open Sans).
        self.assertTrue(1.2 <= words[3] / raw['Status']['text_em'] <= 1.45, (words, raw['Status']['text_em']))
        self.assertNotIn('text_rect', raw['EndCall'])

    def test_a_bar_spans_the_panel_at_its_own_depth(self):
        page, ctl, out = self.probe('Home.dc.html', 'TLP725T')
        self.assertEqual((page['panel'], page['size']), ('TLP725T', [1024, 600]))
        self.assertEqual(ctl['Header'][1], [0, 0, 1024, 60])
        self.assertEqual(ctl['Footer'][1], [0, 543, 1024, 57])
        # The title in it keeps its shape, centred as it was.
        x, _, w, h = ctl['Title'][1]
        self.assertAlmostEqual(x + w / 2, 512, delta=1)
        self.assertEqual(h, 60)

    def test_an_end_cap_fills_its_band_and_stays_on_the_page(self):
        """Across its band; and the 725's 57 px footer is less than its touch
        minimum, so the cap grows to that - up from the bottom edge, since
        Build moves a control that crosses its page's."""
        page, ctl, out = self.probe('Home.dc.html', 'TLP725T')
        x, y, w, h = ctl['RoomOff'][1]
        self.assertEqual((x, w), (901, 123))
        self.assertEqual((y + h, h), (600, designsys.models(designsys.load('mach'))['TLP725T']['touch']))

    def test_a_modals_window_spans_the_band_between_the_bars(self):
        page, ctl, out = self.probe('ConfirmRoomOff.dc.html', 'TLP725T')
        self.assertEqual(ctl['Window'][1], [0, 60, 1024, 483])

    def test_what_was_in_main_is_in_main(self):
        page, ctl, out = self.probe('Home.dc.html', 'TLP725T')
        for name in ('Status', 'Laptop', 'Wireless', 'RoomPC', 'Display', 'EndCall'):
            self.assertTrue(_inside(ctl[name][1], self.MAIN), (name, ctl[name][1]))

    def test_an_edge_within_4_px_of_a_cut_is_on_it(self):
        """A header 3 px short of main's top is on that edge, and spans to the
        725's; 6 px short, it keeps its own depth at its band's scale."""
        line = 'name="Header" style="position: absolute; left: 0px; top: 0px; width: 1280px; height: 64px"'
        for depth, want in ((61, [0, 0, 1024, 60]), (58, [0, 0, 1024, 54])):
            with self.subTest(depth=depth):
                _, ctl, _ = self.probe('Home.dc.html', 'TLP725T', edit=(line, line.replace('64px', f'{depth}px')))
                self.assertEqual(ctl['Header'][1], want)

    def test_a_hub_gives_the_bars_bands_of_their_own(self):
        """The 535 is a hub: its main region runs from its top to its bottom
        and from its left edge to its menu bar. The header, the footer and the
        left column get bands of their own carved from main, at the page's
        scale (0.9) - as Extron's hub templates keep a title strip at the top
        of main - or the touch minimum deep where the band holds a button, as
        the footer's end caps are; the right column goes to the menu bar."""
        _, ctl, out = self.probe('Home.dc.html', 'TLP535T')
        self.assertEqual(out['problems'], [])
        k, touch = 0.9, designsys.models(designsys.load('mach'))['TLP535T']['touch']
        x, y, w, h = ctl['Header'][1]
        self.assertEqual((x, y, w), (0, 0, 1280))
        self.assertAlmostEqual(h, 64 * k, delta=1)
        # Whole pixels, ending on the canvas's edge: a cut at 720 - 49.5 once
        # rounded the footer's top and height apart and ended it at 721.
        x, y, w, h = ctl['Footer'][1]
        self.assertEqual((x, w, y + h, h), (0, 1280, 720, touch))
        for name, (_, r, _) in ctl.items():
            self.assertTrue(_inside(r, [0, 0, 1280, 720]), (name, r))
        self.assertGreaterEqual(ctl['VolumeLabel'][1][0], 1123 - 1)
        # The sources are a popup group on a hub, in their region.
        for name in ('Status', 'Sources Region', 'Display', 'EndCall'):
            r = ctl[name][1]
            self.assertTrue(_inside(r, [126, 58, 1123 - 126, 720 - touch - 58]), (name, r))

    def test_a_hubs_left_column_is_carved_at_the_pages_scale(self):
        """A control in the column left of main keeps a band of its own on the
        535, at the page's scale (0.9): 126 of the 1035's 140."""
        anchor = '<x-import component-from-global-scope="ExtronMach.Panel" name="Footer"'
        label = ('<x-import component-from-global-scope="ExtronMach.Label" name="Lights" type="body" align="center" '
                 'style="position: absolute; left: 0px; top: 130px; width: 140px; height: 37px">Lights</x-import>\n')
        _, ctl, out = self.probe('Home.dc.html', 'TLP535T', edit=(anchor, label + anchor))
        self.assertEqual(out['problems'], [])
        x, _, w, _ = ctl['Lights'][1]
        self.assertEqual(x, 0)
        self.assertAlmostEqual(w, 140 * 0.9, delta=1)

    def test_a_hubs_level_runs_beside_its_up_and_down(self):
        for panel in ('TLP525T', 'TLP535T'):
            with self.subTest(panel=panel):
                _level_beside(self, 'mach', panel, self.probe)

    def test_on_a_hub_main_area_and_rail_keep_clear_of_the_bars(self):
        """What a MainArea and a Rail lay out on a hub goes in what the bars'
        bands leave of main and of the menu bar, not under the bars."""
        with open(os.path.join(self.dir, 'Help.dc.html'), encoding='utf-8') as fh:
            src = fh.read()
        mach = 'component-from-global-scope="ExtronMach.'
        board = (src[:src.index('<div style="width: 1280px')]
                 + '<div style="width: 1280px; height: 800px; position: relative">\n'
                 f'<x-import {mach}Page" name="Hub Home" panels="TLP1035T TLP725T" theme="sunset" '
                 'style="position: absolute; left: 0px; top: 0px; width: 1280px; height: 800px">\n'
                 f'<x-import {mach}Panel" name="Header" style="position: absolute; left: 0px; top: 0px; '
                 'width: 1280px; height: 64px"></x-import>\n'
                 f'<x-import {mach}Panel" name="Footer" style="position: absolute; left: 0px; top: 745px; '
                 'width: 1280px; height: 55px"></x-import>\n'
                 f'<x-import {mach}Button" name="RoomOff" style="position: absolute; left: 1140px; top: 745px; '
                 'width: 140px; height: 55px">Off</x-import>\n'
                 f'<x-import {mach}MainArea">\n'
                 f'<x-import {mach}Label" name="MainTitle" style="position: absolute; left: 0px; top: 0px; '
                 'width: 1000px; height: 60px">Room</x-import>\n'
                 f'<x-import {mach}Button" name="LowAction" style="position: absolute; left: 400px; top: 621px; '
                 'width: 200px; height: 60px">Go</x-import>\n'
                 '</x-import>\n'
                 f'<x-import {mach}Rail">\n'
                 f'<x-import {mach}Label" name="VolumeLabel">Volume</x-import>\n'
                 f'<x-import {mach}Slider" name="Volume"></x-import>\n'
                 f'<x-import {mach}Button" name="Mute">Mute</x-import>\n'
                 '</x-import>\n</x-import>\n</div>\n</x-dc>\n</body>\n</html>\n')
        with open(os.path.join(self.dir, 'Hub.dc.html'), 'w', encoding='utf-8') as fh:
            fh.write(board)
        _, ctl, out = self.probe('Hub.dc.html', 'TLP535T')
        top = ctl['Header'][1][1] + ctl['Header'][1][3]
        foot = ctl['Footer'][1][1]
        for name in ('MainTitle', 'LowAction', 'VolumeLabel', 'Volume', 'Mute'):
            r = ctl[name][1]
            self.assertTrue(r[1] >= top and r[1] + r[3] <= foot, (name, r, top, foot))
        mute, off = ctl['Mute'][1], ctl['RoomOff'][1]
        self.assertTrue(mute[1] + mute[3] <= off[1] or mute[0] + mute[2] <= off[0], (mute, off))

    def test_a_popup_scales_as_one(self):
        """A popup shows in a region of main, so what is in it scales as one,
        with no bands of its own."""
        with open(os.path.join(self.dir, 'Help.dc.html'), encoding='utf-8') as fh:
            src = fh.read()
        board = (src[:src.index('<div style="width: 1280px')]
                 + '<div style="width: 995px; height: 549px; position: relative">\n'
                   '<x-import component-from-global-scope="ExtronMach.Page" name="Source Controls" '
                   'panels="TLP1035T TLP725T" kind="popup" theme="sunset" '
                   'style="position: absolute; left: 0px; top: 0px; width: 995px; height: 549px">\n'
                   '<x-import component-from-global-scope="ExtronMach.Panel" name="Back" '
                   'style="position: absolute; left: 0px; top: 0px; width: 995px; height: 549px"></x-import>\n'
                   '<x-import component-from-global-scope="ExtronMach.Panel" name="Inner" '
                   'style="position: absolute; left: 100px; top: 100px; width: 400px; height: 200px"></x-import>\n'
                   '</x-import>\n</div>\n</x-dc>\n</body>\n</html>\n')
        with open(os.path.join(self.dir, 'Popup.dc.html'), 'w', encoding='utf-8') as fh:
            fh.write(board)
        page, ctl, out = self.probe('Popup.dc.html', 'TLP725T')
        w, h = page['size']
        k = min(w / 995, h / 549)
        self.assertEqual(ctl['Back'][1], [0, 0, round(995 * k), round(549 * k)])
        self.assertEqual(ctl['Inner'][1], [round(100 * k), round(100 * k), round(400 * k), round(200 * k)])


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestShockwavesBars(_Probe, unittest.TestCase):
    """Shockwave's header and footer capsule are the page's own controls: on
    the 725 the header spans at its series' depth and the capsule stays under
    the well, set in by the well's own bands."""

    CANVAS = os.path.join(HERE, 'data', 'design-panels-shockwave')
    THEME = 'shockwave'

    def test_the_design_panel_is_drawn_as_designed(self):
        """Listing panels moves nothing on the panel drawn, though the capsule
        sits 2 px inside the well's edges there."""
        _, ctl, out = self.probe('Home.dc.html')
        self.assertEqual(ctl['Footer'][1], [166, 718, 928, 62])
        self.assertEqual(ctl['Header'][1], [0, 0, 1280, 91])

    def test_the_725s_header_and_capsule(self):
        _, ctl, out = self.probe('Home.dc.html', 'TLP725T')
        self.assertEqual(ctl['Header'][1], [0, 0, 1024, 68])
        self.assertEqual(ctl['Footer'][1], [133, 538, 739, 47])

    def test_a_hub_carves_the_header_from_main(self):
        """The 525 is a hub: the header gets a band of its own at the top of
        main, at the page's scale (0.6)."""
        _, ctl, out = self.probe('Home.dc.html', 'TLP525T')
        self.assertEqual(out['problems'], [])
        x, y, w, h = ctl['Header'][1]
        self.assertEqual((x, y, w), (0, 0, 800))
        self.assertAlmostEqual(h, 91 * 0.6, delta=1)

    def test_a_hubs_level_runs_beside_its_up_and_down(self):
        for panel in ('TLP525T', 'TLP535T'):
            with self.subTest(panel=panel):
                _level_beside(self, 'shockwave', panel, self.probe)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTurbulencesBars(_Probe, unittest.TestCase):
    """Turbulence's header, footer and side rails are the page's own controls,
    the header ending 4 px above main's top as the template's does."""

    CANVAS = os.path.join(HERE, 'data', 'design-panels-turbulence')
    THEME = 'turbulence'

    def test_the_design_panel_is_drawn_as_designed(self):
        _, ctl, out = self.probe('Home.dc.html')
        self.assertEqual(ctl['Header'][1], [0, 0, 1280, 133])
        self.assertEqual(ctl['RightRail'][1], [1140, 133, 140, 667])
        self.assertEqual(ctl['Footer'][1], [140, 688, 1000, 112])

    def test_the_725s_bars_and_rails(self):
        _, ctl, out = self.probe('Home.dc.html', 'TLP725T')
        self.assertEqual(ctl['Header'][1], [0, 0, 1024, 103])
        self.assertEqual(ctl['LeftRail'][1], [0, 103, 112, 497])
        self.assertEqual(ctl['RightRail'][1], [912, 103, 112, 497])

    def test_a_hub_carves_the_header_and_rails_from_main(self):
        """On the 525 hub the header and the left rail get bands carved from
        main at the page's scale (0.6), the right rail goes to the menu bar."""
        _, ctl, out = self.probe('Home.dc.html', 'TLP525T')
        self.assertEqual(out['problems'], [])
        x, y, w, h = ctl['Header'][1]
        self.assertEqual((x, y, w), (0, 0, 800))
        self.assertAlmostEqual(h, 137 * 0.6, delta=2)
        self.assertEqual(ctl['LeftRail'][1][0], 0)
        self.assertAlmostEqual(ctl['LeftRail'][1][2], 140 * 0.6, delta=1)

    def test_a_hubs_level_runs_beside_its_up_and_down(self):
        ctl = _level_beside(self, 'turbulence', 'TLP525T', self.probe)
        # Its rings carry the kit's own volume icons, as its Mute does.
        for n, icon in (('VolumeSlider Up', 'volume_up'), ('VolumeSlider Down', 'volume_down')):
            g = ctl[n][0]
            self.assertFalse(g.get('text'), n)
            self.assertTrue(all(f'_{icon}_' in (s.get('image') or '') for s in g['states']), (n, g['states']))

    def test_a_row_the_depth_of_its_bar_stays_in_it(self):
        """A row of tabs across the header, the template's own way: spanning the
        header's depth, it is scaled by the smaller of its two mapped sides, and
        the tabs stay inside the 725's 103 px header, centred across it as on
        the 1035."""
        tb = 'component-from-global-scope="ExtronTurbulence.'
        row = ('<div style="position: absolute; left: 430px; top: 0px; width: 421px; height: 133px; display: flex; '
               'gap: 20px">\n' + ''.join(
                   f'<x-import {tb}Button" name="{n}" variant="source" icon="{i}" style="width: 127px; '
                   f'height: 133px">{t}</x-import>\n'
                   for n, i, t in (('TabLaptop', 'input_laptop', 'Laptop'), ('TabPC', 'input_pc', 'PC'),
                                   ('TabCam', 'input_doc-cam', 'Doc Cam'))) + '</div>\n')
        anchor = f'<x-import {tb}Panel" name="LeftRail"'
        _, ctl, out = self.probe('Home.dc.html', 'TLP725T', edit=(anchor, row + anchor))
        tabs = [ctl[n][1] for n in ('TabLaptop', 'TabPC', 'TabCam')]
        for r in tabs:
            self.assertTrue(_inside(r, [0, 0, 1024, 103]), r)
        self.assertLessEqual(abs((tabs[0][0] + tabs[-1][0] + tabs[-1][2]) / 2 - 512), 2, tabs)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestAPagesOwnSliderElsewhere(_Probe, unittest.TestCase):
    """The Afterburn huddle's volume slider is the Page's own, above a Mute in
    the kit's icon look; listed for a panel whose seed has no slider, it is a
    level with Up and Down."""

    CANVAS = CANVAS
    PAGE = 'name="Huddle Home" theme="grape"'

    def _on(self, panel):
        return self.probe('Home.dc.html', panel,
                          edit=(self.PAGE, f'name="Huddle Home" panels="TLP1035T {panel}" theme="grape"'))

    def test_up_and_down_keep_a_look_that_draws_them(self):
        """The icon look draws a kit icon the button names, and the theme has
        none for a step: Up and Down take its default button there. Given the
        Mute's look they had no icon, and the translator refused them."""
        _, ctl, out = self._on('TLP525T')
        self.assertEqual([p for p in out['problems'] if 'VolumeSlider' in p], [])
        for n in ('VolumeSlider Up', 'VolumeSlider Down'):
            g = ctl[n][0]
            self.assertIsNone(g.get('missing_icon'), n)
            self.assertEqual(g['variant'], designsys.load('afterburn')['defaults']['button']['variant'], n)

    def test_on_the_320_it_is_a_level_with_up_and_down(self):
        """Laid in the 320's rows, its cell was 2 px short of what a level
        with Up and Down at the touch minimum, and 24 px of level, need."""
        _, ctl, out = self._on('TLP320M')
        self.assertEqual([p for p in out['problems'] if 'VolumeSlider' in p], [])
        self.assertEqual(ctl['VolumeSlider'][0]['kind'], 'level')
        self.assertGreaterEqual(max(ctl['VolumeSlider'][1][2:]), 24)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestARailsLabel(_Probe, unittest.TestCase):
    """A Rail's label is read, not touched, so it spans the rail's band; its
    touchable neighbours keep the touch padding. Held to that padding, the
    Volume heading three designers put over their rail overflowed every
    hub's rail at the hub's 18 pt floor."""

    CANVAS = PANELS_CANVAS
    RAIL = '<x-import component-from-global-scope="ExtronAfterburn.Rail">'
    LABEL = ('<x-import component-from-global-scope="ExtronAfterburn.Label" name="VolumeLabel" '
             'align="center">Volume</x-import>')

    def test_it_spans_the_band_and_its_words_fit(self):
        band = designsys.models(designsys.load('afterburn'))['TLP525T']['rail']
        _, ctl, _ = self.probe('Home.dc.html', 'TLP525T', edit=(self.RAIL, self.RAIL + self.LABEL))
        _, rect, overflow = ctl['VolumeLabel']
        self.assertEqual((rect[0], rect[2]), (band[0], band[2]))
        self.assertFalse(overflow)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestARailsKitButton(_Probe, unittest.TestCase):
    """A captionless kit button in a Rail takes the size its seed draws its
    variant at - Turbulence's ring is 100 x 100 - where the variant has one.
    Drawn at a generic 64, the rings looked nothing like the template's, and a
    designer placed the rail's controls by hand instead."""

    CANVAS = os.path.join(HERE, 'data', 'design-panels-turbulence')
    THEME = 'turbulence'
    PAGE = ('does="The room\'s home page: share a source, set volume, end the call." style="position: '
            'absolute; left: 0px; top: 0px; width: 1280px; height: 800px">')
    RAIL = ('<x-import component-from-global-scope="ExtronTurbulence.Rail">'
            '<x-import component-from-global-scope="ExtronTurbulence.Button" name="RailMute" variant="ring" '
            'icon="volume_mute" does="Mutes the room."></x-import></x-import>')

    def test_it_takes_its_variants_size(self):
        edit = (self.PAGE, self.PAGE + self.RAIL)
        _, ctl, _ = self.probe('Home.dc.html', 'TLP1035T', edit=edit)
        self.assertEqual(ctl['RailMute'][1][2:], [100, 100])
        # On the 525 the hub carves its bars from the rail, whose scale leaves
        # 100 px under the touch minimum: square, at that minimum.
        _, ctl, _ = self.probe('Home.dc.html', 'TLP525T', edit=edit)
        self.assertEqual(ctl['RailMute'][1][2:], [66, 66])


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

    def test_a_panel_the_other_way_up_is_laid_out_on_its_own_canvas(self):
        """The 300M turned is a panel of its own, TLP300M-Landscape: Afterburn's
        300 Landscape series at 480x320, its own art, its main region beside a
        rail - by the bundle's own table, which took one row a model. The
        huddle's rail is too much for a 300M either way up, and the panel says
        so by its own name."""
        page, ctl, out = self.probe('Home.dc.html', 'TLP300M-Landscape')
        self.assertEqual((page['panel'], page['size']), ('TLP300M-Landscape', [480, 320]))
        self.assertIn('2400x1600', page['background_file'])
        self.assertEqual(page['seed'], 'seeds/Afterburn 300M Landscape.gdl')
        for name in self.MAIN + self.SOURCES:
            self.assertTrue(_inside(ctl[name][1], [0, 0, 392, 320]), (name, ctl[name][1]))
        for name in ('VolumeSlider Down', 'VolumeSlider Up', 'Mute'):
            self.assertGreaterEqual(ctl[name][1][0], 392, (name, ctl[name][1]))
        self.assertTrue(any('the rail needs' in p and "TLP300M-Landscape's 320" in p
                            for p in out.get('problems', [])), out.get('problems'))

    def test_a_panel_turned_where_no_template_is_drawn_is_its_series_turned(self):
        """Extron draws no template for the 1035M portrait, so the panel is the
        1220 series turned - main region and rail transposed, the rail running
        across below - on the page colour, with no art, on its own seed."""
        page, ctl, out = self.probe('Home.dc.html', 'TLP1035M-Portrait')
        self.assertEqual((page['panel'], page['size']), ('TLP1035M-Portrait', [800, 1280]))
        # No art: the bundle leaves the field out, and the page is its colour.
        self.assertIsNone(page.get('background_file'))
        self.assertEqual(page['seed'], 'seeds/Afterburn 1035 Portrait.gdl')
        for name in self.MAIN + self.SOURCES:
            self.assertTrue(_inside(ctl[name][1], [24, 183, 752, 916]), (name, ctl[name][1]))
        for name in ('VolumeSlider', 'Mute', 'HelpBtn', 'RoomOff'):
            self.assertTrue(_inside(ctl[name][1], [0, 1099, 800, 181]), (name, ctl[name][1]))
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

    def test_a_modal_scales_whole_about_the_screen(self):
        """Afterburn's chrome is its background art, not controls, so its
        pages go through no bands: a modal's card scales whole and stays
        centred on the screen, as Extron's own 525 centres its modals."""
        _, ctl, _ = self.probe('ConfirmRoomOff.dc.html', 'TLP525T')
        self.assertEqual(ctl['Card'][1], [244, 150, 312, 180])
        _, ctl, _ = self.probe('Help.dc.html', 'TLP525T')
        x, _, w, _ = ctl['Card'][1]
        self.assertAlmostEqual(x + w / 2, 400, delta=1)

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

    def test_a_level_is_named_where_the_seed_builds_none(self):
        """The 1035's and 725's seeds carry a slider and no level, and a level
        cannot be cloned from them: a Level there is named on the canvas, not
        left for the build to refuse. The 525's seed has one."""
        edit = ('ExtronAfterburn.Slider" name="VolumeSlider"', 'ExtronAfterburn.Level" name="VolumeSlider"')
        for panel in ('TLP1035T', 'TLP725T'):
            with self.subTest(panel=panel):
                _, ctl, out = self.probe('Home.dc.html', panel, edit=edit)
                self.assertIn(f"VolumeSlider is a Level, which the {panel}'s seed cannot build - a Slider can",
                              out['problems'])
        _, ctl, out = self.probe('Home.dc.html', 'TLP525T', edit=edit)
        self.assertEqual(out['problems'], [])
        self.assertEqual(ctl['VolumeSlider'][0]['kind'], 'level')

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
