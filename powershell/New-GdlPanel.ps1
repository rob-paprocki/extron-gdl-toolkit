<#
    Spec in, verified panel out. One command, no hands on GUI Designer.

        powershell\New-GdlPanel.ps1 -Spec examples\panel.json `
            -Donor "seeds\Afterburn 1035.gdl" `
            -Output C:\gdlwork\Boardroom.gdl

    Without -Donor it builds on the seed for the spec's "family", model and
    canvas (python -m gdl.seeds pick), and refuses with the line that makes the
    seed when there is none.

    Everything the Windows half used to need a person for:

        check -> donors -> plan -> apply -> pack -> open -> Save and Build
              -> wait for the build -> verify the built artwork

    Exits 0 only if the verifier passed. Anything else is non-zero, so this can
    gate a run rather than be read.

    Runs the applier under 32-bit PowerShell 5.1 itself, so it does not matter
    which host you start it from.

    It does NOT need the foreground. Save and Build is triggered through
    Invoke-GdlMenu.ps1, which uses UI Automation to click the menu item
    directly, so the pipeline runs while the machine is in use.

    Send-GdlKeys.ps1 is only the fallback if the UIA click fails, and that path
    does need the foreground - it types into whatever holds focus, and a
    pipeline driven from a terminal can never take the foreground away from that
    terminal, because Windows will not hand it to a process that does not
    already have it. So a run that falls back is a run that will stop at that
    step rather than type Ctrl+Shift+B into someone else's window. Send-GdlKeys
    verifies and refuses rather than typing blind.

    It does need a real interactive desktop session - UserInteractive true, with
    a desktop to draw on - not a service or scheduled-task context.

    -KeepOpen leaves GUI Designer up to look at. By default it is closed, since
    an instance holding the file open blocks the next run.

    -IdMap <dir> also writes the panel's ID map - every addressable control's
    ID, type, page, caption and function (python -m gdl.idmap write) - and
    verifies it against the BUILT panel (tests/verify_idmap.py). Navigation is
    checked before anything is built, so a nav to nowhere costs a second, not a
    build.

    -Previous <the previous delivery's idmap folder or idmap.json>, with
    -IdMap, for a revision translated with `gdl.design translate --previous`:
    the map is written with changes.md and changes.json beside it - what a
    program written against the previous map meets (docs/idmap.md section 9).
#>
param(
    [Parameter(Mandatory)][string]$Spec,
    [string]$Donor,
    [Parameter(Mandatory)][string]$Output,
    [string]$IdMap,
    [string]$Previous,
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
. (Join-Path $PSScriptRoot 'GdlBlocker.ps1')
# Timing only reads the host; a host where it cannot (a blocked Add-Type, a
# broken WMI) loses the timing, never the build.
try { . (Join-Path $PSScriptRoot 'GdlTiming.ps1') } catch { Write-Output "  timing unavailable: $($_.Exception.Message)" }

if (-not (Test-Path $ps32)) { throw "32-bit PowerShell 5.1 not found at $ps32" }
if (-not (Test-Path $gd))   { throw "GUI Designer not found at $gd" }
if (-not (Test-Path $Spec)) { throw "not found: $Spec" }
$Spec = (Resolve-Path $Spec).Path
# Relative to where the shell is, as for any cmdlet. [IO.Path]::GetFullPath uses
# the process's own directory, which `cd` does not move in Windows PowerShell,
# so in a shell started elsewhere a relative -Output built the panel there. All
# of them before any Push-Location $repo - the seed pick's below as much as the
# build's - which moves what this reads.
$Output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
# A folder handed to Python loses a trailing backslash, which tab completion
# adds: it escapes the closing quote Windows PowerShell 5.1 puts round an
# argument with a space in it, and the arguments after it run into it.
if ($IdMap) { $IdMap = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($IdMap).TrimEnd('\') }
if ($Previous) { $Previous = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Previous).TrimEnd('\') }
if ($Previous -and -not $IdMap) { throw '-Previous diffs the ID map against the previous one - give -IdMap too' }
# Always an array: an if's empty @() comes back $null, which + appends
# as an empty argument.
$prev = @(if ($Previous) { '--previous', $Previous })

# Build scratch goes on a local disk by default. The repo is often on a mounted
# drive and GUI Designer is slow against one.
if (-not $Work) {
    $Work = Join-Path 'C:\gdlwork' ([System.IO.Path]::GetFileNameWithoutExtension($Output))
}
$Work = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Work)

if (-not $Donor) {
    # The seed for the spec's "family", model and canvas, from the repo root,
    # where gdl imports.
    Push-Location $repo
    try { $picked = & $Python -m gdl.seeds pick $Spec } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "no seed to build on: $($picked -join [Environment]::NewLine)" }
    $Donor = Join-Path $repo ([string]$picked).Trim()
    Write-Output "donor: $Donor"
}
if (-not (Test-Path $Donor)) { throw "not found: $Donor" }
$Donor = (Resolve-Path $Donor).Path

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

# Where the time goes. Each step is timed from its heading to the next, and the
# list is printed as TIMING lines when the run ends, failed or not, so a log
# says what a build cost without a stopwatch beside it (docs/from-scratch.md
# section 5c has what they showed). The Save and Build step adds the finer
# pieces itself: the menu click, the build, the file's last write.
$step = 0
$runStart = Get-Date
$phases = New-Object System.Collections.Specialized.OrderedDictionary
$script:phaseKey = $null
$script:phaseAt = $null
function End-Phase {
    if ($script:phaseKey) {
        $phases[$script:phaseKey] = ((Get-Date) - $script:phaseAt).TotalSeconds
        $script:phaseKey = $null
    }
}
function Step($msg, $key) {
    End-Phase
    $script:step++
    Write-Output ''
    Write-Output "=== [$script:step] $msg"
    $script:phaseKey = if ($key) { $key } else { "step$script:step" }
    $script:phaseAt = Get-Date
    Write-Output ('  at {0:HH:mm:ss}, +{1:N1}s' -f $script:phaseAt, ($script:phaseAt - $runStart).TotalSeconds)
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

    Step 'spec check - ids, canvas, and Extron design rules' 'check'
    Run $Python @('-m', 'gdl.spec', 'check', $Spec) 'spec check'

    if ($IdMap) {
        Step 'ID map check - navigation targets and reachability' 'idmap_check'
        # With -Previous this also refuses a map other than the one the spec
        # kept its IDs against - before the build, not after it.
        Run $Python (@('-m', 'gdl.idmap', 'check', $Spec) + $prev) 'ID map check'
    }

    Step 'donor check - every cloned type available, no name the built panel keeps' 'donors'
    Run $Python @('-m', 'gdl.spec', 'donors', $Spec, $Donor) 'donor check'

    Step 'plan' 'plan'
    # Against the donor: a border it lacks is planned as its own nearest.
    Run $Python @('-m', 'gdl.spec', 'plan', $Spec, $plan, '--donor', $Donor) 'plan'

    Step 'extract the donor' 'extract'
    Run $Python @('-m', 'gdl.container', 'extract', $Donor, $Work) 'extract'

    # A control type the donor has none of, which another seed of its theme
    # carries (the plan's type_donors - a clock on Shockwave's and Turbulence's
    # 320s, from their 525s): that seed's project too, each in a folder of its
    # own, for the applier to clone the type from.
    $typeDonors = @()
    $i = 0
    foreach ($td in @((Get-Content -Raw -Path $plan | ConvertFrom-Json).type_donors)) {
        if ($null -eq $td) { continue }
        $i++
        $dir = Join-Path $Work "type-donor-$i"
        if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
        Run $Python @('-m', 'gdl.container', 'extract', $td.path, $dir) "extract $($td.seed)"
        $typeDonors += "$($td.type)=$(Join-Path $dir 'ProjectGCP')"
        Write-Output "  $($td.type) is cloned from $($td.seed)"
    }
    $typeArgs = @(if ($typeDonors.Count) { '-TypeDonors', ($typeDonors -join ';') })

    Step 'apply the plan (32-bit PowerShell, Extron assemblies are x86)' 'apply'
    Run $ps32 (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                 (Join-Path $PSScriptRoot 'Apply-GdlPlan.ps1'),
                 '-DonorProject', $gcp, '-Plan', $plan, '-Output', $out,
                 '-InstallDir', $InstallDir) + $typeArgs) 'apply'

    Step 'repack' 'pack'
    Run $Python @('-m', 'gdl.container', 'pack', $Donor, $out, $Output) 'pack'

    Step 'open in GUI Designer' 'open'
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
        # A dialog that waits on a person - an Extron Insider login - does not
        # go away by itself, so say which now rather than in three minutes.
        $why = Get-GdlBlocker
        if ($why) { throw "GUI Designer did not open ${leaf}: $why" }
    } while ((-not $proc -or $proc.MainWindowTitle -notlike "*$leaf*") -and (Get-Date) -lt $deadline)
    if (-not $proc -or $proc.MainWindowTitle -notlike "*$leaf*") {
        # Slow or refused: what it shows says which. Handed a donor with no
        # PBProject (a .glt template is a page library, not a project) it came
        # up empty, showing the Project Create Wizard; `gdl.spec donors` now
        # catches that at step 2.
        throw "GUI Designer did not open $leaf within 180s.$(Get-GdlShowing -Opening)"
    }
    Write-Output "  $($proc.MainWindowTitle)"

    Step 'File > Save and Build' 'save_and_build'
    # Capture the baseline BEFORE triggering, because the invoke below blocks on
    # the build modal. Sampling it afterwards can read a mtime the build has
    # already moved, leaving Wait-GdlBuild waiting for a second write that never
    # comes. See its header.
    $buildFrom = (Get-Item $Output).LastWriteTime
    # UIA first: it clicks the menu item directly and needs no focus, so this
    # works while the machine is in use. SendKeys is the fallback and cannot,
    # since a pipeline driven from a terminal can never take the foreground away
    # from that terminal. Both are checked - an unchecked failure here means
    # waiting the full build timeout for a build that never started, which is
    # exactly what it did twice before.
    $load0 = try { Get-GdlLoad } catch { $null }
    $menuAt = Get-Date
    $menuOut = & powershell -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $PSScriptRoot 'Invoke-GdlMenu.ps1') -Item 'Save and Build'
    $menuCode = $LASTEXITCODE
    $menuDone = Get-Date
    $menuOut | ForEach-Object { Write-Output $_ }
    # The click is the moment Invoke-GdlMenu.ps1 stamps just before it invokes
    # the item; the time from $menuAt to it is the script finding the window
    # and the menu, and is not the build's.
    $clickAt = $menuAt
    foreach ($line in @($menuOut)) {
        if ("$line" -match '^clicked at (\S+)') { try { $clickAt = [datetime]::Parse($Matches[1]) } catch { }; break }
    }
    if ($menuCode -ne 0) {
        Write-Output '  UIA menu invoke failed; falling back to SendKeys'
        $clickAt = Get-Date
        Run $ps32 @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    (Join-Path $PSScriptRoot 'Send-GdlKeys.ps1'), '-Keys', '^+b') 'keystroke'
    }
    $waitAt = Get-Date
    Run $ps32 @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                (Join-Path $PSScriptRoot 'Wait-GdlBuild.ps1'),
                '-ProjectFile', $Output, '-TimeoutSeconds', $TimeoutSeconds,
                '-Since', $buildFrom.ToString('o')) 'build'
    $load1 = try { Get-GdlLoad } catch { $null }
    # The time Save and Build takes, to the second: from the click to the last
    # write of the file - not to Wait-GdlBuild's verdict, which comes a few
    # seconds after (its stability check) and 67 s after the click at the
    # earliest (the menu invoke's own timeout).
    $writtenAt = (Get-Item $Output).LastWriteTime
    Write-Output ('SAVE_AND_BUILD click_to_written={0:F1}s menu_find={1:F1}s menu_invoke={2:F1}s wait_started=+{3:F1}s written_at={4:HH:mm:ss.fff}' -f
                  ($writtenAt - $clickAt).TotalSeconds, ($clickAt - $menuAt).TotalSeconds,
                  ($menuDone - $clickAt).TotalSeconds, ($waitAt - $clickAt).TotalSeconds, $writtenAt)
    if ($load0 -and $load1) {
        try { Write-Output (Format-GdlLoad 'save_and_build' $load0 $load1) } catch { Write-Output 'LOAD save_and_build n/a' }
    } else { Write-Output 'LOAD save_and_build n/a' }
    $phases['click_to_written'] = ($writtenAt - $clickAt).TotalSeconds

    if (-not $KeepOpen) {
        Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue |
            Stop-Process -Force -ErrorAction SilentlyContinue
    }

    Step 'verify the build against the plan' 'verify'
    # The gate that matters. A clean build still relocates controls that do not
    # fit, bakes captions into artwork, and drops fills - all reporting 0 errors.
    Run $Python @((Join-Path $repo 'tests\verify_built.py'), $plan, $Output) 'verification'

    if ($IdMap) {
        Step 'write the ID map' 'idmap_write'
        Run $Python (@('-m', 'gdl.idmap', 'write', $Spec, $IdMap) + $prev) 'ID map'

        Step 'verify the ID map against the build' 'idmap_verify'
        # Build renumbers pages, so the names and IDs a programmer will work
        # from are checked against what was built.
        Run $Python @((Join-Path $repo 'tests\verify_idmap.py'), $IdMap, $Output) `
            'ID map verification'
    }

    Write-Output ''
    Write-Output "PANEL BUILT AND VERIFIED -> $Output"
    if ($IdMap) { Write-Output "ID MAP WRITTEN AND VERIFIED -> $IdMap" }
} finally {
    Pop-Location
    End-Phase
    Write-Output ''
    foreach ($k in $phases.Keys) { Write-Output ('TIMING {0} {1:F1}' -f $k, $phases[$k]) }
    Write-Output ('TIMING total {0:F1}' -f ((Get-Date) - $runStart).TotalSeconds)
}
