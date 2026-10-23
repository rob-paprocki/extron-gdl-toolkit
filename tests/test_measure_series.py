"""What tests/measure_series.py reads off a theme's series: which seeds serve
its models - read off each seed's own build, never its name - and where its
regions are when no art draws them, read off the template's own controls."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import measure_series  # noqa: E402
from gdl import templates  # noqa: E402

REPO = os.path.dirname(HERE)


def _facts(part, size):
    return {'part': part, 'size': list(size), 'slider': True, 'level': True, 'datetime': True, 'popup': True,
            'borders': {}}


class TestASeriesSeeds(unittest.TestCase):
    SEEDS = {'seeds/Afterburn 1035.gdl': _facts('60-1999-02', (1280, 800)),
             'seeds/Afterburn 1035 Portrait.gdl': _facts('60-1999-02', (800, 1280)),
             'seeds/Afterburn 300M Landscape.gdl': _facts('60-1667-02', (480, 320))}

    def setUp(self):
        if not templates.table():
            self.skipTest("Extron's template table is not here (vendor/README.md)")

    def test_a_turned_seed_is_its_panels_where_no_template_is_drawn_that_way(self):
        """The 1035M portrait has no template; its seed is its own turned, and
        the series that draws the 1035M serves it under the panel's name."""
        got, _, _ = measure_series.match_seeds('Afterburn', ['TLP1035M', 'TLP1035T', 'TLP835M'],
                                               (1280, 800), self.SEEDS)
        self.assertEqual(got, {'TLP1035M': 'seeds/Afterburn 1035.gdl',
                               'TLP1035T': 'seeds/Afterburn 1035.gdl',
                               'TLP1035M-Portrait': 'seeds/Afterburn 1035 Portrait.gdl'})

    def test_a_seed_another_series_draws_is_not_a_turned_one(self):
        """The 300M's landscape seed is the 300 Landscape series', not the
        Portrait series' turned: Extron draws a template that way."""
        got, _, _ = measure_series.match_seeds('Afterburn', ['TLP300M'], (320, 480), self.SEEDS)
        self.assertEqual(got, {})


# -- regions from controls: pages as gdl.project.Project.pages() yields them --------
DARK = {'A': 180, 'R': 0, 'G': 0, 'B': 0}


def _c(kind, x, y, w, h, fill=None):
    return {'type': kind, 'name': '', 'rect': (x, y, w, h), 'fill': fill}


def _page(name, *controls, size=(1280, 800), kind='page', modal=False):
    return {'kind': kind, 'name': name, 'modal': modal, 'size': size, 'controls': list(controls)}


def _regions(pages, size=(1280, 800)):
    r = measure_series.control_regions(pages, size)
    return r['main'], r['rail'], r['rail_axis']


def _mach(left_cap=140, right_cap=140, footer=True):
    """A Mach main page: a header bar and a footer whose end buttons are as
    wide as the side bands, a settings column and a volume column inside them,
    the full-canvas references Build adds and the standard popup's."""
    cs = [_c('PBShape', 0, 0, 1280, 64, DARK),
          _c('PBButton', 17, 308, 103, 60), _c('PBButton', 17, 438, 103, 60),
          _c('PBSlider', 1198, 178, 30, 363), _c('PBButton', 1161, 560, 103, 60),
          _c('PBPopupPageReference', 0, 0, 1280, 800),
          _c('PBPopupPageReference', 142, 125, 995, 549)]
    if footer:
        cs += [_c('PBButton', 0, 745, left_cap, 55), _c('PBShape', left_cap, 745, 1280 - left_cap - right_cap, 55, DARK),
               _c('PBButton', 1280 - right_cap, 745, right_cap, 55)]
    return cs


class TestRegionsFromControls(unittest.TestCase):
    """Mach, Shockwave and Turbulence draw their bars, wells and rails as
    controls over photographs, so the regions are read off the template's Main*
    pages: one rule, every theme. Each case is a theme's own structure."""

    def test_bars_and_their_end_caps_frame_main(self):
        """Mach: main lies between the header and footer and between the
        footer's end buttons; the standard popup's window, at 80% of that, is
        not main; the full-canvas reference is no window at all."""
        main, rail, axis = _regions([_page('Main Multi-Window', *_mach())])
        self.assertEqual(main, [140, 64, 1000, 681])
        self.assertEqual((rail, axis), ([1140, 64, 140, 681], 'column'))

    def test_a_well_is_main_and_a_floating_footer_ends_the_rail(self):
        """Shockwave: a shape inside the canvas covering a quarter of it is
        main; the footer capsule stands off the bottom edge, and the rail runs
        from the header to it."""
        page = _page('Main', _c('PBShape', 0, 0, 1280, 91, DARK), _c('PBShape', 40, 718, 1200, 60, DARK),
                     _c('PBButton', 1100, 725, 120, 45), _c('PBShape', 168, 120, 926, 574, DARK),
                     _c('PBSlider', 1150, 150, 40, 315), _c('PBPopupPageReference', 170, 122, 921, 574))
        main, rail, axis = _regions([page])
        self.assertEqual(main, [168, 120, 926, 574])
        self.assertEqual((rail, axis), ([1094, 91, 186, 627], 'column'))

    def test_side_bars_and_a_window_that_fills_the_free_canvas(self):
        """Turbulence: tall bars on both sides; its standard popup's window -
        the largest of the page's references - covers most of what the bars
        leave, so it is main, and the rail starts at the right bar."""
        page = _page('Main', _c('PBShape', 0, 100, 112, 500, DARK), _c('PBShape', 1138, 130, 142, 666, DARK),
                     _c('PBShape', 0, 0, 1280, 133, DARK), _c('PBShape', 0, 700, 1280, 100, DARK),
                     _c('PBPopupPageReference', 500, 300, 100, 100),
                     _c('PBPopupPageReference', 140, 137, 995, 549))
        main, rail, axis = _regions([page])
        self.assertEqual(main, [140, 137, 995, 549])
        self.assertEqual((rail, axis), ([1138, 133, 142, 567], 'column'))

    def test_a_bar_between_side_bars_spans_what_they_leave(self):
        """A header and footer that run only between the side bars are bars:
        their coverage is of the span the side bars leave."""
        page = _page('Main', _c('PBShape', 0, 0, 112, 800, DARK), _c('PBShape', 1168, 0, 112, 800, DARK),
                     _c('PBShape', 112, 0, 1056, 90, DARK), _c('PBShape', 112, 710, 1056, 90, DARK))
        main, rail, axis = _regions([page])
        self.assertEqual(main, [112, 90, 1056, 620])
        # Neither bar crosses the rail, so it runs the canvas's height.
        self.assertEqual((rail, axis), ([1168, 0, 112, 800], 'column'))

    def test_a_header_that_stops_short_of_the_rail_leaves_it_running_to_the_top(self):
        page = _page('Main', *(c for c in _mach() if c['rect'] != (0, 0, 1280, 64)),
                     _c('PBShape', 0, 0, 1160, 64, DARK))
        main, rail, axis = _regions([page])
        self.assertEqual(main, [140, 64, 1000, 681])
        self.assertEqual((rail, axis), ([1140, 0, 140, 745], 'column'))

    def test_a_column_standing_off_the_edge_is_centred_in_its_band(self):
        """Its margin from the edge is mirrored on its inner side."""
        page = _page('Main', _c('PBButton', 10, 200, 100, 60), _c('PBButton', 10, 300, 100, 60))
        main, rail, axis = _regions([page])
        self.assertEqual(main, [120, 0, 1160, 800])
        self.assertEqual((rail, axis), (None, None))

    def test_a_title_strip_under_its_own_popup_is_main(self):
        """The 520 hubs: Extron places the standard popup over the title strip,
        so the strip is main, not chrome."""
        page = _page('Main', _c('PBShape', 700, 0, 100, 480, DARK), _c('PBLabel', 0, 0, 700, 72, DARK),
                     _c('PBPopupPageReference', 0, 0, 702, 480), size=(800, 480))
        main, rail, axis = _regions([page], (800, 480))
        self.assertEqual(main, [0, 0, 700, 480])
        self.assertEqual((rail, axis), ([700, 0, 100, 480], 'column'))

    def test_a_footer_bar_is_a_row_rail_where_nothing_stands_beside_main(self):
        """The 300 portrait."""
        page = _page('Main', _c('PBShape', 0, 400, 320, 80, DARK), _c('PBButton', 8, 404, 96, 72),
                     _c('PBButton', 112, 404, 96, 72), _c('PBButton', 216, 404, 96, 72),
                     _c('PBButton', 40, 75, 240, 70), size=(320, 480))
        main, rail, axis = _regions([page], (320, 480))
        self.assertEqual(main, [0, 0, 320, 400])
        self.assertEqual((rail, axis), ([0, 400, 320, 80], 'row'))

    def test_a_row_of_buttons_near_the_bottom_is_one_too(self):
        """Afterburn's 320: no bar, a row hugging the bottom - its band is the
        row with its own margin mirrored above it."""
        page = _page('Main', _c('PBButton', 10, 195, 90, 40), _c('PBButton', 115, 195, 90, 40),
                     _c('PBButton', 220, 195, 90, 40), size=(320, 240))
        main, rail, axis = _regions([page], (320, 240))
        self.assertEqual(main, [0, 0, 320, 190])
        self.assertEqual((rail, axis), ([0, 190, 320, 50], 'row'))

    def test_a_header_alone_leaves_no_rail(self):
        """The 320s of Mach, Shockwave and Turbulence: a filled title label and
        nothing persistent - volume is a popup no page opens."""
        page = _page('Main', _c('PBLabel', 0, 0, 320, 36, DARK), _c('PBLabel', 0, 104, 320, 29), size=(320, 240))
        main, rail, axis = _regions([page], (320, 240))
        self.assertEqual(main, [0, 36, 320, 204])
        self.assertEqual((rail, axis), (None, None))

    def test_columns_flush_with_the_edges_bound_main(self):
        """Afterburn's columns, read without its art: list buttons flush left,
        a volume label 3 px off the right."""
        page = _page('Main', _c('PBButton', 0, 100, 178, 60), _c('PBButton', 0, 170, 178, 60),
                     _c('PBLabel', 1109, 3, 168, 30))
        main, rail, axis = _regions([page])
        self.assertEqual(main, [178, 0, 931, 800])
        self.assertEqual((rail, axis), ([1109, 0, 171, 800], 'column'))

    def test_across_pages_the_most_common_wins(self):
        """Not the first page's, nor the one with the most chrome: Mach's pages
        differ by a few pixels, and one has caps of its own. A page with no
        footer counts as one that ends at the canvas."""
        pages = [_page('Main A', *_mach(left_cap=300, right_cap=300)), _page('Main B', *_mach()),
                 _page('Main C', *_mach()), _page('Main D', *_mach(footer=False))]
        main, _, _ = _regions(pages)
        self.assertEqual(main, [140, 64, 1000, 681])

    def test_a_tie_goes_to_more_chrome(self):
        """Whichever page comes first: Mach's Multi-Window page has narrower
        caps than its others."""
        tied = [_page('Main A', *_mach(left_cap=67, right_cap=94)), _page('Main B', *_mach())]
        main, rail, _ = _regions(tied)
        self.assertEqual(main, [140, 64, 1000, 681])
        self.assertEqual(rail[0], 1140)

    def test_only_main_pages_are_read_when_there_are_any(self):
        pages = [_page('Main', *_mach()), _page('Lighting', *_mach(left_cap=300, right_cap=300)),
                 _page('Volume', *_mach(left_cap=300), kind='popup')]
        main, _, _ = _regions(pages)
        self.assertEqual(main, [140, 64, 1000, 681])


class TestRegionsBesideTheArt(unittest.TestCase):
    """Afterburn's main region is its art's; the rail is what the canvas leaves
    beside it, and the controls are not read."""

    def test_the_art_wins_where_there_is_some(self):
        got = measure_series.regions([_page('Main', *_mach())], (1280, 800), art=[183, 24, 916, 752])
        self.assertEqual(got, {'main': [183, 24, 916, 752], 'rail': [1099, 0, 181, 800], 'rail_axis': 'column'})

    def test_without_art_the_controls_say(self):
        got = measure_series.regions([_page('Main', *_mach())], (1280, 800))
        self.assertEqual(got, {'main': [140, 64, 1000, 681], 'rail': [1140, 64, 140, 681], 'rail_axis': 'column'})

    def test_art_the_width_of_the_canvas_has_its_rail_below(self):
        """Afterburn's 320: the art's body runs across, the rail under it."""
        got = measure_series.regions([], (320, 240), art=[0, 0, 320, 190])
        self.assertEqual((got['rail'], got['rail_axis']), ([0, 190, 320, 50], 'row'))
        got = measure_series.regions([], (320, 240), art=[0, 0, 320, 240])
        self.assertEqual((got['rail'], got['rail_axis']), (None, None))

    def test_a_photograph_opaque_everywhere_draws_no_main_region(self):
        """Mach's, Shockwave's and Turbulence's art is photographs with alpha
        255 throughout: their body is the whole picture, which says nothing
        of where the page's content goes - the controls do."""
        self.assertIsNone(measure_series.art_main((0, 0, 5472, 3648), (5472, 3648), (1280, 800), 'stretch'))
        self.assertIsNone(measure_series.art_main(None, (5472, 3648), (1280, 800), 'stretch'))
        self.assertEqual(measure_series.art_main((100, 50, 800, 500), (1000, 600), (1000, 600), 'stretch'),
                         [100, 50, 700, 450])


class TestThePopupRegion(unittest.TestCase):
    def test_the_largest_named_standard_popup_where_it_fills_a_quarter(self):
        pages = [_page('Big', kind='popup', size=(900, 500)), _page('Modal', kind='popup', modal=True),
                 _page('Small', kind='popup', size=(300, 200)), _page('', kind='popup', size=(1000, 600))]
        self.assertEqual(measure_series.popup_region(pages, (1280, 800)), [900, 500])
        self.assertIsNone(measure_series.popup_region(pages[1:3], (1280, 800)))


def _themes(*pairs):
    return {'themes': [{'id': i, 'image': os.path.basename(f), 'file': f} for i, f in pairs]}


MACH_KIT = [f'Mach/Backgrounds/{s}/{s}_mach-bg-0{n}.png' for s in ('320x480', '5472x3648') for n in (1, 2)]
MACH = _themes(('sunset', 'Mach/Backgrounds/5472x3648/5472x3648_mach-bg-02.png'),
               ('dome', 'Mach/Backgrounds/5472x3648/5472x3648_mach-bg-01.png'))
SHOCKWAVE_KIT = ['Shockwave/backgrounds/1024x600_bkgd.png', 'Shockwave/backgrounds/1024x600_start_bkgd.png',
                 'Shockwave/backgrounds/1280x800 bkgd.png', 'Shockwave/backgrounds/1280x800_start_bkgd.png',
                 'Shockwave/backgrounds/1366x768 bkgd.png', 'Shockwave/backgrounds/800x480 bkgd.png',
                 'Shockwave/backgrounds/5464x3072_bkgd.png', 'Shockwave/backgrounds/5464x3072_Saturn.png',
                 'Shockwave/Slider/156x1026_sw_track_bg.png']
SHOCKWAVE = _themes(('haze', 'Shockwave/backgrounds/1280x800 bkgd.png'),
                    ('saturn', 'Shockwave/backgrounds/5464x3072_Saturn.png'))
TURBULENCE_KIT = ['Turbulence/bkgd_pc.png', 'Turbulence/bkgd_home_plain.png', 'Turbulence/bkgd_start.png']
TURBULENCE = _themes(('corridor', 'Turbulence/bkgd_pc.png'), ('bokeh', 'Turbulence/bkgd_home_plain.png'))


class TestBackgroundsByTheme(unittest.TestCase):
    """Where no kit art draws a series' regions, each of the profile's themes
    still has a background on it: the kit's file of the template's own art
    where the kit has it, else of the theme's art at the series' size, else at
    the nearest shape. The applier reuses a seed's image only where name and
    pixels agree and otherwise appends the file, so the template's own name is
    kept only for the file that is its art pixel for pixel - `own`, which
    measure() finds - and any other file goes by its kit name."""

    def test_the_art_at_the_series_size_named_as_its_template_names_it(self):
        """The Mach 300 draws its own 320x480 photographs, the default named
        with underscores."""
        got = measure_series.theme_backgrounds(MACH, (320, 480), 'mach_bg_02.png', MACH_KIT,
                                               own={'Mach/Backgrounds/320x480/320x480_mach-bg-02.png'})
        self.assertEqual(got, {
            'sunset': {'image': 'mach_bg_02.png', 'file': 'Mach/Backgrounds/320x480/320x480_mach-bg-02.png'},
            'dome': {'image': '320x480_mach-bg-01.png', 'file': 'Mach/Backgrounds/320x480/320x480_mach-bg-01.png'}})

    def test_else_the_art_of_the_nearest_shape(self):
        """Every other Mach series stretches the 3:2 photographs."""
        got = measure_series.theme_backgrounds(MACH, (1280, 800), 'mach-bg-02.png', MACH_KIT,
                                               own={'Mach/Backgrounds/5472x3648/5472x3648_mach-bg-02.png'})
        self.assertEqual(got, {
            'sunset': {'image': 'mach-bg-02.png', 'file': 'Mach/Backgrounds/5472x3648/5472x3648_mach-bg-02.png'},
            'dome': {'image': '5472x3648_mach-bg-01.png',
                     'file': 'Mach/Backgrounds/5472x3648/5472x3648_mach-bg-01.png'}})

    def test_the_templates_own_art_before_the_series_shape(self):
        """The Shockwave 535 is 1280x720 and stretches the 800x480 haze its
        template draws, which the kit has: that file, under that name, which
        the seed carries - not the 13.9 MB 5464x3072 of the 535's own shape,
        which the applier would append beside it."""
        got = measure_series.theme_backgrounds(SHOCKWAVE, (1280, 720), '800x480 bkgd.png', SHOCKWAVE_KIT,
                                               own={'Shockwave/backgrounds/800x480 bkgd.png'})
        self.assertEqual(got['haze'], {'image': '800x480 bkgd.png', 'file': 'Shockwave/backgrounds/800x480 bkgd.png'})

    def test_the_series_own_size_before_a_larger_file_its_shape(self):
        """1366x768 and 5464x3072 are one shape; the 1520's 1366x768 takes its
        own size, not the larger."""
        got = measure_series.theme_backgrounds(SHOCKWAVE, (1366, 768), 'SW_bkgd_01.png', SHOCKWAVE_KIT)
        self.assertEqual(got['haze']['file'], 'Shockwave/backgrounds/1366x768 bkgd.png')

    def test_a_template_naming_its_art_otherwise_takes_the_kit_files(self):
        """Shockwave's tier A templates name their art SW_bkgd_01.png, which is
        no kit file's name; the start-page art is another theme's, not this."""
        got = measure_series.theme_backgrounds(SHOCKWAVE, (1024, 600), 'SW_bkgd_01.png', SHOCKWAVE_KIT)
        self.assertEqual(got, {
            'haze': {'image': '1024x600_bkgd.png', 'file': 'Shockwave/backgrounds/1024x600_bkgd.png'},
            'saturn': {'image': '5464x3072_Saturn.png', 'file': 'Shockwave/backgrounds/5464x3072_Saturn.png'}})

    def test_of_two_files_the_same_shape_the_larger(self):
        """1366x768 and 5464x3072 are both 683:384; the 1720's 1920x1080 takes
        the one with the pixels to fill it."""
        got = measure_series.theme_backgrounds(SHOCKWAVE, (1920, 1080), 'SW_bkgd_01.png', SHOCKWAVE_KIT)
        self.assertEqual(got['haze']['file'], 'Shockwave/backgrounds/5464x3072_bkgd.png')

    def test_art_the_kit_lacks_is_the_nearest_under_its_own_name(self):
        """The Shockwave 320 draws a 320x240 haze the kit does not have. The
        1280x800 is the nearest, and it is what builds - the applier appends
        it - so it goes by its own name, not the 320x240's its seed would carry."""
        got = measure_series.theme_backgrounds(SHOCKWAVE, (320, 240), '320x240 bkgd.png', SHOCKWAVE_KIT)
        self.assertEqual(got['haze'], {'image': '1280x800 bkgd.png', 'file': 'Shockwave/backgrounds/1280x800 bkgd.png'})

    def test_art_of_one_size(self):
        """Turbulence's art comes out of its templates at one size each."""
        got = measure_series.theme_backgrounds(TURBULENCE, (1024, 600), 'bkgd_pc.png', TURBULENCE_KIT,
                                               own={'Turbulence/bkgd_pc.png'})
        self.assertEqual(got, {
            'corridor': {'image': 'bkgd_pc.png', 'file': 'Turbulence/bkgd_pc.png'},
            'bokeh': {'image': 'bkgd_home_plain.png', 'file': 'Turbulence/bkgd_home_plain.png'}})

    def test_a_theme_the_kit_has_no_art_for_has_none(self):
        """A kit with the dome's photograph alone: the sunset has no background."""
        kit = [k for k in MACH_KIT if 'bg-01' in k]
        got = measure_series.theme_backgrounds(MACH, (1280, 800), 'mach-bg-02.png', kit)
        self.assertEqual(sorted(got), ['dome'])


class TestTheTemplatesOwnArt(unittest.TestCase):
    """The kit files that are a template's art pixel for pixel - the only ones
    theme_backgrounds may name as the template names its art, since the
    applier reuses a seed's image only where the pixels agree."""

    def setUp(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('needs Pillow')
        self.Image = Image
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def _png(self, im, name=None, **kw):
        buf = io.BytesIO()
        im.save(buf, 'PNG', **kw)
        if name is None:
            return buf.getvalue()
        path = os.path.join(self.dir, name)
        with open(path, 'wb') as fh:
            fh.write(buf.getvalue())
        return path

    def test_the_same_pixels_however_the_file_is_written(self):
        art = self.Image.new('RGBA', (4, 3), (200, 40, 40, 255))
        art.putpixel((1, 1), (0, 0, 0, 128))
        other = art.copy()
        other.putpixel((2, 2), (0, 0, 1, 255))
        files = {'Kit/same.png': self._png(art, 'same.png', compress_level=0),
                 'Kit/other.png': self._png(other, 'other.png'),
                 'Kit/gone.png': None}
        self.assertEqual(measure_series.own_art(self._png(art, compress_level=9), files), {'Kit/same.png'})

    def test_a_file_of_another_size_is_not_decoded(self):
        """Only its header is read: a torn file of another size is no error."""
        big = self._png(self.Image.new('RGBA', (8, 3), 'red'))
        torn = os.path.join(self.dir, 'torn.png')
        with open(torn, 'wb') as fh:
            fh.write(big[:40])
        art = self._png(self.Image.new('RGBA', (4, 3), 'red'))
        self.assertEqual(measure_series.own_art(art, {'Kit/torn.png': torn}), set())

    def test_shockwaves_535_draws_the_kits_800x480_and_its_320_art_the_kit_lacks(self):
        if not templates.table():
            self.skipTest("Extron's template table is not here (vendor/README.md)")
        from gdl import spec
        from gdl.project import Project
        kit = measure_series.kit_pngs('Shockwave')
        if not kit:
            self.skipTest("Shockwave's kit is not here")
        files = {k: spec.resolve_image(k) for k in kit}
        for series, want in (('Shockwave 535 Series', {'Shockwave/backgrounds/800x480 bkgd.png'}),
                             ('Shockwave 320 Series', set())):
            with self.subTest(series=series):
                row = next(r for r in templates.series('Shockwave') if r['series'] == series)
                p = Project.open(templates.path_of(row))
                resource, _ = measure_series.main_page(p, [pg for pg in p.pages() if pg['name']])
                self.assertEqual(measure_series.own_art(measure_series.template_art(p, resource), files), want)


class TestRegionsOfExtronsOwnTemplates(unittest.TestCase):
    """The rule on Mach's, Shockwave's and Turbulence's 1220 Series: the 1280x800
    main region and popup each profile's design panel already draws, the rail
    beside it - between Mach's bars, from Shockwave's header to its capsule, at
    Turbulence's right bar - and each 1035 seed, a built clone of its template,
    the same."""
    RAILS = {'Mach': [1140, 64, 140, 681], 'Shockwave': [1094, 91, 186, 627], 'Turbulence': [1138, 133, 142, 667]}

    def setUp(self):
        if not templates.table():
            self.skipTest("Extron's template table is not here (vendor/README.md)")

    def _measure(self, path, size):
        from gdl.project import Project
        pages = [pg for pg in Project.open(path).pages() if pg['name']]
        return measure_series.control_regions(pages, size), measure_series.popup_region(pages, size)

    def test_each_profiles_design_panel(self):
        for theme in ('Mach', 'Shockwave', 'Turbulence'):
            with self.subTest(theme=theme):
                row = next(r for r in templates.series(theme) if r['series'] == f'{theme} 1220 Series')
                got, popup = self._measure(templates.path_of(row), tuple(row['size']))
                with open(os.path.join(REPO, 'gdl', 'designsys', theme.lower() + '.json'), encoding='utf-8') as fh:
                    prof = json.load(fh)
                self.assertEqual(got['main'], prof['layout']['main'])
                self.assertEqual(popup, prof['popup'])
                self.assertEqual((got['rail'], got['rail_axis']), (self.RAILS[theme], 'column'))
                seed = os.path.join(REPO, 'seeds', f'{theme} 1035.gdl')
                with open(seed, 'rb') as fh:
                    if fh.read(40).startswith(b'version https://git-lfs'):
                        self.skipTest(f'{theme} 1035.gdl is a Git LFS pointer (git lfs pull)')
                self.assertEqual(self._measure(seed, tuple(row['size'])), (got, popup))


# -- the frame: each series' working page off its own seed ---------------------------
def _profile(theme):
    with open(os.path.join(REPO, 'gdl', 'designsys', theme + '.json'), encoding='utf-8') as fh:
        return json.load(fh)


class TestTheFrameOfEachSeries(unittest.TestCase):
    """frame_of reads a series' working page off its own seed into the five
    bands, their surfaces and their slots by meaning, and each profile records
    what it reads. The values themselves are checked on the checked-in frames
    (tests/test_designsys.py TestTheFrame), which need no seed; these tie the
    frames to the seeds where Git LFS has pulled them."""
    _frames = {}

    def frame(self, theme, series):
        from gdl import seeds
        try:
            import PIL  # noqa: F401
        except ImportError:
            # frame_of counts a window message's lines with gdl.compose's
            # wrap, which draws with Pillow; CI runs this file without it.
            self.skipTest('Pillow is not here: a frame counts its messages\' lines with gdl.compose')
        key = (theme, series)
        if key not in self._frames:
            p = _profile(theme)
            row = p['panels'][series]
            seed = measure_series.series_seed(row)
            if not seeds.usable(seed):
                self._frames[key] = None
            else:
                self._frames[key] = measure_series.frame_of(seeds.path(seed), tuple(row['size']),
                                                            art=measure_series.frame_art(p, row))
        if self._frames[key] is None:
            self.skipTest(f'the {series} seed is not here (git lfs pull)')
        return self._frames[key]

    def test_each_profile_holds_the_frame_its_seed_measures(self):
        from gdl import seeds
        checked = 0
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            p = _profile(theme)
            for series, row in p['panels'].items():
                if series.startswith('_') or not seeds.usable(measure_series.series_seed(row)):
                    continue
                checked += 1
                with self.subTest(series=series):
                    self.assertEqual(self.frame(theme, series), row.get('frame'))
        if not checked:
            self.skipTest('no seeds here (git lfs pull)')

    def test_each_tab_is_where_the_seed_draws_it(self):
        # Read off the seed's own buttons, not through frame_of: the tabs a
        # frame records are the buttons of their IDs, one size, in a row.
        from gdl import seeds
        from gdl.project import Project
        checked = 0
        for theme in ('afterburn', 'mach', 'shockwave', 'turbulence'):
            for series, row in _profile(theme)['panels'].items():
                f = row.get('frame') if not series.startswith('_') else None
                tabs = [(f[b] or {}).get('tabs') for b in ('top', 'center')] if f else []
                tabs = next((t for t in tabs if t), None)
                seed = measure_series.series_seed(row) if tabs else None
                if not seeds.usable(seed):
                    continue
                checked += 1
                with self.subTest(series=series):
                    page = next(pg for pg in Project.open(seeds.path(seed)).pages() if pg['name'] == f['page'])
                    ids = {it['id'] for it in tabs['items']}
                    drawn = sorted(list(c['rect']) for c in page['controls'] if c['type'] == 'PBButton'
                                   and c['id'] in ids and tuple(c['rect'][1:]) == tuple(tabs['first'][1:]))
                    self.assertEqual([it['rect'] for it in tabs['items']], drawn)
        if not checked:
            self.skipTest('no seeds here (git lfs pull)')


if __name__ == '__main__':
    unittest.main()
