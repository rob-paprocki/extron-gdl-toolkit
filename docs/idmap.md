# The ID map: what a programmer gets with the panel

A panel is handed to its programmer with an ID map. It lists every control a
program can address, with its ID, type, page, name and caption, and what it
does. The map is written from the same spec the panel is built from, so the two
cannot drift apart, and it is checked against the built file.

```bash
python -m gdl.idmap check examples/huddle-functions.json
python -m gdl.idmap write examples/huddle-functions.json out/idmap   # idmap.md, .json, .csv
```

With GUI Designer installed, `powershell\New-GdlPanel.ps1 -IdMap out\idmap`
does all of it and verifies the map against the built panel.

## 1. Why a map, and not the panel

**A `.gdl` carries no behavior.** Nothing in the current format says "this
button shows that page". GUI Designer's previous generation had per-button
actions (`PanelBuilder.PBActionShowPage`, `PBActionShowPopup`, `PageBack` and
so on, still visible in `GUI Designer.xml`), but they are gone. They appear in
none of the 26 projects checked (6 fixtures and 20 seeds), and converting an
old project says so outright: *"Local Actions and Audio Resources will be
lost!"*

The format keeps structure only: a start page, popup groups, whether a popup is
modal, an Offline Page, and a numeric ID on every control. Everything a control
does lives in the control program, whatever it is written in, and that program
finds the control by its ID.

**The addressing rule.** A **control** is addressed by its numeric ID, which
survives Build. A **page or popup** is addressed by **name**. Its number does
not survive: a page authored as 1000 comes back from Build as 51
(`docs/gdl-format.md` §7). The map never lists a page number.

## 2. Saying what a control does

Two optional keys go on a control. `examples/huddle-functions.json` is a prose
brief written out this way.

| Key | On | Means |
|---|---|---|
| `nav: "<page or popup>"` | button | Shows that page or popup. This one is **checked** (§3). |
| `does: "<sentence>"` | button, label, level, slider | Anything else, in words, for the programmer: *"Routes the laptop to the display; On while it is live."* |

Two more keys go elsewhere:

- `"reached_by": "program"`, on a page or popup, says the control program shows
  it (an incoming-call popup, for example), so no `nav` has to lead there.
- A top-level `does`, a sentence or a list of them, holds panel-wide functions
  such as *"After ten minutes idle, return home."*

Only the four addressable kinds can carry these keys. Panels, lines, images,
clocks and popup references have no ID a program can take hold of.

**Mirrors.** Controls that pin the same `id` are one control to the program.
Extron's own projects do this on purpose: Liberty Bank mirrors its shutdown
confirm and cancel buttons (81, 82) across two popups. The map lists a mirror
once, with every place it appears. Each copy has to be the same kind doing the
same thing.

## 3. The checks

`check` runs `gdl.spec check` first. Problems block `write`, the same way they
block `plan`.

| Problem | Why |
|---|---|
| A `nav` target that is not a page or popup in the spec | The button would flip to nothing |
| `nav` on anything but a button; `does` that is not a sentence; either key on a kind with no ID | It would go nowhere |
| A standard popup shown where the page beneath has no reference to its group. For a popup shown from another popup, that means every page the first can be showing over. | A standard popup appears only through such a reference (`docs/gdl-format.md` §5) |
| Controls sharing an ID but differing in kind or function | A program sees one control per ID |
| A page or popup no `nav` reaches from the start page, unless it is `reached_by: "program"` | Dead layout, or a missing link |

The reachability check runs only when the spec uses `nav`. Three unlinked pages
in a layout-only spec are a layout, not a broken panel.

**Notes** never block. They cover a button whose function is not described
(once the spec describes any), and a dead-end page that leads to no other page.

The toolkit does **not** require confirmations. Extron's standards ask for a
modal confirmation before costly or irreversible actions (`docs/design-rules.md`
§2), but modern call controls end a call with one tap. Whether an action asks
first is a design decision for the spec. It is not a rule to enforce.

## 4. The map

`write` produces three files with the same content:

- `idmap.md`, to read;
- `idmap.csv`, one row per ID, for a spreadsheet;
- `idmap.json`, which is what the verifier reads.

Each control row carries its ID, type, the page and control name of every place
it appears, its caption, and its function (`nav` and `does`, in words). The page
table shows how each page and popup is reached. Every file carries the spec's
SHA-256.

## 5. Verification

`python tests/verify_idmap.py <idmap> <built.gdl>` checks the map against the
built `layout.json`:

- Every page and popup it names exists, as the kind it says.
- Every control is where the map says, with that ID and that type. Every control
  of that name is checked, not just the first.
- No other control on a mapped page shares a mapped ID. A donor page doing so is
  a note, because it answers to the same handler if it is ever shown.
- No page or popup name appears twice.
- Every popup a button shows can appear over every page it can be shown on.

It exits non-zero on any problem. `tests/test_verify_idmap.py` makes it fail on
each of those.

**End to end.** `examples/huddle-functions.json` was built on
`seeds/Afterburn 1035.gdl` with `New-GdlPanel.ps1 -IdMap` on GUI Designer
1.28.0.7. The layout verified with 98 controls and 0 problems. The map's 27
references verified with 0 problems.

## 6. Designing in Claude Design

The same keys are the target for a Claude Design canvas:

| Design canvas | Spec |
|---|---|
| A prototype link `<a href="X.dc.html">` | `nav: "X"` |
| A component's annotation or description | `does` |
| Repeated component instances | `grid` / `stack`, with per-item overrides |

The translator itself is on `docs/ROADMAP.md`.
