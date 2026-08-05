# Epic ↔ story ↔ slice hierarchy — shared contract

The parent/child relation at **every** level of this hierarchy is GitHub's **native parent/sub-issue relation** — not a markdown checklist. GitHub drives the parent's sub-issue panel, its progress rollup, and a Project's built-in *Sub-issues progress* field from that relation; nothing renders or self-updates from a `- [ ] #NN` bullet.

This file is the single source of truth for how the relation is written and read. Cite it; don't restate the mechanics.

## Three levels, two edges

```
epic ──parent-of──▶ story ──parent-of──▶ deliverable slice
```

A **deliverable slice** is the smallest increment of actor- or business-visible behaviour that could be demonstrated on its own — vertical through whatever layers it needs. "Build the tables" and "add the endpoints" are *tasks inside* a slice, never slices.

A slice differs from a story in exactly **one** parameter, and that parameter is set by one fact — *does the child get its own branch and PR?*

| Child | Own branch + PR? | Independence bar |
| --- | --- | --- |
| story (under an epic) | yes | independently **shippable** |
| slice (under a story or a standalone issue) | no | independently **demonstrable** |

A slice is a **phase marker**: the resolver ships it as a phase on the *parent's* branch and closes it as that phase lands. Say "deliverable slice" in full — a bare "slice" means an ownership boundary in requirements-style prose, which is a different concept entirely.

**Identification is by construction, not by label.** The hierarchy above has exactly three levels, so a **non-epic** issue's sub-issues are its slices, and an **epic's** sub-issues are its stories. No reader needs a label or a per-child fetch to tell them apart. Two constraints keep that inference sound, and both are the writers' responsibility:

- Slices are filed only under a **non-epic** target.
- **A slice is never itself sliced.** It has no branch of its own, so a sub-slice could not ship as anything; and a fourth level would make the inference ambiguous.

## Ownership

- **Writer, epic→story — `slicer` (sole writer).** Every path that files a story under an epic passes `--parent <epic-#>` to `gh_persist.py create`, so the relation is established in the same round-trip that files the issue: the fresh epic cut, the promotion path, and a resume's new-stories path (`skills/slicer/playbooks/cut.md`). The **one** after-the-fact path is adoption: `gh_persist.py add-parent` parents an issue that is already filed, so an epic can be drawn around stories authored upstream. It is slicer-only and gated like every other write in that flow — nothing else establishes either relation after the fact. (Before #16 this edge was the drafter's, written only at filing time; the drafter now drafts and revises one issue's body and decomposes nothing.)
- **Writer, story→slice — `slicer` (sole writer).** Same mechanism, same round-trip: `gh_persist.py create --parent <parent-#>`, one slice at a time in the operator-approved order. Both edges have one writer, and it is the same one: decomposition is one operation at two altitudes, differing only in the bar each child clears.
- **Readers — `planner`, `resolver`, `evaluator`.** They read the epic's story set, a story's parent epic, epic progress, and the slice set of a non-epic target. None of them writes either relation, and **none of them gates on its absence** — a missing relation degrades what GitHub renders, never whether work can proceed.

Filing with `--parent` also fixes the display order for free: GitHub appends each sub-issue, so filing in dependency order gives the panel that order. For slices this is load-bearing rather than convenient — creation order **is** delivery order, so it is fixed at approval time, never repaired afterwards.

## Closing a slice — the rollup is the point

Slices exist to make delivery progress legible in GitHub: the parent's own rollup and a Project's *Sub-issues progress* field track it, with nothing finer-grained added to a board. That purpose decides the closing contract:

- **The resolver closes a slice when its last serving phase ships** — the phase's `sub-issue:` key names it (`skills/planner/references/plan-schema.md`), and the map is N:1, so a slice closes on the last of the phases serving it, not the first.
- **Per shipped phase, not at merge.** Closing every slice when the parent PR merges would move the rollup `0/N → N/N` in one step, and a progress indicator that shows no progress until it shows completion is not a progress indicator.
- **"Closed" means demonstrable, not merged.** A slice's bar is *demonstrable*, and a phase shipped to the parent's branch is demonstrable. The slice does not claim its code is on the default branch — the parent's own state claims that. This is why closing before the parent merges is coherent rather than a lie.
- **The evaluator is a merge-time backstop only**, closing slices left open by an interrupted run (`skills/evaluator/playbooks/story.md`, `standard.md`). Both closes are idempotent, so the two writers never contend.

A slice set that never closes is worse than no slices at all: it leaves a permanent `0/N` rollup, a progress indicator reading "no progress" forever. That is the same defect the `## Stories` checklist was retired for, one level down.

**Reopen is unowned.** If a parent PR is abandoned or hard-rejected after its slices closed, the rollup lies in the other direction. `gh_persist.py reopen` exists, but no skill currently owns firing it; the natural analogue is the evaluator's sticky-veto un-tick machinery. Recorded here as a known gap rather than left to be discovered.

## The facts

`gh_gather.py` surfaces the relation, and every prep that gathers an issue forwards it:

| Fact | Meaning |
| --- | --- |
| `parent` | The parent issue (`{id, number, state, title, url}`), or `null` on an issue with no parent. |
| `sub_issues` | The child issues, in GitHub's own order — same node shape as `parent`. Empty on a leaf. Stories when the target is an epic; slices when it isn't. |
| `sub_issues_summary` | GitHub's rollup: `{total, completed, percentCompleted}` — read progress from here rather than counting states. |
| `subissues_available` | `false` when the host doesn't serve the relation at all (with a `SUBISSUES_UNSUPPORTED` notice). Distinct from an issue that simply has no children. |

The node shape carries **no labels**, which is why identification is by construction (above) rather than by classifying each child.

## Reading the story set — native first, checklist as fallback

An epic's story set comes from two sources, and `stories_source` reports which one answered:

1. **`sub-issues`** — `sub_issues` is non-empty and the body has no `## Stories` section. The source of truth.
2. **`checklist`** — no native children; the epic body carries a `## Stories` section of `- [ ] #NN — <title>` bullets. Parse it.
3. **`mixed`** — **both** are non-empty. Union them by issue number, native state winning where an issue appears in both. Never take one and drop the other: that silently loses stories.

The fallback is load-bearing, not vestigial: epics filed before the native relation was written carry only the checklist, and `subissues_available: false` hosts can't serve the relation at all. Neither case is repaired automatically — there is **no backfill path**, so a legacy epic reads as `checklist` for its whole life.

`mixed` is reachable without anyone doing anything wrong: a slicer resume files a **new** story under a legacy epic with `--parent`, so that one story is native while its siblings remain checklist bullets. It is a real state to read correctly, not an error to report — the reader unions both halves, and the slicer keeps the checklist reconciled (behind its write gate) because for those entries it is still the only record.

Consequences of the source in play:

- **`sub-issues`.** Story state *is* the progress record. There is nothing to tick: a closed story updates the rollup by itself.
- **`checklist`** (and the checklist half of `mixed`). The checkboxes are hand-maintained, so the writer that closes a story also ticks its bullet (`skills/evaluator/playbooks/story.md`), and a checkbox that disagrees with live state is an `attention` item — the mismatch class the native relation makes unrepresentable. A story on the native half of a `mixed` epic has no bullet to tick.

A fresh epic has **no** `## Stories` section (`skills/drafter/references/issue-templates.md`). Don't add one back as a second copy of the relation: it can't self-tick, and a stale copy next to a live rollup reads as a contradiction.

**The slice edge has no checklist fallback and never will.** The two-tier read above exists only because epics predate the native relation; slices do not, so `sub_issues` is the whole story at that level and a `stories_source`-style flag has no slice analogue. For the same reason, no `## Slices` section is ever written to a parent body — the slicer never edits the parent at all, and slice detail lives only in slice bodies.
