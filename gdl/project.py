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

Build rasterises those into `N.png` and assigns TLPImageID. So a generator
never produces artwork — it names resources and sets colours, exactly as a
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

    def control(self, obj):
        return {
            'type': self.kind(obj).rsplit('.', 1)[-1],
            'name': self.field(obj, 'nameField'),
            'id': self.field(obj, 'userIdField'),
            'rect': (self.field(obj, 'leftField'), self.field(obj, 'topField'),
                     self.field(obj, 'widthField'), self.field(obj, 'heightField')),
            'text': self.field(obj, 'textField'),
            'tlp_image': self.field(obj, '<TLPImageID>k__BackingField'),
            # the two the built payload throws away
            'fill': self.color(self.field(obj, 'borderFillColorField')),
            'stroke': self.color(self.field(obj, 'borderColorField')),
            'border': self.border(obj),
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
        """Elements of a serialised List<T>.

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

    def pages(self):
        """Every page and popup, each with its own controls.

        Yields the page's `idField`, which is the same number layout.json
        exports as `Page.ID` - so this is what joins the authoring model to the
        built payload. Same for a control's `idField` and `Control.ID`.
        """
        proj = next(self.instances('PBProject'), None)
        if proj is None:
            return
        for field, kind in (('pagesField', 'page'), ('popupPagesField', 'popup')):
            for pg in self.items(self.field(proj, field)):
                yield {
                    'kind': kind,
                    'id': self.field(pg, 'idField'),
                    'name': self.field(pg, 'nameField'),
                    'modal': self.field(pg, 'modalField'),
                    'controls': [dict(self.control(c), obj_id=self.field(c, 'idField'))
                                 for c in self.items(self.field(pg, 'controlsField'))],
                }

    def fill_map(self):
        """(page id, control id) -> the fill Build would have rasterised.

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
        """Every named border resource the project can draw with."""
        seen = {}
        for obj in self.instances('PBResourceReferenceBorder'):
            n = self.field(obj, 'resourceNameField')
            if n and n not in seen:
                m = BORDER_NAME.search(n)
                seen[n] = {'radius': int(m.group(1)), 'thickness': int(m.group(2))} if m else {}
        return seen


if __name__ == '__main__':
    import sys

    p = Project.open(sys.argv[1])
    res = p.border_resources()
    print(f'border resources ({len(res)}):')
    for n, geo in sorted(res.items()):
        print(f'   {n:<40} {geo}')
    unrasterised = [c for c in p.controls() if c['tlp_image'] == -1 and c['fill']]
    print(f'\ncontrols with no built artwork but a real fill ({len(unrasterised)}) '
          f'- these are the ones layout.json cannot describe:')
    for c in unrasterised:
        print(f"   {c['type']:<10} {str(c['name'])[:22]:<22} {c['rect']} "
              f"fill={c['fill']} border={c['border']}")
