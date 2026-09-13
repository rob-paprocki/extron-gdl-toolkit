# Fonts

The renderer resolves faces from this directory before falling back to the
system font path, so a `.gdl` renders the same on a machine with nothing
installed. Recover the untracked faces with:

```bash
for f in fixtures/gdl/*.gdl; do python -m gdl.fonts "$f" gdl/fonts/; done
```

All six fixtures are needed — no single one embeds every face.

## What is tracked, and why it varies

The nine files do **not** share a license, so they are not treated as one
class. Each row below is read from the font's own `name` table, not assumed:

| file | declares | tracked |
|---|---|---|
| `arial.ttf` | © 2011 The Monotype Corporation, Arial 5.10 | no |
| `ariblk.ttf` | © 2008 The Monotype Corporation, Arial Black 5.06 | no |
| `opensans-regular.ttf` | Apache License 2.0 (nameID 13), Google / Ascender | **yes** |
| `opensans-light.ttf` | Apache License 2.0 (nameID 13), Google / Ascender | **yes** |
| `formadjrdisplay-regular_1.otf` | David Jonathan Ross, all rights reserved, djr.com/license | no |
| `afterburn_modified.ttf` | Copyright (c) 2021, Extron — no license field | no |
| `extron_-_afterburn_1a.ttf` | same bytes as above, different embedded name | no |
| `extron_guic_video_conference_1.ttf` | Extron — no license field | no |
| `crestron_general.ttf` | "Typeface © (your company). 2011" — an unedited template | no |

Open Sans is tracked because Apache 2.0 permits redistribution and the font
says so itself; `LICENSE-OpenSans.txt` is the license text that condition
requires. Arial, Arial Black and Forma DJR Display are retail typefaces. The
four vendor icon fonts carry no grant of any kind, which is more restrictive
than "commercial", not less.

## What the ignore does and does not do

It does **not** keep the font binaries out of git. Every one of these faces is
embedded in the `.gdl` fixtures, which are tracked, and `python -m gdl.fonts`
reproduces each one byte-for-byte from them with no other input. What the
ignore prevents is a second, more conveniently redistributable copy.

If the concern is distribution rather than convenience, the thing to look at is
`fixtures/` — see *Working on the fixtures* in `CLAUDE.md`.

## Arial is embedded too

Genuine Monotype Arial 5.10 and Arial Black 5.06 are embedded in every fixture
and in all 44 of Extron's installed templates, and `python -m gdl.fonts`
recovers them with everything else — so never substitute a system copy. They
are easy to miss: both carry bytes past the far edge of their last sfnt table
(28 for Arial, 30 for Arial Black), so an extractor that matches `layout.json`'s
declared size against the measured table length *exactly* finds neither.
`tests/test_fonts.py` pins this.

## …but not every project embeds every face it declares

A fresh project from File > New *declares* Arial Black without embedding it: 11
of the 14 seeds carry no sfnt table of anything like its declared 119,904
bytes. The Turbulence seed declares Arial the same way, and the Shockwave seeds
`extron_shockwave.ttf`. GUI Designer supplies these itself at build time; the
renderer has no such source, so rendering a seed-built panel can raise
`LookupError`. `docs/ROADMAP.md` tracks the fix.

Prefer the embedded copy over an installed one even on a host that has Arial.
The embedded face is the one GUI Designer rasterized the ground-truth snapshots
with; the system copy is whatever build the OS happens to ship. Windows 11's
`arial.ttf` is 1,016,724 bytes against the fixture's 778,580.

## Missing faces fail loudly, not quietly

`face()` raises `LookupError` on the first face it cannot resolve. It does not
degrade to a wrong score. The exception is a host that has Arial installed
(Windows, macOS), where a missing embedded face does silently resolve to the
system Arial — there, and only there, the harness will report a confident
meaningless number.
