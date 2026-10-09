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


# A System.Drawing.Color stored by name - `state` 1, its `value` 0 - is the
# KnownColor `knownColor`: 27 Transparent, 35 Black, 105 LimeGreen, 164 White.
# Every seed stores colors so (Shockwave's 211 White and 206 Black, every
# Turbulence label's White), and reading only the value read each as none.
# The web colors, 27-167, with .NET Framework's own values (Color.FromKnownColor
# in 32-bit PowerShell 5.1, the host GUI Designer runs on) - where it differs
# from CSS, as DarkSeaGreen does (#8FBC8B, not #8FBC8F), Framework's. The rest
# are Windows system colors, whatever the build host's theme says - none is
# seen in the corpus, and they read as none.
KNOWN_COLORS = {
    27: 0x00FFFFFF, 28: 0xFFF0F8FF, 29: 0xFFFAEBD7, 30: 0xFF00FFFF, 31: 0xFF7FFFD4,
    32: 0xFFF0FFFF, 33: 0xFFF5F5DC, 34: 0xFFFFE4C4, 35: 0xFF000000, 36: 0xFFFFEBCD,
    37: 0xFF0000FF, 38: 0xFF8A2BE2, 39: 0xFFA52A2A, 40: 0xFFDEB887, 41: 0xFF5F9EA0,
    42: 0xFF7FFF00, 43: 0xFFD2691E, 44: 0xFFFF7F50, 45: 0xFF6495ED, 46: 0xFFFFF8DC,
    47: 0xFFDC143C, 48: 0xFF00FFFF, 49: 0xFF00008B, 50: 0xFF008B8B, 51: 0xFFB8860B,
    52: 0xFFA9A9A9, 53: 0xFF006400, 54: 0xFFBDB76B, 55: 0xFF8B008B, 56: 0xFF556B2F,
    57: 0xFFFF8C00, 58: 0xFF9932CC, 59: 0xFF8B0000, 60: 0xFFE9967A, 61: 0xFF8FBC8B,
    62: 0xFF483D8B, 63: 0xFF2F4F4F, 64: 0xFF00CED1, 65: 0xFF9400D3, 66: 0xFFFF1493,
    67: 0xFF00BFFF, 68: 0xFF696969, 69: 0xFF1E90FF, 70: 0xFFB22222, 71: 0xFFFFFAF0,
    72: 0xFF228B22, 73: 0xFFFF00FF, 74: 0xFFDCDCDC, 75: 0xFFF8F8FF, 76: 0xFFFFD700,
    77: 0xFFDAA520, 78: 0xFF808080, 79: 0xFF008000, 80: 0xFFADFF2F, 81: 0xFFF0FFF0,
    82: 0xFFFF69B4, 83: 0xFFCD5C5C, 84: 0xFF4B0082, 85: 0xFFFFFFF0, 86: 0xFFF0E68C,
    87: 0xFFE6E6FA, 88: 0xFFFFF0F5, 89: 0xFF7CFC00, 90: 0xFFFFFACD, 91: 0xFFADD8E6,
    92: 0xFFF08080, 93: 0xFFE0FFFF, 94: 0xFFFAFAD2, 95: 0xFFD3D3D3, 96: 0xFF90EE90,
    97: 0xFFFFB6C1, 98: 0xFFFFA07A, 99: 0xFF20B2AA, 100: 0xFF87CEFA, 101: 0xFF778899,
    102: 0xFFB0C4DE, 103: 0xFFFFFFE0, 104: 0xFF00FF00, 105: 0xFF32CD32,
    106: 0xFFFAF0E6, 107: 0xFFFF00FF, 108: 0xFF800000, 109: 0xFF66CDAA,
    110: 0xFF0000CD, 111: 0xFFBA55D3, 112: 0xFF9370DB, 113: 0xFF3CB371,
    114: 0xFF7B68EE, 115: 0xFF00FA9A, 116: 0xFF48D1CC, 117: 0xFFC71585,
    118: 0xFF191970, 119: 0xFFF5FFFA, 120: 0xFFFFE4E1, 121: 0xFFFFE4B5,
    122: 0xFFFFDEAD, 123: 0xFF000080, 124: 0xFFFDF5E6, 125: 0xFF808000,
    126: 0xFF6B8E23, 127: 0xFFFFA500, 128: 0xFFFF4500, 129: 0xFFDA70D6,
    130: 0xFFEEE8AA, 131: 0xFF98FB98, 132: 0xFFAFEEEE, 133: 0xFFDB7093,
    134: 0xFFFFEFD5, 135: 0xFFFFDAB9, 136: 0xFFCD853F, 137: 0xFFFFC0CB,
    138: 0xFFDDA0DD, 139: 0xFFB0E0E6, 140: 0xFF800080, 141: 0xFFFF0000,
    142: 0xFFBC8F8F, 143: 0xFF4169E1, 144: 0xFF8B4513, 145: 0xFFFA8072,
    146: 0xFFF4A460, 147: 0xFF2E8B57, 148: 0xFFFFF5EE, 149: 0xFFA0522D,
    150: 0xFFC0C0C0, 151: 0xFF87CEEB, 152: 0xFF6A5ACD, 153: 0xFF708090,
    154: 0xFFFFFAFA, 155: 0xFF00FF7F, 156: 0xFF4682B4, 157: 0xFFD2B48C,
    158: 0xFF008080, 159: 0xFFD8BFD8, 160: 0xFFFF6347, 161: 0xFF40E0D0,
    162: 0xFFEE82EE, 163: 0xFFF5DEB3, 164: 0xFFFFFFFF, 165: 0xFFF5F5F5,
    166: 0xFFFFFF00, 167: 0xFF9ACD32,
}


class Project:
    def __init__(self, graph):
        self.g = graph
        self.o = graph.objects
        self._palette = None  # palette_color()'s index -> color, read once

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
        """PBColor -> {'A','R','G','B'} or None when fully transparent.

        A color can name an entry of the project's palette instead of carrying
        a value: `paletteIndexField` >= 0, and `valueField` is then empty. Build
        draws the entry - Shockwave's On captions are palette Black (1), and
        Afterburn's seed has none, which is why reading only the value went
        unnoticed.
        """
        i = self.field(obj, 'paletteIndexField')
        if isinstance(i, int) and i >= 0:
            return self.palette_color(i)
        inner = self.field(obj, 'valueField')
        if not isinstance(inner, dict):
            return None
        if inner.get('state') == 1:  # stored by name: see KNOWN_COLORS
            v = KNOWN_COLORS.get(inner.get('knownColor'))
            c = argb(v) if v is not None else None
            return c if c and c['A'] else None
        c = argb(inner.get('value', 0))
        return c if c['A'] else None

    def palette_color(self, index):
        """The project palette's entry `index` -> {'A','R','G','B'}, or None when
        it is transparent or the palette has no such entry."""
        if self._palette is None:
            self._palette = {}
            for proj in self.instances('PBProject'):
                pal = self.deref(self.field(proj, 'paletteField'))
                for e in self.items((pal or {}).get('itemsField')) if isinstance(pal, dict) else []:
                    e = self.deref(e)
                    self._palette[e.get('indexField')] = {
                        'A': e.get('alphaField'), 'R': e.get('redField'),
                        'G': e.get('greenField'), 'B': e.get('blueField')}
                break
        c = self._palette.get(index)
        return c if c and c['A'] else None

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
            (`'\\t\\tDevice\\r\\n\\t\\tComms'`). 23 controls in the client
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

    def state(self, st):
        """One state's own appearance: what `gdl.edit` matches and rewrites.

        A button draws from its states, not from itself: in the client
        fixture 288 of 442 buttons have no fill of their own and a fill on
        every state. So anything that changes how a button looks has to read
        and write each state, not the control.
        """
        text, ftext = self.deref(st.get('textField')), self.deref(st.get('ftextField'))
        caption, where = None, None
        if text:
            caption, where = text, 'state'
        elif ftext:
            caption, where = ftext.replace('\t', '').replace('\r\n', ' ').strip(), 'fstate'
        return {
            'name': self.field(st, 'nameField'),
            'caption': caption,
            'caption_in': where,
            'fill': self.color(self.field(st, 'borderFillColorField')),
            'stroke': self.color(self.field(st, 'borderColorField')),
            'text_color': self.color(self.field(st, 'textColorField')),
        }

    def control(self, obj):
        states = self.states(obj)
        caption, caption_in = self.caption_at(obj)
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
            'caption': caption,
            'caption_in': caption_in,
            'tlp_image': self.field(obj, '<TLPImageID>k__BackingField'),
            # the two the built payload throws away
            'fill': self.color(self.field(obj, 'borderFillColorField')),
            'stroke': self.color(self.field(obj, 'borderColorField')),
            'text_color': self.color(self.field(obj, 'textColorField')),
            'border': self.border(obj),
            # How many appearances this control can show. A button with one
            # state cannot give feedback. The applier resizes a cloned donor's
            # states to what the spec names, so this is a fact about the donor,
            # not a limit on the spec.
            'n_states': len(states),
            'state_names': [self.field(s, 'nameField') for s in states],
            'states': [self.state(s) for s in states],
            # The state shown while the button is held, and the one it starts
            # in. Default is 0 on every button in the corpus.
            'press': self.field(obj, '<TLPPressFeedbackStateID>k__BackingField'),
            'default_state': self.field(obj, '<TLPDefaultStateID>k__BackingField'),
            # PBStates.statusField: PBState.StatusFlags (PreventAddState = 1,
            # PreventDelete = 2, PreventReorder = 4, PreventRename = 8, ...).
            # 0 on every button in the corpus; the applier will not resize a
            # donor whose states carry any.
            'state_flags': self._state_flags(obj),
        }

    def _state_flags(self, obj):
        sts = self.field(obj, 'statesField')
        return self.field(sts, 'statusField') if sts else None

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
        differ a lot: the client fixture references 7 and defines 34.
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
        1220 defines 31, the client fixture 34.
        """
        return self._resource_names('PBBorderResource')

    def font_resource_names(self):
        """Every font FAMILY the project defines a resource for.

        GUI Designer resolves a typeface through a named `PBFontResource`, and
        the resource name carries a style suffix the spec would never write -
        `Forma DJR Display Regular Bold Italic` for the family `Forma DJR
        Display` - so the suffix is stripped here and matching is on the family.

        Only Regular, Bold and Italic are styles: they are what the suffix lists,
        in every project and template read. A weight Windows reports as part of
        the family name is the family - `Arial Black Regular Bold Italic` is
        Arial Black, `Open Sans Light ...` Open Sans Light and `Segoe UI
        Semibold ...` Segoe UI Semibold. Each is a face of its own that a control
        names in `PBFont.nameField`, and stripping the weight folded each into its
        plain sibling and reported a face missing from a seed that defines it.

        A spec naming a family the donor has no resource for does not fail: the
        applier leaves the donor's font and says so. That is the right call and
        also easy to miss, since the panel then builds cleanly in the wrong face.
        """
        out = set()
        for name in self._resource_names('PBFontResource'):
            fam = re.sub(r'(\s+(Regular|Bold|Italic))+$', '', name).strip()
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
