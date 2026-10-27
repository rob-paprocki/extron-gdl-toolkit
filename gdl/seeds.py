"""Seeds: the themed projects a panel is built on (seeds/README.md).

A built panel is its seed's model, so every panel a canvas lists needs a seed of
its own - a 725 needs a 725 seed. A seed is made once, by driving GUI Designer's
Project Create Wizard (`powershell/New-GdlSeed.ps1`), and kept in Git LFS.
"""
import json
import os
import re
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LFS_POINTER = b'version https://git-lfs.github.com/spec/'
# The wizard names a panel by its family and the word Pro: 'TLP Pro 725T'.
_FAMILIES = ('ZRTP', 'TLP', 'TLC', 'TLI')
# seeds/ names a seed for its panel's size - the number, and the W of a wide one -
# not for its model: 'Afterburn 725.gdl', 'Afterburn 1230W.gdl'. The T, M or C of
# the form and the TG of the generation are in the seed's part number.
_SIZE = re.compile(r'^(?:ZRTP|TLP|TLC|TLI)(\d+W?)')
# The 300M is the one panel named whole, and both its seeds say which way up
# they were made. A seed of any other panel that rotates (gdl.spec.sizes) says
# so only at its second way up: 'Afterburn 1035.gdl', 'Mach 1035 Portrait.gdl'.
_WHOLE = {'TLP300M': '300M'}


def path(seed):
    """A seed path as a profile names it (repo-relative) -> where it is."""
    return seed if os.path.isabs(seed) else os.path.join(REPO, *seed.replace('\\', '/').split('/'))


def usable(seed):
    """A seed that is here: not missing, and not a Git LFS pointer left by a
    clone that skipped `git lfs pull`."""
    if not seed:
        return False
    p = path(seed)
    if not os.path.isfile(p):
        return False
    with open(p, 'rb') as fh:
        return not fh.read(len(_LFS_POINTER)).startswith(_LFS_POINTER)


def here():
    """Every seed in seeds/, named as a profile names one ('seeds/<file>.gdl')."""
    try:
        names = os.listdir(os.path.join(REPO, 'seeds'))
    except OSError:
        return []
    return [f'seeds/{n}' for n in sorted(names) if n.lower().endswith('.gdl')]


_FACTS = {}


def facts(seed):
    """What a seed is, by its own build: (theme, part number, canvas) as its
    layout.json gives them - or None for one that is not here or not built.
    Its name is not evidence: seeds/ names a seed for its size, and the 725T,
    725M and 725C are one size."""
    if not usable(seed):
        return None
    p = path(seed)
    key = (p, os.path.getmtime(p))
    if key not in _FACTS:
        from .container import open_payload
        try:
            j = json.loads(open_payload(p).read('layout.json'))
            got = ((j.get('Skin') or '').strip(), j.get('PartNumber'),
                   (j['ScreenSize']['width'], j['ScreenSize']['height']))
        except (KeyError, OSError, TypeError, ValueError, zipfile.BadZipFile):
            got = None
        _FACTS[key] = got
    return _FACTS[key]


def models_of(part):
    """The model(s) a part number is - the 1035T and 1035M are one."""
    from . import spec
    return ' or '.join(m for m in spec.MODELS_FULL if spec.part_number(m) == part) or part


def panel_type(model):
    """The Project Create Wizard's name for a model: TLP725T -> 'TLP Pro 725T'."""
    for fam in _FAMILIES:
        if model.startswith(fam):
            return f'{fam} Pro {model[len(fam):]}'
    return model


def _canvases(model, size):
    """(the canvas asked for, the model's default) - either None for a model
    GUI Designer does not build for."""
    from . import spec
    if model not in spec.MODELS_FULL:
        return None, None
    default = spec.sizes(model)[0]
    return (tuple(size) if size else default), default


# An ECP seed is named for the preset it was made in, by hand (seeds/README.md),
# not for a size and a way up.
_ECP = {(1920, 1080): 'ECP 16-9', (1280, 800): 'ECP 16-10'}


def default_path(theme, model, size=None):
    """Where a new seed is kept, as a profile names it: 'seeds/<Theme> <size>.gdl',
    with the way up where it is not the panel's default - or, for the 300M,
    always. `size` is the canvas, the model's default without one."""
    if model == 'VTLPEcp':
        return f"seeds/{theme} {_ECP[_canvases(model, size)[0]]}.gdl"
    m = _SIZE.match(model)
    name = _WHOLE.get(model) or (m.group(1) if m else model)
    return f"seeds/{theme} {name}{_way_up(model, size)}.gdl"


def _way_up(model, size):
    canvas, default = _canvases(model, size)
    if canvas and (model in _WHOLE or canvas != default):
        return ' Portrait' if canvas[1] > canvas[0] else ' Landscape'
    return ''


def new_path(theme, model, size=None):
    """Where a new seed of this panel is kept: default_path(), unless a seed of
    another panel already has that name - the TLP725T has 'Afterburn 725.gdl' -
    and then the whole model: 'Afterburn TLP725M.gdl'. New-GdlSeed.ps1 refuses
    to overwrite a seed, so the size's name alone would make nothing."""
    from . import spec
    p = default_path(theme, model, size)
    f = facts(p)
    canvas, _ = _canvases(model, size)
    if not f or (f[1], f[2]) == (spec.part_number(model), canvas):
        return p
    return f'seeds/{theme} {model}{_way_up(model, size)}.gdl'


def turned(theme, model, size):
    """Whether a seed of this panel is its own seed turned: `size` is the
    model's other way up, and the theme draws a template for it its default
    way and none this way - the 835M and 1035M portrait, which the wizard
    offers Blank alone (docs/design-rules.md section 1), and in Mach, which
    draws its 300 portrait alone, the 300M landscape. Afterburn's 300M is the
    wizard's either way up."""
    from . import templates
    canvas, default = _canvases(model, size)
    return bool(canvas and canvas != default and templates.table()
                and templates.template_for(theme, model)
                and not templates.template_for(theme, model, canvas))


def command(theme, model, seed, size=None):
    """The line that makes the seed, for a refusal to print. It is run from the
    repo root, as the script's own path is. A canvas other than the panel's
    default is passed on: the wizard's Resolution starts at the default. A
    panel turned where the theme draws no template (turned()) is its own seed
    turned by New-GdlTurnedSeed.ps1 - after that seed's own line, where it is
    not here either."""
    out = (seed or new_path(theme, model, size)).replace('/', '\\')
    canvas, default = _canvases(model, size)
    if turned(theme, model, size):
        own = pick(theme, model)
        src = (own or new_path(theme, model)).replace('/', '\\')
        turn = (f"powershell\\New-GdlTurnedSeed.ps1 -From '{src}' -Model {model} "
                f"-Resolution '{canvas[0]}x{canvas[1]}' -Output '{out}'")
        return turn if own else command(theme, model, None) + '\n  ' + turn
    line = (f"powershell\\New-GdlSeed.ps1 -PanelType '{panel_type(model)}' -Model {model} "
            f"-Theme '{theme}' -Output '{out}'")
    if canvas and canvas != default:
        line += f" -Resolution '{canvas[0]}x{canvas[1]}'"
    return line


def _profile(theme):
    """A theme family's design-system profile (gdl/designsys/), or None."""
    from . import designsys
    try:
        return designsys.load(theme.lower())
    except (OSError, ValueError):
        return None


def candidates(theme, model, size=None):
    """Where a spec of this theme family, model and canvas looks first for its
    seed: the family's profile - it lists each seed under the models it serves,
    whatever it is called ('Afterburn 835 (Project1).gdl') - then the name
    seeds/ gives a new one. A panel the profile has no row for that way up
    (gdl.spec.panel_id) is the name alone. pick() takes none of them on its
    name."""
    from . import designsys
    p = _profile(theme)
    if p:
        theme = p.get('template') or theme
    canvas, _ = _canvases(model, size)
    out = []
    if p:
        # The profile lists a panel either way up as its own (gdl.spec.panel_id).
        from . import spec
        try:
            row = designsys.models(p).get(spec.panel_id(model, canvas)) if canvas else None
        except ValueError:
            row = None
        if row and row.get('seed') and tuple(row['size']) == canvas:
            out.append(row['seed'])
        if p.get('model') == model and p.get('seed') and tuple(p.get('size') or ()) == canvas:
            out.append(p['seed'])
    out.append(default_path(theme, model, size))
    return list(dict.fromkeys(out))


def pick(theme, model, size=None):
    """The seed here that is this theme, model and canvas by its own build
    (facts()), or None - a seed to make (command() has the line). The
    candidates() are tried first, then every other seed in seeds/, so one named
    for its preset ('Afterburn ECP 16-9.gdl') is found too."""
    from . import spec
    canvas, _ = _canvases(model, size)
    if canvas is None:
        return None
    p = _profile(theme)
    want = ((p or {}).get('template') or theme).strip().casefold(), spec.part_number(model), canvas
    for c in dict.fromkeys(candidates(theme, model, size) + here()):
        f = facts(c)
        if f and (f[0].casefold(), f[1], f[2]) == want:
            return c
    return None


def listing(theme):
    """The step after making a seed, for translate: it reads a theme's profile,
    not seeds/, so the profile lists the seed under its series before translate
    uses it. pick() reads seeds/ itself and needs no listing."""
    return (f"for translate, list it too: its series' `seeds` in the `panels` of "
            f'gdl/designsys/{theme.lower()}.json (`python tests/measure_series.py {theme}` '
            f'measures the entry)')


def _families():
    from . import designsys
    names = [t.capitalize() for t in designsys.TEMPLATES]
    return ', '.join(names[:-1]) + ' or ' + names[-1]


def for_spec(spec):
    """(seed, None) for a spec that names its theme `family`, or (None, why).
    `why` says what will get it one: a family to name, seeds Git LFS left as
    pointers to pull, the line that makes the seed - the wizard's, or for a
    panel turned where no template is drawn that way up its own seed's turn
    (turned()) - or, where its theme draws no template for the panel either
    way up, so no themed seed can be made, a seed to retarget instead."""
    from . import spec as gdlspec, templates
    raw = spec.get('family')
    if not raw:
        return None, f'the spec names no "family" - {_families()} - to pick its seed by'
    p = _profile(raw.strip()) if isinstance(raw, str) else None
    if not p:
        return None, f'the spec\'s "family" {raw!r} is not a theme - it is one of {_families()}'
    model = spec.get('model')
    if model not in gdlspec.MODELS_FULL:
        return None, f'the spec names no model GUI Designer builds for ({model!r})'
    family = p.get('template') or raw.strip()
    size = tuple(spec['size']) if spec.get('size') else None
    canvas, _ = _canvases(model, size)
    if canvas not in gdlspec.sizes(model):
        return None, (f'a {model} runs at {" or ".join("%dx%d" % s for s in gdlspec.sizes(model))}, '
                      f'not {canvas[0]}x{canvas[1]}, so no seed is that canvas')
    seed = pick(family, model, size)
    if seed:
        return seed, None
    where = f'no {family} seed here for a {model} at {canvas[0]}x{canvas[1]}'
    left = [s for s in here() if not usable(s)]
    if left:
        return None, (f'{where} among the seeds pulled - {len(left)} in seeds/ are Git LFS '
                      f'pointers ({", ".join(left[:3])}{", ..." if len(left) > 3 else ""}): '
                      f'run `git lfs pull`, then pick again')
    named = facts(default_path(family, model, size))
    if named:
        where += f' ({default_path(family, model, size)} is a {models_of(named[1])})'
    if model in gdlspec.SOFT_CLIENTS:
        # The seed script drives the wizard for a touch panel; a soft panel's
        # seeds (the six ECP ones) were made in it by hand.
        return None, (f'{where} - pass -Donor a {family} project made for a {model} '
                      f'(seeds/README.md has how the ECP seeds were made)')
    if turned(family, model, size):
        return None, (f'{where} - GUI Designer draws no {family} template for a {model} that way '
                      f'up, so its seed is its own turned:\n  {command(family, model, None, size)}\n'
                      f'  {listing(family)}')
    if templates.table() and not templates.template_for(family, model, canvas):
        return None, (f'{where}, and none can be made: GUI Designer draws no {family} template '
                      f'for a {model} at {canvas[0]}x{canvas[1]}, so its wizard offers that panel '
                      f'Blank alone. Retarget a {family} seed to it and pass that as -Donor '
                      f'(python -m gdl.edit, docs/editing.md)')
    return None, (f'{where} - make one:\n  {command(family, model, None, size)}\n'
                  f'  {listing(family)}')


def main(argv):
    """python -m gdl.seeds pick <spec.json> - the seed a spec builds on."""
    import json
    if len(argv) != 3 or argv[1] != 'pick':
        print('python -m gdl.seeds pick <spec.json>')
        return 2
    with open(argv[2], encoding='utf-8') as fh:
        seed, why = for_spec(json.load(fh))
    print(seed or why)
    return 0 if seed else 1


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
