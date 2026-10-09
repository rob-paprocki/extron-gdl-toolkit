<#
    Worked end-to-end authoring example.

    Takes an existing project and adds a page, a button, a standard popup in a
    newly registered group, and a popup page reference binding them — then
    removes a popup and every reference to it. The output of this script opened
    in GUI Designer 1.28.0.7 and built successfully.

    RUN UNDER 32-BIT WINDOWS POWERSHELL 5.1:
      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -File examples\add-page-and-popup.ps1 <in> <out>

    where <in> is a ProjectGCP extracted with
      python -m gdl.container extract some.gdl out/
    and the result is repacked with
      python -m gdl.container pack some.gdl out/new_ProjectGCP "New Project.gdl"

    Everything here is clone-and-retarget: nothing is constructed. See
    docs/gdl-format.md sections 4 and 6 for why.
#>
param(
    [Parameter(Mandatory)][string]$InputGcp,
    [Parameter(Mandatory)][string]$OutputGcp,
    [string]$GroupName = 'Claude Popups'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\powershell\GdlProject.ps1')
Initialize-Gdl

$p = Open-GdlProject $InputGcp
$NONE = [uint64]::MaxValue
$nextId = Get-GdlNextPageId $p
$popupId = [uint64]($nextId + 1)
$refObjectId = [uint64]901          # control ids only need to be unique per page

# --- register the popup group FIRST; an unregistered id reads "Unassigned" ---
$groupId = Register-GdlPopupGroup $p $GroupName
"registered group $groupId '$GroupName'"

# --- new page, cloned from an existing one and stripped back ----------------
$template = $p.Pages | Where-Object { $_.Name -like '*Home*' } | Select-Object -First 1
if (-not $template) { $template = $p.Pages[0] }
$page = Copy-GdlObject $template
Set-GdlField $page 'idField' $nextId
Set-GdlField $page 'userIdField' ([uint16]$nextId)
Set-GdlField $page 'nameField' '9000 - Generated Page'

# Drop the inherited popup references and any full-screen touch target: Build
# recreates modal references itself, and a 1280x800 button hides everything.
foreach ($c in @($page.Controls)) {
    $kind = $c.GetType().Name
    if ($kind -eq 'PBPopupPageReference' -or
        ($kind -eq 'PBButton' -and $c.Width -ge 1280) -or
        $kind -eq 'PBDateTime') {
        [void]$page.Controls.Remove($c)
    }
}
# Cloned controls carry the source's IDs; give them fresh ones.
$nextControlId = 4002
foreach ($c in $page.Controls) {
    if ($c.GetType().Name -eq 'PBLabel') {
        Set-GdlField $c 'userIdField' ([uint16]$nextControlId)
        $nextControlId++
    }
}
$labels = @($page.Controls | Where-Object { $_.GetType().Name -eq 'PBLabel' })
if ($labels.Count -ge 1) { Set-GdlField $labels[0] 'textField' 'Generated page' }
if ($labels.Count -ge 2) { Set-GdlField $labels[1] 'textField' "Reference bound to '$GroupName'" }
$p.Pages.Add($page)

# --- a button ---------------------------------------------------------------
$srcButton = $null
foreach ($q in $p.Pages) {
    foreach ($c in $q.Controls) {
        if ($c.GetType().Name -eq 'PBButton' -and $c.Width -gt 100 -and $c.Width -lt 400) {
            $srcButton = $c; break
        }
    }
    if ($srcButton) { break }
}
$button = Copy-GdlObject $srcButton
Set-GdlField $button 'nameField' 'GEN_btn'
Set-GdlField $button 'textField' 'Generated Button'
Set-GdlField $button 'userIdField' ([uint16]4001)
Set-GdlField $button 'idField' ([uint64]900)
Set-GdlField $button 'leftField' 140
Set-GdlField $button 'topField' 700
# every state carries its own caption
for ($i = 0; $i -lt $button.States.Count; $i++) {
    Set-GdlField $button.States.Item($i) 'textField' 'Generated Button'
}
$page.Controls.Add($button)

# --- a STANDARD (non-modal) popup in the new group --------------------------
# Modal popups are full screen, ungrouped, and referenced automatically by
# Build. Only standard popups are placed by a hand-authored reference.
$srcPopup = $p.PopupPages | Where-Object { -not $_.Modal } | Select-Object -First 1
$popup = Copy-GdlObject $srcPopup
Set-GdlField $popup 'idField' $popupId
Set-GdlField $popup 'userIdField' ([uint16]$popupId)
Set-GdlField $popup 'nameField' '9100 - Generated Popup'
Set-GdlField $popup 'modalField' $false
Set-GdlField $popup 'groupIDField' $groupId
Set-GdlField $popup 'groupNameField' $GroupName     # members store the NAME too

# --- the reference, bound to the group --------------------------------------
$srcRef = $null
foreach ($q in $p.Pages) {
    foreach ($c in $q.Controls) {
        if ($c.GetType().Name -eq 'PBPopupPageReference' -and $c.PopupPageID.IsPopupGroupIdValid) {
            $srcRef = $c; break
        }
    }
    if ($srcRef) { break }
}
$ref = Copy-GdlObject $srcRef
Set-GdlField $ref 'nameField' 'GEN_ref'
Set-GdlField $ref 'idField' $refObjectId
Set-GdlField $ref 'leftField' 190
Set-GdlField $ref 'topField' 135
Set-GdlField $ref 'widthField' ([int]$popup.Width)      # anchor must match the popup
Set-GdlField $ref 'heightField' ([int]$popup.Height)
$binding = $ref.PopupPageID
Set-GdlField $binding 'popupIDField' $NONE              # sentinel: bound by group
Set-GdlField $binding 'groupIDField' $groupId
Set-GdlField $binding 'popupNameField' ''
Set-GdlField $binding 'groupNameField' $GroupName
$page.Controls.Add($ref)

# --- the other half: popup -> reference back-pointer ------------------------
$backSrc = Get-GdlField ($p.PopupPages | Where-Object { -not $_.Modal } | Select-Object -First 1) 'popupReferencesField'
$back = Copy-GdlObject $backSrc[0]
Set-GdlField $back 'pageIDField' $nextId
Set-GdlField $back 'objectIDField' $refObjectId
Set-GdlField $back 'popupPageIDField' $NONE
$list = [Activator]::CreateInstance($backSrc.GetType())
$list.Add($back)
Set-GdlField $popup 'popupReferencesField' $list
Set-GdlField $popup 'hasReferencesField' $true
$p.PopupPages.Add($popup)

# --- removal: a popup and every reference that points at it -----------------
$victim = $p.PopupPages | Where-Object { $_.Modal -and $_.Name -notlike '*Offline*' } | Select-Object -Last 1
if ($victim) {
    $vid = [uint64]$victim.ID
    $killed = 0
    foreach ($q in @($p.Pages) + @($p.PopupPages)) {
        foreach ($c in @($q.Controls)) {
            if ($c.GetType().Name -eq 'PBPopupPageReference' -and
                [uint64]$c.PopupPageID.PopupID -eq $vid) {
                [void]$q.Controls.Remove($c); $killed++
            }
        }
    }
    [void]$p.PopupPages.Remove($victim)
    "removed popup $vid '$($victim.Name)' and $killed reference(s)"
}

# --- assert before saving: every binding site must agree --------------------
$check = Test-GdlPopupBinding $p $popupId
if (-not $check.ok) {
    throw "popup $popupId is not correctly bound: $($check.problems -join '; ')"
}
"binding verified: $($check.references) reference(s)"

$bytes = Save-GdlProject $p $OutputGcp
"wrote $OutputGcp ($bytes bytes); pages=$($p.Pages.Count) popups=$($p.PopupPages.Count)"
