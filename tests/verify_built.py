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

  * Build's own popup references on a page. Build adds one full-canvas
    PBPopupPageReference per MODAL popup in the project, to every page, so
    every generated page comes back with one per modal the spec names - and
    one per donor modal too, where the spec keeps the donor's pages. Nobody
    authored them; that is Build doing its job.
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
# built files - the client donor and two seeds - against each control's
# `__type`; this once said Line 9, DateTime 12, Slider 14 and Level 15.
# tests/test_verify_built.py pins it.
TYPE_NAME = {6: 'PopupPageReference', 7: 'Button', 8: 'DateTime', 9: 'Level',
             10: 'Image', 11: 'Label', 12: 'Line', 13: 'Shape', 27: 'Slider'}
# TextAlignment -> the spec's word for it, for a problem to say ('centre' is an
# input spelling only).
_ALIGN_NAME = {v: k for k, v in __import__('gdl.spec', fromlist=['ALIGN']).ALIGN.items()
               if k != 'centre'}
# No alignment: what GUI Designer writes on a control whose states disagree -
# all 69 such buttons in the archived builds, and none of the 8463 seed and
# fixture buttons whose states agree.
ALIGN_MIXED = 9


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


def _shares_at(assets, tid, alpha):
    """{(r,g,b): share of all pixels} among those within 3 of `alpha`.

    _shares's opaque-only count reads a translucent fill as nothing at all.
    """
    blob = assets.get(tid)
    if blob is None:
        return {}
    raw = Image.open(io.BytesIO(blob)).convert('RGBA').tobytes()
    n = len(raw) // 4
    counts = collections.Counter(raw[i:i + 3] for i in range(0, len(raw), 4)
                                 if abs(raw[i + 3] - alpha) <= 3)
    return {tuple(k): v / n for k, v in counts.items()} if n else {}


def _fill_tolerance(alpha, under_image=False):
    """How far a channel of a translucent fill at `alpha` can build off its
    plan.

    Build premultiplies each channel rounding to nearest, (c * a + 127) // 255,
    and unpremultiplies it truncating through a 16.16 reciprocal,
    p * ((255 << 16) // a) >> 16 - twice for a fill, and a third time inside
    the rect of an image drawn over it. That reproduces every translucent fill
    in Mach's call builds and its 1035, 725 and 525 seeds - 26 looks at nine
    alphas from 50 to 220, 15 of them under an image - and a channel can come
    back high as well as low (the 1035 seed's VC Call, #86D161 at 80 under its
    icon, built green 210). Mach's Make Call, #659945 at 220, builds (99, 151,
    69) bare and (98, 150, 69) under its 755x440 icon, except in the last
    column and row, which the fitted icon does not reach; the seed's own
    Initiate Call, the same fill under the same icon, is those very bytes. At
    every alpha two passes stay within 255 // alpha + 1 and three within one
    more, and only an image adds the third."""
    return 255 // alpha + 1 + bool(under_image)


def _fill_shares(assets, tid, argb, under_image=False):
    """_shares() for an opaque fill. For a translucent one, {color: share of
    the visible pixels}, every pixel at the fill's own alpha (within 3) and
    color (within Build's rounding, _fill_tolerance(), which an image drawn
    over the fill - `under_image` - widens) counted as the planned (r, g, b)
    itself, the rest by their own (r, g, b, a). Build writes a translucent
    fill's alpha exactly: Turbulence's rail, black at 38, came back (0, 0, 0,
    38) throughout, and its shade, #020D1A at 128, as (1, 13, 25, 128). Read
    off the opaque pixels alone it has none, and nothing would be checked."""
    if _opaque(argb):
        return _shares(assets, tid)
    blob = assets.get(tid)
    if blob is None:
        return {}
    want, alpha = _rgb(argb), (argb >> 24) & 0xFF
    tol = _fill_tolerance(alpha, under_image)
    raw = Image.open(io.BytesIO(blob)).convert('RGBA').tobytes()
    counts = collections.Counter()
    for i in range(0, len(raw), 4):
        r, g, b, a = raw[i:i + 4]
        if not a:
            continue
        if (abs(a - alpha) <= 3 and abs(r - want[0]) <= tol and abs(g - want[1]) <= tol
                and abs(b - want[2]) <= tol):
            counts[want] += 1
        else:
            counts[(r, g, b, a)] += 1
    total = sum(counts.values())
    return {k: v / total for k, v in counts.items()} if total else {}


def _bare(assets, tid):
    """Why artwork `tid` gave a fill nothing to read: absent, fully
    transparent, or drawn but nowhere opaque - an opaque fill built
    see-through, which the panel does draw."""
    blob = assets.get(tid)
    if blob is None:
        return f'artwork {tid} is missing'
    _, hi = Image.open(io.BytesIO(blob)).convert('RGBA').getchannel('A').getextrema()
    if not hi:
        return f'artwork {tid} is fully transparent'
    return f'artwork {tid} has no opaque pixel - it built see-through, at alpha {hi} at most'


def _rgb(argb):
    return ((argb >> 16) & 0xFF, (argb >> 8) & 0xFF, argb & 0xFF)


def _hex(t):
    return '#%02X%02X%02X' % t


def _hexa(t):
    """A color from _fill_shares(): (r, g, b), or (r, g, b, a) off the fill."""
    if len(t) < 4:
        return _hex(t)
    return _hex(t[:3]) + (' opaque' if t[3] == 0xFF else f' at alpha {t[3]}')


def _fill_hex(argb):
    a = (argb >> 24) & 0xFF
    return _hex(_rgb(argb)) + ('' if a == 0xFF else f' at alpha {a}')


def _painted(argb):
    """A planned fill that paints. The spec writes a button with no fill as a
    transparent one (alpha 0), so the donor's does not bleed through - that is
    no fill to find in the artwork."""
    return argb is not None and (argb >> 24) & 0xFF > 0


def _opaque(argb):
    """A planned fill the artwork's opaque pixels can confirm. _shares()
    counts only pixels over alpha 250, so a translucent fill - Mach's `shade`,
    Shockwave's `overlay` - is read at its own alpha by _fill_shares()."""
    return argb is not None and (argb >> 24) & 0xFF == 0xFF


# What the spec plans clear when it has no fill (gdl/spec.py _base_look), whose
# artwork is then its words or outline alone. A button's states carry its look.
CLEAR_TYPES = ('PBLabel', 'PBShape', 'PBLine', 'PBDateTime')

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
            # A Level's fill is its track, drawn as its empty art. Build names
            # its full bar as the TLPImageID - every Level in the seeds and
            # fixtures, where a Slider's is its track - so that would compare
            # the fill with the accent bar.
            field = 'TLPMinValueImageID' if TYPE_NAME.get(c.get('Type')) == 'Level' else 'TLPImageID'
            tid = c.get(field)
            want, label = _rgb(op['fill']), _fill_hex(op['fill'])
            if tid is None or tid < 0:
                problems.append(f"{kind} {item['name']!r} {name!r}: planned fill "
                                f'{label} but Build produced no artwork '
                                f'({field} {tid}), so it will draw nothing')
                continue
            # A button's op carries its first state's image, as its TLPImageID
            # is that state's artwork.
            shares = _fill_shares(assets, tid, op['fill'], op.get('image'))
            if not shares:
                problems.append(f"{kind} {item['name']!r} {name!r}: planned fill {label}, but "
                                f'{_bare(assets, tid)}')
                continue
            checked += 1
            top, top_share = max(shares.items(), key=lambda kv: kv[1])
            if top == want:
                continue
            mine = shares.get(want, 0.0)
            if mine >= WEAK_FILL:
                notes.append(f"{kind} {item['name']!r} {name!r}: fill {label} is "
                             f'{mine:.0%} of the artwork, behind {_hexa(top)} at '
                             f'{top_share:.0%}')
            else:
                problems.append(f"{kind} {item['name']!r} {name!r}: planned fill "
                                f'{label} is {mine:.0%} of the built artwork; '
                                f'it is mostly {_hexa(top)} ({top_share:.0%})')
        # A label planned clear (the spec writes no fill as alpha 0) is its
        # words alone: artwork mostly opaque is a donor label's fill that came
        # through - Turbulence 320's empty state built on black bands. So is a
        # panel, a line or a clock planned clear: the donor's first PBShape is
        # an opaque slab in most seeds.
        for op in item['controls']:
            if op.get('donor_type') not in CLEAR_TYPES or op.get('fill') is None \
                    or _painted(op['fill']):
                continue
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            tid = c.get('TLPImageID') if c else None
            if tid is None or tid < 0 or tid not in assets:
                continue
            checked += 1
            im = Image.open(io.BytesIO(assets[tid])).convert('RGBA')
            if op.get('border') and _painted(op.get('stroke')):
                # Its own outline can be most of a small control's artwork (a
                # 20 x 20 panel with a 5 px one is 75% opaque); a donor's slab
                # fills the middle, so read the central half.
                w, h = im.size
                im = im.crop((w // 4, h // 4, w - w // 4, h - h // 4))
            raw = im.tobytes()
            solid = sum(1 for i in range(3, len(raw), 4) if raw[i] > 250) / max(1, len(raw) // 4)
            if solid > 0.5:
                shares = _shares(assets, tid)
                top = max(shares.items(), key=lambda kv: kv[1])[0]
                problems.append(f"{kind} {item['name']!r} {name!r}: planned clear, but "
                                f'{solid:.0%} of its artwork is opaque, mostly {_hex(top)} - '
                                f"a donor {TYPE_NAME.get(c.get('Type'), 'control').lower()}'s fill")
    return problems, notes, checked


def check_level_bars(plan_items, table, assets, kind):
    """A level's filled part must be its planned color, off its full art.

    gaugeFillColorField: a clone kept its donor's, the Afterburn seeds'
    scheme-1 #626ACF, so the 525's volume built periwinkle under a gold
    scheme. Build draws the level full as TLPMaxValueImageID.
    """
    problems, checked = [], 0
    for item in plan_items:
        got = table.get(item['name'])
        if got is None:
            continue
        by_name = _index(got)
        for op in item['controls']:
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if op.get('keep_art') and c is not None:
                # Drawn from its donor's art, planned no color: its empty and
                # full art must both be built, and differ, or it shows no value.
                checked += 1
                lo, hi = c.get('TLPMinValueImageID'), c.get('TLPMaxValueImageID')
                where = f"{kind} {item['name']!r} {name!r}"
                if lo not in assets or hi not in assets:
                    problems.append(f'{where}: drawn from its seed\'s art, but Build drew no '
                                    f'{"empty" if lo not in assets else "full"} art '
                                    f'(TLPMinValueImageID {lo}, TLPMaxValueImageID {hi})')
                elif assets[lo] == assets[hi]:
                    problems.append(f'{where}: its empty and full art are the same image - it shows no value')
                continue
            if op.get('gauge_fill') is None or c is None:
                continue
            checked += 1
            tid = c.get('TLPMaxValueImageID')
            where = f"{kind} {item['name']!r} {name!r} bar"
            want, label = _rgb(op['gauge_fill']), _fill_hex(op['gauge_fill'])
            shares = _fill_shares(assets, tid, op['gauge_fill']) if tid in assets else None
            if not shares:
                problems.append(f'{where}: planned {label}, but Build drew no full art '
                                f'(TLPMaxValueImageID {tid})')
                continue
            top, top_share = max(shares.items(), key=lambda kv: kv[1])
            if top != want:
                problems.append(f'{where}: planned {label}, but the full art is mostly '
                                f'{_hexa(top)} ({top_share:.0%})')
    return problems, checked


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
            # An image control's art is check_images's, laid out as planned:
            # fitted here as an icon is, the Turbulence 1035's stretched header
            # - its seed's own art - read as 26% off.
            if op.get('donor_type') == 'PBImage':
                continue
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if c is None:
                continue
            where = f"{kind} {item['name']!r} {name!r}"
            built = c.get('States') or []
            if not want:
                # One image on every state - an icon that is not feedback. A
                # control with no states draws from itself.
                for i, bs in enumerate(built or [c]):
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
                                         assets, [w.get('image') for j, w in enumerate(want)
                                                  if j != i and w.get('image')])
                shares = _shares(assets, tid)
                dominant[i] = (tid, max(shares.items(), key=lambda kv: kv[1])[0]
                               if shares else None)
                # A deliberately transparent Off state is a real idiom -
                # Extron's own 'Lighting Preset' buttons are transparent when
                # off - so empty artwork is only wrong if a fill was planned.
                fill = ws.get('fill')
                if not _painted(fill):
                    continue
                # An image opaque over the box hides the fill under it: it is
                # the state's look, and _state_image holds it. Shockwave's
                # Teams tab lit is the kit's opaque _sel tile over white at 60.
                if _covers(ws.get('image'), c):
                    continue
                fills = _fill_shares(assets, tid, fill, ws.get('image'))
                if not fills:
                    problems.append(
                        f"{kind} {item['name']!r} {name!r} state "
                        f"{bs.get('Name') or i}: planned fill {_fill_hex(fill)}, but "
                        f'{_bare(assets, tid)}')
                    continue
                top, top_share = max(fills.items(), key=lambda kv: kv[1])
                target = _rgb(fill)
                if top == target:
                    continue
                mine = fills.get(target, 0.0)
                if mine >= WEAK_FILL:
                    notes.append(
                        f"{kind} {item['name']!r} {name!r} state "
                        f"{bs.get('Name') or i}: fill {_fill_hex(fill)} is {mine:.0%} of "
                        f'the artwork, behind {_hexa(top)} at {top_share:.0%}')
                else:
                    problems.append(
                        f"{kind} {item['name']!r} {name!r} state "
                        f"{bs.get('Name') or i}: planned fill {_fill_hex(fill)} is "
                        f'{mine:.0%} of the built artwork; it is mostly '
                        f'{_hexa(top)} ({top_share:.0%})')

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
            # Stroke and border are in the artwork too: two states apart only
            # in outline are still two states that must not share one image.
            if len({look(w) for w in want}) > 1 and len(dominant) > 1:
                ids = {v[0] for v in dominant.values()}
                colors = {v[1] for v in dominant.values()}
                if len(ids) == 1:
                    problems.append(
                        f"{kind} {item['name']!r} {name!r}: every state shares artwork "
                        f'{ids.pop()}, so Off and On are the same pixels - this button '
                        f'cannot show feedback')
                # By plurality color only where there are no kit images: two
                # speaker icons are both mostly their #414459 ground, and each
                # state's image is checked against its own artwork above. And
                # only where there is a color to compare: translucent states
                # (Mach's black at 70%, gray at 63%) have no opaque pixel, so
                # none of them has one; the artwork ids above still hold them
                # apart.
                elif fills_differ and not any(images) and len(colors) == 1 \
                        and None not in colors:
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
                problems += _gone(where, img)
                continue
            w, h = Image.open(io.BytesIO(assets[tid])).size
            off = image_mismatch(img['file'], assets[tid], w, h)
            if off > IMAGE_OFF:
                problems.append(f"{where}: {off:.0%} of it differs from the planned "
                                f"{img['name']!r} - it is not that image")
    return problems, checked


def check_rails(plan_items, table, assets, kind):
    """A slider's rail must be the kit art the plan gave it, where the
    template draws it from art: its track when empty, its fill when full.

    A clone keeps its donor's, and the applier cleared every clone's
    backgroundImageField - which on a slider IS the track - so Shockwave's
    slider built an opaque black block where its seed's own draw the rail,
    and no other check looked. Build draws the two as the empty and full
    assets, TLPMinValueImageID and TLPMaxValueImageID, the full one the fill
    over the track (rail_image): on the seeds' own sliders they are their
    track and fill files within 0%, the black block 100% and 66%.
    """
    problems, checked = [], 0
    for item in plan_items:
        got = table.get(item['name'])
        if got is None:
            continue
        by_name = _index(got)
        for op in item['controls']:
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if c is None:
                continue
            for key, part, asset in (('track_image', 'track', 'TLPMinValueImageID'),
                                     ('fill_image', 'fill', 'TLPMaxValueImageID')):
                img = op.get(key)
                if not img:
                    continue
                checked += 1
                where = f"{kind} {item['name']!r} {name!r} {part}"
                tid = c.get(asset)
                if tid is None or tid < 0 or tid not in assets:
                    problems.append(f'{where}: planned {img["name"]!r}, but Build drew no '
                                    f'{part} ({asset} {tid})')
                    continue
                if not img.get('file') or not os.path.exists(img['file']):
                    problems += _gone(where, img)
                    continue
                w, h = Image.open(io.BytesIO(assets[tid])).size
                vertical = c.get('Orientation') in (2, 3)   # up, down
                thumb = c.get('SliderIndicatorHeight' if vertical else 'SliderIndicatorWidth')
                # Full is the fill over the track.
                under = (op.get('track_image') or {}).get('file') if part == 'fill' else None
                under = under if under and os.path.exists(under) else None

                def draw(file, w, h, tw=c.get('SliderTrackWidth'), thumb=thumb, under=under):
                    return rail_image(file, w, h, tw, thumb, vertical, under)

                off = image_mismatch(img['file'], assets[tid], w, h, draw=draw)
                if off > IMAGE_OFF:
                    problems.append(f"{where}: {off:.0%} of it differs from the planned "
                                    f"{img['name']!r} - it is not that image")
    return problems, checked


def check_images(plan_items, table, assets, kind):
    """An image control's artwork must be the art the plan gave it, laid out
    as planned: stretched (1), as the Turbulence seeds' header and footer
    bars are, or fitted (0), as their device pictures are.

    layout.json names no image, and a clone's backgroundImageField - where a
    PBImage keeps its art - is cleared with every control's, so an image the
    applier never set builds as its fill alone and every field reads right.
    On the 1035 seed's own bars and device pictures, each against its file
    so laid out is 0% off, and against another's 10% and up
    (tests/test_verify_built.py) - the laptop and the PC are 10% apart, under
    the 25% a kit image on a button may be off, so an image is held to
    IMAGE_ART_OFF.
    """
    problems, checked = [], 0
    for item in plan_items:
        got = table.get(item['name'])
        if got is None:
            continue
        by_name = _index(got)
        for op in item['controls']:
            img = op.get('image')
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if op.get('donor_type') != 'PBImage' or not img or c is None:
                continue
            checked += 1
            where = f"{kind} {item['name']!r} {name!r}"
            tid = c.get('TLPImageID')
            if tid is None or tid < 0 or tid not in assets:
                problems.append(f'{where}: planned {img["name"]!r}, but it built with no artwork '
                                f'(TLPImageID {tid})')
                continue
            if not img.get('file') or not os.path.exists(img['file']):
                problems += _gone(where, img)
                continue
            draw = stretch_image if op.get('image_layout') == 1 else fit_image
            off = image_mismatch(img['file'], assets[tid], c['Width'], c['Height'], op.get('fill'), draw=draw)
            if off > IMAGE_ART_OFF:
                problems.append(f"{where}: {off:.0%} of its artwork differs from the planned "
                                f"{img['name']!r} {'stretched' if draw is stretch_image else 'fitted'} - "
                                f'it is not that image laid out so')
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
            # The face is also named by its resource, '<family> Regular Bold
            # Italic' on every PBFont read; a clone whose name was changed and
            # whose reference was not keeps the donor's resource.
            ref = (font.get('FontResourceReference') or {}).get('ResourceName')
            if want.get('name') and ref and ref != want['name'] + ' Regular Bold Italic':
                problems.append(f"{kind} {item['name']!r} {name!r}: planned font "
                                f"{want['name']!r}, built against resource {ref!r}")
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


def stretch_image(file, w, h):
    """`file` stretched to w x h."""
    return Image.open(file).convert('RGBA').resize((w, h), Image.Resampling.LANCZOS)


def rail_image(file, w, h, track, thumb, vertical, under=None):
    """`file` as Build draws a slider's rail into a w x h control: stretched
    into a box the track's width across and the slider's length less the thumb
    along, centered - inset half the thumb at each end, where the thumb's
    center stops - and cut to the control where the track is wider than it:
    the Shockwave 720's 47 px slider with a 52 px track built its rail 52 wide. The full
    asset is the fill drawn over the track (`under`). Measured on the seeds'
    own built sliders against their kit files: every Turbulence, Mach and
    Shockwave rail 0% off so; drawn alone, Shockwave's fill 6-9%, its track's
    rim showing round it. Drawn the whole length instead, Turbulence's 10 px
    stripes all land elsewhere and its own rails read 48-54%; fitted as a
    button's image is, a narrow bar is a few pixels off along its whole
    length. Only vertical sliders were measured; a horizontal one is assumed
    to mirror them."""
    across, along = (w, h) if vertical else (h, w)
    track = max(1, track or across)
    length = max(1, along - (thumb or 0))
    out = rail_image(under, w, h, track, thumb, vertical) if under else Image.new('RGBA', (w, h), (0, 0, 0, 0))
    im = stretch_image(file, *((track, length) if vertical else (length, track)))
    at = (across - track) // 2
    if at < 0:
        im = im.crop((-at, 0, -at + across, length) if vertical else (0, -at, length, -at + across))
        at = 0
    at = (at, (along - length) // 2)
    out.alpha_composite(im, at if vertical else at[::-1])
    return out


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
# (36%). Against another icon's file - the unselected variant, another
# accent's - 50% and up; but 40 of the 88 states whose button has a differing
# image - every speaker and mic volume level, mute against level 1 too - have a
# sibling under the gate, down to 6.9%: a level and the next differ by one thin
# wave at 64 px. So each state is also held against its button's other states'
# images, and nearer one of those than its own is a failure (_state_image).
IMAGE_PIXEL, IMAGE_OFF, IMAGE_INSET = 60, 0.25, 4
# The gate was measured on Afterburn's 64 px icons. Mach's 1376x440 tab art
# fitted into the 725's 152x60 tab comes out 21 to 25% off its own file -
# ShareLink's 25.1% - and 38% and up off every other icon of its folder. Past
# the gate and under IMAGE_FAMILY_OFF, a state is its planned image when that
# file is nearer the artwork than every other same-size file of its folder by
# IMAGE_FAMILY_MARGIN (_state_image).
IMAGE_FAMILY_OFF, IMAGE_FAMILY_MARGIN = 0.40, 0.10
# An image control has no border, ring or caption to be off by: every bar and
# device picture of the Turbulence 1035, 725 and 525 seeds is 0% off its own
# file laid out as the seed lays it, and the nearest other - the laptop's
# against the PC's - 10% (check_images).
IMAGE_ART_OFF = 0.05


def _max_channel(im):
    r, g, b = im.split()[:3]
    return ImageChops.lighter(ImageChops.lighter(r, g), b)


def image_mismatch(file, art_bytes, w, h, fill=None, draw=None):
    """Share of the inked pixels that differ between the built artwork and
    `file` drawn into w x h - fitted, unless `draw` says otherwise - over
    `fill` (an ARGB int, or None)."""
    base = (((fill >> 16) & 255, (fill >> 8) & 255, fill & 255, (fill >> 24) & 255)
            if fill is not None else (0, 0, 0, 0))
    want = Image.new('RGBA', (w, h), base)
    want.alpha_composite((draw or fit_image)(file, w, h))
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


def _gone(where, img):
    """A problem when the plan names a file this machine lacks.

    A plan carries its kit files' absolute paths, resolved where it was made.
    Verified anywhere else, or after vendor/ moved, every image comparison was
    skipped and the control still counted as verified - Mach's black-block
    rail passed so. A plan with no file at all is the seed's own image, with
    nothing to compare, and stays as it was."""
    f = img.get('file')
    if f and not os.path.exists(f):
        return [f"{where}: the planned {img['name']!r} is not at {f} on this machine, so "
                f'the built art cannot be compared with it - verify where the plan was '
                f'made, or re-plan here']
    return []


def _covers(image, c, share=0.9):
    """Whether `image`, fitted into the control's box as Build lays it, is
    opaque over `share` of the box inside its edge."""
    if not image or not image.get('file') or not os.path.exists(image['file'])             or not c.get('Width') or not c.get('Height'):
        return False
    w, h = c['Width'], c['Height']
    a = fit_image(image['file'], w, h).getchannel('A').crop(
        (IMAGE_INSET, IMAGE_INSET, max(IMAGE_INSET + 1, w - IMAGE_INSET), max(IMAGE_INSET + 1, h - IMAGE_INSET)))
    solid = sum(1 for v in a.getdata() if v > 250)
    return solid >= share * a.width * a.height


def _nearest_of_family(image, off, art, c, fill):
    """Whether the planned file is nearer the artwork than every other file of
    its folder sharing its size prefix (`1376x440_`) by IMAGE_FAMILY_MARGIN. A
    file with no such family has nothing to be told from: False."""
    folder, name = os.path.split(image['file'])
    prefix = name.split('_', 1)[0] + '_' if '_' in name else None
    if not prefix:
        return False
    rivals = [os.path.join(folder, f) for f in os.listdir(folder)
              if f != name and f.startswith(prefix) and f.lower().endswith('.png')]
    if not rivals:
        return False
    return all(image_mismatch(r, art, c['Width'], c['Height'], fill) - off >= IMAGE_FAMILY_MARGIN
               for r in rivals)


def _state_image(where, i, bs, c, image, fill, assets, others=()):
    """A state's artwork must be the kit image the plan gave it.

    The button's model names no image once built - layout.json carries only
    the artwork - so the artwork is compared with the image fitted over the
    planned fill (image_mismatch). `others` are the button's other states'
    images: two a step apart, a volume level and the next, differ by one thin
    wave - a few per cent of the inked pixels at 64 px, under IMAGE_OFF - so
    one built in the other's place passes alone, and is caught as nearer that
    state's image than its own."""
    if not image:
        return []
    tid = bs.get('TLPImageID')
    label = f"{where} state {bs.get('Name') or i!r}"
    if tid is None or tid < 0 or tid not in assets:
        return [f"{label}: planned image {image['name']!r}, but the state built with no "
                f'artwork (TLPImageID {tid})']
    if not image.get('file') or not os.path.exists(image['file']):
        return _gone(label, image)
    off = image_mismatch(image['file'], assets[tid], c['Width'], c['Height'], fill)
    if off > IMAGE_OFF and not (off <= IMAGE_FAMILY_OFF and
                                _nearest_of_family(image, off, assets[tid], c, fill)):
        return [f"{label}: {off:.0%} of the artwork differs from the planned image "
                f"{image['name']!r} - it is not that image"]
    # The NEAREST of them is the one there: levels 1 and 2 can both be nearer
    # than a planned level 3 that level 2 was built over.
    nearest = min(((image_mismatch(o['file'], assets[tid], c['Width'], c['Height'], fill), o['name'])
                   for o in others
                   if o and o.get('name') != image['name'] and o.get('file') != image['file']
                   and o.get('file') and os.path.exists(o['file'])), default=None)
    if nearest and nearest[0] < off:
        return [f"{label}: the artwork is nearer {nearest[1]!r} ({nearest[0]:.0%} differs) than "
                f"its planned {image['name']!r} ({off:.0%}) - another state's image "
                f'built in its place']
    return []


def _check_background_image(spec, pg, assets, kind='page'):
    """The page's artwork must be its planned image, fitted over its fill -
    or a popup's, which Shockwave's and Turbulence's hubs draw on the page's
    photo.

    layout.json does not name a page's background image, so the artwork is
    the only witness. With the image's file at hand, composite it the way the
    page draws it and compare; without one, at least the page must not have
    built as a flat fill.
    """
    img = spec['background_image']
    tid = pg.get('TLPImageID')
    where = f"{kind} {spec['name']!r} background image {img['name']!r}"
    if tid is None or tid < 0 or tid not in assets:
        return [f'{where}: the {kind} built with no artwork (TLPImageID {tid})']
    art = Image.open(io.BytesIO(assets[tid])).convert('RGB')
    if img.get('file') and os.path.exists(img['file']):
        fill = spec['background']
        want = Image.new('RGBA', art.size, _rgb(fill) + ((fill >> 24) & 0xFF,))
        # Laid out as the page lays it out: fitted (Fill), or stretched as
        # Mach's pages stretch their photo.
        drawn = (Image.open(img['file']).convert('RGBA').resize(art.size, Image.Resampling.LANCZOS)
                 if spec.get('background_layout') == 1 else fit_image(img['file'], *art.size))
        want = Image.alpha_composite(want, drawn).convert('RGB')
        hist = ImageChops.difference(art, want).convert('L').histogram()
        mean = sum(i * n for i, n in enumerate(hist)) / max(1, sum(hist))
        if mean > IMAGE_TOLERANCE:
            return [f'{where}: the {kind} artwork differs from the image over its fill by '
                    f'{mean:.0f} levels on average - it is not the planned image']
        return []
    shares = _shares(assets, tid)
    if shares and max(shares.values()) >= 0.99:
        return [f'{where}: the {kind} artwork is a single flat color, so the image did not '
                f'reach it']
    return []


def _no_artwork(kind, spec, tid):
    """A page or popup that built with no artwork shows nothing of its fill.
    Every built page and every referenced standard popup in the 47 corpus
    projects has artwork; the only ones without are GUI Designer's 35 Offline
    Pages and an unreferenced popup in two archived client projects - so this
    was a `continue`, and the check grew quieter as the build got worse."""
    return (f"{kind} {spec['name']!r} background: the {kind} built with no artwork "
            f'(TLPImageID {tid}), so its planned fill is not drawn')


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
        if tid is None or tid < 0 or tid not in assets:
            problems.append(_no_artwork('page', spec, tid))
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


def _check_scrim(spec, pu, assets):
    """A modal's artwork is black at its planned transparency, all over: so
    every template modal in the corpus builds, (0, 0, 0, 166) throughout."""
    tid = pu.get('TLPImageID')
    if tid is None or tid < 0 or tid not in assets:
        return [_no_artwork('popup', spec, tid)]
    alpha = round(255 * (100 - spec['transparency']) / 100)
    shares = _fill_shares(assets, tid, alpha << 24)
    top, top_share = max(shares.items(), key=lambda kv: kv[1]) if shares else (None, 0)
    if top == (0, 0, 0) and top_share >= 0.99:
        return []
    said = _hexa(top) if top else 'transparent'
    return [f"modal {spec['name']!r}: planned black at alpha {alpha} ({spec['transparency']:g}% "
            f'transparent), artwork is mostly {said} ({top_share:.0%}) - a modal is drawn at '
            f"its own transparency, and a clone keeps its donor modal's"]


def check_popup_background(plan_popups, popups, assets):
    """A popup's page fill reaches the panel as its artwork, as a page's does.

    A Group's popup planned with no fill (alpha 0) built as an opaque black
    box over its page on the 525: given none, the spec's popup took black, and
    no check read a popup's page asset. Planned transparent, the artwork must
    have no opaque pixel; planned a color, that color must cover it.

    A modal is not its fill: Build draws it black at the modal's own
    transparency, which a clone kept from its donor modal - 35%, alpha 166, in
    every template, and 0 on the client's archived Incoming modals, which build
    opaque and hide the page beneath. So a modal is held to the transparency
    its plan names, and one from a plan that names none is not checked.
    """
    problems = []
    for spec in plan_popups:
        pu = popups.get(spec['name'])
        if pu is None:
            continue
        if spec.get('modal'):
            if spec.get('transparency') is not None:
                problems += _check_scrim(spec, pu, assets)
            continue
        if spec.get('background') is None:
            continue
        if spec.get('background_image'):
            # On the page's photo, as Shockwave's and Turbulence's hubs draw
            # their popups: checked as a page's image is.
            problems += _check_background_image(spec, pu, assets, 'popup')
            continue
        tid = pu.get('TLPImageID')
        if tid is None or tid < 0 or tid not in assets:
            # Planned clear too: every referenced standard popup in the corpus
            # has artwork, transparent ones included.
            problems.append(_no_artwork('popup', spec, tid))
            continue
        shares = _shares(assets, tid)       # opaque pixels only
        where = f"popup {spec['name']!r} background"
        if not (spec['background'] >> 24) & 0xFF:
            if shares:
                top, top_share = max(shares.items(), key=lambda kv: kv[1])
                problems.append(f'{where}: planned transparent, but {top_share:.0%} of its '
                                f'opaque artwork is {_hex(top)} - it covers the page beneath')
            continue
        want = _rgb(spec['background'])
        alpha = (spec['background'] >> 24) & 0xFF
        if alpha <= 250:
            # A translucent fill (Turbulence's hub Volume Level strip, black
            # at 166) has no opaque pixel to count: read it at its own alpha.
            seen = _shares_at(assets, tid, alpha)
            top, top_share = max(seen.items(), key=lambda kv: kv[1]) if seen else (None, 0)
            if top != want or top_share < 0.99:
                problems.append(f'{where}: planned {_hex(want)} at alpha {alpha}, artwork is mostly '
                                f"{_hex(top) if top else 'something else'} at it ({top_share:.0%})")
            continue
        top, top_share = max(shares.items(), key=lambda kv: kv[1]) if shares else (None, 0)
        if top != want or top_share < 0.99:
            problems.append(f'{where}: planned {_hex(want)}, artwork is mostly '
                            f"{_hex(top) if top else 'transparent'} ({top_share:.0%})")
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
    if not alpha:
        return None, None               # a transparent fill: nothing to find
    argb = int(want.lstrip('#'), 16)
    label = _fill_hex(argb)
    if tid is None or tid < 0:
        return (f'{where}: fill {label} was asked for, but Build produced no '
                f'artwork (TLPImageID {tid})'), None
    shares = _fill_shares(assets, tid, argb)
    if not shares:
        return f'{where}: fill {label} was asked for, but {_bare(assets, tid)}', None
    top, top_share = max(shares.items(), key=lambda kv: kv[1])
    if top == rgb:
        return None, None
    mine = shares.get(rgb, 0.0)
    if mine >= WEAK_FILL:
        return None, (f'{where}: fill {label} is {mine:.0%} of the artwork, '
                      f'behind {_hexa(top)} at {top_share:.0%}')
    return (f'{where}: fill {label} is {mine:.0%} of the built artwork; it is '
            f'mostly {_hexa(top)} ({top_share:.0%})'), None


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
    probs, n = check_retarget(plan, j)
    return problems + probs, checked + n


def check_retarget(plan, j):
    """(problems, checked): an edit plan's `project` and `pages` ops.

    A retarget sets the panel's model and screen, and each page's and popup's
    own canvas - none of it a control, so a walk of plan['controls'] never
    looked, and a retarget without `scale`, which plans no control at all,
    verified with 0 checks against a file that was never retargeted.

    The model is read as its part number, which is how GUI Designer names the
    panel (a TLP 1035T and 1035M share one), and the way up as the platform's
    own resolution beside the screen size (docs/gdl-format.md section 7).
    """
    from gdl.spec import part_number
    problems, checked = [], 0
    scr = j.get('ScreenSize') or {}
    plat = j.get('Platform') or {}
    for op in plan.get('project') or []:
        if not op.get('model'):
            continue
        checked += 1
        w, h = op['size']
        got = (scr.get('width'), scr.get('height'))
        if got != (w, h):
            problems.append(f'the screen is {got[0]}x{got[1]}, the retarget asked for {w}x{h}')
        res = (plat.get('HorizontalResolution'), plat.get('VerticalResolution'))
        if res != (w, h):
            problems.append(f"the platform's resolution is {res[0]}x{res[1]}, the retarget "
                            f'asked for {w}x{h}')
        want = part_number(op['model'])
        for where, part in (('panel', j.get('PartNumber')), ('platform', plat.get('PartNumber'))):
            if want and part != want:
                problems.append(f"the {where}'s part number is {part!r}, and a {op['model']} "
                                f'is {want!r} - the build is not the model the retarget names')
    pages = {p['ID']: p for p in (j.get('Pages') or []) + (j.get('PopupPages') or [])}
    for op in plan.get('pages') or []:
        pg = pages.get(op['page'])
        if pg is None:
            problems.append(f"{op.get('kind', 'page')} {op.get('name')!r} (id {op['page']}) "
                            f'is not in the built file')
            continue
        checked += 1
        got = (pg.get('Width'), pg.get('Height'))
        if list(got) != list(op['size']):
            problems.append(f"{op.get('kind', 'page')} {pg.get('Name')!r} is {got[0]}x{got[1]}, "
                            f"the retarget asked for {op['size'][0]}x{op['size'][1]}")
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


def check_only_planned(plan, j):
    """Is the panel its plan's pages and popups, and nothing else?

    The applier clones from the donor and used to leave the donor's own pages
    and popups in place, unreachable from the start page and some of their
    controls on IDs the spec's own carry (docs/from-scratch.md section 5c).
    GUI Designer's Offline Page is its own and stays. A plan that keeps the
    donor on purpose (`keep_donor_pages`) is not held to this.
    """
    if plan.get('keep_donor_pages'):
        return []
    offline = j.get('OfflinePageID', 65535)
    out = []
    want = {p['name'] for p in plan.get('pages') or []}
    for p in j.get('Pages') or []:
        if p['Name'] not in want:
            out.append(f"page {p['Name']!r} is in the built file and not in the plan - "
                       f"the donor's, left in")
    want = {p['name'] for p in plan.get('popups') or []}
    for p in j.get('PopupPages') or []:
        if p['Name'] not in want and p.get('ID') != offline:
            out.append(f"popup {p['Name']!r} is in the built file and not in the plan - "
                       f"the donor's, left in")
    return out


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


def _check_id(where, f, c):
    """The ID a program addresses the control by. A clone keeps its donor's
    when the write does not take, and two controls then answer to one ID;
    verify_idmap reads them back only where there is a map (New-GdlPanel
    -IdMap). Build keeps each control's userIdField as layout.json's UserId -
    Borders320's three, 1001 to 1003 as planned."""
    want = f.get('userIdField')
    if want is None or 'UserId' not in c or c['UserId'] == want:
        return []
    return [f"{where}: ID {c['UserId']}, planned {want} - the donor's, if a clone kept it"]


def _check_text_color(where, op, c):
    """A caption's color, for a control whose plan names no states - a label,
    a clock, a button with no feedback. It is drawn live, so it is the model's
    TextColor, as a planned state's is (check_states). The applier writes the
    one color to the control and to every state a clone has, and the panel
    draws a button's caption from its state."""
    want = op.get('text_color')
    f = op.get('fields') or {}
    if want is None or op.get('states') or not (f.get('textField') or f.get('patternField')):
        return []
    out = []
    # One wrong color on the control and on its states is one fault: the
    # applier writes the same color to both, so say it once.
    for label, tc in [('', c.get('TextColor'))] + [
            (f" state {s.get('Name') or i!r}", s.get('TextColor'))
            for i, s in enumerate(c.get('States') or [])]:
        if not isinstance(tc, dict):
            continue
        have = (tc.get('R'), tc.get('G'), tc.get('B'))
        if have != _rgb(want):
            out.append(f'{where}{label}: text color {_hex(have)}, planned {_hex(_rgb(want))}'
                       f" - a clone keeps its donor's")
            if not label:
                break
    return out


_ORIENT_NAME = {v: k for k, v in __import__('gdl.spec', fromlist=['ORIENT']).ORIENT.items()}


def _check_slider(where, f, c):
    """A slider's or level's orientation, and a slider's track width and thumb
    size. A clone keeps its donor's - every seed's slider stands up - and
    check_rails draws the art it expects from the built values, so a donor's
    passes there as itself. layout.json carries the authoring fields under its
    own names: orientationField as Orientation, sliderTrackWidth as
    SliderTrackWidth, sliderThumbWidth and sliderThumbHeight as
    SliderIndicatorWidth and SliderIndicatorHeight, literal whichever way the
    slider lies - on every slider and level of the Afterburn 1035 and 525,
    Shockwave 725 and 320, and Zoom Rooms seeds."""
    out = []
    want = f.get('orientationField')
    if want is not None and c.get('Orientation') is not None and c['Orientation'] != want:
        out.append(f"{where}: orientation {_ORIENT_NAME.get(c['Orientation'], c['Orientation'])!r}, "
                   f'planned {_ORIENT_NAME.get(want, want)!r}')
    want = f.get('sliderTrackWidth')
    if want is not None and c.get('SliderTrackWidth') is not None and c['SliderTrackWidth'] != want:
        out.append(f"{where}: track {c['SliderTrackWidth']} wide, planned {want}")
    want = (f.get('sliderThumbWidth'), f.get('sliderThumbHeight'))
    have = (c.get('SliderIndicatorWidth'), c.get('SliderIndicatorHeight'))
    if any(w is not None and h is not None and w != h for w, h in zip(want, have)):
        out.append(f'{where}: thumb {have[0]}x{have[1]}, planned {want[0]}x{want[1]}')
    return out


def check_placed(plan, pages, popups):
    """Each authored control is in the built file, where it was put, and
    captioned - or, for a clock, patterned - as planned, on its planned ID, in
    its planned text color, and a slider lying and sized as planned."""
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
                # The applier writes the alignment, and a clone keeps its
                # donor's: a left-aligned label built centred reads off by half
                # its width, and nothing else here would notice.
                want_align, got_align = op.get('alignment'), c.get('TextAlignment')
                if want_align is not None and got_align is not None and got_align != want_align:
                    said = repr(_ALIGN_NAME.get(got_align, got_align))
                    if got_align == ALIGN_MIXED:
                        said = 'differs by state: ' + ', '.join(
                            f"{s.get('Name')!r} {_ALIGN_NAME.get(s.get('TextAlignment'), s.get('TextAlignment'))!r}"
                            for s in c.get('States') or [])
                    problems.append(f"{kind} {item['name']!r} {name!r}: text alignment "
                                    f'{said}, planned {_ALIGN_NAME.get(want_align, want_align)!r}')
                # A hidden press or state feedback builds a button that
                # never shows what the plan drew for it, and a clone brings
                # its donor's flags.
                for key in ('HidePressFeedback', 'HideVisualFeedback', 'HideTextFeedback'):
                    want_flag = f.get(f'<{key}>k__BackingField')
                    if want_flag is not None and c.get(key) != want_flag:
                        problems.append(f"{kind} {item['name']!r} {name!r}: {key} is "
                                        f"{c.get(key)}, planned {want_flag}")
                # A clock's caption is only a sample; what it shows on the
                # panel is its pattern.
                want_pattern = f.get('patternField')
                if want_pattern is not None and c.get('Pattern') != want_pattern:
                    problems.append(f"{kind} {item['name']!r} {name!r}: clock pattern "
                                    f"{c.get('Pattern')!r}, planned {want_pattern!r}")
                problems += _check_id(f"{kind} {item['name']!r} {name!r}", f, c)
                problems += _check_text_color(f"{kind} {item['name']!r} {name!r}", op, c)
                problems += _check_slider(f"{kind} {item['name']!r} {name!r}", f, c)
            # A generated page or popup is a donor's, cloned and cleared: a
            # control of the donor's left on it ships unasked. Build's own are
            # one full-canvas popup reference per modal popup, on every page.
            planned = {op['fields'].get('nameField') for op in item['controls']}
            canvas = (0, 0, got.get('Width'), got.get('Height'))
            for c in got.get('Controls') or []:
                if c.get('Name') in planned:
                    continue
                if c.get('Type') == 6 and (c.get('Left'), c.get('Top'), c.get('Width'),
                                           c.get('Height')) == canvas:
                    continue
                problems.append(f"{kind} {item['name']!r}: {c.get('Name')!r} "
                                f"({TYPE_NAME.get(c.get('Type'), c.get('Type'))}) is on it and "
                                f"not in the plan - the donor's, left in")
    return problems, checked


def _built_project(built_path, _cache={}):
    """The built file's authoring model, read once per run: the border names
    and the popup group registry are there and not in layout.json."""
    if built_path not in _cache:
        from gdl.project import Project
        _cache.clear()
        _cache[built_path] = Project.open(built_path)
    return _cache[built_path]


def popup_group_registry(built_path):
    """{group id: name}: the built project's popup group registry
    (PBProject.popupPageGroupsField). layout.json does not carry it, and a
    group id that is not in it reads 'Unassigned' (docs/gdl-format.md section
    6)."""
    p = _built_project(built_path)
    proj = next(p.instances('PBProject'), None)
    if proj is None:
        return {}
    return {p.field(g, 'idField'): p.field(g, 'nameField')
            for g in p.items(p.field(proj, 'popupPageGroupsField'))}


def check_popup_groups(plan, j, registry):
    """Is each planned popup reference bound to the group the plan names, and
    is every group a reference names one some popup is in?

    The built file records a binding on the reference (PopupPageID.GroupID
    with IsPopupGroupIdValid), on each popup (GroupID), and in the project's
    group registry (`registry`, popup_group_registry), which alone names the
    group. This read a `PopupGroups` key instead, which no layout.json in the
    corpus has, so it never fired. A reference bound to one popup by its
    PopupID, at GroupID 0 - Extron's 525s show Volume Level so - names no group
    and is not held to one.
    """
    out = []
    popups = {p['Name']: p for p in j.get('PopupPages') or []}
    pages = {p['Name']: p for p in j.get('Pages') or []}
    # The id each planned group built as, read off its popups.
    ids = {}
    for pu in plan.get('popups') or []:
        got = popups.get(pu['name'])
        if not pu.get('group') or pu.get('modal') or got is None:
            continue                     # check_placed reports a popup that is not there
        gid = got.get('GroupID') if got.get('IsGroupValid', True) else 0
        ids.setdefault(pu['group'], {}).setdefault(gid, []).append(pu['name'])
    built = {}
    for g, by_id in sorted(ids.items()):
        if len(by_id) > 1:
            out.append(f'popup group {g!r} built as {len(by_id)} groups: ' + '; '.join(
                f"{', '.join(map(repr, names))} in {f'group {i}' if i else 'no group'}"
                for i, names in sorted(by_id.items())))
            continue
        (gid, names), = by_id.items()
        if not gid:
            out.append(f"popup group {g!r}: {', '.join(map(repr, names))} built in no group, so "
                       f'no reference bound to {g!r} can show it')
            continue
        built[g] = gid
        if gid not in registry:
            out.append(f"popup group {g!r} built as group {gid}, which is not in the project's "
                       f"group registry - its references read 'Unassigned'")
        elif registry[gid] != g:
            out.append(f'popup group {g!r} built as group {gid}, which the registry names '
                       f'{registry[gid]!r}')
    planned = set()                      # said below, so not again with the rest
    for item in plan.get('pages') or []:
        got = pages.get(item['name'])
        if got is None:
            continue
        by_name = _index(got)
        for op in item.get('controls') or []:
            if op.get('donor_type') != 'PBPopupPageReference' or not op.get('group'):
                continue
            name = (op.get('fields') or {}).get('nameField')
            c = by_name.get(name)
            if c is None:
                continue                 # check_placed reports it
            planned.add((item['name'], name))
            pp = c.get('PopupPageID') or {}
            where = f"page {item['name']!r} {name!r}"
            if not pp.get('IsPopupGroupIdValid'):
                out.append(f"{where}: bound to no popup group - it reads 'Unassigned'; the plan "
                           f"binds it to {op['group']!r}")
            elif op['group'] in built and pp.get('GroupID') != built[op['group']]:
                out.append(f"{where}: bound to group {pp.get('GroupID')}, and {op['group']!r} "
                           f"is group {built[op['group']]}")
    # Any reference - on a donor's kept page too - that can show nothing: bound
    # to a group no popup is in, to a popup that is not there, or to neither.
    # Each of the corpus's 3745 built references is bound to a group (161) or
    # to a popup (3584) that is there.
    have = {p.get('GroupID') for p in popups.values() if p.get('GroupID')}
    ids = {p.get('ID') for p in popups.values()}
    for pg in pages.values():
        for c in pg.get('Controls') or []:
            pp = c.get('PopupPageID')
            if not isinstance(pp, dict):
                continue
            where = f"page {pg['Name']!r} {c.get('Name')!r}"
            if pp.get('IsPopupGroupIdValid'):
                if pp.get('GroupID') not in have:
                    out.append(f"{where}: bound to popup group {pp.get('GroupID')}, which no "
                               f'popup is in - it shows nothing')
            elif pp.get('IsPopupPageIdValid'):
                if pp.get('PopupID') not in ids:
                    out.append(f"{where}: bound to popup {pp.get('PopupID')}, which is not in "
                               f'the built file - it shows nothing')
            elif (pg['Name'], c.get('Name')) not in planned:
                out.append(f"{where}: bound to no popup and no group - it reads 'Unassigned'")
    return out


def check_borders(plan, built_path):
    """(problems, checked): every planned control's and state's border is the
    resource the plan names. layout.json keeps no border's name - Build
    rasterizes it - so the built project is read. A plan made without its donor
    (`gdl.spec plan` with no --donor) names a border the donor lacks; the
    applier then leaves the clone's own and only warns, and the artwork shows a
    border either way."""
    want = {}
    for kind, items in (('page', plan.get('pages') or []), ('popup', plan.get('popups') or [])):
        for item in items:
            for op in item.get('controls') or []:
                sts = [s.get('border') for s in op.get('states') or []]
                if op.get('border') or any(sts):
                    name = (op.get('fields') or {}).get('nameField')
                    want[(kind, item['name'], name)] = (op.get('border'), op.get('states') or [])
    if not want:
        return [], 0
    got = {}
    for pg in _built_project(built_path).pages():
        for c in pg['controls']:
            got.setdefault((pg['kind'], pg['name'], c['name']), c)
    problems, checked = [], 0
    for (kind, item, name), (border, states) in want.items():
        c = got.get((kind, item, name))
        if c is None:
            continue            # check_placed reports a planned control that is not there
        where = f'{kind} {item!r} {name!r}'
        if border:
            checked += 1
            have = (c.get('border') or {}).get('resource')
            if have != border:
                problems.append(f'{where}: border {have!r}, planned {border!r}')
        for i, st in enumerate(states):
            if not st.get('border'):
                continue
            checked += 1
            built = c['states'][i] if i < len(c.get('states') or []) else {}
            have = (built.get('border') or {}).get('resource')
            if have != st['border']:
                problems.append(f"{where} state {st.get('name') or i!r}: border {have!r}, "
                                f"planned {st['border']!r}")
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
    grouped = any(pu.get('group') for pu in plan.get('popups') or [])
    problems += check_popup_groups(plan, j, popup_group_registry(built_path) if grouped else {})

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
        probs, n = check_rails(spec, table, assets, kind)
        problems += probs
        checked += n
        probs, n = check_level_bars(spec, table, assets, kind)
        problems += probs
        checked += n
        probs, n = check_images(spec, table, assets, kind)
        problems += probs
        checked += n
        for note in notes:
            print(f'  STATE FILL NOT DOMINANT (survived, but check it by eye): {note}')
    probs, n = check_borders(plan, built_path)
    problems += probs
    checked += n
    problems += check_page_background(plan['pages'], pages, assets)
    problems += check_popup_background(plan.get('popups') or [], popups, assets)
    problems += check_start_page(plan, j)
    problems += check_only_planned(plan, j)
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
    # Checks, not controls: each control is checked several ways - place,
    # fill, font, each state, its border - and the tally was read as a count
    # of controls in three PRs' evidence.
    with open(argv[1], encoding='utf-8') as fh:
        plan = json.load(fh)
    n = (len(plan.get('controls') or []) if plan.get('generated_by') == 'gdl.edit' else
         sum(len(item.get('controls') or [])
             for item in (plan.get('pages') or []) + (plan.get('popups') or [])))
    print(f'{checked} check(s) on {n} authored control(s) against the build, '
          f'{len(problems)} problem(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
