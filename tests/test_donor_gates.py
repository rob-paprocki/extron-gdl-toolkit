"""What a donor must supply, checked before a Windows round trip.

`check_donor` used to verify two things: that every control type could be
cloned, and that no page name collided. Everything else about donor fitness was
discovered on the Windows box, or after it - which is expensive, and in one case
silent.

Each gate here exists because it actually cost something:

  * no PBProject - a .glt template applied and packed fine, then GUI Designer
    opened empty and offered the Project Create Wizard, which from outside looks
    exactly like a hang.
  * border resources - a plan may only name borders the donor defines, so a
    spec's others are built as the donor's nearest shape and refused where it
    has none near enough; the spread is wide (a fresh themed project defines
    13 to 31, the client fixture 34, and they are not the same ones).
  * font families - the softest and worst. A family with no PBFontResource does
    not fail the build; the applier leaves the donor's face and the panel ships
    in the wrong typeface. A three-page panel built cleanly in Open Sans while
    its spec asked for Forma DJR Display, and only the built-file verifier
    noticed. So a face a seed carries is appended, and one none carries is
    refused.
  * canvas - the built panel is the DONOR's model. A 1024x600 spec applied to a
    1280x800 project lays out correctly by its own arithmetic and wrongly on the
    actual panel.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _corpus import MAIN_CLIENT, needs_client  # noqa: E402

from gdl.project import Project  # noqa: E402
from gdl.spec import Panel  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(ROOT, 'fixtures', 'gdl',
                       'client-boardroom-2.0.0.gdl')
# Defines Open Sans Light, which the _alt fixture does not. Plain git, so the
# tests that use it need no LFS pull.
LIGHT_FIXTURE = os.path.join(ROOT, 'fixtures', 'gdl',
                             'client-boardroom-1.1.0.gdl')
PANEL = os.path.join(ROOT, 'examples', 'panel.json')


def spec(path=PANEL, **over):
    with open(path, encoding='utf-8') as fh:
        d = json.load(fh)
    d.update(over)
    return d


class TestTheWorkedExampleStillFits(unittest.TestCase):
    """The regression guard. Every gate below must leave this clean. Its donor is a
    seed: the client's project, which it used to be, is not in the public copy."""

    def test_no_problems_against_its_own_donor(self):
        donor = seed('Afterburn 1035.gdl')
        if not usable(donor):
            self.skipTest('seeds/Afterburn 1035.gdl is not pulled from Git LFS here')
        self.assertEqual(Panel(spec()).check_donor(donor), [])


class TestBorderResources(unittest.TestCase):
    @needs_client(MAIN_CLIENT)
    def test_defined_is_not_the_same_as_referenced(self):
        """The distinction the first version of this gate got wrong."""
        p = Project.open(FIXTURE)
        referenced = set(p.border_resources())
        defined = p.border_resource_names()
        self.assertLess(len(referenced), len(defined))
        # '2D Capsule' is defined and never drawn with - checking the referenced
        # set rejected a spec that had already built.
        self.assertIn('2D Capsule', defined)
        self.assertNotIn('2D Capsule', referenced)

    @needs_client(MAIN_CLIENT)
    def test_an_undefined_border_is_reported(self):
        d = spec()
        d['pages'][0]['controls'][0]['border'] = 'No Such Border'
        msgs = Panel(d).check_donor(FIXTURE)
        self.assertTrue(any('No Such Border' in m and 'border resource' in m
                            for m in msgs), msgs)

    def test_needs_borders_resolves_aliases(self):
        """A spec writes 'capsule'; the resource is named '2D Capsule'."""
        d = spec()
        d['pages'][0]['controls'][0]['border'] = 'capsule'
        self.assertIn('2D Capsule', Panel(d).needs_borders())


class TestABorderTheDonorLacks(unittest.TestCase):
    """A border the spec names and the donor does not define is built as the
    donor's own of the same shape - same family first, then the same
    thickness, then the nearest radius - and said aloud, rather than refused.
    Within one theme family the seeds disagree: the Afterburn 320 seed has no
    10-radius pair, and the Mach 300M Portrait seed no Mach border at all."""

    BUILT_INS = ['2D Rectangle', '2D Rounded Rectangle', '2D Capsule', '2D Ellipse',
                 '3D Rectangle', '3D Rounded Rectangle', '3D Capsule', '3D Gradient']
    # seeds/Afterburn 320.gdl's own, beside the built-ins.
    AB320 = BUILT_INS + ['Afterburn - 14 Radius 0 Thick', 'Afterburn - 7 Radius 2 Thick',
                         'Afterburn - Elipse 0 Thick', 'Afterburn - Elipse 3 Thick']

    def test_the_320_builds_its_own_radius(self):
        """The two the Afterburn design system swaps by hand for the 320."""
        from gdl.spec import nearest_border
        self.assertEqual(nearest_border('Afterburn - 10 Radius 2 Thick', self.AB320),
                         'Afterburn - 7 Radius 2 Thick')
        self.assertEqual(nearest_border('Afterburn - 10 Radius 0 Thick', self.AB320),
                         'Afterburn - 14 Radius 0 Thick')

    def test_a_family_with_none_of_its_own_takes_a_built_in(self):
        from gdl.spec import nearest_border
        self.assertEqual(nearest_border('Mach - 10 Radius 2 Thick', self.BUILT_INS),
                         '2D Rounded Rectangle')

    def test_another_familys_border_of_the_same_shape(self):
        from gdl.spec import nearest_border
        mach = self.BUILT_INS + ['Mach - 10 Radius 2 Thick']
        self.assertEqual(nearest_border('Afterburn - 10 Radius 2 Thick', mach),
                         'Mach - 10 Radius 2 Thick')

    def test_a_rectangle_stays_a_rectangle(self):
        """2D Rectangle_1, the thin one, is in no seed."""
        from gdl.spec import nearest_border
        self.assertEqual(nearest_border('2D Rectangle_1', self.AB320), '2D Rectangle')

    def test_an_ellipse_only_for_an_ellipse(self):
        from gdl.spec import nearest_border
        self.assertEqual(nearest_border('Afterburn - Elipse 0 Thick', self.BUILT_INS), '2D Ellipse')
        self.assertNotIn(nearest_border('Afterburn - 10 Radius 0 Thick', self.AB320),
                         ('Afterburn - Elipse 0 Thick', '2D Ellipse'))

    def test_3d_only_for_3d(self):
        from gdl.spec import nearest_border
        self.assertEqual(nearest_border('3D Rounded Rectangle Selected', self.BUILT_INS),
                         '3D Rounded Rectangle')
        self.assertIsNone(nearest_border('3D Capsule', ['2D Capsule', '2D Rectangle']))

    def test_a_border_of_no_known_shape_has_none(self):
        from gdl.spec import nearest_border
        self.assertIsNone(nearest_border('No Such Border', self.AB320))
        self.assertIsNone(nearest_border('', self.AB320))

    def _afterburn_spec(self):
        return {'name': 'T', 'model': 'TLP320M', 'size': [320, 240], 'theme': {'text': '#FFFFFF'},
                'pages': [{'name': 'P', 'number': 1000, 'controls': [
                    {'kind': 'button', 'name': 'A', 'rect': [16, 16, 120, 64], 'text': 'A',
                     'fill': '#37394E', 'border': 'afterburn',
                     'states': [{'name': 'Off'}, {'name': 'On', 'border': 'afterburn-flat'}]}]}]}

    def test_on_the_320_seed_it_is_no_problem(self):
        donor = seed('Afterburn 320.gdl')
        if not usable(donor):
            self.skipTest('seeds/Afterburn 320.gdl is not pulled from Git LFS here')
        swaps = {}
        problems = Panel(self._afterburn_spec()).check_donor(donor, swaps=swaps)
        self.assertFalse(any('border' in m for m in problems), problems)
        self.assertEqual(swaps, {'Afterburn - 10 Radius 2 Thick': 'Afterburn - 7 Radius 2 Thick',
                                 'Afterburn - 10 Radius 0 Thick': 'Afterburn - 14 Radius 0 Thick'})

    def test_the_plan_builds_the_donors_own(self):
        p = Panel(self._afterburn_spec())
        plan = p.plan(swaps={'Afterburn - 10 Radius 2 Thick': 'Afterburn - 7 Radius 2 Thick',
                             'Afterburn - 10 Radius 0 Thick': 'Afterburn - 14 Radius 0 Thick'})
        op = plan['pages'][0]['controls'][0]
        self.assertEqual(op['border'], 'Afterburn - 7 Radius 2 Thick')
        self.assertEqual([s['border'] for s in op['states']],
                         ['Afterburn - 7 Radius 2 Thick', 'Afterburn - 14 Radius 0 Thick'])

    def test_without_a_donor_the_plan_is_as_written(self):
        op = Panel(self._afterburn_spec()).plan()['pages'][0]['controls'][0]
        self.assertEqual(op['border'], 'Afterburn - 10 Radius 2 Thick')

    def _run(self, *argv):
        import contextlib
        import io
        from gdl.spec import main
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(['spec', *argv])
        return code, out.getvalue()

    def _on_the_320(self):
        import tempfile
        donor = seed('Afterburn 320.gdl')
        if not usable(donor):
            self.skipTest('seeds/Afterburn 320.gdl is not pulled from Git LFS here')
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'spec.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(self._afterburn_spec(), fh)
        return donor, path, d

    def test_donors_says_what_it_builds_instead(self):
        donor, path, _ = self._on_the_320()
        code, out = self._run('donors', path, donor)
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"'Afterburn - 10 Radius 2 Thick'.*'Afterburn - 7 Radius 2 Thick'")

    def test_plan_with_its_donor_writes_the_donors_own(self):
        donor, path, d = self._on_the_320()
        out_path = os.path.join(d, 'plan.json')
        code, out = self._run('plan', path, out_path, '--donor', donor)
        self.assertEqual(code, 0, out)
        with open(out_path, encoding='utf-8') as fh:
            op = json.load(fh)['pages'][0]['controls'][0]
        self.assertEqual(op['border'], 'Afterburn - 7 Radius 2 Thick')

    def test_plan_takes_its_donor_before_or_after_the_plan_path(self):
        donor, path, d = self._on_the_320()
        out_path = os.path.join(d, 'plan2.json')
        code, out = self._run('plan', path, '--donor', donor, out_path)
        self.assertEqual(code, 0, out)
        with open(out_path, encoding='utf-8') as fh:
            self.assertEqual(json.load(fh)['pages'][0]['controls'][0]['border'],
                             'Afterburn - 7 Radius 2 Thick')
        # Misread, the plan went to a file named '--donor' where the shell was.
        self.assertNotIn('-> --donor', out)

    def test_plan_refuses_an_option_it_cannot_read(self):
        _, path, d = self._on_the_320()
        for argv in ((path, os.path.join(d, 'p.json'), '--donor'),
                     (path, os.path.join(d, 'p.json'), '--donr', 'x.gdl'),
                     (path,)):
            code, out = self._run('plan', *argv)
            self.assertEqual(code, 2, (argv, out))
        self.assertFalse(os.path.exists(os.path.join(d, 'p.json')))

    def test_a_swap_that_makes_two_states_one_is_a_problem(self):
        """Off in 10 Radius 0 Thick and On in 14 Radius 0 Thick differ only by
        border, and on the 320 - whose nearest to the first is the second - the
        program could set either and the panel would show no difference."""
        donor = seed('Afterburn 320.gdl')
        if not usable(donor):
            self.skipTest('seeds/Afterburn 320.gdl is not pulled from Git LFS here')
        spec = self._afterburn_spec()
        spec['pages'][0]['controls'][0].update(
            border='afterburn-flat', states=[{'name': 'Off'}, {'name': 'On', 'border': 'afterburn-14'}])
        problems = Panel(spec).check_donor(donor)
        self.assertTrue(any("'Off' and 'On' differ only by border" in m and
                            "'Afterburn - 14 Radius 0 Thick'" in m for m in problems), problems)
        self.assertFalse(any('differ only by border' in m
                             for m in Panel(self._afterburn_spec()).check_donor(donor)))


class TestAFaceTheDonorLacks(unittest.TestCase):
    """A family the spec names and the donor defines no font resource for is
    appended to the donor - a clone of one of its own resources, filled with
    the face a seed carries - rather than left in the donor's face. The
    Afterburn 1035 seed has no Open Sans Light; the Mach 1035 seed carries it."""

    def _light(self):
        return {'name': 'T', 'model': 'TLP1035T', 'size': [1280, 800],
                'theme': {'text': '#FFFFFF', 'font': 'Open Sans', 'size': 18},
                'pages': [{'name': 'P', 'number': 1000, 'controls': [
                    {'kind': 'label', 'name': 'Title', 'rect': [40, 40, 600, 80], 'text': 'Boardroom',
                     'font': 'Open Sans Light', 'size': 32}]}]}

    def _seeds(self, *names):
        for n in names:
            if not usable(seed(n)):
                self.skipTest(f'seeds/{n} is not pulled from Git LFS here')

    def test_a_seed_that_carries_the_face_is_found(self):
        self._seeds('Mach 1035.gdl')
        from gdl.fonts import find_face
        face = find_face('Open Sans Light')
        self.assertEqual((face['family'], face['style'], face['file']),
                         ('Open Sans Light', 'Light', 'opensans-light.ttf'))
        self.assertEqual(len(face['bytes']), face['size'])
        self.assertTrue(face['carrier'].startswith('seeds/'), face['carrier'])
        # Added from a file, where Arial - the donor's first resource, which
        # the append clones - is GUI Designer's own (0).
        self.assertEqual(face['author'], 1)

    def test_a_face_no_seed_carries_is_none(self):
        from gdl.fonts import find_face
        self.assertIsNone(find_face('No Such Face'))

    def test_it_is_appended_rather_than_refused(self):
        self._seeds('Afterburn 1035.gdl', 'Mach 1035.gdl')
        fonts = {}
        problems = Panel(self._light()).check_donor(seed('Afterburn 1035.gdl'), fonts=fonts)
        self.assertFalse(any('Open Sans Light' in m for m in problems), problems)
        self.assertEqual(list(fonts), ['Open Sans Light'])

    def test_a_face_no_seed_has_is_still_refused(self):
        self._seeds('Afterburn 1035.gdl')
        d = self._light()
        d['pages'][0]['controls'][0]['font'] = 'No Such Face'
        problems = Panel(d).check_donor(seed('Afterburn 1035.gdl'))
        self.assertTrue(any("'No Such Face'" in m for m in problems), problems)

    def test_plan_with_its_donor_brings_the_face(self):
        """The face is written beside the plan, which names it for the applier."""
        import contextlib
        import io
        import tempfile
        from gdl.spec import main
        self._seeds('Afterburn 1035.gdl', 'Mach 1035.gdl')
        d = tempfile.mkdtemp()
        path, out_path = os.path.join(d, 'spec.json'), os.path.join(d, 'plan.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(self._light(), fh)
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(['spec', 'plan', path, out_path, '--donor', seed('Afterburn 1035.gdl')])
        self.assertEqual(code, 0)
        with open(out_path, encoding='utf-8') as fh:
            fonts = json.load(fh)['fonts']
        self.assertEqual([(f['family'], f['style']) for f in fonts], [('Open Sans Light', 'Light')])
        self.assertTrue(os.path.isfile(fonts[0]['file']))
        self.assertEqual(os.path.getsize(fonts[0]['file']), fonts[0]['size'])
        self.assertEqual(fonts[0]['author'], 1)
        self.assertRegex(fonts[0]['carrier'], r'^seeds/[^/]+\.gdl$')

    def _icon(self, codepoint):
        return {'name': 'T', 'model': 'TLP1035T', 'size': [1280, 800],
                'theme': {'text': '#FFFFFF', 'font': 'Open Sans', 'size': 18},
                'pages': [{'name': 'P', 'number': 1000, 'controls': [
                    {'kind': 'button', 'name': 'B', 'rect': [40, 40, 160, 160],
                     'icon': codepoint, 'font': 'Extron-Lift'}]}]}

    def test_an_icon_in_a_face_the_donor_lacks_is_checked_in_the_face_appended(self):
        """Extron-Lift is Mach's: the Afterburn seed has no resource for it,
        and the Mach seed's face - 95 glyphs, to U+E95E - is the one appended
        and drawn from."""
        self._seeds('Afterburn 1035.gdl', 'Mach 1035.gdl')
        donor = seed('Afterburn 1035.gdl')
        for fonts in (None, {}):
            self.assertEqual(Panel(self._icon('U+E926')).check_donor(donor, fonts=fonts), [])
        problems = Panel(self._icon('U+E970')).check_donor(donor)
        self.assertTrue(any('U+E970' in m and 'seeds/Mach 1035.gdl' in m for m in problems),
                        problems)

    def test_a_family_the_donor_spells_otherwise_is_refused_in_its_spelling(self):
        self._seeds('Afterburn 1035.gdl')
        d = self._light()
        d['pages'][0]['controls'][0]['font'] = 'open sans'
        fonts = {}
        problems = Panel(d).check_donor(seed('Afterburn 1035.gdl'), fonts=fonts)
        self.assertTrue(any("'open sans'" in m and "'Open Sans'" in m for m in problems), problems)
        self.assertEqual(fonts, {})

    def test_a_face_a_seed_spells_otherwise_is_refused_in_its_spelling(self):
        self._seeds('Afterburn 1035.gdl', 'Mach 1035.gdl')
        d = self._light()
        d['pages'][0]['controls'][0]['font'] = 'OPEN SANS LIGHT'
        fonts = {}
        problems = Panel(d).check_donor(seed('Afterburn 1035.gdl'), fonts=fonts)
        self.assertTrue(any("'OPEN SANS LIGHT'" in m and "'Open Sans Light'" in m
                            for m in problems), problems)
        self.assertEqual(fonts, {})

    def test_only_a_seed_that_carries_the_face_is_parsed(self):
        """Every Afterburn seed declares Arial Black and carries none: the
        stream says so in a tenth of a second, where parsing each took one to
        five."""
        self._seeds('Afterburn 1035.gdl', 'Mach 1035.gdl')
        from unittest import mock
        from gdl import fonts
        parsed, real = [], fonts.carried

        def counting(project):
            parsed.append(os.path.basename(os.fspath(project)))
            return real(project)
        with mock.patch.dict(fonts._FOUND, clear=True), \
                mock.patch.object(fonts, 'carried', counting):
            face = fonts.find_face('Arial Black')
        self.assertEqual(face['family'], 'Arial Black')
        self.assertLessEqual(set(parsed), {os.path.basename(face['carrier'])})

    def test_donors_says_which_faces_it_appends_and_from_where(self):
        import contextlib
        import io
        import tempfile
        from gdl.spec import main
        self._seeds('Afterburn 1035.gdl', 'Mach 1035.gdl')
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'spec.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(self._light(), fh)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(['spec', 'donors', path, seed('Afterburn 1035.gdl')])
        self.assertEqual(code, 0, out.getvalue())
        self.assertRegex(out.getvalue(),
                         r"font 'Open Sans Light' is not in .*: appended from seeds/[^']+\.gdl")

    def test_a_font_that_is_not_a_name_is_refused_not_raised(self):
        """`"font": 14` - a size in the wrong key - passes check."""
        self._seeds('Afterburn 1035.gdl')
        from gdl.fonts import find_face
        self.assertIsNone(find_face(14))
        d = self._light()
        d['pages'][0]['controls'][0]['font'] = 14
        problems = Panel(d).check_donor(seed('Afterburn 1035.gdl'))
        self.assertTrue(any('font family 14 ' in m for m in problems), problems)

    def _repo(self, name, files):
        """A repo root named `name`, its seeds/ holding `files` - {file name:
        bytes, or a seed to link} - in place of this one's."""
        import shutil
        import tempfile
        from unittest import mock
        from gdl import fonts, seeds
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top, True)
        root = os.path.join(top, name)
        os.makedirs(os.path.join(root, 'seeds'))
        for n, src in files.items():
            dst = os.path.join(root, 'seeds', n)
            if isinstance(src, bytes):
                with open(dst, 'wb') as fh:
                    fh.write(src)
                continue
            try:
                os.link(src, dst)
            except OSError:
                shutil.copyfile(src, dst)
        for p in (mock.patch.object(seeds, 'REPO', root), mock.patch.dict(fonts._FOUND, clear=True)):
            p.start()
            self.addCleanup(p.stop)

    def test_a_seed_that_is_not_a_project_is_passed_over(self):
        self._seeds('Mach 1035.gdl')
        from gdl.fonts import find_face
        self._repo('toolkit', {'Afterburn 1035.gdl': b'', 'Mach 1035.gdl': seed('Mach 1035.gdl')})
        self.assertEqual(find_face('Open Sans Light')['carrier'], 'seeds/Mach 1035.gdl')

    def test_a_repo_path_with_brackets_finds_its_seeds(self):
        """glob reads '[work]' as a character class, matching no folder."""
        self._seeds('Mach 1035.gdl')
        from gdl.fonts import find_face
        self._repo('toolkit [work]', {'Mach 1035.gdl': seed('Mach 1035.gdl')})
        self.assertEqual(find_face('Open Sans Light')['carrier'], 'seeds/Mach 1035.gdl')

    def test_with_no_seed_pulled_the_refusal_says_so(self):
        self._seeds('Afterburn 1035.gdl')
        from gdl import seeds
        self._repo('toolkit', {'Mach 1035.gdl': seeds._LFS_POINTER + b'v1\noid sha256:0\nsize 1\n'})
        problems = Panel(self._light()).check_donor(seed('Afterburn 1035.gdl'))
        self.assertTrue(any("'Open Sans Light'" in m and 'git lfs pull' in m for m in problems),
                        problems)


class TestFontResources(unittest.TestCase):
    @needs_client(MAIN_CLIENT, 'client-boardroom-1.1.0.gdl')
    def test_families_are_read_without_their_style_suffix(self):
        names = Project.open(FIXTURE).font_resource_names()
        self.assertIn('Forma DJR Display', names)
        self.assertNotIn('Forma DJR Display Regular Bold Italic', names)

    @needs_client(MAIN_CLIENT, 'client-boardroom-1.1.0.gdl')
    def test_a_weight_named_in_the_family_is_not_a_style(self):
        """Arial Black and Open Sans Light are families of their own, not Arial
        and Open Sans in another weight: a control names them in PBFont.nameField,
        and the resource is `<family> Regular Bold Italic`."""
        names = Project.open(LIGHT_FIXTURE).font_resource_names()
        self.assertEqual(names, {'Arial', 'Arial Black', 'Extron-Afterburn',
                                 'Open Sans', 'Open Sans Light'})

    def test_only_regular_bold_and_italic_are_style_words(self):
        """Light, Black, Semibold and the other weights Windows puts in a family
        name survive; the styles of one family do not."""
        class Named(Project):
            def __init__(self, names):
                self.names = names

            def _resource_names(self, cls):
                return set(self.names) if cls == 'PBFontResource' else set()

        got = Named(['Arial Black Regular Bold Italic',
                     'Open Sans Light Regular Bold Italic',
                     'Open Sans Regular Bold Italic',
                     'Segoe UI Semibold Regular Bold Italic',
                     'FluentSystemIcons-Regular Regular Bold Italic',
                     'Open Sans Bold']).font_resource_names()
        self.assertEqual(got, {'Arial Black', 'Open Sans Light', 'Open Sans',
                               'Segoe UI Semibold', 'FluentSystemIcons-Regular'})

    @needs_client(MAIN_CLIENT, 'client-boardroom-1.1.0.gdl')
    def test_a_face_the_donor_defines_is_not_reported_missing(self):
        """The symptom: `donors` said a project that defines Arial Black and Open
        Sans Light lacked both, and New-GdlPanel.ps1 stops on its exit code."""
        d = spec()
        d['theme']['font'] = 'Open Sans Light'
        d['pages'][0]['controls'][0]['font'] = 'Arial Black'
        msgs = Panel(d).check_donor(LIGHT_FIXTURE)
        self.assertEqual([m for m in msgs if 'font family' in m], [], msgs)

    @needs_client(MAIN_CLIENT, 'client-boardroom-1.1.0.gdl')
    def test_a_family_the_donor_lacks_is_reported(self):
        d = spec()
        d['theme']['font'] = 'Comic Sans MS'
        msgs = Panel(d).check_donor(FIXTURE)
        self.assertTrue(any('Comic Sans MS' in m and 'font family' in m
                            for m in msgs), msgs)

    def test_the_theme_default_counts_not_just_per_control_fonts(self):
        """Most controls name no font, so the theme default is what ships."""
        d = spec()
        d['theme']['font'] = 'Nonexistent Face'
        self.assertIn('Nonexistent Face', Panel(d).needs_fonts())


@needs_client(MAIN_CLIENT)
class TestCanvas(unittest.TestCase):
    def test_a_mismatched_canvas_is_reported(self):
        d = spec(size=[1024, 600])
        msgs = Panel(d).check_donor(FIXTURE)
        self.assertTrue(any('canvas' in m for m in msgs), msgs)

    def test_a_matching_canvas_is_not(self):
        msgs = Panel(spec(size=[1280, 800])).check_donor(FIXTURE)
        self.assertFalse([m for m in msgs if 'canvas' in m], msgs)


sys.path.insert(0, HERE)
from _corpus import seed, template, usable  # noqa: E402


class TestPageLibraryDonors(unittest.TestCase):
    TEMPLATE = template('Afterburn 1020 Series.glt')

    @unittest.skipUnless(usable(TEMPLATE), 'Extron templates not in vendor/ or installed')
    def test_a_glt_template_is_refused(self):
        msgs = Panel(spec()).check_donor(self.TEMPLATE)
        self.assertTrue(any('PBProject' in m for m in msgs), msgs)


class TestSeedFontResources(unittest.TestCase):
    """What a seed defines, which is not what its layout.json declares."""
    SHOCKWAVE = seed('Shockwave 1035.gdl')
    AFTERBURN = seed('Afterburn 1035.gdl')

    @unittest.skipUnless(usable(SHOCKWAVE), 'seed not present (git lfs pull)')
    def test_shockwave_defines_arial_black_and_not_open_sans_light(self):
        names = Project.open(self.SHOCKWAVE).font_resource_names()
        self.assertIn('Arial Black', names)
        self.assertNotIn('Open Sans Light', names)

    @unittest.skipUnless(usable(AFTERBURN), 'seed not present (git lfs pull)')
    def test_a_face_the_seed_only_declares_is_appended_from_one_that_carries_it(self):
        """Afterburn's layout.json declares Arial Black and its project defines
        no resource for it. A seed carries one - the Mach 1035, or one GUI
        Designer added it to when it built it, as the Afterburn 1035 Portrait -
        recorded as GUI Designer writes the faces it supplies: a default, with
        no file name (None in the one, '' in the other). A spec naming it is
        given that, not left in the donor's face."""
        if not usable(seed('Mach 1035.gdl')):
            self.skipTest('seeds/Mach 1035.gdl is not pulled from Git LFS here')
        self.assertEqual(Project.open(self.AFTERBURN).font_resource_names(),
                         {'Arial', 'Extron-Afterburn', 'Open Sans'})
        d = spec()
        d['theme']['font'] = 'Arial Black'
        fonts = {}
        msgs = Panel(d).check_donor(self.AFTERBURN, fonts=fonts)
        self.assertFalse(any('Arial Black' in m and 'font family' in m for m in msgs), msgs)
        self.assertTrue(fonts['Arial Black']['default'])
        self.assertFalse(fonts['Arial Black']['file'])
        self.assertFalse(fonts['Arial Black']['source'])


class TestADonorOfAnotherPanel(unittest.TestCase):
    """The built panel is the donor's model and theme, whatever the spec names.
    seeds/ names a seed for its size, so 'Afterburn 725.gdl' - a TLP725T - is
    where a TLP725M spec at the same 1024x600 would land, and every other gate
    passes it: the canvas matches."""
    S725 = seed('Afterburn 725.gdl')
    S1035 = seed('Afterburn 1035.gdl')

    def setUp(self):
        for s in (self.S725, self.S1035):
            if not usable(s):
                self.skipTest(f'{s} not present (git lfs pull)')

    @staticmethod
    def said(msgs, what):
        return [m for m in msgs if f"the spec's {what}" in m]

    def test_a_donor_of_another_model_is_refused(self):
        msgs = Panel(spec(model='TLP725M', size=[1024, 600])).check_donor(self.S725)
        got = self.said(msgs, 'model')
        self.assertEqual(len(got), 1, msgs)
        self.assertIn('TLP725T', got[0])
        self.assertIn('TLP725M', got[0])

    def test_the_donors_own_model_is_not(self):
        msgs = Panel(spec(model='TLP725T', size=[1024, 600])).check_donor(self.S725)
        self.assertEqual(self.said(msgs, 'model'), [], msgs)

    def test_two_models_of_one_part_number_share_a_donor(self):
        msgs = Panel(spec(model='TLP1035M')).check_donor(self.S1035)
        self.assertEqual(self.said(msgs, 'model'), [], msgs)

    def test_a_spec_that_names_no_model_is_not_held_to_one(self):
        d = spec(size=[1024, 600])
        d.pop('model', None)
        self.assertEqual(self.said(Panel(d).check_donor(self.S725), 'model'), [])

    def test_a_donor_of_another_theme_is_refused(self):
        msgs = Panel(spec(family='Mach')).check_donor(self.S1035)
        got = self.said(msgs, 'family')
        self.assertEqual(len(got), 1, msgs)
        self.assertIn('Afterburn', got[0])
        self.assertIn('Mach', got[0])

    def test_the_family_as_typed_is_the_donors_theme(self):
        msgs = Panel(spec(family='afterburn ')).check_donor(self.S1035)
        self.assertEqual(self.said(msgs, 'family'), [], msgs)


class TestALevelDrawnFromArt(unittest.TestCase):
    """A seed's level fills with a color (gaugeFillType 0: Afterburn's and
    Mach's) or from an image (1: Shockwave's and Turbulence's), which Build
    draws in place of any color. A bar color planned for an image level never
    showed, and the verifier held the art to it on the Shockwave and
    Turbulence hubs. check_donor says which, of the level the applier clones -
    Get-GdlDonor's, the first, pages before popups."""

    LEVEL = {'kind': 'level', 'name': 'Volume', 'rect': [700, 100, 40, 300], 'orientation': 'up',
             'track': 20, 'fill': '#000000', 'bar': '#FFFFFF'}

    def _spec(self):
        return {'name': 'T', 'model': 'TLP525T', 'size': [800, 480], 'theme': {'text': '#FFFFFF'},
                'pages': [{'name': 'P', 'number': 1000, 'controls': [dict(self.LEVEL)]}]}

    def test_which_seeds_levels_are_drawn_from_art(self):
        for name, want in (('Shockwave 525.gdl', {'fill': '19x259_vol-full.png', 'track': '19x259_vol-empty.png'}),
                           ('Turbulence 525.gdl', {'fill': '24x535_vert_vol-bars_full.png',
                                                   'track': '24x535_vert_vol-bars_empty.png'}),
                           ('Mach 525.gdl', None), ('Afterburn 525.gdl', None)):
            with self.subTest(seed=name):
                donor = seed(name)
                if not usable(donor):
                    self.skipTest(f'seeds/{name} is not pulled from Git LFS here')
                art = {}
                Panel(self._spec()).check_donor(donor, art=art)
                self.assertEqual(art.get('level'), want)

    def test_plan_keeps_an_image_levels_art_and_plans_it_no_bar(self):
        import contextlib
        import io
        import tempfile
        from gdl.spec import main
        donor = seed('Shockwave 525.gdl')
        if not usable(donor):
            self.skipTest('seeds/Shockwave 525.gdl is not pulled from Git LFS here')
        with tempfile.TemporaryDirectory() as d:
            path, plan = os.path.join(d, 'spec.json'), os.path.join(d, 'plan.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(self._spec(), fh)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['spec', 'plan', path, plan, '--donor', donor]), 0)
            with open(plan, encoding='utf-8') as fh:
                op = json.load(fh)['pages'][0]['controls'][0]
        self.assertIsNone(op['gauge_fill'])
        self.assertTrue(op['keep_art'])


class TestAPopupTheDonorCannotSupply(unittest.TestCase):
    """The applier clones a popup from a donor popup of its own kind and
    throws "donor project has no standard popup to clone" otherwise. Every 320
    seed has modal popups only, so a spec's standard popup is refused here, by
    name, and not one Windows round trip later."""

    def _spec(self, modal):
        return {'name': 'T', 'model': 'TLP320M', 'size': [320, 240], 'theme': {'text': '#FFFFFF'},
                'popup_groups': ['G'],
                'pages': [{'name': 'P', 'number': 1000, 'controls': [
                    {'kind': 'button', 'name': 'A', 'rect': [16, 16, 120, 64], 'text': 'A'}]}],
                'popups': [{'name': 'Laptop', 'modal': modal, **({} if modal else {'group': 'G', 'size': [200, 120]}),
                            'controls': [{'kind': 'label', 'name': 'L', 'rect': [8, 8, 100, 30], 'text': 'L'}]}]}

    def _need(self, name):
        donor = seed(name)
        if not usable(donor):
            self.skipTest(f'seeds/{name} is not pulled from Git LFS here')
        return donor

    def test_a_standard_popup_is_refused_on_a_320_seed(self):
        for name in ('Mach 320.gdl', 'Afterburn 320.gdl'):
            with self.subTest(seed=name):
                problems = Panel(self._spec(False)).check_donor(self._need(name))
                self.assertTrue(any('no standard popup to clone' in m and "'Laptop'" in m for m in problems),
                                problems)

    def test_a_modal_is_fine_on_a_320_seed(self):
        problems = Panel(self._spec(True)).check_donor(self._need('Mach 320.gdl'))
        self.assertFalse(any('popup' in m for m in problems), problems)

    def test_a_seed_with_a_standard_popup_supplies_one(self):
        spec = self._spec(False)
        spec.update(model='TLP1035T', size=[1280, 800])
        problems = Panel(spec).check_donor(self._need('Mach 1035.gdl'))
        self.assertFalse(any('standard popup' in m for m in problems), problems)


if __name__ == '__main__':
    unittest.main()
