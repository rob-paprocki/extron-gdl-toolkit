"""Test this repo's documented beliefs against every .gdl it can reach.

Almost everything this toolkit knows about the format was inferred from ONE
project - the Liberty Bank fixture. Two bugs on 2026-09-10 came from exactly
that: a rule that is true of that project and false in general.

  * "a popup's authored size is always the whole canvas" - true of Liberty Bank,
    false in Extron's Afterburn template, where 10 of 29 popups are 880x525.
  * "PBStates.Count is the number of states" - it is a logical count and returns
    1 for an ordinary two-state button, so every applier loop wrote state 0.

Both were found by measuring rather than reasoning. This runs that measurement
over the whole corpus, so the next one is found before it ships.

    python tests/audit_corpus.py                  # fixtures + seeds + templates
    python tests/audit_corpus.py --no-templates   # skip Extron's 44 .glt (faster)
    python tests/audit_corpus.py <dir> [<dir>..]  # anywhere else

It prints one line per project, then each invariant as PASS, FAIL or INFO. Exit
code is the number of FAILs, so it works as a gate.

STREAMING, deliberately. The first version loaded every project before checking
anything - 19 projects plus 44 templates, ~600 MB of .gdl parsed into Python
objects at once - on a box with 8 GB of RAM and a 500 MB pagefile, and it took
the machine's commit charge to the limit ("The paging file is too small"). Each
project is now reduced to a small dict of facts and released before the next
one is opened.

A MEASUREMENT tool, not a unit test: what it reports depends on which files a
machine has, so pytest does not collect it and CI does not run it.
"""
import collections
import gc
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from gdl.container import open_gdl, open_payload  # noqa: E402
from gdl.project import Project  # noqa: E402
from _corpus import REPO, SEEDS_DIR, TEMPLATES_DIR, usable  # noqa: E402


def discover(dirs):
    out = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(('.gdl', '.glt')):
                out.append(os.path.join(d, name))
    return out


def _built(path):
    try:
        return json.loads(open_payload(path).read('layout.json').decode('utf-8-sig'))
    except Exception:                                    # noqa: BLE001
        return None


def facts(path):
    """Everything the invariants need from one project, as plain data."""
    from gdl import fonts as gfonts
    p = Project.open(path)
    lay = _built(path)
    pages = list(p.pages())
    f = {
        'name': os.path.basename(path),
        'has_project': next(p.instances('PBProject'), None) is not None,
        'built': lay is not None,
        'part': (lay or {}).get('PartNumber'),
        'platform': ((lay or {}).get('Platform') or {}).get('__type'),
        'n_pages': sum(g['kind'] == 'page' for g in pages),
        'n_popups': sum(g['kind'] == 'popup' for g in pages),
        'n_controls': sum(len(g['controls']) for g in pages),
    }
    sizes = collections.Counter(tuple(g['size']) for g in pages
                                if g['kind'] == 'page' and None not in g['size'])
    f['canvas'] = sizes.most_common(1)[0][0] if sizes else None

    state_counts, state_pairs, caption_in = (collections.Counter() for _ in range(3))
    max_uid = 0
    for g in pages:
        for c in g['controls']:
            if isinstance(c.get('id'), int):
                max_uid = max(max_uid, c['id'])
            if c['type'] != 'PBButton':
                continue
            state_counts[c['n_states']] += 1
            if c['n_states'] == 2:
                state_pairs[tuple(str(s) for s in c['state_names'])] += 1
            if c['caption']:
                caption_in[c['caption_in']] += 1
    f.update(state_counts=state_counts, state_pairs=state_pairs,
             caption_in=caption_in, max_uid=max_uid)

    names = collections.Counter(g['name'] for g in pages if g['name'])
    f['dup_names'] = {k: v for k, v in names.items() if v > 1}

    # Build adds one full-canvas PBPopupPageReference per modal popup to every
    # page - the Offline Page included only when EnableOfflinePage is on. Found
    # in two steps: "every modal popup" failed all 20 built projects by exactly
    # one; "every modal popup but the Offline Page" then failed only the
    # Turbulence seed, the one project with the offline page enabled. Count
    # only full-canvas refs: a page may also carry authored refs that show a
    # sub-popup in a region.
    offline = (lay or {}).get('OfflinePageID')
    offline_on = bool((lay or {}).get('EnableOfflinePage'))
    f['n_modal'] = sum(1 for g in pages if g['kind'] == 'popup' and g.get('modal')
                       and (offline_on or g['id'] != offline))
    full = collections.Counter()
    for g in pages:
        if g['kind'] != 'page':
            continue
        full[sum(1 for c in g['controls']
                 if c['type'] == 'PBPopupPageReference'
                 and tuple(c['rect']) == (0, 0) + tuple(g['size']))] += 1
    f['fullcanvas_refs'] = full

    f['borders'] = sorted(p.border_resource_names())
    f['fonts'] = sorted(p.font_resource_names())

    f['popup_mismatch'], f['default_state'], f['unrasterized'] = [], collections.Counter(), 0
    f['fonts_missing'], f['fonts_error'] = None, None
    if lay:
        authored = {g['name']: tuple(g['size']) for g in pages if g['kind'] == 'popup'}
        for bp in lay.get('PopupPages') or []:
            want = authored.get(bp.get('Name'))
            if want and None not in want and (bp['Width'], bp['Height']) != want:
                f['popup_mismatch'].append((bp['Name'], want, (bp['Width'], bp['Height'])))
        for coll in ('Pages', 'PopupPages'):
            for g in lay.get(coll) or []:
                for c in g.get('Controls') or []:
                    d = c.get('TLPDefaultStateID')
                    if d not in (None, 0):
                        f['default_state'][d] += 1
                    if c.get('TLPImageID') == -1:
                        f['unrasterized'] += 1
        declared = [r for r in lay.get('NonDefaultFontResources') or []
                    if r.get('EmbeddedFileName')]
        if declared:
            try:
                with open_gdl(path) as z:
                    gcp = z.read('ProjectGCP')
                got = gfonts.extract(gcp, declared)
                f['fonts_missing'] = [r['EmbeddedFileName'] for r in declared
                                      if r['EmbeddedFileName'] not in got]
            except Exception as e:                       # noqa: BLE001
                f['fonts_error'] = f'{type(e).__name__}: {e}'
    return f


# -- invariants: (name, fn(F) -> (status, lines)); status PASS / FAIL / INFO ---

def inv_states_countable(F):
    """A button has more than one state, so any loop bounded by a state count
    must use the real one (docs/gdl-format.md: PBStates.Count is not it)."""
    bad = [f"{f['name']}: no button has 2+ states {dict(f['state_counts'])}"
           for f in F if f['state_counts'] and max(f['state_counts']) < 2]
    return ('FAIL' if bad else 'PASS'), bad


def inv_off_on(F):
    """gdl/spec.py names every generated button's states Off/On."""
    total = collections.Counter()
    for f in F:
        total.update(f['state_pairs'])
    n = sum(total.values())
    if not n:
        return 'INFO', ['no two-state buttons']
    share = total[('Off', 'On')] / n
    lines = [f"('Off','On') is {total[('Off','On')]}/{n} = {share:.1%} of two-state buttons"]
    lines += [f'  also: {k} x{v}' for k, v in total.most_common(7) if k != ('Off', 'On')]
    low = sorted(((f['state_pairs'][('Off', 'On')] / sum(f['state_pairs'].values()),
                   f['name']) for f in F if sum(f['state_pairs'].values()) >= 10))[:4]
    lines += [f'  lowest share: {n_} {s:.0%}' for s, n_ in low]
    return ('PASS' if share > 0.8 else 'FAIL'), lines


def inv_popup_size(F):
    """A popup's authored size is its real size; retarget relies on it."""
    bad = [f"{f['name']} {n!r}: authored {a}, built {b}"
           for f in F for n, a, b in f['popup_mismatch']]
    checked = sum(1 for f in F if f['built'])
    return ('FAIL' if bad else 'PASS'), (bad[:12] or [f'{checked} built project(s) checked'])


def inv_default_state(F):
    """TLPDefaultStateID is 0 - which is what made an unwritten state 1 invisible."""
    bad = [f"{f['name']}: {dict(f['default_state'])}" for f in F if f['default_state']]
    return ('FAIL' if bad else 'PASS'), bad[:12]


def inv_unique_names(F):
    """Page and popup names are unique per project; Build refuses duplicates."""
    bad = [f"{f['name']}: {f['dup_names']}" for f in F if f['dup_names']]
    return ('FAIL' if bad else 'PASS'), bad[:12]


def inv_userid(F):
    """userIdField is a UInt16; gdl.spec allocates into it."""
    bad = [f"{f['name']}: max userId {f['max_uid']}" for f in F if f['max_uid'] > 0xFFFF]
    top = max((f['max_uid'], f['name']) for f in F)
    return ('FAIL' if bad else 'PASS'), (bad or [f'highest in corpus: {top[0]} ({top[1]})'])


def inv_caption(F):
    """A button's caption normally lives on its first state (caption_at())."""
    where = collections.Counter()
    for f in F:
        where.update(f['caption_in'])
    n = sum(where.values()) or 1
    lines = [f'{k}: {v} ({v / n:.1%})' for k, v in where.most_common()]
    return ('PASS' if where['state'] >= where['control'] else 'FAIL'), lines


def inv_fonts(F):
    """Every declared face is recoverable (tests/test_fonts.py gates fixtures/)."""
    bad = [f"{f['name']}: extract raised {f['fonts_error']}" for f in F if f['fonts_error']]
    bad += [f"{f['name']}: not recovered {f['fonts_missing'][:4]}"
            for f in F if f['fonts_missing']]
    checked = sum(1 for f in F if f['fonts_missing'] is not None)
    return ('FAIL' if bad else 'PASS'), (bad[:12] or [f'{checked} project(s) checked'])


def inv_canvas(F):
    """Every canvas in the corpus is a model gdl/spec.py can target."""
    from gdl.spec import MODELS
    known = set(MODELS.values())
    bad = [f"{f['name']}: {f['canvas']}" for f in F if f['canvas'] and f['canvas'] not in known]
    return ('FAIL' if bad else 'PASS'), bad


def inv_modal_refs(F):
    """Build adds one full-canvas popup reference per modal popup to every page;
    the Offline Page counts only when EnableOfflinePage is on (docs/gdl-format.md)."""
    lines, bad = [], False
    for f in F:
        if not (f['built'] and f['n_modal']):
            continue
        per = dict(f['fullcanvas_refs'])
        ok = set(per) == {f['n_modal']}
        bad |= not ok
        lines.append(f"{'  ' if ok else '! '}{f['name']}: {f['n_modal']} modal, "
                     f'full-canvas refs per page {per}')
    return ('FAIL' if bad else 'PASS'), lines[:16]


def inv_borders(F):
    """A spec may only name border resources its donor defines - so how portable
    is a spec across themes?"""
    sets = {f['name']: set(f['borders']) for f in F if f['borders']}
    if len(sets) < 2:
        return 'INFO', ['fewer than two projects define borders']
    common = set.intersection(*sets.values())
    lines = [f'{len(sets)} projects; {len(common)} border resource(s) defined by ALL of them']
    lines += [f'  common: {sorted(common)[:8]}'] if common else []
    fams = collections.defaultdict(list)
    for name, s in sets.items():
        fams[name.split()[0]].append(len(s))
    lines += [f'  {k}: {sorted(v)}' for k, v in sorted(fams.items())]
    return 'INFO', lines


def inv_unrasterized(F):
    """Controls Build left at TLPImageID -1. Some are legitimate (the Offline
    Window); a jump in this number is what a broken build looks like."""
    lines = [f"{f['name']}: {f['unrasterized']}" for f in F if f['unrasterized']]
    return 'INFO', lines[:16] or ['none']


INVARIANTS = [
    ('button states are countable', inv_states_countable),
    ('Off/On is the dominant state pair', inv_off_on),
    ('built popup size == authored popup size', inv_popup_size),
    ('TLPDefaultStateID is 0', inv_default_state),
    ('page and popup names unique per project', inv_unique_names),
    ('userId fits in UInt16', inv_userid),
    ('a button caption lives on its state', inv_caption),
    ('every declared face is recoverable', inv_fonts),
    ('canvas matches a known model', inv_canvas),
    ('one full-canvas ref per shown modal popup per page', inv_modal_refs),
    ('border resources shared across themes', inv_borders),
    ('controls left unrasterized by Build', inv_unrasterized),
]


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    if args:
        dirs = args
    else:
        dirs = [os.path.join(REPO, 'fixtures', 'gdl'), SEEDS_DIR]
        if '--no-templates' not in argv:
            dirs.append(TEMPLATES_DIR)
    paths = [p for p in discover(dirs) if usable(p)]
    print(f'scanning {len(paths)} file(s) in: {", ".join(dirs)}', flush=True)

    F = []
    for path in paths:
        try:
            f = facts(path)
        except Exception as e:                           # noqa: BLE001
            print(f'  ! {os.path.basename(path)}: {type(e).__name__}: {e}', flush=True)
            continue
        finally:
            gc.collect()
        F.append(f)
        cv = f"{f['canvas'][0]}x{f['canvas'][1]}" if f['canvas'] else '-'
        print(f"  {f['name'][:44]:<44} {cv:>9} {f['part'] or '':>11} "
              f"{f['n_pages']:>3}pg {f['n_popups']:>3}pop {f['n_controls']:>5}ctl "
              f"{len(f['borders']):>3}bdr  {','.join(f['fonts'])[:60]}", flush=True)
    if not F:
        return 2
    print()
    failed = 0
    for name, fn in INVARIANTS:
        try:
            status, lines = fn(F)
        except Exception as e:                           # noqa: BLE001
            status, lines = 'FAIL', [f'{type(e).__name__}: {e}']
        failed += status == 'FAIL'
        print(f'{status:<5} {name}')
        for line in lines:
            print(f'        {line}')
    held = sum(1 for n, fn in INVARIANTS) - failed
    print(f'\n{failed} FAIL across {len(F)} project(s)'
          f' ({held}/{len(INVARIANTS)} PASS or INFO)')
    return failed


if __name__ == '__main__':
    sys.exit(main(sys.argv))
