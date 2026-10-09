#!/usr/bin/env python3
"""
public_sync.py - build the public copy's next commit from the private archive, and check it.

The project lives in a private archive, extron-gdl-toolkit-archive; the public copy,
extron-gdl-toolkit, carries the same work minus what must stay private: a client's project
files and everything built from them, the working sessions' transcripts, and GUI Designer's
per-user settings file. Doing that by hand each time is how things leak, so this does it the
same way every time:

  build   turn an archive commit into the next commit on the public line: drop the EXCLUDE
          paths, scrub home-folder paths from text, check the result, and point a local branch
          at it. Its only parent is the public line's tip (or none, with --first), so archive
          history never becomes part of the public line.
  check   check any commit - and with --history every ancestor and its message - against the
          same rules.

Nothing here pushes. tools/hooks/pre-push runs `check --history` on anything pushed to the
public remote, and publishing stays a deliberate step with the owner's word:

  python tools/public_sync.py build --archive origin/main --public public/main
  python tools/public_sync.py check --history public-next
  git push public public-next:main

What the check refuses needs what lives in private/ - git-ignored, on the owner's machine
only: private/public-sync-denylist.txt, patterns that would name what they guard if they were
published (one regex per line), and GUI Designer's settings file, whose values are read here
at check time and never written anywhere. Without them it refuses to check at all rather than
pass blind.

Git LFS files are checked by their content, read from the local LFS store; a file whose
content is not there is refused, never passed unseen. Containers - .gdl, .glt, .tgz4 and
ProjectGCP streams, and any zip or gzip member inside one whatever it is named - are checked
member by member, as UTF-8 and as UTF-16 at either byte alignment; one that does not open is
refused. Any other binary must be on BINARY_OK with the hash of the bytes a person looked at:
no text check reads an image. Paths, commit messages and tag messages are checked too, and a
private pattern is matched across a line break, since a hard wrap splits a two-word name.
Nothing private is ever echoed: a hit is reported by its kind and place, masked.

Standard library only (with this repository's gdl.nrbf and gdl.container); needs git on PATH.
"""
import argparse
import base64
import fnmatch
import gzip
import hashlib
import io
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from gdl import nrbf  # noqa: E402
from gdl.container import open_gdl_bytes  # noqa: E402

# ---- what stays private -------------------------------------------------------------------
# Repo-relative paths, fnmatch-style, matched in any case: on Windows a folder takes whatever
# case created it. A pattern ending in "/" means everything under that folder.
EXCLUDE = [
    "fixtures/",                       # the client's project files and GUI Designer's renders of them
    "private/",                        # settings file, temp fonts, denylist (also git-ignored)
    "archive/claude/sessions/",        # whole working conversations
    "archive/gui-designer/",           # where the settings file was once tracked
    "archive/gdlwork/Boardroom/", "archive/gdlwork/Huddle/", "archive/gdlwork/auto/",
    "archive/gdlwork/auto2/", "archive/gdlwork/color/", "archive/gdlwork/ex1/",
    "archive/gdlwork/mp/", "archive/gdlwork/mp2/", "archive/gdlwork/out/",
    "archive/gdlwork/out2/", "archive/gdlwork/out3/",   # builds made from the client's project
    "archive/gdlwork/clean/wizard.png",                  # status bars showing the licensee's e-mail
    "archive/gdlwork/clean/wiz2.png",
    "archive/gdlwork/uia-build.log",                     # cp1252 log naming the owner's home folder
    "archive/job-9fe2c865/timeline.jsonl",               # evidence kept as it was; names the client
    "archive/job-9fe2c865/tmp/statenames.py",
    "archive/job-9fe2c865/tmp/states.py",
    "docs/superpowers/specs/2026-10-07-public-private-split-design.md",   # the split's own notes:
    "docs/superpowers/plans/2026-10-07-public-private-split.md",          # what is held back, and why
    "*__pycache__/*", "*.pyc",                           # byte code embeds the path it was built from
]

# Text rewrites applied to every text file that is published. (pattern, replacement).
_SEP = r"(?:\\+|/)"             # any run of backslashes (JSON escapes nest), or a slash
_NAME = r"[A-Za-z0-9][A-Za-z0-9._-]*"   # a user name; never starts with a dot
_SKIP = r"(?!Public\b|Default\b|All Users\b|Shared\b|<user>)"   # shared folders, and done ones
SCRUB = [
    # an absolute path to a checkout of this repository -> <repo>. First, before <user> blocks it.
    (re.compile(r"(?i)\b[A-Z]:(?:\\+|/)(?:[^\s\"'`<>|*?]+?(?:\\+|/))?extron-gdl-toolkit(?:-archive)?\b"),
     "<repo>"),
    (re.compile(r"(?<![\w.:/])/(?:[^\s\"'`<>|*?/]+/)+extron-gdl-toolkit(?:-archive)?\b"), "<repo>"),
    # a Windows home folder other than the shared Public/Default ones -> <user>
    (re.compile(r"(?i)\b([A-Z]):(" + _SEP + r")Users(" + _SEP + r")" + _SKIP + _NAME), r"\1:\2Users\3<user>"),
    # the same in Git Bash form (/c/Users/...)
    (re.compile(r"(?i)/([a-z])/Users/" + _SKIP + _NAME), r"/\1/Users/<user>"),
    # macOS and Linux home folders
    (re.compile(r"/(Users|home)/" + _SKIP + _NAME + r"(?=/)"), r"/\1/<user>"),
    # a home folder flattened into a folder name, as Claude Code names its project folders
    (re.compile(r"(?i)((?:\b[A-Z]-)?-Users-)(?!<user>)[A-Za-z0-9][A-Za-z0-9._]*(?=-)"), r"\1<user>"),
    # a Windows home folder written without its drive (Users\...\Downloads)
    (re.compile(r"(?i)\b(Users)(\\+)" + _SKIP + _NAME + r"(?=\\)"), r"\1\2<user>"),
]

# Binary files that may be published, each one looked at by a person: no text check can see
# into an image. Pinned by the SHA-256 of the bytes that were looked at (the LFS content, where
# the file is in LFS), so a regenerated image is refused until someone looks again and re-pins
# it - a screenshot showing the licensee's e-mail was found only by looking. A new binary is
# refused until it is reviewed and listed here.
BINARY_OK = {
    # the worked example, rendered
    "docs/panel-preview.png": "c2b9ef77efce72609e7b3da95d7d44b72d3e40e32738d133d41dc420a951836e",
    "docs/generated-built.png": "fcc3fec8148a474f9f3cf634bbfa06d1bcf8775b36e098a6332744ab61a84f7a",
    # Apache-2.0
    "gdl/fonts/opensans-light.ttf": "cf5f5184c1441a1660aa52526328e9d5c2793e77b6d8d3a3ad654bdb07ab8424",
    "gdl/fonts/opensans-regular.ttf": "e64e508b2aa2880f907e470c4550980ec4c0694d103a43f36150ac3f93189bee",
    # panels rendered from seeds
    "archive/gdlwork/CleanRoom/room.png": "11a3598393d1b6394dffc25d08afac96c51b254cf8fbc38e04e38426a4f05f85",
    "archive/gdlwork/clean/preview.png": "c9235802522b3898b6b0b6a89eab4a141eafa3ca0503365423e6dd6f5bd90eeb",
    "archive/gdlwork/seed2/all-pages.png": "46040a76aa5a470f58ce206c36d126576d5d031df4b7a0d58f965d5cf8fdcd91",
}
CONTAINERS = (".gdl", ".glt", ".tgz4")    # and any file named *ProjectGCP
# Forward slashes: these are named in messages, and os.path.join(repo, ...) accepts them.
DENYLIST_FILE = "private/public-sync-denylist.txt"
SETTINGS_FILE = "private/gui-designer/user-config/user.config"
LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"

# What the published result must not contain: these refuse a build. (name, pattern)
LEAKS = [
    ("home path", re.compile(r"(?i)\b[A-Z]:" + _SEP + r"Users" + _SEP + _SKIP + _NAME)),
    ("home path", re.compile(r"(?i)/[a-z]/Users/" + _SKIP + _NAME)),
    ("home path", re.compile(r"/(?:Users|home)/" + _SKIP + _NAME + r"/")),
    ("home path", re.compile(r"(?i)-Users-(?!<user>)[A-Za-z0-9][A-Za-z0-9._]*-")),
    ("home path", re.compile(r"(?i)\bUsers\\+" + _SKIP + _NAME + r"\\")),
    # Claude Code names a project folder after the path it ran in, drive letter and all, so a
    # scratch path from a job site's folder carries the site. Only a home folder (scrubbed above)
    # and a GitHub checkout are expected.
    ("flattened folder name", re.compile(r"(?i)\b[A-Z]--(?!Users-<user>|GitHub-)[A-Za-z0-9]")),
    ("credential in URL", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@'\"<>]+:[^/\s@'\"<>]+@[A-Za-z0-9.-]+")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("AWS key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
]


class CannotCheck(Exception):
    """What the check needs from private/ is not on this machine."""


# ---- git plumbing ---------------------------------------------------------------------------
class Git:
    def __init__(self, repo):
        self.repo = repo
        self._cat = None
        self._blobs = {}          # blob sha -> bytes
        self._scrubbed = {}       # blob sha -> scrubbed blob sha (or same)

    def run(self, *args, input=None, env=None):
        e = dict(os.environ)
        if env:
            e.update(env)
        p = subprocess.run(["git", "-C", self.repo] + list(args), input=input, capture_output=True, env=e)
        if p.returncode != 0:
            raise RuntimeError("git %s failed: %s" % (" ".join(args), p.stderr.decode("utf-8", "replace").strip()))
        return p.stdout

    def text(self, *args, **kw):
        return self.run(*args, **kw).decode("utf-8", "replace")

    def rev(self, name):
        return self.text("rev-parse", "--verify", name + "^{commit}").strip()

    def blob(self, sha):
        if sha not in self._blobs:
            if self._cat is None:
                self._cat = subprocess.Popen(["git", "-C", self.repo, "cat-file", "--batch"],
                                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            pipe_in, pipe_out = self._cat.stdin, self._cat.stdout
            assert pipe_in is not None and pipe_out is not None
            pipe_in.write(sha.encode() + b"\n")
            pipe_in.flush()
            header = pipe_out.readline().split()
            size = int(header[2])
            data = pipe_out.read(size)
            pipe_out.read(1)
            self._blobs[sha] = data
        return self._blobs[sha]

    def entries(self, treeish):
        """(mode, type, sha, path) for every file of a tree."""
        out = self.run("ls-tree", "-r", "-z", "--full-tree", treeish)
        rows = []
        for item in out.split(b"\0"):
            if not item:
                continue
            meta, path = item.split(b"\t", 1)
            mode, typ, sha = meta.decode().split()
            rows.append((mode, typ, sha, path.decode("utf-8")))
        return rows

    def close(self):
        if self._cat:
            if self._cat.stdin:
                self._cat.stdin.close()
            self._cat.wait()


def is_binary(data):
    # A NUL anywhere, not only near the start: a text file that turns into UTF-16 later on
    # would otherwise be read as UTF-8, where the NULs between its letters hide every word.
    if b"\0" in data:
        return True
    try:
        data.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def excluded(path, patterns=EXCLUDE):
    low = path.lower()
    for p in patterns:
        p = p.lower()
        if p.endswith("/"):
            if low.startswith(p):
                return True
        elif fnmatch.fnmatchcase(low, p):
            return True
    return False


def scrub_text(text):
    for rx, rep in SCRUB:
        text = rx.sub(rep, text)
    return text


# ---- what the check reads from private/ -----------------------------------------------------
def load_denylist(repo):
    path = os.path.join(repo, DENYLIST_FILE)
    if not os.path.isfile(path):
        raise CannotCheck(DENYLIST_FILE + " is not here, so the client's name cannot be checked for")
    out = []
    # utf-8-sig: Windows PowerShell 5.1 and older Notepad write a BOM, which would otherwise
    # become part of the first pattern and stop it matching.
    with open(path, encoding="utf-8-sig") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(("private denylist", re.compile(line)))
            except re.error:
                # Named by line only: the pattern itself names what it guards.
                raise CannotCheck("%s line %d is not a valid regular expression" % (DENYLIST_FILE, lineno))
    if not out:
        raise CannotCheck(DENYLIST_FILE + " holds no pattern, so the client's name cannot be checked for")
    return out


def load_secrets(repo):
    """Every value in GUI Designer's settings file worth refusing: the account's e-mail and the
    license's username, password, key, number and owner. Read here, never written anywhere."""
    path = os.path.join(repo, SETTINGS_FILE)
    if not os.path.isfile(path):
        raise CannotCheck(SETTINGS_FILE + " is not here, so its values cannot be checked for")
    out = set()
    for setting in ET.parse(path).iter("setting"):
        text = (setting.findtext("value") or "").strip()
        if setting.get("name") == "LastUsername" and text:
            out.add(text)
        elif setting.get("name") in ("UserLicenses", "LastUserLicense") and text:
            r = nrbf.parse(base64.b64decode(text))
            for o in r.objects.values():
                if isinstance(o, dict):
                    for k in ("_licensekey", "_licensenumber", "_ownerID", "_password", "_username"):
                        v = nrbf.resolve(r, o.get(k)) if k in o else None
                        if isinstance(v, str):
                            out.add(v)
    out = sorted(v for v in out if len(v) >= 4)
    if not out:
        # A truncated copy, or a GUI Designer version whose keys differ: checking against
        # nothing would pass everything.
        raise CannotCheck(SETTINGS_FILE + " yields no values, so its values cannot be checked for")
    return out


class Rules:
    def __init__(self, repo):
        self.deny = load_denylist(repo)
        self.secrets = [("settings value", re.compile(re.escape(s), re.I)) for s in load_secrets(repo)]

    def private(self):
        return self.deny + self.secrets

    def shown(self, where):
        """A path or member name as it may be printed: any private match in it masked."""
        for _, rx in self.private():
            where = rx.sub("***", where)
        return where


# ---- reading through LFS and containers -----------------------------------------------------
def lfs_content(git, data):
    """The content behind an LFS pointer, from the local store, or None if it is not there."""
    m = re.search(rb"oid sha256:([0-9a-f]{64})", data)
    if not m:
        return None
    oid = m.group(1).decode()
    common = git.text("rev-parse", "--git-common-dir").strip()
    if not os.path.isabs(common):
        common = os.path.join(git.repo, common)
    path = os.path.join(common, "lfs", "objects", oid[:2], oid[2:4], oid)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return f.read()


ZIP_MAGIC = (b"PK\x03\x04", b"KP\x03\x04")     # a zip, and a .gdl/.glt's swapped signature
GZIP_MAGIC = b"\x1f\x8b"


def _opened(data):
    """A zip, or a .gdl/.glt (a zip with its signatures swapped), opened; None if it is neither."""
    try:
        return open_gdl_bytes(data) if data[:2] == b"KP" else zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return None


def members(path, data):
    """(name, bytes) of every member of a container, opening any member that is itself a zip,
    a .gdl or a gzip stream whatever it is named - searched compressed, its words would never
    match. A container that does not open yields (name, None), which the check refuses: an
    unreadable file is not a checked one."""
    if os.path.basename(path).endswith("ProjectGCP"):
        yield path, data
        return
    z = _opened(data)
    if z is None:
        yield path, None
        return
    for n in z.namelist():
        inner, where = z.read(n), path + "!" + n
        if inner[:2] == GZIP_MAGIC:
            try:
                inner, where = gzip.decompress(inner), where + " (gunzipped)"
            except (OSError, EOFError):
                yield where, None
                continue
        if inner[:4] in ZIP_MAGIC or n.endswith(CONTAINERS) or n.endswith("ProjectGCP"):
            yield from members(where, inner)
        else:
            yield where, inner


# ---- transform and check ------------------------------------------------------------------
def transform(git, treeish):
    """The public version of a tree: excluded paths dropped, text scrubbed. Returns a tree sha."""
    lines = []
    for mode, typ, sha, path in git.entries(treeish):
        if excluded(path):
            continue
        if typ == "blob" and mode in ("100644", "100755"):
            if sha not in git._scrubbed:
                data = git.blob(sha)
                new = sha
                if not is_binary(data):
                    text = data.decode("utf-8")
                    out = scrub_text(text)
                    if out != text:
                        new = git.text("hash-object", "-w", "--stdin", input=out.encode("utf-8")).strip()
                git._scrubbed[sha] = new
            sha = git._scrubbed[sha]
        lines.append("%s %s %s\t%s" % (mode, typ, sha, path))
    fd, index = tempfile.mkstemp(prefix="public-sync-index-")
    os.close(fd)
    os.unlink(index)                               # git creates it fresh
    try:
        env = {"GIT_INDEX_FILE": index}
        git.run("update-index", "--index-info", input=("\n".join(lines) + "\n").encode("utf-8"), env=env)
        return git.text("write-tree", env=env).strip()
    finally:
        if os.path.exists(index):
            os.unlink(index)


def _mask(s):
    """A leak-pattern hit as it may be printed: its first three characters, enough to say what
    it is (a drive, a token prefix), and none of the rest."""
    return s.strip()[:3] + "***"


# A hard wrap, or a comment or quote marker at the start of the next line, between the two words
# of a name. Collapsed to one space before the private patterns run over a pair of lines.
_GAP = re.compile(r"[\s#*>/|;\"'`-]+")


def check_text(where, text, rules):
    """Problems in one text: the leak patterns and the private ones, line by line, and the
    private ones again over each pair of lines, where a wrapped name is whole. A private hit is
    reported by its kind alone - never any part of what matched."""
    problems = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, 1):
        for kind, rx in LEAKS:
            m = rx.search(line)
            if m:
                problems.append((where, lineno, kind, _mask(m.group(0))))
        for kind, rx in rules.private():
            if rx.search(line):
                problems.append((where, lineno, kind, "***"))
    for lineno in range(1, len(lines)):
        a, b = lines[lineno - 1], lines[lineno]
        pair = _GAP.sub(" ", a + "\n" + b)
        for kind, rx in rules.private():
            if rx.search(pair) and not rx.search(a) and not rx.search(b):
                problems.append((where, lineno, kind + " (across a line break)", "***"))
    return problems


def check_bytes(where, data, rules):
    """The private patterns in a binary, read as UTF-8 and as UTF-16 at both byte alignments -
    a UTF-16 string can start at an odd offset. Not the home-path rules: a seed's project
    carries paths of the machine that made it, which cannot be rewritten."""
    problems = set()
    texts = (data.decode("utf-8", "ignore"), data.decode("utf-16-le", "ignore"),
             data[1:].decode("utf-16-le", "ignore"))
    for text in texts:
        for kind, rx in rules.private():
            if rx.search(text):
                problems.add((where, 0, kind, "(in a binary)"))
    return sorted(problems)


def check_path(path, rules):
    """A path, or a member's name inside a container, is published as much as its content."""
    return [(rules.shown(path), 0, kind + " (in the path)", "***")
            for kind, rx in list(LEAKS) + rules.private() if rx.search(path)]


def check_tree(git, treeish, rules):
    """Problems in a tree that is meant to be public: list of (path, line, kind, excerpt)."""
    problems = []
    for mode, typ, sha, path in git.entries(treeish):
        if typ != "blob":
            continue
        shown = rules.shown(path)
        if excluded(path):
            problems.append((shown, 0, "held-back path present", ""))
            continue
        problems += check_path(path, rules)
        data = git.blob(sha)
        if data.startswith(LFS_POINTER):
            content = lfs_content(git, data)
            if content is None:
                problems.append((shown, 0, "LFS content not in the local LFS store (git lfs pull)", ""))
                continue
            data = content
        if path.endswith(CONTAINERS) or path.endswith("ProjectGCP"):
            for where, inner in members(path, data):
                if where != path:
                    problems += check_path(where[len(path):], rules)
                if inner is None:
                    problems.append((rules.shown(where), 0, "container does not open", ""))
                else:
                    problems += check_bytes(rules.shown(where), inner, rules)
        elif is_binary(data):
            want = BINARY_OK.get(path)
            if want is None:
                problems.append((shown, 0, "binary file not reviewed (BINARY_OK)", ""))
            elif hashlib.sha256(data).hexdigest() != want:
                problems.append((shown, 0, "binary changed since it was reviewed (re-pin in BINARY_OK)", ""))
        else:
            problems += check_text(shown, data.decode("utf-8"), rules)
    return problems


def check_message(git, commit, rules):
    """A commit's message, author and committer."""
    text = git.text("log", "-1", "--format=%B", commit)
    out = [(p[0], p[1], p[2] + " (in %s)" % commit[:7], p[3])
           for p in check_text("<commit message>", text, rules)]
    ident = git.text("log", "-1", "--format=%an <%ae>%n%cn <%ce>", commit)
    for lineno, line in enumerate(ident.splitlines(), 1):
        for kind, rx in rules.private():
            if rx.search(line):
                out.append(("<author>" if lineno == 1 else "<committer>", 0,
                            kind + " (in %s)" % commit[:7], "***"))
    return out


def check_tags(git, name, rules):
    """The message and tagger of an annotated tag, and of any tag it points at: a pushed tag
    carries them to the remote as surely as a commit carries its message."""
    problems = []
    obj = git.text("rev-parse", "--verify", name).strip()
    while git.text("cat-file", "-t", obj).strip() == "tag":
        body = git.text("cat-file", "tag", obj)
        problems += check_text("<tag %s>" % obj[:7], body, rules)
        obj = re.match(r"object ([0-9a-f]+)", body).group(1)
    return problems


def shares_history(git, a, b):
    """Whether two commits have a common ancestor. The public line never shares one with the
    archive: that is what keeps archive history out of it."""
    p = subprocess.run(["git", "-C", git.repo, "merge-base", a, b], capture_output=True)
    return p.returncode == 0


def report(problems, out=None):
    out = out or sys.stdout
    for path, line, kind, excerpt in problems:
        out.write("  %s:%s  %s  %s\n" % (path, line or "-", kind, excerpt))


# ---- commands -----------------------------------------------------------------------------
def _rules(repo):
    try:
        return Rules(repo)
    except CannotCheck as e:
        print("CANNOT CHECK: %s" % e)
        return None


def cmd_build(args):
    rules = _rules(args.repo)
    if rules is None:
        return 2
    git = Git(args.repo)
    try:
        archive = git.rev(args.archive)
        public = None if args.first else git.rev(args.public)
        if public and shares_history(git, archive, public):
            print("NOT BUILT: %s shares history with the archive (%s); the public line never does."
                  % (args.public, args.archive))
            return 1
        branch = subprocess.run(["git", "-C", args.repo, "rev-parse", "--verify", "--quiet",
                                 "refs/heads/" + args.branch], capture_output=True, text=True)
        if branch.returncode == 0 and shares_history(git, branch.stdout.strip(), archive):
            print("NOT BUILT: branch %s is on the archive line, and building would move it. "
                  "Name another with --branch." % args.branch)
            return 1
        tree = transform(git, archive)
        problems = check_tree(git, tree, rules)
        if problems:
            print("NOT BUILT: the public tree would contain %d problem(s):" % len(problems))
            report(problems)
            return 1
        parents = []
        if public:
            if tree == git.text("rev-parse", public + "^{tree}").strip():
                print("Nothing to publish: %s already matches." % args.public)
                return 0
            parents = ["-p", public]
        msg = args.message or ("Publish from the archive's main line\n\nBuilt by tools/public_sync.py: "
                               "held-back paths left out, home paths scrubbed.\n")
        commit = git.text("commit-tree", tree, *parents, "-F", "-", input=msg.encode("utf-8")).strip()
        git.run("update-ref", "refs/heads/" + args.branch, commit)
        print("built %s (branch %s). Checked: clean." % (commit[:7], args.branch))
        print("To publish (needs the owner's word): git push public %s:main" % args.branch)
        return 0
    finally:
        git.close()


def cmd_check(args):
    rules = _rules(args.repo)
    if rules is None:
        return 2
    git = Git(args.repo)
    try:
        rev = git.rev(args.rev)
        problems = check_tags(git, args.rev, rules) + check_tree(git, rev, rules)
        stopped = None
        if args.history:
            # Newest first, and stop at the first commit that fails: a refusal needs one, and a
            # full check of every commit on a long line would keep a refused push waiting for
            # the better part of an hour.
            for c in git.text("rev-list", rev).split():
                if problems:
                    stopped = c
                    break
                problems += check_message(git, c, rules)
                if c != rev:
                    problems += [(p[0], p[1], p[2] + " (in %s)" % c[:7], p[3])
                                 for p in check_tree(git, c, rules)]
        if problems:
            print("%d problem(s) in %s:" % (len(problems), args.rev))
            report(problems)
            if stopped:
                print("(stopped at the first commit that fails; older ones are not checked)")
            return 1
        print("clean: %s%s" % (args.rev, " and its history" if args.history else ""))
        return 0
    finally:
        git.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build and check the public copy from the private archive.")
    ap.add_argument("--repo", default=".", help="the repository (default: current directory)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("--archive", required=True, help="archive commit to publish (e.g. origin/main)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--public", help="tip of the public line (e.g. public/main)")
    g.add_argument("--first", action="store_true", help="start the public line: a commit with no parent")
    p.add_argument("--branch", default="public-next")
    p.add_argument("--message")
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser("check")
    p.add_argument("rev")
    p.add_argument("--history", action="store_true", help="also check every ancestor commit")
    p.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
