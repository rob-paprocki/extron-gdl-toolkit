"""Did the build actually produce what the plan asked for?

A clean build is not the same as a correct one, and the gap is not small. GUI
Designer relocates a control that falls outside its page to 0,0 - at build time,
silently, still reporting 0 errors - and it bakes captions into artwork when
`flattenText` rides along on a clone. Both produce a file that opens, builds and
is wrong, and both were found by eye rather than by a check.

This is that check. It reads the plan the applier consumed and the `.gdl` GUI
Designer built, and asserts op by op that every authored control is present,
where it was put, and captioned as asked.

    python tests/verify_built.py out/plan.json out/generated9_built.gdl

Exits non-zero on any mismatch, so it can gate an authoring run the way
tests/score.py gates a render change.

Two things it deliberately does NOT treat as failures:

  * extra controls on a page. Build adds one full-canvas PBPopupPageReference
    per MODAL popup in the project, to every page. The Liberty Bank donor has
    six modal popups, so every generated page comes back with six references
    nobody authored. That is Build doing its job.
  * a popup page larger than the spec's size. A popup inherits its displayed
    dimensions from the reference that shows it; the page's own size only has
    to be big enough to hold the controls.
"""
import collections
import io
import json
import os
import sys

# os.path, not a '/' rsplit: on Windows __file__ comes back with backslashes and
# the split is a no-op, so the import below fails with ModuleNotFoundError.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageChops  # noqa: E402

from gdl.compose import load  # noqa: E402

# Type numbers as layout.json writes them, for the message only. Tabulated off
# built files - the Liberty Bank donor and two seeds - against each control's
# `__type`; this once said Line 9, DateTime 12, Slider 14 and Level 15.
# tests/test_verify_built.py pins it.
TYPE_NAME = {6: 'PopupPageReference', 7: 'Button', 8: 'DateTime', 9: 'Level',
             10: 'Image', 11: 'Label', 12: 'Line', 13: 'Shape', 27: 'Slider'}


def _caption(c):
    st = c.get('States') or []
    return (st[0].get('Text') if st else None) or c.get('Text') or ''


def _shares(assets, tid):
    """{(r,g,b): share of opaque pixels} for one rasterized asset.

    The authored fill does not survive into `layout.json`. A built control's
    `BackgroundFillColor` reads back as transparent white no matter what was
    authored, because Build rasterizes fill, border and caption together into a
    PNG and leaves only a `TLPImageID` behind. So the artwork is the only place
    the color a panel will actually show can be read - checking the model here
    would confirm nothing, which is the same trap `flattenText` set.
    """
    blob = assets.get(tid)
    if blob is None:
        return {}
    im = Image.open(io.BytesIO(blob)).convert('RGBA')
    raw = im.tobytes()
    counts = collections.Counter()
    for i in range(0, len(raw), 4):
        if raw[i + 3] > 250:                    # ignore antialiased edges
            counts[raw[i:i + 3]] += 1
    total = sum(counts.values())
    if not total:
        return {}
    return {tuple(k): v / total for k, v in counts.items()}


def _rgb(argb):
    return ((argb >> 16) & 0xFF, (argb >> 8) & 0xFF, argb & 0xFF)


def _hex(t):
    return '#%02X%02X%02X' % t


def _painted(argb):
    """A planned fill that paints. The spec writes a button with no fill as a
    transparent one (alpha 0), so the donor's does not bleed through - that is
    no fill to find in the artwork."""
    return argb is not None and (argb >> 24) & 0xFF > 0


# Below this share of a control's opaque pixels, the planned fill is present but
# not the field - a caption-heavy button, say. Reported, not failed: the color
# did survive, and calling that a failure would make the gate untrustworthy.
WEAK_FILL = 0.10


def check_fills(plan_items, table, assets, kind):
    """Every planned fill must be the plurality color of the control's artwork."""
    problems, notes, checked = [], [], 0
    for item in plan_items:
        got = table.get(item['name'])
        if got is None:
            continue
        by_name = _index(got)
        planned = [(item, op) for op in item['controls'] if _painted(op.get('fill'))]
        for _, op in planned:
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if c is None:
                continue
            tid = c.get('TLPImageID')
            want = _rgb(op['fill'])
            if tid is None or tid < 0:
                problems.append(f"{kind} {item['name']!r} {name!r}: planned fill "
                                f'{_hex(want)} but Build produced no artwork '
                                f'(TLPImageID {tid}), so it will draw nothing')
                continue
            shares = _shares(assets, tid)
            if not shares:
                problems.append(f"{kind} {item['name']!r} {name!r}: artwork "
                                f'{tid} is missing or fully transparent')
                continue
            checked += 1
            top, top_share = max(shares.items(), key=lambda kv: kv[1])
            if top == want:
                continue
            mine = shares.get(want, 0.0)
            if mine >= WEAK_FILL:
                notes.append(f"{kind} {item['name']!r} {name!r}: fill {_hex(want)} is "
                             f'{mine:.0%} of the artwork, behind {_hex(top)} at '
                             f'{top_share:.0%}')
            else:
                problems.append(f"{kind} {item['name']!r} {name!r}: planned fill "
                                f'{_hex(want)} is {mine:.0%} of the built artwork; '
                                f'it is mostly {_hex(top)} ({top_share:.0%})')
    return problems, notes, checked


def check_states(plan_items, table, assets, kind):
    """A button that asked for feedback must actually show it.

    The failure this exists for is silent and total: the applier wrote one
    appearance to every state of the cloned donor, so Off and On rasterized
    identically. The button builds, verifies against every other check, looks
    correct in the preview - and does nothing visible when the control system
    sets it On.

    Build gives each state its own TLPImageID, so the states really are drawn
    separately and can be compared as pixels. Two states that share an image id,
    or whose artwork has the same plurality color, are inert - and that is a
    problem regardless of what the model says, because the model is not what
    the panel draws.

    The count must match exactly, in both directions. Too few and the feedback
    the spec described cannot be shown; too many and the program can set a
    state nobody drew - a clone keeps its donor's states unless the applier
    resizes it.
    """
    problems, notes, checked = [], [], 0
    for item in plan_items:
        got = table.get(item['name'])
        if got is None:
            continue
        by_name = _index(got)
        for op in item['controls']:
            want = op.get('states')
            if not want and not op.get('image'):
                continue
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if c is None:
                continue
            where = f"{kind} {item['name']!r} {name!r}"
            built = c.get('States') or []
            if not want:
                # One image on every state - an icon that is not feedback.
                for i, bs in enumerate(built):
                    checked += 1
                    problems += _state_image(where, i, bs, c, op['image'], op.get('fill'),
                                             assets)
                continue
            if len(built) != len(want):
                extra = [s.get('Name') for s in built[len(want):]]
                problems.append(
                    f'{where}: planned {len(want)} states but the built control has '
                    f'{len(built)}' + (f" - {', '.join(map(repr, extra))} the spec never "
                                        f'named' if extra else ' - it cannot show the '
                                        f'feedback the spec describes'))
                continue

            fields = op.get('fields') or {}
            for key, label in (('<TLPPressFeedbackStateID>k__BackingField', 'press'),
                               ('<TLPDefaultStateID>k__BackingField', 'default')):
                bkey = key[1:key.index('>')]
                if key in fields and c.get(bkey) != fields[key]:
                    problems.append(f'{where}: {label} state is {c.get(bkey)}, planned '
                                    f'{fields[key]}')

            dominant = {}
            for i, ws in enumerate(want):
                bs = built[i]
                checked += 1
                if ws.get('name') and bs.get('Name') != ws['name']:
                    problems.append(
                        f"{where} state {i}: named {bs.get('Name')!r}, planned {ws['name']!r}")
                if 'text' in ws and not c.get('FlattenText') and \
                        (bs.get('Text') or '') != ws['text']:
                    problems.append(f"{where} state {bs.get('Name') or i!r}: caption "
                                    f"{bs.get('Text')!r}, planned {ws['text']!r}")
                # The caption is drawn live, so its color is in the model, not
                # the artwork - read it there.
                tc = bs.get('TextColor')
                if ws.get('text_color') is not None:
                    if not isinstance(tc, dict):
                        problems.append(f"{where} state {bs.get('Name') or i!r}: planned text "
                                        f"color {_hex(_rgb(ws['text_color']))}, but the built "
                                        f'state carries none')
                    elif (tc.get('R'), tc.get('G'), tc.get('B')) != _rgb(ws['text_color']):
                        problems.append(
                            f"{where} state {bs.get('Name') or i!r}: text color "
                            f"{_hex((tc.get('R'), tc.get('G'), tc.get('B')))}, planned "
                            f"{_hex(_rgb(ws['text_color']))}")
                tid = bs.get('TLPImageID')
                if tid is None or tid < 0:
                    problems.append(
                        f"{kind} {item['name']!r} {name!r} state "
                        f"{bs.get('Name') or i!r}: Build produced no artwork "
                        f'(TLPImageID {tid}), so it will draw nothing')
                    continue
                problems += _state_image(where, i, bs, c, ws.get('image'), ws.get('fill'),
                                         assets)
                shares = _shares(assets, tid)
                if not shares:
                    # A deliberately transparent Off state is a real idiom -
                    # Extron's own 'Lighting Preset' buttons are transparent
                    # when off - so this is only wrong if a fill was planned.
                    if _painted(ws.get('fill')):
                        problems.append(
                            f"{kind} {item['name']!r} {name!r} state "
                            f"{bs.get('Name') or i}: artwork {tid} is missing or "
                            f'fully transparent, but a fill was planned')
                    dominant[i] = (tid, None)
                    continue
                top, top_share = max(shares.items(), key=lambda kv: kv[1])
                dominant[i] = (tid, top)
                if not _painted(ws.get('fill')):
                    continue
                target = _rgb(ws['fill'])
                if top == target:
                    continue
                mine = shares.get(target, 0.0)
                if mine >= WEAK_FILL:
                    notes.append(
                        f"{kind} {item['name']!r} {name!r} state "
                        f"{bs.get('Name') or i}: fill {_hex(target)} is {mine:.0%} of "
                        f'the artwork, behind {_hex(top)} at {top_share:.0%}')
                else:
                    problems.append(
                        f"{kind} {item['name']!r} {name!r} state "
                        f"{bs.get('Name') or i}: planned fill {_hex(target)} is "
                        f'{mine:.0%} of the built artwork; it is mostly '
                        f'{_hex(top)} ({top_share:.0%})')

            # Pairwise, for any number of states: Build rasterizes each state
            # and dedupes identical images to one TLPImageID, so two states the
            # plan drew differently but that built as one image are one state to
            # the eye. Only fill, stroke and border are in the artwork. A
            # caption and its color are drawn live from layout.json - the
            # applier clears flattenText - so 'Warming Up' and 'Cooling Down' on
            # one fill share an image and are still two states; the caption and
            # text-color checks above cover them. A kit image is in the artwork.
            def look(w):
                return tuple(str(w.get(k)) for k in ('fill', 'stroke', 'border', 'image'))
            for i in range(len(want)):
                for j in range(i + 1, len(want)):
                    if look(want[i]) == look(want[j]):
                        continue
                    ti, tj = built[i].get('TLPImageID'), built[j].get('TLPImageID')
                    if ti is not None and ti >= 0 and ti == tj:
                        problems.append(
                            f"{where}: states {want[i].get('name')!r} and "
                            f"{want[j].get('name')!r} were planned differently but built "
                            f'as the same artwork {ti} - the panel cannot tell them apart')

            # The point of the whole feature. If the plan asked for two
            # different appearances and the panel cannot tell them apart, the
            # button is decorative.
            fills_differ = len({_hex(_rgb(w['fill'])) if _painted(w.get('fill')) else None
                                for w in want}) > 1
            images = [(w.get('image') or {}).get('name') for w in want]
            if (fills_differ or len(set(images)) > 1) and len(dominant) > 1:
                ids = {v[0] for v in dominant.values()}
                colors = {v[1] for v in dominant.values()}
                if len(ids) == 1:
                    problems.append(
                        f"{kind} {item['name']!r} {name!r}: every state shares artwork "
                        f'{ids.pop()}, so Off and On are the same pixels - this button '
                        f'cannot show feedback')
                # By plurality color only where there are no kit images: two
                # speaker icons are both mostly their #414459 ground, and each
                # state's image is checked against its own artwork above.
                elif fills_differ and not any(images) and len(colors) == 1:
                    problems.append(
                        f"{kind} {item['name']!r} {name!r}: the states were planned in "
                        f'different colors but all built {_hex(colors.pop())} - no '
                        f'visible feedback')
    return problems, notes, checked


def check_thumbs(plan_items, table, assets, kind):
    """A slider's thumb must be the kit image the plan gave it.

    It is an image (sliderThumbImageField), not a color, and a clone keeps its
    donor's: an Afterburn slider built under the medium-blue scheme came back
    with the seed's scheme-1 periwinkle thumb while every field that names a
    color read right. Build draws the thumb as its own asset,
    SliderIndicatorImageID, so that is what is compared.
    """
    problems, checked = [], 0
    for item in plan_items:
        got = table.get(item['name'])
        if got is None:
            continue
        by_name = _index(got)
        for op in item['controls']:
            img = op.get('thumb_image')
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if not img or c is None:
                continue
            checked += 1
            where = f"{kind} {item['name']!r} {name!r} thumb"
            tid = c.get('SliderIndicatorImageID')
            if tid is None or tid < 0 or tid not in assets:
                problems.append(f'{where}: planned {img["name"]!r}, but Build drew no thumb '
                                f'(SliderIndicatorImageID {tid})')
                continue
            if not img.get('file') or not os.path.exists(img['file']):
                continue
            w, h = Image.open(io.BytesIO(assets[tid])).size
            off = image_mismatch(img['file'], assets[tid], w, h)
            if off > IMAGE_OFF:
                problems.append(f"{where}: {off:.0%} of it differs from the planned "
                                f"{img['name']!r} - it is not that image")
    return problems, checked


def check_fonts(plan_items, table, kind):
    """Typography must reach the panel, not just the preview.

    `Apply-GdlPlan.ps1` set no font at all for as long as it existed, so a
    spec's `size` was honored by `gdl.spec render` and then dropped: every
    generated label built at the donor's 20pt, every button at 13pt, every shape
    at 14.25pt. The preview was an honest picture of a design nobody was
    building. Worse, `gdl.spec check` enforces Extron's >=14pt body-text rule
    against the spec, so the one gate that should have caught it was measuring a
    number that never left the file.

    Unlike fill, this one IS readable from the model - `layout.json` carries
    Font.PointSize per control - so it needs no artwork.
    """
    problems, checked = [], 0
    for item in plan_items:
        got = table.get(item['name'])
        if got is None:
            continue
        by_name = _index(got)
        for op in item['controls']:
            want = op.get('font')
            if not want:
                continue
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if c is None:
                continue
            font = c.get('Font') or {}
            size = want.get('size')
            if size is not None and font.get('PointSize') is not None:
                checked += 1
                if abs(float(font['PointSize']) - float(size)) > 0.01:
                    problems.append(
                        f"{kind} {item['name']!r} {name!r}: planned {size}pt, built "
                        f"{font['PointSize']}pt - the applier is leaving the donor's font")
            if want.get('name') and font.get('Name') and font['Name'] != want['name']:
                problems.append(f"{kind} {item['name']!r} {name!r}: planned font "
                                f"{want['name']!r}, built {font['Name']!r}")
            style = font.get('Style') or {}
            for key, built in (('bold', 'Bold'), ('italic', 'Italic')):
                if want.get(key) is not None and built in style:
                    if bool(style[built]) != bool(want[key]):
                        problems.append(f"{kind} {item['name']!r} {name!r}: planned "
                                        f'{key}={want[key]}, built {style[built]}')
    return problems, checked


# Mean difference per channel, 0-255, above which a page's artwork is not the
# planned image over the planned fill. Resampling a 6400x4000 image to the page
# accounts for a few levels.
IMAGE_TOLERANCE = 12


def fit_image(file, w, h):
    """`file` drawn into a w x h box as Build draws a button's image:
    ImageLayoutEnum Fill (fit, keeping the aspect), MiddleCenter."""
    src = Image.open(file).convert('RGBA')
    k = min(w / src.width, h / src.height)
    src = src.resize((max(1, round(src.width * k)), max(1, round(src.height * k))),
                     Image.Resampling.LANCZOS)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    out.alpha_composite(src, ((w - src.width) // 2, (h - src.height) // 2))
    return out


# A built state's image is judged by drawing what the plan asked for - its fill,
# then its image fitted - and comparing it with the artwork both ways: a pixel
# either one inks that the other does not. Both ways, because one icon can be
# a subset of the next (a speaker with one wave inside a speaker with two). The
# edge of the box is left out, which is where the border and rounded corners
# are; the caption is drawn live, so it is not in the artwork. A pixel is off
# when a channel differs by more than IMAGE_PIXEL levels; more than IMAGE_OFF
# of the inked pixels off and it is another image. Measured on the Afterburn
# 1035 seed's 117 captionless image states against their own kit files: all
# under 8%, bar a round button whose 3 px ellipse ring nothing here draws
# (36%). Against the other states' files - another icon, the unselected
# variant, another accent's - 50% and up. The blind spot is one volume level
# against the next: at 64 px they differ by one thin wave, 7%.
IMAGE_PIXEL, IMAGE_OFF, IMAGE_INSET = 60, 0.25, 4


def _max_channel(im):
    r, g, b = im.split()[:3]
    return ImageChops.lighter(ImageChops.lighter(r, g), b)


def image_mismatch(file, art_bytes, w, h, fill=None):
    """Share of the inked pixels that differ between the built artwork and
    `file` fitted into w x h over `fill` (an ARGB int, or None)."""
    base = (((fill >> 16) & 255, (fill >> 8) & 255, fill & 255, (fill >> 24) & 255)
            if fill is not None else (0, 0, 0, 0))
    want = Image.new('RGBA', (w, h), base)
    want.alpha_composite(fit_image(file, w, h))
    got = Image.open(io.BytesIO(art_bytes)).convert('RGBA')
    if got.size != (w, h):
        got = got.resize((w, h))
    # Onto one opaque key color, so a transparent pixel compares as itself.
    key = Image.new('RGBA', (w, h), (255, 0, 255, 255))
    plain = Image.alpha_composite(key, Image.new('RGBA', (w, h), base)).convert('RGB')
    a = Image.alpha_composite(key, want).convert('RGB')
    b = Image.alpha_composite(key, got).convert('RGB')

    def over(im):
        return _max_channel(im).point(lambda d: 255 if d > IMAGE_PIXEL else 0)

    # Inked: neither the fill nor nothing. The border resource decides the
    # fill's shape - Extron's round Power button is an ellipse - so a pixel
    # that is fill on one side and empty on the other is the border's
    # business, not the image's.
    empty = key.convert('RGB')

    def ink(im):
        return ImageChops.multiply(over(ImageChops.difference(im, plain)),
                                   over(ImageChops.difference(im, empty)))

    region = Image.new('L', (w, h), 0)
    region.paste(255, (IMAGE_INSET, IMAGE_INSET, w - IMAGE_INSET, h - IMAGE_INSET))
    inked = ImageChops.multiply(ImageChops.lighter(ink(a), ink(b)), region)
    # A pixel is off when nothing within one pixel of it on the other side
    # matches - a 2 px kit line downscaled sevenfold lands a pixel apart in
    # GDI+ and in Pillow - looked at from both sides, or a thin extra stroke
    # would find the empty pixels beside it and pass.
    def unmatched(x, y):
        near = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                d = _max_channel(ImageChops.difference(x, ImageChops.offset(y, dx, dy)))
                near = d if near is None else ImageChops.darker(near, d)
        return near.point(lambda d: 255 if d > IMAGE_PIXEL else 0)

    off = ImageChops.multiply(ImageChops.lighter(unmatched(a, b), unmatched(b, a)), inked)
    n = inked.histogram()[255]
    return off.histogram()[255] / n if n else 0.0


def _state_image(where, i, bs, c, image, fill, assets):
    """A state's artwork must be the kit image the plan gave it.

    The button's model names no image once built - layout.json carries only
    the artwork - so the artwork is compared with the image fitted over the
    planned fill (image_mismatch)."""
    if not image:
        return []
    tid = bs.get('TLPImageID')
    label = f"{where} state {bs.get('Name') or i!r}"
    if tid is None or tid < 0 or tid not in assets:
        return [f"{label}: planned image {image['name']!r}, but the state built with no "
                f'artwork (TLPImageID {tid})']
    if not image.get('file') or not os.path.exists(image['file']):
        return []
    off = image_mismatch(image['file'], assets[tid], c['Width'], c['Height'], fill)
    if off > IMAGE_OFF:
        return [f"{label}: {off:.0%} of the artwork differs from the planned image "
                f"{image['name']!r} - it is not that image"]
    return []


def _check_background_image(spec, pg, assets):
    """The page's artwork must be its planned image, fitted over its fill.

    layout.json does not name a page's background image, so the artwork is
    the only witness. With the image's file at hand, composite it the way the
    page draws it and compare; without one, at least the page must not have
    built as a flat fill.
    """
    img = spec['background_image']
    tid = pg.get('TLPImageID')
    where = f"page {spec['name']!r} background image {img['name']!r}"
    if tid is None or tid < 0 or tid not in assets:
        return [f'{where}: the page built with no artwork (TLPImageID {tid})']
    art = Image.open(io.BytesIO(assets[tid])).convert('RGB')
    if img.get('file') and os.path.exists(img['file']):
        fill = spec['background']
        want = Image.new('RGBA', art.size, _rgb(fill) + ((fill >> 24) & 0xFF,))
        src = Image.open(img["file"]).convert("RGBA").resize(art.size, Image.Resampling.LANCZOS)
        want = Image.alpha_composite(want, src).convert('RGB')
        hist = ImageChops.difference(art, want).convert('L').histogram()
        mean = sum(i * n for i, n in enumerate(hist)) / max(1, sum(hist))
        if mean > IMAGE_TOLERANCE:
            return [f'{where}: the page artwork differs from the image over its fill by '
                    f'{mean:.0f} levels on average - it is not the planned image']
        return []
    shares = _shares(assets, tid)
    if shares and max(shares.values()) >= 0.99:
        return [f'{where}: the page artwork is a single flat color, so the image did not '
                f'reach it']
    return []


def check_page_background(plan_pages, pages, assets):
    """The donor's background image is a separate reference from its artwork.

    Clearing `<TLPImageID>` alone left `backgroundImageField` pointing at the
    donor's image, Build re-rasterized fill and image together, and the donor's
    artwork came back as a tint over the whole page. Reading the page asset is
    what catches that; the fill field on its own looked correct throughout.
    """
    problems = []
    for spec in plan_pages:
        pg = pages.get(spec['name'])
        if pg is None or spec.get('background') is None:
            continue
        if spec.get('background_image'):
            problems += _check_background_image(spec, pg, assets)
            continue
        want = _rgb(spec['background'])
        tid = pg.get('TLPImageID')
        if tid is None or tid < 0:
            continue
        shares = _shares(assets, tid)
        if not shares:
            continue
        top, top_share = max(shares.items(), key=lambda kv: kv[1])
        if top != want:
            problems.append(f"page {spec['name']!r} background: planned {_hex(want)}, "
                            f'artwork is mostly {_hex(top)} ({top_share:.0%}) - a donor '
                            f'background image re-rasterized under the fill looks '
                            f'exactly like this')
        elif top_share < 0.99:
            problems.append(f"page {spec['name']!r} background: {_hex(want)} covers only "
                            f'{top_share:.0%} of the page artwork, so something else is '
                            f'painted under the controls')
    return problems


def _index(page):
    """name -> control. Names are unique per page by construction (spec ids)."""
    out = {}
    for c in page.get('Controls') or []:
        out.setdefault(c.get('Name'), c)
    return out


def _hex_rgb(h):
    """'#AARRGGBB' -> ((r, g, b), alpha), from an edit plan."""
    v = int(h.lstrip('#'), 16)
    return _rgb(v), (v >> 24) & 0xFF


def _edit_fill(where, tid, want, assets):
    """(problem or None, note or None): is `want` the plurality color of the
    artwork `tid`? The same test check_fills applies to an authored control."""
    rgb, alpha = _hex_rgb(want)
    if alpha != 0xFF:
        return None, None               # a translucent fill has no opaque pixels
    if tid is None or tid < 0:
        return (f'{where}: fill {_hex(rgb)} was asked for, but Build produced no '
                f'artwork (TLPImageID {tid})'), None
    shares = _shares(assets, tid)
    if not shares:
        return f'{where}: artwork {tid} is missing or fully transparent', None
    top, top_share = max(shares.items(), key=lambda kv: kv[1])
    if top == rgb:
        return None, None
    mine = shares.get(rgb, 0.0)
    if mine >= WEAK_FILL:
        return None, (f'{where}: fill {_hex(rgb)} is {mine:.0%} of the artwork, '
                      f'behind {_hex(top)} at {top_share:.0%}')
    return (f'{where}: fill {_hex(rgb)} is {mine:.0%} of the built artwork; it is '
            f'mostly {_hex(top)} ({top_share:.0%})'), None


def _edit_text_color(where, got, want):
    rgb, _ = _hex_rgb(want)
    if not isinstance(got, dict):
        return f'{where}: text color {_hex(rgb)} was asked for, but it built with none'
    have = (got.get('R'), got.get('G'), got.get('B'))
    if have != rgb:
        return f'{where}: text color is {_hex(have)}, the edit asked for {_hex(rgb)}'
    return None


def check_edit_states(op, c, label, assets):
    """Each state an edit wrote, and - for the `states` op - every state.

    (problems, notes, unverifiable). A state is found by index, which is what
    the plan addressed and what the control program sets. Colors are read the
    way check_fills reads them: a fill off the state's own artwork, a text
    color off the model, because the caption is drawn live.
    """
    problems, notes, unverifiable = [], [], []
    built = c.get('States') or []
    fields = op.get('fields') or {}
    if op.get('state_count') is not None:
        if len(built) != op['state_count']:
            names = [s.get('Name') for s in built]
            return ([f"{label}: {len(built)} states built ({', '.join(map(repr, names))}), "
                     f"the edit asked for {op['state_count']}"], [], [])
        for key, what in (('<TLPPressFeedbackStateID>k__BackingField', 'press'),
                          ('<TLPDefaultStateID>k__BackingField', 'default')):
            bkey = key[1:key.index('>')]
            if key in fields and c.get(bkey) != fields[key]:
                problems.append(f'{label}: {what} state is {c.get(bkey)}, the edit asked '
                                f'for {fields[key]}')

    want = {}
    for i, s in enumerate(op.get('expect_states') or []):
        want[i] = {k: v for k, v in s.items() if v is not None}
    for ps in op.get('per_state') or []:
        w = want.setdefault(ps['index'], {})
        f, col = ps.get('fields') or {}, ps.get('colors') or {}
        if 'nameField' in f:
            w['name'] = f['nameField']
        if 'textField' in f:
            w['text'] = f['textField']
        if ps.get('flattened'):
            w.pop('text', None)
            w['ftext'] = ps['ftext']
        for field, key in (('borderFillColorField', 'fill'), ('textColorField', 'text_color'),
                           ('borderColorField', 'stroke')):
            if field in col:
                w[key] = col[field]

    for i, w in sorted(want.items()):
        if i >= len(built):
            problems.append(f'{label}: the edit wrote state {i}, but it built with '
                            f'{len(built)} state(s)')
            continue
        bs = built[i]
        where = f"{label} state {i} {bs.get('Name')!r}"
        if 'name' in w and bs.get('Name') != w['name']:
            problems.append(f"{label} state {i}: named {bs.get('Name')!r}, the edit asked "
                            f"for {w['name']!r}")
        if 'ftext' in w:
            # Formatted text is baked into the artwork and reads back as ''.
            unverifiable.append(f"{where} -> {w['ftext']!r}")
        elif 'text' in w and not c.get('FlattenText') and \
                (bs.get('Text') or '') != w['text']:
            problems.append(f"{where}: caption is {bs.get('Text')!r}, the edit asked for "
                            f"{w['text']!r}")
        if 'text_color' in w:
            p = _edit_text_color(where, bs.get('TextColor'), w['text_color'])
            if p:
                problems.append(p)
        if 'fill' in w:
            p, n = _edit_fill(where, bs.get('TLPImageID'), w['fill'], assets)
            if p:
                problems.append(p)
            if n:
                notes.append(n)

    # Two states the edit made look different must be two images. Only fill
    # and stroke are in the artwork; a caption and its color are drawn live.
    exp = op.get('expect_states') or []
    for i in range(len(exp)):
        for k in range(i + 1, min(len(exp), len(built))):
            if (exp[i].get('fill'), exp[i].get('stroke')) == \
                    (exp[k].get('fill'), exp[k].get('stroke')):
                continue
            ti, tk = built[i].get('TLPImageID'), built[k].get('TLPImageID')
            if ti is not None and ti >= 0 and ti == tk:
                problems.append(f"{label}: states {exp[i]['name']!r} and {exp[k]['name']!r} "
                                f'were meant to look different but built as the same '
                                f'artwork {ti}')
    return problems, notes, unverifiable


def check_edits(plan, j, assets=None):
    """An EDIT plan addresses existing controls by id, so verification is a
    direct lookup: did the field we asked for actually change?

    Captions and colors are checked state by state (check_edit_states), since
    that is how the plan writes them. A control's own caption, where it has no
    states, is compared with the merged caption layout.json reports.
    """
    assets = assets or {}
    pages = {p['ID']: p for p in j['Pages'] + j['PopupPages']}
    problems, checked, unverifiable, notes = [], 0, [], []
    for op in plan['controls']:
        pg = pages.get(op['page'])
        if pg is None:
            problems.append(f"page id {op['page']} is not in the built file")
            continue
        c = next((x for x in (pg.get('Controls') or []) if x.get('ID') == op['control']),
                 None)
        if c is None:
            problems.append(f"control id {op['control']} is not on page {pg['Name']!r}")
            continue
        checked += 1
        label = f"{pg['Name']!r} {c.get('Name')!r}"
        if op.get('states') or op.get('states_colors') or op.get('states_ftext') is not None:
            problems.append(f"{label}: this plan writes every state alike - re-plan it "
                            f'with gdl.edit, which writes each state by index')
            continue
        want_text = (op.get('fields') or {}).get('textField')
        if want_text is not None and not op.get('per_state'):
            got = (_caption(c) or '').replace('\t', '').replace('\r\n', ' ').strip()
            if got != want_text:
                problems.append(f'{label}: caption is {got!r}, the edit asked for '
                                f'{want_text!r}')
        own = op.get('colors') or {}
        if 'textColorField' in own and not c.get('States'):
            p = _edit_text_color(label, c.get('TextColor'), own['textColorField'])
            if p:
                problems.append(p)
        if 'borderFillColorField' in own and not c.get('States'):
            p, n = _edit_fill(label, c.get('TLPImageID'), own['borderFillColorField'], assets)
            if p:
                problems.append(p)
            if n:
                notes.append(n)
        p, n, u = check_edit_states(op, c, label, assets)
        problems += p
        notes += n
        unverifiable += u
        # 'UserId', as layout.json spells it. This said 'UserID', matched no
        # key, and the `key not in c` guard below skipped it - so a renumber
        # was never actually checked against the build.
        for f, key in (('leftField', 'Left'), ('topField', 'Top'),
                       ('widthField', 'Width'), ('heightField', 'Height'),
                       ('userIdField', 'UserId')):
            want = (op.get('fields') or {}).get(f)
            if want is None or key not in c:
                continue
            if c[key] != want:
                problems.append(f"{pg['Name']!r} {c.get('Name')!r}: {key} is {c[key]}, "
                                f'the edit asked for {want}')
    for u in unverifiable:
        # A formatted-text caption is baked into the artwork, and layout.json
        # reports it as '' both before and after the edit. There is nothing
        # here to compare, so checking it would report a failure that is
        # really a lookup in the wrong place. Say so instead.
        print(f'  NOT VERIFIABLE HERE (caption is baked into the artwork, '
              f'compare the asset PNG): {u}')
    for n in notes:
        print(f'  FILL NOT DOMINANT (survived, but check it by eye): {n}')
    return problems, checked


def check_start_page(plan, j):
    """Does the panel boot into the page the plan asked for?

    A page's ID only exists once the applier has picked a free one, so the plan
    names the page and this joins on the name. Without the check a generated
    panel booted into the donor's start page - DefaultPage 21, the client's
    '1000 - Home' - and nothing noticed.
    """
    want = plan.get('default_page')
    if not want:
        return []
    page = next((p for p in j['Pages'] if p['Name'] == want), None)
    if page is None:
        return [f'start page {want!r} is not in the built file']
    got = j.get('DefaultPage')
    if got != page['ID']:
        name = next((p['Name'] for p in j['Pages'] if p['ID'] == got), '?')
        return [f'the panel boots into {name!r} (DefaultPage {got}), not the planned '
                f"start page {want!r} (ID {page['ID']})"]
    return []


def check_modal(plan, j):
    """Did each popup build modal or standard as planned, and can a modal show?

    The applier once wrote modalField = false on every popup, so a modal
    confirmation built as an ungrouped standard popup that no reference can
    show. Build places one full-canvas reference per modal popup on every page,
    with PopupPageID.PopupID set to the popup's own ID - so a modal with no such
    reference on a generated page cannot appear there.
    """
    out = []
    popups = {p['Name']: p for p in j['PopupPages']}
    pages = {p['Name']: p for p in j['Pages']}
    for pu in plan.get('popups') or []:
        got = popups.get(pu['name'])
        if got is None:
            continue                     # check() already reports a missing popup
        want = bool(pu.get('modal'))
        if bool(got.get('Modal')) != want:
            out.append(f"popup {pu['name']!r} built {'modal' if got.get('Modal') else 'standard'}"
                       f", the plan asked for {'modal' if want else 'standard'}")
            continue
        if not want:
            continue
        for pg in plan.get('pages') or []:
            built = pages.get(pg['name'])
            if built is None:
                continue
            if not any(c.get('Type') == 6 and isinstance(c.get('PopupPageID'), dict)
                       and c['PopupPageID'].get('IsPopupPageIdValid')
                       and c['PopupPageID'].get('PopupID') == got['ID']
                       for c in built.get('Controls') or []):
                out.append(f"page {pg['name']!r} has no reference to modal popup "
                           f"{pu['name']!r}, so it cannot be shown there")
    return out


def check_placed(plan, pages, popups):
    """Each authored control is in the built file, where it was put, and
    captioned - or, for a clock, patterned - as planned."""
    problems = []
    checked = 0
    for spec, table, kind in ((plan['pages'], pages, 'page'),
                              (plan.get('popups') or [], popups, 'popup')):
        for item in spec:
            got = table.get(item['name'])
            if got is None:
                problems.append(f"{kind} {item['name']!r} is not in the built file")
                continue
            by_name = _index(got)
            for op in item['controls']:
                f = op['fields']
                name = f.get('nameField')
                c = by_name.get(name)
                if c is None:
                    problems.append(f"{kind} {item['name']!r}: control {name!r} "
                                    f'is not in the built file')
                    continue
                checked += 1
                want = (f.get('leftField'), f.get('topField'),
                        f.get('widthField'), f.get('heightField'))
                have = (c['Left'], c['Top'], c['Width'], c['Height'])
                if any(w is not None and w != h for w, h in zip(want, have)):
                    extra = ''
                    if have[:2] == (0, 0) and want[:2] != (0, 0):
                        extra = (' - moved to the origin, which is what GUI Designer '
                                 'does to a control that does not fit its page')
                    problems.append(
                        f"{kind} {item['name']!r} {name!r} "
                        f"({TYPE_NAME.get(c.get('Type'), c.get('Type'))}): "
                        f'planned {want}, built {have}{extra}')
                want_text = f.get('textField')
                if want_text is not None and _caption(c) != want_text:
                    problems.append(f"{kind} {item['name']!r} {name!r}: caption "
                                    f'{_caption(c)!r}, planned {want_text!r}')
                # A clock's caption is only a sample; what it shows on the
                # panel is its pattern.
                want_pattern = f.get('patternField')
                if want_pattern is not None and c.get('Pattern') != want_pattern:
                    problems.append(f"{kind} {item['name']!r} {name!r}: clock pattern "
                                    f"{c.get('Pattern')!r}, planned {want_pattern!r}")
    return problems, checked


def check(plan_path, built_path):
    with open(plan_path, encoding='utf-8') as fh:
        plan = json.load(fh)
    j, assets = load(built_path)
    if plan.get('generated_by') == 'gdl.edit':
        return check_edits(plan, j, assets)
    pages = {p['Name']: p for p in j['Pages']}
    popups = {p['Name']: p for p in j['PopupPages']}

    problems, checked = check_placed(plan, pages, popups)

    # A popup reference bound to nothing reads "Unassigned" on the panel and is
    # invisible in the file, so check the binding survived rather than trusting
    # that the applier's own assertion still holds after a build.
    groups = {g['ID'] for g in (j.get('PopupGroups') or [])}
    for pg in pages.values():
        for c in pg.get('Controls') or []:
            pp = c.get('PopupPageID')
            if not isinstance(pp, dict):
                continue
            if pp.get('IsPopupGroupIdValid') and groups and pp['GroupID'] not in groups:
                problems.append(f"page {pg['Name']!r} {c.get('Name')!r}: bound to popup "
                                f"group {pp['GroupID']}, which the built file has no "
                                f'record of')

    # Color, read off the artwork rather than the model - see _shares().
    for spec, table, kind in ((plan['pages'], pages, 'page'),
                              (plan.get('popups') or [], popups, 'popup')):
        probs, notes, n = check_fills(spec, table, assets, kind)
        problems += probs
        checked += n
        for note in notes:
            print(f'  FILL NOT DOMINANT (survived, but check it by eye): {note}')
        probs, n = check_fonts(spec, table, kind)
        problems += probs
        checked += n
        probs, notes, n = check_states(spec, table, assets, kind)
        problems += probs
        checked += n
        probs, n = check_thumbs(spec, table, assets, kind)
        problems += probs
        checked += n
        for note in notes:
            print(f'  STATE FILL NOT DOMINANT (survived, but check it by eye): {note}')
    problems += check_page_background(plan['pages'], pages, assets)
    problems += check_start_page(plan, j)
    problems += check_modal(plan, j)

    return problems, checked


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[0])
        print('usage: verify_built.py <plan.json> <built.gdl>')
        return 2
    problems, checked = check(argv[1], argv[2])
    for p in problems:
        print('  ' + p)
    print(f'{checked} authored control(s) verified against the build, '
          f'{len(problems)} problem(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
