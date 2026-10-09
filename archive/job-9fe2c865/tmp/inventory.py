import glob, os, sys, collections
sys.path.insert(0, os.getcwd())
from gdl.project import Project

SEEDS = "C:/Users/Public/Documents/Extron/GUI Designer"
rows = []
for f in sorted(glob.glob(SEEDS + "/*.gdl")):
    base = os.path.basename(f)
    try:
        p = Project.open(f)
        pages = list(p.pages())
        main = [g for g in pages if g.get('kind') != 'popup']
        pops = [g for g in pages if g.get('kind') == 'popup']
        ctl = sum(len(g['controls']) for g in pages)
        sizes = collections.Counter(tuple(g['size']) for g in main if g.get('size'))
        canvas = sizes.most_common(1)[0][0] if sizes else None
        borders = p.border_resource_names()
        fonts = p.font_resource_names()
        rows.append((base, canvas, len(main), len(pops), ctl, len(borders), sorted(fonts)))
    except Exception as e:
        rows.append((base, 'ERROR', type(e).__name__, str(e)[:60], '', '', ''))

w = max(len(r[0]) for r in rows)
for r in rows:
    if r[1] == 'ERROR':
        print(f'{r[0]:<{w}}  !! {r[2]}: {r[3]}')
        continue
    base, canvas, nmain, npop, ctl, nb, fonts = r
    cv = f'{canvas[0]}x{canvas[1]}' if canvas else '?'
    print(f'{base:<{w}}  {cv:>9}  {nmain:>2}pg {npop:>3}pop {ctl:>5}ctl  {nb:>3}bdr  {",".join(fonts)}')
