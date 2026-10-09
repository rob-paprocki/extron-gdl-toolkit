"""Extron's series templates, indexed from GUI Designer's own table.

GUI Designer's template installer keeps `TemplateInfoTable.config` beside the
templates: an NRBF `TemplateManager+TemplateInfoDictionary` whose `mTemplates`
maps each `.glt`'s path to a `TemplateInfo` - theme, resolution and DPI. On
1.28.0.7 it holds 50 rows, 13 of them Afterburn. Its `mSeries` is stored as
a number - GUI Designer's `TLPSeries` (`Series1020` is 1), whose names are in
the assembly and not the file - so a row's series is its file stem
(`Afterburn 1020 Series`); every `.glt` carries the same facts in a
`PBTemplate`, and all 13 Afterburn files agree with the table.

    python -m gdl.templates Afterburn          # every series, with tier
    python -m gdl.templates Afterburn TLP725T  # the series a model takes
"""
import math
import os
import sys

from . import nrbf, spec

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# vendor/ first (vendor/README.md), the install as the fallback - the order
# gdl.spec.RESOURCE_ROOTS and tests/_corpus.py use.
TABLE_DIRS = (
    os.path.join(REPO, 'vendor', 'extron', 'TouchLink Templates'),
    r'C:\Users\Public\Documents\Extron\GUI Designer Templates\TouchLink Templates',
)


def _default_path():
    for d in TABLE_DIRS:
        p = os.path.join(d, 'TemplateInfoTable.config')
        if os.path.exists(p):
            return p
    return None


_TABLE = {}


def table(path=None):
    """Every row: {file, theme, series, size, dpi, soft}. `soft` is a soft-client
    row (an ECP template), whose resolution is a device preset rather than a
    panel's - its record is a `ResolutionPlus`, keyed 'Resolution+resolutionX'.
    [] when there is no table."""
    path = path or _default_path()
    if not path or not os.path.exists(path):
        return []
    if path not in _TABLE:
        _TABLE[path] = _read(path)
    return list(_TABLE[path])


def _read(path):
    with open(path, 'rb') as f:
        objects = nrbf.parse(f.read()).objects

    def deref(v):
        while isinstance(v, tuple) and len(v) == 2 and v[0] == 'ref':
            v = objects.get(v[1])
        return v

    root = next(o for o in objects.values()
                if isinstance(o, dict) and 'mTemplates' in o)
    rows = []
    for kv in deref(deref(deref(root['mTemplates'])['KeyValuePairs'])) or []:
        info = deref(deref(kv)['value'])
        res = deref(info['mResolution'])
        soft = res['__class'].endswith('ResolutionPlus')
        key = 'Resolution+' if soft else ''
        name = os.path.basename(deref(info['mFilePath']))
        rows.append({
            'file': name,
            'theme': deref(info['mTheme']),
            'series': os.path.splitext(name)[0],
            'size': (res[key + 'resolutionX'], res[key + 'resolutionY']),
            'dpi': res[key + 'dpi'],
            'soft': soft,
        })
    return rows


def series(theme, path=None):
    """One theme's panel templates - soft clients left out."""
    return [r for r in table(path) if r['theme'] == theme and not r['soft']]


def path_of(row, path=None):
    """Where a row's .glt is: beside the table. None when there is no table."""
    table_path = path or _default_path()
    return os.path.join(os.path.dirname(table_path), row['file']) if table_path else None


def _tier(row):
    w, h = row['size']
    return spec.tier_for(math.hypot(w, h) / row['dpi']) if row['dpi'] else None


def template_for(theme, model, path=None):
    """The series template a model takes, or None.

    An exact (size, DPI) match first. Failing that, a size match only when the
    template is in the model's own tier: no template is authored at the 725's
    169.55 DPI, and the 1024x600 one (the 1020, 118 DPI) is tier A like the 725;
    but Afterburn's only 800x480 template is the 520's tier B hub, the wrong
    layout for a 7" 720 - so a 720 gets None, not a 5" layout. A tie - the 300M's
    '300 Series' and '300 Portrait Series' share size and DPI - goes to the one
    named for the canvas's orientation, which is the one the wizard seeds.
    """
    if model not in spec.MODELS_FULL or model in spec.SOFT_CLIENTS:
        return None
    w, h, d, _ = spec.MODELS_FULL[model]
    rows = [r for r in series(theme, path) if tuple(r['size']) == (w, h)]
    exact = [r for r in rows if d and abs(r['dpi'] - d) < 0.01]
    pick = exact or [r for r in rows if _tier(r) == spec.tier(model)]
    if not pick:
        return None
    word = 'Portrait' if h > w else 'Landscape'
    return next((r for r in pick if word in r['series']), pick[0])


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[-2].strip())
        print(__doc__.strip().splitlines()[-1].strip())
        return 2
    if not table():
        print('no TemplateInfoTable.config in', ' or '.join(TABLE_DIRS))
        return 1
    if len(argv) > 2:
        r = template_for(argv[1], argv[2])
        print(r['series'] if r else f'no {argv[1]} series for {argv[2]}')
        return 0 if r else 1
    for r in sorted(series(argv[1]), key=lambda r: (r['size'], r['series'])):
        print(f"{r['series']:<34} {r['size'][0]}x{r['size'][1]:<5} {r['dpi']:>8.2f} dpi  tier {_tier(r)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
