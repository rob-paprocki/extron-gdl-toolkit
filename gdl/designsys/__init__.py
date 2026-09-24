"""Build an Extron template's design system for Claude Design.

    python -m gdl.designsys build afterburn out/designsys/afterburn

One Design System artifact per Extron template (docs/claude-design.md §1).
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
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = ('afterburn',)

# Token and style names the Design System page accepts; anything else drops.
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')

# (component, card group, card height). Order is the catalogue's.
COMPONENTS = (
    ('Page', 'Layout', 200), ('MainArea', 'Layout', 150), ('Button', 'Controls', 150), ('Label', 'Controls', 110),
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


# -- the bundle -----------------------------------------------------------------
def backdrops(p):
    """{theme id: data URI} - each theme's background image as the page shows
    it: stretched to the panel over the page color, as a JPEG.

    Embedded in the bundle because a canvas copies a system's bundle but not
    its uploads. Built from Extron's resource kit (spec.resolve_image), so a
    machine without the kit, or without Pillow, gets a system whose pages are
    the page color alone - and says so.
    """
    out = {}
    wanted = [t for t in themes(p) if t.get('file')]
    if not wanted:
        return out
    try:
        import base64
        import io
        from PIL import Image
    except ImportError:
        print('  note: no Pillow - the themes carry no background images')
        return out
    from ..spec import color, resolve_image
    page = next(c['value'] for c in p['colors'] if c['name'] == p['defaults']['page']['background'])
    rgb = color(page)
    for t in wanted:
        f = resolve_image(t['file'])
        if not f:
            print(f"  note: {t['file']} not found - theme {t['id']!r} has no background image")
            continue
        im = Image.new('RGBA', tuple(p['size']), (rgb['R'], rgb['G'], rgb['B'], 255))
        src = Image.open(f).convert('RGBA').resize(tuple(p['size']), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        Image.alpha_composite(im, src).convert('RGB').save(buf, 'JPEG', quality=85)
        out[t['id']] = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    return out


# -- the resource kit -------------------------------------------------------------
# The accent colors Extron's kits name their selected images by. A name ends
# `_nsel` unselected, and `-<color>_sel` (or `-<color>-sel`, or `-<color>` with
# no suffix, or `-<color>_<n>` for a level) selected in one accent.
KIT_COLORS = ('light-blue', 'med-blue', 'light-green', 'periwinkle', 'orange', 'gold',
              'red', 'gray')
# Spelled so in Extron's Afterburn kit.
KIT_TYPOS = {'ligh-blue': 'light-blue', 'ornage': 'orange'}
_KIT_FILE = re.compile(r'^(\d+x\d+)_([^ ]+)\.png$', re.I)
_KIT_COLOR = re.compile(r'[-_](' + '|'.join(KIT_COLORS + tuple(KIT_TYPOS)) + r')(?=$|[-_])')


def kit_look(stem):
    """A kit file's stem (no size, no .png) -> (icon, look).

    'laptop_nsel' -> ('laptop', 'off'); 'laptop-orange_sel' -> ('laptop',
    'orange'); 'speaker-volume-periwinkle_3' -> ('speaker-volume_3',
    'periwinkle'); 'power' -> ('power', 'plain'); 'stop_sel' -> ('stop', 'sel').
    """
    look = None
    for suffix, what in (('_nsel', 'off'), ('-nsel', 'off'), ('_sel', 'sel'), ('-sel', 'sel')):
        if stem.endswith(suffix):
            stem, look = stem[:-len(suffix)], what
            break
    # A color wins over the suffix: the kit spells a few selected images
    # `-<color>_nsel` (756x756_dual-display-1-gold_nsel.png).
    m = _KIT_COLOR.search(stem)
    if m:
        stem, look = stem[:m.start()] + stem[m.end():], KIT_TYPOS.get(m.group(1), m.group(1))
    return stem, look or 'plain'


def kit_root(p, part='root'):
    """A part of the template's kit on this machine, or None: `root` its
    buttons, `thumbs` its slider thumbs."""
    from ..spec import RESOURCE_ROOTS
    if not (p.get('kit') or {}).get(part):
        return None
    for root in RESOURCE_ROOTS:
        d = os.path.join(root, *p['kit'][part].split('/'))
        if os.path.isdir(d):
            return d
    return None


def kit_index(p, part='root'):
    """{'files': {size: {icon: {look: file}}}, 'paths': {file: kit path}}.

    The paths are relative to the resource roots, as a spec's `images` takes
    them. Empty where the kit is not installed.
    """
    files, paths = {}, {}
    root = kit_root(p, part)
    if not root:
        return {'files': files, 'paths': paths}
    for d, _, names in sorted(os.walk(root)):
        for f in sorted(names):
            m = _KIT_FILE.match(f)
            if not m:
                continue
            size, stem = m.groups()
            icon, look = kit_look(stem)
            # Two files can read as one look: the Afterburn kit has
            # 1224x344_record_red.png beside 1224x344_record_red_sel.png. The
            # selected one is what a state asks for, so it wins, and the
            # other is named rather than dropped silently.
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
            paths.setdefault(f, p['kit'][part] + '/' + rel)
    return {'files': files, 'paths': paths}


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
    index = kit_index(p, 'thumbs')
    for icons in index['files'].values():
        looks = icons.get(family) or {}
        f = looks.get(p['kit']['secondary'].get(scheme))
        if f:
            return f, index['paths'][f]
    return None


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
    root = kit_root(p)
    if root in _ART:
        return _ART[root]
    out = _ART[root] = {}
    scale = p['kit'].get('scale') or {}
    for size, icons in index['files'].items():
        w = scale.get(size, 160)
        for looks in icons.values():
            for f in looks.values():
                if f in out:
                    continue
                rel = index['paths'][f][len(p['kit']['root']) + 1:]
                path = os.path.join(root, *rel.split('/'))
                out[f] = _webp(Image, path, w)
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
    profile['backdrops'] = backdrops(p)
    if p.get('kit'):
        index = kit_index(p)
        profile['kit'] = dict(p['kit'], files=index['files'],
                              art=kit_art(p, index) if art and index['files'] else {},
                              thumb_art=thumb_art(p) if art else {})
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
    # A variant with an icon of its own (a toggle's `toggle-1`) takes that
    # family, and only it; the others sharing its kit size leave it out.
    claimed = {}
    for k, v in p['buttons'].items():
        if v.get('kit') and v.get('icon'):
            family = v['icon'].rsplit('-', 1)[0]
            claimed[k] = sorted(n for n in files.get(v['kit'], {}) if n.startswith(family))
    taken = {n for names in claimed.values() for n in names}
    for k, v in p['buttons'].items():
        size = v.get('kit') or (v.get('with_icon') or {}).get('kit')
        if k in claimed:
            out[k] = claimed[k]
        elif size and files.get(size):
            out[k] = sorted(set(files[size]) - taken)
    return out


def _icons_md(p):
    names = icon_names(p)
    if not names:
        return ('The kit was not installed where this system was built, so it lists no icon '
                'names.')
    return '\n'.join(f"- `{k}`: {', '.join(f'`{n}`' for n in v)}" for k, v in names.items())


def component_docs(p):
    """{name: README markdown} - guidelines Claude Design reads before mounting."""
    t = p['template']
    variants = '\n'.join(f"- `{k}`: {v['usage']}" for k, v in p['buttons'].items())
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

Place controls inside it with absolute positions or with flex and grid containers: containers that paint nothing are fine. Anything that paints and is not one of these components is not built.

```html
{_x(p, 'Page', ' name="Home" start="true"', '...')}
```
""",
        'MainArea': f"""# MainArea

The {t} page's main region, as a layout container: {_main_words(p)} It paints nothing and is not a control - the page draws the region - so put the page's main task inside it, positioned relative to it or with flex and grid.

```html
{_x(p, 'MainArea', '', chr(10) + '  ' + _x(p, 'Label', ' name="Title" type="subheading" align="center"', 'Select a Source', 'position: absolute; left: 0px; top: 190px; width: 100%; height: 60px') + chr(10))}
```
""",
        'Button': f"""# Button

The panel's button: a caption, the states the program switches it between, and what pressing it does. Size it with the x-import's own style; it fills that box, at least {p['touch']}px each way.

Props:
- The caption is the element's text. `type`: `button` (14 pt, default) or `button-large` (20 pt bold); `size` in points overrides it.
- `variant`:
{variants}
- `icon`: an icon from {t}'s resource kit, by name, for the image variants - `source`, `list`, `icon`, `toggle` (default `toggle-1`) - or on an `outlined` button, where it sits left of the caption. The kit draws each icon unselected and selected in every accent, with the selection line where the variant has one, so the button's states show themselves: state 0 unselected, the rest selected in the page's accent. The names, by variant:
{_icons_md(p)}
- `states`: the states the program sets, in order - state 0 is what the panel shows first. `"Off, On"` by name, or JSON for looks: `'{p['examples']['states']}'`. A state takes `name`, `fill`, `stroke`, `color` (caption color), `border`, `text` (its own caption), and on an image button `look` (`off` or `on`) and `icon` (its own icon: a mute button is `speaker-volume_3` when live and `speaker-mute-1` when muted). Off and On start from the variant's look. Every state must look different. {p['examples']['states_note']}
- `press`: the state shown while the button is held. Default: On, else the second state. The canvas draws it while you hold the button in Play, as the panel does, so give it a look that reads as pressed. It cannot be the state the button rests in, and a button with a single state has nothing to show - give it a second.
- `nav`: the artboard this button shows, by its file name without `.dc.html` - `nav="Help"` shows `Help.dc.html`. The button becomes that link, so Play follows it.
- `does`: anything else it does, in a sentence for the programmer: "Routes the laptop to the display; Live while it is routed."
- `show`: the state to draw on the canvas (default the first). Design only.
- `name`: the control's name; `id` pins its number.
- `fill`, `stroke`, `color`, `border` override the variant for every state.

Size an image button to its kit image's shape, or the image is letterboxed: `source` square (110x110 as the seed has them), `icon` square (64x64), `list` and `toggle` about 3.6:1 (192x54), an `outlined` button with an icon 2.4:1 (154x64).

```html
{_x(p, 'Button', ' name="Laptop" type="button-large" states="Off, On" does="Routes the laptop to the display."', 'Laptop', 'width: 280px; height: 120px')}
{_x(p, 'Button', ' name="HelpBtn" nav="Help"', 'Help', 'width: 200px; height: 64px')}
{_x(p, 'Button', ' name="Wireless" variant="source" icon="sharelink-1" states="Off, On" does="Routes wireless presentation to the display."', 'Wireless', 'width: 110px; height: 110px')}
{_x(p, 'Button', ' name="Power" variant="icon" icon="power" nav="ConfirmOff"', '', 'width: 64px; height: 64px')}
```
""",
        'Label': f"""# Label

Text on the panel: a title, a status line, a caption beside a control. It fills its box and centers the text vertically.

Props: the text is the element's text; `type` (`title`, `heading`, `subheading`, `body`, `body-strong`), `size` in points, `bold`, `align` (`left`, `center`, `right`), `color` (a token: `text`, `text-secondary`, `accent`), `name`, `does` - when the program changes the text, say so: "Shows the codec's call status."

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

A divider. `orientation` (`horizontal`, default, or `vertical`), `color` (default `text-secondary`), `thickness` in px, `name`.

```html
{_x(p, 'Line', ' name="Divider"', '', 'width: 1200px; height: 2px')}
```
""",
        'Slider': f"""# Slider

A control the user drags: volume, a light level. Drawn as {t} builds it: a rounded rail `track` px wide (default {p['defaults']['slider']['track']}) down the middle of the control's box, the rail's filled part in `{p['defaults']['slider']['value']}`, and a round thumb in `{p['defaults']['slider']['thumb_color']}` whose box is `thumb` px (default {p['defaults']['slider']['thumb']}) - the circle itself about two-thirds of that, with a shadow round it, as the panel draws it. The box is the touch area: make it at least as wide as the thumb. `orientation`: the direction the value grows, `{p['defaults']['slider']['orientation']}` by default as {t}'s own volume sliders are (`up`, `down`, `left`, `right`). `fill`: the rail's empty part, default `{p['defaults']['slider']['fill']}` - on a `raised` panel use `page`. `name`, and `does` - what it sets and whether it follows feedback. `value` (0-100) only draws the canvas. The filled part and the thumb come from the template's own slider, so they are not props.

```html
{_x(p, 'Slider', ' name="Volume" does="Sets program volume; follows the DSP level."', '', 'width: 50px; height: 395px')}
```
""",
        'Level': f"""# Level

A meter the program drives: signal level, a countdown. A rail like Slider's with no thumb, filled in `{p['defaults']['level']['value']}`, and not touchable. `orientation` (default `{p['defaults']['level']['orientation']}`), `track`, `fill`, `name`, `does`.

```html
{_x(p, 'Level', ' name="MicLevel" orientation="up" does="Shows the microphone level."', '', 'width: 40px; height: 240px')}
```
""",
        'Clock': f"""# Clock

The panel's own date or time, drawn by the panel with no program. `format`: `time` (default, `h:mm tt`), `date` (`MMMM d`), `datetime`, or any .NET date pattern - the pattern the panel formats its clock with, drawn here for 28 September 1960 at midnight as GUI Designer draws it; `align` (`left`, `center`, `right`); `type`, `size`, `color` (default `text-secondary`), `name`.

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
            '  function row(kids) { return h("div", { style: { display: "flex", gap: "24px", padding: "16px", alignItems: "center", flexWrap: "wrap" } }, kids); }\n'
            f'  ReactDOM.createRoot(document.getElementById("root")).render({body});\n'
            '</script>\n</body>\n</html>\n')


def previews(p):
    heights = {n: ht for n, _, ht in COMPONENTS}
    s = p['size']
    scale = 0.12
    b = {
        'Page': ('h("div", { style: { transform: "scale(' + str(scale) + ')", transformOrigin: "0 0", width: "'
                 + str(s[0]) + 'px", margin: "16px" } }, h(N.Page, { name: "Home" }, '
                 'h("div", { style: { position: "absolute", left: "40px", top: "40px", width: "1200px", height: "112px" } }, '
                 'h(N.Label, { type: "title" }, "Huddle Room")), '
                 'h("div", { style: { position: "absolute", left: "40px", top: "200px", width: "360px", height: "200px" } }, '
                 'h(N.Button, { type: "button-large" }, "Laptop"))))'),
        'MainArea': ('h("div", { style: { transform: "scale(' + str(scale) + ')", transformOrigin: "0 0", width: "'
                     + str(s[0]) + 'px", margin: "16px" } }, h(N.Page, { name: "Home" }, '
                     'h(N.MainArea, null, h("div", { style: { position: "absolute", left: 0, right: 0, top: "300px", height: "120px" } }, '
                     'h(N.Label, { type: "title", align: "center" }, "Main area")))))'),
        'Button': ('row(Object.keys(N.profile.buttons).filter(function (v) { return !N.profile.buttons[v].kit; })'
                   '.map(function (v) { return [box(180, 64, h(N.Button, { key: v, variant: v }, v)), '
                   'box(180, 64, h(N.Button, { key: v + "on", variant: v, show: "On" }, v + " On"))]; })'
                   '.concat(N.profile.kit ? [["source", "laptop", 110, 110, "Laptop"], ["list", "display", 192, 54, "Display"], '
                   '["icon", "help", 64, 64, ""], ["toggle", null, 192, 54, "Power"], ["outlined", "swap", 154, 64, "Swap"]]'
                   '.map(function (x) { return ["Off", "On"].map(function (st) { return box(x[2], x[3], '
                   'h(N.Button, { key: x[0] + st, variant: x[0], icon: x[1] || undefined, show: st }, x[4])); }); }) : []))'),
        'Label': ('row(["title", "heading", "body", "body-strong"].map(function (t) { '
                  'return box(260, 60, h(N.Label, { key: t, type: t }, t)); }))'),
        'Panel': 'row([box(260, 90, h(N.Panel, { key: 1 })), box(260, 90, h(N.Panel, { key: 2, fill: "pressed", border: "rect" }))])',
        'Line': 'row([box(560, 2, h(N.Line))])',
        'Slider': 'row([box(420, 60, h(N.Slider, { value: 60 }))])',
        'Level': 'row([box(420, 40, h(N.Level, { value: 40 })), box(40, 88, h(N.Level, { orientation: "up", value: 70 }))])',
        'Clock': 'row([box(200, 40, h(N.Clock)), box(360, 40, h(N.Clock, { format: "date" }))])',
        'PopupRegion': 'row([box(440, 90, h(N.PopupRegion, { group: "Sources" }))])',
    }
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
export interface PageProps {{ name: string; kind?: 'page' | 'popup' | 'modal'; group?: string; start?: boolean | string; reachedBy?: 'program'; theme?: {' | '.join(repr(t['id']) for t in themes(p))}; scheme?: {' | '.join(repr(s['id']) for s in p['schemes'])}; background?: Token; width?: number; height?: number; does?: string; children?: React.ReactNode }}
export declare function Page(props: PageProps): React.ReactElement;
export interface MainAreaProps {{ style?: React.CSSProperties; children?: React.ReactNode }}
export declare function MainArea(props: MainAreaProps): React.ReactElement;
export interface ButtonProps {{ name?: string; id?: number; variant?: {' | '.join(repr(k) for k in p['buttons'])}; type?: 'button' | 'button-large'; size?: number; bold?: boolean; align?: 'left' | 'center' | 'right'; states?: {states}; press?: string; nav?: string; does?: string; show?: string; fill?: Token; stroke?: Token; color?: Token; border?: {' | '.join(repr(k) for k in p['borders'])}; icon?: string; children?: React.ReactNode }}
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
declare global {{ interface Window {{ {ns}: {{ Page: typeof Page; MainArea: typeof MainArea; Button: typeof Button; Label: typeof Label; Panel: typeof Panel; Line: typeof Line; Slider: typeof Slider; Level: typeof Level; Clock: typeof Clock; PopupRegion: typeof PopupRegion }} }} }}
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
    return f"""Every artboard on a canvas that uses this system is one page or popup of an Extron {p['model']} touch panel ({w}x{ht}) in Extron's {t} template. The canvas is built into a real GUI Designer project and its control map by Claude Code, so a canvas says two things: how the panel looks, drawn only with these components, and what every control does.

## Designing a panel

Start from what the panel has to do - the rooms, sources, calls and settings - and give every job a control.

- **One artboard per page or popup.** Its root is one `{ns}.Page`, at {w}x{ht} for a page or a modal popup and {p['popup'][0]}x{p['popup'][1]} for a popup card. Give the artboard file a plain stem (`Home.dc.html`, `Help.dc.html`) and the Page a `name`. Mark the start page `start="true"`.
- **Only these components are built.** Use {comps} for everything that shows, and `{ns}.MainArea` to place the main task. Flex and grid containers that paint nothing are fine for layout. Text, color, borders, images or icons drawn any other way are reported and never reach the panel.
- **Say what every control does.** A button that shows another page or popup has `nav` - the target artboard's file stem - and becomes a working link in Play. Anything else it does goes in `does`, a plain sentence for the programmer: "Routes the laptop to the display." Labels the program rewrites, sliders and levels get a `does` too.
- **Give feedback with `states`.** A button's `states` are what the program switches it between, in order: `"Off, On"`, or `No Signal / Ready / Live` with each its own look. Every state must look different. `press` is the state shown while it is held.
- **Popups.** A standard popup (`kind="popup"`, with a `group`) appears where a page has a `PopupRegion` for that group. A modal popup (`kind="modal"`) shows the page beneath, dimmed; put its card inside as a `Panel` and its buttons on the card. Confirmations are the designer's choice, not a rule.
- **A page the program opens by itself**, like an incoming call, has `reached-by="program"`. Every other page must be reachable by `nav` from the start page.

{layout_md}{themes_md}## Visual foundations

- **Color.** Use the tokens by name, each for what its note says. {p['examples']['color_rule']} Extron caps a project at **six colors** (Design Standards p.49), captions included: pick six and keep to them.
- **Type** is {p['font']['family']}. Sizes are points, drawn at {p['pt']} px per point as GUI Designer draws them: {type_line}. Nothing under 14 pt.
- **Shapes** come from the template's border resources only: {border_line}. The panel cannot draw any other corner, a gradient, a shadow or transparency effects.
- **Size and spacing** follow the panel's physical size: every button and slider at least {p['touch']} px each way (9 mm on a {p['model']}), at least {p['spacing']} px between touchable controls (2 mm), no more than nine buttons in one group, and place things on GUI Designer's 10 px nudge. {t}'s usual button is {p['defaults']['button']['height']} px tall.

## Iconography

{t} shows state with icons, not with colored text. Every icon comes from {t}'s own resource kit through a Button's `icon` - never draw one, and never color a caption red.

- **Anatomy** (the guide's p.4): a `text-secondary` ({_hex_of(p, 'text-secondary')}) stroke and primary elements, `text-subtle` ({_hex_of(p, 'text-subtle')}) secondary elements, an `icon-ground` ({_hex_of(p, 'icon-ground')}) background inside the icon, and - selected - the supporting element in the accent. The kit already draws all of this, for every accent scheme.
- **Which button**: a stand-alone control (help, power, close, mute) is `variant="icon"`, 64x64. Sources and cameras are `source`, a row of squares with the label under the icon. Options down the left rail are `list`, a selection line at the left when chosen. On and off is `toggle`. An important action with a label is `outlined` with an `icon` (End Call, Swap).
- **Feedback**: state 0 draws the icon unselected, the others selected - in the accent, with the variant's selection line and fill. A single-image icon (`power`, `call_connected`) still shows it is pressed.
- **Alerts** are `variant="alert"`: a red fill with a white caption, for a condition someone has to act on - a fault, a warning - and one per screen at most. An ordinary action, even a final one like shutting the room down, is an outlined button unless the designer asks for red.

## Example

```html
{example}
```
"""


def _hex_of(p, name):
    return next((c['value'] for c in p['colors'] if c['name'] == name), '?')


def _example(p):
    """A start page composed the template's way."""
    states = "'" + p['examples']['on_off'] + "'"
    main = (p.get('layout') or {}).get('main')
    inner = [
        _x(p, 'Label', ' name="RoomName" type="title" align="center"', 'Huddle Room',
           'position: absolute; left: 0px; top: 90px; width: 100%; height: 100px'),
        (_x(p, 'Button', ' name="Laptop" variant="source" icon="laptop" states="Off, On" '
                         'does="Routes the laptop to the display."',
            'Laptop', 'position: absolute; left: 403px; top: 320px; width: 110px; height: 110px')
         if p.get('kit') else
         _x(p, 'Button', f' name="Laptop" type="button-large" states={states} '
                         'does="Routes the laptop to the display."',
            'Laptop', 'position: absolute; left: 318px; top: 330px; width: 280px; height: 120px')),
        _x(p, 'Clock', ' name="Date" format="date"', '',
           'position: absolute; left: 17px; top: 696px; width: 360px; height: 40px'),
    ]
    body = [_x(p, 'MainArea', '', '\n    ' + '\n    '.join(inner) + '\n  ')] if main else inner
    if main:
        body.append(_x(p, 'Button', ' name="HelpBtn" variant="icon" icon="help" nav="Help"', '',
                       'position: absolute; left: 1157px; top: 706px; width: 64px; height: 64px')
                    if p.get('kit') else
                    _x(p, 'Button', ' name="HelpBtn" variant="ghost" nav="Help"', 'Help',
                       'position: absolute; left: 1121px; top: 706px; width: 144px; height: 64px'))
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
    if len(argv) < 4 or argv[1] != 'build' or argv[2] not in TEMPLATES:
        print(__doc__.strip().split('\n\n')[0])
        print(f"\n  python -m gdl.designsys build <{'|'.join(TEMPLATES)}> <out dir> "
              '[--at ISO-8601] [--index existing design-system.json]')
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
