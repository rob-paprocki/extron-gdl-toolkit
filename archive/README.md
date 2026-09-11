# archive/

Raw working state carried off the Windows box's `C:` drive on 2026-09-10, so
that nothing about this project lives only on one machine. Every file here is a
**byte-identical** copy of its source (verified with `cmp` at copy time).

Nothing in the toolkit imports from here and nothing here is maintained. It is
the evidence behind the commit messages and docs - the builds that proved or
disproved something - kept so a claim can be re-checked against the actual file
rather than against someone's summary of it. Binaries are in Git LFS; run
`git lfs pull --include "archive/**"` to fetch them.

**Sensitivity.** Several builds under `gdlwork/` were made with the Liberty Bank
fixture as the donor, so they carry the same client material as `fixtures/`.
The session transcripts contain the whole working conversation. The repo is
private; keep it that way while these are in it.

| Here | From | What it is |
|---|---|---|
| `gdlwork/` | `C:\gdlwork` | Build scratch from 2026-09-08/09 (session `d41fdd7d`). See below. |
| `job-9fe2c865/` | `C:\Users\robp\.claude\jobs\9fe2c865` | Scratch from 2026-09-09/10 (session `9fe2c865`). See below. |
| `desktop/gdl-retarget-proof/` | `C:\Users\robp\Desktop\gdl-retarget-proof` | The retarget and feedback-state builds, as handed over. |
| `claude/memory/` | `~\.claude\projects\Z--GitHub-rob-paprocki\memory` | Claude Code's saved notes for this folder: the project goal, the move to native Windows, American spelling. |
| `claude/sessions/` | `~\.claude\projects\Z--GitHub-rob-paprocki*` | Claude Code transcripts - see below. |

`Project1.gdl`, the TLP Pro 835M seed that was on the Desktop, had been moved to
the Recycle Bin. It was copied out (not restored) and lives on as
`seeds/Afterburn 835 (Project1).gdl`.

## gdlwork/

| Dir | What was being tested |
|---|---|
| `color/` | Color fidelity end to end: `ColorTest.gdl`, `plan_mutated.json`, and `home_built.png` / `page_asset36.png` read off the built artwork. The run that re-verified color after the fix. |
| `Boardroom/`, `auto/`, `auto2/`, `out3/` | `examples/panel.json` against the Liberty Bank donor; `auto*/` are the first unattended `New-GdlPanel.ps1` runs. |
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
| `tmp/fb/` | The first Off/On feedback build, which **failed** verification with 10 "no visible feedback" problems. This is the evidence for the `PBStates.Count` bug: `pre.gdl` is the applier's output before the build, where every On state still carries the Off fill. |
| `tmp/fb2/` | The same build after the fix: 0 problems, Off and On rasterized separately. |
| `tmp/*.py` | The measurement scripts. The maintained copies are in `research/2026-09-10/`. |
| `state.json`, `timeline.jsonl` | Claude Code's job metadata for the session. |

## claude/sessions/

| File | Session |
|---|---|
| `d41fdd7d-83be-42c0-9daa-57b180473df0.jsonl` | 2026-09-08: embedded Arial, native Windows, `New-GdlPanel.ps1`, the focus-free UIA build, donor gates, the first clean-room builds. |
| `9fe2c865-64e6-481a-a3ab-0ba8f9108851.jsonl` | 2026-09-09/10: the seeds, retarget against Extron's own 1535, Off/On feedback states and `PBStates.Count`, the bug hunt, and this packing. |
| `9fe2c865-.../subagents/` | Partial transcripts of the two bug-hunt workflow runs. Both died about 90 seconds in, when the machine hit its commit limit (8 GB RAM, 500 MB pagefile); see `workflows/README.md`. |
| `extron-project-dir/` | The first run's copy of the workflow script. |

The session that preceded these (`7538bd59`, Mac/Parallels era) was never on
this machine. The transcripts were scanned for GitHub, Anthropic, Slack and AWS
tokens and private keys before commit; none were found.
