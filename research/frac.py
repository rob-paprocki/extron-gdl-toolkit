"""Text layout with exact fractional advances (what GUI Designer does)."""
import os, re
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from compose import face, FONTDIR, FILES, PT

_adv={}
def advtab(name,bold,italic):
    k=(name,bold,italic)
    if k in _adv: return _adv[k]
    fn=FILES.get(k) or FILES.get((name,0,0)) or 'arial.ttf'
    p=os.path.join(FONTDIR,fn)
    if not os.path.exists(p): p=os.path.join('C:/Windows/Fonts',fn)
    t=TTFont(p, lazy=True)
    hm=t['hmtx']; cm=t.getBestCmap(); upem=t['head'].unitsPerEm
    d={}
    for cp,g in cm.items():
        try: d[chr(cp)]=hm[g][0]/upem
        except Exception: pass
    _adv[k]=(d, d.get(' ',0.25))
    return _adv[k]

def adv(s, tab, px):
    d,sp=tab
    return sum(d.get(ch,sp) for ch in s)*px

def wrap_frac(text, tab, px, width):
    out=[]
    for para in text.replace('\r\n','\n').replace('\r','\n').split('\n'):
        if not para: out.append(''); continue
        line=''
        for word in re.split(r'(\s+)', para):
            if not word: continue
            trial=line+word
            if adv(trial,tab,px)<=width or not line.strip():
                while adv(trial,tab,px)>width and len(trial)>1:
                    cut=len(trial)-1
                    while cut>1 and adv(trial[:cut],tab,px)>width: cut-=1
                    out.append(trial[:cut]); trial=trial[cut:]
                line=trial
            else:
                out.append(line.rstrip()); line=word.lstrip()
        out.append(line.rstrip())
    return out

def draw_frac(draw, xy, text, fnt, tab, px, fill, aa=True):
    d,sp=tab
    x,y=xy
    if not aa: draw.fontmode='1'
    for ch in text:
        if ch!=' ':
            draw.text((x,y), ch, font=fnt, fill=fill, anchor='la')
        x += d.get(ch,sp)*px
