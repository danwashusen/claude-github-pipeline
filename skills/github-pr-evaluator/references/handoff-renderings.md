# Handoff renderings — github-pr-evaluator

Every clean run of the evaluator ends with a single `## Handoff` block. The schema, omission rules, and closed-set state-marker vocabulary live in [`../../_shared/handoff-format.md`](../../_shared/handoff-format.md); this file holds the evaluator's outcome→rendering rubric and the worked shapes. Match the run's outcome against the rubric, then emit the matching shape, filling the snapshot from the data §15 lists.

#### Rendering rubric

| Outcome | Step 15 rendering |
|---|---|
| Standard PR merged — §12a `auto`, or §12.0 operator **Approve** | **Terminal.** Issue line, PR line with `merge: squash → main@<sha>`, Cleanup line. `review:` is `APPROVE` (auto path) or `APPROVE (operator)` (gate path). |
| Story PR merged, more sibling stories pending | **Forward → `github-issue-planner`** to plan the next story in dependency order just-in-time (it has no plan yet — the planner grounds it against the now-current epic HEAD, then the resolver implements it). Story / Epic / PR / Cleanup lines; Epic progress is e.g. `open (2 of 5 stories closed)`. `review:` is `APPROVE` or `APPROVE (operator)`. |
| Story PR merged, *last* sibling story | **Forward → `github-issue-resolver`** on the Epic, in Epic-integration mode. Story / Epic / PR / Cleanup lines; Epic progress is `open (5 of 5 stories closed)`. |
| Epic integration PR merged — §12.0 operator **Approve (merge commit / squash)** → §12b | **Terminal.** Epic line, PR line with `merge: merge → main@<sha>` (or `squash → main@<sha>`), Cleanup line. `review:` is `APPROVE (operator)` (epic is always gated). |
| Any PR, COMMENT verdict (soft-reject) — §7's `comment` action driven by a real COMMENT verdict | **Re-route → `github-issue-resolver continue #<N>`.** Issue / PR lines; PR line carries `state: draft` (§11 flipped it back), `review: COMMENT (soft-reject)`, and `merge: skipped (verdict)`. No Cleanup line. |
| Any PR, §12.0 operator **Needs Revision** / **Reject** | **Re-route → `github-issue-resolver continue #<N>`.** Same shape as the COMMENT-verdict row, but `review:` is `COMMENT (operator: needs-revision)` or `COMMENT (operator: reject)` and `merge: skipped (verdict)`. `state: draft` (§12.0 flipped it back). The `Why:` carries the operator's recorded rationale. For a **story PR**, this is **not** the forward-to-next-story route — §13 didn't run because no merge landed; the next story is deferred to a later evaluator run that actually merges this one. |
| APPROVE but `mergeStateStatus ∈ {DIRTY, BLOCKED}` → §12c skipped | **Terminal with manual command.** Issue / PR lines (PR line: `merge: skipped (DIRTY)` or `skipped (BLOCKED)`); no Cleanup. The `Next:` action quotes the recommended `gh pr merge` command verbatim and names the blocker; the `Why:` line names what the user needs to do to clear the blocker. |
| §12.0 operator-deferred merge ("Other": approved, merge manually later) | **Same shape as the DIRTY/BLOCKED case** — terminal with the recommended `gh pr merge` command; `merge: skipped (deferred)`. The `Why:` notes the operator approved but opted to merge manually. For a **story PR**, same nuance as the Needs-Revision/Reject row: §13 didn't run, so this is terminal-with-command, not forward-to-next-story. |

Self-authored PRs (the §2 self-approval pre-check that downgraded `--approve` to `--comment`) still follow the table above — the verdict is approval-equivalent; only the review action differed. On the §12.0 gate path the operator **Approve** posts as `--comment` for the same 422 reason, but the `review:` marker stays `APPROVE (operator)`.

#### Renderings

**Standard PR clean merged — terminal.**

```
## Handoff

**Issue:** #142 — Add CSV export · closed · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · merged · base main · review: APPROVE · health: ✅ at abc1234 · merge: squash → main@def5678
**Cleanup:** worktree removed; teardown ran; scratch dir purged

**Next:** (terminal — no follow-up skill)

**Why:** the PR satisfied every dimension cleanly and merged into main. The issue is closed by GitHub's auto-close; no follow-up skill is required for this issue.
```

The `review: APPROVE` above is the `auto`-policy (§12a) shape. Under the default `ask` policy the operator approved at the §12.0 gate, so the same terminal shape carries `review: APPROVE (operator)` and the `Why:` may note the operator's sign-off. The merge / Cleanup / terminal lines are identical either way.

**Story PR merged — more stories pending.** The Epic stays open; the next story is planned just-in-time before it's implemented. Read the Epic body's `## Stories` list (re-fetched in §13) to pick the next-in-sequence; the epic plan's `## Story breakdown` order is the source of truth.

```
## Handoff

**Story:** #151 — Add export service · closed · story · plan: ✓
**Epic:** #150 — Chat & session UX polish · open (1 of 5 stories closed)
**PR:** #287 — Add export service (#151) · merged · base epic/150-chat-ux · review: APPROVE · health: ✅ at abc1234 · merge: squash → epic/150-chat-ux@def5678
**Cleanup:** worktree removed; epic checkbox ticked; delivery log updated; story issue closed

**Next:** plan the next story in dependency order, just-in-time, in a fresh session.

    /github-pipeline:github-issue-planner #152

**Why:** story #151 merged into the epic branch; the Epic checkbox is ticked and the epic delivery log now records what #151 delivered. Story #152 (next in `## Story breakdown` order) has no plan yet — the planner authors it just-in-time against the now-current epic HEAD (which includes #151's merge) and checks it against the epic plan's `## Story contracts` and the delivery log, then the resolver implements it.
```

**Story PR merged — last sibling, Epic integration ready.** Every child story is now closed. The next step is the resolver in Epic-integration mode (it opens the integration PR against `main`).

```
## Handoff

**Story:** #155 — Final polish · closed · story · plan: ✓
**Epic:** #150 — Chat & session UX polish · open (5 of 5 stories closed)
**PR:** #295 — Final polish (#155) · merged · base epic/150-chat-ux · review: APPROVE · health: ✅ at fed4321 · merge: squash → epic/150-chat-ux@9876abc
**Cleanup:** worktree removed; epic checkbox ticked; delivery log updated; story issue closed

**Next:** open the Epic integration PR in a fresh session.

    /github-pipeline:github-issue-resolver #150

**Why:** every child story is closed and on `epic/150-chat-ux`. The resolver in Epic mode opens the integration PR against `main`; pr-evaluator will then escalate to the full canonical test suite (per the `pr_type: epic-integration` rule) before recommending the merge mode.
```

**Epic integration PR clean merged — terminal.**

```
## Handoff

**Epic:** #150 — Chat & session UX polish · closed · epic · plan: ✓
**PR:** #300 — Chat & session UX polish (epic #150) · merged · base main · review: APPROVE · health: ✅ at 1357bdf · merge: merge → main@2468ace
**Cleanup:** worktree removed; teardown ran; scratch dir purged

**Next:** (terminal — no follow-up skill)

**Why:** the integration PR landed every child story's work on `main` in one merge commit (§12b chose Merge commit, preserving the story squash commits in `main`'s history). The Epic is closed by `Fixes #150`; the pipeline ends here.
```

**Soft-reject — re-route to resolver.** §7 produced a `comment` action driven by a real COMMENT verdict (not a §2 self-approval downgrade); §11's draft-flip ran, so the PR is now back in draft. The review names the dimension gaps; the resolver continues on the existing branch (now back in draft) without re-deadlocking on the §3 draft-PR guard the next time it hands back.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · draft · base main · review: COMMENT (soft-reject) · health: ✅ at abc1234 · merge: skipped (verdict)

**Next:** address the review's gaps in a fresh session — the resolver continues on the existing branch (now in draft).

    /github-pipeline:github-issue-resolver continue #287

**Why:** the review cites <N> dimension gaps (acceptance-criterion #3 unaddressed; one plan-locked test missing — see the review comment for the full evidence). §11 flipped the PR back to draft so the resolver's §5 existing-PR check picks it up as in-progress work, not as drift; the resolver's §10 review loop will address each finding, re-push, and (on the §11 *last planned phase shipped* row for multi-phase issues, or directly for single-phase) re-flip to ready before its next forward handoff.
```

**APPROVE but merge skipped — terminal with manual command.** The PR earned approval but isn't mergeable yet (DIRTY or BLOCKED), or the user opted to merge later from §12b. Print the recommended `gh pr merge` command verbatim in the fenced block; the user runs it themselves when the blocker clears.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · open · base main · review: APPROVE · health: ✅ at abc1234 · merge: skipped (DIRTY)

**Next:** resolve the conflict, then run the merge yourself:

    gh pr merge 287 --repo owner/repo --squash --subject "feat: add CSV export (#287)" --body-file /tmp/squash-body-287.md --delete-branch

**Why:** the PR is approved on its merits but `mergeStateStatus == DIRTY` — there's a conflict with the base branch. Resolve the conflict (rebase or merge `main` into the PR branch), confirm the conflict is gone (`gh pr view 287 --json mergeStateStatus`), then run the command above. No follow-up skill — once the merge lands, GitHub auto-closes the issue.
```

For the §12.0 operator-deferred path ("Other": approved but merge manually later), the same shape applies with `merge: skipped (deferred)` and a Why line noting the operator's choice to merge manually.

**Operator soft-reject (Needs Revision / Reject) — re-route to resolver.** The §12.0 gate returned **Needs Revision** or **Reject**; §12.0 posted the review as `--comment` with an `operator action <ISO-date>` header carrying the operator's rationale, then flipped the PR back to draft. The shape matches the COMMENT-verdict soft-reject, but the `review:` marker names the operator decision and the `Why:` carries their reason. (For a story PR, no merge landed, so this re-routes to the resolver on the *same* story — not forward to the next one.)

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓
**PR:** #287 — Add CSV export (#142) · draft · base main · review: COMMENT (operator: needs-revision) · health: ✅ at abc1234 · merge: skipped (verdict)

**Next:** address the operator's requested changes in a fresh session — the resolver continues on the existing branch (now in draft).

    /github-pipeline:github-issue-resolver continue #287

**Why:** the automated evaluation passed, but the operator requested revision at the merge gate (recorded on the PR, <ISO-date>): "export should stream rather than buffer the whole file in memory for large datasets." §12.0 flipped the PR back to draft so the resolver's §5 existing-PR check picks it up as in-progress work; the resolver's §10 review loop addresses the note, re-pushes, and re-flips to ready before the next forward handoff.
```
