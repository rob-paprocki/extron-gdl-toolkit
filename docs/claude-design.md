# Designing a panel on a Design canvas

The goal: describe what a panel has to **do**, in prompts, to Claude in the
Claude app; get a **Design canvas** - an Artifact made from the Design type,
artboards laid out on a canvas - drawn in the real Extron template; and have
Claude Code turn that canvas into a working `.gdl` and its ID map. The canvas
is where the panel is designed. Claude Code is where it is built, because only
Claude Code can run GUI Designer.

What this reads is the Artifact: the canvas's own files and the Design type's
runtime it serves (§5). Claude Design's own site, claude.ai/design, closes on
2026-12-14, as design moves to Artifacts in the Claude app; every canvas here
has been built from a Design artifact, and none needs that site.

```
prompts about functionality
      │  a Design canvas in the Claude app, using one Extron template's design system
      ▼
canvas: one artboard per page or popup, drawn from the system's components
      │  Claude Code reads the canvas (Artifact tool)
      ▼
python -m gdl.design translate <canvas dir> out/   →  out/<panel>/spec.json, one per panel
      │  the existing pipeline, unchanged, once per panel
      ▼
New-GdlPanels.ps1  →  a built, verified .gdl per panel  +  one ID map, verified on each
```

Nothing goes the other way. A spec is an intermediate the translator writes, not
something anyone edits or exports back to a canvas.

## 1. Using it

There are two roles, which can be the same person. The **designer** works in
the Claude app and never needs this repo or Windows. The **builder** works in
Claude Code on the machine GUI Designer runs on.

| Role | Needs |
|---|---|
| Designer | a claude.ai account that can make Design artifacts, with the template's design system shared to it - *Extron Afterburn*, *Mach*, *Shockwave* or *Turbulence* |
| Builder | this repo, set up as `README.md` *Setup* says, on a machine with GUI Designer 1.28.0.7 (`CLAUDE.md` *Environment*), with the seeds pulled from Git LFS and Chrome installed; and Claude Code signed in to a claude.ai account that can open the canvas |

### Once: publish the design system

A design system is built from this repo and published to a claude.ai account.
Nothing else distributes it. In Claude Code, in the repo, ask it to *build the
Afterburn design system and publish it* - or Mach's, Shockwave's or
Turbulence's. It runs:

```bash
python -m gdl.designsys build <afterburn|mach|shockwave|turbulence> <dir>
```

and publishes the `project/` tree that writes as a Design System artifact, with
the Artifact tool. Before it publishes, `python -m gdl.designsys audit
<template>` reports every claim the system makes about its template that the
theme's ledger does not resolve (§2 *Truth*), and exits non-zero on any; a
theme at zero is ready. The icons and theme backgrounds are Extron's kit, read from
the GUI Designer install or `vendor/`, and embedded downscaled. Turbulence's art,
and Mach's slider, are in neither until they are extracted from Extron's own
files, once per machine: `python -m gdl.designsys extract <template>`
(`vendor/README.md`). Without the kit, or without Pillow, the build says so,
naming that step where it applies: the system then has no icons, and its themes
no background images. The template renders the README shows beside its grammar
(§2 *README*) are rendered off the seeds, so they need the seeds pulled from Git
LFS; without them, or without Pillow, the build says so and the README shows
none.

Because it carries Extron's artwork - its kit and the renders of its own
pages - the system is published private (§2 *Icons*), to the account Claude
Code is signed in to, never to the public copy. The designer works in
that account, or has the system shared with theirs.

### Design: on a Design canvas

1. In the Claude app, start a design - a Design canvas - that uses the
   template's design system - *Extron Afterburn* in this example.
2. Describe the panel by what it has to **do**; the system already knows what
   the template looks like. Say:
   - the room and its panels - every panel the room has, by model, and a panel
     that rotates the other way up as model-Portrait or model-Landscape
     (`TLP300M-Landscape`; `gdl.spec.panel_id`). The canvas is
     drawn on the first (each system draws the TLP Pro 1025/1035 at 1280×800) and
     builds for each, sized for its own screen. Every system lists every panel
     its template's series serve, and builds one where its profile names a seed
     for it (`seeds/README.md` lists the seeds; a panel with none is refused
     with the command that makes it). Each is proven on the TLP Pro 1035 and
     725; Mach's, Shockwave's and Turbulence's on the 1525, 720 and their hubs
     too - the 525, and the 535 in Mach and Shockwave - and Afterburn's on the
     525 and 320 (§6, and §7 for what is left). Extron draws no
     template for the 520M, 521M, 535M, 835M or 1035M turned, so each system
     draws each as its series turned - main region and rail transposed, as
     Extron's own 300M is both ways, and its popup with them - on the page
     colour, with no background art;
   - the sources, and what selecting one does;
   - the call, camera, display and audio controls, and what each shows as it
     changes: a display warming up, a microphone muted, a call connected;
   - what has to be confirmed first, such as shutting the room down, and what
     the program shows by itself, such as an incoming call;
   - optionally, one of the template's background themes - Afterburn's are
     Default, Anthracite, Blue Slate and Grape; §2 *Themes* has every
     template's.

   For example: *A huddle room panel for a TLP Pro 1035, a 725, a 525 and a 320, on the Grape theme.
   Three sources - laptop, wireless and the room PC - showing which is selected.
   One display that can be off, warming up, on or cooling down. Volume with mute,
   End Call, help, and turning the room off asks for confirmation.*

   The system's README makes the designer draw only with its components, one
   artboard per page or popup, list every panel the room has on each Page, and
   record what every control does.
3. **Check it in Play.** A button that opens another page follows its link.
   Holding any button shows what the panel shows while it is held.
   **Preview every panel**: set a Page's `preview` to one of its `panels` and the
   artboard draws as that panel will be built - its size, its own background and
   main region, every control at its touch minimum and type floor, a Group paged
   or turned into pages of its own (Next, Previous, Back and its button work in
   Play). A control that collides with its neighbour, or a frame that cannot hold
   what it has, shows a dashed outline; the translator names it.
4. **Ask for feedback where it is missing.** A button the control system drives
   needs at least two states, or the panel cannot show anything changing. Ask by
   meaning - *"the source buttons should show which one is selected"* - and the
   system picks the template's way of showing it: an accent icon, a selection
   line, a toggle's thumb. A button with one state shows nothing when pressed.

### Build: in Claude Code

On the builder's machine, in this repo, give Claude Code the canvas link and ask
for the panel and its ID map. It:

1. **Reads the canvas** into one folder: the canvas artifact's `project/`
   folder, saved without that prefix - `canvas.json`, every `*.dc.html` and the
   installed system's `ds/<folder>/` files - with the Design type's
   `artifact-type/dc-runtime.js` saved beside the artboards as `support.js`.
2. **Translates it:**

   ```bash
   python -m gdl.design translate <that folder> out/huddle        # out/huddle/<panel>/spec.json
   ```

   One spec for each panel the canvas's Pages list (`panels`, §3), each laid out
   by the design system for that panel - its size, main region, background, touch
   minimum and type floor - and naming that panel's own seed, which it prints. A
   panel with no seed here is refused with the line that makes one -
   `New-GdlSeed.ps1`'s, or `New-GdlTurnedSeed.ps1`'s for a panel turned where no
   template is drawn that way up - then the profile entry that lists it
   (`seeds/README.md`). Give a file
   instead of a folder (`out/spec.json`) for the panel the canvas
   is drawn on alone. A canvas with anything it cannot build, on any panel, writes
   no spec for any of them, and names each problem with its panel: something painted
   outside a component with its box (§4), most others with their artboard or
   control, and a color or icon the template lacks by its name alone. Each
   panel drawn is also held to `gdl.spec check` - touch targets, gaps - and to
   its seed's own borders, a stroke on one the seed gives no thickness, whatever
   else is wrong, so one read names everything: a
   designer who revised for the layout problems alone met the spacing ones in
   the next. The fix goes on the canvas, back in the Claude app, where the
   designer can see it; then Claude Code reads it again.

   A revision of a canvas whose ID map a programmer already has is translated
   with that map, `--previous out/huddle/idmap`, so every control the program
   knows keeps its ID (`docs/idmap.md` §9).
3. **Critiques it against the template**, before anything is built: each
   artboard, as each panel the canvas lists draws it, beside the page of
   that panel's own template seed it stands for:

   ```bash
   python -m gdl.design compare <that folder> --template out/huddle/critique   # index.html and sheet.png
   ```

   The working page (one holding a region) is set beside the seed's working
   page (Main SD, a hub's Main Page, the 320's Main), a `role="source"` popup
   beside the seed's source popup of its name (else the frame's), and a window
   beside the seed's window of its role, all off the panel's frame
   (`gdl.design.template_counterparts`); a free page stands alone. The
   template side is `gdl.compose`'s render of the seed with its translucent
   chrome blended over the photo (`compose.BINARY`, docs/render-fidelity.md
   §2), and needs the seeds (Git LFS). `sheet.png` holds every pair on one
   image to show the designer. Going region by region, whatever differs from
   the template that the system's README does not list under *Differences* is
   a fix on the canvas; translate and compare again.
4. **Builds and verifies it**, with nobody touching GUI Designer. Before the
   first unattended build on a machine, and after any GUI Designer upgrade, set
   the one preference `CLAUDE.md` *Driving GUI Designer* names, or the build
   stops at a prompt nothing can see.

   ```bash
   powershell\New-GdlPanels.ps1 -Out out/huddle -Name Huddle      # every panel
   powershell\New-GdlPanel.ps1 -Spec out/spec.json -Donor <seed> -Output <panel.gdl> -IdMap out/idmap   # one
   ```

   `New-GdlPanels.ps1` writes the one ID map every panel shares
   (`docs/idmap.md` §7), builds each panel on its own seed and verifies each
   against that map. GUI Designer opens, builds and closes by itself, a panel
   at a time. The scripts exit non-zero if anything was built other than as
   designed, or the ID map disagrees with a built panel. For a revision,
   `-Previous` names the map the IDs were kept against, and `changes.md`
   beside the new map tells the programmer what changed (`docs/idmap.md` §9).
5. **Puts each artboard beside the page GUI Designer built from it**, for
   sign-off. A client signs off on the panel, not on the canvas:

   ```bash
   python -m gdl.design compare <that folder> out/huddle out/huddle/signoff   # every panel
   python -m gdl.design compare <that folder> <panel.gdl> out/signoff         # one
   ```

   The built side is `gdl.compose`'s render of the built file's own artwork; a
   modal is shown over the start page, and a group's popup in its page's region,
   as the panel shows them. For a canvas of panels the page has a section per
   panel: each artboard drawn for that panel, and each page or popup its layout
   derived shown as Play shows it after a tap. It prints the share of pixels
   that differ per page, and names each panel it did not compare - a folder
   with no built file or several, a panel the canvas lists with no folder -
   in its section and on stdout.

### What comes out

| File | For |
|---|---|
| `out/huddle/<panel>/<Name>.gdl` | each panel, built: open it in GUI Designer, or load it to the touch panel |
| `out/huddle/idmap/` (`idmap.md`, `.csv`, `.json`) | the control-system programmer: every addressable control's ID, type, caption, states and what it does, and where it is on each panel (`docs/idmap.md`). No program is generated. A revision adds `changes.md` and `changes.json`: what a program written against the previous map has to change. |
| `out/huddle/critique/index.html`, `sheet.png` | the designer: each artboard, as each panel draws it, beside the template's own page of its kind (the critique loop) |
| `out/huddle/signoff/index.html` | the client: each panel's pages as designed beside them as built |

To change the panel, change the canvas and build again. Once a programmer has
the map, translate the change with `--previous` and build with `-Previous`.
Every ID the program uses is kept, and `changes.md` says what the program has
to change (`docs/idmap.md` §9).

## 2. One design system per template

Extron ships four themes - **Afterburn, Mach, Shockwave and Turbulence**
(`docs/design-rules.md` §4) - and each becomes its own Design System artifact.
Per template rather than one system with four color themes, because the
templates differ in more than color: fonts, corner shapes, button archetypes,
icon sets and the seed a panel is built on.

`python -m gdl.designsys build <template> <dir>` writes one, from
`gdl/designsys/<template>.json` - the template's profile, each value with where
it came from - and the components shared by all four (`gdl/designsys/bundle.js`).
Claude Code publishes the result with the Artifact tool.

| Part | From |
|---|---|
| **Colors** | Afterburn: the published guide (`docs/design-rules.md` §4), its four accent schemes as the system's themes. Mach: its PSD's `Colors` group and the selected/unselected alpha rule. Shockwave: its seed's own fills and captions, corroborated by `gdl.themes` over its `.glt` - its PSD names swatches but carries no values. Turbulence: its seed's own, state by state - most of them stored by name, so read through the KnownColor table (`docs/gdl-format.md` §7) - with its header and footer read off their art - one color and a 3-row light rule on the edge facing main, which the region components draw as that art, stretched over each band as its seeds lay their bars out, and flat in `shade` where the art is not extracted - and its lit captions' two greens and red (`accent`, `lime`, `alert`). |
| **Themes** | Afterburn's four recommended pairings - Default with accent Scheme 1, Anthracite with 3, Blue Slate with 2, Grape with 4 - as a Page's `theme`. Each is the kit's background image fitted over `#242634`, as the seed draws it, plus its accent scheme. Mach's are its kit's six photos, the seed's sunset first, stretched as its seed stretches them (`background_layout`). Shockwave's are its seed's soft blur and its Start page's Saturn, stretched likewise; Turbulence's its seed's corridor and the bokeh, office, swoop and water photos from its templates. The spec carries the image, and the applier appends it to the project. |
| **Layout** | Where the template puts things. Afterburn keeps most of a page in the squircle main area (`MainArea`, 916×752 at 183,24), with headed groups on the left rail and volume, help and power on the right. Mach puts shade bars top and bottom and rails either side of its photo. Shockwave puts its sources as tabs across a header, the chosen one's page in a black video well (926×574 at 168,120), rails either side and a capsule footer. Turbulence puts its sources as tabs across a translucent header, the chosen one's popup in the region between the bars and the side rails (995×549 at 140,137), and a translucent footer. |
| **Type** | The face the template's profile offers, one its seed can actually author (`Project.font_resource_names()`; Mach's and Turbulence's seeds also define Open Sans Light, which no profile offers), at the sizes its own pages use - none under the 14 pt the toolkit checks. Sizes are points, drawn at GUI Designer's 1.375 px per point. Open Sans is Apache 2.0 and loads from Google Fonts. |
| **Borders** | Only border resources the seed defines and the spec names (`BORDERS`), so a design cannot ask for a shape the panel cannot draw. |
| **Button archetypes** | The looks the seed's own buttons use, per state. Afterburn's captioned ones are outlined (the most common), ghost and inverse, and an alert - an outlined button whose On stroke goes red, as Start Sharing's does while sharing is live (the template never fills a button red). Its image ones - source, list, icon and toggle, and outlined with an icon - are each drawn from the kit as the seed draws them: the image, the fill it takes when selected, and where the caption goes. Afterburn shows state with its icons, never fills a button with an accent, and never colors a caption red. Mach shows it with a brighter fill. Shockwave draws every button as a kit image: a button names its color family, rests dark in a ring of that color and lights up when On (`kit.outline_off` reads the kit so) with its color's dark for a caption (`ink` on gray, `caution` on yellow, `alert` on red, `go` on green), and an `action` button carries the kit's icon at its left with the caption centered past it, as the seed pads it with spaces. Turbulence's are kit images too: a gray tile, a white ring, a navy source tab or, a dock or Help, a clear tile with an inset shadow and a blue bevel at rest, white with a green glow or dark teal when lit. Most of its kit carries its words in the art, so only its blank images take a caption, which turns `accent` when lit - `lime` on a dock, Help and the call tiles, as the seed's own do, and Privacy's `alert`; its `dock` puts two words on two lines as the seed does (`lines`: a caption of two or more words broken at the space nearest its middle). A variant's `size` is the size its seed draws it at - Turbulence's tile is 87×90 - and the Button README states it and the preview draws it there, so a caption keeps its proportion to the art; drawn smaller, a caption at the template's size spills past its tile. |
| **Icons** | The template's resource kit, indexed by name and look (`gdl.designsys.kit_index`) and embedded in the bundle downscaled, as WebP - about 1.8 MB for Afterburn's thousand. Extron's artwork, so only in the owner's private design system, with their agreement (`docs/history.md`). A state asks for an icon unselected or selected; selected is the scheme's primary accent for an icon drawn in the primary accents, its secondary for one drawn in the secondary ones (toggles, volume levels). A variant's `icon` is what it draws unless told otherwise; `icons` narrows what it offers to the families starting so (Afterburn's toggle), or with any of a list (Turbulence's rings). Where an indented caption is centred past an icon at the image's left (Mach's 1376x440 tab art), `kit.icon_right` says how far across its image a kit size's icons reach - measured, the widest of them - and the region Header gives each tab's caption the leading spaces that start it 4 px clear of that on each panel. A file the kit's `<W>x<H>_` naming misses is named in the profile (`kit.named`: Shockwave's modal Close, one file per look; Turbulence's pairs whose two files are named apart, like `outline_01` at rest and `round_01` lit, where the pair replaces the half icons the pattern made of them). A family the naming misses by a prefix of its own is indexed under a size the profile gives it, with its `prefix` and its pixel `size` (`kit.prefixed`: Shockwave's whole-device outlines, `white_<device>.png` in `icons/440x440 White`, as `device`, 440x440, which its `device` variant and its hubs' Select a Source tiles draw). A kit that exists only inside Extron's files - Turbulence's, in its templates - is extracted to `vendor/` first (`python -m gdl.designsys extract <template>`, `vendor/README.md`). |
| **Sliders and levels** | As the seed's built ones draw: a thin rounded rail (Afterburn's slider's is 10 px, filled `#BABCCE`; its level's 15 px, filled in the secondary accent) with a round thumb in the secondary accent. The thumb is a kit image, not a color: its circle is 65% of its 50 px box, so the canvas draws the kit's own, and the translator gives each slider the scheme's (`gdl.designsys.slider_thumb`), since a clone keeps its donor's. A template whose thumb is one file whatever the accent names that file, and one whose rail is art rather than two colors names its rail images too (`track_image`, `fill_image`); the canvas then draws those, the translator gives them to each slider in the spec (`gdl.designsys.slider_rail`), and a thumb that is not round keeps its own proportions (`thumb_height`). A level takes its filled part's colour (`bar`) where one is given, and on a hub is drawn as its Volume Level strip's (the frame's `center.level`): Mach's a square white bar on its shade track, Shockwave's and Turbulence's from the kit's art - which the panel's level, a clone of the seed's own image-filled one, keeps (`keep_art`). |
| **Modals** | As Build draws them: the page beneath under black at alpha 166 - the 35% transparency every template's modals are authored at, which the spec writes on every modal - whatever background color the popup has (`docs/gdl-format.md` §5). So a modal carries no background of its own. |
| **Spacing and sizes** | The panel's touch minimum and spacing for its model (`touch_minimums`), and GUI Designer's 10 px nudge. The tokens state the design panel; every other panel's comes from the profile's per-panel table. |
| **Panels** | A per-panel table (`panels`), one entry per Extron series: the models it serves (`gdl/templates.py`), its main region - measured off its background art where the art draws it (Afterburn's squircle), else off its template's own controls (Mach's bars, Shockwave's well, Turbulence's side bars) - the rail band beside or below it, or none where the template keeps nothing on screen from page to page (those three themes' 320s), its popup region, a background per theme and how its pages draw them (Fill or Stretch), and per seed, what the seed can clone (`kinds`: a slider, a level, a date and time, a standard popup, an image - no Shockwave seed has a `PBImage`), which of the profile's borders it lacks, and the corner it rounds a profile border at where that is not the profile's (`radii`: every project carries its own copy of the built-in borders and Build draws the panel's, so Shockwave's 520s, 535s and 320 round 2D Rounded Rectangle at 10 px where its 1035 does at 2, and the canvas draws each panel's). `gdl.designsys.models()` adds each model's own touch minimum, gap and type floor (`docs/design-rules.md` §1); the bundle carries it so a Page can draw any of them. Measured with `tests/measure_series.py`. |
| **Frame** | Each series' working page in its template's own grammar (`docs/superpowers/specs/2026-10-22-region-frame-design.md`), as its `panels` entry's `frame`, measured off the series' own seed by `tests/measure_series.py` (`frame_of`; `--frame` prints each). `page` names the seed page measured: Main SD on the bar series, Afterburn's among them; a hub's Main Page (Afterburn's 520: Main); a 320's first source page (Doc Cam 1) and a 300's (Computer). The five bands `top`, `left`, `right`, `bottom` and `center` are each `null` where the template draws no such band - Afterburn's top and bottom, a hub's left and bottom - or a `rect` with its `surfaces` (`name`, `rect`, `kind` shape, image or label, `fill` as `#RRGGBBAA` after the control's transparency, `border` resource, `art` file, and `popup` where a source's popup draws it, as it draws Mach's well) and its `items` by role (`role`, `name`, `kind` in `gdl.spec`'s words, `rect`, the seed `id`, a label's `text`). The source `tabs` - in `top`, or in Afterburn's `center` - give the `first` tab's rect, the commonest step `pitch`, the `count`, their `look` off and on (`fill`, `border`, `art`, the caption's `text` color, `null` where it is not drawn), every tab as an item, since Extron's steps are uneven, and on Shockwave's 1035 and 1535 a `twin`: each tab's name, a caption-only button under it sharing its ID, with its own `look`. `top` adds what stands at its `start` and `end`; `left` its `groups` (`heading` rect and text, `buttons` as items, `pitch`); `center` the popup `region` and, off a source's popup (`popup`), its `well`, `title`, `empty` state, `status` (a line under the empty state the program sets: Shockwave's Disconnected) and `close`, in page coordinates, `pt` the sizes it sets its title, empty state and status in, and `title_controls` the title of a source with controls (its Doc Cam's: Turbulence titles one at the popup's top, an empty one 40 px lower), `pictures` the picture each source's popup pins, by the device its art names (`doc-cam` for `1152x1152_doc-cam.png`), in page coordinates and only where the template pins one - Turbulence sizes each device its own way, the 1035's Doc Cam 326x288 to its Laptop's 293x257, and a device a settings popup pictures (the 525's Display Control monitor, Audio Control speaker and Lighting Control lightbulb, popups the page's buttons open) is no source's - and on a hub its `level`: the Volume Level popup its strip reference shows (`popup`), its own `fill`, its level's `rect`, empty `track` and filled `bar` colours (`null` where it fills from art), `border` resource, `art` (its `track` and `fill` images, where it fills from the kit's: Shockwave's and Turbulence's) and the rects of the glyph `labels` over and under it - or on a 320 or a 300 its first control `row`, the `headings` over it, the steps across that row and down its first column (`pitch`: the 320's Doc Cam's, 124 and 60 on Mach's), the sizes it sets its title, its headings and its empty state in (`pt`) and the `empty` state of a source with no controls (`empty_page` where another page draws it), with its lines one label each where the template sets them so (`empty_lines`, each `rect` and seed `id`: the 320's Laptop Label 1-3, 6060-6062). A 320's or 300's frame carries each page a source page does not draw as a record of its own in the same five bands: `home` (the 300's menu bar of Settings, Help and Power; the 320's Select a Source title) and `second` (a source's second page, with its Back), and its `volume`: the modal its program shows the volume in (`popup`, the 320's Volume), its `surfaces` (Mach's #4B4B4C strip at the right edge), its `level` (`rect`, empty `track` and filled `bar` colours or `art`, `border`), the glyph `labels` over and under it (each `rect`, seed `id` and `pt`: Volume Up Label 7023 and Volume Down Label 7026) and its `cancel`, the transparent button over the rest of the screen that puts it away, as an item (Shockwave's and Turbulence's; Mach's has none). `windows` holds what a page opens, in page coordinates: `help`, `confirm` and `wait` (the Help, Confirmation and Powering Down popups, or on a 320 or a 300 the pages so named), and `settings`, every modal with a Close and the popup or page a settings opener names (a hub's More Options), those drawn alike in one record naming its `popups`. Each has its `rect` - the card or band it draws (Mach's #303030 band, Shockwave's #999999 card, Afterburn's art over the whole screen), `null` where a modal draws none, a popup in the region its own - its `surfaces`, `title`, `close` as an item, `pt` the sizes it sets its title and message in, a help, confirm or wait window its `message` and the `lines` that takes in its box in the template's own face (`gdl.compose.wrap` at 1.375 px a point), and a confirm its `buttons`; a window that is a page (a 320's, a 300's) says whether it stands on the photo (`art`: Mach 320's question and wait stand on the page's own #303030), and a question that is a page its own words (`text`: every 320's runs on in one line); settings windows drawn alike at one title size are one record. `ids` holds the seed IDs of the fixed chrome the frame holds: on the bar series help, power, volume, mute and mode; on a hub help, power, mute, volume-up, volume-down and settings (8040 on every hub, captioned More on Shockwave's and Turbulence's); on a 300 help, power and settings; on a 320 none. A hub's frame adds the grids it draws in main: `select`, its Select a Source (Mach's popup of its own; Shockwave's and Turbulence's the page's own grid under their popups), and `options`, the popup its settings opener shows (Mach's Settings, the others' More Options). Each has its `popup` (`null` for a page's own grid), its `title` and its `text`, its header strip's `surfaces`, its `help` and `close` as items, its `tiles` in rows - each tile's `rect` and the `label` rect under it - and `pt`, the sizes it sets its title and its tiles' labels in. `note` says what the bands do not. `models()` gives every panel its series' frame, each button or slider under that panel's own touch minimum with a `legal` rect - grown about its centre, inside its band where the band can hold it - and its `reason`; gaps are left to placement, since meeting one moves a neighbour. A turned panel's frame is its series' transposed, in each page record too, the header becoming its left band and the footer its right, with its note said upright. A series with no seed has none. The bundle of a theme that draws its bars as controls carries it once per series (`frames`, keyed by series, not on each model's row), and the region components draw from it (§3, §4), growing a slot to the panel's own minimums as they place it - only the series they draw, a tier A or B series with all five bands, a hub series and a 320 series, and only what they read of it: of a bar series the four bars, the center's popup `region`, `well`, `title`, `title_controls`, `empty`, `status`, `pt`, `surfaces` and `pictures`, and the `windows`; of a hub (flagged `hub`) its `top` and `right` bars, the center's `region`, `title`, `title_controls`, `empty`, `status`, `pt`, `surfaces`, `pictures`, `close` and `level` and its `strip` (the Volume Level reference's rect), its `select` and `options` grids and its `windows`; of a 320 (flagged `pages`) its strip `top`, its `home`'s and `second`'s strips (and the second's Back), the centre's `rect`, `row`, `headings`, `pitch`, `pt`, `empty`, `empty_lines` and More, its `windows` with their buttons' seed IDs and the question's words, and its `volume`; the profile's `regions` holds what they draw by default and the looks they give what they hold - the clock's pattern off the seed's own Main SD; the looks of the tabs (`tab`), a rail's first group (`rail`) and later ones (`launcher`), the mode slot (`mode`), the Volume heading, Mute, Help and Power; the fill of a surface drawn without its art (`bar`: a surface's `art` is drawn as a derived Image where the kit has the file and the panel's seed can clone one); and the looks a source's popup (`source`: its title, empty state and status, and the labels and buttons put in it) and a window (`window`: its title, message, labels, Close, Power Down and Cancel, and the keys put in it - Mach's ghost, where its page buttons are `solid`) give what they draw, and `hub` the looks a hub's region page, source popups and windows give theirs (§3: its titles, tile labels and tiles - a tile's `glyph` the suffix it drops from its tab's icon to name its own family's, Shockwave's `_white`, so laptop_white's tile is the whole device `white_laptop` - the menu bar's keys, Volume heading, Up and Down, Mute, Power, settings and Display Control openers, Close and Help, its windows' (`window`), and its opaque or options popups' (`options`: their ground, titles, labels, tiles, a blank tile, keys, Close, and the kit `glyphs` an option's caption names)), and `page` the looks the 320's pages give theirs (§3: the strip's words, a column's heading, the empty state, the question's and the waits' words (`message`), the keys, More, Back and Back where it ends the strip (`strip_back`), the Volume modal's Cancel - Shockwave's and Turbulence's a transparent `clear` key - and the wider art a key takes where its caption needs more than its art at the row's depth (`wider`)). Shockwave and Turbulence carry a `header` token, black at 45%, their hubs' header strip, and `regions.hub.popup.photo`: their hubs' popups stand on the page's photo, stretched to the popup. The profile's `writing` holds the template's own words, which they say: the empty state (`{name}` the source's title, `{noun}` it in a sentence's case) and Shockwave's hubs' own (`hub_empty`), Shockwave's `status`, the 320's three-line empty state (`page_empty`), the power-down question (`confirm.power`), the waits (`wait.up`, `wait.down`), Help's message and title (`help_title`) and the buttons' words. Mach's are from the hand-laid slice that built and verified; all three themes' have built and verified as region pages on the 1035 and the 725 (`archive/job-e823df9b/center/`) and on their hubs (`archive/job-e823df9b/hubs/`). |
| **README** | What the designer reads before drawing a canvas (`gdl.designsys.readme`), written around the template's grammar so that each part comes off the profile, the frame or the ledger and cannot drift from them. *Designing a panel*: one artboard per page or popup, every panel the room has in `panels`, only these components, `nav` and `does`, `states`, the program's own pages, a control on several pages one only with one `id`. *The template's grammar*: the five regions and what lives in each, per family - the bar panels (each region's component, the Header's tabs, the LeftRail's Sections under the headings its frame measures, the RightRail's and the Footer's roles as the components split them - Power and Help the Footer's wherever the template stands them, Power's caption as the template's (`regions.power`), Room Mode and Audio Control only where given - the Center's popup region, and the bars that are the template's art drawn as that art (Turbulence's header and footer, where the kit has the file and the panel's seed can clone a `PBImage`)), the hubs (the menu bar, Select a Source and the options popup off their frames, what becomes of the page, its popups on the page's photo where `regions.hub.popup.photo` says so) and the 320 (the strip, Main's keys, More and Back, the Volume window) - and where Help goes (its own `role="help"` artboard, a window on the bar panels and the hubs and a page on the 320), each beside a **template render**: the family's working page rendered off its own seed with `gdl.compose` (`template_renders`, `render_templates`: Main SD with the frame's Laptop popup in its region, a hub's Main Page showing Select a Source, the 320's first source page; and the bar panel's question and the settings window its lighting launcher opens, over its working page, beside *Windows*), its translucent chrome composited over the photo as the panel shows it rather than as GUI Designer's snapshot paints it (`compose.BINARY`), downscaled to a WebP of 320 to 640 px - `templates/<theme>-<series>-<page>.webp` in the system, and on its `Template` card; the owner's call 3 keeps them in the private system only. *The working page*: the regions on a Page, each tab's own glyph from the kit (Streaming's nearest), and a complete room - Start, the page the panel boots to (`Main.dc.html`, `examples.start`), the working page, a source with no controls and one with them (a camera's heading over its keys, `examples.camera`), the settings windows its launchers open (worded as `writing.voice` says), Help, the question and its wait - every Page with `panels` and its `theme`, every place the example chooses on the 10 px nudge and every set in a `Group` with the room the room's panels need, so the room translates clean on every panel it lists (`tests/test_design.py`). *The center*: a source's popup by `role`, its chrome, its controls, its empty state naming its source, its device picture and `device` where the template pins one (Turbulence's), and what a hub - on its photo where it stands its popups there - and the 320 make of it. *Windows*: what a window looks like on the design panel off the frame - each settings frame and the titles it is drawn for, the question's answers in order and in their looks - each `role`, Close and Cancel, a modal without a role and its Close (`nav`, or `does` where more than one page opens it), a settings window's picture as an `Image` where the system offers one (`examples.image`), a hub's settings on its photo, and the owner's rule that nothing forces a confirmation. *Writing*: the profile's `writing` - the template's own words - and its `writing.voice`: the rules its captions, headings, titles and messages keep, the words it says instead of ours on a button (`instead`, as the caption lint applies it), the capitals it sets itself (`caps`) and its sentence-case captions (`sentence`), each `_source` naming the seed and its pages. *Before you hand it over*: the designer's checklist, then what Claude Code checks after the handover - translate and the critique loop (§1, step 3). *Pages without regions*: free pages - Start, a mode chooser - and how they draw and carry (the bar themes). *Differences*: each ledger `deviation`'s `here`, each number in it one its own entry gives (*Truth*). Then the Layout, written from the frame (`gdl.designsys.frame_layout`: every series' bands and popup region in a table, then the design panel's regions - each set with its first rect and its step, each item and surface, and its windows), with the profile's hand-written `layout.regions`, which the claim lint holds to the template; *Every panel the room has*, the room a design leaves for each panel the system serves - its touch minimum and gap measured here, how much wider than its words a box must be, what a hub's rail holds, how deep and wide a panel of rows' rows are and the order it takes a page's controls in - from the scale, touch minimum and type floor that panel's layout applies; the themes, the visual foundations, the iconography (`iconography`) and *Consuming this system*: the global, the bundle and the font link. Afterburn draws its chrome as art and has no region components: its grammar is told in words beside its renders, and since a page drawn at its own spacing carries to the 1035's scale alone - loose, its left rail only scales and grows into itself on a 725, and an icon `list` button's caption needs 177 px of the 725's 145 px rail at 16 pt - its room is drawn whole in the layout that carries to the four panels it lists (`RAIL_CELL`, `RAIL_BOX`, `SET_CELL` in `gdl/designsys/__init__.py`): the left rail one Group under one heading, the sources in a Group over the divider and the template's own 880x525 PopupRegion in MainArea with no date and time, every source popup that size (on the 320 each a page of its own, the region left off), the right column in a Rail with no Volume heading that stacks on every panel, the drawn one too, sets and windows with the 525's room, and every source popup and window written out, each window on a Panel card where the squircle stands - and its windows' words are its `layout.popups`. The components' own READMEs and previews are drawn from the profile too (`examples.source`, `examples.help`, `examples.group`, `examples.panel`, `examples.image` where the system offers an Image, its variants, type styles and tokens, `font.note`, `themes_note`); the region components' point at the README's grammar for the hubs and the 320, and the Header's and Footer's say which of their bar surfaces are the template's art. The round-three designers' asks are each answered there: where Help goes, how a source shows its controls, what a window looks like, which words the template uses, what a hub and the 320 make of the page. So are round four's (`tests/data/round4-<theme>`): Help in your own words as one Label with room, not a stack of one-line Labels; a button's widest caption, a state's own too; the 320's keys and column headings and the words they hold, a Group's title its heading there alone (in capitals on Mach's and Shockwave's, as their templates set theirs); what a hub and the 320 draw by themselves - Select Source, the options, the display popup, the Volume strip and window - and what a designer may draw in their place; and where the 725 keeps the RightRail's audio place. And the four things Afterburn's revising designer guessed (`tests/data/round4-afterburn-revised`, their notes): the order the 320's rows take a page's controls in, how much its main holds, how tall a heading's row is and where it stands, and where Start's button may stand. |
| **Truth** | Each theme's ledger, `gdl/designsys/truth/<theme>.json` (its schema, `schema.json`, beside it): one entry per claim the profile or its README made that the template's own pages contradict - what we said and where (`claim`, `where`), what the template does with the seed and the pages it was read off (`template`), and its `status`: `fixed`, the profile or README now says what the template does (`fix`: a profile key, dotted, a list item by its index or `name`, and the words it `says`, or the README's words); `frame`, the region frame draws it (`frame`: the frame key, in a series or any); or `deviation`, we differ on purpose (`reason`: a gate, or a capability the panel or the system lacks; `here`: what the system does instead, in the designer's words, which the README's *Differences* says). `gone` holds words of the old claim that must not come back; `builds` says what a fix changes in what builds. `python -m gdl.designsys audit <theme>` (`gdl/designsys/audit.py`) reports an entry the schema refuses, one with no status, a `fixed` whose key or words are absent, a `frame` whose key no frame has, a `deviation` with no reason, a number in a `deviation`'s `here` that its own template, reason and evidence never give (the claim lint leaves *Differences* to its entries), and a `gone` still said, then the **claim lint**'s findings: a sentence of the profile (its `_`-keyed sources and its `panels` table aside) or of the README and component READMEs that says what the template does - "as the seed draws it", "as Mach's own pages put them", "every Mach 1035 page", a number said to be the template's or the seed's - and is backed by none of a ledger fix's words, the Layout (the frame's) or a `_` source over it that names the seed and a page (one the frames or the ledger name, or every page, in those words: `pages()`, the function a source was read with, is no page). It is mechanical on purpose: it flags rather than guesses, and the fix is to cite the page or say less. Then the **caption lint** (`audit.caption_lint`): every Button caption and Section, Page or Group `title` in the README's and the component READMEs' code, and every caption example of the profile (its `examples`' and `regions`' `text`, `writing.buttons`, `writing.voice.launchers`), against the template's case and voice - a generic verb (Submit, OK, Yes, Done) where the template names the action, capitals where it writes Title Case (an acronym, and the capitals its `caps` lists, aside), a caption not in Title Case (its `sentence` ones aside), a caption it words otherwise (`instead`: Mach's Lighting, not Lighting Settings). It exits non-zero on any finding; a theme at zero is done. |
| **Donor** | The seed the panel is built on. The canvas's design system therefore also chooses the donor. |

A profile is checked against the seed's **built artwork**, not only its model
and the guide: the first Afterburn system drew a slider as a filled slab and
filled buttons with the accent, and both read fine off the numbers.

The first cut targets **1280×800** - the TLP Pro 1025/1035 family, which every
template has a seed for. Other resolutions follow the seeds (`seeds/README.md`).

**Icons are the kit's images, not its fonts.** Extron's icon fonts carry no
license field (`gdl/fonts/README.md`), so a design system, which takes its art
to claude.ai, draws no glyph and names a kit image instead. An icon the kit
does not have draws as a dashed box and the translator refuses it. A spec
written by hand can name a glyph (`icon`, `SKILL.md`).

## 3. Components that say what they are

Every component draws the template's look for the designer and carries its spec
fields on one element as `data-gdl` JSON:

```html
<button data-gdl='{"kind":"button","name":"Laptop","states":[...],"press":"Live"}' ...>
```

So the translator reads what a control **is** instead of guessing it from
pixels. On the canvas they are `<x-import component-from-global-scope=
"ExtronAfterburn.Button" ...>`, attributes as props.

| Component | Spec | Carries |
|---|---|---|
| Page | a page or popup | `name`, `kind` (`page`, `popup`, `modal`), `group`, `start`, `reached-by`, the `theme` (background and accent) or an accent `scheme` alone; `panels` (every panel the room has, the first the one it is drawn on) and `preview` (one of them to draw it as); on a bar theme `role` - `source` on a popup, `settings`, `help`, `confirm` or `wait` on a modal - with `title` and `topic` (§4), and on Turbulence a source's `device`; its chrome as derived Panels, Labels and Buttons |
| MainArea | nothing of its own | a frame: its children are placed inside the template's main area - on each panel, that panel's own |
| Rail | nothing of its own | a frame: its children stack in the rail beside the main area, or across below it where there is no room beside it; a button in it fills it across, its caption needing only the button's own padding |
| Group | its members; on a smaller panel, the popups or pages it becomes | `title`, `cell`, `gap`, `cap`, `joined`: equal cells in its box - in place, paged as popups in its box (Previous and Next under its cells, or at the row's ends in a box one cell deep - arrows where their words leave no room), or pages of their own opened by a button, by the panel's size; in a modal or a popup on a large or mid-size panel only in place, since a popup shows no popups |
| Button | `button` | caption, `variant`, `icon`, `states` (names, each with its own look, caption and kit image), `press` - the state the panel shows while it is held, which the canvas draws while it is held too - `nav`, `does`, `id` |
| Label | `label` | text, `type` or `size`, `color`, `align`, `does` |
| Panel | `panel` | `fill`, `stroke`, `border` |
| Image | `image` | the template's own art, offered where the profile says what its template draws with one (`examples.image`) and the design panel's seed can clone a `PBImage` - Turbulence's: `image`, a kit file's name, `layout` (`fill`, fitted, the default, or `stretch`), an optional `fill` under it; named on a panel whose seed has none (its series' `kinds`). The regions draw the template's art surfaces as derived Images too (Turbulence's bars, a source's device picture) |
| Line | `line`, or a `panel` of its box on every panel the canvas lists where any one's seed has no line to clone - most of Mach's, Shockwave's and Turbulence's sizes; level or upright, its box is the band it draws | orientation, `color`, `thickness` |
| Slider, Level | `slider`, `level` | `orientation`, `fill`, `track` and `thumb` sizes (and `thumb_height`, where the template's thumb is not square), `does`; a slider also gets its scheme's `thumb_image`, a level its scheme's `bar`, and a level is built `track` wide, centred in its box, since Build draws a level over its whole box |
| Clock | `datetime` | `format` (`time`, `date`, `datetime` or a .NET pattern), `color`, `size`, `align` |
| PopupRegion | `popup_ref` | the popup `group` shown there |
| Header | nothing of its own; its surfaces as derived Panels | a region (Mach, Shockwave, Turbulence): the bar across the top. A child's `slot` says what it is - `source` a tab at the template's tab places, the tabs one joined set of one size; `start` and `end` at the bar's ends. A tab takes the template's variant (`regions.tab`), measured look and caption alignment unless it sets its own, and an indented caption as many leading spaces as clear its icon (`kit.icon_right`). Where that panel's template names its tabs by a `twin` (Shockwave's 1035 and 1535), the tab draws no caption and a derived, caption-only `<name> Caption` across its foot at the twin's depth says it, in the twin's colour in every state - the tab's mirror, with its ID, `nav`, `does` and state names (`docs/idmap.md` Mirrors) |
| LeftRail | nothing of its own; its surfaces as derived Panels | a region: Sections, the template's rail groups in order; a first group's buttons take the template's rail look (`regions.rail`), a later group's its launchers' (`regions.launcher`), unless they set their own |
| Section | its heading as a Label; nothing else of its own | `title`: the group's heading (`<title> Heading`) where the template draws one; its children at the group's places, down its step, one joined set of one width - a column's groups one width where the template draws them so |
| RightRail | nothing of its own; its surfaces as derived Panels | a region: the template's Volume heading, slider (a level where the seed has none) and Mute, keeping the seed's IDs for Volume and Mute (below), one joined set - the right rail's group; a child's `slot` (`heading`, `volume`, `mute`, and `audio` where that panel's template stands Audio Control in its right rail) takes that place; on a panel whose template keeps Audio Control in its left rail instead (Shockwave's 725: its second group, the frame's `audio` role there) the `audio` child goes into that Section at that role's place, in the launchers' look - and where there is no such Section, or it then holds more than the rail has room for, it is named with what to do, the Section left as drawn |
| Footer | nothing of its own; its surfaces as derived Panels | a region: the template's clock, Help and Power - wherever the template stands them, Shockwave's Power at the right rail's foot - keeping the seed's IDs (below); `help` and `power` name the artboards they show; a child's `slot` (`mode`, `clock`, `help`, `power`) takes that place, the mode slot in the template's look (`regions.mode`); the cells the template stands 2 px or less apart one joined set (Mach's Help and Power, Turbulence's Help and Room Mode) |
| Center | its `popup_ref`; a well the template draws round it on the page as a derived Panel (`Center Well`) | a region: a PopupRegion at that panel's own template's popup region, `group` (default `Sources`) and `name` (default `Controls`) |

The region page's fixed chrome - the Footer's Help, Power and the control in
its `mode` slot, the RightRail's Volume and Mute, drawn by default or the
designer's own in that slot - keeps the template's seed ID (the frame's
`ids`: Help 8117, Power 8022, Room Mode 8118, Volume 8024, Mute 8021) by
default: the bundle writes it as the control's `seed_id`, and the translator
pins it on every page that draws it and every panel where the designer gave
the control no `id` and no other canvas control has that ID, its page's band
stepping over it
(`gdl.design.pin_ids`, `docs/idmap.md` §7). A designer's `id` always wins, and
is a whole number from 1 to 65535: the bundle passes anything else to the spec
as written, where `gdl.spec check` refuses it. A
heading's label is no chrome a program drives, and takes its band's.

Colors are the template's token names, and the spec's theme is exactly the
tokens used, resolved for the canvas's accent scheme.

## 4. What a canvas means

- **An artboard is one page or popup.** Its root is one Page. A popup is
  `kind="popup"` with a `group`, or `kind="modal"`; the start page is
  `start="true"`, else the first artboard.
- **A button's `nav` names an artboard** by its file stem (`nav="Help"` is
  `Help.dc.html`), never by a Page's `name`: the Design type forbids spaces in
  a file name, so the Page named Main SD is `MainSD.dc.html` and `nav="MainSD"`. The button draws as that link, so Play follows it, and the
  translator turns it into the target Page's name.
- **What a control does is `does`**, in words, on the component. A page the
  program shows by itself (an incoming call) is `reached-by="program"`.
- **A control is known by its page and its name**, so two controls of one
  name on a page, and a canvas control named like one the layout draws (a
  Group's Next, Previous, Back, Up and Down, a `<name> Title`), are refused
  by name at translate. A panel listed twice in a Page's `panels` is one panel.
- **Anything that paints and is not a component is refused**: text, a fill, a
  border, a shadow, an image, drawn any other way. The translator names it and
  its box. Containers that paint nothing are fine, which is how the designer
  lays controls out with flex and grid.
- **An icon is a kit image, per state.** The component resolves `icon` and
  the state's look to the kit file for the page's scheme and carries the file
  name; the translator gives the spec each file's kit path, and a name the kit
  lacks is refused. The caption is placed as the template places it - line
  breaks under a source's icon (as many as the seed's own tile of that size
  takes, a variant's `breaks`), leading spaces past a list button's. On a
  smaller panel than the one drawn the tile shrinks and the type stops at the
  panel's floor, so the translator keeps only as many breaks as still fit in
  the button there.
- **One template and one accent scheme per panel**, and page names unique.
- **A working page names its regions** (Mach, Shockwave and Turbulence;
  `docs/superpowers/specs/2026-10-22-region-frame-design.md`). A Page holding
  a Header, LeftRail, RightRail, Footer or Center is a region page, and on
  each panel each region takes its band from that panel's own series' frame
  (§2) - the 725's bars from the 725's template, not the 1035's scaled - and
  places what it holds by meaning, not by where it was drawn: a source at the
  template's tab, a Section at its rail group, Volume, Help and Power where
  its own are, the center a popup region. What it holds takes the template's
  look where the designer gives none - the profile's `regions`: Mach's
  `solid` rail and `footer` Room Mode; Shockwave's `button` rail, `tile`
  launchers, gray `square` Mute that lights red and `pill` Help and Power; Turbulence's
  `ring` rail, `dock` launchers and Room Mode, volume_mute ring and
  vc_power-dn Power - a dock's two words on two lines, a state's own caption
  too (measured on one, Mic Mute's 'Mics Muted' grew Turbulence 725's rail
  column from 112 to 128 px, into Help beside it). The bars' surfaces are drawn as derived Panels named
  per region (`Header Left`, `Footer Bar`), since a painting wrapper would be
  refused as stray; a surface that is art (Turbulence's header and footer)
  is a derived Image of that art, stretched over its band as every
  Turbulence seed lays its bars out - where the kit has the file and the
  panel's seed can clone a `PBImage`, else its one measured colour,
  `regions.bar`. A slot under the panel's touch
  minimum or type floor grows as any control does, kept to its band where the
  band holds it: the extra goes on the side that meets nothing, so Help grows
  away from Power, and a set's next slot moves on by the template's seam, so
  the 835's 67 px minimum takes Mach's rail buttons to 68 apart. A set grows
  as one - every tab of a row, every button of a column, to what the one
  that needs most needs - and a surface keeps to what grew by it: one that
  holds a control grows to hold it, one a control stands beside keeps the
  template's seam to it and is as deep as it, so a bar stays one flat band.
  A header's tab row and each rail group - the right rail's volume, heading,
  slider and Mute, among them - are `joined` sets, at the step Extron draws
  them on each series (on the 1035, Mach's 1 px apart and Turbulence's tabs 14
  and its rings 8; Mach's 725 steps its rail groups 10 px apart; owner's call
  2), as are the footer cells the template stands 2 px or
  less apart; the gap check (`gdl.spec`, any axis) passes over each set and
  keeps 2 mm between it and anything else. Where the template's own seam
  between two sets is under 2 mm - Turbulence's last rail launcher 1 px from
  its footer's Help, Shockwave 725's Mute 10 px over Power - the page opens
  it to the panel's gap: each side gives what it can spare above its own
  need, the one whose giving way moves fewer controls first (Turbulence's
  Help, not its column of launchers), and what cannot be opened is named. A
  footer's clock gives way to a control grown into it, about its middle. A
  region page lacking a region the template always draws is
  outlined on the canvas and named as a note in the translate report, and
  still builds; a Start or other splash page says `splash="true"` and is not.
  On a turned panel a region page is refused by name - its header becomes a
  left band, which is not drawn yet - and so is a region on a popup or
  modal; the hubs and the 320 draw it in their own grammar (below). The Center is that panel's own template's popup region on every
  panel. A Page holding no region is laid out exactly as before.
- **On a hub (the 520s and 535s) the same region page is drawn in the hub's
  grammar**, from the hub's own frame (its `right`, `top`, `center`, and the
  `select` and `options` grids `frame_of` measures off its Select a Source
  and its settings opener's popup): no header bar, footer or left rail - a
  right menu bar, and one popup region filling main (the Center, its group
  the Center's, `Sources` by default) in which every popup appears. The
  RightRail and the Footer's Power are the menu bar - its surface `Menu
  Bar`, the Volume heading (white on Mach's bar), Up and Down (derived, with
  the hub's seed IDs 8120 and 8121: Mach's kit chevrons, Shockwave's a
  chevron its Open Sans draws, Turbulence's rings), Mute (its word on Mach
  and Shockwave), the settings opener (derived, 8040: Settings on Mach, More
  on Shockwave and Turbulence - Turbulence's its ••• glyph over its word),
  Shockwave's and Turbulence's Display Control (derived, 8115) and Power
  (Shockwave's square power glyph in its crimson ring) - one stack down the
  bar at the template's places, grown to the touch minimum and to its words
  at the panel's type floor (Mach's Mute, set at 13 pt where the 525's floor
  is 18, grows from 66 to 81 px inside its 98 px bar), its seams closing up
  where they no longer fit (Shockwave 535's 81 px buttons grow to 104), one
  `joined` set; the volume slider is the hub's level, `Volume`, in the
  `Volume Level` strip beside the bar, a popup of its own the program shows
  in the template's own ground with its level where and as the template
  draws it (the frame's `center.level`). The page derives popups of main's
  group: `Select Source` first, wherever the page has a Center - the
  Header's source tabs as its tiles at the template's places, each the same
  control (name, so ID, `nav`, `does`), an icon tile's caption in a derived
  label under it, under the hub's title and its header strip (Shockwave's
  and Turbulence's black 45%, the `header` token), the Footer's Help at its
  place; the options popup the settings opener shows (`Settings` on Mach,
  opaque `page`, its keys the raised `ghost` the template draws on it;
  `More Options` titled Choose an Option elsewhere), holding the LeftRail's
  later Sections' launchers, an Audio Control and the Footer's mode
  launcher, each the template's tile with its caption the label under it -
  the kit's glyph where one names what it opens (`regions.hub.options.glyphs`:
  Lighting's bulb, Audio's speaker), else the kit's blank tile - in one
  centred row while they fit, else in rows centred on the template's; and
  the LeftRail's first Section's popup (`Display Control`, which the bar's
  Display Control opens; on Mach `Display Settings`, from a derived Display
  tile in Settings) - each with its title and a Close back, the options and
  Display Control on the page's photo where the template's are (Shockwave's
  and Turbulence's), Select a Source on none, since there it is the page's
  own grid. The program
  shows `Select Source` first (`reached_by: program`), whatever the boards'
  order. What the hub has no place for - the footer's clock, a Header's
  start and end - is named as a note and listed in the page's `left`, which
  `pin_ids` and `gdl.idmap check_panels` let be absent there; everything
  else on the canvas is on the hub, with its 1035 ID. The look of what a
  hub draws is the profile's `regions.hub`; a launcher's own look stays its
  own there.
- **Two region pages, and a window of a derived one's name.** What a region
  page derives on a hub (Select Source, the options, the display group's
  popup, the Volume Level strip) and on the 320 (its Volume modal) is named
  by the template, not the page, so two region pages - Main SD and a call
  page - derive each twice. The translator (`_one_name_each`) makes it one
  popup where both pages derived it alike - the same controls, by the IDs
  the design panel gives them (`identities`): the Volume strip and the
  320's Volume always are; where they differ - each page's options hold its
  own launchers, its display popup its own first Section - the later page's
  takes its page's name in front (`Video Call More Options`), and what that
  page derived to open it and close back to it follows. A board the designer
  drew under one of those names (a Display Control settings window, as the
  grammar invites) stands in for the derived one that holds nothing it
  lacks - every canvas control by name, kind and ID; a Section's heading,
  which the board's own title says, is listed in the page's `left` - where
  it is the same kind of window in the same group: it is that window, kept
  as drawn. One that lacks any is not, and the derived one is renamed. A hub
  source or settings popup the designer drew closes back to the grid that
  shows it; where two pages' grids differ and both show it, its Close has no
  `nav` - the program's, as a window opened from two places is. `pin_ids`
  holds a control to every panel by its ID: one a page's copy held is still
  there in the window that is one.
- **On the 320 the same region page is drawn as the 320's pages**, from the
  320's own frame (its strip `top`, `home` and `second` records, the centre's
  first `row`, `headings` and steps `pitch`, the sizes it sets its title,
  headings and empty state in, `pt`, its `empty` rect, More, its windows and
  its `volume`): no bar, rail or footer, every page under the 36 px title
  strip (derived: `<page> Strip`, the strip's ground, and `<page> Title`, its
  words at the template's size and seed ID). `Main` is the template's Select
  a Source - its strip says the home page's words - and, since a region
  page's Header tabs are controls with IDs and the 320's template chooses
  sources off screen, holds the Header's tabs under the strip as the 320's
  keys, two to a row at the template's columns, at least its touch minimum:
  the same controls (name, so ID, `nav`, `does`), in the page's key look
  (`regions.page.button`: Mach's shade `solid`, Shockwave's 504x440 `key`,
  Turbulence's square `button`), a tab's own icon and type left to its
  header. What the template keeps off its pages - the LeftRail's Sections,
  the volume's heading and Mute (and an Audio Control), Room Mode, Help and
  Power, a Header's start and end - goes on over pages of Main's own (`Main
  2`, `Main 3`), each a column under its heading where the drawn panel's rail
  draws one, two columns to a page at the template's places, the rows as deep
  as the template's and its columns hold under the headings at the 320's 14
  pt floor - a heading reaching into its keys' clear tops as far as the
  template's does (Turbulence's 14 px); each page's strip titled with the
  Sections it holds, or the first's where they would not stand clear of Back,
  or `Main`. A Group in a Section gives the Section its members; a slider
  there is a level (below). More (derived, `<page> More`) stands where the
  template's first page stands it, at the foot's right; Back (`<page> Back`)
  where its second page does - Mach's at the strip's end, the strip then the
  template's shape short of it; Shockwave's and Turbulence's at the foot's
  right, and at the strip's end where More stands there (Turbulence's there
  the kit's return key, `regions.page.strip_back`: its Back key's word is 5
  px tall at 40). Where Back ends the strip, the strip and its title are as
  deep as Back, the touch minimum: the template's 57x36 Back is under it. A
  title the strip shares with Back is centred where it fits the span Back
  leaves, else centred on what Back leaves of the strip; a designer's title
  that fits neither is named. A key keeps the panel's 2 mm from More and Back
  where they stand side by side, a column moving left clear of them while the
  columns before it can give way. A column of keys whose art is narrower at
  the row's depth than a caption needs takes the theme's next wider art
  (`regions.page.wider`: Shockwave's 712x440 and pill) - only an art that, as
  wide as its column may be, is still the touch minimum deep and holds the
  caption. With none (Turbulence's: its only wider art, the 720x180 bar, is
  23 px deep at a column's 94), the key keeps its own art at the row's depth
  and a caption of two words or more goes on two lines where that holds it
  ('Doc' over 'Cam'); one longer still runs past the art's sides
  (`docs/ROADMAP.md`). The volume slider is the level in the template's
  `Volume` modal, which the program shows (`reached_by: program`): its strip
  where the template draws one (Mach's, `Volume Strip`) and its level where
  and as the template draws it, in the template's own colours (Mach's #4B4B4C
  and #E4EDF5: template chrome, which the six-colour cap exempts - the
  translator adds the frame's colours to `_template_colors`), its glyphs over
  and under the level (`Volume Up Label`, `Volume Down Label`, saying + and
  -, since the template's icon faces are not the system's), and its
  transparent Cancel over the rest of the screen where the template has one
  (`Volume Cancel`, the `clear` variant: Shockwave's and Turbulence's; Mach's
  has none, and the program puts it away). What the 320 has no place for -
  the clock, the Center's popup region (`Controls`), since each source is a
  page of its own - is named as a note and listed in the page's `left`; being
  the template's grammar, not the designer's to change, it does not outline
  the page (nor does what a hub leaves off). What the layout adds keeps a
  seed ID the frame has - the strips' (6075 on Main, 6008 on a source's first
  page, 6009 on a later one), More's 8010, Back's 8011, the Volume modal's
  glyphs (7023, 7026) and Cancel (8001), the empty state's lines (6060 to
  6062) - on the first control that carries it, by page and name
  (`gdl.design.pin_ids`); the rest take IDs from 50001, and what the 1035
  draws too (a source's `<name> Title`, the question's Power Down and Cancel)
  has one ID on every panel, from 50001 (`docs/idmap.md`). The look of what
  the 320 draws is the profile's `regions.page`.
- **A source's controls are a popup with `role="source"`** in the Center's
  group (default `Sources`). On each panel it is that panel's own popup
  region - the 725's from the 725's template, not the 1035's scaled, where a
  popup without the role still scales with main, and one that comes out
  larger than its region there is named as a warning - with no fill of its
  own, and it draws the template's chrome from the frame and the profile, as
  derived controls: Mach's framed shade well (its title bar, 1 px of photo,
  its body, `<name> Title Bar` and `<name> Well`) titled at its left;
  Shockwave's 40 pt title centred across its top, over the translucent well
  the Center draws on the page; Turbulence's large centred title over the
  device picture its template pins at its top left (`<name> Image`, the kit's
  `1152x1152_<device>.png` fitted, behind the words, where that panel's seed
  draws that device - each its own size, the 1035's Doc Cam 326x288 to its
  Laptop's 293x257 (the frame's `pictures`), and the Laptop's for a device
  the seed pictures for no source): the
  Page's `device`, else its `name` or `title` where the kit pictures one
  (Laptop, PC, Doc Cam), else the names its seed pairs with another device's
  picture (`regions.source.devices`: Aux the iPod's) - with none the place
  stays empty and the canvas says so, without outlining the page, and a
  `device` the kit has no picture of is refused. `title` sets the title (`<name> Title`),
  its `name` else, where the template titles a source with controls (the
  frame's `title_controls`: Turbulence's Doc Cam at the popup's top) or one
  with none (its Laptop, 40 px lower). With no controls in it, it says the
  template's empty state in the profile's `writing` (`<name> Empty`) - Mach's
  and Turbulence's "Laptop is currently selected. There are no controls for
  this device.", Shockwave's "Please connect your laptop." over a
  `Disconnected` status (`<name> Status`) the program sets, where its
  template stands it. What it says is set at the size that panel's own
  template sets it (the frame's `pt`), never under the panel's type floor:
  the 725 titles its sources 20 pt to the 1035's 24. The controls put in it
  stay where they were drawn on the panel drawn and are mapped from its well
  into each panel's - Mach's well body, Shockwave's and Turbulence's whole
  region - at one scale, in the template's in-well look where they set none:
  white labels, Mach's `ghost` keys, Shockwave's `key`s, Turbulence's
  `button`s (the profile's `regions.source`); a plain flex or grid container
  among them keeps its own layout there on the 1035, 725 and 525 and is refused,
  by name, on the 320 and the 300s (§7). One that stands under the title is
  named as a warning. On a hub it fills main under the hub's own header - its
  strip where it draws one, its title, a Close back to Select Source (`nav`,
  the one Close that knows where back is; Shockwave's the white X its hub
  draws, not the card's dark one), on the page's photo stretched to it as
  Shockwave's and Turbulence's hubs draw every standard popup
  (`regions.hub.popup.photo`; Turbulence's with its device picture under its
  title) - says the hub's empty state (Shockwave's
  hubs, like Mach's and Turbulence's: "Laptop is currently selected...",
  `writing.hub_empty`), and what it holds is mapped under the header - from
  the box round it, a gap clear, centred on the whole popup as the template
  centres its keys, as wide each side of the middle as the Volume Level strip
  leaves on its side, and scaled up no more than the hub's touch minimum is
  the drawn panel's (a hub's main is about half the 1035's band, and mapped
  from the whole well or window Mach's Audio came out half size, its heading
  grown back into its Mute; settings windows alike). With no working page on
  the canvas a hub has no Select a Source to show it from, and it is refused,
  saying so. On the 320 it is a page of its own, named the popup's name,
  under the strip titled with the source: what is put in it is the 320's
  columns - what stands one over another as drawn, a label at a column's top
  its heading, the designer's words as written - two to a page at the
  template's places, the rest on over `<name> 2` by More and Back; with
  nothing in it, the template's three-line empty state
  (`writing.page_empty`), a label a line at the template's own rects (the
  frame's `empty_lines`: `<name> Empty`, `<name> Empty 2` and `<name> Empty
  3`), its first sentence a paragraph apart from the other two as the
  template sets it; a line its words outrun at the 320's 14 pt floor -
  'Document Camera is currently selected.' - breaks onto two in its label at
  the space that leaves its longer line least wide, as the template's own
  Aux label breaks its sentence, growing up into the room under the strip.
  A Group put in it is a column of its own under its title
  (a derived `<title> Heading`, in capitals on Mach and Shockwave, whose
  templates set a 320's camera column labels so - `writing.column_labels_320`,
  extrapolated to every Group title; the
  control map prints what the panel shows), its members the page's keys,
  paging as any column does; a slider, which the 320's seed cannot clone, is a level there,
  a column of its own with the derived Up and Down every level a slider
  becomes has. The template has no way back from a source on screen - it
  chooses sources off it - so the page's first Back (`<name> Back`) stands
  where its second page stands one, and says `back`: the translator points it
  at the one page whose control shows it (Main, whose key it is) - a page's
  own later pages lead back to it but do not show it. A card or a line put in
  it is named and left. On a turned panel it is refused by name for now.
- **A window is a modal with a `role`**: `settings` (or a `title` and no role)
  and `help`, `confirm` and `wait`. It is drawn as the panel's own template
  draws that window (the frame's `windows`): Mach's opaque #303030 band
  between the bars, Shockwave's #999999 card, Turbulence's navy one - a
  settings window the one the template draws for a window of its name, as
  Shockwave's Audio Control is wider than its Lighting Control, and one whose
  name the template has no window for the same on every panel: on the drawn
  panel its commonest settings window (titled, with a Close, drawn as shapes,
  drawing the most windows) and on another the one there drawing most of the
  same windows - as a derived Panel (`<name> Window`); a settings or help
  window with its title (`<name> Title`) and a Close (`<name> Close`: the word
  in a ghost cell on Mach, the kit's Close elsewhere, square, at the
  template's rect or the legal one about it); `help` with nothing put in it
  the template's message (`<name> Message`) and, with no `title`, the
  template's own title (`writing.help_title`: Shockwave's and Turbulence's
  HELP); `confirm` with `topic="power"` the template's question (`<name>
  Message`) and Power Down and Cancel at its rects (`<name> Power Down`, whose
  `does` is the Page's; `<name> Cancel`); `wait` with `topic="up"` or `"down"`
  the wait, with no buttons. Wording is the profile's `writing`; a topic it
  has no words for is named, and so is a `role` the Page's kind does not take
  (a typo drew a window with no way out). Its title and message are set at
  that panel's own template's sizes (the frame's `pt`: Help's message apart
  from the confirmation's), and a message keeps the lines the template sets it
  in (the frame's `lines`): where the system's Open Sans, wider than the Light
  the templates set their messages in, would take more, its box widens about
  its middle inside the window - Turbulence's 1035 power-down question is one
  line. Close and Cancel go back to the page that opened the window, which
  only the program knows: they carry what they do and no `nav`. What the
  designer puts in a window stays where drawn on the panel drawn and is mapped
  from the body under its title there into the body under its title on each
  panel - the 725's and the 525's titles stand lower in their windows than
  the 1035's, and mapped window to window a line clear of Shockwave 1035's
  HELP came out under the 725's - in the template's window look where it
  sets none (`regions.window`). On a hub a settings window is a popup of
  main's group (the Center's, which the translator binds it to) filling main,
  as the hub draws its settings (Mach's opaque #303030, its keys raised), with
  the hub's header, its title (`<name> Title`) and a Close back to Select
  Source; Help, the question and the wait stay modals in the hub's style
  (`regions.hub.window`) - Mach's on the scrim with no window, Help's title
  centred and its Close the back glyph; Shockwave's and Turbulence's cards,
  rounded as each panel's seed rounds them, Help's Close at the screen's
  corner where the template stands it, off the card. On the 320 the template
  draws its question and its waits as pages (`confirm`, `wait`): the page, on
  the photo or, where the template's stands on the page's own ground, on that
  (the frame's window `art`: Mach's #303030), its rounded box (`<name>
  Window`), its words in white (`regions.page.message`) - the 320's own
  question where it says its own (the frame's confirm `text`: Shockwave's runs
  on where its 1035 breaks the line) - and, for the question, Power Down and
  Cancel at the template's places and sizes, a caption that does not fit one
  line there on two, as Turbulence's own Power Down - Cancel back (`back`) to
  the page whose Power asked. The 1035 draws the same question, so its buttons
  have one ID on every panel, from 50001, not the 320 seed's 9028 and 9029. It
  draws no settings or Help window: each is a page under the strip, titled as
  on the 1035, what is put in it the 320's columns, Help's message under the
  strip, and Back (`back`) to the page whose launcher opened it. Words alone
  - Help in the designer's own words, one Label or a few - are set as the
  template sets Help's message: across the page under the strip, clear of
  More and Back, each Label as deep as its words wrap to at the floor, one
  under another, going on over `<name> 2` by More and Back where they do not
  all fit; a Label too long for a page of its own is named (in the columns
  each was a key's 74x50 cell on Mach, and a sentence ran out of it). On a turned
  panel a window is refused by name for now. A source popup or a window on a
  canvas that lists no panels is drawn on the system's own panel, as a region
  page is. What a source popup or a window draws is derived navigation and
  chrome - in the ID map, with IDs from 50001 up keyed by its popup and name,
  the same on every panel (`docs/idmap.md` §7).
- **A Page's `panels` are the room's panels**, the first the one it is drawn on,
  and every Page lists the same. Each panel is built from the canvas as the
  design system lays it out for that panel (§3, `docs/design-rules.md` §1):
  - its own size, background art and main region, each control grown to that
    panel's touch minimum and its caption to that panel's type floor;
  - on a large or mid-size panel (tiers A and B), `MainArea` and the `Rail`
    each mapped by one scale, and the Page's own children by one scale for
    the page, centred - a modal's card stays centred on the screen, as
    Extron's own 525 centres its modals - each grown to what it needs and kept
    on the page: one drawn flush with the screen's edge (Afterburn's left
    rail at x 0) grows inward, since Build moves a control that crosses its
    page's edge. Where the template draws its bars as
    controls (Mach, Shockwave and Turbulence: the profile's `layout.bars`),
    they go through both panels' bands instead: main's edges cut each page
    into a header, a footer, the bands beside main and main, and a child
    moves with its band. An edge on a cut, or within 4 px of one, stays on
    it, so a bar across the page stretches with it at the panel's own depth
    (Mach's header, 64 deep on the 1035, is 60 across the 725) and an end cap
    fills its band; a child with no edge on one keeps its shape at its band's
    scale; a container spanning one way, edge to edge, scales by that way's
    band, so a row the depth of its bar stays in it; one grown to a touch
    minimum deeper than its bar stays on the page; and on a hub, whose main
    reaches its top and bottom and its left edge (the Page README names each
    system's), the header, the footer and a column beside main get bands of
    their own carved from main at the page's scale, in whole pixels - the
    touch minimum deep where the band holds a button, as deep as a Group's
    cells where it holds one, and Extron's hub templates keep a title strip
    at the top of main - a Group grown past its box keeps to the page as a
    control does, a bar or card drawn as a Panel grows to hold what was drawn
    in it (Shockwave's header under its source tabs, its footer capsule
    under Mic Mute; elsewhere a bar keeps its series' own depth, as Extron's
    templates draw it), the right column goes
    to the menu bar, and `MainArea` and the `Rail` keep to what those bands
    leave, a control grown to the touch minimum staying inside main - as it
    does on every theme, where main reaches the screen's edge (Afterburn's
    sources Group grew 17 px above the 525's). On the panel the canvas is
    drawn on they stay as drawn;
    on a small panel (tier C, the 320's) they reflow into rows in the order
    the controls were placed - and in a template that draws its bars as
    controls a Page is drawn as Extron's own 320 templates draw theirs: its
    header bar is the series' 36 px title strip, with the labels on it where
    they fit there, and everything else - the Page's own controls, its
    `MainArea`'s and its `Rail`'s, since the 320 has no rail - reflows into
    rows in main under it, region by region (the header's, main's, the columns'
    left to right, the footer's), each region's in design order. Rows one
    screen cannot hold go on over pages of their own (Home 2, Home 3), each
    under the strip - a copy the layout derived - with Previous and Next at
    main's foot; a row never splits, a heading goes on with the row it
    heads, and a card goes behind its controls on
    each page they land on. In a template whose chrome is its art
    (Afterburn's) the Page's own controls and its `MainArea`'s are likewise
    one set of rows, in main over the band the `Rail` runs across: the main
    area's first, then the side columns' left to right, each in design order;
    a heading - a Label whose foot meets the Group under it within the
    canvas's gap - stands at the left of that Group's one button, in its row;
    a horizontal `Line` stands across the gap between the rows it was drawn
    between, 2 px clear of each (held to its own 2 px, Main SD's Divider
    touched its sources and its popup region on the 300); and where the rows
    need more than main holds, a side column's row stands beside the first
    earlier row of another region it fits beside. They were two, the Page's
    over the whole screen and `MainArea`'s in main, each centred, so a
    left-rail heading landed on a main-area control. Past what main holds
    the page is refused: it does not go on, as a Group does - the refusal
    gives the depth its rows need one under another, as the README counts
    them, and, where a row moved, beside. Two rows that each hold a Group - a
    button there - keep the panel's gap apart, as two of buttons do. No 320
    seed has a standard popup to clone (every series' `kinds`: Offline Page
    and Volume are modals), so there Afterburn draws every standard popup as
    a page of its own - a bar theme draws a `role="source"` popup so and
    refuses one with no role, by name, where the build would stop at the
    applier. Afterburn's page is named as the popup is,
    on the page's photo, as that template gives each source one: what is put
    in it stands in rows in main, laid out from the popup's own box, and a
    derived Back (`<name> Back`) stands at the foot's left, where a Group's
    pages stand theirs, saying `back` - the translator points it at the one
    page whose button shows it (`Main SD Sources`, the Sources Group's page).
    A `PopupRegion` has nothing to show there, and is left off - named, and
    in the page's `left`, as the region page's 320 leaves its Center. Kept a
    popup, a source was shown from the Sources Group's own pages, which hold
    no reference to its group, and the ID map refused the room. The README's
    *Every panel the room has* says all of it, with how deep and wide each
    panel's rows are (Kind). Words wider than the screen break into lines, a
    line as GUI Designer lays one out. A popup region in a row is rounded as
    its popups are scaled, a popup being its reference's size (Standards
    p.70): rounded up, one came out 223x133 over 222x133 popups. A region
    wider than a row holds (the 300 Portrait's 294 px, its popups 307) is
    named with the widest it can be drawn. A plain modal holds one screen: it
    is a popup over a page, and it does not go on over more (a window - a
    modal with a `role` or a `title` - is a page on a bar theme's 320, and
    goes on over a second);
  - a `Group` in place, paged in its box as popups with no fill of their own -
    the page shows through, as through the seed's own group popups - or turned
    into pages of its own opened by a button, by the panel's size; its
    Previous and Next under its cells, as arrows where their words are wider
    than its box and one over the other where even the arrows do not fit side
    by side (a one-cell column: Afterburn's left rail on a 525); its gap,
    which scales with the page, gives way to its cells first, down to the
    panel's 2 mm, before it pages; a joined
    Group (a segmented control) stays one row, but where that row is wider than
    a small panel's screen - Shockwave's four source tabs on the 320 - it
    opens pages as any Group does;
  - a Slider a Level with Up and Down where the panel's seed has no slider - its
    series' `kinds` in the profile's `panels` say which: the 520s', 535s' and
    320s' seeds, Afterburn's 300M either way up and Mach's 300M. Where a
    Page's own slider is a level, Up and Down stand beside it, one at each end,
    so it keeps the slider's whole length - Extron's own 520 and 535 stand Up,
    Down and Mute beside their volume level, the level the length of the
    column - and in a narrow menu bar the gap between them and the bar's
    margins share what it leaves; without room across, they are along it,
    with at least 24 px of level between them, which the 320's rows size its
    cell for. They take the look of the button the canvas draws nearest the
    slider, in its band - Extron draws its volume Up, Down and Mute alike -
    where that look can draw them: one drawn without the kit, or one whose kit
    size has the theme's own volume icons (its level's `steps`), which they
    then show; else the theme's default button, with `+` and `-`. A slider in a
    `Rail` is stacked along it, Down and Up at the level's ends, the level
    taking the length the rest leave. A seed carries a slider or a
    level, not both, so a Level drawn for a panel whose seed has none - the
    same `kinds` say which, the panel each canvas is drawn on among them - is
    named on the canvas and refused, not left for the build to refuse.
  What the layout adds - Previous, Next, Back, a group's button, Up and Down - is
  navigation the program handles, in the ID map (`docs/idmap.md` §7). A control
  keeps its name and ID on every panel; nothing the canvas draws is dropped -
  what cannot fit on a panel is refused, by panel and name. So are words a
  panel's layout runs into a button, a slider or a level - a Group's cells
  where it pages them over the page among them - or into other words, beyond
  where they met as drawn: a label's box may overlap a button, as a box is
  often bigger than its words, but its words may not.

## 5. The translator

`gdl/design.py`, stdlib Python like the rest of the toolkit. Each artboard is
laid out in **headless Chrome** with the Design type's own runtime - the
designer places controls with flex and grid, so a box exists only after layout -
and a probe reads every component's box relative to its Page, a label's and a
clock's words' own box, and anything that paints outside a component. Chrome is the only new runtime need, and only here.

The runtime is the canvas's own: the Design type's `artifact-type/dc-runtime.js`,
which the canvas serves and the build saves beside its artboards as
`support.js`. It is the Design type's to change, release by release, and its
markup (`<x-import component-from-global-scope=…>`), its `canvas.json` and
how it renders are everything the translator reads. So the runtimes the Chrome
suite has passed on are pinned by SHA-256 in `gdl/dc_runtime.json`, and
`translate` refuses a canvas whose runtime is not one of them, by name, with
what to do: run the Chrome suite with `GDL_DC_RUNTIME` set to it, and when it
passes, `python -m gdl.design pin-runtime <it> --seen <where it came from>`.
`--new-runtime` translates anyway, the build gates still verifying; and run on
a runtime that is not pinned, the suite fails one test that says to pin it.
`pin-runtime` keeps a copy of each in the archive (`archive/dc-runtime/`, in
the private repository only). `compare` refuses the same runtime, since the
sign-off lays the canvas out on it too.

## 6. Verification

- `tests/test_design.py` checks the translation rules on the probe's output,
  anywhere - the tests that read the seeds or Extron's art skip without them.
  With Chrome and `$GDL_DC_RUNTIME` (the Design type's runtime), it
  also lays out the canvas checked into `tests/data/design-huddle/` and refuses
  one with a stray painted element.
- `tests/test_designsys.py` checks each system against the Design System
  page's grammar - it silently drops what it cannot read - and against what the
  spec and the seed can build.
- `tests/test_shockwave_truth.py` holds Shockwave's ledger (§2 *Truth*) to its
  audit and to what its fixes promise, and, where the seed is here, reads the
  template facts each entry rests on off `seeds/Shockwave 1035.gdl` again - its
  art against the kit's files, its captions, modals and fonts.
- `tests/test_afterburn_truth.py` does the same for Afterburn's ledger, off
  `seeds/Afterburn 1035.gdl`: the sources' tab row, Start's button and clock,
  the foot buttons, the rails' rows, the modals' image cards and the red
  stroke of Start Sharing.
- **Kit images are checked off the artwork.** layout.json does not name a
  button's image, so `verify_built.py` draws each state's planned image over
  its planned fill and compares it with the state's artwork, both ways, a
  pixel's slack either side. On the Afterburn 1035 seed's own image buttons
  that comes to under 8% against their own files and 50% or more against
  another icon; the gate is 25%. A volume level and the next differ by one thin
  wave - 7% at 64 px, under the gate - so each state is also held against its
  button's other states' images: nearer one of those than its own, and it is
  that one, built in its place.
- **End to end**, on GUI Designer 1.28.0.7: the huddle brief drawn in Claude
  Design with *Extron Afterburn* on its Grape theme (Home, with Help and a Room
  Off confirmation as modals; three-state source buttons, a four-state Display
  toggle, a two-state mute icon, help and power icons, and End Call with its kit
  icon) translated to a spec
  with 0 problems from `gdl.spec check` and `gdl.idmap check`, built on
  `seeds/Afterburn 1035.gdl` with `New-GdlPanel.ps1 -IdMap`, unattended, and
  verified: layout 87 controls, 0 problems, the kit image on every state and
  the slider's thumb included; ID map 27 references, 0 problems.
  `gdl.design compare` then put 1.2% of Home's pixels, 2.2% of Help's and 1.9%
  of the Room Off confirmation's apart from the build.
- **The same brief in *Extron Mach*** (`tests/data/design-huddle-mach/`: the
  seed's sunset photo, shade bars and rails, 150 px source tiles with their
  kit icons and names on them, Help and Room Off as Mach's full-width modal
  windows), built on `seeds/Mach 1035.gdl`: layout 99 controls, the slider's
  rail art and every translucent fill at its own alpha included, and ID map 27
  references, 0 problems each. Compare put Help 2.7% and Room Off 2.2% apart,
  Home 22.6% - the renderer draws Mach's translucent bars and buttons opaque,
  as GUI Designer's snapshots composite them, where the canvas shows the photo
  through them (`docs/render-fidelity.md` §2).
- **The same brief in *Extron Shockwave*** (`tests/data/design-huddle-shockwave/`:
  the seed's haze, source tabs centered across the header, the video well, kit-image
  buttons resting in their rings and lit, Help and Room Off as modal cards),
  built on `seeds/Shockwave 1035.gdl`: layout 89 controls and ID map 26
  references, 0 problems each. Compare put Home 54.9%, Help 49.9% and Room Off
  56.4% apart. The built artwork is translucent where the canvas is - the
  well white at alpha 38, a resting button black at alpha 64 inside its ring -
  and the renderer, like GUI Designer's snapshots, draws any pixel with alpha
  above 0 at full strength; the modals also draw over the start page in the
  build and over nothing on the canvas. What its first builds got wrong, each
  now fixed or checked, is in `docs/history.md`.
- **The same brief in *Extron Turbulence*** (`tests/data/design-huddle-turbulence/`:
  the seed's corridor photo under translucent bars and rails, source tabs
  centered across the header - Laptop, Room PC and Doc Cam, the kit having no
  wireless glyph - display On and Off rings, the striped volume rail, End
  Call and Power Down tiles, Help and Room Off as modal cards with the seed's
  green Power Down and red Cancel), built on `seeds/Turbulence 1035.gdl`, its
  art extracted from the seed and the six Turbulence templates first:
  layout 91 controls and ID map 27 references, 0 problems each. Compare put
  Home 15.6%, Help 3.0% and Room Off 2.5% apart, and nearly all of Home's is
  the two side rails: Build wrote their black at alpha 38 as authored, and the
  compositor draws any pixel above alpha 0 at full strength, as GUI Designer's
  own snapshots do (`docs/render-fidelity.md` §2), so they render solid black
  where the canvas shows the photo through them. The theme itself leans on
  the panel blending - the seed's own header and footer art is alpha 128
  throughout.
- **The huddle on every panel** (`tests/data/design-panels/`: the same brief in
  *Extron Afterburn*, its Pages listing the TLP Pro 1035, 725, 525 and 320, the
  sources a `Group`, volume, mute, help and power a `Rail`), translated once
  and built by `New-GdlPanels.ps1` on each panel's own seed, unattended, against
  one ID map:

  | Panel | Layout | ID map | Home | Help | Room Off | |
  |---|---|---|---|---|---|---|
  | TLP1035T | 81, 0 problems | 24, 0 | 1.0% | 2.0% | 1.9% | |
  | TLP725T | 81, 0 | 24, 0 | 1.7% | 2.7% | 2.6% | |
  | TLP525T | 93, 0 | 27, 0 | 2.8% | 4.3% | 4.8% | sources popup 2.8% |
  | TLP320M | 101, 0 | 29, 0 | 5.9% | 9.6% | 10.4% | sources page 3.0% |

  The percentages are `gdl.design compare`'s, each page or derived popup as
  designed against as built. On the 525 the sources are a popup in their region
  and the slider a level with Up and Down; on the 320 the sources are a page of
  their own behind a Sources button, and the rail a footer. Most of the 320's
  modal difference is the scrim: the build shows a modal over the start page,
  the canvas over nothing.
- **The huddle on every panel in *Extron Mach*, *Shockwave* and *Turbulence***
  (`tests/data/design-panels-<theme>`: each theme's huddle above, its Pages
  listing the TLP Pro 1035, 725, 1525, 720, 535 and 525 - Turbulence draws no
  535 - the bars and rails the Page's own children, the sources a `Group`,
  given the room the smaller panels' type floor and touch minimum take),
  translated once and built by `New-GdlPanels.ps1` on each panel's own seed,
  against one ID map (`archive/job-2419a20b/hubs/`):

  | Theme | Panel | Layout | ID map | Home | Help | Room Off |
  |---|---|---|---|---|---|---|
  | Mach | TLP1035T | 119, 0 problems | 25, 0 | 23.4% | 2.6% | 2.2% |
  | Mach | TLP725T | 119, 0 | 25, 0 | 27.8% | 2.6% | 2.0% |
  | Mach | TLP1525TG | 119, 0 | 25, 0 | 22.6% | 1.6% | 1.2% |
  | Mach | TLP720T | 119, 0 | 25, 0 | 28.9% | 2.8% | 2.5% |
  | Mach | TLP535T | 137, 0 | 28, 0 | 37.9% | 2.5% | 2.3% |
  | Mach | TLP525T | 137, 0 | 28, 0 | 38.0% | 3.3% | 2.5% |
  | Shockwave | TLP1035T | 95, 0 | 26, 0 | 49.7% | 48.9% | 55.8% |
  | Shockwave | TLP725T | 95, 0 | 26, 0 | 48.8% | 51.5% | 57.4% |
  | Shockwave | TLP1525TG | 95, 0 | 26, 0 | 49.9% | 55.3% | 61.4% |
  | Shockwave | TLP720T | 95, 0 | 26, 0 | 47.8% | 48.8% | 55.3% |
  | Shockwave | TLP535T | 105, 0 | 29, 0 | 47.2% | 53.2% | 61.3% |
  | Shockwave | TLP525T | 105, 0 | 29, 0 | 47.9% | 52.0% | 59.9% |
  | Turbulence | TLP1035T | 95, 0 | 26, 0 | 15.5% | 2.0% | 2.0% |
  | Turbulence | TLP725T | 95, 0 | 26, 0 | 16.0% | 2.7% | 2.3% |
  | Turbulence | TLP1525TG | 95, 0 | 26, 0 | 15.6% | 2.2% | 2.0% |
  | Turbulence | TLP720T | 95, 0 | 26, 0 | 16.1% | 3.1% | 2.4% |
  | Turbulence | TLP525T | 105, 0 | 29, 0 | 18.2% | 4.1% | 2.8% |

  Off the 1035 each theme's bars span the panel at its series' own depths -
  Mach's header 60 deep on the 725, Shockwave's capsule under the well,
  Turbulence's header 103 on the 725 and 83 on the 720 - and its main region is
  its series'. On the hubs the sources are a popup in their region, which
  compares as Home does, and the volume slider is a level with Up and Down
  beside it in the menu bar, 177 to 284 px of it, drawn from the seed's own
  art in Shockwave and Turbulence. The large percentages are the translucency
  each 1035 bullet above explains, not the layout. What the first builds got
  wrong, each now fixed or checked, is in `docs/history.md`; every row is a
  build made after those fixes. Mach's buttons build square-cornered, as most
  of Extron's own Mach 1035's do (`docs/gdl-format.md` §7).
- **A conference room from prose, by fresh designers**
  (`archive/job-2419a20b/prose-in/`, which has the brief): a boardroom with a
  TLP Pro 1035T on the table and a 525T by the door, given to a fresh Claude
  per theme with nothing but the Design type's instructions and the system as
  a Design canvas serves it. Round one, from the READMEs as they were: every
  1035 translated clean, and only Afterburn's 525 - its designer read the
  bundle for the 525's numbers, and its room built and verified on both panels.
  What each designer had to guess became the README's *Every panel the room
  has*, *Consuming this system* and its answers. Round two, fresh designers from
  those READMEs, each 1035 translated alone and built:

  | Theme | Pages, popups | Layout | ID map | Home | Call | Modals |
  |---|---|---|---|---|---|---|
  | Mach | 2, 2 | 251 checks on 50, 0 problems | 50, 0 | 33.5% | 28.1% | 20.1-31.3% |
  | Shockwave | 2, 3 | 253 on 70, 0 | 72, 0 | 5.3% | 14.4% | 47.2-54.7% |
  | Turbulence | 2, 3 | 259 on 75, 0 | 72, 0 | 16.4% | 22.4% | 3.6-7.3% |
  | Afterburn | 2, 3 | 242 on 50, 0 | 54, 0 | 1.4% | 3.6% | 1.8-2.5% |

  Mach's and Turbulence's took one revision each, from the gates' own words -
  a stroke 2D Rounded Rectangle does not draw, one `id` on two Join Calls that
  did different things - and Turbulence's divider built once a Line became a
  shape where the seed has none. Mach's percentages are its translucent
  `shade` drawn at full strength and the states each artboard `show`s;
  Shockwave's modals add the start page the build shows beneath, where the
  canvas shows the page colour. Round three, fresh designers on Sonnet from the
  READMEs after #39 and #40, every room translated for both panels and built
  and verified on each:

  | Theme | Panel | Pages, popups | Layout | ID map | Home | Call | Modals |
  |---|---|---|---|---|---|---|---|
  | Mach | TLP1035T | 2, 3 | 282 checks on 54, 0 problems | 55, 0 | 25.1% | 25.7% | 13.2-34.3% |
  | Mach | TLP525T | 2, 5 | 318 on 60, 0 | 61, 0 | 36.7% | 32.2% | 17.6-33.6% |
  | Shockwave | TLP1035T | 2, 3 | 238 on 66, 0 | 67, 0 | 6.9% | 11.3% | 47.4-68.6% |
  | Shockwave | TLP525T | 2, 6 | 272 on 75, 0 | 82, 0 | 13.5% | 18.0% | 51.9-70.3% |
  | Turbulence | TLP1035T | 2, 3 | 216 on 62, 0 | 59, 0 | 15.9% | 13.6% | 2.8-3.2% |
  | Turbulence | TLP525T | 2, 8 | 260 on 74, 0 | 80, 0 | 15.2% | 13.4% | 5.1-6.6% |

  Mach's took no revision once a Rail's button needed only its own padding
  round its caption (#40); Shockwave's and Turbulence's took two each, from the
  gates' own words - a rail fuller than the 525's under its heading, tiles
  whose captions broke the Words rule, Groups whose gaps scale with the page.
  The percentages are round two's kind: translucency drawn at full strength,
  and the start page under a modal.
- **The same rooms on the 320** (`archive/job-e823df9b/room-320/`): the
  round-three canvases with the TLP320M listed, each translated once and built
  on the 1035, the 525 and the 320 against one ID map - every 1035 and 525
  again with 0 problems, and on the 320:

  | Theme | Pages, popups | Layout | ID map | Home over |
  |---|---|---|---|---|
  | Mach | 11, 3 | 502 checks on 90, 0 problems | 93, 0 | Home to Home 4 |
  | Shockwave | 15, 3 | 386 on 101, 0 | 111, 0 | Home to Home 4 |
  | Turbulence | 14, 3 | 376 on 101, 0 | 104, 0 | Home to Home 4 |

  Each page under its title strip, over pages of its own with Previous and
  Next, its Groups' pages coming Back to the page they are on. Three things
  the 320 asked of the canvases, each named by its gate: Mach's and
  Shockwave's Help modals said more than one screen holds and were revised to
  fit, and Shockwave's and Turbulence's clocks came off, since their 320
  seeds have no date and time control to clone (§7). And one of the Mach 320
  seed's button states is 30% transparent, so its clones built every fill at
  70% of its alpha until the applier cleared it (`docs/gdl-format.md`).
  Built again after a hub's bars came to hold what is in them and a Group's
  gap to give way (§4): all nine panels, 0 problems.
- **Round four** (spec item 10): four fresh designers, one theme's README
  each, drew one boardroom for the TLP1035T, 725T, 525T and 320M
  (`tests/data/round4-<theme>`, as they left them). Translated unchanged:

  | Theme | Refused at first | After the toolkit's share | Left, each one the README tells of |
  |---|---|---|---|
  | Mach | 19 | 6 | the 320's column heading and a Label over a Group; a state caption grown into its gap |
  | Shockwave | 27 | 11 | Help as a stack of one-line Labels; Mic Mute in the 725's audio place, whose Section is full; the 320's column heading |
  | Turbulence | 35 | 8 | Help as a stack of one-line Labels; the 320's column headings |
  | Afterburn | 149 | 90 | the README's 1035-only layout, copied: a loose left rail, the clock, a Volume heading in the Rail, words without the 525's room |

  The toolkit's share is the spec's item 10; what is left is
  `tests/data/round4-left.json`, each problem with its class and why, which
  `TestRoundFourRooms` holds every translation to. Mach's grown state
  caption and Shockwave's and Turbulence's stack of Labels also wait on a
  toolkit limit `docs/ROADMAP.md` keeps open - a row that does not re-space,
  a window's body smaller than the window - and are classed `limit` there.
  Afterburn's designer then revised the room three times from the new
  README and the translator's words (`tests/data/round4-afterburn-revised`):
  the 320 still refused four - Start's Lights heading on Start, Call's VTC
  heading on Camera Presets, and the two overlaps under them - the
  toolkit's, which laid the Page's own controls and `MainArea`'s out apart
  (§4, the small panel). Laid out as one set of rows, the revision
  translates clean on all four panels, and the README says the rows' rule
  the designer had to guess: the order, how deep and wide the rows are,
  how tall a heading is, and that the page does not go on. Its ID map
  checks clean across all four as well (`python -m gdl.idmap
  write-panels`, which a build runs before GUI Designer), each source a
  page of its own on the 320 (§4). Built (2026-10-25): every room - Mach's
  and Turbulence's after one revision, Shockwave's after two, Afterburn's
  revised - built unattended on all four panels and verified, 0 problems,
  its ID map 0 problems on each (`archive/job-e823df9b/round4/`, each
  room's canvas, first and final translations and build log, and
  `round4_vs_templates.png`, each built working page beside its
  template's). Building them found two of the verifier's own limits, fixed:
  a translucent fill held to half Build's premultiplying rounding (#55), an
  icon fitted ninefold small past an image gate measured on 64 px icons
  (#55: the nearest of its kit family instead) and a fill asked for under an
  image opaque over its box (#56). Mach's, Shockwave's and Turbulence's
  rooms read as their templates on every panel; Afterburn's builds and
  verifies but, drawn without regions, its 525 and 320 do not
  (`docs/ROADMAP.md`).

## 7. What is left

- A plain modal on the 320 (no `role` or `title`), and Afterburn's, hold one
  screen, so one that says more is refused there, by name: Mach's and
  Shockwave's round-three Help modals were, until revised (§6). A bar theme's
  window (`role="help"`, `"settings"`) is a page there and goes on over a
  second. Going on over more modals, as a page goes on over pages, is
  unbuilt: whether a modal's button can show another modal is unproven.
- Shockwave's and Turbulence's 320 seeds have no date and time control to
  clone (their profiles' `kinds`), so a Clock on a canvas listing the 320 is
  refused there, by name; the round-three rooms built there with theirs taken
  off (§6). Cloning the control from another of the theme's seeds is unbuilt.
- A plain container - a flex column of labels, as the huddles' Help pages
  hold - cannot reflow on a small panel (the 300s and the 320), and is refused there,
  by name; the Page README says so beside its flex-and-grid sentence.
- On a mid-size panel each Group pages in its own box; the spec's hub - one
  region every group shares, switched by a rail of group buttons - is backlog,
  as are a left `Rail` on Afterburn and an icon on a group's button.
- The region frame's own gaps - region pages on the 300s and turned panels,
  popups sized to the frame's center, the 320's captions too long for its
  key - are in `docs/ROADMAP.md`.
