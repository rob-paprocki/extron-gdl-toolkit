"""tools/public_sync.py and tools/hooks/pre-push against throwaway repositories.

Each test makes a repository with two unrelated lines - an archive and a public one - and a
private/ folder of its own. This file is published through the tool, so the words it plants
are assembled at run time rather than written out.
"""
import contextlib
import gzip
import hashlib
import io
import json
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
# A BinaryFormatter stream's header as GUI Designer writes a ProjectGCP's: record type 0, root
# id 1, header id -1, version 1.0 - whose first four bytes are TrueType's 00 01 00 00.
GRAPH_HEADER = bytes([0, 1, 0, 0, 0, 255, 255, 255, 255, 1, 0, 0, 0, 0, 0, 0, 0])


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
        # fixtures/ and archive/gdlwork/ are deleted: their files here are copies restored
        # from the archive's history, which must not publish either.
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

    def test_every_reviewed_version_of_a_binary_passes(self):
        # A regenerated image keeps the version it replaced on the list, so the published history,
        # which still holds that version, checks clean; a version nobody looked at is refused.
        old, new = b'\x89PNG\r\n\x1a\n\x00\x00old', b'\x89PNG\r\n\x1a\n\x00\x00new'
        both = (hashlib.sha256(new).hexdigest(), hashlib.sha256(old).hexdigest())
        with mock.patch.dict(ps.BINARY_OK, {'docs/panel-preview.png': both}):
            for png in (old, new):
                r = Repo({'docs/panel-preview.png': png})
                self.assertEqual(r.run('build', '--archive', 'archive', '--public', 'public')[0], 0)
            r = Repo({'docs/panel-preview.png': new + b'changed'})
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


def a_font(family, pad=4000, magic=0x00010000):
    """A TrueType file of a name table naming `family` and a table of padding: enough of a font
    for gdl.sfnt to read its names. `magic` makes it an OpenType/CFF one (0x4F54544F, 'OTTO')."""
    import struct
    s = family.encode('utf-16-be')
    tables = [(b'name', struct.pack('>HHH', 0, 1, 18) + struct.pack('>6H', 3, 1, 0x409, 1, len(s), 0) + s),
              (b'zzzz', bytes(range(256)) * (pad // 256))]
    off, entries, body = 12 + 16 * len(tables), b'', b''
    for tag, data in tables:
        entries += struct.pack('>4sIII', tag, 0, off + len(body), len(data))
        body += data + b'\0' * (-len(data) % 4)
    return struct.pack('>IHHHH', magic, len(tables), 0, 0, 0) + entries + body


def sha(data):
    return hashlib.sha256(data).hexdigest()


def wrapped(text, width):
    return '\n'.join(text[i:i + width] for i in range(0, len(text), width))


class TestFontsAreAnAllowlist(unittest.TestCase):
    """Only a font whose bytes FONT_OK pins publishes, and Extron's faces never are: they carry no
    license grant, and the design systems embed them in every bundle they build. As a file of any
    font format, whatever BINARY_OK says or its name table names, and encoded in a text however
    the encoding is wrapped, cut into strings or escaped (FONT_OK's comment says what is read).
    Every face here is made at run time: this file publishes through the same check."""

    FACE = a_font('Extron-Lift')
    B64 = __import__('base64').b64encode(FACE).decode()

    def build(self, files):
        return Repo(files).run('build', '--archive', 'archive', '--public', 'public')

    def found(self, text):
        return [name for _, name in ps.fonts_in_text(text)]

    # -- as a file ---------------------------------------------------------------------------
    def test_a_font_file_is_refused_whatever_binary_ok_or_its_names_say(self):
        """The reviewer's: a renamed name table, a WOFF2 and a collection (no names read here)
        pinned in BINARY_OK all passed. Any font is refused - by its first four bytes, so whatever
        its file is called."""
        faces = {'gdl/fonts/extron-lift.ttf': self.FACE,
                 'gdl/fonts/renamed.ttf': a_font('Nothing To See'),
                 'gdl/fonts/cff.otf': a_font('Extron-Lift', magic=0x4F54544F),
                 'gdl/fonts/face.woff2': b'wOF2\x00\x01\x00\x00' + bytes(range(256)) * 16,
                 'gdl/fonts/faces.ttc': b'ttcf\x00\x01\x00\x00' + bytes(range(256)) * 16,
                 'docs/not-a-font.png': self.FACE,
                 'docs/no-extension': self.FACE}
        for path, face in faces.items():
            with self.subTest(path=path):
                with mock.patch.dict(ps.BINARY_OK, {path: sha(face)}):
                    code, out = self.build({path: face})
                self.assertEqual(code, 1, out)
                self.assertIn('font not reviewed (FONT_OK', out)
                self.assertIn('whatever BINARY_OK says', out)

    def test_a_font_file_font_ok_pins_publishes(self):
        face = b'wOF2\x00\x01\x00\x00' + bytes(range(256)) * 16
        with mock.patch.dict(ps.FONT_OK, {sha(face): 'a reviewed face'}):
            self.assertEqual(self.build({'gdl/fonts/face.woff2': face})[0], 0)

    def test_every_font_this_checkout_would_publish_is_pinned(self):
        """The Open Sans files the systems carry - and nothing else of any font format - of every
        file a publish would carry: not one under a path EXCLUDE holds back, which never
        publishes, and read as the check reads it (is_font), so not a project graph. With Git LFS
        pulled, the ProjectGCP files archive/job-9fe2c865/ tracks begin as TrueType does, and
        failed this as fonts; without it they are pointers."""
        names = subprocess.run(['git', '-C', REPO, 'ls-files', '-z'], capture_output=True,
                               check=True).stdout.decode('utf-8').split('\0')
        fonts = {}
        for name in filter(None, names):
            path = os.path.join(REPO, name)
            if os.path.isfile(path) and not ps.excluded(name):
                with open(path, 'rb') as fh:
                    data = fh.read()
                if ps.is_font(data):
                    fonts[name] = ps.font_ok(data)
        self.assertEqual(fonts, {'gdl/fonts/opensans-latin.woff2': True,
                                 'gdl/fonts/opensans-light.ttf': True,
                                 'gdl/fonts/opensans-regular.ttf': True})
        self.assertEqual(sorted(ps.FONT_OK.values()), sorted(fonts))

    GRAPH = GRAPH_HEADER + bytes(range(256)) * 4

    def test_a_project_graph_is_not_a_font(self):
        """The check reads a font by its first bytes, and a ProjectGCP's are TrueType's: one is
        told apart by the version its stream header goes on to, which no font's table directory
        holds. The synthetic fixture's own ProjectGCP, where it is here, as well as one made."""
        graphs = [self.GRAPH]
        synthetic = os.path.join(REPO, 'tests', 'data', 'synthetic', 'synthetic.gdl')
        try:
            from gdl.container import open_gdl
            graphs.append(open_gdl(synthetic).read('ProjectGCP'))
        except Exception:  # a pointer where Git LFS is not pulled
            pass
        for g in graphs:
            self.assertIn(bytes(g[:4]), ps.FONT_MAGIC, 'the case: it starts as TrueType does')
            self.assertFalse(ps.is_font(g))
        for face in (self.FACE, a_font('X', magic=0x4F54544F), b'wOF2\x00\x01\x00\x00' + bytes(256)):
            self.assertTrue(ps.is_font(face))

    def test_a_font_named_as_a_project_graph_is_refused(self):
        """A file named *ProjectGCP is read as a project graph - for words, not as a font - so a
        face so named published, whatever FONT_OK said: by its bytes it is a font."""
        for path in ('archive/desktop/x/ProjectGCP', 'archive/desktop/x/gen_ProjectGCP'):
            with self.subTest(path=path):
                code, out = self.build({path: self.FACE})
                self.assertEqual(code, 1, out)
                self.assertIn('font not reviewed (FONT_OK', out)

    def test_a_project_graph_is_read_as_one(self):
        """Named as one, it is read for words and publishes; named otherwise, it is a binary no one
        has reviewed, not a font."""
        self.assertEqual(self.build({'archive/desktop/x/ProjectGCP': self.GRAPH})[0], 0)
        code, out = self.build({'archive/desktop/x/graph.bin': self.GRAPH})
        self.assertEqual(code, 1, out)
        self.assertIn('binary file not reviewed (BINARY_OK)', out)
        self.assertNotIn('font not reviewed', out)

    def test_an_excluded_paths_font_is_left_out_not_refused(self):
        """A path EXCLUDE holds back never publishes, so a font there is not the check's: the build
        leaves it out. In a tree meant to be public it is refused as a held-back path."""
        r = Repo({'README.md': '# toolkit\n', 'archive/job-e823df9b/face.ttf': self.FACE})
        code, out = r.run('build', '--archive', 'archive', '--public', 'public')
        self.assertEqual(code, 0, out)
        self.assertNotIn('archive/job-e823df9b/face.ttf', r.files('public-next'))
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertIn('held-back path present', out)

    # -- encoded in a text -------------------------------------------------------------------
    def test_base64_in_a_bundle_is_refused_by_its_line(self):
        js = 'var P = 1;\nadd("Extron-Shockwave", "%s", ["400"]);\n' % self.B64
        code, out = self.build({'out-of-place/bundle.js': js})
        self.assertEqual(code, 1, out)
        self.assertIn('bundle.js:2  font encoded as base64 in a text, not reviewed (FONT_OK', out)
        self.assertNotIn(self.B64[:40], out)

    def test_any_face_in_a_text_is_refused_whatever_its_name(self):
        """A face named for nothing of Extron's, and one whose names cannot be read: both went
        through when the check read names."""
        b64 = __import__('base64').b64encode
        for face in (a_font('Open Sans'), b'wOF2\x00\x01\x00\x00' + bytes(range(256)) * 16):
            with self.subTest(face=face[:4]):
                self.assertEqual(self.found('add("Some Face", "%s");' % b64(face).decode()), ['base64'])
                with mock.patch.dict(ps.FONT_OK, {sha(face): 'a reviewed face'}):
                    self.assertEqual(self.found('add("Some Face", "%s");' % b64(face).decode()), [])

    def test_wrapped_base64_is_read_whole(self):
        """The reviewer's 76 columns, as MIME wraps it - and any width, indented, CRLF."""
        for width in (76, 64, 7, 1):
            with self.subTest(width=width):
                self.assertEqual(self.found('data:\n' + wrapped(self.B64, width) + '\n'), ['base64'])
        self.assertEqual(self.found('    ' + wrapped(self.B64, 76).replace('\n', '\r\n    ')), ['base64'])
        # Read whole, not as a font's first line: a reviewed face wrapped is still itself.
        with mock.patch.dict(ps.FONT_OK, {sha(self.FACE): 'a reviewed face'}):
            self.assertEqual(self.found('x = """\n' + wrapped(self.B64, 76) + '\n"""\n'), [])

    def test_strings_joined_are_read_whole(self):
        """The reviewer's JS concatenation - and Python's implicit kind, and pieces so short that
        the font's first bytes are cut."""
        for size in (1000, 76, 3):
            pieces = [self.B64[i:i + size] for i in range(0, len(self.B64), size)]
            for joint in ('" +\n  "', '"+"', '" "', '"\n    "'):
                with self.subTest(size=size, joint=joint):
                    self.assertEqual(self.found('var f = "' + joint.join(pieces) + '";'), ['base64'])
        pieces = [self.B64[i:i + 60] for i in range(0, len(self.B64), 60)]
        self.assertEqual(self.found("FACE = ('" + "'\n        '".join(pieces) + "')\n"), ['base64'])
        self.assertEqual(self.found('f = `' + '` + `'.join(pieces) + '`'), ['base64'])

    def test_escaped_slashes_and_json_line_breaks_are_read(self):
        """The reviewer's escaped slashes (JSON may write / as \\/), and base64 wrapped inside a
        JSON string, its breaks written \\n."""
        self.assertIn('/', self.B64)
        self.assertEqual(self.found('{"face": "%s"}' % self.B64.replace('/', '\\/')), ['base64'])
        self.assertEqual(self.found(json.dumps({'face': wrapped(self.B64, 76)})), ['base64'])
        self.assertEqual(self.found('s = "' + wrapped(self.B64, 76).replace('\n', '\\\n') + '"'), ['base64'])
        # Read whole, not only as far as the first escape: a face whose slashes come within its
        # first bytes, and a reviewed face, which passes only as exactly its own bytes.
        early = __import__('base64').b64encode(self.FACE[:12] + b'\xff' * 3 + self.FACE[15:]).decode()
        self.assertEqual(early[16:20], '////')
        self.assertEqual(self.found('{"face": "%s"}' % early.replace('/', '\\/')), ['base64'])
        with mock.patch.dict(ps.FONT_OK, {sha(self.FACE): 'a reviewed face'}):
            self.assertEqual(self.found('{"face": "%s"}' % self.B64.replace('/', '\\/')), [])
            self.assertEqual(self.found(json.dumps({'face': wrapped(self.B64, 76)})), [])

    def test_url_safe_base64_is_read(self):
        url = __import__('base64').urlsafe_b64encode(self.FACE).decode()
        self.assertTrue(set('-_') & set(url) and not set('+/') & set(url), 'no URL-safe characters to read')
        self.assertEqual(self.found('https://example.invalid/f?face=' + url), ['base64'])
        self.assertEqual(self.found(wrapped(url.rstrip('='), 76)), ['base64'])
        # Decoded as base64's own alphabet, so a reviewed face is itself.
        with mock.patch.dict(ps.FONT_OK, {sha(self.FACE): 'a reviewed face'}):
            self.assertEqual(self.found('https://example.invalid/f?face=' + url), [])

    def test_base32_hex_and_decimal_bytes_are_read(self):
        b32 = __import__('base64').b32encode(self.FACE).decode()
        hexed = self.FACE.hex()
        each = {
            'base32': [b32, wrapped(b32, 72)],
            'hex': [hexed, hexed.upper(), wrapped(hexed, 60),
                    ' '.join('%02x' % b for b in self.FACE),               # a dump's bytes alone
                    'b"' + ''.join('\\x%02x' % b for b in self.FACE) + '"',
                    '{' + ', '.join('0x%02X' % b for b in self.FACE) + '}',
                    'data:font/ttf,' + ''.join('%%%02X' % b for b in self.FACE)],
            'decimal bytes': ['[' + ', '.join(map(str, self.FACE)) + ']',
                              'new Uint8Array([' + ','.join(map(str, self.FACE)) + '])']}
        for name, texts in each.items():
            for text in texts:
                with self.subTest(encoding=name, text=text[:24]):
                    self.assertEqual(self.found(text), [name])

    def test_a_reviewed_face_passes_only_as_its_own_bytes(self):
        """The design systems' Open Sans, base64 in a bundle as face_js writes it, passes; with
        anything run on after it in the same string - another face, or more bytes - it does not."""
        b64 = __import__('base64').b64encode
        with open(os.path.join(REPO, 'gdl', 'fonts', 'opensans-latin.woff2'), 'rb') as fh:
            face = b64(fh.read()).decode()
        self.assertEqual(self.found('  add("Open Sans", "%s", ["300", "400", "700"]);\n' % face), [])
        self.assertEqual(self.found('add("Open Sans", "%s" + "%s");' % (face, self.B64)), ['base64'])
        self.assertEqual(self.found('add("Open Sans", "%sAAAA");' % face.rstrip('=')), ['base64'])

    def test_a_blank_line_ends_a_run(self):
        """A paragraph after a wrapped run is not read into it; a line straight after it is."""
        self.assertNotIn('=', self.B64)         # no padding to end the run before the break does
        with mock.patch.dict(ps.FONT_OK, {sha(self.FACE): 'a reviewed face'}):
            self.assertEqual(self.found(wrapped(self.B64, 76) + '\n\nNext paragraph'), [])
            self.assertEqual(self.found(wrapped(self.B64, 76) + '\n  \r\nNext paragraph'), [])
            self.assertEqual(self.found(wrapped(self.B64, 76) + '\nNext line'), ['base64'])

    def test_what_is_not_a_font_is_not_refused(self):
        """A font's first bytes alone, too short to be a face; other bytes encoded at length; and
        the tool's own patterns."""
        png = __import__('base64').b64encode(b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 16).decode()
        for text in ('AAEAAA', 'magic 00010000 and 0x00010000', '[0, 1, 0, 0, 5]', 'd09GMgABAAAAA',
                     'src="data:image/png;base64,%s"' % png, wrapped(png, 76)):
            with self.subTest(text=text[:20]):
                self.assertEqual(self.found(text), [])
        with open(os.path.join(REPO, 'tools', 'public_sync.py'), 'rb') as fh:
            self.assertEqual(ps.fonts_in_text(fh.read()), [])

    def test_no_text_this_checkout_tracks_holds_a_font(self):
        """What a publish would refuse, read here first: every tracked text file."""
        names = subprocess.run(['git', '-C', REPO, 'ls-files', '-z'], capture_output=True,
                               check=True).stdout.decode('utf-8').split('\0')
        hits = []
        for name in filter(None, names):
            path = os.path.join(REPO, name)
            if os.path.isfile(path) and not ps.excluded(name):
                with open(path, 'rb') as fh:
                    data = fh.read()
                if not ps.is_binary(data):
                    hits += [(name, h) for h in ps.fonts_in_text(data)]
        self.assertEqual(hits, [])

    def test_a_font_in_a_commit_message_is_refused(self):
        r = Repo({'README.md': '# x\n'})
        r.commit('noted', {'README.md': '# x\n'}, 'notes\n\n' + wrapped(self.B64, 76))
        code, out = r.run('check', '--history', 'noted')
        self.assertEqual(code, 1, out)
        self.assertIn('<commit message>:3  font encoded as base64', out)

    def test_a_blob_is_read_once(self):
        """check --history meets most blobs in every commit: the answer is kept by the blob."""
        text = 'f = "%s"' % self.B64
        self.assertEqual(ps.fonts_in_text(text, key='blob-1'), [(1, 'base64')])
        with mock.patch.object(ps, '_joined', side_effect=AssertionError('read again')):
            self.assertEqual(ps.fonts_in_text(text, key='blob-1'), [(1, 'base64')])
        ps._FONT_HITS.pop('blob-1', None)


class TestCheckSeesInside(unittest.TestCase):
    def test_lfs_content_is_checked(self):
        r = Repo({'README.md': '# x\n'})
        pointer, _, _ = r.lfs(zip_bytes({'ProjectGCP': f'project of {WORD}'.encode()}))
        r.commit('lfs', {'archive/desktop/x/project1.tgz4': pointer}, 'lfs')
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
        r = Repo({'archive/desktop/x/project1.tgz4': tgz4, 'archive/desktop/x/X.gdl': gdl})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count('private denylist'), 2, out)

    def test_a_utf16_secret_in_a_project_stream_is_found(self):
        r = Repo({'archive/desktop/x/ProjectGCP': GRAPH_HEADER + SECRET.encode('utf-16-le') + b'\x00'})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)

    def test_check_history_finds_a_held_back_path_in_an_ancestor(self):
        r = Repo({'fixtures/gdl/c.gdl': 'client\n'})
        git(r.dir, 'checkout', '-q', 'archive')
        git(r.dir, 'rm', '-q', 'fixtures/gdl/c.gdl')
        git(r.dir, 'commit', '-q', '-m', 'drop it')
        self.assertEqual(r.run('check', 'archive')[0], 0)
        self.assertEqual(r.run('check', '--history', 'archive')[0], 1)

    def test_a_deleted_folders_published_files_pass_in_older_commits(self):
        """archive/gdlwork/ is deleted, but published commits hold the files of
        it that were never held back: its exclusion holds back what it did,
        not the folder, so the published line's history still checks clean."""
        r = Repo({'README.md': '# x\n'})
        r.commit('published', {'README.md': '# public\n', 'archive/gdlwork/specs/spec.json': '{}\n'},
                 'published while the folder was there')
        git(r.dir, 'rm', '-q', 'archive/gdlwork/specs/spec.json')
        git(r.dir, 'commit', '-q', '-m', 'the folder deleted')
        code, out = r.run('check', '--history', 'published')
        self.assertEqual(code, 0, out)
        # The whole folder held back would refuse that history. (excluded() binds the list
        # itself as its default, so the list is changed in place.)
        ps.EXCLUDE.append('archive/gdlwork/')
        try:
            self.assertEqual(r.run('check', '--history', 'published')[0], 1)
        finally:
            ps.EXCLUDE.remove('archive/gdlwork/')

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
        r = Repo({'archive/desktop/x/ProjectGCP': GRAPH_HEADER + SECRET.encode('utf-16-le') + b'\x00'})
        self.assertEqual(len(GRAPH_HEADER) % 2, 1, 'the value starts at an odd offset')
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertIn('settings value', out)

    def test_a_nul_past_the_first_8k_still_makes_a_file_binary(self):
        r = Repo({'notes.txt': b'a' * 9000 + SECRET.encode('utf-16-le')})
        self.assertEqual(r.run('check', 'archive')[0], 1)

    def test_a_container_that_does_not_open_is_refused(self):
        r = Repo({'archive/desktop/x/shot.tgz4': b'\x89PNG\r\n\x1a\n\x00\x00not a zip'})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertIn('does not open', out)

    def test_a_member_that_does_not_read_whole_is_refused(self):
        """A damaged member - its data failing its CRC, or a deflate stream
        that does not inflate - is a container that does not open, refused by
        name; it crashed build and check. (One the old pack() wrote is mended:
        the next test.)"""
        deflated = io.BytesIO()
        with zipfile.ZipFile(deflated, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('project1.tgz4', bytes(range(256)) * 64)
        raw = bytearray(deflated.getvalue())
        raw[60] ^= 0xFF
        code, out = Repo({'README.md': '# x\n', 'archive/desktop/x/bad.gdl': bytes(raw)}).run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertIn('does not open', out)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as z:
            z.writestr('project1.tgz4', b'payload ' * 64)
        raw = bytearray(buf.getvalue())
        raw[raw.index(b'payload') + 3] ^= 0x20
        r = Repo({'README.md': '# x\n', 'archive/desktop/x/pre.gdl': bytes(raw)})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertIn('does not open', out)
        code, out = r.run('build', '--archive', 'archive', '--public', 'public')
        self.assertNotEqual(code, 0, out)

    def test_a_gdl_the_old_pack_wrote_is_read_and_checked(self):
        """The old pack() swapped every signature pattern in what it wrote, a
        payload's data with the records', and the old reader's swap undid it;
        the strict reader cannot, and `check --history` refused a published
        commit's such file as a container that does not open - so every push
        after it. The patterns the records do not account for are put back
        where every CRC then agrees, and what the file holds is checked as
        anything else is; a member those do not mend is still refused."""
        def old_pack(content):
            # The built panel is a zip of its own, stored where its bytes do
            # not compress: its records, and the patterns in its data, swapped
            # with the container's.
            inner = io.BytesIO()
            with zipfile.ZipFile(inner, 'w', zipfile.ZIP_STORED) as z:
                z.writestr('layout.json', content)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as z:
                z.writestr('ProjectGCP', b'graph')
                z.writestr('project1.tgz4', inner.getvalue())
            raw = buf.getvalue()
            for s in (b'\x03\x04', b'\x01\x02', b'\x05\x06'):
                raw = raw.replace(b'PK' + s, b'KP' + s)
            return raw
        clean = old_pack(b'images ' + b'PK\x03\x04' + b' and ' + b'PK\x05\x06' + b' end')
        r = Repo({'README.md': '# x\n', 'archive/fb/pre.gdl': clean})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 0, out)
        r = Repo({'README.md': '# x\n', 'archive/fb/pre.gdl': old_pack(b'room ' + WORD.encode() + b' PK\x03\x04')})
        code, out = r.run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertNotIn('does not open', out)
        self.assertIn('pre.gdl!project1.tgz4!layout.json', out)
        damaged = bytearray(clean)
        damaged[damaged.index(b' and ') + 1] ^= 0x20
        code, out = Repo({'README.md': '# x\n', 'archive/fb/pre.gdl': bytes(damaged)}).run('check', 'archive')
        self.assertEqual(code, 1, out)
        self.assertIn('does not open', out)

    def test_a_zip_or_gzip_member_under_any_name_is_opened(self):
        for inner in (zip_bytes({'layout.json': WORD.encode()}), gzip.compress(WORD.encode() * 3)):
            r = Repo({'archive/desktop/x/project1.tgz4': zip_bytes({'assets.bin': inner})})
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
