from qlib import *
from compose import face, PT, rgba, diff_stats, FONTDIR, FILES
from gdl_data import popup_ref
from frac import advtab, adv, wrap_frac
from fontTools.ttLib import TTFont
from PIL import ImageDraw
import numpy as np, os, re

_tm={}
def typo(name,b,i):
    k=(name,b,i)
    if k in _tm: return _tm[k]
    fn=FILES.get(k) or FILES.get((name,0,0)) or 'arial.ttf'
    p=os.path.join(FONTDIR,fn)
    if not os.path.exists(p): p=os.path.join('C:/Windows/Fonts',fn)
    t=TTFont(p,lazy=True); u=t['head'].unitsPerEm; o=t['OS/2']
    _tm[k]=(o.sTypoAscender/u, -o.sTypoDescender/u)
    return _tm[k]

DEF=dict(dy=0.0,dx=0.0,clip=True,aa=False,bold=True,wadj=0,scale=PT,metrics='typo',lg=0.0)

def draw_one(canvas,c,o):
    st=(c.get('States') or [None])[c.get('TLPDefaultStateID',0)] if c.get('States') else None
    src=st or c
    text=src.get('Text') or c.get('Text') or ''
    if not text.strip(): return
    f=src.get('Font') or c.get('Font') or {}
    sty=f.get('Style') or {}
    b,i=int(bool(sty.get('Bold'))),int(bool(sty.get('Italic')))
    nm=f.get('Name','Arial'); ps=f.get('PointSize',12); px=ps*o['scale']
    fnt=face(nm,b,i,px); tab=advtab(nm,b,i)
    col=rgba(src.get('TextColor')) or rgba(c.get('TextColor')) or (255,255,255,255)
    al=src.get('TextAlignment',c.get('TextAlignment',3))
    x,y,w,h=c['Left'],c['Top'],c['Width'],c['Height']
    if o['metrics']=='typo':
        ta,td=typo(nm,b,i); asc=ta*px; lh=(ta+td+o['lg'])*px
    else:
        a_,d_=fnt.getmetrics(); asc=a_; lh=a_+d_
    layer=Image.new('RGBA',canvas.size,(0,0,0,0)); d=ImageDraw.Draw(layer)
    if not o['aa']: d.fontmode='1'
    lines=wrap_frac(text,tab,px,w+o['wadj'])
    block=lh*len(lines); vert=al//3; horz=al%3
    top = y if vert==2 else (y+(h-block)/2 if vert==1 else y+h-block)
    smear=[(0,0)]+([(1,0)] if (o['bold'] and b) else [])
    at,_=tab
    for k,ln in enumerate(lines):
        tw=adv(ln,tab,px)
        tx = x if horz==1 else (x+w-tw if horz==2 else x+(w-tw)/2)
        by = top + k*lh + asc + o['dy']          # baseline
        for ex,ey in smear:
            px_=tx+o['dx']+ex
            for ch in ln:
                if ch!=' ':
                    d.text((px_, by+ey), ch, font=fnt, fill=col, anchor='ls')
                px_+=at.get(ch,0.25)*px
    if o['clip']:
        a=np.array(layer.split()[3]).astype(np.int32)
        m=np.zeros(a.shape,np.int32); m[max(0,y):y+h, max(0,x):x+w]=1
        layer.putalpha(Image.fromarray((a*m).astype('uint8')))
    canvas.alpha_composite(layer)

_nt={}
def nt_of(pid):
    if pid not in _nt:
        r=refimg(pid); _nt[pid]=render_page(pages[pid],assets,r.size,draw_txt=False)
    return _nt[pid]
def pct(pid,**kw):
    o=dict(DEF); o.update(kw); ref=refimg(pid); cv=nt_of(pid).copy()
    for c in pages[pid]['Controls']:
        if popup_ref(c) or c.get('FlattenText'): continue
        draw_one(cv,c,o)
    return diff_stats(cv,ref)['pct_bad'], cv
if __name__=='__main__':
    for n,kw in [('v2 typo',dict()),('v2 typo AA',dict(aa=True)),
                 ('v2 win',dict(metrics='win')),
                 ('v2 typo lg=.2',dict(lg=0.2)),
                 ('v2 typo nobold',dict(bold=False)),
                 ('v2 typo dy-0.5',dict(dy=-0.5)),('v2 typo dy+0.5',dict(dy=0.5)),
                 ('v2 typo dx-0.5',dict(dx=-0.5)),]:
        a,_=pct(10,**kw); b,_=pct(8,**kw)
        print(f'{n:20} p10={a:.3f}  p8={b:.3f}')
