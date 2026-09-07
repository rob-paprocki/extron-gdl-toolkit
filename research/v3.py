"""v3: per-control RGBA layer + binary-alpha composite + fractional text layout."""
from qlib import *
from compose import face, PT, rgba, diff_stats, paste
from gdl_data import popup_ref
from frac import advtab, adv, wrap_frac
from v2 import typo
import os
from fontTools.ttLib import TTFont as _TTF
from compose import FONTDIR as _FD, FILES as _FL
_wm={}
def winm(name,b,i):
    k=(name,b,i)
    if k in _wm: return _wm[k]
    fn=_FL.get(k) or _FL.get((name,0,0)) or 'arial.ttf'
    p_=os.path.join(_FD,fn)
    if not os.path.exists(p_): p_=os.path.join('C:/Windows/Fonts',fn)
    t=_TTF(p_,lazy=True); u=t['head'].unitsPerEm; o_=t['OS/2']
    _wm[k]=(o_.usWinAscent/u, o_.usWinDescent/u); return _wm[k]
from PIL import ImageDraw
import numpy as np, io

DEF=dict(dy=0.0,dx=0.0,clip=True,bold=True,wadj=-4,scale=PT,metrics='typo',thr=1,binary=True,aa=True,lhmul=None,bl=None)

def blit(canvas, layer, thr, binary):
    if not binary:
        canvas.alpha_composite(layer); return
    a=np.array(layer.split()[3])
    m=Image.fromarray(np.where(a>=thr,255,0).astype('uint8'))
    canvas.paste(layer.convert('RGB'), (0,0), m)

def text_into(layer, c, o):
    st=(c.get('States') or [None])[c.get('TLPDefaultStateID',0)] if c.get('States') else None
    src=st or c
    text=src.get('Text') or c.get('Text') or ''
    if not text.strip() or c.get('FlattenText'): return
    f=src.get('Font') or c.get('Font') or {}
    sty=f.get('Style') or {}
    b,i=int(bool(sty.get('Bold'))),int(bool(sty.get('Italic')))
    nm=f.get('Name','Arial'); ps=f.get('PointSize',12); px=ps*o['scale']
    fnt=face(nm,b,i,px); tab=advtab(nm,b,i)
    col=rgba(src.get('TextColor')) or rgba(c.get('TextColor')) or (255,255,255,255)
    al=src.get('TextAlignment',c.get('TextAlignment',3))
    x,y,w,h=c['Left'],c['Top'],c['Width'],c['Height']
    if o.get('css'):
        wa,wd=winm(nm,b,i); ta_,td_=typo(nm,b,i)
        lh=(wa+wd)*px
        asc=(lh-(ta_+td_)*px)/2 + ta_*px
    elif o.get('gdi'):
        src_=o['gdi']            # 'typo' or 'win'
        t_=typo(nm,b,i) if src_=='typo' else winm(nm,b,i)
        asc=round(t_[0]*px); dsc=round(t_[1]*px); lh=asc+dsc
    elif o['lhmul'] is not None:
        lh=o['lhmul']*px; asc=o['bl']*px
    elif o['metrics']=='typo':
        ta,td=typo(nm,b,i); asc=ta*px; lh=(ta+td)*px
    else:
        a_,d_=fnt.getmetrics(); asc=a_; lh=a_+d_
    tl=Image.new('RGBA',layer.size,(0,0,0,0)); d=ImageDraw.Draw(tl)
    if not o['aa']: d.fontmode='1'
    lines=wrap_frac(text,tab,px,w+o['wadj'])
    block=lh*len(lines); vert=al//3; horz=al%3
    if o.get('gdi'):
        import math
        top = y if vert==2 else (y+math.floor((h-block)/2) if vert==1 else y+h-block)
    else:
        top = y if vert==2 else (y+(h-block)/2 if vert==1 else y+h-block)
    at,_=tab
    for k,ln in enumerate(lines):
        tw=(d.textlength(ln,font=fnt) if o.get('roundadv') else adv(ln,tab,px))
        tx = x if horz==1 else (x+w-tw if horz==2 else x+(w-tw)/2)
        by = top+k*lh+asc+o['dy']
        for ex,ey in ([(0,0),(1,0)] if (o['bold'] and b) else [(0,0)]):
            cx=tx+o['dx']+ex
            if o.get('roundadv'):
                d.text((cx,by+ey),ln,font=fnt,fill=col,anchor='ls')
            else:
                for ch in ln:
                    if ch!=' ': d.text((cx,by+ey),ch,font=fnt,fill=col,anchor='ls')
                    cx+=at.get(ch,0.25)*px
    if o['clip']:
        aa_=np.array(tl.split()[3]).astype(np.int32)
        m=np.zeros(aa_.shape,np.int32); m[max(0,y):y+h, max(0,x):x+w]=1
        tl.putalpha(Image.fromarray((aa_*m).astype('uint8')))
    layer.alpha_composite(tl)

def ctl_art(layer, c, assets):
    kind=c['__type'].split(':')[0]
    states=c.get('States') or []
    st=states[c.get('TLPDefaultStateID',0)] if states else None
    base=c.get('TLPImageID')
    if kind=='PBLevel': base=c.get('TLPMinValueImageID',base)
    elif st is not None: base=st.get('TLPImageID',base)
    x,y,w,h=c['Left'],c['Top'],c['Width'],c['Height']
    paste(layer,assets,base,x,y)
    mx=c.get('TLPMaxValueImageID')
    if mx is not None and mx!=base and mx in assets:
        o_=c.get('Orientation',0)
        clip={2:(0,h//2,w,h),3:(0,0,w,h//2),1:(w//2,0,w,h)}.get(o_,(0,0,w//2,h))
        paste(layer,assets,mx,x,y,clip=clip)
    ind=c.get('SliderIndicatorImageID')
    if ind and ind in assets:
        iw=c.get('SliderIndicatorWidth') or w; ih=c.get('SliderIndicatorHeight') or h
        paste(layer,assets,ind,x+(w-iw)//2,y+(h-ih)//2)

def render_v3(pid,o,size=(1280,800)):
    pg=pages[pid]
    canvas=Image.new('RGBA',size,(0,0,0,255))
    bg=Image.new('RGBA',size,(0,0,0,0)); paste(bg,assets,pg.get('TLPImageID'),0,0)
    blit(canvas,bg,o['thr'],o['binary'])
    for c in (pg.get('Controls') or []):
        if popup_ref(c): continue
        L=Image.new('RGBA',size,(0,0,0,0))
        ctl_art(L,c,assets)
        text_into(L,c,o)
        blit(canvas,L,o['thr'],o['binary'])
    return canvas

def pct(pid,**kw):
    o=dict(DEF); o.update(kw)
    return diff_stats(render_v3(pid,o), refimg(pid))['pct_bad']

if __name__=='__main__':
    for n,kw in [('v3 binary thr=1',dict()),
                 ('v3 binary thr=64',dict(thr=64)),('v3 binary thr=128',dict(thr=128)),
                 ('v3 straight alpha',dict(binary=False)),
                 ('v3 binary dy-0.25',dict(dy=-0.25)),
                 ('v3 binary wadj0',dict(wadj=0)),
                 ('v3 binary noAAtext',dict(aa=False))]:
        print(f'{n:22} p10={pct(10,**kw):.3f}  p8={pct(8,**kw):.3f}')
