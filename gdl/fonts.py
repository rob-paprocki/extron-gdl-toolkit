"""Pull the embedded font binaries out of a .gdl's ProjectGCP member.

layout.json's NonDefaultFontResources names each face and gives its on-disk file
size; the bytes themselves live in the .NET BinaryFormatter graph beside the
project. Scanning for sfnt table directories locates each font, and slicing the
declared size from there recovers the original file, so a renderer never has to
depend on the fonts being installed on the machine.

What a project carries is also in its own records: each PBFontResource holds its
face in `dataField`. `carried()` reads those - from a .glt template too, which
declares nothing - and `match()` pairs each declaration with one of them.

**Arial is embedded, and so is every face the fixtures declare.** An earlier
version matched the declared size against `sfnt_length` exactly, which silently
dropped any face whose declared size runs past the far edge of its last table -
28 bytes for Arial 5.10, 30 for Arial Black 5.06. Those two were then written off
as uninstallable system faces, which put a hard `LookupError` in the render path
on any host without Arial. They were in the fixture the whole time. A project
can still declare a face it does not embed: gdl/fonts/README.md has which.
"""
import os
import struct
import sys

from .container import open_gdl, open_payload

SFNT = (b'\x00\x01\x00\x00', b'OTTO', b'true', b'ttcf')

# Where the faces are recovered to, and the file each family is recovered as.
# The renderer draws in these (gdl/compose.py) and a spec's icons read their
# glyph names out of them (gdl/spec.py), which must not need Pillow - so the
# table is here.
FONTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')

# family + bold/italic -> the actual binary
FILES = {
    ('Arial', 0, 0): 'arial.ttf', ('Arial', 1, 0): 'arialbd.ttf',
    ('Arial', 0, 1): 'ariali.ttf', ('Arial', 1, 1): 'arialbi.ttf',
    ('Arial Black', 0, 0): 'ariblk.ttf',
    ('Open Sans', 0, 0): 'opensans-regular.ttf',
    ('Open Sans Light', 0, 0): 'opensans-light.ttf',
    ('Forma DJR Display', 0, 0): 'formadjrdisplay-regular_1.otf',
    ('Extron-Afterburn', 0, 0): 'afterburn_modified.ttf',
    ('Crestron General', 0, 0): 'crestron_general.ttf',
    ('Extron GUIC Video Conference 1', 0, 0): 'extron_guic_video_conference_1.ttf',
    # The icon faces the other theme seeds set their glyphs in, as they embed
    # them: the Mach seeds' Extron-Lift, the Shockwave seeds' Extron-Shockwave
    # and their Video Conference face.
    ('Extron-Lift', 0, 0): 'extron-lift_8.ttf',
    ('Extron-Shockwave', 0, 0): 'extron_shockwave.ttf',
    ('Extron GUIC Video Conference 1a', 0, 0): 'extron_guic_video_conference_1a.ttf',
}
# Some faces are embedded under different EmbeddedFileNames in different
# projects: the _alt fixtures ship Afterburn as extron_-_afterburn_1a.ttf, and
# the Afterburn 320 seed as afterburn.ttf - a build of its own, whose glyphs sit
# at the same codepoints under the same names, each drawn 6% of an em higher
# (docs/design-rules.md section 6). Miss these and the face silently falls back
# to Arial, which is easy not to notice.
ALIASES = {
    'afterburn_modified.ttf': ['extron_-_afterburn_1a.ttf', 'afterburn.ttf'],
    # The system faces ship under Windows 8.3-ish names on Windows and spelled-out
    # ones on macOS. Without these, every Arial variant quietly resolves to plain
    # Arial off Windows - the bold and the black would render as regular.
    'arial.ttf': ['Arial.ttf'],
    'arialbd.ttf': ['Arial Bold.ttf'],
    'ariali.ttf': ['Arial Italic.ttf'],
    'arialbi.ttf': ['Arial Bold Italic.ttf'],
    'ariblk.ttf': ['Arial Black.ttf'],
}


def face_path(family, bold=0, italic=0, fontdir=None):
    """The recovered file a face is in, or None: under its own name, then any
    other it is embedded as. The host's fonts are not searched - the renderer
    does that, as a fallback it reports (gdl.compose.face)."""
    fontdir = fontdir or FONTDIR
    primary = FILES.get((family, bold, italic)) or FILES.get((family, 0, 0))
    for fn in [primary] + ALIASES.get(primary or '', []):
        if fn and os.path.exists(os.path.join(fontdir, fn)):
            return os.path.join(fontdir, fn)
    return None


# The face each theme's own template sets its glyph captions in - a spec's
# `icon` is drawn in it when its control names no font (gdl.spec): Afterburn's
# 60 captions in Extron-Afterburn, Mach's 112 in Extron-Lift, Shockwave's 98 in
# Extron-Shockwave (sixteen glyphs at U+00B0-U+00BF, outside the Private Use
# Area), counted on the 1035 seeds. Turbulence's template draws its icons as
# images, bar two glyphs in symbol faces of their own (docs/design-rules.md
# section 6), so it has none for an icon to default to.
ICON_FONTS = {'Afterburn': 'Extron-Afterburn', 'Mach': 'Extron-Lift',
              'Shockwave': 'Extron-Shockwave', 'Turbulence': None}
_SEEDED = {}


def seed_face(font):
    """(bytes, seed) of a face read straight out of a seed, or (None, None): an
    icon face out of its family's 1035 seed, the build its glyphs were measured
    in, and any other face - Roboto, Extron GUI Configurator, Extron GUIC Video
    Conference 1a, which no fixture carries - out of the first seed that
    carries it (find_face). Read, never recovered: recovering a Mach or
    Shockwave seed into gdl/fonts/ also replaces the Monotype Arial the render
    baseline is scored in with the Windows Arial those seeds embed
    (gdl/fonts/README.md)."""
    if font not in _SEEDED:
        from . import seeds
        family = next((k for k, f in ICON_FONTS.items() if f and f == font), None)
        seed = f'seeds/{family} 1035.gdl' if family else None
        got = (None, None)
        if seed and seeds.usable(seed):
            face = next((f for f in _carried_by(seeds.path(seed)) if f['family'] == font), None)
            if face:
                got = (face['bytes'], seed)
        if got == (None, None):
            face = find_face(font)
            # find_face matches a family whatever its case; a face is drawn
            # in the family it is asked for by name, as GUI Designer does.
            if face and face['family'] == font:
                got = (face['bytes'], face['carrier'])
        _SEEDED[font] = got
    return _SEEDED[font]


def icon_face(font):
    """(bytes, where from) of a face, or (None, None): the file recovered into
    gdl/fonts/, else a seed's (seed_face)."""
    path = face_path(font)
    if path:
        with open(path, 'rb') as fh:
            return fh.read(), path
    return seed_face(font)


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
            # Faces under 2 KB are not looked for: a table directory's magic
            # numbers turn up in image data. Extron-Shockwave, the smallest face
            # in the corpus, is 3,736 bytes, and a floor of 4 KB lost it.
            if n and n > 2048:
                out[i] = n
            i = buf.find(magic, i + 1)
    return out


# A declared file size can exceed the measured sfnt length: it can run past the
# last table, and past what the project embeds. Measured across the six fixtures
# and Extron's 50 installed templates the overhang is 0 (both OTFs, and the
# Extron icon TTFs), 28 (Arial) or 30 (Arial Black); 64 leaves room without
# letting a face match the wrong blob, since the smallest gap between two
# embedded faces is ~33 KB.
SIZE_SLACK = 64


def _locate(gcp, resources):
    """Where each declared resource's face starts in the stream, or None, in
    declaration order.

    Anchors on the sfnt header nearest the declared size, one face to a
    declaration. Sliced `Size` bytes from there, that is, for every face but
    the two System defaults, exactly the array GUI Designer embedded - the one
    it rasterized the ground-truth snapshots with. Arial and Arial Black declare
    a size 28 bytes past their array - the array ends at Arial's last table and
    two bytes after Arial Black's, which declare 28 and 30 past it - so each
    comes back followed by 28 bytes of the stream's next records.
    """
    found = scan(gcp)
    out = []
    used = set()
    for r in resources:
        name, size = r.get('EmbeddedFileName'), r.get('Size')
        if not name or not size:
            out.append(None)
            continue
        # Prefer an exact length match, then the closest under-measure.
        cands = sorted((size - n, off) for off, n in found.items()
                       if off not in used
                       and 0 <= size - n <= SIZE_SLACK
                       and off + size <= len(gcp))
        if not cands:
            out.append(None)
            continue
        off = cands[0][1]
        used.add(off)
        out.append(off)
    return out


def _face_arrays(gcp):
    """{offset: length} of every face the stream carries, without parsing it.

    scan() finds an sfnt header anywhere, and \\x00\\x01\\x00\\x00 turns up all
    through a project - 21 in the client fixture's stream, for 4 faces. A
    carried face is a resource's dataField, which BinaryFormatter writes as a
    byte array: record type 15, an int32 object id, an int32 length, primitive
    type 2 (Byte), then the bytes. Read that way, the count is each project's
    carried() exactly - 4, 3, 6, 8 and 5 faces in the fixture and the Afterburn,
    Mach, Shockwave and Turbulence 1035 seeds."""
    out = {}
    for magic in SFNT:
        i = gcp.find(magic)
        while i != -1:
            if i >= 10 and gcp[i - 10] == 0x0F and gcp[i - 1] == 0x02:
                n = struct.unpack('<i', gcp[i - 5:i - 1])[0]
                if 12 <= n <= len(gcp) - i:
                    out[i] = n
            i = gcp.find(magic, i + 1)
    return out


def extract_each(gcp, resources):
    """Each declared font resource's bytes, or None, in declaration order.

    extract() keys its answer by file name, and a project can declare one name
    twice (gdl/fonts/README.md): whether each declaration came back is this."""
    return [None if off is None else gcp[off:off + r['Size']]
            for r, off in zip(resources, _locate(gcp, resources))]


def extract(gcp, resources):
    """Map each declared font resource's file name to its face (_locate has
    how it is found). A name declared twice keeps the later."""
    out = {}
    for r, data in zip(resources, extract_each(gcp, resources)):
        if data is None:
            continue
        out[r['EmbeddedFileName']] = {
            'family': (r.get('FamilyName') or [r.get('WindowsFamilyName')])[0],
            'style': r.get('WindowsStyleName'),
            'bytes': data,
        }
    return out


def carried(project):
    """Every face a project or template carries, as its own records hold it.

    layout.json declares faces by file name and size, and a project can declare
    one it does not carry, or one file name twice with one of the two carried
    (gdl/fonts/README.md has which). Each PBFontResource is the project's own
    record of a face it carries: `dataField` is the face exactly as embedded -
    Arial and Arial Black each 28 bytes short of their declared size, which
    extract() comes back 28 bytes longer than - and it is there with no file
    name at all on some resources (the Mach 1035 seed's Arial Black). It needs
    no layout.json, so a .glt template, which has none, is read the same way.

    `project` is a path, or an open gdl.project.Project. Each face is
    {family, style, file, source, size, default, author, bytes}: `file` is the
    resource's embedded file name - None or empty where it names none, as the
    fixtures' Arial Black does - `source` the base name of the file it was added
    from or None, `size` the size it declares, `author` its ResourceAuthorEnum:
    0 where GUI Designer supplied the face, 1 where it was added from a file.
    """
    from .project import Project
    p = Project.open(os.fspath(project)) if isinstance(project, (str, os.PathLike)) else project
    out = []
    for r in p.instances('PBFontResource'):
        data = p.field(r, 'dataField')
        if not data:
            continue
        source = p.field(r, 'filenameField')
        author = p.field(r, 'authorField')
        out.append({'family': p.field(r, 'windowsFamilyNameField'),
                    'style': p.field(r, 'windowsStyleNameField'),
                    'file': p.field(r, 'embeddedFileNameField'),
                    'source': (source.replace('\\', '/').rsplit('/', 1)[-1]
                               if isinstance(source, str) and source else None),
                    'size': p.field(r, 'sizeField'),
                    # A face GUI Designer supplies itself - Arial Black, whose
                    # resource a build can add, though not always - is a
                    # default, with no file names.
                    'default': bool(p.field(r, 'mIsDefault')),
                    'author': author.get('value__') if isinstance(author, dict) else author,
                    'bytes': bytes(data)})
    return out


def match(declared, faces):
    """Each declaration's carried face, or None, in declaration order.

    One face per declaration, never two declarations to one face, by the rule
    extract() matches a blob with: the face's length at most SIZE_SLACK under
    the declared size, an exact one first. A file name is not the key - one
    project declares arial.ttf twice, at two sizes, and carries one of them.
    """
    used = set()
    out = []
    for r in declared:
        size = r.get('Size') or 0
        cands = sorted((size - len(f['bytes']), i) for i, f in enumerate(faces)
                       if i not in used and 0 <= size - len(f['bytes']) <= SIZE_SLACK)
        if not cands:
            out.append(None)
            continue
        used.add(cands[0][1])
        out.append(faces[cands[0][1]])
    return out


_FOUND = {}
_CARRIED = {}


def _carried_by(path):
    """carried(path), parsed once per file (and per edit of it): a seed is one
    to five seconds to parse, and an icon face and a face find_face looks for
    are often in the same one."""
    key = (os.path.abspath(path), os.path.getmtime(path))
    if key not in _CARRIED:
        _CARRIED[key] = carried(path)
    return _CARRIED[key]


def find_face(family):
    """A face one of seeds/ carries, by family - {family, style, file, source,
    size, default, author, bytes, carrier}, `carrier` the seed's repo-relative
    path - or None. The family is matched whatever its case, so the caller
    compares the spelling.

    For a donor that defines no resource for a family a spec names: the
    applier appends a clone of the donor's own font resource filled with this
    (Add-GdlFontResource). The first seed in name order that carries it, and
    only that one is parsed - one to five seconds - for the record of the face
    (carried). Which seeds declare the family their layout.json says, and
    whether one carries a face of the size it declares its stream does
    (_face_arrays): every Afterburn seed declares Arial Black and carries none,
    and parsing each to find that out was a minute."""
    if not isinstance(family, str):
        return None
    want = family.casefold()
    if want in _FOUND:
        return _FOUND[want]
    import json as _json
    import zipfile
    from . import seeds
    got = None
    for name in seeds.here():
        path = seeds.path(name)
        if not seeds.usable(path):
            continue
        try:
            declared = [r for r in _json.loads(open_payload(path).read('layout.json'))
                        .get('NonDefaultFontResources') or []
                        if want in {n.casefold() for n in (r.get('FamilyName') or [])
                                    + [r.get('WindowsFamilyName')] if isinstance(n, str)}]
            if not declared:
                continue
            arrays = _face_arrays(open_gdl(path).read('ProjectGCP')).values()
            if not any(0 <= (r.get('Size') or 0) - n <= SIZE_SLACK for r in declared for n in arrays):
                continue
            faces = _carried_by(path)
        except (KeyError, OSError, ValueError, zipfile.BadZipFile):
            continue
        face = next((f for f in faces if (f['family'] or '').casefold() == want and f['bytes']),
                    None)
        if face:
            got = dict(face, carrier=os.path.relpath(path, seeds.REPO).replace('\\', '/'))
            break
    _FOUND[want] = got
    return got


# The two System faces GUI Designer supplies itself, by the names a built
# project's layout.json declares them under - which is what the renderer looks a
# face up by. A template's own resources for them name no file.
_SYSTEM = {('Arial', 'Regular'): 'arial.ttf', ('Arial Black', 'Black'): 'ariblk.ttf'}


def _file_name(face):
    """Where a carried face is written when nothing declares it: its own
    embedded file name, else GUI Designer's name for a System face, else its
    source file's, lower-cased as GUI Designer embeds them, else its family and
    style."""
    if face['file']:
        return face['file']
    if (face['family'], face['style']) in _SYSTEM:
        return _SYSTEM[(face['family'], face['style'])]
    if face['source']:
        return face['source'].lower()
    return f"{face['family']}-{face['style']}.ttf".replace(' ', '').lower()


def _write(dest, name, data):
    if dest:
        os.makedirs(dest, exist_ok=True)
        with open(os.path.join(dest, name), 'wb') as fh:
            fh.write(data)


USAGE = 'python -m gdl.fonts <project.gdl or template.glt> [dest]'


def _say(family, style, data, name, note=''):
    print(f"  {family or '':<24} {style or '':<10} {len(data):>8} B  {name}{note}")


def main(argv):
    """A built project: every face its layout.json declares, recovered as
    extract() finds it; then each declaration it does not carry, and each face
    it carries that nothing declares. A template, or a project never built, has
    no layout.json: every face it carries."""
    import json as _json
    if len(argv) < 2:
        print(USAGE)
        return 2
    src = argv[1]
    dest = argv[2] if len(argv) > 2 else None
    try:
        layout = _json.loads(open_payload(src).read('layout.json'))
    except (KeyError, OSError, ValueError):
        layout = None
    if layout is None:
        for face in carried(src):
            name = _file_name(face)
            _say(face['family'], face['style'], face['bytes'], name)
            _write(dest, name, face['bytes'])
        return 0
    declared = [r for r in layout.get('NonDefaultFontResources') or [] if r.get('EmbeddedFileName')]
    gcp = open_gdl(src).read('ProjectGCP')
    offs = _locate(gcp, declared)
    each = [None if off is None else gcp[off:off + r['Size']] for r, off in zip(declared, offs)]
    for r, data in zip(declared, each):
        if data is not None:
            _say((r.get('FamilyName') or [r.get('WindowsFamilyName')])[0],
                 r.get('WindowsStyleName'), data, r['EmbeddedFileName'])
            _write(dest, r['EmbeddedFileName'], data)
    if None not in offs and set(offs) == set(_face_arrays(gcp)):
        # Every declaration is in the stream at its size, and every face the
        # stream carries is one of them, so there is nothing to say either way
        # and the project is not parsed: that takes 40 s on a 65 MB seed, and
        # it was the whole cost of this command over the fixtures.
        return 0
    faces = carried(src)
    pairs = match(declared, faces)
    for r, data, face in zip(declared, each, pairs):
        if data is None and face is not None:
            # Carried, and the stream scan missed it - a face under scan()'s
            # floor, or one sfnt_length() cannot measure. Its resource holds
            # it, so it is recovered from there, and said.
            _say(face['family'], face['style'], face['bytes'], r['EmbeddedFileName'],
                 ' - from its resource; the stream scan missed it')
            _write(dest, r['EmbeddedFileName'], face['bytes'])
    absent = [f"{r['EmbeddedFileName']} ({r['Size']:,} B)"
              for r, face in zip(declared, pairs) if face is None]
    if absent:
        # Normal for a fresh File > New project, which declares faces such as
        # Arial Black and defines no resource for them - a build can add one,
        # but does not always. The
        # renderer does not need a seed to carry it: gdl/fonts/ holds it,
        # recovered from the fixtures. These are the declarations this file
        # carries nothing for, each on its own - gdl/fonts/README.md has which.
        print('  DECLARED, NOT CARRIED:', ', '.join(absent))
    matched = {id(face) for face in pairs if face is not None}
    extra = [f"{face['family']} {face['style']} ({len(face['bytes']):,} B)"
             for face in faces if id(face) not in matched]
    if extra:
        # A face the project carries under a declaration of a different size,
        # or none: Turbulence's Windows Arial, under a resource with no file
        # name, beside a declaration of the Monotype one.
        print('  CARRIED, NOT DECLARED:', ', '.join(extra))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
