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
  their own size, and button feedback with any number of named states - authored
  from a spec, or edited state by state on an existing panel.
- **Designed in Claude Design**: a canvas drawn with an Extron template's
  design system translates to a spec and builds (`docs/claude-design.md`).
- **What the controls do**, from the same spec: `gdl.idmap` checks the page
  flips and writes the programmer's ID map, verified against the built panel
  (`New-GdlPanel.ps1 -IdMap`). Generated panels boot to their own start page and
  keep modal popups modal. `docs/idmap.md`.
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
2. **Fonts that are declared but not embedded, or not authorable.** Most seeds
   declare Arial Black without embedding it; Turbulence does the same for Arial
   and Shockwave for `extron_shockwave.ttf` (`gdl/fonts/README.md` has which).
   GUI Designer supplies them itself at build time - its temp held Monotype
   Arial Black 5.06 and Arial 5.10 while building from a seed that embeds neither
   (`archive/gui-designer/`). The renderer has no such source, so a preview of a
   seed-built panel can raise `LookupError`. Also: `fonts.extract()` keys
   results by file name, and Shockwave declares `arial.ttf` twice, so a missing
   one hides behind a found one. Separately, no seed has a `PBFontResource` for
   Arial Black, nor Mach or Turbulence for Open Sans Light, so a spec cannot ask
   for either (`seeds/README.md`) - and the applier cannot add one.
3. **Run the bug hunt** (`workflows/gdl-bug-hunt.js`) on a host with enough
   commit limit for the fan-out. `tests/audit_corpus.py` has done the cheap deterministic
   part; the workflow is for the judgment-heavy dimensions: collection traps,
   dead guards, silent no-ops, plan-contract drift, verifier blind spots,
   fields a clone inherits, what is secretly Afterburn-only, layout-math edges.
4. **A real-size panel.** Nothing generated has exceeded three pages; the client
   project has 27. A 20+ page spec with navigation, popups shared across pages
   and per-page popup references is where the next class of bug lives. With `nav`
   the page flow is part of the spec, and `verify_idmap.py` checks it against
   the build.
5. **Claude Design as the front end: the other three templates.** Afterburn is
   a design system, and a canvas drawn with it translates, builds and verifies
   end to end, with a side-by-side of each artboard and the built panel for
   sign-off. Mach, Shockwave and Turbulence need their profiles, each checked
   against its seed's built artwork. `docs/claude-design.md` §7.
6. **Icon-font glyphs in the spec vocabulary.** Kit images are in it - a
   button's `image`, on itself or per state, which is how the Claude Design
   systems draw icons - but the other proven route, font glyphs (~339 icons, no
   image resource), still cannot be written in a spec.
7. **Pick the seed automatically** - `gdl.spec donors --auto` choosing from
   `seeds/` by theme and canvas, so a prose brief needs no file path.
8. **Theme-portable borders.** No border resource is defined by every project
   in the corpus. A spec that says `rounded` or `capsule` should resolve to
   whatever the donor's family calls it.
9. **Close `verify_built.py`'s remaining blind spots**: text alignment, donor
   controls that ride along on a generated page unasked, and one volume-level
   icon built in place of the next - at 64 px they differ by one thin wave, 7%
   of the inked pixels, under the image check's 25%.
10. **Run the seed ground-truth test in CI** with
    `git lfs pull --include "seeds/Afterburn 1035.gdl"` (about 3 MB of LFS
    bandwidth per build).

## Backlog - real, not urgent

- `renumber` is planned and checked but has never been through a build. Build
  one and run `tests/verify_built.py` against it - which, until the behavior
  work, never compared a built control's ID at all (it looked up `UserID`;
  layout.json writes `UserId`).
- **Behavior the format carries but the spec cannot yet say:** the Offline Page
  and its enable flag, and a popup's auto-hide timeout (0 on every popup in the
  corpus). Both are applier work.
- **An ID map for an existing panel.** `gdl.idmap` reads a spec; a client
  project that was never a spec has none, though its built `layout.json` holds
  every ID, type, page and caption a map needs.
- `docs/from-scratch.md` §6: control-ID uniqueness and `referenceCountField`
  (question 6) are untested; an out-of-corpus border radius/thickness *builds*
  but was never checked to *rasterize* correctly; preview fidelity on a fully
  synthetic page rests on one control.
- The 5.86% render residual on the TLP1035 pages. Not the typeface; cause
  unknown.
- **`gdl.compose` draws bold Open Sans as regular.** `gdl/fonts/` carries Open
  Sans Regular and Light only, and `face()` falls back to the regular file, so
  a bold caption on a seed-built panel renders regular - the largest remaining
  difference in `gdl.design compare`. Open Sans Bold is Apache 2.0 like the
  others; adding it is a render change, so it needs `tests/score.py` before and
  after.
- `gdl.fonts` cannot extract from a `.glt`: no `layout.json`, so no declared
  sizes.
- **ECP's phone and tablet canvases have no donor, and cannot have one.** The
  six themable combinations (Afterburn / Mach / Shockwave × 16-9 and 16-10) are
  all seeded. The other five presets — iPhone, Android Phone, iPad, Android
  Tablet and Custom — only offer Blank in the wizard, and a blank ECP project is
  1 page and 3 controls, so there is nothing useful to clone from. Authoring for
  a phone canvas therefore means `retarget` off a 16-9 seed, which has never been
  measured against an ECP target.
- **The probes' error and warning counts are still 1.27.0.9 numbers.**
  `New-FormatProbes.ps1` has been re-run on 1.28.0.7 and all three still author,
  open and build, but the Build Manager's own 0-errors/0-warnings readout was not
  re-read — only the resulting files were checked.
- **The 1.28-written `.gdl` has not been opened in 1.27.** Output is now stamped
  `Layout.Contracts 5.6.0.0`, so files this toolkit writes are probably not
  backward-compatible; 1.27 was uninstalled by the upgrade, so it is untested
  either way. Matters only if a client is still on the old version.
- `referenceCountField` semantics; the size-dependent vertical text residual
  (`docs/render-fidelity.md` finding 7); every text finding validated against
  one typeface.

`python tests/audit_corpus.py` checks the documented invariants against every
project it can reach; `docs/gdl-format.md` §9 has what it checks and its last
result.
