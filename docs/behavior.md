# Behavior: what the controls do, and the program that does it

A panel that only looks right is half a deliverable. This covers the other half:
a spec that says what each control **does**, the checks on it, and the control
program generated from it.

```bash
python -m gdl.behavior check    examples/huddle-program.json
python -m gdl.behavior generate examples/huddle-program.json out/program
```

With GUI Designer installed, `powershell\New-GdlPanel.ps1 -Program out\program`
does all of it and verifies the program against the built panel.

## 1. Why the program is separate

**A `.gdl` carries no behavior.** Nothing in the current format says "this
button shows that page". The per-button actions that GUI Designer's previous
generation had (`PanelBuilder.PBActionShowPage`, `PBActionShowPopup`,
`PageBack` and so on, still visible in `GUI Designer.xml`) are gone. They
appear in none of the 26 projects checked (6 fixtures, 20 seeds), and converting
an old project says so outright: *"Local Actions and Audio Resources will be
lost!"*

What the format does keep is **structure**:

- a start page;
- popup groups, and whether a popup is modal;
- an Offline Page;
- a popup auto-hide timeout, which is 0 on every popup in the corpus;
- a numeric ID on every control.

Everything a control does lives in the **control program**, which finds the
control by that ID. So one spec produces two things: `gdl.spec` builds the
panel, and `gdl.behavior` writes the program. Because both come from the same
file, their IDs and names cannot drift apart.

**The addressing rule.** A **control** is addressed by its numeric ID, which
survives Build. A **page or popup** is addressed by **name**. Its number does
not survive: a page authored as 1000 comes back from Build as 51
(`docs/gdl-format.md` §7). Nothing generated ever uses a page number, and the
test double refuses one.

## 2. The vocabulary

Everything below is optional. A spec with no behavior keys still gets a handoff
that lists every addressable ID, and a program that boots the start page.
`examples/huddle-program.json` is a worked example: a prose brief, with each
sentence of its functions turned into one of these keys.

**Project**

| Key | Meaning |
|---|---|
| `start_page` | The page the panel boots into. Defaults to the first page. It is written into the `.gdl` itself (see SKILL.md). |
| `behavior.panel_alias` | The UI Device alias in Global Scripter. Defaults to `TLP1`, with a note. |
| `behavior.devices` | `{name: "what it is"}`. Every device a `call` may name. |
| `behavior.inactivity` | `{"seconds": N, "do": [actions]}`, run when the panel is idle. |

**Page or popup:** `"reached_by": "program"` declares that your own code shows
it, for example an incoming-call popup. It then counts as reachable.

**Control**

| Key | On | Does |
|---|---|---|
| `nav: "<page or popup>"` | button | On press, shows that page or popup. Shorthand for `press`, so don't use both. |
| `press` / `release` | button, slider | `Pressed` / `Released` |
| `hold`, with `hold_time` | button | `Held`, which fires once after `hold_time` seconds |
| `repeat`, with `hold_time` and `repeat_time` | button | `Repeated` while held, the volume-ramp idiom |
| `tap`, with `hold_time` | button | `Tapped`, which means released before `hold_time` |
| `change` | slider | `Changed`. The slider's value goes to every call as `value=` |
| `select_group: "<name>"` | button with an `on` state | One selection at a time (extronlib `MESet`). Usually shared through a `grid`. |
| `bind: "a.b"` | button, label, level, slider | Shows device state. Generates `ui_feedback.a_b(value)`, which sets the button On/Off, the label's text, or the level or slider's fill. |
| `range: [min, max]` | level, slider | Its range. Defaults to 0-100. |

**Actions:** one object, or a list of them run in order.

```json
{ "do": "show_page",  "target": "<page>" }
{ "do": "show_popup", "target": "<popup>", "duration": 0 }
{ "do": "hide_popup", "target": "<popup>" }
{ "do": "hide_all_popups" }
{ "do": "call", "device": "<declared>", "op": "<name>",
  "args": { "<name>": <any JSON value> }, "costly": false }
```

`duration` is in seconds, and 0 means the popup stays until something hides it.
`costly: true` marks a call that must be confirmed: it has to run from inside a
modal popup that also has a cancel.

**Mirrors.** Controls that pin the same `id` are one extronlib object, sharing
one handler and one state. Extron uses this itself: Liberty Bank mirrors its
shutdown confirm and cancel buttons (81, 82) across two popups. It is allowed
only when every copy is the same kind with the same behavior.

## 3. The checks

`check` runs `gdl.spec check` first, because a spec that cannot be built cannot
be programmed. **Problems** block `generate`, the same way they block `plan`.
**Notes** never block: they are heuristics, and each one says which rule it
comes from.

| Problem | Why |
|---|---|
| An unknown action, a malformed action, or `nav` together with `press` | The generated code would be wrong |
| An event the kind cannot raise, or behavior on a panel, image, line, clock or popup reference | Only button, slider, label and level have extronlib objects (ControlScript reference) |
| A `show_page`, `show_popup` or `nav` target that is not a page or popup here, or is the wrong kind | The program would address a name the panel does not have |
| A call to an undeclared device; an op or argument that is not a Python identifier; a slider call with an argument named `value` | Each becomes Python source |
| `hold`, `repeat` or `tap` without `hold_time`; `repeat` without `repeat_time`; a time that is not positive | Held, Repeated and Tapped are timers the Button object runs from `holdTime` |
| `duration` on anything but `show_popup`, or negative | `ShowPopup(popup, duration)` |
| A bound button with no `on` state; one bind path on controls of different value types; two paths that become the same Python name; `bind` and `select_group` on one button | `SetState(1)` on a single-state button shows nothing; one value cannot be both text and on/off |
| A `select_group` member that is not a button or has no `on` state | An MESet selects with `SetState` |
| Controls sharing an ID but differing in kind or behavior | extronlib keeps one handler per object ("last handler assigned will be called") |
| A grouped popup shown from a page with no reference to its group | A standard popup appears only through such a reference (`docs/gdl-format.md` §5) |
| A `costly` call outside a modal popup, or a modal confirming one with no cancel | GUI Design Standards p.71 |
| A page or popup nothing navigates to, unless it is `reached_by: "program"` | Dead layout, or a missing `nav` |
| A modal with no close path: nothing in it hides it, and it is never shown with a duration | p.71: a modal disables everything beneath it, so this locks the panel |

The graph checks run only when the spec declares some behavior. Three unlinked
pages in a layout-only spec are a layout, not a broken program.

| Note | Rule |
|---|---|
| A button that does nothing when pressed | Every tap needs a visible result (Standards p.13) |
| Devices are called but nothing is bound | The panel then cannot show whether a request succeeded (p.13) |
| A dead-end page: nothing on it leads to another page | Heuristic |
| A device declared but never called; a selection group of one | Tidiness |
| `panel_alias` left at the default | It has to match Global Scripter |

## 4. What is generated

```
<out>/
  ui_objects.py   GENERATED  UIDevice, one Button/Label/Level/Slider per ID, ranges, MESets
  ui_events.py    GENERATED  Online, InactivityChanged, and one @event handler per control event
  ui_feedback.py  GENERATED  one setter per bind path, for devices.py to call
  devices.py      CREATED ONCE, then yours: one class per device, one logging stub per op
  main.py         CREATED ONCE, then yours: the entry file
  handoff.json    GENERATED  the ID map, for a programmer on any platform
  handoff.md      GENERATED  the same as tables, with the System Manager step first
```

- **Generated files are overwritten** every run. Each carries the spec's
  SHA-256, so a stale or hand-edited one is caught.
- **`devices.py` and `main.py` are never touched again.** If the spec later
  calls an op that `devices.py` lacks, `generate` prints a stub ready to paste
  and exits 1.
- **To change a generated handler**, re-register it with `@event` in `main.py`.
  extronlib keeps the last handler assigned.

The generated code stays within the extronlib surface that was confirmed from
Extron's own reference and real deployed code:

- `UIDevice`: `ShowPage`, `ShowPopup`, `HidePopup`, `HideAllPopups`, `SetInactivityTime`.
- `Button`: `SetState`, with `holdTime` and `repeatTime`.
- `Label.SetText`, `Level.SetLevel`, `Slider.SetFill`, and `SetRange` on both.
- `MESet` (from `extronlib.system`), `ProgramLog`, `event` and `Version()`.

Button handlers bind `Pressed` by default: the deployed code examined binds
`Pressed` or `Released`, never `Tapped`, and the reference defines `Tapped` only
in terms of `holdTime`. `HidePopupGroup` is avoided, because it takes a
group *number* that exists only after Build.

It stays Python 3.5-compatible (no f-strings, no annotations, no walrus), and a
test enforces that. Extron has moved IPCP Pro xi to Python 3.11, but *"Control
processors not listed above will continue to use Python 3.5"* (Extron,
*What's New in Python 3.11*, 68-3858-01). The generated files import only
`extronlib` and each other. Real Global Scripter projects import sibling modules
flat, as in `import devices`.

## 5. Verification

- **Simulation.** `tests/fake_extronlib` stands in for extronlib and enforces
  its documented contracts:
  - event names per class and handler arity;
  - `Held` and `Repeated` only with `holdTime`;
  - pages and popups by name only;
  - MESet semantics.

  `tests/test_behavior_sim.py` imports the generated program and presses things.
  It also walks the panel as a user would and requires the page and popup flips
  it observes to equal the static navigation graph the checks reasoned about.
- **Against the build.** `python tests/verify_behavior.py <program> <built.gdl>`
  parses the generated Python itself, not just the handoff, and checks it
  against the built `layout.json`:
  - every page and popup name it shows exists, as the right kind;
  - every control ID it addresses is where the handoff says, with that ID and
    that type;
  - selectable and bound buttons built with two states;
  - no other control in a generated page shares an addressed ID;
  - every popup it shows has a reference on the page that shows it.

  Exits non-zero on any problem. `tests/test_verify_behavior.py` makes it fail on
  each of those.
- **End to end.** `examples/huddle-program.json` was built on
  `seeds/Afterburn 1035.gdl` with `New-GdlPanel.ps1 -Program`: the layout
  verified with 0 problems, and so did all 30 program references.

**Not proven here:** that Global Scripter imports the program, and that it runs
on a processor. Neither Global Scripter nor a processor is available here. The
simulation is a substitute for that proof, not the proof itself.

## 6. Designing in Claude Design

The vocabulary is also the target for a Claude Design canvas:

| Design canvas | Spec |
|---|---|
| A prototype link `<a href="X.dc.html">` | `nav: "X"` |
| An overlay trigger | `press: show_popup` |
| Tabs, or a component's `selected` prop | `select_group`, shared across the instances |
| A data-bound prop | `bind` |
| A destructive variant | a `costly` call, inside a modal with a cancel |
| Repeated component instances | `grid` / `stack`, with per-item overrides |

The translator itself is on `docs/ROADMAP.md`.
