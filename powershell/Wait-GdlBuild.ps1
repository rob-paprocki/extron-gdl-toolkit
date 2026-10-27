<#
    Block until GUI Designer's Save and Build has finished writing the .gdl.

        powershell\Wait-GdlBuild.ps1 -ProjectFile C:\gdlwork\x.gdl

    Getting this wrong costs a whole round trip and does not look like a
    failure - you read the pre-build payload and see a build that "did nothing".
    Three signals were tried; only the last one is real. Timings measured on GUI
    Designer 1.27.0.9 on a 29-control page; the behaviour still holds on
    1.28.0.7, where a rebuilt seed took about 110 seconds to settle:

      * The title bar's trailing '*' means unsaved changes, nothing more. A file
        packed on disk and opened clean never has one, so the wait returns
        immediately.

      * The Build Manager window. GUI Designer's main window owns it, so
        Get-Process MainWindowTitle cannot see it and you need EnumWindows - and
        having gone to that trouble it still does not mean what it looks like.
        It appears several seconds AFTER the keystroke, so a poll that starts
        immediately sees "no dialog" and calls the build finished before it
        began. It then closes BEFORE the file is written - five seconds before
        in the build first watched, under one to 35 in the format probes', a
        "Wait..." window standing between - so even waiting for it to
        disappear truncates the payload if you kill the process on that
        signal. Both mistakes were made here. Nor does it report: on 1.28 it
        shows no error or warning count (docs/from-scratch.md section 7).

      * The .gdl's own mtime. This is the one. The build rewrote the file at
        t+46.4s, and nothing before that moment distinguishes a finished build
        from a running one.

    So: wait for the file to change, then wait for it to stop changing. Exits 0
    when the payload is written and stable, 1 on timeout, and 2 at once when
    GUI Designer sits idle behind a dialog it waits on a person for
    (GdlBlocker.ps1), saying which.

    A real-size panel builds for longer than any fixed timeout a small one
    wants, and a 15-minute wait reported a failure while GUI Designer was still
    building (docs/from-scratch.md section 5c has what one took). So past
    -TimeoutSeconds the wait runs on while GUI Designer is busy, and gives up a
    minute after it goes idle, up to -MaxSeconds. Idle includes a modal that
    blocks a build; the ones GdlBlocker.ps1 names - among them the prompt an
    upgrade's reset preferences raise - end the wait at once instead.

    Busy is a share of a core or a rate of writing well above what GUI Designer
    does idle, and it takes both. Any write at all is no sign of life: idle, and
    behind a modal, GUI Designer writes a steady 3.5 KB/s. A build writes
    300 KB/s at 15% of a core for minutes, and then for a minute and more writes
    no more than idle at a full core (section 7 has the measurements). The Build
    Manager is no sign either: a long build can show none until its last seconds.

    Capture the mtime BEFORE triggering the build and pass it as -Since:

        $t0 = (Get-Item $f).LastWriteTime
        powershell\Invoke-GdlMenu.ps1 -Item 'Save and Build'
        powershell\Wait-GdlBuild.ps1 -ProjectFile $f -Since $t0

    Without it there is a race. Invoke-GdlMenu blocks on the build modal, so if
    the build finishes before that call returns, a baseline sampled here is
    already the post-build mtime and the wait can never be satisfied - it burns
    the full timeout and reports failure for a build that in fact succeeded.
    Machine speed decides which way it falls, so it is not reproducible.
#>
param(
    [Parameter(Mandatory)][string]$ProjectFile,
    [int]$TimeoutSeconds = 900,
    [int]$MaxSeconds = 7200,
    [int]$StableSeconds = 6,
    [int]$PollSeconds = 2,
    [Nullable[DateTime]]$Since = $null
)

if (-not (Test-Path $ProjectFile)) { throw "not found: $ProjectFile" }
. (Join-Path $PSScriptRoot 'GdlBlocker.ps1')

# What GUI Designer has done so far - bytes written and CPU seconds, as Windows
# counts them - summed over every instance, since with two open the build could
# be either's. $null when none is running.
function Get-GdActivity {
    $ps = @(Get-CimInstance Win32_Process -Filter "Name='GUI Designer.exe'" -ErrorAction SilentlyContinue)
    if (-not $ps.Count) { return $null }
    $user = ($ps | Measure-Object -Property UserModeTime -Sum).Sum
    $kernel = ($ps | Measure-Object -Property KernelModeTime -Sum).Sum
    [pscustomobject]@{
        Written = [double](($ps | Measure-Object -Property WriteTransferCount -Sum).Sum)
        Cpu     = ([double]$user + [double]$kernel) / 1e7
    }
}

# Busy, between two polls: a tenth of a core, or 32 KB/s written. Measured on
# 1.28.0.7, idle and behind a modal GUI Designer stays under 3% of a core and
# 5 KB/s; every two-second step of two nine-minute builds was five times one
# or the other, or more (docs/from-scratch.md section 7).
$BusyCpu = 0.10
$BusyBytes = 32KB

$before = Get-Item $ProjectFile

# The caller should capture the mtime BEFORE triggering the build and pass it as
# -Since. Invoke-GdlMenu blocks on the build modal, so on a machine where the
# build completes before that call returns, sampling the baseline here reads the
# post-build mtime and the wait below can never be satisfied - a successful build
# reported as a timeout. Which way the race falls depends on machine speed, so
# both orderings happen in practice. Falling back to the current mtime keeps the
# old single-argument behaviour working for callers that do not pass -Since.
$t0 = if ($null -ne $Since) { $Since } else { $before.LastWriteTime }

$sw = [Diagnostics.Stopwatch]::StartNew()
Write-Output ("waiting for a build to rewrite {0} (was {1:HH:mm:ss}, {2:N0} bytes)" -f
              [System.IO.Path]::GetFileName($ProjectFile), $t0, $before.Length)

# If the file already moved past the baseline, the build we were waiting for has
# happened - fall straight through to the stability check rather than hanging.
$written = ($before.LastWriteTime -ne $t0)
if ($written) { Write-Output '  already rewritten before the wait started' }
$lastSize = -1
$stableFor = 0
# When GUI Designer was last busy; the wait outlasts it by a minute.
$seen = -1
$last = Get-GdActivity
$lastAt = $sw.Elapsed.TotalSeconds
# Whether GUI Designer was running at all, so a wait that ends is not blamed on
# a modal when there was nothing to show one.
$ran = $null -ne $last
$told = $false

while ($sw.Elapsed.TotalSeconds -lt $MaxSeconds) {
    $now = $sw.Elapsed.TotalSeconds
    # Only while waiting for the write: once the file has moved, what is left
    # is the stability check, which takes seconds.
    if (-not $written) {
        $a = Get-GdActivity
        $dt = $now - $lastAt
        $busy = $false
        if ($null -ne $a) {
            $ran = $true
            if ($null -ne $last -and $dt -gt 0 -and
                (($a.Cpu - $last.Cpu) / $dt -ge $BusyCpu -or ($a.Written - $last.Written) / $dt -ge $BusyBytes)) {
                $busy = $true
                if ($now -ge $TimeoutSeconds -and -not $told) {
                    Write-Output ("  past {0}s and GUI Designer is still busy - waiting on it" -f $TimeoutSeconds)
                    $told = $true
                }
                $seen = $now
            }
        }
        $last = $a
        $lastAt = $now
        # A dialog that waits on a person does not go away by itself, so say
        # which now rather than at the end - but only with GUI Designer idle
        # behind it, as it is behind a modal that blocks the build. Busy, it
        # may be building still, and giving up would throw that build away.
        if (-not $busy) {
            $why = Get-GdlBlocker
            if ($why) { Write-Output "  $why"; exit 2 }
        }
        if ($now -ge $TimeoutSeconds -and ($seen -lt 0 -or $now - $seen -ge 60)) { break }
    }
    Start-Sleep -Seconds $PollSeconds
    $it = Get-Item $ProjectFile

    if (-not $written) {
        if ($it.LastWriteTime -ne $t0) {
            $written = $true
            Write-Output ("  rewritten at t+{0:N1}s" -f $sw.Elapsed.TotalSeconds)
        }
        continue
    }

    # Written, but GUI Designer may still be streaming the payload into it.
    if ($it.Length -eq $lastSize) {
        $stableFor += $PollSeconds
        if ($stableFor -ge $StableSeconds) {
            Write-Output ("build finished at t+{0:N1}s, {1:N0} bytes" -f
                          $sw.Elapsed.TotalSeconds, $it.Length)
            exit 0
        }
    } else {
        $stableFor = 0
        $lastSize = $it.Length
    }
}

$state = if ($null -eq (Get-GdActivity)) {
        if ($ran) { 'exited' } else { 'is not running' }
    } elseif ($seen -lt 0) { 'sat idle - a modal waiting on a person, or a click that never landed' }
    else { "has been idle since t+{0:N0}s" -f $seen }
Write-Output (("no completed build after {0:N0}s (written={1}; GUI Designer {2})" -f
               $sw.Elapsed.TotalSeconds, $written, $state) + "$(Get-GdlShowing)")
exit 1
