<#
    Build a queue of specs one after another, timing each, for the question
    "where does Save and Build's time go" (docs/from-scratch.md section 5c).

        powershell -NoProfile -File tools\Run-BuildTiming.ps1 `
            -Queue C:\scratch\queue.tsv -OutDir C:\scratch\runs

    The queue is a tab-separated file, one run a line, '#' lines ignored:

        <run id> <TAB> <spec path> <TAB> <extra builds>

    Each run is New-GdlPanel.ps1 on the spec, on `-Donor` (default: the
    Afterburn 1035 seed), with the host settled first - the whole machine averaging
    under 35% busy and the antivirus engine under a quarter of a core for
    -SettleSeconds - and Sample-GdlHost.ps1 running beside it, so
    the log and the trace say what GUI Designer, the antivirus engine and the
    rest of the host were doing. <extra builds> is how many more times to Save
    and Build the same open project in the same GUI Designer session after the
    first: the first build is on a freshly started GUI Designer, as every
    New-GdlPanel.ps1 run is, and the later ones are not.

    Per run, in -OutDir: <id>.log (the whole run, with the extra builds'
    SAVE_AND_BUILD and LOAD lines), <id>.trace.csv, <id>.plan.json and
    <id>.meta.json. A run whose log already ends in a TIMING total line is
    skipped, so the queue can be started again after a stop. The built files
    are not kept - tools\timing_table.py reads the logs.

    -WatchFiles also runs Watch-GdlFiles.ps1 beside a build, for <id>.files.tsv:
    the folders it wrote into. That run is for the file counts, not for the
    timing: the watcher is a few percent of a core.

    It does not touch GUI Designer's settings, the antivirus or any other
    configuration: it reads the host's counters and runs the scripts.
#>
param(
    [Parameter(Mandatory)][string]$Queue,
    [Parameter(Mandatory)][string]$OutDir,
    [string]$Donor,
    [string]$Work = 'C:\gdlwork\timing',
    [string]$Python = 'python',
    [switch]$IdMap,
    [switch]$WatchFiles,
    [int]$SampleSeconds = 5,
    [int]$SettleSeconds = 20,
    [int]$MaxSettleSeconds = 120,
    [int]$BuildTimeoutSeconds = 900
)

# Continue, not Stop: a child's stderr, merged below with 2>&1, would end the
# whole queue in Windows PowerShell 5.1 at its first line.
$ErrorActionPreference = 'Continue'
$repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $repo 'powershell\GdlTiming.ps1')
$ps32 = 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
if (-not $Donor) { $Donor = Join-Path $repo 'seeds\Afterburn 1035.gdl' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path $Work | Out-Null

# The host is quiet when everything on it together averages under 35% of its
# processors and the antivirus engine under a quarter of a core, over
# -SettleSeconds. This machine idles at 15% to 25% with Claude Code, the
# remote-support client and the sampler itself running, so a lower bar is never
# met; the engine's rate is there because it scans what the last run left
# behind for a while after, which would be charged to this one. Returns the
# seconds waited, the busy share and the engine's rate it settled at; gives up
# after -MaxSettleSeconds and says so.
function Wait-HostQuiet {
    $start = Get-Date
    $busyW = New-Object System.Collections.Generic.Queue[double]
    $avW = New-Object System.Collections.Generic.Queue[double]
    $need = [math]::Max(3, [int]($SettleSeconds / 2))
    $prev = Get-GdlLoad
    $busy = 100.0; $av = 9.0
    while (((Get-Date) - $start).TotalSeconds -lt $MaxSettleSeconds) {
        Start-Sleep -Seconds 2
        $now = Get-GdlLoad
        $d = Get-GdlLoadDelta $prev $now
        $prev = $now
        $busyW.Enqueue($d.SysBusy)
        $avW.Enqueue($(if ($d.Wall -gt 0) { $d.AvCpu / $d.Wall } else { 0 }))
        while ($busyW.Count -gt $need) { [void]$busyW.Dequeue(); [void]$avW.Dequeue() }
        $busy = ($busyW | Measure-Object -Average).Average
        $av = ($avW | Measure-Object -Average).Average
        if ($busyW.Count -ge $need -and $busy -lt 35 -and $av -lt 0.25) {
            return [pscustomobject]@{ Waited = ((Get-Date) - $start).TotalSeconds; Busy = $busy; Av = $av; Quiet = $true }
        }
    }
    return [pscustomobject]@{ Waited = ((Get-Date) - $start).TotalSeconds; Busy = $busy; Av = $av; Quiet = $false }
}

# One more Save and Build of the project GUI Designer has open: the same
# calls New-GdlPanel.ps1 makes, and the same SAVE_AND_BUILD and LOAD lines.
function Invoke-ExtraBuild([string]$Output, [int]$k) {
    $from = (Get-Item $Output).LastWriteTime
    $l0 = Get-GdlLoad
    $menuAt = Get-Date
    $menuOut = & powershell -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $repo 'powershell\Invoke-GdlMenu.ps1') -Item 'Save and Build'
    $menuCode = $LASTEXITCODE
    $menuDone = Get-Date
    $menuOut | ForEach-Object { "$_" }
    $clickAt = $menuAt
    foreach ($line in @($menuOut)) {
        if ("$line" -match '^clicked at (\S+)') { $clickAt = [datetime]::Parse($Matches[1]); break }
    }
    if ($menuCode -ne 0) { "extra build ${k}: menu invoke failed (exit $menuCode)"; return }
    $waitAt = Get-Date
    & $ps32 -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'powershell\Wait-GdlBuild.ps1') `
        -ProjectFile $Output -TimeoutSeconds $BuildTimeoutSeconds -Since $from.ToString('o') |
        ForEach-Object { "$_" }
    $ok = ($LASTEXITCODE -eq 0)
    $l1 = Get-GdlLoad
    $writtenAt = (Get-Item $Output).LastWriteTime
    ('SAVE_AND_BUILD extra={0} click_to_written={1:F1}s menu_find={2:F1}s menu_invoke={3:F1}s wait_started=+{4:F1}s written_at={5:HH:mm:ss.fff} ok={6}' -f
        $k, ($writtenAt - $clickAt).TotalSeconds, ($clickAt - $menuAt).TotalSeconds,
        ($menuDone - $clickAt).TotalSeconds, ($waitAt - $clickAt).TotalSeconds, $writtenAt, $ok)
    Format-GdlLoad "extra$k" $l0 $l1
}

foreach ($raw in Get-Content -Path $Queue) {
    if (-not $raw.Trim() -or $raw.TrimStart().StartsWith('#')) { continue }
    $f = $raw -split "`t"
    $id = $f[0].Trim()
    $spec = $f[1].Trim()
    $extra = if ($f.Count -gt 2 -and $f[2].Trim()) { [int]$f[2] } else { 0 }
    $log = Join-Path $OutDir "$id.log"
    if ((Test-Path $log) -and (Select-String -Path $log -Pattern '^TIMING total ' -Quiet)) {
        Write-Host "skip $id (done)"
        continue
    }
    Write-Host ("{0:HH:mm:ss} {1}: settling" -f (Get-Date), $id)
    $quiet = Wait-HostQuiet
    $pre = Get-GdlLoad
    $runWork = Join-Path $Work $id
    if (Test-Path $runWork) { Remove-Item $runWork -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $runWork | Out-Null
    $output = Join-Path $runWork "$id.gdl"
    $trace = Join-Path $OutDir "$id.trace.csv"
    $stop = Join-Path $runWork 'sampler.stop'
    $sampler = Start-Process -FilePath powershell -PassThru -WindowStyle Hidden -ArgumentList @(
        '-NoProfile', '-File', (Join-Path $PSScriptRoot 'Sample-GdlHost.ps1'),
        '-Out', $trace, '-Stop', $stop, '-IntervalSeconds', $SampleSeconds)

    # -WatchFiles: where the build writes (Watch-GdlFiles.ps1), beside the
    # timing - a run that does it is not one to fit, and says so in its notes.
    $watchStop = Join-Path $runWork 'watcher.stop'
    $watcher = $null
    if ($WatchFiles) {
        $watcher = Start-Process -FilePath powershell -PassThru -WindowStyle Hidden -ArgumentList @(
            '-NoProfile', '-File', (Join-Path $PSScriptRoot 'Watch-GdlFiles.ps1'),
            '-Out', (Join-Path $OutDir "$id.files.tsv"), '-Stop', $watchStop)
        Start-Sleep -Seconds 3
    }
    $began = Get-Date
    Write-Host ("{0:HH:mm:ss} {1}: building {2}" -f $began, $id, (Split-Path $spec -Leaf))
    $args2 = @('-NoProfile', '-File', (Join-Path $repo 'powershell\New-GdlPanel.ps1'),
               '-Spec', $spec, '-Donor', $Donor, '-Output', $output,
               '-Work', (Join-Path $runWork 'work'), '-Python', $Python,
               '-TimeoutSeconds', $BuildTimeoutSeconds)
    if ($IdMap) { $args2 += @('-IdMap', (Join-Path $runWork 'idmap')) }
    if ($extra -gt 0) { $args2 += '-KeepOpen' }
    $header = @("RUN $id", "spec $spec", "started $($began.ToString('o'))",
                ('host settled after {0:N0}s (quiet={1}, busy={2:N0}%, antivirus {3:N2} cores), free memory {4:N0} MB, antivirus CPU so far {5:N0}s' -f
                 $quiet.Waited, $quiet.Quiet, $quiet.Busy, $quiet.Av, $pre.FreeMB, $pre.AvCpu))
    $header | Out-File -FilePath $log -Encoding utf8
    & powershell @args2 2>&1 | ForEach-Object { "$_" } | Out-File -FilePath $log -Encoding utf8 -Append
    $code = $LASTEXITCODE

    if ($code -eq 0 -and $extra -gt 0) {
        for ($k = 1; $k -le $extra; $k++) {
            "" | Out-File -FilePath $log -Encoding utf8 -Append
            "=== extra build $k in the same GUI Designer session" | Out-File -FilePath $log -Encoding utf8 -Append
            Invoke-ExtraBuild $output $k 2>&1 | ForEach-Object { "$_" } |
                Out-File -FilePath $log -Encoding utf8 -Append
        }
    }
    if ($extra -gt 0) {
        Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue |
            Stop-Process -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType File -Force -Path $stop | Out-Null
    if ($watcher) {
        New-Item -ItemType File -Force -Path $watchStop | Out-Null
        [void]$watcher.WaitForExit(120000)
        if (-not $watcher.HasExited) { Stop-Process -Id $watcher.Id -Force -ErrorAction SilentlyContinue }
    }
    [void]$sampler.WaitForExit(30000)
    if (-not $sampler.HasExited) { Stop-Process -Id $sampler.Id -Force -ErrorAction SilentlyContinue }

    $ended = Get-Date
    $builtBytes = if (Test-Path $output) { (Get-Item $output).Length } else { 0 }
    $plan = Join-Path $runWork 'work\plan.json'
    if (Test-Path $plan) { Copy-Item $plan (Join-Path $OutDir "$id.plan.json") -Force }
    [pscustomobject]@{
        id = $id; spec = $spec; started = $began.ToString('o'); ended = $ended.ToString('o')
        exit = $code; extra_builds = $extra; settle_s = [math]::Round($quiet.Waited, 1)
        settled_quiet = $quiet.Quiet; settle_busy_pct = [math]::Round($quiet.Busy, 0); settle_av_cores = [math]::Round($quiet.Av, 2)
        pre_free_mb = [math]::Round($pre.FreeMB, 0); pre_av_cpu_s = [math]::Round($pre.AvCpu, 0)
        built_bytes = $builtBytes; watched_files = [bool]$WatchFiles
    } | ConvertTo-Json | Out-File -FilePath (Join-Path $OutDir "$id.meta.json") -Encoding utf8
    Remove-Item $runWork -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ("{0:HH:mm:ss} {1}: exit {2}, {3:N0}s" -f $ended, $id, $code, ($ended - $began).TotalSeconds)
}
Write-Host 'queue done'
