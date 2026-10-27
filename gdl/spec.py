"""Describe a panel declaratively, lay it out, and render it - without Windows.

The gap this fills is the one CLAUDE.md names: generating a panel from a spec
rather than by cloning an existing one. Two of the three missing pieces live
here, because they are pure arithmetic and need nothing installed:

  * a **layout pass** - `grid` and `stack` turn "six buttons across this region
    with a 16px gutter" into rects, so nothing is a hand-typed literal
  * **ID allocation** - page numbers and per-control `userId`s handed out in
    bands, unique within a page, skipping anything the spec pins by hand and
    any ID it retires (`_retired`: a previous delivery's, docs/idmap.md §9)

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
    python -m gdl.spec plan   examples/panel.json out/plan.json --donor "seeds/Afterburn 1035.gdl"

What it cannot do is prove GUI Designer will accept the result. Nothing here
touches a real `.gdl`; see docs/from-scratch.md for what still needs a human.
"""
import collections
import json
import math
import os
import re
import sys
from fractions import Fraction

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
# dataField. Only what the preview needs to draw; the real geometry is Build's,
# and a seed's own (Project.border_geometry) can differ: Mach's 1035 defines
# 2D Rounded Rectangle at radius 1 and thickness 0.
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
    # The 320's own: its seed has no 10 Radius pair (seeds/Afterburn 320.gdl).
    'Afterburn - 7 Radius 2 Thick': (7, 2),
    'Afterburn - Elipse 3 Thick': (10, 3),
    # An ellipse, drawn as a capsule: the preview clamps the radius to half the
    # box, which in the square boxes these take is the circle Build draws.
    'Afterburn - Elipse 0 Thick': (9999, 0),
}

# A border resource's shape - (kind, radius, thickness), kind '2d' or '3d' with
# '-ellipse' for an ellipse - from its name where the name says it ("Afterburn
# - 10 Radius 2 Thick"), else from BORDER_GEOMETRY; None where neither does.
# The `zGD - Default` copies 15 of the 29 seeds and fixtures carry are among
# those, and every project carries the plain built-ins.
_RADIUS_THICK = re.compile(r'(\d+)\s*Radius\s*(\d+)\s*Thick', re.I)
_THICK = re.compile(r'(\d+)\s*Thick', re.I)


def border_shape(name):
    if not name:
        return None
    kind = '3d' if name.startswith('3D') else '2d'
    if re.search(r'el+ipse', name, re.I):         # Extron spells its own Elipse
        m = _THICK.search(name)
        thick = int(m.group(1)) if m else (BORDER_GEOMETRY.get(name) or (0, None))[1]
        return None if thick is None else (kind + '-ellipse', 0, thick)
    m = _RADIUS_THICK.search(name)
    if m:
        return kind, int(m.group(1)), int(m.group(2))
    if name in BORDER_GEOMETRY:
        return (kind,) + tuple(BORDER_GEOMETRY[name])
    return None


def _border_family(name):
    """'Afterburn - 10 Radius 2 Thick' -> 'Afterburn'; a built-in -> None."""
    return name.split(' - ', 1)[0] if ' - ' in name else None


def nearest_border(wanted, defined):
    """The border resource in `defined` - a donor's - to build `wanted` as
    where the donor lacks it, or None: of the same kind (2D, 3D, ellipse), from
    the same family first - a theme's own, or the built-ins - then of the
    nearest thickness, then the nearest radius. That is the Afterburn design system's
    own choice for the 320, whose seed has no 10-radius pair: 10 Radius 2 Thick
    builds as 7 Radius 2 Thick, and 10 Radius 0 Thick as 14 Radius 0 Thick."""
    want = border_shape(wanted)
    if want is None:
        return None
    kind, radius, thick = want
    cands = [(n, s) for n, s in ((n, border_shape(n)) for n in defined)
             if n != wanted and s and s[0] == kind]
    family = _border_family(wanted)
    pool = [c for c in cands if _border_family(c[0]) == family] or cands
    if not pool:
        return None
    return min(pool, key=lambda c: (abs(c[1][2] - thick), abs(c[1][1] - radius), c[0]))[0]
# Every panel GUI Designer can target: (width, height, DPI, Extron part number).
#
# Read out of the ASSEMBLIES, not off the Project Create Wizard's list box.
# `PBTouchPanelPlatformPro.GetDefaultResolutionDpi(type, out w, out h, out dpi)`
# and `CreatePlatform(project, type)` are Extron's own, so this is primary
# source. `powershell/Get-GdlPlatforms.ps1` regenerates the raw capture,
# `research/data/platform-details.txt`, which also lists the resolutions each
# platform supports.
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

# TLP Pro 1230WTG: CreatePlatform returns the base PBTouchPanelPlatformPro, so
# GetDefaultResolutionDpi falls through to 800x480 at 0 DPI (the note above the
# table). Extron's own TemplateInfoTable.config - the template installer's
# table, NRBF, readable with gdl/nrbf.py - gives its "Afterburn 1230 Series"
# 1920x720 at 166.0 DPI, the canvas a built 1230W project reports too
# (docs/design-rules.md section 1), and the one resolution its platform's own
# supportedResolutions lists.
MODELS_FULL['TLP1230WTG'] = (1920, 720, 166.0, MODELS_FULL['TLP1230WTG'][3])

# A model whose panel runs either way up: its platform's own supportedResolutions
# lists both (powershell/Get-GdlPlatforms.ps1, research/data/platform-details.txt),
# and GUI Designer's Project Create Wizard offers a Resolution for it. These six
# M forms are the only panels of one fixed resolution that list a second; their
# T and C forms do not, though the 1035T shares the 1035M's part number.
# MODELS_FULL holds the factory default, first. A theme reaches the second
# orientation only where a template is drawn at it (gdl/templates.py);
# docs/design-rules.md section 1 has which.
ORIENTATIONS = {m: ((MODELS_FULL[m][0], MODELS_FULL[m][1]), (MODELS_FULL[m][1], MODELS_FULL[m][0]))
                for m in ('TLP300M', 'TLP520M', 'TLC521M', 'TLP535M', 'TLP835M', 'TLP1035M')}

# Extron Control Pro's wizard offers two themable presets, TouchLink 1920x1080
# (16:9) and 1280x800 (16:10); its phone and tablet presets are Blank-only and
# have no donor, so they are no canvas here (seeds/README.md). Both are the
# panel's own screen rather than a turned one, so panel_id names the second by
# its size, not by a way up.
PRESETS = {'VTLPEcp': ((1920, 1080), (1280, 800))}

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


def sizes(model):
    """Every canvas a model runs at: its one resolution, both orientations, or
    the presets of a soft client that has them."""
    return ORIENTATIONS.get(model) or PRESETS.get(model) or ((MODELS_FULL[model][0], MODELS_FULL[model][1]),)


def panel_id(model, size=None):
    """A panel by name: its model on the model's own canvas (sizes()[0]), and
    model-Portrait or model-Landscape the other way up of one that rotates, or
    model-<w>x<h> for another preset of a soft client (VTLPEcp-1280x800) - a
    canvas's `panels`, a design system's table, a folder of specs. No model's
    name has a hyphen. ValueError for a canvas the model does not run at."""
    own = sizes(model)
    size = tuple(size) if size else own[0]
    if size not in own:
        raise ValueError(f'a {model} runs at {" or ".join("%dx%d" % s for s in own)}, '
                         f'not {size[0]}x{size[1]}')
    if size == own[0]:
        return model
    if model in PRESETS:
        return f'{model}-{size[0]}x{size[1]}'
    return f"{model}-{'Portrait' if size[1] > size[0] else 'Landscape'}"


def panel_of(pid):
    """(model, canvas) of a panel_id(); ValueError for a name that is not one."""
    model = str(pid).partition('-')[0]
    if model not in MODELS_FULL:
        raise ValueError(f'{pid!r} is not a panel: {model!r} is no model GUI Designer builds for')
    for size in sizes(model):
        if panel_id(model, size) == pid:
            return model, size
    raise ValueError(f'{pid!r} is not a panel: a {model} runs '
                     f'{" or ".join(panel_id(model, s) for s in sizes(model))}')


# Soft clients and interfaces run on a screen their model does not define, so
# the table's DPI for them is GUI Designer's default, not a physical fact.
SOFT_CLIENTS = ('TLI101', 'TLI201', 'VTLPAndroid', 'VTLPEcp', 'VTLPWeb', 'VTLPiOS')

# Structural tiers by physical diagonal - this toolkit's reading of Extron's own
# per-series templates, not an Extron rule. Every theme's >= 7in series (720,
# 1020, 1220, 1520, 1720) share one full structure; its ~5in series (520, 535)
# fold it into a hub page and popups; its ~3.5in ones (300, 320) into
# single-purpose pages. docs/design-rules.md section 1.
TIER_A_INCHES = 6.5
TIER_B_INCHES = 4.0


def diagonal(model):
    """A model's screen diagonal in inches, from pixels and DPI; None for a soft
    client or a model with no DPI."""
    d = dpi(model)
    if model in SOFT_CLIENTS or not d:
        return None
    w, h = MODELS_FULL[model][:2]
    return math.hypot(w, h) / d


def tier_for(inches):
    """The tier a screen of this diagonal falls in, or None without one."""
    if inches is None:
        return None
    return 'A' if inches >= TIER_A_INCHES else ('B' if inches >= TIER_B_INCHES else 'C')


def tier(model):
    """'A' (the full layout), 'B' (a hub page) or 'C' (single-purpose pages)."""
    return tier_for(diagonal(model))


def _panels():
    """resolution -> (models sharing it, the DENSEST model's DPI).

    Derived, so it cannot drift from MODELS_FULL. The densest model is the
    conservative choice: its pixels are the smallest, so its minimum is the
    largest, and a layout that satisfies it satisfies every other panel at that
    resolution. Name the model in the spec when you know it - it is a much
    tighter answer, and the spread within one resolution is nearly 2x.

    The soft clients are excluded from that maximum. The VTLP* targets are a
    phone, a tablet and a browser, and the TLI interfaces drive a screen their
    model does not define, so their 220 "DPI" is GUI Designer's default rather
    than a fixed panel's; letting it set the minimum for 1280x800 or 1920x1080
    would hold every real panel to a number no Extron hardware implies. They
    stay in the model list, and asking for one by name still gives its own
    figure.
    """
    out = {}
    for model, (_, _, d, _) in MODELS_FULL.items():
        for size in sizes(model):
            out.setdefault(size, []).append((model, d))
    res = {}
    for size, ms in out.items():
        physical = [d for m, d in ms
                    if not m.startswith('VTLP') and m not in SOFT_CLIENTS and d]
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
# What a control with no `size`, on a theme with none, builds at. The plan and
# the checks read this one number: the type floor once read a control with no
# size as none and skipped it, so leaving 14 pt out passed a 535's 28 pt floor
# that writing it did not.
DEFAULT_POINT_SIZE = 14


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


# The DPI the type floor is keyed to: the TLP Pro 1025/1035's, the family the
# first design system targets.
TYPE_FLOOR_DPI = 149.0


def type_floor(target):
    """The smallest point size text may take on a panel, or None with no DPI.

    GUI Designer draws a point at 1.375 px whatever the panel (Phase 0's probe,
    docs/gdl-format.md section 2), so Extron's documented 14 pt minimum is 2.2 mm
    of cap height on a 1035 and 1.1 mm on a 535. The floor keeps the 14 pt as it
    reads on a 1025/1035: 14 x DPI / 149, rounded up - a minimum is never
    rounded down - and never under 14. Ours, not Extron's: Extron's own templates
    break it on dense panels - their 520s keep the 1035's points, their 535s
    step up short of it (docs/design-rules.md section 1).
    """
    if isinstance(target, str):
        d = dpi(target)
    else:
        try:
            _, d = PANELS.get(tuple(target), (None, None))
        except TypeError:
            d = None
    if not d:
        return None
    return max(MIN_BODY_POINT_SIZE, math.ceil(MIN_BODY_POINT_SIZE * d / TYPE_FLOOR_DPI - 1e-9))


KIND_TYPE = {'panel': 'PBShape', 'shape': 'PBShape', 'button': 'PBButton',
             'label': 'PBLabel', 'line': 'PBLine', 'image': 'PBImage',
             'slider': 'PBSlider', 'level': 'PBLevel', 'datetime': 'PBDateTime',
             'popup_ref': 'PBPopupPageReference'}
# Every key a control takes. Anything else is ignored - silently - so a typo in
# one (`joind` for `joined`) would drop what it asked for; check() names it.
CONTROL_KEYS = frozenset((
    'kind', 'name', 'rect', 'id', 'text', 'fill', 'stroke', 'color', 'border', 'size', 'bold',
    'italic', 'align', 'font', 'states', 'on', 'press', 'nav', 'does', 'image', 'thumb_image',
    'track_image', 'fill_image', 'group', 'orientation', 'track', 'bar', 'thumb', 'thumb_height', 'from',
    'to', 'thickness', 'format', 'flatten', 'type', 'grid', 'stack', 'icon',
    # An image's own: how its art lies in its box (IMAGE_LAYOUTS).
    'layout',
    # Added by a panel's layout (docs/claude-design.md): navigation it derived,
    # and the segmented control a segment belongs to.
    'derived', 'joined',
))
# And every key the levels above a control take, for the same reason: a key
# nothing reads falls back to its default, and the plan is made from the same
# spec, so verify_built agrees with it. A typo'd `start_page` booted the panel
# into the wrong page with every gate green. A key starting `_` is the
# translator's own, or a note (`_seed`, `_does`, `_why`), and is never refused.
SPEC_KEYS = frozenset((
    'name', 'model', 'size', 'family', 'theme', 'images', 'pages', 'popups', 'start_page',
    'keep_donor_pages', 'type_floor',
    # What the panel does, for the ID map (gdl/idmap.py).
    'does',
))
PAGE_KEYS = frozenset((
    'name', 'number', 'id_base', 'controls', 'background', 'background_image',
    'background_layout',
    # For the ID map: shown by the program rather than a control, what the
    # page is for, and the template's place a panel's layout named rather than
    # drew.
    'reached_by', 'does', 'left',
))
# `modal` is a popup's: the applier never writes it on a page.
POPUP_KEYS = PAGE_KEYS | {'group', 'size', 'modal'}
# What a grid or stack lays out by. Any other key is shared by its items, and
# held to CONTROL_KEYS there.
LAYOUT_KEYS = frozenset(('rect', 'cols', 'rows', 'gap', 'gap_y', 'pad', 'items', 'count',
                         'horizontal', 'name'))
# A theme's settings. Any other key is a color the palette names - `surface`,
# `shade-on` - so one whose value is not a color is a typo.
THEME_SETTINGS = frozenset(('font', 'size', 'on', 'icon_font', 'background_image',
                            'background_layout'))


# A modal's own transparency, in percent. Build draws a modal's page - black,
# and its photo if it has one - at it over the page beneath, and not its
# background color: a spec modal with a #242634 one built black. 456 of the 460
# modals built in the corpus and the archived builds are authored at 35, alpha
# 166, as every Design canvas draws a modal (the profiles' `scrim`); the other
# 4, in the client's archived projects, are at 0 and build opaque. The applier
# wrote none, so a spec modal took its donor modal's.
MODAL_TRANSPARENCY = 35.0


def is_uint16(v):
    """A whole number a UInt16 holds - not a bool, a float or a string."""
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 0xFFFF


def _odd_keys(d, known):
    """The keys of `d` nothing reads, sorted: not in `known`, and not `_`-prefixed."""
    return sorted(k for k in d if k not in known and not str(k).startswith('_'))
# Interactive kinds are the ones held to the 9mm touch-target rule.
TOUCHABLE = {'button', 'slider'}


def mirrors(controls):
    """The ids (Python's, of the dicts) of `controls` that mirror a touch
    target they lie inside: a button with the ID of a larger button or slider
    whose rect holds its own. Shockwave's 1035 and 1535 draw each source tab's
    name so - a caption-only 152x36 button under the tab's glyph with the
    tab's ID, white in both states (its frame's `twin`). A press there is the
    tab's, and the tab shows its states, so the mirror's touch size, its gaps,
    its alike states and the ID it shares are its control's, not its own."""
    out = set()
    for c in controls:
        if c.get('kind') != 'button' or not c.get('id'):
            continue
        x, y, w, h = (int(v) for v in c['rect'])
        for d in controls:
            if d is c or d.get('id') != c['id'] or d.get('kind') not in TOUCHABLE:
                continue
            dx, dy, dw, dh = (int(v) for v in d['rect'])
            if dx <= x and dy <= y and x + w <= dx + dw and y + h <= dy + dh and w * h < dw * dh:
                out.add(id(c))
                break
    return out

# Button feedback states. GUI Designer 1.28.0.7 reports MaxAllowedStateCount =
# 256 on PBProject, on the TLP Pro 1035 platform and on PBButton, read through
# the installed assemblies. The corpus never goes past four.
MAX_STATES = 256
STATE_KEYS = {'name', 'fill', 'stroke', 'color', 'text_color', 'border', 'text', 'image', 'icon'}

# Which face an icon is drawn in, by theme family, and where that face is read
# from, are font facts: gdl/fonts.py (ICON_FONTS, icon_face).
_GLYPHS = {}


def glyph_names(font):
    """{name: codepoint} a face names its glyphs by - {} for one that names
    none - or None when there is no face to read (gdl.fonts.icon_face,
    gdl.sfnt.Advances.glyph_names)."""
    if font not in _GLYPHS:
        from .fonts import icon_face
        from .sfnt import Advances
        data = icon_face(font)[0]
        _GLYPHS[font] = Advances(data).glyph_names() if data else None
    return _GLYPHS[font]


def icon_codepoint(font, icon):
    """(codepoint, None), or (None, why): `icon` is a glyph's name in `font`, or
    its codepoint as U+E908 / uniE908 - the way into a face that names
    nothing, as Mach's Extron-Lift and Extron-Shockwave do. The face's own
    names come first: Extron GUIC Video Conference 1 names its glyph at U+F081
    'uni0081', and its names are what an icon sheet lists."""
    if not isinstance(icon, str):
        return None, f"icon {icon!r}: an icon is a glyph's name or its codepoint, as U+E908"
    names = glyph_names(font)
    if names and icon in names:
        return names[icon], None
    m = re.fullmatch(r'(?:[Uu]\+|uni)([0-9A-Fa-f]{4,6})', icon)
    if m:
        cp = int(m.group(1), 16)
        if cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
            return None, f'icon {icon!r}: U+{cp:04X} is no character, so no face maps a glyph there'
        return cp, None
    if names is None:
        return None, (f'icon {icon!r}: no {font} face here to read its glyph names from - '
                      f'neither recovered into gdl/fonts/ nor in a seed pulled from Git LFS; '
                      f'a codepoint, as U+E908, needs no names')
    if not names:
        return None, (f'icon {icon!r}: {font} names none of its glyphs - give the codepoint, '
                      f'as U+E900; python -m gdl.spec icons <family> <sheet.png> draws them')
    import difflib
    near = difflib.get_close_matches(icon, list(names), n=3, cutoff=0.6)
    return None, (f'icon {icon!r} is not a glyph of {font}'
                  + (f" - did you mean {', '.join(repr(n) for n in near)}?" if near else '')
                  + ' (python -m gdl.spec icons lists them)')


# How a button's image sits in it, as Extron's own image buttons all have it:
# ImageLayoutEnum Fill (fit, keeping the aspect) and AlignmentEnum
# MiddleCenter. The kit draws each icon, its selection line and its label room
# at the button's own aspect, so fitting it fills the button.
IMAGE_LAYOUT, IMAGE_ALIGN = 0, 3
# A page's background image, by ImageLayoutEnum: Fill (fit) as the Afterburn
# seeds lay theirs out, Stretch as the Mach seeds lay their 3:2 photo over a
# 16:10 page (every one of Mach 1035's pages).
BACKGROUND_LAYOUTS = {'fill': 0, 'stretch': 1}
# An `image` control's art, in its backgroundImageField, by the same enum:
# every PBImage in the Turbulence seeds lies one of these two ways - its
# header and footer bars Stretch, a source popup's device picture Fill - and
# Build's artwork of each is the file laid out so, not a pixel off
# (tests/test_verify_built.py, the 1035 seed's own). A button's image is
# always Fill (IMAGE_LAYOUT).
IMAGE_LAYOUTS = BACKGROUND_LAYOUTS
# The two per-button pointers into the state list, as backing fields.
# TLPDefaultStateID is 0 on every button in the corpus. TLPPressFeedbackStateID
# is the state shown while the button is held: On (1) on every Off/On
# buttons in the seeds and fixtures, the last state on Extron's own 4-state
# volume mute.
PRESS_FIELD = '<TLPPressFeedbackStateID>k__BackingField'
# Whether the panel shows a button's press state, its state feedback and its
# state captions at all. False on every button in the seeds and fixtures.
PRESS_FEEDBACK = {'<HidePressFeedback>k__BackingField': False,
                  '<HideVisualFeedback>k__BackingField': False,
                  '<HideTextFeedback>k__BackingField': False}
DEFAULT_FIELD = '<TLPDefaultStateID>k__BackingField'

# Orientation, as gdl/compose.py decodes it when clipping a level's value fill.
ORIENT = {'right': 0, 'left': 1, 'up': 2, 'down': 3}

def _level_rect(c):
    """A Level's box narrowed to its `track` across the value, centred.

    Build draws a Level over its whole box - unlike a slider it has no track
    width - and every Afterburn seed's Level is its rail: 15 px across, on the
    300M, 320 and 525 alike. Given its touch-sized box, the 525's volume built
    as a 66x45 block where the canvas drew a rail.
    """
    x, y, w, h = c['rect']
    t = int(c['track'])
    if c.get('orientation', 'up') in ('up', 'down'):
        return [x + (w - t) // 2, y, t, h] if t < w else list(c['rect'])
    return [x, y + (h - t) // 2, w, t] if t < h else list(c['rect'])


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
            # `thumb` is across the rail and `thumb_height` along it - square
            # unless the template's thumb is not: Shockwave's is 52 across and
            # 34 along. Build keeps width and height literal (the Zoom Rooms
            # seed's horizontal slider has a thumb 7 wide and 25 tall, and the
            # format probe's Shockwave sliders lying right and left built the
            # 34x52 thumbs this writes), so a slider lying down swaps them, as
            # the canvas draws it. The thumb's art goes into that box
            # stretched, unturned (tests/verify_built.py check_thumbs).
            across = c.get('thumb', 50)
            along = c.get('thumb_height', across)
            if c.get('orientation') in ('right', 'left'):
                across, along = along, across
            out['sliderThumbWidth'] = across
            out['sliderThumbHeight'] = along
    if kind == 'line':
        # Endpoints are an eight-position enum on the control's own rect, so a
        # diagonal is TopLeft -> BottomRight at whatever angle the rect gives.
        out['startPointField'] = LINE_POS.get(c.get('from', 'MiddleLeft'), 6)
        out['endPointField'] = LINE_POS.get(c.get('to', 'MiddleRight'), 2)
        out['thicknessField'] = c.get('thickness', 2)
    if kind == 'button':
        # Written, not inherited: a clone keeps its donor's, and a donor button
        # with either set would build a panel whose buttons never show their
        # press state - every button in the seeds and fixtures has both off,
        # but a client's project need not.
        out.update(PRESS_FEEDBACK)
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
# kits, from vendor/ (vendor/README.md) or the install - or, on a machine
# without GUI Designer, a copy of the install's Resources that
# GDL_EXTRON_RESOURCES names. A copy merged into vendor/ instead changes which
# file wins where both have one (vendor's Mach/Extracted against the kit's
# Mach/Buttons), and so the spec a translate writes.
RESOURCE_ROOTS = (
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'vendor', 'extron', 'Resources'),
    os.environ.get('GDL_EXTRON_RESOURCES')
    or r'C:\Users\Public\Documents\Extron\GUI Designer Templates\Resources',
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
    """'#RRGGBB', '#AARRGGBB' or a theme key -> the ARGB dict layout.json uses.

    `none` is transparent: how a design turns a state's fill or outline off.
    Leaving the key out keeps the button's own instead."""
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    if v == 'none':
        return dict(TRANSPARENT)
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


def _round_half_up(v):
    return math.floor(v + Fraction(1, 2))


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
    # Each cell's two edges, rounded, and its size what lies between them.
    # Rounding a cell's left and its width apart ran 800 across three into 267
    # wide from 0, 267 and 533 - the second a pixel into the third - and left
    # gaps a pixel either side of the one asked for. In exact arithmetic with
    # halves rounded up, a cell's right edge and the next one's left are a
    # whole gap apart, exactly.
    def edges(start, length, n, g):
        start, g = Fraction(start), Fraction(g)
        size = (Fraction(length) - g * (n - 1)) / n
        out = []
        for i in range(n):
            s = start + i * (size + g)
            out.append((_round_half_up(s), _round_half_up(s + size) - _round_half_up(s)))
        return out
    out = []
    for top, ch in edges(y, h, rows, gy):
        for left, cw in edges(x, w, cols, gap):
            out.append([left, top, cw, ch])
    return out


def stack(rect, count, gap=0, horizontal=False, pad=0):
    """A one-dimensional grid - a row or a column of equal cells."""
    return grid(rect, count if horizontal else 1, 1 if horizontal else count,
                gap=gap, pad=pad)


# The donor page the applier keeps whatever a spec says (Apply-GdlPlan.ps1):
# the Offline Page, popup 65535, which every seed and fixture has.
OFFLINE_PAGE_ID = 65535


def kept_names(pages, keep_donor_pages=False):
    """The donor's page and popup names that are still in the built panel, so
    a spec's may not take them - Build refuses a duplicate only once it has
    started. `pages` is gdl.project.Project.pages(). Every one, for a spec that
    keeps the donor's pages; otherwise the applier drops all it did not make
    but the Offline Page."""
    return {pg['name'] for pg in pages
            if pg['name'] and (keep_donor_pages or pg['id'] == OFFLINE_PAGE_ID)}


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
        self._overflow = []
        # What _icons could not draw, for check(), and each glyph it did draw -
        # (where, face, codepoint) - for check_donor() to find in the donor's face.
        self._icon_problems = []
        self._icon_glyphs = []
        # Image resources the spec brings with it: name -> file (resolve_image).
        # A page's `background_image` names one of these or one the donor
        # already defines.
        self.images = dict(spec.get('images') or {})
        self._build()

    # -- icons -------------------------------------------------------------
    def _icon_font(self):
        """(face, None) an `icon` is drawn in when its control names none - the
        theme's `icon_font`, else its family's (ICON_FONTS) - or (None, why)."""
        from .fonts import ICON_FONTS
        if self.theme.get('icon_font'):
            return self.theme['icon_font'], None
        family = str(self.spec.get('family') or '').lower()
        key = next((k for k in ICON_FONTS if k.lower() == family), None)
        if key and ICON_FONTS[key]:
            return ICON_FONTS[key], None
        if key:
            return None, (f'{key} has no icon font - its template draws nearly all its icons '
                          f'as images (docs/design-rules.md section 6): give it an "image", '
                          f'or name the "font" its icon is in')
        return None, ('an icon needs an icon font - the control\'s "font", the theme\'s '
                      '"icon_font", or the spec\'s "family"')

    def _icons(self, controls, where):
        """Each control that names an icon - its own or a state's - drawn as
        the glyph: `text` the glyph's character, `font` the icon font. Run on
        the laid-out controls, so an icon a grid gives every item is each
        item's own. What cannot be drawn is a check() problem."""
        out = []
        for c in controls:
            c = self._on_as_states(c)
            # Anything but a list is _state_rules' to report, not this to read.
            states = c['states'] if isinstance(c.get('states'), list) else []
            if 'icon' not in c and not any(isinstance(s, dict) and 'icon' in s for s in states):
                out.append(c)
                continue
            if 'icon' in c and not c.get('name'):
                # A name falls back to the text, which is about to be the glyph: a
                # private-use character a spreadsheet shows blank and a Windows
                # stdout redirected to a file cannot print.
                c = dict(c, name=str(c['icon']))
            label = f"{where} {c.get('name') or '?'}"
            kind = c.get('kind', 'panel')
            if kind not in ('button', 'label'):
                self._icon_problems.append(f'{label}: a {kind} takes no "icon" - it draws no '
                                           f'caption to set one in; a button or a label does')
                out.append(c)
                continue
            font, why = (c['font'], None) if c.get('font') else self._icon_font()
            if not font:
                self._icon_problems.append(f'{label}: {why}')
                out.append(c)
                continue
            c = dict(c, font=font)
            if 'icon' in c:
                if c.get('text'):
                    self._icon_problems.append(
                        f'{label}: has both "icon" and "text" - a caption is drawn in one face, '
                        f'so the icon replaces the words; put them on a label beside it')
                c['text'] = self._glyph(c['icon'], font, label)
            if states:
                c['states'] = [self._icon_state(s, c, font, label) for s in states]
            out.append(c)
        return out

    def _on_as_states(self, c):
        """A button's `on` that names an icon, as the Off and On states it is
        shorthand for (_feedback), so the icon is the On state's as a state's
        own would be. Left as `on`, the icon was dropped."""
        if c.get('kind') != 'button' or 'states' in c:
            return c
        on = c.get('on', self.theme.get('on'))
        if not (isinstance(on, dict) and 'icon' in on):
            return c
        c = {k: v for k, v in c.items() if k != 'on'}
        c['states'] = [{'name': 'Off'}, dict(on, name='On')]
        return c

    def _icon_state(self, s, c, font, label):
        name = s.get('name') if isinstance(s, dict) else s
        where = f"{label} state {name!r}"
        if isinstance(s, dict) and 'icon' in s:
            if s.get('text'):
                self._icon_problems.append(
                    f'{where}: has both "icon" and "text" - the icon replaces the words')
            return dict(s, text=self._glyph(s['icon'], font, where))
        # Any icon on the button sets its face to the icon font, so a state's
        # words - its own, or the button's it shows - draw in a face with none.
        if isinstance(s, dict) and 'text' in s:
            if s['text']:
                self._icon_problems.append(
                    f'{where}: has "text" on an icon - it would draw in {font}, which has '
                    f'no letters; give the state an "icon"')
        elif 'icon' not in c and c.get('text'):
            self._icon_problems.append(
                f"{where}: shows the button's \"text\" {c['text']!r} in {font}, which has no "
                f'letters - give the state an "icon", or put the words on a label beside it')
        return s

    def _glyph(self, icon, font, label):
        cp, why = icon_codepoint(font, icon)
        if why:
            self._icon_problems.append(f'{label}: {why}')
            return ''
        self._icon_glyphs.append((label, font, cp))
        return chr(cp)

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
                label = spread.get('name') or (items[0].get('text') if items else '?')
                if 'grid' in item:
                    # Given rows and no cols, as many columns as the items
                    # need. One column per item was the default whatever the
                    # rows, which laid a three-row grid out as a single row.
                    rows = spread.get('rows', 1)
                    cols = spread['cols'] if 'cols' in spread else (
                        -(-len(items) // rows) if isinstance(rows, int) and rows >= 1
                        else len(items))
                    cells = grid(rect, cols, rows, spread.get('gap', 0),
                                 spread.get('gap_y'), spread.get('pad', 0))
                else:
                    cells = stack(rect, spread.get('count', len(items)),
                                  spread.get('gap', 0), spread.get('horizontal', False),
                                  spread.get('pad', 0))
                if len(items) > len(cells):
                    # One item to a cell, and zip() below stops at the last
                    # cell: the rest were dropped without a word.
                    n = len(cells)
                    self._overflow.append(
                        f"{'grid' if 'grid' in item else 'stack'} {str(label)!r}: "
                        f"{len(items)} items for {n} cell{'' if n == 1 else 's'} - "
                        f"the last {len(items) - n} would not be laid out")
                shared = {k: v for k, v in spread.items()
                          if k not in ('rect', 'cols', 'rows', 'gap', 'gap_y',
                                       'pad', 'items', 'count', 'horizontal')}
                # p.58 caps a control GROUP at nine buttons. "Group" is not a
                # spec concept, so treat one layout directive as one group -
                # which is what a designer means by it.
                kinds = [sub.get('kind', shared.get('kind')) for sub in items]
                nbtn = sum(1 for k in kinds if k == 'button')
                if nbtn:
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
                if item.get('kind') == 'level' and item.get('track') and item.get('rect'):
                    item = dict(item, rect=_level_rect(item))
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
        under one ID is Extron's own practice (the client's 81/82).
        """
        nxt = base
        for c in controls:
            # A pinned 0 is pinned - GUI Designer's 'no ID', which check()
            # names - not a control with no `id`, to be given another quietly.
            if c.get('id') is not None:
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
            self._groups, self._overflow = {}, []
            flat = self._controls(pu.get('controls') or [], [])
            flat_popups.append((pu, self._icons(flat, f"popup {pu.get('name')!r}"),
                                dict(self._groups), list(self._overflow)))
        flat_pages = []
        for pg in self.spec.get('pages') or []:
            self._groups, self._overflow = {}, []
            flat = self._controls(pg.get('controls') or [], [])
            flat_pages.append((pg, self._icons(flat, f"page {pg.get('name')!r}"),
                               dict(self._groups), list(self._overflow)))
        taken = {c['id'] for _, cs, _, _ in flat_pages + flat_popups for c in cs
                 if isinstance(c.get('id'), int)}
        # IDs an earlier delivery gave controls that are gone (translate
        # --previous writes them): a program still addressing one must reach
        # nothing, so no unpinned control is numbered into one.
        taken |= {r['id'] for r in self.spec.get('_retired') or [] if isinstance(r, dict)}
        # Which IDs the spec gave, so check() can tell a pinned one from one
        # the band ran past 65535 with.
        self._pinned = {id(c) for _, cs, _, _ in flat_pages + flat_popups for c in cs
                        if c.get('id') is not None}

        for i, (pg, controls, groups, overflow) in enumerate(flat_pages):
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
                # Drawn over the background color, fitted to the page (Fill,
                # as the Afterburn seeds lay theirs out - the applier sets it). One
                # image on every page is the themes' own rule, so the theme can
                # name it once.
                'background_image': pg.get('background_image',
                                           self.theme.get('background_image')),
                # Fill (fit) as Afterburn's pages lay theirs out, or stretch
                # as Mach's do its 3:2 photo over a 16:10 page.
                'background_layout': pg.get('background_layout',
                                            self.theme.get('background_layout')),
                'controls': controls,
                'group_sizes': groups,
                'overflow': overflow,
            })

        self.popups = []
        for i, (pu, controls, groups, overflow) in enumerate(flat_popups):
            # A band per popup. The default used to be 9000 + i, so popup i's
            # band began inside popup i-1's and two unnumbered popups shared IDs.
            number = pu.get('number', 9000 + 100 * i)
            self._allocate(controls, pu.get('id_base') or number + 1, taken)
            modal = bool(pu.get('modal'))
            size = pu.get('size')
            if modal and not size:
                # Every modal popup in the corpus is full-canvas - 7 in the client
                # project, 19 in the Afterburn seed, 13 in Shockwave - and Build
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
                # A standard popup's own photo, as Shockwave's and Turbulence's
                # hubs draw every popup on the page's (seeds/Turbulence 525.gdl:
                # all 12 on bkgd_swoop_plain.png, stretched to the popup).
                'background_image': pu.get('background_image'),
                'background_layout': pu.get('background_layout'),
                'controls': controls,
                'group_sizes': groups,
                'overflow': overflow,
            })

        # The page the panel boots into. Without it a generated panel opens on
        # the DONOR's start page - a built panel from the client donor
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
                             'PointSize': c.get('size') or self.theme.get('size') or DEFAULT_POINT_SIZE,
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
                        # An image control's art as it lies: a button's is fitted.
                        'image_layout': (IMAGE_LAYOUTS.get(c.get('layout') or 'fill', 0)
                                         if c.get('kind') == 'image' else IMAGE_LAYOUT),
                    }
            image = (resolve_image(self.images.get(pg['background_image']))
                     if pg.get('background_image') else None)
            pages.append({
                'ID': pg['number'], 'Name': pg['name'], 'TLPImageID': -1,
                'Modal': pg['modal'], 'BackgroundFillColor': pg['background'],
                # Only when the spec brings the file: an image the donor
                # carries is not on this machine to draw.
                '_background_image': image,
                '_background_layout': BACKGROUND_LAYOUTS.get(pg.get('background_layout') or 'fill', 0),
                'Controls': controls,
            })
        return {'Pages': pages, 'PopupPages': []}, fills

    def render(self, page=0):
        """Composite one page to a PIL image. Needs Pillow."""
        from .compose import as_the_panel, render_page
        model, fills = self.layout()
        # As the panel shows it: a translucent fill blends. No donor's faces -
        # a spec alone cannot know which build the panel will embed.
        with as_the_panel():
            return render_page(model['Pages'][page], {}, self.size, fills=fills)

    def plan(self, swaps=None, fonts=None, art=None):
        """A build plan: the clone-and-set operations that would write this spec.

        `swaps` maps a border resource the spec names to the one the donor
        builds it as (border_swaps, `plan --donor`); every op's border, and
        every state's, is written through it. `fonts` lists the faces to append
        to the donor first - {family, style, file, embedded, source, size,
        default, author, carrier}, the file written beside the plan and
        `carrier` the seed it is copied from. `art` is check_donor's: where the
        donor's level is drawn from images, every level keeps them (`keep_art`)
        and is planned no bar color.

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
                'background_layout': BACKGROUND_LAYOUTS.get(pg.get('background_layout') or 'fill', 0),
                'clear_controls': True,
                # Same helper popups use. Building these two separately is what
                # dropped 'group' from every page op and left popup references
                # bound to the donor's group.
                'controls': [self._op_for(c, i) for i, c in enumerate(pg['controls'])],
            })

        plan = {
            'generated_by': 'gdl.spec',
            # By NAME: the applier resolves it to the id it gives that page,
            # which only exists once the donor has decided what is free.
            'default_page': self.start_page,
            # The panel is these pages and popups: the applier drops the
            # donor's own once it has cloned what it needs from them. A seed
            # left in shipped its whole demo, unreachable, sharing IDs with the
            # spec's controls.
            'keep_donor_pages': bool(self.spec.get('keep_donor_pages')),
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
            # Faces the donor lacks, appended before any control is cloned so
            # Set-GdlFont finds them (Add-GdlFontResource).
            'fonts': list(fonts or []),
        }
        if swaps:
            for item in plan['pages'] + plan['popups']:
                for op in item['controls']:
                    if op.get('border') in swaps:
                        op['border'] = swaps[op['border']]
                    for st in op.get('states') or []:
                        if st.get('border') in swaps:
                            st['border'] = swaps[st['border']]
        if (art or {}).get('level'):
            # The donor's level fills from an image (check_donor): a bar color
            # never shows, and its empty track, its background image, is kept.
            for item in plan['pages'] + plan['popups']:
                for op in item['controls']:
                    if op.get('donor_type') == 'PBLevel':
                        op['gauge_fill'] = None
                        op['keep_art'] = True
        return plan

    @staticmethod
    def _image_rules(c, where):
        """An image's own keys: its art or a ground to draw, and a layout
        the panel has a word for. `layout` is an image's alone - a button lays
        its image out Fill whatever it says."""
        out = []
        if c.get('kind') != 'image':
            if 'layout' in c:
                out.append(f"{where}: 'layout' is an image's - a {c.get('kind', 'panel')} lays its "
                           'image out Fill, and would ignore it')
            return out
        if not c.get('image') and not c.get('fill'):
            out.append(f'{where}: an image with no `image` and no `fill` draws nothing')
        if c.get('layout') is not None and c['layout'] not in IMAGE_LAYOUTS:
            out.append(f"{where}: layout {c['layout']!r} is not one an image takes - "
                       f"{' or '.join(map(repr, IMAGE_LAYOUTS))}")
        return out

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
        out = list(self._icon_problems)
        if self.model and self.spec.get('size') and tuple(self.spec['size']) not in sizes(self.model):
            out.append(f"size {'x'.join(map(str, self.spec['size']))} is not a canvas the {self.model} "
                       f"has - it is {' or '.join('%dx%d' % s for s in sizes(self.model))}")
        for item in self.pages + self.popups:
            for c in item['controls']:
                odd = sorted(k for k in c if k not in CONTROL_KEYS and not k.startswith('_'))
                if odd:
                    out.append(f"{item['name']!r} {c.get('name') or c.get('kind')}: "
                               f"{', '.join(repr(k) for k in odd)} is not a key a control takes - "
                               'a typo here is silently ignored')
                on = c.get('on')
                if isinstance(on, dict):
                    odd = _odd_keys(on, STATE_KEYS - {'name'})
                    if odd:
                        out.append(f"{item['name']!r} {c.get('name') or c.get('kind')}: `on` "
                                   f"{', '.join(map(repr, odd))} is not a key a state takes - "
                                   f"it takes {', '.join(sorted(STATE_KEYS - {'name'}))}")
                out += self._value_rules(c, f"{item['name']!r} {c.get('name') or c.get('kind')}")
        out += self._number_rules()
        out += self._key_rules()
        for name, f in self.images.items():
            if not resolve_image(f):
                out.append(f'image {name!r}: {f!r} is not a file here or under '
                           f"{' or '.join(RESOURCE_ROOTS)}")
        for item in self.pages + self.popups:
            for c in item['controls']:
                out += self._image_rules(c, f"{item['name']!r} {c.get('name') or c.get('kind')}")
        for pu in self.popups:
            if pu['modal'] and pu.get('background_image'):
                out.append(f"popup {pu['name']!r} is a modal, and Build draws a modal's page at the "
                           f'modal\'s own transparency ({MODAL_TRANSPARENCY:g}%) over the page '
                           'beneath - its background_image would be a dimmed photo over it, which '
                           'no canvas draws. Put a picture on an image control in it')
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
            inside = mirrors(pg['controls'])
            for c in pg['controls']:
                x, y, w, h = (int(v) for v in c['rect'])
                where = f"page {pg['number']} {c.get('name') or c.get('text') or '?'}"
                if w <= 0 or h <= 0:
                    out.append(f'{where}: non-positive size {w}x{h}')
                if x < 0 or y < 0 or x + w > self.size[0] or y + h > self.size[1]:
                    out.append(f'{where}: rect {[x, y, w, h]} leaves the {self.size} canvas')
                # A mirror inside its control shares its ID on purpose (mirrors).
                if id(c) not in inside:
                    if c['id'] in seen:
                        out.append(f"{where}: id {c['id']} already used by {seen[c['id']]}")
                    seen[c['id']] = where
                b = c.get('border')
                if b and b not in BORDERS and b not in BORDER_GEOMETRY:
                    out.append(f'{where}: unknown border resource {b!r} - a generator may '
                               f'only reference resources the project already carries')
            out += [f"page {pg['number']} {o}" for o in pg.get('overflow') or []]
            out += self._house_rules(pg)
        for pu in self.popups:
            out += [f"popup {pu['name']!r} {o}" for o in pu.get('overflow') or []]
            out += self._house_rules(pu, f"popup {pu['name']!r}")
            seen, inside = {}, mirrors(pu['controls'])
            for c in pu['controls']:
                where = f"popup {pu['name']!r} {c.get('name') or c.get('text') or '?'}"
                if id(c) in inside:
                    continue
                if c['id'] in seen:
                    out.append(f"{where}: id {c['id']} already used by {seen[c['id']]}")
                seen[c['id']] = where
        out += self._popup_rules()
        out += self._name_rules()
        out += self._state_rules()
        out += self._slider_rules()
        for pg in self.pages:
            lay = pg.get('background_layout')
            if lay is not None and lay not in BACKGROUND_LAYOUTS:
                out.append(f"page {pg['name']!r}: background_layout {lay!r} is not one the "
                           f"toolkit draws and checks - {' or '.join(BACKGROUND_LAYOUTS)}")
        if self.start_page is not None and \
                self.start_page not in {pg['name'] for pg in self.pages}:
            out.append(f'start_page {self.start_page!r} is not a page in this spec - the '
                       f'panel boots into it, so it must be one of the pages authored '
                       f'here (a popup cannot be a start page)')
        # A color counts once whatever its transparency: Mach's own rule is
        # "same hue, move the alpha", and its white at 20%, 47% and 100% is one
        # color on the panel. Counting each alpha put Extron's own Mach look
        # over six. The owner's reading of p.49, not Extron's wording.
        drawn = {tuple(kv for kv in c if kv[0] != 'A') for c in self.palette()}
        # The theme's own template chrome is exempt (the owner's call,
        # 2026-10-22): Extron's own Mach working page draws more than six -
        # shade, its pressed tint, white, black, the mute yellow, the
        # power-down red, the window grey - and a panel that speaks the
        # template's language draws them too. The cap holds for the colors a
        # designer adds. The translator names the template's in
        # `_template_colors`, from the theme's measured palette.
        own = set()
        for v in self.spec.get('_template_colors') or ():
            c = color(v, self.theme)
            if c:
                own.add(tuple(kv for kv in sorted(c.items()) if kv[0] != 'A'))
        n = len(drawn - own)
        if n > MAX_COLORS_PER_PROJECT:
            out.append(f'project uses {n} distinct colors'
                       + (' besides the template\'s own' if own else '')
                       + f', above the {MAX_COLORS_PER_PROJECT}-color maximum '
                       f'(GUI Design Standards p.49)')
        return out

    def _value_rules(self, c, where):
        """A control's kind and align must be ones the plan knows, and its ID a
        UInt16 a program can address.

        The plan builds an unknown kind as a PBShape - a mistyped button is a
        rectangle that does nothing, and verify_built agrees with the plan that
        says so - and an unknown align as centre. userIdField is a UInt16: the
        applier's write of anything else fails, warned on Windows only, and the
        clone keeps its donor's ID - another control's address.
        """
        out = []
        kind = c.get('kind', 'panel')
        if not isinstance(kind, str) or kind not in KIND_TYPE:
            out.append(f"{where}: kind {kind!r} is not one the plan builds - "
                       f"{', '.join(map(repr, KIND_TYPE))} - and would build as an inert shape")
        align = c.get('align')
        if align is not None and (not isinstance(align, str) or align not in ALIGN):
            out.append(f"{where}: align {align!r} is not one of "
                       f"{', '.join(repr(a) for a in ALIGN if a != 'centre')} - it would build "
                       f'centred')
        v = c.get('id')
        if not is_uint16(v) or v == 0:
            why = ("0 is GUI Designer's 'no ID' - leave `id` out and one is allocated"
                   if v == 0 and not isinstance(v, bool) else
                   'it was allocated from its page\'s number or id_base - lower that'
                   if id(c) not in self._pinned else
                   "userIdField is a UInt16, and a write of anything else leaves the clone "
                   "the donor's ID")
            out.append(f'{where}: id {v!r} is not a whole number from 1 to 65535 - {why}')
        return out

    def _number_rules(self):
        """A page's and popup's number is written through a [uint16] cast,
        which stops the applier midway on anything else, and the ID band its
        controls are allocated from starts at it."""
        out = []
        for kind, items in (('page', self.pages), ('popup', self.popups)):
            for it in items:
                if not is_uint16(it['number']):
                    out.append(f"{kind} {it['name']!r}: number {it['number']!r} is not a whole "
                               f'number from 0 to 65535 - the applier writes it as a UInt16')
        return out

    def _key_rules(self):
        """Every key above a control's that nothing reads (SPEC_KEYS and the
        rest), named. A control's own are held to CONTROL_KEYS in check()."""
        out = []
        say = ' is not a key {} takes - a typo here is silently ignored'.format
        odd = _odd_keys(self.spec, SPEC_KEYS)
        if odd:
            out.append(', '.join(map(repr, odd)) + say('a spec'))
        for k, v in (self.spec.get('theme') or {}).items():
            if k in THEME_SETTINGS or str(k).startswith('_'):
                continue
            if not (isinstance(v, str) and HEX.match(v)):
                out.append(f'theme {k!r} is not a key a theme takes: {v!r} is neither a color '
                           f"nor one of its settings ({', '.join(sorted(THEME_SETTINGS))}) - a "
                           f'typo here is silently ignored')
        for kind, keys, items in (('page', PAGE_KEYS, self.spec.get('pages') or []),
                                  ('popup', POPUP_KEYS, self.spec.get('popups') or [])):
            for i, it in enumerate(items):
                if not isinstance(it, dict):
                    continue
                where = f"{kind} {it.get('name') or i!r}"
                odd = _odd_keys(it, keys)
                if odd:
                    out.append(f"{where}: {', '.join(map(repr, odd))}" + say(f'a {kind}')
                               + (" - a modal is a popup: put it in `popups` with modal true"
                                  if kind == 'page' and 'modal' in odd else ''))
                out += self._directive_keys(it.get('controls') or [], where)
        return out

    def _directive_keys(self, controls, where):
        """A grid or stack is an object holding one: anything beside it is
        dropped, and its own keys are LAYOUT_KEYS or shared with its items."""
        out = []
        for c in controls:
            if not isinstance(c, dict) or not ('grid' in c or 'stack' in c):
                continue
            which = 'grid' if 'grid' in c else 'stack'
            odd = _odd_keys(c, {which})
            if odd:
                out.append(f"{where}: {', '.join(map(repr, odd))} is not a key beside a {which} "
                           f'- it is dropped; it goes inside the {which}, or on its items')
            spread = c.get(which)
            if isinstance(spread, dict):
                out += self._directive_keys(spread.get('items') or [], where)
        return out

    def _house_rules(self, pg, label=None):
        """Extron's own numeric rules. See docs/design-rules.md for provenance.

        Deliberately separate from the structural checks above: these are
        Extron's design standards, not correctness. A spec that trips one of
        these will still build - it just will not meet the standard.
        """
        out = []
        label = label or f"page {pg['number']}"
        target, spacing = touch_minimums(self.model or self.size)
        # The type floor, ours on top of Extron's 14 pt (docs/design-rules.md
        # section 1): only where the model is named - by resolution alone the
        # densest panel's DPI would hold a 1035 to an 835's 18 pt.
        # A measurement spec - the type probe draws 14 pt on every panel on
        # purpose - turns it off: `"type_floor": "off"`.
        floor = type_floor(self.model) if self.model and self.spec.get('type_floor') != 'off' else None
        if target is None and label.startswith('page'):
            out.append(f"page {pg['number']}: no touch minimum for "
                       f"{self.model or '%dx%d' % tuple(self.size)} - name the panel's "
                       f"model so 9mm can be converted (GUI Design Standards p.55)")
        inside = mirrors(pg['controls'])
        for c in pg['controls']:
            x, y, w, h = (int(v) for v in c['rect'])
            where = f"{label} {c.get('name') or c.get('text') or '?'}"
            # Only interactive controls have a touch target to meet - a mirror
            # inside one is pressed as it (mirrors).
            if target and c.get('kind') in TOUCHABLE and id(c) not in inside and (w < target or h < target):
                out.append(f'{where}: {w}x{h} is below the {target}x{target} px touch '
                           f'target for a {self.size[0]}x{self.size[1]} panel '
                           f'(9mm, GUI Design Standards p.55)')
            # A control with no words - a key drawn in its fill, a derived Back
            # drawn as art - has no type to hold; read at the size it builds,
            # it would be named under every floor above 14.
            states = c.get('states')
            looks = [c, c.get('on')] + (states if isinstance(states, list) else [])
            if c.get('kind') != 'datetime' and not any(
                    isinstance(s, dict) and (s.get('text') or s.get('icon')) for s in looks):
                continue
            given = c.get('size') or self.theme.get('size')
            size = given or DEFAULT_POINT_SIZE
            said = f'{size:g}pt' + ('' if given else ', the size a control with none builds at,')
            if c.get('kind') in ('button', 'label') and size < MIN_BODY_POINT_SIZE:
                out.append(f'{where}: {said} is below the {MIN_BODY_POINT_SIZE}pt '
                           f'body-text minimum (p.65)')
            elif c.get('kind') in ('button', 'label', 'datetime') and floor and size < floor:
                out.append(f'{where}: {said} is under the {floor}pt type floor for a {self.model} - '
                           f'14 pt as it reads on a TLP Pro 1025/1035 (docs/design-rules.md section 1)')

        # p.58: no more than nine buttons in a control group. "Group" is not a
        # spec concept, so approximate it by the layout directive that produced
        # them - which is exactly what a designer means by a group.
        for name, n in (pg.get('group_sizes') or {}).items():
            if n > MAX_BUTTONS_PER_GROUP:
                out.append(f"{label} group {name!r}: {n} buttons exceeds the "
                           f'{MAX_BUTTONS_PER_GROUP}-per-group maximum (p.58)')

        # Adjacent-button spacing, p.56: at least 5-10px for buttons of 72px or
        # less, and 2mm between touchable targets generally.
        # Between every touch target - a slider's too. Two segments of one
        # segmented control (the same `joined`) touch on purpose.
        if spacing:
            btns = [c for c in pg['controls'] if c.get('kind') in TOUCHABLE and id(c) not in inside]
            for i, a in enumerate(btns):
                ax, ay, aw, ah = (int(v) for v in a['rect'])
                for b2 in btns[i + 1:]:
                    if a.get('joined') and a.get('joined') == b2.get('joined'):
                        continue
                    bx, by, bw, bh = (int(v) for v in b2['rect'])
                    gap_x = max(bx - (ax + aw), ax - (bx + bw))
                    gap_y = max(by - (ay + ah), ay - (by + bh))
                    pair = (f"{label} {a.get('name') or a.get('text') or '?'} / "
                            f"{b2.get('name') or b2.get('text') or '?'}")
                    # Neighbours: overlapping on one axis and separated on the
                    # other - and two that overlap outright, which a layout that
                    # grew one past the other makes.
                    if gap_x < 0 and gap_y < 0:
                        out.append(f'{pair}: overlap - two touch targets cannot share pixels')
                    elif gap_x < 0 and 0 <= gap_y < spacing:
                        out.append(f'{pair}: {gap_y}px vertical gap is '
                                   f'below the {spacing}px minimum (2mm, p.56)')
                    elif gap_y < 0 and 0 <= gap_x < spacing:
                        out.append(f'{pair}: {gap_x}px horizontal gap is '
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
        guess: it is nearly every button in Extron's own templates, and most
        of them draw the two differently (docs/gdl-format.md section 7).
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
                'image': self._image_op(None if s.get('image') == 'none' else
                                        s['image'] if 'image' in s else c.get('image')),
            })
        return out

    def _press(self, c, states):
        """The index of the state shown while the button is held.

        Set on every button that plans its states rather than inherited: a
        clone keeps the donor's pointer, which may name a state the clone no
        longer has. Off/On buttons show On (1) - every one in the seeds and
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
        verify_built's image check. So is a label: Turbulence 320's donor
        label is opaque black, and a region page's empty state built on
        black bands over the photo the preview drew through it.
        """
        fill = color(c.get('fill'), self.theme) if c.get('fill') != 'none' else None
        stroke = color(c.get('stroke'), self.theme) or dict(TRANSPARENT)
        text_color = color(c.get('color') or self.theme.get('text') or '#FFFFFF',
                           self.theme)
        border = c.get('border')
        border = BORDERS.get(border, border)
        if border is None and fill is not None:
            border = BORDERS['rounded']
        if fill is None and c.get('kind') in ('button', 'label'):
            fill = dict(TRANSPARENT)
        if fill is None and c.get('kind', 'panel') in ('panel', 'shape', 'line', 'datetime'):
            # And a panel, a line or a clock, with no border either: the first
            # PBShape a clone starts from is an opaque slab in most donors -
            # #37394E bordered in Afterburn 1535, #000000 in the 1230W, the
            # client's #242634 - and a line's is #BABCCE, so a see-through
            # panel in the preview built as the donor's.
            fill = dict(TRANSPARENT)
            if border is None:
                # A stroke is the border resource's outline: with none named,
                # a visible stroke would be planned and previewed, and lost.
                border = BORDERS['rounded'] if stroke['A'] else ''
        if c.get('kind') == 'image':
            # Its art is the picture: a clone of the Turbulence seeds' first
            # PBImage, a side bar black at 85% transparency the applier makes
            # opaque, built the art over an opaque black box. Every PBImage in
            # the seeds has no border resource.
            if fill is None:
                fill = dict(TRANSPARENT)
            if border is None:
                border = ''
        if c.get('kind') == 'slider' and c.get('track_image'):
            # Build draws a slider's bordered fill IN PLACE of its rail art: a
            # Shockwave slider with the profile's rounded border and black fill
            # built a black block, its art on the model and nowhere else. The
            # seed's own image-railed sliders author no border and Transparent.
            fill, stroke, border = dict(TRANSPARENT), dict(TRANSPARENT), ''
        return fill, stroke, text_color, border

    def _slider_rules(self):
        """A slider or level lies one of four ways, and a rail is two images.

        The canvas draws anything but up or down across the page while
        _type_fields falls back to up, so an orientation outside ORIENT was
        approved lying down and built standing up. And the applier writes only
        the rail images it is given, so a rail named by one kept its donor's
        other - every theme seed's slider has fill art.
        """
        out = []
        for kind, items in (('page', self.pages), ('popup', self.popups)):
            for pg in items:
                for c in pg['controls']:
                    if c.get('kind') not in ('slider', 'level'):
                        continue
                    where = f"{kind} {pg['name']!r} {c.get('name') or c.get('text') or '?'}"
                    o = c.get('orientation', 'up')
                    if o not in ORIENT:
                        out.append(f"{where}: orientation {o!r} is not one of "
                                   f"{', '.join(ORIENT)} - the canvas draws it across "
                                   f'and the build stands it up')
                    if c.get('kind') == 'slider' and \
                            bool(c.get('track_image')) != bool(c.get('fill_image')):
                        out.append(f'{where}: a rail takes both track_image and fill_image '
                                   f"- with one, the clone keeps its donor's other")
        return out

    def stroke_rules(self, geometry, source, swaps=None):
        """A stroke must be on a border that draws one - in the project it is
        built in. `geometry` is that project's border_geometry(), `swaps` the
        borders it builds as its nearest (border_swaps).

        A built-in border's thickness is the project's own: Mach's 1035 seed
        defines 2D Rounded Rectangle at thickness 0 (and radius 1), so a display
        button on it built its Warming Up - an accent outline on Off's fill -
        as Off's very artwork, and its Cooling Down's white outline was not
        drawn either. Afterburn's and Turbulence's define it at 3, and draw it.
        """
        out = []
        swaps = swaps or {}
        for kind, items in (('page', self.pages), ('popup', self.popups)):
            for pg in items:
                for c in pg['controls']:
                    where = f"{kind} {pg['name']!r} {c.get('name') or c.get('text') or '?'}"
                    fill, stroke, text_color, border = self._base_look(c)
                    looks = (self._states_for(c, fill, stroke, text_color, border)
                             if c.get('kind') == 'button' else None) or \
                        [{'name': None, 'stroke': _argb(stroke), 'border': border}]
                    for s in looks:
                        # A null stroke is the spec's own problem (_states_of).
                        if not (s['stroke'] or 0) >> 24 & 0xFF:
                            continue
                        built = swaps.get(s['border'], s['border'])
                        g = geometry.get(built)
                        if g is None or g.get('thickness'):
                            continue
                        who = f"its {s['name']!r} state's" if s['name'] else 'its'
                        out.append(f"{where}: {who} stroke is not drawn - {source} defines "
                                   f"{built!r} with no thickness. Give it a border that draws a "
                                   f"stroke, or tell it apart by its fill")
        return out

    def _state_rules(self):
        """A button's states must be ones a program can tell apart."""
        out = []
        for kind, items in (('page', self.pages), ('popup', self.popups)):
            for pg in items:
                inside = mirrors(pg['controls'])
                for c in pg['controls']:
                    out += self._states_of(c, f"{kind} {pg['name']!r} "
                                              f"{c.get('name') or c.get('text') or '?'}",
                                           mirror=id(c) in inside)
        return out

    def _states_of(self, c, where, mirror=False):
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
        # `on` and theme.on make states too, and can make two alike. A mirror
        # inside its control (mirrors) may: the control shows the state.
        if not out and not mirror and self._feedback(c):
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
            # The panel boots into state 0 and shows the press state while
            # held: naming state 0 on a button with others shows no press.
            elif len(specs) > 1 and names.index(c['press']) == 0:
                out.append(f"{where}: press {c['press']!r} is the state the button rests in, "
                           f'so holding it would show nothing - name another state, or leave '
                           f'`press` out for the second')
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
                # errors. The client donor hid it: its first is grouped.
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
                     'size': c.get('size') or self.theme.get('size') or DEFAULT_POINT_SIZE,
                     'bold': bool(c.get('bold')), 'italic': bool(c.get('italic'))},
            # Only meaningful on a popup reference; the applier ignores it
            # elsewhere.
            'group': c.get('group'),
            # A kit image on every state, or none: a clone's donor icon is
            # cleared either way. An image control's art, laid out as it says;
            # a button's is always fitted.
            'image': self._image_op(c.get('image')),
            'image_layout': (IMAGE_LAYOUTS.get(c.get('layout') or 'fill', 0) if kind == 'image'
                             else IMAGE_LAYOUT),
            'image_align': IMAGE_ALIGN,
            # A slider's thumb, where the template draws it from its kit
            # (Afterburn: sliderThumbImageField, in the secondary accent).
            'thumb_image': self._image_op(c.get('thumb_image')) if kind == 'slider' else None,
            # And its rail, where that is art too (Shockwave, Turbulence): the
            # track drawn when empty (backgroundImageField) and the fill when
            # full (sliderFillImageField). A clone's never survived the applier.
            'track_image': self._image_op(c.get('track_image')) if kind == 'slider' else None,
            'fill_image': self._image_op(c.get('fill_image')) if kind == 'slider' else None,
            # A level's filled part (gaugeFillColorField). A clone keeps its
            # donor's: the 525's built in the seed's scheme-1 #626ACF where the
            # grape theme's accent is gold.
            'gauge_fill': _argb(color(c.get('bar'), self.theme)) if kind == 'level' and c.get('bar') else None,
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
        if kind == 'button' and c.get('flatten'):
            # Build bakes the caption into the artwork - GUI Designer's own
            # rasterizer for this platform. Only tests/type_probe.py wants it;
            # everywhere else a baked caption is the flattenText trap.
            op['flatten'] = True
        return op

    def _popup_ops(self):
        return [{
            'op': 'clone-popup',
            'number': pu['number'],
            'name': pu['name'],
            'group': pu['group'],
            'modal': pu['modal'],
            # A modal's scrim: the applier writes it, and verify_built reads
            # it back off the modal's artwork (MODAL_TRANSPARENCY).
            'transparency': MODAL_TRANSPARENCY if pu['modal'] else None,
            'background': _argb(pu['background']),
            # The applier MUST set this. A cloned popup keeps the donor's size,
            # and GUI Designer relocates any control that falls outside the page
            # to 0,0 - silently, at build time. The first popup build lost the
            # last button of every grid that way: the spec said 984 wide, the
            # donor popup was 915, and everything past x=915 stacked up at the
            # origin while the file still built with 0 errors.
            'size': list(pu['size']) if pu['size'] else None,
            # The applier clears the donor's and sets this one, as a page's.
            'background_image': self._image_op(pu.get('background_image')),
            'background_layout': BACKGROUND_LAYOUTS.get(pu.get('background_layout') or 'fill', 0),
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
                # The format also lets a reference name one popup by its ID -
                # nine seeds show an ungrouped Volume Level so - but the
                # applier binds a reference to a group, and only to one.
                out.append(f"popup {pu['name']!r} is neither modal nor in a group, so no "
                           f'reference a spec makes can show it - a spec shows a standard '
                           f'popup through a reference bound to its group')
            if not pu['modal'] and not pu['size']:
                # A modal is given the canvas; a standard popup is given
                # nothing, and the applier keeps the donor popup's size - so
                # the fit check above and the reference check below, which
                # need one, skipped it, and a control past the donor's edge
                # built at 0,0.
                seen = sorted({(r[2], r[3]) for r in refs.get(pu['group'], [])})
                out.append(f"popup {pu['name']!r} has no size - its canvas is its own, and "
                           f"the applier would keep the donor popup's. Give it its "
                           f"reference's" + (f": {' or '.join('%dx%d' % s for s in seen)}"
                                             if seen else ''))
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

    def check_donor(self, path, swaps=None, fonts=None, art=None):
        """Can this donor supply every control type, and do any names collide?

        `swaps`, a dict if one is given, is filled with each border the donor
        lacks and builds as its own nearest instead (border_swaps), `fonts`
        with each family it lacks and a seed carries, to append
        (gdl.fonts.find_face) - what `donors` says aloud and `plan --donor`
        writes - and `art` with the images a level it clones is drawn from,
        which `plan --donor` plans by (keep_art).

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

        have = set()
        for pg in proj.pages():
            for c in pg['controls']:
                have.add(c['type'])
        out += [f'donor {path} has no {t} to clone - that control type cannot '
                f'be authored from it' for t in sorted(self.needs() - have)]

        # Popups clone from their own kind (Apply-GdlPlan.ps1): a seed with
        # modals only - every 320 seed - cannot supply a standard popup, and
        # one with none but Build's own full-canvas reference (id 65535) no
        # modal. Missed here it stops at the apply step, a Windows round trip on.
        have_std = any(pg['kind'] == 'popup' and not pg['modal'] for pg in proj.pages())
        have_modal = any(pg['kind'] == 'popup' and pg['modal'] and pg['id'] != 65535
                         for pg in proj.pages())
        for modal, have, what in ((False, have_std, 'standard'), (True, have_modal, 'modal')):
            names = [pu['name'] for pu in self.popups if bool(pu['modal']) == modal]
            if names and not have:
                out.append(f"donor {path} has no {what} popup to clone, and the spec has "
                           f"{'one' if len(names) == 1 else len(names)}: {', '.join(map(repr, names))} - "
                           + ('make it a modal, or a page, or build from a seed that has a standard popup'
                              if not modal else 'build from a seed that has a modal popup'))

        # A group is registered by cloning one of the project's own (Register-
        # GdlPopupGroup), so a grouped standard popup needs a donor that has
        # one: the 320 and 300M seeds and one client fixture have none, and it
        # stopped at the apply step.
        grouped = [pu for pu in self.popups if not pu['modal'] and pu['group']]
        if grouped and next(proj.instances('PBProject'), None) is not None \
                and not proj.popup_group_count():
            out.append(f"donor {path} has no popup group to clone, and the spec has "
                       + ', '.join(f"{pu['name']!r} in group {pu['group']!r}" for pu in grouped)
                       + ' - build from a seed that has a popup group (the 320 and 300M seeds have none), '
                       'or make it a modal')

        # Border resources, for the same clone-never-construct reason and with a
        # much wider spread than control types. Missed here it costs a whole
        # Windows round trip: Set-GdlBorder reports it per control at apply time,
        # by which point the plan has already been applied and packed.
        # DEFINED, not referenced. border_resources() walks the references, so a
        # donor that defines 2D Capsule but never draws with it would look like
        # it lacked one - which is the false positive this check first produced,
        # against a spec that had already built cleanly.
        # One the donor lacks is built as the donor's own of the nearest shape
        # where it has one - within a family the seeds differ: the 320's has no
        # 10-radius pair - and is a problem only where it has none.
        borders = proj.border_resource_names()
        found = self.border_swaps(borders)
        if swaps is not None:
            swaps.update(found)
        for want in sorted(self.needs_borders() - borders - set(found)):
            out.append(f'border resource {want!r} is not defined in {path}, and it '
                       f'defines none of that shape to build it as. It defines: '
                       f'{", ".join(sorted(borders))}')
        # A swap can make two states one: states that differ only by border
        # look alike where the donor builds both borders as one resource - Off
        # in 10 Radius 0 Thick and On in 14 Radius 0 Thick on the 320, whose
        # nearest to the first is the second. check() saw two borders.
        for item in (self.pages + self.popups) if found else []:
            for c in item['controls']:
                looks = self._states_for(c, *self._base_look(c)) or [] if self._feedback(c) else []

                def built(s):
                    return {k: found.get(v, v) if k == 'border' else v
                            for k, v in s.items() if k != 'name'}
                for i, a in enumerate(looks):
                    for b in looks[i + 1:]:
                        if a['border'] != b['border'] and built(a) == built(b):
                            out.append(
                                f"{item['name']!r} {c.get('name') or c.get('text') or '?'}: "
                                f"states {a['name']!r} and {b['name']!r} differ only by border, "
                                f"and {path} builds both as {built(a)['border']!r} - the panel "
                                f'would show no difference. Give one its own fill, stroke, '
                                f'color, text or image, or a border the donor has')
        # A stroke on a border the donor defines with no thickness is never
        # drawn - Mach's 2D Rounded Rectangle - and verify_built learns it only
        # after a build, where two states apart only by it share one image.
        out += self.stroke_rules(proj.border_geometry(), path, found)

        # Fonts, for the same reason but a softer failure: a family the donor
        # lacks does not stop the build, it silently ships in the donor's face.
        # The three-page panel built cleanly in Open Sans while its spec asked
        # for Forma DJR Display, and only the built-file verifier noticed. A
        # face a seed carries is appended instead (find_face, plan --donor).
        # A family is named as the donor or the seed spells it: one spelled
        # otherwise is refused, as it was before a face could be appended.
        from . import seeds
        from .fonts import find_face
        defined = proj.font_resource_names()
        spelled = {d.casefold(): d for d in defined}
        appended = {}
        for want in sorted(self.needs_fonts() - defined, key=str):
            if isinstance(want, str) and want.casefold() in spelled:
                out.append(f'font family {want!r} is not defined in {path}, which defines '
                           f'{spelled[want.casefold()]!r} - name it so')
                continue
            face = find_face(want)
            if face and face['family'] != want:
                out.append(f"font family {want!r} is not defined in {path}, and "
                           f"{face['carrier']} carries it as {face['family']!r} - name it so")
            elif face:
                appended[want] = face
            else:
                pointers = [s for s in seeds.here() if not seeds.usable(s)]
                none = (f'no seed here carries the face to append - {len(pointers)} of '
                        f'seeds/ are Git LFS pointers (git lfs pull)' if pointers else
                        'no seed carries the face to append')
                out.append(f'font family {want!r} has no resource in {path}, and {none} - '
                           f'every control asking for it would build in the donor\'s face. '
                           f'It defines: {", ".join(sorted(defined))}')
        if fonts is not None:
            fonts.update(appended)

        # A level the template draws from art. The one the applier clones
        # fills with a color (gaugeFillType 0: Afterburn's, Mach's) or from an
        # image (1: Shockwave's, Turbulence's), which Build draws in place of
        # any color - so no bar color is planned for it - and draws its empty
        # track from its background image, which the applier clears from every
        # other clone. `art['level']` names the two images (plan: `keep_art`).
        if art is not None:
            lv = proj.first_control('PBLevel')
            kind = proj.field(lv, 'gaugeFillTypeField') if lv is not None else None
            if isinstance(kind, dict) and kind.get('value__') == 1:
                art['level'] = {
                    part: proj.field(proj.field(lv, field), 'resourceNameField') or None
                    for part, field in (('fill', 'gaugeFillImageField'), ('track', 'backgroundImageField'))}

        # Icons. A glyph is drawn from the face the DONOR embeds, and one face
        # differs by build: the Mach seeds carry Extron-Lift's 95 glyphs, to
        # U+E95E, where the install's has 121, to U+E978. A codepoint the
        # donor's face does not map builds without complaint and draws nothing.
        # A face to be appended is the one drawn from, so it is the one read.
        if self._icon_glyphs:
            from .fonts import carried
            from .sfnt import Advances
            faces, maps = {}, {}
            for f in carried(proj):
                faces.setdefault(f['family'], (f['bytes'], f'the {f["family"]} {path} carries'))
            for font, face in appended.items():
                faces.setdefault(font, (face['bytes'], f"the {font} to be appended from "
                                                       f"{face['carrier']}"))
            for where, font, cp in self._icon_glyphs:
                if font not in faces:
                    if font in defined:     # no resource at all is reported above
                        out.append(f'{where}: {path} defines {font} but carries no face '
                                   f'for it to draw U+{cp:04X} in')
                    continue
                if font not in maps:
                    maps[font] = Advances(faces[font][0]).cmap
                if cp not in maps[font]:
                    out.append(f'{where}: {faces[font][1]} has no glyph at '
                               f'U+{cp:04X} - it would build blank')

        # Model and theme. The built panel is the donor's - the applier never
        # touches its platform or skin - whatever the spec names. seeds/ names a
        # seed for its size, so a TLP725M spec lands on 'Afterburn 725.gdl', a
        # TLP725T of the same canvas that every other gate here passes. The
        # 1035T and 1035M share a part number, so they share a donor.
        top = next(proj.instances('PBProject'), None)
        plat = proj.field(top, 'platformField') if top is not None else None
        got = proj.field(plat, 'partNumberField') if plat is not None else None
        if self.model and got and got != part_number(self.model):
            from .seeds import models_of
            out.append(f"the donor {path} is a {models_of(got)} ({got}), and the spec's model a "
                       f'{self.model} ({part_number(self.model)}) - the built panel is the '
                       f"donor's model. Build on a {self.model} seed (python -m gdl.seeds pick "
                       f'<spec>), or retarget the donor to it first (python -m gdl.edit)')
        family = self.spec.get('family')
        skin = proj.field(top, 'skinField') if top is not None else None
        if isinstance(family, str) and family.strip() and isinstance(skin, str) and skin \
                and skin.casefold() != family.strip().casefold():
            out.append(f"the donor {path} is a {skin} project, and the spec's family "
                       f'{family.strip()} - the built panel is in the donor\'s theme. Name the '
                       f'family it is, or build on a {family.strip()} seed')

        # Canvas. The spec lays out against its own `size`, but the built panel
        # is whatever the DONOR is. Author 1024x600 into a 1280x800 project and
        # the layout is right by its own arithmetic and wrong on the panel.
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
        for kind, items in (('page', self.pages), ('popup', self.popups)):
            for pg in items:
                want = pg.get('background_image')
                if want and want not in self.images and want not in images:
                    out.append(f"{kind} {pg['name']!r}: background image {want!r} is neither in "
                               f"the spec's `images` nor defined in {path}")
        for kind, items in (('page', self.pages), ('popup', self.popups)):
            for pg in items:
                for c in pg['controls']:
                    # Through _feedback, as plan() reads them: an `on` of
                    # {"image": ...} names one as surely as `states` does.
                    named = [c.get('image'), c.get('thumb_image'), c.get('track_image'),
                             c.get('fill_image')] + [
                        st.get('image') for st in self._feedback(c) or []]
                    for want in sorted({n for n in named if n}):
                        if want not in self.images and want not in images:
                            out.append(f"{kind} {pg['name']!r} "
                                       f"{c.get('name') or c.get('text') or '?'}: image "
                                       f"{want!r} is neither in the spec's `images` nor "
                                       f'defined in {path}')

        # Names can collide only with the donor's pages and popups that are
        # still there: every one, for a spec that keeps them; otherwise the
        # Offline Page, which the applier keeps when it drops the rest.
        keep = bool(self.spec.get('keep_donor_pages'))
        taken = kept_names(proj.pages(), keep)
        for it in list(self.pages) + list(self.popups):
            if it['name'] in taken:
                out.append(f"{it['name']!r} already exists in the donor project - page "
                           f'and popup names must be unique, and Build rejects duplicates'
                           + ('' if keep else " (the applier keeps the donor's Offline Page)"))
        return out

    def needs(self):
        """Every control class this spec requires a donor for."""
        return {KIND_TYPE.get(c.get('kind', 'panel'), 'PBShape')
                for pg in self.pages + self.popups for c in pg['controls']}

    def border_swaps(self, defined):
        """{border resource this spec names: the one to build it as} for each
        that `defined` - a donor's border resources - lacks and has one of the
        same shape for (nearest_border)."""
        out = {}
        for want in sorted(self.needs_borders() - set(defined)):
            sub = nearest_border(want, defined)
            if sub:
                out[want] = sub
        return out

    def needs_borders(self):
        """Every named border RESOURCE this spec references, already resolved.

        A plan may only point at a resource the donor carries - creating one
        has never been tested against GUI Designer - so which donor you use
        decides which borders a spec's names are built as: its own where it
        has them, else its nearest shape (border_swaps). Every project defines
        GUI Designer's 13 built-ins; the themed seeds carry 13 to 31 in all.
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
            # A modal's background never reaches the panel: Build draws a
            # modal black at its own transparency (MODAL_TRANSPARENCY).
            if not pg.get('modal'):
                add(pg['background'])
            for c in pg['controls']:
                # A slider drawn from rail art is written with no fill or
                # stroke (_base_look), so the profile's default reaches nothing.
                railed = c.get('kind') == 'slider' and c.get('track_image')
                # A state's colors are on the panel as much as the control's
                # own - an On fill included.
                for look in [c] + (self._feedback(c) or []):
                    for key in ('fill', 'stroke', 'color', 'text_color'):
                        if railed and key in ('fill', 'stroke'):
                            continue
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


def _icons_command(family, sheet=None):
    """Every glyph a family's icon face draws, by codepoint and by the name the
    face gives it, if any - and with `sheet`, the glyphs drawn to pick from by
    eye, which is the only way into a face that names nothing."""
    from .fonts import ICON_FONTS, icon_face
    key = next((k for k in ICON_FONTS if k.lower() == family.lower()), None)
    if key and not ICON_FONTS[key]:
        print(f'{key} has no icon font - its template draws its icons as images '
              f'(docs/design-rules.md section 6)')
        return 1
    font = ICON_FONTS[key] if key else family
    from .sfnt import Advances
    data, where = icon_face(font)
    if not data:
        print(f'no {font} face here: it is not recovered into gdl/fonts/'
              + (f', and seeds/{key} 1035.gdl is not pulled - git lfs pull --include '
                 f'"seeds/{key} 1035.gdl"' if key else ', and no seed here carries it'))
        return 1
    face = Advances(data)
    names = {cp: n for n, cp in face.glyph_names().items()}
    cps = sorted(c for c, g in face.cmap.items() if c > 0x20 and g)
    for cp in cps:
        print(f'  U+{cp:04X}  {names.get(cp, "")}'.rstrip())
    print(f'{len(cps)} glyph(s) in {font}, {len(names) or "none"} named, from {where}'
          + ('' if names or not cps else ' - an icon gives its codepoint, as "U+%04X"' % cps[0]))
    if sheet:
        from .compose import glyph_sheet          # Pillow
        glyph_sheet(data, sheet)
        print(f'drawn -> {sheet}')
    return 0


def main(argv):
    # A report quotes the spec back - a caption, a room name - and a Windows
    # stdout redirected to a file encodes cp1252, which has none of most of
    # that: escape what it cannot take rather than crash mid-report.
    try:
        sys.stdout.reconfigure(errors='backslashreplace')
    except (AttributeError, ValueError):
        pass
    if len(argv) < 3:
        print(__doc__.strip().split('\n\n')[0])
        print('\n  python -m gdl.spec render <spec.json> <out.png> [page]'
              '\n  python -m gdl.spec check  <spec.json>'
              '\n  python -m gdl.spec plan   <spec.json> <plan.json> [--donor <donor.gdl>]'
              '\n  python -m gdl.spec donors <spec.json> [<donor.gdl>|--auto]  (--auto: the'
              '\n      seed for the spec\'s "family", model and canvas - the default)'
              '\n  python -m gdl.spec icons  <family or icon font> [sheet.png]'
              '   (what an "icon" takes; the sheet draws them)')
        return 2
    cmd, path = argv[1], argv[2]
    if cmd == 'icons':
        return _icons_command(path, argv[3] if len(argv) > 3 else None)
    panel = Panel.load(path)
    problems = panel.check()
    if cmd == 'check':
        for p in problems:
            print('  ' + p)
        print(f'{len(problems)} problem(s); {len(panel.pages)} page(s), '
              f'{sum(len(p["controls"]) for p in panel.pages)} controls')
        return 1 if problems else 0
    if cmd == 'donors':
        donor = argv[3] if len(argv) > 3 else '--auto'
        if donor == '--auto':
            # The seed for the spec's family, model and canvas (gdl.seeds).
            from . import seeds
            picked, why = seeds.for_spec(panel.spec)
            if not picked:
                print('  ' + why)
                return 1
            print(f'donor: {picked}')
            donor = seeds.path(picked)
        swaps, fonts = {}, {}
        problems = panel.check_donor(donor, swaps=swaps, fonts=fonts)
        for p in problems:
            print('  ' + p)
        for want, got in swaps.items():
            print(f'  border {want!r} is not in {donor}: built as {got!r}, its nearest '
                  f'(plan --donor writes it)')
        for want, face in fonts.items():
            print(f"  font {want!r} is not in {donor}: appended from {face['carrier']} "
                  f'(plan --donor writes it)')
        print(f'{len(panel.needs())} control type(s) needed: '
              f'{", ".join(sorted(panel.needs()))}')
        print(f'{len(problems)} donor problem(s)')
        return 1 if problems else 0
    if cmd == 'plan':
        # <plan.json> and --donor <gdl>, in either order. A misplaced --donor
        # was taken for the plan path, and a plan named '--donor' written.
        out_path, donor, rest = None, None, list(argv[3:])
        while rest:
            a = rest.pop(0)
            if a == '--donor' and rest and not rest[0].startswith('--'):
                donor = rest.pop(0)
            elif a.startswith('--') or out_path is not None:
                out_path = None
                break
            else:
                out_path = a
        if out_path is None or rest:
            print('  python -m gdl.spec plan <spec.json> <plan.json> [--donor <donor.gdl>]')
            return 2
        if problems:
            for p in problems:
                print('  ' + p)
            return 1
        swaps, fonts, art = {}, [], {}
        if donor:
            # What `donors` says it does (check_donor): the borders the donor
            # lacks, built as its own nearest, and the faces it lacks that a
            # seed carries, written beside the plan for the applier to append.
            # Its problems are `donors`' to refuse; this writes what it can.
            from .fonts import _file_name
            faces = {}
            panel.check_donor(donor, swaps=swaps, fonts=faces, art=art)
            for want, got in swaps.items():
                print(f'  border {want!r} is built as {got!r}, the nearest {donor} has')
            for want, face in faces.items():
                # As the carrier records it: Arial Black, a face GUI Designer
                # supplies, has no file names and declares 28 bytes past its data.
                where = os.path.join(os.path.dirname(os.path.abspath(out_path)), 'fonts',
                                     _file_name(face))
                os.makedirs(os.path.dirname(where), exist_ok=True)
                with open(where, 'wb') as fh:
                    fh.write(face['bytes'])
                fonts.append({'family': face['family'], 'style': face['style'], 'file': where,
                              'embedded': face['file'], 'source': face['source'],
                              'size': face['size'] or len(face['bytes']), 'default': face['default'],
                              'author': face['author'], 'carrier': face['carrier']})
                print(f"  font {want!r} is appended to it from {face['carrier']}")
        plan = panel.plan(swaps, fonts, art)
        with open(out_path, 'w', encoding='utf-8') as fh:
            json.dump(plan, fh, indent=1)
        print(f'{len(plan["pages"])} page(s), '
              f'{sum(len(p["controls"]) for p in plan["pages"])} control ops -> {out_path}')
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
        from .compose import FALLBACKS
        if FALLBACKS:
            print(f"  NOTE drawn in a stand-in, not the panel's face - "
                  f"{'; '.join(sorted(FALLBACKS))}")
        return 0
    print(f'unknown command {cmd!r}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
