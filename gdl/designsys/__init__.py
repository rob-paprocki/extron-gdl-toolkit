"""Build an Extron template's design system, a Design System artifact.

    python -m gdl.designsys build afterburn out/designsys/afterburn

One Design System artifact per Extron template (docs/claude-design.md §2).
Each is written from a profile - `gdl/designsys/<template>.json`, the
template's own colors, type, borders and button archetypes with where each
came from - and one shared set of components in `bundle.js`. The output is the
artifact's `project/` tree; Claude Code publishes it with the Artifact tool.

The components draw the template for the designer and carry their spec fields
as `data-gdl` JSON for `gdl.design`, which turns a canvas into a spec. So the
vocabulary here is the spec's: a kind, a name, token names for colors, point
sizes, `states`, `press`, `nav`, `does`.
"""
import html
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = ('afterburn', 'mach', 'shockwave', 'turbulence')

# Token and style names the Design System page accepts; anything else drops.
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')

# (component, card group, card height). Order is the catalogue's.
COMPONENTS = (
    ('Page', 'Layout', 200), ('MainArea', 'Layout', 150), ('Rail', 'Layout', 200), ('Group', 'Layout', 200),
    ('Button', 'Controls', 150), ('Label', 'Controls', 110),
    ('Slider', 'Controls', 120), ('Level', 'Controls', 120), ('Clock', 'Controls', 90),
    ('Panel', 'Layout', 130), ('Line', 'Layout', 70), ('PopupRegion', 'Layout', 130),
)
# The region frame's (docs/superpowers/specs/2026-10-22-region-frame-design.md):
# a working page named by its regions, each drawn from the panel's own
# series' measured frame. A theme that draws its bars as controls has them
# (`layout.bars`); Afterburn's chrome is its background art, and its system
# is unchanged.
REGION_COMPONENTS = (
    ('Header', 'Regions', 160), ('LeftRail', 'Regions', 160), ('Section', 'Regions', 160),
    ('RightRail', 'Regions', 160), ('Footer', 'Regions', 160), ('Center', 'Regions', 160),
)


# The template's own art (bundle.js's Image): offered where the profile says
# what its template draws with one (`examples.image`) and the design panel's
# seed can clone a PBImage - none of Shockwave's can.
IMAGE_COMPONENTS = (('Image', 'Controls', 130),)


def _regions(p):
    """Whether the system has the region components: its template draws its
    bars as controls (`layout.bars`)."""
    return (p.get('layout') or {}).get('bars') == 'controls'


def offers_image(p):
    """Whether the system offers the Image component (IMAGE_COMPONENTS)."""
    if not (p.get('examples') or {}).get('image'):
        return False
    for series, row in (p.get('panels') or {}).items():
        if not series.startswith('_') and p['model'] in (row.get('models') or ()):
            return bool((row.get('kinds') or {}).get('image'))
    return False


def components(p):
    """(component, card group, card height) for the profile's system: the
    shared ones, the Image where it offers one, and the region frame's where
    the template draws its bars."""
    return (COMPONENTS + (IMAGE_COMPONENTS if offers_image(p) else ())
            + (REGION_COMPONENTS if _regions(p) else ()))


def _popup_noun(p):
    """What a standard popup is. No template's is a card: a source's popup is
    transparent and draws its text over the page's well (Shockwave's 921x574,
    which the ledger found called one) or, on Afterburn, straight onto the
    squircle (an 880x525 image with alpha 0) - so the size is the popup's, and
    only a modal has a card."""
    return 'standard popup'


def load(template):
    with open(os.path.join(HERE, f'{template}.json'), encoding='utf-8') as fh:
        return json.load(fh)


def _read(name):
    with open(os.path.join(HERE, name), encoding='utf-8') as fh:
        return fh.read()


def px(p, pt):
    """Points -> CSS px at the template's DPI, as a clean string."""
    return f'{round(pt * p["pt"], 2):g}px'


# -- tokens.json ----------------------------------------------------------------
def themes(p):
    """The system's themes: a template's background-and-accent pairings where
    it has them (Afterburn's four), else its accent schemes."""
    if p.get('themes'):
        return p['themes']
    return [dict(s, scheme=s['id']) for s in p['schemes']]


def tokens(p):
    colors = []
    for c in p['colors']:
        v = c['value']
        if isinstance(v, dict):
            v = {t['id']: v[t['scheme']] for t in themes(p) if t['scheme'] in v}
        colors.append({'name': c['name'], 'value': v, 'usage': c['usage']})
    styles = [{'name': t['name'], 'fontSize': px(p, t['pt']), 'lineHeight': 1.2,
               'fontWeight': t['weight'],
               'usage': f"{t['pt']:g} pt on the panel. {t['usage']}"} for t in p['type']]
    radii = []
    for key, b in p['borders'].items():
        value = '50%' if b['radius'] < 0 else ('9999px' if b['radius'] >= 9999 else f"{b['radius']}px")
        named = f" ({b['resource']})" if b['resource'] else ''
        radii.append({'name': f'radius-{key}', 'value': value,
                      'usage': f"Border `{key}`{named}. {b['usage']}"})
    return {
        'name': p['title'], 'version': 1,
        'color': {'themes': [{'id': t['id'], 'name': t['name']} for t in themes(p)],
                  'tokens': colors},
        'type': {'fonts': [],
                 'families': {'sans': p['font']['stack']},
                 'groups': [{'name': 'Panel text', 'family': 'sans', 'styles': styles}]},
        'spacing': {'tokens': [
            {'name': 'nudge', 'value': '10px',
             'usage': "GUI Designer's arrow-key nudge: place and size controls on this grid."},
            {'name': 'gap-min', 'value': f"{p['spacing']}px",
             'usage': f"The least space between two touchable controls on a {p['model']} (2 mm)."},
            {'name': 'touch-min', 'value': f"{p['touch']}px",
             'usage': f"The least width and height of a button or slider on a {p['model']} (9 mm)."},
            {'name': 'button-height', 'value': f"{p['defaults']['button']['height']}px",
             'usage': f"The {p['template']} template's usual button height."},
        ]},
        'radius': {'tokens': radii},
        'size': {'tokens': [
            {'name': 'page-width', 'value': f"{p['size'][0]}px", 'usage': f"A page, and a modal popup, on a {p['model']}."},
            {'name': 'page-height', 'value': f"{p['size'][1]}px", 'usage': 'A page, and a modal popup.'},
            {'name': 'popup-width', 'value': f"{p['popup'][0]}px",
             'usage': f"The {p['template']} template's {_popup_noun(p)}."},
            {'name': 'popup-height', 'value': f"{p['popup'][1]}px", 'usage': f"The {_popup_noun(p)}'s height."},
        ]},
    }


# -- the per-panel table -----------------------------------------------------------
# A frame's bands, turned: what ran across the top runs down the left. The
# frame's own page and each page record it carries (a 300's or 320's home and
# second page) name their bands so.
_FRAME_TURN = {'top': 'left', 'left': 'top', 'bottom': 'right', 'right': 'bottom'}
_FRAME_PAGES = ('home', 'second')
_TURNED_NOTE = ("Its series' upright page turned: the upright top band is the left here and the bottom the right. "
                "Upright: ")


def _legal(frame, size, touch, dpi):
    """`frame` with each touchable slot (gdl.spec.TOUCHABLE: a button or a
    slider) under the panel's touch minimum given the rect that meets it -
    grown about its centre, inside its band where the band can hold it, else
    on the canvas - and the reason. The touch minimum is the panel's own: the
    1220 series' tabs are 64 deep, legal on a 1035 (53 px) and short on an 835
    (67 px). Gaps are left to placement: meeting one moves a neighbour, and a
    tab row or a rail group is a joined set, at the step Extron draws it.
    A Shockwave tab's twin is its caption, pressed as the tab."""
    from .. import spec
    W, H = size

    def fit(r, room):
        x, y, w, h = r
        nw, nh = max(w, touch), max(h, touch)
        at = []
        for v, n, lo, span, full in ((x - (nw - w) // 2, nw, room[0], room[2], W),
                                     (y - (nh - h) // 2, nh, room[1], room[3], H)):
            at.append(min(max(v, lo), lo + span - n) if n <= span else min(max(v, 0), full - n))
        return [at[0], at[1], nw, nh]

    def walk(v, room):
        if isinstance(v, list):
            return [walk(x, room) for x in v]
        if not isinstance(v, dict):
            return v
        out = {}
        for k, x in v.items():
            if k == 'twin':
                out[k] = x
                continue
            # A band's or a window's rect is the room its slots grow in.
            inner = x.get('rect') if isinstance(x, dict) and 'kind' not in x else None
            out[k] = walk(x, inner or room)
        r = v.get('rect')
        if v.get('kind') in spec.TOUCHABLE and r and (r[2] < touch or r[3] < touch):
            out['legal'] = fit(r, room)
            out['reason'] = f'{r[2]}x{r[3]} is under the {touch} px touch minimum (9 mm at {round(dpi, 2):g} DPI)'
        return out
    return walk(frame, [0, 0, W, H]) if frame and touch else frame


def models(p):
    """{panel: row} - every panel the profile's series serve, for the bundle to
    derive each panel's layout from (docs/claude-design.md section 2). A panel
    is gdl.spec.panel_id: its model, or model-Portrait / model-Landscape where a
    series serves a panel that rotates the other way up (the 300M's two).

    A row is the series' own measurements (its `panels` entry: main region,
    rail band, popup region, background art and how it is drawn, the seed per
    model and what that seed can clone, and the frame of its working page)
    with the model's own minimums from
    gdl.spec: touch target and gap (9 mm and 2 mm at its DPI) and type floor -
    or, for a panel turned where no series serves it that way up, its own
    series' row transposed, flagged `turned` (below).
    A profile with no `panels` has none, and its components draw its one
    design panel.
    """
    from .. import spec
    out = {}
    for series, s in (p.get('panels') or {}).items():
        if series.startswith('_'):
            continue
        for m in s['models']:
            touch, gap = spec.touch_minimums(m)
            out[spec.panel_id(m, s['size'])] = {
                'series': series, 'size': list(s['size']), 'dpi': spec.dpi(m),
                'tier': spec.tier(m), 'touch': touch, 'gap': gap, 'floor': spec.type_floor(m),
                'main': s['main'], 'rail': s['rail'], 'rail_axis': s['rail_axis'],
                'popup': s['popup'], 'fit': s['fit'], 'backgrounds': s['backgrounds'],
                'seed': (s.get('seeds') or {}).get(m),
                # A series no seed measures can clone what the template has;
                # its panels are refused for want of a seed before that matters.
                'kinds': s.get('kinds') or {'slider': True, 'level': True, 'datetime': True, 'popup': True},
                'borders': s.get('borders') or {},
                # The corners its seed draws where the profile's border is
                # another's (tests/measure_series.py seed_radii): Shockwave's
                # hubs and 320 round 2D Rounded Rectangle at 10, its 1035 at 2.
                'radii': s.get('radii') or {},
                # The series' working page in its template's grammar, measured
                # off its seed (tests/measure_series.py frame_of), with this
                # panel's legal rects (_legal); None for a series no seed
                # measures.
                'frame': _legal(s.get('frame'), s['size'], touch, spec.dpi(m)),
            }
    # A panel that runs the other way up from every series that draws it - the
    # 520M, 521M, 535M, 835M and 1035M turned (docs/design-rules.md section 1) -
    # is its series turned. Extron draws one panel both ways, the 300M, and its
    # Landscape layout is its Portrait one transposed: main, rail and popup, the
    # rail running the other way. Ours, not Extron's. No art: Extron draws none
    # that way up, and the 300M's landscape art is the portrait's shape with its
    # paint redrawn, which a rotation is not. Its seed is the model's own turned
    # (New-GdlTurnedSeed.ps1), kept under the panel's name.
    def turn(r):
        return None if r is None else [r[1], r[0], r[3], r[2]]

    # A frame turns as main and rail do: every rect in it transposed - a rect
    # is the frame's only list of four numbers - and its header becomes its
    # left band, its footer its right, in the frame and in each page record
    # it carries. Its note is the series' own page's, said upright.
    def turn_frame(v, top=True):
        if isinstance(v, list) and len(v) == 4 and all(type(x) is int for x in v):
            return turn(v)
        if isinstance(v, list):
            return [turn_frame(x, False) for x in v]
        if isinstance(v, dict):
            swap = _FRAME_TURN if top else {}
            return {swap.get(k, k): turn_frame(x, top and k in _FRAME_PAGES) for k, x in v.items()}
        return v

    def turned_frame(f, size, m):
        t = turn_frame(f)
        if t.get('note'):
            t['note'] = _TURNED_NOTE + t['note']
        return _legal(t, size, spec.touch_minimums(m)[0], spec.dpi(m))
    for series, s in (p.get('panels') or {}).items():
        if series.startswith('_'):
            continue
        for m in s['models']:
            for size in spec.sizes(m):
                pid = spec.panel_id(m, size)
                if tuple(size) == tuple(s['size']) or pid in out:
                    continue
                row = dict(out[spec.panel_id(m, s['size'])])
                # A series with no rail band (rail None) has none turned either.
                row.update(size=list(size), turned=True, main=turn(s['main']), rail=turn(s['rail']),
                           rail_axis={'column': 'row', 'row': 'column'}.get(s['rail_axis']),
                           popup=list(s['popup'])[::-1] if s['popup'] else None, backgrounds={},
                           seed=(s.get('seeds') or {}).get(pid),
                           frame=turned_frame(s['frame'], size, m) if s.get('frame') else None)
                out[pid] = row
    return out


# -- the bundle -----------------------------------------------------------------
_BACKDROPS = {}


def _backdrop(Image, path, size, fit, rgb):
    """One background as the page shows it, over the page color, as a JPEG data
    URI: fit keeps the art's aspect and centres it (GUI Designer's Fill),
    stretch scales each axis (Stretch)."""
    key = (path, tuple(size), fit, tuple(rgb.values()))
    if key not in _BACKDROPS:
        import base64
        import io
        Image.MAX_IMAGE_PIXELS = None
        src = Image.open(path).convert('RGBA')
        w, h = size
        im = Image.new('RGBA', (w, h), (rgb['R'], rgb['G'], rgb['B'], 255))
        if fit == 'stretch':
            im.alpha_composite(src.resize((w, h), Image.Resampling.LANCZOS))
        else:
            s = min(w / src.width, h / src.height)
            sw, sh = max(1, round(src.width * s)), max(1, round(src.height * s))
            im.alpha_composite(src.resize((sw, sh), Image.Resampling.LANCZOS), ((w - sw) // 2, (h - sh) // 2))
        buf = io.BytesIO()
        im.convert('RGB').save(buf, 'JPEG', quality=80)
        _BACKDROPS[key] = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    return _BACKDROPS[key]


def backdrops(p):
    """Each theme's background image as the page shows it, over the page color.

    Keyed '<series>|<theme id>' - one per series and theme, at the series' own
    canvas, drawn as its template draws it - for a profile with a per-panel
    table, else by theme id at the design panel. Embedded in the bundle because a
    canvas copies a system's bundle but not its uploads. Built from Extron's
    resource kit (spec.resolve_image), so a machine without the kit, or without
    Pillow, gets a system whose pages are the page color alone - and says so.
    """
    out = {}
    wanted = [(t['id'], t['file'], tuple(p['size']), 'stretch') for t in themes(p) if t.get('file')]
    if p.get('panels'):
        wanted = [(f'{series}|{tid}', b['file'], tuple(s['size']), s['fit'])
                  for series, s in p['panels'].items()
                  if not series.startswith('_') and s.get('models')
                  for tid, b in s['backgrounds'].items()]
    if not wanted:
        return out
    try:
        from PIL import Image
    except ImportError:
        print('  note: no Pillow - the themes carry no background images')
        return out
    from ..spec import color, resolve_image
    page = next(c['value'] for c in p['colors'] if c['name'] == p['defaults']['page']['background'])
    rgb = color(page)
    for key, file, size, fit in wanted:
        f = resolve_image(file)
        if not f:
            print(f"  note: {file} not found - {key!r} has no background image")
            continue
        out[key] = _backdrop(Image, f, size, fit, rgb)
    return out


# -- the resource kit -------------------------------------------------------------
# The accent colors Extron's kits name their selected images by. A name ends
# `_nsel` unselected, and `-<color>_sel` (or `-<color>-sel`, or `-<color>` with
# no suffix, or `-<color>_<n>` for a level) selected in one accent.
KIT_COLORS = ('light-blue', 'med-blue', 'light-green', 'periwinkle', 'orange', 'gold',
              'red', 'gray')
# Spelled so in Extron's Afterburn kit.
KIT_TYPOS = {'ligh-blue': 'light-blue', 'ornage': 'orange'}
# A space before `.png` is Extron's too: 23 of Shockwave's are named
# '440x440_help_yellow_sel .png', and a stricter pattern dropped them unseen.
_KIT_FILE = re.compile(r'^(\d+x\d+)_([^ ]+) *\.png$', re.I)
_KIT_COLOR = re.compile(r'[-_](' + '|'.join(KIT_COLORS + tuple(KIT_TYPOS)) + r')(?=$|[-_])')


def kit_look(stem, colors=True):
    """A kit file's stem (no size, no .png) -> (icon, look).

    'laptop_nsel' -> ('laptop', 'off'); 'laptop-orange_sel' -> ('laptop',
    'orange'); 'speaker-volume-periwinkle_3' -> ('speaker-volume_3',
    'periwinkle'); 'power' -> ('power', 'plain'); 'stop_sel' -> ('stop', 'sel').
    With `colors` off, a color stays in the icon's name ('r_power_red_sel' ->
    ('r_power_red', 'sel')): in Shockwave's kit it is the button's own color,
    drawn both off and selected, not an accent scheme's.
    """
    look = None
    for suffix, what in (('_nsel', 'off'), ('-nsel', 'off'), ('_sel', 'sel'), ('-sel', 'sel')):
        if stem.endswith(suffix):
            stem, look = stem[:-len(suffix)], what
            break
    # A color wins over the suffix: the kit spells a few selected images
    # `-<color>_nsel` (756x756_dual-display-1-gold_nsel.png).
    m = _KIT_COLOR.search(stem) if colors else None
    if m:
        stem, look = stem[:m.start()] + stem[m.end():], KIT_TYPOS.get(m.group(1), m.group(1))
    return stem, look or 'plain'


def kit_roots(p, part='root'):
    """Every copy of a part of the template's kit on this machine, in resource-
    root order: `root` its buttons, `thumbs` its slider thumbs. More than one
    when vendor/ holds a slice - extracted art, or part of a kit - beside the
    install's whole one."""
    from .. import spec
    if not (p.get('kit') or {}).get(part):
        return []
    return [d for d in (os.path.join(root, *p['kit'][part].split('/'))
                        for root in spec.RESOURCE_ROOTS) if os.path.isdir(d)]


def kit_root(p, part='root'):
    """The first copy of a part of the template's kit, or None."""
    roots = kit_roots(p, part)
    return roots[0] if roots else None


def kit_index(p, part='root'):
    """{'files': {size: {icon: {look: file}}}, 'paths': {file: kit path}}.

    The paths are relative to the resource roots, as a spec's `images` takes
    them. Empty where the kit is not installed.
    """
    files, paths = {}, {}
    outline = (p.get('kit') or {}).get('outline_off')
    # Every root that has the kit, the first winning a name two have: a slice
    # in vendor/ must add to the install's kit, not hide it.
    for root in kit_roots(p, part):
        for d, _, names in sorted(os.walk(root)):
            for f in sorted(names):
                m = _KIT_FILE.match(f)
                if not m or f in paths:
                    continue
                size, stem = m.groups()
                # Shockwave spells one family blue__round beside blue_round.
                icon, look = kit_look(re.sub('_{2,}', '_', stem), colors=not outline)
                # Two files can read as one look: the Afterburn kit has
                # 1224x344_record_red.png beside 1224x344_record_red_sel.png.
                # The selected one is what a state asks for, so it wins, and
                # the other is named rather than dropped silently.
                looks = files.setdefault(size, {}).setdefault(icon, {})
                prev = looks.get(look)
                if prev and prev != f:
                    keep, drop = ((f, prev) if re.search(r'[-_]sel$', stem)
                                  and not re.search(r'[-_]sel\.png$', prev) else (prev, f))
                    print(f'  note: {drop} reads as {size} {icon!r} {look!r}, as {keep} '
                          f'does - {keep} is used')
                    looks[look] = keep
                else:
                    looks[look] = f
                rel = os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/')
                paths[f] = p['kit'][part] + '/' + rel
    if outline:
        # Shockwave's buttons rest dark with a colored ring and light up when
        # selected, so a family's Off is its `_outline` twin: red's is
        # red_outline_nsel, r_power_red's r_power_outline_red_nsel. Its plain
        # red_nsel is a saturated solid no seed button rests in. Gray has no
        # twin and keeps its own. 504x440's share buttons spell it first
        # (outline_share-1b_blue_nsel).
        twin = re.compile(r'^outline_|_outline(?=$|_)')
        for looks in files.values():
            for name in [n for n in looks if twin.search(n)]:
                base = twin.sub('', name)
                if base in looks and 'off' in looks[name]:
                    looks[base]['off'] = looks[name].pop('off')
                    if not looks[name]:
                        del looks[name]
    # Families the size prefix misses, by a prefix of their own the profile
    # names as a size, with its pixels (`size`): Shockwave's whole-device
    # outlines, white_<device>.png in icons/440x440 White, which its hubs'
    # Select a Source tiles draw where its tabs draw the 744x456 glyph
    # <device>_white.
    for size, fam in (((p.get('kit') or {}).get('prefixed') or {}).items() if part == 'root' else ()):
        prefix = fam['prefix']
        for root in kit_roots(p, part):
            for d, _, names in sorted(os.walk(root)):
                for f in sorted(names):
                    if not (f.startswith(prefix) and f.endswith('.png')):
                        continue
                    looks = files.setdefault(size, {}).setdefault(f[len(prefix):-4], {})
                    if 'plain' not in looks:
                        looks['plain'] = f
                        rel = os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/')
                        paths.setdefault(f, p['kit'][part] + '/' + rel)
    # Files the size prefix misses, named by the profile - one file, or one
    # per look: Shockwave's modal Close is icons/440x440 Black/black_close.png
    # at rest and icons/440x440 White/white_close.png pressed.
    for size, named in (((p.get('kit') or {}).get('named') or {}).items() if part == 'root' else ()):
        for icon, want in named.items():
            looks = {}
            for look, name in (want.items() if isinstance(want, dict) else (('plain', want),)):
                path = _kit_file(p, part, name)
                if path:
                    looks[look] = name
                    paths[name] = path
            if looks:
                family = files.setdefault(size, {})
                # A pair the pattern cannot make - Turbulence's outline_01 at
                # rest, round_01 lit - was already filed as two half icons,
                # each drawing its one file in both states. Named as one,
                # neither half is offered.
                mine = set(looks.values())
                for other in [k for k, v in family.items() if k != icon and set(v.values()) <= mine]:
                    del family[other]
                family[icon] = looks
    return {'files': files, 'paths': paths}


def _kit_file(p, part, name):
    """A file's kit path under one part of the kit, whatever its naming - a
    slider's art need not follow the '<W>x<H>_' pattern (Mach's does not)."""
    for root in kit_roots(p, part):
        for d, _, names in os.walk(root):
            if name in names:
                rel = os.path.relpath(os.path.join(d, name), root).replace(os.sep, '/')
                return p['kit'][part] + '/' + rel
    return None


def rail_art(p):
    """{'track': data URI, 'fill': data URI} - a slider's rail drawn from the
    kit's own images, where the template draws it so (Shockwave, Turbulence,
    Mach) rather than as two colors (Afterburn). Empty without Pillow or art."""
    d = (p.get('defaults') or {}).get('slider') or {}
    want = {k: d.get(k + '_image') for k in ('track', 'fill') if d.get(k + '_image')}
    if not want:
        return {}
    try:
        from PIL import Image
    except ImportError:
        return {}
    from ..spec import resolve_image
    out = {}
    for k, name in want.items():
        f = resolve_image(_kit_file(p, 'thumbs', name))
        if f:
            with Image.open(f) as im:
                w = max(8, round(im.width * 400 / max(im.height, 1))) if im.height > im.width else 400
            out[k] = _webp(Image, f, w)
    return out


def extract_sources(p):
    """The files a profile's `kit.extract.from` names, as found on this machine:
    a `seeds/...` path from the repo, or a name pattern matched against
    Extron's TouchLink templates beside each resource root."""
    import glob
    from ..spec import RESOURCE_ROOTS
    repo = os.path.dirname(os.path.dirname(HERE))
    out = []
    for entry in ((p.get('kit') or {}).get('extract') or {}).get('from') or []:
        if entry.startswith('seeds/'):
            f = os.path.join(repo, *entry.split('/'))
            if os.path.exists(f):
                out.append(f)
            continue
        for root in RESOURCE_ROOTS:
            hits = sorted(glob.glob(os.path.join(os.path.dirname(root), 'TouchLink Templates', entry)))
            if hits:
                out += hits
                break
    return out


def extract_images(sources, out):
    """Write every named image resource in `sources` (.gdl or .glt) to `out`.

    Turbulence has no kit beside the others in 1.28's Resources, and the
    library under Sample Projects\\Resources\\Turbulence is a separate one: it
    lacks a fifth of what the seed draws (its source tabs, slider, header and
    footer) and draws the On and Off rings differently. Its seed and six
    TouchLink templates carry the art the panels use. Mach's slider art lives
    only inside its seed. A resource's data is the PNG file itself
    (System.Drawing.Bitmap's Data), so written to disk under a resource root
    it is a kit like any other, and a spec's `images` resolves it. The
    project's own defaults ('Button',
    'Slider Thumb', an .ico) are not kit art and are left behind. The first
    source to name a file wins; returns the files written.
    """
    from ..project import Project
    os.makedirs(out, exist_ok=True)
    written = []
    for src in sources:
        p = Project.open(src)
        for r in p.instances('PBImageResource'):
            name = p.field(r, 'nameField')
            data = p.deref((p.field(r, 'dataField') or {}).get('Data'))
            if not (isinstance(name, str) and name.lower().endswith('.png') and data):
                continue
            path = os.path.join(out, name)
            if os.path.exists(path):
                continue
            with open(path, 'wb') as fh:
                fh.write(bytes(data))
            written.append(name)
    return written


# kit root -> kit_art()'s result. A thousand WebP encodes take most of a
# minute, and a build or a test run asks more than once.
_ART = {}


def slider_thumb(p, scheme):
    """(file, kit path) of the slider thumb for an accent scheme, or None.

    Afterburn's thumb is a kit image in the secondary accent
    (`sliderThumbImageField`), not a color, so a clone keeps its donor's -
    periwinkle, scheme 1 - under every other scheme.
    """
    family = ((p.get('defaults') or {}).get('slider') or {}).get('thumb_image')
    if not family:
        return None
    if family.lower().endswith('.png'):
        # One thumb whatever the accent - Mach, Shockwave and Turbulence.
        f = _kit_file(p, 'thumbs', family)
        return (family, f) if f else None
    index = kit_index(p, 'thumbs')
    for icons in index['files'].values():
        looks = icons.get(family) or {}
        f = looks.get(p['kit']['secondary'].get(scheme))
        if f:
            return f, index['paths'][f]
    return None


def slider_rail(p):
    """{'track_image': (file, kit path), 'fill_image': ...} - a slider's rail,
    where the template draws it from art rather than two colors, for the
    build as rail_art() gives it to the canvas. Only the files found here."""
    d = (p.get('defaults') or {}).get('slider') or {}
    out = {}
    for k in ('track_image', 'fill_image'):
        f = _kit_file(p, 'thumbs', d[k]) if d.get(k) else None
        if f:
            out[k] = (d[k], f)
    return out


def kit_art(p, index):
    """{file: data URI}: each kit image downscaled for the canvas, as WebP.

    In the bundle, not uploaded beside it, because a canvas copies a system's
    bundle but not its other files - the reason backdrops() embeds too. About
    1.8 MB for Afterburn's thousand. Extron's artwork: it goes into the
    owner's private design system only (docs/claude-design.md section 2).
    """
    try:
        from PIL import Image
    except ImportError:
        print("  note: no Pillow - the system carries no kit art, so its icons do not draw")
        return {}
    from ..spec import resolve_image
    key = (p.get('template'), tuple(kit_roots(p)))
    if key in _ART:
        return _ART[key]
    out = _ART[key] = {}
    scale = p['kit'].get('scale') or {}
    for size, icons in index['files'].items():
        w = scale.get(size, 160)
        for looks in icons.values():
            for f in looks.values():
                if f in out:
                    continue
                # Through the resource roots, since a file may come from any.
                out[f] = _webp(Image, resolve_image(index['paths'][f]), w)
    return out


def _webp(Image, path, w):
    import base64
    import io
    im = Image.open(path).convert('RGBA')
    im = im.resize((w, max(1, round(w * im.height / im.width))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'WEBP', quality=80, method=4)
    return 'data:image/webp;base64,' + base64.b64encode(buf.getvalue()).decode()


def thumb_art(p):
    """{scheme id: data URI} - each scheme's slider thumb, from the kit.

    The kit draws the thumb's circle across 65% of its box, with its shadow
    around it, so a 50 px thumb shows a circle of about 32 px - which is what
    the seed's built slider shows. A circle drawn to the whole box was half as
    wide again as the panel's.
    """
    try:
        from PIL import Image
    except ImportError:
        return {}
    from ..spec import resolve_image
    out = {}
    for s in p['schemes']:
        t = slider_thumb(p, s['id'])
        f = resolve_image(t[1]) if t else None
        if f:
            out[s['id']] = _webp(Image, f, 100)
    return out


def _slim_windows(windows, ids=False):
    """A frame's windows as the bundle draws them: each record's rects, its
    surfaces' shape, fill and border, its Close's and buttons' role and rect,
    the sizes its title and message are set in and the lines its message
    takes, whether a window that is a page stands on the photo (`art`) and
    the words a question that is a page says (`text`, the 320's own) -
    not the seed's names, IDs or art, which are the translator's and the
    reader's (about 16 KB of Mach's, which took its bundle past 260 KB). With
    `ids`, its Close's and buttons' seed IDs, which a 320's pages keep."""
    def item(it):
        if not it:
            return None
        out = {'role': it['role'], 'rect': it['rect']}
        if ids and it.get('id') is not None:
            out['id'] = it['id']
        return out

    def slim(w):
        if not w:
            return w
        out = {'rect': w.get('rect'), 'title': w.get('title'), 'close': item(w.get('close')),
               'surfaces': [{k: s.get(k) for k in ('kind', 'rect', 'fill', 'border')} for s in w.get('surfaces') or []]}
        for k in ('message', 'popups', 'pt', 'lines', 'art', 'text'):
            if k in w:
                out[k] = w[k]
        if 'buttons' in w:
            out['buttons'] = [item(b) for b in w['buttons']]
        return out
    if not windows:
        return windows
    return {k: [slim(w) for w in v] if isinstance(v, list) else slim(v) for k, v in windows.items()}


def bundle(p, art=True):
    header = json.dumps({'format': 4, 'namespace': p['namespace'],
                         'components': [{'name': n} for n, _, _ in components(p)]},
                        separators=(',', ':'))
    profile = {k: p[k] for k in ('template', 'namespace', 'model', 'size', 'popup', 'pt',
                                 'touch', 'font', 'schemes', 'colors', 'type', 'borders',
                                 'buttons', 'defaults')}
    profile['themes'] = themes(p)
    profile['image_kind'] = offers_image(p)
    profile['layout'] = p.get('layout') or {}
    profile['spacing'] = p['spacing']
    # Every panel's own regions, minimums and art; empty for a profile with no
    # per-panel table. art=False (the translator's tests) leaves the images out:
    # the probe reads names, never pixels.
    # The measured frame once per series, keyed by series (each row names
    # its own): repeated on every model row it was 190-320 KB a theme, the
    # bundle twice its size. The region components draw from it, growing a
    # slot to the panel's own minimums as they place it, so the rows' legal
    # rects are not carried. Only where the template draws its bars as
    # controls - Afterburn's system draws no region - and only the series
    # the regions draw: a tier A or B series with all five bands, and the
    # hubs and the 320s (below).
    # And only what they read of it: the four bars; the center's popup
    # region and, off a source's popup, its well, title (and a source's with
    # controls), empty state, status, sizes and surfaces, and each device's
    # picture, which a source popup (role="source") draws; and the windows
    # a working page opens, which a modal with a role draws. The ids and the
    # note are the translator's and the reader's.
    rows = models(p)
    profile['models'] = {m: {k: v for k, v in row.items() if k != 'frame'} for m, row in rows.items()}
    bars = (p.get('layout') or {}).get('bars') == 'controls'
    drawn = {row['series'] for row in rows.values() if row.get('tier') in ('A', 'B')}
    profile['frames'] = {series: dict({b: s['frame'][b] for b in ('top', 'left', 'right', 'bottom')},
                                      center={k: s['frame']['center'].get(k)
                                              for k in ('region', 'well', 'title', 'title_controls', 'empty',
                                                        'status', 'pt', 'surfaces', 'pictures')},
                                      windows=_slim_windows(s['frame'].get('windows')))
                         for series, s in (p.get('panels') or {}).items()
                         if bars and series in drawn and s.get('frame')
                         and all(s['frame'].get(b) for b in ('top', 'left', 'right', 'bottom', 'center'))}
    # A hub's (the 520s and 535s): its right menu bar and the header strip
    # over main where it draws one, the popup region filling main with what
    # a source's popup draws and the Volume Level strip beside the bar (its
    # rect, `strip`, and what it shows, `level`), its Select a Source and
    # options grids, and its windows - which the region
    # page, a source popup and a window draw there in the hub's grammar.
    profile['frames'].update({
        series: {'hub': True, 'top': s['frame']['top'], 'right': s['frame']['right'],
                 'center': dict({k: s['frame']['center'].get(k)
                                 for k in ('region', 'title', 'title_controls', 'empty', 'status', 'pt',
                                           'surfaces', 'pictures', 'close', 'level')},
                                strip=next((it['rect'] for it in s['frame']['center'].get('items') or []
                                            if it['role'] == 'popup'), None)),
                 'select': s['frame'].get('select'), 'options': s['frame'].get('options'),
                 'windows': _slim_windows(s['frame'].get('windows'))}
        for series, s in (p.get('panels') or {}).items()
        if bars and series in drawn and series not in profile['frames'] and s.get('frame')
        and s['frame'].get('right') and s['frame'].get('select') and not s['frame'].get('left')
        and not s['frame'].get('bottom')})
    # A 320's (tier C, a page per source, with a strip and no bar, rail or
    # footer): its strip and what stands in it, its home's and its second
    # page's (Back), the centre's first row, headings and steps (`pitch`),
    # the sizes it sets its title, headings and empty state in, the empty
    # state - one label a line where the template sets it so - and More; its
    # windows, which are pages, with the seed IDs of their buttons; and its
    # Volume modal - which the region page, a source popup and a window draw
    # there as pages of their own.
    paged = {row['series'] for row in rows.values() if row.get('tier') == 'C' and not row.get('turned')}
    profile['frames'].update({
        series: {'pages': True, 'top': f['top'], 'home': {'top': f['home']['top']},
                 'second': {'top': f['second']['top'], 'center': {'items': f['second']['center']['items']}},
                 'center': {k: f['center'].get(k) for k in ('rect', 'row', 'headings', 'pitch', 'pt', 'empty',
                                                            'empty_lines', 'items')},
                 'windows': _slim_windows(f.get('windows'), ids=True), 'volume': f.get('volume')}
        for series, f in ((s, v.get('frame')) for s, v in (p.get('panels') or {}).items() if not s.startswith('_'))
        if bars and f and series in paged and series not in profile['frames'] and f.get('top')
        and f.get('home') and f.get('second') and (f.get('center') or {}).get('row')
        and not any(f.get(b) for b in ('left', 'right', 'bottom'))})
    # What the regions draw by default - Volume, Mute, Help, Power, the clock -
    # in the template's own looks and wording.
    profile['regions'] = {k: v for k, v in (p.get('regions') or {}).items() if not k.startswith('_')}
    # The template's own words, which the center and the windows draw.
    profile['writing'] = {k: v for k, v in (p.get('writing') or {}).items()
                          if not k.startswith('_') and k != 'voice'}
    profile['backdrops'] = backdrops(p) if art else {}
    if p.get('kit'):
        index = kit_index(p)
        # Art that comes out of Extron's own files is in neither the install
        # nor a fresh vendor/ until extracted - Turbulence's, Mach's slider.
        extract = (f" - run `python -m gdl.designsys extract {p['template'].lower()}` "
                   f'first' if p['kit'].get('extract') else '')
        if not index['files']:
            # Said aloud: without it the build looks normal, and the system
            # it publishes names no icons and draws none.
            print(f"  note: the {p['template']} kit is not installed here (GUI Designer's "
                  f"install or vendor/){extract} - the system names no icons and draws none")
        # And so is a kit whose buttons are here but not its slider's part:
        # the system publishes with its sliders drawn plain.
        d = (p.get('defaults') or {}).get('slider') or {}
        found = slider_rail(p)
        lacking = [d[k] for k in ('track_image', 'fill_image') if d.get(k) and k not in found]
        if d.get('thumb_image') and not any(slider_thumb(p, s['id']) for s in p['schemes']):
            lacking.append(d['thumb_image'])
        if lacking and index['files']:
            print(f"  note: the {p['template']} slider art ({', '.join(lacking)}) is not on "
                  f'this machine{extract} - the system draws its sliders plain')
        profile['kit'] = dict(p['kit'], files=index['files'],
                              art=kit_art(p, index) if art and index['files'] else {},
                              thumb_art=thumb_art(p) if art else {},
                              rail_art=rail_art(p) if art else {})
    js = _read('bundle.js')
    for mark, value in (('__HEADER__', header),
                        ('__PROFILE__', json.dumps(profile, separators=(',', ':')))):
        if js.count(mark) != 1:
            raise ValueError(f'bundle.js must hold {mark} exactly once')
        js = js.replace(mark, value)
    # Consumers inline the bundle, so either of these would end or escape it.
    if re.search(r'</script|<!--', js, re.I):
        raise ValueError('bundle.js contains a script close or comment opener')
    return js


BUNDLE_CSS = """\
.xgdl { -webkit-font-smoothing: antialiased; }
a.xgdl-button:focus-visible, button.xgdl-button:focus-visible {
  outline: 3px solid var(--accent, #D69B61); outline-offset: 2px;
}
"""


# -- component cards -------------------------------------------------------------
def _x(p, comp, attrs='', body='', style=''):
    s = f' style="{style}"' if style else ''
    return (f'<x-import component-from-global-scope="{p["namespace"]}.{comp}"{attrs}{s}>'
            f'{body}</x-import>')


def _main_words(p):
    m = (p.get('layout') or {}).get('main')
    if not m:
        return 'the whole page.'
    return (f"{m[2]}x{m[3]} at {m[0]},{m[1]} on the {p['size'][0]}x{p['size'][1]} page. "
            + (p['layout'].get('main_note') or ''))


def icon_names(p):
    """{variant: [icon names]} - what `icon` can be on each image variant,
    from the kit on this machine. Empty where the kit is not installed."""
    files = kit_index(p)['files']
    out = {}
    # A variant naming `icons` (a toggle's `toggle`) takes the families that
    # start so, and only them; the others sharing its kit size leave them out.
    # A list names several - Turbulence's rings are round_NN, on, off. An
    # `icon` alone is only what the variant draws unless told otherwise:
    # Shockwave's `button` is gray by default and offers every color.
    claimed, taken = {}, {}
    for k, v in p['buttons'].items():
        if v.get('kit') and v.get('icons'):
            want = v['icons'] if isinstance(v['icons'], str) else tuple(v['icons'])
            claimed[k] = sorted(n for n in files.get(v['kit'], {}) if n.startswith(want))
            # A claim holds at its own size: Turbulence's 900x648 scene
            # pictures share names with its 504x504 source tabs.
            taken.setdefault(v['kit'], set()).update(claimed[k])
    for k, v in p['buttons'].items():
        size = v.get('kit') or (v.get('with_icon') or {}).get('kit')
        if k in claimed:
            out[k] = claimed[k]
        elif size and files.get(size):
            out[k] = sorted(set(files[size]) - taken.get(size, set()))
    return out


def _icons_md(p):
    names = icon_names(p)
    if not names:
        return ('The kit was not installed where this system was built, so it lists no icon '
                'names.')
    return '\n'.join(f"- `{k}`: {', '.join(f'`{n}`' for n in v)}" for k, v in names.items())


def _kit_size(p, size):
    """A kit size's pixels: '1224x344' -> (1224, 344). A family indexed by
    its prefix (`kit.prefixed`) gives its own: Shockwave's `device`, 440x440."""
    fam = ((p.get('kit') or {}).get('prefixed') or {}).get(size)
    if isinstance(fam, dict) and fam.get('size'):
        return tuple(fam['size'])
    return tuple(int(n) for n in size.split('x'))


def _ratio(p, size):
    """'1224x344' -> '3.6:1'."""
    w, h = _kit_size(p, size)
    r = w / h
    return '1:1' if abs(r - 1) < 0.1 else f'{r:.1f}:1'


def _image_buttons(p):
    """[(variant, kit size, caption placement, default icon or None)] for every
    variant that draws a kit image: its own, or with an icon beside a caption."""
    out = []
    for k, v in p['buttons'].items():
        if v.get('kit'):
            out.append((k, v['kit'], v.get('caption'), v.get('icon')))
        elif v.get('with_icon'):
            out.append((k, v['with_icon']['kit'], v['with_icon'].get('caption'), None))
    return out


def _icon_prop(p):
    """The Button README's `icon` line: this template's image variants, and
    how its kit shows state (the profile's own words where it has them)."""
    own = [f"`{k}`" + (f" (default `{v['icon']}`)" if v.get('icon') else '')
           for k, v in p['buttons'].items() if v.get('kit')]
    beside = [f"`{k}`" for k, v in p['buttons'].items() if v.get('with_icon')]
    where = ' - '.join(filter(None, [
        f"for the image variants - {', '.join(own)}" if own else '',
        (f"{'or ' if own else ''}on {', '.join(beside)}, placed with the caption as the "
         f"variant says" if beside else '')]))
    how = (p.get('iconography') or {}).get('icon_prop') or (
        "State 0 draws the kit's image at rest, the others its selected look.")
    return f"an image from {p['template']}'s resource kit, by name, {where}. {how}"


def _example_button(p, key, name, extra=''):
    ex = p['examples'][key]
    r = ex['rect']
    return _x(p, 'Button', f' name="{name}" {ex["attrs"]}{extra}', ex.get('text', name if key == 'source' else ''),
              f'width: {r[2]}px; height: {r[3]}px')


def _panels_eg(p, ms):
    return ' '.join(m for m in ('TLP1035T', 'TLP725T', 'TLP525T', 'TLP320M') if m in ms) or p['model']


def _panels_readme(p):
    """The README's own word on a room's panels. A designer reads the README
    first, and it called every artboard one page of the design panel: with
    `panels` in the Page card alone, a room's other panels went unasked for
    and only the design panel was built."""
    ms = models(p)
    if not ms:
        return ''
    return (f"- **Every panel the room has.** A room often has more than one panel - a table panel and a "
            f"smaller one by the door. Name them all, by model, in `panels` on every Page "
            f"(`panels=\"{_panels_eg(p, ms)}\"`), the panel the canvas is drawn on first: Claude Code builds one "
            f"panel for each, laid out for its own screen from these artboards. Leave the room each needs - "
            f"*Every panel the room has*, below, says how much.\n")


def _model_names(names):
    """'TLP525C/M/T, TLC521M': a model's variants together, a turned panel as
    itself."""
    out = {}
    for n in names:
        m = re.match(r'^(.*?\d+)([CMT]G?)(-\w+)?$', n)
        base, var, turned = (m.group(1), m.group(2), m.group(3) or '') if m else (n, '', '')
        out.setdefault((base, turned), []).append(var)
    return ', '.join(f"{b}{'/'.join(vs)}{t}" for (b, t), vs in out.items())


def _rail_holds(T, rail=None, heading=0):
    """How many touch-sized buttons a hub's rail holds beside the volume, as
    railLayout stacks them: a level between Down and Up where the seed has no
    slider (24 px of level still reads), else a slider at least a touch target
    long; the panel's gap between, centred in the band with that gap's padding.
    `rail` is the band a page leaves it (_room), the panel's own by default;
    `heading` the slot a heading over the volume takes in a column rail
    (_rail_heading), with its gap."""
    r = rail or T.get('rail')
    if not r:
        return None
    col = (T.get('rail_axis') or 'column') != 'row'
    along, cross = (r[3], r[2]) if col else (r[2], r[3])
    t, g = T['touch'], T['gap']
    pad = math.floor(max(0, min(g, (cross - t) / 2)))
    level = T['kinds'].get('slider') is False
    volume = 2 * t + 24 + 2 * g if level else t
    return max(0, math.floor((along - 2 * pad - volume - (heading if col else 0)) / (t + g)))


def _rail_heading(p, T, k):
    """The slot a volume rail's heading takes on panel T, gap and all, as
    railLayout lays a Label: one line of the label type at that panel's type,
    2 px more. Mach's, Shockwave's and Turbulence's Layouts each head their
    volume rail ("Volume"), and the README's count left it out: Shockwave's
    525 rail of a heading, the volume and Mute needed 344 px of its 320."""
    pt = next((x['pt'] for x in p['type'] if x['name'] == p['defaults']['label']['type']), 14)
    size = max(T['floor'], _js_round(pt * k * 2) / 2)
    return math.ceil(size * p['pt'] * 1.2) + 2 + T['gap']


def _js_round(x):
    """Math.round: halves up, where Python's round() goes to the even."""
    return math.floor(x + 0.5)


def _hub_bands(d_lo, d_hi, d_size, t_lo, t_hi, t_size, k, min_lo, min_hi):
    """bundle.js hubBands on one axis - (lo, hi) of the target's main: a band
    the design panel has beside main and the target has not is cut from the
    target's main at the page's scale, that depth at most a quarter of main,
    and the band then at least as deep as what it holds (`min_lo`, `min_hi`)."""
    lo, hi, quarter = t_lo, t_hi, (t_hi - t_lo) / 4
    if d_lo >= 1 and t_lo < 1:
        lo = _js_round(max(min(d_lo * k, quarter), min_lo))
    if d_size - d_hi >= 1 and t_size - t_hi < 1:
        hi = _js_round(t_size - max(min((d_size - d_hi) * k, t_size - t_hi + quarter), min_hi))
    return lo, hi


def _room(p, D, T, model=None):
    """(main, rail) a page lays out in on panel T, as bundle.js panelPage cuts
    them. Where the bars are controls (Mach, Shockwave, Turbulence) the design
    panel's header, footer and column are carved from a main that reaches the
    screen's edge - a hub's - and the rail keeps to what is left between the
    header and the footer. A band that holds a button is at least the touch
    minimum deep, and one that holds a Group as deep as its cells: the README
    assumes a button in each, and in a header the Layout fills with source
    tabs those tabs (the profile's `layout.hub_header`, measured), so the room
    it gives is the least a page drawn to the Layout has there. It took the
    uncut main, and promised Mach's 525 0.7 and three buttons beside the
    volume where a page has 0.51 to 0.55 and one; then a button in every bar,
    and Turbulence's 525 a button beside its volume where its own source tabs
    leave none."""
    main, rail = T['main'], T.get('rail')
    if ((p.get('layout') or {}).get('bars') != 'controls' or T is D or T['tier'] == 'C'
            or not D.get('main') or not main):
        return main, rail
    (dw, dh), (tw, th), dm = D['size'], T['size'], D['main']
    k = min(tw / dw, th / dh)
    head = (((p.get('layout') or {}).get('hub_header') or {}).get('depth') or {}).get(model, 0)
    x0, x1 = _hub_bands(dm[0], dm[0] + dm[2], dw, main[0], main[0] + main[2], tw, k, T['touch'], T['touch'])
    y0, y1 = _hub_bands(dm[1], dm[1] + dm[3], dh, main[1], main[1] + main[3], th, k,
                        max(T['touch'], head), T['touch'])
    if rail and (T.get('rail_axis') or 'column') != 'row':
        r0, r1 = max(rail[1], y0), min(rail[1] + rail[3], y1)
        rail = [rail[0], r0, rail[2], r1 - r0]
    return [x0, y0, x1 - x0, y1 - y0], rail


def _panel_rooms(p):
    """The README's table of the panels a system serves: those whose room is
    the same in one row, the design panel's first - [(names, row, k, rail)].
    `k` is the scale from the design panel's main region to the one a page has
    on that panel (_room), which a control in main takes (bundle.js
    scaleLayout, cutRect); a control then grows to the panel's touch minimum
    and a word to its type floor. `rail` is the rail a page leaves it."""
    ms = models(p)
    D = ms.get(p['model'])
    if not D:
        return []
    rows = {}
    for m, T in ms.items():
        main, rail = _room(p, D, T, m)
        k = min(main[2] / D['main'][2], main[3] / D['main'][3])
        key = (T['series'], tuple(T['size']), T['touch'], T['gap'], T['floor'], T['tier'], round(k, 2),
               tuple(rail or ()))
        rows.setdefault(key, (m, T, k, rail, []))[4].append(m)
    out = [(names, T, k, rail) for _, T, k, rail, names in rows.values()]
    out.sort(key=lambda r: p['model'] not in r[0])
    return out


def _panels_section(p):
    """`## Every panel the room has`: what a designer leaves room for, panel by
    panel. Three designers of a two-panel room drew the 1035 snug, and the 525
    refused every artboard: its positions scale down, its controls grow to
    66 px and its words to 18 pt. One read the bundle to find out how much, and
    its room built on both."""
    rooms = _panel_rooms(p)
    if not rooms:
        return ''
    lines = []
    for names, T, k, rail in rooms:
        drawn = p['model'] in names
        # Positions scale by k there and a control grows to the touch minimum
        # about where it is: on this canvas that is a control of touch / k,
        # and the gap there is gap / k here.
        smallest, apart = math.ceil(T['touch'] / k), math.ceil(T['gap'] / k)
        # The canvas's smallest type is 14 pt, the floor the design panel holds.
        words = max(T['floor'], round(14 * k * 2) / 2) / 14 / k
        if drawn:
            kind = 'drawn here'
        elif T['tier'] == 'C':
            # How much the rows hold: round four's Afterburn designer could
            # only infer it from which pages the 320 refused.
            deep, across, paged = _rows_room(p, T)
            kind = (f"rows: {deep} px of them, {across} across"
                    + (f" - {paged} on a page that goes on" if paged else ''))
        elif T['tier'] == 'B':
            # The bar themes head their volume rail; Afterburn's has none.
            headed = (p.get('layout') or {}).get('bars') == 'controls'
            col = (T.get('rail_axis') or 'column') != 'row'
            heading = _rail_heading(p, T, min(T['size'][0] / p['size'][0], T['size'][1] / p['size'][1])) \
                if headed and col else 0
            n = _rail_holds(T, rail, heading)
            if n is None:
                kind = 'hub'
            elif n == 0:
                kind = 'hub: its rail holds ' + ('a heading and the volume' if heading else 'the volume alone')
            else:
                kind = (f"hub: its rail holds {'a heading, ' if heading else ''}the volume and {n} "
                        f"button{'' if n == 1 else 's'}"
                        # A row rail's heading takes its word's width, which only the bundle measures.
                        + (' - fewer beside a heading' if headed and not col else ''))
        else:
            kind = 'scaled'
        # A panel that lays its controls out again, in rows, sizes each to what
        # it holds there (bundle.js flowLayout): no distance or room to keep.
        room = ('- | -' if kind.startswith('rows') else
                f"{smallest} px, {apart} px | {'1x' if words < 1.05 else f'{words:.1f}x'}")
        lines.append(f"| {_model_names(names)} | {T['size'][0]}x{T['size'][1]} | {kind} | "
                     f"{1 if drawn else round(k, 2):g} | {T['touch']} px, {T['gap']} px | {T['floor']} pt | "
                     f"{room} |")
    return (f"## Every panel the room has\n\n"
            f"Nothing is drawn twice: each panel the room lists is laid out from these artboards for its own "
            f"screen. Every position and box is scaled to it (Scale); each control then grows to its touch "
            f"minimum and every word to its type floor, which on a small panel is more than the scale leaves. "
            f"So for every panel the room lists, leave room here for what grows there:\n\n"
            f"- **Controls.** *Here* is that panel's touch minimum and gap measured on this canvas: count any "
            f"button or slider smaller than the first as that size, centred where it is - there it grows to "
            f"the touch minimum - and keep any two the second apart.\n"
            f"- **Words.** A label's or caption's box needs *Words* times the width its words take here, and "
            f"room to be as much taller. Keep copy short. A button needs it for its widest caption - a state's "
            f"own `text` too (Mics Muted). Write Help in your own words as one Label of a few short sentences, "
            f"its box with room for them at the room's largest *Words*: a stack of one-line Labels, each a line "
            f"deep here, overflows where the type is larger (the 525's 18 pt), and where they run into each "
            f"other they are refused.\n"
            f"- **Sets.** Put a set of like controls - sources, presets - in a `Group`: its members share one "
            f"cell on every panel, and it pages them where they do not fit, its Previous and Next under them "
            f"or, in a box one cell deep, at the row's ends - as arrows where their words leave no room. In a "
            f"modal or a popup a Group cannot page - its "
            f"pages would be popups, which only a page shows - so give its box room for all its members on "
            f"every large and mid-size panel there. The `Rail` stacks its controls at each panel's gap. Loose controls only "
            f"scale.\n"
            f"- **Hubs** are one page of main controls beside a rail. Where the seed has no slider, a slider "
            f"is a level between `-` and `+`, and the rail holds what the table says - a heading over the "
            f"volume counted in a column rail where the template heads it, and in a row rail a heading takes "
            f"its word's width - and a button there fills the rail across, its caption needing only the "
            f"button's own padding and border; a "
            f"`Group` on a page shows in a popup in its own box, which the control program shows."
            + (" The header, footer and side column drawn beside main here are cut from a hub's main, and "
               "its rail keeps between them; a bar that holds a button is at least the touch minimum deep, "
               "and one that holds a Group as deep as its cells - the table assumes a button in each"
               + (", and in the header the Layout's own source tabs with the seed's captions (longer "
                  "captions are deeper)" if (p.get('layout') or {}).get('hub_header') else '') + "."
               # That is a Page of bars and loose controls. A region page is
               # the hub's own: its header is the template's title strip.
               + (" A region page is drawn in the hub's own grammar instead, its header the template's title "
                  "strip (the Header's README)." if _regions(p) else '')
               if (p.get('layout') or {}).get('bars') == 'controls' else '') + "\n"
            + _rows_md(p) + "\n\n"
            f"Set a Page's `preview` to a panel to see an artboard as that panel draws it: a control that "
            f"collides with its neighbour, or a box its words overflow, is outlined.\n\n"
            f"| Panels | Screen | Kind | Scale | Touch, gap | Type floor | Here | Words |\n"
            f"|---|---|---|---|---|---|---|---|\n" + '\n'.join(lines) + '\n\n')


def _rows_room(p, T):
    """(deep, across, paged): what a panel of rows (tier C) holds, as bundle.js
    lays a page out there - the depth of rows its main region holds, 2 px clear
    of its top and foot, and the width of a row, the panel's gap clear of each
    side (flowRows); and, where the theme draws its bars as controls and a page
    goes on over pages of its own, the depth each keeps above its Previous and
    Next (overPages), else None. Afterburn's page does not go on (rowsPage)."""
    main = T['main']
    deep, across = main[3] - 4, main[2] - 2 * T['gap']
    paged = deep - T['touch'] - T['gap'] if (p.get('layout') or {}).get('bars') == 'controls' else None
    return deep, across, paged


def _rows_md(p):
    """The *Rows* line of *Every panel the room has*: how a panel of rows takes
    a page - the order, a row's depth, the gaps, and what happens past what it
    holds. It said only that the panel lays the page out again, in rows, and
    round four's Afterburn designer revised three times guessing the order,
    how many rows fit and how tall a heading is, from which pages the 320
    refused."""
    ms = models(p)
    small = ms.get('TLP320M') or next((T for T in ms.values() if T['tier'] == 'C'), None)
    if not small:
        return "- **Rows**: the panel lays the page's controls out again, in rows."
    line = math.ceil(small['floor'] * p['pt'] * 1.2) + 2
    out = ("- **Rows** (the Kind *rows*): the panel lays the page's controls out again, in rows across its main "
           "region, each control at what it needs there - a button, or the one button a `Group` is there, the "
           f"touch minimum deep; a line of words one line at the type floor deep ({line} px on the 320), whatever "
           "its box here; a popup region its popups' size - with the panel's gap between two rows where either "
           "holds a button, or both a Group, and 2 px otherwise, the rows centred 2 px clear of main's top and "
           "foot. What you place level is a row: a control joins the row above while its middle is inside it, a "
           "row wider than the screen wraps, and words wider than it break into lines. *Kind* says how deep a "
           "stack of rows main holds and how wide a row, so count a page's rows against it.")
    if (p.get('layout') or {}).get('bars') == 'controls':
        return out + (" The Page's own controls, its `MainArea`'s and its `Rail`'s are one set of rows, region by "
                      "region (Page's `panels`); rows one screen cannot hold go on over pages of their own, with "
                      "Previous and Next at main's foot, a heading - a Label whose foot meets the row under it - "
                      "going on with the row it heads.")
    # The panels of rows whose seed has no standard popup to clone (`kinds`):
    # Afterburn's 320, whose template gives each source a page of its own.
    bare = [m for m, T in ms.items() if T['tier'] == 'C' and not (T.get('kinds') or {}).get('popup', True)]
    # The source's pages its frame was measured off (the 320's Doc Cam 1, 2).
    fr = (ms[bare[0]].get('frame') or {}) if bare else {}
    seen = _say([x for x in (fr.get('page'), (fr.get('second') or {}).get('page')) if x])
    return out + (
        " The Page's own controls and its `MainArea`'s are one set of rows, in main over the row the `Rail` "
        "runs across: the main area's first, then the Page's own column by column - the left rail's, then any "
        "right of main - each top to bottom in the order you placed it. Where a control stands in its column "
        "decides only its order there, so Start's button stands where the Layout puts it. A heading - a Label "
        f"whose foot meets the `Group` under it, within {p['spacing']} px - stands at that Group's left, in its "
        "row, since the Group there is the one button that opens its pages, captioned with its `title`; a "
        "heading over loose controls keeps its own row over theirs. A `Line` stands across the gap between the "
        "rows it was drawn between, 2 px clear of each. Where the rows need more than main holds, a row of a "
        "side column stands beside the first earlier row of another column it fits beside. Past that the page "
        "is refused, by name, with the depth its rows need one under another and, where a row moved, beside: "
        "it does not go on over pages of its own, as a Group does, with Back, Previous and Next - so put a set "
        "in a Group."
        + (f" On the {_model_names(bare)}, whose seed has no standard popup, a popup is a "
           "page of its own, the way that seed draws each source" + (f" (its {seen})" if seen else '')
           + ": what you put in it stands in rows in "
           "main, laid out from the popup's own box as a page's are, and a Back at the foot's left - where a "
           "Group's pages stand theirs - goes back to the page whose button shows it. A `PopupRegion` has "
           "nothing to show there, and is left off." if bare else ''))


def _panels_props(p):
    """The Page's `panels` and `preview` lines, for a system with a per-panel table."""
    ms = models(p)
    if not ms:
        return ''
    eg = _panels_eg(p, ms)
    # A panel this system draws either way up is named for its way up too.
    turned = sorted(m for m in ms if '-' in m)
    either = (f", and one turned from its own canvas as model-Portrait or model-Landscape - "
              f"{', '.join(f'`{t}`' for t in turned)}" if turned else '')
    plain = [t for t in turned if ms[t].get('turned')]
    if plain:
        either += (f". Extron draws no template for {', '.join(f'`{t}`' for t in plain)}: each is its "
                   f"series turned - its main region and rail transposed - on the page colour, with no "
                   f"background art")
    return (f"- `panels`: every panel the room has, by model - `panels=\"{eg}\"`{either}. The first is the panel the "
            f"canvas is drawn on; the translator builds one panel for each, each sized for its own screen "
            f"(docs/claude-design.md). The same on every artboard.\n"
            f"- `preview`: one of `panels` to draw this artboard as that panel derives it - its size, its "
            f"background, its main region, every control at that panel's touch minimum and type floor. "
            f"Design on the first panel, preview the others.\n" + _panels_bars(p))


def _panels_bars(p):
    """How a Page's own bars carry to other panels - for a system that draws
    them as controls (`layout.bars`). Afterburn's chrome is its background
    art, and its pages' own children scale whole."""
    if (p.get('layout') or {}).get('bars') != 'controls':
        return ''
    # The hubs off the profile's own table: a series whose main region reaches
    # its panel's top and bottom - Mach's and Shockwave's 520 and 535,
    # Turbulence's 520 alone.
    hubs = sorted(_series_named(p, lambda s: s.get('tier') != 'C' and s.get('main') and s['main'][1] <= 0
                                and s['main'][1] + s['main'][3] >= s['size'][1]),
                  key=lambda n: int(n.split()[0]) if n.split()[0].isdigit() else 0)
    hub = (f" On a hub, whose main area reaches its top and bottom ({_the_series(hubs)}), the header, "
           f"the footer and a column beside main get bands of their own carved from main, at the panel's "
           f"scale - the touch minimum deep where they hold a button, and as deep as a Group's cells where "
           f"they hold one - a bar or card drawn as a Panel growing with them to hold what was drawn in it - and "
           f"MainArea and the Rail keep to what those bands leave." if hubs else '')
    return ("- On a large or mid-size panel other than the one drawn, what sits on the Page itself rather "
            "than in MainArea or the Rail - a bar across the top or bottom, the buttons at its ends, a "
            "modal's window - keeps to that panel's own bands: a bar drawn edge to edge spans it at its own "
            "depth, and a button flush with a bar's end and the main area's edge fills that end. Draw a bar "
            f"edge to edge where its band in the Layout runs edge to edge.{hub}{_small_pages(p)}\n")


def _back_where(p):
    """Where Extron's own small pages put Back on a source's second page, off
    the 320's frame: Mach's ends the title strip; Shockwave's and
    Turbulence's stand where More stood on the first page, at the foot."""
    for name, s in (p.get('panels') or {}).items():
        sec = (s.get('frame') or {}).get('second') if isinstance(s, dict) and not name.startswith('_') else None
        if isinstance(sec, dict) and any(i.get('role') == 'back' for i in (sec.get('center') or {}).get('items') or ()):
            return 'where More stood'
    return "at the strip's end"


def _small_pages(p):
    """What a bar theme's Page becomes on its small panels (overPages in the
    bundle), the strip's depth off the profile's own table."""
    small = [s for name, s in (p.get('panels') or {}).items()
             if not name.startswith('_') and s.get('models') and s.get('tier') == 'C' and s.get('main')]
    if not small:
        return ' On a small panel what the Page holds reflows into rows.'
    strip = small[0]['main'][1]
    return (f" On a small panel ({_the_series(_series_named(p, lambda s: s.get('tier') == 'C'))}) a Page is "
            f"drawn as Extron's own small templates draw theirs: its header bar becomes the {strip} px title "
            f"strip, with the labels on it where they fit there, and the rest - the Page's own controls, "
            f"MainArea's and the Rail's - reflows into rows under it, region by region: the header's, main's, "
            f"the columns' left to right, then the footer's, each in the order you placed them. Rows one "
            f"screen cannot hold go on over pages of their own - Home 2, Home 3 - each under the strip, with "
            f"Previous and Next at its foot; a row never splits, and a heading goes on with the row it heads. "
            f"That reflow is the toolkit's: Extron's own "
            f"small pages go on by More at the foot and come back by Back {_back_where(p)}, and a region page "
            f"is drawn that way (the region components' READMEs). Words wider than the screen break into "
            f"lines. A modal holds one screen there: say in it what fits one.")


def _panels_main(p):
    if not models(p):
        return ''
    return (" On a Page that lists `panels`, it is each panel's own main region, and what is in it is laid "
            "out for that panel: scaled as the region is on a large or mid-size screen, and on a small one "
            "(the 320's) reflowed into rows in the order you placed them"
            + (" - a bar theme's with the Page's, by region, and over pages of their own where they do not "
               "fit (Page)" if (p.get('layout') or {}).get('bars') == 'controls' else
               # One set with the Page's own: laid out apart, each over the
               # screen, the left rail's heading landed on Start.
               " - with the Page's own controls, the main area's first (the README's *Every panel the room "
               "has*, Rows)")
            + ". Leave room: a caption grows to the "
            "panel's type floor, and a control that collides with its neighbour is refused, by name.")


_ROLE_WORDS = {'heading': 'its heading', 'volume': 'the volume', 'mute': 'Mute', 'help': 'Help', 'power': 'Power',
               'audio': 'Audio Control', 'settings': 'Settings', 'mode': 'the mode launcher', 'clock': 'the clock'}


def _right_roles(p):
    """What the design panel's template stands in its right column, by role,
    off its frame: [] where it has none measured."""
    F = (models(p).get(p['model']) or {}).get('frame') or {}
    right = F.get('right') if isinstance(F.get('right'), dict) else {}
    return list(dict.fromkeys(i['role'] for i in (right or {}).get('items') or () if i.get('role')))


def _rail_words(p):
    """The Rail README's first sentence: the column the template keeps, off
    the frame. It said 'volume, mute, help, power ... as Mach's own pages
    put them on the right' of every theme, and Mach's right column holds the
    volume and Mute, its Help and Power the footer's."""
    roles = _right_roles(p)
    if not roles:
        return "The page's column of system controls beside the main region."
    said = [_ROLE_WORDS.get(r, r.replace('-', ' ')) for r in roles]
    said = ', '.join(said[:-1]) + ' and ' + said[-1] if len(said) > 1 else said[0]
    regions = _regions(p)
    return ("The page's column of system controls beside the main region. On "
            f"{p['template']}'s working page the right column holds {said}, as its frame measures it (the "
            "README's Layout)"
            + (", and a region page draws it as its `RightRail`: a Rail is for a page that is not one."
               if regions else '.'))


def _series_named(p, test):
    """The profile's series that pass `test`, in its own order, named without
    the theme: ['520', '300 Portrait']."""
    return [name[len(p['template']):].strip().removesuffix(' Series')
            for name, s in (p.get('panels') or {}).items()
            if not name.startswith('_') and s.get('models') and test(s)]


def _the_series(names):
    """'the 520, 320 and 300 Portrait Series'."""
    return 'the ' + (names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]) + ' Series'


def _panels_rail(p):
    if not models(p):
        return ' Give it a position and size with its own style.'
    # Each from the profile's own table: Afterburn's 320 runs its rail below,
    # Mach's has none at all.
    below = _series_named(p, lambda s: s['rail'] and s['rail_axis'] == 'row')
    none = _series_named(p, lambda s: not s['rail'])
    level = _series_named(p, lambda s: (s.get('kinds') or {}).get('slider') is False)
    text = (" On a Page that lists `panels`, give the Rail no position or size: it stands in each panel's own "
            "rail, the panel the canvas is drawn on too, whatever you give it - beside the main region")
    text += (f", or below it, running across, on a panel too small to have one beside it ({_the_series(below)})."
             if below else '.')
    if none:
        one = len(none) == 1
        text += (f" T{_the_series(none)[1:]} {'draws' if one else 'draw'} no rail band - "
                 f"{'its template keeps' if one else 'their templates keep'} nothing on screen from page to "
                 f"page - so ")
        text += ("on one of its panels what a Rail holds joins the Page's rows (Page)."
                 if (p.get('layout') or {}).get('bars') == 'controls' else
                 f"a Rail on one of {'its' if one else 'their'} panels is refused: put what it holds in the "
                 f"main region.")
    if level:
        text += (f" On a panel whose seed cannot build a slider - {_the_series(level)} - a Slider in it becomes "
                 f"a Level with Down and Up buttons at its ends, stacked along the rail, the level taking the "
                 f"length the rest leave.")
    return text


def _layout_note(p, key):
    """A sentence or more the profile's `layout` adds to a README (`rail_note`:
    where the template's own column is not the Rail's stack), led by a space,
    or '' where it has none."""
    note = (p.get('layout') or {}).get(key)
    return f' {note}' if note else ''


def _clock_footer(p):
    """The clock the template's own footer draws, where a region Footer draws
    it: the default `time` is the component's, not the template's."""
    fmt = ((p.get('regions') or {}).get('clock') or {}).get('format')
    if not _regions(p) or not fmt:
        return ''
    return (f" The default `time` is this component's: {p['template']}'s footer draws the date and time, "
            f"`{fmt}`, which the `Footer` draws by itself.")


def _main_example(p):
    """The MainArea README's example: what the template stands in its main
    region, placed relative to it - the profile's `examples.main` where its
    sources are not there (Shockwave's are tabs in its header: its Start
    button is), else its source button. It was a 'Select a Source' heading
    190 px down main, which Mach writes in its header bar."""
    ex, main = p['examples'].get('main') or p['examples']['source'], (p.get('layout') or {}).get('main') or [0, 0]
    r = ex['rect']
    return _x(p, ex.get('component', 'Button'), f' name="{ex.get("name", "Laptop")}" {ex["attrs"]}', ex.get('text', ''),
              f'position: absolute; left: {r[0] - main[0]}px; top: {r[1] - main[1]}px; '
              f'width: {r[2]}px; height: {r[3]}px')


def _group_example(p):
    """(cell, gap) of the Group README's example: the profile's own
    (`examples.group`, its template's source row) where it has one."""
    g = (p.get('examples') or {}).get('group') or {}
    return g.get('cell', '110x110'), g.get('gap', 55)


def _design_frame(p):
    return (models(p).get(p['model']) or {}).get('frame') or {}


def _panel_example(p):
    """The Panel README's example: the profile's own (`examples.panel`: what
    the template draws with a Panel, Turbulence's a modal's card - its header
    is art, not a Panel), else the template's own header bar where its frame
    measures one - its depth and the default fill and border - else a bar in
    the default look."""
    own = (p.get('examples') or {}).get('panel')
    if own:
        return _x(p, 'Panel', f' name="{own["name"]}" fill="{own["fill"]}" border="{own["border"]}"', '',
                  f"width: {own['size'][0]}px; height: {own['size'][1]}px")
    top = _design_frame(p).get('top')
    d = p['defaults']['panel']
    h = top['rect'][3] if isinstance(top, dict) else 112
    return _x(p, 'Panel', f' name="TopBar" fill="{d["fill"]}" border="{d["border"]}"', '',
              f"width: {p['size'][0]}px; height: {h}px")


def _region_example(p):
    """(width, height) of the PopupRegion README's example: the template's own
    popup region where its frame measures one."""
    c = _design_frame(p).get('center')
    r = c.get('region') if isinstance(c, dict) else None
    return (r[2], r[3]) if r else (880, 525)


def _clock_none(p):
    """The series whose seed has no date and time control to clone, from the
    profile's own table: a Clock is refused on their panels."""
    none = _series_named(p, lambda s: (s.get('kinds') or {}).get('datetime') is False)
    if not none:
        return ''
    return (f" {_the_series(none)[0].upper()}{_the_series(none)[1:]}'s seed has no date and time control to "
            f"clone, so a Clock on a Page that lists one of its panels is refused there: a room with that "
            f"panel shows the time in words the program sets, a Label, or not at all.")


def _panels_slider(p):
    """Where a Page's own Slider is a level, from the profile's own table."""
    level = _series_named(p, lambda s: (s.get('kinds') or {}).get('slider') is False) if models(p) else None
    if not level:
        return ''
    return (f" On a Page that lists `panels`, on a panel whose seed cannot build a slider - "
            f"{_the_series(level)} - it becomes a Level with Up and Down buttons beside it, one at each end, so "
            f"the level keeps the slider's length: draw it as long as the volume should read there. Extron's own "
            f"smaller templates stand Up, Down and Mute beside their volume level, the level the length of the "
            f"column. Up and Down take the look of the button nearest the slider where that look can draw them. "
            f"A Slider in a Rail is stacked along it instead (Rail).")


def _level_where(p):
    """Where a Level cannot be built, from the profile's own table: a level is
    cloned from the panel's seed, and the series whose `kinds` say a slider
    and no level - the panel each canvas is drawn on among them - have none."""
    if not models(p):
        return ''
    none = _series_named(p, lambda s: (s.get('kinds') or {}).get('level') is False
                         and (s.get('kinds') or {}).get('slider') is not False)
    if not none:
        return ''
    drawn = ((models(p).get(p['model']) or {}).get('kinds') or {}).get('level') is False
    return (f" A Level is cloned from the panel's seed, and on {_the_series(none)} the seed carries a slider "
            f"and no level{' - the panel the canvas is drawn on among them -' if drawn else ','} so a Level "
            f"drawn for one of those panels is named on the canvas: use a Slider there.")


def _group_title_320(p):
    """A Group's title on the 320, where a region system draws a source's and a
    window's Groups as its columns (bundle.js columnsOf); Afterburn's, the one
    button that opens its pages, with the heading over it at its left
    (bundle.js rowsPage)."""
    if not _regions(p):
        return (" On a page on the 320 it is the button that opens its pages, captioned with it, and a Label "
                "heading the group - its foot at the group's top - stands at that button's left, in its row "
                "(the README's *Every panel the room has*, Rows)." if models(p) else '')
    return (" In a source popup or a window it is drawn on the 320 alone, as its column's heading, whose room "
            "the system's README gives (*Words on the 320*): make it one short word (Presets, not Camera "
            "Presets), and put no Label over the group for it.")


def _panels_group(p):
    if not models(p):
        return ''
    return ("\n\nOn a Page that lists `panels`, every cell on each panel is as big as its largest member "
            "needs - the touch minimum, its caption at the panel's type - and then the group is laid out by "
            "the panel's size: on a large screen in place, or, if its members do not fit, as pages in its box "
            "with Previous and Next - under its cells, or at the row's ends where its box is one cell deep, "
            "arrows there where their words leave no room; on "
            "a mid-size one (the 525's) always as popups in its box, the region the program shows them in; on "
            "a small one (the 320's) as one button that opens pages of their own, each with Back - a joined "
            "group too, where its one row is wider than the screen. In a modal "
            "or a popup on a large or mid-size panel it is laid out in place, since a popup shows no popups. Previous, Next, "
            "Back and that button are navigation the program handles - the ID map lists them. A group that "
            "cannot fit even so is named, never dropped.")


def component_docs(p):
    """{name: README markdown} - guidelines a designer reads before mounting."""
    t = p['template']
    # The seed's own size, where the profile records it: a designer drawing a
    # tile smaller than the template does gets a caption that spills.
    variants = '\n'.join(f"- `{k}`: {v['usage']}"
                         + (' The seed draws it {}x{}.'.format(*v['size']) if v.get('size') else '')
                         for k, v in p['buttons'].items())
    types = [s['name'] for s in p['type']]
    by_type = {s['name']: s for s in p['type']}
    button_types = ' or '.join(
        f"`{n}` ({by_type[n]['pt']:g} pt{' bold' if by_type[n]['weight'] >= 600 else ''}"
        f"{', default' if n == p['defaults']['button']['type'] else ''})"
        for n in types if n.startswith('button'))
    sub = 'subheading' if 'subheading' in types else 'heading' if 'heading' in types else types[0]
    tokens = [c['name'] for c in p['colors']]
    label_colors = ', '.join(f'`{n}`' for n in ('text', 'text-secondary', 'accent', 'ink') if n in tokens)
    shapes = ', '.join(f"`{k}` {_ratio(p, size)}" for k, size, _, _ in _image_buttons(p))
    sl = p['defaults']['slider']
    # As wide as it is drawn: a Rail draws a slider 54 px across on the
    # drawn panel (bundle.js railLayout), the regions at the touch minimum.
    slider_w = max(50, sl['thumb'], p['touch'], 54 if not _regions(p) else 0)
    if str(sl.get('thumb_image', '')).lower().endswith('.png'):
        thumb_words = (f"and the template's own thumb image, `thumb` px across (default {sl['thumb']})"
                       + (f" and {sl['thumb_height']} along the rail" if sl.get('thumb_height') else ''))
    else:
        thumb_words = (f"and a round thumb in `{sl['thumb_color']}` whose box is `thumb` px (default "
                       f"{sl['thumb']}) - the circle itself about two-thirds of that, with a shadow round "
                       f"it, as the panel draws it")
    if sl.get('track_image') and sl.get('fill_image'):
        # Mach, Shockwave and Turbulence draw the rail from kit art, on the canvas and the panel alike: it was
        # a rounded rail with its filled part in a color, which none of the three draws.
        rail_words = (f"its kit's rail art - `{sl['track_image']}` for the empty rail and "
                      f"`{sl['fill_image']}` over it as far as the value - `track` px wide (default {sl['track']}) "
                      f"down the middle of the control's box,")
        fill_words = ''
    else:
        rail_words = (f"a rounded rail `track` px wide (default {sl['track']}) down the middle of the control's "
                      f"box, the rail's filled part in `{sl['value']}`,")
        fill_words = (f" `fill`: the rail's empty part, default `{sl['fill']}` - on a `raised` panel use "
                      f"`page`.")
    return {
        'Page': f"""# Page

The root of every artboard: one Page per artboard, holding everything on it. It is one page or popup of the panel, drawn at the panel's size and in the {t} background.

Props:
- `name`: what the page or popup is called on the panel. The control program shows it by this name, so make it unique and plain: `Home`, `Help`, `Confirm Room Off`.
- `kind`: `page` (default, {p['size'][0]}x{p['size'][1]}), {_kind_words(p)}.
- `group`: a popup's group. A standard popup appears where a page has a PopupRegion for its group.
- `start="true"`: the page the panel boots into. One page only; without it, the first artboard.
- `reached-by="program"`: the control program shows this page by itself - an incoming call - so no button has to lead to it.
- `theme`: {', '.join(f'`{th["id"]}`' for th in themes(p))} - {('the background image and accent scheme pairing, ' if len(p['schemes']) > 1 else 'the background photograph, ') if p.get('themes') else ''}{p.get('themes_note') or 'the same on every artboard'}. `scheme` swaps the accent scheme alone: {', '.join(f'`{s["id"]}`' for s in p['schemes'])}.
- `does`: what the page is for, in a sentence, for the programmer.
{_panels_props(p)}{_roles_props(p)}
Place controls inside it with absolute positions or with flex and grid containers: containers that paint nothing are fine. Anything that paints and is not one of these components is not built.

```html
{_x(p, 'Page', ' name="Home" start="true"', '...')}
```
""",
        'MainArea': f"""# MainArea

The {t} page's main region, as a layout container: {_main_words(p)} It paints nothing and is not a control - the page draws the region - so put the page's main task inside it, positioned relative to it or with flex and grid.{_panels_main(p)}

```html
{_x(p, 'MainArea', '', chr(10) + '  ' + _main_example(p) + chr(10))}
```
""",
        'Rail': f"""# Rail

{_rail_words(p)} Its children need no positions: they stack down it in order, each as big as it needs to be on the panel, and a Slider or Level takes the length the others leave. It paints nothing and is not a control. A Label or a Clock in it is one line deep and as wide as the rail (as long as its words, on a rail that runs across), so a heading such as Volume goes above the Slider it names.{_panels_rail(p)}{_layout_note(p, 'rail_note')}

```html
{_x(p, 'Rail', '', chr(10) + '  ' + _x(p, 'Slider', ' name="Volume"') + chr(10) + '  ' + (_example_button(p, 'help', 'HelpBtn') if 'help' in _right_roles(p) or not _right_roles(p) else _x(p, 'Button', ' name="Mute" states="Off, On"', 'Mute', f"width: 103px; height: {p['defaults']['button']['height']}px")) + chr(10))}
```
""",
        'Group': f"""# Group

A titled set of like controls - the sources, the presets, the cameras - laid out as a grid of equal cells in the Group's own box, `cap` to a row. Give the box room: it is where the group lives on every panel. Its children need no positions. The cells keep their size and `gap`, and spare room is not shared out among them: the grid sits centred in the box, across and down, and a last row of fewer cells is centred under the others. Where the group pages, its cells sit at the top of the box with Previous and Next under them - as arrows where their words are wider than the box, one over the other where even the arrows do not fit side by side (a one-cell column) - except in a box one cell deep, where the cells stay centred and Previous and Next (or arrows) stand at the row's ends. On a panel where the cells do not fit at the page's scale, the gap gives way first - down to the panel's own 2 mm - before the group pages.

Props:
- `title`: what the group is called. On a panel too small to show it in place, its pages and the button that opens them take this name.{_group_title_320(p)}
- `cell`: the cell's size, `"110x110"` - its members' drawn size. Default: the first member's.
- `gap`: the space between cells, in px (default 49, the toolkit's). `cap`: the most to a row (default 4). {p['examples']['group_note']}
- `joined="true"`: a segmented control - one row of segments that touch, never paged.{_panels_group(p)}

```html
{_x(p, 'Group', ' title="Sources" cell="{}" gap="{}"'.format(*_group_example(p)), chr(10) + '  ' + _example_button(p, 'source', 'Laptop') + chr(10), 'position: absolute; left: 0px; top: 210px; width: 916px; height: 250px')}
```
""",
        'Button': f"""# Button

The panel's button: a caption, the states the program switches it between, and what pressing it does. Size it with the x-import's own style; it fills that box, at least {p['touch']}px each way.

Props:
- The caption is the element's text. `type`: {button_types}; `size` in points overrides it.
- `variant`:
{variants}
- `icon`: {_icon_prop(p)} The names, by variant:
{_icons_md(p)}
- `states`: the states the program sets, in order - state 0 is what the panel shows first. `"Off, On"` by name, or JSON for looks: `'{p['examples']['states']}'`. A state takes `name`, `fill`, `stroke`, `color` (caption color), `border`, `text` (its own caption), and on an image button `look` (`off` or `on`) and `icon` (its own image, from the variant's list). A state changes only what it names: the rest - fill, stroke, color, border and, on an image button, its icon - stays as the variant draws it. A state named `Off` or `On` first takes the variant's own Off or On look; on an image button the first state shows the `off` image and the others `on`, unless the state sets `look`. Every state must look different. {p['examples']['states_note']}
- `press`: the state shown while the button is held. Default: On, else the second state. The canvas draws it while you hold the button in Play, as the panel does, so give it a look that reads as pressed. It cannot be the state the button rests in, and a button with a single state has nothing to show - give it a second.
- `nav`: the artboard this button shows, by its file name without `.dc.html` - `nav="Help"` shows `Help.dc.html`. The button becomes that link, so Play follows it.
- `does`: anything else it does, in a sentence for the programmer: "Routes the laptop to the display; Live while it is routed."
- `show`: the state to draw on the canvas (default the first). Design only.
- `name`: the control's name; `id` pins its number.
- `fill`, `stroke`, `color`, `border` set the look of every state that does not set its own - and the variant's `On` sets its own, so give `On` its look in `states` to change it.

Size an image button to its kit image's shape, or the image is letterboxed: {shapes}.

```html
{_x(p, 'Button', ' name="Display" states="Off, On" does="Turns the display on and off."', 'Display', f"width: 200px; height: {p['defaults']['button']['height']}px")}
{_example_button(p, 'source', 'Laptop', ' states="Off, On" does="Routes the laptop to the display."')}
{_example_button(p, 'help', 'HelpBtn', ' nav="Help"')}
```
""",
        'Label': f"""# Label

Text on the panel: a title, a status line, a caption beside a control. It fills its box and centers the text vertically.

Props: the text is the element's text; `type` ({', '.join(f'`{n}`' for n in types if not n.startswith('button'))}), `size` in points, `bold`, `align` (`left`, `center`, `right`), `color` (a token: {label_colors}), `name`, `does` - when the program changes the text, say so: "Shows the codec's call status."

```html
{_x(p, 'Label', ' name="RoomName" type="title"', 'Huddle Room', 'width: 520px; height: 112px')}
```
""",
        'Panel': f"""# Panel

A filled shape behind other controls: a bar, a card, a well. `fill` (default `{p['defaults']['panel']['fill']}`), `stroke` (default `{p['defaults']['panel'].get('stroke', 'none')}`; `none` for no outline), `border` ({', '.join(f'`{k}`' for k in p['borders'])}; default `{p['defaults']['panel']['border']}`), `name`. A panel is drawn, not touched; put controls on top of it, later in the markup.

```html
{_panel_example(p)}
```
""",
        'Line': f"""# Line

A divider. `orientation` (`horizontal`, default, or `vertical`), `color` (default `{p['defaults']['line']['color']}`), `thickness` in px, `name`.{(' ' + p['defaults']['line']['note']) if p['defaults']['line'].get('note') else ''}

```html
{_x(p, 'Line', ' name="Divider"', '', 'width: 1200px; height: 2px')}
```
""",
        'Slider': f"""# Slider

A control the user drags: volume, a light level. Drawn as {t} builds it: {rail_words} {thumb_words}. The box is the touch area: make it at least as wide as the thumb. `orientation`: the direction the value grows, `{p['defaults']['slider']['orientation']}` by default as {t}'s own volume sliders are (`up`, `down`, `left`, `right`).{fill_words} `name`, and `does` - what it sets and whether it follows feedback. `value` (0-100) only draws the canvas. The filled part and the thumb come from the template's own slider, so they are not props.{_panels_slider(p)}

```html
{_x(p, 'Slider', ' name="Volume" does="Sets program volume; follows the DSP level."', '', f"width: {slider_w}px; height: 395px")}
```
""",
        'Level': f"""# Level

A meter the program drives: signal level, a countdown. A rail like Slider's with no thumb, filled in `{p['defaults']['level']['value']}`, and not touchable. `orientation` (default `{p['defaults']['level']['orientation']}`), `track`, `fill`, `name`, `does`.{_level_where(p)}

```html
{_x(p, 'Level', ' name="MicLevel" orientation="up" does="Shows the microphone level."', '', 'width: 40px; height: 240px')}
```
""",
        'Clock': f"""# Clock

The panel's own date or time, drawn by the panel with no program. `format`: `time` (default, `h:mm tt`, drawn `12:00 AM`), `date` (`MMMM d`, `September 28`), `datetime` (`MMMM d, h:mm tt`, `September 28, 12:00 AM`), or any .NET date pattern - the pattern the panel formats its clock with, drawn here for 28 September 1960 at midnight as GUI Designer draws it; the panel shows the real time; `align` (`left`, `center`, `right`); `type`, `size`, `color` (default `{p['defaults']['clock']['color']}`), `name`.{_clock_footer(p)}{_clock_none(p)}

```html
{_x(p, 'Clock', ' name="Time"', '', 'width: 200px; height: 40px')}
```
""",
        'PopupRegion': f"""# PopupRegion

Where a group's standard popups appear on this page. `group` names the popup group; every popup whose Page has that `group` shows here, and a button whose `nav` names one of them needs a region for its group on the page it is pressed on. `name`. Modal popups need no region.

```html
{_x(p, 'PopupRegion', ' name="SourceArea" group="Sources"', '', 'width: {}px; height: {}px'.format(*_region_example(p)))}
```
""",
        **_region_docs(p),
        **_image_docs(p),
    }


def _image_docs(p):
    """The Image's README, where the system offers one (offers_image)."""
    if not offers_image(p):
        return {}
    t, ex = p['template'], p['examples']['image']
    w, ht = ex['size']
    # The panels whose seed has no PBImage to clone (its series' `kinds`).
    lack = sorted({m for name, row in (p.get('panels') or {}).items()
                   if not name.startswith('_') and (row.get('kinds') or {}).get('image') is False
                   for m in row.get('seeds') or ()})
    where = f" - {_model_names(lack)} has none" if lack else ''
    return {'Image': f"""# Image

The template's own art, by its kit file: `image` (a file's name, as a Button state's), `layout` - `fill`, the default, fitted keeping its aspect, or `stretch` over the whole box - an optional `fill` under it, and `name`. It is drawn, not touched, and holds nothing; put it before what stands over it. {ex['note']} A file the {t} kit lacks draws dashed and the translator refuses it, and an Image on a panel whose seed has no image to clone is named there{where}.

```html
{_x(p, 'Image', f' name="{ex["name"]}" image="{ex["image"]}"', '', f'width: {w}px; height: {ht}px')}
```
"""}


def _twin_words(p):
    """The Header README's sentence on a tab's twin, where any series' frame
    has one (Shockwave's 1220 and 1720 series: the 1035 and the 1535), or ''."""
    series = [name for name, s in sorted((p.get('panels') or {}).items())
              if isinstance(s, dict) and ((((s.get('frame') or {}).get('top') or {}).get('tabs') or {}).get('twin'))]
    if not series:
        return ''
    return (f" On the {' and '.join(series)}, whose template names each tab by a twin, the tab draws no caption: a "
            "caption-only button across its foot, `<name> Caption`, says it in every state with the tab's ID, `nav` "
            "and states - one control to the program, which the ID map lists as the tab's mirror.")


def _region_docs(p):
    """The region components' READMEs, for a system that has them."""
    if not _regions(p):
        return {}
    t = p['template']
    r = p.get('regions') or {}
    clock = (r.get('clock') or {}).get('format', 'time')

    def look(key):
        v = (r.get(key) or {})
        return f"`{v['variant']}`" + (f" with icon `{v['icon']}`" if v.get('icon') else '') if v.get('variant') else 'the default'
    common = (f"A region of a working page, as {t}'s own Main SD draws it: it paints nothing and is not a "
              "control. Put it directly on the Page, with no position: on every panel the region takes its "
              "band from that panel's own series' template - the 725's from the 725's, not the 1035's "
              "scaled - and places what it holds by meaning, in the template's own look unless a control "
              "sets its own, each control grown where that panel's touch minimum or type floor needs it and "
              "kept in its band. Where the template stands two sets' controls nearer than 2 mm, the page "
              "opens the seam to that panel's gap. A Page holding any region is a region "
              "page: one that lacks a Header, LeftRail, RightRail, Footer or Center is named on the canvas "
              "and in the translate report, and still builds; a Start or other splash page says "
              "`splash=\"true\"` and is not. On a hub (the 520s and 535s) and on the 320 the same regions "
              "are drawn in their own grammar - a menu bar beside popups that fill main, pages under a title "
              "strip - which the system's README says region by region (*The template's grammar*). On a turned "
              "panel a region page is refused by name for now.")
    together = _footer_together(p)
    # The Section and LeftRail examples in the theme's own words: its frame's
    # group headings (Shockwave's second has none) and its launchers
    # (`writing.voice`) - where they showed Mach's Settings and Lighting.
    heads = [((g.get('heading') or {}).get('text') or '') for g in ((_design_frame(p).get('left') or {}).get('groups') or ())]
    g1 = (heads[:1] or ['Display'])[0] or 'Display'
    g2 = heads[1] if heads[1:2] and heads[1] else 'its launchers'
    launcher = ((((p.get('writing') or {}).get('voice') or {}).get('launchers')) or ['Lighting'])[-1]

    def ex(comp, attrs='', body=''):
        return _x(p, comp, attrs, body)

    def btn(attrs, text):
        return _x(p, 'Button', attrs, text)
    return {
        'Header': f"""# Header

The bar across the top: the source tabs. {common}

Its children say where they go with `slot`:
- `slot="source"`: a source tab. The tabs stand at the frame's places - its first tab's, then its step, as the Layout gives them - as one set: the 2 mm between touch targets is kept between the set and anything else, not inside it. Fewer tabs than the template draws take its first places and the bar closes up after them; more continue its step. A tab takes the template's look and caption alignment unless it sets its own: on {t}, {look('tab')}, its measured fill when off and on where it draws no art, and its caption centred - one indented past its icon takes as many leading spaces as clear the icon on each panel. The row is one size: where one caption needs more room on a panel, every tab grows with it, and the bar with them. Give each a `nav` to its source's popup.{_twin_words(p)}
- `slot="start"` and `slot="end"`: anything at the bar's left or right end, at its own size.

The bar's own surfaces are drawn as Panels named `Header Left`, `Header Right` or `Header Bar`{_bar_art_words(p, 'top')}.

```html
{ex('Header', '', chr(10) + '  ' + btn(f' slot="source" name="Laptop" icon="{_tab_icon(p)}" nav="Laptop"', 'Laptop') + chr(10))}
```
""",
        'LeftRail': f"""# LeftRail

The column left of the center: the room's display controls and the launchers for its settings, in titled Sections. {common}

Its children are Sections, the template's groups in order: the first Section stands where the template's first group does ({g1}), the second where its second does ({g2}). The first Section's buttons take the template's rail look ({look('rail')}), a later one's its launchers' ({look('launcher') if r.get('launcher') else look('rail')}), unless they set their own. A control outside a Section is named.

```html
{ex('LeftRail', '', chr(10) + '  ' + ex('Section', ' title="Display"', chr(10) + '    ' + btn(' name="Display On"', 'On') + chr(10) + '  ') + chr(10))}
```
""",
        'Section': f"""# Section

A titled group in the LeftRail. `title` is drawn as the group's heading Label (named `<title> Heading`) where the template draws one; its children need no positions - they stand at the frame's places for that group, down its step as the Layout gives it, as one set, with 2 mm kept between the set and anything else. The set is one width: where one caption needs more room on a panel, every button of the column grows with it. More than the rail holds is named. A Section anywhere but in a LeftRail is named.

```html
{ex('Section', f' title="{g2}"' if heads[1:2] and heads[1] else '', chr(10) + '  ' + btn(f' name="{launcher}" nav="{launcher}"', launcher) + chr(10))}
```
""",
        'RightRail': f"""# RightRail

The column right of the center: volume. {common}

Empty, it draws the template's own: the Volume heading, the volume Slider - or, on a panel whose seed has no slider, a Level with Up and Down - and Mute ({look('mute')}). The Slider and Mute - drawn by default or yours in their slots - keep the template's own IDs where you give them none and no other control has them, so Volume is one control on every page and every panel. The heading, slider and Mute are the rail's group: one set, as near as the frame stands them, with 2 mm kept between it and anything else. A child with a `slot` takes that place instead: `slot="heading"`, `slot="volume"`, `slot="mute"`, or `slot="audio"` for Audio Control where that panel's template stands one in its right rail ({_audio_where(p)}) - on one that keeps Audio Control in its left rail instead it goes into the LeftRail's Section there, at its place (the system's README, *The template's grammar*), and on another it is named.

```html
{ex('RightRail')}
```
""",
        'Footer': f"""# Footer

The bar across the foot: the room's mode, the date and time, Help and Power. {common}

It draws the template's clock (`{clock}`), Help ({look('help')}) and Power ({look('power')}) by default. Help, Power and the control in the mode slot - drawn by default or yours - keep the template's own IDs where you give them none and no other control has them. `help` and `power` name the artboards they show - `help="Help" power="ConfirmPower"`. A child with a `slot` takes that place instead: `slot="mode"` (the template's mode launcher - Room Mode, {look('mode')} - which is drawn only when given), `slot="clock"`, `slot="help"`, `slot="power"`. {together} The clock gives way, about its middle, to a cell grown into it; the bar's own surface - a Panel named `Footer Bar`{_bar_art_words(p, 'bottom', ', or, where it is')} - is kept flush with the cells beside it as they grow.

```html
{ex('Footer', ' help="Help" power="ConfirmPower"', chr(10) + '  ' + btn(' slot="mode" name="Room Mode" nav="Room Mode"', 'Room Mode') + chr(10))}
```
""",
        'Center': f"""# Center

The middle of the working page: the popup region the sources fill, where the template's is - on every panel that panel's own. `group` names the popup group (default `Sources`) - each source's controls are a popup of that group, `kind="popup"` with `role="source"`, which is drawn as the region's size on each panel, in the template's own well and title (the Page README) - and `name` the region (default `Controls`).{_center_well(p)} {common}

```html
{ex('Center', ' group="Sources"')}
```
""",
    }


def _roles_props(p):
    """The Page's `role`, `topic` and `title` lines, for a system with the
    region frame: a source's popup and the windows, drawn as the template
    draws them (docs/claude-design.md section 4)."""
    if not _regions(p):
        return ''
    w = p.get('writing') or {}
    t = p['template']
    empty = ' '.join(w.get('empty', '').split()).format(name='Laptop', noun='laptop')
    question = ' '.join((w.get('confirm') or {}).get('power', '').split())
    status = f", over its `{w['status']}` status." if w.get('status') else ''
    helped = w.get('help_title') or 'Help'
    # Shockwave's and Turbulence's hubs draw every standard popup on the page's photo.
    photo = (f" - on the page's photo, stretched to it, as {t}'s hubs draw every popup"
             if (((p.get('regions') or {}).get('hub') or {}).get('popup') or {}).get('photo') else '')
    return (f"- `role=\"source\"` on a `kind=\"popup\"` in the Center's group: a source's controls. On every panel it "
            f"is that panel's own popup region, and draws {t}'s own chrome for it - {_source_chrome(p)}; `title` names "
            f"it (default: its `name`).{_device_words(p)} Put the source's controls in it where you want them, clear of its title (one "
            f"under it is named): they are laid out in the well on every panel, white where {t} writes white, in its "
            f"in-well look. With none it says {t}'s empty state: '{empty}'{status} Without the role a popup in "
            f"`Sources` scales with main, and is named where it comes out larger than the region. On a hub it fills "
            f"main under the hub's own header - its title and a Close back to Select a Source{photo}. On a 320 it is a page "
            f"of its own under the strip titled with it, what you put in it in columns - a label at a column's top its "
            f"heading, a Group a column of its own under its title, a slider a level with Up and Down - two to a "
            f"page, the rest on a second page by More and Back; with nothing in it, the 320's "
            f"three-line empty state; its Back goes back to the page whose key shows it. On a turned panel a source "
            f"popup is refused by name for now.\n"
            f"- `role` on a `kind=\"modal\"`: a window, drawn as {t} draws its windows. `settings` (or a `title` and "
            f"no role) draws the window with its `title` and a Close; `help` too, titled '{helped}' unless you give a "
            f"`title`, and with nothing put in it {t}'s own help message; `confirm` with `topic=\"power\"` asks "
            f"'{question}' with Power Down - its `does` is the Page's - and Cancel; `wait` with `topic=\"up\"` or "
            f"`\"down\"` says the wait, with no buttons. Close and Cancel go back to the page that opened the window - "
            f"the program's to do, so they carry no `nav`. Put a settings window's own controls inside it. A `role` the "
            f"Page's `kind` does not take is named. On a hub a settings window is a popup filling main, as the hub "
            f"draws its settings, with its title and a Close back to Select a Source; Help, the question and the wait "
            f"stay windows in the hub's own style. On a 320 each is a page: the question and the wait on the "
            f"template's rounded box, a settings window and Help under the strip with Back to the page that opened "
            f"it. On a turned panel a window is refused by name for now.\n")


def _device_pictures(p):
    """The device pictures a source popup draws, by device: the kit's family
    of the frames' source-popup image surfaces ({} where the template pins
    none, or its art is not here)."""
    sizes = {re.match(r'(\d+x\d+)_', s['art']).group(1)
             for row in (p.get('panels') or {}).values() if isinstance(row, dict) and row.get('frame')
             for s in (row['frame'].get('center') or {}).get('surfaces') or ()
             if s.get('popup') and s.get('kind') == 'image' and s.get('art') and re.match(r'\d+x\d+_', s['art'])}
    files = kit_index(p)['files'] if p.get('kit') else {}
    return {fam: looks for size in sorted(sizes) for fam, looks in (files.get(size) or {}).items()}


def _device_words(p):
    """The Page README's `device`, where the template pins a device picture
    on its source popups (Turbulence)."""
    pics = _device_pictures(p)
    if not pics:
        return ''
    aliases = ((p.get('regions') or {}).get('source') or {}).get('devices') or {}
    said = ', '.join(f"{k.title()} the {v}'s" for k, v in sorted(aliases.items()))
    return (f" `device` names the device it pictures - {', '.join(f'`{f}`' for f in sorted(pics))}; by default "
            f"its `name` or `title` where it is one of those (Laptop, PC, Doc Cam){' or ' + said if said else ''}. "
            f"Each is drawn at its own size, where that panel's seed draws that device in a source's popup (the "
            f"Layout's device pictures), and one its seed pictures for no source where it draws the Laptop's. "
            f"With none, the place stays empty and the canvas says so.")


def _art_bars(p):
    """{band: art file} for the design panel's bars that are the template's
    art and drawn as it, as bundle.js surfacesOf() draws them: where the kit
    has the file and the panel's seed can clone an image (Turbulence's
    header and footer). {} where the kit is not here, so the README says no
    more than the canvas draws."""
    row = models(p).get(p['model']) or {}
    if not _regions(p) or not p.get('kit') or (row.get('kinds') or {}).get('image') is False:
        return {}
    F, paths = row.get('frame') or {}, kit_index(p)['paths']
    return {k: s['art'] for k in ('top', 'left', 'right', 'bottom')
            for s in ((F.get(k) or {}).get('surfaces') or ()) if s.get('art') in paths}


def _bar_art_words(p, band, lead=' - or, where one is'):
    """The Header's and Footer's README clause on a bar surface that is art
    (_art_bars), or ''."""
    art = _art_bars(p).get(band)
    if not art:
        return ''
    return (f"{lead} {p['template']}'s own art (`{art}`), an Image of it stretched over the band on every panel "
            f"whose seed can clone an image")


def _grammar_art(p):
    """The grammar's sentence on the bars that are the template's art
    (_art_bars), or ''."""
    bars = _art_bars(p)
    if not bars:
        return ''
    said = [k for k in ('top', 'left', 'right', 'bottom') if k in bars]
    words = {'top': ('header', 'Header'), 'left': ('left rail', 'LeftRail'), 'right': ('right rail', 'RightRail'),
             'bottom': ('footer', 'Footer')}
    one = len(said) == 1
    bar = (p.get('regions') or {}).get('bar')
    return (f"{p['template']}'s {_say([words[k][0] for k in said])} {'is' if one else 'are'} its own art - "
            f"{_say(['`' + bars[k] + '`' for k in said])} - and the {_say(['`' + words[k][1] + '`' for k in said])} "
            f"draw{'s' if one else ''} {'it' if one else 'them'} as that art, stretched over "
            f"{'its band' if one else 'their bands'}, on every panel whose seed can clone an image"
            + (f"; on one that cannot, flat `{bar}`" if bar else '') + ". You draw no bar of your own.\n\n")


def _window_image(p):
    """The Windows section's clause on a settings window's picture, where
    the system offers the Image (offers_image), or ''."""
    if not offers_image(p):
        return ''
    ex = p['examples']['image']
    return (f", and where {p['template']} pictures what it controls, that picture as an `{p['namespace']}.Image` "
            f"before them - `{ex['image']}` in a {ex['name'].split()[0].lower()} window (the Image README)")


def _hub_photo(p):
    """Whether a hub's popups stand on the page's photo
    (`regions.hub.popup.photo`: Shockwave's and Turbulence's)."""
    return bool((((p.get('regions') or {}).get('hub') or {}).get('popup') or {}).get('photo'))


def _source_chrome(p):
    t = p['template']
    return {'Mach': "the framed shade well, its title bar 1 px above its body, titled in white at its left",
            'Shockwave': "its 40 pt white title across the popup's top, over the well the Center draws on the page",
            'Turbulence': "its large centred title over the device picture Extron pins at its top left, fitted - "
                          "the source's `device`"}.get(t, f"{t}'s own well and title")


def _center_well(p):
    """What the Center draws round its region, where the template draws a
    well on the page."""
    wells = any(not s.get('popup') and s.get('kind') == 'shape'
                for row in (p.get('panels') or {}).values() if isinstance(row, dict)
                for s in (((row.get('frame') or {}).get('center') or {}).get('surfaces') or []))
    return (" Where the template draws a well round it on the page, the Center draws it too, as a Panel named "
            "`Center Well`." if wells else '')


def _tab_icon(p):
    """An icon the template's tab look draws, for the Header's example."""
    tab = ((p.get('regions') or {}).get('tab') or {}).get('variant')
    m = re.search(r'variant="([^"]+)" icon="([^"]+)"', ((p.get('examples') or {}).get('source') or {}).get('attrs', ''))
    return m.group(2) if m and m.group(1) == tab else 'laptop'


_ORDINAL = ('first', 'second', 'third', 'fourth')


def _audio_left(p):
    """Where a series' template keeps Audio Control in its left rail's group
    instead of its right rail (Shockwave's 1020: Display Control, Audio
    Control, Lighting Control) - the RightRail's `audio` control goes there
    (bundle.js movedPlace), and that Section has the group's places."""
    found = []
    for name, s in (p.get('panels') or {}).items():
        F = (s.get('frame') or {}) if isinstance(s, dict) and not name.startswith('_') else {}
        if not F.get('left') or any(i['role'] == 'audio' for i in (F.get('right') or {}).get('items') or ()):
            continue
        for gi, g in enumerate(F['left'].get('groups') or ()):
            if any(b.get('role') == 'audio' for b in g.get('buttons') or ()):
                found.append((name[len(p['template']):].strip().removesuffix(' Series'), gi, len(g['buttons'])))
                break
    if not found:
        return ''
    gis = sorted({gi for _, gi, _ in found})
    places = {}
    for series, _, n in found:
        places.setdefault(n, []).append(series)
    room = ' and '.join(f"{n} on the {_say(ss)}" for n, ss in sorted(places.items()))
    which = ' or '.join(_ORDINAL[gi] for gi in gis)
    return (f"; {_the_series([x for x, _, _ in found])} keep Audio Control in the left rail's {which} group "
            f"instead ({room}, its place among them), and it goes there, into the LeftRail's {which} Section: "
            f"leave that Section room for it, or the page is refused on those panels")


def _audio_where(p):
    """Which series stand Audio Control in their right rail."""
    have = _series_named(p, lambda s: any(i['role'] == 'audio' for i in (
        ((s.get('frame') or {}).get('right') or {}).get('items') or [])))
    return f"on {p['template']}, " + _the_series(have) if have else f"{p['template']} draws none"


_ROLE_NAMES = {'mode': 'Room Mode', 'help': 'Help', 'power': 'Power'}


def _footer_together(p):
    """The footer's sentence on which cells its template stands together."""
    F = (models(p).get(p['model']) or {}).get('frame') or {}
    cells = [i for i in ((F.get('bottom') or {}).get('items') or []) if i['kind'] == 'button']
    cells += [i for i in ((F.get('right') or {}).get('items') or []) if i['role'] in ('help', 'power')]
    pairs = []
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            ra, rb = a['rect'], b['rect']
            gx = max(rb[0] - (ra[0] + ra[2]), ra[0] - (rb[0] + rb[2]))
            gy = max(rb[1] - (ra[1] + ra[3]), ra[1] - (rb[1] + rb[3]))
            if (0 <= gx <= 2 and gy < 0) or (0 <= gy <= 2 and gx < 0):
                pairs.append(f"{_ROLE_NAMES.get(a['role'], a['role'])} and {_ROLE_NAMES.get(b['role'], b['role'])}, "
                             f"{max(gx, gy)} px apart")
    # Mach's stand 1 px apart and Turbulence's 2: together, not always touching.
    if not pairs:
        return (f"{p['template']}'s template stands its footer's cells apart: each keeps 2 mm from the "
                "others.")
    return (f"The cells {p['template']}'s template stands together - {'; '.join(pairs)} - stand as it draws "
            "them, one set; every other keeps 2 mm.")


def _preview(p, comp, height, body):
    ns = p['namespace']
    return (f'<!-- @dsCard group="{dict((n, g) for n, g, _ in components(p))[comp]}" height={height} -->\n'
            '<!doctype html>\n<html>\n<head><meta charset="utf-8">'
            f'<title>{comp} - preview</title>'
            f'<link rel="stylesheet" href="{p["font"]["google"]}"></head>\n'
            f'<body style="margin:0;background:var(--page)">\n<div id="root"></div>\n<script>\n'
            f'  var N = window.{ns}, h = React.createElement;\n'
            f'  function box(w, ht, el) {{ return h("div", {{ style: {{ width: w + "px", height: ht + "px" }} }}, el); }}\n'
            # Drawn at its own size and scaled down whole, so a caption keeps
            # its proportion to the art it sits on.
            '  function fit(w, ht, max, el) { var k = Math.min(1, max / ht); return h("div", { style: { width: w * k + "px", height: ht * k + "px" } }, '
            'h("div", { style: { width: w + "px", height: ht + "px", transform: "scale(" + k + ")", transformOrigin: "0 0" } }, el)); }\n'
            '  function row(kids) { return h("div", { style: { display: "flex", gap: "24px", padding: "16px", alignItems: "center", flexWrap: "wrap" } }, kids); }\n'
            f'  ReactDOM.createRoot(document.getElementById("root")).render({body});\n'
            '</script>\n</body>\n</html>\n')


# The tallest a button is drawn in the Button preview; a taller one is scaled
# down whole (`fit`), its caption with it.
PREVIEW_MAX = 110


def _preview_images(p):
    """[variant, icon, w, h, caption] for each image variant's preview: its own
    default icon or the first its kit has, at the size its seed draws it
    (`size`), or else at its kit image's shape. Turbulence's 87x90 tile drawn
    64 tall kept its caption at full size, which spilled past the tile."""
    names = icon_names(p)
    out = []
    for k, size, caption, icon in _image_buttons(p):
        icon = icon or next(iter(names.get(k) or []), None)
        text = '' if caption == 'none' else 'Laptop' if caption == 'below' else k.capitalize()
        seed = p['buttons'][k].get('size')
        if seed:
            w, ht = seed
        else:
            w, h = _kit_size(p, size)
            ht = 110 if caption == 'below' else 64
            w = min(260, round(ht * w / h))
        out.append([k, icon, w, ht, text])
    return out


def _panel_fills(p):
    """The default panel fill and up to two of the template's other surface
    colors, for the Panel preview - only names the template has: Turbulence
    has no `pressed`, which painted the preview magenta."""
    names = {c['name'] for c in p['colors']}
    default = p['defaults']['panel']['fill']
    alt = [n for n in ('pressed', 'shade', 'raised', 'rail', 'well') if n in names and n != default]
    return [default] + alt[:2]


def _button_preview_height(p, width=1100):
    """The Button card's height: its boxes in rows as the preview's flex row
    wraps them, on a card about `width` wide."""
    boxes = [(180, 64)] * 2 * sum(1 for v in p['buttons'].values() if not v.get('kit'))
    for _, _, w, ht, _ in _preview_images(p):
        k = min(1, PREVIEW_MAX / ht)
        boxes += [(round(w * k), round(ht * k))] * 2
    rows, x, tall = [], 16, 0
    for w, ht in boxes:
        if x > 16 and x + w > width - 16:
            rows.append(tall)
            x, tall = 16, 0
        x, tall = x + w + 24, max(tall, ht)
    rows.append(tall)
    return sum(rows) + 24 * (len(rows) - 1) + 32


def previews(p):
    heights = {n: ht for n, _, ht in components(p)}
    s = p['size']
    scale = 0.12
    fills = _panel_fills(p)
    b = {
        'Page': ('h("div", { style: { transform: "scale(' + str(scale) + ')", transformOrigin: "0 0", width: "'
                 + str(s[0]) + 'px", margin: "16px" } }, h(N.Page, { name: "Home" }, '
                 'h("div", { style: { position: "absolute", left: "40px", top: "40px", width: "1200px", height: "112px" } }, '
                 'h(N.Label, { type: "title" }, "Huddle Room")), '
                 'h("div", { style: { position: "absolute", left: "40px", top: "200px", width: "360px", height: "200px" } }, '
                 'h(N.Button, null, "Laptop"))))'),
        'MainArea': ('h("div", { style: { transform: "scale(' + str(scale) + ')", transformOrigin: "0 0", width: "'
                     + str(s[0]) + 'px", margin: "16px" } }, h(N.Page, { name: "Home" }, '
                     'h(N.MainArea, null, h("div", { style: { position: "absolute", left: 0, right: 0, top: "300px", height: "120px" } }, '
                     'h(N.Label, { type: "title", align: "center" }, "Main area")))))'),
        'Rail': ('row([box(200, 300, h(N.Rail, null, h("div", { style: { width: "100%", flex: "1 1 auto" } }, '
                 'h(N.Slider, { value: 60 })), h("div", { style: { width: "64px", height: "64px" } }, '
                 'h(N.Button, null, "Help"))))])'),
        'Group': ('row([box(440, 150, h(N.Group, { title: "Sources", cell: "110x110", gap: 30 }, '
                  '["Laptop", "PC", "Wireless"].map(function (n) { return h("div", { key: n }, h(N.Button, null, n)); })))])'),
        'Button': ('row(Object.keys(N.profile.buttons).filter(function (v) { return !N.profile.buttons[v].kit; })'
                   '.map(function (v) { return [box(180, 64, h(N.Button, { key: v, variant: v }, v)), '
                   'box(180, 64, h(N.Button, { key: v + "on", variant: v, show: "On" }, v + " On"))]; })'
                   '.concat(N.profile.kit ? ' + json.dumps(_preview_images(p)) + ''
                   '.map(function (x) { return ["Off", "On"].map(function (st) { return fit(x[2], x[3], ' + str(PREVIEW_MAX) + ', '
                   'h(N.Button, { key: x[0] + st, variant: x[0], icon: x[1] || undefined, show: st }, x[4])); }); }) : []))'),
        'Label': ('row(["title", "heading", "body", "body-strong"].map(function (t) { '
                  'return box(260, 60, h(N.Label, { key: t, type: t }, t)); }))'),
        # A panel in the page's own color - Turbulence's and Shockwave's are -
        # is shown over the template's page, its photo and all, rather than
        # vanishing into the card's ground. The rest keep the plain ground: a
        # photo squeezed into a strip is no help to them.
        'Panel': ((('h(N.Page, { name: "Panels", width: ' + str(32 + 284 * len(fills) - 24)
                    + ', height: 122 }, ') if fills[0] == p['defaults']['page']['background'] else '(')
                  + 'row([' + ', '.join(
                      f'box(260, 90, h(N.Panel, {{ key: {i}, fill: "{f}" }}))'
                      for i, f in enumerate(fills)) + ']))'),
        'Line': 'row([box(560, 2, h(N.Line))])',
        'Slider': 'row([box(420, 60, h(N.Slider, { value: 60 }))])',
        'Level': 'row([box(420, 40, h(N.Level, { value: 40 })), box(40, 88, h(N.Level, { orientation: "up", value: 70 }))])',
        'Clock': 'row([box(200, 40, h(N.Clock)), box(360, 40, h(N.Clock, { format: "date" }))])',
        'PopupRegion': 'row([box(440, 90, h(N.PopupRegion, { group: "Sources" }))])',
    }
    if offers_image(p):
        ex = p['examples']['image']
        k = min(1, 110 / max(ex['size']))
        b['Image'] = (f'row([box({round(ex["size"][0] * k)}, {round(ex["size"][1] * k)}, '
                      f'h(N.Image, {{ name: {json.dumps(ex["name"])}, image: {json.dumps(ex["image"])} }}))])')
    heights['Button'] = max(heights['Button'], _button_preview_height(p))
    b.update(_region_previews(p))
    return {n: _preview(p, n, heights[n], b[n]) for n, _, _ in components(p)}


def _region_previews(p):
    """Each region's card: the template's working page at a small scale with
    that region and those it needs to read - a page with only its own region,
    marked a splash page so the canvas names nothing missing. The design
    panel draws it from its own series' frame."""
    if not _regions(p):
        return {}
    s, scale = p['size'], 0.12
    tab =('h(N.Header, null, ["Laptop", "PC"].map(function (n) { return h("div", { key: n }, '
           'h(N.Button, { slot: "source", name: n }, n)); }))')
    rail = ('h(N.LeftRail, null, h("div", null, h(N.Section, { title: "Display" }, ["On", "Off"].map(function (n) { '
            'return h("div", { key: n }, h(N.Button, { name: "Display " + n }, n)); }))))')
    body = {
        'Header': tab,
        'LeftRail': rail,
        'Section': rail,
        'RightRail': 'h(N.RightRail)',
        'Footer': 'h(N.Footer, { help: "Help", power: "ConfirmPower" })',
        'Center': 'h(N.Center, { group: "Sources" })',
    }
    return {n: ('h("div", { style: { transform: "scale(' + str(scale) + ')", transformOrigin: "0 0", width: "'
                + str(s[0]) + 'px", margin: "16px" } }, h(N.Page, { name: "Main", splash: "true" }, ' + e + '))')
            for n, e in body.items()}


def cover(p):
    """The cover: the template's colors as blocks, cut at its own radius."""
    blocks = p['cover']['blocks']
    r = p['cover'].get('radius', 10)
    tiles = []
    for i in range(4):
        for j in range(3):
            tiles.append(f'<rect class="t{(i + j) % len(blocks)}" x="{520 + i * 108}" y="{24 + j * 84}" '
                         f'width="{96 if (i + j) % 3 else 204 if i < 3 else 96}" height="72" rx="{r}"/>')
    css = ''.join(f'.t{k}{{fill:var(--{b})}}' for k, b in enumerate(blocks))
    return f"""<!-- @dsCard height=288 -->
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Cover</title>
<link rel="stylesheet" href="{p['font']['google']}">
<style>
body{{margin:0;background:var(--page)}}
.c{{position:relative;width:960px;height:288px;background:var(--page);overflow:hidden;font-family:{p['font']['stack'].replace('"', "'")}}}
svg{{position:absolute;left:0;top:0}}
{css}
.n{{position:absolute;left:40px;bottom:64px;margin:0;font-size:84px;line-height:.95;font-weight:700;color:var(--text);max-width:440px}}
.g{{position:absolute;left:40px;bottom:32px;margin:0;font-size:14px;color:var(--text-secondary);max-width:440px}}
</style></head>
<body>
<div class="c">
<svg width="960" height="288" viewBox="0 0 960 288" aria-hidden="true">
<!-- blocks: {', '.join(blocks)} at the 72 px row of a 64 px button plus nudge
     arrangement: a modular grid of tiles right of x=480, some merged two-wide like list rows
     pattern: {p['cover']['pattern']} - the template's own corner is its signature
     scales: radius-afterburn-flat ({r}px), nudge 10px steps -->
{chr(10).join(tiles)}
</svg>
<p class="n">{p['template']}</p>
<p class="g">{p['tagline']}</p>
</div>
</body>
</html>
"""


def index_dts(p):
    ns = p['namespace']
    states = ("string | Array<string | { name: string; fill?: string; stroke?: string; color?: string; "
              "border?: string; text?: string; look?: 'off' | 'on'; icon?: string }>")
    regions = _region_dts(p)
    image = (("export interface ImageProps { name?: string; image: string; layout?: 'fill' | 'stretch'; fill?: Token }\n"
              "export declare function Image(props: ImageProps): React.ReactElement;\n"),
             '; Image: typeof Image') if offers_image(p) else ('', '')
    # A region places a control by its `slot`, and a splash page says it has
    # none: props of the systems that have regions.
    slot = ' slot?: string;' if regions[0] else ''
    splash = ' splash?: boolean | string;' if regions[0] else ''
    # A source popup and a window say what they are (docs/claude-design.md section 4).
    role = (" role?: 'source' | 'settings' | 'help' | 'confirm' | 'wait'; topic?: string; title?: string;"
            + (' device?: string;' if _device_pictures(p) else '') if regions[0] else '')
    return f"""import type * as React from 'react';
/** Colors are token names ({', '.join(c['name'] for c in p['colors'])}) or '#RRGGBB'. Sizes are points. */
type Token = string;
export interface PageProps {{ name: string; kind?: 'page' | 'popup' | 'modal'; group?: string; start?: boolean | string; reachedBy?: 'program'; theme?: {' | '.join(repr(t['id']) for t in themes(p))}; scheme?: {' | '.join(repr(s['id']) for s in p['schemes'])}; background?: Token; width?: number; height?: number; does?: string; panels?: string; preview?: string;{splash}{role} children?: React.ReactNode }}
export declare function Page(props: PageProps): React.ReactElement;
export interface MainAreaProps {{ style?: React.CSSProperties; children?: React.ReactNode }}
export declare function MainArea(props: MainAreaProps): React.ReactElement;
export interface RailProps {{ children?: React.ReactNode }}
export declare function Rail(props: RailProps): React.ReactElement;
export interface GroupProps {{ title: string; cap?: number | string; cell?: string; gap?: number | string; joined?: boolean | string; children?: React.ReactNode }}
export declare function Group(props: GroupProps): React.ReactElement;
export interface ButtonProps {{ name?: string; id?: number; variant?: {' | '.join(repr(k) for k in p['buttons'])}; type?: {' | '.join(repr(t['name']) for t in p['type'])}; size?: number; bold?: boolean; align?: 'left' | 'center' | 'right'; states?: {states}; press?: string; nav?: string; does?: string; show?: string; fill?: Token; stroke?: Token; color?: Token; border?: {' | '.join(repr(k) for k in p['borders'])}; icon?: string;{slot} children?: React.ReactNode }}
export declare function Button(props: ButtonProps): React.ReactElement;
export interface LabelProps {{ name?: string; id?: number; type?: {' | '.join(repr(t['name']) for t in p['type'])}; size?: number; bold?: boolean; align?: 'left' | 'center' | 'right'; color?: Token; does?: string;{slot} children?: React.ReactNode }}
export declare function Label(props: LabelProps): React.ReactElement;
export interface PanelProps {{ name?: string; fill?: Token; stroke?: Token; border?: string }}
export declare function Panel(props: PanelProps): React.ReactElement;
export interface LineProps {{ name?: string; orientation?: 'horizontal' | 'vertical'; color?: Token; thickness?: number }}
export declare function Line(props: LineProps): React.ReactElement;
export interface TrackProps {{ name?: string; id?: number; orientation?: 'right' | 'left' | 'up' | 'down'; fill?: Token; border?: string; value?: number; does?: string;{slot} }}
export declare function Slider(props: TrackProps): React.ReactElement;
export declare function Level(props: TrackProps): React.ReactElement;
export interface ClockProps {{ name?: string; format?: 'time' | 'date' | 'datetime' | string; type?: string; size?: number; color?: Token;{slot} }}
export declare function Clock(props: ClockProps): React.ReactElement;
export interface PopupRegionProps {{ name?: string; group: string }}
export declare function PopupRegion(props: PopupRegionProps): React.ReactElement;
{image[0]}{regions[0]}declare global {{ interface Window {{ {ns}: {{ Page: typeof Page; MainArea: typeof MainArea; Rail: typeof Rail; Group: typeof Group; Button: typeof Button; Label: typeof Label; Panel: typeof Panel; Line: typeof Line; Slider: typeof Slider; Level: typeof Level; Clock: typeof Clock; PopupRegion: typeof PopupRegion{image[1]}{regions[1]} }} }} }}
"""


def _region_dts(p):
    """(declarations, window members) for the region components, or two empty
    strings for a system without them."""
    if not _regions(p):
        return '', ''
    decls = (
        'export interface HeaderProps { children?: React.ReactNode }\n'
        'export declare function Header(props: HeaderProps): React.ReactElement;\n'
        'export interface LeftRailProps { children?: React.ReactNode }\n'
        'export declare function LeftRail(props: LeftRailProps): React.ReactElement;\n'
        'export interface SectionProps { title?: string; children?: React.ReactNode }\n'
        'export declare function Section(props: SectionProps): React.ReactElement;\n'
        'export interface RightRailProps { children?: React.ReactNode }\n'
        'export declare function RightRail(props: RightRailProps): React.ReactElement;\n'
        'export interface FooterProps { help?: string; power?: string; children?: React.ReactNode }\n'
        'export declare function Footer(props: FooterProps): React.ReactElement;\n'
        'export interface CenterProps { name?: string; group?: string }\n'
        'export declare function Center(props: CenterProps): React.ReactElement;\n')
    members = ''.join(f'; {n}: typeof {n}' for n, _, _ in REGION_COMPONENTS)
    return decls, members


def readme(p, renders=None):
    """The README a designer reads before drawing a canvas: the template's
    grammar first - its regions, the working page drawn in them, its center,
    its windows and its words - then what to check before handing over, the
    pages outside the grammar and where the system differs from the template
    (the ledger's deviations); then the measured Layout, each panel's room and
    the foundations. `renders` is the template renders a build wrote
    (template_renders entries); None names every one the plan has."""
    ns, t = p['namespace'], p['template']
    w, ht = p['size']
    regions = _regions(p)
    comps = ', '.join(f'`{n}`' for n, _, _ in components(p) if n not in ('Page', 'MainArea'))
    type_line = ', '.join(f"`{s['name']}` {s['pt']:g}{' bold' if s['weight'] >= 600 else ''}"
                          for s in p['type'])
    border_line = ', '.join(f"`{k}` ({b['usage'].rstrip('.').lower()})" for k, b in p['borders'].items())
    drawn = (f"one page or popup of the room's Extron touch panels in Extron's {t} template, drawn at the "
             f"{p['model']}'s {w}x{ht}" if models(p) else
             f"one page or popup of an Extron {p['model']} touch panel ({w}x{ht}) in Extron's {t} template")
    renders = template_renders(p) if renders is None else renders
    return f"""Every artboard on a canvas that uses this system is {drawn}. The canvas is built into a real GUI Designer project and its control map by Claude Code, so a canvas says two things: how the panel looks, drawn only with these components, and what every control does.

## Designing a panel

Start from what the panel has to do - the rooms, sources, calls and settings - and give every job a control. Then draw it in {t}'s own grammar (below): the template says where each control goes and how it looks; you say what each one is for.

- **One artboard per page or popup.** Its root is one `{ns}.Page`, at {w}x{ht} for a page or a modal popup and {p['popup'][0]}x{p['popup'][1]} for a {_popup_noun(p)}. Name the start page's file `Main.dc.html`, as the canvas names its entry, and every other plainly (`Call.dc.html`, `Help.dc.html`); a `nav` names one by that stem (`nav="Main"`). Give each Page a `name` - what the panel calls it - and mark the start page `start="true"`.
{_panels_readme(p)}- **Only these components are built.** Use {comps} for everything that shows, and `{ns}.MainArea` to place the main task of a page {'that has no regions' if regions else 'in the main region'}. Flex and grid containers that paint nothing are fine for layout. Text, color, borders, images or icons drawn any other way are reported and never reach the panel.
- **Say what every control does.** A button that shows another page or popup has `nav` - the target artboard's file stem - and becomes a working link in Play; on the panel the program shows it, as the control map tells the programmer to. Anything else it does goes in `does`, a plain sentence for the programmer: "Routes the laptop to the display." Labels the program rewrites, sliders and levels get a `does` too.
- **Give feedback with `states`.** A button's `states` are what the program switches it between, in order: `"Off, On"`, or `No Signal / Ready / Live` with each its own look. Every state must look different: the spec check refuses two alike, since the panel would show no change. `press` is the state shown while it is held.
- **A page or popup the program opens by itself**, like an incoming call, has `reached-by="program"`; a button may lead to it as well. Every other page must be reachable by `nav` from the start page.
- **A control on several pages** - Volume on Home and on Call - is a control on each, with an ID of its own. To make it one control to the program, give every copy the same `id`, a number under 1000 of your own (`id="101"`), and the same kind, `nav`, `does` and `states`: copies that do different things - Join Call opening the call page on Home and joining on Call - keep IDs of their own.

{_grammar_md(p, renders)}{_working_md(p)}{_center_md(p)}{_windows_md(p, renders)}{_writing_md(p)}{_handover_md(p)}{_free_pages_md(p)}{_differences_md(p)}{_layout_md(p)}{_panels_section(p)}{_themes_md(p)}## Visual foundations

- **Color.** Use the tokens by name, each for what its note says. {p['examples']['color_rule']} Extron caps a project at **six colors** (Design Standards p.49), captions included. The tokens here are the template's own palette and do not count against the six; any color you add by hex does, so keep to the tokens.
- **Type** is {p['font']['family']}.{(' ' + p['font']['note']) if p['font'].get('note') else ''} Sizes are points, drawn at {p['pt']} px per point as GUI Designer draws them: {type_line}. Nothing under 14 pt: that is the toolkit's floor, and a template's own smallest captions can be under it.
- **Shapes** come from the template's border resources only: {border_line}. The panel cannot draw any other corner, a gradient or a shadow; a fill's transparency is its alpha (a token's `#RRGGBBAA`).
- **Size and spacing** follow the panel's physical size: every button and slider at least {p['touch']} px each way (9 mm on a {p['model']}), at least {p['spacing']} px between touchable controls (2 mm), no more than nine buttons in one group, and place things on GUI Designer's 10 px nudge - Extron's Design Standards, which its own templates do not always keep{'; the region components keep a set the template stands together (a Header tab row, a Section) as one set, at the step the frame measures' if regions else ''}. {t}'s usual button is {p['defaults']['button']['height']} px tall.

## Iconography

{p['iconography']['intro']}

{chr(10).join('- ' + r for r in p['iconography']['rules'])}

## Consuming this system

The components are `window.{ns}` - `{ns}.Page`, `{ns}.Button` and the rest - each mounted with `<x-import component-from-global-scope="{ns}.Button">`. Install the system on the canvas, then load in each artboard's `<head>`, after the `support.js` line, `components/bundle.css` and then `components/bundle.js` from the installed copy (`ds/<folder>/components/`). Each component's props, with an example, are in `components/<Name>/README.md`. The type is {p['font']['family']}, from Google Fonts: `<link rel="stylesheet" href="{p['font']['google']}">` in each artboard's `<helmet>`.
"""


def _themes_md(p):
    """`## Themes`: the template's background photographs, where it has them."""
    if not p.get('themes'):
        return ''
    t = p['template']
    # Afterburn's are Extron's pairings of a background and an accent scheme;
    # a template with one scheme (Mach) has photographs only, and Extron
    # publishes no pairing for it.
    one = len(p['schemes']) == 1
    return ('## Themes\n\n'
            + (f"Each theme is one of {t}'s background photographs from its kit, with its one accent "
               "scheme" if one else
               "Each theme is one of Extron's recommended pairings of a background image and an accent "
               "scheme")
            + '; set it with `theme` on every Page:\n\n'
            + '\n'.join(f"- `{th['id']}`: {th['usage']}" for th in themes(p))
            + '\n\nThe image is drawn on the page it is set on, under the controls, and built into '
              'the panel as that page\'s background image.'
            + (f" {p['themes_note'][0].upper()}{p['themes_note'][1:]}." if p.get('themes_note') else '')
            + ('' if one else ' Extron allows mixing a background with another accent scheme: '
                              '`scheme` on the Page does that.') + '\n\n')


def _layout_md(p):
    """`## Layout`: the bands and rects are the frame's, written from it; what
    the profile adds by hand (`layout.regions`) is how to compose in them, and
    the claim lint holds it to what the template does."""
    ns, t = p['namespace'], p['template']
    lay = p.get('layout') or {}
    main = lay.get('main')
    measured = frame_layout(p)
    if not (lay.get('regions') or measured):
        return ''
    # A region theme's working pages are composed one way; its Start and
    # mode pages are not (Pages without regions).
    out = (f"## Layout\n\n{t}'s working pages are composed the same way" if measured
           else f"## Layout\n\n{t} pages are composed the same way")
    return (out + f"; follow it, or the panel works but does not look like {t}.\n\n"
            + (measured + '\n' if measured else '')
            + '\n'.join(f'- {r}' for r in lay.get('regions') or ())
            + ('\n\n' if lay.get('regions') else '')
            + (f"`{ns}.MainArea` is that main region ({main[2]}x{main[3]} at "
               f"{main[0]},{main[1]}): {lay.get('main_task') or ('put the main task of a page with no regions inside it (Pages without regions).' if _regions(p) else 'put the main task inside it.')}"
               if main else '')
            + '\n\n')


# -- the grammar --------------------------------------------------------------
# Each family of panels a theme's templates draw its working page for: the
# bar panels (tier A), the hubs (the 520s and 535s) and the 320, each with
# the model its frame and its render are read off.
_FAMILIES = (('bar', None, 640), ('hub', 'TLP525T', 400), ('pages', 'TLP320M', 320))


def template_renders(p):
    """The template renders a build makes: each family's working page - the
    page its frame was measured off (Main SD, a hub's Main Page, the 320's
    first source page) - rendered off that family's own seed with
    gdl.compose and downscaled to `size`, as a WebP the README shows beside
    its grammar. Extron's artwork: the private design system only (the owner's
    call 3, docs/superpowers/specs/2026-10-22-region-frame-design.md)."""
    ms = models(p)
    out = []
    for family, model, width in _FAMILIES:
        model = model or p['model']
        T = ms.get(model) or {}
        if not T.get('frame') or not T.get('seed'):
            continue
        page, screen = T['frame']['page'], T['size']
        k = min(1, width / screen[0])
        series = T['series'][len(p['template']):].strip().removesuffix(' Series')
        slug = re.sub(r'[^a-z0-9]+', '-', f"{p['template']} {series} {page}".lower()).strip('-')
        # What its popup region shows: the source popup the frame was measured
        # off (Laptop, the empty state) on a bar panel; a hub's Select a
        # Source, the program's first - its own popup, or the page's own grid
        # with the region empty (None); the 320's page has none.
        F = T['frame']
        shows = ((F.get('center') or {}).get('popup') if family == 'bar' else
                 (F.get('select') or {}).get('popup') if family == 'hub' else None)
        size = [round(screen[0] * k), round(screen[1] * k)]
        out.append({'family': family, 'model': model, 'series': T['series'], 'seed': T['seed'], 'page': page,
                    'shows': shows, 'screen': list(screen), 'size': size, 'file': f'templates/{slug}.webp'})
        if family != 'bar':
            continue
        # And two of its windows over that page, as the panel shows them -
        # the question and the settings window the README's lighting
        # launcher opens - which a designer otherwise read off coordinates.
        wins = F.get('windows') or {}
        launchers = (((p.get('writing') or {}).get('voice') or {}).get('launchers') or ['Lighting'])
        lit = next((lw for lw in launchers if 'Lighting' in lw), launchers[0])
        sw = _settings_for(F, lit)
        named = next((q for q in sw.get('popups') or () if str(q).split()[0] == lit.split()[0]),
                     (sw.get('popups') or [None])[0])
        for role, popup in (('confirm', (wins.get('confirm') or {}).get('popup')), ('settings', named)):
            if not popup:
                continue
            wslug = re.sub(r'[^a-z0-9]+', '-', f"{p['template']} {series} {popup}".lower()).strip('-')
            out.append({'family': family, 'window': role, 'model': model, 'series': T['series'], 'seed': T['seed'],
                        'page': popup, 'base': page, 'shows': None, 'screen': list(screen), 'size': size,
                        'file': f'templates/{wslug}.webp'})
    return out


def render_templates(p, plan=None):
    """{file: WebP bytes} for each template render whose seed is here (Git
    LFS) and whose page draws; a note names what could not be, since a build
    without them looks like any other."""
    plan = template_renders(p) if plan is None else plan
    t = p['template']
    try:
        import io
        from PIL import Image
        from ..compose import load as load_gdl, render_snapshot
    except ImportError:
        print(f'  note: Pillow is not installed - the {t} system shows no render of its template')
        return {}
    from .. import compose, seeds
    out, missing, built = {}, [], {}
    for r in plan:
        if not seeds.usable(r['seed']):
            missing.append(r['seed'])
            continue
        # Translucent chrome as the panel shows it, the photo through it, not
        # as GUI Designer's snapshot paints it (compose.BINARY) - and the rule
        # put back as it was, so a caller's outlives the render.
        was = compose.BINARY
        compose.BINARY = False
        try:
            if r.get('window'):
                # A window over its page, under Build's scrim, as the critique
                # loop draws the template's (gdl.design._Built).
                from ..design import _Built
                if r['seed'] not in built:
                    built[r['seed']] = _Built(seeds.path(r['seed']))
                img = built[r['seed']].image(r['page'], tuple(r['screen']), base=r.get('base'))
                if img is None:
                    raise LookupError(f"the seed has no {r['page']}")
                img = img.convert('RGB')
            else:
                j, assets = load_gdl(seeds.path(r['seed']))
                pg = next(x for x in j['Pages'] if x['Name'] == r['page'])
                ids = {x['Name']: x['ID'] for x in j['PopupPages']}
                shown = {}
                for c in pg.get('Controls') or ():
                    ref = c.get('PopupPageID')
                    if isinstance(ref, dict) and ref.get('IsPopupGroupIdValid') and r['family'] != 'pages':
                        shown[ref['GroupID']] = ids.get(r['shows'])
                img = render_snapshot(j, pg['ID'], assets, tuple(r['screen']), shown=shown).convert('RGB')
        except (StopIteration, LookupError, OSError, ValueError) as e:
            print(f"  note: {r['seed']}'s {r['page']} did not render ({e}) - the {t} system shows no render "
                  f'of it')
            continue
        finally:
            compose.BINARY = was
        buf = io.BytesIO()
        img.resize(tuple(r['size']), Image.Resampling.LANCZOS).save(buf, 'WEBP', quality=80, method=6)
        out[r['file']] = buf.getvalue()
    if missing:
        print(f"  note: {', '.join(sorted(set(missing)))} {'is' if len(set(missing)) == 1 else 'are'} not here "
              f"(git lfs pull) - the {t} system shows no render of {'its' if len(set(missing)) == 1 else 'their'} "
              f"working page")
    return out


def template_card(p, plan, images):
    """The design system's card of the template renders: each family's
    working page, as the README shows it."""
    import base64
    shown = [r for r in plan if r['file'] in images]
    # A row of the working pages, then a row of the windows over them.
    rows = [[r for r in shown if not r.get('window')], [r for r in shown if r.get('window')]]
    rows = [row for row in rows if row]
    height = sum(max(r['size'][1] for r in row) + 72 for row in rows)

    def fig(r):
        return (f'<figure style="margin:0"><img src="data:image/webp;base64,'
                f'{base64.b64encode(images[r["file"]]).decode()}" width="{r["size"][0]}" height="{r["size"][1]}" '
                f'alt="{html.escape(_render_alt(p, r))}"><figcaption style="margin-top:6px">'
                f'{html.escape(_render_alt(p, r))}</figcaption></figure>')
    figs = ''.join('<div style="display:flex;gap:16px;padding:16px 16px 0;align-items:flex-start">'
                   + ''.join(fig(r) for r in row) + '</div>' for row in rows)
    return (f'<!-- @dsCard height={height} -->\n<!doctype html>\n<html>\n<head><meta charset="utf-8">'
            f"<title>{p['template']} template</title></head>\n"
            '<body style="margin:0;background:#16171d;color:#e8e8ee;font:13px/1.4 system-ui,sans-serif">\n'
            f'{figs}\n</body>\n</html>\n')


def _render_alt(p, r):
    if r.get('window'):
        return f"{p['template']}'s {r['page']} over its {r['base']} on the {r['model']}, off {r['seed']}"
    shows = (f", {r['shows']} in its popup region" if r.get('shows') else '')
    return f"{p['template']}'s {r['page']} on the {r['model']}{shows}, off {r['seed']}"


def _render_md(p, renders, family, window=None):
    r = next((x for x in renders or () if x['family'] == family and x.get('window') == window), None)
    return f"![{_render_alt(p, r)}]({r['file']})\n\n" if r else ''


def _family_series(p, family):
    """The series of a family, named without the theme, smallest number first
    for the hubs: ['1220', '1020', ...], ['520', '535'], ['320']."""
    if family == 'bar':
        return _series_named(p, lambda s: s.get('tier') == 'A')
    if family == 'hub':
        return sorted(_series_named(p, lambda s: s.get('tier') == 'B'),
                      key=lambda n: int(n.split()[0]) if n.split()[0].isdigit() else 0)
    return [n for n in _series_named(p, lambda s: s.get('tier') == 'C') if n.startswith('320')]


def _say(words):
    words = [x for x in words if x]
    return ', '.join(words[:-1]) + ' and ' + words[-1] if len(words) > 1 else (words[0] if words else '')


_GRAMMAR_ROLES = {'heading': 'its Volume heading', 'volume': 'the volume slider', 'mute': 'Mute',
                  'audio': 'Audio Control', 'power': 'Power', 'help': 'Help', 'mode': 'the mode launcher (Room Mode)',
                  'clock': 'the date and time', 'volume-up': 'Up', 'volume-down': 'Down',
                  'display': 'Display Control', 'settings': 'the settings opener'}


def _roles_said(items):
    def said(i):
        # The settings opener by its name where that is not the role's own:
        # Shockwave's and Turbulence's hubs caption theirs More.
        if i['role'] == 'settings' and i.get('name') and i['name'] != 'Settings':
            return f"the settings opener ({i['name']})"
        return _GRAMMAR_ROLES.get(i['role'], i['role'].replace('-', ' '))
    return _say(list(dict.fromkeys(said(i) for i in items or () if i.get('role') and i['role'] != 'surface')))


def _power_words(p):
    """How the template captions its power key (`regions.power`): Shockwave's
    says Off, Mach's and Turbulence's are its icon alone."""
    r = (p.get('regions') or {}).get('power') or {}
    if r.get('text'):
        return f"captioned '{r['text']}'"
    return 'its icon alone' if r.get('icon') else ''


def _foot_words(p, right, bottom):
    """The grammar's RightRail and Footer bullets' words, by the components'
    own split: Power and Help are the Footer's wherever the template stands
    them (bundle.js planRightRail), and Room Mode and Audio Control are drawn
    only where the canvas gives one."""
    ns = p['namespace']
    moved = [i for i in right.get('items') or () if i.get('role') in ('power', 'help')]
    rail = [i for i in right.get('items') or () if i.get('role') not in ('power', 'help', 'surface')]
    foot = [i for i in bottom.get('items') or () if i.get('role') not in ('surface', 'mode')] + moved
    bp = ((p.get('writing') or {}).get('buttons') or {}).get('power', 'Power Down')
    pw = _power_words(p)
    where = ('at the foot of the right rail, where the template stands it'
             if any(i['role'] == 'power' for i in moved) else '')
    if where:
        power = (f" Its Power is {pw} - the Footer draws it {where} - and the question it opens answers {bp}."
                 if pw else f" The Footer draws its Power {where}, and the question it opens answers {bp}.")
    else:
        power = (f" Its Power is {pw}, and the question it opens answers {bp}." if pw else
                 f" The question its Power opens answers {bp}.")
    audio = any(i['role'] == 'audio' for i in rail)
    mode = any(i.get('role') == 'mode' for i in bottom.get('items') or ())
    return (f"- **RightRail** (`{ns}.RightRail`): {_roles_said([i for i in rail if i['role'] != 'audio'])}"
            + ("; Audio Control under them only where you give it one (`slot=\"audio\"`)" if audio else '')
            + (_audio_left(p) if audio else '') + ".\n"
            + f"- **Footer** (`{ns}.Footer`): {_roles_said(foot)}"
            + ("; the mode launcher (Room Mode) only where you give it one (`slot=\"mode\"`)" if mode else '')
            + "." + (power if any(i['role'] == 'power' for i in foot) else '') + "\n")


def _grammar_md(p, renders):
    """`## The template's grammar`: the regions of the template's working page
    on each family of panels and what lives in each, off the frames; the
    template's own working page rendered beside it."""
    t, ns = p['template'], p['namespace']
    ms = models(p)
    if not _regions(p):
        hub = (ms.get('TLP525T') or {}).get('frame') or {}
        small = (ms.get('TLP320M') or {}).get('frame') or {}
        sel = (hub.get('select') or {}).get('text')
        hub_right = (hub.get('right') or {}).get('items') or ()
        foot = (small.get('bottom') or {}).get('rect')
        hub_help = ("in its rail beside the settings opener and Power" if any(i.get('role') == 'help' for i in hub_right)
                    else f"at the top of '{sel or 'Select a Source'}'")
        return (f"## The template's grammar\n\n"
                f"{t} draws its chrome - the squircle, the grounds of its rails, its foot - as background art, "
                f"not controls, so this system has no region components: a page places its own controls where the "
                f"Layout gives them - the left rail's on the Page, the squircle's in `{ns}.MainArea` - with the right "
                f"column in a `Rail` and the selected source's controls in a `PopupRegion`.\n\n"
                f"### The bar panels ({_the_series(_family_series(p, 'bar'))})\n\n"
                + _render_md(p, renders, 'bar')
                + f"A working page is the squircle between two rails: the row of sources across its top over a "
                  f"divider, the selected source's popup under it, the date and time at its foot; the left rail's "
                  f"groups under their headings, the right rail's volume, Mute, Help and Power. The Layout gives "
                  f"each its place.\n\n"
                + (f"### The hubs ({_the_series(_family_series(p, 'hub'))})\n\n" + _render_md(p, renders, 'hub')
                   + f"**What a hub makes of your page.** The template's hub keeps a rail of "
                     f"{_roles_said(hub_right)} down its right"
                   + (f" and starts from '{sel}'" if sel else '')
                   + ". This system lays your page out in the hub's main region beside that rail, scaled, its "
                     "controls grown to the hub's touch minimum (Every panel the room has) - the left rail's "
                     "`Group` a cell at a time with its arrows (The working page).\n\n"
                   if hub else '')
                + (f"### The 320 ({_the_series(_family_series(p, 'pages'))})\n\n" + _render_md(p, renders, 'pages')
                   + "**What the 320 makes of your page.** The template gives each source a page of its own, over a "
                   + (f"{foot[3]} px " if foot else '')
                   + "strip at its foot that holds the page's name with More and Back, and draws no volume, Help or "
                     "Power on screen. This system reflows your page into rows instead, over your Rail run across "
                     "the 320's foot, and draws each source popup as a page of its own too, with a Back at the "
                     "foot's left - the 320's seed has no standard popup - leaving the `PopupRegion` off (Every "
                     "panel the room has, and Differences).\n\n"
                   if small else '')
                + f"**Where Help goes.** In the Rail, with Power, on the bar panels: the template stands the two "
                  f"side by side at the right rail's foot. On a hub, {hub_help}. On the 320 the template draws no "
                  f"Help on screen; this system puts the Rail's Help in the row it runs across the 320's foot. Help "
                  f"opens an artboard of its own, a modal Page you draw (Windows).\n\n")
    F = _design_frame(p)
    hub = (ms.get('TLP525T') or {}).get('frame') or {}
    small = (ms.get('TLP320M') or {}).get('frame') or {}
    top, left, right, bottom, center = (F.get(k) or {} for k in ('top', 'left', 'right', 'bottom', 'center'))
    tabs = top.get('tabs') or {}
    ends = [i for e in ('start', 'end') for i in top.get(e) or () if i.get('role') != 'surface']
    groups = left.get('groups') or ()

    def group_words(i, g):
        # By role, not the seed's control names: Mach names its launchers
        # Lighting Settings and captions them Lighting (writing.voice).
        h = (g.get('heading') or {}).get('text')
        said = _say([b['role'].split('-', 1)[-1].replace('-', ' ').title() for b in g.get('buttons') or ()
                     if b.get('role')])
        what = (f"{said}, the room's display" if i == 0 else f"the {said} launchers, which open settings windows")
        return f"'{h}' over {what}" if h else what
    region = center.get('region')
    out = (f"## The template's grammar\n\n"
           f"{t}'s working page is one grammar: five regions - the header, the left rail, the right rail and the "
           f"footer round the center - that stay put from page to page, and a center that changes with the "
           f"source. Draw a working page in its regions (The working page) and every panel the room has draws "
           f"it in the grammar of its own template: the bar panels round the center, a hub as a menu bar beside popups "
           f"that fill main, the 320 as pages under a title strip.\n\n"
           f"### The bar panels ({_the_series(_family_series(p, 'bar'))})\n\n"
           + _render_md(p, renders, 'bar')
           + f"- **Header** (`{ns}.Header`): {tabs.get('count') or len(tabs.get('items') or ())} source tabs on the "
             f"{p['model']} - one per source, `slot=\"source\"` - each showing its source's popup in the Center "
             f"while the page stays"
           + (f"; at its ends, {_roles_said(ends) or _say([i['name'] for i in ends])}" if ends else '') + ".\n"
           + f"- **LeftRail** (`{ns}.LeftRail`): its Sections in order - "
           + '; then '.join(group_words(i, g) for i, g in enumerate(groups)) + ".\n"
           + _foot_words(p, right, bottom)
           + f"- **Center** (`{ns}.Center`): the popup region"
           + (f" ({region[2]}x{region[3]} on the {p['model']})" if region else '')
           + " that the selected source's popup fills - its controls, or the template's empty state. Nothing "
             "else stands there.\n\n"
           + _grammar_art(p)
           + f"They stay put: only the Center changes when a source is chosen, and Help, the settings and the "
           f"power-down question open windows over the page (Windows).\n\n")
    if hub:
        sel, opt = hub.get('select') or {}, hub.get('options') or {}
        display = any(i.get('role') == 'display' for i in (hub.get('right') or {}).get('items') or ())
        opener = next((i.get('name') for i in (hub.get('right') or {}).get('items') or ()
                       if i.get('role') == 'settings'), None)
        # Shockwave's and Turbulence's hubs caption theirs More, as the 320
        # captions its paging key: two controls, one word.
        opened = ("The settings opener, More - not the 320's More, which goes on to more of Main's pages -"
                  if opener == 'More' else f"The settings opener, {opener}," if opener and opener != 'Settings'
                  else 'The settings opener')
        out += (f"### The hubs ({_the_series(_family_series(p, 'hub'))})\n\n" + _render_md(p, renders, 'hub')
                + f"**What a hub makes of your page.** No header bar, left rail or footer: a menu bar down the right "
                  f"holds {_roles_said((hub.get('right') or {}).get('items'))}, and main is one popup region that "
                  f"every popup fills. The program shows '{sel.get('text')}' first: the Header's source tabs as its "
                  f"tiles - the same controls, so the same IDs - under its title"
                + (", with Help at its top" if sel.get('help') else '')
                + f". {opened} shows '{opt.get('text')}': the later Sections' launchers, an Audio Control "
                  f"and the Footer's mode launcher, as its tiles. The first Section is a popup of its own, opened "
                + ("by the bar's Display Control" if display else "from a Display tile among the options")
                + f". A source's popup fills main under its title, with a Close back to '{sel.get('text')}'; a "
                  f"settings window is a popup there too; Help, the question and the wait stay windows."
                + (f" The source and settings popups, the options and the first Section's popup stand on the page's "
                   f"photo, stretched to the popup" + (", a source's with its device picture under its title" if _device_pictures(p) else '')
                   + f"; '{sel.get('text')}' is the page's own grid, on the photo itself." if _hub_photo(p) else '')
                + " The clock, which no hub draws, is named and left.\n\n"
                + _hub_derived_md(p, hub))
    if small:
        home = next((i.get('text') for i in ((small.get('home') or {}).get('top') or {}).get('items') or ()
                     if i.get('text')), 'Select a Source')
        strip = (small.get('top') or {}).get('rect') or [0, 0, 0, 36]
        out += (f"### The 320 ({_the_series(_family_series(p, 'pages'))})\n\n" + _render_md(p, renders, 'pages')
                + f"**What the 320 makes of your page.** No bar, rail or footer: every page stands under a "
                  f"{strip[3]} px title strip. Main is '{home}': the Header's source tabs as keys under the strip, "
                  f"two to a row, the same controls. More, at the foot, goes on to pages of Main's own holding what "
                  f"the 320 keeps off its pages - the Sections as columns under their headings, the volume's heading "
                  f"and Mute, the mode launcher, Help and Power - and Back {_back_where(p)} comes back. A source, a "
                  f"settings window and Help are pages under the strip titled with them; the question and the wait "
                  f"are pages of their own. The volume slider is the level in the Volume window the program shows; "
                  f"the clock and the Center's popup region are named and left.\n\n"
                + _small_derived_md(p, small))
    # Help is the Footer's wherever the template stands it (planFooter).
    moved = any(i.get('role') == 'help' for i in right.get('items') or ())
    sel = hub.get('select') or {}
    hub_help = (f"at the top of '{sel.get('text') or 'Select a Source'}'" if sel.get('help') else
                'in its rail' if any(i.get('role') == 'help' for i in (hub.get('right') or {}).get('items') or ())
                else "on no page of its own: the Footer's Help is named there")
    out += (f"**Where Help goes.** In the Footer on the bar panels"
            + (", which stands it in the right rail where the template does" if moved else '')
            + f", drawn by default and opening the artboard its `help` names; on a hub, {hub_help}; on the 320, on "
              f"a page of Main's own, reached by More. Draw it once, as an artboard of its own - a Page with "
              f"`kind=\"modal\"` and `role=\"help\"` (Windows): a window over the page on the bar panels and the "
              f"hubs, and on the 320 a page under the strip, with Back.\n\n")
    return out


def _hub_derived_md(p, hub):
    """What a hub's region page draws by itself, by the template's names, and
    what a designer may draw in their place (gdl.design._one_name_each)."""
    sel, opt = hub.get('select') or {}, hub.get('options') or {}
    items = (hub.get('right') or {}).get('items') or ()
    display = next((i.get('name') for i in items if i.get('role') == 'display'), None) or 'Display Settings'
    names = [sel.get('popup') or 'Select Source', opt.get('popup') or 'More Options', display, 'Volume Level']
    return (f"**What it draws by itself, and what you may draw.** {_say([repr(n) for n in names])} are the hub's, "
            f"named by its template and drawn from your working page - draw none of them. Two working pages - "
            f"Main SD and a call page - make one of each where they give it the same controls, and the later "
            f"page's own, named for that page ('Video Call {names[1]}'), where they do not. A window you draw "
            f"yourself under one of those names - a {display} settings window, which the grammar invites - is "
            f"that window where it holds every control the hub would put in it, with the same `id`s (the "
            f"LeftRail's first Section's, there), and its title then says the Section's heading; where it holds "
            f"others, the hub's takes its page's name and yours stays a window of its own.\n\n")


def _small_derived_md(p, small):
    """What the 320's region page draws by itself, and the room its columns
    give words (off its frame: its keys, its headings, its floor)."""
    C = small.get('center') or {}
    key = (C.get('row') or [[0, 0, 0, 0]])[0]
    head = (C.get('headings') or [[0, 0, key[2], 0]])[0]
    floor = next((T['floor'] for m, T in models(p).items() if T.get('frame') is small), 14)
    vol = (small.get('volume') or {}).get('popup') or 'Volume'

    def letters(w):
        # Open Sans averages about 0.55 em a letter; 8 px for the key's edges.
        return max(1, int((w - 8) / (0.55 * floor * p['pt'])))
    return (f"**What it draws by itself.** Main's later pages (`Main SD 2` and on) and the '{vol}' window the "
            f"program shows are the 320's, drawn from your working page - one '{vol}' for every working page; "
            f"draw none of them.\n\n"
            f"**Words on the 320.** What you put in a source or a window stands in the 320's columns, as its "
            f"frame measures them: each key {key[2]}x{key[3]}, room for a word of about {letters(key[2])} letters at its {floor} pt floor "
            f"(two words go on two lines), each column's heading {head[2]} px wide - about {letters(head[2])} "
            f"letters. A `Group`'s `title` is drawn on the 320 alone, as its column's heading: make it one short "
            f"word (Presets, not Camera Presets). A Label over a Group stands at the top of the column beside it "
            f"on the 320, as that column's heading - leave the heading to the Group's `title`. Words alone - Help "
            f"in your own words - are set across the page under the strip instead, going on over a second page "
            f"by More and Back.\n\n")


# -- the working page -----------------------------------------------------------
# A source the kit draws no picture of, by the stems a kit names the nearest:
# Afterburn's streaming, Mach's media-player_1, Shockwave's media-player_white.
_STREAMING = ('streaming', 'media-player', 'apple-tv', 'play', 'sharelink')


def _r10(v):
    """A place on GUI Designer's 10 px nudge."""
    return int(round(v / 10.0)) * 10


def _at(r, o=(0, 0)):
    return (f'position: absolute; left: {r[0] - o[0]}px; top: {r[1] - o[1]}px; width: {r[2]}px; '
            f'height: {r[3]}px')


def _room_panels(p):
    """The README example room's panels: the README's own four - Afterburn's
    too, its working page drawn in the layout that carries to them
    (_afterburn_working), since a round-four designer copying its 1035-only
    room met 149 refusals on the 725, the 525 and the 320."""
    return _panels_eg(p, models(p))


def _room_attrs(p, start=False):
    """An example Page's `panels` and `theme`: the README example room's
    panels (_room_panels), and the theme the template draws behind that kind
    of page (Shockwave's Start on `saturn`, its working pages on `haze`)."""
    out = f' panels="{_room_panels(p)}"'
    if p.get('themes'):
        ths = themes(p)
        pick = next((th for th in ths if start and re.search(r'\bStart\b', th.get('usage') or '')), ths[0])
        out += f' theme="{pick["id"]}"'
    return out


def _glyph(p, names, *stems):
    """The tab look's own glyph for a source, by the stems its kit names it
    with, in the pattern of the template's tab icon - Shockwave's
    laptop_white gives pc_white, Turbulence's input_laptop input_pc - or
    None where the kit has none. A PC tab named no icon drew the look's
    default laptop."""
    icon = _tab_icon(p)
    pattern = icon.replace('laptop', '{}', 1) if 'laptop' in icon else '{}'
    for s in stems:
        for n in (pattern.format(s), s):
            if n in names:
                return n
        hit = sorted(n for n in names if n.startswith(pattern.format(s) + '_') or n.startswith(s + '_'))
        if hit:
            return hit[0]
    return None


def _glyphs_md(p, names):
    """The working page's sentence on each source's glyph, from the kit."""
    said = [(w, _glyph(p, names, s)) for w, s in (('a Laptop', 'laptop'), ('a PC', 'pc'), ('a Doc Cam', 'doc-cam'))]
    said = [f'`{g}` for {w}' for w, g in said if g]
    if not said:
        return ''
    stream = _glyph(p, names, *_STREAMING)
    tail = (f"; a source the kit draws no picture of takes the nearest it has: `{stream}` for Streaming" if stream
            else "; a source the kit draws no picture of, such as Streaming, takes `blank`, its caption alone"
            if 'blank' in names else '')
    return (f"Give every source its own glyph from its look's `icon` list (the Button README): "
            f"{_say(said)}{tail}.\n\n")


def _noun(name):
    """A source's name in a sentence, as bundle.js said() puts it: Laptop's
    'laptop', PC's 'PC'."""
    return ' '.join(w.lower() if len(w) > 1 and w[1:] == w[1:].lower() else w for w in name.split(' '))


def _start_example(p):
    """The template's Start page - its profile's own (`examples.start`) - the
    page the panel boots to, leading on to the working page: placed on the
    Page, or in the main region where the template's chrome is art
    (Afterburn's squircle, whose Start the truth ledger's afterburn-30
    measured)."""
    regions = _regions(p)
    main = None if regions else (p.get('layout') or {}).get('main')
    o = main[:2] if main else (0, 0)
    pad = '\n      ' if main else '\n    '

    def part(s):
        # A set - the presets - is a Group, its members with no places of
        # their own: so it pages, or shows in a popup, where a panel the room
        # has cannot hold it in place (Every panel the room has).
        body = (pad + pad.join(_x(p, 'Button', ' ' + m['attrs'], m.get('text', '')) for m in s['members'])
                + pad[:-2] if s.get('members') else s.get('text', ''))
        return _x(p, s.get('component', 'Button'), ' ' + s['attrs'], body, _at(s['rect'], o))
    parts = [part(s) for s in (p.get('examples') or {}).get('start') or ()]
    splash = ' splash="true"' if regions else ''
    body = ('\n  ' + _x(p, 'MainArea', '', '\n    ' + '\n    '.join(parts) + '\n  ') + '\n' if main
            else '\n  ' + '\n  '.join(parts) + '\n')
    return ("<!-- The page the panel boots to: Main.dc.html, the canvas's entry. -->\n"
            + _x(p, 'Page', f' name="Start"{splash} start="true"{_room_attrs(p, start=True)}', body))


def _settings_for(F, label):
    """The frame's settings window a window titled `label` is drawn from, as
    bundle.js windowOf() picks it: the one whose template window's name
    begins as the title does, else the first."""
    ws = (F.get('windows') or {}).get('settings') or []
    first = (label or '').split()[0].lower() if label else ''
    return next((r for r in ws if any(str(q).split()[0].lower() == first for q in r.get('popups') or ())),
                ws[0] if ws else {})


def _preset_size(p):
    """A preset key's size in a settings window: the template's usual
    height, at its look's own shape where the look is kit art (Shockwave's
    712x440 button), so the art is not letterboxed."""
    bh = p['defaults']['button']['height']
    V = p['buttons'].get(p['defaults']['button']['variant']) or {}
    if V.get('kit') and re.match(r'^\d+x\d+$', V['kit']):
        kw, kh = _kit_size(p, V['kit'])
        return _r10(bh * kw / kh), bh
    return 100, bh


def _working_md(p):
    """`## The working page`: how to draw one, and a complete room - Start,
    the working page and every artboard it leads to, one each."""
    ns, t = p['namespace'], p['template']
    themed = ' and its theme in `theme`' if p.get('themes') else ''
    room = (f"A complete room, one artboard each: Start, the page the panel boots to (`Main.dc.html`, the "
            f"canvas's entry); the working page; a source with no controls and one with them; a settings window; "
            f"Help; the power-down question and its wait. Every Page lists the room's panels in `panels`{themed}, "
            f"and a set of like controls - the presets, a camera's keys - is a `Group` whose box leaves the room "
            f"the room's smaller panels need (Every panel the room has), so the room translates clean on each.")
    if not _regions(p):
        names = icon_names(p).get('source') or []
        region = list(((_design_frame(p).get('center') or {}).get('region')) or [200, 175, 880, 525])
        ms = models(p)
        floor725 = (ms.get('TLP725T') or {}).get('floor', 16)
        return (f"## The working page\n\n"
                f"{t} has no region components, so a working page places its own controls, each where the Layout "
                f"gives it, and every other panel the room has gets that page laid out for its own screen - scaled, "
                f"each control grown to its touch minimum and each word to its type floor - not redrawn in its own "
                f"template's grammar. Drawn at {t}'s own spacing - the left rail's groups on the Page under their "
                f"headings, 53 px tall and 12 px apart (Differences), the date and time at the main region's foot, "
                f"the popup region {region[2]}x{region[3]} - a working page carries to the panels of the "
                f"{p['model']}'s own scale alone. So for a room with a 725, a hub or the 320, draw it as the "
                f"example does, in the layout that carries to all of them:\n\n"
                f"- **The left rail** is one `Group` under one heading - its `toggle` and `list` buttons, in that "
                f"order, in cells {RAIL_CELL[0]} px deep and {RAIL_CELL[1]} apart, in a box {RAIL_BOX} px deep "
                f"from the rail's first place, with `cap=\"1\"`. Loose, each button only scales and grows about "
                f"its centre - on the 725 they ran into each other and into their headings - and a `list` button's "
                f"caption, set past its icon, needs 177 px at the 725's {floor725} pt, more than its 145 px rail; "
                f"a cell keeps its shape as it grows. The 725 shows the Group whole; a hub, which keeps no left "
                f"rail, a cell at a time with its arrows; the 320 as a button that opens its pages, its heading "
                f"at its left (Rows, Every panel the room has).\n"
                f"- **The sources** in a `Group` over the divider and the `PopupRegion` under it, "
                f"{region[2]}x{region[3]} where the Layout stands it, and every source popup that size "
                f"(`width=\"{region[2]}\" height=\"{region[3]}\"`, The center). The 320 gives each source a page "
                f"of its own and leaves the region off (Rows, Every panel the room has). A room with a 525 leaves "
                f"the date and time off the working page: drawn in the template's own boxes, the 525 refused "
                f"both, its type wider than they are.\n"
                f"- **The Rail** holds the Slider, Mute, Help and Power, in that order, with no positions and no "
                f"Volume heading: a hub's rail holds the volume and three buttons, and the row the Rail runs across "
                f"the 320's foot the volume and three. It stands them down the right rail on every panel - the "
                f"drawn one too, Help and Power one over the other where {t} sets them side by side "
                f"(Differences) - and in each other panel's own rail.\n"
                f"- **Windows and sets** with the 525's room (Every panel the room has): a set's cells "
                f"{SET_CELL[0]} px deep and {SET_CELL[1]} apart in a box that holds them all, since in a modal or a "
                f"popup a `Group` cannot page; a title twice as wide as the Layout's; the question and the wait "
                f"two lines deep; the answers 260x{SET_CELL[0]} and 40 apart.\n\n"
                f"Each source is a standard popup of the `PopupRegion`'s group (The center); Help, the question, "
                f"the wait and a set of settings are modal Pages you draw on a `Panel` card (Windows). Preview and "
                f"the left rail's mode button (Video Conference) are the room's own: draw them only where the room "
                f"has a preview or a mode - the mode button in the left rail's `Group`, in a room with a 725, a hub "
                f"or the 320.\n\n"
                + _glyphs_md(p, names) + room
                + f" The example's room is the {_say(_room_panels(p).split())}: drawn as above, it translates "
                  f"clean on each.\n\n"
                + ''.join(f"`{name}.dc.html`:\n\n```html\n{code}\n```\n\n" for name, code in _afterburn_working(p)))
    names = icon_names(p).get(((p.get('regions') or {}).get('tab') or {}).get('variant')) or []
    return (f"## The working page\n\n"
            f"Put `{ns}.Header` (the source tabs, `slot=\"source\"`), `{ns}.LeftRail` (titled `{ns}.Section`s), "
            f"`{ns}.RightRail` (volume), `{ns}.Footer` (mode, date and time, Help and Power) and `{ns}.Center` (the "
            f"popup region the sources fill) directly on the Page, with no positions: each is drawn where {t}'s own "
            f"working page draws it, on every panel from that panel's own template; what you put in it takes the "
            f"template's look unless you give it one, and what you do not give it - Volume, Mute, the clock, Help, "
            f"Power - it draws itself. A working page without one of them is named on the canvas and in the "
            f"translate report, and still builds. Each component's README says what goes in it.\n\n"
            + _glyphs_md(p, names)
            + room + " Extron's own Start also holds the volume: leave it to the working page's RightRail, or give "
              "a Slider there and the RightRail's `slot=\"volume\"` Slider one `id` of your own (Designing a "
              "panel).\n\n"
            + ''.join(f"`{name}.dc.html`:\n\n```html\n{code}\n```\n\n" for name, code in _working_example(p)))


def _working_example(p):
    """[(file stem, markup)]: Start, the page the panel boots to; the working
    page in its regions - the Header's source tabs each with its own glyph,
    the LeftRail's Sections under the headings its frame measures, the
    launchers in the template's words (`writing.voice`), the RightRail, the
    Footer and the Center; and every artboard it leads to, each drawn by its
    `role`. Every Page lists the example room's panels and its theme, and
    every place the example chooses is on GUI Designer's 10 px nudge."""
    def x(comp, attrs='', body='', style=''):
        return _x(p, comp, attrs, body, style)
    room = _room_attrs(p)
    voice = (p.get('writing') or {}).get('voice') or {}
    F = _design_frame(p)
    groups = [((g.get('heading') or {}).get('text') or '') for g in ((F.get('left') or {}).get('groups') or ())]
    first, second = (groups + ['Display'])[0] or 'Display', (groups[1:] + [''])[0]
    names = icon_names(p).get(((p.get('regions') or {}).get('tab') or {}).get('variant')) or []

    def src(name, *stems):
        ic = _glyph(p, names, *stems)
        return x('Button', f' slot="source" name="{name}"' + (f' icon="{ic}"' if ic else '')
                 + f' nav="{name}" does="Routes the {_noun(name)} to the display."', name)
    disp = ''.join('\n      ' + x('Button', f' name="Display {wd}" {a}', wd) for wd, a in (
        ('On', 'does="Turns the display on."'), ('Off', 'does="Turns the display off."'),
        ('Mute', 'states="Off, On" does="Mutes the display; On while muted."')))
    launchers = voice.get('launchers') or ['Lighting', 'Audio']
    sets = ''.join('\n      ' + x('Button', f' name="{lw}" nav="{lw}"', lw) for lw in launchers)
    main = ('<!-- The working page, reached from Start. -->\n'
            + x('Page', f' name="Main SD"{room}', '\n  ' + '\n  '.join([
                x('Header', '', '\n    ' + '\n    '.join((src('Laptop', 'laptop'), src('PC', 'pc'),
                                                        src('Doc Cam', 'doc-cam', 'document-camera')))
                  + '\n  '),
                x('LeftRail', '', '\n    ' + x('Section', f' title="{first}"', disp + '\n    ') + '\n    '
                  + x('Section', f' title="{second}"' if second else '', sets + '\n    ') + '\n  '),
                x('RightRail'),
                x('Footer', ' help="Help" power="Power Down"'),
                x('Center', ' group="Sources"')]) + '\n'))
    # A camera as the template draws one in its source popup: a heading over
    # its zoom keys, the in-well look's own glyphs on them where the kit has
    # them (Mach's plus and dash) - Title Case on the 1035, as its Doc Cam
    # popups head their columns (examples.camera).
    cam = (p.get('examples') or {}).get('camera') or {}
    look = (((p.get('regions') or {}).get('source') or {}).get('button') or {}).get('variant')
    well = icon_names(p).get(look) or []
    keys = []
    if cam:
        # The keys a Group, a column of two at the in-well look's shape, its
        # box the room the panels of the room need (Every panel the room has).
        k, icons = cam['key'], cam.get('icons') or [None, None]
        gap = cam['step'] - k[3]
        keys.append(x('Label', ' name="Zoom Label" align="center"', 'Zoom', _at(cam['heading'])))
        members = []
        for i, (n, d) in enumerate((('Zoom Tele', 'In'), ('Zoom Wide', 'Out'))):
            glyph = icons[i] if icons[i] in well else None
            members.append(x('Button', f' name="{n}"' + (f' icon="{glyph}"' if glyph else '')
                             + f' does="Zooms the document camera {d.lower()}."', '' if glyph else d))
        keys.append(x('Group', f' title="Zoom" cell="{k[2]}x{k[3]}" gap="{gap}" cap="1"',
                      '\n    ' + '\n    '.join(members) + '\n  ',
                      _at(cam.get('box') or [k[0], k[1], k[2], 2 * k[3] + gap])))
    # The presets go in the lighting window, where the launchers have one,
    # inside the settings window the frame draws for its title.
    lit = next((lw for lw in launchers if 'Lighting' in lw), launchers[0])
    title = (lambda lw: lw if lw.endswith('Control') else f'{lw} Settings')
    sw = _settings_for(F, title(lit))
    wr = sw.get('rect') or [0, 0, p['size'][0], p['size'][1]]
    wt = sw.get('title') or [wr[0], wr[1], 0, 40]
    bw, bh = _preset_size(p)
    # A row of three in a Group, its box wider and deeper than the row: a
    # Group in a window cannot page, so its box is the room it has on every
    # panel the room lists (Every panel the room has).
    gap = 40
    box_w, box_h = 3 * bw + 4 * gap, bh + 2 * gap
    px0, py0 = _r10(wr[0] + (wr[2] - box_w) / 2), _r10(wt[1] + wt[3] + 40)
    noun = lit.split()[0]
    members = [x('Button', f' name="{noun} {n}" does="Recalls the {n.lower()} {noun.lower()} preset."', n)
               for n in ('Full', 'Meeting', 'Off')]
    presets = [x('Group', f' title="Presets" cell="{bw}x{bh}" gap="{gap}" cap="3"',
                 '\n    ' + '\n    '.join(members) + '\n  ', _at([px0, py0, box_w, box_h]))]
    out = [('Main', _start_example(p)), ('Main SD', main),
           ('Laptop', '<!-- A source the room only routes: the Center draws its title and the empty state. -->\n'
            + x('Page', f' name="Laptop" kind="popup" group="Sources" role="source"{room}')),
           ('PC', x('Page', f' name="PC" kind="popup" group="Sources" role="source"{room}')),
           ('Doc Cam', x('Page', f' name="Doc Cam" kind="popup" group="Sources" role="source" title="Document Camera"'
                                 f'{room}', ('\n  ' + '\n  '.join(keys) + '\n') if keys else ''))]
    for lw in launchers:
        out.append((lw, x('Page', f' name="{lw}" kind="modal" role="settings" title="{title(lw)}"{room}',
                          ('\n  ' + '\n  '.join(presets) + '\n') if lw == lit else '')))
    out += [('Help', x('Page', f' name="Help" kind="modal" role="help"{room}')),
            ('Power Down', x('Page', f' name="Power Down" kind="modal" role="confirm" topic="power" '
                                     f'does="Powers the room down."{room}')),
            ('Powering Down', x('Page', f' name="Powering Down" kind="modal" role="wait" topic="down" '
                                        f'reached-by="program"{room}'))]
    return out


# Afterburn's example room is laid out for its four panels (_room_panels):
# its left rail one Group, its cells as deep and as far apart as the 725's
# touch minimum and gap need them at its page's 0.75 (60 and 13 px), in a box
# that holds all four there and one at a time with its arrows on the 525;
# its sets' cells and its windows' words and answers with the 525's room.
# Its popup region is the template's: the 320, where a 525-deep popup came
# out 133 px, 5 short of a source's title and its empty state, gives each
# source a page of its own.
RAIL_CELL = (80, 18)
RAIL_BOX = 500
SET_CELL = (110, 25)


def _afterburn_working(p):
    """[(file stem, markup)]: Afterburn's room as its Layout composes it,
    off its frame - Start; the working page, the left rail's groups under
    their headings on the Page, the sources in a Group over the divider, the
    PopupRegion and the date and time in the main region, the right column
    in a Rail; a source with no controls and one with them; a settings
    window, Help, the question and its wait, each on a Panel card the
    squircle's size (the truth ledger, afterburn-11), its words where the
    frame's windows stand them. Its system draws no chrome of its own, so
    every word is here."""
    def x(comp, attrs='', body='', style=''):
        return _x(p, comp, attrs, body, style)
    room = _room_attrs(p)
    w = p.get('writing') or {}
    b = w.get('buttons') or {}
    main = (p.get('layout') or {}).get('main') or [0, 0, p['size'][0], p['size'][1]]
    F = _design_frame(p)
    c = F.get('center') or {}
    tabs = c.get('tabs') or {}
    first = tabs.get('first') or [342, 37, 110, 110]
    pitch = tabs.get('pitch') or first[2] + 49
    # The region one source's popup fills, as the template draws it; its
    # popups take its size (a popup is its reference's size, Standards p.70).
    region = list(c.get('region') or [200, 175, 880, 525])
    names = icon_names(p).get('source') or []
    lists = icon_names(p).get('list') or []
    icons = icon_names(p).get('icon') or []
    voice = w.get('voice') or {}
    launchers = voice.get('launchers') or ['Lighting', 'Audio']
    # The room: the template's own source row (PC, Laptop, TV, Streaming) with
    # a Doc Cam where its TV stands, to show a source with controls.
    sources = (('PC', 'PC'), ('Laptop', 'laptop'), ('Doc Cam', 'doc cam'), ('Streaming', 'streaming player'))
    row = [first[0], first[1], (len(sources) - 1) * pitch + first[2], first[3]]
    cells = []
    for n, noun in sources:
        ic = _glyph(p, names, n.lower().replace(' ', '-')) if names else None
        cells.append(x('Button', f' name="{n}" variant="source"' + (f' icon="{ic}"' if ic else '')
                       + f' states="Off, On" nav="{n}" does="Routes the {noun} to the display."', n))
    inside = [x('Group', f' title="Sources" cell="{first[2]}x{first[3]}" gap="{pitch - first[2]}"',
                '\n      ' + '\n      '.join(cells) + '\n    ', _at(row, main))]
    for it in c.get('items') or ():
        if it.get('role') == 'divider':
            inside.append(x('Line', ' name="Divider"', '', _at(it['rect'], main)))
    inside.append(x('PopupRegion', ' name="Controls" group="Sources"', '', _at(region, main)))
    # No date and time: in the template's own boxes the 525 refused both,
    # its type wider than they are (round four; The working page).
    # The left rail: one Group of the template's kit buttons under one
    # heading, in cells 80 deep and 18 apart. Loose, each button only scales
    # and grows about its centre: on the 725 they ran into each other and
    # their headings; an icon `list` button's caption, indented past its
    # icon, needs 177 px there at 16 pt - more than the rail - and its cell
    # keeps its shape as it grows. The 525 shows the Group a cell at a time
    # with its arrows, the 320 as a button that opens its pages.
    words = {'display-power': ('Power', 'toggle', 'states="Off, On" does="Turns the display on and off."'),
             'display-mute': ('Mute', 'toggle', 'states="Off, On" does="Mutes the display; On while muted."')}
    groups = (F.get('left') or {}).get('groups') or ()
    rows = []
    for gi, g in enumerate(groups):
        if gi == 0:
            rows += [(bt['name'],) + words.get(bt['role'], (bt['name'], 'toggle', 'states="Off, On"'))
                     for bt in g.get('buttons') or ()]
        elif gi == 1:
            # The launchers in the kit's own list glyphs: Lighting's is lights.
            glyph = {lw: {'Lighting': 'lights'}.get(lw, lw.lower()) for lw in launchers}
            rows += [(f'{lw} Settings', lw, 'list', f'nav="{lw} Settings"'
                      + (f' icon="{glyph[lw]}"' if glyph[lw] in lists else '')) for lw in launchers]
    cell_h, gap = RAIL_CELL
    hd = (groups[1] if len(groups) > 1 else groups[0])['heading'] if groups else {'text': 'Settings', 'rect': [14, 160, 152, 50]}
    top = (groups[0].get('buttons') or [{}])[0].get('rect') if groups else [0, 208, 178, 50]
    left = [x('Label', f' name="{hd["text"]} Heading"', hd['text'],
              _at([hd['rect'][0], top[1] - hd['rect'][3], hd['rect'][2], hd['rect'][3]])),
            x('Group', f' title="{hd["text"]}" cell="{top[2]}x{cell_h}" gap="{gap}" cap="1"', ''.join(
                '\n    ' + x('Button', f' name="{name}" variant="{variant}" {attrs}', cap)
                for name, cap, variant, attrs in rows) + '\n  ', _at([top[0], top[1], top[2], RAIL_BOX]))]
    mute_icon = next((n for n in ('speaker-volume_3', 'speaker-mute-1') if n in icons), None)
    # No Volume heading: a hub's rail holds the volume and three buttons.
    rail = [x('Slider', ' name="Volume" does="Sets the program volume."'),
            x('Button', ' name="Mute" variant="icon"' + (f' icon="{mute_icon}"' if mute_icon else '')
              + ' states="Off, On" does="Mutes the program audio; On while muted."'),
            x('Button', ' name="Help" variant="icon" icon="help" nav="Help"'),
            x('Button', ' name="Power" variant="icon" icon="power" nav="Power Down"')]
    page = ('<!-- The working page, reached from Start. Draw Preview and the mode button only where the room has '
            'them. -->\n'
            + x('Page', f' name="Main SD"{room}', '\n  ' + '\n  '.join(
                left + [x('MainArea', '', '\n    ' + '\n    '.join(inside) + '\n  '),
                        x('Rail', '', '\n    ' + '\n    '.join(rail) + '\n  ')]) + '\n'))
    # A source's popup: its title and, with no controls, the empty state, as
    # the frame stands them in the region.
    t_rect = list(c.get('title') or [region[0], region[1], region[2], 50])
    e_rect = c.get('empty') or [region[0], region[1] + 73, region[2], 128]
    # The title twice the template's width about its middle: the 525 sets it
    # at 18 pt in a box scaled to 0.64, and 'Streaming' ran out of its 103 px.
    t_rect = [t_rect[0] - t_rect[2] // 2, t_rect[1], 2 * t_rect[2], t_rect[3]]

    def popup(name, body):
        return x('Page', f' name="{name}" kind="popup" group="Sources" width="{region[2]}" height="{region[3]}"{room}',
                 '\n  ' + '\n  '.join(
            [x('Label', f' name="{name} Title" type="subheading" align="center"', name, _at(t_rect, region))]
            + body) + '\n')

    def empty(name):
        return [x('Label', f' name="{name} Empty" align="center"',
                  ' '.join((w.get('empty') or '').split()).format(name=name, noun=_noun(name)), _at(e_rect, region))]
    zoom = [x('Label', ' name="Zoom Label" type="body-strong" color="text-secondary" align="center"', 'ZOOM',
              _at([279, 73, 120, 50])),
            # A set, so a Group: its cells where the template stands its keys,
            # as deep and as far apart as the 525 needs them in a popup, where
            # a Group cannot page.
            x('Group', f' title="Zoom" cell="154x{SET_CELL[0]}" gap="{SET_CELL[1]}" cap="1"', ''.join(
                '\n    ' + x('Button', f' name="Zoom {n}" variant="ghost" does="Zooms the document camera {d}."', c)
                for n, d, c in (('Tele', 'in', '+'), ('Wide', 'out', '-'))) + '\n  ',
              _at([262, 135, 154, 2 * SET_CELL[0] + SET_CELL[1] + 5]))]
    # The windows: a Panel card where the squircle stands, the frame's words
    # and buttons on it.
    wins = F.get('windows') or {}
    card = x('Panel', ' name="Card"', '', _at(main))

    def modal(name, body, extra=''):
        return x('Page', f' name="{name}" kind="modal"{extra}{room}', '\n  ' + '\n  '.join([card] + body) + '\n')

    def titled(win, text):
        out = []
        if win.get('title'):
            out.append(x('Label', f' name="{text} Title" type="subheading" align="center"', text, _at(win['title'])))
        if win.get('close'):
            out.append(x('Button', f' name="Close {text}" nav="Main SD"', b.get('close', 'Close'),
                         _at(win['close']['rect'])))
        return out
    hw, cw, ww = wins.get('help') or {}, wins.get('confirm') or {}, wins.get('wait') or {}
    sw = _settings_for(F, f'{launchers[0]} Settings')

    def said(s):
        return ' '.join((s or '').split())
    help_ = titled(hw, w.get('help_title') or 'Help') + (
        [x('Label', ' name="Help Message" align="center"', said(w.get('help')), _at(hw['message']))]
        if hw.get('message') else [])
    # The question and the wait two lines deep, and the answers as wide and
    # as far apart as the 525 needs them: it sets them at 18 pt in a window
    # scaled to 0.6, where the template's one line ran onto two and its 154
    # px answers grew into each other.
    def deeper(r, by=60):
        return [r[0], r[1] - by // 2, r[2], r[3] + by]
    q = [x('Label', ' name="Power Down Question" type="subheading" align="center"',
           said((w.get('confirm') or {}).get('power')), _at(deeper(cw.get('message') or [290, 223, 700, 50])))]
    answers = sorted(cw.get('buttons') or (), key=lambda r: r['rect'][0])
    for i, bt in enumerate(answers):
        r = bt['rect']
        mid = (answers[0]['rect'][0] + answers[-1]['rect'][0] + answers[-1]['rect'][2]) // 2
        r = [mid - 290 + i * 300, r[1] + 5, 260, SET_CELL[0]]
        if bt['role'] == 'power':
            q.append(x('Button', ' name="Power Down" does="Powers the room down; the program shows Powering Down."',
                       b.get('power', 'Power Down'), _at(r)))
        elif bt['role'] == 'cancel':
            q.append(x('Button', ' name="Cancel" nav="Main SD"', b.get('cancel', 'Cancel'), _at(r)))
    wait = [x('Label', ' name="Powering Down Message" type="subheading" align="center"',
              said((w.get('wait') or {}).get('down')), _at(deeper(ww.get('message') or [290, 375, 700, 50])))]
    lw0 = launchers[0]
    st = sw.get('title') or [485, 36, 310, 50]
    lights = (titled(sw, f'{lw0} Settings')
              + [x('Label', f' name="{lw0} Label" type="body-strong" color="text-secondary" align="center"',
                   'LIGHTS' if lw0 == 'Lighting' else lw0.upper(), _at([379, st[1] + st[3] + 54, 152, 50]))]
              + [x('Group', f' title="Presets" cell="178x{SET_CELL[0]}" gap="{SET_CELL[1]}" cap="1"', ''.join(
                  '\n    ' + x('Button', f' name="{lw0} {n}" does="Recalls the {n.lower()} {lw0.lower()} preset."', n)
                  for n in ('Full', 'Meeting', 'Off')) + '\n  ',
                  _at([365, st[1] + st[3] + 116, 178, 3 * SET_CELL[0] + 2 * SET_CELL[1] + 10]))])
    out = [('Main', _start_example(p)), ('Main SD', page),
           ('PC', '<!-- A source the room only routes: its title and the template\'s empty state. -->\n'
            + popup('PC', empty('PC'))),
           ('Laptop', popup('Laptop', empty('Laptop'))),
           ('Doc Cam', '<!-- A source with controls: a capitals label over its keys, as the template heads them. -->\n'
            + popup('Doc Cam', zoom)),
           ('Streaming', popup('Streaming', empty('Streaming')))]
    for lw in launchers:
        out.append((f'{lw} Settings', modal(f'{lw} Settings', lights if lw == lw0 else titled(sw, f'{lw} Settings'))))
    out += [('Help', modal('Help', help_)),
            ('Power Down', modal('Power Down', q, ' does="Asks before the room powers down."')),
            ('Powering Down', modal('Powering Down', wait, ' reached-by="program"'))]
    return out


# -- the center ---------------------------------------------------------------
def _center_md(p):
    """`## The center`: how a source shows its controls - a popup by role in
    the Center's group - its empty state in the template's words, naming its
    source, and what a hub and the 320 make of it."""
    t = p['template']
    w = p.get('writing') or {}

    def empty(name):
        return ' '.join((w.get('empty') or '').split()).format(name=name, noun=_noun(name))
    if not _regions(p):
        return (f"## The center\n\n"
                f"**How a source shows its controls.** Each source is a standard popup of its own - `kind=\"popup\"` "
                f"with the `PopupRegion`'s `group` (`Sources` in the example) - opened by its source button's `nav`. "
                f"{t}'s system draws none of a popup's chrome, so you write it: the source's name as a centred "
                f"`subheading` Label at its top, where the Layout's popup title stands, and its controls under it. A "
                f"source with no controls says the template's empty state under its title, and you write that too, "
                f"naming the source: '{empty('PC')}' On a hub and the 320 this system lays the popup out for the "
                f"panel (Every panel the room has).\n\n")
    look = ((p.get('regions') or {}).get('source') or {}).get('button') or {}
    status = (f", over its status - a Label named `<title> Status` that the program sets, `{w['status']}` as "
              f"drawn" if w.get('status') else '')
    page_empty = ' / '.join(x.strip() for x in (w.get('page_empty') or '').format(name='Laptop', noun='laptop')
                            .split('\n') if x.strip())
    hub_empty = ' '.join((w.get('hub_empty') or '').split()).format(name='Laptop', noun='laptop')
    return (f"## The center\n\n"
            f"**How a source shows its controls.** On {t}'s working page one source's controls are a popup in the "
            f"Center (`role=\"source\"`), swapped in by its Header tab while the page stays. Draw each source as a "
            f"Page with `kind=\"popup\"`, the Center's `group` (`Sources` by default) and `role=\"source\"`, its "
            f"`title` the source's name in the template's words - the 1035 titles a Doc Cam tab's popup `Document "
            f"Camera`, as the example does; the 320's own Doc Cam page is titled Doc Cam, and this system titles the "
            f"320's page with the same `title` - and the tab's `nav` names it. On every panel it is that panel's own "
            f"popup region, and draws {t}'s own chrome for it - {_source_chrome(p)}.\n\n"
            f"- **With controls**: put them in it where you want them, clear of its title - one under it is named. "
            f"They are laid out in the well on every panel, in {t}'s in-well look"
            + (f" (`{look['variant']}`)" if look.get('variant') else '') + " unless you give them one.\n"
            f"- **With none**: leave it empty, and it says {t}'s empty state, naming its source - '{empty('Laptop')}' "
            f"for Laptop, '{empty('PC')}' for a PC{status}. A source the room only routes needs nothing more.\n"
            + (f"- **Its picture**: {t} pins a picture of the source's device in its popup, and the Center draws "
               f"it.{_device_words(p)}\n" if _device_pictures(p) else '')
            + f"- **On a hub** it fills main under the hub's own title, with a Close back to Select a Source"
            + (", on the page's photo stretched to it" if _hub_photo(p) else '')
            + (", its device picture under the title" if _device_pictures(p) else '')
            + (f"; with none it says '{hub_empty}'\n" if hub_empty else '.\n')
            + f"- **On a 320** it is a page of its own under the strip, titled with it: what you put in it in "
            f"columns, two to a page, the rest on a second page by More and Back"
            + (f"; with none, the 320's three-line empty state ('{page_empty}')" if page_empty else '') + ".\n"
            f"- **Without `role`** a popup in the Center's group scales with main, and is named where it comes out "
            f"larger than the region: give a source its role.\n\n")


# -- the windows ----------------------------------------------------------------
def _window_look(p):
    """What the design panel's windows look like, off its frame: each
    settings frame and the titles it is drawn for (as bundle.js windowOf()
    picks one), and the question's card with its answers in order and the
    looks the regions give them."""
    F = _design_frame(p)
    wins = F.get('windows') or {}
    b = (p.get('writing') or {}).get('buttons') or {}

    def fill(w):
        # Its alpha where the template's fill has one (Mach's #000000B4).
        f = next((s['fill'] for s in w.get('surfaces') or () if s.get('fill')), None)
        return f[:7] if f and f[7:].upper() in ('', 'FF') else f

    def shape(w):
        f, r = fill(w), w.get('rect')
        if f and r and r[2] >= p['size'][0]:
            return f"a {f} band {r[2]}x{r[3]} at {r[0]},{r[1]}, across the page between its bars"
        return f"a {f} card {r[2]}x{r[3]} at {r[0]},{r[1]}" if f and r else 'its words on the scrim alone'
    said = []
    setts = wins.get('settings') or []
    if setts:
        # windowOf: a title whose first word begins a template window's name
        # takes that window's frame; any other the plain frame with the most.
        plain = [r for r in setts if r.get('title') and r.get('close') and r.get('surfaces')
                 and all(s.get('kind') == 'shape' for s in r['surfaces'])] or setts
        default = max(plain, key=lambda r: len(r.get('popups') or ()))
        rects = {}
        for r in setts:
            rects.setdefault(tuple(r.get('rect') or ()), []).append(r)
        if len(rects) > 1:
            frames = [f"{k[2]}x{k[3]} at {k[0]},{k[1]} for {_say([q for r in rs for q in r.get('popups') or ()])}"
                      + (" and any title it does not name" if default in rs else '')
                      for k, rs in rects.items()]
            s = (f"a settings window is a {fill(default)} card " + ', or '.join(frames)
                 + " - the frame of the template's window whose name begins as its `title` does")
        else:
            s = f"a settings window is {shape(default)}"
            odd = [q for r in setts if any(x.get('art') for x in r.get('surfaces') or ()) for q in r.get('popups') or ()]
            photo = next((r for r in setts if any(x.get('art') for x in r.get('surfaces') or ())), None)
            if odd and photo:
                s += f" ({_say(odd)} draw the photo under a {fill(photo)} band instead)"
        s += ", its title across its top and a Close at its top right" if default.get('title') and default.get(
            'close') else ''
        said.append(s)
    conf = wins.get('confirm') or {}
    if conf:
        btns = sorted(conf.get('buttons') or (), key=lambda r: r['rect'][0])
        words = {'power': b.get('power', 'Power Down'), 'cancel': b.get('cancel', 'Cancel')}
        win = (p.get('regions') or {}).get('window') or {}

        def look(role):
            v = win.get(role) or {}
            if not v.get('variant'):
                return ''
            rest = next((s.get('look') for s in v.get('states') or () if s.get('name') == 'Off' and s.get('look')),
                        None)
            return (f"`{v['variant']}`" + (f" with icon `{v['icon']}`" if v.get('icon') else '')
                    + (f", resting `{rest}`" if rest else ''))
        q = f"the question is {shape(conf)}"
        if len(btns) == 2:
            a, z = (words.get(x['role'], x['name']) for x in btns)
            q += f", its two answers side by side under it, {a} at the left and {z} at the right"
            looks = [f"{words[r]} {look(r)}" for r in ('power', 'cancel') if look(r)]
            if looks:
                q += f" ({'; '.join(looks)})"
        said.append(q)
    return (f"On the {p['model']}, over the page under the scrim, " + '; '.join(said)
            + ". The Layout gives every window's rects.")


def _windows_md(p, renders=()):
    """`## Windows`: settings, Help, the question and the waits by `role`, as
    the template draws them, beside the template's own question and a
    settings window; the modal without one; the Close."""
    t = p['template']
    w = p.get('writing') or {}
    b = w.get('buttons') or {}
    close = ("with a Close: `nav` back to the page that opens it, or, where more than one page opens it, no `nav` "
             "and `does=\"Closes this popup.\"` - the program hides it and the page beneath shows again.")
    rule = "Whether an action asks for confirmation at all is the designer's choice, not a rule."
    shown = _render_md(p, renders, 'bar', 'confirm') + _render_md(p, renders, 'bar', 'settings')
    if not _regions(p):
        own = (p.get('layout') or {}).get('popups') or ''
        m = (p.get('layout') or {}).get('main') or [0, 0, p['size'][0], p['size'][1]]
        return (f"## Windows\n\n"
                f"Help, the power-down question, the waits and a set of settings opened from a page are modal "
                f"popups: a Page with `kind=\"modal\"`, which shows the page beneath under a scrim. {t}'s system "
                f"draws no window of its own, so you draw each: a `Panel` card where the squircle stands, "
                f"{m[2]}x{m[3]} at {m[0]},{m[1]} in the Panel's default look, with the window's words and buttons on "
                f"it where the Layout's windows stand them - as the example's Help, Power Down, Powering Down and "
                f"settings windows do.\n\n"
                + shown
                + f"- {own}\n"
                f"- **Its words** are the template's (Writing): Help's '{' '.join((w.get('help') or '').split())}', "
                f"the question's '{' '.join(((w.get('confirm') or {}).get('power') or '').split())}' with "
                f"{b.get('power', 'Power Down')} and {b.get('cancel', 'Cancel')}.\n"
                f"- {rule}\n\n")
    q = ' '.join(((w.get('confirm') or {}).get('power') or '').split())
    up, down = (' '.join(((w.get('wait') or {}).get(k) or '').split()) for k in ('up', 'down'))
    helped = w.get('help_title') or 'Help'
    return (f"## Windows\n\n"
            f"Help, the power-down question, the waits and a set of settings opened from a page are windows "
            f"(`kind=\"modal\"` with a `role`), each drawn from the frame's windows (Layout) - the window, its "
            f"title, its Close or its answers - with no card of yours.\n\n"
            + shown
            + f"- **What a window looks like.** {_window_look(p)}\n"
            f"- `role=\"settings\"` (or a `title` and no role): the window with its `title` and a Close. Put its "
            f"own controls inside it, in the window's look{_window_image(p)}.\n"
            f"- `role=\"help\"`: titled '{helped}' unless you give a `title`, and with nothing put in it {t}'s own "
            f"message - '{' '.join((w.get('help') or '').split())}'. Your own words replace it: one Label of a "
            f"few short sentences, clear of the title, with the room Every panel the room has gives words - on "
            f"the 320 they are set across the page under its strip, going on over a second page by More and "
            f"Back, and a Label too long for a page of its own is refused.\n"
            f"- `role=\"confirm\"` with `topic=\"power\"`: asks '{q}' with {b.get('power', 'Power Down')} - its "
            f"`does` is the Page's - and {b.get('cancel', 'Cancel')}.\n"
            f"- `role=\"wait\"` with `topic=\"up\"` or `\"down\"`: '{up}' or '{down}', with no buttons; the "
            f"program shows it (`reached-by=\"program\"`).\n"
            f"- A window's Close and Cancel go back to the page that opened it - the program's to do, so they carry "
            f"no `nav`.\n"
            f"- On a hub the settings are popups filling main, each with its title and a Close back to Select a "
            f"Source{', on the page' + chr(39) + 's photo' if _hub_photo(p) else ''}; Help, the question and the wait stay windows in the hub's style. On a 320 each is a page "
            f"(the Page README).\n"
            f"- **A modal without a `role`** is yours to draw: put its card inside as a `Panel` and its buttons on "
            f"the card, {close} A modal the program hides, or whose own answers close it, needs no Close.\n"
            f"- A page flip is for a mode of the room, such as a call. {rule}\n\n")


# -- the template's words ---------------------------------------------------------
def _writing_md(p):
    """`## Writing`: the template's own words (`writing`) and how it words a
    caption (`writing.voice`), which the caption lint holds this system to -
    on a button, as the lint does: a window's title keeps its own rule."""
    t = p['template']
    w = p.get('writing') or {}
    if not w:
        return ''
    voice = w.get('voice') or {}
    b = w.get('buttons') or {}

    def said(s):
        return ' '.join((s or '').split())
    lines = []
    if w.get('empty'):
        lines.append(f"- A source with no controls: '{said(w['empty']).format(name='Laptop', noun='laptop')}'"
                     + (f" over '{w['status']}'" if w.get('status') else '')
                     + (f"; on a hub '{said(w['hub_empty']).format(name='Laptop', noun='laptop')}'"
                        if w.get('hub_empty') else ''))
    if (w.get('confirm') or {}).get('power'):
        lines.append(f"- The power-down question: '{said(w['confirm']['power'])}' - {b.get('power', 'Power Down')} "
                     f"and {b.get('cancel', 'Cancel')}")
    if w.get('wait'):
        lines.append(f"- The waits: '{said(w['wait'].get('up'))}' and '{said(w['wait'].get('down'))}'")
    if w.get('help'):
        lines.append(f"- Help, titled '{w.get('help_title') or 'Help'}': '{said(w['help'])}'")
    if b.get('close'):
        lines.append(f"- A window's Close: '{b['close']}'")
    instead = voice.get('instead') or {}
    caps = voice.get('caps') or []
    rules = [f"- {r}" for r in voice.get('rules') or ()]
    by_theirs = {}
    for ours, theirs in instead.items():
        by_theirs.setdefault(theirs, []).append(ours)
    if instead:
        rules.append(f"- On a button, say what {t} says: "
                     + '; '.join(f"{theirs}, not {_say(ours).replace(' and ', ' or ')}"
                                 for theirs, ours in by_theirs.items())
                     + ". A window's title is not a button: it keeps the words its own rule above gives it.")
    rules.append("- Never a generic verb - Submit, OK, Yes, Done: name the action on the button, as the question's "
                 "answers do.")
    rules.append("- Captions and titles are Title Case" + (f", in capitals only where {t} sets them so ("
                                                          f"{', '.join(caps)})" if caps else '') + ".")
    preface = (f"{t}'s own words. Its system draws no empty state or window of its own, so you write these, in "
               f"its words, on the artboards you draw (The center, Windows)."
               if not _regions(p) else
               f"{t}'s own words. The Center and the windows say them for you; where you write your own, say them "
               f"as {t} does.")
    return (f"## Writing\n\n{preface}\n\n" + '\n'.join(lines) + "\n\nIn its voice:\n\n" + '\n'.join(rules) + '\n\n')


# -- before you hand it over --------------------------------------------------------
def _handover_md(p):
    """`## Before you hand it over`: what the designer checks, then what
    Claude Code checks once it has the canvas - translate and the critique
    loop, which only it can run."""
    t = p['template']
    regions = _regions(p)
    return (f"## Before you hand it over\n\n"
            f"Claude Code builds what the canvas says, on every panel it lists. Before you hand it over, check:\n\n"
            f"- [ ] **Every panel** the room has is in `panels` on every Page, the one drawn on first; `preview` "
            f"each, and nothing is outlined.\n"
            f"- [ ] **Every control says what it does**: a `nav` to an artboard that exists, or a `does`; every "
            f"state looks different; every page is reached by `nav` from the start page or is "
            f"`reached-by=\"program\"`.\n"
            f"- [ ] **IDs**: a control on several pages shares an `id` only where every copy does the same thing"
            + ("; the regions' Help, Power, Volume and Mute keep the template's own IDs, so give them none of yours"
               if regions else '') + ".\n"
            f"- [ ] **Words** in {t}'s voice (Writing): Title Case captions that name the thing, and the "
            f"template's own words for the empty state, the question and the waits.\n\n"
            f"**Claude Code checks after the handover:**\n\n"
            f"- [ ] **Translate clean**: `python -m gdl.design translate` names no problem on any panel - nothing "
            f"refused, nothing painted outside a component - and its notes"
            + (" (a region a working page lacks)" if regions else '') + " are read.\n"
            f"- [ ] **The critique loop**: `python -m gdl.design compare <canvas> --template` sets each artboard, as "
            f"each panel draws it, beside {t}'s own page of that kind - the working page beside the template's "
            f"working page, a source beside its source popup, a window beside its window. Region by region, what "
            f"differs from the template and is not in Differences comes back to the canvas as a fix, and the "
            f"canvas is translated and compared again.\n\n")


# -- pages without regions -----------------------------------------------------------
def _free_pages_md(p):
    """`## Pages without regions`: when a page is free of the grammar, and how
    to draw one."""
    if not _regions(p):
        return ''
    ns, t = p['namespace'], p['template']
    start = (p.get('layout') or {}).get('start')
    return (f"## Pages without regions\n\n"
            f"A Page holding no region is a free page: laid out as you draw it - `{ns}.MainArea`, a `Rail`, a "
            f"`Group`, a `PopupRegion` and loose controls - and carried to the room's other panels by scale, a hub's "
            f"main or the 320's rows (Every panel the room has), not redrawn in their grammar. It draws no chrome of "
            f"its own: no tabs, rails, clock, Help or Power unless you place them, and what you place keeps no "
            f"template ID. Use one where {t}'s own pages stand outside the grammar:\n\n"
            + (f"- **Start.** {start} Mark it `splash=\"true\"` and `start=\"true\"`, and give it what leads on to "
               f"the working page.\n" if start else '')
            + f"- **A mode chooser**, such as Room Mode: a splash page too, its choices leading to the working page "
              f"of each mode.\n"
              f"- **A page the grammar has no region for**: draw it free, in the tokens and looks of the working "
              f"page.\n\n"
              f"Say `splash=\"true\"` on every page that is not a working page, or it is named for the regions it "
              f"lacks. A source's controls and a window are never free pages: they are popups by `role` (The "
              f"center, Windows).\n\n")


# -- where we differ ---------------------------------------------------------------
def _differences_md(p):
    """`## Differences`: where this system deviates from the template and why,
    written from the ledger's `deviation` entries (`here`), so it cannot
    drift from them."""
    from .audit import load_ledger
    t = p['template']
    devs = [e for e in (load_ledger(t.lower()) or {}).get('entries') or () if e.get('status') == 'deviation'
            and e.get('here')]
    if not devs:
        return ''
    return (f"## Differences\n\n"
            f"Where this system draws otherwise than {t}'s own pages, on purpose - each a gate the panel must pass "
            f"or something the system cannot draw. Everything else follows the template:\n\n"
            + '\n'.join(f"- {e['here']}" for e in devs) + '\n\n')


def _rect(r):
    """[x, y, w, h] -> 'WxH at X,Y', or '-' where the template draws none."""
    return f'{r[2]}x{r[3]} at {r[0]},{r[1]}' if r else '-'


def _band(b):
    return _rect(b['rect']) if isinstance(b, dict) and b.get('rect') else '-'


_BANDS = (('top', 'Header'), ('left', 'LeftRail'), ('right', 'RightRail'), ('bottom', 'Footer'),
          ('center', 'Center'))


def _set_words(items, pitch=None):
    """A set the template steps: 'A, B and C 103x60 from 17,186, one every
    61 px (1 px apart)'."""
    names = [f"`{i['name']}`" for i in items]
    r = items[0]['rect']
    said = (', '.join(names[:-1]) + ' and ' + names[-1] if len(names) > 1 else names[0])
    said += f" {r[2]}x{r[3]} from {r[0]},{r[1]}"
    if len(items) > 1:
        a, b = items[0]['rect'], items[1]['rect']
        across = abs(b[0] - a[0]) >= abs(b[1] - a[1])
        step = pitch or (abs(b[0] - a[0]) if across else abs(b[1] - a[1]))
        said += f", one every {step} px ({step - (a[2] if across else a[3])} px apart)"
    return said


def _item_words(i):
    text = f" '{i['text']}'" if i.get('text') else ''
    return f"`{i['name']}`{text} {_rect(i['rect'])}"


def _surface_words(band):
    s = [x for x in band.get('surfaces') or () if x.get('rect')]
    if not s:
        return ''
    return '; drawn on ' + ', '.join(
        f"`{x['name']}` {_rect(x['rect'])}" + (f" ({x['fill']})" if x.get('fill') else
                                              f" (`{x['art']}`)" if x.get('art') else '')
        for x in s)


def _frame_band_words(key, band):
    """One band of a frame, as its template draws it: every set, item and
    surface with its rect."""
    parts = []
    tabs = band.get('tabs')
    if tabs and tabs.get('items'):
        parts.append(f"{tabs.get('count') or len(tabs['items'])} source tabs: "
                     + _set_words(tabs['items'], tabs.get('pitch')))
    for g in band.get('groups') or ():
        h = g.get('heading') or {}
        words = f"'{h['text']}' heading {_rect(h['rect'])}, then " if h.get('rect') else ''
        if g.get('buttons'):
            parts.append(words + _set_words(g['buttons'], g.get('pitch')))
    for end in ('start', 'end'):
        drawn = [i for i in band.get(end) or () if i.get('role') != 'surface' and i.get('rect')]
        if drawn:
            parts.append(f"at its {end} " + ', '.join(_item_words(i) for i in drawn))
    items = [i for i in band.get('items') or () if i.get('rect')]
    if items:
        parts.append(', '.join(_item_words(i) for i in items))
    if key == 'center':
        for k, words in (('region', 'the popup region the sources fill'), ('well', "a source's well"),
                         ('title', "its title"), ('empty', 'the empty state')):
            if band.get(k):
                parts.append(f"{words} {_rect(band[k])}" + (f" (off `{band['popup']}`)"
                                                             if k == 'well' and band.get('popup') else ''))
        # Turbulence sizes each device's picture its own way: the Laptop
        # Image the surfaces name is one of them.
        if band.get('pictures'):
            parts.append("each source's device picture, by `device`: "
                         + ', '.join(f"`{d}` {_rect(r)}" for d, r in band['pictures'].items()))
    return '; '.join(parts) + _surface_words(band)


def _frame_window_words(name, w):
    if not isinstance(w, dict):
        return ''
    parts = [f"{_rect(w.get('rect'))} (off `{w['popup']}`)" if w.get('popup') else _rect(w.get('rect'))]
    if w.get('title'):
        parts.append(f"its title {_rect(w['title'])}")
    if w.get('close'):
        parts.append(f"Close {_rect(w['close']['rect'])}")
    if w.get('message'):
        parts.append(f"its message {_rect(w['message'])}")
    for b in w.get('buttons') or ():
        parts.append(_item_words(b))
    return f"{name} " + ', '.join(parts) + _surface_words(w)


def frame_layout(p):
    """The README's Layout as the frame measures it: each series' bands and
    the design panel's regions, sets and rects, written from
    `panels[series].frame` so it cannot drift from what the region
    components draw. '' for a profile with no frame. The claim lint
    (gdl/designsys/audit.py) takes every number here as a frame value."""
    rows, design = [], None
    for name, s in (p.get('panels') or {}).items():
        f = s.get('frame') if isinstance(s, dict) and not name.startswith('_') else None
        if not f:
            continue
        if p['model'] in (s.get('models') or ()):
            design = (name, f)
        region = (f.get('center') or {}).get('region') if isinstance(f.get('center'), dict) else None
        rows.append(f"| {name[len(p['template']):].strip().removesuffix(' Series')} | "
                    f"{s['size'][0]}x{s['size'][1]} | {f.get('page') or '-'} | "
                    + ' | '.join(_band(f.get(k)) for k, _ in _BANDS) + f" | {_rect(region)} |")
    if not rows:
        return ''
    regions = _regions(p)
    t = p['template']
    out = (f"{t}'s working page, measured off each series' own seed (`panels[series].frame`): the band each "
           + ("region component draws in" if regions else "part of the page stands in")
           + f", in px on that series' own screen, and `-` where its template draws none.\n\n"
           f"| Series | Screen | Page | " + ' | '.join(w for _, w in _BANDS) + " | Popup region |\n"
           f"|---|---|---|---|---|---|---|---|---|\n" + '\n'.join(rows) + '\n')
    if design:
        name, f = design
        lines = [f"- **{w}** {_rect(f[k]['rect'])}: {_frame_band_words(k, f[k]) or 'nothing of its own'}."
                 for k, w in _BANDS if isinstance(f.get(k), dict)]
        wins = f.get('windows') or {}
        said = [_frame_window_words(k, wins.get(k)) for k in ('help', 'confirm', 'wait')]
        for w in wins.get('settings') or ():
            said.append(_frame_window_words('settings', dict(w, popup=', '.join(w.get('popups') or ()))))
        said = [x for x in said if x]
        if said:
            lines.append(f"- **Windows**: " + '; '.join(said) + '.')
        out += (f"\nOn the {p['model']} ({name}), off its `{f.get('page')}`:\n\n" + '\n'.join(lines) + '\n')
        if f.get('note'):
            out += f"\n{f['note']}\n"
    return out


def _kind_words(p):
    """The Page README's `popup` and `modal`. Every system called a popup 'a
    card' and told a modal to hold its card as a Panel; where the template
    has a region frame its standard popup is transparent - a source's draws
    the template's well in it - and its windows are drawn by `role`."""
    size = f"{p['popup'][0]}x{p['popup'][1]} unless `width` and `height` say otherwise"
    if not _regions(p):
        # Afterburn's popup is an alpha-0 image over the squircle, and its modal's card is the squircle art
        # itself, a full-canvas image the Page cannot place (the truth ledger, afterburn-11).
        return (f"`popup` (a standard popup, {size}: it draws nothing of its own, its controls sit on the "
                f"squircle) or `modal` (a full-screen popup over a `scrim`; put its card inside as a Panel - "
                f"{p['template']}'s own card is its squircle art, which a Page cannot place)")
    return (f"`popup` (a standard popup, {size}: it draws nothing of its own, and a source's, `role=\"source\"`, "
            f"draws the template's well in it) or `modal` (a full-screen popup over a `scrim`: with a `role`, one of "
            f"the template's windows, drawn from its frame; without one, put its card inside as a Panel)")


def index(p, at, existing=None):
    """design-system.json. A revision keeps every key the page wrote."""
    out = dict(existing or {})
    out.update({
        'v': 3, 'layout': 'files', 'title': p['title'], 'namespace': p['namespace'],
        'libraries': [{'name': 'react', 'version': '18'}, {'name': 'react-dom', 'version': '18'}],
        'lastChange': {'by': 'Claude', 'at': at, 'via': 'Claude Code (gdl.designsys)',
                       'note': f"The {p['template']} template, from its profile"},
    })
    if not existing:
        out.update({'createdOnFiles': {'v': 1, 'at': at}, 'sections': {}, 'groups': [],
                    'assetGroups': {}, 'blobs': {}, 'docs': {'readme': 'project/README.md',
                                                              'sections': []}})
    return out


def build(template, out, at, existing=None):
    """Write the system's project/ tree under `out`. Returns the paths written."""
    p = load(template)
    # The template's own working pages, rendered off its seeds: Extron's
    # artwork, so in the private design system only (the owner's call 3).
    plan = template_renders(p)
    images = render_templates(p, plan)
    files = {
        'tokens.json': json.dumps(tokens(p), indent=2),
        'README.md': readme(p, renders=[r for r in plan if r['file'] in images]),
        'components/bundle.js': bundle(p),
        'components/bundle.css': BUNDLE_CSS,
        'components/index.d.ts': index_dts(p),
        'components/Cover/preview.html': cover(p),
    }
    for name, text in component_docs(p).items():
        files[f'components/{name}/README.md'] = text
    for name, text in previews(p).items():
        files[f'components/{name}/preview.html'] = text
    if images:
        files['components/Template/preview.html'] = template_card(p, plan, images)
    files['design-system.json'] = json.dumps(index(p, at, existing), indent=2)
    written = []
    for rel, data in images.items():
        path = os.path.join(out, 'project', *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(data)
        written.append('project/' + rel)
    for rel, text in files.items():
        path = os.path.join(out, 'project', *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        written.append('project/' + rel)
    return written


def main(argv):
    if len(argv) >= 2 and argv[1] == 'audit':
        # Is what the system says about its template what the template does?
        # (gdl/designsys/audit.py, the ledger in gdl/designsys/truth/)
        from . import audit
        return audit.main(argv)
    if len(argv) == 3 and argv[1] == 'extract':
        # Images that live only inside Extron's files, written where the kit
        # code and a spec's `images` look: vendor/extron/Resources/<to>.
        from ..spec import RESOURCE_ROOTS
        p = load(argv[2])
        ex = (p.get('kit') or {}).get('extract')
        if not ex:
            print(f'{argv[2]} names nothing to extract (kit.extract)')
            return 2
        sources = extract_sources(p)
        if not sources:
            print(f"none of {ex['from']} is on this machine")
            return 1
        out = os.path.join(RESOURCE_ROOTS[0], *ex['to'].split('/'))
        written = extract_images(sources, out)
        print(f'{len(written)} new image(s) from {len(sources)} file(s) -> {out}')
        return 0
    if len(argv) < 4 or argv[1] != 'build' or argv[2] not in TEMPLATES:
        print(__doc__.strip().split('\n\n')[0])
        print(f"\n  python -m gdl.designsys build <{'|'.join(TEMPLATES)}> <out dir> "
              '[--at ISO-8601] [--index existing design-system.json]'
              '\n  python -m gdl.designsys extract <template>'
              '\n  python -m gdl.designsys audit <template>')
        return 2
    at = argv[argv.index('--at') + 1] if '--at' in argv else None
    if not at:
        import datetime
        at = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    existing = None
    if '--index' in argv:
        with open(argv[argv.index('--index') + 1], encoding='utf-8') as fh:
            existing = json.load(fh)
    written = build(argv[2], argv[3], at, existing)
    print(f'{len(written)} files -> {os.path.join(argv[3], "project")}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
