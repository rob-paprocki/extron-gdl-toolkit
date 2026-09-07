"""Pull the embedded font binaries out of a .gdl's ProjectGCP member.

layout.json's NonDefaultFontResources names each face and gives its exact byte
length; the bytes themselves live in the .NET BinaryFormatter graph beside the
project. Scanning for sfnt table directories and measuring each font from its
own table offsets recovers them exactly, so a renderer never has to depend on
the fonts being installed on the machine.
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


def extract(gcp, resources):
    """Map each declared font resource to its bytes, matching on exact size."""
    found = scan(gcp)
    by_len = {}
    for off, n in found.items():
        by_len.setdefault(n, []).append(off)
    out = {}
    for r in resources:
        name, size = r.get('EmbeddedFileName'), r.get('Size')
        offs = by_len.get(size)
        if not offs:
            continue
        blob = gcp[offs[0]:offs[0] + size]
        out[name] = {
            'family': (r.get('FamilyName') or [r.get('WindowsFamilyName')])[0],
            'style': r.get('WindowsStyleName'),
            'bytes': blob,
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
        # Arial and Arial Black are system faces; GUI Designer references them
        # without embedding, so they are expected here.
        print('  not embedded (system fonts):', ', '.join(absent))
