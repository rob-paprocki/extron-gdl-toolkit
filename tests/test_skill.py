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


class TestSkillNamesTheCanvasWorkflow(unittest.TestCase):
    """Both files send a reader to the canvas workflow's pieces, by name. A
    renamed command or a dropped doc section is a pointer that stops working
    without anything failing, so the names and the places they point are held."""

    # `call`, `select` and `help` are ordinary English, so the roles are held as
    # the quoted words a reader copies, not as substrings of the prose.
    NAMES = ('Header', 'LeftRail', 'RightRail', 'Footer', 'Center',
             '`role`', '`source`', '`call`', '`dialer`', '`select`', '`help`',
             '`settings`', '`confirm`', '`topic`',
             'gdl.design', 'compare', '--template', 'New-GdlPanels.ps1', 'Windows')

    def read(self, *parts):
        with open(os.path.join(REPO, *parts), encoding='utf-8') as fh:
            return fh.read()

    def test_the_root_skill_and_the_registered_one_name_them(self):
        for where in (('SKILL.md',), ('.claude', 'skills', 'extron-panel', 'SKILL.md')):
            text = self.read(*where)
            for name in self.NAMES:
                with self.subTest(file=where[-1] if len(where) == 1 else '/'.join(where), name=name):
                    self.assertIn(name, text)

    def test_the_root_skill_names_the_waits_and_the_canvas_doc_grammar_for_them(self):
        skill = self.read('SKILL.md')
        for word in ('`up`', '`down`', '`power`'):
            with self.subTest(word=word):
                self.assertIn(word, skill)
        # The doc it sends a reader to is where `wait` and its topics are defined.
        design = self.read('docs', 'claude-design.md')
        for form in ('`wait` with `topic="up"`', '`"down"`'):
            with self.subTest(form=form):
                self.assertIn(form, design)

    def test_the_root_skill_names_a_revision(self):
        self.assertIn('--previous', self.read('SKILL.md'))
        self.assertIn('--previous', self.read('.claude', 'skills', 'extron-panel', 'SKILL.md'))

    def test_what_they_point_at_is_still_there(self):
        design = self.read('docs', 'claude-design.md')
        for heading in ('## 3. Components that say what they are', '## 4. What a canvas means'):
            self.assertIn(heading, design)
        self.assertIn('--template', design)
        self.assertIn('## 9. A revision', self.read('docs', 'idmap.md'))
        self.assertTrue(os.path.isfile(os.path.join(REPO, 'powershell', 'New-GdlPanels.ps1')))
        # The flags the skill names are ones the translator reads.
        translator = self.read('gdl', 'design.py')
        for flag in ('--previous', '--template'):
            self.assertIn(flag, translator)


if __name__ == '__main__':
    unittest.main()
