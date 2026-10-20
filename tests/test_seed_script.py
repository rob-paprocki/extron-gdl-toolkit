"""What New-GdlSeed.ps1 must not do again.

It cannot run without a desktop and GUI Designer, so these read it: each pins
one thing that was wrong and would have cost a seed, or put a screenshot of
someone's screen beside the seeds where `git add` finds it.
"""
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(REPO, *parts), encoding='utf-8') as fh:
        return fh.read()


SCRIPT = _read('powershell', 'New-GdlSeed.ps1')


class TestSeedScript(unittest.TestCase):
    def test_a_relative_output_is_relative_to_where_the_shell_is(self):
        """[IO.Path]::GetFullPath uses the process's own directory, which `cd`
        does not change in Windows PowerShell: run in a shell started elsewhere,
        seeds\\X.gdl landed beside wherever that was."""
        self.assertNotIn('GetFullPath($Output)', SCRIPT)
        # Assigned, not merely called: the resolved path is what is used.
        self.assertRegex(SCRIPT, r'\$Output = \$ExecutionContext\.SessionState\.Path\.'
                                 r'GetUnresolvedProviderPathFromPSPath\(\$Output\)')

    def test_a_save_as_that_never_finishes_leaves_no_file_to_refuse_the_next_run(self):
        self.assertRegex(SCRIPT, r'function Wait-For\([^)]*\[scriptblock\]\$cleanup\)')
        self.assertRegex(SCRIPT, r'& \$cleanup \}\s*\n\s*exit 5')
        # And the Save As wait is the one given a cleanup that removes the file.
        self.assertRegex(SCRIPT, r'\} 120 \$Output \{\s*\n\s*if \(Test-Path -LiteralPath \$Output\) \{'
                                 r'\s*\n\s*try \{ Remove-Item -LiteralPath \$Output')

    def test_the_wizard_screenshot_is_not_kept_beside_the_seed(self):
        """It is of the whole primary screen, and seeds/ is where `git add` looks."""
        self.assertNotIn('GetDirectoryName($Output)', SCRIPT)
        self.assertRegex(SCRIPT, r"\$shotDir = if \(\$env:CLAUDE_JOB_DIR\) \{ Join-Path \$env:CLAUDE_JOB_DIR 'tmp' \}"
                                 r' else \{ \[System\.IO\.Path\]::GetTempPath\(\) \}')
        self.assertRegex(SCRIPT, r'\$shot = Join-Path \$shotDir ')

    def test_a_copy_of_it_in_seeds_is_ignored_anyway(self):
        self.assertIn('seeds/*-wizard.png', _read('.gitignore').splitlines())

    def test_a_panel_type_below_the_open_list_is_scrolled_into_view_first(self):
        """'TLP Pro 1525TG', 46th of the wizard's 56 panel types, lies below the
        dropdown's rows: clicked where it was drawn, the click missed the list
        and the combo still read 'Select Your Panel'."""
        pick = SCRIPT[SCRIPT.index('function Select-ComboItem'):SCRIPT.index('function Select-Resolution')]
        self.assertIn('ScrollItemPattern', pick)
        self.assertIn('ScrollIntoView', pick)
        self.assertLess(pick.index('ScrollIntoView'), pick.index('Invoke-Click'))

    def test_an_item_with_no_rectangle_is_off_not_an_error(self):
        """An item scrolled out of a virtualised list can have an empty
        rectangle, whose infinities [int] refuses: its point is computed only
        from a rectangle it has, and it is read as off, to scroll into view."""
        items = SCRIPT[SCRIPT.index('function Get-Items'):SCRIPT.index('function Close-Combo')]
        self.assertRegex(items, r'if \(-not \$r\.IsEmpty\) \{ \$x = \[int\]')
        self.assertNotRegex(items, r'\n\s*\$x = \[int\]')

    def test_the_verifier_is_told_the_theme(self):
        self.assertRegex(SCRIPT, r"verify_seed\.py'\) \$Output \$Model \$Theme")


def _block(text, start):
    """The statement that begins `start`, through its closing brace at the
    left margin."""
    i = text.index(start)
    return text[i:text.index('\n}', i) + 2]


class TestASeedIsWaitedFor(unittest.TestCase):
    """New-GdlSeed.ps1 threw away a Mach 725 seed three times. Create, updating
    the Mach 1020 template's references, outlasted a 180 s wait twice; then,
    the seed saved, GUI Designer was Not Responding - a hung window shows UI
    Automation no menu - so its one try at Save and Build found none, and the
    seed was deleted as one that did not build (archive/job-2419a20b/seeds/)."""

    def setUp(self):
        self.build = SCRIPT[SCRIPT.index('# -- build it'):]

    def test_the_new_project_is_waited_for_minutes_but_not_after_gui_designer_is_gone(self):
        """Turbulence's 720 template outlasted 900 s behind Please Wait, with
        tests running beside it."""
        m = re.search(r"\}\s*(\d+)\s*'the new project'", SCRIPT)
        self.assertGreaterEqual(int(m.group(1)), 1800)
        create = SCRIPT[SCRIPT.index("Click-Named 'Create'"):m.end()]
        self.assertIn("if (-not $p) { return 'gone' }", create)
        self.assertRegex(SCRIPT[m.end():], r"^\s*if \(\$proc -is \[string\]\) \{")

    def test_the_build_waits_for_an_answer_and_says_whether_it_came(self):
        loop = _block(self.build, 'while (((Get-Date) - $t1).TotalSeconds -lt 300) {')
        self.assertIn('if ($p.Responding) { $answered = $true; break }', loop)
        self.assertIn('if (-not $p) { break }', loop)
        self.assertRegex(self.build, r'if \(\$answered\) \{ Write-Output \("  answering after')
        self.assertIn('did not answer within', self.build)
        # The baseline is taken once it answers: the write it was busy with is
        # not the build's.
        self.assertLess(self.build.index('if ($p.Responding)'), self.build.index('$buildFrom ='))

    def test_save_and_build_is_tried_again_only_where_no_click_landed(self):
        """Invoke-GdlMenu.ps1 exits 0 once the item is clicked, a blocked
        invoke included, so a retry follows only a click that did not land -
        never a second build."""
        loop = _block(self.build, 'for ($try = 1; ')
        self.assertIn("'Save and Build'", loop)
        self.assertIn('if ($LASTEXITCODE -eq 0) { break }', loop)
        self.assertGreaterEqual(int(re.search(r'\$try -le (\d+)', loop).group(1)), 3)


class TestATurnedSeedScript(unittest.TestCase):
    """New-GdlTurnedSeed.ps1 makes the seed the wizard cannot - a panel turned
    where its theme draws no template that way up - from its own seed turned."""

    def setUp(self):
        self.script = _read('powershell', 'New-GdlTurnedSeed.ps1')

    def test_its_paths_are_where_the_shell_is(self):
        for p in ('From', 'Output'):
            self.assertIn(f'${p} = $ExecutionContext.SessionState.Path.'
                          f'GetUnresolvedProviderPathFromPSPath(${p})', self.script)
        self.assertNotIn('GetFullPath($', self.script)

    def test_the_turn_is_a_scaled_retarget_written_without_a_bom(self):
        """gdl.edit reads its spec as UTF-8, and json refuses a byte-order mark,
        which Windows PowerShell's Set-Content -Encoding UTF8 writes."""
        self.assertIn("op = 'retarget'; model = $Model; size = $size; scale = $true", self.script)
        self.assertIn('New-Object System.Text.UTF8Encoding $false', self.script)
        self.assertNotIn('Set-Content', self.script)

    def test_it_is_applied_by_the_32_bit_host_and_waited_for_from_before_the_click(self):
        self.assertRegex(self.script, r"& \$ps32 [^\n]*Apply-GdlEdits\.ps1")
        self.assertLess(self.script.index('$buildFrom ='), self.script.index("-Item 'Save and Build'"))

    def test_a_turn_refused_leaves_the_users_gui_designer_alone(self):
        """Fail closes GUI Designer only once the open step has taken it over."""
        fail = self.script[self.script.index('function Fail'):]
        fail = fail[:fail.index('\n}') + 2]
        self.assertRegex(fail, r'if \(\$script:gdOurs\) \{\s*Get-Process -Name .GUI Designer.')
        opened = self.script.index("Step 'open it in GUI Designer'")
        self.assertLess(opened, self.script.index('$gdOurs = $true'))
        self.assertLess(self.script.index("Fail 'the turn was refused' 3"), opened)

    def test_a_seed_that_does_not_verify_is_removed(self):
        self.assertRegex(self.script, r"verify_seed\.py'\) \$Output \$Model")
        self.assertIn('if ($code -ne 0) { Fail', self.script)
        self.assertRegex(self.script, r'function Fail[\s\S]*Remove-Item -LiteralPath \$Output')


if __name__ == '__main__':
    unittest.main()
