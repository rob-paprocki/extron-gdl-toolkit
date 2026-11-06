"""The render rules gdl.compose draws by, each pinned on its own.

tests/score.py scores them all at once against the synthetic fixture's
snapshots (docs/render-fidelity.md); these hold each rule to what was measured,
so a change that drops one fails here by name rather than as a page a little
worse. They draw in the Open Sans the repo carries (gdl/fonts/), so they need
Pillow and nothing recovered.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OPEN_SANS = os.path.join(ROOT, 'gdl', 'fonts', 'opensans-regular.ttf')


def _pillow(case):
    try:
        from PIL import Image, ImageFont  # noqa: F401
    except ImportError:
        case.skipTest('Pillow not installed; gdl.compose draws with it')


class TestTheCaptionsPadding(unittest.TestCase):
    """GDI+ lays a caption out in its box less 1/6 em a side
    (docs/render-fidelity.md section 9): a left- or right-aligned line starts
    that far in, and every line wraps in the box less both sides."""

    def setUp(self):
        _pillow(self)
        from PIL import ImageFont
        from gdl import compose
        self.compose = compose
        self.px = 40 * compose.PT
        self.fnt = ImageFont.truetype(OPEN_SANS, size=self.px)

    def _ink(self, text, align, box=(0, 0, 400, 100), pad=None):
        """The ink's bounding box of `text` drawn in `box` at `align`, with
        PAD_EM as shipped or as `pad`."""
        from PIL import Image
        img = Image.new('RGBA', (box[0] + box[2], box[1] + box[3]), (0, 0, 0, 0))
        was = self.compose.PAD_EM
        if pad is not None:
            self.compose.PAD_EM = pad
        try:
            self.compose.draw_text(img, box, text, self.fnt, (255, 255, 255, 255), align)
        finally:
            self.compose.PAD_EM = was
        return img.getchannel('A').getbbox()

    def test_the_padding_is_a_sixth_of_the_em(self):
        self.assertAlmostEqual(self.compose.PAD_EM, 1 / 6)

    def test_a_left_aligned_line_starts_a_sixth_of_an_em_in(self):
        pad = self.px / 6
        moved = self._ink('Hall', 4)[0] - self._ink('Hall', 4, pad=0)[0]
        self.assertAlmostEqual(moved, pad, delta=1)

    def test_a_right_aligned_line_ends_a_sixth_of_an_em_in(self):
        pad = self.px / 6
        moved = self._ink('Hall', 5, pad=0)[2] - self._ink('Hall', 5)[2]
        self.assertAlmostEqual(moved, pad, delta=1)

    def test_a_centred_line_does_not_move(self):
        self.assertEqual(self._ink('Hall', 3), self._ink('Hall', 3, pad=0))

    def test_a_line_wraps_in_the_box_less_the_padding(self):
        """A caption a little narrower than its box, but wider than the box
        less 1/6 em a side, takes two lines."""
        text = 'Hall Room'
        w = self.compose.measure(text, self.fnt) + self.px / 6
        box = (0, 0, int(w) + 1, 200)
        one = self._ink(text, 3, box, pad=0)
        two = self._ink(text, 3, box)
        self.assertGreater(two[3] - two[1], 1.5 * (one[3] - one[1]))


class TestTheLinesShown(unittest.TestCase):
    """GDI+ shows the lines of a caption that fit its box, a line counting if
    half of it does, and trims the last one shown to the characters that fit
    (compose.fitted, docs/render-fidelity.md section 9)."""

    def setUp(self):
        _pillow(self)
        from PIL import ImageFont
        from gdl import compose
        self.compose = compose
        self.fnt = ImageFont.truetype(OPEN_SANS, size=40 * compose.PT)
        asc, desc = compose.metrics(self.fnt)
        self.lh = asc + desc

    def _fitted(self, text, width, lines_deep):
        return self.compose.fitted(text, self.fnt, width, lines_deep * self.lh, self.lh,
                                   lambda s, f: self.compose.measure(s, f))

    def test_a_caption_one_line_deep_is_trimmed_to_the_characters_that_fit(self):
        """The fixture's Italic40: 340 px less 1/6 em a side, 1.17 lines deep -
        GUI Designer's snapshot shows 'Type 40 Itali'."""
        width = 340 - 2 * self.fnt.size / 6
        self.assertEqual(self.compose.wrap('Type 40 Italic', self.fnt, width,
                                           lambda s, f: self.compose.measure(s, f)), ['Type 40', 'Italic'])
        self.assertEqual(self._fitted('Type 40 Italic', width, 1.17), ['Type 40 Itali'])

    def test_a_second_line_two_thirds_in_the_box_is_shown(self):
        width = self.compose.measure('Type 40', self.fnt) + 1
        self.assertEqual(self._fitted('Type 40 Italic', width, 1.68), ['Type 40', 'Italic'])

    def test_one_line_is_shown_however_shallow_the_box(self):
        self.assertEqual(self._fitted('Overview', 400, 0.4), ['Overview'])

    def test_the_last_line_shown_stops_at_its_paragraphs_end(self):
        self.assertEqual(self._fitted('First\nSecond\nThird', 400, 2), ['First', 'Second'])

    def test_a_word_split_mid_way_trims_where_the_split_was(self):
        """A word too long for the box is split; trimmed, its last line shown
        carries on from the split, not after a space."""
        width = self.compose.measure('Abcdefgh', self.fnt)
        lines = self.compose.wrap('Abcdefghijklmnopqrstuvwxyz', self.fnt, width,
                                  lambda s, f: self.compose.measure(s, f))
        self.assertGreater(len(lines), 2)
        self.assertEqual(self._fitted('Abcdefghijklmnopqrstuvwxyz', width, 2), lines[:2])


class TestWhatACaptionLoses(unittest.TestCase):
    """compose.caption_fit, which gdl.spec check and verify_built hold every
    live caption to: what GUI Designer's layout cuts of one - characters it
    trims, a word it breaks, ink past the box - and nothing where it shows
    every word whole."""

    def setUp(self):
        _pillow(self)
        from PIL import ImageFont
        from gdl import compose
        self.compose = compose
        self.at18 = ImageFont.truetype(OPEN_SANS, size=18 * compose.PT)

    def fit(self, box, text, fnt=None, align=3):
        return self.compose.caption_fit(box, text, fnt or self.at18, align)

    def test_the_525s_volume_heading_is_trimmed_to_volum(self):
        """Shockwave 525's region Main, built at main 0aeccf7: 'Volume' at
        18 pt in its template's 91x37 box - GUI Designer's snapshot reads
        'Volum'. 88 px of words, and 4.125 px of padding a side."""
        got = self.fit((704, 18, 91, 37), 'Volume')
        self.assertEqual([k for k, _ in got], ['trims'])
        self.assertIn("'Volum' of 'Volume'", got[0][1])
        self.assertIn('97 px across', got[0][1])

    def test_the_width_it_names_holds_it(self):
        self.assertEqual(self.fit((701, 18, 97, 37), 'Volume'), [])
        self.assertEqual([k for k, _ in self.fit((701, 18, 96, 37), 'Volume')], ['trims'])

    def test_a_word_wrapped_whole_onto_the_next_line_is_not_cut(self):
        self.assertEqual(self.fit((0, 0, 200, 80), 'Display Control'), [])

    def test_a_word_too_wide_for_a_deep_box_is_split(self):
        """The fixture's LongWord: every letter shows, on three lines."""
        got = self.fit((420, 370, 160, 150), 'Abcdefghijklmnopqrstuvwxyz')
        self.assertEqual([k for k, _ in got], ['splits'])
        self.assertIn("'Abcdefghijklmnopqrstuvwxyz'", got[0][1])

    def test_a_word_too_wide_after_another_is_split_too(self):
        """Afterburn 1035 Portrait's Main Select Source 'Video Conference',
        13 pt in 90x102: 'Conference' is 96 px across, 84 inside the
        padding. wrap() broke a word too wide only at a line's start, and
        set this one whole on its own line, its ink past both sides."""
        from PIL import ImageFont
        at13 = ImageFont.truetype(OPEN_SANS, size=13 * self.compose.PT)
        got = self.fit((12, 1130, 90, 102), 'Video Conference', at13)
        self.assertEqual([k for k, _ in got], ['splits'])
        self.assertIn("'Conference'", got[0][1])

    def test_a_line_too_many_for_the_box_is_trimmed(self):
        got = self.fit((0, 0, 300, 70), 'First line\nSecond line\nThird line')
        self.assertEqual([k for k, _ in got], ['trims'])
        self.assertIn('3 lines need', got[0][1])

    def test_one_line_in_a_box_too_shallow_for_its_ink_is_clipped(self):
        """One line always shows (fitted), its ink cut by the box Build
        rasterizes it into."""
        got = self.fit((0, 0, 200, 12), 'Hamburg')
        self.assertEqual([k for k, _ in got], ['clips'])
        self.assertIn('top', got[0][1])

    def test_a_caption_that_fits_says_nothing(self):
        for box, text in (((0, 0, 460, 36), 'Type 14 Regular'), ((0, 0, 120, 260), 'The quick brown fox')):
            self.assertEqual(self.fit(box, text), [], text)


class TestTheInkGUIDesignerCuts(unittest.TestCase):
    """GUI Designer cuts a live caption's ink flat at its box, row by row
    (compose.caption_fit's 'clips', line_ink, CLIP_PX). Its own snapshots of
    seeds/Turbulence 720.gdl, 1.28.0.7, 2026-11-05: the Confirmation and
    Incoming Call questions, 20 pt Open Sans Light centred in 316x64 at
    242,144, end on their box's last row; in a copy with those boxes shrunk
    about their middles (Shrunk720.gdl) it cut the rows past the new box off
    and drew both lines still. Every row and column below is read off those
    snapshots: the first and last row, and column, at least half inked."""

    LIGHT = os.path.join(ROOT, 'gdl', 'fonts', 'opensans-light.ttf')
    BOX = (242, 144, 316, 64)
    QUESTIONS = {'Confirmation': 'Do you want to power down the system?',
                 'Incoming Call': 'Incoming call, do you wish to accept?'}
    # Each line's (first column, first row, last column + 1, last row + 1).
    SNAPSHOT = {'Confirmation': [(266, 147, 535, 172), (290, 181, 509, 208)],
                'Incoming Call': [(273, 145, 526, 172), (306, 181, 492, 208)]}
    SHRUNK = {'Confirmation': ((242, 146, 316, 60), "2 px past the box's foot"),
              'Incoming Call': ((242, 147, 316, 58), "2 px past the box's top, 3 px past the box's foot")}

    def setUp(self):
        _pillow(self)
        from PIL import ImageFont
        from gdl import compose
        self.compose = compose
        self.fnt = ImageFont.truetype(self.LIGHT, size=20 * compose.PT)

    def test_each_lines_ink_ends_where_the_snapshots_does(self):
        for popup, text in self.QUESTIONS.items():
            lines = self.compose.layout(self.BOX, text, self.fnt, 3)
            self.assertEqual(len(lines), 2, popup)
            for (ln, tx, base), want in zip(lines, self.SNAPSHOT[popup]):
                got = self.compose.line_ink(ln, self.fnt, tx, base)
                self.assertEqual(got[1::2], want[1::2], f'{popup} {ln!r}: its rows')
                for g, w in zip(got[::2], want[::2]):
                    self.assertAlmostEqual(g, w, delta=1, msg=f'{popup} {ln!r}: its columns')

    def test_the_descender_is_six_rows_as_gui_designers_is(self):
        """Drawn at PT the 'y' went seven rows below its baseline and put
        ink on the two rows under the box; drawn at the lines' 96 DPI em
        (compose.drawn), six."""
        self.assertAlmostEqual(self.compose.drawn(self.fnt).size, 20 * 4 / 3)
        self.assertEqual(self.compose.line_ink('y', self.fnt, 0, 100)[3], 106)

    def test_in_its_own_box_it_shows_whole(self):
        for popup, text in self.QUESTIONS.items():
            self.assertEqual(self.compose.caption_fit(self.BOX, text, self.fnt, 3), [], popup)

    def test_shrunk_it_loses_the_rows_gui_designer_cut(self):
        for popup, (box, said) in self.SHRUNK.items():
            got = self.compose.caption_fit(box, self.QUESTIONS[popup], self.fnt, 3)
            self.assertEqual([k for k, _ in got], ['clips'], popup)
            self.assertEqual(got[0][1], f'its ink runs {said} in {box[2]}x{box[3]} - GUI Designer cuts it there')

    def test_the_seeds_window_label_loses_its_ds_top_row(self):
        """Turbulence 720's Main Multi-Window 'Window', 12 pt in 92x15 at
        679,2: its snapshot has the 'd' as tall as the 'W', its top row
        above the box cut off."""
        fnt = self.compose.drawn(self.fnt).font_variant(size=12 * self.compose.PT)
        got = self.compose.caption_fit((679, 2, 92, 15), 'Window', fnt, 3)
        self.assertEqual(got, [('clips', "its ink runs 1 px past the box's top in 92x15 - GUI Designer cuts it there")])

    def test_the_seed_holds_them_so(self):
        """The numbers above are the seed's own layout."""
        sys.path.insert(0, os.path.join(ROOT, 'tests'))
        from _corpus import seed, usable
        path = seed('Turbulence 720.gdl')
        if not usable(path):
            self.skipTest(f'{path} is not pulled (git lfs pull)')
        j, _ = self.compose.load(path)
        pages = {p['Name']: p for p in j['Pages'] + j['PopupPages']}
        for popup, name in (('Confirmation', 'Power Down Confirmation'), ('Incoming Call', 'Incoming Call Label')):
            c = next(c for c in pages[popup]['Controls'] if c.get('Name') == name)
            self.assertEqual((c['Left'], c['Top'], c['Width'], c['Height']), self.BOX)
            self.assertEqual((c['Text'], c['Font']['Name'], c['Font']['PointSize'], c['TextAlignment']),
                             (self.QUESTIONS[popup], 'Open Sans Light', 20, 3))
        c = next(c for c in pages['Main Multi-Window']['Controls'] if c.get('Name') == 'Window Label')
        self.assertEqual((c['Left'], c['Top'], c['Width'], c['Height'], c['Text'], c['Font']['PointSize']),
                         (679, 2, 92, 15, 'Window', 12))


class TestABuiltControlsCaptions(unittest.TestCase):
    """compose.built_captions and caption_cuts: a built control's live
    captions, as verify_built and gdl.edit check measure them."""

    FONT = {'Name': 'Open Sans', 'PointSize': 18, 'Style': {'Bold': False, 'Italic': False}}

    def setUp(self):
        _pillow(self)
        from gdl import compose
        self.compose = compose

    def button(self, *states, **c):
        return dict({'__type': 'PBButton:#Extron', 'Name': 'Key', 'Left': 0, 'Top': 0, 'Width': 91,
                     'Height': 37, 'Font': self.FONT, 'TextAlignment': 3,
                     'States': [dict({'Name': n, 'Text': t, 'Font': self.FONT, 'TextAlignment': 3}, **kw)
                                for n, t, kw in states]}, **c)

    def test_each_caption_once_its_states_named_where_their_words_are_their_own(self):
        c = self.button(('Off', 'Volume', {}), ('On', 'Volume', {}), ('Muted', 'Muted', {}))
        self.assertEqual([(s, t) for s, t, _, _ in self.compose.built_captions(c)],
                         [(None, 'Volume'), ('Muted', 'Muted')])

    def test_baked_one_character_and_transparent_words_are_not_live(self):
        """The Zoom Rooms seeds keep space-padded words behind their icons in
        a color with no alpha: GUI Designer draws nothing of them to cut."""
        clear = {'TextColor': {'A': 0, 'R': 0, 'G': 0, 'B': 0}}
        self.assertEqual(self.compose.built_captions(self.button(('Off', 'Volume', {}), FlattenText=True)), [])
        self.assertEqual(self.compose.built_captions(self.button(('Off', 'W', {}))), [])
        self.assertEqual(self.compose.built_captions(self.button(('Off', '   Shades', clear))), [])
        on_control = self.button(('Off', '   Shades', {}), TextColor=clear['TextColor'])
        self.assertEqual(self.compose.built_captions(on_control), [])
        seen = self.button(('Off', '   Shades', {'TextColor': {'A': 255, 'R': 0, 'G': 0, 'B': 0}}),
                           TextColor=clear['TextColor'])
        self.assertEqual(len(self.compose.built_captions(seen)), 1)

    def test_a_mixed_alignment_is_each_states_own(self):
        c = self.button(('Off', 'Volume', {'TextAlignment': 4}), TextAlignment=9)
        self.assertEqual(self.compose.built_captions(c)[0][3], 4)
        self.assertEqual(self.compose.built_captions(self.button(('Off', 'Volume', {'TextAlignment': 9}),
                                                                 TextAlignment=9))[0][3], 3)

    def test_an_edits_words_are_read_in_place_of_a_states(self):
        c = self.button(('Off', 'Vol', {}), ('On', 'Vol', {}))
        self.assertEqual(self.compose.caption_cuts(c)[0], [])
        cuts, _, n = self.compose.caption_cuts(c, {0: 'Volume', 1: 'Volume'})
        self.assertEqual(n, 1)
        self.assertEqual([(s, t, k) for s, t, k, _, _ in cuts], [(None, 'Volume', 'trims')])
        self.assertEqual(cuts[0][4], '18 pt in Open Sans')
        self.assertEqual(self.compose.caption_cuts(c, {0: 'Volume'}, box=[0, 0, 97, 37])[0], [])

    def test_a_face_drawn_here_in_a_stand_in_is_not_measured(self):
        font = dict(self.FONT, Name='No Such Face 9')
        c = self.button(('Off', 'Volume', {'Font': font}), Font=font)
        cuts, unmeasured, n = self.compose.caption_cuts(c)
        self.assertEqual((cuts, n), ([], 0))
        self.assertEqual(len(unmeasured), 1)
        self.assertEqual(unmeasured[0][:2], (None, 'Volume'))
        self.assertIn('No Such Face 9 as', unmeasured[0][2])
        self.assertIn('a stand-in', unmeasured[0][2])


class TestTheOblique(unittest.TestCase):
    """An italic asked of a face with no italic is the regular sheared 0.34
    about its baseline (docs/render-fidelity.md section 9)."""

    def setUp(self):
        _pillow(self)
        from gdl import compose
        self.compose = compose
        if not os.path.exists(os.path.join(compose.FONTDIR, 'opensans-regular.ttf')):
            self.skipTest('gdl/fonts/ is pointed elsewhere')

    def test_the_slant_is_034(self):
        self.assertAlmostEqual(self.compose.OBLIQUE, 0.34)

    def test_an_italic_without_its_file_is_obliqued_and_the_regular_is_not(self):
        px = 40 * self.compose.PT
        self.assertTrue(self.compose.face('Open Sans', 0, 1, px).oblique)
        self.assertFalse(self.compose.face('Open Sans', 0, 0, px).oblique)

    def _stem(self, italic):
        """The slope of an I's stem, row by row: how far right its ink's
        middle moves a pixel up."""
        from PIL import Image
        fnt = self.compose.face('Open Sans', 0, italic, 40 * self.compose.PT)
        img = Image.new('RGBA', (200, 100), (0, 0, 0, 0))
        self.compose.draw_text(img, (0, 0, 200, 100), 'I', fnt, (255, 255, 255, 255), 3)
        a = img.getchannel('A')
        rows = []
        for y in range(a.height):
            row = [a.getpixel((x, y)) for x in range(a.width)]
            if sum(row) > 255 * 3:
                rows.append((y, sum(x * v for x, v in enumerate(row)) / sum(row)))
        rows = rows[3:-3]
        n = len(rows)
        my, mx = sum(r[0] for r in rows) / n, sum(r[1] for r in rows) / n
        return -sum((y - my) * (x - mx) for y, x in rows) / sum((y - my) ** 2 for y, _ in rows)

    def test_an_obliqued_stem_leans_034_and_an_upright_one_none(self):
        self.assertAlmostEqual(self._stem(1), 0.34, delta=0.02)
        self.assertAlmostEqual(self._stem(0), 0.0, delta=0.02)

    def test_the_baseline_does_not_move(self):
        """Sheared about the baseline: the stem's foot stays where the
        upright one's is."""
        from PIL import Image
        feet = []
        for italic in (0, 1):
            fnt = self.compose.face('Open Sans', 0, italic, 40 * self.compose.PT)
            img = Image.new('RGBA', (200, 100), (0, 0, 0, 0))
            self.compose.draw_text(img, (0, 0, 200, 100), 'I', fnt, (255, 255, 255, 255), 3)
            a = img.getchannel('A')
            bottom = a.getbbox()[3] - 2
            row = [a.getpixel((x, bottom)) for x in range(a.width)]
            feet.append(sum(x * v for x, v in enumerate(row)) / sum(row))
        self.assertAlmostEqual(feet[0], feet[1], delta=1)


class TestTheBold(unittest.TestCase):
    """A bold asked of a face with no bold file is the regular emboldened, as
    GDI+ does it: each glyph's ink smeared a whole pixel to the right, and each
    advance 1/60 em longer (docs/render-fidelity.md section 8)."""

    def setUp(self):
        _pillow(self)
        from gdl import compose
        self.compose = compose
        if not os.path.exists(os.path.join(compose.FONTDIR, 'opensans-regular.ttf')):
            self.skipTest('gdl/fonts/ is pointed elsewhere')
        self.px = 40 * compose.PT
        self.bold = compose.face('Open Sans', 1, 0, self.px)
        self.regular = compose.face('Open Sans', 0, 0, self.px)

    def _alpha(self, text, fnt, size=(1400, 100)):
        """`text` drawn left-aligned, so its first glyph starts where the
        regular's does: the alpha it leaves."""
        from PIL import Image
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        self.compose.draw_text(img, (0, 0) + size, text, fnt, (255, 255, 255, 255), 4)
        return img.getchannel('A')

    def test_the_model_is_a_pixel_and_a_sixtieth_of_an_em(self):
        self.assertEqual(self.compose.BOLD_SMEAR, 1)
        self.assertAlmostEqual(self.compose.BOLD_ADVANCE_EM, 1 / 60)

    def test_a_bold_without_its_file_is_emboldened_and_the_regular_is_not(self):
        self.assertTrue(self.bold.emboldened)
        self.assertFalse(self.regular.emboldened)
        both = self.compose.face('Open Sans', 1, 1, self.px)
        self.assertTrue(both.emboldened and both.oblique)

    def test_a_bold_file_is_drawn_as_it_is(self):
        """A face whose file is its bold is not emboldened again."""
        from unittest import mock
        from PIL import ImageFont
        f = ImageFont.truetype(OPEN_SANS, size=10)
        f.getname = lambda: ('Open Sans', 'Bold')
        with mock.patch.object(self.compose, '_open_face', return_value=(f, None)), \
                mock.patch.dict(self.compose._cache, clear=True):
            self.assertFalse(self.compose.face('Open Sans', 1, 0, 10).emboldened)

    def test_each_advance_is_a_sixtieth_of_an_em_longer(self):
        text = 'Program Level'
        grown = self.compose.measure(text, self.bold) - self.compose.measure(text, self.regular)
        self.assertAlmostEqual(grown, len(text) * self.px / 60, places=6)

    def test_a_glyphs_ink_is_the_regulars_smeared_a_pixel_right(self):
        """One glyph, so no advance moves it: the bold's coverage is the
        regular's or the regular's a pixel to its left, whichever is more."""
        from PIL import Image, ImageChops
        reg = self._alpha('O', self.regular)
        right = Image.new('L', reg.size, 0)
        right.paste(reg.crop((0, 0, reg.width - 1, reg.height)), (1, 0))
        self.assertEqual(self._alpha('O', self.bold).tobytes(),
                         ImageChops.lighter(reg, right).tobytes())

    def test_each_glyph_lands_a_sixtieth_of_an_em_further_along(self):
        """Forty stems: the last one's ink ends 39/60 em further right than
        the regular's, and the smear's pixel past that."""
        text = 'l' * 40
        reg, bold = self._alpha(text, self.regular), self._alpha(text, self.bold)
        self.assertEqual(bold.getbbox()[0], reg.getbbox()[0])
        self.assertAlmostEqual(bold.getbbox()[2] - reg.getbbox()[2], 39 * self.px / 60 + 1, delta=1)

    def test_a_bold_line_wraps_on_its_emboldened_width(self):
        """A caption that fits its box in the regular but not grown by 1/60
        em a glyph takes two lines bold."""
        text = 'Conference Room'
        w = self.compose.measure(text, self.regular) + 2 * self.compose.PAD_EM * self.px + 2
        box = (int(w), 300)
        reg, bold = self._alpha(text, self.regular, box), self._alpha(text, self.bold, box)
        self.assertGreater(bold.getbbox()[3] - bold.getbbox()[1],
                           1.5 * (reg.getbbox()[3] - reg.getbbox()[1]))


class TestTheLinesDown(unittest.TestCase):
    """GDI+ lays a caption out down its box at 96 DPI where it lays it out
    across at 99: the ascent and the line pitch are the face's at 4/3 px a
    point, not PT; and a centred or bottom-aligned block is aligned in its box
    less 0.2 px a point at its foot (docs/render-fidelity.md finding 7)."""

    def setUp(self):
        _pillow(self)
        from PIL import ImageFont
        from gdl import compose
        self.compose = compose
        self.pt = 40
        self.fnt = ImageFont.truetype(OPEN_SANS, size=self.pt * compose.PT)

    def _rows(self, text, align, box=(0, 0, 600, 400)):
        """The rows each line's ink covers, top to bottom: [(first, last)]."""
        from PIL import Image
        img = Image.new('RGBA', (box[2], box[3]), (0, 0, 0, 0))
        self.compose.draw_text(img, box, text, self.fnt, (255, 255, 255, 255), align)
        a = img.getchannel('A')
        inked = [any(a.getpixel((x, y)) for x in range(a.width)) for y in range(a.height)]
        runs, start = [], None
        for y, on in enumerate(inked + [False]):
            if on and start is None:
                start = y
            elif not on and start is not None:
                runs.append((start, y - 1))
                start = None
        return runs

    def test_the_vertical_metrics_are_at_96_dpi(self):
        self.assertAlmostEqual(self.compose.VERTICAL, (4 / 3) / self.compose.PT)
        self.assertAlmostEqual(self.compose.FOOT, 0.2)
        asc, desc = self.compose.metrics(self.fnt)
        got = self.compose.layout_metrics(self.fnt)
        self.assertAlmostEqual(got[0], asc * (4 / 3) / self.compose.PT)
        self.assertAlmostEqual(got[1], desc * (4 / 3) / self.compose.PT)

    def test_lines_are_set_the_pitch_at_four_thirds_apart(self):
        """'H' on three lines, top-aligned: each the face's winAscent +
        winDescent at 4/3 px a point below the last - 72.6 px at 40 pt, where
        at PT it would be 74.9."""
        rows = self._rows('H\nH\nH', 7)
        pitch = (rows[2][1] - rows[0][1]) / 2
        a = self.compose.advances(self.fnt)
        want = (a.win_ascent + a.win_descent) / a.upem * self.pt * 4 / 3
        self.assertAlmostEqual(pitch, want, delta=0.6)

    def test_a_top_aligned_baseline_is_the_ascent_at_four_thirds_down(self):
        a = self.compose.advances(self.fnt)
        foot = self._rows('H', 7)[0][1] + 1
        self.assertAlmostEqual(foot, a.win_ascent / a.upem * self.pt * 4 / 3, delta=1)

    def test_a_centred_block_sits_half_the_foot_higher_and_a_bottom_one_all_of_it(self):
        """Against the same block laid out with no foot: a top-aligned one
        does not move, a centred one rises 0.1 px a point, a bottom one 0.2."""
        was = self.compose.FOOT
        try:
            self.compose.FOOT = 0
            plain = {v: self._rows('H', v)[0][1] for v in (1, 4, 7)}
        finally:
            self.compose.FOOT = was
        got = {v: self._rows('H', v)[0][1] for v in (1, 4, 7)}
        self.assertEqual(got[7], plain[7])
        self.assertAlmostEqual(plain[4] - got[4], 0.1 * self.pt, delta=1)
        self.assertAlmostEqual(plain[1] - got[1], 0.2 * self.pt, delta=1)

    def test_each_line_is_drawn_on_the_baseline_layout_gives_it(self):
        """compose.layout is where draw_text sets each line, which
        research/synthetic_lines.py measures against the snapshots."""
        box = (0, 0, 600, 400)
        for align in (1, 3, 4, 7):
            lines = self.compose.layout(box, 'H\nH\nH', self.fnt, align)
            self.assertEqual([ln for ln, _, _ in lines], ['H', 'H', 'H'])
            feet = [last + 1 for _, last in self._rows('H\nH\nH', align, box)]
            for (_, _, base), foot in zip(lines, feet):
                self.assertAlmostEqual(foot, base, delta=1)


class TestTheSnapshotsBlend(unittest.TestCase):
    """GUI Designer's snapshot blends a translucent pixel over opaque art in
    light - GDI+'s gamma-corrected source-over at 2.2 - and writes one over
    nothing as it is (docs/render-fidelity.md finding 2)."""

    PAGE = (36, 38, 52, 255)        # Afterburn's page, under the Controls page's art

    def setUp(self):
        _pillow(self)
        from gdl import compose
        self.compose = compose

    def _over(self, pixel, under):
        from PIL import Image
        canvas = Image.new('RGBA', (3, 3), under)
        self.compose.snapshot_over(canvas, Image.new('RGBA', (3, 3), pixel), 0, 0)
        return canvas.getpixel((1, 1))

    def assertNear(self, got, want, delta):
        for g, w in zip(got, want):
            self.assertAlmostEqual(g, w, delta=delta, msg=f'{got} is not {want}')

    def test_white_at_20_percent_is_lighter_than_a_plain_blend(self):
        """The synthetic fixture's PanelClear, #33FFFFFF over the page: the
        snapshot reads (126, 126, 130), a plain blend would be (80, 81, 93)."""
        self.assertNear(self._over((255, 255, 255, 51), self.PAGE), (126, 126, 130, 255), 1)

    def test_an_antialiased_edge_blends_at_its_own_alpha(self):
        """The fixture's Rule line: its half-covered row, alpha 128, reads
        (157, 114, 78) in the snapshot, not the solid (213, 155, 97) a binary
        write gives."""
        self.assertNear(self._over((213, 155, 97, 128), self.PAGE), (157, 114, 78, 255), 2)

    def test_an_opaque_pixel_is_written_as_it_is(self):
        self.assertEqual(self._over((213, 155, 97, 255), self.PAGE), (213, 155, 97, 255))

    def test_a_clear_pixel_leaves_what_is_under_it(self):
        self.assertEqual(self._over((255, 255, 255, 0), self.PAGE), self.PAGE)

    def test_over_nothing_a_pixel_is_written_as_it_is(self):
        """Its color undiluted and its alpha with it, for flatten() to put on
        black at full strength - finding 4's bilevel rule."""
        self.assertEqual(self._over((255, 255, 255, 51), (0, 0, 0, 0)), (255, 255, 255, 51))

    def test_paste_keeps_the_snapshots_rule_and_the_panels(self):
        """paste() blends in light by default; with BINARY off, as Pillow
        does, for the picture of the panel."""
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGBA', (3, 3), (255, 255, 255, 51)).save(buf, 'PNG')

        def pasted(rule):
            c = Image.new('RGBA', (3, 3), self.PAGE)
            was, self.compose.BINARY = self.compose.BINARY, rule
            try:
                self.compose.paste(c, {1: buf.getvalue()}, 1, 0, 0)
            finally:
                self.compose.BINARY = was
            return c.getpixel((1, 1))
        self.assertNear(pasted(True), (126, 126, 130, 255), 1)
        self.assertNear(pasted(False), (80, 81, 93, 255), 1)

    def test_a_translucent_fill_without_art_blends_too(self):
        """draw_fill, for a control Build never rasterized, under the same
        rule."""
        from PIL import Image
        c = Image.new('RGBA', (10, 10), self.PAGE)
        self.compose.draw_fill(c, (0, 0, 10, 10), {'fill': {'R': 255, 'G': 255, 'B': 255, 'A': 51}})
        self.assertNear(c.getpixel((5, 5)), (126, 126, 130, 255), 1)


if __name__ == '__main__':
    unittest.main()
