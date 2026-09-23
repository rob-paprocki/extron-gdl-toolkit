"""Does the BUILT panel match its ID map?

An ID map and a panel generated from one spec agree by construction - until
Build gets a say. Build renumbers pages (a page authored as 1000 comes back as
51), keeps the donor's pages alongside the generated ones, and places the
references that decide where a popup can appear. A programmer works from the
map, so every ID and name in it is checked against the built file.

    python tests/verify_idmap.py <idmap_dir> <built.gdl>

Exits non-zero on any problem, the way tests/verify_built.py gates a layout.
Stdlib only: it reads layout.json through gdl.container, not the compositor.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.container import open_payload  # noqa: E402

TYPE = {'Button': 'PBButton', 'Label': 'PBLabel', 'Level': 'PBLevel', 'Slider': 'PBSlider'}
REF_TYPE = 6            # PBPopupPageReference, as layout.json numbers it


def _index(items, kind, problems):
    """Name -> built page or popup, reporting a name that appears twice rather
    than letting the second silently replace the first."""
    out = {}
    for p in items:
        if p['Name'] in out:
            problems.append(f"{kind} {p['Name']!r} appears twice in the built file - every "
                            f'check on it would see only one')
        out[p['Name']] = p
    return out


def _shows(page, popup):
    """Can this built page display this built popup?"""
    for x in page.get('Controls') or []:
        if x.get('Type') != REF_TYPE:
            continue
        r = x.get('PopupPageID') or {}
        if popup.get('Modal'):
            if r.get('IsPopupPageIdValid') and r.get('PopupID') == popup['ID']:
                return True
        elif r.get('IsPopupGroupIdValid') and r.get('GroupID') == popup.get('GroupID'):
            return True
    return False


def _hosts(m, pages, popups):
    """Container -> the map's pages it can be showing over. A popup appears
    over whichever page is up when it is shown; a standard one only where that
    page can display it."""
    ours = [p['name'] for p in m['pages']]
    hosts = {p: {p} for p in ours}

    def only(target, over):
        pu = popups.get(target)
        if pu is None or pu.get('Modal'):
            return set(over)
        return {p for p in over if p in pages and _shows(pages[p], pu)}

    for pu in m['popups']:
        hosts[pu['name']] = only(pu['name'], set(ours) if pu['reached_by'] == 'program'
                                 else set())
    changed = True
    while changed:
        changed = False
        for s, t in m['navigation']:
            if t in ours:
                continue
            add = only(t, hosts.get(s, set()))
            if not add <= hosts.setdefault(t, set()):
                hosts[t] |= add
                changed = True
    return hosts


def check(idmap_dir, built_path):
    """(problems, notes, checked) for an ID map directory and a built .gdl."""
    return check_layout(idmap_dir, json.loads(open_payload(built_path).read('layout.json')))


def check_layout(idmap_dir, j):
    """The same, against an already-read layout.json."""
    with open(os.path.join(idmap_dir, 'idmap.json'), encoding='utf-8') as fh:
        m = json.load(fh)
    problems, notes, checked = [], [], 0
    pages = _index(j['Pages'], 'page', problems)
    popups = _index(j['PopupPages'], 'popup', problems)
    ours = {p['name'] for p in m['pages']} | {p['name'] for p in m['popups']}

    # Every page and popup the map names exists, as the kind it says.
    for kind, items, table in (('page', m['pages'], pages), ('popup', m['popups'], popups)):
        for it in items:
            checked += 1
            if it['name'] not in table:
                other = popups if kind == 'page' else pages
                problems.append(f"{kind} {it['name']!r} is not in the built file"
                                + (f" - it built as a {'popup' if kind == 'page' else 'page'}"
                                   if it['name'] in other else ''))
            elif kind == 'popup' and bool(table[it['name']].get('Modal')) != it['modal']:
                problems.append(f"popup {it['name']!r} built "
                                f"{'modal' if table[it['name']].get('Modal') else 'standard'}, "
                                f"the map says {'modal' if it['modal'] else 'standard'}")

    # Each control is where the map says, with that ID and that type - every
    # control of that name, not just the first - and no other control in a
    # mapped page shares its ID.
    addressed = {c['id'] for c in m['controls']}
    expected = {}
    for c in m['controls']:
        for at in c['at']:
            key = (at['container'], at['name'])
            expected[key] = expected.get(key, 0) + 1
    for c in m['controls']:
        for at in c['at']:
            box = pages.get(at['container']) or popups.get(at['container'])
            if box is None:
                continue                  # reported above
            got = [x for x in box.get('Controls') or [] if x.get('Name') == at['name']]
            checked += 1
            if not got:
                problems.append(f"{at['container']!r}: {at['name']!r} (ID {c['id']}) is not in "
                                f'the built file')
                continue
            if len(got) > expected[(at['container'], at['name'])]:
                problems.append(f"{at['container']!r}: {len(got)} controls are named "
                                f"{at['name']!r}, the map lists "
                                f"{expected[(at['container'], at['name'])]}")
            for x in got:
                if x.get('UserId') != c['id']:
                    problems.append(f"{at['container']!r} {at['name']!r}: built ID "
                                    f"{x.get('UserId')}, the map says {c['id']}")
                if x.get('__type') != TYPE[c['type']]:
                    problems.append(f"{at['container']!r} {at['name']!r}: built as "
                                    f"{x.get('__type')}, the map says {c['type']}")
    for box in list(pages.values()) + list(popups.values()):
        for x in box.get('Controls') or []:
            if x.get('UserId') not in addressed or x.get('Type') == REF_TYPE:
                continue
            if box['Name'] in ours and (box['Name'], x.get('Name')) not in expected:
                problems.append(f"{box['Name']!r} {x.get('Name')!r} carries ID {x['UserId']}, "
                                f'which the map gives to a different control')
            elif box['Name'] not in ours:
                # A program binds by ID alone, so this one answers to the same
                # handler - harmless while the page is never shown.
                notes.append(f"donor page {box['Name']!r} {x.get('Name')!r} also carries ID "
                             f"{x['UserId']} - it shares that control's events and feedback "
                             f'if the page is ever shown')

    # Every popup a button shows can appear over every page it can be shown
    # on - for one shown from another popup, the pages THAT one is over.
    hosts = _hosts(m, pages, popups)
    for src, target in m['navigation']:
        pu = popups.get(target)
        if pu is None:
            continue
        for page in sorted(hosts.get(src, ())):
            if page not in pages:
                continue
            checked += 1
            if not _shows(pages[page], pu):
                via = '' if src == page else f' (shown from {src!r})'
                problems.append(f'popup {target!r}{via} cannot appear over page {page!r}: the '
                                f'built page has no reference that can display it')
    return problems, notes, checked


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[0])
        print('usage: verify_idmap.py <idmap_dir> <built.gdl>')
        return 2
    problems, notes, checked = check(argv[1], argv[2])
    for n in notes:
        print('  note: ' + n)
    for p in problems:
        print('  ' + p)
    print(f'{checked} ID map reference(s) verified against the build, '
          f'{len(problems)} problem(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
