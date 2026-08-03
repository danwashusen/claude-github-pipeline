# Epic ↔ story hierarchy — shared contract

The relation between an **epic** and its **stories** is GitHub's **native parent/sub-issue relation** — not a markdown checklist. GitHub drives the epic's sub-issue panel, its progress rollup, and a Project's built-in *Sub-issues progress* field from that relation; nothing renders or self-updates from a `- [ ] #NN` bullet.

This file is the single source of truth for how the relation is written and read. Cite it; don't restate the mechanics.

## Ownership

- **Writer — `drafter` (sole writer).** Every path that files a story under an epic passes `--parent <epic-#>` to `gh_persist.py create`, so the relation is established in the same round-trip that files the issue: the fresh epic batch, the promotion path, and epic-revise's new-stories path (`skills/drafter/playbooks/epic-split.md`). No skill establishes the relation after the fact.
- **Readers — `planner`, `resolver`, `evaluator`.** They read the epic's story set, a story's parent epic, and epic progress. None of them writes the relation, and **none of them gates on its absence** — a missing relation degrades what GitHub renders, never whether work can proceed.

Filing with `--parent` also fixes the display order for free: GitHub appends each sub-issue, so filing in dependency order gives the panel that order.

## The facts

`gh_gather.py` surfaces the relation, and every prep that gathers an issue forwards it:

| Fact | Meaning |
| --- | --- |
| `parent` | The parent issue (`{id, number, state, title, url}`), or `null` on an issue with no parent. |
| `sub_issues` | The child issues, in GitHub's own order — same node shape as `parent`. Empty on a leaf. |
| `sub_issues_summary` | GitHub's rollup: `{total, completed, percentCompleted}` — read epic progress from here rather than counting states. |
| `subissues_available` | `false` when the host doesn't serve the relation at all (with a `SUBISSUES_UNSUPPORTED` notice). Distinct from an issue that simply has no children. |

## Reading the story set — native first, checklist as fallback

An epic's story set comes from two sources, and `stories_source` reports which one answered:

1. **`sub-issues`** — `sub_issues` is non-empty and the body has no `## Stories` section. The source of truth.
2. **`checklist`** — no native children; the epic body carries a `## Stories` section of `- [ ] #NN — <title>` bullets. Parse it.
3. **`mixed`** — **both** are non-empty. Union them by issue number, native state winning where an issue appears in both. Never take one and drop the other: that silently loses stories.

The fallback is load-bearing, not vestigial: epics filed before the native relation was written carry only the checklist, and `subissues_available: false` hosts can't serve the relation at all. Neither case is repaired automatically — there is **no backfill path**, so a legacy epic reads as `checklist` for its whole life.

`mixed` is reachable without anyone doing anything wrong: epic-revise files a **new** story under a legacy epic with `--parent`, so that one story is native while its siblings remain checklist bullets. It is a real state to read correctly, not an error to report.

Consequences of the source in play:

- **`sub-issues`.** Story state *is* the progress record. There is nothing to tick: a closed story updates the rollup by itself.
- **`checklist`** (and the checklist half of `mixed`). The checkboxes are hand-maintained, so the writer that closes a story also ticks its bullet (`skills/evaluator/playbooks/story.md`), and a checkbox that disagrees with live state is an `attention` item — the mismatch class the native relation makes unrepresentable. A story on the native half of a `mixed` epic has no bullet to tick.

A fresh epic has **no** `## Stories` section (`skills/drafter/references/issue-templates.md`). Don't add one back as a second copy of the relation: it can't self-tick, and a stale copy next to a live rollup reads as a contradiction.
