# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A toolkit for reading, rendering and **authoring** Extron GUI Designer `.gdl`
touch-panel projects. It was reverse-engineered from project files, GUI
Designer's own snapshot exports, and the installed assemblies — **no Extron
documentation exists for any of this**. Version 1.27.0.9 is the tested
boundary.

`SKILL.md` is the repeatable procedure for building or modifying a panel — the
workflows, the verification gates, and the traps. Start there for panel work.
`docs/from-scratch.md` covers generating one; `docs/editing.md` covers changing
one that exists.

Read `docs/gdl-format.md` before changing anything that touches the format. It
is the accumulated findings, and most of them were expensive to discover.
`docs/design-rules.md` is Extron's own design standards reduced to encodable
rules, with what is documented kept strictly separate from what we extrapolated —
never quote an extrapolated number to a client as an Extron requirement.

**The canvas is not 1280x800.** GUI Designer supports eight resolutions across 63
panel models; the fixtures are all one model. Assume nothing about panel geometry
from them.

## Environment

| Task | Needs |
|---|---|
| Reading a `.gdl`, incl. the authoring model | Python 3 only |
| Rendering / the snapshot harness | Pillow (`pip install -r requirements.txt`) |
| **Writing** a `.gdl` | 32-bit Windows PowerShell 5.1 **and** an install of GUI Designer |
| Proving GUI Designer accepts it | the same, driven through its UI — see `docs/from-scratch.md` §7 |

Writing is the constrained one, for two independent reasons:

- `BinaryFormatter` was removed from modern .NET, so it needs .NET Framework —
  `C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`.
- Extron's assemblies are x86, so a 64-bit host fails with "incorrect format".

A 64-bit PowerShell will load 34 of 39 assemblies and then fail on
`GUI Designer.exe` specifically. If you see that, you are in the wrong host.

### Working in a cloud session (Linux, no Windows)

Measured 2026-09-07 in a Claude Code cloud container. Everything except the
PowerShell half runs, and the render harness reproduces `tests/baseline.json`
**exactly** — mean 2.19%, median 1.65%, worst 7.68%, every page within 0.01%.
Treat the cloud as the normal place to work and the Windows trip as one batched
step at the end, not a per-iteration cost.

| Runs in the cloud | Needs the Windows box |
|---|---|
| `gdl.container` / `data` / `nrbf` / `project` / `themes` / `fonts` | `powershell/*.ps1`, all eight |
| `gdl.compose`, `tests/score.py`, `tests/compare_snapshots.py` | File > Save and Build |
| `gdl.spec` check / render / plan / donors | driving the VM — `prlctl` is host-side |
| `gdl.edit` check / plan | `examples/add-page-and-popup.ps1` |
| `tests/test_spec.py` (72 tests), `tests/test_edit.py` (23) | |
| `tests/verify_built.py`, once the built file is carried back | |

Setup is two commands:

```bash
pip install -r requirements.txt
for f in fixtures/gdl/*.gdl; do python -m gdl.fonts "$f" gdl/fonts/; done
```

Only two files need to cross the boundary: `out/plan.json` over, the built
`.gdl` back. Nothing in the repo is blocked on Windows for *reading* a project,
previewing a design, or scoring a render change.

Before working here, note that `fixtures/` is real client material — see
*Working on the fixtures* below. A cloud session clones it into a managed
container, and anything pushed goes to GitHub.

## Three things that will waste your time if you don't know them

1. **Clone, never construct.** `PBPage(PBProject)` and friends throw
   `NullReferenceException` outside the running app. So do the property
   setters — and a failed setter **writes the backing field before it throws**,
   so it looks like it worked. Always `Copy-GdlObject` an existing object and
   `Set-GdlField` its backing fields.

2. **Popup bindings live in four places and every mismatch fails silently.**
   The file opens, it builds, the binding just reads "Unassigned" in the UI.
   Call `Test-GdlPopupBinding` rather than trusting your writes.

3. **Build owns the artwork.** Controls are authored with `TLPImageID = -1`;
   GUI Designer rasterises, deduplicates and assigns on build. What you author
   instead is `borderFillColor` plus a **named** border resource
   (`"Afterburn - 10 Radius 2 Thick"`). Neither survives into `layout.json` —
   read them from `ProjectGCP` via `gdl/project.py`.

## Verifying a change

There is ground truth, so use it rather than eyeballing:

```bash
python tests/compare_snapshots.py fixtures/gdl/<file>.gdl fixtures/snapshots/Individual
```

Current baseline: **mean 2.19%, median 1.65%, worst 7.68%** differing pixels
across 27 pages.

A render change must report its before and after across **all** pages —
several plausible-looking fixes improve one page and regress twenty.
`docs/render-fidelity.md` records which ones, so you don't rediscover them.
Don't do that comparison by eye; `tests/score.py` does it properly and exits
non-zero on any regression:

```bash
python tests/score.py record fixtures/gdl/<file>.gdl fixtures/snapshots/Individual -o /tmp/after.json
python tests/score.py diff tests/baseline.json /tmp/after.json
```

`tests/baseline.json` is the currently shipped state; refresh it when a render
change lands.

For authoring changes, the end-to-end check is `examples/add-page-and-popup.ps1`,
which self-asserts. A file that merely serialises proves nothing; the real test
is that GUI Designer opens *and builds* it, and that needs a Windows box.

A clean build is still not proof the result is *right* — Build silently
relocates controls that don't fit their page, and bakes captions into artwork.
Close the loop:

```bash
python tests/verify_built.py out/plan.json out/generated.gdl
```

It diffs the built `layout.json` against the plan that produced it and exits
non-zero on any authored control that moved or lost its caption.

## Driving the Windows VM from macOS

This is scripted, not manual — `docs/from-scratch.md` §7 has the detail. The two
things that cost time to discover:

- `prlctl exec` runs as `nt authority\system` with `UserInteractive = False`, so
  anything that draws a form dies. Add **`--current-user`** and it runs as the
  logged-on user with a desktop.
- The host is at `\\Mac\Home\...` inside the guest. The `Z:` drive mapping is
  per-interactive-session and is **not** visible to `prlctl exec`.

`prlctl capture "Windows 11" --file x.png` reads the screen back, and
`powershell/Send-GdlKeys.ps1` drives GUI Designer's menus.

**`Project > Verify` (Ctrl+B) is not a build.** It says "Build Complete - 0
errors" and produces no payload; saving after it drops the payload entirely.
The real build is **File > Save and Build (Ctrl+Shift+B)**.

## Conventions

- Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`).
- Python: stdlib-only outside `gdl/compose.py`. Keep it that way — reading a
  `.gdl` on a machine with nothing installed is a feature.
- Comments explain *why*, particularly where the code encodes a
  reverse-engineered rule that looks arbitrary. Those comments are the only
  record that a rule was measured rather than guessed.
- Don't reformat `gdl/nrbf.py` into a house style; it is a compact MS-NRBF
  reader and its terseness is deliberate.

## Environment traps that cost time

- **Do not write backslash escapes through a bash heredoc.** Backslash-v and
  backslash-a get interpreted before Python sees them, leaving literal 0x0B and
  0x07 bytes in the file. This corrupted a documented command in README.md, and
  then corrupted this very warning on the first attempt to write it. Use the
  Write/Edit tools for any content containing backslashes.
- `Save-GdlProject` prints a bare `The system cannot find the file specified.
  (Exception from HRESULT: 0x80070002)` on every save. It comes from inside an
  Extron assembly during serialisation, the return value is intact, and it is
  not an error.
- Windows long paths: the longest tracked path is 118 characters, so cloning
  into a deep directory fails without `core.longpaths`.
- PowerShell execution policy is per-user; the documented entry points need
  `-ExecutionPolicy Bypass` on a machine that has not set it.
- `gdl/fonts/` must be extracted from **all six** fixtures — no single one
  embeds every face.
- **There is no Arial on Linux, and `face()` raises rather than degrading.**
  Arial and Arial Black are system faces, not embedded ones, so on a cloud box
  they resolve nowhere and the render dies with `LookupError`. The scored `_alt`
  fixture never draws Arial — it is Forma DJR Display throughout, so the 2.19%
  baseline reproduces with no Arial present at all — but the `TLP1035-1.1.0`
  fixture does, and hard-fails. Substituting metric-compatible Liberation Sans
  (copy `LiberationSans-*.ttf` over `arial.ttf` / `arialbd.ttf` / `ariali.ttf` /
  `arialbi.ttf` / `ariblk.ttf` in `gdl/fonts/`) gets it to render, but at 5.88%
  mean and 23.51% worst against ground truth. That is good enough to look at and
  **not** good enough to score or to record a baseline from. If you do it, know
  that you have put a file named `arial.ttf` on disk that is not Arial.

## Things deliberately not in git

- `gdl/fonts/` — commercial font binaries, regenerated with
  `python -m gdl.fonts <file.gdl> gdl/fonts/`. Skip it and text renders in
  fallback Arial, which quietly worsens the harness score.
- `out/`, `__pycache__/`, built viewer HTML.

## Working on the fixtures

`fixtures/` holds **real client project files** (Liberty Bank, job J26450039)
and 50 GUI Designer snapshot renders. They are test data — treat them as
read-only, and think before adding a remote or sharing the repo onward.

## Terminology

The addressable number on a control is its **ID** (`userIdField`). Extron calls
it that; it is not a "port" and not a Crestron-style "join". Note the collision:
controls also carry an `ID` field (`idField`) that is only a per-page editor
handle and means nothing to a programmer.

## Known gaps

- `referenceCountField` on a popup group: semantics unknown. A plausible value
  causes no visible problem.
- A size-dependent vertical text residual. Fitting an ascent and
  line-height multiplier reaches 1.72% mean, but the optimum is degenerate, so
  the cause is wanted rather than the fit. See `docs/render-fidelity.md`
  finding 7.
- Every text finding is validated against **one** typeface: the scored fixture
  only ever draws Forma DJR Display.
- Editing an existing panel: `gdl/edit.py` + `powershell/Apply-GdlEdits.ps1`.
  Rename, retarget, renumber and restyle, all **verified end to end** against
  GUI Designer 1.27.0.9 - including a scaled retarget of the whole Liberty Bank
  project from a TLP Pro 1035T to a TLP Pro 1535M, 654/654 controls correct in
  the built file.
- Generating a panel from a spec: `gdl/spec.py` has the layout pass, control ID
  allocation, a preview render and a build-plan emitter, all tested here.
  `powershell/Apply-GdlPlan.ps1` applies a plan to a real project — **verified
  end to end**: the example spec was generated, applied, packed, and built by
  GUI Designer 1.27.0.9 with 0 errors. Use `-WhatIf` first; it dry-runs and
  reports every unresolved donor and field. Colour fidelity is the open gap.
  See `docs/from-scratch.md` §5b. **Group registration was never actually missing**;
  `Register-GdlPopupGroup` is complete. See `docs/from-scratch.md`, which also
  lists the six questions that need one session on a Windows box.
