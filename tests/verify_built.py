"""Did the build actually produce what the plan asked for?

A clean build is not the same as a correct one, and the gap is not small. GUI
Designer relocates a control that falls outside its page to 0,0 - at build time,
silently, still reporting 0 errors - and it bakes captions into artwork when
`flattenText` rides along on a clone. Both produce a file that opens, builds and
is wrong, and both were found by eye rather than by a check.

This is that check. It reads the plan the applier consumed and the `.gdl` GUI
Designer built, and asserts op by op that every authored control is present,
where it was put, and captioned as asked.

    python tests/verify_built.py out/plan.json out/generated9_built.gdl

Exits non-zero on any mismatch, so it can gate an authoring run the way
tests/score.py gates a render change.

Two things it deliberately does NOT treat as failures:

  * extra controls on a page. Build adds one full-canvas PBPopupPageReference
    per MODAL popup in the project, to every page. The Liberty Bank donor has
    six modal popups, so every generated page comes back with six references
    nobody authored. That is Build doing its job.
  * a popup page larger than the spec's size. A popup inherits its displayed
    dimensions from the reference that shows it; the page's own size only has
    to be big enough to hold the controls.
"""
import collections
import io
import json
import os
import sys

# os.path, not a '/' rsplit: on Windows __file__ comes back with backslashes and
# the split is a no-op, so the import below fails with ModuleNotFoundError.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from gdl.compose import load  # noqa: E402

# Type numbers as layout.json writes them, for the message only.
TYPE_NAME = {6: 'PopupPageReference', 7: 'Button', 11: 'Label', 13: 'Shape',
             9: 'Line', 10: 'Image', 14: 'Slider', 15: 'Level', 12: 'DateTime'}


def _caption(c):
    st = c.get('States') or []
    return (st[0].get('Text') if st else None) or c.get('Text') or ''


def _shares(assets, tid):
    """{(r,g,b): share of opaque pixels} for one rasterized asset.

    The authored fill does not survive into `layout.json`. A built control's
    `BackgroundFillColor` reads back as transparent white no matter what was
    authored, because Build rasterizes fill, border and caption together into a
    PNG and leaves only a `TLPImageID` behind. So the artwork is the only place
    the color a panel will actually show can be read - checking the model here
    would confirm nothing, which is the same trap `flattenText` set.
    """
    blob = assets.get(tid)
    if blob is None:
        return {}
    im = Image.open(io.BytesIO(blob)).convert('RGBA')
    raw = im.tobytes()
    counts = collections.Counter()
    for i in range(0, len(raw), 4):
        if raw[i + 3] > 250:                    # ignore antialiased edges
            counts[raw[i:i + 3]] += 1
    total = sum(counts.values())
    if not total:
        return {}
    return {tuple(k): v / total for k, v in counts.items()}


def _rgb(argb):
    return ((argb >> 16) & 0xFF, (argb >> 8) & 0xFF, argb & 0xFF)


def _hex(t):
    return '#%02X%02X%02X' % t


# Below this share of a control's opaque pixels, the planned fill is present but
# not the field - a caption-heavy button, say. Reported, not failed: the color
# did survive, and calling that a failure would make the gate untrustworthy.
WEAK_FILL = 0.10


def check_fills(plan_items, table, assets, kind):
    """Every planned fill must be the plurality color of the control's artwork."""
    problems, notes, checked = [], [], 0
    for item in plan_items:
        got = table.get(item['name'])
        if got is None:
            continue
        by_name = _index(got)
        planned = [(item, op) for op in item['controls'] if op.get('fill') is not None]
        for _, op in planned:
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if c is None:
                continue
            tid = c.get('TLPImageID')
            want = _rgb(op['fill'])
            if tid is None or tid < 0:
                problems.append(f"{kind} {item['name']!r} {name!r}: planned fill "
                                f'{_hex(want)} but Build produced no artwork '
                                f'(TLPImageID {tid}), so it will draw nothing')
                continue
            shares = _shares(assets, tid)
            if not shares:
                problems.append(f"{kind} {item['name']!r} {name!r}: artwork "
                                f'{tid} is missing or fully transparent')
                continue
            checked += 1
            top, top_share = max(shares.items(), key=lambda kv: kv[1])
            if top == want:
                continue
            mine = shares.get(want, 0.0)
            if mine >= WEAK_FILL:
                notes.append(f"{kind} {item['name']!r} {name!r}: fill {_hex(want)} is "
                             f'{mine:.0%} of the artwork, behind {_hex(top)} at '
                             f'{top_share:.0%}')
            else:
                problems.append(f"{kind} {item['name']!r} {name!r}: planned fill "
                                f'{_hex(want)} is {mine:.0%} of the built artwork; '
                                f'it is mostly {_hex(top)} ({top_share:.0%})')
    return problems, notes, checked


def check_page_background(plan_pages, pages, assets):
    """The donor's background image is a separate reference from its artwork.

    Clearing `<TLPImageID>` alone left `backgroundImageField` pointing at the
    donor's image, Build re-rasterized fill and image together, and the donor's
    artwork came back as a tint over the whole page. Reading the page asset is
    what catches that; the fill field on its own looked correct throughout.
    """
    problems = []
    for spec in plan_pages:
        pg = pages.get(spec['name'])
        if pg is None or spec.get('background') is None:
            continue
        want = _rgb(spec['background'])
        tid = pg.get('TLPImageID')
        if tid is None or tid < 0:
            continue
        shares = _shares(assets, tid)
        if not shares:
            continue
        top, top_share = max(shares.items(), key=lambda kv: kv[1])
        if top != want:
            problems.append(f"page {spec['name']!r} background: planned {_hex(want)}, "
                            f'artwork is mostly {_hex(top)} ({top_share:.0%}) - a donor '
                            f'background image re-rasterized under the fill looks '
                            f'exactly like this')
        elif top_share < 0.99:
            problems.append(f"page {spec['name']!r} background: {_hex(want)} covers only "
                            f'{top_share:.0%} of the page artwork, so something else is '
                            f'painted under the controls')
    return problems


def _index(page):
    """name -> control. Names are unique per page by construction (spec ids)."""
    out = {}
    for c in page.get('Controls') or []:
        out.setdefault(c.get('Name'), c)
    return out


def check_edits(plan, j):
    """An EDIT plan addresses existing controls by id, so verification is a
    direct lookup: did the field we asked for actually change?

    Captions need care. The plan may write `textField` on the control, on every
    state, or `ftextField` on every state, and the built `layout.json` reports
    one merged caption - so compare against that rather than against whichever
    field the op happened to name.
    """
    pages = {p['ID']: p for p in j['Pages'] + j['PopupPages']}
    problems, checked, unverifiable = [], 0, []
    for op in plan['controls']:
        pg = pages.get(op['page'])
        if pg is None:
            problems.append(f"page id {op['page']} is not in the built file")
            continue
        c = next((x for x in (pg.get('Controls') or []) if x.get('ID') == op['control']),
                 None)
        if c is None:
            problems.append(f"control id {op['control']} is not on page {pg['Name']!r}")
            continue
        checked += 1
        want_text = None
        for src in (op.get('fields') or {}, op.get('states') or {}):
            if 'textField' in src:
                want_text = src['textField']
        if op.get('states_ftext') is not None:
            want_text = op['states_ftext']
        if want_text is not None and not op.get('flattened'):
            got = (_caption(c) or '').replace('\t', '').replace('\r\n', ' ').strip()
            if got != want_text:
                problems.append(f"{pg['Name']!r} {c.get('Name')!r}: caption is {got!r}, "
                                f'the edit asked for {want_text!r}')
        elif want_text is not None:
            # A formatted-text caption is baked into the artwork, and
            # layout.json reports it as '' both before and after the edit. There
            # is nothing here to compare, so checking it would report a failure
            # that is really a lookup in the wrong place. Say so instead: the
            # only real check is looking at the asset.
            unverifiable.append(f"{pg['Name']!r} {c.get('Name')!r} -> {want_text!r}")
        for f, key in (('leftField', 'Left'), ('topField', 'Top'),
                       ('widthField', 'Width'), ('heightField', 'Height'),
                       ('userIdField', 'UserID')):
            want = (op.get('fields') or {}).get(f)
            if want is None or key not in c:
                continue
            if c[key] != want:
                problems.append(f"{pg['Name']!r} {c.get('Name')!r}: {key} is {c[key]}, "
                                f'the edit asked for {want}')
    for u in unverifiable:
        print(f'  NOT VERIFIABLE HERE (caption is baked into the artwork, '
              f'compare the asset PNG): {u}')
    return problems, checked


def check(plan_path, built_path):
    plan = json.load(open(plan_path))
    j, assets = load(built_path)
    if plan.get('generated_by') == 'gdl.edit':
        return check_edits(plan, j)
    pages = {p['Name']: p for p in j['Pages']}
    popups = {p['Name']: p for p in j['PopupPages']}

    problems = []
    checked = 0

    for spec, table, kind in ((plan['pages'], pages, 'page'),
                              (plan.get('popups') or [], popups, 'popup')):
        for item in spec:
            got = table.get(item['name'])
            if got is None:
                problems.append(f"{kind} {item['name']!r} is not in the built file")
                continue
            by_name = _index(got)
            for op in item['controls']:
                f = op['fields']
                name = f.get('nameField')
                c = by_name.get(name)
                if c is None:
                    problems.append(f"{kind} {item['name']!r}: control {name!r} "
                                    f'is not in the built file')
                    continue
                checked += 1
                want = (f.get('leftField'), f.get('topField'),
                        f.get('widthField'), f.get('heightField'))
                have = (c['Left'], c['Top'], c['Width'], c['Height'])
                if any(w is not None and w != h for w, h in zip(want, have)):
                    extra = ''
                    if have[:2] == (0, 0) and want[:2] != (0, 0):
                        extra = (' - moved to the origin, which is what GUI Designer '
                                 'does to a control that does not fit its page')
                    problems.append(
                        f"{kind} {item['name']!r} {name!r} "
                        f"({TYPE_NAME.get(c.get('Type'), c.get('Type'))}): "
                        f'planned {want}, built {have}{extra}')
                want_text = f.get('textField')
                if want_text is not None and _caption(c) != want_text:
                    problems.append(f"{kind} {item['name']!r} {name!r}: caption "
                                    f'{_caption(c)!r}, planned {want_text!r}')

    # A popup reference bound to nothing reads "Unassigned" on the panel and is
    # invisible in the file, so check the binding survived rather than trusting
    # that the applier's own assertion still holds after a build.
    groups = {g['ID'] for g in (j.get('PopupGroups') or [])}
    for pg in pages.values():
        for c in pg.get('Controls') or []:
            pp = c.get('PopupPageID')
            if not isinstance(pp, dict):
                continue
            if pp.get('IsPopupGroupIdValid') and groups and pp['GroupID'] not in groups:
                problems.append(f"page {pg['Name']!r} {c.get('Name')!r}: bound to popup "
                                f"group {pp['GroupID']}, which the built file has no "
                                f'record of')

    # Color, read off the artwork rather than the model - see _shares().
    for spec, table, kind in ((plan['pages'], pages, 'page'),
                              (plan.get('popups') or [], popups, 'popup')):
        probs, notes, n = check_fills(spec, table, assets, kind)
        problems += probs
        checked += n
        for note in notes:
            print(f'  FILL NOT DOMINANT (survived, but check it by eye): {note}')
    problems += check_page_background(plan['pages'], pages, assets)

    return problems, checked


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[0])
        print('usage: verify_built.py <plan.json> <built.gdl>')
        return 2
    problems, checked = check(argv[1], argv[2])
    for p in problems:
        print('  ' + p)
    print(f'{checked} authored control(s) verified against the build, '
          f'{len(problems)} problem(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
