# Render fidelity: what GUI Designer actually draws

Findings from scoring our compositor against GUI Designer's own snapshot
exports (50 renders of a client project, findings 1-8, and the synthetic
fixture's 29, §9). Every claim below was measured, and findings 1-8 were each
put through an adversarial verification pass. The client project and its
renders are no longer in the repo (`docs/history.md`): findings 1-8 stand as
measured, and the synthetic fixture is the render baseline
(`tests/baseline-synthetic.json`, `CLAUDE.md` *Verifying a change*).

Baseline when this started: mean **4.57%** differing pixels, worst page 40.22%.

## 1. Control fill is `borderFillColor`, and `layout.json` does not export it

The single largest defect. The Offline page differed by 40% because of one
missing rounded rectangle.

`backgroundFillColor` is transparent on **every control in every file**, which
made "the art PNG carries the fill" look like a complete rule. It is not. The
real interior fill is `borderFillColorField`, and the silhouette comes from
`borderField`, a **named** resource:

```
PBShape "Offline Window"
  backgroundFillColorField = ARGB(0,0,0,0)        <- what layout.json exports
  borderFillColorField     = ARGB(255,36,38,52)   <- the actual fill
  borderField              = "Afterburn - 10 Radius 0 Thick"
  <TLPImageID>             = -1
```

`0xFF242634` is exactly the page/modal background from the Afterburn theme
guide. Neither field survives into `layout.json`; Build bakes them into the PNG
and discards them. Wherever a control has real artwork this is invisible — the
Offline page is the only place in the corpus with `TLPImageID == -1`, so it is
the only place the loss shows.

Read them with `gdl/project.py`, which resolves the authoring model directly.

**This matters far more for authoring than for rendering:** these are the
properties a generator sets. Corner radius and thickness come from the resource
name (`"Afterburn - 10 Radius 2 Thick"`), so a generator picks named resources
rather than inventing geometry. Seven are *referenced* by this project — but 34
are **defined** in it; see `docs/from-scratch.md`.

**Implemented** in `gdl/compose.py` as `fill_index()` + `draw_fill()`, joined on
`(page id, control id)` — the pair both models already share. A page's
`idField` is layout.json's `Page.ID` and a control's `idField` is its
`Control.ID`; verified equal across all six of the client project's files
(157 pages, 3,744 controls). `gdl/project.py`'s `pages()` walks the authoring model's page tree to
supply it. Measured: Offline Page 40.22% → 1.28%, all 26 other pages ±0.00%.

The first version keyed on `(type, rect)` instead, because the authoring model
was only read as a flat object graph. It scored identically — but only because
the eligible subset (no artwork *and* a real fill) is a single control per file.
`(type, rect)` is **not** unique over controls generally: each of those files
had 127–132 colliding groups, and nothing checked the destination side, so two
same-typed, same-positioned controls on different pages would both have been
filled. Recorded because "it scored the same" is exactly how a key like that
survives review.

One trap in the page walk: a serialized `List<T>`'s `_items` is over-allocated —
32 slots holding 4 pages — so it must be sliced to `_size`, or the tail of
`None`s reads as real empty objects.

The index held exactly **one** entry in each of those six files — the same
`PBShape "Offline Window"` — so this rule was narrow there even though it was
worth 1.44 points of their mean.

### The scrim half of the rule is not verifiable here

`research/final_patch.py` also implements a rule the earlier writeup recorded:
a modal page with `TLPImageID == -1` paints its `BackgroundFillColor` at 65%
opacity, matching the alpha 166 baked into scrim asset 36. That rule was **not**
shipped, because nothing in the corpus can test it:

- All **seven** modal popups carry `BackgroundFillColor` = opaque **black**.
- Six of them have real artwork (asset 36 — which is where the alpha was
  measured), so the scrim is already in their PNG.
- The Offline page is the only modal without artwork, and there black at 65%
  over an already-black canvas is indistinguishable from black. Measured
  directly: ground truth outside the window rect is `(0,0,0)`, and so is ours,
  before and after.

So `SCRIM_ALPHA = 165` is a plausible generalisation with zero observable
consequence in this corpus. It is left in `research/` rather than shipped into
the maintained compositor, where it would read as a measured rule.

What does hold, and makes the rule unnecessary: **Build bakes the scrim into
every modal's artwork** - full-canvas black at the modal's own transparency,
alpha 166 at the 35% every template authors - whatever background color the
popup was authored with (`docs/gdl-format.md` §5). Every modal in the
Afterburn, Mach and Shockwave seeds carries it, and so did a modal built from a
spec with a `#242634` background. The compositor pastes that artwork like any other; to show what the
panel shows, composite it over the page beneath (`gdl.design compare` does,
over the start page).

## 2. Compositing blends in light, and writes over nothing at full strength

GUI Designer's snapshot composites a control's art with GDI+'s gamma-corrected
source-over. Over opaque art, a pixel with alpha between 0 and 255 blends at
its own alpha **in light**: each channel raised to 2.2, mixed, and lowered
again - so a translucent fill and an antialiased edge are both lighter than a
plain blend of the same colors. Over nothing, a transparent destination, a
pixel is written as it is, and the page then goes on black at full strength
(finding 4).

Measured on the synthetic fixture (§9) over every partial-alpha asset pixel
lying over opaque art and under no later control or caption - 27,127 of them
on its 29 pages, translucent fills and antialiased edges both - the mean error
a channel of each rule:

| binary write | plain blend | sRGB curve | gamma 2.1 | **gamma 2.2** | gamma 2.3 |
|---|---|---|---|---|---|
| 85.43 | 29.04 | 1.80 | 3.10 | **1.08** | 2.72 |

White at 20% over the page (#242634) reads (126,126,130) in the snapshot, where
a plain blend gives (80,81,93) and a binary write white; the half-covered row of
a 1 px line, alpha 128, reads (157,114,78), where a binary write gives the
line's own (213,155,97). Implemented as `gdl.compose.snapshot_over` (`GAMMA`):
the synthetic mean 3.00% → 2.72%, median 2.57% → 2.48%, worst 7.05% → 7.00%,
16 pages better, 13 unmoved and none worse - Buttons 7.05% → 2.54%, Controls
3.73% → 1.85% - and the fixture's every line and slider rect 0.00% where they
were 2.06% and 0.54%.

Nothing in the fixture puts a partial-alpha pixel over nothing, so that half of
the rule rests on finding 4's text and on the client's project: over 3,296
partial-alpha pixels there, a binary write was off by 2.15 levels and a plain
blend by 97. That measurement did not record what lay under them, and the
project is gone, so whether they lay over nothing cannot be checked
(`docs/history.md`).

`gdl.compose.paste` keeps the snapshot's rule by default, and it is the rule
wherever a render is **scored** against a snapshot: `tests/score.py`,
`tests/compare_snapshots.py` and the baseline. Everything a person reads as a
picture of the *panel* blends as Pillow does instead, in
`gdl.compose.as_the_panel()` (`BINARY` off): the sign-off
(`gdl.design compare`, via `_Built.image`), the critique loop's template side
(`gdl.design compare --template`), the design systems' template renders
(`gdl.designsys.render_templates`) and the spec preview (`gdl.spec render`).
There a translucent bar or well over its photo - Mach's #000000B4 header,
Shockwave's white well at 15% - is a plain blend, `draw_fill` composites a fill
the same way, and `flatten` lays the page on black by alpha rather than by the
binary mask. Each caller puts the rule back as it found it. That the panel
blends is read from the art (Build bakes the transparency into the PNG's
alpha); whether its firmware blends in light, as GUI Designer does, or plainly,
is not seen on a panel (`docs/ROADMAP.md` *Yours*).

Blending is the only thing `as_the_panel()` changes. `draw_text` does not read
`BINARY`, so the caption rules (§9) reach every one of those pictures as well:
GDI+'s padding, the lines GDI+ shows of a caption (`fitted`) and the oblique
drawn for an italic the project has no file for. A caption too deep for its box
is therefore cut **without an ellipsis** on the sheet a client signs, as the
snapshot shows it, and a left-aligned caption starts 1/6 em in
(`tests/test_signoff_blend.py` pins both). The Compare figures in
`docs/claude-design.md` were measured before these and are not re-recorded.

The sign-off's percentages stay above a scored page's even so: a modal drawn
over the start page differs from the designed one for other reasons.

## 3. Group-form popup references paint

A reference bound to a single popup (`IsPopupPageIdValid`) paints nothing. A
reference bound to a **group** (`IsPopupGroupIdValid`, `PopupID` =
`UInt64.MaxValue`) does: GUI Designer composites one group member into the
anchor rect, and takes its snapshot that way. Draw it in the anchor's own
z-order slot, not on top.

This was the whole of the Keyboards page error (10.55% -> 1.29%), and most of
Tech and Main-Presentation.

## 4. Text is bilevel or antialiased depending on the backdrop

**Implemented — but structurally, not as a per-control probe.** The compositor
now starts each page canvas *transparent* and flattens it onto black once, at
the end of the outermost `render_page`, with the binary rule the snapshot
keeps over nothing (finding 2). That alone produces finding 4's behavior, per
pixel rather than per control:

- Pillow's `ImageDraw.text` does source-over. Onto a **transparent**
  destination the glyph's coverage lands in the *alpha* channel while RGB stays
  the undiluted ink color, so the binary flatten writes every covered pixel at
  full strength — hard edges, i.e. **bilevel**.
- Over **opaque** artwork the destination alpha is already 255, so the glyph
  blends normally — **antialiased**.

So the backdrop decides, exactly as measured, without needing the `frac <=
0.152` probe. Measured across all 27 pages: mean 2.60% → 2.33%, median 2.02% →
1.85%, worst 8.99% → 8.15%, **16 pages improved and none regressed**.

The flatten threshold was swept, and `alpha > 0` is the corpus optimum by a
clear margin — it is monotonic, so a "truer" 50%-coverage bilevel is worse:

| threshold | 1 | 32 | 64 | 96 | 128 | 160 | 192 | 224 |
|---|---|---|---|---|---|---|---|---|
| mean | **2.328%** | 2.348% | 2.378% | 2.384% | 2.400% | 2.435% | 2.445% | 2.486% |

Treat that as measured, not understood: "any coverage becomes full ink" fattens
glyphs, and it may be winning partly by compensating for glyph advances that
are still slightly narrow (see the fractional-advance work below) rather than
because GDI does precisely this. If advances are ever fixed, re-run this sweep.

### The original measurement — historical

This is how finding 4 was first proven. The structural rule above supersedes
it: **none of this per-control probe was ported**, and `gdl/compose.py`
contains no `frac` computation or 0.152 threshold. Kept because it is the
evidence the rule is real.

GUI Designer renders text **bilevel** — no antialiasing, hard edges,
grid-fitted — when the composited artwork under the control is transparent, and
grayscale-antialiased when it is opaque. Proven over 382 isolated text controls
with zero exceptions: computing `frac = (backdrop alpha > 128).mean()` over the
control rect, every bilevel control has `frac <= 0.152` and every antialiased
one is far above.

So the residual floor is **not** antialiasing physics: only ~55% of it is
genuine GDI+-vs-FreeType rasterization difference.

`research/compose2.py` implements this as an explicit per-control probe with a
threshold of 0.5 — looser than the 0.152 the measurement actually establishes —
bundled with seven other fitted knobs (`aagamma`, `dx`, `wrapk`, bold smear,
`lhk`, `ak`). None of that was ported: the structural rule above achieves the
same decision per pixel, and `lhk`/`ak` are exactly the global line-height
change this document's closing caution warns against.

## 5. Popup placement was already correct

Proven 23/23 against the Permutation snapshots. A popup draws at the anchor's
`Left`/`Top`; its own `Left`/`Top` are 0 on all 24 popups and must be ignored;
child coordinates are popup-local.

## 6. Default state selection was already correct — a negative result

An oracle free to pick whichever state best matches the snapshot picks **state 0
for 350 of 350** pixel-discriminable buttons. `TLPDefaultStateID` is 0 on every
multi-state button in the corpus, and `State.ID` equals the array index in all
2,519 states across the six files. Resolve by ID with an index fallback.

Worth recording because it redirects effort: state choice accounts for none of
the residual, so what remains on text-heavy pages is text metrics and glyph
rasterization.

## 7. Text metrics: Pillow rounds what GDI does not

Implemented, in `gdl/sfnt.py` + `gdl/compose.py`. Three separate roundings, all
Pillow's, each measured on its own:

**Glyph advances.** FreeType grid-fits every advance to a whole pixel, whatever
you pass for `mode` or `layout_engine` — on Open Sans at 22px every glyph comes
back an integer. GDI+ lays out fractionally. `gdl/sfnt.py` reads `hmtx` scaled
by `head.unitsPerEm` directly, with `cmap` for the glyph lookup, in stdlib
only rather than taking on `fontTools`.

Measuring and placing must move **together** — either alone is a regression:

| | measure | place | mean |
|---|---|---|---|
| shipped before | Pillow | Pillow | 2.328% |
| | fractional | Pillow | 2.360% |
| | Pillow | fractional | 2.343% |
| **both** | fractional | fractional | **2.279%** |

**Vertical metrics.** `getmetrics()` returns FreeType's *rounded* ascent and
descent. Open Sans at 22px: ascent 24 against a true `usWinAscent` of 23.51, and
a line box of 31 against 29.96. That is a whole pixel per line, which a
vertically centerd block splits in half and a two-line block pays in full — and
it is why a naive fit wants a ~1.5px downward correction. Reading OS/2
`usWinAscent`/`usWinDescent` fractionally and anchoring on the baseline (`ls`,
not `la`) fixes the cause rather than the symptom.

**Horizontal registration.** `DX = -0.5`, the usual pixel-corner vs
pixel-center convention difference. The value comes from the convention, not
from a fit; the corpus then confirms it as a clean minimum. `research/compose2.py`
also uses -0.5, but on this same corpus and with its own metric preferring
roughly -0.75 — so read that as agreement about the convention, not as
independent evidence.

Together: mean **2.33% → 2.19%**, median 1.85% → 1.65%, worst 8.15% → 7.68%.
24 pages improved, 3 regressed (Presentation Matrix +0.21, Teams Confirmation
+0.06, Display Controls +0.03).

**One DPI is not right both ways.** `PT = 1.375` was swept from 93 to 100 DPI
on the theory that a size-proportional error might be the DPI factor, and the
sweep was flat - 99 DPI scored 2.194% and 98 DPI 2.186% - because one factor
was being asked to fit two: GDI+ lays a caption out across at 99 DPI and down
at 96 (below). `PT` is right for the advances, and the glyphs are drawn at it.

### The lines down the box: 96 DPI, and a foot

Implemented, in `gdl/compose.py` (`VERTICAL`, `FOOT`, `layout_metrics`).

Measured on the synthetic fixture (§9), line by line
(`research/synthetic_lines.py`): each of its 556 live caption lines as the
renderer draws it, moved to where its coverage best matches the snapshot's ink
in the control's rect, a fraction of a pixel found by a parabola through the
best three. Drawn with the vertical metrics above, every line sat low - 2.3 px
on average, rms 2.46, worst 6.56, about 0.08 em centred and **in proportion to
the size, not the box** (a fit in the font's size leaves 0.33 px rms, one in
the box's height 0.62). That is the size-dependent residual this finding left.
Split by alignment, it is two things:

- **Top-aligned**, the snapshot's first baseline sits 0.03 em higher than
  drawn here, and each line after it 0.03 of a line pitch higher again - a
  six-line block's last line 6.6 px. Both are the face's `usWinAscent` and
  line pitch at **4/3 px a point, 96 DPI**, where the advances lie at 99
  (`VERTICAL`, 96/99 of the em drawn). So are the cap heights
  `docs/gdl-format.md` §2 measured, 13 to 34 px at 14 to 36 pt: 0.714 em at
  4/3 px a point, rounded. Set at 4/3, every top-aligned line, one line to
  six, lands within 0.8 px.
- **Centred and bottom-aligned**, set at 4/3, a block still sits high, by one
  amount for both: as though its box were **0.15 em (of the em at 4/3) shorter
  at its foot** - 0.148 over the 454 centred Open Sans lines, one line to four
  alike, 0.147 over the bottom-aligned ones, 0.15 to 0.16 in Arial, Arial Black
  and Open Sans Light. `FOOT` is 0.2 px a point, which is 0.15 of it. **It is
  measured, not explained**: it is not the face's descent, line gap or internal
  leading, which differ between those faces where it does not, and it is not
  GDI+'s padding of 1/6 em, which scores worse.

Scored over the 29 pages: the 4/3 metrics alone take the mean 2.59% → 2.28%
and make the Offline Page 0.02 worse; with the foot, mean **2.59% → 1.55%**,
median 2.29% → 1.30%, worst 6.19% → 3.93%, every page better. `VERTICAL` is a
clean minimum: 1.550% at 0.965, 1.547% at 96/99, 1.570% at 0.975 and 1.654% at
1. The foot's is flat - 1.555% at 0.135 em, 1.544% at 0.14, 1.548% at 0.15 -
and worse either side, 1.590% at 0.155 and 1.661% at 1/6; `FOOT` is the 0.15
measured line by line, not the score's 0.14. Line by line, the residual falls
from rms 2.46 px to 0.42, worst 6.56 to 1.13; what is left of it is a pixel's
rounding, Extron-Afterburn's icons, 0.7 px low, and a slope with the size: a
one-line centred Open Sans caption is off by -0.55 px at 14 pt, Extron's
minimum, +0.21 at 16 and +0.84 at 32 (about 0.023 px a point less 0.43, in
`research/synthetic_lines.py`'s sign).

Ruled out on the way: which table GDI+ reads its ascent and descent from -
`hhea` and the OS/2 `usWin` values are the same in all five faces (Arial's
`hhea` line gap of 67 units aside), so it cannot matter here; the OS/2 typo
metrics, which would set a top-aligned Open Sans line 0.3 em higher than it
is; and a rounding - each baseline snapped to a whole pixel scores the same to
the last digit, as Pillow already rounds a line's y, and floored scores worse
(1.69%).

**The glyphs are drawn at 4/3 too** (`compose.drawn`), both ways, and set
along the line at `PT`'s advances: GDI+ draws a caption's glyphs at the em it
sets the lines down the box at, and FreeType grid-fits them at that size as
GDI+ does. Turbulence 720's 20 pt Open Sans Light question goes 6 rows below
its baseline in GUI Designer's snapshot and has an x-height of 14 rows, where
drawn at `PT` it went 7 and 15 - on its second line, a 'y' on the box's last
row and ink on the two rows under it. Drawn so, the synthetic fixture scores
mean **1.55% → 1.27%**, median 1.30% → 1.08%, worst 3.93% → 3.27%, every
page better; every face's captions differ less (§9's table), Extron-Afterburn's
icons most, 3.07% → 1.63%; and line by line the residual falls from rms
0.42 px to 0.37, worst 1.13 to 1.02, its mean from +0.05 to -0.23 - the
snapshot's lines a quarter of a pixel higher than drawn, as Pillow sets a
glyph on a whole-pixel baseline (40.5 on 40, 40.51 on 41). `FOOT` and `DX`
are still the score's minima: `FOOT` at 0.18 or 0.22 makes 14 and 21 pages
worse, `DX` at -0.75 or -0.25, 20 and 25. Each line drawn at `PT` and
squashed to 4/3 by resampling scores worse than drawn at `PT` (1.61% against
1.55%): it blurs the rows grid-fitting makes whole.

### A caption's ink, and where GUI Designer cuts it

Implemented, in `gdl/compose.py` (`line_ink`, `INK_SEEN`, `CLIP_PX`,
`caption_fit`'s `clips`).

**GUI Designer cuts a live caption's ink off flat at its box**, row by row,
with no tolerance, and still draws the lines it shows. Measured on its own
snapshots of `seeds/Turbulence 720.gdl` (1.28.0.7, 2026-11-05;
`archive/job-e823df9b/clips-gd/`): the
Confirmation and Incoming Call questions, two lines of 20 pt Open Sans Light
centred in 316x64 at 242,144, end on the box's last row, row 207 - the first
line's stems on row 166 exactly, the second's 43% into row 202, so its 'y'
and 'p' run 43% of a row past the box, which nobody sees cut. In a copy with
those boxes shrunk about their middles, the lines where they were, it cut
2 rows off the first question's foot in 316x60, and 3 off the second's foot
and 2 off its top in 316x58 - the tops of its 'l's and 'd', one row 76%
inked and one whole. `tests/test_compose.py`
`TestTheInkGUIDesignerCuts` holds every row and column of it.

`line_ink` reads a line's ink off the line drawn alone, as `draw_text` draws
it - on the whole-pixel baseline Pillow sets it on, emboldened and obliqued
as the face needs - counting a pixel at least half covered (`INK_SEEN`), not
off Pillow's `getbbox`, which reaches to the baseline and the pen whatever
the ink does: an Extron-Afterburn icon whose ink ends 9 px above its
baseline has a box down to it. Against each line's ink in the snapshots
(`research/synthetic_ink.py`, the 537 of the synthetic fixture's lines whose
ink is clear of its box), `line_ink`'s foot lies +0.15 px from the
snapshot's (rms 0.36), its top -0.34 (rms 0.52) and its height -0.18 (rms
0.43), where Pillow's box of the glyphs at `PT` reached 0.70 px too tall
(rms 1.00). `caption_fit` says `clips` where `CLIP_PX`, a whole row or
column, of a line's ink is past the box, and says how many - the shrunk
copies' 2, and 2 and 3. It agrees with every snapshot there is
(`research/caption_clips.py`): on all 32 of Turbulence 720's pages and all
29 of the synthetic fixture's, every line whose ink comes within 2.5 px of
its box ends on the snapshot's row - its one clip, Turbulence 720's 12 pt
'Window' in 92x15 on Main Multi-Window, has its 'd' cut level with its 'W'
in the snapshot, a row short - and both shrunk boxes lose the rows the
snapshot does. Over the 41 seeds this checkout carries, two of Extron's own
captions lose a row so: that 'Window', and Mach 720's 12 pt 'Lighting
Preset' in 80x36 on Start, whose snapshot cuts it too (below).

**That second refusal is confirmed.** Mach 720's 'Lighting Preset Label' is
refused as `clips`: `line_ink` reads the first line's ink as (left 18, top 91,
right 76, foot 108) against a box whose top is row 92, and the one glyph of
'Lighting' that reaches row 91 is the 'h', whose ascender stands a row above
the capital (per glyph, `line_ink` reads the L's top as row 92 and the h's as
91). GUI Designer's snapshot of a copy of `seeds/Mach 720.gdl` (1.28.0.7,
2026-11-05; `archive/job-e823df9b/rebuild2-1105/mach720-lighting-preset/`) draws
nothing on row 91 over the label, and the L, the h and the dots of the two i's
all begin on row 92, in full. In 'Lights' on Lighting Settings, the same face
and size in a box clear of its edge, the h begins a row above the L. So the h's
row is cut flat at the label's top edge, as Turbulence 720's 'Window' is, and
the L, whose top is row 92, is drawn.

The ascent and line-height multipliers once fitted here, `A = 0.90` and
`L = 0.97`, were this: `L` is 96/99, and `A` absorbed the foot, on a project
that centred all but 3 of its 490 captions, where a short ascent and a foot
place a centred line alike (within 0.005 em). Top-aligned captions tell them
apart, and the client's had three at most.

### Scope limit on all of the above

The client project findings 1-8 were scored on only ever drew **one** family:
instrumenting `face()` across a full harness run showed 576 calls, all Forma
DJR Display. Every text finding here was therefore validated against a single
typeface; the corpus's Arial,
Open Sans and Afterburn text is flattened into artwork on these pages. Treat the
constants as measured for Forma and plausible elsewhere. The synthetic fixture
(§9) draws five faces live, and measures them.

The way out of that is now on disk. Extron ships 50 `.glt` templates with GUI
Designer (`C:\Users\Public\Documents\Extron\GUI Designer Templates\TouchLink
Templates`), they are the same `KP`-swapped container, `Project.open()` reads
all 50 unchanged, and between them they define **15 distinct font families** -
Arial, Arial Black, Open Sans, Open Sans Light, Roboto, Segoe UI, Segoe UI
Semibold, FluentSystemIcons-Regular, and seven Extron families (Afterburn,
Shockwave, Lift and Extron-Lift, GUI Configurator, and two GUIC Video
Conference faces) - where `gdl/fonts/` holds the synthetic fixture's (its
README lists them). A weight Windows names as part of the family is a family here
(`font_resource_names()`); Roboto's Light and Thin share the one resource,
`Roboto`. What they do
*not* ship is ground truth: a template carries no built payload, so there are no
snapshots to score against and one would have to be built first.

## 8. Bold is the regular, emboldened

Implemented, in `gdl/compose.py` (`face()`'s `emboldened`, `embolden`,
`BOLD_SMEAR`, `BOLD_ADVANCE_EM`).

GUI Designer has no bold file for the faces a panel draws bold. The client
project embedded Forma DJR Display Regular only; every seed carries Open Sans as Regular
(and Light), none an Open Sans Bold. It emboldens the regular, as GDI+ does for
a family with no bold face - so adding an Open Sans Bold file would draw a
design the panel does not show. `gdl.compose` emboldens a bold asked of a file
that is not one the same way, and `tests/verify_built.py` draws the ink it
looks for in a baked caption with the same code (`compose.draw_glyphs`,
`compose.embolden`), so the synthetic fixture's bold Flat2 is found in the art
Build baked it into. A bold Arial is emboldened too - no build here embeds an
Arial Bold, and no ground truth draws one, so that is unmeasured.

The model is fitted on the client project's 44 bold Forma captions - no seed
flattens a bold caption into its art, and no seed has snapshots - and scored
on the synthetic fixture's 50 bold Open Sans ones. Measured against the
first:

- **Stems** are a whole pixel heavier, on the right: GDI's own simulated-bold
  overstrike. Smearing the glyph's coverage 1 px rightward fits best; a
  symmetric smear, a vertical one, one in em (2-5% of it) and anything past
  1 px (1.1 already) all score worse.
- **Advances** grow about 1/60 em a glyph - 0.016 to 0.0175 em score alike,
  0.015 and 0.02 worse. In em, as GDI+'s fractional layout has it, not GDI's
  whole pixel: every constant growth tried (0.3 to 1 px) scores worse, and
  across 35 measured lines the growth fits within 1.8 px rms where any
  whole-pixel rounding of the advances is 2.7 px or worse.

On the synthetic fixture's 50 bold Open Sans captions (§9) - on one line and
on two, near their box's edge and far from it - laid out in the box less
GDI+'s padding as every caption is, it makes no page worse: mean 2.71% →
2.59%, median 2.48% → 2.29%, worst 6.72% → 6.19%, 24 pages better (21 by more
than 0.01%) and 5 unchanged, and the bold captions' rects from 4.89% to 3.97%
differing. Note Clear moves most, 6.71% → 5.50%, then Type Sizes 6.72% →
6.19% and Start 2.67% → 2.29%.

On the client's 27 pages, scored before the padding was modelled, it took the
mean 2.19% → 2.13%, median 1.65% → 1.54%, worst 7.68% → 7.64%: 17 pages
better, 8 unmoved, and 2 worse - 2210 Conference Volume +0.12% and 2220 CATV
Volume +0.02%. Aligned at each caption's best shift, so §7's size-dependent
vertical residual does not count, the bold captions' own error fell from 51,656
differing pixels to 31,478. What it missed there was the advance on three
captions, which the snapshots showed emboldened and laid out at the regular's
widths: every line of the two-line `Conference` / `Volume` and `Cable TV` /
`Volume` on those two popups, and `Conference Volume` on 120 Audio Controls,
which grown would fill its 167 px box to within GDI+'s padding of 1/6 em a
side. Nothing measured explained the two-line ones - both fit their box by
these metrics - and that project cannot be scored again (§9), so whether the
padding accounts for them is not known.

## 9. The synthetic fixture: ground truth beyond one typeface

`tests/data/synthetic/` is a project of the toolkit's own, in generic words -
10 pages and 18 popups of the client project's sizes, every control type the
renderer draws but a Level - built on `seeds/Afterburn 1035.gdl` by
`powershell/New-GdlPanel.ps1` (verified, 2,836 checks on 531 controls), and
GUI Designer's own *Take All Pages Snapshot (Individual)* of it, exported by
`powershell/Export-GdlSnapshots.ps1`: 29 PNGs, the Offline Page among them.
Its README says what each page holds. Where the client's drew one face, it
draws Open Sans regular, bold and italic from 14 to 40 pt, Open Sans Light,
Arial, Arial Black and the Afterburn icon face, in every alignment.

At its first recording it scored **mean 3.44%, median 2.68%, worst 8.03%**
over 29 pages (Type Sizes), where the client's was 2.19%, 1.65% and 7.68% over
27; what each change since has moved it by is under *Where it stands*, and
the baseline it is scored against now is in `CLAUDE.md` *Verifying a change*.
Each face is the build's own (`python -m gdl.fonts` over it); recovered from
the client's project instead, every page scored the same to the last digit.

Where the pixels differ, inside each control's rect, as the renderer draws it
now (`research/synthetic_breakdown.py`; the client's in brackets, from the
renderer its baseline was last scored with):

| What drew it | Controls | Differing |
|---|---|---|
| Open Sans italic | 8 | 6.00% |
| Arial Black | 9 | 4.69% |
| Open Sans Light | 9 | 4.21% |
| Arial | 22 | 3.19% |
| Open Sans regular | 374 | 2.69% (Forma regular 7.09%) |
| Open Sans bold | 50 | 1.75% (Forma bold 10.50%) |
| Extron-Afterburn | 18 | 1.63% |
| Shape, popup reference, button without words | 59 | 1.5-3.7% (2.2-6.5%) |
| Image | 3 | 0.63% (1.10%) - the stretched stripes under the translucent keys 1.15% |
| Button, caption flattened by Build | 4 | 1.10% (3.38%) |
| Line | 6 | 0.00% (1.72%) |
| Slider | 11 | 0.00% (1.51%) |

What it shows that the client's could not:

- **A caption is laid out in its box less 1/6 em a side**, GDI+'s default
  `StringFormat` padding: a left- or right-aligned line starts that far in -
  3 px at 14 pt, 9 px at 40 pt on Type Sizes - and every line wraps in the box
  less both sides. The client's project centres all but 3 of its 490
  captions, so its baseline never saw it. Shipped (`gdl.compose.PAD_EM`): the
  synthetic mean 3.44% → 3.00%, median 2.68% → 2.57%, worst 8.03% → 7.05%,
  22 pages better and none worse. Modelled in memory before it shipped, it
  took the client's 2.19% → 2.10%, worst 7.68% → 7.06%, 14 better and none
  worse; moving only the line, not its wrap, did the same on the synthetic
  fixture and left the client's mean where it was.
- **A translucent fill is blended in light**, and so is every antialiased
  edge over opaque art (finding 2): the Buttons page's six translucent keys
  show the stripes under them, and Controls' white at 20% reads (126,126,130)
  over #242634, lighter than a plain blend. Shipped: the six keys from 5-88%
  of their rects differing to 3.5-5.6%, the white panel from 90.88% to 0.00%.
- **A caption too deep for its box is trimmed, not overflowed.** GDI+ shows
  the lines that fit, and the last one shown holds the rest of its paragraph,
  cut to the characters that fit - its default `StringTrimming.Character`,
  no ellipsis. 'Type 40 Italic' on Type Sizes, too wide for its box less the
  padding and 1.17 lines deep, shows as 'Type 40 Itali' on one line, where
  wrapped it would be two lines the box cuts through. How much of a line must
  fit for it to show is measured only as between 17% (that caption's second
  line, not shown) and 68% (Content Epsilon's 'speaker mute 2', shown); half
  is assumed (`gdl.compose.fitted`, `TRIM_LINE`). Type Sizes 7.00% → 6.81%,
  the only page with a caption it changes.
- **Italic is the regular, obliqued.** No seed carries an Open Sans Italic,
  and none is installed on the host that exported it: GUI Designer slants the
  regular 0.34 a pixel of height about its baseline, its advances the
  regular's (`gdl.compose.OBLIQUE`) - measured off the stem of each italic
  caption's I, 0.341 at 28, 32 and 40 pt, where hinting does not move it.
  Aligned for §7's vertical residual, the eight italic captions differed by
  7.71% of their rects, against 12.22% drawn upright and 6.70% for the
  regular ones beside them; Type Sizes 6.81% → 6.72%. With the lines set
  down the box as GDI+ sets them (finding 7), they differ by 7.33% at 0.34,
  and the slant that scores best is 0.30, at 6.46% - where it was 0.22 while
  the lines sat 2-3 px low. That is no longer the vertical residual but a
  horizontal one: every caption of 28 to 40 pt on Type Sizes sits 0.6-1.2 px
  right of the snapshot's, regular and bold too, and a shallower slant moves
  an italic's ink left. At 0.34 each italic caption is that far right, as the
  regular and bold on its row are; at 0.30 it is 0.2-0.4 px, apart from
  them. 0.34 stays.
- **Bold is the regular, emboldened** (finding 8), and once a caption is laid
  out in its box less the padding, the model fitted on the client's Forma
  makes none of these pages worse. Shipped: mean 2.71% → 2.59%, median
  2.48% → 2.29%, worst 6.72% → 6.19%, 24 pages better and 5 unchanged, the
  bold captions' rects from 4.89% to 3.97%. Scored without the padding, it
  made 15 pages worse, nearly every one by a bold left-aligned title the
  missing padding misplaced.
- **A caption's lines are set down its box at 96 DPI, and a centred or
  bottom-aligned block aligned in its box less 0.2 px a point at its foot**
  (finding 7). On the
  client's captions, centred all but three, the two were one number; this
  fixture's top-aligned ones tell them apart. Shipped: mean 2.59% → 1.55%,
  median 2.29% → 1.30%, worst 6.19% → 3.93%, every page better.

What it cannot show: a Level, which its seed has none of (neither baseline
scored the renderer's Level path), and Forma, the client's retail face, which
only the client's baseline drew. That baseline is no longer scored - its
project is gone from the repo - so findings 7 and 8's measurements in Forma
stand as recorded and cannot be run again (`docs/ROADMAP.md`).

## Where it stands

| | mean | median | worst |
|---|---|---|---|
| baseline | 4.57% | 2.28% | 40.22% |
| binary alpha + group popups | 4.04% | 2.07% | 40.22% |
| + borderFillColor fill | 2.60% | 2.02% | 8.99% |
| + transparent canvas / bilevel text | 2.33% | 1.85% | 8.15% |
| + fractional text metrics | 2.19% | 1.65% | 7.68% |
| the synthetic fixture, same renderer (§9) | 3.44% | 2.68% | 8.03% |
| + GDI+'s padding (§9) | 3.00% | 2.57% | 7.05% |
| + blending in light (finding 2) | 2.72% | 2.48% | 7.00% |
| + trimming and the oblique (§9) | 2.71% | 2.48% | 6.72% |
| + the emboldened bold (finding 8) | 2.59% | 2.29% | 6.19% |
| + the lines down the box at 96 DPI, and the foot (finding 7) | 1.55% | 1.30% | 3.93% |
| **+ the glyphs drawn at 96 DPI (finding 7, current)** | **1.27%** | **1.08%** | **3.27%** |

The first five rows are the client's 27 pages, a record now that the project
is gone; the rest are the synthetic fixture's 29, from its first recording to
the baseline a render change is scored against.

Implemented in `gdl/compose.py`: findings 1 (fill only), 2, 3, 4, 7 (its
vertical metrics and glyphs at 96 DPI, its foot and the ink GUI Designer
cuts at a caption's box among it) and 8, and §9's padding, trimming and
oblique.

With the Offline page no longer an outlier, the client's mean was a fair
summary of its pages rather than one page's error — every page was between
0.54% and 7.68%.

Not implemented, but **written and measured**:

| Candidate | Measured | Where |
|---|---|---|
| per-control RGBA layering | **rejected** — see below | `research/v3.py` |
| modal scrim at 65% opacity | no observable effect in this corpus | `research/final_patch.py` |

### Why `research/v3.py`'s architecture was not adopted

`research/README.md` calls it "the clearest direction for further fidelity
work". It is not — but not for the reason first written here, which was wrong
and is corrected below.

**It is redundant, not harmful.** Rendering each control into its own
transparent RGBA layer and merging with the binary alpha test produces the same
image as painting onto the shared canvas. Measured directly, by wrapping
`render_control` to composite through a per-control layer:

| page | shipped | per-control layer | |
|---|---|---|---|
| 3110 Adv Device Connectivity | 7.679% | 7.679% | byte-identical |
| 3112 Adv Video Connectivity | 6.720% | 6.720% | byte-identical |
| 1000 Home | 1.427% | 1.401% | −0.03 |
| 3000 Tech | 2.986% | 2.989% | +0.00 |

Byte-identical on both of v3's own tuning pages. So it buys nothing over what is
already shipped, at the cost of a second compositing path.

**The earlier reasoning here was backwards** and is recorded so it is not
re-derived: it claimed the binary merge destroys antialiasing for the ~2/3 of
controls sitting over an opaque backdrop. It does not. Source-over saturates the
layer's alpha to 255 wherever it is already opaque, so the threshold is a no-op
there and the antialiased blend survives. Binarising only changes pixels over a
*transparent* local destination — which is exactly where finding 4 says bilevel
is correct.

v3's real contribution is its *other*, orthogonal one — fractional advances —
which is what was ported here, into the existing shared canvas, without the
layering.

A caution carried over from the measurements: do **not** "fix" the line-height
rule globally. Keeping `px = PointSize * 1.375` with PIL's `ascent + descent`
is the corpus optimum; substituting the hhea line height improved one page and
regressed 24.
