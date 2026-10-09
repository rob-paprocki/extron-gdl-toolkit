"""Seeds: the themed projects a panel is built on (seeds/README.md).

A built panel is its seed's model, so every panel a canvas lists needs a seed of
its own - a 725 needs a 725 seed. A seed is made once, by driving GUI Designer's
Project Create Wizard (`powershell/New-GdlSeed.ps1`), and kept in Git LFS.
"""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LFS_POINTER = b'version https://git-lfs.github.com/spec/'
# The wizard names a panel by its family and the word Pro: 'TLP Pro 725T'.
_FAMILIES = ('ZRTP', 'TLP', 'TLC', 'TLI')
# seeds/ names a seed for its panel's size - the number, and the W of a wide one -
# not for its model: 'Afterburn 725.gdl', 'Afterburn 1230W.gdl'. The T, M or C of
# the form and the TG of the generation are in the seed's part number.
_SIZE = re.compile(r'^(?:ZRTP|TLP|TLC|TLI)(\d+W?)')
# The 300M is the one panel named whole, and its seeds say which way up they
# were made. The model is the portrait canvas, so that is the name; the
# landscape seed is named by hand.
_NAMED = {'TLP300M': '300M Portrait'}


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


def panel_type(model):
    """The Project Create Wizard's name for a model: TLP725T -> 'TLP Pro 725T'."""
    for fam in _FAMILIES:
        if model.startswith(fam):
            return f'{fam} Pro {model[len(fam):]}'
    return model


def default_path(theme, model):
    """Where a new seed is kept, as a profile names it: 'seeds/<Theme> <size>.gdl'."""
    m = _SIZE.match(model)
    return f"seeds/{theme} {_NAMED.get(model) or (m.group(1) if m else model)}.gdl"


def command(theme, model, seed):
    """The line that makes the seed, for a refusal to print. It is run from the
    repo root, as the script's own path is."""
    out = (seed or default_path(theme, model)).replace('/', '\\')
    return (f"powershell\\New-GdlSeed.ps1 -PanelType '{panel_type(model)}' -Model {model} "
            f"-Theme '{theme}' -Output '{out}'")


def listing(theme):
    """The step after making a seed. Translate reads a theme's profile, not
    seeds/, so the profile has to list the seed under its series before it is
    used."""
    return (f"then list it: its series' `seeds` in the `panels` of gdl/designsys/{theme.lower()}.json "
            f'(`python tests/measure_series.py {theme}` measures the entry, and the whole table '
            f'for a theme that has none yet)')
