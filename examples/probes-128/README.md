# Format probes on GUI Designer 1.28 (backlog package 2.1)

Seven probes, one unattended Windows session, one folder of results to send
back. Written on Linux, where none of it can be built; every input here checks,
plans and finds its donor, and the runner parses, but what GUI Designer does
with them is what the session finds out.

Run once, on GUI Designer 1.28.0.7: what each probe answered is in the docs
its *Changes* names, and the record - the summary, logs, the reader's output
and the watcher's captures the docs cite - in
`archive/job-e823df9b/probes-128/`. `horizontal-slider` was reported failed
there by `verify_built`'s rail and thumb models, which the probe proved wrong
and which now pass the same build.

## Running it

On the Windows host with GUI Designer installed, from the repo root, in a
console or Remote Desktop session that stays unlocked (it does not need the
foreground):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File examples\probes-128\Run-Probes128.ps1
```

- Start with GUI Designer closed; it is stopped before every build, as
  `powershell\New-GdlPanel.ps1` stops it, and never two at once.
- The preferences prompt of `docs/from-scratch.md` §7 (*Save and Build
  Optimization*) must already be answered for 1.28.0.7, or the first build stops
  at it and says so.
- A probe that fails is written down and the next one runs. `-Only <names>` and
  `-Skip <names>` choose; `-Out` and `-Work` move the results (`out\probes-128`)
  and the scratch (`C:\gdlwork\probes-128`).
- Expect an hour or two: each probe is one to three builds of a small panel,
  and `twins-1535` is a real-size one. Past `-TimeoutSeconds` a wait runs on
  while GUI Designer is busy (`docs/from-scratch.md` §7).
- Send back the whole `out\probes-128` folder - the `.gdl` files are the
  results - or, from a checkout with Pillow, run
  `python examples/probes-128/read_probes.py out/probes-128` first and send
  that beside it. The runner ends by running it into `summary.txt`.

Needs the client fixture `fixtures/gdl/client-boardroom-2.0.0.gdl` for
`format-probes` (the archive only; a seed stands in, and `fixture.txt` and the
summary say so - the 34-against-35 figure is the fixture's).

## What is here

| File | What it is |
|---|---|
| `Run-Probes128.ps1` | The runner. Builds with `New-GdlPanel.ps1` where a spec is the input, and with its own open - Save and Build - wait, the same steps, where the file is authored by something else. |
| `Watch-BuildManager.ps1` | Runs beside each build and records the windows GUI Designer shows besides its main one, each one's text read two ways, and pictures. See below. |
| `Add-BorderResources.ps1`, `Set-ReferenceCounts.ps1` | The two authoring steps the shipped path has no way to take; 32-bit Windows PowerShell 5.1, like the applier. |
| `probe_tools.py` | Rebinds the border plan; translates the 1535 canvas. |
| `read_probes.py` | Reads the results. Runs on any OS with Python 3; the artwork figures need Pillow. |
| `specs/`, `canvas-1535/`, `borders.json`, `renumber-*.json` | The inputs. |

## The probes

Each result is a figure the reader prints; `probe.log` in each folder is the
whole record, and `buildmgr-*` the Build Manager's.

### `format-probes` - the probes' counts on 1.28, and test 3

- **Input:** `powershell/New-FormatProbes.ps1` on `fixtures/gdl/client-boardroom-2.0.0.gdl`
  (what its 1.27 and 1.28 runs used): tests A (a border resource never
  referenced), B (an appended `Claude - 20 Radius 1 Thick`) and C (a control
  cloned across two graphs). The script only authors them; the runner packs each,
  opens it, Save and Builds it, and watches the Build Manager.
- **Proves:** that all three still open and build on 1.28.0.7 - the readout the
  1.27 numbers came from - and, by `buildmgr-test*`, whether a script can read
  that readout at all.
- **Read:** `read_probes.py`: per test, whether the built file has a payload;
  A's control still on `3D Capsule`; B's 35 resources against 34 and the new one
  defined, bound and with its geometry; C's page gaining a control. The Build
  Manager's counts: the figures in the last `dump-*.txt` of each window, grepped
  for *error* and *warning*; `windows.log` lists the windows; `screen-*.png` is
  the screen every six seconds - read those if the dumps hold no count. On 1.28
  neither holds one: a clean build's Build Manager shows only its phase.
- **Changes:** `docs/from-scratch.md` §5's preamble and the table's rows 1-4;
  the RESULTS note of `powershell/New-FormatProbes.ps1`; the probes' bullet of
  `docs/ROADMAP.md`. If the dumps carry counts, the build scripts can read them
  (`docs/from-scratch.md` §7, *Wait by watching the `.gdl` itself*).

### `borders` - a radius and thickness outside the corpus, on a visible control

- **Input:** `specs/afterburn-borders.json` - six panels on the Afterburn 1035
  seed, each filled and stroked - and `borders.json`: each panel's resource and
  geometry. The spec names the corpus's own border and `probe_tools.py
  bind-borders` rewrites the plan, because `gdl.spec check` refuses a resource
  the project does not carry; `Add-BorderResources.ps1` appends them to the
  donor first. `Afterburn - 10 Radius 2 Thick` is the control, in the corpus;
  the others are 20/1, 40/6, 0/12, 60/3 and 100/9.
- **Proves:** that Build rasterizes a geometry no template defines, at that
  geometry - test 3 was only half answered, on the Offline Window, which has no
  artwork.
- **Read:** per panel, the fitted corner radius and stroke pixels measured off the built
  PNG against the asked radius and thickness, and the share of pixels that
  differ from `gdl.compose`'s drawing of the same geometry; `verify_built` (in
  the log) holds each panel's resource name and colours. Expect the control to
  be near 0%; a large share on the others is a preview that is wrong, or a
  border Build drew differently.
- **Changes:** `docs/from-scratch.md` §5 row 3 and §6's *Test 3* bullet;
  `docs/ROADMAP.md`'s border item. A match lifts the reason `gdl.spec`
  maps a missing border to the nearest one (`nearest_border`,
  `Set-GdlBorder`) from a safety rule to a choice.

### `horizontal-slider` - Shockwave's non-square thumb lying down

- **Input:** `specs/shockwave-hslider.json` on `seeds/Shockwave 1035.gdl`: a
  slider lying right at 700 and one left at 500, a short one with a 40 x 26
  thumb, and the template's vertical slider as the control. The thumb is 52
  across and 34 along, which the plan writes as 34 wide and 52 tall.
- **Proves:** how Build keeps a non-square thumb on a horizontal slider and
  where it draws the rail - `verify_built`'s horizontal rail model only
  mirrors the vertical one.
- **Read:** per slider, the fields as built (`SliderIndicatorWidth`/`Height`,
  track, orientation) and the extents of the empty rail, full rail and thumb
  artwork - inset at each end, thickness, centring - and the share the empty rail
  differs from three models. The same extents for the Zoom Rooms seed's two
  horizontal sliders print beside them, for comparison: their rail is inset half
  the thumb at each end.
- **Changes:** `tests/verify_built.py`'s `rail_image` docstring (*Only vertical
  sliders were measured*) and `gdl/spec.py`'s swap of across and along, with a
  test; `docs/ROADMAP.md`'s slider item.

### `reference-counts` - what `referenceCountField` does

- **Input:** `specs/afterburn-groups.json`: three popup groups of 1, 3 and 5
  members, each shown by a reference. The runner builds it, rewrites the
  registry (`Set-ReferenceCounts.ps1`: `One=46`, `Three=0`, `Five=1`), and
  builds that.
- **Proves:** whether Build recomputes the count, keeps it, or ignores it - the
  applier writes a constant 2, a client's project stores 46, 8, 13 and 2 against
  11, 1, 2 and 2 members.
- **Read:** the registry at each stage - as built from the spec, as written, as
  rebuilt - beside each group's members and references, with a verdict per
  group (kept, recomputed to the popups, recomputed to the references,
  changed). `verify_built` holds the rebuilt panel to the plan: a rewritten
  count that cost a binding fails it.
- **Changes:** `docs/gdl-format.md` §6 and the gotcha in §7; `docs/from-scratch.md`
  §5 row 6; the constant in `Register-GdlPopupGroup` (`powershell/GdlProject.ps1`);
  `docs/ROADMAP.md`.

### `renumber-seed` and `renumber-generated` - `renumber` through a build

- **Input:** `renumber-seed.json` against `seeds/Afterburn 1035.gdl` (a popup's
  twelve buttons from 20000, and a mirror - `TV Preset 1`, on two popups under
  one ID - renumbered by name); `renumber-generated.json` against the panel the
  runner first builds from `examples/huddle-functions.json`. Each: `gdl.edit
  check`, `plan`, `Apply-GdlEdits.ps1`, pack, Save and Build,
  `tests/verify_built.py` on the edit plan, then `gdl.idmap from-built` of the
  file before and after and their diff.
- **Proves:** that `renumber` survives a build - `verify_built` has compared
  `UserId` since it learned to, and nothing has ever passed it on a real build.
- **Read:** the verifier's line; the reader's count of controls built with the
  new ID, still on the old, or elsewhere, found by page and name since Build
  renumbers pages; new IDs two controls share; and the ID map's diff.
- **Changes:** the `renumber` row and the opening sentence of `docs/editing.md`
  ("planned and checked, but has not been through a build"); `docs/ROADMAP.md`;
  the over-claim noted in `docs/history.md`.

### `twins-1535` - Shockwave's tab twins on the 1535

- **Input:** `canvas-1535/`, the Shockwave region canvas
  (`tests/data/design-regions-shockwave`) with its panel list cut to
  `TLP1535M`, and the spec it translates to, `specs/shockwave-1535-twins.json`
  (`python examples/probes-128/probe_tools.py translate examples/probes-128/canvas-1535
  shockwave out/1535`). Built on `seeds/Shockwave 1535.gdl` with `-IdMap`.
  **The 1535 seed is the TLP1535M's:** a canvas listing `TLP1535T` is refused
  for want of a seed.
- **Proves:** that the four caption-only buttons sharing each source tab's ID
  on one page - the first spec mirrors - build as planned on the 1535, as they
  did on the 1035.
- **Read:** per shared ID, controls built against planned, their rectangles and
  captions; `verify_built`'s and `verify_idmap`'s lines in the log.
- **Changes:** the region item in `docs/ROADMAP.md` ("and the 1535's, which no
  region canvas lists, waits for a probe"); `docs/claude-design.md` if a canvas
  may then list the 1535M.

## The Build Manager

Nothing here has read it. `Watch-BuildManager.ps1` records, for each window of
GUI Designer's besides its main one: when it came and went (`windows.log`), its
descendants as `WM_GETTEXT` and as UI Automation read them (`dump-*.txt`, up to
twelve per window while it stays), a picture of it, and a picture of the screen
every six seconds. It clicks nothing. If it finds nothing, the pictures are the
readout. A window's picture is taken after its dump, whose UI Automation walk
took about 16 s against a busy GUI Designer, so it often shows what was behind
the window by then; the screen pictures are the ones that show it.
