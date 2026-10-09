"""Did the BUILT file keep the popup canvases, and how does it compare to
Extron's own hand-authored 1535?"""
import os, sys, json, collections
sys.path.insert(0, os.getcwd())
from gdl.container import open_payload
from gdl.project import Project

W = 'archive/job-9fe2c865/tmp/rt'
SEEDS = "seeds"
OURS = W + '/retargeted.gdl'
THEIRS = SEEDS + '/Afterburn 1535.gdl'

lay = json.loads(open_payload(OURS).read('layout.json').decode('utf-8-sig'))
print('BUILT payload:')
print('  ScreenSize', lay.get('ScreenSize'), ' PartNumber', lay.get('PartNumber'),
      ' Platform', lay.get('Platform'))
c = collections.Counter((p['Width'], p['Height']) for p in lay['PopupPages'])
for s, n in sorted(c.items()):
    print(f'  {n:>2} popup(s) at {s[0]}x{s[1]}')
pg = collections.Counter((p['Width'], p['Height']) for p in lay['Pages'])
for s, n in sorted(pg.items()):
    print(f'  {n:>2} page(s)  at {s[0]}x{s[1]}')

# Did Build relocate anything to 0,0 that was not there before?
plan = json.load(open(W + '/plan.json', encoding='utf-8'))
want = {(o['page'], o['control']): o['fields'] for o in plan['controls']}
built = {}
for coll in ('Pages', 'PopupPages'):
    for p in lay[coll]:
        for ctl in p.get('Controls') or []:
            built[(p['ID'], ctl['ID'])] = (ctl['Left'], ctl['Top'],
                                           ctl['Width'], ctl['Height'])
at00 = bad = seen = 0
for k, f in want.items():
    g = built.get(k)
    if g is None:
        continue
    seen += 1
    exp = (f['leftField'], f['topField'], f['widthField'], f['heightField'])
    if g != exp:
        bad += 1
        if g[0] == 0 and g[1] == 0 and exp[:2] != (0, 0):
            at00 += 1
print(f'\n{seen} planned controls found in the build; {bad} differ from the plan, '
      f'{at00} of those relocated to 0,0')

# Ground truth: ours vs Extron's own 1535.
def index(p):
    out = {}
    for page in p.pages():
        seen = collections.Counter()
        for ctl in page['controls']:
            n = ctl.get('name')
            k = (page['kind'], page['name'], n, seen[n]); seen[n] += 1
            out[k] = tuple(ctl['rect'])
    return out
a, b = index(Project.open(OURS)), index(Project.open(THEIRS))
keys = [k for k in set(a) & set(b) if None not in a[k] and None not in b[k]]
d = sorted(max(abs(x - y) for x, y in zip(a[k], b[k])) for k in keys)
print(f'\nvs Extron\'s own hand-authored 1535 ({len(keys)} matched controls):')
print(f'  identical {100*sum(v==0 for v in d)/len(d):.1f}%   within 4px '
      f'{100*sum(v<=4 for v in d)/len(d):.1f}%   within 16px {100*sum(v<=16 for v in d)/len(d):.1f}%')
print(f'  median {d[len(d)//2]}px   p90 {d[int(len(d)*.9)]}px   max {d[-1]}px')
