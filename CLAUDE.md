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

### Where to work

Three platforms now reproduce `tests/baseline.json` **exactly** — mean 2.19%,
median 1.65%, worst 7.68%, every page within 0.01%: macOS, a Claude Code Linux
cloud container (2026-09-07), and the Windows box natively (2026-09-08).

**If you are on the Windows box, work there.** The premise that "the Windows box
is the scarce resource", which justified batching plans into one trip, no longer
holds — a session there runs the Python half and drives GUI Designer in the same
place, so author → build → verify is one loop with nothing to carry.

Off Windows, everything except the PowerShell half still runs, and the table
below says what waits for a Windows trip.

| Runs in the cloud | Needs the Windows box |
|---|---|
| `gdl.container` / `data` / `nrbf` / `project` / `themes` / `fonts` | `powershell/*.ps1`, all eight |
| `gdl.compose`, `tests/score.py`, `tests/compare_snapshots.py` | File > Save and Build |
| `gdl.spec` check / render / plan / donors | `examples/add-page-and-popup.ps1` |
| `gdl.edit` check / plan | |
| `tests/test_spec.py` (72), `test_edit.py` (23), `test_fonts.py` (7) | |
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
   GUI Designer rasterizes, deduplicates and assigns on build. What you author
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
which self-asserts. A file that merely serializes proves nothing; the real test
is that GUI Designer opens *and builds* it, and that needs a Windows box.

A clean build is still not proof the result is *right* — Build silently
relocates controls that don't fit their page, and bakes captions into artwork.
Close the loop:

```bash
python tests/verify_built.py out/plan.json out/generated.gdl
```

It diffs the built `layout.json` against the plan that produced it and exits
non-zero on any authored control that moved or lost its caption.

## Driving GUI Designer

Scripted, not manual — `docs/from-scratch.md` §7 has the detail.

**Run Claude Code on the Windows box and this is all local.** A session there is
already interactive (`[Environment]::UserInteractive` is true, on session 1
with a real desktop), so nothing needs a VM, a scheduled task or a remote exec:

```powershell
Start-Process "C:\Program Files (x86)\Extron\GUI Designer\GUI Designer.exe" -ArgumentList '"C:\gdlwork\x.gdl"'
powershell\Send-GdlKeys.ps1 -Keys '^+b'      # File > Save and Build
```

and `System.Drawing`'s `CopyFromScreen` reads the screen back. Use `C:\gdlwork`
for build scratch — the repo lives on a mounted drive and GUI Designer is slow
against it.

Two gotchas:

- **`Get-Process` caches `MainWindowTitle`.** It reads `GUI Designer` until you
  call `.Refresh()`, and only then shows `GUI Designer - [TLP Pro 1035T:
  x.gdl*]`. Polling the title for the project name or the dirty marker without
  refreshing waits forever.
- The window title's trailing `*` is the build-finished signal. Save and Build
  clears it; a `Please wait while the project is being saved` overlay is up
  until then.

If you are instead driving a Parallels guest from macOS, the old route still
works: `prlctl exec "Windows 11" --current-user ...` (without `--current-user`
it runs as `nt authority\system` with `UserInteractive = False` and anything
that draws a form dies), the host is at `\\Mac\Home\...` since the `Z:` mapping
is per-interactive-session and invisible to `prlctl exec`, and `prlctl capture`
reads the screen.

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
  Extron assembly during serialization, the return value is intact, and it is
  not an error.
- Windows long paths: the longest tracked path is 118 characters, so cloning
  into a deep directory fails without `core.longpaths`.
- PowerShell execution policy is per-user; the documented entry points need
  `-ExecutionPolicy Bypass` on a machine that has not set it.
- `gdl/fonts/` must be extracted from **all six** fixtures — no single one
  embeds every face.
- **Arial is embedded. Extract it; never substitute it.** This used to read the
  other way, and the correction is worth knowing about because the wrong version
  cost real time. `extract()` matched `layout.json`'s declared size against the
  measured sfnt length *exactly*, and both Arial faces carry bytes past the far
  edge of their last table — 28 for Arial, 30 for Arial Black — so neither ever
  matched, and both were written off as system faces the format referenced
  without embedding. Genuine Monotype Arial 5.10 and Arial Black 5.06 are in
  every fixture and in all 44 of Extron's installed templates. Nothing needs
  Liberation Sans, and a `.gdl` renders identically on a host with no fonts
  installed at all. `tests/test_fonts.py` is the gate that was missing.

## Things deliberately not in git

- **Seven of the nine files in `gdl/fonts/`**, regenerated with
  `python -m gdl.fonts <file.gdl> gdl/fonts/`. Skip that and the harness does
  not degrade, it stops — `face()` raises `LookupError` on the first face it
  cannot resolve. The ignore is per file, not a class: Open Sans is Apache 2.0
  and is tracked with its license; Arial, Arial Black and Forma DJR Display are
  retail typefaces; the four Extron and Crestron icon fonts carry no license
  grant at all. `gdl/fonts/README.md` has the per-file detail.
  Note this keeps out a *convenient* copy, not the bytes — every face is
  embedded in the tracked `.gdl` fixtures and recoverable from them exactly. If
  the concern is distribution, `fixtures/` is the thing to look at.
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
  reports every unresolved donor and field. Color fidelity is the open gap.
  See `docs/from-scratch.md` §5b. **Group registration was never actually missing**;
  `Register-GdlPopupGroup` is complete. See `docs/from-scratch.md`, which also
  lists the six questions that need one session on a Windows box.
