"""What transform DID Extron apply between 1035 and 1535?

Fit each rect component independently as b = m*a + c by least squares, report
how much of the variance that explains, and test named hypotheses.
"""
import os, sys, collections, statistics
sys.path.insert(0, os.getcwd())
from gdl.project import Project

SEEDS = "seeds"
A = Project.open(SEEDS + "/Afterburn 1035.gdl")
B = Project.open(SEEDS + "/Afterburn 1535.gdl")

def index(p):
    out = {}
    for pg in p.pages():
        seen = collections.Counter()
        for c in pg['controls']:
            n = c.get('name')
            k = (pg['kind'], pg['name'], n, seen[n]); seen[n] += 1
            out[k] = (tuple(c['rect']), tuple(pg['size']), pg['kind'])
    return out

ia, ib = index(A), index(B)
# Standard pages only: popups have their own canvas and scale by their own rule.
keys = [k for k in set(ia) & set(ib)
        if ia[k][2] == 'page' and None not in ia[k][0] and None not in ib[k][0]]
print(f'{len(keys)} controls on standard pages\n')

def fit(i):
    xs = [ia[k][0][i] for k in keys]
    ys = [ib[k][0][i] for k in keys]
    n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
    sxy = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    sxx = sum((x-mx)**2 for x in xs)
    m = sxy/sxx; c = my - m*mx
    resid = [y - (m*x+c) for x, y in zip(xs, ys)]
    sst = sum((y-my)**2 for y in ys)
    r2 = 1 - sum(r*r for r in resid)/sst
    return m, c, r2, resid

for i, nm in enumerate(('left', 'top', 'width', 'height')):
    m, c, r2, resid = fit(i)
    ar = sorted(abs(r) for r in resid)
    print(f'{nm:<7} b = {m:.4f}*a + {c:+8.2f}   R2={r2:.5f}   '
          f'|resid| med {ar[len(ar)//2]:5.1f}  p90 {ar[int(len(ar)*.9)]:6.1f}  max {ar[-1]:6.1f}')

print()
SX, SY = 1.5, 1.35
def score(name, fx, fy, fw, fh):
    d = [max(abs(fx(ia[k][0][0])-ib[k][0][0]), abs(fy(ia[k][0][1])-ib[k][0][1]),
             abs(fw(ia[k][0][2])-ib[k][0][2]), abs(fh(ia[k][0][3])-ib[k][0][3])) for k in keys]
    d.sort()
    ex = sum(v == 0 for v in d)
    print(f'{name:<34} exact {100*ex/len(d):5.1f}%   <=2px {100*sum(v<=2 for v in d):5.1f}%   '
          f'med {d[len(d)//2]:5.1f}  max {d[-1]:5.1f}')

score('linear per-axis (current)', lambda v: round(v*SX), lambda v: round(v*SY),
      lambda v: round(v*SX), lambda v: round(v*SY))
score('uniform 1.35, centered X', lambda v: round(96+v*SY), lambda v: round(v*SY),
      lambda v: round(v*SY), lambda v: round(v*SY))
score('uniform 1.5, centered Y', lambda v: round(v*SX), lambda v: round(-60+v*SX),
      lambda v: round(v*SX), lambda v: round(v*SX))
mx, cx, _, _ = fit(0); my_, cy, _, _ = fit(1); mw, cw, _, _ = fit(2); mh, ch, _, _ = fit(3)
score('best-fit affine per axis', lambda v: round(mx*v+cx), lambda v: round(my_*v+cy),
      lambda v: round(mw*v+cw), lambda v: round(mh*v+ch))
