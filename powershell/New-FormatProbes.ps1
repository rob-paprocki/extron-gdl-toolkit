# Author the format-probe projects for docs/from-scratch.md section 5, headlessly.
#
# RESULTS (2026-09-07, GUI Designer 1.27.0.9): all three opened and built with
# 0 errors, 0 warnings. See docs/from-scratch.md section 5. Kept so the probes
# can be re-run against another version, which is the point - 1.27.0.9 is the
# tested boundary, not a guarantee.
#
# Each writes one ProjectGCP that answers one question when GUI Designer opens
# and builds it. Kept separate so a failure identifies its own cause - one
# combined file would only tell you that something was wrong.
#
# This half needs no GUI. Only the open-and-build check does.
param(
    [string]$Repo = '\\Mac\Home\GitHub\rob-paprocki\extron-gdl-toolkit',
    [string]$Work = 'C:\gdlwork'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $Repo 'powershell\GdlProject.ps1')
Initialize-Gdl | Out-Null

$all = @()
foreach ($a in [AppDomain]::CurrentDomain.GetAssemblies()) {
    try { $all += $a.GetTypes() } catch { $all += $_.Exception.Types | Where-Object { $_ } }
}

function Report($m) { [Console]::WriteLine($m) }

# ---------------------------------------------------------------- test A ----
# Q1: does referencing an existing-but-never-referenced border resource work?
# This is the load-bearing one: it decides whether the usable palette is the 6
# names this project actually binds, or all 34 it defines.
$p = Open-GdlProject (Join-Path $Work 'ProjectGCP')
$target = $null
# Must be a control with a REAL named border, else the repoint is invisible and
# the test proves nothing. Popup references carry an empty border name.
foreach ($pg in @($p.Pages) + @($p.PopupPages)) {
    foreach ($c in $pg.Controls) {
        $b = Get-GdlField $c 'borderField'
        if ($b -and $b.ResourceName) { $target = $c; break }
    }
    if ($target) { break }
}
if (-not $target) { throw 'no control with a named border resource' }

$before = (Get-GdlField $target 'borderField')
Report "A: target $($target.GetType().Name) '$($target.Name)' currently uses '$($before.ResourceName)'"

$ref = Copy-GdlObject $before
Set-GdlField $ref 'resourceNameField' '3D Capsule'
Set-GdlField $target 'borderField' $ref
Report "A: repointed to '3D Capsule' (defined in the project, never referenced by any control)"
$n = Save-GdlProject $p (Join-Path $Work 'testA_ProjectGCP')
Report "A: saved testA_ProjectGCP ($n bytes)"

# ---------------------------------------------------------------- test B ----
# Q2: can a NEW PBBorderResource be appended and referenced?
# If yes the parameter space is fully open; if no, test A's answer is the ceiling.
$p2 = Open-GdlProject (Join-Path $Work 'ProjectGCP')
$rs = $p2.ResourceSet
$resources = Get-GdlField $rs 'resourcesField'
if (-not $resources) { $resources = Get-GdlField $rs 'ResourcesField' }
Report "B: resource list type $($resources.GetType().Name), count $($resources.Count)"

$donor = $null
foreach ($r in $resources) {
    if ($r.GetType().Name -eq 'PBBorderResource' -and $r.Name -like 'Afterburn*') { $donor = $r; break }
}
if (-not $donor) { foreach ($r in $resources) { if ($r.GetType().Name -eq 'PBBorderResource') { $donor = $r; break } } }
Report "B: cloning '$($donor.Name)'"

$new = Copy-GdlObject $donor
Set-GdlField $new 'nameField' 'Claude - 20 Radius 1 Thick'
$info = Get-GdlField $new 'dataField'
Set-GdlField $info 'cornerRadiusField' 20      # not present anywhere in the corpus
Set-GdlField $info 'thicknessField' 1
Set-GdlField $new 'dataField' $info
$resources.Add($new)
Report "B: appended; list count now $($resources.Count)"

# bind a control to it
$t2 = $null
foreach ($pg in @($p2.Pages) + @($p2.PopupPages)) {
    foreach ($c in $pg.Controls) {
        $b = Get-GdlField $c 'borderField'
        if ($b -and $b.ResourceName) { $t2 = $c; break }
    }
    if ($t2) { break }
}
if (-not $t2) { throw 'no control with a named border resource' }
$ref2 = Copy-GdlObject (Get-GdlField $t2 'borderField')
Set-GdlField $ref2 'resourceNameField' 'Claude - 20 Radius 1 Thick'
Set-GdlField $t2 'borderField' $ref2
Report "B: bound '$($t2.Name)' to the new resource"
$n2 = Save-GdlProject $p2 (Join-Path $Work 'testB_ProjectGCP')
Report "B: saved testB_ProjectGCP ($n2 bytes)"

# ---------------------------------------------------------------- test C ----
# Q4: does Copy-GdlObject work ACROSS two separately deserialised graphs?
# Decides whether a shared component library is possible at all.
$src = Open-GdlProject (Join-Path $Work 'ProjectGCP')
$dst = Open-GdlProject (Join-Path $Work 'ProjectGCP')
$srcPage = @($src.Pages)[0]
$donorCtl = @($srcPage.Controls)[0]
try {
    $clone = Copy-GdlObject $donorCtl
    $dstPage = @($dst.Pages)[1]
    $ctrls = Get-GdlField $dstPage 'controlsField'
    $ctrls.Add($clone)
    $n3 = Save-GdlProject $dst (Join-Path $Work 'testC_ProjectGCP')
    Report "C: cross-graph clone added and saved ($n3 bytes) - serialisation accepted it"
} catch {
    Report "C: cross-graph clone FAILED: $($_.Exception.Message)"
}

Report ''
Report 'authored. Each needs GUI Designer to open and build it to mean anything.'
Get-ChildItem $Work -Filter '*ProjectGCP' | ForEach-Object { Report "   $($_.Name)  $($_.Length)" }
