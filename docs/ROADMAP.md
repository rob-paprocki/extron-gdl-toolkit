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
- For test results and branch or PR state, run `python -m pytest`, `git` and
  `gh` — a snapshot written into a doc is stale the next time anything merges.
  Setting up a machine is in `README.md` *Setup*.

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
   renderer has no such source, so a preview of a seed-built panel can raise
   `LookupError`. Also: `fonts.extract()` keys results by file name,
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

- `renumber` is planned and checked but has never been through a build. Build
  one and run `tests/verify_built.py` against it.
- `docs/from-scratch.md` §6: control-ID uniqueness and `referenceCountField`
  (question 6) are untested; an out-of-corpus border radius/thickness *builds*
  but was never checked to *rasterize* correctly; preview fidelity on a fully
  synthetic page rests on one control.
- The 5.86% render residual on the TLP1035 pages. Not the typeface; cause
  unknown.
- `gdl.fonts` cannot extract from a `.glt`: no `layout.json`, so no declared
  sizes.
- `referenceCountField` semantics; the size-dependent vertical text residual
  (`docs/render-fidelity.md` finding 7); every text finding validated against
  one typeface.

`python tests/audit_corpus.py` checks the documented invariants against every
project it can reach; `docs/gdl-format.md` §9 has what it checks and its last
result.
