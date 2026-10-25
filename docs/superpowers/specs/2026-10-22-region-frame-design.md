# The region frame: a working page in the template's own grammar

2026-10-22. Status: design, agreed with the owner; delivered as the PR sequence
below.

## Why

The owner looked at the round-three conference rooms - every one built and
verified, 0 problems - and found them "very bare and not following the whole
language of the existing templates with five sections of top rail, left rail,
right rail, bottom rail, center". A measurement of Extron's own template pages
(every page of the Mach, Shockwave, Turbulence and Afterburn seeds, on each
series) confirmed it and found why:

- **Every bar theme's working page is one grammar.** The header holds the
  source tabs; the left rail a Display group (On, Off, Mute - or VTC's Make
  Call, End Call, Privacy) and then a group of launchers (Screen, Lighting,
  Audio) that open settings windows; the right rail Volume, its slider and Mute
  (and Audio Control on some series); the footer a mode launcher, the date and
  time, Help and Power. They stay put. The **center changes per source**: it is
  a popup region in which each source's controls are a popup of its own - a
  framed well titled with the source's name, or the template's empty state
  ("Laptop is currently selected. There are no controls for this device.").
  Settings, Help and the power-down confirmation are windows between the bars.
- **The hubs (525, 535) keep only a right menu bar** - Volume, Up, Down, Mute,
  a settings opener, Power - and make everything else popups filling main,
  starting from a Select a Source grid. **The 320 gives each source a page of
  its own** under a 36 px title strip, with More and Back.
- **Our design systems did not encode any of it.** The profiles were measured
  from the two least typical pages, Start and Main Select Source, and tell a
  designer about 140 things the working pages do not do (Mach's header holds a
  title; the default button is ghost; a source's controls are a page flip; a
  modal is a card; accent marks a selection). The bundle draws whatever
  composition it is given, and every gate passes a page that has drifted far
  from the template.

## What a designer writes

A working page names its regions, and the regions are placed and drawn as that
panel's own template draws them. The designer says what each control is for;
the template says where it goes and how it looks.

```html
<x-import component-from-global-scope="ExtronMach.Page" name="Main" start="true" panels="TLP1035T TLP725T TLP525T TLP320M">
  <x-import component-from-global-scope="ExtronMach.Header">
    <x-import component-from-global-scope="ExtronMach.Button" slot="source" name="Laptop" icon="laptop" popup="Laptop">Laptop</x-import>
    <x-import component-from-global-scope="ExtronMach.Button" slot="source" name="Doc Cam" icon="monitor" popup="Doc Cam">Doc Cam</x-import>
  </x-import>
  <x-import component-from-global-scope="ExtronMach.LeftRail">
    <x-import component-from-global-scope="ExtronMach.Section" title="Display">
      ... On, Off, Mute ...
    </x-import>
    <x-import component-from-global-scope="ExtronMach.Section" title="Settings">
      ... Lighting (nav="Lighting"), Audio (nav="Audio") ...
    </x-import>
  </x-import>
  <x-import component-from-global-scope="ExtronMach.RightRail"></x-import>   <!-- Volume, slider, Mute by default -->
  <x-import component-from-global-scope="ExtronMach.Footer">
    <x-import component-from-global-scope="ExtronMach.Button" slot="mode" name="Room Mode" nav="Room Mode">Room Mode</x-import>
  </x-import>                                                               <!-- date and time, Help, Power by default -->
  <x-import component-from-global-scope="ExtronMach.Center"></x-import>     <!-- the popup region the sources fill -->
</x-import>
```

A source popup is a Page with `kind="popup"`, the Center's group,
`role="source"` and a `title`; its controls go in it, and one with none draws
the template's empty state. A settings window is `kind="modal"` with
`role="settings"` (or a `title` and no role); `role="confirm"` and `role="wait"`
take the template's wording, by `topic`. Start and other splash pages
say `splash="true"`.

## The parts

- **Measured frame data.** `tests/measure_series.frame_of()` measures each
  series' working page - Main SD on tier A, the hubs' Main Page and popups, the
  320's source pages - into `panels[series].frame`: the five bands, each slot's
  rect (the template's, and the gate-legal one where they differ, with the
  reason), each surface (fill, border or art), the center's popup region, well,
  title and empty-state rects, the window rects, the hub menu bar and the 320's
  strip, More and Back. A checked-in fixture per theme pins it, so the tests
  that read it need no seeds; a re-measure test checks the fixture against the
  seeds where Git LFS has pulled them. `models()` passes `frame` through, and a
  turned panel's is its series' transposed. The gate-legal rect is each
  panel's: `models()` adds it where a slot is under that panel's own touch
  minimum (one series serves the 1035 at 53 px and the 835 at 67 px), and leaves gaps to
  placement, since meeting one moves a neighbour.
- **Region components.** Header, LeftRail (holding Sections), RightRail,
  Footer and Center are containers that paint nothing and emit no `data-gdl`,
  as MainArea and Rail do. The bundle places their children by slot from the
  panel's own frame - the 725's from the 725's template, not the 1035's scaled -
  and draws the template's surfaces as derived Panels, its headings as Labels,
  and Volume, the clock, Help and Power unless the designer overrides them.
- **One ID per control.** A region control is keyed by (region, name), so
  Volume on every page and every panel has one ID; fixed chrome takes the
  design panel's seed IDs (Help 8117, Power 8022, Volume 8024, Mute 8021, Room
  Mode 8118) where they are free. Layout navigation keeps its derived IDs.
- **The center and windows.** The template's well, title and empty state per
  theme; windows between the bars (Mach's #303030 band, Shockwave's #999999
  card), Close where the template has one; confirm and wait wording from the
  profile's `writing`.
- **Hubs and the 320** are recomposed from the same regions: the right menu
  bar and popups in main; a page per source under the strip.

## The owner's calls (2026-10-22)

1. **Six colours.** Colours measured from the theme's own template chrome are
   exempt from Extron's six-colour cap; the cap still applies to colours the
   designer adds. The README keeps the cap as Extron's documented standard and
   says which colours are the template's own.
2. **Hairline stacks.** A header tab row and a rail group are `joined`
   segmented sets, kept 1 px apart as the template draws them; unrelated
   controls keep 2 mm. Footer cells that the template itself draws 1 px apart
   (Mach's Help and Power) are such a stack too; cells it spaces keep 2 mm.
3. **Template renders.** A downscaled render of each theme's working page may
   go in the private design system as the designer's reference, never in the
   public copy.
4. **A missing region warns.** A working page without a region the template
   always has is named on the canvas and in the translate report; it still
   builds. Wiring faults (a tab whose popup does not exist, a window nothing
   opens) still refuse.

## Lessons folded in from the frontend-design skill

The skill is written for web pages; its brief - a distinctive identity, a
palette and type of one's own - does not apply, since an Extron panel speaks its
template's language. These do:

- **Ground the design in its subject's vernacular** - here, the template's
  grammar. The frame encodes it rather than describing it.
- **Visual structure is information.** Every region means something; the
  README says what, and nothing decorative is added (no dividers, labels or
  numbering the template does not draw).
- **Spend boldness in one place.** The rails are quiet and fixed; the center,
  the selected source's controls, is where the room's design work goes.
- **Write from the user's side.** Short Title Case captions that name the
  thing ("Lighting", not "Lighting Settings"); confirmations that ask a yes/no
  question and name the action on the button ("Do you want to power down the
  system?" [Power Down] [Cancel]); empty states that direct; no apology. The
  profile's `writing` holds the template's own words, and the README and the
  bundle's defaults both read it.
- **Plan, review against the brief, build, critique with screenshots.** The
  procedure (`SKILL.md`, `docs/claude-design.md`) gains a critique step: each
  built page beside the template's own working page, region by region.

## Delivery

Each PR carries its docs, a local `python -m pytest` run with
`$GDL_DC_RUNTIME` and the LFS seeds (CI runs neither the Chrome probes nor any
seed but Afterburn's 1035), and where it changes what builds, one GUI Designer
build at a time.

1. **Measure** (data only): `frame_of()`, the fixtures, `models()` and
   `turn()`; spec.json byte-identical for every checked-in canvas.
2. **Truth**: the profiles' looks, type and writing re-measured from the
   working pages; the ledger of every disagreement, fixed or a deviation with
   its reason; a claim lint; `python -m gdl.designsys audit <theme>` at zero;
   the six-colour exemption; README Layout generated from the frame.
   Decided in the making (2026-10-23): the ledger is
   `gdl/designsys/truth/<theme>.json`, one entry per disagreement the
   grammar measurement found, against a schema beside it - the claim and
   where it was, what the template does off which seed and pages, and a
   status (`fixed` naming the profile key and words or the README's words
   that now say it, `frame` naming the frame key the regions draw it from,
   `deviation` with its reason), with the old words that must stay `gone`
   and what a fix changes in what builds. The claim lint reads a sentence as
   a claim by its phrasing ("as the seed draws it", "as Mach's own pages
   put them", "every Mach 1035 page", a number said to be the template's)
   and wants a ledger fix's words, the frame or a `_` source naming the
   seed and a page behind it; it flags rather than guesses. The Layout is
   every series' bands in a table and the design panel's regions, sets,
   items, surfaces and windows with their rects, all off the frame, and a
   profile's hand-written `layout.regions` follows it. The README's shared
   words the ledger found wrong are the frame's where the template has one
   (Popups, the Page's `kind`, the Rail's column, the Panel's and
   PopupRegion's examples) and its Example is the working page in the
   region components. Mach is first: its page buttons `solid`, ghost the
   keys on its dark grounds, accent an active mute or privacy with a black
   caption, red and green actions on its square rounded border, its levels
   shade and white, its clock #808080. Turbulence's lit docks, Help and call
   tiles say Lime (`lime`) and Privacy's red (`alert`), Room Mode's card is
   `veil`, its header and footer are art a Panel cannot draw (flat `shade`,
   without the art's rule, until item 9 drew the art), and its README says its tabs run left-aligned
   from the left rail's edge, its rail is the kit's art, its docks and Help
   are clear beveled tiles, not invisible, and its pages take a photograph
   by role. Shockwave's lit captions are its family's dark (`ink` on gray,
   `caution` on yellow, `alert` on red, `go` on green), a source popup's and
   a 320 page's keys light `text-secondary` (`key`), its Mute rests gray and
   lights red, its clock is #C0C0C0 in 14 pt, its scrim is black, its
   standard popups are no cards, its theme is set per page, and its 1035's
   tab names are the twin the region page draws (item 3). Afterburn's chrome is
   its background art, so it keeps its system without region components and
   its Layout is the frame's plus a hand-written account of its working
   page: a row of `source` tabs over a divider and the selected source's
   popup under it, no title, the foot's date, Preview and time; Start and
   Main Select Source told apart from it; `list` and `toggle` rows in the
   left rail, not ghost; the right column that is not a Rail's stack. Its
   titles are the 21 pt white `subheading`, its `heading` an entry readout,
   its modal's card the squircle art (a Panel stands in), its Close, Back and
   arrows glyphs of a font the design system does not carry, and its red the
   On stroke of a sharing button, the one change to what builds.
3. **IDs**: region mirrors and seed IDs for fixed chrome in the translator.
   Decided in the making (2026-10-23): the bundle writes the frame's seed ID
   on the chrome a region draws in those slots - the Footer's Help, Power
   and mode launcher, the RightRail's Volume and Mute, by default or the
   designer's own in the slot - as `seed_id`, not `id`, and `pin_ids` keeps
   it on every page that draws it and every panel where the designer gave
   none and no canvas control has it, keyed by name, before the page's band,
   which steps over it; a designer's `id`
   always wins, and the Volume heading, no chrome a program drives, keeps
   no seed ID. The one mirror the frames record is Shockwave's tab `twin`
   (the 1035's and 1535's): there the tab draws no caption and a derived
   `<name> Caption` across its foot at the twin's depth says it, white in
   both states, with the tab's ID (`mirror`), `nav`, `does` and state
   names. Inside its control and sharing its ID, `gdl.spec` holds it to its
   control's touch target, gaps and states, not its own; the ID map lists
   it as the tab's mirror, and its check across panels still holds the tab
   to every panel.
4. **Regions on tier A**: the components, placement from each series' frame,
   joined stacks, surfaces and default chrome; missing-region warnings.
5. **Center and windows.** Decided in the making (2026-10-22): a source's
   popup says `role="source"`, and is each panel's own popup region - a
   popup without the role still scales with main. Its controls stay where
   drawn on the panel drawn and map from that panel's well into each
   panel's (Mach's well body; Shockwave's and Turbulence's whole region,
   since their keys reach up beside the title). Shockwave's source title is
   centred across the popup's top, as both its seeds align it, and its well
   is the page's (a `Center Well` the Center draws). Turbulence's device
   picture is item 9's.
   A confirm's Power Down takes the Page's `does`; Close and Cancel carry
   what they do and no `nav`, since only the program knows the page that
   opened the window. The template's words are the profile's `writing`.
   After review: what the chrome says is set at each panel's own template's
   size (the frame's `pt`), not the drawn panel's scaled, and a message keeps
   the lines its template sets it in (`lines`), its box widening where the
   system's Open Sans needs it; a source with controls is titled where the
   template titles one (`title_controls`); a window named for none of the
   template's is its commonest settings window on every panel; and a `role`
   a Page's kind does not take, a control under a title and a role-less
   `Sources` popup larger than its region are named.
6. **Hubs**, one theme at a time, Mach first. Decided in the making
   (2026-10-23): the hub's frame gains the grids it draws in main, measured
   off its seed - `select` (Mach's Select Source popup, Shockwave's and
   Turbulence's page grid under their popups) and `options` (the popup its
   settings opener shows) - each with its title, header strip, Help or
   Close, and tiles with the label under each. The region page draws the
   menu bar on the page and derives popups of main's group: Select Source
   (the Header's tabs as tiles - the same controls, so the same IDs), the
   options (later Sections' launchers, Audio Control, the mode launcher)
   and the first Section's popup (Display Control; Mach's Display Settings
   from a Display tile in Settings); the level is the Volume Level strip's,
   a popup of its own. Up, Down and the openers are derived with the hub's
   seed IDs, which `pin_ids` keeps where no canvas control has them; what
   the hub has no place for (the clock, a later Section's heading, a
   Header's ends) is named and listed in the page's `left`, which `pin_ids`
   lets be absent there - nothing is dropped silently. A source popup and a
   settings window are popups of main's group under the hub's header, their
   Close back to Select Source by `nav` (the one place back is known); Help,
   the question and the wait stay modals in the hub's style. Looks are the
   profile's `regions.hub`; Shockwave and Turbulence gain a `header` token
   (black at 45%, their hubs' strips) and Shockwave `writing.hub_empty`.
   After review, set beside each seed's own pages: every hub key, Close and
   tile is the seed's own kit art where the seed builds one (Shockwave's
   712x440 menu keys, its square power_red, its white hub X; Turbulence's
   ••• tile and blank Display Control; Mach's raised keys on its opaque
   popups and its white Volume), checked against the seed's built images;
   the options are the template's tiles, each captioned under it, in one
   centred row while they fit; the Volume Level strip is measured too
   (`center.level`: its ground, its level's rect and fill or art); a hub's
   settings popups take the Center's group and Select Source is the
   program's first whatever the boards' order; and a panel's own seed's
   corners are the canvas's (`radii`: Shockwave's hubs round their cards at
   10 px). What the icon faces draw - the menu's glyphs at their own size,
   the strip's speaker glyphs, Shockwave's chevrons - waits on art or the
   faces (`docs/ROADMAP.md`). Built in GUI Designer on every hub the
   canvases list and set beside each seed's Main Page: Shockwave's Select a
   Source tiles then took the kit's whole-device outlines (`white_<device>`,
   `kit.prefixed`) its seed draws, not its tabs' small glyph; and one
   control's states are one set of names on every panel, which the ID map's
   check across panels now holds (a source's tab named its lit state
   Selected, its hub tile On).
7. **The 320.** Decided in the making (2026-10-23): the 320's frame gains
   the steps its columns stand at (`center.pitch`), the sizes it sets its
   strip, headings and empty state in (`center.pt`), its program-shown
   Volume modal (`volume`: strip, level, its glyphs with their seed IDs,
   the transparent Cancel where the template has one), its empty state's
   lines (`center.empty_lines`), the question's own words (`windows.confirm.text`)
   and whether a window that is a page stands on the photo (`art`). The region page draws Main as the template's Select a Source -
   and, since a region page's Header tabs are controls with IDs and nothing
   is dropped, holds the tabs under the strip as the 320's keys, the same
   controls - going on by More to pages of Main's own with what the
   template keeps off its pages (the Sections as columns under their
   headings, the volume's heading and Mute, Room Mode, Help and Power), each
   strip titled with the Sections it holds; the slider is the Volume modal's
   level; the clock and the Center's popup region are named and left. A
   source popup, a settings window and Help are pages under the strip, what
   is put in them the template's columns (a Group a column of its own
   under its title, a slider a level with Up and Down), two to a page, going
   on over a second by More and Back at the template's places with its seed
   IDs (More 8010, Back 8011, on the first that carries each); the question
   and the waits pages on the template's rounded box, Power Down and Cancel
   at its places and sizes (a caption on two lines where one does not fit).
   Where Back ends the strip, the strip is as deep as Back's touch minimum,
   and a strip's title stands clear of Back. The template has no way
   back from a source on screen - it chooses sources off it - so a page's
   first Back stands where its second page stands Back (at the strip's end
   where More holds the foot) and says `back`: the translator points it at
   the one page whose control shows that page (a page's own later pages
   lead back to it but do not show it). Looks are the profile's
   `regions.page`; a key whose caption needs more than its art at the row's
   depth takes the theme's next wider art where that art is still the touch
   minimum deep (Shockwave's 712x440 and pill), else keeps its own, a
   two-word caption on two lines; Shockwave and Turbulence gain a
   transparent `clear` variant for the Volume modal's Cancel, and
   Turbulence's strip-end Back is its kit's return key (`strip_back`);
   `writing.page_empty` is the 320's three-line empty state, a label a line
   at the template's rects. The Volume modal draws the template's own
   colours (Mach's #4B4B4C and #E4EDF5), which the translator adds to the
   template colours the six-colour cap exempts; what the template's grammar
   leaves off (the clock, the Center's popup region) is named but does not
   outline the page. The region canvases list the TLP320M, the
   320 with a seed; the probes draw the 320C too. Turned panels still refuse. Built in GUI Designer on the TLP320M in all three themes and set beside
   each seed's 320 pages: Turbulence's labels built on its donor label's
   opaque black, so a label with no fill is now written transparent, as a
   button is, and verify_built reports a label planned clear that is not.
8. **The README rewritten around the grammar** and the design systems
   republished, with the template renders. Decided in the making
   (2026-10-23): the README leads with the grammar - per family, off the
   frames: the bar panels' five regions, the hubs' menu bar, Select a Source
   and options, the 320's strip, keys, More and Back - then the working page
   with a complete example (every artboard it leads to, by `role`), the
   center, the windows, the writing, a hand-over checklist, the pages without
   regions and the Differences, which are each ledger `deviation`'s new
   `here` (the audit wants one); the measured Layout and each panel's room
   follow. The renders are each family's frame page off its seed through
   `gdl.compose`, its region showing the frame's own popup (Main SD with
   Laptop, a hub's Select a Source), composited with real alpha
   (`compose.BINARY`, off for these alone, since GUI Designer's snapshot rule
   paints Mach's #000000B4 wells and Shockwave's 15% white well solid),
   WebP at 640, 400 and 320 px, 3 to 15 KB each, in `templates/` and on a
   `Template` card. Each profile gains `writing.voice` - the template's rules
   for captions, headings, titles and messages, its launchers' words, the
   capitals it sets itself, its sentence-case captions and the words it says
   instead of ours - and Afterburn a `writing` of its own; the caption lint
   holds the README's and the profile's caption examples to it, in the audit.
   `compare --template` sets each artboard, per panel, beside the seed's page
   of its kind (the working page, a source's popup by name, a window by role),
   and SKILL.md runs it as the critique loop before a build. From a fresh
   designer's read of the built READMEs (2026-10-23): the example is a whole
   room - Start in `Main.dc.html` (`examples.start`), every Page with
   `panels` and `theme`, every tab its glyph - and Afterburn's is too, its
   right column a Rail that stacks on the drawn panel as on the rest (one
   rule, not two) and every window on a Panel card where the squircle
   stands; the RightRail's and the Footer's words split as the components
   split them; the bar panel's question and a settings window have renders of
   their own; and each number of Differences is held to its ledger entry.
9. **Seed clone** (optional): an image kind and a verbatim clone op for art
   the design system cannot draw (Turbulence's bars, Shockwave's round art).
   Decided in the making (2026-10-23): no verbatim clone op - the image kind
   is a clone of the seed's own `PBImage` with its art set, and the art the
   seed's own resource of that name, which the applier reuses where its
   pixels agree, so a template's bar built from the spec is the seed's,
   checked off its built artwork (`check_images`: the seed's own 0% off its
   file). The spec's `image` names a kit file and its `layout` (`fill` or
   `stretch`, as Turbulence's device pictures and bars lie), and a standard
   popup takes the page's photo (`background_image`), as Shockwave's and
   Turbulence's hubs draw theirs. The design system draws the frame's art
   surfaces as derived Images where the kit has the file and the panel's
   seed can clone a `PBImage` (the series' `kinds`, now measuring `image`),
   else as before; Turbulence's source popups their device picture at the
   frame's rect for that device (`center.pictures`: each device its own
   size, the Laptop's for one the seed pictures for no source), by the
   Page's `device`, its name or the seed's pairing
   (`regions.source.devices`); a hub's popups their photo
   (`regions.hub.popup.photo`); and offers an `Image` component where the
   profile says what its template draws with one (`examples.image`:
   Turbulence's window pictures). Shockwave's seeds have no `PBImage`, so
   its round art stays the kit's gray_round, which it is pixel for pixel,
   and its Share Content art, the seed's own and in no kit, waits for an
   extraction filter (`docs/ROADMAP.md`). The README of 8 says each where a
   designer reads it - the grammar's bars as the template's art (and the
   Header's and Footer's READMEs), the center's picture and `device`, a
   hub's popups on its photo in the grammar, the center and the windows, and
   a settings window's picture as an `Image` - and its Differences no longer
   lists the bars or the device picture: the ledger's turbulence-02 and
   turbulence-34 are the frame's, and turbulence-35 each device's own size.
10. **Round four**: fresh designers from the published systems alone, built on
    the 1035, 725, 525 and 320, each page beside the template's own.
    Drawn (2026-10-24): four designers, each with one theme's built README
    and the Design type's instructions only, drew one 12-seat boardroom for
    the TLP1035T, 725T, 525T and 320M; their canvases as they left them are
    `tests/data/round4-<theme>`. Translated unchanged, every one was refused
    - Mach 19 times, Shockwave 27, Turbulence 35, Afterburn 149 - and each
    problem was put to whoever owned it. The toolkit's: two region pages on a
    hub derived Select Source, the options, the display popup and the Volume
    strip twice, and on the 320 the Volume window - now one popup where both
    derive it alike, the later page's named for its page where not, and a
    designer's board of a derived name standing in where it holds the same
    controls by name, kind and ID (`gdl.design._one_name_each`); the 320's
    empty state breaks a long source name onto two lines in its first label;
    words alone on a 320 page (Help in the designer's words) are set as the
    template sets its message, going on over a second page by More and Back;
    a dock's state caption goes on two lines; a window's content maps from
    the body under its title; a page's own child, and a MainArea's on every
    theme, stays on the screen as it grows; a popup region in a 320 row is
    rounded as its popups; a one-cell paged Group stacks its arrows; and the
    RightRail's audio control goes where the 725's template keeps it, its
    left rail's second group, or is named with what to do. The README's:
    Help as one Label with room, not a stack of one-line Labels; a state's
    own caption counted; the 320's keys and column headings and the words
    they hold, a Group's title the heading there alone; what a hub and the
    320 draw by themselves and what a designer may draw in their place; the
    725's audio place; and Afterburn's example room drawn in the layout that
    carries to all four panels, since at the template's own spacing its page
    carries to the 1035's scale alone. What each canvas, unchanged, is still
    refused for is `tests/data/round4-left.json` - Mach 6, Shockwave 11,
    Turbulence 8, Afterburn 90, every one a README gap the README now tells
    of, Mach's grown state caption and Shockwave's and Turbulence's Help
    behind a toolkit limit too (`docs/ROADMAP.md`) - which
    `TestRoundFourRooms` holds it to.
    Revised (2026-10-25): Mach's, Shockwave's and Turbulence's designers'
    rooms translate clean on all four panels; Afterburn's designer revised
    three times from the README and the translator's words and was left with
    four refusals, all on the 320 - Start's Lights heading running into
    Start, Call's VTC heading into Camera Presets, and the overlaps under
    them - which moving controls and taking things out could not clear. The
    toolkit's: on the 320 Afterburn's Page laid its own controls (the left
    rail's heading and Group) out over the whole screen and its MainArea's
    in main, each set centred, so the two landed on each other - Main SD's
    left rail on its popup region too, unseen, since no check reads a
    region as a touch target. They are now one set of rows (bundle.js
    `rowsPage`): the main area's first, then the side columns left to right;
    a heading at the left of the Group it heads, in its row; a Line in the
    gap between its rows; and, past what main holds, a side column's row
    beside an earlier row with room across - Main SD's left rail Group in
    its sources' row. Two rows of Groups keep the panel's gap apart on every
    theme. The README's: *Every panel the room has* says the rows' rule -
    the order, each kind of row's depth, the gaps, how deep and wide each
    panel's rows are (its Kind, and on the bar themes how deep a page that
    goes on keeps), where a heading stands, and that Afterburn's page does
    not go on - the four things the designer's notes said they had guessed.
    Built (2026-10-25): all sixteen panels - each room on the 1035, 725, 525
    and 320M - built in GUI Designer and verified, 0 problems, their ID maps
    0 problems (`archive/job-e823df9b/round4/`); on the 320 Afterburn's
    sources are pages of their own, as the template draws them, since its
    seed has no popup to clone. The bar set at the start - zero refusals on
    the first try - was not met: every room was refused at first, and came
    clean after the toolkit's and the README's share and one to three
    revisions from the translator's words.
    The revision is `tests/data/round4-afterburn-revised`, and
    `TestRoundFourRooms` holds it clean on every panel it lists. None is
    built yet: the rooms' builds on a host with GUI Designer are what is
    left of the round.
    Building the revision (2026-10-25) stopped before GUI Designer, at the
    ID map's check across every panel: on the 320 the Sources Group's pages
    showed the source popups, whose group only Main SD's popup region
    references, so none would have appeared - and the 320's seed has no
    standard popup to clone them from. The 320 now gives each source a page
    of its own, as its template does: what is put in it in rows in main, a
    Back at the foot's left back to the Group's page that shows it, and the
    popup region left off - so Main SD's left rail Group no longer needs the
    sources' row. A Line keeps 2 px clear of the rows it stands between, a
    page refused for its rows says their depth one under another as well as
    rearranged, and the README's example room takes the template's own
    525-deep popups, its 568 having been for the 320's. `TestRoundFourRooms`
    and `TestTheReadmesRoomTranslates` check the ID map across every panel;
    Afterburn's unrevised room is left 90 refusals, its 320 popups'
    shortfall gone.
