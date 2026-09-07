"""Describe a panel declaratively, lay it out, and render it - without Windows.

The gap this fills is the one CLAUDE.md names: generating a panel from a spec
rather than by cloning an existing one. Two of the three missing pieces live
here, because they are pure arithmetic and need nothing installed:

  * a **layout pass** - `grid` and `stack` turn "six buttons across this region
    with a 16px gutter" into rects, so nothing is a hand-typed literal
  * **ID allocation** - page numbers and per-control `userId`s handed out in
    bands, unique within a page, skipping anything the spec pins by hand

The third piece - writing the authoring model - has to *run* on 32-bit Windows
PowerShell with GUI Designer installed, but everything that step needs is
emitted here as data:

  * a **preview** (`render`) - a spec goes straight through `gdl/compose.py`,
    the same compositor that scores 2.19% against GUI Designer's own snapshot
    exports, so a design can be judged before it reaches a Windows box
  * a **plan** (`plan`) - the clone-and-set ops `powershell/Apply-GdlPlan.ps1`
    applies. That applier is UNVERIFIED; see docs/from-scratch.md.

That works because an authored control carries `TLPImageID = -1` - Build has not
rasterised it yet - and the compositor already knows how to draw those from
their `borderFillColor` plus a named border resource. A spec is exactly a
description of those properties.

    python -m gdl.spec check  examples/panel.json
    python -m gdl.spec render examples/panel.json out/preview.png
    python -m gdl.spec plan   examples/panel.json out/plan.json

What it cannot do is prove GUI Designer will accept the result. Nothing here
touches a real `.gdl`; see docs/from-scratch.md for what still needs a human.
"""
import json
import re
import sys

# AlignmentEnum = 3*vertical + horizontal; vertical 0 bottom / 1 middle / 2 top,
# horizontal 0 centre / 1 left / 2 right. Same convention gdl/compose.py decodes.
ALIGN = {
    'top-left': 7, 'top': 6, 'top-right': 8,
    'left': 4, 'center': 3, 'centre': 3, 'right': 5,
    'bottom-left': 1, 'bottom': 0, 'bottom-right': 2,
}

# The border resources every fixture already carries. A generator that only
# *references* these needs no new resource appended to the project, which is the
# one step that has never been proven against GUI Designer.
BORDERS = {
    'rect': '2D Rectangle',
    'rect-thin': '2D Rectangle_1',
    'rounded': '2D Rounded Rectangle',
    'capsule': '2D Capsule',
    'ellipse': '2D Ellipse',
    'rect-3d': '3D Rectangle',
    'rounded-3d': '3D Rounded Rectangle',
    'capsule-3d': '3D Capsule',
    'gradient': '3D Gradient',
    'afterburn': 'Afterburn - 10 Radius 2 Thick',
    'afterburn-flat': 'Afterburn - 10 Radius 0 Thick',
    'afterburn-14': 'Afterburn - 14 Radius 0 Thick',
}
# radius/thickness per resource, read from the fixtures' own PBBorderResource
# dataField. Only what the preview needs to draw; the real geometry is Build's.
BORDER_GEOMETRY = {
    '2D Rectangle': (0, 3), '2D Rectangle_1': (0, 0),
    '2D Rounded Rectangle': (10, 3), '2D Capsule': (9999, 3), '2D Ellipse': (0, 3),
    '3D Rectangle': (0, 1), '3D Rounded Rectangle': (10, 1), '3D Capsule': (9999, 1),
    '3D Gradient': (5, 1),
    'Afterburn - 10 Radius 0 Thick': (10, 0),
    'Afterburn - 10 Radius 2 Thick': (10, 2),
    'Afterburn - 14 Radius 0 Thick': (14, 0),
    'Afterburn - Elipse 3 Thick': (10, 3),
}
# Panel models by resolution. Names are read from GUI Designer's own Project
# Create Wizard (55 entries), not reconstructed from class symbols - TLC and TLP
# are different product lines and class names outlive retired models.
#
# PPI is what Extron's touch-target Quick Reference table keys its minimums to.
# Where a resolution spans models of different physical size the conservative
# (higher PPI, larger minimum) value is used. 1280x720 HAS models - TLP Pro
# 535M/535T - but no row in that table, so it has no documented minimum.
PANELS = {
    (320, 240): ('CCI Pro 700, TLP Pro 320C/M', 114),
    (320, 480): ('TLP Pro 300M', 165),
    (800, 480): ('TLC Pro 521M/526M, TLP Pro 525C/M/T', 187),
    (1024, 600): ('TLC Pro 726M, TLP Pro 725C/M/T, 1022M/T, ZRTP Pro 725M/T', 170),
    (1280, 720): ('TLP Pro 535M/T', None),
    (1280, 800): ('TLC Pro 1026M, TLP Pro 835/1025/1035/1220/1225, ZRTP Pro 1025', 149),
    (1366, 768): ('TLP Pro 1520MG/TG, 1525MG/TG', 100),
    (1920, 1080): ('TLI Pro 201, TLP Pro 1535M/T, 1720MG/TG, 1725MG/TG', 128),
}
# Extron's own numbers, GUI Design Standards rev E pp.55-56: a touch target must
# be 9mm square, and touchable elements must be 2mm apart. Converting to pixels
# needs the panel's PPI, which is why PANELS carries it.
MM_TOUCH_TARGET = 9.0
MM_SPACING = 2.0
MAX_BUTTONS_PER_GROUP = 9        # p.58
MAX_COLOURS_PER_PROJECT = 6      # p.49
MIN_BODY_POINT_SIZE = 14         # pp.65-67


def touch_minimums(size):
    """(min target px, min spacing px) for a canvas size, or (None, None).

    Derived as mm x PPI. Extron publishes the resulting table but not this
    formula - p.90 says third-party panels must be "calculated manually" and
    gives no formula - so treat these as reproducing the documented rows rather
    than as a documented rule in their own right.
    """
    _, ppi = PANELS.get(tuple(size), (None, None))
    if not ppi:
        return None, None
    mm_per_inch = 25.4
    return (round(MM_TOUCH_TARGET * ppi / mm_per_inch),
            round(MM_SPACING * ppi / mm_per_inch))


KIND_TYPE = {'panel': 'PBShape', 'shape': 'PBShape', 'button': 'PBButton',
             'label': 'PBLabel', 'line': 'PBLine'}


def _argb(c):
    """{'A','R','G','B'} -> the packed 0xAARRGGBB int System.Drawing.Color holds."""
    if not c:
        return None
    return (c['A'] << 24) | (c['R'] << 16) | (c['G'] << 8) | c['B']


HEX = re.compile(r'^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')


def colour(v, theme=None):
    """'#RRGGBB', '#AARRGGBB' or a theme key -> the ARGB dict layout.json uses."""
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    if theme and v in theme:
        v = theme[v]
    m = HEX.match(str(v))
    if not m:
        raise ValueError(f'not a colour or theme key: {v!r}')
    h = m.group(1)
    if len(h) == 6:
        h = 'FF' + h
    return {'A': int(h[0:2], 16), 'R': int(h[2:4], 16),
            'G': int(h[4:6], 16), 'B': int(h[6:8], 16)}


def grid(rect, cols, rows=1, gap=0, gap_y=None, pad=0):
    """Split a region into cell rects, left to right then top to bottom.

    The layout pass in miniature: this is what stops every rect in a generated
    panel being a hand-typed literal, which is how the existing authoring
    example has to do it.
    """
    x, y, w, h = rect
    gy = gap if gap_y is None else gap_y
    # A negative gap silently produces overlapping cells that are individually
    # valid - positive size, on canvas - so nothing downstream would catch it.
    if gap < 0 or gy < 0:
        raise ValueError(f'negative gap ({gap}, {gy}) would overlap cells')
    if cols < 1 or rows < 1:
        raise ValueError(f'grid needs at least one row and column, got {cols}x{rows}')
    x, y, w, h = x + pad, y + pad, w - 2 * pad, h - 2 * pad
    cw = (w - gap * (cols - 1)) / cols
    ch = (h - gy * (rows - 1)) / rows
    out = []
    for r in range(rows):
        for c in range(cols):
            out.append([round(x + c * (cw + gap)), round(y + r * (ch + gy)),
                        round(cw), round(ch)])
    return out


def stack(rect, count, gap=0, horizontal=False, pad=0):
    """A one-dimensional grid - a row or a column of equal cells."""
    return grid(rect, count if horizontal else 1, 1 if horizontal else count,
                gap=gap, pad=pad)


class Panel:
    """A spec, laid out and ID-allocated, ready to render or to hand to a writer."""

    def __init__(self, spec):
        self.spec = spec
        self.theme = dict(spec.get('theme') or {})
        self.size = tuple(spec.get('size') or (1280, 800))
        self.pages = []
        self._groups = {}
        self._build()

    @classmethod
    def load(cls, path):
        with open(path) as fh:
            return cls(json.load(fh))

    # -- layout ------------------------------------------------------------
    def _controls(self, node, out, region=None):
        """Flatten a page's control tree, expanding any layout directive.

        `region` is the cell a nested directive sits in. A grid inside a stack
        lays out within its parent's cell, and a `rect` given at that depth is
        read as an offset into the cell rather than as page coordinates -
        otherwise nesting silently positions against the page origin, which
        looks like it worked and is off by wherever the parent cell is.
        """
        for item in node:
            if 'grid' in item or 'stack' in item:
                spread = item.get('grid') or item.get('stack')
                items = spread.get('items') or []
                rect = self._region(spread.get('rect'), region)
                if 'grid' in item:
                    cells = grid(rect, spread.get('cols', len(items)),
                                 spread.get('rows', 1), spread.get('gap', 0),
                                 spread.get('gap_y'), spread.get('pad', 0))
                else:
                    cells = stack(rect, spread.get('count', len(items)),
                                  spread.get('gap', 0), spread.get('horizontal', False),
                                  spread.get('pad', 0))
                shared = {k: v for k, v in spread.items()
                          if k not in ('rect', 'cols', 'rows', 'gap', 'gap_y',
                                       'pad', 'items', 'count', 'horizontal')}
                # p.58 caps a control GROUP at nine buttons. "Group" is not a
                # spec concept, so treat one layout directive as one group -
                # which is what a designer means by it.
                kinds = [sub.get('kind', shared.get('kind')) for sub in items]
                nbtn = sum(1 for k in kinds if k == 'button')
                if nbtn:
                    label = spread.get('name') or (items[0].get('text') if items else '?')
                    self._groups[str(label)] = self._groups.get(str(label), 0) + nbtn
                for cell, sub in zip(cells, items):
                    merged = dict(shared)
                    merged.update(sub)
                    if 'grid' in sub or 'stack' in sub:
                        # Hand the cell down; the child positions inside it.
                        merged.pop('rect', None)
                        self._controls([merged], out, region=cell)
                    else:
                        merged['rect'] = self._region(sub.get('rect'), cell) \
                            if 'rect' in sub else cell
                        self._controls([merged], out)
            else:
                if region is not None and 'rect' in item:
                    item = dict(item, rect=self._region(item['rect'], region))
                elif region is not None:
                    item = dict(item, rect=region)
                out.append(item)
        return out

    @staticmethod
    def _region(rect, parent):
        """Resolve a rect that may be relative to an enclosing cell."""
        if parent is None:
            return rect
        if rect is None:
            return list(parent)
        return [parent[0] + rect[0], parent[1] + rect[1], rect[2], rect[3]]

    # -- ids ---------------------------------------------------------------
    def _allocate(self, page, controls, base):
        """Hand out userIds in a per-page band, honouring anything pinned.

        Extron numbers a page's controls in a band related to the page number
        (a 2000-series page carries 2000-series ids), which is convention rather
        than anything the engine enforces - but a generated panel that ignores
        it reads as generated.
        """
        taken = {c['id'] for c in controls if c.get('id')}
        nxt = base
        for c in controls:
            if c.get('id'):
                continue
            while nxt in taken:
                nxt += 1
            c['id'] = nxt
            taken.add(nxt)
            nxt += 1
        return controls

    # -- build -------------------------------------------------------------
    def _build(self):
        page_no = None
        for i, pg in enumerate(self.spec.get('pages') or []):
            self._groups = {}
            controls = self._controls(pg.get('controls') or [], [])
            page_no = pg.get('number')
            if page_no is None:
                page_no = 1000 * (i + 1)
            self._allocate(pg, controls, pg.get('id_base') or page_no + 1)
            self.pages.append({
                'number': page_no,
                'name': pg.get('name') or f'Page {page_no}',
                'modal': bool(pg.get('modal')),
                'background': colour(pg.get('background') or self.theme.get('background')
                                     or '#000000', self.theme),
                'controls': controls,
                'group_sizes': dict(self._groups),
            })

    # -- emit --------------------------------------------------------------
    def layout(self):
        """The layout.json-shaped model gdl/compose.py renders, plus its fills.

        Every control is emitted with TLPImageID = -1, exactly as an authored
        one is before Build rasterises it - so the preview is drawing the same
        thing GUI Designer would be asked to build.
        """
        pages, fills = [], {}
        for idx, pg in enumerate(self.pages):
            controls = []
            for c in pg['controls']:
                kind = KIND_TYPE.get(c.get('kind', 'panel'), 'PBShape')
                rect = [int(v) for v in c['rect']]
                fill = colour(c.get('fill'), self.theme)
                border = c.get('border')
                if border in BORDERS:
                    border = BORDERS[border]
                if border is None and fill is not None:
                    border = BORDERS['rounded']
                font = c.get('font') or self.theme.get('font') or 'Arial'
                out = {
                    '__type': kind,
                    'ID': len(controls),
                    'UserId': c.get('id'),
                    'Name': c.get('name') or c.get('text') or kind,
                    'Left': rect[0], 'Top': rect[1], 'Width': rect[2], 'Height': rect[3],
                    'TLPImageID': -1,
                    'Text': c.get('text') or '',
                    'TextColor': colour(c.get('color') or self.theme.get('text')
                                        or '#FFFFFF', self.theme),
                    'TextAlignment': ALIGN.get(c.get('align', 'center'), 3),
                    'Font': {'Name': font,
                             'PointSize': c.get('size') or self.theme.get('size') or 14,
                             'Style': {'Bold': bool(c.get('bold')),
                                       'Italic': bool(c.get('italic'))}},
                }
                controls.append(out)
                if fill:
                    radius, thickness = BORDER_GEOMETRY.get(border, (0, 0))
                    # Keyed the way gdl/compose.py looks it up: (page id,
                    # control id), the pair both models share.
                    fills[(pg['number'], out['ID'])] = {
                        'fill': fill,
                        'stroke': colour(c.get('stroke'), self.theme),
                        'border': {'resource': border, 'radius': radius,
                                   'thickness': thickness},
                    }
            pages.append({
                'ID': pg['number'], 'Name': pg['name'], 'TLPImageID': -1,
                'Modal': pg['modal'], 'BackgroundFillColor': pg['background'],
                'Controls': controls,
            })
        return {'Pages': pages, 'PopupPages': []}, fills

    def render(self, page=0):
        """Composite one page to a PIL image. Needs Pillow."""
        from .compose import render_page
        model, fills = self.layout()
        return render_page(model['Pages'][page], {}, self.size, fills=fills)

    def plan(self):
        """A build plan: the clone-and-set operations that would write this spec.

        Deliberately *data*, not code. Writing the authoring model needs 32-bit
        Windows PowerShell and GUI Designer, which cannot be tested here - so
        the split is: Python decides everything (layout, ids, colours, which
        donor object to clone), and `powershell/Apply-GdlPlan.ps1` does nothing
        but apply the ops. That keeps the untestable half thin and mechanical
        rather than putting a generator in a language this machine cannot run.

        Every op is clone-then-set-backing-field, because constructors and
        property setters both throw headless - see docs/gdl-format.md section 4.
        """
        model, fills = self.layout()
        pages = []
        for pg in model['Pages']:
            controls = []
            for c in pg['Controls']:
                # Keyed the way layout() emits and compose.py looks up:
                # (page id, control id). This used to key on (type, rect) and
                # silently produced fill=None on every op after the join
                # changed - which is exactly the sort of break a plan-level
                # test catches and an end-to-end render does not.
                spec = fills.get((pg['ID'], c['ID'])) or {}
                border = (spec.get('border') or {}).get('resource')
                controls.append({
                    'op': 'clone-control',
                    # Clone a control of the same type from anywhere in the
                    # donor; only its backing fields survive, so any instance
                    # of the right class will do.
                    'donor_type': c['__type'],
                    'fields': {
                        'idField': c['ID'],
                        'userIdField': c['UserId'],
                        'nameField': c['Name'],
                        'textField': c['Text'],
                        'leftField': c['Left'], 'topField': c['Top'],
                        'widthField': c['Width'], 'heightField': c['Height'],
                        '<TLPImageID>k__BackingField': -1,
                    },
                    'fill': _argb(spec.get('fill')),
                    'stroke': _argb(spec.get('stroke')),
                    'border': border,
                    'font': {'name': c['Font']['Name'],
                             'size': c['Font']['PointSize'],
                             'bold': c['Font']['Style']['Bold'],
                             'italic': c['Font']['Style']['Italic']},
                    'text_color': _argb(c['TextColor']),
                    'alignment': c['TextAlignment'],
                })
            pages.append({
                'op': 'clone-page',
                'number': pg['ID'],
                'name': pg['Name'],
                'modal': pg['Modal'],
                'background': _argb(pg['BackgroundFillColor']),
                'clear_controls': True,
                'controls': controls,
            })
        return {
            'generated_by': 'gdl.spec',
            'canvas': list(self.size),
            'note': ('Apply with powershell/Apply-GdlPlan.ps1 under 32-bit '
                     'Windows PowerShell 5.1. Page ids are assigned by the '
                     'applier via Get-GdlNextPageId, not here - the donor '
                     'project decides what is free.'),
            'pages': pages,
        }

    # -- checks ------------------------------------------------------------
    def check(self):
        """Problems a human would otherwise find on the Windows box."""
        out = []
        for pg in self.pages:
            seen = {}
            # Two controls with identical type and rect are almost always a
            # layout mistake - one is invisible behind the other. Harmless to
            # the compositor now that fills join on ids, but worth saying.
            geometry = {}
            for c in pg['controls']:
                key = (KIND_TYPE.get(c.get('kind', 'panel'), 'PBShape'),
                       tuple(int(v) for v in c['rect']))
                label = c.get('name') or c.get('text') or '?'
                if key in geometry:
                    out.append(f"page {pg['number']} {label}: same type and rect as "
                               f"{geometry[key]} - one is hidden behind the other")
                geometry[key] = label
            for c in pg['controls']:
                x, y, w, h = (int(v) for v in c['rect'])
                where = f"page {pg['number']} {c.get('name') or c.get('text') or '?'}"
                if w <= 0 or h <= 0:
                    out.append(f'{where}: non-positive size {w}x{h}')
                if x < 0 or y < 0 or x + w > self.size[0] or y + h > self.size[1]:
                    out.append(f'{where}: rect {[x, y, w, h]} leaves the {self.size} canvas')
                if c['id'] in seen:
                    out.append(f"{where}: id {c['id']} already used by {seen[c['id']]}")
                seen[c['id']] = where
                b = c.get('border')
                if b and b not in BORDERS and b not in BORDER_GEOMETRY:
                    out.append(f'{where}: unknown border resource {b!r} - a generator may '
                               f'only reference resources the project already carries')
            out += self._house_rules(pg)
        n = len(self.palette())
        if n > MAX_COLOURS_PER_PROJECT:
            out.append(f'project uses {n} distinct colours, above the '
                       f'{MAX_COLOURS_PER_PROJECT}-colour maximum '
                       f'(GUI Design Standards p.49)')
        return out

    def _house_rules(self, pg):
        """Extron's own numeric rules. See docs/design-rules.md for provenance.

        Deliberately separate from the structural checks above: these are
        Extron's design standards, not correctness. A spec that trips one of
        these will still build - it just will not meet the standard.
        """
        out = []
        target, spacing = touch_minimums(self.size)
        for c in pg['controls']:
            x, y, w, h = (int(v) for v in c['rect'])
            where = f"page {pg['number']} {c.get('name') or c.get('text') or '?'}"
            # Only interactive controls have a touch target to meet.
            if target and c.get('kind') == 'button' and (w < target or h < target):
                out.append(f'{where}: {w}x{h} is below the {target}x{target} px touch '
                           f'target for a {self.size[0]}x{self.size[1]} panel '
                           f'(9mm, GUI Design Standards p.55)')
            size = c.get('size') or self.theme.get('size') or 0
            if c.get('kind') in ('button', 'label') and size and size < MIN_BODY_POINT_SIZE:
                out.append(f'{where}: {size}pt is below the {MIN_BODY_POINT_SIZE}pt '
                           f'body-text minimum (p.65)')

        # p.58: no more than nine buttons in a control group. "Group" is not a
        # spec concept, so approximate it by the layout directive that produced
        # them - which is exactly what a designer means by a group.
        for name, n in (pg.get('group_sizes') or {}).items():
            if n > MAX_BUTTONS_PER_GROUP:
                out.append(f"page {pg['number']} group {name!r}: {n} buttons exceeds the "
                           f'{MAX_BUTTONS_PER_GROUP}-per-group maximum (p.58)')

        # Adjacent-button spacing, p.56: at least 5-10px for buttons of 72px or
        # less, and 2mm between touchable targets generally.
        if spacing:
            btns = [c for c in pg['controls'] if c.get('kind') == 'button']
            for i, a in enumerate(btns):
                ax, ay, aw, ah = (int(v) for v in a['rect'])
                for b2 in btns[i + 1:]:
                    bx, by, bw, bh = (int(v) for v in b2['rect'])
                    gap_x = max(bx - (ax + aw), ax - (bx + bw))
                    gap_y = max(by - (ay + ah), ay - (by + bh))
                    # Only complain about neighbours: overlapping on one axis
                    # and separated on the other.
                    if gap_x < 0 and 0 <= gap_y < spacing:
                        out.append(f"page {pg['number']} {a.get('text') or '?'} / "
                                   f"{b2.get('text') or '?'}: {gap_y}px vertical gap is "
                                   f'below the {spacing}px minimum (2mm, p.56)')
                    elif gap_y < 0 and 0 <= gap_x < spacing:
                        out.append(f"page {pg['number']} {a.get('text') or '?'} / "
                                   f"{b2.get('text') or '?'}: {gap_x}px horizontal gap is "
                                   f'below the {spacing}px minimum (2mm, p.56)')
        return out

    def palette(self):
        """Every distinct colour the spec uses. p.49 caps a project at six."""
        seen = set()
        for pg in self.pages:
            seen.add(tuple(sorted((pg['background'] or {}).items())))
            for c in pg['controls']:
                for key in ('fill', 'stroke', 'color'):
                    v = colour(c.get(key), self.theme)
                    if v:
                        seen.add(tuple(sorted(v.items())))
        return {s for s in seen if s}


def main(argv):
    if len(argv) < 3:
        print(__doc__.strip().split('\n\n')[0])
        print('\n  python -m gdl.spec render <spec.json> <out.png> [page]'
              '\n  python -m gdl.spec check  <spec.json>'
              '\n  python -m gdl.spec plan   <spec.json> <plan.json>')
        return 2
    cmd, path = argv[1], argv[2]
    panel = Panel.load(path)
    problems = panel.check()
    if cmd == 'check':
        for p in problems:
            print('  ' + p)
        print(f'{len(problems)} problem(s); {len(panel.pages)} page(s), '
              f'{sum(len(p["controls"]) for p in panel.pages)} controls')
        return 1 if problems else 0
    if cmd == 'plan':
        if problems:
            for p in problems:
                print('  ' + p)
            return 1
        plan = panel.plan()
        with open(argv[3], 'w') as fh:
            json.dump(plan, fh, indent=1)
        print(f'{len(plan["pages"])} page(s), '
              f'{sum(len(p["controls"]) for p in plan["pages"])} control ops -> {argv[3]}')
        return 0
    if cmd == 'render':
        if problems:
            for p in problems:
                print('  ' + p)
            return 1
        page = int(argv[4]) if len(argv) > 4 else 0
        img = panel.render(page)
        img.convert('RGB').save(argv[3])
        print(f'{panel.pages[page]["name"]} -> {argv[3]}')
        return 0
    print(f'unknown command {cmd!r}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
