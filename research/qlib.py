import sys, os
SP=r'C:/Users/rob.paprocki/AppData/Local/Temp/claude/C--Remote-Programming-USA-CT-Middletown-245-Boardroom--claude-worktrees-extron-gdl-files-49260a/eb092daf-a13f-462f-8130-eae84b0c21c5/scratchpad'
sys.path.insert(0,SP)
from compose import load, render_page
from PIL import Image, ImageChops
import numpy as np
GDL=SP+'/src/Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl'
REF=r'C:/Users/Public/Documents/Extron/GUI Designer/Snapshots/J26450039 Liberty Bank Boardroom 2_0_0/Individual'
FILES={10:'3110 - Adv Device Connectivity Details_Id10.png',8:'3112 - Adv Video Connectivity Details_Id8.png',
       18:'3100 - Adv Device Connectivity Details_Id18.png',15:'3000 - Tech_Id15.png',
       20:'2000 - Main - Presentation_Id20.png',6:'3400 - Adv Matrix Routing_Id6.png',
       5:'3111 - Adv TP Connectivity Details_Id5.png',9:'3113 - Adv SSI Connectivity Details_Id9.png',
       12:'3600 - Adv Camera Connectivity Details_Id12.png',1:'3500 - Adv Audio Devices_Id1.png',
       21:'1000 - Home_Id21.png',4:'3300 - Adv Display Statuses and Controls_Id4.png'}
j,assets=load(GDL); pages={p['ID']:p for p in j['Pages']+j['PopupPages']}

def refimg(pid): return Image.open(os.path.join(REF,FILES[pid])).convert('RGB')

def ink(a,b,box,thr=32):
    d=np.array(ImageChops.difference(a.crop(box),b.crop(box)).convert('L'))
    return d>=thr

def lines_of(mask, box):
    """split ink mask into horizontal bands -> per-band (top,bot,left,right)"""
    rows=mask.sum(axis=1)
    bands=[];i=0
    while i<len(rows):
        if rows[i]:
            k=i
            while k+1<len(rows) and rows[k+1]: k+=1
            sub=mask[i:k+1]
            cols=np.where(sub.sum(axis=0))[0]
            bands.append((i+box[1],k+box[1],cols.min()+box[0],cols.max()+box[0], int(sub.sum())))
            i=k+1
        else: i+=1
    return bands

def compare(pid, rect, pad=14, thr=32, merge=0):
    ref=refimg(pid)
    nt=render_page(pages[pid],assets,ref.size,draw_txt=False).convert('RGB')
    wt=render_page(pages[pid],assets,ref.size,draw_txt=True).convert('RGB')
    x,y,w,h=rect
    box=(x-pad,y-pad,x+w+pad,y+h+pad)
    rm=ink(ref,nt,box,thr); mm=ink(wt,nt,box,thr)
    return lines_of(rm,box), lines_of(mm,box)
