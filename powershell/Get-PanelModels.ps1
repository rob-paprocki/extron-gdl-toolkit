# Read the authoritative panel model list out of GUI Designer's own Project
# Create Wizard, and map each model to its resolution.
#
# WHY: model names must never be reconstructed from internal class symbols like
# PBTLP1720MGPlatform. TLC and TLP are different product lines, and class names
# outlive retired products. The wizard dropdown is what Extron ships.
#
# Open File > New Project first, then run this with --current-user (it needs a
# desktop to read the dropdown).

# Open the Panel Type dropdown and read its items.
#
# A WinForms ComboBox does not expose its ListItems to UI Automation until the
# drop-down is actually shown, so focus it, drop it, then re-query.
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Windows.Forms

$proc = Get-Process | Where-Object { $_.ProcessName -eq 'GUI Designer' } | Select-Object -First 1
$main = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
$combos = $main.FindAll([System.Windows.Automation.TreeScope]::Descendants,
    (New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::ComboBox)))

$panel = $null
foreach ($c in $combos) { if ($c.Current.Name -match 'Panel Type') { $panel = $c; break } }
if (-not $panel) { Write-Output 'Panel Type combo not found'; return }

$panel.SetFocus()
Start-Sleep -Milliseconds 400
try {
    $exp = $panel.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
    $exp.Expand()
    Start-Sleep -Milliseconds 1200
    Write-Output "expand state: $($exp.Current.ExpandCollapseState)"
} catch {
    Write-Output "expand failed: $($_.Exception.Message); falling back to Alt+Down"
    [System.Windows.Forms.SendKeys]::SendWait('%{DOWN}')
    Start-Sleep -Milliseconds 1200
}




$repo = '\\Mac\Home\GitHub\rob-paprocki\extron-gdl-toolkit'
Import-Module -Name (Join-Path $repo 'powershell\GdlProject.ps1') -ErrorAction SilentlyContinue
if (-not (Get-Command Initialize-Gdl -ErrorAction SilentlyContinue)) {
    # Import-Module will not take a .ps1; fall back to reading and invoking it.
    $sb = [ScriptBlock]::Create((Get-Content -Raw (Join-Path $repo 'powershell\GdlProject.ps1')))
    . $sb
}
Initialize-Gdl | Out-Null

$all = @()
foreach ($a in [AppDomain]::CurrentDomain.GetAssemblies()) {
    try { $all += $a.GetTypes() } catch { $all += $_.Exception.Types | Where-Object { $_ } }
}
$plats = @{}
foreach ($t in ($all | Where-Object { $_.Name -match '^PB.*Platform$' })) {
    $inst = $null
    try { $inst = [Activator]::CreateInstance($t) } catch {
        try { $inst = [System.Runtime.Serialization.FormatterServices]::GetUninitializedObject($t) } catch { }
    }
    if (-not $inst) { continue }
    try {
        $r = $t.GetProperty('Resolution').GetValue($inst)
        if ($r -and $r.Width) {
            # PBTLP1720MGPlatform -> TLP1720MG
            $key = $t.Name -replace '^PB', '' -replace 'Platform$', ''
            $plats[$key.ToUpper()] = "$($r.Width)x$($r.Height)"
        }
    } catch { }
}

Write-Output "platform classes with a resolution: $($plats.Count)"
# Model names from the wizard dropdown, opened above.
$root = [System.Windows.Automation.AutomationElement]::RootElement
$items = $root.FindAll([System.Windows.Automation.TreeScope]::Subtree,
    (New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::ListItem)))
$names = @()
foreach ($it in $items) { if ($it.Current.Name) { $names += $it.Current.Name } }
$names = $names | Select-Object -Unique | Where-Object { $_ -ne 'Select Your Panel' }
Write-Output "model names from the wizard: $($names.Count)"
Write-Output ''

foreach ($n in $names) {
    $key = ($n -replace '\s', '').ToUpper()     # "TLP Pro 1720MG" -> TLPPRO1720MG
    $key2 = $key -replace 'PRO', ''             # -> TLP1720MG
    $res = $plats[$key2]
    if (-not $res) { $res = $plats[$key] }
    if ($res) { Write-Output ("{0,-30} {1}" -f $n, $res) }
    else      { Write-Output ("{0,-30} NO MATCHING PLATFORM CLASS" -f $n) }
}
