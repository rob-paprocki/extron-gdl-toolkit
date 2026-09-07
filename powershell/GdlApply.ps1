<#
    Helpers shared by BOTH appliers - Apply-GdlPlan.ps1 (build a panel from a
    spec) and Apply-GdlEdits.ps1 (change one that exists).

    They live here rather than being copied because every one of them encodes a
    finding that was expensive to get and is easy to lose in a copy:

      * values are coerced to the field's DECLARED type. A plan comes from JSON,
        so numbers arrive as Int32 while fields are UInt16/UInt64, and
        reflection neither widens nor narrows - it throws.
      * "no such field" and "the field is null" are different, and conflating
        them reports a missing field that is right there. Most colour and border
        fields are null on most controls because the value lives on the state.
      * clone, never construct - which applies to PBColor and to border
        references too, hence the donor lookups.

    Dot-source this AFTER GdlProject.ps1; it uses Get-GdlField / Set-GdlField /
    Copy-GdlObject from there.
#>

$script:Problems = @()
function Note-Problem([string]$m) {
    $script:Problems += $m
    Write-Warning $m
}

function Set-GdlFieldIfPresent {
    <#  Set a backing field, but report-and-continue when it does not exist.
        A generated plan that names one field wrong should tell you about all
        the others too, not stop at the first.

        Values are coerced to the field's declared type. A plan comes from JSON,
        so every number arrives as Int32, while the fields are UInt64 (idField),
        UInt16 (userIdField) and so on - and reflection's SetValue will not widen
        or narrow for you, it just throws. #>
    param($Object, [string]$Field, $Value)
    $t = $Object.GetType()
    while ($t -and $t.FullName -ne 'System.Object') {
        $f = $t.GetField($Field, 'Instance,Public,NonPublic,DeclaredOnly')
        if ($f) {
            $v = $Value
            if ($null -ne $v -and $f.FieldType -ne $v.GetType()) {
                try {
                    if ($f.FieldType.IsEnum) {
                        $v = [Enum]::ToObject($f.FieldType, $v)
                    } elseif ($f.FieldType.IsValueType -or $f.FieldType -eq [string]) {
                        $v = [Convert]::ChangeType($v, $f.FieldType)
                    }
                } catch {
                    Note-Problem "cannot convert '$Field' value '$v' to $($f.FieldType.Name)"
                    return $false
                }
            }
            Set-GdlField $Object $Field $v
            return $true
        }
        $t = $t.BaseType
    }
    Note-Problem "no field '$Field' on $($Object.GetType().Name)"
    return $false
}

function Get-GdlDonor {
    <#  Any instance of a class, from anywhere in the project.

        Only backing fields survive a clone, so which instance does not matter -
        but there must BE one. A project with no PBSlider cannot author a slider,
        which is the clone-never-construct rule biting. #>
    param($Project, [string]$TypeName)
    foreach ($pg in @($Project.Pages) + @($Project.PopupPages)) {
        foreach ($c in $pg.Controls) {
            if ($c.GetType().Name -eq $TypeName) { return , $c }
        }
    }
    return $null
}

$script:ColourDonor = $null
function Find-ColourDonor {
    <#  Any PBColor instance in the project, to clone when a target field is null.

        Needed because clone-never-construct applies to PBColor too, and a field
        being null is common - a button leaves textColorField null and carries
        its text colour on the state instead. #>
    param($Project)
    if ($script:ColourDonor) { return , $script:ColourDonor }
    foreach ($pg in @($Project.Pages) + @($Project.PopupPages)) {
        foreach ($c in $pg.Controls) {
            foreach ($n in 'borderFillColorField', 'textColorField', 'borderColorField') {
                $v = Get-GdlField $c $n
                if ($v) { $script:ColourDonor = $v; return , $v }
            }
        }
    }
    return $null
}

function Set-GdlColour {
    <#  Set a PBColor-valued field from a packed 0xAARRGGBB int.

        The PBColor wrapper is cloned - from the field's current value where it
        has one, otherwise from any PBColor in the project. Only its inner
        System.Drawing.Color is replaced; FromArgb avoids reflecting into a
        struct's backing field, which does not behave like a class's. #>
    param($Project, $Control, [string]$Field, $Argb)
    if ($null -eq $Argb) { return }

    # Distinguish "no such field" from "field is null" - conflating them
    # reports a missing field that is right there.
    $t = $Control.GetType(); $has = $false
    while ($t -and $t.FullName -ne 'System.Object') {
        if ($t.GetField($Field, 'Instance,Public,NonPublic,DeclaredOnly')) { $has = $true; break }
        $t = $t.BaseType
    }
    if (-not $has) { Note-Problem "no field '$Field' on $($Control.GetType().Name)"; return }

    $existing = Get-GdlField $Control $Field
    if (-not $existing) { $existing = Find-ColourDonor $Project }
    if (-not $existing) { Note-Problem "no PBColor anywhere to clone for '$Field'"; return }

    $c = Copy-GdlObject $existing
    $a = ($Argb -shr 24) -band 0xFF
    $r = ($Argb -shr 16) -band 0xFF
    $g = ($Argb -shr 8) -band 0xFF
    $b = $Argb -band 0xFF
    Set-GdlFieldIfPresent $c 'valueField' ([System.Drawing.Color]::FromArgb($a, $r, $g, $b)) | Out-Null
    Set-GdlFieldIfPresent $Control $Field $c | Out-Null
}

$script:BorderDonor = $null
function Find-BorderDonor {
    param($Project)
    if ($script:BorderDonor) { return , $script:BorderDonor }
    foreach ($pg in @($Project.Pages) + @($Project.PopupPages)) {
        foreach ($c in $pg.Controls) {
            $v = Get-GdlField $c 'borderField'
            if ($v) { $script:BorderDonor = $v; return , $v }
            $sts = Get-GdlField $c 'statesField'
            if ($sts -and $sts.Count) {
                for ($i = 0; $i -lt $sts.Count; $i++) {
                    if ($null -eq $sts[$i]) { continue }
                    $v2 = Get-GdlField $sts[$i] 'borderField'
                    if ($v2) { $script:BorderDonor = $v2; return , $v2 }
                }
            }
        }
    }
    return $null
}

function Set-GdlBorder {
    <#  Point a control's border at a named resource that already exists.

        Referencing an existing resource is the whole design: appending a NEW
        PBBorderResource has never been tested against GUI Designer, so a plan
        may only name resources the donor already carries. This checks that. #>
    param($Project, $Control, [string]$Name)
    if (-not $Name) { return }
    $known = @($Project.ResourceSet.Resources |
        Where-Object { $_.GetType().Name -eq 'PBBorderResource' } |
        ForEach-Object { $_.Name })
    if ($known -and ($known -notcontains $Name)) {
        Note-Problem "border resource '$Name' is not in the donor project; a plan may only reference existing resources"
        return
    }
    # Same null-vs-missing trap as colours: a button's own borderField is
    # usually null and the border lives on its state, so clone a reference from
    # wherever one exists rather than reporting a field that is right there.
    $existing = Get-GdlField $Control 'borderField'
    if (-not $existing) { $existing = Find-BorderDonor $Project }
    if (-not $existing) { Note-Problem "no PBResourceReferenceBorder anywhere to clone"; return }
    $ref = Copy-GdlObject $existing
    Set-GdlFieldIfPresent $ref 'resourceNameField' $Name | Out-Null
    Set-GdlFieldIfPresent $Control 'borderField' $ref | Out-Null
}
