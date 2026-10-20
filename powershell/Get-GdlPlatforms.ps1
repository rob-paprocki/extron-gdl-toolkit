<#
    Every panel GUI Designer can build for, read from its own assemblies.

        C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile `
            -ExecutionPolicy Bypass -File powershell\Get-GdlPlatforms.ps1 `
            -Donor 'seeds\Afterburn 1035.gdl' -Output research\data\platform-details.txt

    For each PlatformProTypeEnum member it asks Extron's own factory,
    PBTouchPanelPlatformPro.CreatePlatform(project, type), for the platform
    and prints its class, default resolution, DPI, part number and the list of
    resolutions it supports. gdl/spec.py's MODELS_FULL and ORIENTATIONS are
    read off this output.

    The factory takes a project, and PBProject does not construct outside the
    running app (docs/gdl-format.md), so any seed's graph is borrowed: -Donor
    names the .gdl, and its ProjectGCP is extracted with gdl/container.py.
    Nothing is written to the donor.

    A panel that rotates lists both orientations under SUPPORTED; GUI
    Designer's Project Create Wizard then shows a Resolution combo for it.
    The soft clients (VTLP*, TLI*) list named presets and Custom instead of
    fixed resolutions; a ZRTP* lists its one fixed resolution and Custom.

    Needs 32-bit Windows PowerShell 5.1 and GUI Designer installed
    (CLAUDE.md, Environment).
#>
param(
    [Parameter(Mandatory)][string]$Donor,
    [string]$Output,
    [string]$Python = 'python',
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer'
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
. (Join-Path $repo 'powershell\GdlProject.ps1')
Initialize-Gdl -InstallDir $InstallDir | Out-Null

$Donor = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Donor)
$work = Join-Path ([IO.Path]::GetTempPath()) ("gdlplat-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
try {
    Push-Location $repo
    try { & $Python -m gdl.container extract $Donor $work | Out-Null } finally { Pop-Location }
    $gcp = Join-Path $work 'ProjectGCP'
    if (-not (Test-Path $gcp)) { throw "no ProjectGCP in $Donor" }
    $proj = Open-GdlProject $gcp
} finally {
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}

$enumType = $proj.GetType().GetField('platformTypeField', 'Instance,Public,NonPublic').FieldType
$base = (Get-GdlField $proj 'platformField').GetType()
while ($base -and $base.Name -ne 'PBTouchPanelPlatformPro') { $base = $base.BaseType }
if (-not $base) { throw "the donor's platform is not a PBTouchPanelPlatformPro" }
$flags = [Reflection.BindingFlags]'Static,Public,NonPublic,FlattenHierarchy'
$create = $base.GetMethods($flags) | Where-Object { $_.Name -eq 'CreatePlatform' } | Select-Object -First 1

function Get-Fields($r) {
    $f = @{}
    foreach ($x in $r.GetType().GetFields('Instance,Public,NonPublic')) { $f[$x.Name] = $x.GetValue($r) }
    $f
}

$rows = @("ENUM`tCLASS`tRES`tDPI`tPARTNUMBER`tSUPPORTED")
foreach ($name in [Enum]::GetNames($enumType)) {
    $inst = $null
    try { $inst = $create.Invoke($null, [object[]]@($proj, [Enum]::Parse($enumType, $name))) } catch { }
    if (-not $inst) { $rows += "$name`t<null>`t-`t-`t-`t-"; continue }
    # Not @(...): that wraps the List itself as one element (the collection
    # trap in docs/gdl-format.md section 7), and foreach walks its entries.
    $sup = Get-GdlField $inst 'supportedResolutions'
    $listed = @()
    $dpi = $null
    if ($sup) {
        foreach ($r in $sup) {
            if (-not $r) { continue }
            # A fixed panel's entry carries resolutionX/resolutionY/dpi; a soft
            # client's a preset name (and Custom nothing more).
            $f = Get-Fields $r
            if ($f['resolutionX']) {
                $listed += "$($f['resolutionX'])x$($f['resolutionY'])"
                if ($null -eq $dpi) { $dpi = $f['dpi'] }
            } elseif ($f['name']) {
                $listed += "'$($f['name'])'"
            }
        }
    }
    # The platform's own ppiField reads 0; the DPI a panel is drawn at is on
    # its resolution entries, or, for a soft client, GUI Designer's default.
    if ($null -eq $dpi) {
        # Reflection writes out-parameters back into the argument array.
        $a = [object[]]@([Enum]::Parse($enumType, $name), 0, 0, [single]0)
        $m = $base.GetMethods($flags) | Where-Object {
            $_.Name -eq 'GetDefaultResolutionDpi' -and -not $_.IsGenericMethod -and
            @($_.GetParameters()).Count -eq 4 } | Select-Object -First 1
        if ($m) {
            try { $m.Invoke($null, $a) | Out-Null; $dpi = $a[3] } catch { }
        }
    }
    $rows += ("$name`t$($inst.GetType().Name)`t" +
              "$(Get-GdlField $inst 'horizontalResolutionField')x$(Get-GdlField $inst 'verticalResolutionField')`t" +
              "$(if ($null -ne $dpi) { $dpi } else { '-' })`t$(Get-GdlField $inst 'partNumberField')`t" +
              ($listed -join ' '))
}
$rows | ForEach-Object { $_ }
if ($Output) {
    # UTF-8 without the byte-order mark Set-Content -Encoding UTF8 writes in 5.1.
    $Output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
    [IO.File]::WriteAllLines($Output, [string[]]$rows, (New-Object Text.UTF8Encoding $false))
}
