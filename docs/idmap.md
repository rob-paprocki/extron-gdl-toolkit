# The ID map: what a programmer gets with the panel

A panel is handed to its programmer with an ID map. It lists every control a
program can address, with its ID, type, page, name and caption, and what it
does. The map is written from the same spec the panel is built from, so the two
cannot drift apart, and it is checked against the built file.

```bash
python -m gdl.idmap check examples/huddle-functions.json
python -m gdl.idmap write examples/huddle-functions.json out/idmap   # idmap.md, .json, .csv
```

With GUI Designer installed, `powershell\New-GdlPanel.ps1 -IdMap out\idmap`
does all of it and verifies the map against the built panel. A revised canvas
keeps the IDs the programmer already has (§9).

## 1. Why a map, and not the panel

**A `.gdl` carries no behavior.** Nothing in the current format says "this
button shows that page". GUI Designer's previous generation had per-button
actions (`PanelBuilder.PBActionShowPage`, `PBActionShowPopup`, `PageBack` and
so on, still visible in `GUI Designer.xml`), but they are gone. They appear in
none of the fixtures or seeds, and converting an old project says so
outright: *"Local Actions and Audio Resources will be lost!"*

The format keeps structure only: a start page, popup groups, whether a popup is
modal, an Offline Page, and a numeric ID on every control. Everything a control
does lives in the control program, whatever it is written in, and that program
finds the control by its ID.

**The addressing rule.** A **control** is addressed by its numeric ID, which
survives Build. A **page or popup** is addressed by **name**. Its number does
not survive: a page authored as 1000 comes back from Build as 51
(`docs/gdl-format.md` §7). The map never lists a page number.

## 2. Saying what a control does

Two optional keys go on a control. `examples/huddle-functions.json` is a prose
brief written out this way.

| Key | On | Means |
|---|---|---|
| `nav: "<page or popup>"` | button | Shows that page or popup. This one is **checked** (§3). |
| `does: "<sentence>"` | button, label, level, slider | Anything else, in words, for the programmer: *"Routes the laptop to the display; On while it is live."* |

Three more keys go elsewhere:

- `"reached_by": "program"`, on a page or popup, says the control program shows
  it (an incoming-call popup, for example), so no `nav` has to lead there.
- `does` on a page or popup, a sentence, says what it is for - *"Asks before
  the room powers off."* A canvas Page's `does` arrives here. The map shows it
  beside the page.
- A top-level `does`, a sentence or a list of them, holds panel-wide functions
  such as *"After ten minutes idle, return home."*

Only the four addressable kinds can carry these keys. Panels, lines, images,
clocks and popup references have no ID a program can take hold of.

**States.** A program shows feedback on a button by setting its state, by
index. A button that asks for feedback - `on`, which is Off and On, or named
`states` (`SKILL.md` step 3) - is listed with every state in order, so
*Display: 0 Off, 1 Warming, 2 On, 3 Cooling* means `SetState(2)` shows On. The
map also names the state the button shows while it is held (`press`). A button
that asked for no feedback keeps its donor's states, which the spec never
named, so none are listed.

**Mirrors.** Controls that pin the same `id` are one control to the program.
Real projects do this on purpose: the client project mirrors its shutdown
confirm and cancel buttons (81, 82) across two popups, and Extron's Shockwave
1035 and 1535 templates draw each source tab's name as a second, caption-only
button under the tab's glyph with the tab's ID. The map lists a mirror once,
with every place it appears. Each copy has to be the same kind doing the same
thing, with the same state names. A copy a panel's layout added where a canvas
control holds the ID - the region page's tab twin (§7) - is that control's
mirror: the row is the control's, not derived, and the copy's place is marked
(`"mirror": true` in `idmap.json`, *Main (mirror: PC Caption)* in the panel
columns).

## 3. The checks

`check` runs `gdl.spec check` first. Problems block `write`, the same way they
block `plan`.

| Problem | Why |
|---|---|
| A `nav` target that is not a page or popup in the spec | The button would flip to nothing |
| `nav` on anything but a button; `does` that is not a sentence; either key on a kind with no ID | It would go nowhere |
| A standard popup shown where the page beneath has no reference to its group - or, for a popup in no group, none bound to it alone. For a popup shown from another popup, that means every page the first can be showing over. | A spec's standard popup appears only through such a reference: one bound to its group, or one bound to it by its ID, as the seeds' Volume Level is (`docs/gdl-format.md` §5) |
| Controls sharing an ID but differing in kind, function or states | A program sees one control per ID, and GUI Designer gives every copy the same states |
| A page or popup no `nav` reaches from the start page, unless it is `reached_by: "program"` | Dead layout, or a missing link |
| A page's or popup's `does` that is not a sentence | It would say nothing |

The reachability check runs only when the spec uses `nav`. Three unlinked pages
in a layout-only spec are a layout, not a broken panel.

**Notes** never block. They cover a button whose function is not described
(once the spec describes any), and a dead-end page that leads to no other page.

The toolkit does **not** require confirmations. Extron's standards ask for a
modal confirmation before costly or irreversible actions (`docs/design-rules.md`
§2), but modern call controls end a call with one tap. Whether an action asks
first is a design decision for the spec. It is not a rule to enforce.

## 4. The map

`write` produces three files with the same content:

- `idmap.md`, to read;
- `idmap.csv`, one row per ID, for a spreadsheet;
- `idmap.json`, which is what the verifier reads.

Each control row carries its ID, type, the page and control name of every place
it appears, its caption, a button's states (`0 Off, 1 On`) and the one it
shows while pressed, and its function
(`nav` and `does`, in words). The page table shows how each page and popup is
reached, and what it is for (its `does`). In `idmap.json`, a page or popup a
panel's layout derived also names the page that derived it and the layout's
name for it (`window`), by which a revision keeps the IDs of what is in it
(§9). Every file carries the spec's
SHA-256; a map of every panel (§7) carries each panel's spec's in `idmap.json`.
A map of one panel names the panel its spec is laid out for (`model`), which
a revision's changes are compared on (§9).
The CSV puts a caption broken over lines on one line; the JSON keeps the
break, which is what the panel draws.

A map written from a revision (§9) also lists its **retired IDs**: IDs an
earlier delivery gave controls that are gone. No control has one, and the
next revision keeps them out of use too.

## 5. Verification

`python tests/verify_idmap.py <idmap> <built.gdl>` checks the map against the
built `layout.json`:

- Every page and popup it names exists, as the kind it says.
- Every control is where the map says, with that ID and that type. Every control
  of that name is checked, not just the first.
- Every button the map lists states for built with exactly those states, in
  that order, and shows the mapped state while pressed.
- No other control on a mapped page shares a mapped ID. A donor page doing so -
  only a spec that keeps them (`keep_donor_pages`) has any - is a note, because
  it answers to the same handler if it is ever shown.
- No page or popup name appears twice.
- Every popup a button shows can appear over every page it can be shown on.
- No control carries an ID the map retires (§9). On a donor page it is a note.

A map of every panel is checked as one panel's (`--panel`, §7). Without it,
or with a panel the map does not have, the verifier names the map's panels
and stops. It exits non-zero on any problem. `tests/test_verify_idmap.py` makes it fail on
each of those.

**End to end.** `examples/huddle-functions.json` - three-state source buttons
and a four-state Display button among its Off/On ones - was built on
`seeds/Afterburn 1035.gdl` with `New-GdlPanel.ps1 -IdMap` on GUI Designer
1.28.0.7. The layout verified with 108 controls and 0 problems, every state's
name, caption, text color and press state included. The map's 28 references
verified with 0 problems.

## 6. Designing on a Design canvas

A Design canvas carries the same keys - a prototype link is `nav`, a
component's function is `does`, its variants are `states`. `docs/claude-design.md`.

## 7. One map for every panel

A canvas that lists several panels is translated to one spec per panel, and
one program drives them all. So it gets **one map**:

```bash
python -m gdl.idmap write-panels out/huddle out/huddle/idmap      # every out/huddle/<panel>/spec.json
python tests/verify_idmap.py out/huddle/idmap <built TLP725T.gdl> --panel TLP725T
```

- **One ID per control, on every panel.** The translator gives each canvas
  control its ID once, on the panel the canvas is drawn on, in its page's band,
  and writes it onto that control on every panel - wherever that panel's layout
  put it (`gdl.design.pin_ids`). A Laptop button on the Home page of a 1035 and
  on a sources page of its own on a 320 is one ID. A control is known by its
  page and its name, so an addressable control on such a canvas must be named.
- **Where it is, per panel.** The rows are in ID order. Each row has a column
  per panel: the page or popup the control is on there, and the copy's own
  name where it is not the row's - a mirror's, or a copy the designer named
  otherwise (*Home; Settings (Power Off)*). Each panel's own page table follows:
  what it boots into, how each page and popup is shown, and what each is for.
  A control that does something
  different on a panel - a Group's Next shows a popup on a mid-size panel and a
  page on a small one - says what it does on each, by panel.
- **The panels are the canvas's own list.** Every spec carries it; the map
  refuses a listed panel with no spec, and translate leaves no spec behind for a
  panel the canvas no longer lists, or from a run that failed.
- **Derived navigation is in the map.** What a panel's layout added - a Group's
  Previous, Next and Back, the button that opens a group's pages on a small
  panel, a level's Up and Down - is a button like any other to the program,
  because a `.gdl` carries no behaviour (§1): nothing happens when it is pressed
  unless the program shows what it names. Each is marked derived, takes an ID
  from 50001 up - the same on every panel it is on - and is listed only on those
  panels. One in a page or popup the layout derived too - a hub's Select
  Source, a Group's popup, the 320's later pages - is known by the page that
  derived that page or popup, the layout's name for it (on a hub, the
  template's) and its own name: not by the name the page or popup shows,
  which on a hub follows the working pages' order (§9). The
  first popup of a derived group has no button leading to it: the
  program shows it as its page comes up, and the page table says so.
- **So is what a source popup and a window draw** (`role`,
  `docs/claude-design.md` §4): a source's `<name> Title`, `Empty` and `Status`
  (Shockwave's Disconnected, which the program sets), a window's `<name>
  Window`, `Title` and `Message`, and its `Close`, `Cancel` and `Power Down` -
  derived, with an ID from 50001 up keyed by its popup and name, one ID on
  every panel. Close and Cancel carry a `does` and no `nav`: only the program
  knows the page that opened the window, so it hides the window. Power Down's
  `does` is the confirmation Page's own. On a hub, where a source popup and
  a settings window are popups of main's group, there is one place back: a
  source popup's and a settings popup's Close, and the Close of the options
  and Display Control popups the page derives, carry `nav` to Select Source
  (Mach's Display Settings' to its Settings), which the map shows as the
  popup they show. On the 320, where a source, a window and the question are
  pages, a page's Back and the question's Cancel go back to the one page
  whose control shows that page - Main for a source, whose key it is; the
  page whose Power asked, for the question - which translate finds over the
  whole canvas (`back`) and writes as their `nav`; with no such page, or
  more than one, they go where the program says, and translate notes it.
- **A slider on a panel that cannot build one** - the 520s', 535s', 320s' and
  300M's seeds have levels and no slider (the profile's `kinds`,
  `docs/claude-design.md` §4) - is a level there, with that derived Up and Down. It
  keeps the slider's ID, and its type reads *Slider; Level on TLP525T, TLP320M*.
- **A hub's chrome keeps the hub's own IDs** (`docs/claude-design.md` §3): its
  menu bar's Volume Up and Down (8120, 8121), its settings opener (8040) and
  Shockwave's and Turbulence's Display Control (8115) are derived - the 1035
  draws none - and keep the seed's ID where no canvas control has it, rather
  than one from 50001. A hub draws its menu bar on every working page, and
  Volume Up and Down, doing one thing on each, are one control there: one ID
  on every page - the seed's, or where a canvas control holds it (Afterburn's
  mode launcher, 8120) one from 50001. The settings opener and Display
  Control open each page's own window (`_one_name_each`), which the map
  refuses one ID for, so each page's is its own: the seed's on the first
  working page in the canvas's order, one from 50001 on the others. So does the 320's (`docs/claude-design.md` §3): its
  title strips (6075 on Main, 6008 on a source's first page, 6009 on a
  later one), More (8010), Back (8011), the Volume modal's glyphs (7023,
  7026) and Cancel (8001) and the empty state's lines (6060 to 6062) - each
  seed ID on the first control that carries it, in name order, the rest
  from 50001. Each page's More and Back go to pages of their own, so they
  are as many controls - one in the frame's `ids` would give every page's
  one ID doing several things, which the map refuses - and the template
  has one of each, its Doc Cam's: which of a room's keeps it is the first
  in name order, not a place the template gives it. What the 1035 draws too (a source's `<name> Title`, the
  question's Power Down and Cancel) has one ID on every panel, from 50001,
  not the 320 seed's (the question's 9028 and 9029). The Volume modal's
  level has the template's glyphs over and under it, not Up and Down: the
  320's template draws no volume control on a page.
- **A region page's fixed chrome keeps the template's seed IDs**
  (`docs/claude-design.md` §3): the Footer's Help (8117), Power (8022) and
  mode launcher (8118), the RightRail's Volume
  (8024) and Mute (8021) - the frame's `ids` - where the designer gave the
  control no `id` and no other canvas control has that ID, the same on every
  page that draws them and every panel; each page's band steps over them. A designer's `id` always wins, and
  where a seed ID is taken the chrome takes one of its band. A call page
  (`role="call"`) keeps the call mode's too: Make Call (5014), End Call
  (5215) and Privacy (5217) - by what their names say, wherever in the VTC
  Section they stand - and Share Content (8090), the call record's `ids`.
- **The call mode's dialer keeps its template's IDs on every panel.** A
  popup with `role="dialer"` draws the template's VTC Dialer, each key the
  popup's own control with its seed ID as its `id` - Dialer Keypad 0 to 9
  (5202 to 5211), * (5212), # (5213), Period (5228), VC Call (5214), Flash
  (5216), Contacts (5250), Keyboard (5229), Delete (5237) and the entry the
  program writes the number into (50000) - so a key keeps it on every page
  the 320 spreads the dialer over, where a derived control, keyed by its
  page, would take one of its own on each. The incoming call's
  answers (`topic="call"`) are the question's, from 50001, as the
  power-down question's are - not the template's 9032 and 9033, which each
  bar theme's README lists under *Differences* - and so are a recording's
  (`topic="recording"`, Afterburn's and Mach's), not the template's 9244 and
  9245.
- **A region page's mirrors share their control's ID.** Where a template draws
  one function twice and the program addresses it as one control - the
  Shockwave 1035's tab name under the tab's glyph (its frame's `twin`) - the
  region page draws the copy too: a derived `<name> Caption`, the tab's ID,
  `nav`, `does` and state names, on the panels whose template draws one, and
  listed as the tab's mirror (§2). Where another panel's problem stops the IDs
  being pinned, translate's spec check still holds the copy as its tab's, not
  as a control of its own.
- **Checked across panels:** one ID is one control - the same name, kind and
  state names (the map numbers a control's states once, so a source's tab on
  the 1035 and its Select a Source tile on a hub name theirs alike) - on every
  panel, and a control the canvas draws is on every panel: nothing is
  dropped. The one exception is named: what a panel's template has no place
  for - a hub's footer clock, the heading Mach's rail draws over its Settings
  group, the 320's clock and its popup region, the Center's or Afterburn's
  `PopupRegion` (each source is a page of its own there) - is listed in its
  page's `left` and named as a
  note by translate, and may be absent there. A mirror a layout derived does
  not excuse its control: the tab is held to every panel, the twin only to
  the panels that draw it.
- **Verified per build.** A built panel is one panel, so the verifier takes
  that panel's view of the map (`--panel`): its pages, popups, navigation and
  the controls on it, each where it is there.

## 8. A panel that was never a spec

A client project made in GUI Designer by hand has no spec to write a map from,
but its build holds everything a map lists but the functions:

```bash
python -m gdl.idmap from-built <panel.gdl> out/idmap
```

writes the same three files off the built `layout.json` - every ID, its type,
each page and control name it is at, its caption, a button's states and its
press state - and the page it boots into. What `layout.json` leaves out is
read from the project beside it: each popup's group, and a caption Build
flattened into the control's artwork, which leaves its text empty - 71 of the
Afterburn 1035 seed's 365 IDs. Its Function column is empty: a `.gdl` carries
no behavior (§1), so what each control does is the programmer's to fill in. A
control whose ID is 0 - what GUI Designer leaves on one nobody numbered, 98
controls in the client fixture, 59 of them buttons - is left out and counted,
since nothing can address it. An ID on several controls is one row, from its
first copy; where another copy differs in type, states or press state, the map
says which above its tables. A glyph caption in an icon face is the glyph's
name - `icon: close`, as the spec's map gives an `icon` - or its codepoint
where the face names none: its character is one a spreadsheet shows blank, as
on 30 of the Afterburn 1035 seed's controls.

Read off a panel built from a spec, it agrees with the map that spec wrote on
every ID, type, place and caption, and on every state the spec lists. A button
the spec gives no states keeps its clone's, which the built map names and the
spec's cannot; an icon the spec gives by codepoint is named by its glyph where
the face names one (`tests/test_idmap.py`). The project must have been built:
Save and Build writes the `layout.json` it reads.

## 9. A revision: the program keeps its IDs

A client often changes the canvas after the programmer has started. Without
help, every control without its own `id` is numbered again by its band (1001
up on the first page, 9001 up on the first popup, 50001 up for what a layout
derives, in name order). One control drawn ahead of another, or one page whose
Back sorts ahead of another's, renumbers everything after it. The program then
breaks silently: a press arrives on the wrong handler.

So a revision is translated against the previous delivery's map:

```bash
python -m gdl.design translate <canvas dir> out/huddle-r2 --previous out/huddle/idmap
powershell\New-GdlPanels.ps1 -Out out/huddle-r2 -Name Huddle -Previous out/huddle/idmap
```

`--previous` takes the previous delivery's `idmap` folder or its `idmap.json`.
For a single panel, `New-GdlPanel.ps1 -IdMap <dir> -Previous <map>` does the
same, and so does `python -m gdl.idmap write <spec> <dir> --previous <map>`.

**What keeps its ID.** Every control the previous map knew, matched by its page
or popup name and its control name (an unnamed one by the name the map shows),
on whichever panel it is. A control a layout derived is matched by the same
key, its page or popup and its name - and in a page or popup the layout
derived too, by the page that derived it and the layout's name for it (§7),
which the map records (`window`).

- **A designer's `id` still wins.** An `id` that is the ID a control still on
  the canvas keeps is refused, naming both. Copies the previous map gave one
  ID (a mirror) may pin it on one and keep it on the other.
- **A new control** takes a free number in its band that the previous map does
  not use. A page the map knew keeps its band, even with pages drawn in front
  of it since; a new page takes the first band no known page holds.
- **An ID whose control is gone is retired.** It is never handed to a new
  control, nor taken by the chrome's seed rule below. Each spec lists it
  (`_retired`), the spec's bands skip it, and the map lists it under *Retired
  IDs*, so every later revision keeps it out of use too. A program still
  addressing it reaches nothing rather than the wrong control.
- **A designer may pin a retired ID** on a control, and that is how a control
  that moved to another page, or was renamed, keeps the ID the program knows
  it by. The match is by page and name, so without the pin it is a new
  control. translate notes each one it can tell and the `id` to pin: a name
  now on another page and gone from its own (moved), or a control gone from a
  page that gained one of its type with the same `does` (renamed, perhaps).
- **The chrome's seed IDs** (§7) keep their rules: the chrome takes its
  template's ID where that is free. An ID the previous map holds is not free.
  A mirror still takes its control's ID.
- **Pages and popups keep their names.** A program shows them by name, so
  translate never maps one name onto another. A page that is gone, where a new
  one holds most of its controls by name, is reported as a note. The note says
  the page may have been renamed, that its controls are new to the program,
  and which `id` to pin on each one to keep it.
- **A hub's windows are named by the order of the working pages, and keep
  their IDs in any order.** A hub names the window each working page derives
  (Select Source, More Options) by its template, and after its own page where
  an earlier page derives one too (*Video Call Select Source*). Drawing the
  working pages in another order, or removing the earlier one, renames those
  windows, and a program shows each by its new name. What the hub draws in a
  window is known by the page that derived it and the template's name for it,
  so it keeps its IDs. A window whose page and name the map does not have is
  the window it was where one of three rules says so, and keeps what the hub
  draws in it:
  - one window of several pages (the Volume Level strip, two pages' alike
    Select Source) is the window of the page the map knew it by, whichever
    page is drawn first;
  - one the map had by the name it shows - the map's window of that kind and
    name, as a map keyed by name always knew it: the strip when the first
    working page is removed, the first page's Select Source when that page
    is renamed. So a page drawn where a removed one was, its window shown by
    that name, takes that window's IDs, as it always did;
  - a renamed page's window is the one the page derived under its old name,
    where it is the only window of its kind the map lacks and that the only
    one of its kind gone. A page is renamed where its controls are drawn on
    a page of another name, as translate notes it (*Pages and popups keep
    their names* above).

  Anything else is new: a page drawn since takes no window still drawn, nor
  a removed page's under a name of its own, and the IDs of what the hub drew
  in a removed page's own windows are retired. translate notes each
  renamed window with its old name and, where both pages are still on the
  canvas, the page to draw first again to keep that name; a control the
  hub no longer draws in it is retired, and the note says which.
  changes.md lists each as a *renamed window*, and a window gone with its
  page as that page's window, since its name may be another's now. Round
  four's Shockwave canvas drawn with its boards reversed keeps all 139 of
  its IDs, and its 525's Select Source and More Options are its renamed
  windows. Against a map that does not record `window` (one written
  before maps did), a window is known by its name, as that map knows it: the
  IDs of what the hub draws in a renamed one are retired - no `id` on the
  canvas pins them, since the layout draws them - and the note names them and
  the page order that keeps them.

translate ends with one line: how many IDs were kept, how many are new, and
how many are retired.

**What changed.** Written with the same map, the map has `changes.md` and
`changes.json` beside it. `python -m gdl.idmap diff <old> <new>` prints the
same report for any two maps. It exits 0 when a program needs no change and 1
when it does. The report covers:

- panels added or gone;
- pages and popups added, removed, renamed, or shown the other way (page or
  popup); a hub's window renamed by the working pages' order (a *renamed
  window*: the same window, every control in it at its ID, and each control
  that shows it now showing it by its new name, a function changed), and a
  window gone with its page named as that page's; a popup made modal or put
  in another group, which changes what ShowPopup does with it; a page or
  popup the program is now to show on its own, as on an incoming call
  (`reached_by: program`);
- controls added or removed, given another ID (`renumbered`), moved to another
  page or renamed under a new ID (a rename is one gone and one come on a page,
  of one type and the same states and function), or whose ID is now a
  different control (`reassigned`: another name, and another place, type or
  function, or its old name under another ID). That last is what a revision
  translated without `--previous` can do: a control drawn where a moved one
  was takes its number, and the program's handler for the old control fires
  for the new one;
- a control whose type, states, press state or function changed, or that is
  on other panels than it was. A state list matters to a `SetState` program: a
  state put in front of another moves every index after it.
- a control on another page or popup under the same ID (`relocated`). The
  program still addresses it by that ID, but the control is up only while its
  new page or popup is, and the program is what shows that.
- what needs no change: a caption, a control renamed under its ID (doing
  what it did), a page's purpose, the page the panel boots into, a page or
  popup no longer marked `reached_by: program`.

It opens with a one-line verdict, either *A program written against the
previous map needs no change*, or what it needs. A map of every panel is
compared panel by panel, over the panels both maps have: a panel added or
gone is said once, not as a change to every control whose function differs
there. A change on some panels names them.

Every spec a revision writes records the SHA-256 of the map it kept IDs
against (`_previous`). The hash is of what the map says, not its bytes, so a
delivery that came back through Windows re-saved with CRLF line ends or a
BOM is still that map. `gdl.idmap write`, `write-panels` and `check` refuse a
`--previous` map other than that one, because the changes would describe the
wrong delivery. Without `--previous` they write the map and note that it can
take one.

A map of one panel names its panel (`model`). Compared with a previous map of
several, which is what `New-GdlPanel.ps1 -IdMap -Previous` does with one
panel of a canvas of several, it is compared with that map's view of its own
panel. The report says so and says nothing of the other panels, which are not
gone. A map of one panel that names none is taken as the panel the canvas is
drawn on, the first.
