"""Turn a Claude Design canvas into a spec - one for each panel it lists.

    python -m gdl.design translate <canvas dir> <out dir>         # out/<model>/spec.json
    python -m gdl.design translate <canvas dir> <out spec.json>   # the design panel's

A canvas whose Pages list `panels` is translated once per panel: the design
system lays every artboard out for that panel (window.__GDL_PANEL) and the
spec takes the panel's model, size, background art and seed. Any panel with a
problem means no spec for any of them.

The canvas is drawn with one Extron template's design system (gdl/designsys),
whose components carry their spec fields as `data-gdl` JSON. This lays each
artboard out in headless Chrome - the designer places controls with flex and
grid, so a box exists only after layout - reads every component's box and
fields, and writes the spec the rest of the toolkit builds. docs/claude-design.md.

`<canvas dir>` is a local copy of the canvas's `project/` folder: `canvas.json`,
each artboard's `.dc.html`, the installed system under `ds/<folder>/`, and the
canvas runtime saved as `support.js` beside the artboards (the Design type's
`artifact-type/dc-runtime.js`). Claude Code fetches all of it with the Artifact
tool.

Anything on an artboard that paints but is not one of the system's components
is reported and blocks the spec: a panel cannot build it, and a design that
looked right and shipped different is the failure this repo exists to catch.
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys

from . import designsys, seeds, spec as gdlspec

# Where Chrome lives when neither --chrome nor $CHROME says. Headless Chrome is
# the only runtime this needs, and only here.
CHROME = (r'C:\Program Files\Google\Chrome\Application\chrome.exe',
          r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
          '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
          '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser')

# What each kind carries into the spec, beyond kind, name and rect.
FIELDS = {
    'button': ('id', 'text', 'fill', 'stroke', 'color', 'border', 'size', 'bold', 'align',
               'states', 'press', 'nav', 'does', 'derived', 'joined'),
    'label': ('id', 'text', 'color', 'size', 'bold', 'align', 'does'),
    'panel': ('fill', 'stroke', 'border'),
    'line': ('fill', 'thickness', 'from', 'to'),
    'slider': ('id', 'fill', 'border', 'orientation', 'track', 'thumb', 'thumb_height', 'does'),
    'level': ('id', 'fill', 'border', 'orientation', 'track', 'bar', 'does'),
    'datetime': ('color', 'size', 'bold', 'align', 'format'),
    'popup_ref': ('group', 'derived'),
}
COLOR_KEYS = ('fill', 'stroke', 'color', 'bar')
STATE_LOOK = ('fill', 'stroke', 'color', 'text', 'border', 'image')

# Runs inside each artboard once it has rendered. It reports every component
# and every element that paints outside one, relative to the Page's own box.
PROBE = r"""
<script>
(function () {
  function paints(el, cs) {
    if (/^(IMG|SVG|CANVAS|VIDEO|PICTURE|OBJECT)$/i.test(el.tagName)) return el.tagName.toLowerCase();
    if (cs.visibility === 'hidden' || cs.display === 'none') return null;
    if (cs.backgroundImage && cs.backgroundImage !== 'none') return 'background image';
    var bg = cs.backgroundColor;
    if (bg && bg !== 'transparent' && !/rgba\(.*,\s*0\)$/.test(bg)) return 'fill ' + bg;
    for (var s of ['Top', 'Right', 'Bottom', 'Left'])
      if (parseFloat(cs['border' + s + 'Width']) > 0 && cs['border' + s + 'Style'] !== 'none') return 'border';
    if (cs.boxShadow && cs.boxShadow !== 'none') return 'shadow';
    for (var n of el.childNodes) if (n.nodeType === 3 && n.textContent.trim()) return 'text ' + JSON.stringify(n.textContent.trim().slice(0, 40));
    return null;
  }
  // Text a control cannot hold at its size: its content box overflows. Only
  // the kinds whose text the build bakes.
  var TEXT = { button: 1, label: 1, datetime: 1 };
  // Too wide, or an extra line: a line box a few px taller than its control
  // (a 44 px title's 53 px line in a 52 px label) is not - its glyphs fit,
  // and Build draws them centred.
  // The text's own box, not scrollHeight: a label and a button centre their
  // text, so it overflows both ways and scrollHeight sees only the half below
  // - one extra line went unnamed. Read on screen, so a scaled container's
  // text is measured as it shows.
  function overflows(el, kind) {
    if (!TEXT[kind]) return false;
    var line = parseFloat(getComputedStyle(el).lineHeight) || 20;
    if (el.scrollWidth > el.clientWidth + 1) return true;
    var box = el.getBoundingClientRect(), s = el.clientHeight ? box.height / el.clientHeight : 1;
    var rg = document.createRange();
    rg.selectNodeContents(el);
    return rg.getBoundingClientRect().height > box.height + s * line / 2;
  }
  function done() {
    var pages = document.querySelectorAll('[data-gdl]');
    var page = null;
    for (var p of pages) { var k = JSON.parse(p.getAttribute('data-gdl')).kind; if (k === 'page' || k === 'popup') { page = p; break; } }
    var out = { pages: 0, controls: [], stray: [], parts: [], problems: [] };
    for (var p of pages) { var k = JSON.parse(p.getAttribute('data-gdl')).kind; if (k === 'page' || k === 'popup') out.pages++; }
    // What the components found they could not lay out on this panel.
    for (var q of document.querySelectorAll('[data-gdl-problem]')) out.problems.push(q.getAttribute('data-gdl-problem'));
    if (page) {
      var o = page.getBoundingClientRect();
      out.page = { gdl: page.getAttribute('data-gdl'), rect: [0, 0, o.width, o.height] };
      // Derived containers - a Group's pages on this panel - and each one's box.
      var parts = Array.prototype.slice.call(page.querySelectorAll('[data-gdl-part]'));
      var pr = parts.map(function (e) { return e.getBoundingClientRect(); });
      parts.forEach(function (e, i) {
        out.parts.push({ gdl: e.getAttribute('data-gdl-part'),
                         rect: [pr[i].left - o.left, pr[i].top - o.top, pr[i].width, pr[i].height] });
      });
      for (var el of page.querySelectorAll('*')) {
        var r = el.getBoundingClientRect();
        var box = [r.left - o.left, r.top - o.top, r.width, r.height];
        if (el.hasAttribute('data-gdl')) {
          var g = JSON.parse(el.getAttribute('data-gdl'));
          var at = parts.indexOf(el.closest('[data-gdl-part]'));
          if (at >= 0) box = [r.left - pr[at].left, r.top - pr[at].top, r.width, r.height];
          var c = { gdl: el.getAttribute('data-gdl'), rect: box, href: el.getAttribute('href') };
          if (at >= 0) c.part = at;
          if (overflows(el, g.kind)) c.overflow = true;
          out.controls.push(c);
          continue;
        }
        if (el.closest('[data-gdl]') !== page) continue;          // inside a component
        if (el.hasAttribute('data-gdl-part')) continue;           // a derived page wears the page's own look
        var why = paints(el, getComputedStyle(el));
        if (why) out.stray.push({ tag: el.tagName.toLowerCase(), rect: box, why: why });
      }
    }
    var pre = document.createElement('pre'); pre.id = '__gdl_out';
    pre.textContent = JSON.stringify(out); document.documentElement.appendChild(pre);
  }
  var n = 0, last = -1;
  var t = setInterval(function () {
    var k = document.querySelectorAll('[data-gdl]').length;
    if ((k && k === last) || ++n > 80) { clearInterval(t); done(); }
    last = k;
  }, 100);
})();
</script>
"""


def find_chrome(given=None):
    for c in (given, os.environ.get('CHROME')) + CHROME:
        if c and os.path.exists(c):
            return c
    for name in ('google-chrome', 'chromium', 'chrome'):
        path = shutil.which(name)
        if path:
            return path
    return None


def render(board_path, chrome, size, timeout=90, panel=None):
    """Lay one artboard out in headless Chrome; its components and strays.

    The probe goes into a copy beside the original, so relative paths -
    support.js, ds/<folder>/ - resolve the same way they do on the canvas.
    `panel` is the model to lay it out for: set before the design system
    loads, as `window.__GDL_PANEL`, which a Page that lists panels derives
    for (docs/claude-design.md section 2). Without it, the design panel.
    """
    with open(board_path, encoding='utf-8') as fh:
        src = fh.read()
    if '</body>' not in src:
        raise ValueError(f'{os.path.basename(board_path)} has no </body>')
    if panel:
        if '<head>' not in src:
            raise ValueError(f'{os.path.basename(board_path)} has no <head>')
        src = src.replace('<head>', f'<head>\n<script>window.__GDL_PANEL = {json.dumps(panel)};</script>', 1)
    # One probe file per board and panel, so no two renders share a name.
    probe = os.path.join(os.path.dirname(board_path),
                         f"__gdl_probe_{panel + '_' if panel else ''}" + os.path.basename(board_path))
    with open(probe, 'w', encoding='utf-8') as fh:
        fh.write(src.replace('</body>', PROBE + '</body>', 1))
    try:
        r = subprocess.run(
            [chrome, '--headless=new', '--disable-gpu', '--allow-file-access-from-files',
             '--virtual-time-budget=15000', f'--window-size={size[0]},{size[1]}',
             '--enable-logging=stderr', '--v=0', '--dump-dom',
             'file:///' + os.path.abspath(probe).replace('\\', '/').lstrip('/')],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=timeout)
    finally:
        os.remove(probe)
    m = re.search(r'<pre id="__gdl_out">(.*?)</pre>', r.stdout, re.S)
    errors = [ln[ln.find('"'):] for ln in r.stderr.splitlines()
              if 'CONSOLE' in ln and 'Uncaught' in ln]
    if not m:
        raise RuntimeError(f'{os.path.basename(board_path)} did not render'
                           + (f': {errors[0]}' if errors else ''))
    out = json.loads(html.unescape(m.group(1)))
    out['errors'] = errors
    return out


class Canvas:
    """A canvas folder, read and laid out."""

    def __init__(self, folder, chrome=None):
        self.folder = folder
        with open(os.path.join(folder, 'canvas.json'), encoding='utf-8') as fh:
            self.index = json.load(fh)
        self.chrome = find_chrome(chrome)
        self.problems, self.notes = [], []
        self.template = None

    def boards(self):
        order = list(self.index.get('order') or [])
        order += [b for b in self.index.get('boards') or {} if b not in order]
        return order

    def translate(self, rendered=None):
        """(spec, problems, notes). `rendered` maps board -> probe output, for
        tests; otherwise each board is laid out in Chrome."""
        if rendered is None:
            if not self.chrome:
                return None, ['no Chrome found - pass --chrome or set CHROME'], []
            if not os.path.exists(os.path.join(self.folder, 'support.js')):
                return None, ["no support.js beside the artboards - save the Design type's "
                              'artifact-type/dc-runtime.js there'], []
            rendered = {}
            for b in self.boards():
                w = (self.index['boards'].get(b) or {})
                rendered[b] = render(os.path.join(self.folder, *b.split('/')), self.chrome,
                                     (int(w.get('w') or 1280), int(w.get('h') or 800)))
        spec, problems, notes = self._spec(rendered)
        for item in (spec or {}).get('pages', []) + (spec or {}).get('popups', []):
            item.pop('_host', None)
        return spec, problems, notes

    def translate_panels(self, rendered=None):
        """({model: spec} or None, {model: problems}, {model: notes}) - one spec
        per panel the canvas's Pages list, each laid out for its panel by the
        design system (window.__GDL_PANEL). All or nothing: any panel with a
        problem means no specs. A canvas that lists no panels is its profile's
        one design panel. `rendered` maps model -> board -> probe output, for
        tests; otherwise each board is laid out in Chrome once per panel."""
        if rendered is None:
            if not self.chrome:
                msg = ['no Chrome found - pass --chrome or set CHROME']
                return None, {'': msg}, {}
            if not os.path.exists(os.path.join(self.folder, 'support.js')):
                return None, {'': ["no support.js beside the artboards - save the Design type's "
                                   'artifact-type/dc-runtime.js there']}, {}
            design_run = {}
            for b in self.boards():
                design_run[b] = render(os.path.join(self.folder, *b.split('/')), self.chrome,
                                       self._size(b))
            listed = self._panels_of(design_run)
            if not listed:
                listed = [None]
            rendered = {}
            for m in listed:
                rendered[m] = {}
                for b in self.boards():
                    # The design render is the first panel's only if it was
                    # drawn for it: a Page's `preview` draws another.
                    drawn = (json.loads(design_run[b]['page']['gdl']).get('panel')
                             if design_run[b].get('page') else None)
                    rendered[m][b] = design_run[b] if m is None or drawn == m else render(
                        os.path.join(self.folder, *b.split('/')), self.chrome, self._size(b), panel=m)
        specs, problems, notes = {}, {}, {}
        for m, boards in rendered.items():
            self.problems, self.notes = [], []
            spec, probs, nts = self._spec(boards)
            key = m or (spec or {}).get('model') or ''
            if m and spec is not None and spec.get('model') != m:
                probs = probs + [f"laid out for the {spec.get('model')}, not the {m} - remove the "
                                 f"Pages' `preview` before translating, or set it to {m}"]
            if spec is not None:
                self._seed_rules(spec, key, probs)
            problems[key] = [f'{key}: {q}' if key else q for q in probs]
            notes[key] = [f'{key}: {q}' if key else q for q in nts]
            specs[key] = spec
        if not any(problems.values()) and all(v is not None for v in specs.values()):
            for model, q in pin_ids(specs, list(specs)).items():
                problems[model] += [f'{model}: {x}' if model else x for x in q]
            # Each panel's spec as `gdl.spec check` sees it - the touch
            # minimum, the floor, the spacing a grown caption may have broken -
            # here, before a build is ever started. Panel mutates what it reads.
            from copy import deepcopy
            for model, spec in specs.items():
                probe = deepcopy(spec)
                for item in probe['pages'] + probe['popups']:
                    item.pop('_host', None)
                problems[model] += [f'{model}: {x}' if model else x
                                    for x in gdlspec.Panel(probe).check()]
        for spec in specs.values():
            for item in (spec or {}).get('pages', []) + (spec or {}).get('popups', []):
                item.pop('_host', None)
        if any(problems.values()) or any(v is None for v in specs.values()):
            return None, problems, notes
        return specs, problems, notes

    def _size(self, b):
        w = self.index['boards'].get(b) or {}
        return (int(w.get('w') or 1280), int(w.get('h') or 800))

    @staticmethod
    def _panels_of(rendered):
        for out in rendered.values():
            if out.get('page'):
                pg = json.loads(out['page']['gdl'])
                if pg.get('panels'):
                    return list(pg['panels'])
        return []

    _SEED_NAMES = {}

    def _seed_rules(self, spec, model, problems):
        """A panel builds on its own seed: it must be here, and nothing the
        layout derived may take a name the seed already has."""
        seed = spec.get('_seed')
        theme = self.template or 'Afterburn'
        if not seed:
            problems.append(f'no seed for a {model} - make one: {seeds.command(theme, model, None)} - '
                            f'{seeds.listing(theme)}')
            return
        if not seeds.usable(seed):
            problems.append(f'its seed {seed} is not here (or is a Git LFS pointer - git lfs pull) - '
                            f'make it: {seeds.command(theme, model, seed)}')
            return
        if seed not in self._SEED_NAMES:
            from .project import Project
            self._SEED_NAMES[seed] = {pg['name'] for pg in Project.open(seeds.path(seed)).pages()
                                      if pg['name']}
        taken = self._SEED_NAMES[seed]
        for item in spec['pages'] + spec['popups']:
            if item['name'] in taken:
                problems.append(f"{item['name']!r} is a page or popup the seed {seed} already has - "
                                'rename it, or the build fails')

    # -- building the spec ---------------------------------------------------
    def _spec(self, rendered):
        problems, notes = self.problems, self.notes
        profile, scheme, first, names_first = None, None, {}, None
        art = {}
        pages, popups, names, start = [], [], {}, None
        stems = {}
        for b in self.boards():
            out = rendered[b]
            for e in out.get('errors') or []:
                problems.append(f'{b}: script error {e}')
            if out.get('pages', 0) != 1 or not out.get('page'):
                problems.append(f'{b}: needs exactly one Page as its root, found '
                                f"{out.get('pages', 0)}")
                continue
            pg = json.loads(out['page']['gdl'])
            for q in out.get('problems') or []:
                problems.append(f'{b}: {q}')
            if profile is None:
                profile = self._profile(pg.get('template'))
                scheme = pg.get('scheme')
                first = pg
            elif pg.get('panels') != first.get('panels'):
                problems.append(f"{b}: lists panels {' '.join(pg.get('panels') or []) or 'none'}, "
                                f"{names_first} lists {' '.join(first.get('panels') or []) or 'none'} - "
                                'every Page of a canvas lists the same')
            elif pg.get('template') != profile['template']:
                problems.append(f"{b}: drawn in {pg.get('template')!r}, the canvas in "
                                f"{profile['template']!r} - one template per panel")
            if pg.get('scheme') != scheme:
                problems.append(f"{b}: accent scheme {pg.get('scheme')!r}, the others "
                                f'{scheme!r} - one scheme per panel')
            name = pg.get('name') or (self.index['boards'].get(b) or {}).get('title') \
                or b.rsplit('.dc.html', 1)[0]
            if name in names:
                problems.append(f'{b}: page name {name!r} is also {names[name]}')
            names[name] = b
            if len(names) == 1:
                names_first = b
            stems[b.rsplit('/', 1)[-1].rsplit('.dc.html', 1)[0]] = name
            item = {'name': name, 'controls': [], '_board': b, '_host': name}
            # Build draws a modal as the page beneath under black at alpha 166
            # and ignores its background, so a modal carries none.
            if pg.get('background') and not pg.get('modal'):
                item['background'] = pg['background']
            if pg.get('background_image') and pg['kind'] == 'page':
                item['background_image'] = pg['background_image']
                if pg.get('background_file'):
                    art[pg['background_image']] = pg['background_file']
                # Laid out as the template's own pages lay theirs out: Mach's
                # stretch their photo, Afterburn's fit theirs (the default).
                if profile.get('background_layout'):
                    item['background_layout'] = profile['background_layout']
            if pg.get('reached_by'):
                item['reached_by'] = pg['reached_by']
            if pg.get('does'):
                item['_does'] = pg['does']
            if pg['kind'] == 'popup':
                item['modal'] = bool(pg.get('modal'))
                if pg.get('group'):
                    item['group'] = pg['group']
                if not item['modal']:
                    item['size'] = pg.get('size')
                popups.append(item)
            else:
                if pg.get('start'):
                    if start:
                        problems.append(f'{b}: a second start page - {start!r} is one')
                    start = start or name
                pages.append(item)
            for s in out.get('stray') or []:
                problems.append(f"{b}: a {s['tag']} at {_box(s['rect'])} paints ({s['why']}) "
                                f'but is not a component - a panel cannot build it')
            # What the panel's layout derived: a Group's pages, as popups in
            # its box or pages of their own, each control in the one it is in.
            mine = [c for c in out['controls'] if c.get('part') is None]
            for i, prt in enumerate(out.get('parts') or []):
                d = json.loads(prt['gdl'])
                sub = {'name': d['name'], 'controls': [], '_board': b, '_derived': True, '_host': name,
                       '_raw': [c for c in out['controls'] if c.get('part') == i]}
                if d.get('kind') == 'popup':
                    # Its cells are drawn over the page, so it has no fill - as
                    # the seed's own group popups have none. Given none, a spec
                    # popup takes black, and Build drew a black box over the page.
                    sub.update(modal=False, group=d.get('group'), size=d.get('size'), background='none')
                    # Its group's first: nothing leads to it - it is what the
                    # region shows when the page comes up, which the program does.
                    if not any(x.get('group') == d.get('group') for x in popups):
                        sub['reached_by'] = 'program'
                    popups.append(sub)
                else:
                    if d.get('background'):
                        sub['background'] = d['background']
                    if d.get('background_image'):
                        sub['background_image'] = d['background_image']
                        if d.get('background_file'):
                            art[d['background_image']] = d['background_file']
                        if profile.get('background_layout'):
                            sub['background_layout'] = profile['background_layout']
                    pages.append(sub)
            item['_raw'] = mine
        if profile is None:
            return None, problems or ['no artboard has a Page'], notes

        colors = self._colors(profile, scheme)
        self.template = profile['template']
        # A slider's thumb is a kit image in the scheme's secondary accent. The
        # canvas draws it in that color; a clone would keep the donor's.
        thumb = designsys.slider_thumb(profile, scheme)
        # And its rail, where that is art: a clone's never survives the applier.
        rail = designsys.slider_rail(profile)
        # A border the panel's seed lacks is its own of that thickness (the
        # model table's `borders`: the 320's 7 Radius 2 Thick for the profile's
        # 10 Radius 2 Thick) - a spec may only name what its donor carries.
        swap = first.get('borders') or {}
        for item in pages + popups:
            item['controls'] = [c for c in (self._control(item['name'], raw, stems)
                                            for raw in item.pop('_raw')) if c]
            item.pop('_board')
            for c in item['controls']:
                if c.get('border') in swap:
                    c['border'] = swap[c['border']]
                for st in c.get('states') or []:
                    if isinstance(st, dict) and st.get('border') in swap:
                        st['border'] = swap[st['border']]
            for c in item['controls']:
                if c['kind'] == 'slider' and thumb:
                    c['thumb_image'] = thumb[0]
                if c['kind'] == 'slider':
                    c.update({k: f for k, (f, _) in rail.items()})
        wants_thumb = ((profile.get('defaults') or {}).get('slider') or {}).get('thumb_image')
        if wants_thumb and not thumb and any(c['kind'] == 'slider' for item in pages + popups
                                            for c in item['controls']):
            notes.append(f"no {profile['template']} kit thumb for scheme {scheme!r} on this "
                         f"machine - the sliders will build with the donor's thumb")
        used = sorted({v for item in pages + popups for v in _colors_in(item)})
        unknown = [u for u in used if u not in colors and not u.startswith('#')]
        for u in unknown:
            problems.append(f'color {u!r} is not an {profile["template"]} token')
        theme = {k: colors[k] for k in used if k in colors}
        theme.update(font=profile['font']['family'], text=colors.get('text', '#FFFFFF'))
        model, size, seed = profile['model'], list(profile['size']), profile['seed']
        listed = first.get('panels') if first.get('panel') else None
        if first.get('panel'):
            model = first['panel']
            size = list(gdlspec.MODELS[model])
            seed = first.get('seed')
        spec = {
            'name': self.index.get('title') or 'Panel',
            'model': model,
            'size': size,
            '_seed': seed,
            '_from': f"Claude Design canvas, {profile['template']} ({scheme})",
            # Every panel the canvas builds, the one it is drawn on first.
            **({'_panels': listed} if listed else {}),
            'theme': theme,
            'pages': pages,
            'popups': popups,
        }
        # An image goes with the file it comes from, relative to the resource
        # kits: the seed carries some already, and the applier appends the
        # rest. Background images are the themes'; button images the kit's.
        files = {th['image']: th['file'] for th in designsys.themes(profile)
                 if th.get('image') and th.get('file')}
        # A panel's own background art, named by its Page.
        files.update(art)
        used = {pg['background_image'] for pg in pages if pg.get('background_image')}
        buttons = {s['image'] for item in pages + popups for c in item['controls']
                   for s in c.get('states') or [] if isinstance(s, dict) and s.get('image')}
        buttons |= {c[k] for item in pages + popups for c in item['controls']
                    for k in ('thumb_image', 'track_image', 'fill_image') if c.get(k)}
        if buttons:
            files.update(designsys.kit_index(profile)['paths'])
            if thumb:
                files[thumb[0]] = thumb[1]
            files.update({f: path for f, path in rail.values()})
            for n in sorted(buttons - set(files)):
                problems.append(f'image {n!r} is not in the {profile["template"]} kit on this '
                                f'machine (vendor/extron/Resources or the install)')
        used |= buttons
        if used:
            spec['images'] = {n: files[n] for n in sorted(used) if n in files}
        seen = {}
        for item in pages + popups:
            if item['name'] in seen:
                problems.append(f"{item['name']!r} names two pages or popups - a derived one takes "
                                f'its page and group title, so the canvas has it twice')
            seen[item['name']] = item
        for item in pages + popups:
            item.pop('_derived', None)
            for c in item['controls']:
                if c.get('derived') and c.get('nav') and c['nav'] not in seen:
                    problems.append(f"{item['name']!r} {c.get('name')}: nav {c['nav']!r} is not a "
                                    'page or popup of this panel')
        if start:
            spec['start_page'] = start
        elif pages:
            notes.append(f"no Page is marked start - the first, {pages[0]['name']!r}, is")
        return spec, problems, notes

    def _profile(self, template):
        for t in designsys.TEMPLATES:
            p = designsys.load(t)
            if p['template'] == template:
                return p
        raise ValueError(f'no design-system profile for template {template!r}')

    @staticmethod
    def _colors(profile, scheme):
        """Token -> spec color for one scheme.

        A design token is CSS, so an 8-digit value is #RRGGBBAA - alpha LAST.
        The spec reads #AARRGGBB, alpha FIRST, as GUI Designer's ARGB does.
        Passed through unchanged, Afterburn's scrim #242634CC would build as
        alpha 0x24 over #2634CC.
        """
        first = profile['schemes'][0]['id']
        out = {}
        for c in profile['colors']:
            v = c['value']
            out[c['name']] = v.get(scheme) or v[first] if isinstance(v, dict) else v
        for k, v in out.items():
            if v.startswith('{'):
                out[k] = out[v[1:-1]]
        return {k: css_to_argb(v) for k, v in out.items()}

    def _control(self, page, raw, stems):
        g = json.loads(raw['gdl'])
        kind = g.get('kind')
        where = f"{page!r} {g.get('name') or kind}"
        if kind not in FIELDS:
            self.problems.append(f'{where}: {kind!r} is not a control the spec builds')
            return None
        c = {'kind': kind}
        if g.get('name'):
            c['name'] = g['name']
        c['rect'] = [round(v) for v in raw['rect']]
        if raw.get('overflow'):
            # The probe saw its text spill past its box at this panel's type.
            self.problems.append(f"{where}: its text does not fit its {c['rect'][2]}x{c['rect'][3]} box "
                                 'on this panel - give it room, or fewer words')
        for k in FIELDS[kind]:
            # `none` is how a design switches a color off: no key at all. A
            # border of `none` is a value - no border - and is kept.
            if k in g and (g[k] != 'none' or k == 'border'):
                c[k] = g[k]
        if kind == 'button':
            for m in g.get('missing_icon') or []:
                size, icon = m.split(' ', 1)
                self.problems.append(f"{where}: icon {icon!r} is not in {self.template}'s "
                                     f'{size} kit')
            if 'states' in c:
                c['states'] = [_state(s) for s in c['states']]
            if 'nav' in c and g.get('derived'):
                pass  # a page or popup this panel's layout derived: checked once all are known
            elif 'nav' in c:
                target = stems.get(re.sub(r'\.dc\.html$', '', str(c['nav'])))
                if target is None:
                    self.problems.append(f"{where}: nav {c['nav']!r} names no artboard")
                    del c['nav']
                else:
                    c['nav'] = target
        return c


def css_to_argb(v):
    """'#RRGGBBAA' (CSS) -> '#AARRGGBB' (the spec). Six digits pass through."""
    if isinstance(v, str) and re.fullmatch(r'#[0-9A-Fa-f]{8}', v):
        return '#' + v[7:9] + v[1:7]
    return v


def _state(s):
    if isinstance(s, str):
        return s
    # In a state, `none` is an instruction - this state has no fill, outline
    # or image - where on the control it only means "no override". Dropped,
    # the state fell back to the button's own fill.
    look = {k: s[k] for k in STATE_LOOK if k in s}
    return dict(name=s.get('name'), **look) if look else s.get('name')


def _colors_in(item):
    # A derived popup's `none` background is transparent, not a token.
    if item.get('background') and item['background'] != 'none':
        yield item['background']
    for c in item['controls']:
        for k in COLOR_KEYS:
            if c.get(k):
                yield c[k]
        for s in c.get('states') or []:
            if isinstance(s, dict):
                for k in COLOR_KEYS:
                    # `none` is transparent, not a token.
                    if s.get(k) and s[k] != 'none':
                        yield s[k]


def _box(r):
    return f'{round(r[0])},{round(r[1])} {round(r[2])}x{round(r[3])}'


# Derived controls - a Group's Previous, Next and Back, a level's Up and Down -
# take IDs from here up, the same ID for the same control on every panel. Far
# above any page's band (1000 a page) and any popup's (9000 + 100 a popup).
DERIVED_IDS = 50001


def pin_ids(specs, order):
    """One ID per canvas control on every panel - {model: [problems]}.

    A program drives every panel with one set of IDs. So each canvas control's
    ID is allocated once, on the panel the canvas is drawn on (`order[0]`), in
    its page's band as Panel would - 1001 up on the first page, 9001 up on the
    first popup - and written onto that control on every panel, wherever its
    layout put it there. A control is known by its page and its name, so on a
    canvas of several panels an addressable control without a name is refused.
    What a panel's layout added (`derived`) gets an ID from DERIVED_IDS up, by
    its container and name, the same on every panel it is on.
    """
    problems = {m: [] for m in specs}
    design = specs[order[0]]
    canvas_items = [it for it in design['pages'] + design['popups'] if it['_host'] == it['name']]
    bands, pages_seen, popups_seen = {}, 0, 0
    for it in canvas_items:
        if it in design['pages']:
            bands[it['name']] = 1000 * (pages_seen + 1) + 1
            pages_seen += 1
        else:
            bands[it['name']] = 9000 + 100 * popups_seen + 1
            popups_seen += 1
    taken = {c['id'] for spec in specs.values() for it in spec['pages'] + spec['popups']
             for c in it['controls'] if c.get('id')}

    def key(it, c, seen):
        if c.get('name'):
            return (it['_host'], c['name'])
        n = seen.setdefault((it['_host'], c['kind']), 0)
        seen[(it['_host'], c['kind'])] += 1
        return (it['_host'], f"<{c['kind']} {n}>")

    ids, nxt, seen = {}, dict(bands), {}
    for it in design['pages'] + design['popups']:
        for c in it['controls']:
            if c.get('derived'):
                continue
            if not c.get('name') and c['kind'] in ('button', 'label', 'slider', 'level') and len(specs) > 1:
                problems[order[0]].append(f"{it['name']!r}: a {c['kind']} with no name - name it, so it "
                                          'keeps its ID on every panel')
                continue
            k = key(it, c, seen)
            if c.get('id'):
                ids[k] = c['id']
                continue
            n = nxt.get(it['_host'], 1)
            while n in taken:
                n += 1
            ids[k] = n
            taken.add(n)
            nxt[it['_host']] = n + 1
    derived = sorted({(it['name'], c['name']) for spec in specs.values()
                      for it in spec['pages'] + spec['popups'] for c in it['controls']
                      if c.get('derived') and c.get('name')})
    did, n = {}, DERIVED_IDS
    for k in derived:
        while n in taken:
            n += 1
        did[k] = n
        taken.add(n)
        n += 1
    for model, spec in specs.items():
        found, seen = set(), {}
        for it in spec['pages'] + spec['popups']:
            for c in it['controls']:
                if c.get('derived'):
                    c['id'] = did[(it['name'], c['name'])]
                    continue
                if not c.get('name') and c['kind'] in ('button', 'label', 'slider', 'level') and len(specs) > 1:
                    continue
                k = key(it, c, seen)
                if k not in ids:
                    problems[model].append(f"{it['name']!r} {c.get('name') or c['kind']}: on this panel but "
                                           f'not on the {order[0]} the canvas is drawn on')
                    continue
                c['id'] = ids[k]
                found.add(k)
        for k in sorted(set(ids) - found):
            problems[model].append(f'{k[1]} on {k[0]!r} is on the {order[0]} and not here - nothing is '
                                   'dropped from a panel')
    return problems


def clear_panels(out_dir, keep=()):
    """Remove every <out_dir>/<model>/spec.json but `keep`'s; the paths removed.

    A spec an earlier translate wrote, for a panel the canvas has since dropped
    or from a run that has since failed, was read by the ID map and built by
    New-GdlPanels.ps1 as if it were this canvas's. Built files stay.
    """
    gone = []
    if not os.path.isdir(out_dir):
        return gone
    for m in sorted(os.listdir(out_dir)):
        f = os.path.join(out_dir, m, 'spec.json')
        if m not in keep and os.path.isfile(f):
            os.remove(f)
            gone.append(f)
    return gone


def write_panels(specs, out_dir):
    """Each panel's spec to <out_dir>/<model>/spec.json, and no other panel's
    left there; the paths written."""
    clear_panels(out_dir, keep=set(specs))
    written = []
    for model, spec in specs.items():
        d = os.path.join(out_dir, model)
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, 'spec.json')
        with open(f, 'w', encoding='utf-8') as fh:
            json.dump(spec, fh, indent=2, ensure_ascii=False)
        written.append(f)
    return written


def screenshot(board_path, chrome, size, png, timeout=90):
    """The artboard as the designer sees it, at its own size."""
    subprocess.run(
        [chrome, '--headless=new', '--disable-gpu', '--allow-file-access-from-files',
         '--hide-scrollbars', '--virtual-time-budget=15000',
         f'--window-size={size[0]},{size[1]}', f'--screenshot={os.path.abspath(png)}',
         'file:///' + os.path.abspath(board_path).replace('\\', '/').lstrip('/')],
        capture_output=True, timeout=timeout)
    if not os.path.exists(png):
        raise RuntimeError(f'{os.path.basename(board_path)}: no screenshot')


def _as_panel(board_path, panel, show=None):
    """A copy of an artboard set to draw as `panel`, with one of its derived
    pages or popups showing - what the canvas's Play shows after a tap."""
    with open(board_path, encoding='utf-8') as fh:
        src = fh.read()
    sets = f'window.__GDL_PANEL = {json.dumps(panel)};' + (f' window.__GDL_SHOW = {json.dumps(show)};' if show else '')
    tag = re.sub(r'[^A-Za-z0-9]', '_', f"{panel}_{show or ''}")
    copy = os.path.join(os.path.dirname(board_path), f'__gdl_shot_{tag}_' + os.path.basename(board_path))
    with open(copy, 'w', encoding='utf-8') as fh:
        fh.write(src.replace('<head>', f'<head>\n<script>{sets}</script>', 1) if '<head>' in src else src)
    return copy


class _Built:
    """A built panel, rendered the way gdl.compose does: what the panel shows."""

    def __init__(self, built):
        from .compose import fill_index, load  # Pillow
        self.j, self.assets = load(built)
        self.fills = fill_index(built)
        self.by_name = {p['Name']: p for p in self.j['Pages'] + self.j['PopupPages']}

    def image(self, name, size, host=None):
        """The page or popup `name` as the panel shows it: a modal over the
        start page under Build's scrim; a group's popup in its host page's
        region; anything else on its own."""
        from .compose import render_page, render_snapshot
        from PIL import Image
        import io
        pg = self.by_name.get(name)
        if pg is None:
            return None
        psize = (pg.get('Width') or size[0], pg.get('Height') or size[1])
        j, assets, fills = self.j, self.assets, self.fills
        if pg.get('Modal'):
            start = j.get('DefaultPage') or j['Pages'][0]['ID']
            img = render_snapshot(j, start, assets, psize, fills=fills).convert('RGBA')
            if pg.get('TLPImageID', -1) in assets:
                scrim = Image.open(io.BytesIO(assets[pg['TLPImageID']])).convert('RGBA')
                img = Image.alpha_composite(img, scrim.resize(img.size))
            bare = dict(pg, TLPImageID=-1, BackgroundFillColor=None)
            top = render_page(bare, assets, psize, fills=fills, flat=False)
            return Image.alpha_composite(img, top).convert('RGB')
        hp = self.by_name.get(host) if host else None
        if hp is not None and pg.get('GroupID'):
            hsize = (hp.get('Width') or size[0], hp.get('Height') or size[1])
            return render_snapshot(j, hp['ID'], assets, hsize, shown={pg['GroupID']: pg['ID']}, fills=fills)
        return render_snapshot(j, pg['ID'], assets, psize, fills=fills)


def _pair(rows, scores, out_dir, stem, name, design_png, built_img):
    from .compose import diff_stats
    from PIL import Image
    if built_img is None:
        rows.append((name, os.path.basename(design_png), None, None))
        return
    built_png = os.path.join(out_dir, f'{stem}-built.png')
    built_img.save(built_png)
    a = Image.open(design_png).convert('RGB')
    pct = diff_stats(a.resize(built_img.size) if a.size != built_img.size else a, built_img)['pct_bad']
    rows.append((name, os.path.basename(design_png), os.path.basename(built_png), pct))
    scores.append((name, pct))


def _cells(rows, prefix=''):
    return ''.join(
        f'<div class="pairbox"><h3>{html.escape(n)}</h3><div class="pair">'
        f'<figure><img src="{prefix}{d}" alt="{html.escape(n)} as designed"><figcaption>Designed'
        f'</figcaption></figure>'
        + (f'<figure><img src="{prefix}{bpng}" alt="{html.escape(n)} as built"><figcaption>Built'
           f' &middot; {pct:.1f}% of pixels differ</figcaption></figure>' if bpng else
           '<figure><figcaption>Not in the built file</figcaption></figure>')
        + '</div></div>' for n, d, bpng, pct in rows)


def _page(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{html.escape(title)} - designed and built</title>
<style>
body{{margin:0;padding:24px;font:15px/1.4 system-ui,sans-serif;background:#16171d;color:#e8e8ee}}
h1{{font-size:22px;margin:0 0 20px}} h2{{font-size:19px;margin:36px 0 6px}} h3{{font-size:16px;margin:22px 0 10px}}
.pair{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}
figure{{margin:0}} img{{width:100%;height:auto;display:block;border:1px solid #33343f}}
figcaption{{margin-top:6px;color:#a9aab8}} .note{{color:#a9aab8;margin:0 0 8px}}
@media (max-width:700px){{.pair{{grid-template-columns:1fr}}}}
</style></head><body><h1>{html.escape(title)}</h1>
{body}
</body></html>
"""


def compare(folder, built, out_dir, chrome=None):
    """Each artboard beside the page GUI Designer built from it, for sign-off.

    Claude Design does not draw like GUI Designer, so a client signs off on
    the built panel, not on the canvas. The built side is gdl.compose's render
    of the built file's own artwork - scored against GUI Designer's snapshots
    (CLAUDE.md, Verifying a change) - so what shows there is what the panel
    shows. Writes <out_dir>/index.html and a PNG pair per artboard; returns
    [(page name, % of pixels that differ)].

    `built` may be a folder of panels - <model>/<panel>.gdl, as
    New-GdlPanels.ps1 writes them - and then the page has a section per panel:
    each artboard drawn for that panel, and each page or popup its layout
    derived (a Group's) shown as Play shows it after a tap, beside it as built.
    """
    if os.path.isdir(built):
        return compare_panels(folder, built, out_dir, chrome)
    canvas = Canvas(folder, chrome)
    if not canvas.chrome:
        raise RuntimeError('no Chrome found - pass --chrome or set CHROME')
    b_ = _Built(built)
    os.makedirs(out_dir, exist_ok=True)
    rows, scores = [], []
    for b in canvas.boards():
        size = canvas._size(b)
        stem = re.sub(r'[^A-Za-z0-9_.-]', '_', b.rsplit('.dc.html', 1)[0])
        path = os.path.join(folder, *b.split('/'))
        out = render(path, canvas.chrome, size)
        name = json.loads(out['page']['gdl']).get('name') if out.get('page') else None
        design_png = os.path.join(out_dir, f'{stem}-design.png')
        screenshot(path, canvas.chrome, size, design_png)
        _pair(rows, scores, out_dir, stem, name or b, design_png, b_.image(name, size) if name else None)
    body = ''.join(f'<section>{_cells([r])}</section>' for r in rows)
    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(_page(canvas.index.get('title') or 'Panel', body))
    return scores


def compare_panels(folder, built_dir, out_dir, chrome=None):
    """compare() for a canvas of panels: a section per panel."""
    canvas = Canvas(folder, chrome)
    if not canvas.chrome:
        raise RuntimeError('no Chrome found - pass --chrome or set CHROME')
    found = {}
    for m in sorted(os.listdir(built_dir)):
        d = os.path.join(built_dir, m)
        gdls = [f for f in os.listdir(d) if f.lower().endswith('.gdl')] if os.path.isdir(d) else []
        if len(gdls) == 1:
            found[m] = os.path.join(d, gdls[0])
    first = render(os.path.join(folder, *canvas.boards()[0].split('/')), canvas.chrome,
                   canvas._size(canvas.boards()[0]))
    listed = Canvas._panels_of({'b': first}) or list(found)
    models = [m for m in listed if m in found] + [m for m in found if m not in listed]
    scores, sections = [], []
    for m in models:
        sub = os.path.join(out_dir, m)
        os.makedirs(sub, exist_ok=True)
        b_ = _Built(found[m])
        rows = []
        size = tuple(gdlspec.MODELS[m]) if m in gdlspec.MODELS else (1280, 800)
        for b in canvas.boards():
            path = os.path.join(folder, *b.split('/'))
            stem = re.sub(r'[^A-Za-z0-9_.-]', '_', b.rsplit('.dc.html', 1)[0])
            out = render(path, canvas.chrome, canvas._size(b), panel=m)
            pg = json.loads(out['page']['gdl']) if out.get('page') else {}
            name = pg.get('name') or b
            psize = tuple(pg.get('size') or size)
            shots = [(name, None, None)]
            for prt in out.get('parts') or []:
                d = json.loads(prt['gdl'])
                shots.append((d['name'], d['name'], name if d.get('kind') == 'popup' else None))
            for label, show, host in shots:
                copy = _as_panel(path, m, show)
                try:
                    png = os.path.join(sub, re.sub(r'[^A-Za-z0-9_.-]', '_', f"{stem}-{show or 'page'}") + '-design.png')
                    screenshot(copy, canvas.chrome, psize, png)
                finally:
                    if os.path.exists(copy):
                        os.remove(copy)
                tag = re.sub(r'[^A-Za-z0-9_.-]', '_', f"{stem}-{show or 'page'}")
                _pair(rows, scores, sub, tag, label, png, b_.image(label, psize, host))
        sections.append(f'<section class="panel"><h2>{html.escape(m)} '
                        f'&middot; {size[0]}x{size[1]}</h2>'
                        f'<p class="note">Built: {html.escape(os.path.basename(found[m]))}</p>'
                        f'{_cells(rows, m + "/")}</section>')
    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(_page((canvas.index.get('title') or 'Panel') + ', every panel', ''.join(sections)))
    return scores


def main(argv):
    if len(argv) >= 5 and argv[1] == 'compare':
        chrome = argv[argv.index('--chrome') + 1] if '--chrome' in argv else None
        for name, pct in compare(argv[2], argv[3], argv[4], chrome):
            print(f'  {pct:5.1f}%  {name}')
        print(f"-> {os.path.join(argv[4], 'index.html')}")
        return 0
    if len(argv) < 4 or argv[1] != 'translate':
        print(__doc__.strip().split('\n\n')[0])
        print('\n  python -m gdl.design translate <canvas dir> <out dir>        one spec per panel'
              '\n  python -m gdl.design translate <canvas dir> <out spec.json>  the design panel only'
              ' [--lenient]'
              '\n      [--chrome PATH]'
              '\n  python -m gdl.design compare <canvas dir> <built.gdl> <out dir>')
        return 2
    chrome = argv[argv.index('--chrome') + 1] if '--chrome' in argv else None
    canvas = Canvas(argv[2], chrome)
    if not argv[3].lower().endswith('.json'):
        # One spec per panel the canvas lists, each in its own folder - or none.
        specs, problems, notes = canvas.translate_panels()
        for ns in notes.values():
            for n in ns:
                print('  note    ' + n)
        for ps in problems.values():
            for p in ps:
                print('  PROBLEM ' + p)
        if specs is None:
            bad = [m for m, ps in problems.items() if ps]
            print(f"{sum(len(ps) for ps in problems.values())} problem(s) on "
                  f"{', '.join(bad) or 'the canvas'} - no spec written for any panel")
            # And none left from an earlier run, to be mapped and built as this one.
            for f in clear_panels(argv[3]):
                print(f'  removed {f}, an earlier run\'s')
            return 1
        for f, (model, spec) in zip(write_panels(specs, argv[3]), specs.items()):
            n = sum(len(p['controls']) for p in spec['pages'] + spec['popups'])
            print(f"{model}: {len(spec['pages'])} page(s), {len(spec['popups'])} popup(s), "
                  f"{n} controls -> {f}")
            print(f"  donor: {spec['_seed']}")
        return 0
    spec, problems, notes = canvas.translate()
    for n in notes:
        print('  note    ' + n)
    for p in problems:
        print('  PROBLEM ' + p)
    if spec is None or (problems and '--lenient' not in argv):
        print(f'{len(problems)} problem(s) - no spec written'
              + ('' if spec is None else '; --lenient writes it without what could not '
                 'be translated'))
        return 1
    with open(argv[3], 'w', encoding='utf-8') as fh:
        json.dump(spec, fh, indent=2, ensure_ascii=False)
    n = sum(len(p['controls']) for p in spec['pages'] + spec['popups'])
    print(f"{len(spec['pages'])} page(s), {len(spec['popups'])} popup(s), {n} controls "
          f'-> {argv[3]}')
    print(f"donor: {spec['_seed']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
