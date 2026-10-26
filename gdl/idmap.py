"""The ID map: every control a program addresses, where it is, and what it does.

A `.gdl` carries no behavior. GUI Designer's previous generation had per-button
actions (`PanelBuilder.PBActionShowPage` and friends), and converting a project
to the current format says so outright - "Local Actions and Audio Resources
will be lost!". What a control does lives in the control program, which finds
the control by its ID. So a panel is handed to its programmer with an ID map:
each addressable control's ID, type, page, name and caption, and what it does.

    python -m gdl.idmap check <spec.json>
    python -m gdl.idmap write <spec.json> <out_dir> [--previous <map>]
    python -m gdl.idmap write-panels <specs dir> <out_dir> [--previous <map>]   # one map
    python -m gdl.idmap from-built <panel.gdl> <out_dir>     # a panel that was never a spec
    python -m gdl.idmap diff <old map> <new map>             # what a program meets

A revised canvas translated with the previous delivery's map (gdl.design
translate --previous) keeps every ID that map gave; written with the same map
(--previous), the map has changes.md and changes.json beside it - what was
added, removed, renamed or renumbered, and whether a program written against
the previous map needs any change.

A canvas built for several panels (docs/claude-design.md) has one spec per panel
and ONE map: a row per ID, and where the control is on each panel - the program
that drives them is one program. What a panel's layout added (Previous, Next,
Back, a level's Up and Down) is in it too, marked derived: a .gdl carries no
behaviour, so the program handles those buttons like any other.

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
import zipfile

from .spec import Panel, panel_id

# The kinds a control program can address, as Extron's own libraries name them.
# Everything else - panels, lines, images, clocks, popup references - has no
# object a program can take hold of.
CLASS_OF = {'button': 'Button', 'label': 'Label', 'level': 'Level', 'slider': 'Slider'}
KEYS = ('nav', 'does')


def _cell(s):
    """Text safe inside a Markdown table cell: a `|` would split it."""
    return _flat(s).replace('|', '\\|')


def _flat(s):
    """A caption on one line: a spreadsheet shows a cell holding a line break
    as two rows' worth of one row. The JSON keeps the break - it is what the
    panel draws."""
    return str(s).replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')


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
        # What the page is for - a Page's `does` on a canvas.
        does = raw.get('does')
        if does is not None and not (isinstance(does, str) and does.strip()):
            self._problems.append(f"{kind} {item['name']!r}: does must be a sentence saying what it "
                                  f'is for, not {does!r}')
        return {
            'name': item['name'], 'kind': kind,
            'does': does.strip() if isinstance(does, str) and does.strip() else None,
            'modal': bool(item.get('modal')) if kind == 'popup' else False,
            'group': item.get('group') if kind == 'popup' else None,
            'reached_by': rb,
            # Popup groups this container shows standard popups through.
            'refs': {c.get('group') for c in item['controls']
                     if c.get('kind') == 'popup_ref' and c.get('group')},
            'raw': item['controls'],
        }

    def _caption(self, c):
        """What a control says when the panel boots. An icon by its name: its
        caption is the glyph, a private-use character a spreadsheet shows
        blank."""
        st = c.get('states') if c.get('kind') == 'button' else None
        s0 = st[0] if isinstance(st, list) and st and isinstance(st[0], dict) else {}
        icon = s0['icon'] if 'icon' in s0 else None if 'text' in s0 else c.get('icon')
        if icon is not None:
            return f'icon: {icon}'
        return self.panel._default_look(c).get('text') or ''

    def _control(self, ct, c):
        kind = c.get('kind', 'panel')
        where = f"{ct['kind']} {ct['name']!r} {c.get('name') or c.get('text') or '?'!r}"
        rec = {'container': ct['name'], 'container_kind': ct['kind'], 'where': where,
               'name': c.get('name') or c.get('text') or kind,
               # What it says when the panel boots: a button with named states
               # shows its first.
               'text': self._caption(c),
               'kind': kind, 'id': c['id'], 'nav': None, 'does': None,
               'states': None, 'press': None,
               # Added by the panel's layout, not drawn on the canvas.
               'derived': bool(c.get('derived'))}
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

        Real projects do it on purpose - the client project mirrors its
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
    def panel_name(self):
        """The panel the spec is laid out for (gdl.spec.panel_id) - None where
        it names no model, or one that does not run at its size."""
        try:
            return panel_id(self.spec['model'], self.panel.size) if self.spec.get('model') else None
        except (KeyError, TypeError, ValueError):
            return None

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
            # A copy a layout derived where another holds the ID (Shockwave's
            # tab twin, the caption under the 1035's tab) is the control's
            # mirror: one of its places, marked, and the row is the control's.
            own = any(not x['derived'] for x in recs)
            row = {
                'id': uid, 'type': CLASS_OF[r['kind']],
                'at': [dict({'container': x['container'], 'name': x['name'], 'caption': x['text']},
                            **({'mirror': True} if own and x['derived'] else {}))
                       for x in recs],
                'nav': {'kind': r['nav'][0], 'target': r['nav'][1]} if r['nav'] else None,
                'does': r['does'],
                'function': self.function(r),
            }
            if not own:
                row['derived'] = True
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
            # The panel it is of: a revision's changes compare it with the
            # previous map's view of that panel where that map is of several.
            'model': self.panel_name(),
            'start_page': self.start_page,
            'panel': self.panel_does,
            'pages': [{'name': ct['name'], 'reached_by': ct['reached_by'],
                       'shown_from': shown_from[ct['name']], 'does': ct['does']}
                      for ct in self.containers if ct['kind'] == 'page'],
            'popups': [{'name': ct['name'], 'modal': ct['modal'], 'group': ct['group'],
                        'reached_by': ct['reached_by'], 'shown_from': shown_from[ct['name']],
                        'does': ct['does']}
                       for ct in self.containers if ct['kind'] == 'popup'],
            'controls': controls,
            'navigation': [list(e) for e in edges],
            # IDs an earlier delivery gave controls that are gone, which
            # translate --previous keeps out of use (`_retired`): the next
            # revision reads them here and keeps them out too.
            'retired': [{'id': r['id'], 'was': r.get('was') or ''}
                        for r in self.spec.get('_retired') or []],
        }

    def write(self, out_dir, previous=None):
        """idmap.json, idmap.md and idmap.csv - and with the previous
        delivery's map (load_previous), changes.md and changes.json. Returns
        the paths written."""
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
        if previous is not None:
            out += write_changes(out_dir, previous, d, self.spec.get('name') or d['spec'] or 'panel')
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
                        _flat(c['at'][0]['caption']), cls.states(c), c.get('press') or '',
                        c['function']])
        return buf.getvalue()

    def _markdown(self, d):
        return '\n'.join([f"# ID map: {self.spec.get('name') or d['spec'] or 'panel'}", '',
                          f"Generated by `python -m gdl.idmap write` from `{d['spec']}` "
                          f"(spec sha256 `{d['spec_sha256'][:12]}`). Regenerate rather than edit."]
                         + self._tables(d)) + '\n'

    @classmethod
    def _tables(cls, d, built=False):
        """The map below its title: how it is addressed, and its tables.
        `built` for a map read off a build, which names every button's states
        and may say less than a spec - no start page, a popup in no group."""
        out = ['', 'Controls are addressed by **ID**. Pages and popups are addressed by **name** - '
               "Build does not keep a page's number.", '',
               f"The panel boots into **{_cell(d['start_page'])}**." if d['start_page'] is not None
               else 'The build names no page among its own to boot into.']
        if d['panel']:
            out += ['', '**Panel-wide:**', ''] + [f'- {x}' for x in d['panel']]
        out += ['', '## Pages and popups', ''] + _containers_table(d, d['start_page'])
        out += ['', '## Controls', '',
                'A button\'s **States** are numbered as the program sets them' +
                ('.' if built else '; a button with none listed keeps the states of the button '
                                   'it was cloned from.'), '',
                '| ID | Type | Where | Caption | States | Function |',
                '|---|---|---|---|---|---|']
        for c in d['controls']:
            where = '; '.join(f"{a['container']} / {a['name']}" for a in c['at'])
            st = cls.states(c)
            if st and c.get('press'):
                st += f" (press: {c['press']})"
            out.append(f"| {c['id']} | {c['type']} | {_cell(where)} | "
                       f"{_cell(c['at'][0]['caption'])} | {_cell(st) or '-'} | "
                       f"{_cell(c['function']) or '-'} |")
        return out + _retired_table(d)


def _containers_table(d, start):
    """The pages-and-popups table: each one's kind, how it is shown, and what
    it is for (a Page's `does`)."""
    out = ['| Name | Kind | Shown by | Purpose |', '|---|---|---|---|']
    for pg in d['pages']:
        by = (['boot'] if pg['name'] == start else []) + pg['shown_from']
        if pg['reached_by'] == 'program':
            by.append('**the program**')
        out.append(f"| {_cell(pg['name'])} | page | {_cell(', '.join(by)) or '-'} | "
                   f"{_cell(pg.get('does') or '-')} |")
    for pu in d['popups']:
        kind = ('modal popup' if pu['modal'] else 'popup, no group' if pu['group'] is None
                else f"popup, group {pu['group']}")
        by = list(pu['shown_from'])
        if pu['reached_by'] == 'program':
            by.append('**the program**')
        out.append(f"| {_cell(pu['name'])} | {_cell(kind)} | {_cell(', '.join(by)) or '-'} | "
                   f"{_cell(pu.get('does') or '-')} |")
    return out


def _retired_table(d):
    if not d.get('retired'):
        return []
    return ['', '## Retired IDs', '',
            'An earlier delivery gave these IDs to controls that are gone. No control has one, so a '
            'program still addressing it reaches nothing rather than another control; the next '
            'revision keeps them out of use too.', '',
            '| ID | Was |', '|---|---|'] + [f"| {r['id']} | {_cell(r['was']) or '-'} |" for r in d['retired']]


# The classes a program addresses, by the Type a built layout.json gives a
# control (tests/verify_built.py TYPE_NAME has the rest).
BUILT_CLASS = {7: 'Button', 9: 'Level', 11: 'Label', 27: 'Slider'}


class BuiltMap:
    """The ID map of a panel that was never a spec, read off its build.

    A built layout.json holds every ID, type, page, popup and nearly every
    caption a map needs. The rest are only in the project beside it, so that is
    read too: a popup group's name, and a caption Build flattened into the
    control's artwork. GUI Designer's Offline Page is its own and is left out,
    as a spec's map leaves it. What a control does lives in the control
    program, not in the .gdl, so every Function is the programmer's to fill in.
    A control whose ID is 0 - GUI Designer's for one nobody numbered, 98 controls
    in the client fixture, 59 of them buttons - is left out and counted: nothing
    can address it.
    """

    def __init__(self, layout, groups=None, name='panel', sha256='', captions=None):
        self.layout = layout
        self.groups = dict(groups or {})
        self.name = name
        self.sha256 = sha256
        # {(kind, page or popup name, control ID): caption}, the project's.
        self.captions = dict(captions or {})

    @classmethod
    def open(cls, path):
        """Off a built .gdl: its layout.json, its popup groups' names and its
        controls' captions."""
        from .container import open_payload
        from .project import Project
        layout = json.loads(open_payload(path).read('layout.json'))
        proj = Project.open(path)
        top = next(proj.instances('PBProject'), None)
        groups = proj.items(proj.field(top, 'popupPageGroupsField')) if top else []
        captions = {}
        for pg in proj.pages():
            for c in pg['controls']:
                # As layout.json orders them: the first state's, else its own.
                text = (c['states'][0]['caption'] if c['states'] else None) or c['text']
                if text:
                    captions[(pg['kind'], pg['name'], c['obj_id'])] = text
        with open(path, 'rb') as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        return cls(layout, {proj.field(g, 'idField'): proj.field(g, 'nameField') for g in groups},
                   os.path.basename(path), sha, captions)

    @staticmethod
    def _caption(c, flat=None):
        """What a control says when the panel boots: its first state's text -
        or, where Build flattened that into the control's artwork and left
        layout.json's empty, the project's (`flat`): 71 of the Afterburn 1035
        seed's 365 IDs, 23 of the client fixture's. A glyph by its name in its
        face, as a spec's map names its icon (or its codepoint where the face
        names none): it is a private-use character a spreadsheet shows blank -
        Afterburn's 1035 seed has 30 controls of them - or, in Extron-Shockwave,
        a Latin-1 one that is not what it draws."""
        from .fonts import ICON_FONTS
        text = (c.get('States') or [{}])[0].get('Text') or c.get('Text') or ''
        if not text and c.get('FlattenText'):
            text = flat or ''
        font = (c.get('Font') or {}).get('Name')
        icon_face = font and font in {f for f in ICON_FONTS.values() if f}
        if not text or not (icon_face or all(0xE000 <= ord(ch) <= 0xF8FF for ch in text)):
            return text
        from .spec import glyph_names
        named = {cp: n for n, cp in (glyph_names(font) or {}).items()} if font else {}
        return 'icon: ' + ' '.join(named.get(ord(ch), f'U+{ord(ch):04X}') for ch in text)

    @staticmethod
    def _look(c):
        """What a program sets on one copy of an ID: (type, its states in
        index order, its press state) - the states and press a button's."""
        names, press = [], None
        if BUILT_CLASS[c['Type']] == 'Button':
            # The press state is an index, as a plan writes it.
            names = [s.get('Name') for s in c.get('States') or []]
            i = c.get('TLPPressFeedbackStateID')
            press = names[i] if isinstance(i, int) and 0 <= i < len(names) else None
        return BUILT_CLASS[c['Type']], names, press

    @classmethod
    def _say(cls, c):
        kind, names, press = cls._look(c)
        return ', '.join([kind] + ([f"states {IdMap.states({'states': names})}"] if names else [])
                         + ([f'press {press}'] if press else []))

    def data(self):
        j = self.layout
        pages = list(j.get('Pages') or [])
        popups = [p for p in j.get('PopupPages') or [] if p.get('ID') != j.get('OfflinePageID')]
        at = collections.OrderedDict()
        unnumbered = 0
        for kind, items in (('page', pages), ('popup', popups)):
            for item in items:
                for c in item.get('Controls') or []:
                    if c.get('Type') not in BUILT_CLASS:
                        continue
                    if not c.get('UserId'):
                        unnumbered += 1
                        continue
                    at.setdefault(c.get('UserId'), []).append((kind, item, c))
        controls, notes = [], []
        for uid, recs in at.items():
            c = recs[0][2]
            row = {'id': uid, 'type': BUILT_CLASS[c['Type']],
                   'at': [{'container': item.get('Name'), 'name': x.get('Name') or '',
                           'caption': self._caption(x, self.captions.get((kind, item.get('Name'),
                                                                          x.get('ID'))))}
                          for kind, item, x in recs],
                   'nav': None, 'does': None, 'function': ''}
            _, names, press = self._look(c)
            if row['type'] == 'Button':
                row['states'] = names or None
                row['press'] = press
            # One row an ID, from its first copy: a program setting a state by
            # index needs to know where another copy numbers them otherwise -
            # the client fixture's ID 171 has 'Level 3_1' on one page and
            # 'Level 1' on another.
            odd = [(item, x) for _, item, x in recs[1:] if self._look(x) != self._look(c)]
            if odd:
                notes.append(f"ID {uid}'s copies differ, and the map lists the first: " + '; '.join(
                    f"{item.get('Name')} / {x.get('Name') or ''} - {self._say(x)}"
                    for item, x in [(recs[0][1], c)] + odd))
            controls.append(row)
        return {
            'generated_by': 'gdl.idmap',
            'built': self.name,
            'built_sha256': self.sha256,
            'start_page': next((p.get('Name') for p in pages if p.get('ID') == j.get('DefaultPage')), None),
            'panel': notes,
            'pages': [{'name': p.get('Name'), 'reached_by': None, 'shown_from': []} for p in pages],
            'popups': [{'name': p.get('Name'), 'modal': bool(p.get('Modal')),
                        'group': self.groups.get(p.get('GroupID')) if p.get('IsGroupValid') else None,
                        'reached_by': None, 'shown_from': []} for p in popups],
            'controls': controls,
            'navigation': [],
            'unnumbered': unnumbered,
        }

    def write(self, out_dir):
        """idmap.json, idmap.md and idmap.csv. Returns the paths written."""
        os.makedirs(out_dir, exist_ok=True)
        d = self.data()
        head = [f"# ID map: {d['built']}", '',
                f"Read by `python -m gdl.idmap from-built` off the built `{d['built']}` "
                f"(sha256 `{d['built_sha256'][:12]}`). A `.gdl` carries no behavior, so "
                'what each control does - its Function - is the programmer\'s to fill in.']
        if d['unnumbered']:
            n = d['unnumbered']
            head += ['', f"{n} control{' carries' if n == 1 else 's carry'} no ID (0) and "
                         f"{'is' if n == 1 else 'are'} left out: nothing can address "
                         f"{'it' if n == 1 else 'them'}."]
        md = '\n'.join(head + IdMap._tables(d, built=True)) + '\n'
        out = []
        for name, text in (('idmap.json', json.dumps(d, indent=1, ensure_ascii=False) + '\n'),
                           ('idmap.md', md), ('idmap.csv', IdMap._csv(d))):
            path = os.path.join(out_dir, name)
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(text)
            out.append(path)
        return out


# -- one map for every panel a canvas builds -----------------------------------
def combine(maps):
    """One map for {panel: IdMap} (gdl.spec.panel_id), the first the panel the
    canvas is drawn on: its pages, popups and navigation at the top, as a single
    panel's are, and
    each panel's own under `panels`; every control once, with where it is on
    each panel under `panels`."""
    models = list(maps)
    per = {m: maps[m].data() for m in models}
    first = per[models[0]]
    out = dict(first)
    # Each panel is named under `panels`: a map of several is no one's.
    out.pop('model', None)
    out['panels'] = [{'model': m, 'size': list(maps[m].panel.size),
                      'tier': _tier(maps[m].spec.get('model')),
                      'spec_sha256': per[m]['spec_sha256'], 'start_page': per[m]['start_page'],
                      'pages': per[m]['pages'], 'popups': per[m]['popups'],
                      'navigation': per[m]['navigation']} for m in models]
    rows = collections.OrderedDict()
    for m in models:
        for c in per[m]['controls']:
            row = rows.setdefault(c['id'], dict(c, panels={}, types={}, functions={}))
            row['panels'][m] = c['at']
            row['types'][m] = c['type']
            row['functions'][m] = c['function']
            if c.get('derived'):
                row['derived'] = True
    for row in rows.values():
        # The same type everywhere is said once; a slider that is a level on a
        # panel whose seed cannot build one says which panels.
        if len(set(row['types'].values())) == 1:
            del row['types']
        # And what it does: a Group's Next shows a popup on a mid-size panel
        # and a page on a small one, and the row said the first panel's for
        # both.
        if len(set(row['functions'].values())) == 1:
            del row['functions']
        else:
            row['function'] = '; '.join(f'{m}: {f}' for m, f in row['functions'].items())
    # By ID, which is how a programmer looks a control up: in the order first
    # met, each panel's derived controls came after the first panel's.
    out['controls'] = sorted(rows.values(), key=lambda r: r['id'])
    return out


def _tier(model):
    from .spec import tier
    try:
        return tier(model) if model else None
    except KeyError:
        return None


def check_panels(maps):
    """Problems across the panels: each panel's own checks, and one ID meaning
    one control on every panel. A control the canvas drew is on every panel -
    nothing is dropped - but where that panel's layout named it as left off
    (a page's `left`: a hub's footer clock, which its template has no place
    for); what a layout added is on the panels that added it."""
    models = list(maps)
    out = []
    for m in models:
        out += [f'{m}: {p}' for p in maps[m].check()[0]]
    seen = collections.OrderedDict()
    for m in models:
        for uid, recs in maps[m].addressed().items():
            seen.setdefault(uid, {})[m] = recs
    for uid, by in seen.items():
        # What a layout added is on the panels that added it - but a mirror it
        # drew of a canvas control (docs/idmap.md Mirrors) does not make the
        # control one: the control is held to every panel, and is the ID's
        # name on each.
        derived = all(r['derived'] for recs in by.values() for r in recs)
        first = {m: next((r for r in recs if not r['derived']), recs[0]) for m, recs in by.items()}
        ref = next(iter(first.values()))
        for m, recs in by.items():
            r = first[m]
            # A slider is a level on a panel whose seed cannot clone a slider
            # (its series' `kinds` in the profile say which): one control to the
            # program, which sets its level the same way on both.
            same = r['kind'] == ref['kind'] or {r['kind'], ref['kind']} == {'slider', 'level'}
            if r['name'] != ref['name'] or not same:
                out.append(f"ID {uid} is {ref['kind']} {ref['name']!r} on the {next(iter(by))} and "
                           f"{r['kind']} {r['name']!r} on the {m} - one ID is one control to the program")
            # The map numbers a control's states once, for every panel: a
            # source's tab on the 1035 and its tile in a hub's Select a Source
            # are one control, and must name their states alike.
            elif (r['states'] or None) != (ref['states'] or None):
                out.append(f"ID {uid} ({ref['name']!r}) has states {ref['states']} on the {next(iter(by))} and "
                           f"{r['states']} on the {m} - the map numbers a control's states once")
        if not derived:
            for m in models:
                left = {n for it in (maps[m].spec.get('pages') or []) + (maps[m].spec.get('popups') or [])
                        for n in it.get('left') or ()}
                if m not in by and ref['name'] not in left:
                    out.append(f"ID {uid} ({ref['name']!r}) is not on the {m} - a control the canvas "
                               'draws is on every panel')
    return out


def panel_view(m, model):
    """A map of every panel, as one panel's own: its pages, popups, navigation
    and the controls on it, each where it is on that panel."""
    p = next((x for x in m.get('panels') or [] if x['model'] == model), None)
    if p is None:
        raise ValueError(f"the map has no panel {model!r} - it has "
                         f"{', '.join(x['model'] for x in m.get('panels') or []) or 'none'}")
    view = {k: v for k, v in m.items() if k not in ('panels', 'controls')}
    view.update(start_page=p['start_page'], pages=p['pages'], popups=p['popups'],
                navigation=p['navigation'])
    # Its type and function on this panel: a row says each once where every
    # panel agrees, and each panel's where they do not.
    view['controls'] = [dict({k: v for k, v in c.items() if k not in ('panels', 'types', 'functions')},
                             at=c['panels'][model], type=(c.get('types') or {}).get(model, c['type']),
                             function=(c.get('functions') or {}).get(model, c.get('function')))
                        for c in m['controls'] if model in c.get('panels', {})]
    return view


def write_panels(maps, out_dir, previous=None):
    """idmap.json, idmap.md and idmap.csv for every panel at once - and with
    the previous delivery's map (load_previous), changes.md and changes.json."""
    os.makedirs(out_dir, exist_ok=True)
    d = combine(maps)
    models = list(maps)
    first = maps[models[0]]
    out = []
    for name, text in (('idmap.json', json.dumps(d, indent=1, ensure_ascii=False) + '\n'),
                       ('idmap.md', _panels_markdown(first, d, models)),
                       ('idmap.csv', _panels_csv(d, models))):
        path = os.path.join(out_dir, name)
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        out.append(path)
    if previous is not None:
        out += write_changes(out_dir, previous, d, first.spec.get('name') or 'panel')
    return out


def _type(c):
    """'Slider' - or 'Slider; Level on TLP525T, TLP320M' where a panel's seed
    makes it something else."""
    types = c.get('types')
    if not types:
        return c['type']
    first = next(iter(types.values()))
    other = collections.defaultdict(list)
    for m, t in types.items():
        if t != first:
            other[t].append(m)
    return '; '.join([first] + [f"{t} on {', '.join(ms)}" for t, ms in other.items()])


def _where(c, model, name):
    """Where the control is on `model`: each copy's page or popup, and its
    own name where it is not the row's `name` - a mirror's, or a copy the
    designer named otherwise (the client's Room Off on a second popup)."""
    at = c['panels'].get(model)
    return '; '.join(a['container'] + (f" (mirror: {a['name']})" if a.get('mirror') else
                                       f" ({a['name']})" if a['name'] != name else '')
                     for a in at) if at else '-'


def _panels_csv(d, models):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(['ID', 'Type', 'Control'] + models + ['Caption', 'States', 'Press', 'Function', 'Derived'])
    for c in d['controls']:
        at = next(iter(c['panels'].values()))
        w.writerow([c['id'], _type(c), at[0]['name']] + [_where(c, m, at[0]['name']) for m in models]
                   + [_flat(at[0]['caption']), IdMap.states(c), c.get('press') or '', c['function'],
                      'yes' if c.get('derived') else ''])
    return buf.getvalue()


def _panels_markdown(first, d, models):
    out = [f"# ID map: {first.spec.get('name') or 'panel'}, every panel", '',
           f"Generated by `python -m gdl.idmap write-panels` from one spec per panel "
           f"({', '.join(models)}). Regenerate rather than edit.", '',
           'One program drives every panel: a control has **one ID on every panel**, wherever '
           "that panel's layout put it. Pages and popups are addressed by **name**.", '',
           '**Derived** controls are navigation a panel\'s layout added - Previous, Next, Back, '
           "a group's button, a level's Up and Down. The panel does nothing by itself: the "
           'program shows the page or popup each one names, on the panels that have it.']
    for p in d['panels']:
        out += ['', f"## {p['model']} ({p['size'][0]}x{p['size'][1]}, tier {p['tier'] or '-'})", '',
                f"Boots into **{_cell(p['start_page'])}**.", ''] + _containers_table(p, p['start_page'])
    out += ['', '## Controls', '',
            '| ID | Type | Control | ' + ' | '.join(models) + ' | Caption | States | Function |',
            '|' + '---|' * (len(models) + 6)]
    for c in d['controls']:
        at = next(iter(c['panels'].values()))
        st = IdMap.states(c)
        if st and c.get('press'):
            st += f" (press: {c['press']})"
        name = at[0]['name'] + (' *(derived)*' if c.get('derived') else '')
        out.append(f"| {c['id']} | {_cell(_type(c))} | {_cell(name)} | "
                   + ' | '.join(_cell(_where(c, m, at[0]['name'])) for m in models)
                   + f" | {_cell(at[0]['caption'])} | {_cell(st) or '-'} | {_cell(c['function']) or '-'} |")
    return '\n'.join(out + _retired_table(d)) + '\n'


def load_panels(folder):
    """{panel: IdMap} for every <folder>/<panel>/spec.json, the panel the canvas
    is drawn on first (the one each spec's Page listed first)."""
    found = {}
    for name in sorted(os.listdir(folder)):
        f = os.path.join(folder, name, 'spec.json')
        if os.path.isfile(f):
            found[name] = load(f)
    # The canvas's own list, which every spec carries: a listed panel with no
    # spec was dropped from the map without a word, and the build then claimed
    # every panel. Specs that disagree are from two translates.
    lists = {tuple(m.spec.get('_panels') or ()) for m in found.values()}
    lists.discard(())
    if len(lists) > 1:
        raise ValueError(f'the specs under {folder} list different panels {sorted(lists)} - '
                         'translate the canvas there again')
    if not lists:
        return found
    order = list(next(iter(lists)))
    missing = [m for m in order if m not in found]
    if missing:
        raise ValueError(f"no spec for {', '.join(missing)} under {folder}, which the canvas "
                         'lists - translate it there again')
    return {k: found[k] for k in order}


def load(path):
    return IdMap(Panel.load(path), spec_path=path)


# -- a revision: the previous delivery's map --------------------------------------
def load_previous(path):
    """A delivery's map, from its folder or its idmap.json, with the SHA-256
    of what it says under `_sha256`: translate --previous records it in each
    spec it keeps IDs for, so the map written for the build is diffed against
    that map and no other.

    What it says, not its bytes: a delivery that travelled through Windows
    comes back re-saved with CRLF line ends, or a BOM, and is the same map."""
    f = os.path.join(path, 'idmap.json') if os.path.isdir(path) else path
    try:
        with open(f, encoding='utf-8-sig') as fh:
            m = json.load(fh)
    except (OSError, ValueError) as e:
        raise ValueError(f"no ID map to read at {path} ({e}) - give the previous delivery's idmap "
                         'folder or its idmap.json') from None
    if not isinstance(m, dict) or not isinstance(m.get('controls'), list):
        raise ValueError(f'{f} is not an ID map - it lists no controls')
    m['_sha256'] = hashlib.sha256(json.dumps(m, sort_keys=True, ensure_ascii=False,
                                             separators=(',', ':')).encode('utf-8')).hexdigest()
    return m


def places(c):
    """Every place a map's row is, on every panel."""
    return [a for at in (c.get('panels') or {}).values() for a in at] or c.get('at') or []


def known(m):
    """What a previous map gave each control: ({(page or popup, name): ID}
    for the canvas's controls, the same for what a panel's layout derived,
    {every ID it holds, its retired ones too: what it was}).

    A control is known by its page or popup and its name, on whichever panel
    it is - the same name on two pages is two controls. A key the map gives two
    IDs knows neither, and a layout's copy of a control (a mirror) is the
    control's, not a key of its own. The two are kept apart so that a canvas
    control drawn since cannot take the ID of a derived one that happens to
    share its page and name.
    """
    books = ({}, {})
    for c in m.get('controls') or []:
        book = books[1 if c.get('derived') else 0]
        for a in places(c):
            if a.get('mirror'):
                continue
            k = (a['container'], a['name'])
            book[k] = c['id'] if book.get(k, c['id']) == c['id'] else None
    held = {r['id']: r.get('was') or '' for r in m.get('retired') or []}
    for c in m.get('controls') or []:
        at = (c.get('at') or places(c) or [{}])[0]
        held[c['id']] = f"{at.get('container')} / {at.get('name')}"
    canvas, derived = ({k: v for k, v in b.items() if v is not None} for b in books)
    return canvas, derived, held


def views(m):
    """{panel: map as that panel's own} - None for a map of one panel."""
    if m.get('panels'):
        return {p['model']: panel_view(m, p['model']) for p in m['panels']}
    return {None: m}


def view_of(m, model, drawn_on=True):
    """Map `m` as panel `model`'s own: its view of that panel, for a map of
    several - None where it has no such panel; a map of one panel where it
    is of that panel, or names none (written before maps named their panel)
    and `model` is the panel the canvas is drawn on."""
    v = views(m)
    if None not in v:
        return v.get(model)
    return m if m.get('model') == model or (m.get('model') is None and drawn_on) else None


def containers(view):
    """{page or popup name: (kind, {the names of the canvas controls on it})}
    of one panel's view of a map."""
    out = {p['name']: ('page', set()) for p in view.get('pages') or []}
    out.update({p['name']: ('popup', set()) for p in view.get('popups') or []})
    for c in view.get('controls') or []:
        if c.get('derived'):
            continue
        for a in c.get('at') or []:
            if a['container'] in out and not a.get('mirror'):
                out[a['container']][1].add(a['name'])
    return out


def renames(old, new):
    """[(old name, new name, kind)]: a page or popup of `old` that is gone
    from `new`, where one `new` gained holds most of its canvas controls by
    name - renamed, as far as a map can tell. `old` and `new` are
    containers(). It is only ever reported: a program shows a page by its
    name, so a renamed page is a change the program has to make, and its
    controls keep no IDs by it - the key is the page's name."""
    gone = [n for n in old if n not in new]
    came = [n for n in new if n not in old]
    pairs = []
    for g in gone:
        for c in came:
            a, b = old[g][1], new[c][1]
            both = len(a & b)
            if old[g][0] == new[c][0] and both and 2 * both >= min(len(a), len(b)):
                pairs.append((-both, g, c))
    out, used = [], set()
    for _, g, c in sorted(pairs):
        if g not in used and c not in used:
            used |= {g, c}
            out.append((g, c, old[g][0]))
    return out


def _shown(popup):
    """How ShowPopup shows a popup: 'modal', 'group <name>' or 'no group'."""
    return 'modal' if popup.get('modal') else f"group {popup['group']}" if popup.get('group') else 'no group'


def _say_ids(ids, limit=4):
    ids = [str(i) for i in ids]
    return ', '.join(ids[:limit]) + (f' and {len(ids) - limit} more' if len(ids) > limit else '')


def diff(old, new):
    """What a program written against map `old` meets in map `new`: a dict
    of every change by kind, with `needs_change` and a one-line `verdict`.

    A program addresses a control by its ID, its type, its states by index
    and its press state; shows a page or popup by name, a popup as modal or
    in its group, and a page marked reached_by program by itself; shows a
    control by showing the page or popup it is on; and does what each
    control's function says. A change to any of them needs the program
    changed. A caption, a control's name, a page's purpose and the page the
    panel boots into are said too, as needing none.

    A map of every panel is compared panel by panel, over the panels both
    have: a panel added or gone is said once, not as a change to every
    control on it. A map of one panel is of the panel it names (`model`),
    else of the panel the canvas is drawn on, the first. Against a previous
    map of several - New-GdlPanel.ps1 -IdMap -Previous maps one panel of a
    canvas of several - it is compared with that map's view of its panel
    alone (`only`): it says nothing of the others, which are not gone.
    """
    ov, nv = views(old), views(new)
    only = None
    if None in ov and None not in nv:
        ov = {old.get('model') or next(iter(nv)): ov[None]}
    elif None in nv and None not in ov:
        only = new.get('model') or next(iter(ov))
        nv = {only: nv[None]}
        ov = {only: ov[only]} if only in ov else {}
    every = [m for m in nv if m in ov]
    spec_maps = not (old.get('built') or new.get('built'))
    ch = {'generated_by': 'gdl.idmap diff',
          'previous': old.get('spec_sha256') or old.get('built_sha256'),
          'current': new.get('spec_sha256') or new.get('built_sha256'),
          'panels': {'added': [m for m in nv if m not in ov], 'removed': [m for m in ov if m not in nv],
                     'only': only},
          'pages': {k: [] for k in ('added', 'removed', 'renamed', 'kind', 'shown', 'reached', 'purpose',
                                    'start')},
          'controls': {k: [] for k in ('added', 'removed', 'renumbered', 'moved', 'renamed', 'reassigned',
                                       'changed', 'relocated', 'names', 'captions')}}

    def panels(ms):
        # A change on every panel the maps share says no panel.
        return [] if None in ms or (len(every) > 1 and list(ms) == every) else list(ms)

    # Pages and popups, panel by panel, said once for every panel it is on.
    found = collections.OrderedDict()
    for m in every:
        oc, nc = containers(ov[m]), containers(nv[m])
        ren = renames(oc, nc)
        for g, c, kind in ren:
            found.setdefault(('renamed', g, c, kind), []).append(m)
        for n in oc:
            if n not in nc and n not in {g for g, _, _ in ren}:
                found.setdefault(('removed', n, oc[n][0]), []).append(m)
            elif n in nc and oc[n][0] != nc[n][0]:
                found.setdefault(('kind', n, oc[n][0], nc[n][0]), []).append(m)
        for n in nc:
            if n not in oc and n not in {c for _, c, _ in ren}:
                found.setdefault(('added', n, nc[n][0]), []).append(m)
        was = {p['name']: (kind, p) for kind in ('page', 'popup') for p in ov[m].get(kind + 's') or []}
        for kind in ('page', 'popup'):
            for p in nv[m].get(kind + 's') or []:
                k, q = was.get(p['name'], (None, None))
                if q is None:
                    continue
                if q.get('does') != p.get('does'):
                    found.setdefault(('purpose', p['name'], q.get('does'), p.get('does')), []).append(m)
                if k != kind:
                    continue
                # ShowPopup puts a standard popup in its group's region, in
                # place of the group's others, and a modal one over everything.
                if kind == 'popup' and _shown(q) != _shown(p):
                    found.setdefault(('shown', p['name'], _shown(q), _shown(p)), []).append(m)
                # A build does not say which pages the program shows by itself:
                # a map read off one has none, so only two specs' are compared.
                if spec_maps and (q.get('reached_by') or None) != (p.get('reached_by') or None):
                    found.setdefault(('reached', p['name'], kind, q.get('reached_by'), p.get('reached_by')),
                                     []).append(m)
        if ov[m].get('start_page') != nv[m].get('start_page'):
            found.setdefault(('start', ov[m].get('start_page'), nv[m].get('start_page')), []).append(m)
    for (what, *k), ms in found.items():
        row = {'added': lambda: {'name': k[0], 'kind': k[1]},
               'removed': lambda: {'name': k[0], 'kind': k[1]},
               'renamed': lambda: {'from': k[0], 'to': k[1], 'kind': k[2]},
               'kind': lambda: {'name': k[0], 'from': k[1], 'to': k[2]},
               'shown': lambda: {'name': k[0], 'from': k[1], 'to': k[2]},
               'reached': lambda: {'name': k[0], 'kind': k[1], 'from': k[2], 'to': k[3]},
               'purpose': lambda: {'name': k[0], 'from': k[1], 'to': k[2]},
               'start': lambda: {'from': k[0], 'to': k[1]}}[what]()
        ch['pages'][what].append(dict(row, panels=panels(ms)))

    # Controls by ID, each with its row on every panel it is on.
    def index(views):
        out = collections.OrderedDict()
        for m, v in views.items():
            for c in v.get('controls') or []:
                out.setdefault(c['id'], collections.OrderedDict())[m] = c
        return out
    oi, ni = index(ov), index(nv)

    def first(rows):
        return next(iter(rows.values()))

    def where(rows):
        return '; '.join(a['container'] for a in first(rows)['at'])

    def on(rows, m):
        # Its pages and popups on panel m, each once.
        return list(dict.fromkeys(a['container'] for a in rows[m]['at']))

    def keys(rows):
        return {(m, a['container'], a['name']) for m, r in rows.items() for a in r['at'] if not a.get('mirror')}

    def ident(i, rows):
        r = first(rows)
        return {'id': i, 'type': r['type'], 'name': r['at'][0]['name'], 'at': where(rows),
                'panels': panels(rows)}

    added = [i for i in ni if i not in oi]
    removed = [i for i in oi if i not in ni]
    for a in list(added):
        r = next((r for r in removed if keys(oi[r]) & keys(ni[a])), None)
        if r is not None:
            added.remove(a)
            removed.remove(r)
            ch['controls']['renumbered'].append({'name': first(ni[a])['at'][0]['name'], 'at': where(ni[a]),
                                                 'from': r, 'to': a, 'panels': panels(ni[a])})
    for a in list(added):
        name, kind = first(ni[a])['at'][0]['name'], first(ni[a])['type']
        r = next((r for r in removed if first(oi[r])['at'][0]['name'] == name
                  and first(oi[r])['type'] == kind), None)
        if r is not None:
            added.remove(a)
            removed.remove(r)
            ch['controls']['moved'].append({'name': name, 'from': {'id': r, 'at': where(oi[r])},
                                            'to': {'id': a, 'at': where(ni[a])}, 'panels': panels(ni[a])})
    # Gone and come on the same page, the same type with the same states
    # doing the same thing: that control renamed, which its page and name no
    # longer find. Only where each is the other's one match.
    def like(r, a):
        fo, fn = first(oi[r]), first(ni[a])
        return (where(oi[r]) == where(ni[a]) and fo['type'] == fn['type'] and fo.get('function')
                and fo.get('function') == fn.get('function') and (fo.get('states') or None) == (fn.get('states') or None))
    for a in list(added):
        rs = [r for r in removed if like(r, a)]
        if len(rs) == 1 and [x for x in added if like(rs[0], x)] == [a]:
            added.remove(a)
            removed.remove(rs[0])
            ch['controls']['renamed'].append({'at': where(ni[a]), 'from': {'id': rs[0], 'name': first(oi[rs[0]])['at'][0]['name']},
                                              'to': {'id': a, 'name': first(ni[a])['at'][0]['name']},
                                              'panels': panels(ni[a])})
    ch['controls']['added'] = [ident(i, ni[i]) for i in added]
    ch['controls']['removed'] = [ident(i, oi[i]) for i in removed]

    new_names = {a['name'] for rows in ni.values() for r in rows.values() for a in r['at']}
    for i in ni:
        if i not in oi:
            continue
        o, n = oi[i], ni[i]
        fo, fn = first(o), first(n)
        row = {'id': i, 'name': fn['at'][0]['name']}
        what = {}
        types = ({m: r['type'] for m, r in o.items()}, {m: r['type'] for m, r in n.items()})
        if {m: t for m, t in types[0].items() if m in n} != {m: t for m, t in types[1].items() if m in o}:
            what['type'] = [_type({'type': fo['type'], 'types': t}) for t in types]
        for k in ('states', 'press'):
            if (fo.get(k) or None) != (fn.get(k) or None):
                what[k] = [fo.get(k), fn.get(k)]
        # What it does on each panel both maps have it on - said once where
        # it changed alike on every one, else on each panel it changed on.
        does = ({m: o[m].get('function') or None for m in o if m in n},
                {m: n[m].get('function') or None for m in o if m in n})
        ms = [m for m in does[0] if does[0][m] != does[1][m]]
        if ms:
            alike = len(ms) == len(does[0]) and all(len(set(d.values())) == 1 for d in does)
            what['function'] = [d[ms[0]] if alike else '; '.join(f"{m}: {d[m] or '-'}" for m in ms)
                                for d in does]
        # On another set of the panels both maps have: the program binds the
        # control on each panel's device. A panel added or gone is said once.
        if None not in o and [m for m in o if m in every] != [m for m in n if m in every]:
            what['panels'] = [[m for m in o if m in every], [m for m in n if m in every]]
        if what:
            ch['controls']['changed'].append(dict(row, **what))
        same_name = fo['at'][0]['name'] == fn['at'][0]['name']
        same_place = [a['container'] for a in fo['at']] == [a['container'] for a in fn['at']]
        # Another name is only a rename where it is still the control it was:
        # in its place, doing what it did, its old name nowhere else.
        if not same_name and (not same_place or 'function' in what or 'type' in what
                              or fo['at'][0]['name'] in new_names - {fn['at'][0]['name']}):
            ch['controls']['reassigned'].append({'id': i, 'from': {'name': fo['at'][0]['name'], 'at': where(o)},
                                                 'to': {'name': fn['at'][0]['name'], 'at': where(n)}})
            continue
        if not same_name:
            ch['controls']['names'].append({'id': i, 'from': fo['at'][0]['name'], 'to': fn['at'][0]['name']})
        else:
            # On another page or popup under its ID, on a panel both maps
            # have it on: up only while that one is, which the program shows.
            # Said where it moved - on a panel past the first, the first's
            # places read the same on both sides.
            ms = [m for m in o if m in n and set(on(o, m)) != set(on(n, m))]
            if ms:
                fr, to = ({m: '; '.join(on(rows, m)) for m in ms} for rows in (o, n))
                ch['controls']['relocated'].append(
                    {'id': i, 'name': row['name'],
                     **{k: v[ms[0]] if len(set(v.values())) == 1 else '; '.join(f'{m}: {v[m]}' for m in ms)
                        for k, v in (('from', fr), ('to', to))},
                     'panels': panels(ms)})
        if fo['at'][0]['caption'] != fn['at'][0]['caption']:
            ch['controls']['captions'].append({'id': i, 'name': row['name'], 'from': fo['at'][0]['caption'],
                                               'to': fn['at'][0]['caption']})
    ch['needs_change'], ch['verdict'] = _verdict(ch)
    return ch


def _verdict(ch):
    """(needs a change, the one line that says so)."""
    p, c = ch['pages'], ch['controls']
    parts = []
    if ch['panels']['added']:
        parts.append(f"a panel to drive ({', '.join(ch['panels']['added'])})")
    if ch['panels']['removed']:
        parts.append(f"a panel gone ({', '.join(ch['panels']['removed'])})")
    for r in p['renamed']:
        parts.append(f"{r['kind']} {r['from']!r} shown as {r['to']!r}")
    for r in p['kind']:
        parts.append(f"{r['name']!r} shown as a {r['to']}, not a {r['from']}")
    for r in p['shown']:
        parts.append(f"popup {r['name']!r} {r['to']}, not {r['from']}")
    # Shown by the program on its own (an incoming call): nothing else will.
    # The other way the program may still show it, and needs no change.
    for r in p['reached']:
        if r['to'] == 'program':
            parts.append(f"{r['kind']} {r['name']!r} shown by the program on its own")
    if p['added']:
        parts.append(f"{len(p['added'])} new page(s) or popup(s) to show "
                     f"({', '.join(repr(r['name']) for r in p['added'][:4])})")
    if p['removed']:
        parts.append(f"{len(p['removed'])} page(s) or popup(s) gone "
                     f"({', '.join(repr(r['name']) for r in p['removed'][:4])})")
    if c['added']:
        parts.append(f"{len(c['added'])} new control(s) to handle ({_say_ids(r['id'] for r in c['added'])})")
    if c['removed']:
        parts.append(f"{len(c['removed'])} control(s) gone, their IDs retired "
                     f"({_say_ids(r['id'] for r in c['removed'])})")
    # One line however much changed: a kind of change with more than two is
    # counted, and changes.md has each.
    for k, one, many in (
            ('renumbered', lambda r: f"{r['name']} at {r['to']}, not {r['from']}",
             'control(s) at another ID'),
            ('moved', lambda r: f"{r['name']} moved from {r['from']['at']} to {r['to']['at']}: "
                                f"{r['to']['id']}, not {r['from']['id']}", 'control(s) moved to another page'),
            ('renamed', lambda r: f"{r['from']['name']} renamed {r['to']['name']}: {r['to']['id']}, "
                                  f"not {r['from']['id']}", 'control(s) renamed'),
            ('reassigned', lambda r: f"{r['id']} is {r['to']['name']} on {r['to']['at']}, not {r['from']['name']}",
             'ID(s) now another control'),
            ('relocated', lambda r: f"{r['name']} ({r['id']}) on {r['to']}, not {r['from']}"
                                    + (f" ({', '.join(r['panels'])})" if r.get('panels') else ''),
             'control(s) on another page or popup')):
        if len(c[k]) > 2:
            ids = [r['to'] if k == 'renumbered' else r['id'] if k in ('reassigned', 'relocated') else r['to']['id']
                   for r in c[k]]
            parts.append(f'{len(c[k])} {many} ({_say_ids(ids)})' if k in ('reassigned', 'relocated')
                         else f'{len(c[k])} {many}, under new IDs ({_say_ids(ids)})')
        else:
            parts += [one(r) for r in c[k]]
    for k, say in (('type', 'type'), ('states', 'states'), ('press', 'press state'),
                   ('function', 'function'), ('panels', 'panels')):
        ids = [r['id'] for r in c['changed'] if k in r]
        if ids:
            parts.append(f"the {say} of {_say_ids(ids)}")
    if not parts:
        return False, 'A program written against the previous map needs no change.'
    return True, 'A program written against the previous map needs changing: ' + '; '.join(parts) + '.'


def changes_markdown(ch, title):
    """changes.md: the verdict, then each change, those a program must make
    first."""
    def on(r):
        return ', '.join(r.get('panels') or []) or 'every panel'

    def st(v):
        return IdMap.states({'states': v}) if isinstance(v, list) else (v or '-')
    out = [f'# Changes: {title}', '',
           "What a program written against the previous delivery's ID map meets in this one, from "
           '`python -m gdl.idmap diff`. Regenerate rather than edit.', '', f"**{ch['verdict']}**"]
    only = ch['panels'].get('only')
    if only:
        out += ['', f"This map is of the {only} only, so it is compared with the previous map's {only} and "
                    "says nothing of that map's other panels."]
    if ch['panels']['added'] or ch['panels']['removed']:
        out += ['', '## Panels', '']
        out += [f'- New: {m}' for m in ch['panels']['added']] + [f'- Gone: {m}' for m in ch['panels']['removed']]
    p = ch['pages']
    rows = ([f"| renamed | {_cell(r['from'])} -> {_cell(r['to'])} | {r['kind']} | {on(r)} |" for r in p['renamed']]
            + [f"| {r['from']} -> {r['to']} | {_cell(r['name'])} | {r['to']} | {on(r)} |" for r in p['kind']]
            + [f"| {_cell(r['from'])} -> {_cell(r['to'])} | {_cell(r['name'])} | popup | {on(r)} |"
               for r in p['shown']]
            + [f"| shown by the program | {_cell(r['name'])} | {r['kind']} | {on(r)} |"
               for r in p['reached'] if r['to'] == 'program']
            + [f"| added | {_cell(r['name'])} | {r['kind']} | {on(r)} |" for r in p['added']]
            + [f"| removed | {_cell(r['name'])} | {r['kind']} | {on(r)} |" for r in p['removed']])
    if rows:
        out += ['', '## Pages and popups', '',
                'A program shows a page or popup by its name. A renamed one is reported, never mapped: '
                'its controls are new to the program, their old IDs retired, unless the canvas pins '
                "each one's `id`.", '', '| Change | Name | Kind | Panels |', '|---|---|---|---|'] + rows
    c = ch['controls']
    rows = ([f"| added | {r['id']} | {_cell(r['name'])} | {_cell(r['at'])} | - | {r['type']} |" for r in c['added']]
            + [f"| removed | {r['id']} | {_cell(r['name'])} | {_cell(r['at'])} | {r['type']} | retired |"
               for r in c['removed']]
            + [f"| renumbered | {r['to']} | {_cell(r['name'])} | {_cell(r['at'])} | {r['from']} | {r['to']} |"
               for r in c['renumbered']]
            + [f"| moved | {r['to']['id']} | {_cell(r['name'])} | {_cell(r['to']['at'])} | "
               f"{r['from']['id']} on {_cell(r['from']['at'])} | {r['to']['id']} on {_cell(r['to']['at'])} |"
               for r in c['moved']]
            + [f"| renamed | {r['to']['id']} | {_cell(r['to']['name'])} | {_cell(r['at'])} | "
               f"{_cell(r['from']['name'])}, {r['from']['id']} | {_cell(r['to']['name'])}, {r['to']['id']} |"
               for r in c['renamed']]
            + [f"| reassigned | {r['id']} | {_cell(r['to']['name'])} | {_cell(r['to']['at'])} | "
               f"{_cell(r['from']['name'])} on {_cell(r['from']['at'])} | {_cell(r['to']['name'])} |"
               for r in c['reassigned']]
            + [f"| relocated | {r['id']} | {_cell(r['name'])} | {', '.join(r.get('panels') or []) or '-'} | "
               f"{_cell(r['from'])} | {_cell(r['to'])} |" for r in c['relocated']])
    for r in c['changed']:
        for k in ('type', 'states', 'press', 'function', 'panels'):
            if k in r:
                a, b = r[k]
                if k == 'panels':
                    a, b = ', '.join(a), ', '.join(b)
                rows.append(f"| {k} | {r['id']} | {_cell(r['name'])} | - | {_cell(st(a))} | {_cell(st(b))} |")
    if rows:
        out += ['', '## Controls a program must change for', '',
                "**States** are numbered as the program sets them, so a state put in front of another "
                'moves every one after it.', '',
                '| Change | ID | Control | Where | Was | Now |', '|---|---|---|---|---|---|'] + rows
    rows = ([f"| name | {r['id']} | {_cell(r['to'])} | {_cell(r['from'])} | {_cell(r['to'])} |"
             for r in c['names']]
            + [f"| caption | {r['id']} | {_cell(r['name'])} | {_cell(r['from']) or '-'} | {_cell(r['to']) or '-'} |"
               for r in c['captions']]
            + [f"| purpose | - | {_cell(r['name'])} | {_cell(r['from'] or '-')} | {_cell(r['to'] or '-')} |"
               for r in p['purpose']]
            + [f"| reached by | - | {_cell(r['name'])} | {r['from'] or '-'} | {r['to'] or '-'} |"
               for r in p['reached'] if r['to'] != 'program']
            + [f"| boots into | - | - | {_cell(r['from'] or '-')} | {_cell(r['to'] or '-')} |" for r in p['start']])
    if rows:
        out += ['', '## Also changed, no program change', '',
                '| Change | ID | Control | Was | Now |', '|---|---|---|---|---|'] + rows
    return '\n'.join(out) + '\n'


def write_changes(out_dir, previous, d, title):
    """changes.json and changes.md beside the map `d`; the paths written."""
    ch = diff(previous, d)
    out = []
    for name, text in (('changes.json', json.dumps(ch, indent=1, ensure_ascii=False) + '\n'),
                       ('changes.md', changes_markdown(ch, title))):
        path = os.path.join(out_dir, name)
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        out.append(path)
    return out


def previous_problem(specs, previous):
    """(problem, note) for specs translated against a previous map - each
    records its SHA-256 (`_previous`) - and the map `previous` given to write
    the changes against, or None. The changes are only true of the map the
    IDs were kept against."""
    shas = sorted({s.get('_previous') for s in specs} - {None})
    if previous is not None and shas and shas != [previous['_sha256']]:
        return (f"the specs kept the IDs of the map with sha256 {', '.join(x[:12] for x in shas)}, not this "
                f"one ({previous['_sha256'][:12]}) - pass that delivery's map, or translate the canvas again "
                'with this one'), None
    if previous is None and shas:
        return None, (f"translated against a previous delivery's map (sha256 {shas[0][:12]}) - pass it with "
                      '--previous to write changes.md beside this one')
    return None, None


def main(argv):
    # As gdl.spec's: a problem quotes the spec, and a redirected Windows stdout
    # is cp1252 - escape what it cannot take rather than crash mid-report.
    try:
        sys.stdout.reconfigure(errors='backslashreplace')
    except (AttributeError, ValueError):
        pass
    if len(argv) >= 4 and argv[1] == 'from-built':
        try:
            m = BuiltMap.open(argv[2])
        except (KeyError, OSError, ValueError, zipfile.BadZipFile) as e:
            from .seeds import usable
            if os.path.isfile(argv[2]) and not usable(argv[2]):
                print(f'  {argv[2]} is a Git LFS pointer, not the panel - git lfs pull it first')
            else:
                print(f'  {argv[2]} has no built layout.json to read ({e}) - build it in GUI '
                      f'Designer first: Save and Build writes one')
            return 1
        for w in m.write(argv[3]):
            print(f'  wrote {w}')
        print(f"{len(m.data()['controls'])} control(s) mapped off {argv[2]} -> {argv[3]}")
        return 0
    if len(argv) >= 2 and argv[1] == 'diff':
        if len(argv) != 4:
            print('  python -m gdl.idmap diff <old map> <new map>   (an idmap folder or its idmap.json)')
            return 2
        try:
            old, new = load_previous(argv[2]), load_previous(argv[3])
        except ValueError as e:
            print(f'  {e}')
            return 2
        ch = diff(old, new)
        print(changes_markdown(ch, f'{argv[2]} -> {argv[3]}'), end='')
        # Exit as diff(1) does: 0 when there is nothing to do.
        return 1 if ch['needs_change'] else 0
    previous = None
    if '--previous' in argv:
        i = argv.index('--previous')
        path = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
        try:
            previous = load_previous(path) if path else None
        except ValueError as e:
            print(f'  {e}')
            return 1
        if previous is None:
            print('  --previous needs the previous delivery\'s idmap folder or its idmap.json')
            return 2
    if len(argv) >= 4 and argv[1] == 'write-panels':
        try:
            maps = load_panels(argv[2])
        except ValueError as e:
            print(f'  {e}')
            return 1
        if not maps:
            print(f'no <panel>/spec.json under {argv[2]}')
            return 1
        problems = check_panels(maps)
        bad, note = previous_problem([m.spec for m in maps.values()], previous)
        problems += [bad] if bad else []
        for p in problems:
            print('  ' + p)
        if note:
            print('  note: ' + note)
        if problems:
            print(f'{len(problems)} problem(s) - nothing written')
            return 1
        for w in write_panels(maps, argv[3], previous):
            print(f'  wrote {w}')
        print(f"{len(combine(maps)['controls'])} control(s) on {len(maps)} panel(s) "
              f"({', '.join(maps)}) -> {argv[3]}")
        return 0
    if len(argv) < 3 or argv[1] not in ('check', 'write') or \
            (argv[1] == 'write' and len(argv) < 4):
        print(__doc__.strip().split('\n\n')[0])
        print('\n  python -m gdl.idmap check <spec.json>'
              '\n  python -m gdl.idmap write <spec.json> <out_dir> [--previous <map>]'
              '\n  python -m gdl.idmap write-panels <specs dir> <out_dir> [--previous <map>]'
              '\n  python -m gdl.idmap from-built <panel.gdl> <out_dir>'
              '\n  python -m gdl.idmap diff <old map> <new map>')
        return 2
    m = load(argv[2])
    problems, notes = m.check()
    bad, note = previous_problem([m.spec], previous)
    problems += [bad] if bad else []
    notes += [note] if note else []
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
    for w in m.write(argv[3], previous):
        print(f'  wrote {w}')
    print(f'{len(m.addressed())} control(s) mapped -> {argv[3]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
