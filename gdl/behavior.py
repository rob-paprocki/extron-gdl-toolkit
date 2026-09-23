"""What a panel's controls DO, and the control program that makes them do it.

A `.gdl` carries no behavior. GUI Designer's previous product generation had
per-button actions (`PanelBuilder.PBActionShowPage` and friends), and converting
a project to the current format says so outright - "Local Actions and Audio
Resources will be lost!". What survives is structure: pages, popups, popup
groups, a start page, and a numeric ID on every control. Everything a button
does - flip a page, show a popup, route a source, mute a microphone - lives in
the control program, which finds the control by that ID.

So a spec that says what its controls do needs two outputs, not one: the panel,
which `gdl.spec` builds, and the program, which this module writes. Both come
from the same spec file, so the IDs and names in one cannot drift from the
other.

    python -m gdl.behavior check    <spec.json>
    python -m gdl.behavior generate <spec.json> <out_dir>

`generate` writes an Extron Global Scripter (ControlScript / extronlib)
program plus an environment-neutral handoff - an ID map with each control's
job - for a programmer working in anything else. docs/behavior.md has the
vocabulary, every check and where each rule comes from.

Addressing is the one rule to hold on to. A CONTROL is addressed by its numeric
ID, which survives Build. A PAGE or POPUP is addressed by NAME: its number does
not survive Build - a page authored as 1000 comes back as 51 - so nothing here
ever emits one.

Stdlib only, like everything outside gdl/compose.py.
"""
import collections
import hashlib
import json
import keyword
import os
import re
import sys

from .spec import Panel

# spec key -> (extronlib event name, control kinds that raise it). Official
# ControlScript reference: Button raises Pressed, Released, Held, Repeated and
# Tapped; Slider raises Pressed, Released and Changed. Touch panels only send
# Pressed and Released - Held, Repeated and Tapped are timers inside the
# Button object, which is why they need holdTime.
EVENTS = collections.OrderedDict([
    ('press', ('Pressed', {'button', 'slider'})),
    ('release', ('Released', {'button', 'slider'})),
    ('tap', ('Tapped', {'button'})),
    ('hold', ('Held', {'button'})),
    ('repeat', ('Repeated', {'button'})),
    ('change', ('Changed', {'slider'})),
])
# The extronlib class for each addressable kind, and the prefix of the Python
# name generated for it. Everything else - panels, lines, images, clocks,
# popup references - has no extronlib object and no events.
CLASS_OF = {'button': 'Button', 'label': 'Label', 'level': 'Level', 'slider': 'Slider'}
PREFIX = {'button': 'btn', 'label': 'lbl', 'level': 'lvl', 'slider': 'sld'}
# What a bound value is, by the setter the class offers: Button.SetState,
# Label.SetText, Level.SetLevel, Slider.SetFill.
BIND_TYPE = {'button': 'on/off', 'label': 'text', 'level': 'number', 'slider': 'number'}
ACTIONS = ('show_page', 'show_popup', 'hide_popup', 'hide_all_popups', 'call')
BEHAVIOR_KEYS = set(EVENTS) | {'nav', 'bind', 'select_group', 'range', 'hold_time',
                               'repeat_time'}
DEFAULT_ALIAS = 'TLP1'
BIND_PATH = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$')


def _ident(s):
    return isinstance(s, str) and s.isidentifier() and not keyword.iskeyword(s)


def _slug(s):
    """A Python-name fragment from a control's name: 'Vol Down' -> 'vol_down'.

    Only a readability suffix - the ID ahead of it is what makes a generated
    name unique - so a name made of symbols ('-', '+') simply has none.
    """
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', str(s or ''))
    s = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').lower()
    return s if s and not s[0].isdigit() else ''


def _camel(s):
    return ''.join(p[:1].upper() + p[1:] for p in s.split('_') if p) or 'Device'


def _cell(s):
    """Text safe inside a Markdown table cell: a `|` would split it."""
    return str(s).replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')


class Program:
    """A loaded spec's behavior, checked, and ready to generate."""

    def __init__(self, panel, spec_path=None):
        self.panel = panel
        self.spec = panel.spec
        self.spec_path = spec_path
        b = self.spec.get('behavior') or {}
        self.alias = b.get('panel_alias') or DEFAULT_ALIAS
        self.alias_given = bool(b.get('panel_alias'))
        self.devices = b.get('devices') or {}
        self.inactivity = b.get('inactivity')
        self.start_page = panel.start_page
        self._problems, self._notes = [], []
        self.drift_notes = []

        self.page_names = [pg['name'] for pg in panel.pages]
        self.popup_by_name = {pu['name']: pu for pu in panel.popups}
        raw_pages = self.spec.get('pages') or []
        raw_popups = self.spec.get('popups') or []
        self.containers = []
        for i, pg in enumerate(panel.pages):
            self.containers.append(self._container(pg, 'page', raw_pages[i]))
        for i, pu in enumerate(panel.popups):
            self.containers.append(self._container(pu, 'popup', raw_popups[i]))

        self.uses_behavior = bool(self.spec.get('behavior')) or any(
            k in c for ct in self.containers for c in ct['raw'] for k in BEHAVIOR_KEYS)
        self.controls = [self._control(ct, c) for ct in self.containers for c in ct['raw']]
        self.inactivity_actions = self._inactivity()
        for ct in self.containers:
            ct['controls'] = [r for r in self.controls if r['container'] == ct['name']]

    # -- reading the spec ----------------------------------------------------
    def _container(self, item, kind, raw):
        rb = raw.get('reached_by')
        if rb not in (None, 'program'):
            self._problems.append(f"{kind} {item['name']!r}: reached_by must be 'program' "
                                  f'(shown by hand-written code), not {rb!r}')
        return {
            'name': item['name'], 'kind': kind,
            'modal': bool(item.get('modal')) if kind == 'popup' else False,
            'group': item.get('group') if kind == 'popup' else None,
            'reached_by': rb,
            # Popup groups this page can show a standard popup through.
            'refs': {c.get('group') for c in item['controls']
                     if c.get('kind') == 'popup_ref' and c.get('group')},
            'raw': item['controls'],
        }

    def _where(self, ct, c):
        return f"{ct['kind']} {ct['name']!r} {c.get('name') or c.get('text') or '?'!r}"

    def _control(self, ct, c):
        kind = c.get('kind', 'panel')
        where = self._where(ct, c)
        theme_on = self.panel.theme.get('on')
        rec = {
            'container': ct['name'], 'container_kind': ct['kind'], 'where': where,
            'name': c.get('name') or c.get('text') or kind, 'text': c.get('text') or '',
            'kind': kind, 'id': c['id'], 'events': collections.OrderedDict(),
            'bind': c.get('bind'), 'select_group': c.get('select_group'),
            'range': c.get('range'), 'hold_time': c.get('hold_time'),
            'repeat_time': c.get('repeat_time'),
            'has_on': kind == 'button' and bool(c.get('on', theme_on)),
        }
        used = sorted(k for k in BEHAVIOR_KEYS if k in c)
        if kind not in CLASS_OF:
            if used:
                self._problems.append(
                    f"{where}: a {kind} has no extronlib object, so it can carry no behavior "
                    f"({', '.join(used)}) - only button, slider, label and level can")
            return rec

        if 'nav' in c:
            if 'press' in c:
                self._problems.append(f'{where}: nav and press together - nav is shorthand '
                                      f'for a press that shows a page or popup; use one')
            elif kind != 'button':
                self._problems.append(f'{where}: nav belongs on a button, not a {kind}')
            else:
                a = self._nav(c['nav'], where)
                if a:
                    rec['events']['Pressed'] = [a]
        for key, (event, kinds) in EVENTS.items():
            if key not in c:
                continue
            if kind not in kinds:
                self._problems.append(f'{where}: a {kind} raises no {event} event, so it cannot '
                                      f'take {key!r}')
                continue
            rec['events'][event] = self._actions(c[key], where, key, kind)

        self._timing(rec, c, where)
        if rec['bind'] is not None:
            if not isinstance(rec['bind'], str) or not BIND_PATH.match(rec['bind']):
                self._problems.append(f"{where}: bind {rec['bind']!r} must be a dotted path of "
                                      f"identifiers, like 'audio.muted'")
                rec['bind'] = None
            elif kind == 'button' and not rec['has_on']:
                self._problems.append(f"{where}: bound to {rec['bind']!r} but has no 'on' state, "
                                      f'so SetState(1) would change nothing on the panel')
        if rec['range'] is not None:
            r = rec['range']
            if kind not in ('level', 'slider'):
                self._problems.append(f'{where}: range belongs on a level or slider')
            else:
                # Level.SetRange takes ints (ControlScript reference); Slider's
                # takes int or float.
                ok = (int,) if kind == 'level' else (int, float)
                if not (isinstance(r, list) and len(r) == 2
                        and all(isinstance(v, ok) and not isinstance(v, bool) for v in r)
                        and r[0] < r[1]):
                    self._problems.append(
                        f'{where}: range must be [min, max] with min < max'
                        + (', whole numbers for a level' if kind == 'level' else '')
                        + f', not {r!r}')
        return rec

    def _timing(self, rec, c, where):
        for key in ('hold_time', 'repeat_time'):
            v = c.get(key)
            if v is None:
                continue
            if rec['kind'] != 'button':
                self._problems.append(f'{where}: {key} belongs on a button')
            elif isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                self._problems.append(f'{where}: {key} must be a positive number of seconds, '
                                      f'not {v!r}')
        ev = rec['events']
        # Held, Repeated and Tapped are timers inside the extronlib Button,
        # defined relative to holdTime. Without it Held never fires, and Tapped
        # is documented only as "released before holdTime expires".
        for event in ('Held', 'Repeated', 'Tapped'):
            if event in ev and c.get('hold_time') is None:
                self._problems.append(f'{where}: {event} needs hold_time - it is a timer the '
                                      f'Button object runs from holdTime')
        if 'Repeated' in ev and c.get('repeat_time') is None:
            self._problems.append(f'{where}: Repeated needs repeat_time as well as hold_time')
        # The same reference, the other way round: "If button is released
        # before holdTime expires, a Tapped event is triggered instead of a
        # Released event." With hold_time set, a release action alone would not
        # run on an ordinary quick press.
        if 'Released' in ev and c.get('hold_time') is not None and 'Tapped' not in ev:
            self._problems.append(f'{where}: release with hold_time but no tap - a quick '
                                  f'release fires Tapped instead of Released, so the release '
                                  f'action would only run after a long hold. Add tap for the '
                                  f'quick case, or use hold for the long one')

    def _nav(self, target, where):
        if target in self.page_names:
            return {'do': 'show_page', 'target': target}
        if target in self.popup_by_name:
            return {'do': 'show_popup', 'target': target, 'duration': 0}
        self._problems.append(f'{where}: nav target {target!r} is neither a page nor a popup '
                              f'in this spec')
        return None

    def _actions(self, value, where, key, kind='button'):
        items = value if isinstance(value, list) else [value]
        out = []
        for a in items:
            if not isinstance(a, dict) or 'do' not in a:
                self._problems.append(f"{where}: {key} action {a!r} must be an object with "
                                      f"'do' - one of {', '.join(ACTIONS)}")
                continue
            do = a['do']
            if do not in ACTIONS:
                self._problems.append(f"{where}: unknown action {do!r} - one of "
                                      f"{', '.join(ACTIONS)}")
                continue
            if a.get('costly') and do != 'call':
                self._problems.append(f'{where}: costly marks a device call that needs '
                                      f'confirming; {do} is not one')
            if 'duration' in a and do != 'show_popup':
                self._problems.append(f'{where}: duration belongs on show_popup, not {do}')
            n = {'do': do}
            if do in ('show_page', 'show_popup', 'hide_popup'):
                t = a.get('target')
                if do == 'show_page' and t not in self.page_names:
                    self._problems.append(
                        f'{where}: show_page target {t!r} is not a page in this spec'
                        + (' - it is a popup; use show_popup' if t in self.popup_by_name else ''))
                    continue
                if do != 'show_page' and t not in self.popup_by_name:
                    self._problems.append(
                        f'{where}: {do} target {t!r} is not a popup in this spec'
                        + (' - it is a page; use show_page' if t in self.page_names else ''))
                    continue
                n['target'] = t
                if do == 'show_popup':
                    d = a.get('duration', 0)
                    if isinstance(d, bool) or not isinstance(d, (int, float)) or d < 0:
                        self._problems.append(f'{where}: duration must be a number of seconds, '
                                              f'0 meaning until hidden, not {d!r}')
                        d = 0
                    n['duration'] = d
            elif do == 'call':
                dev, op, args = a.get('device'), a.get('op'), a.get('args') or {}
                if dev not in self.devices:
                    self._problems.append(
                        f"{where}: call to device {dev!r}, which behavior.devices does not "
                        f"declare ({', '.join(sorted(self.devices)) or 'none declared'})")
                    continue
                if not _ident(op):
                    self._problems.append(f'{where}: op {op!r} must be a Python identifier - it '
                                          f'becomes a method in devices.py')
                    continue
                if not isinstance(args, dict) or not all(_ident(k) and k != 'self'
                                                         for k in args):
                    self._problems.append(f'{where}: args {args!r} must map identifiers to JSON '
                                          f"values - each becomes a keyword argument, so 'self' "
                                          f'and Python keywords cannot be used')
                    continue
                if kind == 'slider' and 'value' in args:
                    self._problems.append(f"{where}: a slider passes its own value= to every "
                                          f"call, so an argument may not be named 'value'")
                    continue
                n.update(device=dev, op=op, args=dict(args), costly=bool(a.get('costly')))
            out.append(n)
        return out

    def _inactivity(self):
        ia = self.inactivity
        if not ia:
            return []
        s = ia.get('seconds') if isinstance(ia, dict) else None
        if isinstance(s, bool) or not isinstance(s, (int, float)) or s <= 0:
            self._problems.append(f'behavior.inactivity.seconds must be a positive number, '
                                  f'not {s!r}')
        acts = self._actions(ia.get('do', []) if isinstance(ia, dict) else [],
                             'behavior.inactivity', 'do')
        if not acts:
            self._problems.append('behavior.inactivity has no actions - it would arm the '
                                  "panel's inactivity timer to do nothing")
        return acts

    # -- lookups -------------------------------------------------------------
    def control(self, uid):
        """The first control record carrying this ID."""
        return next((r for r in self.controls if r['id'] == uid), None)

    def container(self, name):
        return next((ct for ct in self.containers if ct['name'] == name), None)

    def addressed(self):
        """ID -> the records sharing it, for every control extronlib can address."""
        out = collections.OrderedDict()
        for r in self.controls:
            if r['kind'] in CLASS_OF:
                out.setdefault(r['id'], []).append(r)
        return out

    def select_groups(self):
        out = collections.OrderedDict()
        for r in self.controls:
            if r['select_group'] is not None and r['kind'] in CLASS_OF:
                ids = out.setdefault(r['select_group'], [])
                if r['id'] not in ids:
                    ids.append(r['id'])
        return out

    def binds(self):
        out = collections.OrderedDict()
        for r in self.controls:
            if r['bind'] and r['kind'] in CLASS_OF:
                out.setdefault(r['bind'], []).append(r)
        return out

    def nav_edges(self):
        """{(from container, to container)} for every page and popup a control shows."""
        edges = set()
        for r in self.controls:
            for acts in r['events'].values():
                for a in acts:
                    if a['do'] in ('show_page', 'show_popup'):
                        edges.add((r['container'], a['target']))
        return edges

    def calls(self):
        """(device, op) -> {'args': [names in first-seen order], 'value': bool}."""
        out = collections.OrderedDict()
        for r in self.controls:
            for acts in r['events'].values():
                for a in acts:
                    if a['do'] == 'call':
                        e = out.setdefault((a['device'], a['op']), {'args': [], 'value': False})
                        for k in a['args']:
                            if k not in e['args']:
                                e['args'].append(k)
                        if r['kind'] == 'slider':
                            e['value'] = True
        for a in self.inactivity_actions:
            if a['do'] == 'call':
                e = out.setdefault((a['device'], a['op']), {'args': [], 'value': False})
                for k in a['args']:
                    if k not in e['args']:
                        e['args'].append(k)
        return out

    # -- checks --------------------------------------------------------------
    def check(self):
        """(problems, notes). Problems block `generate`, the way they block `plan`.

        Notes never block: they are heuristics drawn from Extron's standards and
        docs/design-rules.md marks them as extrapolated.
        """
        problems = list(self.panel.check()) + list(self._problems)
        notes = []
        if not self.uses_behavior:
            notes.append('the spec declares no behavior: the handoff still lists every '
                         'addressable ID, and the program only boots the start page')
        if not self.alias_given:
            notes.append(f'behavior.panel_alias not given; the program addresses the panel '
                         f"as {DEFAULT_ALIAS!r}, which must match its UI Device alias in "
                         f'Global Scripter')
        classes = {}
        for name in self.devices:
            if not _ident(name):
                problems.append(f'device {name!r} must be a Python identifier - it becomes an '
                                f'object in devices.py')
                continue
            # devices.py holds one class per device and one object per device,
            # in one namespace next to its ProgramLog import. Two names that
            # meet there silently rebind each other: 'roomDsp' and 'RoomDsp'
            # both become class RoomDsp, and the second class wins.
            cls = _camel(name)
            clash = [n for n in (classes.get(cls),) if n] + \
                [n for n in self.devices if n != name and n == cls]
            if name == 'ProgramLog' or cls == 'ProgramLog':
                problems.append(f"device {name!r} would shadow devices.py's ProgramLog import")
            elif clash:
                problems.append(f"devices {clash[0]!r} and {name!r} collide in devices.py as "
                                f'class {cls} - rename one')
            classes[cls] = name
        problems += self._feedback_rules()
        problems += self._mirror_rules()
        problems += self._showability_rules()
        problems += self._confirmation_rules()
        p, n = self._graph_rules()
        problems += p
        notes += n
        notes += self._notes_on_controls()
        return problems, notes

    def _feedback_rules(self):
        out = []
        for path, recs in self.binds().items():
            types = {BIND_TYPE[r['kind']] for r in recs}
            if len(types) > 1:
                out.append(f'bind {path!r} is bound to {" and ".join(sorted(types))} controls - '
                           f'one feedback value cannot be both')
        seen = {}
        for path in self.binds():
            fn = path.replace('.', '_')
            if fn in seen and seen[fn] != path:
                out.append(f'bind paths {seen[fn]!r} and {path!r} both become ui_feedback.{fn}()')
            seen[fn] = path
        groups = self.select_groups()
        slugs = {}
        for g in groups:
            s = _slug(g) or 'group'
            if s in slugs and slugs[s] != g:
                out.append(f'select groups {slugs[s]!r} and {g!r} both become sel_{s}')
            slugs[s] = g
        for r in self.controls:
            if r['select_group'] is None:
                continue
            if r['kind'] != 'button':
                out.append(f"{r['where']}: select_group members must be buttons - an MESet "
                           f'selects by SetState, which a {r["kind"]} does not have')
            elif not r['has_on']:
                out.append(f"{r['where']}: in select_group {r['select_group']!r} but has no "
                           f"'on' state, so being selected would look like nothing")
            elif r['bind']:
                out.append(f"{r['where']}: select_group and bind both set its state - two "
                           f'sources of truth for one button')
        return out

    @staticmethod
    def _signature(r):
        return (r['kind'], json.dumps(r['events'], sort_keys=True), r['bind'],
                r['select_group'], json.dumps(r['range']), r['hold_time'], r['repeat_time'])

    def _mirror_rules(self):
        """Controls sharing an ID are ONE extronlib object: one handler, one state.

        Extron's own projects do it on purpose - Liberty Bank mirrors its
        shutdown confirm/cancel (81, 82) across two popups - so it is allowed,
        but only when every copy means the same thing. The ControlScript
        reference: "Only one handler can be assigned to a given event of a given
        object. Last handler assigned will be called."
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
            elif len({self._signature(r) for r in recs}) > 1 and kinds & set(CLASS_OF):
                out.append(f'ID {uid} is mirrored with different behavior - the program keeps one '
                           f"object per ID, so they cannot differ: "
                           f"{', '.join(r['where'] for r in recs)}")
        return out

    def host_pages(self):
        """Container -> the pages it can be showing over.

        A page hosts itself. A popup appears over whichever page is up when it
        is shown, so it inherits the hosts of everything that shows it - and a
        standard popup only on those of them that reference its group. Code the
        spec cannot see (`reached_by: program`, the inactivity handler) may
        show it over any page.
        """
        pages = [ct['name'] for ct in self.containers if ct['kind'] == 'page']
        hosts = {p: {p} for p in pages}
        anywhere = {a['target'] for a in self.inactivity_actions if a['do'] == 'show_popup'}
        for ct in self.containers:
            if ct['kind'] == 'popup':
                wide = ct['reached_by'] == 'program' or ct['name'] in anywhere
                hosts[ct['name']] = self._only_referencing(ct, set(pages) if wide else set())
        edges = self.nav_edges()
        changed = True
        while changed:
            changed = False
            for s, t in edges:
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

    def _showability_rules(self):
        """A standard popup shows only through a reference to its group on the
        page beneath - which, for a popup shown from another popup, is every
        page that popup can itself be showing over."""
        out = []
        hosts = self.host_pages()
        for r in self.controls:
            for acts in r['events'].values():
                for a in acts:
                    if a['do'] != 'show_popup':
                        continue
                    pu = self.popup_by_name[a['target']]
                    if pu['modal'] or not pu['group']:
                        continue
                    lacking = sorted(p for p in hosts.get(r['container'], ())
                                     if pu['group'] not in self.container(p)['refs'])
                    if lacking:
                        out.append(f"{r['where']}: shows popup {a['target']!r}, but page"
                                   f"{'s' if len(lacking) > 1 else ''} "
                                   f"{', '.join(repr(p) for p in lacking)} beneath it "
                                   f"{'have' if len(lacking) > 1 else 'has'} no reference to "
                                   f"its group {pu['group']!r}, so it would not appear there")
        return out

    def _confirmation_rules(self):
        """GUI Design Standards p.71: a costly or irreversible action needs a
        modal confirmation with a cancel path. `costly` goes on the call that
        executes, and the structure around it is derived from where that is."""
        out = []
        for r in self.controls:
            for acts in r['events'].values():
                for a in acts:
                    if a['do'] != 'call' or not a['costly']:
                        continue
                    ct = self.container(r['container'])
                    if not ct['modal']:
                        out.append(f"{r['where']}: {a['device']}.{a['op']} is costly, so it must "
                                   f'run from a button inside a modal confirmation popup, not '
                                   f"from a {'standard popup' if ct['kind'] == 'popup' else 'page'}")
        for ct in self.containers:
            if not ct['modal']:
                continue
            costly = any(a['do'] == 'call' and a['costly']
                         for r in ct['controls'] for acts in r['events'].values() for a in acts)
            if not costly:
                continue
            cancel = False
            for r in ct['controls']:
                for acts in r['events'].values():
                    closes = any(a['do'] == 'hide_all_popups'
                                 or (a['do'] == 'hide_popup' and a['target'] == ct['name'])
                                 for a in acts)
                    if closes and not any(a['do'] == 'call' and a['costly'] for a in acts):
                        cancel = True
            if not cancel:
                out.append(f"popup {ct['name']!r} confirms a costly action but has no cancel - a "
                           f'button that hides it without the costly call (Standards p.71)')
        return out

    def _graph_rules(self):
        problems, notes = [], []
        if not self.uses_behavior:
            return problems, notes
        edges = self.nav_edges()
        roots = {self.start_page} if self.start_page else set()
        roots |= {ct['name'] for ct in self.containers if ct['reached_by'] == 'program'}
        roots |= {a['target'] for a in self.inactivity_actions
                  if a['do'] in ('show_page', 'show_popup')}
        seen, todo = set(), list(roots)
        while todo:
            n = todo.pop()
            if n in seen:
                continue
            seen.add(n)
            todo += [t for s, t in edges if s == n]
        for ct in self.containers:
            if ct['name'] not in seen:
                problems.append(f"{ct['kind']} {ct['name']!r} is never shown: nothing navigates "
                                f"to it from the start page. Add a nav or show_{ct['kind']}, or "
                                f"mark it reached_by: 'program' if your own code shows it")
        # A modal disables everything beneath it (Standards p.71), so one with
        # no way out locks the panel.
        for ct in self.containers:
            if not ct['modal'] or ct['reached_by'] == 'program':
                continue
            closes = any(a['do'] == 'hide_all_popups'
                         or (a['do'] == 'hide_popup' and a['target'] == ct['name'])
                         for r in ct['controls'] for acts in r['events'].values() for a in acts)
            timed = any(a['do'] == 'show_popup' and a['target'] == ct['name'] and a['duration']
                        for r in self.controls for acts in r['events'].values() for a in acts)
            if not closes and not timed and ct['name'] in seen:
                problems.append(f"modal popup {ct['name']!r} has no close path: nothing in it "
                                f'hides it and it is never shown with a duration, so it would '
                                f'lock the panel')
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
                    notes.append(f'page {pg!r} is a dead end: nothing on it, or on a popup it '
                                 f'shows, leads to another page')
        return problems, notes

    def _notes_on_controls(self):
        out = []
        if self.uses_behavior:
            for r in self.controls:
                # any(), not the dict: "press": [] declares an event and does
                # nothing, and the generated handler is a bare `pass`.
                if r['kind'] == 'button' and not any(r['events'].values()) \
                        and not r['select_group'] and not r['bind']:
                    out.append(f"{r['where']}: does nothing when pressed (every tap needs "
                               f'a visible result, Standards p.13)')
        used = {dev for dev, _ in self.calls()}
        for name in self.devices:
            if name not in used:
                out.append(f'device {name!r} is declared but never called')
        for g, ids in self.select_groups().items():
            if len(ids) == 1:
                out.append(f'select_group {g!r} has one member - a selection of one never '
                           f'changes')
        # Standards p.13: every tap must show that it was recognized AND whether
        # it succeeded. Only device state can say the second, so a program that
        # calls devices and binds nothing can never show it. Deliberately
        # project-level: per control it flagged every volume step, whose result
        # shows on a level beside it, and a note that cannot be silenced is one
        # people learn to skip.
        if self.calls() and not self.binds():
            out.append('devices are called but nothing is bound: the panel can never show '
                       'whether a request succeeded (Standards p.13). Bind the state a room '
                       'cares about - mute, volume, call status.')
        return out

    # -- generation ------------------------------------------------------------
    def names(self):
        """ID -> the Python name of its extronlib object. Mirrors share one."""
        out = collections.OrderedDict()
        for uid, recs in self.addressed().items():
            r = recs[0]
            slug = _slug(r['name'])
            out[uid] = f"{PREFIX[r['kind']]}_{uid}" + (f'_{slug}' if slug else '')
        return out

    def generate(self, out_dir):
        """Write the program. Returns (written paths, problems).

        Generated files are overwritten on every run; `devices.py` and
        `main.py` are created once and never touched again, so regenerating
        cannot clobber a programmer's work. A device op the spec calls but an
        existing devices.py lacks is returned as a problem, with a stub to paste.
        """
        os.makedirs(out_dir, exist_ok=True)
        sha = self._spec_sha()
        written = []
        for name, text in (('ui_objects.py', self._ui_objects(sha)),
                           ('ui_events.py', self._ui_events(sha)),
                           ('ui_feedback.py', self._ui_feedback(sha)),
                           ('handoff.json', json.dumps(self.handoff(sha), indent=1) + '\n'),
                           ('handoff.md', self._handoff_md(sha))):
            path = os.path.join(out_dir, name)
            with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
            written.append(path)
        problems = []
        for name, text in (('devices.py', self._devices()), ('main.py', self._main())):
            path = os.path.join(out_dir, name)
            if not os.path.exists(path):
                with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write(text)
                written.append(path)
        problems += self.device_drift(os.path.join(out_dir, 'devices.py'))
        return written, problems

    def _spec_sha(self):
        if self.spec_path and os.path.exists(self.spec_path):
            with open(self.spec_path, 'rb') as fh:
                return hashlib.sha256(fh.read()).hexdigest()
        return hashlib.sha256(json.dumps(self.spec, sort_keys=True).encode()).hexdigest()

    def _banner(self, sha, what):
        src = os.path.basename(self.spec_path) if self.spec_path else 'a spec'
        return (f'# GENERATED by `python -m gdl.behavior generate` from {src} - do not edit.\n'
                f'# Regenerating overwrites this file. {what}\n'
                f'# spec_sha256: {sha}\n')

    def _ui_objects(self, sha):
        names = self.names()
        addressed = self.addressed()
        classes = sorted({CLASS_OF[recs[0]['kind']] for recs in addressed.values()})
        groups = self.select_groups()
        lines = [self._banner(sha, 'One extronlib object per addressable control.')]
        lines.append('from extronlib.device import UIDevice')
        if classes:
            lines.append(f"from extronlib.ui import {', '.join(classes)}")
        if groups:
            lines.append('from extronlib.system import MESet')
        lines += ['',
                  "# Must match the UI Device this panel's .gdl is assigned to in Global",
                  "# Scripter's System Manager. Nothing in code refers to the .gdl itself.",
                  f'TLP = UIDevice({self.alias!r})', '',
                  '# Controls are addressed by ID. Pages and popups are addressed by NAME:',
                  "# Build does not keep a page's number, so none is ever used here."]
        done = set()
        for ct in self.containers:
            recs = [r for r in ct['controls'] if r['kind'] in CLASS_OF and r['id'] not in done]
            if not recs:
                continue
            lines.append('')
            lines.append(f"# -- {ct['kind']} {ct['name']!r}")
            for r in recs:
                done.add(r['id'])
                extra = ''
                if r['kind'] == 'button' and r['hold_time']:
                    extra = f", holdTime={r['hold_time']!r}"
                    if r['repeat_time']:
                        extra += f", repeatTime={r['repeat_time']!r}"
                lines.append(f"{names[r['id']]} = {CLASS_OF[r['kind']]}(TLP, {r['id']}{extra})")
        ranged = [(uid, recs[0]) for uid, recs in addressed.items()
                  if recs[0]['kind'] in ('level', 'slider')]
        if ranged:
            lines += ['', "# Always set, so the spec's range is the contract rather than the",
                      "# library's 0-100 default."]
            for uid, r in ranged:
                lo, hi = r['range'] or (0, 100)
                lines.append(f'{names[uid]}.SetRange({lo!r}, {hi!r})')
        if groups:
            lines += ['', '# One selection at a time: SetCurrent sets the chosen button On and the',
                      '# rest Off.']
            for g, ids in groups.items():
                members = ', '.join(names[i] for i in ids)
                lines.append(f'sel_{_slug(g) or "group"} = MESet([{members}])  # {g!r}')
        return '\n'.join(lines) + '\n'

    def _action_code(self, a, slider=False):
        do = a['do']
        if do == 'show_page':
            return f"ui.TLP.ShowPage({a['target']!r})"
        if do == 'show_popup':
            if a['duration']:
                return f"ui.TLP.ShowPopup({a['target']!r}, {a['duration']!r})"
            return f"ui.TLP.ShowPopup({a['target']!r})"
        if do == 'hide_popup':
            return f"ui.TLP.HidePopup({a['target']!r})"
        if do == 'hide_all_popups':
            return 'ui.TLP.HideAllPopups()'
        args = [f'{k}={v!r}' for k, v in a['args'].items()]
        if slider:
            args.append('value=value')
        return f"devices.{a['device']}.{a['op']}({', '.join(args)})"

    def _ui_events(self, sha):
        names = self.names()
        lines = [self._banner(sha, 'Every panel event handler.'),
                 '# To replace a handler, re-register it with @event in main.py after',
                 '# importing this module: extronlib keeps the last handler assigned.',
                 'from extronlib import event',
                 '',
                 'import devices',
                 'import ui_objects as ui',
                 '',
                 f'START_PAGE = {self.start_page!r}']
        secs = None
        if self.inactivity and isinstance(self.inactivity, dict):
            secs = self.inactivity.get('seconds')
            lines += [f'INACTIVITY_SECONDS = [{secs!r}]',
                      'ui.TLP.SetInactivityTime(INACTIVITY_SECONDS)']
        lines += ['', '',
                  "@event(ui.TLP, 'Online')",
                  'def _tlp_online(tlp, state):',
                  '    # The panel boots into START_PAGE by itself; this re-syncs it when the',
                  '    # processor restarts while the panel stays up.']
        if secs:
            lines.append('    ui.TLP.SetInactivityTime(INACTIVITY_SECONDS)')
        lines.append('    ui.TLP.ShowPage(START_PAGE)')
        if secs:
            lines += ['', '',
                      "@event(ui.TLP, 'InactivityChanged')",
                      'def _tlp_inactivity(tlp, seconds):']
            body = [self._action_code(a) for a in self.inactivity_actions] or ['pass']
            lines += ['    ' + b for b in body]
        sel = {}
        for g, ids in self.select_groups().items():
            for i in ids:
                sel[i] = f'ui.sel_{_slug(g) or "group"}'
        for uid, recs in self.addressed().items():
            r = recs[0]
            events = collections.OrderedDict(r['events'])
            if uid in sel and 'Pressed' not in events:
                events['Pressed'] = []
            for event, acts in events.items():
                slider = r['kind'] == 'slider'
                args = '(slider, state, value)' if slider else '(button, state)'
                body = []
                if event == 'Pressed' and uid in sel:
                    body.append(f'{sel[uid]}.SetCurrent(button)')
                body += [self._action_code(a, slider) for a in acts]
                lines += ['', '',
                          f'@event(ui.{names[uid]}, {event!r})',
                          f'def _{names[uid].split("_")[0]}_{uid}_{event.lower()}{args}:']
                lines += ['    ' + b for b in (body or ['pass'])]
        return '\n'.join(lines) + '\n'

    def _ui_feedback(self, sha):
        names = self.names()
        lines = [self._banner(sha, 'Setters for device state the panel shows.'),
                 '# Call these from devices.py when a device reports a change, e.g.',
                 '#     import ui_feedback; ui_feedback.audio_muted(True)',
                 'import ui_objects as ui']
        setter = {'button': '{0}.SetState(1 if value else 0)',
                  'label': '{0}.SetText(str(value))',
                  'level': '{0}.SetLevel(int(value))',
                  'slider': '{0}.SetFill(int(value))'}
        for path, recs in self.binds().items():
            ids = []
            for r in recs:
                if r['id'] not in ids:
                    ids.append(r['id'])
            where = ', '.join(f"{CLASS_OF[self.control(i)['kind']]} {i}" for i in ids)
            lines += ['', '', f"def {path.replace('.', '_')}(value):",
                      f'    # {path!r} -> {where}']
            for i in ids:
                lines.append('    ' + setter[self.control(i)['kind']].format(f'ui.{names[i]}'))
        return '\n'.join(lines) + '\n'

    def _devices(self):
        calls = self.calls()
        lines = ['# Created once by `python -m gdl.behavior generate` and never overwritten -',
                 '# this file is yours. Replace each stub body with the real device control.',
                 '# `generate` reports any op the spec calls that this file lacks.',
                 '# To show device state on the panel: import ui_feedback, then e.g.',
                 '#     ui_feedback.audio_muted(True)',
                 'from extronlib.system import ProgramLog']
        objects = []
        for dev, note in self.devices.items():
            if not _ident(dev):
                continue
            cls = _camel(dev)
            objects.append(f'{dev} = {cls}()')
            lines += ['', '', f'class {cls}:', f'    # {str(note)!r}']
            ops = [(op, spec) for (d, op), spec in calls.items() if d == dev]
            if not ops:
                lines.append('    pass')
            for op, spec in ops:
                lines += [''] + self._stub(dev, op, spec)
        lines += ['', ''] + objects
        return '\n'.join(lines) + '\n'

    @staticmethod
    def _params(spec):
        """An op's parameters: every argument name its callers pass, plus the
        value= a slider passes. Deduplicated - a preset button passing value=3
        and a slider passing its own value= to one op mean ONE `value`, and a
        repeated parameter is a SyntaxError that ast.parse does not catch."""
        return list(spec['args']) + (['value'] if spec['value']
                                     and 'value' not in spec['args'] else [])

    @classmethod
    def _stub(cls, dev, op, spec):
        params = cls._params(spec)
        sig = ', '.join(['self'] + [f'{p}=None' for p in params])
        shown = ', '.join(f'{p}={{{i}!r}}' for i, p in enumerate(params))
        fmt = f'.format({", ".join(params)})' if params else ''
        return [f'    def {op}({sig}):',
                f"        ProgramLog('stub: {dev}.{op}({shown})'{fmt}, 'warning')"]

    def _main(self):
        return ('# Entry point - created once by `python -m gdl.behavior generate`, then yours.\n'
                "# Make this the entry file in Global Scripter's System Manager.\n"
                'from extronlib import Version\n'
                'from extronlib.system import ProgramLog\n'
                '\n'
                'import devices    # noqa: F401 - your device objects\n'
                'import ui_events  # noqa: F401 - registers every panel handler on import\n'
                '\n'
                "ProgramLog('program started, ControlScript {0}'.format(Version()), 'info')\n")

    def device_drift(self, path):
        """Ops the spec calls that an existing devices.py does not define.

        Read with `ast`, not imported: devices.py imports extronlib, which only
        exists on a processor.
        """
        import ast
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
        except SyntaxError as e:
            return [f'{path} does not parse ({e}), so its device ops cannot be checked']
        classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        objects, bound = {}, set()
        for n in tree.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                bound |= {(a.asname or a.name).split('.')[0] for a in n.names}
            if not isinstance(n, ast.Assign):
                continue
            pairs = []
            for t in n.targets:
                if isinstance(t, ast.Name):
                    pairs.append((t, n.value))
                elif isinstance(t, ast.Tuple) and isinstance(n.value, ast.Tuple):
                    pairs += list(zip(t.elts, n.value.elts))
            for t, v in pairs:
                if not isinstance(t, ast.Name):
                    continue
                bound.add(t.id)
                if isinstance(v, ast.Call) and isinstance(v.func, ast.Name):
                    objects[t.id] = v.func.id
        out = []
        # Where a device comes from somewhere this cannot read - a class
        # imported from its own module, a factory - its ops cannot be checked
        # here. Say so rather than calling it missing: splitting drivers into
        # their own files is ordinary.
        self.drift_notes = []
        for (dev, op), spec in self.calls().items():
            cls = classes.get(objects.get(dev))
            if cls is None:
                if dev in bound:
                    note = (f'devices.py builds {dev!r} from outside the file, so its ops '
                            f'cannot be checked here')
                    if note not in self.drift_notes:
                        self.drift_notes.append(note)
                else:
                    out.append(f'devices.py has no {dev!r} object - the program calls '
                               f'{dev}.{op}()')
                continue
            fn = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == op),
                      None)
            want = self._params(spec)
            if fn is None:
                out.append(f'devices.py: {dev} has no {op}() - paste into class '
                           f"{cls.name}:\n" + '\n'.join(self._stub(dev, op, spec)))
                continue
            have = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
            missing = [w for w in want if w not in have]
            if missing and fn.args.kwarg is None:
                out.append(f"devices.py: {dev}.{op}() does not take {', '.join(missing)}, "
                           f'which the spec passes')
        return out

    # -- handoff ---------------------------------------------------------------
    def handoff(self, sha):
        names = self.names()
        controls = []
        for uid, recs in self.addressed().items():
            r = recs[0]
            ev = collections.OrderedDict()
            for event, acts in r['events'].items():
                ev[event] = [self._describe(a) for a in acts]
            controls.append({
                'id': uid, 'class': CLASS_OF[r['kind']], 'python': names[uid],
                'at': [{'container': x['container'], 'name': x['name'], 'text': x['text']}
                       for x in recs],
                'events': ev, 'bind': r['bind'], 'select_group': r['select_group'],
                # Structured, for tests/verify_behavior.py: a donor control
                # sharing this ID would run the call with no confirmation.
                'costly': any(a['do'] == 'call' and a['costly']
                              for acts in r['events'].values() for a in acts),
                'hold_time': r['hold_time'], 'repeat_time': r['repeat_time'],
                'range': (r['range'] or [0, 100]) if r['kind'] in ('level', 'slider') else None,
            })
        return {
            'generated_by': 'gdl.behavior',
            'spec': os.path.basename(self.spec_path) if self.spec_path else None,
            'spec_sha256': sha,
            'panel_alias': self.alias,
            'start_page': self.start_page,
            'pages': [{'name': ct['name'], 'reached_by': ct['reached_by']}
                      for ct in self.containers if ct['kind'] == 'page'],
            'popups': [{'name': ct['name'], 'modal': ct['modal'], 'group': ct['group'],
                        'reached_by': ct['reached_by']}
                       for ct in self.containers if ct['kind'] == 'popup'],
            'controls': controls,
            'select_groups': {g: ids for g, ids in self.select_groups().items()},
            'feedback': {p: {'type': BIND_TYPE[recs[0]['kind']],
                             'ids': sorted({r['id'] for r in recs}),
                             'python': 'ui_feedback.' + p.replace('.', '_')}
                         for p, recs in self.binds().items()},
            'devices': {d: {'note': n,
                            'ops': {op: self._params(spec)
                                    for (dd, op), spec in self.calls().items() if dd == d}}
                        for d, n in self.devices.items()},
            'inactivity': ({'seconds': self.inactivity.get('seconds'),
                            'do': [self._describe(a) for a in self.inactivity_actions]}
                           if isinstance(self.inactivity, dict) else None),
            'navigation': sorted([list(e) for e in self.nav_edges()]),
        }

    @staticmethod
    def _describe(a):
        do = a['do']
        if do == 'call':
            args = ', '.join(f'{k}={v!r}' for k, v in a['args'].items())
            return f"{a['device']}.{a['op']}({args})" + (' [costly]' if a['costly'] else '')
        if do == 'show_popup' and a.get('duration'):
            return f"show popup {a['target']!r} for {a['duration']}s"
        if do in ('show_page', 'show_popup', 'hide_popup'):
            return f"{do.replace('_', ' ')} {a['target']!r}"
        return 'hide all popups'

    def _handoff_md(self, sha):
        h = self.handoff(sha)
        out = [f"# Program handoff: {self.spec.get('name') or h['spec'] or 'panel'}", '',
               f"Generated by `python -m gdl.behavior generate` from `{h['spec']}` "
               f"(spec sha256 `{sha[:12]}`). Regenerate rather than edit.", '',
               f"**Before anything runs:** in Global Scripter's System Manager, assign the "
               f"built `.gdl` to a UI Device whose alias is `{h['panel_alias']}`. The code "
               f'addresses the panel by that alias and never names the file.', '',
               'Controls are addressed by **ID**. Pages and popups are addressed by **name** - '
               "Build does not keep a page's number.", '',
               f"The panel boots into **{h['start_page']}**.", '',
               '## Pages and popups', '',
               '| Name | Kind | Shown by |', '|---|---|---|']
        into = collections.defaultdict(list)
        for s, t in h['navigation']:
            into[t].append(s)
        for pg in h['pages']:
            by = 'boot' if pg['name'] == h['start_page'] else ''
            by = ', '.join(x for x in [by] + sorted(into[pg['name']]) if x)
            if pg['reached_by'] == 'program':
                by = (by + ', ' if by else '') + '**your code**'
            out.append(f"| {_cell(pg['name'])} | page | {_cell(by) or '-'} |")
        for pu in h['popups']:
            kind = 'modal popup' if pu['modal'] else f"popup, group {pu['group']}"
            by = ', '.join(sorted(into[pu['name']]))
            if pu['reached_by'] == 'program':
                by = (by + ', ' if by else '') + '**your code**'
            out.append(f"| {_cell(pu['name'])} | {_cell(kind)} | {_cell(by) or '-'} |")
        out += ['', '## Controls', '',
                '| ID | Class | Where | Caption | Does |', '|---|---|---|---|---|']
        for c in h['controls']:
            where = _cell('; '.join(f"{a['container']} / {a['name']}" for a in c['at']))
            caption = _cell(c['at'][0]['text'] or '')
            does = []
            for event, acts in c['events'].items():
                does.append(f"{event}: {'; '.join(acts) or '-'}")
            if c['select_group']:
                does.append(f"selects in {c['select_group']!r}")
            if c['bind']:
                does.append(f"shows `{c['bind']}`")
            if c['hold_time']:
                does.append(f"hold {c['hold_time']}s" + (f", repeat {c['repeat_time']}s"
                                                          if c['repeat_time'] else ''))
            out.append(f"| {c['id']} | {c['class']} | {where} | {caption} | "
                       f"{'<br>'.join(does).replace('|', '/') or '-'} |")
        if h['feedback']:
            out += ['', '## Feedback the program must push', '',
                    '| Path | Type | IDs | Call |', '|---|---|---|---|']
            for p, f in h['feedback'].items():
                out.append(f"| `{p}` | {f['type']} | {', '.join(map(str, f['ids']))} | "
                           f"`{f['python']}(value)` |")
        if h['devices']:
            out += ['', '## Device operations to implement in `devices.py`', '']
            for d, info in h['devices'].items():
                out.append(f"- **{d}** - {info['note']}")
                for op, args in info['ops'].items():
                    out.append(f"  - `{op}({', '.join(args)})`")
        if h['inactivity']:
            out += ['', f"After **{h['inactivity']['seconds']} s** without a touch: "
                        f"{'; '.join(h['inactivity']['do']) or 'nothing'}."]
        out += ['', '## Not proven here', '',
                'This program has been checked against the built panel and exercised against a '
                'simulated extronlib. It has not run on a control processor.']
        return '\n'.join(out) + '\n'


def load(path):
    return Program(Panel.load(path), spec_path=path)


def main(argv):
    if len(argv) < 3 or argv[1] not in ('check', 'generate') or \
            (argv[1] == 'generate' and len(argv) < 4):
        print(__doc__.strip().split('\n\n')[0])
        print('\n  python -m gdl.behavior check    <spec.json>'
              '\n  python -m gdl.behavior generate <spec.json> <out_dir>')
        return 2
    prog = load(argv[2])
    problems, notes = prog.check()
    for p in problems:
        print('  ' + p)
    for n in notes:
        print('  note: ' + n)
    if argv[1] == 'check':
        print(f'{len(problems)} problem(s), {len(notes)} note(s); '
              f'{len(prog.addressed())} addressable control(s), '
              f'{len(prog.nav_edges())} navigation edge(s)')
        return 1 if problems else 0
    if problems:
        print(f'{len(problems)} problem(s) - nothing generated')
        return 1
    written, drift = prog.generate(argv[3])
    for w in written:
        print(f'  wrote {w}')
    for d in drift:
        print('  ' + d)
    for n in prog.drift_notes:
        print('  note: ' + n)
    print(f'{len(written)} file(s) -> {argv[3]}; {len(drift)} device op(s) missing')
    return 1 if drift else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
