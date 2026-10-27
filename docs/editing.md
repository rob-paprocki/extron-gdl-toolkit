# Editing an existing panel

The other half of `docs/from-scratch.md`. Building a panel from a description is
the impressive demo; changing one that already exists is the job. A client says
"rename those three buttons, and we're moving to the bigger panel" and the
question is whether that can be done reliably rather than by hand.

It can. All five operations are verified end to end against GUI Designer
1.28.0.7: four on the real client project, and `renumber` on Extron's own
Afterburn 1035 seed and on a panel generated from a spec.

| Op | What it does | Verified |
|---|---|---|
| `rename` | captions, state by state, wherever they actually live | 12 controls built: 9 plain captions correct on both states; 3 formatted ones are in the artwork (below) |
| `restyle` | remap colors on each control and each state, text color included | 5 sliders built, 5/5 off the artwork; a fill held only on a state and a text color, built and correct |
| `states` | give a button the states it should have: add, remove, rename or reorder them, and set each one's look | grown 2 to 3, trimmed 3 to 2, and a state inserted before On; built, every state and press state correct |
| `renumber` | reassign the IDs of the addressable controls it selects - each button, label, level or slider that has one - from `start`, `step` apart, within 1 to 65535; controls sharing an ID (mirrors) take one new one, a mirror the selector leaves is a warning, and a band per page is a renumber per page | **26/26 on two builds**: a seed popup's 12 buttons from 20000 and a mirror on two popups to one new ID, and 12 of a generated panel's controls from 30000 - each on its new ID, no other ID moved, `verify_built` 0 problems; the ID map made off each build verifies, and the one from before fails on exactly the controls renumbered (`archive/job-e823df9b/probes-128/`) |
| `retarget` | move to another panel model, or turn one that rotates, optionally rescaling | **654/654 on the fixture; 650/650 on a seed retargeted 1280x800 -> 1920x1080, popup canvases preserved; 650/650 on the same seed turned to a portrait 1035M** |

## The shape

Identical to the spec pipeline, for the same reason. Decisions are made in
Python against the real `.gdl`, on any OS; PowerShell only applies ops.

    python -m gdl.edit check <edits.json> <panel.gdl>
    python -m gdl.edit plan  <edits.json> <panel.gdl> out/edits-plan.json
    powershell\Apply-GdlEdits.ps1 <ProjectGCP> out/edits-plan.json <out>
    # ... open, Save and Build (Ctrl+Shift+B) ...
    python tests/verify_built.py out/edits-plan.json <built.gdl>

Selectors resolve against the actual project at `check` time, so a typo is an
error up front rather than a silent no-op discovered on the panel. So is a
misspelled key, at every level of the file: a selector skips a key it does not
know, so `{"tipe": "PBSlider"}` once selected every control in the project, and
`check` now names the key and plans nothing for that edit. A key starting `_`
is a note (`_why`). Errors
block the plan; warnings never do — a retarget of a real project always
surfaces dozens of pre-existing touch-target violations, and refusing on those
would mean refusing the job.

The edited panel's programmer gets an ID map off its build, as a generated
panel's does from its spec: `python -m gdl.idmap from-built <built.gdl> <out>`
(`docs/idmap.md` §8).

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
caption is replaced by something longer. `verify_built` reads the words off the
built project, where Build reads them, and looks for each line in the art:
drawn by `gdl.compose` in the state's face, where it fits best, a line must
cover the art's text there and be covered by it, and land in a run of text its
own width. A line found nowhere is a failure, and one whose words are found on
two lines is said to have wrapped. The art cannot tell one letter from another,
which is why the words come from the project. Measured on the client
fixture's formatted captions of words - 11 controls, 22 states; its other 12
are icon glyphs - each scores 0.93 or more in its own art and none over 0.89
in another's but `Camera` in Device / Comms, at 0.93 - a near word the project's
words catch and the art does not. A line between 0.85 and 0.93 that lands in a
run its own width, or one in a face drawn in a stand-in, is still reported *not
verifiable here*. So is a line holding an icon glyph - a private-use code point
(U+E000 to U+F8FF), which Build draws in its run's icon face, not the state's -
and a caption whose text color is within the text mask's 64 a channel of its
art's commonest color, where the whole fill reads as text: white on
(200, 200, 200), or the fixture's grey #767789 on #37394E. The fixture's other
12 controls, 24 states, are all one or the other. That is one face at one size
of ground truth.

## A button is its states

A button draws from its states, not from itself. In the fixture, **none of its
442 buttons has a fill of its own**, and 340 have one on each state. Table
Input 1 is transparent when Off and `#242634` when On, and the two need not
share a caption either. So every edit reads and writes each state, addressed by
index, which is also the number the control program sets.

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

  States are matched **by name**. A name the button already has keeps that
  state - its look, caption and press role - wherever it moves in the list.
  Any other name renames the state at its position if nothing else claimed
  it, and otherwise starts as a copy of the last state. Existing states nobody
  names are dropped. Whatever a state sets is written over what it starts
  from: `name`, `text`, `fill`, `stroke` and `color` (the text color).

  The press state follows its state, unless `press` names another. Inserting
  Recalling before On on a camera preset leaves it pressing On, now at index 2.
  Matched by position instead, it pressed Recalling and every check passed,
  because the plan itself was wrong. If the press state was dropped, it goes
  to On: a preset pressing `On_1`, trimmed to Off/On, presses On.

  `check` refuses a copy that would look exactly like the state it was copied
  from: the program could set either, and the panel would show no difference. Every op is planned
  against the file on disk, so `check` also refuses a `states` op on a button
  that another op changes the states of. Put that caption or color in the
  `states` op instead.

`verify_built.py` checks each state an edit wrote: its name, caption and text
color from the model, and its fill off that state's own artwork. After
`states`, it also checks the count, the press state, every state's look, and
that states meant to differ built as different images.

## Retargeting

Three fields must agree: `platformField` (a `PBTouchPanelPlatformPro` subclass
instance), `platformTypeField` (`PlatformProTypeEnum`) and `screenSizeField` -
and on a panel turned the other way up, the platform's own resolution fields
too (below).

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

The first fix for that was wrong, and what it was checked by could not show
it. It set every page *and popup* to the new **screen** size, on the reading
that a popup's authored `widthField`/`heightField` is always the whole canvas
and `layout.json`'s smaller 915x800 is the *displayed* size taken from the
reference that shows it. It is not: 915x800 is that popup's authored size. The
client project's 16 standard popups are authored at their own sizes - 136x496,
900x530, 915x800 and 995x800 - and only its modals are full-canvas. A standard
popup blown up to the screen still holds its scaled controls, so nothing
overflowed, and the 654/654 counted controls landing where planned; no popup's
size was compared.

The corpus settles it. In all 47 projects a popup's built `layout.json` size is
its authored size; every one of the 454 modals is the screen, and none of the
442 standard popups is - Afterburn's 1035 seed has 19 modals at 1280x800 and 10
standard popups at 880x525. Forcing a standard popup to the screen size turns
it into a full-screen page in the shipped file.

So `gdl.edit` emits a size for every page and popup on every retarget. Scaled,
each canvas is scaled by the same per-axis factors as its own controls: the new
screen over the old, the old being the project's `screenSizeField`. It was
taken from the largest control on a page, which 4 of the 47 projects have
nothing as big as the screen for - `client-greenroom-1.1.0`'s is 1185x269 on a
1280x800 screen, and a retarget of it to a 1535 scaled by 1.62x4.01. A
full-canvas page lands exactly on the screen size (1280×1.5, 800×1.35 →
1920×1080); an 880×525 popup becomes 1320×709. Unscaled, a canvas that was the
screen becomes the new one and any other keeps its own - left unplanned, the
applier sets every page and popup to the screen. What matters is that canvas
and contents move together, so nothing can overflow that did not overflow
before. `tests/test_retarget_canvas.py` pins it.

**A panel that rotates is turned with `size`.** The panels that run either way
up (`docs/design-rules.md` §1) take one of their two canvases:
`{"op": "retarget", "model": "TLP1035M", "size": [800, 1280], "scale": true}`.
Without `size` a retarget lands on the panel's default way up; a size the model
does not run at, or one that is not `[width, height]`, is an error. The applier
writes the platform's own resolution fields as well as the screen size - the
fields that say which way up a project is (`docs/gdl-format.md` §7). Turned, the Afterburn 1035 seed built 650/650, every
page at 800x1280. A per-axis scale to the other way up stretches each control
0.625 by 1.6, so it makes a donor the right shape, not a portrait design: a
portrait page is authored at the turned canvas, in a spec. That is how a panel
turned where its theme draws no template that way up gets a seed:
`powershell/New-GdlTurnedSeed.ps1` turns the model's own and builds it
(`seeds/README.md`).

`check` catches the general form of this before anything is built: any control that would
fall outside its page after the edit is an **error**, because Build relocates it
silently. It runs against each page's own new canvas, popups included — they
are the only pages whose canvas may differ from the screen, so they are where it
matters most. It cannot see factors that are wrong, since it measures each
control against a canvas scaled by the same ones, so a standard page planned at
anything but the new screen is an error too.

`verify_built.py` holds the build to both halves of the plan: the screen size,
the platform's own resolution and the part number the model has, and each page's
and popup's canvas at its planned size. A retarget without `scale` plans no
control, so these are all it has to check.

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
Project Create Wizard. `powershell/Get-GdlPlatforms.ps1` regenerates the raw
capture, `research/data/platform-details.txt`, with each panel's supported
resolutions.

The correction that matters: **DPI is per model, not per resolution.** 1280x800
alone spans 124.75 (TLP Pro 1220/1225), 149 (TLC 1026M, TLP Pro 1025/1035,
ZRTP 1025), 188.68 (TLP Pro 835) and 220 (virtual Android). That is a 1.76x
spread and it lands directly on the touch-target minimum: 44px, 53px, 67px,
78px for the same 9mm rule. Keying the minimum off the resolution is right only
for whichever model that resolution's row was measured on.

So name the model. `touch_minimums('TLP1035T')` is the right answer;
`touch_minimums((1280, 800))` is a safe one, using the densest *physical* panel
at that size. (The soft clients - the VTLP virtual targets and the TLI
interfaces - are excluded from that maximum: their 220 "DPI" is GUI Designer's
default for a screen their model does not define, not a panel's.)

Also worth knowing: 1280x720 had *no* documented minimum, because Extron's
published table has no row for it. The assemblies do — TLP Pro 535M/T at
293.72 DPI, giving a 104px target.
