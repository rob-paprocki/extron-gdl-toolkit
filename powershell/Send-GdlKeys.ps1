# Send keystrokes to GUI Designer's main window.
#
# Used to drive Project > Build, which is the only real oracle for whether a
# machine-authored .gdl is acceptable. prlctl has no key injection, so this
# runs inside the guest and uses the shell's AppActivate plus SendKeys.
param([Parameter(Mandatory)][string]$Keys, [string]$Match = 'GUI Designer')

Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
'@

$proc = Get-Process | Where-Object { $_.MainWindowTitle -like "*$Match*" } | Select-Object -First 1
if (-not $proc) { Write-Output "no window matching '$Match'"; exit 1 }
Write-Output "target: [$($proc.MainWindowTitle)] pid=$($proc.Id)"

[Win]::ShowWindow($proc.MainWindowHandle, 9) | Out-Null   # SW_RESTORE
[Win]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 800
[System.Windows.Forms.SendKeys]::SendWait($Keys)
Start-Sleep -Milliseconds 500
Write-Output "sent: $Keys"
