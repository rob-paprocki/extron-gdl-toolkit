# Render fidelity: what GUI Designer actually draws

Findings from scoring our compositor against GUI Designer's own snapshot
exports (50 renders of the `_alt 2_0_0` project). Every claim below was
measured, and each was put through an adversarial verification pass.

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
`Control.ID`; verified equal across all six fixtures (157 pages, 3,744
controls). `gdl/project.py`'s `pages()` walks the authoring model's page tree to
supply it. Measured: Offline Page 40.22% → 1.28%, all 26 other pages ±0.00%.

The first version keyed on `(type, rect)` instead, because the authoring model
was only read as a flat object graph. It scored identically — but only because
the eligible subset (no artwork *and* a real fill) is a single control per file.
`(type, rect)` is **not** unique over controls generally: each fixture has
127–132 colliding groups, and nothing checked the destination side, so two
same-typed, same-positioned controls on different pages would both have been
filled. Recorded because "it scored the same" is exactly how a key like that
survives review.

One trap in the page walk: a serialized `List<T>`'s `_items` is over-allocated —
32 slots holding 4 pages — so it must be sliced to `_size`, or the tail of
`None`s reads as real empty objects.

The index holds exactly **one** entry in each of the six fixtures — the same
`PBShape "Offline Window"` — so this rule is narrow in this corpus even though
it is worth 1.44 points of the corpus mean.

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

## 2. Compositing uses a binary alpha test

GUI Designer renders each control into its own bitmap and composites it with a
**binary** alpha test: any pixel with alpha > 0 is written at full strength;
alpha == 0 is skipped. It does not do straight alpha blending.

Measured over 3,296 partial-alpha pixels: straight alpha is off by a mean of
**97 levels** per channel; binary alpha by **2.15**. This affects every page
with an antialiased asset edge, which is all of them.

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
the end of the outermost `render_page`, with the same binary alpha rule
`paste()` uses. That alone produces finding 4's behavior, per pixel rather
than per control:

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

**A negative result worth keeping:** `PT = 1.375` was re-swept from 93 to 100
DPI on the theory that a size-proportional error might be the DPI factor. It is
not — 99 DPI scores 2.194% and the best neighbour (98 DPI) 2.186%, inside the
noise. The existing constant is right.

### What is left, and why it is not shipped

A size-dependent vertical residual remains. Per-control best-shift analyzis over
67 text controls shows it **scales with point size** (13pt wants ~1.0–1.5px,
16–38pt want ≥2.5px), so it is a metrics error rather than a constant offset.
Fitting an ascent multiplier `A` and line-height multiplier `L` on top reaches
**mean 1.724%** at `A=0.90, L=0.97`.

That is deliberately **not shipped.** The optimum is flat and degenerate —
`(0.90, 0.97)`, `(0.92, 1.00)` and `(0.90, 1.00)` all land within 0.02 of each
other — which is the signature of fitting noise, and `A`/`L` are precisely
`research/compose2.py`'s `ak`/`lhk`, the global line-height change this
document's closing caution already warns about. The next person should find the
*cause* of the size-dependent residual, not refit these two numbers.

### Scope limit on all of the above

The scored fixture only ever draws **one** family: instrumenting `face()` across
a full harness run shows 576 calls, all Forma DJR Display. Every text finding
here is therefore validated against a single typeface; the corpus's Arial,
Open Sans and Afterburn text is flattened into artwork on these pages. Treat the
constants as measured for Forma and plausible elsewhere.

The way out of that is now on disk. Extron ships 50 `.glt` templates with GUI
Designer (`C:\Users\Public\Documents\Extron\GUI Designer Templates\TouchLink
Templates`), they are the same `KP`-swapped container, `Project.open()` reads
all 50 unchanged, and between them they declare **12 distinct font families**
against the seven in `gdl/fonts/` — Arial, Open Sans, Roboto, Segoe UI,
FluentSystemIcons-Regular, and seven Extron families (Afterburn, Shockwave,
Lift and Extron-Lift, GUI Configurator, and two GUIC Video Conference faces).
Weight variants are separate embedded faces but collapse to these families in
`font_resource_names()`. What they do
*not* ship is ground truth: a template carries no built payload, so there are no
snapshots to score against and one would have to be built first.

## Where it stands

| | mean | median | worst |
|---|---|---|---|
| baseline | 4.57% | 2.28% | 40.22% |
| binary alpha + group popups | 4.04% | 2.07% | 40.22% |
| + borderFillColor fill | 2.60% | 2.02% | 8.99% |
| + transparent canvas / bilevel text | 2.33% | 1.85% | 8.15% |
| **+ fractional text metrics (current)** | **2.19%** | **1.65%** | **7.68%** |

Implemented in `gdl/compose.py`: findings 1 (fill only), 2, 3, 4 and 7.

With the Offline page no longer an outlier, the mean is a fair summary of the
corpus rather than one page's error — every page is now between 0.54% and 7.68%.

Not implemented, but **written and measured**:

| Candidate | Measured | Where |
|---|---|---|
| ascent / line-height multipliers | mean 2.19% → 1.72%, but a degenerate fit | see above; `research/q_final.py` |
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
