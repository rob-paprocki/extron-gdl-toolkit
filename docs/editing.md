# Editing an existing panel

The other half of `docs/from-scratch.md`. Building a panel from a description is
the impressive demo; changing one that already exists is the job. A client says
"rename those three buttons, and we're moving to the bigger panel" and the
question is whether that can be done reliably rather than by hand.

It can. All four operations are verified end to end against GUI Designer
1.27.0.9, on the real Liberty Bank project.

| Op | What it does | Verified |
|---|---|---|
| `rename` | captions, wherever they actually live | 12 controls, built, 12/12 correct |
| `restyle` | remap colours across a selection | 5 sliders, built, 5/5 correct |
| `renumber` | reassign addressable `userId`s in bands | planned + checked |
| `retarget` | move to another panel model, optionally rescaling | **654/654 controls correct in the built file** |

## The shape

Identical to the spec pipeline, for the same reason. Decisions are made in
Python against the real `.gdl` on a Mac; PowerShell only applies ops.

    python -m gdl.edit check <edits.json> <panel.gdl>
    python -m gdl.edit plan  <edits.json> <panel.gdl> out/edits-plan.json
    powershell\Apply-GdlEdits.ps1 <ProjectGCP> out/edits-plan.json <out>
    # ... open, Save and Build (Ctrl+Shift+B) ...
    python tests/verify_built.py out/edits-plan.json <built.gdl>

Selectors resolve against the actual project at `check` time, so a typo is an
error on the Mac rather than a silent no-op discovered on the panel. Errors
block the plan; warnings never do — a retarget of a real project always
surfaces dozens of pre-existing touch-target violations, and refusing on those
would mean refusing the job.

## What a caption actually is

The thing that made `rename` harder than it looks. A caption lives in one of
three places and a control that uses one leaves the others empty:

| Where | Count in the fixture | Notes |
|---|---|---|
| the control's `textField` | — | rare on buttons |
| first state's `textField` | 336 | the normal case |
| first state's `ftextField` | 23 | *formatted* text |

A selector that compared the control's `textField` matched **nothing** on a real
project. `Project.caption_at()` returns both the caption and where it lives, and
`gdl.edit` writes the new one back to the same place.

Formatted text is the awkward one. It carries its layout inline —
`"\t\tDevice\r\n\t\tComms"` — and it is **flattened into the artwork**, so
`layout.json` reports it as `''` both before and after an edit. Measured:

- `Displays` → `Screens` rasterised perfectly.
- `Cameras` → `Camera Control` came out as "Camera" on one line and "Control"
  on a second, unindented, over the icon.

The hand-placed tabs indent line one only. `check` warns whenever a formatted
caption is replaced by something longer, and `verify_built` reports these as
*not verifiable here* rather than passing or failing them — the only real check
is looking at the asset PNG.

## Retargeting

Three fields must agree: `platformField` (a `PBTouchPanelPlatformPro` subclass
instance), `platformTypeField` (`PlatformProTypeEnum`) and `screenSizeField`.

Two things had to be got right, and each produced a file that opened and built
and was wrong.

**Construct the platform with Extron's factory, not `Activator`.** A
default-constructed `PBTLP1535MPlatform` has the right resolution and a **null
`partNumberField`**, and GUI Designer then titles the project
`Unknown: file.gdl`. It identifies a panel by part number. The fix is
`PBTouchPanelPlatformPro.CreatePlatform(project, type)`, which returns a fully
initialised instance — after which the title bar reads
`[TLP Pro 1535M: retargeted2.gdl]`.

**Resize the popups too.** A popup's authored `widthField`/`heightField` is the
whole canvas, even where `layout.json` reports the popup as 915x800 — that
smaller figure is the *displayed* size, taken from the reference that shows it.
Resizing only `Pages` left every popup at the old canvas, so all 297 scaled
popup controls overflowed and Build moved them to 0,0. Page controls were fine,
which made it look like a popup-specific bug rather than a missing collection.
With `PopupPages` included: 654/654.

`check` catches the general form of this before the trip: any control that would
fall outside its page after the edit is an **error**, because Build relocates it
silently.

## The model table

`gdl/spec.py`'s `MODELS_FULL` lists all 55 panels GUI Designer builds for, with
resolution, DPI and Extron part number, read from the assemblies via
`GetDefaultResolutionDpi` and `CreatePlatform` rather than transcribed from the
Project Create Wizard. `research/data/platform-details.txt` is the raw capture.

The correction that matters: **DPI is per model, not per resolution.** 1280x800
alone spans 124.75 (TLP Pro 1220/1225), 149 (TLC 1026M, TLP Pro 1025/1035,
ZRTP 1025), 188.68 (TLP Pro 835) and 220 (virtual Android). That is a 1.76x
spread and it lands directly on the touch-target minimum: 44px, 53px, 67px,
78px for the same 9mm rule. Keying the minimum off the resolution — which is
what this repo did until now — was right only for the model whose row happened
to be transcribed.

So name the model. `touch_minimums('TLP1035T')` is the right answer;
`touch_minimums((1280, 800))` is a safe one, using the densest *physical* panel
at that size. (The VTLP virtual targets are excluded from that maximum: their
220 "DPI" is the host phone or browser's, not a panel's.)

Also worth knowing: 1280x720 had *no* documented minimum, because Extron's
published table has no row for it. The assemblies do — TLP Pro 535M/T at
293.72 DPI, giving a 104px target.
