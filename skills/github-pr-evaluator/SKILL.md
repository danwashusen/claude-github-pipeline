---
name: github-pr-evaluator
model: opus
effort: medium
description: Evaluate a pull request against its origin issue, post a formal GitHub approval or soft-rejection review via the `gh` CLI, and recommend the right merge strategy for the cleanest possible git history. Use this skill whenever the user references a PR they want evaluated, approved, or merged — phrases like "is PR #N ready to merge?", "approve that PR if it looks good", "evaluate PR #N", "what's the right merge strategy?", "give me the squash title for #N", or "the review loop is done, what's next?" all qualify. Use this skill even when the code-review `/review` command has already run — `/review` covers code quality; this skill covers issue-fit, scope, doc grounding, and merge strategy. Use this even when the PR was opened manually (not by the issue resolver). Do NOT call `gh pr review --approve` or `gh pr merge` outside this skill.
---

# GitHub PR Evaluator

Evaluate whether a PR actually delivers what its origin issue asked for, post a formal GitHub review (approve or soft-reject), and surface the right merge strategy with a ready-to-run command. This is the final gate between "code reviewed" and "merged cleanly into main."

### Asking the user a decision

When you need a decision from the user — an approval gate, a disambiguation, or a confirmation before a GitHub write — follow the shared contract in [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md): one decision per `AskUserQuestion` card, `header` ≤ 12 chars, imperative `label`s with consequence-bearing `description`s, options generated dynamically when the candidates aren't fixed, and the rule that a sub-agent never calls `AskUserQuestion` itself but surfaces a "decision needed" signal back to this main loop. That file is the single source of truth for every gate in this skill.

### Delegating mechanical work to `github-ops`

The judgment in this skill — the issue-fit evaluation, the verdict, the merge-
strategy call — is what's worth the expensive model. The judgment-free GitHub I/O
is not: fetching the PR + diff + linked issues + prior reviews, the health-cache
marker lookup, the implementation-plan lookup, and posting the cache comment and
the final review. Delegate that to the **`github-ops`** sub-agent
(`subagent_type: "github-pipeline:github-ops"`, Sonnet + medium effort — spawn with **no `model`
override**): `GATHER_PR`, `GATHER_ISSUE`, `PERSIST_COMMENT` (see
`../../agents/github-ops.md`). It returns PR/issue bodies, threads, and the diff
**verbatim** so the evaluation stays yours.

**What does *not* delegate:** the §2 self-approval pre-check and the §5 branch-
health gate (the **test-selection** `Explore` agent and the
`apple-platform-build-tools:builder` delegation) stay exactly as they are — they
are judgment/verification, not mechanical I/O. `github-ops` only runs the
GitHub-API fetch/post above.

Like the other sub-agents, `github-ops` cannot call `AskUserQuestion`; on any
ambiguity it returns `DECISION_NEEDED: <…>` and writes nothing. Every
`PERSIST_COMMENT` — including the final `pr-review` post — runs only **after** the
relevant gate (the §10 draft-confirm for the review; the §2 self-approval check
decides its `review_action` of `approve` vs `comment`). `github-ops` posts the
body you pass and executes the `review_action` you specify; the verdict is yours.

**Trust the returned URL.** `github-ops` returns the canonical comment/review URL
on a successful post — that URL is your confirmation the write landed. Do **not**
re-query the PR's comment thread (`gh api …/comments`, `gh pr view … --json
comments`), and do **not** spawn a second `github-ops` call, to confirm a post you
already dispatched. A tool result that seems slow is buffered, not lost — wait for
it rather than re-verifying.

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

Fetch everything needed for evaluation in one pass via `github-ops`:

> `GATHER_PR(pr=<N>, repo=<owner/repo>, include_diff=true, include_line_comments=true, marker_prefix="<!-- pr-evaluator-health-cache:v1 -->", scratch_dir=/tmp/gh-pr-eval-<N>/)`

`scratch_dir` matters: it's the same per-run dir documented at §5.5.1 ("Scratch-file convention"), and routing every verbatim artifact through it is what keeps the GATHER step from burning 7+ minutes of wall-clock on big-diff PRs (see github-ops.md rule 7). The call returns a `## RESULT` envelope of scalars + path references — `body_path`, `thread_path`, `reviews_path`, `diff_path`, `line_comments_path`, `marker_comment_path` when present — plus all PR metadata (`headRefOid`, `statusCheckRollup`, `closingIssuesReferences`, `mergeStateStatus`, `mergeable`, `reviewDecision`, `additions`/`deletions`/`changedFiles`/`commit_count`, `url`). **Read the PR body, the diff, and any reviews from those paths yourself** — github-ops doesn't echo them inline. Because `marker_prefix` is set, the envelope **also** carries the health-cache marker comment scalars (`marker_comment_id` / `_url` / `_path` / `_bytes`, or `marker_comment_present: false`) — §5.2 reuses that, so the health check needs no second fetch.

Then for every issue number in `closingIssuesReferences`, fetch the issue **with its plan comment** so step 6 already has it (same `scratch_dir` so per-run cleanup stays trivial):

> `GATHER_ISSUE(issue=<issue-#>, repo=<owner/repo>, marker_prefix="<!-- implementation-plan:v1 -->", scratch_dir=/tmp/gh-pr-eval-<N>/)`

The issue's body, thread, and plan-marker body land at the returned `issue_body_path` / `thread_path` / `marker_comment_path` — `Read` them when you need their content.

**Draft PR guard.** If the PR `state` is `DRAFT`, stop here. Tell the user to mark it ready for review before evaluating. (The canonical resolver handoff path doesn't trip this guard: `github-issue-resolver` §11's *last planned phase shipped* row flips a multi-phase PR draft → ready immediately before emitting the handoff, so a draft PR reaching this evaluator is either a genuinely-in-progress PR — multi-phase or otherwise — or a manual invocation on an unfinished PR. In both cases stopping here is the right behavior. On the soft-reject path the evaluator's own §11 flips the PR back to draft so the resolver can re-enter cleanly; that re-flip is part of this skill's contract with the resolver, not a violation of this guard.)

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

The §3 `GATHER_PR` already fetched the health-cache marker (its `marker_comment_id` / `_url` / `_path` if one exists, or `marker_comment_present: false` if not) — reuse it; don't spawn a second `GATHER_PR`. When a marker is present, `Read` its body from `marker_comment_path` to parse the `SHA:` line.

If a cache comment was found, parse the `SHA:` line from its body and compare to `HEAD_SHA`:

- **SHA matches `HEAD_SHA`** → the branch hasn't changed since the last check. Parse `HEALTH_OK` from the body (true if the first line contains "all green ✅", false if "failed ❌"). Parse the `TIER:` line if present (`targeted` or `full`); a comment without a `TIER:` line is from a pre-targeting cache and is interpreted as `full`. Set `HEALTH_BODY` to "Health check: re-using cached result at `<short-sha>` (tier: `<tier>`)." Skip directly to step 6. (Note: if the cached tier is `targeted` and the user has explicitly asked for the full canonical suite this run — e.g., "re-evaluate PR #X with full" — treat the cache as a miss instead. This is rare and only triggered by explicit user direction; ordinary re-evaluations honour the cache as-is.)
- **SHA differs (stale)** → record `OLD_CACHE_ID` from the comment. You'll delete the stale comment in step 5.6 before posting the new one. Continue to 5.3.

If no cache comment exists, continue to 5.3.

#### 5.3 GitHub CI shortcut

Check `statusCheckRollup` from the step 3 fetch. If it is a non-empty array and every entry's `conclusion` (or `state`) is `SUCCESS`, the branch has already been verified by CI at this SHA. Set `HEALTH_OK=true`, source as "GitHub statusCheckRollup", and jump to 5.6 to write the cache comment.

If the rollup is empty or contains any non-success entry (pending, failure, neutral, cancelled), continue to 5.4. Repos with no GitHub Actions always have an empty rollup and always fall through here.

#### 5.4 Discover this repo's health-check blocks

Scan `COMMANDS.md` and `CLAUDE.md` at the repo root — and any file either `@`-includes that is reachable from the root — for three marker-delimited blocks:

```
<!-- pr-evaluator-static-checks -->
- `<command>` — <description>
...
<!-- /pr-evaluator-static-checks -->

<!-- pr-evaluator-test-target -->
- wrapper: `<test-runner command>`
- full-suite-command: `<command for the full canonical suite>`
- targets:
  - `<TargetName>` (unit | UI)
    - naming: <how source files map to suite identifiers>
    - helpers-fallback: <command, or "none">
    - broad-change-fallback: <command, or "none">
  - ...
<!-- /pr-evaluator-test-target -->

<!-- pr-evaluator-escalation-labels -->
- `<label-name>` — <description>
- ...
<!-- /pr-evaluator-escalation-labels -->
```

- **Static checks** (`pr-evaluator-static-checks`) — fail-fast list of always-run hygiene (codegen, dependency resolution, lints, layer-import boundary checks). One Markdown list entry per command, backtick-quoted, followed by ` — ` and a short description. **No test invocations belong here** — tests are handled separately by the test-target block.
- **Test target** (`pr-evaluator-test-target`) — configuration for the test-selection sub-agent (see §5.5). Prose-structured Markdown — read it as natural language; don't try to parse it. The `full-suite-command` line is what gets returned when escalation rules trigger.
- **Escalation labels** (`pr-evaluator-escalation-labels`) — list of GitHub PR labels that force the full-suite command instead of targeted selection. Empty or absent block = no label-based escalation.

Read all three blocks once and remember them for the rest of this step.

**Backward compatibility — projects that haven't migrated.** Older projects still declare a single `<!-- pr-evaluator-health-checks -->` block containing both static checks and the test invocation. If `pr-evaluator-static-checks` is absent but `pr-evaluator-health-checks` is present, treat the legacy block as the full command list and run it as-is — skip the test-selection sub-agent step. This produces the legacy behaviour (full suite every time) and keeps the skill working on un-migrated projects. If `pr-evaluator-test-target` is absent but `issue-resolver-test-target` is present (the project has migrated `github-issue-resolver` but not `github-pr-evaluator`), reuse the issue-resolver block with one assumption: the `full-suite-command` defaults to the wrapper command with no flags (so for `wrapper: ./scripts/xcb.sh`, the full-suite command is `./scripts/xcb.sh`).

**If neither static-checks nor health-checks blocks are found:** tell the user which files were searched, then call `AskUserQuestion` (`header: "Health check"`; question text: "No `<!-- pr-evaluator-static-checks -->` or `<!-- pr-evaluator-health-checks -->` block found in COMMANDS.md or CLAUDE.md. How should I verify this branch?") with options:

- **Skip for now** — set `HEALTH_OK=null` and proceed without running a local gate.
- **I'll specify commands** — use the auto-appended "Other" free-text choice to type the exact commands to run for this branch.

If the user supplies commands (via the "Other" free-text answer), use them for this run as a flat command list (skip the sub-agent step). After a green result, offer to add the static-checks block — but do not write to it without explicit confirmation. If the user opts to skip, set `HEALTH_OK=null`, `HEALTH_BODY="Health check: skipped — no static-checks block found."`, and jump to step 6.

#### 5.5 Run the gate

The local gate is a three-step sequence: static checks (always), test selection (a sub-agent decides which tests are warranted), test execution. Targeted by default; escalates to the full canonical suite when the PR type or labels warrant it. The full canonical suite is **not** the default any more — it runs only for epic-integration PRs and explicitly-labelled PRs. The broader safety net is CI on the integration target (already short-circuited at §5.3); when CI is green at this SHA, the local gate doesn't run at all.

If a legacy `pr-evaluator-health-checks` block was found at §5.4 with no `pr-evaluator-static-checks` counterpart, run that block as a flat command list (the legacy code path) and skip steps 2–3 below. Everything else in §5.5.0 (worktree creation/setup) still applies.

##### 5.5.0 Worktree

Run inside a clean checkout of the PR head. If a worktree at `.worktrees/<branch>` already exists (from the issue-resolver workflow), reuse it. Otherwise create one:

```bash
git fetch origin <branch> --quiet
git worktree add ".worktrees/<branch>" "origin/<branch>" 2>/dev/null \
  || (git -C ".worktrees/<branch>" fetch origin && \
      git -C ".worktrees/<branch>" checkout <HEAD_SHA>)
```

**Run the worktree-setup commands before every test run** — on both the create arm above and the reuse arm. Setup is required to be idempotent by the convention documented at the bottom of this file ("Repo health-check declaration") and in `github-issue-resolver` §P2 "Worktree setup & teardown commands"; re-running it on a healthy worktree must be a no-op or near-no-op (e.g., reuse the existing simulator UDID when it still resolves, otherwise discard stale state and provision afresh). This guarantee removes the failure mode where a reused worktree's per-worktree resources have been lost (state file deleted, simulator wiped externally, or setup never ran in the first place because the original `github-issue-resolver` invocation missed the discovery) and the test wrapper silently falls back to a shared/global resource — masking the per-worktree isolation the setup hook exists to provide.

Discovery: scan `COMMANDS.md` and `CLAUDE.md` at the repo root, plus any file `@`-included from either, for a `<!-- worktree-setup -->` block. Each list item is one Markdown bullet — backtick-quoted command followed by ` — ` and a description (same format as the static-checks block above). Run each command from inside the worktree (`cd .worktrees/<branch>`), in declaration order, fail-fast. On failure, stop and surface the failing command and the last 50 lines of its output — gates against an unprovisioned worktree are unreliable. If no block is present, no-op silently. The teardown counterpart runs in step 14 paired with worktree removal. (`github-issue-resolver` documents the same convention in detail under §P2 "Worktree setup & teardown commands".)

##### 5.5.1 Static checks

**Scratch-file convention.** Every scratch file this run writes lives under a
per-run directory keyed on the PR number: `/tmp/gh-pr-eval-<N>/` (`<N>` is the PR
number from step 1). Concurrent evaluator runs are normal, and a fixed `/tmp` name
is a real failure mode — two runs sharing `/tmp/squash-body.md` or
`/tmp/epic-body-current.md` overwrite each other mid-flight, and acting on a
clobbered epic body can edit the *wrong* epic. Never write a scratch file to a
fixed `/tmp` path; route every one through `/tmp/gh-pr-eval-<N>/`. Create the
directory once before the first write:

```bash
mkdir -p "/tmp/gh-pr-eval-<N>"
```

For each command in `<!-- pr-evaluator-static-checks -->` in declared order:

```bash
START=$(date +%s)
(cd ".worktrees/<branch>" && eval "<command>") > "/tmp/gh-pr-eval-<N>/health-<i>.log" 2>&1
EXIT=$?
END=$(date +%s)
DURATION=$((END - START))
```

On the first non-zero exit: stop. Mark every remaining command (and the test-execution step below) `⏭ skipped`. Set `HEALTH_OK=false`. Capture the last 50 lines of the failing log as `FAIL_TAIL`. Skip ahead to §5.6 to write the cache comment.

##### 5.5.2 Test selection

Spawn a read-only `Explore` sub-agent for selection. Reasoning happens inside the sub-agent so the main conversation never sees the diff hunks, the test directory listings, or the grep output — only the sub-agent's two-section verdict.

Determine the PR type from data already in memory (per the "If the PR is a story PR" / "If the PR is an epic integration PR" sections below):
- `pr_type: epic-integration` if `headRefName` matches `epic/<N>-<slug>` AND `baseRefName == main`
- `pr_type: story` if `baseRefName` matches `epic/<N>-<slug>`
- `pr_type: regular` otherwise

Collect the PR's GitHub labels from the step-3 fetch (`labels` array). If any label name matches an entry in the `pr-evaluator-escalation-labels` block, set `escalation_label_matched: <label-name>`; otherwise empty.

**See [`references/test-selection-sub-agent.md`](references/test-selection-sub-agent.md) for the full prompt template** — substitute the worktree path, PR base branch, HEAD SHA, `pr_type`, the matched escalation label (if any), and the `<!-- pr-evaluator-test-target -->` block contents at dispatch. It applies the escalation rules (epic-integration or escalation-label → full suite) before the heuristic path (diff-driven suite selection plus the UI blast-radius widening pass), and returns exactly two sections with the literal headers `COMMAND:` and `RATIONALE:`.

The step-5 exploration pass is the heart of the selection's safety against root-view regressions: a small diff in a high-fanout view can break unrelated UI tests, and name proximity won't catch it. Trust the sub-agent to decide how deep to read; widening is the correct default when blast radius is uncertain. The full `RATIONALE:` is also written into the cache comment in §5.6, so post-mortems can audit *why* a given run was targeted vs. full.

The skill parses these two sections. Print `RATIONALE:` to the user verbatim as the gate's status line — that's how the user audits the selection in real time. Capture it as `SELECTION_REASONING` for use in the cache comment. Set `TIER`:
- `full` if `COMMAND:` matches the config's `full-suite-command`
- `targeted` otherwise (including `(none)`)

##### 5.5.3 Test execution

If `COMMAND:` is `(none)`, skip execution. Set `HEALTH_OK=true` for the test phase (no tests selected ≠ failure). Skip ahead to §5.6.

Otherwise, run the command from inside the worktree:

```bash
START=$(date +%s)
(cd ".worktrees/<branch>" && eval "<COMMAND>") > "/tmp/gh-pr-eval-<N>/health-test.log" 2>&1
EXIT=$?
END=$(date +%s)
DURATION=$((END - START))
```

If the command begins with `xcodebuild` (or invokes a wrapper that runs `xcodebuild`, like `./scripts/xcb.sh`), delegate to the `apple-platform-build-tools:builder` subagent — it absorbs the verbose build log and returns only pass/fail plus the first error. For all other commands, run inline.

**Bound the subagent's scope explicitly when invoking it.** The builder is a build-runner, not an autonomous coder. The delegation is narrow and one-shot: run the command exactly as given, capture the result, and report pass/fail plus the first error. It must not edit code, "fix" failures it diagnoses, re-run with different flags, or expand scope. Failures bubble back to this skill — `HEALTH_OK=false` is the right outcome for a real failure, and the user (or `github-issue-resolver` on a re-run) decides what to fix. A silent diagnose-and-fix loop inside the subagent uncaps the wall-clock cost of a single delegation, hides code changes from the PR's commit history, and breaks the cache schema's assumption that `HEALTH_OK` reflects the suite's actual state. State the constraint in the prompt:

> *"Run this exact command from this exact directory: `<command>` (cwd: `.worktrees/<branch>`). Absorb the log. Return pass/fail plus, on fail, the first error and the failing test name(s). Do not edit any source files. Do not re-run with modified flags. Do not investigate failures beyond identifying them. If the test fails, the pr-evaluator skill will handle next steps (typically, posting a soft-rejection review and surfacing the failure to the user)."*

On non-zero exit: set `HEALTH_OK=false`. Capture the last 50 lines as `FAIL_TAIL` for the cache comment.

#### 5.6 Write the cache comment

Compose the comment body:

```
<!-- pr-evaluator-health-cache:v1 -->
**Health checks** at `<short-sha>` — <all green ✅ | N failed ❌> — <ISO-8601 UTC timestamp>

SHA: <full-sha>
TIER: <targeted | full>
Source: COMMANDS.md / CLAUDE.md

**Selection reasoning** (from §5.5.2 sub-agent):
> <SELECTION_REASONING verbatim — the sub-agent's RATIONALE: section. Multi-line
> rationales render as one block-quote line per logical line. Omit the entire
> block when test selection didn't run, e.g. when static checks failed before
> §5.5.2 fired.>

| Command | Status | Duration |
|---|---|---|
| `<cmd-1>` | ✅ pass | 1.2s |
| `<cmd-2>` | ❌ fail (exit 1) | 3.8s |
| `<cmd-3>` | ⏭ skipped | — |
| `<COMMAND from §5.5.2>` | ✅ pass | 28s |

<details>
<summary>Failed: `<cmd-2>` — last 50 lines</summary>

```
<FAIL_TAIL>
```
</details>

_Cached by `github-pr-evaluator`. Do not edit; will be regenerated when HEAD changes._
```

Post the cache comment via `github-ops`, deleting the stale one in the same step if 5.2 found one. Stage the cache-comment body to `/tmp/gh-pr-eval-<N>/health-cache.md` first; `github-ops` reads those bytes through `gh-persist.sh` and posts them directly, so the body never has to travel verbatim through the sub-agent prompt (where compaction or an in-agent Write/Bash race could lose it — the surface that filed empty bodies on the drafter's #626/#627 incident).

> `PERSIST_COMMENT(target=pr, id=<N>, repo=<owner/repo>, body_path=/tmp/gh-pr-eval-<N>/health-cache.md, delete_marker_id=<OLD_CACHE_ID if stale>)`

Capture the resulting comment URL for use in `HEALTH_BODY`. That URL confirms the post landed — don't re-fetch the comment thread or spawn a second `github-ops` call to check it.

Set `HEALTH_BODY`:
- All green: `"Health check: ✅ all green at \`<short-sha>\` (<source>)"`
- Any failure: `"Health check: ❌ failed at \`<short-sha>\` — \`<failing-command>\` ([see cache comment](<comment-url>))"`

Do not post a cache comment when the user opted to skip (5.4 fallback).

### 6. Evaluate PR vs issue

For each issue in `closingIssuesReferences`, evaluate five dimensions. Write your assessment before drafting the verdict — this is where the approve/comment decision gets made.

**Scope match.** Does the diff change what the issue asked to change, and only that? Drive-by edits unrelated to the issue's stated problem are a flag. Small incidental fixes (typos in touched files, missing `Localizable.xcstrings` entries required by the build) are acceptable if called out in the PR body.

**Acceptance criteria / Definition of done.** For features, stories, and incomplete-feature issues, the DoD check has two paths depending on whether the resolver projected per-phase claims onto the issue body (`github-issue-resolver` §9's "DoD projection rule"). Annotation shapes and parser live in [`../_shared/dod-annotations.md`](../_shared/dod-annotations.md) — this skill reads the `closed by ...` ticked forms to drive per-phase verification, and writes the `resolver claimed ... evaluator rejected: ...` sticky-veto un-tick form.

- **Projection annotations present.** When one or more bullets carry a `(closed by phase <N>, commit <short-sha>)` or `(closed by commit <short-sha>)` or `(closed by phase <N>, operator action <ISO-date>)` suffix, **verify each projected tick against its attributed phase's diff** rather than re-judging the whole PR diff per bullet. Use the per-phase verification mechanics below to extract the commit range for each phase from the PR's `## Phase tracker`. A clear semantic mismatch between the attributed diff and the bullet's text → un-tick + soft-reject per "Un-tick on rejection" below. Soft / partial mismatches → flag in the review body but leave the tick in place. A bullet currently unticked and missing an annotation is a gap the resolver should have closed — flag as a planner/resolver coverage gap (the bullet's owning phase per the plan's `closes-dod` is the right place for the user to look). A bullet carrying the predecessor annotation form (`previously claimed by phase <N>, commit <sha> on closed PR #<M>`) — written by the planner during a HARD-path "Start fresh" revise — is treated like a regular `- [ ]`: it's a bullet the current PR still needs to satisfy. The historical attribution is metadata only; the verification target is the current PR's diff.
- **No projection annotations** (the issue predates the projection mechanism, was resolved by an older resolver, the projection failed to land and reconciliation hasn't fired, or the issue carries `## Acceptance criteria` rather than a checkbox DoD). Fall back to the historical behaviour: walk every item in `## Acceptance criteria` or `## Definition of done` and judge it against the diff and test files. An unchecked item that the diff doesn't address is a gap. This is the backwards-compatible path; do not insist on projection annotations as a precondition for evaluation.

In either path, the bullet text itself is the authoritative requirement — annotations are attribution metadata, not part of the requirement.

**Per-phase verification mechanics.** When projection annotations are present, the PR's `## Phase tracker` is the canonical phase → commit mapping. Each tracker entry carries the head-of-phase commit SHA (`- [x] Phase N — title (commit <sha>)`); fixup commits that landed between Phase N's tracker SHA and Phase N+1's tracker SHA belong to Phase N too. Run these inside the §5.5.0 worktree at `.worktrees/<branch>` (already on the PR head):

```bash
# Enumerate every PR commit in branch order (oldest first).
git log --reverse --pretty=format:"%H %s" origin/<base-ref>..HEAD \
  > /tmp/gh-pr-eval-<N>/pr-commits.txt

# For phase N's commit range:
#   PHASE_END = SHA from this phase's `## Phase tracker` entry
#   PHASE_START = SHA from the prior phase's tracker entry, OR the PR base if N == 1
git diff <PHASE_START>..<PHASE_END> > /tmp/gh-pr-eval-<N>/phase-<N>-diff.txt
# Or, for a single-commit phase:
git show <PHASE_END> > /tmp/gh-pr-eval-<N>/phase-<N>-diff.txt
```

Then judge each projected bullet against its phase's diff — same standard the historical path applies to the whole-PR diff, just scoped to the attributed phase. Edge cases:

- **Operator / decision-only phase** (the annotation form is `operator action <ISO-date>` and there is no commit range): the phase ships no diff. There is nothing for the evaluator to verify against — record `verification: operator-phase claim — accepted on faith; verify out-of-band` in the review body for each such bullet, do **not** un-tick. The user is responsible for verifying operator action outputs separately (the marker comment on the issue is the audit trail).
- **Broken SHA reference** (the annotation cites a commit no longer reachable from `HEAD` — force-pushed away during a rebase): flag as `verification: unverifiable — attributed commit <sha> not in branch history`, leave the tick in place. Don't un-tick on a missing reference; that punishes the contributor for unrelated branch hygiene.
- **Single-phase fallback** (annotation form is `(closed by commit <short-sha>)` with no phase number): the whole PR is the phase. Use the whole-PR diff for verification — no per-commit extraction needed.

**Un-tick on rejection.** When per-phase verification finds a clear semantic mismatch (the attributed diff does not implement what the bullet's text requires), un-tick the bullet by replacing its line in the issue body with the sticky-veto form:

```
- [ ] <bullet text> (resolver claimed phase <N>, commit <sha>; evaluator rejected: <one-line reason>)
```

The annotation is the **signal to the next resolver run** that the projection was disputed — the resolver's "DoD projection rule" treats annotated-as-rejected bullets as not-projected, even when `Phase tracker × closes-dod` would tick them. The disagreement is resolved by re-planning (the planner reassigns the bullet to a different phase), by a new code phase whose diff actually satisfies the bullet, or by user intervention. Apply the un-tick atomically: stage the corrected body to `/tmp/gh-pr-eval-<N>/issue-body-corrected.md`, then route through `github-ops`:

> `PERSIST_ISSUE_BODY(id=<issue-#>, repo=<owner/repo>, body_path=/tmp/gh-pr-eval-<N>/issue-body-corrected.md)`

If `PERSIST_ISSUE_BODY` is not available in the local `github-ops` profile, fall back to a direct `gh issue edit <N> --repo <owner/repo> --body-file /tmp/gh-pr-eval-<N>/issue-body-corrected.md` in the main loop. Post the un-tick **before** the PR review (so when a reader follows the review's `## DoD verification` section to the issue, the body already reflects the un-tick). On `gh issue edit` failure, still post the PR review with the un-tick verdict — the next resolver run's §4.7 reconciliation will leave the disputed bullet alone (it can't tell projection-not-applied from un-tick-failed, but in either case the safe behaviour is the same: don't re-tick without new evidence).

**Threshold for un-ticking.** Clear semantic mismatch — the attributed diff fails to implement what the bullet's text plainly requires, judged by the same standard the dimension applies today (LLM judgment against the diff). Soft mismatches, partial satisfaction, or implementations that take a surprising-but-defensible path → flag in the review body, **do not un-tick**. The threshold has to be high; un-ticks propagate to the resolver as sticky vetoes and an over-eager evaluator becomes a per-phase nitpicker that blocks merges on disagreements of interpretation.

**Doc grounding.** Per the project's issue resolver workflow, PR bodies must include a `## Doc grounding` section citing the PRD, Architecture doc, or CLAUDE.md sections that constrained the approach. A missing or vague doc-grounding section is a flag for any non-trivial feature or refactor. (Skip for: one-line bug fixes, pure doc/typo changes, and repos with no docs at all.)

**Plan adherence.** The issue may carry a verified implementation plan authored by `github-issue-planner` and stored as a marker comment — the §3 `GATHER_ISSUE` call already passed `marker_prefix="<!-- implementation-plan:v1 -->"`, so its `marker_comment_url` + `marker_comment_path` are in hand. `Read` the plan body from `marker_comment_path`. (If you skipped that or need a fresh copy, re-run `GATHER_ISSUE(issue=<issue-#>, repo=<owner/repo>, marker_prefix="<!-- implementation-plan:v1 -->", scratch_dir=/tmp/gh-pr-eval-<N>/)`.)

- **Plan present** → check the diff against the plan's *locked decisions* (`## Architecture decisions`, `## Changes`, `## Data model / schema impact`, `## Test plan`). **Don't load the full diff into context** — `diff_path` from §3 points at a file that's often 100+ KB. Read it in targeted slices: first scan the `diff --git a/... b/...` headers (e.g. `Read diff_path` with a small `limit` + `grep` for `^diff --git`, or call `Bash` with `grep '^diff --git ' <diff_path>` to enumerate changed files), pick the files the plan's `## Changes` block names, then `Read` each file's hunk range against the plan one at a time. This keeps the evaluator's context small and lets you compare each diff segment to its plan section in isolation. The plan locks decisions, not lines, so don't flag in-spirit implementation detail that differs harmlessly. But a **reversal of a locked decision** — a different architecture, a moved layer assignment, a data-model shape the plan didn't specify, a missing planned test — that is **not** disclosed (neither flagged + agreed in the plan's `## Deviations`, nor recorded as a `## Plan override` in the PR body) is a **gap → soft-reject (`--comment`)**, quoting the specific decision and the diverging diff. If the resolver was supposed to route a plan-invalidating discovery back to the planner (resolver step 8) and instead worked around it silently, this is exactly the dimension that catches it.
- **Plan absent** → many issues predate the planner, or were trivial enough to skip it. Note "no implementation plan found — adherence not evaluated" in the verdict body and **do not hard-block** on its absence. Only issues that *have* a plan are held to adherence.

**Story / epic context.** If this is a story PR, the base must be `epic/<N>-<slug>` (not `main`), and the PR body must contain the caveat "This story targets the `epic/<N>-<slug>` integration branch and will reach `main` via the integration PR for epic #N." If this is an epic integration PR, the base must be `main`, the head must be `epic/<N>-<slug>`, and the body must include `Fixes #<epic-number>` so GitHub auto-closes the epic on merge.

### 7. Decide the verdict

**Approve** when:
- `HEALTH_OK == true`
- All review dimensions pass (including plan adherence when a plan is present)
- No open `/review` issues remain from the latest run (or no `/review` has run and you've noted it)
- `reviewDecision` is not `REVIEW_REQUIRED` waiting on another specific reviewer

**Comment-rejection** (`gh pr review --comment`) when:
- `HEALTH_OK == false` — **always; this is a hard block.** A red branch never approves regardless of how well the code satisfies the issue. Lead the review body with `HEALTH_BODY`, name the failing command, and link to the cache comment. List any review-dimension gaps below it.
- Any review dimension fails — body lists each gap with the specific evidence that would close it. Use `--comment`, not `--request-changes` — `--comment` is a soft signal; `--request-changes` blocks merge and is heavy-handed for this workflow. Only switch to `--request-changes` if the user explicitly asks for a hard block.
- **Per-phase DoD verification un-ticked one or more projected bullets.** A sticky veto is a soft-reject regardless of whether other dimensions pass — the issue's DoD record now reflects the dispute, and the resolver needs to address it (re-plan, ship satisfying code, or surface for user resolution) before another approval pass.

**`## DoD verification` body section.** When the DoD dimension fired per-phase verification (annotations were present), include a `## DoD verification` section in the review body. Omit the section entirely when no per-phase verification ran (the historical-path issue) or when every projected tick verified clean and there is nothing to surface. Per un-ticked bullet, emit:

```markdown
- **Bullet <index>** — <verbatim bullet text>
  - **Resolver claimed:** phase <N>, commit `<short-sha>`
  - **Evidence:** <file:line range or short diff excerpt showing the mismatch>
  - **Why rejected:** <one-sentence rationale>
```

When the section is present but every projected tick verified clean (rare — keep this case in mind for callers who want explicit confirmation), include a single line `All <K> projected DoD ticks verified against their attributed phase diffs.` instead of the per-bullet block. Don't surface operator-phase bullets here unless the verdict turns on them — the `verification: operator-phase claim — accepted on faith` note belongs in the bullet-walkthrough body, not the verification summary.

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

Close with one short line setting expectations for what happens after the review posts, derived from the §12 branch table:
- Standard or story PR, APPROVE, `mergeStateStatus` not in {DIRTY, BLOCKED} → "I'll auto-merge with `<strategy>` after the review posts."
- Epic integration PR, APPROVE → "I'll ask you to confirm the merge mode after the review posts."
- APPROVE but `mergeStateStatus` ∈ {DIRTY, BLOCKED} → "Merge skipped — `<DIRTY | BLOCKED>`. I'll print the command for you to run after resolving it."
- COMMENT (soft-reject) → "No merge — fix the gaps above and re-evaluate."

Don't restate the recommended strategy or the squash subject already shown above; one line is enough. Then proceed directly to step 11.

### 11. Post the review

Stage the review body to `/tmp/gh-pr-eval-<N>/review.md`, then hand the path to `github-ops` with the `review_action` set by the verdict (§7) and the §2 self-approval check. Same path-based contract as §5.6: the body posts byte-for-byte from disk via `gh-persist.sh`, never through the sub-agent prompt.

> `PERSIST_COMMENT(target=pr-review, id=<N>, repo=<owner/repo>, body_path=/tmp/gh-pr-eval-<N>/review.md, review_action=<approve | comment | request-changes>)`

`review_action=approve` for an approval; `comment` for a soft-rejection **or** when the §2 self-approval pre-check flagged that you authored the PR (GitHub rejects self-`--approve` with 422 — the body stays identical, only the action changes). `github-ops` returns the review URL plus `body_bytes` / `body_sha256`; share the URL with the user.

**Flip the PR back to draft on a real COMMENT verdict.** When §7's verdict was COMMENT-REJECTION (any of: `HEALTH_OK == false`, a dimension failed, the per-phase DoD un-tick fired) — *not* when `review_action=comment` was the §2 self-approval downgrade of an APPROVE verdict — flip the PR back to draft immediately after the review post:

```bash
gh pr ready <N> --repo <owner/repo> --undo
```

This is the other half of the handoff contract with `github-issue-resolver` (which flips ready before its forward handoff on the §11 *last planned phase shipped* row; see `github-issue-resolver` SKILL.md §11, the *last planned phase shipped* row). On the soft-reject path the PR's signal should be "not ready for re-review until the gaps land," which on GitHub is the `draft` state. Leaving the PR ready after a soft-reject forces the resolver's §5 existing-PR check to surface it as drift to the user every re-entry — exactly the noise the contract avoids. The §2 self-approval downgrade is the explicit exception: the verdict was APPROVE, the PR is approval-equivalent, and it should stay ready for the manual merge.

This flip is best-effort: if `gh pr ready --undo` fails (e.g., the PR was already in draft because the user beat the evaluator to it), log the failure and continue — the §15 handoff carries the canonical state for the next session.

**Issue-body un-ticks (DoD verification path).** When per-phase verification un-ticked one or more bullets (§6 "Un-tick on rejection"), apply the un-ticks to the issue body **before** posting the PR review. The order matters: a reader who follows the review's `## DoD verification` section to the issue should see the un-tick already in place. Stage the corrected body to `/tmp/gh-pr-eval-<N>/issue-body-corrected.md`, then either route through `github-ops` if `PERSIST_ISSUE_BODY` is available, or fall back to a direct `gh issue edit <N> --repo <owner/repo> --body-file /tmp/gh-pr-eval-<N>/issue-body-corrected.md` from the main loop. If the issue-edit fails, still post the PR review — the verdict is the load-bearing signal and the next resolver run's §4.7 reconciliation respects un-ticks via the same sticky-veto rule whether or not the body itself was updated this time. Surface the issue-edit failure in the review body so the user can re-apply it manually.

### 12. Run the merge

After the review posts, branch on PR type, verdict, and merge-readiness. The verdict at this point is already known from §7; only APPROVE verdicts proceed to a merge attempt (COMMENT soft-rejections stop here — see 12c). Never use `--auto`.

The matrix:

| PR type | Verdict | `mergeStateStatus` | Behaviour |
|---|---|---|---|
| Standard / Story | APPROVE | not in {DIRTY, BLOCKED} | **12a. Auto-merge** — run the recommended `gh pr merge` directly. No prompt. |
| Epic integration | APPROVE | not in {DIRTY, BLOCKED} | **12b. Confirm** — keep the explicit `AskUserQuestion` gate. |
| Standard / Story / Epic integration | APPROVE | DIRTY or BLOCKED | **12c. Skip with command** — print the recommended command and stop. |
| Any | COMMENT (soft-reject) | any | **No merge** — already enforced by §7 producing a `comment` review action; nothing runs in §12. Jump to §14's "merge did not run" summary. |

Self-authored APPROVE PRs (review posted as `--comment` per §7) still take the APPROVE branches above — the verdict is approval-equivalent; only the review action differed.

#### 12a. Auto-merge (standard / story, APPROVE, mergeable)

Print one line so the user sees the command in the transcript before invocation, e.g.:

> Running merge: `gh pr merge 143 --repo owner/repo --squash --subject "fix: …" --body-file /tmp/gh-pr-eval-143/squash-body.md --delete-branch`

Then run the recommended command directly. Story PRs and standard PRs both squash today (§8's strategy table); the command is the same `--subject` / `--body-file` form as before:

```bash
gh pr merge <N> --repo <owner/repo> --squash \
  --subject "<composed squash subject>" \
  --body-file /tmp/gh-pr-eval-<N>/squash-body.md \
  --delete-branch   # append only if delete_branch_on_merge is false
```

On non-zero exit: surface the `gh` output to the user and stop. Do **not** proceed to §13 (story-issue close / epic checkbox) or §14 (worktree cleanup) — the PR is still mergeable and the user may want to re-invoke after addressing whatever failed. The worktree stays in place exactly as it would if the user had declined the merge.

#### 12b. Confirm (epic integration, APPROVE, mergeable)

Epic integration PRs land the accumulated diff of every child story onto `main` in one merge — a qualitatively different risk surface than a single-issue PR. Keep the explicit gate so the user can take one last look at the merged history before it ships.

Ask via a single `AskUserQuestion` (`header: "Merge mode"`; question text: "Merge PR #\<N\>? I recommend the mode below for this PR.") with these options, recommended-mode-first:

- **Merge commit** — preserves all story squash commits as distinct entries in `main`'s history (default for epic integration with `commits.totalCount > 1`).
- **Squash** — description carries the composed subject. Use when the epic collapsed to a single commit (rare but possible — §8 detects this).
- **Don't merge yet** — post nothing further; leave the PR mergeable for the user to land later.

The chosen option determines which command runs.

If the user chooses **Merge commit**:

```bash
gh pr merge <N> --repo <owner/repo> --merge \
  --delete-branch   # if delete_branch_on_merge is false
```

If the user chooses **Squash**:

```bash
gh pr merge <N> --repo <owner/repo> --squash \
  --subject "<composed squash subject>" \
  --body-file /tmp/gh-pr-eval-<N>/squash-body.md \
  --delete-branch   # if delete_branch_on_merge is false
```

If the user chooses **Don't merge yet**: skip ahead to §14's "If the merge did not run" branch.

#### 12c. Skip with command (APPROVE but DIRTY or BLOCKED)

The branch can't merge in its current state, so auto-invoking `gh pr merge` would just emit a noisy failure. Print the recommended command for the user to run after resolving the blocker, name the blocker (`DIRTY` → conflicts to resolve; `BLOCKED` → branch protection check to satisfy), then stop. Do **not** proceed to §13 or §14's cleanup — like 12a's failure path, the worktree stays in place so the user can resolve the blocker and retry.

Temp files from steps 11–12 are cleaned up after use (or left in place for the 12a-fail / 12c paths so a retry can reuse them).

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
mkdir -p "/tmp/gh-pr-eval-<N>"
gh issue view <epic-N> --repo <owner/repo> --json body --jq .body > /tmp/gh-pr-eval-<N>/epic-body-current.md
```

Find the `- [ ] #<story-number>` line in `## Stories` and replace it with `- [x] #<story-number>`. Show the user the diff, then run immediately:

```bash
gh issue edit <epic-N> --repo <owner/repo> --body-file /tmp/gh-pr-eval-<N>/epic-body-updated.md
```

Clean up temp files after. If the checkbox is already `[x]` (another tool beat us to it), note it and skip the edit.

### 14. Clean up and summarise

"Merge ran" here covers both the §12a auto-merge path and the §12b confirmed-merge path — the cleanup logic is shared. The §12a-failure path, the §12c skip path, and the §12b "Don't merge yet" choice all fall into the "merge did not run" branch below.

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

3. **Delete the per-run scratch directory**: `rm -rf "/tmp/gh-pr-eval-<N>"` (it holds the squash body, the epic-body working copies, and the health logs). (The review-body and health-cache temp files are written and removed inside `github-ops`, not here.)

Then end the run with the Step 15 Handoff block (next section) — the handoff is the closing structured summary, replacing the bullet-list summary previously emitted here. The handoff's `Cleanup:` line carries the substantive subset (worktree teardown outcome, removal, scratch-dir status); the URLs of the review, the merge commit, the closed story issue, and the ticked epic checkbox flow into earlier output as they're produced (§11, §12, §13) and don't repeat in the handoff.

**If the merge did not run** (user declined in step 12, or §12c skipped on DIRTY/BLOCKED, or §7 produced a COMMENT verdict), still end the run with the Step 15 Handoff. The handoff's `Cleanup:` line is **omitted** (the worktree stayed in place); the `Next:` action shifts per the §15 rubric — for §12c skips and user-declined merges the handoff carries the manual `gh pr merge` command for the user to run after the blocker resolves; for soft-rejections the handoff re-routes to `github-issue-resolver continue #<N>`.

### 15. Handoff

Every clean run of the evaluator ends with a single `## Handoff` block — the schema, omission rules, and state-marker vocabulary live in [`../_shared/handoff-format.md`](../_shared/handoff-format.md). The handoff is the only bridge between this session and the next; it replaces §14's previously-inlined bullet-list summary. Don't emit both.

Pull the snapshot from data already in hand: the §3 `GATHER_PR` payload (issue/PR numbers, titles, base ref), the §5.5 / §5.6 cache-comment results (`HEALTH_OK`, `<short-sha>`, `TIER`), §7's verdict (`APPROVE` or `COMMENT`), §12's merge command and outcome (target ref + resulting commit SHA when the merge ran, the failure reason when it didn't), and §14's worktree teardown / removal results. The `Why:` line is judgment — describe what the next session does, or for terminal endings, why the pipeline ends here.

**Before composing the handoff, `Read references/handoff-renderings.md`** — it holds the outcome→rendering rubric and the worked `## Handoff` shapes the evaluator emits: standard-PR terminal merge, story-merged (more stories pending / last sibling → Epic integration), epic-integration terminal, soft-reject re-route to the resolver, and approve-but-merge-skipped (DIRTY/BLOCKED or user-declined). It's a progressively-disclosed reference — not auto-loaded with this skill — and this SKILL.md exceeds the default Read cap, so the forced Read is what guarantees the rubric is in your working context regardless of where the initial load truncated; without it the handoff may be emitted from memory and drift from the closed-set shapes. Each shape carries the closed-set state-marker vocabulary from [`../_shared/handoff-format.md`](../_shared/handoff-format.md); fill the snapshot from the data §15 lists above.

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
5. Walk every item in `## Definition of done` and judge it against the accumulated diff. Unfulfilled items → rejection. Epic integration uses the historical "walk every item" path — not the per-phase verification path. Per-phase DoD projection lives on the **child story** issues (each child story's resolver run projects its own per-phase ticks onto the story body), so by integration time the child story DoDs are already mostly ticked there. The epic body's DoD tracks epic-level outcomes; it's reconciled by the resolver's epic-integration close-out batch flip after this PR merges (`github-issue-resolver` §676–679). The evaluator's job here is to verify the accumulated diff actually satisfies those epic-level bullets, not to verify per-phase projections.
6. Strategy: merge commit (if `commits.totalCount > 1`), squash (if single commit).
7. This PR carries more risk than a story PR — it lands the entire epic on main at once. Hold approval if DoD is incomplete or if the diff contains unexpected changes. Ask before proceeding if uncertain. The merge gate in §12 also stays explicit for epic integration PRs even on a clean APPROVE — see §12b. This is the only PR type where the evaluator still asks before merging.

---

## Common pitfalls

- Don't approve when `HEALTH_OK == false` — health-check failure is a hard block regardless of how well the PR satisfies the issue. The branch must be green before any approval.
- Don't run the full canonical suite for every PR. Targeted selection is the default; the full suite is reserved for epic-integration PRs (where the diff *is* the integration risk surface) and PRs flagged by the project's `<!-- pr-evaluator-escalation-labels -->` block. CI on the integration target is the broader safety net for anything targeted misses; lean on it rather than re-running the whole suite locally for every story PR.
- Don't run targeted selection for an epic-integration PR. The diff vs `main` is the union of all child stories — exactly the integration risk this gate exists to verify. Targeted there would miss cross-story interactions. The sub-agent's escalation rules already enforce this; don't override them.
- Don't trust a targeted run alone for cross-cutting changes. When the sub-agent invokes a `broad-change-fallback` or returns "all unit tests" with UI deferred, that's a signal: check whether CI on the integration target is green at this SHA. If CI hasn't run or is red, surface that to the user and prefer the full canonical suite. The `RATIONALE:` line is your audit log — read it.
- Don't let `apple-platform-build-tools:builder` expand scope. When delegating in §5.5.3, the prompt MUST explicitly bound the subagent to "run the command and report result." A build subagent that silently edits source files to fix a failure it diagnosed turns `HEALTH_OK=true` into a lie (the cache comment will say green, but the green came from changes the user never saw), uncaps the wall-clock cost of one delegation, and produces edits that don't appear in any commit on the PR. Failures bubble back; the calling skill decides what to do.
- Don't attempt destructive recovery when tests fail. §5.5.3 prescribes the only correct response to a non-zero test exit: set `HEALTH_OK=false`, capture the last 50 lines as `FAIL_TAIL`, and write the cache comment. Do not try to "fix" a failing run by erasing the simulator (`xcrun simctl erase`), wiping the booted device, deleting the app's data container with `rm -rf`, uninstalling apps from shared simulators, killing CoreSimulator processes, or otherwise mutating shared infrastructure the test wrapper depends on. Recovery actions of that shape almost always target the *wrong* resource — the global default simulator picked up by the wrapper's fallback when the per-worktree state file is missing, not the per-worktree one the gate is supposed to be running against — and surface to the user as data loss on a sim they were using for something else. If the gate fails because of stale environmental state, the right outcome is to record the failure faithfully; the user (or the next `github-issue-resolver` run) decides what to clean up.
- Don't re-verify a `github-ops` write. `PERSIST_COMMENT` (the §5.6 cache comment, the §11 review) returns the canonical URL on success — that *is* the confirmation. Re-fetching the comment thread (`gh api …/comments`, `gh pr view … --json comments`) or spawning a second `github-ops` call to "check it posted" burns context and tokens for nothing. A tool result that seems slow is buffered, not lost — wait, don't probe.
- Don't approve a PR whose latest `/review` run left unresolved flagged issues — cite them in the rejection body.
- Don't recommend rebase for this project — it's allowed but unused. Squash is the grain; go with it.
- For standard and story PRs with an APPROVE verdict, the merge runs automatically after the review posts (§12a) — the verdict itself is the approval, and §10 has already shown the recommended strategy and the composed squash subject. The explicit `AskUserQuestion` gate is reserved for epic integration PRs (§12b — where the diff is the accumulated work of every child story landing on `main` at once) and for any PR with `mergeStateStatus ∈ {DIRTY, BLOCKED}` (§12c — where auto-merging would just produce a noisy gh failure). Once a merge runs, cleanup (worktree removal, story-issue close, epic checkbox) follows automatically without asking again.
- Don't compose a squash subject with a double `(#NN)` suffix. Strip any trailing ` (#\d+)` from the PR title before appending `(#<pr-number>)`.
- Don't post `--approve` for a self-authored PR — GitHub will 422. Use `--comment` with the same body.
- **Don't un-tick a DoD bullet on a soft mismatch.** The un-tick annotation is a sticky veto that propagates to the resolver's projection logic — once the body shows `- [ ] <text> (resolver claimed phase <N>, ...; evaluator rejected: ...)`, no subsequent resolver run will re-tick the bullet on a normal push. Use the un-tick **only** when the diff in the attributed commit(s) clearly fails to satisfy the bullet's stated requirement, judged by the same standard the dimension applies today. Partial satisfaction, implementations that take a surprising-but-defensible path, and disagreements of interpretation get flagged in the review body — not un-ticked. An over-eager evaluator un-ticking on every reading disagreement turns the sticky veto into a merge-blocker for normal review back-and-forth.
- **Don't infer per-phase verification when the issue carries no projection annotations.** The fallback "walk every item against the diff" path is the right call for unticked bullets on pre-projection issues, single-phase issues that ran an older resolver, or issues whose first push's projection-edit failed and reconciliation hasn't fired. Don't synthesize annotations from `## Phase tracker` + `closes-dod` ad-hoc just to drive a per-phase verification — the resolver projects deliberately, and the evaluator's absence-of-annotation read is the backwards-compat signal. Inferring annotations turns the verification path into a parallel projection authority, which breaks the resolver/evaluator boundary in the other direction.
- Don't block approval over `mergeStateStatus == BEHIND` or `DIRTY` — approve on code merit and surface the merge-readiness blocker separately.
- Don't use `--request-changes` unless the user explicitly asks for it — `--comment` is the project default for soft rejections.
- Don't skip the doc-grounding check for features and stories — it's load-bearing for traceability.
- Don't recommend a strategy the repo doesn't allow — always clamp to the `allow_*` fields.
- Don't skip the draft-PR guard — evaluating a draft produces a confusing review that may mislead the author. The guard is also the load-bearing half of the handoff contract with `github-issue-resolver`: the resolver flips ready before its forward handoff so this guard doesn't fire on the canonical path; a draft reaching here means in-progress work, not a missed handoff.
- Don't skip §11's draft-flip on a real COMMENT verdict. Leaving the PR ready after a soft-reject signals "ready for review" on GitHub while the actual signal is "needs more work" — and the resolver's §5 existing-PR check then has to surface it as drift to the user every re-entry. Flip back to draft (`gh pr ready <N> --undo`) so the resolver picks up cleanly. The §2 self-approval downgrade is the exception: that's an APPROVE in COMMENT clothing; the PR stays ready for the manual merge.
- Don't try to approve a PR that has `reviewDecision == REVIEW_REQUIRED` waiting on a named reviewer unless the user confirms. The approval will post, but it may confuse the pending reviewer.
- Don't use `--auto` — the repo has `allow_auto_merge: false`.
- Don't conflate issue-fit and code-quality. Issue-fit (this skill) asks "did the PR deliver what the issue asked for." Code quality (`/review`) asks "is this code well-written." Both are necessary; neither substitutes for the other.
- Don't approve a PR that silently deviates from a stored plan. If the issue has a `github-issue-planner` plan and the diff reverses a locked decision without disclosing it (no `## Deviations` entry on the plan, no `## Plan override` in the PR body), that's a soft-reject — quote the decision and the diverging diff. Harmless in-spirit detail differences are fine; the plan locks decisions, not lines.
- Don't require a plan on issues filed before the planner existed, or on trivial fixes. Plan adherence only binds issues that *have* a plan comment. Absence is noted, never a hard block.
- Don't rely on `Fixes #<story-number>` to auto-close a story issue — story PRs merge into `epic/<N>-<slug>`, not `main`, so GitHub records the linkage but never fires the close. Step 13 closes the story issue explicitly.
- Don't silently write any of the three configuration blocks (`<!-- pr-evaluator-static-checks -->`, `<!-- pr-evaluator-test-target -->`, `<!-- pr-evaluator-escalation-labels -->`) to `COMMANDS.md` / `CLAUDE.md` — always ask the user for confirmation before modifying project files.
- Don't run worktree-teardown when the merge didn't run. Teardown is paired with worktree removal; if the worktree stays, teardown stays deferred. The user will either re-invoke the evaluator (which retries the merge → cleanup pair) or run the manual cleanup sequence (`github-issue-resolver` §11) themselves. Running teardown without removing the worktree leaves a worktree whose resources have been released — tests started from there would silently fail against missing dependencies.
- Don't `git worktree remove` before running worktree-teardown. The teardown commands live inside the worktree — for example, `./scripts/worktree-teardown.sh` is a script in the repo, so once the worktree is removed, the script is gone too and any per-worktree resources it would have released (simulators, containers, ports, scratch databases) become orphans the user has to clean up by hand. §14's step order is load-bearing: step 1 (teardown) must complete — or be confirmed as no-op because no `<!-- worktree-teardown -->` block is declared — before step 2 (worktree removal) can run.
- Don't fail the cleanup step if teardown fails. Teardown is best-effort: log the failure and continue to `git worktree remove`. A leaked resource is recoverable (the user can find and clean it up manually); a stuck worktree blocks future runs against the same branch.

## When to ask the user

- The PR has multiple `closingIssuesReferences` and their acceptance criteria conflict (e.g., one issue wants X, another wants not-X).
- The latest `/review` run flagged issues that look unaddressed — call `AskUserQuestion` (`header: "Open review"`) with options **Hard rejection** (treat the unresolved `/review` points as a blocking soft-reject) / **Note + proceed** (cite them in the verdict body but don't block).
- The composed squash subject's inferred `<type>` is ambiguous (issue labels and PR title disagree, or neither carries a Conventional-Commits prefix).
- The PR is an epic integration PR and one or more `## Definition of done` items aren't evidently satisfied by the diff.
- `reviewDecision == REVIEW_REQUIRED` and it's owed to a specific reviewer who hasn't acted — call `AskUserQuestion` (`header: "Reviewer"`) with options **Proceed anyway** (post your approval now; merge may still be gated on the named reviewer) / **Wait for reviewer** (hold off until the named reviewer acts).
- The PR has no `closingIssuesReferences` — call `AskUserQuestion` (`header: "Issue link"`) with options **Name the issue** (use the auto-appended "Other" free-text choice to type the issue number this PR addresses, then run the scope evaluation against it) / **Intentionally standalone** (no origin issue — e.g. a chore or doc update; skip the scope-against-issue check).
- Branch protection returns something other than 403 that suggests a stricter-than-expected merge policy.
- Neither a `<!-- pr-evaluator-static-checks -->` nor a legacy `<!-- pr-evaluator-health-checks -->` block is found in `COMMANDS.md` / `CLAUDE.md` — ask which commands to run (or whether to skip).

## Repo health-check declaration

A repository declares the gate's behaviour through three marker-delimited blocks in `COMMANDS.md` or `CLAUDE.md` (or any file either `@`-includes that is reachable from the repo root). All three are invisible in rendered Markdown.

**1. Static checks** (`<!-- pr-evaluator-static-checks -->`) — fail-fast list of always-run hygiene. Runs first at every gate. Commands use repo-root-relative paths; the skill `cd`s into the branch worktree before invoking each.

```markdown
<!-- pr-evaluator-static-checks -->
- `<command>` — <description>
- `<command>` — <description>
<!-- /pr-evaluator-static-checks -->
```

**2. Test target** (`<!-- pr-evaluator-test-target -->`) — configuration for the test-selection sub-agent (see §5.5.2). Prose-structured Markdown. Declares the test wrapper, the `full-suite-command` used when escalation rules trigger, and per-target naming conventions and fallback rules.

```markdown
<!-- pr-evaluator-test-target -->
- wrapper: `<test-runner command>`
- full-suite-command: `<full canonical suite command>`
- targets:
  - `<TargetName>` (unit | UI)
    - naming: <how source files map to suite identifiers>
    - helpers-fallback: <command, or "none">
    - broad-change-fallback: <command, or "none">
<!-- /pr-evaluator-test-target -->
```

**3. Escalation labels** (`<!-- pr-evaluator-escalation-labels -->`) — list of GitHub PR labels that force the full-suite command. Empty or absent block = no label-based escalation.

```markdown
<!-- pr-evaluator-escalation-labels -->
- `full-suite-required` — <description>
- `pre-release` — <description>
<!-- /pr-evaluator-escalation-labels -->
```

**Example** (food-journal):

```markdown
<!-- pr-evaluator-static-checks -->
- `./scripts/check-layer-imports.sh` — Layer-import boundary lint (fast, <5s)
- `CI=1 ./scripts/run-swiftlint.sh` — SwiftLint in CI strict mode
<!-- /pr-evaluator-static-checks -->

<!-- pr-evaluator-test-target -->
- wrapper: `./scripts/xcb.sh`
- full-suite-command: `./scripts/xcb.sh`
- targets:
  - `FoodJournalTests` (unit)
    - naming: source `<X>.swift` ↔ `FoodJournalTests/<X>Tests.swift`; suite identifier `FoodJournalTests/<X>Tests`.
    - helpers-fallback: `./scripts/xcb.sh -only-testing FoodJournalTests`
    - broad-change-fallback: `./scripts/xcb.sh -only-testing FoodJournalTests`
  - `FoodJournalUITests` (UI)
    - naming: flow-oriented; map by symbol references and `@testable import`.
    - helpers-fallback: `./scripts/xcb.sh -only-testing FoodJournalUITests`
    - broad-change-fallback: none
<!-- /pr-evaluator-test-target -->

<!-- pr-evaluator-escalation-labels -->
- `full-suite-required` — bypass targeted selection
<!-- /pr-evaluator-escalation-labels -->
```

Order in static-checks matters: put fast commands first so the sequence fails quickly on simple errors without waiting for a multi-minute build.

**Legacy single-block declaration.** Older projects still declare a single `<!-- pr-evaluator-health-checks -->` block containing both static checks and the test invocation as a flat command list. The skill detects this and runs the legacy block as-is (full suite every time), skipping the test-selection sub-agent. This keeps un-migrated projects working, but loses the targeted-selection benefit; offer to migrate when convenient.

The cache comment (posted by §5.6) uses the marker `<!-- pr-evaluator-health-cache:v1 -->` and is keyed to the PR HEAD SHA. It records `TIER: targeted | full` so a re-evaluation can tell what kind of run produced the cached result, and a `**Selection reasoning:**` block with the §5.5.2 sub-agent's verbatim `RATIONALE:` so post-mortems can audit *why* a given run was scoped the way it was. The cache is updated automatically whenever HEAD changes; do not edit it manually.
