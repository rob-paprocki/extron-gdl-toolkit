r"""Specs that vary one thing at a time, for timing GUI Designer's Save and Build.

    python tools/build_timing_specs.py <outdir>            # the whole matrix
    python tools/build_timing_specs.py <outdir> --pages 12 --controls 15 --states 2 \
        --name mine                                         # one spec
    python tools/build_timing_specs.py <outdir> --queue 2   # and a queue.tsv of it, twice over

`examples/boardroom-full.json` builds in a time that varies threefold, and no
one spec can say what that time scales with. These are built on the same donor
(Afterburn 1035), and each differs from the base spec in one count:

    pages      how many pages, the same controls on each
    controls   how many controls on each page (a header panel, a title label,
               then buttons and labels in a 7 : 3 mix on a fixed grid, every
               one the same size, so a control costs the same wherever it is)
    states     how many feedback states each button has
    images     how many buttons carry a kit-sized PNG, and how many distinct
               PNGs they carry (24 uses of one image against 24 uses of 24)
    borders    how many distinct border resources the buttons name
    faces      how many distinct text faces the controls name

The base is 12 pages of 15 controls, two states a button, one border, one
face and no images. `tools/timing_table.py` reads the builds' logs against
the manifest (`manifest.json`) this writes beside the specs, which holds each
spec's counts - from the spec itself, so the fit is against what was built,
not what was asked for.

The PNGs are synthetic - gradients and shapes seeded by their number - and
are written under <outdir>/images; the specs name them by absolute path.
Pillow is needed for them; without it a spec with images is not written.
"""
import argparse
import json
import os
import random
import sys

# The border resources Afterburn's 1035 seed carries, by the spec's name for
# them (gdl.spec.BORDERS): a spec that names any other is planned as its
# nearest, which would blur the count.
BORDERS = ['afterburn', 'afterburn-flat', 'afterburn-14', 'rounded', 'capsule', 'rect',
           'ellipse', 'rect-3d', 'rounded-3d', 'capsule-3d', 'gradient', 'afterburn-ellipse',
           'gradient-selected', 'rounded-3d-selected']
# The seed has the first; the others are appended from another seed that has
# them (gdl.fonts.find_face) - the `donors` step says which.
FACES = ['Open Sans', 'Arial', 'Arial Black', 'Open Sans Light']

CELL_W, CELL_H, GAP = 112, 80, 16
BODY = (32, 112, 1216, 672)            # x, y, w, h under the 96 px header
IMAGE_PX = 440


def grid_slots(n):
    """The first n cells of a grid of CELL_W x CELL_H cells over the body."""
    x0, y0, w, h = BODY
    cols = (w + GAP) // (CELL_W + GAP)
    rows = (h + GAP) // (CELL_H + GAP)
    if n > cols * rows:
        raise ValueError(f'{n} controls do not fit {cols} x {rows} cells')
    return [[x0 + (i % cols) * (CELL_W + GAP), y0 + (i // cols) * (CELL_H + GAP), CELL_W, CELL_H]
            for i in range(n)]


def state_list(n, caption):
    """n distinct feedback states: Off as drawn, On in the accent, then others
    that cycle the theme's own colors and say their number in the caption - a
    spec refuses two states that look alike, and one that adds a color of its
    own goes past the project's six (GUI Design Standards p.49)."""
    if n <= 1:
        return [{'name': 'Off'}]
    out = [{'name': 'Off'}, {'name': 'On', 'fill': 'accent'}]
    cycle = ['raised', 'accent', 'surface', 'background']
    for i in range(2, n):
        out.append({'name': f'S{i + 1}', 'fill': cycle[i % len(cycle)], 'text': f'{caption} s{i + 1}'})
    return out


def write_png(path, k):
    """A 440 x 440 PNG that is nobody else's: a gradient and some shapes,
    seeded by k, about the weight of one of the kit's icons."""
    from PIL import Image, ImageDraw
    rnd = random.Random(k)
    a = tuple(rnd.randrange(30, 200) for _ in range(3))
    b = tuple(rnd.randrange(30, 200) for _ in range(3))
    im = Image.new('RGBA', (IMAGE_PX, IMAGE_PX))
    d = ImageDraw.Draw(im)
    for y in range(IMAGE_PX):
        t = y / (IMAGE_PX - 1)
        d.line([(0, y), (IMAGE_PX, y)], fill=tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,))
    for _ in range(40):
        x, y = rnd.randrange(IMAGE_PX), rnd.randrange(IMAGE_PX)
        r = rnd.randrange(8, 60)
        c = tuple(rnd.randrange(256) for _ in range(3)) + (rnd.randrange(80, 255),)
        (d.ellipse if rnd.random() < .5 else d.rectangle)([x, y, x + r, y + r], fill=c)
    im.save(path)


def make_spec(name, pages=12, controls=15, states=2, img_uses=0, img_distinct=0,
              borders=1, faces=1, img_dir=None, salt=''):
    """(spec dict, counts dict). `controls` counts the header and the title.
    `salt` is put in every caption, with the page's number, so that every
    control's artwork is a file nothing has built before - for telling a build
    of new content from a build of content the host has seen."""
    if controls < 3:
        raise ValueError('a page has a header, a title and at least one control')
    if img_uses and not img_distinct:
        raise ValueError('images in use must be at least one image')
    if borders > len(BORDERS) or faces > len(FACES):
        raise ValueError('more borders or faces than the donor can offer')
    slots = grid_slots(controls - 2)
    image_names = [f'tm_{k:03d}.png' for k in range(img_distinct)]
    counts = dict(pages=pages, controls=0, buttons=0, labels=0, shapes=0, state_renders=0,
                  images_used=0, images_distinct=len(image_names), borders=0, faces=0)
    used_borders, used_faces = set(), set()
    text_i = 0          # which face the next text control takes
    button_i = 0        # which border, and which image, the next button takes
    pgs = []
    for p in range(pages):
        tag = f'{salt}{p + 1}' if salt else ''
        ctl = [{'kind': 'panel', 'name': 'Header', 'rect': [0, 0, 1280, 96], 'fill': 'surface', 'border': 'rect'},
               {'kind': 'label', 'name': 'Title', 'rect': [32, 0, 620, 96], 'text': f'Page {p + 1}{tag}',
                'align': 'left', 'size': 32}]
        counts['shapes'] += 1
        counts['labels'] += 1
        counts['state_renders'] += 2
        if faces > 1:
            ctl[1]['font'] = FACES[text_i % faces]
        used_faces.add(ctl[1].get('font', FACES[0]))
        text_i += 1
        for i, rect in enumerate(slots):
            if i % 10 in (2, 5, 8):
                c = {'kind': 'label', 'name': f'L{i + 1:02d}', 'rect': rect, 'text': f'L{i + 1}{tag}', 'size': 16}
                if faces > 1:
                    c['font'] = FACES[text_i % faces]
                used_faces.add(c.get('font', FACES[0]))
                text_i += 1
                counts['labels'] += 1
                counts['state_renders'] += 1
            else:
                c = {'kind': 'button', 'name': f'B{i + 1:02d}', 'rect': rect, 'text': f'B{i + 1}{tag}',
                     'fill': 'raised', 'size': 16, 'states': state_list(states, f'B{i + 1}{tag}')}
                if faces > 1:
                    c['font'] = FACES[text_i % faces]
                used_faces.add(c.get('font', FACES[0]))
                text_i += 1
                if button_i < img_uses:
                    c['image'] = image_names[button_i % len(image_names)]
                    c['border'] = 'none'
                    counts['images_used'] += 1
                else:
                    c['border'] = BORDERS[button_i % borders]
                    used_borders.add(c['border'])
                button_i += 1
                counts['buttons'] += 1
                counts['state_renders'] += max(1, states)
            ctl.append(c)
        counts['controls'] += len(ctl)
        pgs.append({'name': f'Page {p + 1:02d}', 'number': 1000 + 100 * p, 'controls': ctl})
    counts['borders'] = len(used_borders)
    counts['faces'] = len(used_faces)
    spec = {
        'name': name, 'model': 'TLP1035T', 'family': 'Afterburn', 'size': [1280, 800],
        '_why': 'Build timing (tools/build_timing_specs.py): one count varied from the base spec.',
        'theme': {'background': '#12131C', 'surface': '#242634', 'raised': '#2E3142',
                  'text': '#FFFFFF', 'accent': '#3D8BFD', 'font': 'Open Sans', 'size': 18},
        'start_page': 'Page 01',
        'pages': pgs,
    }
    if image_names:
        spec['images'] = {n: os.path.join(img_dir, n) for n in image_names}
    return spec, counts


# name -> keyword arguments over the base. The base is 'base'; a family of
# names shares a prefix, and every non-base member differs from it in the one
# keyword it gives. 'pg-12', 'c15' and the like are the base under another
# name and are not built twice.
BASE = dict(pages=12, controls=15, states=2, img_uses=0, img_distinct=0, borders=1, faces=1, salt='')
MATRIX = {
    'base': {},
    'pages-01': dict(pages=1), 'pages-06': dict(pages=6), 'pages-23': dict(pages=23),
    'pages-40': dict(pages=40),
    'controls-05': dict(controls=5), 'controls-30': dict(controls=30),
    'controls-60': dict(controls=60),
    'states-1': dict(states=1), 'states-4': dict(states=4), 'states-8': dict(states=8),
    'images-24x1': dict(img_uses=24, img_distinct=1),
    'images-24x24': dict(img_uses=24, img_distinct=24),
    'images-48x48': dict(img_uses=48, img_distinct=48),
    'borders-4': dict(borders=4), 'borders-12': dict(borders=12),
    'faces-2': dict(faces=2), 'faces-4': dict(faces=4),
}


def write_one(outdir, name, **kw):
    img_dir = os.path.abspath(os.path.join(outdir, 'images'))
    args = dict(BASE, **kw)
    if args['img_distinct']:
        os.makedirs(img_dir, exist_ok=True)
        for k in range(args['img_distinct']):
            p = os.path.join(img_dir, f'tm_{k:03d}.png')
            if not os.path.exists(p):
                write_png(p, k)
    spec, counts = make_spec(name, img_dir=img_dir, **args)
    path = os.path.abspath(os.path.join(outdir, f'{name}.json'))
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(spec, fh, indent=1)
    return {'name': name, 'spec': path, 'factors': args, 'counts': counts}


def queue_lines(outdir, rounds=2, seed=24, extra_base=1):
    """Run-BuildTiming.ps1's queue for the matrix: every spec once a round, the
    order shuffled afresh each round (seeded, so it can be made again), so that
    two builds of one spec are far apart in time and a drift in the host does
    not look like a difference between specs. The base is built `extra_base`
    more times a round, spread through it: it is the control the drift shows
    in."""
    rnd = random.Random(seed)
    out = []
    for r in range(1, rounds + 1):
        names = list(MATRIX)
        rnd.shuffle(names)
        for _ in range(extra_base):
            names.insert(rnd.randrange(1, len(names)), 'base')
        for i, n in enumerate(names, 1):
            out.append('\t'.join((f'm{r}{i:02d}-{n}', os.path.abspath(os.path.join(outdir, n + '.json')), '0')))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('outdir')
    ap.add_argument('--name')
    ap.add_argument('--queue', type=int, metavar='ROUNDS',
                    help='write <outdir>/queue.tsv for Run-BuildTiming.ps1: the matrix, ROUNDS times over')
    ap.add_argument('--seed', type=int, default=24, help="the queue's shuffle seed")
    for k, v in BASE.items():
        ap.add_argument('--' + k.replace('_', '-'), type=type(v), default=None)
    ns = ap.parse_args(argv)
    os.makedirs(ns.outdir, exist_ok=True)
    one = {k: getattr(ns, k) for k in BASE if getattr(ns, k) is not None}
    if ns.name or one:
        rows = [write_one(ns.outdir, ns.name or 'custom', **one)]
    else:
        rows = [write_one(ns.outdir, n, **kw) for n, kw in MATRIX.items()]
    if ns.queue:
        with open(os.path.join(ns.outdir, 'queue.tsv'), 'w', encoding='utf-8', newline='') as fh:
            fh.write(chr(10).join(queue_lines(ns.outdir, ns.queue, ns.seed)) + chr(10))
    manifest = os.path.join(ns.outdir, 'manifest.json')
    old = {}
    if os.path.exists(manifest):
        with open(manifest, encoding='utf-8') as fh:
            old = {r['name']: r for r in json.load(fh)}
    old.update({r['name']: r for r in rows})
    with open(manifest, 'w', encoding='utf-8') as fh:
        json.dump(list(old.values()), fh, indent=1)
    for r in rows:
        c = r['counts']
        print(f"{r['name']:14s} pages {c['pages']:3d}  controls {c['controls']:5d}  buttons {c['buttons']:4d}  "
              f"state renders {c['state_renders']:5d}  images {c['images_used']}/{c['images_distinct']}  "
              f"borders {c['borders']}  faces {c['faces']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
