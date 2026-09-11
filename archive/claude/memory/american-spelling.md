---
name: american-spelling
description: "Rob wants American spelling everywhere - \"color\" not \"colour\" - in code, docs and prose"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d41fdd7d-83be-42c0-9daa-57b180473df0
  modified: 2026-09-08T06:49:31.368Z
---

Use American spelling in all code, documentation and prose for this user.
"color", not "colour". Called out explicitly: "COLOR (not colour we are
Americans)".

**Why:** The extron-gdl-toolkit repo had accumulated British spellings
("colour fidelity", "rasterise") from earlier sessions, and it reads wrong to
him.

**How to apply:** Write American spellings by default. When editing a repo that
already has British ones, normalize them rather than matching the surrounding
text. Note this collides with the usual "match the surrounding code style"
instinct - the user's preference wins. See [[extron-gdl-toolkit-goal]].
