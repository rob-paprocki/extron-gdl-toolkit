# research/

> **Status, 2026-09-07 — read this before acting on anything below.**
>
> Most of this file has been **resolved**, and two of its recommendations were
> resolved *against*. It is kept as the record of how the measurements were
> obtained; it is no longer a to-do list.
>
> | Below | Now |
> |---|---|
> | §1 `borderFillColor` fill | **shipped** (`fill_index`/`draw_fill`) |
> | §1 modal scrim, `SCRIM_ALPHA` | **not shipped** — unobservable in this corpus |
> | §2 bilevel/antialiased text | **shipped, but differently** — structurally, per pixel, not via the probe or the fitted 8-knob bundle |
> | §3 `v3.py` "the strongest result reached" | **architecture rejected**; only its fractional advances were ported |
>
> In particular, §3's claim that per-control layering "is the clearest direction
> for further fidelity work" is **wrong**, and following it would undo finding 4.
> Its blit re-binarises the whole merged layer's alpha, which is only correct
> where a control sits over a transparent backdrop — on its own two tuning pages
> only 18/50 and 17/50 controls qualify. See `docs/render-fidelity.md`, which is
> the current record.

Measured but unshipped work. These scripts are **not** part of the toolkit —
they carry hardcoded paths from the session that produced them and will not run
unmodified. They are kept because each one encodes a result that cost real time
to obtain and would otherwise have to be re-derived from scratch.

`gdl/compose.py` remains the maintained compositor. Everything here is a
candidate improvement to it, with the numbers that justify it.

| File | What it establishes |
|---|---|
| `final_patch.py` | the `borderFillColor` fill + modal scrim rule |
| `compose2.py`, `q_final.py` | the bilevel-vs-antialiased text decision, fitted |
| `v3.py`, `v2.py`, `frac.py`, `qlib.py`, `q46.py` | fractional glyph advances + per-control layering — the best result reached |

## 1. `final_patch.py` — the fill the payload cannot describe

Implements `docs/render-fidelity.md` finding 1, plus a second half the doc does
not record: **a page with `TLPImageID == -1` that is modal paints its
`BackgroundFillColor` at 65% opacity**, matching the alpha 166 baked into the
scrim assets.

```
SKIN_SURFACE = (36, 38, 52, 255)     # the Afterburn page/modal surface
SKIN_RADIUS  = 10                    # from "Afterburn - 10 Radius 0 Thick"
SCRIM_ALPHA  = 165                   # modal dim, vs 166 measured in asset 36
```

Measured: **Offline Page 40.22% → 1.28%**, no other page changed. Against the
currently shipped compositor that takes the corpus mean to roughly 2.6%.

The toolkit currently sidesteps this by honouring `EnableOfflinePage`, which is
`false` in all six fixtures. That is correct for a viewer and wrong for anything
that has to render the offline page faithfully.

## 2. `compose2.py` + `q_final.py` — the text raster decision, fitted

Implements finding 4. `compose2.py` is a switchable variant of `gdl/compose.py`;
`q_final.py` is the accounting harness. The fitted configuration:

```python
AFTER = dict(aa='autofill', aagamma=0.7, dx=-0.5, wrapk=1/3,
             bold='smear', boldpx=1, bold_dpx=0.75, lhk=1.19, ak=0.825)
```

Measured over the text-control rects (Offline page excluded):

```
BEFORE  423,319 bad px  (9.16% of rect area)
AFTER   262,479 bad px  (5.68%)   -> 38.0% of the residual removed
ORACLE  233,788 bad px  (5.06%)   -> the per-control best-shift floor
```

So 38% of the text residual is correctable systematics and 55% is genuine
GDI+-vs-FreeType rasterization. Page-level: **mean 4.57% → 3.50%, median 2.28%
→ 1.23%**.

## 3. `v3.py` + `frac.py` — the strongest result reached

A later architecture: each control is rendered into its own RGBA layer and
composited with the binary alpha test, and glyphs are advanced by **exact
fractional widths** (GDI+'s layout) rather than Pillow's integer rounding.

On the two worst text-heavy pages, against the shipped compositor's 9.39% and
8.02%:

```
v3 binary thr=1        p10 4.462   p8 3.957
v3 binary dy-0.25      p10 3.670   p8 3.375     <- best measured
v3 straight alpha      p10 5.537   p8 4.738
FIN = dict(lhmul=1.2, bl=0.83, wadj=-4, binary=True, thr=1, clip=True, bold=True, aa=True)
```

More than halving the residual on the worst pages. Nothing in `gdl/` implements
fractional advances or per-control layering, so this is the clearest direction
for further fidelity work.

## Re-running any of this

The scripts reference the session scratchpad they were written in. Retarget
`SP` / `GDL` / `REF` (in `qlib.py`, `v2.py`, `v3.py`) at `fixtures/gdl/` and
`fixtures/snapshots/Individual/`, and use a Python with Pillow. The snapshot
directory they scored against is byte-identical to `fixtures/snapshots/`, and
their `diff_stats` is the same function as `gdl/compose.py`'s, so the numbers
above are directly comparable to the harness output.
