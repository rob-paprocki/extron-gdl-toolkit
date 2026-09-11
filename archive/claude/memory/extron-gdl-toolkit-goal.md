---
name: extron-gdl-toolkit-goal
description: "The end goal of extron-gdl-toolkit is a skill/plugin that authors a production-ready Extron touch panel from prose, never opening GUI Designer by hand"
metadata: 
  node_type: memory
  type: project
  originSessionId: d41fdd7d-83be-42c0-9daa-57b180473df0
  modified: 2026-09-08T06:49:40.240Z
---

The point of `Z:\GitHub\rob-paprocki\extron-gdl-toolkit` is a **skill/plugin
that turns prose into a production-ready Extron GUI**, in a Claude Code, Claude
Design, or mixed session - with no human ever opening GUI Designer. Everything
else in the repo (the `.gdl` format reverse-engineering, the render harness,
the spec and edit pipelines) is scaffolding for that.

**Why:** Stated directly on 2026-09-08: "at the core of all this remains the
desire to build a skill/plugin to be able to author a GUI without needing to
open GUI designer and instead get to a production ready GUI using prose."

**How to apply:** Judge work against that goal. GUI Designer still owns
rasterization at Build time, so "without opening it" means the toolkit drives
it headlessly, not that it is removed from the loop. As of 2026-09-08 the whole
loop runs natively on the Windows box - see
[[extron-toolkit-windows-native]]. Open blockers were color fidelity and the
unexplained render residual on the TLP1035 fixture. Use American spelling -
[[american-spelling]].
