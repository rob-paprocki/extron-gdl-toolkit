# Turned panels Extron draws no template for

Status: approved under the owner's delegation of the roadmap (2026-10-09);
the remainder of ROADMAP item 1 after #26.

## Goal

The five panels that run turned and have no Extron template that way up -
TLP Pro 520M (480x800), TLC Pro 521M (480x800), TLP Pro 535M (720x1280),
TLP Pro 835M and 1035M (800x1280) - are targets in a design system that
draws their model the other way up: a canvas lists `TLP1035M-Portrait`,
`translate` lays its pages out, and they build on a seed that is that way
up.

## What decides it

- **Regions: the model's own series, transposed.** Extron draws one panel
  both ways - Afterburn's 300M - and its Landscape layout is the exact
  transpose of its Portrait one: main [0,0,320,392] and [0,0,392,320], the
  rail a footer [0,392,320,88] and a column [392,0,88,320], no standard
  popup either way, same DPI, tier and fit. So a turned row is its model's
  series row with main and rail transposed (x and y swapped), the rail
  running the other way, and its popup turned with them - by extension, since
  the 300M has none. Ours, not Extron's: a rule taken from the one panel
  Extron draws both ways.
- **No art.** Extron draws no art for these that way up. Its 300M's
  landscape art is the portrait's shape transposed (the alpha channels agree
  at all but 0.2% of pixels) with its paint redrawn: the portrait art rotated is further from
  the landscape art (mean |diff| 39 per channel) than a flat fill of its mean
  colour (19-27). Rotating art would draw a lie; a turned row has no
  `backgrounds`, and its page is the scheme's page colour.
- **Kinds and borders: the source seed's.** A retarget changes geometry,
  never what a seed can clone or which borders it defines.
- **Derived in code, not written in the profile.** A profile's `panels` are
  measured (`tests/measure_series.py`); these rows follow from a rule, so the
  rule lives once, in `gdl.designsys.models()`: for each model of a series
  that runs either way up (`gdl.spec.sizes`), a row at its other canvas
  unless another series of the profile serves it there (Afterburn's 300M).

## Seeds

A turned seed is the model's default-way-up seed turned by `gdl.edit
retarget` (`{"op": "retarget", "model": M, "size": [w, h], "scale": true}`)
and built - the route `docs/editing.md` already proves (650/650 on the
1035 seed turned). The wizard cannot make one: it offers these panels Blank
alone that way up.

- `powershell/New-GdlTurnedSeed.ps1 -From <seed> -Model <M> -Resolution WxH
  -Output <file>`: plan the retarget, apply it (32-bit), open, Save and
  Build, wait, verify.
- `tests/verify_seed.py` knows a turned seed: its pages are its series
  template's, each rect scaled per axis as the retarget scales it.
- `gdl.seeds`: a turned panel's seed keeps the name `default_path` already
  gives it - `seeds/Afterburn 1035 Portrait.gdl`. With none, `command()`
  gives the turn line where `gdl.templates` has no template that way up
  (the wizard line with `-Resolution` stays for Afterburn's 300M; Mach's,
  drawn portrait alone, is turned), and the refusal
  gives the landscape seed's own line first where that seed is missing too
  (the 520M, 521M and 535M have none yet).
- `tests/measure_series.py` records a turned seed under its panel id in its
  series' `seeds`, by part and canvas as it records the rest.

## Proof

One panel end to end: the 1035 seed turned to `seeds/Afterburn 1035
Portrait.gdl`, built and verified; a canvas translated for
`TLP1035M-Portrait` and built through `New-GdlPanel.ps1`, verified. The
other four rows ship with their seed's line, made when a job needs one.

## Out of scope

Art for turned panels. Mach, Shockwave and Turbulence derive the same turned
rows from their own per-series tables, with no turned seed of theirs made yet.
