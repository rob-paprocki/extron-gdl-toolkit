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
rather than inventing geometry. Seven are available in this project.

Practical fix for a viewer: honour `EnableOfflinePage`, which is `false` in all
six files. The offline page is a system overlay, not a navigable popup.

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

GUI Designer renders text **bilevel** — no antialiasing, hard edges,
grid-fitted — when the composited artwork under the control is transparent, and
grayscale-antialiased when it is opaque. Proven over 382 isolated text controls
with zero exceptions: computing `frac = (backdrop alpha > 128).mean()` over the
control rect, every bilevel control has `frac <= 0.152` and every antialiased
one is far above.

So the residual floor is **not** antialiasing physics: only ~55% of it is
genuine GDI+-vs-FreeType rasterisation difference.

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
rasterisation.

## Where it stands

| | mean | median | worst |
|---|---|---|---|
| baseline | 4.57% | 2.28% | 40.22% |
| binary alpha + group popups (implemented) | 4.04% | 2.07% | 40.22% |
| navigable pages only (offline excluded) | **2.65%** | **2.07%** | 8.99% |

Implemented in `gdl/compose.py`: findings 2 and 3.

Not implemented, but **written and measured** — the code is in `research/`,
with `research/README.md` giving the numbers and the fitted constants:

| Candidate | Measured | Where |
|---|---|---|
| `borderFillColor` fill + modal scrim (finding 1) | Offline 40.22% → 1.28% | `research/final_patch.py` |
| bilevel/antialiased text decision (finding 4) | mean 4.57% → 3.50%, median 2.28% → 1.23% | `research/compose2.py`, `q_final.py` |
| fractional glyph advances + per-control layering | worst two pages 9.39% → 3.67%, 8.02% → 3.38% | `research/v3.py`, `frac.py` |

The third is the strongest result the project reached and is the clearest
direction for further work; nothing in `gdl/` implements it. The constants
behind all three cost hours of sweeps, so re-derive nothing before reading
`research/README.md`.

Finding 1 is sidestepped in the shipped code by honouring `EnableOfflinePage`.

A caution carried over from the measurements: do **not** "fix" the line-height
rule globally. Keeping `px = PointSize * 1.375` with PIL's `ascent + descent`
is the corpus optimum; substituting the hhea line height improved one page and
regressed 24.
