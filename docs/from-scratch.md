# Building a panel from scratch

Can you design an Extron touch panel as an artifact — a spec, a mockup, a
generated layout — and turn it into a real `.gdl` that GUI Designer opens and
builds? Yes, and this is how.

**Short version.** The design space is wide. *Build owns the artwork* is real,
but: the canvas is set by the panel model rather than fixed, lines can be
diagonal, ~339 icons are
available as font glyphs needing no image resource, new border resources can be
appended (§5), and Extron ships per-panel `.glt` template libraries to clone from.
`docs/design-rules.md` holds Extron's own rules, separated from what we guessed.

## 1. What actually bounds the design space

An authored control carries `TLPImageID = -1`. It has no artwork. What it has is
a fill color, a stroke color, and a **named** border resource that supplies
the silhouette. GUI Designer rasterizes those on Build. So a generator never
makes pixels; it names resources and sets colors.

The obvious reading of that is that a
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
| style | 2D flat (0), 3D beveled (1) |
| corner radius | 0, 5, 10, 14, 999, 9999 (9999 = capsule) |
| thickness | 0, 1, 2, 3 |
| 3D lighting | `depth`, `surfaceHeight` (3, 78, 117) |

The six Afterburn resources are **not** clones of the System templates, which
is more interesting than if they were. Every one carries `style = 0` (2D flat)
together with `depth = 1, surfaceHeight = 3` (the 3D lighting values) — and no
System template has that combination: every System `style = 0` record has
`depth = 0, surface = 0`, and every record with `depth = 1, surface = 3` has
`style = 1`.

So a human, working in GUI Designer's own UI, produced border resources with
parameter combinations that ship with no template. §5 confirms the stronger
version: a **hand-appended** resource with out-of-corpus values also survives a
build.

**The consequence that matters:** a generator that only *references* resources
already in a donor project needs no new resource appended.

Worth knowing how narrow the corpus evidence was: across all six fixtures only
**9** distinct border names are ever bound to a control, and ~25 — including
*every* 3D template and every `zGD - Default *` — are defined but never
referenced. §5 tested one of those unreferenced names directly and it built
clean, so the usable palette is the full **34**, and appending more works too.

## 2. What is free, what is bounded, what is impossible

**Free.** Layout and hierarchy, page and popup structure, ID allocation, exact
fill/stroke/text color (any ARGB), typography within the embedded faces, and
which border resource each control uses — all 34, confirmed in §5.

**Bounded — less than expected.** Silhouette is
rectangle/rounded/capsule/ellipse × flat/3D. A new radius means a new resource,
and §5 showed appending one works, so this is bounded by the shape *family*
rather than by the resource list.

**Impossible without new resources, and possibly impossible at all.**

- `PBLine` cannot be **freehand or polyline**. Its `startPoint`/`endPoint` are an
  eight-value enum (TopLeft, TopCenter, TopRight, MiddleRight, BottomRight,
  BottomCenter, BottomLeft, MiddleLeft) plus start/end caps and thickness — so
  TopLeft→BottomRight *is* a diagonal, and since the bounding rect is arbitrary so
  is the angle.
- Canvas size is set by the panel model, **not fixed** — `docs/design-rules.md`
  §1 lists the resolutions. The fixtures are all 1280×800, which is a property
  of this client's hardware, not of the format.
- Arbitrary raster art: unless the bitmap is already a `PBImageResource` it needs
  the resource-append step (which §5 showed works). But note this is rarely the
  binding constraint — ~339 icons are available as *font glyphs* and need no image
  at all. See `docs/design-rules.md` §6.
- Gradients beyond what `depth`/`surfaceHeight`/`lightAngle`/`lightBrightness`
  produce.

## 3. The pipeline, and what exists today

| Stage | State |
|---|---|
| Design artifact → spec | **Built.** `examples/panel.json` is a worked spec. |
| Layout pass | **Built.** `gdl/spec.py` `grid()` / `stack()`. |
| Control ID allocation | **Built.** Per-page bands, honors pinned ids. |
| Preview render | **Built.** Straight through `gdl/compose.py`. |
| Spec → build plan | **Built.** `python -m gdl.spec plan`. |
| Plan → `ProjectGCP` | **Built and verified.** `powershell/Apply-GdlPlan.ps1`; `-WhatIf` dry-runs it. |
| Repack to `.gdl` | Built already — `gdl/container.py pack`. |
| GUI Designer opens + builds | **Verified**, and scriptable from the host (§7). |

Popup groups need nothing more: `Register-GdlPopupGroup` is a complete
implementation of the only group concept the format has — a class census finds
exactly five `PBControlGroup` instances across the whole corpus, all of them
popup-page groups.

## 4. The preview is the point

Building is the slow step — apply, pack, open, Save and Build, verify. The
compositor is scored against GUI Designer's own snapshot exports
(`tests/baseline.json`), which makes it good enough to judge a design *before*
building it:

```bash
python -m gdl.spec check  examples/panel.json     # ids, off-canvas, sizes, unknown resources
python -m gdl.spec render examples/panel.json out/preview.png
python -m gdl.spec plan   examples/panel.json out/plan.json   # ops for the applier
```

![generated panel](panel-preview.png)

That image is a panel that has never existed: 28 controls, every rect computed
by the layout pass, every id allocated, rendered by the same code path that is
measured against ground truth. §5b shows the same spec after GUI Designer has
actually built it, which is the proof; this is the cheap check you run first.

The preview is honest about what it is drawing: every control is emitted with
`TLPImageID = -1`, exactly as an authored control is before Build, so the
preview draws from the same fill-plus-named-border properties a writer would
set.

## 5. Tested against GUI Designer 1.28.0.7 — results

Each test project was authored **headlessly** by PowerShell, packed with
`gdl.container pack`, then opened and built in the real application. See §7 for
how that was driven, which is fully scriptable.

The error and warning counts below were read off 1.27.0.9. `New-FormatProbes.ps1`
was re-run on 1.28.0.7 and all three still author, open and build, each producing
a payload; probe 2's appended resource is still in the built file afterwards (35
border resources against the fixture's 34). The counts themselves were not
re-read from the Build Manager, so treat "0 errors, 0 warnings" as the 1.27
measurement and "builds and keeps the resource" as the 1.28 one.

| | Question | Answer |
|---|---|---|
| 1 | Reference an existing but never-referenced border resource? | **YES** |
| 2 | Append a *new* `PBBorderResource` and bind to it? | **YES** |
| 3 | Out-of-corpus `PBBorderInfo` values? | **Builds clean** (visual check still open) |
| 4 | Cross-graph `Copy-GdlObject`? | **YES** |
| 5 | ID / name uniqueness enforcement | **NAMES yes, hard error**; ids untested |
| 6 | `referenceCountField` semantics | not yet tested |

**1 — referencing an unused resource works.** A `PBShape` was repointed from
`Afterburn - 10 Radius 0 Thick` to `3D Capsule`, a System template no control in
any fixture binds. GUI Designer opened it and built with **0 errors, 0
warnings**. So §1's conclusion holds: the usable palette is all **34** defined
resources, not the 6 this project happens to reference.

**2 — appending a new resource works, so the design space is fully
parametric.** A `PBBorderResource` was cloned, renamed
`Claude - 20 Radius 1 Thick`, given `cornerRadius = 20` and `thickness = 1`
(a combination present nowhere in the corpus), appended to
`resourceSetField.resourcesField` with `.Add()`, and bound to a control. It
opened, built with 0 errors, and the new resource **survived into the built
file** — still present, still bound, verified afterwards with `gdl/project.py`.

This was the biggest open question and it is the more permissive answer: a
generator is not limited to a donor's existing resources.

**4 — cross-graph cloning works.** A control was cloned out of one
independently-deserialized project into another with `Copy-GdlObject`, and the
result opened, built clean, and rendered correctly (the cloned popup reference
paints its group member, per render finding 3). A curated component library in a
separate `.gdl` is therefore viable.

**5 — page and popup names must be unique project-wide.** Found the expensive
way. The worked example's two popups were named `2210 - Conference Volume` and
`2220 - CATV Volume` — perfectly sensible names, and unique *within the spec*.
But a generated panel joins the **donor's** project, and the Liberty Bank donor
already had both. Build rejected it:

    2210 - Conference Volume   Duplicate page or popup page names are not
                               allowed within the same project.
    2220 - CATV Volume         Duplicate page or popup page names are not
                               allowed within the same project.

Two errors, no payload. Points worth keeping:

* Pages and popups share **one** namespace — a popup may not take a page's name.
* It is a **build** error, not a load error. GUI Designer opened the file
  happily and showed both duplicates in the workspace tree, so "it opens" says
  nothing here.
* The **name** is the only identity that matters. Page "number" (the `2210 -`
  prefix) is a naming convention, not a field: `PBPage` has no number, and the
  fixture's own names are just numerically prefixed strings.
* Numeric `idField`s were duplicated across projects throughout this work with
  no complaint, so whatever uniqueness ids need, it is not this one.

`Panel.check_donor()` compares spec names against the donor's before anything
is built, and `Panel.check()` catches a spec that collides with itself. Renaming to `2310 - Program Volume` / `2320 - Speech Volume` cleared it:
the build emitted `generated9.tgz4` with 207 PNGs (a failed build emits none),
661 of 698 controls rasterized, and both popups came through with their own
captions.

**And the file was still wrong** — see the next finding, which is the more
important one.

**A control that does not fit its page is moved to 0,0. Silently, at build
time, with the build still reporting success.** The clean build above was
checked by rendering it, and one button was missing from each popup. Reading the
built `layout.json` back:

    2310 - Program Volume  (page is 915x800)
        Mute     256,24  164x60
        -        436,24  164x60
        +        616,24  164x60
        Presets    0,0   164x60     <- planned 796,24

Every relocated control is exactly one whose right edge passed **915** — the
donor popup's width. The applier sized nothing, so each cloned popup kept the
donor's dimensions while the spec laid its controls out across 984. Note what
survived: the width and height are the planned ones, only the position was
rewritten, so the object is not corrupt and nothing in the file says it was
touched.

Consequences worth keeping:

* **A popup's size must be authored** (`widthField` / `heightField`; both
  `PBPage` and `PBPopupPage` carry them). A clone inherits the donor's, and the
  donor's is arbitrary.
* **"It built with 0 errors" is not a correctness check.** This is the second
  trap of this shape after `flattenText`, and both produced a file that opened,
  built and was wrong.
* So the loop now ends with `python tests/verify_built.py <plan.json>
  <built.gdl>`, which reads the plan and the built file and asserts every
  authored control's rect and caption. It reproduces this defect exactly and
  reports 0 problems on the fixed build.

**What Build adds by itself.** The generated page came back with 35 controls
against 29 authored, which looked like clone contamination and is not: Build
adds one full-canvas `PBPopupPageReference` per **modal** popup to **every**
page, the Offline Page counting only when `EnableOfflinePage` is on — and the
donor has seven modal popups, one of them a switched-off Offline Page. Every
donor page carries the same six. The verifier ignores unauthored extras for this reason.

`Project > Verify` is not the build, and `BuildProject()` cannot be called
headlessly — `docs/gdl-format.md` §2 has both. §7 is how the real build is
driven.

## 5b. The whole loop, closed

`examples/panel.json` was taken end to end:

    spec -> layout pass + ID allocation -> build plan -> Apply-GdlPlan.ps1
         -> ProjectGCP -> gdl.container pack -> GUI Designer -> Save and Build

GUI Designer opened it and built with **0 errors, 0 warnings**, producing a page
of 34 controls with 28 rasterized assets. `docs/generated-built.png` is that
page rendered from GUI Designer's *own* built payload — not a preview:

![generated and built](generated-built.png)

Every rect came from `grid()`/`stack()`, every id from the allocator, every
caption from the spec.

Three defects had to be fixed along the way, all of them the same shape - a
clone inherits things you did not ask for:

1. **The page kept the donor's page-level artwork**, which painted underneath
   everything. Clear `<TLPImageID>` on the cloned page.
2. **Buttons kept the donor's icon.** Clear `buttonImageField`.
3. **`flattenText` bakes the caption INTO the artwork at build time**, and the
   clone inherited it - so Build deduplicated all five nav buttons to a single
   asset carrying the donor's word "Audio", with the correct captions sitting
   unused in `layout.json`. Set `flattenTextField = false` and the firmware
   draws captions live, which is what it does for hand-authored panels anyway.

That third one is worth remembering: the file was *correct* the whole time -
`layout.json` had the right text - and only the rendered artwork was wrong.
Checking the model would have said everything was fine.

Color is checked the same way, off the *built artwork* rather than the model,
because a built control's `BackgroundFillColor` reads back transparent white
whatever was authored. On this panel 21 of 21 planned fills are the plurality
color of their own rasterized asset — the accent button at 87% `#3D8BFD` — and
the page artwork is 100% `#12131C`, with no trace of the donor's.
`tests/verify_built.py` makes that a gate on every build.

## 5c. Authoring without a client project: seeds

Every generated panel so far clones `fixtures/gdl/Interface__alt_...Liberty_Bank...`,
which is a **real client project** for job J26450039. That is fine for testing and
wrong for delivery: the result inherits that client's page names, popups,
resources, artwork and retail fonts, and is pinned to their model and theme.

The obvious fix is to clone one of Extron's own templates instead. There are 50
of them under `GUI Designer Templates\TouchLink Templates` in the shared
Documents folder, they are the same `KP`-swapped container, `Project.open()`
reads all 50, and they cover six theme families across Extron's panel sizes.
(1.28 added six: Afterburn, Mach and Shockwave each gained an ECP 16-9 and an
ECP 16-10 variant. They are new sizes inside existing families, not a seventh
family.)

**It does not work, and it fails quietly.** Measured against
`Afterburn 1020 Series.glt`:

- `gdl.spec donors` was happy — every control type resolved.
- `Apply-GdlPlan.ps1` applied all 16 ops and wrote a 3.4 MB ProjectGCP.
- `gdl.container pack` produced a 1.7 MB `.gdl`.
- GUI Designer opened **empty** and showed the Project Create Wizard.

A `.glt` has no `PBProject`. It is a library of pages, popups and resources with
no project wrapper, so there is nothing for GUI Designer to open and it offers to
make a new project instead. From outside, that is indistinguishable from a hang —
the pipeline waited its full 180s for a window title that was never coming.
`Panel.check_donor` now catches this in about a second, and `New-GdlPanel.ps1`
says what a missing window probably means.

`pack()` no longer requires a payload member, which is worth keeping on its own:
a `.glt` has none, and neither does a `.gdl` saved without building. The result is
a ProjectGCP-only container, which GUI Designer opens and builds happily — the
payload is Build's *output*, not its input.

### Making a seed

The project wrapper has to come from GUI Designer. `PBProject` cannot be
constructed headlessly any more than a `PBPage` can, and a template has none to
clone.

So, once per theme:

1. **File > New Project...**
2. Step 1, pick the panel — ideally the size you will deliver on (see below).
3. Step 2, choose **Theme**, then the theme, project font and application.
4. **Create**, then save it into `seeds/`. That file is the seed.

Then pass `-Donor "seeds/<seed>.gdl"`, and nothing of anyone else's is in the
output.

`seeds/` holds fourteen: Afterburn at five sizes, Mach at
three, Shockwave at two, Turbulence, both Zoom Rooms ZRTP variants, and the 835
seed below. `seeds/README.md` lists each one's model, canvas and resources. They
are in Git LFS, so run `git lfs pull` on a fresh clone.

**Prefer a seed at the target size; retarget is the fallback.** A retarget
builds correctly — 654/654 on the Liberty Bank fixture, 650/650 on the Afterburn
1035 seed taken to a 1535M. But scored against Extron's *own*
hand-authored 1535, only 22% of controls land identically, median 18px off. The
rule is the same per-axis scale Extron used; the difference is their designers
nudging by hand, which a native-size seed carries and a retarget cannot. See
`docs/editing.md`.

### A seed works, end to end

Against a seed made by hand in about a minute (File > New Project, Afterburn
All-inclusive 1220 theme, TLP Pro 835M), now `seeds/Afterburn 835 (Project1).gdl`,
`examples/multipage.json` went through `New-GdlPanel.ps1` unattended:
three pages, 39 authored controls, **built and verified with 0 problems**, and
nothing of any client's in the result.

Two things that seed taught, both now checked by `gdl.spec donors`:

- **A fresh themed project defines a different resource set from a client
  file.** It has 31 border resources and the fixture has 34, but they are not
  the same list. And its only font resources are Arial, Extron-Afterburn and
  Open Sans - so the spec's `Forma DJR Display`, inherited from the Liberty Bank
  fixture, had no resource to resolve against. That does *not* fail the build:
  `Set-GdlFont` correctly leaves the donor's face, the panel builds clean, and
  it ships in Open Sans. Only `tests/verify_built.py` noticed, 14 controls deep.
- **The spec's `model` is not the panel's model.** The built panel is whatever
  the donor is - this seed is an 835M - and `model` only feeds the touch-target
  check. A spec whose canvas differs from the donor's is now refused.

### Automating the wizard: it works in 1.28

**This changed in 1.28 and the old advice here was "it exposes no UIA providers
at all".** That is no longer true. The wizard's descendant tree is now populated:
the Panel Type, Theme and Application combo boxes expose `Value` and
`ExpandCollapse`, the dropdown's items expose `Invoke`, `SelectionItem` and
`ScrollItem`, and expanding Panel Type enumerates all 56 entries ("Select Your
Panel" plus the 55 models) — which is a convenient way to read the shipped panel
list without reflecting over the assemblies.

**It can be driven end to end.** `seeds/Afterburn ECP 16-9 (Project1).gdl` was
made this way, with no hands on the mouse. The working sequence is the plain one
— for each combo in turn, click it to expand, then click the list item you want:

1. Panel Type. Expanding it lists 56 entries ("Select Your Panel" plus the 55
   models), which is also a convenient way to read the shipped panel list.
2. For a soft client, a **Resolution** combo appears once the panel is chosen.
3. Step 2's Blank / Theme radios, then Theme, then Application.
4. Create.

**Do not set a combo by value.** `ValuePattern.SetValue` writes the edit text
without raising the selection, so the combo *reads* "Extron Control Pro" while
the preview still says "No Panel Type Selected", Step 2 stays greyed and Create
stays disabled. Worse, it desynchronises the control from the model: nothing
afterwards commits, the wizard's own accessibility subtree stops responding
(`FindAll` throws `Operation timed out (0x80131505)`), and the only way out is
Cancel. `SelectionItemPattern.Select()` is the same trap — it highlights without
committing. Only a real click on the list item works.

`Create` and `Cancel` expose no patterns, so they need a click by position.

Two things that mislead on the way in. `InvokePattern.Invoke()` on the menu item
that opens the wizard throws `Operation timed out (0x80131505)` because the call
blocks on the modal — the dialog *does* open, so query it from a separate call
rather than believing the exception. And a click by position goes to whatever
window is on top, so raise the wizard first and confirm what is under the point
before clicking; otherwise it lands in your terminal and nothing appears to
happen.

One consequence worth stating plainly: a seed is no longer the step that needs a
person. It still needs GUI Designer running and a desktop to draw on.

## 6. Honest limits of everything above

- Control-ID uniqueness (the other half of question 5) and question 6 are
  untested.
- Test 3 is only half-answered: an out-of-corpus radius/thickness *builds*, but
  nobody has looked at whether it *rasterizes* correctly. The control used was
  the Offline Window, which Build legitimately leaves unrasterized, so there is
  no artwork to inspect. Redo it against a visible control.
- The resource counts are from the `_alt 2_0_0` fixture, which carries 34 border
  resources; the two archived fixtures carry 36. Across Extron's 50 installed
  templates the count runs **13 to 32**, so treat it as per-project and read it,
  never assume it. The low end matters: a Mach or Turbulence template offers 13
  borders, so a spec that names a radius/thickness the target project has no
  resource for will not resolve.
- The preview's fidelity is measured against pages made of *built* artwork. A
  page of `TLPImageID = -1` controls is exercised by exactly one control in the
  whole corpus (the Offline Window), so the preview's accuracy on a fully
  synthetic page is inferred from that one data point, not measured.

## 7. Driving GUI Designer

This section is the one home for scripting GUI Designer; other files point
here. `powershell\New-GdlPanel.ps1` already runs the whole loop — check, donors,
plan, apply, pack, open, Save and Build, wait, verify — and exits 0 only if the
verifier passed. Read on to script anything it does not cover.

### The session it needs

Authoring — reading, cloning, editing and saving a project graph — is headless
and runs in any context. Anything that *draws* does not: GUI Designer and every
dialog it raises need a session where `[Environment]::UserInteractive` is true
and a desktop exists. A service, a scheduled task, or a remote exec that lands
as `nt authority\system` dies at the first form with "Showing a modal dialog box
or form when the application is not running in UserInteractive mode". An
ordinary logged-in session qualifies.

### The loop

```powershell
# 1. author. 32-bit PowerShell 5.1: .NET Framework still has BinaryFormatter,
#    and Extron's assemblies are x86.
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile `
    -ExecutionPolicy Bypass -File examples\add-page-and-popup.ps1 `
    <work>\ProjectGCP <work>\new_ProjectGCP

# 2. repack, open it, and wait for the project window (see the title trap below)
python -m gdl.container pack template.gdl <work>\new_ProjectGCP <work>\x.gdl
Start-Process "$InstallDir\GUI Designer.exe" -ArgumentList '"<work>\x.gdl"'

# 3. Save and Build - take the baseline mtime BEFORE triggering it
$t0 = (Get-Item <work>\x.gdl).LastWriteTime
powershell\Invoke-GdlMenu.ps1 -Item 'Save and Build'
powershell\Wait-GdlBuild.ps1 -ProjectFile <work>\x.gdl -Since $t0
```

`$InstallDir` and `<work>` are `New-GdlPanel.ps1`'s `-InstallDir` (default
`C:\Program Files (x86)\Extron\GUI Designer`) and `-Work` (default a
per-project directory under `C:\gdlwork`). Keep `<work>` on a local disk: GUI
Designer is slow against a network or mounted drive, which is the only reason
the default is not inside the repo.

### What will cost you time

- **After any GUI Designer upgrade, clear the Save-and-Build prompt before
  expecting an unattended build.** GUI Designer's preferences live in a
  *per-version* `user.config`:

  ```
  %LOCALAPPDATA%\Extron\GUI_Designer.exe_Url_<hash>\<version>\user.config
  ```

  A new version gets a new folder, so every preference you had answered falls
  back to its default. The one that matters is *Automatically Remove Unused
  Resource Library Items During Save and Build*, whose default is to **ask**.
  The first Save and Build after an upgrade therefore opens a modal called
  **Save and Build Optimization** (Keep / Remove, plus "Don't show again") and
  waits. Nothing is written while it is up, so `Wait-GdlBuild.ps1` simply times
  out with no diagnosis — it is watching a file that will never change.

  The dialog's own controls expose **no UIA patterns**, so `Invoke-GdlMenu.ps1`
  cannot dismiss it; it is a coordinate click or nothing. Set the preference
  instead, with GUI Designer closed (it rewrites the file on exit):

  ```xml
  <setting name="ShowRemoveUnusedResourcesWarning" serializeAs="String">
      <value>False</value>          <!-- stop asking -->
  </setting>
  <setting name="RemoveUnusedResources" serializeAs="String">
      <value>False</value>          <!-- and Keep, not Remove -->
  </setting>
  ```

  Keep `RemoveUnusedResources` false. The shipped default is **true**, and
  answering "Remove" — or ticking "Don't show again" on that side — makes every
  later build silently strip unused Resource Library items, which is exactly the
  kind of invisible mutation `tests/verify_built.py` exists to catch.

  This is not a 1.28 feature; the preference is long-standing. It is an
  *upgrade* trap, and it will fire again on the next version.
- **Trigger the build with `Invoke-GdlMenu.ps1`, not SendKeys.** UI Automation
  clicks the menu item directly and needs no focus, so the pipeline runs while
  the machine is in use. SendKeys types into whatever holds the foreground, and a
  pipeline driven from a terminal can never take the foreground from that
  terminal. `Send-GdlKeys.ps1` is only the fallback, and it verifies the window
  and refuses rather than typing blind. `Invoke()` throws `Operation timed out
  (0x80131505)` because it blocks on the build modal; the click landed anyway,
  so watch the `.gdl`, not the exit code.
- **Wait by watching the `.gdl` itself, with `Wait-GdlBuild.ps1`.** Both obvious
  signals are wrong. The title's trailing `*` only means unsaved changes, so a
  freshly packed file opened clean never has one, and a wait on it returns at
  once onto the stale payload. The Build Manager window appears seconds *after*
  the click and closes about five seconds *before* the file is written, so
  trusting it truncates the payload. The file's mtime is the real signal: wait
  for it to change, then to stop changing.
- **Take the baseline mtime before triggering, and pass it as `-Since`.**
  `Invoke-GdlMenu.ps1` blocks on the build modal, so when the build finishes
  before that call returns, a baseline sampled afterwards is already the
  post-build mtime, and the wait times out on a build that succeeded. Machine
  speed decides which way the race falls.
- **`Get-Process` caches `MainWindowTitle`.** It reads `GUI Designer` until you
  call `.Refresh()`, and only then shows `GUI Designer - [TLP Pro 1035T:
  x.gdl]`. Polling for the project name without refreshing waits forever.
- **`Responding = False` during a save is not a hang.** A *Please wait while the
  project is being saved* overlay is up, and the process reports it
  intermittently until the write finishes.
- **`Project > Verify` (Ctrl+B) is not a build**, and `PBProject.BuildProject()`
  cannot be called headlessly — `docs/gdl-format.md` §2 has both. The build is
  **File > Save and Build (Ctrl+Shift+B)**.
- **The Project Create Wizard cannot be driven at all** — see §5c.

### Reading the screen back

```powershell
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
[System.Drawing.Graphics]::FromImage($bmp).CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$bmp.Save('shot.png', [System.Drawing.Imaging.ImageFormat]::Png)
```
