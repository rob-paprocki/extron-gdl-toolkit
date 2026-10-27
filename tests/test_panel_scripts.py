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


    def test_a_family_is_read_off_its_resource_not_stripped_from_its_name(self):
        """'Arial Rounded MT Bold' read as Arial Rounded MT when every trailing
        style word was stripped: both places the applier matches a family read
        the resource's own family field, as Project.font_resource_names does."""
        script = _read('GdlApply.ps1')
        helper = script.split('function Get-GdlFontFamily', 1)[1].split('\nfunction ', 1)[0]
        self.assertIn("'windowsFamilyNameField'", helper)
        rest = script.replace(helper, '')
        self.assertEqual(rest.count('Get-GdlFontFamily'), 3, 'the helper, and the two matches')
        self.assertNotIn('(Regular|Bold|Italic)', rest)


class TestThePlanKnowsItsDonor(unittest.TestCase):
    def test_the_plan_is_written_against_the_donor(self):
        """A border the donor lacks is built as the donor's own nearest only
        when the plan is told which donor (gdl.spec plan --donor)."""
        self.assertRegex(_read('New-GdlPanel.ps1'),
                         r"'plan', \$Spec, \$plan, '--donor', \$Donor")


class TestAPlanProblemStopsTheApply(unittest.TestCase):
    """Only Apply-GdlEdits used Note-Fatal, so a hand-run of Apply-GdlPlan on a
    plan whose binding failed or whose donor had nothing to clone wrote the
    file anyway, and only verify_built after a build said so."""

    def test_each_plan_problem_is_fatal_and_the_file_is_not_written(self):
        script = _read('Apply-GdlPlan.ps1')
        for what in ('to clone - cannot author', 'returned null', ') failed:',
                     "default_page '", 'which was never registered', 'has no PopupPageID',
                     'to clone for back-pointers', 'is not correctly bound',
                     'does not make as a standard popup', 'Offline Page cannot be switched',
                     "to say the plan's words on", 'so it cannot be replaced'):
            line = next(ln for ln in script.splitlines() if what in ln)
            self.assertIn('Note-Fatal', line, what)
        stop = script.index('if ($script:Fatal.Count) {')
        self.assertLess(stop, script.index('if ($WhatIf) {\n    Write-Output'))
        self.assertLess(stop, script.index('Save-GdlProject $project $Output'))
        self.assertIn('exit 1', script[stop:stop + 600])

    def test_a_font_or_border_the_donor_lacks_stays_a_warning(self):
        """Built as the donor's nearest, and said by `gdl.spec donors`."""
        self.assertNotIn('Note-Fatal', _read('GdlApply.ps1').split('function Add-GdlFontResource', 1)[1])


class TestAReferenceBoundToOnePopup(unittest.TestCase):
    """Nine seeds show their ungrouped Volume Level through references bound
    to it by its ID: PopupID the popup's, GroupID 0, its name beside it, and
    back-pointers on the popup as a group reference's. IsPopupPageIdValid is
    PopupID != MaxValue, read off GUI Designer's IL - no field of its own."""

    def _bind(self):
        script = _read('Apply-GdlPlan.ps1')
        m = re.search(r"if \(\$r\.Popup\) \{(.*?)\n            continue\n        \}", script, re.S)
        self.assertIsNotNone(m)
        return script, m.group(1)

    def test_a_reference_naming_a_popup_waits_for_it(self):
        script = _read('Apply-GdlPlan.ps1')
        self.assertIn("-eq 'PBPopupPageReference' -and ($op.group -or $op.popup)", script)
        self.assertIn('Popup = $op.popup', script)

    def test_it_is_bound_to_the_id_of_the_popup_the_plan_made(self):
        script, body = self._bind()
        self.assertIn('$made | Where-Object { $_.Name -eq $r.Popup -and -not $_.Modal }', body)
        self.assertIn("Set-GdlFieldIfPresent $binding 'popupIDField' ([uint64]$target[0].Id)", body)
        self.assertIn("Set-GdlFieldIfPresent $binding 'groupIDField' 0", body)
        self.assertIn("Set-GdlFieldIfPresent $binding 'popupNameField' $r.Popup", body)
        # After the popups are made, which is what gives them their ids.
        self.assertLess(script.index('$made += [pscustomobject]'), script.index('if ($r.Popup) {'))

    def test_its_popup_is_written_in_no_group(self):
        """Group 0 and an empty name, as the seeds' Volume Level. The first
        build of one stopped the applier: the popup's group id was looked up
        in the plan's groups by a null name."""
        script = _read('Apply-GdlPlan.ps1')
        m = re.search(r"\} elseif \(-not \$pu\.group\) \{(.*?)\n        \} else \{", script, re.S)
        self.assertIsNotNone(m)
        self.assertIn("Set-GdlFieldIfPresent $popup 'groupIDField' 0", m.group(1))
        self.assertIn("Set-GdlFieldIfPresent $popup 'groupNameField' ''", m.group(1))
        self.assertLess(m.start(), script.index("([int]$groupIds[$pu.group])"))

    def test_its_popup_points_back_at_the_references_bound_to_it(self):
        script = _read('Apply-GdlPlan.ps1')
        self.assertIn('else { $script:PendingRefs | Where-Object { $_.Popup -eq $m.Name } }', script)

    def test_the_binding_test_takes_an_ungrouped_popup_with_its_references(self):
        body = _read('GdlProject.ps1').split('function Test-GdlPopupBinding', 1)[1]
        self.assertNotIn("'standard popup has no group'", body)
        self.assertIn("'standard popup has no group and no reference bound to it'", body)
        self.assertRegex(body, r"-not \$popup\.Modal -and \$grp -eq 0 -and -not \$byId")
        # A reference bound to it by ID names it, and no group.
        self.assertIn("Get-GdlField $id 'popupNameField'", body)
        self.assertIn('[int]$id.GroupID -ne 0', body)


class TestAPopupsTimeout(unittest.TestCase):
    def test_the_applier_writes_the_plans_timeout_on_every_popup(self):
        """PBPopupPage.timeoutField, a UInt32, 0 on every seed popup: written
        so a clone never keeps its donor's. Nothing in GUI Designer reads it
        (docs/gdl-format.md section 7)."""
        script = _read('Apply-GdlPlan.ps1')
        self.assertIn("Set-GdlFieldIfPresent $popup 'timeoutField' ([uint32]$pu.timeout)", script)
        self.assertLess(script.index("'timeoutField'"), script.index('$pops.Add($popup)'))


class TestTheOfflinePage(unittest.TestCase):
    """The donor's own Offline Page (popup 65535), kept whole: the plan
    switches it and replaces words on it."""

    def _block(self):
        script = _read('Apply-GdlPlan.ps1')
        start = script.index('if ($spec.offline) {')
        return script, script[start:script.index('# -- the donor', start)]

    def test_the_switch_is_the_projects_field(self):
        _, body = self._block()
        self.assertIn("Set-GdlFieldIfPresent $project 'enableOfflineField' ([bool]$spec.offline.enabled)",
                      body)
        self.assertIn('if ($null -ne $spec.offline.enabled)', body)

    def test_words_are_replaced_literally_wherever_a_caption_lives(self):
        """String.Replace is ordinal; -replace would read 'XXX.XXX.XXXX' as a
        regex, its dots matching any character."""
        _, body = self._block()
        self.assertIn('.Replace([string]$r.old, [string]$r.new)', body)
        self.assertNotIn('-replace', body)
        self.assertIn("foreach ($f in 'textField', 'ftextField')", body)
        self.assertIn('Get-GdlStates $c', body)

    def test_it_is_applied_before_the_project_is_saved(self):
        script, _ = self._block()
        self.assertLess(script.index('if ($spec.offline) {'), script.index('if ($script:Fatal.Count) {'))


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
