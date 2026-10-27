"""Every Python file here parses as Python 3.11 does.

The Windows host runs 3.11.9 (README.md *Setup*) and hosted CI runs 3.12, so
3.12's syntax passes CI and stops the host. An f-string whose expression
holds a backslash, a comment, a line break or its own quote is legal from
3.12 (PEP 701) and a SyntaxError on 3.11 - one in
examples/probes-128/read_probes.py stopped the probe reader on the host after
an hour of builds. `ast.parse(feature_version=(3, 11))` does not refuse those -
the 3.12 parser accepts them whatever version it is asked for - so they are
found off the tokens here; the rest of 3.12's new syntax (`type` statements,
type parameter lists) the parser does refuse. On 3.11 itself each file is
simply compiled.

    python tests/test_py311.py
"""
import ast
import io
import os
import sys
import tokenize
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Evidence, scratch and other people's code: nothing here maintains them.
SKIP = {'.git', 'archive', 'vendor', 'out', 'private', 'fixtures', '__pycache__', 'node_modules'}


def python_files(root=REPO):
    for d, dirs, names in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP and not x.startswith('.'))
        for n in sorted(names):
            if n.endswith('.py'):
                yield os.path.join(d, n)


def _quote(start):
    """The quote that closes an f-string, off its FSTRING_START token."""
    s = start.lstrip('rRfFbBuUtT')
    return s[:3] if s[:3] in ("'''", '"""') else s[:1]


def problems_311(src):
    """(line, what) for each piece of `src` Python 3.11 would not parse."""
    if sys.version_info < (3, 12):
        try:
            compile(src, '<src>', 'exec')
        except SyntaxError as e:
            return [(e.lineno, e.msg)]
        return []
    try:
        ast.parse(src, feature_version=(3, 11))
    except SyntaxError as e:
        return [(e.lineno, e.msg)]
    start = {tokenize.FSTRING_START, getattr(tokenize, 'TSTRING_START', None)} - {None}
    middle = {tokenize.FSTRING_MIDDLE, getattr(tokenize, 'TSTRING_MIDDLE', None)} - {None}
    end = {tokenize.FSTRING_END, getattr(tokenize, 'TSTRING_END', None)} - {None}
    out, quotes = [], []    # the enclosing f-strings' closing quotes, outermost first
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        line = t.start[0]
        if t.type in start:
            if t.type != tokenize.FSTRING_START:
                out.append((line, 'a t-string (3.14)'))
            # 3.11 reads the whole f-string as one string first, so a quote
            # that closes an outer one closes it, wherever it sits.
            out += [(line, f'a nested string reuses the quote {q}') for q in quotes if q in t.string]
            quotes.append(_quote(t.string))
        elif t.type in middle:
            out += [(line, f'a nested string reuses the quote {q}') for q in quotes[:-1] if q in t.string]
        elif t.type in end:
            quotes.pop()
        elif quotes:        # a token of a replacement field's expression
            if '\\' in t.string:
                out.append((line, 'a backslash in an f-string expression'))
            if t.type == tokenize.COMMENT:
                out.append((line, 'a comment in an f-string expression'))
            if t.type in (tokenize.NL, tokenize.NEWLINE) and any(len(q) == 1 for q in quotes):
                out.append((line, 'a line break in a single-quoted f-string expression'))
            if t.type == tokenize.STRING:
                out += [(line, f'a nested string reuses the quote {q}') for q in quotes if q in t.string]
    return out


class TestTheCheck(unittest.TestCase):
    OK = ["x = f'{\"a\" if x else \"b\"}'", "x = f'{x!r:>10}'", "x = f\"{d['k']}\"",
          "x = f'''{'a'}'''", "x = f'{f\"{x}\"}'", "x = f'{x:{w}}'", "x = f'a\\nb{x}'",
          "x = f'{{}}{x}'", "x = f'''{\n x}'''", "x = '\\n'.join(f'{y}' for y in z)"]
    BAD = ["x = f'{d['k']}'", "x = f'{f'{x}'}'", "x = f'{\"\\n\".join(y)}'",
           "x = f'''{x # c\n}'''", "x = f'{\n x}'", "type X = int", "def f[T](x: T): pass",
           # the line that stopped the reader
           "out(f'  stage 1: Build {\"left the applier\\'s 2 alone\" if same else \"changed\"}')"]

    def test_what_3_11_parses_passes(self):
        for src in self.OK:
            self.assertEqual(problems_311(src), [], src)

    def test_what_3_11_refuses_is_found(self):
        for src in self.BAD:
            self.assertTrue(problems_311(src), src)


class TestTheRepo(unittest.TestCase):
    def test_every_python_file_parses_as_3_11_does(self):
        files = list(python_files())
        self.assertIn(os.path.join(REPO, 'examples', 'probes-128', 'read_probes.py'), files)
        found = []
        for p in files:
            with open(p, encoding='utf-8') as fh:
                found += [f'{os.path.relpath(p, REPO)}:{line}: {what}'
                          for line, what in problems_311(fh.read())]
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()
