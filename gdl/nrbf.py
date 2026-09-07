import struct


class R:
    def __init__(s, b):
        s.b = b
        s.i = 0
        s.objects = {}
        s.classes = {}
        s.libs = {}
        s.records = []

    def u8(s):
        v = s.b[s.i]
        s.i += 1
        return v

    def i32(s):
        v = struct.unpack_from('<i', s.b, s.i)[0]
        s.i += 4
        return v

    def i64(s):
        v = struct.unpack_from('<q', s.b, s.i)[0]
        s.i += 8
        return v

    def string(s):
        n = 0
        sh = 0
        while True:
            x = s.b[s.i]
            s.i += 1
            n |= (x & 0x7f) << sh
            sh += 7
            if not (x & 0x80):
                break
        v = s.b[s.i:s.i + n].decode('utf-8', 'replace')
        s.i += n
        return v

    def prim(s, t):
        import struct as _st
        if t == 1:
            return bool(s.u8())
        if t == 2:
            return s.u8()
        if t == 3:
            n = 1
            c = s.b[s.i]
            if c >= 0xF0: n = 4
            elif c >= 0xE0: n = 3
            elif c >= 0xC0: n = 2
            v = s.b[s.i:s.i + n].decode('utf-8', 'replace')
            s.i += n
            return v
        if t == 5:
            return s.string()
        if t == 6:
            v = _st.unpack_from('<d', s.b, s.i)[0]; s.i += 8; return v
        if t == 7:
            v = _st.unpack_from('<h', s.b, s.i)[0]; s.i += 2; return v
        if t == 8:
            v = _st.unpack_from('<i', s.b, s.i)[0]; s.i += 4; return v
        if t == 9:
            v = _st.unpack_from('<q', s.b, s.i)[0]; s.i += 8; return v
        if t == 10:
            v = _st.unpack_from('<b', s.b, s.i)[0]; s.i += 1; return v
        if t == 11:
            v = _st.unpack_from('<f', s.b, s.i)[0]; s.i += 4; return v
        if t == 12:
            return ('TimeSpan', s.i64())
        if t == 13:
            return ('DateTime', s.i64())
        if t == 14:
            v = _st.unpack_from('<H', s.b, s.i)[0]; s.i += 2; return v
        if t == 15:
            v = _st.unpack_from('<I', s.b, s.i)[0]; s.i += 4; return v
        if t == 16:
            v = _st.unpack_from('<Q', s.b, s.i)[0]; s.i += 8; return v
        if t == 17:
            return None
        if t == 18:
            return s.string()
        raise Exception('prim %d' % t)

    def readtypes(s, count):
        bti = [s.u8() for _ in range(count)]
        add = []
        for t in bti:
            if t == 0:
                add.append(s.u8())
            elif t == 3:
                add.append(s.string())
            elif t == 4:
                add.append((s.string(), s.i32()))
            elif t == 7:
                add.append(s.u8())
            elif t in (1, 2, 5, 6):
                add.append(None)
            else:
                raise Exception('bti %d' % t)
        return bti, add

    def value(s, bt, at):
        if bt == 0:
            return s.prim(at)
        return s.record()

    def members(s, cid):
        name, mnames, bti, add = s.classes[cid]
        d = {'__class': name}
        for mn, bt, at in zip(mnames, bti, add):
            d[mn] = s.value(bt, at)
        return d

    def _arr(s, n):
        arr = []
        i = 0
        while i < n:
            v = s.record()
            if isinstance(v, tuple) and v and v[0] == 'null':
                i += v[1]
                arr.extend([None] * v[1])
            else:
                arr.append(v)
                i += 1
        return arr

    def record(s):
        t = s.u8()
        if t == 0:
            return ('hdr', s.i32(), s.i32(), s.i32(), s.i32())
        if t == 1:
            oid = s.i32()
            mid = s.i32()
            d = s.members(mid)
            d['__id'] = oid
            s.objects[oid] = d
            return d
        if t in (2, 3, 4, 5):
            oid = s.i32()
            nm = s.string()
            cnt = s.i32()
            mn = [s.string() for _ in range(cnt)]
            if t in (4, 5):
                bti, add = s.readtypes(cnt)
            else:
                bti, add = [2] * cnt, [None] * cnt
            if t in (3, 5):
                s.i32()
            s.classes[oid] = (nm, mn, bti, add)
            d = s.members(oid)
            d['__id'] = oid
            s.objects[oid] = d
            return d
        if t == 6:
            oid = s.i32()
            v = s.string()
            s.objects[oid] = v
            return v
        if t == 7:
            oid = s.i32()
            at = s.u8()
            rank = s.i32()
            lens = [s.i32() for _ in range(rank)]
            if at in (3, 4, 5):
                [s.i32() for _ in range(rank)]
            bti, add = s.readtypes(1)
            n = 1
            for L in lens:
                n *= L
            if bti[0] == 0:
                arr = [s.prim(add[0]) for _ in range(n)]
            else:
                arr = s._arr(n)
            s.objects[oid] = arr
            return arr
        if t == 8:
            return s.prim(s.u8())
        if t == 9:
            return ('ref', s.i32())
        if t == 10:
            return None
        if t == 11:
            return ('end',)
        if t == 12:
            oid = s.i32()
            s.libs[oid] = s.string()
            return s.record()
        if t == 13:
            return ('null', s.u8())
        if t == 14:
            return ('null', s.i32())
        if t == 15:
            oid = s.i32()
            n = s.i32()
            pt = s.u8()
            arr = [s.prim(pt) for _ in range(n)]
            s.objects[oid] = arr
            return arr
        if t in (16, 17):
            oid = s.i32()
            n = s.i32()
            arr = s._arr(n)
            s.objects[oid] = arr
            return arr
        raise Exception('unknown record %d at %d' % (t, s.i - 1))


def parse(b):
    r = R(b)
    while r.i < len(b):
        v = r.record()
        r.records.append(v)
        if isinstance(v, tuple) and v and v[0] == 'end':
            break
    return r


def resolve(r, o, depth=0, maxd=12):
    if isinstance(o, tuple) and len(o) == 2 and o[0] == 'ref':
        if depth > maxd:
            return '<ref %d>' % o[1]
        return resolve(r, r.objects.get(o[1]), depth + 1, maxd)
    if isinstance(o, dict):
        if depth > maxd:
            return '<%s #%s>' % (o.get('__class'), o.get('__id'))
        return {k: resolve(r, v, depth + 1, maxd) for k, v in o.items()}
    if isinstance(o, list):
        if depth > maxd:
            return '<list %d>' % len(o)
        return [resolve(r, v, depth + 1, maxd) for v in o]
    return o
