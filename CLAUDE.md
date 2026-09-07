# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A toolkit for reading, rendering and **authoring** Extron GUI Designer `.gdl`
touch-panel projects. It was reverse-engineered from project files, GUI
Designer's own snapshot exports, and the installed assemblies — **no Extron
documentation exists for any of this**. Version 1.27.0.9 is the tested
boundary.

Read `docs/gdl-format.md` before changing anything that touches the format. It
is the accumulated findings, and most of them were expensive to discover.

## Environment

| Task | Needs |
|---|---|
| Reading a `.gdl`, incl. the authoring model | Python 3 only |
| Rendering / the snapshot harness | Pillow (`pip install -r requirements.txt`) |
| **Writing** a `.gdl` | 32-bit Windows PowerShell 5.1 **and** an install of GUI Designer |

Writing is the constrained one, for two independent reasons:

- `BinaryFormatter` was removed from modern .NET, so it needs .NET Framework —
  `C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`.
- Extron's assemblies are x86, so a 64-bit host fails with "incorrect format".

A 64-bit PowerShell will load 34 of 39 assemblies and then fail on
`GUI Designer.exe` specifically. If you see that, you are in the wrong host.

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
is that GUI Designer opens *and builds* it, and that needs a human.

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
- Generating a panel from a spec, rather than by cloning an existing one, is
  not built yet. The parts exist; the missing pieces are ID allocation, group
  registration and a layout pass.
