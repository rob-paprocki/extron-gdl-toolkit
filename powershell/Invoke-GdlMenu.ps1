<#
    Click a GUI Designer menu item through UI Automation. No focus required.

        powershell\Invoke-GdlMenu.ps1 -Item 'Save and Build...'

    This is what makes the pipeline runnable while you are using the machine.
    SendKeys types into whatever holds the foreground, so driving it from a
    terminal cannot work: the terminal is the foreground app, Windows refuses to
    hand the foreground to a process that does not already have it, and the
    keystroke lands in the terminal. UIA invokes the control directly.

    Three things about doing it this way:

    * Expand() on the File menu BLOCKS while the menu is open, so it is
      dispatched to a background job and never waited on.
    * Invoke() on the item blocks on the build modal and then throws
      `Operation timed out (0x80131505)`. The click still landed - measured, a
      three-page project rebuilt from 2,751,958 to 2,848,073 bytes across that
      exact exception. So a timeout is logged, not treated as failure. Watch the
      .gdl with Wait-GdlBuild.ps1; do not believe this script's exit code about
      whether the build finished, only about whether the item was clicked.
    * The wizard is the opposite case and cannot be driven this way at all - its
      controls expose no UIA providers. Only the main window's menus do. See
      docs/from-scratch.md section 5c.
#>
param(
    [Parameter(Mandatory)][string]$Item,
    [string]$Menu = 'File',
    [string]$Window = 'GUI Designer*',
    [int]$MenuWaitSeconds = 3
)

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$CT = [System.Windows.Automation.ControlType]

function Find-Window {
    $root = $AE::RootElement
    foreach ($w in $root.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
        if ($w.Current.Name -like $Window) { return $w }
    }
    return $null
}

$gd = Find-Window
if (-not $gd) { Write-Output "no window matching '$Window'"; exit 1 }
Write-Output "window: $($gd.Current.Name)"

$top = $gd.FindFirst($TS::Descendants,
    (New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, $Menu)))
if (-not $top) { Write-Output "no '$Menu' menu"; exit 1 }

# Fire and forget: this does not return until the menu closes.
$job = Start-Job -ArgumentList $Window, $Menu -ScriptBlock {
    param($Window, $Menu)
    Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
    $AE = [System.Windows.Automation.AutomationElement]
    $TS = [System.Windows.Automation.TreeScope]
    foreach ($w in $AE::RootElement.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
        if ($w.Current.Name -like $Window) {
            $m = $w.FindFirst($TS::Descendants,
                (New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, $Menu)))
            if ($m) {
                try { $m.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand() } catch { }
            }
            break
        }
    }
}
Start-Sleep -Seconds $MenuWaitSeconds

$target = $null
foreach ($m in $gd.FindAll($TS::Descendants,
        (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::MenuItem)))) {
    if ($m.Current.Name -like "$Item*") { $target = $m; break }
}
if (-not $target) {
    Write-Output "no menu item matching '$Item' under '$Menu'"
    Stop-Job $job -ErrorAction SilentlyContinue
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    exit 2
}
if (-not $target.Current.IsEnabled) {
    Write-Output "'$($target.Current.Name)' is disabled"
    exit 3
}

Write-Output "invoking '$($target.Current.Name)'"
try {
    $target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Write-Output 'invoke returned'
} catch {
    # Expected whenever the item opens a modal. The click landed regardless.
    Write-Output "invoke blocked on a modal (this is normal): $($_.Exception.Message)"
}
Stop-Job $job -ErrorAction SilentlyContinue
Remove-Job $job -Force -ErrorAction SilentlyContinue
exit 0
