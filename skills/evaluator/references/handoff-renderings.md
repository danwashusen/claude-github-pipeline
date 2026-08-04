# Handoff renderings — evaluator

Every clean run of the evaluator ends with a single `## Handoff` block. The schema, omission rules, and
closed-set state-marker vocabulary are owned by [`../../_shared/handoff-format.md`](../../_shared/handoff-format.md);
this file holds the evaluator's outcome→rendering rubric and the worked shapes. Match the run's outcome
against the rubric, then emit the matching shape, filling the snapshot from the prep facts plus this
run's results (the review verdict, the cache comment's SHA, the merge command's outcome).
Next-command skills are namespaced `/github-pipeline:<name>` (`planner`, `resolver`,
`workspace-open`, `workspace-close`). **`Workspace:` lines** (v3's "start the next session
here" carrier) substitute `<workspace-path>` from `facts.workspace.path`; the two story-merge
forward routes instead name the **parent epic's** worktree (`.worktrees/epic/<N>-<slug>` under
the project root — the next session grounds/integrates on the epic branch; tell the operator to
open it with `/github-pipeline:workspace-open <epic>` if absent). The worked standard-terminal
block is the v3 frozen rendering (`docs/specs/examples/handoff-evaluator-v3.md`, superseding the
S1 capture, which stays in `docs/specs/` as the v2 historical record).

#### Rendering rubric

| Outcome | Rendering |
|---|---|
| Standard PR merged — `auto` policy, or operator **Approve** at the gate | **Terminal.** Issue line, PR line with `merge: squash → main@<sha>`, Cleanup line (`scratch dir purged; worktree retained — release with workspace-close`); the fence carries `/github-pipeline:workspace-close <branch>`. `review:` is `APPROVE` (auto path) or `APPROVE (operator)` (gate path). |
| Story PR merged, more sibling stories pending | **Forward → `/github-pipeline:planner`** to plan the next story in dependency order just-in-time (it has no plan yet — the planner grounds it against the now-current epic HEAD, then the resolver implements it). Story / Epic / PR / Cleanup lines; Epic progress e.g. `open (2 of 5 stories closed)`. `review:` is `APPROVE` or `APPROVE (operator)`. |
| Story PR merged, *last* sibling story | **Forward → `/github-pipeline:resolver`** on the Epic, in Epic-integration mode. Story / Epic / PR / Cleanup lines; Epic progress `open (5 of 5 stories closed)`. |
| Epic integration PR merged — operator **Approve (merge commit / squash)** | **Terminal.** Epic line, PR line with `merge: merge → main@<sha>` (or `squash → main@<sha>`), Cleanup line; the fence carries `/github-pipeline:workspace-close <branch>`. `review:` is `APPROVE (operator)` (epic is always gated). |
| Any PR, COMMENT verdict (soft-reject) — a real COMMENT verdict drove the `comment` action | **Re-route → `/github-pipeline:resolver continue #<N>`.** Issue / PR lines; PR line carries `state: draft` (S7-post flipped it back), `review: COMMENT (soft-reject)`, `merge: skipped (verdict)`. No Cleanup line. |
| Any PR, operator **Needs Revision** / **Reject** at the gate | **Re-route → `/github-pipeline:resolver continue #<N>`.** Same shape as the COMMENT-verdict row, but `review:` is `COMMENT (operator: needs-revision)` or `COMMENT (operator: reject)` and `merge: skipped (verdict)`. `state: draft` (the gate flipped it back). The `Why:` carries the operator's recorded rationale. For a **story PR**, this is **not** the forward-to-next-story route — no merge landed, so the story-route actions didn't run; the next story is deferred to a later run that actually merges this one. |
| APPROVE but `mergeStateStatus ∈ {DIRTY, BLOCKED}` → skipped | **Terminal with manual command.** Issue / PR lines (PR line: `merge: skipped (DIRTY)` or `skipped (BLOCKED)`); no Cleanup. `Next:` quotes the recommended `gh pr merge` command verbatim and names the blocker; `Why:` names what the user does to clear it. |
| Operator-deferred merge ("Other": approved, merge manually later) | **Same shape as the DIRTY/BLOCKED case** — terminal with the recommended `gh pr merge` command; `merge: skipped (deferred)`. `Why:` notes the operator approved but opted to merge manually. For a **story PR**, same nuance as the Needs-Revision/Reject row: the story-route actions didn't run, so this is terminal-with-command, not forward-to-next-story. |

Self-authored PRs (the self-approval pre-check that downgraded `--approve` to `--comment`) still follow
the table above — the verdict is approval-equivalent; only the review action differed. On the gate path
the operator **Approve** posts as `--comment` for the same 422 reason, but the `review:` marker stays
`APPROVE (operator)`.

#### Renderings

**Standard PR clean merged — terminal.**

```
## Handoff

**Issue:** #142 — Add CSV export · closed · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · merged · base main · review: APPROVE · health: ✅ at abc1234 · merge: squash → main@def5678
**Cleanup:** scratch dir purged; worktree retained — release with workspace-close

**Next:** pipeline terminal — release the workspace:

    /github-pipeline:workspace-close 142-add-csv-export

**Why:** the PR satisfied every dimension cleanly and merged into main. The issue is closed by GitHub's auto-close; no follow-up skill is required for this issue.
```

The `review: APPROVE` above is the `auto`-policy shape. Under the default `ask` policy the operator
approved at the gate, so the same terminal shape carries `review: APPROVE (operator)` and the `Why:`
may note the operator's sign-off. The merge / Cleanup / terminal lines are identical either way.

**Story PR merged — more stories pending.** The Epic stays open; the next story is planned just-in-time
before it's implemented. Read the Epic's story set (`facts.epic.stories` — its sub-issues, or a legacy
epic's re-fetched `## Stories` list) to pick the next-in-sequence; the epic plan's `## Story breakdown`
order is the source of truth. The `K of M stories closed` count comes from
`facts.epic.sub_issues_summary` (`completed` of `total`) where the native relation is present.

```
## Handoff

**Story:** #151 — Add export service · closed · story · plan: ✓
**Epic:** #150 — Chat & session UX polish · open (1 of 5 stories closed)
**PR:** #287 — Add export service (#151) · merged · base epic/150-chat-ux · review: APPROVE · health: ✅ at abc1234 · merge: squash → epic/150-chat-ux@def5678
**Cleanup:** scratch dir purged; worktree retained — release with workspace-close; epic checkbox ticked; delivery log updated; story issue closed
**Workspace:** <project-root>/.worktrees/epic/150-chat-ux — the parent epic's worktree; start the planner session there (open it with /github-pipeline:workspace-open 150 if absent)

**Next:** plan the next story in dependency order, just-in-time, in a fresh session.

    /github-pipeline:planner #152

**Why:** story #151 merged into the epic branch; the Epic checkbox is ticked and the epic delivery log now records what #151 delivered. Story #152 (next in `## Story breakdown` order) has no plan yet — the planner authors it just-in-time against the now-current epic HEAD (which includes #151's merge) and checks it against the epic plan's `## Story contracts` and the delivery log, then the resolver implements it.
```

**Story PR merged — last sibling, Epic integration ready.** Every child story is now closed. The next
step is the resolver in Epic-integration mode (it opens the integration PR against `main`).

```
## Handoff

**Story:** #155 — Final polish · closed · story · plan: ✓
**Epic:** #150 — Chat & session UX polish · open (5 of 5 stories closed)
**PR:** #295 — Final polish (#155) · merged · base epic/150-chat-ux · review: APPROVE · health: ✅ at fed4321 · merge: squash → epic/150-chat-ux@9876abc
**Cleanup:** scratch dir purged; worktree retained — release with workspace-close; epic checkbox ticked; delivery log updated; story issue closed
**Workspace:** <project-root>/.worktrees/epic/150-chat-ux — the epic's worktree; start the resolver session there (open it with /github-pipeline:workspace-open 150 if absent)

**Next:** open the Epic integration PR in a fresh session.

    /github-pipeline:resolver #150

**Why:** every child story is closed and on `epic/150-chat-ux`. The resolver in Epic mode opens the integration PR against `main`; the evaluator will then escalate to the full canonical test suite (per the `pr_type: epic-integration` rule) before recommending the merge mode.
```

**Epic integration PR clean merged — terminal.**

```
## Handoff

**Epic:** #150 — Chat & session UX polish · closed · epic · plan: ✓
**PR:** #300 — Chat & session UX polish (epic #150) · merged · base main · review: APPROVE · health: ✅ at 1357bdf · merge: merge → main@2468ace
**Cleanup:** scratch dir purged; worktree retained — release with workspace-close

**Next:** pipeline terminal — release the workspace:

    /github-pipeline:workspace-close epic/150-chat-ux

**Why:** the integration PR landed every child story's work on `main` in one merge commit (the gate chose Merge commit, preserving the story squash commits in `main`'s history). The Epic is closed by `Fixes #150`; the pipeline ends here.
```

**Soft-reject — re-route to resolver.** A `comment` action driven by a real COMMENT verdict (not a
self-approval downgrade); the draft-flip ran, so the PR is now back in draft. The review names the
dimension gaps; the resolver continues on the existing branch (now back in draft) without
re-deadlocking on the draft-PR guard the next time it hands back.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · draft · base main · review: COMMENT (soft-reject) · health: ✅ at abc1234 · merge: skipped (verdict)
**Workspace:** <workspace-path> — start the next session here

**Next:** address the review's gaps in a fresh session — the resolver continues on the existing branch (now in draft).

    /github-pipeline:resolver continue #287

**Why:** the review cites <N> dimension gaps (acceptance-criterion #3 unaddressed; one plan-locked test missing — see the review comment for the full evidence). The draft-flip put the PR back to draft so the resolver's existing-PR check picks it up as in-progress work, not as drift; the resolver's review loop will address each finding, re-push, and re-flip to ready before its next forward handoff.
```

**APPROVE but merge skipped — terminal with manual command.** The PR earned approval but isn't
mergeable yet (DIRTY or BLOCKED), or the operator opted to merge later. Print the recommended `gh pr
merge` command verbatim in the fenced block; the user runs it themselves when the blocker clears.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · open · base main · review: APPROVE · health: ✅ at abc1234 · merge: skipped (DIRTY)

**Next:** resolve the conflict, then run the merge yourself:

    gh pr merge 287 --repo owner/repo --squash --subject "feat: add CSV export (#287)" --body-file /tmp/gh-evaluator-287/squash-body.md --delete-branch

**Why:** the PR is approved on its merits but `mergeStateStatus == DIRTY` — there's a conflict with the base branch. Resolve the conflict (rebase or merge `main` into the PR branch), confirm it's gone (`gh pr view 287 --json mergeStateStatus`), then run the command above. No follow-up skill — once the merge lands, GitHub auto-closes the issue.
```

For the operator-deferred path ("Other": approved but merge manually later), the same shape applies with
`merge: skipped (deferred)` and a `Why:` noting the operator's choice to merge manually.

**Operator soft-reject (Needs Revision / Reject) — re-route to resolver.** The gate returned **Needs
Revision** or **Reject**; the gate posted the review as `--comment` with an `operator action <ISO-date>`
header carrying the operator's rationale, then flipped the PR back to draft. The shape matches the
COMMENT-verdict soft-reject, but the `review:` marker names the operator decision and the `Why:` carries
their reason. (For a story PR, no merge landed, so this re-routes to the resolver on the *same* story —
not forward to the next one.)

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · draft · base main · review: COMMENT (operator: needs-revision) · health: ✅ at abc1234 · merge: skipped (verdict)
**Workspace:** <workspace-path> — start the next session here

**Next:** address the operator's requested changes in a fresh session — the resolver continues on the existing branch (now in draft).

    /github-pipeline:resolver continue #287

**Why:** the automated evaluation passed, but the operator requested revision at the merge gate (recorded on the PR, <ISO-date>): "export should stream rather than buffer the whole file in memory for large datasets." The gate flipped the PR back to draft so the resolver's existing-PR check picks it up as in-progress work; the resolver's review loop addresses the note, re-pushes, and re-flips to ready before the next forward handoff.
```
