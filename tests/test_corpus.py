"""A test that needs a file the checkout lacks says so and skips.

The synthetic fixture is plain git, but a checkout can still be without its
build (one made before it, or a sparse one), and a seed that was never pulled
from Git LFS is a 130-byte pointer that Project.open() would choke on. Either
is a skip that names the file, never an error and never a silent pass.
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _corpus  # noqa: E402


class TestNeedsSynthetic(unittest.TestCase):
    def test_an_absent_build_skips_and_names_itself(self):
        @_corpus.needs_synthetic(os.path.join(HERE, 'no-such-build.gdl'))
        def t():
            raise AssertionError('ran without its build')
        with self.assertRaises(unittest.SkipTest) as e:
            t()
        self.assertIn('no-such-build.gdl', str(e.exception))
        self.assertIn('tests/data/synthetic/README.md', str(e.exception))

    def test_the_build_that_is_here_runs(self):
        if not _corpus.usable(_corpus.SYNTHETIC):
            self.skipTest(f'{_corpus.SYNTHETIC} is not here')
        ran = []
        _corpus.needs_synthetic()(lambda: ran.append(1))()
        self.assertEqual(ran, [1])


class TestAnUnpulledSeed(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def _write(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, 'wb') as fh:
            fh.write(data)
        return path

    def test_an_lfs_pointer_is_not_usable(self):
        pointer = self._write('Seed.gdl', _corpus._LFS_POINTER + b'\noid sha256:0\nsize 1\n')
        self.assertFalse(_corpus.usable(pointer))
        self.assertTrue(_corpus.usable(self._write('Real.gdl', b'KP\x03\x04 a project')))
        self.assertFalse(_corpus.usable(os.path.join(self.dir, 'missing.gdl')))
        self.assertFalse(_corpus.usable(None))

    def test_a_seed_found_nowhere_names_where_it_was_expected(self):
        """So a skip message points at seeds/, not at an install path."""
        self.assertEqual(_corpus.seed('No Such Seed.gdl'),
                         os.path.join(_corpus.REPO, 'seeds', 'No Such Seed.gdl'))


if __name__ == '__main__':
    unittest.main()
