---
name: extron-panel
description: Use when creating, modifying or reviewing an Extron GUI Designer touch-panel (.gdl/.glt) — designing a panel from a description, editing an existing client panel, checking a design against Extron's standards, or previewing what a panel will look like without Windows.
---

# Building Extron touch panels

This repo can read, render, check and generate Extron `.gdl` panels. The whole
loop is proven against GUI Designer 1.27.0.9: a JSON spec became a page that GUI
Designer opened and built with 0 errors.

Read `docs/design-rules.md` before making design decisions and
`docs/gdl-format.md` before touching the format. Both encode findings that were
expensive to get.

## The one thing to internalise

**Build owns the artwork.** You never make pixels. You set semantic properties —
a fill colour, a stroke, a *named* border resource, a font, a caption — and GUI
Designer rasterises them on build. A control you author carries `TLPImageID = -1`
until then.

This is why a preview is possible at all, and why "the file looks right" is not
the same as "the panel looks right" (see the `flattenText` trap below).

## Two workflows

### A. Generate a panel from a description

1. **Pick the panel model first**, and put it in the spec as `"model"`.
   `gdl/spec.py`'s `MODELS_FULL` has all 55 GUI Designer builds for, with each
   one's resolution, DPI and Extron part number, read from the assemblies. The
   canvas is one of eight resolutions, not a constant - and **DPI varies by
   nearly 2x within a resolution**, so naming the model is what makes the
   touch-target check right rather than merely safe. Ask if you don't know it.
2. **Pick the theme.** `gdl.themes.AFTERBURN` is the documented token set. For
   Mach/Shockwave/Turbulence, or a client's house style, run
   `python -m gdl.themes <template.glt>` and read the tokens off the template.
3. **Write the spec** — see `examples/panel.json`. Use `grid`/`stack` for layout;
   never hand-type a rect. Nest them for sub-regions (a nested directive lays out
   inside its parent cell, and a `rect` at that depth is an offset into it).
4. **Check it**: `python -m gdl.spec check <spec.json>` — ids, off-canvas, sizes,
   unknown resources, and Extron's numeric standards (touch target, spacing,
   ≤9 buttons per group, ≤6 colours, ≥14pt body text).
5. **Preview it**: `python -m gdl.spec render <spec.json> out/preview.png`, then
   **look at the image**. The compositor scores 2.19% against GUI Designer's own
   output, so this is a real preview, not a sketch. Iterate here — it costs
   nothing and needs no Windows.
6. **Check it against the donor**: `python -m gdl.spec donors <spec.json>
   <donor.gdl>`. The donor supplies every cloned control, so a type it lacks is
   unauthorable — and its page/popup names are taken, which is a build error.
   Both are free to find here and cost a Windows round trip to find there.
7. **Emit the plan**: `python -m gdl.spec plan <spec.json> out/plan.json`.
8. **Apply and build** — needs Windows, see below.
9. **Verify the build**: `python tests/verify_built.py out/plan.json
   <built.gdl>`. Do not skip this because the build was clean; that is exactly
   when it earns its keep.

### B. Modify an existing panel

There is a vocabulary for this - write the change as JSON, resolve it against
the real project on the Mac, then apply:

1. **Describe the change** - see `examples/edits.json`. Four ops:
   `rename` (captions), `retarget` (another panel model, optionally rescaling),
   `renumber` (addressable `userId`s), `restyle` (colour remap). Selectors are
   ANDed and support exact or regex match on name and caption.
2. **Check it**: `python -m gdl.edit check <edits.json> <panel.gdl>`. Every
   selector resolves against the real file, so "matched nothing" is an error
   here rather than a silent no-op on Windows. Errors block; warnings do not.
3. **Emit the plan**: `python -m gdl.edit plan <edits.json> <panel.gdl>
   out/edits-plan.json`.
4. **Apply**: `powershell\Apply-GdlEdits.ps1 <ProjectGCP> <plan> <out>`.
5. **Build, then verify**: `python tests/verify_built.py out/edits-plan.json
   <built.gdl>`.

Two things about renaming that are not obvious:

- A caption usually is **not** in the control's `textField`. It is on the first
  state, or it is *formatted* text (`ftextField`) with hand-placed tabs and line
  breaks. `gdl.edit` writes it back wherever it found it.
- A **formatted** caption is baked into the artwork. Making one longer wraps it
  onto an unindented second line over the icon - `check` warns, and the only
  real verification is looking at the rasterised asset.

Reading and rendering need nothing but Python and Pillow:

```bash
python -m gdl.project <file.gdl>      # resources, fills, borders
python -m gdl.themes  <file.gdl>      # the palette it actually uses
python tests/score.py record <file.gdl> <snapshots> -o before.json
```

Writing goes through `powershell/GdlProject.ps1` on Windows. **Clone, never
construct** — every constructor and property setter throws headless, and a failed
setter writes the backing field *before* throwing, so it looks like it worked.

## Running Windows from macOS

Fully scriptable against the Parallels VM; `docs/from-scratch.md` §7 has detail.

```bash
# authoring - runs as SYSTEM, no desktop, fine for anything headless
prlctl exec "Windows 11" 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe' \
    -NoProfile -ExecutionPolicy Bypass -File '\\Mac\Home\...\script.ps1'

# anything that draws - MUST have --current-user or it dies on the first dialog
prlctl exec "Windows 11" --current-user ... -File '...\out\sendkeys.ps1' -Keys '^+b'
prlctl capture "Windows 11" --file /tmp/vm.png     # read the screen back
```

- The host is at `\\Mac\Home\...` in the guest. The `Z:` mapping is
  per-interactive-session and **invisible** to `prlctl exec`.
- **`Project > Verify` (Ctrl+B) is not a build.** It says "Build Complete - 0
  errors" and emits no payload; saving after it drops the payload entirely. The
  real build is **File > Save and Build (Ctrl+Shift+B)**.
- `BuildProject()` is not callable headlessly — it needs state only a running GUI
  Designer has. Drive the UI.

## Traps that have already cost time

- **`flattenText` bakes captions into the artwork.** A cloned button inherits it,
  so Build deduplicates every generated button to one asset carrying the donor's
  word — while `layout.json` holds the correct captions. The model reads
  perfectly and the panel is wrong. Set `flattenTextField = false`.
- **A clone inherits what you didn't ask for.** Page-level artwork, button icons,
  ids. Clear `<TLPImageID>` on a cloned page and `buttonImageField` on a cloned
  button unless you want the donor's.
- **Buttons render from their STATE, not the control.** Set text/colour on every
  state or the caption won't appear.
- **"Field is null" is not "field is missing."** Most colour and image fields are
  null on most controls; clone a donor value from elsewhere in the project.
- **Popup bindings live in four places** and every mismatch fails *silently* —
  the file opens and builds, the binding just reads "Unassigned". Use
  `Register-GdlPopupGroup` and assert with `Test-GdlPopupBinding`. Don't
  hand-author popups any other way.
- **Page and popup names must be unique project-wide** — one namespace for
  both. Build refuses with "Duplicate page or popup page names are not allowed
  within the same project." Your spec joins a *donor* project, so a name that is
  unique in the spec can still collide; `python -m gdl.spec donors <spec>
  <donor.gdl>` is the check.
- **A control that doesn't fit its page is moved to 0,0 by Build**, silently,
  and the build still says 0 errors. Cloned popups keep the *donor's* size, so
  a popup whose controls run wider than the donor's width loses them to the
  origin. Author the popup's size; then run `tests/verify_built.py`.
- **`Save-GdlProject` resets every `TLPImageID` to -1**, so a bridge-saved file
  always needs rebuilding. Harmless, but it means byte comparison against the
  original is meaningless — compare pass1 vs pass2.
- `Save-GdlProject` prints a bare `0x80070002` on every save. Not an error.

## Icons: two routes, both work

- **Images** — the normal route, and what real panels use. Extron's kits ship
  1,316 (Afterburn), 596 (Mach), 1,124 (Shockwave), 1,408 (Turbulence) assets.
  Appending a new `PBImageResource` and binding it to `buttonImageField` is
  proven to build. Set `buttonImageLayout`/alignment or a large icon will fill
  the button.
- **Icon fonts** — for single-colour icons, faster and needs no resource.
  Afterburn 136 glyphs at U+E900–E98C, Mach (Extron-Lift) 121 at U+E900–E978.
  Place them as text in that face.

## Verification gates — do not skip

- **Render change**: `tests/score.py record` before and after, then `diff`. It
  exits non-zero on any page regressing. A change that improves one page and
  regresses twenty is the documented failure mode here.
- **Spec change**: `python tests/test_spec.py` (50 tests).
- **Anything authored**: two gates, not one.
  1. GUI Designer must **open and build** it — a file that merely serialises
     proves nothing.
  2. `python tests/verify_built.py <plan.json> <built.gdl>` — because a build
     that reports 0 errors still relocates controls and bakes captions. Both of
     this repo's worst authoring bugs built perfectly clean.
- Report numbers you actually ran. Never state a build succeeded on the strength
  of "no error dialog appeared" — say what you checked (payload member present,
  N controls rasterised, verifier clean).

## Where the design authority lives

`docs/design-rules.md` separates three things and you must keep them separate:
what Extron **documents**, what the Liberty Bank fixture happens to **do**, and
what we **extrapolated**. Never quote an extrapolated number to a client as an
Extron requirement — the touch-target formula in particular reproduces Extron's
published table but is our derivation, not their stated rule.
