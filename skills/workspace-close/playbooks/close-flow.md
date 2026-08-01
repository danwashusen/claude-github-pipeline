# workspace-close — the one flow

Release the workspace and report faithfully. Linear; the only branch points are decision cards.

## 1. Close

Run the prep call from the router §1 (it is the action — branch resolution, teardown hooks,
gated removal, one envelope).

## 2. Decision cards (render as one `AskUserQuestion` each)

- **Dirty / unpushed** (`AMBIGUOUS`): options are "Discard and remove", "Keep — I'll push or
  commit first", "Abort". On *discard*, the operator has explicitly accepted the loss — re-run
  the prep only after they confirm; on *keep*/*abort*, stop and print the re-run command in the
  summary. The merged-PR variant ("PR #N merged, but the worktree has local commits past the
  merged head") offers salvage-onto-a-new-branch as the safe path — those commits are NOT in the
  merged PR.
- **`cwd_inside_target`** (`WORKSPACE_MISMATCH`): relay the remedy verbatim — re-run from the
  project root; this session cannot remove the checkout it is standing in.
- **Branch resolution** (`AMBIGUOUS` on multiple linked branches / nothing resolvable): re-run
  with the explicit branch name the operator picks.

## 3. Summary

Render, in order:

1. **Outcome** — removed (path gone) / retained (and the exact reason: which gate, which hazard)
   / `not_found` (nothing to do — say so plainly; the tool is safe to re-run).
2. **Teardown** — commands run and any best-effort failures with their `output_tail` (a failed
   teardown never blocks removal, but the operator must see what leaked).
3. **Branch resolution** — `input` → `branch` (`via`), so an issue-number invocation shows its
   work.
4. **Leftovers** — the remote branch (if any) is untouched: deletion follows the repo's
   `delete_branch_on_merge` policy or a manual choice, never this tool.
