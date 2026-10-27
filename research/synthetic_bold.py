"""Synthetic bold, as GUI Designer draws a bold caption in a face it has no bold
file for - measured, not shipped (docs/render-fidelity.md finding 8).

GUI Designer embeds Forma DJR Display regular only, and draws the client
fixture's bold captions by emboldening it. The model fitted on the 44 bold
captions of the scored pages:

  - each glyph's coverage smeared one whole pixel to the right (GDI's own
    simulated-bold overstrike), and
  - each advance grown by 1/60 em - in em, not pixels: every constant-pixel
    growth tried (0.3 to 1 px) scored worse.

Run from the repository root, with the fixtures and recovered faces:

    python research/synthetic_bold.py

It patches gdl.compose in memory, scores the 27 pages as tests/score.py does,
and diffs the result against tests/baseline.json.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tests'))

from PIL import Image, ImageChops, ImageDraw  # noqa: E402

from gdl import compose  # noqa: E402

SMEAR_PX = 1.0          # the overstrike, rightward; 1.1 is already much worse
ADVANCE_EM = 1 / 60     # 0.016-0.0175 em score alike; 0.02 and 0.015 worse

_face, _measure = compose.face, compose.measure


def face(name, bold, italic, px):
    f = _face(name, bold, italic, px)
    # A bold caption drawn from a file that is not bold is emboldened.
    f.synthetic_bold = bool(bold) and 'bold' not in (f.getname()[1] or '').lower()
    return f


def _extra(fnt):
    return ADVANCE_EM * fnt.size if getattr(fnt, 'synthetic_bold', False) else 0.0


def measure(s, fnt, draw=None):
    return _measure(s, fnt, draw) + _extra(fnt) * len(s)


def _shift(mask, dx):
    return mask.transform(mask.size, Image.AFFINE, (1, 0, -dx, 0, 1, 0), resample=Image.BILINEAR)


_draw_text = compose.draw_text


def draw_text(img, box, text, fnt, color, alignv):
    if not getattr(fnt, 'synthetic_bold', False):
        return _draw_text(img, box, text, fnt, color, alignv)
    # As compose.draw_text, but into a coverage mask that is smeared before
    # it is drawn through - so the smear does not compound antialiased edges -
    # with ImageDraw.bitmap, which blends as ImageDraw.text does.
    x, y, w, h = box
    vert, horz = alignv // 3, alignv % 3
    lines = compose.wrap(text, fnt, w, lambda s, f: measure(s, f))
    asc, desc = compose.metrics(fnt)
    lh = asc + desc
    block = lh * len(lines)
    top = y if vert == 2 else y + (h - block) / 2 if vert == 1 else y + h - block
    adv = compose.advances(fnt)
    mask = Image.new('L', img.size, 0)
    m = ImageDraw.Draw(mask)
    for i, ln in enumerate(lines):
        tw = measure(ln, fnt)
        tx = x if horz == 1 else x + w - tw if horz == 2 else x + (w - tw) / 2
        tx += compose.DX
        ty = top + i * lh + asc
        for ch in ln:
            m.text((tx, ty), ch, font=fnt, fill=255, anchor='ls')
            tx += (adv.advance(ch, fnt.size) if adv else m.textlength(ch, font=fnt)) + _extra(fnt)
    smeared = mask
    steps = max(1, int(-(-SMEAR_PX // 0.5)))
    for k in range(1, steps + 1):
        smeared = ImageChops.lighter(smeared, _shift(mask, SMEAR_PX * k / steps))
    ImageDraw.Draw(img).bitmap((0, 0), smeared, fill=color)


def patch():
    compose.face, compose.measure, compose.draw_text = face, measure, draw_text


if __name__ == '__main__':
    import json

    import score
    patch()
    got = score.record(os.path.join(ROOT, 'fixtures/gdl/client-boardroom-2.0.0.gdl'),
                       os.path.join(ROOT, 'fixtures/snapshots/Individual'))
    if compose.FALLBACKS:
        raise SystemExit(f'drawn in stand-ins: {sorted(compose.FALLBACKS)} - recover the faces first')
    with open(os.path.join(ROOT, 'tests/baseline.json'), encoding='utf-8') as fh:
        base = json.load(fh)
    raise SystemExit(score.diff(base, got, 0.01))
