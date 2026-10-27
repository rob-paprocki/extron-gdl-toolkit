"""Read what Run-Probes128.ps1 left, probe by probe: what the built files show
against what was asked.

    python examples/probes-128/read_probes.py out/probes-128 [probe ...]

Runs anywhere with Python 3; the artwork measurements need Pillow and the
authoring-model reads need nothing else but the repo. A folder with no probe in
it, or a probe with no built file, is said and skipped - never a crash - so it
can be run on a half-finished run. The figures it prints are the answers the
README's table lists; each probe's `probe.log` is the full record, and the
Build Manager's own dumps are under `<probe>/buildmgr-*/`.

It reads; it changes nothing, and judges nothing the README does not say a
figure means.
"""
import glob
import json
import os
import re
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

PROBES = ['format-probes', 'borders', 'horizontal-slider', 'reference-counts',
          'renumber-seed', 'renumber-generated', 'twins-1535']

# What a line of a probe's log says about a build or its verifier.
VERDICT = re.compile(r'check\(s\) on|problem\(s\)|FAILED|BUILT AND VERIFIED|ID MAP WRITTEN|'
                     r'build finished|no completed build|GUI Designer (did not|shows)', re.I)
# Whole words only: a stack trace's "Int32 errorCode" once read as 32 errors.
COUNT = re.compile(r'\b(\d+)\s*(errors?|warnings?)\b|\b(errors?|warnings?)\s*[:=(-]?\s*(\d+)\b', re.I)


def out(line=''):
    print(line)


def exists(*parts):
    p = os.path.join(*parts)
    return p if os.path.exists(p) else None


def lines_of(path):
    try:
        with open(path, encoding='utf-8-sig', errors='replace') as fh:
            return fh.read().splitlines()
    except OSError:
        return []


# ---------------------------------------------------------------- shared ----
def log_verdicts(d):
    """The lines of the probe's log that say how a build and its verifiers went."""
    seen = []
    for line in lines_of(os.path.join(d, 'probe.log')):
        if VERDICT.search(line):
            seen.append(line.strip())
    for line in seen[-14:]:
        out('    ' + line)
    if not seen:
        out('    (probe.log says nothing about a build)')


def build_manager(d):
    """What the Build Manager's windows said, and the 0-errors/0-warnings figures
    in it, from every buildmgr-* folder the watcher wrote."""
    folders = sorted(glob.glob(os.path.join(d, 'buildmgr-*')))
    if not folders:
        out('  Build Manager: no watcher output (the probe stopped before a build)')
        return
    for f in folders:
        tag = os.path.basename(f)[len('buildmgr-'):]
        log = lines_of(os.path.join(f, 'windows.log'))
        appeared = [l for l in log if 'appeared' in l]
        titles = sorted({re.search(r"'([^']*)'", l).group(1) for l in appeared if re.search(r"'([^']*)'", l)})
        dumps = sorted(glob.glob(os.path.join(f, 'dump-*.txt')))
        shots = len(glob.glob(os.path.join(f, 'screen-*.png'))) + len(glob.glob(os.path.join(f, 'shot-*.png')))
        out(f'  Build Manager, {tag}: {len(appeared)} window(s) seen besides the main one'
            f'{" - " + ", ".join(repr(t) for t in titles) if titles else ""}; '
            f'{len(dumps)} dump(s), {shots} picture(s)')
        if not dumps:
            out('    nothing to read: look at screen-NNN.png in ' + os.path.relpath(f, REPO if f.startswith(REPO) else d))
            continue
        # The last dump of each window is the fullest, the one nearest the end.
        last = {}
        for p in dumps:
            m = re.match(r'dump-(.*)-\d{6}-\d+\.txt$', os.path.basename(p))
            last[m.group(1) if m else p] = p
        for key, p in sorted(last.items()):
            # What the window said, in the order the dumps caught it: on
            # 1.28 a clean build's Build Manager shows its phase and nothing
            # else, so this is the whole readout.
            said = [m.group(1).strip() for q in dumps if os.path.basename(q).startswith(f'dump-{key}-')
                    for m in [re.match(r'(?i)\s*\S*STATIC\S*\s+0x[0-9A-F]+\s+(.*\S)', l) for l in lines_of(q)] if m]
            if said:
                out(f'    {key} said: {" / ".join(dict.fromkeys(said))}')
            hits = []
            for line in lines_of(p):
                # A .NET stack trace (" at MS.Internal...") is the watcher's, not GUI Designer's.
                if re.search(r'error|warning', line, re.I) and not line.startswith('#') \
                        and not line.strip().startswith('at '):
                    hits.append(line.strip())
            counts = []
            for line in hits:
                for m in COUNT.finditer(line):
                    n = m.group(1) or m.group(4)
                    kind = (m.group(2) or m.group(3)).lower().rstrip('s')
                    counts.append(f'{n} {kind}(s)')
            out(f'    {key}: {", ".join(sorted(set(counts))) or "no count in the text"}')
            for line in list(dict.fromkeys(hits))[:8]:
                out('      ' + line[:160])


def project(path):
    from gdl.project import Project
    return Project.open(path)


def layout(path):
    from gdl.compose import load
    return load(path)


def controls_of(j):
    for key in ('Pages', 'PopupPages'):
        for pg in j[key]:
            for c in pg['Controls']:
                yield key, pg, c


def plan_of(d, name):
    p = exists(d, name)
    if not p:
        return None
    with open(p, encoding='utf-8') as fh:
        return json.load(fh)


def plan_ops(plan):
    for key in ('pages', 'popups'):
        for item in plan.get(key) or []:
            for op in item.get('controls') or []:
                yield key[:-1], item, op


# ------------------------------------------------------------ format probes --
def read_format(d):
    fx = lines_of(os.path.join(d, 'fixture.txt'))
    out(f'  input: {fx[0] if fx else "(no fixture.txt)"}')
    for t in 'ABC':
        pre, built = exists(d, f'test{t}.pre.gdl'), exists(d, f'test{t}.gdl')
        if not built:
            out(f'  test {t}: no file')
            continue
        try:
            j, assets = layout(built)
            payload = f'{len(assets)} PNG(s), {sum(len(p["Controls"]) for p in j["Pages"] + j["PopupPages"])} control(s)'
        except Exception as e:     # an unbuilt file has no payload at all
            payload = f'NO PAYLOAD ({e.__class__.__name__}) - the build did not write one'
        out(f'  test {t}: built file {os.path.getsize(built):,} bytes; payload: {payload}')
        try:
            b = project(built)
            names = sorted(b.border_resource_names())
            b_ctrls = [c for pg in b.pages() for c in pg['controls']]
            if t == 'A':
                bound = [c['name'] for c in b_ctrls if (c.get('border') or {}).get('resource') == '3D Capsule']
                before = ([c['name'] for pg in project(pre).pages() for c in pg['controls']
                           if (c.get('border') or {}).get('resource') == '3D Capsule'] if pre else None)
                out(f'     controls bound to "3D Capsule": {len(bound)} built'
                    f'{f", {len(before)} before the build" if before is not None else ""}  (question 1: expect 1 and 1)')
            if t == 'B':
                new = 'Claude - 20 Radius 1 Thick'
                bound = [c['name'] for c in b_ctrls if (c.get('border') or {}).get('resource') == new]
                out(f'     border resources: {len(names)} built'
                    f'{f", {len(project(pre).border_resource_names())} before" if pre else ""}; '
                    f'{new!r} {"still defined" if new in names else "GONE"}; bound by {len(bound)} control(s)'
                    f'  (question 2: 1.28 gave 35 against the fixture\'s 34)')
                geo = b.border_geometry().get(new)
                out(f'     its geometry as built: {geo}  (asked: radius 20, thickness 1)')
            if t == 'C':
                # Against test A's build, the same fixture without the clone:
                # test C's own .pre.gdl already holds it.
                npg = [len(pg['controls']) for pg in b.pages() if pg['kind'] == 'page']
                a = exists(d, 'testA.gdl')
                na = [len(pg['controls']) for pg in project(a).pages() if pg['kind'] == 'page'] if a else None
                out(f'     controls per page, built: {npg[:3]}...'
                    f'{f"  test A built: {na[:3]}..." if na else ""}  (question 4: page 2 gains the cloned control)')
        except Exception as e:
            out(f'     could not read the authoring model: {e.__class__.__name__}: {e}')
    out('  Question 3 (out-of-corpus border values) is the borders probe; question 5 (names unique) and 6')
    out('  (referenceCountField) are read there and in reference-counts.')


# -------------------------------------------------------------- the borders --
def opaque_rows(img):
    """For each row of the top half, the x of its first opaque pixel."""
    a = img.getchannel('A')
    w, h = img.size
    px = a.load()
    rows = []
    for y in range(h // 2):
        x = next((x for x in range(w) if px[x, y] >= 128), w)
        rows.append(x)
    return rows


def measure_corner(img):
    """The radius a corner shows, and the stroke's thickness, as the run of one
    color in from the left edge along the middle row.

    The radius is the circle that best fits where each of the top rows first
    paints: an arc of radius r is r - sqrt(r^2 - (r - y)^2) in at row y, which
    no single row says by itself (the top row is r - sqrt(r) in). A radius past
    half the height is a capsule, and fits as half."""
    w, h = img.size
    rows = opaque_rows(img)

    def miss(r):
        return sum(abs((r - (max(0.0, r * r - (r - y - 0.5) ** 2) ** 0.5 if y < r else r)) - x)
                   for y, x in enumerate(rows))
    radius = min(range(0, min(w, h) // 2 + 1), key=miss) if rows else 0
    mid = img.getpixel((0, h // 2))
    run = 0
    for x in range(w // 2):
        if img.getpixel((x, h // 2)) == mid:
            run += 1
        else:
            break
    return radius, run, mid


def argb_dict(v):
    if isinstance(v, dict):
        return v
    v = int(v or 0)
    return {'A': v >> 24 & 255, 'R': v >> 16 & 255, 'G': v >> 8 & 255, 'B': v & 255}


def preview_diff(built, w, h, fill, stroke, radius, thickness):
    """The share of pixels where the built artwork differs from the preview's
    drawing of the same fill, stroke, radius and thickness."""
    from PIL import Image, ImageChops
    from gdl.compose import draw_fill
    canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw_fill(canvas, (0, 0, w, h), {'fill': fill, 'stroke': stroke,
                                     'border': {'radius': radius, 'thickness': thickness}})
    if built.size != (w, h):
        built = built.resize((w, h))
    diff = ImageChops.difference(canvas, built).convert('L').point(lambda v: 255 if v > 24 else 0)
    return diff.histogram()[255] / (w * h)


def read_borders(d):
    from PIL import Image
    import io
    plan = plan_of(d, 'plan-bound.json')
    built = exists(d, 'borders.gdl')
    table = None
    t = os.path.join(HERE, 'borders.json')
    with open(t, encoding='utf-8') as fh:
        table = {r['control']: r for r in json.load(fh)['rows']}
    if not (plan and built):
        out('  no plan-bound.json or no built borders.gdl')
        return
    j, assets = layout(built)
    byname = {c['Name']: c for _, _, c in controls_of(j)}
    b = project(built)
    names = set(b.border_resource_names())
    got_res = {c['name']: (c.get('border') or {}).get('resource')
               for pg in b.pages() for c in pg['controls']}
    out('  control            asked          resource built as                 corner  stroke px  vs preview')
    for _, _, op in plan_ops(plan):
        name = op['fields']['nameField']
        row = table.get(name)
        if not row:
            continue
        c = byname.get(name)
        tid = c.get('TLPImageID') if c else None
        if c is None or tid is None or tid < 0 or tid not in assets:
            out(f'  {name:<18} {row["radius"]:>3}R {row["thickness"]:>2}T    NO ARTWORK (TLPImageID {tid}) - '
                f'resource {got_res.get(name)!r}')
            continue
        img = Image.open(io.BytesIO(assets[tid])).convert('RGBA')
        r, s, _ = measure_corner(img)
        diff = preview_diff(img, c['Width'], c['Height'], argb_dict(op['fill']), argb_dict(op['stroke']),
                            row['radius'], row['thickness'])
        out(f'  {name:<18} {row["radius"]:>3}R {row["thickness"]:>2}T    {str(got_res.get(name)):<32} '
            f'{r:>4}         {s:>4}      {diff:6.1%}')
    absent = [r['resource'] for r in table.values() if r['resource'] not in names]
    out(f'  resources the table names that the built file does not define: {absent or "none"}')
    out('  "corner": the radius whose arc best fits the built corner (capped at half the height);')
    out('  "stroke px": pixels of one color in from the left edge on the middle row.')
    out('  "vs preview": share of pixels the built art and gdl.compose\'s drawing of the same geometry differ on.')


# --------------------------------------------------------------- the sliders --
def bbox_of(png):
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(png)).convert('RGBA')
    a = im.getchannel('A').point(lambda v: 255 if v >= 16 else 0)
    return im.size, a.getbbox()


def slider_row(c, assets, label):
    """One slider's figures: its fields as built and the extents of its rail
    and thumb artwork."""
    o = {0: 'right', 1: 'left', 2: 'up', 3: 'down'}.get(c.get('Orientation'), c.get('Orientation'))
    out(f'  {label}: {o}, control {c["Width"]}x{c["Height"]}, track {c.get("SliderTrackWidth")}, '
        f'thumb {c.get("SliderIndicatorWidth")}x{c.get("SliderIndicatorHeight")}')
    horizontal = c.get('Orientation') in (0, 1)
    for part, key in (('empty rail', 'TLPMinValueImageID'), ('full rail ', 'TLPMaxValueImageID'),
                      ('thumb     ', 'SliderIndicatorImageID')):
        tid = c.get(key)
        if tid is None or tid < 0 or tid not in assets:
            out(f'    {part}: no artwork ({key} {tid})')
            continue
        size, box = bbox_of(assets[tid])
        if not box:
            out(f'    {part}: {size[0]}x{size[1]}, fully transparent')
            continue
        x0, y0, x1, y1 = box
        if key == 'SliderIndicatorImageID':
            out(f'    {part}: {size[0]}x{size[1]}, painted {x1 - x0}x{y1 - y0}')
            continue
        a0, a1 = (x0, size[0] - x1) if horizontal else (y0, size[1] - y1)
        thick = (y1 - y0) if horizontal else (x1 - x0)
        c0 = (y0 + y1) / 2 - size[1] / 2 if horizontal else (x0 + x1) / 2 - size[0] / 2
        out(f'    {part}: {size[0]}x{size[1]}, painted {x1 - x0}x{y1 - y0}; inset {a0} at the start and {a1} at the end '
            f'along its length, {thick} thick across, centred to {c0:+.1f}')


def kit_file(name):
    from gdl.spec import resolve_image
    return resolve_image('Shockwave/Slider/' + name)


def model_diffs(c, assets, op):
    """The built rails and thumb against verify_built's models and the
    alternatives the probe set out to tell apart: the rail art turned the
    other way, or laid on its side unturned, and the thumb fitted or turned
    rather than stretched. "off" is the verifier's share of differing pixels
    (25% fails); "mean" the mean difference per channel, 0-255, which is what
    tells one quarter turn from the other on a near-symmetric rail."""
    from PIL import Image, ImageChops, ImageStat
    import io
    sys.path.insert(0, os.path.join(REPO, 'tests'))
    import verify_built as vb
    o = c.get('Orientation')
    vertical = o in (2, 3)
    files = {k: kit_file((op.get(k) or {}).get('name') or '') for k in ('track_image', 'fill_image', 'thumb_image')}
    if not files['track_image']:
        out('    (the kit\'s slider art is not on this machine - set $GDL_EXTRON_RESOURCES - so no model comparison)')
        return
    track = c.get('SliderTrackWidth')
    thumb = c.get('SliderIndicatorHeight' if vertical else 'SliderIndicatorWidth')

    def mean(want, got):
        key = Image.new('RGBA', got.size, (255, 0, 255, 255))
        a, b = Image.alpha_composite(key, want).convert('RGB'), Image.alpha_composite(key, got).convert('RGB')
        return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3

    def unturned(file, w, h, under=None):
        im = unturned(under, w, h) if under else Image.new('RGBA', (w, h), (0, 0, 0, 0))
        art = vb.stretch_image(file, *((track, h - thumb) if vertical else (w - thumb, track)))
        im.alpha_composite(art, ((w - track) // 2, thumb // 2) if vertical else (thumb // 2, (h - track) // 2))
        return im

    for part, key, file, under in (('empty rail', 'TLPMinValueImageID', files['track_image'], None),
                                   ('full rail ', 'TLPMaxValueImageID', files['fill_image'], files['track_image'])):
        tid = c.get(key)
        if not file or tid is None or tid not in assets:
            continue
        got = Image.open(io.BytesIO(assets[tid])).convert('RGBA')
        w, h = got.size
        models = {'verify_built (turned to the full end)': vb.rail_image(file, w, h, track, thumb, o, under)}
        if not vertical:
            models['turned the other way'] = vb.rail_image(file, w, h, track, thumb, 1 - o, under)
            models['unturned, on its side'] = unturned(file, w, h, under)
        for label, want in models.items():
            off = vb.image_mismatch(file, assets[tid], w, h, draw=lambda f, w, h, want=want: want)
            out(f'    {part} vs "{label}": off {off:.1%}, mean {mean(want, got):.2f}')
    tid = c.get('SliderIndicatorImageID')
    if files['thumb_image'] and tid in assets:
        got = Image.open(io.BytesIO(assets[tid])).convert('RGBA')
        w, h = got.size
        f = files['thumb_image']

        def turned(file, w, h):
            return Image.open(file).convert('RGBA').transpose(Image.Transpose.ROTATE_270).resize(
                (w, h), Image.Resampling.LANCZOS)
        for label, draw in (('verify_built (stretched)', vb.stretch_image), ('fitted', vb.fit_image),
                            ('turned, stretched', turned)):
            off = vb.image_mismatch(f, assets[tid], w, h, draw=draw)
            out(f'    thumb      vs "{label}": off {off:.1%}, mean {mean(draw(f, w, h), got):.2f}')


def read_slider(d):
    plan = plan_of(d, 'hslider.plan.json')
    built = exists(d, 'hslider.gdl')
    if not (plan and built):
        out('  no hslider.plan.json or no built hslider.gdl')
        return
    j, assets = layout(built)
    byname = {c['Name']: c for _, _, c in controls_of(j)}
    for _, _, op in plan_ops(plan):
        name = op['fields']['nameField']
        c = byname.get(name)
        if c is None:
            out(f'  {name}: not in the built file')
            continue
        f = op['fields']
        out(f'  planned {name}: track {f.get("sliderTrackWidth")}, thumb {f.get("sliderThumbWidth")}x{f.get("sliderThumbHeight")}')
        slider_row(c, assets, '   built')
        try:
            model_diffs(c, assets, op)
        except Exception as e:
            out(f'    model comparison failed: {e.__class__.__name__}: {e}')
    # The seeds' own horizontal sliders: what Build did with them, the figures to set beside ours.
    for seed in sorted(glob.glob(os.path.join(REPO, 'seeds', 'Zoom Rooms Dark ZRTP 1035.gdl'))):
        try:
            sj, sassets = layout(seed)
        except Exception as e:
            out(f'  {os.path.basename(seed)}: {e}')
            continue
        out(f'  the reference: {os.path.basename(seed)}\'s horizontal sliders')
        for _, pg, c in controls_of(sj):
            if c.get('__type') == 'PBSlider' and c.get('Orientation') in (0, 1):
                slider_row(c, sassets, f'   {pg["Name"]} / {c["Name"]}')


# ---------------------------------------------------------- reference counts --
def registry(path):
    p = project(path)
    proj = next(p.instances('PBProject'), None)
    j, _ = layout(path)
    members = {}
    for pg in j['PopupPages']:
        members[pg.get('GroupID')] = members.get(pg.get('GroupID'), 0) + 1
    refs = {}
    for _, _, c in controls_of(j):
        if c.get('__type') == 'PBPopupPageReference':
            g = (c.get('PopupPageID') or {}).get('GroupID') if isinstance(c.get('PopupPageID'), dict) else None
            refs[g] = refs.get(g, 0) + 1
    rows = []
    for g in p.items(p.field(proj, 'popupPageGroupsField')):
        gid = p.field(g, 'idField')
        rows.append((p.field(g, 'nameField'), gid, p.field(g, 'referenceCountField'),
                     members.get(gid, 0), refs.get(gid, 0)))
    return rows


def read_counts(d):
    stages = [('stage 1, built from the spec (the applier wrote 2 on each)', 'stage1.gdl'),
              ('stage 2 as written (what Set-ReferenceCounts.ps1 put there)', 'stage2.pre.gdl'),
              ('stage 2, built', 'stage2.gdl')]
    table = {}
    for label, f in stages:
        p = exists(d, f)
        if not p:
            out(f'  {label}: no {f}')
            continue
        try:
            rows = registry(p)
        except Exception as e:
            out(f'  {label}: could not read: {e.__class__.__name__}: {e}')
            continue
        table[f] = {r[0]: r for r in rows}
        out(f'  {label}:')
        for name, gid, count, members, refs in rows:
            out(f'      group {gid} {name!r}: referenceCountField {count}; {members} popup(s) in it, {refs} reference(s) to it')
    a, b, c = (table.get(f) for _, f in stages)
    if b and c:
        out('  verdict by group (written -> built):')
        for name, row in b.items():
            built = c.get(name)
            if not built:
                out(f'      {name}: not in the built registry')
                continue
            w, got, members, refs = row[2], built[2], built[3], built[4]
            what = ('kept what was written' if got == w else
                    'recomputed to the popups in the group' if got == members else
                    'recomputed to the references to it' if got == refs and refs != members else
                    'changed to something else')
            out(f'      {name}: wrote {w}, built {got} (popups {members}, references {refs}) - {what}')
    if a:
        same = all(r[2] == 2 for r in a.values())
        # No backslash inside the braces: Python 3.11, the Windows host's, rejects one there.
        verdict = "left the applier's 2 alone" if same else "changed the applier's 2 on at least one group"
        out(f'  stage 1: Build {verdict}')


# ---------------------------------------------------------------- renumber ----
def read_renumber(d, tag):
    plan = plan_of(d, f'{tag}-plan.json')
    before, built = exists(d, f'{tag}-before.gdl'), exists(d, f'{tag}-edited.gdl')
    if not (plan and before and built):
        out(f'  no {tag}-plan.json / {tag}-before.gdl / {tag}-edited.gdl')
        return
    jb, _ = layout(before)
    ja, _ = layout(built)
    pages_before = {p['ID']: p['Name'] for k in ('Pages', 'PopupPages') for p in jb[k]}
    ctl_before = {(p['ID'], c['ID']): c for k in ('Pages', 'PopupPages') for p in jb[k] for c in p['Controls']}
    built_by = {}
    for _, pg, c in controls_of(ja):
        built_by.setdefault((pg['Name'], c['Name']), []).append(c)
    n = took = kept = other = missing = 0
    for op in plan['controls']:
        want = (op.get('fields') or {}).get('userIdField')
        c0 = ctl_before.get((op['page'], op['control']))
        if c0 is None or want is None:
            continue
        n += 1
        got = built_by.get((pages_before[op['page']], c0['Name']))
        if not got:
            missing += 1
        elif any(g['UserId'] == want for g in got):
            took += 1
        elif any(g['UserId'] == op['was'] for g in got):
            kept += 1
        else:
            other += 1
    out(f'  planned {n} control(s) renumbered: {took} built with the new ID, {kept} still on the old one, '
        f'{other} on another, {missing} not found by page and name')
    # One new ID, one control: a new ID the build gave two controls that were not mirrors before.
    news = {(op.get('fields') or {}).get('userIdField') for op in plan['controls']}
    users = {}
    for _, pg, c in controls_of(ja):
        if c['UserId'] in news:
            users.setdefault(c['UserId'], []).append((pg['Name'], c['Name']))
    shared = {i: v for i, v in users.items() if len({x for x in v}) > 1 and len({n for _, n in v}) > 1}
    out(f'  new IDs carried by differently named controls: {len(shared)}'
        f'{" - " + str(list(shared.items())[:3]) if shared else ""}')
    pre = exists(d, f'{tag}-edited.pre.gdl')
    if pre:
        # The file as applied is read off its authoring model: its layout.json
        # is still the donor's last build, with every old ID in it.
        same = {(pg['name'], c['name']): c['id'] for pg in project(pre).pages() for c in pg['controls']}
        moved = sum(1 for k, v in same.items() if k in built_by and all(g['UserId'] != v for g in built_by[k]))
        out(f'  controls whose ID differs between the file as applied and as built: {moved}'
            f'  (a renumber Build then changed would show here)')
    diff = lines_of(os.path.join(d, f'{tag}-idmap-after', 'changes.md'))
    if not diff:
        diff = [l for l in lines_of(os.path.join(d, 'probe.log')) if re.search(r'renumber|verdict|changes', l, re.I)][-6:]
    for l in diff[:8]:
        out('    idmap diff: ' + l.strip()[:150])


# ------------------------------------------------------------------- twins ----
def read_twins(d):
    plan = plan_of(d, 'twins-1535.plan.json')
    built = exists(d, 'twins-1535.gdl')
    if not (plan and built):
        out('  no twins-1535.plan.json or no built twins-1535.gdl')
        return
    j, _ = layout(built)
    planned = {}
    for kind, item, op in plan_ops(plan):
        uid = (op.get('fields') or {}).get('userIdField')
        if uid:
            planned.setdefault((item['name'], uid), []).append(op)
    twin_keys = {k for k, v in planned.items() if len(v) > 1}
    out(f'  planned: {len(twin_keys)} ID(s) shared by two controls on one page or popup of the plan')
    pgs = {p['Name']: p for k in ('Pages', 'PopupPages') for p in j[k]}
    ok = 0
    for (page, uid) in sorted(twin_keys):
        pg = pgs.get(page)
        if pg is None:
            out(f'    {page!r} {uid}: the page is not in the built file')
            continue
        got = [c for c in pg['Controls'] if c.get('UserId') == uid]
        want = planned[(page, uid)]
        rects = [(c['Left'], c['Top'], c['Width'], c['Height']) for c in got]
        wrects = [tuple(int(op['fields'][k]) for k in ('leftField', 'topField', 'widthField', 'heightField')) for op in want]
        same = sorted(rects) == sorted(wrects)
        ok += same and len(got) == len(want)
        out(f'    {page!r} ID {uid}: {len(got)} built of {len(want)} planned; rects '
            f'{"as planned" if same else f"built {rects} planned {wrects}"}; '
            f'captions {[c.get("Text") for c in got]}')
    out(f'  twins that built as planned: {ok} of {len(twin_keys)}')
    out('  (the verifier\'s and the ID map\'s verdicts are in the log lines above)')


READERS = {
    'format-probes': read_format,
    'borders': read_borders,
    'horizontal-slider': read_slider,
    'reference-counts': read_counts,
    'renumber-seed': lambda d: read_renumber(d, 'seed'),
    'renumber-generated': lambda d: read_renumber(d, 'huddle'),
    'twins-1535': read_twins,
}


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[0])
        print('usage: read_probes.py <out/probes-128> [probe ...]')
        return 2
    root = argv[1]
    names = argv[2:] or PROBES
    found = [n for n in names if os.path.isdir(os.path.join(root, n))]
    summary = os.path.join(root, 'summary.txt')
    if os.path.exists(summary):
        out('summary.txt:')
        for line in lines_of(summary):
            if line.startswith('--- read_probes'):
                break
            out('  ' + line)
        out()
    if not found:
        out(f'no probe folder under {root} ({", ".join(names)})')
        return 0
    for n in found:
        d = os.path.join(root, n)
        out(f'== {n}')
        log_verdicts(d)
        try:
            READERS[n](d)
        except ImportError as e:
            # Pillow measures the artwork; without it the probe is unread, not failed.
            out(f'  needs {e.name or e} to read this probe (pip install -r requirements.txt)')
        except Exception:
            out('  reader failed:')
            for line in traceback.format_exc().splitlines()[-4:]:
                out('    ' + line)
        build_manager(d)
        out()
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
