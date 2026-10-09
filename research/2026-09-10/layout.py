import os, sys, json
sys.path.insert(0, os.getcwd())
from gdl.container import open_payload
from gdl.project import Project

SEEDS = "seeds"
f = SEEDS + "/Afterburn 1035.gdl"
z = open_payload(f)
names = z.namelist()
print(len(names), 'entries; json:', [n for n in names if n.lower().endswith('.json')][:5])
lay = json.loads(z.read('layout.json').decode('utf-8-sig'))
print('top keys:', sorted(lay)[:15])
pages = lay.get('Pages') or lay.get('pages') or []
print(len(pages), 'pages;  keys:', sorted(pages[0])[:20] if pages else '')
auth = {p['name']: (p['size'], p['kind']) for p in Project.open(f).pages()}
diff = 0
print(f'\n{"page":<34} {"layout.json":>13} {"authored":>13}')
for p in pages:
    nm = p.get('Name') or p.get('name')
    w = p.get('Width') or p.get('width'); h = p.get('Height') or p.get('height')
    a = auth.get(nm)
    if not a:
        continue
    mark = '' if (w, h) == tuple(a[0]) else '  <-- DIFFER'
    if mark:
        diff += 1
    print(f'{str(nm)[:34]:<34} {f"{w}x{h}":>13} {f"{a[0][0]}x{a[0][1]}":>13} {a[1][:5]}{mark}')
print(f'\n{diff} page(s) where layout.json disagrees with the authored canvas')
