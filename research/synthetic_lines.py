"""Where GUI Designer's snapshot puts each caption line, against gdl.compose.

    python research/synthetic_lines.py [--json out.json]

tests/score.py scores whole pages, and research/synthetic_breakdown.py splits
them by control; this goes a line further. Each line of every live caption on
the synthetic fixture's pages, as gdl.compose lays it out (compose.layout)
and draws it, is moved to where its coverage best matches the snapshot's ink
in the control's rect - the correlation of the two over shifts of up to 4 px
across and 8 down, refined to a fraction of a pixel by a parabola through the
best three. The snapshot's ink is read as how far each pixel lies from the
page drawn without words toward the caption's color, so a fill or a photo
behind it drops out. dy > 0: the snapshot's line is lower than the
renderer's; dx > 0, further right.

It found finding 7's vertical model (docs/render-fidelity.md): drawn at PT
both ways, the lines sat 2.3 px low, in proportion to their size, and split
by alignment the offset was the line pitch at 96 DPI and a foot under a
centred or bottom-aligned block. Printed: the offsets by alignment and face,
by line count and line, and by point size.
"""
import collections
import json
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from gdl import compose  # noqa: E402
from gdl.compose import fill_index, group_members, load, render_page  # noqa: E402

GDL = os.path.join(ROOT, 'tests', 'data', 'synthetic', 'synthetic.gdl')
SNAPS = os.path.join(ROOT, 'tests', 'data', 'synthetic', 'snapshots', 'Individual')
ID_RE = re.compile(r'_Id(\d+)\.png$')
RX, RY = 5, 9           # the rect grown by this much, and the shifts tried within it


def coverage(img, bare, color):
    """How far each pixel of `img` lies from `bare` toward `color`, 0 to 1 -
    0 where the color is too near its ground to read."""
    img, bare = img.astype(float), bare.astype(float)
    d = np.array(color[:3], float)[None, None, :] - bare
    den = (d * d).sum(-1)
    f = ((img - bare) * d).sum(-1) / np.maximum(den, 1)
    f[den < 40 * 40] = 0
    return np.clip(f, 0, 1)


def _line(size, fnt, ln, x, base):
    """One line's coverage, as compose.draw_text draws it."""
    img = Image.new('L', size, 0)
    compose.draw_glyphs(ImageDraw.Draw(img), x + compose.DX, base, ln, fnt, 255,
                        compose.advances(fnt) if compose.FRAC_PLACE else None)
    img = compose.embolden(img, fnt)
    if getattr(fnt, 'oblique', False):
        s = compose.OBLIQUE
        img = img.transform(img.size, Image.AFFINE, (1, s, -s * base, 0, 1, 0),
                            resample=Image.BILINEAR)
    return np.asarray(img, float) / 255


def _shift(a, dx, dy):
    """`a` moved dx right and dy down, what it leaves empty 0."""
    out = np.zeros_like(a)
    h, w = a.shape
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = \
        a[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
    return out


def best_shift(mine, theirs, lo, hi):
    """(score, dx, dy): where `mine` best matches `theirs`, their ink taken only
    in rows lo..hi as `mine` moves."""
    grid = {}
    for dy in range(-RY + 1, RY):
        band = np.zeros_like(theirs)
        r0, r1 = max(0, int(lo + dy)), min(theirs.shape[0], int(hi + dy) + 1)
        band[r0:r1] = theirs[r0:r1]
        bb = max((band * band).sum(), 1e-9)
        for dx in range(-RX + 1, RX):
            sh = _shift(mine, dx, dy)
            den = np.sqrt((sh * sh).sum() * bb)
            grid[(dx, dy)] = (sh * band).sum() / den if den else 0.0
    (dx, dy), s = max(grid.items(), key=lambda kv: kv[1])

    def refine(a, b, at):
        if a is None or b is None or a - 2 * s + b >= 0:
            return at
        return at + 0.5 * (a - b) / (a - 2 * s + b)
    return (s, refine(grid.get((dx - 1, dy)), grid.get((dx + 1, dy)), dx),
            refine(grid.get((dx, dy - 1)), grid.get((dx, dy + 1)), dy))


def measure_lines(gdl=GDL, snaps=SNAPS):
    layout, assets = load(gdl)
    groups, fills = group_members(layout), fill_index(gdl)
    pages = {p['ID']: p for p in layout['Pages'] + layout['PopupPages']}
    rows = []
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
            fnt = compose.face(f.get('Name', 'Arial'), bold, italic, f.get('PointSize', 12) * compose.PT)
            color = compose.rgba(src.get('TextColor')) or compose.rgba(c.get('TextColor')) or (255, 255, 255, 255)
            align = src.get('TextAlignment', c.get('TextAlignment', 3))
            box = (c['Left'], c['Top'], c['Width'], c['Height'])
            lines = compose.layout(box, text, fnt, align)
            X0, Y0 = max(0, box[0] - RX), max(0, box[1] - RY)
            X1, Y1 = min(ref.width, box[0] + box[2] + RX), min(ref.height, box[1] + box[3] + RY)
            theirs = coverage(snap[Y0:Y1, X0:X1], bare[Y0:Y1, X0:X1], color)
            asc, desc = compose.layout_metrics(fnt)
            for i, (ln, x, base) in enumerate(lines):
                if not ln.strip():
                    continue
                mine = _line(ref.size, fnt, ln, x, base)[Y0:Y1, X0:X1]
                if mine.sum() < 4:
                    continue
                s, dx, dy = best_shift(mine, theirs, base - asc - Y0 - 1, base + desc - Y0 + 1)
                rows.append(dict(page=page['Name'], name=c.get('Name'), face=f.get('Name'), bold=bold,
                                 italic=italic, pt=f.get('PointSize', 12), valign=align // 3,
                                 halign=align % 3, nlines=len(lines), line=i, text=ln, box=list(box),
                                 score=round(float(s), 3), dx=round(float(dx), 2), dy=round(float(dy), 2)))
    return rows


def summarise(rows):
    def table(title, key, rs=rows):
        print(title)
        g = collections.defaultdict(list)
        for r in rs:
            g[key(r)].append(r)
        for k in sorted(g, key=str):
            dy, dx = [r['dy'] for r in g[k]], [r['dx'] for r in g[k]]
            print(f'  {str(k):40s} n={len(dy):3d}  dy {st.mean(dy):+.2f} (rms {st.mean(v * v for v in dy) ** .5:.2f})'
                  f'  dx {st.mean(dx):+.2f}')
    dys = [r['dy'] for r in rows]
    print(f'{len(rows)} lines: dy mean {st.mean(dys):+.2f}, rms {st.mean(v * v for v in dys) ** .5:.2f}, '
          f'worst {max(map(abs, dys)):.2f}')
    names = {0: 'bottom', 1: 'middle', 2: 'top'}
    table('by alignment and face', lambda r: (names[r['valign']], r['face'], 'bold' if r['bold'] else '',
                                              'italic' if r['italic'] else ''))
    table('by line count and line', lambda r: (r['nlines'], r['line']))
    table('by point size', lambda r: r['pt'])


if __name__ == '__main__':
    got = measure_lines()
    if compose.FALLBACKS:
        raise SystemExit(f'drawn in stand-ins: {sorted(compose.FALLBACKS)} - recover the faces first')
    summarise(got)
    if '--json' in sys.argv:
        with open(sys.argv[sys.argv.index('--json') + 1], 'w', encoding='utf-8') as fh:
            json.dump(got, fh, indent=1)
