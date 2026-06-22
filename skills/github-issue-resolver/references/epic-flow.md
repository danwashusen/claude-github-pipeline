# Epic-flow runbooks (resolver)

Epic-only procedures the `github-issue-resolver` **"If the issue is an Epic"** flow invokes — the full-canonical-suite runbook, the drift-rectification execution paths, and the bootstrap + legacy-recovery sequences. They are extracted here so they don't consume the default Read budget on the hotter story / single-issue paths; the epic flow force-`Read`s this file before running any rectification or bootstrap step (see SKILL.md "Check the integration branch").

References back to SKILL.md primitives are written as "SKILL.md §PN" / "SKILL.md §N". The assess-step shell variables this file uses — `$FORK_POINT`, `$COMMITS_BEHIND`, `$OPEN_STORY_PRS`, `$EPIC_FILES`, `$OVERLAP` — are set by SKILL.md's "Assess before rectifying" step, which runs inline before the reader reaches the rectification runbooks here.

## Running the full canonical suite (epic baseline / bootstrap / post-rectification)

This subsection applies **only** to the epic-baseline, bootstrap, and post-rectification flows in SKILL.md "If the issue is an Epic" — the places that legitimately run the project's *full* canonical suite (every unit + UI test) in a worktree. It does **not** loosen the §8/§10.6 story gates, which stay targeted-only (see "Don't run the full unit + UI suite at the §8/§10.6 story gates" in SKILL.md Common pitfalls). It exists because a full-suite run is a 15–30 minute, cold-build-bearing operation, and three foot-guns turned one such run into a multi-hour hang in the past.

**1. Which command — never improvise it, and never cold-rebuild on every attempt.** Read the project's `issue-resolver-canonical-suite` block (per SKILL.md §P3.1) and use its labelled commands:

- **First attempt** → `full-suite` (one cold build + every suite).
- **Any re-run** (the first run's result was lost or partial, or you're re-running specific failures) → `build-once` **once**, then `retry-without-rebuild` (append `-only-testing <Suite>/<test>` to re-run only the failures). Do **not** re-issue `full-suite`.

The reason is wall-clock: a plain `<wrapper> test` recompiles the whole app target on every invocation, and that cold build — not the tests — dominates the time. Re-paying it on each retry is what produced the past hang. If the block is absent, fall back as described in SKILL.md §P3.1 (pr-evaluator `full-suite-command`, then prose + ask) and tell the user retries will cold-rebuild until the block is declared.

**2. Make it survive across turns — own it from the main loop.** A 15–30 min suite must be run as a **harness-tracked background bash** (`run_in_background: true`) owned by *this* main loop, not delegated to the `apple-platform-build-tools:builder` sub-agent. A sub-agent can end its turn while `xcodebuild` is still running and then have its session torn down, orphaning the process and losing the final tally (this is exactly what happened — the builder returned a partial snapshot and the run was lost). The harness auto-notifies you when a background bash completes, and the process survives across turns because the parent owns it. Keep the builder delegation (SKILL.md §P3.4) for the *short targeted* suites at §8/§10.6 only — the full canonical suite is the documented exception.

**3. cwd / command hygiene for the backgrounded command.** Two rules, both learned the hard way:

- **Use absolute paths; never chain the real command behind a relative `cd … &&`.** The skill's shell cwd may already be the worktree (cwd persists between Bash calls), so a relative `cd .worktrees/<branch> && …` *fails* — and `&&` then silently short-circuits the whole command to a no-op that exits `0`, so it looks like the suite passed when nothing ran. Resolve an absolute worktree path into a variable and `cd "$WT"` on its own line, or pass the command's directory explicitly.
- **Capture to files and read the file — don't re-run to see output.** Tee the full log to one file and a one-line pass/fail summary to another; on the completion notification, read the summary file. Re-running a 15–30 min suite just to see scrolled-off output is the same wasted cost the build-once rule exists to avoid (mirrors `COMMANDS.md`'s live-test "always re-read the log; never re-run" guidance).

## Drift rectification (Path A rebase / Path B merge / conflict handling / post-rectification)

Reached from SKILL.md "Check the integration branch" once the epic branch is behind `main` and "Choose strategy" has picked rebase or merge. Run the matching path, handle conflicts via the shared "Conflict handling" procedure, then "Post-rectification".

### Path A — Rebase

**Path A — Rebase.** Set up a worktree on the epic branch (reuse if one already exists per the worktree rules):

```bash
git worktree add .worktrees/epic-<N>-<slug> epic/<N>-<slug>
cd .worktrees/epic-<N>-<slug>
git rebase origin/main
```

Run the rebase. If it succeeds, push with `--force-with-lease` (never bare `--force`):

```bash
git push --force-with-lease origin epic/<N>-<slug>
```

If the rebase produces conflicts, follow the **Conflict handling** procedure — do not `git rebase --abort` yet.

### Path B — Merge

**Path B — Merge.** Set up a worktree on the epic branch (reuse if one already exists per the worktree rules):

```bash
git worktree add .worktrees/epic-<N>-<slug> epic/<N>-<slug>
cd .worktrees/epic-<N>-<slug>
git fetch origin main
git merge origin/main
```

If the merge is clean, git creates a merge commit. Push it:

```bash
git push origin epic/<N>-<slug>
```

This is a **normal push** — no `--force-with-lease`. Merge does not rewrite epic history, so open story PRs against `epic/<N>-<slug>` continue without disruption. (If `git push` is rejected because someone else advanced the epic branch since fetch, surface this to the user and re-run the assess phase rather than force-pushing.)

If the merge produces conflicts, follow the **Conflict handling** procedure — do not `git merge --abort` yet.

### Conflict handling

**Conflict handling.** Whichever path is running, on conflict the procedure is the same:

1. **Capture the conflict set.** (Scratch-file convention: route every scratch file this run writes through a per-run directory keyed on the issue/epic number this run targets — `/tmp/gh-resolver-<N>/` — so concurrent resolver runs never clobber each other's files. Here `<N>` is the epic number. Never write a scratch file to a fixed `/tmp` path or a bare relative path.)
   ```bash
   mkdir -p "/tmp/gh-resolver-<N>"
   git diff --name-only --diff-filter=U > /tmp/gh-resolver-<N>/conflict-files.txt
   ```
   Show the user the list. If the user prefers to handle conflicts manually, `git rebase --abort` or `git merge --abort` and stop here.

2. **Gather context for the sub-agent.** The sub-agent needs to see the conflict set as a whole, not file-by-file — a single commit on either side often touches multiple files in coordinated ways (renames, signature changes, paired test/implementation files), and resolving each file in isolation produces locally-plausible but globally-broken results. Collect:

   - Every conflicted file (with the `<<<<<<<` / `=======` / `>>>>>>>` markers as-is).
   - **Epic-side commit context.** `git log "$FORK_POINT"..origin/epic/<N>-<slug> --oneline` for the overview; for each commit that touched any conflicted file, `git show <sha>` to capture the commit message + the non-conflicted hunks (so the sub-agent sees the pattern, not just the collision points).
   - **Main-side commit context.** Same as the Epic-side bullet, for `"$FORK_POINT"..origin/main`.
   - **Epic-side PR/issue context.** The parent epic's `## Goal` and `## Stories` checklist, plus the merged story PR refs (which tell the sub-agent what landed during this epic's life).
   - **Main-side PR/issue context.** `gh pr list --repo <owner/repo> --base main --state merged --search "merged:>=<fork-date>" --json number,title,url` — what landed in `main` since fork.

3. **Spawn the sub-agent.** Use the `general-purpose` subagent (it needs both read tools and the ability to write a proposal). Prompt template:

   > You are resolving a git conflict set that arose from `<path>` of `epic/<N>-<slug>` onto `main`. Treat all conflicted files as one coherent unit — a single commit on either side often touches multiple files together, so resolving files in isolation produces broken results.
   >
   > Inputs:
   > - Conflicted files with markers: `<paths + contents>`
   > - Epic-side commit context (since fork): `<git log + git show output>`
   > - Main-side commit context (since fork): `<git log + git show output>`
   > - Epic Goal / Stories context: `<epic issue excerpt>`
   > - Main merged PRs since fork: `<gh pr list output>`
   >
   > Output one coherent resolution proposal across all files. For each file: the proposed final contents (or unified-diff-style edits), and a one-paragraph rationale explaining which side prevailed and why, plus any cross-file consequences (e.g. "kept the rename from the epic side; updated four call sites that arrived from main to use the new name"). If the conflict set is very large (more than ~20 files), first cluster files into logical groups (rename group, signature-change group, schema group, independent group) and emit one proposal per group with cross-group references where they matter.
   >
   > Do NOT edit any files. Return text only.

4. **Review and apply.** Show the user the whole proposal in one go (or grouped, for large sets). Ask for approval via `AskUserQuestion` (header "Rectify epic"): **Apply all** — apply the whole proposal; **Apply some** — apply a subset (the user names which groups to keep or skip via the free-text "Other", e.g. "apply rename group, skip schema group"); **Abort — manual** — resolve the conflicts by hand. On apply, **the skill** applies the proposed edits via the `Edit` tool — the sub-agent only proposes; the skill never lets the sub-agent write. On abort, `git rebase --abort` or `git merge --abort` and stop.

5. **Continue.** After edits are applied, stage and continue: `git add <files>` then `git rebase --continue` (Path A) or `git commit` to finalise the merge commit (Path B). If a second conflict round fires (e.g., rebase replaying the next commit hits new conflicts), re-enter conflict handling with the new conflict set.

### Post-rectification

**Post-rectification.** The epic HEAD has changed; the prior baseline (if any) is no longer trusted. Run the project's full canonical suite in the worktree per "Running the full canonical suite". On green, post a fresh `Baseline established` comment on the epic issue, recording the new `Epic branch SHA` (the post-rectification HEAD) and the new `Main SHA` (`git merge-base origin/main HEAD` — equals `origin/main`'s current tip for the rebase path; equals the `main` SHA that was merged in for the merge path). Without this, story-flow trust checks will detect the divergence and stop every subsequent story run. On red, handle per SKILL.md §7's standard red-baseline procedure (detour-first or explicit override).

## Bootstrap a new epic branch (branch does not exist on origin)

The epic infrastructure hasn't been bootstrapped yet. The epic-as-target run is the canonical place to do this — story runs deliberately stop and redirect here rather than bootstrap silently, so a missing step in the user's workflow stays visible. Bootstrap now (this includes a remote write).

Before the numbered steps that follow, derive the slug per SKILL.md's "Computing a fresh slug" (in "Resolving the epic branch name"); the resulting `epic/<N>-<slug>` is the `<branch>` for the rest of this bootstrap.

Every step runs from the new epic worktree; the main checkout is never touched:

1. Fetch the latest `main` and capture the SHA the bootstrap will pin to:
   ```bash
   git fetch origin main
   MAIN_SHA=$(git rev-parse origin/main)
   ```
2. Ensure `.gitignore` contains `.worktrees/` (append if missing). Run `git worktree list --porcelain` and reuse if a worktree for `epic/<N>-<slug>` already exists; otherwise create it branched directly off `origin/main`:
   ```bash
   git worktree add -b epic/<N>-<slug> .worktrees/epic-<N>-<slug> origin/main
   cd .worktrees/epic-<N>-<slug>
   ```
   Announce the path. Every subsequent command in the bootstrap (and every later epic-as-target run) lives here. Branching from `origin/main` rather than local `main` lets the bootstrap proceed without a `git checkout main` in the main tree, while still preserving the SHA invariant — the worktree's HEAD equals `MAIN_SHA` at creation time. If a fresh worktree was created (not reused), run the project's worktree-setup commands per SKILL.md §P2 before continuing to step 3.
3. Run the project's full canonical suite *in the worktree* per "Running the full canonical suite". This is the green baseline — it will be inherited by every story under this epic until invalidated. If red, follow SKILL.md §7's standard handling (detour-first or explicit override). If overridden, post a `Baseline override` comment on this epic issue before proceeding so any later story re-establishes the baseline.
4. On green (or after override), push the new branch from the worktree:
   ```bash
   git push -u origin epic/<N>-<slug>
   ```
5. Post the `Baseline established` comment on the epic issue (format per SKILL.md §7's "Persistence" subsection). At the fork point `Epic branch SHA` and `Main SHA` are both equal to the `MAIN_SHA` you captured in step 1 — record that single SHA in both fields.

## Legacy recovery (branch exists, comment missing)

The branch exists but the epic issue has no `Baseline established` comment (epic predates this rule, or the comment was never posted) → offer to establish one now on the epic branch HEAD. Set up a worktree on the epic branch first — fetch the branch, ensure `.gitignore` contains `.worktrees/`, run `git worktree list --porcelain` and reuse if one exists; otherwise:

```bash
git fetch origin epic/<N>-<slug>
git worktree add .worktrees/epic-<N>-<slug> epic/<N>-<slug>
cd .worktrees/epic-<N>-<slug>
```

If a fresh worktree was created (not reused), run the project's worktree-setup commands per SKILL.md §P2 before the canonical suite. Run the canonical suite *in the worktree* (per "Running the full canonical suite"), and on green post the comment with the current epic-branch SHA and the current `git merge-base origin/main origin/epic/<N>-<slug>` as `Main SHA`. Without this comment, every story under the epic would otherwise stop and redirect back here — establishing it once unblocks the whole epic.
