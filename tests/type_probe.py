"""How big does a panel draw a point? Bake captions and measure them.

    python tests/type_probe.py specs <out dir>
    python tests/type_probe.py measure <built.gdl> [<built.gdl> ...]

layout.json exports only a font's PointSize and a cloned button draws its
caption live, so no built file says how many pixels a point is. A button with
`flatten` on has Build bake its caption into the artwork with GUI Designer's own
rasterizer for that project's platform: measure the cap height of "HHHH" there,
at each probe size, on each model's seed. docs/gdl-format.md has the result.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.spec import touch_minimums  # noqa: E402

POINTS = (14, 18, 24, 30, 36)   # 14 is the documented body minimum; none below
PAGE = 'Type Probe'
# (seed file, model, canvas) - one per DPI we can build on today.
SEEDS = (('Afterburn 1035.gdl', 'TLP1035T', (1280, 800)),
         ('Afterburn 835 (Project1).gdl', 'TLP835M', (1280, 800)),
         ('Afterburn 1535.gdl', 'TLP1535M', (1920, 1080)),
         ('Afterburn 300M Portrait.gdl', 'TLP300M', (320, 480)),
         ('Afterburn 1230W.gdl', 'TLP1230WTG', (1920, 720)))


def probe_spec(model, size):
    """One page: a black button per point size, captioned HHHH in white, baked."""
    target, gap = touch_minimums(model)
    w = min(300, size[0] - 20)
    h = max(target, 80)
    controls = []
    for i, pt in enumerate(POINTS):
        controls.append({'kind': 'button', 'name': f'P{pt}', 'text': 'HHHH', 'size': pt,
                         'rect': [10, 10 + i * (h + max(gap, 8)), w, h],
                         'fill': '#000000', 'color': '#FFFFFF', 'border': 'none',
                         'align': 'left', 'flatten': True})
    return {'name': f'Type probe {model}', 'model': model, 'size': list(size),
            'theme': {'background': '#000000', 'text': '#FFFFFF',
                      'font': 'Open Sans', 'size': 14},
            'pages': [{'name': PAGE, 'number': 900, 'controls': controls}]}


def cap_height(png, ink=(255, 255, 255)):
    """Rows whose brightest pixel is at least half-way to `ink`, top to bottom;
    None when there are none - a caption that did not bake is not 0 px."""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert('RGB')
    w, h = im.size
    px = im.load()
    half = sum(ink) / 2
    rows = [y for y in range(h) if max(sum(px[x, y]) for x in range(w)) >= half]
    return rows[-1] - rows[0] + 1 if rows else None


def measure(built):
    """{point size: cap height px or None} for the probe page of a built file."""
    from gdl.compose import load
    j, assets = load(built)
    page = next(p for p in j['Pages'] if p['Name'] == PAGE)
    out = {}
    for c in page.get('Controls') or []:
        if c.get('Name', '').startswith('P') and c['Name'][1:].isdigit():
            art = assets.get(c.get('TLPImageID'))
            out[int(c['Name'][1:])] = cap_height(art) if art else None
    return out


def main(argv):
    if len(argv) >= 3 and argv[1] == 'specs':
        os.makedirs(argv[2], exist_ok=True)
        for seed, model, size in SEEDS:
            path = os.path.join(argv[2], f'{model}.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(probe_spec(model, size), fh, indent=1)
            print(f'{path}  <- seeds/{seed}')
        return 0
    if len(argv) >= 3 and argv[1] == 'measure':
        for built in argv[2:]:
            got = measure(built)
            print(os.path.basename(built), ' '.join(
                f'{pt}pt={v}px({v / pt:.3f})' if v else f'{pt}pt=NO INK'
                for pt, v in sorted(got.items())))
        return 0
    print(__doc__.strip().split('\n\n')[0])
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
