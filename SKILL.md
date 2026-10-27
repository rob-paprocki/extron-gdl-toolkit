---
name: extron-panel
description: Use when creating, modifying or reviewing an Extron GUI Designer touch-panel (.gdl/.glt) — building a panel from a Design canvas link or from a description, editing an existing client panel, checking a design against Extron's standards, or previewing what a panel will look like before it is built.
---

# Building Extron touch panels

This repo can read, render, check and generate Extron `.gdl` panels. The whole
loop is proven against GUI Designer 1.28.0.7, and on a machine with GUI
Designer installed it runs unattended end to end — `powershell\New-GdlPanel.ps1` takes a JSON spec and
returns a built, verified panel without anyone opening GUI Designer.

So the job here is usually to turn a description into a good spec. The build is
mechanical; the design is not.

Read `docs/design-rules.md` before making design decisions and
`docs/gdl-format.md` before touching the format. Both encode findings that were
expensive to get.

## The one thing to internalize

**Build owns the artwork.** You never make pixels. You set semantic properties —
a fill color, a stroke, a *named* border resource, a font, a caption — and GUI
Designer rasterizes them on build. A control you author carries `TLPImageID = -1`
until then.

This is why a preview is possible at all, and why "the file looks right" is not
the same as "the panel looks right" (see the `flattenText` trap below).

## Two workflows

A panel designed on a Design canvas with an Extron template's design system
comes in through workflow A: `python -m gdl.design translate` writes its spec -
one per panel the canvas lists, each with its own seed - and every step from 4
on applies to each, with one difference: the panels share one ID map, so they
are built with `powershell\New-GdlPanels.ps1` (step 7), not one by one with
`-IdMap`. `docs/claude-design.md`. A revision of a canvas whose map a
programmer already has is translated with `--previous <that map>` and built
with `-Previous`, so every ID the program uses is kept and `changes.md` says
what changed (`docs/idmap.md` §9).

A canvas draws a bar panel's working page as **region pages** - Header,
LeftRail, RightRail, Footer and Center - and says what a page or popup is for
with a `role`: `source` and `dialer` popups; `call` and `select` pages;
`help` and `settings` windows; `confirm` windows by `topic` (`power`, `call`,
and `recording` where the template asks one), and waits (`up`, `down`). Their
grammar, per template, is `docs/claude-design.md`
§3 and §4; read it before drawing or translating one, not from here.

`New-GdlPanels.ps1` builds and verifies every panel and writes the one ID map;
it needs a **Windows host with GUI Designer installed** (`CLAUDE.md`
*Environment*), so on any other machine stop at the translated specs and
`gdl.spec` / `gdl.design` checks and say the build is waiting for one.

Before a canvas is built, run its **critique loop** - translate, `python -m
gdl.design compare <canvas dir> --template <out dir>`, fix on the canvas, and
again until nothing differs that the README's *Differences* does not list
(`docs/claude-design.md` §1, step 3). That is the critique, before the build.
The **sign-off** is after it: `python -m gdl.design compare <canvas dir>
<out dir or panel.gdl> <signoff dir>` puts each artboard beside the page Build
made from it (`docs/claude-design.md` §1, *Build*). Neither replaces `tests/verify_built.py`.

### A. Generate a panel from a description

1. **Pick the panel model first**, and put it in the spec as `"model"`.
   `gdl/spec.py`'s `MODELS_FULL` holds every panel GUI Designer builds for, with
   each one's resolution, DPI and Extron part number, read from the assemblies
   (`docs/design-rules.md` §1 lists them). The canvas is not a constant - and
   **DPI varies by nearly 2x within a resolution**, so naming the model is what
   makes the touch-target check right rather than merely safe. Ask if you don't
   know it. A panel that rotates (`docs/design-rules.md` §1) also needs its way
   up: a turned one's `size` is its turned canvas.
2. **Pick the theme.** `gdl.themes.AFTERBURN` is the documented token set. For
   Mach/Shockwave/Turbulence, or a client's house style, run
   `python -m gdl.themes <template.glt>` and read the tokens off the template.
   Name the theme family in the spec as `"family": "Afterburn"` (or `Mach`,
   `Shockwave`, `Turbulence`): `gdl.spec donors <spec.json> --auto` and
   `New-GdlPanel.ps1` without `-Donor` then find its seed by family, model and
   canvas, read off each seed's own build rather than its name (`python -m
   gdl.seeds pick <spec.json>`), and say how to make one where `seeds/` has
   none - or why none can be made (`seeds/README.md`). `donors` refuses a donor
   of another model or theme, picked or passed: the built panel is the donor's.
3. **Write the spec** — see `examples/panel.json` for the full vocabulary and
   `examples/huddle.json` for a small one written straight from a prose brief.
   Use `grid`/`stack` for layout;
   never hand-type a rect. Nest them for sub-regions (a nested directive lays out
   inside its parent cell, and a `rect` at that depth is an offset into it). A
   `grid` given `rows` and no `cols` takes as many columns as its items need; a
   column of buttons is a `stack`.

   **Give the buttons feedback.** A button with one appearance is inert: the
   control system sets it On and nothing on the panel changes. Set `"on"` in
   the theme and every button gets an On state for free:

   ```json
   "theme": { "raised": "#37394E", "accent": "#3D8BFD", "on": "accent" }
   ```

   Per button, `"on": "accent"` changes just the fill; `"on": {"fill": "surface",
   "color": "muted", "stroke": "accent", "border": "capsule"}` changes whatever
   it names - an `icon` or `image` too - and inherits the rest from the Off
   appearance. Omit `on` entirely
   and the button keeps a single appearance, which is right for a label-like
   button and wrong for anything the control system drives.

   `Off`/`On` is what nearly every button in Extron's own templates uses
   (`docs/gdl-format.md` §7). When a button shows more than that, name its
   `states` in order -
   each a name, or a name with its own `fill`, `stroke`, `color`, `border`,
   `text`, `icon` and `image`, inheriting the rest from the button:

   ```json
   { "kind": "button", "name": "Display", "text": "Display Off", "fill": "raised",
     "states": ["Off",
                {"name": "Warming", "fill": "surface", "text": "Warming Up"},
                {"name": "On", "fill": "accent", "text": "Display On"},
                {"name": "Cooling", "fill": "surface", "text": "Cooling Down"}],
     "press": "On" }
   ```

   The program sets a state by its index - its position here - and the ID map
   lists them that way. `press` names the state shown while the button is held;
   it defaults to the second, and naming the first - the state the button rests
   in - is a problem, since holding it would show nothing. Two states that look
   identical are a problem, whether `states` or `on` made them, as is a mirror
   (a shared `id`) with different states. A mirror inside the touch target
   whose `id` it shares - Shockwave 1035's tab name, a caption-only button
   under the tab's glyph - is pressed as that target and shows its states, so
   its own touch size, gaps and alike states are not held against it, nor its
   shared `id` on the page. In a state, `none` turns its fill or outline off;
   leaving the key out keeps the button's own.

   **Say where the panel boots.** `"start_page": "<page name>"` - the first page
   when omitted - is written into the project, because otherwise the built panel
   opens on the donor's start page.

   **Name the page art and the clock format.** A page's `background_image` - or
   the theme's, for every page - names an image drawn fitted, keeping its
   aspect, over the page's `background`; `"background_layout": "stretch"` stretches
   it instead, as Mach's pages lay out their photo. One the donor lacks needs `"images": {"<name>": "<path>"}`,
   the path relative to the theme resource kits (`vendor/extron/Resources`, or
   the install), and the applier appends it. A standard popup takes a
   `background_image` and `background_layout` too - Shockwave's and
   Turbulence's hubs draw their popups on the page's photo, stretched; a
   modal takes none - Build draws a modal's page, photo too, at the modal's
   35% transparency, which no canvas draws. Art that is
   neither a page's nor a button's is an `image` control:
   `{"kind": "image", "name": "Top bar", "rect": [0, 0, 1280, 133], "image":
   "2047x151_header.png", "layout": "stretch"}` - `layout` `fill` (the
   default: fitted, keeping the aspect) or `stretch`, an optional `fill`
   under it (none is written clear, and no border), and no states; one with neither `image` nor `fill` draws
   nothing and is a problem. Only a donor with a `PBImage` can clone one
   (`docs/gdl-format.md` §7 says which seeds have one). A button's icon is an `image` the
   same way, on the button or on each state (*Icons* below). A `datetime` control's `format` is
   `time` (the default), `date`, `datetime` or any .NET date pattern
   (`"MMMM d, yyyy"`). Both are written explicitly, because a clone keeps the
   donor's: the donor's background under every page, its clock pattern on every
   clock.

   **Popups are one of two kinds.** A *standard* popup sits in a `group` and
   shows through a `popup_ref` bound to that group, at the reference's size -
   or sits in no group and shows through a `popup_ref` bound to it alone,
   `"popup": "<its name>"`, as Extron's hubs place their Volume Level strip. A
   *modal* one (`"modal": true`) covers the whole canvas - draw the confirmation
   card inside it - and needs no reference; Build places those. `check` rejects
   anything else, since neither kind can otherwise be shown. A popup's
   `timeout` is written into the project, but nothing GUI Designer builds
   carries it to the panel - `check` says so - so a popup that hides by itself
   is the program's to hide (`docs/gdl-format.md` §7).

   **Say what the panel shows when it loses its controller.** GUI Designer's
   Offline Page is the seed's own, shown or not as the seed ships it - the
   seeds go both ways - and every one says *call XXX.XXX.XXXX*. `"offline":
   {"enabled": true, "replace": {"XXX.XXX.XXXX": "555.010.4567"}}` switches it
   and replaces words on it; its layout and type stay the seed's. `donors` says
   which way the seed ships it when the spec does not, and refuses a word its
   page does not say.

   **Say what it does.** A brief describes functions as well as a layout - "the
   sources route to the display and show which is live; Help explains sharing".
   Page and popup flips are `nav` on the button, which is checked; everything
   else is `does`, in words, for the programmer's ID map. `docs/idmap.md` has
   the keys and `examples/huddle-functions.json` a brief worked through. Then
   `python -m gdl.idmap check <spec.json>` - it rejects a nav to nowhere, a
   popup that cannot appear where it is shown, a page nothing reaches.
4. **Check it**: `python -m gdl.spec check <spec.json>` — ids, off-canvas, sizes,
   a size the model does not have, unknown resources, a key nothing reads at
   any level - the spec's, a page's or popup's, a control's, a state's, the
   Offline Page's, a theme's that is neither a setting nor a color (a key starting `_` is the
   translator's, or a note) -
   a `grid` or `stack` with more items than cells (the rest would not be laid out),
   and Extron's numeric standards on every page and popup (touch target, 2 mm
   between touch targets and no two overlapping - except the segments of one
   segmented control, which share a `joined` - ≤9 buttons per group, ≤6 colors
   drawn besides the template's own (`_template_colors`) - a caption's default
   color and the popups' colors included, each color counted once whatever its
   transparency - and ≥14pt body text), plus the type
   floor for the named model (`docs/design-rules.md` §1; a measurement spec turns
   it off with `"type_floor": "off"`).
5. **Preview it**: `python -m gdl.spec render <spec.json> out/preview.png`, then
   **look at the image**. The compositor is scored against GUI Designer's own
   output, so this is a real preview, not a sketch. Iterate here — it is fast
   and needs no GUI Designer.
6. **Check it against the donor**: `python -m gdl.spec donors <spec.json>
   <donor.gdl>`. The donor supplies every cloned control, so a type it lacks is
   unauthorable - but a clock, which is cloned from the smallest other seed of
   its theme that has one (Shockwave's and Turbulence's 320s take their 525's;
   `docs/gdl-format.md` §7). A font family it lacks is appended from a seed that carries
   the face, and a border it lacks is built as its own of the nearest shape -
   all three said by `donors` and written by `plan --donor` (`New-GdlPanel.ps1`
   passes the donor); only a face no seed carries, or a border of no shape near
   enough, is refused (`seeds/README.md`). A family is named as the donor or
   the seed spells it. Each takes seconds to find here - a face to append costs
   a parse of the seed that carries it, 2 s for a Shockwave seed and up to 45 s
   for a Turbulence one - and a whole build to find there.

   **Pick the donor deliberately — what the panel draws with comes from it.**
   The applier drops the donor's own pages and popups once it has cloned what
   it needs (`"keep_donor_pages": true` keeps them), but every border, font and
   image a generated control draws with is the donor's: a panel cloned from a
   client fixture draws in that client's retail fonts and artwork. For anything
   going to a client, use a
   *seed* from `seeds/` — themed projects made through the Project Create
   Wizard (`powershell/New-GdlSeed.ps1`), across several theme families and sizes (`seeds/README.md` lists them; `git
   lfs pull` fetches them). Prefer one at the target size:
   `retarget` builds a correct panel at another size, but only 22% of controls
   match what Extron's own designers drew there. A panel turned where Extron
   draws no template that way up has no seed from the wizard: its seed is its
   default seed turned, by `powershell/New-GdlTurnedSeed.ps1`, whose line
   `gdl.seeds pick` prints (`seeds/README.md`). Extron's `.glt` templates cannot be
   donors — they have no `PBProject`, and a file built from one makes GUI
   Designer open empty and offer the Create Wizard. `donors` refuses them with
   that explanation. See `docs/from-scratch.md` §5c.

   `donors` checks six things, each of which otherwise surfaces only in a build:
   control types, page-name collisions (only a spec that keeps the donor's
   pages can have one), **border resources**, **font families**,
   **canvas size** and **button states**. The font one is the sly one — a family
   the donor has no `PBFontResource` for, and no seed carries to append, does not
   fail the build, it ships the panel in the donor's face. The states one is a guard: the applier gives each
   button exactly the states the spec names by resizing the cloned donor's, and
   refuses a donor button whose states are flagged against that - which no
   project in the corpus does. Answer its complaints before building; that is
   the entire point of the step.
7. **Build it.** With GUI Designer installed this is one command, which re-runs steps 4
   and 6 and finishes with step 8:

   ```powershell
   powershell\New-GdlPanel.ps1 -Spec examples\panel.json `
       -Donor "seeds\Afterburn 1035.gdl" -Output C:\gdlwork\Boardroom.gdl
   ```

   Leave out `-Donor` and it builds on the seed for the spec's `"family"`
   (step 2).

   check → donors → plan → apply → pack → open → Save and Build → wait →
   verify. It exits 0 only if the verifier passed, so it gates rather than
   reports. Nobody touches GUI Designer. Add `-KeepOpen` to leave it up, and
   `-IdMap <dir>` to also write the programmer's ID map, verified against the
   built panel.

   A canvas of several panels is built in one command too:
   `powershell\New-GdlPanels.ps1 -Out <translate's out dir> -Name <panel name>`
   writes the one ID map every panel shares (`python -m gdl.idmap
   write-panels`), builds each panel on its own seed with `New-GdlPanel.ps1`,
   and verifies each against that map (`tests/verify_idmap.py --panel`).

   Without GUI Designer, stop at `python -m gdl.spec plan <spec.json>
   out/plan.json --donor <donor.gdl>` - without the donor, a border it lacks
   is planned as named and builds as the clone's own; the rest runs where it
   is installed, per `docs/from-scratch.md` §7.
8. **Verify the build** (already done for you by `New-GdlPanel.ps1`):
   `python tests/verify_built.py out/plan.json <built.gdl>`. Do not skip this
   because the build was clean; that is exactly when it earns its keep. It
   checks geometry, captions, popup bindings **and color** — the last read off
   the rasterized artwork, since a built control's `BackgroundFillColor` reads
   back transparent white whatever you authored.

### B. Modify an existing panel

There is a vocabulary for this - write the change as JSON, resolve it against
the real project, then apply:

1. **Describe the change** - see `examples/edits.json`. Five ops:
   `rename` (captions), `restyle` (color remap), `states` (add, remove or
   rename a button's states), `retarget` (another panel model, or the other
   way up for one that rotates, optionally rescaling), `renumber` (addressable
   `userId`s). Selectors are ANDed and
   support exact or regex match on name and caption.
2. **Check it**: `python -m gdl.edit check <edits.json> <panel.gdl>`. Every
   selector resolves against the real file, so "matched nothing" is an error
   here rather than a silent no-op at apply time. Errors block; warnings do not.
3. **Emit the plan**: `python -m gdl.edit plan <edits.json> <panel.gdl>
   out/edits-plan.json`.
4. **Apply**: `powershell\Apply-GdlEdits.ps1 <ProjectGCP> <plan> <out>`.
5. **Build, then verify**: `python tests/verify_built.py out/edits-plan.json
   <built.gdl>`.

Three things about renaming and restyling that are not obvious:

- A caption usually is **not** in the control's `textField`. It is on the first
  state, or it is *formatted* text (`ftextField`) with hand-placed tabs and line
  breaks. `gdl.edit` writes it back wherever it found it.
- A **formatted** caption is baked into the artwork. Making one longer wraps it
  onto an unindented second line over the icon - `check` warns, and the only
  real verification is looking at the rasterized asset.
- **A button is its states**, and they need not match: most keep their fill
  only on their states, and Off and On may say different things. `rename` and
  `restyle` write each state by index. A `rename` with one `text` is refused
  on a button whose states say different things unless `state` names which to
  rename; `map` renames only the states that say the old caption.
  `docs/editing.md` *A button is its states*.

Reading and rendering need nothing but Python and Pillow:

```bash
python -m gdl.project <file.gdl>      # resources, fills, borders
python -m gdl.themes  <file.gdl>      # the palette it actually uses
python tests/score.py record <file.gdl> <snapshots> -o before.json
```

Writing goes through `powershell/GdlProject.ps1`, with GUI Designer installed. **Clone, never
construct** — every constructor and property setter throws headless, and a failed
setter writes the backing field *before* throwing, so it looks like it worked.

## Driving GUI Designer

Use `powershell\New-GdlPanel.ps1` (step A7). To script anything it does not
cover, read `docs/from-scratch.md` §7 first — the obvious ways to trigger a
build and to tell when it has finished are both wrong, and each fails in a way
that looks like success.

## Traps that have already cost time

Each of these produced a build that reported success and a panel that was
wrong. What to do is here; why is in `docs/gdl-format.md` §7 unless noted.

- **Check the font came from the spec.** `Set-GdlFont` applies size, weight and
  — only where the project has a `PBFontResource` for it — family. A family the
  donor lacks is appended first where a seed carries it (`plan --donor`); one
  no seed carries is refused by `gdl.spec donors`, which stops
  `New-GdlPanel.ps1` before anything is built. Applied any other way - a plan
  made without `--donor` - the panel ships in the donor's face and
  `verify_built.py` catches it after.
- **Set `flattenTextField = false` on cloned buttons**, or Build bakes the
  donor's caption into every button's artwork (`docs/from-scratch.md` §5b). The
  applier does. The one exception is a spec button with `"flatten": true`, used
  only by `tests/type_probe.py`: Build bakes it from each state's `ftextField`,
  which the applier then writes too (`docs/gdl-format.md` §2).
- **Clear what a clone inherits:** `<TLPImageID>` on a cloned page,
  `buttonImageField` on a cloned button.
- **Buttons render from their states.** Set text and color on every state, and
  reach them with `Get-GdlStates` — `$states.Count` reads 1 whatever the count,
  because `PBStates` has no `Count` and PowerShell answers 1 for it, so a loop
  to `.Count` writes state 0 only. Resize with `Set-GdlStateCount`, or reorder
  with `Set-GdlStateOrder`, never by constructing a `PBState`.
- **Wrap an `if` in `@()`, not the other way round.** `$x = if (...) { @($a) }`
  unrolls a one-element array into a bare object, and a `PSCustomObject`'s
  `.Count` is `$null` on 5.1 - which silently skipped resizing a one-state
  button. Write `$x = @(if (...) { $a })`.
- **"Field is null" is not "field is missing."** Clone a donor value from
  elsewhere in the project.
- **Popups go through `Register-GdlPopupGroup`, checked by
  `Test-GdlPopupBinding`** — a binding lives in four places (§6).
- **A page or popup may not take the name of one the built panel keeps from
  the donor** - its Offline Page, or every one under `keep_donor_pages`. Build
  refuses the duplicate only once it has started; `gdl.spec donors` checks.
- **Author every popup's size.** Build moves a control that overflows its page
  to 0,0, and a cloned popup keeps the donor's size. A modal is given the
  canvas; `check` names a standard popup with none, and its references' size.
- **A bridge-saved file always needs rebuilding** — `Save-GdlProject` resets
  every `TLPImageID` (§3) — and the bare `0x80070002` it prints on every save is
  not an error.

## Icons: two routes, both work

- **Images** — the normal route, and what real panels use. Extron's kits are
  under the install's `Resources\` (`docs/design-rules.md` §7 has what each
  holds), and Turbulence's art is extracted from its seed and templates, and
  Shockwave's Share Content from its seed (`vendor/README.md`); a spec names
  only what those resolve to.
  A spec button names one by its file name as `image`, on the button or per
  state (`{"name": "On", "image": "756x756_laptop-orange_sel.png"}`), with
  `"border": "none"` since the kit image draws the button; `images` brings any
  the donor lacks. The applier appends it and draws it the way every image
  button in the Afterburn seeds is drawn — `Fill` (fit, keeping the aspect),
  `MiddleCenter` — so size the button to the image's shape. A button or a
  label with no `fill` is written transparent, so neither keeps its donor's
  (Turbulence 320's donor label is opaque black); so is a panel, a line or a
  clock, and with no border unless it names one (the first panel in most
  seeds is an opaque, bordered slab). A donor
  image of the same name but other pixels is not reused: the file goes in as
  `<name>_1`. A slider's thumb is a kit image too: `thumb_image`, in the
  scheme's secondary accent (Afterburn: `440x440_thumb-1-<color>_sel.png`),
  `thumb` across and `thumb_height` along the rail where it is not square
  (Shockwave's is 52 by 34). Where the rail is art too, `track_image` and
  `fill_image` name it - both, since the applier writes only what it is given
  and a clone keeps its donor's other; such a slider is planned with no border
  or fill, since Build draws a bordered fill in place of the art.
- **Icon fonts** — for single-color icons, faster and needs no resource. Name
  the glyph - `"icon": "cable_tv"` on a button, a label or a state - and it is
  drawn in the icon font: the control's `font`, else the theme's `icon_font`,
  else the face the spec's `"family"` sets its own icons in. Afterburn, Mach
  and Shockwave each have one; Turbulence draws nearly all of its icons as images
  (`docs/design-rules.md` §6 has the faces). `python -m gdl.spec icons
  <family>` lists what an icon takes, and with a `.png` after it draws the
  glyphs: Extron-Afterburn names its own (`cable_tv`, `home`, `power`); Mach's
  and Shockwave's faces name none, so pick from the sheet and give the
  codepoint, `"icon": "U+E93A"`. A name the face lacks is a `check` problem
  that offers the nearest, and a glyph the donor's own face lacks is a `donors`
  one - the Mach seeds embed an older Extron-Lift than the install has. An icon
  is the control's whole caption, in a face with no letters, so its words go on
  a label beside it. `examples/icons.json` has each of these.

## Verification gates — do not skip

- **Render change**: `tests/score.py record` before and after, then `diff`. It
  exits non-zero on any page regressing. A change that improves one page and
  regresses twenty is the documented failure mode here.
- **Spec or edit change**: `python -m pytest`, all of it.
- **Anything authored**: two gates, not one.
  1. GUI Designer must **open and build** it — a file that merely serializes
     proves nothing.
  2. `python tests/verify_built.py <plan.json> <built.gdl>` — because a build
     that reports 0 errors still relocates controls, bakes captions and drops
     fills. Every one of this repo's worst authoring bugs built perfectly
     clean. `New-GdlPanel.ps1` runs this for you and fails the run on it.
- Report numbers you actually ran. Never state a build succeeded on the strength
  of "no error dialog appeared" — say what you checked (payload member present,
  N controls rasterized, verifier clean).

## Where the design authority lives

`docs/design-rules.md` separates three things and you must keep them separate:
what Extron **documents**, what the client fixture happens to **do**, and
what we **extrapolated**. Never quote an extrapolated number to a client as an
Extron requirement — the touch-target formula in particular reproduces Extron's
published table but is our derivation, not their stated rule.
