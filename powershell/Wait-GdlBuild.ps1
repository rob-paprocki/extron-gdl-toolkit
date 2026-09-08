<#
    Block until GUI Designer's Save and Build finishes.

    Getting this wrong wastes a whole round trip, and the two obvious signals
    are both wrong:

      * The title bar's trailing '*'. It only means unsaved changes, so a file
        that was packed on disk and opened clean never has one - the wait
        returns instantly and you read a stale payload, which looks exactly
        like the build silently doing nothing.
      * The .gdl's LastWriteTime. Save and Build writes the project first and
        the payload after, so the file stops changing long before the build is
        done.

    The real signal is the Build Manager window, which is a child window and so
    invisible to Get-Process MainWindowTitle. This enumerates top-level windows
    owned by the process, waits for it to appear, then waits for it to close.

      powershell\Wait-GdlBuild.ps1 -TimeoutSeconds 900

    Exits 0 when a build completed, 1 on timeout, 2 if no build ever started.
#>
param(
    [int]$TimeoutSeconds = 900,
    [int]$StartSeconds = 60,
    [string]$Match = 'Build Manager'
)

Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public class WinEnum {
    delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    public static List<string> Titles() {
        var found = new List<string>();
        EnumWindows((h, p) => {
            if (!IsWindowVisible(h)) return true;
            var sb = new StringBuilder(512);
            if (GetWindowText(h, sb, sb.Capacity) > 0) found.Add(sb.ToString());
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
'@

function Test-BuildWindow {
    foreach ($t in [WinEnum]::Titles()) { if ($t -like "*$Match*") { return $true } }
    return $false
}

$started = $false
$deadline = (Get-Date).AddSeconds($StartSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-BuildWindow) { $started = $true; break }
    Start-Sleep -Milliseconds 500
}
if (-not $started) {
    Write-Output "no '$Match' window appeared within ${StartSeconds}s - did the build start?"
    exit 2
}
Write-Output "build started"

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if (-not (Test-BuildWindow)) {
        # The window closes just before the payload lands; give the write a beat.
        Start-Sleep -Seconds 2
        Write-Output 'build finished'
        exit 0
    }
    Start-Sleep -Seconds 2
}
Write-Output "build still running after ${TimeoutSeconds}s"
exit 1
