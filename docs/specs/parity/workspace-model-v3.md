# Live verification — the v3 workspace model (operator-owned worktrees)

> Status: **TODO — fill each result after the live run.** This file is the live-verification
> record for the v3.0.0 workspace-model inversion (workspace-open / workspace-close; stage preps
> assert the ambient checkout; gate config read at the origin/main pin). It is a NEW record —
> `docs/specs/**` is the frozen historical archive, so the v2 per-skill parity files and
> `conveyor.md` are **not** edited; this file supersedes the workspace-behavior D-bindings they
> carried: `setup.md` D3/D4 ("root stays clean throughout" / "landing = `workspace.py ensure
> --work` + `create-pr`" — the landing leg below re-verifies both under v3), `resolver.md` and
> `evaluator.md`'s prep-ensured-worktree bindings, and `conveyor.md`'s workspace lifecycle
> observations (the S20 finding "workspace.py remove can't finish the evaluator's teardown" is
> closed by design: the evaluator no longer removes, and workspace-close runs from outside).

Sandbox: the repo recorded in `tests/SANDBOX.md`; harness: the tmux interactive recipe (the
parity runs' standing gotcha — `AskUserQuestion` needs an interactive session, headless `claude
-p` cannot render cards).

## Scenario 1 — the v3 conveyor

Seed a standard issue with a plan. Then:

1. `/github-pipeline:workspace-open <N>` — assert: the linked branch appears on the issue
   (GitHub "Development" panel), the worktree exists at the printed path, the sandbox's
   worktree-setup hook ran, and the summary routes next-step per plan presence.
2. Resolver session **started inside the worktree** — assert: prep `ok` with
   `workspace.source: ambient`, hooks re-ran (second hook-log entry), `config.sha` equals
   `origin/main`'s tip even with a dirty main checkout, PR opened with the right base/head.
3. Evaluator session inside the same worktree — assert: prep asserts at exactly the PR head OID;
   merge runs; the worktree is **still present** afterward; the handoff carries
   `Cleanup: scratch dir purged; worktree retained — release with workspace-close` and the
   terminal fence `/github-pipeline:workspace-close <branch>`.
4. `/github-pipeline:workspace-close <branch>` from the project root — assert: teardown hook ran,
   worktree removed, and the merged-PR path did NOT trip the generic push-first card
   (squash-merge + delete-branch-on-merge is the sandbox's config — the review-M2 leg).

- [ ] Result:

## Scenario 2 — negative legs

- (a) Start a resolver session at the project root (no worktree) → one `WORKSPACE_MISMATCH`
  card whose options name workspace-open; nothing built.
- (b) Start it in a worktree on the wrong branch → `branch_mismatch` card.
- (c) `workspace-close` on a worktree with uncommitted edits → gated (`AMBIGUOUS`), worktree
  retained; answering "keep" prints the re-run command.
- (d) `gh issue develop --list` on an issue with zero linked branches — record the exit code and
  output shape observed live (unverifiable offline; the ladder treats any non-auth non-zero as
  `ISSUE_LINK_UNSUPPORTED` and degrades — confirm no spurious notice on a healthy zero-linked
  issue, or record that the degradation fires and is benign).

- [ ] Result:

## Scenario 3 — the surviving v2 gates

One `setup` landing run (approve leg) — assert the `ROOT_*` freshness gates still fire on the
landing tools' staging path (dirty the root first, expect the `ROOT_DIRTY` card), and the landing
still stages in a tool-created workspace exactly as the frozen S17 record describes.

- [ ] Result:

## Go/no-go

- [ ] All three scenarios recorded; divergences adjudicated or fixed.
