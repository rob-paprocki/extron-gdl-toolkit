"""Extract layer names from a PSD without loading pixel data.

Scans the layer-and-mask section for 'luni' (Unicode layer name) additional
layer-info blocks: 4-byte '8BIM', 4-byte 'luni', 4-byte length, then a
4-byte character count and UTF-16BE text. Heuristic but reliable, and it
avoids parsing every layer record in a 222 MB file.
"""
import struct
import sys

path = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 400

with open(path, 'rb') as fh:
    sig, ver = struct.unpack('>4sH', fh.read(6))
    assert sig == b'8BPS', sig
    fh.read(6)
    channels, height, width, depth, mode = struct.unpack('>HIIHH', fh.read(14))
    print(f'PSD v{ver}  {width}x{height}  channels={channels} depth={depth} mode={mode}')
    cm = struct.unpack('>I', fh.read(4))[0]
    fh.seek(cm, 1)
    ir = struct.unpack('>I', fh.read(4))[0]
    fh.seek(ir, 1)
    lm_len = struct.unpack('>I', fh.read(4))[0] if ver == 1 else struct.unpack('>Q', fh.read(8))[0]
    print(f'layer+mask section: {lm_len:,} bytes')
    blob = fh.read(min(lm_len, 120 * 1024 * 1024))

names, i = [], 0
while True:
    i = blob.find(b'8BIMluni', i)
    if i < 0:
        break
    try:
        ln = struct.unpack('>I', blob[i + 8:i + 12])[0]
        cnt = struct.unpack('>I', blob[i + 12:i + 16])[0]
        raw = blob[i + 16:i + 16 + cnt * 2]
        names.append(raw.decode('utf-16-be', 'replace'))
    except Exception:
        pass
    i += 8

print(f'layer names found: {len(names)}')
seen = set()
shown = 0
for n in names:
    n = n.strip()
    if not n or n in seen:
        continue
    seen.add(n)
    print('   ', n)
    shown += 1
    if shown >= limit:
        print(f'   ... ({len(names)} total)')
        break
