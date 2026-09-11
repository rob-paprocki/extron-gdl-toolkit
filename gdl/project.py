"""Semantic read access to the authoring model inside ProjectGCP.

`layout.json` is the *built* view: every control's appearance has been flattened
into a PNG, and the properties that produced it are gone. The authoring model
kept in ProjectGCP still has them, and they are what an authoring tool sets:

    borderFillColor   the control's interior fill  (NOT backgroundFillColor,
                      which is transparent on every control in every file)
    borderColor       its stroke
    border            a *named* resource, e.g. "Afterburn - 10 Radius 0 Thick",
                      giving shape type, corner radius and thickness
    backgroundImage / buttonImage   named image resources

Build rasterizes those into `N.png` and assigns TLPImageID. So a generator
never produces artwork — it names resources and sets colors, exactly as a
designer does in the UI.

This module is read-only and pure Python: it does not need GUI Designer
installed, unlike powershell/GdlProject.ps1 which is required for *writing*.

    from gdl.project import Project
    p = Project.open('some.gdl')
    for c in p.controls():
        print(c['name'], c['rect'], c['fill'], c['border'])
"""
import re

from . import nrbf
from .container import open_gdl

REF = 'ref'
CONTROL_TYPES = ('PBButton', 'PBLabel', 'PBShape', 'PBLine', 'PBImage',
                 'PBSlider', 'PBLevel', 'PBDateTime', 'PBPopupPageReference')
# "Afterburn - 10 Radius 0 Thick" -> radius 10, thickness 0
BORDER_NAME = re.compile(r'(\d+)\s*Radius\s*(\d+)\s*Thick', re.I)


def argb(value):
    """System.Drawing.Color.value is a packed 0xAARRGGBB int."""
    v = int(value) & 0xFFFFFFFF
    return {'A': v >> 24, 'R': (v >> 16) & 0xFF, 'G': (v >> 8) & 0xFF, 'B': v & 0xFF}


class Project:
    def __init__(self, graph):
        self.g = graph
        self.o = graph.objects

    @classmethod
    def open(cls, path):
        return cls(nrbf.parse(open_gdl(path).read('ProjectGCP')))

    # -- graph helpers -----------------------------------------------------
    def deref(self, v, depth=0):
        if depth > 8:
            return v
        if isinstance(v, tuple) and len(v) == 2 and v[0] == REF:
            return self.deref(self.o.get(v[1]), depth + 1)
        return v

    def field(self, obj, name):
        """Fields are stored qualified by declaring type ('PBControl+xField')."""
        obj = self.deref(obj)
        if not isinstance(obj, dict):
            return None
        if name in obj:
            return self.deref(obj[name])
        for k, v in obj.items():
            if k.split('+')[-1] == name:
                return self.deref(v)
        return None

    def kind(self, obj):
        obj = self.deref(obj)
        return obj.get('__class', '').split(',')[0] if isinstance(obj, dict) else ''

    def instances(self, suffix):
        for v in self.o.values():
            if isinstance(v, dict) and self.kind(v).endswith(suffix):
                yield v

    # -- semantic accessors ------------------------------------------------
    def color(self, obj):
        """PBColor -> {'A','R','G','B'} or None when fully transparent."""
        inner = self.field(obj, 'valueField')
        if not isinstance(inner, dict):
            return None
        c = argb(inner.get('value', 0))
        return c if c['A'] else None

    def border(self, obj):
        """The named border resource, decoded to shape geometry."""
        ref = self.field(obj, 'borderField')
        name = self.field(ref, 'resourceNameField') if ref else None
        if not name:
            return None
        m = BORDER_NAME.search(name)
        out = {'resource': name}
        if m:
            out['radius'], out['thickness'] = int(m.group(1)), int(m.group(2))
        return out

    def states(self, obj):
        """A control's `PBState`s, in order.

        `statesField` is a `PBStates` wrapper, NOT the list - the `List<PBState>`
        hangs off its `mItems`. Reading `statesField` as a list yields nothing
        and looks like a control with no states, which is wrong for every
        button in every fixture. (The same wrapper is why PowerShell must index
        `PBStates` rather than `foreach` it.)
        """
        d = self.field(obj, 'statesField')
        if not isinstance(d, dict):
            return []
        return [self.deref(x) for x in self.items(d.get('mItems'))]

    def caption(self, obj):
        """What a control actually says, wherever the caption happens to live.

        Three places, in priority order, and a control that uses one leaves the
        others empty:
          * the control's own `textField`
          * `textField` on its first state - where a BUTTON's caption lives, and
            a caption set only on the control builds blank
          * `ftextField` on the first state - GUI Designer's formatted-text
            variant, which arrives with tab and CRLF layout markers baked in
            (`'\\t\\tDevice\\r\\n\\t\\tComms'`). 23 controls in the Liberty Bank
            fixture against 336 plain ones, so it is the minority path, but
            missing it means a caption search silently skips them.
        """
        return self.caption_at(obj)[0]

    def caption_at(self, obj):
        """(caption, where) - `where` being which field an edit has to write.

        Renaming has to put the new text where the old text was: writing
        `textField` on a control whose caption lives in a state's `ftextField`
        leaves the original showing.
        """
        own = self.field(obj, 'textField')
        if own:
            return own, 'control'
        for st in self.states(obj):
            for f, where in (('textField', 'state'), ('ftextField', 'fstate')):
                v = self.deref(st.get(f))
                if v:
                    return v.replace('\t', '').replace('\r\n', ' ').strip(), where
        return None, None

    def control(self, obj):
        return {
            'type': self.kind(obj).rsplit('.', 1)[-1],
            'name': self.field(obj, 'nameField'),
            'id': self.field(obj, 'userIdField'),
            'rect': (self.field(obj, 'leftField'), self.field(obj, 'topField'),
                     self.field(obj, 'widthField'), self.field(obj, 'heightField')),
            'text': self.field(obj, 'textField'),
            # What it says on the panel, which is usually NOT `text` - see
            # caption(). Anything selecting a control by its wording wants this,
            # and anything CHANGING it wants caption_in as well.
            'caption': self.caption_at(obj)[0],
            'caption_in': self.caption_at(obj)[1],
            'tlp_image': self.field(obj, '<TLPImageID>k__BackingField'),
            # the two the built payload throws away
            'fill': self.color(self.field(obj, 'borderFillColorField')),
            'stroke': self.color(self.field(obj, 'borderColorField')),
            'border': self.border(obj),
            # How many appearances this control can show. A button with one
            # state cannot give feedback, and a plan can only fill states the
            # donor already has - see Spec.check_donor. `states` is the whole
            # picture; this is the number a donor check needs.
            'n_states': len(self.states(obj)),
            'state_names': [self.field(s, 'nameField') for s in self.states(obj)],
        }

    def controls(self, types=CONTROL_TYPES):
        """Every control in the graph, with no page context.

        A flat scan by class name. Cheap, and enough when you only want to know
        what a project contains - but see `pages()` when you need to know which
        page something is on, which is most of the time.
        """
        for suffix in types:
            for obj in self.instances(suffix):
                yield self.control(obj)

    # -- the page tree -----------------------------------------------------
    def items(self, lst):
        """Elements of a serialized List<T>.

        `_items` is the backing array and is over-allocated - 32 slots holding
        4 pages - so it must be sliced to `_size`. Reading the whole array
        yields a tail of Nones that look like real, empty objects.
        """
        lst = self.deref(lst)
        if not isinstance(lst, dict):
            return []
        arr = self.deref(lst.get('_items')) or []
        size = self.deref(lst.get('_size'))
        if size is None:
            size = len(arr)
        return [self.deref(x) for x in arr[:size]]

    def _page(self, pg, kind):
        return {
            'kind': kind,
            'id': self.field(pg, 'idField'),
            'name': self.field(pg, 'nameField'),
            'modal': self.field(pg, 'modalField'),
            # A page's own canvas. Standard pages match the panel; popups have
            # their own, and a control outside it is relocated to 0,0 by Build.
            'size': (self.field(pg, 'widthField'), self.field(pg, 'heightField')),
            'controls': [dict(self.control(c), obj_id=self.field(c, 'idField'))
                         for c in self.items(self.field(pg, 'controlsField'))],
        }

    def pages(self):
        """Every page and popup, each with its own controls.

        Yields the page's `idField`, which is the same number layout.json
        exports as `Page.ID` - so this is what joins the authoring model to the
        built payload. Same for a control's `idField` and `Control.ID`.

        A `.glt` template has **no PBProject** - it is a bare library of pages
        and popups with no project wrapper - so walking down from the project
        finds nothing. Fall back to scanning for the page classes directly,
        which is what makes Extron's own per-panel templates readable. Ordering
        is then whatever the graph gives, not declaration order; the project
        path is used whenever there is a project, because order matters there
        (popup group members are resolved by it).
        """
        proj = next(self.instances('PBProject'), None)
        if proj is not None:
            for field, kind in (('pagesField', 'page'), ('popupPagesField', 'popup')):
                for pg in self.items(self.field(proj, field)):
                    yield self._page(pg, kind)
            return
        for suffix, kind in (('PBPopupPage', 'popup'), ('PBPage', 'page')):
            for pg in self.instances(suffix):
                # PBPopupPage derives from PBPage, so match the exact class or
                # every popup is yielded twice.
                if self.kind(pg).rsplit('.', 1)[-1] != suffix:
                    continue
                yield self._page(pg, kind)

    def fill_map(self):
        """(page id, control id) -> the fill Build would have rasterized.

        Only controls Build left without artwork, which are the only ones whose
        appearance layout.json cannot describe. Keyed on the ids both models
        share, so unlike a geometry-based key this cannot match the wrong
        control on another page.
        """
        out = {}
        for pg in self.pages():
            for c in pg['controls']:
                if c['tlp_image'] == -1 and c['fill']:
                    out[(pg['id'], c['obj_id'])] = {'fill': c['fill'], 'border': c['border']}
        return out

    def border_resources(self):
        """Every named border resource the project's controls actually USE.

        This walks `PBResourceReferenceBorder` - the references - so it answers
        "what does this design draw with", not "what may I draw with". The two
        differ a lot: the Liberty Bank fixture references 7 and defines 34.
        Use `border_resource_names()` before authoring against a donor.
        """
        seen = {}
        for obj in self.instances('PBResourceReferenceBorder'):
            n = self.field(obj, 'resourceNameField')
            if n and n not in seen:
                m = BORDER_NAME.search(n)
                seen[n] = {'radius': int(m.group(1)), 'thickness': int(m.group(2))} if m else {}
        return seen

    def border_resource_names(self):
        """Every border resource the project DEFINES, whether drawn with or not.

        The set a spec may reference, and the same one `Set-GdlBorder` checks
        against `ResourceSet.Resources` on the Windows side. Reading the
        `PBBorderResource` instances out of the graph gets it without a Windows
        box, so an unavailable border is a one-second check here instead of a
        per-control complaint after a plan has been applied and packed.

        Every project carries the ~14 GUI Designer built-ins twice - once plain
        and once `zGD - Default ...` - plus its theme's own. A fresh Afterburn
        1220 defines 31, the Liberty Bank fixture 34.
        """
        return self._resource_names('PBBorderResource')

    def font_resource_names(self):
        """Every font FAMILY the project defines a resource for.

        GUI Designer resolves a typeface through a named `PBFontResource`, and
        the resource name carries a style suffix the spec would never write -
        `Forma DJR Display Regular Bold Italic` for the family `Forma DJR
        Display` - so the suffix is stripped here and matching is on the family.

        A spec naming a family the donor has no resource for does not fail: the
        applier leaves the donor's font and says so. That is the right call and
        also easy to miss, since the panel then builds cleanly in the wrong face.
        """
        out = set()
        for name in self._resource_names('PBFontResource'):
            fam = re.sub(r'(\s+(Regular|Bold|Italic|Light|Black|Semibold|Medium|Thin))+$',
                         '', name).strip()
            out.add(fam or name)
        return out

    def _resource_names(self, cls):
        out = set()
        for obj in self.instances(cls):
            n = self.field(obj, 'PBResource+nameField') or self.field(obj, 'nameField')
            if n:
                out.add(n)
        return out


if __name__ == '__main__':
    import sys

    p = Project.open(sys.argv[1])
    res = p.border_resources()
    print(f'border resources ({len(res)}):')
    for n, geo in sorted(res.items()):
        print(f'   {n:<40} {geo}')
    unrasterized = [c for c in p.controls() if c['tlp_image'] == -1 and c['fill']]
    print(f'\ncontrols with no built artwork but a real fill ({len(unrasterized)}) '
          f'- these are the ones layout.json cannot describe:')
    for c in unrasterized:
        print(f"   {c['type']:<10} {str(c['name'])[:22]:<22} {c['rect']} "
              f"fill={c['fill']} border={c['border']}")
