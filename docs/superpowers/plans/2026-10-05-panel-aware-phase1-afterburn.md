# Panel-aware Phase 1 - Afterburn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One Afterburn Claude Design canvas, `panels="TLP1035T TLP725T TLP525T TLP320M"`, translates to four specs, builds on four seeds and verifies on every panel, with one ID map - each panel sized for its own screen.

**Architecture:** The design system's components derive each panel's layout from the canvas (spec §1, "where derivation lives"). A Page resolves its panel from a model table the bundle carries; frames (the page, `MainArea`, a new `Rail`) map the design panel's regions onto that panel's series regions by a uniform scale; controls grow to the panel's touch minimum and its type floor; a new `Group` reflows its cells and paginates by tier. The translator runs the same bundle headlessly once per panel and reads the derived structure from `data-gdl`.

**Tech Stack:** Python 3 (stdlib outside `gdl/compose.py`), headless Chrome with the Design type runtime (`$GDL_DC_RUNTIME`), 32-bit Windows PowerShell 5.1 and GUI Designer 1.28.0.7 for builds.

**Spec:** `docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md`. Phase 0's plan, `docs/superpowers/plans/2026-09-24-panel-aware-design-systems.md`, lists Phase 1 at task level; this plan replaces that section.

**Branch:** `feat/panel-aware-afterburn`, from `main` at `4c44164`. One PR.

**Steps:** ticked when done. A note under a step says how it differs from what is written, where it does; the one step still open is unticked.

## Global Constraints

The Phase 0 plan's Global Constraints hold unchanged. In particular:

- Python is stdlib-only outside `gdl/compose.py`.
- A change and the docs it invalidates land in the same commit.
- `fixtures/` is read-only.
- Kit art goes only into the owner's private design system.
- Never push to `main`; merge only when the owner asks.
- Scratch goes in `C:\Users\<user>\.claude\jobs\2419a20b\tmp`.

Added for this phase:

- `bundle.js` serves all four templates. Everything per-panel is optional in `P`, and Mach, Shockwave and Turbulence behave exactly as today until their own phase.
- Existing single-panel canvases and specs keep translating and building unchanged. A canvas with no `panels` is its profile's one design panel.
- Chrome tests use `designsys.bundle(p, art=False)` and skip without `$GDL_DC_RUNTIME`.

## Rulings - where the spec is silent or wrong

Each is recorded in the ledger. The cost is what a wrong call would cost.

1. **Derived navigation gets an ID and goes in the ID map.** Spec §4.2 says rail, Previous, Next and Back buttons carry "no program ID". But a `.gdl` carries no behaviour (`docs/idmap.md` §1): only the program flips pages, by the button's ID. A derived button left out of the map is a dead button on the real panel.
   - They take IDs from a reserved band (50001 and up), the same ID for the same derived name on every panel.
   - They are listed in the map as derived navigation, with the panels they exist on.
   - Cost if wrong: extra rows in the map.
2. **Type scales with its frame, never below the panel's floor:** `pt = max(floor, round(pt_design × s))`.
   - Spec §4.1 says type "stays in points". At 1.375 px/pt on every panel, a 38 pt title is 52 px tall on a 320×240 and cannot fit.
   - Extron steps type down on smaller series too (spec §3, Turbulence 16 → 12 pt).
   - The floor is `max(14, ceil(14 × dpi / 149))`, using ceil because a floor is a minimum. That gives 16 on a 725, 18 on a 525 and 835, 28 on a 535, and 16 on a 300M.
   - Cost if wrong: titles smaller than the owner wants on small panels.
3. **Frames, not per-control coordinates.**
   - A control maps to a panel through the frame it is drawn in, at one uniform scale `s` per frame, centred: `MainArea` maps to the series' main region, `Rail` to its rail band, and anything else on the Page to the whole canvas.
   - Nothing is stretched non-uniformly, so squares stay square.
   - A control on the Page outside both frames is mapped with the page; on a smaller panel it may land in the squircle and fail the spacing check, which names it.
   - Cost if wrong: canvases need their side controls in a `Rail` to derive well.
4. **`Rail` is new: one per page, a flow stack along the series' rail band.**
   - On tier A and B that is the right band (beside the squircle), stacking down.
   - On tier C it is the 320's footer, running across.
   - A slider in it takes the space the rest leaves.
   - The Afterburn layout notes already put volume and system controls in the right rail.
   - Cost if wrong: a left rail is not derived; design for one rail.
5. **Tier B pages each `Group` in place, always as a popup group in the Group's own box.**
   - The spec's hub (one region shared by every group, switched by a rail of group buttons) needs page-level coordination this phase does not prove.
   - In-place paging keeps every group's items, IDs and names, and is what the plan's Task 9 test asks for ("on a 525 become a hub popup").
   - The shared region goes to the ROADMAP backlog.
   - Cost if wrong: a 525 page with several groups shows them all, each paged, instead of one at a time.
6. **A slider becomes a level with Up and Down buttons on a panel whose seed has no slider.**
   - The 525 and 320 seeds carry `PBLevel` but no `PBSlider`, and clone-never-construct means a slider cannot be authored from them.
   - This is what Extron's own 520 and 320 templates do.
   - The level keeps the slider's ID, so the program's feedback is the same; Up and Down are derived controls (ruling 1).
   - Cost if wrong: the program handles two more IDs on small panels.
7. **Derivation is arithmetic on the canvas's own markup, with no DOM measurement** (revised in Task 8, after a second spike).
   - The runtime hands a component its children as React elements: each x-import is a host `div` whose `style` is the designer's rect, holding the component element and its props (`tmp/spike/kids.dc.html`).
   - A frame (the Page, `MainArea`, `Rail`) lays its children out per panel from those rects and clones each host at its panel rect. A `Group` gets its box the same way. Nothing is scaled by CSS transform.
   - On tiers A and B a frame maps rects by its uniform scale (ruling 3). On tier C it reflows its children into rows in design order: positions scaled by a quarter cannot keep 14 pt lines apart.
   - A frame's problems render as hidden `data-gdl-problem` markers the probe collects, and as a dashed outline the designer sees.
   - Cost if wrong: a runtime that stops passing `style` breaks every frame at once, and the Chrome tests fail loudly.
8. **A series is chosen by model, never by resolution.**
   - Afterburn has no 720 template, and the 800×480 match is the tier B 520, so a TLP720T is refused rather than given a 5" layout.
   - The profile records each series' models, measured with `gdl/templates.py`. A test checks the record against the install when the install is present.
   - Cost if wrong: an unsupported model is named instead of guessed.
9. **Backgrounds use each series' main art.**
   - The 520 and 535 split their art into `_start` and `_main`. A canvas page is a working page, not a splash, so it takes `_main`.
   - The 1720 uses the 1520's 6830×3840 art, as Extron's template and seed do.
   - Cost if wrong: a start page on a 525 shows the hub art.

## Review Focus

1. **A canvas with no `panels`, and every Mach, Shockwave and Turbulence canvas, translates exactly as before.** This covers model, seed, rects and background. Pinned in Task 8 by the existing `TestInChrome` assertions, unchanged, and in Task 10.
2. **A panel whose seed is missing or an LFS pointer** is refused at translate time with the `New-GdlSeed.ps1` command, and nothing is written for any panel. Pinned in Task 10.
3. **A derived name that collides with a name in that panel's seed, or with a canvas name**, is a problem before any build. Pinned in Task 10.
4. **The same canvas control gets the same ID on every panel**, including when derivation inserts controls before it. Pinned in Task 11.
5. **Text that overflows its box on a panel** (type floor up, box scale down) is named, not built clipped. Pinned in Task 9 through the probe's `overflow`, and in Task 12.

---

## The derivation contract (Tasks 7-10 share it)

**`P.models`**, added to the bundle by `designsys.models(p)`, maps each model the profile supports to:

```
{series, size:[w,h], dpi, tier, touch, gap, floor,
 main:[x,y,w,h], rail:[x,y,w,h]|null, rail_axis:'column'|'row', popup:[w,h]|null,
 fit:'fill'|'stretch', backgrounds:{theme id: {image, file}}, seed,
 kinds:{slider:bool, level:bool, popup:bool}, borders:{profile border name: resource}}
```

- `touch` and `gap` come from `gdl.spec.touch_minimums(model)`. `floor` comes from `gdl.spec.type_floor(model)`.
- `main`, `rail`, `popup`, `fit` and `backgrounds` come from the profile's `panels` block for the model's series.
- `seed`, `kinds` and `borders` come from the series entry too, measured off that seed.

**Panels on a Page.**
- `panels="TLP1035T TLP725T ..."` lists the canvas's panels; the first is the design panel.
- The panel a render derives for is `window.__GDL_PANEL` (set by the translator), else `preview`, else the design panel.
- Every Page of a canvas must give the same `panels`. The translator checks this.

**Frame map.** For a design rect `D` and target rect `T`:

```js
s = min(T.w / D.w, T.h / D.h);
x = T.x + (T.w - D.w * s) / 2;
y = T.y + (T.h - D.h * s) / 2;
```

Here panel px = `x + s × local` design px. Each frame clones its children's hosts at the mapped rects (ruling 7); a plain container is scaled as a whole by a transform on a zero-size layer at the frame's origin.
- The Page's frame maps `[0, 0, Dw, Dh]` onto `[0, 0, Tw, Th]`.
- `MainArea` maps `D.main` onto `T.main`.
- `Rail` stacks its children along `T.rail`.

Context carries the cumulative frame `{s, x, y}`.

**Minimums, in panel px.**
- A button, and a slider across its rail, is at least `touch` px. It grows about its centre, as `width: max(100%, touch/s px)` inside a centred box.
- Text is `max(floor, round(pt × s))` pt, drawn at `px(pt) / s` CSS px, so it renders at the panel's true size.
- A label or caption box is at least one line tall at that size.

**Derived structure.** Each derived container is an element with `data-gdl-part`, holding JSON:

```
{kind:'popup', name, group, size:[w,h]}       // tier A/B page of a Group, in its box
{kind:'page',  name, host, size:[w,h]}        // tier C page of a Group
```

- `{kind:'popup_ref', name, group}` is the region on its host, and is an ordinary control.
- The probe reports each part and its rect.
- Each control reports the index of its nearest part (`part`), with its rect relative to that part. Controls outside any part keep rects relative to the Page.
- Inactive parts are laid out with `visibility: hidden`, so they measure but do not paint.

**Names.**
- Derived popups and pages are `"<page> <group title>"`, with a number from 2 on when there are several.
- Derived buttons are `"<title> Previous"`, `"<title> Next"`, `"<title> Back"` and `"<title>"`; the last is tier C's open button.
- A derived control carries `derived: true`. A slider's Up and Down are `"<slider> Up"` and `"<slider> Down"`.

---

## Task 6: Series templates, indexed

**Files:**
- Create: `gdl/templates.py`
- Create: `tests/test_templates.py`
- Modify: `vendor/README.md` (it says nothing reads `TemplateInfoTable.config`)
- Modify: `README.md` *What is here* (one row)

**Interfaces:**
- Produces:
  - `gdl.templates.TABLE_DIRS`: a tuple of dirs searched in order, `vendor/extron/TouchLink Templates` then the install's `TouchLink Templates`.
  - `gdl.templates.table(path=None) -> list[dict]`: every row as `{file, theme, series, size:(w,h), dpi, soft}`. `soft` means the row is a soft client (`ResolutionPlus`). It returns `[]` when no table is found.
  - `gdl.templates.series(theme) -> list[dict]`: one theme's rows, excluding `soft`.
  - `gdl.templates.template_for(theme, model) -> dict | None`. It matches on exact `(size, dpi)`. Failing that, it accepts a size match only when `gdl.spec.tier` of the model equals the tier of the row's diagonal; otherwise it returns `None`. A portrait/landscape tie on the 300M prefers the stem containing `Portrait`.

- [x] **Step 1: Write the failing tests.** Create `tests/test_templates.py`. It skips the whole class when `templates.table()` is `[]`, with the message `'no TemplateInfoTable.config - GUI Designer not installed and vendor/ empty'`. Tests:
  - `test_the_1230w_row`: `Afterburn 1230 Series` has size `(1920, 720)` and dpi `166.0`.
  - `test_a_725_takes_the_1020_series`: `template_for('Afterburn','TLP725T')['file']` ends in `Afterburn 1020 Series.glt`.
  - `test_a_525_takes_the_520_series`.
  - `test_a_535_takes_the_535_series`.
  - `test_a_720_has_no_afterburn_series`: the size match is the 520's tier B, so the result is `None`.
  - `test_ecp_rows_are_soft_and_never_matched`: `template_for('Afterburn','VTLPEcp')` is `None`.
  - `test_a_portrait_300m_takes_the_portrait_series`.
  - `test_no_table_reads_empty`: `table('C:/nowhere/TemplateInfoTable.config') == []`.
- [x] **Step 2:** `python -m pytest tests/test_templates.py -q`. Expected: `ModuleNotFoundError: No module named 'gdl.templates'`.
- [x] **Step 3: Implement** with `gdl.nrbf.parse`:
  - Walk `objects` for the `TemplateManager` root, then `mTemplates`, then `KeyValuePairs`, and dereference every `('ref', n)`.
  - The row's resolution is `mResolution` (`resolutionX`, `resolutionY`, `dpi`), or the `ResolutionPlus` fields, which mean `soft=True`.
  - `theme` is `mTheme`; `file` is the dereferenced `mFilePath`; `series` is the file stem.
  - Comments say what was measured: 50 rows, 13 Afterburn, the enum not used.
- [x] **Step 4:** Run the tests. Expected: 8 passed. *Nine pass: `test_series_lists_one_theme_without_soft_clients` was added.*
- [x] **Step 5:** Fix `vendor/README.md` lines 36-38 and add the README row. Commit: `feat: index Extron's series templates from GUI Designer's own table`.

## Task 7: The profile's per-panel table

**Files:**
- Modify: `gdl/spec.py` (add `type_floor`, after `touch_minimums` ~line 330)
- Modify: `gdl/designsys/afterburn.json` (a `panels` block)
- Modify: `gdl/designsys/__init__.py` (`models(p)`, per-series `backdrops`, the `bundle()` allowlist, `_BACKDROPS` cache)
- Create: `research/2026-10-05/measure_afterburn.py` (the measuring script, cleaned from the mapping run)
- Test: `tests/test_spec.py` (`TestExtronRules`), `tests/test_designsys.py` (new class `TestModels`)
- Docs: `docs/design-rules.md` §1 (type floor home), `docs/claude-design.md` §2 "Spacing and sizes"

**Interfaces:**
- Produces:
  - `gdl.spec.type_floor(target) -> int | None`: `max(14, ceil(14 * dpi / 149))`, or None with no DPI.
  - `gdl.designsys.models(p) -> dict[model, dict]`, the contract above. It returns `{}` for a profile with no `panels`.
  - `gdl.designsys.backdrops(p) -> {f'{series}|{theme}': data URI}`.
  - The profile's `panels` block:

```json
"panels": {
  "_source": ["..."],
  "Afterburn 1220 Series": {
    "models": ["TLP1035T", "TLP1035M", "TLP1025T", "TLP1025M", "TLC1026M", "TLP835T", "TLP835M", "TLP835C", "TLP1220TG", "TLP1220MG", "TLP1225TG", "TLP1225MG"],
    "main": [183, 24, 916, 752], "rail": [1099, 0, 181, 800], "rail_axis": "column",
    "popup": [880, 525], "fit": "fill",
    "backgrounds": {"default": {"image": "6400x4000_bg1.png", "file": "Afterburn/Backgrounds/6400x4000/TLP 1025 & 1220/6400x4000_bg1-default.png"}, "...": {}},
    "seeds": {"TLP1035T": "seeds/Afterburn 1035.gdl", "TLP1035M": "seeds/Afterburn 1035.gdl", "TLP835M": "seeds/Afterburn 835 (Project1).gdl"},
    "kinds": {"slider": true, "level": false, "popup": true},
    "borders": {}
  },
  "Afterburn 1020 Series": {"models": ["TLP725T", "TLP725M", "TLP725C", "TLC726M", "TLP1020T", "TLP1020M", "TLP1022T", "TLP1022M"], "main": [145, 10, 733, 581], "rail": [878, 0, 146, 600], "popup": [692, 406], "fit": "stretch", "...": "..."},
  "Afterburn 520 Series":  {"models": ["TLP525T", "TLP525M", "TLP525C", "TLP520M", "TLC521M", "TLC526M"], "main": [0, 0, 688, 480], "rail": [688, 0, 112, 480], "popup": [686, 480], "fit": "fill", "kinds": {"slider": false, "level": true, "popup": true}, "...": "..."},
  "Afterburn 320 Series":  {"models": ["TLP320M", "TLP320C"], "main": [0, 0, 320, 190], "rail": [0, 190, 320, 50], "rail_axis": "row", "popup": null, "kinds": {"slider": false, "level": true, "popup": false}, "borders": {"afterburn": "Afterburn - 7 Radius 2 Thick"}, "...": "..."}
}
```

  - The remaining series are 1520, 1720, 1230, 535 and 300 (portrait and landscape). They get the measured rows with no seed where none exists.
  - The table's models come from `gdl.templates` (ruling 8).

- [x] **Step 1: Failing tests.**
  - In `tests/test_spec.py` `TestExtronRules`, add `test_the_type_floor_follows_the_dpi`:
    - `type_floor('TLP1035T') == 14`, 725T 16, 525T 18, 835M 18, 535M 28, 320M 14, 300M 16.
    - `type_floor((1000, 700)) is None`.
  - In `tests/test_designsys.py`, add class `TestModels`:
    - `test_every_afterburn_model_resolves`: every model in the profile's `panels` resolves. Each has `tier` in `'ABC'`, `touch`/`gap` equal to `touch_minimums(m)`, and `floor == type_floor(m)`.
    - `test_the_design_panel_agrees_with_the_profile`: `models(p)['TLP1035T']['touch'] == p['touch']`, and the same for `spacing` and `gap`. `main == p['layout']['main']`, `popup == p['popup']`, and the seed is `p['seed']`.
    - `test_the_725_and_1230w_have_their_own_backgrounds`: the file names contain `5120x3000` and `9600x3600`.
    - `test_no_series_claims_a_model_twice`.
    - `test_profiles_without_panels_have_no_models`: mach, shockwave and turbulence give `{}`.
    - `test_the_table_agrees_with_the_install`: skips without `templates.table()`. Every listed model's `template_for` stem equals its series key.
    - `test_a_seed_named_is_a_seed_there`: each named seed exists and `tests/verify_seed.check_seed` passes for its model, skipping an LFS pointer.
    - `test_tokens_still_state_the_design_panel`: the existing token tests are unchanged.
    - *`test_a_seed_named_is_a_seed_there` is `test_a_seed_named_is_that_models_seed`; the existing token tests were left as they were.*
- [x] **Step 2:** Run them. Expected: ImportError for `type_floor`, and `AttributeError: module 'gdl.designsys' has no attribute 'models'`.
- [x] **Step 3: Implement.**
  - Add `type_floor` with a comment pointing to the Phase 0 measurement (`docs/gdl-format.md` §2).
  - Commit the measuring script, which prints the table rows from the installed templates and kit.
  - Write the `panels` block from its output, with `_source` lines saying what each number was measured on.
  - Add `models(p)`, then the backdrops:
    - `backdrops` keyed `series|theme`, fitted or stretched as the series' `fit`, at the series size, JPEG q80.
    - Cache them in `_BACKDROPS`, keyed by template and kit roots, as `_ART` is.
  - Add `models` and `panels_design` (the design model) to the `bundle()` allowlist.
  - *The measuring script is `tests/measure_series.py`, which takes any theme, not `research/2026-10-05/measure_afterburn.py`; the design model is read as `P.models[P.model]`, so there is no `panels_design`.*
- [x] **Step 4:** Run the new tests, then `python -m pytest tests/test_designsys.py tests/test_spec.py -q`. Expected: all pass, with the 300M floor at 16.
- [x] **Step 5:** Docs:
  - `docs/design-rules.md` §1 gets the type floor (ours, not Extron's) and a pointer to the tier table.
  - `docs/claude-design.md` §2 says per-panel sizes come from the model table.

  Commit: `feat: Afterburn's per-panel table - regions, backgrounds, seeds and floors per series`.

## Task 8: Millimetre components and the Page's panels

**Files:**
- Modify: `gdl/designsys/bundle.js`:
  - the resolver near `P` (~line 16-42);
  - `Page` (121-157);
  - `MainArea` (163-169);
  - `font()` (54-65);
  - `Button` (217-285);
  - `Label`, `Clock`, `PopupRegion`;
  - `track()` (345-413) for the slider's minimum and the level conversion;
  - a new `Rail` component.
- Modify: `gdl/designsys/__init__.py`:
  - `COMPONENTS` gains `Rail`;
  - `component_docs`, `previews`, `index_dts` and `readme` get Page `panels` and `preview`, and `Rail`.
- Modify: `gdl/design.py` `PROBE`, which waits for `derived` when the Page has `panels`.
- Create: `tests/data/design-panels/` (canvas.json; `Home.dc.html` with `MainArea` and `Rail`; `Help.dc.html`; `ConfirmRoomOff.dc.html`; all Pages with `panels="TLP1035T TLP725T TLP525T TLP320M"`).
- Test: `tests/test_design.py` (new class `TestPanelsInChrome`, the same skip as `TestInChrome`).

**Interfaces:**
- Consumes `P.models` from Task 7.
- Produces:
  - **Page `data-gdl`** gains `panel` (the model it derived for), `panels`, `tier`, `seed`, `derived: true` and `background_file`. Its `size` is the panel's.
  - **Probe output** gains `parts` and per-control `part` and `overflow`; parts are Task 9's, empty here.
  - **JS helpers** used by Task 9's `Group`:
    - `frameMap(D, T)`;
    - `useFrame()`, which gives `{s, x, y, panel, design}`;
    - `minPx(panel, kind)`;
    - `fontFor(type, size, frame)`.

- [x] **Step 1: Failing tests** (Chrome, using `_translate`'s pattern with a `panel` argument that injects `window.__GDL_PANEL`):
  - `test_a_canvas_without_panels_is_unchanged`: the existing huddle gives the same spec as before, with model TLP1035T, rects and images.
  - `test_the_725_home_sits_in_the_1020_squircle`. On `TLP725T`:
    - Page `size == [1024, 600]`.
    - `background_image` names a `5120x3000` file.
    - Every MainArea control lies inside `[145, 10, 733, 581]`, and a control centred in the design squircle stays centred within 2 px.
  - `test_a_button_meets_the_panels_touch_minimum`: the same Home on `TLP835M` has every button ≥ 67 px both ways, and on `TLP1220MG` ≥ 44 px. The canvas buttons are drawn at 64 or 54 px.
  - `test_text_never_falls_under_the_floor`: on `TLP725T`, every label and button `size` ≥ 16, and on `TLP320M` ≥ 14.
  - `test_the_rail_stacks_down_on_a_725_and_across_on_a_320`:
    - On a 725, Rail controls share one x-centre and increase in y.
    - On a 320, they share a y-centre, lie inside `[0, 190, 320, 50]`, and the slider's `orientation` is `right`.
  - `test_a_slider_becomes_a_level_where_the_seed_has_no_slider`: on `TLP525T` the VolumeSlider is a `level` with the same name. `VolumeSlider Up` and `VolumeSlider Down` are buttons with `derived: true`.
  - `test_a_preview_page_draws_at_its_panel`: with `preview="TLP725T"` and no injection, the Page box is 1024×600.
  - *`test_a_canvas_without_panels_is_unchanged` was not written: the existing `TestInChrome` tests stand for it, and `test_the_design_panel_is_drawn_as_designed` pins that listing panels leaves the design panel as drawn.*
- [x] **Step 2:** Run with `GDL_DC_RUNTIME` set. Expected: the unchanged-canvas test passes; the others fail, because the Page ignores `panels` and `__GDL_PANEL`.
- [x] **Step 3: Implement**, in this order, re-running the tests after each:
  1. The resolver and the Page's panel.
  2. The page frame.
  3. MainArea's frame.
  4. The Button and slider minimums.
  5. Type.
  6. Rail.
  7. The level conversion.
  8. The `derived` marker and the probe's wait.
  - The probe changes are reporting only: parts, `part` indices, and `overflow` (an element's `scrollWidth` or `scrollHeight` beyond its client box by more than 1 px).
  - *Ruling 7 as revised: frames clone each host at its panel rect, so `frameMap`, `useFrame`, `minPx` and `fontFor` do not exist.*
- [x] **Step 4:** Full Chrome run of `tests/test_design.py` and `tests/test_designsys.py`. Expected: all pass, and the existing `TestInChrome` assertions are unchanged.
- [x] **Step 5:** Component docs and README: Page `panels`/`preview`, Rail. Commit: `feat: components size in millimetres for the Page's panel, and a Rail`.

## Task 9: `Group`, reflow and tier pagination

**Files:**
- Modify: `gdl/designsys/bundle.js` (a new `Group`, and Page support for `data-gdl-part`).
- Modify: `gdl/designsys/__init__.py`. `COMPONENTS`, docs, previews and `index_dts` get Group. Groups' kinds stay inside `KIND_TYPE`: derived containers use `data-gdl-part`, not a `kind:` literal on a control.
- Modify: `gdl/design.py` `PROBE`, to report parts.
- Create: `tests/data/design-groups/`, a synthetic canvas: one Page with a Group "Sources" of 8 source buttons in a 900×130 box, `cell="110x110"`, `cap="4"`.
- Test: `tests/test_design.py` (class `TestGroupsInChrome`).

**Interfaces:**
- Produces:
  - **Group props:** `title`, `icon`, `cap` (default 4), `cell` (`"WxH"` design px, default `110x110`), `gap` (design px, default 49, Extron's 1220 source gap) and `joined` (a segmented control: no gap, and each cell's `data-gdl` carries `joined: <title>`).
  - **`data-gdl-part`** containers, per the contract.
- Rules (on panel `T`, in frame `f`):
  - Cell size is `max(cell × f.s, T.touch)`; the gap is `max(gap × f.s, T.gap)`.
  - `perRow = min(cap, ⌊(boxW+g)/(cw+g)⌋)` and `rows = ⌊(boxH+g)/(ch+g)⌋`.
  - Tier A, when everything fits: in place, rows centred.
  - Tier A overflow, and always on tier B: a popup group named `"<page> <title>"` in the box.
    - Each popup holds `perRow × rowsAvail` cells, where `rowsAvail` reserves a bottom row of `touch` for Previous and Next.
    - It has Previous unless first, and Next unless last.
  - Tier C:
    - The box shows one open button, `"<title>"`, with the group's icon, at least `touch`.
    - Derived pages `"<page> <title>"` lay the cells in `T.main`, with Back bottom-left, and Previous and Next bottom-right when several.
  - A Group that cannot hold one cell and its nav row is refused: the Page's `data-gdl` carries `problems: ["<title> cannot fit one cell on TLP320M"]`, and the translator reports them.

- [x] **Step 1: Failing tests** (Chrome):
  - `test_eight_sources_fit_on_a_1035`: 8 buttons in 2 rows of 4, no parts.
  - `test_on_a_725_they_page_in_place`:
    - There is one `popup_ref` with the Group's group.
    - There are two popup parts.
    - Every source is in exactly one part.
    - Part 1 has `Sources Next`, part 2 has `Sources Previous`, both `derived: true`.
  - `test_on_a_525_they_become_a_popup_even_when_they_fit`: 3 sources on a 525 give one popup part, sized to the box.
  - `test_on_a_320_they_become_pages`:
    - The host has a `Sources` button with `nav` naming the page part.
    - The page parts carry `Sources Back` with `nav` naming the host.
  - `test_a_group_that_cannot_fit_is_refused_by_name`: a Group in a 60×60 box on a 320 gives a problem naming the Group.
  - `test_a_joined_group_butts_its_cells`: `joined` cells touch, and each carries `joined`.
- [x] **Step 2:** Run. Expected: fail, because `ExtronAfterburn.Group` is undefined.
- [x] **Step 3: Implement** `Group` with `React.useLayoutEffect` measuring the root once, then the parts, the probe reporting, and the docs. *Ruling 7 again: a Group gets its box from its frame (`__box`), with no `useLayoutEffect`. Its `icon` prop, and the open button's icon on tier C, are not built (`docs/ROADMAP.md` backlog).*
- [x] **Step 4:** Chrome run of `tests/test_design.py` and `tests/test_designsys.py`. Expected: all pass.
- [x] **Step 5:** Commit: `feat: Group - cells that reflow, page in place, or become pages, by tier`.

## Task 10: Translation per panel

**Files:**
- Modify: `gdl/design.py`:
  - `render` takes `panel=`, injected as `<script>window.__GDL_PANEL=...</script>` before the bundle, with the probe file name carrying the panel;
  - `Canvas.translate_panels`;
  - `_spec` reads model, size, seed and images from the Page;
  - parts become popups and pages;
  - derived `nav` resolves to part names;
  - `main` handles an output directory.
- Create: `gdl/seeds.py`:
  - `usable(path) -> bool` (not missing, not an LFS pointer);
  - `command(theme, model, path) -> str` (the `New-GdlSeed.ps1` line).
- Test: `tests/test_design.py` (`TestPanels`, fed probe output through `Fake`; no Chrome).
- Docs:
  - `docs/claude-design.md` §1 (step 3, the out/ layout) and §5;
  - `SKILL.md` (the translate line);
  - `README.md` (the translate line);
  - `CLAUDE.md` *Environment* (the translate cell, which is unchanged in substance);
  - the `gdl/design.py` docstring.

**Interfaces:**
- Produces:
  - `Canvas.translate_panels(rendered=None) -> (specs: dict[model, spec] | None, problems: dict[model, list[str]], notes: dict[model, list[str]])`. It returns `None` for `specs` if any panel has a problem.
  - The CLI: `python -m gdl.design translate <canvas> <out dir>` writes `out/<model>/spec.json` for each panel, or nothing. `translate <canvas> <file.json>` (a path ending `.json`) keeps writing the design panel's one spec.
- Rules:
  - `_seed` is the Page's `seed`. A panel whose seed fails `seeds.usable` is a problem carrying `seeds.command(...)`.
  - A derived part's name that is also a canvas name or a name in the seed is a problem. Seed names are read once per seed with `gdl.project`.
  - Every Page must give the same `panels`.
  - Messages are prefixed with the model.

- [x] **Step 1: Failing tests**, with `Fake` given `{model: {board: probe}}`:
  - `test_each_panel_gets_its_own_spec`: model, size, `_seed` and `background_image` per panel.
  - `test_a_missing_seed_refuses_every_panel`: `specs is None`, and the problem has `New-GdlSeed.ps1 -PanelType`.
  - `test_parts_become_popups_and_pages`: a popup part becomes a `popups[]` entry with group and size, and its controls are relative. A page part becomes a page.
  - `test_derived_nav_names_a_part`.
  - `test_a_derived_name_colliding_with_the_canvas_is_a_problem`.
  - `test_pages_must_agree_on_their_panels`.
  - `test_the_one_file_form_still_writes_the_design_panel`.
  - *`test_derived_nav_names_a_part` is `test_derived_nav_names_a_part_not_an_artboard`. `test_the_one_file_form_still_writes_the_design_panel` was not written; the CLI's one-file branch has no test.*
- [x] **Step 2:** Run. Expected: fail, with no `translate_panels`.
- [x] **Step 3: Implement.**
- [x] **Step 4:** `python -m pytest tests/test_design.py -q` with and without the runtime. Expected: all pass, and the Chrome classes skip without it.
- [x] **Step 5:** Docs, then commit: `feat: translate a canvas once per panel, each on its own seed, all or nothing`.

## Task 11: Shared IDs and one ID map across panels

**Files:**
- Modify: `gdl/design.py`. `translate_panels` pins IDs after every panel is translated:
  - Canvas controls are allocated on the design panel's spec with `Panel`'s own banding (on a deep copy), then written by `(board, name)` into every panel.
  - Derived controls get 50001 and up, in the order of `(container name, control name)`, the same on every panel.
  - An unnamed addressable control on a multi-panel canvas is a problem.
- Modify: `gdl/idmap.py`:
  - `IdMap` records `derived` (a control key);
  - `write_panels(specs: dict[model, spec], out_dir)` and `check_panels(specs)`;
  - a CLI `python -m gdl.idmap write-panels <out dir> <map dir>`.
- Modify: `tests/verify_idmap.py`: `check_layout(idmap_dir, j, panel=None)`, which filters to one panel's rows, and `--panel MODEL`.
- Test: `tests/test_idmap.py` (`TestPanels`) and `tests/test_verify_idmap.py` (`test_one_panels_rows_against_its_build`).
- Docs: `docs/idmap.md` (a section on panels: columns, derived navigation and ruling 1).

**Interfaces:**
- Produces:
  - **`idmap.json`**, with these additions:
    - `panels: [{model, size, tier, spec_sha256}]`;
    - each control's `panels: {model: [{container, kind, name, caption}]}`, with `at` kept as the design panel's;
    - `derived: true` on derived navigation.
  - **CSV and markdown** gain a column per panel, holding where the control is on that panel.
- Checks (`check_panels`):
  - The same ID means the same name, type, states, `does` and `nav` meaning on every panel.
  - A canvas ID absent from a panel is a problem ("nothing is dropped").
  - A derived ID is listed with the panels it is on.

- [x] **Step 1: Failing tests:**
  - `test_the_same_control_has_one_id_on_every_panel`: this holds with a derived Previous inserted before it on one panel.
  - `test_derived_navigation_is_mapped_and_marked`.
  - `test_a_canvas_control_missing_on_one_panel_is_a_problem`.
  - `test_the_single_panel_map_is_unchanged`: the existing `TestOutput` stays as is.
  - `test_one_panels_rows_against_its_build`: `verify_idmap` with `panel=` ignores other panels' containers.
- [x] **Step 2:** Run. Expected: fail.
- [x] **Step 3: Implement.**
- [x] **Step 4:** `python -m pytest tests/test_idmap.py tests/test_verify_idmap.py tests/test_design.py -q`. Expected: all pass.
- [x] **Step 5:** Docs, then commit: `feat: one ID per canvas control on every panel, and one ID map with a column per panel`.

## Task 12: Checks per panel

**Files:**
- Modify: `gdl/spec.py`:
  - `_house_rules(container, label)`, also run on `self.popups`;
  - spacing over `TOUCHABLE` pairs, exempting a pair with the same non-empty `joined`;
  - the type floor through `type_floor(self.model)`;
  - `size in sizes(model)` when both are given;
  - unknown control keys reported.
- Modify: `gdl/design.py` `FIELDS` (`joined`, `derived`) and probe `overflow` becoming a problem.
- Test: `tests/test_spec.py` (`TestExtronRules`, `TestModalPopups`).
- Docs: `docs/design-rules.md` §2 (what is checked) and `SKILL.md` (the checks list).

- [x] **Step 1: Failing tests:**
  - `test_two_touching_segments_pass` (same `joined`).
  - `test_two_touching_separate_buttons_fail`.
  - `test_a_14pt_caption_on_a_535_fails`: the message has `floor` and `28`.
  - `test_a_popup_is_house_checked`: a 20×20 button in a popup on a 1035 fails.
  - `test_a_modal_on_a_725_is_given_its_canvas`: `[1024, 600]`.
  - `test_a_size_the_model_does_not_have_is_a_problem`: `model: TLP725T`, `size: [1280,800]`.
  - `test_an_unknown_control_key_is_named`: `joind`.
  - `test_text_that_overflows_its_box_is_a_problem`, through `design._control` given `overflow: true`.
  - *`test_two_touching_segments_pass` is `test_two_touching_segments_of_one_control_pass`.*
- [x] **Step 2:** Run. Expected: fail.
- [x] **Step 3: Implement**, then check `examples/*.json`.
  - `examples/clean-room.json` (TLP835M, floor 18) has 15 and 16 pt captions. Raise them to 18 in the same commit, and confirm with `python -m gdl.spec check examples/clean-room.json`.
- [x] **Step 4:** Full suite. Expected: all pass.
- [x] **Step 5:** Docs, then commit: `feat: per-panel checks - floor, spacing within segments, popups, model size`.

## Task 13: Build every panel, sign off every panel

**Files:**
- Create: `powershell/New-GdlPanels.ps1`. Parameters: `-Out <dir>` (holding `<model>/spec.json`), `-Name <panel name>`, and the optional `-Models`, `-Python` and `-KeepGoing`.
  - It runs `python -m gdl.idmap write-panels <Out> <Out>\idmap`.
  - For each model it runs `powershell -NoProfile -File New-GdlPanel.ps1 -Spec <Out>\<m>\spec.json -Donor <repo>\<_seed> -Output <Out>\<m>\<Name>.gdl -Work C:\gdlwork\<Name>-<m>` as a child process, so each gets its own exit code, then `python tests\verify_idmap.py <Out>\idmap <built> --panel <m>`.
  - It prints a table of model, built, verified and ID map, and exits non-zero if any panel failed.
- Modify: `gdl/design.py` `compare(folder, out, out_dir, chrome=None)`. When `out` is a directory of panels, it writes one section per panel. The design side is rendered with `__GDL_PANEL` at the panel's size, and each part is shown with `__GDL_SHOW=<part name>`. The built side renders a derived popup inside its host (`render_snapshot(..., shown={GroupID: popup ID})`).
- Test: `tests/test_design.py` (`TestCompare`, with `render`, `screenshot` and `find_chrome` patched, and Pillow required): the index has one `<section>` per panel and names each part.
- Docs:
  - `CLAUDE.md` *Environment* (`New-GdlPanels.ps1` needs GUI Designer);
  - `README.md` (file table);
  - `docs/claude-design.md` §1 step 3 and *What comes out*;
  - `docs/from-scratch.md` §7 (one line: builds are serial and the script kills GUI Designer).

- [x] **Step 1:** Failing compare test.
- [x] **Step 2:** Run. Expected: fail.
- [x] **Step 3:** Implement the compare change and the script.
- [x] **Step 4:** Run the compare test, then build one panel with the script (`-Models TLP1035T`) on the huddle panels canvas. Expected: `PANEL BUILT AND VERIFIED` and the ID map verified for that panel.
- [x] **Step 5:** Commit: `feat: build and verify every panel of a canvas, and compare them side by side`.

## Task 14: Proof, docs, review, PR

- [x] Translate `tests/data/design-panels` (the huddle, panel-aware) to `out/huddle-panels`. Build all four panels with `New-GdlPanels.ps1`, then compare.
  - Expected: four `PANEL BUILT AND VERIFIED` lines, each panel's ID map verified, and a compare index with four sections.
  - Record per panel in `docs/claude-design.md` §6: controls, derived parts, problems (0), and the compare figures.
  - *§6 records controls, problems, ID map and compare figures per panel; derived parts are named in its last column, not counted.*
- [x] Move what this phase made true from the spec into its homes:
  - `docs/claude-design.md` §1-4 (panels, preview, Rail, Group, tiers);
  - `docs/design-rules.md` (tiers and floor);
  - `docs/idmap.md` (panels);
  - `docs/gdl-format.md` (nothing new expected; say so in the ledger).
  - The spec's §5 Phase 1 paragraph says it landed. `docs/ROADMAP.md` item 5 is updated, and the backlog gains the shared tier B region and a left rail.
- [ ] Republish the Afterburn design system (`https://claude.ai/artifact/1nZsxvdm7HsXpfoSXBVjvx`) and the huddle canvas (`https://claude.ai/artifact/EeyjX6LCjnKicv6ZB32xUq`) with `panels` and a `preview` per board. Publish the compare page for the owner's sign-off. *Open: republishing the huddle canvas was declined by the session's permission check (the PR description says so); the design system and the compare page are not recorded as republished.*
- [x] Adversarial review of `git diff origin/main...HEAD`: finders for correctness, silent failure and docs drift, then skeptics, under 10 agents, sonnet. Fix what survives, test-first.
- [x] Push and open the PR "Panel-aware Phase 1: Afterburn on every panel". Its body gives the per-panel results, the rulings and the review.
