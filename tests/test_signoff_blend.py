"""The sign-off draws the panel, the scoring path draws GUI Designer's snapshot.

The two differ on purpose (docs/render-fidelity.md finding 2): the snapshots
paint any pixel with alpha > 0 solid, so scoring against them keeps that rule,
but a client signing a sheet should see Shockwave's 15% well as a well.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PIL import Image
except ImportError:                                  # pragma: no cover
    Image = None

from gdl import compose, design  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _png(rgba, size=(40, 40)):
    buf = io.BytesIO()
    Image.new('RGBA', size, rgba).save(buf, 'PNG')
    return buf.getvalue()


def _built():
    """A _Built over a one-page layout: a translucent-black image control and a
    control with no art whose fill is white at alpha 128, over a red page."""
    page = {'ID': 1, 'Name': 'Home', 'Width': 40, 'Height': 40, 'TLPImageID': 1,
            'Controls': [
                {'__type': 'PBImage:x', 'ID': 5, 'Left': 0, 'Top': 0, 'Width': 20, 'Height': 40,
                 'TLPImageID': 2},
                {'__type': 'PBButton:x', 'ID': 6, 'Left': 20, 'Top': 0, 'Width': 20, 'Height': 40,
                 'TLPImageID': -1}]}
    b = design._Built.__new__(design._Built)
    b.path = None
    b.j = {'Pages': [page], 'PopupPages': [], 'DefaultPage': 1}
    b.assets = {1: _png((255, 0, 0, 255)), 2: _png((0, 0, 0, 128), (20, 40))}
    b.fills = {(1, 6): {'fill': {'A': 128, 'R': 255, 'G': 255, 'B': 255}, 'stroke': None}}
    b.by_name = {'Home': page}
    return b


@unittest.skipIf(Image is None, 'Pillow not installed')
class SignOffBlend(unittest.TestCase):
    def test_the_sign_off_blends_translucent_art_and_fills(self):
        img = _built().image('Home', (40, 40))
        art = img.getpixel((5, 20))        # 50% black over red
        fill = img.getpixel((30, 20))      # 50% white over red
        self.assertAlmostEqual(art[0], 127, delta=2)
        self.assertEqual(art[1:3], (0, 0))
        self.assertAlmostEqual(fill[1], 128, delta=2)
        self.assertGreater(fill[0], 250)

    def test_the_scoring_path_still_writes_them_solid(self):
        b = _built()
        self.assertIs(compose.BINARY, True)
        img = compose.render_snapshot(b.j, 1, b.assets, (40, 40), fills=b.fills)
        self.assertEqual(img.getpixel((5, 20))[:3], (0, 0, 0))
        self.assertEqual(img.getpixel((30, 20))[:3], (255, 255, 255))

    def test_the_rule_goes_back(self):
        _built().image('Home', (40, 40))
        self.assertIs(compose.BINARY, True)
        self.assertIsNone(compose._carried)

    def test_a_spec_preview_blends_a_translucent_fill(self):
        from gdl.spec import Panel
        p = Panel({'name': 'T', 'size': [40, 40], 'theme': {'text': '#FFFFFF', 'background': '#FF0000'},
                   'pages': [{'name': 'Home', 'number': 1, 'controls': [
                       {'kind': 'panel', 'rect': [0, 0, 40, 40], 'fill': '#80FFFFFF'}]}]})
        px = p.render(0).getpixel((20, 20))
        self.assertGreater(px[1], 100)
        self.assertLess(px[1], 160)


@unittest.skipIf(Image is None, 'Pillow not installed')
class CarriedFaces(unittest.TestCase):
    def setUp(self):
        self.saved = dict(compose._cache)
        self.addCleanup(lambda: (compose._cache.clear(), compose._cache.update(self.saved)))
        path = os.path.join(compose.FONTDIR, 'arial.ttf')
        if not os.path.exists(path):
            self.skipTest('arial.ttf not recovered')
        self.path = path
        with open(path, 'rb') as fh:
            self.data = fh.read()

    def test_a_face_the_file_carries_is_drawn_from_it(self):
        compose._carried = [{'family': 'Extron-Afterburn', 'style': 'Regular', 'bytes': self.data}]
        compose._carried_tag = 'p1'
        try:
            f = compose.face('Extron-Afterburn', 0, 0, 20)
        finally:
            compose._carried, compose._carried_tag = None, None
        self.assertIsInstance(f.path, io.BytesIO)

    def test_the_cache_is_per_project(self):
        compose._carried = [{'family': 'Arial', 'style': 'Regular', 'bytes': self.data}]
        compose._carried_tag = 'p1'
        try:
            a = compose.face('Arial', 0, 0, 20)
        finally:
            compose._carried, compose._carried_tag = None, None
        b = compose.face('Arial', 0, 0, 20)
        self.assertIsNot(a, b)
        self.assertNotIsInstance(b.path, io.BytesIO)

    def test_bold_wants_a_bold_face_then_the_regular(self):
        faces = [{'family': 'F', 'style': 'Regular', 'bytes': b'r'},
                 {'family': 'F', 'style': 'Bold', 'bytes': b'b'}]
        compose._carried = faces
        try:
            self.assertEqual(compose._carried_face('F', 1, 0), b'b')
            self.assertEqual(compose._carried_face('F', 0, 1), b'r')
            self.assertIsNone(compose._carried_face('G', 0, 0))
        finally:
            compose._carried = None

    def test_no_file_means_the_recovered_face_as_before(self):
        with compose.as_the_panel():
            f = compose.face('Arial', 0, 0, 20)
        self.assertNotIsInstance(f.path, io.BytesIO)


class StandIns(unittest.TestCase):
    def test_a_stand_in_is_named_in_the_output(self):
        import contextlib
        saved = set(compose.FALLBACKS)
        compose.FALLBACKS.add('Roboto as arial.ttf')
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                design.print_standins()
        finally:
            compose.FALLBACKS.clear()
            compose.FALLBACKS.update(saved)
        self.assertIn('Roboto as arial.ttf', out.getvalue())


@unittest.skipIf(Image is None, 'Pillow not installed')
class CarriedFaceReads(unittest.TestCase):
    def setUp(self):
        import tempfile
        saved = dict(compose._cache), dict(compose._PROJECT_FACES)
        self.addCleanup(lambda: (compose._cache.clear(), compose._cache.update(saved[0]),
                                 compose._PROJECT_FACES.clear(), compose._PROJECT_FACES.update(saved[1])))
        path = os.path.join(compose.FONTDIR, 'arial.ttf')
        if not os.path.exists(path):
            self.skipTest('arial.ttf not recovered')
        with open(path, 'rb') as fh:
            self.data = fh.read()
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, 'a.gdl')

    def _write(self, faces, mtime):
        from unittest import mock
        with open(self.path, 'wb') as fh:
            fh.write(b'x')
        os.utime(self.path, (mtime, mtime))
        return mock.patch('gdl.fonts.carried', return_value=faces)

    def test_a_file_rebuilt_at_the_same_path_draws_its_new_faces(self):
        one = [{'family': 'Arial', 'style': 'Regular', 'bytes': self.data}]
        two = [{'family': 'Arial', 'style': 'Regular', 'bytes': bytes(self.data)}]
        with self._write(one, 1000000000):
            with compose.as_the_panel(self.path):
                a = compose.face('Arial', 0, 0, 20)
        with self._write(two, 1000000100):
            with compose.as_the_panel(self.path):
                b = compose.face('Arial', 0, 0, 20)
        self.assertIsNot(a, b)

    def test_only_the_latest_read_of_a_path_is_kept(self):
        for t, faces in ((1000000000, [{'family': 'A', 'style': '', 'bytes': b'1'}]),
                         (1000000100, [{'family': 'A', 'style': '', 'bytes': b'2'}])):
            with self._write(faces, t):
                compose.project_faces(self.path)
        mine = [k for k in compose._PROJECT_FACES if k[0] == os.path.abspath(self.path)]
        self.assertEqual(len(mine), 1)

    def test_state_is_restored_after_an_exception_and_when_nested(self):
        with self._write([{'family': 'A', 'style': '', 'bytes': b'1'}], 1000000000):
            with self.assertRaises(RuntimeError):
                with compose.as_the_panel(self.path):
                    raise RuntimeError
            self.assertIs(compose.BINARY, True)
            self.assertIsNone(compose._carried)
            self.assertIsNone(compose._carried_tag)
            with compose.as_the_panel(self.path):
                outer = compose._carried
                with compose.as_the_panel():
                    # No project of its own: the outer one's faces still apply.
                    self.assertIs(compose._carried, outer)
                    self.assertIs(compose.BINARY, False)
                self.assertIs(compose._carried, outer)
                self.assertIs(compose.BINARY, False)
            self.assertIs(compose.BINARY, True)
            self.assertIsNone(compose._carried)

    def test_a_real_seed_is_read_once(self):
        seed = os.path.join(os.path.dirname(HERE), 'seeds', 'Afterburn 320.gdl')
        if not os.path.exists(seed) or os.path.getsize(seed) < 1024:
            self.skipTest('seed is absent or an LFS pointer')
        faces = compose.project_faces(seed)
        self.assertTrue(faces)
        self.assertTrue(all(f['bytes'] for f in faces))
        self.assertIs(compose.project_faces(seed), faces)


class StandInNotes(unittest.TestCase):
    """The CLI wiring, not only the helper."""

    def setUp(self):
        saved = set(compose.FALLBACKS)
        compose.FALLBACKS.add('Roboto as arial.ttf')
        self.addCleanup(lambda: (compose.FALLBACKS.clear(), compose.FALLBACKS.update(saved)))

    def _run(self, main, argv, **patches):
        import contextlib
        from unittest import mock
        out = io.StringIO()
        with contextlib.ExitStack() as st:
            for target, value in patches.items():
                st.enter_context(mock.patch(target.replace('__', '.'), value))
            st.enter_context(contextlib.redirect_stdout(out))
            main(argv)
        return out.getvalue()

    def test_design_compare_prints_the_note(self):
        text = self._run(design.main, ['x', 'compare', 'canvas', 'built', 'out'],
                         gdl__design__runtime_problem=lambda *a: None,
                         gdl__design__compare=lambda *a: [('Home', 1.0)])
        self.assertIn('Roboto as arial.ttf', text)

    def test_design_compare_template_prints_the_note(self):
        text = self._run(design.main, ['x', 'compare', 'canvas', '--template', 'out'],
                         gdl__design__runtime_problem=lambda *a: None,
                         gdl__design__compare_template=lambda *a: [('m', 'Home', None)])
        self.assertIn('Roboto as arial.ttf', text)

    def test_spec_render_prints_the_note(self):
        from unittest import mock
        from gdl import spec
        panel = mock.MagicMock()
        panel.check.return_value = []
        panel.pages = [{'name': 'Home'}]
        panel.render.return_value = Image.new('RGB', (4, 4))
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            text = self._run(spec.main, ['x', 'render', 'spec.json', os.path.join(d, 'o.png')],
                             gdl__spec__Panel=mock.MagicMock(load=lambda p: panel))
        self.assertIn('Roboto as arial.ttf', text)


if __name__ == '__main__':
    unittest.main()
