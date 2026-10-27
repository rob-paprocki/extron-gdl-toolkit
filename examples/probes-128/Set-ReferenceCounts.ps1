<#
    Read, and optionally rewrite, the reference count of each popup page group.

    MUST be run under 32-bit Windows PowerShell 5.1:
      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File examples\probes-128\Set-ReferenceCounts.ps1 -Project C:\gdlwork\x\ProjectGCP `
        -Counts 'One=46;Three=0;Five=1' -Output C:\gdlwork\x\counts_ProjectGCP

    Every group of the project's registry (popupPageGroupsField) is listed first
    with its id, its name and the referenceCountField it stores, beside how many
    popups name it and how many references bind to it. A group named in -Counts
    is then given that count; without -Counts, or without -Output, nothing is
    written.

    The applier writes 2 on every group it registers (Register-GdlPopupGroup),
    and a client's project stores 46, 8, 13 and 2 against 11, 1, 2 and 2
    members (docs/gdl-format.md section 6). What the field is for is the open
    question, so this puts values on a built project that no rule of
    "members" or "references" would give, and the next build says whether any
    of them survives.
#>
param(
    [Parameter(Mandatory)][string]$Project,
    [string]$Counts,
    [string]$Output,
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer'
)

$ErrorActionPreference = 'Stop'
. (Join-Path (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'powershell') 'GdlProject.ps1')
Initialize-Gdl -InstallDir $InstallDir | Out-Null

function Report($m) { [Console]::WriteLine($m) }

$p = Open-GdlProject $Project
$groups = Get-GdlField $p 'popupPageGroupsField'

function Show-Groups($label) {
    Report $label
    foreach ($g in $groups) {
        $id = [int](Get-GdlField $g 'idField')
        $popups = @($p.PopupPages | Where-Object { [int]$_.GroupID -eq $id }).Count
        $refs = 0
        foreach ($pg in @($p.Pages) + @($p.PopupPages)) {
            foreach ($c in $pg.Controls) {
                if ($c.GetType().Name -eq 'PBPopupPageReference' -and [int]$c.PopupPageID.GroupID -eq $id) { $refs++ }
            }
        }
        Report ("  group {0,-4} {1,-24} referenceCountField {2,-6} popups in it {3,-3} references to it {4}" -f
                $id, (Get-GdlField $g 'nameField'), (Get-GdlField $g 'referenceCountField'), $popups, $refs)
    }
}

Show-Groups "registry of $Project ($($groups.Count) group(s)):"

if ($Counts) {
    $want = @{}
    foreach ($pair in ($Counts -split ';')) {
        if (-not $pair.Trim()) { continue }
        $k, $v = $pair -split '=', 2
        $want[$k.Trim()] = $v.Trim()
    }
    foreach ($g in $groups) {
        $name = Get-GdlField $g 'nameField'
        if (-not $want.ContainsKey($name)) { continue }
        # Converted to the field's own type, so a value it cannot hold is said
        # here rather than written as something else.
        $field = $g.GetType().GetField('referenceCountField', 'Instance,Public,NonPublic')
        try {
            $value = [Convert]::ChangeType($want[$name], $field.FieldType)
            Set-GdlField $g 'referenceCountField' $value
            Report ("set    {0} -> {1} ({2})" -f $name, $value, $field.FieldType.Name)
        } catch {
            Report ("could not set {0} to {1} as a {2}: {3}" -f $name, $want[$name], $field.FieldType.Name, $_.Exception.Message)
        }
        $want.Remove($name)
    }
    foreach ($k in $want.Keys) { Report "no group named '$k' in the registry" }
    Show-Groups 'registry after:'
    if ($Output) {
        $n = Save-GdlProject $p $Output
        Report "wrote $Output ($n bytes)"
    }
}
