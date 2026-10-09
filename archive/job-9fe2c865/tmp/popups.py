import os, sys, collections
sys.path.insert(0, os.getcwd())
from gdl.project import Project
SEEDS = "C:/Users/Public/Documents/Extron/GUI Designer"
A = Project.open(SEEDS + "/Afterburn 1035.gdl")
B = Project.open(SEEDS + "/Afterburn 1535.gdl")
pa = {p['name']: p for p in A.pages() if p['kind'] == 'popup'}
pb = {p['name']: p for p in B.pages() if p['kind'] == 'popup'}
same = grew = 0
print(f'{"popup":<34} {"1035 canvas":>12} {"1535 canvas":>12}   ratio')
for n in sorted(set(pa) & set(pb)):
    sa, sb = pa[n]['size'], pb[n]['size']
    if sa == sb: same += 1
    else: grew += 1
    r = f'{sb[0]/sa[0]:.3f}x{sb[1]/sa[1]:.3f}' if all(sa) else '?'
    print(f'{n[:34]:<34} {str(sa):>12} {str(sb):>12}   {r}')
print(f'\n{same} popups kept their canvas, {grew} were resized')
