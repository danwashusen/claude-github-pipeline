# Epic split — fresh Epic batch, epic-revise, and promotion

Route for the Epic shape (`vector.mode: epic-revise`; a new-mode session the router overrode after
classifying the feedback as **Epic**; or a revise-mode session the router overrode to **promote** the
target into an Epic — SKILL.md §2). One playbook serves all three: a fresh Epic files the whole set in
one batch; an epic-revise reconciles the existing set; a promotion rewrites #N in place as the Epic and
batch-files its stories (values below). An Epic decomposes into **independently shippable** stories —
each a separate PR, review, and merge.

This route uses the shared spine's primitives — read [`draft-spine.md`](draft-spine.md) for the review
loop, the Step-3.5 open-question resolution, and the staged-filing discipline; the E1–E3 sequence below is
this route's own (the batch filing skips the single-issue confirmation gate — E3).

## Step E1 — Settle the split (coalescing + adversarial loop)

Produce the candidate story list — each a short title plus a one-line scope naming the files, layer, and
test surface it will touch (the two bookend slots below carry slot-level scopes instead). Apply the **coalescing pass** yourself first: "independently shippable" is a
ceiling, not a target — every story pays a fixed tax (worktree + per-worktree resources, baseline, cold
build/boot, targeted test run, review round-trip) before its own work counts, so aim for the **coarsest**
slicing that still keeps each story independently shippable. **Merge** a pair/cluster when any fire:

1. **Shared verification surface** — they'd re-run the same build / integration target / snapshot set.
2. **Sequential with no standalone value** — one slice only feeds the next and delivers nothing a reviewer
   could sign off alone (a wiring change meaningless until its view lands; deleting a legacy component once
   its sole consumer is rewired).
3. **Same files / layer, individually thin** — several small edits a reviewer reads as one change.

**Guardrail — don't over-coalesce.** Keep slices separate when each has independent value, a clean
contract, *and* a cheaper isolated test surface (the clearest case: pure functions/models with fast unit
tests and no build/UI/snapshot cost). Thin is not the same as mergeable.

**Bookend stories (default slots, planner-filled).** After coalescing, the candidate list includes two
bookends by default:

- **Technical-foundation story, first** — the slot for shared groundwork that two or more later stories
  will consume (contracts, schema, scaffolding, build plumbing). Keep its one-line scope at the slot
  level; never enumerate the seams — identifying and pinning them is the planner's job (seam
  dispositions + the epic plan's `## Story contracts`).
- **Finalization story, last** — the slot for the end-of-epic sweep: cleanup of what the epic
  accumulated, updating the project docs to reflect what actually shipped, epic-level DoD verification.
  Never itemize the sweep — its just-in-time plan grounds on the epic delivery log, which exists only
  after the other stories land.

The slots exist at draft time because the planner never files issues and needs filed issues to plan
into; their first/last positions bracket the filed story order. Omission is
allowed but **never silent**: record the omitted bookend and a one-line reason as a note in the Epic
body's `## Background` (e.g. `_No foundation story: the shared groundwork is story #1's
entire scope._`) so it survives the E2 re-confirm and every epic-revise; the split reviewer may
challenge the justification.

Then hand the split to the review sub-agent in **`split` mode** (dimensions **5 and 7 only**, adversarial,
grepping the codebase to ground every surface-overlap claim). Apply its merges/reorders and re-loop under
the standard control (3-pass cap + circular guard, per the spine's review loop).

## Step E2 — Draft bodies and confirm the review

Draft the Epic body and every Story body per the built-in templates
([`../references/issue-templates.md`](../references/issue-templates.md)) — each Story's first line is the
`**Epic:** #<epic-#> — <Epic title>` backlink. Run the spine's review loop over the set: dimensions
`1, 2, 3, 6` on each body **plus a re-confirm of 5 and 7** on the real bodies (a body can reveal a slice is
bigger/smaller than its one-line scope claimed). Resolve OQs per the spine's Step 3.5 for the Epic and each
Story that a gating OQ touches.

Bookend bodies use the Story template with **explicit deferral placeholders**, never invented specifics —
e.g. a DoD entry "Deliver the shared groundwork pinned by the epic plan's `## Story contracts` (specified
at planning time)" or "Cleanup + doc-reality sweep per the just-in-time plan (grounded on the epic
delivery log)". Deferral is the sanctioned placeholder form here; a fabricated seam list or cleanup list
in a bookend body is the defect (anti-fabrication), not the placeholder.

## Step E3 — File the batch (hands-off on a clean run)

This is the **one** place the drafter skips the human filing gate: a clean E1+E2 pass *is* the go-ahead —
the split loop + body review stand in for the confirmation. Stage every body to `facts.scratch` first
(Epic → `epic.md`, each Story → `story-<i>.md` with its backlink already written in), then file the
Epic, then each Story **in dependency order** with `--parent <epic-#>`:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py create <owner/repo> "<facts.scratch>/epic.md" --title "Epic: <theme>" --label epic
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py create <owner/repo> "<facts.scratch>/story-<i>.md" --title "<story title>" --label story --parent <epic-#>
```

`--parent` establishes GitHub's native parent/sub-issue relation in the same round-trip that files the
story ([`../../_shared/epic-story-hierarchy.md`](../../_shared/epic-story-hierarchy.md)) — that relation, not any body text, is what drives the epic's
sub-issue panel and its progress rollup. Sub-issues append, so filing in dependency order gives the
panel that order for free. There is **no epic-body patch step**: the epic body never lists its stories
(`../references/issue-templates.md`), so nothing needs swapping after the numbers come back.

All-or-nothing per batch, sequenced Epic → stories. On a mid-batch `create` failure, **stop and
report exactly what filed and what didn't** — don't blind-retry. On `EMPTY_BODY_FILE`, re-stage that one
body and re-run with the same path. A `SUBISSUES_UNSUPPORTED` notice means the story filed but the
relation didn't (the host doesn't serve it) — report it in the summary and carry on; it degrades what
GitHub renders, never the batch.

## Promotion — an existing standard issue becomes the Epic

A revise-mode session the router overrode to promote (SKILL.md §2) runs E1–E3 with these values. A
planner seam-analysis comment in the thread (prep spills it) pre-seeds E1's candidate story list; the
split reviewer may disagree with those suggested boundaries — ground its verdict as usual. E2's bodies
redistribute #N's original content across the Epic and Story bodies (edit history preserves the
original).

- **The Epic body lands on #N via `edit-body`, not `create`.** That rewrite is destructive where a
  fresh `create` is not, so it does **not** ride E3's gate-skip: inherit `revise.md`'s discipline —
  diff-show the old→new body (Title; Labels ±; changed/added/removed sections) and wait for **explicit
  confirmation** before applying, and preserve any `> 📋 **Implementation plan:**` pointer line
  verbatim (the superseded plan comment is the planner's artifact; the Epic's own re-plan replaces it).
- **Label swap in the same step:** `gh_persist.py edit-labels <owner/repo> <N> --add epic --remove feature`.
- **Stories still file via `create --parent <N>`** (E3 unchanged, its gate-skip intact — the clean
  E1+E2 pass plus the confirmed #N rewrite cover the batch). The promoted #N is the parent like any
  freshly-filed epic; if its original body carried a `## Stories` section, the rewrite drops it.

## Epic-revise reconciliation

For `vector.mode: epic-revise`, `facts.epic_revise.stories` carries the epic's story set with live
per-story state, and `facts.epic_revise.stories_source` names which tier produced it
([`../../_shared/epic-story-hierarchy.md`](../../_shared/epic-story-hierarchy.md)):

- **`sub-issues`** — the native relation. Story state *is* the record, so there is nothing to
  reconcile and no mismatch to flag.
- **`checklist`** — a legacy epic whose stories live in a `## Stories` section. Reconcile the
  checkboxes (closed → checked; open → unchecked) and `edit-body` the reconciled body;
  `facts.attention` flags each checkbox/live-state mismatch. Leave the section in place — this epic
  has no native relation, so the checklist is still its only story record.

Either way, re-run the **dependency-graph ordering (5)** and **sizing / over-split (7)** dimensions
against the current story set. Surface findings with evidence + a proposed re-order/merge for the user
to confirm — don't silently merge or re-order (a sizing finding can't un-file a story; it's a
recommendation). Dimension 7's bookend check rides this same re-run: a missing-bookend finding is a
recommendation like any sizing finding, and a confirmed new bookend files through the new-stories path.
Then batch-file only genuinely **new** stories (the same E2/E3 discipline, `--parent <epic-#>` included
so a story added to a legacy epic still gets the native relation).

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md) immediately before
composing this and emit the matching shape verbatim — copy it, substitute only the data below, never
rename a field or restructure it. **Epic batch filed** →
forward to the planner on the Epic — `Epic:` line (`plan: ✗`) + `Stories:` line (the filed,
dependency-ordered set) + `Next: /github-pipeline:planner #<epic-#>`; `Why:` the planner posts the
epic-level plan (contracts + sequencing), then each story is planned just-in-time. Add the
`**Open questions:**` line when any filed body carries an `## Open questions` section.
