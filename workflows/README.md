# workflows/

## gdl-bug-hunt.js - planned, never completed

A multi-agent hunt for latent bugs of the shape this repo's worst ones have
had: **the code is confident, the format disagrees, and nothing fails loudly.**
It is a Claude Code Workflow script: run it with the Workflow tool,
`scriptPath: workflows/gdl-bug-hunt.js`, from the repo root, or pass
`args: {"repo": "<absolute path of the checkout>"}` if the agents may start
elsewhere.

| Phase | Model | What |
|---|---|---|
| Extract | haiku, one per source | Pull every absolute claim ("always", "never", counts) out of one source: a slice of the docs, of the Python, the PowerShell, or the gates and measurement scripts. The sources are `CLAIM_SOURCES` in the script. |
| Falsify | sonnet, one per source | Test that source's claims against every project in the corpus. Pipelined behind its extractor. Any extractor, falsifier or sweep that returns nothing is logged and named in the result's `uncovered`, so a dead agent never reads as a clean one. |
| Hunt | sonnet, one per dimension | Independent sweeps: collection traps (more `.Count` liars), guards that cannot fire, silent no-ops, Python↔PowerShell plan-contract drift, `verify_built.py` blind spots, fields a clone inherits that nobody clears, what is secretly Afterburn-only, layout-math edge cases. |
| Verify | sonnet, two per finding | Adversarial, default-refuted, two lenses (reproduce; already-handled). The top findings by severity, up to `MAX_VERIFY`; the rest are reported as unverified rather than dropped, and so is a finding that a lens's agent died before judging - it survives only on every lens's verdict. |

No agent runs on Opus. Extraction is mechanical, so haiku; the rest is
analysis, so sonnet; and the synthesis is the session that launched the run,
reading what the script returns. Every agent is read-only and must attach a
paste-able command and its real output to each finding.

The corpus is every usable project under `fixtures/gdl/` and `seeds/`. The
agents enumerate it themselves with `usable()` from `tests/_corpus.py`, so a
seed added later is picked up and an un-pulled LFS pointer is skipped and
reported. The script states neither a corpus size nor an agent total: it logs
how many agents each phase starts, and the total depends on how many findings
survive deduplication.

The Python and PowerShell sources are globs with a catch-all, so a new module
is read by default. The docs are named: a new doc that states format facts has
to be added to `CLAIM_SOURCES`.

### Before running it

1. Check the commit limit has room (`CLAUDE.md` *Environment traps that cost
   time*), in PowerShell:

   ```powershell
   (Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile
   Get-CimInstance Win32_OperatingSystem | Select-Object TotalVirtualMemorySize, FreeVirtualMemory
   ```

   The first prints `True` when Windows manages the pagefile, which it should.
   The second is in KB; the limit is RAM plus pagefile, and the free figure
   should comfortably exceed the agents that run at once, each a Claude process
   of a few hundred MB.
2. `git lfs pull` so `seeds/` holds real files.
3. Run `python tests/audit_corpus.py` first. The Falsify phase's core idea
   already runs there deterministically and cheaply, with no agents at all; the
   workflow is for the judgment-heavy dimensions it cannot cover. The FAILs it
   reports should already be open items (`docs/gdl-format.md` §9).

`docs/history.md` records why the first two runs did not finish.
