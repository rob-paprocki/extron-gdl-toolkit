"""Where GUI Designer cuts a live caption's ink at its box, against what
gdl.compose.caption_fit says of it.

    python research/caption_clips.py [<project.gdl> <snapshot_dir> [<authored.gdl>]]

With no project it reads the synthetic fixture. <authored.gdl> is a copy
whose boxes were moved after the build - each control's box is read from its
ProjectGCP (gdl.project) in place of layout.json's, as GUI Designer's
snapshot of an unbuilt edit draws them: run so on seeds/Turbulence 720.gdl,
its snapshots, and a copy with its Confirmation and Incoming Call questions'
boxes shrunk about their middles and that copy's snapshots, it found the
rows GUI Designer cuts (docs/render-fidelity.md finding 7; the copy and
both sets of snapshots, of 2026-11-05, are not in the repo - the rows they
show are in tests/test_compose.py TestTheInkGUIDesignerCuts).

Each line of every live caption whose ink compose.line_ink puts within
NEAR px of a side of its box is printed with its ink's coverage row by row
(column by column for a side) across that edge: the snapshot's, read as
research/synthetic_lines.py reads it, beside compose's own drawn alone and
uncut - the snapshot's stops at the box where GUI Designer cuts it, compose's
shows what was cut - and what caption_fit says of the caption.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from gdl import compose  # noqa: E402
from gdl.compose import fill_index, group_members, load, render_page  # noqa: E402
from synthetic_lines import GDL, SNAPS, _line, coverage  # noqa: E402

ID_RE = re.compile(r'_Id(\d+)\.png$')
# Lines whose ink comes within this many px of a side of their box are printed
# ($NEAR; finding 7 read them at 2.5).
NEAR = float(os.environ.get('NEAR', 1.0))
SPAN = 3            # rows either side of the edge printed


def authored_boxes(path):
    """{(page name, control name): (x, y, w, h)} as `path`'s ProjectGCP holds them."""
    from gdl.project import Project
    return {(pg['name'], c.get('name')): tuple(c['rect']) for pg in Project.open(path).pages()
            for c in pg['controls'] if c.get('rect')}


def main(gdl, snaps, authored=None):
    layout, assets = load(gdl)
    groups, fills = group_members(layout), fill_index(gdl)
    pages = {p['ID']: p for p in layout['Pages'] + layout['PopupPages']}
    boxes = authored_boxes(authored) if authored else {}
    with compose.as_the_panel(gdl):
        for fn in sorted(os.listdir(snaps)):
            m = ID_RE.search(fn)
            if not m or int(m.group(1)) not in pages:
                continue
            page = pages[int(m.group(1))]
            ref = Image.open(os.path.join(snaps, fn)).convert('RGB')
            snap = np.asarray(ref)
            bare = None
            for c in page.get('Controls') or []:
                for state, text, f, align in compose.built_captions(c):
                    style = f.get('Style') or {}
                    pt = f.get('PointSize', 12)
                    fnt = compose.face(f.get('Name', 'Arial'), int(bool(style.get('Bold'))),
                                       int(bool(style.get('Italic'))), pt * compose.PT)
                    if getattr(fnt, 'stand_in', None) or state is not None:
                        continue
                    box = boxes.get((page['Name'], c.get('Name'))) or (c['Left'], c['Top'], c['Width'], c['Height'])
                    x, y, w, h = box
                    near = []
                    for i, (ln, tx, base) in enumerate(compose.layout(box, text, fnt, align)):
                        ink = compose.line_ink(ln, fnt, tx, base)
                        if ink is None:
                            continue
                        for side, past in (('top', y - ink[1]), ('foot', ink[3] - (y + h)),
                                           ('left', x - ink[0]), ('right', ink[2] - (x + w))):
                            if past > -NEAR:
                                near.append((i, ln, tx, base, side, past))
                    if not near:
                        continue
                    if bare is None:
                        bare = np.asarray(render_page(page, assets, ref.size, draw_txt=False, groups=groups,
                                                      fills=fills).convert('RGB'))
                    src = (c.get('States') or [c])[0]
                    color = compose.rgba(src.get('TextColor')) or compose.rgba(c.get('TextColor')) or (255, 255, 255, 255)
                    theirs = coverage(snap, bare, color)
                    said = compose.caption_fit(box, text, fnt, align)
                    print(f"{page['Name']!r} {c.get('Name')!r} {f.get('Name')} {pt} pt in {box}: "
                          f"{[k + ': ' + v for k, v in said] or 'fits'}")
                    lh = sum(compose.layout_metrics(fnt))
                    for i, ln, tx, base, side, past in near:
                        mine = _line(ref.size, fnt, ln, tx + compose.OBLIQUE * i * lh * getattr(fnt, 'oblique', 0), base)
                        lo, hi = int(tx) - 2, int(tx + compose.measure(ln, fnt)) + 3
                        top, foot = int(base - lh), int(base + lh)
                        if side in ('top', 'foot'):
                            edge = y if side == 'top' else y + h
                            rows = range(edge - SPAN, edge + SPAN)
                            cut = lambda a, r: float(a[r, max(lo, 0):hi].max())
                        else:
                            edge = x if side == 'left' else x + w
                            rows = range(edge - SPAN, edge + SPAN)
                            cut = lambda a, r: float(a[max(top, 0):foot, r].max())
                        print(f'   line {i} {ln!r} {side}: ink {past:+.2f} px past; '
                              f"{'row' if side in ('top', 'foot') else 'col'} {rows[0]}..{rows[-1]} (edge at {edge})")
                        print('     snapshot ' + ' '.join(f'{cut(theirs, r):4.2f}' for r in rows))
                        print('     compose  ' + ' '.join(f'{cut(mine, r):4.2f}' for r in rows))


if __name__ == '__main__':
    a = sys.argv[1:]
    main(*a) if a else main(GDL, SNAPS)
