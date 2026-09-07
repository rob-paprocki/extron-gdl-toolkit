# Fonts

The renderer resolves faces from this directory before falling back to the
system font path, so a `.gdl` renders the same on a machine with nothing
installed. Recover the untracked faces with:

```bash
for f in fixtures/gdl/*.gdl; do python -m gdl.fonts "$f" gdl/fonts/; done
```

All six fixtures are needed — no single one embeds every face.

## What is tracked, and why it varies

The seven faces do **not** share a licence, so they are not treated as one
class. Each row below is read from the font's own `name` table, not assumed:

| file | declares | tracked |
|---|---|---|
| `opensans-regular.ttf` | Apache License 2.0 (nameID 13), Google / Ascender | **yes** |
| `opensans-light.ttf` | Apache License 2.0 (nameID 13), Google / Ascender | **yes** |
| `formadjrdisplay-regular_1.otf` | David Jonathan Ross, all rights reserved, djr.com/license | no |
| `afterburn_modified.ttf` | Copyright (c) 2021, Extron — no licence field | no |
| `extron_-_afterburn_1a.ttf` | same bytes as above, different embedded name | no |
| `extron_guic_video_conference_1.ttf` | Extron — no licence field | no |
| `crestron_general.ttf` | "Typeface © (your company). 2011" — an unedited template | no |

Open Sans is tracked because Apache 2.0 permits redistribution and the font
says so itself; `LICENSE-OpenSans.txt` is the licence text that condition
requires. Forma DJR Display is a retail typeface. The four vendor icon fonts
carry no grant of any kind, which is more restrictive than "commercial", not
less.

## What the ignore does and does not do

It does **not** keep the font binaries out of git. Every one of these faces is
embedded in the `.gdl` fixtures, which are tracked, and `python -m gdl.fonts`
reproduces each one byte-for-byte from them with no other input. What the
ignore prevents is a second, more conveniently redistributable copy.

If the concern is distribution rather than convenience, the thing to look at is
`fixtures/` — see *Working on the fixtures* in `CLAUDE.md`.

## Missing faces fail loudly, not quietly

`face()` raises `LookupError` on the first face it cannot resolve. It does not
degrade to a wrong score. The exception is a host that has Arial installed
(Windows, macOS), where a missing embedded face does silently resolve to Arial —
there, and only there, the harness will report a confident meaningless number.
