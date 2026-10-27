<#
    The format probes of backlog package 2.1, on GUI Designer 1.28, in one
    unattended session. From the repo root:

        powershell -NoProfile -ExecutionPolicy Bypass -File examples\probes-128\Run-Probes128.ps1

    Needs what New-GdlPanel.ps1 needs: Windows, GUI Designer installed, an
    interactive desktop (a console or Remote Desktop session that stays
    unlocked), 32-bit Windows PowerShell 5.1 beside this one, and Python. It
    does not need the foreground. Start it with GUI Designer closed and leave
    the desktop alone for its length - an hour or two; examples\probes-128\README.md
    says which probe takes how long.

    One probe after another, never two GUI Designers: each build opens GUI
    Designer, builds, and closes it, as New-GdlPanel.ps1 does. A probe that
    fails is written down and the next one runs. Everything lands in
    out\probes-128\<probe>\ and one summary in out\probes-128\summary.txt,
    which this rewrites after every probe, so a run that is cut short leaves
    what it had. Send the whole out\probes-128 folder back; `python
    examples\probes-128\read_probes.py out\probes-128` reads it.

    Every input is a path inside the repo, relative to its root - the table in
    examples\probes-128\README.md.

    -Only <probe names> runs some; -Skip leaves some out. The names:
      format-probes  renumber-seed  renumber-generated  borders
      horizontal-slider  reference-counts  twins-1535
#>
param(
    [string]$Out = 'out\probes-128',
    # Build scratch on a local disk, as New-GdlPanel.ps1 keeps it: GUI Designer
    # is slow against a mounted drive.
    [string]$Work = 'C:\gdlwork\probes-128',
    [string[]]$Only,
    [string[]]$Skip,
    [string]$Python = 'python',
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer',
    [int]$TimeoutSeconds = 900,
    # The project New-FormatProbes.ps1 authors its three tests on. The same
    # fixture its 1.27 and 1.28 runs used; a seed stands in where the client
    # fixtures are not (the archive only), and the summary says so.
    [string]$FormatFixture = 'fixtures\gdl\client-boardroom-2.0.0.gdl'
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$ps32 = 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
$gd = Join-Path $InstallDir 'GUI Designer.exe'
$ps = Join-Path $repo 'powershell'
$here = Join-Path $repo 'examples\probes-128'
. (Join-Path $ps 'GdlBlocker.ps1')

# ---------------------------------------------------------------- inputs ----
# Every input, by its path from the repo root.
$In = [ordered]@{
    FormatProbes      = 'powershell\New-FormatProbes.ps1'
    FormatFixtureSeed = 'seeds\Afterburn 1035.gdl'
    RenumberSeed      = 'seeds\Afterburn 1035.gdl'
    RenumberSeedEdits = 'examples\probes-128\renumber-seed.json'
    HuddleSpec        = 'examples\huddle-functions.json'
    HuddleDonor       = 'seeds\Afterburn 1035.gdl'
    RenumberGenEdits  = 'examples\probes-128\renumber-generated.json'
    BorderSpec        = 'examples\probes-128\specs\afterburn-borders.json'
    BorderTable       = 'examples\probes-128\borders.json'
    BorderDonor       = 'seeds\Afterburn 1035.gdl'
    SliderSpec        = 'examples\probes-128\specs\shockwave-hslider.json'
    SliderDonor       = 'seeds\Shockwave 1035.gdl'
    GroupsSpec        = 'examples\probes-128\specs\afterburn-groups.json'
    GroupsDonor       = 'seeds\Afterburn 1035.gdl'
    TwinSpec          = 'examples\probes-128\specs\shockwave-1535-twins.json'
    TwinDonor         = 'seeds\Shockwave 1535.gdl'
}
$Probes = @('format-probes', 'borders', 'horizontal-slider', 'reference-counts',
            'renumber-seed', 'renumber-generated', 'twins-1535')

Set-Location $repo
if ($Only) { $Probes = @($Probes | Where-Object { $Only -contains $_ }) }
if ($Skip) { $Probes = @($Probes | Where-Object { $Skip -notcontains $_ }) }
$Out = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out)
$Work = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Work)

if (-not (Test-Path $ps32)) { throw "32-bit PowerShell 5.1 not found at $ps32" }
if (-not (Test-Path $gd))   { throw "GUI Designer not found at $gd" }
if (-not [Environment]::UserInteractive) { throw 'needs an interactive desktop session' }
foreach ($k in $In.Keys) {
    if ($k -eq 'FormatFixtureSeed') { continue }
    if (-not (Test-Path (Join-Path $repo $In[$k]))) { throw "input missing: $($In[$k])" }
}
New-Item -ItemType Directory -Force -Path $Out, $Work | Out-Null

# ----------------------------------------------------------------- helpers --
$summaryPath = Join-Path $Out 'summary.txt'
$results = New-Object System.Collections.ArrayList
$gdVersion = try { (Get-Item $gd).VersionInfo.FileVersion } catch { 'unknown' }
$rev = try { (& git -C $repo rev-parse --short HEAD 2>$null) } catch { 'unknown' }

function Write-Summary([string]$tail) {
    $lines = @(
        'Format probes on GUI Designer, package 2.1 (examples/probes-128/README.md)',
        "started   $script:Started",
        "host      $env:COMPUTERNAME  GUI Designer $gdVersion  repo $rev",
        "folder    $Out",
        '')
    foreach ($r in $results) {
        $lines += ('{0,-20} {1,-7} {2,6:N0}s  {3}' -f $r.Name, $r.Status, $r.Seconds, $r.Note)
    }
    if ($tail) { $lines += ''; $lines += $tail }
    Set-Content -Path $summaryPath -Value $lines -Encoding UTF8
}
$script:Started = Get-Date -Format 's'

$script:Log = $null
function Say([string]$m) {
    $line = ('{0:HH:mm:ss}  {1}' -f (Get-Date), $m)
    Write-Host $line
    if ($script:Log) { Add-Content -Path $script:Log -Value $line -Encoding UTF8 }
}

# A command, its output to the screen and the probe's log, and a thrown error
# when it exits non-zero. Windows PowerShell 5.1 turns a native command's
# stderr into error records under 2>&1, so errors are not fatal inside it.
function Run([string]$what, [string]$exe, [string[]]$argv, [switch]$AllowFail) {
    Say "--- $what"
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $exe @argv 2>&1 | ForEach-Object { Say ("    " + "$_") }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    if ($code -ne 0) {
        if ($AllowFail) { Say "    ($what exited $code; carried on)"; return $code }
        throw "$what failed (exit $code)"
    }
    return 0
}
function Py([string]$what, [string[]]$argv, [switch]$AllowFail) {
    Run $what $Python $argv -AllowFail:$AllowFail
}
function Ps32([string]$what, [string]$script, [string[]]$argv) {
    Run $what $ps32 (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script) + $argv)
}

function Stop-GuiDesigner {
    Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

function Start-Watcher([string]$dir) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $stop = Join-Path $dir 'stop'
    if (Test-Path $stop) { Remove-Item $stop -Force }
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
           ('"' + (Join-Path $here 'Watch-BuildManager.ps1') + '"'),
           '-OutDir', ('"' + $dir + '"'), '-StopFile', ('"' + $stop + '"'))
    Start-Process -FilePath 'powershell' -ArgumentList $a -WindowStyle Hidden -PassThru
}
function Stop-Watcher($proc, [string]$dir) {
    if (-not $proc) { return }
    Set-Content -Path (Join-Path $dir 'stop') -Value 'stop'
    if (-not $proc.WaitForExit(15000)) { $proc.Kill() }
}

# Open a .gdl in GUI Designer, Save and Build it, wait for the .gdl to be
# rewritten, close GUI Designer. The steps of New-GdlPanel.ps1, for the probes
# that author a file it does not (the format probes, an edit, a registry
# rewritten), with the Build Manager watcher beside it. Throws on any failure.
function Build-Gdl([string]$gdl, [string]$dir) {
    $leaf = [System.IO.Path]::GetFileName($gdl)
    $bm = Join-Path $dir ('buildmgr-' + [System.IO.Path]::GetFileNameWithoutExtension($gdl))
    Say "--- open $leaf in GUI Designer, Save and Build"
    Stop-GuiDesigner
    $watch = Start-Watcher $bm
    try {
        Start-Process -FilePath $gd -ArgumentList ('"' + $gdl + '"')
        $deadline = (Get-Date).AddSeconds(180)
        $proc = $null
        do {
            Start-Sleep -Seconds 3
            $proc = Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($proc) { $proc.Refresh() }
            $why = Get-GdlBlocker
            if ($why) { throw "GUI Designer did not open ${leaf}: $why" }
        } while ((-not $proc -or $proc.MainWindowTitle -notlike "*$leaf*") -and (Get-Date) -lt $deadline)
        if (-not $proc -or $proc.MainWindowTitle -notlike "*$leaf*") {
            throw "GUI Designer did not open $leaf within 180s.$(Get-GdlShowing -Opening)"
        }
        Say "    $($proc.MainWindowTitle)"
        # The baseline before the trigger, which blocks on the build modal.
        $from = (Get-Item $gdl).LastWriteTime
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ps 'Invoke-GdlMenu.ps1') -Item 'Save and Build' 2>&1 |
            ForEach-Object { Say ("    " + "$_") }
        $menu = $LASTEXITCODE
        $ErrorActionPreference = $old
        if ($menu -ne 0) {
            Say '    UIA menu invoke failed; falling back to SendKeys'
            Ps32 'send Ctrl+Shift+B' (Join-Path $ps 'Send-GdlKeys.ps1') @('-Keys', '^+b')
        }
        Ps32 'wait for the build' (Join-Path $ps 'Wait-GdlBuild.ps1') @(
            '-ProjectFile', $gdl, '-TimeoutSeconds', "$TimeoutSeconds", '-Since', $from.ToString('o'))
    } finally {
        Stop-GuiDesigner
        Stop-Watcher $watch $bm
    }
}

# A spec built by New-GdlPanel.ps1, with the watcher round it. Returns nothing;
# a non-zero exit (the verifier's included) is a thrown error, after the files
# are kept.
function Build-Spec([string]$spec, [string]$donor, [string]$output, [string]$dir, [string[]]$extra) {
    $bm = Join-Path $dir ('buildmgr-' + [System.IO.Path]::GetFileNameWithoutExtension($output))
    $watch = Start-Watcher $bm
    try {
        $args2 = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $ps 'New-GdlPanel.ps1'),
                   '-Spec', $spec, '-Donor', $donor, '-Output', $output,
                   '-Work', (Join-Path $Work ([System.IO.Path]::GetFileNameWithoutExtension($output))),
                   '-InstallDir', $InstallDir, '-TimeoutSeconds', "$TimeoutSeconds", '-Python', $Python) + $extra
        Run "New-GdlPanel.ps1 -Spec $spec" 'powershell' $args2
    } finally {
        $built = Join-Path $Work ([System.IO.Path]::GetFileNameWithoutExtension($output))
        # The plan the build was held to, kept beside the results: the reader and a second stage compare against it.
        if (Test-Path (Join-Path $built 'plan.json')) {
            Copy-Item (Join-Path $built 'plan.json') ($output -replace '\.gdl$', '.plan.json') -Force
        }
        Stop-GuiDesigner
        Stop-Watcher $watch $bm
    }
}

function Rel([string]$p) { if ($p.StartsWith($repo)) { $p.Substring($repo.Length).TrimStart('\') } else { $p } }
function Extract([string]$gdl, [string]$to) {
    if (-not $to.StartsWith($Work, 'OrdinalIgnoreCase')) { throw "refusing to clear $to - it is outside $Work" }
    if (Test-Path $to) { Remove-Item $to -Recurse -Force }
    Py "extract $(Rel $gdl)" @('-m', 'gdl.container', 'extract', $gdl, $to)
}

# An edit plan applied to a .gdl, packed, built and verified: the edit path of
# docs/editing.md, for the renumber probes. `$before` is kept as it was.
function Edit-Build([string]$source, [string]$edits, [string]$dir, [string]$tag) {
    $before = Join-Path $dir "$tag-before.gdl"
    $after = Join-Path $dir "$tag-edited.gdl"
    $plan = Join-Path $dir "$tag-plan.json"
    $w = Join-Path $Work $tag
    Copy-Item $source $before -Force
    Py 'edit check' @('-m', 'gdl.edit', 'check', $edits, $before)
    Py 'edit plan' @('-m', 'gdl.edit', 'plan', $edits, $before, $plan)
    Extract $before $w
    Ps32 'apply the edit plan (Apply-GdlEdits.ps1)' (Join-Path $ps 'Apply-GdlEdits.ps1') @(
        (Join-Path $w 'ProjectGCP'), $plan, (Join-Path $w 'edited_ProjectGCP'), '-InstallDir', $InstallDir)
    Py 'repack' @('-m', 'gdl.container', 'pack', $before, (Join-Path $w 'edited_ProjectGCP'), $after)
    Copy-Item $after (Join-Path $dir "$tag-edited.pre.gdl") -Force
    Build-Gdl $after $dir
    Py 'idmap of the file before' @('-m', 'gdl.idmap', 'from-built', $before, (Join-Path $dir "$tag-idmap-before"))
    Py 'idmap of the built file' @('-m', 'gdl.idmap', 'from-built', $after, (Join-Path $dir "$tag-idmap-after"))
    Py 'idmap diff' @('-m', 'gdl.idmap', 'diff', (Join-Path $dir "$tag-idmap-before"), (Join-Path $dir "$tag-idmap-after")) -AllowFail
    Py 'verify the build against the edit plan' @((Join-Path $repo 'tests\verify_built.py'), $plan, $after)
}

# ------------------------------------------------------------------ probes ---
function Probe-FormatProbes([string]$dir) {
    $fixture = Join-Path $repo $FormatFixture
    if (-not (Test-Path $fixture)) {
        Say "the fixture $FormatFixture is not here (the client fixtures are in the archive only); using $($In.FormatFixtureSeed)"
        $fixture = Join-Path $repo $In.FormatFixtureSeed
        Set-Content -Path (Join-Path $dir 'fixture.txt') -Value "seed: $($In.FormatFixtureSeed)" -Encoding UTF8
    } else {
        Set-Content -Path (Join-Path $dir 'fixture.txt') -Value "fixture: $FormatFixture" -Encoding UTF8
    }
    $w = Join-Path $Work 'format'
    Extract $fixture $w
    Ps32 'author the three probes (New-FormatProbes.ps1)' (Join-Path $repo $In.FormatProbes) @('-Repo', $repo, '-Work', $w)
    foreach ($t in 'A', 'B', 'C') {
        $gdl = Join-Path $dir "test$t.gdl"
        Py "pack test$t" @('-m', 'gdl.container', 'pack', $fixture, (Join-Path $w "test${t}_ProjectGCP"), $gdl)
        Copy-Item $gdl (Join-Path $dir "test$t.pre.gdl") -Force
    }
    $fails = @()
    foreach ($t in 'A', 'B', 'C') {
        try { Build-Gdl (Join-Path $dir "test$t.gdl") $dir }
        catch { Say "test $t did not build: $($_.Exception.Message)"; $fails += $t }
    }
    if ($fails) { throw "no build for test $($fails -join ', ')" }
}

function Probe-Borders([string]$dir) {
    $spec = Join-Path $repo $In.BorderSpec
    $donor = Join-Path $repo $In.BorderDonor
    $plan = Join-Path $dir 'plan.json'
    $bound = Join-Path $dir 'plan-bound.json'
    $w = Join-Path $Work 'borders'
    $out = Join-Path $dir 'borders.gdl'
    Py 'spec check' @('-m', 'gdl.spec', 'check', $spec)
    Py 'spec plan' @('-m', 'gdl.spec', 'plan', $spec, $plan, '--donor', $donor)
    Py 'rebind the plan to the appended resources' @((Join-Path $here 'probe_tools.py'), 'bind-borders', $plan,
                                                     (Join-Path $repo $In.BorderTable), $bound)
    Extract $donor $w
    Ps32 'append the border resources' (Join-Path $here 'Add-BorderResources.ps1') @(
        '-Project', (Join-Path $w 'ProjectGCP'), '-Table', (Join-Path $repo $In.BorderTable),
        '-Output', (Join-Path $w 'res_ProjectGCP'), '-InstallDir', $InstallDir)
    Ps32 'apply the plan' (Join-Path $ps 'Apply-GdlPlan.ps1') @(
        '-DonorProject', (Join-Path $w 'res_ProjectGCP'), '-Plan', $bound,
        '-Output', (Join-Path $w 'gen_ProjectGCP'), '-InstallDir', $InstallDir)
    Py 'repack' @('-m', 'gdl.container', 'pack', $donor, (Join-Path $w 'gen_ProjectGCP'), $out)
    Copy-Item $out (Join-Path $dir 'borders.pre.gdl') -Force
    Build-Gdl $out $dir
    Py 'verify the build against the plan' @((Join-Path $repo 'tests\verify_built.py'), $bound, $out)
}

function Probe-HorizontalSlider([string]$dir) {
    Build-Spec (Join-Path $repo $In.SliderSpec) (Join-Path $repo $In.SliderDonor) (Join-Path $dir 'hslider.gdl') $dir @()
}

function Probe-ReferenceCounts([string]$dir) {
    $stage1 = Join-Path $dir 'stage1.gdl'
    $stage2 = Join-Path $dir 'stage2.gdl'
    Build-Spec (Join-Path $repo $In.GroupsSpec) (Join-Path $repo $In.GroupsDonor) $stage1 $dir @()
    $w = Join-Path $Work 'refcount'
    Extract $stage1 $w
    Ps32 'the registry as built, then rewritten' (Join-Path $here 'Set-ReferenceCounts.ps1') @(
        '-Project', (Join-Path $w 'ProjectGCP'), '-Counts', 'One=46;Three=0;Five=1',
        '-Output', (Join-Path $w 'counts_ProjectGCP'), '-InstallDir', $InstallDir)
    Py 'repack' @('-m', 'gdl.container', 'pack', $stage1, (Join-Path $w 'counts_ProjectGCP'), $stage2)
    Copy-Item $stage2 (Join-Path $dir 'stage2.pre.gdl') -Force
    Build-Gdl $stage2 $dir
    # The plan the first stage was built from, held to the second build as well:
    # a registry rewritten must not have cost the panel a binding.
    Py 'verify the second build against the plan' @((Join-Path $repo 'tests\verify_built.py'),
        (Join-Path $dir 'stage1.plan.json'), $stage2) -AllowFail
}

function Probe-RenumberSeed([string]$dir) {
    Edit-Build (Join-Path $repo $In.RenumberSeed) (Join-Path $repo $In.RenumberSeedEdits) $dir 'seed'
}

function Probe-RenumberGenerated([string]$dir) {
    $base = Join-Path $dir 'huddle.gdl'
    Build-Spec (Join-Path $repo $In.HuddleSpec) (Join-Path $repo $In.HuddleDonor) $base $dir @('-IdMap', (Join-Path $dir 'huddle-idmap'))
    Edit-Build $base (Join-Path $repo $In.RenumberGenEdits) $dir 'huddle'
}

function Probe-Twins1535([string]$dir) {
    Build-Spec (Join-Path $repo $In.TwinSpec) (Join-Path $repo $In.TwinDonor) (Join-Path $dir 'twins-1535.gdl') $dir `
        @('-IdMap', (Join-Path $dir 'idmap'))
}

# -------------------------------------------------------------------- run ----
Stop-GuiDesigner
foreach ($name in $Probes) {
    $dir = Join-Path $Out $name
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $script:Log = Join-Path $dir 'probe.log'
    Set-Content -Path $script:Log -Value '' -Encoding UTF8
    $t0 = Get-Date
    $status = 'ok'
    $note = ''
    Say "=========== $name"
    try {
        switch ($name) {
            'format-probes'      { Probe-FormatProbes $dir }
            'borders'            { Probe-Borders $dir }
            'horizontal-slider'  { Probe-HorizontalSlider $dir }
            'reference-counts'   { Probe-ReferenceCounts $dir }
            'renumber-seed'      { Probe-RenumberSeed $dir }
            'renumber-generated' { Probe-RenumberGenerated $dir }
            'twins-1535'         { Probe-Twins1535 $dir }
        }
    } catch {
        $status = 'FAILED'
        $note = "$($_.Exception.Message)"
        Say "FAILED: $note"
    }
    Stop-GuiDesigner
    [void]$results.Add([pscustomobject]@{
        Name = $name; Status = $status; Seconds = ((Get-Date) - $t0).TotalSeconds; Note = $note })
    $script:Log = $null
    Write-Summary ''
}

# What each probe's files show, read by the reader the summary ends with.
$read = ''
try {
    $read = (& $Python (Join-Path $here 'read_probes.py') $Out 2>&1 | Out-String)
} catch { $read = "read_probes.py failed: $($_.Exception.Message)" }
Write-Summary ("--- read_probes.py out\probes-128`r`n" + $read)
Write-Host ''
Write-Host "summary: $summaryPath"
$bad = @($results | Where-Object { $_.Status -ne 'ok' }).Count
exit $(if ($bad) { 1 } else { 0 })
