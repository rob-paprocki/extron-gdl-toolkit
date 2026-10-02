<#
    A seed, made by GUI Designer's Project Create Wizard with nobody at the mouse.

        powershell\New-GdlSeed.ps1 -List
        powershell\New-GdlSeed.ps1 -PanelType 'TLP Pro 725T' -ListThemes
        powershell\New-GdlSeed.ps1 -PanelType 'TLP Pro 725T' -Model TLP725T `
            -Theme 'Afterburn' -Output 'seeds\Afterburn 725.gdl'

    -List prints what Panel Type offers; -ListThemes what Theme offers once a
    panel is chosen. Names are the wizard's own, exactly.

    Only a real click commits a combo. ValuePattern.SetValue and
    SelectionItemPattern.Select both leave the wizard reading right and
    internally unselected, Create greyed and the accessibility tree hung
    (docs/from-scratch.md section 5c). The Theme radio is clicked too, because
    the wizard fills Theme on its own and builds Blank while reading
    "Theme: X". Its radios expose no state, so a screenshot of the wizard is
    saved before Create - and the saved file must pass tests/verify_seed.py as a
    themed project for -Model, or it is deleted.

    A click by position goes to whatever window is on top, so each click raises
    the wizard first and refuses to click unless GUI Designer owns the window
    under the point. Needs an interactive desktop, like New-GdlPanel.ps1.

    It closes any GUI Designer already running, unsaved work and all - the
    wizard has to open in an instance this script owns - and says so first.

    Exit codes: 0 made and verified; 2 bad arguments; 3 a name the wizard does
    not offer (it prints what it does); 4 a click that did not take; 5 GUI
    Designer or a dialog did not appear; 6 the verifier could not run; the
    verifier's code if it refused. On 6 and a refusal the saved file is removed.
#>
param(
    [string]$PanelType,
    [string]$Model,
    [string]$Theme,
    [string]$Application,
    [string]$Output,
    [switch]$List,
    [switch]$ListThemes,
    [string]$Python = 'python',
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer'
)

# UI Automation's client assemblies are .NET Framework ones.
if ($PSVersionTable.PSEdition -eq 'Core') {
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
    foreach ($k in $PSBoundParameters.Keys) {
        $v = $PSBoundParameters[$k]
        if ($v -is [System.Management.Automation.SwitchParameter]) { if ($v) { $a += "-$k" } }
        else { $a += "-$k"; $a += "$v" }
    }
    & "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" @a
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$gd = Join-Path $InstallDir 'GUI Designer.exe'
if (-not (Test-Path $gd)) { Write-Output "GUI Designer not found at $gd"; exit 2 }
if (-not $List) {
    if (-not $PanelType) { Write-Output '-PanelType is required (see -List)'; exit 2 }
    if (-not $ListThemes) {
        if (-not ($Model -and $Theme -and $Output)) {
            Write-Output '-Model, -Theme and -Output are required to make a seed'; exit 2
        }
        $Output = [System.IO.Path]::GetFullPath($Output)
        if (Test-Path $Output) { Write-Output "$Output exists - not overwriting a seed"; exit 2 }
    }
}

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System; using System.Text; using System.Collections.Generic; using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)] public struct SeedPt { public int X; public int Y; }
public class SeedWin {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(SeedPt p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, string l);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  public static string Cls(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }
  public static string Txt(IntPtr h) { var s = new StringBuilder(512); GetWindowText(h, s, 512); return s.ToString(); }
  public static List<IntPtr> Tops(uint pid) { var r = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (p == pid) r.Add(h); return true; }, IntPtr.Zero); return r; }
  public static List<IntPtr> Kids(IntPtr p) { var r = new List<IntPtr>();
    EnumChildWindows(p, (h, l) => { r.Add(h); return true; }, IntPtr.Zero); return r; }
}
"@
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$CT = [System.Windows.Automation.ControlType]
$All = [System.Windows.Automation.Condition]::TrueCondition

function Get-GdPids { @(Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | ForEach-Object Id) }

function Get-GdWindows {
    $pids = Get-GdPids
    # A window can close mid-walk - the File menu's dropdown as Save As opens -
    # and UI Automation throws ElementNotAvailable for it. Walk again.
    for ($i = 0; $i -lt 5; $i++) {
        try {
            return @($AE::RootElement.FindAll($TS::Children, $All) |
                Where-Object { $pids -contains $_.Current.ProcessId })
        } catch { Start-Sleep -Milliseconds 300 }
    }
    return @()
}

function New-Cond($name, $type) {
    $n = New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, $name)
    if (-not $type) { return $n }
    $t = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $type)
    New-Object System.Windows.Automation.AndCondition($n, $t)
}

function Get-Wizard {
    $found = @()
    foreach ($w in Get-GdWindows) {
        if ($w.Current.Name -eq 'Project Create Wizard') { $found += $w }
        $found += @($w.FindAll($TS::Descendants, (New-Cond 'Project Create Wizard')))
    }
    # Two wizards means one was opened over the other (see the launch below):
    # the one underneath reads as a wizard with no combos, and queries can hang.
    if ($found.Count -gt 1) {
        Write-Output "$($found.Count) Project Create Wizards are open - one was opened over another; not clicking into either"
        Stop-Gd; exit 5
    }
    if ($found.Count) { return $found[0] }
    return $null
}

function Stop-Gd {
    Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
}

function Save-Shot($path) {
    try {
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
        [System.Drawing.Graphics]::FromImage($bmp).CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
        $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
        return $true
    } catch { return $false }
}

# A locked screen, or a minimized Remote Desktop window, has no desktop to draw
# on: the wizard's dropdowns never open, Expand() blocks for good, and a click by
# position lands nowhere. Screen capture fails the same way ("The handle is
# invalid"), so it is the check.
function Test-Desktop {
    try {
        $bmp = New-Object System.Drawing.Bitmap 1, 1
        [System.Drawing.Graphics]::FromImage($bmp).CopyFromScreen(0, 0, 0, 0, (New-Object System.Drawing.Size 1, 1))
        return $true
    } catch { return $false }
}

function Invoke-Click([int]$x, [int]$y) {
    $wiz = Get-Wizard
    if ($wiz) {
        $h = [IntPtr]$wiz.Current.NativeWindowHandle
        if ($h -ne [IntPtr]::Zero) {
            [void][SeedWin]::ShowWindow($h, 5)
            [void][SeedWin]::BringWindowToTop($h)
            [void][SeedWin]::SetForegroundWindow($h)
        }
    }
    Start-Sleep -Milliseconds 600
    $p = New-Object SeedPt; $p.X = $x; $p.Y = $y
    $under = [SeedWin]::WindowFromPoint($p)
    [uint32]$owner = 0
    [void][SeedWin]::GetWindowThreadProcessId($under, [ref]$owner)
    if ((Get-GdPids) -notcontains [int]$owner) {
        Write-Output "refusing to click ($x,$y): the window there belongs to process $owner, not GUI Designer"
        Stop-Gd; exit 4
    }
    [void][SeedWin]::SetCursorPos($x, $y)
    [SeedWin]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)   # left down
    [SeedWin]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)   # left up
}

function Get-Combo($name) {
    # The wizard's window appears before its controls are in the tree.
    $deadline = (Get-Date).AddSeconds(30)
    do {
        $wiz = Get-Wizard
        if (-not $wiz) { Write-Output 'the wizard has gone'; Stop-Gd; exit 5 }
        $c = $wiz.FindFirst($TS::Descendants, (New-Cond $name $CT::ComboBox))
        if ($c) { return $c }
        Start-Sleep -Milliseconds 700
    } while ((Get-Date) -lt $deadline)
    $seen = @($wiz.FindAll($TS::Descendants,
        (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::ComboBox))) |
        ForEach-Object { "'$($_.Current.Name)'" })
    Write-Output "the wizard has no '$name' combo (combos: $($seen -join ', '); wizard element: $($wiz.Current.ControlType.ProgrammaticName) '$($wiz.Current.Name)')"
    Stop-Gd; exit 5
}

function Get-Items($combo) {
    $name = $combo.Current.Name
    $ec = $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
    $job = $null
    if ($ec.Current.ExpandCollapseState -ne 'Expanded') {
        # Expand() can block until the dropdown closes, so it runs in a job and
        # is never waited on - the same reason Invoke-GdlMenu.ps1 does.
        $job = Start-Job -ArgumentList $name -ScriptBlock {
            param($name)
            Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
            $AE = [System.Windows.Automation.AutomationElement]
            $TS = [System.Windows.Automation.TreeScope]
            $pids = @(Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | ForEach-Object Id)
            # The combo's type as well as its name: its label is a Text element
            # of the same name, earlier in the tree, and has nothing to expand.
            $n = New-Object System.Windows.Automation.AndCondition(
                (New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, $name)),
                (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty,
                    [System.Windows.Automation.ControlType]::ComboBox)))
            foreach ($w in $AE::RootElement.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
                if ($pids -notcontains $w.Current.ProcessId) { continue }
                $c = $w.FindFirst($TS::Descendants, $n)
                if ($c) {
                    try { $c.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand() } catch { }
                    break
                }
            }
        }
    }
    $cond = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::ListItem)
    $out = @()
    $deadline = (Get-Date).AddSeconds(20)
    while (-not $out.Count -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 700
        # The open dropdown is a window of its own; the wizard's own lists are not it.
        foreach ($w in Get-GdWindows) {
            if ($w.Current.Name -eq 'Project Create Wizard') { continue }
            foreach ($li in $w.FindAll($TS::Descendants, $cond)) {
                $r = $li.Current.BoundingRectangle
                $out += [pscustomobject]@{ Name = $li.Current.Name
                                           X = [int]($r.X + $r.Width / 2); Y = [int]($r.Y + $r.Height / 2) }
            }
        }
    }
    if ($job) { Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue }
    if (-not $out.Count) {
        Write-Output "the '$name' dropdown did not open within 20 s"
        Stop-Gd; exit 5
    }
    return , $out
}

function Close-Combo($combo) {
    try { $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Collapse() } catch { }
}

function Select-ComboItem($name, $item) {
    $combo = Get-Combo $name
    $items = Get-Items $combo
    $hit = $items | Where-Object { $_.Name -eq $item } | Select-Object -First 1
    if (-not $hit) {
        Write-Output "'$item' is not offered under '$name'. It offers:"
        $items | ForEach-Object { Write-Output "  $($_.Name)" }
        Close-Combo $combo
        Stop-Gd; exit 3
    }
    Invoke-Click $hit.X $hit.Y
    Start-Sleep -Seconds 2
    $v = (Get-Combo $name).GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value
    if ($v -ne $item) {
        Write-Output "clicked '$item' under '$name' but it reads '$v'"
        Stop-Gd; exit 4
    }
    Write-Output "  $name $v"
}

function Click-Named($name) {
    $wiz = Get-Wizard
    $e = $wiz.FindFirst($TS::Descendants, (New-Cond $name))
    if (-not $e) { Write-Output "the wizard has no '$name'"; Stop-Gd; exit 5 }
    if (-not $e.Current.IsEnabled) { Write-Output "'$name' is disabled"; Stop-Gd; exit 4 }
    $r = $e.Current.BoundingRectangle
    Invoke-Click ([int]($r.X + $r.Width / 2)) ([int]($r.Y + $r.Height / 2))
}

function Wait-For([scriptblock]$test, [int]$seconds, [string]$what) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        # An element can vanish between finding it and reading it; that is a
        # poll that found nothing yet, not a failure.
        try { $r = & $test } catch { $r = $null }
        if ($r) { return $r }
        Start-Sleep -Milliseconds 700
    }
    Write-Output "$what did not appear within $seconds s"
    Stop-Gd; exit 5
}

# -- open the wizard ------------------------------------------------------------
if (-not (Test-Desktop)) {
    Write-Output ('no desktop to draw on - the screen is locked, or this is a minimized Remote ' +
                  'Desktop session. The wizard needs real clicks: unlock it, or restore the window, and rerun.')
    exit 5
}
$running = @(Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue)
if ($running.Count) {
    Write-Output ("closing $($running.Count) running GUI Designer - unsaved work in it is lost; " +
                  'the wizard needs one this script owns')
}
Stop-Gd
Start-Sleep -Seconds 2
Start-Process -FilePath $gd
[void](Wait-For { Get-GdWindows | Where-Object { $_.Current.Name -like 'GUI Designer*' -or $_.Current.Name -eq 'Project Create Wizard' } } 180 'GUI Designer')
# GUI Designer opens the wizard itself once it has loaded, seconds after its
# main window appears (1.4 s and about 12 s, warm). File > New Project in that
# gap opens a second wizard over the first, and UI Automation then finds one
# with no combos or hangs. So wait for its own, and use the menu only if none
# comes.
$deadline = (Get-Date).AddSeconds(180)
while (-not (Get-Wizard) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 700 }
if (-not (Get-Wizard)) {
    # Invoke blocks on the modal and times out; the wizard opens regardless.
    & "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $PSScriptRoot 'Invoke-GdlMenu.ps1') -Item 'New Project' | ForEach-Object { "  menu: $_" }
}
[void](Wait-For { Get-Wizard } 60 'the Project Create Wizard')
Write-Output 'wizard open'

if ($List) {
    $combo = Get-Combo 'Panel Type:'
    (Get-Items $combo) | ForEach-Object { Write-Output $_.Name }
    Close-Combo $combo
    Stop-Gd; exit 0
}

Select-ComboItem 'Panel Type:' $PanelType

if ($ListThemes) {
    $combo = Get-Combo 'Theme:'
    (Get-Items $combo) | ForEach-Object { Write-Output $_.Name }
    Close-Combo $combo
    $combo = Get-Combo 'Application:'
    Write-Output "Application: $($combo.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value)"
    Stop-Gd; exit 0
}

# The radio first: Theme's combo fills itself while Blank stays selected.
Click-Named 'Theme'
Start-Sleep -Seconds 1
Select-ComboItem 'Theme:' $Theme
if ($Application) { Select-ComboItem 'Application:' $Application }

$shot = Join-Path ([System.IO.Path]::GetDirectoryName($Output)) (
    [System.IO.Path]::GetFileNameWithoutExtension($Output) + '-wizard.png')
if ($env:CLAUDE_JOB_DIR) { $shot = Join-Path $env:CLAUDE_JOB_DIR ('tmp\' + [System.IO.Path]::GetFileName($shot)) }
if (Save-Shot $shot) { Write-Output "wizard as created: $shot" }
else { Write-Output 'no screenshot of the wizard (screen capture failed); the verifier still checks the result' }

Click-Named 'Create'
$proc = Wait-For {
    $p = Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p) { $p.Refresh() }   # MainWindowTitle is cached until Refresh
    if ($p -and $p.MainWindowTitle -like 'GUI Designer - `[*') { $p }
} 180 'the new project'
Write-Output "  $($proc.MainWindowTitle)"

# -- save it --------------------------------------------------------------------
# The title names the project before the window has a menu bar: Create is
# still building the project from the template. Wait for the File menu, and
# say what else GUI Designer has open meanwhile - a dialog would explain a wait.
$t0 = Get-Date
$seen = @{}
$main = $null
while (((Get-Date) - $t0).TotalSeconds -lt 180) {
    try {
        foreach ($w in Get-GdWindows) {
            $n = $w.Current.Name
            if ($n -like 'GUI Designer - `[*') { $main = $w; continue }
            if (-not $seen[$n]) { $seen[$n] = $true; Write-Output "  also open: '$n'" }
        }
        if ($main -and $main.FindFirst($TS::Descendants, (New-Cond 'File' $CT::MenuItem))) { break }
    } catch { }   # a window closed mid-walk; look again
    Start-Sleep -Seconds 2
}
Write-Output ("  menu bar after {0:N0} s" -f ((Get-Date) - $t0).TotalSeconds)
# The item carries the project's name - "Save Afterburn All-inclusive 1220
# As..." (archive/gdlwork/uia-build.log) - so match around it.
for ($try = 1; $try -le 3; $try++) {
    & "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $PSScriptRoot 'Invoke-GdlMenu.ps1') -Item 'Save * As...' | ForEach-Object { "  menu: $_" }
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 5
}
if ($LASTEXITCODE -ne 0) {
    $fail = Join-Path ([System.IO.Path]::GetTempPath()) 'New-GdlSeed-save.png'
    if ($env:CLAUDE_JOB_DIR) { $fail = Join-Path $env:CLAUDE_JOB_DIR 'tmp\New-GdlSeed-save.png' }
    if (Save-Shot $fail) { Write-Output "the screen when Save As could not be reached: $fail" }
    Stop-Gd; exit 5
}
# "Save Project As (<project name>)" is the Windows common dialog, and UI
# Automation cannot drive it: opened by a UIA Invoke, it answers slowly or not
# at all - a 111 s walk of it returned neither its File name box nor its Save
# button. Plain window messages work at once, with no mouse and no focus:
# WM_SETTEXT into the box, then WM_COMMAND IDOK to the dialog.
$gdPid = [uint32](Get-GdPids | Select-Object -First 1)
$dialog = Wait-For {
    foreach ($h in [SeedWin]::Tops($gdPid)) {
        if ([SeedWin]::Cls($h) -eq '#32770' -and [SeedWin]::IsWindowVisible($h) -and
            [SeedWin]::Txt($h) -like 'Save Project As*') { return $h }
    }
} 60 'the Save Project As dialog'
Write-Output "  dialog: $([SeedWin]::Txt($dialog))"
# The File name box is the visible Edit in a ComboBox under FloatNotifySink;
# the address bar's Edit is the dialog's only other one, and hidden.
$box = [SeedWin]::Kids($dialog) | Where-Object {
    [SeedWin]::Cls($_) -eq 'Edit' -and [SeedWin]::IsWindowVisible($_) -and
    [SeedWin]::Cls([SeedWin]::GetParent($_)) -eq 'ComboBox' -and
    [SeedWin]::Cls([SeedWin]::GetParent([SeedWin]::GetParent($_))) -eq 'FloatNotifySink' } |
    Select-Object -First 1
if (-not $box) { Write-Output 'the Save Project As dialog has no File name box'; Stop-Gd; exit 5 }
[void][SeedWin]::SendMessage($box, 0x000C, [IntPtr]::Zero, $Output)        # WM_SETTEXT
[void][SeedWin]::PostMessage($dialog, 0x0111, [IntPtr]1, [IntPtr]::Zero)   # WM_COMMAND IDOK: Save
[void](Wait-For { if (Test-Path $Output) { $s1 = (Get-Item $Output).Length; Start-Sleep -Seconds 2
                  if ((Get-Item $Output).Length -eq $s1 -and $s1 -gt 0) { $true } } } 120 $Output)
Stop-Gd
Write-Output "saved $Output"

# -- refuse a wrong seed --------------------------------------------------------
# A seed nobody verified must not stay where the next run refuses to overwrite
# it, so a verifier that cannot run at all - no Python on this host's PATH, a
# wrong -Python - removes it as a refusal does. Under 'Stop' that call throws.
try {
    & $Python (Join-Path $repo 'tests\verify_seed.py') $Output $Model
    $code = $LASTEXITCODE
} catch {
    Write-Output "could not run '$Python' to verify the seed: $($_.Exception.Message)"
    $code = 6
}
if ($code -ne 0) {
    Remove-Item $Output -Force
    Write-Output "removed $Output - not verified as a themed $Model seed"
    exit $code
}
exit 0
