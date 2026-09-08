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

The four operations:

  rename    change captions. Rewrites the control AND every state, because a
            button renders from its state and a caption set only on the control
            builds blank.
  retarget  move the project to another panel model. Sets the three fields that
            have to agree (platform instance, platform type enum, screen size)
            and optionally rescales the layout.
  renumber  reassign the addressable IDs (`userIdField`) in per-page bands.
  restyle   remap colors across the whole project.

Selectors are ANDed, and every one of them is resolved against the real project
here, so `check` can say "this matched nothing" instead of the edit silently
doing nothing on Windows - which is the failure mode that makes this kind of
tool untrustworthy.
"""
import json
import re
import sys

from .project import Project
from .spec import MODELS, dpi, touch_minimums, MM_TOUCH_TARGET

# Fields that carry a color, and are therefore what `restyle` rewrites. A
# control's own three plus the page background; states carry the same three.
COLOR_FIELDS = ('borderFillColorField', 'borderColorField', 'textColorField')


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
        with open(spec_path) as fh:
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
        with Cam" is the request people actually have.
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
                if 'text' in sel and (c['caption'] or '') != sel['text']:
                    continue
                if 'id' in sel and c['id'] != sel['id']:
                    continue
                if 'name_matches' in sel and not re.search(sel['name_matches'],
                                                           c['name'] or ''):
                    continue
                if 'text_matches' in sel and not re.search(sel['text_matches'],
                                                           c['caption'] or ''):
                    continue
                out.append((pg, c))
        return out

    # -- the ops -----------------------------------------------------------
    def _rename(self, e, ops, problems):
        """Captions. Also rewrites every state - see the module docstring."""
        pairs = e.get('map')
        if pairs:
            # {"old caption": "new caption"} across whatever the selector covers.
            base = e.get('select') or {}
            for old, new in pairs.items():
                hits = self.select(dict(base, text=old))
                if not hits:
                    problems.append(f'rename: nothing has the caption {old!r}'
                                    + (f" under {base}" if base else ''))
                for pg, c in hits:
                    ops.append(self._text_op(pg, c, new))
            return
        new = e.get('text')
        if new is None:
            problems.append("rename: needs either 'text' or 'map'")
            return
        hits = self.select(e.get('select'))
        if not hits:
            problems.append(f"rename: selector {e.get('select')} matched nothing")
        for pg, c in hits:
            ops.append(self._text_op(pg, c, new))

    def _text_op(self, pg, c, new):
        """Write the caption back where the old one was.

        `caption_in` says which of the three places holds it. Writing the wrong
        one leaves the original text showing - the control still has it, and
        whichever field the renderer prefers wins.
        """
        where = c.get('caption_in')
        op = {'page': pg['id'], 'control': c['obj_id'], 'was': c['caption'],
              'why': f'rename {c["caption"]!r} -> {new!r}'}
        if where == 'fstate':
            op['flattened'] = True
            # Formatted text carries tab/CRLF layout markers that are part of
            # how it draws, so keep the leading whitespace of the original.
            op['states_ftext'] = new
        elif where == 'state':
            op['states'] = {'textField': new}
        else:
            # No caption anywhere (an icon-only button), or it is on the
            # control. Set both: a button renders from its state, and a caption
            # written only on the control builds blank.
            op['fields'] = {'textField': new}
            op['states'] = {'textField': new}
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
        """Remap colors project-wide, or under a selector."""
        table = {_norm(k): _norm(v) for k, v in (e.get('map') or {}).items()}
        if not table:
            problems.append("restyle: needs a 'map' of old color -> new color")
            return
        hits = self.select(e.get('select'))
        seen = set()
        for pg, c in hits:
            changes = {}
            for field, key in (('borderFillColorField', 'fill'),
                               ('borderColorField', 'stroke')):
                have = _norm(c.get(key))
                if have:
                    seen.add(have)
                if have in table:
                    changes[field] = table[have]
            if changes:
                ops.append({'page': pg['id'], 'control': c['obj_id'],
                            'why': f'restyle {c["name"] or c["type"]}',
                            'colors': changes, 'states_colors': changes})
        self._unused_colors += [k for k in table if k not in seen]

    def _retarget(self, e, ops, problems, project_ops):
        """Move the project to another panel model.

        Three fields have to agree or GUI Designer is being told two different
        things about what it is building for: the platform INSTANCE
        (`platformField`, a `PBTouchPanelPlatformPro` subclass), the enum
        (`platformTypeField`) and `screenSizeField`. The applier constructs the
        class, because a platform is one of the few objects that does construct
        headlessly - it holds no project state.
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
        project_ops.append({'why': f'retarget to {model} ({new_size[0]}x{new_size[1]})',
                            'model': model, 'size': list(new_size),
                            'platform_class': f'Extron.GUICPro.PB{model}Platform'})
        if not e.get('scale'):
            return old_size, new_size
        if not old_size:
            problems.append('retarget: cannot scale - the project has no screen size')
            return old_size, new_size
        sx = new_size[0] / old_size[0]
        sy = new_size[1] / old_size[1]
        for pg in self.pages:
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
        ops, project_ops, problems = [], [], []
        self._resize = None
        self._model = None
        self._unused_colors = []
        for e in self.edits:
            op = e.get('op')
            if op == 'rename':
                self._rename(e, ops, problems)
            elif op == 'renumber':
                self._renumber(e, ops, problems)
            elif op == 'restyle':
                self._restyle(e, ops, problems)
            elif op == 'retarget':
                self._resize = self._retarget(e, ops, problems, project_ops)
            else:
                problems.append(f'unknown op {op!r}')
        return {
            'generated_by': 'gdl.edit',
            'target': self.path,
            'note': ('Apply with powershell/Apply-GdlEdits.ps1 under 32-bit Windows '
                     'PowerShell 5.1, then verify the BUILT file - a clean build '
                     'does not mean a correct one.'),
            'project': project_ops,
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
            if not o.get('flattened'):
                continue
            old, newt = o.get('was') or '', ''
            for src in (o.get('states') or {},):
                newt = src.get('textField') or newt
            newt = o.get('states_ftext') or newt
            if len(newt.split()) > len(old.split()) or len(newt) > len(old):
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
            for pg in self.pages:
                if pg['kind'] != 'page':
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
                    if x + w > size[0] or y + h > size[1]:
                        errors.append(
                            f"{pg['name']} {c['name'] or c['type']}: {x},{y} {w}x{h} "
                            f'falls outside the new {size[0]}x{size[1]} canvas - Build '
                            f'moves it to 0,0 without reporting anything')

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
        with open(out, 'w') as fh:
            json.dump(plan, fh, indent=2)
        print(f'-> {out}')
        return 0
    print(f'unknown command {cmd!r}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
