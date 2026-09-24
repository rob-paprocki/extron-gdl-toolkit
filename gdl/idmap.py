"""The ID map: every control a program addresses, where it is, and what it does.

A `.gdl` carries no behavior. GUI Designer's previous generation had per-button
actions (`PanelBuilder.PBActionShowPage` and friends), and converting a project
to the current format says so outright - "Local Actions and Audio Resources
will be lost!". What a control does lives in the control program, which finds
the control by its ID. So a panel is handed to its programmer with an ID map:
each addressable control's ID, type, page, name and caption, and what it does.

    python -m gdl.idmap check <spec.json>
    python -m gdl.idmap write <spec.json> <out_dir>

Two optional keys on a control say what it does:

  * `nav` - a button that shows a page or popup. Checked: the target exists,
    a popup can appear over the page that shows it, and every page and popup
    is reachable from the start page.
  * `does` - anything else, in words: "Routes the laptop to the display".

Addressing is the one rule to hold on to. A CONTROL is addressed by its numeric
ID, which survives Build. A PAGE or POPUP is addressed by NAME: its number does
not survive Build - a page authored as 1000 comes back as 51 - so the map never
lists one.

Stdlib only, like everything outside gdl/compose.py. docs/idmap.md has the
vocabulary and every check.
"""
import collections
import csv
import hashlib
import io
import json
import os
import sys

from .spec import Panel

# The kinds a control program can address, as Extron's own libraries name them.
# Everything else - panels, lines, images, clocks, popup references - has no
# object a program can take hold of.
CLASS_OF = {'button': 'Button', 'label': 'Label', 'level': 'Level', 'slider': 'Slider'}
KEYS = ('nav', 'does')


def _cell(s):
    """Text safe inside a Markdown table cell: a `|` would split it."""
    return str(s).replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')


class IdMap:
    """A loaded spec's addressable controls and navigation, checked."""

    def __init__(self, panel, spec_path=None):
        self.panel = panel
        self.spec = panel.spec
        self.spec_path = spec_path
        self.start_page = panel.start_page
        self._problems = []
        self.page_names = [pg['name'] for pg in panel.pages]
        self.popup_by_name = {pu['name']: pu for pu in panel.popups}
        raw_pages = self.spec.get('pages') or []
        raw_popups = self.spec.get('popups') or []
        self.containers = [self._container(pg, 'page', raw_pages[i])
                           for i, pg in enumerate(panel.pages)]
        self.containers += [self._container(pu, 'popup', raw_popups[i])
                            for i, pu in enumerate(panel.popups)]
        self.controls = [self._control(ct, c) for ct in self.containers for c in ct['raw']]
        for ct in self.containers:
            ct['controls'] = [r for r in self.controls if r['container'] == ct['name']]
        # Navigation is only checked once a spec uses it: three unlinked pages
        # in a layout-only spec are a layout, not a broken panel.
        self.uses_nav = any(r['nav'] for r in self.controls) or \
            any(ct['reached_by'] for ct in self.containers)
        does = self.spec.get('does')
        self.panel_does = [does] if isinstance(does, str) else list(does or [])
        if not all(isinstance(d, str) and d.strip() for d in self.panel_does):
            self._problems.append('does at the top of the spec must be a sentence or a list '
                                  'of them')

    # -- reading the spec ----------------------------------------------------
    def _container(self, item, kind, raw):
        rb = raw.get('reached_by')
        if rb not in (None, 'program'):
            self._problems.append(f"{kind} {item['name']!r}: reached_by must be 'program' "
                                  f'(shown by the control program), not {rb!r}')
        return {
            'name': item['name'], 'kind': kind,
            'modal': bool(item.get('modal')) if kind == 'popup' else False,
            'group': item.get('group') if kind == 'popup' else None,
            'reached_by': rb,
            # Popup groups this container shows standard popups through.
            'refs': {c.get('group') for c in item['controls']
                     if c.get('kind') == 'popup_ref' and c.get('group')},
            'raw': item['controls'],
        }

    def _control(self, ct, c):
        kind = c.get('kind', 'panel')
        where = f"{ct['kind']} {ct['name']!r} {c.get('name') or c.get('text') or '?'!r}"
        rec = {'container': ct['name'], 'container_kind': ct['kind'], 'where': where,
               'name': c.get('name') or c.get('text') or kind,
               # What it says when the panel boots: a button with named states
               # shows its first.
               'text': self.panel._default_look(c).get('text') or '',
               'kind': kind, 'id': c['id'], 'nav': None, 'does': None,
               'states': None, 'press': None}
        # A program sets a button's feedback by state index, so the map lists
        # every state in order. A button that asked for none keeps whatever
        # states its donor had, which the spec never named - so none are listed.
        feedback = self.panel._feedback(c)
        if kind == 'button' and feedback:
            names = [s.get('name') for s in feedback]
            if all(isinstance(n, str) for n in names):
                rec['states'] = names
                rec['press'] = names[self.panel._press(c, feedback)]
        used = [k for k in KEYS if k in c]
        if kind not in CLASS_OF:
            if used:
                self._problems.append(f"{where}: a {kind} has no ID a program can address, so "
                                      f"{' and '.join(used)} would go nowhere - only button, "
                                      f'label, level and slider are in the ID map')
            return rec
        if 'does' in c:
            if isinstance(c['does'], str) and c['does'].strip():
                rec['does'] = c['does'].strip()
            else:
                self._problems.append(f"{where}: does must be a sentence, not {c['does']!r}")
        if 'nav' in c:
            t = c['nav']
            if kind != 'button':
                self._problems.append(f'{where}: nav belongs on a button, not a {kind}')
            elif t in self.page_names:
                rec['nav'] = ('page', t)
            elif t in self.popup_by_name:
                rec['nav'] = ('popup', t)
            else:
                self._problems.append(f'{where}: nav target {t!r} is neither a page nor a popup '
                                      f'in this spec')
        return rec

    # -- lookups -------------------------------------------------------------
    def container(self, name):
        return next((ct for ct in self.containers if ct['name'] == name), None)

    def addressed(self):
        """ID -> the records sharing it, for every addressable control."""
        out = collections.OrderedDict()
        for r in self.controls:
            if r['kind'] in CLASS_OF:
                out.setdefault(r['id'], []).append(r)
        return out

    def nav_edges(self):
        """{(from container, to container)} for every page and popup a button shows."""
        return {(r['container'], r['nav'][1]) for r in self.controls if r['nav']}

    def host_pages(self):
        """Container -> the pages it can be showing over.

        A page hosts itself. A popup appears over whichever page is up when it
        is shown, so it inherits the hosts of everything that shows it - and a
        standard popup only on those of them that reference its group. One the
        control program shows (`reached_by: program`) may be over any page.
        """
        pages = [ct['name'] for ct in self.containers if ct['kind'] == 'page']
        hosts = {p: {p} for p in pages}
        for ct in self.containers:
            if ct['kind'] == 'popup':
                wide = set(pages) if ct['reached_by'] == 'program' else set()
                hosts[ct['name']] = self._only_referencing(ct, wide)
        changed = True
        while changed:
            changed = False
            for s, t in self.nav_edges():
                tgt = self.container(t)
                if tgt['kind'] == 'page':
                    continue
                add = self._only_referencing(tgt, hosts.get(s, set()))
                if not add <= hosts[t]:
                    hosts[t] |= add
                    changed = True
        return hosts

    def _only_referencing(self, popup, pages):
        if popup['modal'] or not popup['group']:
            return set(pages)
        return {p for p in pages if popup['group'] in self.container(p)['refs']}

    # -- checks --------------------------------------------------------------
    def check(self):
        """(problems, notes). Problems block `write`, the way they block `plan`."""
        problems = list(self.panel.check()) + list(self._problems)
        notes = []
        problems += self._mirror_rules()
        problems += self._showability_rules()
        p, n = self._graph_rules()
        problems += p
        notes += n
        if any(r['nav'] or r['does'] for r in self.controls):
            for r in self.controls:
                if r['kind'] == 'button' and not r['nav'] and not r['does']:
                    notes.append(f"{r['where']}: its function is not described - the ID map "
                                 f'will list it with none')
        return problems, notes

    def _mirror_rules(self):
        """Controls sharing an ID are ONE control to the program.

        Extron's own projects do it on purpose - Liberty Bank mirrors its
        shutdown confirm and cancel (81, 82) across two popups - so it is
        allowed, but every copy has to be the same kind doing the same thing.
        """
        out = []
        by_id = collections.OrderedDict()
        for r in self.controls:
            by_id.setdefault(r['id'], []).append(r)
        for uid, recs in by_id.items():
            if len(recs) < 2:
                continue
            kinds = {r['kind'] for r in recs}
            if len(kinds) > 1:
                out.append(f"ID {uid} is shared by a {' and a '.join(sorted(kinds))} - a mirror "
                           f"must be the same kind: {', '.join(r['where'] for r in recs)}")
                continue
            if len({(r['nav'], r['does']) for r in recs}) > 1 and kinds & set(CLASS_OF):
                out.append(f'ID {uid} is mirrored with different functions - a program sees one '
                           f"control per ID: {', '.join(r['where'] for r in recs)}")
            # Checked separately: a copy that differs in both must be told both.
            if len({tuple(r['states'] or ()) for r in recs}) > 1:
                # GUI Designer's own help: "The same control states are added
                # to all objects sharing an ID."
                out.append(f'ID {uid} is mirrored with different states - a program sets one '
                           f"state for every copy: {', '.join(r['where'] for r in recs)}")
        return out

    def _showability_rules(self):
        """A standard popup appears only through a reference to its group on the
        page beneath - for a popup shown from another popup, every page that
        one can be showing over."""
        out = []
        hosts = self.host_pages()
        for r in self.controls:
            if not r['nav'] or r['nav'][0] != 'popup':
                continue
            pu = self.popup_by_name[r['nav'][1]]
            if pu['modal'] or not pu['group']:
                continue
            lacking = sorted(p for p in hosts.get(r['container'], ())
                             if pu['group'] not in self.container(p)['refs'])
            if lacking:
                out.append(f"{r['where']}: shows popup {pu['name']!r}, but page"
                           f"{'s' if len(lacking) > 1 else ''} "
                           f"{', '.join(repr(p) for p in lacking)} beneath it "
                           f"{'have' if len(lacking) > 1 else 'has'} no reference to its group "
                           f"{pu['group']!r}, so it would not appear there")
        return out

    def _graph_rules(self):
        problems, notes = [], []
        if not self.uses_nav:
            return problems, notes
        edges = self.nav_edges()
        roots = {self.start_page} if self.start_page else set()
        roots |= {ct['name'] for ct in self.containers if ct['reached_by'] == 'program'}
        seen, todo = set(), list(roots)
        while todo:
            n = todo.pop()
            if n in seen:
                continue
            seen.add(n)
            todo += [t for s, t in edges if s == n]
        for ct in self.containers:
            if ct['name'] not in seen:
                problems.append(f"{ct['kind']} {ct['name']!r} is never shown: no nav leads to it "
                                f"from the start page. Add one, or mark it reached_by: 'program' "
                                f'if the control program shows it')
        pages = [ct['name'] for ct in self.containers if ct['kind'] == 'page']
        if len(pages) > 1:
            for pg in pages:
                reach, todo = set(), [pg]
                while todo:
                    n = todo.pop()
                    if n in reach:
                        continue
                    reach.add(n)
                    todo += [t for s, t in edges if s == n]
                if not (reach - {pg}) & set(pages):
                    notes.append(f'page {pg!r} is a dead end: no nav on it, or on a popup it '
                                 f'shows, leads to another page')
        return problems, notes

    # -- the map ---------------------------------------------------------------
    def _spec_sha(self):
        if self.spec_path and os.path.exists(self.spec_path):
            with open(self.spec_path, 'rb') as fh:
                return hashlib.sha256(fh.read()).hexdigest()
        return hashlib.sha256(json.dumps(self.spec, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def function(r):
        """What a control does, in words."""
        parts = []
        if r['nav']:
            parts.append(f"Shows {r['nav'][0]} {r['nav'][1]!r}")
        if r['does']:
            parts.append(r['does'])
        return '; '.join(parts)

    def data(self):
        edges = sorted(self.nav_edges())
        shown_from = collections.defaultdict(list)
        for s, t in edges:
            shown_from[t].append(s)
        controls = []
        for uid, recs in self.addressed().items():
            r = recs[0]
            row = {
                'id': uid, 'type': CLASS_OF[r['kind']],
                'at': [{'container': x['container'], 'name': x['name'], 'caption': x['text']}
                       for x in recs],
                'nav': {'kind': r['nav'][0], 'target': r['nav'][1]} if r['nav'] else None,
                'does': r['does'],
                'function': self.function(r),
            }
            if r['kind'] == 'button':
                # Index = position = the number the program sets. `press` is
                # the state shown while the button is held.
                row['states'] = r['states']
                row['press'] = r['press']
            controls.append(row)
        return {
            'generated_by': 'gdl.idmap',
            'spec': os.path.basename(self.spec_path) if self.spec_path else None,
            'spec_sha256': self._spec_sha(),
            'start_page': self.start_page,
            'panel': self.panel_does,
            'pages': [{'name': ct['name'], 'reached_by': ct['reached_by'],
                       'shown_from': shown_from[ct['name']]}
                      for ct in self.containers if ct['kind'] == 'page'],
            'popups': [{'name': ct['name'], 'modal': ct['modal'], 'group': ct['group'],
                        'reached_by': ct['reached_by'], 'shown_from': shown_from[ct['name']]}
                       for ct in self.containers if ct['kind'] == 'popup'],
            'controls': controls,
            'navigation': [list(e) for e in edges],
        }

    def write(self, out_dir):
        """idmap.json, idmap.md and idmap.csv. Returns the paths written."""
        os.makedirs(out_dir, exist_ok=True)
        d = self.data()
        out = []
        for name, text in (('idmap.json', json.dumps(d, indent=1, ensure_ascii=False) + '\n'),
                           ('idmap.md', self._markdown(d)),
                           ('idmap.csv', self._csv(d))):
            path = os.path.join(out_dir, name)
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(text)
            out.append(path)
        return out

    @staticmethod
    def states(c):
        """'0 Off, 1 On' - each state's index, which is what a program sets,
        and its name."""
        return ', '.join(f'{i} {n}' for i, n in enumerate(c.get('states') or []))

    @classmethod
    def _csv(cls, d):
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\n')
        w.writerow(['ID', 'Type', 'Page', 'Control', 'Caption', 'States', 'Press', 'Function'])
        for c in d['controls']:
            w.writerow([c['id'], c['type'],
                        '; '.join(a['container'] for a in c['at']),
                        '; '.join(a['name'] for a in c['at']),
                        c['at'][0]['caption'], cls.states(c), c.get('press') or '',
                        c['function']])
        return buf.getvalue()

    def _markdown(self, d):
        out = [f"# ID map: {self.spec.get('name') or d['spec'] or 'panel'}", '',
               f"Generated by `python -m gdl.idmap write` from `{d['spec']}` "
               f"(spec sha256 `{d['spec_sha256'][:12]}`). Regenerate rather than edit.", '',
               'Controls are addressed by **ID**. Pages and popups are addressed by **name** - '
               "Build does not keep a page's number.", '',
               f"The panel boots into **{_cell(d['start_page'])}**."]
        if d['panel']:
            out += ['', '**Panel-wide:**', ''] + [f'- {x}' for x in d['panel']]
        out += ['', '## Pages and popups', '', '| Name | Kind | Shown by |', '|---|---|---|']
        for pg in d['pages']:
            by = (['boot'] if pg['name'] == d['start_page'] else []) + pg['shown_from']
            if pg['reached_by'] == 'program':
                by.append('**the program**')
            out.append(f"| {_cell(pg['name'])} | page | {_cell(', '.join(by)) or '-'} |")
        for pu in d['popups']:
            kind = 'modal popup' if pu['modal'] else f"popup, group {pu['group']}"
            by = list(pu['shown_from'])
            if pu['reached_by'] == 'program':
                by.append('**the program**')
            out.append(f"| {_cell(pu['name'])} | {_cell(kind)} | {_cell(', '.join(by)) or '-'} |")
        out += ['', '## Controls', '',
                'A button\'s **States** are numbered as the program sets them; a button with '
                'none listed keeps the states of the button it was cloned from.', '',
                '| ID | Type | Where | Caption | States | Function |',
                '|---|---|---|---|---|---|']
        for c in d['controls']:
            where = '; '.join(f"{a['container']} / {a['name']}" for a in c['at'])
            st = self.states(c)
            if st and c.get('press'):
                st += f" (press: {c['press']})"
            out.append(f"| {c['id']} | {c['type']} | {_cell(where)} | "
                       f"{_cell(c['at'][0]['caption'])} | {_cell(st) or '-'} | "
                       f"{_cell(c['function']) or '-'} |")
        return '\n'.join(out) + '\n'


def load(path):
    return IdMap(Panel.load(path), spec_path=path)


def main(argv):
    if len(argv) < 3 or argv[1] not in ('check', 'write') or \
            (argv[1] == 'write' and len(argv) < 4):
        print(__doc__.strip().split('\n\n')[0])
        print('\n  python -m gdl.idmap check <spec.json>'
              '\n  python -m gdl.idmap write <spec.json> <out_dir>')
        return 2
    m = load(argv[2])
    problems, notes = m.check()
    for p in problems:
        print('  ' + p)
    for n in notes:
        print('  note: ' + n)
    if argv[1] == 'check':
        print(f'{len(problems)} problem(s), {len(notes)} note(s); '
              f'{len(m.addressed())} addressable control(s), '
              f'{len(m.nav_edges())} navigation link(s)')
        return 1 if problems else 0
    if problems:
        print(f'{len(problems)} problem(s) - nothing written')
        return 1
    for w in m.write(argv[3]):
        print(f'  wrote {w}')
    print(f'{len(m.addressed())} control(s) mapped -> {argv[3]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
