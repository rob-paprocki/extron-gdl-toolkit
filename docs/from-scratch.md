# Building a panel from scratch

Can you design an Extron touch panel as an artefact — a spec, a mockup, a
generated layout — and turn it into a real `.gdl` that GUI Designer opens and
builds? This is the answer as far as it can be established without Windows,
which is further than expected.

**Short version.** Yes, as a constrained layout-and-theming generator. The
binding constraint is real — *Build owns the artwork* — but the design space it
leaves is much wider than "seven border resources", and the risky step everyone
assumes is necessary turns out to be avoidable.

## 1. What actually bounds the design space

An authored control carries `TLPImageID = -1`. It has no artwork. What it has is
a fill colour, a stroke colour, and a **named** border resource that supplies
the silhouette. GUI Designer rasterises those on Build. So a generator never
makes pixels; it names resources and sets colours.

The obvious reading of that — and what the older notes imply — is that a
generator is limited to the seven border resources the shipped panel references.
That reading is wrong. `gdl/project.py`'s `border_resources()` enumerates
`PBResourceReferenceBorder`, which is *bindings in use*, not definitions. The
definitions live in `PBProject.resourceSetField`, and there are far more of them:

| Class | Count in `_alt 2_0_0` |
|---|---|
| `PBBorderResource` | **34** |
| `PBImageResource` | 38 |
| `PBFontResource` | 4 |

Of the 34 borders, 28 are System-authored (`authorField = 0`) templates and 6
are the User-authored `Afterburn - *` ones. Read out of their `dataField`
(`PBBorderInfo`), the parametric vocabulary is:

| | values present |
|---|---|
| shape | rectangle family (1), ellipse (2) |
| style | 2D flat (0), 3D bevelled (1) |
| corner radius | 0, 5, 10, 14, 999, 9999 (9999 = capsule) |
| thickness | 0, 1, 2, 3 |
| 3D lighting | `depth`, `surfaceHeight` (3, 78, 117) |

The six Afterburn resources are literally reparametrised clones of the System
templates — same `type`/`style`/`depth`/`surfaceHeight`, differing only in
`cornerRadius` and `thickness`.

**The consequence that matters:** a generator that only *references* the 34
resources already in a donor project needs no new resource appended. Referencing
is proven — it is what every control in every fixture does. So the interesting
design space is reachable without the one operation nobody has tested.

## 2. What is free, what is bounded, what is impossible

**Free.** Layout and hierarchy, page and popup structure, ID allocation, exact
fill/stroke/text colour (any ARGB), typography within the embedded faces, which
of the 34 border resources each control uses.

**Bounded.** Silhouette — rectangle/rounded/capsule/ellipse × flat/3D, at the
radii and thicknesses those 34 resources encode. A new radius means a new
resource, which is the unverified step.

**Impossible without new resources, and possibly impossible at all.**

- `PBLine` endpoints are an enum of anchor positions on the control's own rect,
  not coordinates — no diagonal or freehand line.
- Canvas size is fixed by the panel model (1280×800 across every fixture).
- Arbitrary raster art: unless the bitmap is already a `PBImageResource`, or can
  be drawn from the two embedded icon fonts, it needs the resource-append step.
- Gradients beyond what `depth`/`surfaceHeight`/`lightAngle`/`lightBrightness`
  produce.

## 3. The pipeline, and what exists today

| Stage | State |
|---|---|
| Design artefact → spec | **Built.** `examples/panel.json` is a worked spec. |
| Layout pass | **Built.** `gdl/spec.py` `grid()` / `stack()`. |
| Control ID allocation | **Built.** Per-page bands, honours pinned ids. |
| Preview render | **Built.** Straight through `gdl/compose.py`. |
| Spec → `ProjectGCP` | **Not built.** Needs the PowerShell bridge. |
| Repack to `.gdl` | Built already — `gdl/container.py pack`. |
| GUI Designer opens + builds | **Human, on Windows.** The only real oracle. |

Note one correction to `CLAUDE.md`'s gap list: **group registration is not
missing.** `Register-GdlPopupGroup` is a complete, exercised implementation of
the only group concept the format has (a class census finds exactly five
`PBControlGroup` instances across the whole corpus, all popup-page groups). The
genuine gaps were control-level ID allocation and a layout pass, and both are
now in `gdl/spec.py`.

## 4. The preview is the point

The expensive step is the round trip to a Windows box with GUI Designer
installed. The compositor now scores **2.19% mean** differing pixels against
GUI Designer's own snapshot exports, which makes it good enough to judge a
design *before* paying that cost:

```bash
python -m gdl.spec check  examples/panel.json     # ids, overlaps, off-canvas, unknown resources
python -m gdl.spec render examples/panel.json out/preview.png
```

![generated panel](panel-preview.png)

That image is a panel that has never existed: 28 controls, every rect computed
by the layout pass, every id allocated, rendered by the same code path that is
measured against ground truth. It is not proof GUI Designer will accept it — see
below — but it is proof the *design* is right.

The preview is honest about what it is drawing: every control is emitted with
`TLPImageID = -1`, exactly as an authored control is before Build, so the
preview draws from the same fill-plus-named-border properties a writer would
set.

## 5. What still needs a Windows box

These are batched deliberately. Each needs the same setup — 32-bit PowerShell
5.1, `Initialize-Gdl`, a donor project — and the expensive part is the human
open-and-build round trip, so do them in one session rather than one at a time.

1. **Does referencing an unused-but-present border resource work?** Take a
   control, repoint its `PBResourceReferenceBorder` at a System template the
   project does not currently use (say `3D Capsule`), build. *This is the one
   that decides whether §1's conclusion holds.* Cheapest and highest value.
2. **Can a `PBBorderResource` be appended?** Clone an entry from
   `resourceSetField`, set a new `nameField` and an out-of-corpus
   `cornerRadius`/`thickness` (e.g. 20/1), `.Add()` it the way
   `Register-GdlPopupGroup` appends to `popupPageGroupsField`, bind a control to
   it, build. If this works the design space is fully parametric; if not, §1's
   34 are the ceiling.
3. **Does an out-of-corpus `PBBorderInfo` combination rasterise sanely,** or get
   clamped/garbled?
4. **Cross-graph cloning.** Can `Copy-GdlObject` move an object between two
   separately-deserialised projects? Decides whether a shared component library
   is possible, or whether every generated panel is limited to its own donor.
5. **What ID uniqueness does GUI Designer enforce** on open/Build? Decides how
   defensive the allocator must be.
6. **`referenceCountField` semantics** — `Register-GdlPopupGroup` hardcodes 2.
   Does a group with more or fewer members misbehave?

## 6. Honest limits of everything above

- Nothing here has been through GUI Designer. `gdl/spec.py` produces a render
  and a model; it does not write a `.gdl`. A file that merely serialises proves
  nothing — that is this project's own standard and it still applies.
- The resource counts and parameters are from the `_alt 2_0_0` fixture. The two
  archived fixtures carry 36 border resources, so the number is project-specific.
- The preview's fidelity is measured against pages made of *built* artwork. A
  page of `TLPImageID = -1` controls is exercised by exactly one control in the
  whole corpus (the Offline Window), so the preview's accuracy on a fully
  synthetic page is inferred from that one data point, not measured.
