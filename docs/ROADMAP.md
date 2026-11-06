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
  beside it in all four themes, and on the 320 in all four (§6).
- **What the controls do**, from the same spec: `gdl.idmap` checks the page
  flips and writes the programmer's ID map, verified against the built panel
  (`New-GdlPanel.ps1 -IdMap`). Generated panels boot to their own start page and
  keep modal popups modal. A revised canvas keeps every ID the program uses,
  those in a hub window its pages' order renamed too, and says what changed
  (`--previous`, `docs/idmap.md` §9). `docs/idmap.md`.
- For test results and branch or PR state, run `python -m pytest`, `git` and
  `gh` — a snapshot written into a doc is stale the next time anything merges.
  Setting up a machine is in `README.md` *Setup*.

## Yours

1. **Keep the Windows session connected while seeds are made.**
   `powershell/New-GdlSeed.ps1` clicks through GUI Designer's Project Create
   Wizard, which draws nothing in a locked or disconnected session, so the
   script refuses rather than click blind. Sign in at the console, or keep a
   Remote Desktop window open and restored, for the run - from under three
   minutes to three-quarters of an hour a seed, with its build
   (`docs/from-scratch.md` §7). Next needed when a job needs a panel
   `seeds/README.md` lists as a gap.
2. **Confirm or overrule where a mic mute and a display's state go.** Round
   four's brief asks for both, and each designer's notes show a place of their
   own for each - the footer's mode slot, the RightRail's audio slot, a rail
   dock, a status Label in the header. Assumed, until you say otherwise: follow the template's own
   places, and where it has none give the README a recipe in its grammar and
   draw no region of our own. So a mic's Mute is in the audio window, as the
   template's Mic column (Mic 4050, its level 9018, Mute 9017), and a
   display's state is its On and Off keys' `states` - Warming Up and Cooling
   Down as their own `text` - since no template page draws a status field
   (`docs/claude-design.md` §4, each theme's README *The working page*, the
   ledgers' entries). Overruled, a slot for either is a region's to draw.
   Round five's brief added three more each designer improvised, assumed the
   same way: two displays a key each in the first Section, its states the
   display's and its `display` naming it, with which source each shows a
   source popup's Group; a disc player's transport a Group of the kit's
   transport glyphs, or of worded keys in two rows where the kit has none; and
   a recording's state its launcher's lit state, the question before it stops
   a plain modal the designer draws, since no template asks one.
3. **Confirm or overrule the ten assumptions Afterburn's regions are built
   on** (`docs/superpowers/specs/2026-10-26-afterburn-regions-design.md` §7,
   each taken at its recommended answer, §8): (1) the same component names on
   Afterburn - Header, LeftRail, Section, RightRail, Footer, Center; (2) a
   725 rail as full as the template's own closes up and lifts, refused only
   past what the README's left-rail table says it holds; (3) more Sections
   than Main SD draws, each a seam under the one above; (4) the kit's icons
   drawn fitted to their buttons, Close 41 px where the glyph is 27; (5) a
   Group's Previous and Next the kit's chevrons; (6) the 520's Select a
   Source tiles its seed's own extracted art, orange scheme only - the seed
   draws them in orange alone - and the `source` tile in the other schemes
   and where it has none; (7) Start a region page measured off the template's Start, going on
   by More on the 320 - not built: its stage waits for your word, and Start
   stays a page without regions; (8) the mode launcher keeps 8120 and the
   525's derived Volume Up takes a fresh ID; (9) a display's state kept in
   Power's states and the toggle's own switch art, Power in every state, a
   mic's Mute an uncaptioned icon key - and on the 320, whose keys draw no
   switch, each middle state its name; (10) a toggle holds one short word,
   a longer one named with the room it has. Overruled, each is the region
   code's and the README's to change.

4. **Load a built panel onto a touch panel.** No load is recorded: the proof
   ends at the built file and its artwork (*Where things stand*), so what a
   panel's firmware draws from `layout.json` - live captions, translucent
   fills, a held button - has not been seen on hardware: GUI Designer's
   snapshot blends a translucent fill in light, and the picture of the panel
   blends it plainly (`docs/render-fidelity.md` §2), and which the panel does
   is unknown. Needs a panel, and a person to read it.
5. **Decide whether to exclude GUI Designer's folders from real-time
   scanning, and run the build timing once with it set.** A build holds the
   antivirus engine at one whole core while GUI Designer uses a sixth of one
   (`docs/from-scratch.md` §5c). Which folders, and the commands to time the
   effect, are in *Mine*, item 1; an exclusion lets those files go unscanned,
   so it is yours to weigh and to set.
6. **Confirm or overrule the 300's four assumptions, and say whether a
   turned panel should have a region grammar of ours** (region-frame spec
   item 14). The 300 draws a region page as its template does, and where the
   template has no answer: (1) its Main holds the template's two source keys,
   and more go on over pages of Main's own by a More in the second's place,
   and a page that goes on stands a More in its bar's last place - no 300
   template pages anything, so both pagers are ours; (2) Afterburn's 300
   Landscape sets a page's title in its column's foot, 79 px across, where at
   the 300's 16 pt floor about six letters fit - its template sets 14 pt and
   shortens Computer to Comp. - so a longer title, and a source's name used
   as one, is refused by name; (3) a 300's derived chrome keeps its own
   template's seed IDs (Main's title 6072, Back 8041), a 320's its own (6075,
   8011, More 8010), so on a canvas listing both, those controls take IDs from
   50001 on both; (4) the template's Settings is a plain list of key pages,
   so the pages Settings goes on to on Main's own (`Main 3` and on) - the
   LeftRail's Sections as columns under their headings, Room Mode, an Audio
   Control and the Header's ends - are ours: the template has no such page.
   Overruled, each is the 300's code's and its README's to change. And turned panels: Extron draws no bar or hub template turned -
   its one turned template is the 300 Landscape - so a region page, a source
   popup and a window on a 1035M or 835M portrait, or a 520M, 521M or 535M
   turned, or Mach's 300M landscape, are refused by name. Drawing one needs a
   grammar no template measures: turned, Mach's 1220 header is a 64 px band
   down the left, whose tabs hold a caption of four letters or so at the
   1035's 14 pt floor (Help fits, Laptop does not), and its footer a 55 px
   band down the right, which holds neither its clock nor Room Mode. Yours
   to ask for, and to shape.
7. **Say whether a 300 key's caption may go down to its template's size, as
   you let a 320's.** Your call of 2026-11-04 covered the 320 only. We
   carried it to the 300 by analogy, where its template sets its keys' words
   under 14 pt: Afterburn's 300 draws its keys of words at 13 pt, the least
   its Display Settings - the page its columns are read off - sets them in,
   and its spec says `"type_floor": {"button": 13}`, where the 300's own
   floor is 16. Mach's 300 sets its keys at 15, under 16 but not under 14,
   and is untouched. Its template is not one size: Recording Controls' keys
   are 10.5 and the Landscape's Main sources 12 (`docs/design-rules.md` §1).
   Overruled, Afterburn's 300 keys go back to the 16 pt floor, where the
   Landscape's Settings says Setup in its 88 px column, and `key_floor` is
   the 320's alone (`gdl.designsys.models`).

## Mine, in order

The order these and the backlog below are worked in, as pull requests, and
where each runs: `docs/superpowers/plans/2026-10-26-backlog-plan.md`.

1. **A real-size build with real-time scanning off.** Where Save and Build's
   time goes is measured, with the mode on as the owner keeps it and Windows
   Defender's real-time scanning as it is (`docs/from-scratch.md` §5c): about 2 s
   a control, 2 s a distinct image, nothing for a page past its controls, a
   border or a face; a spread that is the processor's clock, 3.1 GHz or about
   1.1; and one whole core of the antivirus engine for the whole of every
   build against a sixth of one for GUI Designer. What is left is the half
   that needs the owner, and is theirs to decide because it lets files go
   unscanned: **a Defender exclusion** (Windows Security > Virus & threat
   protection > Manage settings > Exclusions). A file-system watcher on the
   base spec's build (`archive/job-e823df9b/build-timing/runs/x4-probe-files.files.tsv`)
   saw GUI Designer write in `%TEMP%`, in `C:\ProgramData\Extron\Temp`, in the
   folder the project is built in (`C:\gdlwork` by default) and in
   `%LOCALAPPDATA%\Extron`; it creates only a few dozen files there, so whether
   the engine's core is scanning those or watching GUI Designer's memory and
   behavior a folder exclusion does not say. To find out: exclude those four
   folders (`%TEMP%` is every program's, so that one is the wider exclusion);
   build the base twice; then add the process
   `C:\Program Files (x86)\Extron\GUI Designer\GUI Designer.exe` and build it
   twice more. `python tools/build_timing_specs.py <dir> --name base` writes
   the base spec; a queue is a tab-separated line a build - an id, the spec's
   path, and `0` - and `powershell -NoProfile -File tools\Run-BuildTiming.ps1
   -Queue <queue> -OutDir <dir>` builds it; `python tools/timing_table.py <dir>`
   reads the clock and the time beside each other, against the 371 s the base
   takes at the full clock with scanning on. If the engine's core was what GUI
   Designer waited on, the build falls toward its own sixth of a core, and the
   exclusion's worth is that ratio. Also open: what holds the clock down in
   one build of about twenty, which the operating system's counters do not
   show. The mode-off half is not planned - the owner keeps the mode on.
2. **A Design canvas as the front end: every panel.** Afterburn's design system
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
   spreads a room over twelve (§4, §6). Round four's rooms, drawn for the
   1035, 725, 525 and 320 from the region-frame READMEs, are translated and
   what each designer still has to fix is named (§6, spec item 10): revised
   from the new READMEs, they are built and verified on all sixteen panels.
   Their call pages, sources, mic mutes and display states, which every
   designer improvised, are now the template's (spec item 11): redrawn so,
   Mach's, Shockwave's and Turbulence's translate clean on all four panels.
   What is left is in §7: a plain container on the 320, a Group's `icon` on
   the buttons of the region a mid-size panel's Groups share, a left Rail on
   Afterburn, and the region frame's gaps below. A plain modal that says more
   than the 320's one screen goes on over modals of its own, and a Clock on
   Shockwave's and Turbulence's 320 is cloned from the theme's 525, each built
   and verified there (`archive/job-e823df9b/small-panels/`). Round five's
   training room, drawn for the same four panels on a harder brief, was
   refused at first and is left only what its designer would now revise from
   the README, and one limit (§6, spec item 13).
   800x480 is two series in all three themes - the 520, tier B, and the 720,
   tier A, which take different layouts - where Afterburn has only the 520.
   Design and phases: `docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md`.
   A native-size seed beats a retarget, which matches Extron's own hand layout
   for only 22% of controls. The other gaps in `seeds/README.md` (Teams Rooms,
   Zoom Rooms and the turned panels its *Gaps* lists) wait for a job that needs
   one.

## Backlog - real, not urgent

- **A Label over a row of keys does not move apart from them** as they grow,
  in a window or a plain modal. A window's body, a source popup's well and a
  plain modal's card re-space a row, or a stack, whose members came nearer
  than they may (bundle.js `freeLayout`), but a Label standing over two keys
  side by side is neither. Round five's Turbulence stop question showed it -
  its Stop Recording key grown from 92 to 192 px deep on the 525 ran up into
  its question's words; its two keys now come out one size, 125x131, its words
  on two lines (`artRows`, `twoLineNeed`), and clear of them, so no canvas here
  shows it. Needs the rows below a heading re-spaced as one block of its column.
- **Segoe UI, Segoe UI Semibold and FluentSystemIcons-Regular preview in
  Arial**, said aloud (`gdl.design compare` and `gdl.spec render` print
  `compose.FALLBACKS`): Extron's templates carry them and no seed does, so
  there is nowhere to read them from (`gdl/fonts/README.md`). Roboto, Extron
  GUI Configurator and GUIC Video Conference 1a are read from the seed that
  carries them.

- **The Offline Page's words, not its layout.** A spec switches GUI Designer's
  Offline Page on or off and replaces words on it (`offline`, built and
  verified on 1.28.0.7 - `docs/gdl-format.md` §7), but the page stays the
  seed's: one or two labels where the seed puts them, in its type and colors.
  A Design canvas cannot draw the page, nor does the translator say
  `offline` - a panel translated from a canvas ships its seed's
  switch, so the panels of one canvas can differ (Shockwave's 525 on, its 1035
  off), and `gdl.spec donors` says which way each ships it.
- **A popup's auto-hide timeout is unreachable.** `PBPopupPage.timeoutField` is
  authored (`timeout`) and kept by Save and Build, but nothing in GUI Designer
  1.28.0.7 reads it and `layout.json` has no timeout, so no build can give a
  panel one (`docs/gdl-format.md` §7). Extron's to change; until then the
  program hides a timed popup. A version that exports the field would show it
  in `layout.json`.
- **The hubs' Volume Level strip is still bound to a group of its own.** A
  spec binds a reference to one popup by its ID as the seeds bind theirs
  (`popup`, built and verified on 1.28.0.7 - `docs/gdl-format.md` §5), but the
  design systems' hubs (`gdl/designsys/bundle.js`) still give the strip a group
  of its own, so every theme's hub shows it on every working page where its
  template shows it only when the program does - each README's *Differences*
  says so (the ledgers' `afterburn-45`, `mach-54`, `shockwave-44`,
  `turbulence-47`). Emitting it bound by its ID changes the four ledgers and
  needs the hubs rebuilt.
- **A seed of the forms still missing.** `seeds/` holds a seed of each form
  of the 320, 520, 521, 525, 526, 535, 720, 725, 726, 835, 1020, 1022, 1025,
  1026, 1220, 1225, 1520, 1525, 1535, 1720 and 1725 in every theme that draws it
  (backlog plan 2.6; `gdl.seeds pick` finds each by its part number, and the
  profiles list them), and the 835M turned to portrait in each. What it finds
  none for is in `seeds/README.md` *Gaps*: Teams Rooms, Zoom Rooms at 725 and
  986x740, and the panels turned where no template is drawn that way up other
  than those - the 520M, 521M and 535M, and the 1035M outside Afterburn - whose
  own seed is here, so `New-GdlTurnedSeed.ps1` makes each in a run.
- **Afterburn's Level is one width in its profile, and its 535 seed draws it wider.**
  `defaults.level.track` is 15 px for every series; the 320, 525 and 300 seeds draw
  their Level 15 across and the 535 seed 24 (its DPI is 294, against their 113 to
  188), so a Level drawn on a 535 is narrower than the template's own.
  `tests/test_designsys.py` pins both widths.
- **A Group's title in capitals on the 320 is extrapolated.** Mach's and
  Shockwave's 320 seeds set only their camera column labels in capitals (ZOOM,
  FOCUS, INPUTS, IRIS); `writing.column_labels_320` applies it to every Group
  title there, PRESETS and DISPLAY included, which no seed shows. Afterburn's
  320 seed uses capitals too, but its translation draws no Group heading there.
  Not an Extron requirement (`docs/design-rules.md` keeps extrapolated rules apart).
- The preview draws a border's corner as a circle of its
  radius, where Build's is a little rounder - up to 3 px further in along the
  diagonal at radius 100, 0.0% to 3.2% of a 360x260 panel's pixels
  (`docs/from-scratch.md` §5, test 3); a render change, so `tests/score.py`
  before and after.
- **A border the donor lacks is built as its nearest** (`nearest_border`),
  though a resource appended at the asked geometry builds and rasterizes as
  asked (`docs/from-scratch.md` §5, tests 2 and 3). Appending it - as
  `examples/probes-128/Add-BorderResources.ps1` does by hand - would end the
  swap and the refusal of a border with no shape near enough; applier work,
  with a build to show it.
- **The spec preview draws a level whose art the donor keeps as its bare
  bar** (`keep_art`: Shockwave's and Turbulence's volume levels), where Build
  draws the donor's track and fill. It is most of what differs between the
  preview and the build (`docs/from-scratch.md` §6) - all of the worst popup,
  15.85%. The preview knows no donor, so it needs the theme's own level art.
- **The profiles count a template message's lines in its whole box**
  (`tests/measure_series.py` `_lines`, each window frame's `lines`), where
  GUI Designer wraps it in the box less 1/6 em a side and trims what is too
  deep (`docs/render-fidelity.md` §9). A message within that of its box's
  width counts a line short. Measuring them again with `gdl.compose.fitted`
  in the padded box moves design-system data, so it is its own change, with
  the canvases it reaches rebuilt.
- **How much of a caption's last line GUI Designer needs in its box to show
  it is not pinned**: between 17% and 68% of its height, on the one caption
  either side the synthetic fixture has, and `gdl.compose.TRIM_LINE` assumes
  half (`docs/render-fidelity.md` §9). A caption in a box 1.3 to 1.6 lines
  deep, built and snapshot, would settle it - a rebuild of the fixture.
- **Three things the synthetic fixture's first build failed on**, each taken
  out of its spec so it builds and verifies (`tests/data/synthetic/make_synthetic.py`
  says where):
  - A button on **3D Gradient**, a built-in border the seeds define (`gradient`),
    builds right and fails `tests/verify_built.py`: Build draws the fill as a
    gradient, so the planned #37394E is none of the art (mostly #1A1B26, 1%).
    The fill check needs the gradient's model, or the border refused.
  - A **rail of art on an Afterburn slider**: its `track_image` built, its
    `fill_image` came back as the clone's own #BABCCE bar, which the verifier
    caught. Rails of art are proven on Shockwave's seed only (the format
    probes, 2.1); Afterburn's slider draws its fill another way.
  - A **1 px line** through the middle of an even-height box builds half on
    each of two rows, at alpha 128 at most - a faint double line where the
    preview draws one solid, and see-through to the verifier. Nothing says so
    before the build.
- **A horizontal Shockwave slider's thumb is the vertical one squeezed.**
  Build stretches a thumb's kit art into its box unturned, so on a slider
  lying right or left Shockwave's 156x102 thumb is squeezed into 34x52, the
  wide art made tall (`tests/verify_built.py` `check_thumbs`). The kit carries
  a thumb drawn for it, `Shockwave/Slider/90x156_sw_horizontal_thumb.png`,
  which no template and nothing here uses; a profile could name it for a
  slider lying right or left (`defaults.slider`). The rail is right as it
  is: Build turns its art to lie as the slider does. A slider whose
  orientation is `down` was never built, and `verify_built` draws its rail
  as `up`'s.
- **The tier B hub a page's Groups share holds only a `MainArea`'s.** On a
  mid-size panel (the 525) the Groups of a page's `MainArea` share one region
  where they stood, switched by a rail of a button per Group
  (`docs/claude-design.md` §4) - built and verified, its region's popups each
  a different Group's (`tests/data/design-groups`' Groups board on the
  TLP1035T, 725T, 525T and 320M, `archive/job-e823df9b/hub-grammar/`). Groups
  standing elsewhere on the page - the Page's own children, a
  Group in a plain container - each keep their own box, as do Groups with
  another of the main area's controls in their bounds or grown into the
  region (named, a warning); Groups whose popups would share a name are
  refused by name.
  Its rail's buttons carry each Group's title and not its `icon`, which
  the 320's button carries.
- **Afterburn's hub tiles in its 520 seed's own art are not built.** Its
  region pages are built and verified on the 1035, 725, 525 and 320
  (`archive/job-e823df9b/afterburn-regions/`, `docs/claude-design.md` §6),
  but those rooms are blue-slate, so the 525's Select a Source drew the
  fitted `source` tiles: the seed's extracted 756x688 tiles, which only the
  orange scheme draws (`kit.extract`), want an orange room built on the 525
  after `python -m gdl.designsys extract afterburn` on that host, and
  `verify_built` at 0 there.
- **Afterburn's page without regions on the 320 does not go on.** A region
  page goes on over pages of its own by its foot strip's More and Back, as
  its template does (`docs/claude-design.md` §4). A Page without regions is
  still its own controls and its MainArea's in one set of rows in main, over
  the row the Rail runs across the foot, and one past the 186 px main holds
  is refused, by name: the Rail's row holds the volume and three, which
  leaves no room for More and Back beside them.
- **The region frame, beyond tier A** (PR sequence in
  `docs/superpowers/specs/2026-10-22-region-frame-design.md`):
  - on the 300 the region page derives to the 300's pages, under its menu bar
    (`docs/claude-design.md` §3, spec item 14) - Mach's 300 and Afterburn's 300
    Portrait and 300 Landscape - and Mach's and Afterburn's region canvases
    translate clean on the TLP300M beside the 1035, their ID maps too, and
    Afterburn's on its TLP300M-Landscape with titles its column holds;
    Afterburn's 300 draws its keys of words at 13 pt, the least its Display
    Settings sets them in, under 14 as Mach's 15 is not - the 320's rule
    carried over by analogy, ours and pending the owner (*Yours* item 7,
    `docs/design-rules.md` §1); `tests/data/design-300-afterburn`, the
    region canvas listing the TLP300M beside the 1035, is the canvas to build
    that on, its key floor and its bar's seed IDs translated and checked
    clean, its ID map too, and built in GUI Designer on the TLP1035T and the
    TLP300M and verified, both at 0 problems and their ID map at 0
    (`archive/job-e823df9b/rebuild-1104/`); GUI Designer's own snapshot of
    the 300's Main draws its bar keys, its Volume key and its Down and Up in
    Extron-Afterburn (`glyphs/`). Mach's 300 is not built, nor Mach's level
    glyphs (Extron-Lift) on any panel. What it does not do yet: Mach's level
    stands on the photo, its glyphs at its ends, where its template shows it
    in a Volume Level popup; and what *Yours* item 6 asks;
  - a region page, a source popup (`role="source"`) and a window (a modal
    with a `role` or a `title`) on a turned panel are refused by name: no
    template of the theme is drawn that way up - Extron's one turned
    template, Afterburn's 300 Landscape, is a series of its own, and turns
    its Main as `models()` turns a frame but stands its other pages' bar down
    the opposite side (`tests/test_measure_series.py`); a grammar of our own
    is *Yours* item 6;
  - on the 320 the region page derives to the 320's pages
    (`docs/claude-design.md` §3), probed on the TLP320C and translated clean
    on the TLP320M the region canvases list - the 320C's seed is here in each
    theme now (`seeds/README.md`), and no region page has been built on it - and
    built and verified on the TLP320M in all three themes
    (`archive/job-e823df9b/p320/`). What it does not do yet: the template puts
    no volume control on a page - Volume is the modal its program shows - so
    a 320 has no on-screen Up or Down, and Mach's modal has no Cancel, which
    the program puts away; the strip's chevrons and the Volume modal's glyphs are
    drawn in the template's icon faces, where the machine that builds the
    system carries them (`docs/claude-design.md` §2), translated, checked
    clean, and built and verified on every TLP320M spec they changed
    (`archive/job-e823df9b/rebuild-1104/`; the Afterburn 320's Privacy key,
    stopped by a limit of the verifier since fixed, verified again at 0) -
    Turbulence's Back
    and More are the kit's own keys, as its template's are; a page's first Back -
    to Main, which the template has none of on screen, since it chooses
    sources off it - stands where its second page's Back does, or at the
    strip's end where More holds the foot's right (Shockwave's and
    Turbulence's), the strip there as deep as Back's touch minimum, 40 to the
    template's 36; at the 320's 14 pt floor, where the template sets its
    headings at 11 to 12, a heading takes some of a column's depth - its
    words fill its box, so it cannot reach into its keys' clear tops as the
    template's does (Shockwave's keys 57 deep to its 60, Turbulence's 57 to
    its 65); a key's caption takes the size its template sets that kind of
    key in - a key of digits or signs its Doc Cam Inputs' 18, 22 and 11 pt
    on Mach's, Shockwave's and Afterburn's, the question's answers its own
    question's 11, 12 and 10, a key of words 10 (Freeze, Auto and Normal) -
    going down to fit no further than that 10 (the owner's call, 2026-11-04,
    `docs/design-rules.md` §1), and a key the designer gave a `size` keeps
    it, at the 14 pt floor, where its words fit, translated, checked
    clean, and built and verified on every TLP320M spec it changed
    (`archive/job-e823df9b/rebuild-1104/`); Start's key does not yet,
    though its templates set it at 16, 20 and 12 pt: it is a key of words
    on the designer's own Start
    page at 10, where the 320 cannot yet tell it from another drawn beside it
    (round five's Mach Start holds Lighting too), and at the template's size
    the two would not fit across - which wants a Start page laid out as the
    template's, or a key's words pushed down to fit wherever it grows;
    and Turbulence's, whose template sets its keys' words in their art and
    so measures no size of its own, keeps 14: its square key, whose wider
    art is too shallow to take, holds no word longer than about five
    letters - a longer one ('Normal', 'Streaming') runs past the key's art,
    where the template's words are the art's;
  - on a hub the region page derives to the hub's grammar
    (`docs/claude-design.md` §3) - built and verified on Mach's 525 and
    535, Shockwave's 525 and 535 and Turbulence's 525
    (`archive/job-e823df9b/hubs/`); the popups' photo and Turbulence's
    device pictures (below) are built (`archive/job-e823df9b/seed-art/`);
    each settings popup's own picture (Turbulence 525's Lighting
    lightbulb, Audio speaker and Display Control monitor, drawn by the
    window), a card per display in the Display Control where the first
    Section's buttons say which display each drives (`display`), and a
    later Section's heading's words as the options' title (which keeps its
    name, so its ID) are built and verified: the region and call canvases
    they change, built again on the hubs (`archive/job-e823df9b/hub-grammar/`),
    and the display cards in round five's Afterburn room
    (`archive/job-e823df9b/round5/`); the footer's clock is named and left, since
    each hub template draws its clock on its Start page alone.
    What it does not do yet: a two-display Section on a bar panel stands
    down its rail as any Section does, and of six keys (three a display)
    with the launchers under them, Mach's 725, Shockwave's 1035 and 725 and
    Turbulence's 1035 and 725 hold fewer, each refused by name - their
    templates' answer, a Display Control modal the rail opens, is a settings
    window the hub draws as any, not as cards; two region pages on one canvas derive the
    same popups (Select Source, the options) on a hub once, and rename what
    differs (`_one_name_each`); Mach's Settings popup draws a fourth tile, Recording,
    whose Main Recording page the regions do not draw - the recording's
    question is drawn now, but not the working page its tile opens, a page
    of its own grammar (its record status in the left rail, Recording
    Controls at the foot), which is more than the question's measurement
    gives. The hubs'
    menu glyphs, Close and Volume Level strip glyphs - Mach's Extron-Lift,
    Shockwave's Extron-Shockwave Up and Down and Extron GUI Configurator
    strip, Afterburn's icon font's carets and Back - are drawn in those faces
    where the machine that builds the system carries them, translated,
    checked clean, and built and verified on the region and call canvases,
    and drawn in GUI Designer's own snapshot of Mach's, Shockwave's and
    Afterburn's 525 Main (`archive/job-e823df9b/rebuild-1104/glyphs/`); a
    Shockwave source whose glyph has no whole-device outline in the kit
    (blu-ray-2) keeps its tab's art on its Select a Source tile, a pressed
    tile lightens without the template's white ring, and an
    option with no glyph (Room Mode) is the kit's grey tile, which the
    template's options grid has no example of; options past what their
    popup holds go on over pages of it by a More and a Back tile, the 320's
    words on the blank tile - no hub template pages its options, so the
    pager is the toolkit's, translated (`tests/test_design.py`'s hub
    classes) and not built; the template sets its
    menu words at 12 to 13 pt, under the 525's 18 pt type floor, so Mach's
    Mute and Shockwave's and Turbulence's Display Control grow their cells
    inside the bar;
  - a popup in the Center's group without `role="source"` is still sized
    from main on another panel, while the Center is that panel's own region:
    it shows a little smaller or larger than its reference there (Mach 725:
    710x392 in a 710x405 region). Every grouped popup with no role is named
    as a warning where it differs from the region by more than 2 px, either
    way, in any group - a popup is laid out on its own board and cannot read
    which group the Page's Center shows, so a popup in another group is named
    too, and the warning says to ignore it if it is not the Center's. A
    source's popup says `role="source"`, and is the region on every panel;
  - the template's own art - Turbulence's header and footer bars (a
    stretched `image`), its source popups' device pictures (a fitted one,
    by the source's `device`) and Shockwave's and Turbulence's hub popups
    on the page's photo (a popup's `background_image`) - translates and
    checks clean on every panel the region canvases list, and is built and
    verified in GUI Designer (`archive/job-e823df9b/seed-art/`: Turbulence's
    on the 1035, 725, 525 and 320M, Shockwave's on all five panels, and
    again in round four). A source naming no
    device the kit pictures (the region canvas's Streaming) leaves the place
    empty until it says `device`, and a device the panel's seed pictures
    for no source (a `monitor`, which only the 525's settings popups draw)
    stands at the Laptop's rect, since the frame's `center.pictures`
    measures only what the seed's own source popups picture;
  - Shockwave's own art: its seeds have no `PBImage`, so whatever art is
    its template's own is a button's. Its round art (1248x440_r_gray) is
    the kit's gray_round pixel for pixel, which the system draws; its Share
    Content is the seed's own 120x75 art with the words baked in
    (712x440_share-content_nsel, lit 712x440_stop-sharing_sel), in no kit,
    which `python -m gdl.designsys extract shockwave` takes from the seed
    (`kit.extract.only`, the two alone) and its `share` variant draws at a
    call page's header end - built and verified in round four's Shockwave
    call room (`tests/data/round4-shockwave-call`) on all four panels;
  - the power-down confirmation (`topic="power"`), the incoming call's
    question (`"call"`), a recording's (`"recording"`) and the waits
    (`"up"`, `"down"`) have the template's words; a recording's stands in
    its own window, measured off each series' seed (Afterburn's and Mach's
    bar series, hubs and Afterburn's 300 Landscape), built and verified on
    Mach's 1035 and 525 and Afterburn's 1035
    (`archive/job-e823df9b/small-panels/recording/`), and is refused by name
    on the 320, whose template asks none and whose power-down box cannot
    hold its words. A room-mode question is still refused by topic: its
    words and places are measured - Mach's, Shockwave's and Turbulence's
    Room Mode VC page, 'Please select a room mode.' over Presentation and
    Video Conference (Turbulence's 'Presentation Mode' and 'Video Conference
    Mode'), in `recording/questions.json` - but the template draws it as a
    page, not a modal question, and its two choices in looks of its own (Mach's
    shade keys, Shockwave's and Turbulence's kit art) that no profile has yet,
    so drawing it needs those looks measured into each profile's
    `regions.window`, a `windows.mode` record per series and the choices'
    seed IDs (8254, 8255); until then a canvas draws the template's mode
    chooser as a splash page (the README's *Pages without regions*);
  - the call mode - a call page (`role="call"`, Main VC), its dialer
    (`role="dialer"`) and the incoming call's question (`topic="call"`) -
    and the page sources are chosen on (`role="select"`, Main Select
    Source) translate and check clean, their ID maps too, on the TLP1035T,
    725T, 525T and 320M in all three themes (`tests/data/design-call-<theme>`)
    and in round four's rooms redrawn so (`tests/data/round4-<theme>-call`).
    Those rooms and those canvases were each built in GUI Designer and
    verified on every panel, their ID maps too, in a first pass
    (`archive/job-e823df9b/call/first-*`). After the call mode's review the
    panels its fixes change were built again at 6111a7f and verified there
    (`second-*`): all four panels of each theme's design-call canvas, Mach's
    and Shockwave's round-four rooms on the 1035, 725 and 525, Turbulence's on
    the 525. Mach's six on the 1035, 725 and 525 were
    re-verified with the fixed verifier against those builds
    (`reverify-mach.log`). The panels not rebuilt keep their first-pass
    builds, whose specs the fixes do not change. Afterburn's review then gave a
    hub's menu bar one ID per key on every working page, and every call room
    whose hub draws two working pages was built again and verified on the
    panels that changes (`archive/job-e823df9b/afterburn-regions/rebuild/`).
    The call keys' lit captions and words past the glyph (below) were built
    and verified where they change what a panel builds: Shockwave's design
    call and both its round-four rooms on all four panels, Mach's design call
    on the 1035 and the 725 (`archive/job-e823df9b/call-cosmetics/`).
    A key whose template sets its words past its glyph (the dialer's Call
    and Flash, Mach's Contacts, Shockwave's incoming answers) takes them the
    gap its panel's template leaves between the kit's glyph and the first
    letter - measured per key and panel off the seeds (the frame's `gap`;
    the 1035's Shockwave Call 24 px, Flash 20, Accept Call 18, Ignore Call
    25), to the nearest space and never closer than 4 px or the gap measured, if
    that is less (Mach's Contacts, 0 to 3) - and the Header's
    tabs and a key whose template sets none take 4 px; a lit caption is its
    icon's color's dark on every Shockwave variant, as its template's are.
    Both build differently from the passes above, and every call canvas -
    the three `design-call-<theme>` and round four's three call rooms - was
    built again at main 0aeccf7 on all four panels and verified there
    (`archive/job-e823df9b/rebuild-1104/`).
    An incoming call's answers keep the template's 9032 and 9033 on every
    panel, and Turbulence's Select a Source tiles their tabs' IDs, as their
    templates give them (the owner's call, 2026-11-04; `docs/idmap.md` §7):
    translated, checked clean and mapped on every panel the three
    `design-call-<theme>` canvases list - and on a TLP300M added to Mach's -
    and built and verified on every panel those canvases list, their ID maps
    at 0 (the TLP300M added to Mach's is not built).
    What it does not do yet: Mach's Share Content
    says Share, and Shockwave's 725 call page holds two of its
    Main VC's three launchers (Differences) - it has not the room the
    template gives a third, which at the template's 98 px would end 27 px
    past the rail's foot under the VTC pills grown to the 725's touch
    minimum (`archive/job-e823df9b/small-panels/launchers-725/`); on a hub
    and the 320, which draw no dialer of their template's, the dialer's
    Call, Flash and Contacts say their words on the key, Mach's without
    their 880x440 art; a hub draws a
    call page's keys as a popup named for its Section's title, shown first,
    and leaves its bar's Display Control off that page, whose first Section
    is no display's - no hub template draws a call; the 320 shows a call page's
    Select a Source keys first and its call keys on Main's later pages, and
    pages the dialer over four, no page holding one control alone where there
    are two to a page; what
    Share Content opens (Mach's 'Select a source to share', Shockwave's and
    Turbulence's Main VC Share Content) is the designer's to draw; and a
    room with more sources than a Header holds is refused on Shockwave's bar
    panels, whose templates draw no Main Select Source, with fewer tabs and a
    source popup of keys as the remedy;
  - the glyphs the templates set in Extron's icon faces - a hub's menu,
    Close and Volume Level glyphs, the 320's More, Back and Volume glyphs,
    Afterburn's window Close, Shockwave's dialer star and Turbulence's
    keyboard key - and Open Sans Light where the templates set it (Mach's
    and Turbulence's bar series; `docs/claude-design.md` §2) translate and
    check clean, the donor check too, on every panel the region and call
    canvases list, and are built and verified (`verify_built`'s caption and
    font checks included, 0 problems, the ID maps at 0) on every panel whose
    spec they change (the Afterburn 320's Privacy key, stopped by a limit of
    the verifier since fixed, verified again at 0) - the list is in
    `archive/job-e823df9b/rebuild-1104/spec-diff/`, and the builds in
    `builds/` - with a face a donor lacks appended where the plan asked:
    Extron GUI Configurator, from Mach's 1035, on Shockwave's 320, 525 and
    535 and Turbulence's 320; Extron GUIC Video Conference 1, from
    Turbulence's 1035, on Turbulence's 320 and 525; Extron GUIC Video
    Conference 1a, from Shockwave's 1035, on Shockwave's 320 and 525. A
    caption is drawn live and not into the artwork `verify_built` reads
    (`docs/gdl-format.md` §2), so GUI Designer's own snapshot is the witness
    of each glyph drawn: it draws Mach's, Shockwave's and Afterburn's 525
    Main with their menu glyphs and the Volume strip's Up and Down,
    Afterburn's 300 Main, Shockwave's dialer with its star key, and
    Turbulence's keyboard key on all four builds
    (`archive/job-e823df9b/rebuild-1104/item2/`, `glyphs/`).
    Turbulence's keyboard key is the one glyph whose code is not the
    template's: the seed's VC Keyboard (5229, on `seeds/Turbulence 1035.gdl`'s
    VTC Dialer) types 'B' (U+0042), which GDI maps into Extron GUIC Video
    Conference 1's symbol range - its cmaps are Mac Roman and Windows Symbol,
    U+F020 to U+F0FF - and the spec gives U+F042, the code that range holds.
    `design-call-turbulence`'s TLP1035T, 725T and 525T (VC Keyboard on VTC
    Dialer) and 320M (on VTC Dialer 2) build with VC Keyboard at 5229,
    caption U+F042, in Extron GUIC Video Conference 1 at 28 pt, and GUI
    Designer's snapshot of each page draws the keyboard glyph on the key as
    it draws the seed's: on the 1035, at the seed's rect, the same
    bounding box and no shift, 52 pixels in 9,500 more than 32 levels
    apart, none more than 39. So U+F042 stays, and nothing changes in
    `regions.dialer.keyboard.glyph.char` or turbulence-42's `fix`. A panel
    draws live captions itself, which nothing here has measured, so the
    touch panel is the last word if one is to hand. A designer's own Button
    names a kit image, not a glyph: the arrows and transport keys its
    template sets in the faces still draw the kit's art;
  - the region page's seed IDs and mirrors (`docs/idmap.md` §7) translate
    and check clean on every panel the region canvases list, and are built
    and verified on every one whose spec they changed, the ID maps at 0
    (`archive/job-e823df9b/rebuild-1104/`; Shockwave's 1035 and 725 region
    specs do not change). Shockwave's tab twins - a caption-only
    button inside the tab with the tab's ID, as the template draws it, the
    first spec mirror on one page - were built and verified earlier on the
    1035 in round four's Shockwave room (`archive/job-e823df9b/round4/shockwave/reverify.log`,
    once the verifier's own limits were fixed) and on the 1535M in the format
    probes, its four twins as planned and the ID map 0 problems
    (`archive/job-e823df9b/probes-128/`);
  - Shockwave's and Turbulence's region defaults (the profile's `regions`:
    their tabs, rail, launchers, Room Mode, Mute, Help and Power) are the
    looks those profiles measured off the 1035's seed, built and verified on
    every panel the region canvases list (`archive/job-e823df9b/center/`,
    `hubs/`, `p320/`). Where the working page stands each slot, and its
    bars' fills and art, are scored against the template's frame within what
    the ledger's deviations allow (`gdl.design.region_score`,
    `docs/claude-design.md` §2 *Truth*); a slot's own look - its kit art and
    caption - is still set beside the template by eye, and so are the hub
    and 320 pages, which the score does not read yet;
  - Shockwave stands Audio Control in its right rail on the 1035's series
    only, and in its left rail's second group elsewhere: a RightRail
    `slot="audio"` is moved into the LeftRail's second Section on a panel whose
    template does not draw it there, and refused by name where that Section
    is missing or full;
  - the truth ledger (`gdl/designsys/truth/`, `docs/claude-design.md` §2
    *Truth*) covers a theme once its file is there: `python -m gdl.designsys
    audit <theme>` names a theme with none, and every entry or claim not yet
    resolved. What Mach's records the system cannot draw: the Extron-Lift glyph
    captions on a designer's arrows, transport and back keys (the kit's
    images stand in - the system's own chrome draws the face's), and its
    whole-button image presets (Window Layout, TV Channels, the
    recording layouts), which no Mach variant offers; and where it differs
    for a gate, its 30 px volume slider is drawn 53, the touch minimum.
    Where Shockwave's differs: its
    tab captions stay on the tab (above); its 52 px volume slider is drawn
    53, the touch minimum, and the Screen and Lighting tiles its template
    stands 104 apart (110 deep) stand 110 apart, since two controls may not
    overlap. Where Turbulence's
    differs for a gate: the 1035's 52 px volume slider is drawn 53
    (the touch minimum) and its Help 12 px in, at x 152 where the template
    has 141 (the footer opens its seam to the left rail's last launcher to
    the 2 mm gap). Privacy's red lit caption is `alert`, which a designer
    sets on its On state;
  - what Afterburn's ledger records the system does not draw: the glyphs of
    Extron's Afterburn icon font on a designer's arrows, d-pad, transport and
    zoom keys. The system's own chrome sets the font's glyphs - a window's
    Close, a hub's Up, Down and Back, the 320's More and Back (afterburn-36),
    where the machine that builds the system carries the face - and the kit
    draws most of the rest as images in Afterburn/Icons/PNG - the triangles
    (Carets), minus, plus, the More dots and most of the transport keys -
    which the profile indexes beside its Buttons/PNG (`kit.icons`), so a
    designer can name each on a button, drawn fitted to it; a Group pages
    with the kit's chevrons (afterburn-32); a Rail's level, on a page without
    regions, still steps with `-` and `+`. The
    squircle card under a modal with
    no `role` (Help's Background), which a window with a role draws as the
    page's own art but a plain modal cannot - Afterburn's system offers no
    Image - so a Panel stands in there; the 520's and 535's Start page on its
    own `_start` art, since every page of those panels is built on the Main
    art; and the 320's page per source, title footer and Volume modal for a
    page without regions, which Afterburn's small panels re-lay as a Page's
    controls
    in rows over a Rail. Where it differs for a gate: its 50 px volume
    slider grows to the touch minimum, and the 14 pt floor lifts its 13 pt
    captions;
  - the footer's cells the template stands together (Mach's Help and Power,
    1 px apart; Turbulence's Help and Room Mode, 2) are a `joined` set, which
    goes past the owner's call 2 as written (a header tab row and a rail
    group): the owner's word on it is awaited;
  - a column of keys a designer draws in a source popup at the template's
    own row pitch (Mach's Doc Cam, 70 px apart on the 1035) is a `joined` set
    on each panel that keeps the pitch, since the template itself stands
    those keys 10 px apart, under the 2 mm the gap check keeps: past the
    owner's call 2 as written too, and awaiting the owner's word. Overruled,
    such a column stands at the 2 mm, a little longer than the template's;
  - a column of kit-art keys in a source popup (Shockwave's `key`,
    Turbulence's `button`) is not grown as one: Build fits the art to its
    box, so each key keeps its own art's shape, and where one caption needs
    more the column is ragged (Shockwave 725's Freeze 76x66 among 71x61).
- **A Group's icon on the shared rail's button.** On a mid-size panel the
  rail of a button per Group that a page's Groups share carries each Group's
  title, and not its `icon`, which the 320's button carries.
- **The bundle measures captions 6% wide** (each `* 1.06` in
  `gdl/designsys/bundle.js`: a Label's wrap, a message's box, a 320 strip's
  title, a line of chrome's words), most of it set as a margin for the
  fallback face captions were measured in while Open Sans came from Google
  Fonts. The system carries its face (`gdl.designsys.face_js`), so the 6% is
  margin over Open Sans 3.003's own widths. The build draws its seed's Open
  Sans 1.10, which over every word the built canvases caption runs at most
  0.52% wider (its Light 0.19%), and emboldens it for bold where the canvas
  measures a real Bold, wider; the boxes the layout sizes for their words
  measure them 0.6% wide and give them GDI+'s third of an em
  (`gdiWidth`, `FACE_SLACK`) where GDI+ would cut them (`gdiCut`), and
  `gdl.spec check` refuses a caption GUI Designer would cut. The 0.6% is the
  worst word's: a box it grows can be a pixel wider than the seed's own face
  needs, and only where a word comes within 0.6% of its room. The 6% sites
  keep their margin over that, which no
  build has shown is needed; taking it out changes what most canvases
  translate to, so it waits on a build that compares the two. Letters outside the face's Latin
  (Ł, ő) still come from the Google Fonts link as it arrives, or from the
  fallback.
- **Two of the seeds' captions lose a row of ink.** `gdl.compose.caption_fit`
  says a line a row of whose ink runs past its box (`clips`), and the three
  checks refuse it: GUI Designer cuts it off flat there
  (`docs/render-fidelity.md` finding 7). Over the 41 seeds this checkout
  carries, two of Extron's own captions do, and GUI Designer's snapshots show
  both cut: Turbulence 720's 12 pt 'Window' on Main Multi-Window, whose 'd' is
  cut, and Mach 720's 12 pt 'Lighting Preset' in 80x36 on Start, whose 'h' is
  the one glyph of 'Lighting' that `line_ink` - (18, 91, 76, 108) - puts on
  row 91, a row above the box: it begins on row 92 as the L does, where an
  uncut 'Lights' of the same face has its h a row above its L
  (`archive/job-e823df9b/rebuild2-1105/mach720-lighting-preset/`). A canvas
  that sets a caption in either template box is refused until its box holds
  it.
- **A word too wide for its box after another word is broken at a character,
  as one snapshot shows.** `compose.wrap` and `bundle.js` `gdiCut` break a
  word wider than the box less its padding at a character wherever it falls -
  GDI+'s word break, as the synthetic fixture shows it for a word alone on its
  line (Wrapping's LongWord) - where they broke one only at a line's start and
  set one after another word whole. GUI Designer's snapshot of round five's
  Turbulence 320M as the rebuild of 2026-11-04 built it
  (`archive/job-e823df9b/rebuild2-1105/item1/`) draws its Display Control's
  Monitor Status, 'Back: Laptop' at 14 pt in 65x57, as 'Back:' over 'Lapto':
  the second line 48 px across where 'Laptop' is 60, ending 9 px short of the
  box's edge - the word broken or trimmed at a character, as `caption_fit`
  reads it ('Laptop' is 62.7 px across and 65 less the padding 58.6), not
  cut flat at the edge. Translated at main the spec widens that box to 70 px
  (63.6 px of room for 62.7) and moves Projector Source a pixel - the one
  panel of the built canvases that #100 changes
  (`archive/job-e823df9b/rebuild2-1105/spec-diff/`) - and GUI Designer's
  snapshot of that panel built at main
  (`archive/job-e823df9b/rebuild2-1105/monitor-status-rebuilt/`) draws 'Back:'
  over 'Laptop' whole, 60 px across, 5 px in from each edge. What no snapshot
  shows is a word broken after another onto a line the box has the depth for:
  Afterburn 1035 Portrait's 13 pt 'Video Conference' in 90x102, whose
  'Conference' is 96 px across, is `splits`.
- **A trimmed paragraph's last line keeps no indent, as `compose.fitted`
  lays it.** Where a box shows fewer lines than its words wrap to, the last
  one shown holds the rest of its paragraph with its leading spaces stripped,
  so a list key's second line indented past its icon - round five's Afterburn
  525 'Video Conference', '            Video' over '            Conference'
  at 18 pt in 214x66 - comes out 'Conference' from the box's left, over the
  icon, and `caption_fit` names nothing: every character shows. Whether GDI+
  strips those spaces, or trims the indented line at a character, no
  snapshot shows; the translation sets it as main did.
- **ECP's phone and tablet canvases have no donor, and cannot have one.** The
  six themable combinations (Afterburn / Mach / Shockwave × 16-9 and 16-10) are
  all seeded, and a spec can target either TouchLink canvas (`spec.sizes('VTLPEcp')`
  is 1920x1080 and 1280x800, the second named `VTLPEcp-1280x800`). The ECP
  series themselves are in no profile's `panels` - the templates table lists
  none for a soft client - so a Design canvas cannot list one yet. The other five
  presets — iPhone, Android Phone, iPad, Android Tablet and Custom — only offer
  Blank in the wizard, and a blank ECP project is 1 page and 3 controls, so
  there is nothing useful to clone from. A phone canvas cannot be authored
  either: `retarget` and `check` refuse any ECP size but the two TouchLink
  ones (`docs/design-rules.md` §1).
- **What a failed build shows on 1.28 is unread.** A clean build's Build
  Manager has no count (`docs/from-scratch.md` §7), and none of the format
  probes' builds failed. `GdlBlocker.ps1` reads GUI Designer's error boxes; a
  build failing on purpose (a duplicate page name, `docs/from-scratch.md` §5)
  with `examples/probes-128/Watch-BuildManager.ps1` beside it would show
  whether a failure is one of those or a list in the Build Manager.
- **CI cannot run what needs Extron's kit or GUI Designer.** The `lfs` job
  pulls the seeds the suite reads (`.github/workflows/ci.yml` names them) and
  the `chrome` job runs the translator in Chrome on the archive's pinned Design
  runtime, but `vendor/` is not in git and no GUI Designer is installed, so
  every test that reads Extron's kit (`needs_kit` in `tests/test_design.py`)
  and everything that builds skips on the runner; the public copy, which holds
  no runtime and fewer seeds, skips more. A green CI is therefore still not a
  green suite on a provisioned machine.
- **Why GDI+ aligns a centred or bottom-aligned caption as in a box 0.2 px a
  point shorter at its foot is not known** (`gdl.compose.FOOT`,
  `docs/render-fidelity.md` finding 7). It is measured on the synthetic
  fixture's five faces, the same for one line to four and for any box, and
  nothing in the faces' metrics explains it. A caption built at several sizes
  in boxes of several heights, at each vertical alignment, and snapshot, would
  pin it - a rebuild of the fixture - and GDI+'s `StringFormat` as GUI
  Designer's assembly sets it would say whether GUI Designer shrinks the box
  itself. The glyphs are drawn here at 1.375 px a point down, where GUI
  Designer draws them at 4/3, so a large caption's ink is 2-3% too tall:
  Pillow draws a face at one size, and resampling each line scores worse.
- **A left-aligned caption is drawn a little right of where GUI Designer
  draws it** - 0.24 px at 14 pt to 0.96 px at 40 on the synthetic fixture,
  centred ones about half that, right-aligned ones not at all
  (`research/synthetic_lines.py`). It is why the oblique that scores best is
  0.30 where its stems measure 0.34 (`docs/render-fidelity.md` §9): a
  shallower slant moves an italic's ink left by as much. The padding, the
  registration (`DX`) and the glyphs' side bearings are where to look; a
  render change, scored over all pages.
- **The design system and `gdl.design` give a caption's line 1.375 px a
  point** (`gdl.design._line_px`, the `* 1.37` lines of
  `gdl/designsys/bundle.js`, the profiles' `pt` and their notes on it), where
  GDI+ sets one at 4/3 (`docs/render-fidelity.md` finding 7) - 3% more room
  than a line takes. It errs safe, since a caption judged to fit does, but
  moving it changes what canvases translate to, so it is its own change, with
  the canvases it reaches rebuilt.
- **What deleting the client fixtures took with it** (2026-11-03,
  `docs/history.md`). The tests that had a synthetic twin kept it; what only
  the client's project had is laid into hand-made pages or rebuilt on a seed or
  the synthetic build, except:
  - **Forma DJR Display and the client's other faces.** Findings 7 and 8 of
    `docs/render-fidelity.md` were measured in Forma and cannot be run again;
    `tests/test_fonts.py`'s recovery checks run on the synthetic build's five
    faces, not the client's six projects, so Forma, `crestron_general.ttf`,
    `extron_guic_video_conference_1.ttf` and Extron-Afterburn under its
    `extron_-_afterburn_1a.ttf` name are recovered from nothing
    (`gdl/fonts/README.md`).
  - **GUI Designer's own baking of formatted text.** The verifier's caption
    thresholds (`CAPTION_FOUND`, `CAPTION_GONE`) were measured on the client's
    tab-indented, CRLF-broken formatted captions; the ground truth left is the
    synthetic build's four flattened captions, plain words in regular Open
    Sans and Arial, and an icon glyph in a formatted caption is tested only on
    art `gdl.compose` draws (`TestBakedCaption`). A hand-made project's
    formatted captions, mirrors across popups, fills held only on a state and
    touch targets already too small are now pages the tests lay out as the
    client's had them (`tests/test_edit.py`), not a project GUI Designer
    wrote.
  - **The only hand-made projects in the corpus.** `tests/audit_corpus.py` and
    the bug hunt now read the synthetic fixture, the seeds and Extron's
    templates: every one made by Extron's wizard or by this toolkit, so a
    claim true of those and false of an integrator's project is no longer
    caught there. CI's check that the client's colors are the Afterburn
    guide's is gone with it; the named colors it guarded are read in
    `tests/test_palette.py`.
  - **Measured records**: `docs/editing.md`'s 654/654 retarget, the format
    probes' 34-against-35 (`examples/probes-128/`, which now authors on a
    seed), and the `research/` scripts written against the client's snapshots
    stand as recorded and cannot be re-run on their own inputs.
  - **The builds made on them** (`archive/gdlwork/`, deleted 2026-11-04). One
    test read one: `tests/test_idmap.py`'s map off a build whose buttons keep
    their clone's states reads the synthetic build now, which has one such
    button (`OneState`) where the archived build of `examples/huddle.json`
    had seven. The records the folder held - the color run, the `.glt` donor GUI
    Designer refused, the Save As item that carries the project's name - stand
    as recorded.
- **The repo's layout, reviewed 2026-11-02: one optional move, everything else
  stays.** The optional move is `workflows/` to `tools/workflows/`. At the root
  it sits beside `.github/workflows/` and reads as CI, while under `tools/` it
  reads as maintainer tooling. The steps: `git mv workflows tools/workflows`,
  then point at the new path in `README.md`'s folder table, `CLAUDE.md`
  *Environment traps*, `archive/README.md`, and `tools/workflows/README.md`'s
  title and both `scriptPath` lines. The scripts take the repo root as an
  argument and name no path under `workflows/`, and no test or CI step reads
  the folder. The bug hunt's archived results quote the old path; leave them.
  What stays, and why:
  - `archive/`, `research/` and `workflows/` under one history folder: several
    misses would fail silently. `ci.yml` guards the Chrome job with
    `hashFiles('archive/dc-runtime/...')`, so a stale path turns the job off
    without a red run. `gdl/design.py` writes pin-runtime's copy to
    `archive/dc-runtime`. `.gitattributes` matches `archive/` for
    Git LFS. `tools/public_sync.py`'s `EXCLUDE` and
    `BINARY_OK` name archive paths, and the docs cite `archive/job-*` paths
    throughout.
  - `SKILL.md` at the root: `tests/test_skill.py` ties it to
    `.claude/skills/extron-panel/SKILL.md`, and the root is where a reader
    without Claude Code finds the runbook.
  - The scripts in `tests/` (`verify_built.py`, `score.py` and the rest): the
    gate commands in `CLAUDE.md` *Verifying a change* and the docs name them
    by these paths.
  - `research/` and `viewer/`: their commands are documented where they are,
    and moving them gains little.

`python tests/audit_corpus.py` checks the documented invariants against every
project it can reach; `docs/gdl-format.md` §9 has what it checks and its last
result.
