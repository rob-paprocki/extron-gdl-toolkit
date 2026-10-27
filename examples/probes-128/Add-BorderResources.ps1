<#
    Append border resources to a project's resource set.

    MUST be run under 32-bit Windows PowerShell 5.1:
      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File examples\probes-128\Add-BorderResources.ps1 -Project C:\gdlwork\x\ProjectGCP `
        -Table examples\probes-128\borders.json -Output C:\gdlwork\x\res_ProjectGCP

    The probe New-FormatProbes.ps1 ran as test B, made reusable: it clones a
    PBBorderResource the project already has, renames it and sets its corner
    radius and thickness - the one way the format lets a project carry a
    geometry no template defines, since the shipped applier only references the
    resources its donor has (Set-GdlBorder in GdlApply.ps1). A row the project
    already defines is left as it is and said so.

    Run on the donor's ProjectGCP before Apply-GdlPlan.ps1, so the applier finds
    the resource by name and binds it exactly as it binds any other.
#>
param(
    [Parameter(Mandatory)][string]$Project,
    [Parameter(Mandatory)][string]$Table,
    [Parameter(Mandatory)][string]$Output,
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer'
)

$ErrorActionPreference = 'Stop'
. (Join-Path (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'powershell') 'GdlProject.ps1')
Initialize-Gdl -InstallDir $InstallDir | Out-Null

function Report($m) { [Console]::WriteLine($m) }

$rows = (Get-Content -Raw -Path $Table -Encoding UTF8 | ConvertFrom-Json).rows
$p = Open-GdlProject $Project
$resources = Get-GdlField $p.ResourceSet 'resourcesField'
if (-not $resources) { $resources = Get-GdlField $p.ResourceSet 'ResourcesField' }
$borders = @($resources | Where-Object { $_.GetType().Name -eq 'PBBorderResource' })
Report "border resources before: $($borders.Count) of $($resources.Count) resources"

$family = $borders | Where-Object { $_.Name -like 'Afterburn*' } | Select-Object -First 1
if (-not $family) { $family = $borders | Select-Object -First 1 }
if (-not $family) { throw 'the project defines no border resource to clone' }

$added = 0
foreach ($r in $rows) {
    $have = $borders | Where-Object { $_.Name -eq $r.resource } | Select-Object -First 1
    if ($have) {
        $d = Get-GdlField $have 'dataField'
        Report ("kept   '{0}' - the project defines it: radius {1}, thickness {2}" -f $r.resource,
                (Get-GdlField $d 'cornerRadiusField'), (Get-GdlField $d 'thicknessField'))
        continue
    }
    $new = Copy-GdlObject $family
    Set-GdlField $new 'nameField' $r.resource
    $info = Get-GdlField $new 'dataField'
    Set-GdlField $info 'cornerRadiusField' $r.radius
    Set-GdlField $info 'thicknessField' $r.thickness
    Set-GdlField $new 'dataField' $info
    $resources.Add($new)
    $added++
    Report ("added  '{0}': radius {1}, thickness {2}" -f $r.resource, $r.radius, $r.thickness)
}
$n = Save-GdlProject $p $Output
$after = @($resources | Where-Object { $_.GetType().Name -eq 'PBBorderResource' }).Count
Report "border resources after: $after ($added added); wrote $Output ($n bytes)"
