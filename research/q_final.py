"""Final accounting: text-rect residual before, after, and with an oracle shift."""
import sys, os, re
import numpy as np
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
from PIL import Image, ImageDraw
import compose2
from compose import load, rgba, face, metrics
from gdl_data import popup_ref

REF = r'C:/Users/Public/Documents/Extron/GUI Designer/Snapshots/J26450039 Liberty Bank Boardroom 2_0_0/Individual'
BEFORE = dict(aa='L')
AFTER = dict(aa='autofill', aagamma=0.7, dx=-0.5, wrapk=1 / 3,
             bold='smear', boldpx=1, bold_dpx=0.75, lhk=1.19, ak=0.825)
j, assets = load(SP + '/src/Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
pages = {p['ID']: p for p in j['Pages'] + j['PopupPages']}


def cov(rec, px, dy, dx, aa):
    x, y, w, h = rec['rect']
    m = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(m)
    d.fontmode = 'L'
    f = face(rec['fname'], rec['bold'], rec['italic'], px)
    ftasc = metrics(f)[0]
    smear = 1 if rec['bold'] else 0
    lines = compose2.wrap(rec['text'], f, w - px / 3, lambda s, ff: d.textlength(s, font=ff))
    lh, A = 1.19 * px, 0.825 * px
    vert, horz = rec['align'] // 3, rec['align'] % 3
    top = 0 if vert == 2 else ((h - lh * len(lines)) / 2 if vert == 1 else h - lh * len(lines))
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f) + smear
        tx = (0 if horz == 1 else (w - tw if horz == 2 else (w - tw) / 2)) - 0.5 + dx
        for s in range(smear + 1):
            d.text((tx + s, top + i * lh + A - ftasc + dy), ln, font=f, fill=255, anchor='la')
    a = np.asarray(m, dtype=np.float32) / 255.0
    return (a >= 2 / 255).astype(np.float32) if not aa else np.clip(a, 0, 1) ** 0.7


def scan(opt, oracle=False):
    tot = area = 0
    for fn in sorted(os.listdir(REF)):
        pid = int(re.search(r'_Id(\d+)\.png$', fn).group(1))
        if pid == 65535:
            continue
        ref = np.asarray(Image.open(os.path.join(REF, fn)).convert('RGB'), int)
        H, W = ref.shape[:2]
        pg = pages[pid]
        M = np.asarray(compose2.render_page(pg, assets, (W, H), opt=opt).convert('RGB'), int)
        A = np.asarray(compose2.render_page(pg, assets, (W, H), draw_txt=False, opt=opt).convert('RGB'), float)
        cvv = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        compose2.render_page(pg, assets, (W, H), canvas=cvv, draw_txt=False, opt=opt)
        alpha = np.asarray(cvv)[:, :, 3].astype(float)
        bad = np.abs(M - ref).max(2) >= 24
        for c in (pg.get('Controls') or []):
            if popup_ref(c) or c.get('FlattenText'):
                continue
            sts = c.get('States') or []
            st = sts[c.get('TLPDefaultStateID', 0)] if sts else None
            src = st or c
            t = src.get('Text') or c.get('Text') or ''
            if not t.strip():
                continue
            x, y, w, h = c['Left'], c['Top'], c['Width'], c['Height']
            if x < 0 or y < 0 or x + w > W or y + h > H or w < 4 or h < 4:
                continue
            sl = (slice(y, y + h), slice(x, x + w))
            n = int(bad[sl].sum())
            area += w * h
            if oracle:
                f = src.get('Font') or c.get('Font') or {}
                stl = f.get('Style') or {}
                rec = dict(rect=(x, y, w, h), text=t, fname=f.get('Name', 'Arial'),
                           bold=int(bool(stl.get('Bold'))), italic=int(bool(stl.get('Italic'))),
                           align=src.get('TextAlignment', c.get('TextAlignment', 3)))
                px = f.get('PointSize', 12) * 1.375 + (0.75 if rec['bold'] else 0.0)
                aa = (alpha[sl] > 128).mean() >= 0.5
                tc = np.array((rgba(src.get('TextColor')) or rgba(c.get('TextColor')) or (255, 255, 255, 255))[:3], float)
                art = A[sl]
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        cc = cov(rec, px, dy, dx, aa)
                        out = art + cc[:, :, None] * (tc[None, None, :] - art)
                        k = int((np.abs(np.rint(out).astype(int) - ref[sl]).max(2) >= 24).sum())
                        n = min(n, k)
            tot += n
    return tot, area


b, area = scan(BEFORE)
a, _ = scan(AFTER)
o, _ = scan(AFTER, oracle=True)
print(f"text-control rect area (Offline page excluded): {area}")
print(f"BEFORE  bad px in text rects: {b:7d}  ({100*b/area:.2f}% of rect area)")
print(f"AFTER   bad px in text rects: {a:7d}  ({100*a/area:.2f}%)   -> {100*(1-a/b):.1f}% removed")
print(f"ORACLE  per-control shift   : {o:7d}  ({100*o/area:.2f}%)")
print()
print(f"correctable systematics found & fixed : {b-a:7d}  ({100*(b-a)/b:.1f}% of the original text residual)")
print(f"placement rule still imperfect        : {a-o:7d}  ({100*(a-o)/b:.1f}%)")
print(f"glyph rasterizer difference (floor)   : {o:7d}  ({100*o/b:.1f}%)")
