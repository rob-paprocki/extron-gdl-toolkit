"""Measure a theme's series templates and seeds for a design system's `panels` table.

    python tests/measure_series.py Afterburn            # the table, as JSON
    python tests/measure_series.py Afterburn --brief    # one line a series
    python tests/measure_series.py Afterburn --frame    # each series' frame, as JSON

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
    can clone (a seed with no PBSlider cannot author a slider), which of the
    profile's border resources it lacks, each mapped to the seed's own of the
    same thickness and nearest radius, and the corner it rounds a profile
    border at where that is not the profile's (`radii`, seed_radii);
  * with --frame, each series' own seed's working page in the template's own
    grammar (frame_of): its five bands, their surfaces and their slots by
    meaning, and the windows it opens - the profile's per-series `frame`
    (docs/claude-design.md section 2, *Frame*).

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


# -- the frame: a series' working page in its template's own grammar ----------------
# Every bar theme's working page is one grammar (docs/superpowers/specs/
# 2026-10-22-region-frame-design.md): a header of source tabs, a left rail of
# titled groups, a right rail of volume, a footer of a mode launcher, the clock,
# Help and Power, and a centre the selected source's popup fills. The hubs keep
# only a right menu bar and fill main with popups; the 320 gives each source a
# page of its own under a title strip. frame_of reads that off the seed - the
# series' template, built - so a page can be placed as the panel's own template
# places it, the 725's from the 725's seed, not the 1035's scaled.
BANDS = ('top', 'left', 'right', 'bottom', 'center')
# The fixed chrome whose seed IDs a page keeps: one ID per control, on every page
# and every panel of a theme (Help 8117, Power 8022 on the bar themes' seeds).
CHROME = ('help', 'power', 'volume', 'mute', 'mode', 'volume-up', 'volume-down', 'settings')
# A control's meaning off its name: the seeds name their chrome alike across
# themes ('Volume Mute', 'Power Down', 'Room Mode'), and the first rule whose
# words all appear wins - Display Power is the display's, not the room's, and
# the 1230's video Full Screen is not the projection screen's launcher.
ROLES = ((('display', 'on'), 'display-on'), (('display', 'off'), 'display-off'),
         (('display', 'mute'), 'display-mute'), (('display', 'power'), 'display-power'),
         (('display',), 'display'), (('volume', 'up'), 'volume-up'), (('volume', 'down'), 'volume-down'),
         # The call mode's (Main VC's Initiate Call, End Call, VC Privacy and
         # Share Content; Incoming Call's Accept Call and Decline or Ignore
         # Call; the dialer's VC Call): an ending or an answer before the call
         # it names.
         (('end', 'call'), 'end-call'), (('accept',), 'accept'), (('decline',), 'decline'),
         (('ignore',), 'decline'), (('privacy',), 'privacy'), (('share',), 'share'), (('call',), 'call'),
         (('mute',), 'mute'), (('help',), 'help'), (('power',), 'power'), (('room', 'mode'), 'mode'),
         # Afterburn's foot-left launcher goes to the call's page as Mach's Room
         # Mode goes to its mode page.
         (('video', 'conference'), 'mode'), (('lighting',), 'lighting'), (('audio',), 'audio'),
         (('full', 'screen'), 'fullscreen'), (('screen',), 'screen'), (('settings',), 'settings'),
         (('more',), 'more'), (('back',), 'back'), (('close',), 'close'), (('cancel',), 'cancel'),
         (('preview',), 'preview'),
         # A hub's or a 300's own source tiles: 'Main Laptop', 'Main Computer'.
         (('main',), 'source'))
_KIND_ROLE = {'PBDateTime': 'clock', 'PBSlider': 'volume', 'PBLevel': 'level', 'PBLine': 'divider',
              'PBShape': 'surface', 'PBImage': 'surface', 'PBPopupPageReference': 'popup', 'PBLabel': 'heading'}
# A control's kind in gdl.spec's words (KIND_TYPE): what a placement draws it
# as, and whether it has a touch target to meet (spec.TOUCHABLE).
KINDS = {t: k for k, t in spec.KIND_TYPE.items() if k != 'panel'}
# The source popup whose well, title and empty state the centre records: the
# first of these a seed has (Shockwave's Laptop says 'Please connect your
# laptop.', its empty state; Mach's 'There are no controls for this device.').
EMPTY_SOURCES = ('Laptop', 'PC', 'Aux', 'AUX')
# The source popup with controls whose title the centre records too
# (`title_controls`): the Doc Cam, as every template has one.
CONTROL_SOURCES = ('Doc Cam',)
# The windows every theme opens over a working page, by the popup's name - or
# the page's, on the 300 and the 320, which flip pages for them.
WINDOWS = (('help', 'Help'), ('confirm', 'Confirmation'), ('wait', 'Powering Down'))
# The call mode, where a bar series' template draws one: its working page
# (Main VC - the header's tabs and Share Content at its end, the left rail's
# VTC group of Make Call, End Call and Privacy over its launchers), the
# dialer its popup region shows (VTC Dialer), and the question the program
# shows when a call comes in - 'Incoming Call', which Turbulence's 1035
# names 'Incoming Call Label'.
CALL_PAGE = 'Main VC'
DIALER = 'VTC Dialer'
INCOMING = ('Incoming Call', 'Incoming Call Label')
# The call mode's chrome a program drives, whose seed IDs the call page
# keeps (Initiate Call 5014, End Call 5215, VC Privacy 5217, Share Content
# 8090 on every bar seed).
CALL_CHROME = ('call', 'end-call', 'privacy', 'share')
# The page a bar series chooses among its sources on, with nothing chosen
# yet - Mach's and Turbulence's, which Shockwave's bar templates do not draw:
# a title in the header and the sources as tiles in the centre.
SELECT_PAGE = 'Main Select Source'
# The number the program writes into a dialer's entry, on every seed.
ENTRY_ID = 50000
# The page an Afterburn bar series draws three rail groups on (Display,
# Screen, Settings), whose seams say how a third group stacks.
THREE_GROUPS = 'Main SD Screen Arrows'
# The cells an Afterburn working page stands along the screen's foot, across
# its three bands (`foot`): the mode launcher, the clocks, Preview, Help and
# Power - the row a bar theme's Footer draws.
FOOT_ROLES = ('mode', 'clock', 'preview', 'help', 'power')


def series_seed(row):
    """The seed a series' own models are built on (its `seeds`, by model; a
    turned panel's own turned seed is not the series'), the commonest where
    its models have several - the 1220's 1035 over its 835."""
    own = [v for k, v in sorted((row.get('seeds') or {}).items()) if k in row.get('models', [])]
    return collections.Counter(own).most_common(1)[0][0] if own else None


def frame_art(profile, row):
    """The main region Afterburn's art draws, which its frame's bands stand
    around: a profile whose bars are not controls (layout.bars) draws its
    chrome as background art, and the series' main is that art's body."""
    return None if (profile.get('layout') or {}).get('bars') == 'controls' else row.get('main')


def _res(p, obj, field):
    ref = p.field(obj, field)
    return (p.field(ref, 'resourceNameField') or None) if isinstance(ref, dict) else None


def _hex(c, transparency=0):
    # A control's transparency fades all it draws (docs/gdl-format.md), so the
    # fill a band shows is the color's alpha less that percent.
    if not c:
        return None
    a = round(c['A'] * (100 - (transparency or 0)) / 100)
    return '#%02X%02X%02X%02X' % (c['R'], c['G'], c['B'], a)


def _num(v):
    """A point size as GUI Designer stores it (20.0), as the profiles write one (20)."""
    return int(v) if isinstance(v, float) and v.is_integer() else v


def _lines(c):
    """How many lines a label's words take in its box in its own face and
    size, as GUI Designer breaks them (gdl.compose.wrap, at 1.375 px a point):
    Turbulence's power-down question is one line in Open Sans Light on the
    1035 and two on the 725 - and two on the 1035 in the system's Open Sans,
    a little wider. None where the face is not here to measure."""
    from gdl import data, fonts, sfnt
    from gdl.compose import wrap
    path = fonts.face_path(c['face'] or '', 1 if c['bold'] else 0) or fonts.face_path(c['face'] or '')
    if not path or not c['caption'] or not c['pt']:
        return None
    adv, px = sfnt.Advances(path), c['pt'] * data.PT_TO_PX
    return len(wrap(c['caption'], None, c['rect'][2], lambda s, _: adv.length(s, px)))


def seed_pages(p):
    """Project.pages(), each control with what a frame reads that pages()
    leaves out: its fill after its transparency, its art (an image's picture,
    a button's own) and each state's fill, border, art and caption color; and
    each page with its background art and how it draws it."""
    proj = next(p.instances('PBProject'), None)
    raw = [(pg, kind) for f, kind in (('pagesField', 'page'), ('popupPagesField', 'popup'))
           for pg in p.items(p.field(proj, f))] if proj is not None else []
    out = []
    for pg, kind in raw:
        page = p._page(pg, kind)
        lay = p.field(pg, 'backgroundImageLayoutField')
        page['background'] = _res(p, pg, 'backgroundImageField')
        # Its own fill, which a popup that draws no shape shows (a hub's
        # Volume Level strip).
        page['paint'] = _hex(p.color(p.field(pg, 'borderFillColorField')), p.field(pg, 'transparencyField'))
        page['layout'] = LAYOUT.get(lay.get('value__') if isinstance(lay, dict) else lay, 'fill')
        for c, obj in zip(page['controls'], p.items(p.field(pg, 'controlsField'))):
            c['rect'] = list(c['rect'])
            c['paint'] = _hex(p.color(p.field(obj, 'borderFillColorField')), p.field(obj, 'transparencyField'))
            c['art'] = _res(p, obj, 'backgroundImageField') or _res(p, obj, 'buttonImageField')
            # Its face and size, which a label the centre or a window draws
            # keeps per series: the 725 sets its titles 20 pt to the 1035's 24.
            font = p.field(obj, 'fontField')
            style = p.field(font, 'styleField') if font else None
            c['face'] = p.field(font, 'nameField') if font else None
            c['bold'] = bool(p.field(style, 'boldField')) if style else False
            c['pt'] = _num(p.field(font, 'pointSizeField')) if font else None
            # A caption color reads None where it is fully transparent: a
            # Shockwave tab's own caption, which its twin draws instead.
            # A level's filled part: a color (gaugeFillType 0, Mach's) or
            # art over its empty track's (1, Shockwave's and Turbulence's).
            if c['type'] == 'PBLevel':
                kind_ = p.field(obj, 'gaugeFillTypeField')
                c['gauge'] = {'art': (kind_.get('value__') if isinstance(kind_, dict) else kind_) == 1,
                              'fill': _hex(p.color(p.field(obj, 'gaugeFillColorField'))),
                              'fill_image': _res(p, obj, 'gaugeFillImageField'),
                              'track_image': _res(p, obj, 'backgroundImageField')}
            c['looks'] = [{'fill': _hex(p.color(p.field(s, 'borderFillColorField')), p.field(s, 'transparencyField')),
                           'border': (p.border(s) or {}).get('resource'),
                           'art': _res(p, s, 'buttonImageField') or _res(p, s, 'backgroundImageField'),
                           'text': _hex(p.color(p.field(s, 'textColorField')), p.field(s, 'transparencyField'))}
                          for s in p.states(obj)]
        out.append(page)
    return out


def page_art(p, page, size):
    """The main region a page's own background art draws (art_main) - the 300
    Landscape's source pages draw their column on the left, its Main on the
    right - read off the PNG the seed carries under the art's name."""
    data = template_art(p, page.get('background')) if page.get('background') else None
    if not data:
        return None
    img, box = alpha_box(io.BytesIO(data))
    return art_main(box, img, size, page.get('layout') or 'fill')


def _role(c):
    words = re.findall(r'[a-z]+', (c['name'] or '').lower())
    if c['type'] == 'PBButton':
        # A window's Close is named for it - 'Close Help', 'Close Display
        # Control' - and is a Close whatever it names; a doc camera's Iris
        # Close is not. A Back is named for its page: 'Help Back', 'Page Back'.
        if words[:1] == ['close']:
            return 'close'
        if words[-1:] == ['back']:
            return 'back'
        for need, role in ROLES:
            if all(w in words for w in need):
                return role
        return '-'.join(words) or 'button'
    return _KIND_ROLE.get(c['type'], c['type'][2:].lower())


def _item(c, at=(0, 0), role=None):
    it = {'role': role or _role(c), 'name': c['name'], 'kind': KINDS.get(c['type'], c['type'][2:].lower()),
          'rect': _offset(c['rect'], at)}
    if c['id']:
        it['id'] = c['id']
    if c['type'] == 'PBLabel' and c['caption']:
        it['text'] = c['caption']
    return it


def _surface_of(c, at=(0, 0), popup=None):
    kind = {'PBShape': 'shape', 'PBImage': 'image', 'PBLine': 'line'}.get(c['type'], 'label')
    out = {'name': c['name'], 'rect': _offset(c['rect'], at), 'kind': kind, 'fill': c['paint'],
           'border': (c['border'] or {}).get('resource'), 'art': c['art']}
    if popup:
        out['popup'] = popup
    return out


def _offset(r, at):
    return None if r is None else [r[0] + at[0], r[1] + at[1], r[2], r[3]]


def _bbox(rects):
    rects = [r for r in rects if r]
    if not rects:
        return None
    x0, y0 = min(r[0] for r in rects), min(r[1] for r in rects)
    return [x0, y0, max(r[0] + r[2] for r in rects) - x0, max(r[1] + r[3] for r in rects) - y0]


def _centre_in(r, band):
    cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
    return band and band[0] <= cx < band[0] + band[2] and band[1] <= cy < band[1] + band[3]


def _pitch(values):
    steps = [b - a for a, b in zip(values, values[1:])]
    return _mode(steps, max) if steps else None


def _look(c):
    names = ('off', 'on')
    return {names[i]: s for i, s in enumerate(c['looks'][:2])}


def _tabs(buttons):
    """The source tabs: the longest row of like buttons - one size, one top -
    each with its own rect, since Extron's steps are uneven (the Turbulence
    1220's run 141, 141, 140, 142, 141) and `pitch` is only the commonest; and
    a twin row sharing their IDs: Shockwave's tab names, caption-only buttons
    under the tabs, whose own captions are not drawn."""
    rows = collections.defaultdict(list)
    for c in buttons:
        rows[(c['rect'][1], c['rect'][2], c['rect'][3])].append(c)
    best = max(rows.values(), key=lambda cs: (len(cs), cs[0]['rect'][3]), default=[])
    if len(best) < 2:
        return None, []
    best.sort(key=lambda c: c['rect'][0])
    ids = {c['id'] for c in best if c['id']}
    twins = sorted((c for c in buttons if c not in best and c['id'] in ids), key=lambda c: c['rect'][0])
    out = {'first': list(best[0]['rect']), 'pitch': _pitch([c['rect'][0] for c in best]), 'count': len(best),
           'look': _look(best[0]), 'items': [_item(c, role='source') for c in best]}
    if twins:
        out['twin'] = {'look': _look(twins[0]), 'items': [_item(c, role='caption') for c in twins]}
    return out, best + twins


def _groups(cs):
    """A rail's groups, down it: each heading and the run of like buttons under
    it, a run of two or more with no heading a group of its own (Shockwave's
    launchers); what is in no group is left over."""
    cs = sorted(cs, key=lambda c: (c['rect'][1], c['rect'][0]))
    groups, rest, cur = [], [], None
    for c in cs:
        if c['type'] == 'PBLabel':
            cur = {'heading': {'rect': list(c['rect']), 'text': c['caption']}, 'buttons': []}
            groups.append(cur)
            continue
        if c['type'] != 'PBButton':
            rest.append(c)
            continue
        if cur is not None and cur['buttons'] and tuple(cur['_size']) != tuple(c['rect'][2:]):
            cur = None
        if cur is None:
            cur = {'heading': None, 'buttons': []}
            groups.append(cur)
        cur.setdefault('_size', c['rect'][2:])
        cur['buttons'].append(c)
    out = []
    for g in groups:
        if g['heading'] is None and len(g['buttons']) < 2:
            rest += g['buttons']
            continue
        out.append({'heading': g['heading'], 'buttons': [_item(b) for b in g['buttons']],
                    'pitch': _pitch([b['rect'][1] for b in g['buttons']])})
    return out, rest


def _source_popup(pages):
    pops = {pg['name']: pg for pg in pages if pg['kind'] == 'popup' and not pg['modal'] and pg['name']}
    return next((pops[n] for n in EMPTY_SOURCES if n in pops), None)


def _controls_title(pages, at):
    """The title of a source's popup that has controls (CONTROL_SOURCES), on
    the page at `at`, or None: Turbulence titles its Doc Cam at the popup's
    top, where its Laptop's sits 40 px lower over the empty state."""
    pops = {pg['name']: pg for pg in pages if pg['kind'] == 'popup' and not pg['modal'] and pg['name']}
    pg = next((pops[n] for n in CONTROL_SOURCES if n in pops), None)
    title = _title_of(pg) if pg else None
    return _offset(title['rect'], at) if title else None


def _centre_from(popup, at):
    """A source popup's well (its shapes), title (the label naming it), empty
    state (its other labels) and Close, on the page at `at`; and every surface
    it draws, marked with its name - Mach's well is two shapes, the title bar
    and the body 1 px under it, and a hub's popup draws its own header strip."""
    if popup is None:
        return {}, []
    cs = popup['controls']
    labels = [c for c in cs if c['type'] == 'PBLabel']
    title = next((c for c in labels if (c['caption'] or '').strip().lower() == popup['name'].lower()), None)
    # The well is the popup's shapes, but not a hub popup's header strip,
    # across its whole top.
    W = popup['size'][0]
    shapes = [c['rect'] for c in cs if c['type'] == 'PBShape'
              and not (c['rect'][1] <= TOL and c['rect'][0] <= TOL and c['rect'][2] >= W - TOL)]
    closer = [c for c in cs if c['type'] == 'PBButton' and _role(c) in ('close', 'back')]
    said = sorted((c for c in labels if c is not title), key=lambda c: (c['rect'][1], c['rect'][0]))
    out = {'popup': popup['name'], 'well': _offset(_bbox(shapes), at),
           'title': _offset(title['rect'], at) if title else None,
           'empty': _offset(_bbox([c['rect'] for c in said]), at)}
    # Its sizes on this series, and under the empty state's request a status
    # the program sets: Shockwave's 'Disconnected' under 'Please connect your
    # laptop.'.
    pt = {'title': title['pt'] if title else None, 'empty': said[0]['pt'] if said else None}
    if len(said) == 2 and said[1]['rect'][1] >= said[0]['rect'][1] + said[0]['rect'][3]:
        out['status'] = _offset(said[1]['rect'], at)
        pt['status'] = said[1]['pt']
    out['pt'] = {k: v for k, v in pt.items() if v is not None}
    if closer:
        out['close'] = _item(closer[0], at)
    return out, [_surface_of(c, at, popup['name']) for c in sorted(cs, key=lambda c: (c['rect'][1], c['rect'][0]))
                 if _surface(c)]


def _pictures(page, pages, at, drawn):
    """{device: rect} - the picture each source's popup pins, on the page at
    `at`, by the device its art names (1152x1152_doc-cam.png is the kit's
    doc-cam: a plain picture, its stem its family). Turbulence sizes each
    device its own way - the 1035's Doc Cam 326x288 and Tuner 526x329 where
    its Laptop is 293x257 - so the measured popup's own picture (in `drawn`,
    its surfaces: the Laptop's) is no other's. Only pictures named at that
    one's size, so a template that pins none (Mach, Shockwave) records none.

    A popup the working page's buttons open, or one those open, is a
    setting's - the 525's Display Control, and More Options' Audio and
    Lighting Control, standard popups on a hub where its bar series' are
    modals - and the device it pictures is no source's, wherever else it is
    drawn: Dual Display Select, the 525's Blu-ray routing step, pictures
    the monitor its Display Control does."""
    own = next((s['art'] for s in drawn if s['kind'] == 'image' and s['art']), None)
    size = re.match(r'^(\d+x\d+)_', own or '')
    if not size:
        return {}
    art = re.compile('^' + re.escape(size.group(1)) + r'_(.+)\.png$')
    std = [pg for pg in pages if pg['kind'] == 'popup' and not pg['modal'] and pg['name']]

    def opened(cs):
        return [pg for pg in (_windows_named(std, c['name']) for c in cs if c['type'] == 'PBButton' and c['name'])
                if pg]

    def devices(pg):
        return [(m.group(1), c) for c in pg['controls'] if c['type'] == 'PBImage'
                for m in [art.match(c['art'] or '')] if m]
    settings = opened(page['controls'])
    settings += [pg for s in list(settings) for pg in opened(s['controls']) if pg not in settings]
    theirs = {d for pg in settings for d, _ in devices(pg)}
    out = {}
    for pg in std:
        for d, c in devices(pg) if pg not in settings else ():
            if d not in theirs:
                out.setdefault(d, _offset(c['rect'], at))
    return dict(sorted(out.items()))


def _band(rect, cs, surfaces):
    return {'rect': rect, 'surfaces': [_surface_of(c) for c in surfaces],
            'items': [_item(c) for c in sorted(cs, key=lambda c: (c['rect'][1], c['rect'][0]))]}


def _snap(band, surfaces):
    """A band its own art covers is that art: Turbulence's footer image
    stops a px short of the right bar and two of the screen's foot, its 1520
    right bar three short of the screen's edge. Shockwave's footer capsule,
    20 px off the foot, is a surface in its band, not the band."""
    for c in surfaces:
        both = _area(_inter(c['rect'], band))
        if both >= 0.95 * _area(band) and both >= 0.95 * _area(c['rect']):
            return list(c['rect'])
    return band


def _ids(frame_items, popups):
    ids = {}
    for it in frame_items:
        if it['role'] in CHROME and it.get('id') and it['role'] not in ids:
            ids[it['role']] = it['id']
    # A hub's Help is on its Select a Source popup, not its menu bar.
    for pg in popups:
        for c in pg['controls']:
            r = _role(c)
            if c['type'] == 'PBButton' and r in CHROME and c['id'] and r not in ids:
                ids[r] = c['id']
    return {k: ids[k] for k in CHROME if k in ids}


def _full(r, size):
    W, H = size
    return r[0] <= TOL and r[1] <= TOL and r[0] + r[2] >= W - TOL and r[1] + r[3] >= H - TOL


def _records(f):
    """A frame's page records: its own, and the pages a 300's or 320's lends it."""
    return [f] + [f[k] for k in ('home', 'second') if f.get(k)]


def frame_of(path, size, art=None):
    """A series' frame off its seed at `path` (canvas `size`): the working page
    in the five bands (top, left, right, bottom, center), each band's rect -
    None where the template draws none - its surfaces and its items by role,
    the header's tabs, the left rail's groups and the centre's popup region,
    with the well, title, empty state and status of a source's popup on it,
    the sizes it sets them in, the title of a source with controls and the
    picture each source's popup pins, by device;
    the windows' sizes and the lines their messages take; on a 300
    or a 320 the home page's and a source's second page's bands as records of
    their own; the windows a page opens; the seed IDs of the fixed chrome; the
    page measured and a note of what the bands alone do not say. `art` is the
    main region Afterburn's background art draws (frame_art), around which its
    bands stand; a 300's or 320's pages each stand around their own art."""
    p = Project.open(path)
    pages = seed_pages(p)
    W, H = size
    named = {pg['name']: pg for pg in pages if pg['kind'] == 'page' and pg['name']}
    popups = [pg for pg in pages if pg['kind'] == 'popup' and not pg['modal'] and pg['name']]
    # A hub's one working page before its variants (Mach's Main Recording).
    work = sorted((pg for n, pg in named.items() if n.startswith('Main')),
                  key=lambda pg: pg['name'] not in ('Main Page', 'Main'))
    # The working page: Main SD, else the first Main* page with all four bars;
    # a hub's one Main page whose popup region fills main; else the 320's pages.
    out = None
    if 'Main SD' in named:
        out = _bars_frame(named['Main SD'], pages, size, art)
    for pg in work if out is None else ():
        f = page_bands(pg, size)
        if f['L'] > 0 and f['R'] < W and f['T'] > 0 and f['B'] < H:
            out = _bars_frame(pg, pages, size, art)
            break
    for pg in work if out is None else ():
        refs = [c['rect'] for c in pg['controls'] if c['type'] == 'PBPopupPageReference' and not _full(c['rect'], size)]
        if refs and _area(max(refs, key=_area)) >= 0.5 * W * H:
            out = _hub_frame(pg, popups, size, art)
            break
    paged = out is None
    if paged:
        out = _pages_frame(named, size, (lambda pg: page_art(p, pg, size)) if art else (lambda pg: None))
    # The windows, then what the bands do not say, last.
    items = [it for rec in _records(out) for b in BANDS if rec[b] for it in rec[b]['items']]
    region = out['center'].get('region')
    note, ids = out.pop('note'), out.pop('ids')
    out['windows'] = _windows(pages, size, region[:2] if region else (0, 0),
                              [it['name'] for it in items if it['role'] == 'settings'])
    # A page per source shows its volume in a modal the program shows (the
    # 320's Volume): where it draws it, what it draws.
    volume = _volume_modal(pages, size) if paged else None
    if volume:
        out['volume'] = volume
    # A bar series' call mode and the page it chooses sources on - Afterburn's
    # too, whose bar-class templates draw all of them round the art's
    # squircle - and none of the hubs' or the 320's, which draw neither.
    if not paged and 'options' not in out:
        # The seam a third group stands under the one above it at (`seam`),
        # off the series' own three-group page.
        if art and THREE_GROUPS in named:
            seam = _rail_seam(named[THREE_GROUPS], out['left']['rect'])
            if seam is not None:
                out['left']['seam'] = seam
        if CALL_PAGE in named:
            out['call'] = _call_frame(named[CALL_PAGE], pages, size, art)
        if SELECT_PAGE in named:
            out['choose'] = _select_frame(named[SELECT_PAGE], out, size)
        incoming = next((pg for n in INCOMING for pg in pages
                         if pg['name'] == n and pg['kind'] == 'popup' and pg['modal']), None)
        if incoming:
            out['windows']['incoming'] = _incoming(incoming, size)
    out['ids'], out['note'] = ids, note
    # Each band reads rect, surfaces, its own slots (tabs, groups, the
    # centre's region), then what is left in it.
    for rec in _records(out):
        for b in BANDS:
            if rec[b]:
                rec[b]['items'] = rec[b].pop('items')
    return out


def _controls(page, size):
    return [c for c in page['controls'] if not (c['type'] == 'PBPopupPageReference' and _full(c['rect'], size))]


def _call_frame(page, pages, size, art=None):
    """The call mode's working page (Main VC) as the working page is read: its
    four bars - the header's tabs with Share Content at its end, the left
    rail's VTC group (Make Call, End Call, Privacy) over its launchers, which
    hold one more than Main SD's on Mach (Display, Screen, Lighting, Audio) -
    and the centre's popup region and the page's own surfaces round it (a
    source's popup's are the working page's); the dialer that region shows
    (VTC Dialer, `center.dialer`); and the seed IDs of the call's chrome.
    Afterburn's (`art`, its squircle) has no bars: its Share Content stands
    at the right rail's head (1121,30 on the 1035), an item of `right`."""
    f = _bars_frame(page, pages, size, art)
    c = f['center']
    rec = {'page': page['name']}
    for b in ('top', 'left', 'right', 'bottom'):
        rec[b] = f[b]
    rec['center'] = {'rect': c['rect'], 'region': c['region'],
                     'surfaces': [s for s in c['surfaces'] if not s.get('popup')], 'items': c['items']}
    # The VTC keys' own words (Mach's Make Call, Shockwave's Call,
    # Turbulence's Initiate Call), which an example call page says.
    said = {c['name']: _said(' '.join((c['caption'] or '').split())) for c in page['controls'] if c['type'] == 'PBButton'}
    for g in rec['left']['groups'][:1]:
        for btn in g['buttons']:
            if said.get(btn['name']):
                btn['text'] = said[btn['name']]
    region = c['region']
    dialer = next((pg for pg in pages if pg['kind'] == 'popup' and not pg['modal'] and pg['name'] == DIALER), None)
    if dialer is not None and region:
        rec['center']['dialer'] = _dialer(dialer, region[:2])
    ids = {}
    for b in ('top', 'left', 'right'):
        if not rec[b]:
            continue
        for it in (rec[b]['items'] + [x for e in ('start', 'end') for x in rec[b].get(e) or ()]
                   + [x for g in rec[b].get('groups') or () for x in g['buttons']]):
            if it['role'] in CALL_CHROME and it.get('id') and it['role'] not in ids:
                ids[it['role']] = it['id']
    rec['ids'] = {k: ids[k] for k in CALL_CHROME if k in ids}
    return rec


def _dial_role(c):
    """A dialer key's meaning off its name: 'Dialer Keypad 1' is digit-1,
    'Dialer Keypad *' star, '#' hash, 'Dialer Keypad Period' period; 'VC
    Call', 'VC Flash', 'VC PhoneBook' (contacts), 'VC Keyboard', 'VC Delete'."""
    words = (c['name'] or '').split()
    low = [w.lower() for w in words]
    if 'keypad' in low:
        k = low[-1]
        return {'*': 'star', '#': 'hash'}.get(k, 'digit-' + k if k.isdigit() else k)
    if 'phonebook' in low or 'contacts' in low:
        return 'contacts'
    return next((r for r in ('call', 'flash', 'keyboard', 'delete') if r in low), _role(c))


def _said(caption):
    """A caption as words a system can set: None where it is a glyph of an icon
    face (Mach's \\ue913 Delete, Shockwave's '(' star) or nothing."""
    s = (caption or '').strip()
    return s if s and re.match(r'^[A-Za-z0-9 #*.@-]+$', s) else None


def _dialer(pg, at):
    """The dialer a call page's popup region shows (VTC Dialer), on the page
    at `at`: its title (the label naming it) and the size it sets it in, the
    entry the program writes the number into (Dialer Feedback Label, 50000)
    with the field drawn behind it, its surfaces - Mach's well, its title bar
    and that field - and each key by its meaning (_dial_role) with its seed
    ID, its words where it says any, and its art at rest."""
    cs = pg['controls']
    labels = [c for c in cs if c['type'] == 'PBLabel']
    title = next((c for c in labels if (c['caption'] or '').strip().lower() == pg['name'].lower()), None)
    # The entry is 50000 on every seed; Afterburn's dialer draws a label of
    # letters under each digit too (Dialer Keypad 9 Letters Label), first.
    entry = next((c for c in labels if c['id'] == ENTRY_ID), None) or next(
        (c for c in labels if c is not title), None)
    keys = []
    for c in sorted((c for c in cs if c['type'] == 'PBButton'), key=lambda c: (c['rect'][1], c['rect'][0])):
        k = _item(c, at, _dial_role(c))
        if _said(c['caption']):
            k['text'] = _said(c['caption'])
        art = (c['looks'][0] if c['looks'] else {}).get('art')
        if art:
            k['art'] = art
        keys.append(k)
    out = {'popup': pg['name'], 'title': _offset(title['rect'], at) if title else None,
           'text': title['caption'] if title else None,
           'pt': {k: v for k, v in (('title', title['pt'] if title else None), ('entry', entry['pt'] if entry else None))
                  if v is not None},
           'entry': _item(entry, at, 'entry') if entry else None,
           'surfaces': [_surface_of(c, at, pg['name']) for c in sorted(cs, key=lambda c: (c['rect'][1], c['rect'][0]))
                        if _surface(c)],
           'keys': keys}
    return out


def _select_frame(page, bars, size):
    """The page a bar series chooses among its sources on (Main Select
    Source): its title - in the header band on both the series that draw it,
    Mach's 'Select a source' on its strip, Turbulence's 'Select a Source' -
    with the surfaces across the screen's top, and the source tiles in the
    centre band (the working page's, `bars`), each with the label under it,
    as a hub's grid is read (_grid_of)."""
    centre = bars['center']['rect']
    # Afterburn's centre is its squircle, whose foot holds the foot row
    # (Preview): no tile. Its sources stand over the popup region, as wide as
    # it - the 1230's squircle holds a preview pane beside it, with a row of
    # source buttons of its own.
    foot = (bars.get('foot') or {}).get('rect')
    region = bars['center'].get('region')
    if foot and region:
        centre = [region[0], centre[1], region[2], centre[3]]
    cs = _controls(page, size)
    labels = sorted((c for c in cs if c['type'] == 'PBLabel'), key=lambda c: (c['rect'][1], c['rect'][0]))
    title = next((c for c in labels if 'select' in (c['caption'] or '').lower()), None)
    head = [c for c in cs if c['type'] in SURFACES and c['rect'][1] <= TOL and c['rect'][3] < size[1] / 4]
    held = [c for c in cs if c['type'] in ('PBButton', 'PBLabel') and c is not title and _centre_in(c['rect'], centre)
            and not (foot and _centre_in(c['rect'], foot))]
    out = _grid_of(([title] if title else []) + head + held, (0, 0), None)
    out = dict({'page': page['name']}, **{k: v for k, v in out.items() if k != 'popup'})
    return out


def _incoming(pg, size):
    """The question the program shows when a call comes in, as the power-down
    question is read (_window), with its words - Mach's and Turbulence's on
    one line, Shockwave's broken after its comma - and each answer's where it
    says any (Mach's Accept and Decline, Shockwave's Accept Call and Ignore
    Call; Turbulence's are in their art)."""
    w = _window(pg, size, (0, 0), 'confirm')
    cs = _controls(pg, size)
    said = sorted((c for c in cs if c['type'] == 'PBLabel'), key=lambda c: (c['rect'][1], c['rect'][0]))
    w['text'] = '\n'.join(' '.join(ln.split()) for c in said if c['caption']
                          for ln in c['caption'].replace('\r\n', '\n').split('\n'))
    named = {c['name']: c for c in cs if c['type'] == 'PBButton'}
    for b in w.get('buttons') or ():
        words = _said((named.get(b['name']) or {}).get('caption'))
        if words:
            b['text'] = words
    return dict({'popup': pg['name']}, **w)


def _bars_frame(page, pages, size, art):
    W, H = size
    cs = _controls(page, size)
    f = page_bands(page, size)
    notes = []
    if art:
        # Afterburn: no bar at all - the art's squircle is the centre and the
        # columns either side of it the rails.
        x0, x1 = art[0], art[0] + art[2]
        rects = {'top': None, 'bottom': None, 'left': [0, 0, x0, H], 'right': [x1, 0, W - x1, H], 'center': list(art)}
    else:
        L, R, T, B = f['L'], f['R'], f['T'], f['B']
        # A well is main (control_regions), so the rails stand outside it:
        # Shockwave's well and footer are wider than its header's tab span,
        # whose end blocks would put each rail 7-13 px inside the well.
        if f['well']:
            L, R = min(L, f['well'][0]), max(R, f['well'][0] + f['well'][2])
        # A bar whose controls reach both side edges owns the corners (Mach's
        # header and footer, Shockwave's header); else the rails run past it
        # (Turbulence's, Shockwave's footer capsule).
        spans = f['spans']
        wide = {e: bool(spans.get(e)) and min(a for a, _ in spans[e]) <= TOL and max(b for _, b in spans[e]) >= W - TOL
                for e in ('top', 'bottom')}
        y0 = T if wide['top'] else 0
        y1 = B if wide['bottom'] else H
        rects = {'top': [0, 0, W, T] if wide['top'] else [L, 0, R - L, T],
                 'bottom': [0, B, W, H - B] if wide['bottom'] else [L, B, R - L, H - B],
                 'left': [0, y0, L, y1 - y0], 'right': [R, y0, W - R, y1 - y0], 'center': [L, T, R - L, B - T]}
        surf = [c for c in cs if _surface(c)]
        for b in ('top', 'bottom', 'left', 'right'):
            rects[b] = _snap(rects[b], [c for c in surf if _centre_in(c['rect'], rects[b])])
    held = {b: [] for b in BANDS}
    for c in cs:
        b = next((b for b in ('top', 'bottom', 'left', 'right', 'center') if _centre_in(c['rect'], rects[b])), 'center')
        held[b].append(c)
    region = f['window']
    out = {'page': page['name']}
    for b in BANDS:
        if rects[b] is None:
            out[b] = None
            continue
        mine = [c for c in held[b]
                if not (b == 'center' and c['type'] == 'PBPopupPageReference' and c['rect'] == region)]
        surfaces = [c for c in mine if _surface(c) and not (c['type'] == 'PBLabel' and b != 'top')]
        rest = [c for c in mine if c not in surfaces]
        band = _band(rects[b], [], surfaces)
        tabs, taken = _tabs([c for c in rest if c['type'] == 'PBButton']) if b in ('top', 'center') else (None, [])
        if tabs and (b == 'top' or art):
            band['tabs'] = tabs
            rest = [c for c in rest if c not in taken]
            if b == 'top':
                x0, x1 = tabs['first'][0], tabs['items'][-1]['rect'][0] + tabs['items'][-1]['rect'][2]
                band['start'] = [_item(c) for c in sorted(surfaces + rest, key=lambda c: c['rect'][0])
                                 if c['rect'][0] + c['rect'][2] <= x0 + TOL]
                band['end'] = [_item(c) for c in sorted(surfaces + rest, key=lambda c: c['rect'][0])
                               if c['rect'][0] >= x1 - TOL]
        if b == 'left':
            band['groups'], rest = _groups(rest)
        # Last, after the band's tabs or groups: what is left in it.
        band.pop('items')
        band['items'] = [_item(c) for c in sorted(rest, key=lambda c: (c['rect'][1], c['rect'][0]))]
        out[b] = band
    centre, drawn = _centre_from(_source_popup(pages), region[:2] if region else (0, 0))
    out['center'].update({'region': region}, **centre)
    out['center']['surfaces'] += drawn
    titled = _controls_title(pages, region[:2] if region else (0, 0))
    if titled:
        out['center']['title_controls'] = titled
    pictures = _pictures(page, pages, region[:2] if region else (0, 0), drawn)
    if pictures:
        out['center']['pictures'] = pictures
    if f['well'] and not out['center'].get('well'):
        out['center']['well'] = list(f['well'])
    if art:
        foot = _foot(out, size)
        if foot:
            out['foot'] = foot
    out['ids'] = _ids([it for b in BANDS if out[b] for it in out[b]['items']], [])
    # What the five bands do not say, from what was measured.
    if art:
        notes.append('No top or bottom bar: the background art draws the centre and the rails beside it, '
                     'the source tabs sit across the centre\'s top and the clock in its foot.')
    tabs = (out['top'] or {}).get('tabs') or {}
    if tabs and tabs['pitch'] - tabs['first'][2] == 1:
        notes.append('The tabs stand 1 px apart, so the photo draws a hairline between them.')
    tw = tabs.get('twin')
    if tw:
        w, h = tw['items'][0]['rect'][2:]
        mute = not any(look.get('text') for look in tabs['look'].values())
        notes.append(f"Each tab's name is a {w}x{h} caption under it, a button with the tab's ID and no fill or art"
                     + ("; the tab draws no caption of its own" if mute else '') + '.')
    for b in ('left', 'right'):
        for it in (out[b] or {}).get('items', []):
            foot = out['bottom'] and it['rect'][1] >= out['bottom']['rect'][1] - TOL
            if it['role'] in ('power', 'help', 'mode') and foot:
                notes.append(f"{it['name']} stands at the {b} rail's foot, beside the footer.")
    if out['bottom'] and not any(s['rect'] == out['bottom']['rect'] for s in out['bottom']['surfaces']) \
            and any(s['rect'][1] + s['rect'][3] < H - TOL for s in out['bottom']['surfaces']):
        notes.append('The footer is a capsule standing off the bottom edge.')
    if out['bottom'] and out['bottom']['rect'][0] > TOL:
        notes.append('The rails run down beside the footer, to the foot of the screen.')
    if region and _area(region) < 0.5 * _area(out['center']['rect']):
        notes.append("The popup region fills only part of the centre; the page's own controls hold the rest.")
    out['note'] = ' '.join(notes) or None
    return out


def _foot(out, size):
    """Afterburn's foot row: no footer bar, but every working page stands a
    row of cells along the screen's foot across its three bands - the mode
    launcher in the left rail, the date, Preview and the time in the
    squircle's foot, Help and Power in the right rail - which is the row a bar
    theme's Footer draws. Its rect runs across the screen from the top of the
    lowest-standing row of touch targets and clocks (the cells overlapping the
    lowest one's span down), and its items are the row's mode, clocks,
    Preview, Help and Power (FOOT_ROLES), in x order. Each stays an item of
    its own band too."""
    W, H = size
    cells = [it for b in ('left', 'center', 'right') if out[b] for it in out[b]['items']
             if it['kind'] in ('button', 'datetime')]
    if not cells:
        return None
    low = max(cells, key=lambda it: (it['rect'][1] + it['rect'][3], it['rect'][1]))
    y, h = low['rect'][1], low['rect'][3]
    row = [it for it in cells if it['rect'][1] < y + h and y < it['rect'][1] + it['rect'][3]]
    y0 = min(it['rect'][1] for it in row)
    return {'rect': [0, y0, W, H - y0],
            'items': [it for it in sorted(row, key=lambda it: it['rect'][0]) if it['role'] in FOOT_ROLES]}


def _rail_seam(page, band):
    """The seam a third rail group stands under the one above it at: on the
    series' three-group page (THREE_GROUPS: Display, Screen, Settings), from
    the first group's foot to the next group's heading - 21 px on the 1220,
    12 on the 1020. None where the page draws fewer than three."""
    groups, _ = _groups([c for c in page['controls'] if _centre_in(c['rect'], band)])
    groups = [g for g in groups if g['heading'] and g['buttons']]
    if len(groups) < 3:
        return None
    last = groups[0]['buttons'][-1]['rect']
    return groups[1]['heading']['rect'][1] - (last[1] + last[3])


def _hub_frame(page, popups, size, art):
    """A hub: the right menu bar, the popup region filling main and, where the
    template draws one, the header strip over main the popups also cover."""
    W, H = size
    cs = _controls(page, size)
    refs = [c for c in cs if c['type'] == 'PBPopupPageReference']
    region = max((c['rect'] for c in refs), key=_area)
    x1 = region[0] + region[2]
    bar = [c for c in cs if _surface(c) and c['rect'][3] >= H / 2 and c['rect'][0] + c['rect'][2] >= W - TOL]
    right = list(bar[0]['rect']) if bar else ([x1, 0, W - x1, H] if not art else
                                              [art[0] + art[2], 0, W - art[0] - art[2], H])
    strip = [c for c in cs if _surface(c) and c['rect'][1] <= TOL and c['rect'][3] < H / 4
             and c['rect'][2] >= 0.5 * W and c not in bar]
    top = list(strip[0]['rect']) if strip else None
    out = {'page': page['name'], 'top': None, 'left': None, 'right': None, 'bottom': None}
    held = {'top': [], 'right': [], 'center': []}
    for c in cs:
        if c['rect'] == region and c['type'] == 'PBPopupPageReference':
            continue
        b = 'right' if _centre_in(c['rect'], right) else 'top' if top and _centre_in(c['rect'], top) else 'center'
        held[b].append(c)
    for b, rect in (('top', top), ('right', right)):
        if rect:
            surfaces = [c for c in held[b] if _surface(c) and c['type'] != 'PBLabel']
            out[b] = _band(rect, [c for c in held[b] if c not in surfaces], surfaces)
    # Every hub's menu bar opens its settings with seed ID 8040: Mach's and
    # Afterburn's caption it Settings, Shockwave's and Turbulence's More, which
    # opens their Choose an Option (Audio, Lighting/Blinds).
    for it in out['right']['items']:
        if it['role'] == 'more':
            it['role'] = 'settings'
    centre = _band(list(region), [c for c in held['center'] if not _surface(c)],
                   [c for c in held['center'] if _surface(c)])
    fields, drawn = _centre_from(_source_popup(popups), region[:2])
    centre.update({'region': list(region)}, **fields)
    centre['surfaces'] += drawn
    titled = _controls_title(popups, region[:2])
    if titled:
        centre['title_controls'] = titled
    pictures = _pictures(page, popups, region[:2], drawn)
    if pictures:
        centre['pictures'] = pictures
    level = _level_strip(popups, next((it['rect'] for it in centre['items'] if it['role'] == 'popup'), None))
    if level:
        centre['level'] = level
    out['center'] = centre
    # The grids a hub draws in main: its Select a Source (a popup of its own
    # on Mach, the page's own under the popups on Shockwave and Turbulence)
    # and the options its settings opener shows (Mach's Settings,
    # Shockwave's and Turbulence's More Options).
    pops = {pg['name']: pg for pg in popups}
    select = pops.get('Select Source')
    out['select'] = (_grid_of(select['controls'], region[:2], select['name']) if select else
                     _grid_of(held['top'] + held['center'], (0, 0), None, top))
    opener = next((it for it in out['right']['items'] if it['role'] == 'settings'), None)
    named = _windows_named(popups, opener['name']) if opener else None
    out['options'] = _grid_of(named['controls'], region[:2], named['name']) if named else None
    out['ids'] = _ids([it for b in BANDS if out[b] for it in out[b]['items']],
                      [pg for pg in popups if 'source' in pg['name'].lower()])
    notes = ['The popups fill main' + (', the header strip included' if top else '') + '.']
    if any(it['role'] != 'popup' for it in centre['items']):
        notes.append('Under them the page holds its own Select a Source grid.')
    if 'help' in out['ids'] and not any(it['role'] == 'help' for b in ('top', 'right', 'center') if out[b]
                                        for it in out[b]['items']):
        notes.append('Help is on the Select Source popup, not the bar.')
    out['note'] = ' '.join(notes)
    return out


def _level_strip(popups, strip):
    """The Volume Level popup a hub's strip reference shows beside its bar: its
    own fill, its level's rect, track and filled part, and the glyph labels
    over and under the level (Mach's speaker+ and speaker- in Extron-Lift,
    Shockwave's and Turbulence's in Extron GUI Configurator), in the popup's
    coordinates."""
    if not strip:
        return None
    pg = next((pg for pg in popups if list(pg['size']) == list(strip[2:])
               and any(c['type'] == 'PBLevel' for c in pg['controls'])), None)
    if not pg:
        return None
    lv = next(c for c in pg['controls'] if c['type'] == 'PBLevel')
    g = lv.get('gauge') or {}
    return {'popup': pg['name'], 'fill': pg.get('paint'), 'rect': list(lv['rect']), 'track': lv['paint'],
            'border': (lv['border'] or {}).get('resource'),
            'bar': None if g.get('art') else g.get('fill'),
            'art': {'track': g.get('track_image'), 'fill': g.get('fill_image')} if g.get('art') else None,
            'labels': [list(c['rect']) for c in sorted(pg['controls'], key=lambda c: c['rect'][1])
                       if c['type'] == 'PBLabel']}


def _volume_modal(pages, size):
    """The modal a page-per-source series shows its volume in (the 320's
    Volume, which no control on a page opens): its name, its surfaces (Mach's
    #4B4B4C strip at the right edge), its level's rect, empty `track` and
    filled `bar` colours or `art`, and `border`, the glyph `labels` over and
    under it, and `cancel`, the transparent button over the rest of the screen
    that puts it away (Shockwave's and Turbulence's; Mach's has none), as an
    item - in page coordinates."""
    W, H = size
    pg = next((pg for pg in pages if pg['kind'] == 'popup' and pg['modal'] and tuple(pg['size']) == (W, H)
               and any(c['type'] == 'PBLevel' for c in pg['controls'])), None)
    if not pg:
        return None
    cs = _controls(pg, size)
    lv = next(c for c in cs if c['type'] == 'PBLevel')
    g = lv.get('gauge') or {}
    cancel = max((c for c in cs if c['type'] == 'PBButton'), key=lambda c: _area(c['rect']), default=None)
    return {'popup': pg['name'], 'surfaces': [_surface_of(c) for c in cs if c['type'] in SURFACES],
            'level': {'rect': list(lv['rect']), 'track': lv['paint'], 'border': (lv['border'] or {}).get('resource'),
                      'bar': None if g.get('art') else g.get('fill'),
                      'art': {'track': g.get('track_image'), 'fill': g.get('fill_image')} if g.get('art') else None},
            # Its glyphs over and under the level (Volume Up Label 7023 and
            # Volume Down Label 7026), with their seed IDs and sizes.
            'labels': [{'rect': list(c['rect']), 'id': c['id'], 'pt': c['pt']}
                       for c in sorted(cs, key=lambda c: c['rect'][1]) if c['type'] == 'PBLabel'],
            'cancel': dict(_item(cancel), role='cancel') if cancel else None}


def _windows_named(popups, opener):
    """The popup a hub's opener shows: its name, or its name and more - More
    opens More Options."""
    return next((pg for pg in popups if pg['name'] == opener or pg['name'].startswith(opener + ' ')), None)


def _grid_of(cs, at, popup, strip=None):
    """A hub's grid in main, on the page at `at`: its title (the topmost
    label), its header strip (a shape across the top, or `strip`, the page's
    header band, whose surfaces are its) and its lines (Afterburn 520's
    Divider under its tiles), its Help and Close, its tiles - the buttons, in
    rows - each with the label under it, and the sizes it sets them in.
    Shockwave's and Turbulence's Select a Source is the page's own under the
    popups, Mach's a popup of its own."""
    labels = [c for c in cs if c['type'] == 'PBLabel']
    title = min(labels, key=lambda c: (c['rect'][1], c['rect'][0])) if labels else None
    W = max((c['rect'][0] + c['rect'][2] for c in cs), default=0)
    head = [c for c in cs if _surface(c) and c['type'] != 'PBLabel' and c['rect'][1] <= TOL
            and (strip and _centre_in(c['rect'], strip) or c['rect'][2] >= 0.9 * W)]
    buttons = [c for c in cs if c['type'] == 'PBButton']
    helps = [c for c in buttons if _role(c) == 'help']
    closes = [c for c in buttons if _role(c) in ('close', 'back')]
    tiles = sorted((c for c in buttons if c not in helps and c not in closes),
                   key=lambda c: (round(c['rect'][1] / 20), c['rect'][0]))

    def under(t):
        # Its name, below its middle - Turbulence's runs 7 px up into its
        # tile's foot - and above the next row's; or inside the tile's foot,
        # its middle in the tile's lower half and within the tile's width, as
        # Afterburn's hub sets its 13 pt caption at 194 in a tile from 147 to
        # 247.
        r = t['rect']

        def inside(c):
            q = c['rect']
            return q[1] + q[3] / 2 >= r[1] + r[3] / 2 and r[0] <= q[0] and q[0] + q[2] <= r[0] + r[2]
        below = [c for c in labels if c is not title and (c['rect'][1] >= r[1] + r[3] / 2 or inside(c))
                 and r[0] <= c['rect'][0] + c['rect'][2] / 2 <= r[0] + r[2]
                 and not any(o is not t and o['rect'][1] > r[1] + r[3] / 2 and o['rect'][1] < c['rect'][1]
                             and o['rect'][0] < r[0] + r[2] and r[0] < o['rect'][0] + o['rect'][2]
                             for o in tiles)]
        return min(below, key=lambda c: c['rect'][1], default=None)
    out = {'popup': popup, 'title': _offset(title['rect'], at) if title else None,
           'text': title['caption'] if title else None,
           'surfaces': [_surface_of(c, at) for c in head + [c for c in cs if c['type'] == 'PBLine']],
           'help': _item(helps[0], at) if helps else None,
           'close': _item(closes[0], at) if closes else None, 'tiles': []}
    pt = {'title': title['pt'] if title else None}
    for t in tiles:
        lab = under(t)
        tile = {'rect': _offset(t['rect'], at), 'label': _offset(lab['rect'], at) if lab else None}
        if lab and lab['pt'] and 'label' not in pt:
            pt['label'] = lab['pt']
        out['tiles'].append(tile)
    out['pt'] = {k: v for k, v in pt.items() if v is not None}
    return out


def _title_of(pg):
    """A page's title: the label named for it - 'Computer Label', not
    'Computer Instructions Label'; 'Doc Cam 1 Label' - or None: the home
    page's labels ('Main Volume Label') are not named for it."""
    name = pg['name'] or ''
    want = (name + ' Label', re.sub(r' \d+$', '', name) + ' Label')
    return next((c for c in pg['controls'] if c['type'] == 'PBLabel' and c['name'] in want), None)


def _page_bands(pg, size, art):
    """One page's bands as a 300 or a 320 draws them: around its own art's
    body (Afterburn's), else a strip across the top - controls on the top
    edge spanning it, the 320's title label or Mach's second page's shape and
    Back - and a bar across the foot (the 300's menu); the centre between."""
    W, H = size
    bands = dict.fromkeys(BANDS)
    if art:
        x, y, w, h = art
        bands.update(top=[0, 0, W, y] if y > TOL else None,
                     bottom=[0, y + h, W, H - y - h] if y + h < H - TOL else None,
                     left=[0, 0, x, H] if x > TOL else None,
                     right=[x + w, 0, W - x - w, H] if x + w < W - TOL else None, center=list(art))
        return bands
    cs = _controls(pg, size)
    top = [c['rect'] for c in cs if c['rect'][1] <= TOL and c['rect'][3] < H / 4]
    if top and _covered([(r[0], r[0] + r[2]) for r in top], 0, W) >= RUN * W:
        bands['top'] = [0, 0, W, max(r[1] + r[3] for r in top)]
    foot = [c['rect'] for c in cs if _surface(c) and c['rect'][2] >= W - TOL
            and c['rect'][1] + c['rect'][3] >= H - TOL and c['rect'][3] < H / 4]
    if foot:
        y = min(r[1] for r in foot)
        bands['bottom'] = [0, y, W, H - y]
    y0 = bands['top'][3] if bands['top'] else 0
    y1 = bands['bottom'][1] if bands['bottom'] else H
    bands['center'] = [0, y0, W, y1 - y0]
    return bands


def _page_record(pg, size, art):
    """A page's five bands, each with its surfaces (a filled label's ground
    among them) and its items - the centre's only its title, More and Back,
    the chrome a source page keeps: its controls are the source's own."""
    bands = _page_bands(pg, size, art)
    title = _title_of(pg)
    held = {b: [] for b in BANDS}
    for c in _controls(pg, size):
        b = next((b for b in ('top', 'bottom', 'left', 'right') if bands[b] and _centre_in(c['rect'], bands[b])),
                 'center')
        if b == 'center' and c is not title and _role(c) not in ('more', 'back'):
            continue
        held[b].append(c)
    rec = {'page': pg['name']}
    for b in BANDS:
        if bands[b] is None:
            rec[b] = None
            continue
        rec[b] = {'rect': bands[b], 'surfaces': [_surface_of(c) for c in held[b] if _surface(c)], 'items': [
            _item(c, role='title' if c is title else None)
            for c in sorted(held[b], key=lambda c: (c['rect'][1], c['rect'][0])) if c['type'] not in SURFACES]}
    return rec, bands, title


def _said_of(pg, size, art):
    """A source page's empty state's labels, top down: its labels in the
    centre, less its title."""
    bands, title = _page_bands(pg, size, art), _title_of(pg)
    return sorted((c for c in pg['controls'] if c['type'] == 'PBLabel' and c is not title
                   and _centre_in(c['rect'], bands['center'])), key=lambda c: (c['rect'][1], c['rect'][0]))


def _empty_of(pg, size, art):
    """A source page's empty state: its labels in the centre, less its title."""
    return _bbox([c['rect'] for c in _said_of(pg, size, art)])


def _and(words):
    return ', '.join(words[:-1]) + ' and ' + words[-1] if len(words) > 1 else ''.join(words)


def _pages_frame(named, size, art_of):
    """The 320 and the 300: a page per source. The first source page in the
    five bands - its title, More and the centre's first row of controls and
    the headings over it, and the empty state of a source with no controls -
    with the home page (the 300's menu bar, the 320's Select a Source strip)
    and the source's second page (its Back) as records of their own, since a
    band holds one page's controls. `art_of` is a page's own art's main
    region (page_art) on Afterburn, else None."""
    W, H = size
    home = named.get('Main')
    # The source page: a source's first of two (the 320's Doc Cam 1 and 2, the
    # Doc Cam first, as every 320 template has it), else the first page the
    # home page's source buttons name (the 300's Main Computer), else the
    # first with a Back.
    pairs = sorted((n for n in named if n.endswith(' 1') and n[:-2] + ' 2' in named),
                   key=lambda n: (n != 'Doc Cam 1', n))
    tiles = [c['name'][len('Main '):] for c in (home or {'controls': []})['controls']
             if c['type'] == 'PBButton' and (c['name'] or '').startswith('Main ')]
    first = named[pairs[0]] if pairs else next(
        (named[n] for n in tiles if n in named),
        next((pg for pg in named.values() if pg is not home and any(_role(c) == 'back' for c in pg['controls'])), home))
    second = named.get(first['name'][:-2] + ' 2') if pairs else None
    out, bands, title = _page_record(first, size, art_of(first))
    # The source page's first row: its controls nearest the strip, and the
    # headings over them.
    inner = [c for c in first['controls'] if c['type'] == 'PBButton' and _role(c) not in ('more', 'back')
             and _centre_in(c['rect'], bands['center'])]
    if inner:
        y = min(c['rect'][1] for c in inner)
        row = sorted((c for c in inner if c['rect'][1] <= y + TOL), key=lambda c: c['rect'][0])
        out['center']['row'] = [list(c['rect']) for c in row]
        heads = [c for c in sorted(first['controls'], key=lambda c: c['rect'][0])
                 if c['type'] == 'PBLabel' and c is not title
                 and c['rect'][1] + c['rect'][3] / 2 < y and _centre_in(c['rect'], bands['center'])]
        out['center']['headings'] = [list(c['rect']) for c in heads]
        # The steps across the row and down a column (the 320's Doc Cam: 124
        # and 60 on Mach's, 103 and 61 on Shockwave's and Turbulence's),
        # which a page per source lays a source's columns out at.
        col = sorted((c for c in inner if abs(c['rect'][0] - row[0]['rect'][0]) <= TOL), key=lambda c: c['rect'][1])
        out['center']['pitch'] = [row[1]['rect'][0] - row[0]['rect'][0] if len(row) > 1 else None,
                                  col[1]['rect'][1] - col[0]['rect'][1] if len(col) > 1 else None]
        # The sizes it sets its title, its headings and its empty state in.
        pt = {'title': title['pt'] if title else None, 'heading': heads[0]['pt'] if heads else None}
        # A source with controls has no empty state: a source page with none
        # draws it (the 320's Laptop: 'Laptop is currently selected.').
        empty = next((named[n] for n in EMPTY_SOURCES if n in named), None)
        if empty is not None:
            out['center']['empty'] = _empty_of(empty, size, art_of(empty))
            out['center']['empty_page'] = empty['name']
            said = _said_of(empty, size, art_of(empty))
            pt['empty'] = said[0]['pt'] if said else None
            # Its lines one label each, where the template sets them so (the
            # 320's Laptop Label 1-3, 6060-6062): the first sentence a
            # paragraph apart from the other two, which one box loses.
            if len(said) > 1:
                out['center']['empty_lines'] = [{'rect': list(c['rect']), 'id': c['id']} for c in said]
        out['center']['pt'] = pt
    else:
        out['center']['empty'] = _empty_of(first, size, art_of(first))
    if home is not None and home is not first:
        out['home'] = _page_record(home, size, art_of(home))[0]
    if second is not None:
        out['second'] = _page_record(second, size, art_of(second))[0]
    out['ids'] = _ids([it for rec in _records(out) for b in BANDS if rec[b] for it in rec[b]['items']], [])
    notes = ['Each source is a page of its own' + (', its second page from More and back by Back' if second else '')
             + '.']
    where = {'bottom': 'the row along the foot', 'left': 'the column at the left', 'right': 'the column at the right'}
    at = next((b for b in ('top', 'bottom', 'left', 'right') if title and out[b]
               and _centre_in(title['rect'], out[b]['rect'])), 'center')
    if at in where:
        beside = [it['role'].capitalize() for it in out[at]['items'] if it['role'] in ('more', 'back')]
        notes.append(f'The title sits in {where[at]}' + (f", with {_and(beside)}" if beside else '') + '.')
    elif at == 'center' and title:
        notes.append('The title sits on the page, with no strip or bar behind it.')
    loose = [it['role'].capitalize() for rec in _records(out)[:1] + ([out['second']] if second else [])
             for it in rec['center']['items'] if it['role'] in ('more', 'back')]
    if loose:
        notes.append(f"{_and(loose)} {'sit' if len(loose) > 1 else 'sits'} on the page, not in a bar.")
    lent = out.get('home') or {}
    for b in ('top', 'bottom', 'left', 'right'):
        names = [it['name'] for it in (lent.get(b) or {}).get('items', []) if it['role'] in CHROME]
        if names:
            own = [it for it in (out[b] or {}).get('items', []) if it['role'] == 'back']
            notes.append(f"{home['name']} holds {_and(names)} in {where.get(b, 'the strip across the top')}"
                         + ('; a source page holds Back there instead' if own else '') + '.')
    out['note'] = ' '.join(notes)
    return out


def _window(pg, size, at, kind):
    """One window as the page it covers shows it: a modal popup over the whole
    canvas (Build adds its scrim), a popup in the popup region (a hub's, at
    `at`) or a page (the 300's, the 320's). Its rect is its card or band - the
    largest shape or image a modal draws, Mach's #303030 band between the
    bars, Shockwave's #999999 card, Afterburn's art over the whole screen -
    or None where a modal draws none (Mach's hubs); a region popup is its own
    rect. Its title is the label naming it, else on a settings window the
    topmost in its top fifth (Shockwave's More Options: 'Choose an Option')."""
    full = tuple(pg['size']) == tuple(size)
    at = (0, 0) if full else at
    cs = _controls(pg, size)
    drawn = [c for c in cs if c['type'] in SURFACES]
    if full:
        # Its largest surface and those drawn over it: Mach's Share Content
        # lays its #000000B4 band over a photo of the band's size.
        big = max((c['rect'] for c in drawn), key=_area, default=None)
        card = [c for c in drawn if c['rect'] == big]
        rect = _offset(big, at)
    else:
        card = [c for c in drawn if c['rect'][2] >= pg['size'][0] - TOL]
        rect = [at[0], at[1], pg['size'][0], pg['size'][1]]
    labels = [c for c in cs if c['type'] == 'PBLabel']
    said = lambda c: ' '.join((c['caption'] or '').split()).lower()
    title = next((c for c in labels if said(c) == pg['name'].lower()), None)
    # A confirmation or a wait says only its message ('Powering Down Label'
    # reads 'Please wait while the system is powering down.').
    if title is None and kind in ('help', 'settings'):
        box = rect or [at[0], at[1], pg['size'][0], pg['size'][1]]
        top = [c for c in labels if c['rect'][1] + at[1] < box[1] + box[3] / 5]
        title = next((c for c in labels if c['name'] == pg['name'] + ' Label'), None) or min(
            top, key=lambda c: c['rect'][1], default=None)
    buttons = [c for c in cs if c['type'] == 'PBButton']
    # A page, and an Afterburn hub's popup, closes with its Back.
    close = next((c for c in buttons if _role(c) == 'close'), None) or next(
        (c for c in buttons if _role(c) == 'back'), None)
    out = {'rect': rect, 'surfaces': [_surface_of(c, at) for c in card],
           'title': _offset(title['rect'], at) if title else None, 'close': _item(close, at) if close else None}
    # A window that is a page (a 300's, a 320's) on the template's photo, or
    # on the page's own ground (Mach 320's Confirmation, on #303030).
    if pg['kind'] == 'page':
        out['art'] = bool(pg.get('background'))
    # The sizes it sets on this series - Help's message apart from the
    # confirmation's, which every template sets larger - and how many lines
    # the message takes in its box in its own face (_lines).
    out['pt'] = {'title': title['pt']} if title and title['pt'] else {}
    if kind != 'settings':
        said = sorted((c for c in labels if c is not title), key=lambda c: (c['rect'][1], c['rect'][0]))
        out['message'] = _offset(_bbox([c['rect'] for c in said]), at)
        if said and said[0]['pt']:
            out['pt']['message'] = said[0]['pt']
            out['lines'] = _lines(said[0])
    if kind == 'confirm':
        out['buttons'] = [_item(c, at) for c in sorted(buttons, key=lambda c: c['rect'][0]) if c is not close]
        # A question that is a page says its own words, where they are not
        # its series' bigger panels' (Shockwave 320's 'Do you want to power
        # down the system?' in one run, where its 1035 breaks after 'to').
        if pg['kind'] == 'page' and said:
            out['text'] = '\n'.join(c['caption'] for c in said if c['caption'])
    return out


def _windows(pages, size, at, openers):
    """The windows a working page opens, in page coordinates: Help, the
    power-down confirmation and the wait while it powers down, by name; and
    each settings window - every modal with a Close, and the popup or page a
    settings opener names (a hub's More opens More Options, a 300's Settings
    its Settings page) - one record for those drawn alike, naming each."""
    named = {}
    for pg in sorted(pages, key=lambda pg: pg['kind'] != 'popup'):
        named.setdefault(pg['name'], pg)
    out = {}
    for kind, name in WINDOWS:
        pg = named.get(name)
        out[kind] = dict({'popup': name}, **_window(pg, size, at, kind)) if pg else None
    taken = {name for _, name in WINDOWS}
    settings = [pg for pg in pages if pg['kind'] == 'popup' and pg['modal'] and pg['name'] not in taken
                and any(c['type'] == 'PBButton' and _role(c) == 'close' for c in pg['controls'])]
    settings += [pg for pg in pages if pg['name'] and pg not in settings and pg['name'] not in taken
                 and any(pg['name'] == o or pg['name'].startswith(o + ' ') for o in openers)]
    records = []
    for pg in settings:
        w = _window(pg, size, at, 'settings')
        key = json.dumps([w['rect'], w['surfaces'], w['title'], (w['close'] or {}).get('rect'), w['pt']])
        same = next((r for r in records if r[0] == key), None)
        if same:
            same[1]['popups'].append(pg['name'])
        else:
            records.append((key, dict({'popups': [pg['name']]}, **w)))
    out['settings'] = [r for _, r in records]
    return out


def frames(theme, profile=None):
    """{series: frame} of the theme's series whose seed is here (the profile's
    `panels`, gdl/designsys/<theme>.json)."""
    from gdl import seeds
    if profile is None:
        with open(os.path.join(REPO, 'gdl', 'designsys', theme.lower() + '.json'), encoding='utf-8') as fh:
            profile = json.load(fh)
    out = {}
    for series, row in (profile.get('panels') or {}).items():
        if series.startswith('_'):
            continue
        seed = series_seed(row)
        if seeds.usable(seed):
            out[series] = frame_of(seeds.path(seed), tuple(row['size']), art=frame_art(profile, row))
    return out


def seed_facts(path, border_names, border_defs=None):
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
            'datetime': kinds['PBDateTime'] > 0, 'popup': std, 'borders': borders,
            # An image control clones a PBImage: no Shockwave seed has one.
            'image': kinds['PBImage'] > 0,
            'radii': seed_radii(p, border_defs or {})}


def seed_radii(p, border_defs):
    # A built-in border's corner as the seed defines it, where the profile
    # records another: every project carries its own copy of the 13
    # (gdl.project border_geometry), and Build draws the panel's own -
    # Shockwave's 520, 535 and 320 seeds define 2D Rounded Rectangle at
    # radius 10 where its 1035's and 725's, the profile's, are 2, so a card
    # the canvas drew near-square came out round on the panel. {profile
    # border: radius}; a negative radius (an ellipse's) is the shape's, not
    # a corner, and is left out.
    have = p.border_geometry()
    out = {}
    for name, d in border_defs.items():
        g = have.get(d.get('resource') or '')
        if not g or d.get('radius') is None or d['radius'] < 0 or (g.get('radius') or 0) < 0:
            continue
        if g['radius'] != d['radius']:
            out[name] = g['radius']
    return out


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
                    kinds = {k: facts[k] for k in ('slider', 'level', 'datetime', 'popup', 'image')}
                    borders = facts['borders']
    return out, kinds, borders


def measure(theme, profile=None):
    _, kit = kit_files(theme)
    borders = {k: v.get('resource') for k, v in (profile or {}).get('borders', {}).items()}
    defs = (profile or {}).get('borders') or {}
    seeds = {}
    for f in sorted(glob.glob(os.path.join(REPO, 'seeds', f'{theme} *.gdl'))):
        with open(f, 'rb') as fh:
            if fh.read(40).startswith(b'version https://git-lfs'):
                continue
        seeds[os.path.relpath(f, REPO).replace('\\', '/')] = seed_facts(f, borders, defs)
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
        # The series' own seed's corners, where they are not the profile's
        # (seed_radii): the canvas draws the panel's.
        own = next((sp for m, sp in entry['seeds'].items() if m in entry['models']), None)
        if own and seeds[own].get('radii'):
            entry['radii'] = seeds[own]['radii']
        out[row['series']] = entry
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    theme = argv[1]
    prof = os.path.join(REPO, 'gdl', 'designsys', theme.lower() + '.json')
    profile = json.load(open(prof, encoding='utf-8')) if os.path.exists(prof) else None
    if '--frame' in argv:
        print(json.dumps(frames(theme, profile), indent=1))
        return 0
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
