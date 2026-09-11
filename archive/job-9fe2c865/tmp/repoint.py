"""Point this session's research scripts at the repo instead of C: and the job dir."""
import glob

SUBS = [
    ('C:/Users/Public/Documents/Extron/GUI Designer', 'seeds'),
    ("os.environ['CLAUDE_JOB_DIR'] + '/tmp/rt'", "'archive/job-9fe2c865/tmp/rt'"),
    ("os.environ['CLAUDE_JOB_DIR']+'/tmp/rt'", "'archive/job-9fe2c865/tmp/rt'"),
]
for path in sorted(glob.glob('research/2026-09-10/*.py')):
    with open(path, encoding='utf-8') as fh:
        s = fh.read()
    o = s
    for a, b in SUBS:
        s = s.replace(a, b)
    if s != o:
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(s)
    left = [ln.strip() for ln in s.splitlines()
            if 'CLAUDE_JOB_DIR' in ln or 'C:/' in ln or 'C:\\' in ln]
    print(f"{path:<46} {'changed' if s != o else 'as-is':<8} {left[:2]}")
