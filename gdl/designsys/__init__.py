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
            {'name': 'popup-width', 'value': f"{p['popup'][0]}px", 'usage': f"The {p['template']} template's popup card."},
            {'name': 'popup-height', 'value': f"{p['popup'][1]}px", 'usage': "The popup card's height."},
        ]},
    }


# -- the per-panel table -----------------------------------------------------------
def models(p):
    """{panel: row} - every panel the profile's series serve, for the bundle to
    derive each panel's layout from (docs/claude-design.md section 2). A panel
    is gdl.spec.panel_id: its model, or model-Portrait / model-Landscape where a
    series serves a panel that rotates the other way up (the 300M's two).

    A row is the series' own measurements (its `panels` entry: main region,
    rail band, popup region, background art and how it is drawn, the seed per
    model and what that seed can clone) with the model's own minimums from
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
                           seed=(s.get('seeds') or {}).get(pid))
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


def bundle(p, art=True):
    header = json.dumps({'format': 4, 'namespace': p['namespace'],
                         'components': [{'name': n} for n, _, _ in COMPONENTS]},
                        separators=(',', ':'))
    profile = {k: p[k] for k in ('template', 'namespace', 'model', 'size', 'popup', 'pt',
                                 'touch', 'font', 'schemes', 'colors', 'type', 'borders',
                                 'buttons', 'defaults')}
    profile['themes'] = themes(p)
    profile['layout'] = p.get('layout') or {}
    profile['spacing'] = p['spacing']
    # Every panel's own regions, minimums and art; empty for a profile with no
    # per-panel table. art=False (the translator's tests) leaves the images out:
    # the probe reads names, never pixels.
    profile['models'] = models(p)
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


def _ratio(size):
    """'1224x344' -> '3.6:1'."""
    w, h = (int(n) for n in size.split('x'))
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
            kind = 'rows'
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
        room = ('- | -' if kind == 'rows' else
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
            f"room to be as much taller. Keep copy short, and break help into short lines.\n"
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
               if (p.get('layout') or {}).get('bars') == 'controls' else '') + "\n"
            f"- **Rows**: the panel lays the page's controls out again, in rows.\n\n"
            f"Set a Page's `preview` to a panel to see an artboard as that panel draws it: a control that "
            f"collides with its neighbour, or a box its words overflow, is outlined.\n\n"
            f"| Panels | Screen | Kind | Scale | Touch, gap | Type floor | Here | Words |\n"
            f"|---|---|---|---|---|---|---|---|\n" + '\n'.join(lines) + '\n\n')


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
            "depth, and a button flush with a bar's end and the main area's edge fills that end. Draw bars "
            f"as the template does, edge to edge.{hub}{_small_pages(p)}\n")


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
            f"Previous and Next at its foot; a row never splits. Words wider than the screen break into "
            f"lines. A modal holds one screen there: say in it what fits one.")


def _panels_main(p):
    if not models(p):
        return ''
    return (" On a Page that lists `panels`, it is each panel's own main region, and what is in it is laid "
            "out for that panel: scaled as the region is on a large or mid-size screen, and on a small one "
            "(the 320's) reflowed into rows in the order you placed them"
            + (" - a bar theme's with the Page's, by region, and over pages of their own where they do not "
               "fit (Page)" if (p.get('layout') or {}).get('bars') == 'controls' else '')
            + ". Leave room: a caption grows to the "
            "panel's type floor, and a control that collides with its neighbour is refused, by name.")


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
    text = (" On a Page that lists `panels`, place no Rail yourself: it takes each panel's own rail, whatever "
            "position or size you give it - beside the main region")
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
    shapes = ', '.join(f"`{k}` {_ratio(size)}" for k, size, _, _ in _image_buttons(p))
    sl = p['defaults']['slider']
    if str(sl.get('thumb_image', '')).lower().endswith('.png'):
        thumb_words = (f"and the template's own thumb image, `thumb` px across (default {sl['thumb']})"
                       + (f" and {sl['thumb_height']} along the rail" if sl.get('thumb_height') else ''))
    else:
        thumb_words = (f"and a round thumb in `{sl['thumb_color']}` whose box is `thumb` px (default "
                       f"{sl['thumb']}) - the circle itself about two-thirds of that, with a shadow round "
                       f"it, as the panel draws it")
    return {
        'Page': f"""# Page

The root of every artboard: one Page per artboard, holding everything on it. It is one page or popup of the panel, drawn at the panel's size and in the {t} background.

Props:
- `name`: what the page or popup is called on the panel. The control program shows it by this name, so make it unique and plain: `Home`, `Help`, `Confirm Room Off`.
- `kind`: `page` (default, {p['size'][0]}x{p['size'][1]}), `popup` (a card, {p['popup'][0]}x{p['popup'][1]} unless `width` and `height` say otherwise) or `modal` (a full-screen popup over a `scrim`; put its card inside as a Panel).
- `group`: a popup's group. A standard popup appears where a page has a PopupRegion for its group.
- `start="true"`: the page the panel boots into. One page only; without it, the first artboard.
- `reached-by="program"`: the control program shows this page by itself - an incoming call - so no button has to lead to it.
- `theme`: {', '.join(f'`{th["id"]}`' for th in themes(p))} - {'the background image and accent scheme pairing, ' if p.get('themes') else ''}the same on every artboard. `scheme` swaps the accent scheme alone: {', '.join(f'`{s["id"]}`' for s in p['schemes'])}.
- `does`: what the page is for, in a sentence, for the programmer.
{_panels_props(p)}
Place controls inside it with absolute positions or with flex and grid containers: containers that paint nothing are fine. Anything that paints and is not one of these components is not built.

```html
{_x(p, 'Page', ' name="Home" start="true"', '...')}
```
""",
        'MainArea': f"""# MainArea

The {t} page's main region, as a layout container: {_main_words(p)} It paints nothing and is not a control - the page draws the region - so put the page's main task inside it, positioned relative to it or with flex and grid.{_panels_main(p)}

```html
{_x(p, 'MainArea', '', chr(10) + '  ' + _x(p, 'Label', f' name="Title" type="{sub}" align="center"', 'Select a Source', 'position: absolute; left: 0px; top: 190px; width: 100%; height: 60px') + chr(10))}
```
""",
        'Rail': f"""# Rail

The page's column of system controls - volume, mute, help, power - beside the main region, as {t}'s own pages put them on the right. Its children need no positions: they stack down it in order, each as big as it needs to be on the panel, and a Slider or Level takes the length the others leave. It paints nothing and is not a control. A Label or a Clock in it is one line deep and as wide as the rail (as long as its words, on a rail that runs across), so a heading such as Volume goes above the Slider it names.{_panels_rail(p)}

```html
{_x(p, 'Rail', '', chr(10) + '  ' + _x(p, 'Slider', ' name="Volume"') + chr(10) + '  ' + _example_button(p, 'help', 'HelpBtn') + chr(10))}
```
""",
        'Group': f"""# Group

A titled set of like controls - the sources, the presets, the cameras - laid out as a grid of equal cells in the Group's own box, `cap` to a row. Give the box room: it is where the group lives on every panel. Its children need no positions. The cells keep their size and `gap`, and spare room is not shared out among them: the grid sits centred in the box, across and down, and a last row of fewer cells is centred under the others. Where the group pages, its cells sit at the top of the box with Previous and Next under them - except in a box one cell deep, where the cells stay centred and Previous and Next (or arrows) stand at the row's ends. On a panel where the cells do not fit at the page's scale, the gap gives way first - down to the panel's own 2 mm - before the group pages.

Props:
- `title`: what the group is called. On a panel too small to show it in place, its pages and the button that opens them take this name.
- `cell`: the cell's size, `"110x110"` - its members' drawn size. Default: the first member's.
- `gap`: the space between cells, in px (default 49). `cap`: the most to a row (default 4). {p['examples']['group_note']}
- `joined="true"`: a segmented control - one row of segments that touch, never paged.{_panels_group(p)}

```html
{_x(p, 'Group', ' title="Sources" cell="110x110" gap="55"', chr(10) + '  ' + _example_button(p, 'source', 'Laptop') + chr(10), 'position: absolute; left: 0px; top: 210px; width: 916px; height: 250px')}
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
{_x(p, 'Panel', ' name="TopBar" fill="raised" border="rect"', '', 'width: 1280px; height: 112px')}
```
""",
        'Line': f"""# Line

A divider. `orientation` (`horizontal`, default, or `vertical`), `color` (default `{p['defaults']['line']['color']}`), `thickness` in px, `name`.

```html
{_x(p, 'Line', ' name="Divider"', '', 'width: 1200px; height: 2px')}
```
""",
        'Slider': f"""# Slider

A control the user drags: volume, a light level. Drawn as {t} builds it: a rounded rail `track` px wide (default {p['defaults']['slider']['track']}) down the middle of the control's box, the rail's filled part in `{p['defaults']['slider']['value']}`, {thumb_words}. The box is the touch area: make it at least as wide as the thumb. `orientation`: the direction the value grows, `{p['defaults']['slider']['orientation']}` by default as {t}'s own volume sliders are (`up`, `down`, `left`, `right`). `fill`: the rail's empty part, default `{p['defaults']['slider']['fill']}` - on a `raised` panel use `page`. `name`, and `does` - what it sets and whether it follows feedback. `value` (0-100) only draws the canvas. The filled part and the thumb come from the template's own slider, so they are not props.{_panels_slider(p)}

```html
{_x(p, 'Slider', ' name="Volume" does="Sets program volume; follows the DSP level."', '', f"width: {max(50, sl['thumb'], p['touch'])}px; height: 395px")}
```
""",
        'Level': f"""# Level

A meter the program drives: signal level, a countdown. A rail like Slider's with no thumb, filled in `{p['defaults']['level']['value']}`, and not touchable. `orientation` (default `{p['defaults']['level']['orientation']}`), `track`, `fill`, `name`, `does`.{_level_where(p)}

```html
{_x(p, 'Level', ' name="MicLevel" orientation="up" does="Shows the microphone level."', '', 'width: 40px; height: 240px')}
```
""",
        'Clock': f"""# Clock

The panel's own date or time, drawn by the panel with no program. `format`: `time` (default, `h:mm tt`, drawn `12:00 AM`), `date` (`MMMM d`, `September 28`), `datetime` (`MMMM d, h:mm tt`, `September 28, 12:00 AM`), or any .NET date pattern - the pattern the panel formats its clock with, drawn here for 28 September 1960 at midnight as GUI Designer draws it; the panel shows the real time; `align` (`left`, `center`, `right`); `type`, `size`, `color` (default `{p['defaults']['clock']['color']}`), `name`.{_clock_none(p)}

```html
{_x(p, 'Clock', ' name="Time"', '', 'width: 200px; height: 40px')}
```
""",
        'PopupRegion': f"""# PopupRegion

Where a group's standard popups appear on this page. `group` names the popup group; every popup whose Page has that `group` shows here, and a button whose `nav` names one of them needs a region for its group on the page it is pressed on. `name`. Modal popups need no region.

```html
{_x(p, 'PopupRegion', ' name="SourceArea" group="Sources"', '', 'width: 880px; height: 525px')}
```
""",
    }


def _preview(p, comp, height, body):
    ns = p['namespace']
    return (f'<!-- @dsCard group="{dict((n, g) for n, g, _ in COMPONENTS)[comp]}" height={height} -->\n'
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
            w, h = (int(n) for n in size.split('x'))
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
    heights = {n: ht for n, _, ht in COMPONENTS}
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
    heights['Button'] = max(heights['Button'], _button_preview_height(p))
    return {n: _preview(p, n, heights[n], b[n]) for n, _, _ in COMPONENTS}


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
    return f"""import type * as React from 'react';
/** Colors are token names ({', '.join(c['name'] for c in p['colors'])}) or '#RRGGBB'. Sizes are points. */
type Token = string;
export interface PageProps {{ name: string; kind?: 'page' | 'popup' | 'modal'; group?: string; start?: boolean | string; reachedBy?: 'program'; theme?: {' | '.join(repr(t['id']) for t in themes(p))}; scheme?: {' | '.join(repr(s['id']) for s in p['schemes'])}; background?: Token; width?: number; height?: number; does?: string; panels?: string; preview?: string; children?: React.ReactNode }}
export declare function Page(props: PageProps): React.ReactElement;
export interface MainAreaProps {{ style?: React.CSSProperties; children?: React.ReactNode }}
export declare function MainArea(props: MainAreaProps): React.ReactElement;
export interface RailProps {{ children?: React.ReactNode }}
export declare function Rail(props: RailProps): React.ReactElement;
export interface GroupProps {{ title: string; cap?: number | string; cell?: string; gap?: number | string; joined?: boolean | string; children?: React.ReactNode }}
export declare function Group(props: GroupProps): React.ReactElement;
export interface ButtonProps {{ name?: string; id?: number; variant?: {' | '.join(repr(k) for k in p['buttons'])}; type?: {' | '.join(repr(t['name']) for t in p['type'])}; size?: number; bold?: boolean; align?: 'left' | 'center' | 'right'; states?: {states}; press?: string; nav?: string; does?: string; show?: string; fill?: Token; stroke?: Token; color?: Token; border?: {' | '.join(repr(k) for k in p['borders'])}; icon?: string; children?: React.ReactNode }}
export declare function Button(props: ButtonProps): React.ReactElement;
export interface LabelProps {{ name?: string; id?: number; type?: {' | '.join(repr(t['name']) for t in p['type'])}; size?: number; bold?: boolean; align?: 'left' | 'center' | 'right'; color?: Token; does?: string; children?: React.ReactNode }}
export declare function Label(props: LabelProps): React.ReactElement;
export interface PanelProps {{ name?: string; fill?: Token; stroke?: Token; border?: string }}
export declare function Panel(props: PanelProps): React.ReactElement;
export interface LineProps {{ name?: string; orientation?: 'horizontal' | 'vertical'; color?: Token; thickness?: number }}
export declare function Line(props: LineProps): React.ReactElement;
export interface TrackProps {{ name?: string; id?: number; orientation?: 'right' | 'left' | 'up' | 'down'; fill?: Token; border?: string; value?: number; does?: string }}
export declare function Slider(props: TrackProps): React.ReactElement;
export declare function Level(props: TrackProps): React.ReactElement;
export interface ClockProps {{ name?: string; format?: 'time' | 'date' | 'datetime' | string; type?: string; size?: number; color?: Token }}
export declare function Clock(props: ClockProps): React.ReactElement;
export interface PopupRegionProps {{ name?: string; group: string }}
export declare function PopupRegion(props: PopupRegionProps): React.ReactElement;
declare global {{ interface Window {{ {ns}: {{ Page: typeof Page; MainArea: typeof MainArea; Rail: typeof Rail; Group: typeof Group; Button: typeof Button; Label: typeof Label; Panel: typeof Panel; Line: typeof Line; Slider: typeof Slider; Level: typeof Level; Clock: typeof Clock; PopupRegion: typeof PopupRegion }} }} }}
"""


def readme(p):
    ns, t = p['namespace'], p['template']
    w, ht = p['size']
    lay = p.get('layout') or {}
    main = lay.get('main')
    comps = ', '.join(f'`{n}`' for n, _, _ in COMPONENTS if n not in ('Page', 'MainArea'))
    type_line = ', '.join(f"`{s['name']}` {s['pt']:g}{' bold' if s['weight'] >= 600 else ''}"
                          for s in p['type'])
    border_line = ', '.join(f"`{k}` ({b['usage'].rstrip('.').lower()})" for k, b in p['borders'].items())
    theme_list = themes(p)
    if p.get('themes'):
        themes_md = ('## Themes\n\nEach theme is one of Extron\'s recommended pairings of a background '
                     'image and an accent scheme; set it with `theme` on every Page:\n\n'
                     + '\n'.join(f"- `{th['id']}`: {th['usage']}" for th in theme_list)
                     + '\n\nThe image is drawn on every page, under the controls, and built into '
                       'the panel as the page\'s background image. Extron allows mixing a background '
                       'with another accent scheme: `scheme` on the Page does that.\n\n')
    else:
        themes_md = ''
    if lay.get('regions'):
        layout_md = (f"## Layout\n\n{t} pages are composed the same way; follow it, or the panel "
                     f"works but does not look like {t}.\n\n"
                     + '\n'.join(f'- {r}' for r in lay['regions'])
                     + (f"\n\n`{ns}.MainArea` is that main region ({main[2]}x{main[3]} at "
                        f"{main[0]},{main[1]}): put the main task inside it." if main else '')
                     + '\n\n')
    else:
        layout_md = ''
    example = _example(p)
    drawn = (f"one page or popup of the room's Extron touch panels in Extron's {t} template, drawn at the "
             f"{p['model']}'s {w}x{ht}" if models(p) else
             f"one page or popup of an Extron {p['model']} touch panel ({w}x{ht}) in Extron's {t} template")
    return f"""Every artboard on a canvas that uses this system is {drawn}. The canvas is built into a real GUI Designer project and its control map by Claude Code, so a canvas says two things: how the panel looks, drawn only with these components, and what every control does.

## Designing a panel

Start from what the panel has to do - the rooms, sources, calls and settings - and give every job a control.

- **One artboard per page or popup.** Its root is one `{ns}.Page`, at {w}x{ht} for a page or a modal popup and {p['popup'][0]}x{p['popup'][1]} for a popup card. Name the start page's file `Main.dc.html`, as the canvas names its entry, and every other plainly (`Call.dc.html`, `Help.dc.html`); a `nav` names one by that stem (`nav="Main"`). Give each Page a `name` - what the panel calls it - and mark the start page `start="true"`.
{_panels_readme(p)}- **Only these components are built.** Use {comps} for everything that shows, and `{ns}.MainArea` to place the main task. Flex and grid containers that paint nothing are fine for layout. Text, color, borders, images or icons drawn any other way are reported and never reach the panel.
- **Say what every control does.** A button that shows another page or popup has `nav` - the target artboard's file stem - and becomes a working link in Play; on the panel the program shows it, as the control map tells the programmer to. Anything else it does goes in `does`, a plain sentence for the programmer: "Routes the laptop to the display." Labels the program rewrites, sliders and levels get a `does` too.
- **Give feedback with `states`.** A button's `states` are what the program switches it between, in order: `"Off, On"`, or `No Signal / Ready / Live` with each its own look. Every state must look different. `press` is the state shown while it is held.
- **Popups.** A standard popup (`kind="popup"`, with a `group`) appears where a page has a `PopupRegion` for that group. A modal popup (`kind="modal"`) shows the page beneath, dimmed; put its card inside as a `Panel` and its buttons on the card, with a Close: `nav` back to the page that opens it, or, where more than one page opens it, no `nav` and `does="Closes this popup."` - the program hides it and the page beneath shows again. Help, a confirmation, and a set of controls opened from a page - lighting, audio, camera select, presets - are modals, as {p['template']}'s own templates draw them; a page flip is for a mode of the room, such as a call or one source's controls. Whether an action asks for confirmation at all is the designer's choice, not a rule.
- **A page the program opens by itself**, like an incoming call, has `reached-by="program"`; a button may lead to it as well. Every other page must be reachable by `nav` from the start page.
- **A control on several pages** - Volume on Home and on Call - is a control on each, with an ID of its own. To make it one control to the program, give every copy the same `id`, a number under 1000 of your own (`id="101"`), and the same kind, `nav`, `does` and `states`: copies that do different things - Join Call opening the call page on Home and joining on Call - keep IDs of their own.

{layout_md}{_panels_section(p)}{themes_md}## Visual foundations

- **Color.** Use the tokens by name, each for what its note says. {p['examples']['color_rule']} Extron caps a project at **six colors** (Design Standards p.49), captions included: pick six and keep to them.
- **Type** is {p['font']['family']}. Sizes are points, drawn at {p['pt']} px per point as GUI Designer draws them: {type_line}. Nothing under 14 pt.
- **Shapes** come from the template's border resources only: {border_line}. The panel cannot draw any other corner, a gradient, a shadow or transparency effects.
- **Size and spacing** follow the panel's physical size: every button and slider at least {p['touch']} px each way (9 mm on a {p['model']}), at least {p['spacing']} px between touchable controls (2 mm), no more than nine buttons in one group, and place things on GUI Designer's 10 px nudge. {t}'s usual button is {p['defaults']['button']['height']} px tall.

## Iconography

{p['iconography']['intro']}

{chr(10).join('- ' + r for r in p['iconography']['rules'])}

## Example

```html
{example}
```

## Consuming this system

The components are `window.{ns}` - `{ns}.Page`, `{ns}.Button` and the rest - each mounted with `<x-import component-from-global-scope="{ns}.Button">`. Install the system on the canvas, then load in each artboard's `<head>`, after the `support.js` line, `components/bundle.css` and then `components/bundle.js` from the installed copy (`ds/<folder>/components/`). Each component's props, with an example, are in `components/<Name>/README.md`. The type is {p['font']['family']}, from Google Fonts: `<link rel="stylesheet" href="{p['font']['google']}">` in each artboard's `<helmet>`.
"""


def _example(p):
    """A start page composed the template's way: the profile's own source
    button inside the main region, and its own Help outside it."""
    def at(r):
        return f'position: absolute; left: {r[0]}px; top: {r[1]}px; width: {r[2]}px; height: {r[3]}px'
    ex = p['examples']
    src, hlp = ex['source'], ex['help']
    laptop = _x(p, 'Button', f' name="Laptop" {src["attrs"]} states="Off, On" '
                             'does="Routes the laptop to the display."', 'Laptop', at(src['rect']))
    inner = [
        _x(p, 'Label', ' name="RoomName" type="title" align="center"', 'Huddle Room',
           'position: absolute; left: 0px; top: 90px; width: 100%; height: 100px'),
        # At the foot of the main region, 16 px up: 696 px down was inside
        # Afterburn's 752 and below every bar theme's main region.
        _x(p, 'Clock', ' name="Date" format="date"', '',
           f"position: absolute; left: 17px; top: {p['layout']['main'][3] - 56}px; width: 360px; height: 40px"),
    ]
    # A source sits in the main region unless the template puts its sources
    # elsewhere: Shockwave's are tabs across the header, placed on the page.
    outside = src.get('in_main') is False
    if not outside:
        inner.insert(1, laptop)
    main = (p.get('layout') or {}).get('main')
    body = [_x(p, 'MainArea', '', '\n    ' + '\n    '.join(inner) + '\n  ')] if main else inner
    if outside:
        body.insert(0, laptop)
    body.append(_x(p, 'Button', f' name="HelpBtn" {hlp["attrs"]} nav="Help"', hlp.get('text', ''),
                   at(hlp['rect'])))
    return _x(p, 'Page', ' name="Home" start="true"', '\n  ' + '\n  '.join(body) + '\n')


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
    files = {
        'tokens.json': json.dumps(tokens(p), indent=2),
        'README.md': readme(p),
        'components/bundle.js': bundle(p),
        'components/bundle.css': BUNDLE_CSS,
        'components/index.d.ts': index_dts(p),
        'components/Cover/preview.html': cover(p),
    }
    for name, text in component_docs(p).items():
        files[f'components/{name}/README.md'] = text
    for name, text in previews(p).items():
        files[f'components/{name}/preview.html'] = text
    files['design-system.json'] = json.dumps(index(p, at, existing), indent=2)
    written = []
    for rel, text in files.items():
        path = os.path.join(out, 'project', *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        written.append('project/' + rel)
    return written


def main(argv):
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
              '\n  python -m gdl.designsys extract <template>')
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
