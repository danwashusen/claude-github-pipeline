---
name: drafter
description: Drafts well-structured GitHub issues from informal developer feedback and files them, or revises an existing one. Use this skill whenever the user describes a bug they hit, an incomplete or half-built feature they noticed, or a new feature idea — and wants it captured as a GitHub issue. Trigger this even when the user does not explicitly say "make an issue" — phrases like "I should track this," "let's file this," "we need to remember to fix X," "log this for later," or simply describing a problem in a repo context all qualify. Also use this skill to **revise an existing issue** when the user references one by number/URL with revision intent — phrases like "revise #N," "update issue #N," "improve #N," "does #N still match the docs?", or "rewrite the description of #N." Also use it to **file or track an open question / decision request** for one or more named audiences (business, architect, developer, UX, …) as a `question`-type issue labeled by audience — but only on an explicit capture verb: "file/open/log/track a question," "capture this decision for the architect," "raise an issue to ask the business," or "track `PRD-OQ-06b` as an issue." A bare decision-question with no capture intent ("should we use phone or video?") is asking for *your* answer and is **not** a trigger; naming an audience alone ("the business should weigh in on this") isn't one either without a file/track/log verb. Works best when the user is inside a git repository directory. Uses repo issue templates and labels if they exist, otherwise applies a consistent built-in format. Reads the project PRD (if one exists at `docs/prd.md` or similar) to ground feature framing and surface tensions between feedback and spec. Every drafted or revised issue is automatically validated by an isolated review sub-agent that checks the issue against the project's PRD, architecture, constitution, and current codebase before the user sees the final draft. Do NOT use for: writing or fixing code (that's the resolver), planning the approach (that's the planner), reviewing a PR or choosing a merge strategy (that's the evaluator).
---

# drafter — router

The first stage of the pipeline: informal feedback in → one filed/revised, template-conformant issue
(bug / incomplete / feature / story), **or** a filed Epic plus its child stories in one batch, **or** a
filed/revised `question`-type issue — always ending in a single `## Handoff`. The drafter files; the
planner researches and attaches the plan later, the resolver builds it. One drafting attempt, one
session; nothing survives between runs except what is persisted to GitHub. Read this router, run prep,
route to exactly one playbook, then hand off. Scripts own the mechanical I/O; your judgment is the
classification, the PRD-tension calls, the drafting, the open-question dispositions, the review
verdicts, and the handoff `Why:`.

## 1. Prep

Assemble the entire starting state in **one** call. `<owner/repo>` is the repo; `--issue N` selects
revise/epic-revise mode (a target issue exists) — omit it for new-issue mode:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/prep_drafter.py <owner/repo> [--issue N]
```

It returns one JSON **facts block** (`architecture.md §4`): `vector` (`mode` × `type` — the routing
contract), `suggested_playbook`, `target` (revise/epic-revise: number/title/state/labels/`blocked_by`/
`blocking`/`deps_available`), `config.oq_markers` (the `<!-- drafter-open-question-markers -->` block, or
`heuristics_active` — a **detection hint**, never a gate), `repo_context` (issue templates, `gh label
list`, grounding-doc presence), `open_questions` + `open_question_candidates` (the search-before-file
tracker de-dup on the target body), `revise`/`epic_revise` mode facts, `sections` (spilled issue-body/
thread/plan-marker paths), and `attention`. Consume every fact as **data** — never re-derive the mode,
the target's type, or the tracker candidates in prose; prep already did.

**Decision card rule.** If prep exits with `status: needs_decision`, render its `decision` as one
`AskUserQuestion` card (per [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md)), act on the
answer, and re-run prep. This is the single universal handler for every closed-set code (`AUTH_REQUIRED`,
`AMBIGUOUS`, …).

**Newly-detected OQ lookup.** When you spot an open question in the feedback/grounding text that prep's
body-driven `open_question_candidates` never searched (new mode has no target body; a grounding-doc OQ
isn't in the issue body), run the tracker de-dup search before recording it `(not filed)` or filing a
companion — one authorized call, never a raw `gh issue list`:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/prep_drafter.py <owner/repo> --oq-query "<OQ topic>"
```

## 2. Route

Prep proposes `suggested_playbook`; confirm it against this table, keyed on `vector`. Read **exactly
one** playbook.

| `vector` | Playbook | Flow |
|---|---|---|
| `mode: new` (no target issue) | `playbooks/new.md` | classify → gather → draft → review → gate → file a single build issue |
| `mode: revise`, `type` ≠ `question` | `playbooks/revise.md` | fetch + latest-direction → review → diff-show → confirm → edit-body |
| `mode: revise`, `type: question` | `playbooks/question.md` | revise the question issue; terminal handoff |
| `mode: epic-revise` | `playbooks/epic-split.md` | reconcile `## Stories` + re-run ordering/sizing; batch-file only what's new |

Every playbook opens by reading the shared spine [`playbooks/draft-spine.md`](playbooks/draft-spine.md)
(gather missing context → resolve open questions → draft against the template → review loop → show +
filing gate → staged filing → hand back). The routed playbook supplies only what **differs in actions**:
its reconnaissance, the template sections it fills, the reviewer dimension set, the filing sequence, and
its handoff shape. Type differences the spine consumes (which template, which dimensions, single-vs-batch
filing) are **facts / values**, never branches.

**New-mode classification override rule** (`architecture.md §5`). Prep can't read the feedback text, so it
proposes `new.md` for **every** new-mode session (`vector.type` is `null`). Step 1 of `new.md` classifies
the feedback — bug / incomplete / new feature / Epic / question. When that classification is **Epic** or
**question**, the router **overrides** `suggested_playbook` and reads `epic-split.md` (fresh Epic) or
`question.md` (a direct question) instead — evidence the script could not see ahead of the read. State the
override reason (the S13-scenario-3 precedent: a route the classification, not the label, selects). One
route per session; do **not** interleave type branches inside a playbook body — the route *is* the branch.

**Feature-vs-Epic is a gate, not a silent promotion.** When Epic signals fire but scope is genuinely the
user's call, `new.md`'s Step 1 asks (`header: "Issue size"`) before the override — confirm, don't promote.

**Promotion override (revise → Epic split).** A revise-mode session reads `epic-split.md` instead of
`revise.md` when the invocation itself says to re-shape the target as an Epic (e.g. a planner handoff's
"revise #N as an Epic — split per the seam-analysis comment"). If only the *thread* carries that
recommendation and the invocation doesn't, the size call is still the user's — ask first
(`header: "Issue size"`), never promote silently. State the override reason. Promotion rewrites #N in
place, so it inherits `revise.md`'s diff-show + explicit-confirm and plan-pointer preservation
(`epic-split.md`, "Promotion").

## 3. Invariants

Universal across every route:

- **Nothing is filed without the Step-6 gate** — except the Epic one-shot batch, where the adversarial
  split loop + per-story body review *stand in* for the human confirmation (a clean pass is the go-ahead).
  Silence, a tweak request, or "Other" all count as keep-iterating. "Filed issues are annoying to clean
  up; a 10-second confirmation prevents that."
- **Staged-body writes.** Every GitHub write goes through `${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py`
  via Bash: stage the verbatim body to `facts.scratch` (`/tmp/gh-drafter-<issue-or-"new">/…`) and pass the
  **path**. The script gates empty bodies (`EMPTY_BODY_FILE`) and returns `body_sha256` — the #626/#627
  empty-body race fix (the body never travels through a dispatch prompt). The drafter has **no** scriptless
  raw-`gh` executor; if a real op doesn't fit a subcommand, that's a gap to report, not a raw call to roll.
- **Successful write is self-confirming.** A zero exit with a URL *is* the confirmation; never re-read the
  issue to check it landed.
- **Never silently freeze an untracked OQ.** An OQ that gates a build issue's scope gets a Step-3.5
  disposition + a tracked companion (matched or filed) before it enters the body — the falsifiable rule in
  [`playbooks/draft-spine.md`](playbooks/draft-spine.md). Absorbing an untracked OQ silently is a defect.
- **Never touch the plan comment.** Revise mode reads the `<!-- implementation-plan:v1 -->` pointer to
  preserve it verbatim; it never edits or deletes the comment — that's the planner's artifact.
- **Anti-fabrication.** Never invent reproduction steps, error messages, behaviors, out-of-scope items, or
  relationships the user didn't describe. A vague-but-honest issue beats a confidently-wrong one.
- **Gates only for genuine decisions** (per [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md)):
  issue size, ambiguous classification/reference, PRD conflict, OQ disposition, companion reuse-vs-file,
  the filing gate, revise state-summary + diff confirmation, closed-issue handling, review-loop tie-break.
  A judgment sub-agent (the issue reviewer) never calls `AskUserQuestion`; it returns findings to this loop.
- **Handoff on clean exit** (§4). One `## Handoff` block ends every clean run; it replaces any bullet-list
  summary. Don't add anything after it.

## 4. Handoff

Every clean run ends with a single `## Handoff` block — the only bridge to the next session. The schema,
omission rules, and closed-set state-marker vocabulary are owned by
[`../_shared/handoff-format.md`](../_shared/handoff-format.md); the drafter's per-outcome shapes (single
issue filed → planner; single issue with open questions → planner + `**Open questions:**` line; Epic batch
→ planner; revise → author/refresh/terminal; the terminal `question` shape) are in
[`references/handoff-renderings.md`](references/handoff-renderings.md). **Read that reference immediately
before composing the handoff — not earlier in the session — then emit the matching shape verbatim.** The
field names (`**Issue:**`/`**Epic:**`, `**Next:**`, `**Why:**`, …), the block structure, and the closed-set
state markers are **contract, not prose to summarize**: copy the shape and substitute only the
issue/Epic/story numbers, titles, and state values it names — never paraphrase, restructure, rename a
field, drop a segment, or add a block the shape doesn't have. Concretely forbidden (observed live-parity
drift): renaming `**Issue:**` to `**Filed:**` or anything else; dropping the `· <state> ·` segment; adding
an invented `Snapshot` (or similarly-named) block; inlining the fenced `Next:` command into prose instead
of its own indented code line. Fill the snapshot from data in hand — the `create` result carries the
issue/Epic/story numbers and titles; `plan: ✗` is always correct (the drafter never authors plans). The
`Why:` line is yours. The forward route is the `planner` (`/github-pipeline:planner`); an OQ deferral
points at `/github-pipeline:question-sweep`. A `question`'s handoff is **terminal** — a human answers it,
not a downstream skill. The handoff is the only signal; the user runs the next command in a fresh session
(session-per-skill is the context-isolation choice).
