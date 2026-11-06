# gdl/

The Python package. It needs only the standard library, apart from Pillow for
rendering (`compose.py`). The package is not pip-installable, so run each
entry point from the repo root as `python -m gdl.<module>`.

## Entry points

| module | does | needs |
|---|---|---|
| `spec` | `check`, `render`, `donors`, `icons`, `plan`: a panel described as JSON, laid out, its IDs allocated, previewed, and turned into the build plan `powershell/` applies | Pillow for `render` and `icons` |
| `edit` | `check`, `plan`: rename, restyle, states, retarget and renumber for a panel that exists, resolved against the real file before anything runs on Windows | |
| `idmap` | `check`, `write`, `write-panels`, `from-built`, `diff`: the ID map a programmer works from, with every addressable control, where it is and what it does | |
| `design` | `translate`, `pin-runtime`: a Design canvas to a spec for each panel it lists, laid out in headless Chrome with the canvas's own runtime | Chrome |
| `designsys` | `build`, `extract`, `audit`: an Extron template as a Design System artifact, and a check of each theme's truth ledger | Extron's files for `extract` |
| `seeds` | `pick <spec.json>`: the seed a spec builds on | the seeds, via Git LFS |
| `container` | `extract`, `pack`, `payload`: open and repack a `.gdl` | |
| `data` | `<folder> <out.json> [name filters]`: the render model the HTML viewer in `viewer/` reads | |
| `project` | `<file.gdl>`: the authoring model, read without GUI Designer. Run directly, it prints the border resources and the controls whose fill Build does not export | |
| `fonts` | `<file.gdl> [dest]`: recovers the fonts a project embeds | |
| `templates` | `<Theme> [model] [WxH]`: which Extron series template a panel model takes | Extron's templates, in `vendor/` or an install |
| `themes` | `<template.glt or project.gdl>`: Afterburn's tokens, and the palette of any template | |

## Internals

| file | what it is |
|---|---|
| `nrbf.py` | the .NET BinaryFormatter reader under `project.py`. It is terse on purpose |
| `compose.py` | the reference compositor: draws a page the way GUI Designer does, and renders `spec`'s previews |
| `sfnt.py` | exact glyph advances from a font's own tables, so text wraps and centers as GUI Designer's does, and each glyph's outline box (`research/synthetic_ink.py` measures ink on it) |
| `designsys/` | each theme's profile (`afterburn.json` and the rest), the canvas components every template shares (`bundle.js`), including the region components (Header, LeftRail, Section, RightRail, Footer, Center) that draw each template's working page from its measured frames, and `truth/`, each theme's ledger of what its profile once said that its template does not do |
| `fonts/` | the Open Sans faces the renderer ships with. `fonts/README.md` says how to recover the rest and why they are not tracked |
| `dc_runtime.json` | the Design canvas runtimes `design` accepts, pinned by SHA-256 |
