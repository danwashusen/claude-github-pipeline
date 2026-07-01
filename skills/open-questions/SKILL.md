---
name: open-questions
model: opus
effort: high
disable-model-invocation: true
description: Reconcile the project's open questions between its docs and the GitHub tracker. Scans docs for unresolved open questions (`PROVISIONAL` / `TBD` / "open question" markers, or a repo-declared pattern), cross-checks them against the `question`-type issues that are the registry of record, then proposes filing the untracked ones, flagging docs left stale by an answered question, and adding the missing doc↔issue back-links. Reports first and applies only on confirmation — never silently rewrites a doc or files an issue without a gate. Explicit-invocation only — run it as `/github-pipeline:open-questions [docs-path-or-glob]`. It is a periodic hygiene sweep, **not** a pipeline stage and **not** for use mid-drafting or mid-planning: a bare open question raised in conversation ("should we use phone or video?") is asking for *your* answer, not a trigger to run this. Not for code, pull requests, or filing a single issue (that's `github-issue-drafter`).
---

# Open-questions sweep

Reconcile the project's **open questions** (OQs) between the docs that raise them and the GitHub
tracker that answers them. OQs aren't centralized — they live inline in *any* doc — and the **registry
of record is the set of `question`-type issues**, not a doc field: docs are the sources, the tracker is
the truth. A doc marker can lag a decision made in a question's thread, so this sweep's job is to find
the drift and close it — filing what's untracked, flagging what's stale, and wiring the back-links —
so the two stay in sync.

This skill **reports first and applies only on request**. Docs and issues are expensive to get wrong,
so you show the full reconciliation before touching anything: GitHub writes gate on the user; doc edits
are shown as a diff and applied only on confirmation.

Shared contracts (read as you reach the step that needs them):
[`../_shared/open-question-detection.md`](../_shared/open-question-detection.md) (find + match OQs),
[`../_shared/open-question-links.md`](../_shared/open-question-links.md) (the `## Open questions`
section, dispositions, and the tiered status read),
[`../_shared/question-issue.md`](../_shared/question-issue.md) (the `question`-issue body schema).

Use a scratch dir under `/tmp/gh-open-questions-<short-slug>/` for staged issue bodies and any spilled
gather output. Never write plugin-bundle paths.

## Step 1 — Scope and capabilities

- **Scope.** Parse the path/glob argument. Default to `docs/**` plus any register locations the config
  block declares (Step 1 config read). If the user named a path, honor it.
- **Repo.** `gh repo view --json nameWithOwner -q '.nameWithOwner'`.
- **Detection config.** Read the consuming repo's `<!-- drafter-open-question-markers -->` block via
  `${CLAUDE_PLUGIN_ROOT}/scripts/config-block.sh read CLAUDE.md drafter-open-question-markers` (or a
  plain read); if absent, use the heuristic cues. Both paths are defined in
  [`../_shared/open-question-detection.md`](../_shared/open-question-detection.md) — read it now.
- **Labels.** `gh label list --limit 100` (you need `question` and any `audience:*` labels; note which
  are missing so Step 6 can offer to create them).

If there are no docs in scope, report "nothing to reconcile" and stop.

## Step 2 — Detect OQs across the docs

Detect project-wide — **every** OQ in scope is a candidate (unlike the drafter, which filters to one
issue's gated scope). To bound cost:

1. **grep-prefilter** the scope for the detection cues defined in
   [`../_shared/open-question-detection.md`](../_shared/open-question-detection.md) (the config-block
   pattern, else its heuristic cues) to get the candidate files.
2. **Confirm** by fanning out `Explore` sub-agents over the candidate files (one per file, or batched
   for many small files). Each returns, per real OQ: `{source doc + location, topic/text, native id if
   any, inline "tracked in #N" if any, gated scope}`. `Explore` reads excerpts — that keeps the doc
   bytes out of this loop.

Report how many files were prefiltered vs. read, so a narrowed scope is never silent.

## Step 3 — Load the tracker registry

The `question`-type issues are the registry. Fetch the skeleton inline (a lightweight list read, like
the drafter's de-dup search):

```bash
gh issue list --repo <owner/repo> --state all --label question --limit 500 \
  --json number,title,state,labels,url
```

This gives each question's `#`, title, `state` (half of Tier-1 status — free here), and `audience:*`
labels. For a question you need to **match** (its `## Tracked in` back-links) or **status-read** (its
thread), fetch the body/thread through `github-ops` — passing the decision marker as `marker_prefix` so
`marker_comment_present` supplies the other half of Tier 1 (a recorded decision → resolved, no reader
needed). Don't hand-roll `gh issue view`:

> `Agent(subagent_type: "github-pipeline:github-ops", no model override)` with
> `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- question-decision:v1 -->", scratch_dir=/tmp/gh-open-questions-<slug>/)`

## Step 4 — Reconcile

Match each doc-OQ to a tracker issue per [`../_shared/open-question-detection.md`](../_shared/open-question-detection.md)
(native id first, else topic keywords + `Read` the candidate body to confirm it's the same OQ). Then
classify every OQ and every question issue into one class:

- **untracked** — doc marker, no matching question issue → propose **filing** a companion (Step 6).
- **stale-doc** — the matched question is **resolved** but the doc still marks the OQ open (or lacks a
  resolution note) → propose a doc update per [`../_shared/open-question-links.md`](../_shared/open-question-links.md)
  §"Doc fold-back" (rewrite to the decided state / remove the marker / flip the register). Read
  resolution via the **tiered status read** in [`../_shared/open-question-links.md`](../_shared/open-question-links.md)
  §"Status is the tracker's": Tier 1 = a `closed` question **or** one carrying a
  `<!-- question-decision:v1 -->` comment (`marker_comment_present` from Step 3) is resolved; Tier 2 =
  for a still-`open` question with no decision marker, dispatch the status reader (Step 4a) and treat
  `resolved-in-thread` as resolved. The tracker wins over the doc.
- **missing-back-link** — question open, doc marker present, but no inline `tracked in #N` (and/or the
  question's `## Tracked in` doesn't name the doc) → propose adding the link **both** ways.
- **orphaned-issue** — an open question whose doc marker is gone (decision folded but the issue never
  closed) → surface it and suggest closing; **never auto-close**.
- **in-sync** — matched and consistent → count only, no action.

### Step 4a — Tier-2 status read (only for still-`open` questions)

When a doc says open and the matched question is still `open`, you can't tell from state alone whether
the thread already answered it. Read the question's body + thread (from Step 3's `GATHER_ISSUE`) with
the status reader: `Read` [`references/question-status-reader-prompt.md`](references/question-status-reader-prompt.md),
fill its `<<...>>` placeholders (issue #, repo, body, thread — pass the scratch paths github-ops
spilled, or inline content), and dispatch it as an `Explore` sub-agent. It returns a typed reading —
`resolved-in-thread` (→ stale-doc) / `still-open` (→ in-sync or missing-back-link) — or an `AMBIGUOUS`
exception (surface it; don't guess). Skip this when Tier 1 already answers — a `closed` question or one
carrying a `<!-- question-decision:v1 -->` comment.

## Step 5 — Report and gate

Present **one** consolidated reconciliation report, grouped by class, each entry naming the OQ, the
doc location, the matched issue (if any), and the proposed action with its evidence (a quote + the
question's state/thread finding). Don't fire a card per OQ — the report is the review surface.

Then gate the actions:
- **GitHub writes** (filing companions, back-link edits to issue bodies) — confirm via `AskUserQuestion`
  per [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md).
- **Doc edits** — propose-then-apply-on-confirm: show the exact diff/snippet and apply only on "yes".
- **Never** auto-close or auto-resolve a question — that's the human's call in the thread (the closing
  protocol in [`../_shared/open-question-links.md`](../_shared/open-question-links.md)).

## Step 6 — Apply approved actions

- **File a companion question** (untracked class): build the body per
  [`../_shared/question-issue.md`](../_shared/question-issue.md) (template, `## Tracked in` naming the
  source doc, audience labels), stage it to `/tmp/gh-open-questions-<slug>/q-<slug>.md`, create any
  missing `audience:*` label inline, then file through `github-ops`:
  > `PERSIST_CREATE(repo=<owner/repo>, title=<title>, body_path=<staged_path>, labels=[question, audience:*, …])`
- **Apply a doc edit** (stale-doc / missing-back-link): use `Edit` on the consuming-repo doc — the
  §"Doc fold-back" moves (add the `tracked in #N` back-link, a resolution note, or remove a retired
  marker) exactly as shown at Step 5.
- **Patch a question's `## Tracked in`** (missing-back-link): fetch current body, add the doc location
  and/or build-issue `#`, and write it back through `github-ops`:
  > `PERSIST_BODY(repo=<owner/repo>, issue=<N>, body_path=<staged_path>)`

Every GitHub write goes through `github-ops` (never hand-rolled `gh … --body-file`), and every body is
staged to a scratch file first (the path-based write contract that closes the empty-body race).

## Step 7 — Summary

Close with a plain summary (this is a hygiene sweep — **not** a pipeline `## Handoff`): companions
filed, docs updated, back-links added, and any discrepancies left (orphaned issues, `AMBIGUOUS` reads,
declined actions). If a resolved OQ means a **filed build issue** now needs its plan revisited,
breadcrumb it in prose — "#<build> depended on `<oq-id>`, now answered in #<question>; consider
`/github-pipeline:github-issue-planner <build>` to revise" — a pointer, not a forward handoff.
