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
  * every seed of the theme in seeds/ (by part number): which control kinds it
    can clone (a seed with no PBSlider cannot author a slider) and which of the
    profile's border resources it lacks, each mapped to the seed's own of the
    same thickness and nearest radius.

Read only. It takes a few minutes: Pillow on the 9600 px PNGs, gdl.project on
every template and seed. The output is what gdl/designsys/<theme>.json's
`panels` block records; re-run it when Extron's templates or the seeds change.
"""
import collections
import glob
import json
import os
import re
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
    return {'part': part, 'slider': kinds['PBSlider'] > 0, 'level': kinds['PBLevel'] > 0,
            'popup': std, 'borders': borders}


def _radius_thick(resource):
    m = re.search(r'(\d+) Radius (\d+) Thick', resource or '')
    return (int(m.group(1)), int(m.group(2))) if m else None


def measure(theme, profile=None):
    _, kit = kit_files(theme)
    borders = {k: v.get('resource') for k, v in (profile or {}).get('borders', {}).items()}
    seeds = {}
    for f in sorted(glob.glob(os.path.join(REPO, 'seeds', f'{theme} *.gdl'))):
        with open(f, 'rb') as fh:
            if fh.read(40).startswith(b'version https://git-lfs'):
                continue
        seeds[os.path.relpath(f, REPO).replace('\\', '/')] = seed_facts(f, borders)
    out = {}
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
                entry['main'] = to_canvas(box, img, (w, h), layout)
        main = entry.get('main') or [0, 0, w, h]
        right = main[0] + main[2]
        if right < w - 1:
            entry['rail'], entry['rail_axis'] = [right, 0, w - right, h], 'column'
        elif main[1] + main[3] < h - 1:
            bottom = main[1] + main[3]
            entry['rail'], entry['rail_axis'] = [0, bottom, w, h - bottom], 'row'
        else:
            entry['rail'], entry['rail_axis'] = None, None
        popups = sorted((tuple(pg['size']) for pg in pages if pg['kind'] == 'popup' and not pg['modal']),
                        key=lambda s: s[0] * s[1])
        big = popups[-1] if popups else None
        entry['popup'] = list(big) if big and big[0] * big[1] >= 0.25 * w * h else None
        for m in sorted(spec.MODELS_FULL):
            hit = templates.template_for(theme, m)
            if hit and hit['series'] == row['series']:
                entry['models'].append(m)
        entry['seeds'] = {}
        for sp, facts in seeds.items():
            for m in entry['models']:
                if facts['part'] and spec.part_number(m) == facts['part']:
                    entry['seeds'][m] = sp
                    entry['kinds'] = {k: facts[k] for k in ('slider', 'level', 'popup')}
                    entry['borders'] = facts['borders']
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
