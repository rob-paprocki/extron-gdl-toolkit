<#
    Apply a build plan from `python -m gdl.spec plan` to a donor ProjectGCP.

    MUST be run under 32-bit Windows PowerShell 5.1:
      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe

      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass `
        -File powershell\Apply-GdlPlan.ps1 out\ProjectGCP plan.json out\new_ProjectGCP

    Verified end to end against GUI Designer 1.27.0.9: pages, popups, popup
    groups and bindings all survive open + Save and Build. What it cannot tell
    you is whether the RESULT is right - Build silently relocates and rewrites
    things - so always finish with

        python tests/verify_built.py <plan.json> <built.gdl>

    which is the gate that catches what a clean build does not report.

    It is deliberately thin. Every decision - layout, ids, colors, which donor
    to clone - was made in Python, where it is testable; this only applies ops.
    That is why the interesting logic is in gdl/spec.py and not here.

    It is also deliberately self-diagnosing: -WhatIf resolves every donor and
    every field WITHOUT mutating anything, and unknown fields are reported and
    skipped rather than thrown on, so the first real run produces a punch list
    instead of one stack trace.

    Everything here follows the rules in docs/gdl-format.md:
      * clone, never construct (section 4)
      * write backing fields, never properties (section 4)
      * a popup binding lives in four places (section 6). This script DOES
        author popups, and every one is asserted with Test-GdlPopupBinding
        before the project is saved - a mismatch there opens and builds fine
        and simply reads "Unassigned", so trusting the writes is not enough.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$DonorProject,
    [Parameter(Mandatory)][string]$Plan,
    [string]$Output,
    [switch]$WhatIf,
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'GdlProject.ps1')

. (Join-Path $PSScriptRoot 'GdlApply.ps1')

$script:PendingRefs = @()

function Add-GdlControls {
    <#  Apply every clone-control op onto a page or popup.

        Pages and popups take the SAME path deliberately - built separately,
        one of them silently loses a fix the other gets. #>
    param($Project, $Controls, $Ops, $PageId, [switch]$DryRun)
    foreach ($op in $Ops) {
        $donor = Get-GdlDonor $Project $op.donor_type
        if (-not $donor) {
            Note-Problem "donor project has no $($op.donor_type) to clone - cannot author '$($op.fields.nameField)'"
            continue
        }
        $c = Copy-GdlObject $donor
        if ($null -eq $c) {
            Note-Problem "clone of $($op.donor_type) returned null (donor was $(if($null -eq $donor){'null'}else{$donor.GetType().Name}))"
            continue
        }
        # Fault-isolate per control: one bad op should name itself, not kill the
        # run anonymously. That is the whole point of the dry run.
        try {
            foreach ($f in $op.fields.PSObject.Properties) {
                Set-GdlFieldIfPresent $c $f.Name $f.Value | Out-Null
            }
            Set-GdlColor $Project $c 'borderFillColorField' $op.fill
            Set-GdlColor $Project $c 'borderColorField' $op.stroke
            Set-GdlColor $Project $c 'textColorField' $op.text_color
            # flattenText bakes the caption INTO the artwork at build time, and a
        # clone inherits the donor's. Build then dedupes every generated button
        # to one asset carrying the donor's word. Captions must be drawn live
        # from layout.json, which is what the panel firmware does anyway.
        Set-GdlFieldIfPresent $c 'flattenTextField' $false | Out-Null
        Set-GdlFieldIfPresent $c 'buttonImageField' $null | Out-Null
        Set-GdlFieldIfPresent $c 'backgroundImageField' $null | Out-Null
        Set-GdlBorder $Project $c $op.border
            Set-GdlFieldIfPresent $c 'textAlignmentField' $op.alignment | Out-Null

            # A button renders from its STATE, not from the control: layout.json's
            # reader takes state[0]'s text/font/color in preference. Mirror the
            # caption onto every state or the button builds blank.
            # Index rather than foreach: PBStates is a collection object that
            # supports .Count and [i], but enumerating it yields the collection
            # itself, so foreach would silently write to the wrong thing.
            $states = Get-GdlField $c 'statesField'
            $script:StateWrites = 0
            if ($states -and $states.Count) {
                for ($si = 0; $si -lt $states.Count; $si++) {
                    $st = $states[$si]
                    # A shape/label reports a non-zero Count on an empty states
                    # collection and then indexes to null, so check rather than
                    # trusting Count.
                    if ($null -eq $st) { continue }
                    $script:StateWrites++
                    # The donor's own caption and icon ride along on a clone, so
                    # a state that is not rewritten renders the donor's text.
                    Set-GdlFieldIfPresent $st 'buttonImageField' $null | Out-Null
                    Set-GdlFieldIfPresent $st 'textField' $op.fields.textField | Out-Null
                    Set-GdlFieldIfPresent $st 'textAlignmentField' $op.alignment | Out-Null
                    Set-GdlColor $Project $st 'textColorField' $op.text_color
                    Set-GdlColor $Project $st 'borderFillColorField' $op.fill
                    Set-GdlColor $Project $st 'borderColorField' $op.stroke
                    Set-GdlBorder $Project $st $op.border
                }
            }

            if ($op.donor_type -eq 'PBButton' -and $script:StateWrites -eq 0) {
                Note-Problem "'$($op.fields.nameField)': no state was written, so it will render the donor's caption"
            }
        } catch {
            Note-Problem "op '$($op.fields.nameField)' ($($op.donor_type)) failed: $($_.Exception.Message)"
            ($_.ScriptStackTrace -split "`n") | Select-Object -First 4 | ForEach-Object { Write-Output "      $_" }
        }
        if ($op.donor_type -eq 'PBPopupPageReference' -and $op.group) {
            # Remember it: the binding cannot be made until the popups exist.
            $script:PendingRefs += [pscustomobject]@{
                Control = $c; Group = $op.group
                ObjectId = [uint64]$op.fields.idField
                PageId = [uint64]$PageId
            }
        }
        if (-not $DryRun) { $Controls.Add($c) }
    }
}

# -- main ---------------------------------------------------------------------

Initialize-Gdl -InstallDir $InstallDir
$project = Open-GdlProject $DonorProject
# NOT $plan: PowerShell variables are case-insensitive, so $plan and the
# $Plan parameter are the same variable, and the parsed object overwrites the
# path it was read from.
$spec = Get-Content -Raw -Path $Plan | ConvertFrom-Json

Write-Output "plan: $(@($spec.pages).Count) page(s), canvas $($spec.canvas -join 'x')"

$donorPage = @($project.Pages)[0]
if (-not $donorPage) { throw 'donor project has no pages to clone from' }

foreach ($pg in $spec.pages) {
    $pageId = Get-GdlNextPageId $project
    Write-Output "page '$($pg.name)' -> id $pageId"

    $newPage = Copy-GdlObject $donorPage
    Set-GdlFieldIfPresent $newPage 'idField' $pageId | Out-Null
    Set-GdlFieldIfPresent $newPage 'nameField' $pg.name | Out-Null
    Set-GdlFieldIfPresent $newPage 'userIdField' ([uint16]$pg.number) | Out-Null
    Set-GdlColor $project $newPage 'backgroundFillColorField' $pg.background
    # A cloned page keeps the DONOR's page-level artwork, which then paints
    # underneath everything the plan authors. Clearing <TLPImageID> is not
    # enough: backgroundImageField is a separate reference to the donor's
    # background IMAGE, and Build re-rasterizes fill + image together into a new
    # page asset, so the donor's art comes back looking like a stray tint.
    Set-GdlFieldIfPresent $newPage '<TLPImageID>k__BackingField' -1 | Out-Null
    Set-GdlFieldIfPresent $newPage 'backgroundImageField' $null | Out-Null

    # Start from an empty page: the donor's controls carry its ids and popup
    # references, and inherited references are the documented way to end up
    # with a binding that reads "Unassigned".
    $controls = Get-GdlField $newPage 'controlsField'
    if ($pg.clear_controls -and $controls) { $controls.Clear() }

    Add-GdlControls $project $controls $pg.controls $pageId -DryRun:$WhatIf

    # Add through the backing field, not $project.Pages: the property may hand
    # back a copy, and appending to a copy silently does nothing.
    if (-not $WhatIf) {
        $pages = Get-GdlField $project 'pagesField'
        if (-not $pages) { throw 'no pagesField on the project' }
        $pages.Add($newPage)
    }
}


# -- popups --------------------------------------------------------------------
# Deliberately last: a popup binding lives in FOUR places and every mismatch
# fails silently, so the order is register group -> make popups -> bind the
# references -> write the back-pointers -> assert. See docs/gdl-format.md #6.
if (@($spec.popups).Count) {
    $NONE = [uint64]::MaxValue
    $groupIds = @{}
    foreach ($g in $spec.popup_groups) {
        $groupIds[$g] = Register-GdlPopupGroup $project $g
        Write-Output "popup group '$g' -> id $($groupIds[$g])"
    }

    # Only a STANDARD popup can be the target of a hand-authored reference;
    # modal popups are ungrouped and Build makes their references.
    $donorPopup = $project.PopupPages | Where-Object { -not $_.Modal } | Select-Object -First 1
    if (-not $donorPopup) { throw 'donor project has no standard popup to clone' }

    $made = @()
    foreach ($pu in $spec.popups) {
        $popupId = Get-GdlNextPageId $project
        $popup = Copy-GdlObject $donorPopup
        Set-GdlFieldIfPresent $popup 'idField' $popupId | Out-Null
        Set-GdlFieldIfPresent $popup 'userIdField' ([uint16]$pu.number) | Out-Null
        Set-GdlFieldIfPresent $popup 'nameField' $pu.name | Out-Null
        Set-GdlFieldIfPresent $popup 'modalField' $false | Out-Null
        # A cloned popup keeps the DONOR's size, and GUI Designer RELOCATES any
        # control that falls outside its page to 0,0 - at build time, silently,
        # with the build still reporting 0 errors. The first popup build lost
        # the last button of every grid to this: the spec said 984 wide, the
        # donor standard popup was 915, and everything past x=915 piled up at
        # the origin. Nothing in the file says so; you only see it in the
        # rendered result. Size the popup before its controls go in.
        if ($pu.size) {
            Set-GdlFieldIfPresent $popup 'widthField'  ([int]$pu.size[0]) | Out-Null
            Set-GdlFieldIfPresent $popup 'heightField' ([int]$pu.size[1]) | Out-Null
        } else {
            Note-Problem "popup '$($pu.name)' has no size in the plan - it will keep the donor's, and any control outside that is moved to 0,0"
        }
        Set-GdlFieldIfPresent $popup '<TLPImageID>k__BackingField' -1 | Out-Null
        Set-GdlFieldIfPresent $popup 'backgroundImageField' $null | Out-Null
        Set-GdlColor $project $popup 'backgroundFillColorField' $pu.background
        # A member stores the group's NAME as well as its id; one without the
        # other is one of the four silent-failure sites.
        Set-GdlFieldIfPresent $popup 'groupIDField' ([int]$groupIds[$pu.group]) | Out-Null
        Set-GdlFieldIfPresent $popup 'groupNameField' $pu.group | Out-Null

        $pcontrols = Get-GdlField $popup 'controlsField'
        if ($pu.clear_controls -and $pcontrols) { $pcontrols.Clear() }
        Add-GdlControls $project $pcontrols $pu.controls $popupId -DryRun:$WhatIf

        if (-not $WhatIf) {
            $pops = Get-GdlField $project 'popupPagesField'
            if (-not $pops) { throw 'no popupPagesField on the project' }
            $pops.Add($popup)
        }
        $made += [pscustomobject]@{ Popup = $popup; Id = $popupId; Group = $pu.group; Name = $pu.name }
        Write-Output "popup '$($pu.name)' -> id $popupId (group '$($pu.group)')"
    }

    # Bind each reference to its GROUP: PopupID is the sentinel, not a page id.
    foreach ($r in $script:PendingRefs) {
        $gid = $groupIds[$r.Group]
        if ($null -eq $gid) {
            Note-Problem "reference names group '$($r.Group)' which was never registered"
            continue
        }
        $binding = Get-GdlField $r.Control 'popupPageIDField'
        if (-not $binding) { $binding = $r.Control.PopupPageID }
        if (-not $binding) { Note-Problem 'popup reference has no PopupPageID'; continue }
        Set-GdlFieldIfPresent $binding 'popupIDField' $NONE | Out-Null
        Set-GdlFieldIfPresent $binding 'groupIDField' ([int]$gid) | Out-Null
        Set-GdlFieldIfPresent $binding 'popupNameField' '' | Out-Null
        Set-GdlFieldIfPresent $binding 'groupNameField' $r.Group | Out-Null
    }

    # The other half: each popup keeps back-pointers to the references that
    # place it. hasReferencesField must agree or the binding reads Unassigned.
    $backTemplate = Get-GdlField $donorPopup 'popupReferencesField'
    foreach ($m in $made) {
        $refsFor = @($script:PendingRefs | Where-Object { $_.Group -eq $m.Group })
        if (-not $refsFor.Count) { continue }
        if (-not $backTemplate -or -not $backTemplate.Count) {
            Note-Problem "no PBPopupReference to clone for back-pointers on '$($m.Name)'"
            continue
        }
        $list = [Activator]::CreateInstance($backTemplate.GetType())
        foreach ($r in $refsFor) {
            $back = Copy-GdlObject $backTemplate[0]
            Set-GdlFieldIfPresent $back 'pageIDField' ([uint64]$r.PageId) | Out-Null
            Set-GdlFieldIfPresent $back 'objectIDField' ([uint64]$r.ObjectId) | Out-Null
            Set-GdlFieldIfPresent $back 'popupPageIDField' $NONE | Out-Null
            $list.Add($back)
        }
        Set-GdlFieldIfPresent $m.Popup 'popupReferencesField' $list | Out-Null
        Set-GdlFieldIfPresent $m.Popup 'hasReferencesField' $true | Out-Null
    }

    # Assert rather than trust: this is the only check that catches a binding
    # that opens, builds, and reads "Unassigned".
    if (-not $WhatIf) {
        foreach ($m in $made) {
            $chk = Test-GdlPopupBinding $project $m.Id
            if ($chk.ok) { Write-Output "binding verified for '$($m.Name)': $($chk.references) reference(s)" }
            else { Note-Problem "popup '$($m.Name)' is not correctly bound: $($chk.problems -join '; ')" }
        }
    }
}

if ($script:Problems.Count) {
    Write-Output ''
    Write-Output "$($script:Problems.Count) problem(s):"
    $script:Problems | Select-Object -Unique | ForEach-Object { Write-Output "  $_" }
}

if ($WhatIf) {
    Write-Output ''
    Write-Output 'WhatIf: nothing was written. Re-run without -WhatIf to save.'
    return
}
if (-not $Output) { throw 'give -Output to save, or -WhatIf to dry-run' }

# Save-GdlProject prints a bare "The system cannot find the file specified"
# from inside an Extron assembly on every save. The return value is intact and
# it is not an error - see CLAUDE.md.
$bytes = Save-GdlProject $project $Output
Write-Output "wrote $Output ($bytes bytes)"
Write-Output 'Now repack and open in GUI Designer:'
Write-Output "  python -m gdl.container pack <donor.gdl> $Output ""Generated.gdl"""
