# History

Where the project's dated narrative lives, so the instructions elsewhere can
stay in the present tense.

Nothing here is needed to use the toolkit. It exists because several of these
entries are corrections — a claim in the docs was wrong, cost time, and was
fixed — and knowing a belief was *revised* is worth keeping even when the
revised belief is all you need day to day. The rule for this file: if a passage
says what is true now, it belongs in the live docs; if it says what used to be
believed, or which machine something was measured on, it belongs here.

## Where the work has run

The toolkit has been developed across several setups. None of them are
requirements; the only environment split that matters is whether GUI Designer is
installed (see `CLAUDE.md`, *Where to work*).

- **macOS host driving a Parallels Windows 11 guest.** Retired. Commands went
  through `prlctl exec "Windows 11" --current-user ...` — `--current-user` being
  essential, since without it the command ran as `nt authority\system` with
  `UserInteractive = False` and anything drawing a form died. The host
  filesystem was reached at `\\Mac\Home\...` because a mapped drive letter is
  per-interactive-session and invisible to `prlctl exec`. `prlctl capture` read
  the screen. The durable lesson — authoring is headless, anything that draws
  needs a real interactive desktop — is in `docs/from-scratch.md` §7.
- **A Claude Code Linux cloud container**, and **macOS natively**, both of which
  reproduced `tests/baseline.json` exactly. This is why the render half carries
  no platform-specific code.
- **Windows natively, with GUI Designer installed.** The current arrangement,
  and the only one where author → build → verify is a single loop.

An earlier working assumption, now dropped, was that the Windows machine was a
scarce shared resource, which justified batching plans into one trip and
carrying two files across a boundary. It is not true when GUI Designer is on the
machine you are already working on.

## Migrations

- **2026-09-10/11** — the Windows host was about to be reimaged, so everything
  the project had on its `C:` drive was moved into the repo: the seed projects
  into `seeds/`, the build scratch and job scratch into `archive/`, that
  session's measurement scripts into `research/`, Extron's templates and icon
  kit into `vendor/` (manifest only — the bytes are reinstallable), and the
  Claude Code transcripts and memory into `archive/claude/`. Login tokens were
  deliberately not copied.
- **2026-09-11** — re-cloned to a local disk after the reimage. Paths of the
  form `Z:\GitHub\...` in older commits and transcripts refer to the previous
  mounted-drive checkout and no longer resolve anywhere.
- **2026-09-17/18 — GUI Designer 1.27.0.9 → 1.28.0.7.** The first version
  change the toolkit has been through, so it is also the first evidence of what
  an upgrade does and does not break.

  Nothing in the format moved. A 1.27-authored `ProjectGCP` still deserializes,
  because `Initialize-Gdl` resolves assemblies by simple name and ignores the
  version — which matters, since `Extron.GUICPro.Layout.Contracts` went
  **4.22.0.0 → 5.6.0.0** and `GUI Designer.exe.config` carries no binding
  redirect for it. Output written under 1.28 is restamped `1.28.0.7` /
  `5.6.0.0`, so files this toolkit writes are probably not openable in 1.27;
  that was not tested, because 1.27 was gone. `pytest` was unaffected (157
  passing before the upgrade, 157 after), the authoring example ran clean, and a
  real Liberty Bank project opened with no conversion prompt and rebuilt twice
  with identical page, control, border and font counts.

  Two catalogue changes, both invisible to a count check because they cancel
  out at 60 enum members and 55 platforms: **CCI700 was removed** (its integer
  slot, 19, is now an orphaned gap, and the hardware is discontinued) and
  **VTLPEcp — Extron Control Pro — was added**. Extron's release notes list only
  two features, Dynamic Images and ECP theme support; everything else here had
  to be found by reflection and diffing.

  The upgrade's actual cost was none of that. It was a *Save and Build
  Optimization* modal on the first build, which blocked an unattended run for
  the full 900-second timeout with no diagnosis. The preference behind it is
  long-standing; what fired it was that `user.config` is per-version, so the
  upgrade reset it to its "ask" default. The live warning is in
  `docs/from-scratch.md` §7.

  One belief corrected on the way: the Project Create Wizard is no longer
  entirely opaque to UI Automation. See *Corrections worth remembering*.

## Corrections worth remembering

Each of these was believed, written down, and later found wrong. The current
statement is in the live docs; this is the record that it changed.

- **The Project Create Wizard cannot be automated.** Twice wrong, in different
  ways. The original claim, true of 1.27.0.9, was that its descendant tree came
  back empty — zero combo boxes, zero buttons. In 1.28.0.7 the tree is populated,
  so that reason expired. The *replacement* claim, written the same day, was that
  it still could not be driven because nothing committed a selection. That was
  wrong too, and for an avoidable reason: the first thing tried was
  `ValuePattern.SetValue`, which desynchronises the combo from the model and
  poisons the dialog for everything after it. Every later attempt was measuring
  the damage from that, not the wizard. Expanding a combo and clicking the list
  item — the plain thing — works, and all six `seeds/*ECP*.gdl` were made that
  way with no hands on the mouse. Making a seed is no longer a step that needs a
  person.

  A second trap sits behind the first. Step 2's Theme and Application combos
  populate by themselves once a themable resolution is picked, so the wizard can
  read `Theme: Mach` while `Blank` is still the selected radio, with Create
  enabled either way. Two seeds were built blank before anyone checked the page
  count. The radios expose no toggle state, so there is nothing to assert
  against — only a screenshot, or the built result.
- **`gdl/edit.py` annotated each retarget plan with a `platform_class`.** It was
  `f'Extron.GUICPro.PB{model}Platform'`, which is wrong for 9 of the 55 models
  (TLP720T is `PBTLP720TVPlatform`; TLP1230WTG is the bare
  `PBTouchPanelPlatformPro`). Nothing ever read it — the applier resolves the
  class through `Enum.Parse` + `CreatePlatform` — so it was removed rather than
  corrected.
- **`gdl/spec.py` wrote three PBSlider fields that do not exist.**
  `sliderTrackWidthField` / `sliderIndicatorWidthField` /
  `sliderIndicatorHeightField`, authored before the code had ever run against a
  real install. The real names carry no `Field` suffix —
  `sliderTrackWidth` / `sliderThumbWidth` / `sliderThumbHeight`. Two things made
  it survive: `Set-GdlFieldIfPresent` warns and continues, so a slider just
  built at the donor's dimensions; and there are **two** `PBSlider` types, so
  reflecting over the wrong one (`Extron.GUICPro.Layout.Data.PBSlider` in
  Layout.NET, where they are auto-properties with `k__BackingField` names)
  produces a confident, equally wrong answer. The authoring graph holds
  `Extron.GUICPro.PBSlider` from `GUI Designer.exe`.
- **Arial is embedded in the fixtures.** The docs previously said the opposite —
  that Arial and Arial Black were system faces the format merely referenced.
  `fonts.extract()` matched a declared size against the measured sfnt length
  exactly, and both faces carry bytes past the end of their last table (28 for
  Arial, 30 for Arial Black), so neither ever matched. `tests/test_fonts.py` is
  the gate that was missing. See `CLAUDE.md`.
- **…but "every declared face is embedded" is not true of every project.** Found
  by `tests/audit_corpus.py`: a fresh project declares Arial Black without
  embedding it. `docs/ROADMAP.md` *Mine* #2.
- **Generated popups and start pages were assumed to work because the builds
  were clean.** Three silent failures sat behind that, found when the behavior
  layer first needed them:
  - The applier wrote `modalField = false` on every popup, so a modal
    confirmation built as an ungrouped standard popup that nothing could show.
  - A generated panel kept the donor's start page.
  - Every popup reference authored from a **seed** was discarded by Build. The
    clone inherited the reference's own `modalField = True` from one of Build's
    modal references, and Build then treated it as its own. The Liberty Bank
    donor, whose first reference is a group reference, hid it in every earlier
    build.

  `docs/gdl-format.md` §5 and §7 have the rules; `tests/verify_built.py` checks
  the first two.
- **Page numbers were treated as addresses.** A spec's page `number` is written
  to `userIdField`, but Build reports every page's `UserId` as its `ID`, so
  pages and popups are addressed by name.
- **Two unnumbered popups shared control IDs.** Their default numbers were 9000
  and 9001, so the second popup's ID band started inside the first's, and
  `check()` never looked inside popups for duplicates. Allocation is now
  project-wide.
- **"No ECP seed declares Arial Black"** stood in `seeds/README.md` for the
  first days of the ECP seeds. Every ECP seed declares it, like every other
  seed; the six ECP rows had been read from `ProjectGCP`'s font resources while
  the other rows came from `layout.json`. The real fact behind the mismatch: no
  seed at all has a font resource for Arial Black.
- **Modal popup references are one per modal popup, not one per page plus one.**
  Corrected twice. The first correction ("one too many on 19 of 20 built
  projects") still failed the one project with `EnableOfflinePage` on; the rule
  counts the Offline Page only when it is enabled. See `docs/gdl-format.md`.
- **Group registration was never missing.** An early gap list said it was;
  `Register-GdlPopupGroup` was complete all along.
- **`rename` wrote only state 0** until `7b3e630`, so a renamed button showed
  its old caption once switched On. The verifier compared only the merged
  caption, which is state 0's, so it never noticed. On 2026-09-24 the worked
  edit (`examples/edits.json`) was rebuilt under a verifier that checks every
  state an edit writes: all nine plain renames correct on both states.
- **Then `rename` wrote one caption to every state, and `restyle` matched only
  a control's own colors** (until 2026-09-24). A button whose states said
  different things lost its feedback wording. 288 of the Liberty Bank
  fixture's 442 buttons keep their fill only on their states, so `restyle`
  matched none of them - and one it did match got the control's new color on
  every state, On included. Nothing was reported, and the verifier never
  checked an edit's colors at all. Both now edit state by state, and colors are
  read off the built artwork.
- **The Liberty Bank fixture was thought to deviate from Afterburn's modal
  scrim.** Its modals are black at alpha 166 where the guide says `#242634` at
  20% transparency. On 2026-09-24 every modal in three seeds, and one built from
  a spec with a `#242634` background, turned out the same: Build draws the scrim
  itself.
- **A spec control with no stroke kept its donor's** (until 2026-09-24). The
  applier skips a color it is not given, so a panel with no `stroke` built with
  the seed's `#6A6E89` outline while the preview drew none. Found by putting a
  Claude Design canvas beside the panel built from it; no stroke is now written
  as transparent.
- **A button state with no fill kept its donor state's** (until 2026-09-24),
  as the stroke had. The Afterburn seed's On state is `#37394E`, so the first
  build of the icon canvas put a raised slab behind every kit image after
  state 0 - caught by the new check of each state's image against its
  artwork. A button with no fill is now written transparent. The same build
  showed a slider thumb still the seed's periwinkle under the Grape theme (it
  is a kit image, and nothing set it) and a left-aligned clock built centered
  (the component left `align` out when it was `left`, and the spec's default
  is `center`).
- **`Invoke-GdlMenu.ps1` waited a fixed 3 s for the File menu** (until
  2026-09-24). The menu is expanded by a background PowerShell job that has to
  start first; on a busy machine the item was not there yet, the build fell
  back to SendKeys, and that could not take the foreground from a minimized
  Remote Desktop session. It now polls for the item.
- **A spec clock kept its donor's format** (until 2026-09-24). The format is
  `PBDateTime.patternField`, which nothing wrote, so a "date" and a "time"
  clock both built as the Afterburn seed's `September 28, 12:00 AM`. The
  verifier caught the caption; the pattern is now written and checked.
- **The first Afterburn design system misread the theme** (2026-09-24, caught
  by the user): a slider drawn as a filled slab where Afterburn's is a 10 px
  rail with a `#BABCCE` fill and a periwinkle thumb; `accent` used as a button
  fill, where the guide keeps it to selection lines and the seed to active
  captions; a panel with no `#6A6E89` outline. Corrected against the seed's
  built artwork, which is now how every template's profile is checked.
- **Afterburn's design system colored captions red, and drew no icons**
  (until 2026-09-24, caught by the user). Its `alert` token was read as a
  caption color off the seed's two record buttons - whose captions are empty;
  the red is their icon's - and a mute or End Call turned its caption red. The
  guide has no red at all: Afterburn shows state with kit icons in the accent,
  and an alert is a red fill with a white caption. Icons had been left out
  pending a decision on putting Extron's artwork in claude.ai; the owner agreed
  to downscaled kit images in their private design system, and every image
  button is now drawn from the kit as the seed draws it.
- **The six-color check counted only colors a spec names, and only on pages**
  (until 2026-09-24). A caption with no `color` draws in the theme's text
  color, and popups are on the panel too. `examples/huddle-functions.json`
  passed at six while it drew seven; it dropped `muted` to meet p.49.
- **A line can be diagonal.** An early draft of `docs/from-scratch.md` said
  otherwise; `PBLine`'s endpoints are an eight-value enum over an arbitrary
  bounding rect, so the angle is arbitrary too.
- **Icons are not only font glyphs.** An earlier draft overcorrected to "icons
  come from a font, not images". Both routes work.
- **Panel model names must be read from GUI Designer's shipped list**, not
  reconstructed from internal class symbols — class names outlive retired
  models and will mislead you. See `docs/design-rules.md`.
- **The build-completion signal is the `.gdl`'s own mtime.** The title bar's
  trailing `*` only means unsaved changes, and the Build Manager window appears
  after the menu click and closes before the file is written. A doc revision
  once named the Build Manager window as the signal while the script was already
  correct.
- **`New-GdlPanel.ps1` does not need the foreground.** Its header described the
  original SendKeys implementation long after the script had moved to UI
  Automation.
- **`Wait-GdlBuild.ps1` must be given a baseline captured before the build is
  triggered.** Sampling it afterwards is a race: the trigger blocks on the build
  modal, so on a fast enough machine the watcher starts with the post-build
  mtime already in hand and waits out its full timeout, reporting a successful
  build as a failure. Fixed by `-Since`.
- **`vendor/`'s repopulate command needed its destination created first.**
  `Copy-Item -Recurse` copies a folder's contents rather than the folder when
  the destination does not exist, so on a fresh clone — the exact case the
  instructions were written for — the templates landed one directory too high.
- **`Apply-GdlPlan.ps1` set no font until 2026-09-08.** Every label built at the
  donor's 20pt, every button at 13pt, every shape at 14.25pt, whatever the spec
  said — while `gdl.spec check` enforced Extron's ≥14pt rule against the *spec*,
  a number that never left the file. Hence the rule in `CLAUDE.md`: verify
  against the built result, not the plan.
- **Both appliers wrote only state 0 until 2026-09-10**, because they looped to
  `PBStates.Count`, which reports 1 for an Off/On button. The reason given then
  - that it is a "logical count" - was wrong. `PBStates` has no `Count`;
  PowerShell 5.1 answers 1 for any object without one, so it reads 1 for every
  button whatever its state count (disassembled 2026-09-23).
- **Press feedback was written up as "barely used"** from the -1 on 7320 of
  7392 *per-state* `<TLPPressFeedbackStateID>` fields. The one that matters is
  the button's own, which is a real state on every button in the corpus - On
  for an Off/On button. Corrected 2026-09-23.
- **A cloned button was thought unable to gain a state** without constructing a
  `PBState`, so a spec could ask for no more states than its donor button had.
  `mItems` is an ordinary `List<PBState>`; appending a clone of the last state
  builds, proven on GUI Designer 1.28.0.7 on 2026-09-23 (`docs/gdl-format.md`
  §7).
- **Re-serializing a project was once thought byte-identical**, and the
  difference then put down to "lazily-built state". Measured on 2026-09-07, it
  is every `TLPImageID` reset to -1 (`docs/gdl-format.md` §3).
- **Color fidelity sat in `docs/from-scratch.md`'s limits** for longer than the
  bug was alive: `bf0fe8b` fixed it, and it was re-verified off the built
  artwork on 2026-09-08. `tests/verify_built.py` has checked it since.
- **One seed per theme was thought enough**, on the grounds that `retarget`
  covers the other sizes. It builds correctly, but matches Extron's own
  hand-authored layout at another size for only 22% of controls
  (`docs/editing.md`).
- **Touch-target minimums were keyed off resolution.** DPI is per model, and
  varies 1.76x within 1280x800 alone (`docs/editing.md`).
- **The fixture docs said a popup's authored size is always the whole canvas.**
  True of every Liberty Bank popup and false of Extron's own Afterburn template,
  where 10 of 29 are authored — and built — at 880x525.
- **`renumber` was described as verified end to end** alongside the other three
  edit operations. Its own table in `docs/editing.md` always said "planned +
  checked"; it has never been through a build.
- **"Eight resolutions across 63 panel models"** stood in `CLAUDE.md` while
  `MODELS_FULL` held 55 and a seed built at 1920x720, a resolution the table
  lacked. `docs/design-rules.md` §1 is now the one list.
- **`docs/from-scratch.md` gave the `_alt 2_0_0` fixture 32 border resources** in
  one section and 34 in another. It has 34.

## Dated facts moved out of the live docs

- **Seeds** were made by hand on 2026-09-09; the 835 seed a day earlier (it was
  recovered from the Recycle Bin on 2026-09-10).
- **Both bug-hunt runs** died on a host with 8 GB of RAM and a pagefile pinned at
  500 MB — an 8.5 GB commit limit, of which six Claude processes already held
  about 2 GB.
