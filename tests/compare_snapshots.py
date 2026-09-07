"""Score the reference compositor against GUI Designer's own snapshot renders.

GUI Designer can export a PNG per page (and per page+popup permutation) under
  C:/Users/Public/Documents/Extron/GUI Designer/Snapshots/<project>/
Those are ground truth: whatever the application draws is by definition right.
This harness composites the same pages from the .gdl and reports how far off we
are, so a change to the render rules can be judged by a number instead of by eye.

    python tests/compare_snapshots.py <project.gdl> <snapshot_dir> [--save out/]

Needs Pillow. Font rendering also wants the faces the project uses; run
`python -m gdl.fonts <project.gdl> gdl/fonts/` first to pull them out of the
file itself.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from gdl.compose import diff_stats, group_members, load, render_page  # noqa: E402

ID_RE = re.compile(r'_Id(\d+)\.png$')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('gdl')
    ap.add_argument('snapshots', help='the Individual/ directory of a snapshot export')
    ap.add_argument('--save', help='write our render of each page here')
    args = ap.parse_args()

    layout, assets = load(args.gdl)
    groups = group_members(layout)
    pages = {p['ID']: p for p in layout['Pages'] + layout['PopupPages']}
    if args.save:
        os.makedirs(args.save, exist_ok=True)

    rows, missing = [], []
    for fn in sorted(os.listdir(args.snapshots)):
        m = ID_RE.search(fn)
        if not m:
            continue
        pid = int(m.group(1))
        page = pages.get(pid)
        if page is None:
            missing.append(fn)
            continue
        ref = Image.open(os.path.join(args.snapshots, fn)).convert('RGB')
        mine = render_page(page, assets, ref.size, groups=groups)
        if args.save:
            mine.convert('RGB').save(os.path.join(args.save, f'{pid}.png'))
        rows.append((diff_stats(mine, ref)['pct_bad'], fn))

    # Snapshots are matched to pages by numeric id only, so pointing this at a
    # fixture the snapshots do not belong to yields a confident, meaningless
    # score. Refuse rather than mislead.
    if missing and len(missing) > len(rows):
        print(f'{len(missing)} of {len(missing) + len(rows)} snapshots have no matching page '
              f'- these snapshots are probably not from this .gdl')
        return 2

    rows.sort(reverse=True)
    width = max((len(n) for _, n in rows), default=10)
    print(f'{"snapshot":<{width}}  differing')
    for pct, name in rows:
        print(f'{name:<{width}}  {pct:7.2f}%')
    if rows:
        vals = sorted(p for p, _ in rows)
        mean = sum(vals) / len(vals)
        print(f'\n{len(rows)} pages   mean {mean:.2f}%   '
              f'median {vals[len(vals) // 2]:.2f}%   worst {vals[-1]:.2f}%')
    for fn in missing:
        print(f'  no such page in the .gdl: {fn}')
    # A regression guard, not a fidelity claim: GDI and Pillow will never agree
    # to the pixel, so this only catches a rule that has genuinely broken.
    return 1 if rows and sum(p for p, _ in rows) / len(rows) > 15 else 0


if __name__ == '__main__':
    raise SystemExit(main())
