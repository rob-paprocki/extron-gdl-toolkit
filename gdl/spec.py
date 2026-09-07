"""Describe a panel declaratively, lay it out, and render it - without Windows.

The gap this fills is the one CLAUDE.md names: generating a panel from a spec
rather than by cloning an existing one. Two of the three missing pieces live
here, because they are pure arithmetic and need nothing installed:

  * a **layout pass** - `grid` and `stack` turn "six buttons across this region
    with a 16px gutter" into rects, so nothing is a hand-typed literal
  * **ID allocation** - page numbers and per-control `userId`s handed out in
    bands, unique within a page, skipping anything the spec pins by hand

The third piece, writing the authoring model, still needs 32-bit Windows
PowerShell and GUI Designer. What this module gives you instead is a **preview**:
a spec renders straight through `gdl/compose.py`, the same compositor that scores
2.19% against GUI Designer's own snapshot exports. So a design can be judged
before it ever reaches a Windows box, which is the expensive step.

That works because an authored control carries `TLPImageID = -1` - Build has not
rasterised it yet - and the compositor already knows how to draw those from
their `borderFillColor` plus a named border resource. A spec is exactly a
description of those properties.

    python -m gdl.spec render examples/panel.json out/preview.png
    python -m gdl.spec check  examples/panel.json

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
KIND_TYPE = {'panel': 'PBShape', 'shape': 'PBShape', 'button': 'PBButton',
             'label': 'PBLabel', 'line': 'PBLine'}
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
        self._build()

    @classmethod
    def load(cls, path):
        with open(path) as fh:
            return cls(json.load(fh))

    # -- layout ------------------------------------------------------------
    def _controls(self, node, out):
        """Flatten a page's control tree, expanding any layout directive."""
        for item in node:
            if 'grid' in item or 'stack' in item:
                spread = item.get('grid') or item.get('stack')
                items = spread.get('items') or []
                if 'grid' in item:
                    cells = grid(spread['rect'], spread.get('cols', len(items)),
                                 spread.get('rows', 1), spread.get('gap', 0),
                                 spread.get('gap_y'), spread.get('pad', 0))
                else:
                    cells = stack(spread['rect'], spread.get('count', len(items)),
                                  spread.get('gap', 0), spread.get('horizontal', False),
                                  spread.get('pad', 0))
                shared = {k: v for k, v in spread.items()
                          if k not in ('rect', 'cols', 'rows', 'gap', 'gap_y',
                                       'pad', 'items', 'count', 'horizontal')}
                for cell, sub in zip(cells, items):
                    merged = dict(shared)
                    merged.update(sub)
                    merged['rect'] = cell
                    self._controls([merged], out)
            else:
                out.append(item)
        return out

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
                    fills[(kind, tuple(rect))] = {
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

    # -- checks ------------------------------------------------------------
    def check(self):
        """Problems a human would otherwise find on the Windows box."""
        out = []
        for pg in self.pages:
            seen = {}
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
        return out


def main(argv):
    if len(argv) < 3:
        print(__doc__.strip().split('\n\n')[0])
        print('\n  python -m gdl.spec render <spec.json> <out.png> [page]'
              '\n  python -m gdl.spec check  <spec.json>')
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
