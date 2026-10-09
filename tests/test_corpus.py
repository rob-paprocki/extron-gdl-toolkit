"""A test that needs the client's files says so and skips where they are not."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _corpus  # noqa: E402


class TestNeedsClient(unittest.TestCase):
    def test_an_absent_client_file_skips_and_names_itself(self):
        @_corpus.needs_client('no-such-client-file.gdl')
        def t():
            raise AssertionError('ran without its fixture')
        with self.assertRaises(unittest.SkipTest) as e:
            t()
        self.assertIn('no-such-client-file.gdl', str(e.exception))
        self.assertIn('held back from the public copy', str(e.exception))

    def test_a_present_client_file_runs(self):
        if not _corpus.usable(_corpus.client(_corpus.MAIN_CLIENT)):
            self.skipTest('the client fixtures are not here')
        ran = []
        _corpus.needs_client(_corpus.MAIN_CLIENT)(lambda: ran.append(1))()
        self.assertEqual(ran, [1])


if __name__ == '__main__':
    unittest.main()
