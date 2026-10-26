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

    def test_a_folder_handed_to_python_loses_its_trailing_backslash(self):
        """Tab completion ends a folder with a backslash, which escapes the
        closing quote Windows PowerShell 5.1 puts round an argument with a
        space in it: the folder and every argument after it arrive as one."""
        for name, params in (('New-GdlPanels.ps1', ('Out', 'Previous')), ('New-GdlPanel.ps1', ('IdMap', 'Previous'))):
            script = _read(name)
            for p in params:
                self.assertIn(f"GetUnresolvedProviderPathFromPSPath(${p}).TrimEnd('\\')", script, f'{name} -{p}')

    def test_no_entry_point_resolves_a_parameter_against_the_process(self):
        for name in sorted(os.listdir(os.path.join(REPO, 'powershell'))):
            if not name.endswith('.ps1'):
                continue
            script = _read(name)
            params = re.search(r'(?ms)^param\((.*?)^\)', script)
            for p in re.findall(r'\[string\]\$(\w+)', params.group(1) if params else ''):
                self.assertNotRegex(script, rf'GetFullPath\(\${p}\)', f'{name} -{p}')


class TestARevisionPassesThePreviousMap(unittest.TestCase):
    """A revised canvas translated with --previous keeps the IDs the previous
    delivery's map gave; the map written for the build is diffed against that
    map into changes.md, so both scripts hand -Previous to gdl.idmap - resolved
    where the shell is, before the script moves to the repo."""

    def check(self, name, command):
        script = _read(name)
        self.assertRegex(re.search(r'(?ms)^param\((.*?)^\)', script).group(1), r'\[string\]\$Previous\b', name)
        # Trimmed as -Out is: a trailing backslash, which tab completion adds
        # to a folder, escapes the closing quote Windows PowerShell 5.1 puts
        # round an argument with a space in it.
        resolve = script.index("GetUnresolvedProviderPathFromPSPath($Previous).TrimEnd('\\')")
        self.assertLess(resolve, re.search(r'(?m)^\s*Push-Location \$repo\s*$', script).start(), name)
        # Always an array: `if` hands back an empty @() as $null, which `+`
        # appends as an empty argument.
        self.assertIn("$prev = @(if ($Previous) { '--previous', $Previous })", script, name)
        self.assertRegex(script, command, name)

    def test_every_panel(self):
        self.check('New-GdlPanels.ps1', r"& \$Python -m gdl\.idmap write-panels \$Out \$map @prev")

    def test_one_panel(self):
        self.check('New-GdlPanel.ps1', r"Run \$Python \(@\('-m', 'gdl\.idmap', 'write', \$Spec, \$IdMap\) \+ \$prev\)")


class TestAPanelKeepsNoDonorsChecksum(unittest.TestCase):
    def test_the_applier_clears_the_donors_checksum_before_it_saves(self):
        """A seed built with Gd Generate Checksum on carries a CRC of its own
        metadata (docs/from-scratch.md section 7). Cloned, a panel would ship
        that stale value; cleared, its own build writes its own, or none."""
        script = _read('Apply-GdlPlan.ps1')
        self.assertRegex(script, r"Set-GdlField \$project 'checksum' ")
        self.assertLess(script.index("'checksum'"), script.index('Save-GdlProject $project'))


class TestAFaceThePlanBringsIsAppended(unittest.TestCase):
    def test_the_applier_appends_the_plans_fonts_before_any_control(self):
        """Set-GdlFont binds a control to a family only if the project has a
        resource for it, so the faces go in first."""
        script = _read('Apply-GdlPlan.ps1')
        append = script.index('Add-GdlFontResource $project $f')
        self.assertLess(append, script.index('$madePages = New-Object'))
        self.assertIn('function Add-GdlFontResource', _read('GdlApply.ps1'))

    def test_the_appended_resource_is_recorded_as_its_carrier_records_it(self):
        """Every field the plan's entry carries is written: a clone left with
        the donor's own value - its first resource's author - says nothing."""
        body = _read('GdlApply.ps1').split('function Add-GdlFontResource', 1)[1]
        body = body.split('\nfunction ', 1)[0]
        for field in ('windowsFamilyNameField', 'windowsStyleNameField', 'embeddedFileNameField',
                      'filenameField', 'sizeField', 'dataField', 'mIsDefault', 'authorField'):
            self.assertRegex(body, rf"Set-GdlField \$new '{field}'", field)


class TestThePlanKnowsItsDonor(unittest.TestCase):
    def test_the_plan_is_written_against_the_donor(self):
        """A border the donor lacks is built as the donor's own nearest only
        when the plan is told which donor (gdl.spec plan --donor)."""
        self.assertRegex(_read('New-GdlPanel.ps1'),
                         r"'plan', \$Spec, \$plan, '--donor', \$Donor")


class TestALevelKeepsItsArt(unittest.TestCase):
    def test_a_level_drawn_from_art_keeps_its_empty_track(self):
        """A clone's background image is cleared - but a level whose donor
        draws it from art (the plan's `keep_art`: Shockwave's, Turbulence's)
        keeps it, as it is the empty bar; cleared, the hubs' levels built a
        plain block where the seed's own draw it."""
        script = _read('Apply-GdlPlan.ps1')
        self.assertRegex(script, r"if \(-not \$op\.keep_art\) \{\s*Set-GdlFieldIfPresent \$c "
                                 r"'backgroundImageField' \$null")


class TestAModalIsGivenItsScrim(unittest.TestCase):
    def test_the_applier_writes_the_plans_transparency_on_a_modal(self):
        """Build draws a modal black at its own transparency, and a clone kept
        its donor modal's - 0, opaque, on the client's archived Incoming
        modals - while every canvas draws 35%."""
        script = _read('Apply-GdlPlan.ps1')
        m = re.search(r"if \(\$pu\.modal\) \{(.*?)\n        \}", script, re.S)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1), r"Set-GdlFieldIfPresent \$popup 'transparencyField' "
                                     r"\(\[double\]\$pu\.transparency\)")


class TestAnImageDrawsItsArt(unittest.TestCase):
    """A PBImage draws its art from its backgroundImageField - every one in
    the Turbulence seeds - which a clone is cleared of with every control's;
    buttonImageField is a button's. Laid out Stretch (1) as the seeds' bars
    are, Fill (0) as their device pictures are."""

    def _block(self, script, test):
        m = re.search(r"if \(" + re.escape(test) + r"\) \{(.*?)\n\s*\}", script, re.S)
        self.assertIsNotNone(m, test)
        return m

    def test_an_image_is_given_the_plans_art_after_the_clones_is_cleared(self):
        script = _read('Apply-GdlPlan.ps1')
        m = self._block(script, "$op.donor_type -eq 'PBImage' -and $op.image")
        self.assertLess(script.index("Set-GdlFieldIfPresent $c 'backgroundImageField' $null"), m.start())
        body = m.group(1)
        self.assertIn("Set-GdlImage $c 'backgroundImageField' $imageRef (Get-PlanImageName $op.image.name)", body)
        self.assertIn("'backgroundImageLayoutField' ([int]$op.image_layout)", body)
        self.assertIn("'backgroundImageAlignmentField' ([int]$op.image_align)", body)
        self.assertNotIn('buttonImageField', body)

    def test_a_popup_is_given_its_photo_after_the_donors_is_cleared(self):
        script = _read('Apply-GdlPlan.ps1')
        m = self._block(script, '$pu.background_image')
        self.assertLess(script.index("Set-GdlFieldIfPresent $popup 'backgroundImageField' $null"), m.start())
        body = m.group(1)
        self.assertIn("Set-GdlImage $popup 'backgroundImageField' $imageRef "
                      "(Get-PlanImageName $pu.background_image.name)", body)
        self.assertIn("'backgroundImageLayoutField' ([int]$pu.background_layout)", body)


if __name__ == '__main__':
    unittest.main()
