"""A seed is a themed project for the model it claims - never a Blank one."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import verify_seed  # noqa: E402

SEEDS = os.path.join(os.path.dirname(HERE), 'seeds')


def _seed(name):
    path = os.path.join(SEEDS, name)
    if not os.path.exists(path) or os.path.getsize(path) < 1024:
        raise unittest.SkipTest(f'{name} is not pulled from Git LFS here')
    return path


class TestVerifySeed(unittest.TestCase):
    def test_a_real_seed_passes(self):
        self.assertEqual(verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP1035T'), [])

    def test_the_wrong_model_is_refused(self):
        probs = verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP725T')
        self.assertTrue(any('part number' in p for p in probs), probs)

    def test_a_blank_project_is_refused(self):
        """What the wizard makes when Blank is still the selected radio: one page
        and a handful of controls, and it reads as a seed by every other test."""
        probs = verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP1035T',
                                       min_pages=99)
        self.assertTrue(any('Blank' in p for p in probs), probs)


if __name__ == '__main__':
    unittest.main()
