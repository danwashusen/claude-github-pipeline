# Standard PR

Route for `vector.type == standard` (base `main`, head not `epic/<N>-<slug>`). A single-issue PR that
lands directly on `main`.

**Run the spine first.** Read [`evaluate-spine.md`](evaluate-spine.md) and execute it end to end
(identify → health gate → five-dimension evaluation → verdict → merge strategy → merge-approval gate →
merge). Everything below runs **only after S7-merge actually merged**; on any no-merge exit, skip to
the handoff.

## After the merge — close any remaining deliverable slices

The issue itself closes via GitHub's auto-close on merge into `main`, but **its sub-issues do not**. By
construction a non-epic issue's sub-issues are its deliverable slices
([`../../_shared/epic-story-hierarchy.md`](../../_shared/epic-story-hierarchy.md)), and the resolver
normally closes each as its last serving phase ships. This is the **backstop only**, for a run
interrupted before that: a slice left open behind a merged parent leaves the rollup permanently short,
the one thing the slices exist to get right. For each still-open sub-issue of the closing issue (already
closed is a safe no-op):

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py close <owner/repo> <slice> --reason completed
```

Don't tick the slices' `## Acceptance criteria` here — the resolver owns that projection, and inventing
it at merge time would create a second writer for one fact.

## After the merge — residual follow-ups

File the **residual non-blocking** work this run surfaced but hasn't filed: a finding from your own
review, or a `## Follow-ups` *Procedural notes* item, that warrants an issue. **De-duplicate** against
issues already linked in the PR body's `## Follow-ups` *Filed* entries — never re-file those. (In-scope
grounding violations never reach here — they soft-reject pre-merge and take the no-merge exit.)

File each via the shared protocol in [`../../_shared/follow-up-filing.md`](../../_shared/follow-up-filing.md)
— one `general-purpose` sub-agent per item, type from `bug | incomplete-feature | deferred-test |
revise-existing`, parent reference = this PR + the issue. After filing, post the URLs as a brief PR
comment so they're durable (stage the list to `<facts.scratch>/followups.md`):
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py comment <owner/repo> pr <PR> "<facts.scratch>/followups.md"
```
If nothing is residual, say nothing.

## Cleanup (merge ran)

Purge the scratch dir only: `rm -rf "<facts.scratch>"`. The worktree is **deliberately retained** —
this session is running inside it and must never remove its own checkout; the handoff hands the
operator `/github-pipeline:workspace-close <facts.workspace.branch>`, which runs the repo's
`<!-- worktree-teardown -->` hooks and the gated removal from outside.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md) and emit the
**Standard PR clean merged — terminal** shape: Issue line, PR line (`merge: squash → main@<sha>`),
Cleanup line (`scratch dir purged; worktree retained — release with workspace-close`), a
`Next:` of `pipeline terminal — release the workspace:` whose fence carries
`/github-pipeline:workspace-close <facts.workspace.branch>`, and a `Why:`. `review:` is `APPROVE` (auto
policy) or `APPROVE (operator)` (gate path). The issue closes via GitHub's auto-close on merge into
`main` — the pipeline ends here.

On a **no-merge** exit, emit the matching rubric shape instead — **soft-reject → re-route** to
`/github-pipeline:resolver continue #<PR>` (COMMENT verdict or operator Needs-Revision / Reject; PR is
back in draft, `merge: skipped (verdict)`, no Cleanup line), or **APPROVE-but-skipped** (DIRTY/BLOCKED
or operator-deferred; `merge: skipped (DIRTY|BLOCKED|deferred)`, the `Next:` quotes the manual `gh pr
merge` command).
