"""Exact glyph advance widths, straight out of a font's own tables.

Pillow will not give these. FreeType grid-fits every advance to a whole pixel,
and it does so whatever you pass for mode or layout_engine - measured on
Open Sans at 22px, every glyph comes back an integer and the string length is
their integer sum. GDI+ lays text out with *fractional* advances, so our wrap
points and our centred/right-aligned text drift from GUI Designer's by up to
half a pixel per glyph, accumulating across a line.

So read the advances ourselves: `hmtx` scaled by `head.unitsPerEm`, with `cmap`
to get from a character to a glyph id. That is a small amount of binary
plumbing and it keeps this package dependency-free, which is the point of
gdl/ being importable on a machine with nothing installed.

Works for both TrueType outlines and the OTF/CFF face in this corpus: hmtx,
hhea, head and cmap are required tables in both flavours.

    from gdl.sfnt import Advances
    adv = Advances('gdl/fonts/opensans-regular.ttf')
    adv.length('Matrix Routing', 22)   # -> 153.63..., not Pillow's 154.0
"""
import struct

# cmap subtable preference, best first: Windows BMP and full-repertoire
# encodings before the Mac 8-bit ones, which cannot represent most of what
# these panels display.
_CMAP_RANK = ((3, 10), (3, 1), (0, 4), (0, 3), (0, 6), (3, 0), (0, 0), (1, 0))


class Advances:
    """Character -> advance width in font units, plus the em size to scale by."""

    def __init__(self, path):
        with open(path, 'rb') as fh:
            self.d = fh.read()
        self.tables = self._directory()
        self.upem = self._upem()
        self.hmtx = self._hmtx()
        self.cmap = self._cmap()
        self.win_ascent, self.win_descent = self._vmetrics()
        self._px = {}

    def _vmetrics(self):
        """OS/2 usWinAscent / usWinDescent, in font units.

        These are the numbers GDI builds its line box from, and they are not
        what Pillow reports: getmetrics() returns FreeType's scaled *and
        rounded* values. On Open Sans at 22px that is ascent 24 against a true
        23.51, and a line box of 31 against 29.96 - a whole pixel per line,
        which a vertically centred block splits in half and a two-line block
        pays in full.
        """
        try:
            os2 = self._table(b'OS/2')
            return struct.unpack('>HH', os2[74:78])
        except (ValueError, struct.error):
            # No OS/2 (rare, mostly old Mac-only fonts): fall back to hhea.
            asc, desc = struct.unpack('>hh', self._table(b'hhea')[4:8])
            return asc, -desc

    # -- container ---------------------------------------------------------
    def _directory(self):
        tag, num = struct.unpack('>IH', self.d[:6])
        if tag == 0x74746366:                       # 'ttcf' - collection
            off = struct.unpack('>I', self.d[12:16])[0]
            num = struct.unpack('>H', self.d[off + 4:off + 6])[0]
            base = off + 12
        else:
            base = 12
        out = {}
        for i in range(num):
            rec = self.d[base + 16 * i:base + 16 * i + 16]
            if len(rec) < 16:
                break
            name, _, offset, length = struct.unpack('>4sIII', rec)
            out[name] = (offset, length)
        return out

    def _table(self, name):
        got = self.tables.get(name)
        if not got:
            raise ValueError(f'font has no {name!r} table')
        off, length = got
        return self.d[off:off + length]

    # -- metrics -----------------------------------------------------------
    def _upem(self):
        return struct.unpack('>H', self._table(b'head')[18:20])[0]

    def _hmtx(self):
        # hhea.numberOfHMetrics is the count of *paired* entries; every glyph
        # past that repeats the last advance, which is how monospaced tails
        # and many CJK faces are stored.
        n = struct.unpack('>H', self._table(b'hhea')[34:36])[0]
        raw = self._table(b'hmtx')
        adv = []
        for i in range(n):
            if len(raw) < 4 * i + 2:
                break
            adv.append(struct.unpack('>H', raw[4 * i:4 * i + 2])[0])
        return adv

    # -- character mapping -------------------------------------------------
    def _cmap(self):
        raw = self._table(b'cmap')
        n = struct.unpack('>H', raw[2:4])[0]
        subtables = {}
        for i in range(n):
            pid, eid, off = struct.unpack('>HHI', raw[4 + 8 * i:12 + 8 * i])
            subtables.setdefault((pid, eid), off)
        for key in _CMAP_RANK:
            if key in subtables:
                got = self._parse_cmap(raw, subtables[key])
                if got:
                    return got
        for off in subtables.values():
            got = self._parse_cmap(raw, off)
            if got:
                return got
        return {}

    def _parse_cmap(self, raw, off):
        fmt = struct.unpack('>H', raw[off:off + 2])[0]
        if fmt == 4:
            return self._cmap4(raw, off)
        if fmt == 12:
            return self._cmap12(raw, off)
        if fmt == 6:
            first, count = struct.unpack('>HH', raw[off + 6:off + 10])
            ids = struct.unpack(f'>{count}H', raw[off + 10:off + 10 + 2 * count])
            return {first + i: g for i, g in enumerate(ids)}
        if fmt == 0:
            return {i: raw[off + 6 + i] for i in range(256)}
        return {}

    def _cmap4(self, raw, off):
        segx2 = struct.unpack('>H', raw[off + 6:off + 8])[0]
        seg = segx2 // 2
        ends = struct.unpack(f'>{seg}H', raw[off + 14:off + 14 + segx2])
        p = off + 16 + segx2
        starts = struct.unpack(f'>{seg}H', raw[p:p + segx2])
        p += segx2
        deltas = struct.unpack(f'>{seg}h', raw[p:p + segx2])
        p += segx2
        range_off_at = p
        range_offs = struct.unpack(f'>{seg}H', raw[p:p + segx2])
        out = {}
        for i in range(seg):
            for ch in range(starts[i], min(ends[i], 0xFFFF) + 1):
                if range_offs[i] == 0:
                    gid = (ch + deltas[i]) & 0xFFFF
                else:
                    # The spec's pointer arithmetic: the offset is relative to
                    # the range_offset slot's own address.
                    at = range_off_at + 2 * i + range_offs[i] + 2 * (ch - starts[i])
                    if at + 2 > len(raw):
                        continue
                    gid = struct.unpack('>H', raw[at:at + 2])[0]
                    if gid:
                        gid = (gid + deltas[i]) & 0xFFFF
                if gid:
                    out[ch] = gid
        return out

    def _cmap12(self, raw, off):
        ngroups = struct.unpack('>I', raw[off + 12:off + 16])[0]
        out = {}
        for i in range(ngroups):
            p = off + 16 + 12 * i
            start, end, gid = struct.unpack('>III', raw[p:p + 12])
            if end - start > 0x10000:               # refuse absurd groups
                continue
            for j, ch in enumerate(range(start, end + 1)):
                out[ch] = gid + j
        return out

    # -- public ------------------------------------------------------------
    def advance(self, ch, px):
        """Advance of one character in pixels at a given em size, unrounded."""
        key = (ch, px)
        got = self._px.get(key)
        if got is None:
            gid = self.cmap.get(ord(ch), 0)
            units = self.hmtx[gid] if gid < len(self.hmtx) else (self.hmtx[-1] if self.hmtx else 0)
            got = self._px[key] = units * px / self.upem
        return got

    def length(self, text, px):
        return sum(self.advance(c, px) for c in text)

    def vmetrics(self, px):
        """(ascent, descent) in pixels at a given em size, unrounded."""
        return (self.win_ascent * px / self.upem,
                self.win_descent * px / self.upem)
