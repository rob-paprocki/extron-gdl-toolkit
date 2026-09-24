<#
    A seed, made by GUI Designer's Project Create Wizard with nobody at the mouse.

        powershell\New-GdlSeed.ps1 -List
        powershell\New-GdlSeed.ps1 -PanelType 'TLP Pro 725T' -ListThemes
        powershell\New-GdlSeed.ps1 -PanelType 'TLP Pro 725T' -Model TLP725T `
            -Theme 'Afterburn All-inclusive 1020' -Output 'seeds\Afterburn 725.gdl'

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

    Exit codes: 0 made and verified; 2 bad arguments; 3 a name the wizard does
    not offer (it prints what it does); 4 a click that did not take; 5 GUI
    Designer or a dialog did not appear; the verifier's code if it refused.
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
using System; using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)] public struct SeedPt { public int X; public int Y; }
public class SeedWin {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(SeedPt p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
"@
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$CT = [System.Windows.Automation.ControlType]
$All = [System.Windows.Automation.Condition]::TrueCondition

function Get-GdPids { @(Get-Process -Name 'GUI Designer' -ErrorAction SilentlyContinue | ForEach-Object Id) }

function Get-GdWindows {
    $pids = Get-GdPids
    @($AE::RootElement.FindAll($TS::Children, $All) | Where-Object { $pids -contains $_.Current.ProcessId })
}

function New-Cond($name, $type) {
    $n = New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, $name)
    if (-not $type) { return $n }
    $t = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $type)
    New-Object System.Windows.Automation.AndCondition($n, $t)
}

function Get-Wizard {
    foreach ($w in Get-GdWindows) {
        if ($w.Current.Name -eq 'Project Create Wizard') { return $w }
        $d = $w.FindFirst($TS::Descendants, (New-Cond 'Project Create Wizard'))
        if ($d) { return $d }
    }
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
            $n = New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, $name)
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
        $r = & $test
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
Stop-Gd
Start-Sleep -Seconds 2
Start-Process -FilePath $gd
[void](Wait-For { Get-GdWindows | Where-Object { $_.Current.Name -like 'GUI Designer*' -or $_.Current.Name -eq 'Project Create Wizard' } } 180 'GUI Designer')
Start-Sleep -Seconds 3
if (-not (Get-Wizard)) {
    # Invoke blocks on the modal and times out; the wizard opens regardless.
    & "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $PSScriptRoot 'Invoke-GdlMenu.ps1') -Item 'New Project' | Out-Null
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
& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $PSScriptRoot 'Invoke-GdlMenu.ps1') -Item 'Save As' | Out-Null
$dialog = Wait-For {
    foreach ($w in Get-GdWindows) {
        $d = if ($w.Current.Name -eq 'Save As') { $w } else { $w.FindFirst($TS::Descendants, (New-Cond 'Save As' $CT::Window)) }
        if ($d) { return $d }
    }
} 60 'the Save As dialog'
# A common dialog, not the wizard: SetValue is how its file name is typed.
$name = $dialog.FindFirst($TS::Descendants, (New-Cond 'File name:' $CT::Edit))
if (-not $name) { Write-Output 'the Save As dialog has no File name box'; Stop-Gd; exit 5 }
$name.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($Output)
$save = $dialog.FindFirst($TS::Descendants, (New-Cond 'Save' $CT::Button))
if (-not $save) { Write-Output 'the Save As dialog has no Save button'; Stop-Gd; exit 5 }
try { $save.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke() } catch { }
[void](Wait-For { if (Test-Path $Output) { $s1 = (Get-Item $Output).Length; Start-Sleep -Seconds 2
                  if ((Get-Item $Output).Length -eq $s1 -and $s1 -gt 0) { $true } } } 120 $Output)
Stop-Gd
Write-Output "saved $Output"

# -- refuse a wrong seed --------------------------------------------------------
& $Python (Join-Path $repo 'tests\verify_seed.py') $Output $Model
$code = $LASTEXITCODE
if ($code -ne 0) {
    Remove-Item $Output -Force
    Write-Output "removed $Output - not a themed $Model seed"
    exit $code
}
exit 0
