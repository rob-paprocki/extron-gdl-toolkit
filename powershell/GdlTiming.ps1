<#
    What the host spent while a build ran. Dot-source it:

        . (Join-Path $PSScriptRoot 'GdlTiming.ps1')
        $a = Get-GdlLoad
        ...                              # the work
        $b = Get-GdlLoad
        Format-GdlLoad $a $b             # lines for a log

    A build's wall-clock time says how long a designer waits, not what GUI
    Designer waited for. Set beside it, these say whether the run was GUI
    Designer's own processor time (CPU seconds near the wall clock), its disk
    (bytes written and read), real-time scanning (the antivirus engine's CPU
    seconds, MsMpEng, which scans the files a build writes) or something else
    on the host (the whole machine's busy share, and the processors' clock,
    which sets how fast a scanning thread goes). All of it is read, not
    changed: Windows' own process and system counters.

    Counters are summed over every GUI Designer there is, as Wait-GdlBuild.ps1's
    are, and a process that is not running contributes nothing.
#>

if (-not ('GdlSystemTimes' -as [type])) {
    # Windows PowerShell compiles this against mscorlib and System alone.
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class GdlSystemTimes {
    [DllImport("kernel32.dll")]
    static extern bool GetSystemTimes(out long idle, out long kernel, out long user);
    // Idle, kernel (which includes idle) and user time, all processors, in 100 ns.
    public static long[] Read() {
        long i, k, u;
        GetSystemTimes(out i, out k, out u);
        return new long[] { i, k, u };
    }
}
'@
}

# The sum of a Win32_Process property over the processes of one name.
function Sum-GdlProcess($procs, [string[]]$props) {
    $t = 0.0
    foreach ($p in @($procs)) { foreach ($n in $props) { $t += [double]$p.$n } }
    return $t
}

# The processors' performance as Windows counts it - "% Processor Performance",
# their clock as a share of the nominal one, about 385 at the 3.1 GHz an Intel
# N100 runs a build at and about 140 at the 1.1 GHz it sometimes falls to
# (docs/from-scratch.md section 5c). A rate counter reads as the mean since its
# last read, so each snapshot's Clock is the mean since the snapshot before it
# in this process - which is the span a caller measures when it takes one at
# each end and none between. 0 on the first, -1 where Windows has no such
# counter.
$script:GdlClockCounter = $null
$script:GdlClockTried = $false
function Read-GdlClock {
    if (-not $script:GdlClockTried) {
        $script:GdlClockTried = $true
        try {
            $script:GdlClockCounter = New-Object System.Diagnostics.PerformanceCounter(
                'Processor Information', '% Processor Performance', '_Total')
        } catch { $script:GdlClockCounter = $null }
    }
    if (-not $script:GdlClockCounter) { return -1.0 }
    try { return [double]$script:GdlClockCounter.NextValue() } catch { return -1.0 }
}

function Get-GdlLoad {
    $gd = @(Get-CimInstance Win32_Process -Filter "Name='GUI Designer.exe'" -ErrorAction SilentlyContinue)
    $av = @(Get-CimInstance Win32_Process -Filter "Name='MsMpEng.exe'" -ErrorAction SilentlyContinue)
    $os = Get-CimInstance Win32_OperatingSystem
    $st = [GdlSystemTimes]::Read()
    [pscustomobject]@{
        At         = Get-Date
        GdRunning  = $gd.Count
        GdCpu      = (Sum-GdlProcess $gd 'UserModeTime', 'KernelModeTime') / 1e7
        GdWritten  = Sum-GdlProcess $gd 'WriteTransferCount'
        GdRead     = Sum-GdlProcess $gd 'ReadTransferCount'
        # Win32_Process reports the working set in bytes and its peak in KB.
        GdWsMB     = (Sum-GdlProcess $gd 'WorkingSetSize') / 1MB
        GdPeakMB   = (Sum-GdlProcess $gd 'PeakWorkingSetSize') / 1KB
        AvCpu      = (Sum-GdlProcess $av 'UserModeTime', 'KernelModeTime') / 1e7
        SysIdle    = [double]$st[0]
        SysTotal   = [double]$st[1] + [double]$st[2]
        FreeMB     = [double]$os.FreePhysicalMemory / 1KB
        Clock      = Read-GdlClock
    }
}

# Between two snapshots: seconds of wall clock, GUI Designer's CPU seconds and
# its share of one core, MB it wrote and read, the antivirus engine's CPU
# seconds, the share of all the machine's processors that anything was using,
# GUI Designer's peak working set at the end, and the processors' clock.
function Get-GdlLoadDelta($a, $b) {
    $wall = ($b.At - $a.At).TotalSeconds
    $tot = $b.SysTotal - $a.SysTotal
    [pscustomobject]@{
        Wall      = $wall
        GdCpu     = $b.GdCpu - $a.GdCpu
        GdCores   = if ($wall -gt 0) { ($b.GdCpu - $a.GdCpu) / $wall } else { 0 }
        GdWriteMB = ($b.GdWritten - $a.GdWritten) / 1MB
        GdReadMB  = ($b.GdRead - $a.GdRead) / 1MB
        AvCpu     = $b.AvCpu - $a.AvCpu
        SysBusy   = if ($tot -gt 0) { 100.0 * (1.0 - ($b.SysIdle - $a.SysIdle) / $tot) } else { 0 }
        GdPeakMB  = $b.GdPeakMB
        FreeMB    = $b.FreeMB
        Clock     = $b.Clock
    }
}

# Key=value lines a log keeps and a script can read back: "LOAD <label> k=v ...".
function Format-GdlLoad([string]$label, $a, $b) {
    $d = Get-GdlLoadDelta $a $b
    ('LOAD {0} wall={1:N1} gd_cpu={2:N1} gd_cores={3:N2} gd_write_mb={4:N1} gd_read_mb={5:N1} ' +
     'av_cpu={6:N1} sys_busy_pct={7:N0} gd_peak_mb={8:N0} free_mb={9:F0} clock_pct={10:F0}') -f
        $label, $d.Wall, $d.GdCpu, $d.GdCores, $d.GdWriteMB, $d.GdReadMB,
        $d.AvCpu, $d.SysBusy, $d.GdPeakMB, $d.FreeMB, $d.Clock
}
