"""Composite a .gdl page exactly the way the HTML viewer does, then diff the
result against GUI Designer's own snapshot render.

The point is not to ship this image - it is to prove the render RULES
(geometry, z-order, state choice, alignment enum, point-size factor, line
metrics) against ground truth the application produced itself.
"""
import contextlib
import io
import json
import math
import os
import re
import struct
import sys
import zipfile

from PIL import Image, ImageChops, ImageDraw, ImageFont

from . import sfnt
from .container import open_gdl
from .data import popup_ref  # noqa: E402

PT = 1.375           # 99 DPI, per the glyph-outline measurements

# family + bold/italic -> the file it is recovered as, and the other names a
# face is embedded under, and where. One table, in gdl/fonts.py: a spec reads
# its icons' glyph names from the same files without Pillow. FONTDIR is bound
# here too, so a test can point the renderer elsewhere.
from .fonts import ALIASES, FILES, FONTDIR, face_path, seed_face  # noqa: E402
# Fallback only. Arial and Arial Black ARE embedded in the .gdl - every fixture
# and every Extron template carries Monotype Arial 5.10 and Arial Black 5.06 -
# so `python -m gdl.fonts` puts them in FONTDIR and this list is never reached.
# It stays for a checkout whose fonts have not been extracted yet, and it is a
# worse answer than extraction: the system Arial is whatever build the host
# happens to ship, not the one GUI Designer rasterized the snapshots with.
SYSFONTS = (
    'C:/Windows/Fonts',
    '/System/Library/Fonts/Supplemental', '/System/Library/Fonts', '/Library/Fonts',
    os.path.expanduser('~/Library/Fonts'),
    '/usr/share/fonts', '/usr/local/share/fonts', os.path.expanduser('~/.fonts'),
)
WINFONTS = SYSFONTS[0]          # kept: referenced by name elsewhere
_cache = {}
_sysindex = None
# Every face drawn in a stand-in - neither its own recovered file nor a seed's
# (gdl.fonts.seed_face) - for a caller to say so: on a checkout that never ran
# `python -m gdl.fonts`, every face falls back
# to the host's Arial and the render baseline scores 2.81% for 2.19% - silently,
# since a fallback is not an error - and after a partial recovery each missing
# face draws in the recovered Arial instead. tests/score.py refuses to record
# over one.
FALLBACKS = set()
# Every face read out of a seed because no file of it is recovered here
# (gdl.fonts.seed_face), as '<face> from <seed>'. Right for a preview, which
# has nothing better; wrong for the render baseline, which is scored in the
# faces the synthetic fixture embeds - a seed's Arial Black can be Windows', not
# its Monotype 5.06 - and would then score by which seeds are pulled.
# tests/score.py refuses to record over one, as over a stand-in.
FROM_SEED = set()


def _system_fonts():
    """lowercased filename -> full path, for every system font dir that exists.

    Indexed case-insensitively because the same face is `arial.ttf` on Windows
    and `Arial.ttf` on macOS, and an exact-name lookup silently misses it.
    """
    global _sysindex
    if _sysindex is None:
        _sysindex = {}
        for base in SYSFONTS:
            if not os.path.isdir(base):
                continue
            for root, _, names in os.walk(base):
                for n in names:
                    _sysindex.setdefault(n.lower(), os.path.join(root, n))
    return _sysindex


# The faces the built file being drawn carries (gdl.fonts.carried), or None.
# Set only by as_the_panel(): the render baseline is scored in the Monotype
# faces the synthetic fixture embeds, and drawing a Mach seed's Windows Arial
# there would move it.
_carried = None
_carried_tag = None
_PROJECT_FACES = {}


def project_faces(path):
    """gdl.fonts.carried(path), read once per file (and per edit of it)."""
    from .fonts import carried
    key = _project_key(path)
    if key not in _PROJECT_FACES:
        # Only the latest edit of a path: an earlier one's bytes are never read
        # again, and a long session rebuilds the same file many times.
        for old in [k for k in _PROJECT_FACES if k[0] == key[0]]:
            del _PROJECT_FACES[old]
        _PROJECT_FACES[key] = carried(path)
    return _PROJECT_FACES[key]


def _project_key(path):
    """(abspath, mtime): the one identity of a built file, for both the read of
    its faces and the faces drawn from them - a file rebuilt in place is new."""
    return os.path.abspath(path), os.path.getmtime(path)


def _carried_face(name, bold, italic):
    """The bytes of the project's own `name` face in this style, or None.
    The Regular stands in for a style the project does not carry, as FILES'
    (name, 0, 0) does for a recovered one."""
    mine = [f for f in _carried or () if f['family'] == name and f['bytes']]
    def style(f):
        s = (f['style'] or '').lower()
        return int('bold' in s), int('italic' in s or 'oblique' in s)
    for wanted in ((int(bool(bold)), int(bool(italic))), (0, 0)):
        for f in mine:
            if style(f) == wanted:
                return f['bytes']
    return None


@contextlib.contextmanager
def as_the_panel(project=None):
    """Draw as the panel shows, not as GUI Designer's snapshot export does.

    Two rules differ, and a sheet a client signs wants the panel's: a
    translucent control blends as Pillow blends, not in light as the snapshot
    does, and the page goes on black by its alpha (BINARY off), and a face
    is the one the built file `project` embeds, not the build recovered into
    gdl/fonts/ (Afterburn's 320/525/725/300M seeds embed a different
    afterburn.ttf from the others; Mach, Shockwave and Turbulence embed Windows
    Arial, not the Monotype the synthetic fixture does). A face the file does not carry
    falls back as it always has. The scoring path (tests/score.py) never enters
    this and keeps the snapshot rule. Both settings go back as found. Nested, an
    inner call with no `project` keeps the outer one's faces (only BINARY is
    set again); one with its own replaces them until it exits."""
    global BINARY, _carried, _carried_tag
    was = BINARY, _carried, _carried_tag
    BINARY = False
    if project is not None:
        _carried = project_faces(project)
        _carried_tag = _project_key(project)
    try:
        yield
    finally:
        BINARY, _carried, _carried_tag = was


def face(name, bold, italic, px):
    """The Pillow font a caption in `name` is drawn in, `oblique` set where
    an italic is asked of a file that is not one, and `emboldened` where a
    bold is: GUI Designer obliques the regular (draw_text, OBLIQUE) and
    emboldens it (embolden, BOLD_ADVANCE_EM) there, as no seed carries an Open
    Sans Italic or Bold."""
    key = (name, bold, italic, round(px, 2), _carried_tag)
    if key in _cache:
        return _cache[key]
    f, f_stand_in = _open_face(name, bold, italic, px)
    _cache[key] = f
    # The stand-in it is drawn in (FALLBACKS' words), or None: a caption
    # measured in one says nothing of how the panel's face lays it out, and
    # caption_fit's callers pass over it, saying so.
    f.stand_in = f_stand_in
    style = (f.getname()[1] or '').lower()
    f.oblique = bool(italic) and 'italic' not in style and 'oblique' not in style
    f.emboldened = bool(bold) and 'bold' not in style
    return f


def _open_face(name, bold, italic, px):
    """(the Pillow font, the stand-in's words in FALLBACKS or None)."""
    if _carried:
        data = _carried_face(name, bold, italic)
        if data:
            return ImageFont.truetype(io.BytesIO(data), size=px), None
    primary = FILES.get((name, bold, italic)) or FILES.get((name, 0, 0))
    own = [c for c in [primary] + ALIASES.get(primary or '', []) if c]
    candidates = own + [c for c in ['arial.ttf'] if c not in own]
    for fn in own:
        p = os.path.join(FONTDIR, fn)
        if os.path.exists(p):
            return ImageFont.truetype(p, size=px), None
    if not face_path(name, fontdir=FONTDIR):
        # Before anything stands in: a face no recovery put here, read
        # straight out of a seed that carries it - an icon face out of its
        # family's, Roboto out of a Shockwave seed. Recovering a Mach or
        # Shockwave seed would replace the Monotype Arial here with theirs.
        # Only when no file of the family is here: Arial's bold has none
        # anywhere, and parsing a seed for the Arial already here is seconds.
        data, seed = seed_face(name)
        if data:
            FROM_SEED.add(f'{name} from {seed}')
            return ImageFont.truetype(io.BytesIO(data), size=px), None
    if 'arial.ttf' not in own and os.path.exists(os.path.join(FONTDIR, 'arial.ttf')):
        why = f'{name} as arial.ttf'
        FALLBACKS.add(why)
        return ImageFont.truetype(os.path.join(FONTDIR, 'arial.ttf'), size=px), why
    index = _system_fonts()
    for fn in candidates:
        p = index.get(fn.lower())
        if p:
            why = f"{name} as the host's {fn}"
            FALLBACKS.add(why)
            return ImageFont.truetype(p, size=px), why
    raise LookupError(
        f'no font file for {name!r} (bold={bold} italic={italic}). A built project '
        f'embeds the faces it declares, Arial included - run '
        f'`python -m gdl.fonts <file.gdl> gdl/fonts/` over the project, or over '
        f'tests/data/synthetic/synthetic.gdl for the faces the render baseline is '
        f'scored in. Failing that, {SYSFONTS} is searched.')


def metrics(f):
    """(ascent, descent) from the OS/2 winAscent/winDescent GDI actually uses.

    Read from the font rather than via Pillow: getmetrics() rounds both to
    whole pixels, which costs a pixel of line box per line and pushes a
    vertically centerd block off by half of it. See gdl/sfnt.py.
    """
    a = advances(f)
    if a is not None:
        return a.vmetrics(f.size)
    return f.getmetrics()


# GDI+ lays a caption out down its box at 96 DPI where it lays it out across
# at 99 (PT): the ascent that sets a block's first baseline below its top, and
# the pitch from one line to the next, are the face's usWinAscent and
# usWinAscent + usWinDescent at 4/3 px a point. On the synthetic fixture a
# top-aligned caption's lines, one to six of them, land within 0.8 px of it,
# where at PT a sixth line falls 6.6 px low; 96/99 is a clean minimum of the
# score (0.965 and 0.975 both worse); and docs/gdl-format.md section 2's cap
# heights, 13 to 34 px at 14 to 36 pt, are the face's at 4/3. The glyphs are
# drawn at 4/3 too (drawn()), both ways, and set along the line at PT's
# advances: a 20 pt Open Sans Light 'y' goes 6 rows below its baseline in GUI
# Designer's snapshot, where drawn at PT it goes 7, and drawn so the synthetic
# fixture scores 1.27% for 1.55%, every page better (docs/render-fidelity.md
# finding 7).
VERTICAL = (4 / 3) / PT
# And a centred or bottom-aligned block is aligned in its box less this many
# px a point at its foot, where a top-aligned one is not. Measured, not
# explained: 0.148 of the vertical em over the fixture's 454 centred Open Sans
# lines, for one line to four alike, 0.15 over its bottom-aligned ones and
# 0.15 to 0.16 in Arial, Arial Black and Open Sans Light. 0.2 px a point is
# 0.15 of it; the score is flat from 0.135 to 0.15 and worse past 0.155 -
# 0.18 to 0.2 px a point, so FOOT, the line-by-line measurement, is the
# plateau's upper edge, not its middle (0.19 scores 1.54% against 1.55%).
FOOT = 0.2


def layout_metrics(f):
    """(ascent, descent) as GDI+ lays a caption's lines out: metrics() at
    VERTICAL of the em the glyphs are drawn at."""
    asc, desc = metrics(f)
    return asc * VERTICAL, desc * VERTICAL


# Lay text out with the font's own fractional advances instead of Pillow's
# grid-fitted integer ones, and place each glyph at its own fractional x.
# See docs/render-fidelity.md finding 7 for what each is worth.
FRAC_MEASURE = True
FRAC_PLACE = True
# Horizontal registration: Pillow's rasterizer and GDI+ disagree by the usual
# half pixel (sample at the pixel corner vs at its center). The value is a
# convention, not a fit - and it is a clean minimum on the shipped model, which
# is confirmation rather than derivation. research/compose2.py also uses -0.5,
# but on the same corpus and with its own metric preferring roughly -0.75, so
# treat that as agreement about the convention, not independent evidence.
DX = -0.5
# GDI+ lays a caption out in its box less StringFormat's default padding, a
# sixth of the font's em on the left and on the right (none above or below):
# a left- or right-aligned line starts that far in from the box's edge, and
# every line wraps in the box less both. The synthetic fixture shows it - 3 px
# at 14 pt, 9 px at 40 pt on its Type Sizes page - where the client project the
# first baseline was scored on centred all but 3 of its 490 captions, so never
# did (docs/render-fidelity.md section 9).
PAD_EM = 1 / 6
# GDI+'s simulated bold: a face with no bold file of its own (no seed carries
# an Open Sans Bold) drawn as the regular, each glyph's ink smeared this many
# whole pixels to the right - GDI's overstrike - and each advance this much of
# the em longer. Fitted on the client project's 44 bold Forma captions and
# confirmed on the synthetic fixture's 50 bold Open Sans ones: a symmetric, a
# vertical or a fractional smear (1.1 px already) all score worse, and so does
# every growth in whole pixels (0.3 to 1 px); 0.016 to 0.0175 em score alike,
# 0.015 and 0.02 worse (docs/render-fidelity.md section 8).
BOLD_SMEAR = 1
BOLD_ADVANCE_EM = 1 / 60
_adv = {}


def bold_advance(fnt):
    """How much further than the regular's each glyph's advance takes the
    pen in `fnt`: BOLD_ADVANCE_EM of its em where face() emboldens it, else
    nothing."""
    return BOLD_ADVANCE_EM * fnt.size if getattr(fnt, 'emboldened', False) else 0.0


def advances(fnt):
    """The sfnt advance table for a Pillow font, or None if it will not parse."""
    path = getattr(fnt, 'path', None)
    if path not in _adv:
        try:
            # A face read out of a seed (face()) is opened from memory.
            _adv[path] = sfnt.Advances(path.getvalue() if isinstance(path, io.BytesIO) else path)
        except Exception:
            # A face we cannot parse falls back to Pillow's own measurement
            # rather than failing the render.
            _adv[path] = None
    return _adv[path]


def measure(s, fnt, draw=None):
    """Text width in pixels, fractional where the font lets us read it, each
    glyph's advance grown where the face is emboldened (bold_advance)."""
    grown = bold_advance(fnt) * len(s)
    if FRAC_MEASURE:
        a = advances(fnt)
        if a is not None:
            return a.length(s, fnt.size) + grown
    return (draw or ImageDraw.Draw(Image.new('RGBA', (1, 1)))).textlength(s, font=fnt) + grown


_drawn = {}  # (font path, size, index) -> the Pillow font drawn() returns


def drawn(fnt):
    """The Pillow font `fnt`'s glyphs are drawn in: the face at VERTICAL of
    its em, the em GDI+ sets the lines down the box at - 4/3 px a point, where
    `fnt` is at PT - so a glyph is as tall as GUI Designer's and FreeType
    grid-fits it at the size GDI+ does (20 pt: 26.67 px, hinted at 27, a 'y'
    six rows deep). Its advances stay `fnt`'s (draw_glyphs)."""
    # Keyed by what makes the face, not id(fnt): a key of id() kept `fnt`
    # alive for good, and an id is reused once its font is collected.
    key = (getattr(fnt, 'path', None), fnt.size, getattr(fnt, 'index', 0))
    got = _drawn.get(key)
    if got is None:
        got = _drawn[key] = fnt.font_variant(size=fnt.size * VERTICAL)
    return got


def draw_glyphs(d, x, y, line, fnt, fill, adv=None):
    """`line` drawn with ImageDraw `d` from (x, y) on its baseline, glyph by
    glyph so each lands on its own fractional x - Pillow advances by whole
    pixels within a string, which drifts a line's interior apart from GDI+'s
    layout even when the total width agrees - each glyph in drawn(fnt) and
    each advance `adv`'s (the font's sfnt table at `fnt`'s em) or, without
    one, Pillow's in `fnt`, grown where the face is emboldened
    (bold_advance). Every line is drawn so, without `adv` too: an
    unemboldened line used to be drawn whole in `fnt`, with Pillow's kerning
    between its pairs, and cannot be now - a whole line in drawn(fnt) would
    advance at the larger em, and in `fnt` would draw the smaller glyphs -
    so Pillow's kerning between pairs is dropped on that path (the synthetic
    baseline was recorded after the change). Anchored on the baseline: 'la'
    would re-introduce Pillow's own rounded ascender, which metrics()
    avoids."""
    extra = bold_advance(fnt)
    small = drawn(fnt)
    for ch in line:
        d.text((x, y), ch, font=small, fill=fill, anchor='ls')
        x += (adv.advance(ch, fnt.size) if adv else d.textlength(ch, font=fnt)) + extra


def embolden(mask, fnt):
    """A coverage mask of text in `fnt` as GDI+ emboldens it where face()
    says it does: each pixel the more of its own coverage and its
    BOLD_SMEAR'th neighbour's to the left - the overstrike, drawn into the
    mask before it is drawn through so the smear does not compound
    antialiased edges. `mask` as it is otherwise."""
    if not getattr(fnt, 'emboldened', False):
        return mask
    out = mask
    for k in range(1, BOLD_SMEAR + 1):
        right = Image.new('L', mask.size, 0)
        right.paste(mask.crop((0, 0, mask.width - k, mask.height)), (k, 0))
        out = ImageChops.lighter(out, right)
    return out


def rgba(c):
    if not isinstance(c, dict):
        return None
    return (c.get('R', 0), c.get('G', 0), c.get('B', 0), c.get('A', 255))


def wrap(text, fnt, width, measure):
    """GDI DT_WORDBREAK: break on spaces, then split any word too long to fit."""
    out = []
    for para in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if not para:
            out.append('')
            continue
        line = ''
        for word in re.split(r'(\s+)', para):
            if not word:
                continue
            trial = line + word
            if measure(trial, fnt) > width and line.strip():
                out.append(line.rstrip())
                trial = word.lstrip()
            # The word itself may still be wider than the box, at a line's
            # start or after a word: Afterburn 1035 Portrait's 13 pt 'Video
            # Conference' in 90 px, whose 'Conference' is 96 px across.
            while measure(trial, fnt) > width and len(trial) > 1:
                cut = len(trial) - 1
                while cut > 1 and measure(trial[:cut], fnt) > width:
                    cut -= 1
                out.append(trial[:cut])
                trial = trial[cut:]
            line = trial
        out.append(line.rstrip())
    return out


# How much of a line must fit its box's height for GDI+ to show it. Measured
# only as between 17% and 68%: on the synthetic fixture a 40 pt caption whose
# second line would have 17% of its height in the box shows one line, and a
# 14 pt one whose second line has 68% shows two. Half is the assumption.
TRIM_LINE = 0.5


def fitted(text, fnt, width, height, line, measure):
    """The lines GDI+ shows of `text` wrapped to `width` in a box `height`
    tall, each `line` high: as many as fit (TRIM_LINE), one at least, and
    past that the last one shown holds the rest of its paragraph on one line,
    cut to the characters that fit - GDI+'s default StringTrimming.Character,
    no ellipsis. The synthetic fixture's 'Type 40 Italic', in a box one line
    deep and too narrow for it, shows as 'Type 40 Itali'."""
    lines = wrap(text, fnt, width, measure)
    room = max(1, int(height / line + TRIM_LINE)) if line > 0 else len(lines)
    if len(lines) <= room:
        return lines
    k = 0
    for para in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        mine = wrap(para, fnt, width, measure)
        if k + len(mine) < room:
            k += len(mine)
            continue
        # Where the last line shown starts in its paragraph: past the lines
        # before it, each a run of the paragraph's own text.
        pos = 0
        for ln in mine[:room - 1 - k]:
            pos = para.index(ln, pos) + len(ln)
        rest = para[pos:].lstrip()
        cut = len(rest)
        while cut > 1 and measure(rest[:cut], fnt) > width:
            cut -= 1
        return lines[:room - 1] + [rest[:cut].rstrip()]
    return lines[:room]


# GDI+'s simulated italic: a face with no italic of its own drawn as the
# regular sheared right by this much a pixel of height above its baseline,
# its advances the regular's. Measured, not fitted: the stem of the I in each
# of the synthetic fixture's italic captions leans 0.341 at 28 to 40 pt. A
# slant fitted on the page's score comes out at 0.30 instead, because the
# large captions there all sit 0.6-1.2 px right of the snapshot's, and a
# shallower slant moves an italic's ink left; at 0.34 the italic ones sit as
# far right as the regular and bold beside them (docs/render-fidelity.md
# section 9).
OBLIQUE = 0.34


def layout(box, text, fnt, alignv):
    """Where GDI+ sets the lines of `text` in `box` per AlignmentEnum (value =
    3*vertical + horizontal): [(line, x, baseline)], x before DX and the
    oblique's shear. The lines GDI+ shows of it (fitted) in the box less its
    padding (PAD_EM) a side and, centred or at the bottom, less FOOT at its
    foot, set down the box as GDI+ sets them (layout_metrics)."""
    x, y, w, h = box
    pad = PAD_EM * fnt.size
    x, w = x + pad, w - 2 * pad
    vert = alignv // 3          # 0 bottom, 1 middle, 2 top
    horz = alignv % 3           # 0 center, 1 left, 2 right
    d0 = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    asc, desc = layout_metrics(fnt)
    lh = asc + desc
    lines = fitted(text, fnt, w, h, lh, lambda s, f: measure(s, f, d0))
    block = lh * len(lines)
    foot = FOOT * fnt.size / PT
    if vert == 2:
        top = y
    elif vert == 1:
        top = y + (h - foot - block) / 2
    else:
        top = y + h - foot - block
    out = []
    for i, ln in enumerate(lines):
        tw = measure(ln, fnt, d0)
        if horz == 1:
            tx = x
        elif horz == 2:
            tx = x + w - tw
        else:
            tx = x + (w - tw) / 2
        out.append((ln, tx, top + i * lh + asc))
    return out


def _breaks(text, fnt, width, measure):
    """Each place wrap() breaks a paragraph of `text` in a box `width` across:
    (the line before the break, counted across the caption as wrap() counts
    them; the paragraph; where in it that line ends; where the next starts)."""
    out, g = [], 0
    for para in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        lines = wrap(para, fnt, width, measure)
        pos, ends = 0, []
        for ln in lines:
            at = para.index(ln, pos) if ln else pos
            ends.append((at, at + len(ln)))
            pos = at + len(ln)
        out += [(g + i, para, a[1], b[0]) for i, (a, b) in enumerate(zip(ends, ends[1:]))]
        g += len(lines)
    return out


# How many whole rows or columns of a line's ink (line_ink) past its box make
# caption_fit say GUI Designer cuts it. GUI Designer cuts a live caption's
# ink flat at its box, row by row, with no tolerance: Turbulence 720's
# Confirmation and Incoming Call questions, two lines of 20 pt Open Sans
# Light in 316x64 boxes, end on the box's last row in its snapshot, and in a
# copy with the boxes shrunk about their middles to 316x60 and 316x58 it cut
# 2 rows off the first's foot and 2 off the second's top and 3 off its foot,
# where line_ink puts exactly those rows past the box. On that seed's other 31
# pages and the synthetic fixture's 29, every line whose ink comes within
# 2.5 px of its box ends on the row the snapshot's does, and the one line
# line_ink puts past it, Turbulence 720's 12 pt 'Window' in 92x15, has the
# top row of its 'd' cut off in the snapshot (docs/render-fidelity.md
# finding 7).
CLIP_PX = 1


def caption_fit(box, text, fnt, alignv):
    """What GUI Designer does to a live caption that loses its words, laid out
    as layout() lays it in `box` per AlignmentEnum `alignv`: [] where every
    character shows, each word on one line, inside the box. Else each of

      ('trims', words)  - fitted() shows fewer of its characters than it has:
                          a line too many for the box's depth dropped, the
                          last line shown cut at a character, no ellipsis
                          (StringTrimming.Character) - the Shockwave 525's
                          18 pt 'Volume' in its 91 px heading box built as
                          'Volum';
      ('splits', words) - a word too wide for the box less its padding
                          (PAD_EM) broken across two lines (wrap);
      ('clips', words)  - a line shown with CLIP_PX or more rows or columns
                          of its ink (line_ink) past the box, which GUI
                          Designer cuts off flat there: Turbulence 720's
                          'Incoming call, do you wish to accept?' at 20 pt in
                          316x58 lost 2 rows off its top and 3 off its foot.

    `words` says it, with the room the caption needs where that is one
    number: across for its longest line or word, at its padding, or down for
    its lines."""
    x, y, w, h = box
    pad = PAD_EM * fnt.size
    d0 = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    m = lambda s, f: measure(s, f, d0)
    placed = layout(box, text, fnt, alignv)
    shown = [ln for ln, _, _ in placed]
    lh = sum(layout_metrics(fnt))
    out = []
    full = [p for p in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    if len(re.sub(r'\s+', '', ''.join(shown))) < len(re.sub(r'\s+', '', text)):
        lines = wrap(text, fnt, w - 2 * pad, m)
        across = int(-(-(max(m(p, fnt) for p in full) + 2 * pad) // 1))
        down = int(-(-(len(full) * lh) // 1))
        if len(lines) > len(full):
            # Wrapped onto lines the box has no depth for: wider, each of its
            # own lines on one - and deeper, where it has not the depth for
            # those either.
            holds = max(1, int(h / lh + TRIM_LINE)) >= len(full)
            room = (f"its words need {across} px across{' on one line' if len(full) == 1 else ''}"
                    + ('' if holds else f' and {down} px down'))
        else:
            room = f'its {len(full)} lines need {down} px down'
        out.append(('trims', f"GUI Designer shows {' / '.join(shown)!r} of {' / '.join(full)!r} in "
                             f'{w}x{h} - {room}'))
    # A break shown on both sides: one into what is trimmed is the trim's.
    split = []
    for i, para, end, nxt in _breaks(text, fnt, w - 2 * pad, m):
        if i + 1 >= len(shown):
            break
        if 0 < end < len(para) and nxt == end and not para[end - 1].isspace() and not para[end].isspace():
            a = end
            while a > 0 and not para[a - 1].isspace():
                a -= 1
            b = end
            while b < len(para) and not para[b].isspace():
                b += 1
            if para[a:b] not in split:
                split.append(para[a:b])
    for word in split:
        need = m(word, fnt) + 2 * pad
        out.append(('splits', f'GUI Designer breaks {word!r} across lines in {w} px - it needs '
                              f'{int(-(-need // 1))} px across'))
    over = {}
    for i, (ln, tx, base) in enumerate(placed):
        ink = line_ink(ln, fnt, tx, base)
        if ink is None:
            continue
        for side, past in (('top', y - ink[1]), ('foot', ink[3] - (y + h)),
                           ('left side', x - ink[0]), ('right side', ink[2] - (x + w))):
            if past >= CLIP_PX:
                over[side] = max(over.get(side, 0), past)
    if over:
        out.append(('clips', 'its ink runs ' + ', '.join(f'{int(v)} px past the box\'s {k}' for k, v in over.items())
                    + f' in {w}x{h} - GUI Designer cuts it there'))
    return out


# How much of a pixel a glyph's ink must cover for line_ink to count it:
# half. A 20 pt Open Sans Light 'y' on Turbulence 720's Confirmation runs
# 43% of a row past its box in GUI Designer's snapshot, which cuts it there,
# and no one sees it; the hinted rows above and below a glyph are near whole.
INK_SEEN = 128


def line_ink(ln, fnt, tx, base):
    """(left, top, right, foot) of the ink of `ln` - its pixels INK_SEEN
    covered, the outer edges of the outermost - as draw_text draws it from
    `tx` (layout()'s, before DX) on `base`, read off the line drawn alone so:
    each glyph in drawn(fnt) on its baseline rounded to a whole pixel, as
    Pillow sets one, emboldened (embolden) and leant by the oblique about
    its own baseline (OBLIQUE). None where it draws none."""
    if not ln.strip():
        return None
    shear = OBLIQUE if getattr(fnt, 'oblique', False) else 0.0
    small = drawn(fnt)
    pad = int(small.size * (1 + shear)) + 4
    ox, oy = math.floor(tx) - pad, math.floor(base) - 2 * pad
    mask = Image.new('L', (int(measure(ln, fnt)) + 2 * pad + BOLD_SMEAR, 3 * pad), 0)
    # The page's own fractions, so Pillow rounds this baseline as it does there.
    draw_glyphs(ImageDraw.Draw(mask), tx + DX - ox, base - oy, ln, fnt, 255,
                advances(fnt) if FRAC_PLACE else None)
    mask = embolden(mask, fnt)
    if shear:
        mask = mask.transform(mask.size, Image.AFFINE, (1, shear, -shear * (base - oy), 0, 1, 0),
                              resample=Image.BILINEAR)
    bb = mask.point(lambda v: 255 if v >= INK_SEEN else 0).getbbox()
    return None if bb is None else (bb[0] + ox, bb[1] + oy, bb[2] + ox, bb[3] + oy)


# No alignment: what GUI Designer writes on a built control whose states
# disagree, each state carrying its own (tests/verify_built.py ALIGN_MIXED).
_ALIGN_MIXED = 9


def built_captions(c, texts=None):
    """Each live caption a built control shows, once, as caption_fit takes
    it: [(state, text, font, align)] for layout.json's PBLabel or PBButton
    `c` - `font` the Font it is set in, `align` its AlignmentEnum, `state`
    the state's Name where its words are not the control's own, else None.
    `texts` is {index: words} to read in place of those states' own (an
    edit's rename; None for the control's own, where it has no states).

    None of a caption Build bakes (FlattenText; a formatted caption reads
    back ''), of one character - a glyph, a key's letter, never trimmed or
    split - or drawn in a color with no alpha, which shows nothing to cut:
    the Zoom Rooms seeds keep space-padded words so behind their icons."""
    if c.get('FlattenText'):
        return []
    sts = c.get('States') or []
    rows = list(enumerate(sts)) if sts else [(None, c)]
    texts = texts or {}

    def words(i, st):
        return texts[i] if i in texts else st.get('Text') or ''
    first = words(*rows[0]) or c.get('Text') or ''
    out, seen = [], set()
    for i, st in rows:
        text = words(i, st)
        if len(text.strip()) <= 1 or text in seen:
            continue
        seen.add(text)
        color = st.get('TextColor') or c.get('TextColor')
        if isinstance(color, dict) and color.get('A') == 0:
            continue
        align = st.get('TextAlignment')
        if align is None or align == _ALIGN_MIXED:
            align = c.get('TextAlignment')
        if align is None or align == _ALIGN_MIXED:
            align = 3
        out.append((st.get('Name') if sts and text != first else None, text,
                    st.get('Font') or c.get('Font') or {}, align))
    return out


def caption_cuts(c, texts=None, box=None):
    """caption_fit over each of built_captions(c, texts), in its own face -
    the built file's, inside as_the_panel(project). (cuts, unmeasured,
    measured): cuts [(state, text, kind, words, at)] - `at` the size and face
    it is set in, as a problem says it - and unmeasured [(state, text,
    why)], each caption whose face is drawn here in a stand-in (face()),
    whose widths are not the panel's, or is not here at all. `box` is
    [x, y, w, h] in place of the control's."""
    box = tuple(box) if box else (c['Left'], c['Top'], c['Width'], c['Height'])
    cuts, unmeasured, measured = [], [], 0
    for state, text, f, align in built_captions(c, texts):
        style = f.get('Style') or {}
        name, pt = f.get('Name', 'Arial'), f.get('PointSize', 12)
        try:
            fnt = face(name, int(bool(style.get('Bold'))), int(bool(style.get('Italic'))), pt * PT)
        except (LookupError, OSError) as e:
            unmeasured.append((state, text, f'{name} has no face here to draw it in ({e})'))
            continue
        if getattr(fnt, 'stand_in', None):
            unmeasured.append((state, text, f'{fnt.stand_in}, a stand-in'))
            continue
        measured += 1
        at = (f"{pt:g} pt in {name}{' bold' if style.get('Bold') else ''}"
              f"{' italic' if style.get('Italic') else ''}")
        cuts += [(state, text, kind, words, at) for kind, words in caption_fit(box, text, fnt, align)]
    return cuts, unmeasured, measured


def draw_text(img, box, text, fnt, color, alignv):
    """Draw `text` in `box` per AlignmentEnum where GDI+ sets its lines
    (layout) - emboldened (embolden, BOLD_ADVANCE_EM) and obliqued (OBLIQUE)
    where the face stands in for a bold or an italic it does not have
    (face())."""
    lines = layout(box, text, fnt, alignv)
    lh = sum(layout_metrics(fnt))
    shear = OBLIQUE if getattr(fnt, 'oblique', False) else 0.0
    bold = getattr(fnt, 'emboldened', False)
    # Emboldened or sheared, the glyphs are drawn into a coverage mask first,
    # the mask smeared (embolden) and sheared about the first line's baseline -
    # each line set right by as much as that moves its own baseline left - and
    # drawn through, which blends as ImageDraw.text does.
    mask = Image.new('L', img.size, 0) if shear or bold else None
    d = ImageDraw.Draw(img if mask is None else mask)
    ink = color if mask is None else 255
    adv = advances(fnt) if FRAC_PLACE else None
    for i, (ln, tx, base) in enumerate(lines):
        draw_glyphs(d, tx + DX + shear * i * lh, base, ln, fnt, ink, adv)
    if mask is None:
        return
    mask = embolden(mask, fnt)
    if shear and lines:
        y0 = lines[0][2]
        mask = mask.transform(mask.size, Image.AFFINE, (1, shear, -shear * y0, 0, 1, 0),
                              resample=Image.BILINEAR)
    ImageDraw.Draw(img).bitmap((0, 0), mask, fill=color)


# Whether paste() composites as GUI Designer's own snapshots do (snapshot_over).
# as_the_panel() turns it off for a picture of the panel a person reads, which
# blends as Pillow does (alpha_composite). The name is the rule's first
# measurement's: over a transparent destination the snapshot rule still writes
# a pixel at full strength, binary, as flatten() does.
BINARY = True

# GDI+'s gamma-corrected compositing: a translucent pixel is blended over what
# is under it in light, each channel raised to 2.2 before and lowered after.
# Measured on the synthetic fixture over every partial-alpha asset pixel above
# opaque art - 27,127 of them, translucent fills and antialiased edges both:
# mean error 1.08 levels a channel, where 2.1 is 3.10, 2.3 is 2.72, the sRGB
# curve 1.80, a plain blend 29.04 and a binary write 85.43
# (docs/render-fidelity.md finding 2).
GAMMA = 2.2
_LIN = [(v / 255) ** GAMMA for v in range(256)]


def snapshot_over(canvas, im, x, y):
    """Composite RGBA `im` onto `canvas` at (x, y) as GUI Designer's snapshot
    does, GDI+'s source-over in light (GAMMA).

    Over an opaque destination a pixel blends at its own alpha. Over a
    transparent one it is written as it is, its alpha with it, and flatten()
    then puts it on black at full strength - the rule finding 4's bilevel text
    reads. A destination in between (a modal's scrim) takes the general form,
    the destination's alpha weighting its color. Only the pixels that blend
    are computed; the rest are a plain masked paste."""
    x, y = int(x), int(y)
    sa = im.getchannel('A')
    under = canvas.crop((x, y, x + im.width, y + im.height))
    canvas.paste(im, (x, y), sa.point(lambda a: 255 if a else 0))
    blend = ImageChops.multiply(sa.point(lambda a: 255 if 0 < a < 255 else 0),
                                under.getchannel('A').point(lambda a: 255 if a else 0))
    box = blend.getbbox()
    if box is None:
        return
    src, dst, m = im.crop(box).tobytes(), under.crop(box).tobytes(), blend.crop(box).tobytes()
    out = bytearray(len(src))
    inv = 1 / GAMMA
    for i, on in enumerate(m):
        if not on:
            continue
        j = 4 * i
        a, d = src[j + 3] / 255, dst[j + 3] / 255
        da = d * (1 - a)
        oa = a + da
        for k in range(3):
            v = (_LIN[src[j + k]] * a + _LIN[dst[j + k]] * da) / oa
            out[j + k] = round(255 * v ** inv)
        out[j + 3] = round(255 * oa)
    canvas.paste(Image.frombytes('RGBA', (box[2] - box[0], box[3] - box[1]), bytes(out)),
                 (x + box[0], y + box[1]), blend.crop(box))


def paste(canvas, assets, img_id, x, y, clip=None, binary=None):
    """Blit an asset: as GUI Designer's snapshot composites it
    (snapshot_over), or, with BINARY off, as Pillow blends it."""
    binary = BINARY if binary is None else binary
    if img_id is None or img_id not in assets:
        return
    im = Image.open(io.BytesIO(assets[img_id])).convert('RGBA')
    if clip:
        im = im.crop(clip)
        x, y = x + clip[0], y + clip[1]
    if binary:
        snapshot_over(canvas, im, x, y)
    else:
        canvas.alpha_composite(im, (int(x), int(y)))


def fill_index(path):
    """(page id, control id) -> the fill Build would have rasterized.

    A control authored with TLPImageID == -1 has no artwork in the payload, and
    its real interior color - borderFillColor plus a *named* border resource
    giving the corner radius - exists only in ProjectGCP. layout.json exports
    neither, so the compositor cannot draw the control at all without going
    back to the authoring model. See docs/render-fidelity.md finding 1.

    The key is the pair of ids both models already share: a page's `idField` is
    layout.json's `Page.ID`, and a control's `idField` is its `Control.ID`
    (verified equal across all six fixtures). An earlier version keyed on
    (type, rect) because the authoring model was only read as a flat object
    graph - that worked here, but only because the eligible set is a single
    control per file. (type, rect) is not unique over controls generally, and
    nothing checked the destination side, so two same-typed same-positioned
    controls on different pages would both have been filled.
    """
    from .project import Project

    return Project.open(path).fill_map()


def draw_fill(canvas, box, spec):
    """Paint the rounded rectangle Build would have baked into a PNG - and,
    for a spec's image button, its image fitted over it (ImageLayoutEnum
    Fill, MiddleCenter, as every image button in Extron's templates has it),
    or for an image control its art as it lies (`image_layout` 1: stretched,
    as the Turbulence seeds' header and footer bars are)."""
    fill = rgba(spec['fill'])
    stroke = rgba(spec.get('stroke'))
    if not fill or not fill[3]:
        fill = None
    if not stroke or not stroke[3]:
        stroke = None
    if fill or stroke:
        _draw_box(canvas, box, spec, fill, stroke)
    if spec.get('image'):
        (draw_stretched if spec.get('image_layout') == 1 else draw_fitted)(canvas, box, spec['image'])


def draw_stretched(canvas, box, path):
    """`path` stretched over `box`, as Build draws an image laid out
    Stretch."""
    art = Image.open(path).convert('RGBA').resize((max(1, box[2]), max(1, box[3])), Image.LANCZOS)
    canvas.alpha_composite(art, (box[0], box[1]))


def draw_fitted(canvas, box, path):
    """`path` drawn into `box` as Build draws an authored image: Fill (fit,
    keeping the aspect) and MiddleCenter, as every image in the Afterburn
    seeds is laid out."""
    art = Image.open(path).convert('RGBA')
    k = min(box[2] / art.width, box[3] / art.height)
    art = art.resize((max(1, round(art.width * k)), max(1, round(art.height * k))),
                     Image.LANCZOS)
    canvas.alpha_composite(art, (box[0] + (box[2] - art.width) // 2,
                                 box[1] + (box[3] - art.height) // 2))


def _draw_box(canvas, box, spec, fill, stroke):
    border = spec.get('border') or {}
    radius = border.get('radius', 0)
    thickness = border.get('thickness', 0) if stroke else 0
    x0, y0 = box[0], box[1]
    x1, y1 = box[0] + box[2] - 1, box[1] + box[3] - 1
    # A capsule is stored as radius 9999 rather than a shape flag, so clamp
    # rather than hand Pillow a radius larger than the box.
    radius = min(radius, min(box[2], box[3]) // 2)
    # ImageDraw writes an RGBA fill over the pixels under it, translucent or
    # not. So draw on a clear layer and composite it, so a fill at 85% shows
    # what is under it: as the snapshot blends (snapshot_over), or as the
    # panel picture does.
    # The layer is the box's own bounds (less what lies off the canvas), not the
    # canvas: snapshot_over walks every pixel of what it is given.
    lx, ly = max(0, int(x0)), max(0, int(y0))
    lw, lh = min(canvas.width, int(x1) + 1) - lx, min(canvas.height, int(y1) + 1) - ly
    if lw <= 0 or lh <= 0:
        return
    layer = Image.new('RGBA', (lw, lh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = [x0 - lx, y0 - ly, x1 - lx, y1 - ly]
    if radius > 0:
        d.rounded_rectangle(r, radius=radius, fill=fill,
                            outline=stroke, width=max(1, thickness) if stroke else 0)
    else:
        d.rectangle(r, fill=fill,
                    outline=stroke, width=max(1, thickness) if stroke else 0)
    if BINARY:
        snapshot_over(canvas, layer, lx, ly)
    else:
        canvas.alpha_composite(layer, (lx, ly))


def group_members(layout):
    """GroupID -> popup page IDs, in PopupPages array order."""
    out = {}
    for p in layout.get('PopupPages') or []:
        g = p.get('GroupID')
        if g:
            out.setdefault(g, []).append(p)
    return out


def render_control(canvas, c, assets, ox, oy, draw_txt=True, groups=None, fills=None,
                   page_id=None):
    ref = popup_ref(c)
    if ref:
        # A reference bound to one popup paints nothing. A reference bound to a
        # GROUP does: GUI Designer composites one member into the anchor rect,
        # and its snapshot is taken with that member showing. Draw it here, in
        # the anchor's own z-order slot rather than on top of everything.
        gid = ref.get('group')
        if gid and groups and groups.get(gid):
            render_page(groups[gid][0], assets, None, ox + c['Left'], oy + c['Top'],
                        canvas=canvas, draw_txt=draw_txt, groups=groups, fills=fills)
        return
    kind = c['__type'].split(':')[0]
    states = c.get('States') or []
    st = states[c.get('TLPDefaultStateID', 0)] if states else None
    src = st or c

    base = c.get('TLPImageID')
    if kind == 'PBLevel':
        base = c.get('TLPMinValueImageID', base)
    elif st is not None:
        base = st.get('TLPImageID', base)
    x, y, w, h = c['Left'] + ox, c['Top'] + oy, c['Width'], c['Height']
    if base in (None, -1) or base not in assets:
        # Build never rasterized this one, so there is no PNG to blit. Its fill
        # lives in the authoring model; synthesise what Build would have baked.
        spec = (fills or {}).get((page_id, c.get('ID')))
        if spec:
            draw_fill(canvas, (x, y, w, h), spec)
    paste(canvas, assets, base, x, y)

    # value fill for sliders / levels, parked at half travel
    mx = c.get('TLPMaxValueImageID')
    if mx is not None and mx != base and mx in assets:
        o = c.get('Orientation', 0)
        if o == 2:
            paste(canvas, assets, mx, x, y, clip=(0, h // 2, w, h))
        elif o == 3:
            paste(canvas, assets, mx, x, y, clip=(0, 0, w, h // 2))
        elif o == 1:
            paste(canvas, assets, mx, x, y, clip=(w // 2, 0, w, h))
        else:
            paste(canvas, assets, mx, x, y, clip=(0, 0, w // 2, h))
    ind = c.get('SliderIndicatorImageID')
    if ind and ind in assets:
        iw = c.get('SliderIndicatorWidth') or w
        ih = c.get('SliderIndicatorHeight') or h
        o = c.get('Orientation', 0)
        if o in (2, 3):
            paste(canvas, assets, ind, x + (w - iw) // 2, y + (h - ih) // 2)
        else:
            paste(canvas, assets, ind, x + (w - iw) // 2, y + (h - ih) // 2)

    if not draw_txt or c.get('FlattenText'):
        return
    text = src.get('Text') or c.get('Text') or ''
    if not text.strip():
        return
    f = src.get('Font') or c.get('Font') or {}
    style = f.get('Style') or {}
    fnt = face(f.get('Name', 'Arial'), int(bool(style.get('Bold'))),
               int(bool(style.get('Italic'))), f.get('PointSize', 12) * PT)
    col = rgba(src.get('TextColor')) or rgba(c.get('TextColor')) or (255, 255, 255, 255)
    draw_text(canvas, (x, y, w, h), text,
              fnt, col, src.get('TextAlignment', c.get('TextAlignment', 3)))


def flatten(canvas):
    """Put the finished page on opaque black, the way the panel displays it.

    Deliberately the same binary rule paste() uses rather than an alpha
    composite: a pixel that was painted keeps its own color at full strength,
    an untouched one stays black. That reproduces the previous
    opaque-canvas-from-the-start behavior exactly.

    The final putalpha is not cosmetic. paste() copies the source's own alpha
    through, so a page whose art is itself semi-transparent (the modal scrim
    asset is a uniform alpha 166) would otherwise come back partly transparent
    from a function whose contract says opaque. Every caller today converts to
    RGB, which drops alpha rather than compositing it, so this is currently
    invisible - measured identical across all 27 pages. It is here so the
    contract is true rather than true-by-accident-of-the-caller.
    """
    bg = Image.new('RGBA', canvas.size, (0, 0, 0, 255))
    if not BINARY:
        # The panel's black shows through what is translucent.
        bg.alpha_composite(canvas)
        return bg
    bg.paste(canvas, (0, 0), canvas.getchannel('A').point(lambda a: 255 if a else 0))
    bg.putalpha(255)
    return bg


def render_page(pg, assets, size, ox=0, oy=0, canvas=None, draw_txt=True, groups=None,
                fills=None, flat=True):
    # The canvas starts *transparent* and is flattened onto black once, at the
    # end of the outermost call. An opaque-from-the-start canvas destroys the
    # only signal that says whether a control sits over real artwork or over
    # nothing, and that signal is what finding 4's bilevel/antialiased text
    # decision reads. Nested calls (popup-group members) are handed the live
    # canvas and must not flatten it.
    outermost = canvas is None
    if outermost:
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        fill = rgba(pg.get('BackgroundFillColor'))
        if pg.get('TLPImageID', -1) == -1 and fill and fill[3]:
            canvas.paste(fill, [0, 0, *size])
        # A spec's page image: an authored page has no artwork yet, so draw
        # what Build will bake - the image over the fill. Built pages never
        # carry this key.
        if pg.get('TLPImageID', -1) == -1 and pg.get('_background_image'):
            if pg.get('_background_layout') == 1:
                # Stretch, as Mach's pages lay out their photo.
                art = Image.open(pg['_background_image']).convert('RGBA').resize(
                    (size[0], size[1]), Image.Resampling.LANCZOS)
                canvas.alpha_composite(art)
            else:
                draw_fitted(canvas, (0, 0, size[0], size[1]), pg['_background_image'])
    paste(canvas, assets, pg.get('TLPImageID'), ox, oy)
    for c in (pg.get('Controls') or []):
        render_control(canvas, c, assets, ox, oy, draw_txt, groups, fills, pg.get('ID'))
    return flatten(canvas) if outermost and flat else canvas


def popup_groups(j):
    """GroupID -> member popup IDs, in PopupPages declaration order.

    Element 0 of each list is the member GUI Designer previews on the host
    page (proven against Individual == Permutation snapshots for groups 1,
    2, 3 and 5).
    """
    g = {}
    for p in j.get('PopupPages') or []:
        if p.get('IsGroupValid'):
            g.setdefault(p['GroupID'], []).append(p['ID'])
    return g


def render_snapshot(j, pid, assets, size, shown=None, draw_txt=True, fills=None):
    """Render a page the way GUI Designer's own snapshot does.

    A PBPopupPageReference bound to a single popup (IsPopupPageIdValid)
    paints nothing.  One bound to a popup *group* (IsPopupGroupIdValid)
    paints a member of that group at the anchor's origin - by default the
    first member in declaration order, or `shown[GroupID]` if given.
    """
    pages = {p['ID']: p for p in j['Pages'] + j['PopupPages']}
    groups = popup_groups(j)
    pg = pages[pid]
    canvas = render_page(pg, assets, size, draw_txt=draw_txt, fills=fills, flat=False)
    for c in (pg.get('Controls') or []):
        pp = c.get('PopupPageID')
        if not isinstance(pp, dict) or not pp.get('IsPopupGroupIdValid'):
            continue
        members = groups.get(pp.get('GroupID')) or []
        if not members:
            continue
        mid = (shown or {}).get(pp['GroupID'], members[0])
        if mid is None:
            continue
        render_page(pages[mid], assets, size, ox=c['Left'], oy=c['Top'],
                    canvas=canvas, draw_txt=draw_txt, fills=fills)
    return flatten(canvas)


def load(path):
    z = open_gdl(path)
    # A .gdl saved by GUI Designer *without* building carries only ProjectGCP -
    # the stale payload is dropped rather than kept. That is a legitimate state
    # (an unbuilt project), so say so instead of failing with a bare
    # StopIteration from the generator below.
    payload = next((n for n in z.namelist() if n != 'ProjectGCP'), None)
    if payload is None:
        raise ValueError(
            f'{path} has no built payload - only ProjectGCP. GUI Designer drops the '
            f'payload when a project is saved without building; open it and use '
            f'File > Save and Build (Ctrl+Shift+B). The authoring model is still '
            f'readable with gdl.project.')
    inner = zipfile.ZipFile(io.BytesIO(z.read(payload)))
    j = json.loads(inner.read('layout.json'))
    assets = {int(n[:-4]): inner.read(n) for n in inner.namelist() if n.endswith('.png')}
    return j, assets


def glyph_sheet(data, out, cols=10, cell=96):
    """Every glyph a face draws - its bytes - ten to a row, each with its
    codepoint and the name the face gives it: how an icon is picked out of a
    face that names nothing (python -m gdl.spec icons)."""
    face = sfnt.Advances(data)
    cps = sorted(c for c, g in face.cmap.items() if c > 0x20 and g)
    names = {cp: n for n, cp in face.glyph_names().items()}
    img = Image.new('RGB', (cols * cell, max(1, -(-len(cps) // cols)) * cell), (27, 29, 38))
    d = ImageDraw.Draw(img)
    glyph = ImageFont.truetype(io.BytesIO(data), cell // 2)
    label = ImageFont.load_default()
    for i, cp in enumerate(cps):
        x, y = i % cols * cell, i // cols * cell
        d.rectangle([x + 2, y + 2, x + cell - 3, y + cell - 3], outline=(58, 62, 82))
        d.text((x + cell // 2, y + cell * 2 // 5), chr(cp), font=glyph, fill='white', anchor='mm')
        d.text((x + 6, y + cell - 26), f'U+{cp:04X}', font=label, fill=(154, 160, 184))
        if cp in names:
            d.text((x + 6, y + cell - 14), names[cp][:14], font=label, fill=(154, 160, 184))
    img.save(out)


def diff_stats(a, b):
    a, b = a.convert('RGB'), b.convert('RGB')
    d = ImageChops.difference(a, b)
    bbox = d.getbbox()
    hist = d.convert('L').histogram()
    total = a.width * a.height
    off = total - hist[0]
    bad = sum(hist[24:])
    return {'pct_any': 100 * off / total, 'pct_bad': 100 * bad / total, 'bbox': bbox}
