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

from gdl.project import Project  # noqa: E402
from gdl.spec import Panel  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(ROOT, 'fixtures', 'gdl',
                       'Interface__alt_J26450039_Liberty_Bank_Boardroom_2_0_0.gdl')
PANEL = os.path.join(ROOT, 'examples', 'panel.json')


def spec(path=PANEL, **over):
    with open(path, encoding='utf-8') as fh:
        d = json.load(fh)
    d.update(over)
    return d


class TestTheWorkedExampleStillFits(unittest.TestCase):
    """The regression guard. Every gate below must leave this clean."""

    def test_no_problems_against_its_own_donor(self):
        self.assertEqual(Panel(spec()).check_donor(FIXTURE), [])


class TestBorderResources(unittest.TestCase):
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
    def test_families_are_read_without_their_style_suffix(self):
        names = Project.open(FIXTURE).font_resource_names()
        self.assertIn('Forma DJR Display', names)
        self.assertNotIn('Forma DJR Display Regular Bold Italic', names)

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


class TestCanvas(unittest.TestCase):
    def test_a_mismatched_canvas_is_reported(self):
        d = spec(size=[1024, 600])
        msgs = Panel(d).check_donor(FIXTURE)
        self.assertTrue(any('canvas' in m for m in msgs), msgs)

    def test_a_matching_canvas_is_not(self):
        msgs = Panel(spec(size=[1280, 800])).check_donor(FIXTURE)
        self.assertFalse([m for m in msgs if 'canvas' in m], msgs)


class TestPageLibraryDonors(unittest.TestCase):
    TEMPLATE = ('C:/Users/Public/Documents/Extron/GUI Designer Templates/'
                'TouchLink Templates/Afterburn 1020 Series.glt')

    @unittest.skipUnless(os.path.exists(TEMPLATE), 'GUI Designer templates not installed')
    def test_a_glt_template_is_refused(self):
        msgs = Panel(spec()).check_donor(self.TEMPLATE)
        self.assertTrue(any('PBProject' in m for m in msgs), msgs)


if __name__ == '__main__':
    unittest.main()
