# extron-gdl-toolkit

Read, render and **author** Extron GUI Designer `.gdl` touch-panel projects
from code.

Verified against GUI Designer **1.27.0.9**: files written by this toolkit open
in the application, survive structural edits — adding and removing pages, popup
pages, popup page references and controls — and build successfully.

## Why

A `.gdl` is opaque: a ZIP with deliberately mangled signatures wrapping a .NET
`BinaryFormatter` graph. That makes ordinary things hard — diffing two panel
revisions, auditing which control drives which ID, or generating a panel from a
spec instead of clicking it together. This toolkit opens the format up.

## What is here

| Path | |
|---|---|
| `gdl/` | Python: container, render model, font recovery, reference compositor |
| `gdl/nrbf.py`, `gdl/project.py` | pure-Python reader for the authoring model — no GUI Designer needed |
| `powershell/GdlProject.ps1` | authoring bridge — load, clone, edit, save a real project graph |
| `viewer/` | builds a single-file HTML browser for every page and popup |
| `tests/compare_snapshots.py` | scores our render against GUI Designer's own snapshot exports |
| `examples/` | a worked authoring script that opens and builds in GUI Designer |
| `docs/gdl-format.md` | **the format writeup — read this first** |
| `docs/render-fidelity.md` | what GUI Designer actually draws, measured against its own renders |
| `fixtures/` | real `.gdl` files and 50 GUI Designer snapshot renders to test against |
| `research/` | measured but unshipped render improvements, with their numbers |

## Quick start

Run these from the repo root — the package is not pip-installable, so
`python -m gdl.*` needs the repo as the working directory.

Only the rendering side needs a dependency: `pip install -r requirements.txt`
(Pillow). Reading and authoring are stdlib-only.

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

Edit a project graph — **32-bit Windows PowerShell 5.1 only**
(`C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`; .NET Framework
still has `BinaryFormatter`, and Extron's assemblies are x86):

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

## The three things that will bite you

1. **Clone, never construct.** Constructors and property setters both need
   runtime services that are null outside the app — and a failed setter writes
   the backing field before it throws, so it looks like it worked.
2. **Popup bindings live in four places** and every mismatch fails *silently*:
   the file opens and builds, the binding just reads "Unassigned".
   `Test-GdlPopupBinding` checks all four.
3. **Build owns the artwork.** Controls are authored with `TLPImageID = -1`;
   GUI Designer rasterises, deduplicates and assigns on build. Never hand-author
   PNGs. What you *do* author is `borderFillColor` plus a named border resource
   (`"Afterburn - 10 Radius 2 Thick"`) — and neither survives into
   `layout.json`, so read them from `ProjectGCP` via `gdl/project.py`.

`docs/gdl-format.md` has the full detail.

## Status

Working and verified: reading, rendering, structural authoring, round-tripping,
building.

Known gaps:

- `referenceCountField` on a popup group — semantics unknown, a plausible value
  causes no visible problem.
- The Pillow compositor sits at a **2.19% mean / 1.65% median** pixel
  difference across 27 pages, worst page 7.68%. What remains is a
  size-dependent vertical text residual; it can be fitted away but the fit is
  degenerate, so the cause is still wanted. See `docs/render-fidelity.md`.
- Generating a panel from a spec, rather than by cloning an existing one, is
  not built yet.

## Provenance

Reverse-engineered from project files, GUI Designer's own snapshot exports, and
the installed assemblies. No Extron documentation was involved, so 1.27.0.9 is
the tested boundary. The `fixtures/` files are real Liberty Bank project files
kept as test data.
