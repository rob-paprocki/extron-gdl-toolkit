---
name: extron-panel
description: Use when creating, modifying or reviewing an Extron GUI Designer touch-panel (.gdl/.glt) — designing a panel from a description, editing an existing client panel, checking a design against Extron's standards, or previewing what a panel will look like without Windows.
---

# Building Extron touch panels

This repo can read, render, check and generate Extron `.gdl` panels. The whole
loop is proven against GUI Designer 1.27.0.9, and on a Windows box it runs
unattended end to end — `powershell\New-GdlPanel.ps1` takes a JSON spec and
returns a built, verified panel without anyone opening GUI Designer.

So the job here is usually to turn a description into a good spec. The build is
mechanical; the design is not.

Read `docs/design-rules.md` before making design decisions and
`docs/gdl-format.md` before touching the format. Both encode findings that were
expensive to get.

## The one thing to internalise

**Build owns the artwork.** You never make pixels. You set semantic properties —
a fill color, a stroke, a *named* border resource, a font, a caption — and GUI
Designer rasterizes them on build. A control you author carries `TLPImageID = -1`
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
3. **Write the spec** — see `examples/panel.json` for the full vocabulary and
   `examples/huddle.json` for a small one written straight from a prose brief.
   Use `grid`/`stack` for layout;
   never hand-type a rect. Nest them for sub-regions (a nested directive lays out
   inside its parent cell, and a `rect` at that depth is an offset into it).
4. **Check it**: `python -m gdl.spec check <spec.json>` — ids, off-canvas, sizes,
   unknown resources, and Extron's numeric standards (touch target, spacing,
   ≤9 buttons per group, ≤6 colors, ≥14pt body text).
5. **Preview it**: `python -m gdl.spec render <spec.json> out/preview.png`, then
   **look at the image**. The compositor scores 2.19% against GUI Designer's own
   output, so this is a real preview, not a sketch. Iterate here — it costs
   nothing and needs no Windows.
6. **Check it against the donor**: `python -m gdl.spec donors <spec.json>
   <donor.gdl>`. The donor supplies every cloned control, so a type it lacks is
   unauthorable — and its page/popup names are taken, which is a build error.
   Both are free to find here and cost a Windows round trip to find there.

   **Pick the donor deliberately — it ships in the result.** The fixtures are a
   real client's project, so a panel cloned from one carries their page names,
   popups, artwork and retail fonts. For anything going to a client, use a
   *seed*: a blank themed project from **File > New Project...**, saved once per
   theme and retargeted to other models. Extron's `.glt` templates cannot be
   donors — they have no `PBProject`, and a file built from one makes GUI
   Designer open empty and offer the Create Wizard. `donors` refuses them with
   that explanation. See `docs/from-scratch.md` §5c.
7. **Build it.** On the Windows box this is one command, which re-runs steps 4
   and 6 and finishes with step 8:

   ```powershell
   powershell\New-GdlPanel.ps1 -Spec examples\panel.json `
       -Donor fixtures\gdl\Interface__alt_....gdl -Output C:\gdlwork\Boardroom.gdl
   ```

   check → donors → plan → apply → pack → open → Save and Build → wait →
   verify. It exits 0 only if the verifier passed, so it gates rather than
   reports. Nobody touches GUI Designer. Add `-KeepOpen` to leave it up.

   Off Windows, run the steps by hand — `python -m gdl.spec plan <spec.json>
   out/plan.json`, then the Windows half per `docs/from-scratch.md` §7.
8. **Verify the build** (already done for you by `New-GdlPanel.ps1`):
   `python tests/verify_built.py out/plan.json <built.gdl>`. Do not skip this
   because the build was clean; that is exactly when it earns its keep. It
   checks geometry, captions, popup bindings **and color** — the last read off
   the rasterized artwork, since a built control's `BackgroundFillColor` reads
   back transparent white whatever you authored.

### B. Modify an existing panel

There is a vocabulary for this - write the change as JSON, resolve it against
the real project on the Mac, then apply:

1. **Describe the change** - see `examples/edits.json`. Four ops:
   `rename` (captions), `retarget` (another panel model, optionally rescaling),
   `renumber` (addressable `userId`s), `restyle` (color remap). Selectors are
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
  real verification is looking at the rasterized asset.

Reading and rendering need nothing but Python and Pillow:

```bash
python -m gdl.project <file.gdl>      # resources, fills, borders
python -m gdl.themes  <file.gdl>      # the palette it actually uses
python tests/score.py record <file.gdl> <snapshots> -o before.json
```

Writing goes through `powershell/GdlProject.ps1` on Windows. **Clone, never
construct** — every constructor and property setter throws headless, and a failed
setter writes the backing field *before* throwing, so it looks like it worked.

## Running the Windows half

**On the Windows box, use `powershell\New-GdlPanel.ps1`** (above) and skip the
rest of this section. A Claude Code session there is already interactive, so
there is no VM, no remote exec and no scheduled task.

Three things about driving GUI Designer that cost time here, in case you are
scripting something it does not cover:

- **Wait for a build with `powershell\Wait-GdlBuild.ps1`.** It waits for the
  `.gdl` to be rewritten and then to stop growing. Every cheaper signal is
  wrong: the title's trailing `*` only means unsaved changes, so a freshly
  packed file never has one and the wait returns instantly onto a stale
  payload; and the Build Manager window appears seconds *after* the keystroke
  and closes ~5s *before* the file is written, so killing the process on that
  signal truncates the payload. Measured: dialog gone at t+4s while still
  building, file written at t+46s.
- **`Get-Process` caches `MainWindowTitle`** — call `.Refresh()` or it reads
  `GUI Designer` forever and your wait never ends.
- Read the screen back with `System.Drawing`'s `CopyFromScreen`.

### From macOS against a Parallels guest

Fully scriptable; `docs/from-scratch.md` §7 has detail.

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

- **The font is not the donor's any more, but check that it isn't.**
  `Apply-GdlPlan.ps1` set no font at all until 2026-09-08, so a spec's `size`
  reached the preview and stopped there - labels built at the donor's 20pt,
  buttons at 13pt, shapes at 14.25pt. `Set-GdlFont` now applies size, weight and
  (where the project already carries the resource) family, on the control and on
  every state. Family is the conservative one: a face with no `PBFontResource`
  in the donor is reported, not silently substituted.
- **`flattenText` bakes captions into the artwork.** A cloned button inherits it,
  so Build deduplicates every generated button to one asset carrying the donor's
  word — while `layout.json` holds the correct captions. The model reads
  perfectly and the panel is wrong. Set `flattenTextField = false`.
- **A clone inherits what you didn't ask for.** Page-level artwork, button icons,
  ids. Clear `<TLPImageID>` on a cloned page and `buttonImageField` on a cloned
  button unless you want the donor's.
- **Buttons render from their STATE, not the control.** Set text/color on every
  state or the caption won't appear.
- **"Field is null" is not "field is missing."** Most color and image fields are
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
- **Icon fonts** — for single-color icons, faster and needs no resource.
  Afterburn 136 glyphs at U+E900–E98C, Mach (Extron-Lift) 121 at U+E900–E978.
  Place them as text in that face.

## Verification gates — do not skip

- **Render change**: `tests/score.py record` before and after, then `diff`. It
  exits non-zero on any page regressing. A change that improves one page and
  regresses twenty is the documented failure mode here.
- **Spec change**: `python -m pytest` (102 tests: 72 spec, 23 edit, 7 fonts).
- **Anything authored**: two gates, not one.
  1. GUI Designer must **open and build** it — a file that merely serializes
     proves nothing.
  2. `python tests/verify_built.py <plan.json> <built.gdl>` — because a build
     that reports 0 errors still relocates controls, bakes captions and drops
     fills. Every one of this repo's worst authoring bugs built perfectly
     clean. `New-GdlPanel.ps1` runs this for you and fails the run on it.
- Report numbers you actually ran. Never state a build succeeded on the strength
  of "no error dialog appeared" — say what you checked (payload member present,
  N controls rasterized, verifier clean).

## Where the design authority lives

`docs/design-rules.md` separates three things and you must keep them separate:
what Extron **documents**, what the Liberty Bank fixture happens to **do**, and
what we **extrapolated**. Never quote an extrapolated number to a client as an
Extron requirement — the touch-target formula in particular reproduces Extron's
published table but is our derivation, not their stated rule.
