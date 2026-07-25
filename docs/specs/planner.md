# planner — v1 functional spec (baseline)

> Source: `skills/github-issue-planner/SKILL.md` (503 lines) + references: `handoff-renderings.md`
> (160 lines), `plan-reviewer-prompt.md` (178 lines), `plan-schema.md` (139 lines),
> `revise-reconciliation.md` (70 lines).
> Captures v1 behavior as the parity baseline for [implementation.md](../implementation.md) S13
> (planner rewrite) and S12 (`prep_planner.py` deterministic tracker search).
> v1 skill name: `github-issue-planner`; v2 name: `planner`.

## Overview

Turns a filed GitHub issue (or an Epic and its stories) into a verified, durable **implementation
plan** posted as an `<!-- implementation-plan:v1 -->` issue comment, before any code is written.
The plan locks the architectural approach, layer assignments, file-level changes, data-model
impact, and test strategy so the resolver executes a vetted design instead of re-deriving it. Runs
as its own Claude Code session (`model: opus`, `effort: xhigh`), fetches issue state and posts via
the `github-ops` sub-agent, grounds every decision in codebase precedent and project docs read at
an explicit `plan_ref`, and verifies the drafted plan with an isolated `Explore` review sub-agent
(up to 3 passes) before posting. Ends every clean run with a `## Handoff` block routing to the next
session (usually the resolver).

## Artifacts written

| Artifact | Marker / schema | Location | Section+heading set (order) | Trigger |
|---|---|---|---|---|
| Implementation plan (single-issue / bug / feature) | `<!-- implementation-plan:v1 -->` as first line of comment body (SKILL.md:208, plan-schema.md:6) | issue comment | `## Approach`, `## Doc grounding`, `## Architecture decisions`, `## UI decisions` (omit if no UI), `## Changes (file-level)`, `## Data model / schema impact` (omit if none), `## Test plan`, `## Coverage gap` (bug fixes only), `## Phases` (multi-phase only), `## External sources consulted` (omit if none), `## Deviations from project docs` (omit if none), `## Risks & watchpoints`, `## Open questions` (omit if none), closing provenance footer (plan-schema.md:6-109) | Step 10, on a clean verify exit (Step 8) or after the cap/circular decision |
| Implementation plan (Epic) | Same marker; replaces `## Phases` with Epic-only sections | issue comment (on the Epic issue) | After `## Approach`: `## Story breakdown`, `## Story contracts`, `## Integration strategy` (plan-schema.md:117-127), then the standard `## Doc grounding` … `## Open questions` tail | Step 11.1, epic-level plan authored up front |
| Implementation plan (story under an Epic) | Same marker; `**Epic:** #<epic-#> — <epic title>` is the **first line after** the marker (SKILL.md:226-234, plan-schema.md:129) | issue comment (on the story issue) | Standard single-issue schema **plus** `## Epic contract` (`Delivers:` / `Consumes:`, each `[epic-plan: #<N>]`-cited) (plan-schema.md:132-135) | "Just-in-time story planning" step 6, per story, authored just-in-time against current epic HEAD — never fanned out up front |
| Plan comment body first line (always) | `<!-- implementation-plan:v1 -->` | issue comment | — | Every post/repost; consumers locate the plan via `startswith` |
| Plan footer / provenance line | `**Implementation plan** — #<N> <title> — planned <ISO-8601 UTC> at \`<plan-ref>@<short-sha>\`` (plan-schema.md:7) plus closing paragraph `_Authored by \`github-issue-planner\` and verified in <N> review pass(es). ... Re-run this skill to revise — do not hand-edit._` (plan-schema.md:107-109) | issue comment (same comment) | Top line of body; footer at end | Every post |
| Issue body plan pointer | `> 📋 **Implementation plan:** see [the implementation-plan comment](<plan-comment-url>) — authored by \`github-issue-planner\`; re-run that skill to revise.` (SKILL.md:395) | issue body | one blockquote line, idempotent (`mode=pointer`) | Step 10, after `PERSIST_COMMENT` succeeds |
| `planned` label | GitHub label `planned` (color `FBCA04`, description `"Implementation plan posted by github-issue-planner"`) (SKILL.md:402-412) | issue labels | — | Step 10, after `PERSIST_COMMENT` succeeds; idempotent; skipped entirely on the trivial-skip branch (no plan authored) |
| `## Predecessor` section (HARD re-plan only) | Plain heading, no marker (SKILL.md's `revise-reconciliation.md:56-61`) | new plan comment, inserted immediately after `## Approach` | `## Predecessor` naming the closed PR #, close date, preserved branch name, one-line rationale | Revise-mode HARD path "Start fresh", step 3 |
| Reconciled issue body (`## Definition of done` annotations) | DoD checkbox annotation forms per `_shared/dod-annotations.md` — planner writes the SOFT-path re-attribution forms and the HARD-path `(previously claimed by phase <N>, commit <sha> on closed PR #<M>)` predecessor annotation (revise-reconciliation.md:34-63) | issue body | — | Revise mode, step 5, after user confirms the reconciliation diff |
| `## Handoff` block | Schema in `_shared/handoff-format.md`; planner-specific renderings in `references/handoff-renderings.md` | session output (not a GitHub artifact) | `**Issue:**/**Epic:**/**Story:**`, `**Grounding:**` (planner-specific — `read at <plan-ref>@<short-sha> · <docs> · external: … · full detail in the plan's ## Doc grounding`), `**Open questions:**` (optional), `**Next:**`, fenced command, `**Why:**` | Step 12, end of every clean exit |

## Artifacts read

| Artifact | Marker | Where | What's extracted |
|---|---|---|---|
| Issue body + full comment thread | — | issue | latest decision direction (thread supersedes stale body proposals), classification signals, `## Open questions` section (via `<!-- open-question-links:v1 -->`), native `blocked_by` |
| Prior plan comment (revise-mode trigger) | `<!-- implementation-plan:v1 -->` | issue comment | `marker_comment_present` flags revise mode; its `id` becomes `delete_marker_id` at repost; `marker_comment_count > 1` forces `DECISION_NEEDED` |
| Research dossier | `<!-- issue-research:v1 -->` | issue comment | current, fetched external truth with provenance (source + fetch date); feeds `## Doc grounding` / `## Architecture decisions`; its `## Tensions for the planner to resolve` are settled, never taken as instruction (SKILL.md:104-122) |
| Epic body + `## Stories` list | — | epic issue (via `GATHER_EPIC`) | ordered story list (`{number, title, checked, state}` or plain-bullet flag), resolved `epic/<N>-<slug>` branch, named-dependency landed flag |
| Epic plan (for a story under it) | `<!-- implementation-plan:v1 -->` | epic issue comment | `## Approach`, this story's `## Story contracts` entry (delivers/consumes), `## Story breakdown` |
| Epic delivery log | `<!-- epic-delivery-log:v1 -->` | epic issue comment | per-story actually-delivered contract shapes, `@ commit-sha`, PR #, merge date — reconciled against the epic plan's *pinned* contracts before a story is grounded (`_shared/epic-delivery-log.md`) |
| Open PR for this issue | — | PR | `headRefName` (becomes `plan_ref` per the Step 4.5 table), body, `## Phase tracker` (revise mode) |
| `question`-type tracker issues | `question` / `audience:*` labels; `<!-- question-decision:v1 -->` comment | issue state/comments | Tier-1/Tier-2 tiered status read (`_shared/open-question-links.md` §"Status is the tracker's") — whether an OQ the plan planned around is now resolved |
| Project docs at `plan_ref` | — | `docs/architecture.md`, `docs/architecture-notes.md`, `docs/ui-design.md`, `docs/constitution.md`, `CLAUDE.md`, `docs/prd.md` | grounding citations for every architecture/UI decision; read via `git show <plan_ref>:<path>`, never the working tree |
| Codebase at `plan_ref` | — | source tree | precedent for architecture decisions, symbol/signature confirmation |

## Operator gates

| Gate | Step | Asked via | Options | What each does |
|---|---|---|---|---|
| Latest-decision-direction confirmation | 3 | prose ("Body proposes X; @maintainer settled on W — correct?") | free-form correction | Confirms which thread direction to plan toward before research begins |
| External sources | 4 | prose | paste URLs/paths, or none | Anything supplied is treated as authoritative over training knowledge; recorded in `## External sources consulted` |
| Deviation from docs/precedent | 6 | `AskUserQuestion`, header `"Deviation"` | **Approve** (record in `## Deviations from project docs` with agreement date) / **Reject — re-plan** (drop the deviation) / **Update doc first** (doc edit becomes a prerequisite) | Gates any genuine departure from architecture/architecture-notes/ui-design/precedent. A constitution violation is never offered here — it's not negotiable |
| Genuine design decision (Decision gate) | 6.5 | `AskUserQuestion`, header `"Decision"` | 2–4 named-approach options, planner's recommendation as option 1 | Only surfaced when two approaches are equally precedent-grounded AND the choice has a user-visible consequence; the answer becomes `[user decision <date>]` in `## Architecture decisions`, binding until a step-9 revise |
| Review-notes disposition (dimension-4 BLOCKER present) | end of Step 8 | `AskUserQuestion`, header `"Review notes"` | **Surface as decision gate** / **Fix manually** / **Push back on reviewer** — "Post as-is" is **not** offered | A dimension-4 (implementation readiness) BLOCKER is by definition an open design decision; posting it would reintroduce the planner→resolver→planner round-trip |
| Review-notes disposition (only dims 1/2/3/5/6 unresolved) | end of Step 8 | `AskUserQuestion`, header `"Review notes"` | **Post as-is** / **Fix manually** / **Push back on reviewer** | Non-dimension-4 findings may be accepted as watchpoints or doc-deviation entries |
| Show plan before posting (opt-in) | 9 | user's own prompt phrasing ("draft the plan, but don't post yet") | pause for confirmation | Overrides the default auto-post-on-clean-exit behavior |
| Revise-mode reconciliation confirm (SOFT) | Revise step 5 | `AskUserQuestion` | **Apply** / **Cancel** | Applies the reconciled body-edit diff alongside the refreshed plan |
| Revise-mode reconciliation confirm (HARD) | Revise step 5 | `AskUserQuestion` | **Start fresh (recommended)** / **Apply in place anyway** / **Cancel** | Start fresh closes the old PR, un-ticks DoD with predecessor annotations, adds `## Predecessor`; "Apply in place" keeps the same PR despite the shipped-phase mismatch |

## Judgment steps (model reasoning — stays in the prompt)

- **Classify type** (bug / incomplete / feature / epic / story) and **scale to the work** (trivial vs full machinery vs small-bug-shaped plan) — Step 3, main loop.
- **Classify multi-phase vs Epic** — Step 3, main loop; the rule of thumb (distinct trackable user-facing deliverables vs sequential beats of one indivisible piece) is judgment, not a mechanical test.
- **Route by shape** (Epic / story-under-epic / everything-else) — Step 3, main loop.
- **Detect open-question dependencies** and record disposition/treatment — Step 3, main loop, per `_shared/open-question-detection.md` and `_shared/open-question-links.md`.
- **Research and ground the approach** (Step 5) — reading docs + codebase precedent at `plan_ref`, deciding layer assignments, citing `[precedent: …]`. Broad sweeps delegate to an **`Explore`** sub-agent with a focused prompt (no dedicated reference file — an inline prompt naming symbols/patterns/doc sections and asking for `path:line` pointers); narrow single-symbol lookups stay in the main loop.
- **Knowledge-gap handling** — Step 5, main loop decides depth: a single quick fact spawns an inline **`Explore`**/**`general-purpose`** web-research sub-agent (ad hoc prompt: the exact question + pinned dependency version + "answer only from a fetched primary source"); anything broader re-routes to `github-issue-researcher` entirely (no in-session sub-agent).
- **Surface deviations** (Step 6) and **surface genuine design decisions** (Step 6.5) — main loop, deciding when precedent can decide autonomously vs when a user gate is warranted.
- **Draft the plan** against the schema (Step 7) — main loop; this is the core "lock decisions, not lines" judgment call throughout `## Architecture decisions`, `## Changes`, `## Data model / schema impact`, `## Test plan`, `## Coverage gap`, `## Phases`, `## Open questions`.
- **Pre-flight hedge sweep** (Step 7.5) — main loop; grep-driven, but the resolution of each hit (resolve from precedent / surface as Decision gate / demote to watchpoint / recognize as a tracked-OQ carve-out) is judgment.
- **Verify the plan** (Step 8) — delegated to an isolated **`Explore`**-type review sub-agent, prompt at `references/plan-reviewer-prompt.md`. Runs up to 3 passes with `drop_findings_without_evidence` / circular-repeat / cap-reached exit logic (SKILL.md:340-353). This is the plan's own dedicated fresh-implementer read, distinct from the ad hoc `Explore` dispatches above.
- **Apply findings** from the review sub-agent directly to the plan — main loop (unlike the resolver, which routes findings to the drafter, the planner owns its own artifact and fixes it in place).
- **Epic plan authoring** (Step 11.1) — main loop: `## Approach`, `## Story breakdown`, `## Story contracts`, `## Integration strategy`, `## Definition of done` grounding.
- **Just-in-time story planning** (dedicated mode) — main loop, including the "reconcile contracts against what actually shipped" judgment (step 3 of that mode) that decides whether to re-route to the planner-on-the-epic in revise mode.
- **Revise-mode SOFT vs HARD classification** — main loop, LLM judgment bounded by structural rules (`references/revise-reconciliation.md`); some cases ("Changes block text edits", "DoD bullet wording adjustments") are explicitly named judgment calls that lean HARD when ambiguous.
- **Compose the `## Handoff`** (Step 12) — main loop; mechanical snapshot fields plus judgment `Next:`/`Why:` authorship, per `references/handoff-renderings.md` (forced `Read` before composing).

## Deterministic steps (candidate script work — moves to a prep/executor script)

- **Fetch issue + thread + prior plan comment lookup** — `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- implementation-plan:v1 -->", scratch_dir=/tmp/gh-planner-<N>/)` via `github-ops`. Input: issue number + repo. Output: metadata scalars, `issue_body_path`/`thread_path`, `marker_comment_id`/`_url`/`_path`/`_present`/`_count`, `open_prs`, native `blocked_by`/`blocking`/`deps_available`.
- **Fetch epic reconnaissance** — `GATHER_EPIC(epic=<N>, repo=<owner/repo>, dependency=<…>, scratch_dir=…)` via `github-ops`. Output: `epic_body_path`, parsed `## Stories` list, resolved `epic/<N>-<slug>` branch, dependency-landed flag.
- **Targeted research-dossier fetch** — `gh api "repos/<owner/repo>/issues/<N>/comments" --jq 'first(.[] | select(.body | startswith("<!-- issue-research:v1 -->")) | .body) // ""'`, written to `research.md` (SKILL.md:111-113). Input: issue number + repo. Output: dossier body or empty file.
- **Derive `plan_ref`** (Step 4.5) — a pure lookup table keyed on issue context (regular issue → `origin/main`; epic-as-target → `epic/<N>-<slug>` HEAD via `git ls-remote --heads origin "epic/<N>-*"`; story under open epic → parent epic branch HEAD; open-PR-for-this-issue → PR's `headRefName` HEAD; story with no/closed parent epic → `origin/main`), with a fixed precedence rule when more than one row applies (open-PR-head wins). Fully mechanical given the inputs (issue type, epic-branch existence, open-PR existence).
- **List docs existing at a ref** — `git ls-tree -r --name-only <plan_ref> -- docs/ CLAUDE.md`. Deterministic given the ref.
- **Codebase precedent manifest generation** (narrow lookups) — `git show <plan_ref>:<path>` / `git grep <pattern> <plan_ref>`. Mechanical fetch; the *interpretation* of what's fetched stays judgment.
- **Tracker de-dup search** — `gh issue list --repo <owner/repo> --state all --label question --search "<query>"`, run whenever a companion is about to be recorded `(not filed)`, per `_shared/open-question-detection.md` §Matching. Input: OQ tracker id or topic keywords. Output: candidate issue list — **this is the exact mechanism S12's `prep_planner.py` deterministic tracker search absorbs** (see Bug (a) below).
- **Hedge-phrase grep sweep** (Step 7.5) — the regex list in SKILL.md:282-286 run against the draft plan body. Mechanical detection; resolution stays judgment.
- **Stage plan body to scratch file + persist** — `PERSIST_COMMENT(target=issue, id=<N>, repo=<owner/repo>, body_path=/tmp/gh-planner-<N>/plan.md, delete_marker_id=<…>)` via `github-ops`. Mechanical given an already-approved body.
- **Issue-body pointer upsert** — `PERSIST_BODY(issue=<N>, repo=<owner/repo>, mode=pointer, pointer_line=<…>)` via `github-ops`. Idempotent mechanical edit.
- **Apply the `planned` label** — `gh issue edit <N> --repo <owner/repo> --add-label planned`, with a fallback `gh label create planned --repo <owner/repo> --color FBCA04 --description "..."` on first-use failure. Mechanical, idempotent.
- **DoD-annotation reconciliation body diff computation** (SOFT and HARD paths) — walking captured annotations against the new plan's `closes-dod` mappings per the fixed case table in `references/revise-reconciliation.md` (unchanged-attribution / reassignment-not-shipped / reassignment-shipped / phase-removed / orphaned-bullet / evaluator-rejected-preserve). Mechanical given (old annotations, new plan's `closes-dod` map, PR's ticked Phase tracker) — the SOFT/HARD *classification* upstream of this is judgment, but this diff computation itself is a deterministic table lookup.
- **HARD-path predecessor mechanics** — `gh pr close <PR#> --repo <owner/repo> --comment "..."`, un-tick DoD bullets to the predecessor annotation form, insert the fixed `## Predecessor` template. Mechanical given the HARD decision is already made.
- **Handoff snapshot field assembly** — issue/Epic number+title, plan-comment URL, child-story state: all already in hand from prior `GATHER_*` calls and the current run's own persist results; assembling them into the fixed field slots is mechanical (the `Next:`/`Why:` content remains judgment).

## Invariants (with the WHY)

- **The marker is always the first line of the comment body.** Every consumer (resolver step 4.6, drafter revise mode, this skill's own revise-mode lookup) locates the plan via `startswith` — any character before the marker makes the plan invisible to every downstream reader, and a consumer that can't find it behaves as if no plan exists at all, even though one was posted (SKILL.md:208).
- **For a story, the `**Epic:**` backlink goes immediately after the marker, never above it.** Same reason as above — preserving the marker-first invariant while still surfacing the epic relationship (SKILL.md:208, 226-234).
- **Stage the plan body to disk before dispatching `PERSIST_COMMENT`, never re-serialize it into the sub-agent prompt.** `github-ops` reads the bytes directly through `gh-persist.sh`, so prompt compaction can't abbreviate the body and an in-agent Write/Bash race can't lose it — this is the same failure surface that filed empty bodies on the drafter's #626/#627 incident (SKILL.md:386).
- **`plan_ref` grounds every doc/code read, never the orchestrator's working tree.** The working tree usually sits on `main`, but the issue's integration target may be an epic branch or an open PR's head; reading the wrong copy grounds the plan on stale docs/code — the exact failure class the resolver's §4.5 audit was built to prevent (its Epic #154 incident: the audit grepped `main` and missed every epic-branch symbol) (SKILL.md:128).
- **When more than one `plan_ref` table row applies, the open-PR-head row wins.** That head is a strict superset of the epic branch (epic HEAD plus the story's shipped commits) and is what the resolver actually continues on (SKILL.md:140).
- **The footer/handoff record the *branch*, never elide it to a short form.** `<plan-ref>@<short-sha>` is also the resolver's PR base — eliding `epic/<N>-<slug>` to a shortened form would break that reuse (SKILL.md:210).
- **A revise-with-open-PR footer pinned to the PR head is safe** because a revise-with-open-PR is always a resolver *continue* where the §4.6 currency check is skipped — so a PR-head footer never reaches a firing dimension-7 check; if that PR is later abandoned, a fresh resolver run grounds fresh at `origin/main` (SKILL.md:210).
- **Lock decisions, not lines.** Under-specification is the dominant planner→resolver failure mode: a hedge survives to the posted plan, the resolver's dimension-4 audit catches it, the user routes back here, and the planner ends up resolving the very decision it could have resolved on the first pass — the round-trip is pure waste (SKILL.md:238, 476).
- **The resolver may fill gaps but never reverse a locked decision.** The asymmetry is deliberate: filling an unlocked gap from precedent is cheap and low-risk; silently overturning a plan decision defeats the entire point of locking it (SKILL.md:261).
- **A tracked open question is not a hedge and must never be resolved from precedent or the Decision gate.** It is a decision a human must make; resolving it would be silently overriding an already-flagged human-owned call (SKILL.md:271, 296).
- **Re-route (don't post a hollow plan) when the whole plan is blocked by an unanswered OQ.** A plan that builds nothing the issue actually asked for isn't a plan — even a trivial unblocked slice doesn't change that (SKILL.md:273).
- **Step 7.5's hedge sweep runs before the expensive reviewer, not instead of it.** Catching a hedge in-loop costs almost nothing; catching it via the reviewer costs a full sub-agent pass. The reviewer is the second line of defense, not the first (SKILL.md:277, 300).
- **No hedge phrasing may survive the pre-flight exit gate anywhere in the plan body**, except the five sanctioned survivors: precedent-cited decisions, dated deviations, dated user decisions, watchpoints, and attributed tracked-OQ entries (SKILL.md:298).
- **A dimension-4 BLOCKER at Step 8's post-cap gate removes "Post as-is" from the option set entirely.** It is by definition an open design decision; posting it would silently reintroduce the very round-trip this skill exists to prevent (SKILL.md:360).
- **Auto-post on a clean verify exit — no confirmation gate on the common path.** The verification loop already is the quality gate; a redundant confirmation on top adds latency without adding safety, and a user who wants to review first can say so explicitly (SKILL.md:365, 382).
- **Never fan out full per-story plans up front for an Epic.** Per-story plans grounded against one epic-branch snapshot go stale the instant a predecessor story lands, and the resolver re-plans each one anyway — the durable up-front artifact is the epic plan's pinned contracts; each story is planned just-in-time against current epic HEAD (SKILL.md:418, 482).
- **The epic delivery log is a separate comment from the verified plan, never folded into it.** The plan is verified and immutable; the delivery log changes on every story merge — conflating them would force either re-verifying the plan on every merge or losing immutability (`_shared/epic-delivery-log.md:12`, plan-schema.md:114, 139).
- **Just-in-time story planning must reconcile the delivery log against the epic plan's pinned contracts before grounding, and re-route to the epic in revise mode (not an inline fix) on a mismatch.** Grounding a story on a stale contract propagates the epic plan's error into every subsequent story (SKILL.md:435).
- **`## Phases` uses fixed structured keys, never free-form sequencing prose**, because the resolver parses `## Phases` deterministically to route each phase — it cannot grep loose prose for a `closes-dod` mapping or a `kind` enum. This is a named regression: issue #640's Phase 1 PR shipped partway through the DoD to `main` because a prior free-form `## Sequencing` section gave the resolver no way to recognize more phases were due (SKILL.md:485).
- **`closes-dod` names the phase whose deliverable *satisfies* the DoD bullet, never the phase whose code merely *enables* it.** A substrate phase claiming a measurement DoD bullet on grounds that "my code makes the measurement possible" causes the evaluator to mark that bullet satisfied before the measurement has actually run (SKILL.md:218, 486).
- **The plan is never stored in the issue body.** The body is the drafter's artifact and gets repainted in its own revise mode; a plan stored there would be clobbered. The marker comment is the durable home; the body carries only a one-line pointer (SKILL.md:480).
- **A revise-mode SOFT reassignment must never auto-clear an evaluator-rejection annotation.** The rejection is the evaluator's hard evidence that prior code failed the bullet; silently swapping it for a new phase attribution during reconciliation would remove that evidence and reintroduce the silent-rubber-stamping failure mode the per-phase verification exists to prevent. The user must explicitly confirm before it transitions (SKILL.md:488, revise-reconciliation.md:39).
- **HARD reconciliation is chosen over papering the divergence with SOFT un-ticks when classification reads HARD**, because the evaluator's own per-phase verification would catch the same divergence at PR-readiness time and un-tick anyway — making an in-place SOFT reconciliation mostly wasted resolver work (SKILL.md:487).
- **A bug-fix plan must close the coverage gap that let the defect ship, not just repair it**, otherwise the same blind spot that hid the original bug remains invisible to the next regression on that path (SKILL.md:474; Dimension 9).
- **Every architectural/UI decision must cite real precedent or an agreed deviation — a fabricated citation is a BLOCKER, not a style nit.** A citation is the plan's evidence base; if it's fabricated, every decision resting on it is unsupported (SKILL.md:167, 483; plan-reviewer-prompt.md:50).
- **The reviewer sub-agent must never see the conversation history, the user's framing, or the planner's research notes.** Only the plan + issue + docs + codebase — that isolation is what makes "would a fresh implementer understand this cold" a meaningful test; injecting context defeats the fresh-reader property (SKILL.md:306, 479; plan-reviewer-prompt.md:3, 9).

## Sub-agents dispatched

| Sub-agent | Reference prompt file | Consumes | Returns |
|---|---|---|---|
| `github-ops` (`subagent_type: "github-pipeline:github-ops"`, Sonnet + medium, no `model` override) | `agents/github-ops.md` (not under this skill's `references/`) | Named op (`GATHER_ISSUE`, `GATHER_EPIC`, `PERSIST_COMMENT`, `PERSIST_BODY`) + args | `## RESULT` envelope: scalars + path references (`*_path`), or `DECISION_NEEDED: <…>` with no write performed |
| Plan reviewer (`Explore`-type) | `references/plan-reviewer-prompt.md` | Plan body, `mode` (`draft`/`revise <N>`), `issue_number`, `repo_owner`/`repo_name`, `repo_root`, `plan_ref`, `dimensions` (subset of 1–10), `external_sources`, `epic_plan` (story-under-epic only), `epic_delivery_log` (story-under-epic only) | `## Plan review summary` + `## Findings` block: per-finding severity (BLOCKER/SUGGESTION/NIT), dimension, evidence, what's wrong, remediation — or the exact "Findings: 0 / None." shape when clean |
| Broad codebase-precedent search (`Explore`) | inline prompt, no dedicated reference file | Focused prompt naming symbols/patterns/doc sections + `plan_ref` | Manifest of `path:line-start–line-end` pointers (planner then `Read`s the cited ranges itself) |
| Inline knowledge-gap fact-check (`Explore` or `general-purpose`) | inline prompt, no dedicated reference file | The exact question, the dependency + pinned version, instruction to answer only from a fetched primary source | A verified claim + its URL + fetch date, or an indication it couldn't be answered |

## Known bugs / gaps

**Bug (a) — tracker-search-miss (open-question integrity).**

Requirement: *An open question that already has a tracker issue MUST be cited by its `#N`; it must
never be recorded as "(not filed)".*

Falsifiable test: given a source-doc OQ whose topic matches an existing **OPEN** `question`-labelled
issue, the posted plan's `## Open questions` cites that issue number by `#N`. Recording
`(not filed — tracked in the … register)` for a genuinely-filed question is a defect.

Real occurrence: the planner, run on rails-playground #29 (plan posted 2026-07-01), recorded the
"Tag case sensitivity" OQ as `(not filed)` although question **#51** — labels `question` +
`audience:developer`, state OPEN, filed ~19h earlier — already tracked it. Root cause: the mandated
de-dup tracker search from `_shared/open-question-detection.md` §Matching
(`gh issue list --repo <owner/repo> --state all --label question --search "<query>"`) was not
re-run at plan time; the stale `(not filed)` was copied forward verbatim from the epic's issue body
instead of being re-verified against the tracker.

Secondary defect, same run, also falsifiable: *a plan's `## Open questions` treatment label
(`planned-around` / `provisional-default` / `scoped-out`) must be internally consistent with the
`## Risks & watchpoints` entry describing the same OQ.* The #29 plan labelled the entry
`planned-around` while the mechanics it described (a provisional choice built now, with a named
retirement condition) matched `provisional-default` — the two vocabularies (SKILL.md:265-271,
plan-schema.md:74-81, 100-105) disagreed about the same decision within one plan.

This is the S1-frozen falsifiable requirement S12's `prep_planner.py` deterministic tracker search
must satisfy: the search in "Deterministic steps" above (tracker de-dup search) is exactly the
mechanism that must run — as a script, not a skipped model step — every time a `(not filed)` claim
is about to be recorded or carried forward.

**Bug (b) — composite-handoff OQ-line drop.**

Requirement: *The handoff's `**Open questions:**` line MUST render in every session shape, including
a combined epic + story session.*

Falsifiable test: given one planner session that posts both an epic plan and a just-in-time story
plan, where **both** plan bodies carry `## Open questions`, the emitted `## Handoff` includes the
`**Open questions:**` line. Dropping it is a defect.

Real occurrence: the planner, run on rails-playground #28/#29 (2026-07-01) — a hybrid epic+story
session (the "Epic-plus-story hybrid, one session" rendering, then being drafted for
`references/handoff-renderings.md:56-71`, triggered when "Just-in-time story planning" is invoked on
a story whose parent epic has no plan yet, so the epic plan is bootstrapped inline first). Both plan
bodies correctly carried `## Open questions`, but the composed handoff dropped the
`**Open questions:**` line entirely. Root cause, as observed 2026-07-01 against the then-current
`references/handoff-renderings.md`: the file had no worked example composing the epic/story hybrid
shape *with* an open-questions line, nor a `(not filed)` companion-question example within that
hybrid — the file's header (handoff-renderings.md:5) noted shapes "compose along independent axes"
but the hybrid rendering was the one example that didn't show the composition with an OQ line, so
the planner pattern-matched to the nearest single-axis shape it did have a worked example for and
silently dropped the field.

**Current state (re-verified at S1 freeze):** this gap is closed in the working tree. Commit
`9e4222e` (2026-07-03, "fix(planner): provisional-default OQ treatment + tracker re-verification")
added the missing worked example — `references/handoff-renderings.md:56-71` now *is* the
epic-plus-story hybrid rendering, and its line 64 reads
`**Open questions:** (not filed) (audience:developer) provisional-default — see the plan's ## Open
questions`, which is simultaneously the hybrid-shape composition **and** the `(not filed)`
companion-question example the 2026-07-01 run lacked. S1 freezes v1 as it exists in the working
tree now, so the worked-example gap is **not** an open defect as of this baseline.

**Residual requirement for S13:** a worked example closes the one gap it covers; it does not by
itself guarantee every future shape combination renders the line. The rewritten handoff-rendering
logic must not depend on worked-example coverage at all — see the falsifiable requirement below,
which the v2 rewrite must satisfy as **rendering logic**, not as an artifact of which examples
happen to exist in the reference file.

This is the S1-frozen falsifiable requirement S13 (planner rewrite handoff rendering) must satisfy:
the rewritten handoff-rendering logic must treat "does this plan/story carry `## Open questions`" as
an independent, always-checked condition — never one that can be dropped because the *structural*
shape (single-issue / epic / story / hybrid) matched a different worked example first. The v2
playbook rule this frozen requirement backs is: *emit `**Open questions:**` whenever any plan body
posted in this session carries an `## Open questions` section, and render `(not filed)` only when
the tracker search (Bug (a)'s mechanism) found no candidate or an existing candidate was explicitly
rejected as not-the-same-question* — never as a default absence.

**Bug (c) — bare-digit `in:body` search false-positives (newly discovered, not captured at S1
freeze).**

Requirement: *`plan_ref`'s open-PR-head row (Step 4.5) must only fire for a PR that genuinely
references the issue being planned; it must never ground a plan on a stranger PR's branch.*

Falsifiable test: given an issue `#N` with **no** open PR referencing it, but at least one *other*
open PR whose body happens to contain the bare digit `N` in unrelated prose (a `## Phase tracker`
entry, an unrelated issue number sharing digits), `plan_ref` selection must resolve via whichever
row actually applies (default branch / epic branch / parent-epic branch) — never
`open-pr-head` pointing at that stranger's branch.

Real occurrence (live, read-only, against the sandbox repo, 2026-07-11): running S12's
`prep_planner.py` against sandbox story `#2` and epic `#1` — neither of which has any open PR
referencing it — both resolved `plan_ref_row: open-pr-head` at branch `issue-43-fix-helpers-a`, a
PR for **issue #43** with no relationship to `#2`/`#1` whatsoever. Root cause, confirmed directly:
`gh pr list --search "2 in:body"` returns four open PRs, none of which reference issue `#2` — each
merely contains the literal text `"Phase 2"` in its `## Phase tracker` section (a section present
on nearly every multi-phase PR in the sandbox). A parallel control run, `gh pr list --search "#2
in:body"` (the hash-prefixed form `_search_parent_epic`'s query already uses), returned the
**identical** four false positives — proving GitHub's server-side full-text search does not anchor
on the `#` at all; the query *form* provides no protection, only a client-side filter does.

Scope: this is not planner-specific — the same `--search "<N> in:body"` construction is
`gh_gather.py`'s `_fetch_open_prs` (feeding both this skill's `plan_ref` row 1 and the resolver's
prior-PR row), `prep_resolver.py`'s `_search_closed_prs`, and the `_search_parent_epic` search both
this skill and the resolver run (its `#N in:body` form making no real difference per the control
run above). v1's `gh-gather.sh` and `github-ops.md` carry the identical construction and are
therefore exposed to the identical false-positive class — **this is a real v1-inherited defect not
captured at S1 freeze**, discovered only once S12's live smoke exercised a repo state where a
stranger PR's incidental digit collided with a real target.

**Current state:** v2 closes this in the same round S12 discovered it (`gh_gather.references_issue`
— a digit-boundary-guarded `#<N>` match, or membership in `closingIssuesReferences`, applied as a
client-side post-filter on the search's already-necessarily-loose candidate set). v1 does **not**
carry this fix — `gh-gather.sh`'s open-PR/closed-PR/parent-epic searches remain exposed. This is
therefore an **expected, explained parity divergence**: an S13/S15 (or any later) parity run
comparing v1 against v2 on a repo state with an incidental digit collision will legitimately see v2
route differently (correctly) from v1 (which inherits the false positive) — the divergence is the
fix working as intended, not a v2 regression to chase down.

**Bug (d) — composite epic+story session: v1's own JIT guidance can't reach its own routing
decision (source-verified AND live-observed at S13's scenario-3 parity run — stronger evidence than
Bug (c), which is source-only).**

Requirement: *when this skill is invoked on a story whose open parent epic has no plan yet — the
"composite" case — the guidance for what to do (bootstrap the epic plan inline, then continue to
the story) must be in context at the point the routing decision is made, not only after.*

Falsifiable test: given a story under an open parent epic with no epic plan yet, an **unaided**
v1 session (no operator prompting) must reach the "bootstrap the epic plan inline, then continue"
decision from its own in-context guidance at Step 3 ("Route by shape") — the point where it decides
this is a Just-in-time-story-planning invocation — without stalling to ask the user what to do.

Real occurrence, verified against the frozen v1 source and observed live: v1's "Just-in-time story
planning" section opens by asserting its own precondition — `skills/github-issue-planner/
SKILL.md:429`: *"the epic plan is already posted with its `## Story contracts`"* — a precondition
the composite case, by definition, violates (the whole point of the composite case is that no epic
plan exists yet). The section's own worked guidance for exactly this violated-precondition case —
*"Bootstrapping the epic plan first ... is a reasonable judgment call, not a documented default
path"* — lives in `references/handoff-renderings.md:56` (the "Epic-plus-story hybrid, one session"
rendering's lead paragraph), a file that `SKILL.md:450` force-reads only *"before composing the
handoff"* — i.e. at Step 12, the very last step of the run, long after Step 3's routing decision has
already had to be made without it. So the one place in the v1 source that tells the model what to
do when Step 3's precondition fails is structurally unreachable at Step 3 itself. Live-observed at
S13's scenario-3 parity run (`docs/specs/parity/planner.md`, scenario 3, D5): an unaided v1 session
invoked on a composite story stalled at routing, asking the operator what to do — **twice** (two
operator resumes were required to complete the v1 leg) — while the v2 leg (`skills/planner/
playbooks/story-jit.md`) completed the identical scenario with **zero** gates, because its
bootstrap-when-absent guidance is authored directly inside the playbook the router reads *at route
time*, not deferred to a handoff-composition reference read at the end of the run.

**v2 consequence:** the composite epic+story session is a first-class, in-route-time-context case
in v2 — `story-jit.md`'s "Bootstrap the epic plan when absent" bullet is read by the router before
any routing/grounding decision is made, not force-read only at handoff time. The v1 "force a Read
of a reference file at a specific step so its content reaches context regardless of where the
initial skill load truncated" workaround class (`CLAUDE.md`'s own documented device, used
repeatedly across v1 `SKILL.md`s) is retired for this case in v2: the guidance a routing decision
needs lives where the routing decision is made, so no forced-read choreography is needed to get it
there in time.

**Parity-protocol consequence:** gate-count comparisons on a composite-session scenario are **not
comparable** between v1 and v2 under this defect — a live v1 gate count on such a scenario measures
this structural stall, not a genuine decision requiring a human, so a parity run's "same genuine
decisions gated" check must treat v1's composite-case gates as explained by this defect rather than
as evidence of a decision v2 silently skipped.
