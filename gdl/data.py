"""Build a slim render model from Extron GUI Designer .gdl files.

Emits one JSON blob holding every page, popup and control of each project,
plus the PNG asset set as data URIs, ready to inject into an HTML viewer.

Established by inspection of the six .gdl files in this repo:
  - a .gdl is a ZIP whose record signatures read 'KP' instead of 'PK'
  - it holds 'ProjectGCP' (a .NET BinaryFormatter graph, the editor's own
    project state) and a '*.tgz4' member that is a plain ZIP of the built
    panel payload: layout.json + N.png
  - TLPImageID maps exactly to '<id>.png'; -1 means no image
  - every asset is pre-rendered at its control's exact pixel size (verified
    across 8,000+ references in all six files, 100% exact) so images blit 1:1
  - text is NOT baked into the assets: one asset backs many captions, so the
    viewer draws text itself
  - a page's Controls array is in ascending z-order, so DOM order is correct
  - BackgroundFillColor is alpha-0 everywhere; the PNG carries the fill
"""
import base64
import io
import json
import os
import re
import struct
import sys
import zipfile

SIGS = (b'KP\x03\x04', b'KP\x01\x02', b'KP\x05\x06', b'KP\x07\x08')
PT_TO_PX = 1.375  # the panel rasterizes at 99 DPI, not the usual 96
NO_POPUP = 0xFFFFFFFFFFFFFFFF
STALE_ID = re.compile(r'_ID(\d+)$')

# Line box = (usWinAscent + usWinDescent) / unitsPerEm, measured from the
# shipped font binaries. GDI adds no external leading.
LINE_FACTOR = {
    'Arial': 1.1172,
    'Arial Black': 1.4102,
    'Open Sans': 1.3618,
    'Open Sans Light': 1.3618,
    'Forma DJR Display': 1.2000,
    'Crestron General': 1.0420,
}


def open_gdl(path):
    """Un-mangle the KP signatures and return the outer container."""
    with open(path, 'rb') as fh:
        d = bytearray(fh.read())
    for s in SIGS:
        i = d.find(s)
        while i != -1:
            d[i:i + 2] = b'PK'
            i = d.find(s, i + 1)
    return zipfile.ZipFile(io.BytesIO(bytes(d)))


def payload(path):
    """Return the inner built-panel ZIP (the '*.tgz4' member)."""
    z = open_gdl(path)
    name = next(n for n in z.namelist() if n != 'ProjectGCP')
    return zipfile.ZipFile(io.BytesIO(z.read(name)))


def png_size(raw):
    w, h = struct.unpack('>II', raw[16:24])
    return w, h


def color(c):
    """PBColor {A,R,G,B} -> css rgba(), or None when absent/transparent."""
    if not isinstance(c, dict):
        return None
    a = c.get('A', 255)
    if a == 0:
        return None
    return f"rgba({c.get('R',0)},{c.get('G',0)},{c.get('B',0)},{round(a/255, 3)})"


def font(f):
    if not isinstance(f, dict):
        return None
    style = f.get('Style') or {}
    name = f.get('Name')
    out = {
        'n': name,
        'p': round(f.get('PointSize', 12) * PT_TO_PX, 2),
        'lh': LINE_FACTOR.get(name, 1.2),
    }
    if style.get('Bold'):
        out['b'] = 1
    if style.get('Italic'):
        out['i'] = 1
    if style.get('Underline'):
        out['u'] = 1
    if style.get('Strikeout'):
        out['s'] = 1
    return out


def popup_ref(c):
    """A PBPopupPageReference reserves the rect where a popup will appear.

    It binds either to one popup (IsPopupPageIdValid) or to a popup *group*
    (IsPopupGroupIdValid), in which case any popup whose own size matches the
    reserved rect can occupy it.
    """
    p = c.get('PopupPageID')
    if not isinstance(p, dict):
        return None
    if p.get('IsPopupPageIdValid') and p.get('PopupID') != NO_POPUP:
        return {'id': p['PopupID']}
    if p.get('IsPopupGroupIdValid'):
        return {'group': p.get('GroupID')}
    return None


def control(c, assets):
    kind = c['__type'].split(':')[0][2:]  # PBButton -> Button
    out = {
        't': kind,
        'x': c['Left'], 'y': c['Top'], 'w': c['Width'], 'h': c['Height'],
    }

    # A PBPopupPageReference paints nothing — it is a design-time anchor saying
    # where a popup lands. It must never become a hit target.
    ref = popup_ref(c)
    if ref:
        out['pp'] = ref
        out['anchor'] = 1
        return out

    states = c.get('States') or []
    # A button's own TLPImageID/Text/Font mirror States[0], but its TextColor is
    # null on two thirds of buttons — the real color only lives on the state.
    default = states[c['TLPDefaultStateID']] if states and c.get('TLPDefaultStateID', 0) < len(states) else None
    src = default or c

    base = c.get('TLPImageID')
    if kind == 'Level':
        # Trap: a level's TLPImageID is the FULL bar. Its empty trough is the
        # min image, so a blind blit would draw every meter at 100%.
        base = c.get('TLPMinValueImageID', base)
    elif default is not None:
        base = default.get('TLPImageID', base)
    if isinstance(base, int) and base in assets:
        out['i'] = base

    # FlattenText means the caption is already rasterized into the artwork.
    if c.get('FlattenText'):
        out['ft'] = 1
    txt = '' if c.get('FlattenText') else (src.get('Text') or c.get('Text') or '')
    if txt:
        out['tx'] = txt
    align = src.get('TextAlignment', c.get('TextAlignment'))
    if align is not None:
        out['a'] = align
    col = color(src.get('TextColor')) or color(c.get('TextColor'))
    if col:
        out['c'] = col
    fnt = font(src.get('Font') or c.get('Font'))
    if fnt:
        out['f'] = fnt

    if c.get('UserId'):  # 0 is the sentinel for "not addressable"
        out['u'] = c['UserId']
    if c.get('ID') is not None:
        out['id'] = c['ID']
    name = c.get('Name') or ''
    if name:
        # A trailing _ID<n> is the port frozen at copy time and is often stale.
        m = STALE_ID.search(name)
        out['n'] = STALE_ID.sub('', name)
        if m and c.get('UserId') and int(m.group(1)) != c['UserId']:
            out['stale'] = int(m.group(1))
    if c.get('Pattern'):
        out['pat'] = c['Pattern']

    if states:
        out['st'] = [{
            'id': s.get('ID'), 'n': s.get('Name'),
            'i': s.get('TLPImageID') if s.get('TLPImageID') in assets else None,
            'tx': '' if c.get('FlattenText') else (s.get('Text') or ''),
            'c': color(s.get('TextColor')),
            'f': font(s.get('Font')),
            'a': s.get('TextAlignment'),
        } for s in states]
        out['ds'] = c.get('TLPDefaultStateID', 0)
        out['ps'] = c.get('TLPPressFeedbackStateID')

    # Slider / level compositing parts
    for key, srck in (('ind', 'SliderIndicatorImageID'),
                      ('mn', 'TLPMinValueImageID'),
                      ('mx', 'TLPMaxValueImageID')):
        v = c.get(srck)
        if isinstance(v, int) and v in assets:
            out[key] = v
    for key, srck in (('io', 'Orientation'), ('iw', 'SliderIndicatorWidth'),
                      ('ih', 'SliderIndicatorHeight'), ('dt', 'DisplayType')):
        if c.get(srck) is not None:
            out[key] = c[srck]
    return out


def page(p, assets):
    out = {
        'id': p['ID'], 'n': p['Name'],
        'w': p['Width'], 'h': p['Height'],
        'bg': p['TLPImageID'] if p.get('TLPImageID') in assets else None,
        'c': [control(c, assets) for c in (p.get('Controls') or [])],
    }
    # The page image is authoritative; the fill only shows through when there
    # is no image (the Offline page and the empty template popups).
    if out['bg'] is None:
        out['fill'] = color(p.get('BackgroundFillColor'))
    for key, src in (('grp', 'GroupID'), ('modal', 'Modal'), ('used', 'HasReferences')):
        if p.get(src) is not None:
            out[key] = p[src]
    return out


def project(path, label):
    z = payload(path)
    j = json.loads(z.read('layout.json'))
    assets, sizes = {}, {}
    for n in z.namelist():
        if not n.endswith('.png'):
            continue
        raw = z.read(n)
        i = int(n[:-4])
        assets[i] = 'data:image/png;base64,' + base64.b64encode(raw).decode()
        sizes[i] = png_size(raw)

    pages = [page(p, assets) for p in j['Pages']]
    popups = [page(p, assets) for p in j['PopupPages']]

    fonts = sorted({c['f']['n'] for pg in pages + popups for c in pg['c']
                    if c.get('f') and c['f'].get('n')})
    return {
        'label': label,
        'name': j.get('Name'),
        'job': j.get('JobNumber'),
        'author': j.get('Author'),
        'skin': j.get('Skin'),
        'app': j.get('ApplicationBuildVersionInfo'),
        'ver': j.get('VersionInfo'),
        'part': j.get('PartNumber'),
        'panel': (j.get('Platform') or {}).get('__type', '').replace('Platform', ''),
        'screen': [j['Platform']['HorizontalResolution'], j['Platform']['VerticalResolution']],
        'default': j.get('DefaultPage'),
        'offline': j.get('OfflinePageID') if j.get('EnableOfflinePage') else None,
        'pages': pages,
        'popups': popups,
        'assets': assets,
        'sizes': sizes,
        'fonts': fonts,
    }


if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    wanted = sys.argv[3:]
    projects = []
    for fn in sorted(os.listdir(src)):
        if not fn.endswith('.gdl'):
            continue
        label = fn[:-4].replace('Interface_', '').replace('J26450039_Liberty_Bank_Boardroom', 'Panel').replace('_', ' ').strip()
        if wanted and not any(w in fn for w in wanted):
            continue
        p = project(os.path.join(src, fn), label)
        projects.append(p)
        n = sum(len(pg['c']) for pg in p['pages'] + p['popups'])
        print(f"  {label[:48]:<48} {len(p['pages'])} pages {len(p['popups'])} popups "
              f"{n:>4} controls {len(p['assets']):>3} assets")
    blob = json.dumps(projects, separators=(',', ':'))
    with open(out, 'w', encoding='utf8') as fh:
        fh.write(blob)
    print(f"\nwrote {out}  {len(blob)/1024/1024:.2f} MB")
