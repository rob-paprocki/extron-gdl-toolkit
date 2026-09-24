"""Turn a Claude Design canvas into a spec.

    python -m gdl.design translate <canvas dir> <out spec.json>

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

from . import designsys

# Where Chrome lives when neither --chrome nor $CHROME says. Headless Chrome is
# the only runtime this needs, and only here.
CHROME = (r'C:\Program Files\Google\Chrome\Application\chrome.exe',
          r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
          '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
          '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser')

# What each kind carries into the spec, beyond kind, name and rect.
FIELDS = {
    'button': ('id', 'text', 'fill', 'stroke', 'color', 'border', 'size', 'bold', 'align',
               'states', 'press', 'nav', 'does'),
    'label': ('id', 'text', 'color', 'size', 'bold', 'align', 'does'),
    'panel': ('fill', 'stroke', 'border'),
    'line': ('fill', 'thickness', 'from', 'to'),
    'slider': ('id', 'fill', 'border', 'orientation', 'track', 'thumb', 'does'),
    'level': ('id', 'fill', 'border', 'orientation', 'track', 'does'),
    'datetime': ('color', 'size', 'bold', 'align', 'format'),
    'popup_ref': ('group',),
}
COLOR_KEYS = ('fill', 'stroke', 'color')
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
  function done() {
    var pages = document.querySelectorAll('[data-gdl]');
    var page = null;
    for (var p of pages) { var k = JSON.parse(p.getAttribute('data-gdl')).kind; if (k === 'page' || k === 'popup') { page = p; break; } }
    var out = { pages: 0, controls: [], stray: [] };
    for (var p of pages) { var k = JSON.parse(p.getAttribute('data-gdl')).kind; if (k === 'page' || k === 'popup') out.pages++; }
    if (page) {
      var o = page.getBoundingClientRect();
      out.page = { gdl: page.getAttribute('data-gdl'), rect: [0, 0, o.width, o.height] };
      for (var el of page.querySelectorAll('*')) {
        var r = el.getBoundingClientRect();
        var box = [r.left - o.left, r.top - o.top, r.width, r.height];
        if (el.hasAttribute('data-gdl')) {
          out.controls.push({ gdl: el.getAttribute('data-gdl'), rect: box, href: el.getAttribute('href') });
          continue;
        }
        if (el.closest('[data-gdl]') !== page) continue;          // inside a component
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


def render(board_path, chrome, size, timeout=90):
    """Lay one artboard out in headless Chrome; its components and strays.

    The probe goes into a copy beside the original, so relative paths -
    support.js, ds/<folder>/ - resolve the same way they do on the canvas.
    """
    with open(board_path, encoding='utf-8') as fh:
        src = fh.read()
    if '</body>' not in src:
        raise ValueError(f'{os.path.basename(board_path)} has no </body>')
    probe = os.path.join(os.path.dirname(board_path),
                         '__gdl_probe_' + os.path.basename(board_path))
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
        return self._spec(rendered)

    # -- building the spec ---------------------------------------------------
    def _spec(self, rendered):
        problems, notes = self.problems, self.notes
        profile, scheme = None, None
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
            if profile is None:
                profile = self._profile(pg.get('template'))
                scheme = pg.get('scheme')
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
            stems[b.rsplit('/', 1)[-1].rsplit('.dc.html', 1)[0]] = name
            item = {'name': name, 'controls': [], '_board': b}
            # Build draws a modal as the page beneath under black at alpha 166
            # and ignores its background, so a modal carries none.
            if pg.get('background') and not pg.get('modal'):
                item['background'] = pg['background']
            if pg.get('background_image') and pg['kind'] == 'page':
                item['background_image'] = pg['background_image']
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
            item['_raw'] = out['controls']
        if profile is None:
            return None, problems or ['no artboard has a Page'], notes

        colors = self._colors(profile, scheme)
        self.template = profile['template']
        # A slider's thumb is a kit image in the scheme's secondary accent. The
        # canvas draws it in that color; a clone would keep the donor's.
        thumb = designsys.slider_thumb(profile, scheme)
        for item in pages + popups:
            item['controls'] = [c for c in (self._control(item['name'], raw, stems)
                                            for raw in item.pop('_raw')) if c]
            item.pop('_board')
            for c in item['controls']:
                if c['kind'] == 'slider' and thumb:
                    c['thumb_image'] = thumb[0]
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
        spec = {
            'name': self.index.get('title') or 'Panel',
            'model': profile['model'],
            'size': list(profile['size']),
            '_seed': profile['seed'],
            '_from': f"Claude Design canvas, {profile['template']} ({scheme})",
            'theme': theme,
            'pages': pages,
            'popups': popups,
        }
        # An image goes with the file it comes from, relative to the resource
        # kits: the seed carries some already, and the applier appends the
        # rest. Background images are the themes'; button images the kit's.
        files = {th['image']: th['file'] for th in designsys.themes(profile)
                 if th.get('image') and th.get('file')}
        used = {pg['background_image'] for pg in pages if pg.get('background_image')}
        buttons = {s['image'] for item in pages + popups for c in item['controls']
                   for s in c.get('states') or [] if isinstance(s, dict) and s.get('image')}
        buttons |= {c['thumb_image'] for item in pages + popups for c in item['controls']
                    if c.get('thumb_image')}
        if buttons:
            files.update(designsys.kit_index(profile)['paths'])
            if thumb:
                files[thumb[0]] = thumb[1]
            for n in sorted(buttons - set(files)):
                problems.append(f'image {n!r} is not in the {profile["template"]} kit on this '
                                f'machine (vendor/extron/Resources or the install)')
        used |= buttons
        if used:
            spec['images'] = {n: files[n] for n in sorted(used) if n in files}
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
            if 'nav' in c:
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
    look = {k: s[k] for k in STATE_LOOK if k in s and (s[k] != 'none' or k == 'border')}
    return dict(name=s.get('name'), **look) if look else s.get('name')


def _colors_in(item):
    if item.get('background'):
        yield item['background']
    for c in item['controls']:
        for k in COLOR_KEYS:
            if c.get(k):
                yield c[k]
        for s in c.get('states') or []:
            if isinstance(s, dict):
                for k in COLOR_KEYS:
                    if s.get(k):
                        yield s[k]


def _box(r):
    return f'{round(r[0])},{round(r[1])} {round(r[2])}x{round(r[3])}'


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


def compare(folder, built, out_dir, chrome=None):
    """Each artboard beside the page GUI Designer built from it, for sign-off.

    Claude Design does not draw like GUI Designer, so a client signs off on
    the built panel, not on the canvas. The built side is gdl.compose's render
    of the built file's own artwork - scored against GUI Designer's snapshots
    (CLAUDE.md, Verifying a change) - so what shows there is what the panel
    shows. Writes <out_dir>/index.html and a PNG pair per artboard; returns
    [(page name, % of pixels that differ)].
    """
    from .compose import diff_stats, fill_index, load, render_page, render_snapshot  # Pillow
    from PIL import Image
    import io

    canvas = Canvas(folder, chrome)
    if not canvas.chrome:
        raise RuntimeError('no Chrome found - pass --chrome or set CHROME')
    j, assets = load(built)
    fills = fill_index(built)
    by_name = {p['Name']: p for p in j['Pages'] + j['PopupPages']}
    os.makedirs(out_dir, exist_ok=True)
    rows, scores = [], []
    for b in canvas.boards():
        w = canvas.index['boards'].get(b) or {}
        size = (int(w.get('w') or 1280), int(w.get('h') or 800))
        stem = re.sub(r'[^A-Za-z0-9_.-]', '_', b.rsplit('.dc.html', 1)[0])
        path = os.path.join(folder, *b.split('/'))
        out = render(path, canvas.chrome, size)
        name = json.loads(out['page']['gdl']).get('name') if out.get('page') else None
        design_png = os.path.join(out_dir, f'{stem}-design.png')
        screenshot(path, canvas.chrome, size, design_png)
        pg = by_name.get(name)
        if pg is None:
            rows.append((name or b, f'{stem}-design.png', None, None))
            continue
        psize = (pg.get('Width') or size[0], pg.get('Height') or size[1])
        if pg.get('Modal'):
            # What the panel shows: the start page, Build's alpha-166 scrim
            # (the modal's own artwork), then the modal's controls on top.
            start = j.get('DefaultPage') or j['Pages'][0]['ID']
            img = render_snapshot(j, start, assets, psize, fills=fills).convert('RGBA')
            if pg.get('TLPImageID', -1) in assets:
                scrim = Image.open(io.BytesIO(assets[pg['TLPImageID']])).convert('RGBA')
                img = Image.alpha_composite(img, scrim.resize(img.size))
            bare = dict(pg, TLPImageID=-1, BackgroundFillColor=None)
            top = render_page(bare, assets, psize, fills=fills, flat=False)
            img = Image.alpha_composite(img, top).convert('RGB')
        else:
            img = render_snapshot(j, pg['ID'], assets, psize, fills=fills)
        built_png = os.path.join(out_dir, f'{stem}-built.png')
        img.save(built_png)
        a = Image.open(design_png).convert('RGB')
        pct = diff_stats(a.resize(img.size) if a.size != img.size else a, img)['pct_bad']
        rows.append((name, f'{stem}-design.png', f'{stem}-built.png', pct))
        scores.append((name, pct))
    cells = ''.join(
        f'<section><h2>{html.escape(n)}</h2><div class="pair">'
        f'<figure><img src="{d}" alt="{html.escape(n)} as designed"><figcaption>Designed'
        f'</figcaption></figure>'
        + (f'<figure><img src="{bpng}" alt="{html.escape(n)} as built"><figcaption>Built'
           f' &middot; {pct:.1f}% of pixels differ</figcaption></figure>' if bpng else
           '<figure><figcaption>Not in the built file</figcaption></figure>')
        + '</div></section>' for n, d, bpng, pct in rows)
    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{html.escape(canvas.index.get('title') or 'Panel')} - designed and built</title>
<style>
body{{margin:0;padding:24px;font:15px/1.4 system-ui,sans-serif;background:#16171d;color:#e8e8ee}}
h1{{font-size:22px;margin:0 0 20px}} h2{{font-size:17px;margin:28px 0 10px}}
.pair{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}
figure{{margin:0}} img{{width:100%;height:auto;display:block;border:1px solid #33343f}}
figcaption{{margin-top:6px;color:#a9aab8}}
@media (max-width:700px){{.pair{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>{html.escape(canvas.index.get('title') or 'Panel')}: as designed, and as GUI Designer built it</h1>
{cells}
</body></html>
""")
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
        print('\n  python -m gdl.design translate <canvas dir> <out spec.json> '
              '[--chrome PATH] [--lenient]'
              '\n  python -m gdl.design compare <canvas dir> <built.gdl> <out dir>')
        return 2
    chrome = argv[argv.index('--chrome') + 1] if '--chrome' in argv else None
    canvas = Canvas(argv[2], chrome)
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
