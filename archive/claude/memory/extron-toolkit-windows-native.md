---
name: extron-toolkit-windows-native
description: extron-gdl-toolkit now runs its whole loop natively on the Windows 11 box - the macOS/Parallels prlctl apparatus is obsolete
metadata: 
  node_type: memory
  type: project
  originSessionId: d41fdd7d-83be-42c0-9daa-57b180473df0
  modified: 2026-09-08T06:49:51.227Z
---

As of 2026-09-08 the extron-gdl-toolkit round trip runs entirely on the local
Windows 11 machine. Verified that day: GUI Designer 1.27.0.9 installed at
`C:\Program Files (x86)\Extron\GUI Designer`, 32-bit PowerShell 5.1 loads
39/39 Extron assemblies, `UserInteractive=True` on session 1, and an authored
project opened, Saved-and-Built, and verified in its regenerated payload.

**Why:** The repo's `docs/from-scratch.md` §7 and `out/run-build.ps1` were
written for a macOS host driving a Parallels VM - `prlctl exec --current-user`,
`\\Mac\Home\...` UNC paths, a scheduled task with `/IT` to get a desktop. None
of that is needed now; plain `Start-Process`, `SendKeys` and a .NET
`CopyFromScreen` grab do all of it. The premise that "the Windows box is the
scarce resource," which justified batching plans into single trips, no longer
holds.

**How to apply:** Don't reach for prlctl. The repo still lives on `Z:\` (a
mounted macOS home) so paths are `Z:\GitHub\rob-paprocki\extron-gdl-toolkit`,
but execution is local; use `C:\gdlwork` for build scratch since `Z:` is slow.
Supports [[extron-gdl-toolkit-goal]].
