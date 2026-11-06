# tests/

The pytest suite, and the scripts that check a panel GUI Designer built.

## Checking a built panel

| script | checks |
|---|---|
| `verify_built.py <plan.json> <built.gdl>` | the built `layout.json` and artwork against the plan that produced it. Exits non-zero on any control that moved, lost its caption, came back with one GUI Designer cuts, or came back different |
| `verify_idmap.py <idmap> <built.gdl>` | an ID map's page names and control IDs against the built panel |
| `verify_seed.py` | that a seed is a themed project of its theme for its model, made from that model's series template, not a blank or the wrong panel |
| `score.py preview` | a spec's preview against the panel built from it |

These read the built file, so none needs GUI Designer. `verify_built.py` and
`score.py` need Pillow.

## Render fidelity

These score the compositor against GUI Designer's own snapshot renders of the
synthetic fixture (`data/synthetic/`), in the public copy too, and need Pillow.
`score.py record` and `score.py diff` score every page and fail on any
regression against `baseline-synthetic.json`; `compare_snapshots.py` prints the
same comparison per page. With no project argument both use the fixture.
`CLAUDE.md` *Verifying a change* has the commands and the current numbers.

## Measurement tools

| script | measures |
|---|---|
| `audit_corpus.py` | the repo's documented beliefs, re-tested against the synthetic fixture, the seeds and Extron's templates |
| `measure_series.py` | a theme's templates and seeds, for the design-system profiles. Needs Extron's templates |
| `type_probe.py` | how many pixels a point is on a panel, off captions Build bakes. A GUI Designer build sits between its two steps |

## The suite

`python -m pytest` from the repo root runs every `test_*.py`. A test whose
input is missing (the seeds before `git lfs pull`, Chrome, the Design runtime,
Extron's templates) skips and says which. Each `test_*.py` is named for the
module or script it holds to account. `data/` holds the synthetic fixture
(its README says what is in it) and the Design canvases and expected outputs
the translator tests lay out; `_corpus.py` finds the seeds and templates.
