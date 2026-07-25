# question-sweep — v1 functional spec (baseline)

> Source: `skills/open-questions/SKILL.md` (147 lines) + references:
> `references/question-status-reader-prompt.md` (79 lines).
> Captures v1 behavior as the parity baseline for [implementation.md](../implementation.md) S<cutover>.
> v1 skill name: `github-pipeline:open-questions`; v2 name: `question-sweep`.

## Overview

A project-wide hygiene sweep that reconciles the **open questions** (OQs) scattered across the
consuming repo's docs against the GitHub **question registry** — the set of `question`-labelled
issues, which is the registry of record (`skills/open-questions/SKILL.md:13`). Session shape:
single standalone session, explicit-invocation only
(`disable-model-invocation: true`, `skills/open-questions/SKILL.md:5`), run as
`/github-pipeline:open-questions [docs-path-or-glob]` (`SKILL.md:6`). Inputs: an optional
docs path/glob argument (defaults to `docs/**` plus config-declared register locations,
`SKILL.md:33`). Outputs: filed companion `question` issues, doc edits (back-links / stale-marker
fixes), and a plain summary — **never** a pipeline `## Handoff` (`SKILL.md:143`). It owns the
open-question registry: it is the only skill that detects OQs project-wide and maintains the
doc↔issue back-links in both directions (`SKILL.md:9-16`).

## Artifacts written

| Artifact | Marker / schema | Lives in | Trigger |
|---|---|---|---|
| Companion `question` issue | Full `question`-issue body template (`## Question` / `## Audience` / `## Constraints` / `## Context` / `## References` / `## Why this matters` / `## Tracked in`) per `skills/_shared/question-issue.md:12-33`; `## Tracked in` names the source doc | New GitHub issue, labelled `question` + `audience:*` | Step 6, for every OQ classified **untracked** at Step 4, on operator confirmation at Step 5 (`SKILL.md:85`, `SKILL.md:126-130`) |
| Doc edit — stale-doc fold-back | The §"Doc fold-back" moves from `skills/_shared/open-question-links.md:136-138`: rewrite prose to the decided state, remove the `PROVISIONAL`/open-question marker, flip a register's status + add `tracked in #<N>` | Consuming-repo doc (in place, via `Edit`) | Step 6, for every OQ classified **stale-doc** at Step 4, on operator confirmation (`SKILL.md:87-93`, `SKILL.md:131-133`) |
| Doc edit — missing-back-link (doc side) | Inline `tracked in #N` marker added at the OQ's doc location | Consuming-repo doc | Step 6, for **missing-back-link** class, doc-side half (`SKILL.md:94-95`, `SKILL.md:131-133`) |
| Question issue body edit — missing-back-link (issue side) | `## Tracked in` patched with the doc location and/or build-issue `#` | Question issue body (via `PERSIST_BODY`) | Step 6, for **missing-back-link** class, issue-side half (`SKILL.md:134-136`) |

No section is edited in place with a delete-old-then-post-new pattern here — Step 6's issue-side
edit is a body patch (`PERSIST_BODY`), not a marker-comment replace; the skill posts no marker
comment of its own (it *reads* `<!-- question-decision:v1 -->`, written only by
`question-resolver` — see Artifacts read).

## Artifacts read

| Artifact | Marker / location | What's extracted |
|---|---|---|
| `<!-- question-decision:v1 -->` decision comment | Question-issue comment | Tier-1 status signal: presence (`marker_comment_present`) means the question is **resolved** without a reader dispatch (`SKILL.md:71-73`, `SKILL.md:90-93`) |
| `question`-type issue skeleton | `gh issue list --repo <owner/repo> --state all --label question --limit 500 --json number,title,state,labels,url` | `#`, title, `state` (Tier-1 status half), `audience:*` labels — the registry snapshot (`SKILL.md:66-70`) |
| `## Tracked in` section | Question-issue body | Doc↔issue back-link target, used for matching (`SKILL.md:81`, `skills/_shared/question-issue.md:31-32`) |
| `<!-- drafter-open-question-markers -->` config block | Consuming repo `CLAUDE.md`, read via `${CLAUDE_PLUGIN_ROOT}/scripts/config-block.sh read CLAUDE.md drafter-open-question-markers` | Register location(s), inline-marker pattern, open-status rule — detection hint only, not status authority (`SKILL.md:36-39`, `skills/_shared/open-question-detection.md:18-24`) |
| Doc-inline OQ markers | Any project doc, per the detection heuristics (`PROVISIONAL`, `TBD`, "open question", "to be decided", or an `open[- ]questions?` heading) when no config block | `{source doc + location, topic/text, native id if any, inline "tracked in #N" if any, gated scope}` per OQ (`SKILL.md:50-56`, `skills/_shared/open-question-detection.md:26-36`) |
| Repo label list | `gh label list --limit 100` | Existence of `question` and `audience:*` labels, so Step 6 knows which to create (`SKILL.md:40-41`) |

## Operator gates

| Gate | Options | Effect |
|---|---|---|
| Step 5 — GitHub writes (file companions, back-link body edits) | Confirm via `AskUserQuestion` per `skills/_shared/asking-the-user.md` (`SKILL.md:118-119`) | Approving lets Step 6 execute the filing/link writes; declining performs none |
| Step 5 — Doc edits | Propose-then-apply-on-confirm: exact diff/snippet shown, applied only on "yes" (`SKILL.md:120`) | Approving applies the shown diff via `Edit`; declining leaves the doc untouched |
| Step 5 — Orphaned-issue disposition | Surfaced, never auto-closed — closing is the human's call in the thread (`SKILL.md:97`, `SKILL.md:121-122`) | No automatic action; the sweep only reports the orphan |
| Implicit: never resolve a question | Not a selectable option — a structural rule, not a gate with choices | The sweep never auto-closes or auto-resolves a question issue regardless of what Step 4 finds (`SKILL.md:121-122`) |

## Judgment steps (model reasoning — stays in the prompt)

- **OQ detection/confirmation** (Step 2) — grep-prefilters candidate files by the detection cues,
  then fans out `Explore` sub-agents (one per file, or batched for many small files) to confirm
  real OQs and extract their fields; reports how many files were prefiltered vs. read
  (`SKILL.md:45-58`). Isolated sub-agent: unnamed generic `Explore`, not a named reference prompt.
- **Matching a doc-OQ to a tracker issue** (Step 4) — native id first, else topic keywords plus a
  `Read` of the candidate body to confirm sameness, per `skills/_shared/open-question-detection.md:39-52`
  (`SKILL.md:81`). Main-loop reasoning, not delegated.
- **Reconciliation classification** (Step 4) — classifies every OQ/question pairing into one of
  five closed classes: `untracked`, `stale-doc`, `missing-back-link`, `orphaned-issue`, `in-sync`
  (`SKILL.md:83-98`). Main-loop reasoning.
- **Tier-2 status read** (Step 4a) — dispatches the **question-status reader** `Explore` sub-agent
  (`skills/open-questions/references/question-status-reader-prompt.md`) only when a doc says open
  and the matched question is still `open` with no decision marker; returns `resolved-in-thread` /
  `still-open` or the `AMBIGUOUS` exception (`SKILL.md:100-109`).
- **Report composition and severity/class grouping** (Step 5) — one consolidated reconciliation
  report grouped by class, each entry naming the OQ, doc location, matched issue, proposed action,
  and evidence (`SKILL.md:113-115`). Main-loop reasoning.
- **Summary composition, including the plan-revisit breadcrumb** (Step 7) — when a resolved OQ
  means a filed build issue now needs replanning, breadcrumbs it in prose rather than emitting a
  handoff (`SKILL.md:145-147`). Main-loop reasoning.

## Deterministic steps (candidate script work — moves to a prep/executor script)

- **Repo resolution** — `gh repo view --json nameWithOwner -q '.nameWithOwner'` (`SKILL.md:35`).
  Input: none. Output: `owner/repo` string.
- **Detection-config read** — `config-block.sh read CLAUDE.md drafter-open-question-markers`
  (`SKILL.md:37-38`). Input: `CLAUDE.md` path. Output: block content or absence.
- **Label inventory** — `gh label list --limit 100` (`SKILL.md:40-41`). Input: none. Output: label
  list, diffed against `question`/`audience:*` needed downstream.
- **grep-prefilter of scope** — apply the detection cues (config-block pattern or heuristic cues)
  across the docs in scope to shortlist candidate files (`SKILL.md:50-51`). Input: scope glob +
  cue pattern. Output: candidate file list.
- **Tracker registry fetch** — `gh issue list --repo <owner/repo> --state all --label question
  --limit 500 --json number,title,state,labels,url` (`SKILL.md:66-68`). Input: repo. Output: JSON
  array of question-issue skeletons.
- **Per-question `GATHER_ISSUE` fetch** — for matching/status-reading, via `github-ops`
  `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- question-decision:v1 -->",
  scratch_dir=/tmp/gh-open-questions-<slug>/)` (`SKILL.md:76-77`). Input: issue #, repo. Output:
  body/thread (inline or spilled path), `state`, `marker_comment_present`/`_count`/`_id`,
  `blocked_by`/`blocking`.
- **Tier-1 status derivation** — `state == closed` OR `marker_comment_present` ⇒ resolved,
  computed purely from the `GATHER_ISSUE` scalars (`skills/_shared/open-question-links.md:104-109`).
  Input: `state`, `marker_comment_present`. Output: resolved/not-yet-determined.
- **Issue filing** — `PERSIST_CREATE(repo=<owner/repo>, title=<title>, body_path=<staged_path>,
  labels=[question, audience:*, …])` (`SKILL.md:130`). Input: staged body file, title, labels.
  Output: new issue URL/number.
- **Missing-label creation** — `gh label create "audience:<x>" --description "…" --color BFD4F2
  2>/dev/null || true` per `skills/_shared/question-issue.md:70-72`, run inline in the main loop,
  not through `github-ops` (`skills/_shared/question-issue.md:68-69`). Input: label name. Output:
  label created or already-exists no-op.
- **Body patch** — `PERSIST_BODY(repo=<owner/repo>, issue=<N>, body_path=<staged_path>)`
  (`SKILL.md:136`). Input: staged full body. Output: confirmation + `body_sha256`.

## Invariants (with the WHY)

- **Reports before it applies anything.** Docs and issues are expensive to get wrong, so the full
  reconciliation is shown before any write (`SKILL.md:18-19`). WHY: an unreviewed GitHub write or
  silent doc rewrite is unrecoverable-by-inspection — the operator must see the diff/plan first.
- **The tracker is the registry of record, never a doc field.** OQs live inline in any doc; the
  set of `question`-type issues is the source of truth (`SKILL.md:11-14`,
  `skills/_shared/open-question-links.md:7-8`). WHY: a doc marker can lag a decision made in a
  question's thread — trusting the doc would silently reintroduce stale state.
- **Never auto-close or auto-resolve a question.** Explicit rule at Step 5 (`SKILL.md:121-122`).
  WHY: closing/resolving a question is the human's call in the thread (the closing protocol,
  `skills/_shared/open-question-links.md:147-149`) — the sweep only detects and reconciles.
- **De-dup search before filing.** Search the tracker (`gh issue list … --label question --search
  <query>`) and `Read` a candidate's body to confirm sameness before proposing a file
  (`skills/_shared/open-question-detection.md:41-52`). WHY: proposing a file before checking is how
  a duplicate question gets created (stated verbatim in the shared contract).
- **`marker_prefix` fetch realizes the full Tier-1 read.** The sweep fetches with
  `marker_prefix="<!-- question-decision:v1 -->"` specifically so `marker_comment_present`
  populates (`SKILL.md:72-73`, `skills/_shared/open-question-links.md:118-120`). WHY: without
  passing the marker prefix, a recorded decision on a still-`open` issue would be invisible to
  Tier 1 and force an unnecessary Tier-2 dispatch.
- **Tier 2 only when Tier 1 doesn't resolve it.** The status reader is dispatched only for
  still-`open` questions with no decision marker (`SKILL.md:100-101`, `references/question-status-reader-prompt.md:11-12`).
  WHY: a `closed` question or a decision-marked one is already resolved — dispatching a reader
  sub-agent for it is wasted judgment work.
- **Every GitHub write goes through `github-ops`; every body is staged to a scratch file first**
  (`SKILL.md:138-139`). WHY: this is the path-based write contract that closes the empty-body race
  (the #626/#627 incident referenced by the broader plugin convention) — nothing re-serializes a
  body across the prompt boundary.
- **Scratch dir under `/tmp/gh-open-questions-<short-slug>/`, never a plugin-bundle path**
  (`SKILL.md:28-29`). WHY: the plugin install directory is read-only at runtime.
- **A resolved OQ that affects a filed build issue is breadcrumbed, not auto-chained**
  (`SKILL.md:145-147`). WHY: this is a standalone hygiene tool — it must not cross the session
  boundary or start another skill's session itself; the pointer lets the operator choose to act.

## Sub-agents dispatched

| Sub-agent | Reference prompt file | Consumes | Returns |
|---|---|---|---|
| OQ detection/confirmation `Explore` (unnamed, generic) | none (ad hoc per-file dispatch, `SKILL.md:52-56`) | Doc file content excerpts (candidate files from the grep-prefilter) | Per real OQ: `{source doc + location, topic/text, native id if any, inline "tracked in #N" if any, gated scope}` |
| Question-status reader | `skills/open-questions/references/question-status-reader-prompt.md` | Issue #, repo, question body (path or inline), thread (path or inline) — **never** the caller's task, state, or prior conversation (`references/question-status-reader-prompt.md:6-7`) | `## Reading` block: `status: resolved-in-thread \| still-open`, `evidence:`, `answer_summary:` (when resolved); or `## Exception` `code: AMBIGUOUS` per `skills/_shared/subagent-decision-signal.md` (`references/question-status-reader-prompt.md:60-79`) |

The question-status reader first checks for a `<!-- question-decision:v1 -->` comment in the
thread itself; if present, it returns `resolved-in-thread` citing that comment as the recorded
answer without independently judging the thread (`references/question-status-reader-prompt.md:36-39`).
It cannot call `AskUserQuestion` and never re-fetches via `gh` (`references/question-status-reader-prompt.md:19-20`, `:71`).

## Known bugs / gaps

None is documented in v1 *source* (the two mandatory falsifiable planner bugs named in the S1 step
definition belong to `docs/specs/planner.md`, not this file). One v1 defect was **observed live** at the
S18 scenario-1 run and is recorded here:

- **v1 registry-coverage + empty-thread defect (observed live 2026-07-22/23, S18 scenario-1 —
  [`parity/question-pair.md`](parity/question-pair.md) Div-1).** v1 `open-questions` fetched only a
  **subset** of the `question` registry (3 of 7 live questions) and then asserted an **empty thread for
  every** question ("every question in scope is unambiguously still open — empty threads, no decision
  markers"), so it missed two **resolved-in-thread** answers: #29 and #30 each carry an owner comment that
  answers the question but was never folded to docs or used to close the issue. **Falsifiable:** on a
  registry where a still-`open` question has a direction-setting thread answer and no
  `<!-- question-decision:v1 -->` comment, v1 reports it `still-open` (and never dispatches a Tier-2
  reader), rather than `resolved-in-thread`. **v2 does not reproduce it:** the deterministic Tier-1 join
  covers **every** registry entry (`prep_question_sweep.py`), and the Tier-2 question-status reader is
  dispatched for every `tier2_needed` (`still-open`, no-marker) entry — catching exactly the
  answered-in-thread-but-still-open staleness case, which is the tiered read's stated purpose
  (`skills/_shared/open-question-links.md` §"Status is the tracker's"). This is the highest-value finding
  the whole skill exists to produce.
