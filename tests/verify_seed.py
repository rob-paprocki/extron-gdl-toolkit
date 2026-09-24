"""Is this file a seed for this model? Run on every seed New-GdlSeed.ps1 makes.

    python tests/verify_seed.py <seed.gdl> <model>

The Project Create Wizard can make a Blank project while reading "Theme: X"
(docs/from-scratch.md section 5c), and a seed for the wrong model builds the
wrong panel with every other gate green - the built panel is the seed's model.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.project import Project  # noqa: E402
from gdl.spec import MODELS, part_number, sizes  # noqa: E402

# A themed project has 2-13 pages and 170-880 controls; a Blank one 1 page and 3.
MIN_PAGES = 2
MIN_CONTROLS = 100


def check_seed(path, model, min_pages=MIN_PAGES, min_controls=MIN_CONTROLS):
    if model not in MODELS:
        return [f'{model!r} is not a panel GUI Designer builds for']
    p = Project.open(path)
    probs = []
    proj = next(p.instances('PBProject'), None)
    if proj is None:
        return [f'{path} has no PBProject - a template, not a project']
    plat = p.field(proj, 'platformField')
    got = p.field(plat, 'partNumberField') if plat is not None else None
    if got != part_number(model):
        probs.append(f'part number {got!r}, but {model} is {part_number(model)!r}')
    pages = list(p.pages())
    n_pages = sum(1 for pg in pages if pg['kind'] == 'page')
    n_controls = sum(len(pg['controls']) for pg in pages)
    if n_pages < min_pages or n_controls < min_controls:
        probs.append(f'{n_pages} page(s), {n_controls} controls - a Blank project, not a '
                     f'themed seed (a themed one has {min_pages}+ pages, {min_controls}+ controls)')
    canvas = max(((c['rect'][2], c['rect'][3]) for pg in pages if pg['kind'] == 'page'
                  for c in pg['controls'] if None not in c['rect'][2:]),
                 key=lambda s: s[0] * s[1], default=None)
    if canvas and not any(canvas[0] <= w and canvas[1] <= h for w, h in sizes(model)):
        probs.append(f'largest control {canvas[0]}x{canvas[1]} does not fit a {model} '
                     f'({" or ".join("%dx%d" % s for s in sizes(model))})')
    return probs


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().split('\n\n')[0])
        return 2
    probs = check_seed(argv[1], argv[2])
    for pr in probs:
        print('  PROBLEM ' + pr)
    print(f"{'ok' if not probs else f'{len(probs)} problem(s)'}: {argv[1]} as {argv[2]}")
    return 1 if probs else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
