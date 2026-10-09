"""Is this file a seed for this model? Run on every seed New-GdlSeed.ps1 makes.

    python tests/verify_seed.py <seed.gdl> <model> [<theme>]

The Project Create Wizard can make a Blank project while reading "Theme: X"
(docs/from-scratch.md section 5c), and a seed for the wrong model builds the
wrong panel with every other gate green - the built panel is the seed's model.
So does one made from another series' template: a built seed names no series,
so its pages are compared with the template GUI Designer takes for the model.
"""
import collections
import functools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl import templates  # noqa: E402
from gdl.project import Project  # noqa: E402
from gdl.spec import MODELS, part_number, sizes  # noqa: E402

# A themed project has 2-13 pages and 86-880 controls once built - the fewest
# the 320M's, twelve single-purpose pages on a 320x240 screen - and a Blank one
# 1 page and 3. A floor of 100, set before any small panel had a seed, refused
# the 320M's.
MIN_PAGES = 2
MIN_CONTROLS = 20

# Create copies a series template's pages into the project with their ids, names,
# sizes and controls' rectangles, and Build adds a popup reference per modal popup
# to each (docs/gdl-format.md section 7). So a seed's pages are found in its
# template bar those references: every seed here, against the template its model
# takes, holds all of them. The nearest other template of the same canvas shares
# 58% of a seed's pages (Afterburn's '300 Series' for a '300 Portrait Series'
# seed; 69% the other way); the 520 and the 720, both 800x480, share none, in
# every theme that has both. The line sits between, with room each side.
ADDED = 'PBPopupPageReference'
SERIES_SHARE = 0.75


def _controls(pg):
    return collections.Counter((c['type'], c['name'], tuple(c['rect']))
                               for c in pg['controls'] if c['type'] != ADDED)


@functools.lru_cache(maxsize=None)
def template_pages(path):
    """A template's pages. Reading one takes seconds (Turbulence's, half a
    minute), and a run asks for the same few more than once."""
    return tuple(Project.open(path).pages())


def clone_share(pages, of):
    """The part of a seed's named pages that are a page of the template `of`:
    the same kind and id, the same name and size, and every control of the
    seed's among the template's - a panel can drop what it cannot show."""
    there = {(pg['kind'], pg['id']): pg for pg in of}
    named = [pg for pg in pages if pg['name']]
    hit = 0
    for pg in named:
        t = there.get((pg['kind'], pg['id']))
        if (t and t['name'] == pg['name'] and tuple(t['size']) == tuple(pg['size'])
                and not _controls(pg) - _controls(t)):
            hit += 1
    return hit / len(named) if named else 0.0


def series_problems(pages, size, model, theme):
    """Is the seed a clone of the series template GUI Designer takes for `model`?

    Nothing in a built seed names its series - its name is the theme, the
    application and the screen's number ('Afterburn All-inclusive 725' is the
    1020 series) - so the pages are compared. [] when there is no template to
    compare with: none installed here, or none of this theme serves the model."""
    want = templates.template_for(theme, model)
    if want is None:
        return []
    same = [r for r in templates.series(theme) if tuple(r['size']) == tuple(size)]
    if tuple(want['size']) == tuple(size):
        mine = [want]
    else:
        # the 300M runs either way up, and its templates come in both
        # orientations at one DPI
        mine = [r for r in same if abs(r['dpi'] - want['dpi']) < 0.01]
    if not mine:
        return [f"no {theme} template at {size[0]}x{size[1]} to compare with - GUI Designer takes "
                f"{want['series']} for a {model}"]
    # a table without its templates beside it: nothing to read, and a verifier
    # that raises makes New-GdlSeed.ps1 delete a good seed
    if not all(templates.path_of(r) and os.path.exists(templates.path_of(r)) for r in mine):
        return []

    def share(rows):
        return max((clone_share(pages, template_pages(templates.path_of(r))) for r in rows), default=0.0)

    got = share(mine)
    if got >= SERIES_SHARE:
        return []
    said = (f"its pages are not the {want['series']} template's (only {got:.0%} are) - "
            f"GUI Designer takes that series for a {model}")
    rival = [(share([r]), r['series']) for r in same
             if r not in mine and templates.path_of(r) and os.path.exists(templates.path_of(r))]
    best = max(rival, default=(0.0, ''))
    if best[0] >= SERIES_SHARE:
        said += f", and they are {best[1]}'s"
    return [said]


def check_seed(path, model, min_pages=MIN_PAGES, min_controls=MIN_CONTROLS, theme=None):
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
    skin = p.field(proj, 'skinField')
    # In any case, as the wizard's combo matches it: New-GdlSeed.ps1 passes the
    # -Theme it was given, and deletes the seed if this refuses it.
    if theme and (skin or '').casefold() != theme.casefold():
        probs.append(f'theme {skin!r}, not {theme!r}')
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
    # The series, once the rest has passed - a Blank project would only add a
    # second, confusing message - and only where Extron's templates are.
    # A table or template this cannot read is no evidence against the seed, and
    # New-GdlSeed.ps1 deletes a seed the verifier refuses or crashes on.
    screen = p.field(proj, 'screenSizeField')
    if skin and isinstance(screen, dict) and n_pages >= min_pages:
        try:
            if templates.table():
                probs += series_problems(pages, (screen['width'], screen['height']), model, skin)
        except Exception as e:  # noqa: BLE001 - whatever GUI Designer's files hold
            print(f"  note: the seed's series is not compared - {type(e).__name__}: {e}")
    return probs


def main(argv):
    if len(argv) not in (3, 4):
        print(__doc__.strip().split('\n\n')[0])
        return 2
    try:
        if not templates.table():
            print("  note: no TemplateInfoTable.config here, so the seed's series is not compared")
    except Exception:  # noqa: BLE001 - check_seed says why it cannot compare
        pass
    probs = check_seed(argv[1], argv[2], theme=argv[3] if len(argv) == 4 else None)
    for pr in probs:
        print('  PROBLEM ' + pr)
    print(f"{'ok' if not probs else f'{len(probs)} problem(s)'}: {argv[1]} as {argv[2]}")
    return 1 if probs else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
