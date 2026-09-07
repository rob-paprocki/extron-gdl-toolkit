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
}
WINFONTS = 'C:/Windows/Fonts'
_cache = {}


def face(name, bold, italic, px):
    key = (name, bold, italic, round(px, 2))
    if key in _cache:
        return _cache[key]
    primary = FILES.get((name, bold, italic)) or FILES.get((name, 0, 0))
    candidates = [primary] + ALIASES.get(primary, []) + ['arial.ttf']
    for base, fn in ((b, c) for b in (FONTDIR, WINFONTS) for c in candidates if c):
        p = os.path.join(base, fn)
        if os.path.exists(p):
            f = ImageFont.truetype(p, size=px)
            _cache[key] = f
            return f
    f = ImageFont.truetype(os.path.join(WINFONTS, 'arial.ttf'), size=px)
    _cache[key] = f
    return f


def metrics(f):
    """(ascent, descent) from the OS/2 winAscent/winDescent GDI actually uses."""
    a, d = f.getmetrics()
    return a, d


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
    lines = wrap(text, fnt, w, lambda s, f: d0.textlength(s, font=f))
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
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=fnt)
        if horz == 1:
            tx = x
        elif horz == 2:
            tx = x + w - tw
        else:
            tx = x + (w - tw) / 2
        d.text((tx, top + i * lh), ln, font=fnt, fill=color, anchor='la')


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


def group_members(layout):
    """GroupID -> popup page IDs, in PopupPages array order."""
    out = {}
    for p in layout.get('PopupPages') or []:
        g = p.get('GroupID')
        if g:
            out.setdefault(g, []).append(p)
    return out


def render_control(canvas, c, assets, ox, oy, draw_txt=True, groups=None):
    ref = popup_ref(c)
    if ref:
        # A reference bound to one popup paints nothing. A reference bound to a
        # GROUP does: GUI Designer composites one member into the anchor rect,
        # and its snapshot is taken with that member showing. Draw it here, in
        # the anchor's own z-order slot rather than on top of everything.
        gid = ref.get('group')
        if gid and groups and groups.get(gid):
            render_page(groups[gid][0], assets, None, ox + c['Left'], oy + c['Top'],
                        canvas=canvas, draw_txt=draw_txt, groups=groups)
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


def render_page(pg, assets, size, ox=0, oy=0, canvas=None, draw_txt=True, groups=None):
    if canvas is None:
        canvas = Image.new('RGBA', size, (0, 0, 0, 255))
        fill = rgba(pg.get('BackgroundFillColor'))
        if pg.get('TLPImageID', -1) == -1 and fill and fill[3]:
            canvas.paste(fill, [0, 0, *size])
    paste(canvas, assets, pg.get('TLPImageID'), ox, oy)
    for c in (pg.get('Controls') or []):
        render_control(canvas, c, assets, ox, oy, draw_txt, groups)
    return canvas


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


def render_snapshot(j, pid, assets, size, shown=None, draw_txt=True):
    """Render a page the way GUI Designer's own snapshot does.

    A PBPopupPageReference bound to a single popup (IsPopupPageIdValid)
    paints nothing.  One bound to a popup *group* (IsPopupGroupIdValid)
    paints a member of that group at the anchor's origin - by default the
    first member in declaration order, or `shown[GroupID]` if given.
    """
    pages = {p['ID']: p for p in j['Pages'] + j['PopupPages']}
    groups = popup_groups(j)
    pg = pages[pid]
    canvas = render_page(pg, assets, size, draw_txt=draw_txt)
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
                    canvas=canvas, draw_txt=draw_txt)
    return canvas


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
