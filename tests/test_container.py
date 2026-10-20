"""Containers that hold only a ProjectGCP are legitimate, and must round-trip.

`payload_name` used to be `next(n for n in ... )`, so a container with no built
payload raised a bare `StopIteration` from inside a generator - which is what
`gdl.fonts` did against every one of Extron's templates. And `pack` unpacked
that name unconditionally, so it could not write a project that had never been
built.

Both cases are normal:

  * a `.glt` template is a library of pages, popups and resources, never built;
  * a `.gdl` that GUI Designer saved without building drops its stale payload.

GUI Designer opens either and builds it. The payload is Build's output, not its
input.
"""
import glob
import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import MAIN_CLIENT, needs_client  # noqa: E402

from gdl.container import open_gdl, pack, payload_name  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, '..', 'fixtures', 'gdl',
                       'client-boardroom-2.0.0.gdl')
sys.path.insert(0, HERE)
from _corpus import TEMPLATES_DIR as TEMPLATES  # noqa: E402


def write_bare(path, gcp=b'stand-in graph'):
    """A container holding only a ProjectGCP, in the KP-swapped on-disk form."""
    from gdl.container import _resign
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('ProjectGCP', gcp)
    with open(path, 'wb') as fh:
        fh.write(_resign(buf.getvalue(), b'PK', b'KP'))
    return path


class TestPayloadName(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.d = tempfile.mkdtemp()

    @needs_client(MAIN_CLIENT)
    def test_a_built_gdl_reports_its_payload(self):
        self.assertTrue(payload_name(open_gdl(FIXTURE)).endswith('.tgz4'))

    def test_a_payloadless_container_returns_none_when_optional(self):
        bare = write_bare(os.path.join(self.d, 'bare.gdl'))
        self.assertIsNone(payload_name(open_gdl(bare), required=False))

    def test_it_raises_a_useful_error_when_required(self):
        bare = write_bare(os.path.join(self.d, 'bare.gdl'))
        with self.assertRaises(ValueError) as cm:
            payload_name(open_gdl(bare))
        # Not StopIteration, and it must say what to do about it.
        self.assertIn('only a ProjectGCP', str(cm.exception))
        self.assertIn('Save and Build', str(cm.exception))


class TestPackWithoutAPayload(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.d = tempfile.mkdtemp()

    def test_packing_from_a_payloadless_template_keeps_only_the_gcp(self):
        bare = write_bare(os.path.join(self.d, 'template.gdl'))
        out = pack(bare, b'a new graph', os.path.join(self.d, 'out.gdl'))
        z = open_gdl(out)
        self.assertEqual(z.namelist(), ['ProjectGCP'])
        self.assertEqual(z.read('ProjectGCP'), b'a new graph')

    @needs_client(MAIN_CLIENT)
    def test_packing_from_a_built_donor_still_carries_the_payload(self):
        out = pack(FIXTURE, b'a new graph', os.path.join(self.d, 'out.gdl'))
        z = open_gdl(out)
        self.assertEqual(len(z.namelist()), 2)
        self.assertEqual(z.read('ProjectGCP'), b'a new graph')
        # the donor's built payload, carried across unchanged
        self.assertEqual(z.read(payload_name(z)),
                         open_gdl(FIXTURE).read(payload_name(open_gdl(FIXTURE))))


@unittest.skipUnless(os.path.isdir(TEMPLATES), 'GUI Designer templates not installed')
class TestExtronTemplates(unittest.TestCase):
    """The templates are the reason payload_name had to stop raising."""

    def test_every_template_holds_only_a_projectgcp(self):
        files = sorted(glob.glob(os.path.join(TEMPLATES, '*.glt')))
        self.assertTrue(files, 'no templates found')
        for f in files:
            z = open_gdl(f)
            self.assertEqual(z.namelist(), ['ProjectGCP'], os.path.basename(f))
            self.assertIsNone(payload_name(z, required=False))


def stored(members):
    """A plain ZIP's bytes, every member stored as it is - so a member's data
    holds whatever bytes it was given, signatures included."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as z:
        for name, data in members:
            z.writestr(name, data)
    return buf.getvalue()


class TestSignatures(unittest.TestCase):
    """A .gdl's ZIP records read KP for PK - and only its records: a member's
    compressed data can hold the same four bytes by chance. Swapping every
    occurrence in the file, as gdl.container once did, reached into the
    Turbulence 725 huddle's ProjectGCP - a KP 05 06 50 MB in - damaged 7 bytes
    of a PNG in it, and read as a wrong CRC-32: the verifier stopped on a panel
    GUI Designer had built whole."""

    # Every record signature, each way, inside a member's data.
    DATA = b'graph ' + b''.join(m + s for m in (b'KP', b'PK')
                                for s in (b'\x03\x04', b'\x01\x02', b'\x05\x06', b'\x07\x08')) + b' end'

    def test_the_records_are_the_archives_own(self):
        """Its end of central directory record, and each member's central
        directory header and local header - and not the bytes in its data."""
        from gdl.container import _records
        raw = stored([('ProjectGCP', self.DATA), ('x.tgz4', self.DATA)])
        z = zipfile.ZipFile(io.BytesIO(raw))
        want = {raw.rindex(b'PK\x05\x06'), z.start_dir}
        want |= {i.header_offset for i in z.infolist()}
        want.add(raw.index(b'PK\x01\x02', z.start_dir + 4))
        self.assertEqual(sorted(_records(raw, b'PK')), sorted(want))

    def test_a_signature_in_a_members_data_is_read_as_it_was_written(self):
        from gdl.container import _resign, open_gdl_bytes
        gdl = _resign(stored([('ProjectGCP', self.DATA), ('x.tgz4', b'payload')]), b'PK', b'KP')
        # Written: the records mangled, the data as it was.
        self.assertEqual(gdl.count(self.DATA), 1)
        self.assertEqual(open_gdl_bytes(gdl).read('ProjectGCP'), self.DATA)

    def test_a_container_written_plain_is_read_as_it_is(self):
        """A ZIP whose records already read PK - no mangling to undo."""
        from gdl.container import open_gdl_bytes
        self.assertEqual(open_gdl_bytes(stored([('ProjectGCP', self.DATA)])).read('ProjectGCP'), self.DATA)

    def test_packing_leaves_the_data_alone(self):
        """pack() mangles the records it writes and nothing else. Deflate
        stores bytes it cannot compress as they are, so a payload's own
        signatures reach the file - a seed's, among its PNGs - and the old
        pack(), which swapped every one, wrote payloads that failed their
        CRC."""
        import random
        import tempfile
        rnd = random.Random(35)

        def noise(n):
            return bytes(rnd.getrandbits(8) for _ in range(n))
        payload = (noise(2000) + b'PK\x03\x04' + noise(1000) + b'PK\x01\x02' + noise(500)
                   + b'PK\x05\x06' + noise(100))
        with tempfile.TemporaryDirectory() as d:
            template = write_bare(os.path.join(d, 't.gdl'))
            out = pack(template, b'a new graph', os.path.join(d, 'out.gdl'), payload_bytes=payload, name='x.tgz4')
            with open(out, 'rb') as fh:
                raw = fh.read()
            for sig in (b'PK\x03\x04', b'PK\x01\x02', b'PK\x05\x06'):
                self.assertEqual(raw.count(sig), 1, sig)
            z = open_gdl(out)
            self.assertEqual(z.read('x.tgz4'), payload)
            self.assertEqual(z.read('ProjectGCP'), b'a new graph')

    def test_the_built_panel_is_read_as_it_was_written(self):
        """gdl.data reads a built panel through the container's reader; its own
        once swapped every KP in the file back to PK, the payload's data with
        the records."""
        import tempfile
        from gdl.container import _resign
        from gdl.data import payload
        built = stored([('layout.json', b'{}'), ('7.png', self.DATA)])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'built.gdl')
            with open(path, 'wb') as fh:
                fh.write(_resign(stored([('ProjectGCP', b'graph'), ('project1.tgz4', built)]), b'PK', b'KP'))
            self.assertEqual(payload(path).read('7.png'), self.DATA)


if __name__ == '__main__':
    unittest.main()
