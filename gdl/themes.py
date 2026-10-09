"""Theme token sets - one shipped, and a way to read the rest out of a template.

Extron ships four themes (Afterburn, Mach, Shockwave, Turbulence) with a
resource kit each, but publishes a color guide for only one of them. Hard-coding
Afterburn would make the toolkit a one-theme tool, so there are two routes here:

  * `AFTERBURN` - the documented token set, transcribed from the Afterburn Theme
    Guide. Authoritative, and includes the four accent schemes.
  * `extract(path)` - read ANY `.glt` template or `.gdl` project and report the
    colors, border resources and fonts it actually uses, ranked by frequency.
    Empirical rather than documented, but it works for every theme, including
    ones with no published guide, and for a client's own house style.

`extract()` was checked against the theme it can be checked against: run it on
Afterburn 1020 Series.glt and the top fills come back #BABCCE / #37394E /
#242634 with #6A6E89 strokes - exactly the guide's values, arrived at without
reading the guide.

    python -m gdl.themes "out/templates/Mach 1020 Series.glt"
"""
import sys
from collections import Counter

from .project import Project

# Transcribed from the Extron Afterburn Theme Guide (79-607-24 rev A).
# See docs/design-rules.md section 4 for the same table with usage notes.
AFTERBURN = {
    'name': 'Afterburn',
    'font': 'Open Sans',
    'icon_font': 'Extron-Afterburn',      # 136 glyphs at U+E900..U+E98C
    'background': '#242634',
    'surface': '#242634',                 # page background
    'raised': '#37394E',                  # button fill, idle
    'pressed': '#242634',                 # button fill, pressed/selected
    'border': '#BABCCE',                  # button border, idle
    'border_active': '#FFFFFF',
    'text': '#FFFFFF',                    # headings, button labels, paragraphs
    'muted': '#BABCCE',                   # subheadings, date/time
    'icon': '#BABCCE',
    'icon_secondary': '#767789',
    'icon_background': '#414459',
    'divider': '#BABCCE',
    'shape': '#6A6E89',
    'track': '#37394E',                   # slider/level track over a color
    'track_on_image': '#242634',
    'fill': '#BABCCE',                    # slider fill
    'thumb_off': '#6A6E89',
    # The modal scrim, as the guide gives it. It is NOT what ships: Build draws
    # every modal as black at alpha 166 over the page beneath, whatever its
    # background (docs/design-rules.md section 4).
    'modal_scrim': '#33242634',
}

# Accent schemes, guide p.8. Primary drives selection lines and icon selection;
# secondary drives toggle/slider thumbs and level fill. Pick one per project.
AFTERBURN_ACCENTS = {
    1: {'primary': '#D69B61', 'secondary': '#626ACF'},   # orange / periwinkle
    2: {'primary': '#6ACFE8', 'secondary': '#84B266'},   # light blue / light green
    3: {'primary': '#D6B961', 'secondary': '#84B266'},   # gold / light green
    4: {'primary': '#4695D6', 'secondary': '#D6B961'},   # medium blue / gold
}

THEMES = {'afterburn': AFTERBURN}


def _hex(c):
    return None if not c else '#%02X%02X%02X%02X' % (c['A'], c['R'], c['G'], c['B'])


def extract(path, top=8):
    """What a template or project actually uses, ranked by frequency.

    Works on a `.glt` (Extron's per-panel template libraries) and on a real
    `.gdl`. Use it to derive a token set for a theme with no published guide, or
    to read a client's existing house style off a panel they already have.
    """
    p = Project.open(path)
    fills, strokes, borders, fonts = Counter(), Counter(), Counter(), Counter()
    canvas = [0, 0]
    for pg in p.pages():
        for c in pg['controls']:
            if c['fill']:
                fills[_hex(c['fill'])] += 1
            if c['stroke']:
                strokes[_hex(c['stroke'])] += 1
            if c['border']:
                borders[c['border']['resource']] += 1
            x, y, w, h = c['rect']
            if all(isinstance(v, int) for v in (x, y, w, h)):
                canvas = [max(canvas[0], x + w), max(canvas[1], y + h)]
    for o in p.instances('PBResourceReferenceFont'):
        n = p.field(o, 'resourceNameField')
        if n:
            fonts[n] += 1
    return {
        'source': path,
        # The extent of the controls, which is the panel resolution in every
        # template checked - the templates fill their canvas.
        'canvas': canvas,
        'fills': fills.most_common(top),
        'strokes': strokes.most_common(top),
        'borders': borders.most_common(top),
        'fonts': fonts.most_common(top),
        'border_resources': sorted(p.border_resources()),
    }


def main(argv):
    if len(argv) < 2:
        print('Theme token sets, and extraction from a template.')
        print('\n  python -m gdl.themes <template.glt | project.gdl>')
        print('\n  shipped token sets:', ', '.join(sorted(THEMES)))
        return 2
    t = extract(argv[1])
    print(f"{t['source']}")
    print(f"  canvas (control extent) : {t['canvas'][0]} x {t['canvas'][1]}")
    for key in ('fills', 'strokes', 'borders', 'fonts'):
        print(f"  {key:<24}: " + ', '.join(f'{k} x{v}' for k, v in t[key][:6]))
    print(f"  border resources defined: {len(t['border_resources'])}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
