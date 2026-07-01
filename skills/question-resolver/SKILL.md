---
name: question-resolver
model: opus
effort: high
disable-model-invocation: true
description: Assisted closing of an open `question`-type GitHub issue. Evaluates the question and its thread against the project docs (especially hard constraints — regulatory / legal / contractual), discusses a decision with the operator, records the operator's approved decision as a durable `<!-- question-decision:v1 -->` comment, offers to close the issue, and produces detailed **proposals** for folding the decision back into the docs (state-now; never applied). It **does not make the decision** — the operator does — and it never edits docs. Explicit-invocation only — run it as `/github-pipeline:question-resolver <issue>`. Not a pipeline stage; not for build issues (that's `github-issue-resolver`) or for filing a new question (that's `github-issue-drafter`).
---

# Question resolver

The assisted-closing path for an open `question`-type issue. It grounds the question against the
project docs, helps the operator reach a decision, records that decision durably, and proposes how the
docs should change to reflect it — completing the open-question lifecycle (open → resolve → fold-back).

**The operator decides — never you.** This skill grounds the question, surfaces the constraints,
presents the viable options with a recommendation, and faithfully records the operator's call. It does
**not** choose the answer. This matters most because a question's `## Constraints` are often
regulatory/legal — the exact place a model must not decide silently. The "discuss with the operator"
step (Step 4) is where the decision is actually made.

**Two write surfaces only, both gated:** the durable **decision comment** (Step 6) and — offered, not
automatic — **closing the issue** (Step 7). Docs are **proposal-only**: Step 8 produces detailed,
cited, state-now change proposals; the operator applies them however they choose. This skill never
edits a doc.

Shared contracts (read as you reach the step that needs them):
[`../_shared/open-question-links.md`](../_shared/open-question-links.md) (the closing protocol + the
tiered status read + the decision marker), [`../_shared/question-issue.md`](../_shared/question-issue.md)
(the `question`-issue body schema it reads), [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md)
(the `AskUserQuestion` gate).

Use a scratch dir under `/tmp/gh-question-resolver-<N>/` for the staged decision comment and any
spilled gather output. Never write plugin-bundle paths.

## Step 1 — Fetch the question and detect a prior decision (reentrancy)

`gh repo view --json nameWithOwner -q '.nameWithOwner'`. Then fetch via `github-ops` — pass the
decision marker as the `marker_prefix` so the same call detects this skill's own prior run:

> `Agent(subagent_type: "github-pipeline:github-ops", no model override)` with
> `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- question-decision:v1 -->", scratch_dir=/tmp/gh-question-resolver-<N>/)`

From the result use: the body, thread (path or inline), `state`, labels (`question` + `audience:*`),
the native **`blocking`** list (the build issues this question gates), and the marker scalars
(`marker_comment_present` / `marker_comment_count` / `marker_comment_id`).

- **Not a `question` issue** (no `question` label / it's a build issue) → stop and say so; point at
  `/github-pipeline:github-issue-resolver` for build work.
- **Reentrancy** (this skill is reentrant — a re-run must revise, not duplicate):
  - `marker_comment_count == 0` → **fresh** run.
  - `marker_comment_count == 1` → **revise**: a prior decision exists. Capture `marker_comment_id`;
    show the operator what the prior decision said and reconcile against it. On re-post (Step 6) pass
    `delete_marker_id` so the old comment is replaced, not duplicated.
  - `marker_comment_count > 1` → `DECISION_NEEDED`: ambiguous which decision is current; ask the
    operator which to supersede before proceeding.
- **Already `closed`** → a re-run revises the decision comment in place; only offer `reopen` (Step 7)
  if the decision materially changes and the issue should be reopened for visibility.

## Step 2 — Read the thread's current state

Dispatch the existing question-status reader to distill the thread (keeps a long thread out of this
loop and classifies the entry condition). `Read` the reader prompt at
`${CLAUDE_PLUGIN_ROOT}/skills/open-questions/references/question-status-reader-prompt.md` (a raw-read
reference in another skill — use the plugin-root path, not a relative link), fill its `<<...>>`
placeholders (issue #, repo, body, thread — pass the scratch paths github-ops spilled, or inline
content), and dispatch it as an `Explore` sub-agent. It returns:

- `resolved-in-thread` — a stakeholder already answered. You will **formalize + verify** that answer
  (Steps 4–5), not invent a new one.
- `still-open` — no answer yet. You will **facilitate** a decision from the grounded options.
- `AMBIGUOUS` — the thread conflicts; surface it in Step 4 and let the discussion resolve it.

## Step 3 — Ground against the project docs

Read the docs the question's `## Constraints` and `## References` point at (targeted — not a blind
sweep of every doc), plus `docs/constitution.md` (the inviolable rules). Extract, with citations, the
**binding constraints** (regulatory/legal/contractual/architectural — `constitution §N`, `PRD §N`,
`architecture.md §X`, or `path/to/file:NN`) and the **decision space** (the viable options and what
each would commit the project to). Anti-fabrication: a constraint you can't cite to a doc §/line is
not a constraint — don't invent one. This grounding feeds the discussion; it does not decide anything.

## Step 4 — Present the evaluation and discuss (the operator decides)

Present, in one consolidated view:
- **Current state** — the Step 2 reading (answered-in-thread / still-open / ambiguous), with the
  distilled answer if one exists.
- **Viable option(s)** — each with its cited constraint implications from Step 3 (which options a
  constraint rules out, and why, with the doc citation).
- **Coverage gaps** — evaluate the substance that exists and flag what the decision-as-it-stands
  leaves unaddressed relative to the question's audiences/constraints (e.g. "the thread settles the
  business angle; nothing addresses the schema implication this `audience:architect` question also
  asks"). Flag gaps by **topic coverage** — do not attribute comments to audiences (a comment carries
  an author, not an `audience:*` role, so a comment→audience mapping isn't reliable).
- **Recommendation** — your grounded recommendation, clearly marked as a recommendation.

Then get the operator's decision via `AskUserQuestion` (per [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md))
or conversation. **The operator's call is the decision.** If the reading was `AMBIGUOUS`, or a
constraint rules out every option, surface that plainly — the question may need reframing or another
audience's input before it can be answered; don't force a decision.

## Step 5 — Verify the chosen decision against the constraints

Once the operator settles on a decision, verify it independently before recording — a constraint
missed in discussion is the failure mode with the highest cost here. `Read`
[`references/constraint-audit-prompt.md`](references/constraint-audit-prompt.md), fill its `<<...>>`
placeholders (the question incl. `## Constraints`, the **chosen decision**, repo root, the doc set),
and dispatch it as an `Explore` sub-agent. It returns cited findings with severity:

- A **BLOCKER** (the decision violates an inviolable/documented constraint) → return to Step 4: show
  the operator the finding and re-decide. Do **not** record a decision that trips a BLOCKER.
- **SUGGESTION / NIT** → surface them; they inform but don't gate.

## Step 6 — Record the decision (the answer)

Compose the decision comment, stage it to `/tmp/gh-question-resolver-<N>/decision.md`, and post via
`github-ops` (`PERSIST_COMMENT`) — passing `delete_marker_id=<marker_comment_id>` when Step 1 found a
prior decision (revise), so the old comment is replaced, not duplicated:

> `PERSIST_COMMENT(target=issue, id=<N>, repo=<owner/repo>, body_path=/tmp/gh-question-resolver-<N>/decision.md, delete_marker_id=<id if revising>)`

**Decision comment schema** (the `<!-- question-decision:v1 -->` marker is the first line — the durable,
machine-readable resolution the tiered status read short-circuits on):

```markdown
<!-- question-decision:v1 -->
## Decision
<the decision, stated plainly — what was decided>

## Rationale
<why — the reasoning, the option chosen over the alternatives>

## Constraints respected
<the binding constraints the decision honors, each cited — `constitution §N`, `PRD §N`, `path/to/file:NN`>

## Unblocks
<the build issues this answer unblocks (from the native `blocking` list), or "none">

## Caveats
<any coverage gap, provisional edge, or follow-up the decision leaves open — or omit if none>
```

Attribute the decision to the operator (it's their call, recorded by this skill). Never author a
decision the operator didn't approve.

## Step 7 — Offer to close the issue

Offer to close via `github-ops` (`PERSIST_CLOSE`) — gated, not automatic (some teams keep the question
open until the doc fold-back merges):

> `PERSIST_CLOSE(repo=<owner/repo>, issue=<N>, reason=completed)`

Closing an already-closed issue is a no-op, so this is safe on a re-run. In the rare reentrant case
where a materially-changed decision needs the issue reopened for visibility, offer `PERSIST_REOPEN`
first.

## Step 8 — Doc fold-back proposals (propose-only — never applied)

Assess which docs the decision touches and produce a **detailed proposal report** — you do **not**
edit the docs; the operator decides how to apply them. Because the docs are version-controlled, frame
every proposal as the **state now**, not a changelog ("Tags are matched case-insensitively." — not
"Changed the provisional rule to case-insensitive.").

Report format (mirrors `doc-reviewer`), one entry per affected doc/section:

```
### <doc path> §<section>
- Change: <the state-now edit to fold the decision in>
- Why: <the decision + citation it reflects>
```

Cover the fold-back moves defined in [`../_shared/open-question-links.md`](../_shared/open-question-links.md)
§"Doc fold-back" (rewrite to the decided state; remove the `PROVISIONAL` / open-question marker; flip
any register status + add the `tracked in #<N>` back-link) where each applies. If the decision touches
no docs, say so.

## Step 9 — Summary

Close with a plain summary (this is a utility skill — **not** a pipeline `## Handoff`):
- The decision recorded (comment URL) and whether the issue was closed.
- The doc fold-back proposals (which docs/sections) — for the operator to apply.
- The build issues this decision **unblocks** (the native `blocking` list). For each, breadcrumb the
  downstream step per the closing protocol — e.g. "`#<M>` was `blocked by` this; run
  `/github-pipeline:github-issue-planner <M>` (or the drafter in revise mode) to fold the decided
  scope in and remove the block." A pointer, not a forward handoff — this skill never crosses the
  session boundary or removes a block itself.
