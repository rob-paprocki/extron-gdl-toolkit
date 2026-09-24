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
python -m gdl.design translate <canvas dir> out/spec.json
      │  the existing pipeline, unchanged
      ▼
New-GdlPanel.ps1 -IdMap  →  built, verified .gdl  +  verified ID map
```

Nothing goes the other way. A spec is an intermediate the translator writes, not
something anyone edits or exports back to a canvas.

## 1. Using it

1. **In Claude Design**, start a design with the template's design system - for
   Afterburn, *Extron Afterburn* - and describe the panel by what it does: the
   sources, the call controls, what needs confirming, what the program shows by
   itself. The system's README tells Claude Design how to draw it and what to
   record.
2. **In Claude Code**, give it the canvas link and ask for the panel. It reads
   `project/canvas.json`, every `project/*.dc.html` and the installed system's
   `project/ds/<folder>/` files into one folder, with the Design type's
   `artifact-type/dc-runtime.js` saved beside the artboards as `support.js`,
   then:

   ```bash
   python -m gdl.design translate <that folder> out/spec.json
   ```

   It prints the donor seed the design system names. From there it is the
   normal pipeline: `powershell\New-GdlPanel.ps1 -Spec out/spec.json -Donor
   <seed> -Output <panel.gdl> -IdMap out/idmap`.
3. **For sign-off**, put each artboard beside the page GUI Designer built from
   it - a client signs off on the panel, not on the canvas:

   ```bash
   python -m gdl.design compare <that folder> <panel.gdl> out/signoff   # index.html
   ```

   The built side is `gdl.compose`'s render of the built file's own artwork; a
   modal is shown over the start page, as the panel shows it. It prints the
   share of pixels that differ per page.

A translation that finds anything it cannot build writes no spec (§4), so the
fix happens on the canvas, where the designer can see it.

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
| **Colors** | Afterburn: the published guide (`docs/design-rules.md` §4), its four accent schemes as the system's themes. Mach: its PSD's `Colors` group and the selected/unselected alpha rule. Shockwave, Turbulence: `gdl.themes` over the seeds and `.glt` templates, cross-checked against their PSDs. |
| **Themes** | Afterburn's four recommended pairings - Default with accent Scheme 1, Anthracite with 3, Blue Slate with 2, Grape with 4 - as a Page's `theme`. Each is the kit's background image fitted over `#242634`, as the seed draws it, plus its accent scheme. The spec carries the image, and the applier appends it to the project. |
| **Layout** | Where the template puts things. Afterburn keeps most of a page in the squircle main area (`MainArea`, 916×752 at 183,24), with headed groups on the left rail and volume, help and power on the right. |
| **Type** | The faces the template's seed can actually author (`Project.font_resource_names()`), at the sizes its own pages use - none under the 14 pt the toolkit checks. Sizes are points, drawn at GUI Designer's 1.375 px per point. Open Sans is Apache 2.0 and loads from Google Fonts. |
| **Borders** | Only border resources the seed defines and the spec names (`BORDERS`), so a design cannot ask for a shape the panel cannot draw. |
| **Button archetypes** | The looks the seed's own buttons use, per state. Afterburn's captioned ones are outlined (the most common), ghost and inverse, and an alert - a red fill with a white caption, for a condition someone has to act on, not an ordinary action such as shutting down. Its image ones - source, list, icon and toggle, and outlined with an icon - are each drawn from the kit as the seed draws them: the image, the fill it takes when selected, and where the caption goes. Afterburn shows state with its icons, never fills a button with an accent, and never colors a caption red. |
| **Icons** | The template's resource kit, indexed by name and look (`gdl.designsys.kit_index`) and embedded in the bundle downscaled, as WebP - about 1.8 MB for Afterburn's thousand. Extron's artwork, so only in the owner's private design system, with their agreement (`docs/history.md`). A state asks for an icon unselected or selected; selected is the scheme's primary accent for an icon drawn in the primary accents, its secondary for one drawn in the secondary ones (toggles, volume levels). |
| **Sliders and levels** | As the seed's built ones draw: a thin rounded rail (Afterburn's is 10 px, filled `#BABCCE`) with a round thumb in the secondary accent. The thumb is a kit image, not a color: its circle is 65% of its 50 px box, so the canvas draws the kit's own, and the translator gives each slider the scheme's (`gdl.designsys.slider_thumb`), since a clone keeps its donor's. |
| **Modals** | As Build draws them: the page beneath under black at alpha 166, whatever background the popup has. So a modal carries no background of its own. |
| **Spacing and sizes** | The panel's touch minimum and spacing for its model (`touch_minimums`), and GUI Designer's 10 px nudge. |
| **README** | The panel's rules and its function vocabulary: what Claude Design reads first. |
| **Donor** | The seed the panel is built on. The canvas's design system therefore also chooses the donor. |

A profile is checked against the seed's **built artwork**, not only its model
and the guide: the first Afterburn system drew a slider as a filled slab and
filled buttons with the accent, and both read fine off the numbers.

The first cut targets **1280×800** - the TLP Pro 1025/1035 family, which every
template has a seed for. Other resolutions follow the seeds (`seeds/README.md`).

**Icons are the kit's images, not its fonts.** Extron's icon fonts carry no
license field (`gdl/fonts/README.md`) and a spec cannot place a glyph
(`docs/ROADMAP.md`), so a design names a kit image instead. An icon the kit
does not have draws as a dashed box and the translator refuses it.

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
| Page | a page or popup | `name`, `kind` (`page`, `popup`, `modal`), `group`, `start`, `reached-by`, the `theme` (background and accent) or an accent `scheme` alone |
| MainArea | nothing of its own | a frame: its children are placed inside the template's main area |
| Button | `button` | caption, `variant`, `icon`, `states` (names, each with its own look, caption and kit image), `press` - the state the panel shows while it is held, which the canvas draws while it is held too - `nav`, `does`, `id` |
| Label | `label` | text, `type` or `size`, `color`, `align`, `does` |
| Panel | `panel` | `fill`, `stroke`, `border` |
| Line | `line` | orientation, `color`, `thickness` |
| Slider, Level | `slider`, `level` | `orientation`, `fill`, `track` and `thumb` sizes, `does`; a slider also gets its scheme's `thumb_image` |
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
  breaks under a source's icon, leading spaces past a list button's.
- **One template and one accent scheme per panel**, and page names unique.

## 5. The translator

`gdl/design.py`, stdlib Python like the rest of the toolkit. Each artboard is
laid out in **headless Chrome** with the Design type's own runtime - the
designer places controls with flex and grid, so a box exists only after layout -
and a probe reads every component's box relative to its Page, plus anything
that paints outside one. Chrome is the only new runtime need, and only here.

## 6. Verification

- `tests/test_design.py` checks the translation rules on the probe's output,
  anywhere. With Chrome and `$GDL_DC_RUNTIME` (the Design type's runtime), it
  also lays out the canvas checked into `tests/data/design-huddle/` and refuses
  one with a stray painted element.
- `tests/test_designsys.py` checks each system against the Design System
  page's grammar - it silently drops what it cannot read - and against what the
  spec and the seed can build.
- **Kit images are checked off the artwork.** layout.json does not name a
  button's image, so `verify_built.py` draws each state's planned image over
  its planned fill and compares it with the state's artwork, both ways, a
  pixel's slack either side. On the Afterburn 1035 seed's own image buttons
  that comes to under 8% against their own files and 50% or more against a
  wrong one; the gate is 25%.
- **End to end**, on GUI Designer 1.28.0.7: the huddle brief drawn in Claude
  Design with *Extron Afterburn* on its Grape theme (Home, Help and a Room Off
  confirmation; three-state source buttons, a four-state Display toggle, a
  two-state mute icon, help and power icons, and End Call with its kit icon)
  translated to a spec
  with 0 problems from `gdl.spec check` and `gdl.idmap check`, built on
  `seeds/Afterburn 1035.gdl` with `New-GdlPanel.ps1 -IdMap`, unattended, and
  verified: layout 84 controls, 0 problems, the kit image on every state and
  the slider's thumb included; ID map 26 references, 0 problems.
  `gdl.design compare` then put 1.2% of Home's pixels, 0.6% of Help's and 1.9%
  of the Room Off confirmation's apart from the build.

## 7. What is left

- Mach, Shockwave and Turbulence as design systems.
- A Page's `does` reaches the spec as `_does` and goes no further: the ID map
  has nowhere to say what a page is for yet.
