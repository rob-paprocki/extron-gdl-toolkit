"""The truth ledger and the claim lint: is what a theme's system says about
its template what the template does?

    python -m gdl.designsys audit <theme>

A profile (`gdl/designsys/<theme>.json`) and the README written from it were
measured off the two least typical pages of each template, and told a
designer things the working pages do not do (the region frame spec,
docs/superpowers/specs/2026-10-22-region-frame-design.md, *Truth*). Each
such claim is an entry in the theme's ledger, `gdl/designsys/truth/<theme>.json`
(its schema beside it): what we said, what the template does - with the seed
and the pages it was read off - and how it is resolved:

- `fixed`: the profile or README now says what the template does - `fix`
  names the key and the words it holds, or the README's words;
- `frame`: the region frame draws it - `frame` names the frame key it draws
  from;
- `deviation`: we differ on purpose - `reason` says why (a gate, or a
  capability the panel lacks).

The audit reports every entry not resolved and every sentence the claim lint
finds unbacked, and exits non-zero on any: a theme at zero is done. A
deviation's `here` is the README's Differences word for word, so the lint
leaves it to its entry, and the audit holds every number it gives to one its
own template, reason or evidence gives.

The claim lint is mechanical on purpose: a sentence in the profile or the
README that claims what the template does ("as the seed draws it", "every
Mach 1035 page", a measured number said to be the template's) must be backed
by a ledger entry's words, by a frame value (the README's Layout, written
from the frame), or by a `_source` over it that names the seed and a page. It
flags rather than guesses: a sentence it cannot back is reported, and the fix
is to cite the page or say less.
"""
import json
import os
import re

from . import HERE, TEMPLATES, component_docs, frame_layout, load, readme

TRUTH = os.path.join(HERE, 'truth')
STATUSES = ('fixed', 'frame', 'deviation')
_MISSING = object()


# -- the ledger ---------------------------------------------------------------
def ledger_path(theme):
    return os.path.join(TRUTH, f'{theme}.json')


def schema():
    with open(os.path.join(TRUTH, 'schema.json'), encoding='utf-8') as fh:
        return json.load(fh)


def load_ledger(theme):
    """The theme's ledger, or None where it has none yet."""
    path = ledger_path(theme)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


_TYPES = {'object': dict, 'array': list, 'string': str, 'boolean': bool,
          'integer': int, 'number': (int, float)}


def validate(value, sch=None, root=None, where='ledger'):
    """[problem] of `value` against the schema: the subset of JSON Schema the
    ledger's schema uses (type, required, properties, additionalProperties,
    enum, items, minItems, minLength, pattern, $ref within the file). Stdlib
    only, as the rest of the package is."""
    root = root or schema()
    sch = root if sch is None else sch
    if '$ref' in sch:
        node = root
        for part in sch['$ref'].lstrip('#/').split('/'):
            node = node[part]
        sch = node
    out = []
    t = sch.get('type')
    if t and not isinstance(value, _TYPES[t]) or (t in ('integer', 'number') and isinstance(value, bool)):
        return [f'{where}: is not {"an" if t[0] in "aeiou" else "a"} {t}']
    if 'enum' in sch and value not in sch['enum']:
        out.append(f"{where}: {value!r} is not one of {', '.join(sch['enum'])}")
    if isinstance(value, str):
        if len(value) < sch.get('minLength', 0):
            out.append(f'{where}: is empty')
        if 'pattern' in sch and not re.search(sch['pattern'], value):
            out.append(f"{where}: {value!r} does not match {sch['pattern']}")
    if isinstance(value, list):
        if len(value) < sch.get('minItems', 0):
            out.append(f"{where}: needs at least {sch['minItems']}")
        for i, v in enumerate(value):
            out += validate(v, sch.get('items') or {}, root, f'{where}[{i}]')
    if isinstance(value, dict):
        props = sch.get('properties') or {}
        for k in sch.get('required') or ():
            if k not in value:
                out.append(f'{where}: has no `{k}`')
        for k, v in value.items():
            if k in props:
                out += validate(v, props[k], root, f'{where}.{k}')
            elif sch.get('additionalProperties') is False:
                out.append(f'{where}: `{k}` is not a ledger field')
    return out


def resolve(obj, key):
    """The value at a dotted key, or _MISSING. A list item is named by its
    index or by its `name` (`colors.accent.usage`, `layout.regions.0`)."""
    for part in key.split('.'):
        if isinstance(obj, dict):
            if part not in obj:
                return _MISSING
            obj = obj[part]
        elif isinstance(obj, list):
            if part.isdigit() and int(part) < len(obj):
                obj = obj[int(part)]
            else:
                hit = [x for x in obj if isinstance(x, dict) and part in (x.get('name'), x.get('id'))]
                if not hit:
                    return _MISSING
                obj = hit[0]
        else:
            return _MISSING
    return obj


def _flat(v):
    """Every word a value holds, whitespace collapsed: a string, or the
    strings in a list or a dict."""
    if isinstance(v, str):
        return ' '.join(v.split())
    if isinstance(v, dict):
        return ' '.join(_flat(x) for x in v.values())
    if isinstance(v, list):
        return ' '.join(_flat(x) for x in v)
    return json.dumps(v)


def system_text(p):
    """The README and every component's README, as the designer reads them."""
    return '\n\n'.join([readme(p)] + list(component_docs(p).values()))


def _series_frames(p):
    return {name: s.get('frame') for name, s in (p.get('panels') or {}).items()
            if not name.startswith('_') and isinstance(s, dict) and s.get('frame')}


# A number the words claim: standing alone, or with a unit (99px, 14pt, 9mm),
# either side of a size (880x525), or a sentence's last (ends at 42.). Not one
# inside a word or a name - TLP1035T, 2D, h264. Stepping over any a letter or a
# period followed let a Differences sentence say '99px' that nothing backed.
_NUMBER = re.compile(r'(?:(?<![\w.])|(?<=\dx))(\d+(?:\.\d+)?)'
                     r'(?=(?:px|pt|mm)\b|x\d|\.(?!\w)|(?![\w.]))')


def _numbers_unbacked(e):
    """The numbers an entry's `here` says that its template's words, its
    reason and its evidence never do."""
    here = e.get('here') or ''
    said = set(_NUMBER.findall(' '.join([(e.get('template') or {}).get('does') or '', e.get('reason') or '',
                                         e.get('evidence') or ''])))
    return sorted(set(_NUMBER.findall(here)) - said, key=lambda n: float(n))


def _ids_in(v, out):
    """Every seed `id` a frame value holds, at any depth - and the IDs of an
    `ids: {name: id}` map, which a frame keeps its call keys' IDs in."""
    if isinstance(v, dict):
        for k, x in v.items():
            if k == 'id' and isinstance(x, int) and not isinstance(x, bool):
                out.add(x)
            elif k == 'ids' and isinstance(x, dict):
                out.update(i for i in x.values() if isinstance(i, int) and not isinstance(i, bool))
            _ids_in(x, out)
    elif isinstance(v, list):
        for x in v:
            _ids_in(x, out)
    return out


# A seed ID as the words state it: a number from 5000 up (the theme frames'
# lowest is 5002, and every panel model, size and coordinate the words give is
# smaller - 1035, 1220, 2047x151) that is not a size, a coordinate or a
# unit's number. A range
# ("5203 to 5211") states every ID between, which the frame holds one by one.
_ID_WORD = re.compile(r'(?<![\w.,])([5-9]\d{3}|\d{5})(?![\w.]*\d|x\d|,\d|px\b|pt\b|mm\b|%)(?<!x\d{4})(?<!x\d{5})')
_ID_RANGE = re.compile(r'(?<![\w.])([5-9]\d{3}|\d{5}) to ([5-9]\d{3}|\d{5})(?!\d)')


def _ids_said(text):
    """The seed IDs a sentence states, range interiors included."""
    out = set()
    for a, b in _ID_RANGE.findall(text):
        if int(a) < int(b) <= int(a) + 100:
            out.update(range(int(a), int(b) + 1))
    for m in _ID_WORD.finditer(text):
        out.add(int(m.group(1)))
    return out


def _ids_unframed(e, frames):
    """The seed IDs a `frame` entry's template says that none of the frames it
    names holds at its keys. `frame` says the region frame draws what the
    template does; an ID the template's words give that the frame has not
    measured there is the template read off something else - whether another
    frame holds it, or none does. A frame is looked up in the entry's own
    series; only an entry naming none pools them. The frame's own numbers are
    checked only so: a size or a step is many numbers' sum."""
    if e.get('status') != 'frame':
        return []
    held = set()
    for f in e.get('frame') or ():
        pool = [frames.get(f['series'])] if f.get('series') else list(frames.values())
        for fr in pool:
            v = resolve(fr, f['key']) if fr else _MISSING
            if v is not _MISSING:
                _ids_in(v, held)
    return sorted(_ids_said((e.get('template') or {}).get('does') or '') - held)


def audit_ledger(p, ledger, text=None):
    """[finding] for every ledger entry that is not resolved."""
    theme = p['template'].lower()
    if ledger is None:
        return [f'{theme}: no ledger ({os.path.relpath(ledger_path(theme), os.path.dirname(os.path.dirname(HERE)))})']
    out = validate(ledger)
    if out:
        return out
    text = ' '.join((text if text is not None else system_text(p)).split())
    words = text + ' ' + _flat({k: v for k, v in p.items() if k != 'panels'})
    frames = _series_frames(p)
    seen = set()
    for e in ledger['entries']:
        tag = e['id']
        if tag in seen:
            out.append(f'{tag}: the id is used twice')
        seen.add(tag)
        st = e['status']
        if st == 'fixed' and not e.get('fix'):
            out.append(f'{tag}: `fixed`, but names no key or README words that now say it')
        if st == 'frame' and not e.get('frame'):
            out.append(f'{tag}: `frame`, but names no frame key that draws it')
        if st == 'deviation' and not (e.get('reason') or '').strip():
            out.append(f'{tag}: a `deviation` without a reason')
        if st == 'deviation' and not (e.get('here') or '').strip():
            out.append(f"{tag}: a `deviation` that says nothing to the designer - its `here` is the README's "
                       'Differences')
        # Differences is each `here`, which the claim lint leaves to its entry:
        # every number it gives must be one the entry's own template, reason or
        # evidence gives, so the README's Differences cannot drift from them.
        for n in _numbers_unbacked(e):
            out.append(f"{tag}: its `here` says {n}, which its template, reason and evidence do not")
        for n in _ids_unframed(e, frames):
            out.append(f"{tag}: its template says ID {n}, which no frame it names holds at its keys")
        for f in e.get('fix') or ():
            if not f.get('key') and not f.get('readme'):
                out.append(f'{tag}: a fix names neither a key nor README words')
            if f.get('key'):
                v = resolve(p, f['key'])
                if v is _MISSING:
                    out.append(f"{tag}: fixed at `{f['key']}`, which the profile does not have")
                elif f.get('says') and ' '.join(f['says'].split()) not in _flat(v):
                    out.append(f"{tag}: `{f['key']}` does not say {f['says']!r}")
            elif f.get('says'):
                out.append(f'{tag}: a fix says words but names no key')
            if f.get('readme') and ' '.join(f['readme'].split()) not in text:
                out.append(f"{tag}: the README does not say {f['readme']!r}")
        for f in e.get('frame') or ():
            pool = {f['series']: frames.get(f['series'])} if f.get('series') else frames
            if not any(fr and resolve(fr, f['key']) not in (_MISSING, None) for fr in pool.values()):
                out.append(f"{tag}: no {f.get('series') or 'series'} frame has `{f['key']}`")
        for g in e.get('gone') or ():
            if ' '.join(g.split()) in words:
                out.append(f'{tag}: the profile or README still says {g!r}')
    return out


# -- the claim lint -----------------------------------------------------------
# What makes a sentence a claim about the template, not a rule of ours. Each
# is a phrase the measured disagreements were written in: "as the seed draws
# it", "as Mach's own templates draw them", "every Mach 1035 page's own header
# label", "the template's own 1 px".
_THEMES = r'(?:Afterburn|Mach|Shockwave|Turbulence)'
CLAIMS = (
    ('as the template draws it',
     re.compile(r"\bas (?:the|its|their|" + _THEMES + r"'s)\s+(?:own\s+)?(?:[\w-]+\s+){0,2}?"
                r"(?:seeds?|templates?)\b|\bas " + _THEMES + r"'s own\s+(?:[\w-]+\s+){0,2}?pages?\b", re.I)),
    ('every template page',
     re.compile(r"\bevery\b[^.;:]{0,40}?\b(?:seed|template|" + _THEMES + r"|\d{3,4})\b[^.;:]{0,30}?\bpages?\b", re.I)),
    ("a number said to be the template's",
     re.compile(r"\b(?:the|its) (?:template|seed)'s\b[^.;]*?\b\d+(?:\.\d+)?\s*(?:px|pt|mm|%|wide|deep|apart|x\d+)"
                r"|\b\d+(?:\.\d+)?\s*(?:px|pt)\b[^.;]*?\b(?:the|its) (?:template|seed)'s\b", re.I)),
)
_SEED = re.compile(r'\bseeds?\b|seeds/', re.I)
# A survey of the whole seed names every page, not one - in words: a source's
# `pages()` is the function it was read with (gdl.project), not a page.
_EVERY_PAGE = re.compile(r'\bevery (?:one of [^.]*?)?pages?\b|\ball (?:of its )?pages\b', re.I)
_SENTENCE = re.compile(r'(?<=[.!?])\s+(?=[A-Z*`(\'"])')


def sentences(text):
    """A text's sentences: code blocks, table rows and headings left out."""
    text = re.sub(r'```.*?```', ' ', text, flags=re.S)
    out = []
    # A list item is a paragraph of its own.
    for para in re.split(r'\n\s*\n|\n(?=\s*[-*] )', text):
        lines = [ln for ln in para.splitlines() if not ln.lstrip().startswith(('|', '#'))]
        para = ' '.join(' '.join(lines).split())
        out += [s for s in _SENTENCE.split(para) if s.strip()]
    return out


def claim(sentence):
    """Why a sentence is a claim about the template, or None."""
    for why, pat in CLAIMS:
        if pat.search(sentence):
            return why
    return None


def _strings(v, path=()):
    """(path, text) for every prose string under v, leaving out what is
    evidence rather than claim: `_`-keys (the sources), and the measured
    `panels` table, which has its own."""
    if isinstance(v, str):
        if len(v.split()) >= 4:
            yield path, v
    elif isinstance(v, dict):
        for k, x in v.items():
            if k.startswith('_') or (not path and k == 'panels'):
                continue
            yield from _strings(x, path + (k,))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from _strings(x, path + (str(x.get('name')) if isinstance(x, dict) and x.get('name') else str(i),))


def _page_names(p, ledger):
    """The template's page names this system knows: each frame's own page and
    the popups and pages it was measured off, and every page the ledger read."""
    names = set()

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k in ('page', 'popup') and isinstance(x, str):
                    names.add(x)
                elif k == 'popups' and isinstance(x, list):
                    names.update(n for n in x if isinstance(n, str))
                else:
                    walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(_series_frames(p))
    for e in (ledger or {}).get('entries') or ():
        names.update((e.get('template') or {}).get('pages') or ())
    return {n for n in names if n}


def _sources_over(p, path):
    """The `_`-keyed sources over a profile key: every `_` string in each
    dict on its way down, and of a top-level `_source` list the entries on
    its topic ("Colors: ..." over `colors`, "Slider: ..." over
    `defaults.slider`)."""
    out, node = [], p
    for depth, part in enumerate(path):
        if not isinstance(node, dict):
            break
        for k, v in node.items():
            if not k.startswith('_'):
                continue
            items = v if isinstance(v, list) else [v]
            for s in items:
                if not isinstance(s, str):
                    continue
                if depth == 0 and isinstance(v, list):
                    topic = s.split(':', 1)[0].strip().lower().rstrip('s')
                    if not any(topic == seg.lower().rstrip('s') for seg in path):
                        continue
                out.append(s)
        node = node.get(part)
    return out


def _cites(source, pages):
    """Whether a source names the seed and a page."""
    if not _SEED.search(source):
        return False
    return bool(_EVERY_PAGE.search(source)) or any(
        re.search(r'(?<![\w-])' + re.escape(n) + r'(?![\w-])', source) for n in pages)


def lint(p, ledger=None, text=None):
    """[(where, sentence, why)] for every claim about the template that is not
    backed by the ledger, the frame or a source citing the seed and a page."""
    backed = []
    for e in (ledger or {}).get('entries') or ():
        for f in e.get('fix') or ():
            backed += [' '.join(f[k].split()) for k in ('says', 'readme') if f.get(k)]
    pages = _page_names(p, ledger)
    out, said = [], set()

    def ok(s):
        return any(b and b in s for b in backed)
    for path, value in _strings(p):
        cites = any(_cites(s, pages) for s in _sources_over(p, path))
        for s in sentences(value):
            said.add(s)
            why = claim(s)
            if why and not cites and not ok(s):
                out.append(('.'.join(path), s, why))
    text = text if text is not None else system_text(p)
    # The Layout is written from the frame: each of its numbers is a frame value.
    layout = frame_layout(p)
    if layout:
        text = text.replace(layout, '')
    # And Differences is the ledger's own words (each deviation's `here`), each
    # with its evidence there.
    for e in (ledger or {}).get('entries') or ():
        if e.get('here'):
            text = text.replace(e['here'], '')
    # What the README says in the profile's words is the profile's claim,
    # linted there (a border's usage comes into it lower-cased); and a
    # component README's common paragraph is one claim, however often said.
    said = {x.lower() for x in said}
    for s in dict.fromkeys(sentences(text)):
        low = s.lower()
        if low in said or any(x in low for x in said if len(x) > 40):
            continue
        why = claim(s)
        if why and not ok(s):
            out.append(('README', s, why))
    return out


# -- the caption lint ---------------------------------------------------------
# What a caption must not be, whatever the template: a generic verb where the
# template names the action on the button ("Do you want to power down the
# system?" [Power Down] [Cancel], never [Yes] [No] or [OK]).
GENERIC = ('Submit', 'OK', 'Okay', 'Ok', 'Yes', 'No', 'Done', 'Apply', 'Go', 'Confirm', 'Click Here',
           'Press Here')
# Capitals that are no shout: the acronyms a source or a call is named by.
ACRONYMS = ('PC', 'TV', 'AUX', 'VTC', 'USB', 'DVD', 'AV', 'VC', 'HDMI', 'PTZ', 'DSP', 'IP', 'ID', 'UI', 'TLP',
            'CD', 'HD', 'UHD', 'AM', 'PM')
# The words a Title Case caption leaves small.
_SMALL = {'a', 'an', 'and', 'as', 'at', 'by', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'with', 'from'}
_CAPTION = re.compile(r'<x-import component-from-global-scope="[\w.]+\.Button"[^>]*>(.*?)</x-import>', re.S)
_TITLE = re.compile(r'<x-import component-from-global-scope="[\w.]+\.(?:Section|Page|Group)"[^>]*?\btitle="([^"]*)"')


def _captions_in(text):
    """(caption, kind) for every Button's caption and every Section's, Page's
    and Group's `title` in a README's code."""
    out = []
    for code in re.findall(r'```(?:html)?\n(.*?)```', text, re.S):
        out += [(c, 'caption') for c in _CAPTION.findall(code) if '<' not in c]
        out += [(c, 'title') for c in _TITLE.findall(code)]
    return out


def _profile_captions(p):
    """(where, caption) for every caption example the profile gives: its
    examples' and regions' `text`, its `writing` buttons' words and its
    voice's launchers."""
    out = []

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                if k.startswith('_'):
                    continue
                if k == 'text' and isinstance(x, str):
                    out.append(('.'.join(path + (k,)), x))
                else:
                    walk(x, path + (k,))
    for key in ('examples', 'regions'):
        walk(p.get(key) or {}, (key,))
    w = p.get('writing') or {}
    out += [(f'writing.buttons.{k}', v) for k, v in (w.get('buttons') or {}).items() if isinstance(v, str)]
    out += [(f'writing.voice.launchers.{i}', v) for i, v in enumerate((w.get('voice') or {}).get('launchers') or ())]
    return out


def _caption_fault(p, caption, kind='caption'):
    """Why a caption contradicts the template's words, case or voice, or None."""
    t = p['template']
    voice = (p.get('writing') or {}).get('voice') or {}
    c = ' '.join(caption.split())
    if not re.search(r'[A-Za-z]', c):
        return None
    if c.lower() in {g.lower() for g in GENERIC}:
        return f'a generic verb: {t} names the action on the button'
    if kind == 'caption' and c in (voice.get('instead') or {}):
        return f"{t} says '{voice['instead'][c]}'"
    caps = voice.get('caps') or ()
    words = re.findall(r"[A-Za-z][A-Za-z'/-]*", c)
    shouts = [x for x in words if len(x) > 1 and x.isupper() and x not in ACRONYMS and x not in caps]
    if shouts:
        return f'capitals where {t} writes Title Case'
    if c in (voice.get('sentence') or ()):
        return None
    if [x for i, x in enumerate(words) if x[0].islower() and (i == 0 or x.lower() not in _SMALL)]:
        return f'{t} writes captions and titles in Title Case'
    return None


def caption_lint(p, text=None):
    """[(where, caption, why)] for every caption example of the README, the
    component READMEs and the profile that contradicts the template's words
    (`writing`), case or voice (`writing.voice`): a generic verb, capitals
    where it writes Title Case, a caption it words otherwise."""
    text = system_text(p) if text is None else text
    out = []
    for c, kind in dict.fromkeys(_captions_in(text)):
        why = _caption_fault(p, c, kind)
        if why:
            out.append(('README', c, why))
    for where, c in _profile_captions(p):
        why = _caption_fault(p, c)
        if why:
            out.append((where, c, why))
    return out


def audit(theme, profile=None, text=None):
    """[finding] for a theme: its unresolved ledger entries, its unbacked
    claims, then its captions out of the template's voice. `profile` and
    `text` stand in for the theme's own, for tests."""
    p = profile or load(theme)
    ledger = load_ledger(theme)
    text = system_text(p) if text is None else text
    out = audit_ledger(p, ledger, text)
    for where, s, why in lint(p, ledger, text):
        out.append(f'claim at {where} ({why}), not backed by the ledger, the frame or a source naming '
                   f'the seed and its page: {s}')
    for where, c, why in caption_lint(p, text):
        out.append(f"caption '{c}' at {where}: {why}")
    return out


def main(argv):
    if len(argv) != 3 or argv[2] not in TEMPLATES:
        print(f"python -m gdl.designsys audit <{'|'.join(TEMPLATES)}>")
        return 2
    out = audit(argv[2])
    for line in out:
        print(line)
    ledger = load_ledger(argv[2])
    n = len((ledger or {}).get('entries') or ())
    print(f"{argv[2]}: {len(out)} finding{'' if len(out) == 1 else 's'}"
          f" ({n} ledger entr{'y' if n == 1 else 'ies'})")
    return 1 if out else 0
