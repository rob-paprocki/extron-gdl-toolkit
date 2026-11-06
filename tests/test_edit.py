"""Tests for the edit vocabulary.

These run against a built project rather than hand-made page dicts, on purpose.
Every bug this vocabulary has had came from the difference between what a
panel file looks like in the abstract and what a real one contains: a button
whose caption is not in `textField`, a caption that is formatted text with
hand-placed tabs, a page whose controls do not fit a smaller panel. The
synthetic fixture (tests/data/synthetic/), built by the toolkit on a seed, is
that project, everywhere.

What only a hand-edited project holds - a caption stored as formatted text on
a state, one ID mirrored across two popups, a fill only a state has, a touch
target under Extron's minimum - the synthetic spec cannot carry: a spec never
writes formatted text, and it has to pass the design rules to build. Each is
put, as the client project that found it had it, into a page shaped exactly as
Project.pages() reads one (`_hand_made`, below), or spliced into the
fixture's own pages.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import SYNTHETIC, needs_synthetic  # noqa: E402

from gdl.edit import Edits, _norm  # noqa: E402
from gdl.spec import MODELS_FULL, PRESS_FIELD as PRESS  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _on_synthetic(edits):
    return Edits({'edits': edits}, SYNTHETIC)


@needs_synthetic()
class TestSelectionOnTheSyntheticFixture(unittest.TestCase):
    def test_an_empty_selector_matches_everything(self):
        self.assertGreater(len(_on_synthetic([]).select({})), 500)

    def test_page_and_type_are_anded(self):
        hits = _on_synthetic([]).select({'page': 'Controls', 'type': 'PBSlider'})
        self.assertEqual(len(hits), 5)
        self.assertTrue(all(pg['name'] == 'Controls' and c['type'] == 'PBSlider' for pg, c in hits))

    def test_text_matches_a_buttons_caption(self):
        hits = _on_synthetic([]).select({'page': 'Main', 'text': 'Alpha'})
        self.assertEqual([c['caption'] for _, c in hits], ['Alpha'])

    def test_text_matches_a_caption_only_a_state_holds(self):
        """The trap this vocabulary was built around. A button's wording often
        lives on its states, so a selector that compared `textField` matched
        nothing on a real project and the edit silently did nothing. The
        fixture's picture buttons have no textField, and on each state the
        formatted 'Preset 1' their seed's clone carries (docs/gdl-format.md
        section 2)."""
        hits = _on_synthetic([]).select({'page': 'Buttons', 'text': 'Preset 1'})
        self.assertEqual(sorted(c['name'] for _, c in hits), ['PicA', 'PicB', 'PicC'])
        for _, c in hits:
            self.assertFalse(c['text'], 'held on the state, not the control')
            self.assertEqual(c['caption_in'], 'fstate')

    def test_regex_selection(self):
        hits = _on_synthetic([]).select({'text_matches': r'^Channel \d\d$'})
        self.assertEqual(len(hits), 8)


@needs_synthetic()
class TestUnknownKeysOnTheSyntheticFixture(unittest.TestCase):
    """select() tests only the keys it knows, so a misspelled one was skipped
    and the selector matched everything: a recolor meant for five sliders
    restyled 292 controls, and a renumber of one page's buttons renumbered its
    labels and shapes too - with 0 errors, and verify_built checking the same
    plan. Every level of an edit file is held to the keys something reads."""

    def _errors(self, spec):
        return Edits(spec, SYNTHETIC).check()[1]

    def test_a_misspelled_selector_key_is_an_error_and_plans_nothing(self):
        spec = {'edits': [{'op': 'restyle', 'select': {'tipe': 'PBSlider'},
                           'map': {'#37394E': '#1B2233'}}]}
        plan, errors, _ = Edits(spec, SYNTHETIC).check()
        self.assertTrue([e for e in errors if "'tipe'" in e], errors)
        self.assertEqual(plan['controls'], [])

    def test_the_correct_selector_still_plans(self):
        spec = {'edits': [{'op': 'restyle', 'select': {'type': 'PBSlider'},
                           'map': {'#37394E': '#1B2233'}}]}
        plan, errors, _ = Edits(spec, SYNTHETIC).check()
        self.assertEqual(errors, [])
        self.assertTrue(plan['controls'])

    def test_a_renumber_with_a_misspelled_selector_is_an_error(self):
        errors = self._errors({'edits': [{'op': 'renumber', 'start': 5000,
                                          'select': {'tpye': 'PBButton', 'page': 'Main'}}]})
        self.assertTrue([e for e in errors if "'tpye'" in e], errors)

    def test_a_misspelled_op_key_is_an_error(self):
        errors = self._errors({'edits': [{'op': 'restyle', 'mpa': {'#37394E': '#1B2233'}}]})
        self.assertTrue([e for e in errors if "'mpa'" in e], errors)

    def test_a_key_of_another_op_is_an_error(self):
        """`scale` belongs to retarget; on a rename it does nothing."""
        errors = self._errors({'edits': [{'op': 'rename', 'map': {'Alpha': 'First'},
                                          'scale': True}]})
        self.assertTrue([e for e in errors if "'scale'" in e], errors)

    def test_a_misspelled_top_level_key_is_an_error(self):
        """`edit` for `edits` planned nothing, with 0 errors."""
        errors = self._errors({'edit': [{'op': 'rename', 'map': {'Alpha': 'First'}}]})
        self.assertTrue([e for e in errors if "'edit'" in e], errors)

    def test_underscored_keys_are_notes(self):
        errors = self._errors({'_why': 'a note', 'edits': [
            {'op': 'rename', '_why': 'shorter', 'select': {'page': 'Main'},
             'map': {'Alpha': 'First'}}]})
        self.assertEqual(errors, [])

    def test_the_examples_edit_file_passes(self):
        """examples/edits.json is written against the synthetic fixture, so it
        is checked wherever the toolkit is."""
        import json
        with open(os.path.join(HERE, 'examples', 'edits.json'), encoding='utf-8') as fh:
            spec = json.load(fh)
        plan, errors, _ = Edits(spec, SYNTHETIC).check()
        self.assertEqual(errors, [])
        self.assertTrue(plan['controls'])


@needs_synthetic()
class TestRenameOnTheSyntheticFixture(unittest.TestCase):
    def test_a_caption_on_the_control_is_written_there_and_on_every_state(self):
        """A button renders from its states, so a caption written only on the
        control builds blank."""
        plan, problems = _on_synthetic([{'op': 'rename', 'select': {'page': 'Main', 'text': 'Alpha'},
                                         'text': 'First'}]).plan()
        self.assertEqual(problems, [])
        (op,) = plan['controls']
        self.assertEqual(op['fields'], {'textField': 'First'})
        self.assertEqual(op['per_state'], [{'index': 0, 'fields': {'textField': 'First'}},
                                           {'index': 1, 'fields': {'textField': 'First'}}])

    def test_a_selector_matching_nothing_is_an_error(self):
        _, problems = _on_synthetic([{'op': 'rename', 'select': {'text': 'No Such Caption'},
                                      'text': 'x'}]).plan()
        self.assertTrue(any('matched nothing' in p or 'nothing has the caption' in p
                            for p in problems), problems)

    def test_map_form_renames_several_at_once(self):
        plan, problems = _on_synthetic([{'op': 'rename', 'select': {'page': 'Main'},
                                         'map': {'Alpha': 'A', 'Beta': 'B'}}]).plan()
        self.assertEqual(problems, [])
        self.assertEqual(len(plan['controls']), 2)

    def test_a_flattened_buttons_rename_writes_the_field_build_bakes(self):
        """Build bakes a flattened button's caption from each state's
        ftextField and from nothing else (docs/gdl-format.md section 2): Flat1
        renamed on a copy of this fixture kept 'Flattened 16' in its art while
        its textField and layout.json said the new words. So each state takes
        the new words in ftextField too - and in textField, where layout.json
        reads them - and the plan marks it baked, for verify_built to look for
        in the art."""
        plan, problems = _on_synthetic([{'op': 'rename', 'select': {'page': 'Buttons', 'name': 'Flat1'},
                                         'text': 'Renamed 16'}]).plan()
        self.assertEqual(problems, [])
        (op,) = plan['controls']
        self.assertEqual(op['fields'], {'textField': 'Renamed 16'})
        self.assertEqual([(ps['index'], ps['fields'], ps.get('ftext'), ps.get('flattened'))
                          for ps in op['per_state']],
                         [(i, {'textField': 'Renamed 16', 'ftextField': 'Renamed 16'}, 'Renamed 16', True)
                          for i in (0, 1)])

    def test_a_flattened_caption_keeps_its_own_line_break(self):
        """Flat3 breaks at LF, as a spec writes it, and Build bakes it as two
        lines: the new caption breaks where it asks, at the field's own LF."""
        plan, _ = _on_synthetic([{'op': 'rename', 'select': {'page': 'Buttons', 'name': 'Flat3'},
                                  'text': 'Three\r\nlines'}]).plan()
        for ps in plan['controls'][0]['per_state']:
            self.assertEqual(ps['fields']['ftextField'], 'Three\nlines')

    def test_a_button_that_is_not_flattened_is_not_baked(self):
        """Brect draws its caption live: its ftextField is the seed's clone's
        '               Preset 1', which nothing draws, and is left alone."""
        plan, _ = _on_synthetic([{'op': 'rename', 'select': {'page': 'Buttons', 'name': 'Brect'},
                                  'text': 'square'}]).plan()
        for ps in plan['controls'][0]['per_state']:
            self.assertEqual(ps['fields'], {'textField': 'square'})
            self.assertNotIn('flattened', ps)


@needs_synthetic()
class TestRenumberOnTheSyntheticFixture(unittest.TestCase):
    def test_ids_are_handed_out_in_order_and_by_step(self):
        sel = {'page': 'Start', 'type': 'PBLabel'}
        plan, problems = _on_synthetic([{'op': 'renumber', 'select': sel, 'start': 1100}]).plan()
        self.assertEqual(problems, [])
        self.assertEqual([o['fields']['userIdField'] for o in plan['controls']], [1100, 1101])
        plan, _ = _on_synthetic([{'op': 'renumber', 'select': sel, 'start': 200, 'step': 10}]).plan()
        self.assertEqual([o['fields']['userIdField'] for o in plan['controls']], [200, 210])

    def test_colliding_with_an_untouched_control_is_an_error(self):
        """Duplicate IDs are legal in the format - Extron uses them for feedback
        mirrors - so nothing downstream would complain. It is still never what a
        renumber means."""
        start = [p for p in _on_synthetic([]).pages if p['name'] == 'Start'][0]
        taken = next(c['id'] for c in start['controls'] if c['id'] and c['type'] == 'PBButton')
        _, errors, _ = _on_synthetic([{'op': 'renumber', 'start': taken,
                                       'select': {'page': 'Start', 'type': 'PBLabel'}}]).check()
        self.assertTrue(any('already has it' in e for e in errors), errors)

    def test_only_an_addressable_control_is_numbered(self):
        """A button, label, level or slider with an ID. Start's popup
        references and clocks are not addressable, and its four unnamed
        references have no ID on purpose: numbering one gives the program a
        control it never had."""
        plan, errors, warnings = _on_synthetic([{'op': 'renumber', 'select': {'page': 'Start'},
                                                 'start': 1100}]).check()
        self.assertEqual(errors, [])
        self.assertEqual([(o['was'], o['fields']['userIdField']) for o in plan['controls']],
                         [(1001, 1100), (1002, 1101), (1004, 1102)])
        self.assertTrue(any('7 control(s) the selector matched' in w and 'no ID' in w
                            for w in warnings), warnings)

    def test_nothing_addressable_is_an_error(self):
        _, errors, _ = _on_synthetic([{'op': 'renumber', 'start': 1100,
                                       'select': {'page': 'Start',
                                                  'type': 'PBPopupPageReference'}}]).check()
        self.assertTrue(any('nothing addressable' in e for e in errors), errors)

    def test_an_id_past_uint16_is_an_error(self):
        _, errors, _ = _on_synthetic([{'op': 'renumber', 'select': {'type': 'PBButton'},
                                       'start': 65530, 'step': 3}]).check()
        self.assertTrue(any('65535' in e for e in errors), errors)

    def test_a_start_or_step_that_cannot_be_is_an_error_not_a_hang(self):
        """A step of 0 never moves past a taken ID: the planner spun forever."""
        for start, step in ((1, 0), (1, -1), (1, 1.5), (0, 1), (70000, 1), ('abc', 1), (True, 1)):
            plan, errors, _ = _on_synthetic([{'op': 'renumber', 'select': {'type': 'PBLabel'},
                                              'start': start, 'step': step}]).check()
            self.assertTrue(errors, (start, step))
            self.assertEqual(plan['controls'], [], (start, step))


@needs_synthetic()
class TestRestyleOnTheSyntheticFixture(unittest.TestCase):
    def test_colors_are_remapped(self):
        plan, problems = _on_synthetic([{'op': 'restyle', 'select': {'type': 'PBSlider'},
                                         'map': {'#37394E': '#1B2233'}}]).plan()
        self.assertEqual(problems, [])
        self.assertTrue(plan['controls'])
        for o in plan['controls']:
            self.assertEqual(o['colors']['borderFillColorField'], '#FF1B2233')

    def test_an_unused_color_is_a_warning_not_an_error(self):
        """A theme map legitimately covers colors a given project happens not
        to use, so this must not block the edit."""
        ed = _on_synthetic([{'op': 'restyle', 'map': {'#010203': '#040506'}}])
        _, errors, _ = ed.check()
        self.assertEqual(errors, [])
        self.assertIn('#FF010203', ed._unused_colors)


class TestColors(unittest.TestCase):
    def test_short_hex_means_opaque(self):
        self.assertEqual(_norm('#242634'), '#FF242634')
        self.assertEqual(_norm('#FF242634'), '#FF242634')


@needs_synthetic()
class TestRetargetOnTheSyntheticFixture(unittest.TestCase):
    def test_an_unknown_model_is_an_error_with_a_suggestion(self):
        _, errors, _ = _on_synthetic([{'op': 'retarget', 'model': 'TLP1720'}]).check()
        self.assertTrue(errors)
        self.assertIn('TLP1720MG', errors[0])

    def test_cci700_is_gone(self):
        """GUI Designer 1.28 dropped CCI700 from PlatformProTypeEnum.

        It has to be absent from MODELS too, or `check()` passes a retarget the
        applier cannot perform - and because the control-geometry ops are a
        separate pass from the project ops, a half-applied retarget writes a
        file whose controls are scaled for one panel on another panel's canvas.
        """
        self.assertNotIn('CCI700', MODELS_FULL)
        _, errors, _ = _on_synthetic([{'op': 'retarget', 'model': 'CCI700'}]).check()
        self.assertTrue(errors, 'a CCI700 retarget must not pass check()')

    def test_a_real_model_sets_all_three_fields_and_moves_every_control(self):
        plan, errors, _ = _on_synthetic([{'op': 'retarget', 'model': 'TLP1535M',
                                          'scale': True}]).check()
        self.assertEqual(errors, [], 'scaling up should not overflow')
        self.assertEqual(len(plan['project']), 1)
        self.assertEqual(plan['project'][0]['size'], [1920, 1080])
        self.assertEqual(plan['project'][0]['model'], 'TLP1535M')
        # The plan names the MODEL, never a platform class. The applier gets the
        # class from Enum.Parse + CreatePlatform; a guessed class name was wrong
        # for 9 of the 55 models and read by nothing.
        self.assertNotIn('platform_class', plan['project'][0])
        self.assertGreater(len(plan['controls']), 500)
        for o in plan['controls']:
            self.assertIn('leftField', o['fields'])

    def test_shrinking_without_scaling_is_an_error(self):
        """The whole point of the check. Build moves a control that no longer
        fits to 0,0 - silently, reporting 0 errors - so an unscaled retarget to
        a smaller panel destroys the layout and nothing says so."""
        _, errors, _ = _on_synthetic([{'op': 'retarget', 'model': 'TLP725M'}]).check()
        self.assertTrue(any('falls outside' in e and '0,0' in e for e in errors), errors)

    def test_the_old_minimum_is_the_projects_own_model(self):
        """A TLP Pro 1035, minimum 53 px, every touch target at least that: on
        an 835 (67 px) some are under, and none was already."""
        _, _, warnings = _on_synthetic([{'op': 'retarget', 'model': 'TLP835M'}]).check()
        under = [w for w in warnings if 'touch target' in w]
        self.assertTrue(under)
        self.assertFalse([w for w in under if 'already under' in w], under)


@needs_synthetic()
class TestATouchTargetAlreadyUnder(unittest.TestCase):
    """A retarget of a hand-made project surfaces the touch targets that were
    already under the minimum of the panel it leaves - dozens on the client
    project this was found on. The synthetic spec passes the design rules to
    build, so it has none: a key under the 1035's 53 px is spliced into its
    Start page, read exactly as the fixture's own are."""

    def _check(self, edit, size=(30, 30)):
        ed = _on_synthetic([edit])
        start = next(pg for pg in ed.pages if pg['name'] == 'Start')
        begin = next(c for c in start['controls'] if c['name'] == 'Begin')
        start['controls'].append(dict(begin, obj_id=999999, id=1999, name='Tiny',
                                      rect=(20, 20) + size))
        return ed.check()

    def test_a_pre_existing_touch_violation_says_so(self):
        _, errors, warnings = self._check({'op': 'retarget', 'model': 'TLP1535M', 'scale': True})
        self.assertEqual(errors, [])
        # Scaled to 45x40, under the 1535's 45; the fixture's own keys all clear it.
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn('Tiny', warnings[0])
        self.assertIn("already under the old panel's minimum - the TLP1035M or TLP1035T's 53px",
                      warnings[0])

    def test_the_old_minimum_is_the_projects_own_model(self):
        """The fixture is a TLP Pro 1035 (60-1999-02), whose minimum is 53 px.
        By its resolution alone the old minimum was the 835's 67, so a button
        legal on the 1035 that the move to an 835 makes too small was tagged as
        one that already was."""
        _, _, warnings = self._check({'op': 'retarget', 'model': 'TLP835M'})
        under = [w for w in warnings if 'touch target' in w]
        for w in under:
            w_, h_ = (int(v) for v in w.split(': ', 1)[1].split()[0].split('x'))
            self.assertEqual('already under' in w, min(w_, h_) < 53, w)
        self.assertEqual([w for w in under if 'already under' in w and 'Tiny' in w],
                         [w for w in under if 'already under' in w])
        self.assertTrue([w for w in under if 'already under' in w], under)
        self.assertTrue(any('already under' not in w for w in under), under)
        self.assertTrue(all("the TLP1035M or TLP1035T's" in w for w in under
                            if 'already under' in w), under)

    def test_warnings_never_block_a_plan(self):
        """A retarget of a real project surfaces touch-target warnings. If those
        blocked, the tool would refuse the job it was asked to do."""
        plan, errors, warnings = self._check({'op': 'retarget', 'model': 'TLP1535M', 'scale': True})
        self.assertTrue(warnings)
        self.assertEqual(errors, [])
        self.assertTrue(plan['controls'])


class TestRetarget(unittest.TestCase):
    def test_ecp_is_a_known_model(self):
        """Extron Control Pro, new in 1.28. Read out of the assemblies:
        CreatePlatform -> PBVTLPEcpPlatform, 1920x1080 @ 220 DPI, 60-sVTLPEcp."""
        self.assertEqual(MODELS_FULL['VTLPEcp'], (1920, 1080, 220.0, '60-sVTLPEcp'))


class TestRetargetOrientation(unittest.TestCase):
    """A panel that rotates (gdl.spec.sizes) is a target either way up. On a
    seed, so the public copy runs it too."""

    def setUp(self):
        from _corpus import seed, usable
        self.path = seed('Afterburn 1035.gdl')
        if not usable(self.path):
            self.skipTest('seeds/Afterburn 1035.gdl is not here (git lfs pull)')

    def _plan(self, op):
        return Edits({'edits': [op]}, self.path).check()

    def test_a_1035m_turned_portrait_carries_its_canvas(self):
        plan, errors, _ = self._plan({'op': 'retarget', 'model': 'TLP1035M', 'size': [800, 1280],
                                      'scale': True})
        self.assertEqual(errors, [])
        self.assertEqual(plan['project'][0]['model'], 'TLP1035M')
        self.assertEqual(plan['project'][0]['size'], [800, 1280])
        # every page canvas turns with it: 1280x800 pages land at 800x1280
        full = [p for p in plan['pages'] if p['was'] == [1280, 800]]
        self.assertTrue(full)
        self.assertTrue(all(p['size'] == [800, 1280] for p in full))

    def test_without_a_size_it_is_the_panels_default(self):
        plan, errors, _ = self._plan({'op': 'retarget', 'model': 'TLP1035M'})
        self.assertEqual(errors, [])
        self.assertEqual(plan['project'][0]['size'], [1280, 800])

    def test_a_canvas_the_panel_does_not_run_at_is_an_error(self):
        """The 1035T does not rotate; its platform lists one resolution."""
        _, errors, _ = self._plan({'op': 'retarget', 'model': 'TLP1035T', 'size': [800, 1280],
                                   'scale': True})
        self.assertTrue(any('800x1280' in e and 'TLP1035T' in e for e in errors), errors)

    def test_a_size_that_is_not_width_and_height_is_an_error_not_a_crash(self):
        """'800x1280' is how New-GdlSeed.ps1 and gdl.templates take a canvas, so
        it is the slip to expect here; it was read as the characters 8 and 0. A
        list of one number crashed check() outright."""
        for size in ('800x1280', [800], 800, [800, 1280, 1], ['800', '1280'], [800, None]):
            with self.subTest(size=size):
                _, errors, _ = self._plan({'op': 'retarget', 'model': 'TLP1035M', 'size': size,
                                           'scale': True})
                self.assertTrue(any('size is [width, height]' in e for e in errors), errors)


# -- what only a hand-edited project holds ------------------------------------
#
# The synthetic fixture has no button whose states say different things, no
# caption held as formatted text, no mirror and no fill only a state has, so
# those cases use a page shaped exactly like Project.pages() output - each as
# the client project these rules were found on had it.

def _st(name, caption=None, fill=None, where='state', text_color=None, stroke=None, ftext=None):
    """A state as Project.state() reads one. `ftext` is its ftextField as
    stored; a formatted caption's defaults to the caption itself."""
    if ftext is None and where == 'fstate':
        ftext = caption
    return {'name': name, 'caption': caption, 'caption_in': where if caption else None,
            'ftext': ftext, 'fill': fill, 'stroke': stroke, 'text_color': text_color}


def _button(name, states, **kw):
    first = next((s for s in states if s['caption']), None)
    c = {'type': 'PBButton', 'name': name, 'id': 11, 'rect': (0, 0, 200, 80),
         'text': None, 'caption': first['caption'] if first else None,
         'caption_in': first['caption_in'] if first else None, 'tlp_image': -1,
         'fill': None, 'stroke': None, 'text_color': None, 'border': None,
         'n_states': len(states), 'state_names': [s['name'] for s in states],
         'states': states, 'press': 1, 'default_state': 0, 'state_flags': 0,
         'obj_id': 7}
    c.update(kw)
    return c


def _hand_made(edits, *controls, pages=None):
    """Edits over one page holding `controls`, or over `pages`, with no
    project behind them."""
    ed = Edits.__new__(Edits)
    ed.spec, ed.path, ed.project, ed.edits = {'edits': edits}, 'hand-made', None, edits
    ed.pages = pages or [{'kind': 'page', 'id': 51, 'name': 'Home', 'modal': None,
                          'size': (1280, 800), 'controls': list(controls)}]
    return ed


GREY, NAVY, BLUE = ({'A': 255, 'R': 0x37, 'G': 0x39, 'B': 0x4E},
                    {'A': 255, 'R': 0x24, 'G': 0x26, 'B': 0x34},
                    {'A': 255, 'R': 0x3D, 'G': 0x8B, 'B': 0xFD})
DISPLAY = _button('Display', [_st('Off', 'Display Off', GREY),
                              _st('On', 'Display On', BLUE)])
# A key whose caption is on both states and whose fill is only On's.
INPUT = _button('Input', [_st('Off', 'Input 1'), _st('On', 'Input 1', NAVY)])


class TestRenameByState(unittest.TestCase):
    def test_the_selector_finds_a_caption_in_any_state(self):
        ed = _hand_made([], DISPLAY)
        self.assertEqual(len(ed.select({'text': 'Display On'})), 1)
        self.assertEqual(len(ed.select({'text_matches': 'On$'})), 1)

    def test_map_renames_only_the_state_that_says_it(self):
        plan, problems = _hand_made([{'op': 'rename', 'map': {'Display On': 'Screen On'}}],
                                    DISPLAY).plan()
        self.assertEqual(problems, [])
        (op,) = plan['controls']
        self.assertEqual(op['per_state'], [{'index': 1, 'was': 'Display On',
                                            'fields': {'textField': 'Screen On'}}])

    def test_one_caption_over_different_ones_is_refused(self):
        """Writing 'Screen' to every state would erase the feedback wording,
        silently - the old behavior."""
        _, problems = _hand_made([{'op': 'rename', 'select': {'name': 'Display'},
                                   'text': 'Screen'}], DISPLAY).plan()
        self.assertTrue(any('different in each state' in p and "'Display Off'" in p
                            for p in problems), problems)

    def test_state_narrows_a_rename(self):
        plan, problems = _hand_made([{'op': 'rename', 'select': {'name': 'Display'},
                                      'text': 'Screen Off', 'state': 'Off'}],
                                    DISPLAY).plan()
        self.assertEqual(problems, [])
        self.assertEqual([ps['index'] for ps in plan['controls'][0]['per_state']], [0])

    def test_an_unknown_state_is_an_error(self):
        _, problems = _hand_made([{'op': 'rename', 'select': {'name': 'Display'},
                                   'text': 'x', 'state': 'Standby'}], DISPLAY).plan()
        self.assertTrue(any("no state 'Standby'" in p for p in problems), problems)

    def test_state_with_map_is_an_error(self):
        _, problems = _hand_made([{'op': 'rename', 'map': {'Display On': 'x'},
                                   'state': 'On'}], DISPLAY).plan()
        self.assertTrue(any('`state` goes with `text`' in p for p in problems), problems)

    def test_each_state_is_written_where_its_own_caption_lives(self):
        mixed = _button('M', [_st('Off', 'Cams', where='fstate'), _st('On', 'Cams')])
        plan, _ = _hand_made([{'op': 'rename', 'map': {'Cams': 'Cameras'}}], mixed).plan()
        a, b = plan['controls'][0]['per_state']
        self.assertEqual((a.get('ftext'), a.get('flattened')), ('Cameras', True))
        self.assertEqual(b['fields'], {'textField': 'Cameras'})

    def test_a_caption_on_its_states_is_written_on_each_by_index(self):
        """No textField, the caption on both states, as most of the client
        project's buttons held theirs: both are written, each by index, and not
        the control."""
        plan, problems = _hand_made([{'op': 'rename', 'select': {'text': 'Input 1'},
                                      'text': 'Laptop'}], INPUT).plan()
        self.assertEqual(problems, [])
        (op,) = plan['controls']
        self.assertEqual([(ps['index'], ps['fields']) for ps in op['per_state']],
                         [(0, {'textField': 'Laptop'}), (1, {'textField': 'Laptop'})])
        self.assertNotIn('fields', op)


class TestFormattedCaptions(unittest.TestCase):
    """A caption GUI Designer stores as formatted text (`ftextField`), with
    hand-placed tabs and line breaks, is baked into the artwork. Only a
    hand-edited project has one - a spec never writes it - so each case is a
    button holding one on both states, as the client project's Cameras and
    Displays did (docs/editing.md)."""

    def _ed(self, old, new):
        b = _button('F', [_st('Off', old, where='fstate'), _st('On', old, where='fstate')])
        return _hand_made([{'op': 'rename', 'select': {'text': old}, 'text': new}], b)

    def test_rename_writes_ftext_for_a_formatted_caption(self):
        plan, _ = self._ed('Cameras', 'Camera Control').plan()
        op = plan['controls'][0]
        self.assertTrue(op['per_state'])
        for ps in op['per_state']:
            self.assertEqual(ps['ftext'], 'Camera Control')
            self.assertTrue(ps['flattened'])
            self.assertEqual(ps['fields'], {'ftextField': 'Camera Control'}, 'not textField')

    def test_growing_a_formatted_caption_warns(self):
        """Measured against the real build: 'Cameras' -> 'Camera Control'
        rasterizes as two lines with the second unindented over the icon."""
        _, _, warnings = self._ed('Cameras', 'Camera Control').check()
        self.assertEqual(len([w for w in warnings if 'baked into the artwork' in w]), 1, warnings)

    def test_a_same_length_formatted_rename_does_not_warn(self):
        """'Displays' -> 'Screens' built correctly, so warning on it would be
        crying wolf on the one case that works."""
        _, errors, warnings = self._ed('Displays', 'Screens').check()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_the_new_words_keep_the_fields_layout(self):
        """Its tabs, line breaks and leading spaces are how a formatted caption
        draws - two CRLFs put a source's label under its icon, leading spaces
        put a list button's past it - so the new words go where the old ones
        were, line by line, at the field's own line break, and a line it did
        not have takes its last line's indent: unindented, it lies over the
        icon (docs/editing.md). New words that bring a layout of their own - a
        tab, or a leading space or break - are written as they are. The plan
        carries the field whole: gdl.edit decides it, the applier writes it."""
        for old, new, want in (('\t\tDevice\r\n\t\tComms', 'Device\nRouting', '\t\tDevice\r\n\t\tRouting'),
                               ('\t\tDevice\r\n\t\tComms', 'Screens', '\t\tScreens'),
                               ('\t\tCameras', 'Camera\nControl', '\t\tCamera\n\t\tControl'),
                               ('\r\n\r\nLaptop', 'PC', '\r\n\r\nPC'),
                               ('Laptop\r\n\r\n', 'PC', 'PC\r\n\r\n'),
                               ('               Preset 1', 'Scene 1', '               Scene 1'),
                               ('     Call', 'Dial\nNow', '     Dial\n     Now'),
                               ('\t\tCameras', '\tCamera\r\n\tControl', '\tCamera\r\n\tControl')):
            with self.subTest(old=old, new=new):
                b = _button('F', [_st('Off', 'x', where='fstate', ftext=old)])
                plan, _ = _hand_made([{'op': 'rename', 'select': {'name': 'F'}, 'text': new}], b).plan()
                (ps,) = plan['controls'][0]['per_state']
                self.assertEqual(ps['fields'], {'ftextField': want})
                self.assertEqual((ps['ftext'], ps['flattened']), (new, True))


class TestFlattenedCaptions(unittest.TestCase):
    """A button whose flattenTextField is true has Build bake its caption from
    each state's ftextField alone - not textField, and an empty one bakes no
    words (docs/gdl-format.md section 2). Measured on a copy of the synthetic
    fixture: three of its plain buttons made flattened and renamed, and its
    own Flat1, built with the old words or none in their art
    (archive/job-e823df9b/rebuild-1104/item3/)."""

    def _plan(self, *states, **op):
        b = _button('B', list(states), flatten=True)
        edit = dict({'op': 'rename', 'select': {'name': 'B'}}, **op)
        plan, problems = _hand_made([edit], b).plan()
        self.assertEqual(problems, [])
        return plan['controls'][0]['per_state']

    def test_words_in_textfield_and_none_in_ftextfield_are_written_to_both(self):
        """Brect made flattened: its words in its states' textField and an
        empty ftextField, which built with no words in its art."""
        for ps in self._plan(_st('Off', 'rect', ftext=''), _st('On', 'rect', ftext=''), text='square'):
            self.assertEqual(ps['fields'], {'textField': 'square', 'ftextField': 'square'})
            self.assertEqual((ps['ftext'], ps['flattened'], ps['was']), ('square', True, 'rect'))

    def test_a_donors_ftextfield_keeps_its_layout_and_takes_the_words(self):
        """Bcapsule made flattened kept its seed's clone's
        '               Preset 1', and baked those words: its leading
        spaces are the layout its art drew, so they stay."""
        (ps,) = self._plan(_st('Off', 'capsule', ftext='               Preset 1'), text='pill')
        self.assertEqual(ps['fields'], {'textField': 'pill', 'ftextField': '               pill'})

    def test_growing_one_warns_as_a_formatted_one_does(self):
        """Baked, it wraps where Build wraps it, which no one sees before the
        build."""
        b = _button('B', [_st('Off', 'Mic', ftext='Mic')], flatten=True)
        _, _, warnings = _hand_made([{'op': 'rename', 'select': {'name': 'B'},
                                      'text': 'Microphone Mute'}], b).check()
        self.assertEqual(len([w for w in warnings if 'baked into the artwork' in w]), 1, warnings)

    def test_a_map_reaches_only_the_state_that_says_it(self):
        per = self._plan(_st('Off', 'Mic On', ftext='Mic On'), _st('On', 'Mic Off', ftext='Mic Off'),
                         map={'Mic Off': 'Muted'})
        self.assertEqual([(ps['index'], ps['fields']) for ps in per],
                         [(1, {'textField': 'Muted', 'ftextField': 'Muted'})])

    def test_a_states_op_writes_a_flattened_states_words_where_build_bakes_them(self):
        """`states` gives a state its text as `rename` does, so it is baked the
        same way."""
        b = _button('B', [_st('Off', 'rect', ftext='rect'), _st('On', 'rect', ftext='rect')], flatten=True)
        plan, problems = _hand_made([{'op': 'states', 'select': {'name': 'B'},
                                      'states': [{'name': 'Off', 'text': 'Idle'},
                                                 {'name': 'On', 'text': 'Live'}]}], b).plan()
        self.assertEqual(problems, [])
        per = plan['controls'][0]['per_state']
        self.assertEqual([(ps['fields'].get('textField'), ps['fields'].get('ftextField'), ps.get('ftext'),
                           ps.get('flattened')) for ps in per],
                         [('Idle', 'Idle', 'Idle', True), ('Live', 'Live', 'Live', True)])


class TestRenumberMirrors(unittest.TestCase):
    """Controls sharing an ID are one control to the program - a feedback twin
    on its page, one button on two confirmation popups. Numbered one by one,
    each took its own, and check() said nothing. Laid out as the client
    project these were found on had them: a source key and its twin on the
    main page, and its shutdown key on two confirmation popups."""

    @staticmethod
    def _pages():
        def key(name, caption, id_, obj_id):
            return _button(name, [_st('Off', caption), _st('On', caption)], id=id_, obj_id=obj_id)
        return [
            {'kind': 'page', 'id': 51, 'name': 'Main', 'modal': None, 'size': (1280, 800),
             'controls': [key('Source', 'Laptop', 5000, 1), key('Source Twin', 'Laptop', 5000, 2),
                          key('Mute', 'Mute', 5001, 3)]},
            {'kind': 'popup', 'id': 52, 'name': 'Confirmation', 'modal': True, 'size': (1280, 800),
             'controls': [key('Shutdown', 'Yes', 81, 1)]},
            {'kind': 'popup', 'id': 53, 'name': 'Teams Confirmation', 'modal': True,
             'size': (1280, 800), 'controls': [key('Shutdown', 'Yes', 81, 1)]}]

    def _check(self, edit):
        return _hand_made([edit], pages=self._pages()).check()

    def test_mirrors_take_one_new_id(self):
        plan, errors, _ = self._check({'op': 'renumber', 'start': 30000,
                                       'select': {'page': 'Main', 'type': 'PBButton'}})
        self.assertEqual(errors, [])
        new = {o['fields']['userIdField'] for o in plan['controls'] if o['was'] == 5000}
        self.assertEqual(len(new), 1, new)
        olds = {o['was'] for o in plan['controls']}
        self.assertEqual(len({o['fields']['userIdField'] for o in plan['controls']}), len(olds))
        plan, errors, warnings = self._check({'op': 'renumber', 'start': 40000,
                                              'select': {'name': 'Shutdown'}})
        self.assertEqual((errors, [o['fields']['userIdField'] for o in plan['controls']]),
                         ([], [40000, 40000]))
        self.assertEqual([w for w in warnings if 'mirror' in w], [])

    def test_a_mirror_the_selector_leaves_is_a_warning(self):
        _, errors, warnings = self._check({'op': 'renumber', 'start': 40000, 'select': {
            'page': 'Confirmation', 'name': 'Shutdown'}})
        self.assertEqual(errors, [])
        self.assertTrue(any("'Teams Confirmation'" in w and 'keeps id 81' in w
                            for w in warnings), warnings)


class TestRestyleByState(unittest.TestCase):
    def test_a_fill_that_lives_only_on_a_state_is_restyled(self):
        """No fill of its own: Off is transparent and On is #242634, as on the
        client project's Table Input keys. Matching the control's colors found
        nothing to restyle on 288 of that project's 442 buttons."""
        plan, problems = _hand_made([{'op': 'restyle', 'map': {'#242634': '#101826'}}],
                                    INPUT).plan()
        self.assertEqual(problems, [])
        (op,) = plan['controls']
        self.assertNotIn('colors', op)
        self.assertEqual(op['per_state'], [{'index': 1, 'colors': {
            'borderFillColorField': '#FF101826'}}])

    def test_each_state_is_remapped_from_its_own_color(self):
        """The old op wrote the control's new color to every state, so an On
        state came out in the Off color."""
        plan, _ = _hand_made([{'op': 'restyle', 'map': {'#37394E': '#111111',
                                                        '#3D8BFD': '#2266EE'}}],
                             DISPLAY).plan()
        per = plan['controls'][0]['per_state']
        self.assertEqual([(ps['index'], ps['colors']['borderFillColorField']) for ps in per],
                         [(0, '#FF111111'), (1, '#FF2266EE')])

    def test_text_color_is_remapped(self):
        white = {'A': 255, 'R': 255, 'G': 255, 'B': 255}
        b = _button('T', [_st('Off', 'x', GREY, text_color=white),
                          _st('On', 'x', BLUE, text_color=white)])
        plan, _ = _hand_made([{'op': 'restyle', 'map': {'#FFFFFF': '#F0F0F0'}}], b).plan()
        per = plan['controls'][0]['per_state']
        self.assertEqual([ps['colors'] for ps in per],
                         [{'textColorField': '#FFF0F0F0'}] * 2)


class TestStatesOp(unittest.TestCase):
    FOUR = ['Off', {'name': 'Warming', 'fill': '#5A5C70', 'text': 'Warming Up'},
            {'name': 'On', 'text': 'Display On'},
            {'name': 'Cooling', 'fill': '#2E3040', 'text': 'Cooling Down'}]

    def _op(self, states, *controls, **kw):
        plan, problems = _hand_made([dict({'op': 'states', 'select': {'name': 'Display'},
                                           'states': states}, **kw)],
                                    *(controls or (DISPLAY,))).plan()
        return (plan['controls'][0] if plan['controls'] else None), problems

    def test_growing_names_writes_and_expects_every_state(self):
        op, problems = self._op(self.FOUR)
        self.assertEqual(problems, [])
        self.assertEqual(op['state_count'], 4)
        self.assertEqual([ps['fields']['nameField'] for ps in op['per_state']],
                         ['Off', 'Warming', 'On', 'Cooling'])
        # State 1 keeps On's look; state 3 starts as a copy of it.
        exp = op['expect_states']
        self.assertEqual(exp[2]['fill'], '#FF3D8BFD')
        self.assertEqual(exp[2]['text'], 'Display On')
        self.assertEqual(exp[3]['fill'], '#FF2E3040')
        self.assertEqual(exp[0]['text'], 'Display Off')

    def test_the_press_state_follows_its_state_or_is_named(self):
        # Display pressed to On (1); with Warming inserted, On is 2.
        op, _ = self._op(self.FOUR)
        self.assertEqual(op['fields'][PRESS], 2)
        op, _ = self._op(self.FOUR, press='Cooling')
        self.assertEqual(op['fields'][PRESS], 3)
        op, _ = self._op(['Only'])
        self.assertEqual(op['fields'][PRESS], 0)

    def test_a_state_keeps_its_identity_when_one_is_inserted_before_it(self):
        """The review's repro. Matched by position, inserting Middle before
        On left the press pointer on Middle, gave On the look of Extra, and
        every check passed - the plan itself was wrong."""
        extra = {'A': 255, 'R': 0x5A, 'G': 0x5C, 'B': 0x70}
        preset = _button('Display', [_st('Off', 'P', GREY), _st('On', 'P', BLUE),
                                     _st('Extra', 'P', extra)])
        op, problems = self._op(['Off', 'Middle', 'On'], preset)
        self.assertEqual(problems, [])
        self.assertEqual(op['state_order'], [0, 2, 1])
        self.assertEqual(op['fields'][PRESS], 2)
        self.assertEqual(op['expect_states'][2]['fill'], '#FF3D8BFD')

    def test_a_new_name_renames_the_state_in_its_place(self):
        op, _ = self._op(['Off', {'name': 'Live', 'fill': '#2266EE'}])
        self.assertEqual(op['state_order'], [0, 1])
        self.assertEqual(op['fields'][PRESS], 1)

    def test_states_can_be_reordered(self):
        op, _ = self._op(['On', 'Off'])
        self.assertEqual(op['state_order'], [1, 0])
        self.assertEqual(op['fields'][PRESS], 0)
        self.assertEqual(op['expect_states'][0]['text'], 'Display On')

    def test_a_dropped_press_state_goes_to_on(self):
        """A camera preset pressed to On_1; trimmed to Off/On it presses On."""
        preset = _button('Display', [_st('Off', '1', GREY), _st('On', '1', BLUE),
                                     _st('On_1', '1', NAVY)], press=2)
        op, _ = self._op(['Off', 'On'], preset)
        self.assertEqual(op['state_order'], [0, 1])
        self.assertEqual(op['fields'][PRESS], 1)

    def test_a_new_state_that_copies_the_last_unchanged_is_an_error(self):
        _, problems = self._op(['Off', 'On', 'Standby'])
        self.assertTrue(any("'On' and 'Standby' would look identical" in p
                            for p in problems), problems)

    def test_existing_states_are_not_compared(self):
        """Two existing states can differ in things this cannot see - an icon,
        a border - so only a copy is compared with what it was copied from."""
        same = _button('Display', [_st('Off', 'x', GREY), _st('On', 'x', GREY)])
        _, problems = self._op(['Off', 'On'], same)
        self.assertEqual(problems, [])

    def test_only_a_button_has_states(self):
        label = dict(DISPLAY, type='PBLabel')
        _, problems = self._op(['Off', 'On'], label)
        self.assertTrue(any('only a button' in p for p in problems), problems)

    def test_flagged_states_are_not_resized(self):
        _, problems = self._op(self.FOUR, dict(DISPLAY, state_flags=1))
        self.assertTrue(any('status flags' in p for p in problems), problems)

    def test_bad_states_are_refused_before_any_control(self):
        for states, needle in ((['Off', 'Off'], 'used twice'),
                               ([{'name': 'Off', 'border': 'x'}], 'unknown key'),
                               ([{'name': 'Off', 'fill': 'blue'}], 'not #RRGGBB'),
                               ([{'name': 'Off', 'text': None}], 'is null'),
                               ([{'fill': '#000000'}], 'has no name'),
                               ([], 'at least one')):
            _, problems = self._op(states)
            self.assertTrue(any(needle in p for p in problems), (states, problems))
        _, problems = self._op(['Off', 'On'], press='Standby')
        self.assertTrue(any('press' in p for p in problems), problems)

    def test_another_op_on_the_same_buttons_states_is_an_error(self):
        """Each op is planned against the file on disk, so a rename before a
        `states` op would make its expected captions wrong."""
        _, errors, _ = _hand_made([
            {'op': 'rename', 'map': {'Display On': 'Screen On'}},
            {'op': 'states', 'select': {'name': 'Display'}, 'states': self.FOUR}],
            DISPLAY).check()
        self.assertTrue(any('rename and states both change' in e for e in errors), errors)
        _, errors, _ = _hand_made([
            {'op': 'rename', 'map': {'Display On': 'Screen On'}},
            {'op': 'restyle', 'map': {'#3D8BFD': '#2266EE'}}], DISPLAY).check()
        self.assertEqual(errors, [])

    @needs_synthetic()
    def test_on_the_synthetic_fixture(self):
        """Grow a built two-state button to three; the new state starts as On."""
        plan, problems = _on_synthetic([{'op': 'states', 'select': {'page': 'Main', 'text': 'Alpha'},
                                         'states': ['Off', 'On', {'name': 'Fault',
                                                                  'fill': '#8B1E1E'}]}]).plan()
        self.assertEqual(problems, [])
        (op,) = plan['controls']
        self.assertEqual(op['was'], ['Off', 'On'])
        self.assertEqual(op['expect_states'][1]['fill'], '#FFD69B61')
        self.assertEqual(op['expect_states'][2]['fill'], '#FF8B1E1E')
        self.assertEqual(op['expect_states'][2]['text'], 'Alpha')



@needs_synthetic()
class TestARenamesWordsInItsBox(unittest.TestCase):
    """`gdl.edit check` warns where a rename's words would be cut in the
    control's box (Edits._caption_warnings, gdl.compose.caption_cuts): a
    rename writes words into a box sized for the old ones, and nothing
    else measured them - the field changes, and the panel shows 'Volum'.
    The synthetic fixture's NavAlpha is 317x62 at 20 pt."""

    def setUp(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; a caption is measured with gdl.compose')

    def check(self, new, **e):
        ed = _on_synthetic([dict({'op': 'rename', 'select': {'page': 'Main', 'name': 'NavAlpha'},
                                  'text': new}, **e)])
        plan, errors, warnings = ed.check()
        return [w for w in warnings if 'GUI Designer' in w], ed.notes

    def test_words_that_fit_say_nothing(self):
        self.assertEqual(self.check('Omega'), ([], []))

    def test_a_word_too_wide_for_the_box_is_warned_of(self):
        warned, notes = self.check('Supercalifragilisticexpialidocious')
        self.assertEqual(len(warned), 1, warned)
        self.assertIn("rename 'Main' 'NavAlpha': GUI Designer breaks 'Supercalifragilisticexpialidocious'", warned[0])
        self.assertIn('at 20 pt in Open Sans', warned[0])
        self.assertIn('give it room, or fewer words', warned[0])

    def test_words_whose_ink_the_box_cuts_are_warned_of(self):
        """Two lines of 20 pt in 62 px: both shown, the second's descenders
        a row past the box's foot, which GUI Designer cuts off there."""
        warned, notes = self.check('Display Display Display Display')
        self.assertEqual(len(warned), 1, warned)
        self.assertIn("rename 'Main' 'NavAlpha': its ink runs 1 px past the box's foot in 317x62", warned[0])
        self.assertIn('give it room, or fewer words', warned[0])
        self.assertEqual(notes, [])

    def test_a_retargets_box_is_the_one_measured(self):
        """Scaled to a smaller panel, a caption that fitted may not."""
        warned, _ = self.check('Omega Omega Omega')
        self.assertEqual(warned, [])
        ed = _on_synthetic([{'op': 'rename', 'select': {'page': 'Main', 'name': 'NavAlpha'},
                             'text': 'Omega Omega Omega'},
                            {'op': 'retarget', 'model': 'TLP725T', 'scale': True}])
        _, _, warnings = ed.check()
        self.assertTrue(any('NavAlpha' in w and 'GUI Designer' in w for w in warnings), warnings)

    def test_a_project_never_built_is_a_note(self):
        from unittest import mock
        with mock.patch('gdl.container.open_payload', side_effect=ValueError('no built payload')):
            warned, notes = self.check('Supercalifragilisticexpialidocious')
        self.assertEqual(warned, [])
        self.assertEqual(len(notes), 1, notes)
        self.assertIn('not measured', notes[0])
        self.assertIn('no built layout', notes[0])

    def test_without_pillow_it_is_a_note_and_check_runs(self):
        """PIL blocked at the import system, in a process of its own."""
        import json
        import subprocess
        code = '\n'.join((
            'import json, sys',
            'class NoPIL:',
            '    def find_spec(self, name, path=None, target=None):',
            "        if name == 'PIL' or name.startswith('PIL.'):",
            "            raise ImportError('no Pillow here')",
            'sys.meta_path.insert(0, NoPIL())',
            'from gdl.edit import Edits',
            "ed = Edits({'edits': [{'op': 'rename', 'select': {'page': 'Main', 'name': 'NavAlpha'},",
            "                       'text': 'Supercalifragilisticexpialidocious'}]}, sys.argv[1])",
            'plan, errors, warnings = ed.check()',
            "print(json.dumps({'errors': errors, 'warnings': warnings, 'notes': ed.notes,",
            "                  'ops': len(plan['controls']), 'pil': 'PIL' in sys.modules}))"))
        r = subprocess.run([sys.executable, '-c', code, SYNTHETIC], capture_output=True, text=True,
                           cwd=HERE, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertFalse(got['pil'], got)
        self.assertEqual((got['errors'], got['ops']), ([], 1), got)
        self.assertFalse([w for w in got['warnings'] if 'GUI Designer' in w], got)
        self.assertEqual(len(got['notes']), 1, got)
        self.assertIn('Pillow', got['notes'][0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
