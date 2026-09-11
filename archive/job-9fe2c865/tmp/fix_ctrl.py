"""Repair control characters a past heredoc wrote into tracked text files.

CLAUDE.md warns that backslash-v and backslash-a get interpreted on the way
through a shell heredoc. docs/from-scratch.md still carries three instances:
'\v1.0' became 0x0B, 'examples\add' became 'examples' + 0x07 + 'dd', and
'C:\gdlwork\new_ProjectGCP' lost its '\n' to a real newline.
"""
import os
import re
import sys

ROOT = sys.argv[1]
SKIP = {'.git', 'fixtures', 'archive', 'vendor', 'seeds', '__pycache__', 'gdl'}
EXTS = ('.md', '.py', '.ps1', '.json', '.yml', '.txt')

FIXES = [
    (b'WindowsPowerShell\x0b1.0', b'WindowsPowerShell\\v1.0'),
    (b'examples\x07dd-page-and-popup', b'examples\\add-page-and-popup'),
    (b'C:\\gdlwork\x0aew_ProjectGCP', b'C:\\gdlwork\\new_ProjectGCP'),
]
BAD = re.compile(rb'[\x00-\x08\x0b\x0c\x0e-\x1f]')

for dirpath, dirnames, filenames in os.walk(ROOT):
    rel = os.path.relpath(dirpath, ROOT)
    if rel.split(os.sep)[0] in SKIP:
        dirnames[:] = []
        continue
    for fn in filenames:
        if not fn.endswith(EXTS):
            continue
        path = os.path.join(dirpath, fn)
        with open(path, 'rb') as fh:
            data = fh.read()
        new = data
        for old, good in FIXES:
            new = new.replace(old, good)
        if new != data:
            with open(path, 'wb') as fh:
                fh.write(new)
            print(f'fixed   {os.path.relpath(path, ROOT)}')
        for m in BAD.finditer(new):
            line = new.count(b'\n', 0, m.start()) + 1
            print(f'REMAINS {os.path.relpath(path, ROOT)}:{line} byte 0x{m.group()[0]:02x}')
        for m in re.finditer(rb'\n(ew_ProjectGCP|ew_[A-Za-z])', new):
            line = new.count(b'\n', 0, m.start()) + 2
            print(f'SUSPECT {os.path.relpath(path, ROOT)}:{line} line starts with {m.group(1)!r}')
