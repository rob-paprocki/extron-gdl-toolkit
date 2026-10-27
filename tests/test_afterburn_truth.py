"""Afterburn's truth ledger (gdl/designsys/truth/afterburn.json): is what its
system says about its template what the template does?

Three layers. The ledger is complete and `python -m gdl.designsys audit
afterburn` is at zero. The profile and README say what each entry's fix
promises, so a later edit cannot quietly bring an old claim back. And, where
the seeds are here (Git LFS), the template facts the ledger rests on are read
off seeds/Afterburn 1035.gdl again - its buttons' fills and strokes, its
clocks, its sizes - so the ledger's evidence is a check, not a note.
"""
import contextlib
import io
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from _corpus import seed as seed_path, usable  # noqa: E402
from gdl import designsys  # noqa: E402
from gdl.designsys import audit  # noqa: E402

SEED = seed_path('Afterburn 1035.gdl')


def _hex(c):
    return '#%02X%02X%02X' % (c['R'], c['G'], c['B']) if c else None


def _colors(p):
    return {c['name']: c['value'] for c in p['colors']}


class TestAfterburnsLedger(unittest.TestCase):
    def setUp(self):
        self.p = designsys.load('afterburn')
        self.ledger = audit.load_ledger('afterburn')

    def test_it_has_an_entry_for_every_disagreement(self):
        """The grammar measurement found 35 claims of Afterburn's profile and
        README that its pages contradict, the mic mute and display state's one
        more (afterburn-35), the kit's drawings of its glyphs, fitted to their
        buttons (afterburn-36), its hub's own grammar (37), the hub's Volume
        Up giving way to the mode launcher's 8120 (38), and its regions'
        README: the left rail in Sections (39), each panel's clocks (40), the
        computed indents (41), and the gates' moves on the 725's rail (42), its
        Help and Power (43) and the 320's rows (44), and the hub's Volume
        Level strip, shown on every working page (45), its right column's
        flex, which the region score measured (46), its Mute's two glyphs
        (47), and the recording question's answers, whose IDs are the
        layout's own (48): one entry each, in its order."""
        ids = [e['id'] for e in self.ledger['entries']]
        self.assertEqual(ids, [f'afterburn-{i:02d}' for i in range(49)])

    def test_afterburn_is_done(self):
        self.assertEqual(audit.audit('afterburn'), [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(designsys.main(['gdl.designsys', 'audit', 'afterburn']), 0)

    def test_what_it_keeps_differing_in_is_said_with_its_reason(self):
        """The 14 pt floor, the spacing standards, the Group's paging, the
        hubs' one background, the kit's drawings of the glyph font fitted to
        their buttons, the 8120 a launcher keeps, and the gates' moves on the
        725's rail, its Help and Power and the 320's rows, the hub's Volume
        Level strip on every working page, the right column's flex and the
        recording question's answers' IDs - and only those. The
        right column, the hub's carets, the left rail, the clocks, a window's
        card and the 320's pages are the frame's now."""
        dev = {e['id']: e for e in self.ledger['entries'] if e['status'] == 'deviation'}
        self.assertEqual(sorted(dev), [f'afterburn-{i:02d}' for i in (23, 24, 32, 34, 36, 38, 42, 43, 44, 45, 46, 48)])
        for i in ('afterburn-08', 'afterburn-09', 'afterburn-10', 'afterburn-11', 'afterburn-39', 'afterburn-40'):
            self.assertEqual(next(e for e in self.ledger['entries'] if e['id'] == i)['status'], 'frame')
        for e in dev.values():
            self.assertGreater(len(e['reason'].split()), 12, e['id'])

    def test_what_changes_what_builds_is_named(self):
        """The right column and the foot row, the hub's carets, the 320's
        pages, a window's card drawn as the page's own art, a button naming a
        kit drawing of a glyph, which now resolves to Icons/PNG, the alert
        variant, a Group's chevrons, the 520's hub, the left rail in Sections
        and each panel's own clocks, and the Mute's muted glyph."""
        built = [e['id'] for e in self.ledger['entries'] if e.get('builds')]
        self.assertEqual(built, [f'afterburn-{i:02d}' for i in (8, 9, 10, 11, 15, 25, 32, 37, 39, 40, 47)])


class TestTheGlyphsTheKitDrawsAsImages(unittest.TestCase):
    """afterburn-09, -15 and -32: the template's Close, Back, More, scroll
    and volume triangles, minus and plus are glyphs of its icon font, and
    Afterburn's kit draws the same glyphs as images in Afterburn/Icons/PNG,
    beside its Buttons/PNG. The system offers them by name (`kit.icons`);
    the ledger and the profile say so, and say where they are not drawn by
    default yet - not that the kit lacks them, or that the canvas cannot
    draw them."""

    # Each the image of a glyph the template sets: Close U+E95C, Back U+E97B
    # and the 320's More U+E97C, Search Results' scroll and the 525's volume
    # U+E94E and U+E91D, the 300M's volume U+E912 and U+E939, More Presets
    # U+E933 - the same drawings in Extron - Afterburn 1a.ttf.
    STAND_INS = ('440x440_close.png', 'Chevron/440x440_chevron-left.png', 'Chevron/440x440_chevron-right.png',
                 'Carets/440x440_caret-up-gray.png', 'Carets/440x440_caret-down-gray.png',
                 'Carets/440x440_caret-up-dark-gray.png', 'Carets/440x440_caret-down-dark-gray.png',
                 '440x440_minus.png', '440x440_plus.png', '440x440_more.png')

    def setUp(self):
        self.p = designsys.load('afterburn')
        self.ledger = {e['id']: e for e in audit.load_ledger('afterburn')['entries']}

    def test_the_kit_has_them_beside_the_buttons_the_system_reads(self):
        from gdl.spec import resolve_image
        if not resolve_image('Afterburn/Icons/PNG/440x440_close.png'):
            self.skipTest("Extron's Afterburn kit is not here")
        for f in self.STAND_INS:
            self.assertTrue(resolve_image('Afterburn/Icons/PNG/' + f), f)
        self.assertEqual(self.p['kit']['root'], 'Afterburn/Buttons/PNG')

    def test_no_entry_says_the_kit_lacks_them_or_the_canvas_cannot_draw_them(self):
        # The hub's carets are the frame's now, the kit's drawings by name.
        self.assertEqual(self.ledger['afterburn-09']['status'], 'frame')
        self.assertIn('caret-up-gray', self.ledger['afterburn-09']['builds'])
        for k in ('afterburn-09', 'afterburn-15', 'afterburn-32'):
            e = self.ledger[k]
            said = ' '.join((e.get('reason', ''), e['template']['does']))
            if k != 'afterburn-09':
                self.assertIn('Afterburn/Icons/PNG', said, k)
            for wrong in ('cannot draw them', 'cannot be built', "`icon` list has no close", 'glyph arrows',
                          'does not reach yet', 'does not name them'):
                self.assertNotIn(wrong, said, k)
        self.assertEqual(self.ledger['afterburn-15']['status'], 'fixed')

    def test_the_profile_says_the_system_offers_the_images(self):
        for text in (self.p['iconography']['intro'], self.p['layout']['popups'], self.p['layout']['rail_note'],
                     self.p['examples']['group_note']):
            self.assertIn('Afterburn/Icons/PNG', text)
            self.assertNotIn('does not name', text)
        text = designsys.readme(self.p) + '\n'.join(designsys.component_docs(self.p).values())
        self.assertNotIn('not kit images', text)
        self.assertNotIn('the Close says Close', text)
        self.assertIn('icon="close"', text)


class TestWhatTheProfileNowSays(unittest.TestCase):
    def setUp(self):
        self.p = designsys.load('afterburn')
        self.readme = designsys.readme(self.p)
        self.docs = designsys.component_docs(self.p)
        self.type = {t['name']: t for t in self.p['type']}

    def test_a_title_is_the_21_pt_regular_white_label_and_a_heading_an_entry_readout(self):
        """Every popup and modal title is 21 pt regular #FFFFFF; 23.5 bold is
        the TV channel's and the keyboard's address; 38 pt is Start's room."""
        self.assertEqual((self.type['subheading']['pt'], self.type['subheading']['weight']), (21, 400))
        self.assertNotIn('text-secondary', self.type['subheading']['usage'])
        self.assertEqual((self.type['heading']['pt'], self.type['heading']['weight']), (23.5, 700))
        self.assertIn('entry readout', self.type['heading']['usage'])
        self.assertIn('Start page', self.type['title']['usage'])
        self.assertEqual(self.p['defaults']['label']['color'], 'text')

    def test_the_two_group_labels_are_told_apart(self):
        """A rail group's heading is 16 regular white in Title case; a popup's
        is 16 bold #BABCCE in capitals - which a Label does not default to."""
        self.assertIn('Title case', self.type['body']['usage'])
        usage = self.type['body-strong']['usage']
        self.assertIn('capitals', usage)
        self.assertIn('text-secondary', usage)

    def test_button_large_is_the_keys_and_the_smaller_captions_are_said(self):
        usage = self.type['button-large']['usage']
        self.assertIn('keypad or keyboard key', usage)
        self.assertIn('17', usage)
        self.assertEqual(self.p['defaults']['button']['type'], 'button')

    def test_red_is_a_live_stroke_and_never_a_fill_or_a_caption(self):
        """Start Sharing and Stop Share stroke #D32A2A when On, and the record
        icon is red; no button state of any page fills red."""
        alert = self.p['buttons']['alert']
        self.assertEqual(alert['look'], {'fill': 'raised', 'stroke': 'text-secondary', 'border': 'afterburn',
                                         'color': 'text'})
        self.assertEqual(alert['states'], [{'name': 'Off'}, {'name': 'On', 'stroke': 'alert'}])
        self.assertEqual(_colors(self.p)['alert'], '#D32929')
        token = next(c for c in self.p['colors'] if c['name'] == 'alert')
        for text in (alert['usage'], token['usage'], self.p['examples']['color_rule']):
            self.assertNotIn('red fill', text)
        self.assertNotIn('only as an alert', self.p['examples']['color_rule'])

    def test_the_ghost_variant_is_no_tab_and_no_rail_row(self):
        usage = self.p['buttons']['ghost']['usage']
        self.assertIn('not ghost', usage)
        self.assertIn('keypad', usage)
        for variant in ('source', 'list'):
            self.assertIn(variant, usage)

    def test_the_outlined_icon_buttons_are_make_call_swap_and_contacts(self):
        text = self.p['buttons']['outlined']['usage'] + ' '.join(self.p['iconography']['rules'])
        self.assertIn('Make Call, Swap, Contacts', text)
        self.assertNotIn('(End Call, Swap)', text)
        self.assertIn('End Call', self.p['buttons']['list']['usage'])

    def test_close_is_the_kits_drawing_of_the_templates_glyph(self):
        """The template's Close, Back and arrows are glyphs of its icon font;
        the kit draws them in Icons/PNG, which the system now reads beside
        Buttons/PNG (`kit.icons`), so its `icon` list offers them by name."""
        names = designsys.icon_names(self.p).get('icon') or []
        if names:
            for glyph in ('close', 'back', 'chevron-left', 'chevron-right', 'caret-up-gray', 'plus', 'minus'):
                self.assertIn(glyph, names)
        self.assertNotIn('close, mute', ' '.join(self.p['iconography']['rules']))
        self.assertNotIn('Close, mute', self.p['buttons']['icon']['usage'])
        self.assertIn('Extron-Afterburn icon font', self.p['iconography']['intro'])
        self.assertIn('`variant="icon" icon="close"`', self.p['iconography']['intro'])
        self.assertNotIn('does not name them yet', json.dumps(self.p))

    def test_the_icon_variant_says_what_the_template_draws_on_help_power_and_mute(self):
        usage = self.p['buttons']['icon']['usage']
        self.assertIn("Power's raised", usage)
        self.assertIn('Level 1 to 3', usage)

    def test_the_card_is_art_and_the_one_panel_is_the_search_list(self):
        raised = next(c for c in self.p['colors'] if c['name'] == 'raised')
        self.assertIn("background image's art", raised['usage'])
        self.assertIn('gradient', self.p['layout']['main_note'])
        self.assertEqual(self.p['examples']['panel'],
                         {'name': 'Results', 'fill': 'raised', 'border': 'afterburn', 'size': [345, 385]})
        self.assertNotIn('TopBar', self.docs['Panel'])
        self.assertIn('video window', self.p['borders']['rect']['usage'])
        self.assertNotIn('bar', self.p['borders']['rect']['usage'])

    def test_a_standard_popup_is_no_card(self):
        """The 880x525 popup is an alpha-0 image over the squircle."""
        self.assertIn('for a standard popup', self.readme)
        self.assertNotIn('popup card', self.readme)
        usage = next(t for t in designsys.tokens(self.p)['size']['tokens'] if t['name'] == 'popup-width')['usage']
        self.assertIn('standard popup', usage)
        self.assertIn('draws nothing of its own', self.docs['Page'])

    def test_the_popups_line_says_what_flips_and_what_is_a_modal_where(self):
        # The profile's words (layout.popups); the README's Windows draws each
        # window by its role, and a modal without one its card and its Close.
        windows = self.readme.split('\n## Windows\n', 1)[1].split('\n## ', 1)[0]
        line = self.p['layout']['popups']
        # The owner's rule, unchanged: nothing forces a confirmation.
        self.assertIn('not a rule', windows)
        self.assertIn('with a Close at its top right where it has a title', windows)
        self.assertIn("one source's controls are a standard popup of its own group in that region (the template's group 1", line)
        self.assertIn('1020, 1220, 1230, 1520 and 1720 Series', line)
        self.assertIn('the 520 and 535 draw them as standard popups filling main', line)
        self.assertIn('the 300M as pages', line)
        self.assertIn('A confirmation has neither title nor Close', line)
        self.assertIn('does="Closes this popup."', windows)
        self.assertNotIn('one source\'s controls.', line)

    def test_a_modals_card_is_a_panel_because_a_page_cannot_place_the_art(self):
        kind = next(ln for ln in self.docs['Page'].splitlines() if ln.startswith('- `kind`'))
        self.assertIn('put its card inside as a Panel', kind)
        self.assertIn('squircle art', kind)

    def test_the_rail_is_not_the_templates_column(self):
        rail = self.docs['Rail']
        for words in ('is not one stack', 'side by side in one row', 'triangle glyphs', 'minus and plus',
                      'The 320 draws no volume, Help or Power on screen', 'Settings, Help and Power'):
            self.assertIn(words, rail)

    def test_the_layout_is_the_working_page_and_not_the_two_least_typical_ones(self):
        regions = ' '.join(self.p['layout']['regions'])
        for words in ('has no title of its own', 'Start and Main Select Source are not working pages',
                      'Window Layout (Multi-Window) and Recording Controls (Recording) open a window',
                      "Start Sharing (outlined, 144x64 at 1121,30) on a video-conference page",
                      'Help and Power side by side', 'record status', 'vertical divider'):
            self.assertIn(words, regions)
        for gone in ('Nothing else goes outside', 'ghost, left-aligned', 'in the middle, and one outlined action'):
            self.assertNotIn(gone, regions)
        # The generated Layout above it is the frame's, with the 1230's own
        # region, its Header the band of its source tabs over the Divider
        # under them and its Footer its foot row.
        layout = self.readme.split('## Layout', 1)[1].split('\n## ', 1)[0]
        self.assertIn('| 1230 | 1920x720 | Main SD | 608x139 at 1049,13 | 185x720 at 0,0 | 184x720 at 1736,0 | '
                      '1920x85 at 0,635 | 1551x695 at 185,13 | 650x500 at 1028,149 |', layout)

    def test_the_example_is_the_start_page(self):
        """Start holds the room's name, Press to begin and one date-and-time
        clock: no source, which the hub and the tabs hold, and no Help, which
        only the working pages have."""
        working = self.readme.split('\n## The working page\n', 1)[1].split('\n## ', 1)[0]
        example = next(b for b in re.findall(r'```html\n(.*?)```', working, re.S) if 'name="Start"' in b)
        self.assertIn('name="Start" splash="true" start="true"', example)
        for words in ('type="title"', 'size="17"', 'Press to begin', 'format="datetime"', 'color="text"'):
            self.assertIn(words, example)
        for gone in ('variant="source"', 'variant="icon"', 'format="date"', 'left: 1157px'):
            self.assertNotIn(gone, example)
        main = self.p['layout']['main']
        for top, h in re.findall(r'top: (\d+)px; width: [\d%]+(?:px)?; height: (\d+)px', example):
            self.assertLessEqual(int(top) + int(h), main[3])

    def test_the_examples_stand_where_the_template_stands_them(self):
        """Laptop where Main Select Source puts a source, Help where the
        working pages put it - beside Power, not at the rail's centre."""
        self.assertEqual(self.p['examples']['source']['rect'], [505, 315, 110, 110])
        self.assertEqual(self.p['examples']['help']['rect'], [1125, 706, 64, 64])
        self.assertEqual(self.p['examples']['group'], {'cell': '110x110', 'gap': 49})
        self.assertIn('cell="110x110" gap="49"', self.docs['Group'])
        self.assertIn('left: 322px; top: 291px', self.docs['MainArea'])

    def test_a_group_pages_with_the_kits_chevrons(self):
        self.assertIn("A Group that pages draws its Previous and Next as the kit's chevrons", self.docs['Group'])
        self.assertIn('VTC Search Results', self.docs['Group'])
        self.assertEqual(self.p['regions']['group']['next'], {'variant': 'icon', 'icon': 'chevron-right'})

    def test_the_start_page_is_named_start(self):
        regions = self.p['layout']['regions'][1]
        self.assertIn('name it `Start`', regions)
        self.assertIn('`Main.dc.html`', regions)
        self.assertIn('the system builds every page of those panels on their Main art', regions)

    def test_the_panels_notes_say_what_the_table_cannot(self):
        notes = ' '.join(self.p['panels']['_source'])
        self.assertIn("the 1230's 650x500", notes)
        self.assertIn('`_start` art', notes)
        # The measured frames are untouched: the seeds pin them
        # (tests/test_measure_series.py).
        self.assertEqual(self.p['panels']['Afterburn 1230 Series']['frame']['center']['region'], [1028, 149, 650, 500])
        self.assertIsNone(self.p['panels']['Afterburn 1230 Series']['popup'])


@unittest.skipUnless(usable(SEED), 'seeds/Afterburn 1035.gdl is not here (git lfs pull)')
class TestTheSeedSaysIt(unittest.TestCase):
    """The facts the ledger's entries rest on, off the seed."""

    @classmethod
    def setUpClass(cls):
        from gdl.project import Project
        cls.project = Project.open(SEED)
        cls.pages = {pg['name']: pg for pg in cls.project.pages()}

    def ctl(self, page, name):
        return next(c for c in self.pages[page]['controls'] if c['name'] == name)

    def test_the_flat_scan_holds_every_control_its_pages_do(self):
        """Project.controls() scans by class name, and its list had no PBVideo:
        it gave 648 of the seed's 650, its two video windows short - 11 short on
        the 1230W. PBVideo is the one class the corpus's pages hold that the
        list lacked (layout.json, all 47 projects)."""
        on_pages = sorted((c['type'], c['name']) for pg in self.pages.values()
                          for c in pg['controls'])
        flat = sorted((c['type'], c['name']) for c in self.project.controls())
        self.assertEqual(flat, on_pages)
        self.assertEqual(sum(t == 'PBVideo' for t, _ in flat), 2)

    def test_only_main_select_source_puts_the_sources_in_the_middle(self):
        """afterburn-00."""
        row = {c['name']: c['rect'] for c in self.pages['Main Select Source']['controls']
               if c['name'].endswith('Select Source') and c['type'] == 'PBButton'}
        self.assertEqual({r[1] for r in row.values()}, {315})
        for page in ('Main SD', 'Main SD Screen Arrows', 'Main Multi-Window', 'Main VC', 'Main Recording'):
            tabs = [c['rect'] for c in self.pages[page]['controls'] if c['name'] in ('PC', 'Laptop', 'TV', 'Streaming')]
            self.assertEqual(sorted(tabs), [(342, 37, 110, 110), (501, 37, 110, 110), (660, 37, 110, 110),
                                            (819, 37, 110, 110)], page)

    def test_start_is_the_room_a_button_in_the_middle_and_one_white_clock(self):
        """afterburn-02, -03, -30."""
        self.assertEqual(self.ctl('Start', 'Start')['rect'], (527, 384, 228, 64))
        clock = self.ctl('Start', 'Current Date & Time')
        self.assertEqual(clock['rect'], (415, 714, 450, 60))
        self.assertEqual(self.ctl('Main SD', 'Current Date')['rect'], (200, 710, 208, 60))
        self.assertEqual(self.ctl('Main SD', 'Time')['rect'], (932, 710, 148, 60))
        self.assertEqual(self.ctl('Main SD', 'Preview Source')['rect'], (568, 701, 144, 64))
        self.assertEqual([c['name'] for c in self.pages['Start']['controls'] if c['name'] in ('Help', 'Power')], [])

    def test_the_foot_buttons_and_the_right_rails_top_slot(self):
        """afterburn-05, -06, -07."""
        foot = {pg: self.ctl(pg, n)['rect'] for pg, n in (
            ('Main SD', 'Video Conference'), ('Main VC', 'Presentation'), ('Main Multi-Window', 'Window Layout'),
            ('Main Recording', 'Recording Controls'))}
        self.assertEqual(set(foot.values()), {(20, 706, 144, 64)})
        self.assertNotIn('Video Conference', {c['name'] for c in self.pages['Start']['controls']})
        self.assertEqual(self.ctl('Main VC', 'Share Content')['rect'], (1121, 30, 144, 64))
        self.assertEqual(self.ctl('Main Multi-Window', 'Window 1')['rect'], (1104, 30, 82, 64))
        self.assertEqual(self.ctl('Main Multi-Window', 'Window 2')['rect'], (1193, 30, 82, 64))
        self.assertEqual(self.ctl('Main Recording', 'Recording Timer - Not Recording')['rect'][:2], (68, 14))

    def test_the_rails_rows_are_178x50_every_58_and_the_right_column_is_not_a_stack(self):
        """afterburn-04, -08."""
        rows = [self.ctl('Main SD', n)['rect'] for n in ('Display Power', 'Display Mute')]
        self.assertEqual(rows, [(0, 208, 178, 50), (0, 266, 178, 50)])
        self.assertEqual(self.ctl('Main SD', 'Main Volume Slider')['rect'], (1168, 202, 50, 395))
        mute = self.ctl('Main SD', 'Main Volume Mute')['rect']
        self.assertLess(mute[1], 202 + 395)
        self.assertEqual(self.ctl('Main SD', 'Help')['rect'][1], self.ctl('Main SD', 'Power')['rect'][1])
        self.assertEqual((self.ctl('Main SD', 'Help')['rect'][0], self.ctl('Main SD', 'Power')['rect'][0]), (1125, 1197))

    def test_the_modals_card_is_an_image_and_a_confirmation_has_no_title_or_close(self):
        """afterburn-11, -12."""
        for page in ('Help', 'Confirmation', 'Starting Up'):
            self.assertEqual(self.ctl(page, 'Background')['type'], 'PBImage', page)
            self.assertEqual(self.ctl(page, 'Background')['rect'], (0, 0, 1280, 800), page)
        names = {c['name'] for c in self.pages['Confirmation']['controls']}
        self.assertFalse([n for n in names if n.startswith('Close')])
        self.assertEqual(self.ctl('Confirmation', 'Power Down')['rect'], (462, 325, 154, 64))
        self.assertEqual(self.ctl('Confirmation', 'Confirmation Cancel')['rect'], (664, 325, 154, 64))
        self.assertFalse([c for c in self.pages['Starting Up']['controls'] if c['type'] == 'PBButton'])
        self.assertTrue(self.ctl('Help', 'Close Help'))

    def test_a_source_s_controls_are_a_group_1_popup_in_the_region(self):
        """afterburn-13."""
        for page in ('Main SD', 'Main VC', 'Main Recording'):
            region = self.ctl(page, 'Controls')
            self.assertEqual(region['rect'], (200, 175, 880, 525), page)
        for name in ('PC', 'Laptop', 'TV', 'Streaming', 'Doc Cam', 'VTC Dialer'):
            self.assertEqual(self.pages[name]['size'], (880, 525), name)
            self.assertFalse(self.pages[name]['modal'], name)

    def test_the_icons_On_looks_and_the_four_mute_states(self):
        """afterburn-17."""
        help_, power = self.ctl('Main SD', 'Help'), self.ctl('Main SD', 'Power')
        self.assertIsNone(help_['states'][1]['fill'])
        self.assertEqual(_hex(power['states'][1]['fill']), '#37394E')
        self.assertEqual(power['states'][1]['border']['resource'], 'Afterburn - Elipse 0 Thick')
        mute = self.ctl('Main SD', 'Main Volume Mute')
        self.assertEqual([s['name'] for s in mute['states']], ['Muted', 'Level 1', 'Level 2', 'Level 3'])

    def test_red_is_a_stroke_and_no_state_fills_red(self):
        """afterburn-25."""
        on = self.ctl('Main VC', 'Share Content')['states'][1]
        self.assertEqual((_hex(on['fill']), _hex(on['stroke'])), ('#37394E', '#D32A2A'))
        reds = {'#D32929', '#D32A2A'}
        for pg in self.pages.values():
            for c in pg['controls']:
                for s in c.get('states') or ():
                    self.assertNotIn(_hex(s['fill']), reds, (pg['name'], c['name']))

    def test_the_only_drawn_container_is_the_search_list_and_rect_is_only_the_video(self):
        """afterburn-27, -28."""
        shapes = [(pg['name'], c['name'], c['rect'], _hex(c['fill']), _hex(c['stroke']))
                  for pg in self.pages.values() for c in pg['controls']
                  if c['type'] == 'PBShape' and c['fill'] and c['border']
                  and c['border']['resource'] == 'Afterburn - 10 Radius 2 Thick']
        self.assertEqual(shapes, [('VTC Search Results', 'Search Result List Background', (156, 75, 345, 385),
                                   '#37394E', '#6A6E89')])
        rect = [(pg['name'], c['type']) for pg in self.pages.values() for c in pg['controls']
                if (c.get('border') or {}).get('resource') == '2D Rectangle']
        self.assertTrue(rect)
        self.assertEqual({t for _, t in rect}, {'PBVideo'})

    def test_the_keypad_keys_press_to_a_circle_and_the_rail_has_no_ghost(self):
        """afterburn-29."""
        for page, name in (('VTC Dialer', 'Dialer Keypad 1'), ('TV', 'TV Keypad 1')):
            key = self.ctl(page, name)
            self.assertIsNone(key['states'][0]['fill'])
            self.assertEqual(key['states'][1]['border']['resource'], 'Afterburn - Elipse 0 Thick')
        self.assertEqual(self.ctl('Camera Settings', 'Camera Zoom -')['states'][0]['border']['resource'],
                         'Afterburn - 10 Radius 0 Thick')
        self.assertEqual(len(self.ctl('Main SD', 'Display Power')['states']), 2)

    def test_the_dialers_buttons_are_the_outlined_icon_ones_and_end_call_is_a_list_row(self):
        """afterburn-16."""
        for name in ('Swap', 'Contacts', 'Call'):
            self.assertEqual(self.ctl('VTC Dialer', name)['rect'][2:], (154, 64), name)
        self.assertEqual(self.ctl('Main VC', 'End Call')['rect'], (0, 266, 178, 50))


if __name__ == '__main__':
    unittest.main()
