---
name: extron-panel
description: Use when creating, modifying or reviewing an Extron GUI Designer touch-panel (.gdl/.glt) — designing a panel from a description, editing an existing client panel, checking a design against Extron's standards, or previewing what a panel will look like before it is built.
---

# Building Extron touch panels

This repo can read, render, check and generate Extron `.gdl` panels. The whole
loop is proven against GUI Designer 1.28.0.7, and on a machine with GUI
Designer installed it runs unattended end to end — `powershell\New-GdlPanel.ps1` takes a JSON spec and
returns a built, verified panel without anyone opening GUI Designer.

So the job here is usually to turn a description into a good spec. The build is
mechanical; the design is not.

Read `docs/design-rules.md` before making design decisions and
`docs/gdl-format.md` before touching the format. Both encode findings that were
expensive to get.

## The one thing to internalize

**Build owns the artwork.** You never make pixels. You set semantic properties —
a fill color, a stroke, a *named* border resource, a font, a caption — and GUI
Designer rasterizes them on build. A control you author carries `TLPImageID = -1`
until then.

This is why a preview is possible at all, and why "the file looks right" is not
the same as "the panel looks right" (see the `flattenText` trap below).

## Two workflows

### A. Generate a panel from a description

1. **Pick the panel model first**, and put it in the spec as `"model"`.
   `gdl/spec.py`'s `MODELS_FULL` holds every panel GUI Designer builds for, with
   each one's resolution, DPI and Extron part number, read from the assemblies
   (`docs/design-rules.md` §1 lists them). The canvas is not a constant - and
   **DPI varies by nearly 2x within a resolution**, so naming the model is what
   makes the touch-target check right rather than merely safe. Ask if you don't
   know it.
2. **Pick the theme.** `gdl.themes.AFTERBURN` is the documented token set. For
   Mach/Shockwave/Turbulence, or a client's house style, run
   `python -m gdl.themes <template.glt>` and read the tokens off the template.
3. **Write the spec** — see `examples/panel.json` for the full vocabulary and
   `examples/huddle.json` for a small one written straight from a prose brief.
   Use `grid`/`stack` for layout;
   never hand-type a rect. Nest them for sub-regions (a nested directive lays out
   inside its parent cell, and a `rect` at that depth is an offset into it).

   **Give the buttons feedback.** A button with one appearance is inert: the
   control system sets it On and nothing on the panel changes. Set `"on"` in
   the theme and every button gets an On state for free:

   ```json
   "theme": { "raised": "#37394E", "accent": "#3D8BFD", "on": "accent" }
   ```

   Per button, `"on": "accent"` changes just the fill; `"on": {"fill": "surface",
   "color": "muted", "stroke": "accent", "border": "capsule"}` changes whatever
   it names and inherits the rest from the Off appearance. Omit `on` entirely
   and the button keeps a single appearance, which is right for a label-like
   button and wrong for anything the control system drives.

   `Off`/`On` is what Extron's own templates use for **3475 of 3668** buttons
   (94.7%). Multi-state idioms (`Muted`/`Level 1`/`Level 2`/`Level 3`) exist but
   are domain-specific; do those with `gdl.edit` on a real project.
4. **Check it**: `python -m gdl.spec check <spec.json>` — ids, off-canvas, sizes,
   unknown resources, and Extron's numeric standards (touch target, spacing,
   ≤9 buttons per group, ≤6 colors, ≥14pt body text).
5. **Preview it**: `python -m gdl.spec render <spec.json> out/preview.png`, then
   **look at the image**. The compositor is scored against GUI Designer's own
   output, so this is a real preview, not a sketch. Iterate here — it is fast
   and needs no GUI Designer.
6. **Check it against the donor**: `python -m gdl.spec donors <spec.json>
   <donor.gdl>`. The donor supplies every cloned control, so a type it lacks is
   unauthorable — and its page/popup names are taken, which is a build error.
   Both take a second to find here and a whole build to find there.

   **Pick the donor deliberately — it ships in the result.** The fixtures are a
   real client's project, so a panel cloned from one carries their page names,
   popups, artwork and retail fonts. For anything going to a client, use a
   *seed* from `seeds/` — fourteen themed projects made with **File > New
   Project...**, across six theme families and several sizes (`seeds/README.md`
   lists them; `git lfs pull` fetches them). Prefer one at the target size:
   `retarget` builds a correct panel at another size, but only 22% of controls
   match what Extron's own designers drew there. Extron's `.glt` templates cannot be
   donors — they have no `PBProject`, and a file built from one makes GUI
   Designer open empty and offer the Create Wizard. `donors` refuses them with
   that explanation. See `docs/from-scratch.md` §5c.

   `donors` checks six things, each of which otherwise surfaces only in a build:
   control types, page-name collisions, **border resources**, **font families**,
   **canvas size** and **button states**. The font one is the sly one — a family
   the donor has no `PBFontResource` for does not fail the build, it ships the
   panel in the donor's face. The states one is the same shape: a donor whose
   buttons carry a single state cannot express Off/On, the applier cannot create
   the missing one, and the panel builds looking correct and does nothing when
   switched. Answer its complaints before building; that is the entire
   point of the step.
7. **Build it.** With GUI Designer installed this is one command, which re-runs steps 4
   and 6 and finishes with step 8:

   ```powershell
   powershell\New-GdlPanel.ps1 -Spec examples\panel.json `
       -Donor fixtures\gdl\Interface__alt_....gdl -Output C:\gdlwork\Boardroom.gdl
   ```

   check → donors → plan → apply → pack → open → Save and Build → wait →
   verify. It exits 0 only if the verifier passed, so it gates rather than
   reports. Nobody touches GUI Designer. Add `-KeepOpen` to leave it up.

   Without GUI Designer, stop at `python -m gdl.spec plan <spec.json>
   out/plan.json`; the rest runs where it is installed, per
   `docs/from-scratch.md` §7.
8. **Verify the build** (already done for you by `New-GdlPanel.ps1`):
   `python tests/verify_built.py out/plan.json <built.gdl>`. Do not skip this
   because the build was clean; that is exactly when it earns its keep. It
   checks geometry, captions, popup bindings **and color** — the last read off
   the rasterized artwork, since a built control's `BackgroundFillColor` reads
   back transparent white whatever you authored.

### B. Modify an existing panel

There is a vocabulary for this - write the change as JSON, resolve it against
the real project, then apply:

1. **Describe the change** - see `examples/edits.json`. Four ops:
   `rename` (captions), `retarget` (another panel model, optionally rescaling),
   `renumber` (addressable `userId`s), `restyle` (color remap). Selectors are
   ANDed and support exact or regex match on name and caption.
2. **Check it**: `python -m gdl.edit check <edits.json> <panel.gdl>`. Every
   selector resolves against the real file, so "matched nothing" is an error
   here rather than a silent no-op at apply time. Errors block; warnings do not.
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

Writing goes through `powershell/GdlProject.ps1`, with GUI Designer installed. **Clone, never
construct** — every constructor and property setter throws headless, and a failed
setter writes the backing field *before* throwing, so it looks like it worked.

## Driving GUI Designer

Use `powershell\New-GdlPanel.ps1` (step A7). To script anything it does not
cover, read `docs/from-scratch.md` §7 first — the obvious ways to trigger a
build and to tell when it has finished are both wrong, and each fails in a way
that looks like success.

## Traps that have already cost time

Each of these produced a build that reported success and a panel that was
wrong. What to do is here; why is in `docs/gdl-format.md` §7 unless noted.

- **Check the font came from the spec.** `Set-GdlFont` applies size, weight and
  — only where the donor already has a `PBFontResource` for it — family. A
  family the donor lacks is reported and the panel ships in the donor's face;
  `gdl.spec donors` warns first and `verify_built.py` catches it after.
- **Set `flattenTextField = false` on cloned buttons**, or Build bakes the
  donor's caption into every button's artwork (`docs/from-scratch.md` §5b).
- **Clear what a clone inherits:** `<TLPImageID>` on a cloned page,
  `buttonImageField` on a cloned button.
- **Buttons render from their states.** Set text and color on every state, and
  reach them with `Get-GdlStates` — `PBStates.Count` reports 1 for an Off/On
  button, so a loop to `.Count` writes state 0 only.
- **"Field is null" is not "field is missing."** Clone a donor value from
  elsewhere in the project.
- **Popups go through `Register-GdlPopupGroup`, checked by
  `Test-GdlPopupBinding`** — a binding lives in four places (§6).
- **Page and popup names share one namespace with the donor's.** `gdl.spec
  donors` checks.
- **Author every popup's size.** Build moves a control that overflows its page
  to 0,0, and a cloned popup keeps the donor's size.
- **A bridge-saved file always needs rebuilding** — `Save-GdlProject` resets
  every `TLPImageID` (§3) — and the bare `0x80070002` it prints on every save is
  not an error.

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
- **Spec or edit change**: `python -m pytest`, all of it.
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
