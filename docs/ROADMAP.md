# Roadmap

Everything left to do on this project, in order, split by who has to do it. The
goal is unchanged: **prose in, production-ready Extron panel out, with nobody
opening GUI Designer.**

## Where things stand

- Proven end to end on a real GUI Designer install (1.28.0.7): spec → plan →
  apply → pack → Save and Build → verify, unattended and without taking the
  foreground (`powershell/New-GdlPanel.ps1`), from a client project or from a
  clean seed. The proof ends at the built file and its artwork; no load onto a
  touch panel is recorded, so what a panel's firmware draws from `layout.json` -
  live captions, translucent fills, a held button - is read off the file, not
  seen.
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

1. **Keep the Windows session connected while seeds are made.**
   `powershell/New-GdlSeed.ps1` clicks through GUI Designer's Project Create
   Wizard, which draws nothing in a locked or disconnected session, so the
   script refuses rather than click blind. Sign in at the console, or keep a
   Remote Desktop window open and restored, for the run - about two minutes a
   seed, with its build. Next needed when a theme's phase starts (item 5).
2. **Say whether any client is still on GUI Designer 1.27.** What this toolkit
   writes is stamped for 1.28 and has never been opened in 1.27 (*Backlog*).
   If a client is, a 1.27 install to test against is the next step; if none
   is, that Backlog item can go.

## Mine, in order

1. **Both orientations as targets.** Every `MODELS_FULL` entry holds one
   orientation, where a built project's `Platform.SupportedResolutions` - the
   ground truth - lists both for the 300M (320x480 and 480x320) and for the
   835M and 1035M (1280x800 and 800x1280; `docs/design-rules.md` §1). So
   `retarget` cannot make a portrait 835 or 1035 or a landscape 300M, and no
   model reaches Afterburn's 300 Landscape series: `gdl.templates.template_for`
   matches the model's one size, so the 300M (320x480) takes the Portrait
   series, and the Landscape series' entry in `gdl/designsys/afterburn.json` has
   no models and no seed, though `seeds/Afterburn 300M Landscape.gdl` exists.
   The touch check and the corpus audit know the 300M both ways
   (`gdl.spec.sizes`); the model table, the template match and the seed map do
   not.
2. **Fonts: declared is not carried.** `gdl.fonts` follows `layout.json`, which
   does not always match what a project carries: a seed can declare Arial Black
   and define no resource for it (`seeds/README.md` has which), or declare
   `arial.ttf` twice with one of the two embedded (`gdl/fonts/README.md` has
   which). `tests/audit_corpus.py` reports the first as a FAIL and cannot see
   the second: `extract()` keys results by file name, so a declaration that
   matches nothing hides behind one that does. GUI Designer adds Arial Black
   when it builds: `archive/job-9fe2c865/tmp/rt/` holds a seed with no
   resource for it and its build with one. Reading each `PBFontResource`'s own
   `dataField` recovers what a project carries, from a `.glt` as well. A face a
   seed has no resource for is still one a spec cannot ask for there - the
   applier cannot add one (`seeds/README.md` has which seeds define which).
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
5. **Claude Design as the front end: every panel.** Afterburn's design system
   builds one canvas for every panel a room has, each sized for its physical
   screen - proven on the TLP Pro 1035, 725, 525 and 320 (`docs/claude-design.md`
   §4 and §6). Mach, Shockwave and Turbulence are design systems for the
   1280×800 TLP Pro 1025/1035 only. Each next needs:
   - **Its per-series table, measured another way.** `tests/measure_series.py`
     finds a series' main region in the opaque body of Afterburn's background
     art, and these themes have none to find: it prints `main None rail None`
     for every one of their series, because their pages name backgrounds it
     cannot read as kit art (`mach-bg-02.png`, `SW_bkgd_01.png`, `bkgd_pc.png`)
     and draw their bars, wells and rails as controls. Their regions come off
     each series template's own controls.
   - **Proof on two panels:** the 1035 and one smaller, a 725 or a 525. That
     needs one small seed, not three - Mach has a 300M Portrait seed and no 725
     or 525, Shockwave and Turbulence no small seed at all.
   - **Seeds at the other sizes**, as a theme's series need them, made with
     `New-GdlSeed.ps1`, which needs the connected desktop (*Yours*). 800x480 is
     two series in all three themes - the 520, tier B, and the 720, tier A, which
     take different layouts - where Afterburn has only the 520.
   Design and phases: `docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md`.
   A native-size seed beats a retarget, which matches Extron's own hand layout
   for only 22% of controls. The other gaps in `seeds/README.md` (Teams Rooms,
   Zoom Rooms, 1366x768, 1280x720) wait for a job that needs one.
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
10. **Retire the client fixtures.** `fixtures/` is a real client's project,
    in the archive only, and the builds in `archive/gdlwork/` made with it as
    the donor carry the same material (`archive/README.md` *Sensitivity*). The
    render baseline is scored against the fixtures' snapshot exports, so they
    go last: first a synthetic fixture with the same reach (many pages, every
    control type the renderer scores) and GUI Designer's snapshot exports of
    it, and a new `tests/baseline.json` from `tests/score.py` - which also gives
    the public copy a render baseline; then delete them. The examples and CI
    already run on a seed.

## Backlog - real, not urgent

- **`gdl.compose` draws a translucent control at full strength.** The Shockwave
  seeds' video well - white at 85% transparency, which Build bakes into its art
  as alpha 38 - renders opaque white, because `paste` writes any pixel above
  alpha 0 as GUI Designer's snapshots do (`docs/render-fidelity.md` §2); the
  compositor never reads `transparencyField`, and the art already carries it.
  Ten controls in each of the two archived client fixtures set it (75 and
  80), and so do the Turbulence seed's side bars, modal windows and room shape.
  Blending any of them moves the preview off the snapshots the baseline is
  scored against, so score a change before and after (`docs/gdl-format.md` §7).
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
- **`gdl.compose` draws bold Open Sans as regular.** `gdl/fonts/` carries Open
  Sans Regular and Light only, and `face()` falls back to the regular file, so
  a bold caption on a seed-built panel renders regular - the largest remaining
  difference in `gdl.design compare`. Open Sans Bold is Apache 2.0 like the
  others; adding it is a render change, so it needs `tests/score.py` before and
  after.
- `gdl.fonts` cannot extract from a `.glt`: no `layout.json`, so no declared
  sizes.
- **A horizontal slider in a template whose thumb is not square** (Shockwave's,
  52 across and 34 along). The spec turns the thumb's box as the canvas does, as
  Build keeps width and height literal: the Zoom Rooms seeds' two horizontal
  sliders each (on the Lighting popup, 564x25) have a thumb 7 wide and 25 tall.
  But the kit's thumb art is drawn for a vertical slider and goes into the
  turned box as it is, and `verify_built`'s horizontal rail model mirrors the
  vertical one, which is all that was measured; those Zoom seeds' built rails
  are the ground truth to check it against. No Shockwave seed or canvas has a
  horizontal slider yet; build one and measure both before relying on it.
- **A tier B hub shared by several groups.** On a mid-size panel (the 525)
  each `Group` pages as popups in its own box. The spec's hub - one region all
  the page's groups share, switched by a rail of group buttons - needs the Page
  to lay its groups out together; a page with several groups shows them all,
  each paged, until then.
- **A left `Rail`.** A canvas has one Rail, the right one; side controls on the
  left are mapped with the page, and on a panel with no room beside its main
  region they are refused, by name.
- **An icon on a group's button.** On a small panel a Group becomes one button
  that opens its pages; it carries the group's title, and no icon yet.
- **Smaller gaps in translating for every panel**, each found in review and
  none met by the huddle canvas:
  - a canvas's own repeats (`sc-for`) in a main area are not laid out for
    other panels - they stay where they were drawn;
  - a derived control named like a canvas control on its page, two controls
    with one name on a page, and a panel listed twice are not refused by name
    (the second is refused, as an ID clash);
  - an empty Group leaves an empty region on a mid-size panel;
  - captions are measured with the fallback face until Open Sans has loaded,
    about 4% narrow;
  - `gdl.design compare` says nothing of a panel folder with no built file or
    several, or of a page the built file lacks;
  - the map of every panel lists rows in the order first met, shows the first
    copy's control name only, and keeps a caption's line breaks;
    `verify_idmap.py` on it without `--panel` stops with a traceback.
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
- **A family whose own name ends in Regular, Bold or Italic** - Arial Rounded
  MT Bold, Britannic Bold - reads as its sibling (`Arial Rounded MT`):
  `font_resource_names()` and `Set-GdlFont` strip every trailing style word
  from the resource's name, so `donors` refuses a face the donor defines.
  Python matches the words' case and PowerShell does not. No project here
  has such a face; reading each resource's own family field would end both.
- `referenceCountField` semantics; the size-dependent vertical text residual
  (`docs/render-fidelity.md` finding 7); every text finding validated against
  one typeface.

`python tests/audit_corpus.py` checks the documented invariants against every
project it can reach; `docs/gdl-format.md` §9 has what it checks and its last
result.
