---
name: slicer
description: You have one filed GitHub issue that is too large to plan or build as a single unit, and you want it cut into ordered, operator-approved **deliverable slices** filed as native sub-issues so GitHub's own rollup tracks delivery progress. Use this skill for requests like "slice #103", "cut #103 into deliverable slices", "break this story into demonstrable increments before we plan it", "decompose #103", "what are the slices for #103", or when the planner re-routes here saying an issue wants slices rather than promotion to an Epic. It is report-then-apply: nothing is written to GitHub until you confirm the whole cut, and it refuses rather than guessing when the repo declares no grounding documents. Also handles the resume case — re-run it on a partially-sliced issue and it reports what exists and cuts only the remainder. Do NOT use it to split an Epic into stories (that is the drafter), to author the plan or its phases (planner), to write code (resolver), to file an ordinary issue (drafter), or on an issue that is blocked, closed, a question, or itself a slice — it refuses each of those and says why.
---

# slicer — router

Cut **one filed issue** into ordered **deliverable slices** and file them as native sub-issues in
approved order. One session; the slices and the handoff are all that survive. Read this router, run
prep, run the one playbook, hand off. Your judgment is the decomposition: where the seams are, what the
walking skeleton is, how thick each slice should be, and whether the grounding supports cutting at all.

A slice is a **phase marker**, not a sub-story — no branch of its own, so its bar is *independently
demonstrable*, and the resolver ships it as a phase on this issue's branch and closes it as that phase
lands. That closing is what makes the parent's rollup a live progress record; the definitions and the
closing contract are [`../_shared/epic-story-hierarchy.md`](../_shared/epic-story-hierarchy.md).

## 1. Prep

Assemble the entire starting state in **one** call:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/prep_slicer.py <issue> <owner/repo>
```

It returns one JSON **facts block** (`architecture.md §4`): `vector` (`type` × `mode` (`fresh`/`resume`)
× `refusals`), `suggested_playbook`, `target` (number/title/state/labels/`type`, the typed `parent`, open
`blocked_by`), `slices` (existing sub-issues in panel order + `count`, `open_count`, `next_index`),
`grounding_docs` (the repo's `<!-- doc-catalogue -->` entries — `path`/`role`/`authority`/`present`),
`research` (dossier present), `open_questions` (the `in-scope (blocked)` entries), `sections` (spilled
body/thread paths), and `attention`. Consume each as **data** — never re-derive the type, the mode, the
refusal set, or the slice numbering.

**Decision card rule.** If prep exits `status: needs_decision`, render its `decision` as one
`AskUserQuestion` card (per [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md)), act,
and re-run prep — the single universal handler for every closed-set code (`AUTH_REQUIRED`).

## 2. Route

| `vector` | Route |
|---|---|
| `refusals: []` (`mode: fresh` or `resume`) | `playbooks/cut.md` |
| `refusals` non-empty | no playbook — refusal handoff, stop |

On a refusal, **do not read the playbook**: render the matching shape from
[`references/handoff-renderings.md`](references/handoff-renderings.md) (first token wins; the `attention`
line carries the evidence) and stop. Nothing is written on any refusal path.

`fresh` and `resume` share one playbook deliberately: they differ only in **values** (which slices exist,
what index numbering resumes from), never in actions taken — facts, not a branch (CLAUDE.md's
"parameterize before you playbook"). No route override either — the refusal set is closed and fully
mechanical: `epic-target` (the drafter splits an epic into *stories*), `slice-target` (**a slice is never
sliced** — no branch, so a sub-slice could not ship), `question-target`, `closed-target`, `blocked` (an
open native blocker or an `in-scope (blocked)` open question — cutting against an unanswered question
produces slices the answer may invalidate).

## 3. Invariants

- **Zero GitHub mutations before the one write gate.** Everything up to the cut summary is a read;
  everything after it is a write ([prd.md §8.2](../../docs/prd.md) report-then-apply). Aborting at the
  gate costs nothing — that is the point of the gate, so never let a write creep earlier.
- **The parent's body is never edited**, and no `## Slices` section is ever written (the shared
  contract says why). Slice detail lives only in slice bodies.
- **Grounding is required, and every slice cites it.** Cut only from what the repo's declared docs,
  the issue body/thread, and any dossier actually record. A slice citing nothing is a gap in the
  source or invented scope — surface it, never file it. No catalogue and no operator-named sources →
  refuse: decomposing from a two-line body invents scope, and invented scope becomes real issues the
  pipeline then plans against.
- **Sequential creation in approved order.** `addSubIssue` appends, so creation order **is** display
  and delivery order: file one slice at a time via
  `${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py create --parent`, staging each body to `facts.scratch/`
  and passing the **path** (the script gates empty bodies and returns `body_sha256`, so no body crosses
  a dispatch prompt). Never batch, never create-all-then-parent-all, never reorder after.
- **Partial failure is reported, never rounded up.** The gate guarantees zero-mutation *aborts*, not
  atomic *execution*: a mid-batch failure stops and reports exactly which slices landed — never "all
  done" after a partial run. **Resume, don't duplicate**: on `mode: resume` report the existing slices
  and cut only the remainder from `slices.next_index`.

## 4. Handoff

Every clean run — including every refusal — ends with a single `## Handoff` block, the only bridge to
the next session. The schema, omission rules, the `Slices:` line, and the closed-set state markers are
owned by [`../_shared/handoff-format.md`](../_shared/handoff-format.md); this skill's shapes are in
[`references/handoff-renderings.md`](references/handoff-renderings.md). **Read that reference
immediately before composing the handoff — not earlier — then emit the matching shape verbatim.** The
field names (`**Issue:**`, `**Slices:**`, `**Grounding:**`, `**Next:**`, `**Why:**`), block structure,
and closed-set markers are **contract, not prose to summarize**: substitute only numbers, titles, states
and citations — never paraphrase, restructure, rename a field, drop a segment, or add a block the shape
lacks. The forward route is the `planner` (`/github-pipeline:planner <N>`), whose phases must map onto
the slices you filed; the grounding refusal routes to `/github-pipeline:setup`.
