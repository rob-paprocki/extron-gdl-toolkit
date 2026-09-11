import os, sys, glob, collections
sys.path.insert(0, os.getcwd())
from gdl.project import Project

names = collections.Counter()
counts = collections.Counter()
pressfb = collections.Counter()
blink = collections.Counter()
combos = collections.Counter()

files = sorted(glob.glob('C:/Users/Public/Documents/Extron/GUI Designer/*.gdl'))
files.append('fixtures/gdl/Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
for f in files:
    p = Project.open(f)
    proj = next(p.instances('PBProject'), None)
    if proj is None:
        continue
    for fld in ('pagesField', 'popupPagesField'):
        for pg in p.items(p.field(proj, fld)):
            for c in p.items(p.field(pg, 'controlsField')):
                if p.kind(c).rsplit('.', 1)[-1] != 'PBButton':
                    continue
                sts = p.states(c)
                counts[len(sts)] += 1
                combo = tuple(str(p.field(s, 'nameField')) for s in sts)
                combos[combo] += 1
                for s in sts:
                    names[str(p.field(s, 'nameField'))] += 1
                    v = p.field(s, '<TLPPressFeedbackStateID>k__BackingField')
                    pressfb[v] += 1
                    b = p.field(s, 'blinkingField')
                    blink[str(b)[-24:] if b else None] += 1

print('state COUNT per button:', dict(sorted(counts.items())))
print('\nstate NAME frequency:')
for k, v in names.most_common(12):
    print(f'  {v:>6}  {k}')
print('\nmost common state-name TUPLES per button:')
for k, v in combos.most_common(10):
    print(f'  {v:>6}  {k}')
print('\nTLPPressFeedbackStateID values:')
for k, v in pressfb.most_common(8):
    print(f'  {v:>6}  {k}')
