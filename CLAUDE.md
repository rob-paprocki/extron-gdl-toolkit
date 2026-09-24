# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A toolkit for reading, rendering and **authoring** Extron GUI Designer `.gdl`
touch-panel projects. It was reverse-engineered from project files, GUI
Designer's own snapshot exports, and the installed assemblies — **no Extron
documentation exists for any of this**. Version 1.28.0.7 is the tested
boundary.

`SKILL.md` is the repeatable procedure for building or modifying a panel — the
workflows, the verification gates, and the traps. Start there for panel work.
`docs/history.md` holds retired setups and the record of which claims changed;
nothing in it is needed to use the toolkit, so keep dated narrative there rather
than in these instructions.
`docs/from-scratch.md` covers generating one; `docs/editing.md` covers changing
one that exists.

Read `docs/gdl-format.md` before changing anything that touches the format. It
is the accumulated findings, and most of them were expensive to discover.
`docs/design-rules.md` is Extron's own design standards reduced to encodable
rules, with what is documented kept strictly separate from what we extrapolated —
never quote an extrapolated number to a client as an Extron requirement.

**The canvas is not 1280x800.** Resolution and DPI are set by the panel model —
`docs/design-rules.md` §1 — and the fixtures are all one model. Assume nothing
about panel geometry from them.

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

**Whether GUI Designer is installed is the only environment split that matters.**
Everything that reads, renders, previews or plans runs on any OS with Python 3
(plus Pillow for rendering), and reproduces `tests/baseline.json` exactly.
Everything that *writes* or *builds* a `.gdl` needs Windows, 32-bit PowerShell
5.1 and an install of GUI Designer — and where GUI Designer is installed,
author, build and verify in one session.

| Runs anywhere | Needs GUI Designer installed |
|---|---|
| `gdl.container` / `data` / `nrbf` / `project` / `themes` / `fonts` | every `powershell/*.ps1` |
| `gdl.compose`, `tests/score.py`, `tests/compare_snapshots.py` | File > Save and Build |
| `gdl.spec` check / render / plan / donors | `examples/add-page-and-popup.ps1` |
| `gdl.edit` check / plan | |
| `gdl.idmap` check / write | |
| `gdl.designsys` build; `gdl.design` translate (needs headless Chrome) | |
| the `python -m pytest` suite | |
| `tests/verify_built.py`, `tests/verify_idmap.py`, given the built file | |

Setup is in `README.md` *Setup*. `fixtures/` is real client material — see
*Working on the fixtures* below — and anything pushed goes to GitHub.

## Four things that will waste your time if you don't know them

Each fails silently — the file opens, builds, and is wrong. The detail is in
`docs/gdl-format.md`.

1. **Clone, never construct** (§4). Constructors and property setters throw
   outside the running app, and a failed setter writes the backing field before
   it throws, so it looks like it worked. `Copy-GdlObject` an existing object,
   then `Set-GdlField` its backing fields.
2. **Popup bindings live in four places** (§6). Call `Test-GdlPopupBinding`
   rather than trusting your writes.
3. **Build owns the artwork** (§2). Author `borderFillColor` and a **named**
   border resource, never pixels. Neither survives into `layout.json`, so read
   them from `ProjectGCP` via `gdl/project.py`.
4. **A preview agreeing with the spec proves nothing about the panel.** Every
   silent authoring failure so far had the preview drawing what the spec said
   while the applier shipped the donor's value, and `gdl.spec check` measuring a
   number that never left the file. Verify the built result — *Verifying a
   change* below.

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
is that GUI Designer opens *and builds* it, and that needs GUI Designer
installed.

A clean build is still not proof the result is *right* — Build silently
relocates controls that don't fit their page, and bakes captions into artwork.
Close the loop:

```bash
python tests/verify_built.py out/plan.json out/generated.gdl
```

It diffs the built `layout.json` against the plan that produced it and exits
non-zero on any authored control that moved, lost its caption, or came back at
the donor's font size instead of the spec's - and on a panel that boots into the
wrong page, a popup that built as the wrong kind, or a button whose states
came back more, fewer, misnamed or drawn alike.

It also checks **color, off the artwork rather than the model.** That
distinction is the whole point: a built control's `BackgroundFillColor` reads
back as transparent white whatever you authored, because Build rasterizes fill,
border and caption into a PNG and leaves a `TLPImageID` behind. So the check
takes the plurality opaque color of each control's own asset, and reads the page
asset too — a donor background image re-rasterized under the fill is invisible
in every field and obvious in the artwork.

The ID map a programmer works from has a second gate:

```bash
python tests/verify_idmap.py out/idmap out/generated.gdl
```

It checks every page and popup name and every control ID in the map against the
built file - Build renumbers pages and keeps the donor's alongside, so agreement
with the spec is not agreement with the panel. `docs/idmap.md` §5 has what else
it checks.

## Driving GUI Designer

`powershell\New-GdlPanel.ps1` takes a spec to a built, verified panel with
nobody touching GUI Designer. To script anything it does not cover, read
`docs/from-scratch.md` §7 first: the obvious ways to trigger a build and to tell
when it has finished are both wrong, and each fails in a way that looks like
success.

**After upgrading GUI Designer, do that before trusting an unattended build.**
Preferences are stored per version, so an upgrade resets them, and the restored
default for *Automatically Remove Unused Resource Library Items During Save and
Build* is to ask. The first build then blocks on a modal that exposes no UIA
patterns, `Wait-GdlBuild.ps1` times out with no diagnosis, and nothing is
written. `docs/from-scratch.md` §7 *What will cost you time* has the fix.

## Conventions

- Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`).
- Python: stdlib-only outside `gdl/compose.py`. Keep it that way — reading a
  `.gdl` on a machine with nothing installed is a feature.
- Comments explain *why*, particularly where the code encodes a
  reverse-engineered rule that looks arbitrary. Those comments are the only
  record that a rule was measured rather than guessed.
- Don't reformat `gdl/nrbf.py` into a house style; it is a compact MS-NRBF
  reader and its terseness is deliberate.

## Keeping the docs true

These docs have drifted before — a stale test count, a build-completion signal
two files had already corrected, a SendKeys command the scripts had moved past —
each time because the same material lived in several files and only some copies
were updated. So:

- **A change and the docs it invalidates land in the same commit.** Before
  committing, search the docs for every name, path, parameter, number and
  behavior you touched — `git grep -n '<old thing>' -- '*.md'` — and fix each
  hit. A known-stale doc is a bug to fix now, not a follow-up to list.
- **Each topic has one home.** Other files get a one-line pointer, never a
  second copy — a second copy is a future contradiction.

  | Topic | Home |
  |---|---|
  | What is in the repo, install and setup | `README.md` |
  | What needs GUI Designer, and why | `CLAUDE.md` *Environment* |
  | Format facts and what Build does | `docs/gdl-format.md` |
  | Driving GUI Designer from a script | `docs/from-scratch.md` §7 |
  | Generating a panel, step by step | `SKILL.md` |
  | What controls do, and the ID map | `docs/idmap.md` |
  | Designing a panel in Claude Design | `docs/claude-design.md` |
  | Editing an existing panel | `docs/editing.md` |
  | Verification gates and the render baseline | `CLAUDE.md` *Verifying a change* |
  | Render findings | `docs/render-fidelity.md` |
  | Extron's design standards | `docs/design-rules.md` |
  | Fonts: recovery and licensing | `gdl/fonts/README.md` |
  | What is left to do, and known gaps | `docs/ROADMAP.md` |
  | Retired setups and revised beliefs | `docs/history.md` |

- **No counts that drift in prose.** Don't write how many tests or scripts
  there are; the tools report that. Measured results — baseline percentages,
  corpus-audit figures — are fine in their home, with where they came from.
- **Present tense only.** What used to be believed, when something was found,
  or which machine it ran on goes in `docs/history.md`.

## Environment traps that cost time

- **Check the commit limit before any large fan-out.** It is physical RAM plus
  the pagefile, so a machine with a small or fixed-size pagefile can be far
  tighter than its RAM suggests. Claude Code processes hold 150-600 MB each,
  every workflow agent adds one, and a Python process holding many parsed
  projects at once adds more. Past the limit, processes die mid-task and new
  ones fail with *The paging file is too small for this operation to complete* —
  which is what killed both runs of `workflows/gdl-bug-hunt.js` and the first
  version of `tests/audit_corpus.py`. Stream over
  projects instead of loading them all, keep workflows small, and let the OS
  manage the pagefile.
- **Do not write backslash escapes through a bash heredoc.** Backslash-v and
  backslash-a get interpreted before Python sees them, leaving literal 0x0B and
  0x07 bytes in the file. A doubled backslash does not survive either: `'C:\\'`
  in a quoted heredoc arrived as `'C:\'`. This has silently corrupted documented
  commands in these very files more than once. Use the Write/Edit tools for any
  content containing backslashes — which means essentially every Windows path.
- `Save-GdlProject` prints a bare `The system cannot find the file specified.
  (Exception from HRESULT: 0x80070002)` on every save. It comes from inside an
  Extron assembly during serialization, the return value is intact, and it is
  not an error.

## Things deliberately not in git

- **Most of `gdl/fonts/`** — retail and unlicensed faces, recovered from the
  tracked fixtures during setup. `face()` raises `LookupError` on the first face
  it cannot resolve, so skipping that stops the harness rather than degrading
  it. `gdl/fonts/README.md` has the per-file licensing, and which projects
  declare faces they do not embed. The bytes are still inside the tracked `.gdl`
  fixtures, so if the concern is distribution, `fixtures/` is the thing to look
  at.
- `out/`, `__pycache__/`, built viewer HTML.
- **`vendor/`'s contents** — Extron's templates and icon kit, reinstallable,
  pinned by SHA-256 in `vendor/MANIFEST.md`; `vendor/README.md` repopulates it.
  `tests/_corpus.py` falls back to the install path when it is empty.

## Where things live

`README.md` *What is here* maps the repo. `seeds/` and `archive/` are Git LFS:
without an LFS pull they are pointer files, and the seed tests skip rather than
fail.

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

Everything left to do, and every known gap, is in `docs/ROADMAP.md`.
