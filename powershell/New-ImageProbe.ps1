# Probe: can a NEW image resource be appended and bound to a button's icon slot?
#
# The border-resource append is proven (docs/from-scratch.md section 5). Images
# are the OTHER half of the icon story - the Afterburn kit ships 1,316 icon PNGs
# and real panels use them heavily (the Liberty Bank fixture carries 38 image
# resources and 1,855 references). The font route covers single-colour icons;
# this covers everything else.
#
# Uses an icon from Extron's own resource kit, which is the realistic workflow.
param(
    [string]$Repo = '\\Mac\Home\GitHub\rob-paprocki\extron-gdl-toolkit',
    [string]$Work = 'C:\gdlwork',
    [string]$Icon = 'C:\Users\Public\Documents\Extron\GUI Designer Templates\Resources\Afterburn\Icons'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $Repo 'powershell\GdlProject.ps1')
Initialize-Gdl | Out-Null
Add-Type -AssemblyName System.Drawing

function Report($m) { [Console]::WriteLine($m) }

# Pick a real icon PNG from the kit.
$png = Get-ChildItem -Path $Icon -Filter *.png -Recurse | Select-Object -First 1
if (-not $png) { throw "no icon PNGs under $Icon" }
Report "icon: $($png.FullName)"

$p = Open-GdlProject (Join-Path $Work 'ProjectGCP')
$resources = Get-GdlField $p.ResourceSet 'resourcesField'
$before = $resources.Count

# Clone an existing image resource and replace its bitmap. Same clone-never-
# construct rule as everything else: PBImageResource's constructor is no more
# reachable headless than PBPage's.
$donor = $null
foreach ($r in $resources) { if ($r.GetType().Name -eq 'PBImageResource') { $donor = $r; break } }
if (-not $donor) { throw 'no PBImageResource to clone' }
Report "cloning image resource '$($donor.Name)' ($($donor.Width)x$($donor.Height))"

$bmp = New-Object System.Drawing.Bitmap($png.FullName)
Report "new bitmap: $($bmp.Width)x$($bmp.Height) $($bmp.PixelFormat)"

$new = Copy-GdlObject $donor
$name = 'Claude Icon.png'
Set-GdlField $new 'nameField' $name
Set-GdlField $new 'dataField' $bmp
Set-GdlField $new 'widthField' $bmp.Width
Set-GdlField $new 'heightField' $bmp.Height
Set-GdlField $new 'sizeField' ([int]$png.Length)
$resources.Add($new)
Report "appended; resource count $before -> $($resources.Count)"

# Bind it to a button's ICON slot (buttonImageField), not the background.
# A control's own buttonImageField is usually NULL - the icon lives on the
# STATE. So pick any button, and clone an image reference from wherever one
# exists in the project (clone-never-construct applies to references too).
$target = $null
foreach ($pg in @($p.Pages) + @($p.PopupPages)) {
    foreach ($c in $pg.Controls) { if ($c.GetType().Name -eq 'PBButton') { $target = $c; break } }
    if ($target) { break }
}
if (-not $target) { throw 'no PBButton in the project' }

$existing = Get-GdlField $target 'buttonImageField'
if (-not $existing) {
    foreach ($pg in @($p.Pages) + @($p.PopupPages)) {
        foreach ($c in $pg.Controls) {
            $v = Get-GdlField $c 'buttonImageField'
            if ($v) { $existing = $v; break }
            $sts = Get-GdlField $c 'statesField'
            if ($sts -and $sts.Count) {
                for ($k = 0; $k -lt $sts.Count; $k++) {
                    if ($null -eq $sts[$k]) { continue }
                    $v2 = Get-GdlField $sts[$k] 'buttonImageField'
                    if ($v2) { $existing = $v2; break }
                }
            }
            if ($existing) { break }
        }
        if ($existing) { break }
    }
}
if (-not $existing) { throw 'no PBResourceReferenceImage anywhere to clone' }
Report "target button '$($target.Name)'; cloning an image reference to '$($existing.ResourceName)'"

$ref = Copy-GdlObject $existing
Set-GdlField $ref 'resourceNameField' $name
Set-GdlField $target 'buttonImageField' $ref

# States carry their own icon slot; mirror it or the default state keeps the old one.
$states = Get-GdlField $target 'statesField'
if ($states -and $states.Count) {
    for ($i = 0; $i -lt $states.Count; $i++) {
        $st = $states[$i]
        if ($null -eq $st) { continue }
        $sref = Get-GdlField $st 'buttonImageField'
        if ($sref) {
            $c2 = Copy-GdlObject $sref
            Set-GdlField $c2 'resourceNameField' $name
            Set-GdlField $st 'buttonImageField' $c2
        }
    }
}
Report "bound '$name' to the button and its $($states.Count) state(s)"

$n = Save-GdlProject $p (Join-Path $Work 'testD_ProjectGCP')
Report "saved testD_ProjectGCP ($n bytes)"
