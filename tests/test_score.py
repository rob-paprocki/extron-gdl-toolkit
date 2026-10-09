"""The render harness refuses snapshots that are not of the .gdl it is given.

Snapshots were matched to pages by number alone, and refused only when more
than half matched nothing. The TLP1035-1.1.0 fixture matched 14 of the 27
`_alt 2_0_0` snapshots - two of them pages since renamed - and scored 5.86%, a
figure that stood in the ROADMAP for a month as an unexplained render residual.
A snapshot's file is named for its page, so the name is checked too.
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import MAIN_CLIENT, needs_client  # noqa: E402
sys.path.insert(0, os.path.dirname(HERE))

FIXTURE = os.path.join(os.path.dirname(HERE), 'fixtures', 'gdl',
                       'client-boardroom-2.0.0.gdl')
SNAPS = os.path.join(os.path.dirname(HERE), 'fixtures', 'snapshots', 'Individual')
HOME = '1000 - Home_Id21.png'


@needs_client(MAIN_CLIENT)
class TestTheWrongFixtureIsRefused(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not installed; the harness renders with it')
        import score
        self.score = score
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_a_snapshot_of_a_page_by_another_name_is_refused(self):
        shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, '1000 - Lobby_Id21.png'))
        with self.assertRaises(SystemExit) as e:
            self.score.record(FIXTURE, self.dir)
        self.assertIn('1000 - Lobby', str(e.exception))

    def test_the_snapshots_own_fixture_is_scored(self):
        shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, HOME))
        self.assertEqual(list(self.score.record(FIXTURE, self.dir)), [HOME])

    def test_the_per_page_harness_refuses_it_too_and_counts_every_snapshot(self):
        """compare_snapshots.py left a renamed snapshot out of both counts, so
        the 1.1.0 fixture was refused as '13 of 25' missing - of 27 files -
        before the names were ever compared. One page scored, one renamed and
        two that match nothing is the same mix, smaller."""
        import subprocess
        shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, HOME))
        shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, '1000 - Lobby_Id21.png'))
        for n in (9998, 9999):
            shutil.copy(os.path.join(SNAPS, HOME), os.path.join(self.dir, f'Gone_Id{n}.png'))
        r = subprocess.run([sys.executable, os.path.join(HERE, 'compare_snapshots.py'), FIXTURE, self.dir],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('1000 - Lobby', r.stdout)
        self.assertNotIn(' of 3 ', r.stdout)


if __name__ == '__main__':
    unittest.main()
