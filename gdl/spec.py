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
rasterized it yet - and the compositor already knows how to draw those from
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
# horizontal 0 center / 1 left / 2 right. Same convention gdl/compose.py decodes.
ALIGN = {
    'top-left': 7, 'top': 6, 'top-right': 8,
    'left': 4, 'center': 3, 'right': 5,
    'bottom-left': 1, 'bottom': 0, 'bottom-right': 2,
}
# Accepted on input, not produced: a spec written in British English should not
# fail over one letter.
ALIGN['centre'] = ALIGN['center']

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
# Every panel GUI Designer can target: (width, height, DPI, Extron part number).
#
# Read out of the ASSEMBLIES, not off the Project Create Wizard's list box.
# `PBTouchPanelPlatformPro.GetDefaultResolutionDpi(type, out w, out h, out dpi)`
# and `CreatePlatform(project, type)` are Extron's own, so this is primary
# source. `out/probe-22-createplatform.ps1` regenerates it and
# `research/data/platform-details.txt` is the raw capture.
#
# The part number matters: GUI Designer identifies a panel by it, and a project
# whose platform object lacks one opens as "Unknown" no matter how correct the
# class, enum and screen size are. See docs/from-scratch.md.
#
# DPI IS PER MODEL, NOT PER RESOLUTION. 1280x800 alone spans 124.75 (TLP Pro
# 1220/1225), 149 (TLC 1026M, TLP Pro 1025/1035, ZRTP 1025), 188.68 (TLP Pro
# 835) and 220 (virtual Android) - a 1.76x spread, which is 1.76x on the
# touch-target minimum. An earlier version of this table keyed PPI off the
# resolution and was therefore wrong for most 1280x800 models.
#
# Two things it is NOT:
#   * not a catalogue of purchasable panels. Retired models (TLP Pro 1720MG/TG)
#     and the virtual targets (VTLP Web/iOS/Android) are here because GUI
#     Designer still builds for them.
#   * not the enum. `PlatformProTypeEnum` has 60 members to these 55 platforms;
#     `Unknown`, the MLC 84 button panels, TLP 1022W and TLP 1230WTG have no
#     touch-panel platform class behind them, and CreatePlatform returns null.
MODELS_FULL = {
    'CCI700': (320, 240, 114.29, '60-1206-02'),
    'TLC1026M': (1280, 800, 149.0, '60-1855-02'),
    'TLC521M': (800, 480, 187.0, '60-1284-02'),
    'TLC526M': (800, 480, 186.59, '60-1853-02'),
    'TLC726M': (1024, 600, 169.55, '60-1854-02'),
    'TLI101': (1920, 1080, 220.0, '60-1083-01'),
    'TLI201': (1920, 1080, 220.0, '60-1669-01'),
    'TLP1020M': (1024, 600, 118.0023, '60-1392-02'),
    'TLP1020T': (1024, 600, 118.0023, '60-1393-02'),
    'TLP1022M': (1024, 600, 117.51, '60-1602-02'),
    'TLP1022T': (1024, 600, 117.51, '60-1601-02'),
    'TLP1025M': (1280, 800, 149.0, '60-1566-02'),
    'TLP1025T': (1280, 800, 149.0, '60-1565-02'),
    'TLP1035M': (1280, 800, 149.0, '60-1999-02'),
    'TLP1035T': (1280, 800, 149.0, '60-1999-02'),
    'TLP1220MG': (1280, 800, 124.75, '60-1340-02'),
    'TLP1220TG': (1280, 800, 124.75, '60-1341-02'),
    'TLP1225MG': (1280, 800, 124.75, '60-1787-02'),
    'TLP1225TG': (1280, 800, 124.75, '60-1788-02'),
    'TLP1230WTG': (800, 480, 0.0, '60-1668-02'),
    'TLP1520MG': (1366, 768, 100.45, '60-1342-02'),
    'TLP1520TG': (1366, 768, 100.45, '60-1343-02'),
    'TLP1525MG': (1366, 768, 100.45, '60-1789-02'),
    'TLP1525TG': (1366, 768, 100.45, '60-1790-02'),
    'TLP1535M': (1920, 1080, 127.7, '60-2000-02'),
    'TLP1535T': (1920, 1080, 127.7, '60-2001-02'),
    'TLP1720MG': (1920, 1080, 127.7, '60-1344-02'),
    'TLP1720TG': (1920, 1080, 127.7, '60-1345-02'),
    'TLP1725MG': (1920, 1080, 127.7, '60-1791-02'),
    'TLP1725TG': (1920, 1080, 127.7, '60-1792-02'),
    'TLP300M': (480, 320, 164.83, '60-1667-02'),
    'TLP320C': (320, 240, 113.647, '60-1452-02'),
    'TLP320M': (320, 240, 113.647, '60-1451-02'),
    'TLP520M': (800, 480, 188.148, '60-1185-02'),
    'TLP525C': (800, 480, 186.59, '60-1560-02'),
    'TLP525M': (800, 480, 186.59, '60-1561-02'),
    'TLP525T': (800, 480, 186.59, '60-1559-02'),
    'TLP535M': (1280, 720, 293.72, '60-1993-02'),
    'TLP535T': (1280, 720, 293.72, '60-1994-02'),
    'TLP720C': (800, 480, 133.33, '60-1396-02'),
    'TLP720M': (800, 480, 133.33, '60-1394-02'),
    'TLP720T': (800, 480, 133.33, '60-1395-02'),
    'TLP725C': (1024, 600, 169.55, '60-1564-02'),
    'TLP725M': (1024, 600, 169.55, '60-1563-02'),
    'TLP725T': (1024, 600, 169.55, '60-1562-02'),
    'TLP835C': (1280, 800, 188.68, '60-1995-02'),
    'TLP835M': (1280, 800, 188.68, '60-1996-02'),
    'TLP835T': (1280, 800, 188.68, '60-1997-02'),
    'VTLPAndroid': (1280, 800, 220.0, '79-600-01'),
    'VTLPWeb': (1920, 1080, 220.0, '60-sVTLP'),
    'VTLPiOS': (1920, 1080, 220.0, '79-559'),
    'ZRTP1025M': (1280, 800, 149.0, '60-1566-212'),
    'ZRTP1025T': (1280, 800, 149.0, '60-1565-212'),
    'ZRTP725M': (1024, 600, 169.55, '60-1563-212'),
    'ZRTP725T': (1024, 600, 169.55, '60-1562-212'),
}

# TLP Pro 300M is the one disagreement between the two sources: the platform
# class reports 320x480 (portrait, which is how the panel is sold and how
# Extron's own 300 template library is laid out) while GetDefaultResolutionDpi
# reports 480x320. `GetDefaultValues(type, landscape)` takes an orientation
# flag, so both are real - they are the two orientations of one panel. Portrait
# is used here because that is what the shipped templates assume.
MODELS_FULL['TLP300M'] = (320, 480, MODELS_FULL['TLP300M'][2],
                          MODELS_FULL['TLP300M'][3])

# name -> (width, height). The common case; the rest of MODELS_FULL is there
# when you need the DPI or the part number.
MODELS = {k: (v[0], v[1]) for k, v in MODELS_FULL.items()}


def dpi(model):
    """A model's DPI, straight from Extron's code. None if unknown."""
    e = MODELS_FULL.get(model)
    return e[2] if e else None


def part_number(model):
    """The Extron part number GUI Designer identifies the panel by."""
    e = MODELS_FULL.get(model)
    return e[3] if e else None


# Extron's own numbers, GUI Design Standards rev E pp.55-56: a touch target must
# be 9mm square, and touchable elements must be 2mm apart.
MM_TOUCH_TARGET = 9.0
MM_SPACING = 2.0
MAX_BUTTONS_PER_GROUP = 9        # p.58
MAX_COLORS_PER_PROJECT = 6      # p.49
MIN_BODY_POINT_SIZE = 14         # pp.65-67


def _panels():
    """resolution -> (models sharing it, the DENSEST model's DPI).

    Derived, so it cannot drift from MODELS_FULL. The densest model is the
    conservative choice: its pixels are the smallest, so its minimum is the
    largest, and a layout that satisfies it satisfies every other panel at that
    resolution. Name the model in the spec when you know it - it is a much
    tighter answer, and the spread within one resolution is nearly 2x.

    The VTLP* virtual targets are excluded from that maximum. They are a phone,
    a tablet and a browser, so their 220 "DPI" is the host device's rather than
    a fixed panel's, and letting it set the minimum for 1280x800 would hold
    every real panel to a number no Extron hardware implies. They stay in the
    model list, and asking for one by name still gives its own figure.
    """
    out = {}
    for model, (w, h, d, _) in MODELS_FULL.items():
        out.setdefault((w, h), []).append((model, d))
    res = {}
    for size, ms in out.items():
        physical = [d for m, d in ms if not m.startswith('VTLP') and d]
        res[size] = (', '.join(sorted(m for m, _ in ms)),
                     max(physical) if physical else None)
    return res


PANELS = _panels()
# Extron's own numbers, GUI Design Standards rev E pp.55-56: a touch target must
# be 9mm square, and touchable elements must be 2mm apart. Converting to pixels
# needs the panel's PPI, which is why PANELS carries it.
MM_TOUCH_TARGET = 9.0
MM_SPACING = 2.0
MAX_BUTTONS_PER_GROUP = 9        # p.58
MAX_COLORS_PER_PROJECT = 6      # p.49
MIN_BODY_POINT_SIZE = 14         # pp.65-67


def touch_minimums(target):
    """(min target px, min spacing px) for a panel, or (None, None).

    `target` is either a model name ('TLP1535M') or a (width, height) - the
    model is the better answer, because DPI varies by nearly 2x within a single
    resolution.

    Derived as mm x DPI. Extron publishes the resulting table but not this
    formula - p.90 says third-party panels must be "calculated manually" and
    gives no formula - so treat these as reproducing the documented rows rather
    than as a documented rule in their own right.
    """
    if isinstance(target, str):
        d = dpi(target)
    else:
        try:
            _, d = PANELS.get(tuple(target), (None, None))
        except TypeError:
            d = None
    if not d:
        return None, None
    mm_per_inch = 25.4
    return (round(MM_TOUCH_TARGET * d / mm_per_inch),
            round(MM_SPACING * d / mm_per_inch))


KIND_TYPE = {'panel': 'PBShape', 'shape': 'PBShape', 'button': 'PBButton',
             'label': 'PBLabel', 'line': 'PBLine', 'image': 'PBImage',
             'slider': 'PBSlider', 'level': 'PBLevel', 'datetime': 'PBDateTime',
             'popup_ref': 'PBPopupPageReference'}
# Interactive kinds are the ones held to the 9mm touch-target rule.
TOUCHABLE = {'button', 'slider'}

# Orientation, as gdl/compose.py decodes it when clipping a level's value fill.
ORIENT = {'right': 0, 'left': 1, 'up': 2, 'down': 3}

# Fields that only some control types carry. A generator has to emit these or
# the cloned donor's own values ride along - the same trap as captions and
# icons, just less visible.
def _type_fields(kind, c):
    out = {}
    if kind in ('slider', 'level'):
        out['orientationField'] = ORIENT.get(c.get('orientation', 'up'), 2)
        if kind == 'slider':
            out['sliderTrackWidthField'] = c.get('track', 10)
            out['sliderIndicatorWidthField'] = c.get('thumb', 50)
            out['sliderIndicatorHeightField'] = c.get('thumb', 50)
    if kind == 'line':
        # Endpoints are an eight-position enum on the control's own rect, so a
        # diagonal is TopLeft -> BottomRight at whatever angle the rect gives.
        out['startPointField'] = LINE_POS.get(c.get('from', 'MiddleLeft'), 6)
        out['endPointField'] = LINE_POS.get(c.get('to', 'MiddleRight'), 2)
        out['thicknessField'] = c.get('thickness', 2)
    return out


# Extron.GUICPro.ControlLinePositionEnum, read out of the assemblies.
LINE_POS = {'TopCenter': 0, 'TopRight': 1, 'MiddleRight': 2, 'BottomRight': 3,
            'BottomCenter': 4, 'BottomLeft': 5, 'MiddleLeft': 6, 'TopLeft': 7}


def _argb(c):
    """{'A','R','G','B'} -> the packed 0xAARRGGBB int System.Drawing.Color holds."""
    if not c:
        return None
    return (c['A'] << 24) | (c['R'] << 16) | (c['G'] << 8) | c['B']


HEX = re.compile(r'^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')


def color(v, theme=None):
    """'#RRGGBB', '#AARRGGBB' or a theme key -> the ARGB dict layout.json uses."""
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    if theme and v in theme:
        v = theme[v]
    m = HEX.match(str(v))
    if not m:
        raise ValueError(f'not a color or theme key: {v!r}')
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
        # Name the MODEL when you know it. DPI varies by nearly 2x within one
        # resolution, so the model gives a touch minimum that is right rather
        # than merely safe: a 1280x800 TLP Pro 1035T needs 53px, a TLP Pro 835M
        # at the same resolution needs 67px. Without a model the check falls
        # back to the densest physical panel at that size.
        self.model = spec.get('model')
        if self.model and self.model not in MODELS:
            raise ValueError(f'{self.model!r} is not a panel GUI Designer builds for')
        if self.model and not spec.get('size'):
            self.size = MODELS[self.model]
        else:
            self.size = tuple(spec.get('size') or (1280, 800))
        self.pages = []
        self.popups = []
        self._groups = {}
        self._build()

    @classmethod
    def load(cls, path):
        # JSON is UTF-8 by definition (RFC 8259). Without this Python uses the
        # locale encoding, which on Windows is cp1252 - so an en-dash, a degree
        # sign or an accented room name in a spec comes through as mojibake and
        # gets rasterized into the panel. Silent, and invisible off Windows.
        with open(path, encoding='utf-8') as fh:
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
        self.popups = []
        for i, pu in enumerate(self.spec.get('popups') or []):
            self._groups = {}
            controls = self._controls(pu.get('controls') or [], [])
            number = pu.get('number', 9000 + i)
            self._allocate(pu, controls, pu.get('id_base') or number + 1)
            self.popups.append({
                'number': number,
                'name': pu.get('name') or f'Popup {number}',
                'group': pu.get('group'),
                # A popup inherits its reference's dimensions (GUI Design
                # Standards p.70), so its own size is the anchor's, not its own
                # choice. Recorded for the check, not authored.
                'size': pu.get('size'),
                'modal': bool(pu.get('modal')),
                'background': color(pu.get('background') or self.theme.get('background')
                                     or '#000000', self.theme),
                'controls': controls,
                'group_sizes': dict(self._groups),
            })
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
                'background': color(pg.get('background') or self.theme.get('background')
                                     or '#000000', self.theme),
                'controls': controls,
                'group_sizes': dict(self._groups),
            })

    # -- emit --------------------------------------------------------------
    def layout(self):
        """The layout.json-shaped model gdl/compose.py renders, plus its fills.

        Every control is emitted with TLPImageID = -1, exactly as an authored
        one is before Build rasterizes it - so the preview is drawing the same
        thing GUI Designer would be asked to build.
        """
        pages, fills = [], {}
        for idx, pg in enumerate(self.pages):
            controls = []
            for c in pg['controls']:
                kind = KIND_TYPE.get(c.get('kind', 'panel'), 'PBShape')
                rect = [int(v) for v in c['rect']]
                fill = color(c.get('fill'), self.theme)
                border = c.get('border')
                if border in BORDERS:
                    border = BORDERS[border]
                if border is None and fill is not None:
                    border = BORDERS['rounded']
                font = c.get('font') or self.theme.get('font') or 'Arial'
                out = {
                    '__type': kind,
                    'kind': c.get('kind', 'panel'),
                    # Type-specific backing fields must be computed HERE, where
                    # the spec control is in scope. plan() iterates the layout
                    # model, which does not carry 'thumb', 'from', 'thickness'
                    # and friends - reading them there silently yields defaults.
                    'TypeFields': _type_fields(c.get('kind', 'panel'), c),
                    'ID': len(controls),
                    'UserId': c.get('id'),
                    'Name': c.get('name') or c.get('text') or kind,
                    'Left': rect[0], 'Top': rect[1], 'Width': rect[2], 'Height': rect[3],
                    'TLPImageID': -1,
                    'Text': c.get('text') or '',
                    'TextColor': color(c.get('color') or self.theme.get('text')
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
                        'stroke': color(c.get('stroke'), self.theme),
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
        the split is: Python decides everything (layout, ids, colors, which
        donor object to clone, popup grouping), and
        `powershell/Apply-GdlPlan.ps1` does nothing but apply the ops.

        Every op is clone-then-set-backing-field, because constructors and
        property setters both throw headless - see docs/gdl-format.md section 4.
        """
        pages = []
        for pg in self.pages:
            pages.append({
                'op': 'clone-page',
                'number': pg['number'],
                'name': pg['name'],
                'modal': pg['modal'],
                'background': _argb(pg['background']),
                'clear_controls': True,
                # Same helper popups use. Building these two separately is what
                # dropped 'group' from every page op and left popup references
                # bound to the donor's group.
                'controls': [self._op_for(c, i) for i, c in enumerate(pg['controls'])],
            })

        return {
            'generated_by': 'gdl.spec',
            'popup_groups': sorted({p['group'] for p in self.popups if p['group']}),
            'popups': self._popup_ops(),
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
        out += self._popup_rules()
        out += self._name_rules()
        n = len(self.palette())
        if n > MAX_COLORS_PER_PROJECT:
            out.append(f'project uses {n} distinct colors, above the '
                       f'{MAX_COLORS_PER_PROJECT}-color maximum '
                       f'(GUI Design Standards p.49)')
        return out

    def _house_rules(self, pg):
        """Extron's own numeric rules. See docs/design-rules.md for provenance.

        Deliberately separate from the structural checks above: these are
        Extron's design standards, not correctness. A spec that trips one of
        these will still build - it just will not meet the standard.
        """
        out = []
        target, spacing = touch_minimums(self.model or self.size)
        for c in pg['controls']:
            x, y, w, h = (int(v) for v in c['rect'])
            where = f"page {pg['number']} {c.get('name') or c.get('text') or '?'}"
            # Only interactive controls have a touch target to meet.
            if target and c.get('kind') in TOUCHABLE and (w < target or h < target):
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

    def _op_for(self, c, index):
        """One clone-control op, from a SPEC control (not a layout-model one).

        Popups take the same path as pages so the two cannot drift apart - the
        last time they were built separately, one of them silently lost its
        fills.
        """
        kind = c.get('kind', 'panel')
        cls = KIND_TYPE.get(kind, 'PBShape')
        rect = [int(v) for v in c['rect']]
        fill = color(c.get('fill'), self.theme)
        border = c.get('border')
        border = BORDERS.get(border, border)
        if border is None and fill is not None:
            border = BORDERS['rounded']
        return {
            'op': 'clone-control',
            'donor_type': cls,
            'fields': {
                'idField': index,
                'userIdField': c.get('id'),
                'nameField': c.get('name') or c.get('text') or cls,
                'textField': c.get('text') or '',
                'leftField': rect[0], 'topField': rect[1],
                'widthField': rect[2], 'heightField': rect[3],
                '<TLPImageID>k__BackingField': -1,
                **(_type_fields(kind, c) or {}),
            },
            'fill': _argb(fill),
            'stroke': _argb(color(c.get('stroke'), self.theme)),
            'border': border,
            'text_color': _argb(color(c.get('color') or self.theme.get('text')
                                       or '#FFFFFF', self.theme)),
            'alignment': ALIGN.get(c.get('align', 'center'), 3),
            'font': {'name': c.get('font') or self.theme.get('font') or 'Arial',
                     'size': c.get('size') or self.theme.get('size') or 14,
                     'bold': bool(c.get('bold')), 'italic': bool(c.get('italic'))},
            # Only meaningful on a popup reference; the applier ignores it
            # elsewhere.
            'group': c.get('group'),
        }

    def _popup_ops(self):
        return [{
            'op': 'clone-popup',
            'number': pu['number'],
            'name': pu['name'],
            'group': pu['group'],
            'modal': pu['modal'],
            'background': _argb(pu['background']),
            # The applier MUST set this. A cloned popup keeps the donor's size,
            # and GUI Designer relocates any control that falls outside the page
            # to 0,0 - silently, at build time. The first popup build lost the
            # last button of every grid that way: the spec said 984 wide, the
            # donor popup was 915, and everything past x=915 stacked up at the
            # origin while the file still built with 0 errors.
            'size': list(pu['size']) if pu['size'] else None,
            'clear_controls': True,
            'controls': [self._op_for(c, i) for i, c in enumerate(pu['controls'])],
        } for pu in self.popups]

    def _popup_rules(self):
        """What the format and GUI Design Standards p.70 require of popups.

        Every one of these fails SILENTLY in GUI Designer - the file opens, it
        builds, and the binding just reads "Unassigned" - which is why they are
        checked here rather than discovered on the panel.
        """
        out = []
        refs = {}
        for pg in self.pages:
            for c in pg['controls']:
                if c.get('kind') != 'popup_ref':
                    continue
                g = c.get('group')
                if not g:
                    out.append(f"page {pg['number']} {c.get('name') or '?'}: a popup "
                               f'reference must name a group')
                    continue
                refs.setdefault(g, []).append(tuple(int(v) for v in c['rect']))

        groups = {p['group'] for p in self.popups if p['group']}
        for g in sorted(groups - set(refs)):
            out.append(f'popup group {g!r} has no reference on any page - its popups '
                       f'can never be shown')
        for g in sorted(set(refs) - groups):
            out.append(f'popup reference bound to group {g!r}, but no popup is in that '
                       f"group - the binding would read 'Unassigned'")

        # A control that does not fit inside its popup is RELOCATED TO 0,0 by
        # GUI Designer, at build time, with no error. Pages get this check from
        # the off-canvas rule; popups need their own because their canvas is the
        # popup's own size, not the panel's.
        for pu in self.popups:
            if not pu['size']:
                continue
            w, h = int(pu['size'][0]), int(pu['size'][1])
            flat = []
            self._controls(pu['controls'], flat)
            for c in flat:
                x, y, cw, ch = (int(v) for v in c['rect'])
                if x < 0 or y < 0 or x + cw > w or y + ch > h:
                    label = c.get('name') or c.get('text') or '?'
                    out.append(f"popup {pu['name']!r} {label}: "
                               f'{x},{y} {cw}x{ch} does not fit the popup\'s {w}x{h} - '
                               f'GUI Designer moves it to 0,0 without reporting anything')

        for pu in self.popups:
            if pu['modal'] and pu['group']:
                out.append(f"popup {pu['name']!r} is modal AND grouped - modal popups are "
                           f'always ungrouped, and Build makes their references')
            if not pu['group'] or not pu['size']:
                continue
            for rect in refs.get(pu['group'], []):
                if tuple(pu['size']) != (rect[2], rect[3]):
                    out.append(f"popup {pu['name']!r} is {pu['size'][0]}x{pu['size'][1]} but "
                               f'its reference is {rect[2]}x{rect[3]} - a popup inherits its '
                               f"reference's dimensions (Standards p.70)")
        return out

    def _name_rules(self):
        """Page and popup NAMES must be unique within a project.

        GUI Designer enforces this at build time - "Duplicate page or popup page
        names are not allowed within the same project" - and it is a build
        ERROR, not a warning. Cheap to check here; a wasted Windows round trip
        otherwise.
        """
        out = []
        seen = {}
        for kind, items in (('page', self.pages), ('popup', self.popups)):
            for it in items:
                n = it['name']
                if n in seen:
                    out.append(f'{kind} {n!r} has the same name as {seen[n]} - page and '
                               f'popup names must be unique within a project')
                seen[n] = f'{kind} {n!r}'
        return out

    def check_donor(self, path):
        """Can this donor supply every control type, and do any names collide?

        Clone-never-construct means a type absent from the donor cannot be
        authored at all, and donors genuinely differ: the _alt fixture has no
        PBLevel, Extron's Afterburn 1020 template has no PBLevel either, its 300
        Portrait template has Levels but no Slider, and Mach 1020 has neither
        Level nor Line.

        Names matter too: the generated pages join the DONOR's project, so a
        name that already exists there is a build error even though it is unique
        within the spec.
        """
        from .project import Project
        proj = Project.open(path)
        out = []

        # A donor must be a PROJECT, not a page library. Extron's .glt templates
        # have no PBProject - they are pages, popups and resources with no
        # project wrapper - and everything downstream still appears to work: the
        # types all resolve, the applier writes 16 of 16 ops, the pack succeeds.
        # GUI Designer then silently declines to open the result and offers the
        # Project Create Wizard instead, which reads as "it hung" rather than as
        # a rejection. Caught here it costs a second instead of a build cycle.
        if next(proj.instances('PBProject'), None) is None:
            out.append(
                f'{path} has no PBProject, so it is a page library rather than a '
                f'project. GUI Designer will not open a file built from it - it '
                f'opens empty and shows the Project Create Wizard. Use a real '
                f'.gdl as the donor; to author from Extron content with no client '
                f'material in it, make a seed project first (File > New, pick the '
                f'panel and theme, save) and use that.')

        have, names = set(), set()
        for pg in proj.pages():
            names.add(pg['name'])
            for c in pg['controls']:
                have.add(c['type'])
        out += [f'donor {path} has no {t} to clone - that control type cannot '
                f'be authored from it' for t in sorted(self.needs() - have)]
        for it in list(self.pages) + list(self.popups):
            if it['name'] in names:
                out.append(f"{it['name']!r} already exists in the donor project - page and "
                           f'popup names must be unique, and Build rejects duplicates')
        return out

    def needs(self):
        """Every control class this spec requires a donor for."""
        return {KIND_TYPE.get(c.get('kind', 'panel'), 'PBShape')
                for pg in self.pages for c in pg['controls']}


    def palette(self):
        """Every distinct color the spec uses. p.49 caps a project at six."""
        seen = set()
        for pg in self.pages:
            seen.add(tuple(sorted((pg['background'] or {}).items())))
            for c in pg['controls']:
                for key in ('fill', 'stroke', 'color'):
                    v = color(c.get(key), self.theme)
                    if v:
                        seen.add(tuple(sorted(v.items())))
        return {s for s in seen if s}


def main(argv):
    if len(argv) < 3:
        print(__doc__.strip().split('\n\n')[0])
        print('\n  python -m gdl.spec render <spec.json> <out.png> [page]'
              '\n  python -m gdl.spec check  <spec.json>'
              '\n  python -m gdl.spec plan   <spec.json> <plan.json>'
              '\n  python -m gdl.spec donors <spec.json> <donor.gdl|template.glt>')
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
    if cmd == 'donors':
        problems = panel.check_donor(argv[3])
        for p in problems:
            print('  ' + p)
        print(f'{len(panel.needs())} control type(s) needed: '
              f'{", ".join(sorted(panel.needs()))}')
        print(f'{len(problems)} donor problem(s)')
        return 1 if problems else 0
    if cmd == 'plan':
        if problems:
            for p in problems:
                print('  ' + p)
            return 1
        plan = panel.plan()
        with open(argv[3], 'w', encoding='utf-8') as fh:
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
