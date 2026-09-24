# Editing an existing panel

The other half of `docs/from-scratch.md`. Building a panel from a description is
the impressive demo; changing one that already exists is the job. A client says
"rename those three buttons, and we're moving to the bigger panel" and the
question is whether that can be done reliably rather than by hand.

It can. Four of the five operations are verified end to end against GUI
Designer 1.28.0.7 on the real Liberty Bank project; `renumber` is planned and
checked, but has not been through a build.

| Op | What it does | Verified |
|---|---|---|
| `rename` | captions, state by state, wherever they actually live | 12 controls built: 9 plain captions correct on both states; 3 formatted ones are in the artwork (below) |
| `restyle` | remap colors on each control and each state, text color included | 5 sliders built, 5/5 off the artwork; a fill held only on a state and a text color, built and correct |
| `states` | give a button the states it should have: add, remove or rename them, and set each one's look | grown 2 to 3 and trimmed 3 to 2, built, every state correct |
| `renumber` | reassign addressable `userId`s in bands | planned + checked |
| `retarget` | move to another panel model, optionally rescaling | **654/654 on the fixture; 650/650 on a seed retargeted 1280x800 -> 1920x1080, popup canvases preserved** |

## The shape

Identical to the spec pipeline, for the same reason. Decisions are made in
Python against the real `.gdl`, on any OS; PowerShell only applies ops.

    python -m gdl.edit check <edits.json> <panel.gdl>
    python -m gdl.edit plan  <edits.json> <panel.gdl> out/edits-plan.json
    powershell\Apply-GdlEdits.ps1 <ProjectGCP> out/edits-plan.json <out>
    # ... open, Save and Build (Ctrl+Shift+B) ...
    python tests/verify_built.py out/edits-plan.json <built.gdl>

Selectors resolve against the actual project at `check` time, so a typo is an
error up front rather than a silent no-op discovered on the panel. Errors
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
`gdl.edit` writes the new one back to the same place - state by state, since
each state keeps its own.

Formatted text is the awkward one. It carries its layout inline —
`"\t\tDevice\r\n\t\tComms"` — and it is **flattened into the artwork**, so
`layout.json` reports it as `''` both before and after an edit. Measured:

- `Displays` → `Screens` rasterized perfectly.
- `Cameras` → `Camera Control` came out as "Camera" on one line and "Control"
  on a second, unindented, over the icon.

The hand-placed tabs indent line one only. `check` warns whenever a formatted
caption is replaced by something longer, and `verify_built` reports these as
*not verifiable here* rather than passing or failing them — the only real check
is looking at the asset PNG.

## A button is its states

A button draws from its states, not from itself. In the fixture, **288 of 442
buttons have no fill of their own** and a fill on each state. Table Input 1 is
transparent when Off and `#242634` when On, and the two need not share a
caption either. So every edit reads and writes each state, addressed by index,
which is also the number the control program sets.

- **`rename` with `map`** changes whatever says the old caption, and nothing
  else. `{"Display On": "Screen On"}` leaves `Display Off` alone.
- **`rename` with `text`** renames the whole control, so it is refused on a
  button whose states say different things. One caption on every state would
  erase the feedback wording. Add `"state": "On"` (or a list) to rename only
  those states. A selector's `text` matches a caption in any state.
- **`restyle`** remaps each state from its own colors: fill, stroke and text
  color. An Off-to-new mapping never reaches an On state that was a different
  color.
- **`states`** sets a button's state list, in order:

  ```json
  { "op": "states", "select": { "text": "Table Input 1" },
    "states": ["Off", "On", { "name": "Fault", "fill": "#8B1E1E", "text": "No Signal" }],
    "press": "On" }
  ```

  State *i* keeps the look of the button's existing state *i*. A new state
  starts as a copy of the last one, which is how the applier grows the list,
  and whatever it names is written over that. A state takes `name`, `text`,
  `fill`, `stroke` and `color` (the text color). Extra states are dropped from
  the end. The press state stays where it was, unless `press` names another or
  the state it pointed at is gone. A three-state camera preset whose press
  state was `On_1`, trimmed to Off/On, presses to On. `check` refuses a copy
  that would look exactly like the state it was copied from: the program could
  set either, and the panel would show no difference. Every op is planned
  against the file on disk, so `check` also refuses a `states` op on a button
  that another op changes the states of. Put that caption or color in the
  `states` op instead.

`verify_built.py` checks each state an edit wrote: its name, caption and text
color from the model, and its fill off that state's own artwork. After
`states`, it also checks the count, the press state, every state's look, and
that states meant to differ built as different images.

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
initialized instance — after which the title bar reads
`[TLP Pro 1535M: retargeted2.gdl]`.

**Resize the popups too — but to their own size, not the screen's.** Resizing
only `Pages` left every popup at the old canvas, so all 297 scaled popup
controls overflowed and Build moved them to 0,0. Page controls were fine, which
made it look like a popup-specific bug rather than a missing collection. With
`PopupPages` included: 654/654.

The first fix for that was wrong in a way the Liberty Bank project could not
show. It set every page *and popup* to the new **screen** size, on the reading
that a popup's authored `widthField`/`heightField` is always the whole canvas
and `layout.json`'s smaller 915x800 is the *displayed* size taken from the
reference that shows it. Every popup in that project happens to be authored
full-canvas, so both rules agree there and it verified 654/654.

Extron's own Afterburn template settles it: **10 of its 29 popups are authored
at 880x525, and the built `layout.json` reports 880x525 for them** — all 29
built popup sizes match the authored canvas exactly. The authored size *is* the
popup size. Forcing it to the screen size turns a modal card into a
full-screen page in the shipped file.

So `gdl.edit` now emits a size per page, each scaled by the same per-axis
factors as its own controls. A full-canvas page lands exactly on the screen size
(1280×1.5, 800×1.35 → 1920×1080); an 880×525 card becomes 1320×709. What matters
is that canvas and contents move together, so nothing can overflow that did not
overflow before. `tests/test_retarget_canvas.py` pins it.

`check` catches the general form of this before anything is built: any control that would
fall outside its page after the edit is an **error**, because Build relocates it
silently. It runs against each page's own new canvas, popups included — they
are the only pages whose canvas may differ from the screen, so they are where it
matters most.

### What a retarget does and does not promise

Extron ships the same Afterburn project at 1280×800 and 1920×1080, both authored
by hand, so for once there is a ground truth to score against. Retargeting the
1035 seed to `TLP1535M` and building it:

| | |
|---|---|
| planned controls landing exactly where planned | **650/650** |
| controls Build relocated to 0,0 | **0** |
| popup canvases preserved (10 at 1320×709, 19 full-screen) | ✓ |
| title bar / part number | `TLP Pro 1535M`, `60-2000-02` |
| identical to Extron's own hand-authored 1535 | **22%** (median 18px, p90 54px, max 127px) |

That last row is the honest bound. Per-axis linear scaling **is** the rule
Extron used — fitting their two files against each other gives R²≈0.9997 on all
four rect components, with slopes 1.507/1.366 against our 1.5/1.35. The residual
is hand-nudging by their design team, not a different transform.

So a retarget produces a **valid, self-consistent, buildable** panel at the new
size, and not a reproduction of a human redesign. For a client's own project
that is the right answer — proportional rescale is what "move this to the bigger
panel" means. Do not read it as "indistinguishable from what a designer would
have drawn."

## The model table

`gdl/spec.py`'s `MODELS_FULL` lists all 55 panels GUI Designer builds for, with
resolution, DPI and Extron part number, read from the assemblies via
`GetDefaultResolutionDpi` and `CreatePlatform` rather than transcribed from the
Project Create Wizard. `research/data/platform-details.txt` is the raw capture.

The correction that matters: **DPI is per model, not per resolution.** 1280x800
alone spans 124.75 (TLP Pro 1220/1225), 149 (TLC 1026M, TLP Pro 1025/1035,
ZRTP 1025), 188.68 (TLP Pro 835) and 220 (virtual Android). That is a 1.76x
spread and it lands directly on the touch-target minimum: 44px, 53px, 67px,
78px for the same 9mm rule. Keying the minimum off the resolution is right only
for whichever model that resolution's row was measured on.

So name the model. `touch_minimums('TLP1035T')` is the right answer;
`touch_minimums((1280, 800))` is a safe one, using the densest *physical* panel
at that size. (The VTLP virtual targets are excluded from that maximum: their
220 "DPI" is the host phone or browser's, not a panel's.)

Also worth knowing: 1280x720 had *no* documented minimum, because Extron's
published table has no row for it. The assemblies do — TLP Pro 535M/T at
293.72 DPI, giving a 104px target.
