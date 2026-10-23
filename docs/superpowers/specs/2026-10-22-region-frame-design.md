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
3. **IDs**: region mirrors and seed IDs for fixed chrome in the translator.
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
   picture waits for the image kind (9): the popup leaves its place empty.
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
7. **The 320.**
8. **The README rewritten around the grammar** and the design systems
   republished, with the template renders.
9. **Seed clone** (optional): an image kind and a verbatim clone op for art
   the design system cannot draw (Turbulence's bars, Shockwave's round art).
10. **Round four**: fresh designers from the published systems alone, built on
    the 1035, 725, 525 and 320, each page beside the template's own.
