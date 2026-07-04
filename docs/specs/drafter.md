# drafter — v1 functional spec (baseline)

> Source: `skills/github-issue-drafter/SKILL.md` (576 lines) + references: `handoff-renderings.md`,
> `issue-reviewer-prompt.md`, `issue-templates.md`.
> Captures v1 behavior as the parity baseline for [implementation.md](../implementation.md) S14–S15.
> v1 skill name: `github-issue-drafter`; v2 name: `drafter`.

## Overview

Turns informal developer feedback into a filed, template-conformant GitHub issue, or revises an
existing one. Single Claude Code session, `opus`/`high` (`skills/github-issue-drafter/SKILL.md:3-4`).
Inputs: freeform user feedback (new-issue mode) or an issue number/URL with revision intent (revise
mode); repo conventions (templates, labels); the consuming repo's `docs/prd.md` if present. Outputs:
one filed/edited issue (bug, incomplete feature, new feature, story) **or** a filed Epic plus its
child stories in one batch, **or** a filed/edited `question`-type issue — always ending in a single
`## Handoff` block. It is the first stage of the pipeline (`SKILL.md:12`): it files the issue;
`github-issue-planner` researches and attaches the plan later. It delegates judgment-free GitHub/git
I/O to the `github-ops` sub-agent (`subagent_type: "github-pipeline:github-ops"`, Sonnet + medium,
no `model` override — `SKILL.md:18-40`) and delegates isolated coherence review to an `Explore`
sub-agent (Step 5).

## Artifacts written

| Artifact | Where it lives | Trigger | Source |
|---|---|---|---|
| Filed issue (bug / incomplete / feature template) | issue body, via `PERSIST_CREATE` | Step 7, after Step 6 user confirmation | `SKILL.md:501-507` |
| Filed Epic + child Story issues (one-shot batch) | Epic issue body + each Story issue body | Step E3, after a clean E1+E2 pass (no per-item confirmation gate) | `SKILL.md:285,529-542` |
| Filed `question`-type issue | issue body | Step 7 "Filing a build issue that has open questions" step 1, or standalone question filing | `SKILL.md:509-516` |
| `<!-- open-question-links:v1 -->` `## Open questions` section | build-issue body (bug/incomplete/feature/epic/story) | Step 4 "Recording open questions", from Step 3.5 dispositions | `SKILL.md:352-355`; schema in `_shared/open-question-links.md:40-53` |
| `## Out of scope` line naming the OQ | build-issue body | Step 4, for every `scoped-out` disposition | `SKILL.md:354`; `references/issue-templates.md:119-127` |
| `question`-issue body (schema: `## Question`/`## Audience`/`## Constraints`/`## Context`/`## References`/`## Why this matters`/`## Tracked in`) | question-issue body | Step 3.5 companion filing or a direct question classification | schema owned by `_shared/question-issue.md:10-33`; drafter is a filer, not the schema owner |
| `audience:*` label(s) | question issue labels | Step 4 "Audience labels", created in the main loop right before filing | `SKILL.md:369-371`; rule in `_shared/question-issue.md:46-77` |
| `**Epic:** #<epic-#> — <Epic title>` backlink (first line of every Story body) | Story issue body | staged into the story file before `PERSIST_CREATE`, at Step E2/E3 | `SKILL.md:291-299,533` |
| Epic `## Stories` bullets patched from placeholders to `- [ ] #NN — <title>` links | Epic issue body | Step 3 of "Filing an Epic with child stories", after all stories are created | `SKILL.md:539-540` |
| `## PRD impact` note (`This <extends\|contradicts\|clarifies> the PRD (section: <name or quote>)...`) | build-issue body | Step 4 drafting, only when PRD tension detected | `SKILL.md:198-205` |
| `## Related issues` section (`Expected behavior is described in #78.` / `May be resolved by #21...` / `Blocked by #50.` / `Duplicate of #99.` / `Related to #12.` / `Closes #5.`) | build-issue body | Step 4 drafting, when the user referenced other issues | `SKILL.md:234-253` |
| Native `blocked by` dependency | issue relationship (GitHub native), via `blocked_by=` on `PERSIST_CREATE` or `PERSIST_LINK(add_blocked_by=…)` | when rendering `Blocked by #N` (user-stated) or an `in-scope (blocked)` OQ with a filed companion | `SKILL.md:255,514-516` |
| Companion question's `## Tracked in` patched with the build issue `#` | question-issue body | step 3 of "Filing a build issue that has open questions", via staged `PERSIST_BODY` | `SKILL.md:517` |
| Native blocked-by removal via `PERSIST_LINK(remove_blocked_by=#N)` | issue relationship (GitHub native) | revise Step R4, when a companion OQ resolves | `SKILL.md:92` |
| Revised issue body (title/body/labels delta) | issue body, via `PERSIST_BODY(mode=replace)` | Step R6, after revise-mode confirmation | `SKILL.md:115-129` |
| Paste-ready doc snippet for a filed question (e.g. `- PRD-OQ-06b: Which billing model for v1? — tracked in #210`) | printed to the user, not written to any doc | immediately after filing a question, before the terminal handoff | `SKILL.md:519-527` |
| `## Handoff` block (closed-set schema) | session output (chat) | Step 8, end of every clean run | schema owned by `_shared/handoff-format.md`; renderings in `references/handoff-renderings.md` |

## Artifacts read

| Artifact | Where | What's extracted | Source |
|---|---|---|---|
| `<!-- implementation-plan:v1 -->` plan comment | issue comment | Revise mode only: fetched via `GATHER_ISSUE(marker_prefix="<!-- implementation-plan:v1 -->", …)`; drafter reads only enough to ground the revise against the same approach and to preserve the body's `> 📋 **Implementation plan:**` pointer line verbatim — it never edits or deletes the comment itself | `SKILL.md:70-76,119` |
| Issue body + full comment thread | issue body/comments | Revise mode: fetched via `GATHER_ISSUE`; used to find the latest substantive direction (Step R3) that may supersede the original body | `SKILL.md:66-80` |
| Closed-by-PR / project references, open-PR list | issue metadata | Revise mode: `GATHER_ISSUE(extra_json="closedByPullRequestsReferences,projectItems", …)`; surfaced before editing so the user can coordinate | `SKILL.md:70,74` |
| `<!-- drafter-open-question-markers -->` config block | consuming repo `CLAUDE.md` | Step 2 "Detecting open questions": register location(s), inline-marker pattern, open-status rule — degrades to heuristic cues when absent | `SKILL.md:402`; contract in `_shared/open-question-detection.md:16-28` |
| `docs/prd.md` (or `docs/PRD.md`/`PRD.md`/`prd.md`) | project doc | Step 2 check + "Using the PRD": grounds language/terminology, detects contradicts/extends/gap tension | `SKILL.md:167-209` |
| Existing labels (`gh label list`) | repo config | Step 2: maps feedback to existing labels rather than inventing new ones | `SKILL.md:165,173` |
| Issue templates (`.github/ISSUE_TEMPLATE/`) | repo config | Step 2: followed verbatim when present, in preference to the built-in fallback templates | `SKILL.md:162,171` |
| Referenced sibling/other issues (`gh issue view <N> --json title,state,body,labels`) | issue body | "Detecting related issues": read before drafting to classify the relationship correctly | `SKILL.md:224-230` |
| Question-registry search results (`gh issue list --label question --search "<query>"`) | issue list | Step 3.5 "Match first": de-dup search before proposing to file a companion question | `_shared/open-question-detection.md:44-52`, invoked from `SKILL.md:319-327` |
| Companion question `state` (+ `<!-- question-decision:v1 -->` marker via `marker_prefix`) | question-issue state/comment | Step R4 "Reconcile open questions": tiered status read to detect a now-resolved companion | `SKILL.md:92`; tiered read in `_shared/open-question-links.md:97-123` |
| Epic body + each `## Stories` entry's live state (`{number, title, checked, state}`) | Epic issue body + child states | "Special case — revising an Epic": via `GATHER_EPIC`, to reconcile checkboxes and re-run ordering/sizing dimensions | `SKILL.md:133` |

## Operator gates

| Gate | Asked via | Options | Consequence | Source |
|---|---|---|---|---|
| Feature vs. Epic | `AskUserQuestion` (header "Issue size") | **One feature** / **Epic + child stories** | Confirms scope before drafting rather than silently promoting/demoting | `SKILL.md:149` |
| Ambiguous classification (bug/feature/epic) | freeform ask | — | Never guesses when genuinely ambiguous | `SKILL.md:151` |
| Ambiguous issue reference ("the dashboard ticket") | freeform ask | — | Applies both to related-issue detection and Step R1 issue identification | `SKILL.md:64,222` |
| Revise: pre-work state-summary confirmation ("Correct?") | freeform statement + implicit confirm (not `AskUserQuestion`) | user corrects or confirms the one-line state summary | Anchors the rest of the revise response to the right thread-direction reading before any work begins — distinct from, and prior to, the Step R6 diff-confirmation gate | `SKILL.md:82-84` |
| PRD conflict | `AskUserQuestion` (header "PRD conflict") | **File to update PRD** / **File the feature** / **Flag for discussion** | User decides whether PRD or feedback is the thing that's stale | `SKILL.md:207` |
| Filing confirmation ("File issue?") | `AskUserQuestion` (header "File issue?") | **File it** / **Keep iterating** | Nothing is filed without an explicit "File it" — silence, a tweak request, or "Other" all count as keep-iterating. **Skipped only** for the Epic one-shot batch (Step E3), where a clean E1+E2 pass is the go-ahead | `SKILL.md:497,52,285-289` |
| Revise: apply-the-diff confirmation ("Wait for explicit confirmation") | freeform prose gate (not an `AskUserQuestion` card; no fixed header/options) | proceed to `PERSIST_BODY` only after explicit confirmation of the R5 diff-style draft | Separate gate from the new-issue "File issue?" card — revise mode confirms a diff, not a fresh draft, and uses plain prose rather than the card mechanism | `SKILL.md:117` |
| OQ disposition (per gating OQ) | `AskUserQuestion` (header e.g. `"OQ <id>"`) | **Scope it out** (default) / **Keep in-scope (blocked)** / **Build on a provisional default** | Determines `## Open questions` entry + whether a native `blocked by` is set | `SKILL.md:317-324` |
| Companion question disposition (when a tracker match exists) | `AskUserQuestion` | **Reuse #N** (default) / **File a new one** | Only asked to resolve genuine ambiguity about whether #N is the same OQ | `SKILL.md:326` |
| Revise: closed issue | `AskUserQuestion` (header "Closed issue") | **Revise as-is** / **Reopen first** / **File follow-up** | Decides whether to edit in place, reopen, or leave closed and file new | `SKILL.md:568` |
| Revise: Epic closed (revising a Story) | `AskUserQuestion` (header "Epic closed") | **Close the story** / **Detach backlink** / **Relink to epic** | Prevents a Story silently dangling under a closed Epic | `SKILL.md:137` |
| Related-issue "may be resolved by #21" nuance | freeform ask | file now with note vs. wait and check #21 | Respects that the user may be unsure whether to file at all | `SKILL.md:257` |
| Review loop cap/circular exit | `AskUserQuestion` (header "Review loop") | **It's real, keep fixing** / **Override and file** | Human breaks the tie when the reviewer sub-agent's finding can't be resolved automatically | `SKILL.md:572` |
| `in-scope (blocked)` OQ declined to file a companion | implicit (no filed companion) | falls back to **scoped-out** or a **prose-only** blocker | Never emits a `blocked_by=` with no `#N` | `SKILL.md:329` |
| Multiple unrelated things in one feedback message | confirm-and-split | — | Files as separate issues, confirmed with the user first | `SKILL.md:558` |

## Judgment steps (model reasoning — stays in the prompt)

- **Classification** (Step 1): bug / incomplete feature / new feature / Epic / question, via cue-matching (`SKILL.md:139-151`). Main loop.
- **PRD grounding + tension detection** ("Using the PRD"): contradicts/extends/gap pattern detection, terminology mirroring (`SKILL.md:187-209`). Main loop.
- **Detecting open questions in the source** (Step 2 subsection): recognizing an OQ marker while reading grounding docs (`SKILL.md:179-186`). Main loop, per `_shared/open-question-detection.md`.
- **Resolving open questions** (Step 3.5): match-first search, disposition assignment, companion reuse/file/defer judgment (`SKILL.md:317-331`). Main loop.
- **Latest-direction reading** (Step R3, revise mode): identifying which comment-thread reply supersedes the original body (`SKILL.md:78-86`). Main loop.
- **Adversarial issue/coherence review** (Step 5): 7-dimension review against docs, codebase, internal consistency, thread, ordering, completeness, sizing. **Isolated `Explore` sub-agent**, prompt at `references/issue-reviewer-prompt.md` (`SKILL.md:373-478`).
- **Epic split settling** (Step E1): coalescing pass (3 merge signals + 1 guardrail) applied by the main loop first, then adversarially re-checked by the same review sub-agent in `split` mode (`SKILL.md:265-289`).
- **Epic/story sizing and ordering** (dimensions 5 and 7): dependency-graph story ordering, coalesce-vs-split calls. Isolated sub-agent, `references/issue-reviewer-prompt.md` §5/§7.
- **Epic re-audit on revise** ("Special case — revising an Epic"): checkbox reconciliation plus re-running ordering/sizing dimensions against the current story set (`SKILL.md:133`). Main loop for reconciliation, sub-agent for the dimension re-run.
- **Story-body drafting, title conventions, label selection** (Step 4): main loop.
- **Deciding what context to ask for** (Step 3): per-type minimum-viable-issue judgment, kept surgical (`SKILL.md:303-315`). Main loop.

## Deterministic steps (candidate script work — moves to a prep/executor script)

| Step | Inputs → Output | Source |
|---|---|---|
| Repo context probe | repo cwd → `{nameWithOwner, defaultBranchRef}`, `.github/ISSUE_TEMPLATE/` listing, `gh label list` output, PRD-file presence (`docs/prd.md`/`docs/PRD.md`/`PRD.md`/`prd.md`) | `SKILL.md:157-169` |
| OQ marker config read | `CLAUDE.md` path → `<!-- drafter-open-question-markers -->` block contents or empty | `SKILL.md:402`; `_shared/open-question-detection.md:19-24` |
| Revise-mode gather | issue `N`, repo → issue body, full thread, plan-marker comment (if any) + its URL, closed-by-PR/project refs, open-PR list — via `GATHER_ISSUE` | `SKILL.md:70-76` |
| Epic-revise gather | epic `#`, repo → epic body + each `## Stories` entry `{number, title, checked, state}` — via `GATHER_EPIC` | `SKILL.md:133` |
| Question-registry candidate search (de-dup, search-before-file) | OQ tracker id or topic keywords → candidate issue list: `gh issue list --repo <owner/repo> --state all --label question --search "<query>"` | `_shared/open-question-detection.md:44-52` |
| Referenced-issue lookup | issue number(s) named in feedback → `gh issue view <N> --json title,state,body,labels` | `SKILL.md:227` |
| Staging bodies to disk before dispatch | approved/revised body text → file write at `/tmp/gh-drafter-<slug-or-N>/<name>.md` (draft-final.md, revised.md, epic.md, story-<i>.md, epic-patched.md) | `SKILL.md:129,499,533,536-540` |
| Missing-label creation for audience labels | audience name(s) → `gh label create "audience:<x>" --description "..." --color BFD4F2` | `SKILL.md:371`; `_shared/question-issue.md:70-72` |
| `PERSIST_CREATE` / `PERSIST_BODY` / `PERSIST_LINK` dispatch (via `github-ops`) | staged body path + title/labels/blocked_by deltas → issue URL, `#NN`, `body_bytes`, `body_sha256` | `SKILL.md:503-540` |
| `body_sha256` cross-check | staged file → `shasum -a 256 <path>` compared to `github-ops`'s returned hash | `SKILL.md:129,507` |

## Invariants (with the WHY)

- **Follow the repo's issue template verbatim when one exists.** "Templates encode the team's
  expectations — don't override them" (`SKILL.md:171`).
- **Map feedback to the repo's existing labels; don't invent new ones.** "Don't invent `bug` if
  the repo uses `kind/bug`. Don't make up priority labels if the repo uses `P0`/`P1`/`P2` instead
  of `priority:high`" (`SKILL.md:173`).
- **Never file without step-6 confirmation (except the Epic one-shot batch).** "Filed issues are annoying to clean up, and a 10-second confirmation prevents that." (`SKILL.md:52`) The Epic exception exists because the adversarial split loop (E1) plus the per-story body review (E2) *are* the safety net standing in for human confirmation — a clean pass through both is the go-ahead (`SKILL.md:285`).
- **Stage bodies to disk before every `PERSIST_*` dispatch; never re-inline body content into a sub-agent prompt.** This is the fix for the #626/#627 incident: two stories in an Epic batch were filed with empty bodies because the old inline-body contract let prompt compaction abbreviate the body or an in-agent Write/Bash race lose it. Writing to `/tmp/gh-drafter-.../*.md` and passing only the path means "the body never travels through the dispatch prompt, so prompt compaction can't abbreviate it and an in-agent Write/Bash race can't lose it" (`SKILL.md:123,129,499,531`). `gh-persist.sh`'s leading `test -s <body_path>` gate (the empty-body gate) is what makes this enforceable — an empty/missing staged file surfaces as `DECISION_NEEDED: PERSIST_* called with empty body file at <path>` rather than posting silently (`SKILL.md:36,503,507,542`).
- **Match before file (question de-dup).** "proposing a file before checking is how you offer to duplicate a question that already exists" (`SKILL.md:319`). Applies to every companion-question resolution in Step 3.5.
- **Never silently absorb an unresolved source-doc OQ.** "if you spot an OQ gating this issue, surface it and give it a Step 3.5 disposition rather than baking the undecided part in" (`SKILL.md:185`) — building on an undecided OQ "silently freezes a decision that isn't yours to make" (`SKILL.md:181`).
- **`in-scope (blocked)` never emits a dangling `blocked_by`.** "Never emit `blocked_by=` with no `#N`" (`SKILL.md:329`) — a native block can't point at a question that doesn't exist, so the disposition falls back to `scoped-out` or a prose-only blocker when the user declines to file a companion.
- **Preserve the plan pointer verbatim on revise.** "If the issue body carries a `> 📋 **Implementation plan:**` pointer line ... keep it verbatim in the revised body — don't drop it, don't duplicate it, don't touch the plan comment it links to" (`SKILL.md:119`) — the plan is the planner's artifact; the drafter must not disturb the bridge to it.
- **Never edit or delete the plan comment itself.** "Never edit or delete the plan comment itself; it's the planner's artifact, refreshed only by re-running that skill" (`SKILL.md:76`).
- **Do not use auto-close keywords unless the user explicitly said this issue resolves another.** "Those keywords cause GitHub to auto-close the referenced issue when this one closes — a side effect the user must opt into" (`SKILL.md:243`).
- **Mirror the user's hedging in related-issue phrasing.** "if they said 'may be resolved,' the draft says 'may be resolved.' Don't upgrade uncertainty into certainty" (`SKILL.md:245`).
- **Findings without evidence are dropped, never acted on.** "'Seems unclear' without a quote and an alternative wording does not pass the bar" (`SKILL.md:438`) — same anti-fabrication bar as drafting itself ("Never invent reproduction steps, error messages, or behavior the user didn't describe" — `SKILL.md:315`).
- **The review sub-agent must be isolated from conversation history.** "The isolation property is what makes the review meaningful — leaking conversation context defeats the purpose" (`SKILL.md:406`); the sub-agent tests whether the issue stands on its own the way a teammate reading it cold six months later would (`SKILL.md:375`).
- **Review loop has a 3-pass cap and a circular-repeat guard.** "don't iterate forever on a finding that's either wrong, unactionable, or needs human judgment" (`SKILL.md:468`); a repeated finding with no progress exits to the user rather than burning the third pass guessing (`SKILL.md:466`).
- **Epic filing is all-or-nothing per batch, sequenced Epic→stories→patch.** "there's no 'file the Epic now, promote bullets later' mode — a half-filed Epic with placeholder bullets is exactly what this flow exists to avoid" (`SKILL.md:279`); on a mid-batch failure, "stop and report exactly what filed and what didn't — don't blind-retry" (`SKILL.md:287,542`).
- **File companion questions before the build issue that references them.** "so no dispatch forward-references an issue that doesn't exist yet" (`SKILL.md:511`).
- **Don't fabricate an `## Out of scope` section.** "Inventing out-of-scope items the user never mentioned is a form of hallucination — resist it" (`references/issue-templates.md:125`).
- **Coalesce thin story slices; don't over-split.** "Splitting has a cost the issue body never shows... Slice too thin and that tax dominates" (`SKILL.md:267`) — balanced by a guardrail against over-coalescing independently-valuable slices (`SKILL.md:275`).
- **A `Blocked by #N` prose line always survives even when the native dependency can't be set.** Capability-gated degradation: "on a repo/gh without the feature, and the prose `Blocked by #N.` line is the always-present fallback — so keep the prose line regardless" (`SKILL.md:255`).
- **Audience labels are created, not merely suggested (unlike type/priority labels).** "The label is the whole point of an audience question — one filed without it can't be found by the people meant to answer it" (`_shared/question-issue.md:74`).
- **A question's handoff is terminal.** "it's answered by a human, not a downstream skill" (`SKILL.md:147,550`) — no `research:`/`plan:` markers apply.

## Sub-agents dispatched

| Sub-agent | Reference prompt file | Consumes | Returns |
|---|---|---|---|
| `github-ops` (`subagent_type: "github-pipeline:github-ops"`, Sonnet + medium, no `model` override) | `agents/github-ops.md` (not under this skill's `references/`) | Named op (`GATHER_ISSUE`, `GATHER_EPIC`, `PERSIST_CREATE`, `PERSIST_BODY`, `PERSIST_LINK`) + params | Structured `## RESULT` envelope: scalars + path references (`issue_body_path`, `thread_path`, `marker_comment_path`, etc.), or `DECISION_NEEDED: <…>` on ambiguity | `SKILL.md:18-40,70-76,133` |
| Issue reviewer (`Explore` type) | `references/issue-reviewer-prompt.md` | Draft (title/body/labels/priority/type), mode (`draft`/`revise <N>`/`split`), repo root, open-question markers, dimensions to check, related drafts (siblings for Epic) | `## Review summary` + `## Findings` block: severity (BLOCKER/SUGGESTION/NIT), dimension, evidence, what's wrong, remediation — or `Findings: 0` clean exit | `SKILL.md:383-478`; format in `issue-reviewer-prompt.md:85-120` |

Note: the sub-agent cannot call `AskUserQuestion` (`SKILL.md:33-36`); on ambiguity `github-ops` returns `DECISION_NEEDED: <…>` and writes nothing, which the main loop surfaces and re-dispatches after resolving.

## Known bugs / gaps

- **Dimension-count/table mismatch in the Step 5 review spec.** `SKILL.md:410` states "Six
  dimensions," but the table immediately below it (`SKILL.md:412-420`) lists **seven** numbered
  dimensions (1 Doc coherence, 2 Codebase coherence, 3 Internal coherence, 4 Latest-decisions, 5
  Story ordering, 6 Completeness, 7 Story sizing/over-split), and `SKILL.md:422` assigns dimensions
  5 and 7 to Epic sizing/ordering by number. `references/issue-reviewer-prompt.md:34` corroborates
  the 7-element set: "a subset of {1, 2, 3, 4, 5, 6, 7}." The prose count and the table/usage
  disagree by one; this spec records the inconsistency as v1 behavior rather than silently
  reconciling it to "seven."

(The two known planner bugs named in the S1 brief — an OQ with an existing tracker issue recorded
as "(not filed)," and the handoff's open-questions line dropping in combined epic+story sessions —
are **planner** defects and are recorded as falsifiable requirements in `docs/specs/planner.md`,
not here.)
