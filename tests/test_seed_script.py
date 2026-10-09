"""What New-GdlSeed.ps1 must not do again.

It cannot run without a desktop and GUI Designer, so these read it: each pins
one thing that was wrong and would have cost a seed, or put a screenshot of
someone's screen beside the seeds where `git add` finds it.
"""
import os
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

    def test_the_verifier_is_told_the_theme(self):
        self.assertRegex(SCRIPT, r"verify_seed\.py'\) \$Output \$Model \$Theme")


if __name__ == '__main__':
    unittest.main()
