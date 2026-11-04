<#
    GUI Designer's own snapshot of every page and popup of a built project,
    with nobody touching GUI Designer: the render baseline's ground truth.

        powershell\Export-GdlSnapshots.ps1 -ProjectFile C:\gdlwork\Synthetic.gdl `
            -Out tests\data\synthetic\snapshots\Individual

    It opens the file and takes File > Snapshot > Take All Pages Snapshot
    (Individual)..., which is how tests/data/synthetic/snapshots/Individual
    was made:

      1. The menu, through UI Automation, as Invoke-GdlMenu.ps1 clicks Save and
         Build - no focus, no keystrokes. The File menu and its Snapshot
         submenu are each expanded from a background job, since Expand()
         blocks while a menu is open, and the item is invoked from one too:
         its Invoke() blocks on the dialog it opens.
      2. Its Select Pages dialog: a tree of every page, its root Select All,
         ticked as it opens, then OK - by window messages, since UI
         Automation reaches nothing in it while the menu's invoke is blocked.
         Every page and popup, modals and the Offline Page included, is one
         PNG named '<page name>_Id<page ID>.png' - what tests/score.py
         matches on - and the PNGs are counted against the project's pages
         and popups, so a partial set is refused.
      3. Its progress window, then a message box: "Snapshot completed
         successfully. Snapshots created in <folder>. Open Folder?" - read for
         the folder, and answered No with a window message (WM_COMMAND IDNO),
         as New-GdlSeed.ps1 answers Save As. "Snapshot has been cancelled" is
         a failure.
      4. The PNGs that folder holds, written by this export, are copied to
         -Out - which this clears of PNGs first, and nothing else - and GUI
         Designer is closed.

    Where the folder is is GUI Designer's preference (File > Preferences >
    Directories, SnapshotsDirectory - by default
    C:\Users\Public\Documents\Extron\GUI Designer\Snapshots), under a folder
    named for the project; *Overwrite Bulk Snapshot Folder* clears it first.
    Only the files this export wrote are taken, whichever way that is set.

    -Mode Permutation takes File > Snapshot > Take All Pages Snapshot
    (Permutation) instead: every page with each popup its references can show.

    A dialog GUI Designer waits on a person behind - an Extron Insider login,
    an error box (GdlBlocker.ps1) - ends the run, saying which, as the build
    does. It needs an interactive desktop session, as every script that drives
    GUI Designer does (docs/from-scratch.md section 7). Exits 0 with the PNGs
    copied, non-zero otherwise.
#>
param(
    [Parameter(Mandatory)][string]$ProjectFile,
    [Parameter(Mandatory)][string]$Out,
    [ValidateSet('Individual', 'Permutation')][string]$Mode = 'Individual',
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer',
    [int]$TimeoutSeconds = 900,
    [int]$MenuWaitSeconds = 30,
    [string]$Python = 'python',
    [switch]$KeepOpen
)

$ErrorActionPreference = 'Stop'
$gd = Join-Path $InstallDir 'GUI Designer.exe'
. (Join-Path $PSScriptRoot 'GdlBlocker.ps1')
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
if (-not ('GdlSnapWin' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class GdlSnapWin {
    delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessageTimeout(
        IntPtr h, uint msg, IntPtr w, StringBuilder l, uint flags, uint ms, out IntPtr result);

    // A visible button among a window's children whose words are `text`, an
    // accelerator's '&' aside; WM_GETTEXT, with a timeout, as GdlBlocker.ps1
    // reads a message box. IntPtr.Zero when there is none.
    public static IntPtr Button(IntPtr parent, string text) {
        IntPtr found = IntPtr.Zero;
        EnumChildWindows(parent, (h, p) => {
            var c = new StringBuilder(256);
            GetClassName(h, c, 256);
            if (!IsWindowVisible(h) || c.ToString().IndexOf("button", StringComparison.OrdinalIgnoreCase) < 0)
                return true;
            var s = new StringBuilder(512);
            IntPtr r;
            if (SendMessageTimeout(h, 0x000D, (IntPtr)s.Capacity, s, 0x0002, 1000, out r) != IntPtr.Zero
                    && s.ToString().Replace("&", "") == text) {
                found = h;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
'@
}
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$CT = [System.Windows.Automation.ControlType]

if (-not (Test-Path $gd)) { throw "GUI Designer not found at $gd" }
# Relative to where the shell is, as for any cmdlet (New-GdlPanel.ps1 says why).
$ProjectFile = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ProjectFile)
$Out = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out).TrimEnd('\')
if (-not (Test-Path -LiteralPath $ProjectFile)) { throw "not found: $ProjectFile" }
$item = if ($Mode -eq 'Individual') { 'Take All Pages Snapshot (Individual)' } else { 'Take All Pages Snapshot (Permutation)' }

function Stop-Gd {
    Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
}

function Stop-Run([string]$why, [int]$code = 5) {
    Write-Output $why
    if (-not $KeepOpen) { Stop-Gd }
    exit $code
}

# A dialog GUI Designer waits on a person behind ends the run at once.
function Stop-IfBlocked {
    $why = Get-GdlBlocker
    if ($why) { Stop-Run $why }
}

# GUI Designer's own windows but its main one, as GdlBlocker.ps1 reads them.
function Find-Dialog([string]$like) {
    @(Get-GdlWindow) | Where-Object { $_.Title -like $like } | Select-Object -First 1
}

function Find-Main {
    foreach ($w in $AE::RootElement.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
        try { if ($w.Current.Name -like 'GUI Designer - `[*') { return $w } } catch { }
    }
    $null
}

function Find-MenuItem($root, [string]$like) {
    $cond = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::MenuItem)
    foreach ($m in $root.FindAll($TS::Descendants, $cond)) {
        try { if ($m.Current.Name -like $like) { return $m } } catch { }
    }
    $null
}

# Expand a menu, or invoke an item, from a background job: each blocks while
# what it opens is up. The job finds the element again by name - a UI
# Automation element does not cross into another process.
$uiaJob = {
    param($Path, $Act)
    Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
    $AE = [System.Windows.Automation.AutomationElement]
    $TS = [System.Windows.Automation.TreeScope]
    $CT = [System.Windows.Automation.ControlType]
    $root = $null
    foreach ($w in $AE::RootElement.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
        if ($w.Current.Name -like 'GUI Designer - `[*') { $root = $w; break }
    }
    if (-not $root) { return }
    $el = $null
    $items = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::MenuItem)
    foreach ($m in $root.FindAll($TS::Descendants, $items)) {
        try { if ($m.Current.Name -like $Path) { $el = $m; break } } catch { }
    }
    if (-not $el) { return }
    try {
        if ($Act -eq 'expand') {
            $el.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
        } else {
            $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
        }
    } catch { }
}

function Wait-Until([scriptblock]$test, [int]$seconds, [string]$what) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try { $r = & $test } catch { $r = $null }
        if ($r) { return $r }
        Stop-IfBlocked
        Start-Sleep -Milliseconds 700
    }
    Stop-Run "$what did not appear within $seconds s.$(Get-GdlShowing)"
}

# -- open the project ----------------------------------------------------------
Write-Output "=== open $ProjectFile"
Stop-Gd
Start-Sleep -Seconds 2
Start-Process -FilePath $gd -ArgumentList ('"' + $ProjectFile + '"')
$leaf = [System.IO.Path]::GetFileName($ProjectFile)
[void](Wait-Until {
    $p = Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | Select-Object -First 1
    # Get-Process caches the title; without Refresh it never shows the file.
    if ($p) { $p.Refresh(); if ($p.MainWindowTitle -like "*$leaf*") { $p } }
} 180 "GUI Designer with $leaf open")
# Its menu bar is not in the tree the moment the title is: wait for File.
$main = Wait-Until { $m = Find-Main; if ($m -and (Find-MenuItem $m 'File')) { $m } } 120 'its File menu'
Write-Output "  $($main.Current.Name)"

# -- File > Snapshot > Take All Pages Snapshot (...) --------------------------
Write-Output "=== File > Snapshot > $item"
$started = Get-Date
$jobs = @()
$jobs += Start-Job -ScriptBlock $uiaJob -ArgumentList 'File', 'expand'
$snap = Wait-Until { Find-MenuItem $main 'Snapshot' } $MenuWaitSeconds "the File menu's Snapshot item"
$jobs += Start-Job -ScriptBlock $uiaJob -ArgumentList 'Snapshot', 'expand'
$target = Wait-Until { Find-MenuItem $main "$item*" } $MenuWaitSeconds "'$item' under File > Snapshot"
if (-not $target.Current.IsEnabled) { Stop-Run "'$($target.Current.Name)' is disabled" 3 }
Write-Output "  invoking '$($target.Current.Name)'"
$jobs += Start-Job -ScriptBlock $uiaJob -ArgumentList "$item*", 'invoke'

if ($Mode -eq 'Individual') {
    # -- Select Pages: everything, then OK -------------------------------------
    # By window messages, not UI Automation: opened by a UIA invoke that is
    # still blocked on it, the dialog answered UI Automation nothing for 30 s,
    # as Save As does New-GdlSeed.ps1. Its 'Select All' is the root of a tree
    # of check boxes (a CheckboxTreeView, read off the assembly), ticked when
    # it opens; a tree item's tick is not a window to read, so what was taken
    # is counted against the project instead, below.
    $dlg = Wait-Until { Find-Dialog 'Select Pages' } 60 'the Select Pages dialog'
    $ok = Wait-Until { $h = [GdlSnapWin]::Button($dlg.Handle, 'OK'); if ($h -ne [IntPtr]::Zero) { $h } } 30 'its OK button'
    Write-Output '  Select Pages: OK, Select All as it opens'
    [void][GdlSnapWin]::PostMessage($ok, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero)   # BM_CLICK
}

# -- the message that says it is done -----------------------------------------
# Its progress window ('Take Page Snapshots') is up while it works; the message
# box that follows is what says it finished, and where. A large project takes
# minutes, so wait as long as the build would.
$done = Wait-Until {
    foreach ($w in @(Get-GdlWindow)) {
        $text = [GdlBlockerWindows]::Text($w.Handle)
        if ($text -match 'Snapshot completed successfully|Snapshot has been cancelled') {
            [pscustomobject]@{ Window = $w; Text = $text }
        }
    }
} $TimeoutSeconds 'the snapshot completion message'
$said = ($done.Text -replace '\s+', ' ').Trim()
Write-Output "  GUI Designer: $said"
# Answer No to "Open Folder?": IDNO, posted, so nothing waits on the click.
# That is a Windows message box's answer; one of GUI Designer's own forms takes
# its No button, through UI Automation, if the message has not gone.
[void][GdlSnapWin]::PostMessage($done.Window.Handle, 0x0111, [IntPtr]7, [IntPtr]::Zero)
Start-Sleep -Seconds 3
if (-not (@(Get-GdlWindow) | Where-Object { $_.Handle -eq $done.Window.Handle })) {
    Write-Output '  answered No (IDNO)'
} else {
    Write-Output '  IDNO left it up - its No button, through UI Automation'
    $jobs += Start-Job -ScriptBlock {
        param($Handle)
        Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
        $AE = [System.Windows.Automation.AutomationElement]
        $no = $AE::FromHandle([IntPtr]$Handle).FindFirst([System.Windows.Automation.TreeScope]::Descendants,
            (New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, 'No')))
        try { $no.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke() } catch { }
    } -ArgumentList ([int64]$done.Window.Handle)
    Start-Sleep -Seconds 5
}
foreach ($j in $jobs) { Stop-Job $j -ErrorAction SilentlyContinue; Remove-Job $j -Force -ErrorAction SilentlyContinue }
if ($said -match 'cancelled') { Stop-Run 'the snapshot was cancelled' }

# The folder is the message's: "Snapshots created in <folder> Open Folder?".
if ($said -notmatch 'created in\s+(.+?)\s+Open Folder\?') { Stop-Run "could not read the folder out of '$said'" }
$folder = $Matches[1].Trim()
if (-not (Test-Path -LiteralPath $folder)) { Stop-Run "GUI Designer named $folder, which is not there" }

# -- take what this export wrote ----------------------------------------------
# Only files written since the menu was clicked: with Overwrite Bulk Snapshot
# Folder off, an earlier export's pages would otherwise ride along.
$pngs = @(Get-ChildItem -LiteralPath $folder -Filter '*.png' -File -Recurse |
          Where-Object { $_.LastWriteTime -ge $started.AddSeconds(-2) })
if (-not $pngs.Count) { Stop-Run "$folder holds no PNG written by this export" }
if ($Mode -eq 'Individual') {
    # One PNG a page and popup, the Offline Page among them, or the export took
    # less than Select All: read off the project's own layout.json.
    Push-Location (Split-Path $PSScriptRoot -Parent)
    try {
        $want = & $Python -c ("import json, sys; from gdl.container import open_payload; " +
                              "j = json.loads(open_payload(sys.argv[1]).read('layout.json')); " +
                              "print(len(j['Pages']) + len(j['PopupPages']))") $ProjectFile
    } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0 -or [int]$want -ne $pngs.Count) {
        Stop-Run "the export wrote $($pngs.Count) PNG(s) for a project of $want page(s) and popup(s) - not taking a partial set"
    }
}
New-Item -ItemType Directory -Force -Path $Out | Out-Null
Get-ChildItem -LiteralPath $Out -Filter '*.png' -File | Remove-Item -Force
foreach ($f in $pngs) { Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $Out $f.Name) -Force }
Write-Output "  $($pngs.Count) snapshot(s) from $folder -> $Out"

if (-not $KeepOpen) { Stop-Gd }
Write-Output "SNAPSHOTS EXPORTED -> $Out"
exit 0
