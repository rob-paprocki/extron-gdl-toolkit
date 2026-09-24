# Panel-aware design systems

Design, approved 2026-09-24. One Claude Design canvas describes a room; the
toolkit builds it for every panel the room has, each sized for that panel's
physical screen, so a 7" or 5" panel is not a cramped copy of a 10" one. Then
Mach, Shockwave and Turbulence as design systems on the same footing.

This is a forward-looking record. As each phase lands, what it makes true moves
into the topic homes (`docs/claude-design.md`, `docs/design-rules.md`,
`docs/gdl-format.md`, `docs/idmap.md`), and `docs/ROADMAP.md` stops pointing
here.

## 1. Decisions

| Question | Decision |
|---|---|
| Which panels | All four groups: 320×240 and 300M; 800×480 and 1024×600; 1280×800; 1366×768, 1920×1080 and 1920×720. Not the Zoom Rooms or Teams Rooms templates. |
| What "cramped" means | Physical: targets, gaps and text too small **in millimetres** on a small, dense screen. DPI, not resolution. |
| A room with two panel sizes | **One canvas, many panels.** Each panel's layout is derived from the canvas. |
| When it does not fit | **Reflow, then paginate**, the way Extron does per tier (§4.2). Same controls, names and IDs on every panel; one ID map. |
| Where derivation lives | **In the design system's components**, so the canvas previews what gets built, and the translator runs the same code headlessly per panel. |

## 2. Terms

GUI Designer's, used exactly:

- **Page** - the whole screen, one at a time. Navigation flips pages.
- **Popup** (standard popup) - part of the screen. It belongs to a popup
  group and shows in a region of a page (a popup page reference); showing
  another popup of the same group replaces it, and the page around it stays
  usable.
- **Modal** (modal popup) - the whole screen, over the current page, which it
  dims and blocks until closed. Build adds the scrim; every modal in the corpus
  is full-canvas (`docs/gdl-format.md` §5).

This design's own:

- **Panel** - a model (`TLP725T`), not a resolution: its pixel size and DPI
  come from `gdl.spec.MODELS_FULL`.
- **Design panel** - the first of a canvas's panels, the one it is drawn at.
- **Tier** - a panel's structural class by physical diagonal (§4.1).
- **Group** - a titled set of like controls on a page (Sources, Displays,
  Presets, Cameras): the unit that paginates.

## 3. What Extron's templates do

Measured off every series template of all four themes
(`C:\Users\Public\Documents\Extron\GUI Designer Templates\TouchLink Templates`)
by parsing each `.glt`'s authoring graph with `gdl/project.py`, DPIs from GUI
Designer's own `TemplateInfoTable.config` and `MODELS_FULL`. Nothing was built,
so these are authored geometry, not built artwork.

- **Structure steps by physical size, not pixels.** Three families, the same in
  all four themes:
  - **≥ about 7"** (720, 1020, 1220, 1520, 1720, ECP): the full template - 7-8
    pages, 24-29 popups - resized only.
  - **about 5"** (520, 535): 2-3 pages. One hub page with a content region
    (Afterburn 520: a 686×480 popup region) and a rail of buttons (66 px wide,
    at x 712-778); the source picker becomes a popup in that region.
  - **about 3.5"** (300, 320): single-purpose pages, a page per source, and
    whole features (video conferencing, recording, multi-window) dropped.

  Pixels cannot place a panel: the 520 and 720 series are both 800×480, at
  188.15 DPI (4.96") and 133.33 DPI (7.00"), and sit in different families.
- **Within the full family, sizes resize** - Afterburn in a few discrete sets
  (1220 and 1520 identical; 1020 smaller; 1720 larger), Shockwave and
  Turbulence proportionally to canvas width with a floor near 100 px.
- **Type holds its point size**, stepping once or twice across the range
  (Turbulence: 12 pt body on 720/1020, 16 pt on 1220/1520). Content is
  trimmed; text is not shrunk.
- **Source rows cap at 4** in every Afterburn series that has one, 1024 px wide
  to 1920 px; extra width makes bigger buttons, never a fifth.
- **Extron's own templates break Extron's documented minimums on dense
  panels.** One 1280×800 template serves 124.75 DPI (1220), 149 (1025/1035) and
  188.68 (835): its common 64 px button is 13.0, 10.9 and 8.6 mm, and an 8 px
  gap is 1.1 mm on an 835. The 520's own common button is 8.9 mm; its tightest
  rail gap 0.4 mm. Captions run 10-12 pt against the documented 14. So the
  templates are evidence of structure, not of minimums.
- **Segmented controls touch on purpose**: Shockwave's Display On/Off/Mute is
  butted at 0-5 px in every series. A spacing check must tell one segmented
  control from two neighbours.
- **Artwork**: button and icon art is one master per glyph, scaled to any rect.
  Backgrounds are drawn per resolution - Afterburn all nine
  (`Backgrounds/<5x canvas>/`), Shockwave four, Mach six generic photographs;
  Turbulence has no `Resources` folder here at all, its images live inside each
  `.glt`.
- **Soft clients have no DPI.** ECP templates are pixel copies of the 1220 and
  1720 series; GUI Designer's 220 DPI is a default, not the host's.

## 4. Design

### 4.1 Panels, tiers and physical units

A canvas names its panels on its Pages: `panels="TLP1025T TLP725T TLP525T"`.
The first is the design panel. Each resolves through `MODELS_FULL` to pixels
and DPI, so to a diagonal and a tier:

| Tier | Diagonal | Pattern | Panels |
|---|---|---|---|
| A | ≥ 6.5" | the full layout, resized | 1025/1035/1026/835, 1220/1225, 725/726, 1020/1022, 720, 1520/1525, 1535/1720/1725, 1230W |
| B | 4 - 6.5" | a hub page: content region and rail | 520/525, 521/526, 535 |
| C | < 4" | single-purpose pages | 320, 300M |

The thresholds are this toolkit's reading of Extron's templates, not an Extron
rule. ECP and TLI Pro run on a screen their model does not define, so they take
a device preset and a DPI from the canvas; the table's 220 DPI is a default.

**Sizes are physical, per panel:**

- **Touch target ≥ 9 mm, gap ≥ 2 mm** - Extron's documented minimums
  (`docs/design-rules.md` §2), converted with the panel's DPI
  (`gdl.spec.touch_minimums`). Buttons of one segmented control may touch.
- **Type stays in points**, with a per-panel floor: the documented 14 pt, and
  if Phase 0 shows GUI Designer draws points at a fixed pixel size on every
  panel, a physical floor on top for dense panels - labelled as ours, never as
  Extron's.
- **Tokens state the design panel only.** The Design System format lets only
  colors vary (per theme); everything per-panel lives in a model table the
  bundle carries, built from `MODELS_FULL`, and reaches components through the
  context Page already provides.

**Per-resolution assets come from Extron, never from scaling:** each series'
background art, and its layout regions (Afterburn's squircle main area, a tier
B hub's content region and rail) measured off that series' own template.
Scaling one layout matches Extron's hand layout for 22% of controls
(`seeds/README.md`).

**Model table fixes first**: `TLP1230WTG` reads 800×480 at 0 DPI (it is
1920×720; its template says 166 DPI), and `TLP300M` is portrait only (the 300M
also runs 480×320).

### 4.2 Deriving a layout per panel

`Group` lays its children out as a wrapping grid: physical minimum sizes, the
template's cap per row. For each panel, a page is:

1. **Sized** - every control at that panel's minimums, text at its points.
2. **Reflowed** - containers wrap; groups take the columns that fit, to their
   cap.
3. **Paginated, by tier:**
   - **A: the group pages in place.** Its region holds a popup group; each page
     of its items is a popup there, flipped with Previous and Next. The rest of
     the page does not change.
   - **B: the page becomes a hub** - a rail of buttons, one per group (its title
     and icon), and a content region. Each group is a popup in that region, one
     showing at a time, the first on arrival. Controls in no group (volume,
     power) stay on the hub page. A group too big for the region is several
     popups of the same group, each with Previous and Next - never a popup
     within a popup.
   - **C: groups become pages**, reached from buttons on the hub page, each with
     Back; one too big for a page runs over several, with Previous and Next.
4. **Refused**, if it still does not fit: the translator names that panel and
   what does not fit. Nothing is dropped.

What the canvas designed stays what it is on every panel: a modal stays a
modal, full screen at that panel's size; a popup keeps its group and region and
reflows; every control keeps its name, states, `does` and ID. What the
derivation adds - rail buttons, Previous, Next, Back - is navigation, with no
program ID.

**Preview**: a Page's `preview` panel draws the artboard as that panel derives
it, scaled to fit, its derived popups and pages reachable in Play. Phase 0
checks Claude Design shows that; if it cannot, derived layouts are seen on the
sign-off page only.

### 4.3 Translation, seeds, build, ID map, sign-off

- **Translate** lays every artboard out once per panel - viewport and
  millimetre scale from the model table - and writes `out/<model>/spec.json`
  each naming its seed. Any panel refused writes nothing, and each panel's
  problems are named.
- **A seed per panel.** The built panel is its seed's model (`seeds/README.md`),
  so a 725 needs a 725 seed. `New-GdlSeed.ps1` drives the Project Create Wizard
  for a theme and model - proven by hand for the ECP seeds - and refuses a blank
  result, since the wizard can produce one silently. The translator refuses a
  panel with no seed and prints the command that makes it.
- **Build**: `New-GdlPanel.ps1` per panel, each verified on its own as now, by a
  wrapper that builds them all.
- **IDs** are assigned once per canvas control, so a control has one ID on
  every panel and one program drives them all. **One ID map**, with a column per
  panel for where the control is (page, popup or modal), verified against every
  built panel.
- **Sign-off**: one page, a section per panel; each page, popup and modal as
  designed and derived, beside it as built.
- **Checks per panel**: 9 mm targets (already applied by `gdl.spec`), 2 mm
  spacing except within a segmented control, the type floor, and a modal is
  full screen.

## 5. Phases

Each phase is its own PR, with its tests and the docs it changes, and an
adversarial review before merge.

**Phase 0 - settle the unknowns.**
1. **Type across panels.** Build labels at known point sizes on a non-1280×800
   seed and a dense one; measure the built glyphs. Decides the type floor, and
   whether type sizes vary by model at all (`gdl/compose.py`'s 1.375 px/pt was
   calibrated on one model).
2. **Claude Design preview.** A test system whose Page changes size with
   `preview`; see what the canvas shows.
3. **Model table**: the 1230W and 300M rows.
4. **Seeds**: `New-GdlSeed.ps1`, and the Afterburn seeds the proof needs
   beside the 1035 one that exists: TLP725T (a dense A), TLP525T (B) and
   TLP320M (C).

**Phase 1 - Afterburn, panel-aware.** The per-panel model table; layouts and
backgrounds per series; millimetre components; Page `panels` and `preview`;
`Group` with reflow and tier pagination; per-panel translation; shared IDs and
the ID map across panels; per-panel sign-off; the checks. Proof: the huddle
canvas built and verified on the 1035, 725, 525 and 320.

**Phase 2 - Mach.** It builds today. Register it; correct its slider track (15
px, not 8, from `15x182_empty.png`/`182x15_empty.png`) in the profile and
`docs/design-rules.md` §7 together; themes from its kit backgrounds; its
per-series layouts; every design-system test run against every template.
Proven on two panels.

**Phase 3 - Shockwave.** Its profile does not build: add `examples`, and give
`defaults.slider`/`level` the shape the others use (`thumb` a size,
`thumb_color` the color, `orientation`, `track`). Its kit is keyed by status
color (`1248x440_blue_nsel.png`), not icon, so no icon variants without a
parser for that. Backgrounds for four resolutions. Proven on two panels.

**Phase 4 - Turbulence.** Its images come out of the `.glt` files, since no
`Resources/Turbulence` exists; its seeds come from `New-GdlSeed.ps1`; its
profile's claim that 2D Rectangle is drawn by nothing is wrong (12 references)
and gets re-derived. Proven on two panels.

## 6. Also found

- `docs/from-scratch.md` line 564 says the Project Create Wizard "cannot be
  driven at all", against its own §5c and `seeds/README.md`.
- `mach.json` and `turbulence.json` cite counts from a `theme_survey.py` that
  is not in the repo; a plain `gdl.project` scan gets close but not identical
  (189 against 183). The counting script gets committed, or the counts
  re-derived by one that is.
- The design-system tests load only Afterburn, so a broken profile (Shockwave's
  today) passes CI.
