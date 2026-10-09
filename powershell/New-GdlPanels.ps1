<#
    Every panel of a canvas, built and verified. One command per room.

        python -m gdl.design translate <canvas dir> out\huddle
        powershell\New-GdlPanels.ps1 -Out out\huddle -Name Huddle

    `translate` writes one spec per panel the canvas lists, each naming its own
    seed (out\huddle\<model>\spec.json). This writes their one ID map -
    python -m gdl.idmap write-panels, every control's ID the same on every
    panel - then builds each panel with New-GdlPanel.ps1 on its own seed and
    verifies it against that map (tests\verify_idmap.py --panel):

        out\huddle\idmap\                  the map: a row per ID, a column per panel
        out\huddle\<model>\<Name>.gdl      each panel, built and verified

    Panels build one after another - each run opens GUI Designer, builds and
    closes it - so a running GUI Designer is closed first, as New-GdlPanel.ps1
    closes it. Allow two to four minutes a panel.

    -Models builds some of them (the map is still every panel's). -KeepGoing
    builds the rest after one fails. Exits 0 only if every panel built and
    verified, and prints a table either way.

    Then: python -m gdl.design compare <canvas dir> out\huddle out\huddle\signoff
#>
param(
    [Parameter(Mandatory)][string]$Out,
    [Parameter(Mandatory)][string]$Name,
    [string[]]$Models,
    [string]$Python = 'python',
    [switch]$KeepGoing
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
# A trailing backslash, which tab completion adds, escapes the closing quote
# Windows PowerShell 5.1 puts round an argument with a space in it.
$Out = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out).TrimEnd('\')
if (-not (Test-Path $Out)) { throw "not found: $Out - translate the canvas there first" }

# The canvas's own list, the panel it is drawn on first: each spec carries it.
# Only those: a folder another translate left is not this canvas's panel, and a
# listed panel with no spec is not one to skip.
$specs = Get-ChildItem -Path $Out -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'spec.json') }
if (-not $specs) { throw "no <model>\spec.json under $Out - translate the canvas there first" }
$first = Get-Content (Join-Path $specs[0].FullName 'spec.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$order = if ($first._panels) { @($first._panels) } else { @($specs.Name) }
$missing = @($order | Where-Object { $specs.Name -notcontains $_ })
if ($missing) { throw "no spec for $($missing -join ', ') under $Out, which the canvas lists - translate it there again" }
if ($Models) {
    $unknown = @($Models | Where-Object { $order -notcontains $_ })
    if ($unknown) { throw "no spec for $($unknown -join ', ') under $Out - it has $($order -join ', ')" }
    $order = @($order | Where-Object { $Models -contains $_ })
}

Push-Location $repo
try {
    $map = Join-Path $Out 'idmap'
    Write-Output "=== the ID map, every panel -> $map"
    & $Python -m gdl.idmap write-panels $Out $map
    if ($LASTEXITCODE -ne 0) { throw "the ID map did not check (exit $LASTEXITCODE)" }

    $results = @()
    foreach ($m in $order) {
        $dir = Join-Path $Out $m
        $spec = Join-Path $dir 'spec.json'
        $seed = (Get-Content $spec -Raw -Encoding UTF8 | ConvertFrom-Json)._seed
        $donor = Join-Path $repo $seed
        $built = Join-Path $dir "$Name.gdl"
        $work = Join-Path 'C:\gdlwork' "$Name-$m"
        $row = [pscustomobject]@{ Panel = $m; Seed = $seed; Built = 'no'; Verified = 'no'; IdMap = 'no' }
        Write-Output ''
        Write-Output "=== $m on $seed"
        # A child process per panel: New-GdlPanel throws on a failure, which in
        # this process would end every panel after it, and a child's exit code
        # is its own.
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'New-GdlPanel.ps1') `
            -Spec $spec -Donor $donor -Output $built -Work $work -Python $Python
        if ($LASTEXITCODE -eq 0) {
            $row.Built = 'yes'
            $row.Verified = 'yes'
            & $Python tests\verify_idmap.py $map $built --panel $m
            if ($LASTEXITCODE -eq 0) { $row.IdMap = 'yes' }
        } elseif (Test-Path $built) {
            $row.Built = 'yes'
        }
        $results += $row
        if ($row.IdMap -ne 'yes' -and -not $KeepGoing) { break }
    }
    Write-Output ''
    $results | Format-Table -AutoSize | Out-String -Width 200 | Write-Output
    $failed = @($results | Where-Object { $_.IdMap -ne 'yes' })
    if ($failed -or $results.Count -lt $order.Count) {
        Write-Output "NOT EVERY PANEL BUILT AND VERIFIED ($($results.Count - $failed.Count) of $($order.Count))"
        exit 1
    }
    Write-Output "EVERY PANEL BUILT AND VERIFIED -> $Out ($($order -join ', '))"
    exit 0
} finally {
    Pop-Location
}
