"""tools/public_sync.py and tools/hooks/pre-push against throwaway repositories.

Each test makes a repository with two unrelated lines - an archive and a public one - and a
private/ folder of its own. This file is published through the tool, so the words it plants
are assembled at run time rather than written out.
"""
import contextlib
import gzip
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)

import public_sync as ps  # noqa: E402

os.environ.update({'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'noreply@example.com',
                   'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'noreply@example.com',
                   'GIT_CONFIG_NOSYSTEM': '1'})
WORD = 'Acme' + 'corp'                 # stands in for the client's name, two words run together
DENY = f'(?i){WORD[:4]}[ _-]?{WORD[4:]}'   # the shape of the real pattern: one optional separator
SECRET = 'hunter2' + '-xyzzy'          # stands in for a settings value
USER = 'ali' + 'ce'


def git(repo, *args, input=None):
    p = subprocess.run(['git', '-C', repo] + list(args), input=input, capture_output=True)
    assert p.returncode == 0, p.stderr.decode('utf-8', 'replace')
    return p.stdout.decode('utf-8', 'replace').strip()


def settings_file(value):
    return ('<?xml version="1.0" encoding="utf-8"?><configuration><userSettings><S>'
            f'<setting name="LastUsername" serializeAs="String"><value>{value}</value></setting>'
            '</S></userSettings></configuration>')


class Repo:
    """An archive line, a public line and a private/ folder, in a temporary repository."""

    def __init__(self, archive, private=True, secret=SECRET):
        self.dir = tempfile.mkdtemp(prefix='public-sync-test-')
        git(self.dir, 'init', '-q')
        git(self.dir, 'config', 'commit.gpgsign', 'false')
        self.public = self.commit('public', {'README.md': '# public\n'}, 'public start')
        self.archive = self.commit('archive', archive, 'archive work')
        if private:
            self.write('private/public-sync-denylist.txt', DENY + '\n')
            self.write('private/gui-designer/user-config/user.config', settings_file(secret))

    def write(self, path, data):
        full = os.path.join(self.dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as fh:
            fh.write(data if isinstance(data, bytes) else data.encode('utf-8'))

    def commit(self, branch, files, message):
        git(self.dir, 'checkout', '-q', '--orphan', branch)
        git(self.dir, 'rm', '-r', '-q', '--cached', '--ignore-unmatch', '.')
        for name in os.listdir(self.dir):
            if name not in ('.git', 'private'):
                p = os.path.join(self.dir, name)
                shutil.rmtree(p) if os.path.isdir(p) else os.unlink(p)
        for path, data in files.items():
            self.write(path, data)
            git(self.dir, 'add', '-f', path)
        git(self.dir, 'commit', '-q', '-m', message)
        return git(self.dir, 'rev-parse', 'HEAD')

    def lfs(self, content):
        """A Git LFS pointer to `content`, with the content put in the local store."""
        import hashlib
        oid = hashlib.sha256(content).hexdigest()
        store = os.path.join(git(self.dir, 'rev-parse', '--git-common-dir'), 'lfs', 'objects',
                             oid[:2], oid[2:4])
        store = store if os.path.isabs(store) else os.path.join(self.dir, store)
        os.makedirs(store, exist_ok=True)
        with open(os.path.join(store, oid), 'wb') as fh:
            fh.write(content)
        return (f'version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {len(content)}\n', oid, store)

    def run(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ps.main(['--repo', self.dir] + list(argv))
        return code, out.getvalue()

    def files(self, rev):
        return set(git(self.dir, 'ls-tree', '-r', '--name-only', rev).splitlines())

    def show(self, rev, path):
        return git(self.dir, 'show', f'{rev}:{path}')


def zip_bytes(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


class TestBuild(unittest.TestCase):
    def test_build_leaves_out_held_back_paths_and_keeps_public_ancestry(self):
        r = Repo({'README.md': '# toolkit\n', 'gdl/a.py': 'x = 1\n', 'fixtures/gdl/c.gdl': 'client\n',
                  'archive/claude/sessions/s.jsonl': '{}\n', 'archive/gdlwork/clean/wizard.png': 'png\n'})
        code, out = r.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 0, out)
        self.assertEqual(r.files('public-next'), {'README.md', 'gdl/a.py'})
        self.assertEqual(git(r.dir, 'rev-parse', 'public-next^'), r.public)
        p = subprocess.run(['git', '-C', r.dir, 'merge-base', '--is-ancestor', r.archive, 'public-next'])
        self.assertNotEqual(p.returncode, 0, 'archive history reached the public line')

    def test_the_first_build_has_no_parent(self):
        r = Repo({'README.md': '# toolkit\n'})
        code, out = r.run('build', '--archive', 'archive', '--first')
        self.assertEqual(code, 0, out)
        self.assertEqual(git(r.dir, 'rev-list', '--count', 'public-next'), '1')

    def test_home_paths_are_scrubbed(self):
        r = Repo({'notes.md': f'C:\\Users\\{USER}\\x.py and /c/Users/{USER}/y and C:\\Users\\Public\\z\n'})
        code, out = r.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 0, out)
        text = r.show('public-next', 'notes.md')
        self.assertNotIn(USER, text)
        self.assertIn('C:\\Users\\Public\\z', text)

    def test_the_client_name_refuses_a_build(self):
        r = Repo({'notes.md': f'built on the {WORD} project\n'})
        code, out = r.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 1, out)
        self.assertNotIn(WORD, out)          # reported masked, never echoed

    def test_a_settings_value_refuses_a_build(self):
        r = Repo({'notes.md': f'password {SECRET}\n'})
        code, out = r.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 1, out)
        self.assertNotIn(SECRET, out)

    def test_an_unreviewed_binary_is_refused_and_a_reviewed_one_passes(self):
        png = b'\x89PNG\r\n\x1a\n\x00\x00binary'
        with mock.patch.dict(ps.BINARY_OK, {'docs/panel-preview.png': hashlib.sha256(png).hexdigest()}):
            ok = Repo({'docs/panel-preview.png': png})
            self.assertEqual(ok.run('build', '--archive', 'archive', '--public', 'public')[0], 0)
            bad = Repo({'docs/other.png': png})
            code, out = bad.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 1, out)
        self.assertIn('not reviewed', out)

    def test_a_reviewed_binary_whose_bytes_changed_is_refused(self):
        # The list pins what a person looked at, not a path: a regenerated image is looked at again.
        png = b'\x89PNG\r\n\x1a\n\x00\x00binary'
        with mock.patch.dict(ps.BINARY_OK, {'docs/panel-preview.png': hashlib.sha256(png).hexdigest()}):
            r = Repo({'docs/panel-preview.png': png + b'changed'})
            code, out = r.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 1, out)
        self.assertIn('changed since it was reviewed', out)

    def test_build_refuses_a_public_parent_on_the_archive_line(self):
        r = Repo({'README.md': '# toolkit\n'})
        code, out = r.run('build', '--archive', 'archive', '--public', 'archive')
        self.assertEqual(code, 1, out)
        self.assertIn('shares history with the archive', out)

    def test_build_will_not_move_an_archive_branch(self):
        r = Repo({'README.md': '# toolkit\n'})
        code, out = r.run('build', '--archive', 'archive', '--first', '--branch', 'archive')
        self.assertEqual(code, 1, out)
        self.assertEqual(git(r.dir, 'rev-parse', 'archive'), r.archive)


class TestCheckSeesInside(unittest.TestCase):
    def test_lfs_content_is_checked(self):
        r = Repo({'README.md': '# x\n'})
        pointer, _, _ = r.lfs(zip_bytes({'ProjectGCP': f'project of {WORD}'.encode()}))
        r.commit('lfs', {'archive/gdlwork/x/project1.tgz4': pointer}, 'lfs')
        code, out = r.run('check', 'lfs')
        self.assertEqual(code, 1, out)

    def test_lfs_content_missing_locally_is_refused(self):
        r = Repo({'README.md': '# x\n'})
        pointer, oid, store = r.lfs(b'anything')
        os.unlink(os.path.join(store, oid))
        r.commit('lfs', {'seeds/S.gdl': pointer}, 'lfs')
        code, out = r.run('check', 'lfs')
        self.assertEqual(code, 1, out)
        self.assertIn('not in the local LFS store', out)

    def test_a_word_inside_a_deflated_member_is_found(self):
        tgz4 = zip_bytes({'layout.json': f'{{"Name": "{WORD} Boardroom"}}'.encode()})
        gdl = bytearray(zip_bytes({'ProjectGCP': b'x', 'p.tgz4': tgz4}))
        gdl = bytes(gdl).replace(b'PK\x03\x04', b'KP\x03\x04').replace(b'PK\x01\x02', b'KP\x01\x02') \
                        .replace(b'PK\x05\x06', b'KP\x05\x06')
        r = Repo({'archive/gdlwork/x/project1.tgz4': tgz4, 'archive/gdlwork/x/X.gdl': gdl})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count('private denylist'), 2, out)

    def test_a_utf16_secret_in_a_project_stream_is_found(self):
        r = Repo({'archive/gdlwork/x/ProjectGCP': b'\x00\x01' + SECRET.encode('utf-16-le') + b'\x00'})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)

    def test_check_history_finds_a_held_back_path_in_an_ancestor(self):
        r = Repo({'fixtures/gdl/c.gdl': 'client\n'})
        git(r.dir, 'checkout', '-q', 'archive')
        git(r.dir, 'rm', '-q', 'fixtures/gdl/c.gdl')
        git(r.dir, 'commit', '-q', '-m', 'drop it')
        self.assertEqual(r.run('check', 'archive')[0], 0)
        self.assertEqual(r.run('check', '--history', 'archive')[0], 1)

    def test_check_history_stops_at_the_first_commit_that_fails(self):
        # Refusing the archive line must not take a full check of every commit: one is enough.
        r = Repo({'fixtures/gdl/a.gdl': 'client\n'})
        git(r.dir, 'checkout', '-q', 'archive')
        r.write('fixtures/gdl/b.gdl', 'client\n')
        git(r.dir, 'add', '-f', 'fixtures/gdl/b.gdl')
        git(r.dir, 'commit', '-q', '-m', 'more')
        code, out = r.run('check', '--history', 'archive')
        self.assertEqual(code, 1, out)
        self.assertNotIn('a.gdl: held-back path present (in', out)
        self.assertIn('stopped at the first commit that fails', out)


class TestCheckIsNotFooled(unittest.TestCase):
    def test_a_name_split_by_a_line_wrap_or_a_comment_marker_is_found(self):
        a, b = WORD[:4], WORD[4:]
        for text in (f'built for {a}\n{b} last year\n', f'x = 1  # for {a}\n        # {b}\n'):
            r = Repo({'notes.md': text})
            code, out = r.run('check', 'archive')
            self.assertEqual(code, 1, (text, out))
            self.assertNotIn(b, out)

    def test_a_name_in_a_path_is_found_and_not_echoed(self):
        r = Repo({f'docs/{WORD}-notes.md': 'nothing here\n'})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertNotIn(WORD, out)

    def test_a_short_settings_value_is_never_echoed(self):
        short = 'zq' + 'x9k'
        r = Repo({'notes.md': f'code {short} here\n'}, secret=short)
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertNotIn(short[:3], out)
        self.assertNotIn(short[-2:], out)

    def test_a_utf16_value_at_an_odd_offset_is_found(self):
        r = Repo({'archive/gdlwork/x/ProjectGCP': b'\x00' + SECRET.encode('utf-16-le') + b'\x00'})
        self.assertEqual(r.run('check', 'archive')[0], 1)

    def test_a_nul_past_the_first_8k_still_makes_a_file_binary(self):
        r = Repo({'notes.txt': b'a' * 9000 + SECRET.encode('utf-16-le')})
        self.assertEqual(r.run('check', 'archive')[0], 1)

    def test_a_container_that_does_not_open_is_refused(self):
        r = Repo({'archive/gdlwork/x/shot.tgz4': b'\x89PNG\r\n\x1a\n\x00\x00not a zip'})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertIn('does not open', out)

    def test_a_zip_or_gzip_member_under_any_name_is_opened(self):
        for inner in (zip_bytes({'layout.json': WORD.encode()}), gzip.compress(WORD.encode() * 3)):
            r = Repo({'archive/gdlwork/x/project1.tgz4': zip_bytes({'assets.bin': inner})})
            self.assertEqual(r.run('check', 'archive')[0], 1)

    def test_held_back_paths_match_in_any_case(self):
        r = Repo({'README.md': '# x\n', 'Fixtures/gdl/c.gdl': 'client\n',
                  'ARCHIVE/claude/Sessions/s.jsonl': '{}\n'})
        code, out = r.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 0, out)
        self.assertEqual(r.files('public-next'), {'README.md'})

    def test_a_tag_message_is_checked(self):
        r = Repo({'README.md': '# x\n'})
        git(r.dir, 'tag', '-a', 'v1', '-m', f'for {WORD}', 'archive')
        self.assertEqual(r.run('check', 'v1')[0], 1)

    def test_a_flattened_folder_name_outside_home_and_checkouts_is_refused(self):
        # Claude Code names a project folder after its path, so a job site's folder shows up flattened.
        d = 'C'
        bad = Repo({'notes.md': f'see {d}--Remote-Site-Room--claude-worktrees-x\n'})
        self.assertEqual(bad.run('check', 'archive')[0], 1)
        ok = Repo({'notes.md': f'see {d}--Users-{USER}-git and Z--GitHub-owner\n'})
        code, out = ok.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 0, out)


class TestPrivateFiles(unittest.TestCase):
    """Without what private/ holds the check refuses to run: it never passes blind."""
    DENY_FILE = 'private/public-sync-denylist.txt'
    SETTINGS = 'private/gui-designer/user-config/user.config'

    def refused(self, r, names):
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 2, out)
        self.assertIn(names, out)
        return out

    def test_without_the_denylist(self):
        r = Repo({'README.md': '# x\n'})
        os.unlink(os.path.join(r.dir, self.DENY_FILE))
        self.refused(r, 'denylist')

    def test_without_the_settings_file(self):
        r = Repo({'README.md': '# x\n'})
        os.unlink(os.path.join(r.dir, self.SETTINGS))
        self.refused(r, 'user.config')

    def test_with_a_denylist_of_comments_only(self):
        r = Repo({'README.md': '# x\n'})
        r.write(self.DENY_FILE, '# only a comment\n\n')
        self.refused(r, 'denylist')

    def test_with_a_settings_file_that_yields_no_values(self):
        r = Repo({'README.md': '# x\n'})
        r.write(self.SETTINGS, settings_file(''))
        self.refused(r, 'user.config')

    def test_with_a_denylist_line_that_does_not_compile(self):
        r = Repo({'README.md': '# x\n'})
        r.write(self.DENY_FILE, DENY + '\n(unclosed\n')
        out = self.refused(r, 'line 2')
        self.assertNotIn('unclosed', out)

    def test_a_denylist_saved_with_a_bom_still_matches(self):
        r = Repo({'notes.md': f'built on the {WORD} project\n'})
        r.write(self.DENY_FILE, ('\ufeff' + DENY + '\n').encode('utf-8'))
        self.assertEqual(r.run('check', 'archive')[0], 1)


class TestHook(unittest.TestCase):
    def setUp(self):
        if not shutil.which('sh') or not shutil.which('git-lfs'):
            self.skipTest('needs sh and git-lfs on PATH')

    def test_the_hook_refuses_an_archive_branch_pushed_to_public(self):
        r = Repo({'README.md': '# x\n', 'fixtures/gdl/c.gdl': 'client\n'})
        bare = tempfile.mkdtemp(prefix='public-remote-')
        git(bare, 'init', '-q', '--bare')
        git(r.dir, 'remote', 'add', 'public', bare)
        hooks = os.path.join(r.dir, git(r.dir, 'rev-parse', '--git-common-dir'), 'hooks')
        shutil.copy(os.path.join(REPO, 'tools', 'hooks', 'pre-push'), os.path.join(hooks, 'pre-push'))
        env = dict(os.environ, PUBLIC_SYNC=os.path.join(REPO, 'tools', 'public_sync.py'))
        p = subprocess.run(['git', '-C', r.dir, 'push', 'public', 'archive:main'], env=env,
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('fails the publish check', p.stderr)
        self.assertEqual(git(bare, 'for-each-ref'), '', 'something reached the public remote')
        code, out = r.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 0, out)
        p = subprocess.run(['git', '-C', r.dir, 'push', 'public', 'public-next:main'], env=env,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_the_hook_checks_a_push_to_any_remote_but_the_archive(self):
        # Another name for the public repository, or a URL spelled differently, is still checked:
        # only the archive itself (origin) is exempt.
        r = Repo({'README.md': '# x\n', 'fixtures/gdl/c.gdl': 'client\n'})
        mirror, origin = tempfile.mkdtemp(prefix='mirror-'), tempfile.mkdtemp(prefix='origin-')
        for bare in (mirror, origin):
            git(bare, 'init', '-q', '--bare')
        git(r.dir, 'remote', 'add', 'mirror', mirror)
        git(r.dir, 'remote', 'add', 'origin', origin)
        hooks = os.path.join(r.dir, git(r.dir, 'rev-parse', '--git-common-dir'), 'hooks')
        shutil.copy(os.path.join(REPO, 'tools', 'hooks', 'pre-push'), os.path.join(hooks, 'pre-push'))
        env = dict(os.environ, PUBLIC_SYNC=os.path.join(REPO, 'tools', 'public_sync.py'))
        p = subprocess.run(['git', '-C', r.dir, 'push', 'mirror', 'archive:main'], env=env,
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(git(mirror, 'for-each-ref'), '', 'something reached the other remote')
        p = subprocess.run(['git', '-C', r.dir, 'push', 'origin', 'archive:main'], env=env,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class TestTheRealRepository(unittest.TestCase):
    def test_settings_values_are_read_from_the_owners_file(self):
        if not os.path.isfile(os.path.join(REPO, ps.SETTINGS_FILE)):
            self.skipTest('the settings file is on the owner machine only')
        values = ps.load_secrets(REPO)
        # e-mail, username, password, key, number, owner - some may be the same value
        self.assertGreaterEqual(len(values), 4)
        self.assertTrue(all(len(v) >= 4 for v in values))

    def test_the_tool_and_this_file_publish_unchanged(self):
        for path in ('tools/public_sync.py', 'tests/test_public_sync.py'):
            with open(os.path.join(REPO, path), encoding='utf-8') as fh:
                text = fh.read()
            self.assertEqual(ps.scrub_text(text), text, path)


if __name__ == '__main__':
    unittest.main()
