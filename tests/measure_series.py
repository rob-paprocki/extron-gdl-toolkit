"""Measure a theme's series templates and seeds for a design system's `panels` table.

    python tests/measure_series.py Afterburn            # the table, as JSON
    python tests/measure_series.py Afterburn --brief    # one line a series

For every panel series of the theme (gdl.templates), it reads:

  * the series template (.glt, through gdl.project): its canvas, its main
    page's background art and how the page draws it (Fill or Stretch), and its
    standard popup region;
  * the kit's background PNG for each of the four themes: the main region is the
    art's opaque body (alpha 255), mapped onto the canvas the way the page draws
    it - no control draws Afterburn's squircle, the background image does;
  * where no art draws one - Mach, Shockwave and Turbulence lay their bars,
    wells and rails as controls over photographs with no alpha - the main region
    and rail off the template's own Main* pages instead (control_regions);
  * every seed of the theme in seeds/ (by part number and canvas - both 300M
    seeds are one part, either way up): which control kinds it
    can clone (a seed with no PBSlider cannot author a slider) and which of the
    profile's border resources it lacks, each mapped to the seed's own of the
    same thickness and nearest radius.

Read only. It takes a few minutes: Pillow on the 9600 px PNGs, gdl.project on
every template and seed. The output is what gdl/designsys/<theme>.json's
`panels` block records; re-run it when Extron's templates or the seeds change.
"""
import collections
import glob
import hashlib
import io
import json
import os
import re
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from gdl import spec, templates  # noqa: E402
from gdl.project import Project  # noqa: E402

KIT_DIRS = [os.path.join(r, '{theme}', 'Backgrounds') for r in spec.RESOURCE_ROOTS]
# ImageLayoutEnum (docs/gdl-format.md section 7)
LAYOUT = {0: 'fill', 1: 'stretch'}
# The kit's four page backgrounds per size, bg1-bg4, and the profile's theme ids.
THEMES = {1: 'default', 2: 'anthracite', 3: 'blue-slate', 4: 'grape'}
# A kit file name: '6400x4000_bg1-default.png', '9600x3600_bg1_default.png',
# '4000x2400_bg1-default_main.png', '1600x2400_bg-anthracite .png' (sic: no
# number, a space), '2400x1600_bg2-anthracyte.png' (sic), '6830x3840_bg3-blurslate.png' (sic).
_KIT = re.compile(r'^(\d+x\d+)_bg(\d?)[-_ ]?([a-z]+)?(?:[-_ ]+(main|start|starrt|left))?\s*\.png$', re.I)
_NUM = {'default': 1, 'anthracite': 2, 'anthracyte': 2, 'blueslate': 3, 'blurslate': 3, 'grape': 4}


def kit_files(theme):
    root = next((d.format(theme=theme) for d in KIT_DIRS if os.path.isdir(d.format(theme=theme))), None)
    out = []
    if not root:
        return root, out
    for f in glob.glob(os.path.join(root, '**', '*.png'), recursive=True):
        m = _KIT.match(os.path.basename(f))
        if not m:
            continue
        word = (m.group(3) or '').lower()
        n = int(m.group(2)) if m.group(2) else _NUM.get(word)
        if not n:
            continue
        variant = {'starrt': 'start'}.get((m.group(4) or '').lower(), (m.group(4) or '').lower())
        rel = os.path.relpath(f, os.path.dirname(os.path.dirname(root))).replace('\\', '/')
        out.append({'path': f, 'rel': rel, 'size': m.group(1), 'n': n, 'variant': variant,
                    'folder': os.path.dirname(os.path.relpath(f, root)).replace('\\', '/')})
    return root, out


# -- backgrounds by theme --------------------------------------------------------------
# Mach's, Shockwave's and Turbulence's kits name their art otherwise -
# '5472x3648_mach-bg-02.png', '1280x800 bkgd.png', 'bkgd_pc.png' - and their
# templates often otherwise again - 'mach_bg_02.png', 'SW_bkgd_01.png' - so a
# file is known by its stem: the name less any size prefix, its separators one.
_SIZED = re.compile(r'^(\d+)x(\d+)[ _-]+(.+)$')


def _stem(name):
    base = os.path.basename(name or '').lower()
    m = _SIZED.match(base)
    return re.sub(r'[ _-]+', '-', m.group(3) if m else base)


def _kit_size(name):
    m = _SIZED.match(os.path.basename(name))
    return (int(m.group(1)), int(m.group(2))) if m else None


def kit_pngs(theme):
    """Every PNG of the theme's kit, relative to its resource root - the paths
    spec.resolve_image takes - the first root's where two have one."""
    out = {}
    for root in spec.RESOURCE_ROOTS:
        for f in glob.glob(os.path.join(root, theme, '**', '*.png'), recursive=True):
            out.setdefault(os.path.relpath(f, root).replace('\\', '/').lower(),
                           os.path.relpath(f, root).replace('\\', '/'))
    return sorted(out.values())


def template_art(p, resource):
    """The PNG a template's image resource holds - System.Drawing.Bitmap's Data
    is the file itself - or None."""
    for r in p.instances('PBImageResource'):
        if p.field(r, 'nameField') == resource:
            data = p.deref((p.field(r, 'dataField') or {}).get('Data'))
            return bytes(data) if data else None
    return None


def _png_size(path):
    with open(path, 'rb') as fh:
        head = fh.read(24)
    return struct.unpack('>II', head[16:24]) if head[:8] == b'\x89PNG\r\n\x1a\n' and len(head) == 24 else None


def own_art(data, files, digests=None):
    """The kit files - {kit path: file on disk} - that hold the PNG `data`'s
    pixels exactly: a template's art, which a seed made from the template
    carries under the template's own name. The applier reuses a seed's image
    only where name and pixels agree (Add-GdlImageResource), so these alone
    may take that name. Only a file of the art's size, read off its PNG header,
    is decoded; `digests` keeps each decoded file's across calls."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    digests = {} if digests is None else digests

    def digest(im):
        return hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest()
    with Image.open(io.BytesIO(data)) as im:
        size, want = im.size, digest(im)
    out = set()
    for k, f in files.items():
        if not f or _png_size(f) != size:
            continue
        if f not in digests:
            with Image.open(f) as im:
                digests[f] = digest(im)
        if digests[f] == want:
            out.add(k)
    return out


def theme_backgrounds(profile, size, resource, kit, own=()):
    """{theme id: {'image', 'file'}} for a series at `size` whose main page draws
    `resource`: each of the profile's themes, as the kit file of the template's
    own art where the kit has it - `own`, the files that are that art pixel for
    pixel (own_art) - else of the theme's art at the series' size, else at the
    nearest shape - of two that shape, the larger - and a theme the kit has no
    art for left out. Only the template's own art takes the template's name,
    which its seed carries with those pixels, so the applier reuses the seed's
    copy; any other file goes by its kit name, and the applier appends it
    unless the seed has that name with those pixels."""
    import math
    w, h = size
    out = {}
    for t in (profile or {}).get('themes', []):
        same = [k for k in kit if _stem(k) == _stem(t.get('file'))]
        if not same:
            continue
        mine = sorted(k for k in same if k in own)
        if mine:
            out[t['id']] = {'image': resource, 'file': mine[0]}
            continue
        sized = [k for k in same if _kit_size(k)]

        def off(k):
            kw, kh = _kit_size(k)
            return (_kit_size(k) != (w, h), abs(math.log((kw / kh) / (w / h))), -kw * kh, k)
        f = min(sized, key=off) if sized else same[0]
        out[t['id']] = {'image': os.path.basename(f), 'file': f}
    return out


def resource_parts(name):
    """A template's background resource name -> (size, bg number, variant)."""
    m = _KIT.match(name or '')
    if not m:
        return None
    word = (m.group(3) or '').lower()
    n = int(m.group(2)) if m.group(2) else _NUM.get(word)
    return m.group(1), n, {'starrt': 'start'}.get((m.group(4) or '').lower(), (m.group(4) or '').lower())


def alpha_box(path):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path).convert('RGBA')
    box = im.split()[3].point(lambda v: 255 if v >= 255 else 0).getbbox()
    return im.size, box


def to_canvas(box, img, canvas, layout):
    """An image box -> canvas px, the way the page draws it: stretch scales each
    axis; fill keeps the aspect and centres."""
    (iw, ih), (cw, ch) = img, canvas
    if layout == 'stretch':
        sx, sy, ox, oy = cw / iw, ch / ih, 0, 0
    else:
        sx = sy = min(cw / iw, ch / ih)
        ox, oy = (cw - iw * sx) / 2, (ch - ih * sy) / 2
    x0, y0, x1, y1 = box
    return [round(ox + x0 * sx), round(oy + y0 * sy), round((x1 - x0) * sx), round((y1 - y0) * sy)]


def art_main(box, img, canvas, layout):
    """The main region the art draws: its opaque body mapped onto the canvas -
    or None where it draws none, having no body or one that is the whole
    picture. Mach's, Shockwave's and Turbulence's photographs are opaque
    throughout and say nothing of where a page's content goes."""
    if not box or tuple(box) == (0, 0, img[0], img[1]):
        return None
    return to_canvas(box, img, canvas, layout)


def main_page(p, pages):
    """The page whose art a working page shows: the most-used background among
    pages named Main*, else among all pages."""
    def bg(pg):
        for o in p.instances('PBPage'):
            if p.kind(o).rsplit('.', 1)[-1] == 'PBPage' and p.field(o, 'nameField') == pg['name']:
                ref = p.field(o, 'backgroundImageField')
                lay = p.field(o, 'backgroundImageLayoutField')
                return ((p.field(ref, 'resourceNameField') if ref else None) or None,
                        LAYOUT.get(lay.get('value__') if isinstance(lay, dict) else lay, 'fill'))
        return (None, 'fill')
    named = [pg for pg in pages if pg['kind'] == 'page' and (pg['name'] or '').startswith('Main')]
    pool = named or [pg for pg in pages if pg['kind'] == 'page']
    counts = collections.Counter(bg(pg) for pg in pool if bg(pg)[0])
    return counts.most_common(1)[0][0] if counts else (None, 'fill')


# -- regions from controls -----------------------------------------------------------
# Mach, Shockwave and Turbulence lay their bars, wells and rails as controls over
# photographs with no alpha, so there is no art body to measure. One rule reads
# them off every theme's template: the themes differ only in which evidence they
# carry - Mach end caps, Shockwave a well and a footer capsule standing off the
# bottom, Turbulence side bars and a popup window filling what they leave, the
# 520 and 535 hubs a side bar and a popup over their title strip. On Afterburn's
# templates its main region's sides come within 13 px of the art's - 25 on the
# 1230's left, where a 160 px column stops short of the squircle - and its top and
# bottom up to 24 px outside, margins only the art draws; so Afterburn keeps its
# art.
#
# Each constant was swept alone over the four themes' series templates. The
# regions held for TOL 3-4 (at 2 the Turbulence 1520's bars, 3 px short of the
# canvas, miss; from 5, Afterburn's labels 5 px off the edge read as touching),
# RUN 0.5-0.999, HUG 0.03-0.14, BARGAP 0.025-0.2, NARROW 0.15-0.4, WELL 0.05-0.5,
# SNAP 0.82-0.98 and CROSS 0.05-0.7.
TOL = 4          # px within which a side touches an edge
RUN = 0.9        # of an edge a bar's controls cover
HUG = 0.03       # of the canvas a loose column or row stands off its edge, at most
BARGAP = 0.05    # of the height a floating bar stands off its edge, at most
NARROW = 0.2     # of the width a side bar or column is, at most
WELL = 0.25      # of the canvas a well covers, at least
SNAP = 0.9       # of the free canvas a popup window covers to be main
CROSS = 0.5      # of the rail's width a bar covers to end the rail
SURFACES = ('PBShape', 'PBImage')


def _inside(a, b):
    return (a[0] >= b[0] - TOL and a[1] >= b[1] - TOL and a[0] + a[2] <= b[0] + b[2] + TOL
            and a[1] + a[3] <= b[1] + b[3] + TOL)


def _inter(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return [x0, y0, x1 - x0, y1 - y0] if x1 > x0 and y1 > y0 else None


def _area(r):
    return r[2] * r[3] if r else 0


def _covered(spans, lo, hi):
    """How much of [lo, hi] the spans cover, bridging gaps of TOL or less."""
    total, cur = 0, None
    for a, b in sorted((max(a, lo), min(b, hi)) for a, b in spans if min(b, hi) > max(a, lo)):
        if cur and a <= cur[1] + TOL:
            cur[1] = max(cur[1], b)
        else:
            total += cur[1] - cur[0] if cur else 0
            cur = [a, b]
    return total + (cur[1] - cur[0] if cur else 0)


def _surface(c):
    # A label with a fill paints as a shape does.
    return c['type'] in SURFACES or (c['type'] == 'PBLabel' and c['fill'])


def page_bands(page, size):
    """One working page's bands: where main's sides are on it - L, R, T, B, or
    0, W, 0, H where no band stands - its standard popup's window, its well,
    and the x-extents of its top and bottom bars' members."""
    W, H = size
    full = lambda r: r[0] <= TOL and r[1] <= TOL and r[0] + r[2] >= W - TOL and r[1] + r[3] >= H - TOL
    # Build adds a full-canvas reference per modal popup; the others place the
    # page's popups, and the largest is the standard popup's window.
    refs = [c['rect'] for c in page['controls'] if c['type'] == 'PBPopupPageReference' and not full(c['rect'])]
    ctl = [c for c in page['controls'] if c['type'] != 'PBPopupPageReference']
    window = max(refs, key=_area) if refs else None
    # Side bars: tall, narrow surfaces on a side (Turbulence, the hubs' menus).
    bars = {'left': [], 'right': []}
    for c in ctl:
        x, _, w, h = c['rect']
        if _surface(c) and h >= H / 2 and w <= NARROW * W:
            if x <= TOL:
                bars['left'].append(c['rect'])
            elif x + w >= W - TOL:
                bars['right'].append(c['rect'])
    lo = max([r[0] + r[2] for r in bars['left']] or [0])
    hi = min([r[0] for r in bars['right']] or [W])
    in_bar = lambda r: any(_inside(r, b) for b in bars['left'] + bars['right'])
    # Top and bottom bars: the controls on the edge, covering it between the
    # side bars - a header of shapes and source tabs counts as one.
    edges = {}
    for edge in ('top', 'bottom'):
        gap = (lambda r: r[1]) if edge == 'top' else (lambda r: H - (r[1] + r[3]))
        members = [c['rect'] for c in ctl if c['rect'][3] < H / 2 and not in_bar(c['rect']) and gap(c['rect']) <= TOL]
        depth = None
        if members and _covered([(r[0], r[0] + r[2]) for r in members], lo, hi) >= RUN * (hi - lo):
            depth = max(r[1] + r[3] for r in members) if edge == 'top' else min(r[1] for r in members)
        else:
            # A bar standing a little off the edge: Shockwave's footer capsule.
            # Its band runs from it to the edge and holds what lies there.
            floating = [c['rect'] for c in ctl if _surface(c) and c['rect'][2] >= W / 2 and c['rect'][3] < H / 2
                        and TOL < gap(c['rect']) <= BARGAP * H]
            if floating:
                depth = max(r[1] + r[3] for r in floating) if edge == 'top' else min(r[1] for r in floating)
                members = [c['rect'] for c in ctl if not in_bar(c['rect']) and (
                    c['rect'][1] + c['rect'][3] <= depth + TOL if edge == 'top' else c['rect'][1] >= depth - TOL)]
        if depth is None:
            continue
        band = [lo, 0, hi - lo, depth] if edge == 'top' else [lo, depth, hi - lo, H - depth]
        # A bar the page's own standard popup is placed over is main, not
        # chrome: the hubs' title strips.
        if window and _area(_inter(window, band)) >= 0.5 * _area(band):
            continue
        edges[edge] = {'depth': depth, 'members': members}
    member = [r for e in edges.values() for r in e['members']]
    loose = [c['rect'] for c in ctl if c['rect'] not in member]
    # Side bands: a side bar; else the narrowest end cap of a bar (Mach's footer
    # buttons are as wide as its columns' bands); else controls flush with the
    # side; else a column standing a little off it, centred in its band.
    side = {}
    for s in ('left', 'right'):
        if bars[s]:
            side[s] = lo if s == 'left' else hi
            continue
        near = (lambda r: r[0]) if s == 'left' else (lambda r: W - (r[0] + r[2]))
        caps = [r for r in member if near(r) <= TOL and r[2] < W / 2
                and not any(o != r and _inside(r, o) for o in member)]
        flush = [r for r in loose if near(r) <= TOL and r[2] <= NARROW * W]
        column = [r for r in loose if near(r) <= HUG * W and r[2] <= NARROW * W]
        if caps:
            side[s] = min(r[0] + r[2] for r in caps) if s == 'left' else max(r[0] for r in caps)
        elif flush:
            side[s] = max(r[0] + r[2] for r in flush) if s == 'left' else min(r[0] for r in flush)
        elif column:
            m = min(near(r) for r in column)
            side[s] = max(r[0] + r[2] for r in column) + m if s == 'left' else min(r[0] for r in column) - m
        else:
            side[s] = 0 if s == 'left' else W
    top = edges['top']['depth'] if 'top' in edges else 0
    bottom = edges['bottom']['depth'] if 'bottom' in edges else H
    # A row of controls hugging the bottom where nothing stands beside main: the
    # tier C panels' rail.
    if 'bottom' not in edges and side['right'] >= W:
        row = [r for r in loose if H - (r[1] + r[3]) <= HUG * H and r[3] <= NARROW * H]
        if row:
            bottom = min(r[1] for r in row) - min(H - (r[1] + r[3]) for r in row)
    # A well: a shape inside the canvas covering a quarter of it (Shockwave).
    wells = [c['rect'] for c in ctl if c['type'] == 'PBShape' and c['rect'][0] > TOL and c['rect'][1] > TOL
             and c['rect'][0] + c['rect'][2] < W - TOL and c['rect'][1] + c['rect'][3] < H - TOL
             and _area(c['rect']) >= WELL * W * H]
    return {'L': side['left'], 'R': side['right'], 'T': top, 'B': bottom, 'window': window,
            'well': max(wells, key=_area) if wells else None,
            'spans': {e: [(r[0], r[0] + r[2]) for r in v['members']] for e, v in edges.items()}}


def _mode(values, prefer):
    counts = collections.Counter(values)
    most = max(counts.values())
    return prefer(v for v, n in counts.items() if n == most)


def control_regions(pages, size):
    """{'main', 'rail', 'rail_axis'} off a series' pages, as gdl.project's
    Project.pages() yields them: each working page's bands (page_bands), the
    most common across them."""
    W, H = size
    named = [pg for pg in pages if pg['name']]
    work = ([pg for pg in named if pg['kind'] == 'page' and pg['name'].startswith('Main')]
            or [pg for pg in named if pg['kind'] == 'page'])
    facts = [page_bands(pg, size) for pg in work]
    if not facts:
        return {'main': [0, 0, W, H], 'rail': None, 'rail_axis': None}
    # A tie goes to more chrome: a page's band is never less than drawn.
    L = _mode([f['L'] for f in facts], max)
    R = _mode([f['R'] for f in facts], min)
    T = _mode([f['T'] for f in facts], max)
    B = _mode([f['B'] for f in facts], min)
    free = [L, T, R - L, B - T]
    main = free
    wells = collections.Counter(tuple(f['well']) for f in facts if f['well'])
    windows = collections.Counter(tuple(f['window']) for f in facts if f['window'])
    if wells and wells.most_common(1)[0][1] >= 0.5 * len(facts):
        main = list(wells.most_common(1)[0][0])
    elif windows:
        # A popup window filling the free canvas is main (Turbulence's sit a few
        # px inside its bars); one that leaves a fifth of it is not (Mach's).
        snap = _inter(list(windows.most_common(1)[0][0]), free)
        if snap and _area(snap) >= SNAP * _area(free):
            main = snap
    # The rail starts at the right band where that is past main's edge (a
    # window inside its bars), and runs between the bars that cross it.
    right = max(main[0] + main[2], R) if R < W else main[0] + main[2]
    bottom = max(main[1] + main[3], B) if B < H else main[1] + main[3]
    if right < W - TOL:
        def crosses(edge):
            hits = sum(1 for f in facts if f['spans'].get(edge)
                       and _covered(f['spans'][edge], right, W) >= CROSS * (W - right))
            return hits >= 0.5 * len(facts)
        y0 = T if T and crosses('top') else 0
        y1 = B if B < H and crosses('bottom') else H
        return {'main': main, 'rail': [right, y0, W - right, y1 - y0], 'rail_axis': 'column'}
    if bottom < H - TOL:
        return {'main': main, 'rail': [0, bottom, W, H - bottom], 'rail_axis': 'row'}
    return {'main': main, 'rail': None, 'rail_axis': None}


def regions(pages, size, art=None):
    """{'main', 'rail', 'rail_axis'}: the art's main region, with the rail what
    the canvas leaves beside it - right of it where there is room, else below -
    where the art draws one (Afterburn); else the controls' (control_regions)."""
    if not art:
        return control_regions(pages, size)
    w, h = size
    right, bottom = art[0] + art[2], art[1] + art[3]
    if right < w - 1:
        return {'main': art, 'rail': [right, 0, w - right, h], 'rail_axis': 'column'}
    if bottom < h - 1:
        return {'main': art, 'rail': [0, bottom, w, h - bottom], 'rail_axis': 'row'}
    return {'main': art, 'rail': None, 'rail_axis': None}


def popup_region(pages, size):
    """The template's standard popup region, [w, h]: its largest named non-modal
    popup, where that fills a quarter of the canvas or more."""
    w, h = size
    popups = sorted((tuple(pg['size']) for pg in pages if pg['name'] and pg['kind'] == 'popup' and not pg['modal']),
                    key=lambda s: s[0] * s[1])
    big = popups[-1] if popups else None
    return list(big) if big and big[0] * big[1] >= 0.25 * w * h else None


def seed_facts(path, border_names):
    p = Project.open(path)
    kinds = collections.Counter(p.kind(o).rsplit('.', 1)[-1] for o in p.o.values()
                                if isinstance(o, dict) and '__class' in o)
    std = any(pg['kind'] == 'popup' and not pg['modal'] and pg['name'] for pg in p.pages())
    have = set(p.border_resources())
    part = None
    for o in p.instances('PBProject'):
        plat = p.field(o, 'platformField')
        part = p.field(plat, 'partNumberField') if plat else None
    borders = {}
    for name, res in border_names.items():
        if not res or res in have or not res.startswith(('Afterburn - ', 'Mach - ', 'Shockwave - ', 'Turbulence - ')):
            continue
        want = _radius_thick(res)
        same = [r for r in have if _radius_thick(r) and want and _radius_thick(r)[1] == want[1]]
        if same:
            borders[name] = min(same, key=lambda r: abs(_radius_thick(r)[0] - want[0]))
    # Its canvas, as its pages are: both 300M seeds are one part number, and
    # only the canvas says which series each is.
    canvas = collections.Counter(tuple(pg['size']) for pg in p.pages()
                                 if pg['kind'] == 'page' and pg.get('size'))
    return {'part': part, 'size': list(canvas.most_common(1)[0][0]) if canvas else None,
            'slider': kinds['PBSlider'] > 0, 'level': kinds['PBLevel'] > 0,
            'datetime': kinds['PBDateTime'] > 0, 'popup': std, 'borders': borders}


def _radius_thick(resource):
    m = re.search(r'(\d+) Radius (\d+) Thick', resource or '')
    return (int(m.group(1)), int(m.group(2))) if m else None


def match_seeds(theme, models, size, seeds):
    """({model or panel: seed}, kinds, borders) of the series at `size` that
    serves `models`, from `seeds` ({path: seed_facts()}).

    A seed is a model's by part number and canvas - both 300M seeds are one
    part, either way up. One at the model's other way up, where the theme draws
    no template that way, is its own turned (New-GdlTurnedSeed.ps1) and is the
    panel's (gdl.spec.panel_id), the 1035M portrait's under TLP1035M-Portrait.
    Kinds and borders are what the series' own seed can clone, else a turned
    one's: a retarget changes neither."""
    out, kinds, borders = {}, None, None
    for turned in (False, True):
        for sp, facts in seeds.items():
            for m in models:
                if not facts['part'] or spec.part_number(m) != facts['part']:
                    continue
                at = tuple(facts['size'])
                if not turned and at == tuple(size):
                    out[m] = sp
                elif turned and at != tuple(size) and at in spec.sizes(m) \
                        and not templates.template_for(theme, m, at):
                    out[spec.panel_id(m, at)] = sp
                else:
                    continue
                if not turned or kinds is None:
                    kinds = {k: facts[k] for k in ('slider', 'level', 'datetime', 'popup')}
                    borders = facts['borders']
    return out, kinds, borders


def measure(theme, profile=None):
    _, kit = kit_files(theme)
    borders = {k: v.get('resource') for k, v in (profile or {}).get('borders', {}).items()}
    seeds = {}
    for f in sorted(glob.glob(os.path.join(REPO, 'seeds', f'{theme} *.gdl'))):
        with open(f, 'rb') as fh:
            if fh.read(40).startswith(b'version https://git-lfs'):
                continue
        seeds[os.path.relpath(f, REPO).replace('\\', '/')] = seed_facts(f, borders)
    out, pngs, digests = {}, None, {}
    for row in templates.series(theme):
        path = os.path.join(os.path.dirname(templates._default_path() or ''), row['file'])
        p = Project.open(path)
        pages = [pg for pg in p.pages() if pg['name']]
        w, h = row['size']
        resource, layout = main_page(p, pages)
        parts = resource_parts(resource)
        entry = {'size': [w, h], 'dpi': round(row['dpi'], 2), 'tier': templates._tier(row),
                 'fit': layout, 'models': [], 'backgrounds': {}}
        if parts:
            size, _, variant = parts
            for n, tid in THEMES.items():
                cands = sorted((k for k in kit if k['size'] == size and k['n'] == n
                                and k['variant'] == variant), key=lambda k: ('Other' in k['folder'], k['rel']))
                if cands:
                    entry['backgrounds'][tid] = {
                        'image': resource if n == 1 else os.path.basename(cands[0]['path']).replace(' .png', '.png'),
                        'file': cands[0]['rel']}
            first = entry['backgrounds'].get('default')
            if first:
                img, box = alpha_box(os.path.join(os.path.dirname(os.path.dirname(kit_files(theme)[0])), first['file']))
                drawn = art_main(box, img, (w, h), layout)
                if drawn:
                    entry['main'] = drawn
        elif resource:
            # Not Afterburn's kit art: a background for each of the profile's
            # themes by its art's own name, and no region read off it.
            if pngs is None:
                pngs = kit_pngs(theme)
            art = template_art(p, resource)
            own = own_art(art, {k: spec.resolve_image(k) for k in pngs}, digests) if art else set()
            entry['backgrounds'] = theme_backgrounds(profile, (w, h), resource, pngs, own)
        entry.update(regions(pages, (w, h), entry.get('main')))
        entry['popup'] = popup_region(pages, (w, h))
        # Every model the series serves, either way up of one that rotates:
        # Afterburn's 300 Landscape series is the 300M's, turned.
        for m in sorted(spec.MODELS_FULL):
            if any((templates.template_for(theme, m, s) or {}).get('series') == row['series']
                   for s in spec.sizes(m)):
                entry['models'].append(m)
        entry['seeds'], kinds, borders = match_seeds(theme, entry['models'], (w, h), seeds)
        if kinds is not None:
            entry['kinds'], entry['borders'] = kinds, borders
        out[row['series']] = entry
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    theme = argv[1]
    prof = os.path.join(REPO, 'gdl', 'designsys', theme.lower() + '.json')
    profile = json.load(open(prof, encoding='utf-8')) if os.path.exists(prof) else None
    table = measure(theme, profile)
    if '--brief' in argv:
        for k, v in table.items():
            print(f"{k:<32} {v['size']} tier {v['tier']} {v['fit']:<7} main {v.get('main')} "
                  f"rail {v['rail']} popup {v['popup']} seeds {sorted(set(v['seeds'].values()))}")
        return 0
    print(json.dumps(table, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
