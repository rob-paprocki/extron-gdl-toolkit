# The synthetic fixture

A project with no client in it, built by this toolkit, and GUI Designer's own
snapshot exports of it: the render baseline's ground truth, and the built
project the edit, render and verifier tests read. It replaced a client's
project and its snapshots, which are no longer in the repo
(`docs/history.md`). `CLAUDE.md` *Verifying a change* has the baseline and
how to score against it.

| File | What it is |
|---|---|
| `make_synthetic.py` | writes `synthetic.json`, and with `--art` the pictures in `art/` (Pillow) |
| `synthetic.json` | the spec: 10 pages and 18 popups on a TLP Pro 1035T, Afterburn |
| `art/` | its own pictures - a backdrop, a test pattern, stripes, a glyph twice, a slider's thumb - drawn by `make_synthetic.py`, no Extron art |
| `synthetic.gdl` | the spec built on `seeds/Afterburn 1035.gdl` by `powershell/New-GdlPanel.ps1`, which verified it |
| `snapshots/Individual/` | GUI Designer's *Take All Pages Snapshot (Individual)* of `synthetic.gdl`, exported by `powershell/Export-GdlSnapshots.ps1` |

`tests/test_synthetic.py` holds these to one another, and every picture to the
hash `tools/public_sync.py`'s `BINARY_OK` pins it by.

## What it holds

That client project's reach, in generic words: pages and popups of the sizes it
had (full-screen pages, a 915x800 content area, 136x496 strips, a 900x530
panel, a 995x800 keyboard, modals), every control type the renderer draws -
buttons of one to four states, labels, panels, lines, images, sliders, clocks,
popup references bound to a group (which a snapshot paints) and to one popup
(which it does not) - and the Offline Page.

Its text is what the client's lacked. The client's drew one family, Forma DJR
Display (`docs/render-fidelity.md` §7 *Scope limit*); this one draws Open Sans
regular, bold and italic from 14 to 40 pt, Open Sans Light, Arial, Arial Black
and the Extron-Afterburn icon face, in all nine alignments, wrapped at four
widths, broken by hand, split mid-word, bold on one line and on two near its
box's edge and far from it (§8), flattened into the art by Build, over
opaque art and over nothing (a popup with no background, a modal's scrim).

| Page or popup | What it covers |
|---|---|
| Start | a fitted background picture, a clock and a date, a group reference to a popup with no background |
| Main | a rail of buttons, a clock, references to the Content and Level groups and one bound to a single popup |
| Matrix | a reference to the Wide group |
| Type Sizes | Open Sans regular, bold and italic at eight sizes |
| Type Faces | Arial, Arial Black, Open Sans Light and Open Sans at four sizes, on a fill, in color |
| Alignment | the nine alignments, one line on a fill and two lines off one |
| Wrapping | a sentence at four widths, hand breaks, a split word, bold captions near and far from their edge |
| Buttons | the seed's borders but 3D Gradient (`docs/ROADMAP.md`), translucent fills over a picture, one to four states, icons, pictures, captions Build flattens |
| Controls | sliders four ways up and one with a thumb of its own art, lines of three weights and three ways, a picture fitted and stretched, panels, three clocks |
| Keys | a reference to the Keys group |
| Content Alpha to Theta | the 915x800 group: lists, two-line bold keys, dense labels, paragraphs, icons, sliders, a matrix, Arial |
| Level One, Level Two | the 136x496 strips: a slider, a two-line bold label, a key |
| Wide Grid | the 900x530 panel: rows of two-line keys |
| Keys Upper, Keys Lower | the 995x800 keyboard: single-character keys, an entry field |
| Note Clear | a popup with no background: text over nothing |
| Single | shown through a reference bound to it alone |
| Confirm, Notice, Busy | modals: a card, a paragraph, text on the scrim |

What it does not hold: a Level - the Afterburn 1035 seed has none, and the
applier clones only a clock from another seed (`docs/gdl-format.md` §7), so
the renderer's Level path is scored by neither baseline - and a caption stored
only as formatted text, with hand-placed tabs and line breaks, which only a
hand-edited project has (its flattened captions carry their words as plain
text in both fields, as a spec writes them). Three things its
first build failed `tests/verify_built.py` on are out of it, each said where
it was in `make_synthetic.py` and in `docs/ROADMAP.md`'s backlog: a 3D
Gradient border, a slider's rail of art, a 1 px line.

Two of its captions GUI Designer cuts, and its snapshots show it: Type Sizes'
Italic40 trimmed to 'Type 40 Itali', Wrapping's LongWord split over three
lines - what `gdl.compose.fitted` is measured on. So its spec says
`"caption_fit": "off"`, as a measurement spec does (SKILL.md step 4):
`gdl.spec check` passes over its captions and `tests/verify_built.py` says the
two rather than refusing them. With the key taken away the check names those
two and nothing else (`tests/test_synthetic.py`). The key reaches no op of the
plan, so the build is the one it always was.

## As built

Built on GUI Designer 1.28.0.7: 531 controls, 2,836 checks of the build
against its plan and none failed, Save and Build 1,315 s (the first build of
it, before the three above came out, 836 s). Exported: 29 PNGs, the 28 pages
and popups and the Offline Page. Scored at its first recording: **mean 3.44%,
median 2.68%, worst 8.03%**, the same to the last digit whether its faces were
recovered from it or from the client's project; the baseline the renderer is
scored against now (`tests/baseline-synthetic.json`) is in `CLAUDE.md`
*Verifying a change*, and `docs/render-fidelity.md` §9 says where the pixels
differ.

## Making it again

A change to the spec, the art or the seed is a rebuild and a re-export, and
new pins. On the Windows host with GUI Designer, from the repo root, with GUI
Designer closed (each script opens and closes it):

```bash
python tests/data/synthetic/make_synthetic.py            # --art too, if the art changed
powershell -NoProfile -File powershell/New-GdlPanel.ps1 -Spec tests/data/synthetic/synthetic.json \
    -Donor "seeds/Afterburn 1035.gdl" -Output C:/gdlwork/synthetic/synthetic.gdl -TimeoutSeconds 1800
cp C:/gdlwork/synthetic/synthetic.gdl tests/data/synthetic/synthetic.gdl
powershell -NoProfile -File powershell/Export-GdlSnapshots.ps1 \
    -ProjectFile tests/data/synthetic/synthetic.gdl -Out tests/data/synthetic/snapshots/Individual
python tests/score.py record tests/data/synthetic/synthetic.gdl \
    tests/data/synthetic/snapshots/Individual -o tests/baseline-synthetic.json
python tests/test_synthetic.py
```

`New-GdlPanel.ps1` must end `PANEL BUILT AND VERIFIED`, and
`Export-GdlSnapshots.ps1` `SNAPSHOTS EXPORTED` - it refuses a set short of the
project's pages and popups. Then look at every new picture and pin it in
`BINARY_OK`, and say what the baseline moved by - a rebuilt fixture is new
ground truth, not a render change.
