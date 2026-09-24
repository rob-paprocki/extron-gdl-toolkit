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
    applies, verified end to end by `powershell/New-GdlPanel.ps1`.

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
import collections
import json
import os
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
    # The pressed halves of the 3D pairs: Turbulence and Shockwave buttons
    # change border per state, from one to its Selected twin.
    'gradient-selected': '3D Gradient Selected',
    'rounded-3d-selected': '3D Rounded Rectangle Selected',
    # No border at all: a kit image button draws its own shape, and the
    # template's own ones reference a border resource named ''. A clone kept
    # the donor's border when the spec named none.
    'none': '',
    'afterburn': 'Afterburn - 10 Radius 2 Thick',
    'afterburn-flat': 'Afterburn - 10 Radius 0 Thick',
    'afterburn-14': 'Afterburn - 14 Radius 0 Thick',
    # An icon button's pressed fill: a circle behind the icon.
    'afterburn-ellipse': 'Afterburn - Elipse 0 Thick',
    # Mach's one border of its own (seeds/Mach 1035.gdl).
    'mach': 'Mach - 10 Radius 2 Thick',
}
# radius/thickness per resource, read from the fixtures' own PBBorderResource
# dataField. Only what the preview needs to draw; the real geometry is Build's.
BORDER_GEOMETRY = {
    '': (0, 0),
    '2D Rectangle': (0, 3), '2D Rectangle_1': (0, 0),
    '2D Rounded Rectangle': (10, 3), '2D Capsule': (9999, 3), '2D Ellipse': (0, 3),
    '3D Rectangle': (0, 1), '3D Rounded Rectangle': (10, 1), '3D Capsule': (9999, 1),
    '3D Gradient': (5, 1),
    # Assumed the same as their unselected twins; not read off a dataField.
    '3D Gradient Selected': (5, 1), '3D Rounded Rectangle Selected': (10, 1),
    'Mach - 10 Radius 2 Thick': (10, 2),
    'Afterburn - 10 Radius 0 Thick': (10, 0),
    'Afterburn - 10 Radius 2 Thick': (10, 2),
    'Afterburn - 14 Radius 0 Thick': (14, 0),
    'Afterburn - Elipse 3 Thick': (10, 3),
    # An ellipse, drawn as a capsule: the preview clamps the radius to half the
    # box, which in the square boxes these take is the circle Build draws.
    'Afterburn - Elipse 0 Thick': (9999, 0),
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
#     and the virtual targets (VTLP Web/iOS/Android/Ecp) are here because GUI
#     Designer still builds for them.
#   * not the enum. `PlatformProTypeEnum` has 60 members to these 55 platforms.
#     `Unknown`, the three MLC 84 button panels and TLP 1022W have no
#     touch-panel platform class behind them, and CreatePlatform returns null.
#     TLP 1230WTG is a sixth odd one out in the other direction: CreatePlatform
#     hands back the *base* `PBTouchPanelPlatformPro` rather than a model class,
#     so it carries a part number but GetDefaultResolutionDpi falls through to
#     the 800x480 default. Its real 1920x720 canvas is read off a built project
#     instead - see `docs/design-rules.md` section 1.
MODELS_FULL = {
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
    'VTLPEcp': (1920, 1080, 220.0, '60-sVTLPEcp'),
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

# Button feedback states. GUI Designer 1.28.0.7 reports MaxAllowedStateCount =
# 256 on PBProject, on the TLP Pro 1035 platform and on PBButton, read through
# the installed assemblies. The corpus never goes past four.
MAX_STATES = 256
STATE_KEYS = {'name', 'fill', 'stroke', 'color', 'text_color', 'border', 'text', 'image'}
# How a button's image sits in it, as Extron's own image buttons all have it:
# ImageLayoutEnum Fill (fit, keeping the aspect) and AlignmentEnum
# MiddleCenter. The kit draws each icon, its selection line and its label room
# at the button's own aspect, so fitting it fills the button.
IMAGE_LAYOUT, IMAGE_ALIGN = 0, 3
# The two per-button pointers into the state list, as backing fields.
# TLPDefaultStateID is 0 on every button in the corpus. TLPPressFeedbackStateID
# is the state shown while the button is held: On (1) on all 7518 Off/On
# buttons in the seeds and fixtures, the last state on Extron's own 4-state
# volume mute.
PRESS_FIELD = '<TLPPressFeedbackStateID>k__BackingField'
DEFAULT_FIELD = '<TLPDefaultStateID>k__BackingField'

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
            # These three carry NO `Field` suffix, unlike `orientationField`
            # right beside them. Read off `Extron.GUICPro.PBSlider` in
            # `GUI Designer.exe` - which is NOT the same type as
            # `Extron.GUICPro.Layout.Data.PBSlider` in Layout.NET, where the
            # same four values are auto-properties with `k__BackingField`
            # names. The authoring graph holds the former. Getting this wrong
            # is invisible: Set-GdlFieldIfPresent warns and continues, so the
            # slider builds fine at the donor's dimensions.
            out['sliderTrackWidth'] = c.get('track', 10)
            out['sliderThumbWidth'] = c.get('thumb', 50)
            out['sliderThumbHeight'] = c.get('thumb', 50)
    if kind == 'line':
        # Endpoints are an eight-position enum on the control's own rect, so a
        # diagonal is TopLeft -> BottomRight at whatever angle the rect gives.
        out['startPointField'] = LINE_POS.get(c.get('from', 'MiddleLeft'), 6)
        out['endPointField'] = LINE_POS.get(c.get('to', 'MiddleRight'), 2)
        out['thicknessField'] = c.get('thickness', 2)
    if kind == 'datetime':
        pattern = clock_pattern(c.get('format'))
        out['patternField'] = pattern
        out['textField'] = clock_sample(pattern)
    return out


# A clock's format is the .NET date pattern in `patternField`; PBDateTime has
# no format enum. `textField` holds that pattern rendered for 28 September 1960
# at midnight - the sample every Extron seed carries, and what layout.json
# reports as the clock's Text. A cloned clock kept the donor's pattern, so a
# "date" clock built showing the date and the time.
CLOCK_FORMATS = {'date': 'MMMM d', 'time': 'h:mm tt', 'datetime': 'MMMM d, h:mm tt'}
_CLOCK_TOKEN = re.compile(r"MMMM|MMM|MM|M|dddd|ddd|dd|d|yyyy|yy|HH|H|hh|h|mm|m|ss|s|tt|t|'[^']*'|.")


def clock_pattern(fmt):
    """A spec clock's `format` - date, time, datetime, or a .NET pattern."""
    return CLOCK_FORMATS.get(fmt or 'time', fmt)


def clock_sample(pattern):
    """`pattern` rendered for Wednesday 28 September 1960, 00:00:00."""
    words = {'MMMM': 'September', 'MMM': 'Sep', 'MM': '09', 'M': '9',
             'dddd': 'Wednesday', 'ddd': 'Wed', 'dd': '28', 'd': '28',
             'yyyy': '1960', 'yy': '60', 'HH': '00', 'H': '0', 'hh': '12', 'h': '12',
             'mm': '00', 'm': '0', 'ss': '00', 's': '0', 'tt': 'AM', 't': 'A'}
    return ''.join(words.get(t, t.strip("'") if t.startswith("'") else t)
                   for t in _CLOCK_TOKEN.findall(pattern))


# Extron.GUICPro.ControlLinePositionEnum, read out of the assemblies.
LINE_POS = {'TopCenter': 0, 'TopRight': 1, 'MiddleRight': 2, 'BottomRight': 3,
            'BottomCenter': 4, 'BottomLeft': 5, 'MiddleLeft': 6, 'TopLeft': 7}


def _argb(c):
    """{'A','R','G','B'} -> the packed 0xAARRGGBB int System.Drawing.Color holds."""
    if not c:
        return None
    return (c['A'] << 24) | (c['R'] << 16) | (c['G'] << 8) | c['B']


# Where a spec's `images` paths resolve when relative: Extron's theme resource
# kits, from vendor/ (vendor/README.md) or the install.
RESOURCE_ROOTS = (
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'vendor', 'extron', 'Resources'),
    r'C:\Users\Public\Documents\Extron\GUI Designer Templates\Resources',
)


def resolve_image(path):
    """A spec `images` path -> an existing file, or None."""
    if not path:
        return None
    if os.path.isabs(path):
        return path if os.path.exists(path) else None
    for root in RESOURCE_ROOTS:
        p = os.path.join(root, *path.replace('\\', '/').split('/'))
        if os.path.exists(p):
            return p
    return None


HEX = re.compile(r'^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')
# Written where a spec gives no color, so the clone does not keep its donor's.
TRANSPARENT = {'A': 0, 'R': 0, 'G': 0, 'B': 0}


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
        # Image resources the spec brings with it: name -> file (resolve_image).
        # A page's `background_image` names one of these or one the donor
        # already defines.
        self.images = dict(spec.get('images') or {})
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
    @staticmethod
    def _allocate(controls, base, taken):
        """Hand out userIds in a per-page band, honouring anything pinned.

        Extron numbers a page's controls in a band related to the page number
        (a 2000-series page carries 2000-series ids), which is convention rather
        than anything the engine enforces - but a generated panel that ignores
        it reads as generated.

        `taken` is shared across the WHOLE project, because the control program
        addresses a control by ID alone: extronlib binds one object per ID on a
        panel, so an ID handed to two unrelated controls makes one button's
        handler fire for the other's press. It arrives pre-seeded with every
        pinned ID, so allocation never lands on one - and a pinned ID may still
        repeat, deliberately, because mirroring one button onto several popups
        under one ID is Extron's own practice (Liberty Bank's 81/82).
        """
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
        # Flatten every container first: allocation needs every pinned ID in
        # the project before it hands out the first free one.
        flat_popups = []
        for pu in self.spec.get('popups') or []:
            self._groups = {}
            flat_popups.append((pu, self._controls(pu.get('controls') or [], []),
                                dict(self._groups)))
        flat_pages = []
        for pg in self.spec.get('pages') or []:
            self._groups = {}
            flat_pages.append((pg, self._controls(pg.get('controls') or [], []),
                               dict(self._groups)))
        taken = {c['id'] for _, cs, _ in flat_pages + flat_popups for c in cs
                 if c.get('id')}

        for i, (pg, controls, groups) in enumerate(flat_pages):
            page_no = pg.get('number')
            if page_no is None:
                page_no = 1000 * (i + 1)
            self._allocate(controls, pg.get('id_base') or page_no + 1, taken)
            self.pages.append({
                'number': page_no,
                'name': pg.get('name') or f'Page {page_no}',
                'modal': bool(pg.get('modal')),
                'background': color(pg.get('background') or self.theme.get('background')
                                     or '#000000', self.theme),
                # Drawn over the background color, stretched to the page. One
                # image on every page is the themes' own rule, so the theme can
                # name it once.
                'background_image': pg.get('background_image',
                                           self.theme.get('background_image')),
                'controls': controls,
                'group_sizes': groups,
            })

        self.popups = []
        for i, (pu, controls, groups) in enumerate(flat_popups):
            # A band per popup. The default used to be 9000 + i, so popup i's
            # band began inside popup i-1's and two unnumbered popups shared IDs.
            number = pu.get('number', 9000 + 100 * i)
            self._allocate(controls, pu.get('id_base') or number + 1, taken)
            modal = bool(pu.get('modal'))
            size = pu.get('size')
            if modal and not size:
                # Every modal popup in the corpus is full-canvas - 7 in Liberty
                # Bank, 19 in the Afterburn seed, 13 in Shockwave - and Build
                # places a full-canvas reference for each on every page. So the
                # canvas is the modal's size, not a choice.
                size = list(self.size)
            self.popups.append({
                'number': number,
                'name': pu.get('name') or f'Popup {number}',
                'group': pu.get('group'),
                # A popup inherits its reference's dimensions (GUI Design
                # Standards p.70), so its own size is the anchor's, not its own
                # choice. Recorded for the check, not authored.
                'size': size,
                'modal': modal,
                'background': color(pu.get('background') or self.theme.get('background')
                                     or '#000000', self.theme),
                'controls': controls,
                'group_sizes': groups,
            })

        # The page the panel boots into. Without it a generated panel opens on
        # the DONOR's start page - a built panel from the Liberty Bank donor
        # reported DefaultPage 21, the client's '1000 - Home'.
        self.start_page = self.spec.get('start_page') or (
            self.pages[0]['name'] if self.pages else None)

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
                # A button with named states draws its first one, as Build does.
                c = self._default_look(c)
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
                    # A clock has no text of its own; it shows its pattern's
                    # sample, as GUI Designer does.
                    'Text': c.get('text') or _type_fields(c.get('kind', 'panel'), c)
                    .get('textField', ''),
                    'TextColor': color(c.get('color') or self.theme.get('text')
                                        or '#FFFFFF', self.theme),
                    'TextAlignment': ALIGN.get(c.get('align', 'center'), 3),
                    'Font': {'Name': font,
                             'PointSize': c.get('size') or self.theme.get('size') or 14,
                             'Style': {'Bold': bool(c.get('bold')),
                                       'Italic': bool(c.get('italic'))}},
                }
                controls.append(out)
                image = resolve_image(self.images.get(c.get('image'))) if c.get('image') else None
                if fill or image:
                    radius, thickness = BORDER_GEOMETRY.get(border, (0, 0))
                    # Keyed the way gdl/compose.py looks it up: (page id,
                    # control id), the pair both models share.
                    fills[(pg['number'], out['ID'])] = {
                        'fill': fill,
                        'stroke': color(c.get('stroke'), self.theme),
                        'border': {'resource': border, 'radius': radius,
                                   'thickness': thickness},
                        'image': image,
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
                'background_image': self._image_op(pg.get('background_image')),
                'clear_controls': True,
                # Same helper popups use. Building these two separately is what
                # dropped 'group' from every page op and left popup references
                # bound to the donor's group.
                'controls': [self._op_for(c, i) for i, c in enumerate(pg['controls'])],
            })

        return {
            'generated_by': 'gdl.spec',
            # By NAME: the applier resolves it to the id it gives that page,
            # which only exists once the donor has decided what is free.
            'default_page': self.start_page,
            'popup_groups': sorted({p['group'] for p in self.popups if p['group']}),
            'popups': self._popup_ops(),
            # Appended to the donor's resource library where it lacks them;
            # the applier leaves one it already has alone.
            'images': [{'name': n, 'file': resolve_image(f)} for n, f in self.images.items()],
            'canvas': list(self.size),
            'note': ('Apply with powershell/Apply-GdlPlan.ps1 under 32-bit '
                     'Windows PowerShell 5.1. Page ids are assigned by the '
                     'applier via Get-GdlNextPageId, not here - the donor '
                     'project decides what is free.'),
            'pages': pages,
        }

    def _image_op(self, name):
        """A page's background image, or a button state's, for the plan: its
        resource name, and its file when the spec brings it - the verifier
        composites that file to check the built artwork."""
        if not name:
            return None
        return {'name': name, 'file': resolve_image(self.images.get(name))}

    # -- checks ------------------------------------------------------------
    def check(self):
        """Problems a human would otherwise find on the Windows box."""
        out = []
        for name, f in self.images.items():
            if not resolve_image(f):
                out.append(f'image {name!r}: {f!r} is not a file here or under '
                           f"{' or '.join(RESOURCE_ROOTS)}")
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
        for pu in self.popups:
            seen = {}
            for c in pu['controls']:
                where = f"popup {pu['name']!r} {c.get('name') or c.get('text') or '?'}"
                if c['id'] in seen:
                    out.append(f"{where}: id {c['id']} already used by {seen[c['id']]}")
                seen[c['id']] = where
        out += self._popup_rules()
        out += self._name_rules()
        out += self._state_rules()
        if self.start_page is not None and \
                self.start_page not in {pg['name'] for pg in self.pages}:
            out.append(f'start_page {self.start_page!r} is not a page in this spec - the '
                       f'panel boots into it, so it must be one of the pages authored '
                       f'here (a popup cannot be a start page)')
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
                        out.append(f"page {pg['number']} {a.get('name') or a.get('text') or '?'} / "
                                   f"{b2.get('name') or b2.get('text') or '?'}: {gap_y}px vertical gap is "
                                   f'below the {spacing}px minimum (2mm, p.56)')
                    elif gap_y < 0 and 0 <= gap_x < spacing:
                        out.append(f"page {pg['number']} {a.get('name') or a.get('text') or '?'} / "
                                   f"{b2.get('name') or b2.get('text') or '?'}: {gap_x}px horizontal gap is "
                                   f'below the {spacing}px minimum (2mm, p.56)')
        return out

    def _feedback(self, c):
        """The states a button asks for, in order, as spec dicts - or None.

        A button that looks the same in every state is inert: the control
        system sets it On and nothing on the panel changes. Every generated
        button used to be exactly that, because the applier wrote one
        appearance to every state of the cloned donor.

        `states` names them outright - a name, or a name with its own fill,
        stroke, color, border and caption - for idioms like Extron's 4-state
        volume mute ('Muted', 'Level 1', 'Level 2', 'Level 3') or 3-state call
        button ('Unavailable', 'Ready', 'Connected'). `on`, on the button or the
        theme, is shorthand for two states named Off and On. That pair is not a
        guess: across Extron's six theme templates plus the Liberty Bank project
        it covers 3475 of 3668 buttons (94.7%), 60% of them with different
        fills and 68% with different artwork.
        """
        if c.get('kind') != 'button':
            return None
        if 'states' in c:
            st = c['states']
            if not isinstance(st, list):
                return None                 # _state_rules reports it
            return [dict(s) if isinstance(s, dict) else {'name': s} for s in st]
        on = c.get('on', self.theme.get('on'))
        if not on:
            return None
        if on is True:                      # "give it feedback, you pick"
            if not self.theme.get('accent'):
                return None
            on = {'fill': 'accent'}
        if not isinstance(on, dict):
            # A bare color is the common case: "on": "accent".
            on = {'fill': on}
        return [{'name': 'Off'}, dict(on, name='On')]

    def _states_for(self, c, fill, stroke, text_color, border):
        """The planned appearance of every state, or None for a button that
        asked for no feedback.

        A state inherits whatever it does not name from the button itself, so
        `"on": "accent"` changes the fill and nothing else, and a bare state
        name is the button's own look.
        """
        specs = self._feedback(c)
        if not specs:
            return None
        out = []
        for s in specs:
            has_color = 'color' in s or 'text_color' in s
            out.append({
                'name': s.get('name'),
                'fill': _argb(color(s['fill'], self.theme)) if 'fill' in s else _argb(fill),
                'stroke': (_argb(color(s['stroke'], self.theme))
                           if 'stroke' in s else _argb(stroke)),
                'text_color': (_argb(color(s.get('color') or s.get('text_color'), self.theme))
                               if has_color else _argb(text_color)),
                'border': (BORDERS.get(s['border'], s['border']) if s.get('border') is not None
                           else border),
                'text': s['text'] if 'text' in s else (c.get('text') or ''),
                'image': self._image_op(s['image'] if 'image' in s else c.get('image')),
            })
        return out

    def _press(self, c, states):
        """The index of the state shown while the button is held.

        Set on every button that plans its states rather than inherited: a
        clone keeps the donor's pointer, which may name a state the clone no
        longer has. Off/On buttons show On (1) - all 7518 in the seeds and
        fixtures - so that is the default.
        """
        names = [s['name'] for s in states]
        if c.get('press') in names:
            return names.index(c['press'])
        return 1 if len(states) > 1 else 0

    def _default_look(self, c):
        """The control as it first appears: its own look, overridden by
        whatever its first named state sets. Build renders a button from
        TLPDefaultStateID, which is 0 on every button in the corpus."""
        st = c.get('states') if c.get('kind') == 'button' else None
        if not isinstance(st, list) or not st or not isinstance(st[0], dict):
            return c
        s0 = st[0]
        out = dict(c)
        for k in ('fill', 'stroke', 'border', 'text', 'image'):
            if k in s0:
                out[k] = s0[k]
        if 'color' in s0 or 'text_color' in s0:
            out['color'] = s0.get('color') or s0.get('text_color')
        return out

    def _base_look(self, c):
        """(fill, stroke, text color, border) for a spec control, as authored.

        No stroke is a TRANSPARENT stroke, written as one. The applier skips a
        color it is not given, so a control with none kept its donor's outline:
        a panel with no `stroke` built with the seed's #6A6E89 edge while the
        preview drew none, found by putting the canvas beside the build.

        A button with no fill is a TRANSPARENT one, for the same reason, state
        by state: a state the spec gives no fill kept its donor state's, and
        the Afterburn seed's On state is #37394E - so a kit image button's
        Ready, On and Muted states built on a raised slab, found by
        verify_built's image check.
        """
        fill = color(c.get('fill'), self.theme)
        stroke = color(c.get('stroke'), self.theme) or dict(TRANSPARENT)
        text_color = color(c.get('color') or self.theme.get('text') or '#FFFFFF',
                           self.theme)
        border = c.get('border')
        border = BORDERS.get(border, border)
        if border is None and fill is not None:
            border = BORDERS['rounded']
        if fill is None and c.get('kind') == 'button':
            fill = dict(TRANSPARENT)
        return fill, stroke, text_color, border

    def _state_rules(self):
        """A button's states must be ones a program can tell apart."""
        out = []
        for kind, items in (('page', self.pages), ('popup', self.popups)):
            for pg in items:
                for c in pg['controls']:
                    out += self._states_of(c, f"{kind} {pg['name']!r} "
                                              f"{c.get('name') or c.get('text') or '?'}")
        return out

    def _states_of(self, c, where):
        out = []
        asked = [k for k in ('states', 'press') if k in c]
        if c.get('kind') != 'button':
            if asked:
                out.append(f"{where}: only a button has feedback states, so "
                           f"{' and '.join(asked)} would do nothing on a {c.get('kind', 'panel')}")
            return out
        if 'states' in c and 'on' in c:
            out.append(f'{where}: give `on` or `states`, not both - `on` is shorthand for '
                       f'two states named Off and On')
        if 'states' not in c and c.get('on', self.theme.get('on')) is True \
                and not self.theme.get('accent'):
            out.append(f'{where}: `on`: true picks the theme accent, and the theme has none - '
                       f'the button would get no feedback. Add theme.accent, or give `on` '
                       f'a color')
        if 'states' in c:
            st = c['states']
            if not isinstance(st, list) or not st:
                return out + [f'{where}: states must be a list of at least one state']
            if len(st) > MAX_STATES:
                out.append(f'{where}: {len(st)} states is more than the {MAX_STATES} GUI '
                           f'Designer allows on a button')
            names = []
            for i, s in enumerate(st):
                if isinstance(s, dict):
                    extra = sorted(set(s) - STATE_KEYS)
                    if extra:
                        out.append(f"{where}: state {i} has unknown key(s) {', '.join(extra)} - "
                                   f"a state takes {', '.join(sorted(STATE_KEYS))}")
                    b = s.get('border')
                    if b and b not in BORDERS and b not in BORDER_GEOMETRY:
                        out.append(f'{where}: state {i}: unknown border resource {b!r}')
                    # A null would reach the applier as "nothing to write", and
                    # the state would keep whatever the cloned donor state had.
                    nulls = sorted(k for k in STATE_KEYS - {'name'} if k in s and s[k] is None)
                    if nulls:
                        out.append(f"{where}: state {i}: {', '.join(nulls)} is null - leave "
                                   f"the key out to keep the button's own, or give "
                                   f"'#00000000' for transparent or '' for no caption")
                    s = s.get('name')
                if not isinstance(s, str) or not s.strip():
                    out.append(f'{where}: state {i} has no name - a state is a name, or an '
                               f'object with a name')
                    continue
                names.append(s)
            dup = sorted({n for n in names if names.count(n) > 1})
            if dup:
                out.append(f"{where}: state name(s) {', '.join(map(repr, dup))} used twice - "
                           f'the program and the ID map tell states apart by name')
            if not out:
                look = self._states_for(c, *self._base_look(c)) or []
                for i, a in enumerate(look):
                    for b in look[i + 1:]:
                        if {k: v for k, v in a.items() if k != 'name'} == \
                                {k: v for k, v in b.items() if k != 'name'}:
                            out.append(f"{where}: states {a['name']!r} and {b['name']!r} look "
                                       f'identical - the program could set either and the '
                                       f'panel would show no difference. Give one its own '
                                       f'fill, stroke, color, border, text or image')
        if 'press' in c:
            specs = self._feedback(c) or []
            names = [s.get('name') for s in specs]
            if not specs:
                out.append(f"{where}: press {c['press']!r} names a state, but the button has "
                           f'no states - give it `states` or `on`')
            elif c['press'] not in names:
                out.append(f"{where}: press {c['press']!r} is not one of its states "
                           f"({', '.join(map(repr, names))})")
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
        fill, stroke, text_color, border = self._base_look(c)
        states = self._states_for(c, fill, stroke, text_color, border)
        op = {
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
                # A reference has its OWN modalField, True on the references
                # Build generates for modal popups - and a seed's first
                # reference is one of those (126 of 131 in the Afterburn 1035
                # seed). A clone inherited True, and Build dropped the authored
                # group reference as one of its own on the next build, with 0
                # errors. The Liberty Bank donor hid it: its first is grouped.
                **({'modalField': False} if kind == 'popup_ref' else {}),
            },
            'fill': _argb(fill),
            'stroke': _argb(stroke),
            'border': border,
            'text_color': _argb(text_color),
            # Per-state appearance, when the button asked for one. The applier
            # gives the clone exactly this many states and writes each; it
            # falls back to the flat values above for every donor state when
            # this is absent, which is what a control with no feedback wants.
            'states': states,
            'alignment': ALIGN.get(c.get('align', 'center'), 3),
            'font': {'name': c.get('font') or self.theme.get('font') or 'Arial',
                     'size': c.get('size') or self.theme.get('size') or 14,
                     'bold': bool(c.get('bold')), 'italic': bool(c.get('italic'))},
            # Only meaningful on a popup reference; the applier ignores it
            # elsewhere.
            'group': c.get('group'),
            # A kit image on every state, or none: a clone's donor icon is
            # cleared either way.
            'image': self._image_op(c.get('image')),
            'image_layout': IMAGE_LAYOUT,
            'image_align': IMAGE_ALIGN,
            # A slider's thumb, where the template draws it from its kit
            # (Afterburn: sliderThumbImageField, in the secondary accent).
            'thumb_image': self._image_op(c.get('thumb_image')) if kind == 'slider' else None,
        }
        if states:
            # Build renders the button from state 0, so that is what the
            # control-level fields - and verify_built's checks of them - carry.
            first = states[0]
            op.update(fill=first['fill'], stroke=first['stroke'],
                      text_color=first['text_color'], border=first['border'],
                      image=first['image'])
            op['fields']['textField'] = first['text']
            op['fields'][DEFAULT_FIELD] = 0
            op['fields'][PRESS_FIELD] = self._press(c, states)
        return op

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
            if pu['modal'] and pu['size'] and tuple(pu['size']) != tuple(self.size):
                out.append(f"popup {pu['name']!r} is modal but {pu['size'][0]}x"
                           f"{pu['size'][1]}, not the {self.size[0]}x{self.size[1]} canvas - "
                           f'every modal in the corpus is full-canvas, and Build shows it '
                           f'through a full-canvas reference. Draw the card inside it.')
            if not pu['modal'] and not pu['group']:
                out.append(f"popup {pu['name']!r} is neither modal nor in a group, so no "
                           f'reference can show it - a standard popup is shown through a '
                           f'reference bound to its group')
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

        # Border resources, for the same clone-never-construct reason and with a
        # much wider spread than control types. Missed here it costs a whole
        # Windows round trip: Set-GdlBorder reports it per control at apply time,
        # by which point the plan has already been applied and packed.
        # DEFINED, not referenced. border_resources() walks the references, so a
        # donor that defines 2D Capsule but never draws with it would look like
        # it lacked one - which is the false positive this check first produced,
        # against a spec that had already built cleanly.
        borders = proj.border_resource_names()
        for want in sorted(self.needs_borders() - borders):
            out.append(f'border resource {want!r} is not defined in {path} - a '
                       f'spec may only name resources the donor already carries. '
                       f'It defines: {", ".join(sorted(borders))}')

        # Fonts, for the same reason but a softer failure: a family the donor
        # lacks does not stop the build, it silently ships in the donor's face.
        # The three-page panel built cleanly in Open Sans while its spec asked
        # for Forma DJR Display, and only the built-file verifier noticed.
        fonts = proj.font_resource_names()
        for want in sorted(self.needs_fonts() - fonts):
            out.append(f'font family {want!r} has no resource in {path}, so every '
                       f'control asking for it will build in the donor\'s face '
                       f'instead. It defines: {", ".join(sorted(fonts))}')

        # Canvas. The spec lays out against its own `size`, but the built panel
        # is whatever model the DONOR is - the spec's `model` only feeds the
        # touch-target check. Author 1024x600 into a 1280x800 project and the
        # layout is right by its own arithmetic and wrong on the panel.
        canvas = collections.Counter(
            tuple(pg['size']) for pg in proj.pages()
            if pg.get('kind') != 'popup' and pg.get('size'))
        if canvas:
            donor_size, _ = canvas.most_common(1)[0]
            if tuple(self.size) != donor_size:
                out.append(
                    f'spec canvas {tuple(self.size)} does not match the donor\'s '
                    f'{donor_size}. The built panel is the donor\'s model, so the '
                    f'layout would be sized for a panel this is not. Match the '
                    f'spec to the donor, or retarget the donor first '
                    f'(python -m gdl.edit).')
        # Feedback states. The applier gives each cloned button exactly the
        # states the spec names, cloning its last state to grow and dropping
        # from the end to trim (Set-GdlStateCount). What stops it is
        # PBStates.statusField - PBState.StatusFlags, PreventAddState and
        # friends - on the button it clones, which is the FIRST PBButton in
        # page-then-popup order (Get-GdlDonor). 0 on every button in the corpus,
        # so this is a guard, not a thing seen.
        if any(self._feedback(c) for pg in self.pages + self.popups
               for c in pg['controls']):
            first = next((c for pg in proj.pages() for c in pg['controls']
                          if c['type'] == 'PBButton'), None)
            if first and first.get('state_flags'):
                out.append(
                    f"the donor button {first['name']!r} in {path} carries state status "
                    f"flags {first['state_flags']} (PBState.StatusFlags), which forbid "
                    f'adding or removing states - the applier refuses to resize it, so '
                    f'no button in this spec would get the states it names')

        # An image the spec does not bring must be one the donor has.
        images = proj._resource_names('PBImageResource')
        for pg in self.pages:
            want = pg.get('background_image')
            if want and want not in self.images and want not in images:
                out.append(f"page {pg['name']!r}: background image {want!r} is neither in "
                           f"the spec's `images` nor defined in {path}")
        for kind, items in (('page', self.pages), ('popup', self.popups)):
            for pg in items:
                for c in pg['controls']:
                    named = [c.get('image'), c.get('thumb_image')] + [
                        st.get('image') for st in c.get('states') or [] if isinstance(st, dict)]
                    for want in sorted({n for n in named if n}):
                        if want not in self.images and want not in images:
                            out.append(f"{kind} {pg['name']!r} "
                                       f"{c.get('name') or c.get('text') or '?'}: image "
                                       f"{want!r} is neither in the spec's `images` nor "
                                       f'defined in {path}')

        for it in list(self.pages) + list(self.popups):
            if it['name'] in names:
                out.append(f"{it['name']!r} already exists in the donor project - page and "
                           f'popup names must be unique, and Build rejects duplicates')
        return out

    def needs(self):
        """Every control class this spec requires a donor for."""
        return {KIND_TYPE.get(c.get('kind', 'panel'), 'PBShape')
                for pg in self.pages + self.popups for c in pg['controls']}

    def needs_borders(self):
        """Every named border RESOURCE this spec references, already resolved.

        A spec may only point at a resource the donor already carries - creating
        one has never been tested against GUI Designer - so which donor you use
        decides which borders are available. That varies far more than it looks:
        the client fixture carries 32 and a fresh themed project carries 6.
        `2D Capsule` is in the first and not the second.
        """
        out = set()
        for pg in self.pages + self.popups:
            for c in pg['controls']:
                # A state can name its own border, and it needs a resource too.
                for look in [c] + (self._feedback(c) or []):
                    b = look.get('border')
                    # `none` is an empty name, not a resource.
                    if b and BORDERS.get(b, b):
                        out.add(BORDERS.get(b, b))
        return out

    def needs_fonts(self):
        """Every font family this spec asks for, theme default included."""
        out = set()
        default = self.theme.get('font')
        for pg in self.pages + self.popups:
            for c in pg['controls']:
                f = c.get('font') or default
                if f:
                    out.add(f)
        return out


    def palette(self):
        """Every distinct color the panel shows. p.49 caps a project at six.

        Counted from what each control draws, not only from what the spec
        names: a caption with no `color` is drawn in the theme's text color, or
        white, and a popup is on the panel as much as a page is. Counting only
        named colors let a spec pass at six while the panel showed seven.
        """
        seen = set()

        def add(v):
            if v and v.get('A'):            # a transparent color draws nothing
                seen.add(tuple(sorted(v.items())))

        for pg in self.pages + self.popups:
            # A modal's background never reaches the panel: Build draws every
            # modal as the page beneath under black at alpha 166.
            if not pg.get('modal'):
                add(pg['background'])
            for c in pg['controls']:
                # A state's colors are on the panel as much as the control's
                # own - an On fill included.
                for look in [c] + (self._feedback(c) or []):
                    for key in ('fill', 'stroke', 'color', 'text_color'):
                        add(color(look.get(key), self.theme))
                if self._default_text_shown(c):
                    # Resolved only when something draws in it, as the
                    # applier does (_base_look).
                    add(color(self.theme.get('text') or '#FFFFFF', self.theme))
        return seen

    def _default_text_shown(self, c):
        """Does any caption on this control draw in the default text color?

        A clock draws the time whatever its `text`, so it always has one.
        """
        if c.get('color'):
            return False
        specs = self._feedback(c)
        if not specs:
            return bool(c.get('text')) or c.get('kind') == 'datetime'
        return any(s.get('text', c.get('text')) and not ('color' in s or 'text_color' in s)
                   for s in specs)


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
