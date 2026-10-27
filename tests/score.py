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

The snapshots score the renderer on built artwork. What the spec preview draws
in place of artwork Build has not made yet is scored against a build instead:

    python tests/score.py preview <spec.json> <built.gdl> [<spec.json> <built.gdl> ...]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from gdl.compose import (FALLBACKS, FROM_SEED, diff_stats, fill_index,  # noqa: E402
                         group_members, load, render_page)

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
    # And a snapshot is named for its page: another version of the project
    # matches more than half by number - the TLP1035-1.1.0 fixture matched 14 of
    # the 27 and scored a 5.86% "residual" that was another project's pages.
    renamed = [f'{fn} is page {pages[int(ID_RE.search(fn).group(1))]["Name"]!r}'
               for fn in scores if fn[:ID_RE.search(fn).start()] !=
               pages[int(ID_RE.search(fn).group(1))]['Name']]
    if renamed:
        raise SystemExit('snapshots of pages by another name - these snapshots are not from '
                         'this .gdl:\n  ' + '\n  '.join(renamed))
    return scores


def preview(spec_path, built_path):
    """The spec preview against the panel built from that spec.

    Each page and popup of the spec, drawn by gdl.spec's preview, beside the
    same one drawn from the built file's own artwork - both as the panel shows
    them (compose.as_the_panel) and each alone, no popup shown in a group's
    region, since the preview draws none. Returns [(name, 'page' or 'popup',
    % differing, % differing with every level and slider set aside)], the two
    None where the build has nothing of that name.

    The panel draws a caption at runtime, in the faces the built file embeds,
    so text is drawn by the same code in those faces on both sides - the
    preview alone knows no donor, and would draw a seed's Roboto Thin where a
    320 embeds Light: this measures what the preview synthesises in place of
    Build's artwork - fills, borders, art and where each lies."""
    import copy

    from gdl.compose import as_the_panel, popup_groups, render_snapshot
    from gdl.spec import Panel
    panel = Panel.load(spec_path)
    layout, assets = load(built_path)
    fills = fill_index(built_path)
    built = {p['Name']: p for p in layout['Pages'] + layout['PopupPages']}
    hide = {g: None for g in popup_groups(layout)}
    # The preview lays out pages; a popup is laid out the same way.
    popups = copy.copy(panel)
    popups.pages = panel.popups
    rows = []
    for who, kind in ((panel, 'page'), (popups, 'popup')):
        for i, pg in enumerate(who.pages):
            b = built.get(pg['name'])
            if b is None:
                rows.append((pg['name'], kind, None, None))
                continue
            size = (b.get('Width') or panel.size[0], b.get('Height') or panel.size[1])
            with as_the_panel(built_path):
                # The preview's own as_the_panel() inside keeps these faces.
                mine = who.render(i).convert('RGB').crop((0, 0) + size)
                theirs = render_snapshot(layout, b['ID'], assets, size, shown=hide,
                                         fills=fills).convert('RGB')
            pct = diff_stats(mine, theirs)['pct_bad']
            # A level whose art the donor keeps (plan: keep_art) is previewed
            # as its bare bar, which is most of what differs where there is
            # one: the figure without them says what the rest is worth.
            for c in b.get('Controls') or []:
                if c['__type'].split(':')[0] in ('PBLevel', 'PBSlider'):
                    box = (c['Left'], c['Top'], c['Left'] + c['Width'], c['Top'] + c['Height'])
                    mine.paste((255, 0, 255), box)
                    theirs.paste((255, 0, 255), box)
            rows.append((pg['name'], kind, pct, diff_stats(mine, theirs)['pct_bad']))
    return rows


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

    p = sub.add_parser('preview', help='score the spec preview against the panel built from it')
    p.add_argument('pairs', nargs='+', metavar='spec.json built.gdl',
                   help='a spec and the panel built from it, as many pairs as you like')

    args = ap.parse_args()

    if args.cmd == 'preview':
        if len(args.pairs) % 2:
            ap.error('preview takes a spec and its built panel, in pairs')
        rows = []
        for spec, built in zip(args.pairs[::2], args.pairs[1::2]):
            print(built)
            for name, kind, pct, rest in preview(spec, built):
                print(f'  {kind:<5}  {name:<40}  ' + ('not in the built file' if pct is None else
                                                    f'{pct:6.2f}%  {rest:6.2f}% with levels and sliders aside'))
                if pct is not None:
                    rows.append((pct, rest))
        for col, what in ((0, 'all of it'), (1, 'levels and sliders aside')):
            vals = sorted(r[col] for r in rows)
            if vals:
                print(f'{len(vals)} page(s) and popup(s), {what}: mean {sum(vals) / len(vals):.2f}%   '
                      f'median {vals[len(vals) // 2]:.2f}%   worst {vals[-1]:.2f}%')
        if FALLBACKS:
            print(f"drawn in a stand-in on both sides - {'; '.join(sorted(FALLBACKS))}")
        if FROM_SEED:
            print(f"read from a seed on both sides, not carried by the build - {'; '.join(sorted(FROM_SEED))}")
        return 0

    if args.cmd == 'record':
        scores = record(args.gdl, args.snapshots)
        if FALLBACKS or FROM_SEED:
            # Not comparable with tests/baseline.json, which was scored on the
            # faces the project embeds: the host's Arial costs every page, and
            # a seed's face is another build of it, so the score would turn
            # on which seeds are pulled.
            print(f"scored on faces the fixtures do not embed - {'; '.join(sorted(FALLBACKS | FROM_SEED))} - "
                  f'for want of the recovered faces, nothing written. Recover them first:\n'
                  f'  for f in fixtures/gdl/*.gdl; do python -m gdl.fonts "$f" gdl/fonts/; done')
            return 2
        with open(args.out, 'w', encoding='utf-8') as fh:
            json.dump(scores, fh, indent=1, sort_keys=True)
        s = summarise(scores)
        print(f'{s["pages"]} pages   mean {s["mean"]:.2f}%   '
              f'median {s["median"]:.2f}%   worst {s["worst"]:.2f}%   -> {args.out}')
        return 0

    with open(args.before, encoding='utf-8') as fh:
        before = json.load(fh)
    with open(args.after, encoding='utf-8') as fh:
        after = json.load(fh)
    return diff(before, after, args.tol)


if __name__ == '__main__':
    raise SystemExit(main())
