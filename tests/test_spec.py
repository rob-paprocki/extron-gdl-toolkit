"""Tests for the layout pass and ID allocation.

These are the two pieces of `gdl/spec.py` that are pure arithmetic, so unlike
everything on the authoring side they can be pinned down without Windows. They
are also where an off-by-one hides quietly: a grid whose last column is a pixel
narrow looks fine in a preview and wrong on a panel.

    python tests/test_spec.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.spec import ALIGN, BORDER_GEOMETRY, Panel, colour, grid, stack  # noqa: E402


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


class TestColour(unittest.TestCase):
    def test_six_digit_hex_is_opaque(self):
        self.assertEqual(colour('#242634'), {'A': 255, 'R': 36, 'G': 38, 'B': 52})

    def test_eight_digit_hex_carries_alpha(self):
        self.assertEqual(colour('#80242634'), {'A': 128, 'R': 36, 'G': 38, 'B': 52})

    def test_theme_key_resolves(self):
        self.assertEqual(colour('surface', {'surface': '#242634'}),
                         {'A': 255, 'R': 36, 'G': 38, 'B': 52})

    def test_garbage_is_rejected_rather_than_defaulted(self):
        # Silently defaulting an unknown colour would produce a panel that
        # looks subtly wrong instead of failing.
        with self.assertRaises(ValueError):
            colour('not-a-colour')


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


class TestExtronRules(unittest.TestCase):
    """Extron's own numeric standards. See docs/design-rules.md for provenance."""

    def test_touch_minimums_reproduce_extrons_published_rows(self):
        from gdl.spec import touch_minimums
        # Values Extron publishes in its Quick Reference table (p.90).
        self.assertEqual(touch_minimums((1280, 800)), (53, 12))
        self.assertEqual(touch_minimums((320, 480)), (58, 13))
        self.assertEqual(touch_minimums((320, 240)), (40, 9))

    def test_1280x720_has_no_documented_minimum(self):
        # Extron's table has no row for it; inventing one would be a guess
        # presented as a requirement.
        from gdl.spec import touch_minimums
        self.assertEqual(touch_minimums((1280, 720)), (None, None))

    def test_undersized_button_is_caught(self):
        p = _spec([{'kind': 'button', 'rect': [0, 0, 40, 40], 'text': 'tiny'}])
        self.assertTrue(any('touch target' in m for m in p.check()))

    def test_button_at_the_minimum_passes(self):
        p = _spec([{'kind': 'button', 'rect': [0, 0, 53, 53], 'text': 'ok'}])
        self.assertFalse(any('touch target' in m for m in p.check()))

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

    def test_too_many_colours_is_caught(self):
        hues = ['#111111', '#222222', '#333333', '#444444',
                '#555555', '#666666', '#777777', '#888888']
        p = _spec([{'kind': 'panel', 'rect': [i * 60, 0, 50, 50], 'fill': h}
                   for i, h in enumerate(hues)])
        self.assertTrue(any('colour' in m and 'maximum' in m for m in p.check()))

    def test_small_body_text_is_caught(self):
        p = _spec([{'kind': 'label', 'rect': [0, 0, 100, 40], 'text': 'x', 'size': 10}])
        self.assertTrue(any('body-text minimum' in m for m in p.check()))

    def test_buttons_too_close_together_are_caught(self):
        # 12px is the 1280x800 minimum; 4px is well under it.
        p = _spec([
            {'kind': 'button', 'rect': [0, 0, 100, 60], 'text': 'a'},
            {'kind': 'button', 'rect': [0, 64, 100, 60], 'text': 'b'},
        ])
        self.assertTrue(any('below the 12px minimum' in m for m in p.check()))

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
        # horizontal 0 centre/1 left/2 right.
        self.assertEqual(ALIGN['center'], 3 * 1 + 0)
        self.assertEqual(ALIGN['top-left'], 3 * 2 + 1)
        self.assertEqual(ALIGN['bottom-right'], 3 * 0 + 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
