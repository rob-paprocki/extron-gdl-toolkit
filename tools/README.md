# tools/

Maintainer tooling. Nothing here is needed to read, render or author a panel.

| file | what it is |
|---|---|
| `public_sync.py` | builds the public copy from the private archive and checks it (`build`, `check`). `CLAUDE.md` *Where work happens* has the procedure |
| `hooks/pre-push` | refuses a push to any remote but the archive unless `public_sync.py check --history` passes. Install it as `CLAUDE.md` says |
| `build_timing_specs.py` | specs that vary one count at a time (pages, controls, states), and a queue file of them |
| `Run-BuildTiming.ps1` | builds a queue of those specs one after another with the host's counters beside each build. Needs Windows and GUI Designer |
| `Sample-GdlHost.ps1`, `Watch-GdlFiles.ps1` | the runner's samplers: host load, and the files a build writes |
| `timing_table.py` | the table and fit read from the runner's logs |

`docs/from-scratch.md` §5c is the home of what the timing runs found.
