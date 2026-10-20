"""The extron-panel skill is registered twice: by the root SKILL.md, the
procedure's home, and by .claude/skills/extron-panel/SKILL.md, the copy Claude
Code loads in this repository. Their trigger text has to be one text, or an edit
to the root changes nothing Claude Code sees."""
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def frontmatter(path):
    """The `key: value` lines between a file's opening `---` fences."""
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().split('\n')
    if lines[0].strip() != '---':
        return {}
    end = lines.index('---', 1)
    return dict(l.split(': ', 1) for l in lines[1:end] if ': ' in l)


class TestSkill(unittest.TestCase):
    def test_the_registered_skill_triggers_as_the_root_one_says(self):
        root = frontmatter(os.path.join(REPO, 'SKILL.md'))
        shim = frontmatter(os.path.join(REPO, '.claude', 'skills', 'extron-panel', 'SKILL.md'))
        self.assertEqual(root.get('name'), 'extron-panel')
        self.assertTrue(root.get('description'))
        self.assertEqual(shim, root)


if __name__ == '__main__':
    unittest.main()
