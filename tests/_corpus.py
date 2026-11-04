"""Where the corpus lives: this repo first, the GUI Designer install second.

Tests used to address the seeds and Extron's templates by absolute C: paths, so
they only ran on a machine with GUI Designer installed and silently skipped
everywhere else. The files now live in the repo:

  seeds/                          one themed project per theme/size, in Git LFS
  vendor/extron/TouchLink Templates/   Extron's 50 .glt templates, local only

and the install paths are the fallback. A clone that has not run
`git lfs pull` holds 130-byte pointer files where the seeds should be, which
Project.open() would choke on - so `usable()` treats a pointer as absent and the
test skips instead of erroring.
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SEED_DIRS = (
    os.path.join(REPO, 'seeds'),
    'C:/Users/Public/Documents/Extron/GUI Designer',
)
_TEMPLATE_DIRS = (
    os.path.join(REPO, 'vendor', 'extron', 'TouchLink Templates'),
    'C:/Users/Public/Documents/Extron/GUI Designer Templates/TouchLink Templates',
)

_LFS_POINTER = b'version https://git-lfs.github.com/spec/'


def usable(path):
    """A real file on disk - not missing, and not an un-pulled LFS pointer."""
    if not path or not os.path.isfile(path):
        return False
    with open(path, 'rb') as fh:
        return fh.read(len(_LFS_POINTER)) != _LFS_POINTER


def _first_file(dirs, name):
    for d in dirs:
        p = os.path.join(d, name)
        if usable(p):
            return p
    # Nothing usable: name the preferred location so a skip message says where
    # the file was expected rather than pointing at an install path.
    return os.path.join(dirs[0], name)


def _first_dir(dirs):
    for d in dirs:
        if os.path.isdir(d):
            return d
    return dirs[0]


def seed(name):
    """A seed project by file name, e.g. seed('Afterburn 1035.gdl')."""
    return _first_file(_SEED_DIRS, name)


def template(name):
    """One of Extron's .glt templates, e.g. template('Afterburn 1020 Series.glt')."""
    return _first_file(_TEMPLATE_DIRS, name)


# The synthetic fixture: a project of generic words built by the toolkit on the
# Afterburn 1035 seed, and GUI Designer's own snapshots of it
# (tests/data/synthetic/README.md) - the one built project the suite reads, and
# the render baseline. Plain git, in the public copy too, so what runs on it
# runs everywhere.
SYNTHETIC_DIR = os.path.join(REPO, 'tests', 'data', 'synthetic')
SYNTHETIC = os.path.join(SYNTHETIC_DIR, 'synthetic.gdl')
SYNTHETIC_SPEC = os.path.join(SYNTHETIC_DIR, 'synthetic.json')
SYNTHETIC_SNAPSHOTS = os.path.join(SYNTHETIC_DIR, 'snapshots', 'Individual')
# The render baseline: tests/score.py's record of the synthetic fixture.
BASELINE = os.path.join(REPO, 'tests', 'baseline-synthetic.json')


def needs_synthetic(path=SYNTHETIC):
    """Skip a test or class unless the synthetic fixture's build is here, naming
    where it was looked for. `path` is for the test of this gate."""
    import unittest
    return unittest.skipUnless(usable(path), f'{path} is not here - build it with '
                                             f'tests/data/synthetic/README.md')


SEEDS_DIR = _first_dir(_SEED_DIRS)
TEMPLATES_DIR = _first_dir(_TEMPLATE_DIRS)
