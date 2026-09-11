# Trigger File > Save and Build through UI Automation instead of SendKeys.
#
# SendKeys needs the foreground, and a pipeline driven from a terminal cannot
# take it - the terminal is the foreground app and Windows will not hand it over.
# UIA invokes a control directly, so it needs no focus at all.
#
# Everything here blocks: Expand() and Invoke() on a WinForms menu do not return
# until the menu closes / the modal finishes, and UIA gives up with
# "Operation timed out (0x80131505)" long before the build does. That is not a
# failure - the click still landed. So this logs each step and never treats a
# timeout as fatal; the caller watches the .gdl, not this script.
param([string]$Log = 'C:\gdlwork\uia-build.log')

function L($m) { Add-Content -Path $Log -Value ("{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }
Set-Content -Path $Log -Value '=== uia build ==='

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$CT = [System.Windows.Automation.ControlType]

function ByName($root, $name, $scope) {
    $root.FindFirst($scope, (New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, $name)))
}

try {
    $root = $AE::RootElement
    $gd = $null
    foreach ($w in $root.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
        if ($w.Current.Name -like 'GUI Designer*') { $gd = $w; break }
    }
    if (-not $gd) { L 'no GUI Designer window'; exit 1 }
    L "window: $($gd.Current.Name)"

    $file = ByName $gd 'File' $TS::Descendants
    if (-not $file) { L 'no File menu'; exit 1 }

    # Expand blocks while the menu is open. Fire and forget.
    $null = Start-Job -ScriptBlock {
        Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
        # re-find in the job's own UIA context
        $AE = [System.Windows.Automation.AutomationElement]
        $TS = [System.Windows.Automation.TreeScope]
        $root = $AE::RootElement
        foreach ($w in $root.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
            if ($w.Current.Name -like 'GUI Designer*') {
                $f = $w.FindFirst($TS::Descendants, (New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, 'File')))
                if ($f) { try { $f.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand() } catch {} }
                break
            }
        }
    }
    L 'File expand dispatched'
    Start-Sleep -Seconds 3

    $items = $gd.FindAll($TS::Descendants,
        (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::MenuItem)))
    L "menu items visible: $($items.Count)"
    $target = $null
    foreach ($m in $items) {
        $n = $m.Current.Name
        if ($n) { L "  item: '$n' enabled=$($m.Current.IsEnabled)" }
        if ($n -and $n -match 'Save and Build') { $target = $m }
    }
    if (-not $target) { L 'NO "Save and Build" ITEM FOUND'; exit 2 }

    L "invoking: '$($target.Current.Name)'"
    try {
        $target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
        L 'invoke returned'
    } catch {
        L "invoke threw (expected if it blocked on the build): $($_.Exception.Message)"
    }
    L 'done'
    exit 0
} catch {
    L "FAILED: $($_.Exception.Message)"
    exit 3
}
