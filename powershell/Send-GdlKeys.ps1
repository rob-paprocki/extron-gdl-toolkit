# Send keystrokes to GUI Designer's main window.
#
# Used to drive File > Save and Build, which is the only real oracle for whether
# a machine-authored .gdl is acceptable.
#
# SendKeys goes to whatever has focus, not to a window you name, so this has to
# actually OWN the foreground before it types - and Windows will not simply hand
# it over. SetForegroundWindow fails for a process that is not already the
# foreground one; it returns false and flashes the taskbar instead. The previous
# version discarded that return value and typed regardless, so Ctrl+Shift+B went
# to whatever was in front - usually the terminal that launched the pipeline -
# while still printing "sent: ^+b". The build never ran, the .gdl was never
# rewritten, and the only symptom was the build waiter timing out 15 minutes
# later. That is also why this now refuses rather than typing blind: keystrokes
# aimed at an unknown window are worse than no keystrokes.
#
# AttachThreadInput ties this thread's input queue to the target's, which is what
# grants the foreground right. Then verify, because it can still lose.
param(
    [Parameter(Mandatory)][string]$Keys,
    [string]$Match = 'GUI Designer',
    [int]$Attempts = 5
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class Win {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint from, uint to, bool attach);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();

    public static bool Focus(IntPtr h) {
        uint target = GetWindowThreadProcessId(h, IntPtr.Zero);
        uint self = GetCurrentThreadId();
        bool attached = (target != self) && AttachThreadInput(self, target, true);
        try {
            ShowWindow(h, 9);              // SW_RESTORE
            BringWindowToTop(h);
            SetForegroundWindow(h);
        } finally {
            if (attached) AttachThreadInput(self, target, false);
        }
        return GetForegroundWindow() == h;
    }

    public static string TitleOf(IntPtr h) {
        var sb = new StringBuilder(512);
        GetWindowText(h, sb, sb.Capacity);
        return sb.ToString();
    }
}
'@

$proc = Get-Process |
    Where-Object { $_.MainWindowTitle -like "*$Match*" } |
    Select-Object -First 1
if (-not $proc) { Write-Output "no window matching '$Match'"; exit 1 }
$h = $proc.MainWindowHandle
Write-Output "target: [$($proc.MainWindowTitle)] pid=$($proc.Id)"

$ok = $false
for ($i = 1; $i -le $Attempts; $i++) {
    if ([Win]::Focus($h)) { $ok = $true; break }
    Start-Sleep -Milliseconds 400
}
if (-not $ok) {
    $fg = [Win]::GetForegroundWindow()
    Write-Output ("could not bring [$($proc.MainWindowTitle)] to the foreground after " +
                  "$Attempts attempts - '$([Win]::TitleOf($fg))' still has focus. " +
                  'NOT sending keys: they would go to that window instead. The desktop ' +
                  'must be unlocked and no other app may be holding focus.')
    exit 2
}

Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait($Keys)
Start-Sleep -Milliseconds 500

# Confirm it still had focus while typing - a dialog stealing it mid-send would
# split the keystrokes between two windows.
$after = [Win]::GetForegroundWindow()
if ($after -ne $h) {
    Write-Output "sent: $Keys  (focus moved to '$([Win]::TitleOf($after))' during send)"
} else {
    Write-Output "sent: $Keys"
}
