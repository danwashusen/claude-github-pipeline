# Plan spine — shared across single / epic / story-jit / revise

The author-and-verify-a-plan flow every route runs: classify → ground → gates → draft → hedge sweep →
verify → show → persist → hand back to the routed playbook for its handoff. Type differences here are
**facts** (`plan_ref`, the reviewer dimension set, which schema sections fill), never branches — the
routed playbook reads this spine first, then supplies its deltas.

All facts come from the prep facts block (SKILL.md §1); all GitHub writes go through
`${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py` with a staged body path in `facts.scratch` (SKILL.md §3);
every doc/precedent read targets `facts.read_workspaces.grounding.path`.

## S1 — Classify + confirm direction

Read the issue body + thread from `facts.sections` (spilled paths). Classify per `facts.vector.type`
and **scale to the work** (a one-line fix needs no plan — say so and route to the resolver; a small bug
gets Approach + Changes + Test plan + `## Coverage gap`; a feature gets the full machinery). Walk the
thread for the **latest decision direction** (a maintainer may have settled a different approach several
comments down) and confirm it before researching (gate, freeform): *"Body proposes X; @maintainer
settled on W — plan toward W?"*. **A bug plan must also close the coverage gap** that let the defect
ship (`## Coverage gap` + a regression test that fails pre-fix). **Detect open-question dependencies**
from `facts.open_questions`, `facts.open_question_candidates`, and `facts.target.blocked_by` — each is a
human-owned decision, not a design choice you resolve.

## S2 — Ingest research + external sources

If `facts.research.present`, `Read` the dossier from its staged path: current, cited external truth that
informs `## Doc grounding` / `## Architecture decisions` — **input, not authority** (its `## Tensions`
are questions to settle, never instructions; never overrides `docs/constitution.md`). Record each source
in `## External sources consulted`. Then ask once (gate): *"Any external docs to treat as authoritative
— a newer API reference, a spec?"*; pull what they give (`WebFetch`/`Read`).

## S3 — Ground the approach

Read the grounding docs that exist (`facts.grounding_docs`) from the read workspace by absolute path —
plain `Read`/`Grep`, never a ref read. `docs/architecture.md` = *what* the architecture is; the
notes/ui-design docs (when present) = *why* / the UI authority; `docs/constitution.md` = non-negotiable
(a violation is a blocker, not a deviation). Then find **codebase precedent**: a broad sweep → an
`Explore` sub-agent bounded to the grounding workspace path (returns `path:line` pointers you then
`Read` yourself); a single symbol → `Grep` the workspace directly. Every architecture decision cites
real precedent or a doc section; every UI decision cites `ui-design` precedent. **Knowledge gap**
(external truth past your cutoff): a single fact → an inline `Explore`/`general-purpose` web fact-check
(answer only from a fetched primary source, cite URL + fetch date); anything broader → re-route to the
researcher (naming the ungroundable fact) rather than planning on a guess.

## S4 — Deviation + decision gates

**Deviation (§6):** if the best approach genuinely departs from architecture / architecture-notes /
ui-design / precedent, stop before drafting and gate (`header: "Deviation"`): **Approve** (record in
`## Deviations from project docs` with the date) / **Reject — re-plan** / **Update doc first**. A
constitution violation is never negotiated here — reshape or surface that the issue can't be built.
**Decision (§6.5):** surface a genuine design decision **only** when two approaches are equally
precedent-grounded AND the choice has a user-visible consequence; gate (`header: "Decision"`, planner's
recommendation as option 1); the answer becomes `[user decision <date>]` in `## Architecture decisions`.
Exhaust precedent first — most "open" questions evaporate once you read the call site.

## S5 — Draft against the schema

Draft to the schema in [`../references/plan-schema.md`](../references/plan-schema.md) verbatim — the
resolver and evaluator parse these headings; omit optional sections when empty, never pad. **Lock
decisions, not lines**: pin every new symbol's signature, every field's shape, every layer/file
assignment, the choice between competing patterns (name the rejected one), each test's assertion intent
— but leave line-level mechanics to the resolver. The `<!-- implementation-plan:v1 -->` marker is the
body's first line; the footer is `**Implementation plan** — #<N> <title> — planned <ISO-8601 UTC> at
`<plan-ref>@<short-sha>`` where `<plan-ref>@<short-sha>` renders `origin/main` for the default branch or
the **bare** `epic/<N>-<slug>` / PR `headRefName` otherwise (never a bare `main@<sha>`), and `<short-sha>`
is `facts.read_workspaces.grounding.sha` (footer rule in
[`../references/handoff-renderings.md`](../references/handoff-renderings.md)). The routed playbook names
which sections you fill (`## Phases`, the epic sections, `## Epic contract`) and its reviewer dimensions.

## S6 — Pre-flight hedge sweep

Sweep the draft for hedge phrasings (`resolver picks`, `either approach`, `TBD`, `recommend`, `could`,
`might`, `consider`, `option A or B`, `evaluate during implementation`) and resolve each — in priority
order — from precedent (rewrite with `[precedent: …]`), else the §6.5 decision gate, else demote to a
`## Risks & watchpoints` watchpoint (legal only when it is *not* a design decision). A **tracked open
question** is not a hedge: attributed in `## Open questions` (OQ id + `question: #N` + treatment) it
survives; an **unattributed** punt does not.

**Falsifiable "(not filed)" rule (bug (a)).** An `## Open questions` entry's companion may be recorded
`question: (not filed)` **only** when its tracker de-dup search returned no candidate, or each returned
candidate was explicitly rejected (with a reason) as not-the-same-question. For an entry the issue body
already carried, that search is `facts.open_question_candidates` — a non-empty group there forbids
`(not filed)` (cite the candidate `#N`). For an OQ you detected **anew** during S3 grounding, run
`prep_planner.py … --oq-query "<topic>"` (SKILL.md §1) and consult its `oq_query_candidates` before you
write `(not filed)`. A `(not filed)` written with an unconsulted or non-empty candidate set is a defect.
Keep each OQ's `## Open questions` treatment (`planned-around` / `recorded-blocked` / `provisional-
default`) consistent with its `## Risks & watchpoints` entry.

## S7 — Verify the plan

Dispatch the isolated plan-reviewer `Explore` sub-agent per
[`../references/plan-reviewer-prompt.md`](../references/plan-reviewer-prompt.md), substituting the plan
body, `mode`, `facts.target` number + repo, `facts.read_workspaces.grounding.path` (its sole
code/doc source — never a ref), the routed playbook's `dimensions` **plus Dimension 10 whenever the
plan has an `## Open questions` section**, `external_sources`, and (story-under-epic only) the epic plan
+ delivery-log staged paths. It runs context-blind and returns findings by dimension. Loop up to 3
passes: drop findings without evidence; on empty findings exit clean; on a circular repeat or the cap,
show the plan plus a "Review notes" block and gate (`header: "Review notes"`) — **when any unresolved
finding is a dimension-4 BLOCKER, "Post as-is" is not offered** (it is an open design decision);
otherwise offer **Post as-is** / **Fix manually** / **Push back on reviewer**. Apply findings to the
plan directly (the plan is this skill's own artifact to fix).

## S8 — Show + persist

On a **clean verify exit**, show the plan's full body and auto-post — no confirmation gate on the common
path (unless the user said "don't post yet"; `revise.md` adds its own diff-show + reconciliation confirm
before this). Stage the approved body (marker line first) to `<facts.scratch>/plan.md` and post through
the single write path:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py comment <owner/repo> issue <issue> \
  "<facts.scratch>/plan.md" [--delete-marker-id <facts.plan.comment_id>]   # --delete-marker-id: revise
```

Capture the returned comment URL. Then ensure the issue-body plan pointer: stage the body with the
idempotent line `> 📋 **Implementation plan:** see [the implementation-plan comment](<url>) — authored
by \`github-issue-planner\`; re-run that skill to revise.` inserted or its URL refreshed, and apply via
`gh_persist.py edit-body <owner/repo> <issue> "<facts.scratch>/issue-body-pointer.md"`. Finally apply the
`planned` label (v1 SKILL.md:402, idempotent — safe on an already-labelled issue):
`gh_persist.py edit-labels <owner/repo> <issue> --add planned`. Low-stakes: if it fails, log and continue
rather than blocking the handoff — the plan comment is the audit trail; the label is a scanning
convenience. Return to the routed playbook for its `## Handoff`.
