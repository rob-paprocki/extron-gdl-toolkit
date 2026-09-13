<#
    Block until GUI Designer's Save and Build has finished writing the .gdl.

        powershell\Wait-GdlBuild.ps1 -ProjectFile C:\gdlwork\x.gdl

    Getting this wrong costs a whole round trip and does not look like a
    failure - you read the pre-build payload and see a build that "did nothing".
    Three signals were tried; only the last one is real. Measured against GUI
    Designer 1.27.0.9 on a 29-control page:

      * The title bar's trailing '*' means unsaved changes, nothing more. A file
        packed on disk and opened clean never has one, so the wait returns
        immediately.

      * The Build Manager window. It is a child window, so Get-Process
        MainWindowTitle cannot see it and you need EnumWindows - and having gone
        to that trouble it still does not mean what it looks like. It appears
        several seconds AFTER the keystroke, so a poll that starts immediately
        sees "no dialog" and calls the build finished before it began. It then
        closes about five seconds BEFORE the file is written, so even waiting
        for it to disappear truncates the payload if you kill the process on
        that signal. Both mistakes were made here.

      * The .gdl's own mtime. This is the one. The build rewrote the file at
        t+46.4s, and nothing before that moment distinguishes a finished build
        from a running one.

    So: wait for the file to change, then wait for it to stop changing. Exits 0
    when the payload is written and stable, 1 on timeout.

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
    [int]$StableSeconds = 6,
    [int]$PollSeconds = 2,
    [Nullable[DateTime]]$Since = $null
)

if (-not (Test-Path $ProjectFile)) { throw "not found: $ProjectFile" }

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

while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
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

Write-Output ("no completed build after {0}s (written={1})" -f $TimeoutSeconds, $written)
exit 1
