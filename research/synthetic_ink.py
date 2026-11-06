"""How far down and up each caption line's ink reaches in GUI Designer's
snapshot, against what gdl.compose.caption_fit says of it.

    python research/synthetic_ink.py [<project.gdl> <snapshot_dir>] [--json out.json]

With no project it reads the synthetic fixture. Each line of every live
caption, as compose.layout sets it, has its snapshot ink read as
research/synthetic_lines.py reads it - how far each pixel lies from the page
drawn without words toward the caption's color - over the columns the line
spans and the rows of its own line box. Its ink's foot is the lowest row
holding any, plus that row's coverage, and its top the highest less its
own, each to a fraction of a pixel; a line whose ink comes within 1.5 px of
its box is left out, as GUI Designer cuts ink at the box. Each is set
against the lines' ink as these models put it, from the baseline layout()
sets:

  pillow   - Pillow's ink box (getbbox) of the glyphs at PT, the size
             gdl.compose drew them at before it drew them at VERTICAL of it
             (what caption_fit read until then)
  outline  - the outline's own box (gdl.sfnt bounds) at 96 DPI, the em the
             lines are set down the box at (compose.VERTICAL)
  hinted   - the same, each extent from the baseline rounded to a whole
             pixel, as grid-fitting snaps a glyph's heights
  ppem     - the same at a whole number of pixels to the em, as TrueType
             hints a face: 20 pt is 26.67 px at 96 DPI, hinted at 27
  drawn    - Pillow's ink box of the glyphs at the 96 DPI em (compose.drawn)
  line_ink - compose.line_ink, what caption_fit reads now: the line drawn
             alone as draw_text draws it, its pixels half covered, on the
             whole-pixel baseline Pillow sets it on

and printed as each model's error, its foot and its top: mean, rms and worst,
> 0 where the model's ink reaches further than the snapshot's.
"""
import collections
import json
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from gdl import compose  # noqa: E402
from gdl.compose import fill_index, group_members, load, render_page  # noqa: E402
from synthetic_lines import GDL, SNAPS, coverage  # noqa: E402

ID_RE = re.compile(r'_Id(\d+)\.png$')
SEEN = 0.1          # coverage a row needs for its ink to count
MARGIN = 1.5        # how near its box a model may put a line's ink and it still be measured
REACH = 3           # px past the furthest model's ink that a line's band reaches


def outline(fnt, ln):
    """(top, foot) of `ln`'s outline from its baseline in font units, y up,
    and the face's em in units; None where it has no glyf."""
    a = compose.advances(fnt)
    if a is None:
        return None
    bs = [a.bounds(ch) for ch in ln]
    bs = [b for b in bs if b]
    if not bs:
        return None
    return max(b[3] for b in bs), min(b[1] for b in bs), a.upem


def models(fnt, ln, tx, base, pt):
    """{model: (ink top, ink foot)} in page px."""
    out = {}
    _, t, _, b = fnt.getbbox(ln, anchor='ls')
    out['pillow'] = (base + t, base + b)
    got = outline(fnt, ln)
    if got:
        top, foot, upem = got
        em = pt * 4 / 3
        out['outline'] = (base - top * em / upem, base - foot * em / upem)
        out['hinted'] = (base - round(top * em / upem), base + round(-foot * em / upem))
        # Grid-fitted at a whole number of pixels to the em, as TrueType
        # hints a face: 20 pt is 26.67 px at 96 DPI, hinted at 27.
        ppem = round(em)
        out['ppem'] = (base - round(top * ppem / upem), base + round(-foot * ppem / upem))
    # Pillow's ink box of the glyphs drawn at the em the lines are set at.
    small = fnt.font_variant(size=fnt.size * compose.VERTICAL)
    _, t, _, b = small.getbbox(ln, anchor='ls')
    out['drawn'] = (base + t, base + b)
    ink = compose.line_ink(ln, fnt, tx, base)
    if ink:
        out['line_ink'] = (ink[1], ink[3])
    return out


def measure(gdl, snaps):
    layout, assets = load(gdl)
    groups, fills = group_members(layout), fill_index(gdl)
    pages = {p['ID']: p for p in layout['Pages'] + layout['PopupPages']}
    rows = []
    with compose.as_the_panel(gdl):
        for fn in sorted(os.listdir(snaps)):
            m = ID_RE.search(fn)
            if not m or int(m.group(1)) not in pages:
                continue
            page = pages[int(m.group(1))]
            ref = Image.open(os.path.join(snaps, fn)).convert('RGB')
            snap = np.asarray(ref)
            bare = np.asarray(render_page(page, assets, ref.size, draw_txt=False, groups=groups,
                                          fills=fills).convert('RGB'))
            for c in page.get('Controls') or []:
                kind = c['__type'].split(':')[0]
                if kind == 'PBPopupPageReference' or c.get('FlattenText'):
                    continue
                states = c.get('States') or []
                src = states[c.get('TLPDefaultStateID', 0)] if states else c
                text = src.get('Text') or c.get('Text') or ''
                if not text.strip():
                    continue
                f = src.get('Font') or c.get('Font') or {}
                style = f.get('Style') or {}
                bold, italic = int(bool(style.get('Bold'))), int(bool(style.get('Italic')))
                pt = f.get('PointSize', 12)
                fnt = compose.face(f.get('Name', 'Arial'), bold, italic, pt * compose.PT)
                if getattr(fnt, 'stand_in', None):
                    continue
                color = compose.rgba(src.get('TextColor')) or compose.rgba(c.get('TextColor')) or (255, 255, 255, 255)
                align = src.get('TextAlignment', c.get('TextAlignment', 3))
                if align == 9:
                    align = c.get('TextAlignment', 3)
                box = (c['Left'], c['Top'], c['Width'], c['Height'])
                theirs = coverage(snap, bare, color)
                asc, desc = compose.layout_metrics(fnt)
                lh = asc + desc
                shear = compose.OBLIQUE if getattr(fnt, 'oblique', False) else 0.0
                for i, (ln, x, base) in enumerate(compose.layout(box, text, fnt, align)):
                    if not ln.strip():
                        continue
                    ms = models(fnt, ln, x, base, pt)
                    if not all(box[1] + MARGIN <= t and b <= box[1] + box[3] - MARGIN for t, b in ms.values()):
                        continue
                    x0 = int(x + compose.DX + shear * i * lh - shear * asc) - 2
                    x1 = int(x + compose.DX + shear * i * lh + compose.measure(ln, fnt) + shear * desc) + 3
                    x0, x1 = max(x0, box[0]), min(x1, box[0] + box[2])
                    # The rows any model puts ink in, and REACH more: ink
                    # further off is another control's, or art under it.
                    r0 = max(int(base - asc), int(min(t for t, _ in ms.values()) - REACH))
                    r1 = min(int(base + desc) + 1, int(max(b for _, b in ms.values()) + REACH) + 1)
                    band = theirs[r0:r1, x0:x1]
                    if band.size == 0:
                        continue
                    prof = band.max(axis=1)
                    # The run of inked rows through the line's baseline, and
                    # none above or below it: a gap is something else's ink.
                    at = int(base) - 1 - r0
                    if not 0 <= at < len(prof) or prof[at] < SEEN:
                        continue
                    lo = hi = at
                    while lo > 0 and prof[lo - 1] >= SEEN:
                        lo -= 1
                    while hi + 1 < len(prof) and prof[hi + 1] >= SEEN:
                        hi += 1
                    if (prof[:max(lo - 1, 0)] >= SEEN).any() or (prof[hi + 2:] >= SEEN).any():
                        continue
                    top = r0 + lo + 1 - prof[lo]
                    foot = r0 + hi + prof[hi]
                    rows.append(dict(page=page['Name'], name=c.get('Name'), face=f.get('Name'), pt=pt,
                                     bold=bold, italic=italic, line=i, text=ln, base=round(base, 2),
                                     top=round(float(top), 2), foot=round(float(foot), 2),
                                     **{f'{k}_top': round(t - top, 2) for k, (t, _) in ms.items()},
                                     **{f'{k}_foot': round(b - foot, 2) for k, (_, b) in ms.items()}))
    return rows


MODELS = ('pillow', 'outline', 'hinted', 'ppem', 'drawn', 'line_ink')


def summarise(rows):
    def stats(vs):
        return (f'mean {st.mean(vs):+.2f} rms {st.mean(v * v for v in vs) ** .5:.2f} '
                f'worst {max(vs, key=abs):+.2f}')
    print(f'{len(rows)} lines')
    for k in MODELS:
        hs = [(r[f'{k}_foot'] - r[f'{k}_top']) for r in rows if f'{k}_foot' in r]
        if hs:
            print(f'  {k:8s} height n={len(hs):3d}  {stats(hs)}')
        for side in ('foot', 'top'):
            vs = [r[f'{k}_{side}'] for r in rows if f'{k}_{side}' in r]
            if vs:
                # The foot reaches further down as it grows; the top up as it falls.
                vs = vs if side == 'foot' else [-v for v in vs]
                print(f'  {k:8s} {side:4s} n={len(vs):3d}  {stats(vs)}')
    by = collections.defaultdict(list)
    for r in rows:
        by[(r['face'], r['pt'])].append(r)
    print('by face and size: hinted foot / top')
    for k in sorted(by):
        rs = by[k]
        if 'hinted_foot' not in rs[0]:
            continue
        print(f'  {str(k):30s} n={len(rs):3d}  foot {st.mean(r["hinted_foot"] for r in rs):+.2f}'
              f'  top {-st.mean(r["hinted_top"] for r in rs):+.2f}'
              f'   outline foot {st.mean(r["outline_foot"] for r in rs):+.2f}'
              f'  pillow foot {st.mean(r["pillow_foot"] for r in rs):+.2f}')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--json' in sys.argv:
        args.remove(sys.argv[sys.argv.index('--json') + 1])
    gdl, snaps = (args + [None, None])[:2] if args else (GDL, SNAPS)
    got = measure(gdl, snaps)
    summarise(got)
    if '--json' in sys.argv:
        with open(sys.argv[sys.argv.index('--json') + 1], 'w', encoding='utf-8') as fh:
            json.dump(got, fh, indent=1)
