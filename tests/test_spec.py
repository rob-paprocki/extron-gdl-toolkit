"""Tests for the layout pass and ID allocation.

These are the two pieces of `gdl/spec.py` that are pure arithmetic, so unlike
everything on the authoring side they can be pinned down without Windows. They
are also where an off-by-one hides quietly: a grid whose last column is a pixel
narrow looks fine in a preview and wrong on a panel.

    python tests/test_spec.py
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.spec import ALIGN, BORDER_GEOMETRY, Panel, color, grid, stack  # noqa: E402


class TestGrid(unittest.TestCase):
    def test_single_cell_is_the_whole_region(self):
        self.assertEqual(grid([10, 20, 100, 50], 1, 1), [[10, 20, 100, 50]])

    def test_cells_tile_without_overlap_or_gap(self):
        cells = grid([0, 0, 300, 100], 3)
        self.assertEqual(cells, [[0, 0, 100, 100], [100, 0, 100, 100], [200, 0, 100, 100]])

    def test_gaps_come_out_of_the_cells_not_the_region(self):
        cells = grid([0, 0, 320, 100], 3, gap=10)
        self.assertEqual(cells[0][0], 0)
        # last cell must still end on the region's right edge
        self.assertEqual(cells[-1][0] + cells[-1][2], 320)

    def test_indivisible_width_still_fills_the_region(self):
        # 100 across 3 columns is 33.33 each; rounding must not lose a pixel
        # off the end or spill past it.
        for w in (100, 101, 997, 1280):
            for cols in (3, 6, 7):
                cells = grid([0, 0, w, 60], cols, gap=7)
                self.assertLessEqual(cells[-1][0] + cells[-1][2], w,
                                     f'{w}/{cols} spills past the region')
                self.assertGreaterEqual(cells[-1][0] + cells[-1][2], w - 1,
                                        f'{w}/{cols} leaves a gap at the end')

    def test_rows_advance_downward_and_fill(self):
        cells = grid([0, 0, 200, 200], 2, 2)
        self.assertEqual([c[1] for c in cells], [0, 0, 100, 100])
        self.assertEqual(cells[-1][1] + cells[-1][3], 200)

    def test_row_major_order(self):
        cells = grid([0, 0, 200, 200], 2, 2)
        self.assertEqual([(c[0], c[1]) for c in cells],
                         [(0, 0), (100, 0), (0, 100), (100, 100)])

    def test_padding_insets_all_four_edges(self):
        (x, y, w, h), = grid([0, 0, 100, 100], 1, 1, pad=10)
        self.assertEqual((x, y, w, h), (10, 10, 80, 80))

    def test_negative_gap_is_rejected(self):
        # A negative gap makes cells overlap while each stays individually
        # valid - positive size, on canvas - so nothing downstream catches it.
        with self.assertRaises(ValueError):
            grid([0, 0, 100, 100], 3, gap=-10)
        with self.assertRaises(ValueError):
            grid([0, 0, 100, 100], 2, 2, gap=0, gap_y=-5)

    def test_empty_grid_is_rejected(self):
        with self.assertRaises(ValueError):
            grid([0, 0, 100, 100], 0)
        with self.assertRaises(ValueError):
            grid([0, 0, 100, 100], 2, 0)

    def test_separate_vertical_gap(self):
        cells = grid([0, 0, 200, 210], 2, 2, gap=0, gap_y=10)
        self.assertEqual(cells[0][3], 100)
        self.assertEqual(cells[2][1], 110)


class TestStack(unittest.TestCase):
    def test_vertical_by_default(self):
        cells = stack([0, 0, 100, 300], 3)
        self.assertEqual([c[1] for c in cells], [0, 100, 200])
        self.assertTrue(all(c[0] == 0 and c[2] == 100 for c in cells))

    def test_horizontal_when_asked(self):
        cells = stack([0, 0, 300, 100], 3, horizontal=True)
        self.assertEqual([c[0] for c in cells], [0, 100, 200])
        self.assertTrue(all(c[1] == 0 and c[3] == 100 for c in cells))


class TestColor(unittest.TestCase):
    def test_six_digit_hex_is_opaque(self):
        self.assertEqual(color('#242634'), {'A': 255, 'R': 36, 'G': 38, 'B': 52})

    def test_eight_digit_hex_carries_alpha(self):
        self.assertEqual(color('#80242634'), {'A': 128, 'R': 36, 'G': 38, 'B': 52})

    def test_theme_key_resolves(self):
        self.assertEqual(color('surface', {'surface': '#242634'}),
                         {'A': 255, 'R': 36, 'G': 38, 'B': 52})

    def test_garbage_is_rejected_rather_than_defaulted(self):
        # Silently defaulting an unknown color would produce a panel that
        # looks subtly wrong instead of failing.
        with self.assertRaises(ValueError):
            color('not-a-color')


def _spec(controls, **kw):
    base = {'name': 'T', 'size': [1280, 800], 'theme': {'text': '#FFFFFF'},
            'pages': [dict({'name': 'P', 'number': 1000, 'controls': controls}, **kw)]}
    return Panel(base)


class TestIdAllocation(unittest.TestCase):
    def test_ids_are_banded_off_the_page_number(self):
        p = _spec([{'kind': 'label', 'rect': [0, 0, 10, 10]} for _ in range(3)])
        self.assertEqual([c['id'] for c in p.pages[0]['controls']], [1001, 1002, 1003])

    def test_pinned_ids_are_honoured_and_not_reissued(self):
        p = _spec([
            {'kind': 'label', 'rect': [0, 0, 10, 10]},
            {'kind': 'label', 'rect': [0, 0, 10, 10], 'id': 1002},
            {'kind': 'label', 'rect': [0, 0, 10, 10]},
        ])
        ids = [c['id'] for c in p.pages[0]['controls']]
        self.assertEqual(len(set(ids)), 3, f'ids collided: {ids}')
        self.assertIn(1002, ids)

    def test_pinned_id_inside_the_band_does_not_collide(self):
        p = _spec([{'kind': 'label', 'rect': [0, 0, 10, 10]} for _ in range(5)]
                  + [{'kind': 'label', 'rect': [0, 0, 10, 10], 'id': 1003}])
        ids = [c['id'] for c in p.pages[0]['controls']]
        self.assertEqual(len(set(ids)), len(ids), f'ids collided: {ids}')

    def test_two_controls_pinning_the_same_id_is_reported(self):
        p = _spec([
            {'kind': 'label', 'rect': [0, 0, 10, 10], 'id': 7},
            {'kind': 'label', 'rect': [0, 0, 10, 10], 'id': 7},
        ])
        self.assertTrue(any('already used' in m for m in p.check()),
                        'a duplicate pinned id must be caught, not silently kept')


class TestCheck(unittest.TestCase):
    def test_off_canvas_is_caught(self):
        p = _spec([{'kind': 'label', 'rect': [1200, 0, 200, 10]}])
        self.assertTrue(any('leaves the' in m for m in p.check()))

    def test_negative_origin_is_caught(self):
        p = _spec([{'kind': 'label', 'rect': [-5, 0, 10, 10]}])
        self.assertTrue(any('leaves the' in m for m in p.check()))

    def test_non_positive_size_is_caught(self):
        p = _spec([{'kind': 'label', 'rect': [0, 0, 0, 10]}])
        self.assertTrue(any('non-positive' in m for m in p.check()))

    def test_unknown_border_resource_is_caught(self):
        # A generator may only reference resources the donor already carries;
        # inventing a name is the one thing that has never been tested.
        p = _spec([{'kind': 'panel', 'rect': [0, 0, 10, 10],
                    'fill': '#FFFFFF', 'border': 'Invented - 3 Radius'}])
        self.assertTrue(any('unknown border' in m for m in p.check()))

    def test_identical_type_and_rect_is_caught(self):
        # One control is invisible behind the other - almost always a mistake.
        p = _spec([
            {'kind': 'panel', 'rect': [0, 0, 10, 10], 'fill': '#242634'},
            {'kind': 'panel', 'rect': [0, 0, 10, 10], 'fill': '#FF0000'},
        ])
        self.assertTrue(any('hidden behind' in m for m in p.check()))

    def test_same_rect_different_type_is_fine(self):
        # A label sitting exactly on its panel is normal design, not an error.
        p = _spec([
            {'kind': 'panel', 'rect': [0, 0, 10, 10], 'fill': '#242634'},
            {'kind': 'label', 'rect': [0, 0, 10, 10], 'text': 'hi'},
        ])
        self.assertEqual(p.check(), [])

    def test_a_clean_spec_has_no_complaints(self):
        p = _spec([{'kind': 'panel', 'rect': [0, 0, 100, 50],
                    'fill': '#242634', 'border': 'rounded'}])
        self.assertEqual(p.check(), [])


class TestControlTypes(unittest.TestCase):
    """The four types beyond panel/button/label/line, and their own fields."""

    def _ops(self, control):
        return _spec([control]).plan()['pages'][0]['controls'][0]

    def test_slider_carries_orientation_track_and_thumb(self):
        op = self._ops({'kind': 'slider', 'rect': [0, 0, 60, 300],
                        'orientation': 'down', 'track': 14, 'thumb': 40})
        self.assertEqual(op['donor_type'], 'PBSlider')
        f = op['fields']
        self.assertEqual(f['orientationField'], 3)          # down
        # No `Field` suffix on these three, unlike orientationField above.
        # Verified by writing them onto a live Extron.GUICPro.PBSlider.
        self.assertEqual(f['sliderTrackWidth'], 14)
        self.assertEqual(f['sliderThumbWidth'], 40)

    def test_line_endpoints_are_the_eight_position_enum(self):
        # A diagonal is TopLeft -> BottomRight; the angle comes from the rect.
        op = self._ops({'kind': 'line', 'rect': [0, 0, 600, 200],
                        'from': 'TopLeft', 'to': 'BottomRight', 'thickness': 3})
        f = op['fields']
        self.assertEqual(f['startPointField'], 7)
        self.assertEqual(f['endPointField'], 3)
        self.assertEqual(f['thicknessField'], 3)

    def test_level_and_image_and_datetime_map_to_their_classes(self):
        self.assertEqual(self._ops({'kind': 'level', 'rect': [0, 0, 40, 300]})['donor_type'],
                         'PBLevel')
        self.assertEqual(self._ops({'kind': 'image', 'rect': [0, 0, 40, 40]})['donor_type'],
                         'PBImage')
        self.assertEqual(self._ops({'kind': 'datetime', 'rect': [0, 0, 200, 40]})['donor_type'],
                         'PBDateTime')

    def test_type_fields_survive_into_the_plan(self):
        # They are computed in layout(), where the spec control is in scope.
        # Computing them in plan() silently yielded defaults, because plan()
        # iterates the layout model which has no 'thumb' or 'from'.
        op = self._ops({'kind': 'slider', 'rect': [0, 0, 60, 300], 'thumb': 33})
        self.assertEqual(op['fields']['sliderThumbWidth'], 33)

    def test_a_slider_is_a_touch_target_but_a_level_is_not(self):
        small = {'rect': [0, 0, 20, 20]}
        self.assertTrue(any('touch target' in m
                            for m in _spec([dict(small, kind='slider')]).check()))
        self.assertFalse(any('touch target' in m
                             for m in _spec([dict(small, kind='level')]).check()))


class TestDonorAvailability(unittest.TestCase):
    """Clone-never-construct means a type absent from the donor is unauthorable."""

    def _path(self, *parts):
        import os
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(here, *parts)

    def test_needs_lists_every_class_the_spec_uses(self):
        p = _spec([{'kind': 'button', 'rect': [0, 0, 60, 60], 'text': 'a'},
                   {'kind': 'level', 'rect': [0, 0, 40, 300]}])
        self.assertEqual(p.needs(), {'PBButton', 'PBLevel'})

    def test_a_donor_without_the_type_is_reported(self):
        p = _spec([{'kind': 'level', 'rect': [0, 0, 40, 300]}])
        alt = self._path('fixtures', 'gdl',
                         'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
        problems = p.check_donor(alt)
        self.assertTrue(any('PBLevel' in m for m in problems))

    def test_a_donor_with_the_type_is_accepted(self):
        p = _spec([{'kind': 'level', 'rect': [0, 0, 40, 300]}])
        archived = self._path('fixtures', 'gdl',
                              'Interface_Archived_J26450039_Liberty_Bank_Boardroom_TLP1025.gdl')
        self.assertEqual(p.check_donor(archived), [])

    def test_the_worked_example_is_satisfiable_by_the_main_fixture(self):
        import os
        p = Panel.load(self._path('examples', 'panel.json'))
        alt = self._path('fixtures', 'gdl',
                         'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
        self.assertEqual(p.check_donor(alt), [])

    def test_a_name_the_donor_already_uses_is_reported(self):
        """GUI Designer: "Duplicate page or popup page names are not allowed
        within the same project." It is a build ERROR, and it cost a Windows
        round trip to find - the generated popups joined the donor's project,
        where those two names were already taken."""
        p = Panel({'name': 'T', 'size': [1280, 800], 'theme': {'text': '#FFFFFF'},
                   'pages': [{'name': '1000 - Home', 'number': 1000,
                              'controls': [{'kind': 'label', 'rect': [0, 0, 8, 8]}]}]})
        alt = self._path('fixtures', 'gdl',
                         'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
        problems = p.check_donor(alt)
        self.assertTrue(any('1000 - Home' in m and 'unique' in m for m in problems))

    def test_a_popup_name_the_donor_already_uses_is_reported(self):
        p = Panel({'name': 'T', 'size': [1280, 800], 'theme': {'text': '#FFFFFF'},
                   'pages': [{'name': 'Fresh', 'number': 1000, 'controls': [
                       {'kind': 'popup_ref', 'rect': [0, 0, 100, 60], 'group': 'G'}]}],
                   'popups': [{'name': '160 - Confirmation', 'number': 2100,
                               'group': 'G', 'size': [100, 60], 'controls': []}]})
        alt = self._path('fixtures', 'gdl',
                         'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
        self.assertTrue(any('160 - Confirmation' in m for m in p.check_donor(alt)))


class TestNameUniqueness(unittest.TestCase):
    """Names must be unique project-wide, across pages AND popups together."""

    def _panel(self, page, popup):
        return Panel({'name': 'T', 'size': [1280, 800], 'theme': {'text': '#FFFFFF'},
                      'pages': [{'name': page, 'number': 1000, 'controls': [
                          {'kind': 'popup_ref', 'rect': [0, 0, 100, 60], 'group': 'G'}]}],
                      'popups': [{'name': popup, 'number': 2100, 'group': 'G',
                                  'size': [100, 60], 'controls': []}]})

    def test_distinct_names_are_clean(self):
        self.assertEqual(self._panel('Home', 'Volume').check(), [])

    def test_a_popup_may_not_reuse_a_page_name(self):
        problems = self._panel('Volume', 'Volume').check()
        self.assertTrue(any('unique' in m for m in problems), problems)

    def test_two_popups_may_not_share_a_name(self):
        p = Panel({'name': 'T', 'size': [1280, 800], 'theme': {'text': '#FFFFFF'},
                   'pages': [{'name': 'Home', 'number': 1000, 'controls': [
                       {'kind': 'popup_ref', 'rect': [0, 0, 100, 60], 'group': 'G'}]}],
                   'popups': [{'name': 'Dup', 'number': 2100, 'group': 'G',
                               'size': [100, 60], 'controls': []},
                              {'name': 'Dup', 'number': 2200, 'group': 'G',
                               'size': [100, 60], 'controls': []}]})
        self.assertTrue(any('unique' in m for m in p.check()))


class TestBuildPlan(unittest.TestCase):
    """The plan is what the Windows applier consumes, so it needs its own tests.

    layout() and plan() look fills up by the same key, and when that key changed
    only layout() was updated - so every plan carried fill=None and every
    generated panel came out uncolored. Nothing caught it, because the preview
    renders from layout() and the tests only exercised layout().
    """

    def test_fills_reach_the_plan(self):
        p = _spec([{'kind': 'panel', 'rect': [0, 0, 100, 50], 'fill': '#242634'}])
        op = p.plan()['pages'][0]['controls'][0]
        self.assertEqual(op['fill'], 0xFF242634)

    def test_borders_reach_the_plan(self):
        p = _spec([{'kind': 'panel', 'rect': [0, 0, 100, 50],
                    'fill': '#242634', 'border': 'capsule'}])
        op = p.plan()['pages'][0]['controls'][0]
        self.assertEqual(op['border'], '2D Capsule')

    def test_text_color_reaches_the_plan(self):
        p = _spec([{'kind': 'label', 'rect': [0, 0, 100, 50],
                    'text': 'x', 'color': '#FF0000'}])
        op = p.plan()['pages'][0]['controls'][0]
        self.assertEqual(op['text_color'], 0xFFFF0000)

    def test_the_worked_example_carries_its_colors_into_the_plan(self):
        import os
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = Panel.load(os.path.join(here, 'examples', 'panel.json'))
        ops = p.plan()['pages'][0]['controls']
        filled = [o for o in ops if o['fill']]
        self.assertGreater(len(filled), 15, 'most controls in the example are filled')
        accent = [o for o in ops if o['fields']['nameField'] == 'Presets']
        self.assertEqual(accent[0]['fill'], 0xFF3D8BFD, 'the accent color must survive')


class TestExtronRules(unittest.TestCase):
    """Extron's own numeric standards. See docs/design-rules.md for provenance."""

    def test_a_named_model_reproduces_extrons_published_rows(self):
        """By MODEL, which is the number Extron's Quick Reference table (p.90)
        actually gives - its rows name panels, not resolutions."""
        from gdl.spec import touch_minimums
        self.assertEqual(touch_minimums('TLP1035T'), (53, 12))    # 1280x800
        self.assertEqual(touch_minimums('TLP300M'), (58, 13))     # 320x480
        self.assertEqual(touch_minimums('TLP320M'), (40, 9))      # 320x240

    def test_dpi_varies_within_a_resolution(self):
        """The correction that made the model-keyed lookup necessary. Keying
        the minimum off the resolution gave every 1280x800 panel the TLP Pro
        1035's 53px, which is 14px too small for a TLP Pro 835."""
        from gdl.spec import touch_minimums, dpi
        self.assertEqual(dpi('TLP1035M'), 149.0)
        self.assertEqual(dpi('TLP1220MG'), 124.75)
        self.assertEqual(dpi('TLP835M'), 188.68)
        self.assertEqual(touch_minimums('TLP835M'), (67, 15))
        self.assertEqual(touch_minimums('TLP1220MG'), (44, 10))

    def test_an_unnamed_model_falls_back_to_the_densest_physical_panel(self):
        """Safe rather than right: without a model the check cannot know which
        1280x800 panel this is, so it holds the design to the tightest one."""
        from gdl.spec import touch_minimums
        self.assertEqual(touch_minimums((1280, 800)), (67, 15))   # TLP Pro 835

    def test_a_model_carries_its_extron_part_number(self):
        """GUI Designer identifies a panel by part number - a platform object
        without one opens as "Unknown"."""
        from gdl.spec import part_number
        self.assertEqual(part_number('TLP1535M'), '60-2000-02')

    def test_1280x720_now_has_a_minimum(self):
        """It had none while the table came from Extron's published rows, which
        have no 1280x720 row. The assemblies do: TLP Pro 535M/T at 293.72 DPI."""
        from gdl.spec import touch_minimums
        self.assertEqual(touch_minimums('TLP535M'), (104, 23))

    def test_undersized_button_is_caught(self):
        p = _spec([{'kind': 'button', 'rect': [0, 0, 40, 40], 'text': 'tiny'}])
        self.assertTrue(any('touch target' in m for m in p.check()))

    def test_button_at_the_minimum_passes(self):
        p = _spec([{'kind': 'button', 'rect': [0, 0, 67, 67], 'text': 'ok'}])
        self.assertFalse(any('touch target' in m for m in p.check()))

    def test_naming_the_model_gives_the_tighter_minimum(self):
        """A 60px button fails the unnamed 1280x800 fallback and passes on the
        panel this project is actually for."""
        big = {'kind': 'button', 'rect': [0, 0, 60, 60], 'text': 'ok'}
        self.assertTrue(any('touch target' in m for m in _spec([big]).check()))
        named = Panel({'name': 'T', 'model': 'TLP1035T', 'theme': {'text': '#FFFFFF'},
                       'pages': [{'name': 'P', 'number': 1000, 'controls': [big]}]})
        self.assertFalse(any('touch target' in m for m in named.check()))

    def test_labels_are_not_touch_targets(self):
        # Only interactive controls need to meet 9mm.
        p = _spec([{'kind': 'label', 'rect': [0, 0, 20, 20], 'text': 'hi'}])
        self.assertFalse(any('touch target' in m for m in p.check()))

    def test_more_than_nine_buttons_in_a_group_is_caught(self):
        p = _spec([{'grid': {'rect': [0, 0, 1200, 100], 'cols': 10, 'kind': 'button',
                             'name': 'toomany',
                             'items': [{'text': str(i)} for i in range(10)]}}])
        self.assertTrue(any('per-group maximum' in m for m in p.check()))

    def test_nine_buttons_in_a_group_passes(self):
        p = _spec([{'grid': {'rect': [0, 0, 1200, 100], 'cols': 9, 'kind': 'button',
                             'name': 'ok',
                             'items': [{'text': str(i)} for i in range(9)]}}])
        self.assertFalse(any('per-group maximum' in m for m in p.check()))

    def test_too_many_colors_is_caught(self):
        hues = ['#111111', '#222222', '#333333', '#444444',
                '#555555', '#666666', '#777777', '#888888']
        p = _spec([{'kind': 'panel', 'rect': [i * 60, 0, 50, 50], 'fill': h}
                   for i, h in enumerate(hues)])
        self.assertTrue(any('color' in m and 'maximum' in m for m in p.check()))

    def test_small_body_text_is_caught(self):
        p = _spec([{'kind': 'label', 'rect': [0, 0, 100, 40], 'text': 'x', 'size': 10}])
        self.assertTrue(any('body-text minimum' in m for m in p.check()))

    def test_buttons_too_close_together_are_caught(self):
        # 15px is the unnamed-1280x800 minimum (2mm at the densest physical
        # panel that size, the TLP Pro 835); 4px is well under it.
        p = _spec([
            {'kind': 'button', 'rect': [0, 0, 100, 60], 'text': 'a'},
            {'kind': 'button', 'rect': [0, 64, 100, 60], 'text': 'b'},
        ])
        self.assertTrue(any('below the 15px minimum' in m for m in p.check()))

    def test_adequately_spaced_buttons_pass(self):
        p = _spec([
            {'kind': 'button', 'rect': [0, 0, 100, 60], 'text': 'a'},
            {'kind': 'button', 'rect': [0, 80, 100, 60], 'text': 'b'},
        ])
        self.assertFalse(any('minimum (2mm' in m for m in p.check()))

    def test_the_worked_example_meets_the_standards(self):
        # examples/panel.json is what docs/from-scratch.md shows being built.
        import os
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = Panel.load(os.path.join(here, 'examples', 'panel.json'))
        self.assertEqual(p.check(), [])


class TestLayoutModel(unittest.TestCase):
    def test_controls_are_authored_without_artwork(self):
        # TLPImageID = -1 is what makes this a spec for Build rather than a
        # claim about pixels.
        p = _spec([{'kind': 'panel', 'rect': [0, 0, 10, 10], 'fill': '#242634'}])
        model, _ = p.layout()
        self.assertTrue(all(c['TLPImageID'] == -1 for c in model['Pages'][0]['Controls']))

    def test_per_page_ids_are_unique_within_the_page(self):
        # idField is a per-page editor handle; userIdField is the addressable
        # ID. They are different things and both must be unique per page.
        p = _spec([{'kind': 'label', 'rect': [0, 0, 10, 10]} for _ in range(6)])
        model, _ = p.layout()
        ids = [c['ID'] for c in model['Pages'][0]['Controls']]
        self.assertEqual(len(set(ids)), len(ids))

    def test_fills_key_matches_what_the_compositor_looks_up(self):
        # compose.render_control looks up (page id, control id).
        p = _spec([{'kind': 'panel', 'rect': [3, 4, 10, 20], 'fill': '#242634'}])
        model, fills = p.layout()
        pg = model['Pages'][0]
        self.assertIn((pg['ID'], pg['Controls'][0]['ID']), fills)

    def test_grid_directive_expands_to_controls(self):
        p = _spec([{'grid': {'rect': [0, 0, 300, 100], 'cols': 3, 'kind': 'button',
                             'items': [{'text': 'a'}, {'text': 'b'}, {'text': 'c'}]}}])
        model, _ = p.layout()
        cs = model['Pages'][0]['Controls']
        self.assertEqual([c['Text'] for c in cs], ['a', 'b', 'c'])
        self.assertEqual([c['Left'] for c in cs], [0, 100, 200])

    def test_grid_shared_properties_reach_every_item(self):
        p = _spec([{'grid': {'rect': [0, 0, 200, 50], 'cols': 2, 'kind': 'button',
                             'fill': '#242634',
                             'items': [{'text': 'a'}, {'text': 'b'}]}}])
        _, fills = p.layout()
        self.assertEqual(len(fills), 2)

    def test_item_overrides_shared_property(self):
        p = _spec([{'grid': {'rect': [0, 0, 200, 50], 'cols': 2, 'kind': 'button',
                             'fill': '#242634',
                             'items': [{'text': 'a'}, {'text': 'b', 'fill': '#FF0000'}]}}])
        _, fills = p.layout()
        reds = [v for v in fills.values() if v['fill']['R'] == 255]
        self.assertEqual(len(reds), 1)


class TestNestedLayout(unittest.TestCase):
    def test_nested_grid_lays_out_inside_its_parent_cell(self):
        # Without this, a nested directive positions against the page origin -
        # it looks like it worked and is off by wherever the parent cell is.
        p = _spec([{'stack': {'rect': [0, 0, 1280, 800], 'count': 2,
                              'items': [
                                  {'grid': {'cols': 2, 'kind': 'button',
                                            'items': [{'text': 'a'}, {'text': 'b'}]}},
                                  {'kind': 'label', 'text': 'bottom'},
                              ]}}])
        model, _ = p.layout()
        cs = {c['Text']: c for c in model['Pages'][0]['Controls']}
        # top cell is [0,0,1280,400]; two columns inside it
        self.assertEqual((cs['a']['Left'], cs['a']['Top'], cs['a']['Width']), (0, 0, 640))
        self.assertEqual((cs['b']['Left'], cs['b']['Top'], cs['b']['Width']), (640, 0, 640))
        self.assertEqual(cs['a']['Height'], 400)
        # the sibling still gets the second cell
        self.assertEqual((cs['bottom']['Left'], cs['bottom']['Top']), (0, 400))

    def test_rect_inside_a_cell_is_an_offset_not_page_coordinates(self):
        p = _spec([{'stack': {'rect': [100, 200, 400, 400], 'count': 1,
                              'items': [{'kind': 'label', 'text': 'x',
                                         'rect': [10, 20, 50, 30]}]}}])
        model, _ = p.layout()
        c = model['Pages'][0]['Controls'][0]
        self.assertEqual((c['Left'], c['Top'], c['Width'], c['Height']), (110, 220, 50, 30))

    def test_unnested_rects_are_still_page_coordinates(self):
        p = _spec([{'kind': 'label', 'text': 'x', 'rect': [10, 20, 50, 30]}])
        model, _ = p.layout()
        c = model['Pages'][0]['Controls'][0]
        self.assertEqual((c['Left'], c['Top']), (10, 20))


class TestBorderGeometry(unittest.TestCase):
    def test_every_alias_resolves_to_known_geometry(self):
        from gdl.spec import BORDERS
        for alias, name in BORDERS.items():
            self.assertIn(name, BORDER_GEOMETRY, f'{alias} -> {name} has no geometry')

    def test_alignment_enum_matches_the_documented_formula(self):
        # value = 3*vertical + horizontal, vertical 0 bottom/1 middle/2 top,
        # horizontal 0 center/1 left/2 right.
        self.assertEqual(ALIGN['center'], 3 * 1 + 0)
        self.assertEqual(ALIGN['top-left'], 3 * 2 + 1)
        self.assertEqual(ALIGN['bottom-right'], 3 * 0 + 2)


class TestSpecsAreUTF8(unittest.TestCase):
    """A spec is JSON, and JSON is UTF-8 (RFC 8259) whatever the locale says.

    `open(path)` without an encoding uses the platform default, which is cp1252
    on a stock Windows install. A prose-written spec arrives full of characters
    that are not ASCII - typographic dashes and quotes, degree signs, accented
    room names - and cp1252 mishandles them two different ways:

      * an en-dash decodes to mojibake, silently. Found by rendering a volume
        row whose minus was an en-dash: the button read a-EUR-quote, the build
        was clean, and no check looked at captions as text.
      * a curly quote raises UnicodeDecodeError outright, because 0x9D is not
        assigned in cp1252. The spec simply will not load.

    Neither is reproducible off Windows, where the default is already UTF-8.
    """

    SAMPLE = {'name': 'Sala Café', 'size': [1280, 800],
              'theme': {'text': '#FFFFFF', 'raised': '#2E3142'},
              'pages': [{'name': 'P', 'number': 1000, 'controls': [
                  {'kind': 'button', 'name': 'Down', 'rect': [0, 0, 200, 80],
                   'text': '–', 'fill': 'raised'},
                  {'kind': 'label', 'name': 'Temp', 'rect': [0, 100, 200, 80],
                   'text': '21° — “Auto”'},
              ]}]}

    def _round_trip(self, encoding_written='utf-8'):
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'spec.json')
        with open(path, 'w', encoding=encoding_written) as fh:
            json.dump(self.SAMPLE, fh, ensure_ascii=False)
        return Panel.load(path)

    def test_non_ascii_captions_survive_loading(self):
        p = self._round_trip()
        caps = [c['text'] for c in p.spec['pages'][0]['controls']]
        self.assertIn('–', caps[0])
        self.assertEqual(caps[1], '21° — “Auto”')
        self.assertEqual(p.spec['name'], 'Sala Café')

    def test_non_ascii_reaches_the_plan(self):
        p = self._round_trip()
        plan = p.plan()
        texts = [(op.get('fields') or {}).get('textField')
                 for op in plan['pages'][0]['controls']]
        self.assertIn('–', texts)
        self.assertTrue(any(t and '“' in t for t in texts),
                        f'curly quotes lost on the way to the plan: {texts}')

    def test_a_plan_written_out_and_read_back_keeps_them(self):
        p = self._round_trip()
        d = tempfile.mkdtemp()
        out = os.path.join(d, 'plan.json')
        with open(out, 'w', encoding='utf-8') as fh:
            json.dump(p.plan(), fh, ensure_ascii=False)
        with open(out, encoding='utf-8') as fh:
            back = json.load(fh)
        texts = [(op.get('fields') or {}).get('textField')
                 for op in back['pages'][0]['controls']]
        self.assertIn('–', texts)


def _project(pages=(), popups=(), **top):
    spec = {'name': 'T', 'size': [1280, 800], 'theme': {'text': '#FFFFFF'},
            'pages': list(pages), 'popups': list(popups)}
    spec.update(top)
    return Panel(spec)


def _label(**kw):
    return dict({'kind': 'label', 'rect': [0, 0, 10, 10]}, **kw)


class TestProjectWideIds(unittest.TestCase):
    """A control ID is what the control program addresses, and extronlib binds
    one object per ID across the WHOLE panel - so an ID handed to two unrelated
    controls makes one button's handler fire for another's press."""

    def test_unnumbered_popups_get_disjoint_ids(self):
        # The defaults used to be popup numbers 9000 and 9001, whose bands start
        # at 9001 and 9002: the second popup's first control got the first
        # popup's second ID, and check() said nothing.
        p = _project(
            pages=[{'name': 'P', 'number': 1000, 'controls': [
                {'kind': 'popup_ref', 'rect': [0, 0, 100, 100], 'group': 'G'}]}],
            popups=[{'name': n, 'group': 'G', 'size': [100, 100],
                     'controls': [_label(), _label(rect=[20, 0, 10, 10])]}
                    for n in ('A', 'B')])
        ids = [c['id'] for pu in p.popups for c in pu['controls']]
        self.assertEqual(len(ids), len(set(ids)), f'popup ids collided: {ids}')

    def test_overlapping_page_bands_do_not_reuse_ids(self):
        p = _project(pages=[
            {'name': 'A', 'number': 1000, 'controls': [_label(rect=[i * 11, 0, 10, 10])
                                                       for i in range(3)]},
            {'name': 'B', 'number': 1001, 'controls': [_label(rect=[i * 11, 0, 10, 10])
                                                       for i in range(3)]}])
        ids = [c['id'] for pg in p.pages for c in pg['controls']]
        self.assertEqual(len(ids), len(set(ids)), f'page ids collided: {ids}')

    def test_an_id_pinned_on_another_page_is_not_handed_out(self):
        p = _project(pages=[
            {'name': 'A', 'number': 1000, 'controls': [_label()]},
            {'name': 'B', 'number': 2000, 'controls': [_label(id=1001)]}])
        self.assertNotEqual(p.pages[0]['controls'][0]['id'], 1001)

    def test_a_pinned_id_may_repeat_across_pages(self):
        # Deliberate: Extron's own projects mirror one button onto several
        # popups under one ID (Liberty Bank reuses 81/82 across confirmations).
        p = _project(pages=[
            {'name': 'A', 'number': 1000, 'controls': [_label(id=500)]},
            {'name': 'B', 'number': 2000, 'controls': [_label(id=500)]}])
        self.assertEqual(p.check(), [])

    def test_a_duplicate_id_inside_a_popup_is_reported(self):
        p = _project(
            pages=[{'name': 'P', 'number': 1000, 'controls': [
                {'kind': 'popup_ref', 'rect': [0, 0, 100, 100], 'group': 'G'}]}],
            popups=[{'name': 'A', 'group': 'G', 'size': [100, 100],
                     'controls': [_label(id=7), _label(id=7, rect=[20, 0, 10, 10])]}])
        self.assertTrue(any('already used' in m for m in p.check()), p.check())

    def test_needs_counts_popup_controls(self):
        # Donor checks key off needs(); a type used only inside a popup used to
        # be skipped, so a donor lacking it passed and the build could not
        # author it.
        p = _project(
            pages=[{'name': 'P', 'number': 1000, 'controls': [
                {'kind': 'popup_ref', 'rect': [0, 0, 100, 100], 'group': 'G'}]}],
            popups=[{'name': 'A', 'group': 'G', 'size': [100, 100],
                     'controls': [{'kind': 'slider', 'rect': [0, 0, 60, 90]}]}])
        self.assertIn('PBSlider', p.needs())


class TestStartPage(unittest.TestCase):
    """A generated panel used to boot into the DONOR's start page: the built
    DefaultPage stayed pointing at the client's '1000 - Home'."""

    PAGES = [{'name': 'Home', 'number': 1000, 'controls': [_label()]},
             {'name': 'Settings', 'number': 1100, 'controls': [_label()]}]

    def test_default_is_the_first_spec_page(self):
        self.assertEqual(_project(pages=self.PAGES).plan()['default_page'], 'Home')

    def test_an_explicit_start_page_reaches_the_plan(self):
        p = _project(pages=self.PAGES, start_page='Settings')
        self.assertEqual(p.plan()['default_page'], 'Settings')

    def test_an_unknown_start_page_is_reported(self):
        p = _project(pages=self.PAGES, start_page='Nowhere')
        self.assertTrue(any('start_page' in m for m in p.check()), p.check())

    def test_a_popup_cannot_be_the_start_page(self):
        p = _project(pages=self.PAGES, start_page='Pop',
                     popups=[{'name': 'Pop', 'modal': True, 'controls': []}])
        self.assertTrue(any('start_page' in m for m in p.check()), p.check())


class TestModalPopups(unittest.TestCase):
    """The applier used to write modalField = false on every popup, so a spec's
    modal confirmation built as an ungrouped STANDARD popup - which no
    reference can ever show."""

    def _p(self, popup):
        return _project(pages=[{'name': 'Home', 'number': 1000, 'controls': [_label()]}],
                        popups=[popup])

    def test_modal_reaches_the_plan(self):
        op = self._p({'name': 'Confirm', 'modal': True, 'controls': []}).plan()['popups'][0]
        self.assertTrue(op['modal'])

    def test_a_modal_popup_without_a_size_is_given_the_canvas(self):
        op = self._p({'name': 'Confirm', 'modal': True, 'controls': []}).plan()['popups'][0]
        self.assertEqual(op['size'], [1280, 800])

    def test_a_modal_popup_smaller_than_the_canvas_is_reported(self):
        p = self._p({'name': 'Confirm', 'modal': True, 'size': [600, 400], 'controls': []})
        self.assertTrue(any('modal' in m and 'canvas' in m for m in p.check()), p.check())

    def test_a_full_canvas_modal_is_clean(self):
        p = self._p({'name': 'Confirm', 'modal': True, 'size': [1280, 800],
                     'controls': [_label()]})
        self.assertEqual(p.check(), [])

    def test_a_standard_popup_with_no_group_is_reported(self):
        # Only a reference can show a standard popup, and a reference binds to
        # a group. With no group it can never appear.
        p = self._p({'name': 'Loose', 'size': [100, 100], 'controls': []})
        self.assertTrue(any('group' in m for m in p.check()), p.check())

    def test_an_authored_reference_is_never_modal(self):
        # PBPopupPageReference has its own modalField, True on the references
        # Build generates for modal popups. A seed's first reference is one of
        # those, so a clone inherited True and Build discarded the authored
        # group reference on the next build - silently, 0 errors.
        p = _project(pages=[{'name': 'Home', 'number': 1000, 'controls': [
            {'kind': 'popup_ref', 'rect': [0, 0, 100, 100], 'group': 'G'}]}],
            popups=[{'name': 'A', 'group': 'G', 'size': [100, 100], 'controls': []}])
        op = p.plan()['pages'][0]['controls'][0]
        self.assertIs(op['fields']['modalField'], False)

    def test_a_modal_control_off_the_canvas_is_reported(self):
        p = self._p({'name': 'Confirm', 'modal': True,
                     'controls': [_label(rect=[1275, 0, 10, 10])]})
        self.assertTrue(any('does not fit' in m for m in p.check()), p.check())


class TestPalette(unittest.TestCase):
    """p.49's six colors are counted off what the panel draws. Counting only
    the colors a spec names let examples/huddle-functions.json pass at six
    while its white captions made seven."""

    BG = {'background': '#000000'}
    WHITE = (('A', 255), ('B', 255), ('G', 255), ('R', 255))

    def _pal(self, controls, popups=()):
        return _project([dict({'name': 'P', 'controls': controls}, **self.BG)],
                        [dict(pu, **self.BG) for pu in popups]).palette()

    def test_a_caption_with_no_color_counts_the_theme_text_color(self):
        self.assertIn(self.WHITE, self._pal([_label(text='Hi')]))

    def test_a_control_with_nothing_to_say_does_not(self):
        self.assertNotIn(self.WHITE, self._pal([_label()]))

    def test_a_named_color_replaces_the_default(self):
        self.assertNotIn(self.WHITE, self._pal([_label(text='Hi', color='#FF0000')]))

    def test_a_clock_always_draws_text(self):
        self.assertIn(self.WHITE, self._pal([{'kind': 'datetime', 'rect': [0, 0, 10, 10]}]))

    def test_a_state_caption_counts_unless_the_state_names_a_color(self):
        btn = {'kind': 'button', 'rect': [0, 0, 80, 80], 'color': '#FF0000',
               'states': ['Off', {'name': 'On', 'fill': '#00FF00'}]}
        self.assertNotIn(self.WHITE, self._pal([btn]))
        del btn['color']
        btn['states'] = [{'name': 'Off', 'color': '#FF0000', 'text': 'x'},
                         {'name': 'On', 'fill': '#00FF00', 'text': 'y'}]
        self.assertIn(self.WHITE, self._pal([btn]))

    def test_popups_count(self):
        pal = self._pal([], popups=[{'name': 'Pop', 'controls': [
            _label(text='x', color='#123456')]}])
        self.assertIn((('A', 255), ('B', 0x56), ('G', 0x34), ('R', 0x12)), pal)

    def test_seven_drawn_colors_are_reported(self):
        controls = [_label(text='x', fill=f) for f in
                    ('#111111', '#222222', '#333333', '#444444', '#555555')]
        p = _project([dict({'name': 'P', 'controls': controls}, **self.BG)])
        self.assertEqual(len(p.palette()), 7)
        self.assertTrue(any('7 distinct colors' in m for m in p.check()), p.check())


if __name__ == '__main__':
    unittest.main(verbosity=2)
