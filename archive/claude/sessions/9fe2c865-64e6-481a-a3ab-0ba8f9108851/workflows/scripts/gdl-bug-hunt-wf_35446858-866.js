export const meta = {
  name: 'gdl-bug-hunt',
  description: 'Hunt latent bugs in extron-gdl-toolkit by falsifying code/doc claims against 19 real .gdl projects, then adversarially verify',
  phases: [
    { title: 'Extract', detail: 'haiku pulls every absolute claim out of docs, Python and PowerShell', model: 'haiku' },
    { title: 'Falsify', detail: 'sonnet tests each claim against all 19 real projects', model: 'sonnet' },
    { title: 'Hunt', detail: 'sonnet sweeps eight bug-class dimensions', model: 'sonnet' },
    { title: 'Verify', detail: 'adversarial refutation, two independent lenses per finding' },
  ],
}

const REPO = 'Z:/GitHub/rob-paprocki/extron-gdl-toolkit'
const SEEDS = 'C:/Users/Public/Documents/Extron/GUI Designer'

const CONTEXT = `
You are bug-hunting in a Python + PowerShell toolkit that reads and writes Extron
GUI Designer .gdl files. Repo root: ${REPO} (cd there first; run python from there).

READ-ONLY. Do not edit, create or delete any file in the repo. You are finding, not fixing.
You MAY write throwaway scripts to your temp dir and run them.

THE CORPUS - this is the point of the exercise:
  - ${REPO}/fixtures/gdl/*.gdl        6 real client projects (Liberty Bank)
  - "${SEEDS}"/*.gdl                  13 Extron theme templates, NEW as of today
    (Afterburn 1035/1230W/1535/300M Landscape/300M Portrait, Mach 1035/1535/300M Portrait,
     Shockwave 1035/1535, Turbulence 1035, Zoom Rooms Dark/Light ZRTP 1035)
Nearly every claim in this repo was inferred from ONE project (Liberty Bank). There are
now 19. Claims that were "always true" may be true only of that one project.

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

TWO BUGS FOUND TODAY, as calibration for the class of thing worth reporting:

1. PBStates.Count is a LOGICAL count, not the number of PBState objects - it returns 1 for
   an ordinary two-state Off/On button, while the indexer [0] and [1] both work. So every
   'for ($i=0; $i -lt $states.Count; $i++)' loop in both PowerShell appliers wrote state 0
   and stopped. Invisible from outside because TLPDefaultStateID is 0: the panel renders
   state 0, so the file looks perfect and only misbehaves once a control system switches it.

2. "A popup's authored size is always the whole canvas" was inferred from Liberty Bank,
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
          testable: { type: 'string', description: 'how you would falsify it against the 19 projects' },
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

const CLAIM_SOURCES = [
  {
    key: 'docs',
    where: 'docs/gdl-format.md, docs/from-scratch.md, docs/editing.md, docs/design-rules.md, SKILL.md, CLAUDE.md, README.md',
  },
  {
    key: 'python',
    where: 'every docstring and comment in gdl/*.py (spec.py, edit.py, project.py, compose.py, container.py, fonts.py, themes.py, data.py, nrbf.py, sfnt.py)',
  },
  {
    key: 'powershell',
    where: 'every comment block in powershell/*.ps1',
  },
]

phase('Extract')

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
it looks like it was inferred from the Liberty Bank fixture. Those are the ones that ship
wrong output.

Be thorough - this is extraction, not judgment. 30+ claims from the docs source is normal.`,
    { label: `extract:${src.key}`, phase: 'Extract', model: 'haiku', schema: CLAIMS_SCHEMA }),

  (extracted, src) => {
    const claims = (extracted?.claims || []).filter(c => c.risk !== 'low')
    if (!claims.length) return { findings: [] }
    return agent(
      `${CONTEXT}

Below are ${claims.length} claims extracted from ${src.where}. Your job is to FALSIFY them
against all 19 projects in the corpus. Not to confirm them - to find the ones that are
false, or true only of the Liberty Bank fixture.

${claims.map((c, i) => `${i + 1}. [${c.risk}] "${c.claim}"
   (${c.file}${c.line ? ':' + c.line : ''})  test: ${c.testable}`).join('\n')}

Method: write ONE Python script that loops over all 19 .gdl files and checks as many of
these claims as you can at once. Run it. Read the output. Then follow up on whatever looks
wrong. Prefer measuring over reasoning - the corpus is right there.

A claim being false is only a FINDING if code or documentation acts on it in a way that
produces wrong output, a wrong gate, or a wrong instruction to a future reader. Say which,
in 'impact'. If a claim is false but harmless, skip it.

Report only what you actually demonstrated.`,
      { label: `falsify:${src.key}`, phase: 'Falsify', model: 'sonnet', schema: FINDINGS_SCHEMA })
  },
)

const DIMENSIONS = [
  {
    key: 'collection-traps',
    prompt: `Hunt for more instances of the PBStates.Count class of bug: a .NET object whose
apparent size, length or emptiness LIES to the code reading it.

Go through powershell/*.ps1 and gdl/*.py and find every place that trusts a collection's
count, truthiness, enumerability or indexer without checking it against the underlying
storage. PBStates was one. PBPages, PBControls, PBResources, PBPopupPages, the ResourceSet,
and anything else Extron wraps are candidates.

You can settle these empirically. Under 32-bit PowerShell:
  C:\\Windows\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "..."
dot-source powershell/GdlProject.ps1, Initialize-Gdl, Open-GdlProject on an extracted
ProjectGCP, and compare .Count against the mItems list length for each wrapper type.
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

Look at every check in gdl/spec.py (check(), check_donor(), the design-rule checks),
gdl/edit.py (check()), tests/verify_built.py, and the Note-Problem calls in powershell/*.ps1.
For each: construct an input that SHOULD trip it, and confirm it actually trips. A guard
that never fires on any of the 19 projects, or that filters away its own subject, is a finding.

Pay attention to: early continue/return in loops, filters applied before a check rather
than after, conditions that are unreachable given how the data is shaped, and checks that
compare a value to itself.`,
  },
  {
    key: 'silent-noop',
    prompt: `Hunt for code that reports success while doing nothing.

Places to look:
- Set-GdlFieldIfPresent returns $true/$false. Every call site that pipes it to Out-Null is
  discarding a failure. Which of those failures would ship a wrong panel?
- $LASTEXITCODE checked in some places and not others across powershell/*.ps1.
- try/catch blocks that Note-Problem and continue - does the caller ever act on
  $script:Problems, or does the pipeline exit 0 regardless?
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
  - every key gdl/spec.py's plan() and gdl/edit.py's plan() can emit, at every nesting level
  - every key powershell/Apply-GdlPlan.ps1 and powershell/Apply-GdlEdits.ps1 actually read

Then find the mismatches:
  - emitted but never read (the instruction silently does nothing)
  - read but never emitted (dead branch, or a stale name from an older plan format)
  - same key, different meaning or type on the two sides
  - JSON numbers vs the .NET field's declared type (UInt16/UInt64/single/enum) - reflection
    neither widens nor narrows, and ConvertFrom-Json's typing is its own trap
  - a key whose ABSENCE means something different from its presence-with-null
    (note: @($null) in PowerShell is an array of one null, not an empty array)

Generate a real plan to work from:
  python -m gdl.spec plan examples/panel.json <tmp>/plan.json
  python -m gdl.edit plan examples/retarget.json fixtures/gdl/<fixture>.gdl <tmp>/edits.json`,
  },
  {
    key: 'verifier-blindspots',
    prompt: `tests/verify_built.py is the last gate before a panel ships - New-GdlPanel.ps1 exits 0
only if it passes. So a blind spot in it is the most expensive kind of bug here.

Enumerate everything the built layout.json carries that the verifier does NOT check.
Then, for each gap, decide whether a plausible applier bug could produce a wrong panel that
still passes. Rank by that.

Known-checked: geometry, captions, popup bindings, fill (via artwork), fonts, page
background, and as of today per-state feedback. Look at what else is in layout.json:
alignment, transparency, image layout/alignment, key colors, blinking, DynamicText,
FlattenText, HideVisualFeedback, IsConfigurable, UserId, GroupID, TLPDefaultStateID,
the popup group tables, ScreenSize/PartNumber/Platform.

Also audit the checks that DO exist for weakness: _shares() ignores pixels with alpha<=250
and takes a plurality - what wrong panel survives that? check_fills only looks at controls
whose plan carries a non-null fill. Does anything verify a control the plan did NOT mention,
i.e. donor leftovers riding along in a generated page?`,
  },
  {
    key: 'donor-inheritance',
    prompt: `Every generated control is a CLONE of a donor control, so it inherits every field
nobody thought to clear. Known cases already handled: TLPImageID, buttonImageField,
flattenTextField, backgroundImageField.

Systematically find the rest. Method: clone-by-hand in Python - take a real donor control
from a fixture, list every field it carries, and subtract the set of fields
powershell/Apply-GdlPlan.ps1 explicitly sets or clears. What remains is inherited silently.

For each inherited field, judge whether it changes what the panel does or shows. Candidates
worth checking in the corpus: key colors, image layout/alignment/left/top, transparency,
blinking, ebusControlState, dynamic text, HideVisualFeedback/HidePressFeedback/HideTextFeedback,
IsConfigurable, IsHardwareBased, HwID, Comments, WasGroupIdEntered, and anything on PBState
beyond the handful the applier writes.

Compare a BUILT generated panel against its plan to see which inherited fields survived:
there are recently built ones under the job temp dir, or build the comparison from
fixtures/gdl plus examples/panel.json's plan.`,
  },
  {
    key: 'cross-theme',
    prompt: `The 13 seed templates are six different theme families (Afterburn, Mach, Shockwave,
Turbulence, Zoom Rooms ZRTP, and the 300M small-panel variants). Almost all of this repo's
knowledge came from Afterburn and from one client project.

Find what breaks on the OTHER themes. Concretely, for each of the 19 projects, run the
repo's own tools and look for what fails, warns, or silently produces something odd:
  python -m gdl.spec donors examples/panel.json "<each project>"
  python -m gdl.spec donors examples/clean-room.json "<each project>"
  python -m gdl.themes "<each project>"
  python -m gdl.fonts "<each project>" <tmpdir>
  python -c "...Project.open(...); count pages, controls, states, resources..."

Look for: border/font resource names that differ by theme so a spec is only portable within
one family; control types missing from some themes (clone-never-construct means unauthorable);
the small 320x480 and 480x320 panels breaking layout or touch-target assumptions; DPI
handling; themes whose buttons carry state names other than Off/On; anything in gdl/themes.py
that only understands Afterburn's token names.

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
  against docs/design-rules.md and against what the 320x480 and 1920x1080 panels actually need.
- page numbering and banding in renumber

Write property-style tests: generate many random-but-legal grid/stack specs, run them
through the planner, and assert every control lands inside its parent and no two overlap.
Randomness note: derive variety from a fixed seed or an index, not from Math.random.`,
  },
]

phase('Hunt')

const huntResults = await parallel(DIMENSIONS.map(d => () => agent(
  `${CONTEXT}

YOUR DIMENSION: ${d.key}

${d.prompt}

Work empirically. Read the code, form a specific suspicion, then TEST it against the corpus
and report what you actually observed. A finding without a command-and-output is not a finding.`,
  { label: `hunt:${d.key}`, phase: 'Hunt', model: 'sonnet', schema: FINDINGS_SCHEMA })))

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
    { label: `verify:${lens.key}:${i + 1}`, phase: 'Verify', schema: VERDICT_SCHEMA })))
    .then(votes => {
      const v = votes.filter(Boolean)
      const survives = v.length > 0 && v.every(x => !x.refuted)
      const corrected = v.map(x => x.severity_correction)
        .filter(s => s && s !== 'unchanged')
        .sort((a, b) => RANK[b] - RANK[a])[0]
      return {
        ...f,
        severity: corrected || f.severity,
        survives,
        reproduced: v.some(x => x.reproduced),
        verdicts: v.map(x => ({ refuted: x.refuted, reproduced: x.reproduced,
                                reasoning: x.reasoning, actual_output: x.actual_output })),
      }
    }),
)

const ok = verified.filter(Boolean)
const confirmed = ok.filter(f => f.survives)
  .sort((a, b) => (RANK[a.severity] - RANK[b.severity]))
const killed = ok.filter(f => !f.survives)

log(`${confirmed.length} confirmed, ${killed.length} refuted by the adversarial pass`)

return {
  confirmed,
  refuted: killed.map(f => ({ title: f.title, file: f.file, severity: f.severity,
                              why: f.verdicts.filter(v => v.refuted).map(v => v.reasoning) })),
  unverified: deduped.slice(MAX_VERIFY).map(f => ({
    title: f.title, file: f.file, severity: f.severity, confidence: f.confidence,
    impact: f.impact, note: 'over the verification cap - NOT adversarially checked' })),
  counts: { raw: raw.length, deduped: deduped.length, verified: toVerify.length,
            confirmed: confirmed.length, refuted: killed.length },
}
