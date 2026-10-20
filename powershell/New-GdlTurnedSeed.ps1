<#
    A seed for a panel turned where its theme draws no template that way up,
    made from the model's own seed turned, built and verified - nobody at the
    mouse.

        powershell\New-GdlTurnedSeed.ps1 -From 'seeds\Afterburn 1035.gdl' -Model TLP1035M `
            -Resolution '800x1280' -Output 'seeds\Afterburn 1035 Portrait.gdl'

    The 835M and 1035M portrait, and the 520M, 521M and 535M turned, have no
    template that way up (docs/design-rules.md section 1), so the Project
    Create Wizard offers them Blank and New-GdlSeed.ps1 cannot make one. The
    model's own seed turned by gdl.edit retarget (docs/editing.md) is one: its
    controls stretched per axis, the right shape for a donor though not a
    portrait design - a panel is drawn at the turned canvas, in a spec, and
    the applier drops the seed's own pages. gdl.seeds gives this line where a
    seed is missing.

    It plans the retarget, applies it (32-bit PowerShell: Extron's assemblies
    are x86), packs it, opens it in GUI Designer, saves and builds it, and
    verifies it with tests/verify_seed.py, which compares a turned seed with
    its series template turned the same way. A seed that does not build or
    verify is removed. Like New-GdlPanel.ps1 it needs GUI Designer's window,
    and once the turn is planned and applied it closes any GUI Designer already
    running - a turn refused before that leaves it alone.

    Exit codes: 0 made and verified; 2 bad arguments; 3 the edit was refused;
    5 GUI Designer did not open it; 7 it did not build; the verifier's code
    if it refused.
#>
param(
    [Parameter(Mandatory)][string]$From,
    [Parameter(Mandatory)][string]$Model,
    [Parameter(Mandatory)][string]$Resolution,
    [Parameter(Mandatory)][string]$Output,
    [string]$Python = 'python',
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer',
    [int]$TimeoutSeconds = 1800
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$ps32 = 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
$gd = Join-Path $InstallDir 'GUI Designer.exe'
. (Join-Path $PSScriptRoot 'GdlBlocker.ps1')

# Relative to where the shell is, as for any cmdlet (New-GdlPanel.ps1 has why
# not [IO.Path]::GetFullPath), and before anything moves the location.
$From = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($From)
$Output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)

$bad = @()
$size = $null
if ($Resolution -match '^(\d+)x(\d+)$') { $size = @([int]$Matches[1], [int]$Matches[2]) }
else { $bad += "-Resolution '$Resolution' is not WxH, as '800x1280'" }
if (-not (Test-Path -LiteralPath $From -PathType Leaf)) { $bad += "-From $From is not here" }
else {
    $head = New-Object byte[] 40
    $fs = [System.IO.File]::OpenRead($From)
    try { [void]$fs.Read($head, 0, 40) } finally { $fs.Dispose() }
    if ([System.Text.Encoding]::ASCII.GetString($head).StartsWith('version https://git-lfs')) {
        $bad += "-From $From is a Git LFS pointer, not the seed - git lfs pull it first"
    }
}
if (Test-Path -LiteralPath $Output) { $bad += "-Output $Output is there already - this makes a seed, it overwrites none" }
elseif (-not (Test-Path -LiteralPath (Split-Path $Output -Parent) -PathType Container)) {
    $bad += "-Output's folder $(Split-Path $Output -Parent) is not here"
}
if (-not (Test-Path $ps32)) { $bad += "32-bit PowerShell 5.1 is not at $ps32" }
if (-not (Test-Path $gd)) { $bad += "GUI Designer is not at $gd" }
if ($bad) { $bad | ForEach-Object { Write-Output $_ }; exit 2 }

# Scratch on a local disk, as New-GdlPanel.ps1's, under a name of its own.
$Work = Join-Path 'C:\gdlwork' ('turned-' + [System.IO.Path]::GetFileNameWithoutExtension($Output))
New-Item -ItemType Directory -Force -Path $Work | Out-Null
foreach ($n in 'edits.json', 'plan.json', 'ProjectGCP', 'turned_ProjectGCP') {
    $p = Join-Path $Work $n
    if (Test-Path $p) { Remove-Item $p -Force }
}

$step = 0
function Step($msg) {
    $script:step++
    Write-Output ''
    Write-Output "=== [$script:step] $msg"
}
# A seed nobody verified must not stay where the next run refuses to overwrite it.
# GUI Designer is this script's to close only from the open step on; before
# that, a failure leaves the user's own session as it was.
$gdOurs = $false
function Fail([string]$why, [int]$code) {
    Write-Output $why
    if ($script:gdOurs) {
        Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $Output) {
        Start-Sleep -Seconds 1
        Remove-Item -LiteralPath $Output -Force
        Write-Output "removed $Output"
    }
    exit $code
}

Push-Location $repo
try {
    Step "plan the turn: $Model at $Resolution, from $From"
    $edits = Join-Path $Work 'edits.json'
    $plan = Join-Path $Work 'plan.json'
    $json = @{ edits = @(@{ op = 'retarget'; model = $Model; size = $size; scale = $true }) } |
        ConvertTo-Json -Depth 5
    # No byte-order mark: gdl.edit reads its spec as UTF-8, and json refuses one.
    [System.IO.File]::WriteAllText($edits, $json, (New-Object System.Text.UTF8Encoding $false))
    & $Python -m gdl.edit check $edits $From
    if ($LASTEXITCODE -ne 0) { Fail 'the turn was refused' 3 }
    & $Python -m gdl.edit plan $edits $From $plan
    if ($LASTEXITCODE -ne 0) { Fail 'the turn could not be planned' 3 }

    Step 'apply it (32-bit PowerShell)'
    & $Python -m gdl.container extract $From $Work
    if ($LASTEXITCODE -ne 0) { Fail "could not extract $From" 7 }
    $gcp = Join-Path $Work 'ProjectGCP'
    $turnedGcp = Join-Path $Work 'turned_ProjectGCP'
    & $ps32 -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Apply-GdlEdits.ps1') `
        -Project $gcp -Plan $plan -Output $turnedGcp -InstallDir $InstallDir
    if ($LASTEXITCODE -ne 0) { Fail 'the turn did not apply' 7 }
    & $Python -m gdl.container pack $From $turnedGcp $Output
    if ($LASTEXITCODE -ne 0) { Fail "could not pack $Output" 7 }

    Step 'open it in GUI Designer'
    $gdOurs = $true
    Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-Process -FilePath $gd -ArgumentList ('"' + $Output + '"')
    $leaf = [System.IO.Path]::GetFileName($Output)
    $deadline = (Get-Date).AddSeconds(180)
    $proc = $null
    do {
        Start-Sleep -Seconds 3
        $proc = Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | Select-Object -First 1
        # Get-Process caches the title until Refresh.
        if ($proc) { $proc.Refresh() }
        # A dialog that waits on a person does not go away by itself.
        $why = Get-GdlBlocker
        if ($why) { Fail "GUI Designer did not open ${leaf}: $why" 5 }
    } while ((-not $proc -or $proc.MainWindowTitle -notlike "*$leaf*") -and (Get-Date) -lt $deadline)
    if (-not $proc -or $proc.MainWindowTitle -notlike "*$leaf*") { Fail "GUI Designer did not open $leaf within 180 s.$(Get-GdlShowing -Opening)" 5 }
    Write-Output "  $($proc.MainWindowTitle)"

    Step 'File > Save and Build'
    # The baseline before the click: the invoke blocks on the build, and one
    # taken after can already be the build's (docs/from-scratch.md section 7).
    $buildFrom = (Get-Item -LiteralPath $Output).LastWriteTime
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Invoke-GdlMenu.ps1') -Item 'Save and Build'
    if ($LASTEXITCODE -ne 0) {
        Write-Output '  UIA menu invoke failed; falling back to SendKeys'
        & $ps32 -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Send-GdlKeys.ps1') -Keys '^+b'
        if ($LASTEXITCODE -ne 0) { Fail 'Save and Build could not be started' 7 }
    }
    & $ps32 -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Wait-GdlBuild.ps1') `
        -ProjectFile $Output -TimeoutSeconds $TimeoutSeconds -Since $buildFrom.ToString('o')
    if ($LASTEXITCODE -ne 0) { Fail 'it did not build' 7 }
    Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

    Step 'verify it as a seed'
    & $Python (Join-Path $repo 'tests\verify_seed.py') $Output $Model
    $code = $LASTEXITCODE
    if ($code -ne 0) { Fail "not a $Model seed" $code }
    Write-Output "made $Output"
} finally {
    Pop-Location
}
exit 0
