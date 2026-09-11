# extron-gdl-toolkit

Read, render, edit and author Extron GUI Designer `.gdl` touch-panel projects
from code.

Verified against GUI Designer 1.27.0.9. Files written by this toolkit open in
the application, survive structural edits (adding and removing pages, popup
pages, popup page references and controls) and build successfully.

Not affiliated with Extron.

## Why

A `.gdl` is opaque: a ZIP with deliberately mangled signatures wrapping a .NET
`BinaryFormatter` graph. So you cannot diff two panel revisions, audit which
control drives which ID, or generate a panel from a spec instead of clicking it
together.

## What is here

| Path | |
|---|---|
| `gdl/` | Python: container, render model, font recovery, reference compositor |
| `gdl/nrbf.py`, `gdl/project.py` | pure-Python reader for the authoring model, no GUI Designer needed |
| `gdl/spec.py` | declarative panel spec: layout pass, ID allocation, preview render, build plan |
| `gdl/edit.py` | change vocabulary for an existing panel: rename, retarget, renumber, restyle |
| `gdl/themes.py` | Afterburn tokens, and palette extraction from any theme's template |
| `powershell/GdlProject.ps1` | authoring bridge: load, clone, edit, save a real project graph |
| `powershell/Apply-GdlPlan.ps1` | applies a build plan to a real project. `-WhatIf` dry-runs it |
| `powershell/Apply-GdlEdits.ps1` | applies an edit plan to a real project |
| `viewer/` | builds a single-file HTML browser for every page and popup |
| `tests/score.py` | scores the render against ground truth and fails on any regression |
| `tests/compare_snapshots.py` | the same comparison, printed per page |
| `tests/verify_built.py` | diffs a built `layout.json` against the plan that produced it |
| `examples/` | worked spec, edit set and authoring script, all of which run |
| `SKILL.md` | the repeatable procedure. Start here to build or modify a panel |
| `docs/gdl-format.md` | the format writeup. Read this first |
| `docs/from-scratch.md` | generating a panel from a spec, and what needs Windows |
| `docs/editing.md` | changing a panel that already exists |
| `docs/render-fidelity.md` | what GUI Designer actually draws, measured against its own renders |
| `docs/design-rules.md` | Extron's own design standards plus Afterburn tokens, encodable, with provenance |
| `fixtures/` | real `.gdl` files and 50 GUI Designer snapshot renders to test against |
| `seeds/` | fourteen themed seed projects to author from without client material (Git LFS) |
| `tests/audit_corpus.py` | re-tests the repo's documented beliefs against every project it can reach |
| `research/` | measured findings and unshipped render improvements, with their numbers and scripts |
| `workflows/` | the planned multi-agent bug hunt, not yet run |
| `archive/` | raw working state carried off the Windows box, kept as evidence (Git LFS) |
| `vendor/` | Extron's templates and icons, on disk but not pushed - see its README |
| `docs/ROADMAP.md` | what is left, in order, and who has to do it |

## Quick start

Run these from the repo root. The package is not pip-installable, so
`python -m gdl.*` needs the repo as the working directory.

Only the rendering side needs a dependency: `pip install -r requirements.txt`
(Pillow). Reading, editing and plan generation are stdlib-only, and none of
them need Windows.

Inspect a project:

```bash
python -m gdl.container extract "fixtures/gdl/<file>.gdl" out/
# no single fixture embeds every face - extract from all of them
for f in fixtures/gdl/*.gdl; do python -m gdl.fonts "$f" gdl/fonts/; done
```

Build the HTML viewer for a set of projects:

```bash
python -m gdl.data fixtures/gdl panel-data.json
python viewer/build_viewer.py viewer/template.html panel-data.json panel-atlas.html
```

Score the compositor against ground truth (needs Pillow):

```bash
# the snapshots belong to this fixture; pointing it at another silently
# scores unrelated pages
python tests/compare_snapshots.py "fixtures/gdl/Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl" fixtures/snapshots/Individual
```

`tests/score.py record` and `tests/score.py diff` do the same comparison and
exit non-zero on a regression, which is what a render change should be checked
against.

## Changing a panel that already exists

Write the change as JSON, resolve it against the real project, then apply it.
Four operations: `rename` captions, `retarget` to another panel model with
optional rescaling, `renumber` addressable IDs, and `restyle` a color remap.
Selectors are ANDed and match exactly or by regex.

```bash
python -m gdl.edit check examples/edits.json "fixtures/gdl/<file>.gdl"
python -m gdl.edit plan  examples/edits.json "fixtures/gdl/<file>.gdl" out/edits-plan.json
```

`check` resolves every selector against the real file, so a selector that
matches nothing is an error here rather than a silent no-op on Windows.

## Generating a panel from a spec

```bash
python -m gdl.spec check   examples/panel.json          # ids, off-canvas, sizes, resources
python -m gdl.spec render  examples/panel.json out/preview.png
python -m gdl.spec donors  examples/panel.json "fixtures/gdl/<donor>.gdl"
python -m gdl.spec plan    examples/panel.json out/plan.json
```

Look at the preview before paying for a Windows round trip. The compositor is
scored against GUI Designer's own output, so it is a real preview. `donors`
catches the two failures that otherwise cost a trip to the VM: a control type
the donor cannot supply, and a page or popup name the donor already uses.

## Applying a plan, which needs Windows

Editing the project graph needs 32-bit Windows PowerShell 5.1
(`C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`), because .NET
Framework still has `BinaryFormatter` and Extron's assemblies are x86. A 64-bit
host loads most of the assemblies and then fails on `GUI Designer.exe`.

```powershell
. .\powershell\GdlProject.ps1
Initialize-Gdl
$p = Open-GdlProject 'out\ProjectGCP'
Set-GdlField $p 'nameField' 'My Project'
$gid = Register-GdlPopupGroup $p 'My Popups'
Test-GdlPopupBinding $p 22          # assert all four binding sites agree
Save-GdlProject $p 'out\new_ProjectGCP'
```

or run the worked example, which does all of the above and self-checks:

```
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -File examples\add-page-and-popup.ps1 out\ProjectGCP out\new_ProjectGCP
```

then repack and open in GUI Designer:

```bash
python -m gdl.container pack "fixtures/gdl/<template>.gdl" out/new_ProjectGCP "My Project.gdl"
```

A clean build is not proof the result is right, because Build silently
relocates controls that do not fit their page and bakes captions into artwork.
`python tests/verify_built.py out/plan.json <built.gdl>` diffs the built
`layout.json` against the plan and exits non-zero on any control that moved or
lost its caption.

## The three things that will bite you

1. Clone, never construct. Constructors and property setters both need runtime
   services that are null outside the app, and a failed setter writes the
   backing field before it throws, so it looks like it worked.
2. Popup bindings live in four places, and every mismatch fails silently: the
   file opens and builds, the binding just reads "Unassigned".
   `Test-GdlPopupBinding` checks all four.
3. Build owns the artwork. Controls are authored with `TLPImageID = -1`, and
   GUI Designer rasterizes, deduplicates and assigns on build, so never
   hand-author PNGs. What you author instead is `borderFillColor` plus a named
   border resource (`"Afterburn - 10 Radius 2 Thick"`). Neither survives into
   `layout.json`, so read them from `ProjectGCP` via `gdl/project.py`.

`docs/gdl-format.md` has the full detail.

## Status

Reading, rendering, editing, generating, round-tripping and building all work
and are verified against 1.27.0.9.

A retarget of the whole Liberty Bank project from a TLP Pro 1035T to a TLP Pro
1535M came back 654 of 654 controls correct in the built file. A generated
panel went from `examples/panel.json` through the layout pass, ID allocation,
`Apply-GdlPlan.ps1` and `gdl.container pack` into GUI Designer, which built it
with 0 errors and 0 warnings. `docs/generated-built.png` is that page rendered
from its own built payload rather than from a preview.

Known gaps — `docs/ROADMAP.md` has the full list, in order:

- Nothing generated has been larger than three pages yet, against a 27-page
  client project; icons are not in the spec vocabulary; buttons get Off/On
  feedback but not multi-state (`Muted` / `Level 1..3`).
- A retarget builds correctly but matches Extron's own hand-authored layout at
  another size for only 22% of controls. Prefer a native-size seed.
- The Pillow compositor sits at a 2.19% mean and 1.65% median pixel difference
  across 27 pages, worst page 7.68%. What remains is a size-dependent vertical
  text residual. It can be fitted away, but the fit is degenerate, so the cause
  is still wanted. See `docs/render-fidelity.md`.
- Every text finding is validated against one typeface, because the scored
  fixture only ever draws Forma DJR Display.
- `referenceCountField` on a popup group. The semantics are unknown, and a
  plausible value causes no visible problem.

## Fonts

The renderer resolves faces from `gdl/fonts/` before falling back to the system
font path, so a project renders the same on a machine with nothing installed.
Open Sans is tracked because it is Apache 2.0 and says so in its own name
table. The other seven files are recovered from the fixtures with the command in
Quick start above, and `gdl/fonts/README.md` records where each one stands.

**Every face a project declares is embedded in it, Arial included** — genuine
Monotype Arial 5.10 and Arial Black 5.06, in each of the six fixtures. So the
harness needs no fonts installed on the host, and on a host that has Arial the
embedded copy is still the better one: it is what GUI Designer rasterized the
ground-truth snapshots with, where the system copy is whatever build the OS
shipped.

Missing faces fail loudly: `face()` raises `LookupError` rather than degrading
to a wrong score. The exception is a host with Arial installed, where a missing
embedded face silently resolves to the system Arial instead.

## Provenance

Reverse-engineered from project files, GUI Designer's own snapshot exports and
the installed assemblies. No Extron documentation was involved, so 1.27.0.9 is
the tested boundary. The `fixtures/` files are real Liberty Bank project files
kept as test data.
