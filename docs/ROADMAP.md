# Roadmap

Everything left to do on this project, in order, split by who has to do it. The
goal is unchanged: **prose in, production-ready Extron panel out, with nobody
opening GUI Designer.**

## Where things stand

- Proven end to end on real hardware: spec → plan → apply → pack → GUI Designer
  Save and Build → verify, unattended and without taking the foreground
  (`powershell/New-GdlPanel.ps1`), from a client project or from a clean seed.
- Also proven: Arial recovery, font application, UTF-8 specs, multi-page panels,
  clean-room authoring, retarget from a seed (650/650), popup canvases that keep
  their own size, and Off/On button feedback.
- `python -m pytest` is 157 tests and they pass. For live branch and PR state,
  ask `git` and `gh` — a status snapshot written into a doc is stale the next
  time anything merges.

## Setting up a working machine

Nothing this project needs lives only on one machine: everything that was
working state is in the repo, and everything else is installed software or GUI
Designer's own shipped content, which a reinstall restores. Login tokens are
deliberately not in the repo — sign in again.

What this project needs, with the versions it has been verified against:

| Install | Version | Why |
|---|---|---|
| Extron GUI Designer | **1.27.0.9** | the tested boundary; builds and the authoring bridge need it |
| Python | 3.11.9 | then `pip install -r requirements.txt pytest` (Pillow 12.3.0, pytest 9.1.1) |
| Git + Git LFS | 2.55 / 3.7.1 | `seeds/` and `archive/` are LFS objects |
| GitHub CLI | 2.100 | PRs and issues, as `rob-paprocki` |
| VS Code (optional) | 1.136 | with `ms-python.python`, `ms-vscode.powershell`, `anthropic.claude-code` |
| Extron Global Configurator Professional | 3.33.0.38 | not used by this repo; it was installed for other Extron work |

Then:

1. **Let the OS manage the pagefile** (System > About > Advanced system
   settings > Performance Settings > Advanced > Virtual memory > *Automatically
   manage paging file size*). The commit limit is RAM plus pagefile, so a fixed
   small pagefile can be far tighter than the RAM suggests. A host limited to
   8.5 GB this way killed both runs of the bug-hunt workflow about 90 seconds in
   and made the next command fail with *The paging file is too small*.
2. `git clone`, then `git lfs pull`.
3. `pip install -r requirements.txt pytest`, then extract the fonts:
   `for f in fixtures/gdl/*.gdl; do python -m gdl.fonts "$f" gdl/fonts/; done`.
   All six fixtures — no single one embeds every face.
4. **Repopulate `vendor/`** from the GUI Designer install -
   `vendor/README.md` has the commands, and `vendor/MANIFEST.md` the
   SHA-256 of every file, so a changed template shows up.
5. `python -m pytest`, then `python tests/audit_corpus.py` - both should match
   what is recorded here. The audit is expected to report 2 FAIL of 12
   invariants; they are *Mine* #1 and #2 below, not a broken checkout.
6. **Restore Claude Code's memory for this folder** if you want the accumulated
   project context: `archive/claude/memory/` is the copy. It belongs in the
   per-project memory directory, whose name Claude Code derives from the repo's
   working path — so it changes if the repo moves.
7. Keep build scratch on a local disk (`-Work`, default under `C:\gdlwork`).
   GUI Designer is slow against a network or mounted drive.

## Yours

1. **Decide what `fixtures/` should be.** It is a real client's project
   (Liberty Bank, job J26450039), on GitHub, private. Seeds mean it no longer
   has to be the donor in the examples and CI - but the render baseline is
   scored against its snapshot exports, so it cannot simply be deleted. Keep
   it; keep it but move examples and CI onto seeds; or replace it with a
   synthetic fixture and re-baseline (about a day).
2. **Make seeds at the sizes you deliver on.** `seeds/README.md` lists the gaps:
   the Teams Rooms family, Zoom Rooms at 725 and 986x740, and 1024x600, 1366x768,
   800x480, 1280x720 and 320x240. About a minute each in GUI Designer; a
   native-size seed beats a retarget, which matches Extron's own hand layout
   for only 22% of controls.
3. **Say whether `vendor/` should be pushed** (about 470 MB of Extron's
   reinstallable content; one `git add -f vendor/extron` plus an LFS rule).

## Mine, in order

1. **Fix the model table.** `MODELS_FULL['TLP1230WTG']` is 800x480 at 0 DPI -
   the generic platform class's default - but Extron's own 1230W project builds
   at 1920x720, its only supported resolution, so `retarget` to that model sets
   the wrong screen size. And every entry holds one orientation where the
   platforms support both (300M 320x480 and 480x320; 1035M 1280x800 and
   800x1280), so a portrait 1035 or a landscape 300M cannot be targeted.
   `layout.json`'s `Platform.SupportedResolutions` is the ground truth.
2. **Fonts that are declared but not embedded.** 11 of the 14 seeds declare
   Arial Black without embedding it; Turbulence does the same for Arial and
   Shockwave for `extron_shockwave.ttf`. GUI Designer supplies them itself at
   build time - its temp held Monotype Arial Black 5.06 and Arial 5.10 while
   building from a seed that embeds neither (`archive/gui-designer/`). The
   renderer has no such source, so a preview of a seed-built panel off Windows
   can raise `LookupError`. Also: `fonts.extract()` keys results by file name,
   and Shockwave declares `arial.ttf` twice, so a missing one hides behind a
   found one.
3. **Run the bug hunt** (`workflows/gdl-bug-hunt.js`) on a host with enough
   commit limit for the fan-out. `tests/audit_corpus.py` has done the cheap deterministic
   part; the workflow is for the judgment-heavy dimensions: collection traps,
   dead guards, silent no-ops, plan-contract drift, verifier blind spots,
   fields a clone inherits, what is secretly Afterburn-only, layout-math edges.
4. **Re-verify anything edited with `rename` before `7b3e630`.** Until then it
   wrote only state 0, so a renamed button shows its old caption once the
   control system switches it On. The 12/12 rename verification never looked at
   state 1. Extend `verify_built.check_edits` to every state and re-run the
   worked edit.
5. **A real-size panel.** Nothing generated has exceeded three pages; the client
   project has 27. A 20+ page spec with navigation, popups shared across pages
   and per-page popup references is where the next class of bug lives.
6. **Icons in the spec vocabulary.** Both routes are proven by probe - font
   glyphs (~339 icons, no image resource) and appended image resources
   (`powershell/New-ImageProbe.ps1`) - and neither can be written in a spec.
7. **Pick the seed automatically** - `gdl.spec donors --auto` choosing from
   `seeds/` by theme and canvas, so a prose brief needs no file path.
8. **Theme-portable borders.** No border resource is defined by all 64 projects
   in the corpus. A spec that says `rounded` or `capsule` should resolve to
   whatever the donor's family calls it.
9. **Multi-state buttons.** Off/On is 98.5% of two-state buttons; the rest are
   `Disconnected` / `Connected`, `Not Muted` / `Muted`, `Muted` / `Level 1..3`.
10. **Close `verify_built.py`'s remaining blind spots**: `TLPDefaultStateID`,
    text alignment, per-state captions, and donor controls that ride along on a
    generated page unasked.
11. **Run the seed ground-truth test in CI** with
    `git lfs pull --include "seeds/Afterburn 1035.gdl"` (about 3 MB of LFS
    bandwidth per build).

## Backlog - real, not urgent

- `docs/from-scratch.md` §6: questions 5 and 6 untested; an out-of-corpus border
  radius/thickness *builds* but was never checked to *rasterize* correctly;
  preview fidelity on a fully synthetic page rests on one control.
- The 5.86% render residual on the TLP1035 pages. Not the typeface; cause
  unknown.
- `gdl.fonts` cannot extract from a `.glt`: no `layout.json`, so no declared
  sizes.
- `referenceCountField` semantics; the size-dependent vertical text residual
  (`docs/render-fidelity.md` finding 7); every text finding validated against
  one typeface.

## Corpus audit, 2026-09-11

`python tests/audit_corpus.py` over every project on the box - 6 fixtures, 14
seeds, 44 templates - after the Offline Page correction below.

| Invariant | Result |
|---|---|
| Button states are countable (the `PBStates.Count` trap) | PASS |
| Off/On is the dominant state pair | PASS - 13,589 of 13,792 two-state buttons, 98.5% |
| A popup's built size equals its authored size | PASS on all 20 built projects |
| `TLPDefaultStateID` is 0 | PASS |
| Page and popup names unique per project | PASS |
| `userId` fits in UInt16 | PASS - highest 61,091 |
| A button's caption lives on its state | PASS - state 88.6%, formatted state 11.4% |
| One full-canvas popup reference per shown modal popup, per page | PASS on all 20 - after correcting the rule (below) |
| Every declared face is recoverable | **FAIL** - see *Mine* #2 |
| Every canvas is a model the table can target | **FAIL** - 1920x720 and 480x320 (*Mine* #1); also 1920x1200 and 986x740, the Teams Rooms and Zoom Rooms control templates, whose platforms the table does not list |
| Border resources shared across themes | INFO - none common to all 64 projects; Afterburn 17-32, Mach 13-15, Shockwave 13-14, Turbulence 13, Zoom Rooms 16-17 |
| Controls Build leaves unrasterized | INFO - 2 to 187 per project; the baseline to compare a suspect build against |

The modal-reference rule took two corrections, both found by this audit. The
docs said Build adds one full-canvas reference per modal popup; that was one
too many on 19 of the 20 built projects. "All but the Offline Page" then failed
only the Turbulence seed - the one project with `EnableOfflinePage` on. The
rule is: one per modal popup, the Offline Page counting only when it is enabled.
