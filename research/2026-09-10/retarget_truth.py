"""Ground truth for `retarget --scale`.

Extron shipped the same Afterburn project at 1280x800 and 1920x1080. Whatever
they did by hand between those two is the correct answer. Compare it against
what our linear scale would have produced.
"""
import os, sys, collections
sys.path.insert(0, os.getcwd())
from gdl.project import Project

SEEDS = "seeds"
A = Project.open(SEEDS + "/Afterburn 1035.gdl")   # 1280x800
B = Project.open(SEEDS + "/Afterburn 1535.gdl")   # 1920x1080

def index(p):
    """(page kind, page name, control name, nth) -> (rect, page size)."""
    out = {}
    for pg in p.pages():
        seen = collections.Counter()
        for c in pg['controls']:
            n = c.get('name')
            k = (pg['kind'], pg['name'], n, seen[n])
            seen[n] += 1
            out[k] = (tuple(c['rect']), tuple(pg['size']))
    return out

ia, ib = index(A), index(B)
common = sorted(set(ia) & set(ib))
print(f'A {len(ia)} controls, B {len(ib)} controls, {len(common)} matched by name')
print(f'A-only {len(set(ia)-set(ib))}, B-only {len(set(ib)-set(ia))}')

SX, SY = 1920/1280, 1080/800     # 1.5, 1.35 -- what retarget --scale would do
exact = collections.Counter()
err = []
per_page = collections.defaultdict(lambda: [0, 0])
for k in common:
    (ax, ay, aw, ah), _ = ia[k]
    (bx, by, bw, bh), _ = ib[k]
    if None in (ax, ay, aw, ah, bx, by, bw, bh):
        continue
    pred = (round(ax*SX), round(ay*SY), round(aw*SX), round(ah*SY))
    got  = (bx, by, bw, bh)
    d = max(abs(p-g) for p, g in zip(pred, got))
    exact[d == 0] += 1
    per_page[k[1]][0] += (d == 0)
    per_page[k[1]][1] += 1
    if d:
        err.append((d, k, pred, got))

n = exact[True] + exact[False]
print(f'\nlinear scale reproduces Extron exactly: {exact[True]}/{n}  ({100*exact[True]/n:.1f}%)')
if err:
    err.sort(reverse=True)
    ds = [e[0] for e in err]
    ds.sort()
    print(f'off-by distribution (px): median {ds[len(ds)//2]}, p90 {ds[int(len(ds)*.9)]}, max {ds[-1]}')
    print(f'  <=1px {sum(d<=1 for d in ds)}   <=2px {sum(d<=2 for d in ds)}   <=4px {sum(d<=4 for d in ds)}   >4px {sum(d>4 for d in ds)}')
    print('\nworst 12:')
    for d, k, pred, got in err[:12]:
        print(f'  {d:>4}px  {k[1][:26]:<26} {str(k[2])[:22]:<22} pred {pred} got {got}')
print('\nper page (exact/total):')
for pg, (ok, tot) in sorted(per_page.items(), key=lambda kv: kv[1][0]/kv[1][1]):
    print(f'  {100*ok/tot:>5.1f}%  {ok:>4}/{tot:<4} {pg}')
