# Afterburn's regions: its working page in its template's own grammar

2026-10-26. Status: built on `docs/afterburn-regions`, stages 1 to 6 and 8 of
§4.12, with §7's ten questions taken at their recommended answers as
assumptions (§8), each the owner's to overrule (`docs/ROADMAP.md` *Yours*);
stage 7, Start, waits on the owner's word. It follows
`2026-10-22-region-frame-design.md`, which gave Mach, Shockwave and Turbulence
their five regions and left Afterburn without them, and is built on
`feat/call-page`'s call mode (merged as #65). That branch's call mode (the region
spec's item 11) is written for the bar themes, and Afterburn takes it as they
do (§4.7). Its recipe for a mic mute and a display's state, which awaits the
owner (`docs/ROADMAP.md` *Yours* on that branch), is followed here, with
where Afterburn's art strains it (§5, question 9).

## Why

Mach, Shockwave and Turbulence draw a working page as their template's five
regions. Each region has its own component, its places come from each series'
measured frame, and hubs and the 320 have their own versions of it. Afterburn's
chrome is its background art, so the region work stopped at writing its
grammar down in words. On Afterburn a designer draws the left rail as loose
controls on the Page. Those controls only scale and grow on the room's other
panels. The result builds, but on the 725, the 525 and the 320 the room does
not read as its template (round four, `archive/job-e823df9b/round4/`).
Afterburn's unrevised round-four canvas is left with 90 refusals
(`tests/data/round4-left.json`). 63 of them are classed as "the left rail
loose at the template's spacing" (53) or "the date and time and the loose left
rail" (10). Those 63 are 11 on the 725, 31 on the 525 and 21 on the 320. The
designer's revision cleared them only by drawing the README's workaround: the
left rail as one Group under one heading, no date and time, and a Rail with no
Volume heading. That workaround leaves the template's look on the 1035 itself
(`docs/ROADMAP.md`, *Afterburn's working page on the room's other panels*).

The measurements below show that Afterburn's working page *is* the same
grammar. It has a left rail of headed groups and a right column of volume. A
foot row holds the mode launcher, the date and time, Preview, Help and Power,
the sources run across the squircle's top, and a popup region sits in the
middle. The art draws the squircle round them, not bars. So Afterburn can use
the bar themes' region machinery, with its own frame and a handful of rules
where its template differs.

Built, this closes three `docs/ROADMAP.md` items: *A left `Rail` on
Afterburn*, *Afterburn's working page on the room's other panels*, and
*Afterburn's page on the 320 does not go on* (for region pages). It also
closes most of the ledger's glyph item there: Close, Back, More, the carets,
minus and plus.

## How it was measured

- **Off the templates, every series.** `vendor/extron/TouchLink Templates/
  Afterburn <series>.glt` was read with `gdl.project` for all 11 series the
  install lists, the 1520 and 535 included (they have no seed). A `.glt` has
  no `PBProject`, so `measure_series.seed_pages` reads nothing from it. The
  scratch reader walks `PBPage` and `PBPopupPage` directly, as
  `Project.pages()` already does.
- **The seeds are the templates.** Each Afterburn seed's pages hold exactly
  their template's controls plus one full-screen `Popup Page Reference`, which
  `frame_of` already drops (`_controls`). Its popups are identical.
  `frame_of` run on the templates reproduces every seeded series' frame in
  geometry. The only differences are the reader's extra keys, a `.glt`'s graph
  order of popups, and the level fill the scratch reader skipped. So the 1520
  and 535 can be measured off their templates. Nothing can be built on them
  until they have seeds (`docs/ROADMAP.md`).
- **The profile's frames already record Afterburn.** `panels[series].frame` in
  `gdl/designsys/afterburn.json` holds the 1220, 1020, 1720, 1230, 520, 320 and
  300 frames. The bundle drops them (`profile['frames']` packs only
  `layout.bars == "controls"` themes). This design reads those frames and
  names the few things they miss (§1.10).
- **Rects** are `[x, y, w, h]` in px on the series' own canvas. **pt** is as
  GUI Designer stores it, and the system draws 1.375 px a point. **Touch
  minimum, gap and type floor** are each panel's own (`designsys.models()`).
- **Not seen:** `round4_vs_templates.png` is a Git LFS object and this checkout
  has no `git lfs`, so the comparison image was not viewed. The findings stand
  on the measurements.

Scratch scripts and their output stayed under `/tmp/afterburn-regions/` and
are not committed.

## 1. What each series draws

### 1.1 The series

| Series | Canvas | Tier | Panels it serves (some) | Seed | Working page |
|---|---|---|---|---|---|
| 1220 | 1280x800 | A | TLP1035T/M, 1025, 835T/M, 1220/1225 | `Afterburn 1035.gdl` (and the 835, the 1035 Portrait) | Main SD, bar-class |
| 1020 | 1024x600 | A | TLP725T/M/C, 1020, 1022 | `Afterburn 725.gdl` | Main SD, bar-class |
| 1520 | 1366x768 | A | TLP1520/1525 MG, TG | none | Main SD, bar-class (template only) |
| 1720 | 1920x1080 | A | TLP1535T/M, 1720, 1725 | `Afterburn 1535.gdl` | Main SD, bar-class |
| 1230 | 1920x720 | A | TLP1230WTG | `Afterburn 1230W.gdl` | Main SD, bar-class with a preview pane |
| 520 | 800x480 | B | TLP525T/M/C, TLP520M, TLC521M, TLC526M | `Afterburn 525.gdl` | Main, a hub |
| 535 | 1280x720 | B | TLP535T/M | none | Main, a hub (template only) |
| 320 | 320x240 | C | TLP320M/C | `Afterburn 320.gdl` | a page per source |
| 300 Portrait, 300 Landscape | 320x480, 480x320 | C | TLP300M | the two 300M seeds | Main and a page per source |

The install also has `Afterburn 300 Series.glt`, a third 320x480 template
that the profile maps no model to, and `Afterburn ECP 16-9/16-10`. The ECP
templates have the 1220's pages and are not TouchLink panels. None of these is
in the profile's `panels`, and this design leaves them out.

### 1.2 The bar-class working page: the left rail

Main SD's left rail, as each series' frame (`left.groups`, `left.items`)
records it. *Offset* is from a heading's top to its group's first button.
*Seam* is the gap between buttons. The mode launcher stands at the rail's
foot.

| Series | Band | Heading (Display) | Group 1 | Heading (Settings) | Group 2 | Offset | Mode launcher |
|---|---|---|---|---|---|---|---|
| 1220 | 0,0 183x800 | 14,160 152x50, 16 pt | 2 toggles 178x50 from 0,208, pitch 58 (seam 8) | 14,403 152x50 | 3 list 178x50 from 0,451, pitch 58 | 48 | Video Conference 20,706 144x64, 13 pt, two lines |
| 1020 | 0,0 145x600 | 11,100 114x37, 13.5 pt | 2 toggles 132x50 from 0,136, pitch 60 (seam 10) | 11,289 114x37 | 3 list 132x37 from 0,326, pitch 46 (seam 9) | 36 / 37 | 15,528 115x60, 10.5 pt |
| 1520 | 0,0 179x768 | 14,146 152x50, 16 pt | 2 x 178x50 from 0,194, pitch 58 | 14,389 152x50 | 3 x 178x50 from 0,437, pitch 58 | 48 | 20,684 144x64, 13 pt |
| 1720 | 0,0 252x1080 | 19,204 213x69, 22 pt | 2 x 249x69 from 0,271, pitch 83 | 19,546 213x69 | 3 x 249x69 from 0,613, pitch 83/81 | 67 | 27,961 201x90, 18 pt |
| 1230 | 0,0 185x720 | 11,100 114x37, 18 pt | 2 x 160x60 from 0,136, pitch 60 (seam 0) | 11,409 114x37 | 3 x 160x45 from 0,449, pitch 49 | 36 / 40 | 15,635 140x73, 13 pt |

Every heading is a white Label, left-aligned, in the rail's type. Every
button's caption is white at 13 pt (10.5 on the 1020, 18 on the 1720). The
group's IDs are the template's own on every series: Display Power 8112,
Display Mute 8114, Screen 8115, Lighting 8116, Audio 8020. The mode launcher
is 8120 (Video Conference). On Main VC it is Presentation (8118), and on
Main Multi-Window it is Window Layout (8119).

The other working pages draw the rail by the same grammar:

| 1220 page | Groups (heading y: buttons) | Seam between a group's foot and the next heading |
|---|---|---|
| Main SD, Main Select Source, Main Multi-Window | Display 160: 2; Settings 403: 3 (2 on Multi-Window) | 87 |
| Main VC | VTC 160: Make Call, End Call, Privacy; Settings 403: Display, Screen, Lighting, Audio | 29 |
| Main SD Screen Arrows | Display 160: 2; Screen 337: Up, Down; Settings 515: Lighting | 21, 21 |
| Main Recording | Display 160: 2; Recording 347: Record, Stop, Pause, Mark (pitch 59-60) | 31 |
| Start | Lights 160: Preset 1-5 from 0,221, pitch 66 (seam 16) | - |

Read together: the second group's heading stands at the template's place (403
on the 1220) whatever the first group holds, and a third group stacks under
the one above it at a seam of its own. That seam is 21 and 21 px on the 1220,
21 and 16 on the 1520, 12 and 10 on the 1020, 30 and 24 on the 1720, and 22
and 15 on the 1230, each series' Main SD Screen Arrows.

**The rail buttons are kit art.** A `list` button is `1224x344_<icon>_nsel`,
or `<icon>-<accent>_sel` when lit. Its icon stands at the art's left: the
widest family, privacy, ends at x 399 of 1224, and the median at 371. The
caption follows past it. A `toggle` button is `1224x344_toggle-1` (the 1020
uses `1224x464_toggle-1` for its 132x50 cells), with its caption at the left
and the switch from x 637 of 1224 (701 on 1224x464). The template indents a
list caption by 15 leading spaces (14 on the 1020 and 1230) and a toggle's by
4, each counted at the template's own 13 pt or 10.5 pt.

### 1.3 The bar-class working page: the right column, the centre and the foot row

| Series | Volume heading | Slider | Mute | Help | Power |
|---|---|---|---|---|---|
| 1220 | 1109,160 168x50, 16 pt (4052) | 1168,202 50x395 (8024) | 1161,594 64x64 (8021), 3 px over the slider's foot | 1125,706 64x64 (8117) | 1197,706 64x64 (8022), 8 px from Help |
| 1020 | 883,100 138x37, 13.5 pt | 927,131 50x338 | 922,469 60x48, flush under it | 899,528 48x60 | 958,528 48x60, 11 px from Help |
| 1520 | 1190,146 171x50 | 1250,188 50x395 | 1243,580 64x64 | 1209,684 64x64 | 1283,684 64x64 |
| 1720 | 1672,204 240x69, 22 pt | 1756,264 69x555 | 1746,814 88x90, 5 px over it | 1698,961 88x90 | 1803,961 88x90 |
| 1230 | 1762,110 138x37, 18 pt | 1806,141 50x338 | 1801,479 60x48, flush | 1768,635 60x73 | 1837,635 60x73 |

| Series | Sources (first, step, row) | Divider | Popup region | Source title | Empty state |
|---|---|---|---|---|---|
| 1220 | 342,37 110x110, pitch 159, 342-929 | 260,137 760x20 | 200,175 880x525 | 559,175 162x50, 21 pt | 320,248 640x128, 16 pt |
| 1020 | 279,16 85x85, pitch 127, 279-745 | 208,93 608x15 | 166,120 692x406 | 431,120 162x37, 17.5 pt | 272,193 480x96, 12.5 pt |
| 1520 | 385,28 110x110, pitch 159 | 303,128 760x20 | 243,161 880x517 | 602,161 162x50, 21 pt | 363,234 640x128, 16 pt |
| 1720 | 540,39 154x154, pitch 223 | 424,180 1068x27 | 340,225 1236x726 | 844,225 226x69, 30 pt | 508,327 898x180, 22 pt |
| 1230 | 1100,18 125x125, pitch 127 | 1049,137 608x15 | 1028,149 650x500 | 1272,169 162x37, 21 pt | 1113,252 480x96, 15 pt |

The sources are `source` kit art (756x756), selected with the accent's `_sel`
image on a `#242634` fill, and their IDs are the same on every series (PC
8052, Laptop 8050, TV 8059, Streaming 8063). The row is centred on the
squircle to within 8 px: 1220 159 px in from the squircle's left and 170 from
its right, 1020 134 and 133, 1520 206 and 214, 1720 288 and 304. A source's
popup has no well, no fill and no Close. Its title is centred at its top,
white, and with nothing in it, it says the empty state
(`writing.empty`). The 1230 adds a preview pane on the left of the squircle:
its own row of source buttons over a second Divider, a Video window, Full
Screen and Send to Display. The frame records all of it as `preview`,
`video`, `fullscreen` and `display` items.

**The foot row.** Afterburn has no footer bar, but each working page stands a
row of cells along the screen's foot, across all three bands:

| Series | Left band | Squircle's foot | Right band |
|---|---|---|---|
| 1220 | Video Conference 20,706 144x64 | Current Date 200,710 208x60 (left-aligned) · Preview 568,701 144x64 · Time 932,710 148x60 (right-aligned) | Help 1125,706 · Power 1197,706 |
| 1020 | 15,528 115x60 | Current Date & Time 287,545 450x45, centred (no Preview) | Help 899,528 · Power 958,528 |
| 1520 | 20,684 144x64 | Date 203,688 208x60 · Preview 611,679 144x64 · Time 1015,688 148x60 | 1209,684 · 1283,684 |
| 1720 | 27,961 201x90 | Date 285,967 291x84 · Preview 858,954 201x90 · Time 1426,967 207x84 | 1698,961 · 1803,961 |
| 1230 | 15,635 140x73 | Send to Display 473,635 194x64 · Current Date & Time 760,655 400x45, centred | 1768,635 · 1837,635 |

That row is exactly the Footer the bar themes draw: mode launcher, clock, Help
and Power, plus Afterburn's Preview. The frame records its cells, but splits
them across `left.items`, `center.items` and `right.items` (§1.10).

### 1.4 The windows (tier A)

Every window is a modal over the whole screen. Its card is a `PBImage` named
`Background` that is the page's own background art (`6400x4000_bg1.png` on the
1220, `5120x3000_bg1-default.png` on the 1020), full screen, under the
template's `#000000A6` scrim. So a window looks like an empty squircle with
its title at the top and its Close at the squircle's top right.

| Series | Title | Close | Help's message | The question | Power Down, Cancel |
|---|---|---|---|---|---|
| 1220 | 485,36 310x50, 21 pt | 1026,25 64x64 | 290,140 700x100, 16 pt, 3 lines | 290,223 700x50, 21 pt | 462,325 and 664,325, 154x64 |
| 1020 | 357,24 310x37, 17.5 pt | 813,9 60x60 | 252,97 520x128, 12.5 pt | 252,184 520x50, 17.5 pt | 346,275 and 533,275, 144x60 |
| 1520 | 528,28 310x50 | 1114,19 64x64 | 333,132 700x100 | 333,215 700x50 | 505,317 and 707,317, 154x64 |
| 1720 | 741,39 435x69, 30 pt | 1564,25 88x90 | 468,184 982x139, 22 pt | 468,301 982x69, 30 pt | 709,445 and 993,445, 216x90 |
| 1230 | 805,34 310x37, 20 pt | 1666,17 64x64 | 700,127 520x128, 16 pt | 648,184 624x50, 20 pt | 764,275 and 981,275, 174x72 |

Close is the icon font's close glyph (§3) in `#BABCCE` on no fill. When
pressed it shows a round `#242634` fill (`Elipse 0 Thick`), as the profile's
`icon` variant already draws its On.

### 1.5 The hubs (520, 535)

| | 520 (800x480) | 535 (1280x720) |
|---|---|---|
| Main | no left rail, no clock, no foot row; Controls popup region 0,0 686x480 filling main | 0,0 1097x720 |
| Menu bar (right, 688,0 112x480) | Volume 695,4 100x48, 16 pt bold (4052); Up 712,49 and Down 712,130 66x66 outlined (`#37394E`, 10 Radius 2 Thick) with the caret glyphs at 50 pt (8120, 8121); Mute 712,211 66x66 outlined with `speaker-mute-2` art (8021); Help 712,292, Settings 712,357, Power 712,422 66x50 icon art (8117, 8040, 8022) | Volume 1112,6 160x72, 24 pt; Up, Down, Mute 1139 x 73/195/316, 105x99; Help, Settings, Power 1139 x 438/535/633, 105x75 |
| Volume Level strip | popup 637,0 50x480 on `#BABCCE`, level 17,40 15x400 (track `#242634`, bar `#626ACF`) | 1019,0 80x720, level 27,60 24x600 |
| A popup's chrome | Back (chevron glyph, 70 pt, `#BABCCE`) 0,13 66x66; title 66,21 x50, 21 pt, left-aligned, white | Back 0,19 105x99; title 105,31 x75, 32 pt |
| Select Source | title "Select a Source" 199,21 290x50, 21 pt, centred; 4 tiles 110x100 at y 147 (x 57, 210, 363, 518), art `756x688_<source>`; each caption a 13 pt Label 110x36 at the tile's y 194, *inside* its foot; Divider 32,238 621x20 | title 318,31 464x75; tiles 176x150 at y 220; captions 22 pt 176x54 at y 291 |
| Settings (8040 opens it) | a column of `list` launchers 178x50 at 52,83, pitch 58: Audio 8020, Display 8214, Screen 8115, Lighting 8116, Recording 8123 | 284x75 at 83,124, pitch 87 |
| Display Settings | opened from Settings' Display; columns at x 123 and 385 under "DISPLAY 1" and "DISPLAY 2" headings (16 pt bold, `#BABCCE`, 133,83 152x50), each a Power and a Mute toggle 178x50 from y 145, pitch 58 | - |
| A source's popup | Back and title as above; empty state 68,147 550x80, 16 pt | 108,220 880x120, 24 pt |
| Help | a popup in main: Back, title "Help", message 68,147 550x80 | - |
| Confirmation, Powering Down | modals, the Start art as their `Background`; question 141,125 517x84, 16 pt; Power Down 222,222 and Cancel 424,222, 154x66 | - |
| Start | Lights heading 14,52 152x50; Preset 1-4 178x50 from 0,113, pitch 66; Room Name 235,52 330x37, 28 pt; Start 287,207 226x66; clock 200,419 400x45, 14 pt, centred, white; Volume heading, Level 670,113 15x314, Up, Down, Mute 705 x 113/194/361 66x66 | Lights 22,78; presets 284x75 pitch 99; clock 320,628 640x67, 22 pt |

The hub's tile art is in no kit folder. `756x688_<source>_nsel` is the kit's
`756x756_<source>_nsel` with its top 68 rows cut off (1 px differs). The
selected `756x688_<source>-<accent>_sel` is a redrawn plate that differs from
any crop of the 756x756 by 4% of its pixels. So it exists only in the seed.

### 1.6 The 320

| Page | What it draws |
|---|---|
| every page but the windows | a **foot strip** 0,190 320x50 with no ground (the photo shows through); the page's title in it at 12,197 x36, 17.5 pt, white, left-aligned |
| Main | strip "Select Source" 12,197 269x36 (6071); "Select a source to begin." 35,46 250x34, 12 pt; the source picture 100,53 120x120 (`440x440_source.png`, which is the kit's `Icons/PNG/440x440_select-source.png` to within 26 of 193,600 pixels) |
| a source's first page (Doc Cam 1) | title 12,197 120x36 (6008); **More** at the strip's right 270,190 50x50, the icon font's chevron-right at 70 pt in `#BABCCE` on no fill, pressed `#37394E` round (8010), with a "More" Label 202,197 68x36, 10 pt, right-aligned (6010); keys outlined 108x45 (`#37394E`, 7 Radius 2 Thick) in two columns at x 35 and 176, three rows from y 29, pitch 141 by 54; headings over them at y 6, 107x21, 10 pt bold capitals in `#BABCCE` (ZOOM, FOCUS) |
| a source's second page (Doc Cam 2) | **Back** at the strip's left 0,190 50x50, chevron-left (8011); the title after it at 50,197 135x36 (6009) |
| a source with no controls (Laptop, PC, AUX) | one Label 35,44 250x102, 12 pt: "Laptop is currently selected." then a blank line, then "There are no controls" and "for this device." (6060) |
| Start | room title 65,22 190x37, 20 pt; Start 88,95 143x50; clock 41,179 238x38, 12 pt, white |
| Confirmation, Powering Down | pages on no art: question 35,49 250x60, 12 pt; Power Down 38,127 and Cancel 175,127, 107x50 (9028, 9029); wait 35,80 250x80 |
| Volume Level | a modal the program shows: a `#BABCCE` strip 270,0 50x240 at the right edge, level 288,25 15x190; no Cancel |

The 320 draws no left rail and no right column on any page, and no clock but
Start's. Sources are chosen off the screen. The frame records the strip as its
`bottom` band (`top` is null), with More and the title in it, `home` for
Main's strip and `second` for Back.

### 1.7 The 300s

Both 300M templates draw the 320's grammar at 320x480 and 480x320. A source
page has a Back chevron 0,405 66x66 (8041) and its title at 66,413 x50, 21 pt.
Main draws Select a Source tiles, a Volume level over Mute, Down and Up
(66x66, the minus and plus glyphs), and Settings, Help and Power along its
foot. Settings is a column of `list` launchers 178x50, pitch 56. Region pages
stay refused there by name, as on the bar themes (`docs/ROADMAP.md`).

### 1.8 The clock, everywhere

| Series | Working page | Start |
|---|---|---|
| 1220, 1520, 1720 | two: Current Date, left-aligned, and Time, right-aligned, in `#BABCCE` (16, 16, 22 pt) | one, centred, white: 415,714 450x60 on the 1220 |
| 1020 | one Current Date & Time 287,545 450x45, centred, 13.5 pt, `#BABCCE` | 287,535 450x45, white |
| 1230 | one 760,655 400x45, centred, 18 pt, white | 735,665 450x45 |
| 520, 535 | none | 200,419 400x45, 14 pt; 320,628 640x67, 22 pt |
| 320 | none | 41,179 238x38, 12 pt |
| 300 Portrait, Landscape | none | 41,326 238x45 and 80,275 238x45, 14 pt |

At each panel's floor the template's sample text fits its box. On the 725,
"September 28, 1960 12:00:00 AM" is 338 px at 16 pt in 450. On the 1035,
"September 28" is 144 px in 208 and "12:00 AM" is 96 in 148. On the 1230,
"September 28, 12:00:00 AM" is 317 px at 18 pt in 400. The README says the
525 refused both clocks because its type was wider than their boxes. That
refusal came from clocks drawn loose in the 1035's boxes, on a panel whose
template draws no clock on its working page.

### 1.9 What the template's working page is, in one sentence per family

- **Bar-class (1220, 1020, 1520, 1720, 1230):** the squircle between two
  rails. The left rail holds headed groups of `toggle` and `list` buttons over
  a mode launcher at its foot. The right column holds Volume, its slider and
  Mute. The sources run across the squircle's top over a Divider, the popup
  region sits under them, and the foot row holds the date, Preview and the
  time, with Help and Power at the right.
- **Hubs (520, 535):** a right menu bar and popups filling main. Select a
  Source comes first, a Settings column of the left rail's launchers, and
  Display Settings for the display group. Each popup has a Back chevron and a
  left-aligned title.
- **320:** a page per source over a foot strip that holds the page's name and
  More, or Back and the name.

### 1.10 What the frames miss

1. **The foot row has no record of its own.** Its cells sit in three bands'
   `items` (mode in `left`, the clocks and Preview in `center`, Help and
   Power in `right`), and `top` and `bottom` are null, which is right: the
   art draws no bars. `frameFor()` and the frame packing want all five bands.
2. **The three-group seam.** The frame is Main SD's, which has two groups. How
   a third stacks (21 px on the 1220) is on Main SD Screen Arrows.
3. **The hub's tile captions.** `select.tiles[].label` is null on the 520,
   because `_grid_of`'s `under()` wants a label whose top is below its tile's
   middle. Afterburn's caption sits inside its tile's foot: label 194 against
   a middle of 197.
4. **Start.** No frame measures it. Every bar-class and hub Start draws the
   Lights group, the room's title, Start, a centred clock and the volume, and
   the 320's draws the title, Start and the clock (§1.5, §1.6, §1.8).
5. **The 1520 and 535** have no frame, since they have no seed. Their templates
   measure (§ How it was measured).

## 2. The left rail and the clock on the 725, the 525 and the 320

### 2.1 The 725 (TLP725T: touch 60, gap 13, floor 16 pt)

The template's own 725 rail is drawn below the toolkit's minimums. Its
launchers are 37 px tall and its Help and Power are 48 wide, so the rail
cannot keep every place as drawn. Each panel's rail was simulated with every
button grown to its touch minimum at the template's seam, each heading at its
template offset over its group, and the mode launcher at its place, grown
about its middle. That gives the room left above the mode launcher, after the
panel's gap, in px:

| Panel (touch, gap; seam) | Main SD (2+3) | Main VC (3+4; 3+3 on the 725 and 1230) | Screen Arrows (2+2+1) | §5's Main SD (1+2) | §5's Call (3+2, Main VC's keys) |
|---|---|---|---|---|---|
| TLP1035T (53, 12; 21) | template places +68 | template +6 | template +7 | template +129 | template +128 |
| TLP835T (67, 15; 21) | template +22 | template -96, closed up -96, lifted +40 | template -40, closed up -8, lifted +128 | template +96 | template +54 |
| TLP725T (60, 13; 13) | template -9, closed up +1 | template -69, closed up -69, lifted +21 | template -50, closed up -40, lifted +50 | template +60 | template +2 |
| TLP1535T (45, 10; 30) | template +103 | template +20 | template +20 | template +186 | template +186 |
| TLP1230WTG (59, 13; 22) | template -12, closed up +119 | template -12, closed up +59 | template -70, closed up +61 | template +51 | template +51 |

*Template places* stands the Sections the frame draws at their groups'
places (the second at 403 on the 1035, unless the first grew into it) and a
later one a seam under the one above. *Closed up* stands every Section a seam
under the one above. The seam is the template's three-group seam
(`left.seam`, §1.2) or the panel's gap, whichever is larger. *Lifted* also
starts the first heading at main's top (y 10 on the 725) rather than at the
template's place (y 100). So on the 725 the template's own Main SD holds only
closed up, and its Main VC (six buttons) only lifted. Five buttons in two
Sections (three and two) is the most the 725's rail holds at 60 px, whether
at the template's places or closed up. Lifted, it holds six.

A rail button's width is the other limit. The art keeps its shape as the cell
grows, so a list cell 145 px wide (the 725's whole band) draws its art
145x41, its icon reaching x 47. The caption has 90 px past the icon, 4 px
clear of it and 4 px in from the right:

| Panel, floor | List caption room (one line) | Fits one line | Needs two | Does not fit |
|---|---|---|---|---|
| TLP1035T, 14 pt, 178-183 wide | 112-115 | Lighting, Audio, Display, Screen, Privacy, End Call, Make Call, Recording, Presentation (183) | Video Conference | - |
| TLP725T, 16 pt, 145 | 90 | Lighting, Audio, Display, Screen, Privacy, End Call | Make Call | Presentation, Recording, Video Conference |
| TLP835T and TLP525T, 18 pt, 178 | 112 | ... Make Call | - | Presentation, Recording, Video Conference |
| TLP1230WTG, 16 pt, 185 | 117 | ... Make Call, Recording | - | Presentation, Video Conference |

A toggle's caption stands before its switch:

| Panel, floor | Room with the template's 4-space start | Room starting 8 px in | Fits (8 px start) |
|---|---|---|---|
| TLP1035T, 14 pt | 73 | 83 | Power, Mute, Mic Live, Cooling, Warming |
| TLP725T, 16 pt (1224x464 art) | 64 | 71 | Power, Mute |
| TLP835T and TLP525T, 18 pt | 70-73 | 81-83 | Power, Mute |
| TLP1230WTG, 16 pt | 74 | 84 | Power, Mute, Mic Live, Cooling |

The README's "177 px of the 725's 145 px rail" comes from the fixed
15-space list indent (counted for 13 pt) at 16 pt. Counted from the icon's
reach at the panel's type, Lighting fits the 725's rail with 9 px to spare.

On the 725 the right column holds as well, once the slider gives way. The
slider runs from its template top (131) to Mute. Mute ends a gap above the
foot row: 455-515 against the template's 469-517. The slider is then 324 px
long. Help and Power, 48 px wide and 11 apart in the template, grow to 60 and
re-space about the pair's middle (952) at the 13 px gap: 886-946 and
959-1019, inside the 146 px right band.

### 2.2 The 525 (TLP525T: touch 66, gap 15, floor 18 pt)

The 525's template keeps no left rail, no right column and no foot row on its
Main. So the region page is drawn in the hub's grammar, as Mach's,
Shockwave's and Turbulence's already are (`planHub`). Afterburn's hub
template places the rail's parts as follows:

- **The first Section (the display group)** becomes `Display Settings`, a
  popup of main's group. Settings opens it through a derived `Display` list
  button (8214), which is Mach's pattern ("Display Settings, from a derived
  Display tile in Settings"). Its members stand in the template's first column
  (x 123, from y 145, pitch 58) under the Section's title as a 16 pt bold
  heading in capitals at 133,83 ("DISPLAY"), as the template heads its
  DISPLAY 1 column.
- **The later Sections' launchers and the mode launcher** become the Settings
  column: `list` buttons at the template's places (52,83, pitch 58, the 525's
  66 px cells at its 8 px seam). Five rows fit at 66 px, from 83 to 445. A
  later Section's heading has no place in Settings: it is named and listed in
  the page's `left`, as on the bar themes' hubs. The bar hubs' options are
  tiles in a centred row with captions under them. Afterburn's are its own
  list buttons, captioned inside, in a column.
- **The sources** become the Select Source tiles at the template's places,
  each the same control (name, ID, `nav`, `does`), with its caption a 13 pt
  Label inside the tile's foot, set at 18 pt here. "Streaming" at 18 pt is 118
  px, wider than its 110 px tile, so a tile's label widens about its middle
  into the 43 px between tiles.
- **The volume** goes in the menu bar: the Volume heading, Up and Down
  (derived, 8120 and 8121), Mute, Help, Settings (8040) and Power at the
  template's places, and the Volume Level strip.
- **The clock** has no place on the hub's Main: it is named and listed in
  `left`, as the bar hubs leave their footer's clock. Only Start draws one on
  the 525 (§4.10).
- **Source popups, Help, and the settings windows** are popups in main with a
  Back chevron at 0,13 back to Select Source (`nav`) and the title after it.
  The question and the wait stay modals on their `Background` art.

### 2.3 The 320 (TLP320M: touch 40, gap 9, floor 14 pt)

The region page is drawn as the 320's pages (`planPages`), with Afterburn's
strip at the **foot**:

- **Main** is the template's Select Source. Its strip says "Select Source",
  and it holds the Header's tabs as the 320's keys: two to a row at x 35 and
  176, from y 29, 108x45 outlined (14 pt captions; "ShareLink" is 89 px of
  108). Three rows fit above the strip. With no tabs it draws the template's
  "Select a source to begin." and the source picture.
- **What the 320 keeps off its pages** goes on over pages of Main's own
  (`Main 2`...): the LeftRail's Sections, Mute, the mode launcher, Help and
  Power. Each Section is a column under its heading, which takes the 10 pt
  bold capitals of the template's column headings, set at the 14 pt floor.
  The mode launcher, Help and Power are keys there. **More** stands at the
  strip's right (270,190 50x50, 8010), with the "More" Label beside it
  (6010). **Back** stands at the strip's left (0,190, 8011), with the title
  moved past it (50,197).
- **The clock** is named and left, since no 320 working page draws one.
  **The slider** becomes the Volume modal's level (the program shows it), as
  on the bar themes.
- **A source** is a page of its own, titled in the strip. With no controls it
  says the template's empty state as one label of three lines, as its own
  `Laptop Label 1` does.
- Afterburn's page **goes on** by More and Back, as the template's do. That
  retires *Afterburn's page on the 320 does not go on* for region pages.

### 2.4 The clock in one rule

The Footer draws the clock as each panel's own template draws it on its
working page: the date and the time apart on the 1220, 1520 and 1720, one
centred date and time on the 1020 and 1230, and none on a hub or the 320,
where it is named and left. Start, where every series draws one centred
clock, is §4.10.

## 3. The kit's Icons/PNG

`$GDL_EXTRON_RESOURCES/Afterburn/Icons/PNG` holds 657 PNGs, every one
440x440. They sit beside the `Buttons/PNG` the profile's kit root reads (`kit.root:
Afterburn/Buttons/PNG`), and no file name is in both. They are the drawings
of the template's icon font, `Font/Extron - Afterburn 1a.ttf`. Its glyph
names (fontTools' `cmap`: `close`, `chevron_left`, `caret_up`, `plus`...) name
the same drawings as the PNGs, with each caret in a gray and a dark-gray file,
and rendered side by side they are the same drawings. The templates draw them as **font glyphs**
(the face `Extron-Afterburn`, a private-use code point as a state's caption),
never as these images. The only exceptions are the recording icons,
`record-gray`/`record-red`, `stop` and `pause`, which the Recording pages
draw as images.

| Kit file | What it is | Glyph | Colour | Where the template uses it (box, size) |
|---|---|---|---|---|
| `440x440_close.png` | an X | U+E95C `close` | `#BABCCE`, no fill; pressed round `#242634` | every tier-A window's Close: Help, the settings windows, Share Content, Preview, Window Layout, Recording (1220/1230/1520 64x64 at 30 pt, 1020 60x60 at 25, 1720 88x90 at 36). Never on a hub, 320 or 300, which use Back. |
| `Chevron/440x440_chevron-left.png` | `<` | U+E97B `chevron_left` | `#BABCCE` | Back: every hub popup's (520 66x66, 535 105x99, 70/95 pt), the 300s' Page Back (66x66), the 320's second-page Back (50x50), tier A's VTC Keyboard and Search Back |
| `Chevron/440x440_chevron-right.png` | `>` | U+E97C `chevron_right` | `#BABCCE` | the 320's More (Doc Cam More, DVD More, 50x50, 70 pt), beside its "More" Label |
| `Chevron/440x440_chevron-up.png`, `-down.png` | `^` `v` | - | `#BABCCE` | not used by any template |
| `440x440_back.png` | a curved return arrow | U+E906 `back` | `#BABCCE` (white on Camera Settings) | TV Last (TV popups), VC Back (Camera Settings) |
| `440x440_more.png` | three dots | U+E933 `more` | `#BABCCE` on an outlined key | TV's More Presets, tier A (154x64, 50 pt) |
| `440x440_minus.png`, `440x440_plus.png` | - and + | U+E912, U+E939 | `#BABCCE` on outlined keys | Zoom Wide and Tele on every Doc Cam (320 108x45 at 40 pt); Camera Zoom; Mic and Program Vol Down/Up (Audio Settings); the 300s' Main Volume Down/Up (66x66, 60 pt) |
| `Carets/440x440_caret-up-gray.png`, `-down-gray.png` | filled triangles | U+E94E, U+E91D | `#BABCCE` on outlined keys | the hubs' Main Volume Up/Down (520 66x66 at 50 pt, 535 105x99 at 75); Focus Far/Near, Iris Open/Close, Screen Up/Down (white on Screen Settings), TV Channel Up/Down |
| `Carets/440x440_caret-{up,down,left,right}-dark-gray.png` | filled triangles | U+E94E, U+E91D, U+E92B, U+E938 | `#767789` (`text-subtle`) on outlined keys | the d-pads (Blu-ray, Streaming, Video, the 320's DVD 2) and VTC search scrolling |
| `Carets/440x440_caret-right-gray.png` | a filled triangle | U+E938 | `#BABCCE` | Play (Blu-ray, Streaming, Video, the 320's DVD) |
| `Carets/440x440_caret-left-gray.png` | a filled triangle | - | `#BABCCE` | not used |
| `440x440_dot.png` | a dot | U+E91C `dot` | `#BABCCE` | Recording Feedback |
| `Arrows/440x440_arrow-up.png`, `-down.png`, `440x440_return.png` | thin arrows; a mirrored return | - | `#BABCCE` | not used |
| `440x440_rewind`, `fast-forward`, `pause`, `stop`, `next-chapter`, `previous-chapter` | transport | U+E93F, E920, E936, E94B, E935, E93C | `#BABCCE` | Blu-ray, DVD, Streaming, Video transport keys |
| `440x440_select-source.png` | the source picture | - | `#BABCCE` | the 320's Main (as `440x440_source.png`, the seed's copy) |

**Sizes.** A kit PNG fitted to the template's button draws 0.9x to 1.6x the
glyph. Close on the 1035 draws 41 px fitted to its 64 px box, where the glyph
is 27x27. The hub's Volume Up draws 40x34 where its caret is 24x22, and the
320's More draws 17x30 where its chevron is 20x34. The kit's other icon art
in the same boxes draws as large as the fitted Close: Help, Power and
Settings draw 39 to 44 px in 64. The kit has no white caret, so Screen
Settings' white carets would be `#BABCCE` ones.

## 4. The design

### 4.1 One grammar, Afterburn's frame

Afterburn's working page uses the bar themes' region components and their
machinery, placed from Afterburn's own frames. Where Afterburn's template
differs, it draws its own way, and those ways are listed here. The art still
draws the squircle, so Afterburn's regions paint no surfaces: they place
controls and draw the template's chrome controls.

Two things in the profile move apart:

- `layout.bars` keeps its meaning: Afterburn's chrome is art, so a page's own
  children are not cut into bands, and pages without regions (Start, free
  pages) lay out as today (MainArea, Rail, `rowsPage`).
- A new `layout.regions: "frame"` means the theme draws a working page from
  its frames. In the code, `_regions(p)`, `components()`, the frame packing
  and the bundle's `barFrames()` (renamed `regionFrames()`) test it. A bar
  theme needs no new key, since `bars == "controls"` implies it.

### 4.2 The components on Afterburn

| Component | On Afterburn | Where it differs from the bar themes |
|---|---|---|
| Page | as now; a working page holds the regions | - |
| Header | the sources (`slot="source"`) across the squircle's top, at `center.tabs`, and the template's Divider under them as a derived Line (`Header Divider`, `text-secondary`) | no bar and no surfaces; the tabs are a set at the template's step (49 px apart on the 1035), not `joined`; a row of other than the template's four is centred on the template's own row centre (635 on the 1035); no `start` or `end` slots (the squircle's top draws none) |
| LeftRail, Section | headed groups at `left.groups`; a first Section's buttons take `toggle`, a later one's `list` (`regions.rail`, `regions.launcher`) | the column **closes up** where the template's places do not hold (§4.4); a Section past the frame's group count stacks under the one above at the template's three-group seam (`left.seam`), not refused; list and toggle captions start from the icon's reach (§4.4) |
| RightRail | Volume heading, slider, Mute at `right.items` (4052, 8024, 8021) | the slider runs from its template top to Mute, and Mute ends a gap above the foot row (§4.4); the action some pages stand at the rail's head (Main VC's Start Sharing 1121,30 144x64, Multi-Window's Window 1 and 2) is not in Main SD's frame, so a child there is named until a later measure adds the slot |
| Footer | the foot row: `mode` (left), `clock` and `preview` (the squircle's foot), Help and Power (right), at the new `foot` record | its cells sit in three bands; Help and Power re-space about their middle where they cannot shrink to the gap (§4.4); the clock is a pair or one, as the panel's template draws it; `preview` is Afterburn's slot, drawn only when given, as `mode` is |
| Center | the popup region at `center.region` | no well: Afterburn draws none |

`Group`, `Button`, `Label`, `Panel`, `Line`, `Slider`, `Level`, `Clock`,
`PopupRegion`, `MainArea` and `Rail` stay as they are. MainArea and Rail are
for pages without regions.

### 4.3 Frame data (the measure PR)

All of it measured in `tests/measure_series.py`, pinned by the profile's
`panels[series].frame`, re-measured against the seeds where LFS has them, and
spec.json byte-identical for every checked-in canvas:

- **`foot`** on an art-chrome bar frame (`_bars_frame` with `art`): the row of
  cells along the screen's foot, `{rect, items}`. Its rect is `[0, y0, W, H -
  y0]`, where y0 is the top of the lowest-standing row of touch targets and
  clocks across the three bands. Its items are mode, the clocks, Preview,
  Help and Power, in x order, by role. A cell keeps its own `items` entry in
  its band too, so nothing that reads the bands changes. `top` and `bottom`
  stay null, as Afterburn's art draws no bars.
- **`left.seam`**: on the series' three-group page (Main SD Screen Arrows),
  the seam from a group's foot to the next heading. It is 21 on the 1220 and
  1520, 12 on the 1020, 30 on the 1720, 22 on the 1230.
- **`select.tiles[].label`** for a caption inside its tile's foot: a label
  whose middle is in the tile's lower half and inside its width. It is 194 on
  the 520, against a tile middle of 197.
- **The 1520's and 535's frames** off their templates. This is optional and
  builds nothing until they have seeds, but it lets their rows of the README
  and the tests say what the template draws.
- **`start`** (§4.10, optional): a record of the Start page in the same five
  bands.

The bundle packs Afterburn's frames once per series, as the bar themes' are
packed. For a bar-class series it packs `top` as the tabs' band (the squircle
from its top to the Divider's foot, with `tabs` and the Divider), `bottom` as
`foot`, and `left`, `right` and the `center`'s keys as now. A hub (`hub`) and
the 320 (`pages`) are packed by the same rules as the bar themes. The 320's
packing reads its strip from `bottom` where `top` is null (`strip:
"bottom"`). Every read of `F.top` in `planPages`, `stripEls` and `navPlaces`
reads the strip instead.

### 4.4 The placement rules Afterburn adds

1. **The left rail column closes up.** Sections stand at the template's group
   places, and a later one a seam under the one above. One grown past the
   next one's top moves it down the rail, which is `feat/call-page`'s rule for
   every theme. Afterburn adds the rest: where the column would then end
   within the panel's gap of the mode launcher, every Section stands a seam
   under the one above. The seam is the template's `left.seam` or the panel's gap,
   whichever is larger. Where that still does not hold, the first heading
   lifts toward main's top, keeping its offset. Only then is the rail
   refused, by name, with how many buttons that panel's rail holds and the
   advice to move a launcher into a later Section's `Group` (which pages).
   §2.1's table is what this gives. A column is one width, as on the bar
   themes: every button takes the widest need of any.
2. **The right column flexes.** The heading and the slider's top keep their
   places. Mute keeps its place unless the foot row is within a gap of it,
   and then it rises. The slider ends where Mute starts, so the template's
   3 px overlap on the 1035 and 5 on the 1535 come out flush. A slider shorter
   than the touch minimum is named.
3. **The foot row re-spaces a pair.** Two cells in one band that the template
   stands nearer than the panel's gap give way first, as `openSeams` does.
   Where neither can give way because both are at their minimum (the 725's
   Help and Power, 48 → 60 wide, 11 apart), they move apart about the pair's
   middle to the gap, kept inside their band. Where the band cannot hold them
   at the gap, they are named. A clock gives way to a cell grown into it, as
   on the bar themes.
4. **A list or toggle caption starts from its art.** `kit.icon_right` gains
   `1224x344`: a list icon reaches 399/1224 at most (the screen-up and
   screen-down families, whose arrow stands at the right, are named apart).
   `kit.switch_left` records where the toggle's switch starts: 637/1224 on
   `1224x344`, 701/1224 on `1224x464`. `indentFit` learns left-aligned captions: the leading spaces that
   start the caption 4 px clear of the icon at the cell's own width and the
   panel's type. A toggle's caption starts 8 px in, or at the template's own
   start where that is less, and ends 4 px before the switch. The fixed
   `indent` counts (15 and 4) go. A caption of two words or more that does not
   fit one line goes on two, each line indented, as the 320's keys and
   Turbulence's docks already do (`lines`). One that fits neither way is named
   with the room the panel gives it (§2.1's tables).
5. **The sources row centres.** With other than the template's count, the
   tabs keep the template's size and step about the template row's own
   centre. A row wider than the squircle less the template's margins is
   named.
6. **Hub options are a column** (`regions.hub.options.layout: "column"`). The
   Settings launchers stand at the template's places in their own `list`
   look, captioned inside, one column of as many as the panel's main holds
   (five on the 525). Past that a second column stands at the template's
   two-column step, which the 520's Lighting Settings draws at x 123 and 385.
7. **The hub's and the 320's nav chrome are kit icons** (§4.8): Back (chevron
   left), More (chevron right, with its Label), and the hub's Up and Down
   (outlined keys with the gray carets).

### 4.5 Each panel tier

- **Tier A, bar-class:** the 1035, the 835, the 725, the 1535 and the 1230 (a
  seed each). The 1520 has none and is refused, as now. Each draws the five
  regions from its own series' frame, the 725's from the 725's template,
  growing to its own minimums (§4.4). The 1230 draws Main SD's regions, its
  sources at the right of the squircle. Its preview pane (a second row of
  sources, Video, Full Screen and Send to Display) is the room's own, as the
  1220's Preview button is. The regions do not draw it: a room with a preview
  draws its pane in a MainArea, and its Preview button in the Footer's
  `preview` slot.
- **Tier B hubs:** the 525. The 535 has no seed. It draws the hub's grammar
  (§2.2) through `planHub`, with Afterburn's differences: a Settings column,
  Back chevrons, tile captions inside the tile, and the tile art (§4.8).
- **Tier C:** the 320 draws the 320's pages with the strip at the foot (§2.3).
  The 300s and turned panels (the 1035 Portrait) refuse a region page by name,
  as the bar themes do.

### 4.6 IDs

The region's fixed chrome keeps the template's seed IDs, as on the bar
themes. The bundle writes them as `seed_id` and `pin_ids` keeps them where
the designer gave none. They are Help 8117, Power 8022, Volume 8024, Mute
8021 and the mode launcher 8120. On the hub they are Up 8120, Down 8121 and
Settings 8040, and on the 320, More 8010 and Back 8011. Display Settings'
derived opener takes the template's 8214. The hub draws its menu bar on every
working page, and Up and Down are one control there, with one ID on every
page; Settings opens each page's own options, so it is each page's, the
seed's ID the first working page's (§8.2).

One collision is new. Afterburn's **mode launcher and the 520's Volume Up are
both 8120**, where Mach's mode launcher is 8118. In a room with a 1035 and a
525, Video Conference would be 8120 on every panel, and the 525's derived Up
8120 too: two controls, one ID, on one panel. The rule: a seed ID that two
roles share across the room's panels stays the control every panel draws.
That is the mode launcher, the designer's own. The derived one takes the next
free ID from 50001 and is named in the translate report. `gdl.idmap
check_panels` holds it.

### 4.7 The center and the windows

- **A source** is a popup with `role="source"` in the Center's group, as on
  the bar themes. It is each panel's own popup region, with no fill. It draws
  its title centred at the frame's `title` in the frame's `pt` (21 pt on the
  1035, 17.5 on the 725), white. With nothing in it, it draws the empty state
  at `empty` in the template's words. What is put in it maps from that
  panel's region into each panel's. On the hub it fills main under its Back
  and left-aligned title, and on the 320 it is a page under the strip. The
  README's `width="880" height="525"` instruction goes, since the role sizes
  it.
- **A window** is a modal with a `role` (`settings`, `help`, `confirm`,
  `wait`) drawn as the template draws it. Its card is a derived Image,
  `<name> Background`, of the page's own background art for that panel and
  theme, full screen. That is the image kind of the region frame's item 9, a
  clone of the seed's own `PBImage` with its art set, and every Afterburn seed
  has a `PBImage`. Over it go the title at the frame's rect, the Close (the
  kit's close, §4.8) at the template's Close rect, the message, and for the
  question, Power Down and Cancel at the template's rects. This replaces the
  Panel card that stands in for the squircle today (ledger afterburn-11). A
  settings window's content maps from the body under its title, as on the bar
  themes. On a hub, settings and Help are popups in main; the question and the
  wait stay modals. On the 320 each is a page.
- **The call page** is `feat/call-page`'s: a Page with `role="call"` drawn
  from the series' measured Main VC (`call`), a `role="dialer"` popup from
  its VTC Dialer, `role="confirm" topic="call"` from its Incoming Call, and
  `role="select"` from its Main Select Source (`choose`). Every Afterburn
  bar-class template draws all four, so the measure PR records them for
  Afterburn too. The VTC Section's keys are list art (make-call, end-call,
  privacy) with their seed IDs (5014, 5215, 5217), and the launchers Section
  holds Display, Screen, Lighting and Audio. Afterburn differs in one place:
  its Share Content (Start Sharing, 8090, outlined, its On stroke `alert`)
  stands at the right rail's head (1121,30 144x64 on the 1035), not at the
  Header's end. So `slot="share"` takes that place on Afterburn. As on the bar
  themes, a hub draws the call's first Section as a popup of its own, shown
  first, and no hub or 320 seed draws a call mode.

### 4.8 The kit's icons, wired in

- **`kit.icons`:** a second kit part, `{"root": "Afterburn/Icons/PNG",
  "families": [...]}`. `kit_index(p, part='icons')` indexes the named
  families only: close, back, more, plus, minus, the chevrons, the gray and
  dark-gray carets, dot, select-source and the transport keys. That keeps the
  embedded WebPs to a few dozen. An icon from it is a state's `icon` like any
  other, and the translator gives the spec its kit path. They are Extron's
  artwork, so they go in the private design system only, as the kit does
  now.
- **Where the system draws them by default:** a window's Close (the `icon`
  variant, kit close, at the template's Close rect). The hub's Back and the
  320's Back (chevron left) and More (chevron right). The hub's Up and Down
  (the `outlined` variant `with_icon`, with the gray carets). A Level's Up and
  Down where a slider becomes a level (the gray carets on the hub, plus and
  minus on the 300s). A Group's Previous and Next, as chevrons left and right
  (owner's question 5). A designer can name any of them on their own keys:
  plus and minus on a camera's Zoom, the dark-gray carets on a d-pad.
- **Size:** fitted to the button, as every other Afterburn icon button's art
  is. That draws Close 41 px where the template's glyph is 27, as large as
  the Help and Power icons beside it. It is recorded as a deviation, not
  hidden (§4.10).
- **The hub's tile art** (`756x688`) is extracted from the 520 seed into
  `vendor/` (`kit.extract`, as Mach's and Turbulence's art is). A source
  family the seed lacks takes the kit's `756x756` art fitted, a 100x100 icon
  in the 110x100 tile (owner's question 6).

### 4.9 What the README tells a designer

The README is generated from the profile, the frames and the ledger. For
Afterburn:

- ***The template's grammar*** gains Afterburn's regions per family, off the
  frames. The bar panels get the squircle between its rails: the Header's
  sources over the Divider, the LeftRail's Sections under their headings, the
  RightRail's volume, the Footer's mode launcher, clock, Preview, Help and
  Power along the foot, and the Center. It says that the art, not a bar,
  draws round them. The hub gets the menu bar, Select a Source, the Settings
  column and Display Settings. The 320 gets the foot strip, Main's keys, More
  and Back, and the Volume window. Each has its template render, as now.
- ***The working page*** is the region example (`_working_example`), with the
  room's Start, every source and every window by `role`. `_afterburn_working`
  goes, and so does the guidance it carries for the working page: one Group
  under one heading, cells 80 deep and 18 apart in a 500 px box
  (`RAIL_CELL`, `RAIL_BOX`), no date and time, a Rail with no Volume heading,
  880x525 source popups drawn by hand, and Panel cards. `SET_CELL` stays for
  sets in a window, where a Group cannot page.
- ***Every panel the room has*** says each panel's rail capacity and caption
  room, off §2.1's rules computed per panel. It gives how many buttons the
  LeftRail holds at the template's places, closed up and lifted, the room
  past a list icon and before a toggle's switch at the panel's floor, and
  what goes on two lines. That way a designer can count instead of guessing,
  which round four's notes asked for four times.
- ***Writing*** keeps Afterburn's `writing`, adding the toggle's rule: one
  short word before the switch (Power, Mute), the device in the Section's
  heading, as the template's Display group draws it.
- ***Pages without regions*** says Start and free pages place their own
  controls (MainArea, Rail), as today, unless Start becomes a region page
  (§4.10).
- ***Differences*** are each ledger deviation's `here` (§4.10).

### 4.10 What the truth ledger gains

`gdl/designsys/truth/afterburn.json`, statuses as the schema has them. The new
entries are numbered after `feat/call-page`'s afterburn-35, the mic and
display recipe:

| Entry | Now | Becomes |
|---|---|---|
| afterburn-08: the Rail stacks Help and Power one over the other | deviation | `frame`: `foot` (the Footer stands them side by side as the template does) and `right` (Mute over the slider's foot, the slider ending at Mute) |
| afterburn-09: a level between `-` and `+` | deviation | `frame`/`fixed`: the hub's Up and Down are the template's carets (`kit.icons`); `+` and `-` stay only where the template's are plus and minus (the 300s) |
| afterburn-10: the 320 laid out in rows over a Rail | deviation | `frame`: the 320's pages, foot strip, More and Back (`320.bottom`, `home`, `second`) |
| afterburn-11: a modal's card is a Panel | deviation | `frame`: the window's `Background` image (`windows.*.surfaces`) |
| afterburn-15: Close, Back, More and the arrows are words | deviation | `fixed` (`kit.icons`) for what is wired in; a deviation stays for the size: drawn fitted, Close 41 px where the glyph is 27, its reason the kit carrying the drawings as 440x440 art and not the font |
| afterburn-32: a Group pages with Previous and Next words | deviation | `fixed`: chevrons (if the owner agrees, question 5) |
| new: the README's working page, the left rail as one Group in 80 px cells | - | `frame`: `left.groups`, `left.seam`; `gone`: "one `Group` under one heading", "cells 80 px deep and 18 apart" |
| new: "a room with a 525 leaves the date and time off the working page" | - | `frame`: `foot` and the hubs' clock left; `gone` those words |
| new: list and toggle indents of 15 and 4 spaces | - | `fixed`: `kit.icon_right`, `kit.switch_left` |
| new: the 725 cannot keep the template's own rail places at its 60 px minimum | - | `deviation`, reason the touch minimum (a gate); `here`: "On the 725 the left rail closes up to hold its Sections at 60 px; the template's own rail stands its second group at 289" |
| new: the 725's Help and Power, 48 wide and 11 apart | - | `deviation`, gate; `here`: "On the 725 Help and Power are 60 px, 13 apart about the template's pair's middle" |
| new: the hub's tile art | - | `frame` via `kit.extract`, or a deviation (fitted 756x756) |
| new: the 525's derived Volume Up loses 8120 where the room's mode launcher has it | - | `deviation`, the ID map's one ID per control; `here`: says which ID it takes |

The claim lint holds the new README words to the frame and the ledger. The
caption lint holds the example's captions to `writing.voice`.
`python -m gdl.designsys audit afterburn` stays at zero.

**Start** (optional, its own PR, owner's question 7): `frame.start`
measured off Start. It holds the Lights group's places (pitch 66 on the 1220,
46 on the 1020), the room's title, Start, the centred clock and the volume.
A Start that holds regions and says `splash="true"` draws them from it: the
LeftRail its presets, the RightRail its volume, the Footer only its centred
clock, and a MainArea the title and Start. On a hub, Start keeps its own
left rail and clock as its template does. On the 320 the template's Start
has no rail, so its presets go on a page by More, or are left, as the owner
says.

### 4.11 Tests

Each in the PR that makes it pass. `$GDL_DC_RUNTIME` and the LFS seeds run
locally; CI runs neither the Chrome probes nor any seed but the 1035.

- **Measure:** `foot` per tier-A Afterburn series (its cells, their order and
  roles, and a cell still in its band), `left.seam`, the 520's tile labels,
  and the template frames equal to the seed frames in geometry. The fixture
  re-measure test covers them all. `test_afterburns_art_draws_no_top_or_bottom_bar`
  keeps `top` and `bottom` null and adds `foot`.
- **Packing:** Afterburn's bundle carries its frames (bar, hub, pages),
  replacing the assertion that its `frames` are `{}`, under a size backstop.
- **Components:** Afterburn exports Header, LeftRail, Section, RightRail,
  Footer and Center, replacing `test_afterburn_has_no_regions` and
  `test_a_bar_theme_has_them_and_afterburn_does_not`.
- **The region canvas in Afterburn** (`_RegionProbe` with Afterburn's
  example). On the 1035 every slot stands at the template's rect, or its legal
  rect, and nothing outlines. On the 725 the Sections close up, the mode
  launcher clears the last group by at least 13, Mute ends 13 above Help, and
  Help and Power are 13 apart inside the right band. On the 835 the
  template's Main VC lifts. A column past capacity is refused with the
  capacity. On the 525 come the Settings column, Display Settings through its
  derived opener, Select Source tiles with labels, Back chevrons, the clock in
  `left`, and the ID collision resolved. On the 320 come the foot strip, More
  with its Label, Back with the title past it, Main's keys, `Main 2`, and a
  page that goes on.
- **Captions:** a list button's leading spaces start its caption 4 px clear
  of its icon on each panel. The 725's Lighting fits 145 px. Make Call goes
  on two lines there, and a list button captioned Presentation is named with
  the room it has.
- **Icons:** `kit_index(p, 'icons')` holds each named family, and the
  translator gives each a kit path.
- **Windows:** a role modal on Afterburn draws `<name> Background` as the
  image kind, with the theme's art, and its Close as the kit's close.
- **Round four:** the unrevised canvas still translates to exactly its listed
  refusals, since it draws no regions. `round4-left.json`'s 63 reasons point
  at the regions ("the left rail loose ... - the working page now draws a
  LeftRail"). `tests/data/round4-afterburn-call`, the redraw in §5, named as
  `feat/call-page` names the other themes' redraws, translates clean on all
  four panels, and its ID map is clean across them.
- **The README's room** translates clean on every panel it lists
  (`TestTheReadmesRoomTranslates`).
- **No regression:** spec.json byte-identical for every checked-in Mach,
  Shockwave and Turbulence canvas, and their probes unchanged.
- **Built:** one GUI Designer build at a time, on the 1035, the 725, the 525
  and the 320M, each `verify_built` and `verify_idmap` at 0 problems, and each
  page set beside its template's (`compare --template`).

### 4.12 Delivery

After `feat/call-page` merges, each PR with its docs:

1. **Measure:** `foot`, `left.seam`, the tile labels, and the call mode's
   `call`, `choose` and `windows.incoming` for Afterburn's bar series, with
   `feat/call-page`'s code. Optionally the 1520 and 535. Data only.
2. **Kit:** `kit.icons`, `kit.icon_right` and `kit.switch_left` for the rail
   art, computed indents, two-line list captions. The bar themes are
   untouched.
3. **Regions on tier A:** `layout.regions`, the packing, Afterburn's
   `regions` looks, the components, §4.4's rules 1 to 5, seed IDs and missing
   region warnings.
4. **Center and windows:** role popups, the `Background` image, the kit
   Close.
5. **Hub:** the Settings column, Display Settings, Back, the carets, tile art,
   the clock left, the 8120 rule.
6. **The 320:** the foot strip, More and Back, keys, the empty state, going
   on.
7. **Start** (if the owner agrees).
8. **README, ledger and audit at zero; the round-four redraw; the builds.**

## 5. Round four's Afterburn canvas, redrawn

The brief (`archive/job-e823df9b/round4/afterburn/BRIEF.md`) and the
designer's own controls, put in the regions. Every Page lists `TLP1035T
TLP725T TLP525T TLP320M`, `theme="blue-slate"`.

- **Start** stays the designer's revision (`round4-afterburn-revised/Main.dc.html`),
  a page without regions that already translates clean on all four. It
  becomes a region page if §4.10's Start lands.
- **Main SD:**
  - **Header:** Laptop, ShareLink, PC, Doc Cam (`slot="source"`, their
    kit icons, `nav` to their popups). The Header draws the Divider.
  - **LeftRail:** Section "Display" holds Display Power (`toggle`, caption
    Power), its display's state in its `states` as `feat/call-page`'s recipe
    gives it: Off, Warming Up, On and Cooling Down, its switch lit while
    Warming Up and On. Section "Settings" holds Lighting and Audio (`list`,
    the kit's lights and audio). The designer's loose Mic heading and Mic
    Mute go where the recipe puts a mic mute, in Audio Settings.
  - **RightRail:** by default, with the designer's `id`s: Volume 100, Mute
    101.
  - **Footer:** `help="Help" power="PowerDown"`, with Video Conference in
    `slot="mode"` (`nav="Call"`) and the clock by default.
  - **Center:** `group="Sources"`.

  That is the template's own rail, one display key and two launchers, and it
  holds at the template's places on every panel. On the 1035 the headings
  stand at 160 and 403. On the 725 they stand at 100 and 289, the column
  ending 60 px clear of Video Conference's gap. On the 525, Display Settings
  holds Power, Settings holds the derived Display opener, Lighting, Audio and
  Video Conference, and the Settings heading is left. On the 320 the sources
  are Main's keys, and the Sections go on over Main 2.
- **Call** is the call mode's page (`role="call"`, `reached-by="program"`),
  drawn from Afterburn's measured Main VC:
  - **Header:** the same four sources.
  - **LeftRail:** Section "VTC" holds Make Call, End Call and Privacy, the
    template's VTC keys with their seed IDs, in the designer's states.
    Section "Settings" holds Camera (`list`, `nav` to Camera Select) and
    Audio (the same control as Main SD's).
  - **RightRail** by default, and the **Footer** with Presentation in
    `slot="mode"` (`nav="MainSD"`), captioned Present: one word wider than
    the 725's rail at its floor is named (§8.2).
  - **Center:** by default.

  On the 725 the call frame's VTC keys are 132x37 at pitch 46. At 60 px they
  end at 334, the Settings heading moves down to 347, and its two launchers
  end at 513, 2 px inside the panel's gap above Presentation. Make Call goes
  on two lines there. On the 525 the VTC Section is a popup of its own, shown
  first, as `feat/call-page` draws a call page on a hub. Camera, Audio and
  Presentation go in the Settings column.
- **Laptop, ShareLink, PC** are `role="source"` popups with nothing in them:
  the empty state. **Doc Cam** is `role="source"` with its Zoom keys, a
  Group of two with the kit's plus and minus icons.
- **Lighting Settings** (`role="settings"`) holds the four presets in a
  Group with `SET_CELL`'s room. **Camera Select** (`role="settings"`, title
  "Camera Presets") holds Wide, Table and Presenter as `source` tiles with
  the kit's ptz-camera icon, the way the template's Camera Select draws its
  cameras: 110x110 tiles under its title, over a Divider. **Audio Settings**
  (`role="settings"`) holds the template's MIC column, a "MIC" heading over
  Mic Mute (`icon`, the kit's mic-mute-1, `id="201"`, lit while muted),
  beside the PROGRAM column's Mute. **Help** (`role="help"`) holds the AV
  desk's words as one Label. **Power Down** (`role="confirm"
  topic="power"`) and **Powering Down** (`role="wait" topic="down"
  reached-by="program"`).

Where the recipe strains on Afterburn, measured:

- **A display's state as words.** The recipe keeps the middle states' `text`
  to a word, Warming or Cooling. Afterburn's display key is a toggle, whose
  word stands before its switch. "Warming" is 93 px at the 725's 16 pt,
  where the toggle has 71 px and a list caption 90. "Cooling" is 77. Only the
  1035, the 1230 and the 1535 hold them. So the redraw keeps "Power" in
  every state, and the switch's light and the state names carry the state.
- **A muted mic's words.** The recipe gives the lit Mute its own `text`
  (Mics Muted). Afterburn's Mic Mute is an `icon` key with no caption,
  as the template's own (9017) is, and its lit icon in the accent says it.

Both are question 9.

## 6. Risks

- **The bar themes.** `barFrames()`, `frameFor()` and the packing are shared,
  and widening them to Afterburn can move a bar theme's output. The guard is
  spec.json byte-identical for every checked-in canvas and the probes
  unchanged (§4.11).
- **The column close-up is new layout.** It moves a Section off its template
  place, and on a lifted 725 rail the first heading leaves the Volume
  heading's line (y 100). It is drawn only where the template's places do not
  hold, and the README's capacity table says when.
- **The 320's strip at the foot** reaches into code written for a strip at
  the top (`stripEls`, `navPlaces`, a title clear of Back). Mach's,
  Shockwave's and Turbulence's 320 tests must stay byte-identical.
- **Two-line indented captions** on kit art have no template precedent.
  GUI Designer's leading spaces do not carry to a second line, so each line
  needs its own. This is unproven until built.
- **Kit icons on outlined keys** (`with_icon` on 66x66 at 440x440 art), and
  the full-screen `PBImage` clone on a modal, are unbuilt on Afterburn. The
  template does both with glyphs and its own `Background`, so the risk is the
  applier's, not GUI Designer's.
- **Icon size.** Close draws 41 px where the template's glyph is 27. It is
  recorded, but it is a visible difference beside the template's render.
- **The 8120 collision** has to land in `pin_ids` and `check_panels` before
  any room lists a 1035 and a 525 with a mode launcher.
- **The clock differs by panel:** two controls on the 1035 and one on the 725.
  They carry no ID, so the ID map's check across panels has to pass over them
  by kind. That has to be confirmed.
- **Bundle size:** Afterburn's frames and a few dozen icon WebPs on top of
  its kit. The size backstop gets an Afterburn figure.
- **The 1520 and 535** still build nothing without seeds, and their frames are
  data only.

## 7. Open questions for the owner

1. **The same component names for Afterburn,** though it draws no header or
   footer bar? Recommended: yes. One grammar across the four themes, with the
   README saying what each region is on Afterburn.
2. **The 725's rail closing up.** Is moving a Section off its template place
   acceptable, and lifting the column to main's top for a rail as full as the
   template's own Main VC? Or should such a rail be refused there?
   Recommended: close up and lift, with the capacity table, and refuse only
   past it.
3. **More Sections than Main SD draws**, at the template's three-group seam?
   Recommended: yes. The template's own Screen Arrows page draws three
   (Display, Screen, Settings), and round four's designer drew three (Display,
   Mic, Settings).
4. **Kit icons drawn fitted to their button** (Close 41 px against the glyph's
   27), as a recorded deviation? Recommended: yes. Inset images would put the
   touch target and the art in two controls.
5. **A Group's Previous and Next as chevrons** (the 320's More and Back) or
   as carets (the template's search scrolling)? Recommended: chevrons.
6. **The hub's tiles:** extract the 520 seed's `756x688` art into `vendor/`,
   or fit the kit's `756x756`? Recommended: extract, with the 756x756 for a
   family the seed lacks.
7. **Start as a region page** from a measured `start` record, and on the 320
   its presets by More or left off? Recommended: measure it. On the 320, More,
   as Main's Sections do.
8. **The 8120 rule:** the mode launcher keeps 8120, and the 525's derived Up
   takes a fresh ID? Recommended: yes. The designer's control wins, as a
   designer's `id` always does.
9. **`feat/call-page`'s recipe on Afterburn.** The recipe puts a mic mute in
   the audio window and a display's state in its key's states, with Warming
   and Cooling as their own words. It awaits your word for every theme.
   Afterburn's toggle cannot hold those words on the 725, 835 or 525, and its
   Mic Mute is an uncaptioned icon key. Keep the states and drop the words on
   Afterburn, as §5 does? Or should the display key there be a `list`
   button? That holds "Cooling" on the 725 but not "Warming" (93 px of 90).
   Recommended: keep the states and the template's toggle. The template
   draws neither word anywhere.
10. **The toggle's one word:** the README says a toggle holds one short word
   before its switch (Power, Mute) and names a longer one. Is that the right
   rule, or should a longer one take the `list` look? Recommended: name it.
   The template's toggles say one word.

## 8. As built

### 8.1 The ten assumptions

Each question of §7 is taken at its recommended answer, and recorded in
`docs/ROADMAP.md` *Yours* for the owner to overrule:

1. **The same component names:** yes. Afterburn exports Header, LeftRail,
   Section, RightRail, Footer and Center behind `layout.region_frame`, and
   each README says what its region is round the squircle.
2. **The 725's rail closing up:** close up and lift, refused only past
   capacity (`planArtRail`; the README's left-rail table, per panel;
   afterburn-42).
3. **More Sections than Main SD draws:** yes, a later Section a seam under
   the one above (`left.seam`, the panel's gap where that is more).
4. **Kit icons drawn fitted to their button:** yes, a recorded deviation
   (afterburn-36).
5. **A Group's Previous and Next:** chevrons, the kit's chevron-left and
   chevron-right, each the touch minimum square, on every Afterburn panel
   (`regions.group`; afterburn-32); the 320's Back on a Group's pages too.
6. **The hub's tiles:** extracted - the 520 seed's 756x688 art
   (`kit.extract`), the `source` tile fitted where the seed draws no such
   family or the room's scheme is not its orange (afterburn-37).
7. **Start as a region page:** measure it, and on the 320 go on by More - but
   §4.12 makes its stage the owner's to start, so it is not built: Start stays
   a page without regions (`splash="true"`, in the squircle's MainArea), and
   the round-four redraw keeps its designer's Start.
8. **The 8120 rule:** the mode launcher keeps 8120 on every panel, and the
   525's derived Up takes an ID from 50001, which the translate report names
   (`gdl.design._yielded`; afterburn-38).
9. **The call mode's recipe on Afterburn:** the states and the template's
   toggle, with Power in every state, Warming Up and Cooling Down the
   switch's `toggle-2` art lit and unlit; the Mic Mute an uncaptioned icon
   key (`mic-mute-1`, 9017) in the audio window. On the 320, whose outlined
   keys draw no switch, a state its icon alone told apart says its own name
   (Warming Up, a call key's In Call) - two alike are refused by the spec
   check.
10. **The toggle's one word:** name it. The README's left-rail table gives
    each panel's room before a toggle's switch, and a caption that fits
    neither one line nor two is named with that room.

### 8.2 Where the build departs from this design

- **`layout.region_frame`**, not `layout.regions`: that key already holds the
  Layout's hand-written list, which the claim lint holds.
- **The Header's band is the Divider's span** (`_squircle_bands`, `apart`): its
  tabs a centred row at the template's step, each the panel's gap apart
  rather than one joined set, a tab grown to a panel's minimum closing the
  seams toward the gap inside the Divider; the Divider itself a derived line
  (`Header Divider`).
- **The clocks are each panel's own** (`regions.clocks`) and derived: the
  1035's date and time apart, the 725's one. The translator carries a derived
  clock or line on no other panel and gives it no ID (`gdl.design` `NO_ID`).
- **Preview** is the Footer's `slot="preview"`, drawn only where given, with
  its seed ID 8301.
- **The hub's in-tile captions** are their tiles' (`caption_of`): the
  translator does not hold a caption's words against the tile it captions,
  only against the tiles beside it.
- **The 320's rows stop the panel's gap above its strip** at the touch minimum
  they grow to: two rows of the template's 45 px keys to a page where its
  template stands a third 8 px over the strip (afterburn-44), and an empty
  state's three lines, set at the 14 pt floor, widen and grow their 12 pt box
  about its middle. More's label gives way to a title that needs its room.
- **The round-four redraw** is `tests/data/round4-afterburn-regions`. Its
  Lighting Settings holds the four presets as a two-by-two Group of outlined
  keys, titled Lights - the `list` launchers of §5 need more than the 320's
  column - and Camera Select's Group is titled Presets.
- **Not measured:** the 1520 and 535 (no seeds), and Start (stage 7).
- **After the review.** The region pages were built at 09b60cc and verified
  on all four panels (`archive/job-e823df9b/afterburn-regions/`); the review
  that followed changed what they build (`docs/ROADMAP.md`): a hub's Volume
  Up and Down are one control, one ID, on every working page, and its
  Settings, each page's own, keeps 8040 on the page the canvas draws first
  (`gdl.design.pin_ids`); the mode launcher is no wider than its
  left rail (`capMode`) - the 725's Presentation, 156 px from x 0, ran into
  the squircle - and the README's left-rail table gives its room; the
  Divider, the Header's and the 525 Select a Source's (now measured, a
  `line` surface), is drawn through its box's middle, as the template's
  PBLine is; Mute shows the volume glyph while live and the mute glyph while
  muted, as the template's does (afterburn-47); the hub's level is filled in
  the scheme's accent-2, not the token nearest the seed's orange #626ACF;
  the 320's empty state widens to its longest line.
  `TestRegionPagesAgainstTheirTemplates` scores the region canvas against
  its frame on the 1035, 725 and 1535, the rail's, right column's and foot
  row's deliberate moves each bounded in the ledger (afterburn-23, 24, 42,
  43 and 46), and every hub's Volume Level strip showing on every working
  page is a deviation in all four ledgers (afterburn-45).
