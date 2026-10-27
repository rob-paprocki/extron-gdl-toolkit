<#
    Record what GUI Designer's Build Manager says while a build runs.

        powershell -NoProfile -ExecutionPolicy Bypass -File examples\probes-128\Watch-BuildManager.ps1 `
            -OutDir out\probes-128\<probe>\buildmgr -StopFile out\probes-128\<probe>\buildmgr\stop

    Run-Probes128.ps1 starts it before a build and stops it after. The build
    waits watch the .gdl, because the window appears seconds after the click
    and closes before the file is written (docs/from-scratch.md section 7).
    This records every way the window could be read - on 1.28 it is a
    top-level window GUI Designer's main one owns, WM_GETTEXT reads its phase,
    UI Automation no name in it, and it shows no count - and
    examples/probes-128/read_probes.py greps what it wrote:

      windows.log    one line each time a GUI Designer window other than its main
                     one appears or goes: time, title, class, handle, rectangle.
      dump-N.txt     for each such window, up to -MaxDumps times while it stays
                     up: its descendants as WM_GETTEXT reads them (class and
                     text), then as UI Automation reads them (control type, name,
                     value). UI Automation is slow against this process, so the
                     poll is a second and a half and the walk is capped.
      shot-N.png     the window's own rectangle at the same moments, and the
                     whole screen every -ScreenSeconds while GUI Designer is up,
                     since a Build Manager that is a child of the main window is
                     in none of the lists above and is on the screen.

    Reads only. It never clicks, so it cannot answer a dialog; GdlBlocker.ps1
    is what names one that waits on a person.

    Runs under either PowerShell host. UI Automation and the screen are the
    interactive desktop's, as for Invoke-GdlMenu.ps1.
#>
param(
    [Parameter(Mandatory)][string]$OutDir,
    [string]$StopFile,
    [int]$PollMilliseconds = 1500,
    [int]$MaxDumps = 12,
    [int]$ScreenSeconds = 6,
    [int]$MaxScreens = 120
)

$ErrorActionPreference = 'Continue'
$OutDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutDir)
if (-not $StopFile) { $StopFile = Join-Path $OutDir 'stop' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
if (Test-Path $StopFile) { Remove-Item $StopFile -Force }

Add-Type -AssemblyName System.Drawing, System.Windows.Forms
$haveUia = $true
try { Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes } catch { $haveUia = $false }

if (-not ('GdlProbeWin' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class GdlProbeWin {
    delegate bool EnumProc(IntPtr h, IntPtr p);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessageTimeout(
        IntPtr h, uint msg, IntPtr w, StringBuilder l, uint flags, uint ms, out IntPtr result);
    const uint WM_GETTEXT = 0x000D, SMTO_ABORTIFHUNG = 0x0002;

    public class Win {
        public long Handle; public string Title; public string Class; public bool Owned;
        public int Left, Top, Right, Bottom;
    }

    static string Text(IntPtr h) {
        var s = new StringBuilder(4096);
        IntPtr r;
        if (SendMessageTimeout(h, WM_GETTEXT, (IntPtr)s.Capacity, s, SMTO_ABORTIFHUNG, 500, out r) == IntPtr.Zero) return "";
        return s.ToString();
    }

    // The visible top-level windows of these processes, titled or not.
    public static List<Win> Tops(uint[] pids) {
        var found = new List<Win>();
        EnumWindows((h, p) => {
            uint pid;
            GetWindowThreadProcessId(h, out pid);
            if (Array.IndexOf(pids, pid) >= 0 && IsWindowVisible(h)) {
                var t = new StringBuilder(512); GetWindowText(h, t, 512);
                var c = new StringBuilder(256); GetClassName(h, c, 256);
                RECT rc; GetWindowRect(h, out rc);
                found.Add(new Win { Handle = (long)h, Title = t.ToString(), Class = c.ToString(),
                    Owned = GetWindow(h, 4) != IntPtr.Zero,
                    Left = rc.Left, Top = rc.Top, Right = rc.Right, Bottom = rc.Bottom });
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }

    // Every descendant window's class and WM_GETTEXT text, visible or not.
    public static List<string> Dump(IntPtr window) {
        var lines = new List<string>();
        EnumChildWindows(window, (h, p) => {
            var c = new StringBuilder(256); GetClassName(h, c, 256);
            lines.Add(string.Format("{0}{1,-28} 0x{2:X} {3}", IsWindowVisible(h) ? " " : "-", c, (long)h, Text(h).Replace("\r", " ").Replace("\n", " | ")));
            return true;
        }, IntPtr.Zero);
        return lines;
    }
}
'@
}

function Get-GdProcessId {
    @(Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
}

function Save-Shot([string]$Path, [int]$Left, [int]$Top, [int]$Width, [int]$Height) {
    try {
        if ($Width -le 0 -or $Height -le 0) { return }
        $bmp = New-Object System.Drawing.Bitmap $Width, $Height
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($Left, $Top, 0, 0, (New-Object System.Drawing.Size $Width, $Height))
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
    } catch { }
}

# What UI Automation reads under a window: control type, name, value. Capped, and
# the walk is allowed to fail - the window can close during it.
function Get-UiaLines([long]$Handle) {
    if (-not $haveUia) { return @('(UI Automation not available)') }
    $out = @()
    try {
        $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Handle)
        $all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants,
                             [System.Windows.Automation.Condition]::TrueCondition)
        $n = 0
        foreach ($e in $all) {
            $n++
            if ($n -gt 500) { $out += '(more than 500 elements; the rest not listed)'; break }
            try {
                $c = $e.Current
                $val = ''
                $vp = $null
                if ($e.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$vp)) {
                    $val = $vp.Current.Value
                }
                $out += ('{0} | {1} | {2}' -f $c.ControlType.ProgrammaticName, $c.Name, $val)
            } catch { }
        }
    } catch { $out += "(UI Automation walk failed: $($_.Exception.Message))" }
    $out
}

$log = Join-Path $OutDir 'windows.log'
function Note([string]$m) { Add-Content -Path $log -Value ('{0:HH:mm:ss.fff}  {1}' -f (Get-Date), $m) -Encoding UTF8 }
Note "watching GUI Designer (UI Automation: $haveUia)"

$seen = @{}            # handle -> @{ Title; Dumps; First }
$screens = 0
$lastScreen = [DateTime]::MinValue
$shots = 0

while (-not (Test-Path $StopFile)) {
    $ids = Get-GdProcessId
    if ($ids.Count) {
        $now = Get-Date
        if ($screens -lt $MaxScreens -and ($now - $lastScreen).TotalSeconds -ge $ScreenSeconds) {
            $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
            Save-Shot (Join-Path $OutDir ('screen-{0:000}.png' -f $screens)) $b.Left $b.Top $b.Width $b.Height
            $screens++
            $lastScreen = $now
        }
        $wins = @([GdlProbeWin]::Tops([uint32[]]$ids))
        $live = @{}
        foreach ($w in $wins) {
            $main = (-not $w.Owned) -and ($w.Title -eq 'GUI Designer' -or $w.Title -like 'GUI Designer - `[*')
            if ($main -or ((-not $w.Title) -and $w.Class -match 'tooltip|IME|MSCTF')) { continue }
            $live[$w.Handle] = $true
            if (-not $seen.ContainsKey($w.Handle)) {
                $seen[$w.Handle] = @{ Title = $w.Title; Dumps = 0 }
                Note ("appeared  '{0}'  class={1}  handle=0x{2:X}  rect={3},{4},{5},{6}  owned={7}" -f
                      $w.Title, $w.Class, $w.Handle, $w.Left, $w.Top, $w.Right, $w.Bottom, $w.Owned)
            }
            $s = $seen[$w.Handle]
            if ($s.Dumps -lt $MaxDumps) {
                $s.Dumps++
                $stamp = '{0:HHmmss}' -f (Get-Date)
                $lines = @("# '{0}' class={1} handle=0x{2:X} dump {3} at {4}" -f $w.Title, $w.Class, $w.Handle, $s.Dumps, $stamp)
                $lines += '## WM_GETTEXT (visible flag, class, handle, text)'
                $lines += [GdlProbeWin]::Dump([IntPtr]$w.Handle)
                $lines += '## UI Automation (control type | name | value)'
                $lines += Get-UiaLines $w.Handle
                $name = ($w.Title -replace '[^A-Za-z0-9]+', '-').Trim('-')
                Set-Content -Path (Join-Path $OutDir ('dump-{0}-{1}-{2:00}.txt' -f $name, $stamp, $s.Dumps)) -Value $lines -Encoding UTF8
                if ($shots -lt 60) {
                    Save-Shot (Join-Path $OutDir ('shot-{0}-{1}-{2:00}.png' -f $name, $stamp, $s.Dumps)) $w.Left $w.Top ($w.Right - $w.Left) ($w.Bottom - $w.Top)
                    $shots++
                }
            }
        }
        foreach ($h in @($seen.Keys)) {
            if (-not $live.ContainsKey($h)) {
                Note ("gone      '{0}'  handle=0x{1:X}" -f $seen[$h].Title, $h)
                $seen.Remove($h)
            }
        }
    }
    Start-Sleep -Milliseconds $PollMilliseconds
}
Note 'stopped'
