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
import json
import sys

sys.path.insert(0, __file__.rsplit('/', 2)[0])

from gdl.compose import load  # noqa: E402

# Type numbers as layout.json writes them, for the message only.
TYPE_NAME = {6: 'PopupPageReference', 7: 'Button', 11: 'Label', 13: 'Shape',
             9: 'Line', 10: 'Image', 14: 'Slider', 15: 'Level', 12: 'DateTime'}


def _caption(c):
    st = c.get('States') or []
    return (st[0].get('Text') if st else None) or c.get('Text') or ''


def _index(page):
    """name -> control. Names are unique per page by construction (spec ids)."""
    out = {}
    for c in page.get('Controls') or []:
        out.setdefault(c.get('Name'), c)
    return out


def check(plan_path, built_path):
    plan = json.load(open(plan_path))
    j, _ = load(built_path)
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
