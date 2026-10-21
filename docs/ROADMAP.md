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
  a real-size panel of 23 pages (`docs/from-scratch.md` §5c), clean-room
  authoring, retarget from a seed (650/650), popup canvases that keep their own
  size, and button feedback with any number of named states - authored from a
  spec, or edited state by state on an existing panel.
- **Designed in Claude Design**: a canvas drawn with an Extron template's
  design system translates to a spec and builds (`docs/claude-design.md`).
  From prose: one conference-room brief, given to a fresh designer per theme
  with only the design system, built and verified on the TLP1035T in all four
  themes, and on the 525 beside it in Afterburn (§6).
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
   Remote Desktop window open and restored, for the run - from two minutes to
   over twenty a seed, with its build (`docs/from-scratch.md` §7). Next needed
   when a job needs a panel `seeds/README.md` lists as a gap.

## Mine, in order

1. **Run the bug hunt** (`workflows/gdl-bug-hunt.js`) on a host with enough
   commit limit for the fan-out. `tests/audit_corpus.py` has done the cheap deterministic
   part; the workflow is for the judgment-heavy dimensions: collection traps,
   dead guards, silent no-ops, plan-contract drift, verifier blind spots,
   fields a clone inherits, what is secretly Afterburn-only, layout-math edges.
2. **What a real-size build spends its time on.** `examples/boardroom-full.json`,
   23 pages, builds and verifies, but Save and Build's time varied threefold
   over runs of the same spec on one host, and dropping the donor's pages did
   not decide it - though they are nearly all of a one-page panel's build
   (`docs/from-scratch.md` §5c has the runs). Where Build's time
   goes - per page, per control, per state, per resource, or what else on the
   machine - is not measured, and a designer iterating on a real panel pays it
   for each change. Those runs were made with GUI Designer in feature-flag mode,
   and one seed shows how much the host's state can matter: the Afterburn 725
   took 168 s, and 935 s made again in that mode with other work on the host
   (`docs/from-scratch.md` §7). Measure with the mode off, on a quiet host,
   with and without real-time scanning of the files a build writes, first.
3. **Claude Design as the front end: every panel.** Afterburn's design system
   builds one canvas for every panel a room has, each sized for its physical
   screen - proven on the TLP Pro 1035, 725, 525 and 320 (`docs/claude-design.md`
   §4 and §6). Mach, Shockwave and Turbulence list every panel too - main
   region and rail read off each template's own controls, since they lay their
   bars, wells and rails as controls over photographs - with a seed for every
   series they draw (`seeds/README.md`), and each theme's huddle is built on
   the 1035, 725, 1525 and 720 and on its hubs - the 525, and Mach's and
   Shockwave's 535 - against one ID map (§6) - and in each a conference room
   drawn from prose by a fresh designer is built and verified on the 1035 and
   the 525 (§6, round three). What is left, first, is **their 320s**.
   The huddle canvases are refused there, by name (§7): the page's controls,
   stacked in rows, need 285-482 px of its 240. Next: a rule for what a bar
   theme's page becomes on a screen that holds a few rows. Extron's own Mach
   320 spreads a room over twelve pages, each source a page of its own under
   a 36 px title strip, with volume a level in a popup.
   800x480 is two series in all three themes - the 520, tier B, and the 720,
   tier A, which take different layouts - where Afterburn has only the 520.
   Design and phases: `docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md`.
   A native-size seed beats a retarget, which matches Extron's own hand layout
   for only 22% of controls. The other gaps in `seeds/README.md` (Teams Rooms,
   Zoom Rooms, Afterburn's 1520 and 535) wait for a job that needs one.
4. **Retire the client fixtures.** `fixtures/` is a real client's project,
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
- **A seed of a panel's other form.** `seeds/` holds one form per size - the
  725T, 525T, 320M, 1535M - so a TLP725M, 725C, 525M, 525C, 320C or 1535T spec
  has no seed, and is refused the other form's rather than built as it
  (`seeds/README.md`). `gdl.seeds pick` prints the `New-GdlSeed.ps1` line for
  the form's own (`Afterburn TLP725M.gdl`); none has been made, so the wizard's
  name for each form's panel type, as `seeds.panel_type()` spells it, is unproven.
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
- **`gdl.compose` draws a face in the build it finds, not the panel's.** A face
  is resolved by family, so a panel on the Afterburn 320, 525, 725 or 300M
  Portrait seed previews its icons in the kit's Extron-Afterburn, 6% of an em
  lower than the build it embeds draws them (`docs/design-rules.md` §6).
  Drawing each panel's own needs the face its project carries
  (`gdl.fonts.carried`), which the compositor does not read.
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
- **A left `Rail`.** A canvas has one Rail, the right one. Side controls on the
  left are the Page's own - through the left band where the template draws
  its bars as controls, with the page otherwise - and on a panel with no room
  beside its main region they are refused, by name.
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
