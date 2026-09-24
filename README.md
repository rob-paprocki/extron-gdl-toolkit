# extron-gdl-toolkit

Read, render, edit and author Extron GUI Designer `.gdl` touch-panel projects
from code.

Verified against GUI Designer 1.28.0.7. Files written by this toolkit open in
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
| `gdl/edit.py` | change vocabulary for an existing panel: rename, restyle, states, retarget, renumber |
| `gdl/idmap.py` | the ID map a programmer works from: every addressable control, where it is, what it does |
| `gdl/designsys/` | an Extron template as a Claude Design design system: its profile, and the components every template shares |
| `gdl/design.py` | turns a Claude Design canvas into a spec, laying it out in headless Chrome |
| `gdl/themes.py` | Afterburn tokens, and palette extraction from any theme's template |
| `powershell/GdlProject.ps1` | authoring bridge: load, clone, edit, save a real project graph |
| `powershell/Apply-GdlPlan.ps1` | applies a build plan to a real project. `-WhatIf` dry-runs it |
| `powershell/Apply-GdlEdits.ps1` | applies an edit plan to a real project |
| `viewer/` | builds a single-file HTML browser for every page and popup |
| `tests/score.py` | scores the render against ground truth and fails on any regression |
| `tests/compare_snapshots.py` | the same comparison, printed per page |
| `tests/verify_built.py` | diffs a built `layout.json` against the plan that produced it |
| `tests/verify_idmap.py` | checks an ID map's page names and control IDs against the built panel |
| `examples/` | worked spec, edit set and authoring script, all of which run |
| `SKILL.md` | the repeatable procedure. Start here to build or modify a panel |
| `docs/gdl-format.md` | the format writeup. Read this first |
| `docs/from-scratch.md` | generating a panel from a spec, and driving GUI Designer from a script |
| `docs/editing.md` | changing a panel that already exists |
| `docs/claude-design.md` | designing a panel in Claude Design and building it from the canvas |
| `docs/render-fidelity.md` | what GUI Designer actually draws, measured against its own renders |
| `docs/design-rules.md` | Extron's own design standards plus Afterburn tokens, encodable, with provenance |
| `fixtures/` | real `.gdl` files and 50 GUI Designer snapshot renders to test against |
| `seeds/` | themed seed projects to author from without client material (Git LFS); its README lists them |
| `tests/audit_corpus.py` | re-tests the repo's documented beliefs against every project it can reach |
| `research/` | measured findings and unshipped render improvements, with their numbers and scripts |
| `workflows/` | the planned multi-agent bug hunt, not yet run |
| `archive/` | raw working state carried off an earlier build host, kept as evidence (Git LFS) |
| `vendor/` | Extron's templates and icons, on disk but not pushed - see its README |
| `docs/ROADMAP.md` | what is left, in order, and who has to do it |
| `docs/history.md` | retired setups and corrections — why a claim changed. Not needed to use the toolkit |

## Setup

Verified with:

| Install | Version | Needed for |
|---|---|---|
| Python | 3.11.9 | everything; reading, editing and plan generation are stdlib-only |
| Pillow, pytest | 12.3.0, 9.1.1 | rendering and the test suite |
| Git LFS | 3.7.1 | `seeds/` and `archive/` |
| Extron GUI Designer | **1.28.0.7**, the tested boundary | writing and building a `.gdl` — `CLAUDE.md` *Environment* says what else that needs |

Then, from the repo root:

1. `git clone`, then `git lfs pull`. Without it `seeds/` holds LFS pointer
   files, and the seed tests skip rather than fail.
2. `pip install -r requirements.txt pytest`
3. Extract the fonts from every fixture — no single one embeds every face:
   `for f in fixtures/gdl/*.gdl; do python -m gdl.fonts "$f" gdl/fonts/; done`
4. With GUI Designer installed, repopulate `vendor/`; `vendor/README.md` has
   the commands.
5. `python -m pytest`, then `python tests/audit_corpus.py`. Any FAIL the audit
   reports should already be an open item in `docs/ROADMAP.md`.

Three things trip a fresh Windows machine: cloning into a deep directory needs
`git config --global core.longpaths true`; the PowerShell entry points need
`-ExecutionPolicy Bypass` where no policy is set; and a small fixed pagefile
caps the commit limit well below RAM, so let the OS manage it before running
anything that fans out agents.

Optionally, `archive/claude/memory/` holds Claude Code's accumulated context for
this project. It belongs in the per-project memory directory, whose name Claude
Code derives from the repo's path.

## Quick start

Run these from the repo root. The package is not pip-installable, so
`python -m gdl.*` needs the repo as the working directory.

Inspect a project:

```bash
python -m gdl.container extract "fixtures/gdl/<file>.gdl" out/
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
Five operations: `rename` captions and `restyle` colors, both state by state;
`states` to add, remove or rename a button's states; `retarget` to another
panel model with optional rescaling; and `renumber` addressable IDs. Selectors
are ANDed and match exactly or by regex. `docs/editing.md` has the detail.

```bash
python -m gdl.edit check examples/edits.json "fixtures/gdl/<file>.gdl"
python -m gdl.edit plan  examples/edits.json "fixtures/gdl/<file>.gdl" out/edits-plan.json
```

`check` resolves every selector against the real file, so a selector that
matches nothing is an error here rather than a silent no-op at apply time.

## Generating a panel from a spec

```bash
python -m gdl.spec check   examples/panel.json          # ids, off-canvas, sizes, resources
python -m gdl.spec render  examples/panel.json out/preview.png
python -m gdl.spec donors  examples/panel.json "fixtures/gdl/<donor>.gdl"
python -m gdl.spec plan    examples/panel.json out/plan.json

python -m gdl.idmap check examples/huddle-functions.json   # what the controls do
python -m gdl.idmap write examples/huddle-functions.json out/idmap
```

Look at the preview before building. The compositor is scored against GUI
Designer's own output, so it is a real preview. `donors` finds in a second what
would otherwise surface only in a build — a control type the donor cannot
supply, a page or popup name it already uses, a border resource or font it
lacks. `SKILL.md` has the full procedure, and where GUI Designer is installed
`powershell\New-GdlPanel.ps1` runs all of it, build and verification included.
A spec can also say what its controls do; `gdl.idmap` checks the page flips and
writes the programmer's ID map from the same file (`docs/idmap.md`).

## Applying a plan, which needs GUI Designer

Editing the project graph needs 32-bit Windows PowerShell 5.1 and an install of
GUI Designer; `CLAUDE.md` *Environment* says why.

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

## Before writing to a project

Read `docs/gdl-format.md` — at least §2 *What Build actually does*, §4 *Clone,
never construct* and §6 *Popup bindings live in four places*. Getting any of
them wrong fails silently: the file opens, builds, and is wrong.

## Status

Reading, rendering, editing, generating, round-tripping and building all work
and are verified against 1.28.0.7.

A retarget of the whole Liberty Bank project from a TLP Pro 1035T to a TLP Pro
1535M came back 654 of 654 controls correct in the built file. A generated
panel went from `examples/panel.json` through the layout pass, ID allocation,
`Apply-GdlPlan.ps1` and `gdl.container pack` into GUI Designer, which built it
with 0 errors and 0 warnings. `docs/generated-built.png` is that page rendered
from its own built payload rather than from a preview.

The compositor is scored against GUI Designer's own snapshot exports:
`tests/baseline.json` holds the current numbers, and `docs/render-fidelity.md`
what the residual is. Known gaps, and everything left to do, are in
`docs/ROADMAP.md`.

## Fonts

The renderer resolves faces from `gdl/fonts/` before the system font path, and
fails loudly on a face it cannot resolve. `gdl/fonts/README.md` has which faces
are tracked and why, how the rest are recovered from the fixtures, and which
projects declare faces they do not embed.

## Provenance

Reverse-engineered from project files, GUI Designer's own snapshot exports and
the installed assemblies. No Extron documentation was involved, so 1.28.0.7 is
the tested boundary. The `fixtures/` files are real Liberty Bank project files
kept as test data.
