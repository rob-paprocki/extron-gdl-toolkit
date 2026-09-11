"""Pull the embedded font binaries out of a .gdl's ProjectGCP member.

layout.json's NonDefaultFontResources names each face and gives its on-disk file
size; the bytes themselves live in the .NET BinaryFormatter graph beside the
project. Scanning for sfnt table directories locates each font, and slicing the
declared size from there recovers the original file, so a renderer never has to
depend on the fonts being installed on the machine.

**Every declared face is embedded, Arial included.** An earlier version matched
the declared size against `sfnt_length` exactly, which silently dropped any face
whose file carries bytes past the far edge of its last table - 28 for Arial 5.10,
30 for Arial Black 5.06. Those two were then written off as uninstallable system
faces, which put a hard `LookupError` in the render path on any host without
Arial. They were in the fixture the whole time.
"""
import os
import struct
import sys

from .container import open_gdl, open_payload

SFNT = (b'\x00\x01\x00\x00', b'OTTO', b'true', b'ttcf')


def sfnt_length(buf, off):
    """Length of the sfnt at `off`, from the far edge of its table directory."""
    if off + 12 > len(buf):
        return None
    num = struct.unpack('>H', buf[off + 4:off + 6])[0]
    if not 1 <= num <= 512 or off + 12 + num * 16 > len(buf):
        return None
    end = 12 + num * 16
    for i in range(num):
        rec = off + 12 + i * 16
        t_off, t_len = struct.unpack('>II', buf[rec + 8:rec + 16])
        if t_off > len(buf) or t_len > len(buf):
            return None
        end = max(end, t_off + t_len)
    return end if off + end <= len(buf) else None


def scan(buf):
    """Every sfnt found in the blob, as {offset: length}."""
    out = {}
    for magic in SFNT:
        i = buf.find(magic)
        while i != -1:
            n = sfnt_length(buf, i)
            if n and n > 4096:
                out[i] = n
            i = buf.find(magic, i + 1)
    return out


# A declared file size can exceed the measured sfnt length, because the file may
# carry bytes after its last table. Measured across the six fixtures and Extron's
# 44 installed templates the overhang is 0 (both OTFs, and the Extron icon TTFs),
# 28 (Arial) or 30 (Arial Black); 64 leaves room without letting a face match the
# wrong blob, since the smallest gap between two embedded faces is ~33 KB.
SIZE_SLACK = 64


def extract(gcp, resources):
    """Map each declared font resource to its bytes.

    Anchors on the sfnt header nearest the declared size and slices `Size` bytes
    from it, so the recovered file is byte-identical to the one GUI Designer
    embedded - which is the one it rasterized the ground-truth snapshots with.
    """
    found = scan(gcp)
    out = {}
    used = set()
    for r in resources:
        name, size = r.get('EmbeddedFileName'), r.get('Size')
        if not name or not size:
            continue
        # Prefer an exact length match, then the closest under-measure.
        cands = sorted((size - n, off) for off, n in found.items()
                       if off not in used
                       and 0 <= size - n <= SIZE_SLACK
                       and off + size <= len(gcp))
        if not cands:
            continue
        off = cands[0][1]
        used.add(off)
        out[name] = {
            'family': (r.get('FamilyName') or [r.get('WindowsFamilyName')])[0],
            'style': r.get('WindowsStyleName'),
            'bytes': gcp[off:off + size],
        }
    return out


if __name__ == '__main__':
    import json as _json

    src = sys.argv[1]
    dest = sys.argv[2] if len(sys.argv) > 2 else None
    container = open_gdl(src)
    layout = _json.loads(open_payload(src).read('layout.json'))
    found = extract(container.read('ProjectGCP'), layout.get('NonDefaultFontResources') or [])
    for name, face in found.items():
        print(f"  {face['family']:<24} {face['style'] or '':<10} {len(face['bytes']):>8} B  {name}")
        if dest:
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, name), 'wb') as fh:
                fh.write(face['bytes'])
    absent = [r['EmbeddedFileName'] for r in (layout.get('NonDefaultFontResources') or [])
              if r.get('EmbeddedFileName') not in found]
    if absent:
        # Not expected: every face a project declares has been embedded in every
        # file looked at so far. Treat this as a finding, not as normal output.
        print('  DECLARED BUT NOT FOUND:', ', '.join(absent))
