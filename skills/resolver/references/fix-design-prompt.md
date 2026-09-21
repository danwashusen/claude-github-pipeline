# Fix-design sub-agent prompt (pre-edit seam re-derivation)

Dispatched from `review-fix-round.md` step 4, before the first edit of a round, when the round's findings
land on a **hot seam** — a file this review loop's own commits have already changed — or when the round's
fix plan fails its set check. A fix round carries a real defect rate: a retro counted 7 of 24 loop items
created by the loop's own fixes, five of them on one seam, where every fix changed a guard and each change
had a second-order effect on a sibling property nobody re-derived (`canSave` / `canAnswer` / `canEdit`
disagreeing for four rounds). The main conversation cannot see this reliably — by then it reasons forward
from its own prior fixes. This sub-agent is the fresh instrument, run **before** the edit rather than
after settle: an `Explore`-type judgment sub-agent (architecture.md §8) that re-derives the seam from its
final state and designs the change set. It designs; the main loop edits.

The orchestrator fills the `<<...>>` placeholders before sending. **Do not include the review-loop
history, prior `review` verdicts, prior round replies, the resolver's state summary, or any conversation
turns** — the design is only meaningful unanchored. `<<addressed_items>>` carries *surfaces* only (what
was changed where), never the reasoning behind a prior fix. The plan's phase list and decision bullets are
plan text, not history. The sub-agent is context-blind, cannot call `AskUserQuestion`, and never writes to
GitHub or the workspace. Checks 1–3 below are the design-side rendering of the fix disciplines whose
canonical statement lives in `common-pitfalls.md` — an edit there propagates here.

---

You are designing the fix for a set of review findings on code that has already been corrected at least
once. Earlier corrections on this code introduced new defects because each changed one guard without
re-deriving the properties that share it. Your job is to derive those properties from what the code now
*is*, then design a change set that keeps them all consistent. Do not edit anything.

## Inputs

- **Workspace**: `<<workspace_path>>` — the absolute path to the checkout holding the current state
  (`facts.workspace.path`). Every `Read` / `grep` you run names paths inside it. Do not read any other
  checkout, and do not run ref arithmetic.
- **Scope diff**: `<<diff_path>>` — this phase's changes (the review scope), staged to a file. Read it to
  learn what changed; read the workspace for what the code now says.
- **Loop-changed files**: `<<loop_files>>` — the files the review loop's own fix commits have changed
  this run (`(none)` when the dispatch came from a fix-plan conflict on untouched code).
- **Findings**: `<<findings>>` — the items to design, verbatim, one per bullet.
- **Already changed**: `<<addressed_items>>` — one-line surfaces earlier rounds changed (`(none)` on the
  first round). A finding on one of these is likely a second-order effect of that change.
- **Plan decisions**: `<<plan_decisions>>` — the plan's `## Architecture decisions` / `## UI decisions` /
  `## Deviations from project docs` bullets, verbatim. These are locked.
- **Phase context**: `<<phase_context>>` — the plan's `## Phases` list with the current phase marked. A
  seam a **later** phase ships is not in scope.

## What to do

If the diff file is missing or empty, return the single line `code: AMBIGUOUS` plus one sentence naming
what was missing, and stop.

1. **Map the seam.** For each finding, name the concept it touches (a guard, a flag, a state transition,
   a lifecycle event) and grep for every site that reads, writes, or gates on it — including sibling
   predicates whose rules must agree with it, and every call path (event handlers, timers, teardown,
   visibility or lifecycle callbacks) that can reach it. Findings sharing a seam share one map.
2. **Derive the rules.** For each property on the map, state the rule it must satisfy in terms of user- or
   caller-visible intent, from the code and the plan decisions — not from any comment you cannot
   re-derive. Where two siblings' rules currently disagree, that disagreement is the defect.
3. **Design at the class.** Prefer one rule stated once over a local guard at each site; when a new rule
   supersedes an existing local guard, delete the guard rather than leave both. Where a change splits an
   atomic call, name the properties the call carried and where each lands.
4. **Check second-order effects.** For every change, walk each other property on the map and each call
   path: does the change alter what it permits or when it fires? A change that fixes the finding and
   silently widens or narrows a sibling is not a design.

## Output format

Return markdown, nothing else:

- `## Seam` — per seam: the properties/sites (`<file>:<symbol>`), each with its one-line rule, and the call
  paths that reach it.
- `## Change set` — one bullet per finding:
  `<finding> — class: <every site> — change: <what, where> — preserves: <which seam rules> — removes: <superseded guards, or none>`.
  Concrete enough that a fixer can edit without re-deriving your analysis.
- `## Plan conflicts` — a finding whose correct fix reverses a plan decision: the finding, the decision
  bullet verbatim, and why. Design nothing for it. Empty section → say so.
- `## Out of reach` — a finding you could not design (the seam extends past what you could read, or the
  intent is genuinely ambiguous), with the reason. Empty section → say so.
