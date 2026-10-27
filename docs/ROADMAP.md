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
   Remote Desktop window open and restored, for the run - from two minutes to
   over twenty a seed, with its build (`docs/from-scratch.md` §7). Next needed
   when a job needs a panel `seeds/README.md` lists as a gap.
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

## Mine, in order

The order these and the backlog below are worked in, as pull requests, and
where each runs: `docs/superpowers/plans/2026-10-26-backlog-plan.md`.

1. **What a real-size build spends its time on.** `examples/boardroom-full.json`,
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
   What is left is in §7: a plain container on the 320, a shared hub across
   a mid-size panel's Groups, a left Rail on Afterburn, an icon on a group's
   button, and the region frame's gaps below. A plain modal that says more
   than the 320's one screen goes on over modals of its own, and a Clock on
   Shockwave's and Turbulence's 320 is cloned from the theme's 525, each built
   and verified there (`archive/job-e823df9b/small-panels/`).
   800x480 is two series in all three themes - the 520, tier B, and the 720,
   tier A, which take different layouts - where Afterburn has only the 520.
   Design and phases: `docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md`.
   A native-size seed beats a retarget, which matches Extron's own hand layout
   for only 22% of controls. The other gaps in `seeds/README.md` (Teams Rooms,
   Zoom Rooms, Afterburn's 1520 and 535) wait for a job that needs one.
3. **Retire the client fixtures.** `fixtures/` is a real client's project,
   in the archive only, and the builds in `archive/gdlwork/` made with it as
   the donor carry the same material (`archive/README.md` *Sensitivity*). The
   render baseline is scored against the fixtures' snapshot exports, so they
   go last: first a synthetic fixture with the same reach (many pages, every
   control type the renderer scores) and GUI Designer's snapshot exports of
   it, and a new `tests/baseline.json` from `tests/score.py` - which also gives
   the public copy a render baseline; then delete them. The dependency is
   wider than the baseline: tests in several files (those marked
   `needs_client`, and `test_verify_built.py`'s), steps of CI,
   `examples/edits.json`, `tests/audit_corpus.py`, the bug-hunt corpus and
   `docs/editing.md`'s verification table also read the fixtures, and all of
   them skip or fail where the fixtures are not (a host that has only the
   public copy). The worked examples that build run on a seed.

## Backlog - real, not urgent

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
- **A seed of a panel's other form.** `seeds/` holds one form per size - the
  725T, 525T, 320M, 1535M - so a TLP725M, 725C, 525M, 525C, 320C or 1535T spec
  has no seed, and is refused the other form's rather than built as it
  (`seeds/README.md`). Nor has most of what a profile lists a seed of its own
  part number: `gdl.seeds pick` finds none for the 835T and (outside Afterburn, whose
  `Afterburn 835 (Project1).gdl` it finds) the 835M, nor for the TLP1220MG and
  TLP1220TG, the TLP1225MG and TLP1225TG, the 1025s and 1020s, the 1525MG, the
  720M and 720C and others, and prints the
  `New-GdlSeed.ps1` line for the form's own (`Afterburn TLP725M.gdl`); none
  has been made, so the wizard's name for each form's panel type, as
  `seeds.panel_type()` spells it, is unproven.
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
  bold file either (no seed or fixture carries one): it emboldens the regular,
  so adding Open Sans Bold would draw a design the panel does not show. A model
  of the emboldening - a 1 px rightward smear and 1/60 em more advance a glyph -
  takes the render baseline's mean from 2.19% to 2.13% but regresses two popups
  whose two-line captions keep the regular's advances, so it is not shipped
  (`docs/render-fidelity.md` §8). It needs bold ground truth beyond the
  fixture's 44 Forma captions: the synthetic fixture above.
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
- **A tier B hub shared by several groups.** On a mid-size panel (the 525)
  each `Group` pages as popups in its own box. The spec's hub - one region all
  the page's groups share, switched by a rail of group buttons - needs the Page
  to lay its groups out together; a page with several groups shows them all,
  each paged, until then.
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
    template's own size is the owner's call);
  - on a hub the region page derives to the hub's grammar
    (`docs/claude-design.md` §3) - built and verified on Mach's 525 and
    535, Shockwave's 525 and 535 and Turbulence's 525
    (`archive/job-e823df9b/hubs/`) - and what it does not do yet: the
    popups' photo and Turbulence's device pictures (below) are built
    (`archive/job-e823df9b/seed-art/`); Turbulence's settings windows' own pictures (the 525's Lighting
    Control lightbulb, Audio Control speaker and Display Control monitor)
    are an Image the designer places, which the window does not draw by
    itself; a hub's
    Display Control popup lays the LeftRail's first Section out as a row
    under its heading, where Extron's draws a card per display (Display 1
    and 2) - a canvas with two displays has no way to say so yet; a later
    Section's heading has no place among the hub's options and is named, as
    is the footer's clock; two region pages on one canvas derive the
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
    template's options grid has no example of; the template sets its
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
    pages the dialer over four, each page filled before the next, so a last
    page can hold one control alone (Share Content on Video Call 4, Mach's
    Keyboard on VTC Dialer 4) where evening the pages out would not; what
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
- **An icon on a group's button.** On a small panel a Group becomes one button
  that opens its pages; it carries the group's title, and no icon yet.
- **Smaller gaps in translating for every panel**, each found in review and
  none met by the huddle canvas:
  - a canvas's own repeats (`sc-for`) in a main area are not laid out for
    other panels - they stay where they were drawn;
  - captions are measured before Open Sans has loaded - the components
    measure as they render, and the face arrives after - so the bundle widens
    each measure 5-6% for the fallback face. The probe now waits for the face
    and translate says by name, once for the canvas, when it did not load, but the
    measure itself is still the fallback's: making it wait would mean laying
    the canvas out a second time once the face is there;
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
  finding 7); every text finding validated against one typeface.

`python tests/audit_corpus.py` checks the documented invariants against every
project it can reach; `docs/gdl-format.md` §9 has what it checks and its last
result.
