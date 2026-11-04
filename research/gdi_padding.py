"""GDI+'s 1/6 em of padding a side, as a left- or right-aligned caption shows it -
measured, not shipped (docs/render-fidelity.md section 9).

GUI Designer's snapshot sets a left-aligned caption in from its box's edge by
about a sixth of the font's size - 3 px at 14 pt, 9 px at 40 pt on the
synthetic fixture's Type Sizes page - where gdl.compose sets it at the edge.
That is GDI+'s default StringFormat padding, 1/6 em a side, which a centred
caption never shows: the client project the first baseline was scored on
centred all but three of its 490 captions, so it never measured it. The
figures on that project are in docs/render-fidelity.md section 9.

    python research/gdi_padding.py            # each variant on the synthetic fixture

It patches gdl.compose.draw_text in memory - `inset`: a left- or right-aligned
line moved in by PAD em; `wrap`: every caption also wrapped 2 x PAD em
narrower, as GDI+ lays it out in its box less the padding - and scores the
synthetic fixture as tests/score.py does, diffed against its shipped baseline.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tests'))

from PIL import ImageDraw  # noqa: E402

from gdl import compose  # noqa: E402

PAD = 1 / 6
_draw_text = compose.draw_text


def padded(wrap):
    def draw_text(img, box, text, fnt, color, alignv):
        x, y, w, h = box
        pad = PAD * fnt.size
        horz = alignv % 3
        if not wrap:
            # Only the line's position moves: wrap at the box as before.
            dx = pad if horz == 1 else -pad if horz == 2 else 0
            return _draw_text(img, (x + dx, y, w, h), text, fnt, color, alignv)
        return _draw_text(img, (x + pad, y, w - 2 * pad, h), text, fnt, color, alignv)
    return draw_text


def score(gdl, snaps, base):
    import score as harness
    got = harness.record(os.path.join(ROOT, gdl), os.path.join(ROOT, snaps))
    with open(os.path.join(ROOT, base), encoding='utf-8') as fh:
        before = json.load(fh)
    s, b = harness.summarise(got), harness.summarise(before)
    worse = sum(1 for k in got if got[k] - before[k] > 0.01)
    better = sum(1 for k in got if before[k] - got[k] > 0.01)
    return (f"mean {b['mean']:.2f}% -> {s['mean']:.2f}%, median {b['median']:.2f}% -> "
            f"{s['median']:.2f}%, worst {b['worst']:.2f}% -> {s['worst']:.2f}%; "
            f'{better} better, {worse} worse')


if __name__ == '__main__':
    fixtures = [('synthetic', 'tests/data/synthetic/synthetic.gdl',
                 'tests/data/synthetic/snapshots/Individual', 'tests/baseline-synthetic.json')]
    for name, wrap in (('inset', False), ('inset and wrap', True)):
        compose.draw_text = padded(wrap)
        for fx, gdl, snaps, base in fixtures:
            print(f'{name:<15} {fx:<9} {score(gdl, snaps, base)}', flush=True)
    compose.draw_text = _draw_text
    if compose.FALLBACKS:
        raise SystemExit(f'drawn in stand-ins: {sorted(compose.FALLBACKS)} - recover the faces first')
