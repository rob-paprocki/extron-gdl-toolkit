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

from gdl import design, designsys  # noqa: E402
from gdl.spec import Panel  # noqa: E402

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
        spec, problems, _ = design.Canvas(self.dir).translate()
        self.assertEqual(problems, [])
        self.assertEqual([p['name'] for p in spec['pages']], ['Huddle Home', 'Huddle Help'])
        home = {c['name']: c for c in spec['pages'][0]['controls']}
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
        self.assertEqual(Panel(spec).check(), [])

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
