<#
    Spec in, verified panel out. One command, no hands on GUI Designer.

        powershell\New-GdlPanel.ps1 -Spec examples\panel.json `
            -Donor fixtures\gdl\Interface__alt_....gdl `
            -Output C:\gdlwork\Boardroom.gdl

    Everything the Windows half used to need a person for:

        check -> donors -> plan -> apply -> pack -> open -> Save and Build
              -> wait for the build -> verify the built artwork

    Exits 0 only if the verifier passed. Anything else is non-zero, so this can
    gate a run rather than be read.

    Runs the applier under 32-bit PowerShell 5.1 itself, so it does not matter
    which host you start it from. It does need a desktop - GUI Designer draws a
    build dialog, and BuildProject() is not callable headlessly.

    -KeepOpen leaves GUI Designer up to look at. By default it is closed, since
    an instance holding the file open blocks the next run.
#>
param(
    [Parameter(Mandatory)][string]$Spec,
    [Parameter(Mandatory)][string]$Donor,
    [Parameter(Mandatory)][string]$Output,
    [string]$Work,
    [string]$Python = 'python',
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer',
    [int]$TimeoutSeconds = 900,
    [switch]$KeepOpen
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$ps32 = 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
$gd = Join-Path $InstallDir 'GUI Designer.exe'

if (-not (Test-Path $ps32)) { throw "32-bit PowerShell 5.1 not found at $ps32" }
if (-not (Test-Path $gd))   { throw "GUI Designer not found at $gd" }
foreach ($p in @($Spec, $Donor)) {
    if (-not (Test-Path $p)) { throw "not found: $p" }
}

$Spec   = (Resolve-Path $Spec).Path
$Donor  = (Resolve-Path $Donor).Path
$Output = [System.IO.Path]::GetFullPath($Output)

# Build scratch goes on a local disk by default. The repo is often on a mounted
# drive and GUI Designer is slow against one.
if (-not $Work) {
    $Work = Join-Path 'C:\gdlwork' ([System.IO.Path]::GetFileNameWithoutExtension($Output))
}
if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Work | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $Output -Parent) | Out-Null

$step = 0
function Step($msg) {
    $script:step++
    Write-Output ''
    Write-Output "=== [$script:step] $msg"
}
function Run($exe, $arguments, $what) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" }
}

Push-Location $repo
try {
    $plan = Join-Path $Work 'plan.json'
    $gcp  = Join-Path $Work 'ProjectGCP'
    $out  = Join-Path $Work 'gen_ProjectGCP'

    Step 'spec check - ids, canvas, and Extron design rules'
    Run $Python @('-m', 'gdl.spec', 'check', $Spec) 'spec check'

    Step 'donor check - every cloned type available, no page name collision'
    Run $Python @('-m', 'gdl.spec', 'donors', $Spec, $Donor) 'donor check'

    Step 'plan'
    Run $Python @('-m', 'gdl.spec', 'plan', $Spec, $plan) 'plan'

    Step 'extract the donor'
    Run $Python @('-m', 'gdl.container', 'extract', $Donor, $Work) 'extract'

    Step 'apply the plan (32-bit PowerShell, Extron assemblies are x86)'
    Run $ps32 @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                (Join-Path $PSScriptRoot 'Apply-GdlPlan.ps1'),
                '-DonorProject', $gcp, '-Plan', $plan, '-Output', $out,
                '-InstallDir', $InstallDir) 'apply'

    Step 'repack'
    Run $Python @('-m', 'gdl.container', 'pack', $Donor, $out, $Output) 'pack'

    Step 'open in GUI Designer'
    Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-Process -FilePath $gd -ArgumentList ('"' + $Output + '"')
    $leaf = [System.IO.Path]::GetFileName($Output)
    $deadline = (Get-Date).AddSeconds(180)
    $proc = $null
    do {
        Start-Sleep -Seconds 3
        $proc = Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue |
                Select-Object -First 1
        # Get-Process caches the title; without Refresh it reads 'GUI Designer'
        # forever and this loop never exits.
        if ($proc) { $proc.Refresh() }
    } while ((-not $proc -or $proc.MainWindowTitle -notlike "*$leaf*") -and (Get-Date) -lt $deadline)
    if (-not $proc -or $proc.MainWindowTitle -notlike "*$leaf*") {
        throw "GUI Designer did not open $leaf within 180s"
    }
    Write-Output "  $($proc.MainWindowTitle)"

    Step 'File > Save and Build'
    & $ps32 @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
              (Join-Path $PSScriptRoot 'Send-GdlKeys.ps1'), '-Keys', '^+b')
    Run $ps32 @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                (Join-Path $PSScriptRoot 'Wait-GdlBuild.ps1'),
                '-ProjectFile', $Output, '-TimeoutSeconds', $TimeoutSeconds) 'build'

    if (-not $KeepOpen) {
        Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue |
            Stop-Process -Force -ErrorAction SilentlyContinue
    }

    Step 'verify the build against the plan'
    # The gate that matters. A clean build still relocates controls that do not
    # fit, bakes captions into artwork, and drops fills - all reporting 0 errors.
    Run $Python @((Join-Path $repo 'tests\verify_built.py'), $plan, $Output) 'verification'

    Write-Output ''
    Write-Output "PANEL BUILT AND VERIFIED -> $Output"
} finally {
    Pop-Location
}
