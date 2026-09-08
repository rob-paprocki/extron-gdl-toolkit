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

from gdl.container import open_gdl, pack, payload_name  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, '..', 'fixtures', 'gdl',
                       'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
TEMPLATES = ('C:/Users/Public/Documents/Extron/GUI Designer Templates/'
             'TouchLink Templates')


def write_bare(path, gcp=b'stand-in graph'):
    """A container holding only a ProjectGCP, in the KP-swapped on-disk form."""
    from gdl.container import NORMAL, _swap
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('ProjectGCP', gcp)
    with open(path, 'wb') as fh:
        fh.write(_swap(buf.getvalue(), NORMAL, b'KP'))
    return path


class TestPayloadName(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.d = tempfile.mkdtemp()

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


if __name__ == '__main__':
    unittest.main()
