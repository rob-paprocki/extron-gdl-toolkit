<#
    Sample what GUI Designer and the host are doing, every few seconds, into a
    CSV until a stop file appears. Started beside a build by
    Run-BuildTiming.ps1; the columns are Get-GdlLoad's (powershell\GdlTiming.ps1):

        t              ISO 8601 local time of the sample
        gd_cpu_s       GUI Designer's CPU seconds so far
        gd_write_mb    MB it has written so far (read_mb: read)
        gd_ws_mb       its working set now
        av_cpu_s       the antivirus engine's (MsMpEng) CPU seconds so far
        sys_busy_pct   share of all processors in use since the last sample
        free_mb        free physical memory
        cpu_perf_pct   the processors' performance as a share of their maximum
                       (Windows' "% Processor Performance": below 100 when
                       power or heat holds them back)
        disk_busy_pct  the disks' busy share, and disk_ms their average
                       time per transfer
        top            the three busiest processes other than GUI Designer and
                       the antivirus engine, as name:cores

    Counters are totals, so a period's figure is the difference of two rows.

        powershell -NoProfile -File tools\Sample-GdlHost.ps1 -Out t.csv -Stop t.stop
#>
param(
    [Parameter(Mandatory)][string]$Out,
    [Parameter(Mandatory)][string]$Stop,
    [int]$IntervalSeconds = 5
)

. (Join-Path (Split-Path $PSScriptRoot -Parent) 'powershell\GdlTiming.ps1')

't,gd_cpu_s,gd_write_mb,gd_read_mb,gd_ws_mb,av_cpu_s,sys_busy_pct,free_mb,cpu_perf_pct,disk_busy_pct,disk_ms,top' |
    Out-File -FilePath $Out -Encoding ascii

# A counter reads as a rate between two reads, so each is read once now.
function New-Counter($cat, $name, $inst) {
    try {
        $c = New-Object System.Diagnostics.PerformanceCounter($cat, $name, $inst)
        [void]$c.NextValue()
        return $c
    } catch { return $null }
}
function Read-Counter($c) { if ($c) { try { return $c.NextValue() } catch { } } return -1 }
$perf = New-Counter 'Processor Information' '% Processor Performance' '_Total'
$disk = New-Counter 'PhysicalDisk' '% Disk Time' '_Total'
$lat = New-Counter 'PhysicalDisk' 'Avg. Disk sec/Transfer' '_Total'

# Cores each process used since the last sample, for the three busiest others.
function Get-CpuTimes {
    $h = @{}
    foreach ($p in [System.Diagnostics.Process]::GetProcesses()) {
        try { $h[$p.Id] = @($p.ProcessName, $p.TotalProcessorTime.TotalSeconds) } catch { }
    }
    return $h
}
$prevTimes = Get-CpuTimes
$prev = Get-GdlLoad
while (-not (Test-Path $Stop)) {
    Start-Sleep -Seconds $IntervalSeconds
    $now = Get-GdlLoad
    $d = Get-GdlLoadDelta $prev $now
    $times = Get-CpuTimes
    $busiest = foreach ($id in $times.Keys) {
        if ($prevTimes.ContainsKey($id) -and $times[$id][0] -notin 'GUI Designer', 'MsMpEng', 'Idle') {
            [pscustomobject]@{ N = $times[$id][0]; C = ($times[$id][1] - $prevTimes[$id][1]) / $d.Wall }
        }
    }
    $top = (@($busiest | Sort-Object C -Descending | Select-Object -First 3 |
              ForEach-Object { '{0}:{1:F2}' -f $_.N, $_.C }) -join ';')
    $prevTimes = $times
    $prev = $now
    ('{0},{1:F1},{2:F1},{3:F1},{4:F0},{5:F1},{6:F0},{7:F0},{8:F0},{9:F0},{10:F1},{11}' -f
        $now.At.ToString('o'), $now.GdCpu, ($now.GdWritten / 1MB), ($now.GdRead / 1MB),
        $now.GdWsMB, $now.AvCpu, $d.SysBusy, $now.FreeMB,
        (Read-Counter $perf), (Read-Counter $disk), (1000 * (Read-Counter $lat)), $top) |
        Out-File -FilePath $Out -Encoding ascii -Append
}
