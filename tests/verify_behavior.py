"""Does the BUILT panel carry everything the generated program addresses?

A program and a panel generated from one spec agree by construction - until
Build gets a say. Build renumbers pages (a page authored as 1000 comes back as
51), keeps the donor's pages alongside the generated ones, and places the
references that decide where a popup can appear. So this reads the program that
will actually run - the generated Python, parsed, not just its handoff - and
checks every name and ID in it against the built file.

    python tests/verify_behavior.py <program_dir> <built.gdl>

Exits non-zero on any problem, the way tests/verify_built.py gates a layout.
Stdlib only: it reads layout.json through gdl.container, not the compositor.
"""
import ast
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.container import open_payload  # noqa: E402

CLASS_TYPE = {'Button': 'PBButton', 'Label': 'PBLabel', 'Level': 'PBLevel',
              'Slider': 'PBSlider'}
REF_TYPE = 6            # PBPopupPageReference, as layout.json numbers it
GENERATED = ('ui_objects.py', 'ui_events.py', 'ui_feedback.py')


def _sha(src):
    for line in src.splitlines()[:6]:
        if line.startswith('# spec_sha256:'):
            return line.split(':', 1)[1].strip()
    return None


def read_program(out_dir):
    """(handoff, {id: class}, [(method, name)], start page, problems)."""
    problems = []
    with open(os.path.join(out_dir, 'handoff.json'), encoding='utf-8') as fh:
        handoff = json.load(fh)
    srcs = {}
    for name in GENERATED:
        with open(os.path.join(out_dir, name), encoding='utf-8') as fh:
            srcs[name] = fh.read()
    # V6: every generated file and the handoff come from one generation. A
    # hand-edited or half-regenerated program is exactly what this catches.
    for name, src in srcs.items():
        if _sha(src) != handoff['spec_sha256']:
            problems.append(f"{name} was generated from a different spec than handoff.json "
                            f"({_sha(src)} vs {handoff['spec_sha256']}) - regenerate")

    objects = {}
    for n in ast.parse(srcs['ui_objects.py']).body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and \
                isinstance(n.value.func, ast.Name) and n.value.func.id in CLASS_TYPE:
            args = n.value.args
            if len(args) >= 2 and isinstance(args[1], ast.Constant) and \
                    isinstance(args[1].value, int) and not isinstance(args[1].value, bool):
                objects[args[1].value] = n.value.func.id
            else:
                problems.append(f'ui_objects.py line {n.lineno}: a control not addressed by an '
                                f'int ID')
    shows, start = [], None
    for n in ast.walk(ast.parse(srcs['ui_events.py'])):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'START_PAGE'
                                             for t in n.targets):
            if isinstance(n.value, ast.Constant):
                start = n.value.value
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and \
                n.func.attr in ('ShowPage', 'ShowPopup', 'HidePopup') and n.args:
            a = n.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                shows.append((n.func.attr, a.value))
            elif not (isinstance(a, ast.Name) and a.id == 'START_PAGE'):
                problems.append(f'ui_events.py line {n.lineno}: {n.func.attr} not given a name - '
                                f'pages and popups are addressed by name')
    return handoff, objects, shows, start, problems


def check(out_dir, built_path):
    """(problems, notes, checked) for a program directory and a built .gdl."""
    return check_layout(out_dir, json.loads(open_payload(built_path).read('layout.json')))


def check_layout(out_dir, j):
    """The same, against an already-read layout.json."""
    handoff, objects, shows, start, problems = read_program(out_dir)
    notes, checked = [], 0
    pages = {p['Name']: p for p in j['Pages']}
    popups = {p['Name']: p for p in j['PopupPages']}
    ours = {p['name'] for p in handoff['pages']} | {p['name'] for p in handoff['popups']}

    # V1: every page and popup name the code passes exists, as the right kind.
    if start is None:
        problems.append('ui_events.py sets no START_PAGE')
    for method, name in [('ShowPage', start)] + shows:
        if name is None:
            continue
        table, kind = (pages, 'page') if method == 'ShowPage' else (popups, 'popup')
        checked += 1
        if name not in table:
            other = 'popup' if kind == 'page' else 'page'
            is_other = name in (popups if kind == 'page' else pages)
            problems.append(f'{method}({name!r}): no {kind} of that name in the built file'
                            + (f" - it is a {other}" if is_other else ''))

    # V6, the other half: the objects the code builds are the handoff's.
    listed = {c['id']: c['class'] for c in handoff['controls']}
    if listed != objects:
        problems.append(f'ui_objects.py and handoff.json disagree on the addressed controls: '
                        f'{sorted(set(objects.items()) ^ set(listed.items()))}')

    # V2/V3: each addressed control is where the handoff says, with that ID and
    # that type - and no other control in a generated container shares its ID.
    addressed = set(listed)
    for c in handoff['controls']:
        for at in c['at']:
            box = pages.get(at['container']) or popups.get(at['container'])
            if box is None:
                problems.append(f"{at['container']!r} is not in the built file")
                continue
            got = [x for x in box.get('Controls') or [] if x.get('Name') == at['name']]
            checked += 1
            if not got:
                problems.append(f"{at['container']!r}: {at['name']!r} (ID {c['id']}) is not in "
                                f'the built file')
                continue
            x = got[0]
            if x.get('UserId') != c['id']:
                problems.append(f"{at['container']!r} {at['name']!r}: built ID {x.get('UserId')}, "
                                f"the program addresses {c['id']}")
            if x.get('__type') != CLASS_TYPE[c['class']]:
                problems.append(f"{at['container']!r} {at['name']!r}: built as "
                                f"{x.get('__type')}, the program makes it a {c['class']}")
            # V4: a control the program switches On must have an On to show.
            if c['class'] == 'Button' and (c['bind'] or c['select_group']) and \
                    len(x.get('States') or []) < 2:
                problems.append(f"{at['container']!r} {at['name']!r}: the program sets its "
                                f"state, but it built with {len(x.get('States') or [])} state(s)")
    expected = {(at['container'], at['name']) for c in handoff['controls'] for at in c['at']}
    for box in list(pages.values()) + list(popups.values()):
        for x in box.get('Controls') or []:
            if x.get('UserId') not in addressed or x.get('Type') == REF_TYPE:
                continue
            if box['Name'] in ours and (box['Name'], x.get('Name')) not in expected:
                problems.append(f"{box['Name']!r} {x.get('Name')!r} carries ID {x['UserId']}, "
                                f'which the program uses for a different control')
            elif box['Name'] not in ours:
                notes.append(f"donor page {box['Name']!r} {x.get('Name')!r} also carries ID "
                             f"{x['UserId']} - unreachable from the generated pages, but it "
                             f'shares their events and feedback if shown')

    # V5: a shown popup can actually appear on the page that shows it. A
    # standard popup needs a reference bound to its group on that page; a modal
    # needs the reference Build places for it on every page.
    for src, target in handoff['navigation']:
        pu = popups.get(target)
        if pu is None or src not in pages:
            continue
        refs = [x.get('PopupPageID') or {} for x in pages[src].get('Controls') or []
                if x.get('Type') == REF_TYPE]
        checked += 1
        if pu.get('Modal'):
            ok = any(r.get('IsPopupPageIdValid') and r.get('PopupID') == pu['ID'] for r in refs)
        else:
            ok = any(r.get('IsPopupGroupIdValid') and r.get('GroupID') == pu.get('GroupID')
                     for r in refs)
        if not ok:
            problems.append(f'page {src!r} shows popup {target!r}, but the built page has no '
                            f'reference that can display it')
    return problems, notes, checked


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[0])
        print('usage: verify_behavior.py <program_dir> <built.gdl>')
        return 2
    problems, notes, checked = check(argv[1], argv[2])
    for n in notes:
        print('  note: ' + n)
    for p in problems:
        print('  ' + p)
    print(f'{checked} program reference(s) verified against the build, '
          f'{len(problems)} problem(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
