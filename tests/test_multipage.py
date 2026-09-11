"""More than one page per spec.

Every example and every test in this repo used exactly one page, while the real
client fixture has 27 - so page-to-page ID allocation, the thing a real panel
depends on most, had never been exercised at all. It turns out to work; these
tests are here so it keeps working, and so the gap is not silently reopened.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.spec import Panel  # noqa: E402

EXAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', 'examples', 'multipage.json')


def load():
    with open(EXAMPLE, encoding='utf-8') as fh:
        return Panel(json.load(fh))


class TestMultiplePages(unittest.TestCase):
    def test_the_example_has_more_than_one_page(self):
        """Guard the guard: this suite is pointless against a one-page spec."""
        self.assertGreater(len(load().pages), 1)

    def test_check_passes(self):
        self.assertEqual(load().check(), [])

    def test_every_page_reaches_the_plan(self):
        p = load()
        plan = p.plan()
        self.assertEqual(len(plan['pages']), len(p.pages))
        self.assertEqual([x['name'] for x in plan['pages']],
                         [x['name'] for x in p.pages])

    def test_control_ids_are_unique_across_pages_not_just_within_one(self):
        """The failure a one-page suite cannot see."""
        plan = load().plan()
        ids = [(op.get('fields') or {}).get('userIdField')
               for pg in plan['pages'] for op in pg['controls']]
        self.assertTrue(all(i is not None for i in ids))
        self.assertEqual(len(ids), len(set(ids)),
                         f'control userIds collide across pages: {ids}')

    def test_ids_are_banded_by_page_number(self):
        """1000 -> 1001.., 1100 -> 1101.., so an id says which page it is on."""
        for pg in load().plan()['pages']:
            base = pg['number']
            for op in pg['controls']:
                uid = (op.get('fields') or {}).get('userIdField')
                self.assertGreater(uid, base, f"{pg['name']}: {uid} <= {base}")
                self.assertLess(uid, base + 100,
                                f"{pg['name']}: {uid} is outside the {base} band")

    def test_page_numbers_are_distinct(self):
        nums = [pg['number'] for pg in load().plan()['pages']]
        self.assertEqual(len(nums), len(set(nums)))

    def test_a_name_repeated_across_pages_is_caught(self):
        """Page and popup names share one namespace project-wide."""
        spec = json.load(open(EXAMPLE, encoding='utf-8'))
        spec['pages'][1]['name'] = spec['pages'][0]['name']
        self.assertTrue(any('same name' in m or 'unique' in m
                            for m in Panel(spec).check()),
                        'a duplicate page name was not reported')


if __name__ == '__main__':
    unittest.main()
