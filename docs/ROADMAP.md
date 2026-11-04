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
   fills, a held button - has not been seen on hardware. Needs a panel, and
   a person to read it.
5. **Decide whether to exclude GUI Designer's folders from real-time
   scanning, and run the build timing once with it set.** A build holds the
   antivirus engine at one whole core while GUI Designer uses a sixth of one
   (`docs/from-scratch.md` §5c). Which folders, and the commands to time the
   effect, are in *Mine*, item 1; an exclusion lets those files go unscanned,
   so it is yours to weigh and to set.

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
   Zoom Rooms and the forms its *Gaps* lists) wait for a job that needs one.
3. **Lay a caption out in its box less GDI+'s padding.** GUI Designer sets a
   left- or right-aligned caption in by 1/6 em a side and wraps every caption
   in the box less that padding; `gdl.compose` uses the whole box. The
   synthetic fixture found it - the client project the first baseline was
   scored on centred all but 3 of its 490 captions - and modelled in memory it
   improved both baselines with no page worse: the synthetic 3.44% → 3.00%
   (worst 8.03% → 7.05%), the client's 2.19% → 2.10% (worst 7.68% → 7.06%)
   (`docs/render-fidelity.md`
   §9, `research/gdi_padding.py`). Ship it with the baseline refreshed, then
   score the bold model again.

## Backlog - real, not urgent

- **A Label over a row of keys does not move apart from them** as they grow,
  in a window or a plain modal. A window's body, a source popup's well and a
  plain modal's card re-space a row, or a stack, whose members came nearer
  than they may (bundle.js `freeLayout`), but a Label standing over two keys
  side by side is neither: round five's Turbulence stop question, its Stop
  Recording key grown from 92 to 192 px deep on the 525, ran up into its
  question's words (`tests/data/round5-left.json`). Needs the rows below a
  heading re-spaced as one block of its column.
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
  of the 320, 525, 720, 725, 835, 1020, 1025, 1220, 1225, 1525 and 1535 in every
  theme that draws it, and Afterburn's 1520 and 535 series (backlog plan 2.6;
  `gdl.seeds pick` finds each by its part number, and the profiles list them).
  What it finds none for is in `seeds/README.md` *Gaps*: the 520M and 535M, the
  1022s, the 1520s, the 1720s and 1725s, and the TLC panels. The wizard offers
  each under the name `seeds.panel_type()` spells, so `New-GdlSeed.ps1` makes one
  in a run.
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
- **`gdl.compose` draws a bold caption regular** - on a seed-built panel the
  largest remaining difference in `gdl.design compare`. GUI Designer has no
  bold file either (no seed carries one): it emboldens the regular, so adding
  Open Sans Bold would draw a design the panel does not show. A model of the
  emboldening - a 1 px rightward smear and 1/60 em more advance a glyph - took
  the client project's render baseline's mean from 2.19% to 2.13% but
  regressed two popups whose two-line captions keep the regular's advances, so
  it is not shipped (`docs/render-fidelity.md` §8). The synthetic fixture's 50
  bold Open Sans captions are the bold ground truth now; on them the model is
  mean 3.44% → 3.40% with 15 pages worse, nearly all through a bold
  left-aligned title the missing padding misplaces (*Mine*, 3) - so run it
  again once that is in (§9). It costs the built-file verifier too: a renamed
  formatted caption in bold is looked for in the regular's ink, so a bold
  caption Build baked right is reported not in its art (the synthetic
  fixture's Flat2, `tests/test_verify_built.py`).
- **`verify_built` splits a formatted caption's lines at CRLF only**
  (`check_baked_caption`), as GUI Designer's own formatted text breaks them. A
  caption whose lines break at LF, as a spec's do - the synthetic fixture's
  Flat3, which Build bakes as two lines - is looked for as one line and
  reported not in its art. An edit that renames a caption to two lines would
  fail a right build the same way; the test of it normalises the breaks.
- **A translucent fill is pasted solid where the snapshot draws it
  translucent** (`docs/render-fidelity.md` §9): finding 2's binary rule holds
  for antialiased edges, not for a fill at 20 to 75% - the synthetic
  fixture's translucent keys differ by 39-88% each, and its white at 20% is
  lighter in the snapshot than a plain blend would make it. Measure the rule
  before modelling it.
- **An italic caption is drawn upright**: GUI Designer obliques the regular,
  as it emboldens it, and the synthetic fixture's italic rects differ by
  14.76% (`docs/render-fidelity.md` §9).
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
  - a region page, a source popup (`role="source"`) and a window (a modal
    with a `role` or a `title`) on a turned panel or a 300 are refused by
    name: a turned frame's header-as-left-band and the 300's menu bar are not
    drawn yet;
  - on the 320 the region page derives to the 320's pages
    (`docs/claude-design.md` §3), probed on the TLP320C and translated clean
    on the TLP320M the region canvases list - the 320C's seed is here in each
    theme now (`seeds/README.md`), and no region page has been built on it - and
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
    template's own size is the owner's call);
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
    gives. The hubs set their
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
    Both build differently from the passes above, which are not yet built
    again.
    What it does not do yet: Mach's Share Content
    says Share, an incoming call's answers take IDs of their own, Turbulence's
    Select a Source tiles too, and Shockwave's 725 call page holds two of its
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
  - the region page's seed IDs and mirrors (`docs/idmap.md` §7) translate
    and check clean on every panel the region canvases list, and are not yet
    built in GUI Designer but for Shockwave's tab twins - a caption-only
    button inside the tab with the tab's ID, as the template draws it, the
    first spec mirror on one page - built and verified on the 1035 in round
    four's Shockwave room (`archive/job-e823df9b/round4/shockwave/reverify.log`,
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
    overlap. What Turbulence's
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
    minus, plus, the More dots and most of the transport keys - which the
    profile now indexes beside its Buttons/PNG (`kit.icons`), so a designer
    can name each on a button, drawn fitted to it (afterburn-36), and a
    window's Close draws the X, a Group pages with the chevrons
    (afterburn-32) and a hub's Up and Down are the carets (afterburn-09); a
    Rail's level, on a page without regions, still steps with `-` and `+`. The
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
  margin over Open Sans 3.003's own widths, and no build has shown it is
  needed or enough: the build draws its seed's Open Sans 1.10, a few font
  units a glyph apart, and emboldens it for bold where the canvas measures a
  real Bold. Taking it out changes what most canvases translate to, so it
  waits on a build that compares the two. Letters outside the face's Latin
  (Ł, ő) still come from the Google Fonts link as it arrives, or from the
  fallback.
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
- The size-dependent vertical text residual (`docs/render-fidelity.md`
  finding 7); every text finding validated against one typeface, the client
  project's Forma DJR Display, which can no longer be scored (below).
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

`python tests/audit_corpus.py` checks the documented invariants against every
project it can reach; `docs/gdl-format.md` §9 has what it checks and its last
result.
