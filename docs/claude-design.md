# Designing a panel in Claude Design

The goal: describe what a panel has to **do**, in prompts, to Claude Design; get
a canvas drawn in the real Extron template; and have Claude Code turn that
canvas into a working `.gdl` and its ID map. Claude Design is where the panel is
designed. Claude Code is where it is built, because only Claude Code can run GUI
Designer.

```
prompts about functionality
      │  Claude Design, using one Extron template's design system
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
Claude Design and never needs this repo or Windows. The **builder** works in
Claude Code on the machine GUI Designer runs on.

| Role | Needs |
|---|---|
| Designer | a claude.ai account with Claude Design, and the template's design system in it - *Extron Afterburn*, *Mach*, *Shockwave* or *Turbulence* |
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
the Artifact tool. The icons and theme backgrounds are Extron's kit, read from
the GUI Designer install or `vendor/`, and embedded downscaled. Turbulence's art,
and Mach's slider, are in neither until they are extracted from Extron's own
files, once per machine: `python -m gdl.designsys extract <template>`
(`vendor/README.md`). Without the kit, or without Pillow, the build says so,
naming that step where it applies: the system then has no icons, and its themes
no background images.

Because it carries Extron's artwork, the system is published private (§2
*Icons*), to the account Claude Code is signed in to. The designer works in
that account, or has the system shared with theirs.

### Design: in Claude Design

1. Start a design that uses the template's design system - *Extron Afterburn*
   in this example.
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

   The system's README makes Claude Design draw only with its components, one
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
   the next. The fix goes on the canvas, back in Claude Design, where the
   designer can see it; then Claude Code reads it again.
3. **Builds and verifies it**, with nobody touching GUI Designer. Before the
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
   designed, or the ID map disagrees with a built panel.
4. **Puts each artboard beside the page GUI Designer built from it**, for
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
   that differ per page.

### What comes out

| File | For |
|---|---|
| `out/huddle/<panel>/<Name>.gdl` | each panel, built: open it in GUI Designer, or load it to the touch panel |
| `out/huddle/idmap/` (`idmap.md`, `.csv`, `.json`) | the control-system programmer: every addressable control's ID, type, caption, states and what it does, and where it is on each panel (`docs/idmap.md`). No program is generated. |
| `out/huddle/signoff/index.html` | the client: each panel's pages as designed beside them as built |

To change the panel, change the canvas and build again.

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
| **Colors** | Afterburn: the published guide (`docs/design-rules.md` §4), its four accent schemes as the system's themes. Mach: its PSD's `Colors` group and the selected/unselected alpha rule. Shockwave: its seed's own fills and captions, corroborated by `gdl.themes` over its `.glt` - its PSD names swatches but carries no values. Turbulence: its seed's own, state by state - most of them stored by name, so read through the KnownColor table (`docs/gdl-format.md` §7) - with its header and footer read off their art, which is one color. |
| **Themes** | Afterburn's four recommended pairings - Default with accent Scheme 1, Anthracite with 3, Blue Slate with 2, Grape with 4 - as a Page's `theme`. Each is the kit's background image fitted over `#242634`, as the seed draws it, plus its accent scheme. Mach's are its kit's six photos, the seed's sunset first, stretched as its seed stretches them (`background_layout`). Shockwave's are its seed's soft blur and its Start page's Saturn, stretched likewise; Turbulence's its seed's corridor and the bokeh, office, swoop and water photos from its templates. The spec carries the image, and the applier appends it to the project. |
| **Layout** | Where the template puts things. Afterburn keeps most of a page in the squircle main area (`MainArea`, 916×752 at 183,24), with headed groups on the left rail and volume, help and power on the right. Mach puts shade bars top and bottom and rails either side of its photo. Shockwave puts its sources as tabs across a header, the chosen one's page in a black video well (926×574 at 168,120), rails either side and a capsule footer. Turbulence puts its sources as tabs across a translucent header, the chosen one's popup in the region between the bars and the side rails (995×549 at 140,137), and a translucent footer. |
| **Type** | The face the template's profile offers, one its seed can actually author (`Project.font_resource_names()`; Mach's and Turbulence's seeds also define Open Sans Light, which no profile offers), at the sizes its own pages use - none under the 14 pt the toolkit checks. Sizes are points, drawn at GUI Designer's 1.375 px per point. Open Sans is Apache 2.0 and loads from Google Fonts. |
| **Borders** | Only border resources the seed defines and the spec names (`BORDERS`), so a design cannot ask for a shape the panel cannot draw. |
| **Button archetypes** | The looks the seed's own buttons use, per state. Afterburn's captioned ones are outlined (the most common), ghost and inverse, and an alert - a red fill with a white caption, for a condition someone has to act on, not an ordinary action such as shutting down. Its image ones - source, list, icon and toggle, and outlined with an icon - are each drawn from the kit as the seed draws them: the image, the fill it takes when selected, and where the caption goes. Afterburn shows state with its icons, never fills a button with an accent, and never colors a caption red. Mach shows it with a brighter fill. Shockwave draws every button as a kit image: a button names its color family, rests dark in a ring of that color and lights up when On (`kit.outline_off` reads the kit so), and an `action` button carries the kit's icon at its left with the caption centered past it, as the seed pads it with spaces. Turbulence's are kit images too: a gray tile, a white ring, a navy source tab or nothing at rest, white with a green glow or dark teal when lit. Most of its kit carries its words in the art, so only its blank images take a caption, which turns `accent` when lit. A variant's `size` is the size its seed draws it at - Turbulence's tile is 87×90 - and the Button README states it and the preview draws it there, so a caption keeps its proportion to the art; drawn smaller, a caption at the template's size spills past its tile. |
| **Icons** | The template's resource kit, indexed by name and look (`gdl.designsys.kit_index`) and embedded in the bundle downscaled, as WebP - about 1.8 MB for Afterburn's thousand. Extron's artwork, so only in the owner's private design system, with their agreement (`docs/history.md`). A state asks for an icon unselected or selected; selected is the scheme's primary accent for an icon drawn in the primary accents, its secondary for one drawn in the secondary ones (toggles, volume levels). A variant's `icon` is what it draws unless told otherwise; `icons` narrows what it offers to the families starting so (Afterburn's toggle), or with any of a list (Turbulence's rings). A file the kit's `<W>x<H>_` naming misses is named in the profile (`kit.named`: Shockwave's modal Close, one file per look; Turbulence's pairs whose two files are named apart, like `outline_01` at rest and `round_01` lit, where the pair replaces the half icons the pattern made of them). A kit that exists only inside Extron's files - Turbulence's, in its templates - is extracted to `vendor/` first (`python -m gdl.designsys extract <template>`, `vendor/README.md`). |
| **Sliders and levels** | As the seed's built ones draw: a thin rounded rail (Afterburn's slider's is 10 px, filled `#BABCCE`; its level's 15 px, filled in the secondary accent) with a round thumb in the secondary accent. The thumb is a kit image, not a color: its circle is 65% of its 50 px box, so the canvas draws the kit's own, and the translator gives each slider the scheme's (`gdl.designsys.slider_thumb`), since a clone keeps its donor's. A template whose thumb is one file whatever the accent names that file, and one whose rail is art rather than two colors names its rail images too (`track_image`, `fill_image`); the canvas then draws those, the translator gives them to each slider in the spec (`gdl.designsys.slider_rail`), and a thumb that is not round keeps its own proportions (`thumb_height`). |
| **Modals** | As Build draws them: the page beneath under black at alpha 166, whatever background the popup has. So a modal carries no background of its own. |
| **Spacing and sizes** | The panel's touch minimum and spacing for its model (`touch_minimums`), and GUI Designer's 10 px nudge. The tokens state the design panel; every other panel's comes from the profile's per-panel table. |
| **Panels** | A per-panel table (`panels`), one entry per Extron series: the models it serves (`gdl/templates.py`), its main region - measured off its background art where the art draws it (Afterburn's squircle), else off its template's own controls (Mach's bars, Shockwave's well, Turbulence's side bars) - the rail band beside or below it, or none where the template keeps nothing on screen from page to page (those three themes' 320s), its popup region, a background per theme and how its pages draw them (Fill or Stretch), and per seed, what the seed can clone and which of the profile's borders it lacks. `gdl.designsys.models()` adds each model's own touch minimum, gap and type floor (`docs/design-rules.md` §1); the bundle carries it so a Page can draw any of them. Measured with `tests/measure_series.py`. |
| **README** | The panel's rules and its function vocabulary: what Claude Design reads first. Its iconography, its example page and the components' own READMEs and previews are drawn from the profile (`iconography`, `examples.source` and `examples.help`, its variants, type styles and tokens), so each names only what its template has. *Every panel the room has* tabulates, for each panel the system serves, the room a design leaves for it on the canvas - that panel's touch minimum and gap measured here, how much wider than its words a box must be, what a hub's rail holds - from the scale, touch minimum and type floor that panel's layout applies; four fresh designers of a two-panel room, without it, drew the 1035 snug and saw the 525 refused. Where a template's own geometry breaks a gate - Shockwave's flush tabs, Mach's sliders 30 px wide - the Layout says what to draw instead. It answers what each of those designers asked: a modal opened from several pages closes with `does`, not `nav`, since a `nav` is what the programmer is told to show; a control on several pages is one control only with one `id`. It ends with *Consuming this system*: the global, the bundle and the font link. |
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
| Page | a page or popup | `name`, `kind` (`page`, `popup`, `modal`), `group`, `start`, `reached-by`, the `theme` (background and accent) or an accent `scheme` alone; `panels` (every panel the room has, the first the one it is drawn on) and `preview` (one of them to draw it as) |
| MainArea | nothing of its own | a frame: its children are placed inside the template's main area - on each panel, that panel's own |
| Rail | nothing of its own | a frame: its children stack in the rail beside the main area, or across below it where there is no room beside it; a button in it fills it across, its caption needing only the button's own padding |
| Group | its members; on a smaller panel, the popups or pages it becomes | `title`, `cell`, `gap`, `cap`, `joined`: equal cells in its box - in place, paged as popups in its box (Previous and Next under its cells, or at the row's ends in a box one cell deep - arrows where their words leave no room), or pages of their own opened by a button, by the panel's size; in a modal or a popup on a large or mid-size panel only in place, since a popup shows no popups |
| Button | `button` | caption, `variant`, `icon`, `states` (names, each with its own look, caption and kit image), `press` - the state the panel shows while it is held, which the canvas draws while it is held too - `nav`, `does`, `id` |
| Label | `label` | text, `type` or `size`, `color`, `align`, `does` |
| Panel | `panel` | `fill`, `stroke`, `border` |
| Line | `line`, or a `panel` of its box on every panel the canvas lists where any one's seed has no line to clone - most of Mach's, Shockwave's and Turbulence's sizes; level or upright, its box is the band it draws | orientation, `color`, `thickness` |
| Slider, Level | `slider`, `level` | `orientation`, `fill`, `track` and `thumb` sizes (and `thumb_height`, where the template's thumb is not square), `does`; a slider also gets its scheme's `thumb_image`, a level its scheme's `bar`, and a level is built `track` wide, centred in its box, since Build draws a level over its whole box |
| Clock | `datetime` | `format` (`time`, `date`, `datetime` or a .NET pattern), `color`, `size`, `align` |
| PopupRegion | `popup_ref` | the popup `group` shown there |

Colors are the template's token names, and the spec's theme is exactly the
tokens used, resolved for the canvas's accent scheme.

## 4. What a canvas means

- **An artboard is one page or popup.** Its root is one Page. A popup is
  `kind="popup"` with a `group`, or `kind="modal"`; the start page is
  `start="true"`, else the first artboard.
- **A button's `nav` names an artboard** by its file stem (`nav="Help"` is
  `Help.dc.html`). The button draws as that link, so Play follows it, and the
  translator turns it into the target Page's name.
- **What a control does is `does`**, in words, on the component. A page the
  program shows by itself (an incoming call) is `reached-by="program"`.
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
- **A Page's `panels` are the room's panels**, the first the one it is drawn on,
  and every Page lists the same. Each panel is built from the canvas as the
  design system lays it out for that panel (§3, `docs/design-rules.md` §1):
  - its own size, background art and main region, each control grown to that
    panel's touch minimum and its caption to that panel's type floor;
  - on a large or mid-size panel (tiers A and B), `MainArea` and the `Rail`
    each mapped by one scale, and the Page's own children by one scale for
    the page, centred - a modal's card stays centred on the screen, as
    Extron's own 525 centres its modals. Where the template draws its bars as
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
    control does, the right column goes
    to the menu bar, and `MainArea` and the `Rail` keep to what those bands
    leave, a control grown to the touch minimum staying inside main. On the
    panel the canvas is drawn on they stay as drawn;
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
    main's foot; a row never splits, and a card goes behind its controls on
    each page they land on. Words wider than the screen break into lines, a
    line as GUI Designer lays one out. A modal holds one screen: it is a popup
    over a page, and it does not go on over more;
  - a `Group` in place, paged in its box as popups with no fill of their own -
    the page shows through, as through the seed's own group popups - or turned
    into pages of its own opened by a button, by the panel's size; a joined
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

## 6. Verification

- `tests/test_design.py` checks the translation rules on the probe's output,
  anywhere - the tests that read the seeds or Extron's art skip without them.
  With Chrome and `$GDL_DC_RUNTIME` (the Design type's runtime), it
  also lays out the canvas checked into `tests/data/design-huddle/` and refuses
  one with a stray painted element.
- `tests/test_designsys.py` checks each system against the Design System
  page's grammar - it silently drops what it cannot read - and against what the
  spec and the seed can build.
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
  Claude Design is served it. Round one, from the READMEs as they were: every
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

## 7. What is left

- A bar drawn as a Panel does not grow with a deeper Group in it - on the 525
  Shockwave's source tabs stand below its header bar - and a Group's gap,
  which scales with the page, does not give way to its cells before the Group
  pages: Turbulence's round-three designer narrowed its gaps by hand to fit
  the 525 (§6).
- A modal on the 320 holds one screen, so one that says more is refused
  there, by name: Mach's and Shockwave's round-three Help modals were, until
  revised (§6). Going on over more modals, as a page goes on over pages, is
  unbuilt: whether a modal's button can show another modal is unproven.
- Shockwave's and Turbulence's 320 seeds have no date and time control to
  clone (their profiles' `kinds`), so a Clock on a canvas listing the 320 is
  refused there, by name; the round-three rooms built there with theirs taken
  off (§6). Cloning the control from another of the theme's seeds is unbuilt.
- A plain container - a flex column of labels, as the huddles' Help pages
  hold - cannot reflow on a small panel, and is refused there, by name; the
  Page README still offers flex and grid containers without that caveat.
- On a mid-size panel each Group pages in its own box; the spec's hub - one
  region every group shares, switched by a rail of group buttons - is backlog,
  as are a left `Rail` and an icon on a group's button.
- A Page's `does` reaches the spec as `_does` and goes no further: the ID map
  has nowhere to say what a page is for yet.
