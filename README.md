# extron-gdl-toolkit

Read, render, edit and author Extron GUI Designer `.gdl` touch-panel projects
from code.

Verified against GUI Designer 1.28.0.7. Files written by this toolkit open in
the application, survive structural edits (adding and removing pages, popup
pages, popup page references and controls) and build successfully.

Not affiliated with Extron.

## Start here

| if you want to | go to |
|---|---|
| see every page, popup and control ID in a `.gdl` | `python -m gdl.idmap from-built tests/data/synthetic/synthetic.gdl out/idmap`, or the HTML viewer in *Quick start* |
| change a panel that already exists | *Changing a panel that already exists*, below, then `docs/editing.md` |
| generate a panel from a spec | *Generating a panel from a spec*, below, then `docs/from-scratch.md` |
| have Claude Code build a panel | the paragraph that begins "With Claude Code", below |
| understand the file format | `docs/gdl-format.md` |
| see what is left to do | `docs/ROADMAP.md` |

Reading, rendering, previewing and planning run on any OS with Python 3.11
(Pillow for rendering). Writing or building a `.gdl` needs Windows, 32-bit
Windows PowerShell 5.1 and GUI Designer. `CLAUDE.md` *Environment* has the
split command by command. The seeds are Git LFS files, so run `git lfs pull`
after cloning, or every command that names one reads a small pointer file.

With Claude Code, ask for the panel you want in this repository: *"build the
huddle canvas at <claude.ai link> for a TLP Pro 1035 and 725"*, *"make a
boardroom panel from this brief"*, *"change the client's 1035 panel so..."*.
The `extron-panel` skill (`.claude/skills/`) points Claude Code at the
procedure in `SKILL.md`, which also reads fine as a runbook without it. A
Design canvas drawn in the Claude app with an Extron template's design system
is built as `docs/claude-design.md` §1 says, and comes out as each panel's
built `.gdl`, the programmer's ID map and a sign-off page. Building from a
canvas needs Chrome too; *Setup*, below, gets a machine ready.

## Why

A `.gdl` is opaque: a ZIP with deliberately mangled signatures wrapping a .NET
`BinaryFormatter` graph. So you cannot diff two panel revisions, audit which
control drives which ID, or generate a panel from a spec instead of clicking it
together.

## What is here

Each folder marked with a README lists its own files.

| folder | what is there | need it? |
|---|---|---|
| [`gdl/`](gdl/) | the Python package: read, render, spec, edit, ID map, Design canvases and design systems (README) | yes |
| [`powershell/`](powershell/) | scripts that write and build `.gdl` files through GUI Designer, Windows only (README) | to build |
| [`examples/`](examples/) | specs, edit sets and an authoring script to start from (README) | to learn |
| [`seeds/`](seeds/) | themed starting projects per panel model, made in GUI Designer, with no client material (Git LFS; README lists them) | to author |
| [`docs/`](docs/) | the format write-up, the how-to guides, the roadmap (README) | `gdl-format.md` first |
| [`tests/`](tests/) | the pytest suite, the gates that check a built panel, and `data/synthetic/`, the render baseline (README) | to check a build |
| [`viewer/`](viewer/) | builds a single-file HTML browser for every page and popup | optional |
| [`vendor/`](vendor/) | where Extron's templates and icons go; on disk, not pushed (README) | for templates and icons |
| [`research/`](research/) | measured findings and unshipped render improvements, with their numbers and scripts | no |
| [`workflows/`](workflows/) | the multi-agent bug hunt: falsifies the code's and docs' claims against every project, then verifies each finding adversarially | no |
| [`archive/`](archive/) | raw working state carried off an earlier build host, kept as evidence (Git LFS) | no |
| [`tools/`](tools/) | `public_sync.py`, which builds and checks the public copy, and the build-timing tools (README) | no |
| `private/` | the owner's machine only, never tracked: GUI Designer's settings, the publish denylist, notes | |

And the files at the top:

| file | what it is |
|---|---|
| `SKILL.md` | the repeatable procedure for building or modifying a panel. Written for Claude Code; reads as a runbook too |
| `CLAUDE.md` | instructions for AI agents, including the *Environment* table of what needs GUI Designer |
| `.claude/skills/extron-panel/` | registers `SKILL.md` as a Claude Code skill, so asking for a panel in this repo finds it |
| `requirements.txt` | Pillow, for rendering |
| `pytest.ini` | pytest settings |

## Setup

Verified with:

| Install | Version | Needed for |
|---|---|---|
| Python | 3.11.9 | everything; reading, editing and plan generation are stdlib-only |
| Pillow, pytest | 12.3.0, 9.1.1 | rendering and the test suite |
| Git LFS | 3.7.1 | `seeds/` and `archive/` |
| Google Chrome or Chromium | 155.0.8059.40 | a Design canvas: `gdl.design` lays it out and draws its sign-off page headless (`--chrome` or `CHROME` for one it does not find) |
| Extron GUI Designer | **1.28.0.7**, the tested boundary | writing and building a `.gdl` — `CLAUDE.md` *Environment* says what else that needs |

Then, from the repo root:

1. `git clone`, then `git lfs pull`. Without it `seeds/` holds LFS pointer
   files, and the seed tests skip rather than fail.
2. `pip install -r requirements.txt pytest`
3. Extract the fonts from the synthetic fixture's build, which carries
   Monotype Arial and Arial Black and every face the render baseline is scored
   in: `python -m gdl.fonts tests/data/synthetic/synthetic.gdl gdl/fonts/`.
4. With GUI Designer installed, repopulate `vendor/`; `vendor/README.md` has
   the commands. On a machine without it - a Linux box that translates and
   runs the tests while the Windows one builds - copy `vendor/` and the
   install's `Resources/` from the Windows machine, and set
   `GDL_EXTRON_RESOURCES` to the copy of `Resources/`, kept apart from
   `vendor/` (`vendor/README.md` says why).
5. For translating a canvas and the Chrome tests, the Design type's runtime:
   set `GDL_DC_RUNTIME` to a copy of `artifact-type/dc-runtime.js`, read off
   any Design canvas with Claude Code's Artifact tool, or - in the private
   archive repository only - its copy under `archive/dc-runtime/`. It must be
   one `gdl/dc_runtime.json` pins
   (`docs/claude-design.md` §5). Without it the Chrome tests skip. Where Chrome
   cannot make its sandbox (a root shell, a container), set
   `GDL_CHROME_NO_SANDBOX=1`; unset, the sandbox stays on.
6. `python -m pytest`, then `python tests/audit_corpus.py`. Any FAIL the audit
   reports should already be an open item in `docs/ROADMAP.md`. Before
   publishing a theme's design system, `python -m gdl.designsys audit <theme>`
   reports what it says about its template that the template's own pages do
   not back (`docs/claude-design.md` §2 *Truth*); a theme at zero is ready.

Three things trip a fresh Windows machine: cloning into a deep directory needs
`git config --global core.longpaths true`; the PowerShell entry points need
`-ExecutionPolicy Bypass` where no policy is set; and anything that fans out
agents needs the commit limit to allow it (`CLAUDE.md` *Environment traps
that cost time*).

Optionally, `archive/claude/memory/` holds Claude Code's accumulated context for
this project. It belongs in the per-project memory directory, whose name Claude
Code derives from the repo's path.

## Quick start

Run these from the repo root. The package is not pip-installable, so
`python -m gdl.*` needs the repo as the working directory.

Each command below uses the synthetic fixture, a tracked project in generic
words, so it runs in the private archive and the public copy alike with no
`git lfs pull`. Swap in your own `.gdl` the same way.

List every page, popup and addressable control, with IDs and captions:

```bash
python -m gdl.idmap from-built tests/data/synthetic/synthetic.gdl out/idmap
```

Unpack a project's raw contents:

```bash
python -m gdl.container extract tests/data/synthetic/synthetic.gdl out/
```

Build the HTML viewer for the projects in a folder:

```bash
python -m gdl.data tests/data/synthetic panel-data.json
python viewer/build_viewer.py viewer/template.html panel-data.json panel-atlas.html
```

Score the compositor against ground truth (needs Pillow):

```bash
# the snapshots belong to this project; the harness refuses any other (exit 2)
python tests/compare_snapshots.py tests/data/synthetic/synthetic.gdl tests/data/synthetic/snapshots/Individual
# the same: with no project it scores the synthetic fixture
python tests/compare_snapshots.py
```

`tests/score.py record` and `tests/score.py diff` do the same comparison and
exit non-zero on a regression, which is what a render change should be checked
against.

## Changing a panel that already exists

Write the change as JSON, resolve it against the real project, then apply it.
Five operations: `rename` captions and `restyle` colors, both state by state;
`states` to add, remove or rename a button's states; `retarget` to another
panel model, or the other way up for a panel that rotates, with optional
rescaling; and `renumber` addressable IDs. Selectors
are ANDed and match exactly or by regex. `docs/editing.md` has the detail.

```bash
python -m gdl.edit check examples/edits.json tests/data/synthetic/synthetic.gdl
python -m gdl.edit plan  examples/edits.json tests/data/synthetic/synthetic.gdl out/edits-plan.json
```

`check` resolves every selector against the real file, so a selector that
matches nothing is an error here rather than a silent no-op at apply time.

## Generating a panel from a spec

```bash
python -m gdl.spec check   examples/panel.json          # ids, off-canvas, sizes, resources
python -m gdl.spec render  examples/panel.json out/preview.png
python -m gdl.spec donors  examples/panel.json "seeds/Afterburn 1035.gdl"
python -m gdl.spec donors  examples/panel.json --auto   # the seed for its "family"
python -m gdl.spec icons   Mach out/mach-icons.png       # what an "icon" takes, drawn
python -m gdl.spec plan    examples/panel.json out/plan.json --donor "seeds/Afterburn 1035.gdl"

python -m gdl.idmap check examples/huddle-functions.json   # what the controls do
python -m gdl.idmap write examples/huddle-functions.json out/idmap
python -m gdl.idmap from-built <panel.gdl> out/idmap        # a panel that was never a spec
python -m gdl.idmap diff out/idmap-r1 out/idmap-r2          # what a program meets in a revision
```

Look at the preview before building. The compositor is scored against GUI
Designer's own output, so it is a real preview. `donors` finds in seconds what
would otherwise surface only in a build — a control type the donor cannot
supply, a page or popup name the built panel keeps from it, a font it lacks and
no seed carries, a border it lacks and has nothing of that shape for. A face a
seed carries, or a border of a near shape, it names, and `plan --donor` appends
or builds. `SKILL.md` has the full procedure, and where GUI Designer is installed
`powershell\New-GdlPanel.ps1` runs all of it, build and verification included.
A spec can also say what its controls do; `gdl.idmap` checks the page flips and
writes the programmer's ID map from the same file (`docs/idmap.md`). A revised
canvas translated with the previous map (`--previous`) keeps every ID the
program uses, and its map comes with the changes (`docs/idmap.md` §9).

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
python -m gdl.container pack tests/data/synthetic/synthetic.gdl out/new_ProjectGCP "My Project.gdl"
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

A retarget of a whole client project from a TLP Pro 1035T to a TLP Pro
1535M came back 654 of 654 controls correct in the built file, and of the
Afterburn 1035 seed 650 of 650. A generated
panel went from `examples/panel.json` through the layout pass, ID allocation,
`Apply-GdlPlan.ps1` and `gdl.container pack` into GUI Designer on the Afterburn
1035 seed, which built it and verified clean. `docs/generated-built.png` is
that page rendered from its own built payload rather than from a preview.

The compositor is scored against GUI Designer's own snapshot exports:
`tests/baseline-synthetic.json` holds the current numbers on the synthetic
fixture, and `docs/render-fidelity.md` what the residual is. Known gaps, and everything left to do, are in
`docs/ROADMAP.md`.

## Fonts

The renderer resolves faces from `gdl/fonts/`, then a family with no file
there from the seed that carries it, before the system font path. A face it
cannot find in any draws in a stand-in - the host's copy, or Arial - and
`tests/score.py record` refuses to score over one, or over a face read from a
seed, which can be another build than the synthetic fixture embeds; a face
found nowhere raises.
`gdl/fonts/README.md` has which faces are tracked and why, how the rest are
recovered from the synthetic fixture's build, and which projects declare faces
they do not embed.

## Provenance and licensing

Reverse-engineered from project files, GUI Designer's own snapshot exports and
the installed assemblies. No Extron documentation was involved, so 1.28.0.7 is
the tested boundary.

**Licence.** The toolkit's own code and documentation are under the Apache
License 2.0 (`LICENSE`). It does not relicense what is not the project's own:
`seeds/` carries Extron's artwork and fonts, and the fonts in `gdl/fonts/` keep
their own licences. `NOTICE` says which is which.

**The project has two repositories.** Work happens in a private archive,
`extron-gdl-toolkit-archive`, with the complete history. The public copy,
`extron-gdl-toolkit`, is built from it by `tools/public_sync.py`, and leaves
out:

- the evidence logs and builds of `archive/job-2419a20b/` and
  `archive/job-e823df9b/` (that `docs/claude-design.md` and `docs/ROADMAP.md`
  cite throughout), scratch files that name the client or the owner's folders,
  and the working sessions' transcripts;
- the design notes and plan for the split itself;
- GUI Designer's per-user settings file, which neither repository tracks.

`tools/public_sync.py`'s `EXCLUDE` is the full list.

A doc that names one of these means the archive's copy. A test that needs one
skips and says which, so a clone of the public copy runs everything else, the
render baseline (the synthetic fixture, `tests/data/synthetic/`) included.
`seeds/`, made from Extron's
templates in GUI Designer, is published. Extron's own installer files are in
neither repository: `vendor/README.md` repopulates them from an install.

Every public commit is checked before it is pushed: no held-back path, no
home-folder path or job-site folder name, nothing the owner's private denylist
names - in a file, a path or a message - nothing from the settings file, and no
binary other than the bytes a person looked at.
