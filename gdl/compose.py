"""Composite a .gdl page exactly the way the HTML viewer does, then diff the
result against GUI Designer's own snapshot render.

The point is not to ship this image - it is to prove the render RULES
(geometry, z-order, state choice, alignment enum, point-size factor, line
metrics) against ground truth the application produced itself.
"""
import io
import json
import os
import re
import struct
import sys
import zipfile

from PIL import Image, ImageChops, ImageDraw, ImageFont

from . import sfnt
from .container import open_gdl
from .data import popup_ref  # noqa: E402

PT = 1.375           # 99 DPI, per the glyph-outline measurements
FONTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')

# family + bold/italic -> the actual binary
FILES = {
    ('Arial', 0, 0): 'arial.ttf', ('Arial', 1, 0): 'arialbd.ttf',
    ('Arial', 0, 1): 'ariali.ttf', ('Arial', 1, 1): 'arialbi.ttf',
    ('Arial Black', 0, 0): 'ariblk.ttf',
    ('Open Sans', 0, 0): 'opensans-regular.ttf',
    ('Open Sans Light', 0, 0): 'opensans-light.ttf',
    ('Forma DJR Display', 0, 0): 'formadjrdisplay-regular_1.otf',
    ('Extron-Afterburn', 0, 0): 'afterburn_modified.ttf',
    ('Crestron General', 0, 0): 'crestron_general.ttf',
    ('Extron GUIC Video Conference 1', 0, 0): 'extron_guic_video_conference_1.ttf',
}
# Some faces are embedded under different EmbeddedFileNames in different
# projects: the _alt fixtures ship Afterburn as extron_-_afterburn_1a.ttf. Miss
# these and the face silently falls back to Arial, which is easy not to notice.
ALIASES = {
    'afterburn_modified.ttf': ['extron_-_afterburn_1a.ttf'],
    # The system faces ship under Windows 8.3-ish names on Windows and spelled-out
    # ones on macOS. Without these, every Arial variant quietly resolves to plain
    # Arial off Windows - the bold and the black would render as regular.
    'arial.ttf': ['Arial.ttf'],
    'arialbd.ttf': ['Arial Bold.ttf'],
    'ariali.ttf': ['Arial Italic.ttf'],
    'arialbi.ttf': ['Arial Bold Italic.ttf'],
    'ariblk.ttf': ['Arial Black.ttf'],
}
# Where the *system* faces live. Arial and Arial Black are not embedded in a
# .gdl - on Windows they come from C:/Windows/Fonts, and off Windows they have
# to be found somewhere else or the render dies rather than degrades.
SYSFONTS = (
    'C:/Windows/Fonts',
    '/System/Library/Fonts/Supplemental', '/System/Library/Fonts', '/Library/Fonts',
    os.path.expanduser('~/Library/Fonts'),
    '/usr/share/fonts', '/usr/local/share/fonts', os.path.expanduser('~/.fonts'),
)
WINFONTS = SYSFONTS[0]          # kept: referenced by name elsewhere
_cache = {}
_sysindex = None


def _system_fonts():
    """lowercased filename -> full path, for every system font dir that exists.

    Indexed case-insensitively because the same face is `arial.ttf` on Windows
    and `Arial.ttf` on macOS, and an exact-name lookup silently misses it.
    """
    global _sysindex
    if _sysindex is None:
        _sysindex = {}
        for base in SYSFONTS:
            if not os.path.isdir(base):
                continue
            for root, _, names in os.walk(base):
                for n in names:
                    _sysindex.setdefault(n.lower(), os.path.join(root, n))
    return _sysindex


def face(name, bold, italic, px):
    key = (name, bold, italic, round(px, 2))
    if key in _cache:
        return _cache[key]
    primary = FILES.get((name, bold, italic)) or FILES.get((name, 0, 0))
    candidates = [c for c in [primary] + ALIASES.get(primary or '', []) + ['arial.ttf'] if c]
    for fn in candidates:
        p = os.path.join(FONTDIR, fn)
        if os.path.exists(p):
            f = _cache[key] = ImageFont.truetype(p, size=px)
            return f
    index = _system_fonts()
    for fn in candidates:
        p = index.get(fn.lower())
        if p:
            f = _cache[key] = ImageFont.truetype(p, size=px)
            return f
    raise LookupError(
        f'no font file for {name!r} (bold={bold} italic={italic}). Embedded faces '
        f'come from `python -m gdl.fonts <file.gdl> gdl/fonts/`; system faces like '
        f'Arial must exist in one of {SYSFONTS}.')


def metrics(f):
    """(ascent, descent) from the OS/2 winAscent/winDescent GDI actually uses.

    Read from the font rather than via Pillow: getmetrics() rounds both to
    whole pixels, which costs a pixel of line box per line and pushes a
    vertically centred block off by half of it. See gdl/sfnt.py.
    """
    a = advances(f)
    if a is not None:
        return a.vmetrics(f.size)
    return f.getmetrics()


# Lay text out with the font's own fractional advances instead of Pillow's
# grid-fitted integer ones, and place each glyph at its own fractional x.
# See docs/render-fidelity.md finding 7 for what each is worth.
FRAC_MEASURE = True
FRAC_PLACE = True
# Horizontal registration: Pillow's rasteriser and GDI+ disagree by the usual
# half pixel (sample at the pixel corner vs at its centre). The value is a
# convention, not a fit - and it is a clean minimum on the shipped model, which
# is confirmation rather than derivation. research/compose2.py also uses -0.5,
# but on the same corpus and with its own metric preferring roughly -0.75, so
# treat that as agreement about the convention, not independent evidence.
DX = -0.5
_adv = {}


def advances(fnt):
    """The sfnt advance table for a Pillow font, or None if it will not parse."""
    path = getattr(fnt, 'path', None)
    if path not in _adv:
        try:
            _adv[path] = sfnt.Advances(path)
        except Exception:
            # A face we cannot parse falls back to Pillow's own measurement
            # rather than failing the render.
            _adv[path] = None
    return _adv[path]


def measure(s, fnt, draw=None):
    """Text width in pixels, fractional where the font lets us read it."""
    if FRAC_MEASURE:
        a = advances(fnt)
        if a is not None:
            return a.length(s, fnt.size)
    return (draw or ImageDraw.Draw(Image.new('RGBA', (1, 1)))).textlength(s, font=fnt)


def rgba(c):
    if not isinstance(c, dict):
        return None
    return (c.get('R', 0), c.get('G', 0), c.get('B', 0), c.get('A', 255))


def wrap(text, fnt, width, measure):
    """GDI DT_WORDBREAK: break on spaces, then split any word too long to fit."""
    out = []
    for para in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if not para:
            out.append('')
            continue
        line = ''
        for word in re.split(r'(\s+)', para):
            if not word:
                continue
            trial = line + word
            if measure(trial, fnt) <= width or not line.strip():
                # the word itself may still be wider than the box
                while measure(trial, fnt) > width and len(trial) > 1:
                    cut = len(trial) - 1
                    while cut > 1 and measure(trial[:cut], fnt) > width:
                        cut -= 1
                    out.append(trial[:cut])
                    trial = trial[cut:]
                line = trial
            else:
                out.append(line.rstrip())
                line = word.lstrip()
        out.append(line.rstrip())
    return out


def draw_text(img, box, text, fnt, color, alignv):
    """Place a text block per AlignmentEnum: value = 3*vertical + horizontal."""
    x, y, w, h = box
    vert = alignv // 3          # 0 bottom, 1 middle, 2 top
    horz = alignv % 3           # 0 centre, 1 left, 2 right
    d0 = ImageDraw.Draw(img)
    lines = wrap(text, fnt, w, lambda s, f: measure(s, f, d0))
    asc, desc = metrics(fnt)
    lh = asc + desc
    block = lh * len(lines)
    if vert == 2:
        top = y
    elif vert == 1:
        top = y + (h - block) / 2
    else:
        top = y + h - block
    d = ImageDraw.Draw(img)
    adv = advances(fnt) if FRAC_PLACE else None
    for i, ln in enumerate(lines):
        tw = measure(ln, fnt, d)
        if horz == 1:
            tx = x
        elif horz == 2:
            tx = x + w - tw
        else:
            tx = x + (w - tw) / 2
        # Anchor on the baseline: 'la' would re-introduce Pillow's own rounded
        # ascender, which is the thing metrics() exists to avoid.
        tx += DX
        ty = top + i * lh + asc
        if adv is None:
            d.text((tx, ty), ln, font=fnt, fill=color, anchor='ls')
            continue
        # Draw glyph by glyph so each lands on its own fractional x. Pillow
        # advances by whole pixels within a string, which drifts a line's
        # interior apart from GDI+'s layout even when the total width agrees.
        for ch in ln:
            d.text((tx, ty), ch, font=fnt, fill=color, anchor='ls')
            tx += adv.advance(ch, fnt.size)


def paste(canvas, assets, img_id, x, y, clip=None, binary=True):
    """Blit an asset.

    GUI Designer composites a control with a BINARY alpha test rather than
    straight alpha: any source pixel with alpha > 0 is written at full
    strength, alpha == 0 is skipped. Measured over 3,296 partial-alpha pixels,
    straight alpha is off by a mean of 97 levels per channel; binary by 2.15.
    """
    if img_id is None or img_id not in assets:
        return
    im = Image.open(io.BytesIO(assets[img_id])).convert('RGBA')
    if clip:
        im = im.crop(clip)
        x, y = x + clip[0], y + clip[1]
    if binary:
        mask = im.getchannel('A').point(lambda a: 255 if a > 0 else 0)
        canvas.paste(im, (int(x), int(y)), mask)
    else:
        canvas.alpha_composite(im, (int(x), int(y)))


def fill_index(path):
    """(page id, control id) -> the fill Build would have rasterised.

    A control authored with TLPImageID == -1 has no artwork in the payload, and
    its real interior colour - borderFillColor plus a *named* border resource
    giving the corner radius - exists only in ProjectGCP. layout.json exports
    neither, so the compositor cannot draw the control at all without going
    back to the authoring model. See docs/render-fidelity.md finding 1.

    The key is the pair of ids both models already share: a page's `idField` is
    layout.json's `Page.ID`, and a control's `idField` is its `Control.ID`
    (verified equal across all six fixtures). An earlier version keyed on
    (type, rect) because the authoring model was only read as a flat object
    graph - that worked here, but only because the eligible set is a single
    control per file. (type, rect) is not unique over controls generally, and
    nothing checked the destination side, so two same-typed same-positioned
    controls on different pages would both have been filled.
    """
    from .project import Project

    return Project.open(path).fill_map()


def draw_fill(canvas, box, spec):
    """Paint the rounded rectangle Build would have baked into a PNG."""
    fill = rgba(spec['fill'])
    stroke = rgba(spec.get('stroke'))
    if not fill or not fill[3]:
        fill = None
    if not stroke or not stroke[3]:
        stroke = None
    if not fill and not stroke:
        return
    border = spec.get('border') or {}
    radius = border.get('radius', 0)
    thickness = border.get('thickness', 0) if stroke else 0
    x0, y0 = box[0], box[1]
    x1, y1 = box[0] + box[2] - 1, box[1] + box[3] - 1
    # A capsule is stored as radius 9999 rather than a shape flag, so clamp
    # rather than hand Pillow a radius larger than the box.
    radius = min(radius, min(box[2], box[3]) // 2)
    d = ImageDraw.Draw(canvas)
    if radius > 0:
        d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                            outline=stroke, width=max(1, thickness) if stroke else 0)
    else:
        d.rectangle([x0, y0, x1, y1], fill=fill,
                    outline=stroke, width=max(1, thickness) if stroke else 0)


def group_members(layout):
    """GroupID -> popup page IDs, in PopupPages array order."""
    out = {}
    for p in layout.get('PopupPages') or []:
        g = p.get('GroupID')
        if g:
            out.setdefault(g, []).append(p)
    return out


def render_control(canvas, c, assets, ox, oy, draw_txt=True, groups=None, fills=None,
                   page_id=None):
    ref = popup_ref(c)
    if ref:
        # A reference bound to one popup paints nothing. A reference bound to a
        # GROUP does: GUI Designer composites one member into the anchor rect,
        # and its snapshot is taken with that member showing. Draw it here, in
        # the anchor's own z-order slot rather than on top of everything.
        gid = ref.get('group')
        if gid and groups and groups.get(gid):
            render_page(groups[gid][0], assets, None, ox + c['Left'], oy + c['Top'],
                        canvas=canvas, draw_txt=draw_txt, groups=groups, fills=fills)
        return
    kind = c['__type'].split(':')[0]
    states = c.get('States') or []
    st = states[c.get('TLPDefaultStateID', 0)] if states else None
    src = st or c

    base = c.get('TLPImageID')
    if kind == 'PBLevel':
        base = c.get('TLPMinValueImageID', base)
    elif st is not None:
        base = st.get('TLPImageID', base)
    x, y, w, h = c['Left'] + ox, c['Top'] + oy, c['Width'], c['Height']
    if base in (None, -1) or base not in assets:
        # Build never rasterised this one, so there is no PNG to blit. Its fill
        # lives in the authoring model; synthesise what Build would have baked.
        spec = (fills or {}).get((page_id, c.get('ID')))
        if spec:
            draw_fill(canvas, (x, y, w, h), spec)
    paste(canvas, assets, base, x, y)

    # value fill for sliders / levels, parked at half travel
    mx = c.get('TLPMaxValueImageID')
    if mx is not None and mx != base and mx in assets:
        o = c.get('Orientation', 0)
        if o == 2:
            paste(canvas, assets, mx, x, y, clip=(0, h // 2, w, h))
        elif o == 3:
            paste(canvas, assets, mx, x, y, clip=(0, 0, w, h // 2))
        elif o == 1:
            paste(canvas, assets, mx, x, y, clip=(w // 2, 0, w, h))
        else:
            paste(canvas, assets, mx, x, y, clip=(0, 0, w // 2, h))
    ind = c.get('SliderIndicatorImageID')
    if ind and ind in assets:
        iw = c.get('SliderIndicatorWidth') or w
        ih = c.get('SliderIndicatorHeight') or h
        o = c.get('Orientation', 0)
        if o in (2, 3):
            paste(canvas, assets, ind, x + (w - iw) // 2, y + (h - ih) // 2)
        else:
            paste(canvas, assets, ind, x + (w - iw) // 2, y + (h - ih) // 2)

    if not draw_txt or c.get('FlattenText'):
        return
    text = src.get('Text') or c.get('Text') or ''
    if not text.strip():
        return
    f = src.get('Font') or c.get('Font') or {}
    style = f.get('Style') or {}
    fnt = face(f.get('Name', 'Arial'), int(bool(style.get('Bold'))),
               int(bool(style.get('Italic'))), f.get('PointSize', 12) * PT)
    col = rgba(src.get('TextColor')) or rgba(c.get('TextColor')) or (255, 255, 255, 255)
    draw_text(canvas, (x, y, w, h), text,
              fnt, col, src.get('TextAlignment', c.get('TextAlignment', 3)))


def flatten(canvas):
    """Put the finished page on opaque black, the way the panel displays it.

    Deliberately the same binary rule paste() uses rather than an alpha
    composite: a pixel that was painted keeps its own colour at full strength,
    an untouched one stays black. That reproduces the previous
    opaque-canvas-from-the-start behaviour exactly.

    The final putalpha is not cosmetic. paste() copies the source's own alpha
    through, so a page whose art is itself semi-transparent (the modal scrim
    asset is a uniform alpha 166) would otherwise come back partly transparent
    from a function whose contract says opaque. Every caller today converts to
    RGB, which drops alpha rather than compositing it, so this is currently
    invisible - measured identical across all 27 pages. It is here so the
    contract is true rather than true-by-accident-of-the-caller.
    """
    bg = Image.new('RGBA', canvas.size, (0, 0, 0, 255))
    bg.paste(canvas, (0, 0), canvas.getchannel('A').point(lambda a: 255 if a else 0))
    bg.putalpha(255)
    return bg


def render_page(pg, assets, size, ox=0, oy=0, canvas=None, draw_txt=True, groups=None,
                fills=None, flat=True):
    # The canvas starts *transparent* and is flattened onto black once, at the
    # end of the outermost call. An opaque-from-the-start canvas destroys the
    # only signal that says whether a control sits over real artwork or over
    # nothing, and that signal is what finding 4's bilevel/antialiased text
    # decision reads. Nested calls (popup-group members) are handed the live
    # canvas and must not flatten it.
    outermost = canvas is None
    if outermost:
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        fill = rgba(pg.get('BackgroundFillColor'))
        if pg.get('TLPImageID', -1) == -1 and fill and fill[3]:
            canvas.paste(fill, [0, 0, *size])
    paste(canvas, assets, pg.get('TLPImageID'), ox, oy)
    for c in (pg.get('Controls') or []):
        render_control(canvas, c, assets, ox, oy, draw_txt, groups, fills, pg.get('ID'))
    return flatten(canvas) if outermost and flat else canvas


def popup_groups(j):
    """GroupID -> member popup IDs, in PopupPages declaration order.

    Element 0 of each list is the member GUI Designer previews on the host
    page (proven against Individual == Permutation snapshots for groups 1,
    2, 3 and 5).
    """
    g = {}
    for p in j.get('PopupPages') or []:
        if p.get('IsGroupValid'):
            g.setdefault(p['GroupID'], []).append(p['ID'])
    return g


def render_snapshot(j, pid, assets, size, shown=None, draw_txt=True, fills=None):
    """Render a page the way GUI Designer's own snapshot does.

    A PBPopupPageReference bound to a single popup (IsPopupPageIdValid)
    paints nothing.  One bound to a popup *group* (IsPopupGroupIdValid)
    paints a member of that group at the anchor's origin - by default the
    first member in declaration order, or `shown[GroupID]` if given.
    """
    pages = {p['ID']: p for p in j['Pages'] + j['PopupPages']}
    groups = popup_groups(j)
    pg = pages[pid]
    canvas = render_page(pg, assets, size, draw_txt=draw_txt, fills=fills, flat=False)
    for c in (pg.get('Controls') or []):
        pp = c.get('PopupPageID')
        if not isinstance(pp, dict) or not pp.get('IsPopupGroupIdValid'):
            continue
        members = groups.get(pp.get('GroupID')) or []
        if not members:
            continue
        mid = (shown or {}).get(pp['GroupID'], members[0])
        if mid is None:
            continue
        render_page(pages[mid], assets, size, ox=c['Left'], oy=c['Top'],
                    canvas=canvas, draw_txt=draw_txt, fills=fills)
    return flatten(canvas)


def load(path):
    z = open_gdl(path)
    inner = zipfile.ZipFile(io.BytesIO(z.read(next(n for n in z.namelist() if n != 'ProjectGCP'))))
    j = json.loads(inner.read('layout.json'))
    assets = {int(n[:-4]): inner.read(n) for n in inner.namelist() if n.endswith('.png')}
    return j, assets


def diff_stats(a, b):
    a, b = a.convert('RGB'), b.convert('RGB')
    d = ImageChops.difference(a, b)
    bbox = d.getbbox()
    hist = d.convert('L').histogram()
    total = a.width * a.height
    off = total - hist[0]
    bad = sum(hist[24:])
    return {'pct_any': 100 * off / total, 'pct_bad': 100 * bad / total, 'bbox': bbox}
