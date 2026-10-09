"""What a donor must supply, checked before a Windows round trip.

`check_donor` used to verify two things: that every control type could be
cloned, and that no page name collided. Everything else about donor fitness was
discovered on the Windows box, or after it - which is expensive, and in one case
silent.

Each gate here exists because it actually cost something:

  * no PBProject - a .glt template applied and packed fine, then GUI Designer
    opened empty and offered the Project Create Wizard, which from outside looks
    exactly like a hang.
  * border resources - a spec may only reference borders the donor defines, and
    the spread is wide (a fresh themed project defines 31, the client fixture
    34, but they are not the same 31).
  * font families - the softest and worst. A family with no PBFontResource does
    not fail the build; the applier leaves the donor's face and the panel ships
    in the wrong typeface. A three-page panel built cleanly in Open Sans while
    its spec asked for Forma DJR Display, and only the built-file verifier
    noticed.
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
    def test_a_face_the_seed_only_declares_is_still_reported(self):
        """Afterburn's layout.json declares Arial Black; its project defines no
        resource for it, so a spec naming it still builds in the donor's face."""
        self.assertEqual(Project.open(self.AFTERBURN).font_resource_names(),
                         {'Arial', 'Extron-Afterburn', 'Open Sans'})
        d = spec()
        d['theme']['font'] = 'Arial Black'
        msgs = Panel(d).check_donor(self.AFTERBURN)
        self.assertTrue(any('Arial Black' in m and 'font family' in m for m in msgs), msgs)


if __name__ == '__main__':
    unittest.main()
