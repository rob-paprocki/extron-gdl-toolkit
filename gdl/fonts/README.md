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
records. Every other face is cut exactly, and so is any face written from its
resource (below). `tests/test_fonts.py` pins this.

## …but not every project embeds every face it declares

`layout.json` declares a face by file name and size, and a project carries its
own list of font resources, so the two can disagree. What a project carries is
each resource's own data - `gdl.fonts.carried()` reads it, from a `.glt`
template as readily as a project - and `python -m gdl.fonts` pairs each
declaration with a carried face one by one (`gdl.fonts.match()`), then names
every declaration it carries nothing for (`DECLARED, NOT CARRIED`) and every
face no declaration names (`CARRIED, NOT DECLARED`). A face declared and
carried that the stream scan cannot find is written from its resource, and the
line says so. When every declaration is found and every face the stream carries
is declared - every fixture - there is nothing to say, and the command answers
without parsing the project, which takes a large seed most of a minute. Run
over `seeds/`:

- **Arial Black** (`ariblk.ttf`, 119,904 bytes) is embedded only in the seeds
  that define a resource for it - `seeds/README.md` has which. The rest declare
  it and define no resource for it, so there is nothing to recover. A build
  can add the resource - `archive/job-9fe2c865/tmp/rt/seed.gdl` has none and
  `retargeted.gdl`, its build, has one - but does not always: half the seeds
  made from Extron's Mach, Shockwave and Turbulence templates were built and
  have none, and what decides it is not known. A face a donor has no resource for is appended from a seed
  that carries it, never from this directory (`gdl.fonts.find_face`,
  `seeds/README.md`).
- **Arial** (`arial.ttf`) is Monotype Arial 5.10, 778,580 bytes, in the Afterburn
  seeds for the 1035, 1230W, 1535, 725, 835 and both ECP presets, in the
  Shockwave 320, 525 and 535 seeds and in both Zoom Rooms seeds. Every other seed embeds the Windows Arial of the machine that made
  it, 7.05 (1,016,724 bytes) or 7.06 (1,045,720), and all of them but Turbulence
  still declare the Monotype file as well, so they declare `arial.ttf` twice and
  carry one of the two. Turbulence declares only the Monotype file and carries a
  Windows Arial - 7.05 in the 1035 seed, 7.06 in the 725 - under an Arial
  resource with no embedded file name, so
  `extract()`, which goes by the declared name and size, returns no `arial.ttf`
  for it, and `python -m gdl.fonts` says both sides of that.
- **Extron-Shockwave** (`extron_shockwave.ttf`, 3,736 bytes, the smallest face
  in the corpus) is embedded in every Shockwave seed, and read out of one
  rather than recovered (below).

Recovering from a seed that embeds a Windows Arial replaces the Monotype
`arial.ttf` here; the fixtures all embed the Monotype one. So the icon faces
only the Mach and Shockwave seeds carry - Extron-Lift and Extron-Shockwave - are
not recovered at all: the renderer and a spec's `icon` read each straight out of
its family's 1035 seed (`gdl.fonts.seed_face`), and leave this directory alone.
Arial and Arial Black they read from here, which the fixtures supply. A face is
drawn in the one build found, whichever build the panel embeds: Extron-Afterburn
is the kit's, which the 1035 seeds embed, and the 320, 525, 725 and 300M
Portrait seeds embed one of their own whose glyphs sit 6% of an em higher
(`docs/design-rules.md` §6).

A template has no `layout.json`, so nothing in it declares a face; `python -m
gdl.fonts "<Template>.glt" gdl/fonts/` writes every face it carries, each under
its resource's own file name, or GUI Designer's `arial.ttf` and `ariblk.ttf`
for the System faces, whose resources in a template name no file.

Prefer the embedded copy over an installed one even on a host that has Arial.
The embedded face is the one GUI Designer rasterized the ground-truth snapshots
with; the system copy is whatever build the OS happens to ship. Windows' own
`arial.ttf` is 1,016,724 or 1,045,720 bytes against the fixtures' 778,580.

## A missing face is said aloud

`face()` takes a face from its own file recovered here first; then, for an
icon face no recovery put here, from its family's seed (above); then from a
stand-in - the recovered Arial, after a partial recovery, or the host's copy of
the face or of Arial - and raises `LookupError` only when none has it. On a host
with Arial installed (Windows, macOS) the host's Arial stands in for every face
missing here, so a checkout that skipped recovery renders on it and scores
worse - the render baseline reads 2.81% instead of 2.19%.
`gdl.compose.FALLBACKS` records every face drawn in a stand-in, and
`tests/score.py record` refuses to write a score over one, naming the recovery
loop above.
