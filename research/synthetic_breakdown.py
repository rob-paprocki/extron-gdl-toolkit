"""Where the render differs on the synthetic fixture, control by control.

    python research/synthetic_breakdown.py [<project.gdl> <snapshots/Individual>]

tests/score.py scores whole pages. The synthetic fixture (tests/data/synthetic/)
was made to give the text findings ground truth beyond one typeface
(docs/render-fidelity.md section 9), so this splits its pages' differing pixels
by what drew them: each control's own rect, grouped by face and style for one
with a caption and by type for one without. The same `diff_stats` threshold as
the harness (a pixel differs by more than 24 levels), counted inside the rect.
Overlapping rects count a pixel in each, so the groups do not add up to a page.
"""
import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageChops  # noqa: E402

from gdl.compose import fill_index, group_members, load, render_page  # noqa: E402

ID_RE = re.compile(r'_Id(\d+)\.png$')


def bad_mask(a, b):
    d = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).convert('L')
    return d.point(lambda v: 255 if v >= 24 else 0)


def main(argv):
    gdl = argv[1] if len(argv) > 1 else os.path.join(ROOT, 'tests', 'data', 'synthetic', 'synthetic.gdl')
    snaps = argv[2] if len(argv) > 2 else os.path.join(ROOT, 'tests', 'data', 'synthetic', 'snapshots',
                                                         'Individual')
    layout, assets = load(gdl)
    groups = group_members(layout)
    fills = fill_index(gdl)
    pages = {p['ID']: p for p in layout['Pages'] + layout['PopupPages']}
    tally = collections.defaultdict(lambda: [0, 0, 0])      # group -> [bad, area, controls]
    for fn in sorted(os.listdir(snaps)):
        m = ID_RE.search(fn)
        if not m or int(m.group(1)) not in pages:
            continue
        page = pages[int(m.group(1))]
        ref = Image.open(os.path.join(snaps, fn)).convert('RGB')
        mine = render_page(page, assets, ref.size, groups=groups, fills=fills)
        mask = bad_mask(mine, ref)
        for c in page.get('Controls') or []:
            kind = c['__type'].split(':')[0][2:]
            states = c.get('States') or []
            src = states[c.get('TLPDefaultStateID', 0)] if states else c
            text = (src.get('Text') or c.get('Text') or '').strip()
            if text and not c.get('FlattenText') and kind != 'PopupPageReference':
                f = src.get('Font') or c.get('Font') or {}
                st = f.get('Style') or {}
                style = ('bold ' if st.get('Bold') else '') + ('italic' if st.get('Italic') else '')
                key = f"text: {f.get('Name')} {style.strip() or 'regular'}"
            else:
                key = f'no live text: {kind}' + (' (flattened)' if c.get('FlattenText') else '')
            x, y = max(0, c['Left']), max(0, c['Top'])
            box = (x, y, min(ref.width, c['Left'] + c['Width']), min(ref.height, c['Top'] + c['Height']))
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            region = mask.crop(box)
            tally[key][0] += region.histogram()[255]
            tally[key][1] += region.width * region.height
            tally[key][2] += 1
    width = max(len(k) for k in tally)
    print(f'{"what drew it":<{width}}  controls  differing')
    for key, (bad, area, n) in sorted(tally.items(), key=lambda kv: -kv[1][0] / max(1, kv[1][1])):
        print(f'{key:<{width}}  {n:>8}  {100 * bad / max(1, area):8.2f}%')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
