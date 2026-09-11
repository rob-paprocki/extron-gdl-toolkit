---
name: extron-box-commit-limit
description: The Windows box has 8 GB RAM + a fixed 500 MB pagefile; big workflows and batch-parsing .gdl files exhaust it and kill the session.
metadata: 
  node_type: memory
  type: project
  originSessionId: 9fe2c865-64e6-481a-a3ab-0ba8f9108851
  modified: 2026-09-11T04:09:40.740Z
---

The Windows machine running [[extron-toolkit-windows-native]] work has 8 GB of RAM and a pagefile pinned at 500 MB (automatic management off), so the commit limit is ~8.5 GB. On 2026-09-10 two runs of a ~40-agent bug-hunt workflow each died ~90 s in, and the next command failed with "The paging file is too small for this operation to complete".

**Why:** each Claude Code process holds 150-600 MB (six were running), each workflow agent adds a process, and Python code that parses many .gdl files at once holds them all in memory.

**How to apply:** until the user switches the pagefile to system-managed (or >= 8 GB) and reboots, keep workflows small, stream over projects one at a time, and check free virtual memory before any large fan-out. The planned hunt is saved at `workflows/gdl-bug-hunt.js` in the repo. Related: [[extron-gdl-toolkit-goal]].
