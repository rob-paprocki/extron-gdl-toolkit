"""Extract and repack Extron GUI Designer .gdl containers.

A .gdl is a ZIP whose 4-byte record signatures read 'KP' instead of 'PK'.
Swapping those two bytes back yields a normal archive holding 'ProjectGCP'
(the .NET BinaryFormatter authoring graph) and a '*.tgz4' member that is itself
a plain ZIP of the built panel payload (layout.json + N.png).

Usage:
    python -m gdl.container extract <file.gdl> <out_dir>
    python -m gdl.container pack    <template.gdl> <ProjectGCP> <out.gdl>
    python -m gdl.container payload <file.gdl> <out_dir>     # unpack the .tgz4 too
"""
import io
import os
import sys
import zipfile

MANGLED = (b'KP\x03\x04', b'KP\x01\x02', b'KP\x05\x06', b'KP\x07\x08')
NORMAL = (b'PK\x03\x04', b'PK\x01\x02', b'PK\x05\x06', b'PK\x07\x08')


def _swap(raw, sigs, to):
    d = bytearray(raw)
    for s in sigs:
        i = d.find(s)
        while i != -1:
            d[i:i + 2] = to
            i = d.find(s, i + 1)
    return bytes(d)


def open_gdl(path):
    """Return the outer container as a normal ZipFile."""
    with open(path, 'rb') as fh:
        return zipfile.ZipFile(io.BytesIO(_swap(fh.read(), MANGLED, b'PK')))


def payload_name(z):
    return next(n for n in z.namelist() if n != 'ProjectGCP')


def open_payload(path):
    """Return the inner built-panel ZIP (layout.json + N.png)."""
    z = open_gdl(path)
    return zipfile.ZipFile(io.BytesIO(z.read(payload_name(z))))


def pack(template, gcp_bytes, dest, payload_bytes=None, name=None):
    """Write a .gdl from a ProjectGCP, reusing a template's payload by default.

    GUI Designer regenerates the payload on its next Build, so carrying the
    template's stale one across is fine for a project you intend to open.
    """
    src = open_gdl(template)
    name = name or payload_name(src)
    payload_bytes = payload_bytes if payload_bytes is not None else src.read(name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('ProjectGCP', gcp_bytes)
        z.writestr(name, payload_bytes)
    with open(dest, 'wb') as fh:
        fh.write(_swap(buf.getvalue(), NORMAL, b'KP'))
    return dest


def _dump(z, out):
    os.makedirs(out, exist_ok=True)
    for info in z.infolist():
        p = os.path.join(out, info.filename.replace('/', '_'))
        with open(p, 'wb') as fh:
            fh.write(z.read(info))
        print(f'  {info.file_size:>10,}  {info.filename}')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'extract':
        _dump(open_gdl(sys.argv[2]), sys.argv[3])
    elif cmd == 'payload':
        _dump(open_payload(sys.argv[2]), sys.argv[3])
    elif cmd == 'pack':
        with open(sys.argv[3], 'rb') as fh:
            gcp = fh.read()
        out = pack(sys.argv[2], gcp, sys.argv[4])
        print(f'  wrote {out}  {os.path.getsize(out):,} bytes')
    else:
        sys.exit(__doc__)
