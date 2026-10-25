"""Turn a Design canvas into a spec - one for each panel it lists.

    python -m gdl.design translate <canvas dir> <out dir>         # out/<panel>/spec.json
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
import datetime
import hashlib
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
               'states', 'press', 'nav', 'does', 'derived', 'joined', 'back'),
    'label': ('id', 'text', 'color', 'size', 'bold', 'align', 'does', 'derived'),
    'panel': ('fill', 'stroke', 'border', 'derived'),
    'line': ('fill', 'thickness', 'from', 'to'),
    # A slider's `joined`: the right rail's volume group, heading, slider and
    # Mute, is one set as the template stands it (gdl.spec's gap rule).
    'slider': ('id', 'fill', 'border', 'orientation', 'track', 'thumb', 'thumb_height', 'does', 'joined'),
    'level': ('id', 'fill', 'border', 'orientation', 'track', 'bar', 'does'),
    'datetime': ('color', 'size', 'bold', 'align', 'format'),
    'popup_ref': ('group', 'derived'),
    # The template's own art (bundle.js's Image, and the art a region draws:
    # Turbulence's bars, a source's device picture), by its kit file.
    'image': ('image', 'layout', 'fill', 'derived'),
}
COLOR_KEYS = ('fill', 'stroke', 'color', 'bar')
# The kinds a program addresses by ID (gdl.idmap): those a seed ID is kept on.
ID_KINDS = ('button', 'label', 'slider', 'level')
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
  // A label's and a clock's words, boxed on their own: the box drawn round
  // them is often bigger, and overlapping a button is harmless where the
  // words are clear of it (the translator's _collisions).
  var WORDS = { label: 1, datetime: 1 };
  function wordsBox(el, ox, oy) {
    var rg = document.createRange();
    rg.selectNodeContents(el);
    var t = rg.getBoundingClientRect();
    return t.width > 0 && t.height > 0 ? [t.left - ox, t.top - oy, t.width, t.height] : null;
  }
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
    var out = { pages: 0, controls: [], stray: [], parts: [], problems: [], warnings: [] };
    for (var p of pages) { var k = JSON.parse(p.getAttribute('data-gdl')).kind; if (k === 'page' || k === 'popup') out.pages++; }
    // What the components found they could not lay out on this panel.
    for (var q of document.querySelectorAll('[data-gdl-problem]')) out.problems.push(q.getAttribute('data-gdl-problem'));
    // What they drew but would draw otherwise - a region page missing a
    // region the template always has: a note, never a refusal.
    for (var q of document.querySelectorAll('[data-gdl-warning]')) out.warnings.push(q.getAttribute('data-gdl-warning'));
    if (page) {
      var o = page.getBoundingClientRect();
      // `outlined`: drawn with the canvas's problem outline (bundle.js
      // outlined()), which a warning the template's own grammar makes does
      // not draw.
      out.page = { gdl: page.getAttribute('data-gdl'), rect: [0, 0, o.width, o.height],
                   outlined: getComputedStyle(page).outlineStyle !== 'none' };
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
          if (WORDS[g.kind]) {
            var wb = wordsBox(el, at >= 0 ? pr[at].left : o.left, at >= 0 ? pr[at].top : o.top);
            if (wb) {
              c.text_rect = wb;
              // Its em as it shows: a scaled container's text is drawn smaller.
              c.text_em = parseFloat(getComputedStyle(el).fontSize) * (el.offsetHeight ? r.height / el.offsetHeight : 1);
            }
          }
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
    `panel` is the panel to lay it out for (gdl.spec.panel_id): set before
    the design system loads, as `window.__GDL_PANEL`, which a Page that lists
    panels derives for (docs/claude-design.md section 2). Without it, the
    design panel.
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


# The Design type's runtimes the Chrome suite has passed on (dc_runtime.json).
# The translator lays a canvas out with the runtime the canvas itself serves,
# and that runtime is the Design type's to change, release by release - its
# markup, its index and how it renders are all this translator reads. One the
# suite has not passed on is refused by name, so a change shows up as that
# rather than as a canvas that translates wrong.
RUNTIMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dc_runtime.json')
# Where each pinned runtime is kept, in the private archive (not the public copy).
ARCHIVE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'archive', 'dc-runtime')


def runtime_sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def proven_runtimes():
    with open(RUNTIMES, encoding='utf-8') as fh:
        return {r['sha256']: r for r in json.load(fh)['proven']}


def runtime_problem(folder):
    """A problem naming the canvas's runtime (its support.js) if the suite
    has not passed on it, else None."""
    path = os.path.join(folder, 'support.js')
    if not os.path.exists(path):
        return None
    sha = runtime_sha(path)
    if sha in proven_runtimes():
        return None
    return (f"this canvas's Design runtime (support.js, sha256 {sha[:12]}) is not one the toolkit has "
            'been proven on (gdl/dc_runtime.json): the Design type has changed. Run the Chrome suite '
            f'with GDL_DC_RUNTIME={path}, and when it passes, python -m gdl.design pin-runtime {path} '
            '--seen <where it came from>; or translate with --new-runtime, and the build gates still verify')


def pin_runtime(path, seen, suite=None):
    """Add `path`'s runtime to dc_runtime.json, and keep a copy of it in the
    archive where there is one; returns its entry."""
    with open(RUNTIMES, encoding='utf-8') as fh:
        data = json.load(fh)
    sha = runtime_sha(path)
    if os.path.isdir(os.path.dirname(ARCHIVE)):
        keep = os.path.join(ARCHIVE, sha[:16])
        os.makedirs(keep, exist_ok=True)
        shutil.copyfile(path, os.path.join(keep, 'dc-runtime.js'))
    for r in data['proven']:
        if r['sha256'] == sha:
            return r
    entry = {'sha256': sha, 'bytes': os.path.getsize(path),
             'proven': datetime.date.today().isoformat(), 'seen': seen}
    if suite:
        entry['suite'] = suite
    data['proven'].append(entry)
    with open(RUNTIMES, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write('\n')
    return entry


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
        if spec is not None:
            if not self._seed_has_line(spec):
                notes = notes + lines_as_shapes(spec)
            # A region page's chrome keeps its seed IDs and a mirror its
            # control's, as on a canvas of panels; nothing else is pinned here.
            if any('_seed_id' in c or '_mirror' in c for it in spec['pages'] + spec['popups']
                   for c in it['controls']):
                problems = problems + pin_ids({'': spec}, [''])['']
            problems = problems + _spec_check(spec, self._seed_geometry(spec), problems)
        for item in (spec or {}).get('pages', []) + (spec or {}).get('popups', []):
            item.pop('_host', None)
        return spec, problems, notes

    def translate_panels(self, rendered=None):
        """({panel: spec} or None, {panel: problems}, {panel: notes}) - one spec
        per panel the canvas's Pages list, each laid out for its panel by the
        design system (window.__GDL_PANEL). All or nothing: any panel with a
        problem means no specs. A canvas that lists no panels is its profile's
        one design panel. `rendered` maps panel -> board -> probe output, for
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
        # The first panel listed is the one the canvas is drawn on: what met
        # there was drawn so.
        drawn = next(iter(rendered.values()), {})
        for m, boards in rendered.items():
            self.problems, self.notes = [], []
            spec, probs, nts = self._spec(boards)
            if boards is not drawn:
                for b, o in boards.items():
                    probs = probs + _collisions(drawn.get(b), o)
            key = m or (spec or {}).get('model') or ''
            if m and spec is not None and _panel(spec) != m:
                probs = probs + [f"laid out for the {_panel(spec)}, not the {m} - remove the "
                                 f"Pages' `preview` before translating, or set it to {m}"]
            if spec is not None:
                self._seed_rules(spec, key, probs)
            problems[key] = [f'{key}: {q}' if key else q for q in probs]
            notes[key] = [f'{key}: {q}' if key else q for q in nts]
            specs[key] = spec
        # Before the IDs are pinned, which number unnamed controls by kind.
        for model, q in lines_everywhere(specs, self._seed_has_line).items():
            notes[model] += [f'{model}: {x}' if model else x for x in q]
        if not any(problems.values()) and all(v is not None for v in specs.values()):
            for model, q in pin_ids(specs, list(specs)).items():
                problems[model] += [f'{model}: {x}' if model else x for x in q]
        # Each panel's spec as `gdl.spec check` sees it - the touch minimum,
        # the floor, the spacing a grown caption may have broken - here,
        # before a build is ever started, and for every panel drawn whatever
        # else is wrong: checked only on a clean canvas, a designer who revised
        # for what one read named met a new list in the next.
        for model, spec in specs.items():
            if spec is None:
                continue
            problems[model] += [f'{model}: {x}' if model else x
                                for x in _spec_check(spec, self._seed_geometry(spec), problems[model])]
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
    # seed -> whether it carries a PBLine to clone.
    _SEED_LINES = {}
    # seed -> its own border geometry (Project.border_geometry).
    _SEED_GEOMETRY = {}

    def _seed_geometry(self, spec):
        """The seed's border geometry, or None where the seed is not here: a
        stroke is drawn only on a border the seed gives a thickness."""
        seed = spec.get('_seed')
        if not seed or not seeds.usable(seed):
            return None
        if seed not in self._SEED_GEOMETRY:
            from .project import Project
            self._SEED_GEOMETRY[seed] = Project.open(seeds.path(seed)).border_geometry()
        return self._SEED_GEOMETRY[seed]

    def _seed_has_line(self, spec):
        """Whether the spec's seed carries a PBLine to clone - the donor check
        refuses a line otherwise. True where the seed is not here to say."""
        seed = spec.get('_seed')
        if not seed or not seeds.usable(seed):
            return True
        if seed not in self._SEED_LINES:
            from .project import Project
            self._SEED_LINES[seed] = any(True for _ in Project.open(seeds.path(seed)).instances('PBLine'))
        return self._SEED_LINES[seed]

    def _seed_rules(self, spec, model, problems):
        """A panel builds on its own seed: it must be here, and nothing the
        layout derived may take a name the seed already has."""
        seed = spec.get('_seed')
        theme = self.template or 'Afterburn'
        # `model` names the panel; the seed is made for its model at its canvas.
        at = (spec.get('model'), spec.get('size'))
        if not seed:
            problems.append(f'no seed for a {model} - make one: {seeds.command(theme, at[0], None, at[1])} - '
                            f'{seeds.listing(theme)}')
            return
        if not seeds.usable(seed):
            problems.append(f'its seed {seed} is not here (or is a Git LFS pointer - git lfs pull) - '
                            f'make it: {seeds.command(theme, at[0], seed, at[1])}')
            return
        if seed not in self._SEED_NAMES:
            # The specs this writes never keep the seed's pages, so the applier
            # drops them all but the one it keeps (gdl.spec.kept_names).
            from .project import Project
            self._SEED_NAMES[seed] = gdlspec.kept_names(Project.open(seeds.path(seed)).pages())
        taken = self._SEED_NAMES[seed]
        for item in spec['pages'] + spec['popups']:
            if item['name'] in taken:
                problems.append(f"{item['name']!r} is a page of the seed {seed} that the built panel "
                                'keeps - rename it, or Build refuses the duplicate')

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
            for q in out.get('warnings') or []:
                notes.append(f'{b}: {q}')
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
            # A page's photo - and a hub popup's, which Shockwave's and
            # Turbulence's draw on the page's own (bundle.js, regions.hub.popup.photo).
            if pg.get('background_image') and (pg['kind'] == 'page' or not pg.get('modal')):
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
            # What this panel's template has no place for, which its layout
            # named rather than drew (a hub's footer clock): pin_ids and the
            # ID map let it be absent here, and the canvas's warning says why.
            if pg.get('left'):
                item['left'] = list(pg['left'])
            # A hub's source or settings popup (bundle.js hubPart): shown from
            # the Select a Source a region page derives there, and - a
            # settings window naming no group - in that page's main group.
            if pg.get('hub'):
                item['_hub'] = pg['hub']
            if pg.get('main_group'):
                item['_main_group'] = True
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
                if d.get('kind') == 'popup' and d.get('modal'):
                    # A modal the panel's layout derived - the 320's Volume,
                    # which the program shows - over the whole screen.
                    sub.update(modal=True)
                    if d.get('reached_by'):
                        sub['reached_by'] = d['reached_by']
                    popups.append(sub)
                elif d.get('kind') == 'popup':
                    # Its cells are drawn over the page, so it has no fill - as
                    # the seed's own group popups have none. Given none, a spec
                    # popup takes black, and Build drew a black box over the page.
                    # A hub's settings popups are opaque, as Mach's #303030
                    # draws them, and carry the fill their layout gives them.
                    sub.update(modal=False, group=d.get('group'), size=d.get('size'),
                               background=d.get('background') or 'none')
                    # A hub's options and display popups on the page's photo,
                    # as Shockwave's and Turbulence's own are.
                    if d.get('background_image'):
                        sub['background_image'] = d['background_image']
                        if d.get('background_file'):
                            art[d['background_image']] = d['background_file']
                        if profile.get('background_layout'):
                            sub['background_layout'] = profile['background_layout']
                    # Its group's first of what this page derived: nothing
                    # leads to it - it is what the region shows when the page
                    # comes up, which the program does. Only this page's parts
                    # count: a hub's source popups and settings are in its
                    # Select a Source's group too, and one whose board stood
                    # before Main's took the flag from it.
                    if not any(x.get('group') == d.get('group') and x.get('_derived') and x['_host'] == name
                               for x in popups):
                        sub['reached_by'] = 'program'
                    if d.get('main'):
                        sub['_main'] = True
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
        # A hub's settings popups go in the group main's popup region shows -
        # the Center's, which the derived Select a Source carries - not a
        # literal 'Sources': a canvas whose Center says group="Room" was
        # refused on every hub.
        mains = [x['group'] for x in popups if x.get('_main') and x.get('group')]
        for x in popups:
            if x.pop('_main_group', None) and mains:
                x['group'] = mains[0]

        colors = self._colors(profile, scheme)
        self.template = profile['template']
        # A slider's thumb is a kit image in the scheme's secondary accent. The
        # canvas draws it in that color; a clone would keep the donor's.
        thumb = designsys.slider_thumb(profile, scheme)
        # And its rail, where that is art: a clone's never survives the applier.
        rail = designsys.slider_rail(profile)
        # A border the panel's seed lacks is its own of that thickness (the
        # model table's `borders`: the 320's 7 Radius 2 Thick for the profile's
        # 10 Radius 2 Thick), written into the spec as the plan would build it.
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
                if c['kind'] == 'button':
                    _fit_breaks(c, profile['pt'], profile['font']['family'])
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
            # A panel is its model, the other way up as model-Portrait or
            # model-Landscape (gdl.spec.panel_id): the spec is the model at its canvas.
            model, size = gdlspec.panel_of(first['panel'])
            size = list(size)
            seed = first.get('seed')
        spec = {
            'name': self.index.get('title') or 'Panel',
            'model': model,
            'size': size,
            '_seed': seed,
            '_from': f"Design canvas, {profile['template']} ({scheme})",
            # Every panel the canvas builds, the one it is drawn on first.
            **({'_panels': listed} if listed else {}),
            'theme': theme,
            # The template's own palette - every token the theme measured off
            # it - which the six-color cap exempts (gdl.spec check, p.49); and
            # the colours this panel's own template draws its chrome in, as
            # measured (its frame: the 320's #4B4B4C Volume strip and #E4EDF5
            # level, which no token is).
            '_template_colors': sorted({v for v in colors.values() if isinstance(v, str) and v.startswith('#')}
                                       | _frame_colors(designsys.models(profile).get(first.get('panel') or '',
                                                                                     {}).get('frame'))),
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
        used = {pg['background_image'] for pg in pages + popups if pg.get('background_image')}
        buttons = {s['image'] for item in pages + popups for c in item['controls']
                   for s in c.get('states') or [] if isinstance(s, dict) and s.get('image')}
        buttons |= {c['image'] for item in pages + popups for c in item['controls']
                    if c['kind'] == 'image' and c.get('image')}
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
        # A derived Back with no `nav` of its own (`back`: the 320's, from a
        # source, a window or the question, which is a page there) goes back
        # to the page that shows its page - the one page with a control that
        # leads to it. Only the canvas as a whole knows it; with none, or more
        # than one, it is the program's, as a window's Close is. A page's own
        # later pages lead back to it but do not show it: counted, Doc Cam's
        # 'DocCam 2' made two pages show DocCam, and its first Back went
        # nowhere - no way back to Main on screen.
        openers = {}
        for item in pages:
            for c in item['controls']:
                if c.get('nav') and c['nav'] not in (item['name'], item.get('_host')):
                    openers.setdefault(c['nav'], set()).add(item['name'])
        for item in pages + popups:
            for c in item['controls']:
                if not c.pop('back', None) or c.get('nav'):
                    continue
                whose = sorted(openers.get(item['name'], ()))
                if len(whose) == 1:
                    c['nav'] = whose[0]
                else:
                    notes.append(f"{item['name']!r} {c.get('name')}: "
                                 + (f"{', '.join(whose)} all show {item['name']!r}" if whose
                                    else f"nothing on this panel shows {item['name']!r}")
                                 + ' - it goes back where the program says')
        seen = {}
        for item in pages + popups:
            if item['name'] in seen:
                problems.append(f"{item['name']!r} names two pages or popups - a derived one takes "
                                f'its page and group title, so the canvas has it twice')
            seen[item['name']] = item
        for item in pages + popups:
            item.pop('_derived', None)
            item.pop('_main', None)
            hub = item.pop('_hub', None)
            for c in item['controls']:
                if c.get('derived') and c.get('nav') and c['nav'] not in seen:
                    if hub:
                        # Its Close goes back to the grid a region page derives
                        # on the hub; with no region page there is none.
                        what = 'a source popup' if hub == 'source' else 'a settings window'
                        problems.append(f"{item['name']!r} is {what}, which a {model} shows in main from the "
                                        f"{c['nav']!r} a region page derives there - draw a working page with a "
                                        'Center (and its Header) on the canvas')
                    else:
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
        # The translator's own, which pin_ids reads and takes off: the
        # template's seed ID a region's fixed chrome keeps where it is free
        # (`seed_id`: Help 8117 on the bar themes), and the control a copy
        # the layout drew mirrors under its ID (`mirror`: Shockwave's tab
        # twin, the caption under the 1035's tab).
        if kind in ID_KINDS and isinstance(g.get('seed_id'), int):
            c['_seed_id'] = g['seed_id']
        if kind == 'button' and g.get('mirror'):
            c['_mirror'] = str(g['mirror'])
        if kind == 'button':
            for m in g.get('missing_icon') or []:
                size, icon = m.split(' ', 1)
                self.problems.append(f"{where}: icon {icon!r} is not in {self.template}'s "
                                     f'{size} kit')
            if 'states' in c:
                c['states'] = [_state(s) for s in c['states']]
            if 'nav' in c and g.get('derived') and not g.get('mirror'):
                pass  # a page or popup this panel's layout derived: checked once all are known
            elif 'nav' in c:
                target = stems.get(re.sub(r'\.dc\.html$', '', str(c['nav'])))
                if target is None:
                    self.problems.append(f"{where}: nav {c['nav']!r} names no artboard")
                    del c['nav']
                else:
                    c['nav'] = target
        return c


def _line_px(family, bold, px):
    """A caption line as GUI Designer lays it out: the face's usWinAscent +
    usWinDescent at that size - 1.362 em for Open Sans, where the canvas's line
    box is 1.2 em. The Mach 725's built tiles show it: a caption one break
    shorter moved 15 px, half a 30 px line at 16 pt. Bold sets no other
    height. Without the face here, the canvas's own measure."""
    from . import fonts, sfnt
    path = fonts.face_path(family, 1 if bold else 0) or fonts.face_path(family)
    if not path:
        return px * 1.2
    a, d = sfnt.Advances(path).vmetrics(px)
    return a + d


def _fit_breaks(c, pt, family):
    """A caption below its icon keeps as many of its leading line breaks as
    fit in its button on this panel - in the button's own caption and each
    state's. The template's tiles reach the caption with breaks counted for the
    panel the canvas is drawn on; on a smaller one the tile shrinks and the
    caption stops at the panel's type floor, and three breaks put the Mach
    725's 106 px source tiles' 16 pt captions past their edge, where GUI
    Designer clipped them. A line is as the panel lays it out (_line_px)."""
    if not c.get('size'):
        return
    line = _line_px(family, c.get('bold'), c['size'] * pt)

    def fit(text):
        if not isinstance(text, str) or not text.startswith('\r\n'):
            return text
        rest = text.lstrip('\r\n')
        breaks, lines = (len(text) - len(rest)) // 2, rest.count('\r\n') + 1
        while breaks and (breaks + lines) * line > c['rect'][3]:
            breaks -= 1
        return '\r\n' * breaks + rest
    if 'text' in c:
        c['text'] = fit(c['text'])
    for s in c.get('states') or []:
        if isinstance(s, dict) and 'text' in s:
            s['text'] = fit(s['text'])


# What a finger presses: words may not reach one.
TOUCH = ('button', 'slider', 'level')


def _meet(a, b):
    """How deep two boxes meet - the lesser of what they share across and
    down - or 0 where they share less than 2 px across and 1 down."""
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return min(w, h) if w >= 2 and h >= 1 else 0


# What a pair that met as drawn may meet by more on another panel - the
# rounding of a layout scaled to it - before it is named.
_DRAWN_SLACK = 4


# Characters that reach below the baseline - or might: anything outside
# printable ASCII is assumed to.
_PLAIN = set(' !"#%&\'*+-.0123456789:<=>?ABCDEFGHIJKLMNOPRSTUVWXYZ^abcdefhiklmnorstuvwxz~')


def _ink(c, g, dx, dy):
    """A label's or a clock's words as their glyphs fill them: the probe's box
    round them - each line's content area, the face's ascent and descent,
    1.36 em for Open Sans, deeper than the 1.2 em line it sits on - less the
    quarter em that ascent keeps above the tallest glyph (Open Sans's is
    1.07 em, its ascenders reach 0.76), and, where no character of a label's
    words reaches below the line, the quarter em its descent keeps under them
    (0.29 em). A clock's words change, so they keep theirs. Two labels' 28 pt
    boxes 5 px over each other on a 535 left their words clear, and so did
    Mach's 'Volume' over its level's Up."""
    x, y, w, h = c['text_rect']
    em = c.get('text_em') or 0
    top = min(0.25 * em, h / 2)
    text = g.get('text') if g.get('kind') == 'label' else None
    foot = min(0.25 * em, (h - top) / 2) if isinstance(text, str) and set(text) <= _PLAIN else 0
    return [x + dx, y + dy + top, w, h - top - foot]


def lines_as_shapes(spec):
    """Every line in `spec` as a filled shape of its box, for a seed with no
    PBLine to clone - most of Mach's, Shockwave's and Turbulence's sizes. A
    design-system Line is level or upright and its box is the band it draws
    (bundle.js Line), so the shape draws it exactly - with no border resource:
    on 2D Rectangle a 2 px band built fully transparent (Turbulence 1035,
    verify_built). Returns a note per line."""
    notes = []
    for item in spec['pages'] + spec['popups']:
        for i, c in enumerate(item['controls']):
            if c.get('kind') != 'line':
                continue
            shape = {'kind': 'panel', 'rect': c['rect'], 'fill': c.get('fill'), 'border': 'none'}
            if c.get('name'):
                shape['name'] = c['name']
            item['controls'][i] = shape
            who = f"{item['name']!r} {c['name']}" if c.get('name') else repr(item['name'])
            notes.append(f"{who}: a Line, built as a filled shape - a panel's seed has no line to clone")
    return notes


def lines_everywhere(specs, has_line):
    """A canvas's lines as shapes on every panel if any panel's seed has no
    line to clone (`has_line(spec)` false), as lines on all of them otherwise -
    {panel: notes}, empty where nothing changed. One way on every panel: decided
    panel by panel, an unnamed Line was a shape on the 1035 and a line on the
    525 - Mach's 525 seed has a PBLine, its 1035 none - the unnamed controls
    were numbered apart, and the ID map refused the canvas."""
    live = {m: s for m, s in specs.items() if s is not None}
    if all(has_line(s) for s in live.values()):
        return {}
    return {m: lines_as_shapes(s) for m, s in live.items()}


def _spec_check(spec, geometry=None, known=()):
    """`gdl.spec check`'s problems with a translated spec, as a build would
    meet them - touch minimums, gaps - and, given its seed's border_geometry(),
    a stroke the seed's border does not draw: on a copy, as Panel mutates what
    it reads and `_host` is the translator's own.

    It runs whatever else is wrong, so it can meet a spec it cannot read: a
    colour no token names stays on its control, and `color()` raises. Where
    the translator has already said why (`known`), that is the problem; where
    it has not, the failure is one."""
    from copy import deepcopy
    probe = deepcopy(spec)
    used = {c['id'] for item in probe['pages'] + probe['popups'] for c in item['controls'] if c.get('id')}
    stand = 60000
    for item in probe['pages'] + probe['popups']:
        item.pop('_host', None)
        # A mirror pin_ids has not given its control's ID - another panel's
        # problem stops the pinning - is still its control's (gdl.spec
        # mirrors): sharing a stand-in ID here, it is not reported as a
        # control of its own, under the touch minimum and over its tab.
        named = {c.get('name'): c for c in item['controls'] if c.get('name') and not c.get('_mirror')}
        for c in item['controls']:
            host = named.get(c.pop('_mirror', None))
            if host is None:
                continue
            if not host.get('id'):
                while stand in used:
                    stand += 1
                host['id'] = stand
                used.add(stand)
            c['id'] = host['id']
    try:
        panel = gdlspec.Panel(probe)
        out = list(panel.check())
        if geometry is not None:
            out += panel.stroke_rules(geometry, spec.get('_seed'))
    except ValueError as e:
        return [] if known else [f'the spec check could not read it: {e}']
    return out


def _collisions(drawn, laid):
    """Words a panel's layout ran into a touch target or into other words,
    beyond where they met as drawn (`drawn`: the same board on the panel the
    canvas is drawn on; _DRAWN_SLACK) - by page and name, an unnamed control
    by its kind and place. A label's box is often bigger than its
    words, and overlapping a button is harmless; the words reaching it are
    not. Two touch targets that meet are gdl.spec check's. Laid out for the
    Shockwave 720, the huddle's clock box ran 6 px into Help and nothing said
    whether its date did.

    A Group's cells, where it pages them, are a popup over the page in its
    region (a part of kind popup), reported in the popup's own coordinates:
    they are held against the page's in the page's, and two popups of one
    group, which never show together, against each other not at all. A part
    of kind page is a page of its own, and one that is a modal is over the
    page, not beside what is on it."""
    def met(o):
        parts = [dict(json.loads(p['gdl']), rect=p['rect']) for p in o.get('parts') or []]
        cs, unnamed = [], {}
        for c in o.get('controls') or []:
            g = json.loads(c['gdl'])
            # A Clock need not be named: an unnamed control is its kind and
            # its place among the unnamed of its kind, the same on every panel.
            name = g.get('name')
            if not name:
                unnamed[g.get('kind')] = unnamed.get(g.get('kind'), 0) + 1
                name = f"{g.get('kind')} {unnamed[g.get('kind')]}"
            p = c.get('part')
            d = parts[p] if p is not None and p < len(parts) else None
            dx, dy = (d['rect'][0], d['rect'][1]) if d and d.get('kind') == 'popup' else (0, 0)
            r = c['rect']
            cs.append((name, g.get('kind'), p, d, [r[0] + dx, r[1] + dy, r[2], r[3]],
                       _ink(c, g, dx, dy) if c.get('text_rect') else None))

        def together(p1, d1, p2, d2):
            if p1 == p2:
                return True
            # A modal a layout derived (the 320's Volume) shows over the page
            # under Build's scrim: nothing under it is read beside it.
            if (d1 is not None and d1.get('modal')) or (d2 is not None and d2.get('modal')):
                return False
            if (d1 is not None and d1.get('kind') != 'popup') or (d2 is not None and d2.get('kind') != 'popup'):
                return False
            return d1 is None or d2 is None or d1.get('group') != d2.get('group')

        found = {}
        for i, (n1, _, p1, d1, _, t1) in enumerate(cs):
            if not t1:
                continue
            for j, (n2, k2, p2, d2, r2, t2) in enumerate(cs):
                if j == i or not together(p1, d1, p2, d2):
                    continue
                if k2 in TOUCH:
                    deep = _meet(t1, r2)
                    if deep:
                        found[(n1, n2)] = ('run into', deep)
                elif t2 and j > i:
                    deep = _meet(t1, t2)
                    if deep:
                        found[(n1, n2)] = ('run into the words of', deep)
        return found
    page = json.loads(laid['page']['gdl']).get('name') if laid.get('page') else None
    # A pair that met as drawn is the designer's - as deep as it was drawn.
    drawn_met = met(drawn) if drawn else {}
    return [f'{page!r} {a}: its words {how} {b} on this panel - give them room'
            for (a, b), (how, deep) in met(laid).items()
            if (a, b) not in drawn_met or deep > drawn_met[(a, b)][1] + _DRAWN_SLACK]


def _frame_colors(frame):
    """Every colour a series' measured frame draws its chrome in - its
    surfaces' fills, a level's track and bar - as the spec reads them."""
    out = set()

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k in ('fill', 'track', 'bar') and isinstance(x, str) and x.startswith('#'):
                    out.add(css_to_argb(x))
                else:
                    walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(frame)
    return out


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
    """One ID per canvas control on every panel - {panel: [problems]}.

    A program drives every panel with one set of IDs. So each canvas control's
    ID is allocated once, on the panel the canvas is drawn on (`order[0]`), in
    its page's band as Panel would - 1001 up on the first page, 9001 up on the
    first popup - and written onto that control on every panel, wherever its
    layout put it there. A control is known by its page and its name, so on a
    canvas of several panels an addressable control without a name is refused.
    What a panel's layout added (`derived`) gets an ID from DERIVED_IDS up, by
    its container and name, the same on every panel it is on - or the ID it
    carries, where it carries one on every panel it is on and no canvas
    control has it: a hub's Volume Up and Down and its settings opener are
    chrome the 1035 does not draw, and keep the hub's own seed IDs.
    A region page's fixed chrome (`_seed_id`: the Footer's Help, Power and
    mode launcher, the RightRail's Volume and Mute) keeps the template's seed
    ID on every page that draws it, where it has no ID of its own and no
    canvas control has it, pinned before the bands, which step over it. A copy a layout drew of a canvas
    control (`_mirror`: Shockwave 1035's tab twin) takes that control's ID on
    its page. A canvas control a panel's layout left out by name (its page's `left`:
    a hub's footer clock, which its template has no place for) may be absent
    there.
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
    # A region page's fixed chrome - the Footer's Help and Power, the
    # RightRail's Volume and Mute, the mode launcher - keeps the template's
    # seed ID (`_seed_id`, off its frame's `ids`) where the designer gave it
    # none and no canvas control has it: a program written against Extron's
    # template finds Help at 8117 on every panel. Pinned before the bands,
    # which step over it. Keyed by name, not page: every working page draws
    # the chrome, and it is one control a program drives from any of them, so
    # Help is 8117 on the second page as on the first. A seed ID goes to the
    # first name that carries it; another name that claims it takes its band.
    explicit = {c['id'] for spec in specs.values() for it in spec['pages'] + spec['popups']
                for c in it['controls'] if c.get('id') and not c.get('derived')}
    seeded, holder = {}, {}
    for it in design['pages'] + design['popups']:
        for c in it['controls']:
            sid = c.get('_seed_id')
            if (c.get('derived') or c.get('id') or not c.get('name') or sid is None
                    or sid in explicit):
                continue
            if seeded.get(c['name'], sid) != sid or holder.get(sid, c['name']) != c['name']:
                continue
            seeded[c['name']], holder[sid] = sid, c['name']
    taken |= set(seeded.values())

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
            if c.get('_seed_id') is not None and seeded.get(c.get('name')) == c['_seed_id']:
                ids[k] = c['_seed_id']
                continue
            n = nxt.get(it['_host'], 1)
            while n in taken:
                n += 1
            ids[k] = n
            taken.add(n)
            nxt[it['_host']] = n + 1
    # A mirror the layout drew (`_mirror`: Shockwave's tab twin) has its
    # control's ID, not one of its own.
    derived = sorted({(it['name'], c['name']) for spec in specs.values()
                      for it in spec['pages'] + spec['popups'] for c in it['controls']
                      if c.get('derived') and c.get('name') and not c.get('_mirror')})
    did, n = {}, DERIVED_IDS
    carried = {}
    for spec in specs.values():
        for it in spec['pages'] + spec['popups']:
            for c in it['controls']:
                if c.get('derived') and c.get('name') and not c.get('_mirror'):
                    carried.setdefault((it['name'], c['name']), set()).add(c.get('id'))
    canvas_ids = set(ids.values())
    for k in derived:
        own = carried.get(k, set())
        cid = next(iter(own)) if len(own) == 1 else None
        if cid is not None and cid not in canvas_ids and cid not in did.values():
            did[k] = cid
    for k in derived:
        if k in did:
            continue
        while n in taken:
            n += 1
        did[k] = n
        taken.add(n)
        n += 1
    for model, spec in specs.items():
        found, seen = set(), {}
        for it in spec['pages'] + spec['popups']:
            for c in it['controls']:
                c.pop('_seed_id', None)
                mirror = c.pop('_mirror', None)
                if mirror:
                    # Where the template draws one function twice and the
                    # program addresses it as one control (docs/idmap.md
                    # Mirrors): the copy takes the control's ID on this page.
                    if (it['_host'], mirror) in ids:
                        c['id'] = ids[(it['_host'], mirror)]
                    else:
                        problems[model].append(f"{it['name']!r} {c.get('name')}: mirrors {mirror!r}, which "
                                               'is not on this page')
                    continue
                if c.get('derived'):
                    # A derived copy of an unnamed card has nothing to key an
                    # ID by, and a shape needs none.
                    if c.get('name'):
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
        left = {(it['_host'], n) for it in spec['pages'] + spec['popups'] for n in it.get('left') or ()}
        for k in sorted(set(ids) - found - left):
            problems[model].append(f'{k[1]} on {k[0]!r} is on the {order[0]} and not here - nothing is '
                                   'dropped from a panel')
    return problems


def _panel(spec):
    """The panel a spec is laid out for (gdl.spec.panel_id) - its model where
    its canvas is no panel's."""
    try:
        return gdlspec.panel_id(spec.get('model'), spec.get('size'))
    except (KeyError, TypeError, ValueError):
        return spec.get('model')


def clear_panels(out_dir, keep=()):
    """Remove every <out_dir>/<panel>/spec.json but `keep`'s; the paths removed.

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
    """Each panel's spec to <out_dir>/<panel>/spec.json, and no other panel's
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

    def image(self, name, size, host=None, base=None):
        """The page or popup `name` as the panel shows it: a modal over the
        start page - or `base` - under Build's scrim; a group's popup in its
        host page's region; anything else on its own."""
        from .compose import render_page, render_snapshot
        from PIL import Image
        import io
        pg = self.by_name.get(name)
        if pg is None:
            return None
        psize = (pg.get('Width') or size[0], pg.get('Height') or size[1])
        j, assets, fills = self.j, self.assets, self.fills
        if pg.get('Modal'):
            start = (self.by_name[base]['ID'] if base in self.by_name
                     else j.get('DefaultPage') or j['Pages'][0]['ID'])
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

    A Design canvas does not draw like GUI Designer, so a client signs off on
    the built panel, not on the canvas. The built side is gdl.compose's render
    of the built file's own artwork - scored against GUI Designer's snapshots
    (CLAUDE.md, Verifying a change) - so what shows there is what the panel
    shows. Writes <out_dir>/index.html and a PNG pair per artboard; returns
    [(page name, % of pixels that differ)].

    `built` may be a folder of panels - <panel>/<Name>.gdl, as
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
        # A built folder is named for its panel (gdl.spec.panel_id), which is
        # its canvas too: TLP300M-Landscape is 480x320, its model 320x480.
        try:
            size = gdlspec.panel_of(m)[1]
        except ValueError:
            size = (1280, 800)
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


_PAGE_TAG = re.compile(r'<x-import component-from-global-scope="[\w.]+\.Page"([^>]*)>')
_REGION_TAG = re.compile(r'component-from-global-scope="[\w.]+\.(?:Header|LeftRail|RightRail|Footer|Center)"')


def board_role(src):
    """What an artboard is, by its root Page: 'page' for a working page (one
    holding a region), its `role` for a source's popup or a window, else None
    - a free page, which the template's grammar has no counterpart for."""
    m = _PAGE_TAG.search(src)
    if not m:
        return None
    role = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1))).get('role')
    if role:
        return role.lower()
    return 'page' if _REGION_TAG.search(src) else None


def template_counterparts(frame):
    """{role: (seed page or popup, the page it shows over or in)}: what the
    template seed whose frame this is draws for a working page ('page'), a
    source's popup and each window - its frame's own page and popups. On a
    bar panel or a hub a source's popup shows in the working page's region
    and a window over it; a 320's are pages of their own, and its working
    page is Main, the home its frame records."""
    page = frame.get('page')
    pages = bool(frame.get('home'))
    host = None if pages else page
    out = {'page': ((frame.get('home') or {}).get('page') or page, None)}
    src = (frame.get('center') or {}).get('popup')
    out['source'] = (src, host) if src and not pages else (page, None)
    wins = frame.get('windows') or {}
    for k in ('help', 'confirm', 'wait'):
        w = wins.get(k)
        if isinstance(w, dict) and (w.get('popup') or w.get('page')):
            out[k] = (w.get('popup') or w.get('page'), host)
    sett = wins.get('settings') or []
    if sett and (sett[0].get('popups') or [None])[0]:
        out['settings'] = (sett[0]['popups'][0], host)
    return out


def _same_name(built, *names):
    """The built file's page or popup named as one of `names`, letters and
    digits alone and in any case: exactly ('DocCam' is 'Doc Cam'), or as its
    first page ('Doc Cam 1') or with a word after ('Lighting Settings')."""
    def norm(s):
        return re.sub(r'[^a-z0-9]', '', (s or '').lower())
    have = {}
    for n in built.by_name:
        have.setdefault(norm(n), n)
    for want in filter(None, (norm(x) for x in names)):
        for key in (want, want + '1'):
            if key in have:
                return have[key]
        hit = sorted(k for k in have if k.startswith(want))
        if hit:
            return have[hit[0]]
    return None


def _sheet(sections, path, width=480):
    """One PNG of every pair, panel by panel, for a designer to read at a
    glance: each artboard as drawn beside the template's page, labelled."""
    from PIL import Image, ImageDraw
    rows = []
    for title, pairs in sections:
        rows.append(('title', title))
        rows += [('pair', p) for p in pairs]
    pad, head = 12, 22
    cells = []
    for kind, v in rows:
        if kind == 'title':
            cells.append((head + pad, kind, v))
            continue
        name, design_png, template_png, label = v
        imgs = []
        for f in (design_png, template_png):
            if f and os.path.exists(f):
                im = Image.open(f).convert('RGB')
                imgs.append(im.resize((width, max(1, round(width * im.height / im.width)))))
            else:
                imgs.append(None)
        h = max([im.height for im in imgs if im] + [60])
        cells.append((h + head + pad, kind, (name, imgs, label)))
    sheet = Image.new('RGB', (2 * width + 3 * pad, sum(c[0] for c in cells) + pad), (22, 23, 29))
    d = ImageDraw.Draw(sheet)
    y = pad
    for h, kind, v in cells:
        if kind == 'title':
            d.text((pad, y + 4), v, fill=(232, 232, 238))
        else:
            name, imgs, label = v
            d.text((pad, y + 4), f'{name} - as drawn', fill=(169, 170, 184))
            d.text((2 * pad + width, y + 4), f"template: {label}" if label else 'no counterpart in the template',
                   fill=(169, 170, 184))
            for i, im in enumerate(imgs):
                if im:
                    sheet.paste(im, (pad + i * (width + pad), y + head))
        y += h
    sheet.save(path)


def compare_template(folder, out_dir, chrome=None):
    """Each artboard of a canvas, as drawn for each panel it lists, beside the
    page of that panel's own template seed it stands for - the working page
    beside the seed's working page (Main SD, a hub's Main Page, the 320's
    Main), a source beside the seed's source popup, a window beside its window
    of that role (template_counterparts) - for the designer's critique loop
    (SKILL.md): region by region, what differs from the template that the
    README's Differences does not list is a fix. A free page has no
    counterpart and stands alone. Writes <out_dir>/index.html, a PNG pair per
    artboard and panel, and sheet.png, every pair on one sheet; returns
    [(panel, page, the seed page beside it or None)]."""
    canvas = Canvas(folder, chrome)
    if not canvas.chrome:
        raise RuntimeError('no Chrome found - pass --chrome or set CHROME')
    boards = canvas.boards()
    first = render(os.path.join(folder, *boards[0].split('/')), canvas.chrome, canvas._size(boards[0]))
    profile = canvas._profile(json.loads(first['page']['gdl']).get('template') if first.get('page') else None)
    listed = Canvas._panels_of({'b': first}) or [profile['model']]
    ms = designsys.models(profile)
    os.makedirs(out_dir, exist_ok=True)
    pairs, sections, sheet = [], [], []
    for m in listed:
        T = ms.get(m) or {}
        frame, seed = T.get('frame'), T.get('seed')
        built = _Built(seeds.path(seed)) if frame and seed and seeds.usable(seed) else None
        counter = template_counterparts(frame) if frame else {}
        sub = os.path.join(out_dir, m)
        os.makedirs(sub, exist_ok=True)
        rows = []
        for b in boards:
            path = os.path.join(folder, *b.split('/'))
            with open(path, encoding='utf-8') as fh:
                role = board_role(fh.read())
            out = render(path, canvas.chrome, canvas._size(b), panel=m)
            pg = json.loads(out['page']['gdl']) if out.get('page') else {}
            name = pg.get('name') or b
            psize = tuple(pg.get('size') or T.get('size') or canvas._size(b))
            stem = re.sub(r'[^A-Za-z0-9_.-]', '_', b.rsplit('.dc.html', 1)[0])
            design_png = os.path.join(sub, f'{stem}-design.png')
            copy = _as_panel(path, m)
            try:
                screenshot(copy, canvas.chrome, psize, design_png)
            finally:
                if os.path.exists(copy):
                    os.remove(copy)
            target = counter.get(role) if role else None
            if target and built and role in ('source', 'settings'):
                # The seed's own of the same name where it has one - its PC
                # beside the canvas's PC, its Lighting Settings beside a
                # Lighting window - else the frame's.
                target = (_same_name(built, name, pg.get('title')) or target[0], target[1])
            template_png = None
            if target and built:
                # Translucent chrome over the photo as the panel shows it, as
                # the design system's template renders draw it (compose.BINARY).
                # The rule goes back as it was, so a caller's outlives the pair.
                from . import compose
                was, compose.BINARY = compose.BINARY, False
                try:
                    img = built.image(target[0], tuple(T['size']), host=target[1], base=target[1])
                finally:
                    compose.BINARY = was
                if img is not None:
                    template_png = os.path.join(sub, f'{stem}-template.png')
                    img.save(template_png)
            label = f"{seed}'s {target[0]}" if target else None
            pairs.append((m, name, target[0] if target else None))
            rows.append((name, design_png, template_png, label))
        size = T.get('size') or canvas._size(boards[0])
        sections.append(
            f'<section class="panel"><h2>{html.escape(m)} &middot; {size[0]}x{size[1]}</h2>'
            f'<p class="note">Beside {html.escape(seed or "no seed")}'
            + ('' if built else ' - not here (git lfs pull), so the template side is empty') + '</p>'
            + ''.join(
                f'<div class="pairbox"><h3>{html.escape(n)}</h3><div class="pair">'
                f'<figure><img src="{html.escape(m)}/{os.path.basename(d)}" alt="{html.escape(n)} as drawn">'
                f'<figcaption>As drawn for the {html.escape(m)}</figcaption></figure>'
                + (f'<figure><img src="{html.escape(m)}/{os.path.basename(t)}" alt="{html.escape(lab)}">'
                   f'<figcaption>The template: {html.escape(lab)}</figcaption></figure>' if t else
                   f'<figure><figcaption>{"The template: " + html.escape(lab) + " (not drawn)" if lab else "The template has no page of its kind"}'
                   f'</figcaption></figure>')
                + '</div></div>' for n, d, t, lab in rows)
            + '</section>')
        sheet.append((f'{m} - beside {seed}', rows))
    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(_page((canvas.index.get('title') or 'Panel') + ', beside its template', ''.join(sections))
                 .replace(' - designed and built</title>', ' - beside its template</title>'))
    _sheet(sheet, os.path.join(out_dir, 'sheet.png'))
    return pairs


def main(argv):
    if len(argv) >= 2 and argv[1] == 'pin-runtime':
        def flag(name):
            i = argv.index(name) if name in argv else -1
            return argv[i + 1] if 0 <= i < len(argv) - 1 and not argv[i + 1].startswith('--') else None
        seen, suite = flag('--seen'), flag('--suite')
        if len(argv) < 3 or argv[2].startswith('--') or not os.path.isfile(argv[2]) or not seen \
                or ('--suite' in argv and not suite):
            print('  python -m gdl.design pin-runtime <dc-runtime.js> --seen <where it came from> '
                  '[--suite <what passed>]')
            return 2
        e = pin_runtime(argv[2], seen, suite)
        print(f"proven: {e['sha256']} ({e['bytes']:,} bytes) -> {RUNTIMES}")
        return 0
    if len(argv) >= 5 and argv[1] == 'compare' and argv[3] == '--template':
        # The critique loop: each artboard beside its template's own page.
        chrome = argv[argv.index('--chrome') + 1] if '--chrome' in argv else None
        unproven = runtime_problem(argv[2])
        if unproven and '--new-runtime' not in argv:
            print('  PROBLEM ' + unproven)
            return 1
        for m, name, seed_page in compare_template(argv[2], argv[4], chrome):
            print(f"  {m}: {name}" + (f" beside {seed_page}" if seed_page else ' (the template has no page of its kind)'))
        print(f"-> {os.path.join(argv[4], 'index.html')} and sheet.png")
        return 0
    if len(argv) >= 5 and argv[1] == 'compare':
        chrome = argv[argv.index('--chrome') + 1] if '--chrome' in argv else None
        # The sign-off lays the canvas out on its runtime too.
        unproven = runtime_problem(argv[2])
        if unproven and '--new-runtime' not in argv:
            print('  PROBLEM ' + unproven)
            return 1
        for name, pct in compare(argv[2], argv[3], argv[4], chrome):
            print(f'  {pct:5.1f}%  {name}')
        print(f"-> {os.path.join(argv[4], 'index.html')}")
        return 0
    if len(argv) < 4 or argv[1] != 'translate':
        print(__doc__.strip().split('\n\n')[0])
        print('\n  python -m gdl.design translate <canvas dir> <out dir>        one spec per panel'
              '\n  python -m gdl.design translate <canvas dir> <out spec.json>  the design panel only'
              ' [--lenient]'
              '\n      [--chrome PATH] [--new-runtime]'
              '\n  python -m gdl.design compare <canvas dir> <built.gdl> <out dir>'
              '\n  python -m gdl.design compare <canvas dir> --template <out dir>   beside the template'
              '\n  python -m gdl.design pin-runtime <dc-runtime.js> --seen <where it came from>')
        return 2
    chrome = argv[argv.index('--chrome') + 1] if '--chrome' in argv else None
    unproven = runtime_problem(argv[2])
    if unproven and '--new-runtime' not in argv:
        print('  PROBLEM ' + unproven)
        return 1
    if unproven:
        print('  note    ' + unproven)
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
