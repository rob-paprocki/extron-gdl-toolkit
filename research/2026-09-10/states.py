"""How do real Extron buttons differ between states? (raw graph walk)"""
import os, sys, glob, collections
sys.path.insert(0, os.getcwd())
from gdl.project import Project

def hexc(pr, obj, fld):
    c = pr.color(pr.field(obj, fld))
    return None if not c else '#{:02X}{:02X}{:02X}{:02X}'.format(c['A'], c['R'], c['G'], c['B'])

FIELDS = ('borderFillColorField', 'borderColorField', 'textColorField')

def raw_controls(p):
    """(page name, raw control) for every control, walking the graph directly."""
    proj = next(p.instances('PBProject'), None)
    fields = (('pagesField',), ('popupPagesField',)) if proj else ()
    if proj:
        for (fld,) in fields:
            for pg in p.items(p.field(proj, fld)):
                nm = p.field(pg, 'nameField')
                for c in p.items(p.field(pg, 'controlsField')):
                    yield nm, c

nstates = collections.Counter()
differs = collections.Counter()
total = 0
examples = []
per_file = {}

files = sorted(glob.glob('seeds/*.gdl'))
files.append('fixtures/gdl/Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
for f in files:
    p = Project.open(f)
    n2 = 0
    for pgname, c in raw_controls(p):
        if p.kind(c).rsplit('.', 1)[-1] != 'PBButton':
            continue
        sts = p.states(c)
        nstates[len(sts)] += 1
        if len(sts) < 2:
            continue
        n2 += 1
        total += 1
        fills = [hexc(p, s, 'borderFillColorField') for s in sts]
        for fld in FIELDS:
            vs = [hexc(p, s, fld) for s in sts]
            if len(set(vs)) > 1:
                differs[fld] += 1
        imgs = [str(p.field(s, 'buttonImageField')) for s in sts]
        if len(set(imgs)) > 1:
            differs['buttonImage'] += 1
        if len(examples) < 8 and len(set(fills)) > 1:
            examples.append((os.path.basename(f)[:20], pgname[:16],
                             str(p.field(c, 'nameField'))[:18], fills))
    per_file[os.path.basename(f)[:34]] = n2

print('states per button (all files):', dict(sorted(nstates.items())))
print(f'\n{total} buttons with 2+ states. How many DIFFER between states:')
for k, v in differs.most_common():
    print(f'  {k:<24} {v:>6}  ({100*v/total:.1f}%)' if total else k)
print('\nbuttons with 2+ states, per file:')
for k, v in sorted(per_file.items()):
    print(f'  {v:>5}  {k}')
print('\nexamples where the fill changes with state:')
for e in examples:
    print(f'  {e[0]:<20} {e[1]:<16} {e[2]:<18} {e[3]}')
