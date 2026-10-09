# Fonts

The renderer resolves faces from this directory before falling back to the
system font path, so a `.gdl` renders the same on a machine with nothing
installed. Recover the untracked faces with:

```bash
for f in fixtures/gdl/*.gdl; do python -m gdl.fonts "$f" gdl/fonts/; done
```

All six fixtures are needed — no single one embeds every face. The public copy
holds the fixtures back; there, recover the faces from a seed, which carries
the same Monotype Arial (the render baseline itself is scored only where the
fixtures are):

```bash
python -m gdl.fonts "seeds/Afterburn 1035.gdl" gdl/fonts/
```

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
reproduces each one from them with no other input (byte for byte, but for the
28-byte tail on Arial and Arial Black below). What the ignore prevents is a
second, more conveniently redistributable copy.

If the concern is distribution rather than convenience, the thing to look at is
`fixtures/` — see *Working on the fixtures* in `CLAUDE.md`.

## Arial is embedded too

Genuine Monotype Arial 5.10 and Arial Black 5.06 are embedded in every fixture
and in all 50 of Extron's installed templates, and `python -m gdl.fonts`
recovers them with everything else — so never substitute a system copy. They
are easy to miss: the declared size runs past the far edge of their last sfnt
table (28 bytes for Arial, 30 for Arial Black), so an extractor that matches
`layout.json`'s declared size against the measured table length *exactly* finds
neither. Those bytes are not in the project: the embedded array ends at the last
table (Arial) or two bytes after it (Arial Black), and `extract()` keeps the
declared length, so each recovered file ends in 28 bytes of the project's next
records. Every other face is cut exactly. `tests/test_fonts.py` pins this.

## …but not every project embeds every face it declares

`layout.json` declares a face by file name and size, and a project carries its
own list of font resources, so the two can disagree. Run over `seeds/`:

- **Arial Black** (`ariblk.ttf`, 119,904 bytes) is embedded only in the seeds
  that define a resource for it - `seeds/README.md` has which. The rest declare
  it and define no resource for it, so there is nothing to recover. GUI
  Designer adds the resource when it builds:
  `archive/job-9fe2c865/tmp/rt/seed.gdl` has none and `retargeted.gdl`, its
  build, has one.
- **Arial** (`arial.ttf`) is Monotype Arial 5.10, 778,580 bytes, in the Afterburn
  seeds for the 1035, 1230W, 1535, 725, 835 and both ECP presets and in both Zoom
  Rooms seeds. Every other seed embeds the Windows Arial of the machine that made
  it, 7.05 (1,016,724 bytes) or 7.06 (1,045,720), and all of them but Turbulence
  still declare the Monotype file as well, so they declare `arial.ttf` twice and
  the first matches nothing. `extract()` keys results by file name, so the
  declaration that matches hides the one that does not. Turbulence declares only
  the Monotype file and carries a Windows Arial 7.05 under an Arial resource with
  no embedded file name, so `extract()` returns no `arial.ttf` for it.
- **Extron-Shockwave** (`extron_shockwave.ttf`, 3,736 bytes, the smallest face
  in the corpus) is embedded in every Shockwave seed and recovered like any
  other.

Recovering from a seed that embeds a Windows Arial replaces the Monotype
`arial.ttf` here; the fixtures all embed the Monotype one. The renderer needs
nothing from a seed: it reads Arial and Arial Black from this directory, which the
fixtures supply. `docs/ROADMAP.md` tracks recovering what a project carries.

Prefer the embedded copy over an installed one even on a host that has Arial.
The embedded face is the one GUI Designer rasterized the ground-truth snapshots
with; the system copy is whatever build the OS happens to ship. Windows' own
`arial.ttf` is 1,016,724 or 1,045,720 bytes against the fixtures' 778,580.

## A missing face is said aloud

`face()` takes a face from the files recovered here first, then from the host's
fonts, and raises `LookupError` only when neither has it. A face missing here
draws in a stand-in: the recovered Arial, after a partial recovery, or the
host's copy - and on a host with Arial installed (Windows, macOS) the host's
Arial stands in for every face, so a checkout that skipped recovery renders on
it and scores worse - the render baseline reads 2.81% instead of 2.19%.
`gdl.compose.FALLBACKS` records every face drawn in anything but its own
recovered file, and `tests/score.py record` refuses to write a score over one,
naming the recovery loop above.
