# Extron's own design rules, as far as they can be encoded

Sources, all primary:

- **GUI Design Standards rev E** (94pp) — Extron's design guide. Page numbers below
  are its printed page numbers.
- **Afterburn Theme Guide** (16pp, 79-607-24 rev A) — the theme's colour system.
- **GUI Designer 1.27.0.9 itself** — platform classes and control fields, read out
  of the installed assemblies.

The point of this file is to separate three things that are easy to blur: what
Extron **documents**, what the Liberty Bank fixture happens to **do**, and what we
**guessed**. Only the first is authoritative. Anything marked *extrapolated* must
never be presented to a client as an Extron requirement.

---

## 1. Panels and resolutions

The canvas is **not** fixed. GUI Designer 1.27.0.9's Project Create Wizard offers
**55 panel types**. Model names below are read from that dropdown — the shipped,
authoritative list — and resolutions from the matching platform class.

| Resolution | Models |
|---|---|
| 320 × 240 | CCI Pro 700, TLP Pro 320C, TLP Pro 320M |
| 320 × 480 | TLP Pro 300M |
| 800 × 480 | **TLC** Pro 521M, **TLC** Pro 526M, TLP Pro 525C/M/T |
| 1024 × 600 | **TLC** Pro 726M, TLP Pro 725C/M/T, TLP Pro 1022M/T, ZRTP Pro 725M/T |
| 1280 × 720 | TLP Pro 535M, TLP Pro 535T |
| 1280 × 800 | **TLC** Pro 1026M, TLP Pro 835C/M/T, TLP Pro 1025M/T, TLP Pro 1035M/T, TLP Pro 1220MG/TG, TLP Pro 1225MG/TG, ZRTP Pro 1025M/T |
| 1366 × 768 | TLP Pro 1520MG/TG, TLP Pro 1525MG/TG |
| 1920 × 1080 | TLI Pro 201, TLP Pro 1535M/T, TLP Pro 1720MG/TG, TLP Pro 1725MG/TG |

Resolution not determined by this probe: TLP Pro 520M, 720C/M/T, 1020M/T,
1230WTG, TLI Pro 101 (the class-name match failed and was not guessed at). The
three "Extron Control for Android / iOS / Web" entries are soft clients with no
fixed panel class.

**TLC and TLP are different product lines** — TLC Pro 521M/526M/726M/1026M are
not TLP panels. An earlier version of this table conflated them, because the
names were reconstructed from internal class symbols like `PBTLP1720MGPlatform`
rather than read from the shipped list. Don't do that; models get retired and
class names outlive them.

**Touch-target minimums are keyed to physical PPI, not to pixel resolution.** The
same resolution spans several models at different physical sizes, so one
resolution can have more than one documented minimum. Note also that 1280 × 720
*does* have models (TLP Pro 535M/T) — what it lacks is a row in Extron's
touch-target Quick Reference table, which is a different thing.

## 2. Hard rules — stated as musts

**Touch targets and spacing** (pp. 22–25, 55–56, 90)

- A touch target must be **9 mm × 9 mm (3/8″)** or larger. Restated identically for
  every panel size category. 7 mm is called the absolute floor for *phones*;
  touchpanels need more because the user is further away.
- Leave at least **2 mm (1/16″)** between touchable elements.
- "As a general rule for small buttons of **72 pixels or less**, there should be at
  least **5 to 10 pixels** between them." (p. 56)
- GUI Designer 1.7+ nudges by **10 px** per arrow key press — a de facto grid unit.
- Spacing must be uniform horizontally and vertically.

**Density** (pp. 49, 58) — the two numeric caps in the document:

- **No more than nine buttons in a control group.** (p. 58)
- **No more than six colours in a project.** (p. 49)

**Contrast** (p. 43)

- Minimum **4.5 : 1** for all text and objects needed for interaction.
- ~12.63 : 1 is called optimum; the 19.22 : 1 example is shown *reducing*
  readability, so treat ~16 : 1 as a soft ceiling.

**Keypads** (p. 59)

- The **telephone** layout (1-2-3 on the top row) is the standard and must be used.
  The calculator/ten-key layout (7-8-9 top) is explicitly "do not use".

**Typography** (pp. 65–67, 84)

- At most **2 fonts** per project. Named: Arial, Verdana, Calibri, Open Sans.
- Body text **14 pt or larger**.
- **Never** italic or bold-italic; never underline, small caps, subscript,
  strikethrough, outline, embossed, superscript or narrow; no serif fonts; no
  script faces, Chalkduster or Papyrus.
- Label text must fill its button without touching the border. If it does not fit,
  resize the **whole group** — never mix font sizes within one button group.
- Different font sizes *between* group label and sub-label are required, to create
  hierarchy (p. 63).

**Behaviour** (pp. 8, 13, 15, 70, 71)

- Respond within **1 second**. (A progress indicator is required past 5 s per the
  p. 13 table, or past 10 s per the p. 8 body text — the document contradicts
  itself; take the conservative 5 s.)
- Every tap must give obvious feedback that the request was recognised *and*
  whether it succeeded.
- Any costly or irreversible action needs a **modal confirmation with a cancel
  path**. Press-and-hold with no escape is called out as a failure.
- Every action needs a reachable inverse (end call, unmute, stop presenting).
- All popups on a given Popup Page Reference **inherit that reference's exact
  dimensions**, and only one can show at a time. To swap between them they must be
  in a named **Popup Page Group**. (p. 70 — this matches what the format enforces.)
- A modal covers the page and any active non-modal popups with a translucent
  overlay, disabling them. (p. 71)

## 3. Don'ts

- Don't signal "selected" with a border alone — change colour *and* add a text cue.
- Don't use flip-flop buttons (one button whose label swaps between On/Off): the
  user cannot tell whether it shows current state or the action. Separate control
  from status. (p. 54)
- Don't label things by room-relative direction — "left display", "front sources".
  Panel orientation is ambiguous; use a room diagram. (p. 33)
- Don't hyphenate to achieve word wrap. (p. 60)
- Don't repeat a group's noun on every button — label the group "Volume" and the
  buttons "Up"/"Down", not "Volume Up"/"Volume Down". (p. 64)
- Don't use ALL CAPS or all lowercase except sparingly; mixed case reads fastest.
- Don't use "Yes"/"No" on a confirmation — use the verb ("End Call" / "Cancel").
- Don't style a non-interactive label with button affordance.
- Don't rely on colour alone; GUI Designer has a monochrome test mode for this.
- Don't use acronyms the audience may not share (VTC, ALC). HDMI/DVD/DVR/AUX are
  fine.

## 4. Themes — four of them, one documented

Extron ships **Afterburn, Mach, Shockwave and Turbulence**, each with a resource
kit, but publishes a colour guide only for Afterburn. `gdl/themes.py` handles both
cases: `AFTERBURN` is the transcribed token set, and `extract(path)` reads the
palette, borders and fonts a `.glt` template or `.gdl` project actually uses.

`extract()` is validated against the one theme that can be: run on
`Afterburn 1020 Series.glt` it returns `#BABCCE`, `#37394E`, `#242634` and
`#6A6E89` — every one in the published guide, and nothing spurious — without
reading the guide. So it can be trusted on the three undocumented themes, and on
a client's own house style read off a panel they already have.

### The Afterburn colour system — fully encodable

Straight from the theme guide. This is a complete token set.

| Token | Hex | Use |
|---|---|---|
| page background | `#242634` | pages |
| modal background | `#242634` @ 20% transparency | modal scrim |
| primary text | `#FFFFFF` | headings, button labels, paragraphs |
| secondary text | `#BABCCE` | subheadings, date/time |
| button border (idle) | `#BABCCE` | outlined buttons |
| button border (pressed/selected) | `#FFFFFF` | |
| button fill (idle) | `#37394E` | |
| button fill (pressed/selected) | `#242634` | |
| icon primary | `#BABCCE` | single-colour icons, strokes |
| icon secondary | `#767789` | de-emphasised icon parts |
| icon background | `#414459` | |
| divider lines | `#BABCCE` | |
| shapes | `#6A6E89` | container shapes |
| slider/level track | `#242634` (over image) or `#37394E` (over colour) | |
| slider fill | `#BABCCE` | |
| toggle thumb (off) | `#6A6E89` | |

Four accent schemes; pick one per project and keep it:

| Scheme | Primary (selection lines, icon selection) | Secondary (toggle/slider thumb, level fill) |
|---|---|---|
| 1 (default) | Orange `#D69B61` | Periwinkle `#626ACF` |
| 2 | Light Blue `#6ACFE8` | Light Green `#84B266` |
| 3 | Gold `#D6B961` | Light Green `#84B266` |
| 4 | Medium Blue `#4695D6` | Gold `#D6B961` |

**Note the discrepancy:** the guide specifies the modal background as `#242634` at
20% transparency. The Liberty Bank fixture instead uses **opaque black** on every
modal, with the dimming baked into artwork asset 36 at alpha 166 (~65% opacity).
So the fixture deviates from the theme, which is why the scrim rule in
`research/final_patch.py` was unobservable there — see `docs/render-fidelity.md`.

## 5. Four button archetypes

The theme guide defines these, and they map cleanly onto generator output:

| Type | Border | Fill | Selection indicator |
|---|---|---|---|
| Icon | none | pressed state only | — |
| Outlined | yes | yes | border + fill change |
| Vertical list | none | pressed/selected only | **line on the left** |
| Horizontal list | none | pressed/selected only | **line on the bottom** |

States: Not Selected, Selected, Pressed, Multi-state Status.

## 6. Icons: images **and** fonts, both supported

Two routes. Images are the normal one — real panels use them heavily (the Liberty
Bank fixture carries 38 `PBImageResource` and 1,855 `PBResourceReferenceImage`) —
and the font is an additional convenience for single-colour icons. An earlier
draft of this file said icons "come from a font, not images", which was an
overcorrection.

**Images.** Every control has *two* image slots — `buttonImageField` (the icon)
and `backgroundImageField` — each with its own alignment, layout, left/top offset
and transparency key colour. A `PBImageResource` holds the bitmap
(`dataField` is a `System.Drawing.Bitmap`); a `PBResourceReferenceImage` names it.
**Verified**: cloning an image resource, replacing its bitmap with a PNG from
Extron's kit, appending it and binding it to a button built with 0 errors, and the
icon was rasterised into the button's artwork. Set `buttonImageLayout`/alignment
or a 440×440 kit icon will swamp a small button.

Extron's kits ship: Afterburn 3,376 files, Turbulence 1,408, Shockwave 1,124,
Mach 596.

**Icon fonts.** For single-colour icons the theme guide says to use the theme
font instead, which needs no resource at all:

| Font | Glyphs | Range |
|---|---|---|
| `Extron - Afterburn 1a` | 136 | U+E900–U+E98C |
| `Extron-Lift` (Mach) | 121 | U+E900–U+E978 |
| `Extron GUIC Video Conference 1` | 203 | U+F008–U+F0FF |

Shockwave's font has only 18 glyphs and is not an icon set; Turbulence ships no
font. Those two are images-only.

## 7. Extron ships the donor library

`C:\Users\Public\Documents\Extron\GUI Designer Templates` contains per-series
`.glt` templates — Afterburn and Mach for the 300/320/520/535/1020/1220/1230/1520/
1720 families, plus Zoom Rooms and Teams Rooms variants — and the full Afterburn
resource kit.

A `.glt` is the same container as a `.gdl` (KP-mangled ZIP, one `ProjectGCP`) but
has **no `PBProject`** — it is a bare library of pages and popups. `gdl/project.py`
reads them. This answers "where does a generator get donor objects to clone" with
an official per-panel-model answer.

## 8. What the standards do NOT specify

A generator has to decide these itself, and should say so rather than implying
Extron blessed them:

- Page or popup **numbering/naming** conventions. Nothing, anywhere.
- **Margins / safe area** from the screen edge. Only inter-object spacing is given.
- Any **grid system**. The document's "zones" are qualitative (top-left, footer),
  not coordinates.
- A **pt → px** basis. Sizes are in points with no stated DPI.
- Default **popup/modal dimensions** — only that a popup inherits its reference's.
- A **formula** for touch targets on panels absent from the table. p. 90 says
  third-party devices must be "calculated manually" and gives no formula.
  `9 mm × PPI` and `2 mm × PPI` reproduce every documented row closely, but that is
  our reverse-engineering, *not* a stated rule.
- Corner radius, bevel width, shadow depth; animation timings; icon-specific size
  minimums.

## 9. Where the Liberty Bank fixture sits

Useful because it is a real shipped panel, but it is evidence of one integrator's
taste, not of the standard:

- Its 1280×800 buttons (200×70, 320×120) and 16–20 px gutters **comfortably exceed**
  every documented minimum for that resolution. Over-compliant, not in conflict.
- Its 96 px header band and 232 px left nav rail correspond to **no documented
  number** — the standards give no header height or rail width at all.
- Its single-left-rail layout **diverges from** the canonical medium/large pattern
  (pp. 34–37), which puts environmental controls on *both* side bars with source
  selection top-right. Not wrong — the standards describe one canonical scheme, they
  do not forbid others — but it should not be cited as "the" Extron layout.
