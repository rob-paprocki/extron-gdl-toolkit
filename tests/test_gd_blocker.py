"""What powershell/GdlBlocker.ps1 must see, and where the scripts that drive
GUI Designer must ask it.

GUI Designer waits on a person behind some dialogs - its Application Licensing
window, asking for an Extron Insider login; the Save and Build Optimization
prompt the first build after an upgrade raises; its own error boxes - and from
outside, each looks like slow work. So a run sat out its whole timeout and then
said GUI Designer did not open the file, or sat idle.

The window tests put a stand-in up - a form with the dialog's title, off-screen,
in a process of its own - and point the check at that process, from both the
64-bit Windows PowerShell and the 32-bit one Wait-GdlBuild.ps1 runs in. What
finds GUI Designer by name runs against a stand-in under its name: a copy of
powershell.exe. They need Windows; the pins on where the scripts ask run
anywhere.
"""
import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCKER = os.path.join(REPO, 'powershell', 'GdlBlocker.ps1')
SEED = os.path.join(REPO, 'powershell', 'New-GdlSeed.ps1')
_WINDIR = os.environ.get('WINDIR', r'C:\Windows')
HOSTS = {name: path for name, path in (
    ('64-bit', os.path.join(_WINDIR, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')),
    ('32-bit', os.path.join(_WINDIR, 'SysWOW64', 'WindowsPowerShell', 'v1.0', 'powershell.exe')),
) if sys.platform == 'win32' and os.path.exists(path)}
# No console window for each PowerShell started: someone may be at this desktop.
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _read(*parts):
    with open(os.path.join(REPO, *parts), encoding='utf-8') as fh:
        return fh.read()


def _q(text):
    """`text` inside a single-quoted PowerShell string."""
    return text.replace("'", "''")


def _ask(host, call, pid):
    """The lines `call` prints about process `pid`'s windows, from `host`."""
    r = subprocess.run([host, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command',
                        f". '{_q(BLOCKER)}'; {call} -ProcessId {pid}"],
                       capture_output=True, text=True, timeout=180, creationflags=_NO_WINDOW)
    if r.returncode or r.stderr.strip():
        raise AssertionError(f'{call} failed in {host}: {r.stderr.strip() or r.returncode}')
    return [line for line in r.stdout.splitlines() if line.strip()]


def _ask_until(host, call, pid, seconds=30):
    """`_ask`, again until it prints something: a box the stand-in raises once
    it is up takes a moment to show."""
    deadline = time.time() + seconds
    while True:
        said = _ask(host, call, pid)
        if said or time.time() > deadline:
            return said
        time.sleep(0.5)


_FORM = """
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
{spin}$f = New-Object System.Windows.Forms.Form
$f.Text = '{title}'
$f.FormBorderStyle = 'FixedToolWindow'
$f.StartPosition = 'Manual'
$f.Location = New-Object System.Drawing.Point(-3000, -3000)
{label}$f.Add_Shown({{ [IO.File]::WriteAllText('{marker}', 'up'); {after} }})
[System.Windows.Forms.Application]::Run($f)
"""
# Kept off the taskbar as a tool window: ShowInTaskbar = $false would do it by
# giving the form a hidden owner, and an application's main window - GUI
# Designer's - has none. Run, not ShowDialog, for the same reason.
# A core kept busy beside the window, as a build keeps GUI Designer's.
_SPIN = '$spin = [PowerShell]::Create().AddScript({ while ($true) { } }); [void]$spin.BeginInvoke()\n'
# Text on the form, as the licensing window shows the user's e-mail address.
_LABEL = "$l = New-Object System.Windows.Forms.Label; $l.Text = '{text}'; $l.AutoSize = $true; $f.Controls.Add($l)\n"
# A message box the form owns, raised once the form is up.
_BOX = "[void][System.Windows.Forms.MessageBox]::Show($f, '{text}', '{caption}')"


@contextlib.contextmanager
def _window(title, exe=None, busy=False, label=None, after=''):
    """A visible top-level window titled `title`, off-screen, in a process of
    its own - `exe`, a PowerShell, the 64-bit one by default - busy or not,
    with a `label` on it, running `after` once it is up; yields the process's
    id once the window is."""
    with tempfile.TemporaryDirectory() as tmp:
        marker = os.path.join(tmp, 'up')
        script = _FORM.format(title=_q(title), marker=_q(marker), spin=_SPIN if busy else '',
                              label=_LABEL.format(text=_q(label)) if label else '', after=after)
        p = subprocess.Popen([exe or HOSTS['64-bit'], '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                              '-Command', script], creationflags=_NO_WINDOW)
        try:
            deadline = time.time() + 120
            while not os.path.exists(marker):
                if p.poll() is not None or time.time() > deadline:
                    raise AssertionError(f'the stand-in {title!r} never showed')
                time.sleep(0.5)
            yield p.pid
        finally:
            p.kill()
            p.wait(timeout=60)


def _box(text, caption):
    return _BOX.format(text=_q(text), caption=_q(caption))


@unittest.skipUnless('64-bit' in HOSTS, 'needs Windows PowerShell')
class TestWhatItSees(unittest.TestCase):
    def test_the_licensing_window_is_a_login_to_give(self):
        """And never what it says: it shows the user's e-mail address."""
        with _window('Application Licensing', label='You are logged in as: someone@example.com') as pid:
            for name, host in HOSTS.items():
                with self.subTest(host=name):
                    said = _ask(host, 'Get-GdlBlocker', pid)
                    self.assertEqual(len(said), 1, said)
                    self.assertIn('Extron Insider login', said[0])
                    self.assertNotIn('example.com', said[0])

    def test_the_upgrade_prompt_points_at_its_preference(self):
        with _window('Save and Build Optimization') as pid:
            for name, host in HOSTS.items():
                with self.subTest(host=name):
                    said = _ask(host, 'Get-GdlBlocker', pid)
                    self.assertEqual(len(said), 1, said)
                    self.assertIn('docs/from-scratch.md section 7', said[0])

    def test_an_error_box_stops_it_and_says_what_it_says(self):
        """What an unattended run has to report is what the box says."""
        for caption in ('GUI Designer Error', 'GUI Designer Application Error'):
            box = _box('Project Load Failed. Unable to open file at x.gdl.', caption)
            with self.subTest(caption=caption), _window('GUI Designer - [x.gdl]', after=box) as pid:
                for name, host in HOSTS.items():
                    with self.subTest(host=name):
                        said = _ask_until(host, 'Get-GdlBlocker', pid)
                        self.assertEqual(len(said), 1, said)
                        self.assertIn(caption, said[0])
                        self.assertIn('Project Load Failed. Unable to open file at x.gdl.', said[0])

    def test_another_window_is_said_but_blocks_nothing(self):
        """The Build Manager shows while a build runs; a wait that stopped on
        it would stop every build."""
        with _window('Build Manager') as pid:
            for name, host in HOSTS.items():
                with self.subTest(host=name):
                    self.assertEqual(_ask(host, 'Get-GdlBlocker', pid), [])
                    self.assertEqual(_ask(host, 'Get-GdlDialog', pid), ['Build Manager'])
                    # A sentence to append to one that ended, space and all.
                    self.assertEqual(_ask(host, 'Get-GdlShowing', pid), [" It shows 'Build Manager'."])

    def test_its_main_window_is_no_dialog(self):
        """Its main window has no owner and is titled 'GUI Designer', or 'GUI
        Designer - [project]'."""
        for title in ('GUI Designer', 'GUI Designer - [x.gdl]', 'GUI Designer - [x.gdl]*'):
            with self.subTest(title=title), _window(title) as pid:
                self.assertEqual(_ask(HOSTS['64-bit'], 'Get-GdlDialog', pid), [])
                self.assertEqual(_ask(HOSTS['64-bit'], 'Get-GdlShowing', pid), [])

    def test_its_own_windows_titled_for_it_are_dialogs(self):
        """Not every title that starts 'GUI Designer' is its main window: its
        error and start-option windows' do too."""
        for title in ('GUI Designer Error', 'GUI Designer Start Options'):
            with self.subTest(title=title), _window(title) as pid:
                self.assertEqual(_ask(HOSTS['64-bit'], 'Get-GdlDialog', pid), [title])

    def test_a_box_it_owns_is_a_dialog_whatever_its_caption(self):
        with _window('GUI Designer - [x.gdl]', after=_box('Saved.', 'GUI Designer')) as pid:
            self.assertEqual(_ask_until(HOSTS['64-bit'], 'Get-GdlDialog', pid), ['GUI Designer'])

    def test_the_wizard_in_place_of_a_file_is_said_to_be_a_refusal(self):
        """Only where a file was handed to it: the seed wizard's waits have the
        wizard up by design."""
        with _window('Project Create Wizard') as pid:
            said = _ask(HOSTS['64-bit'], 'Get-GdlShowing -Opening', pid)
            self.assertEqual(len(said), 1, said)
            self.assertIn("'Project Create Wizard'", said[0])
            self.assertIn('refused', said[0])
            self.assertEqual(_ask(HOSTS['64-bit'], 'Get-GdlShowing', pid), [" It shows 'Project Create Wizard'."])

    def test_a_file_not_opened_with_nothing_else_up_says_whether_it_runs(self):
        with _window('GUI Designer - [other.gdl]') as pid:
            self.assertEqual(_ask(HOSTS['64-bit'], 'Get-GdlShowing -Opening', pid),
                             [' It is running, with no other window up.'])
        self.assertEqual(_ask(HOSTS['64-bit'], 'Get-GdlShowing -Opening', pid), [' It is not running.'])


def _gd_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq GUI Designer.exe', '/NH'],
                       capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW)
    return 'GUI Designer.exe' in r.stdout


def _alive(pid, seconds=10):
    """Whether process `pid` is still there after up to `seconds` to go."""
    deadline = time.time() + seconds
    while True:
        r = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                           capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW)
        if str(pid) not in r.stdout:
            return False
        if time.time() > deadline:
            return True
        time.sleep(0.5)


class _StandIn(unittest.TestCase):
    """What finds GUI Designer by name, run against a copy of powershell.exe
    under its name. Never beside a real one: the build wait would watch it too,
    and the seed script's Stop-Gd closes every GUI Designer."""

    @classmethod
    def setUpClass(cls):
        if '64-bit' not in HOSTS or '32-bit' not in HOSTS:
            raise unittest.SkipTest('needs both Windows PowerShells')
        if _gd_running():
            raise unittest.SkipTest('GUI Designer is running')
        cls._tmp = tempfile.mkdtemp()
        cls.exe = os.path.join(cls._tmp, 'GUI Designer.exe')
        shutil.copyfile(HOSTS['64-bit'], cls.exe)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)


class TestTheBuildWait(_StandIn):
    """Wait-GdlBuild.ps1 itself, in the 32-bit PowerShell the pipelines run it
    in. Nothing in the wait is pointed at the stand-in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = os.path.join(cls._tmp, 'x.gdl')
        with open(cls.project, 'w', encoding='utf-8') as fh:
            fh.write('not built')

    def _wait(self, timeout, most):
        """The wait's exit code, what it printed, and how long it took."""
        t0 = time.time()
        r = subprocess.run([HOSTS['32-bit'], '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                            os.path.join(REPO, 'powershell', 'Wait-GdlBuild.ps1'), '-ProjectFile', self.project,
                            '-TimeoutSeconds', str(timeout), '-MaxSeconds', str(most)],
                           capture_output=True, text=True, timeout=most + 180, creationflags=_NO_WINDOW)
        return r.returncode, r.stdout + r.stderr, time.time() - t0

    def test_a_login_ends_it_at_once(self):
        with _window('Application Licensing', exe=self.exe):
            code, said, took = self._wait(timeout=30, most=60)
        self.assertEqual(code, 2, said)
        self.assertIn('Extron Insider login', said)
        self.assertLess(took, 30, said)

    def test_a_window_that_blocks_nothing_is_said_when_it_runs_out(self):
        with _window('Build Manager', exe=self.exe):
            code, said, _ = self._wait(timeout=8, most=30)
        self.assertEqual(code, 1, said)
        self.assertIn("It shows 'Build Manager'.", said)

    def test_busy_behind_a_login_it_waits_on(self):
        """A build may go on behind a dialog that came up during it; the wait
        gives up on a dialog only with GUI Designer idle behind it."""
        with _window('Application Licensing', exe=self.exe, busy=True):
            code, said, _ = self._wait(timeout=8, most=20)
        self.assertEqual(code, 1, said)
        self.assertNotIn('Extron Insider login', said)
        self.assertIn("It shows 'Application Licensing'.", said)


class TestTheSeedWizardsWait(_StandIn):
    """New-GdlSeed.ps1's own Wait-For, Stop-IfBlocked and Stop-Gd, taken out of
    the script by PowerShell's parser and called as the script calls them."""

    def test_a_login_ends_the_run_closing_gui_designer_and_cleaning_up(self):
        """Exit 5, GUI Designer closed, and what the wait was told to clean up
        cleaned - a Save As cut off by a dialog must not leave a file the next
        run refuses to overwrite. Said even through [void], as the script
        calls its first wait."""
        cleaned = os.path.join(self._tmp, 'cleaned')
        run = f"""
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{_q(SEED)}', [ref]$null, [ref]$null)
$wanted = 'Stop-Gd', 'Stop-IfBlocked', 'Wait-For'
foreach ($d in $ast.FindAll({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }}, $true)) {{
    if ($wanted -contains $d.Name) {{ . ([scriptblock]::Create($d.Extent.Text)) }}
}}
. '{_q(BLOCKER)}'
[void](Wait-For {{ $null }} 60 'the new project' {{ [IO.File]::WriteAllText('{_q(cleaned)}', 'cleaned') }})
'not stopped'
"""
        with _window('Application Licensing', exe=self.exe) as pid:
            r = subprocess.run([HOSTS['64-bit'], '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                '-Command', run], capture_output=True, text=True, timeout=240,
                               creationflags=_NO_WINDOW)
            alive = _alive(pid)
        said = r.stdout + r.stderr
        self.assertEqual(r.returncode, 5, said)
        self.assertIn('Extron Insider login', said)
        self.assertNotIn('not stopped', said)
        self.assertTrue(os.path.exists(cleaned), 'the cleanup did not run')
        self.assertFalse(alive, 'GUI Designer was left running')


def _block(text, start):
    """The statement that begins `start`, through its closing brace at the
    left margin."""
    i = text.index(start)
    return text[i:text.index('\n}', i) + 2]


_SOURCED = ". (Join-Path $PSScriptRoot 'GdlBlocker.ps1')"


class TestTheWaitsAsk(unittest.TestCase):
    """The waits on GUI Designer ask while they wait, so a dialog ends them
    with what to do, and one that runs out says what is on screen."""

    def test_the_build_wait_stops_on_one_while_nothing_is_written(self):
        """Only with GUI Designer idle behind it, as it is behind a modal that
        blocks: busy, it may be building still, and a wait that gave up then
        would throw a build away."""
        s = _read('powershell', 'Wait-GdlBuild.ps1')
        self.assertIn(_SOURCED, s)
        poll = s[s.index('    if (-not $written) {'):s.index('Start-Sleep -Seconds $PollSeconds')]
        self.assertRegex(poll, r'if \(-not \$busy\) \{\s*\n\s*\$why = Get-GdlBlocker\s*\n'
                               r'\s*if \(\$why\) \{ Write-Output "  \$why"; exit 2 \}')
        # Busy is this poll's, measured before the ask.
        self.assertIn('$busy = $false', poll)
        self.assertLess(poll.index('$busy = $true'), poll.index('Get-GdlBlocker'))
        self.assertIn('$(Get-GdlShowing)', s[s.index('$state = '):])

    def test_opening_a_panel_stops_on_one(self):
        s = _read('powershell', 'New-GdlPanel.ps1')
        self.assertIn(_SOURCED, s)
        step = s[s.index("Step 'open in GUI Designer'"):s.index("Step 'File > Save and Build'")]
        loop = step[step.index('do {'):step.index('} while')]
        self.assertIn('$why = Get-GdlBlocker\n', loop)
        self.assertIn('if ($why) { throw "GUI Designer did not open ${leaf}: $why" }', loop)
        self.assertIn('$(Get-GdlShowing -Opening)', step[step.index('} while'):])

    def test_opening_a_turned_seed_stops_on_one(self):
        s = _read('powershell', 'New-GdlTurnedSeed.ps1')
        self.assertIn(_SOURCED, s)
        step = s[s.index("Step 'open it in GUI Designer'"):s.index("Step 'File > Save and Build'")]
        loop = step[step.index('do {'):step.index('} while')]
        self.assertIn('$why = Get-GdlBlocker\n', loop)
        self.assertIn('if ($why) { Fail "GUI Designer did not open ${leaf}: $why" 5 }', loop)
        self.assertIn('$(Get-GdlShowing -Opening)', step[step.index('} while'):])

    def test_the_seed_wizards_long_waits_stop_on_one(self):
        """Wait-For, GUI Designer's own wizard, and the menu bar after Create -
        the waits of a minute and more."""
        s = _read('powershell', 'New-GdlSeed.ps1')
        self.assertIn(_SOURCED, s)
        stop = _block(s, 'function Stop-IfBlocked(')
        self.assertIn('$why = Get-GdlBlocker\n', stop)
        wait = _block(s, 'function Wait-For(')
        self.assertIn('Stop-IfBlocked $cleanup', wait)
        self.assertIn('$(Get-GdlShowing)', wait)
        own = s[s.index('while (-not (Get-Wizard) -and'):]
        self.assertIn('Stop-IfBlocked', own[:own.index('\n}')])
        menu = s[s.index('while (((Get-Date) - $t0).TotalSeconds -lt 180) {'):]
        self.assertIn('Stop-IfBlocked', menu[:menu.index('\n}')])
        # Its exit codes say what 5 now covers.
        self.assertIn('waits on a person', s[:s.index('#>')])


if __name__ == '__main__':
    unittest.main()
