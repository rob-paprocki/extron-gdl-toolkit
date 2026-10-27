# workflows/

## gdl-bug-hunt.js

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
| Hunt | sonnet, one per dimension | Independent sweeps: collection traps (more `.Count` liars), guards that cannot fire, silent no-ops, Python↔PowerShell plan-contract drift, `verify_built.py` blind spots, fields a clone inherits that nobody clears, what is secretly Afterburn-only, the translator's contract (what `bundle.js` writes into `data-gdl` against what `design.py` reads, refusals that cannot fire, layout math at each panel tier, ID allocation), the region frame measured against the template's own pages in the seeds, layout-math edge cases. |
| Verify | sonnet, two per finding | Adversarial, default-refuted, two lenses (reproduce; already-handled). The top findings by severity, up to `MAX_VERIFY`; the rest are reported as unverified rather than dropped, and so is a finding that a lens's agent died before judging - it survives only on every lens's verdict. |

No agent runs on Opus. Extraction is mechanical, so haiku; the rest is
analysis, so sonnet; and the synthesis is the session that launched the run,
reading what the script returns. Every agent is read-only and must attach a
paste-able command and its real output to each finding.

The corpus is every usable project under `fixtures/gdl/` and `seeds/` - the
client fixtures are in the private archive only, so a checkout without them
hunts the seeds. The translator dimensions also use the Design canvases in
`tests/data/` and the series profiles in `gdl/designsys/*.json`; running
`translate` needs `GDL_DC_RUNTIME`. The
agents enumerate it themselves with `usable()` from `tests/_corpus.py`, so a
seed added later is picked up and an un-pulled LFS pointer is skipped and
reported. The script states neither a corpus size nor an agent total: it logs
how many agents each phase starts, and the total depends on how many findings
survive deduplication.

The Python and PowerShell sources are globs with a catch-all, so a new module
is read by default. The docs are named: a new doc that states format facts has
to be added to `CLAIM_SOURCES`. `docs/ROADMAP.md` is a source (its measured
facts about templates and Build); `docs/history.md` is not, because it records
beliefs that were retired, and `docs/superpowers/plans/` is not, because a plan
states what will be done rather than what a file holds - the script's comment
says so beside `docs-roadmap`.

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

4. Keep the launching session open until the workflow finishes - it runs
   for hours. A headless `claude -p` session exits when its turn ends and
   takes a running workflow with it; tell it in its prompt to wait for the
   workflow (the Monitor tool, or repeated `until` loops on the workflow
   task's `.output` file) rather than end its turn.

Findings over `MAX_VERIFY` come back unverified: verify them in a second,
smaller workflow with the same two lenses rather than raising the cap, and
deduplicate them first.

## gdl-verify-findings.js

That second workflow. It takes a JSON file of findings and runs the hunt's two
lenses (reproduce; already-handled), default-refuted, on sonnet, over each.

```
Workflow scriptPath: workflows/gdl-verify-findings.js
         args: {"findings": "<path to the findings file>", "repo": "<absolute path of the checkout>"}
```

`ids` (a list) limits it to those entries; without it a haiku agent lists the
file's. The file is a JSON list of findings, each with an `id`, `title`,
`file`, `severity`, `confidence` and `impact`, and `assumption`, `reality`,
`evidence_command` and `evidence_output` where the reporter had them - the
shape of `archive/job-e823df9b/bug-hunt/hunt-unverified-distinct.json`, which
is what the first hunt's second pass ran on. That path is in the private archive
only; `tools/public_sync.py` leaves `archive/job-e823df9b/` out of the public
copy, where the shape is the one this paragraph describes. A script cannot read files, so each
verifier opens its own entry by id. Deduplicate first: two entries for one bug
are two verifications spent on it. The result has the shape of that run's
`hunt-verify2.json` - `confirmed`, `refuted`, `unjudged` (ids a lens never
judged) and `counts` - each entry whole: `id`, `title`, `file`, `impact`,
`original_severity` (the reporter's), `severity` (the verifiers' correction, or
null), `reproduced` (any lens ran it and saw the behavior) and each lens's
verdict. An empty file is an error, not a clean run, and so is an `ids` value
the file does not hold. The reproduce lens refutes a claim about a `.gdl` file
that no corpus file demonstrates; a PowerShell or documentation finding is
judged on its own evidence.

`docs/history.md` records why the first two runs did not finish and what the
first complete one found; its results are in `archive/job-e823df9b/bug-hunt/` (the private archive only;
the public copy leaves that folder out, and holds the history entry alone).
