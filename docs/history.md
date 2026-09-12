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

## Corrections worth remembering

Each of these was believed, written down, and later found wrong. The current
statement is in the live docs; this is the record that it changed.

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
