---
name: github-pr-evaluator
description: Evaluate a pull request against its origin issue, post a formal GitHub approval or soft-rejection review via the `gh` CLI, and recommend the right merge strategy for the cleanest possible git history. Use this skill whenever the user references a PR they want evaluated, approved, or merged — phrases like "is PR #N ready to merge?", "approve that PR if it looks good", "evaluate PR #N", "what's the right merge strategy?", "give me the squash title for #N", or "the review loop is done, what's next?" all qualify. Use this skill even when the code-review `/review` command has already run — `/review` covers code quality; this skill covers issue-fit, scope, doc grounding, and merge strategy. Use this even when the PR was opened manually (not by the issue resolver). Do NOT call `gh pr review --approve` or `gh pr merge` outside this skill.
---

# GitHub PR Evaluator

Evaluate whether a PR actually delivers what its origin issue asked for, post a formal GitHub review (approve or soft-reject), and surface the right merge strategy with a ready-to-run command. This is the final gate between "code reviewed" and "merged cleanly into main."

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status` to check)
- Working directory is the repo the PR belongs to, OR the user has specified `--repo owner/name`

If `gh` isn't authenticated, stop and tell the user — don't try to work around it.

## Workflow

### 1. Identify the PR

The user will give you a PR number (`#143`), a URL (`https://github.com/owner/repo/pull/143`), or context like "the PR I just opened." If you're already inside a `.worktrees/issue-<N>-...` directory, look up the PR for the current branch:

```bash
gh pr view --json number,title,url 2>/dev/null
```

Extract the PR number and owner/repo before proceeding. If the repo is ambiguous, ask once.

### 2. Self-approval pre-check

GitHub rejects self-approval with HTTP 422. Check upfront to avoid an error at the end:

```bash
PR_AUTHOR=$(gh pr view <N> --repo <owner/repo> --json author --jq .author.login)
CURRENT_USER=$(gh api user --jq .login)
```

If `$PR_AUTHOR == $CURRENT_USER`, note this now: the final review post must use `--comment` instead of `--approve`, regardless of verdict. The approval body content stays identical — only the review type changes.

### 3. Read the PR, linked issues, and prior reviews

Fetch everything needed for evaluation in one pass:

```bash
# Full PR context
gh pr view <N> --repo <owner/repo> --comments \
  --json number,title,body,state,isDraft,author,baseRefName,headRefName, \
         commits,additions,deletions,changedFiles,closingIssuesReferences, \
         comments,reviews,latestReviews,reviewDecision,mergeStateStatus, \
         mergeable,statusCheckRollup,headRefOid,url

# The diff
gh pr diff <N> --repo <owner/repo>

# Line-level code review comments (NOT included in the --comments flag above)
gh api repos/<owner>/<repo>/pulls/<N>/comments
```

Then for every issue number in `closingIssuesReferences`:

```bash
gh issue view <issue-#> --repo <owner/repo> --comments \
  --json number,title,body,state,labels,comments,url
```

**Draft PR guard.** If the PR `state` is `DRAFT`, stop here. Tell the user to mark it ready for review before evaluating.

**Story PR detection.** If `baseRefName` matches `epic/<N>-<slug>`, also fetch the parent epic's body and extract its `## Goal` and `## Background` sections for use in step 6.

Read everything before forming a verdict. The PR thread contains implementation decisions that may not be in the diff.

### 4. Read prior `/review` comments as a code-quality signal

The marketplace `/review` command (code-review quality) posts a numbered list of scored issues or a "No issues found" verdict as a PR comment. Filter `comments` and `reviews` for entries that look like that output.

- **"No issues found"** (or all issues scored below 80) → code quality is blessed; proceed to issue-fit evaluation.
- **Open issues remain** from the latest `/review` run and no subsequent commits address them → these become rejection signals. Your review body will cite which `/review` points are unresolved.
- **No `/review` comment found** → note this in your verdict body, but don't refuse to run. Many PRs arrive at this skill outside the resolver's review loop.

Do not re-invoke `/review` yourself.

### 5. Verify branch health

Before evaluating issue-fit, confirm the branch itself is green. This gate runs on every evaluation but uses a cached result when the PR head hasn't changed — so re-evaluating an unchanged PR costs nothing and leaves an auditable trail on the PR.

Produce two outputs for use in step 7 (verdict):
- `HEALTH_OK` — `true`, `false`, or `null` (user opted to skip)
- `HEALTH_BODY` — a short markdown fragment embedded near the top of the review body

#### 5.1 Resolve the PR HEAD SHA

Use `headRefOid` from the step 3 fetch (already in memory):

```bash
HEAD_SHA=<headRefOid value from step 3>
SHORT_SHA=${HEAD_SHA:0:7}
```

#### 5.2 Look for a prior cache comment

Search the PR comments for the health cache marker:

```bash
CACHE_COMMENT=$(gh api "repos/<owner>/<repo>/issues/<N>/comments" \
  --jq '.[] | select(.body | startswith("<!-- pr-evaluator-health-cache:v1 -->")) | {id: .id, body: .body}' \
  | head -n 1)
```

If a cache comment is found, parse the `SHA:` line from its body and compare to `HEAD_SHA`:

- **SHA matches `HEAD_SHA`** → the branch hasn't changed since the last check. Parse `HEALTH_OK` from the body (true if the first line contains "all green ✅", false if "failed ❌"). Set `HEALTH_BODY` to "Health check: re-using cached result at `<short-sha>`." Skip directly to step 6.
- **SHA differs (stale)** → record `OLD_CACHE_ID` from the comment. You'll delete the stale comment in step 5.6 before posting the new one. Continue to 5.3.

If no cache comment exists, continue to 5.3.

#### 5.3 GitHub CI shortcut

Check `statusCheckRollup` from the step 3 fetch. If it is a non-empty array and every entry's `conclusion` (or `state`) is `SUCCESS`, the branch has already been verified by CI at this SHA. Set `HEALTH_OK=true`, source as "GitHub statusCheckRollup", and jump to 5.6 to write the cache comment.

If the rollup is empty or contains any non-success entry (pending, failure, neutral, cancelled), continue to 5.4. Repos with no GitHub Actions always have an empty rollup and always fall through here.

#### 5.4 Discover this repo's health-check commands

Scan `CLAUDE.md` at the repo root — and any file it `@`-includes that is reachable from the root — for a block delimited by HTML comments:

```
<!-- pr-evaluator-health-checks -->
- `<command>` — <description>
- `<command>` — <description>
<!-- /pr-evaluator-health-checks -->
```

Each list item is a single Markdown list entry. Parse the first backtick-quoted span as the command and everything after ` — ` as the human label. Order matters: commands run in declaration order and the sequence is fail-fast.

**If no block is found:** tell the user which files were searched, then ask:

> "No `<!-- pr-evaluator-health-checks -->` block found in CLAUDE.md. Which commands should I run to verify this branch is green? (Or say 'skip health check for now'.)"

If the user supplies commands, use them for this run. After a green result, offer to add the block to CLAUDE.md — but do not write to it without explicit confirmation. If the user opts to skip, set `HEALTH_OK=null`, `HEALTH_BODY="Health check: skipped — no health-check block found in CLAUDE.md."`, and jump to step 6.

#### 5.5 Run the commands

This is the sole canonical full-suite gate. `github-issue-resolver` runs only Claude-selected unit and UI tests during its review-loop iterations (per "Test selection during iteration" in that skill); the comprehensive run — every test plan, lint, and type-check — fires here for the first time per PR HEAD SHA. If the run is red, that's the first authoritative signal that something needs fixing, so don't soft-pedal failures back to the user — surface them directly.

Run inside a clean checkout of the PR head. If a worktree at `.worktrees/<branch>` already exists (from the issue resolver workflow), reuse it. Otherwise create one:

```bash
git fetch origin <branch> --quiet
git worktree add ".worktrees/<branch>" "origin/<branch>" 2>/dev/null \
  || (git -C ".worktrees/<branch>" fetch origin && \
      git -C ".worktrees/<branch>" checkout <HEAD_SHA>)
```

**After creating a worktree** (the `git worktree add` arm above; not the reuse arm), run the project's worktree-setup commands. Discovery: scan `COMMANDS.md` and `CLAUDE.md` at the repo root, plus any file `@`-included from either, for a `<!-- worktree-setup -->` block. Each list item is one Markdown bullet — backtick-quoted command followed by ` — ` and a description (same format as the health-check block below). Run each command from inside the worktree (`cd .worktrees/<branch>`), in declaration order, fail-fast. On failure, stop and surface the failing command and the last 50 lines of its output — health checks against an unprovisioned worktree are unreliable. If no block is present, no-op silently. The teardown counterpart runs in step 14 paired with worktree removal. (`github-issue-resolver` documents the same convention in detail under "Worktree setup & teardown commands".)

For each command in declared order:

```bash
START=$(date +%s)
(cd ".worktrees/<branch>" && eval "<command>") > "/tmp/health-<i>.log" 2>&1
EXIT=$?
END=$(date +%s)
DURATION=$((END - START))
```

On the first non-zero exit: stop. Mark every remaining command `⏭ skipped`. Set `HEALTH_OK=false`. Capture the last 50 lines of the failing log as `FAIL_TAIL`.

**Apple-platform note:** when a command begins with `xcodebuild`, delegate to the `apple-platform-build-tools:builder` subagent — it absorbs the verbose build log and returns only pass/fail plus the first error. For all other commands, run inline.

#### 5.6 Write the cache comment

Compose the comment body:

```
<!-- pr-evaluator-health-cache:v1 -->
**Health checks** at `<short-sha>` — <all green ✅ | N failed ❌> — <ISO-8601 UTC timestamp>

SHA: <full-sha>
Source: CLAUDE.md

| Command | Status | Duration |
|---|---|---|
| `<cmd-1>` | ✅ pass | 1.2s |
| `<cmd-2>` | ❌ fail (exit 1) | 3.8s |
| `<cmd-3>` | ⏭ skipped | — |

<details>
<summary>Failed: `<cmd-2>` — last 50 lines</summary>

```
<FAIL_TAIL>
```
</details>

_Cached by `github-pr-evaluator`. Do not edit; will be regenerated when HEAD changes._
```

If a stale cache comment was found in 5.2, delete it first:

```bash
gh api -X DELETE "repos/<owner>/<repo>/issues/comments/<OLD_CACHE_ID>"
```

Then post:

```bash
gh pr comment <N> --repo <owner/repo> --body-file /tmp/pr-health-cache.md
```

Capture the resulting comment URL for use in `HEALTH_BODY`.

Set `HEALTH_BODY`:
- All green: `"Health check: ✅ all green at \`<short-sha>\` (<source>)"`
- Any failure: `"Health check: ❌ failed at \`<short-sha>\` — \`<failing-command>\` ([see cache comment](<comment-url>))"`

Do not post a cache comment when the user opted to skip (5.4 fallback).

### 6. Evaluate PR vs issue

For each issue in `closingIssuesReferences`, evaluate four dimensions. Write your assessment before drafting the verdict — this is where the approve/comment decision gets made.

**Scope match.** Does the diff change what the issue asked to change, and only that? Drive-by edits unrelated to the issue's stated problem are a flag. Small incidental fixes (typos in touched files, missing `Localizable.xcstrings` entries required by the build) are acceptable if called out in the PR body.

**Acceptance criteria / Definition of done.** For features, stories, and incomplete-feature issues, walk every item in `## Acceptance criteria` or `## Definition of done` and judge it against the diff and test files. An unchecked item that the diff doesn't address is a gap.

**Doc grounding.** Per the project's issue resolver workflow, PR bodies must include a `## Doc grounding` section citing the PRD, Architecture doc, or CLAUDE.md sections that constrained the approach. A missing or vague doc-grounding section is a flag for any non-trivial feature or refactor. (Skip for: one-line bug fixes, pure doc/typo changes, and repos with no docs at all.)

**Story / epic context.** If this is a story PR, the base must be `epic/<N>-<slug>` (not `main`), and the PR body must contain the caveat "This story targets the `epic/<N>-<slug>` integration branch and will reach `main` via the integration PR for epic #N." If this is an epic integration PR, the base must be `main`, the head must be `epic/<N>-<slug>`, and the body must include `Fixes #<epic-number>` so GitHub auto-closes the epic on merge.

### 7. Decide the verdict

**Approve** when:
- `HEALTH_OK == true`
- All four review dimensions pass
- No open `/review` issues remain from the latest run (or no `/review` has run and you've noted it)
- `reviewDecision` is not `REVIEW_REQUIRED` waiting on another specific reviewer

**Comment-rejection** (`gh pr review --comment`) when:
- `HEALTH_OK == false` — **always; this is a hard block.** A red branch never approves regardless of how well the code satisfies the issue. Lead the review body with `HEALTH_BODY`, name the failing command, and link to the cache comment. List any review-dimension gaps below it.
- Any review dimension fails — body lists each gap with the specific evidence that would close it. Use `--comment`, not `--request-changes` — `--comment` is a soft signal; `--request-changes` blocks merge and is heavy-handed for this workflow. Only switch to `--request-changes` if the user explicitly asks for a hard block.

When `HEALTH_OK == null` (user opted to skip): proceed with the dimension-only verdict and include `HEALTH_BODY` verbatim at the top of the review body so the human reviewer can see health was skipped.

If self-authored (step 2): downgrade `--approve` to `--comment` with identical body content, adding one line: "Self-authored PR — GitHub blocks self-approval. This comment documents the approval verdict; the merge can proceed."

### 8. Decide the merge strategy

First, check what the repo allows:

```bash
gh api repos/<owner>/<repo> \
  --jq '{allow_squash_merge,allow_merge_commit,allow_rebase_merge,delete_branch_on_merge,allow_auto_merge}'
```

If `gh api repos/<owner>/<repo>/branches/main/protection` returns 403 (private repo on free plan), that's expected — treat it as "no enforced linear-history rule" and move on.

Then pick the strategy by PR shape:

| PR shape | Detection | Strategy |
|---|---|---|
| Epic integration PR, multiple commits | `headRefName` matches `epic/...`, `baseRefName == main`, `commits.totalCount > 1` | **Merge commit** — preserves the per-story squash commits already on the epic branch as distinct entries in main's history |
| Epic integration PR, single commit | Same as above, `commits.totalCount == 1` | **Squash** — a merge commit wrapping one squash produces the orphan `Merge pull request #N` title that's the outlier in this project's history; squash yields canonical `feat: ... (#NN)` |
| Story PR | `baseRefName` matches `epic/...` | **Squash** — story collapses to one commit on the epic branch; the integration PR later preserves it |
| Standard PR | `baseRefName == main`, `headRefName` doesn't match `epic/...` | **Squash** — project default, consistent with 50-commit history |

Rebase is allowed by the repo but is unused in the project's history. Do not surface it as a peer option; if asked about it, explain the tradeoff but default to squash.

If the recommended strategy isn't allowed by the repo, fall back to the next best that is, and note why.

Never suggest `--auto` — the repo's `allow_auto_merge: false`.

### 9. Compose the squash subject (when recommending squash)

Format: `<type>(<scope>)?: <summary> (#<pr-number>)`

**Type** — inferred from the PR title prefix (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`) or issue labels when the title doesn't carry one (bug/incomplete → `fix`, feature/story/enhancement → `feat`). If both sources disagree, flag for user confirmation.

**Summary** — the PR title stripped of:
1. Any existing Conventional-Commits type prefix (`fix: `, `feat(auth): `, etc.)
2. Any trailing ` (#\d+)` suffix — this is the double-suffix bug visible in this project's history, where a PR title like `fix: resolve null token (#143)` becomes `fix: resolve null token (#143) (#143)` on squash. Strip it before appending the new `(#<pr-number>)`.

**Body** — PR body's `## Summary` section (or the first paragraph if no Summary section), with `Fixes #<issue-number>` appended if not already present. For epic integration PRs merged with `--merge`, omit body composition — the PR body itself becomes the merge commit message.

Always show the proposed subject and body to the user before posting (step 10). Type inference is reliable enough to be useful but not reliable enough to trust silently.

### 10. Show the draft and post the review

Show the user a summary of the verdict and merge plan, then **immediately post the review without waiting for confirmation**. The review is informational — confirming it buys nothing and adds friction.

Display before posting:

**Review verdict:**
```
Verdict: APPROVE (or COMMENT-REJECTION)
Review type: --approve (or --comment — self-authored)

<review body text — starts with HEALTH_BODY, then dimension-by-dimension assessment>
```

**Merge strategy:**
```
Recommended merge: SQUASH (or MERGE COMMIT, with rationale)
Allowed strategies: squash ✓, merge ✓, rebase ✓

Proposed squash subject:
  fix: resolve null token in onboarding (#143)

Proposed squash body:
  Resolves the nil-token crash on first launch.
  Fixes #141
```

**Merge-readiness flags** (surfaced separately from the verdict — don't let them block approval):
- `mergeStateStatus == BEHIND` → "Branch is behind base — rebase or merge base before merging."
- `mergeStateStatus == DIRTY` → "Branch has conflicts — resolve before merging."
- `mergeStateStatus == BLOCKED` → "Merge blocked by branch protection — check status checks."
- `reviewDecision == REVIEW_REQUIRED` and owed to another reviewer → "Awaiting review from @reviewer — your approval will still post, but merge may be gated."

Then proceed directly to step 11 — no confirmation needed.

### 11. Post the review

Write the review body to a temp file and post:

```bash
cat > /tmp/pr-review-body.md <<'EOF'
<review body content>
EOF

gh pr review <N> --repo <owner/repo> --approve --body-file /tmp/pr-review-body.md
# or: --comment  (self-authored or soft-rejection)
```

Capture the URL returned (or construct it from the PR URL) and share it with the user. Clean up the temp file.

### 12. Offer to run the merge

After the review posts, show the exact command and ask for explicit confirmation before running. Name the merge mode prominently so the user knows exactly what will happen.

**Squash merge** — ask:
> "Merge PR #\<N\> using **SQUASH** (`--squash`) with subject: `fix: resolve null token in onboarding (#143)`? Reply yes to proceed."

```bash
gh pr merge <N> --repo <owner/repo> --squash \
  --subject "fix: resolve null token in onboarding (#143)" \
  --body-file /tmp/squash-body.md \
  --delete-branch   # append only if delete_branch_on_merge is false
```

**Merge commit** (epic integration) — ask:
> "Merge PR #\<N\> using a **MERGE COMMIT** (`--merge`) — this preserves all story squash commits as distinct entries in main's history. Reply yes to proceed."

```bash
gh pr merge <N> --repo <owner/repo> --merge \
  --delete-branch   # if delete_branch_on_merge is false
```

Run only on explicit user confirmation. Never use `--auto`.

Temp files from steps 11–12 are cleaned up after use.

### 13. Close the story issue and tick the epic checkbox (story PRs only)

Story PRs merge into `epic/<N>-<slug>`, not `main`. GitHub's auto-close-on-merge only fires when a PR merges into the default branch, so `Fixes #<story-number>` in the PR body is never triggered. Both actions below are needed to reflect reality in the issue tracker.

Skip this entire step if the merge didn't run (the user declined in step 12). Neither action should fire before the branch has actually landed.

The user already approved the merge — run both cleanup actions immediately without asking again.

**First: close the story issue.** Re-fetch its current state in case another tool already closed it:

```bash
STORY_STATE=$(gh issue view <story-N> --repo <owner/repo> --json state --jq .state)
```

If `STORY_STATE == "OPEN"`, run immediately:

```bash
gh issue close <story-N> --repo <owner/repo> --reason completed \
  --comment "Closed by #<pr-number> (merged into \`epic/<N>-<slug>\`). GitHub does not auto-close issues from PRs that merge into a non-default branch."
```

If already `CLOSED`, note it and skip — don't re-close.

**Second: tick the epic checkbox.** GitHub task lists don't auto-tick on PR merge. Now that the story is confirmed done, update the parent epic's `## Stories` checkbox.

Fetch the current epic body (always re-fetch; don't use the copy from step 3 — another story may have merged since then):

```bash
gh issue view <epic-N> --repo <owner/repo> --json body --jq .body > /tmp/epic-body-current.md
```

Find the `- [ ] #<story-number>` line in `## Stories` and replace it with `- [x] #<story-number>`. Show the user the diff, then run immediately:

```bash
gh issue edit <epic-N> --repo <owner/repo> --body-file /tmp/epic-body-updated.md
```

Clean up temp files after. If the checkbox is already `[x]` (another tool beat us to it), note it and skip the edit.

### 14. Clean up and summarise

**If the merge ran**, execute cleanup immediately — no further confirmation needed:

1. **Run worktree-teardown** (if any commands are declared and a worktree exists). Discover the `<!-- worktree-teardown -->` block from `COMMANDS.md` / `CLAUDE.md` (and any file `@`-included from either), using the same parser as the health-check block. From inside the worktree (`cd .worktrees/<branch>`), run each command in declaration order. **Best-effort**: log any failure with the failing command and the last 50 lines of its output, then continue to the next command and on to step 2. Skip silently if no block is declared. This releases per-worktree resources the project provisioned at setup (simulators, containers, ports, scratch databases, etc.) before the worktree itself is removed.

2. **Remove the worktree** (if one exists for this PR's branch):
   ```bash
   git worktree list --porcelain | grep -A1 'branch refs/heads/<branch>' | grep 'worktree' | awk '{print $2}'
   ```
   If a worktree path is found under `.worktrees/`:
   ```bash
   git worktree remove .worktrees/<branch>
   ```

3. **Delete temp files** created during this run: `/tmp/pr-review-body.md`, `/tmp/squash-body.md`, `/tmp/epic-body-current.md`, `/tmp/epic-body-updated.md`, `/tmp/pr-health-cache.md`, `/tmp/health-*.log`.

Then print the final summary:
- Review posted: URL
- Merge: run (with resulting commit hash if available)
- Story issue: closed (link) or "already closed" *(story PRs only)*
- Epic checkbox: ticked (link to updated epic) *(story PRs only)*
- Worktree teardown: ran (N command(s)) | none declared | failed at step *i*: `<command>` (continued)
- Worktree: removed at `<path>` or "none found"

**If the merge did not run** (user declined in step 12):
- Review posted: URL
- Merge: not run — command shown above, run when ready
- Story issue / epic checkbox: left unchanged *(story PRs only)*
- Worktree teardown: not run (worktree left in place)
- Worktree: left in place

---

## If the PR is a story PR

Detection: `baseRefName` matches `epic/<N>-<slug>`.

1. Fetch the parent epic using the same logic as the issue resolver (search open/closed epics whose body contains `#<story-number>`).
2. Read the epic's `## Goal` and `## Background` as additional grounding for the scope evaluation in step 6.
3. In your verdict, cite the parent epic's goal when assessing whether the diff advances it.
4. Verify the PR body contains the integration-branch caveat (the line beginning "This story targets the `epic/<N>-<slug>` integration branch"). Flag if missing.
5. Recommended strategy: squash (not merge commit). The story's commits collapse to one on the epic branch; the integration PR later preserves them.
6. After merge, close the story issue (`gh issue close --reason completed`) and tick the parent epic's `## Stories` checkbox for this story — see step 13.

---

## If the PR is an epic integration PR

Detection: `headRefName` matches `epic/<N>-<slug>` AND `baseRefName == main`.

1. Fetch the epic issue and read its `## Stories`, `## Definition of done`, and `## Goal` sections.
2. For scope evaluation: the diff should be the accumulated stories — each story's squash commit landing on the epic branch. Drive-by changes beyond what the stories describe are a flag.
3. Verify `Fixes #<epic-number>` is in the PR body.
4. Verify every story PR is listed in the body.
5. Walk every item in `## Definition of done` and judge it against the accumulated diff. Unfulfilled items → rejection.
6. Strategy: merge commit (if `commits.totalCount > 1`), squash (if single commit).
7. This PR carries more risk than a story PR — it lands the entire epic on main at once. Hold approval if DoD is incomplete or if the diff contains unexpected changes. Ask before proceeding if uncertain.

---

## Common pitfalls

- Don't approve when `HEALTH_OK == false` — health-check failure is a hard block regardless of how well the PR satisfies the issue. The branch must be green before any approval.
- Don't approve a PR whose latest `/review` run left unresolved flagged issues — cite them in the rejection body.
- Don't recommend rebase for this project — it's allowed but unused. Squash is the grain; go with it.
- Don't run `gh pr merge` automatically — the user must confirm the merge in step 12. Once confirmed, run all cleanup (worktree removal, story issue close, epic checkbox) without asking again.
- Don't compose a squash subject with a double `(#NN)` suffix. Strip any trailing ` (#\d+)` from the PR title before appending `(#<pr-number>)`.
- Don't post `--approve` for a self-authored PR — GitHub will 422. Use `--comment` with the same body.
- Don't block approval over `mergeStateStatus == BEHIND` or `DIRTY` — approve on code merit and surface the merge-readiness blocker separately.
- Don't use `--request-changes` unless the user explicitly asks for it — `--comment` is the project default for soft rejections.
- Don't skip the doc-grounding check for features and stories — it's load-bearing for traceability.
- Don't recommend a strategy the repo doesn't allow — always clamp to the `allow_*` fields.
- Don't skip the draft-PR guard — evaluating a draft produces a confusing review that may mislead the author.
- Don't try to approve a PR that has `reviewDecision == REVIEW_REQUIRED` waiting on a named reviewer unless the user confirms. The approval will post, but it may confuse the pending reviewer.
- Don't use `--auto` — the repo has `allow_auto_merge: false`.
- Don't conflate issue-fit and code-quality. Issue-fit (this skill) asks "did the PR deliver what the issue asked for." Code quality (`/review`) asks "is this code well-written." Both are necessary; neither substitutes for the other.
- Don't rely on `Fixes #<story-number>` to auto-close a story issue — story PRs merge into `epic/<N>-<slug>`, not `main`, so GitHub records the linkage but never fires the close. Step 13 closes the story issue explicitly.
- Don't silently write the `<!-- pr-evaluator-health-checks -->` block to CLAUDE.md — always ask the user for confirmation before modifying project files.
- Don't run worktree-teardown when the merge didn't run. Teardown is paired with worktree removal; if the worktree stays, teardown stays deferred. The user will either re-invoke the evaluator (which retries the merge → cleanup pair) or run the manual cleanup sequence (`github-issue-resolver` §11) themselves. Running teardown without removing the worktree leaves a worktree whose resources have been released — tests started from there would silently fail against missing dependencies.
- Don't fail the cleanup step if teardown fails. Teardown is best-effort: log the failure and continue to `git worktree remove`. A leaked resource is recoverable (the user can find and clean it up manually); a stuck worktree blocks future runs against the same branch.

## When to ask the user

- The PR has multiple `closingIssuesReferences` and their acceptance criteria conflict (e.g., one issue wants X, another wants not-X).
- The latest `/review` run flagged issues that look unaddressed — confirm whether to treat them as a hard rejection or note them and proceed.
- The composed squash subject's inferred `<type>` is ambiguous (issue labels and PR title disagree, or neither carries a Conventional-Commits prefix).
- The PR is an epic integration PR and one or more `## Definition of done` items aren't evidently satisfied by the diff.
- `reviewDecision == REVIEW_REQUIRED` and it's owed to a specific reviewer who hasn't acted — ask whether to proceed or wait.
- The PR has no `closingIssuesReferences` — ask which issue it addresses before running the scope evaluation, or confirm that it's intentionally standalone (e.g., a chore or doc update).
- Branch protection returns something other than 403 that suggests a stricter-than-expected merge policy.
- No `<!-- pr-evaluator-health-checks -->` block is found in CLAUDE.md — ask which commands to run (or whether to skip).

## Repo health-check declaration

A repository declares its merge-readiness commands by placing a fenced block in `CLAUDE.md` (or any file `CLAUDE.md` `@`-includes that is reachable from the repo root). The block is delimited by HTML comments so it's invisible in rendered Markdown:

```markdown
<!-- pr-evaluator-health-checks -->
- `<command>` — <description>
- `<command>` — <description>
<!-- /pr-evaluator-health-checks -->
```

Each item is a single Markdown list entry: a backtick-quoted command followed by ` — ` and a short human description. Commands run in declaration order and are fail-fast — the first non-zero exit stops the sequence and marks remaining commands as skipped. Commands may use repo-root-relative paths (e.g. `./scripts/lint.sh`); the skill always `cd`s into the branch worktree before invoking each one.

**Example** (food-journal):

```markdown
<!-- pr-evaluator-health-checks -->
- `./scripts/check-layer-imports.sh` — Layer-import boundary lint (fast, <5s)
- `./scripts/run-swiftlint.sh` — SwiftLint (CI=1 promotes to --strict)
- `xcodebuild test -project FoodJournal.xcodeproj -scheme FoodJournal -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro'` — Build + full unit/UI test suite
<!-- /pr-evaluator-health-checks -->
```

Order matters: put fast commands first so the sequence fails quickly on simple errors without waiting for a multi-minute build.

The health-check cache comment (posted by step 5.6) uses the marker `<!-- pr-evaluator-health-cache:v1 -->` and is keyed to the PR HEAD SHA. It is updated automatically whenever HEAD changes; do not edit it manually.
