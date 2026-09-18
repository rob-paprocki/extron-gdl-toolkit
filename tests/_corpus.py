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


SEEDS_DIR = _first_dir(_SEED_DIRS)
TEMPLATES_DIR = _first_dir(_TEMPLATE_DIRS)
