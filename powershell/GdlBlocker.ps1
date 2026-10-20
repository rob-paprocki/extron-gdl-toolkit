<#
    What GUI Designer is showing that only a person can answer. Dot-source it:

        . (Join-Path $PSScriptRoot 'GdlBlocker.ps1')
        $why = Get-GdlBlocker    # $null, or what is in the way and what to do
        Get-GdlDialog            # every window it shows but its main one, by title
        Get-GdlShowing           # the same as a sentence for a wait that ran out

    GUI Designer waits on a person behind some dialogs, and from outside each
    looks like slow work: a wait that watched only for its work sat out its
    whole timeout, then said GUI Designer did not open the file, or sat idle.
    The ones it names:

      Application Licensing          an Extron Insider login. It can come up
                                     at start with the user logged in, and
                                     nothing opens until it is answered.
      Save and Build Optimization    the first Save and Build after an upgrade
                                     asks it (docs/from-scratch.md section 7).
      GUI Designer Error,            GUI Designer's own error boxes, named in
      GUI Designer Application Error its executable; what they say is read
                                     out, since that is what a run has to
                                     report.

    Each is a top-level window of GUI Designer's own, so EnumWindows finds it by
    title - in any PowerShell, the 32-bit one included, and in milliseconds, so
    a wait can ask on every poll. UI Automation sees them too, slower, and
    throws when a window closes during the walk.

    -ProcessId asks about other processes: one a caller started, or a test's
    stand-in window. Without it, every running GUI Designer is asked.
#>

if (-not ('GdlBlockerWindows' -as [type])) {
    # No HashSet or LINQ: Windows PowerShell compiles this against mscorlib and
    # System alone.
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class GdlBlockerWindows {
    delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessageTimeout(
        IntPtr h, uint msg, IntPtr w, StringBuilder l, uint flags, uint ms, out IntPtr result);
    const uint GW_OWNER = 4, WM_GETTEXT = 0x000D, SMTO_ABORTIFHUNG = 0x0002;

    public class Window { public IntPtr Handle; public string Title; public bool Owned; }

    // These processes' visible top-level windows that have a title.
    public static List<Window> Tops(uint[] pids) {
        var found = new List<Window>();
        EnumWindows((h, p) => {
            uint pid;
            GetWindowThreadProcessId(h, out pid);
            if (Array.IndexOf(pids, pid) >= 0 && IsWindowVisible(h)) {
                var s = new StringBuilder(512);
                GetWindowText(h, s, 512);
                if (s.Length > 0)
                    found.Add(new Window { Handle = h, Title = s.ToString(), Owned = GetWindow(h, GW_OWNER) != IntPtr.Zero });
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }

    // What a window's static text says - a message box's message. WM_GETTEXT,
    // since GetWindowText does not read another process's controls, with a
    // timeout so a hung GUI Designer cannot hang the wait.
    public static string Text(IntPtr window) {
        var parts = new List<string>();
        EnumChildWindows(window, (h, p) => {
            var c = new StringBuilder(256);
            GetClassName(h, c, 256);
            if (IsWindowVisible(h) && c.ToString().IndexOf("static", StringComparison.OrdinalIgnoreCase) >= 0) {
                var s = new StringBuilder(2048);
                IntPtr r;
                if (SendMessageTimeout(h, WM_GETTEXT, (IntPtr)s.Capacity, s, SMTO_ABORTIFHUNG, 1000, out r) != IntPtr.Zero
                        && s.Length > 0)
                    parts.Add(s.ToString());
            }
            return true;
        }, IntPtr.Zero);
        return string.Join(" ", parts.ToArray());
    }
}
'@
}

# The processes asked about that are running: those named, else every GUI
# Designer.
function Get-GdlProcessId([int[]]$ProcessId) {
    if ($ProcessId) { return @($ProcessId | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue }) }
    @(Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | ForEach-Object Id)
}

# Every window GUI Designer shows but its main one. That one has no owner and
# is titled 'GUI Designer', or 'GUI Designer - [project]'. Neither alone says
# which it is: its error windows' titles begin 'GUI Designer' too, and a box it
# owns can be captioned 'GUI Designer' itself.
function Get-GdlWindow([int[]]$ProcessId) {
    $ids = Get-GdlProcessId $ProcessId
    if (-not $ids) { return }
    [GdlBlockerWindows]::Tops([uint32[]]$ids) | Where-Object {
        $_.Owned -or -not ($_.Title -eq 'GUI Designer' -or $_.Title -like 'GUI Designer - `[*')
    }
}

function Get-GdlDialog([int[]]$ProcessId) {
    Get-GdlWindow $ProcessId | ForEach-Object { $_.Title }
}

# What GUI Designer waits on a person for, and what to do; $null when nothing.
function Get-GdlBlocker([int[]]$ProcessId) {
    foreach ($w in @(Get-GdlWindow $ProcessId)) {
        # Never what this one says: it shows the user's e-mail address.
        if ($w.Title -eq 'Application Licensing') {
            return ('GUI Designer is asking for an Extron Insider login (its Application Licensing ' +
                    'window) and opens nothing until it is answered - open GUI Designer on this ' +
                    'machine, log in, then run this again')
        }
        if ($w.Title -eq 'Save and Build Optimization') {
            return ('GUI Designer is asking whether to remove unused resources (Save and Build ' +
                    'Optimization), as the first build after an upgrade does - set its preference ' +
                    'as docs/from-scratch.md section 7 says, then run this again')
        }
        if ($w.Title -eq 'GUI Designer Error' -or $w.Title -eq 'GUI Designer Application Error') {
            $text = ([GdlBlockerWindows]::Text($w.Handle) -replace '\s+', ' ').Trim()
            if ($text.Length -gt 400) { $text = $text.Substring(0, 400) + '...' }
            $says = if ($text) { ": $text" } else { '' }
            return ("GUI Designer shows an error and waits for someone to close it ($($w.Title)$says) - " +
                    'close it on this machine, then run this again')
        }
    }
    $null
}

# What GUI Designer shows beside its main window, as a sentence to add to a
# wait that ran out; nothing when it shows nothing else. -Opening is for a
# wait on a file handed to it, which also says whether it is running at all.
function Get-GdlShowing([int[]]$ProcessId, [switch]$Opening) {
    $shown = @(Get-GdlDialog $ProcessId)
    if ($shown.Count) {
        $said = ' It shows ' + (($shown | ForEach-Object { "'$_'" }) -join ', ') + '.'
        # Seen with a .glt handed to it: it came up empty, showing the wizard
        # it shows when started with no file.
        if ($Opening -and $shown -contains 'Project Create Wizard') {
            $said += ' The Project Create Wizard in place of the file is how it refused a .glt page library - a template, not a project.'
        }
        return $said
    }
    if ($Opening) {
        if (@(Get-GdlProcessId $ProcessId).Count) { return ' It is running, with no other window up.' }
        ' It is not running.'
    }
}
