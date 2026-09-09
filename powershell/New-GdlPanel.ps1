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
    which host you start it from.

    IT NEEDS THE DESKTOP TO ITSELF. Save and Build is driven by SendKeys, which
    types into whatever holds focus, so this script has to bring GUI Designer to
    the foreground - and Windows only grants that to a process that already has
    it or has just received input. Anything else grabbing focus while this runs
    makes the keystroke unsendable, and the run stops at that step rather than
    typing Ctrl+Shift+B into someone else's window.

    In practice that means: do not use the machine while it runs, and do not
    poll it from another shell. Polling was what broke the first two attempts at
    a three-page build - every command run from a terminal brings that terminal
    forward, and the pipeline could not take the foreground back.

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
$Work = [System.IO.Path]::GetFullPath($Work)

# This used to be `Remove-Item $Work -Recurse -Force`, and it deleted the spec it
# was about to build. -Output C:\gdlwork\huddle\Huddle.gdl derives a work
# directory of C:\gdlwork\Huddle, Windows paths are case-insensitive, and the
# spec was sitting in C:\gdlwork\huddle. Refuse the case rather than narrow it:
# a scratch directory that eats its own inputs is worth failing loudly over.
function Test-Inside([string]$child, [string]$parent) {
    $c = [System.IO.Path]::GetFullPath($child).TrimEnd('\')
    $p = [System.IO.Path]::GetFullPath($parent).TrimEnd('\')
    return $c.Equals($p, 'OrdinalIgnoreCase') -or
           $c.StartsWith($p + '\', 'OrdinalIgnoreCase')
}
foreach ($pair in @(@{n = 'spec'; v = $Spec}, @{n = 'donor'; v = $Donor})) {
    if (Test-Inside $pair.v $Work) {
        throw ("the $($pair.n) is inside the work directory ($Work), which this " +
               'script clears. Pass -Work somewhere else, or move the file out.')
    }
}

# Clear only what this script writes, so an unrelated file in a reused scratch
# directory survives.
New-Item -ItemType Directory -Force -Path $Work | Out-Null
foreach ($n in 'plan.json', 'ProjectGCP', 'gen_ProjectGCP') {
    $p = Join-Path $Work $n
    if (Test-Path $p) { Remove-Item $p -Force }
}
Get-ChildItem -Path $Work -Filter '*.tgz4' -File -ErrorAction SilentlyContinue |
    Remove-Item -Force
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
        # Distinguish "slow" from "refused". GUI Designer does not report a file
        # it declines to open - it comes up empty and shows the Project Create
        # Wizard, which from out here looks identical to a hang. The usual cause
        # is a donor with no PBProject (a .glt template is a page library, not a
        # project); `gdl.spec donors` now catches that at step 2.
        $wizard = $null -ne (Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue)
        $hint = if ($wizard) {
            " GUI Designer is running but has not opened it - check for a Project " +
            "Create Wizard on screen, which means it rejected the file rather than " +
            "being slow."
        } else { '' }
        throw "GUI Designer did not open $leaf within 180s.$hint"
    }
    Write-Output "  $($proc.MainWindowTitle)"

    Step 'File > Save and Build'
    # UIA first: it clicks the menu item directly and needs no focus, so this
    # works while the machine is in use. SendKeys is the fallback and cannot,
    # since a pipeline driven from a terminal can never take the foreground away
    # from that terminal. Both are checked - an unchecked failure here means
    # waiting the full build timeout for a build that never started, which is
    # exactly what it did twice before.
    & powershell -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $PSScriptRoot 'Invoke-GdlMenu.ps1') -Item 'Save and Build'
    if ($LASTEXITCODE -ne 0) {
        Write-Output '  UIA menu invoke failed; falling back to SendKeys'
        Run $ps32 @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    (Join-Path $PSScriptRoot 'Send-GdlKeys.ps1'), '-Keys', '^+b') 'keystroke'
    }
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
