# The backlog, in order

The order in which Claude works through what `docs/ROADMAP.md` lists as its own.
The ROADMAP stays the home of each item, with what is left of it; this plan only
sequences them into pull requests, says where each runs, and names what waits on
the owner. Drawn from a read-only inventory of every open item against main at
#65 (2026-10-26): 164 items, of which about 90 are Claude's - 56 code and tests
only, 36 needing GUI Designer - 23 wait on the owner, 11 on a job, 1 on a
physical panel, and 16 are Extron's or decided against.

Where things run: code, tests, translates and reviews on the Linux box, several
workers at once, each package reviewed independently before it merges; builds
and probes in GUI Designer on the Windows host, one at a time. Each package is
one pull request, merged when CI is green and its review is clean, with its docs
in the same commit.

## In flight

| Package | What | Where |
|---|---|---|
| Afterburn's regions | Its working page as its template's five regions on every panel tier - the left rail, the 525's hub, the 320's foot strip - the kit's `Icons/PNG` drawings and its windows' art (`docs/superpowers/specs/2026-10-26-afterburn-regions-design.md`). Ten open questions taken at the design's recommended answers, recorded in the ROADMAP for the owner. | Linux, then a Windows build of round four's Afterburn room redrawn |

## Phase 1 - code and tests, in parallel on the Linux box

| # | Package | ROADMAP items it closes | Size |
|---|---|---|---|
| 1.1 | **Small refusals and stale docs, round two** | a panel listed twice; an empty Group refused at its name; translate waits for Open Sans to load and says when it did not; `compare` on one built file names a page it lacks; a popup in the Center's group without `role="source"` checked on every panel; a page-level `modal` refused; the seven-tab Header refusal pinned; a family named "... Bold" read by its family field; the ECP 16:10 presets reachable (`spec.sizes`); `verify_built` compares a popup's planned size with its built size; `Register-GdlPopupGroup` and `check_donor` guard a seed with no popup group; `Apply-GdlPlan.ps1` stops on a plan problem; `gdl.themes`' claim narrowed; and the stale statements the inventory found | M |
| 1.2 | **Rows and columns that re-space** | a row of loose controls opens its gaps as captions grow; a source popup's columns grown as one and its pitch kept per panel (Mach's Doc Cam on the 725); a window's body mapped at the target panel's title height; the 725's Footer gives way to a rail column a long caption widened | M+M |
| 1.3 | **The hub, small-panel grammar** | one region shared by a page's Groups on the 525, switched by a rail of group buttons; an icon on a Group's button; the hub's Display Control as a card per display, a later Section heading, the footer clock, window pictures; a canvas's own repeats (`sc-for`) laid out on other panels; the 320's dialer paged so no page holds one control | L |
| 1.4 | **IDs that survive more** | a hub window keyed by its host page and the template's window name, so a reordered canvas keeps its IDs | M |
| 1.5 | **Preview fidelity** | a face with no recovered file drawn from the seed that carries it (Roboto, Segoe UI, GUI Configurator, GUIC 1a); bold scored against the client fixtures' Forma ground truth; the preview's accuracy on authored panels measured over the archived builds and stated; a renamed formatted caption rendered and compared; the region pages scored against their templates rather than set beside them by eye | M+M |
| 1.6 | **CI and the skill** | the whole suite where hosted CI skips it (every seed and the kit, or a provisioned run); the PowerShell scripts parsed on every push; SKILL.md and the `extron-panel` skill name the region frame, the call mode and `translate --previous`; the bug hunt's second-verification workflow committed and its doc sources widened | M |
| 1.7 | **Call-mode cosmetics** | Shockwave's lit captions per variant; a key's words set where its template sets them past its glyph | S |

## Phase 2 - GUI Designer, serial on the Windows host, between Phase 1's builds

| # | Package | ROADMAP items it closes | Size |
|---|---|---|---|
| 2.1 | **Format probes on 1.28** | the probes' error and warning readout; a `renumber` through a build; a border outside the corpus and a same-page ID twin; Shockwave's 1535 tab twin; a horizontal slider with a non-square thumb; what `referenceCountField` does | M |
| 2.2 | **What the spec cannot say yet** | the Offline Page and its enable flag; a popup's auto-hide timeout; a reference bound to one popup by its ID, as the seeds' Volume Level is | M each |
| 2.3 | **The small panels' last refusals** | a modal that shows another modal (so a plain modal goes on past the 320's screen); a Clock on Shockwave's and Turbulence's 320 cloned from another seed of the theme; the recording and room-mode questions' words measured, and Mach's Recording tile; Shockwave's 725 call page's third launcher | M each |
| 2.4 | **Where a build spends its time** | a 23-page build timed per page, control, state and resource, with feature-flag mode on as the owner keeps it, on a quiet host, with and without scanning | M |
| 2.5 | **A synthetic fixture** | a many-page project of every renderer-scored control type, GUI Designer's snapshots of it, a new render baseline, the fixture-gated tests moved onto it - so the client fixtures can go, on the owner's word, and the text findings get ground truth beyond one typeface | L |
| 2.6 | **Seeds ahead of jobs** | the forms a client most often lists - 725M/C, 525M/C, 320C, 835, 1220/1225, 1025/1020, 1525MG, 720M/C, 1535T, Afterburn's 1520 and 535 - made in one session while the owner keeps the desktop connected | M |

## Phase 3 - proof

| # | Package | What |
|---|---|---|
| 3.1 | **Round five** | Fresh designers against the READMEs as they then stand, translated unchanged, refusals counted, then built - after Afterburn's regions and Phase 1.2-1.4, so it measures them |
| 3.2 | **The bug hunt again** | Over everything since its first run (#62's fixes, the call mode, Afterburn's regions, Phase 1), with its second verification in the same session |
| 3.3 | **The region frame on turned panels and the 300** | The turned frame's header as a left band and the 300's menu bar measured and drawn - when a job lists one, or once Phases 1-2 are done |
| 3.4 | **Research** | The size-dependent vertical text residual in the preview |

## What waits on the owner

None of these blocks the phases above; each is in the ROADMAP's *Yours*.

- **Load a built panel onto a TouchLink Pro panel**, and say how panels are loaded - the one step with no evidence.
- **Confirm or overrule** the assumptions already built: a mic mute and a display's state where the template keeps them; the footer cells the template stands together drawn as a joined set; a source popup's column of keys drawn at the template's row pitch kept at each panel's as a joined set; the 320's column headings in capitals; Afterburn's regions' ten answers.
- **Decide**: kit art or Extron's icon fonts for the small glyphs; whether a 320 key's caption may go below 14 pt (and the type floor's formula on the 535); whether the call mode's derived answers and tiles take the template's IDs; Open Sans Light; an empty caption on Mach's Share Content.
- **Approve** deleting the client fixtures once 2.5 has replaced them; schedule `~/gdltmp/nightly.sh` on the Linux box; pick a licence.
- **Larger calls**: a room whose panels are in two themes or two zones (a cross-canvas ID check); a Design front end for Teams and Zoom Rooms.

## What waits on a job

Seeds for forms 2.6 does not make, turned panels' seeds, Zoom and Teams Rooms seeds, and a fifteen-input room on Shockwave (whose bar templates have no Select Source page).
