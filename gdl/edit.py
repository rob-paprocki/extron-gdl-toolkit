"""Describe a change to an EXISTING panel, and emit the ops that make it.

`gdl/spec.py` builds a panel from nothing. This is the other half of the job and
the more common one: a client project already exists and someone wants the
buttons renamed, the whole thing moved to a bigger panel, the IDs renumbered, or
the colors restyled.

Same architecture, for the same reason: every decision is made here, in Python,
where it can be tested against a real `.gdl` on a Mac, and `Apply-GdlEdits.ps1`
only applies what it is told. The Windows box is the slow, scarce resource - it
should never be where a selector gets debugged.

    python -m gdl.edit check <edits.json> <panel.gdl>
    python -m gdl.edit plan  <edits.json> <panel.gdl> out/edits-plan.json

The five operations:

  rename    change captions, state by state. A button renders from its states,
            and they need not all say the same thing.
  restyle   remap colors across the whole project, on each state's own colors
            as well as the control's.
  states    give a button the states it should have: add, remove or rename
            them, and set how each looks.
  retarget  move the project to another panel model. Sets the three fields that
            have to agree (platform instance, platform type enum, screen size)
            and optionally rescales the layout.
  renumber  reassign the addressable IDs (`userIdField`) in per-page bands.

Selectors are ANDed, and every one of them is resolved against the real project
here, so `check` can say "this matched nothing" instead of the edit silently
doing nothing on Windows - which is the failure mode that makes this kind of
tool untrustworthy.

A control op writes the control's own `fields` and `colors`, and each state it
touches through `per_state`, which addresses the state by index. The index is
what the control program sets, so it is also what the edit has to be exact
about.
"""
import json
import re
import sys

from .project import Project
from .spec import (HEX, MAX_STATES, MODELS, PRESS_FIELD, DEFAULT_FIELD, dpi,
                   touch_minimums, MM_TOUCH_TARGET)

# The colors `restyle` rewrites, on the control and on each state: the field,
# and the key gdl/project.py reads it into.
COLOR_KEYS = (('borderFillColorField', 'fill'), ('borderColorField', 'stroke'),
              ('textColorField', 'text_color'))

# What a state in a `states` edit may set. `color` is the text color, spelled
# as the spec spells it. No border: a border is a named resource, and the edit
# applier writes colors and captions only.
STATE_KEYS = {'name', 'text', 'fill', 'stroke', 'color'}


def _argb_hex(c):
    """The reader's {'A','R','G','B'} -> '#AARRGGBB', for matching and reports."""
    if not c:
        return None
    return '#{:02X}{:02X}{:02X}{:02X}'.format(c['A'], c['R'], c['G'], c['B'])


def _norm(v):
    """Any accepted color spelling -> '#AARRGGBB'. '#RRGGBB' means opaque."""
    if v is None:
        return None
    if isinstance(v, dict):
        return _argb_hex(v)
    s = str(v).upper().lstrip('#')
    if len(s) == 6:
        s = 'FF' + s
    return '#' + s


def _captions(c):
    """Everything a control says: its caption, and each state's."""
    return [c['caption'] or ''] + [s['caption'] or '' for s in c.get('states') or []]


def _label(pg, c):
    return f"{pg['name']!r} {c['name'] or c['caption'] or c['type']}"


class Edits:
    """An edit spec resolved against one real project."""

    def __init__(self, spec, path):
        self.spec = spec
        self.path = path
        self.project = Project.open(path)
        self.pages = list(self.project.pages())
        self.edits = spec.get('edits') or []

    @classmethod
    def load(cls, spec_path, gdl_path):
        # UTF-8, not the locale codepage - see the note in gdl/spec.py.
        with open(spec_path, encoding='utf-8') as fh:
            return cls(json.load(fh), gdl_path)

    # -- selection ---------------------------------------------------------
    def _pages_for(self, sel):
        """Pages a selector covers. No `page` key means every page and popup."""
        want = sel.get('page')
        if want is None:
            return self.pages
        wants = want if isinstance(want, list) else [want]
        out = []
        for pg in self.pages:
            if pg['name'] in wants or pg['id'] in wants:
                out.append(pg)
        return out

    def select(self, sel):
        """(page, control) pairs matching a selector.

        Keys are ANDed. `text` and `name` are exact; `text_matches` and
        `name_matches` are regexes, because "every button whose caption starts
        with Cam" is the request people actually have. `text` matches a caption
        in any state, so a button that says 'Display Off' and 'Display On' is
        found by either.
        """
        sel = sel or {}
        out = []
        for pg in self._pages_for(sel):
            for c in pg['controls']:
                if 'type' in sel and c['type'] != sel['type']:
                    continue
                if 'name' in sel and c['name'] != sel['name']:
                    continue
                # Match on the CAPTION, not on textField: a button's wording
                # usually lives in its state, so selecting on the control's own
                # text silently matches nothing. See Project.caption_at().
                if 'text' in sel and sel['text'] not in _captions(c):
                    continue
                if 'id' in sel and c['id'] != sel['id']:
                    continue
                if 'name_matches' in sel and not re.search(sel['name_matches'],
                                                           c['name'] or ''):
                    continue
                if 'text_matches' in sel and not any(
                        re.search(sel['text_matches'], t) for t in _captions(c)):
                    continue
                out.append((pg, c))
        return out

    # -- the ops -----------------------------------------------------------
    def _rename(self, e, ops, problems):
        """Captions, state by state.

        `map` renames whatever says the old caption, and only that: a button
        saying 'Display Off' and 'Display On' keeps 'Display On' when the map
        names only the first. `text` renames the whole control, and so is
        refused on a button whose states say different things - one caption
        on every state would erase the feedback wording. `state` narrows it to
        the states named.
        """
        pairs = e.get('map')
        names = e.get('state')
        if names is not None:
            names = names if isinstance(names, list) else [names]
            if pairs:
                problems.append("rename: `state` goes with `text` - `map` already picks "
                                'the states that say each old caption')
                return
        if pairs:
            # {"old caption": "new caption"} across whatever the selector covers.
            base = e.get('select') or {}
            for old, new in pairs.items():
                hits = self.select(dict(base, text=old))
                if not hits:
                    problems.append(f'rename: nothing has the caption {old!r}'
                                    + (f" under {base}" if base else ''))
                for pg, c in hits:
                    ops.append(self._text_op(pg, c, new, match=old))
            return
        new = e.get('text')
        if new is None:
            problems.append("rename: needs either 'text' or 'map'")
            return
        hits = self.select(e.get('select'))
        if not hits:
            problems.append(f"rename: selector {e.get('select')} matched nothing")
        for pg, c in hits:
            states = c.get('states') or []
            if names is not None:
                have = [s['name'] for s in states]
                missing = [n for n in names if n not in have]
                if missing:
                    problems.append(f"rename: {_label(pg, c)} has no state "
                                    f"{', '.join(map(repr, missing))} - its states are "
                                    f"{', '.join(map(repr, have)) or 'none'}")
                    continue
            elif c.get('caption_in') in ('state', 'fstate') and \
                    len({s['caption'] or '' for s in states}) > 1:
                says = ', '.join(f"{s['name']} {s['caption'] or ''!r}" for s in states)
                problems.append(f'rename: {_label(pg, c)} says something different in '
                                f'each state ({says}) - one caption on every state '
                                f'would erase that. Give `state` to rename some of '
                                f'them, or `map` each old caption to its new one')
                continue
            ops.append(self._text_op(pg, c, new, names=names))

    def _text_op(self, pg, c, new, match=None, names=None):
        """Write the caption back where the old one was, in each state it is in.

        `caption_in` says which of the three places holds it. Writing the wrong
        one leaves the original text showing - the control still has it, and
        whichever field the renderer prefers wins. Each state is written where
        its own caption lives, and only the states that `match` the old
        caption, or are `names`d, are written at all.
        """
        states = c.get('states') or []
        op = {'page': pg['id'], 'control': c['obj_id'],
              'was': match if match is not None else c['caption'],
              'why': f'rename {match if match is not None else c["caption"]!r} -> {new!r}'}
        if c.get('caption_in') in (None, 'control') and not names:
            # No caption anywhere (an icon-only button), or it is on the
            # control. Set both: a button renders from its state, and a caption
            # written only on the control builds blank.
            op['fields'] = {'textField': new}
            op['per_state'] = [{'index': i, 'fields': {'textField': new}}
                               for i in range(len(states))]
            return op
        per = []
        for i, s in enumerate(states):
            if names is not None and s['name'] not in names:
                continue
            if match is not None and (s['caption'] or '') != match:
                continue
            entry = {'index': i, 'was': s['caption']}
            if s['caption_in'] == 'fstate':
                # Formatted text carries tab/CRLF layout markers that are part
                # of how it draws; the applier keeps the original's leading
                # whitespace and replaces the words.
                entry.update(ftext=new, flattened=True)
            else:
                entry['fields'] = {'textField': new}
            per.append(entry)
        op['per_state'] = per
        return op

    def _renumber(self, e, ops, problems):
        """Fresh `userIdField`s in a per-page band.

        This changes the numbers a control system talks to. That is the point,
        but it also means the control program has to change with it, so the
        plan records every old -> new pair for whoever has to do that.
        """
        start = e.get('start')
        step = e.get('step', 1)
        if start is None:
            problems.append("renumber: needs 'start'")
            return
        hits = self.select(e.get('select'))
        if not hits:
            problems.append(f"renumber: selector {e.get('select')} matched nothing")
        # Only controls that are actually addressable are worth a number.
        n = int(start)
        taken = set()
        for pg, c in hits:
            while n in taken:
                n += step
            ops.append({'page': pg['id'], 'control': c['obj_id'],
                        'was': c['id'], 'why': f'renumber id {c["id"]} -> {n}',
                        'fields': {'userIdField': n}})
            taken.add(n)
            n += step

    def _restyle(self, e, ops, problems):
        """Remap colors project-wide, or under a selector.

        Each state is remapped from its OWN colors. A button's look lives on
        its states - 288 of the 442 buttons in the Liberty Bank fixture have no
        fill of their own - so matching only the control's colors missed most
        buttons, and writing the control's new color to every state would have
        painted an On state the Off color.
        """
        table = {_norm(k): _norm(v) for k, v in (e.get('map') or {}).items()}
        if not table:
            problems.append("restyle: needs a 'map' of old color -> new color")
            return
        hits = self.select(e.get('select'))
        seen = set()

        def remap(look):
            changes = {}
            for field, key in COLOR_KEYS:
                have = _norm(look.get(key))
                if have:
                    seen.add(have)
                if have in table:
                    changes[field] = table[have]
            return changes

        for pg, c in hits:
            own = remap(c)
            per = [{'index': i, 'colors': ch}
                   for i, ch in enumerate(remap(s) for s in c.get('states') or []) if ch]
            if own or per:
                op = {'page': pg['id'], 'control': c['obj_id'],
                      'why': f'restyle {c["name"] or c["type"]}'}
                if own:
                    op['colors'] = own
                if per:
                    op['per_state'] = per
                ops.append(op)
        self._unused_colors += [k for k in table if k not in seen]

    def _states(self, e, ops, problems):
        """Give a button exactly the states `states` lists, matched by NAME.

        A name the button already has keeps that state - its look, caption
        and press role - wherever it moves in the list. Any other name
        renames the state at its position if nothing else claimed it, and
        otherwise starts as a copy of the last state. Existing states nobody
        claimed are dropped. Anything a state names is written over what it
        starts from.

        By name because a position is not an identity: matched by index,
        inserting 'Middle' before 'On' left the press pointer on index 1 -
        now Middle - and gave 'On' the look of whatever used to be third, and
        every check still passed, because the plan itself was wrong.
        """
        want = e.get('states')
        if not isinstance(want, list) or not want:
            problems.append('states: needs `states`, a list of at least one state')
            return
        specs = [dict(s) if isinstance(s, dict) else {'name': s} for s in want]
        bad = self._state_spec_problems(specs, e.get('press'))
        if bad:
            problems += bad
            return
        hits = self.select(e.get('select'))
        if not hits:
            problems.append(f"states: selector {e.get('select')} matched nothing")
        names = [s['name'] for s in specs]
        for pg, c in hits:
            where = f'states: {_label(pg, c)}'
            have = c.get('states') or []
            if c['type'] != 'PBButton':
                problems.append(f"{where} is a {c['type']} - only a button has "
                                f'feedback states')
                continue
            if not have:
                problems.append(f'{where} has no state to copy a new one from')
                continue
            order, kept = self._state_sources(names, [s['name'] for s in have])
            if c.get('state_flags') and order != list(range(len(have))):
                problems.append(f"{where}: its states carry status flags "
                                f"{c['state_flags']}, which may forbid adding, removing "
                                f'or reordering them; the applier will not change them')
                continue
            per, looks = [], []
            for i, s in enumerate(specs):
                src = have[order[i]]
                entry = {'index': i, 'fields': {'nameField': s['name']}}
                colors = {field: _norm(s[k]) for field, k in
                          (('borderFillColorField', 'fill'), ('borderColorField', 'stroke'),
                           ('textColorField', 'color')) if k in s}
                if colors:
                    entry['colors'] = colors
                if 'text' in s:
                    if src['caption_in'] == 'fstate':
                        entry.update(ftext=s['text'], flattened=True, was=src['caption'])
                    else:
                        entry['fields']['textField'] = s['text']
                per.append(entry)
                looks.append({
                    'name': s['name'],
                    'text': s['text'] if 'text' in s else (src['caption'] or ''),
                    'fill': _norm(s['fill']) if 'fill' in s else _norm(src['fill']),
                    'stroke': _norm(s['stroke']) if 'stroke' in s else _norm(src['stroke']),
                    'text_color': (_norm(s['color']) if 'color' in s
                                   else _norm(src['text_color'])),
                    # Which existing state it starts as. Two states that start
                    # as the same one share everything this cannot see - icon,
                    # border, image - so only they can be compared exactly.
                    'from': order[i],
                })
            for i, a in enumerate(looks):
                for b in looks[i + 1:]:
                    if a['from'] == b['from'] and all(
                            a[k] == b[k] for k in ('text', 'fill', 'stroke', 'text_color')):
                        problems.append(
                            f"{where}: {a['name']!r} and {b['name']!r} would look "
                            f'identical - a new state is a copy of the last one, so '
                            f'give it its own fill, stroke, color or text')
            ops.append({
                'page': pg['id'], 'control': c['obj_id'],
                'why': f"states {c['name'] or c['type']}: {', '.join(names)}",
                'was': [s['name'] for s in have],
                'state_count': len(specs),
                # For each new state, the existing state it is taken from; a
                # source used twice is copied. The applier rebuilds the list
                # in this order.
                'state_order': order,
                'fields': {PRESS_FIELD: self._follow(c.get('press'), kept, names,
                                                     e.get('press')),
                           DEFAULT_FIELD: self._follow(c.get('default_state'), kept,
                                                       names, None, fallback=0)},
                'per_state': per,
                # What every state should look like once built, for
                # verify_built - including the ones this op does not write.
                'expect_states': [{k: v for k, v in lk.items() if k != 'from'}
                                  for lk in looks],
            })

    @staticmethod
    def _state_sources(names, old):
        """(order, kept): for each wanted state, the index of the existing
        state it is taken from - see _states for the rule - and, for each
        existing state that survives as itself, its new position.

        `kept` is what a pointer follows. A copy of a state is not that state:
        Warming, copied from On and listed before it, must not take On's
        press role.
        """
        claimed = {n: old.index(n) for n in names if n in old}
        taken = set(claimed.values())
        order, kept = [], {}
        for i, n in enumerate(names):
            if n in claimed:
                order.append(claimed[n])
                kept[claimed[n]] = i
            elif i < len(old) and i not in taken:
                order.append(i)                 # renamed in place
                taken.add(i)
                kept[i] = i
            else:
                order.append(len(old) - 1)      # a copy of the last
        return order, kept

    @staticmethod
    def _follow(pointer, kept, names, named, fallback=None):
        """Where a state pointer lands after the states are rebuilt.

        It follows the state it pointed at. If that state was dropped, it goes
        to 'On' - the press state of all 7518 Off/On buttons in the corpus -
        or to the second state, or the first.
        """
        if named is not None:
            return names.index(named)
        if pointer is not None and pointer in kept:
            return kept[pointer]
        if fallback is not None:
            return fallback
        if 'On' in names:
            return names.index('On')
        return 1 if len(names) > 1 else 0

    @staticmethod
    def _state_spec_problems(specs, press):
        out = []
        if len(specs) > MAX_STATES:
            out.append(f'states: {len(specs)} is more than the {MAX_STATES} GUI Designer '
                       f'allows on a button')
        names = []
        for i, s in enumerate(specs):
            extra = sorted(set(s) - STATE_KEYS)
            if extra:
                out.append(f"states: state {i} has unknown key(s) {', '.join(extra)} - a "
                           f"state takes {', '.join(sorted(STATE_KEYS))}")
            nulls = sorted(k for k in STATE_KEYS if k in s and s[k] is None)
            if nulls:
                out.append(f"states: state {i}: {', '.join(nulls)} is null - leave the key "
                           f'out to keep what the state has')
            for k in ('fill', 'stroke', 'color'):
                if s.get(k) is not None and not HEX.match(str(s[k])):
                    out.append(f'states: state {i}: {k} {s[k]!r} is not #RRGGBB or '
                               f'#AARRGGBB')
            n = s.get('name')
            if not isinstance(n, str) or not n.strip():
                out.append(f'states: state {i} has no name - a state is a name, or an '
                           f'object with a name')
                continue
            names.append(n)
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            out.append(f"states: state name(s) {', '.join(map(repr, dup))} used twice - "
                       f'the program and the ID map tell states apart by name')
        if press is not None and press not in names:
            out.append(f"states: press {press!r} is not one of the states "
                       f"({', '.join(map(repr, names))})")
        return out

    def _retarget(self, e, ops, problems, project_ops, page_ops):
        """Move the project to another panel model.

        Three fields have to agree or GUI Designer is being told two different
        things about what it is building for: the platform INSTANCE
        (`platformField`, a `PBTouchPanelPlatformPro` subclass), the enum
        (`platformTypeField`) and `screenSizeField`. The applier constructs the
        class, because a platform is one of the few objects that does construct
        headlessly - it holds no project state.

        Every PAGE also carries its own canvas, and scaling the controls without
        scaling the canvas is the silent-destruction case: Build moves anything
        that no longer fits to 0,0 and reports nothing. The applier used to set
        every page - popups included - to the new SCREEN size, on the belief
        that a popup's authored size is always the full canvas. That came from
        the Liberty Bank fixture, where every popup happens to be full-canvas,
        and it is wrong: 10 of the 29 popups in Extron's own Afterburn template
        are authored at 880x525, and the built layout.json reports 880x525 for
        them. Blowing those up to the screen size turns a modal card into a
        full-screen page.

        So scale each page's own canvas by the same per-axis factors as its
        controls. A full-canvas popup lands exactly on the screen size
        (1280*1.5, 800*1.35 -> 1920x1080), and a genuinely small one keeps its
        proportions. What matters is that canvas and contents move together, so
        nothing can overflow that did not overflow before.
        """
        model = e.get('model')
        if model not in MODELS:
            near = [m for m in MODELS if str(model).upper() in m.upper()]
            problems.append(f'retarget: {model!r} is not a panel GUI Designer builds for'
                            + (f'; did you mean {", ".join(sorted(near))}?' if near else ''))
            return None
        new_size = MODELS[model]
        self._model = model
        old_size = self._screen_size()
        # No `platform_class` hint here on purpose. It used to carry
        # f'Extron.GUICPro.PB{model}Platform', which is wrong for 9 of the 55
        # models - TLP720T is PBTLP720TVPlatform, TLP1230WTG is the bare
        # PBTouchPanelPlatformPro, and so on. Nothing read it: the applier
        # resolves the class through Enum.Parse + CreatePlatform, which is
        # Extron's own code and always right. A hint that is wrong 16% of the
        # time and authoritative 0% of the time is worse than no hint.
        project_ops.append({'why': f'retarget to {model} ({new_size[0]}x{new_size[1]})',
                            'model': model, 'size': list(new_size)})
        if not e.get('scale'):
            return old_size, new_size
        if not old_size:
            problems.append('retarget: cannot scale - the project has no screen size')
            return old_size, new_size
        sx = new_size[0] / old_size[0]
        sy = new_size[1] / old_size[1]
        self._scale = (sx, sy)
        for pg in self.pages:
            pw, ph = pg['size']
            if None not in (pw, ph):
                page_ops.append({
                    'page': pg['id'], 'name': pg['name'], 'kind': pg['kind'],
                    'why': f'scale canvas {sx:.4g}x{sy:.4g}',
                    'was': [pw, ph],
                    'size': [round(pw * sx), round(ph * sy)],
                })
            for c in pg['controls']:
                x, y, w, h = c['rect']
                if None in (x, y, w, h):
                    continue
                ops.append({
                    'page': pg['id'], 'control': c['obj_id'],
                    'why': f'scale {sx:.4g}x{sy:.4g}',
                    'fields': {'leftField': round(x * sx), 'topField': round(y * sy),
                               'widthField': round(w * sx), 'heightField': round(h * sy)},
                })
        return old_size, new_size

    def _screen_size(self):
        """The project's current canvas, taken from its own pages.

        `screenSizeField` lives on PBProject and the reader does not surface it,
        but a standard page IS the canvas, so the largest page is the panel.
        """
        best = None
        for pg in self.pages:
            if pg['kind'] != 'page':
                continue
            for c in pg['controls']:
                x, y, w, h = c['rect']
                if None in (w, h):
                    continue
                if best is None or w * h > best[0] * best[1]:
                    best = (w, h)
        return best

    # -- plan and checks ---------------------------------------------------
    def plan(self):
        ops, project_ops, page_ops, problems = [], [], [], []
        self._resize = None
        self._model = None
        self._scale = None
        self._unused_colors = []
        for e in self.edits:
            op = e.get('op')
            if op == 'rename':
                self._rename(e, ops, problems)
            elif op == 'renumber':
                self._renumber(e, ops, problems)
            elif op == 'restyle':
                self._restyle(e, ops, problems)
            elif op == 'states':
                self._states(e, ops, problems)
            elif op == 'retarget':
                self._resize = self._retarget(e, ops, problems, project_ops, page_ops)
            else:
                problems.append(f'unknown op {op!r}')
        return {
            'generated_by': 'gdl.edit',
            'target': self.path,
            'note': ('Apply with powershell/Apply-GdlEdits.ps1 under 32-bit Windows '
                     'PowerShell 5.1, then verify the BUILT file - a clean build '
                     'does not mean a correct one.'),
            'project': project_ops,
            'pages': page_ops,
            'controls': ops,
        }, problems

    def check(self):
        """Everything that would otherwise be found on the Windows box.

        Two severities, because they are not the same kind of statement.
        An ERROR means the edit as written cannot be right - a selector matched
        nothing, a model does not exist, a control would be silently relocated.
        A WARNING is a judgement about the result: a button under Extron's touch
        minimum is bad design but a legal file, and on a real project a retarget
        surfaces dozens that were already there. Errors block the plan; warnings
        never do, or the tool would refuse to do the job it was asked to do.
        """
        plan, errors = self.plan()
        warnings = []

        # A formatted-text caption is baked INTO the artwork at build time, and
        # its tab/CRLF scaffolding is hand-placed per line. Renaming one works -
        # Build re-rasterizes and the new word appears - but a longer caption
        # wraps onto a second line that has none of that indent, so it starts at
        # x=0 on top of the icon. Measured: "Displays" -> "Screens" rasterizes
        # perfectly; "Cameras" -> "Camera Control" comes out as "Camera" over
        # "Control" hanging off the left edge. Nothing in the file says so - the
        # model reads correctly and only the pixels are wrong, exactly like the
        # flattenText trap.
        for o in plan['controls']:
            said = set()        # once per control, not once per state
            for ps in o.get('per_state') or []:
                if not ps.get('flattened'):
                    continue
                old, newt = ps.get('was') or '', ps['ftext']
                if len(newt.split()) <= len(old.split()) and len(newt) <= len(old):
                    continue
                if (old, newt) in said:
                    continue
                said.add((old, newt))
                warnings.append(
                    f'rename {old!r} -> {newt!r}: this caption is FORMATTED text baked '
                    f'into the artwork with hand-placed line breaks. The new text is '
                    f'longer, so it will wrap onto an unindented second line over the '
                    f"icon. Check the rasterized asset, don't trust the model.")

        # After the ops, does every control still fit its page? Build relocates
        # anything that does not to 0,0 - silently, with 0 errors reported - so
        # a retarget that shrinks the canvas destroys the layout and says
        # nothing. This is the check that makes retargeting safe to offer.
        moved = {(o['page'], o['control']): o['fields'] for o in plan['controls']
                 if 'leftField' in (o.get('fields') or {})}
        size = self._resize[1] if getattr(self, '_resize', None) else None
        if size:
            # Against each page's OWN new canvas, popups included. Checking only
            # standard pages was the blind spot that let the applier's blanket
            # popup resize through: popups are exactly where the canvas and the
            # screen are allowed to disagree, so they are the only place this
            # check could ever have fired.
            resized = {p['page']: p['size'] for p in plan['pages']}
            for pg in self.pages:
                canvas = resized.get(pg['id'])
                if canvas is None:
                    canvas = size if pg['kind'] == 'page' else pg['size']
                if not canvas or None in tuple(canvas):
                    continue
                for c in pg['controls']:
                    f = moved.get((pg['id'], c['obj_id']))
                    if f:
                        x, y, w, h = (f['leftField'], f['topField'],
                                      f['widthField'], f['heightField'])
                    else:
                        x, y, w, h = c['rect']
                    if None in (x, y, w, h):
                        continue
                    if x + w > canvas[0] or y + h > canvas[1]:
                        errors.append(
                            f"{pg['name']} {c['name'] or c['type']}: {x},{y} {w}x{h} "
                            f'falls outside the new {canvas[0]}x{canvas[1]} '
                            f"{'canvas' if pg['kind'] == 'page' else 'popup canvas'} - "
                            f'Build moves it to 0,0 without reporting anything')

            # Shrinking pixel-wise is not the same as shrinking physically. A
            # 1366x768 panel is bigger than a 1280x800 one, so scaling down can
            # still be legal; scaling to a denser panel is what breaks touch.
            target, _ = touch_minimums(self._model or size)
            if target:
                for pg in self.pages:
                    for c in pg['controls']:
                        if c['type'] not in ('PBButton', 'PBSlider'):
                            continue
                        f = moved.get((pg['id'], c['obj_id']))
                        w, h = ((f['widthField'], f['heightField']) if f
                                else (c['rect'][2], c['rect'][3]))
                        if None in (w, h):
                            continue
                        if w >= target and h >= target:
                            continue
                        # Was it already too small on the panel it is leaving?
                        # If so the retarget did not cause this, and saying so
                        # is the difference between a useful warning and noise.
                        was = ''
                        old_target, _ = touch_minimums(self._resize[0] or ())
                        ow, oh = c['rect'][2], c['rect'][3]
                        if old_target and None not in (ow, oh) and (
                                ow < old_target or oh < old_target):
                            was = ' (already under the old panel\'s minimum)'
                        warnings.append(
                            f"{pg['name']} {c['name'] or c['caption'] or c['type']}: "
                            f'{w}x{h} is under the {target}px touch target for a '
                            f'{self._model or f"{size[0]}x{size[1]}"} panel '
                            f'({MM_TOUCH_TARGET}mm at {dpi(self._model)} DPI){was}')

        # Every op is planned against the project as it is on disk, so a
        # `states` op cannot see what another op does to the same button's
        # states first - a rename before it, or a restyle of a state it is about
        # to drop. Say so rather than verify against the wrong expectation.
        touching = {}
        for o in plan['controls']:
            if o.get('per_state') is not None:
                touching.setdefault((o['page'], o['control']), []).append(o)
        for ops in touching.values():
            if len(ops) > 1 and any(o.get('state_count') is not None for o in ops):
                errors.append(
                    f"{' and '.join(o['why'].split()[0] for o in ops)} both change the "
                    f"states of control {ops[0]['control']} on page {ops[0]['page']} - put "
                    f"the caption or color in the `states` op, as that state's `text`, "
                    f'`fill`, `stroke` or `color`')

        # Renumbering to an ID something else already has is legal in the format
        # (Extron uses duplicates for feedback mirrors) but is almost never what
        # a renumber means.
        assigned = {}
        for o in plan['controls']:
            new = (o.get('fields') or {}).get('userIdField')
            if new is None:
                continue
            key = (o['page'], new)
            if key in assigned:
                errors.append(f'renumber: two controls on page {o["page"]} both get '
                              f'id {new}')
            assigned[key] = o['control']
        touched = {(o['page'], o['control']) for o in plan['controls']
                   if 'userIdField' in (o.get('fields') or {})}
        for pg in self.pages:
            for c in pg['controls']:
                if (pg['id'], c['obj_id']) in touched:
                    continue
                if (pg['id'], c['id']) in assigned:
                    errors.append(
                        f"renumber: id {c['id']} is being given to another control on "
                        f"{pg['name']}, but {c['name'] or c['type']} already has it")
        return plan, errors, warnings


def _summarise(plan):
    kinds = {}
    for o in plan['controls']:
        kinds[o['why'].split()[0]] = kinds.get(o['why'].split()[0], 0) + 1
    return ', '.join(f'{v} {k}' for k, v in sorted(kinds.items())) or 'nothing'


def main(argv):
    if len(argv) < 4:
        print('usage: python -m gdl.edit check|plan <edits.json> <panel.gdl> [out.json]')
        return 2
    cmd, spec_path, gdl_path = argv[1], argv[2], argv[3]
    ed = Edits.load(spec_path, gdl_path)
    plan, errors, warnings = ed.check()
    for p in errors:
        print('  ERROR   ' + p)
    for p in warnings[:20]:
        print('  warning ' + p)
    if len(warnings) > 20:
        print(f'  warning ... and {len(warnings) - 20} more')
    for c in ed._unused_colors:
        print(f'  warning restyle: no control uses {c} - nothing to remap')
    print(f'{len(plan["controls"])} control op(s), '
          f'{len(plan["project"])} project op(s): {_summarise(plan)}')
    print(f'{len(errors)} error(s), {len(warnings)} warning(s)')
    if cmd == 'check':
        return 1 if errors else 0
    if cmd == 'plan':
        if errors:
            print('refusing to emit a plan while there are errors')
            return 1
        out = argv[4] if len(argv) > 4 else 'out/edits-plan.json'
        with open(out, 'w', encoding='utf-8') as fh:
            json.dump(plan, fh, indent=2)
        print(f'-> {out}')
        return 0
    print(f'unknown command {cmd!r}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
