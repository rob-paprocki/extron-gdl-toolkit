<#
    Apply a build plan from `python -m gdl.spec plan` to a donor ProjectGCP.

    MUST be run under 32-bit Windows PowerShell 5.1:
      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe

      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass `
        -File powershell\Apply-GdlPlan.ps1 out\ProjectGCP plan.json out\new_ProjectGCP

    ############################################################################
    #  UNVERIFIED. This script has never been run - it was written on a Mac,   #
    #  where neither BinaryFormatter nor Extron's x86 assemblies exist. Treat  #
    #  the first run as an experiment, not as a tool.                          #
    ############################################################################

    It is deliberately thin. Every decision - layout, ids, colours, which donor
    to clone - was made in Python, where it is testable; this only applies ops.
    That is why the interesting logic is in gdl/spec.py and not here.

    It is also deliberately self-diagnosing: -WhatIf resolves every donor and
    every field WITHOUT mutating anything, and unknown fields are reported and
    skipped rather than thrown on, so the first real run produces a punch list
    instead of one stack trace.

    Everything here follows the rules in docs/gdl-format.md:
      * clone, never construct (section 4)
      * write backing fields, never properties (section 4)
      * a popup binding lives in four places (section 6) - this script does not
        author popups at all, precisely because that is the part that fails
        silently; use Register-GdlPopupGroup + Test-GdlPopupBinding for those.
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

$script:Problems = @()
function Note-Problem([string]$m) {
    $script:Problems += $m
    Write-Warning $m
}

function Set-GdlFieldIfPresent {
    <#  Set a backing field, but report-and-continue when it does not exist.
        A generated plan that names one field wrong should tell you about all
        the others too, not stop at the first.

        Values are coerced to the field's declared type. A plan comes from JSON,
        so every number arrives as Int32, while the fields are UInt64 (idField),
        UInt16 (userIdField) and so on - and reflection's SetValue will not widen
        or narrow for you, it just throws. #>
    param($Object, [string]$Field, $Value)
    $t = $Object.GetType()
    while ($t -and $t.FullName -ne 'System.Object') {
        $f = $t.GetField($Field, 'Instance,Public,NonPublic,DeclaredOnly')
        if ($f) {
            $v = $Value
            if ($null -ne $v -and $f.FieldType -ne $v.GetType()) {
                try {
                    if ($f.FieldType.IsEnum) {
                        $v = [Enum]::ToObject($f.FieldType, $v)
                    } elseif ($f.FieldType.IsValueType -or $f.FieldType -eq [string]) {
                        $v = [Convert]::ChangeType($v, $f.FieldType)
                    }
                } catch {
                    Note-Problem "cannot convert '$Field' value '$v' to $($f.FieldType.Name)"
                    return $false
                }
            }
            Set-GdlField $Object $Field $v
            return $true
        }
        $t = $t.BaseType
    }
    Note-Problem "no field '$Field' on $($Object.GetType().Name)"
    return $false
}

function Get-GdlDonor {
    <#  Any instance of a class, from anywhere in the project.

        Only backing fields survive a clone, so which instance does not matter -
        but there must BE one. A project with no PBSlider cannot author a slider,
        which is the clone-never-construct rule biting. #>
    param($Project, [string]$TypeName)
    foreach ($pg in @($Project.Pages) + @($Project.PopupPages)) {
        foreach ($c in $pg.Controls) {
            if ($c.GetType().Name -eq $TypeName) { return , $c }
        }
    }
    return $null
}

$script:ColourDonor = $null
function Find-ColourDonor {
    <#  Any PBColor instance in the project, to clone when a target field is null.

        Needed because clone-never-construct applies to PBColor too, and a field
        being null is common - a button leaves textColorField null and carries
        its text colour on the state instead. #>
    param($Project)
    if ($script:ColourDonor) { return , $script:ColourDonor }
    foreach ($pg in @($Project.Pages) + @($Project.PopupPages)) {
        foreach ($c in $pg.Controls) {
            foreach ($n in 'borderFillColorField', 'textColorField', 'borderColorField') {
                $v = Get-GdlField $c $n
                if ($v) { $script:ColourDonor = $v; return , $v }
            }
        }
    }
    return $null
}

function Set-GdlColour {
    <#  Set a PBColor-valued field from a packed 0xAARRGGBB int.

        The PBColor wrapper is cloned - from the field's current value where it
        has one, otherwise from any PBColor in the project. Only its inner
        System.Drawing.Color is replaced; FromArgb avoids reflecting into a
        struct's backing field, which does not behave like a class's. #>
    param($Project, $Control, [string]$Field, $Argb)
    if ($null -eq $Argb) { return }

    # Distinguish "no such field" from "field is null" - conflating them
    # reports a missing field that is right there.
    $t = $Control.GetType(); $has = $false
    while ($t -and $t.FullName -ne 'System.Object') {
        if ($t.GetField($Field, 'Instance,Public,NonPublic,DeclaredOnly')) { $has = $true; break }
        $t = $t.BaseType
    }
    if (-not $has) { Note-Problem "no field '$Field' on $($Control.GetType().Name)"; return }

    $existing = Get-GdlField $Control $Field
    if (-not $existing) { $existing = Find-ColourDonor $Project }
    if (-not $existing) { Note-Problem "no PBColor anywhere to clone for '$Field'"; return }

    $c = Copy-GdlObject $existing
    $a = ($Argb -shr 24) -band 0xFF
    $r = ($Argb -shr 16) -band 0xFF
    $g = ($Argb -shr 8) -band 0xFF
    $b = $Argb -band 0xFF
    Set-GdlFieldIfPresent $c 'valueField' ([System.Drawing.Color]::FromArgb($a, $r, $g, $b)) | Out-Null
    Set-GdlFieldIfPresent $Control $Field $c | Out-Null
}

function Set-GdlBorder {
    <#  Point a control's border at a named resource that already exists.

        Referencing an existing resource is the whole design: appending a NEW
        PBBorderResource has never been tested against GUI Designer, so a plan
        may only name resources the donor already carries. This checks that. #>
    param($Project, $Control, [string]$Name)
    if (-not $Name) { return }
    $known = @($Project.ResourceSet.Resources |
        Where-Object { $_.GetType().Name -eq 'PBBorderResource' } |
        ForEach-Object { $_.Name })
    if ($known -and ($known -notcontains $Name)) {
        Note-Problem "border resource '$Name' is not in the donor project; a plan may only reference existing resources"
        return
    }
    $existing = Get-GdlField $Control 'borderField'
    if (-not $existing) { Note-Problem "no borderField on $($Control.GetType().Name)"; return }
    $ref = Copy-GdlObject $existing
    Set-GdlFieldIfPresent $ref 'resourceNameField' $Name | Out-Null
    Set-GdlFieldIfPresent $Control 'borderField' $ref | Out-Null
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
    Set-GdlColour $project $newPage 'backgroundFillColorField' $pg.background
    # A cloned page keeps the DONOR's page-level artwork, which then paints
    # underneath everything the plan authors. Clear it and let Build redraw.
    Set-GdlFieldIfPresent $newPage '<TLPImageID>k__BackingField' -1 | Out-Null

    # Start from an empty page: the donor's controls carry its ids and popup
    # references, and inherited references are the documented way to end up
    # with a binding that reads "Unassigned".
    $controls = Get-GdlField $newPage 'controlsField'
    if ($pg.clear_controls -and $controls) { $controls.Clear() }

    foreach ($op in $pg.controls) {
        $donor = Get-GdlDonor $project $op.donor_type
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
            Set-GdlColour $project $c 'borderFillColorField' $op.fill
            Set-GdlColour $project $c 'borderColorField' $op.stroke
            Set-GdlColour $project $c 'textColorField' $op.text_color
            # flattenText bakes the caption INTO the artwork at build time, and a
        # clone inherits the donor's. Build then dedupes every generated button
        # to one asset carrying the donor's word. Captions must be drawn live
        # from layout.json, which is what the panel firmware does anyway.
        Set-GdlFieldIfPresent $c 'flattenTextField' $false | Out-Null
        Set-GdlFieldIfPresent $c 'buttonImageField' $null | Out-Null
        Set-GdlFieldIfPresent $c 'backgroundImageField' $null | Out-Null
        Set-GdlBorder $project $c $op.border
            Set-GdlFieldIfPresent $c 'textAlignmentField' $op.alignment | Out-Null

            # A button renders from its STATE, not from the control: layout.json's
            # reader takes state[0]'s text/font/colour in preference. Mirror the
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
                    Set-GdlColour $project $st 'textColorField' $op.text_color
                    Set-GdlColour $project $st 'borderFillColorField' $op.fill
                    Set-GdlColour $project $st 'borderColorField' $op.stroke
                }
            }

            if ($op.donor_type -eq 'PBButton' -and $script:StateWrites -eq 0) {
                Note-Problem "'$($op.fields.nameField)': no state was written, so it will render the donor's caption"
            }
        } catch {
            Note-Problem "op '$($op.fields.nameField)' ($($op.donor_type)) failed: $($_.Exception.Message)"
            ($_.ScriptStackTrace -split "`n") | Select-Object -First 4 | ForEach-Object { Write-Output "      $_" }
        }
        if (-not $WhatIf) { $controls.Add($c) }
    }

    # Add through the backing field, not $project.Pages: the property may hand
    # back a copy, and appending to a copy silently does nothing.
    if (-not $WhatIf) {
        $pages = Get-GdlField $project 'pagesField'
        if (-not $pages) { throw 'no pagesField on the project' }
        $pages.Add($newPage)
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
