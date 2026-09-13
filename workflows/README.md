# workflows/

## gdl-bug-hunt.js - planned, never completed

A multi-agent hunt for latent bugs of the shape this repo's worst ones have
had: **the code is confident, the format disagrees, and nothing fails loudly.** It is a Claude Code Workflow script (run it with the
Workflow tool, `scriptPath: workflows/gdl-bug-hunt.js`).

| Phase | Model | What |
|---|---|---|
| Extract | haiku ×3 | Pull every absolute claim ("always", "never", counts) out of the docs, the Python and the PowerShell. |
| Falsify | sonnet ×3 | Test each batch of claims against every project in the corpus. Pipelined behind its extractor. |
| Hunt | sonnet ×8 | Independent sweeps: collection traps (more `.Count` liars), guards that cannot fire, silent no-ops, Python↔PowerShell plan-contract drift, `verify_built.py` blind spots, fields a clone inherits that nobody clears, what is secretly Afterburn-only, layout-math edge cases. |
| Verify | default ×2 per finding | Adversarial, default-refuted, two lenses (reproduce; already-handled). Top 16 by severity; the rest are reported as unverified rather than dropped. |

Every agent is read-only and must attach a paste-able command and its real
output to each finding.

### Why it has not run

Both attempts (runs `wf_3d13556c-96d` and `wf_35446858-866`) died about 90
seconds in, with the three extract agents healthy and mid-read. The cause was
the host's commit limit, not the script: the limit is RAM plus pagefile, every
workflow agent adds a process, and past it the session under the workflow is
killed and the next command fails with "The paging file is too small for this
operation to complete". Partial agent transcripts are in
`archive/claude/sessions/9fe2c865-.../subagents/`.

### Before running it again

1. Let Windows manage the pagefile (System > About > Advanced system settings >
   Performance > Advanced > Virtual memory > *Automatically manage*), or set it
   to at least 8 GB, and reboot.
2. `git lfs pull` so `seeds/` holds real files - the script now reads the seeds
   from there rather than from the GUI Designer Documents folder.
3. Expect roughly 40 agents.

The Falsify phase's core idea already runs deterministically and cheaply as
`python tests/audit_corpus.py`, which needs no agents at all. Run that first;
the workflow is for the judgment-heavy dimensions it cannot cover.
