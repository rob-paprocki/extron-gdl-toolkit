"""Record a per-page fidelity score, and diff two recordings.

`compare_snapshots.py` prints a table for a human to read. That is the wrong
shape for the rule in CLAUDE.md - a render change must report before and after
across *all* pages, because several plausible fixes improve one page and
regress twenty. Reading two tables side by side does not catch a page that got
0.4% worse.

So: record a run to JSON, make the change, record again, and diff.

    python tests/score.py record <project.gdl> <snapshots/Individual> -o before.json
    # ... edit gdl/compose.py ...
    python tests/score.py record <project.gdl> <snapshots/Individual> -o after.json
    python tests/score.py diff before.json after.json

tests/baseline.json is the currently shipped state, refreshed whenever a
render change lands, so any working change can be diffed against it directly.
The diff exits non-zero if any page regressed by more than --tol (default
0.01%), so it can gate a commit. Scores come from the same `diff_stats` the
harness uses, so the numbers are directly comparable to its output.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from gdl.compose import (diff_stats, fill_index, group_members, load,  # noqa: E402
                         render_page)

ID_RE = re.compile(r'_Id(\d+)\.png$')


def record(gdl_path, snapshot_dir):
    """Score every snapshot that maps to a page. Returns {filename: pct_bad}."""
    layout, assets = load(gdl_path)
    groups = group_members(layout)
    fills = fill_index(gdl_path)
    pages = {p['ID']: p for p in layout['Pages'] + layout['PopupPages']}

    scores, missing = {}, []
    for fn in sorted(os.listdir(snapshot_dir)):
        m = ID_RE.search(fn)
        if not m:
            continue
        page = pages.get(int(m.group(1)))
        if page is None:
            missing.append(fn)
            continue
        ref = Image.open(os.path.join(snapshot_dir, fn)).convert('RGB')
        mine = render_page(page, assets, ref.size, groups=groups, fills=fills)
        scores[fn] = diff_stats(mine, ref)['pct_bad']

    # Same guard as compare_snapshots: matching is by numeric id alone, so the
    # wrong fixture scores confidently against unrelated pages.
    if missing and len(missing) > len(scores):
        raise SystemExit(f'{len(missing)} of {len(missing) + len(scores)} snapshots have no '
                         f'matching page - these snapshots are probably not from this .gdl')
    return scores


def summarise(scores):
    vals = sorted(scores.values())
    if not vals:
        return {'pages': 0}
    return {
        'pages': len(vals),
        'mean': sum(vals) / len(vals),
        'median': vals[len(vals) // 2],
        'worst': vals[-1],
    }


def diff(before, after, tol):
    """Print every page's delta, worst regression first. Non-zero if any regressed."""
    names = sorted(set(before) | set(after))
    width = max(len(n) for n in names)
    rows = []
    for n in names:
        b, a = before.get(n), after.get(n)
        if b is None or a is None:
            # A page appearing or vanishing changes the mean's denominator, so
            # it is a finding in itself rather than something to skip over.
            rows.append((float('inf') if b is None else float('-inf'), n, b, a))
        else:
            rows.append((a - b, n, b, a))
    rows.sort(reverse=True)

    print(f'{"snapshot":<{width}}  {"before":>8}  {"after":>8}  {"delta":>8}')
    for delta, n, b, a in rows:
        if b is None:
            print(f'{n:<{width}}  {"-":>8}  {a:7.2f}%  {"NEW":>8}')
        elif a is None:
            print(f'{n:<{width}}  {b:7.2f}%  {"-":>8}  {"GONE":>8}')
        else:
            mark = '  <-- REGRESSED' if delta > tol else ''
            print(f'{n:<{width}}  {b:7.2f}%  {a:7.2f}%  {delta:+7.2f}%{mark}')

    sb, sa = summarise(before), summarise(after)
    print(f'\nbefore  {sb["pages"]} pages   mean {sb["mean"]:.2f}%   '
          f'median {sb["median"]:.2f}%   worst {sb["worst"]:.2f}%')
    print(f'after   {sa["pages"]} pages   mean {sa["mean"]:.2f}%   '
          f'median {sa["median"]:.2f}%   worst {sa["worst"]:.2f}%')

    if sb['pages'] != sa['pages']:
        print(f'\nPAGE COUNT CHANGED {sb["pages"]} -> {sa["pages"]} - the means are not comparable')
        return 1

    regressed = [(d, n) for d, n, b, a in rows if b is not None and a is not None and d > tol]
    if regressed:
        print(f'\n{len(regressed)} page(s) regressed by more than {tol}%:')
        for d, n in regressed:
            print(f'  {n}  {d:+.2f}%')
        return 1
    print(f'\nno page regressed by more than {tol}%')
    return 0


def main():
    ap = argparse.ArgumentParser(description='Record a per-page fidelity score, and diff two recordings.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    r = sub.add_parser('record', help='score every page and write JSON')
    r.add_argument('gdl')
    r.add_argument('snapshots', help='the Individual/ directory of a snapshot export')
    r.add_argument('-o', '--out', required=True)

    d = sub.add_parser('diff', help='compare two recordings')
    d.add_argument('before')
    d.add_argument('after')
    d.add_argument('--tol', type=float, default=0.01,
                   help='percentage points of regression to tolerate (default 0.01)')

    args = ap.parse_args()

    if args.cmd == 'record':
        scores = record(args.gdl, args.snapshots)
        with open(args.out, 'w') as fh:
            json.dump(scores, fh, indent=1, sort_keys=True)
        s = summarise(scores)
        print(f'{s["pages"]} pages   mean {s["mean"]:.2f}%   '
              f'median {s["median"]:.2f}%   worst {s["worst"]:.2f}%   -> {args.out}')
        return 0

    with open(args.before) as fh:
        before = json.load(fh)
    with open(args.after) as fh:
        after = json.load(fh)
    return diff(before, after, args.tol)


if __name__ == '__main__':
    raise SystemExit(main())
