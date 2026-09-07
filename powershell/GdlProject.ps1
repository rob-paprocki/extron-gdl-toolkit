<#
    Authoring bridge for Extron GUI Designer project graphs.

    MUST be run under 32-bit Windows PowerShell 5.1:
      C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe

    .NET Framework still has BinaryFormatter (removed in modern .NET), and
    Extron's assemblies are x86 so a 64-bit host throws "incorrect format".

    Dot-source it:
      . .\GdlProject.ps1
      Initialize-Gdl
      $p = Open-GdlProject 'out\ProjectGCP'
      Set-GdlField $p 'nameField' 'My Project'
      Save-GdlProject $p 'out\new_ProjectGCP'
#>

$script:GdlAssemblies = @{}
$script:GdlFormatter = $null

function Initialize-Gdl {
    <#  Preload every GUI Designer assembly, then resolve from what is already
        loaded. Calling LoadFrom inside the resolve handler recurses until the
        stack overflows, so the handler must only ever do a lookup. #>
    param([string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer')

    if (-not (Test-Path $InstallDir)) { throw "GUI Designer not found at $InstallDir" }
    $files = @(Get-ChildItem -Path "$InstallDir\*" -Include *.dll -ErrorAction SilentlyContinue)
    $exe = Join-Path $InstallDir 'GUI Designer.exe'
    if (Test-Path $exe) { $files += Get-Item $exe }

    foreach ($f in $files) {
        try {
            $a = [System.Reflection.Assembly]::LoadFrom($f.FullName)
            $script:GdlAssemblies[$a.GetName().Name] = $a
        } catch { }   # a few native/mixed-mode DLLs never load; none are needed
    }
    if (-not $script:GdlAssemblies.ContainsKey('GUI Designer')) {
        throw 'Could not load "GUI Designer.exe" — are you running 32-bit PowerShell 5.1?'
    }
    [AppDomain]::CurrentDomain.add_AssemblyResolve([System.ResolveEventHandler] {
        param($sender, $e)
        $n = $e.Name.Split(',')[0]
        if ($script:GdlAssemblies.ContainsKey($n)) { return $script:GdlAssemblies[$n] }
        return $null
    })
    $script:GdlFormatter =
        New-Object System.Runtime.Serialization.Formatters.Binary.BinaryFormatter
    Write-Output "loaded $($script:GdlAssemblies.Count) assemblies"
}

function Open-GdlProject {
    param([Parameter(Mandatory)][string]$Path)
    $fs = [System.IO.File]::OpenRead($Path)
    try { $script:GdlFormatter.Deserialize($fs) } finally { $fs.Close() }
}

function Save-GdlProject {
    param([Parameter(Mandatory)]$Project, [Parameter(Mandatory)][string]$Path)
    $ms = New-Object System.IO.MemoryStream
    $script:GdlFormatter.Serialize($ms, $Project)
    [System.IO.File]::WriteAllBytes($Path, $ms.ToArray())
    $ms.Length
}

function Copy-GdlObject {
    <#  Deep clone through BinaryFormatter. Safe because ParentProject, Site,
        DesignView and PBSystem are [NonSerialized] — the stored graph is a
        pure data tree, so an element clones without dragging the project. #>
    param([Parameter(Mandatory)]$Object)
    $ms = New-Object System.IO.MemoryStream
    $script:GdlFormatter.Serialize($ms, $Object)
    $ms.Position = 0
    $script:GdlFormatter.Deserialize($ms)
}

function Set-GdlField {
    <#  Write the serialized backing field directly.

        The public property setters fire change notification into runtime
        services that are null outside the app: they write the backing field
        and THEN throw, so a failed set looks like it succeeded. Always go
        through the field. #>
    param([Parameter(Mandatory)]$Object, [Parameter(Mandatory)][string]$Field, $Value)
    $t = $Object.GetType()
    while ($t -and $t.FullName -ne 'System.Object') {
        $f = $t.GetField($Field, 'Instance,Public,NonPublic,DeclaredOnly')
        if ($f) { $f.SetValue($Object, $Value); return }
        $t = $t.BaseType
    }
    throw "no serialized field '$Field' on $($Object.GetType().Name)"
}

function Get-GdlField {
    # NOTE the comma: PowerShell unrolls a single-element List<T> on return.
    param([Parameter(Mandatory)]$Object, [Parameter(Mandatory)][string]$Field)
    $t = $Object.GetType()
    while ($t -and $t.FullName -ne 'System.Object') {
        $f = $t.GetField($Field, 'Instance,Public,NonPublic,DeclaredOnly')
        if ($f) { return , $f.GetValue($Object) }
        $t = $t.BaseType
    }
    return $null
}

function Get-GdlNextPageId {
    param([Parameter(Mandatory)]$Project)
    $ids = @()
    foreach ($q in $Project.Pages) { $ids += [uint64]$q.ID }
    foreach ($q in $Project.PopupPages) { $ids += [uint64]$q.ID }
    [uint64](($ids | Where-Object { $_ -ne 65535 } | Measure-Object -Maximum).Maximum) + 1
}

function Register-GdlPopupGroup {
    <#  Create a popup page group in the project registry. Without this, any
        popup or reference pointing at the group id shows as "Unassigned". #>
    param([Parameter(Mandatory)]$Project, [Parameter(Mandatory)][string]$Name)
    $groups = Get-GdlField $Project 'popupPageGroupsField'
    $id = [uint16](($groups | ForEach-Object { [int]$_.ID } | Measure-Object -Maximum).Maximum + 1)
    $g = Copy-GdlObject $groups[0]
    Set-GdlField $g 'nameField' $Name
    Set-GdlField $g 'idField' $id
    Set-GdlField $g 'referenceCountField' 2
    Set-GdlField $g 'indexField' 0
    $groups.Add($g)
    $id
}

function Test-GdlPopupBinding {
    <#  Verify all four places a popup binding lives actually agree. Each of
        them fails silently on its own, so assert rather than trust. #>
    param([Parameter(Mandatory)]$Project, [Parameter(Mandatory)][uint64]$PopupId)

    $popup = $Project.PopupPages | Where-Object { [uint64]$_.ID -eq $PopupId } | Select-Object -First 1
    if (-not $popup) { return @{ ok = $false; problems = @("no popup $PopupId") } }
    $problems = @()
    $grp = [int]$popup.GroupID

    if ($popup.Modal -and $grp -ne 0) { $problems += 'modal popup should not be grouped' }
    if (-not $popup.Modal -and $grp -eq 0) { $problems += 'standard popup has no group' }

    if ($grp -ne 0) {
        $reg = $Project.PopupPageGroups | Where-Object { [int]$_.ID -eq $grp }
        if (-not $reg) { $problems += "group $grp is not in the project registry" }
        elseif ((Get-GdlField $popup 'groupNameField') -ne $reg.Name) {
            $problems += "popup groupNameField does not match registry name '$($reg.Name)'"
        }
    }
    $refs = @()
    foreach ($pg in @($Project.Pages) + @($Project.PopupPages)) {
        foreach ($c in $pg.Controls) {
            if ($c.GetType().Name -ne 'PBPopupPageReference') { continue }
            $id = $c.PopupPageID
            if (([uint64]$id.PopupID -eq $PopupId) -or ($grp -ne 0 -and [int]$id.GroupID -eq $grp)) {
                $refs += @{ page = [uint64]$pg.ID; obj = [uint64]$c.ID }
            }
        }
    }
    if (-not $refs) { $problems += 'no reference control points at this popup' }
    if (-not (Get-GdlField $popup 'hasReferencesField')) { $problems += 'hasReferencesField is false' }

    $back = Get-GdlField $popup 'popupReferencesField'
    foreach ($r in $refs) {
        $hit = $back | Where-Object { [uint64]$_.PageID -eq $r.page -and [uint64]$_.ObjectID -eq $r.obj }
        if (-not $hit) { $problems += "no back-reference for page $($r.page) object $($r.obj)" }
    }
    @{ ok = ($problems.Count -eq 0); problems = $problems; references = $refs.Count }
}
