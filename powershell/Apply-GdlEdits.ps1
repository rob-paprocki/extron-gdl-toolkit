<#
    Apply an edit plan from `python -m gdl.edit plan` to an existing ProjectGCP.

    MUST be run under 32-bit Windows PowerShell 5.1:
      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe

      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass `
        -File powershell\Apply-GdlEdits.ps1 C:\work\ProjectGCP edits-plan.json C:\work\out_ProjectGCP

    The sibling of Apply-GdlPlan.ps1 and deliberately the same shape: every
    decision - which controls match, what the new ids are, whether the layout
    still fits - was made in `gdl/edit.py`, against the real project, on a Mac.
    This walks the ops and sets fields.

    The one thing it does that the other applier does not is CONSTRUCT: a
    retarget needs a `PBTouchPanelPlatformPro` instance, and platform classes
    are among the few Extron types that construct headlessly, because they hold
    no project state. Everything else still clones.

    Ops are addressed by id, not by index. `page` is the page's `idField` and
    `control` is the control's `idField` - the same numbers `gdl/project.py`
    reports and `layout.json` exports as `Page.ID` / `Control.ID`, so a plan
    stays valid even if collection order changes.

    Finish with `python tests/verify_built.py` on the BUILT file. A clean build
    does not mean a correct one; see docs/gdl-format.md section 7.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Project,
    [Parameter(Mandatory)][string]$Plan,
    [string]$Output,
    [switch]$WhatIf,
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'GdlProject.ps1')
. (Join-Path $PSScriptRoot 'GdlApply.ps1')

function Get-GdlPageById {
    param($Proj, $Id)
    foreach ($pg in @($Proj.Pages) + @($Proj.PopupPages)) {
        if ([uint64](Get-GdlField $pg 'idField') -eq [uint64]$Id) { return , $pg }
    }
    return $null
}

function Get-GdlControlById {
    param($Page, $Id)
    foreach ($c in $Page.Controls) {
        if ([uint64](Get-GdlField $c 'idField') -eq [uint64]$Id) { return , $c }
    }
    return $null
}

function Set-GdlStates {
    <#  Apply a change to every state of a control.

        Index rather than foreach: PBStates supports .Count and [i] but
        enumerating it yields the collection itself, so foreach silently writes
        to the wrong object. A shape also reports a non-zero Count on an empty
        states collection and then indexes to null, so check each one. #>
    param($Proj, $Control, $Fields, $Colors, $FText)
    $states = Get-GdlField $Control 'statesField'
    if (-not $states -or -not $states.Count) { return 0 }
    $n = 0
    for ($i = 0; $i -lt $states.Count; $i++) {
        $st = $states[$i]
        if ($null -eq $st) { continue }
        $n++
        if ($Fields) {
            foreach ($f in $Fields.PSObject.Properties) {
                Set-GdlFieldIfPresent $st $f.Name $f.Value | Out-Null
            }
        }
        if ($null -ne $FText) {
            # Formatted text keeps the original's leading layout markers - the
            # tabs and CRLFs are how it draws, not decoration - so splice the
            # new wording into the old scaffolding rather than replacing it.
            $old = [string](Get-GdlField $st 'ftextField')
            $lead = ''
            if ($old -match '^([\t\r\n ]*)') { $lead = $Matches[1] }
            Set-GdlFieldIfPresent $st 'ftextField' ($lead + $FText) | Out-Null
        }
        if ($Colors) {
            foreach ($f in $Colors.PSObject.Properties) {
                Set-GdlColor $Proj $st $f.Name (ConvertTo-Argb $f.Value)
            }
        }
    }
    return $n
}

function ConvertTo-Argb {
    <#  '#AARRGGBB' -> the packed int Set-GdlColor wants.

        The plan carries colors as hex strings because that is what a human
        writes in an edit spec and what gdl/edit.py matches on. #>
    param([string]$Hex)
    if (-not $Hex) { return $null }
    return [Convert]::ToInt64($Hex.TrimStart('#'), 16)
}

# -- main ---------------------------------------------------------------------

Initialize-Gdl -InstallDir $InstallDir
$proj = Open-GdlProject $Project
$spec = Get-Content -Raw -Path $Plan | ConvertFrom-Json

Write-Output "project: $($proj.Name)"
Write-Output "plan: $(@($spec.controls).Count) control op(s), $(@($spec.project).Count) project op(s)"

# -- project-level ops (retarget) ---------------------------------------------
foreach ($op in $spec.project) {
    if (-not $op.model) { continue }
    Write-Output "retarget -> $($op.model) $($op.size -join 'x')"

    # Use Extron's own factory, NOT [Activator]::CreateInstance.
    #
    # A default-constructed platform class gets its resolution right and leaves
    # `partNumberField` null, and GUI Designer then titles the project
    # "Unknown: file.gdl" - it identifies the panel by part number, not by
    # class. Everything else about the file was correct, which is what made it
    # worth chasing rather than shrugging at.
    #
    #   PBTouchPanelPlatformPro.CreatePlatform(PBProject, PlatformProTypeEnum)
    #
    # returns a fully initialized instance, part number and all. It needs the
    # project, which is presumably why the wizard is the only thing that
    # normally calls it.
    $enumField = $proj.GetType().GetField('platformTypeField', 'Instance,Public,NonPublic')
    if (-not $enumField) { Note-Problem 'no platformTypeField on the project'; continue }
    try {
        $etype = [Enum]::Parse($enumField.FieldType, $op.model)
    } catch {
        Note-Problem "PlatformProTypeEnum has no member '$($op.model)'"
        continue
    }

    $current = Get-GdlField $proj 'platformField'
    $base = $current.GetType().BaseType
    $flags = [Reflection.BindingFlags]'Static,Public,NonPublic,FlattenHierarchy'
    $create = $base.GetMethods($flags) |
              Where-Object { $_.Name -eq 'CreatePlatform' } | Select-Object -First 1
    if (-not $create) { Note-Problem 'PBTouchPanelPlatformPro has no CreatePlatform'; continue }

    $inst = $null
    try { $inst = $create.Invoke($null, [object[]]@($proj, $etype)) }
    catch {
        $inner = $_.Exception.InnerException
        Note-Problem "CreatePlatform($($op.model)) threw $(if($inner){$inner.GetType().Name}else{'?'})"
        continue
    }
    if (-not $inst) {
        Note-Problem "CreatePlatform returned null for '$($op.model)' - the enum has no touch-panel platform behind it (the MLC 84 button panels and TLP 1022W are like this)"
        continue
    }
    Write-Output "   platform $($inst.GetType().Name) part $(Get-GdlField $inst 'partNumberField')"

    if (-not $WhatIf) {
        Set-GdlFieldIfPresent $proj 'platformField' $inst | Out-Null
        Set-GdlField $proj 'platformTypeField' $etype
        Set-GdlFieldIfPresent $proj 'screenSizeField' `
            (New-Object System.Drawing.Size([int]$op.size[0], [int]$op.size[1])) | Out-Null

        # Pages ARE the canvas - a page left at the old size would put every
        # control outside it, and Build moves those to 0,0 without a word.
        #
        # POPUPS TOO, but NOT at the screen size. This used to set every page
        # and popup to $op.size, on the belief that a popup's authored
        # widthField/heightField is always the full canvas (1280x800 here) with
        # layout.json's smaller 915x800 being the DISPLAYED size taken from the
        # reference that shows it. That belief came from the Liberty Bank
        # fixture, where every popup happens to be authored full-canvas, and it
        # is wrong. In Extron's own Afterburn template 10 of the 29 popups are
        # authored at 880x525, and the BUILT payload reports 880x525 for them -
        # all 29 popup sizes in layout.json match the authored canvas exactly.
        # The authored size IS the popup size. Forcing it to the screen size
        # turns a modal card into a full-screen page in the shipped file.
        #
        # gdl.edit now emits a size per page, each scaled by the same per-axis
        # factors as its controls, so canvas and contents move together. Fall
        # back to the old blanket behaviour only for a plan that predates it -
        # leaving a popup at the old canvas is the one outcome that silently
        # destroys the layout.
        $sized = @{}
        foreach ($pgop in @($spec.pages)) {
            if ($null -ne $pgop) { $sized[[string]$pgop.page] = $pgop.size }
        }
        foreach ($pg in @($proj.Pages) + @($proj.PopupPages)) {
            $want = $sized[[string](Get-GdlField $pg 'idField')]
            if (-not $want) { $want = $op.size }
            Set-GdlFieldIfPresent $pg 'widthField' ([int]$want[0]) | Out-Null
            Set-GdlFieldIfPresent $pg 'heightField' ([int]$want[1]) | Out-Null
        }
    }
}

# -- control ops ---------------------------------------------------------------
$applied = 0
$pageCache = @{}
foreach ($op in $spec.controls) {
    $pg = $pageCache[[string]$op.page]
    if (-not $pg) {
        $pg = Get-GdlPageById $proj $op.page
        if (-not $pg) { Note-Problem "no page with id $($op.page)"; continue }
        $pageCache[[string]$op.page] = $pg
    }
    $c = Get-GdlControlById $pg $op.control
    if (-not $c) {
        Note-Problem "no control with id $($op.control) on page '$($pg.Name)'"
        continue
    }
    if ($WhatIf) { $applied++; continue }

    try {
        if ($op.fields) {
            foreach ($f in $op.fields.PSObject.Properties) {
                Set-GdlFieldIfPresent $c $f.Name $f.Value | Out-Null
            }
        }
        if ($op.colors) {
            foreach ($f in $op.colors.PSObject.Properties) {
                Set-GdlColor $proj $c $f.Name (ConvertTo-Argb $f.Value)
            }
        }
        if ($op.states -or $op.states_colors -or $null -ne $op.states_ftext) {
            Set-GdlStates $proj $c $op.states $op.states_colors $op.states_ftext | Out-Null
        }
        $applied++
    } catch {
        Note-Problem "op on control $($op.control) ('$($op.why)') failed: $($_.Exception.Message)"
    }
}

Write-Output "$applied of $(@($spec.controls).Count) control op(s) applied"

if ($script:Problems.Count) {
    Write-Output ''
    Write-Output "$($script:Problems.Count) problem(s):"
    $script:Problems | ForEach-Object { Write-Output "   $_" }
}

if ($WhatIf) {
    Write-Output '-WhatIf: nothing was written'
    return
}
if (-not $Output) { $Output = $Project + '.edited' }
Save-GdlProject $proj $Output | Out-Null
Write-Output "wrote $Output ($((Get-Item $Output).Length) bytes)"
Write-Output 'Now repack, open in GUI Designer, Save and Build (Ctrl+Shift+B), then:'
Write-Output "  python tests/verify_built.py $Plan <built.gdl>"
