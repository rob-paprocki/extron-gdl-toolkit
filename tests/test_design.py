"""The Design canvas -> spec translator (gdl/design.py).

Most of these feed the translator what the in-browser probe reports, so they
run anywhere. The last class lays a real canvas out in headless Chrome with
the Design type's runtime: it needs Chrome and the runtime file, named by
$GDL_DC_RUNTIME (the type's artifact-type/dc-runtime.js, fetched with the
Artifact tool), and skips without them.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from gdl import design, designsys, idmap, seeds  # noqa: E402
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

    def test_a_canvas_warning_is_a_note_not_a_problem(self):
        """A region page missing a region the template always draws is named
        on the canvas and in the translate report, and still builds (owner's
        call 4, docs/superpowers/specs/2026-10-22-region-frame-design.md)."""
        said = 'Main has no RightRail - the Mach working page always draws one'
        o = out(HOME)
        o['warnings'] = [said]
        spec, problems, notes = translate({'Home.dc.html': o})
        self.assertEqual(problems, [])
        self.assertIsNotNone(spec)
        self.assertIn(f'Home.dc.html: {said}', notes)

    def _backs(self):
        """A 320's pages as its layout derives them (bundle.js planPages,
        pagePart): Main's keys lead to Laptop, DocCam and Help, Other's to
        Help too; DocCam goes on over 'DocCam 2', whose Back leads back to
        it; Orphan nothing leads to. Each page's own Back says only `back`."""
        def back(name, **g):
            return ctl([263, 0, 57, 40], kind='button', name=name, text='', derived=True, back=True, **g)

        def key(name, to):
            return ctl([20, 60, 100, 50], kind='button', name=name, text=name, nav=to)
        doccam = out(page('DocCam'), back('DocCam Back'),
                     ctl([280, 200, 40, 40], kind='button', name='DocCam More', text='', derived=True,
                         nav='DocCam 2'),
                     dict(back('DocCam 2 Back', nav='DocCam'), part=0))
        doccam['parts'] = [{'gdl': json.dumps({'kind': 'page', 'name': 'DocCam 2', 'host': 'DocCam',
                                               'size': [320, 240]}), 'rect': [0, 0, 320, 240]}]
        return translate({
            'Main.dc.html': out(page('Main', start=True), key('Laptop', 'Laptop'), key('Doc Cam', 'DocCam'),
                                key('Help', 'Help')),
            'Other.dc.html': out(page('Other'), key('Other Help', 'Help')),
            'Laptop.dc.html': out(page('Laptop'), back('Laptop Back')),
            'DocCam.dc.html': doccam,
            'Help.dc.html': out(page('Help'), back('Help Back')),
            'Orphan.dc.html': out(page('Orphan'), back('Orphan Back')),
        })

    def test_the_templates_measured_chrome_colours_are_its_own(self):
        """The colours a series' frame measured its chrome in - the 320's
        #4B4B4C Volume strip, its #E4EDF5 level - are the template's, which
        the six-colour cap exempts, as the spec reads them (#AARRGGBB)."""
        frame = {'volume': {'surfaces': [{'fill': '#4B4B4CFF', 'rect': [278, 0, 42, 240]}],
                            'level': {'track': '#000000FF', 'bar': '#E4EDF5FF', 'art': None}},
                 'top': {'surfaces': [{'fill': '#000000B4'}, {'fill': None}]}}
        self.assertEqual(design._frame_colors(frame), {'#FF4B4B4C', '#FF000000', '#FFE4EDF5', '#B4000000'})
        self.assertEqual(design._frame_colors(None), set())

    def test_a_derived_back_goes_to_the_one_page_that_shows_its_page(self):
        """The 320's Back says only `back`: translate gives it the nav of the
        one page with a control leading to its page - and no `back` stays in
        the spec."""
        spec, _, _ = self._backs()
        on = {c['name']: c for q in spec['pages'] for c in q['controls']}
        self.assertEqual(on['Laptop Back']['nav'], 'Main')
        self.assertFalse([c for c in on.values() if 'back' in c])

    def test_a_pages_own_later_page_does_not_show_it(self):
        """'DocCam 2' leads back to DocCam but does not show it: DocCam's own
        Back still goes back to Main, the one page that shows DocCam (a page
        that runs over two had none, and no way back to Main on screen)."""
        spec, _, notes = self._backs()
        on = {c['name']: c for q in spec['pages'] for c in q['controls']}
        self.assertEqual((on['DocCam Back']['nav'], on['DocCam 2 Back']['nav']), ('Main', 'DocCam'))
        self.assertFalse([n for n in notes if 'DocCam' in n], notes)

    def test_a_back_with_no_page_or_two_showing_its_page_is_the_programs(self):
        """With two pages that show Help, or none that shows Orphan, its Back
        has no `nav` - it goes where the program says - and the note says why."""
        spec, _, notes = self._backs()
        on = {c['name']: c for q in spec['pages'] for c in q['controls']}
        self.assertNotIn('nav', on['Help Back'])
        self.assertNotIn('nav', on['Orphan Back'])
        self.assertIn("'Help' Help Back: Main, Other all show 'Help' - it goes back where the program says", notes)
        self.assertIn("'Orphan' Orphan Back: nothing on this panel shows 'Orphan' - it goes back where the "
                      'program says', notes)

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

    def test_an_image_brings_its_art_and_its_layout(self):
        """The template's own art - Turbulence's header bar, its device
        pictures - is an image control naming its kit file, which the spec
        takes with its kit path."""
        if '2047x151_header.png' not in designsys.kit_index(designsys.load('turbulence'))['paths']:
            self.skipTest("Turbulence's art is not extracted here (python -m gdl.designsys extract turbulence)")
        home = page('Home', start=True, template='Turbulence', scheme='default')
        spec, problems, _ = translate({'Home.dc.html': out(home, ctl(
            [0, 0, 1280, 133], kind='image', name='Header Bar', image='2047x151_header.png', layout='stretch',
            derived=True), ctl([140, 137, 293, 257], kind='image', name='Laptop Image',
                               image='1152x1152_laptop.png'))})
        self.assertEqual(problems, [])
        bar, pic = spec['pages'][0]['controls']
        self.assertEqual(bar, {'kind': 'image', 'name': 'Header Bar', 'rect': [0, 0, 1280, 133],
                               'image': '2047x151_header.png', 'layout': 'stretch', 'derived': True})
        self.assertNotIn('layout', pic)
        self.assertEqual(spec['images']['2047x151_header.png'], 'Turbulence/2047x151_header.png')
        self.assertEqual(spec['images']['1152x1152_laptop.png'], 'Turbulence/1152x1152_laptop.png')

    def test_an_image_the_kit_lacks_is_refused(self):
        home = page('Home', start=True, template='Turbulence', scheme='default')
        _, problems, _ = translate({'Home.dc.html': out(home, ctl(
            [0, 0, 100, 100], kind='image', name='Odd', image='1152x1152_nothing.png'))})
        self.assertTrue(any('1152x1152_nothing.png' in p for p in problems), problems)

    def test_a_popup_takes_its_photo(self):
        """A hub's popups stand on the page's photo, as Shockwave's and
        Turbulence's own do: the popup carries it, a modal never does."""
        pop = page('Laptop', kind='popup', template='Turbulence', scheme='default', group='Sources',
                   size=[702, 480], background='none', background_image='bkgd_swoop_plain.png',
                   background_file='Turbulence/bkgd_swoop_plain.png')
        modal = page('Help', kind='popup', modal=True, template='Turbulence', scheme='default',
                     background_image='bkgd_swoop_plain.png', background_file='Turbulence/bkgd_swoop_plain.png')
        spec, _, _ = translate({'Home.dc.html': out(page('Home', start=True, template='Turbulence', scheme='default')),
                                'Laptop.dc.html': out(pop), 'Help.dc.html': out(modal)})
        laptop, help_ = spec['popups']
        self.assertEqual((laptop['background_image'], laptop['background_layout']), ('bkgd_swoop_plain.png', 'stretch'))
        self.assertNotIn('background_image', help_)
        self.assertEqual(spec['images']['bkgd_swoop_plain.png'], 'Turbulence/bkgd_swoop_plain.png')

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

    def test_two_boards_of_one_name_are_a_problem(self):
        rendered = {'TLP725T': {'Home.dc.html': self.home('TLP725T'),
                                'Help.dc.html': dict(out(panel_page('Home', 'TLP725T')), parts=[], problems=[])}}
        specs, problems, _ = Fake(['Home.dc.html', 'Help.dc.html']).translate_panels(rendered)
        self.assertIsNone(specs)
        self.assertTrue(any("'Home'" in p and 'also' in p for p in problems['TLP725T']), problems)

    # -- what two region pages derive, and a designer's own window of its name --
    # A hub derives Select Source, its options, the display group's popup and
    # the Volume Level strip from each region page, and the 320 its Volume
    # modal: two working pages (Main SD and a call page) derived each twice.
    LEVEL = dict(kind='level', name='Volume', fill='raised', track=15, orientation='up', seed_id=8024)
    STRIP = {'kind': 'popup', 'name': 'Volume Level', 'group': 'Volume Level', 'size': [66, 300]}

    def board(self, name, model, *controls, parts=(), start=False, **kw):
        pg = json.loads(panel_page(name, model, start=start))
        o = out(json.dumps(dict(pg, **kw)), *controls)
        o['parts'], o['problems'] = list(parts), []
        return o

    @staticmethod
    def in_part(i, rect, **g):
        return dict(ctl(rect, **g), part=i)

    # The Center's popup region, on every page of both panels.
    CENTER = ctl([0, 0, 700, 500], kind='popup_ref', name='Controls', group='Sources')

    def two_pages(self, parts, home=(), call=(), home_big=(), call_big=(), boards=None):
        """Home and Call on the 1035 as drawn (`home_big`, `call_big`: each
        page's own controls there) and on the 725 with what its layout derived
        - `parts` the same on each page, `home` and `call` what is drawn
        there - with any other `boards` on each panel."""
        big = [self.CENTER] if boards else []
        small = [self.CENTER] if boards or any(json.loads(p['gdl']).get('group') == 'Sources' for p in parts) else []
        rendered = {'TLP1035T': {'Home.dc.html': self.board('Home', 'TLP1035T', *big, *home_big, start=True),
                                 'Call.dc.html': self.board('Call', 'TLP1035T', *big, *call_big)},
                    'TLP725T': {'Home.dc.html': self.board('Home', 'TLP725T', *small, *home, parts=parts, start=True),
                                'Call.dc.html': self.board('Call', 'TLP725T', *small, *call, parts=parts)}}
        for m in rendered:
            rendered[m].update({f"{n.replace(' ', '')}.dc.html": self.board(n, m, *(c(m) if callable(c) else c),
                                                                             kind='popup', group='Sources',
                                                                             size=[700, 500], **kw)
                                for n, c, kw in boards or ()})
        return Fake(list(rendered['TLP1035T'])).translate_panels(rendered)

    @needs_panel_files
    def test_a_window_two_region_pages_derive_alike_is_one(self):
        """The Volume Level strip, or the 320's Volume modal, is one window the
        program shows from any page: derived alike by two region pages - the
        same controls, the same IDs - it is one popup, not two of one name."""
        vol = ctl([1100, 200, 66, 300], **dict(self.LEVEL, kind='slider'))
        # A hub's level carries no seed ID: it is the 1035's slider's by name.
        lv = self.in_part(0, [10, 10, 46, 280], **{k: v for k, v in self.LEVEL.items() if k != 'seed_id'})
        ref = ctl([900, 100, 66, 300], kind='popup_ref', name='Volume Region', group='Volume Level', derived=True)
        specs, problems, _ = self.two_pages([part(self.STRIP, [900, 100, 66, 300])], home=[ref, lv],
                                            call=[ref, lv], home_big=[vol], call_big=[vol])
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
        self.assertEqual([p['name'] for p in specs['TLP725T']['popups']], ['Volume Level'])
        self.assertEqual(specs['TLP725T']['popups'][0]['controls'][0]['id'], 8024)

    @needs_panel_files
    def test_what_the_program_knows_a_control_by_is_read_off_the_drawn_panel_alone(self):
        """Whether two derived windows are one is read off the panel the canvas
        is drawn on. Where it has no spec - the 1035's boards hold no Page - no
        later panel stands in for it: what the 525 makes of its two Volume
        strips is what it makes of them listed without the 725, whose slider's
        seed ID had made them one."""
        seed = 'seeds/Afterburn 525.gdl'
        art = ('4000x2400_bg1-default_main.png',
               'Afterburn/Backgrounds/4000x2400/TLP 525/4000x2400_bg1-default_main.png')
        if not (seeds.usable(seed) and resolve_image(art[1])):
            self.skipTest("needs the Afterburn 525 seed and Extron's Afterburn art")
        three = PANELS + ['TLP525T']
        lv = self.in_part(0, [10, 10, 46, 280], **{k: v for k, v in self.LEVEL.items() if k != 'seed_id'})
        ref = ctl([700, 100, 66, 300], kind='popup_ref', name='Volume Region', group='Volume Level', derived=True)
        vol = ctl([900, 150, 66, 300], **dict(self.LEVEL, kind='slider'))

        def board(name, model, *controls, parts=()):
            if model == 'TLP525T':
                pg = page(name, panel=model, panels=three, tier='A', derived=True, size=[800, 480], seed=seed,
                          background_image=art[0], background_file=art[1], theme='default', start=name == 'Home')
            else:
                pg = panel_page(name, model, panels=three, start=name == 'Home')
            o = out(pg, *controls)
            o['parts'], o['problems'] = list(parts), []
            return o
        none = {'pages': 0, 'page': None, 'controls': [], 'parts': [], 'stray': [], 'errors': [], 'problems': []}
        strip = [part(self.STRIP, [700, 100, 66, 300])]
        rendered = {'TLP1035T': {'Home.dc.html': none, 'Call.dc.html': none},
                    'TLP725T': {n + '.dc.html': board(n, 'TLP725T', vol) for n in ('Home', 'Call')},
                    'TLP525T': {n + '.dc.html': board(n, 'TLP525T', ref, lv, parts=strip) for n in ('Home', 'Call')}}
        boards = list(rendered['TLP1035T'])
        specs, problems, notes = Fake(boards).translate_panels(rendered)
        self.assertIsNone(specs)
        self.assertTrue(problems['TLP1035T'], problems)
        del rendered['TLP725T']
        _, alone, alone_notes = Fake(boards).translate_panels(rendered)
        self.assertEqual((problems['TLP525T'], notes['TLP525T']), (alone['TLP525T'], alone_notes['TLP525T']))

    @needs_panel_files
    def test_a_window_two_region_pages_derive_unalike_is_named_for_its_page(self):
        """Each page's options hold its own launchers: the later page's takes
        its page's name in front, and its opener follows it."""
        opts = {'kind': 'popup', 'name': 'More Options', 'group': 'Options', 'size': [700, 500]}
        light = dict(BTN16, name='Lighting', text='Lighting', id=301)
        cam = dict(BTN16, name='Camera', text='Camera', id=302)
        opener = ctl([800, 300, 120, 80], **dict(BTN16, name='Settings', text='Settings', derived=True,
                                                   nav='More Options'))
        ref = ctl([0, 0, 700, 500], kind='popup_ref', name='Options Region', group='Options', derived=True)
        specs, problems, notes = self.two_pages(
            [part(opts, [0, 0, 700, 500])],
            home=[ref, opener, self.in_part(0, [40, 100, 200, 64], **light)],
            call=[ref, opener, self.in_part(0, [40, 100, 200, 64], **cam)],
            home_big=[ctl([40, 520, 200, 64], **light)], call_big=[ctl([40, 520, 200, 64], **cam)])
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
        spec = specs['TLP725T']
        self.assertEqual(sorted(p['name'] for p in spec['popups']), ['Call More Options', 'More Options'])
        navs = {pg['name']: next(c['nav'] for c in pg['controls'] if c['name'] == 'Settings') for pg in spec['pages']}
        self.assertEqual(navs, {'Home': 'More Options', 'Call': 'Call More Options'})
        self.assertTrue(any("'Call More Options'" in n for n in notes['TLP725T']), notes)

    @needs_panel_files
    def test_a_designers_window_stands_in_for_the_one_derived_where_it_holds_its_controls(self):
        """A designer who draws Display Control themselves - the window the
        hub's display opener shows - is not refused: where their board holds
        the controls the derived one would (the same names and IDs), it is
        that window, and the Section's heading, which its title says, is left
        off the page by name. Where it holds others, the derived one takes its
        page's name."""
        disp = {'kind': 'popup', 'name': 'Display Control', 'group': 'Sources', 'size': [700, 500]}
        on = dict(BTN16, name='Display On', text='On', id=112)
        dial = dict(BTN16, name='Dial', text='Dial', id=114)
        heading = dict(kind='label', name='Display Heading', text='Display', color='text', size=16)
        opener = ctl([800, 300, 120, 80], **dict(BTN16, name='Display Opener', text='Display', derived=True,
                                                   nav='Display Control'))
        close = dict(BTN16, name='Display Control Close', text='Close', derived=True, nav='Home')
        specs, problems, notes = self.two_pages(
            [part(disp, [0, 0, 700, 500])],
            home=[opener, self.in_part(0, [40, 40, 300, 30], **heading), self.in_part(0, [40, 100, 200, 64], **on),
                  self.in_part(0, [600, 10, 80, 60], **close)],
            call=[opener, self.in_part(0, [40, 100, 200, 64], **dial),
                  self.in_part(0, [600, 10, 80, 60], **dict(close, nav='Call'))],
            home_big=[ctl([40, 520, 300, 30], **heading), ctl([40, 580, 200, 64], **on)],
            call_big=[ctl([40, 580, 200, 64], **dial)],
            boards=[('Display Control', [ctl([400, 300, 200, 64], **on)], {})])
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
        spec = specs['TLP725T']
        by = {p['name']: p for p in spec['popups']}
        self.assertEqual(sorted(by), ['Call Display Control', 'Display Control'])
        self.assertEqual([c['name'] for c in by['Display Control']['controls']], ['Display On'])
        self.assertEqual(by['Display Control']['controls'][0]['id'], 112)
        home = next(p for p in spec['pages'] if p['name'] == 'Home')
        self.assertIn('Display Heading', home['left'])
        navs = {pg['name']: next(c['nav'] for c in pg['controls'] if c['name'] == 'Display Opener')
                for pg in spec['pages']}
        self.assertEqual(navs, {'Home': 'Display Control', 'Call': 'Call Display Control'})
        self.assertTrue(any('stands in' in n for n in notes['TLP725T']), notes)

    @needs_panel_files
    def test_a_hub_popups_close_goes_back_to_the_one_grid_that_shows_it(self):
        """With a Select a Source of each page's own, a source both grids show
        closes where the program says, as a window opened from two places
        does; one only the call page's grid shows closes back to that one."""
        grid = {'kind': 'popup', 'name': 'Select Source', 'group': 'Sources', 'size': [700, 500], 'main': True}
        laptop = dict(BTN16, name='Laptop', text='Laptop', id=101, nav='Laptop')
        teams = dict(BTN16, name='Teams', text='Teams', id=105, nav='Teams')

        def source(name):
            def drawn(m):
                key = ctl([40, 140, 200, 64], **dict(BTN16, name=name + ' Key', text='Key'))
                if m == 'TLP725T':
                    return [key, ctl([600, 10, 80, 60], **dict(BTN16, name=name + ' Close', text='Close',
                                                              derived=True, nav='Select Source'))]
                return [key]
            return drawn
        specs, problems, notes = self.two_pages(
            [part(grid, [0, 0, 700, 500])],
            home=[self.in_part(0, [40, 100, 200, 64], **laptop)],
            call=[self.in_part(0, [40, 100, 200, 64], **laptop), self.in_part(0, [300, 100, 200, 64], **teams)],
            home_big=[ctl([40, 520, 200, 64], **laptop)],
            call_big=[ctl([40, 520, 200, 64], **laptop), ctl([300, 520, 200, 64], **teams)],
            boards=[(n, source(n), {'hub': 'source'}) for n in ('Laptop', 'Teams')])
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
        by = {p['name']: p for p in specs['TLP725T']['popups']}
        self.assertEqual(sorted(by), ['Call Select Source', 'Laptop', 'Select Source', 'Teams'])
        closes = {n: next(c for c in by[n]['controls'] if c['name'] == n + ' Close') for n in ('Laptop', 'Teams')}
        self.assertNotIn('nav', closes['Laptop'])
        self.assertEqual(closes['Teams']['nav'], 'Call Select Source')
        self.assertTrue(any("'Laptop'" in n and 'program' in n for n in notes['TLP725T']), notes)

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
    def test_fixed_chrome_keeps_its_seed_id_where_it_is_free(self):
        """A region page's Help, Power, Volume, Mute and mode launcher carry
        the template's seed ID (`seed_id`, off the frame's `ids`): kept, the
        same on every panel, where the designer gave none and no canvas
        control has it - and the page's band steps over it."""
        helpb = dict(BTN16, name='Help', text='Help', seed_id=1001)
        laptop = dict(BTN16, name='Laptop', text='Laptop')
        rendered = {m: {'Home.dc.html': self.home(m, ctl([40, 40, 200, 64], **laptop),
                                                  ctl([400, 40, 200, 64], **helpb))} for m in PANELS}
        specs, problems, _ = translate_panels(rendered)
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
        for m in PANELS:
            ids = {c['name']: c['id'] for c in specs[m]['pages'][0]['controls']}
            self.assertEqual((ids['Help'], ids['Laptop']), (1001, 1002), m)
            self.assertFalse([c for c in specs[m]['pages'][0]['controls'] if '_seed_id' in c], m)

    @needs_panel_files
    def test_the_chrome_keeps_its_seed_ids_on_every_page(self):
        """Every working page draws the region chrome, and a program finds it
        at the template's IDs on each: Help, Power, Room Mode, Mute and Volume
        are one control on every page and every panel. Help's seed sits in the
        second page's band here, so that band steps over it."""
        chrome = [dict(BTN16, name='Help', text='Help', seed_id=2001),
                  dict(BTN16, name='Power', text='Power', seed_id=8022),
                  dict(BTN16, name='Room Mode', text='Mode', seed_id=8118),
                  dict(BTN16, name='Volume Mute', text='Mute', seed_id=8021),
                  dict(kind='slider', name='Volume', fill='raised', seed_id=8024)]
        want = {'Help': 2001, 'Power': 8022, 'Room Mode': 8118, 'Volume Mute': 8021, 'Volume': 8024}

        def board(name, model, own):
            at = [[40, 40, 200, 64], [40, 120, 200, 64], [40, 200, 200, 64], [40, 280, 200, 64],
                  [300, 40, 64, 380]]
            o = out(panel_page(name, model, start=name == 'Home'), ctl([600, 40, 200, 64], **own),
                    *(ctl(r, **g) for r, g in zip(at, chrome)))
            o['parts'], o['problems'] = [], []
            return o
        rendered = {m: {'Home.dc.html': board('Home', m, dict(BTN16, name='Laptop', text='Laptop')),
                        'Call.dc.html': board('Call', m, dict(BTN16, name='Dial', text='Dial'))}
                    for m in PANELS}
        specs, problems, _ = Fake(['Home.dc.html', 'Call.dc.html']).translate_panels(rendered)
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
        for m in PANELS:
            for pg, own, band in zip(specs[m]['pages'], ('Laptop', 'Dial'), (1001, 2002)):
                ids = {c['name']: c['id'] for c in pg['controls']}
                self.assertEqual({n: ids[n] for n in want}, want, (m, pg['name']))
                self.assertEqual(ids[own], band, (m, pg['name']))

    @needs_panel_files
    def test_a_designers_id_wins_over_a_seed_id(self):
        """The designer's own ID on the chrome is kept; and a seed ID another
        canvas control has is not the chrome's - it takes one of its band."""
        for helpb, laptop, want in ((dict(seed_id=8117, id=42), {}, (42, 1001)),
                                    (dict(seed_id=8117), dict(id=8117), (1001, 8117))):
            with self.subTest(helpb=helpb, laptop=laptop):
                h = dict(BTN16, name='Help', text='Help', **helpb)
                lp = dict(BTN16, name='Laptop', text='Laptop', **laptop)
                rendered = {m: {'Home.dc.html': self.home(m, ctl([40, 40, 200, 64], **lp),
                                                          ctl([400, 40, 200, 64], **h))} for m in PANELS}
                specs, problems, _ = translate_panels(rendered)
                self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
                for m in PANELS:
                    ids = {c['name']: c['id'] for c in specs[m]['pages'][0]['controls']}
                    self.assertEqual((ids['Help'], ids['Laptop']), want, m)

    @needs_panel_files
    def test_a_mirror_shares_its_controls_id(self):
        """Where the template draws one control twice - Shockwave 1035's tab
        and the caption under its glyph (`twin`) - the copy the layout adds
        (`mirror`: the control's name) takes that control's ID on the panel
        that draws it, not one from 50001, and the spec checks clean."""
        laptop = dict(BTN16, name='Laptop', text='', nav='Help', does='Routes it.')
        twin = dict(kind='button', name='Laptop Caption', text='Laptop', derived=True, mirror='Laptop',
                    nav='Help', does='Routes it.', size=16,
                    states=[{'name': 'Off', 'fill': 'none'}, {'name': 'On', 'fill': 'none'}])
        rendered = {'TLP1035T': {'Home.dc.html': self.home('TLP1035T', ctl([40, 40, 200, 90], **laptop),
                                                           ctl([40, 94, 200, 36], **twin)),
                                 'Help.dc.html': out(panel_page('Help', 'TLP1035T'))},
                    'TLP725T': {'Home.dc.html': self.home('TLP725T', ctl([40, 40, 200, 90], **laptop)),
                                'Help.dc.html': out(panel_page('Help', 'TLP725T'))}}
        for o in rendered.values():
            o['Help.dc.html'].update(parts=[], problems=[])
        specs, problems, _ = translate_panels(rendered)
        self.assertEqual(problems, {'TLP1035T': [], 'TLP725T': []})
        big = {c['name']: c for c in specs['TLP1035T']['pages'][0]['controls']}
        self.assertEqual(big['Laptop Caption']['id'], big['Laptop']['id'])
        self.assertEqual(big['Laptop Caption']['nav'], big['Laptop']['nav'])
        self.assertNotIn('_mirror', big['Laptop Caption'])
        from gdl.idmap import IdMap, check_panels
        self.assertEqual(check_panels({m: IdMap(Panel(s)) for m, s in specs.items()}), [])

    @needs_panel_files
    def test_a_mirror_is_its_controls_while_another_panel_has_a_problem(self):
        """A problem on any panel stops the IDs being pinned, and the spec
        check still runs on every panel: the 1035's tab twins came out as
        controls of their own - 152x36 under the touch minimum, overlapping
        their tabs, alike in both states - on a Shockwave room whose 525 had
        an overlap of its own, the README's example among them (PR8 review)."""
        laptop = dict(BTN16, name='Laptop', text='', nav='Help', does='Routes it.')
        twin = dict(kind='button', name='Laptop Caption', text='Laptop', derived=True, mirror='Laptop',
                    nav='Help', does='Routes it.', size=16,
                    states=[{'name': 'Off', 'fill': 'none'}, {'name': 'On', 'fill': 'none'}])
        rendered = {'TLP1035T': {'Home.dc.html': self.home('TLP1035T', ctl([40, 40, 200, 90], **laptop),
                                                           ctl([40, 94, 200, 36], **twin)),
                                 'Help.dc.html': out(panel_page('Help', 'TLP1035T'))},
                    'TLP725T': {'Home.dc.html': self.home('TLP725T', ctl([40, 40, 200, 90], **laptop)),
                                'Help.dc.html': out(panel_page('Help', 'TLP725T'))}}
        for o in rendered.values():
            o['Help.dc.html'].update(parts=[], problems=[])
        rendered['TLP725T']['Help.dc.html']['problems'] = ['Help: a problem of its own']
        specs, problems, _ = translate_panels(rendered)
        self.assertIsNone(specs)
        self.assertTrue(problems['TLP725T'])
        self.assertEqual([p for p in problems['TLP1035T'] if 'Laptop Caption' in p], [])

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


class TestCompareTemplate(unittest.TestCase):
    """`compare <canvas> --template`: each artboard as drawn for each panel the
    canvas lists, beside the page of that panel's own template seed it stands
    for - the working page beside the seed's (Main SD, a hub's Main Page, the
    320's Main), a source beside the seed's source popup, a window beside the
    seed's window of that role - for the designer's critique loop (SKILL.md).
    Chrome is stood in for; the template side is the real seed."""

    BOARDS = {
        'Main.dc.html': ('<x-import component-from-global-scope="ExtronMach.Page" name="Main" '
                         'panels="TLP1035T TLP525T"><x-import component-from-global-scope="ExtronMach.Header">'
                         '</x-import><x-import component-from-global-scope="ExtronMach.Center"></x-import></x-import>'),
        'Laptop.dc.html': ('<x-import component-from-global-scope="ExtronMach.Page" name="Laptop" kind="popup" '
                           'group="Sources" role="source"></x-import>'),
        'Help.dc.html': '<x-import component-from-global-scope="ExtronMach.Page" name="Help" kind="modal" role="help">',
        'Power Down.dc.html': ('<x-import component-from-global-scope="ExtronMach.Page" name="Power Down" '
                               'kind="modal" role="confirm" topic="power">'),
        'Notes.dc.html': '<x-import component-from-global-scope="ExtronMach.Page" name="Notes">',
    }

    def test_each_role_has_its_counterpart_in_each_familys_frame(self):
        p = designsys.load('mach')
        ms = designsys.models(p)
        bar = design.template_counterparts(ms['TLP1035T']['frame'])
        self.assertEqual(bar['page'], ('Main SD', None))
        self.assertEqual(bar['source'], ('Laptop', 'Main SD'))
        self.assertEqual(bar['help'], ('Help', 'Main SD'))
        self.assertEqual(bar['confirm'], ('Confirmation', 'Main SD'))
        self.assertEqual(bar['wait'], ('Powering Down', 'Main SD'))
        self.assertEqual(bar['settings'], ('Display Settings', 'Main SD'))
        hub = design.template_counterparts(ms['TLP525T']['frame'])
        self.assertEqual(hub['page'], ('Main Page', None))
        self.assertEqual(hub['source'], ('Laptop', 'Main Page'))
        self.assertEqual(hub['settings'], ('Settings', 'Main Page'))
        small = design.template_counterparts(ms['TLP320M']['frame'])
        self.assertEqual(small['page'], ('Main', None))
        self.assertEqual(small['source'], ('Doc Cam 1', None))
        self.assertEqual(small['confirm'], ('Confirmation', None))

    def test_a_source_or_window_is_set_beside_the_seeds_own_of_its_name(self):
        """The canvas's PC beside the seed's PC, its DocCam beside Doc Cam,
        its Lighting window beside Lighting Settings, a 320's source beside its
        first page; else the frame's own."""
        class Built:
            by_name = {n: {} for n in ('PC', 'Doc Cam', 'Doc Cam 1', 'Doc Cam 2', 'Lighting Settings', 'Laptop')}
        self.assertEqual(design._same_name(Built, 'PC'), 'PC')
        self.assertEqual(design._same_name(Built, 'DocCam', 'Document Camera'), 'Doc Cam')
        self.assertEqual(design._same_name(Built, 'Lighting'), 'Lighting Settings')
        self.assertIsNone(design._same_name(Built, 'Streaming', None))

    def test_an_artboard_says_its_role(self):
        self.assertEqual(design.board_role(self.BOARDS['Main.dc.html']), 'page')
        self.assertEqual(design.board_role(self.BOARDS['Laptop.dc.html']), 'source')
        self.assertEqual(design.board_role(self.BOARDS['Power Down.dc.html']), 'confirm')
        self.assertIsNone(design.board_role(self.BOARDS['Notes.dc.html']))

    def _critique(self, built=None):
        """compare_template on a Mach canvas of BOARDS for the 1035 and the
        525, Chrome stood in for and the seeds real; `built` stands in for
        gdl.design._Built. Returns (out dir, pairs) and leaves the caller's
        compose.BINARY, a sentinel, to be checked."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow not installed')
        from _corpus import usable
        for s in ('Mach 1035.gdl', 'Mach 525.gdl'):
            if not usable(os.path.join(HERE, '..', 'seeds', s)):
                self.skipTest('seeds not present (git lfs pull)')
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        canvas = os.path.join(d, 'canvas')
        os.makedirs(canvas)
        with open(os.path.join(canvas, 'canvas.json'), 'w', encoding='utf-8') as fh:
            json.dump({'title': 'Room', 'order': list(self.BOARDS),
                       'boards': {b: {'w': 1280, 'h': 800} for b in self.BOARDS}}, fh)
        for b, body in self.BOARDS.items():
            with open(os.path.join(canvas, b), 'w', encoding='utf-8') as fh:
                fh.write(f'<html><head></head><body>{body}</body></html>')

        def fake_render(path, chrome, size, timeout=90, panel=None):
            name = os.path.basename(path).rsplit('.dc.html', 1)[0]
            m = panel or 'TLP1035T'
            return {'page': {'gdl': json.dumps({'kind': 'page', 'name': name, 'template': 'Mach',
                                                'panels': ['TLP1035T', 'TLP525T'], 'panel': m,
                                                'size': [1280, 800] if m == 'TLP1035T' else [800, 480]})},
                    'controls': [], 'stray': [], 'errors': [], 'parts': []}

        def fake_shot(path, chrome, size, png, timeout=90):
            Image.new('RGB', tuple(size), (20, 20, 20)).save(png)

        from gdl import compose
        saved = design.render, design.screenshot, design.find_chrome, design._Built, compose.BINARY
        design.render, design.screenshot = fake_render, fake_shot
        design.find_chrome = lambda given=None: 'chrome'
        if built:
            design._Built = built
        # A caller's compositing rule outlives the critique, whichever it was.
        compose.BINARY = 'the callers'
        try:
            try:
                return d, design.compare_template(canvas, os.path.join(d, 'critique'))
            finally:
                self.binary = compose.BINARY
        finally:
            design.render, design.screenshot, design.find_chrome, design._Built, compose.BINARY = saved

    def test_a_sheet_per_canvas_each_artboard_beside_the_templates_page(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow is not here: the sheet is drawn with gdl.compose')
        d, pairs = self._critique()
        self.assertEqual(self.binary, 'the callers')
        with open(os.path.join(d, 'critique', 'index.html'), encoding='utf-8') as fh:
            page = fh.read()
        self.assertEqual(page.count('<section class="panel">'), 2)
        got = {(m, board): seed_page for m, board, seed_page in pairs}
        self.assertEqual(got[('TLP1035T', 'Main')], 'Main SD')
        self.assertEqual(got[('TLP525T', 'Main')], 'Main Page')
        self.assertEqual(got[('TLP1035T', 'Laptop')], 'Laptop')
        self.assertEqual(got[('TLP1035T', 'Help')], 'Help')
        self.assertEqual(got[('TLP1035T', 'Power Down')], 'Confirmation')
        self.assertIsNone(got[('TLP1035T', 'Notes')])
        self.assertIn('seeds/Mach 1035.gdl', page)
        # The template side is drawn: the seed's own page, not a blank, for
        # the working page, a source and each window - and none for a page
        # the template has no counterpart for.
        for m, stem in (('TLP1035T', 'Main'), ('TLP525T', 'Main'), ('TLP1035T', 'Laptop'),
                        ('TLP1035T', 'Help'), ('TLP1035T', 'Power_Down')):
            png = os.path.join(d, 'critique', m, f'{stem}-template.png')
            self.assertTrue(os.path.exists(png), (m, stem))
            with Image.open(png) as im:
                self.assertGreater(len(im.convert('RGB').getcolors(1 << 20) or ()), 50, (m, stem))
        self.assertFalse(os.path.exists(os.path.join(d, 'critique', 'TLP1035T', 'Notes-template.png')))
        self.assertIn('Main-template.png', page)
        with Image.open(os.path.join(d, 'critique', 'sheet.png')) as sheet:
            self.assertGreater(sheet.size[1], sheet.size[0])
            # The sheet's template column is not the design side's flat 20,20,20.
            right = sheet.convert('RGB').crop((sheet.size[0] // 2 + 12, 40, sheet.size[0] - 12, sheet.size[1] - 12))
            self.assertGreater(len(right.getcolors(1 << 20) or ()), 50)

    def test_the_critique_puts_the_compositing_rule_back_after_a_failure(self):
        """compare --template blends the template's translucent chrome
        (compose.BINARY off) and puts the rule back however a page ends: it
        was written True, whatever the caller had."""
        seen = []

        class Boom:
            def __init__(self, path):
                self.by_name = {n: {} for n in ('Main SD', 'Laptop', 'Help', 'Confirmation', 'Main Page')}

            def image(self, *a, **k):
                from gdl import compose
                seen.append(compose.BINARY)
                raise RuntimeError('boom')
        with self.assertRaises(RuntimeError):
            self._critique(built=Boom)
        self.assertEqual(seen, [False])
        self.assertEqual(self.binary, 'the callers')

    def test_the_command_line_takes_template(self):
        seen = []
        saved = design.compare_template
        design.compare_template = lambda folder, out, chrome=None: seen.append((folder, out)) or []
        try:
            self.assertEqual(design.main(['gdl.design', 'compare', 'canvasdir', '--template', 'outdir']), 0)
        finally:
            design.compare_template = saved
        self.assertEqual(seen, [('canvasdir', 'outdir')])


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


class TestTheRuntimePin(unittest.TestCase):
    """The Design type's runtime is the Design type's to change. A canvas
    whose runtime the suite has not passed on is refused by name, with what
    to do, until it is pinned (gdl/dc_runtime.json)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        pins = os.path.join(self.dir, 'dc_runtime.json')
        shutil.copy(design.RUNTIMES, pins)
        self.addCleanup(setattr, design, 'RUNTIMES', design.RUNTIMES)
        design.RUNTIMES = pins
        self.addCleanup(setattr, design, 'ARCHIVE', design.ARCHIVE)
        design.ARCHIVE = os.path.join(self.dir, 'archive', 'dc-runtime')
        os.makedirs(os.path.dirname(design.ARCHIVE))
        self.canvas = os.path.join(self.dir, 'canvas')
        os.makedirs(self.canvas)
        self.js = os.path.join(self.canvas, 'support.js')
        with open(self.js, 'w', encoding='utf-8') as fh:
            fh.write('/* a runtime no suite has passed on */')

    def test_an_unproven_runtime_is_refused_by_name(self):
        why = design.runtime_problem(self.canvas)
        self.assertIn(design.runtime_sha(self.js)[:12], why)
        self.assertIn('pin-runtime', why)
        self.assertEqual(design.main(['gdl.design', 'translate', self.canvas, os.path.join(self.dir, 'out')]), 1)

    def test_pinned_it_passes_and_is_kept(self):
        self.assertEqual(design.main(['gdl.design', 'pin-runtime', self.js, '--seen', 'a test']), 0)
        self.assertIsNone(design.runtime_problem(self.canvas))
        sha = design.runtime_sha(self.js)
        self.assertEqual(design.proven_runtimes()[sha]['seen'], 'a test')
        self.assertEqual(design.runtime_sha(os.path.join(design.ARCHIVE, sha[:16], 'dc-runtime.js')), sha)

    def test_the_sign_off_is_refused_on_it_too(self):
        self.assertEqual(design.main(['gdl.design', 'compare', self.canvas, 'built.gdl', self.dir]), 1)

    def test_pin_runtime_says_how_when_asked_wrong(self):
        for argv in (['pin-runtime'], ['pin-runtime', self.js], ['pin-runtime', self.js, '--seen'],
                     ['pin-runtime', '--seen', 'x', self.js], ['pin-runtime', 'no-such.js', '--seen', 'x']):
            with self.subTest(argv=argv):
                self.assertEqual(design.main(['gdl.design'] + argv), 2)

    def test_a_folder_with_no_runtime_is_not_this_checks_to_refuse(self):
        os.remove(self.js)
        self.assertIsNone(design.runtime_problem(self.canvas))

    @unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME), 'needs $GDL_DC_RUNTIME')
    def test_the_suites_own_runtime_is_pinned(self):
        """The canary for the suite: run it on a new runtime and this fails
        until that runtime is pinned - once the rest has passed on it."""
        self.assertIn(design.runtime_sha(RUNTIME), design.proven_runtimes(),
                      f'{RUNTIME} is not in gdl/dc_runtime.json: if every other test passed on it, '
                      'pin it with python -m gdl.design pin-runtime')


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
        (board, old, new), or a list of them, applied to that board first."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copytree(os.path.join(HERE, 'data', data), d, dirs_exist_ok=True)
        for edit in ([edit] if edit and isinstance(edit[0], str) else edit or []):
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

    def test_the_round_three_rooms_translate_for_the_320(self):
        """The round-three conference rooms, drawn by fresh designers for the
        1035 and the 525, translate for the 320 as well, against the one ID
        map: each page under its title strip, over as many pages as its rows
        need. A modal holds one screen, and Mach's and Shockwave's Help modals
        say more than the 320's holds; and Shockwave's and Turbulence's 320
        seeds have no date and time control to clone. Revised as their gates'
        words ask - Mach's AV desk said shorter, Shockwave's sources left to
        the tabs they name, the clock off the pages - the rooms translate."""
        def label(name, text, x, y, w, h=50):
            return (f'<x-import component-from-global-scope="ExtronShockwave.Label" name="{name}" type="body" '
                    f'align="left" color="text-secondary" style="position: absolute; left: {x}px; top: {y}px; '
                    f'width: {w}px; height: {h}px">{text}</x-import>')
        sw_clock = ('<x-import component-from-global-scope="ExtronShockwave.Clock" name="DateTime" format="time" '
                    'size="14" align="center" style="position: absolute; left: 740px; top: 720px; width: 220px; '
                    'height: 60px"></x-import>')
        tb_clock = ('<x-import component-from-global-scope="ExtronTurbulence.Clock" name="Clock" format="datetime" '
                    'type="body" align="center" style="position: absolute; left: 360px; top: 711px; width: 560px; '
                    'height: 64px"></x-import>')
        edits = {
            'mach': [('Help.dc.html', 'Call the AV desk at extension 4400.', 'AV desk: ext. 4400.')],
            'shockwave': [('Help.dc.html', label('Step2Sources1', 'Laptop, ShareLink (wireless),', 260, 380, 801), ''),
                          ('Help.dc.html', label('Step2Sources2', 'Room PC or Doc Camera.', 260, 430, 801), ''),
                          ('Help.dc.html', 'Call the AV desk: extension 4400', 'AV desk: ext. 4400'),
                          ('Main.dc.html', sw_clock, ''), ('Call.dc.html', sw_clock, '')],
            'turbulence': [('Main.dc.html', tb_clock, ''), ('Call.dc.html', tb_clock, '')],
        }
        for theme, edit in edits.items():
            with self.subTest(theme=theme):
                if not all(seeds.usable(f'seeds/{theme.title()} {s}.gdl') for s in ('1035', '525', '320')):
                    self.skipTest(f'the {theme} seeds are not here (git lfs pull)')
                if not designsys.kit_root(designsys.load(theme)):
                    self.skipTest(f"Extron's {theme} kit is not here")
                specs, problems, _ = self._translate_panels(theme, f'design-room-{theme}', edit=edit)
                self.assertEqual({m: p for m, p in problems.items() if p}, {})
                self.assertEqual(sorted(specs), ['TLP1035T', 'TLP320M', 'TLP525T'])
                small = specs['TLP320M']
                self.assertEqual((small['size'], small['_seed']), ([320, 240], f'seeds/{theme.title()} 320.gdl'))
                self.assertIn('Home 2', [pg['name'] for pg in small['pages']])

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

    def test_the_mach_region_canvas_translates_clean_for_the_1035_and_725(self):
        """The slice's Main page in regions (tests/data/design-regions-mach):
        clean on the 1035 and the 725 (and its hubs: _the_hubs_derive),
        the tabs, rail groups, Help and Power 1 px apart where Extron's own
        Main SD puts them, through every gate."""
        if not all(seeds.usable(f'seeds/Mach {s}.gdl') for s in ('1035', '725', '525', '535')):
            self.skipTest('the Mach seeds are not here (git lfs pull)')
        if not designsys.kit_root(designsys.load('mach')):
            self.skipTest("Extron's Mach kit is not here")
        specs, problems, notes = self._translate_panels('mach', 'design-regions-mach')
        self.assertEqual({m: p for m, p in problems.items() if p}, {})
        self.assertEqual(sorted(specs), sorted(_listed('mach').split()))
        self.assertFalse([n for ns in notes.values() for n in ns if 'has no' in n])
        main = {c['name']: c for c in specs['TLP1035T']['pages'][0]['controls']}
        self.assertEqual([main[n]['rect'] for n in ('PC', 'Laptop')], [[258, 0, 190, 64], [449, 0, 190, 64]])
        self.assertEqual([main[n]['rect'] for n in ('Help', 'Power')], [[1069, 745, 70, 55], [1140, 745, 140, 55]])
        # The fixed chrome keeps the template's seed IDs, Room Mode the mode
        # launcher's; the heading is no chrome a program drives.
        self.assertEqual([main[n]['id'] for n in ('Help', 'Power', 'Volume', 'Volume Mute', 'Room Mode')],
                         [8117, 8022, 8024, 8021, 8118])
        self.assertLess(main['Volume Heading']['id'], 2000)
        for m, spec in specs.items():
            self.assertEqual(Panel(spec).check(), [], m)

    def test_every_bar_themes_center_and_windows_translate_clean(self):
        """tests/data/design-regions-<theme>: the working page, its sources as
        role="source" popups, its settings, Help and power-down windows by
        role - clean on the 1035, the 725 and each hub of Mach, Shockwave
        and Turbulence. Each source popup is its own panel's popup region; the
        chrome the center and the windows derived is derived, with one ID on
        every panel, and Close and Cancel go nowhere by `nav`: back is the
        program's."""
        for theme in ('mach', 'shockwave', 'turbulence'):
            with self.subTest(theme=theme):
                p = designsys.load(theme)
                listed = _listed(theme).split()
                if not all(seeds.usable(f'seeds/{p["template"]} {m[3:-1]}.gdl') for m in listed):
                    self.skipTest(f'the {theme} seeds are not here (git lfs pull)')
                if not designsys.kit_root(p):
                    self.skipTest(f"Extron's {theme} kit is not here")
                specs, problems, notes = self._translate_panels(theme, f'design-regions-{theme}')
                self.assertEqual({m: q for m, q in problems.items() if q}, {})
                self.assertEqual(sorted(specs), sorted(listed))
                self.assertFalse([n for ns in notes.values() for n in ns if 'has no' in n])
                rows = designsys.models(p)
                self._the_chrome_keeps_its_seed_ids(specs, rows)
                self._the_hubs_derive(theme, specs, notes)
                self._the_320_derives(theme, specs, notes)
                ids = {}
                for m, spec in specs.items():
                    self.assertEqual(Panel(spec).check(), [], m)
                    if rows[m]['tier'] == 'C':
                        continue
                    pops = {q['name']: q for q in spec['popups']}
                    region = rows[m]['frame']['center']['region']
                    for name in ('Laptop', 'PC', 'Streaming', 'DocCam'):
                        self.assertEqual(pops[name]['size'], region[2:], (m, name))
                        self.assertEqual(pops[name]['group'], 'Sources', (m, name))
                    for q in spec['popups']:
                        for c in q['controls']:
                            if c.get('derived') and c.get('name'):
                                ids.setdefault((q['name'], c['name']), set()).add(c['id'])
                    confirm = {c['name']: c for c in pops['ConfirmPower']['controls']}
                    self.assertNotIn('nav', confirm['ConfirmPower Cancel'])
                    self.assertTrue(confirm['ConfirmPower Cancel']['derived'])
                    self.assertEqual(confirm['ConfirmPower Power Down']['does'], 'Powers the room down.')
                # One ID a derived control, on both panels.
                self.assertTrue(ids)
                self.assertEqual({k: v for k, v in ids.items() if len(v) != 1}, {})

    def _the_chrome_keeps_its_seed_ids(self, specs, rows):
        """The region page's fixed chrome - the Footer's Help, Power and mode
        launcher, the RightRail's Volume and Mute - has the 1035 template's
        seed IDs (its frame's `ids`) on every panel the canvas lists; a page's
        band steps over them. Where the template names its tabs by a twin
        (Shockwave's 1035), each tab's caption is a mirror under its glyph
        with the tab's ID, nav and states - and on no other panel."""
        seed = rows['TLP1035T']['frame']['ids']
        want = {'Help': seed['help'], 'Power': seed['power'], 'Volume': seed['volume'],
                'Volume Mute': seed['mute'], 'Room Mode': seed['mode']}
        for m, spec in specs.items():
            # Each page's own, so a later page that lost the seed shows.
            got = {(it['name'], c['name']): c['id'] for it in spec['pages'] + spec['popups']
                   for c in it['controls'] if c.get('name') in want and not c.get('derived')}
            self.assertTrue(got, m)
            self.assertEqual({k: want[k[1]] for k in got}, got, m)
            self.assertFalse([c for it in spec['pages'] + spec['popups'] for c in it['controls']
                              if '_seed_id' in c or '_mirror' in c], m)
        twins = (rows['TLP1035T']['frame']['top'].get('tabs') or {}).get('twin')
        for m, spec in specs.items():
            main = {c['name']: c for c in spec['pages'][0]['controls']}
            caps = [n for n in main if n.endswith(' Caption')]
            if not twins or m != 'TLP1035T':
                self.assertEqual(caps, [], m)
                continue
            for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming'):
                tab, cap = main[n], main[n + ' Caption']
                self.assertEqual((cap['id'], cap.get('nav'), cap['derived']), (tab['id'], tab.get('nav'), True), n)
                self.assertEqual([s['name'] if isinstance(s, dict) else s for s in cap['states']],
                                 [s['name'] if isinstance(s, dict) else s for s in tab['states']], n)
                self.assertEqual((tab.get('text', ''), cap['text']), ('', n), n)
                t, r = tab['rect'], cap['rect']
                self.assertEqual((r[0], r[2], r[1] + r[3]), (t[0], t[2], t[1] + t[3]), n)

    def _the_hubs_derive(self, theme, specs, notes):
        """The region canvas on each hub the canvas lists, as its template
        draws its working page: the menu bar's Up, Down and settings opener
        keep the hub's seed IDs, every canvas control the ID it has on the
        1035 - a source's tile its tab's, Help, Power, Mute and the volume
        level theirs - nothing dropped but the clock, which is named; the
        Select a Source grid, the settings and the sources popups of main's
        group, and Help a modal still."""
        rows = designsys.models(designsys.load(theme))
        big = specs['TLP1035T']
        main1035 = {c['name']: c for c in big['pages'][0]['controls']}
        hubs = [m for m in specs if rows[m]['frame'].get('select')]
        self.assertTrue(hubs, theme)
        for m in hubs:
            with self.subTest(theme=theme, hub=m):
                F, spec = rows[m]['frame'], specs[m]
                pops = {q['name']: q for q in spec['popups']}
                main = {c['name']: c for c in spec['pages'][0]['controls']}
                right = {x['role']: x for x in F['right']['items']}
                select = F['select']['popup'] or 'Select Source'
                grid = pops[select]
                self.assertEqual((grid['group'], grid['size'], grid['modal']),
                                 ('Sources', F['center']['region'][2:], False))
                tiles = {c['name']: c for c in grid['controls']}
                for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming', 'Help'):
                    self.assertEqual(tiles[n]['id'], main1035[n]['id'], n)
                    self.assertEqual(tiles[n].get('nav'), main1035[n].get('nav'), n)
                    self.assertFalse(tiles[n].get('derived'), n)
                for n in ('Volume Mute', 'Power'):
                    self.assertEqual(main[n]['id'], main1035[n]['id'], n)
                self.assertEqual([main['Volume Up']['id'], main['Volume Down']['id'], main[right['settings']['name']]['id']],
                                 [right['volume-up']['id'], right['volume-down']['id'], right['settings']['id']])
                level = {c['name']: c for c in pops['Volume Level']['controls']}['Volume']
                self.assertEqual((level['kind'], level['id']), ('level', main1035['Volume']['id']))
                self.assertNotIn('Date Time', main)
                self.assertTrue(any("Date Time is left off the " + m in n for n in notes[m]), notes[m])
                for name in ('Laptop', 'DocCam', 'Lighting', 'Audio'):
                    self.assertEqual((pops[name]['group'], pops[name]['modal'], pops[name]['size']),
                                     ('Sources', False, F['center']['region'][2:]), name)
                close = {c['name']: c for c in pops['Laptop']['controls']}['Laptop Close']
                self.assertEqual((close['nav'], close['derived']), (select, True))
                self.assertTrue(pops['Help']['modal'] and pops['ConfirmPower']['modal'])
                # The program shows the grid first, whatever the board order.
                self.assertEqual(grid.get('reached_by'), 'program')
                if theme == 'mach':
                    # Mach's settings popups are opaque #303030, in the spec too.
                    self.assertEqual([pops[n].get('background') for n in ('Settings', 'Display Settings',
                                                                           'Lighting', 'Audio')], ['page'] * 4)
        # The ID map over every panel: nothing dropped but what a hub's page
        # names as left off (its `left`), one ID one control.
        from gdl.idmap import IdMap, check_panels
        self.assertEqual(check_panels({m: IdMap(Panel(s)) for m, s in specs.items()}), [])

    def _the_320_derives(self, theme, specs, notes):
        """The region canvas on the 320, as its template draws its pages: Main
        the template's Select a Source, its source buttons the 1035's tabs -
        their IDs - and More on to pages of Main's own; each source, the
        question, Help and the settings a page; the volume's level in the
        template's modal, the 1035's Volume's ID; every Back back to the page
        that shows its page; nothing dropped but the clock and the Center's
        popup region, which are named."""
        rows = designsys.models(designsys.load(theme))
        M320 = 'TLP320M'
        self.assertIn(M320, specs)
        big = specs['TLP1035T']
        main1035 = {c['name']: c for c in big['pages'][0]['controls']}
        spec, F = specs[M320], rows[M320]['frame']
        pages = {q['name']: q for q in spec['pages']}
        pops = {q['name']: q for q in spec['popups']}
        for n in ('Main', 'Main 2', 'Laptop', 'PC', 'Streaming', 'DocCam', 'DocCam 2', 'Lighting', 'Audio', 'Help',
                  'ConfirmPower'):
            self.assertIn(n, pages, n)
        self.assertEqual(spec['start_page'], 'Main')
        self.assertEqual(sorted(pages['Main']['left']), ['Controls', 'Date Time'])
        main = {c['name']: c for c in pages['Main']['controls']}
        for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming'):
            self.assertEqual((main[n]['id'], main[n]['nav']), (main1035[n]['id'], main1035[n]['nav']), n)
        on = {c['name']: (q['name'], c) for q in spec['pages'] + spec['popups'] for c in q['controls']}
        for n in ('Help', 'Power', 'Volume Mute', 'Volume', 'Display On', 'Lighting Settings', 'Room Mode'):
            self.assertEqual(on[n][1]['id'], main1035[n]['id'], n)
        V = F['volume']
        vol = pops[V['popup']]
        self.assertEqual((vol['modal'], vol.get('reached_by')), (True, 'program'))
        self.assertEqual(on['Volume'][1]['kind'], 'level')
        # Every Back goes back to the page that shows its page - a source's
        # first page's too where it runs over two: its later page leads back
        # to it but does not show it.
        self.assertEqual(on['Laptop Back'][1]['nav'], 'Main')
        self.assertEqual(on['DocCam Back'][1]['nav'], 'Main')
        self.assertEqual(on['DocCam 2 Back'][1]['nav'], 'DocCam')
        self.assertFalse([n for n in notes[M320] if 'goes back where the program says' in n], notes[M320])
        # The Volume modal's glyphs keep the template's seed IDs; its strip's
        # measured #4B4B4C (Mach) is the template's, exempt from the cap.
        vol_on = {c['name']: c for c in vol['controls']}
        self.assertEqual([vol_on[n]['id'] for n in ('Volume Up Label', 'Volume Down Label')], [7023, 7026])
        # The empty state a label a line: the first source page's carries the
        # template's seed IDs, the rest from 50001.
        self.assertEqual([on[f'Laptop Empty{s}'][1]['kind'] for s in ('', ' 2', ' 3')], ['label'] * 3)
        self.assertEqual(on['Help Back'][1]['nav'], on['Help'][0])
        self.assertEqual(on['Lighting Back'][1]['nav'], on['Lighting Settings'][0])
        self.assertEqual(on['ConfirmPower Cancel'][1]['nav'], on['Power'][0])
        for q in spec['pages'] + spec['popups']:
            for c in q['controls']:
                self.assertNotIn('back', c, (q['name'], c.get('name')))
        self.assertTrue(any(f'Date Time is left off the {M320}' in n for n in notes[M320]), notes[M320])

    def test_a_hub_takes_the_centers_group_and_shows_its_grid_first(self):
        """A canvas whose Center and source popups say group="Room", its
        Laptop board standing before Main's: on the 525 the settings popups
        go in Room too, as Select a Source does, and the program still shows
        Select a Source first. With no working page at all, a source popup on
        a hub is named for what it lacks - the Select a Source a region page
        derives - not for a nav to nothing."""
        theme = 'shockwave'
        p = designsys.load(theme)
        if not all(seeds.usable(f'seeds/{p["template"]} {s}.gdl') for s in ('1035', '525')):
            self.skipTest('the Shockwave seeds are not here (git lfs pull)')
        if not designsys.kit_root(p):
            self.skipTest("Extron's Shockwave kit is not here")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        region_canvas(theme, d, panels=('TLP1035T', 'TLP525T'))
        for n in os.listdir(d):
            if n.endswith('.dc.html'):
                path = os.path.join(d, n)
                with open(path, encoding='utf-8') as fh:
                    src = fh.read()
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(src.replace('group="Sources"', 'group="Room"'))
        with open(os.path.join(d, 'canvas.json'), encoding='utf-8') as fh:
            idx = json.load(fh)
        idx['order'] = ['Laptop.dc.html'] + [b for b in idx.get('order') or idx['boards'] if b != 'Laptop.dc.html']
        with open(os.path.join(d, 'canvas.json'), 'w', encoding='utf-8') as fh:
            json.dump(idx, fh)
        _stage(d, theme)
        canvas = design.Canvas(d)
        self.assertEqual(canvas.boards()[0], 'Laptop.dc.html')
        specs, problems, _ = canvas.translate_panels()
        self.assertEqual({m: q for m, q in problems.items() if q}, {})
        pops = {q['name']: q for q in specs['TLP525T']['popups']}
        self.assertEqual({n: pops[n]['group'] for n in ('Select Source', 'Laptop', 'Lighting', 'Audio',
                                                         'More Options', 'Display Control')},
                         dict.fromkeys(('Select Source', 'Laptop', 'Lighting', 'Audio', 'More Options',
                                        'Display Control'), 'Room'))
        self.assertEqual([n for n, q in pops.items() if q.get('reached_by') == 'program'],
                         ['Select Source', 'Volume Level'])
        # No working page: the hub has nowhere to show its sources from.
        os.remove(os.path.join(d, 'Main.dc.html'))
        idx['order'] = [b for b in idx['order'] if b != 'Main.dc.html']
        idx['boards'].pop('Main.dc.html')
        with open(os.path.join(d, 'canvas.json'), 'w', encoding='utf-8') as fh:
            json.dump(idx, fh)
        _, problems, _ = design.Canvas(d).translate_panels()
        self.assertIn("TLP525T: 'Laptop' is a source popup, which a TLP525T shows in main from the 'Select Source' a region "
                      'page derives there - draw a working page with a Center (and its Header) on the canvas',
                      problems['TLP525T'])
        self.assertFalse([q for q in problems['TLP525T'] if 'is not a page or popup' in q], problems['TLP525T'])

    def test_the_hand_laid_slice_translates_clean(self):
        """tests/data/design-slice-mach: Mach's working page laid by hand at
        the measured 1220 frame with the components there were before the
        regions - built in GUI Designer and verified, region for region
        beside Extron's own Main SD, and the source of mach.json's `regions`
        looks. Its deviations were the gates': tabs and rail buttons 12 px
        apart where the template draws 1, the slider 54 wide, Help clear of
        Power. The region canvas is held to it (TestARegionPage)."""
        if not seeds.usable('seeds/Mach 1035.gdl'):
            self.skipTest('the Mach seed is not here (git lfs pull)')
        if not designsys.kit_root(designsys.load('mach')):
            self.skipTest("Extron's Mach kit is not here")
        specs, problems, _ = self._translate_panels('mach', 'design-slice-mach')
        self.assertEqual({m: q for m, q in problems.items() if q}, {})
        self.assertEqual(sorted(specs), ['TLP1035T'])
        main = {c['name']: c for c in specs['TLP1035T']['pages'][0]['controls']}
        self.assertEqual([main[n]['rect'] for n in ('PC', 'Laptop')], [[258, 0, 182, 64], [452, 0, 182, 64]])
        self.assertEqual([main[n]['rect'] for n in ('Help', 'Power')], [[1058, 745, 70, 55], [1140, 745, 140, 55]])
        self.assertEqual(Panel(specs['TLP1035T']).check(), [])

    def _translate_regions(self, theme, panels, edit=None):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        region_canvas(theme, d, panels, edit)
        _stage(d, theme)
        return design.Canvas(d).translate_panels()

    def test_every_bar_themes_region_page_translates_clean(self):
        """The region page with nothing but its regions' own chrome passes
        every gate on the 1035, the 725 and the 720 of Mach, Shockwave and
        Turbulence - and with the right rail's Audio Control where the
        template draws one. The volume stack is a rail group (owner's call
        2); a seam the template draws under 2 mm between two regions -
        Turbulence's last launcher 1 px from Help, Shockwave 725's Mute 10 px
        over Power - opens to the panel's gap."""
        for theme in ('mach', 'shockwave', 'turbulence'):
            for edit in (None, AUDIO_RAIL) if theme != 'mach' else (None,):
                # Shockwave stands Audio Control in the right rail on the
                # 1035's series only.
                panels = ('TLP1035T',) if edit and theme == 'shockwave' else ('TLP1035T', 'TLP725T', 'TLP720T')
                with self.subTest(theme=theme, audio=bool(edit)):
                    p = designsys.load(theme)
                    if not all(seeds.usable(f'seeds/{p["template"]} {m[3:-1]}.gdl') for m in panels):
                        self.skipTest(f'the {theme} seeds are not here (git lfs pull)')
                    if not designsys.kit_root(p):
                        self.skipTest(f"Extron's {theme} kit is not here")
                    specs, problems, notes = self._translate_regions(theme, panels, edit)
                    self.assertEqual({m: q for m, q in problems.items() if q}, {})
                    self.assertEqual(sorted(specs), sorted(panels))
                    self.assertFalse([n for ns in notes.values() for n in ns if 'has no' in n])
                    for m, spec in specs.items():
                        self.assertEqual(Panel(spec).check(), [], m)
                    if edit:
                        self.assertIn('Audio Control', {c['name'] for c in specs['TLP1035T']['pages'][0]['controls']})

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


def _overlaps(a, b):
    """Two rects share pixels."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


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
                # One (old, new) pair, or a tuple of them.
                for e in (edit if isinstance(edit[0], tuple) else (edit,)):
                    src = src.replace(*e)
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(src)
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


REGIONS_CANVAS = os.path.join(HERE, 'data', 'design-regions-mach')
NO_RIGHT_RAIL = ('<x-import component-from-global-scope="ExtronMach.RightRail"></x-import>', '')


def _legal(item):
    """A frame item's rect on its panel: the gate-legal one where models()
    grew it to that panel's touch minimum."""
    return item.get('legal') or item['rect']


AUDIO_RAIL = ('<x-import component-from-global-scope="{ns}.RightRail"></x-import>',
              '<x-import component-from-global-scope="{ns}.RightRail">'
              '<x-import component-from-global-scope="{ns}.Button" slot="audio" name="Audio Control" nav="Audio" '
              'does="Opens audio settings.">Audio</x-import></x-import>')


def region_canvas(theme, dest, panels=('TLP1035T', 'TLP725T'), edit=None):
    """tests/data/design-regions-<theme> written to `dest`: the working page
    in regions, its sources as role="source" popups and its windows by role,
    each control in the look its region, its well or its window gives it.
    Every Page lists `panels`; `edit` is (old, new) on Main, with `{ns}` for
    the namespace."""
    p = designsys.load(theme)
    ns = p['namespace']
    shutil.copytree(os.path.join(HERE, 'data', f'design-regions-{theme}'), dest, dirs_exist_ok=True)
    for name in os.listdir(dest):
        path = os.path.join(dest, name)
        if not name.endswith('.dc.html'):
            continue
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        text = re.sub(r'panels="[^"]*"', f'panels="{" ".join(panels)}"', text)
        if name == 'Main.dc.html' and edit:
            old, new = (e.replace('{ns}', ns) for e in edit)
            assert text.count(old) == 1, old
            text = text.replace(old, new)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
    return dest


def readme_room(theme, dest):
    """A canvas at `dest` of `theme`'s README example room: every
    `<stem>.dc.html` artboard of its *The working page*, as a designer would
    copy them, each at its Page's size."""
    p = designsys.load(theme)
    ns = p['namespace']
    section = designsys.readme(p).split('\n## The working page\n', 1)[1].split('\n## ', 1)[0]
    os.makedirs(dest, exist_ok=True)
    boards = {}
    for name, code in re.findall(r'`([^`]+)\.dc\.html`:\n\n```html\n(.*?)```', section, re.S):
        size = p['popup'] if 'kind="popup"' in code else p['size']
        code = code.replace(f'{ns}.Page" ', f'{ns}.Page" style="position: absolute; left: 0px; top: 0px; '
                            f'width: {size[0]}px; height: {size[1]}px" ', 1)
        boards[f'{name}.dc.html'] = {'w': size[0], 'h': size[1]}
        with open(os.path.join(dest, f'{name}.dc.html'), 'w', encoding='utf-8') as fh:
            fh.write('<html><head><script src="support.js"></script>'
                     f'<link rel="stylesheet" href="ds/{ns.lower()}/components/bundle.css">'
                     f'<script src="ds/{ns.lower()}/components/bundle.js"></script></head><body>'
                     f'<x-dc><div style="width: {size[0]}px; height: {size[1]}px; position: relative">{code}'
                     '</div></x-dc></body></html>')
    with open(os.path.join(dest, 'canvas.json'), 'w', encoding='utf-8') as fh:
        json.dump({'title': f'{theme} README room', 'order': list(boards), 'boards': boards}, fh)
    _stage(dest, theme)
    return boards


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTheReadmesRoomTranslates(unittest.TestCase):
    """Each README's example room - Start, the working page and every
    artboard it leads to - translates clean on every panel its Pages list:
    copied as written, it builds. Drawn snug, the presets and keys of the
    first version overlapped on the 725 and the 525, and the 320 refused
    Shockwave's Start clock (PR8 review). And its ID map checks clean across
    every panel, the gate a build stops at before GUI Designer: Afterburn's
    sources, shown from the 320's Sources pages, refused there."""

    def test_each_room_translates_on_every_panel_it_lists(self):
        for theme in designsys.TEMPLATES:
            with self.subTest(theme=theme):
                d = tempfile.mkdtemp()
                self.addCleanup(shutil.rmtree, d, True)
                boards = readme_room(theme, d)
                self.assertIn('Main.dc.html', boards)
                specs, problems, _ = design.Canvas(d).translate_panels()
                self.assertEqual({m: q for m, q in problems.items() if q}, {})
                listed = re.search(r'panels="([^"]+)"', open(os.path.join(d, 'Main.dc.html'),
                                                              encoding='utf-8').read()).group(1).split()
                self.assertEqual(sorted(specs), sorted(listed))
                out = os.path.join(d, 'specs')
                design.write_panels(specs, out)
                self.assertEqual(idmap.check_panels(idmap.load_panels(out)), [])


# Round four (docs/superpowers/specs/2026-10-22-region-frame-design.md, item
# 10): what each fresh designer's room, as they left it, is still refused
# for, panel by panel, once the toolkit's share was fixed
# (tests/data/round4-left.json) - each problem the designer's to fix, with
# its class and why: `readme`, a gap round four found in the README, which
# the README now tells them of; `limit`, one the README now tells them of too,
# behind which a toolkit limit stays open - named, third, by its heading in
# docs/ROADMAP.md; or `designer`, what no README could have prevented.
# Anything else a translation names is a regression; anything it no longer
# names is a fix to take out of the file, and a limit the ROADMAP no longer
# lists is one to reclass.
with open(os.path.join(HERE, 'data', 'round4-left.json'), encoding='utf-8') as _fh:
    ROUND4_LEFT = json.load(_fh)


class TestRoundFourLeft(unittest.TestCase):
    def test_each_problem_left_has_its_class_and_why(self):
        with open(os.path.join(os.path.dirname(HERE), 'docs', 'ROADMAP.md'), encoding='utf-8') as fh:
            roadmap = fh.read()
        for theme, left in ROUND4_LEFT.items():
            for q, (c, why, *limit) in left.items():
                self.assertIn(c, ('readme', 'limit', 'designer'), (theme, q))
                self.assertTrue(why, (theme, q))
                self.assertEqual(len(limit), c == 'limit', (theme, q))
                if limit:
                    self.assertIn(f'- **{limit[0]}**', roadmap, (theme, q))


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestRoundFourRooms(unittest.TestCase):
    """The round-four rooms (tests/data/round4-<theme>), drawn for a TLP1035T,
    725T, 525T and 320M by four fresh designers from one theme's README each,
    translated unchanged for every panel they list: what is refused is only
    what ROUND4_LEFT classes as theirs to fix. Their first translation
    refused Mach 19 times, Shockwave 27, Turbulence 35 and Afterburn 149."""

    def translate(self, theme, folder):
        """({panel: spec}, {panel: problems}) of tests/data/`folder`, drawn in `theme`."""
        p = designsys.load(theme)
        panels = ('TLP1035T', 'TLP725T', 'TLP525T', 'TLP320M')
        if not all(seeds.usable(f'seeds/{p["template"]} {m[3:-1]}.gdl') for m in panels):
            self.skipTest(f'the {theme} seeds are not here (git lfs pull)')
        if not designsys.kit_root(p):
            self.skipTest(f"Extron's {theme} kit is not here")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copytree(os.path.join(HERE, 'data', folder), d, dirs_exist_ok=True)
        _stage(d, theme)
        specs, problems, _ = design.Canvas(d).translate_panels()
        return specs, problems

    def left(self, theme):
        _, problems = self.translate(theme, f'round4-{theme}')
        return sorted(q for qs in problems.values() for q in qs)

    def check(self, theme):
        got = self.left(theme)
        self.assertEqual(sorted(ROUND4_LEFT[theme]), got)

    def test_mach(self):
        self.check('mach')

    def test_shockwave(self):
        self.check('shockwave')

    def test_turbulence(self):
        self.check('turbulence')

    def test_afterburn(self):
        self.check('afterburn')

    _revised = None

    def revised(self):
        """translate() of Afterburn's revision, once for the tests that read it."""
        if TestRoundFourRooms._revised is None:
            TestRoundFourRooms._revised = self.translate('afterburn', 'round4-afterburn-revised')
        return TestRoundFourRooms._revised

    def test_afterburns_revision_translates_clean(self):
        """Afterburn's designer revised the room three times from the
        translator's words and the README (tests/data/round4-afterburn-revised,
        their notes' Revision sections): the 320 still refused four, a heading
        each on Start and Call landing on the main area's control and the two
        overlaps that made - the toolkit's, which laid the page's own controls
        and the MainArea's out apart, each over the whole screen."""
        specs, problems = self.revised()
        self.assertEqual({m: q for m, q in problems.items() if q}, {})
        listed = re.search(r'panels="([^"]+)"', open(os.path.join(HERE, 'data', 'round4-afterburn-revised',
                                                                   'Main.dc.html'), encoding='utf-8').read())
        self.assertEqual(sorted(specs), sorted(listed.group(1).split()))

    def test_afterburns_revision_maps_clean_on_every_panel(self):
        """The ID map's check across every panel, as `python -m gdl.idmap
        write-panels` runs it over the translated specs - where the revision's
        Windows build stopped, before GUI Designer. On the 320 the sources'
        Group is pages of its own, and its buttons showed the Sources popups
        from pages with no reference to that group - only Main SD's popup
        region has one - so none would have appeared; nor could the 320's
        seed, which has no standard popup, have cloned them. There each
        source is a page of its own, as the 320's template draws it."""
        specs, _ = self.revised()
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        design.write_panels(specs, d)
        maps = idmap.load_panels(d)
        self.assertEqual(list(maps), list(specs))
        self.assertEqual(idmap.check_panels(maps), [])


def _stage(d, theme):
    """The runtime and `theme`'s bundle beside a canvas at `d`."""
    shutil.copy(RUNTIME, os.path.join(d, 'support.js'))
    p = designsys.load(theme)
    comps = os.path.join(d, 'ds', p['namespace'].lower(), 'components')
    os.makedirs(comps, exist_ok=True)
    with open(os.path.join(comps, 'bundle.js'), 'w', encoding='utf-8') as fh:
        fh.write(designsys.bundle(p, art=False))
    with open(os.path.join(comps, 'bundle.css'), 'w', encoding='utf-8') as fh:
        fh.write(designsys.BUNDLE_CSS)
    return p


def _gaps(ctl, model):
    """gdl.spec's 2 mm rule over the probe's touch targets, a joined set's
    own members exempt, and a mirror inside its control (a Shockwave tab's
    twin), which is pressed as that control: each pair under it, as
    'A / B: Npx'."""
    from gdl.spec import touch_minimums
    _, spacing = touch_minimums(model)
    touch = [(n, g, r) for n, (g, r, _) in ctl.items() if g.get('kind') in ('button', 'slider')
             and not g.get('mirror')]
    out = []
    for i, (an, ag, a) in enumerate(touch):
        for bn, bg, b in touch[i + 1:]:
            if ag.get('joined') and ag.get('joined') == bg.get('joined'):
                continue
            gx = max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]))
            gy = max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]))
            if (gx < 0 and gy < spacing) or (gy < 0 and gx < spacing):
                out.append(f'{an} / {bn}: {max(gx, gy)}px')
    return out


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestARegionPage(_Probe, unittest.TestCase):
    """A working page that names its regions - Header, LeftRail, RightRail,
    Footer, Center - is drawn as the panel's own template draws its working
    page: each region's band, slots and surfaces from that panel's series'
    measured frame (docs/superpowers/specs/2026-10-22-region-frame-design.md).
    The hand-laid slice (tests/data/design-slice-mach) had to stand its tabs
    and rail buttons 12 px apart, its slider 54 wide and its Help clear of
    Power; the regions put them where Extron's own Main SD does."""

    CANVAS = REGIONS_CANVAS
    THEME = 'mach'

    def frame(self, model):
        return designsys.models(designsys.load('mach'))[model]['frame']

    def test_the_1035_is_drawn_at_its_templates_own_rects(self):
        page, ctl, out = self.probe('Main.dc.html')
        self.assertEqual(page['panel'], 'TLP1035T')
        self.assertEqual(out['problems'], [])
        self.assertEqual(out.get('warnings'), [])
        F = self.frame('TLP1035T')
        tabs = F['top']['tabs']['items']
        for name, item in zip(('PC', 'Laptop', 'Doc Cam', 'Streaming'), tabs):
            self.assertEqual(ctl[name][1], item['rect'], name)
        display, settings = F['left']['groups']
        for name, item in zip(('Display On', 'Display Off', 'Display Mute'), display['buttons']):
            self.assertEqual(ctl[name][1], item['rect'], name)
        for name, item in zip(('Lighting Settings', 'Audio Settings'), settings['buttons']):
            self.assertEqual(ctl[name][1], item['rect'], name)
        for name, g in (('Display Heading', display), ('Settings Heading', settings)):
            self.assertEqual(ctl[name][1], g['heading']['rect'], name)
            self.assertEqual(ctl[name][0]['text'], g['heading']['text'])
        right = {i['role']: i for i in F['right']['items']}
        bottom = {i['role']: i for i in F['bottom']['items']}
        # The right rail, drawn by default with the seed's own IDs as the
        # translator's default (`seed_id`, pinned where free); the slider 30
        # wide in the template, grown to the 1035's touch minimum. The
        # heading is no chrome a program drives: it carries none.
        self.assertEqual(ctl['Volume Heading'][1], right['heading']['rect'])
        self.assertEqual(ctl['Volume Heading'][0]['text'], 'Volume')
        self.assertNotIn('seed_id', ctl['Volume Heading'][0])
        self.assertEqual(ctl['Volume'][1], _legal(right['volume']))
        self.assertEqual((ctl['Volume'][0]['kind'], ctl['Volume'][0]['seed_id']), ('slider', 8024))
        self.assertEqual(ctl['Volume Mute'][1], right['mute']['rect'])
        self.assertEqual(ctl['Volume Mute'][0]['seed_id'], 8021)
        self.assertNotIn('id', ctl['Volume Mute'][0])
        # The designer's own control in the mode slot keeps the launcher's.
        self.assertEqual(ctl['Room Mode'][0]['seed_id'], bottom['mode']['id'])
        # The footer: the mode slot, the clock in the template's pattern, and
        # Help and Power where the template puts them, 1 px apart.
        self.assertEqual(ctl['Room Mode'][1], bottom['mode']['rect'])
        self.assertEqual(ctl['Date Time'][1], bottom['clock']['rect'])
        self.assertEqual(ctl['Date Time'][0]['format'], 'MMMM dd, yyyy - h:mm tt')
        self.assertEqual(ctl['Help'][1], bottom['help']['rect'])
        self.assertEqual(ctl['Power'][1], bottom['power']['rect'])
        self.assertEqual((ctl['Help'][0]['seed_id'], ctl['Help'][0]['nav']), (8117, 'Help'))
        self.assertEqual((ctl['Power'][0]['seed_id'], ctl['Power'][0]['nav']), (8022, 'ConfirmPower'))
        # The center is the popup region its sources fill.
        self.assertEqual(ctl['Controls'][1], F['center']['region'])
        self.assertEqual((ctl['Controls'][0]['kind'], ctl['Controls'][0]['group']), ('popup_ref', 'Sources'))
        # The bars' surfaces, as derived Panels in the template's own fill.
        for name, rect in (('Header Left', [0, 0, 257, 64]), ('Header Right', [1022, 0, 258, 64]),
                           ('Footer Bar', [141, 745, 927, 55])):
            g, r, _ = ctl[name]
            self.assertEqual((g['kind'], r, g['fill'], g.get('derived')), ('panel', rect, 'shade', True), name)

    def test_a_tab_takes_the_templates_look_and_caption_alignment(self):
        """Mach's tab is a shade cell, shade-on when selected, its caption
        centred past the icon by leading spaces - as the frame measured."""
        _, ctl, _ = self.probe('Main.dc.html')
        g = ctl['Laptop'][0]
        self.assertEqual((g['fill'], g['border'], g.get('align', 'center')), ('shade', 'none', 'center'))
        self.assertEqual([s.get('fill') for s in g['states']][1], 'shade-on')
        self.assertEqual(g['text'], '    Laptop')

    def test_the_tab_row_and_each_rail_group_are_joined_sets(self):
        """Owner's call 2: a header tab row and a rail group are segmented
        sets, 1 px apart as the template draws them, so the gap rule passes
        over each set (gdl.spec's `joined`); unrelated controls keep 2 mm.
        The right rail's volume - heading, slider and Mute - is its rail
        group. In the footer only the cells the template stands together
        (Help and Power, 1 px apart) are a set; Room Mode, 929 px from Help,
        is in none."""
        _, ctl, _ = self.probe('Main.dc.html')
        joined = {n: ctl[n][0].get('joined') for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming', 'Display On',
                                                        'Display Off', 'Display Mute', 'Lighting Settings',
                                                        'Audio Settings', 'Volume', 'Volume Mute', 'Help', 'Power')}
        self.assertEqual(len({joined[n] for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming')}), 1)
        self.assertEqual(len({joined[n] for n in ('Display On', 'Display Off', 'Display Mute')}), 1)
        self.assertEqual(len({joined[n] for n in ('Lighting Settings', 'Audio Settings')}), 1)
        self.assertEqual(joined['Volume'], joined['Volume Mute'])
        self.assertEqual(joined['Help'], joined['Power'])
        self.assertEqual(len({joined[n] for n in ('PC', 'Display On', 'Lighting Settings', 'Volume', 'Help')}), 5)
        self.assertTrue(all(joined.values()), joined)
        self.assertIsNone(ctl['Room Mode'][0].get('joined'))
        # 1 px apart, as Extron draws them.
        pc, laptop = ctl['PC'][1], ctl['Laptop'][1]
        self.assertEqual(laptop[0] - (pc[0] + pc[2]), 1)
        on, off = ctl['Display On'][1], ctl['Display Off'][1]
        self.assertEqual(off[1] - (on[1] + on[3]), 1)

    def test_a_designers_title_cannot_join_a_regions_set(self):
        """A region's sets are named apart from anything a designer titles: a
        Section called Header stays a set of its own, not one with the tabs
        that the gap rule would pass over."""
        _, ctl, out = self.probe('Main.dc.html', edit=('title="Settings"', 'title="Header"'))
        self.assertEqual(out['problems'], [])
        self.assertNotEqual(ctl['Lighting Settings'][0]['joined'], ctl['PC'][0]['joined'])
        self.assertEqual(ctl['Header Heading'][0]['text'], 'Header')

    def test_the_rail_and_the_mode_take_the_templates_look(self):
        """The canvas writes no variant on its rail buttons or Room Mode: the
        regions give them Mach's own - the rail's `solid` shade buttons, the
        footer's `footer` cell - where the default ghost's white wash read
        white on white over the sky."""
        _, ctl, _ = self.probe('Main.dc.html')
        for n in ('Display On', 'Display Off', 'Display Mute', 'Lighting Settings', 'Audio Settings'):
            self.assertEqual((ctl[n][0]['variant'], ctl[n][0]['fill']), ('solid', 'shade'), n)
        self.assertEqual((ctl['Room Mode'][0]['variant'], ctl['Room Mode'][0]['fill']), ('footer', 'shade'))
        # A designer's own look still wins.
        _, ctl, _ = self.probe('Main.dc.html', edit=('name="Display On"', 'name="Display On" variant="ghost"'))
        self.assertEqual(ctl['Display On'][0]['variant'], 'ghost')

    def test_a_long_tab_caption_clears_its_icon(self):
        """Mach centres a tab's caption past its icon with leading spaces. At
        the 725's and 720's type floor four spaces ran Streaming into its
        glyph: the caption takes as many as clear the icon the kit draws
        there (its reach, `kit.icon_right`), and its tab grows where they and
        the caption do not fit - by the build's own Open Sans."""
        from gdl import fonts, sfnt
        p = designsys.load('mach')
        adv = sfnt.Advances(fonts.face_path(p['font']['family'], 0))
        aw, ah = 1376, 440
        reach = p['kit']['icon_right'][f'{aw}x{ah}']
        for model in ('TLP1035T', 'TLP725T', 'TLP720T'):
            _, ctl, out = self.probe('Main.dc.html', model)
            self.assertEqual(out['problems'], [], model)
            widths = set()
            for name in ('PC', 'Laptop', 'Doc Cam', 'Streaming'):
                g, (x, y, w, h), over = ctl[name]
                widths.add(w)
                px = g['size'] * p['pt']
                caption = g['text'].lstrip(' ')
                spaces = len(g['text']) - len(caption)
                s = min(w / aw, h / ah)
                icon = (w - aw * s) / 2 + reach * aw * s
                start = (w - adv.length(g['text'], px)) / 2 + adv.length(' ' * spaces, px)
                self.assertGreaterEqual(start, icon, (model, name, g['text'], w))
                self.assertLessEqual(start + adv.length(caption, px), w, (model, name))
                self.assertGreaterEqual(spaces, 4, (model, name))
            # One row of tabs, one width.
            self.assertEqual(len(widths), 1, (model, widths))

    def test_a_rail_column_stays_one_width(self):
        """A caption that needs more than its slot on the 720 grows every
        button of the column with it, as the template's column is one width:
        Lighting alone came out 92 wide among 80s."""
        _, ctl, out = self.probe('Main.dc.html', 'TLP720T')
        self.assertEqual(out['problems'], [])
        cells = [ctl[n][1] for n in ('Display On', 'Display Off', 'Display Mute', 'Lighting Settings',
                                     'Audio Settings')]
        self.assertEqual(len({(r[0], r[2]) for r in cells}), 1, cells)
        F = self.frame('TLP720T')['left']['groups'][0]['buttons'][0]['rect']
        self.assertAlmostEqual(cells[0][0] + cells[0][2] / 2, F[0] + F[2] / 2, delta=1)

    def test_the_725_is_drawn_at_its_own_templates_rects(self):
        """The 725's bars from the 725's template, not the 1035's scaled."""
        page, ctl, out = self.probe('Main.dc.html', 'TLP725T')
        self.assertEqual((page['panel'], page['size']), ('TLP725T', [1024, 600]))
        self.assertEqual(out['problems'], [])
        F, touch = self.frame('TLP725T'), designsys.models(designsys.load('mach'))['TLP725T']['touch']
        for name, item in zip(('PC', 'Laptop', 'Doc Cam', 'Streaming'), F['top']['tabs']['items']):
            self.assertEqual(ctl[name][1], item['rect'], name)
        display, settings = F['left']['groups']
        for names, g in ((('Display On', 'Display Off', 'Display Mute'), display),
                         (('Lighting Settings', 'Audio Settings'), settings)):
            for name, item in zip(names, g['buttons']):
                x, y, w, h = ctl[name][1]
                # Down the template's own pitch; across, centred on its slot
                # and grown only where a caption at the 725's type floor needs it.
                self.assertEqual((y, h), (item['rect'][1], item['rect'][3]), name)
                self.assertAlmostEqual(x + w / 2, item['rect'][0] + item['rect'][2] / 2, delta=1)
                self.assertGreaterEqual(w, item['rect'][2])
        right = {i['role']: i for i in F['right']['items']}
        bottom = {i['role']: i for i in F['bottom']['items']}
        self.assertEqual(ctl['Volume'][1], _legal(right['volume']))
        self.assertEqual(ctl['Volume Mute'][1], right['mute']['rect'])
        self.assertEqual(ctl['Power'][1], _legal(bottom['power']))
        # Help grows to the 725's touch minimum, and to its caption at the
        # type floor, away from Power: its seam with Power stays 1 px.
        help_, power = ctl['Help'][1], ctl['Power'][1]
        self.assertEqual(power[0] - (help_[0] + help_[2]), 1)
        self.assertEqual((help_[1], help_[3]), (600 - touch, touch))
        self.assertGreaterEqual(help_[2], touch)
        # The popup region: the 725's own, which its source popups
        # (role="source") are sized to.
        self.assertEqual(ctl['Controls'][1], F['center']['region'])
        self.assertEqual(ctl['Header Right'][1], [818, 0, 206, 60])
        # The footer strip keeps the template's 1 px seams to the cells
        # either side as they grew - Room Mode to its caption, Help and Power
        # to the 725's 60 px - and is as deep as they are: one flat band,
        # no cell over it.
        bar, mode = ctl['Footer Bar'][1], ctl['Room Mode'][1]
        self.assertEqual(bar[0], mode[0] + mode[2] + 1)
        self.assertEqual(bar[0] + bar[2], help_[0] - 1)
        self.assertEqual((bar[1], bar[3]), (help_[1], help_[3]))
        for n in ('Room Mode', 'Help', 'Power'):
            self.assertFalse(_overlaps(ctl[n][1], bar), n)
        # A heading keeps its slot's middle, as deep as a line at the floor.
        x, y, w, h = ctl['Display Heading'][1]
        r = display['heading']['rect']
        self.assertEqual((x, w), (r[0], r[2]))
        self.assertAlmostEqual(y + h / 2, r[1] + r[3] / 2, delta=1)
        self.assertGreaterEqual(h, r[3])

    def test_a_rail_group_grown_to_a_panels_touch_minimum_moves_on_down(self):
        """The 835 shares the 1035's series and template, at a 67 px touch
        minimum: Mach's 60 px rail buttons, 61 apart, grow to 67 and stand
        68 apart from the group's first place - still one set, 1 px apart -
        rather than into each other."""
        _, ctl, out = self.probe('Main.dc.html', 'TLP835T')
        self.assertEqual(out['problems'], [])
        touch = designsys.models(designsys.load('mach'))['TLP835T']['touch']
        first = self.frame('TLP835T')['left']['groups'][0]['buttons'][0]['rect']
        on, off, mute = (ctl[n][1] for n in ('Display On', 'Display Off', 'Display Mute'))
        self.assertEqual(on[1], first[1])
        self.assertEqual([b[3] for b in (on, off, mute)], [touch] * 3)
        self.assertEqual([off[1] - (on[1] + on[3]), mute[1] - (off[1] + off[3])], [1, 1])

    def test_fewer_tabs_take_the_first_slots_and_the_header_closes_up(self):
        tab = next(line for line in open(os.path.join(REGIONS_CANVAS, 'Main.dc.html'), encoding='utf-8')
                   if 'name="Streaming"' in line)
        _, ctl, out = self.probe('Main.dc.html', edit=(tab, ''))
        self.assertEqual(out['problems'], [])
        F = self.frame('TLP1035T')
        self.assertNotIn('Streaming', ctl)
        self.assertEqual(ctl['Doc Cam'][1], F['top']['tabs']['items'][2]['rect'])
        self.assertEqual(ctl['Header Right'][1], [831, 0, 449, 64])

    def test_more_tabs_continue_the_pitch(self):
        tab = next(line for line in open(os.path.join(REGIONS_CANVAS, 'Main.dc.html'), encoding='utf-8')
                   if 'name="Streaming"' in line)
        more = tab + tab.replace('name="Streaming"', 'name="Room PC"').replace('>Streaming<', '>Room PC<')
        _, ctl, out = self.probe('Main.dc.html', edit=(tab, more))
        self.assertEqual(out['problems'], [])
        self.assertEqual(ctl['Room PC'][1], [1022, 0, 190, 64])
        self.assertEqual(ctl['Header Right'][1], [1213, 0, 67, 64])

    def test_a_childs_slot_overrides_the_default(self):
        """The designer's own control in a slot wins over the default there."""
        mine = ('<x-import component-from-global-scope="ExtronMach.RightRail">'
                '<x-import component-from-global-scope="ExtronMach.Button" slot="mute" name="Program Mute" '
                'variant="solid" does="Mutes the program.">Mute</x-import></x-import>')
        _, ctl, out = self.probe('Main.dc.html', edit=(NO_RIGHT_RAIL[0], mine))
        self.assertEqual(out['problems'], [])
        self.assertNotIn('Volume Mute', ctl)
        mute = {i['role']: i for i in self.frame('TLP1035T')['right']['items']}['mute']
        self.assertEqual(ctl['Program Mute'][1], mute['rect'])
        self.assertIn('Volume', ctl)

    def test_a_missing_region_warns_and_does_not_refuse(self):
        """Owner's call 4: named on the canvas and in the translate report,
        never refused."""
        _, ctl, out = self.probe('Main.dc.html', edit=NO_RIGHT_RAIL)
        self.assertEqual(out['problems'], [])
        self.assertEqual(out['warnings'], ['Main has no RightRail - the Mach working page always draws one'])
        self.assertNotIn('Volume', ctl)

    def test_a_splash_page_is_exempt(self):
        page = 'start="true"'
        _, _, out = self.probe('Main.dc.html', edit=(NO_RIGHT_RAIL, (page, page + ' splash="true"')))
        self.assertEqual((out['problems'], out['warnings']), ([], []))

    def test_the_300_is_refused_by_name_for_now(self):
        """A hub draws the region page in its own grammar (_HubProbe), and the
        320 in its own (_PagesProbe); the 300's menu bar is not drawn yet."""
        _, _, out = self.probe('Main.dc.html', 'TLP300M')
        self.assertIn('Main uses the region frame, which the TLP300M does not draw yet', out['problems'])
        for m in ('TLP525T', 'TLP320M'):
            _, _, out = self.probe('Main.dc.html', m)
            self.assertEqual(out['problems'], [], m)

    def test_a_second_of_one_region_is_named(self):
        """A working page has one of each region: a second is named, and draws
        nothing over the first."""
        rail = NO_RIGHT_RAIL[0]
        _, _, out = self.probe('Main.dc.html', edit=(rail, rail + rail))
        self.assertEqual(out['problems'], ['Main holds more than one RightRail - a working page has one of each'])
        names = [json.loads(c['gdl']).get('name') for c in out['controls']]
        self.assertEqual(names.count('Volume'), 1)

    def test_a_turned_panel_is_refused_by_name_for_now(self):
        """A turned panel's frame turns the header into a left band: not drawn
        yet, and said so rather than drawn upright."""
        _, _, out = self.probe('Main.dc.html', 'TLP1035M-Portrait')
        self.assertIn('Main uses the region frame, which the TLP1035M-Portrait does not draw yet', out['problems'])

    def test_a_region_on_a_popup_is_refused(self):
        """The regions are a working page's: a popup or a modal holding one is
        named, and its regions draw nothing."""
        for kind in ('popup', 'modal'):
            with self.subTest(kind=kind):
                _, ctl, out = self.probe('Main.dc.html', edit=('start="true"', f'kind="{kind}"'))
                self.assertIn(f"Main is a {kind} and holds a Header - the regions are a working page's",
                              out['problems'])
                self.assertNotIn('Help', ctl)

    def test_a_page_with_no_region_is_untouched(self):
        """A popup with no region and no role: no warning, and every control
        where it was drawn."""
        page, ctl, out = self.probe('DocCam.dc.html', edit=(' role="source"', ''))
        self.assertEqual((out['problems'], out.get('warnings')), ([], []))
        self.assertEqual(ctl['Inputs Heading'][1], [187, 160, 103, 40])
        self.assertNotIn('DocCam Title', ctl)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTheRegionPreviews(unittest.TestCase):
    """Each region's card in the design system draws its region, not a
    complaint: its Page holds the region directly, with no x-import host
    round it, and is a region page all the same."""

    def card(self, theme, html):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        _stage(d, theme)
        p = designsys.load(theme)
        path = os.path.join(d, 'card.html')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(html.replace('<head>', '<head><script src="support.js"></script>'
                                  f'<script src="ds/{p["namespace"].lower()}/components/bundle.js"></script>', 1))
        return design.render(path, design.find_chrome(), (1280, 800))

    def test_each_card_draws_its_region(self):
        want = {'Header': 'Laptop', 'LeftRail': 'Display On', 'Section': 'Display On', 'RightRail': 'Volume',
                'Footer': 'Help', 'Center': 'Controls'}
        for theme in ('mach', 'shockwave', 'turbulence'):
            cards = designsys.previews(designsys.load(theme))
            for n, name in want.items():
                with self.subTest(theme=theme, card=n):
                    out = self.card(theme, cards[n])
                    self.assertEqual((out['problems'], out['warnings'], out['errors']), ([], [], []))
                    self.assertIn(name, [json.loads(c['gdl']).get('name') for c in out['controls']])

    def test_afterburn_has_no_regions(self):
        """Afterburn's chrome is its background art: its system exports none."""
        out = self.card('afterburn', '<!doctype html><html><head></head><body><div id="r"></div><script>'
                        'var N = window.ExtronAfterburn; document.getElementById("r").setAttribute('
                        '"data-gdl-problem", ["Header", "LeftRail", "Section", "RightRail", "Footer", "Center"]'
                        '.filter(function (n) { return N[n]; }).join(" ") || "none");</script></body></html>')
        self.assertEqual(out['problems'], ['none'])


class _RegionProbe(_Probe):
    """The region canvas drawn in another bar theme (region_canvas)."""

    PANELS = ('TLP1035T', 'TLP725T', 'TLP720T')

    @classmethod
    def setUpClass(cls):
        src = tempfile.mkdtemp()
        try:
            cls.CANVAS = region_canvas(cls.THEME, os.path.join(src, 'canvas'), cls.PANELS)
            super().setUpClass()
        finally:
            shutil.rmtree(src, ignore_errors=True)

    def frame(self, model):
        return designsys.models(designsys.load(self.THEME))[model]['frame']

    def image(self, g, i=0):
        """The kit file a probed button draws in its state `i`."""
        return (g.get('states') or [{}])[i].get('image') or ''


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestShockwavesRegionPage(_RegionProbe, unittest.TestCase):
    """The region page on Shockwave, whose canvas names no look of its own:
    each control comes out in the look the template draws it in."""

    THEME = 'shockwave'

    def test_each_control_takes_the_templates_look(self):
        """The profile's own measured looks: the rail's `button`s, the
        launchers' `tile`s, a `wide` gray_round Room Mode, a gray `square`
        Mute that lights red, a yellow `pill` Help and a red `pill` Power
        captioned Off - not the default button with a caption - each lit in
        its family's caption (the truth ledger, shockwave-08 and -20)."""
        _, ctl, out = self.probe('Main.dc.html')
        self.assertEqual(out['problems'], [])
        looks = {n: (ctl[n][0]['variant'], ctl[n][0].get('text')) for n in ctl
                 if ctl[n][0].get('kind') == 'button'}
        for n in ('Display On', 'Display Off', 'Display Mute'):
            self.assertEqual(looks[n][0], 'button', n)
        for n in ('Lighting Settings', 'Audio Settings'):
            self.assertEqual(looks[n][0], 'tile', n)
        for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming'):
            self.assertEqual(looks[n][0], 'source', n)
        self.assertEqual(looks['Room Mode'][0], 'wide')
        self.assertIn('gray_round', self.image(ctl['Room Mode'][0]))
        self.assertEqual(looks['Volume Mute'], ('square', 'Mute'))
        # Every template Mute rests gray and lights red, #75063C.
        self.assertIn('gray', self.image(ctl['Volume Mute'][0]))
        self.assertIn('red', self.image(ctl['Volume Mute'][0], 1))
        self.assertEqual(ctl['Volume Mute'][0]['states'][1]['color'], 'alert')
        self.assertEqual(looks['Help'], ('pill', 'Help'))
        self.assertIn('yellow', self.image(ctl['Help'][0]))
        self.assertEqual(ctl['Help'][0]['states'][1]['color'], 'caution')
        self.assertEqual(looks['Power'], ('pill', 'Off'))
        self.assertIn('red', self.image(ctl['Power'][0]))
        self.assertEqual(ctl['Power'][0]['states'][1]['color'], 'alert')
        # A rail's lit gray button keeps ink.
        self.assertEqual(ctl['Display On'][0]['states'][1]['color'], 'ink')
        self.assertTrue(all(not ctl[n][0].get('missing_icon') for n in looks), looks)

    def test_a_tab_is_named_by_its_twin_where_the_template_draws_one(self):
        """The 1035's and 1535's templates name each tab by a caption-only
        button across its foot sharing its ID (the frame's `twin`): the
        Header draws it so - the tab no caption, `<name> Caption` at the
        twin's depth in the twin's white, a mirror of the tab with its nav,
        does and state names, not held to the touch minimum - and on the
        725, whose tabs say their own names, it draws none."""
        for model in ('TLP1035T', 'TLP1535T', 'TLP725T'):
            with self.subTest(model=model):
                _, ctl, out = self.probe('Main.dc.html', model)
                self.assertEqual(out['problems'], [], model)
                twin = self.frame(model)['top']['tabs'].get('twin')
                for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming'):
                    tab, r = ctl[n][0], ctl[n][1]
                    if not twin:
                        self.assertNotIn(n + ' Caption', ctl)
                        self.assertTrue(tab.get('text', '').endswith(n), (model, n))
                        continue
                    cap, c = ctl[n + ' Caption'][0], ctl[n + ' Caption'][1]
                    self.assertEqual(tab.get('text', ''), '', (model, n))
                    self.assertEqual((cap['text'], cap['mirror'], cap['derived'], cap['nav'], cap['does']),
                                     (n, n, True, tab['nav'], tab['does']), (model, n))
                    self.assertEqual([s['name'] for s in cap['states']], [s['name'] for s in tab['states']])
                    self.assertEqual({s.get('fill') for s in cap['states']}, {'none'})
                    self.assertEqual((c[0], c[2], c[1] + c[3], c[3]),
                                     (r[0], r[2], r[1] + r[3], twin['items'][0]['rect'][3]), (model, n))

    def test_the_header_is_one_band_on_every_panel(self):
        """At the 725's and 720's type floor a tab's caption two breaks under
        its glyph needs more than the band: the bar's surfaces grow with the
        tabs, so the tabs never hang below it."""
        for model in self.PANELS:
            _, ctl, out = self.probe('Main.dc.html', model)
            self.assertEqual(out['problems'], [], model)
            tabs = [ctl[n][1] for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming')]
            bars = [ctl[n][1] for n in ('Header Left', 'Header Right')]
            foot = max(t[1] + t[3] for t in tabs)
            self.assertEqual({b[1] + b[3] for b in bars}, {foot}, model)
            self.assertEqual({b[1] for b in bars} | {t[1] for t in tabs}, {0}, model)

    def test_seams_under_the_gap_open_on_the_725_and_720(self):
        """The template's own seams across regions are under 2 mm on the 725
        (Mute 10 px over Power, the last launcher 8 px from Room Mode) and
        the 720: each opens to the panel's gap, the control that moves fewer
        others giving way, and the volume stack - one rail group - keeps its
        own."""
        for model in ('TLP725T', 'TLP720T'):
            _, ctl, out = self.probe('Main.dc.html', model)
            self.assertEqual(out['problems'], [], model)
            self.assertEqual(_gaps(ctl, model), [], model)
            launchers = [ctl[n][1] for n in ('Lighting Settings', 'Audio Settings')]
            self.assertEqual(len({(r[0], r[2]) for r in launchers}), 1, (model, launchers))

    def test_audio_control_keeps_its_gap(self):
        """The right rail's Audio Control, where the 1035's template stands it
        flush under Mute, opens to the gap."""
        edit = tuple(e.replace('{ns}', 'ExtronShockwave') for e in AUDIO_RAIL)
        _, ctl, out = self.probe('Main.dc.html', edit=edit)
        self.assertEqual(out['problems'], [])
        self.assertIn('Audio Control', ctl)
        self.assertEqual(_gaps(ctl, 'TLP1035T'), [])

    def test_the_725_keeps_audio_control_where_its_template_does(self):
        """The 725's template draws no audio place in its right rail: it keeps
        Audio Control in its left rail's second group (the frame's `audio`
        role there). The RightRail's audio control goes there, at that place,
        in the launchers' look - one control, by its name, on both panels."""
        rail = tuple(e.replace('{ns}', 'ExtronShockwave') for e in AUDIO_RAIL)
        drop = ('<x-import component-from-global-scope="ExtronShockwave.Button" name="Audio Settings" nav="Audio" '
                'does="Opens audio settings.">Audio</x-import>', '')
        _, ctl, out = self.probe('Main.dc.html', 'TLP725T', edit=(rail, drop))
        self.assertEqual(out['problems'], [])
        G = self.frame('TLP725T')['left']['groups'][1]['buttons']
        want = {b['role']: b['rect'] for b in G}
        self.assertEqual(ctl['Audio Control'][1], want['audio'])
        self.assertEqual(ctl['Lighting Settings'][1], want['lighting'])
        self.assertEqual(ctl['Audio Control'][0].get('joined'), ctl['Lighting Settings'][0].get('joined'))

    def test_where_the_725s_left_rail_cannot_hold_it_says_what_to_do(self):
        """With both launchers kept the second group holds three, more than the
        725's rail has room for; with no second Section there is nowhere to
        put it. Each is named with what to do."""
        rail = tuple(e.replace('{ns}', 'ExtronShockwave') for e in AUDIO_RAIL)
        _, ctl, out = self.probe('Main.dc.html', 'TLP725T', edit=rail)
        self.assertEqual(len(out['problems']), 1, out['problems'])
        # The Section stands as drawn, its launchers at the template's places.
        G = self.frame('TLP725T')['left']['groups'][1]['buttons']
        self.assertEqual([ctl[n][1][1] for n in ('Lighting Settings', 'Audio Settings')], [b['rect'][1] for b in G])
        self.assertNotIn('Audio Control', ctl)
        self.assertIn("Audio Control takes the RightRail's audio place", out['problems'][0])
        self.assertIn("keeps it in its LeftRail's second Section", out['problems'][0])
        self.assertIn('holds 3', out['problems'][0])
        section = ('<x-import component-from-global-scope="ExtronShockwave.Section" title="Settings">\n'
                   '<x-import component-from-global-scope="ExtronShockwave.Button" name="Lighting Settings" nav="Lighting" '
                   'does="Opens lighting settings.">Lighting</x-import>\n'
                   '<x-import component-from-global-scope="ExtronShockwave.Button" name="Audio Settings" nav="Audio" '
                   'does="Opens audio settings.">Audio</x-import>\n</x-import>\n')
        _, _, out = self.probe('Main.dc.html', 'TLP725T', edit=(rail, (section, '')))
        self.assertTrue(any("draw a second Section" in p for p in out['problems']), out['problems'])


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTurbulencesRegionPage(_RegionProbe, unittest.TestCase):
    """The region page on Turbulence, whose canvas names no look of its own."""

    THEME = 'turbulence'

    def test_each_control_takes_the_templates_look(self):
        """Display's `ring`s, `dock` launchers and Room Mode, a ring Mute
        that is the kit's volume_mute glyph, Help the input_help tab, Power
        the vc_power-dn key - the seed's own, none with a caption it lacks."""
        _, ctl, out = self.probe('Main.dc.html')
        self.assertEqual(out['problems'], [])
        looks = {n: (ctl[n][0]['variant'], ctl[n][0].get('text')) for n in ctl
                 if ctl[n][0].get('kind') == 'button'}
        for n in ('Display On', 'Display Off', 'Display Mute'):
            self.assertEqual(looks[n][0], 'ring', n)
        for n in ('Lighting Settings', 'Audio Settings', 'Room Mode'):
            self.assertEqual(looks[n][0], 'dock', n)
        self.assertEqual(looks['Volume Mute'], ('ring', None))
        self.assertIn('volume_mute', self.image(ctl['Volume Mute'][0]))
        self.assertEqual(looks['Help'][0], 'source')
        self.assertIn('input_help', self.image(ctl['Help'][0]))
        self.assertEqual(looks['Power'], ('button', None))
        self.assertIn('vc_power-dn', self.image(ctl['Power'][0]))
        self.assertTrue(all(not ctl[n][0].get('missing_icon') for n in looks), looks)

    def test_a_lit_dock_and_help_say_lime(self):
        """The seed's lit docks and Help are captioned Lime #00FF00, its rings
        and tabs LimeGreen: the profile said `accent` for all (the ledger's
        turbulence-27)."""
        _, ctl, _ = self.probe('Main.dc.html')
        lit = lambda n: ctl[n][0]['states'][1].get('color')
        for n in ('Room Mode', 'Lighting Settings', 'Audio Settings', 'Help'):
            self.assertEqual(lit(n), 'lime', n)
        for n in ('Display On', 'Volume Mute', 'Power'):
            self.assertEqual(lit(n), 'accent', n)

    def test_the_bars_are_the_templates_art(self):
        """Turbulence draws its header and footer as art - #020D1A at alpha
        128 under a 3-row light rule - in PBImages laid out Stretch: so do the
        regions, on every panel whose frame measures the art, from the kit's
        own file (the ledger's turbulence-02). Its side bars stay `rail`
        Panels: the seed's are PBImages with no art, a fill."""
        if '2047x151_header.png' not in designsys.kit_index(designsys.load('turbulence'))['paths']:
            self.skipTest("Turbulence's art is not extracted here (python -m gdl.designsys extract turbulence)")
        for model in self.PANELS:
            _, ctl, out = self.probe('Main.dc.html', model)
            self.assertEqual(out['problems'], [], model)
            F = self.frame(model)
            for n, band in (('Header Bar', 'top'), ('Footer Bar', 'bottom')):
                g, r, _ = ctl[n]
                art = F[band]['surfaces'][0]['art']
                self.assertEqual((g['kind'], g['image'], g['layout'], g.get('derived')),
                                 ('image', art, 'stretch', True), (model, n))
                self.assertNotIn('fill', g, (model, n))
            self.assertEqual([ctl[n][0]['fill'] for n in ('Left Rail Bar', 'Right Rail Bar')], ['rail', 'rail'])

    def test_help_gives_way_to_the_rail_launcher_beside_it(self):
        """The template stands its footer's Help 1 px from the left rail's
        last launcher: Help, the one control that moves, gives the panel's
        gap - x 152 on the 1035, as the profile's own Layout says - and the
        launcher column keeps its width."""
        F = self.frame('TLP1035T')
        for model in self.PANELS:
            _, ctl, out = self.probe('Main.dc.html', model)
            self.assertEqual(out['problems'], [], model)
            self.assertEqual(_gaps(ctl, model), [], model)
            launchers = [ctl[n][1] for n in ('Lighting Settings', 'Audio Settings')]
            self.assertEqual(len({(r[0], r[2]) for r in launchers}), 1, (model, launchers))
        _, ctl, _ = self.probe('Main.dc.html')
        help_ = {i['role']: i for i in F['bottom']['items']}['help']['rect']
        self.assertEqual(ctl['Help'][1], [152, help_[1], help_[0] + help_[2] - 152, help_[3]])
        # Help and Room Mode stand together (2 px apart): one set; Power is in none.
        self.assertEqual(ctl['Help'][0]['joined'], ctl['Room Mode'][0]['joined'])
        self.assertIsNotNone(ctl['Help'][0]['joined'])
        self.assertIsNone(ctl['Power'][0].get('joined'))

    def test_a_docks_two_words_go_on_two_lines(self):
        """Turbulence's dock draws two words on two lines, as the seed's Room
        Mode does: on one, the 720's Room Mode grew 23 px into the date
        beside it."""
        for model in self.PANELS:
            _, ctl, out = self.probe('Main.dc.html', model)
            self.assertEqual(ctl['Room Mode'][0]['text'], 'Room\r\nMode', model)
            self.assertFalse(ctl['Room Mode'][2], model)
        bottom = {i['role']: i for i in self.frame('TLP720T')['bottom']['items']}
        _, ctl, _ = self.probe('Main.dc.html', 'TLP720T')
        self.assertEqual(ctl['Room Mode'][1], bottom['mode']['rect'])
        self.assertEqual(ctl['Date Time'][1], bottom['clock']['rect'])

    def test_a_docks_state_caption_goes_on_two_lines_too(self):
        """A state's own caption is the dock's caption in that state, two
        words on two lines: 'Mics Muted' measured on one at the 725's 16 pt
        floor grew the rail's column from 112 to 128 px, into Help beside it
        (the round-four room's Mic Mute)."""
        mute = ('>Audio</x-import>', '>Audio</x-import><x-import component-from-global-scope="ExtronTurbulence.Button" '
                'name="Mic Mute" states=\'[{"name":"Live","look":"off"},{"name":"Muted","look":"on","text":"Mics Muted"}]\'>'
                'Mic Mute</x-import>')
        drop = ('<x-import component-from-global-scope="ExtronTurbulence.Button" name="Audio Settings" nav="Audio" '
                'does="Opens audio settings.">Audio</x-import>', '')
        _, ctl, out = self.probe('Main.dc.html', 'TLP725T', edit=(mute, drop))
        self.assertEqual(out['problems'], [])
        g, r, over = ctl['Mic Mute']
        self.assertEqual([s.get('text') for s in g['states']], [None, 'Mics\r\nMuted'])
        self.assertFalse(over)
        left = self.frame('TLP725T')['left']['groups'][1]['buttons']
        self.assertEqual(r[2], left[1]['rect'][2])

    def test_a_tab_row_stays_one_width(self):
        """Streaming's caption needs more than the 720's 80 px tab: the whole
        row grows with it, each tab the template's step after the last."""
        _, ctl, out = self.probe('Main.dc.html', 'TLP720T')
        self.assertEqual(out['problems'], [])
        tabs = [ctl[n][1] for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming')]
        F = self.frame('TLP720T')['top']['tabs']['items']
        seam = F[1]['rect'][0] - (F[0]['rect'][0] + F[0]['rect'][2])
        self.assertEqual(len({t[2] for t in tabs}), 1, tabs)
        self.assertEqual(tabs[0][0], F[0]['rect'][0])
        self.assertEqual([b[0] - (a[0] + a[2]) for a, b in zip(tabs, tabs[1:])], [seam] * 3)

    def test_audio_control_keeps_its_gap(self):
        for model in self.PANELS:
            _, ctl, out = self.probe('Main.dc.html', model, edit=tuple(
                e.replace('{ns}', 'ExtronTurbulence') for e in AUDIO_RAIL))
            self.assertEqual(out['problems'], [], model)
            self.assertIn('Audio Control', ctl)
            self.assertEqual(_gaps(ctl, model), [], model)


def _listed(theme):
    """The panels tests/data/design-regions-<theme> lists: the 1035, the 725
    and each hub its theme draws (Turbulence has no 535)."""
    with open(os.path.join(HERE, 'data', f'design-regions-{theme}', 'Main.dc.html'), encoding='utf-8') as fh:
        return re.search(r'panels="([^"]*)"', fh.read()).group(1)


def _hex8(v):
    v = str(v or '').upper()
    return v + 'FF' if re.fullmatch(r'#[0-9A-F]{6}', v) else v


class _CenterProbe(_Probe):
    """A bar theme's region canvas (tests/data/design-regions-<theme>): its
    sources as role="source" popups, its windows by role, each drawn as that
    panel's own template draws its center and its windows."""

    PANELS = ('TLP1035T', 'TLP725T')

    @classmethod
    def setUpClass(cls):
        cls.CANVAS = os.path.join(HERE, 'data', f'design-regions-{cls.THEME}')
        super().setUpClass()

    def profile(self):
        return designsys.load(self.THEME)

    def row(self, model):
        return designsys.models(self.profile())[model]

    def frame(self, model):
        return self.row(model)['frame']

    def writing(self):
        return self.profile()['writing']

    def pt(self, model, pt):
        """A size the template sets on `model`, as that panel draws it: never
        under its type floor."""
        return max(self.row(model)['floor'], pt)

    def token(self, fill):
        """The template's token for a measured #RRGGBBAA, as the bundle names
        it: exactly, else the one of its colour."""
        colors = {c['name']: c['value'] for c in self.profile()['colors'] if isinstance(c['value'], str)}
        want = _hex8(fill)
        for n, v in colors.items():
            if _hex8(v) == want:
                return n
        return next((n for n, v in colors.items() if _hex8(v)[:7] == want[:7]), None)

    def in_popup(self, r, model):
        g = self.frame(model)['center']['region']
        return [r[0] - g[0], r[1] - g[1], r[2], r[3]]

    def window(self, model, name):
        """The settings record a window named `name` draws as."""
        W = self.frame(model)['windows']
        recs = list(W['settings'] or []) + ([dict(W['help'], popups=['Help'])] if W.get('help') else [])
        first = name.split()[0].lower()
        return next(r for r in recs if any(q.split()[0].lower() == first for q in r['popups']))

    def assertAt(self, got, want, msg=None):
        """A derived control at the template's rect: there, or grown about it
        to the panel's touch minimum or a line at its type floor."""
        self.assertTrue(got == want or _inside(want, got), (got, want, msg))

    def assertClose(self, close, got, rec, model):
        """A derived Close at the template's rect where it is legal, else the
        frame's legal rect, on the window - a kit X that draws no caption
        exactly there, square; a captioned one as wide as its word needs."""
        want = list(rec['close'].get('legal') or rec['close']['rect'])
        # Kept on the window's card: Shockwave 725's legal Close stands 3 px
        # above its Lighting card.
        w = rec['rect']
        for a in (0, 1):
            want[a] = min(max(want[a], w[a]), w[a] + w[a + 2] - want[a + 2])
        V = self.profile()['buttons'][close.get('variant')]
        if V.get('caption') == 'none':
            self.assertEqual(got, want, (model, close['name']))
            self.assertIsNone(close.get('text'), (model, close['name']))
        else:
            self.assertAt(got, want, (model, close['name']))

    def test_a_source_popup_is_its_own_panels_region(self):
        """Sized to the panel's own popup region - the 725's from the 725's
        template, not the 1035's scaled - with no fill of its own."""
        for model in self.PANELS:
            for board in ('Laptop.dc.html', 'DocCam.dc.html'):
                page, ctl, out = self.probe(board, model)
                self.assertEqual((out['problems'], out['warnings']), ([], []), (model, board))
                self.assertEqual(page['size'], self.frame(model)['center']['region'][2:], (model, board))
                self.assertEqual((page['kind'], page['group'], page['background']), ('popup', 'Sources', 'none'))

    def test_the_main_pages_center_is_its_own_region(self):
        for model in self.PANELS:
            _, ctl, out = self.probe('Main.dc.html', model)
            self.assertEqual(out['problems'], [], model)
            self.assertEqual(ctl['Controls'][1], self.frame(model)['center']['region'], model)

    def test_the_well_and_title_are_the_templates(self):
        look = self.profile()['regions']['source']['title']
        for model in self.PANELS:
            F = self.frame(model)['center']
            _, ctl, _ = self.probe('Laptop.dc.html', model)
            g, r, _ = ctl['Laptop Title']
            self.assertAt(r, self.in_popup(F['title'], model), model)
            self.assertEqual((g['text'], g['color'], g['align'], g.get('derived')),
                             ('Laptop', look['color'], look['align'], True), model)
            shapes = [s for s in F['surfaces'] if s.get('popup') and s['kind'] == 'shape']
            drawn = sorted((r, g['fill']) for n, (g, r, _) in ctl.items() if g['kind'] == 'panel')
            self.assertEqual(drawn, sorted((self.in_popup(s['rect'], model), self.token(s['fill'])) for s in shapes),
                             model)
            # A source with controls is titled where the template titles one:
            # Turbulence's Doc Cam at the popup's top, its Laptop 40 px lower.
            _, ctl, _ = self.probe('DocCam.dc.html', model)
            self.assertAt(ctl['DocCam Title'][1], self.in_popup(F['title_controls'], model), model)
        # A title= names the popup's source.
        _, ctl, _ = self.probe('DocCam.dc.html')
        self.assertEqual(ctl['DocCam Title'][0]['text'], 'Document Camera')

    def test_what_the_chrome_says_is_set_at_each_panels_own_size(self):
        """Each panel's own template's sizes, never under its floor - the 725's
        from the 725's seed, not the 1035's scaled: the hierarchy the
        templates keep, a title over a Close, a question over its answers."""
        for model in self.PANELS:
            F = self.frame(model)
            pt = F['center']['pt']
            _, ctl, _ = self.probe('Laptop.dc.html', model)
            self.assertEqual(ctl['Laptop Title'][0]['size'], self.pt(model, pt['title']), model)
            self.assertEqual(ctl['Laptop Empty'][0]['size'], self.pt(model, pt['empty']), model)
            if 'status' in pt:
                self.assertEqual(ctl['Laptop Status'][0]['size'], self.pt(model, pt['status']), model)
            _, ctl, _ = self.probe('DocCam.dc.html', model)
            self.assertEqual(ctl['DocCam Title'][0]['size'], self.pt(model, pt['title']), model)
            _, ctl, _ = self.probe('Lighting.dc.html', model)
            self.assertEqual(ctl['Lighting Title'][0]['size'],
                             self.pt(model, self.window(model, 'Lighting')['pt']['title']), model)
            _, ctl, _ = self.probe('ConfirmPower.dc.html', model)
            self.assertEqual(ctl['ConfirmPower Message'][0]['size'],
                             self.pt(model, F['windows']['confirm']['pt']['message']), model)
            _, ctl, _ = self.probe('Help.dc.html', model)
            self.assertEqual(ctl['Help Title'][0]['size'], self.pt(model, F['windows']['help']['pt']['title']), model)
            self.assertEqual(ctl['Help Message'][0]['size'],
                             self.pt(model, F['windows']['help']['pt']['message']), model)
            for n, (g, r, _) in ctl.items():
                if g['kind'] == 'button' and g.get('text'):
                    self.assertLess(g['size'], ctl['Help Title'][0]['size'], (model, n))

    def test_an_empty_source_says_the_templates_words(self):
        w = self.writing()
        for model in self.PANELS:
            F = self.frame(model)['center']
            for name, noun in (('Laptop', 'laptop'), ('PC', 'PC')):
                _, ctl, out = self.probe(f'{name}.dc.html', model)
                g, r, _ = ctl[f'{name} Empty']
                self.assertEqual(g['text'], w['empty'].format(name=name, noun=noun), (model, name))
                self.assertTrue(_inside(r, self.in_popup(F['empty'], model)), (model, r, F['empty']))
                self.assertEqual(g['color'], 'text')
                if w.get('status'):
                    g, r, _ = ctl[f'{name} Status']
                    self.assertEqual(g['text'], w['status'])
                    self.assertEqual(r, self.in_popup(F['status'], model), model)
                else:
                    self.assertNotIn(f'{name} Status', ctl)

    def test_a_sources_controls_lay_out_in_the_well(self):
        """In the popup on every panel, in white where the template writes
        white, in the template's in-well look, clear of the title; and no
        empty state."""
        want = self.profile()['regions']['source']
        for model in self.PANELS:
            _, ctl, out = self.probe('DocCam.dc.html', model)
            self.assertEqual((out['problems'], out['warnings']), ([], []), model)
            self.assertNotIn('DocCam Empty', ctl)
            region = self.frame(model)['center']['region']
            mine = {n: v for n, v in ctl.items() if not v[0].get('derived')}
            self.assertIn('Doc Cam Zoom In', mine)
            title = ctl['DocCam Title'][1]
            for n, (g, r, over) in mine.items():
                self.assertTrue(_inside(r, [0, 0, region[2], region[3]]), (model, n, r))
                self.assertFalse(over, (model, n))
                self.assertFalse(_overlaps(r, [title[0] + 1, title[1] + 1, title[2] - 2, title[3] - 2]), (model, n))
                if g['kind'] == 'label':
                    self.assertEqual(g['color'], (want.get('label') or {}).get('color', 'text'), n)
                if g['kind'] == 'button' and (want.get('button') or {}).get('variant'):
                    self.assertEqual(g['variant'], want['button']['variant'], n)

    def test_a_control_under_the_title_is_named(self):
        """A heading moved up into the title's place is a warning, on the
        canvas and in the translate report: it is drawn, and runs into the
        title."""
        t = self.in_popup(self.frame('TLP1035T')['center']['title_controls'], 'TLP1035T')
        with open(os.path.join(self.dir, 'DocCam.dc.html'), encoding='utf-8') as fh:
            old = re.search(r'name="Inputs Heading"[^>]*?top: \d+px', fh.read()).group(0)
        new = re.sub(r'top: \d+px$', f'top: {t[1] + t[3] // 2 - 10}px', old)
        _, _, out = self.probe('DocCam.dc.html', edit=(old, new))
        self.assertTrue(any(w.startswith("Inputs Heading stands under DocCam's title") for w in out['warnings']),
                        out['warnings'])
        self.assertEqual(out['problems'], [])

    def test_a_window_is_the_templates_band_or_card(self):
        p = self.profile()
        for model in self.PANELS:
            for board, name in (('Lighting.dc.html', 'Lighting'), ('Help.dc.html', 'Help')):
                page, ctl, out = self.probe(board, model)
                self.assertEqual((out['problems'], out['warnings']), ([], []), (model, board))
                self.assertTrue(page.get('modal'))
                rec = self.window(model, name)
                shapes = [s for s in rec['surfaces'] if s['kind'] == 'shape']
                g, r, _ = ctl[f'{name} Window']
                self.assertEqual(r, rec['rect'], (model, name))
                self.assertEqual(g['fill'], self.token(shapes[-1]['fill']), (model, name))
                g, r, _ = ctl[f'{name} Title']
                self.assertAt(r, rec['title'], (model, name))
                self.assertEqual(g['color'], p['regions']['window']['title']['color'])
                close, r, _ = ctl[f'{name} Close']
                self.assertClose(close, r, rec, model)
                self.assertTrue(_inside(r, rec['rect']), (model, name))
                self.assertTrue(close.get('derived'))
                self.assertNotIn('nav', close)
                self.assertIn('back to the page that opened it', close['does'])
                # The designer's own controls stay in the window.
                for n, (g, r, _) in ctl.items():
                    if not g.get('derived'):
                        self.assertTrue(_inside(r, rec['rect']), (model, n, r))

    def test_help_says_the_templates_words(self):
        """role="help" with nothing in it: the template's title (HELP on
        Shockwave and Turbulence), its message where the template sets it, at
        Help's own size, and its Close."""
        w = self.writing()
        for model in self.PANELS:
            rec = self.frame(model)['windows']['help']
            _, ctl, out = self.probe('Help.dc.html', model)
            self.assertEqual((out['problems'], out['warnings']), ([], []), model)
            self.assertEqual(ctl['Help Title'][0]['text'], w.get('help_title', 'Help'))
            g, r, _ = ctl['Help Message']
            self.assertEqual((g['text'], g.get('derived')), (w['help'], True), model)
            self.assertAt(r, rec['message'], model)
            self.assertIn('Help Close', ctl)
            self.assertEqual(ctl['Help Window'][1], rec['rect'])
        # A title= is its title; with something put in it, no message.
        desk = (f'<x-import component-from-global-scope="{self.profile()["namespace"]}.Label" name="Desk" '
                'style="position: absolute; left: 400px; top: 400px; width: 400px; height: 60px">Call 4400.</x-import>')
        _, ctl, _ = self.probe('Help.dc.html', edit=(('role="help"', 'role="help" title="Assistance"'),
                                                     ('height: 800px"></x-import>', f'height: 800px">{desk}</x-import>')))
        self.assertEqual(ctl['Help Title'][0]['text'], 'Assistance')
        self.assertNotIn('Help Message', ctl)

    def test_what_stands_clear_of_a_windows_title_stays_clear_of_it(self):
        """What is put in a window is laid out from the body under its title
        on the panel drawn into the body under its title on each panel: the
        725's and the 525's titles stand lower in their windows than the
        1035's, and a Label 7 px under Shockwave 1035's HELP came out under
        the 725's title, and into its words on the 525 (round four)."""
        rec = self.frame('TLP1035T')['windows']['help']
        t = rec['title']
        ns = self.profile()['namespace']
        lab = (f'<x-import component-from-global-scope="{ns}.Label" name="Steps" align="center" style="position: '
               f'absolute; left: {rec["rect"][0] + 40}px; top: {t[1] + t[3] + 7}px; width: {rec["rect"][2] - 80}px; '
               'height: 50px">Choose a source.</x-import>')
        for model in ('TLP1035T', 'TLP725T', 'TLP525T'):
            _, ctl, out = self.probe('Help.dc.html', model,
                                     edit=('height: 800px"></x-import>', f'height: 800px">{lab}</x-import>'))
            self.assertEqual(out['warnings'], [], model)
            title, steps = ctl['Help Title'][1], ctl['Steps'][1]
            self.assertGreaterEqual(steps[1], title[1] + title[3], (model, title, steps))
        if self.THEME == 'shockwave':
            # Mapped body to body, Shockwave 725's windows set what is in them
            # a pixel lower than mapped window to window: Lights Preset 1, at
            # 360 on the 1035, was 268 on the 725 and is 269; Mic Heading 219
            # and 220.
            self.assertEqual(self.probe('Lighting.dc.html', 'TLP725T')[1]['Lights Preset 1'][1],
                             [305, 269, 128, 64])
            self.assertEqual(self.probe('Audio.dc.html', 'TLP725T')[1]['Mic Heading'][1], [470, 220, 84, 32])

    def test_a_window_no_record_names_is_drawn_alike_on_every_panel(self):
        """A settings window whose title names none of the template's windows
        is its commonest - titled, with a Close, drawn as shapes - on every
        panel: Mach's 725 measures its Share Content first, an untitled shade
        over a photo, where its 1035's first is the titled #303030 band."""
        fills = set()
        for model in self.PANELS:
            _, ctl, out = self.probe('Lighting.dc.html', model,
                                     edit=('title="Lighting Settings"', 'title="Room Mode"'))
            self.assertEqual((out['problems'], out['warnings']), ([], []), model)
            self.assertEqual(ctl['Lighting Title'][0]['text'], 'Room Mode', model)
            self.assertIn('Lighting Close', ctl)
            g, r, _ = ctl['Lighting Window']
            fills.add(g['fill'])
            recs = [s for s in self.frame(model)['windows']['settings'] if s['rect'] == r and s['title']
                    and all(x['kind'] == 'shape' for x in s['surfaces'])]
            self.assertTrue(recs, (model, r))
        self.assertEqual(len(fills), 1, fills)

    def test_the_confirm_asks_the_templates_question(self):
        w = self.writing()
        for model in self.PANELS:
            rec = self.frame(model)['windows']['confirm']
            _, ctl, out = self.probe('ConfirmPower.dc.html', model)
            self.assertEqual((out['problems'], out['warnings']), ([], []), model)
            self.assertEqual(ctl['ConfirmPower Window'][1], rec['rect'])
            g, r, _ = ctl['ConfirmPower Message']
            self.assertEqual(g['text'], w['confirm']['power'])
            self.assertAt(r, rec['message'], model)
            self.assertTrue(_inside(r, rec['rect']), (model, r))
            buttons = {b['role']: b for b in rec['buttons']}
            power, r, _ = ctl['ConfirmPower Power Down']
            self.assertAt(r, buttons['power']['rect'], model)
            self.assertEqual(power['does'], 'Powers the room down.')
            cancel, r, _ = ctl['ConfirmPower Cancel']
            self.assertAt(r, buttons['cancel']['rect'], model)
            self.assertNotIn('nav', cancel)
            self.assertTrue(power.get('derived') and cancel.get('derived'))
            self.assertNotIn('ConfirmPower Close', ctl)
            self.assertNotIn('ConfirmPower Title', ctl)

    def test_a_message_keeps_the_lines_its_template_sets_it_in(self):
        """Where the template sets a message on one line, its box holds the
        words on one line in the system's Open Sans - wider than the Light
        Turbulence's 1035 sets its power-down question in - and where it
        breaks them, the box is the template's."""
        from gdl import data, fonts, sfnt
        adv = sfnt.Advances(fonts.face_path('Open Sans'))
        for model in self.PANELS:
            W = self.frame(model)['windows']
            for board, key, edit in (('ConfirmPower.dc.html', 'confirm', None),
                                     ('ConfirmPower.dc.html', 'wait',
                                      ('role="confirm" topic="power"', 'role="wait" topic="down"')),
                                     ('Help.dc.html', 'help', None)):
                rec = W[key]
                _, ctl, _ = self.probe(board, model, edit=edit)
                g, r, _ = next(v for n, v in ctl.items() if n.endswith(' Message'))
                widest = max(adv.length(line, g['size'] * data.PT_TO_PX) for line in g['text'].split('\n'))
                room = rec['rect'][2] - 2 * self.row(model)['gap']
                with self.subTest(model=model, window=key):
                    self.assertTrue(_inside(r, rec['rect'], 0), (r, rec['rect']))
                    if rec['lines'] == 1 and '\n' not in g['text'] and widest * 1.06 <= room:
                        self.assertGreaterEqual(r[2], widest, r)
                    elif r != rec['message']:
                        self.assertGreater(widest * 1.06, rec['message'][2], r)

    def test_a_wait_says_the_templates_words_and_has_no_buttons(self):
        w = self.writing()
        for topic in ('down', 'up'):
            for model in self.PANELS:
                _, ctl, out = self.probe('ConfirmPower.dc.html', model,
                                         edit=('role="confirm" topic="power"', f'role="wait" topic="{topic}"'))
                self.assertEqual(out['problems'], [], model)
                self.assertEqual(ctl['ConfirmPower Message'][0]['text'], w['wait'][topic])
                self.assertEqual(ctl['ConfirmPower Window'][1], self.frame(model)['windows']['wait']['rect'])
                self.assertFalse([n for n, v in ctl.items() if v[0]['kind'] == 'button'], model)

    def test_a_topic_the_template_has_no_words_for_is_named(self):
        _, _, out = self.probe('ConfirmPower.dc.html', edit=('topic="power"', 'topic="recording"'))
        self.assertTrue(any("'recording'" in q and 'ConfirmPower' in q for q in out['problems']), out['problems'])

    def test_a_role_a_page_does_not_take_is_named(self):
        """A typo, a source role on a modal, a window's role on a popup: named,
        not drawn bare - the role draws the Close a designer leaves out."""
        for board, edit, kind in (('Lighting.dc.html', ('role="settings"', 'role="setting"'), 'modal'),
                                  ('Lighting.dc.html', ('role="settings"', 'role="source"'), 'modal'),
                                  ('Laptop.dc.html', ('role="source"', 'role="settings"'), 'popup')):
            role = edit[1].split('"')[1]
            _, ctl, out = self.probe(board, edit=edit)
            name = board.split('.')[0]
            self.assertTrue(any(q.startswith(f'{name}\'s role="{role}" is not one a kind="{kind}" takes')
                                and 'role="source" on a kind="popup"' in q for q in out['problems']),
                            (board, role, out['problems']))

    def test_a_role_draws_its_chrome_with_no_panels_listed(self):
        """A canvas that lists no panels draws on the system's own: a source
        popup at its region with its title and empty state, a confirm with
        its question and answers - not a bare board."""
        model = self.profile()['model']
        unlisted = (f' panels="{_listed(self.THEME)}"', '')
        page, ctl, out = self.probe('Laptop.dc.html', edit=unlisted)
        self.assertEqual(out['problems'], [])
        self.assertEqual(page['size'], self.frame(model)['center']['region'][2:])
        self.assertEqual((page['background'], page.get('panels')), ('none', None))
        self.assertIn('Laptop Title', ctl)
        self.assertIn('Laptop Empty', ctl)
        page, ctl, out = self.probe('ConfirmPower.dc.html', edit=unlisted)
        self.assertEqual(out['problems'], [])
        self.assertIsNone(page.get('panels'))
        self.assertTrue({'ConfirmPower Window', 'ConfirmPower Message', 'ConfirmPower Power Down',
                         'ConfirmPower Cancel'} <= set(ctl), sorted(ctl))

    def test_a_plain_container_in_a_window_or_a_source_is_where_it_was_drawn(self):
        """A flex row is laid out at its own place on the panel drawn, in a
        window and in a source popup, not moved by the window's or the well's
        origin - and inside them on another."""
        ns = self.profile()['namespace']
        row = ('<div style="position: absolute; left: {x}px; top: {y}px; width: 300px; height: 60px; display: flex; '
               'gap: 20px"><x-import component-from-global-scope="' + ns + '.Button" name="Flex A" does="Tests." '
               'style="width: 140px; height: 60px">A</x-import><x-import component-from-global-scope="' + ns
               + '.Button" name="Flex B" does="Tests." style="width: 140px; height: 60px">B</x-import></div>')
        for board, (x, y), box in (('Lighting.dc.html', (420, 520), None), ('Laptop.dc.html', (190, 300), 'source')):
            with open(os.path.join(self.dir, board), encoding='utf-8') as fh:
                src = fh.read()
            tail = src[src.rindex('</x-import>'):]
            edit = (tail, row.format(x=x, y=y) + tail)
            for model in self.PANELS:
                page, ctl, out = self.probe(board, model, edit=edit)
                a, b = ctl['Flex A'][1], ctl['Flex B'][1]
                if model == self.PANELS[0]:
                    self.assertEqual((a[:2], b[0] - a[0]), ([x, y], 160), (board, a, b))
                inner = self.frame(model)['center']['region'] if box else self.window(model, 'Lighting')['rect']
                frame = [0, 0, inner[2], inner[3]] if box else inner
                for r in (a, b):
                    self.assertTrue(_inside(r, frame), (board, model, r, frame))

    def test_a_source_popup_on_a_turned_panel_is_refused_by_name_for_now(self):
        """The 320 draws a source as a page of its own (_PagesProbe); a turned
        panel's frame is not drawn yet."""
        _, _, out = self.probe('Laptop.dc.html', 'TLP1035M-Portrait')
        self.assertIn('Laptop is a source popup, which the TLP1035M-Portrait does not draw yet', out['problems'])

    def test_a_window_on_a_turned_panel_is_refused_by_name_for_now(self):
        _, _, out = self.probe('Lighting.dc.html', 'TLP1035M-Portrait')
        self.assertIn('Lighting is a settings window, which the TLP1035M-Portrait does not draw yet', out['problems'])


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestMachsCenterAndWindows(_CenterProbe, unittest.TestCase):
    """Mach's framed shade well - a 58 px title bar, 1 px of photo, the body -
    titled in white at the left, and its #303030 band between the bars."""

    THEME = 'mach'

    def test_on_the_725_a_title_stands_over_what_it_titles(self):
        """The 725's own sizes: its source and window titles 20 pt, its
        question 18 - over the 16 pt floor its Close and answers stand at."""
        _, ctl, _ = self.probe('Laptop.dc.html', 'TLP725T')
        self.assertEqual((ctl['Laptop Title'][0]['size'], ctl['Laptop Empty'][0]['size']), (20, 16))
        _, ctl, _ = self.probe('Help.dc.html', 'TLP725T')
        self.assertEqual((ctl['Help Title'][0]['size'], ctl['Help Message'][0]['size'], ctl['Help Close'][0]['size']),
                         (20, 16, 16))
        _, ctl, _ = self.probe('ConfirmPower.dc.html', 'TLP725T')
        self.assertEqual(ctl['ConfirmPower Message'][0]['size'], 18)

    def test_a_popup_in_the_sources_group_without_the_role_is_named_where_it_outgrows_its_region(self):
        """Without role="source" a source's popup scales with main, and on the
        720 comes out 564 px in its 554 px region: named, as a warning."""
        edit = ((' role="source"', ''), (f'panels="{_listed(self.THEME)}"', 'panels="TLP1035T TLP720T"'))
        page, _, out = self.probe('DocCam.dc.html', 'TLP720T', edit=edit)
        self.assertEqual(page['size'], [564, 311])
        self.assertTrue(any(w.startswith('DocCam comes out 564x311 on a TLP720T, larger than the 554x324 popup region')
                            and 'role="source"' in w for w in out['warnings']), out['warnings'])
        # Drawn where it fits, it is not.
        _, _, out = self.probe('DocCam.dc.html', 'TLP1035T', edit=edit)
        self.assertEqual(out['warnings'], [])


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestShockwavesCenterAndWindows(_CenterProbe, unittest.TestCase):
    """Shockwave's translucent white well on the page, a white 40 pt title in
    each source's popup, 'Please connect your laptop.' and its Disconnected
    status, and its #999999 cards."""

    THEME = 'shockwave'

    def test_the_well_is_the_pages(self):
        """The well is a Center surface on the working page, not the popup's."""
        for model in self.PANELS:
            F = self.frame(model)['center']
            well = next(s for s in F['surfaces'] if not s.get('popup'))
            _, ctl, _ = self.probe('Main.dc.html', model)
            g, r, _ = ctl['Center Well']
            self.assertEqual((r, g['fill'], g.get('derived')), (well['rect'], 'well', True), model)

    def test_on_the_725_a_title_stands_over_what_it_titles(self):
        _, ctl, _ = self.probe('Laptop.dc.html', 'TLP725T')
        self.assertEqual([ctl[f'Laptop {n}'][0]['size'] for n in ('Title', 'Empty', 'Status')], [30, 20, 16])
        _, ctl, _ = self.probe('Lighting.dc.html', 'TLP725T')
        self.assertEqual(ctl['Lighting Title'][0]['size'], 30)
        _, ctl, _ = self.probe('ConfirmPower.dc.html', 'TLP725T')
        self.assertEqual(ctl['ConfirmPower Message'][0]['size'], 20)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTurbulencesCenterAndWindows(_CenterProbe, unittest.TestCase):
    """Turbulence draws no well: a large centred title over the photo, room
    left at the top left for the device picture, and its navy cards."""

    THEME = 'turbulence'

    def test_no_well_is_drawn(self):
        """Turbulence's source popups draw no frame, well, card or fill: an
        empty one only its title and its empty state."""
        for model in self.PANELS:
            for board, name in (('Laptop.dc.html', 'Laptop'), ('DocCam.dc.html', 'DocCam')):
                _, ctl, _ = self.probe(board, model)
                self.assertFalse([n for n, v in ctl.items() if v[0]['kind'] == 'panel'], (model, board))
            _, ctl, _ = self.probe('Laptop.dc.html', model)
            self.assertEqual(sorted(n for n in ctl if n != 'Laptop Image'), ['Laptop Empty', 'Laptop Title'], model)

    # Each source's picture where its own seed draws that device, in the
    # popup's coordinates: seeds/Turbulence 1035.gdl's and 725.gdl's Laptop,
    # PC and Doc Cam popups, whose Doc Cam is larger than the other two.
    PICTURES = {'TLP1035T': {'Laptop': [0, 0, 293, 257], 'PC': [0, 0, 293, 257], 'DocCam': [0, 0, 326, 288]},
                'TLP725T': {'Laptop': [0, 0, 235, 193], 'PC': [0, 0, 235, 193], 'DocCam': [0, 0, 261, 216]}}

    def test_a_source_draws_its_device_picture(self):
        """The template pins its device picture at the popup's top left,
        fitted, at the size it draws that device (1152x1152_laptop.png
        293x257 on the 1035's Laptop, 1152x1152_doc-cam.png 326x288 on its
        Doc Cam), behind the title: by the Page's `device`, else its name
        where the kit pictures one."""
        if '1152x1152_laptop.png' not in designsys.kit_index(self.profile())['paths']:
            self.skipTest("Turbulence's art is not extracted here (python -m gdl.designsys extract turbulence)")
        for model in self.PANELS:
            for board, name, art in (('Laptop.dc.html', 'Laptop', '1152x1152_laptop.png'),
                                     ('PC.dc.html', 'PC', '1152x1152_pc.png'),
                                     ('DocCam.dc.html', 'DocCam', '1152x1152_doc-cam.png')):
                _, ctl, out = self.probe(board, model)
                self.assertEqual(out['problems'], [], (model, board))
                g, r, _ = ctl[name + ' Image']
                self.assertEqual((g['kind'], g['image'], g.get('layout'), g.get('derived')),
                                 ('image', art, None, True), (model, board))
                self.assertEqual(r, self.PICTURES[model][name], (model, board))
                names = [json.loads(c['gdl']).get('name') for c in out['controls']]
                self.assertLess(names.index(name + ' Image'), names.index(name + ' Title'), (model, board))

    def test_a_device_the_seed_pictures_in_no_source_takes_the_laptops_place(self):
        """A device named is drawn at its own seed's size where a source's
        popup pictures it - the 1035's Camera Control draws vc-1 200x209 -
        and at the Laptop's where none does: the kit's monitor is a settings
        window's picture on Turbulence, no source's."""
        if '1152x1152_vc-1.png' not in designsys.kit_index(self.profile())['paths']:
            self.skipTest("Turbulence's art is not extracted here (python -m gdl.designsys extract turbulence)")
        for device, art, want in (('vc-1', '1152x1152_vc-1.png', [0, 0, 200, 209]),
                                  ('monitor', '1152x1152_monitor.png', [0, 0, 293, 257])):
            _, ctl, out = self.probe('Streaming.dc.html', 'TLP1035T',
                                     edit=('role="source"', f'role="source" device="{device}"'))
            self.assertEqual(out['problems'], [], device)
            g, r, _ = ctl['Streaming Image']
            self.assertEqual((g['image'], r), (art, want), device)

    def test_a_source_whose_device_is_not_pictured_is_named(self):
        """Streaming is no device the kit pictures: its place stays empty and
        the canvas says how to name one, without outlining the page; named,
        it is drawn."""
        if '1152x1152_ipod.png' not in designsys.kit_index(self.profile())['paths']:
            self.skipTest("Turbulence's art is not extracted here (python -m gdl.designsys extract turbulence)")
        _, ctl, out = self.probe('Streaming.dc.html')
        self.assertNotIn('Streaming Image', ctl)
        self.assertEqual(out['problems'], [])
        self.assertTrue(any('Streaming' in w and 'device=' in w for w in out['warnings']), out['warnings'])
        self.assertFalse(out['page']['outlined'])
        _, ctl, out = self.probe('Streaming.dc.html', edit=('role="source"', 'role="source" device="ipod"'))
        self.assertEqual(ctl['Streaming Image'][0]['image'], '1152x1152_ipod.png')
        self.assertEqual(out['warnings'], [])
        _, ctl, out = self.probe('Streaming.dc.html', edit=('role="source"', 'role="source" device="toaster"'))
        self.assertTrue(any('toaster' in p for p in out['problems']), out['problems'])

    def test_on_the_725_a_title_stands_over_what_it_titles(self):
        """The 725 keeps its sources' 36 pt titles, and sets its windows' 30."""
        _, ctl, _ = self.probe('Laptop.dc.html', 'TLP725T')
        self.assertEqual(ctl['Laptop Title'][0]['size'], 36)
        _, ctl, _ = self.probe('Lighting.dc.html', 'TLP725T')
        self.assertEqual(ctl['Lighting Title'][0]['size'], 30)
        _, ctl, _ = self.probe('ConfirmPower.dc.html', 'TLP725T')
        self.assertEqual(ctl['ConfirmPower Message'][0]['size'], 20)

    def test_the_power_down_question_is_one_line_on_the_1035(self):
        """The template's 505 px box holds it on one line in Open Sans Light;
        in the system's Open Sans the box widens to hold it so, inside the
        window. The 725's template breaks it, and so does its box."""
        rec = self.frame('TLP1035T')['windows']['confirm']
        _, ctl, _ = self.probe('ConfirmPower.dc.html', 'TLP1035T')
        r = ctl['ConfirmPower Message'][1]
        self.assertGreater(r[2], rec['message'][2])
        self.assertTrue(_inside(r, rec['rect'], 0), (r, rec['rect']))
        _, ctl, _ = self.probe('ConfirmPower.dc.html', 'TLP725T')
        self.assertEqual(ctl['ConfirmPower Message'][1], self.frame('TLP725T')['windows']['confirm']['message'])


class _HubProbe(_Probe):
    """A bar theme's region canvas (tests/data/design-regions-<theme>) on its
    hubs, drawn as each hub's own template draws its working page
    (docs/superpowers/specs/2026-10-22-region-frame-design.md, PR6): a right
    menu bar, and one popup region filling main in which a Select a Source
    grid, every source's popup and the settings appear."""

    HUBS = ('TLP525T',)

    @classmethod
    def setUpClass(cls):
        cls.CANVAS = os.path.join(HERE, 'data', f'design-regions-{cls.THEME}')
        super().setUpClass()

    def profile(self):
        return designsys.load(self.THEME)

    def frame(self, model):
        F = designsys.models(self.profile())[model]['frame']
        F['center']['strip_rect'] = next(x['rect'] for x in F['center']['items'] if x['role'] == 'popup')
        return F

    def roles(self, model):
        return {x['role']: x for x in self.frame(model)['right']['items']}

    def names(self, model):
        F = self.frame(model)
        right = self.roles(model)
        return {'select': F['select']['popup'] or 'Select Source', 'options': F['options']['popup'],
                'display': right['display']['name'] if 'display' in right else 'Display Settings'}

    def split(self, board, model, edit=None):
        """The page, its derived popups, and {popup or None: {name: (data-gdl,
        rect)}} - the page's own controls under None, each popup's in its own
        coordinates."""
        page, _, out = self.probe(board, model, edit)
        parts = [json.loads(p['gdl']) for p in out['parts']]
        on = {None: {}}
        for c in out['controls']:
            g = json.loads(c['gdl'])
            where = parts[c['part']]['name'] if c.get('part') is not None else None
            on.setdefault(where, {})[g.get('name')] = (g, [round(v) for v in c['rect']], c.get('overflow'))
        return page, {p['name']: p for p in parts}, on, out

    def assertAt(self, got, want, msg=None):
        """At the template's rect, or grown about it to what it needs here."""
        self.assertTrue(got == want or _inside(want, got), (got, want, msg))

    def left_off(self, model):
        """What the canvas's Main draws on the 1035 that the hub has no place
        for, each named: the footer's clock, and on Mach the heading its
        rail draws over its Settings group, which the hub's options do not."""
        out = [f"Main's Date Time is left off the {model} - its template draws no clock"]
        if self.THEME == 'mach':
            out.append(f"Main's Settings Heading is left off the {model} - its template's options draw no heading")
        return out

    def test_the_menu_bar_is_the_hubs_own(self):
        """Volume, Up, Down, Mute, the settings opener (Display Control too
        on Shockwave and Turbulence) and Power down the hub's own bar, in
        its order, at least the touch minimum, Up, Down and the openers with
        the hub's seed IDs; the bar's surface its own; nothing but the clock
        left off, and that named."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                page, parts, on, out = self.split('Main.dc.html', m)
                self.assertEqual(out['problems'], [])
                self.assertEqual(out['warnings'], self.left_off(m))
                self.assertEqual(page['left'], [w.split("'s ", 1)[1].split(' is left off')[0] for w in self.left_off(m)])
                F, right = self.frame(m), self.roles(m)
                band, main = F['right']['rect'], on[None]
                touch = designsys.models(self.profile())[m]['touch']
                self.assertEqual(main['Menu Bar'][1], band)
                self.assertTrue(main['Menu Bar'][0].get('derived'))
                g, r, _ = main['Volume Heading']
                self.assertEqual(g['text'], 'Volume')
                names = {'volume-up': 'Volume Up', 'volume-down': 'Volume Down', 'mute': 'Volume Mute',
                         'settings': right['settings']['name'], 'power': 'Power'}
                if 'display' in right:
                    names['display'] = right['display']['name']
                tops, sets = [], set()
                for role in [x['role'] for x in F['right']['items'] if x['role'] in names]:
                    g, r, _ = main[names[role]]
                    self.assertTrue(_inside(r, band, 0), (m, role, r, band))
                    self.assertGreaterEqual(min(r[2], r[3]), touch, (m, role, r))
                    # Derived chrome carries the hub's seed ID; Mute and Power
                    # are the canvas's, which keep the 1035's (pin_ids).
                    self.assertEqual(g.get('id') if g.get('derived') else g.get('seed_id'), right[role]['id'],
                                     (m, role))
                    self.assertEqual(bool(g.get('derived')), role not in ('mute', 'power'), (m, role))
                    tops.append(r[1])
                    sets.add(g.get('joined'))
                self.assertEqual(tops, sorted(tops), m)
                self.assertEqual(len(sets), 1, sets)
                self.assertEqual(main['Power'][0]['nav'], 'ConfirmPower')
                self.assertEqual(main[right['settings']['name']][0]['nav'], self.names(m)['options'])

    def test_the_level_is_a_popup_beside_the_bar(self):
        """The volume slider is the hub's level, in the Volume Level strip the
        template stands beside its bar: a popup of its own the program shows,
        named Volume as on every panel."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, parts, on, _ = self.split('Main.dc.html', m)
                strip = next(x['rect'] for x in self.frame(m)['center']['items'] if x['role'] == 'popup')
                part = parts['Volume Level']
                self.assertEqual((part['kind'], part['group'], part['size']), ('popup', 'Volume Level', strip[2:]))
                g, r, _ = on['Volume Level']['Volume']
                self.assertEqual(g['kind'], 'level')
                self.assertTrue(_inside(r, [0, 0, strip[2], strip[3]]), r)
                g, r, _ = on[None]['Volume']
                self.assertEqual((g['kind'], g['group'], r), ('popup_ref', 'Volume Level', strip))

    def test_select_a_source_holds_the_tabs_as_its_tiles(self):
        """The Header's source tabs are the grid's tiles, each the same
        control - its name, so its ID, its nav and its does - a popup of
        main's group filling main, under the hub's own title, Help where the
        template stands it."""
        _, ctl1035, _ = self.probe('Main.dc.html', 'TLP1035T')
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, parts, on, _ = self.split('Main.dc.html', m)
                F = self.frame(m)
                region, S, name = F['center']['region'], F['select'], self.names(m)['select']
                part = parts[name]
                self.assertEqual((part['kind'], part['group'], part['size']), ('popup', 'Sources', region[2:]))
                self.assertEqual(on[None]['Controls'][1], region)
                grid = on[name]
                joined = set()
                for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming'):
                    g, r, _ = grid[n]
                    self.assertFalse(g.get('derived'), n)
                    self.assertEqual((g['nav'], g['does']), (ctl1035[n][0]['nav'], ctl1035[n][0]['does']), n)
                    joined.add(g.get('joined'))
                self.assertEqual(len(joined), 1)
                # The template's first row, centred where its is.
                self.assertEqual(grid['PC'][1][1], S['tiles'][0]['rect'][1], m)
                g, r, _ = grid[name + ' Title']
                self.assertEqual((g['text'], g.get('derived')), (S['text'], True))
                self.assertAt(r, S['title'], m)
                g, r, _ = grid['Help']
                self.assertEqual((g['nav'], g.get('derived')), ('Help', None))
                self.assertAt(r, S['help']['rect'], m)
                for s in S['surfaces']:
                    self.assertEqual(grid[name + ' Header'][1], s['rect'])

    def test_the_settings_opener_shows_the_launchers(self):
        """The LeftRail's later Section and the footer's Room Mode are the
        options the hub's settings opener shows, each the same control; its
        first, the display group, the popup the hub's Display Control opens
        (Mach's from a tile in its Settings), with a Close back."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, parts, on, out = self.split('Main.dc.html', m)
                N, F = self.names(m), self.frame(m)
                region = F['center']['region']
                opts = on[N['options']]
                self.assertEqual((parts[N['options']]['group'], parts[N['options']]['size']), ('Sources', region[2:]))
                for n, nav in (('Lighting Settings', 'Lighting'), ('Audio Settings', 'Audio'), ('Room Mode', None)):
                    g, r, _ = opts[n]
                    self.assertEqual((g.get('nav'), g.get('derived')), (nav, None), n)
                    self.assertTrue(_inside(r, [0, 0, region[2], region[3]]), (n, r))
                g, r, _ = opts[N['options'] + ' Close']
                self.assertEqual((g['nav'], g['derived']), (N['select'], True))
                self.assertEqual(opts[N['options'] + ' Title'][0]['text'], F['options']['text'])
                disp = on[N['display']]
                head = disp[N['display'] + ' Title'][1]
                for n in ('Display On', 'Display Off', 'Display Mute'):
                    g, r, _ = disp[n]
                    self.assertFalse(g.get('derived'), n)
                    self.assertGreaterEqual(r[1], head[1] + head[3], n)
                opener = on[None].get(N['display']) or opts.get(N['display'])
                self.assertEqual((opener[0]['nav'], opener[0]['derived']), (N['display'], True))
                self.assertEqual(_gaps({n: v for n, v in on[None].items()}, m), [])

    def test_nothing_on_the_canvas_is_dropped(self):
        """Every control the 1035 draws from the canvas is on the hub - on its
        page or in a popup it derives - but the clock its template has no
        place for, which the page names."""
        _, ctl1035, _ = self.probe('Main.dc.html', 'TLP1035T')
        mine = {n for n, (g, _, _) in ctl1035.items() if not g.get('derived')}
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Main.dc.html', m)
                here = {n for ctl in on.values() for n, (g, _, _) in ctl.items() if not g.get('derived')}
                self.assertEqual(mine - here, set(self.split('Main.dc.html', m)[0]['left']), m)
                self.assertIn('Date Time', mine - here)

    def test_what_the_hub_has_no_place_for_is_named_and_the_rest_placed(self):
        """A Header's start control has no header bar on a hub: left off, by
        name, and in the page's `left`. An Audio Control in the RightRail is
        one of the options the settings opener shows, and a launcher's own
        fill stays its own there. A RightRail child in a place only the hub's
        layout fills (its settings opener) is told the slots a designer fills."""
        ns, m = self.profile()['namespace'], self.HUBS[0]
        edit = ((f'<x-import component-from-global-scope="{ns}.Header">',
                 f'<x-import component-from-global-scope="{ns}.Header"><x-import component-from-global-scope='
                 f'"{ns}.Label" slot="start" name="Room Name">Room 101</x-import>'),
                (f'<x-import component-from-global-scope="{ns}.RightRail"></x-import>',
                 f'<x-import component-from-global-scope="{ns}.RightRail"><x-import component-from-global-scope='
                 f'"{ns}.Button" slot="audio" name="Audio Control" nav="Audio" does="Opens audio settings.">Audio'
                 f'</x-import><x-import component-from-global-scope="{ns}.Button" slot="settings" name="Gear" '
                 f'does="Opens settings.">Gear</x-import></x-import>'),
                ('name="Lighting Settings"', 'name="Lighting Settings" fill="page"'))
        page, _, on, out = self.split('Main.dc.html', m, edit)
        self.assertEqual(out['problems'], ['Gear in the RightRail has no slot it draws - say slot="heading", '
                                           '"volume", "mute", "audio"'])
        self.assertIn(f"Main's Room Name is left off the {m} - its template has no header bar for the Header's "
                      'start controls', out['warnings'])
        self.assertIn('Room Name', page['left'])
        opts = on[self.names(m)['options']]
        g, _, _ = opts['Audio Control']
        self.assertEqual((g['nav'], g.get('derived')), ('Audio', None))
        self.assertEqual(opts['Lighting Settings'][0]['fill'], 'page')

    def test_a_source_popup_is_the_hubs(self):
        """Main's size, a popup of its group, no fill; the hub's header - its
        strip where it draws one, the title, a Close back to Select a Source -
        and its empty state; what it holds under the header, clear of the
        Volume Level strip."""
        w = self.profile()['writing']
        for m in self.HUBS:
            with self.subTest(hub=m):
                F = self.frame(m)
                C, region = F['center'], F['center']['region']
                page, _, on, out = self.split('Laptop.dc.html', m)
                self.assertEqual((out['problems'], out['warnings']), ([], []))
                self.assertEqual((page['kind'], page['group'], page['size'], page['background']),
                                 ('popup', 'Sources', region[2:], 'none'))
                ctl = on[None]
                self.assertAt(ctl['Laptop Title'][1], C['title'], m)
                g, r, _ = ctl['Laptop Close']
                self.assertEqual((g['nav'], g['derived']), (self.names(m)['select'], True))
                self.assertAt(r, C['close']['rect'], m)
                self.assertEqual(ctl['Laptop Empty'][0]['text'],
                                 w.get('hub_empty', w['empty']).format(name='Laptop', noun='laptop'))
                self.assertNotIn('Laptop Status', ctl)
                page, _, on, out = self.split('DocCam.dc.html', m)
                self.assertEqual((out['problems'], out['warnings']), ([], []))
                strip = next(x['rect'] for x in C['items'] if x['role'] == 'popup')
                head = max(C['title'][1] + C['title'][3], C['close']['rect'][1] + C['close']['rect'][3])
                for n, (g, r, _) in on[None].items():
                    if not g.get('derived'):
                        self.assertTrue(_inside(r, [0, head, strip[0], region[3] - head]), (m, n, r))

    def test_a_sources_controls_are_centred_on_the_popup(self):
        """What a source popup holds is centred on the whole popup, as the
        template centres its keys, and stays clear of the Volume Level strip:
        centred on the box left of the strip, Mach 525's Doc Cam came out
        15 px from the screen's edge where the template's is 55."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                F = self.frame(m)
                region, strip = F['center']['region'], F['center']['strip_rect']
                _, _, on, _ = self.split('DocCam.dc.html', m)
                mine = [r for g, r, _ in on[None].values() if not g.get('derived')]
                x0, x1 = min(r[0] for r in mine), max(r[0] + r[2] for r in mine)
                gap = designsys.models(self.profile())[m]['gap']
                self.assertLessEqual(abs((x0 + x1) / 2 - region[2] / 2), gap, (m, x0, x1))
                self.assertLessEqual(x1, strip[0], (m, x1, strip))
                self.assertGreaterEqual(x0, region[2] - strip[0] - 1, (m, x0))

    def test_the_volume_level_strip_is_the_templates(self):
        """The Volume Level popup in the template's own ground, its level where
        and as the template draws it (`center.level`, measured off the seed):
        square, at the template's rect and width."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                SL = self.frame(m)['center']['level']
                _, parts, on, _ = self.split('Main.dc.html', m)
                self.assertTrue(parts['Volume Level'].get('background'), m)
                g, r, _ = on['Volume Level']['Volume']
                self.assertEqual(r, SL['rect'], m)
                self.assertEqual((g['track'], g['border']), (SL['rect'][2], 'none'), m)

    def test_helps_close_is_where_the_template_stands_it(self):
        """Shockwave's and Turbulence's hub Help stand their Close at the
        screen's corner, off the card: settled in the window, it came out in
        the card's corner."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                W = self.frame(m)['windows']['help']
                _, _, on, _ = self.split('Help.dc.html', m)
                self.assertAt(on[None]['Help Close'][1], W['close']['rect'], m)

    def test_a_settings_window_is_a_popup_of_main(self):
        """The hub draws its settings as popups of main's group, not windows
        over the page: the hub's header, title and Close back to Select a
        Source, what it holds under them."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                F = self.frame(m)
                region, rec = F['center']['region'], F['windows']['settings'][0]
                page, _, on, out = self.split('Lighting.dc.html', m)
                self.assertEqual((out['problems'], out['warnings']), ([], []))
                self.assertEqual((page['kind'], page.get('modal'), page['group'], page['size']),
                                 ('popup', None, 'Sources', region[2:]))
                ctl = on[None]
                self.assertEqual(ctl['Lighting Title'][0]['text'], 'Lighting Settings')
                self.assertAt(ctl['Lighting Title'][1], rec['title'], m)
                self.assertEqual(ctl['Lighting Close'][0]['nav'], self.names(m)['select'])
                head = ctl['Lighting Title'][1]
                for n in ('Lights Preset 1', 'Lights Preset 2'):
                    r = ctl[n][1]
                    self.assertTrue(_inside(r, [0, head[1] + head[3], region[2], region[3]]), (m, n, r))

    def test_its_popups_stand_on_the_pages_photo(self):
        """Shockwave's and Turbulence's hubs draw every standard popup on the
        page's photo, stretched to it (seeds/<theme> 525.gdl): a source's
        popup, a settings window, the options and Display Control. Select a
        Source is the page's own grid there, and the Volume Level strip its
        own ground. Mach's are not."""
        photo = bool(((self.profile()['regions'].get('hub') or {}).get('popup') or {}).get('photo'))
        self.assertEqual(photo, self.THEME in ('shockwave', 'turbulence'))
        theme = designsys.themes(self.profile())[0]['id']
        for m in self.HUBS:
            with self.subTest(hub=m):
                want = designsys.models(self.profile())[m]['backgrounds'][theme]['image'] if photo else None
                for board in ('Laptop.dc.html', 'Lighting.dc.html'):
                    page, _, _, _ = self.split(board, m)
                    self.assertEqual(page.get('background_image'), want, (m, board))
                _, parts, _, _ = self.split('Main.dc.html', m)
                N = self.names(m)
                for n in (N['options'], N['display']):
                    self.assertEqual(parts[n].get('background_image'), want, (m, n))
                for n in (N['select'], 'Volume Level'):
                    self.assertIsNone(parts.get(n, {}).get('background_image'), (m, n))

    def test_help_and_the_power_down_question_stay_windows(self):
        """A hub's Help, its question and its wait are modals still, in its
        own style: Mach's text on the scrim, Shockwave's and Turbulence's
        cards."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                W = self.frame(m)['windows']
                page, _, on, out = self.split('Help.dc.html', m)
                self.assertEqual((out['problems'], out['warnings']), ([], []))
                self.assertTrue(page['modal'])
                self.assertAt(on[None]['Help Title'][1], W['help']['title'], m)
                self.assertIn('Help Close', on[None])
                self.assertEqual('Help Window' in on[None], bool(W['help']['surfaces']))
                page, _, on, out = self.split('ConfirmPower.dc.html', m)
                self.assertEqual((out['problems'], out['warnings']), ([], []))
                for b in W['confirm']['buttons']:
                    n = 'ConfirmPower ' + ('Power Down' if b['role'] == 'power' else 'Cancel')
                    self.assertAt(on[None][n][1], b['rect'], (m, n))


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestMachsHubs(_HubProbe, unittest.TestCase):
    """Mach's 525 and 535: a shade menu bar of ghost glyphs, Select a Source a
    popup of its own with black titles over the photo, its Settings opaque
    #303030 with a Display tile."""

    THEME = 'mach'
    HUBS = ('TLP525T', 'TLP535T')

    def test_the_525_is_its_templates_own_rects(self):
        """The 525's 66 px menu cells are its touch minimum: each exactly
        where the template draws it - but Mute, whose word the template sets
        at 13 pt, under the 525's 18 pt type floor: grown about its place,
        inside the bar, to hold it."""
        _, _, on, _ = self.split('Main.dc.html', 'TLP525T')
        right = self.roles('TLP525T')
        for role, n in (('volume-up', 'Volume Up'), ('volume-down', 'Volume Down'), ('settings', 'Settings'),
                        ('power', 'Power')):
            self.assertEqual(on[None][n][1], right[role]['rect'], n)
        mute = on[None]['Volume Mute'][1]
        self.assertAt(mute, right['mute']['rect'])
        self.assertTrue(_inside(mute, self.frame('TLP525T')['right']['rect'], 0), mute)
        S = self.frame('TLP525T')['select']
        for n, t in zip(('PC', 'Laptop', 'Doc Cam', 'Streaming'), S['tiles']):
            self.assertEqual(on['Select Source'][n][1], t['rect'], n)

    def test_settings_are_opaque_and_titled_white(self):
        _, parts, on, _ = self.split('Main.dc.html', 'TLP525T')
        self.assertEqual(parts['Settings'].get('background'), 'page')
        self.assertEqual(on['Settings']['Settings Title'][0]['color'], 'text')
        self.assertEqual(on['Select Source']['Select Source Title'][0]['color'], 'ink')
        page, _, _, _ = self.split('Lighting.dc.html', 'TLP525T')
        self.assertEqual(page['background'], 'page')

    def test_its_opaque_popups_draw_raised_keys(self):
        """On Settings, Display Settings and a settings window - opaque #303030
        - every key is the template's raised white wash (`ghost`), not the
        shade it draws over the photo, which read as black holes there; over
        the photo, Select a Source's tiles and a source's Close keep the shade."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Main.dc.html', m)
                for where, n in (('Settings', 'Display Settings'), ('Settings', 'Lighting Settings'),
                                 ('Settings', 'Room Mode'), ('Settings', 'Settings Close'),
                                 ('Display Settings', 'Display On'), ('Display Settings', 'Display Settings Close')):
                    self.assertEqual(on[where][n][0]['variant'], 'ghost', (m, where, n))
                self.assertEqual(on['Select Source']['PC'][0]['variant'], 'solid', m)
                _, _, on, _ = self.split('Lighting.dc.html', m)
                self.assertEqual(on[None]['Lighting Close'][0]['variant'], 'ghost', m)
                _, _, on, _ = self.split('Laptop.dc.html', m)
                self.assertEqual(on[None]['Laptop Close'][0]['variant'], 'solid', m)

    def test_its_menu_bar_draws_the_templates_words_and_glyphs(self):
        """Volume white on the bar, Up and Down the kit's chevrons (not the
        level's speaker+ and speaker-), Mute its word."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Main.dc.html', m)
                main = on[None]
                self.assertEqual(main['Volume Heading'][0]['color'], 'text', m)
                self.assertEqual([main[n][0]['states'][0]['image'] for n in ('Volume Up', 'Volume Down')],
                                 ['440x440_up.png', '440x440_down.png'], m)
                g = main['Volume Mute'][0]
                self.assertEqual((g['text'], g['states'][0].get('image')), ('Mute', None), m)

    def test_its_help_is_titled_and_closed_as_the_hubs(self):
        """Help on the scrim: its title centred, its Close the back glyph."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Help.dc.html', m)
                self.assertEqual(on[None]['Help Title'][0]['align'], 'center', m)
                g = on[None]['Help Close'][0]
                self.assertEqual((g['variant'], g.get('text', ''), g['states'][0]['image']),
                                 ('ghost', '', '440x440_back.png'), m)

    def test_its_level_is_the_templates_white_bar(self):
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, parts, on, _ = self.split('Main.dc.html', m)
                self.assertEqual(parts['Volume Level']['background'], 'page')
                g = on['Volume Level']['Volume'][0]
                self.assertEqual((g['fill'], g['bar']), ('shade', 'text'), m)

    def test_its_options_are_the_templates_tiles(self):
        """Every launcher a 100 px tile, in one row, its caption the label
        under it, Lighting and Audio with the kit's bulb and speaker."""
        _, _, on, _ = self.split('Main.dc.html', 'TLP525T')
        opts = on['Settings']
        tops = {opts[n][1][1] for n in ('Display Settings', 'Lighting Settings', 'Audio Settings', 'Room Mode')}
        self.assertEqual(tops, {self.frame('TLP525T')['options']['tiles'][0]['rect'][1]})
        for n, icon in (('Lighting Settings', '440x440_lighting.png'), ('Audio Settings', '440x440_speaker.png'),
                        ('Room Mode', None)):
            g, r, _ = opts[n]
            self.assertEqual((r[2], r[3], g.get('text', ''), g['states'][0].get('image')), (100, 100, '', icon), n)
            self.assertIn(n + ' Label', opts)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestShockwavesHubs(_HubProbe, unittest.TestCase):
    """Shockwave's 525 and 535: a side bar, Display Control and More, a black
    45% header strip over every popup of main."""

    THEME = 'shockwave'
    HUBS = ('TLP525T', 'TLP535T')

    def test_its_menu_bar_is_the_templates(self):
        """The template's cells: its gray key art with Up and Down chevrons and
        Mute's word - Mute plain at rest, red when on - and Power its square
        power glyph in a crimson ring, not the footer's Off pill."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Main.dc.html', m)
                main = on[None]
                for n, text in (('Volume Up', 'Λ'), ('Volume Down', 'V'), ('Volume Mute', 'Mute')):
                    g = main[n][0]
                    self.assertEqual((g['variant'], g.get('text', ''), g['states'][0]['image']),
                                     ('button', text, '712x440_gray_nsel.png'), (m, n))
                self.assertEqual(main['Volume Mute'][0]['states'][1]['image'], '712x440_red_sel.png', m)
                g = main['Power'][0]
                self.assertEqual((g['variant'], g.get('text', ''), g['states'][0]['image']),
                                 ('square', '', '440x440_power_outline_red_nsel.png'), m)
                for n in ('Display Control', 'More'):
                    self.assertEqual(main[n][0]['variant'], 'button', (m, n))

    def test_its_close_is_the_white_x(self):
        """The hub's Close at rest is the white X in its ring, on the dark
        header strip of every popup of main and at Help's corner - the
        card's dark X was near invisible there."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Main.dc.html', m)
                N = self.names(m)
                for where in (N['options'], N['display']):
                    g = on[where][where + ' Close'][0]
                    self.assertEqual([st['image'] for st in g['states']], ['white_close.png', 'black_close.png'], where)
                for board, n in (('Laptop.dc.html', 'Laptop Close'), ('Lighting.dc.html', 'Lighting Close'),
                                 ('Help.dc.html', 'Help Close')):
                    _, _, on, _ = self.split(board, m)
                    self.assertEqual(on[None][n][0]['states'][0]['image'], 'white_close.png', (m, n))

    def test_its_tiles_are_translucent_and_rounded(self):
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Main.dc.html', m)
                g = on[self.names(m)['select']]['PC'][0]
                self.assertEqual((g['fill'], g['border']), ('well', 'rounded'), m)

    def test_its_tiles_draw_the_whole_device(self):
        """The template's Select a Source tile is the kit's whole-device
        outline (icons/440x440 White/white_laptop.png, its seed's image 20),
        not the tab's 744x456 glyph its source keeps on the 1035; in both
        states, pressed lit by the fill."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Main.dc.html', m)
                tiles = on[self.names(m)['select']]
                for n, f in (('PC', 'white_pc.png'), ('Laptop', 'white_laptop.png'), ('Doc Cam', 'white_doc-cam.png')):
                    self.assertEqual([s.get('image') for s in tiles[n][0]['states']], [f, f], (m, n))

    def test_its_options_stand_in_one_centred_row(self):
        """Three launchers where the template draws two: one row at the
        template's, each captioned under its tile."""
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Main.dc.html', m)
                opts = on[self.names(m)['options']]
                rects = [opts[n][1] for n in ('Lighting Settings', 'Audio Settings', 'Room Mode')]
                self.assertEqual({r[1] for r in rects}, {self.frame(m)['options']['tiles'][0]['rect'][1]}, m)
                for n in ('Lighting Settings', 'Audio Settings', 'Room Mode'):
                    self.assertEqual(opts[n][0].get('text', ''), '', (m, n))
                    self.assertIn(n + ' Label', opts)
                self.assertEqual(opts['Lighting Settings'][0]['states'][0]['image'], '744x456_lightbulb_white.png')

    def test_every_popup_of_main_wears_the_header_strip(self):
        for m in self.HUBS:
            with self.subTest(hub=m):
                _, _, on, _ = self.split('Main.dc.html', m)
                N = self.names(m)
                for where in (N['select'], N['options'], N['display']):
                    g = next(g for n, (g, _, _) in on[where].items() if n.endswith(' Header'))
                    self.assertEqual((g['kind'], g['fill']), ('panel', 'header'), where)
                _, _, on, _ = self.split('Laptop.dc.html', m)
                self.assertEqual(on[None]['Laptop Title Bar'][0]['fill'], 'header')


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTurbulencesHubs(_HubProbe, unittest.TestCase):
    """Turbulence's 525: its rings down the side bar, its header strip over
    every popup of main."""

    THEME = 'turbulence'

    def test_display_control_and_more_are_the_templates(self):
        """Display Control the template's blank tile with its words over it,
        not a ring its caption spills from; More the ••• glyph with More under
        it, not the kit's grey More key; each inside the bar - grown from the
        template's 75 px where its words, which the template sets at 12 pt,
        need the 525's 18 pt type floor, and no further."""
        _, _, on, _ = self.split('Main.dc.html', 'TLP525T')
        main, band = on[None], self.frame('TLP525T')['right']['rect']
        g = main['Display Control'][0]
        self.assertEqual((g['variant'], g['states'][0]['image'], g['text']),
                         ('source', '504x504_transp_blank_nsel.png', 'Display\nControl'))
        g = main['More'][0]
        self.assertEqual((g['variant'], g['states'][0]['image']), ('source', 'sm-input_elipses_transp_nsel.png'))
        self.assertTrue(g['text'].endswith('More'), g['text'])
        for n in ('Display Control', 'More'):
            self.assertTrue(_inside(main[n][1], band, 0), (n, main[n][1], band))
            self.assertFalse(main[n][2], n)

    def test_a_source_draws_its_device_picture(self):
        """The 525's own sources pin their pictures under the title, fitted,
        as its 1035 does at its top left - each where the 525 draws that
        device (seeds/Turbulence 525.gdl's Laptop, PC and Doc Cam popups):
        its PC 264x260 beside its Laptop's 310x241."""
        if '1152x1152_laptop.png' not in designsys.kit_index(self.profile())['paths']:
            self.skipTest("Turbulence's art is not extracted here (python -m gdl.designsys extract turbulence)")
        for board, name, art, want in (('Laptop.dc.html', 'Laptop', '1152x1152_laptop.png', [196, 45, 310, 241]),
                                       ('PC.dc.html', 'PC', '1152x1152_pc.png', [219, 38, 264, 260]),
                                       ('DocCam.dc.html', 'DocCam', '1152x1152_doc-cam.png', [212, 57, 278, 252])):
            _, _, on, out = self.split(board, 'TLP525T')
            self.assertEqual(out['problems'], [], board)
            g, r, _ = on[None][name + ' Image']
            self.assertEqual((g['kind'], g['image'], r), ('image', art, want), board)
        # The 525 has no Camera Control, and its monitor is its Display
        # Control's and Dual Display Select's, settings popups' and no
        # source's: each takes the Laptop's place.
        for device in ('vc-1', 'monitor'):
            _, _, on, out = self.split('Streaming.dc.html', 'TLP525T',
                                       edit=('role="source"', f'role="source" device="{device}"'))
            self.assertEqual(out['problems'], [], device)
            self.assertEqual(on[None]['Streaming Image'][1], [196, 45, 310, 241], device)

    def test_its_options_are_the_templates_pictures(self):
        _, _, on, _ = self.split('Main.dc.html', 'TLP525T')
        opts = on[self.names('TLP525T')['options']]
        for n, icon in (('Lighting Settings', '900x648_input_lightbulb_nsel.png'),
                        ('Audio Settings', '900x648_input_audio_nsel.png')):
            self.assertEqual((opts[n][0]['variant'], opts[n][0]['states'][0]['image']), ('scene', icon), n)
            self.assertIn(n + ' Label', opts)
        self.assertEqual(opts['Room Mode'][0]['states'][0]['image'], '504x504_transp_blank_nsel.png')


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

    HEADER = ('<x-import component-from-global-scope="ExtronShockwave.Panel" name="Header" style="position: absolute; '
              'left: 0px; top: 0px; width: 1280px; height: 91px"></x-import>')
    TABS = ('<x-import component-from-global-scope="ExtronShockwave.Group" title="Tabs" joined="true" cell="152x91" '
            'gap="0" cap="4" style="position: absolute; left: 336px; top: 0px; width: 608px; height: 91px">'
            + ''.join('<x-import component-from-global-scope="ExtronShockwave.Button" name="Tab%d" variant="source" '
                      'icon="%s" style="width: 152px; height: 91px">%s</x-import>' % (i + 1, icon, word)
                      for i, (icon, word) in enumerate((('laptop_white', 'Laptop'), ('sharelink_white', 'ShareLink'),
                                                        ('pc_white', 'Room PC'), ('doc-cam_white', 'Doc Cam'))))
            + '</x-import>')

    def test_a_group_in_a_hubs_header_keeps_to_the_screen(self):
        """The round-two Shockwave room drew its sources as tabs in its 91 px
        header. On the 525 a band beside main counted a button's touch minimum
        and never a Group's cells, so the header was cut 55 px deep and the
        tabs, grown past it, were centred on it - 19 px above the screen. The
        band is as deep as its tabs, and main - the Well starts it - begins
        under them."""
        _, ctl, _ = self.probe('Home.dc.html', 'TLP525T', edit=(self.HEADER, self.HEADER + self.TABS))
        tabs = [ctl['Tab%d' % i][1] for i in range(1, 5)]
        for r in tabs:
            self.assertTrue(_inside(r, [0, 0, 800, 480]), tabs)
        self.assertGreaterEqual(ctl['Well'][1][1], max(r[1] + r[3] for r in tabs), (ctl['Well'][1], tabs))

    def test_bars_that_leave_main_no_room_are_named(self):
        """What a band holds wins over its quarter of main, so a bar deep
        enough could leave main nothing: named, not drawn as a negative box."""
        tall = self.TABS.replace('cell="152x91"', 'cell="152x600"')
        _, _, out = self.probe('Home.dc.html', 'TLP525T', edit=(self.HEADER, self.HEADER + tall))
        self.assertTrue(any('carves from its main leave it' in p for p in out['problems']), out['problems'])


    def test_a_hubs_level_runs_beside_its_up_and_down(self):
        for panel in ('TLP525T', 'TLP535T'):
            with self.subTest(panel=panel):
                _level_beside(self, 'shockwave', panel, self.probe)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTurbulencesHubHeader(_Probe, unittest.TestCase):
    """The README reads Turbulence's hub rows off its header as its Layout
    fills it - six source tabs with the seed's captions - from the depth the
    bundle gives them (`layout.hub_header`). Measured again here, so the
    profile cannot drift from what the bundle draws."""

    CANVAS = os.path.join(HERE, 'data', 'design-hub-turbulence')
    THEME = 'turbulence'

    def test_the_profiles_header_depth_is_the_bundles(self):
        depth = designsys.load(self.THEME)['layout']['hub_header']['depth']
        for model, want in sorted(depth.items()):
            with self.subTest(model=model):
                _, ctl, _ = self.probe('Tabs.dc.html', model)
                self.assertEqual(max(ctl['Tab%d' % i][1][3] for i in range(1, 7)), want)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestShockwavesHubHeader(TestTurbulencesHubHeader):
    """Shockwave's Layout heads its pages with joined source tabs too: the
    round-three room's 525 header came out as deep as them, where the README
    had taken a button's 66."""

    CANVAS = os.path.join(HERE, 'data', 'design-hub-shockwave')
    THEME = 'shockwave'


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
class TestARailsCaption(_Probe, unittest.TestCase):
    """A button in a Rail fills the rail across, so its caption needs only
    the button's own padding, 10 px a side: the round-three Mach room's Mute -
    its Muted caption at the 525's 18 pt - was refused at 100 px across a
    98 px rail, held to the 24 px a loose button keeps."""

    CANVAS = os.path.join(HERE, 'data', 'design-panels-mach')
    THEME = 'mach'
    PAGE = ('does="The room\'s home page: share a source, set volume, end the call." style="position: '
            'absolute; left: 0px; top: 0px; width: 1280px; height: 800px">')
    RAIL = ('<x-import component-from-global-scope="ExtronMach.Rail" style="position: absolute; left: 1161px; '
            'top: 80px; width: 103px; height: 650px">'
            '<x-import component-from-global-scope="ExtronMach.Button" name="RailMute" variant="solid" '
            'states=\'[{"name":"Off","text":"Mute"},{"name":"On","fill":"alert","color":"text","text":"Muted"}]\' '
            'style="width: 103px; height: 60px">Mute</x-import></x-import>')

    def test_a_captioned_button_fills_the_hubs_rail(self):
        _, ctl, out = self.probe('Home.dc.html', 'TLP525T', edit=(self.PAGE, self.PAGE + self.RAIL))
        self.assertEqual([p for p in out['problems'] if 'RailMute' in p], [])
        self.assertFalse(ctl['RailMute'][2], ctl['RailMute'][1])


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
class TestAfterburnsRowsOnThe320(_Probe, unittest.TestCase):
    """The round-four Afterburn room (tests/data/round4-afterburn) on the 320,
    whose page reflows into rows."""

    CANVAS = os.path.join(HERE, 'data', 'round4-afterburn')

    def test_a_popup_region_in_a_row_is_its_popups_size(self):
        """A popup inherits its reference's size (Standards p.70): the region
        a row holds is rounded as the popup is scaled, not up - the 880x525
        region came out 223x133 over its 222x133 popups. Held on the 300,
        whose seed has standard popups - the 320 makes each source a page of
        its own and leaves the region off - with a region and popup 690 wide,
        which a row there holds across (241.04 and 183.4 px at its scale)."""
        narrow = 'width: 690px; height: 525px'
        _, ctl, _ = self.probe('MainSD.dc.html', 'TLP300M', ('width: 880px; height: 525px', narrow))
        page, _, _ = self.probe('Laptop.dc.html', 'TLP300M', ('kind="popup"', 'kind="popup" width="690" height="525"'))
        self.assertEqual(page['kind'], 'popup')
        self.assertEqual(page['size'], [241, 183])
        self.assertEqual(ctl['Controls'][1][2:], page['size'])

    def test_a_pages_own_control_grown_at_its_edge_stays_on_the_page(self):
        """Grown about its centre, a control drawn flush with the screen's edge
        - Afterburn's left rail at x 0 - crossed it, and Build moves a control
        that crosses its page's edge: it grows inward instead, on the panel
        drawn (the Start page's Lights) as on the 725."""
        for board, model in (('Main.dc.html', 'TLP1035T'), ('MainSD.dc.html', 'TLP725T')):
            page, ctl, _ = self.probe(board, model)
            W, H = designsys.models(designsys.load('afterburn'))[model]['size']
            for n, (g, r, _) in ctl.items():
                self.assertTrue(_inside(r, [0, 0, W, H], 0), (board, model, n, r))

    def test_a_main_areas_group_grown_at_its_edge_stays_in_it(self):
        """In a MainArea too, on every theme: the sources Group's region, grown
        to the 525's tiles about its centre, stood 17 px above the screen."""
        _, ctl, _ = self.probe('MainSD.dc.html', 'TLP525T')
        T = designsys.models(designsys.load('afterburn'))['TLP525T']
        self.assertTrue(_inside(ctl['Sources Region'][1], [0, 0] + T['size'], 0), ctl['Sources Region'][1])


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestAfterburnsRevisedRowsOnThe320(_Probe, unittest.TestCase):
    """Round four's revised Afterburn room (tests/data/round4-afterburn-revised)
    on the 320, where a page's own controls - the left rail's heading and its
    Group - and its MainArea's are laid out in one set of rows. They were two,
    each centred on the screen, so the heading landed on a main-area control
    whatever the designer moved: Start's Lights Heading on Start, Call's VTC
    Heading on Camera Presets - and Main SD's Settings heading and button on
    its popup region, which no check reads as a touch target."""

    CANVAS = os.path.join(HERE, 'data', 'round4-afterburn-revised')
    # Each working page and the title of its left rail's Group, under a
    # heading Label named for it.
    PAGES = (('Main.dc.html', 'Lights'), ('Call.dc.html', 'VTC'), ('MainSD.dc.html', 'Settings'))
    RAIL = ('Volume Down', 'Volume', 'Volume Up', 'Mute', 'Help', 'Power')

    def on_page(self, board):
        """{name: rect} of what the 320 draws on the page itself, not on a
        Group's pages of its own."""
        _, _, out = self.probe(board, 'TLP320M')
        return {json.loads(c['gdl']).get('name'): [round(v) for v in c['rect']]
                for c in out['controls'] if c.get('part') is None}

    def test_nothing_on_a_page_meets(self):
        for board, _ in self.PAGES:
            got = sorted(self.on_page(board).items())
            for i, (a, ra) in enumerate(got):
                for b, rb in got[i + 1:]:
                    self.assertFalse(_overlaps(ra, rb), (board, a, ra, b, rb))

    def test_the_rows_stand_in_main_over_the_rail(self):
        """And the left rail's heading and Group are rows of their own among
        the main area's, not a second set laid over the same depth: apart,
        each centred, the two shared their rows whatever the designer moved."""
        T = designsys.models(designsys.load('afterburn'))['TLP320M']
        for board, title in self.PAGES:
            got = self.on_page(board)
            for n, r in got.items():
                self.assertTrue(_inside(r, T['rail'] if n in self.RAIL else T['main'], 0), (board, n, r))
            own = {n: r for n, r in got.items() if n in (title, title + ' Heading')}
            area = {n: r for n, r in got.items() if n not in own and n not in self.RAIL}
            self.assertEqual(len(own), 2, (board, own))
            self.assertTrue(area, board)
            for a, ra in own.items():
                for b, rb in area.items():
                    self.assertFalse(ra[1] < rb[1] + rb[3] and rb[1] < ra[1] + ra[3], (board, a, ra, b, rb))

    def test_a_heading_stands_beside_the_group_it_heads(self):
        """On the 320 a Group is the one button that opens its pages, captioned
        with its title: the heading drawn over it on the 1035 stays with it, at
        its left in its row, with nothing between them."""
        gap = designsys.models(designsys.load('afterburn'))['TLP320M']['gap']
        for board, title in self.PAGES:
            got = self.on_page(board)
            head, grp = got[title + ' Heading'], got[title]
            self.assertTrue(grp[1] <= head[1] and head[1] + head[3] <= grp[1] + grp[3], (board, head, grp))
            self.assertEqual(grp[0] - (head[0] + head[2]), gap, (board, head, grp))

    def test_a_source_is_a_page_of_its_own(self):
        """The 320's seed has no standard popup to clone (its series' `kinds`),
        and its template gives each source a page of its own: a source popup
        is a page there, named as it is, on the page's photo, what is put in
        it in rows in main and a Back at the foot's left - where a Group's
        pages stand theirs - that goes back to the page whose button shows
        it. Kept a popup, it was shown from the Sources Group's pages, which
        hold no reference to its group: the ID map refused all four."""
        T = designsys.models(designsys.load('afterburn'))['TLP320M']
        _, ctl, out = self.probe('MainSD.dc.html', 'TLP320M')
        group_back = ctl['Sources Back'][1]
        for board, name in (('Laptop.dc.html', 'Laptop'), ('DocCam.dc.html', 'Doc Cam')):
            page, got, out = self.probe(board, 'TLP320M')
            self.assertEqual((page['kind'], page['name'], page.get('group'), page['size']),
                             ('page', name, None, [320, 240]), board)
            self.assertEqual(page['background_image'], T['backgrounds']['blue-slate']['image'])
            self.assertEqual(out.get('problems', []), [], board)
            back = got[name + ' Back']
            self.assertTrue(back[0].get('derived') and back[0].get('back'), back)
            self.assertNotIn('nav', back[0])
            self.assertEqual(back[1], group_back)
            for n, r in self.on_page(board).items():
                if n != name + ' Back':
                    self.assertTrue(_inside(r, T['main'], 0), (board, n, r))
        # A Group in it is the one button that opens its pages, its heading at
        # its left in its row, as on a page; and its pages' Back is the page.
        _, got, _ = self.probe('DocCam.dc.html', 'TLP320M')
        zoom, head = got['Zoom'][1], got['Zoom Label'][1]
        self.assertTrue(zoom[1] <= head[1] and head[1] + head[3] <= zoom[1] + zoom[3], (head, zoom))
        self.assertEqual(got['Zoom Back'][0].get('nav'), 'Doc Cam')
        # Drawn on the 1035 it is the popup it was drawn as.
        page, _, _ = self.probe('Laptop.dc.html', 'TLP1035T')
        self.assertEqual((page['kind'], page['group']), ('popup', 'Sources'))

    def test_main_sd_leaves_its_region_off(self):
        """Each source a page of its own, the popup region has nothing to
        show on the 320: it is left off (the page's `left`), named, as the
        region page's 320 leaves its Center - and the Divider drawn between
        the sources and the region stands between the sources and the left
        rail's row, clear of each."""
        page, ctl, out = self.probe('MainSD.dc.html', 'TLP320M')
        self.assertEqual(page.get('left'), ['Controls'])
        self.assertNotIn('Controls', self.on_page('MainSD.dc.html'))
        self.assertIn("Main SD's Controls is left off the TLP320M - its seed has no standard popup, and each source "
                      'is a page of its own', out.get('warnings', []))
        got = self.on_page('MainSD.dc.html')
        src, st, div = (got[n] for n in ('Sources', 'Settings', 'Divider'))
        self.assertLess(src[1] + src[3], div[1])
        self.assertLess(div[1] + div[3], st[1])

    def test_a_line_keeps_clear_of_the_rows_it_stands_between(self):
        """A Line between two rows stands in the gap between them with 2 px
        clear each side: between Main SD's sources and its popup region on
        the 300 (whose seed has standard popups, so the region stays), the
        Divider was given exactly its own 2 px and touched both."""
        _, ctl, out = self.probe('MainSD.dc.html', 'TLP300M')
        src, div, reg = (ctl[n][1] for n in ('Sources', 'Divider', 'Controls'))
        self.assertGreaterEqual(div[1] - (src[1] + src[3]), 2, (src, div))
        self.assertGreaterEqual(reg[1] - (div[1] + div[3]), 2, (div, reg))


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
        """Nothing is dropped: a page whose rows its main area cannot hold on
        a panel says so, with the panel, the room they needed and the room
        main has, as the README's Kind gives it."""
        extra = ('<x-import component-from-global-scope="ExtronAfterburn.Clock" name="Date"',
                 '<x-import component-from-global-scope="ExtronAfterburn.Label" name="Extra1" type="title" '
                 'style="position: absolute; left: 0px; top: 630px; width: 916px; height: 30px">More</x-import>\n'
                 '<x-import component-from-global-scope="ExtronAfterburn.Label" name="Extra2" type="title" '
                 'style="position: absolute; left: 0px; top: 662px; width: 916px; height: 30px">More</x-import>\n'
                 '<x-import component-from-global-scope="ExtronAfterburn.Clock" name="Date"')
        _, _, out = self.probe('Home.dc.html', 'TLP320M', edit=extra)
        deep = designsys.models(designsys.load('afterburn'))['TLP320M']['main'][3] - 4
        self.assertTrue(any(p.startswith("Huddle Home's rows need ") and f"of the {deep} a TLP320M's main holds" in p
                            for p in out['problems']), out['problems'])

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
        """On a Design canvas nothing is injected: `preview` picks the panel."""
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

    def test_a_column_too_narrow_for_previous_and_next_stacks_their_arrows(self):
        """A one-cell column paged on a 525 - Afterburn's left rail in a Group -
        has no room for Previous and Next side by side, nor for either word:
        they are arrows at the touch minimum, one over the other under its
        cells, each in the box and clear of the rest. Side by side they came
        out 2 px apart, and 'Previous' wider than the box."""
        edit = ('title="Sources" cell="54x54" gap="16" cap="4" style="position: absolute; left: 326px; top: 40px; '
                'width: 264px; height: 240px"',
                'title="Sources" cell="54x54" gap="16" cap="1" style="position: absolute; left: 326px; top: 40px; '
                'width: 60px; height: 420px"')
        _, ctl, out = self.probe('Groups.dc.html', 'TLP525T', edit=edit)
        self.assertEqual([p for p in out['problems'] if 'Sources' in p], [])
        parts = {p['name']: p for p in self.parts(out) if p.get('group') == 'Group Test Sources'}
        self.assertGreater(len(parts), 2)
        by = {}
        for c in out['controls']:
            g = json.loads(c['gdl'])
            if c.get('part') is not None:
                by.setdefault(self.parts(out)[c['part']]['name'], []).append((g, [round(v) for v in c['rect']]))
        for name, part in parts.items():
            box = [0, 0] + part['size']
            nav = [(g, r) for g, r in by[name] if g['name'].endswith(('Previous', 'Next'))]
            self.assertTrue(nav, name)
            for g, r in by[name]:
                self.assertTrue(_inside(r, box), (name, g['name'], r, box))
            for (g1, a), (g2, b) in ((x, y) for i, x in enumerate(by[name]) for y in by[name][i + 1:]):
                self.assertFalse(_overlaps(a, b), (name, g1['name'], g2['name']))
            for g, r in nav:
                self.assertIn(g['text'], ('‹', '›'), g['name'])

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

    def test_a_group_in_a_modal_lays_out_in_place_on_a_525(self):
        """A 525's Group is a popup group shown in a region of the page, and a
        modal is a popup, which can show none: the round-two conference rooms'
        Lighting Presets built a popup group no page referenced. In a modal it
        lays out in place, as it fits."""
        _, ctl, out = self.probe('Lights.dc.html', 'TLP525T')
        self.assertEqual(out['parts'], [])
        self.assertNotIn('popup_ref', [json.loads(c['gdl'])['kind'] for c in out['controls']])
        for n in ('P1', 'P2', 'P3', 'P4'):
            self.assertTrue(_inside(ctl[n][1], [0, 0, 800, 480]), (n, ctl[n][1]))
        self.assertEqual(out['problems'], [])

    def test_a_group_a_modal_cannot_hold_is_refused_by_name(self):
        """Nor can it page there - its pages would be popups - so a Group too
        big for its box in a modal is named, with what to do."""
        _, _, out = self.probe('Crowd.dc.html', 'TLP525T')
        self.assertEqual(out['parts'], [])
        self.assertTrue(any('Scenes' in p and 'TLP525T' in p and 'cannot page in a modal' in p
                            for p in out['problems']), out['problems'])

    def test_a_group_one_row_deep_pages_with_previous_and_next_beside_it(self):
        """On a 525 a row of presets drawn one cell deep had no room under it
        for Previous and Next: the Group was refused, and its derived buttons
        overlapped its members (Mach's Sources and Lighting, Shockwave's Camera
        Presets, Turbulence's Sources). Beside the row they fit."""
        _, _, out = self.probe('Strip.dc.html', 'TLP525T')
        self.assertEqual(out['problems'], [])
        parts = self.parts(out)
        strip = [i for i, p in enumerate(parts) if p.get('group') == 'Strip Test Strip']
        self.assertGreaterEqual(len(strip), 2)
        on = {}
        for c in out['controls']:
            on.setdefault(c.get('part'), []).append((json.loads(c['gdl']).get('name'), c['rect']))
        members = {'R%d' % i for i in range(1, 7)}
        self.assertEqual(sorted(n for i in strip for n, _ in on.get(i, []) if n in members), sorted(members))
        for i in strip:
            navs = [(n, r) for n, r in on[i] if n in ('Strip Previous', 'Strip Next')]
            self.assertTrue(navs, parts[i]['name'])
            for n, r in navs:
                self.assertTrue(_inside(r, [0, 0] + parts[i]['size']), (n, r, parts[i]['size']))
                for m, mr in on[i]:
                    if m in members:
                        self.assertFalse(_overlaps(r, mr), (n, r, m, mr))

    def test_a_box_too_narrow_for_their_words_gets_arrows(self):
        """Mach's Sources - 113 px cells in a 320 px box - had no room for
        Previous and Next in words even beside one cell; touch-sized arrows
        fit. The controls keep their names: the ID map still says which."""
        _, _, out = self.probe('Pair.dc.html', 'TLP525T')
        self.assertEqual(out['problems'], [])
        on = {}
        for c in out['controls']:
            g = json.loads(c['gdl'])
            on.setdefault(c.get('part'), {})[g.get('name')] = (g, c['rect'])
        navs = [v for part in on.values() for n, v in part.items() if n in ('Pair Previous', 'Pair Next')]
        self.assertTrue(navs)
        self.assertEqual({g.get('text') for g, _ in navs}, {'\u2039', '\u203a'})
        for part in on.values():
            for n, (g, r) in part.items():
                if n in ('Pair Previous', 'Pair Next'):
                    for m, (_, mr) in part.items():
                        if m in ('Q1', 'Q2', 'Q3', 'Q4'):
                            self.assertFalse(_overlaps(r, mr), (n, r, m, mr))


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestABarThemeOnThe320(_Probe, unittest.TestCase):
    """A bar theme's page on the 320, as Extron's own 320 templates draw one:
    its header bar becomes the 36 px title strip, and what the page holds -
    its own controls, its MainArea's and its Rail's, since the 320 has no rail
    - reflows in rows in design order under it, going on over pages of its
    own (Home 2, Home 3) with Next and Previous where one screen cannot hold
    them. The round-three conference rooms, drawn for the 1035 and the 525,
    needed 201 to 359 px of the 320's 240 and were refused."""

    CANVAS = os.path.join(HERE, 'data', 'design-room-mach')
    THEME = 'mach'
    ORDER = ('SourceHeading', 'DisplayState', 'JoinCall', 'DateTime')
    # What a board cannot do on the 320, by name. A modal holds one screen:
    # a popup over the page, it does not go on over more, and its designer's
    # four steps, each two lines on the 320, and the AV desk are too deep.
    REFUSED = {'Help.dc.html': ["Help needs 247 px of a TLP320M's 240 - it does not fit"]}
    STRIP = [0, 0, 320, 36]
    MAIN = [0, 36, 320, 204]

    def split(self, board):
        """The probe's output, its parts, and each part's controls by part
        name - None for the page itself."""
        _, _, out = self.probe(board, 'TLP320M')
        parts = [json.loads(p['gdl']) for p in out['parts']]
        on = {}
        for c in out['controls']:
            i = c.get('part')
            on.setdefault(None if i is None else parts[i]['name'], []).append(
                (json.loads(c['gdl']), [round(v) for v in c['rect']]))
        return out, parts, on

    @staticmethod
    def over(parts, page):
        """The pages a page goes on over: Home 2, Home 3."""
        return [p for p in parts if p['kind'] == 'page' and p.get('host') == page
                and re.fullmatch(re.escape(page) + r' \d+', p['name'])]

    def test_every_board_fits_the_320(self):
        for board in sorted(f for f in os.listdir(self.CANVAS) if f.endswith('.dc.html')):
            with self.subTest(board=board):
                out, _, _ = self.split(board)
                self.assertEqual(out['problems'], self.REFUSED.get(board, []))

    def test_the_page_goes_on_over_pages_of_its_own(self):
        _, parts, on = self.split('Main.dc.html')
        more = self.over(parts, 'Home')
        self.assertTrue(more)
        self.assertEqual([p['name'] for p in more], ['Home %d' % i for i in range(2, len(more) + 2)])
        for p in more:
            self.assertEqual(p['size'], [320, 240])
        touch = designsys.models(designsys.load(self.THEME))['TLP320M']['touch']
        names = ['Home'] + [p['name'] for p in more]
        for i, here in enumerate(names):
            ctl = {g.get('name'): (g, r) for g, r in on[None if i == 0 else here]}
            for word, to in (('Next', names[i + 1] if i + 1 < len(names) else None),
                             ('Previous', names[i - 1] if i else None)):
                if to is None:
                    self.assertNotIn(here + ' ' + word, ctl)
                    continue
                g, r = ctl[here + ' ' + word]
                self.assertEqual((g['kind'], g['nav'], g['derived']), ('button', to, True))
                self.assertTrue(_inside(r, self.MAIN), (here, word, r))
                self.assertGreaterEqual(min(r[2:]), touch, (here, word, r))

    def test_the_title_strip_heads_each_of_them(self):
        _, parts, on = self.split('Main.dc.html')
        for where in [None] + [p['name'] for p in self.over(parts, 'Home')]:
            strip = [g for g, r in on[where] if g['kind'] == 'panel' and r == self.STRIP]
            self.assertEqual(len(strip), 1, where)
            self.assertEqual(bool(strip[0].get('derived')), where is not None, where)

    def test_the_rest_lies_in_main_in_design_order_and_once(self):
        _, parts, on = self.split('Main.dc.html')
        wheres = [None] + [p['name'] for p in self.over(parts, 'Home')]
        seen, at = [], {}
        for n, where in enumerate(wheres):
            for g, r in on[where]:
                if g['kind'] == 'panel' and r == self.STRIP:
                    continue
                self.assertTrue(_inside(r, self.STRIP) or _inside(r, self.MAIN), (where, g.get('name'), r))
                if not g.get('derived'):
                    seen.append(g.get('name'))
                    at[g.get('name')] = (n, r[1])
        self.assertEqual(len(seen), len(set(seen)), seen)
        self.assertEqual([at[n] for n in self.ORDER], sorted(at[n] for n in self.ORDER))

    def test_a_page_with_no_header_bar_still_goes_on_over(self):
        """With no bar across its top the strip is empty, and the rest still
        goes on over pages - a review found the strip's labels read before
        anything set them, and the whole artboard drew nothing."""
        if self.THEME != 'mach':
            self.skipTest("Mach's room is the one with a header Panel to take away")
        bar = ('<x-import component-from-global-scope="ExtronMach.Panel" name="HeaderBar" fill="shade" '
               'border="rect" style="position: absolute; left: 0px; top: 0px; width: 1280px; height: 64px">'
               '</x-import>')
        _, _, out = self.probe('Main.dc.html', 'TLP320M', edit=(bar, ''))
        self.assertEqual(out['problems'], [])
        self.assertTrue(self.over([json.loads(p['gdl']) for p in out['parts']], 'Home'))

    def test_a_heading_goes_on_with_the_row_it_heads(self):
        """The room's Volume label fitted at Home 2's foot and the volume it
        heads did not: it stood there alone, its volume over the page on
        Home 3. It goes on with it."""
        if self.THEME != 'mach':
            self.skipTest("Mach's room is the one whose heading met a page's foot")
        _, parts, on = self.split('Main.dc.html')
        where = {g.get('name'): w for w, cs in on.items() for g, _ in cs if not g.get('derived')}
        self.assertEqual(where['VolumeLabel'], where['Volume'])

    def test_a_group_on_a_later_page_comes_back_to_it(self):
        """A Group's own pages, opened from Home 2, go Back to Home 2."""
        _, parts, on = self.split('Main.dc.html')
        for where in [p['name'] for p in self.over(parts, 'Home')]:
            for g, _ in on[where]:
                if g['kind'] == 'button' and g.get('derived') and str(g.get('nav', '')).startswith(where + ' '):
                    if g['name'].endswith((' Next', ' Previous')):
                        continue
                    group = [p for p in parts if p['name'] == g['nav']]
                    self.assertEqual(group[0]['host'], where)
                    backs = [b for b, _ in on[g['nav']] if b.get('name', '').endswith(' Back')]
                    self.assertEqual([b['nav'] for b in backs], [where])


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestABarHoldsWhatIsInIt(_Probe, unittest.TestCase):
    """A bar drawn as a Panel grows with what it holds: on the 525 the
    round-three Shockwave room's header came out 71 px deep and its source
    tabs, grown to the touch minimum, 94 - they stood below the bar."""

    CANVAS = os.path.join(HERE, 'data', 'design-room-shockwave')
    THEME = 'shockwave'

    def test_the_header_holds_its_tabs_on_the_525(self):
        _, ctl, out = self.probe('Main.dc.html', 'TLP525T')
        self.assertEqual(out['problems'], [])
        bar = ctl['Header'][1]
        self.assertEqual(bar[1], 0)
        for n in ('Laptop', 'ShareLink', 'RoomPC', 'DocCamera'):
            tab = ctl[n][1]
            self.assertLessEqual(tab[1] + tab[3], bar[1] + bar[3], (n, tab, bar))

    def test_the_footer_still_ends_at_the_screens_foot(self):
        _, ctl, _ = self.probe('Main.dc.html', 'TLP525T')
        foot = ctl['Footer'][1]
        self.assertLessEqual(foot[1] + foot[3], 480)
        for n in ('MicMute', 'HelpBtn'):
            r = ctl[n][1]
            self.assertGreaterEqual(r[1], foot[1], (n, r, foot))


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestAGroupsGapGivesWay(_Probe, unittest.TestCase):
    """A Group's gap, which scales with the page, gives way to its cells - down
    to the panel's own 2 mm - before the Group pages or is refused: the
    round-three Turbulence designer narrowed its Lighting gaps by hand before
    its cells fitted the 525."""

    CANVAS = os.path.join(HERE, 'data', 'design-room-turbulence')
    THEME = 'turbulence'
    WIDE = ('title="Lighting" cell="400x100" gap="24"', 'title="Lighting" cell="400x100" gap="80"')

    def test_a_wide_gap_narrows_to_fit_the_525(self):
        _, ctl, out = self.probe('Lighting.dc.html', 'TLP525T', edit=self.WIDE)
        self.assertEqual(out['problems'], [])
        gap = designsys.models(designsys.load(self.THEME))['TLP525T']['gap']
        cells = sorted((r for g, r, _ in ctl.values() if g.get('kind') == 'button' and r[3] == 66 and r[2] > r[3]), key=lambda r: (r[1], r[0]))
        self.assertEqual(len(cells), 4, cells)
        across = cells[1][0] - (cells[0][0] + cells[0][2])
        self.assertGreaterEqual(across, gap)

    def test_where_it_fits_the_gap_is_as_drawn(self):
        """On the 1035 it is drawn for, the wide gap stays wide."""
        _, ctl, out = self.probe('Lighting.dc.html', None, edit=self.WIDE)
        cells = sorted((r for g, r, _ in ctl.values() if g.get('kind') == 'button' and r[2] == 400), key=lambda r: (r[1], r[0]))
        self.assertEqual(len(cells), 4, cells)
        self.assertEqual(cells[1][0] - (cells[0][0] + cells[0][2]), 80)


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestShockwaveOnThe320(TestABarThemeOnThe320):
    CANVAS = os.path.join(HERE, 'data', 'design-room-shockwave')
    THEME = 'shockwave'
    ORDER = ('RoomName', 'SourceStatus', 'Display', 'DateTime')
    # Its designer's nine lines of help, as Mach's four steps, are too deep;
    # and the 320's seed has no date and time control to clone.
    CLOCK = ["DateTime is a date and time, which the TLP320M's seed cannot build"]
    REFUSED = {'Help.dc.html': ["Help needs 306 px of a TLP320M's 240 - it does not fit"],
               'Main.dc.html': CLOCK, 'Call.dc.html': CLOCK}


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTurbulenceOnThe320(TestABarThemeOnThe320):
    CANVAS = os.path.join(HERE, 'data', 'design-room-turbulence')
    THEME = 'turbulence'
    ORDER = ('DisplayStatus', 'SourceStatus', 'OpenCall', 'Clock')
    # The 320's seed has no date and time control to clone.
    CLOCK = ["Clock is a date and time, which the TLP320M's seed cannot build"]
    REFUSED = {'Main.dc.html': CLOCK, 'Call.dc.html': CLOCK}


class _PagesProbe(_Probe):
    """A bar theme's region canvas (tests/data/design-regions-<theme>) on the
    320, drawn as its own template draws its pages
    (docs/superpowers/specs/2026-10-22-region-frame-design.md, PR7): no bar,
    rail or footer; every page under a 36 px title strip; Main the template's
    Select a Source, holding the Header's tabs as the 320's buttons; each
    source a page of its own, going on over a second joined by More and Back;
    what the template has no place for on pages Main's More leads to; the
    question and the waits pages on the template's rounded box; the volume
    the template's program-shown modal."""

    PANEL = 'TLP320C'

    @classmethod
    def setUpClass(cls):
        cls.CANVAS = os.path.join(HERE, 'data', f'design-regions-{cls.THEME}')
        super().setUpClass()

    def profile(self):
        return designsys.load(self.THEME)

    def row(self):
        return designsys.models(self.profile())[self.PANEL]

    def frame(self):
        return self.row()['frame']

    def item(self, rec, role):
        """A page record's item of `role`, in whichever band it stands."""
        return next(it for b in ('top', 'bottom', 'left', 'right', 'center') if rec.get(b)
                    for it in rec[b]['items'] if it['role'] == role)

    def split(self, board, edit=None):
        """The page, its derived parts by name, and {part or None: {name:
        (data-gdl, rect, overflow)}} - the page's own under None."""
        page, _, out = self.probe(board, self.PANEL, edit)
        parts = [json.loads(p['gdl']) for p in out['parts']]
        on = {None: {}}
        for c in out['controls']:
            g = json.loads(c['gdl'])
            where = parts[c['part']]['name'] if c.get('part') is not None else None
            on.setdefault(where, {})[g.get('name')] = (g, [round(v) for v in c['rect']], c.get('overflow'))
        return page, {p['name']: p for p in parts}, on, out

    def assertAt(self, got, want, msg=None):
        """At the template's rect, or grown about it to what it needs here."""
        self.assertTrue(got == want or _inside(want, got), (got, want, msg))

    def mine(self, on):
        """Every canvas control the page and its parts draw: {name: (where, data-gdl, rect)}."""
        return {n: (w, g, r) for w, ctl in on.items() for n, (g, r, _) in ctl.items() if not g.get('derived')}

    def test_main_is_the_templates_select_a_source(self):
        """Main under the template's own strip - its ground, its words, its
        seed ID - and the Header's tabs under it as the 320's buttons: the
        same controls as the 1035's, by name, nav and does, at least the
        touch minimum, one set, clear of each other; what the 320 has no
        place for (the clock, the Center's popup region) named and left."""
        page, parts, on, out = self.split('Main.dc.html')
        self.assertEqual(out['problems'], [])
        F, main = self.frame(), on[None]
        self.assertEqual(out['warnings'],
                         [f"Main's Date Time is left off the {self.PANEL} - its template draws no clock",
                          f"Main's Controls is left off the {self.PANEL} - its template shows each source as a "
                          'page of its own'])
        self.assertEqual(page['left'], ['Date Time', 'Controls'])
        self.assertEqual((page['kind'], page['size']), ('page', [320, 240]))
        head = self.item(F['home'], 'heading')
        g, r, _ = main['Main Title']
        self.assertEqual((g['kind'], g['text'], g['id'], g['derived'], r),
                         ('label', head['text'], head['id'], True, head['rect']))
        g, r, _ = main['Main Strip']
        self.assertEqual((g['kind'], g['derived'], r), ('panel', True, F['home']['top']['surfaces'][0]['rect']))
        _, ctl1035, _ = self.probe('Main.dc.html', 'TLP1035T')
        touch, joined = self.row()['touch'], set()
        tiles = []
        for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming'):
            g, r, over = main[n]
            self.assertFalse(g.get('derived'), n)
            self.assertEqual((g['nav'], g['does']), (ctl1035[n][0]['nav'], ctl1035[n][0]['does']), n)
            self.assertGreaterEqual(min(r[2], r[3]), touch, (n, r))
            self.assertTrue(_inside(r, F['center']['rect'], 0), (n, r))
            self.assertFalse(over, n)
            joined.add(g.get('joined'))
            tiles.append(r)
        self.assertEqual(len(joined), 1)
        self.assertFalse([(a, b) for i, a in enumerate(tiles) for b in tiles[i + 1:] if _overlaps(a, b)])
        self.assertEqual(_gaps(main, self.PANEL), [])

    def test_mains_more_leads_to_what_the_320_keeps_off_its_pages(self):
        """The template keeps no display, settings, mute, help or power on
        its pages: Main's More - the template's, at its place with its seed
        ID - leads on to pages of Main's own, each under the strip, back by
        the second page's Back with its seed ID, more by More; the Sections,
        the volume's heading and Mute, Room Mode, Help and Power on them,
        each the same control as the 1035's."""
        _, parts, on, out = self.split('Main.dc.html')
        F = self.frame()
        more, back = self.item(F, 'more'), self.item(F['second'], 'back')
        g, r, _ = on[None]['Main More']
        self.assertEqual((g['kind'], g['derived'], g['id'], g['nav']), ('button', True, more['id'], 'Main 2'))
        self.assertAt(r, more['rect'])
        later = sorted((p for p in parts.values() if p['kind'] == 'page'), key=lambda p: p['name'])
        self.assertTrue(later)
        self.assertEqual([p['name'] for p in later], [f'Main {i}' for i in range(2, len(later) + 2)])
        for i, p in enumerate(later):
            ctl = on[p['name']]
            self.assertEqual((p['size'], p['host']), ([320, 240], 'Main'), p)
            g, r, _ = ctl[p['name'] + ' Back']
            self.assertEqual((g['derived'], g['nav']), (True, 'Main' if i == 0 else later[i - 1]['name']))
            if i == len(later) - 1 or self.THEME == 'mach':
                self.assertAt(r, back['rect'])
            self.assertEqual(g['id'], back['id'])
            self.assertTrue(ctl[p['name'] + ' Title'][0]['text'], p)
            self.assertEqual(ctl[p['name'] + ' Title'][1][1], 0)
            self.assertEqual((p['name'] + ' More') in ctl, i < len(later) - 1, p)
            self.assertEqual(_gaps(ctl, self.PANEL), [], p)
            for n, (g, r, _) in ctl.items():
                self.assertTrue(_inside(r, [0, 0, 320, 240], 0), (p['name'], n, r))
        here = self.mine(on)
        for n in ('Display Heading', 'Display On', 'Display Off', 'Display Mute', 'Lighting Settings',
                  'Audio Settings', 'Volume Heading', 'Volume Mute', 'Room Mode', 'Help', 'Power'):
            self.assertIn(here.get(n, (None,))[0], [p['name'] for p in later], n)
        self.assertEqual(here['Help'][1]['nav'], 'Help')
        self.assertEqual(here['Power'][1]['nav'], 'ConfirmPower')
        self.assertEqual(here['Lighting Settings'][1]['nav'], 'Lighting')

    def test_nothing_on_the_canvas_is_dropped(self):
        """Every control the 1035 draws from the canvas is on the 320 - on
        Main, a page it goes on over or the volume's modal - but what its
        page names as left off."""
        _, ctl1035, _ = self.probe('Main.dc.html', 'TLP1035T')
        mine = {n for n, (g, _, _) in ctl1035.items() if not g.get('derived')}
        page, _, on, _ = self.split('Main.dc.html')
        self.assertEqual(mine - set(self.mine(on)), set(page['left']))

    def test_the_volume_is_the_templates_modal(self):
        """The volume slider is the level in the template's Volume modal - a
        full-screen modal the program shows, its strip and level where the
        template draws them, put away by its transparent Cancel where the
        template has one (its seed ID)."""
        _, parts, on, _ = self.split('Main.dc.html')
        V = self.frame()['volume']
        part = parts[V['popup']]
        self.assertEqual((part['kind'], part['modal'], part.get('reached_by')), ('popup', True, 'program'))
        ctl = on[V['popup']]
        g, r, _ = ctl['Volume']
        self.assertEqual((g['kind'], r), ('level', V['level']['rect']))
        self.assertNotIn('derived', g)
        self.assertEqual([ctl[V['popup'] + ' Strip' + (f' {i + 1}' if i else '')][1] for i in range(len(V['surfaces']))],
                         [s['rect'] for s in V['surfaces']])
        if V['cancel']:
            g, r, _ = ctl[V['popup'] + ' Cancel']
            self.assertEqual((g['derived'], g['id'], r), (True, V['cancel']['id'], V['cancel']['rect']))
        else:
            self.assertNotIn(V['popup'] + ' Cancel', ctl)
        # The template's colours as it measures them (Mach's #4B4B4C strip and
        # #E4EDF5 bar), not the nearest token: its chrome is exempt from the
        # six-colour cap.
        def rgba(v):
            return (v + 'FF' if len(v) == 7 else v).upper()
        for i, s in enumerate(V['surfaces']):
            g = ctl[V['popup'] + ' Strip' + (f' {i + 1}' if i else '')][0]
            self.assertEqual(rgba(g['fill']), rgba(s['fill']))
        if V['level']['bar']:
            self.assertEqual(rgba(ctl['Volume'][0]['bar']), rgba(V['level']['bar']))

    def test_the_volume_modal_draws_its_glyphs_over_and_under_the_level(self):
        """The template's Volume Up and Down glyphs - labels with its seed IDs,
        white, at its rects - one over the level and one under it."""
        _, _, on, _ = self.split('Main.dc.html')
        V = self.frame()['volume']
        ctl = on[V['popup']]
        for n, x in zip(('Volume Up Label', 'Volume Down Label'), V['labels']):
            g, r, over = ctl[n]
            self.assertEqual((g['kind'], g['derived'], g['id']), ('label', True, x['id']), n)
            self.assertAt(r, x['rect'], n)
            self.assertTrue(_inside(r, [0, 0, 320, 240], 0), (n, r))
            self.assertEqual(g['color'], 'text', n)
            self.assertTrue(g['text'], n)
            self.assertFalse(over, n)
        lv = ctl['Volume'][1]
        self.assertLessEqual(ctl['Volume Up Label'][1][1] + ctl['Volume Up Label'][1][3], lv[1])
        self.assertGreaterEqual(ctl['Volume Down Label'][1][1], lv[1] + lv[3])

    def test_a_source_with_nothing_says_the_templates_empty_state(self):
        """A role="source" popup is a page of its own, under the strip titled
        with the source, saying the template's three-line empty state where
        it does, with Back to the page that shows it - which the translator
        finds (`back`)."""
        F, w = self.frame(), self.profile()['writing']
        page, parts, on, out = self.split('Laptop.dc.html')
        self.assertEqual((out['problems'], out['warnings']), ([], []))
        self.assertEqual((page['kind'], page.get('group'), page['size']), ('page', None, [320, 240]))
        self.assertTrue(page.get('background_image'))
        ctl = on[None]
        # At the template's rect - as deep as Back where Back ends the strip.
        g, r, _ = ctl['Laptop Title']
        self.assertEqual(g['text'], 'Laptop')
        self.assertAt(r, self.item(F, 'title')['rect'])
        # A label a line at the template's own rects and seed IDs: its first
        # sentence a paragraph apart from the other two.
        lines = w['page_empty'].format(name='Laptop').split('\n')
        self.assertEqual(len(lines), 3)
        for i, (text, x) in enumerate(zip(lines, F['center']['empty_lines'])):
            n = 'Laptop Empty' + (f' {i + 1}' if i else '')
            g, r, over = ctl[n]
            self.assertEqual((g['text'], g['derived'], g['id'], r), (text, True, x['id'], x['rect']), n)
            self.assertFalse(over, n)
        g, r, _ = ctl['Laptop Back']
        self.assertEqual((g['derived'], g['back'], g.get('nav')), (True, True, None))
        self.assertNotIn('Laptop More', ctl)
        self.assertEqual(parts, {})

    def _help_in_words(self, *labels):
        ns = {'mach': 'ExtronMach', 'shockwave': 'ExtronShockwave', 'turbulence': 'ExtronTurbulence'}[self.THEME]
        tag = 'style="position: absolute; left: 0px; top: 0px; width: 1280px; height: 800px"></x-import>'
        body = ''.join(f'<x-import component-from-global-scope="{ns}.Label" name="{n}" style="position: absolute; '
                       f'left: 160px; top: {170 + 120 * i}px; width: 960px; height: 100px">{t}</x-import>'
                       for i, (n, t) in enumerate(labels))
        return self.split('Help.dc.html', edit=(tag, tag[:-len('</x-import>')] + body + '</x-import>'))

    def test_help_in_the_designers_words_is_set_as_the_templates_message(self):
        """Help holding only words - one Label, or a few - is set as the
        template sets its Help message: across the page under the strip,
        clear of Back, each Label as deep as its words wrap to at the 320's
        floor, one under the other. In the template's columns each was a
        key's cell (Mach's 74x50), and a sentence ran out of it."""
        text = 'To share, plug in the table cable or use ShareLink. For help, call the AV desk at 4400.'
        page, parts, on, out = self._help_in_words(('Help Text', text))
        self.assertEqual((out['problems'], parts), ([], {}))
        ctl = on[None]
        g, r, over = ctl['Help Text']
        self.assertFalse(over)
        gap = self.row()['gap']
        self.assertEqual((r[0], r[2]), (gap, 320 - 2 * gap))
        strip = ctl['Help Title'][1]
        self.assertGreater(r[1], strip[1] + strip[3] - 1)
        self.assertLessEqual(r[1] + r[3], 240)
        page, parts, on, out = self._help_in_words(('Help Step', 'Press a source to share it.'),
                                                   ('Help Desk', 'Call the AV desk at 4400.'))
        self.assertEqual(out['problems'], [])
        a, b = on[None]['Help Step'][1], on[None]['Help Desk'][1]
        self.assertLessEqual(a[1] + a[3], b[1])
        self.assertFalse(on[None]['Help Step'][2] or on[None]['Help Desk'][2])

    def test_help_in_more_lines_than_a_page_goes_on_over_a_second(self):
        """Lines that do not all fit under the strip go on over a second page
        by the template's More and Back, at their places and seed IDs; a
        Label too long for a page of its own is named - one control does not
        break across pages."""
        F = self.frame()
        lines = [(f'Help Step {i}', f'Step {i}: press the source you want, then wait.') for i in range(1, 7)]
        page, parts, on, out = self._help_in_words(*lines)
        self.assertEqual(out['problems'], [])
        self.assertTrue(parts)
        self.assertEqual(list(parts), [f'Help {i}' for i in range(2, len(parts) + 2)])
        here = self.mine(on)
        self.assertEqual({w for w, _, _ in here.values()}, {None} | set(parts))
        self.assertNotIn(f'Help {len(parts) + 1} More', on[f'Help {len(parts) + 1}'])
        more, back = self.item(F, 'more'), self.item(F['second'], 'back')
        g, r, _ = on[None]['Help More']
        self.assertEqual((g['nav'], g['id']), ('Help 2', more['id']))
        g, r, _ = on['Help 2']['Help 2 Back']
        self.assertEqual((g['nav'], g['id']), ('Help', back['id']))
        for where in [None] + list(parts):
            for n, (g, r, over) in on[where].items():
                self.assertTrue(_inside(r, [0, 0, 320, 240], 0), (where, n, r))
                self.assertFalse(over, (where, n))
        long_ = ' '.join(['Press the source on the panel, then wait for the display to show it.'] * 4)
        _, _, _, out = self._help_in_words(('Help Text', long_))
        self.assertTrue(any("Help's Help Text needs" in p and 'say less' in p for p in out['problems']), out['problems'])

    def test_a_long_source_name_breaks_its_first_line_as_the_template_does(self):
        """'Document Camera is currently selected.' does not fit the first
        line's 320 px at the 320's 14 pt floor: it breaks onto two lines in
        that label, as the template's own Aux Label 2 breaks its sentence
        (CRLF in one label, grown by a line) - growing up into the room under
        the strip, so the paragraph under it stays where the template sets it."""
        F = self.frame()
        page, parts, on, out = self.split('Laptop.dc.html', edit=('name="Laptop"', 'name="Laptop" title="Document Camera"'))
        self.assertEqual((out['problems'], out['warnings']), ([], []))
        ctl = on[None]
        lines = F['center']['empty_lines']
        g, r, over = ctl['Laptop Empty']
        self.assertEqual(len(g['text'].split('\r\n')), 2, g['text'])
        self.assertEqual(' '.join(g['text'].split('\r\n')), 'Document Camera is currently selected.')
        self.assertFalse(over)
        self.assertEqual(r[1] + r[3], lines[0]['rect'][1] + lines[0]['rect'][3])
        self.assertLess(r[1], lines[0]['rect'][1])
        self.assertGreaterEqual(r[1], ctl['Laptop Title'][1][1] + ctl['Laptop Title'][1][3])
        for i in (1, 2):
            g, r, over = ctl[f'Laptop Empty {i + 1}']
            self.assertEqual((r, over), (lines[i]['rect'], None), i)

    def test_a_source_with_more_than_a_page_goes_on_over_a_second(self):
        """Doc Cam's four columns: its headings over their controls as the
        template's columns stand, the designer's words as written, two to a
        page; the rest on 'DocCam 2', joined by the template's More and Back
        at their places with their seed IDs, each page under the strip."""
        F = self.frame()
        page, parts, on, out = self.split('DocCam.dc.html')
        self.assertEqual((out['problems'], out['warnings']), ([], []))
        self.assertEqual(list(parts), ['DocCam 2'])
        self.assertEqual((parts['DocCam 2']['kind'], parts['DocCam 2']['host']), ('page', 'DocCam'))
        more, back = self.item(F, 'more'), self.item(F['second'], 'back')
        g, r, _ = on[None]['DocCam More']
        self.assertEqual((g['nav'], g['id']), ('DocCam 2', more['id']))
        self.assertAt(r, more['rect'])
        g, r, _ = on['DocCam 2']['DocCam 2 Back']
        self.assertEqual((g['nav'], g['id']), ('DocCam', back['id']))
        self.assertAt(r, back['rect'])
        self.assertEqual(on['DocCam 2']['DocCam 2 Title'][0]['text'], 'Document Camera')
        here = self.mine(on)
        heads = {'Inputs Heading': 'Inputs', 'Zoom Heading': 'Zoom', 'Focus Heading': 'Focus', 'Iris Heading': 'Iris'}
        for n, text in heads.items():
            self.assertEqual(here[n][1]['text'], text)
        self.assertEqual(len(here), 16, sorted(here))
        self.assertEqual({w for w, _, _ in here.values()}, {None, 'DocCam 2'})
        row = F['center']['row']
        for where in (None, 'DocCam 2'):
            ctl = on[where]
            self.assertEqual(_gaps(ctl, self.PANEL), [], where)
            mine = {n: r for n, (g, r, _) in ctl.items() if not g.get('derived')}
            self.assertTrue(mine)
            for n, r in mine.items():
                self.assertTrue(_inside(r, F['center']['rect'], 0), (where, n, r))
            # Each column under its heading.
            for hn in [h for h in heads if h in mine]:
                col = hn.split()[0]
                keys = [n for n in mine if n.startswith('Doc Cam ' + col)]
                self.assertTrue(keys, hn)
                hr = mine[hn]
                for k in keys:
                    self.assertGreaterEqual(mine[k][1], hr[1] + hr[3], (hn, k))
                    self.assertLess(abs((mine[k][0] + mine[k][2] / 2) - (hr[0] + hr[2] / 2)), 2, (hn, k))
        # The first page's first column where the template's first column is.
        x0 = min(r[0] for n, (g, r, _) in on[None].items() if not g.get('derived') and g['kind'] == 'button')
        self.assertLessEqual(abs(x0 - row[0][0]), 12, (x0, row))

    def test_the_question_is_a_page_on_the_templates_box(self):
        """The power-down question is a page as the template draws it: its
        rounded box, its question, Power Down and Cancel at its places with
        their seed IDs - Cancel back to the page that asked (`back`)."""
        W, w = self.frame()['windows']['confirm'], self.profile()['writing']
        page, parts, on, out = self.split('ConfirmPower.dc.html')
        self.assertEqual((out['problems'], out['warnings']), ([], []))
        self.assertEqual((page['kind'], page.get('modal'), page['size']), ('page', None, [320, 240]))
        self.assertEqual(bool(page.get('background_image')), W['art'])
        ctl = on[None]
        self.assertEqual(ctl['ConfirmPower Window'][1], W['rect'])
        # The 320's own words (Shockwave's in one run, where its 1035 breaks).
        self.assertEqual(ctl['ConfirmPower Message'][0]['text'], W.get('text') or w['confirm']['power'])
        # Each at the template's rect, the two alike: a caption that does
        # not fit one line there goes on two, as Turbulence's own Power Down.
        for b in W['buttons']:
            n = 'ConfirmPower ' + ('Power Down' if b['role'] == 'power' else 'Cancel')
            g, r, over = ctl[n]
            self.assertEqual(r, b['rect'], n)
            self.assertEqual(g['id'], b['id'], n)
            self.assertFalse(over, n)
        self.assertEqual(ctl['ConfirmPower Power Down'][0]['does'], 'Powers the room down.')
        self.assertTrue(ctl['ConfirmPower Cancel'][0]['back'])

    def test_help_and_the_settings_are_pages_under_the_strip(self):
        """The 320 draws no Help or settings window: each is a page under the
        strip, titled as on the 1035, what it holds under the strip, with
        Back to the page that opened it."""
        w = self.profile()['writing']
        page, _, on, out = self.split('Help.dc.html')
        self.assertEqual((out['problems'], out['warnings']), ([], []))
        self.assertEqual(page['kind'], 'page')
        ctl = on[None]
        self.assertEqual(ctl['Help Title'][0]['text'], w['help_title'])
        self.assertEqual(ctl['Help Message'][0]['text'], w['help'])
        self.assertFalse(ctl['Help Message'][2])
        self.assertTrue(ctl['Help Back'][0]['back'])
        page, _, on, out = self.split('Lighting.dc.html')
        self.assertEqual((out['problems'], out['warnings']), ([], []))
        ctl = on[None]
        self.assertEqual(ctl['Lighting Title'][0]['text'], 'Lighting Settings')
        for n in ('Lights Preset 1', 'Lights Preset 2'):
            self.assertTrue(_inside(ctl[n][1], self.frame()['center']['rect'], 0), n)
        self.assertEqual(_gaps(ctl, self.PANEL), [])

    def strips(self, on):
        """Each page whose Back ends its strip: {page: (Back's rect, its
        strip's rects, its title's rect, its title's data-gdl, overflow)}."""
        out = {}
        for where, ctl in on.items():
            for n, (g, r, _) in ctl.items():
                if not (n.endswith(' Back') and g.get('derived') and r[1] == 0):
                    continue
                page = n[:-len(' Back')]
                strips = [rr for nn, (gg, rr, _) in ctl.items() if nn.startswith(page + ' Strip')]
                tg, tr, over = ctl[page + ' Title']
                out[page] = (r, strips, tr, tg, over)
        return out

    def test_back_at_the_strips_end_is_flush_with_the_strip(self):
        """Where Back ends the strip, the strip and its title are as deep as
        Back (the touch minimum): Back does not hang under it."""
        seen = 0
        for board in ('Main.dc.html', 'DocCam.dc.html', 'Laptop.dc.html'):
            _, _, on, _ = self.split(board)
            for page, (back, strips, title, _, _) in self.strips(on).items():
                seen += 1
                self.assertTrue(strips, page)
                for r in strips:
                    self.assertEqual(r[3], back[3], (page, r, back))
                self.assertEqual(title[3], back[3], page)
        self.assertTrue(seen)

    def test_a_strips_title_stays_clear_of_back(self):
        """A title the strip shares with Back stands clear of it: centred on
        the strip where it fits beside Back, else on what Back leaves of it.
        Main's later pages' titles join their Sections' - and say only the
        first where the rest would not fit. A designer's own title too long
        for it is named."""
        def check(on, out):
            said = {json.loads(c['gdl']).get('name'): c.get('text_rect') for c in out['controls']}
            for page, (back, _, title, _, over) in self.strips(on).items():
                self.assertFalse(over, page)
                t = said[page + ' Title']
                self.assertLessEqual(t[0] + t[2], back[0] + 0.5, (page, t, back))
        _, _, on, out = self.split('Main.dc.html')
        check(on, out)
        _, _, on, out = self.split('Main.dc.html', (' title="Settings"', ' title="Room Settings and Scheduling"'))
        self.assertEqual(out['problems'], [])
        check(on, out)
        titles = [ctl[p + ' Title'][0]['text'] for p, ctl in on.items() if p and p.startswith('Main ')]
        self.assertIn('Display', titles)
        self.assertNotIn('Display and Room Settings and Scheduling', titles)
        _, _, on, out = self.split('DocCam.dc.html', ('title="Document Camera"',
                                                      'title="Document Camera and Visualizer Controls"'))
        self.assertTrue([p for p in out['problems'] if "DocCam's title" in p and 'Back' in p], out['problems'])

    def test_every_keys_art_is_at_least_the_touch_minimum_deep(self):
        """A key's kit art, drawn to fit its box, is never a sliver: a caption
        wider than the theme's key takes a wider art only where that art,
        as wide as its column, is still the touch minimum deep - else the
        key's own art, grown in its own shape to hold it."""
        touch = self.row()['touch']
        for board in ('Main.dc.html', 'DocCam.dc.html'):
            _, _, on, _ = self.split(board)
            for where, ctl in on.items():
                for n, (g, r, _) in ctl.items():
                    imgs = [s.get('image') for s in g.get('states') or [] if isinstance(s, dict) and s.get('image')]
                    if g.get('kind') != 'button' or not imgs or not re.match(r'\d+x\d+_', imgs[0]):
                        continue
                    kw, kh = (int(v) for v in imgs[0].split('_')[0].split('x'))
                    s = min(r[2] / kw, r[3] / kh)
                    self.assertGreaterEqual(round(kh * s), touch, (where, n, r, imgs[0]))

    def test_mains_template_left_offs_do_not_mark_it(self):
        """The clock and the Center's popup region are left off the 320 by
        its template's grammar, not by anything the designer can change: they
        are named (`left`, a warning) but do not outline Main as a problem."""
        page, _, _, out = self.split('Main.dc.html')
        self.assertEqual(page['left'], ['Date Time', 'Controls'])
        self.assertEqual(len(out['warnings']), 2)
        self.assertFalse(out['page'].get('outlined'))

    def window_with(self, board, old_name, new):
        """(old, new): the control named `old_name` on `board`, and `new` in
        the theme's namespace (`{ns}`)."""
        with open(os.path.join(self.CANVAS, board), encoding='utf-8') as fh:
            src = fh.read()
        m = re.search(r'<x-import [^>]*name="' + re.escape(old_name) + r'"[^>]*>[^<]*</x-import>', src)
        self.assertTrue(m, old_name)
        return (m.group(0), new.replace('{ns}', self.profile()['namespace']))

    def test_a_group_in_a_window_pages_as_its_columns(self):
        """A Group in a settings window: its title a heading, its members in
        the 320's columns over as many pages as they need - each on the
        screen, clear of the strip and of each other - not one cell's worth
        spilling off the screen."""
        grp = ('<x-import component-from-global-scope="{ns}.Group" title="Scenes" cell="140x60" gap="20" cap="2" '
               'style="position: absolute; left: 380px; top: 360px; width: 300px; height: 300px">'
               + ''.join(f'<x-import component-from-global-scope="{{ns}}.Button" name="Scene {i}" '
                         f'does="Recalls scene {i}." style="width: 140px; height: 60px">Scene {i}</x-import>'
                         for i in range(1, 7)) + '</x-import>')
        _, _, on, out = self.split('Lighting.dc.html', self.window_with('Lighting.dc.html', 'Lights Preset 1', grp))
        self.assertEqual((out['problems'], out['warnings']), ([], []))
        here = self.mine(on)
        for i in range(1, 7):
            w, g, r = here[f'Scene {i}']
            self.assertEqual(g['kind'], 'button')
            self.assertTrue(_inside(r, self.frame()['center']['rect'], 0), (f'Scene {i}', r))
        heads = [g['text'] for ctl in on.values() for n, (g, r, _) in ctl.items() if g.get('kind') == 'label'
                 and g.get('derived') and n.endswith(' Heading')]
        self.assertIn('Scenes', heads)
        for where, ctl in on.items():
            self.assertEqual(_gaps(ctl, self.PANEL), [], where)
            for n, (g, r, _) in ctl.items():
                self.assertTrue(_inside(r, [0, 0, 320, 240], 0), (where, n, r))

    def test_a_slider_in_a_window_is_a_level_with_up_and_down(self):
        """The 320's seed has no slider to clone: a slider in a settings
        window is a level there, a column of its own, with the derived Up and
        Down every level a slider becomes has - not a slider in a key's cell."""
        sl = ('<x-import component-from-global-scope="{ns}.Slider" name="Lights Level" orientation="up" '
              'does="Sets the lights." style="position: absolute; left: 760px; top: 300px; width: 40px; '
              'height: 300px"></x-import>')
        old = self.window_with('Lighting.dc.html', 'Lights Preset 2', '')[0]
        _, _, on, out = self.split('Lighting.dc.html', (old, old + sl.replace('{ns}', self.profile()['namespace'])))
        self.assertEqual((out['problems'], out['warnings']), ([], []))
        here = {n: (w, g, r) for w, ctl in on.items() for n, (g, r, _) in ctl.items()}
        w, g, r = here['Lights Level']
        self.assertEqual(g['kind'], 'level')
        up, down = here['Lights Level Up'], here['Lights Level Down']
        self.assertEqual((up[0], down[0]), (w, w))
        self.assertTrue(up[1]['derived'] and down[1]['derived'])
        self.assertLessEqual(up[2][1] + up[2][3], r[1])
        self.assertGreaterEqual(down[2][1], r[1] + r[3])
        for x in (up[2], down[2], r):
            self.assertTrue(_inside(x, self.frame()['center']['rect'], 0), x)
        self.assertEqual(_gaps(on[w], self.PANEL), [])


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestMachsPages(_PagesProbe, unittest.TestCase):
    """Mach's 320: a black 70% strip, shade keys on the photo, More at the
    foot's right and Back at the strip's right end; the question on #303030."""

    THEME = 'mach'

    def test_back_ends_the_strip_and_the_question_is_on_its_ground(self):
        """On a page with Back the strip is the template's second page's: a
        shape short of the edge, Back at its end. The question stands on the
        page's own #303030, not the photo."""
        F = self.frame()
        _, _, on, _ = self.split('DocCam.dc.html')
        strip, back = on['DocCam 2']['DocCam 2 Strip'][1], on['DocCam 2']['DocCam 2 Back'][1]
        want = F['second']['top']['surfaces'][0]['rect']
        self.assertEqual((strip[:3], strip[3]), (want[:3], back[3]))
        self.assertEqual(back[0], want[0] + want[2] + 1)
        page, _, _, _ = self.split('ConfirmPower.dc.html')
        self.assertEqual((page['background'], page.get('background_image')), ('page', None))


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestShockwavesPages(_PagesProbe, unittest.TestCase):
    """Shockwave's 320: its gray keys, More and Back at the foot's right."""

    THEME = 'shockwave'


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTurbulencesPages(_PagesProbe, unittest.TestCase):
    """Turbulence's 320: its square keys, More and Back the kit's own."""

    THEME = 'turbulence'

    def test_its_keys_are_its_square_keys_and_its_strip_back_is_a_glyph(self):
        """No key is the 720x180 bar, 23 px deep as wide as a column may be:
        Doc Cam's and Main's are the template's square key, a two-word
        caption on two lines ('Doc' over 'Cam'). Back where it ends the strip
        is the kit's return key, not its 'Back' key, whose word is 5 px tall
        at 40."""
        _, _, on, _ = self.split('DocCam.dc.html')
        for where, ctl in on.items():
            for n, (g, r, _) in ctl.items():
                if g.get('kind') == 'button' and not g.get('derived'):
                    self.assertNotEqual(g.get('variant'), 'wide', (where, n))
        _, _, on, _ = self.split('Main.dc.html')
        for n in ('PC', 'Laptop', 'Doc Cam', 'Streaming'):
            self.assertNotEqual(on[None][n][0].get('variant'), 'wide', n)
        self.assertEqual(on[None]['Doc Cam'][0]['text'], 'Doc' + chr(10) + 'Cam')
        seen = 0
        for board in ('Main.dc.html', 'DocCam.dc.html'):
            _, _, on, _ = self.split(board)
            for page in self.strips(on):
                g = next(ctl[page + ' Back'][0] for ctl in on.values() if page + ' Back' in ctl)
                imgs = [s['image'] for s in g['states'] if s.get('image')]
                self.assertTrue(imgs and all('vc_return' in i for i in imgs), (page, imgs))
                seen += 1
        self.assertTrue(seen)


if __name__ == '__main__':
    unittest.main(verbosity=2)
