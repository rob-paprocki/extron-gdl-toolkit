export const meta = {
  name: 'gdl-verify-findings',
  description: 'Adversarially verify a file of bug-hunt findings with two default-refuted lenses each - the second, smaller workflow gdl-bug-hunt.js leaves its over-cap findings to',
  phases: [
    { title: 'List', detail: 'haiku reads the findings file for its ids', model: 'haiku' },
    { title: 'Verify', detail: 'sonnet, adversarial refutation, two independent lenses per finding', model: 'sonnet' },
  ],
}

// Input: args = {"findings": "<path to a JSON file>", "repo": "<absolute path of the checkout>",
//                "ids": ["U00", ...]}   (ids optional: all of the file's, when absent)
//
// The file is a JSON list of findings, each with an `id`, `title`, `file`, `severity`,
// `confidence` and `impact`, and where the reporter had them `assumption`, `reality`,
// `evidence_command` and `evidence_output` - the shape of
// archive/job-e823df9b/bug-hunt/hunt-unverified-distinct.json (the private archive
// only: tools/public_sync.py leaves archive/job-e823df9b out of the public copy, so
// there the shape is the one this sentence describes). Deduplicate before
// running (a finding reported by two dimensions is two verifications spent on one);
// `merges` records what a distinct entry stands for. A script has no filesystem, so
// each verifier reads its own finding from the file by id; nothing passes through
// this script's memory but the ids, so the haiku list step also returns each entry's
// title, file, impact and severity, and the result carries them whole.
//
// Same lenses, same default-refuted stance and same model as gdl-bug-hunt.js, which
// is the reason this exists: a finding verified here and one verified there mean the
// same thing. Output has the shape of hunt-verify2.json: confirmed, refuted, unjudged.
const FILE = typeof args !== 'undefined' && args && args.findings ? String(args.findings) : null
const REPO = typeof args !== 'undefined' && args && args.repo ? String(args.repo) : null
const GIVEN = typeof args !== 'undefined' && args && Array.isArray(args.ids) ? args.ids.map(String) : null
if (!FILE) throw new Error('pass args {"findings": "<path to the findings JSON>"} (and "repo" if the agents may start elsewhere)')

const ROOT = REPO
  ? `${REPO} (cd there first; run python from there)`
  : 'the directory you start in (run python from there)'

const CONTEXT = `
You are checking a reported bug in a Python + PowerShell toolkit that reads and writes
Extron GUI Designer .gdl files. Repo root: ${ROOT}.

READ-ONLY. Do not edit, create or delete any file in the repo. You MAY write throwaway
scripts to your temp dir and run them.

THE CORPUS: fixtures/gdl/*.gdl (real client projects, in the private archive only) and
seeds/*.gdl (themed seeds, Git LFS). Enumerate it yourself, and skip what is an un-pulled
LFS pointer:
  import glob, sys; sys.path.insert(0, '.'); sys.path.insert(0, 'tests')
  from _corpus import usable
  paths = [p for p in sorted(glob.glob('fixtures/gdl/*.gdl') + glob.glob('seeds/*.gdl')) if usable(p)]
Stream it - open one project, reduce it to facts, drop it - parsed projects are large.
The translator works on Design canvases (tests/data/design-*/, tests/data/round4-*/) and
the profiles gdl/designsys/*.json; running translate needs $GDL_DC_RUNTIME.

HOW TO READ A PROJECT (stdlib, from the repo root):
  from gdl.project import Project
  p = Project.open(path)
  for pg in p.pages():          # {'kind','id','name','size','controls':[...]}
      for c in pg['controls']: ...
  # the BUILT payload, the ground truth for what a panel shows:
  import json; from gdl.container import open_payload
  lay = json.loads(open_payload(path).read('layout.json').decode('utf-8-sig'))

The bugs worth confirming are those where THE CODE IS CONFIDENT AND THE FORMAT DISAGREES
and nothing fails loudly. Style, naming, a missing test and anything docs/ROADMAP.md lists
as a known gap are not bugs.`

const ENTRY_SCHEMA = {
  type: 'object',
  properties: {
    id: { type: 'string' }, title: { type: 'string' }, file: { type: 'string' },
    impact: { type: 'string' }, severity: { type: 'string' },
  },
  required: ['id'],
}

const LIST_SCHEMA = {
  type: 'object',
  properties: { entries: { type: 'array', items: ENTRY_SCHEMA } },
  required: ['entries'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean', description: 'true if the finding is wrong, already handled, or unprovable' },
    reasoning: { type: 'string' },
    reproduced: { type: 'boolean', description: 'did you personally run something and see the claimed behavior' },
    actual_output: { type: 'string', description: 'what you saw when you ran it' },
    severity_correction: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'unchanged'] },
  },
  required: ['refuted', 'reasoning', 'reproduced'],
}

const RANK = { critical: 0, high: 1, medium: 2, low: 3 }

phase('List')
const listed = await agent(
  `Read ${FILE} (a JSON list; run python from ${ROOT} to load it). For every entry, in file order,
return its \`id\` exactly as written (its zero-based position as a string if it has none), and its
\`title\`, \`file\`, \`impact\` and \`severity\` copied verbatim. Return nothing else.`,
  { label: 'list', phase: 'List', model: 'haiku', schema: LIST_SCHEMA })
const entries = listed?.entries || []
if (!entries.length) throw new Error(`no findings to verify: ${FILE} listed none, so nothing was checked`)
const byId = new Map(entries.map(e => [e.id, e]))
// An id the caller named that the file does not hold is a mistake in the input, not a
// finding the verifiers refuted: stop before spending a single agent on it.
const unknown = GIVEN ? GIVEN.filter(i => !byId.has(i)) : []
if (unknown.length) throw new Error(`ids not in ${FILE}: ${unknown.join(', ')} (it holds ${entries.map(e => e.id).join(', ')})`)
const ids = GIVEN || entries.map(e => e.id)

const LENSES = [
  {
    key: 'reproduce',
    ask: `Run their evidence command yourself where they gave one; where they gave none, build the
smallest command of your own that would show the behavior. Does it actually produce what is
claimed? Then ask whether the output really demonstrates the bug, or merely something
adjacent. For a claim about what a .gdl file holds or how the toolkit reads one, a finding
that cannot be demonstrated against a real file in the corpus is REFUTED. A finding about
PowerShell or a document is judged on its own evidence instead - the script's text, what a
doc says against what the code does - and is refuted only if that evidence does not show
the defect (a PowerShell finding you cannot run on this host is not thereby refuted: read it).`,
  },
  {
    key: 'already-handled',
    ask: `Assume the finding is wrong because the codebase already handles this. Search for the
handling: a guard upstream, a caller that checks, a test that covers it, a comment explaining
why it is deliberate, or a data invariant that makes the bad case impossible. Read the
surrounding code properly rather than the one line quoted. If the bad path cannot actually
be reached in any real run of the pipeline, it is REFUTED.`,
  },
]

phase('Verify')
log(`Verify: ${ids.length * LENSES.length} sonnet agents (${LENSES.length} lenses x ${ids.length} findings)`)

const results = await pipeline(
  ids,
  (id, _item, i) => parallel(LENSES.map(lens => () => agent(
    `${CONTEXT}

You are ADVERSARIALLY VERIFYING a reported bug. Your default is REFUTED. The reporter was
optimistic; your job is to be the reason a false finding does not reach the user.

The finding is the entry with id ${JSON.stringify(id)} in ${FILE}. Read that entry (title, file,
severity, impact, and assumption / reality / evidence where present) and nothing else of the file.

YOUR LENS - ${lens.key}:
${lens.ask}

Set reproduced=true ONLY if you personally ran something and saw the behavior. Guessing is
refuting. If it is real but the severity is inflated, set refuted=false and correct the
severity - overstating an impact is its own kind of wrong.`,
    { label: `verify:${lens.key}:${id}`, phase: 'Verify', model: 'sonnet', schema: VERDICT_SCHEMA })))
    .then(votes => {
      // Keep each verdict with the lens that gave it, then drop the dead agents: indexing
      // LENSES after the filter would credit a verdict to the wrong lens.
      const given = votes.map((x, k) => (x ? { x, lens: LENSES[k].key } : null)).filter(Boolean)
      const v = given.map(g => g.x)
      // Either lens can kill it; a lens whose agent died gave no verdict, so a finding
      // no lens refuted that not every lens judged is unjudged, never confirmed.
      const refuted = v.some(x => x.refuted)
      const corrected = v.map(x => x.severity_correction)
        .filter(s => s && s !== 'unchanged')
        .sort((a, b) => RANK[b] - RANK[a])[0]
      const e = byId.get(id) || { id }
      return {
        id, title: e.title, file: e.file, impact: e.impact, original_severity: e.severity,
        reproduced: v.some(x => x.reproduced),
        refuted,
        survives: !refuted && v.length === LENSES.length,
        severity: corrected || null,
        lenses_returned: v.length,
        verdicts: given.map(({ x, lens }) => ({ lens, refuted: x.refuted, reproduced: x.reproduced,
                                                reasoning: x.reasoning, actual_output: x.actual_output })),
      }
    }),
)

const ok = results.filter(Boolean)
const confirmed = ok.filter(f => f.survives)
const refuted = ok.filter(f => f.refuted)
const unjudged = ok.filter(f => !f.survives && !f.refuted).map(f => f.id)
  .concat(ids.filter((_, i) => !results[i]))

log(`${confirmed.length} confirmed, ${refuted.length} refuted` +
    (unjudged.length ? `, ${unjudged.length} not judged by every lens: ${unjudged.join(', ')}` : ''))

return {
  confirmed, refuted, unjudged,
  counts: { total: ids.length, confirmed: confirmed.length, refuted: refuted.length, unjudged: unjudged.length },
}
