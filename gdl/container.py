"""Extract and repack Extron GUI Designer .gdl containers.

A .gdl is a ZIP whose 4-byte record signatures read 'KP' instead of 'PK' -
its records', not the same bytes in its data (_records). Swapping those two
bytes back yields a normal archive holding 'ProjectGCP'
(the .NET BinaryFormatter authoring graph) and a '*.tgz4' member that is itself
a plain ZIP of the built panel payload (layout.json + N.png).

Usage:
    python -m gdl.container extract <file.gdl> <out_dir>
    python -m gdl.container pack    <template.gdl> <ProjectGCP> <out.gdl>
    python -m gdl.container payload <file.gdl> <out_dir>     # unpack the .tgz4 too
"""
import io
import os
import struct
import sys
import zipfile


def _records(raw, m):
    """Where a ZIP's records begin - its end of central directory record, each
    central directory header, each local header and each data descriptor -
    found as a ZIP reader finds them, from the end, with signatures starting
    `m` (b'PK' plain, b'KP' as GUI Designer writes them).

    Only these are signatures. The same four bytes can stand anywhere in a
    member's compressed data: the Turbulence 725 huddle's ProjectGCP holds
    KP 05 06 50 MB in, and swapping every occurrence in the file damaged 7
    bytes of a PNG in it, which read as a wrong CRC-32 on a panel GUI Designer
    had built whole."""
    eocd = raw.rfind(m + b'\x05\x06', max(0, len(raw) - 65557))
    if eocd < 0:
        raise zipfile.BadZipFile('no end of central directory record')
    count, start = struct.unpack('<H', raw[eocd + 10:eocd + 12])[0], struct.unpack('<I', raw[eocd + 16:eocd + 20])[0]
    out, at = [eocd], start
    for _ in range(count):
        if raw[at:at + 4] != m + b'\x01\x02':
            raise zipfile.BadZipFile(f'no central directory header at {at}')
        flags = struct.unpack('<H', raw[at + 8:at + 10])[0]
        csize = struct.unpack('<I', raw[at + 20:at + 24])[0]
        flen, xlen, clen = struct.unpack('<HHH', raw[at + 28:at + 34])
        local = struct.unpack('<I', raw[at + 42:at + 46])[0]
        if raw[local:local + 4] != m + b'\x03\x04':
            raise zipfile.BadZipFile(f'no local header at {local}')
        out += [at, local]
        if flags & 8:
            lf, lx = struct.unpack('<HH', raw[local + 26:local + 30])
            desc = local + 30 + lf + lx + csize
            if raw[desc:desc + 4] == m + b'\x07\x08':
                out.append(desc)
        at += 46 + flen + xlen + clen
    return out


def _resign(raw, frm, to):
    """A ZIP's bytes with its records' signatures turned from `frm` to `to` -
    b'KP' to b'PK' to read a .gdl, back to write one - and nothing else."""
    d = bytearray(raw)
    for at in _records(raw, frm):
        d[at:at + 2] = to
    return bytes(d)


def open_gdl_bytes(raw):
    """A .gdl (or .glt) held in memory, as a normal ZipFile. One whose records
    already read PK is read as it is."""
    try:
        raw = _resign(raw, b'KP', b'PK')
    except zipfile.BadZipFile:
        pass
    return zipfile.ZipFile(io.BytesIO(raw))


def open_gdl(path):
    """Return the outer container as a normal ZipFile."""
    with open(path, 'rb') as fh:
        return open_gdl_bytes(fh.read())


def payload_name(z, required=True):
    """The built-panel member, or None when the container has none.

    Extron's own `.glt` templates carry ONLY a ProjectGCP - they are design
    libraries, never built - and so does a `.gdl` that GUI Designer saved
    without building. Both are legitimate, so a caller that can cope with the
    absence asks for `required=False` rather than catching StopIteration.
    """
    name = next((n for n in z.namelist() if n != 'ProjectGCP'), None)
    if name is None and required:
        raise ValueError(
            'this container holds only a ProjectGCP, with no built payload. '
            'That is normal for a .glt template and for a .gdl saved without '
            'building; open it in GUI Designer and use File > Save and Build.')
    return name


def open_payload(path):
    """Return the inner built-panel ZIP (layout.json + N.png)."""
    z = open_gdl(path)
    return zipfile.ZipFile(io.BytesIO(z.read(payload_name(z))))


def pack(template, gcp_bytes, dest, payload_bytes=None, name=None):
    """Write a .gdl from a ProjectGCP, reusing a template's payload by default.

    GUI Designer regenerates the payload on its next Build, so carrying the
    template's stale one across is fine for a project you intend to open.

    When the template has no payload to carry - an Extron `.glt`, or a project
    saved without building - the result is written with just a ProjectGCP. GUI
    Designer opens that and builds it; the payload is its output, not its
    input. This is what lets a panel be authored from Extron's own templates
    instead of from somebody's client project.
    """
    src = open_gdl(template)
    name = name or payload_name(src, required=False)
    if payload_bytes is None and name is not None:
        payload_bytes = src.read(name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('ProjectGCP', gcp_bytes)
        if name is not None and payload_bytes is not None:
            z.writestr(name, payload_bytes)
    with open(dest, 'wb') as fh:
        fh.write(_resign(buf.getvalue(), b'PK', b'KP'))
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
