"""Inject a render model into the viewer template to make a standalone page.

    python viewer/build_viewer.py viewer/template.html panel-data.json out.html

The template is a fragment: it is also published as a Claude Artifact, which
supplies its own document shell. Standalone it needs a doctype and an explicit
charset, or browsers sniff windows-1252 in quirks mode and every non-ASCII
character in the chrome renders as mojibake.

The page inlines all panel artwork as data URIs, so it works from a file:// URL
with no server. It does still pull its two UI typefaces from Google Fonts; with
no network the chrome falls back to a system sans and the panel captions to
whatever the machine has, which changes their metrics but not the layout.
"""
import sys

SHELL = '<!doctype html>\n<meta charset="utf-8">\n'

tpl, data, out = sys.argv[1], sys.argv[2], sys.argv[3]
with open(tpl, encoding='utf8') as fh:
    template = fh.read()
with open(data, encoding='utf8') as fh:
    model = fh.read()

assert '/*__DATA__*/' in template, 'template is missing the /*__DATA__*/ placeholder'
with open(out, 'w', encoding='utf8') as fh:
    fh.write(SHELL + template.replace('/*__DATA__*/', model))
print(f'{out}  {len(SHELL) + len(template) + len(model):,} bytes')
