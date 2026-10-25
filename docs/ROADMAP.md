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
- **Designed on a Design canvas**: a canvas drawn with an Extron template's
  design system translates to a spec and builds (`docs/claude-design.md`).
  From prose: one conference-room brief, given to a fresh designer per theme
  with only the design system, built and verified on the TLP1035T and the 525
  beside it in all four themes, and on the 320 in Mach, Shockwave and
  Turbulence (§6).
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
3. **A Design canvas as the front end: every panel.** Afterburn's design system
   builds one canvas for every panel a room has, each sized for its physical
   screen - proven on the TLP Pro 1035, 725, 525 and 320 (`docs/claude-design.md`
   §4 and §6). Mach, Shockwave and Turbulence list every panel too - main
   region and rail read off each template's own controls, since they lay their
   bars, wells and rails as controls over photographs - with a seed for every
   series they draw (`seeds/README.md`), and each theme's huddle is built on
   the 1035, 725, 1525 and 720 and on its hubs - the 525, and Mach's and
   Shockwave's 535 - against one ID map (§6) - and in each a conference room
   drawn from prose by a fresh designer is built and verified on the 1035 and
   the 525 (§6, round three) - and on the 320, where a page goes on over
   pages of its own under the series' title strip, as Extron's own Mach 320
   spreads a room over twelve (§4, §6). What is left is in §7: a modal that
   says more than the 320's one screen, and a plain container there.
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
  The template renders and the critique loop blend instead
  (`docs/render-fidelity.md` §2).
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
- **A left `Rail` on Afterburn.** Mach, Shockwave and Turbulence have a
  `LeftRail` region (`docs/claude-design.md` §3). Afterburn's canvas has one
  Rail, the right one: side controls on the left are the Page's own, and on a
  panel with no room beside its main region they are refused, by name.
- **Afterburn's working page on the room's other panels.** Drawn at the
  template's own spacing, it does not carry to a 725, a hub or the 320: its
  `list` and `toggle` buttons are kit art, which keeps its shape as it grows
  to the touch minimum, wider than the band beside main there, and its
  popups' words stand where the 320's rows have no room - so the README's
  Afterburn example room is the 1035 alone.
- **The region frame, beyond tier A** (PR sequence in
  `docs/superpowers/specs/2026-10-22-region-frame-design.md`):
  - a region page, a source popup (`role="source"`) and a window (a modal
    with a `role` or a `title`) on a turned panel or a 300 are refused by
    name: a turned frame's header-as-left-band and the 300's menu bar are not
    drawn yet;
  - on the 320 the region page derives to the 320's pages
    (`docs/claude-design.md` §3), probed on the TLP320C and translated clean
    on the TLP320M the region canvases list - the 320C has no seed here yet
    (`seeds/README.md`; `New-GdlSeed.ps1` makes one in GUI Designer) - and
    built and verified on the TLP320M in all three themes
    (`archive/job-e823df9b/p320/`). What it does not do yet: the template puts
    no volume control on a page - Volume is the modal its program shows - so
    a 320 has no on-screen Up or Down, and Mach's modal has no Cancel, which
    the program puts away; the strip's chevrons and the volume glyphs are in
    icon faces the systems do not carry, so Back is the kit's back art
    (Shockwave's its return glyph, Turbulence's its return key at the strip's
    end) drawn across its whole key - Mach's about 1.6 times the template's
    glyph - and the Volume modal's glyphs say + and -; a page's first Back -
    to Main, which the template has none of on screen, since it chooses
    sources off it - stands where its second page's Back does, or at the
    strip's end where More holds the foot's right (Shockwave's and
    Turbulence's), the strip there as deep as Back's touch minimum, 40 to the
    template's 36; at the 320's 14 pt floor, where the template sets its
    headings at 11 to 12, a heading takes some of a column's depth - its
    words fill its box, so it cannot reach into its keys' clear tops as the
    template's does (Shockwave's keys 57 deep to its 60, Turbulence's 57 to
    its 65) - its digit keys' captions are 14 pt to the template's 18 to 22,
    and Turbulence's square key, whose wider art is too shallow to take,
    holds no word longer than about five letters - a longer one ('Normal',
    'Streaming') runs past the key's art, where the template sets its own
    words in the art or at 11 pt (whether a 320 key's caption may take the
    template's own size is the owner's call); a column heading says the
    designer's words as written, where Mach's and Shockwave's 320 templates
    capitalise theirs (ZOOM, INPUTS);
  - on a hub the region page derives to the hub's grammar
    (`docs/claude-design.md` §3) - built and verified on Mach's 525 and
    535, Shockwave's 525 and 535 and Turbulence's 525
    (`archive/job-e823df9b/hubs/`) - and what it does not do yet: the
    popups' photo and Turbulence's device pictures (below) are not yet
    built; Turbulence's settings windows' own pictures (the 525's Lighting
    Control lightbulb, Audio Control speaker and Display Control monitor)
    are an Image the designer places, which the window does not draw by
    itself; a hub's
    Display Control popup lays the LeftRail's first Section out as a row
    under its heading, where Extron's draws a card per display (Display 1
    and 2) - a canvas with two displays has no way to say so yet; a later
    Section's heading has no place among the hub's options and is named, as
    is the footer's clock; two region pages on one canvas would derive the
    same popups (Select Source, the options) on a hub, and are refused as a
    name both have; Mach's Settings popup draws a fourth tile, Recording,
    whose Main Recording page the regions do not draw. The hubs set their
    menu glyphs, their Volume Level strip's speaker glyphs and Shockwave's
    Up and Down in icon faces (Extron-Lift, Extron GUI Configurator,
    Extron-Shockwave) the design systems do not carry - fonts stay out of
    them - so the menu draws the kit's art, which fills its key where the
    template's glyph is about half the key (a kit image builds `Fill`, so a
    smaller glyph needs art drawn smaller or the face), Shockwave's Up and
    Down are Open Sans's Λ and V, and the strip's glyphs are not drawn;
    a Shockwave source whose glyph has no whole-device outline in the kit
    (blu-ray-2) keeps its tab's art on its Select a Source tile, a pressed
    tile lightens without the template's white ring, and an
    option with no glyph (Room Mode) is the kit's grey tile, which the
    template's options grid has no example of; the template sets its
    menu words at 12 to 13 pt, under the 525's 18 pt type floor, so Mach's
    Mute and Shockwave's and Turbulence's Display Control grow their cells
    inside the bar;
  - a popup in the Center's group without `role="source"` is still sized
    from main on another panel, while the Center is that panel's own region:
    it shows a little smaller or larger than its reference there (Mach 725:
    710x392 in a 710x405 region). Larger is named as a warning; only a
    popup in the Center's default group, `Sources`, is checked. A source's
    popup says `role="source"`;
  - the template's own art - Turbulence's header and footer bars (a
    stretched `image`), its source popups' device pictures (a fitted one,
    by the source's `device`) and Shockwave's and Turbulence's hub popups
    on the page's photo (a popup's `background_image`) - translates and
    checks clean on every panel the region canvases list, and is not yet
    built in GUI Designer: what the applier does with an `image` control's
    art and a popup's photo (`Apply-GdlPlan.ps1`) is pinned by text tests
    only, so a build of the Turbulence region canvas on the 1035 and the
    525 and of Shockwave's on the 525, each through `verify_built` (its
    `check_images` and the popup's photo), is the proof. A source naming no
    device the kit pictures (the region canvas's Streaming) leaves the place
    empty until it says `device`, and a device the panel's seed pictures
    for no source (a `monitor`, which only the 525's settings popups draw)
    stands at the Laptop's rect, since the frame's `center.pictures`
    measures only what the seed's own source popups picture;
  - Shockwave's own art: its seeds have no `PBImage`, so whatever art is
    its template's own is a button's. Its round art (1248x440_r_gray) is
    the kit's gray_round pixel for pixel, which the system draws; its Share
    Content is the seed's own 120x75 art with the words baked in
    (712x440_share-content_nsel, lit 712x440_stop-sharing_sel), in no kit:
    drawing it needs the two extracted from the seed - `kit.extract` takes
    every image a seed names, and the 1035 names 34 its kit does not, so a
    filter first - and a variant that draws them;
  - a source popup's controls are mapped from the drawn panel's well into
    each panel's at one scale, each grown about its centre: a column whose
    captions need more than the scaled width on the 725 comes out ragged
    (Mach's Doc Cam: Freeze 92 and Normal 101 among 76s), where the region
    rail grows a column as one; and rows the template keeps at one pitch on
    every panel overlap there - Mach's Doc Cam keys 70 apart on the 1035 come
    out 52 apart, under the 725's 60 px keys - so the canvas draws them
    100 apart, and its headings 20 px over them, where the template's
    stand 9: at the 725's 16 pt floor a heading's words grow into the key
    under it;
  - only the power-down confirmation (`topic="power"`) and the waits
    (`"up"`, `"down"`) have the template's words; a recording or incoming
    call confirmation is refused by topic until its words are measured;
  - the region page's seed IDs and mirrors (`docs/idmap.md` §7) translate
    and check clean on every panel the region canvases list, and are not yet
    built in GUI Designer: Shockwave's 1035 tab twins - a caption-only
    button inside the tab with the tab's ID, as the template draws it, the
    first spec mirror on one page - wait for a build and `verify_built` on
    the 1035, and the 1535's, which no region canvas lists, for a probe;
  - Shockwave's and Turbulence's region defaults (the profile's `regions`:
    their tabs, rail, launchers, Room Mode, Mute, Help and Power) are the
    looks those profiles measured off the 1035's seed, built and verified on
    every panel the region canvases list (`archive/job-e823df9b/center/`,
    `hubs/`, `p320/`) and set beside each template by eye, not scored
    against it;
  - Shockwave stands Audio Control in its right rail on the 1035's series
    only, and in its left rail's second group elsewhere: a RightRail
    `slot="audio"` is refused by name on a panel whose template does not
    draw it there, rather than moved to where that template does;
  - the truth ledger (`gdl/designsys/truth/`, `docs/claude-design.md` §2
    *Truth*) covers a theme once its file is there: `python -m gdl.designsys
    audit <theme>` names a theme with none, and every entry or claim not yet
    resolved. What Mach's records the system cannot draw: Open Sans Light
    (its titles, the footer clock and Main Select Source's header title are
    drawn in Open Sans at the template's size), the Extron-Lift glyph
    captions on its arrows, transport and back keys (the kit's images stand
    in), and its whole-button image presets (Window Layout, TV Channels, the
    recording layouts), which no Mach variant offers; and where it differs
    for a gate, its 30 px volume slider is drawn 53, the touch minimum.
    Where Shockwave's differs: its
    tab captions stay on the tab (above); its 52 px volume slider is drawn
    53, the touch minimum, and the Screen and Lighting tiles its template
    stands 104 apart (110 deep) stand 110 apart, since two controls may not
    overlap; and the lit caption of Room Mode VC's two choices (`action`)
    and of a blue Flash is `ink` where the template's is #474747, which a
    state's `color` sets. What Turbulence's
    records the system cannot draw: Open Sans Light (every label and
    caption, drawn in Open Sans); and
    where it differs for a gate: the 1035's 52 px volume slider is drawn 53
    (the touch minimum) and its Help 12 px in, at x 152 where the template
    has 141 (the footer opens its seam to the left rail's last launcher to
    the 2 mm gap). Privacy's red lit caption is `alert`, which a designer
    sets on its On state;
  - what Afterburn's ledger records the system does not draw: the glyphs of
    Extron's Afterburn icon font (its Close, Back, More, arrows, d-pad,
    transport and zoom keys, and the 520's and 535's triangle Up and Down),
    a font it carries none of. The kit draws most of them as images in
    Afterburn/Icons/PNG - Close's X, the chevrons, the triangles (Carets),
    minus, plus, the More dots and most of the transport keys - beside the
    Buttons/PNG the profile's kit root reads, so the `icon` list does not
    name them: wired in, as Mach's kit images stand in for its glyphs, they
    would draw a Close, a level's steps and a Group's paging as the
    template does. Until then a Close says Close, a level's steps say `-`
    and `+` and a Group pages with Previous and Next; the squircle
    card under a modal, a full-canvas `PBImage` (Help's Background), which
    the spec's `image` kind could now carry - every Afterburn seed has a
    `PBImage` - but Afterburn's system offers no Image and its modal draws
    none, so a Panel stands in; the 520's and 535's Start page on its own `_start` art, since
    every page of those panels is built on the Main art; and the 320's page
    per source, title footer and Volume modal, which only the bar themes'
    region pages build, so Afterburn's small panels re-lay a Page's controls
    in rows over a Rail. Where it differs for a gate: its 50 px volume
    slider grows to the touch minimum, and the 14 pt floor lifts its 13 pt
    captions;
  - the footer's cells the template stands together (Mach's Help and Power,
    1 px apart; Turbulence's Help and Room Mode, 2) are a `joined` set, which
    goes past the owner's call 2 as written (a header tab row and a rail
    group): the owner's word on it is awaited.
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
