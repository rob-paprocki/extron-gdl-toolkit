---
name: scope-project-not-machine
description: "Get X off drive C" means the project's and its turnover's material only - never a machine-wide backup.
metadata:
  type: feedback
---

When asked to make sure nothing unique is left on a drive (e.g. before a reimage), scope it to **the project and its turnover** - project files, build artifacts, transcripts/memory for that project, what a successor needs to rebuild the toolchain. Do not widen it into backing up the whole machine (browser profiles, other projects' config, app settings).

**Why:** on 2026-09-11, told "at the end there should be absolutely nothing unique on drive C, this machine is being reimaged", I started a machine-wide backup to `Z:\C-drive-backup-2026-09-11`; the user corrected: "I didn't say to do that, I said to ensure that nothing unique for the project or turnover remains on C."

**How to apply:** inventory what belongs to the project, move that, and for anything else found on the drive, list it and ask rather than copying it. Related: [[extron-gdl-toolkit-goal]].
