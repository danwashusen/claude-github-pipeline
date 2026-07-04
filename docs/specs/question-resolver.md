# question-resolver — v1 functional spec (baseline)

> Source: `skills/question-resolver/SKILL.md` (185 lines) + references:
> `references/constraint-audit-prompt.md` (71 lines).
> Captures v1 behavior as the parity baseline for [implementation.md](../implementation.md) S<cutover>.
> v1 skill name: `github-pipeline:question-resolver`; v2 name: `question-resolver`.

## Overview

The assisted-closing path for **one** open `question`-type GitHub issue: grounds the question
against project docs, helps the operator reach a decision, records that decision durably, and
proposes (never applies) the doc fold-back — completing the open-question lifecycle open → resolve
→ fold-back (`skills/question-resolver/SKILL.md:9-13`). Session shape: single standalone session,
explicit-invocation only (`disable-model-invocation: true`, `SKILL.md:5`), run as
`/github-pipeline:question-resolver <issue>` (`SKILL.md:6`). Input: one question-issue number.
Outputs: a `<!-- question-decision:v1 -->` decision comment (the sole write besides an optional
close/reopen), an optional issue close, and a doc-fold-back proposal report — ends with a plain
summary, **never** a pipeline `## Handoff` (`SKILL.md:178`). It never decides the answer and never
edits a doc itself — "the operator decides, the skill records" (`SKILL.md:15-19`).

## Artifacts written

| Artifact | Marker / schema | Lives in | Trigger |
|---|---|---|---|
| Decision comment | `<!-- question-decision:v1 -->` marker is the **first line**; body has `## Decision` / `## Rationale` / `## Constraints respected` / `## Unblocks` / `## Caveats` (`SKILL.md:121-140`) — quoted verbatim below | Question-issue comment, via `PERSIST_COMMENT` | Step 6, after the operator's decision (Step 4) passes the constraint audit clean of BLOCKERs (Step 5) (`SKILL.md:101-119`) |
| Issue close | No body — `PERSIST_CLOSE(repo=<owner/repo>, issue=<N>, reason=completed)` | Question-issue state | Step 7, offered (not automatic) after the decision is recorded (`SKILL.md:145-152`) |
| Issue reopen (rare) | No body — `PERSIST_REOPEN(repo=<owner/repo>, issue=<N>)` | Question-issue state | Step 7, only in the reentrant case where a materially-changed decision needs the closed issue reopened for visibility, offered before the close step (`SKILL.md:153-154`) |

Decision comment schema, quoted verbatim (`SKILL.md:124-140`):

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

This skill **never edits a project doc** — Step 8 is proposal-only (`SKILL.md:21-24`, `SKILL.md:156-158`).
The doc-fold-back report format (mirrors `doc-reviewer`) is:

```
### <doc path> §<section>
- Change: <the state-now edit to fold the decision in>
- Why: <the decision + citation it reflects>
```

## Artifacts read

| Artifact | Marker / location | What's extracted |
|---|---|---|
| Question-issue body + thread | Fetched via `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- question-decision:v1 -->", scratch_dir=/tmp/gh-question-resolver-<N>/)` | Body, thread (path or inline), `state`, labels (`question` + `audience:*`), native **`blocking`** list, `marker_comment_present`/`_count`/`_id` (`SKILL.md:37-45`) |
| `<!-- question-decision:v1 -->` prior decision comment | Question-issue comment | Reentrancy signal: `marker_comment_count` of 0/1/>1 drives fresh/revise/`DECISION_NEEDED` branching; `marker_comment_id` is captured for `delete_marker_id` on re-post (`SKILL.md:49-55`) |
| Question's `## Constraints` / `## References` | Question-issue body | The docs/sections to read at Step 3 for grounding (targeted, not a blind sweep) (`SKILL.md:75`) |
| Project docs (targeted) | `docs/constitution.md` plus whichever the question's `## Constraints`/`## References` name | Binding constraints (regulatory/legal/contractual/architectural, cited) and the decision space (viable options + commitments) (`SKILL.md:75-81`) |
| Native `blocking` list | `GATHER_ISSUE` result | The build issues this question gates — surfaced in the decision comment's `## Unblocks` and in the Step 9 summary breadcrumb (`SKILL.md:44`, `SKILL.md:136`, `SKILL.md:181-185`) |

## Operator gates

| Gate | Options | Effect |
|---|---|---|
| Step 1 — ambiguous prior decision (`marker_comment_count > 1`) | `DECISION_NEEDED`: ask which decision is current before proceeding (`SKILL.md:54-55`) | Blocks progress until the operator identifies the current decision |
| Step 4 — the decision itself | Via `AskUserQuestion` (per `skills/_shared/asking-the-user.md`) or conversation, over the presented current state / viable options / coverage gaps / recommendation (`SKILL.md:82-99`) | **The operator's call is the decision** — nothing downstream proceeds without it; if `AMBIGUOUS` or every option is constraint-ruled-out, the skill surfaces that and does not force a decision (`SKILL.md:97-99`) |
| Step 5 — BLOCKER re-decide loop | Return to Step 4 to show the finding and re-decide | A constraint-audit BLOCKER means the skill does **not** record the decision; it loops back rather than proceeding (`SKILL.md:109-110`) |
| Step 7 — offer to close | Offered via `PERSIST_CLOSE`, not automatic | Some teams keep the question open until the doc fold-back merges, so closing requires explicit confirmation (`SKILL.md:147`) |
| Step 7 — offer to reopen (reentrant case) | Offered via `PERSIST_REOPEN` before the close offer | Only surfaced when a materially-changed decision needs the already-closed issue visible again (`SKILL.md:153-154`) |

## Judgment steps (model reasoning — stays in the prompt)

- **Reentrancy classification** (Step 1) — fresh / revise / `DECISION_NEEDED` / already-closed
  branching from `marker_comment_count` and `state` (`SKILL.md:49-57`). Main-loop reasoning.
- **Thread-state distillation** (Step 2) — dispatches the question-status reader to classify entry
  condition as `resolved-in-thread` / `still-open` / `AMBIGUOUS`, determining whether the skill
  will *formalize+verify* an existing answer or *facilitate* a new one (`SKILL.md:59-71`). Isolated
  sub-agent: question-status reader (a raw-read cross-skill reference, not this skill's own file).
- **Doc grounding extraction** (Step 3) — reads the constraints/references-pointed docs plus the
  constitution and extracts cited binding constraints + the decision space; explicit
  anti-fabrication rule: an uncitable constraint is not a constraint (`SKILL.md:73-81`). Main-loop
  reasoning.
- **Evaluation presentation + recommendation** (Step 4) — composes the consolidated view (current
  state, viable options with cited constraint implications, coverage-gap analysis by **topic**
  (never attributing a comment to an audience role), and a clearly-marked recommendation)
  (`SKILL.md:83-95`). Main-loop reasoning.
- **Constraint-audit verification** (Step 5) — dispatches the isolated constraint-audit sub-agent
  to independently verify the chosen decision against documented constraints before it's recorded
  (`SKILL.md:101-111`). Isolated sub-agent: constraint-audit
  (`references/constraint-audit-prompt.md`).
- **Decision-comment composition** (Step 6) — writes the decision comment attributing the call to
  the operator, never authoring a decision the operator didn't approve (`SKILL.md:113-143`).
  Main-loop reasoning.
- **Doc-fold-back proposal drafting** (Step 8) — assesses which docs the decision touches and
  produces detailed, cited, state-now (not changelog-framed) change proposals per doc/section
  (`SKILL.md:156-174`). Main-loop reasoning.
- **Summary + downstream breadcrumb composition** (Step 9) — for each unblocked build issue,
  breadcrumbs the next step (planner or drafter revise) as a pointer, explicitly not a forward
  handoff (`SKILL.md:181-185`). Main-loop reasoning.

## Deterministic steps (candidate script work — moves to a prep/executor script)

- **Repo resolution** — `gh repo view --json nameWithOwner -q '.nameWithOwner'` (`SKILL.md:37`).
  Input: none. Output: `owner/repo`.
- **Question + thread fetch with reentrancy detection** — `GATHER_ISSUE(issue=<N>,
  repo=<owner/repo>, marker_prefix="<!-- question-decision:v1 -->",
  scratch_dir=/tmp/gh-question-resolver-<N>/)` (`SKILL.md:40-41`). Input: issue #, repo. Output:
  body/thread (inline or path), `state`, labels, `blocking`, marker scalars.
- **Not-a-question-issue check** — label inspection (absence of `question` label ⇒ stop and point
  at the resolver) (`SKILL.md:47-48`). Input: labels. Output: stop-or-continue branch (the
  *branch* itself is a judgment call at the boundary, but the label-presence check is mechanical).
- **Decision-comment staging + post** — stage to
  `/tmp/gh-question-resolver-<N>/decision.md`, then `PERSIST_COMMENT(target=issue, id=<N>,
  repo=<owner/repo>, body_path=…, delete_marker_id=<marker_comment_id if revising>)`
  (`SKILL.md:115-119`). Input: composed decision text. Output: comment URL, `body_bytes`,
  `body_sha256`; on revise, the script post-then-deletes the prior marker comment.
- **Close/reopen execution** — `PERSIST_CLOSE(repo=<owner/repo>, issue=<N>, reason=completed)` /
  `PERSIST_REOPEN(repo=<owner/repo>, issue=<N>)` (`SKILL.md:150-154`). Input: issue #, repo, reason.
  Output: `closed: true` / `reopened: true`; close on an already-closed issue is a `gh` no-op.

## Invariants (with the WHY)

- **The operator decides — never the skill.** Stated as the skill's lead invariant
  (`SKILL.md:15-19`). WHY: a question's `## Constraints` are often regulatory/legal — "the exact
  place a model must not decide silently" (`SKILL.md:18`).
- **Two write surfaces only, both gated: the decision comment and the offered close.** Docs are
  proposal-only (`SKILL.md:21-24`). WHY: keeps the skill's actual write footprint minimal and
  auditable — nothing happens to a doc without a separate, explicit human action outside this
  skill.
- **Verify before recording — the constraint audit runs on every decision, not just ones that
  "seem risky."** (`SKILL.md:101-111`). WHY: "a constraint missed in discussion is the failure mode
  with the highest cost here" (`SKILL.md:103`) — the operator reached the decision holding the full
  conversation, so from inside that context they can't reliably tell whether it quietly violates a
  documented constraint; the audit sub-agent is deliberately isolated from that conversation
  (`references/constraint-audit-prompt.md:5-7`).
- **A BLOCKER halts recording and returns to the discussion, never silently overridden.**
  (`SKILL.md:109-110`). WHY: an inviolable/documented constraint violation must be seen by the
  operator before anything durable is written.
- **Reentrancy: revise, never duplicate.** `marker_comment_count` of 0/1/>1 branches to
  fresh/revise/ambiguous; on revise, `delete_marker_id` is passed so the old comment is replaced
  (`SKILL.md:50-55`, `SKILL.md:116-119`). WHY: a re-run of this skill on the same question must not
  leave two competing decision comments — the tiered status read elsewhere in the pipeline treats
  `marker_comment_present` as a boolean fact, so duplicates would corrupt that signal.
- **Post-then-delete on the marker replace** (the underlying `PERSIST_COMMENT` mechanism, per
  `agents/github-ops.md:384-389`, invoked here via `delete_marker_id`). WHY: a failed post must
  never destroy the existing decision comment with no replacement — the same post-new-before-
  delete-old discipline the broader plugin convention calls out for the #626/#627 race.
  (Cross-referenced here because this skill is the one that exercises the revise path on a
  decision comment.)
- **Closing an already-closed issue is a safe no-op.** (`SKILL.md:152`). WHY: makes the skill safe
  to re-run without an extra guard — the reentrant caller doesn't need to check state before
  offering the close.
- **Coverage gaps are flagged by topic, never comment-to-audience attribution.** (`SKILL.md:92-93`).
  WHY: "a comment carries an author, not an `audience:*` role, so a comment→audience mapping isn't
  reliable" — stated verbatim as the reason to avoid a specific false-precision failure mode.
- **Doc fold-back is proposed as the state now, never a changelog.** (`SKILL.md:159-161`). WHY:
  the docs are version-controlled, so framing an edit as "changed X to Y" duplicates history the
  VCS already carries — the doc should read as true today, not as a diff narrative.
- **This skill never crosses the session boundary itself.** The Step 9 downstream breadcrumbs are
  explicitly "a pointer, not a forward handoff" (`SKILL.md:184-185`). WHY: consistent with
  session-per-skill and the no-auto-cross-boundary rule (`skills/_shared/open-question-links.md:147-148`)
  — no skill auto-reopens work when a question is answered; that decision is the human's.
- **Scratch dir under `/tmp/gh-question-resolver-<N>/`, never a plugin-bundle path**
  (`SKILL.md:32-33`). WHY: the plugin install directory is read-only at runtime.

## Sub-agents dispatched

| Sub-agent | Reference prompt file | Consumes | Returns |
|---|---|---|---|
| Question-status reader | `${CLAUDE_PLUGIN_ROOT}/skills/open-questions/references/question-status-reader-prompt.md` — a raw-read cross-skill reference, resolved via the plugin-root path rather than a relative link because it lives in another skill's directory (`SKILL.md:62-64`) | Issue #, repo, question body (path or inline), thread (path or inline) | `resolved-in-thread` / `still-open`, or the `AMBIGUOUS` exception (`SKILL.md:67-71`) |
| Constraint audit | `references/constraint-audit-prompt.md` (this skill's own reference) | Question # + repo, question body (incl. `## Constraints`), the **chosen decision**, repo root, doc set — explicitly **not** the conversation history, the operator's framing, or the skill's discussion notes (`references/constraint-audit-prompt.md:4-22`) | `## Constraint audit` block with `Findings: <n> blocker, <n> suggestion, <n> nit` and per-finding `Severity` / `Evidence` (doc §/line or `path:NN`) / `What's wrong` / `Remediation` (`references/constraint-audit-prompt.md:50-71`) |

The constraint audit's evidence rule is identical in spirit to the rest of the pipeline's
anti-fabrication bar: "a constraint you cannot cite to a doc is **not** a constraint — do not
invent one" (`references/constraint-audit-prompt.md:37-38`). It cannot call `AskUserQuestion` and
returns findings, never a decision (`references/constraint-audit-prompt.md:71`).

## Known bugs / gaps

None recorded in v1 source for this skill.
