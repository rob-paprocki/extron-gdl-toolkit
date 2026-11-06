# docs/

Read `gdl-format.md` first. Most of what it records was expensive to find,
and getting its §2, §4 or §6 wrong fails silently: the file opens, builds,
and is wrong.

## How-to

| doc | read it when |
|---|---|
| `gdl-format.md` | before writing to a project: the container, what Build regenerates, why to clone and never construct, where popup bindings live |
| `from-scratch.md` | generating a panel from a spec, and driving GUI Designer from a script (§7) |
| `editing.md` | changing a panel that already exists |
| `idmap.md` | handing a panel to its programmer: the ID map, and how IDs stay stable across revisions |
| `claude-design.md` | designing on a Claude Design canvas and building from it. It is long; §1 is the procedure |
| `design-rules.md` | checking a design against Extron's own standards, kept apart from what was extrapolated |

## Reference and record

| doc | what it is |
|---|---|
| `render-fidelity.md` | what GUI Designer actually draws, measured against its own renders |
| `ROADMAP.md` | what is left, in order, and who has to do it |
| `history.md` | retired setups and corrected claims. Not needed to use the toolkit |
| `superpowers/` | dated design specs and implementation plans: the record of how features were decided, not instructions |
| `panel-preview.png`, `generated-built.png` | `examples/panel.json` as previewed, and as GUI Designer built it |

Many of these cite `archive/job-*` folders as evidence. The public copy holds
those back, so there a citation means the private archive's copy. A citation of
`fixtures/` or the client's project names files deleted in 2026-11 (`history.md`);
the render baseline is now `tests/data/synthetic/`.
