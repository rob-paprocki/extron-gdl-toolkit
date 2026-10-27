"""Shockwave's truth ledger (gdl/designsys/truth/shockwave.json): is what its
system says about its template what the template does?

Three layers. The ledger is complete and `python -m gdl.designsys audit
shockwave` is at zero. The profile and README say what each entry's fix
promises, so a later edit cannot quietly bring an old claim back. And, where
the seeds are here (Git LFS), the template facts the ledger rests on are read
off the seed again - its art, its captions, its modals, its fonts - so the
ledger's evidence is a check, not a note.
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
from gdl import designsys, spec  # noqa: E402
from gdl.designsys import audit  # noqa: E402

REPO = os.path.dirname(HERE)
SEED = seed_path('Shockwave 1035.gdl')


class _Text(str):
    """A long text whose failure message names its length, not all of it."""

    def __repr__(self):
        return f'<{len(self)} characters>'


def _colors(p):
    return {c['name']: c['value'] for c in p['colors']}


class TestShockwavesLedger(unittest.TestCase):
    def setUp(self):
        self.p = designsys.load('shockwave')
        self.ledger = audit.load_ledger('shockwave')

    def test_it_has_an_entry_for_every_disagreement(self):
        """The grammar measurement found 31 claims of Shockwave's profile and
        README that its pages contradict, and the PR8 review two more (the
        14 pt floor and the 2 mm gap, missing from Differences), and the call
        mode's measurement six (shockwave-33 to 38: the call page and its
        Share Content art, its dialer and question, the Header's count, the
        mic and display, and the call keys resting ringed, as the template's
        do), and its review three (shockwave-39 to 41: the dialer's captions
        and the answers' art, the answers' IDs, and the 725's call page's
        launchers): one entry each, in order."""
        ids = [e['id'] for e in self.ledger['entries']]
        self.assertEqual(ids, [f'shockwave-{i:02d}' for i in range(45)])

    def test_shockwave_is_done(self):
        self.assertEqual(audit.audit('shockwave'), [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(designsys.main(['gdl.designsys', 'audit', 'shockwave']), 0)

    def test_it_keeps_differing_where_it_says_and_says_why(self):
        """The lit captions of the variants with one, and the gates: the
        slider and the overlapping tiles, the 14 pt floor and a designer's own
        2 mm (the PR8 review: Differences lacked the last two), and the
        incoming call's answers' IDs. The tab captions are the twin the region
        page draws, as the template does (shockwave-03); the call keys rest
        ringed as the template's do (shockwave-38); and the hub's Volume Level
        strip, which a group binding shows on every page (shockwave-44)."""
        dev = {e['id']: e for e in self.ledger['entries'] if e['status'] == 'deviation'}
        self.assertEqual(sorted(dev), ['shockwave-20', 'shockwave-30', 'shockwave-31', 'shockwave-32', 'shockwave-40',
                                     'shockwave-41', 'shockwave-42', 'shockwave-43', 'shockwave-44'])
        for e in dev.values():
            self.assertTrue(e['reason'].strip(), e['id'])

    def test_a_fix_that_changes_what_builds_says_so(self):
        """What the region page draws differently from before is named in the
        entry: the tab twins, the Mute, the lit captions, the clock and the
        scrim."""
        builds = {e['id'] for e in self.ledger['entries'] if e.get('builds')}
        self.assertTrue({'shockwave-03', 'shockwave-08', 'shockwave-13', 'shockwave-14', 'shockwave-20'} <= builds,
                        builds)


class TestWhatTheProfileSays(unittest.TestCase):
    def setUp(self):
        self.p = designsys.load('shockwave')
        self.readme = _Text(designsys.readme(self.p))
        self.docs = {k: _Text(v) for k, v in designsys.component_docs(self.p).items()}

    def state(self, node, name):
        return next(s for s in node['states'] if s['name'] == name)

    def test_a_mute_rests_gray_and_lights_red(self):
        """Every template Mute rests 440x440_gray_nsel (712x440 on a rail) and
        lights red with #75063C (shockwave-08)."""
        r = self.p['regions']
        self.assertEqual(r['mute']['icon'], 'gray')
        on = self.state(r['mute'], 'On')
        self.assertEqual((on['icon'], on['color']), ('red', 'alert'))
        hub = self.state(r['hub']['mute'], 'On')
        self.assertEqual((hub['icon'], hub['color']), ('red', 'alert'))

    def test_a_lit_caption_is_its_familys_dark(self):
        """Gray lights ink, yellow #946E06, red #75063C, green #355424; a key
        in a source popup or on a 320 page lights #474747 (shockwave-20)."""
        c = _colors(self.p)
        self.assertEqual((c['ink'], c['alert'], c['caution'], c['go']),
                         ('#000000', '#75063C', '#946E06', '#355424'))
        r = self.p['regions']
        for node, token in ((r['help'], 'caution'), (r['power'], 'alert'),
                            (r['window']['power'], 'go'), (r['window']['cancel'], 'alert')):
            self.assertEqual(self.state(node, 'On')['color'], token, node)
        self.assertEqual(self.state(self.p['buttons']['key'], 'On')['color'], 'text-secondary')
        self.assertEqual(self.state(self.p['buttons']['tile'], 'On')['color'], 'ink')
        self.assertEqual(r['source']['button']['variant'], 'key')
        self.assertEqual(r['page']['button']['variant'], 'key')
        live = json.loads(self.p['examples']['states'])[-1]
        self.assertEqual((live['icon'], live['color']), ('green', 'go'))
        names = {t['name'] for t in designsys.tokens(self.p)['color']['tokens']}
        self.assertTrue({'caution', 'go', 'clock'} <= names, names)

    def test_the_footer_clock_is_the_templates(self):
        """#C0C0C0 in Open Sans 14, not raised's #999999 in 16 (shockwave-13)."""
        c = _colors(self.p)
        self.assertEqual(c['clock'], '#C0C0C0')
        self.assertEqual(self.p['defaults']['clock'], {'type': 'button', 'color': 'clock'})
        self.assertEqual(next(t['pt'] for t in self.p['type'] if t['name'] == 'button'), 14)

    def test_the_scrim_is_black_at_alpha_166(self):
        """Every seed modal is #000000 at transparency 35 (shockwave-14)."""
        self.assertEqual(_colors(self.p)['scrim'], '#000000A6')

    def test_the_tabs_are_neither_centered_nor_butted(self):
        ex = self.p['examples']
        self.assertEqual(ex['source']['rect'], [169, 0, 152, 91])
        self.assertIn('1 px apart', ex['group_note'])
        self.assertNotIn('butted', ex['group_note'])
        self.assertIn('one every 153 px (1 px apart)', self.readme)

    def test_the_source_tab_says_where_its_name_is_drawn(self):
        usage = self.p['buttons']['source']['usage']
        self.assertIn('draws no caption of its own', usage)
        self.assertIn('iphone (AUX)', usage)
        self.assertNotIn('apple-tv_white.', usage)

    def test_the_hub_header_depth_is_measured_with_the_seeds_six(self):
        """The probe canvas (TestShockwavesHubHeader) heads a hub with the
        seed's six captions, not ShareLink and HDMI (shockwave-05)."""
        canvas = os.path.join(HERE, 'data', 'design-hub-shockwave', 'Tabs.dc.html')
        with open(canvas, encoding='utf-8') as fh:
            tabs = re.findall(r'name="Tab\d" variant="source" icon="([\w-]+)">([^<]+)<', fh.read())
        self.assertEqual([t for _, t in tabs], ['PC', 'Laptop', 'Blu-ray', 'Doc Cam', 'Tuner', 'AUX'])

    def test_a_standard_popup_is_no_card(self):
        """The 921x574 popups draw nothing of their own (shockwave-19)."""
        self.assertIn('921x574 for a standard popup', self.readme)
        self.assertNotIn('popup card', self.readme)
        size = {t['name']: t['usage'] for t in designsys.tokens(self.p)['size']['tokens']}
        self.assertIn('standard popup', size['popup-width'])
        self.assertIn('standard popup', size['popup-height'])

    def test_a_popup_the_program_shows_is_no_page(self):
        """The incoming call is a modal popup (shockwave-18); a modal the
        program hides needs no Close (shockwave-16)."""
        self.assertIn('**A page or popup the program opens by itself**, like an incoming call', self.readme)
        self.assertIn('A modal the program hides, or whose own answers close it, needs no Close.', self.readme)

    def test_the_layout_is_the_working_pages_and_the_start_page_is_said_apart(self):
        """shockwave-24: Start has no bars or well, and Room Mode VC is a card."""
        self.assertIn("Shockwave's working pages are composed the same way", self.readme)
        self.assertIn('a splash page with no bars or well', self.readme)
        self.assertIn('Room Mode VC', self.p['layout']['start'])
        first = self.p['layout']['regions'][0]
        for word in ('VTC', 'Main SD Screen Arrows', 'Main VC Share Content'):
            self.assertIn(word, first)
        self.assertIn('169x59', self.p['layout']['regions'][1])

    def test_a_theme_is_set_per_page(self):
        """Start is Saturn, the working pages haze (shockwave-25)."""
        self.assertIn('Set per page: the working pages on `haze`, the Start page on `saturn`.', self.readme)
        self.assertIn('set per page', self.docs['Page'])
        self.assertNotIn('The image is drawn on every page', self.readme)

    def test_the_main_area_example_is_what_the_template_stands_in_main(self):
        """The Start pill, 550,407 179x80 on the page, is 382,287 in the well
        at 168,120 (shockwave-26); the Example is the working page."""
        area = self.docs['MainArea']
        self.assertIn('name="Start" variant="pill" icon="yellow"', area)
        self.assertIn('left: 382px; top: 287px; width: 179px; height: 80px', area)
        self.assertNotIn('Select a Source', area)
        self.assertIn("a working page's Center draws it", self.readme)

    def test_a_small_pages_back_stands_where_more_did(self):
        """Shockwave's 320 puts More and Back in the same place at the foot's
        right, not at the strip's end (shockwave-27)."""
        self.assertIn('come back by Back where More stood', self.docs['Page'])
        self.assertNotIn("Back at the strip's end", self.docs['Page'])

    def test_a_hubs_header_is_its_title_strip(self):
        self.assertIn("A region page is drawn in the hub's own grammar instead", self.readme)
        self.assertIn('for a plain Page that heads itself', self.p['layout']['hub_header']['_source'])

    def test_the_old_claims_are_gone(self):
        """Every `gone` phrase of the ledger, once more over the profile and
        the READMEs (the audit checks it too; this names what was wrong)."""
        words = ' '.join((self.readme + ' ' + ' '.join(self.docs.values()) + ' '
                          + json.dumps({k: v for k, v in self.p.items() if k != 'panels'}, ensure_ascii=False)
                          ).split())
        for phrase in ('a `square` Mute 80x80 below (icon red)', 'the row centered on the page',
                       'butted', 'blue to share', 'red for power and mute', 'About 40x40',
                       '#3B2F2AA6', "is every modal's card", 'no seed label or button authors bold'):
            self.assertNotIn(phrase, words)


@unittest.skipUnless(usable(SEED), 'seeds/Shockwave 1035.gdl is not here (git lfs pull)')
class TestTheLedgerAgainstTheSeed(unittest.TestCase):
    """The template facts the ledger rests on, read off seeds/Shockwave
    1035.gdl: each assertion is the evidence of the entry named."""

    @classmethod
    def setUpClass(cls):
        import measure_series
        from gdl.project import Project
        cls.ms = measure_series
        cls.proj = Project.open(SEED)
        cls.pages = {(pg['kind'], pg['name']): pg for pg in measure_series.seed_pages(cls.proj)}

    def page(self, name, kind='page'):
        return self.pages[(kind, name)]

    def ctl(self, page, name, nth=0):
        got = [c for c in page['controls'] if c['name'] == name]
        return got[nth]

    def hexes(self, c):
        return [lk['text'] for lk in c['looks']]

    def test_the_bar_is_two_blocks_and_the_tabs_stand_1_px_apart(self):
        """shockwave-00 to -02."""
        pg = self.page('Main SD')
        self.assertEqual([self.ctl(pg, n)['rect'] for n in ('Shape1_1', 'Shape1_1_ID0')],
                         [[0, 0, 168, 91], [1087, 0, 193, 91]])
        tabs = [self.ctl(pg, n, 0)['rect'] for n in ('SD PC', 'SD Laptop', 'SD Blu-ray', 'SD Doc Cam', 'SD Tuner', 'SD AUX')]
        self.assertEqual([t[0] for t in tabs], [169, 322, 475, 628, 781, 934])
        self.assertEqual({tuple(t[2:]) for t in tabs}, {(152, 91)})
        share = self.page('Main VC Share Content')
        self.assertEqual([self.ctl(share, 'Shape2', 1)['rect']], [[781, 0, 499, 91]])
        self.assertEqual([self.ctl(share, n)['rect'][0] for n in ('PC', 'Laptop', 'Aux', 'Doc Cam')],
                         [169, 322, 475, 628])

    def test_a_tab_draws_no_caption_and_its_name_is_a_twin(self):
        """shockwave-03."""
        pg = self.page('Main SD')
        tab, twin = self.ctl(pg, 'SD PC', 0), self.ctl(pg, 'SD PC', 1)
        self.assertEqual(self.hexes(tab), [None, None])
        self.assertEqual(self.hexes(twin), ['#FFFFFFFF', '#FFFFFFFF'])
        self.assertEqual((tab['id'], twin['id']), (8052, 8052))
        self.assertEqual(twin['rect'], [169, 55, 152, 36])
        self.assertEqual([lk['art'] for lk in twin['looks']], [None, None])

    def test_the_seeds_mutes_rest_gray_and_light_red(self):
        """shockwave-08."""
        pg = self.page('Main SD')
        for name, rest, lit in (('Volume Mute', '440x440_gray_nsel.png', '440x440_red_sel.png_1'),
                                ('Display Mute', '712x440_gray_nsel.png', '712x440_red_sel-2.png')):
            c = self.ctl(pg, name)
            self.assertEqual([lk['art'] for lk in c['looks']], [rest, lit], name)
            self.assertEqual(c['looks'][1]['text'], '#75063CFF', name)

    def test_the_footer_clock_and_room_mode(self):
        """shockwave-12, -13."""
        pg = self.page('Main SD')
        clock = self.ctl(pg, 'Date/Time')
        self.assertEqual(clock['rect'], [402, 725, 475, 49])
        self.assertEqual(clock['text_color'], {'A': 255, 'R': 192, 'G': 192, 'B': 192})
        self.assertEqual((clock['face'], clock['pt']), ('Open Sans', 14))
        mode = self.ctl(pg, 'Room Mode')
        self.assertEqual(mode['rect'], [168, 720, 169, 59])
        self.assertEqual([lk['art'] for lk in mode['looks']], ['1248x440_r_gray_nsel.png', '1248x440_r_gray_sel.png'])
        multi = self.page('Main Multi-Window')
        self.assertEqual(self.ctl(multi, 'Preset Selection')['id'], 8119)
        start = self.page('Start')
        self.assertEqual((self.ctl(start, 'Date/Time1')['face'], self.ctl(start, 'Date/Time1')['pt']), ('Roboto', 72))

    def test_audio_control_is_in_the_right_rail_on_the_1035_only_by_series(self):
        """shockwave-09 (this seed: the right rail)."""
        self.assertEqual(self.ctl(self.page('Main SD'), 'Audio Control')['rect'], [1127, 573, 120, 110])

    def test_the_left_rail_is_the_modes_column(self):
        """shockwave-07."""
        vc = self.page('Main VC')
        self.assertEqual(self.ctl(vc, 'VTC Label')['rect'], [29, 109, 120, 61])
        self.assertEqual([self.ctl(vc, n)['rect'] for n in ('Initiate Call', 'End Call', 'VC Privacy')],
                         [[29, 170, 120, 60], [29, 240, 120, 60], [29, 310, 120, 60]])
        self.assertEqual([self.ctl(vc, n)['rect'][1] for n in ('Display Control', 'Screen Control', 'Lighting Control')],
                         [469, 573, 678])
        arrows = self.page('Main SD Screen Arrows')
        self.assertEqual(self.ctl(arrows, 'Screen Label')['rect'], [29, 434, 115, 61])
        sd = self.page('Main SD')
        screen, lighting = self.ctl(sd, 'Screen Control')['rect'], self.ctl(sd, 'Lighting Control')['rect']
        self.assertEqual(lighting[1] - screen[1], 104)
        self.assertEqual(screen[3], 110)

    def test_every_modal_is_black_at_alpha_166_over_a_gray_card(self):
        """shockwave-14, -28."""
        modals = [pg for (kind, _), pg in self.pages.items() if kind == 'popup' and pg['modal']]
        self.assertTrue(len(modals) >= 12)
        for pg in modals:
            self.assertEqual(pg['paint'], '#000000A6', pg['name'])
        self.assertEqual(self.ctl(self.page('Help', 'popup'), 'Modal Window_ID0')['paint'], '#999999FF')
        self.assertEqual(self.ctl(self.page('Offline Page', 'popup'), 'Offline Window')['paint'], '#FFFFFFBF')

    def test_a_close_is_50x50_seven_px_in(self):
        """shockwave-15."""
        close = self.ctl(self.page('Camera Select', 'popup'), 'Close Camera Select')
        card = self.ctl(self.page('Camera Select', 'popup'), 'Modal Window')
        self.assertEqual(close['rect'][2:], [50, 50])
        self.assertEqual(card['rect'][0] + card['rect'][2] - (close['rect'][0] + close['rect'][2]), 7)
        self.assertEqual(close['rect'][1] - card['rect'][1], 7)

    def test_the_windows_that_have_no_close(self):
        """shockwave-16."""
        for name in ('Confirmation', 'Incoming Call', 'Starting Up', 'Powering Down', 'Offline Page'):
            pg = self.page(name, 'popup')
            self.assertFalse([c for c in pg['controls'] if (c['name'] or '').startswith('Close')], name)
        for name in ('Help', 'Camera Select', 'Display Control'):
            pg = self.page(name, 'popup')
            self.assertTrue([c for c in pg['controls'] if (c['name'] or '').startswith('Close')], name)

    def test_a_sources_controls_are_a_standard_popup_and_not_a_card(self):
        """shockwave-17, -19: transparent 921x574 popups in one group; the
        only page flips are Room Mode and Share Content."""
        for name in ('Aux', 'Blu-ray', 'Camera Control', 'Doc Cam', 'Laptop', 'PC', 'Tuner', 'VTC Dialer',
                     'VTC Keyboard', 'VTC Search Result', 'Apple TV'):
            pg = self.page(name, 'popup')
            self.assertFalse(pg['modal'], name)
            self.assertEqual(tuple(pg['size']), (921, 574), name)
            self.assertIsNone(pg['paint'], name)
            self.assertFalse([c for c in pg['controls'] if c['type'] == 'PBShape'], name)

    def test_the_incoming_call_is_a_modal_popup(self):
        """shockwave-18."""
        pg = self.page('Incoming Call', 'popup')
        self.assertTrue(pg['modal'])
        self.assertEqual(self.ctl(pg, 'Modal Window')['rect'], [288, 173, 703, 453])

    def test_lit_captions_are_the_familys_dark(self):
        """shockwave-20, -21, -22."""
        sd, vc = self.page('Main SD'), self.page('Main VC')
        self.assertEqual(self.ctl(sd, 'Help')['looks'][1]['text'], '#946E06FF')
        self.assertEqual(self.ctl(sd, 'Power Down')['looks'][1]['text'], '#75063CFF')
        self.assertEqual(self.ctl(vc, 'Initiate Call')['looks'][1]['text'], '#355424FF')
        self.assertEqual(self.ctl(vc, 'VC Privacy')['looks'][1]['text'], '#946E06FF')
        self.assertEqual(self.ctl(vc, 'End Call')['looks'][1]['text'], '#75063CFF')
        self.assertEqual(self.ctl(sd, 'Display On')['looks'][1]['text'], '#000000FF')
        confirm = self.page('Confirmation', 'popup')
        down, cancel = self.ctl(confirm, 'Power Down'), self.ctl(confirm, 'Confirmation Cancel')
        self.assertEqual((down['looks'][0]['art'], down['looks'][1]['text']),
                         ('1248x440_green_round_outline_nsel.png', '#355424FF'))
        self.assertEqual((cancel['looks'][0]['art'], cancel['looks'][1]['text']),
                         ('1248x440_red_round_outline_nsel.png', '#75063CFF'))
        # A source popup's keys light #474747; a modal's #000000.
        self.assertEqual(self.ctl(self.page('Blu-ray', 'popup'), 'Blu-ray Rewind')['looks'][1]['text'], '#474747FF')
        self.assertEqual(self.ctl(self.page('Camera Select', 'popup'), 'Camera 1')['looks'][1]['text'], '#000000FF')
        flash = self.ctl(self.page('VTC Dialer', 'popup'), 'VC Flash')
        self.assertEqual((flash['looks'][0]['art'], flash['looks'][1]['text']),
                         ('960x440_flash_outline_blue_nsel.png', '#474747FF'))
        share = self.ctl(vc, 'Share Content')
        self.assertEqual(share['rect'], [1123, 7, 120, 75])
        self.assertEqual([lk['art'] for lk in share['looks']],
                         ['712x440_share-content_nsel.png', '712x440_stop-sharing_sel.png'])

    def test_start_and_room_mode_vc_are_composed_apart(self):
        """shockwave-24, -25."""
        start, mode = self.page('Start'), self.page('Room Mode VC')
        self.assertEqual(start['background'], 'SW_start_bkgd_01_mockup.png')
        self.assertEqual(self.page('Main SD')['background'], 'SW_bkgd_01.png')
        self.assertEqual(mode['background'], '1024x600_bkgd.png')
        self.assertEqual(self.ctl(mode, 'Modal Window')['rect'], [260, 154, 759, 492])
        self.assertEqual(self.ctl(start, 'Start')['rect'], [550, 407, 179, 80])
        self.assertFalse([c for c in mode['controls'] if c['type'] == 'PBShape' and c['rect'][3] <= 91])

    def test_the_wells_nothing_but_the_sources_popup_region(self):
        """shockwave-26: Main SD's one well, and the popup region in it."""
        pg = self.page('Main SD')
        well = self.ctl(pg, 'Shape1')['rect']
        inside = [c for c in pg['controls']
                  if c['type'] not in ('PBPopupPageReference', 'PBShape') and well[0] <= c['rect'][0] < well[0] + well[2]
                  and well[1] + 30 <= c['rect'][1] < well[1] + well[3]]
        self.assertEqual([c['name'] for c in inside], [])
        self.assertEqual(self.ctl(pg, 'Popup Page Reference1')['rect'], [172, 124, 921, 574])

    def test_translucent_fills(self):
        """shockwave-23."""
        pg = self.page('Main SD')
        self.assertEqual(self.ctl(pg, 'Shape1')['paint'], '#FFFFFF26')
        self.assertEqual(self.ctl(pg, 'SD PC', 0)['looks'][1]['fill'], '#FFFFFF3C')

    def test_one_label_is_bold_and_the_sizes_are_more_than_the_scale(self):
        """shockwave-29."""
        proj = self.proj
        top = next(proj.instances('PBProject'))
        bold, sizes = [], set()
        for field in ('pagesField', 'popupPagesField'):
            for pg in proj.items(proj.field(top, field)):
                for c in proj.items(proj.field(pg, 'controlsField')):
                    fonts = [proj.field(c, 'fontField')] + [proj.field(s, 'fontField') for s in proj.states(c)]
                    for f in filter(None, fonts):
                        style = proj.field(f, 'styleField')
                        if proj.field(f, 'nameField') == 'Open Sans':
                            sizes.add(proj.field(f, 'pointSizeField'))
                        if style and proj.field(style, 'boldField'):
                            bold.append((proj.field(pg, 'nameField'), proj.field(c, 'nameField')))
        self.assertEqual(bold, [('Display Control', 'Display 1 Mute')])
        self.assertTrue({13, 20, 22, 24, 28, 30, 36} <= sizes, sizes)

    def test_the_slider_is_52_wide_and_the_display_buttons_4_apart(self):
        """shockwave-30."""
        pg = self.page('Main SD')
        self.assertEqual(self.ctl(pg, 'SD Volume Slider')['rect'], [1163, 163, 52, 315])
        ys = [self.ctl(pg, n)['rect'] for n in ('Display On', 'Display Off', 'Display Mute')]
        self.assertEqual([r[1] for r in ys], [170, 254, 338])
        self.assertEqual({r[3] for r in ys}, {80})


@unittest.skipUnless(usable(SEED), 'seeds/Shockwave 1035.gdl is not here (git lfs pull)')
class TestTheSeedsArtIsTheKits(unittest.TestCase):
    """The seed's tab, Room Mode, Mute and Close art are the kit's files pixel
    for pixel, under the seed's names (shockwave-04, -08, -12, -15)."""

    PAIRS = (
        ('744x456_pc_nsel.png', 'buttons/744x456 Inputs/744x456_pc_white.png'),
        ('744x456_laptop_nsel.png', 'buttons/744x456 Inputs/744x456_laptop_white.png'),
        ('744x456_iphone_nsel.png', 'buttons/744x456 Inputs/744x456_iphone_white.png'),
        ('744x456_tuner_nsel.png', 'buttons/744x456 Inputs/744x456_tuner_white.png'),
        ('744x456_doc-cam_nsel.png', 'buttons/744x456 Inputs/744x456_doc-cam_white.png'),
        ('744x456_polycom_nsel.png', 'buttons/744x456 Inputs/744x456_polycom_white.png'),
        ('1248x440_r_gray_nsel.png', 'buttons/1248x440/1248x440_gray_round_nsel.png'),
        ('1248x440_r_gray_sel.png', 'buttons/1248x440/1248x440_gray_round_sel.png'),
        ('440x440_red_sel.png_1', 'buttons/440x440/440x440_red_sel.png'),
        ('712x440_red_sel-2.png', 'buttons/712x440/712x440_red_sel.png'),
        ('960x440_yellow_sel.png', 'buttons/960x440/960x440_yellow_outline_nsel.png'),
        ('SW_close.png_1', 'icons/440x440 Black/black_close.png'),
    )

    def test_each_is_the_kits(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('no Pillow')
        import measure_series
        from gdl.project import Project
        # The install's kit, not a slice of it vendor/ holds (its extracted
        # Share Content art, Shockwave/Extracted).
        roots = [os.path.join(r, 'Shockwave') for r in spec.RESOURCE_ROOTS if r]
        root = next((r for r in roots if os.path.isdir(os.path.join(r, 'buttons'))), None)
        if not root:
            self.skipTest("Extron's Shockwave kit is not here")
        proj = Project.open(SEED)
        for seed_name, kit in self.PAIRS:
            with self.subTest(art=seed_name):
                data = measure_series.template_art(proj, seed_name)
                self.assertTrue(data, f'{seed_name} is not in the seed')
                a = Image.open(io.BytesIO(data)).convert('RGBA')
                b = Image.open(os.path.join(root, kit)).convert('RGBA')
                self.assertEqual(a.size, b.size)
                self.assertEqual(a.tobytes(), b.tobytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
