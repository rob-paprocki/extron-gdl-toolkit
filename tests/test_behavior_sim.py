"""The generated program, run: import it against a fake extronlib and press things.

The program cannot run here for real - extronlib exists only on a control
processor - so tests/fake_extronlib stands in for it, and enforces the
ControlScript reference's contracts rather than accepting anything: event
names per class, handler arity, Held/Repeated only with holdTime, pages and
popups by name. A generator that emits a wrong event name or a page number
fails here.

What this cannot prove is that Global Scripter imports the program or that it
runs on a processor. docs/behavior.md says so too.

    python tests/test_behavior_sim.py
"""
import ast
import io
import json
import os
import shutil
import sys
import tempfile
import tokenize
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from gdl.behavior import load  # noqa: E402

FAKE = os.path.join(HERE, 'fake_extronlib')
EXAMPLE = os.path.join(REPO, 'examples', 'huddle-program.json')
GENERATED = ('ui_objects.py', 'ui_events.py', 'ui_feedback.py')
PROGRAM_MODULES = ('ui_objects', 'ui_events', 'ui_feedback', 'devices', 'main')


def _purge():
    for m in list(sys.modules):
        if m in PROGRAM_MODULES or m == 'extronlib' or m.startswith('extronlib.'):
            del sys.modules[m]


class Sim(unittest.TestCase):
    """Generate a spec's program into a temp dir and import it."""

    SPEC = EXAMPLE

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.prog = load(self.SPEC)
        problems, _ = self.prog.check()
        self.assertEqual(problems, [], problems)
        _, drift = self.prog.generate(self.dir)
        self.assertEqual(drift, [])
        _purge()
        sys.path[:0] = [self.dir, FAKE]
        import extronlib
        extronlib.reset()
        self.x = extronlib
        import ui_events
        import ui_objects
        import ui_feedback
        self.ev, self.ui, self.fb = ui_events, ui_objects, ui_feedback
        del extronlib.JOURNAL[:]

    def tearDown(self):
        for p in (self.dir, FAKE):
            while p in sys.path:
                sys.path.remove(p)
        _purge()
        shutil.rmtree(self.dir, ignore_errors=True)

    def obj(self, uid):
        return getattr(self.ui, self.prog.names()[uid])

    def by_name(self, name):
        r = next(r for r in self.prog.controls if r['name'] == name)
        return self.obj(r['id'])

    def journal(self, *methods):
        return [e for e in self.x.JOURNAL if not methods or e[1] in methods]

    def device_calls(self):
        return [e[2] for e in self.x.JOURNAL if e[0] == 'ProgramLog' and 'stub:' in e[2]]


class TestHuddle(Sim):
    def test_online_shows_the_start_page(self):
        self.x.fire(self.ui.TLP, 'Online', 'Online')
        self.assertIn(('HuddleTLP', 'ShowPage', 'Huddle Home'), self.journal('ShowPage'))

    def test_the_inactivity_time_is_set_at_start(self):
        self.assertEqual(self.ui.TLP.InactivityTime, [600])

    def test_end_call_asks_and_calls_nothing(self):
        self.by_name('EndCall').fire('Pressed')
        self.assertEqual(self.journal('ShowPopup'),
                         [('HuddleTLP', 'ShowPopup', 'Confirm End Call', 0)])
        self.assertEqual(self.device_calls(), [])

    def test_confirm_hangs_up_then_closes(self):
        self.by_name('ConfirmEnd').fire('Pressed')
        seq = [e for e in self.x.JOURNAL if e[1] == 'HidePopup' or e[0] == 'ProgramLog']
        self.assertIn('stub: codec.hang_up()', seq[0][2])
        self.assertEqual(seq[1], ('HuddleTLP', 'HidePopup', 'Confirm End Call'))

    def test_cancel_only_closes(self):
        self.by_name('CancelEnd').fire('Pressed')
        self.assertEqual(self.device_calls(), [])
        self.assertEqual(self.journal('HidePopup'),
                         [('HuddleTLP', 'HidePopup', 'Confirm End Call')])

    def test_a_source_press_selects_it_alone_and_routes_it(self):
        laptop, wireless, pc = (self.by_name(n) for n in ('Laptop', 'Wireless', 'RoomPC'))
        wireless.fire('Pressed')
        laptop.fire('Pressed')
        self.assertEqual((laptop.State, wireless.State, pc.State), (1, 0, 0))
        self.assertIn("stub: switcher.route(source='laptop')", self.device_calls())

    def test_volume_steps_on_press_and_on_repeat(self):
        down = self.by_name('VolDown')
        down.fire('Pressed')
        down.fire('Repeated')
        self.assertEqual(self.device_calls(), ['stub: dsp.step_volume(db=-2)'] * 2)

    def test_the_slider_passes_its_value(self):
        self.by_name('VolumeSlider').fire('Changed', 42)
        self.assertEqual(self.device_calls(), ['stub: dsp.set_volume(value=42)'])

    def test_feedback_setters_reach_their_controls(self):
        self.fb.audio_muted(True)
        self.fb.audio_volume(35)
        self.fb.call_status('In a call')
        self.assertEqual(self.by_name('Mute').State, 1)
        self.assertEqual(self.by_name('VolumeSlider').Fill, 35)
        self.assertIn(('Label({0})'.format(self.prog.control(
            next(r['id'] for r in self.prog.controls if r['name'] == 'CallState'))['id']),
            'SetText', 'In a call'), self.journal('SetText'))

    def test_inactivity_hides_popups_then_goes_home(self):
        self.x.fire(self.ui.TLP, 'InactivityChanged', 600.0)
        self.assertEqual([e[1] for e in self.journal('HideAllPopups', 'ShowPage')],
                         ['HideAllPopups', 'ShowPage'])
        self.assertEqual(self.journal('ShowPage')[-1][2], 'Huddle Home')

    def test_the_runtime_graph_is_the_static_graph(self):
        """Walk the panel as a user would - from the start page, press every
        button on every page and popup reached - and compare the pages and
        popups actually shown with what the checks reasoned about."""
        seen, todo, observed = set(), [self.prog.start_page], set()
        while todo:
            here = todo.pop()
            if here in seen:
                continue
            seen.add(here)
            for r in self.prog.controls:
                if r['container'] != here or r['kind'] not in ('button', 'slider'):
                    continue
                o = self.obj(r['id'])
                for event in r['events']:
                    del self.x.JOURNAL[:]
                    if r['kind'] == 'slider':
                        o.fire(event, 50)
                    else:
                        o.fire(event)
                    for e in self.journal('ShowPage', 'ShowPopup'):
                        observed.add((here, e[2]))
                        todo.append(e[2])
        self.assertEqual(observed, self.prog.nav_edges())
        self.assertEqual(seen, {ct['name'] for ct in self.prog.containers})


class TestProgramShape(unittest.TestCase):
    """The generated files must run on a processor still on Python 3.5, and
    under ControlScript's module and builtin restrictions."""

    FORBIDDEN_BUILTINS = {'compile', 'dir', 'eval', 'exec', 'exit', 'globals', 'help',
                          'input', 'locals', 'open', 'quit', 'vars'}
    OWN = {'devices', 'ui_objects', 'ui_events', 'ui_feedback'}

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        load(EXAMPLE).generate(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def files(self):
        return [os.path.join(self.dir, f) for f in GENERATED + ('devices.py', 'main.py')]

    def test_no_syntax_newer_than_python_3_5(self):
        for path in self.files():
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            tree = ast.parse(src)
            for node in ast.walk(tree):
                bad = type(node).__name__ in ('JoinedStr', 'NamedExpr', 'AnnAssign', 'Match')
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    bad = bad or node.returns is not None or any(
                        a.annotation is not None for a in node.args.args)
                self.assertFalse(bad, f'{os.path.basename(path)}: {type(node).__name__} '
                                      f'needs Python > 3.5')
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                self.assertNotEqual(tokenize.tok_name.get(tok.type), 'FSTRING_START',
                                    f'{os.path.basename(path)}: f-string')

    def test_imports_only_extronlib_and_the_programs_own_modules(self):
        for path in self.files():
            with open(path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module]
                for n in names:
                    self.assertTrue(n.split('.')[0] == 'extronlib' or n in self.OWN,
                                    f'{os.path.basename(path)} imports {n}')

    def test_no_builtin_controlscript_forbids(self):
        for path in self.files():
            with open(path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, self.FORBIDDEN_BUILTINS,
                                     os.path.basename(path))

    def test_no_page_or_popup_is_ever_addressed_by_number(self):
        with open(os.path.join(self.dir, 'ui_events.py'), encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and \
                    node.func.attr in ('ShowPage', 'ShowPopup', 'HidePopup'):
                arg = node.args[0]
                self.assertFalse(isinstance(arg, ast.Constant) and isinstance(arg.value, int))


class TestRegeneration(unittest.TestCase):
    """devices.py and main.py are the programmer's: never overwritten."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.prog = load(EXAMPLE)
        self.prog.generate(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_hand_edits_to_devices_survive_regeneration(self):
        path = os.path.join(self.dir, 'devices.py')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n# my own code\n')
        self.prog.generate(self.dir)
        with open(path, encoding='utf-8') as fh:
            self.assertIn('# my own code', fh.read())

    def test_generated_files_are_rewritten(self):
        path = os.path.join(self.dir, 'ui_events.py')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n# hand edit that must not survive\n')
        self.prog.generate(self.dir)
        with open(path, encoding='utf-8') as fh:
            self.assertNotIn('hand edit', fh.read())

    def test_an_op_missing_from_devices_is_reported_with_a_stub(self):
        path = os.path.join(self.dir, 'devices.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(src.replace('def hang_up(', 'def hang_up_old('))
        _, drift = self.prog.generate(self.dir)
        self.assertTrue(any('hang_up' in d and 'def hang_up(self)' in d for d in drift), drift)

    def test_a_missing_argument_is_reported(self):
        path = os.path.join(self.dir, 'devices.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(src.replace('def route(self, source=None)', 'def route(self)'))
        _, drift = self.prog.generate(self.dir)
        self.assertTrue(any('route' in d and 'source' in d for d in drift), drift)


class TestHandoff(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        load(EXAMPLE).generate(self.dir)
        with open(os.path.join(self.dir, 'handoff.json'), encoding='utf-8') as fh:
            self.h = json.load(fh)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_pages_carry_no_number(self):
        # Build does not keep a page's number, so a handoff that listed one
        # would hand the programmer an address that does not exist.
        for pg in self.h['pages'] + self.h['popups']:
            self.assertNotIn('number', pg)

    def test_every_addressable_control_is_listed_once(self):
        ids = [c['id'] for c in self.h['controls']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 22)

    def test_the_costly_call_is_marked(self):
        confirm = next(c for c in self.h['controls'] if c['at'][0]['name'] == 'ConfirmEnd')
        self.assertIn('codec.hang_up() [costly]', confirm['events']['Pressed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
