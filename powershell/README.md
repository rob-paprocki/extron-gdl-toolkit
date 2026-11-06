# powershell/

The Windows half: scripts that write and build `.gdl` files through GUI
Designer's own assemblies and windows. Everything here needs Windows and GUI
Designer 1.28.0.7, and whatever loads the assemblies needs 32-bit Windows
PowerShell 5.1 (`C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`).
`CLAUDE.md` *Environment* says why. Where no execution policy is set, run them
with `-ExecutionPolicy Bypass`.

## Run these

| script | does |
|---|---|
| `New-GdlPanel.ps1` | a spec to a built, verified panel, with nobody touching GUI Designer: plan, apply, pack, Save and Build, then verify. Exits 0 only if verification passed |
| `New-GdlPanels.ps1` | every panel of a canvas built on its own seed, each verified against one ID map |
| `New-GdlSeed.ps1` | a seed for any panel and theme, made through GUI Designer's Project Create Wizard. `-List` and `-ListThemes` show what the wizard offers |
| `New-GdlTurnedSeed.ps1` | a seed for a panel turned where its theme draws no template that way up: its own seed turned, built and verified |
| `Apply-GdlPlan.ps1` | applies a build plan to a real project; `-WhatIf` dry-runs it. `New-GdlPanel.ps1` calls it for you |
| `Apply-GdlEdits.ps1` | applies an edit plan to a real project |
| `Export-GdlSnapshots.ps1` | GUI Designer's own snapshot of every page and popup of a built project, exported with nobody touching it: the render baseline's ground truth |
| `Get-GdlPlatforms.ps1` | every panel GUI Designer builds for, from its own assemblies: resolution, DPI, part number and the resolutions it runs at |

## Libraries the scripts load

| script | does |
|---|---|
| `GdlProject.ps1` | the authoring bridge, dot-sourced: load, clone, edit and save a real project graph (`Open-GdlProject`, `Copy-GdlObject`, `Set-GdlField`, `Test-GdlPopupBinding` and more) |
| `GdlApply.ps1` | helpers both appliers share |
| `GdlTiming.ps1` | what the host spent while a build ran: process, disk and scanner counters, for `tools/Run-BuildTiming.ps1` |
| `GdlBlocker.ps1` | spots GUI Designer dialogs that wait for a person, such as the Extron Insider login, so a build wait names them instead of timing out. Needs Windows only |
| `Invoke-GdlMenu.ps1`, `Send-GdlKeys.ps1`, `Wait-GdlBuild.ps1` | start Save and Build and wait for it to finish. `docs/from-scratch.md` §7 explains why the obvious ways are wrong |

## Probes

`New-FormatProbes.ps1` and `New-ImageProbe.ps1` each answered one format
question and are kept for re-running. `Get-PanelModels.ps1` read the panel
list off the wizard by hand; `New-GdlSeed.ps1 -List` and
`Get-GdlPlatforms.ps1` now report it.
