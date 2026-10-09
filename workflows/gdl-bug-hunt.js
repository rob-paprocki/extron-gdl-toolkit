export const meta = {
  name: 'gdl-bug-hunt',
  description: 'Hunt latent bugs in extron-gdl-toolkit by falsifying code/doc claims against every real .gdl project in the corpus, then adversarially verify',
  phases: [
    { title: 'Extract', detail: 'haiku pulls every absolute claim out of docs, Python and PowerShell', model: 'haiku' },
    { title: 'Falsify', detail: 'sonnet tests each claim against every project in the corpus', model: 'sonnet' },
    { title: 'Hunt', detail: 'sonnet sweeps the bug-class dimensions', model: 'sonnet' },
    { title: 'Verify', detail: 'sonnet, adversarial refutation, two independent lenses per finding', model: 'sonnet' },
  ],
}

// A workflow script has no Node API (no process, no filesystem), so it cannot look
// the checkout up, and it must never hardcode one: a drive letter outlives the
// checkout and fails the run on its first line. The caller may pass the checkout
// as the workflow's args ({"repo": "<absolute path>"}); without it the agents work
// from the directory they start in, which is the repo root when this is launched
// from there.
const REPO = typeof args !== 'undefined' && args && args.repo ? String(args.repo) : null
const ROOT = REPO
  ? `${REPO} (cd there first; run python from there)`
  : 'the directory you start in (run python from there)'

const CONTEXT = `
You are bug-hunting in a Python + PowerShell toolkit that reads and writes Extron
GUI Designer .gdl files. Repo root: ${ROOT}.

READ-ONLY. Do not edit, create or delete any file in the repo. You are finding, not fixing.
You MAY write throwaway scripts to your temp dir and run them.

THE CORPUS - this is the point of the exercise: every .gdl project the repo carries.
  - fixtures/gdl/*.gdl    real client projects
  - seeds/*.gdl           themed seed projects, one per theme and panel size (Git LFS)
Any count or list of them written in a doc or a prompt goes stale, so enumerate them
yourself, once, from the repo root, and quote what that prints:
  import glob, sys; sys.path.insert(0, '.'); sys.path.insert(0, 'tests')
  from _corpus import usable      # False for a missing file or an un-pulled LFS pointer
  paths = [p for p in sorted(glob.glob('fixtures/gdl/*.gdl') + glob.glob('seeds/*.gdl')) if usable(p)]
  print(len(paths), 'usable projects')
A seed that is still an LFS pointer is not in the corpus: say so rather than guess at it.
Stream the corpus: open one project, reduce it to plain facts, drop it, then open the
next. Parsed projects are large, and holding many at once in every parallel agent can
exhaust the host's commit limit.
Nearly every claim in this repo was first inferred from ONE project (the client project), and
the seeds differ in theme, platform, panel size and canvas. Claims that were "always
true" may be true only of that one project.

HOW TO READ A PROJECT (all stdlib, works from the repo root):
  import sys; sys.path.insert(0, '.')
  from gdl.project import Project
  p = Project.open(path)
  for pg in p.pages():          # {'kind','id','name','size','controls':[...]}
      for c in pg['controls']:  # {'type','name','rect','fill','border','n_states',...}
          ...
  # raw graph walk, when you need fields pages() does not surface:
  proj = next(p.instances('PBProject'), None)
  for pg in p.items(p.field(proj, 'pagesField')):
      for c in p.items(p.field(pg, 'controlsField')):
          p.field(c, 'someField'); p.states(c); p.color(p.field(c, 'borderFillColorField'))
  # the BUILT payload (ground truth for what the panel actually shows):
  import json; from gdl.container import open_payload
  lay = json.loads(open_payload(path).read('layout.json').decode('utf-8-sig'))
  lay['Pages'], lay['PopupPages'], lay['ScreenSize'], lay['NonDefaultFontResources']
  # a page/control/state carries 'TLPImageID'; open_payload(path).read(f'{id}.png') is its artwork.

TWO BUGS ALREADY FOUND, as calibration for the class of thing worth reporting:

1. PBStates has no Count member at all (docs/gdl-format.md section 7). PowerShell 5.1 answers
   1 for .Count on any object that lacks one, so it read 1 for an ordinary two-state Off/On
   button, while the indexer [0] and [1] both worked. So every
   'for ($i=0; $i -lt $states.Count; $i++)' loop in both PowerShell appliers wrote state 0
   and stopped. Invisible from outside because TLPDefaultStateID is 0: the panel renders
   state 0, so the file looks perfect and only misbehaves once a control system switches it.

2. "A popup's authored size is always the whole canvas" was inferred from the client project,
   where it happens to be true. In Extron's Afterburn template 10 of 29 popups are authored
   at 880x525 and the BUILT layout.json reports 880x525 for them. Code acting on the old
   belief resized every popup to the screen size, turning modal cards into full-screen pages.

Both share a shape: THE CODE IS CONFIDENT AND THE FORMAT DISAGREES, and nothing fails loudly.
That is what you are looking for. Rank a silent wrong-output bug far above a crash.

WHAT IS NOT INTERESTING - do not report these:
  - style, naming, typos, missing type hints, "could be refactored"
  - hypotheticals you cannot demonstrate against a real file in the corpus
  - a missing test, unless it hides a real defect you can show
  - anything in tests/ that is merely incomplete rather than wrong
  - the bare '0x80070002' printed by Save-GdlProject (known, harmless, documented)
  - anything docs/ROADMAP.md already lists as a known gap or a backlog item

EVERY finding must carry a command someone can paste to see it, and that command's real
output. If you cannot produce that, lower confidence or drop the finding.`

const CLAIMS_SCHEMA = {
  type: 'object',
  properties: {
    claims: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string', description: 'the assertion, quoted or closely paraphrased' },
          file: { type: 'string' },
          line: { type: 'integer' },
          testable: { type: 'string', description: 'how you would falsify it against the corpus' },
          risk: { type: 'string', enum: ['high', 'medium', 'low'], description: 'high = code acts on it and it was inferred from one project' },
        },
        required: ['claim', 'file', 'testable', 'risk'],
      },
    },
  },
  required: ['claims'],
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string', description: 'one line, specific' },
          file: { type: 'string' },
          line: { type: 'integer' },
          bug_class: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          assumption: { type: 'string', description: 'what the code believes' },
          reality: { type: 'string', description: 'what the corpus shows is actually true' },
          evidence_command: { type: 'string', description: 'paste-able command proving it' },
          evidence_output: { type: 'string', description: 'what that command actually printed when you ran it' },
          impact: { type: 'string', description: 'what ships wrong, and whether anything reports it' },
          fix_sketch: { type: 'string' },
          confidence: { type: 'string', enum: ['certain', 'likely', 'possible'] },
        },
        required: ['title', 'file', 'bug_class', 'severity', 'assumption', 'reality',
                   'evidence_command', 'evidence_output', 'impact', 'confidence'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean', description: 'true if the finding is wrong, already handled, or unprovable' },
    reasoning: { type: 'string' },
    reproduced: { type: 'boolean', description: 'did you personally run the evidence command and see the claimed behavior' },
    actual_output: { type: 'string', description: 'what you saw when you ran it' },
    severity_correction: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'unchanged'] },
  },
  required: ['refuted', 'reasoning', 'reproduced'],
}

// ---------------------------------------------------------------------------
// Phase 1+2: extract absolute claims (cheap, mechanical), then falsify each
// batch against every project in the corpus. Pipelined - no barrier, a batch
// starts being falsified the moment its extractor returns.
//
// One extractor per source, each sized so that one haiku agent can read its
// whole slice. The Python and PowerShell slices are globs with a catch-all, so a
// module added later is read by default; the docs are named, so a new doc that
// states format facts has to be added here.
// ---------------------------------------------------------------------------
const CLAIM_SOURCES = [
  {
    key: 'docs-format',
    where: 'docs/gdl-format.md, docs/from-scratch.md, docs/editing.md, docs/render-fidelity.md, seeds/README.md, gdl/fonts/README.md',
  },
  {
    key: 'docs-guides',
    where: 'docs/design-rules.md, docs/claude-design.md, docs/idmap.md, SKILL.md, CLAUDE.md, README.md',
  },
  {
    key: 'python-read',
    where: 'every docstring and comment in the gdl/*.py modules other than spec.py, edit.py, idmap.py and design.py (those have extractors of their own)',
  },
  {
    key: 'python-author',
    where: 'every docstring and comment in gdl/spec.py, gdl/edit.py and gdl/idmap.py',
  },
  {
    key: 'python-design',
    where: 'every docstring and comment in gdl/design.py and in the .py files under gdl/designsys/ (its .json files are data, not claims)',
  },
  {
    key: 'powershell',
    where: 'every comment block in powershell/*.ps1',
  },
  {
    key: 'gates',
    where: 'every docstring and comment in the gates and measurement scripts: tests/verify_*.py, tests/type_probe.py, tests/measure_series.py and tests/audit_corpus.py (not the test_*.py files)',
  },
]

phase('Extract')
log(`Extract: ${CLAIM_SOURCES.length} haiku extractors, each followed by one sonnet falsifier`)

// An agent that dies takes its share of the hunt with it, and its null looks
// exactly like a share that found nothing. So each one is named, in the log and
// in what the run returns.
const uncovered = []

const claimResults = await pipeline(
  CLAIM_SOURCES,
  src => agent(
    `${CONTEXT}

Read ${src.where}.

Extract every ABSOLUTE, FALSIFIABLE claim about the .gdl format or about GUI Designer's
behavior. You are looking for sentences that assert something is universally true:
"always", "never", "every", "the only", "must", "is the", "cannot", and bare statements
of fact about how the format works ("a popup's authored size is the whole canvas",
"a button's caption lives in its first state", "Build relocates X to 0,0").

Include specific NUMBERS presented as facts (counts, percentages, sizes, DPI values) -
a number measured against one project is exactly the kind of claim that turns out to be
local rather than universal.

EXCLUDE: claims about this repo's own architecture or workflow ("decisions are made in
Python", "run this under 32-bit PowerShell"), and anything you cannot test by reading
.gdl files.

Mark risk=high when the code ACTS on the claim (a check, a branch, a written field) AND
it looks like it was inferred from the client fixture. Those are the ones that ship
wrong output.

Be thorough - this is extraction, not judgment. 30+ claims from a docs source is normal.`,
    { label: `extract:${src.key}`, phase: 'Extract', model: 'haiku', schema: CLAIMS_SCHEMA }),

  (extracted, src) => {
    const all = extracted?.claims || []
    const claims = all.filter(c => c.risk !== 'low')
    // A dead extractor and a source with nothing testable look the same downstream,
    // so say which: silence here reads as "covered".
    if (!extracted) {
      log(`extract:${src.key} returned nothing, so this source is NOT covered (${src.where})`)
      uncovered.push(`extract:${src.key}`)
    }
    else log(`extract:${src.key} -> ${all.length} claims, ${claims.length} to falsify, ${all.length - claims.length} low-risk set aside`)
    if (!claims.length) return { findings: [] }
    return agent(
      `${CONTEXT}

Below are ${claims.length} claims extracted from ${src.where}. Your job is to FALSIFY them
against every project in the corpus. Not to confirm them - to find the ones that are
false, or true only of the client fixture.

${claims.map((c, i) => `${i + 1}. [${c.risk}] "${c.claim}"
   (${c.file}${c.line ? ':' + c.line : ''})  test: ${c.testable}`).join('\n')}

Method: write ONE Python script that loops over every usable project in the corpus, one
open at a time, and checks as many of these claims as you can at once. Run it. Read the
output. Then follow up on whatever looks wrong. Prefer measuring over reasoning - the
corpus is right there.

A claim being false is only a FINDING if code or documentation acts on it in a way that
produces wrong output, a wrong gate, or a wrong instruction to a future reader. Say which,
in 'impact'. If a claim is false but harmless, skip it.

Report only what you actually demonstrated.`,
      { label: `falsify:${src.key}`, phase: 'Falsify', model: 'sonnet', schema: FINDINGS_SCHEMA })
  },
)

// ---------------------------------------------------------------------------
// Phase 3: independent bug-class sweeps. Each is blind to the others.
// ---------------------------------------------------------------------------
const DIMENSIONS = [
  {
    key: 'collection-traps',
    prompt: `Hunt for more instances of the PBStates.Count class of bug: a .NET wrapper with no
Count of its own, so that PowerShell answers 1 for .Count (docs/gdl-format.md section 7) - an
object whose apparent size, length or emptiness LIES to the code reading it.

Go through powershell/*.ps1 and gdl/*.py and find every place that trusts a collection's
count, truthiness, enumerability or indexer without checking it against the underlying
storage. PBStates was one, and Get-GdlStates (powershell/GdlApply.ps1) is its fix; a loop
bound that does not go through such a helper is a candidate. The page, popup, control and
resource collections are plain List<T>, with a real Count; the wrappers are the PB* types
that hold a collection inside them - PBStates and PBResourceSet among them. Find the rest
in Extron's assemblies rather than trusting this list.

You can settle these empirically. Under 32-bit PowerShell:
  C:\\Windows\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "..."
dot-source powershell/GdlProject.ps1, Initialize-Gdl, Open-GdlProject on an extracted
ProjectGCP, and compare .Count against the length of the list inside each wrapper type.
Extract one first: python -m gdl.container extract <some.gdl> <tmpdir>

Also check the mirror image in Python: does gdl/project.py read any collection in a way
that silently yields fewer items than exist? items() and deref() are the places to look.`,
  },
  {
    key: 'dead-guards',
    prompt: `Hunt for validation that CANNOT FIRE - guards with a blind spot exactly where the
thing they guard against happens.

The exemplar: gdl/edit.py's overflow check called itself "the check that makes retargeting
safe to offer" and began with 'if pg["kind"] != "page": continue'. Popups are the only pages
whose canvas may differ from the screen, so it was skipping the only case it could ever
have caught.

Look at every check in gdl/spec.py (Panel.check(), Panel.check_donor(), the design-rule
checks), gdl/edit.py (Edits.check()), gdl/idmap.py (check(), check_panels()),
tests/verify_built.py, tests/verify_idmap.py, tests/verify_seed.py, and the Note-Problem and
Note-Fatal calls in powershell/*.ps1 (the helpers are in powershell/GdlApply.ps1).
For each: construct an input that SHOULD trip it, and confirm it actually trips. A guard
that never fires on any project in the corpus, or that filters away its own subject, is a finding.

Pay attention to: early continue/return in loops, filters applied before a check rather
than after, conditions that are unreachable given how the data is shaped, and checks that
compare a value to itself.`,
  },
  {
    key: 'silent-noop',
    prompt: `Hunt for code that reports success while doing nothing.

Places to look:
- Set-GdlFieldIfPresent (powershell/GdlApply.ps1) records a failure with Note-Problem and
  returns $true/$false. Every call site that pipes it to Out-Null discards that result.
  Which of those failures would ship a wrong panel?
- $LASTEXITCODE checked in some places and not others across powershell/*.ps1.
- try/catch blocks that Note-Problem and continue - does the caller ever act on
  $script:Problems, or does the pipeline exit 0 regardless? Note-Fatal also aborts the
  write: which Note-Problem calls describe a problem that leaves the file WRONG rather than
  merely incomplete, and so should have been Note-Fatal?
- Python: exception handlers that swallow, functions that return None on a path the caller
  treats as success, dict.get() with a default that masks a missing key.
- A loop that writes N things where the caller believes it wrote M.

For each candidate, show the path that leads to a wrong .gdl with a clean exit code.`,
  },
  {
    key: 'plan-contract',
    prompt: `The Python side emits a plan (JSON) and the PowerShell side applies it. Audit that
contract for DRIFT.

Build the full inventory both ways:
  - every key gdl/spec.py's Panel.plan() and gdl/edit.py's Edits.plan() can emit, at every
    nesting level
  - every key powershell/Apply-GdlPlan.ps1 and powershell/Apply-GdlEdits.ps1 actually read
  - every key tests/verify_built.py reads from the same plan (New-GdlPanel.ps1 hands it the
    plan), which is a third reader

Then find the mismatches:
  - emitted but never read (the instruction silently does nothing)
  - read but never emitted (dead branch, or a stale name from an older plan format)
  - same key, different meaning or type on the two sides
  - JSON numbers vs the .NET field's declared type (UInt16/UInt64/single/enum) - reflection
    neither widens nor narrows, and ConvertFrom-Json's typing is its own trap; the coercion
    both appliers share is Set-GdlFieldIfPresent in powershell/GdlApply.ps1
  - a key whose ABSENCE means something different from its presence-with-null
    (note: @($null) in PowerShell is an array of one null, not an empty array)

Generate real plans to work from; the specs in examples/ (panel.json, multipage.json,
clean-room.json, huddle.json) exercise different keys, so use more than one:
  python -m gdl.spec plan examples/panel.json <tmp>/plan.json
  python -m gdl.edit plan examples/retarget.json fixtures/gdl/<fixture>.gdl <tmp>/edits.json`,
  },
  {
    key: 'verifier-blindspots',
    prompt: `tests/verify_built.py is the last gate before a panel ships - New-GdlPanel.ps1 stops
unless it passes, and with an ID map tests/verify_idmap.py must pass too. So a blind spot in
either is the most expensive kind of bug here.

Enumerate everything the built layout.json carries that the verifier does NOT check. Read
the check_* functions in tests/verify_built.py first: that list, not this prompt, is what is
checked today. Then, for each gap, decide whether a plausible applier bug could produce a
wrong panel that still passes. Rank by that. docs/ROADMAP.md lists the blind spots already
known; report what it does not.

Look at what layout.json carries and cross each against the checks that exist: alignment,
transparency, image layout/alignment, key colors, blinking, DynamicText, FlattenText,
HideVisualFeedback, IsConfigurable, UserId, GroupID, TLPDefaultStateID, the popup group
tables, ScreenSize/PartNumber/Platform.

Also audit the checks that DO exist for weakness: _shares() ignores pixels with alpha<=250
and takes a plurality (_fill_shares() reads a translucent fill at its own alpha) - what wrong
panel survives that? WEAK_FILL is reported, not failed. check_fills only looks at controls
whose plan carries a painted fill. Does anything verify a control the plan did NOT mention,
i.e. donor leftovers riding along in a generated page?`,
  },
  {
    key: 'donor-inheritance',
    prompt: `Every generated control is a CLONE of a donor control, so it inherits every field
nobody thought to clear. Known cases already handled: TLPImageID, buttonImageField,
flattenTextField, backgroundImageField.

Systematically find the rest. Method: clone-by-hand in Python - take a real donor control
from a fixture, list every field it carries, and subtract the set of fields
powershell/Apply-GdlPlan.ps1 (and the helpers it shares in powershell/GdlApply.ps1)
explicitly sets or clears. What remains is inherited silently.

For each inherited field, judge whether it changes what the panel does or shows. Candidates
worth checking in the corpus: key colors, image layout/alignment/left/top, transparency,
blinking, ebusControlState, dynamic text, HideVisualFeedback/HidePressFeedback/HideTextFeedback,
IsConfigurable, IsHardwareBased, HwID, Comments, WasGroupIdEntered, and anything on PBState
beyond the handful the applier writes.

Compare a BUILT generated panel against its plan to see which inherited fields survived.
Built panels with their plans are kept in archive/gdlwork/ (Git LFS; usable() in
tests/_corpus.py says whether they are pulled), for example CleanRoom/CleanRoom.gdl with
CleanRoom/plan.json. They were built by earlier appliers, so a field that survived there
may be handled since. Otherwise build the comparison from a seed or fixture plus the plan
python -m gdl.spec plan gives for examples/panel.json.`,
  },
  {
    key: 'cross-theme',
    prompt: `The seeds cover several theme families, such as Afterburn, Mach, Shockwave,
Turbulence and Zoom Rooms, and a theme comes at several panel sizes and on more than one
platform; each seed's file name says which. Almost all of this repo's knowledge came from
Afterburn and from one client project.

Find what breaks on the OTHER themes and sizes. Concretely, for each project in the corpus,
run the repo's own tools and look for what fails, warns, or silently produces something odd:
  python -m gdl.spec donors examples/panel.json "<each project>"
  python -m gdl.spec donors examples/clean-room.json "<each project>"
  python -m gdl.themes "<each project>"
  python -m gdl.fonts "<each project>" <tmpdir>
  python -c "...Project.open(...); count pages, controls, states, resources..."

Look for: border/font resource names that differ by theme so a spec is only portable within
one family; control types missing from some themes (clone-never-construct means unauthorable);
the smallest canvases in the corpus (320x240, 320x480 and 480x320 among them) and the largest
breaking layout or touch-target assumptions; DPI handling; themes whose buttons carry state
names other than Off/On; anything in gdl/themes.py that only understands Afterburn's token
names.

The deliverable is: which of the repo's capabilities are actually Afterburn-only, and does
anything TELL the user that, or does it just quietly do the wrong thing?`,
  },
  {
    key: 'layout-math',
    prompt: `Audit the layout engine in gdl/spec.py - grid(), stack(), the nesting rules, id
allocation, and the numeric design-rule checks - for arithmetic that is wrong at the edges.

Specifically:
- grid/stack with gap large enough to exceed the rect; cols or rows of 0; 1 item; more items
  than cells; a nested directive whose parent cell is smaller than its own rect
- rounding: where does a fractional division get floor()ed, round()ed, or truncated, and can
  the last cell in a row end up outside the parent, or a 1px seam appear between cells?
- id allocation across pages and popups: can two controls collide, or an id exceed the
  UInt16 that userIdField is stored in?
- the touch-target and spacing checks: they convert mm to px via DPI. Check the arithmetic
  against docs/design-rules.md and against what the smallest and the largest canvases in the
  corpus actually need.
- per-page ID banding in renumber (gdl/edit.py)

Write property-style tests: generate many random-but-legal grid/stack specs, run them
through the planner, and assert every control lands inside its parent and no two overlap.
Randomness note: derive variety from a fixed seed or an index, not from Math.random.`,
  },
]

phase('Hunt')
log(`Hunt: ${DIMENSIONS.length} sonnet sweeps`)

const huntResults = await parallel(DIMENSIONS.map(d => () => agent(
  `${CONTEXT}

YOUR DIMENSION: ${d.key}

${d.prompt}

Work empirically. Read the code, form a specific suspicion, then TEST it against the corpus
and report what you actually observed. A finding without a command-and-output is not a finding.`,
  { label: `hunt:${d.key}`, phase: 'Hunt', model: 'sonnet', schema: FINDINGS_SCHEMA })))

claimResults.forEach((r, i) => {
  if (!r) {
    log(`falsify:${CLAIM_SOURCES[i].key} returned nothing, so ${CLAIM_SOURCES[i].where} is NOT covered`)
    uncovered.push(`falsify:${CLAIM_SOURCES[i].key}`)
  }
})
huntResults.forEach((r, i) => {
  if (!r) {
    log(`hunt:${DIMENSIONS[i].key} returned nothing, so that sweep is NOT covered`)
    uncovered.push(`hunt:${DIMENSIONS[i].key}`)
  }
})

// ---------------------------------------------------------------------------
// Barrier is correct here: dedup across the FULL result set before spending two
// adversarial verifiers per finding. Several dimensions overlap by design.
// ---------------------------------------------------------------------------
const RANK = { critical: 0, high: 1, medium: 2, low: 3 }
const CONF = { certain: 0, likely: 1, possible: 2 }

const raw = [...claimResults, ...huntResults]
  .filter(Boolean)
  .flatMap(r => r.findings || [])

const seen = new Map()
for (const f of raw) {
  const key = `${(f.file || '').toLowerCase().replace(/\\/g, '/')}::${(f.title || '')
    .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().split(' ').slice(0, 7).join(' ')}`
  const prev = seen.get(key)
  if (!prev || RANK[f.severity] < RANK[prev.severity]) seen.set(key, f)
}

const deduped = [...seen.values()].sort((a, b) =>
  (RANK[a.severity] - RANK[b.severity]) || (CONF[a.confidence] - CONF[b.confidence]))

log(`${raw.length} raw findings -> ${deduped.length} after dedup`)

const MAX_VERIFY = 16
const toVerify = deduped.slice(0, MAX_VERIFY)
if (deduped.length > MAX_VERIFY) {
  log(`verifying the top ${MAX_VERIFY} by severity; ${deduped.length - MAX_VERIFY} lower-ranked findings NOT verified and are reported separately as unverified`)
}

// ---------------------------------------------------------------------------
// Phase 4: two independent lenses per finding, both told to refute.
//
// Both lenses run on sonnet. Reproducing a command and judging what it shows, or
// reading the code around a finding to see whether it is already handled, is
// analysis that needs judgment but not deep reasoning, and a weaker model here is
// the safety net failing, so not haiku. This is also the largest fan-out (two
// agents per finding), so leaving the model unset would run whatever model the
// launching session has on most of the agents. Nothing in this script
// synthesizes: the session that launched it reads what it returns, which is the
// one place Opus belongs.
// ---------------------------------------------------------------------------
phase('Verify')

const LENSES = [
  {
    key: 'reproduce',
    ask: `Run their evidence command yourself. Does it actually produce what they claim?
Then ask whether the output really demonstrates the bug, or merely something adjacent.
A finding whose command does not run, or whose output does not show what is claimed,
is REFUTED.`,
  },
  {
    key: 'already-handled',
    ask: `Assume the finding is wrong because the codebase already handles this. Search for
the handling: a guard upstream, a caller that checks, a test that covers it, a comment
explaining why it is deliberate, or a data invariant that makes the bad case impossible.
Read the surrounding code properly rather than the one line quoted. If the bad path cannot
actually be reached in any real run of the pipeline, it is REFUTED.`,
  },
]

log(`Verify: ${toVerify.length * LENSES.length} sonnet agents (${LENSES.length} lenses x ${toVerify.length} findings)`)

const verified = await pipeline(
  toVerify,
  (f, _item, i) => parallel(LENSES.map(lens => () => agent(
    `${CONTEXT}

You are ADVERSARIALLY VERIFYING a reported bug. Your default is REFUTED. The reporter was
optimistic; your job is to be the reason a false finding does not reach the user.

  title:      ${f.title}
  file:       ${f.file}${f.line ? ':' + f.line : ''}
  class:      ${f.bug_class}
  severity:   ${f.severity}   (reporter's confidence: ${f.confidence})
  assumption: ${f.assumption}
  reality:    ${f.reality}
  impact:     ${f.impact}
  command:    ${f.evidence_command}
  claimed output:
${(f.evidence_output || '').split('\n').slice(0, 25).map(l => '    ' + l).join('\n')}

YOUR LENS - ${lens.key}:
${lens.ask}

Set reproduced=true ONLY if you personally ran something and saw the behavior. Guessing is
refuting. If it is real but the severity is inflated, set refuted=false and correct the
severity - overstating an impact is its own kind of wrong.`,
    { label: `verify:${lens.key}:${i + 1}`, phase: 'Verify', model: 'sonnet', schema: VERDICT_SCHEMA })))
    .then(votes => {
      const v = votes.filter(Boolean)
      // Unanimous survival required: two lenses, either one can kill it. A lens
      // whose agent died gave no verdict, so a finding no lens refuted that not
      // every lens judged is neither confirmed nor refuted: it is unverified.
      const refuted = v.some(x => x.refuted)
      const survives = !refuted && v.length === LENSES.length
      const corrected = v.map(x => x.severity_correction)
        .filter(s => s && s !== 'unchanged')
        .sort((a, b) => RANK[b] - RANK[a])[0]
      return {
        ...f,
        severity: corrected || f.severity,
        survives,
        refuted,
        reproduced: v.some(x => x.reproduced),
        verdicts: v.map(x => ({ refuted: x.refuted, reproduced: x.reproduced,
                                reasoning: x.reasoning, actual_output: x.actual_output })),
      }
    }),
)

const ok = verified.filter(Boolean)
const confirmed = ok.filter(f => f.survives)
  .sort((a, b) => (RANK[a.severity] - RANK[b.severity]))
const killed = ok.filter(f => f.refuted)
// Short of a verdict from every lens, or whose verification threw (null above):
// reported, never dropped and never counted as surviving.
const unjudged = ok.filter(f => !f.survives && !f.refuted)
  .concat(toVerify.filter((_, i) => !verified[i]))

log(`${confirmed.length} confirmed, ${killed.length} refuted by the adversarial pass` +
    (unjudged.length ? `, ${unjudged.length} not judged by every lens - reported as unverified` : ''))

if (uncovered.length) log(`NOT covered, because an agent died: ${uncovered.join(', ')}`)

return {
  confirmed,
  // What no agent got to: a clean hunt has this empty, a dead one does not.
  uncovered,
  refuted: killed.map(f => ({ title: f.title, file: f.file, severity: f.severity,
                              why: f.verdicts.filter(v => v.refuted).map(v => v.reasoning) })),
  unverified: unjudged.map(f => ({
    title: f.title, file: f.file, severity: f.severity, confidence: f.confidence,
    impact: f.impact, note: 'a verifying lens returned nothing - NOT fully adversarially checked' }))
    .concat(deduped.slice(MAX_VERIFY).map(f => ({
      title: f.title, file: f.file, severity: f.severity, confidence: f.confidence,
      impact: f.impact, note: 'over the verification cap - NOT adversarially checked' }))),
  counts: { raw: raw.length, deduped: deduped.length, verified: toVerify.length,
            confirmed: confirmed.length, refuted: killed.length, unjudged: unjudged.length,
            uncovered: uncovered.length },
}
