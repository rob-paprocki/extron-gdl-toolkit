from v3 import *
from compose import render_page
FIN=dict(lhmul=1.2,bl=0.83,wadj=-4,binary=True,thr=1,clip=True,bold=True,aa=True)
o=dict(DEF); o.update(FIN)
new=render_v3(10,o).convert('RGB'); ref=refimg(10)
old=render_page(pages[10],assets,ref.size).convert('RGB')
box=(4,104,226,250); S=4
im=Image.new('RGB',((box[2]-box[0])*S,(box[3]-box[1])*S*3+16),(0,200,0))
for i,s in enumerate([ref,new,old]):
    im.paste(s.crop(box).resize(((box[2]-box[0])*S,(box[3]-box[1])*S),Image.NEAREST),(0,i*((box[3]-box[1])*S+8)))
im.save('q46.png'); print('ref / NEW / old', im.size)
