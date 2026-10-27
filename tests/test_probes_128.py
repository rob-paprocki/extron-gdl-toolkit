"""The format probes of examples/probes-128/, as far as they can be tested
without GUI Designer.

The runner drives GUI Designer and the reader reads what a Windows host sends
back, so neither runs here. What is pinned: every input the runner names is
there and checks, plans and finds its donor; the border table is the probe it
says it is; the runner parses and keeps the conventions the other scripts
keep; and the reader runs on an empty folder, a half-finished one and a
synthetic Build Manager dump without falling over - the day a result comes
back it must not be the reader that fails.

Pillow is not needed at import: what draws with it skips without.

    python tests/test_probes_128.py
"""
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import seed, usable  # noqa: E402

from gdl import design  # noqa: E402
from gdl.spec import BORDER_GEOMETRY, Panel, border_shape, mirrors  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(REPO, 'examples', 'probes-128')
RUNNER = os.path.join(PROBES, 'Run-Probes128.ps1')
RUNTIME = os.environ.get('GDL_DC_RUNTIME')


def _load(name):
    """A module of examples/probes-128 by file name; the folder's name has a
    hyphen, so it cannot be imported as a package."""
    spec = importlib.util.spec_from_file_location(name[:-3].replace('-', '_'), os.path.join(PROBES, name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(*parts):
    with open(os.path.join(PROBES, *parts), encoding='utf-8') as fh:
        return fh.read()


def _runner_inputs():
    """{key: path} of the runner's `$In` table."""
    body = re.search(r'\$In = \[ordered\]@\{(.*?)\n\}', _read('Run-Probes128.ps1'), re.S).group(1)
    return dict(re.findall(r"(\w+)\s*=\s*'([^']+)'", body))


def _runner_probes():
    m = re.search(r'\$Probes = @\((.*?)\)', _read('Run-Probes128.ps1'), re.S)
    return re.findall(r"'([\w-]+)'", m.group(1))


SPECS = {  # spec -> the seed it is built on
    'afterburn-borders.json': 'Afterburn 1035.gdl',
    'afterburn-groups.json': 'Afterburn 1035.gdl',
    'shockwave-hslider.json': 'Shockwave 1035.gdl',
    'shockwave-1535-twins.json': 'Shockwave 1535.gdl',
}


# The specs whose images are Extron's kit art, which is in neither git nor a
# CI runner (vendor/README.md): checked and planned only where the kit is.
KIT_ART = {'shockwave-hslider.json': ('shockwave', 'thumbs'),
           'shockwave-1535-twins.json': ('shockwave', 'root')}


def _kit_here(name):
    if name not in KIT_ART:
        return True
    from gdl import designsys
    theme, part = KIT_ART[name]
    return bool(designsys.kit_root(designsys.load(theme), part))


class TestTheInputs(unittest.TestCase):
    def test_every_path_the_runner_names_is_in_the_repo(self):
        for key, rel in _runner_inputs().items():
            if key == 'FormatFixtureSeed':
                continue
            path = os.path.join(REPO, *rel.split('\\'))
            # A seed is Git LFS: a pointer file is there, and is enough to name.
            self.assertTrue(os.path.exists(path), f'{key}: {rel}')

    def test_every_spec_checks(self):
        for name in SPECS:
            if not _kit_here(name):
                continue
            panel = Panel.load(os.path.join(PROBES, 'specs', name))
            self.assertEqual(panel.check(), [], name)

    def test_every_spec_plans_against_its_donor(self):
        for name, donor in SPECS.items():
            if not _kit_here(name):
                continue
            if not usable(seed(donor)):
                self.skipTest(f'needs seeds/{donor}')
            spec = os.path.join(PROBES, 'specs', name)
            out = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, out, True)
            for cmd in (['donors', spec, seed(donor)], ['plan', spec, os.path.join(out, 'plan.json'), '--donor', seed(donor)]):
                r = subprocess.run([sys.executable, '-B', '-m', 'gdl.spec'] + cmd, cwd=REPO,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f'{name} {cmd[0]}: {r.stdout[-400:]}{r.stderr[-400:]}')

    def test_a_translated_spec_names_its_donor_and_the_runner_hands_it_over(self):
        """A translated spec has no `family` for `gdl.seeds pick`, so the runner
        names the donor itself - and it must be the one the spec was made for."""
        spec = json.loads(_read('specs', 'shockwave-1535-twins.json'))
        donor = _runner_inputs()['TwinDonor'].replace('\\', '/')
        self.assertEqual(spec['_seed'], donor)
        self.assertEqual(spec['model'], 'TLP1535M',
                         "the seed is the 1535M's: no region canvas can list a TLP1535T until one is made")

    def test_the_1535_canvas_lists_only_the_1535m(self):
        panels = set()
        for f in os.listdir(os.path.join(PROBES, 'canvas-1535')):
            if f.endswith('.dc.html'):
                panels |= set(re.findall(r'panels="([^"]*)"', _read('canvas-1535', f)))
        self.assertEqual(panels, {'TLP1535M'})

    def test_the_1535_spec_holds_the_tab_twins(self):
        """What the probe is for: a caption-only button sharing a tab's ID on
        one page - the spec's mirrors."""
        spec = json.loads(_read('specs', 'shockwave-1535-twins.json'))
        main = next(p for p in spec['pages'] if p['name'] == 'Main')
        inside = mirrors(main['controls'])
        twins = [c for c in main['controls'] if id(c) in inside]
        self.assertEqual(len(twins), 4)
        for t in twins:
            tab = [c for c in main['controls'] if c.get('id') == t['id'] and c is not t][0]
            self.assertIsNone(tab.get('text'), 'the tab draws no caption; its twin says the name')
            self.assertTrue(t['text'])

    def test_the_slider_probe_is_horizontal_with_a_thumb_that_is_not_square(self):
        spec = json.loads(_read('specs', 'shockwave-hslider.json'))
        sliders = {c['name']: c for p in spec['pages'] for c in p['controls']}
        horizontal = [c for c in sliders.values() if c['orientation'] in ('right', 'left')]
        self.assertEqual({c['orientation'] for c in horizontal}, {'right', 'left'})
        for c in sliders.values():
            self.assertNotEqual(c['thumb'], c['thumb_height'], c['name'])
        self.assertTrue(any(c['orientation'] == 'up' for c in sliders.values()), 'the vertical control')

    def test_the_groups_probe_has_groups_of_different_sizes(self):
        spec = json.loads(_read('specs', 'afterburn-groups.json'))
        sizes = {}
        for p in spec['popups']:
            sizes[p['group']] = sizes.get(p['group'], 0) + 1
        self.assertEqual(sorted(sizes.values()), [1, 3, 5])
        counts = re.search(r"'-Counts', '([^']+)'", _read('Run-Probes128.ps1')).group(1)
        self.assertEqual(sorted(k for k, _ in (p.split('=') for p in counts.split(';'))), sorted(sizes))
        written = {k: int(v) for k, v in (p.split('=') for p in counts.split(';'))}
        for g, members in sizes.items():
            self.assertNotEqual(written[g], members, f'{g}: a count equal to its members proves nothing')
            self.assertNotEqual(written[g], 2, f'{g}: 2 is what the applier writes')


class TestTheBorderTable(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads(_read('borders.json'))['rows']

    def test_every_row_is_a_panel_of_the_spec(self):
        spec = json.loads(_read('specs', 'afterburn-borders.json'))
        names = {c['name'] for p in spec['pages'] for c in p['controls']}
        self.assertEqual({r['control'] for r in self.rows}, names)

    def test_a_resource_name_says_the_geometry_the_row_does(self):
        for r in self.rows:
            self.assertEqual(border_shape(r['resource']), ('2d', r['radius'], r['thickness']), r['resource'])

    def test_one_row_is_the_corpus_and_the_rest_are_not(self):
        inside = [r for r in self.rows if r['resource'] in BORDER_GEOMETRY]
        self.assertEqual([r['in_corpus'] for r in self.rows].count(True), 1)
        self.assertEqual([r['resource'] for r in inside], ['Afterburn - 10 Radius 2 Thick'])

    def test_no_out_of_corpus_row_is_in_the_afterburn_seed(self):
        if not usable(seed('Afterburn 1035.gdl')):
            self.skipTest('needs seeds/Afterburn 1035.gdl')
        from gdl.project import Project
        have = Project.open(seed('Afterburn 1035.gdl')).border_resource_names()
        for r in self.rows:
            self.assertEqual(r['resource'] in have, r['in_corpus'], r['resource'])

    def test_the_plan_is_rebound_to_the_resources(self):
        if not usable(seed('Afterburn 1035.gdl')):
            self.skipTest('needs seeds/Afterburn 1035.gdl')
        tools = _load('probe_tools.py')
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        plan, bound = os.path.join(out, 'plan.json'), os.path.join(out, 'bound.json')
        r = subprocess.run([sys.executable, '-B', '-m', 'gdl.spec', 'plan',
                            os.path.join(PROBES, 'specs', 'afterburn-borders.json'), plan,
                            '--donor', seed('Afterburn 1035.gdl')], cwd=REPO, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(tools.bind_borders(plan, os.path.join(PROBES, 'borders.json'), bound), len(self.rows))
        with open(bound, encoding='utf-8') as fh:
            got = {op['fields']['nameField']: op['border'] for op in json.load(fh)['pages'][0]['controls']}
        self.assertEqual(got, {r['control']: r['resource'] for r in self.rows})

    def test_a_row_the_plan_lacks_is_refused_not_skipped(self):
        tools = _load('probe_tools.py')
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        plan = os.path.join(out, 'plan.json')
        with open(plan, 'w', encoding='utf-8') as fh:
            json.dump({'pages': [{'name': 'P', 'controls': [{'fields': {'nameField': 'Other'}}]}]}, fh)
        with self.assertRaises(SystemExit):
            tools.bind_borders(plan, os.path.join(PROBES, 'borders.json'), os.path.join(out, 'x.json'))


class TestTheEdits(unittest.TestCase):
    def test_the_seed_renumber_checks_clean_against_the_seed(self):
        if not usable(seed('Afterburn 1035.gdl')):
            self.skipTest('needs seeds/Afterburn 1035.gdl')
        from gdl.edit import Edits
        with open(os.path.join(PROBES, 'renumber-seed.json'), encoding='utf-8') as fh:
            edits = json.load(fh)
        plan, errors, warnings = Edits(edits, seed('Afterburn 1035.gdl')).check()
        self.assertEqual((errors, warnings), ([], []))
        self.assertTrue(plan['controls'])
        # The mirror: one ID on two popups, both taking the one new ID.
        mirror = [o for o in plan['controls'] if o['was'] == 5465]
        self.assertEqual(len({o['page'] for o in mirror}), 2)
        self.assertEqual(len({o['fields']['userIdField'] for o in mirror}), 1)

    def test_the_generated_panels_renumber_names_pages_its_spec_has(self):
        with open(os.path.join(PROBES, 'renumber-generated.json'), encoding='utf-8') as fh:
            edits = json.load(fh)['edits']
        with open(os.path.join(REPO, 'examples', 'huddle-functions.json'), encoding='utf-8') as fh:
            spec = json.load(fh)
        names = {p['name'] for p in spec['pages']} | {p['name'] for p in spec.get('popups') or []}
        for e in edits:
            self.assertEqual(e['op'], 'renumber')
            self.assertIn(e['select']['page'], names)
        taken = {c['id'] for p in spec['pages'] + spec.get('popups', []) for c in p['controls'] if c.get('id')}
        for e in edits:
            self.assertNotIn(e['start'], taken)


class TestTheRunner(unittest.TestCase):
    def test_it_parses(self):
        pwsh = shutil.which('pwsh')
        if not pwsh:
            self.skipTest('needs pwsh for its parser')
        for f in sorted(os.listdir(PROBES)):
            if not f.endswith('.ps1'):
                continue
            script = ('$e = $null; $t = $null; '
                      '[System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$t, [ref]$e) | Out-Null; '
                      '$e | ForEach-Object { "$($_.Extent.StartLineNumber): $($_.Message)" }')
            r = subprocess.run([pwsh, '-NoProfile', '-Command', script, os.path.join(PROBES, f)],
                               capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), '', f)

    def test_every_script_is_ascii(self):
        """Windows PowerShell 5.1 reads a script without a byte order mark as
        the ANSI code page."""
        for f in os.listdir(PROBES):
            if f.endswith('.ps1'):
                _read(f).encode('ascii')

    def test_the_probes_it_runs_are_the_ones_the_reader_and_the_readme_name(self):
        probes = _runner_probes()
        reader = _load('read_probes.py')
        self.assertEqual(probes, reader.PROBES)
        self.assertEqual(sorted(reader.READERS), sorted(probes))
        readme = _read('README.md')
        for p in probes:
            self.assertIn(f'`{p}`', readme, p)
        for key, rel in _runner_inputs().items():
            if key != 'FormatFixtureSeed':
                self.assertIn(rel.replace('\\', '/').rsplit('/', 1)[-1], readme, rel)

    def test_it_keeps_the_scripts_conventions(self):
        s = _read('Run-Probes128.ps1')
        self.assertIn(r'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe', s)
        for script in ('New-GdlPanel.ps1', 'Apply-GdlEdits.ps1', 'Apply-GdlPlan.ps1', 'Invoke-GdlMenu.ps1',
                       'Wait-GdlBuild.ps1', 'GdlBlocker.ps1', 'Send-GdlKeys.ps1'):
            self.assertIn(script, s)
            self.assertTrue(os.path.exists(os.path.join(REPO, 'powershell', script)), script)
        # New-FormatProbes.ps1 is run by its path from the inputs table.
        self.assertIn('FormatProbes', s)
        # The build is waited for by the file, with the baseline taken first.
        self.assertRegex(s, r"-Since', \$from")
        self.assertLess(s.index('$from = (Get-Item $gdl).LastWriteTime'), s.index("'Save and Build'"))
        # One GUI Designer at a time: it is stopped before each is opened.
        self.assertRegex(s, r'Stop-GuiDesigner\n\s+\$watch = Start-Watcher')
        # 5.1 has neither.
        for token in ('??', '?.', ' && ', ' || '):
            self.assertNotIn(token, s)

    def test_a_failed_probe_does_not_end_the_run(self):
        s = _read('Run-Probes128.ps1')
        loop = s[s.index('foreach ($name in $Probes)'):]
        self.assertRegex(loop, r'try \{\s+switch \(\$name\)')
        self.assertIn("$status = 'FAILED'", loop)
        self.assertIn('Write-Summary', loop)

    def test_it_clears_nothing_outside_its_scratch_folder(self):
        s = _read('Run-Probes128.ps1')
        self.assertIn("StartsWith($Work, 'OrdinalIgnoreCase')", s)
        self.assertEqual(len(re.findall(r'Remove-Item', s)), 2)   # the stop file, and the guarded extract folder


class TestTheReader(unittest.TestCase):
    def setUp(self):
        self.reader = _load('read_probes.py')
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def run_reader(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.reader.main(['read_probes.py'] + list(argv))
        return code, buf.getvalue()

    def test_an_empty_folder_and_a_missing_one_are_said_not_crashed_on(self):
        for d in (self.dir, os.path.join(self.dir, 'nope')):
            code, text = self.run_reader(d)
            self.assertEqual(code, 0)
            self.assertIn('no probe folder', text)

    def test_a_probe_folder_with_nothing_in_it_is_read_without_failing(self):
        for n in self.reader.PROBES:
            os.makedirs(os.path.join(self.dir, n))
        code, text = self.run_reader(self.dir)
        self.assertEqual(code, 0)
        for n in self.reader.PROBES:
            self.assertIn(f'== {n}', text)
        self.assertNotIn('reader failed', text)

    def test_it_reads_the_build_managers_counts_off_a_dump(self):
        d = os.path.join(self.dir, 'borders', 'buildmgr-borders')
        os.makedirs(d)
        with open(os.path.join(d, 'windows.log'), 'w', encoding='utf-8') as fh:
            fh.write("10:00:00.100  appeared  'Build Manager'  class=X handle=0x1 rect=0,0,1,1  owned=True\n")
        with open(os.path.join(d, 'dump-Build-Manager-100001-01.txt'), 'w', encoding='utf-8') as fh:
            fh.write('# x\n## WM_GETTEXT\n Static 0x2 Build finished: 0 errors, 3 warnings\n'
                     '## UI Automation\nText | Warnings: 3 | \n')
        code, text = self.run_reader(self.dir, 'borders')
        self.assertEqual(code, 0)
        self.assertIn("'Build Manager'", text)
        self.assertIn('0 error(s)', text)
        self.assertIn('3 warning(s)', text)

    def test_a_stack_trace_in_a_dump_is_not_a_count(self):
        """The watcher's own UI Automation failure, dumped beside the window:
        its "Int32 errorCode" read as 32 errors on every 1.28 build."""
        d = os.path.join(self.dir, 'borders', 'buildmgr-borders')
        os.makedirs(d)
        with open(os.path.join(d, 'windows.log'), 'w', encoding='utf-8') as fh:
            fh.write("10:00:00.100  appeared  'Wait...'  class=X handle=0x1 rect=0,0,1,1  owned=True\n")
        with open(os.path.join(d, 'dump-Wait-100001-01.txt'), 'w', encoding='utf-8') as fh:
            fh.write('# x\n## WM_GETTEXT\n WindowsForms10.STATIC.app.0 0x2 Please wait while the project is being saved\n'
                     '## UI Automation\n (UI Automation walk failed: "Unrecognized error.")\n'
                     '   at MS.Internal.Automation.Misc.ThrowWin32ExceptionsIfError(Int32 errorCode)\n')
        _, text = self.run_reader(self.dir, 'borders')
        self.assertNotIn('32 error', text)
        self.assertIn('Wait: no count in the text', text)

    def test_it_prints_what_the_build_manager_said(self):
        """On 1.28 a clean build's Build Manager says its phase and no count,
        so the phases are the readout."""
        d = os.path.join(self.dir, 'borders', 'buildmgr-borders')
        os.makedirs(d)
        with open(os.path.join(d, 'windows.log'), 'w', encoding='utf-8') as fh:
            fh.write("10:00:00.100  appeared  'Build Manager'  class=X handle=0x1 rect=0,0,1,1  owned=True\n")
        for n, (stamp, said) in enumerate((('100001', 'Building Platform ...'),
                                           ('100017', 'Validating Popup Page References ...')), 1):
            with open(os.path.join(d, f'dump-Build-Manager-{stamp}-0{n}.txt'), 'w', encoding='utf-8') as fh:
                fh.write(f'# x\n## WM_GETTEXT\n WindowsForms10.BUTTON.app.0 0x3 Cancel\n'
                         f' WindowsForms10.STATIC.app.0 0x2 {said}\n')
        _, text = self.run_reader(self.dir, 'borders')
        self.assertIn('Build-Manager said: Building Platform ... / Validating Popup Page References ...', text)
        self.assertIn('Build-Manager: no count in the text', text)

    def test_it_says_where_to_look_when_the_watcher_saw_no_window(self):
        d = os.path.join(self.dir, 'borders', 'buildmgr-borders')
        os.makedirs(d)
        open(os.path.join(d, 'windows.log'), 'w').close()
        _, text = self.run_reader(self.dir, 'borders')
        self.assertIn('nothing to read', text)

    def test_the_log_lines_that_say_how_a_build_went_are_kept(self):
        d = os.path.join(self.dir, 'twins-1535')
        os.makedirs(d)
        with open(os.path.join(d, 'probe.log'), 'w', encoding='utf-8') as fh:
            fh.write('10:00:00  noise\n10:00:01      12 check(s) on 56 authored control(s) against the build, 0 problem(s)\n')
        _, text = self.run_reader(self.dir, 'twins-1535')
        self.assertIn('0 problem(s)', text)
        self.assertNotIn('noise', text)

    def test_a_corner_is_measured_off_the_artwork(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('needs Pillow')
        for radius, thickness in ((20, 3), (40, 6), (0, 9)):
            fill, stroke = {'A': 255, 'R': 46, 'G': 49, 'B': 66}, {'A': 255, 'R': 255, 'G': 212, 'B': 0}
            img = Image.new('RGBA', (360, 260), (0, 0, 0, 0))
            from gdl.compose import draw_fill
            draw_fill(img, (0, 0, 360, 260), {'fill': fill, 'stroke': stroke,
                                              'border': {'radius': radius, 'thickness': thickness}})
            r, s, _ = self.reader.measure_corner(img)
            self.assertAlmostEqual(r, radius, delta=2, msg=(radius, thickness))
            self.assertEqual(s, thickness, (radius, thickness))
            self.assertLess(self.reader.preview_diff(img, 360, 260, fill, stroke, radius, thickness), 0.001)
            if radius:
                self.assertGreater(self.reader.preview_diff(img, 360, 260, fill, stroke, radius + 20, thickness), 0.001)

    def test_a_rail_is_measured_off_the_artwork(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('needs Pillow')
        im = Image.new('RGBA', (300, 40), (0, 0, 0, 0))
        im.paste((255, 255, 255, 255), (17, 10, 283, 30))
        buf = io.BytesIO()
        im.save(buf, 'PNG')
        size, box = self.reader.bbox_of(buf.getvalue())
        self.assertEqual((size, box), ((300, 40), (17, 10, 283, 30)))


@unittest.skipUnless(RUNTIME and os.path.exists(RUNTIME) and design.find_chrome(),
                     'needs headless Chrome and $GDL_DC_RUNTIME (the Design type runtime)')
class TestTheTranslation(unittest.TestCase):
    def test_the_checked_in_spec_is_what_the_canvas_translates_to(self):
        tools = _load('probe_tools.py')
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        with redirect_stdout(io.StringIO()):
            code = tools.translate(os.path.join(PROBES, 'canvas-1535'), 'shockwave', out)
        self.assertEqual(code, 0)
        with open(os.path.join(out, 'TLP1535M', 'spec.json'), encoding='utf-8') as fh:
            made = json.load(fh)
        self.assertEqual(made, json.loads(_read('specs', 'shockwave-1535-twins.json')))


if __name__ == '__main__':
    unittest.main()
