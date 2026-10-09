"""Experimental compositor: compose.py plus switchable text-rendering rules."""
import io, json, os, re, sys, zipfile
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdl_data import popup_ref
from compose import PT, face, metrics, rgba, paste, load, diff_stats

OPT = dict(
    aa='auto',        # 'L' always AA, '1' always aliased, 'auto' = by backdrop opacity
    dy=0.0,           # extra vertical offset applied to the text block
    bold='none',      # 'none' | 'smear' | 'advance' | 'both'
    boldpx=1,         # smear width in px / extra advance per glyph
    vmetric='ft',     # 'ft' = Pillow getmetrics, 'win' = OS/2 winAscent/Descent
    vround='none',    # 'none' | 'floor' | 'round' on the block top
    dy_a=0.0, dy_b=0.0,   # dy = dy_a + dy_b*px
    dx=0.0,
    dpx=0.0,          # px size adjustment (bold only, when boldpx_scale set)
    bold_dpx=0.0,     # extra px added to the face size for synthetic-bold runs
    wrapk=0.0,        # GDI+ StringFormat padding: usable width = w - wrapk*px
    lhk=None,         # line pitch = lhk*px  (None keeps Pillow's asc+desc)
    ak=None,          # baseline from line top = ak*px
    fillthr=2,        # coverage (0-255) at which a bilevel pixel turns on
    aagamma=1.0,      # coverage exponent for the antialiased branch
)

_wm = {}


def winmetrics(fname, bold, italic, px):
    key = (fname, bold, italic, round(px, 3))
    if key in _wm:
        return _wm[key]
    from fontTools.ttLib import TTFont
    from compose import FILES, FONTDIR, WINFONTS
    fn = FILES.get((fname, bold, italic)) or FILES.get((fname, 0, 0)) or 'arial.ttf'
    p = os.path.join(FONTDIR, fn)
    if not os.path.exists(p):
        p = os.path.join(WINFONTS, fn)
    t = TTFont(p, lazy=True)
    upem = t['head'].unitsPerEm
    o = t['OS/2']
    _wm[key] = (o.usWinAscent * px / upem, o.usWinDescent * px / upem)
    return _wm[key]


def wrap(text, fnt, width, measure):
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


def draw_text(img, box, text, fnt, color, alignv, opt, mode):
    x, y, w, h = box
    vert, horz = alignv // 3, alignv % 3
    d = ImageDraw.Draw(img)
    d.fontmode = mode
    bold = opt['bold']
    bpx = opt['boldpx']
    extra = bpx if bold in ('advance', 'both') else 0
    smear = bpx if bold in ('smear', 'both') else 0

    def measure(s, f):
        return d.textlength(s, font=f) + extra * len(s)

    lines = wrap(text, fnt, w - opt.get('wrapk', 0.0) * opt['_px'], measure)
    if opt['vmetric'] == 'win':
        asc, desc = winmetrics(opt['_fname'], opt['_bold'], opt['_italic'], opt['_px'])
    else:
        asc, desc = metrics(fnt)
    lh = asc + desc
    if opt.get('lhk'):
        lh = opt['lhk'] * opt['_px']
        asc = (opt['ak'] if opt.get('ak') else 0.82) * opt['_px']
    block = lh * len(lines)
    if vert == 2:
        top = y
    elif vert == 1:
        top = y + (h - block) / 2
    else:
        top = y + h - block
    top += opt['dy'] + opt.get('dy_a',0.0) + opt.get('dy_b',0.0)*opt['_px']
    if opt['vround'] == 'floor':
        top = float(int(top))
    elif opt['vround'] == 'round':
        top = float(round(top))
    ftasc = metrics(fnt)[0]
    for i, ln in enumerate(lines):
        tw = measure(ln, fnt) + smear
        if horz == 1:
            tx = x
        elif horz == 2:
            tx = x + w - tw
        else:
            tx = x + (w - tw) / 2
        tx += opt.get('dx', 0.0)
        ty = top + i * lh
        if opt['vmetric'] == 'win' or opt.get('lhk'):
            ty = ty + asc - ftasc
        for sx in range(smear + 1):
            if extra:
                cx = tx + sx
                for ch in ln:
                    d.text((cx, ty), ch, font=fnt, fill=color, anchor='la')
                    cx += d.textlength(ch, font=fnt) + extra
            else:
                d.text((tx + sx, ty), ln, font=fnt, fill=color, anchor='la')


def render_control(canvas, c, assets, ox, oy, draw_txt, opt, alpha_probe):
    if popup_ref(c):
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
        paste(canvas, assets, ind, x + (w - iw) // 2, y + (h - ih) // 2)
    if not draw_txt or c.get('FlattenText'):
        return
    text = src.get('Text') or c.get('Text') or ''
    if not text.strip():
        return
    f = src.get('Font') or c.get('Font') or {}
    style = f.get('Style') or {}
    name = f.get('Name', 'Arial')
    bold = int(bool(style.get('Bold')))
    ital = int(bool(style.get('Italic')))
    px = f.get('PointSize', 12) * PT
    if bold:
        px += opt.get('bold_dpx', 0.0)
    fnt = face(name, bold, ital, px)
    col = rgba(src.get('TextColor')) or rgba(c.get('TextColor')) or (255, 255, 255, 255)
    o = dict(opt)
    o['_fname'] = name
    o['_bold'] = bold
    o['_italic'] = ital
    o['_px'] = px
    if not bold:
        o['bold'] = 'none'
    mode = opt['aa']
    if mode in ('auto', 'autofill'):
        aa = alpha_probe(canvas, x, y, w, h) >= 0.5
        mode = 'L' if aa else ('FILL' if opt['aa'] == 'autofill' else '1')
    align = src.get('TextAlignment', c.get('TextAlignment', 3))
    if mode == 'FILL':
        # GDI bilevel scan conversion fills every pixel the outline touches
        m = Image.new('L', (w, h), 0)
        draw_text(m, (0, 0, w, h), text, fnt, 255, align, o, 'L')
        thr = opt.get('fillthr', 2)
        m = m.point(lambda v: 255 if v >= thr else 0)
        canvas.paste(tuple(col), (x, y), m)
        return
    g = opt.get('aagamma', 1.0)
    if mode == 'L' and g != 1.0:
        m = Image.new('L', (w, h), 0)
        draw_text(m, (0, 0, w, h), text, fnt, 255, align, o, 'L')
        m = m.point(lambda v: int(round(255 * (v / 255.0) ** g)))
        canvas.paste(tuple(col), (x, y), m)
        return
    draw_text(canvas, (x, y, w, h), text, fnt, col, align, o, mode)


def _probe(canvas, x, y, w, h):
    a = np.asarray(canvas.crop((x, y, x + w, y + h)))[:, :, 3]
    return float((a > 128).mean()) if a.size else 0.0


def render_page(pg, assets, size, ox=0, oy=0, canvas=None, draw_txt=True, opt=None):
    opt = dict(OPT, **(opt or {}))
    top = canvas is None
    if canvas is None:
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        fill = rgba(pg.get('BackgroundFillColor'))
        if pg.get('TLPImageID', -1) == -1 and fill and fill[3]:
            canvas.paste(fill, [0, 0, *size])
    paste(canvas, assets, pg.get('TLPImageID'), ox, oy)
    for c in (pg.get('Controls') or []):
        render_control(canvas, c, assets, ox, oy, draw_txt, opt, _probe)
    if top:
        out = Image.new('RGBA', size, (0, 0, 0, 255))
        out.alpha_composite(canvas)
        return out
    return canvas
