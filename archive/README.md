# archive/

Raw working state carried off the Windows box's `C:` drive on 2026-09-10, so
that nothing about this project lives only on one machine. Every file here is a
**byte-identical** copy of its source (verified with `cmp` at copy time).

Nothing in the toolkit imports from here and nothing here is maintained. It is
the evidence behind the commit messages and docs - the builds that proved or
disproved something - kept so a claim can be re-checked against the actual file
rather than against someone's summary of it. Binaries are in Git LFS; run
`git lfs pull --include "archive/**"` to fetch them.

**Sensitivity.** Several builds under `gdlwork/` were made with the client
fixture as the donor, so they carry the same client material as `fixtures/`,
and the session transcripts contain the whole working conversation. The
public copy holds those back, and `gdlwork/clean/wizard.png` and `wiz2.png`,
whose status bar shows an account, and a few evidence logs and scratch files
that name the client or the owner's folders: `tools/public_sync.py`'s
`EXCLUDE` lists every one.

| Here | From | What it is |
|---|---|---|
| `gdlwork/` | `C:\gdlwork` | Build scratch from 2026-09-08/09 (session `d41fdd7d`). See below. |
| `job-9fe2c865/` | `C:\Users\<user>\.claude\jobs\9fe2c865` | Scratch from 2026-09-09/10 (session `9fe2c865`). See below. |
| `job-2419a20b/` | `C:\Users\<user>\.claude\jobs\2419a20b` | Build evidence from 2026-10-10 and 11 (session `2419a20b`). See below. |
| `desktop/gdl-retarget-proof/` | `C:\Users\<user>\Desktop\gdl-retarget-proof` | The retarget and feedback-state builds, as handed over. |
| `claude/memory/` | `~\.claude\projects\Z--GitHub-rob-paprocki\memory` | Claude Code's saved notes for this folder: the project goal, the move to native Windows, American spelling. |
| `claude/sessions/` | `~\.claude\projects\Z--GitHub-rob-paprocki*` | Claude Code transcripts - see below. |
| `gui-designer/` | `C:\ProgramData\Extron\Temp\GDFont`, and GUI Designer's per-user settings | **Not here any more**: moved to the git-ignored `private/gui-designer/` (`CLAUDE.md` *Things deliberately not in git*). GUI Designer's temp copies of the fonts a project carries - retail Monotype Arial and Arial Black among them, which the seeds embed as well - and its per-user settings. |

`Project1.gdl`, the TLP Pro 835M seed that was on the Desktop, had been moved to
the Recycle Bin. It was copied out (not restored) and lives on as
`seeds/Afterburn 835 (Project1).gdl`.

## gdlwork/

| Dir | What was being tested |
|---|---|
| `color/` | Color fidelity end to end: `ColorTest.gdl`, `plan_mutated.json`, and `home_built.png` / `page_asset36.png` read off the built artwork. The run that re-verified color after the fix. |
| `Boardroom/`, `auto/`, `auto2/`, `out3/` | `examples/panel.json` against the client donor; `auto*/` are the first unattended `New-GdlPanel.ps1` runs. |
| `huddle/`, `Huddle/`, `out/`, `out2/` | `examples/huddle.json` - the prose-brief panel that exposed the missing font application and the cp1252 spec read. |
| `mp/`, `mp2/`, `seed1/`, `seed2/`, `Multipage/` | `examples/multipage.json`, first against the fixture, then (`seed*`, `Multipage/`) against the 835 seed - the first clean-room build. |
| `clean/` | The first clean-room attempt, including screenshots of the Project Create Wizard that UI Automation cannot see into. |
| `CleanRoom/` | `examples/clean-room.json` built from the 835 seed; `room.png` is the result. |
| `tmpl/` | A `.glt` template used as a donor - the file GUI Designer silently refused to open (docs/from-scratch.md §5c). |
| `ex1/` | Resume test of the authoring bridge. |
| `specs/` | Specs as used on the box. |
| `uia-build.ps1`, `uia-build.log` | The UI Automation prototype that became `powershell/Invoke-GdlMenu.ps1`. |

## job-9fe2c865/

| Path | What it is |
|---|---|
| `tmp/rt/` | Retarget ground truth. `seed.gdl` is `Afterburn 1035.gdl`; `plan.json` is `retarget -> TLP1535M --scale`; `retargeted.gdl` is GUI Designer's build of it (650/650 controls, 0 relocated, 10 popups kept at 1320x709). `noop_ProjectGCP` and `plan_empty.json` are the diagnostic that pinned the `0x80070002` message on `Save-GdlProject` itself. |
| `tmp/fb/` | The first Off/On feedback build, which **failed** verification with 10 "no visible feedback" problems. This is the evidence for the `PBStates.Count` bug: `pre.gdl` is the applier's output before the build, where every On state still carries the Off fill - as packed then, but for two signature patterns in its payload that packer swapped with the records', put back so it reads whole (`docs/history.md`). |
| `tmp/fb2/` | The same build after the fix: 0 problems, Off and On rasterized separately. |
| `tmp/*.py` | The measurement scripts. The maintained copies are in `research/2026-09-10/`. |
| `state.json`, `timeline.jsonl` | Claude Code's job metadata for the session. |

## job-2419a20b/

Held back from the public copy whole: the logs name the owner's folders, and
the built files are not reviewed for it.

| Path | What it is |
|---|---|
| `borders/` | Theme-portable borders built: `ab320.json` - Afterburn's `afterburn` and `afterburn-flat` (10 Radius 2 Thick, 10 Radius 0 Thick) on a TLP320M - through `New-GdlPanel.ps1` with no `-Donor`, so on the seed the pick gives it, `seeds/Afterburn 320.gdl`, which has neither. `build.log`, the `plan.json` that names the 320's 7 Radius 2 Thick and 14 Radius 0 Thick instead, the built `Borders320.gdl` (its 3 controls verified, 0 problems) whose project names those on every control and state, and `built_home.png`, its page drawn from the built payload at 2x. |
| `fonts/` | Faces appended: `spec.json` - labels in Open Sans Light, Arial Black and Open Sans on a TLP1035T - through `New-GdlPanel.ps1` with no `-Donor`, so on `seeds/Afterburn 1035.gdl`, which has a font resource for neither of the first two. `build.log`, whose `donors` step names each face it appends and the seed it is copied from, the `plan.json` whose `fonts` record each as that seed does - author included - and name the seed (the faces themselves, written beside it, are left out: the built file carries them), the built `FontAppend.gdl` (its 3 labels verified, 0 problems), which declares and carries both, Open Sans Light recorded as added from a file as the Mach seed records it, and `built_page.png`, its page drawn from the built payload. |
| `item6/` | Icon-font glyphs built: `examples/icons.json` on `seeds/Afterburn 1035.gdl` - `New-GdlPanel.ps1`'s `build.log`, the `plan.json` it applied and the built `IconSources.gdl`, whose `layout.json` carries each glyph in Extron-Afterburn on every state, and which `tests/verify_built.py` checks clean. |
| `item4/` | The real-size panel, `examples/boardroom-full.json` on `seeds/Afterburn 1035.gdl` (`docs/from-scratch.md` §5c). Each `build<n>/build.log` is `New-GdlPanel.ps1`'s log of one of six builds. `build1/` kept the donor's own pages and popups - its `BoardroomFull.gdl` is the 3.66 MB file, and `verify_built.log` its check; builds 2 to 6 dropped them. Builds 4 and 5 end where an earlier wait gave up at 60 s: 4 was then closed, 5 left to finish, which `watch5.log`, a window watcher's log, follows to the save (`watch.log` is build 4's). `build6/` holds the last build's plan, ID map and built file, which `tests/verify_built.py` and `tests/verify_idmap.py` check clean. |
| `autoseed/` | `examples/panel.json` built through `New-GdlPanel.ps1` with no `-Donor`: its `build.log` - the seed it picked, and the build with the seed's pages dropped, whose time `docs/from-scratch.md` §5c gives from the click - and the built `AutoSeed.gdl`, 152 checks over its 38 controls, 0 problems. `wait/long-build.log` is the same spec with the seed's pages kept (`docs/from-scratch.md` §5c). |
| `seeds/` | The three 725 seeds `New-GdlSeed.ps1` made (`seeds/Mach 725.gdl`, `Shockwave 725.gdl`, `Turbulence 725.gdl`): each run's log, with how long GUI Designer took to answer after Save As (16 s, 34 s, 34 s) and its build, and `Mach-TLP725T-long.log`, the run that lost the Mach seed to the hung window - no File menu while Not Responding, deleted as unbuilt (`docs/from-scratch.md` §7). `Afterburn 725 again.gdl` and `Afterburn-TLP725T-again.log`: the Afterburn 725 made again through the fixed script with GUI Designer in feature-flag mode - its checksum noted by the verifier, and 935 s from Create to its build where `seeds/Afterburn 725.gdl` took 168 s. The wizard screenshots are left out: they are of the whole screen. |
| `seeds-mst/` | The fourteen Mach, Shockwave and Turbulence seeds `New-GdlSeed.ps1` made at the sizes those themes lacked - the 525, 320, 1525TG and 720T in each, and the 535T in Mach and Shockwave - each run's log and `summary.txt`, each run's exit and time. The first pass's three 1525TG runs stopped at exit 4 (the panel type below the open list's rows, clicked where it was drawn) and the Turbulence 720's at exit 5 (Create behind *Please Wait* past 900 s, 1,570 s when made again); their logs are the second pass's, after the fixes in `docs/from-scratch.md` §7. |
| `turned/` | A panel turned where Extron draws no template that way up, built: `seed.log` is `New-GdlTurnedSeed.ps1` turning `seeds/Afterburn 1035.gdl` into `seeds/Afterburn 1035 Portrait.gdl` (650 of 650 controls, verified as a TLP1035M); `build.log` is `New-GdlPanels.ps1` building a copy of the panels canvas (`tests/data/design-panels`) with every Page's `panels` set to `TLP1035T TLP1035M-Portrait` - both panels built and verified against one ID map. `spec.json` is the portrait panel's, `Huddle Portrait.gdl` its build (800x1280, Orientation 1, its own checksum, not the seed's), and `built_page.png` its page drawn from the built payload. |
| `panels-mst/` | Mach, Shockwave and Turbulence on every tier A panel, built: each `<theme>-build.log` is `New-GdlPanels.ps1` building that theme's panels canvas (`tests/data/design-panels-<theme>`, the Huddle listing the TLP1035T, TLP725T, TLP1525TG and TLP720T) - each panel on its own seed, verified against one ID map. In `turbulence-build.log` the 725 is built and not verified: the verifier stopped on a wrong CRC-32 in its `ProjectGCP`, which the reader had made by swapping signature bytes inside its data (`docs/gdl-format.md` §1). `turbulence-725-crc.txt` is what was found, including what was first wrongly concluded, and `turbulence-725-build.log` a later build of the 725, verified while the readers still read past a wrong CRC; the same file verifies with the fixed reader, with no note. `<theme>-<725, 1525 or 720>-home-design.png` and `-built.png` are `gdl.design compare`'s Home on that panel, as designed and as built. `mach-725-home-built-captions-clipped.png` is the Mach 725 built before captions below an icon kept only the line breaks that fit (`gdl/design.py` `_fit_breaks`): three breaks put its source tiles' captions past their edge. The logs are UTF-16, as Windows PowerShell 5.1 writes them, but `turbulence-725-build.log`, UTF-8 from PowerShell 7. |
| `hubs/` | Mach, Shockwave and Turbulence on every panel but the 320, built: each `<theme>-build.log` is `New-GdlPanels.ps1` building that theme's hub-ready canvas (`tests/data/design-panels-<theme>`, the Huddle listing the TLP1035T, TLP725T, TLP1525TG, TLP720T, TLP535T and TLP525T - Turbulence draws no 535), each panel on its own seed and verified against one ID map; `<theme>-hubs-build.log` builds the hubs again, `-Models`, with their Up and Down in the look of the Mute below them where that look can draw them (Mach's, Turbulence's; Shockwave's in its default), against the same map. `<theme>-<525 or 535>-home-design.png` and `-built.png` are `gdl.design compare`'s Home on that hub, as designed and as built. The logs are UTF-8, from PowerShell 7. |
| `prose-in/` | A conference room from one prose brief, drawn by a fresh designer per theme with nothing but the Design type's instructions and the theme's design system, read back, translated and built: `round1/` from the READMEs as they were (every 1035 clean; only Afterburn's 525, built on both panels), `round2/` from the READMEs after (every 1035 built and verified), `round3/` from the READMEs after #39 and #40 (Mach's, Shockwave's and Turbulence's rooms built and verified on the 1035 and the 525). Each holds the canvases, the translator's and the builds' logs and the sign-off images; its `README.md` has the brief and what each round showed. The PowerShell 5.1 build logs are decoded from UTF-16. |
| `wait/` | What `Wait-GdlBuild.ps1` tells a build from a modal by (`docs/from-scratch.md` §7). `modal.log`: GUI Designer's writes idle and behind its About box. `modal-wait.log`: the wait, and the writes-only wait before it, against that modal. `icon-build.csv` and `long-build.csv`: two nine-minute builds sampled every two seconds - bytes written, CPU seconds, whether the window answered - with `long-build.log`, the second run under the wait at a 60-second timeout. |

## claude/sessions/

| File | Session |
|---|---|
| `d41fdd7d-83be-42c0-9daa-57b180473df0.jsonl` | 2026-09-08: embedded Arial, native Windows, `New-GdlPanel.ps1`, the focus-free UIA build, donor gates, the first clean-room builds. |
| `9fe2c865-64e6-481a-a3ab-0ba8f9108851.jsonl` | 2026-09-09/10: the seeds, retarget against Extron's own 1535, Off/On feedback states and `PBStates.Count`, the bug hunt, and this packing. |
| `9fe2c865-.../subagents/` | Partial transcripts, with their journals, of the two bug-hunt workflow runs. Both ended within 80 seconds of launching, very likely when the machine hit its commit limit (8 GB RAM, 500 MB pagefile); `docs/history.md` has the account. |
| `extron-project-dir/` | The first run's copy of the workflow script. |

The session that preceded these (`7538bd59`, Mac/Parallels era) was never on
this machine. The transcripts were scanned for GitHub, Anthropic, Slack and AWS
tokens and private keys before commit; none were found.
