"""The build-timing tools: the specs they generate and the table they read.

`tools/build_timing_specs.py` writes specs that differ from a base in one
count, and `tools/timing_table.py` reads the logs of `tools/Run-BuildTiming.ps1`
and fits what Save and Build's time scales with. Neither needs GUI Designer
(the builds that feed them do), so the arithmetic is pinned here: a spec has
the counts it was asked for and passes the spec check, a plan is counted the
way the table counts it, a log is read back, and the fit recovers a known line.

    python tests/test_build_timing.py
"""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'tools'))

import build_timing_specs as gen  # noqa: E402
import timing_table as table  # noqa: E402

from gdl.spec import Panel  # noqa: E402


class TestGeneratedSpecs(unittest.TestCase):
    def test_a_spec_has_the_counts_it_was_asked_for(self):
        spec, c = gen.make_spec('t', pages=3, controls=15, states=4, borders=2, faces=2)
        self.assertEqual(len(spec['pages']), 3)
        self.assertEqual(c['controls'], 45)
        self.assertEqual(sum(len(p['controls']) for p in spec['pages']), 45)
        buttons = [x for p in spec['pages'] for x in p['controls'] if x['kind'] == 'button']
        self.assertEqual(len(buttons), c['buttons'])
        self.assertTrue(all(len(b['states']) == 4 for b in buttons))
        # one state render for every state of a button and for any other control
        self.assertEqual(c['state_renders'], c['buttons'] * 4 + (c['controls'] - c['buttons']))
        self.assertEqual({b['border'] for b in buttons}, set(gen.BORDERS[:2]))
        self.assertEqual({x['font'] for p in spec['pages'] for x in p['controls'] if 'font' in x},
                         set(gen.FACES[:2]))

    def test_one_count_changes_and_the_others_do_not(self):
        _, base = gen.make_spec('b')
        _, more = gen.make_spec('m', pages=gen.BASE['pages'] * 2)
        self.assertEqual(more['controls'], 2 * base['controls'])
        self.assertEqual(more['borders'], base['borders'])
        _, st = gen.make_spec('s', states=8)
        self.assertEqual(st['controls'], base['controls'])
        self.assertGreater(st['state_renders'], base['state_renders'])

    def test_images_in_use_and_images_distinct_are_two_counts(self):
        spec, c = gen.make_spec('i', pages=2, img_uses=6, img_distinct=2, img_dir=os.path.join(os.sep, 'x'))
        self.assertEqual((c['images_used'], c['images_distinct']), (6, 2))
        self.assertEqual(len(spec['images']), 2)
        used = [x['image'] for p in spec['pages'] for x in p['controls'] if x.get('image')]
        self.assertEqual(len(used), 6)
        self.assertEqual(len(set(used)), 2)
        with self.assertRaises(ValueError):
            gen.make_spec('bad', img_uses=3, img_distinct=0)

    def test_a_page_that_does_not_fit_its_grid_is_refused(self):
        with self.assertRaises(ValueError):
            gen.make_spec('big', controls=200)

    def test_every_matrix_spec_passes_the_spec_check(self):
        """Except for the image ones, which name PNGs that are written on
        demand: those are checked with their PNGs (Pillow)."""
        with tempfile.TemporaryDirectory() as d:
            for name, kw in gen.MATRIX.items():
                if kw.get('img_uses'):
                    try:
                        import PIL  # noqa: F401
                    except ImportError:
                        continue
                row = gen.write_one(d, name, **kw)
                problems = Panel.load(row['spec']).check()
                self.assertEqual(problems, [], name)


PLAN = {
    'pages': [
        {'background_image': None, 'controls': [
            {'donor_type': 'PBShape', 'border': '2D Rectangle', 'font': {'name': 'Open Sans'}, 'states': None},
            {'donor_type': 'PBButton', 'border': 'A', 'font': {'name': 'Arial'},
             'image': {'name': 'x.png', 'file': None},
             'states': [{'name': 'Off', 'border': 'A', 'image': {'name': 'x.png'}},
                        {'name': 'On', 'border': 'B', 'image': {'name': 'y.png'}}]},
        ]},
    ],
    'popups': [{'controls': [{'donor_type': 'PBLabel', 'border': None, 'font': {'name': 'Arial'}, 'states': None}]}],
}

LOG = """\ufeffRUN r9
spec C:\\x\\base.json
started 2026-11-03T10:00:00.0000000-05:00
host settled after 12s (quiet=True, busy=21%, antivirus 0.10 cores), free memory 6,100 MB, antivirus CPU so far 66,000s

=== [8] File > Save and Build
  at 10:00:30, +30.0s
waiting for a build to rewrite r9.gdl (was 10:00:20, 2,540,705 bytes)
  rewritten at t+40.0s
build finished at t+48.0s, 2,700,000 bytes
SAVE_AND_BUILD click_to_written=100.5s menu_find=2.0s menu_invoke=65.7s wait_started=+65.7s written_at=10:02:10.500
LOAD save_and_build wall=110.0 gd_cpu=20.0 gd_cores=0.18 gd_write_mb=24.3 gd_read_mb=3.8 av_cpu=90.0 sys_busy_pct=39 gd_peak_mb=600 free_mb=5500 clock_pct=308

PANEL BUILT AND VERIFIED -> C:\\x\\r9.gdl
TIMING check 0.2
TIMING save_and_build 112.0
TIMING total 150.0

=== extra build 1 in the same GUI Designer session
  rewritten at t+30.0s
build finished at t+38.0s, 2,700,000 bytes
SAVE_AND_BUILD extra=1 click_to_written=95.0s menu_find=1.7s menu_invoke=65.6s wait_started=+65.6s written_at=10:03:50.000 ok=True
LOAD extra1 wall=100.0 gd_cpu=19.0 gd_cores=0.19 gd_write_mb=24.0 gd_read_mb=3.8 av_cpu=85.0 sys_busy_pct=40 gd_peak_mb=610 free_mb=5510
"""


class TestTable(unittest.TestCase):
    def test_a_plan_is_counted_by_what_it_builds(self):
        c = table.counts_of(PLAN)
        self.assertEqual((c['pages'], c['popups'], c['controls'], c['buttons']), (1, 1, 3, 1))
        self.assertEqual(c['state_renders'], 1 + 2 + 1)
        self.assertEqual(c['images_distinct'], 2)
        self.assertEqual(c['images_used'], 1)
        self.assertEqual(c['borders'], 3)         # 2D Rectangle, A, B
        self.assertEqual(c['faces'], 2)

    def test_a_log_is_read_back_build_by_build(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'r9.log'), 'w', encoding='utf-8') as fh:
                fh.write(LOG)
            with open(os.path.join(d, 'r9.plan.json'), 'w', encoding='utf-8') as fh:
                json.dump(PLAN, fh)
            rows = table.rows_of(d)
        self.assertEqual([r['build'] for r in rows], ['first', 'extra1'])
        first, extra = rows
        self.assertEqual(first['verified'], 'yes')
        self.assertEqual(first['click_to_written'], 100.5)
        self.assertEqual((first['wait_rewritten'], first['wait_finished']), (40.0, 48.0))
        self.assertEqual(first['t_total'], 150.0)
        self.assertEqual(first['av_cpu_s'], 90.0)
        self.assertEqual(first['settle_s'], 12.0)
        # the clock the build logged itself: 308 of the full 385
        self.assertEqual(first['clock_pct'], 308)
        self.assertEqual(first['t_full_clock'], round(100.5 * 308 / table.FULL_CLOCK, 1))
        self.assertEqual(extra['clock_pct'], '')
        self.assertEqual(extra['click_to_written'], 95.0)
        self.assertEqual((extra['wait_rewritten'], extra['wait_finished']), (30.0, 38.0))
        self.assertEqual(extra['t_total'], '')

    def test_the_fit_recovers_a_known_line(self):
        rows = [{'y': 60 + 2 * p + 0.5 * c + 0.1 * s, 'p': p, 'c': c, 's': s}
                for p, c, s in [(1, 15, 24), (6, 90, 144), (12, 180, 288), (23, 345, 552), (40, 600, 960),
                                (12, 60, 84), (12, 360, 600), (12, 720, 1212), (12, 180, 180), (12, 180, 936)]]
        beta, se, r2, sd, n = table.fit(rows, 'y', ['p', 'c', 's'])
        self.assertAlmostEqual(r2, 1.0, places=6)
        for got, want in zip(beta, (60, 2, 0.5, 0.1)):
            self.assertAlmostEqual(got, want, places=4)
        self.assertEqual(n, 10)

    def test_columns_that_do_not_vary_cannot_be_fitted(self):
        rows = [{'y': i, 'a': 1, 'b': 1} for i in range(6)]
        with self.assertRaises(ValueError):
            table.fit(rows, 'y', ['a', 'b'])


if __name__ == '__main__':
    unittest.main()
