"""What New-GdlPanel.ps1 and New-GdlPanels.ps1 must not do.

They cannot run without a desktop and GUI Designer, so these read them.
"""
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(REPO, 'powershell', name), encoding='utf-8') as fh:
        return fh.read()


class TestPathsAreTheShells(unittest.TestCase):
    """[IO.Path]::GetFullPath resolves against the process's own directory,
    which `cd` does not move in Windows PowerShell: in a shell started in the
    home folder and then pointed at the repo, -Output out\\x\\Huddle.gdl built
    the panel under the home folder. New-GdlSeed.ps1 had the same bug."""

    def test_a_panels_paths_are_relative_to_where_the_shell_is(self):
        script = _read('New-GdlPanel.ps1')
        for param in ('Output', 'Work', 'IdMap'):
            self.assertNotRegex(script, rf'GetFullPath\(\${param}\)', param)
            self.assertIn(f'GetUnresolvedProviderPathFromPSPath(${param})', script, param)

    def test_every_path_is_resolved_before_the_script_moves_to_the_repo(self):
        """Push-Location moves the shell's location, which is what the
        resolution reads: -IdMap resolved after it landed under the repo while
        -Output, resolved before it, landed where the shell was."""
        script = _read('New-GdlPanel.ps1')
        push = re.search(r'(?m)^\s*Push-Location \$repo\s*$', script).start()
        for m in re.finditer(r'GetUnresolvedProviderPathFromPSPath\(\$(\w+)\)', script):
            self.assertLess(m.start(), push, f'-{m.group(1)} is resolved after Push-Location')

    def test_a_project_is_opened_and_saved_where_the_shell_says(self):
        """Apply-GdlPlan.ps1 and Apply-GdlEdits.ps1 hand their -Output and
        project paths to these, and [IO.File] resolves against the process."""
        script = _read('GdlProject.ps1')
        for fn in ('Open-GdlProject', 'Save-GdlProject'):
            body = script[script.index(f'function {fn}'):]
            body = body[:body.index('\n}')]
            self.assertIn('GetUnresolvedProviderPathFromPSPath($Path)', body, fn)

    def test_a_panel_sets_out_folder_is_relative_to_where_the_shell_is(self):
        script = _read('New-GdlPanels.ps1')
        self.assertNotRegex(script, r'GetFullPath\(\$Out\)')
        self.assertIn('GetUnresolvedProviderPathFromPSPath($Out)', script)

    def test_no_entry_point_resolves_a_parameter_against_the_process(self):
        for name in sorted(os.listdir(os.path.join(REPO, 'powershell'))):
            if not name.endswith('.ps1'):
                continue
            script = _read(name)
            params = re.search(r'(?ms)^param\((.*?)^\)', script)
            for p in re.findall(r'\[string\]\$(\w+)', params.group(1) if params else ''):
                self.assertNotRegex(script, rf'GetFullPath\(\${p}\)', f'{name} -{p}')


if __name__ == '__main__':
    unittest.main()
