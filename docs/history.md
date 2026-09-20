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
  item — the plain thing — works, and `seeds/Afterburn ECP 16-9 (Project1).gdl`
  was made that way with no hands on the mouse. Making a seed is no longer a
  step that needs a person.
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
- **Modal popup references are one per modal popup, not one per page plus one.**
  Corrected twice. The first correction ("one too many on 19 of 20 built
  projects") still failed the one project with `EnableOfflinePage` on; the rule
  counts the Offline Page only when it is enabled. See `docs/gdl-format.md`.
- **Group registration was never missing.** An early gap list said it was;
  `Register-GdlPopupGroup` was complete all along.
- **`rename` wrote only state 0** until `7b3e630`, so a renamed button showed
  its old caption once switched On. `docs/ROADMAP.md` *Mine* #4 covers
  re-verifying anything edited before that commit.
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
  `PBStates.Count`, which reports 1 for an Off/On button.
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
