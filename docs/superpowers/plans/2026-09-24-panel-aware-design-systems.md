# Panel-aware design systems Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One Claude Design canvas builds a verified `.gdl` for every panel a room has, each sized for its physical screen; then Mach, Shockwave and Turbulence as design systems on the same footing.

**Architecture:** Panels are models from `gdl.spec.MODELS_FULL` (pixels + DPI → diagonal → tier). The design system's components size in millimetres from the Page's panel and derive each panel's layout (reflow, then paginate by tier); the translator runs the same component code headlessly once per panel and writes one spec per panel, each built on its own seed, all sharing control IDs and one ID map.

**Tech Stack:** Python 3 (stdlib outside `gdl/compose.py`; Pillow for rendering), headless Chrome, the Design type runtime (`support.js`), 32-bit Windows PowerShell 5.1 + GUI Designer 1.28.0.7 for writing and building, UI Automation for driving GUI Designer.

**Spec:** `docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md`

**Scope of this plan:** Phase 0 in full detail. Phase 1 at task level - its interfaces depend on Phase 0's two open answers (how the panel draws points; how Claude Design previews a resized Page), so it is re-planned in full, as its own plan, when Phase 0 lands. Phases 2-4 are outlines, re-planned when reached.

## Global Constraints

- Python stays stdlib-only outside `gdl/compose.py` (CLAUDE.md *Conventions*).
- Writing or building a `.gdl` needs 32-bit Windows PowerShell 5.1 and GUI Designer 1.28.0.7; `New-GdlPanel.ps1` relaunches itself under it.
- Terms are GUI Designer's, used exactly: **page** (whole screen), **popup** (standard popup: part of the screen, in a popup group, shown in a region of a page), **modal** (modal popup: full screen over the page, blocks it until closed). Spec §2.
- Touch target ≥ 9 mm and gap ≥ 2 mm are Extron's documented minimums (`docs/design-rules.md` §2). The tier thresholds (6.5", 4") and any physical type floor are this toolkit's, and every doc that states them says so.
- A change and the docs it invalidates land in the same commit; each topic has one home (CLAUDE.md *Keeping the docs true*). No drifting counts in prose.
- `fixtures/` is real client data: read-only. Seeds are Git LFS; the repo stays private while they are in it.
- Extron kit art goes only into the owner's private design system.
- Never push to `main`; one PR per phase, merged only when the owner asks.
- Never write backslash content through a bash heredoc - use the Write/Edit tools for anything with a Windows path.
- Scratch files go in `$CLAUDE_JOB_DIR/tmp` (`C:\Users\robp\.claude\jobs\2419a20b\tmp`), never `/tmp`.

## Review Focus

1. **A size-only spec at 480×320** (the 300M in landscape) is held to the 300M's touch minimum, not silently to none. Pinned in Task 1.
2. **A spec whose panel has no known DPI** (a custom size, or a model whose DPI is missing) says the touch check was skipped instead of passing quietly. Pinned in Task 1.
3. **A type-probe button whose artwork has no caption ink** (flatten did not take, or the text was clipped) reports "no ink", never a 0 px height that reads as a measurement. Pinned in Task 2.
4. **A wizard-made seed that came out Blank**, or for the wrong model, is refused before it lands in `seeds/`. Pinned in Task 4.
5. **A seed script run with a panel or theme name the wizard does not offer** lists what it does offer and exits non-zero, rather than clicking the wrong item. Pinned in Task 4.

---

## Phase 0 - settle the unknowns

Branch: `feat/panel-aware` (exists; spec committed as `2d0d485`). One PR for the phase.

### Task 1: The model table - the 1230W, both 300M orientations, diagonal and tier

**Files:**
- Modify: `gdl/spec.py` (imports ~line 34; after the `TLP300M` patch ~line 193; `_panels()` ~line 213; after `part_number()` ~line 206; `_house_rules()` ~line 865)
- Modify: `docs/design-rules.md` §1 (the 1920 × 720 row; add the tier table)
- Test: `tests/test_spec.py` (class `TestExtronRules`, ~line 359)

**Interfaces:**
- Produces: `gdl.spec.ORIENTATIONS: dict[str, tuple[tuple[int,int], ...]]`, `gdl.spec.sizes(model: str) -> tuple[tuple[int,int], ...]`, `gdl.spec.SOFT_CLIENTS: tuple[str, ...]`, `gdl.spec.diagonal(model: str) -> float | None` (inches), `gdl.spec.tier(model: str) -> 'A' | 'B' | 'C' | None`, `gdl.spec.TIER_A_INCHES = 6.5`, `gdl.spec.TIER_B_INCHES = 4.0`. Phase 1 builds the design system's model table from these.

- [ ] **Step 1: Write the failing tests**

Add to `class TestExtronRules` in `tests/test_spec.py`:

```python
    def test_the_1230w_is_its_real_wide_canvas(self):
        """CreatePlatform hands the 1230WTG back as the base platform class, so
        the probe read 800x480 at 0 DPI - which made its touch check a silent
        no-op. Extron's template table says 1920x720 at 166 DPI."""
        from gdl.spec import MODELS, dpi, touch_minimums
        self.assertEqual(MODELS['TLP1230WTG'], (1920, 720))
        self.assertEqual(dpi('TLP1230WTG'), 166.0)
        self.assertEqual(touch_minimums('TLP1230WTG'), (59, 13))

    def test_a_landscape_300m_has_a_minimum(self):
        """The 300M runs both ways up; a size-only spec at 480x320 had no row
        to find, so no touch check at all."""
        from gdl.spec import touch_minimums
        self.assertEqual(touch_minimums((480, 320)), touch_minimums('TLP300M'))
        self.assertEqual(touch_minimums((320, 480)), touch_minimums('TLP300M'))

    def test_every_panel_has_a_diagonal_and_a_tier(self):
        """Tiers are this toolkit's reading of Extron's templates, not an Extron
        rule: >= 6.5in full layout, 4-6.5in a hub page, under 4in single-purpose
        pages. Soft clients run on a screen their model does not define."""
        from gdl.spec import diagonal, tier
        self.assertAlmostEqual(diagonal('TLP1035T'), 10.13, places=2)
        for model, want in (('TLP1035T', 'A'), ('TLP835M', 'A'), ('TLP725T', 'A'),
                            ('TLP720T', 'A'), ('TLP1230WTG', 'A'), ('TLP525T', 'B'),
                            ('TLP520M', 'B'), ('TLP535M', 'B'), ('TLP320M', 'C'),
                            ('TLP300M', 'C'), ('VTLPEcp', None), ('TLI201', None)):
            self.assertEqual(tier(model), want, model)

    def test_a_panel_with_no_known_minimum_says_so(self):
        """A custom canvas has no DPI to convert 9mm with. Passing quietly would
        read as 'meets the touch minimum'."""
        p = Panel({'name': 'T', 'size': [1000, 700], 'theme': {'text': '#FFFFFF'},
                   'pages': [{'name': 'P', 'number': 1000, 'controls': [
                       {'kind': 'button', 'rect': [0, 0, 20, 20], 'text': 'x'}]}]})
        self.assertTrue(any('no touch minimum' in m for m in p.check()), p.check())
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_spec.py -q -k "1230w or landscape_300m or diagonal_and_a_tier or no_known_minimum"`
Expected: 4 failed - `MODELS['TLP1230WTG']` is `(800, 480)`; `touch_minimums((480, 320))` is `(None, None)`; `ImportError: cannot import name 'diagonal'`; no "no touch minimum" message.

- [ ] **Step 3: Implement**

In `gdl/spec.py`, add `import math` to the imports (alphabetical, after `import json`).

Directly after the existing `MODELS_FULL['TLP300M'] = (...)` patch, add:

```python
# TLP Pro 1230WTG: CreatePlatform returns the base PBTouchPanelPlatformPro, so
# GetDefaultResolutionDpi falls through to 800x480 at 0 DPI (the note above the
# table). Extron's own TemplateInfoTable.config - the template installer's
# table, NRBF, readable with gdl/nrbf.py - gives its "Afterburn 1230 Series"
# 1920x720 at 166.0 DPI, the canvas a built 1230W project reports too
# (docs/design-rules.md section 1).
MODELS_FULL['TLP1230WTG'] = (1920, 720, 166.0, MODELS_FULL['TLP1230WTG'][3])

# A model whose panel runs either way up. The 300M's templates come portrait and
# landscape (Afterburn 300 Portrait and Landscape Series, both 164.83 DPI).
ORIENTATIONS = {'TLP300M': ((320, 480), (480, 320))}
```

After `part_number()`, add:

```python
def sizes(model):
    """Every canvas a model runs at: its one resolution, or both orientations."""
    return ORIENTATIONS.get(model) or ((MODELS_FULL[model][0], MODELS_FULL[model][1]),)


# Soft clients and interfaces run on a screen their model does not define, so
# the table's DPI for them is GUI Designer's default, not a physical fact.
SOFT_CLIENTS = ('TLI101', 'TLI201', 'VTLPAndroid', 'VTLPEcp', 'VTLPWeb', 'VTLPiOS')

# Structural tiers by physical diagonal - this toolkit's reading of Extron's own
# per-series templates, not an Extron rule. Every theme's >= 7in series (720,
# 1020, 1220, 1520, 1720) share one full structure; its ~5in series (520, 535)
# fold it into a hub page and popups; its ~3.5in ones (300, 320) into
# single-purpose pages. docs/design-rules.md section 1.
TIER_A_INCHES = 6.5
TIER_B_INCHES = 4.0


def diagonal(model):
    """A model's screen diagonal in inches, from pixels and DPI; None for a soft
    client or a model with no DPI."""
    if model in SOFT_CLIENTS or not dpi(model):
        return None
    w, h = MODELS_FULL[model][:2]
    return math.hypot(w, h) / dpi(model)


def tier(model):
    """'A' (the full layout), 'B' (a hub page) or 'C' (single-purpose pages)."""
    d = diagonal(model)
    if d is None:
        return None
    return 'A' if d >= TIER_A_INCHES else ('B' if d >= TIER_B_INCHES else 'C')
```

`sizes()` is used by `_panels()`, which runs at import time, so move `sizes()` and `ORIENTATIONS` above `_panels()` if the definition order requires it. In `_panels()`, replace the loop

```python
    for model, (w, h, d, _) in MODELS_FULL.items():
        out.setdefault((w, h), []).append((model, d))
```

with

```python
    for model, (_, _, d, _) in MODELS_FULL.items():
        for size in sizes(model):
            out.setdefault(size, []).append((model, d))
```

In `_house_rules()`, directly after `target, spacing = touch_minimums(self.model or self.size)`, add:

```python
        if target is None:
            out.append(f"page {pg['number']}: no touch minimum for "
                       f"{self.model or '%dx%d' % tuple(self.size)} - name the panel's "
                       f"model so 9mm can be converted (GUI Design Standards p.55)")
```

- [ ] **Step 4: Run the tests to verify they pass, then the whole suite**

Run: `python -m pytest tests/test_spec.py -q -k "1230w or landscape_300m or diagonal_and_a_tier or no_known_minimum"`
Expected: 4 passed.
Run: `python -m pytest -q`
Expected: all pass. If an existing test built a Panel at a size with no model row and now fails on "no touch minimum", give that test's spec a `model` - do not weaken the new message.

- [ ] **Step 5: Docs**

In `docs/design-rules.md` §1, change the row `| 1920 × 720 | TLP Pro 1230WTG — read from a built project, not from the probe |` to `| 1920 × 720 | TLP Pro 1230WTG — 166 DPI, from Extron's TemplateInfoTable.config; the probe reads the base platform class |`, and add after the resolution table:

```markdown
**Tiers** - this toolkit's reading of Extron's per-series templates, not an
Extron rule. By physical diagonal (`gdl.spec.tier`): **A**, 6.5" and up, the
full layout, resized; **B**, 4 to 6.5", a hub page with popups; **C**, under 4",
single-purpose pages. The 520 and 720 are both 800 × 480, at 4.96" and 7.00":
pixels alone cannot place a panel. Soft clients (ECP, the VTLP targets, TLI Pro)
have no tier - their screen is the host's.
```

- [ ] **Step 6: Commit**

```bash
git add gdl/spec.py tests/test_spec.py docs/design-rules.md
git commit -m "fix: the 1230W's real canvas, both 300M orientations, and a panel's tier"
```

### Task 2: How the panel draws points, measured on five models

**Files:**
- Modify: `gdl/spec.py` - `_op_for()`: a button's `flatten` reaches its op
- Modify: `powershell/Apply-GdlPlan.ps1:78-82` - write `flattenTextField` from the op
- Create: `tests/type_probe.py` - writes the probe specs; measures built caption height
- Test: `tests/test_type_probe.py`
- Modify: `docs/gdl-format.md` (the finding), `docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md` §4.1 (the type-floor decision), `docs/gdl-format.md`'s spec vocabulary section for `flatten`

**Interfaces:**
- Consumes: `gdl.compose.load(path) -> (layout_json: dict, assets: dict[int, bytes])`; `gdl.spec.touch_minimums`; `powershell\New-GdlPanel.ps1 -Spec -Donor -Output`.
- Produces: `tests/type_probe.py` functions `cap_height(png: bytes, ink=(255,255,255)) -> int | None`, `probe_spec(model: str, size: tuple[int,int]) -> dict`, `measure(built_gdl: str) -> dict[int, int | None]` (pt → cap-height px); spec button field `"flatten": true`. The finding decides Phase 1's type floor.

Why this shape: `layout.json` exports only `PointSize` (checked on the 1035, 835, 1535, 300M, 1230W and ECP seeds), and a cloned button has `flattenText` off, so the panel draws text live and no built file shows its pixel size. A button with `flattenText` on has Build bake its caption into the artwork - GUI Designer's own rasterization for that project's platform - which is the best evidence available without the physical panels.

- [ ] **Step 1: Write the failing measuring tests**

Create `tests/test_type_probe.py`:

```python
"""The type probe's measuring half, on synthetic artwork."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw  # noqa: E402

import type_probe  # noqa: E402


def _png(rows):
    """A black 40x60 button with white ink on the given (top, bottom) rows."""
    im = Image.new('RGB', (40, 60), (0, 0, 0))
    d = ImageDraw.Draw(im)
    for top, bottom in rows:
        d.rectangle([5, top, 30, bottom], fill=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return buf.getvalue()


class TestCapHeight(unittest.TestCase):
    def test_measures_the_inked_rows(self):
        self.assertEqual(type_probe.cap_height(_png([(20, 39)])), 20)

    def test_no_ink_is_none_not_zero(self):
        """A caption that did not bake must not read as a 0 px measurement."""
        self.assertIsNone(type_probe.cap_height(_png([])))

    def test_antialiased_edges_count_only_when_mostly_ink(self):
        im = Image.new('RGB', (40, 60), (0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rectangle([5, 20, 30, 39], fill=(255, 255, 255))
        d.line([5, 19, 30, 19], fill=(60, 60, 60))      # faint anti-alias row
        buf = io.BytesIO()
        im.save(buf, 'PNG')
        self.assertEqual(type_probe.cap_height(buf.getvalue()), 20)


class TestProbeSpec(unittest.TestCase):
    def test_every_probe_button_meets_the_panels_touch_minimum(self):
        from gdl.spec import Panel, touch_minimums
        for model, size in (('TLP1035T', (1280, 800)), ('TLP300M', (320, 480)),
                            ('TLP1230WTG', (1920, 720))):
            spec = type_probe.probe_spec(model, size)
            self.assertEqual(Panel(spec).check(), [], model)
            target, _ = touch_minimums(model)
            for c in spec['pages'][0]['controls']:
                self.assertGreaterEqual(c['rect'][3], target, model)
                self.assertTrue(c['flatten'])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_type_probe.py -q`
Expected: collection error - `ModuleNotFoundError: No module named 'type_probe'`.

- [ ] **Step 3: Implement `tests/type_probe.py`**

```python
"""How big does a panel draw a point? Bake captions and measure them.

    python tests/type_probe.py specs <out dir>
    python tests/type_probe.py measure <built.gdl> [<built.gdl> ...]

layout.json exports only a font's PointSize and a cloned button draws its
caption live, so no built file says how many pixels a point is. A button with
`flatten` on has Build bake its caption into the artwork with GUI Designer's own
rasterizer for that project's platform: measure the cap height of "HHHH" there,
at each probe size, on each model's seed. docs/gdl-format.md has the result.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.spec import touch_minimums  # noqa: E402

POINTS = (14, 18, 24, 30, 36)   # 14 is the documented body minimum; none below
PAGE = 'Type Probe'
# (seed file, model, canvas) - one per DPI we can build on today.
SEEDS = (('Afterburn 1035.gdl', 'TLP1035T', (1280, 800)),
         ('Afterburn 835 (Project1).gdl', 'TLP835M', (1280, 800)),
         ('Afterburn 1535.gdl', 'TLP1535M', (1920, 1080)),
         ('Afterburn 300M Portrait.gdl', 'TLP300M', (320, 480)),
         ('Afterburn 1230W.gdl', 'TLP1230WTG', (1920, 720)))


def probe_spec(model, size):
    """One page: a black button per point size, captioned HHHH in white, baked."""
    target, gap = touch_minimums(model)
    w = min(300, size[0] - 20)
    h = max(target, 80)
    controls = []
    for i, pt in enumerate(POINTS):
        controls.append({'kind': 'button', 'name': f'P{pt}', 'text': 'HHHH', 'size': pt,
                         'rect': [10, 10 + i * (h + max(gap, 8)), w, h],
                         'fill': '#000000', 'color': '#FFFFFF', 'border': 'none',
                         'align': 'left', 'flatten': True})
    return {'name': f'Type probe {model}', 'model': model, 'size': list(size),
            'theme': {'background': '#000000', 'text': '#FFFFFF',
                      'font': 'Open Sans', 'size': 14},
            'pages': [{'name': PAGE, 'number': 900, 'controls': controls}]}


def cap_height(png, ink=(255, 255, 255)):
    """Rows whose brightest pixel is at least half-way to `ink`, top to bottom;
    None when there are none - a caption that did not bake is not 0 px."""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert('RGB')
    w, h = im.size
    px = im.load()
    half = sum(ink) / 2
    rows = [y for y in range(h) if max(sum(px[x, y]) for x in range(w)) >= half]
    return rows[-1] - rows[0] + 1 if rows else None


def measure(built):
    """{point size: cap height px or None} for the probe page of a built file."""
    from gdl.compose import load
    j, assets = load(built)
    page = next(p for p in j['Pages'] if p['Name'] == PAGE)
    out = {}
    for c in page.get('Controls') or []:
        if c.get('Name', '').startswith('P') and c['Name'][1:].isdigit():
            art = assets.get(c.get('TLPImageID'))
            out[int(c['Name'][1:])] = cap_height(art) if art else None
    return out


def main(argv):
    if len(argv) >= 3 and argv[1] == 'specs':
        os.makedirs(argv[2], exist_ok=True)
        for seed, model, size in SEEDS:
            path = os.path.join(argv[2], f'{model}.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(probe_spec(model, size), fh, indent=1)
            print(f'{path}  <- seeds/{seed}')
        return 0
    if len(argv) >= 3 and argv[1] == 'measure':
        for built in argv[2:]:
            got = measure(built)
            print(os.path.basename(built), ' '.join(
                f'{pt}pt={v}px({v / pt:.3f})' if v else f'{pt}pt=NO INK' for pt, v in sorted(got.items())))
        return 0
    print(__doc__.strip().split('\n\n')[0])
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 4: Run the measuring tests**

Run: `python -m pytest tests/test_type_probe.py -q -k CapHeight`
Expected: 3 passed. (`TestProbeSpec` still fails until Step 6: `flatten` is not yet spec vocabulary, and `Panel(spec).check()` may name it.)

- [ ] **Step 5: Write the failing spec test for `flatten`**

Add to `tests/test_spec.py` (next to the other button-op tests, e.g. after `class TestButtonImages`):

```python
class TestFlatten(unittest.TestCase):
    def test_a_button_can_ask_for_its_caption_baked(self):
        """Only the type probe does: a baked caption is Build's rasterization,
        which is the one way to see how a platform draws a point."""
        p = _spec([{'kind': 'button', 'rect': [0, 0, 100, 100], 'text': 'H', 'flatten': True},
                   {'kind': 'button', 'rect': [0, 200, 100, 100], 'text': 'H'}])
        ops = [o for o in p.plan()['ops'] if o.get('donor_type', '').endswith('PBButton')]
        self.assertEqual([o.get('flatten', False) for o in ops], [True, False])
```

Run: `python -m pytest tests/test_spec.py -q -k flatten` - Expected: FAIL (`[False, False]`). If `p.plan()`'s shape differs (ops under another key), read `Panel.plan` and adjust only the lookup, not the assertion.

- [ ] **Step 6: Implement `flatten` in the spec and applier**

In `gdl/spec.py` `_op_for()`, where the button's op dict is assembled (next to `thumb_image` for sliders), add:

```python
        if c.get('kind') == 'button' and c.get('flatten'):
            # Build bakes the caption into the artwork - GUI Designer's own
            # rasterizer for this platform. Only tests/type_probe.py wants it;
            # everywhere else a baked caption is the flattenText trap.
            op['flatten'] = True
```

If the spec validates button keys against an allow-list, add `'flatten'` to it. In `powershell/Apply-GdlPlan.ps1`, replace line 82

```powershell
        Set-GdlFieldIfPresent $c 'flattenTextField' $false | Out-Null
```

with

```powershell
        Set-GdlFieldIfPresent $c 'flattenTextField' ([bool]$op.flatten) | Out-Null
```

keeping the comment above it and adding one line to it: `# Only the type probe (tests/type_probe.py) asks for $true.`

Run: `python -m pytest tests/test_spec.py tests/test_type_probe.py -q`
Expected: all pass.

- [ ] **Step 7: Build the probes**

```bash
python tests/type_probe.py specs "$CLAUDE_JOB_DIR/tmp/typeprobe"
```

Then for each of the five (PowerShell, one at a time - an open GUI Designer blocks the next run):

```powershell
powershell\New-GdlPanel.ps1 -Spec "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP1035T.json" -Donor "seeds\Afterburn 1035.gdl" -Output "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP1035T.gdl"
powershell\New-GdlPanel.ps1 -Spec "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP835M.json" -Donor "seeds\Afterburn 835 (Project1).gdl" -Output "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP835M.gdl"
powershell\New-GdlPanel.ps1 -Spec "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP1535M.json" -Donor "seeds\Afterburn 1535.gdl" -Output "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP1535M.gdl"
powershell\New-GdlPanel.ps1 -Spec "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP300M.json" -Donor "seeds\Afterburn 300M Portrait.gdl" -Output "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP300M.gdl"
powershell\New-GdlPanel.ps1 -Spec "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP1230WTG.json" -Donor "seeds\Afterburn 1230W.gdl" -Output "$env:CLAUDE_JOB_DIR\tmp\typeprobe\TLP1230WTG.gdl"
```

Expected: each exits 0. `verify_built.py` may flag the baked caption as a caption mismatch - that is the probe working; read it, do not suppress it. If the before-first-build preference modal appears, follow CLAUDE.md *Driving GUI Designer*.

- [ ] **Step 8: Measure**

```bash
python tests/type_probe.py measure "$CLAUDE_JOB_DIR"/tmp/typeprobe/*.gdl
```

Expected: a line per model with `pt=px(ratio)`. **If every button reads `NO INK`**, `flattenText` is per state: set `flattenTextField` on each state in the applier's state loop too, rebuild, re-measure. **Read the result:** ratios equal across all five models (within 1 px) → GUI Designer draws a point at a fixed pixel size whatever the DPI, so physical text shrinks on dense panels and Phase 1 needs a per-model floor; ratios proportional to DPI → points are physical and 14 pt is enough everywhere.

- [ ] **Step 9: Record it**

In `docs/gdl-format.md`, add a subsection under the section that covers what Build does (next to the `flattenText` notes): the five models, their DPI, the measured cap height per point size, the ratio, and the one-sentence conclusion, with how it was measured (`tests/type_probe.py`) and its limit (Build's rasterizer, not the panel firmware). In the spec's §4.1 "Type stays in points" bullet, replace "if Phase 0 shows ... on top for dense panels" with the decision the numbers support. Add `flatten` to the spec vocabulary wherever `docs/gdl-format.md` or `SKILL.md` lists button fields, marked "type probe only".

- [ ] **Step 10: Commit**

```bash
git add gdl/spec.py powershell/Apply-GdlPlan.ps1 tests/type_probe.py tests/test_type_probe.py tests/test_spec.py docs/gdl-format.md docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md SKILL.md
git commit -m "test: measure how GUI Designer draws a point on five panel models"
```

### Task 3: How Claude Design previews a resized Page

**Files:**
- No repo code. Scratch: `$CLAUDE_JOB_DIR/tmp/preview-check/`
- Modify: `docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md` §4.2 *Preview* (the decision)

**Interfaces:**
- Consumes: the published *Extron Afterburn* design system (`https://claude.ai/artifact/1nZsxvdm7HsXpfoSXBVjvx`); `tests/data/design-huddle/` (canvas.json, Home.dc.html); `Page`'s existing `width`/`height` props (`gdl/designsys/bundle.js` Page).
- Produces: a written decision - **live** (Phase 1 builds `preview` into Page) or **sign-off only** (Phase 1 shows derived layouts only in `gdl.design compare`).

- [ ] **Step 1: Make the scratch canvas**

Copy `tests/data/design-huddle/` to `$CLAUDE_JOB_DIR/tmp/preview-check/project/`. Copy `Home.dc.html` twice, to `Home725.dc.html` and `Home725b.dc.html`. In both copies, add `width="1024" height="600"` to the root `Page` element's attributes. In `canvas.json`, add two boards that mirror Home's entry: `Home725` at Home's own size (1280 × 800) and `Home725b` at 1024 × 600 (w/h fields as Home's entry spells them).

- [ ] **Step 2: Publish it as a new, private Design artifact**

`Artifact` `action: "quickstart"`, `intent: "design"` → the Design type's `type_url`. Publish with that `type_url`, `title: "Preview check"`, `auto_open: "after_first_write"`, then publish the scratch `project/` files to the returned `url` (`root` = the scratch folder, `file_path` = `project/canvas.json`, `files` = every file under `project/`). Pin it to the design system the way the huddle canvas is (its `canvas.json` already names the system version).

- [ ] **Step 3: Look at it**

Load the Chrome tools in one call (`ToolSearch` `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page`), open the artifact in a new tab, and screenshot: the canvas overview; `Home725` (a 1024 × 600 Page on a 1280 × 800 board); `Home725b` (both 1024 × 600); and each in Play. If the browser tools cannot reach claude.ai, stop and ask the owner to open the link and describe the three boards - `needs input`.

- [ ] **Step 4: Decide and record**

- `Home725` shows a correctly laid-out 1024 × 600 page (whatever margin) → **live**: Page's `preview` sets the Page's own width and height from the panel, board size untouched.
- Only `Home725b` looks right → **live, per board**: the preview needs the board resized too; record that the designer (or Claude Code) sets the board size when previewing, and that the translator ignores board size.
- Neither → **sign-off only**.

Write the decision and the evidence (which board did what) into the spec's §4.2 *Preview* paragraph, replacing "Phase 0 checks Claude Design shows that; if it cannot, ...". Delete the scratch artifact only if the owner agrees.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-09-24-panel-aware-design-systems-design.md
git commit -m "docs: how Claude Design previews a page at another panel's size"
```

### Task 4: `New-GdlSeed.ps1`, and seeds for the 725, 525 and 320

**Files:**
- Create: `powershell/New-GdlSeed.ps1`
- Create: `tests/verify_seed.py`
- Test: `tests/test_verify_seed.py`
- Create (LFS): `seeds/Afterburn 725.gdl`, `seeds/Afterburn 525.gdl`, `seeds/Afterburn 320.gdl`
- Modify: `seeds/README.md` (table rows, *Gaps*, how seeds are made), `docs/from-scratch.md` §5c/§7 (the script; delete line 564's "cannot be driven at all"), `README.md` *What is here* if it lists the PowerShell scripts, `CLAUDE.md` *Environment* table (`New-GdlSeed.ps1` needs GUI Designer)

**Interfaces:**
- Consumes: `gdl.project.Project` (`instances()`, `field()`, `pages()`, `controls()`); `gdl.spec.MODELS`, `gdl.spec.part_number`, `gdl.spec.sizes`; `powershell\Invoke-GdlMenu.ps1`; the launch code in `powershell\New-GdlPanel.ps1`.
- Produces: `powershell\New-GdlSeed.ps1 -PanelType <wizard name> -Model <MODELS key> -Theme <wizard name> [-Application <name>] -Output <seed.gdl> [-List]`; `tests/verify_seed.py <seed.gdl> <model>` (exit 0/1) with `check_seed(path, model) -> list[str]` problems. Phase 1's translator prints the `New-GdlSeed.ps1` command for a panel with no seed.

- [ ] **Step 1: Write the failing verifier tests**

Create `tests/test_verify_seed.py`:

```python
"""A seed is a themed project for the model it claims - never a Blank one."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import verify_seed  # noqa: E402

SEEDS = os.path.join(os.path.dirname(HERE), 'seeds')


def _seed(name):
    path = os.path.join(SEEDS, name)
    if not os.path.exists(path) or os.path.getsize(path) < 1024:
        raise unittest.SkipTest(f'{name} is not pulled from Git LFS here')
    return path


class TestVerifySeed(unittest.TestCase):
    def test_a_real_seed_passes(self):
        self.assertEqual(verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP1035T'), [])

    def test_the_wrong_model_is_refused(self):
        probs = verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP725T')
        self.assertTrue(any('part number' in p for p in probs), probs)

    def test_a_blank_project_is_refused(self):
        """What the wizard makes when Blank is still the selected radio: one page
        and a handful of controls, and it reads as a seed by every other test."""
        probs = verify_seed.check_seed(_seed('Afterburn 1035.gdl'), 'TLP1035T',
                                       min_pages=99)
        self.assertTrue(any('Blank' in p for p in probs), probs)


if __name__ == '__main__':
    unittest.main()
```

Run: `python -m pytest tests/test_verify_seed.py -q` - Expected: collection error, `No module named 'verify_seed'`.

- [ ] **Step 2: Implement `tests/verify_seed.py`**

```python
"""Is this file a seed for this model? Run on every seed New-GdlSeed.ps1 makes.

    python tests/verify_seed.py <seed.gdl> <model>

The Project Create Wizard can make a Blank project while reading "Theme: X"
(docs/from-scratch.md section 5c), and a seed for the wrong model builds the
wrong panel with every other gate green - the built panel is the seed's model.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdl.project import Project  # noqa: E402
from gdl.spec import MODELS, part_number, sizes  # noqa: E402

# A themed project has 2-13 pages and 170-880 controls; a Blank one 1 page and 3.
MIN_PAGES = 2
MIN_CONTROLS = 100


def check_seed(path, model, min_pages=MIN_PAGES, min_controls=MIN_CONTROLS):
    if model not in MODELS:
        return [f'{model!r} is not a panel GUI Designer builds for']
    p = Project.open(path)
    probs = []
    proj = next(p.instances('PBProject'), None)
    if proj is None:
        return [f'{path} has no PBProject - a template, not a project']
    plat = p.field(proj, 'platformField')
    got = p.field(plat, 'partNumberField') if plat is not None else None
    if got != part_number(model):
        probs.append(f'part number {got!r}, but {model} is {part_number(model)!r}')
    pages = list(p.pages())
    n_pages = sum(1 for pg in pages if pg['kind'] == 'page')
    n_controls = sum(len(pg['controls']) for pg in pages)
    if n_pages < min_pages or n_controls < min_controls:
        probs.append(f'{n_pages} page(s), {n_controls} controls - a Blank project, not a '
                     f'themed seed (a themed one has {min_pages}+ pages, {min_controls}+ controls)')
    canvas = max(((c['rect'][2], c['rect'][3]) for pg in pages if pg['kind'] == 'page'
                  for c in pg['controls'] if None not in c['rect'][2:]),
                 key=lambda s: s[0] * s[1], default=None)
    if canvas and canvas not in sizes(model) and not any(
            canvas[0] <= w and canvas[1] <= h for w, h in sizes(model)):
        probs.append(f'largest control {canvas[0]}x{canvas[1]} does not fit a {model} '
                     f'({" or ".join("%dx%d" % s for s in sizes(model))})')
    return probs


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().split('\n\n')[0])
        return 2
    probs = check_seed(argv[1], argv[2])
    for pr in probs:
        print('  PROBLEM ' + pr)
    print(f"{'ok' if not probs else f'{len(probs)} problem(s)'}: {argv[1]} as {argv[2]}")
    return 1 if probs else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
```

If `Project.open` is spelled differently (read `gdl/project.py`), use the real constructor. If `partNumberField` is not directly on the platform object, print `p.kind(plat)` and its field names once and follow them - the Turbulence research read it from "each platform object's own partNumberField".

Run: `python -m pytest tests/test_verify_seed.py -q` - Expected: 3 passed (or 3 skipped where the seed is an LFS pointer - then `git lfs pull --include "seeds/Afterburn 1035.gdl"` and re-run; skips are not a pass).

- [ ] **Step 3: Write `powershell/New-GdlSeed.ps1`**

Structure (follow `New-GdlPanel.ps1` for launching GUI Designer and `Invoke-GdlMenu.ps1` for UIA; every UIA idiom below is the one that made the six ECP seeds, `docs/from-scratch.md` §5c):

```powershell
<#
    A seed, made by GUI Designer's Project Create Wizard with nobody at the mouse.

        powershell\New-GdlSeed.ps1 -PanelType 'TLP Pro 725T' -Model TLP725T `
            -Theme 'Afterburn' -Output 'seeds\Afterburn 725.gdl'
        powershell\New-GdlSeed.ps1 -List      # what Panel Type offers

    Only a real click commits a combo: ValuePattern.SetValue and
    SelectionItemPattern.Select both leave the wizard reading right and
    internally unselected (docs/from-scratch.md section 5c). The Theme radio is
    clicked and the result checked, because the wizard builds Blank while
    reading "Theme: X" otherwise. The saved file is then refused by
    tests/verify_seed.py unless it is a themed project for -Model.
#>
param(
    [string]$PanelType,
    [string]$Model,
    [string]$Theme,
    [string]$Application,
    [string]$Output,
    [switch]$List,
    [string]$Python = 'python',
    [string]$InstallDir = 'C:\Program Files (x86)\Extron\GUI Designer'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$CT = [System.Windows.Automation.ControlType]
$True_ = [System.Windows.Automation.Condition]::TrueCondition
```

Then, as functions, each lifted from the scratch scripts that drove the ECP seeds (`$CLAUDE_JOB_DIR/tmp/wizpick.ps1`, `wizexpand.ps1`, `wizstate.ps1`, `focusclick.ps1`):

1. `Get-Wizard` - the descendant named `Project Create Wizard` of a window owned by a `GUI Designer` process (from `wizpick.ps1`).
2. `Get-Combo $name` - the wizard's `ComboBox` named `Panel Type:`, `Theme:` or `Application:`.
3. `Get-Items $combo` - expand it (`ExpandCollapsePattern.Expand()`, wait 1.5 s), return every `ListItem` (name, centre point) in the GUI Designer windows other than the wizard itself (the dropdown is its own window).
4. `Invoke-Click $x $y` - raise the wizard (`ShowWindow`/`BringWindowToTop`/`SetForegroundWindow`), confirm `WindowFromPoint` is a GUI Designer window, then click (from `focusclick.ps1`). Refuse, rather than click, if the window under the point is not GUI Designer's.
5. `Select-ComboItem $name $item` - `Get-Items`; if `$item` is absent, print every item offered, collapse the combo, click Cancel, close GUI Designer with **File > Exit**, and `exit 3`; else `Invoke-Click` its centre; wait 2 s; read the combo's `ValuePattern.Current.Value` and `exit 4` unless it equals `$item`.
6. Launch GUI Designer as `New-GdlPanel.ps1` does, open the wizard with `Invoke-GdlMenu.ps1` on **File > New Project...** (catch the `0x80131505` timeout: the modal opened), and wait up to 30 s for `Get-Wizard`.
7. `-List`: print `Get-Items (Get-Combo 'Panel Type:')`, collapse, click Cancel, close GUI Designer, `exit 0`.
8. Otherwise: `Select-ComboItem 'Panel Type:' $PanelType`; find the element named `Theme` (a `Pane`, `wizstate.ps1`), `Invoke-Click` its centre; `Select-ComboItem 'Theme:' $Theme`; if `$Application`, `Select-ComboItem 'Application:' $Application`; save a screenshot to `$env:CLAUDE_JOB_DIR\tmp\seed-wizard.png` (the only record of the radio - it exposes no state); click `Create` by position (it exposes no patterns); wait for the main window title to show a project (`Get-Process` + `.Refresh()` - `MainWindowTitle` is cached, `docs/from-scratch.md` §7).
9. **File > Save As...** via `Invoke-GdlMenu.ps1`; in the standard Save dialog set the `Edit` named `File name:` with `ValuePattern.SetValue` (a Win32 common dialog, not the wizard - SetValue is safe there) to the absolute `$Output`, and `Invoke` the `Save` button; wait for the file; close GUI Designer with **File > Exit**.
10. `& $Python tests\verify_seed.py $Output $Model`; if it fails, delete `$Output` and exit with its code - a wrong seed must not stay where the next run finds it.

- [ ] **Step 4: Dry-run the listing**

Run (PowerShell): `powershell\New-GdlSeed.ps1 -List`
Expected: 56 lines - `Select Your Panel` and the 55 models. Note the exact names for the TLP Pro 725T, 525T and 320M, then run the wizard once by hand to read the Theme and Application names offered for each (or add a `-ListThemes` pass that selects the panel and lists `Theme:`'s items - do this if the names are not obvious).

Then pin Review Focus 5 - a name the wizard does not offer:

Run: `powershell\New-GdlSeed.ps1 -PanelType 'TLP Pro 9999' -Model TLP725T -Theme 'Afterburn' -Output "$env:CLAUDE_JOB_DIR\tmp\nope.gdl"; $LASTEXITCODE`
Expected: the 56 offered names printed, exit code `3`, no `nope.gdl`, no click on any list item, and GUI Designer closed (or the wizard cancelled) so the next run starts clean.

- [ ] **Step 5: Make the three seeds**

```powershell
powershell\New-GdlSeed.ps1 -PanelType '<725T name from Step 4>' -Model TLP725T -Theme '<Afterburn theme name>' -Output "$PWD\seeds\Afterburn 725.gdl"
powershell\New-GdlSeed.ps1 -PanelType '<525T name>' -Model TLP525T -Theme '<Afterburn theme name>' -Output "$PWD\seeds\Afterburn 525.gdl"
powershell\New-GdlSeed.ps1 -PanelType '<320M name>' -Model TLP320M -Theme '<Afterburn theme name>' -Output "$PWD\seeds\Afterburn 320.gdl"
```

Expected: each ends `ok: ... as TLP...`. Open `$env:CLAUDE_JOB_DIR\tmp\seed-wizard.png` after each and confirm the Theme radio was selected.

- [ ] **Step 6: Confirm LFS tracks them, and describe them**

Run: `git check-attr filter -- "seeds/Afterburn 725.gdl"` - Expected: `filter: lfs`. Add a row per seed to `seeds/README.md`'s table in the existing format (project name, model(s), part, canvas, pages, popups, controls, borders, declared fonts - read with `gdl.project`, as the existing rows were), remove 1024 × 600, 800 × 480 and 320 × 240 from *Gaps* for Afterburn, and say seeds are now made with `New-GdlSeed.ps1`. In `docs/from-scratch.md` §5c *Automating the wizard*, name the script as the way to do it; delete §7's bullet "The Project Create Wizard cannot be driven at all — see §5c." Add `New-GdlSeed.ps1` to CLAUDE.md's *Environment* "Needs GUI Designer installed" column, and to `README.md` *What is here* if that lists scripts.

- [ ] **Step 7: Commit**

```bash
git add powershell/New-GdlSeed.ps1 tests/verify_seed.py tests/test_verify_seed.py "seeds/Afterburn 725.gdl" "seeds/Afterburn 525.gdl" "seeds/Afterburn 320.gdl" seeds/README.md docs/from-scratch.md CLAUDE.md README.md
git commit -m "feat: make a seed for any panel through the Project Create Wizard"
```

### Task 5: Phase 0 review and PR

- [ ] **Step 1:** `python -m pytest -q` - all pass; note the count of skips and that none is a new test skipping for a missing seed.
- [ ] **Step 2:** Run an adversarial review over `git diff origin/main...HEAD` (Workflow: finders per dimension - correctness, silent failure, docs drift - then skeptics per finding). Fix what survives, with tests.
- [ ] **Step 3:** Push `feat/panel-aware` and open a draft PR "Phase 0: settle the unknowns for panel-aware design systems", its body the type-probe numbers, the preview decision and the three new seeds. Update the spec's §5 with anything Phase 0 changed.

---

## Phase 1 - Afterburn, panel-aware (task level; full plan written when Phase 0 lands)

Each task below lists what it produces and the tests that prove it; the full step-by-step plan is written against Phase 0's answers.

### Task 6: Series templates, indexed
- **Create** `gdl/templates.py`: read `TemplateInfoTable.config` (NRBF, `gdl/nrbf.py`) from the install or `vendor/`; `series(theme) -> [{file, series, res, dpi}]`; `template_for(theme, model) -> path | None` by (resolution, DPI) then resolution. **Tests:** Afterburn 1230 → 1920×720/166; TLP725T → `Afterburn 1020 Series.glt`; TLP525T → `Afterburn 520 Series.glt`; no install → `[]` with a clear skip.

### Task 7: The profile's per-panel table
- **Modify** `gdl/designsys/afterburn.json`: a `panels` block keyed by series - layout regions (main area; tier B content region and rail), background file per resolution (`Backgrounds/<5x canvas>/`), source-row cap - each measured off that series' template with `_source`. **Modify** `gdl/designsys/__init__.py`: `models(p) -> {model: {size, dpi, tier, touch, gap, type_floor, layout, background}}` from `gdl.spec` + the profile; `backdrops()` per resolution; tokens describe the design panel only. **Tests:** every tier-A/B/C model resolves; touch/gap equal `touch_minimums`; the 1230W and 725 get their own backgrounds; token grammar still passes.

### Task 8: Millimetre components and the Page's panels
- **Modify** `gdl/designsys/bundle.js`: the Page's context carries the resolved panel (`panels`, the design panel, `preview` per Task 3's decision); Button/Slider/Level minimums, MainArea and backdrop read it. **Tests** (Chrome): a Button on a TLP835M page is ≥ 67 px; on a TLP1220MG page ≥ 44 px; MainArea sits in the series' own region.

### Task 9: `Group`, reflow and tier pagination
- **Modify** `gdl/designsys/bundle.js`, `gdl/designsys/__init__.py` (component docs, README text): `Group` - wrap grid, cap per row; tier A pages in place (popup group in its region, Previous/Next); tier B hub (rail + content region, a popup per group, split popups with Previous/Next); tier C pages with Back. Derived structure carried in `data-gdl`. **Tests** (Chrome, synthetic canvas): 8 sources on a 1035 fit; on a 725 page in place; on a 525 become a hub popup; on a 320 become pages; a page that cannot fit even so is refused, naming the control.

### Task 10: Translation per panel
- **Modify** `gdl/design.py`: lay each artboard out once per panel (viewport + mm scale), read derived popups/pages, write `out/<model>/spec.json`; all-or-nothing across panels; seed per panel from `seeds/` by theme + model, refusing with the `New-GdlSeed.ps1` command. **Tests:** two-panel canvas → two specs with the same control names; one panel refused → nothing written, both panels' problems named.

### Task 11: Shared IDs and one ID map across panels
- **Modify** `gdl/spec.py` (IDs pinned from the canvas control, not per spec), `gdl/idmap.py` (a column per panel: page, popup or modal), `tests/verify_idmap.py` (every built panel). **Tests:** the same control has the same ID in every panel's spec; derived navigation carries no ID; the map lists each control's location per panel.

### Task 12: Checks per panel
- **Modify** `gdl/spec.py` `_house_rules()`: 2 mm spacing except within one segmented control (a `joined` marker the Group/segmented component emits); the Phase 0 type floor; a modal is full screen. **Tests:** two touching segments pass; two touching separate buttons fail; a 14 pt caption on a TLP535M fails if Task 2 found points pixel-fixed.

### Task 13: Build every panel, sign off every panel
- **Create** `powershell/New-GdlPanels.ps1` (each `out/<model>/spec.json` through `New-GdlPanel.ps1`, then `verify_idmap.py` per panel). **Modify** `gdl/design.py` `compare`: a section per panel, derived popups in their regions, modals over the start page. **Tests:** compare's index has a section per panel (no GUI Designer needed, fed built fixtures).

### Task 14: Proof, docs, review, PR
- The huddle canvas with `panels="TLP1035T TLP725T TLP525T TLP320M"` translated, built on all four seeds, every panel verified (layout, ID map), compared; results in `docs/claude-design.md` §6. Docs moved from the spec into their homes (`docs/claude-design.md` §1-4, `docs/design-rules.md`, `docs/idmap.md`, `docs/gdl-format.md`); the design system and the huddle canvas republished. Adversarial review; PR.

---

## Phases 2-4 - outlines, re-planned when reached

**Phase 2 - Mach.** Register in `TEMPLATES`; slider track 15 px from `15x182_empty.png` / `182x15_empty.png` (profile and `docs/design-rules.md` §7 together); themes from `Backgrounds/5472x3648/`; the per-panel table from Mach's series templates; every `tests/test_designsys.py` class parameterised over all templates; commit the counting script or re-derive the `_source` counts; built and verified on two panels (1035 and one of 725/525).

**Phase 3 - Shockwave.** Add `examples`; `defaults.slider`/`level` in the shared shape (`thumb` a size, `thumb_color`, `orientation`, `track`); decide on a parser for its status-color kit (`1248x440_blue_nsel.png`) or none; backgrounds for its four resolutions; per-panel table; two panels.

**Phase 4 - Turbulence.** Extract its images from the `.glt` files (`PBImageResource`); seeds via `New-GdlSeed.ps1`; re-derive the 2D Rectangle border claim (12 references on an object type the reader does not walk); per-panel table; two panels.
