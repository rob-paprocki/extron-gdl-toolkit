"""Measured fix: PBShape with TLPImageID == -1 paints the skin's rounded-rect
surface; page with TLPImageID == -1 paints BackgroundFillColor as a scrim."""
import sys, os, re, statistics
sys.path.insert(0,'.')
import compose
from compose import load, diff_stats, rgba, paste, render_control
from PIL import Image, ImageDraw

SKIN_SURFACE = (36,38,52,255)   # Afterburn "6400x4000_bg1" page colour, ARGB FF242634
SKIN_RADIUS  = 10               # skin resource "Afterburn - 10 Radius 0 Thick"
SCRIM_ALPHA  = 165              # 65% - matches the 166 baked into asset 36

def render_page2(pg, assets, size, ox=0, oy=0, canvas=None, draw_txt=True):
    if canvas is None:
        canvas = Image.new('RGBA', size, (0,0,0,255))
        f = rgba(pg.get('BackgroundFillColor'))
        if pg.get('TLPImageID',-1) == -1 and f and f[3]:
            a = SCRIM_ALPHA if pg.get('Modal') else f[3]
            canvas.paste((f[0],f[1],f[2],a), [0,0,*size])
    paste(canvas, assets, pg.get('TLPImageID'), ox, oy)
    for c in (pg.get('Controls') or []):
        if c['__type'].split(':')[0]=='PBShape' and c.get('TLPImageID',-1)==-1:
            lay = Image.new('RGBA', size, (0,0,0,0))
            ImageDraw.Draw(lay).rounded_rectangle(
                [c['Left']+ox, c['Top']+oy,
                 c['Left']+ox+c['Width']-1, c['Top']+oy+c['Height']-1],
                radius=SKIN_RADIUS, fill=SKIN_SURFACE)
            canvas.alpha_composite(lay)
            continue
        render_control(canvas, c, assets, ox, oy, draw_txt)
    return canvas

SNAP=r'C:/Users/Public/Documents/Extron/GUI Designer/Snapshots/J26450039 Liberty Bank Boardroom 2_0_0/Individual'
j,assets=load(r'src/Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
pages={p['ID']:p for p in j['Pages']+j['PopupPages']}
rows=[]
for f in sorted(os.listdir(SNAP)):
    pid=int(re.search(r'_Id(\d+)\.png$',f).group(1))
    ref=Image.open(os.path.join(SNAP,f)).convert('RGB')
    a=diff_stats(compose.render_page(pages[pid],assets,ref.size),ref)['pct_bad']
    b=diff_stats(render_page2(pages[pid],assets,ref.size),ref)['pct_bad']
    rows.append((f,a,b))
for f,a,b in sorted(rows,key=lambda r:-r[1])[:6]:
    print('%-46s %7.3f -> %7.3f'%(f[:46],a,b))
A=[r[1] for r in rows]; B=[r[2] for r in rows]
print('median %.3f -> %.3f   mean %.3f -> %.3f   changed: %s'%(
    statistics.median(A),statistics.median(B),statistics.mean(A),statistics.mean(B),
    [r[0] for r in rows if abs(r[1]-r[2])>1e-9]))
