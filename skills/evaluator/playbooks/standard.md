# Standard PR

Route for `vector.type == standard` (base `main`, head not `epic/<N>-<slug>`). A single-issue PR that
lands directly on `main`.

**Run the spine first.** Read [`evaluate-spine.md`](evaluate-spine.md) and execute it end to end
(identify → health gate → five-dimension evaluation → verdict → merge strategy → merge-approval gate →
merge). Everything below runs **only after S7-merge actually merged**; on any no-merge exit, skip to
the handoff.

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

Tear down and remove the work workspace, then purge the scratch dir:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/workspace.py remove --work <facts.workspace.branch> --root <root>
```
`remove --work` runs the consuming repo's `<!-- worktree-teardown -->` hooks (best-effort — a leaked
resource is recoverable; a stuck worktree blocks every future run against the branch) **before** the
`git worktree remove`, because the teardown commands live inside the worktree. Then
`rm -rf "<facts.scratch>"`.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md) and emit the
**Standard PR clean merged — terminal** shape: Issue line, PR line (`merge: squash → main@<sha>`),
Cleanup line, `Next: (terminal — no follow-up skill)`, and a `Why:`. `review:` is `APPROVE` (auto
policy) or `APPROVE (operator)` (gate path). The issue closes via GitHub's auto-close on merge into
`main` — the pipeline ends here.

On a **no-merge** exit, emit the matching rubric shape instead — **soft-reject → re-route** to
`/github-pipeline:resolver continue #<PR>` (COMMENT verdict or operator Needs-Revision / Reject; PR is
back in draft, `merge: skipped (verdict)`, no Cleanup line), or **APPROVE-but-skipped** (DIRTY/BLOCKED
or operator-deferred; `merge: skipped (DIRTY|BLOCKED|deferred)`, the `Next:` quotes the manual `gh pr
merge` command).
