---
name: github-issue-resolver
description: Investigate and resolve a specific GitHub issue end-to-end via the `gh` CLI. Trigger when the user gives an issue number/URL or asks to "look at", "work on", "fix", "implement", "resolve", "triage", or "respond to" an issue — bugs, features, questions, or refactors. Reads the issue and its full comment thread (separating stale early discussion from latest decisions), checks for existing open/draft/prior PRs to avoid trampling in-progress work, decides the response type, does the work, and posts a comment or opens a PR. For code changes, opens or continues a PR and loops with the `review` skill until approved. Reads `docs/prd.md`, `docs/architecture.md`, and `CLAUDE.md` to ground implementations. Recognises epics (long-lived `epic/<N>-<slug>` integration branch, child-story audit, integration PR) and stories under an open epic (PR base = epic branch). Use even on casual mentions ("look at #423?", "what is left in the auth epic?") — don't handle GitHub issues without it.
---

# GitHub Issue Resolver

Resolve a GitHub issue by reading it carefully, doing the right kind of work for the issue type, and reporting back.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status` to check)
- Working directory is the repo the issue belongs to, OR the user has specified `--repo owner/name` context
- For code-change issues the skill works inside a `git worktree` at `.worktrees/<branch-name>/` in the repo (see next section). Cleanup is the user's job.

If `gh` isn't authenticated, stop and tell the user — don't try to work around it.

## Working in a worktree

For any code-change issue, the skill works inside a `git worktree` rather than the main checkout. This lets multiple issues stay in flight at once — each branch lives in its own working tree, builds and tests run independently, and the main checkout stays untouched on whatever branch you had open before.

**Where they live.** `.worktrees/<branch-name>/` inside the repo. Before creating the first worktree, ensure `.gitignore` contains a `.worktrees/` line — append it if missing (small, idempotent edit; never remove anything else). Without that entry every worktree's files show up as untracked in the main checkout's `git status`.

**The worktree is the working directory.** Once a worktree is created or reused, `cd .worktrees/<branch-name>` is the cwd for every subsequent command in this skill run — baseline tests in step 7, edits in step 8, `git add/commit/push` and `gh pr create` in step 9, the review loop in step 10. State the path explicitly when you switch so the user can follow along (and run their own commands in the same place).

**Reuse rule.** Before any `git worktree add`, run `git worktree list --porcelain` and check whether the target branch is already checked out somewhere. If it is, `cd` to that path and continue — don't try to add it again (git will error) and don't recreate it. The existing worktree is the source of truth.

**Nesting guard.** If `git rev-parse --git-dir` shows a path under `.git/worktrees/`, the skill is already running inside a worktree. Don't nest. Find the main working tree (the first `worktree` entry in `git worktree list --porcelain`) and run `git worktree add` with paths relative to that main tree's root.

**Setup hook on creation.** After every `git worktree add` succeeds, run the project's worktree-setup commands (see "Worktree setup & teardown commands" below). On reuse, skip them — they already ran at creation time.

**Cleanup is manual.** The skill never runs `git worktree remove`. A worktree may hold unpushed commits or in-flight edits, and tearing it down silently would lose work. When the user is done with an issue they run `git worktree remove .worktrees/<branch-name>` themselves (preceded by the project's worktree-teardown commands, if any are declared). Step 11 reminds them; that's all.

**Comment-only responses skip this entirely.** Questions, blocked issues, duplicates, and other no-code responses don't need a worktree — there's no branch to host. Skip directly to drafting the comment.

## Worktree setup & teardown commands

Worktrees give every issue a sandboxed checkout, but some projects also need per-worktree resources the worktree itself can't carry: an isolated iOS Simulator, a free localhost port, a scratch database, a cache directory keyed to the branch. Without lifecycle hooks the project would have to wedge that work into individual test commands — fragile and easy to forget. With hooks the project declares setup and teardown commands once and the skill runs them at the right moments. The skill stays opaque to *what* the commands do — that's the project's concern. It only guarantees they run inside the worktree at the right point in the worktree lifecycle.

**Where the commands live.** A project declares hooks via two marker-delimited blocks in `COMMANDS.md` (preferred) or `CLAUDE.md`:

```markdown
<!-- worktree-setup -->
- `<command>` — <description>
- `<command>` — <description>
<!-- /worktree-setup -->

<!-- worktree-teardown -->
- `<command>` — <description>
<!-- /worktree-teardown -->
```

Format matches the other list-style command blocks (`issue-resolver-fast-checks`, `pr-evaluator-static-checks`): one Markdown list entry per command, backtick-quoted command followed by ` — ` and a short human description. Order matters — commands run in declaration order. **Setup is fail-fast** (the first non-zero exit stops the run); **teardown is best-effort** (a failure is logged but doesn't block subsequent teardown commands or the worktree removal that follows).

**Discovery.** Scan `COMMANDS.md` and `CLAUDE.md` at the repo root, plus any file `@`-included from either and reachable from root. If neither block is present, the corresponding phase no-ops silently — many projects won't need either hook, and the skill should not warn or prompt about their absence.

**When setup runs.** Immediately after a `git worktree add` returns success — *only* on the create arm of every worktree decision in this skill (§5 takeover, §8 fresh branch, the epic-bootstrap and legacy-recovery flows in "If the issue is an Epic", and the story-worktree creation in "If the issue is a Story"). Skip on the reuse arm; reused worktrees are already set up. Run each setup command from inside the worktree (`cd .worktrees/<branch>` first), in declaration order, fail-fast. On failure, surface the failing command and the last 50 lines of its output and stop the workflow — the worktree exists but isn't ready for tests, and silently proceeding would mean running against a missing resource.

**When teardown runs.** This skill never removes worktrees, so it never runs teardown directly. The hook is documented here for symmetry; the executor is `github-pr-evaluator` §14 (the only place a worktree is removed automatically). Step 11's manual-cleanup reminder names the teardown commands and `git worktree remove` together so users running cleanup outside the evaluator know the sequence.

**What setup commands typically do.** Provision per-worktree resources and persist any state the rest of the workflow needs. The skill does not interpret that state — projects use whatever mechanism fits. Common patterns: write a `<worktree>/.worktree-state/<key>` file the project's other commands read; allocate a free port and export it via a `.envrc`; provision a scratch container and record its name. Make setup idempotent against a half-failed prior run so the user can re-trigger without orphan resources.

**What teardown commands typically do.** Release the resources setup created. Read the same state and tear them down. Idempotent and tolerant of missing state — teardown may run on a worktree whose setup partially failed, or which the user has already cleaned up manually.

**Status line announcements.** Setup: *"Running worktree setup (N command(s))…"* before the first command; *"Worktree setup complete."* on full pass; *"Worktree setup failed at step i: `<command>`"* with the output tail on failure. Reuse: silent — the absence of a setup announcement is itself the signal that the worktree was reused. Teardown (executed by the evaluator, but the convention is shared): *"Running worktree teardown (N command(s))…"* / *"Worktree teardown complete."* / *"Worktree teardown step i failed: `<command>`"* — log and continue to the next command.

**No stamp file needed.** The skill ties setup to the worktree-creation event, not to a persistent stamp on disk. If the user manually re-runs setup on a reused worktree (e.g., to recover a lost resource), that's their call — the skill doesn't track it.

## Test selection during iteration

§7 baseline runs the project's static-checks block. **§8 (after the first round of code changes, before the first push) and every §10.6 iteration (after addressing review feedback, before the next push)** run the static-checks block followed by a Claude-selected set of test suites scoped to the diff vs the integration target — this is the **pre-push verification gate** described below. Both gates are mandatory before a push; never push code without one of them having run green. The full canonical suite (every unit test + every UI test) is **not** run inside this skill at any gate. The point of this design is fast feedback during development: a one-Service edit should run that Service's tests, not a 10-minute UI suite.

The full canonical suite still runs in two places outside this skill: **CI on the integration target** (the authoritative answer to "is `main` / the epic branch green?") and **`github-pr-evaluator`** for epic-integration PRs and PRs flagged by the project's escalation-labels block. Pr-evaluator now also runs targeted selection for ordinary story and bug-fix PRs — so don't assume "pr-evaluator will catch it" for cross-cutting changes; CI is the broader safety net.

The bug this design avoids: if the test gate lived only inside §10.6, a clean first-pass review approval (review approves without requesting changes) would skip §10.6 entirely and a PR would land with zero tests run beyond static checks. §8 closes that gap.

**These conventions apply only when step 7 applies.** Comment-only flows (questions, blocked issues, duplicates, doc/typo edits) skip steps 7/8/10/11 entirely and use none of this.

### Two project-side blocks the skill reads

```markdown
<!-- issue-resolver-fast-checks -->
- `<command>` — <description>
...
<!-- /issue-resolver-fast-checks -->

<!-- issue-resolver-test-target -->
- wrapper: `<test-runner command>`
- targets:
  - `<TargetName>` (unit | UI)
    - naming: <how source files map to suite identifiers>
    - helpers-fallback: <command, or "none">
    - broad-change-fallback: <command, or "none">
  - ...
<!-- /issue-resolver-test-target -->
```

Both blocks are delimited by HTML comments (invisible in rendered Markdown) and are discovered by scanning `COMMANDS.md` and `CLAUDE.md` at the repo root, plus any file `@`-included from either.

- **`issue-resolver-fast-checks`** = a fail-fast list of static commands (codegen, dependency resolution, lints, layer-import boundary checks, etc.). One Markdown list entry per command, backtick-quoted, followed by ` — ` and a short description. **No test invocations belong in this block** — tests are handled separately by the test-target block below.
- **`issue-resolver-test-target`** = configuration for the test-selection sub-agent (see next section). Prose-structured Markdown — read it as natural language; don't try to parse it.

Read both blocks once at the start of step 7 and remember them for the rest of the run.

**Backward compatibility.** If `issue-resolver-test-target` is absent but `issue-resolver-fast-checks` contains an inline test invocation (older convention), run that block as a flat command list and skip the selection step. Many projects haven't yet split the two; the skill should still work.

If neither block is present, fall back to the `pr-evaluator-static-checks` block for static checks (or the legacy `pr-evaluator-health-checks` block if that's all that exists) at the gates where tests are needed (§8 and §10.6 — §7 stays static-only). This is the worst case, but it preserves correctness on projects that haven't declared either issue-resolver-side block.

### Per-step behaviour

| Step | Static checks | Test selection sub-agent | Test execution |
|---|---|---|---|
| §7 baseline | Yes | No (no diff yet) | No |
| §8 pre-push verification (after code changes, before §9 push) | Yes | Yes | Yes (when sub-agent returns a non-empty COMMAND) |
| §10.6 review-loop iteration (after addressing feedback, before re-push) | Yes | Yes | Yes (when sub-agent returns a non-empty COMMAND) |
| Post-`review`-approved | — | — | No (removed; pr-evaluator's full suite replaces it) |
| §11 final verification | — | — | No (removed; pr-evaluator's full suite replaces it) |

The §7 baseline gate is now narrower in scope: "is the project's static toolchain healthy?" — not "is the full test suite green on `main`?" The latter is the project's CI's responsibility. Trust-decay rules and the `Baseline established` epic comment format stay (they govern when to *re-run* the baseline at all); they no longer record a tier.

### Test-selection sub-agent

§8 and §10.6 each spawn a read-only `Explore` agent for selection. Reasoning happens entirely inside the sub-agent so the main conversation never sees the diff hunks, the test directory listings, or the grep output — only the sub-agent's two-section verdict. The sub-agent uses Bash/Read/Glob/Grep against the worktree to read the diff, list each declared target's directory, and grep for changed symbols.

**Prompt template** (substitute the placeholders at call time):

```
You are selecting which test suites to run for a Claude Code dev iteration of the
`github-issue-resolver` skill. Your output drives the next test command; the rest of
the workflow does not see your reasoning, so be explicit in your rationale.

Inputs:
- Worktree path: <absolute path to .worktrees/<branch>>
- Integration target: <main, or epic/<N>-<slug> for stories under an open epic>
- Test-target config (verbatim from the project's COMMANDS.md / CLAUDE.md):
  <contents of the <!-- issue-resolver-test-target --> block>

Steps:

1. Compute the diff: `git diff <integration-target>...HEAD` from the worktree.
   Read both the file paths and the hunk contents — don't decide based on paths alone.
   If the diff is empty, return COMMAND: (none) and a one-line rationale.
2. List each declared target's directory: `ls <target>/` for each target in the config.
3. Apply these heuristics in order, building a union of suite identifiers across all
   declared targets:
   a. Direct filename mapping per the target's `naming` rule (when a 1:1 mapping is
      declared and the corresponding test file exists).
   b. Test files modified directly → include their suite.
   c. Symbol references — identify symbols introduced, modified, removed, or renamed
      in the diff (types, functions, accessibility identifiers, error cases,
      string-catalog keys). For renames, search both the old and new names.
      `grep -l` across each target's directory; include any test file that mentions
      any matching symbol. Translate file paths to suite identifiers using the
      target's `naming` rule.
   d. `@testable import` tracking — a test file that imports a sub-module touched
      by the diff is a candidate even if no explicit symbol matches (extension
      methods, Codable conformances, etc.).
4. Apply per-target widening rules from the config:
   - Helpers-fallback triggers when a test-side helper changes (a file in the
     target's directory not matching the suite-naming pattern).
   - Broad-change-fallback triggers when the diff changes a widely-referenced type
     (more than ~5 test files mention it), a persistence-model schema, generated
     config, or any change you cannot narrow with confidence.
   - If a target declares a fallback as `none`, do not widen for that target —
     return zero suites for it instead and let `github-pr-evaluator`'s canonical
     run cover the gap.
5. UI blast-radius exploration. Name/symbol proximity is fine for unit tests
   but a poor proxy for UI tests, because UI tests are integration tests that
   transit shared view-tree state. A small diff in a high-fanout view (the
   running app's root, a top-level navigation container, a view that gates
   the rest of the UI behind a sheet) can break unrelated UI tests, and
   step 3's symbol-grep won't catch it. Before finalising the UI test set,
   do a focused exploration pass:

   a. For each modified Swift file under the project's source tree, decide
      whether it is a View. A View is anything declaring `: View` or whose
      name matches the project's view-naming convention (e.g. `*View.swift`).

   b. For each modified View, trace its consumers: `grep -rln "<TypeName>("`
      across the source tree (excluding tests). Build a small list of "Views
      that use this View." If any consumer has UI tests (by symbol grep or
      name proximity), those UI tests are candidates regardless of whether
      they reference the diff directly.

   c. Treat any of these as broad UI impact and widen the UI selection to
      the per-target broad-change-fallback (or, if that is `none`, to the
      union of every UI test file that transits the affected view-tree
      surface):

      - The diff modifies the app entry point (`@main`) or the top-level
        body composition reachable from it.
      - The diff modifies a View instantiated in another View's `body`, and
        that other View is reached by existing UI tests.
      - The diff adds, removes, or modifies a presentation modifier on a
        root-reachable View — `.sheet`, `.fullScreenCover`, `.alert`,
        `.confirmationDialog`, `.popover`, `.overlay`. These insert global
        UI surface that intercepts unrelated tests.
      - The diff changes `@Environment` or `.environment(...)` injection
        at or near the app root, or modifies launch-environment reading or
        initial-state gating logic.

   d. When uncertain about a UI file's blast radius, widen rather than
      narrow. The targeted-selection win on UI is bounded (UI tests are
      already expensive per case); the cost of merging a root-view
      regression masquerading as a leaf change is the entire next baseline,
      plus the diagnostic cost. The asymmetry strongly favours widening.

   You decide how deep to read. Stop when you can name the affected surface
   confidently or when further reads aren't changing the test set; widen
   rather than continue exploring.
6. Pure-docs / comment-only diffs (only `*.md`, `docs/`, code-comment changes) →
   COMMAND: (none).

Output exactly two sections, in this order, with these literal headers:

COMMAND:
<single shell command using the wrapper from the config plus -only-testing flags
for each selected suite, OR one of the fallback commands declared in the config,
OR the literal string `(none)` if zero suites selected>

RATIONALE:
<one or two sentences naming the selected suites and the heuristic that produced
them. Be specific about what you searched and what matched. If you returned
`(none)` or invoked a fallback, name the trigger explicitly so the user can audit.>

Examples of well-formed output:

COMMAND:
./scripts/xcb.sh -only-testing FoodJournalTests/ProposalServiceTests -only-testing FoodJournalTests/IngredientMatcherTests

RATIONALE:
Selected ProposalServiceTests (direct mapping: ProposalService.swift) and
IngredientMatcherTests (symbol-grep hit: NutritionCalculator referenced from
matcher tests). UI tests deferred to pr-evaluator — no UI test references the
changed views.

—

COMMAND:
./scripts/xcb.sh -only-testing FoodJournalTests

RATIONALE:
Logger renamed from .nutrition to .meals; symbol-grep matches 12 test files across
unit suites. Triggered FoodJournalTests broad-change-fallback. UI selection deferred
(no UI tests reference the renamed category and FoodJournalUITests broad-change is
declared "none").

—

COMMAND:
./scripts/xcb.sh -only-testing FoodJournalTests/OnboardingStepTests -only-testing FoodJournalUITests

RATIONALE:
Diff adds a `.sheet(...)` to `DailyJournalView` (root-reachable view) and introduces
`OnboardingView`. Step-5 UI blast-radius rule (5c) fires on the new presentation
modifier on a root view — widened UI selection to the full FoodJournalUITests target
rather than just an onboarding-named suite, because every UI test transits
DailyJournalView. Unit selection stays tight: only OnboardingStepTests references
the new types.

—

COMMAND:
(none)

RATIONALE:
Diff touches only docs/architecture.md. Pure-docs path — no tests selected.
```

The skill parses these two sections and proceeds:
- `COMMAND: (none)` → skip test execution entirely; print the rationale to the user; mark the iteration's test status as "skipped (no tests selected)" and continue.
- `COMMAND: <shell command>` → print the rationale to the user; delegate execution per the next section.

### Test execution — Apple-platform subagent delegation

If the resolved command begins with `xcodebuild` (or invokes a wrapper that runs `xcodebuild`, like `./scripts/xcb.sh`), delegate execution to the `apple-platform-build-tools:builder` subagent. The subagent absorbs the verbose build log and returns terse pass/fail plus the first error if any — keeping conversation context clean. Non-xcodebuild commands (e.g., `pytest`, `go test`) run inline.

**Bound the subagent's scope explicitly when invoking it.** The subagent is a build-runner, not an autonomous coder. Its job for this delegation is narrow and one-shot: run the command exactly as given, capture the result, and return pass/fail plus the first error if any. It must not edit code, "fix" failures it diagnoses, re-run with different flags, or expand scope. Build/test failures bubble back to this skill — the calling workflow decides next steps. A silent diagnose-and-fix loop inside the subagent breaks the review-loop's visibility into what changed and why, hides edits from the user's audit trail, and uncaps the wall-clock cost of a single delegation. State the constraint in the prompt you hand to the subagent; don't assume it.

Concretely, the prompt should look like: *"Run this exact command from this exact directory: `<command>` (cwd: `<worktree path>`). Absorb the log. Return pass/fail plus, on fail, the first error and the failing test name(s). Do not edit any source files. Do not re-run with modified flags. Do not investigate failures beyond identifying them. If the test fails, the calling skill will handle next steps."*

This mirrors `github-pr-evaluator` §5.5.3. The targeted-tests strategy means each invocation runs only the selected suites, so the build log per iteration is much shorter than a full-suite run anyway — but the delegation layer is still useful and keeps the convention consistent across both skills.

## Workflow

### 1. Identify the issue

The user will give you an issue number (`#423`), a URL (`https://github.com/owner/repo/issues/423`), or both. Extract:
- The issue number
- The repo (from URL, current git remote, or user-supplied `--repo`)

If ambiguous (e.g., they said "issue 42" but you're in a monorepo or there's no obvious repo context), ask once before proceeding.

### 2. Fetch the full issue context

Always pull the issue **and all comments** in one go:

```bash
gh issue view <number> --repo <owner/repo> --comments --json number,title,body,state,labels,author,createdAt,updatedAt,comments,assignees,milestone,url
```

Also check for linked PRs and related issues:

```bash
gh issue view <number> --repo <owner/repo> --json closedByPullRequestsReferences,projectItems
```

And explicitly search for **any** open or draft PR that references the issue — `closedByPullRequestsReferences` only covers PRs that *would close* the issue, and only catches them if the linkage syntax was used. Open/in-progress PRs by other contributors often won't appear there:

```bash
gh pr list --repo <owner/repo> --state open --search "<issue-number> in:body" --json number,title,author,isDraft,headRefName,url,updatedAt
```

Read everything before forming an opinion. Long threads matter — the original post is often outdated by the time someone asks you to work on it.

### 3. Determine the current state

This is the most important step. After reading the thread, explicitly identify:

- **Latest decision or direction** — what's the most recent substantive comment that shifts the plan? Treat earlier proposals as superseded if a maintainer or the OP has agreed to a different approach.
- **Open questions** — anything the thread is waiting on (clarification, design decision, third-party action).
- **Already-tried approaches** — work that's been attempted and rejected. Don't re-propose these.
- **Who's blocked on what** — is the issue blocked on the user, on a maintainer review, on an upstream dependency, or ready to be worked?
- **Issue type** — bug / feature / question / refactor / discussion / duplicate / **epic** / **story**. This determines what "resolved" means.
- **Epic / Story detection.** Check the issue's `labels` array:
  - Label includes `epic` (case-insensitive) → or title starts with `Epic:` → treat as an Epic; skip to the "If the issue is an Epic" section after step 4.
  - Label includes `story` → treat as a Story; skip to the "If the issue is a Story" section after step 4.
  - Neither → continue with the standard workflow.

Write this state summary out loud (briefly) before doing any work. It anchors the rest of the response and lets the user correct you if you've misread the thread.

### 4. Choose the right kind of response

Match the work to the issue type:

| Issue type | What "resolving" looks like |
|---|---|
| **Bug report** | Reproduce locally if possible, find root cause, fix it, add a regression test |
| **Feature request** | Confirm scope from thread, design, implement, add tests + docs |
| **Question / discussion** | Research the answer (code, docs, history), draft a clear response |
| **Refactoring / cleanup** | Make the change, verify tests pass, keep behaviour identical |
| **Blocked / needs info** | Don't implement — draft a comment asking the specific question that unblocks it |
| **Duplicate / already fixed** | Verify, then draft a comment with the link to the resolving issue/PR |
| **Epic** | Audit child story states; reconcile body checkboxes with reality; manage the epic integration branch; if all stories closed and DoD verifiable, propose the integration PR (`epic/<N>-<slug>` → `main`) and, after it merges, the body-tick + close. Otherwise report progress and stop. **The epic itself never gets a single feature PR.** See "If the issue is an Epic" below. |
| **Story** | Resolve like a normal feature/bug, but: (a) read the parent epic's `## Goal` and `## Background` as additional grounding; (b) target the parent epic's integration branch, not `main`; (c) PR title and body reference both the story and the parent epic. See "If the issue is a Story" below. |

If the issue type is genuinely unclear from the thread, ask the user before doing significant work.

## If the issue is an Epic

Epics use a consistent body template: `## Goal`, `## Background`, `## Stories` (a markdown task list of `- [ ] #NN — description` lines), `## Definition of done` (a second task list), and occasionally `## PRD impact`. There are no native GitHub sub-issues — child relationships exist only as `#N` references inside these task lists.

**Resolving the epic branch name.** Both the epic-as-target flow and the story flow need to refer to the integration branch by name. The branch follows the pattern `epic/<N>-<slug>`, but the slug is derived from the epic title — and titles can shift, slugging conventions can be ambiguous, and two runs computing slugs independently have already produced divergent names (issue #102: run 1 picked `visual-redesign`, run 2 picked `daily-journal-visual-redesign`, which would have orphaned the original branch). To prevent that class of bug, **discover the existing branch by prefix; only compute a fresh slug on the bootstrap path.**

**Discovering an existing epic branch.** Run:

```bash
git ls-remote --heads origin "epic/<N>-*"
```

- **One match** → use that branch name verbatim for every subsequent command in this run (worktree paths, fetch targets, push targets, `--base`, PR body references, the legacy-recovery worktree). If you need a slug for a worktree directory, extract it from the actual branch name. **Do not recompute it from the title.**
- **Zero matches** → the integration branch hasn't been bootstrapped. Continue per "If the branch does not exist on origin" below (epic flow) or the existing stop-and-redirect message (story flow).
- **Multiple matches** → flag every candidate to the user and ask which is canonical. Multiple matches usually indicate an orphaned bootstrap or a hand-created branch; silently picking one risks landing work on the wrong branch. Stop until the user resolves it.

**Computing a fresh slug (bootstrap only).** Used only when discovery returns zero matches and the epic flow is bootstrapping a new branch. The derivation is:

1. Take the epic issue title.
2. If it begins with `Epic:` (case-insensitive), strip that prefix and any leading whitespace.
3. Lowercase.
4. Replace every run of characters not in `[a-z0-9]` with a single `-`.
5. Strip leading and trailing `-`.
6. Truncate to at most 50 characters; if the truncation would land mid-word (the next character is `[a-z0-9]`), keep truncating back to the previous `-`. Strip any trailing `-` left behind.

The full slug is preferred over a "short" version. Subjective shortening is what produced the divergent run-1/run-2 names on issue #102 — the algorithm has no manual shortening step. 50 characters is enough for any realistic epic title and gives every run the same answer.

**Examples.**
- `Daily Journal Visual Redesign` → `daily-journal-visual-redesign`
- `Epic: Macro Radials Data` → `macro-radials-data`
- `Auth/Token Refresh (Phase 2)` → `auth-token-refresh-phase-2`

For the rest of this section and the Story section, `<branch>` refers to the result of discovery (one match) or the bootstrap branch name (zero matches → fresh slug). The literal placeholder `epic/<N>-<slug>` in command snippets is shorthand for `<branch>`; substitute the discovered or freshly-computed name.

**Parse the body.** Extract every `- [ ]` / `- [x]` line from `## Stories` and `## Definition of done`, noting the referenced issue number and current checkbox state.

**Reconcile story states.** For each `#N` in Stories, fetch its real state:

```bash
gh issue view <N> --repo <owner/repo> --json number,title,state,stateReason,closedAt
```

Build a table comparing what the body says (checked/unchecked) against what GitHub says (open/closed). Surface any drift — body says `- [ ]` but issue is actually closed, or vice versa.

**Check the integration branch.** Resolve `<branch>` per "Resolving the epic branch name" above (discover by prefix; if zero matches, the bootstrap path will compute a fresh slug).

If discovery returned a match, fetch it and check drift against `main`:

```bash
git fetch origin epic/<N>-<slug> main
git rev-list --count origin/main..origin/epic/<N>-<slug>   # ahead
git rev-list --count origin/epic/<N>-<slug>..origin/main   # behind (drift)
```

If the epic branch is behind `main`, rectify this before proceeding — story work landing on a stale epic branch will inherit the drift and make the integration PR harder to merge. Set up a worktree on the epic branch and rebase onto `main`:

```bash
git worktree add .worktrees/epic-<N>-<slug> epic/<N>-<slug>
cd .worktrees/epic-<N>-<slug>
git rebase origin/main
```

Show the user the rebase plan (commit list) before running it. If the rebase succeeds, push with `--force-with-lease` (never bare `--force`) and confirm with the user before doing so:

```bash
git push --force-with-lease origin epic/<N>-<slug>
```

If the rebase produces conflicts, run `git rebase --abort`, surface the conflicting files to the user, and stop — ask the user to resolve the conflicts manually before continuing.

**If the branch does not exist on origin** → the epic infrastructure hasn't been bootstrapped yet. The epic-as-target run is the canonical place to do this — story runs deliberately stop and redirect here rather than bootstrap silently, so a missing step in the user's workflow stays visible. Offer to bootstrap now (this includes a remote write — show the user and confirm before each step).

Before the numbered steps below, derive the slug per "Computing a fresh slug" in the "Resolving the epic branch name" section above; the resulting `epic/<N>-<slug>` is the `<branch>` for the rest of this bootstrap. Show the user the computed name before proceeding so a typo or unexpected slug surfaces before the first remote write.

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
   Announce the path. Every subsequent command in the bootstrap (and every later epic-as-target run) lives here. Branching from `origin/main` rather than local `main` lets the bootstrap proceed without a `git checkout main` in the main tree, while still preserving the SHA invariant — the worktree's HEAD equals `MAIN_SHA` at creation time. If a fresh worktree was created (not reused), run the project's worktree-setup commands per "Worktree setup & teardown commands" above before continuing to step 3.
3. Run the project's full canonical suite *in the worktree*. This is the green baseline — it will be inherited by every story under this epic until invalidated. If red, follow step 7's standard handling (detour-first or explicit override). If overridden, post a `Baseline override` comment on this epic issue before proceeding so any later story re-establishes the baseline.
4. On green (or after override), push the new branch from the worktree:
   ```bash
   git push -u origin epic/<N>-<slug>
   ```
5. Post the `Baseline established` comment on the epic issue (format per step 7's "Persistence" subsection). At the fork point `Epic branch SHA` and `Main SHA` are both equal to the `MAIN_SHA` you captured in step 1 — record that single SHA in both fields.

**If the branch exists but the epic issue has no `Baseline established` comment** (epic predates this rule, or the comment was never posted) → offer to establish one now on the epic branch HEAD. Set up a worktree on the epic branch first — fetch the branch, ensure `.gitignore` contains `.worktrees/`, run `git worktree list --porcelain` and reuse if one exists; otherwise:

```bash
git fetch origin epic/<N>-<slug>
git worktree add .worktrees/epic-<N>-<slug> epic/<N>-<slug>
cd .worktrees/epic-<N>-<slug>
```

If a fresh worktree was created (not reused), run the project's worktree-setup commands per "Worktree setup & teardown commands" above before the canonical suite. Run the canonical suite *in the worktree*, and on green post the comment with the current epic-branch SHA and the current `git merge-base origin/main origin/epic/<N>-<slug>` as `Main SHA`. Without this comment, every story under the epic would otherwise stop and redirect back here — establishing it once unblocks the whole epic.

**Classify the situation and act accordingly:**

**All stories closed + all DoD items verifiable → "ready to integrate then close"**

1. Confirm the integration branch exists. Verify that every story's PR has merged into it by checking each story PR's `baseRefName` via `gh pr list --search "closes #<N> OR fixes #<N>"` and inspecting `--json baseRefName`. Flag any story whose PR targeted `main` directly.
2. Set up a worktree on the epic branch (follow the worktree rules in the section above), merge `origin/main` into it if drift exists, run the full canonical suite, and report results.
3. If the suite is green, draft an integration PR body (`epic/<N>-<slug>` → `main`) listing every story PR that landed in it, citing the epic's `## Goal` and DoD checklist, and including `Fixes #<epic-number>` so GitHub auto-closes the epic on merge. Show the draft and confirm before running:
   ```bash
   gh pr create --repo <owner/repo> --base main --head epic/<N>-<slug> --title "Epic #<N>: <title>" --body-file integration-pr.md
   ```
4. Run the review loop (step 10) on the integration PR. After it merges, draft the body-tick diff (flip every `- [ ]` → `- [x]` in Stories and DoD, including stretch items marked as "deferred"), and a closing summary comment. Show both to the user and confirm before:
   ```bash
   gh issue edit <N> --repo <owner/repo> --body-file updated-body.md
   ```
   GitHub auto-closes the epic via the `Fixes` linkage on integration-PR merge; if it didn't, fall back to `gh issue close <N> --reason completed`.

**All stories closed but DoD items not fully verifiable → "DoD verification needed"**

List each unticked DoD item alongside what evidence would satisfy it (code path, test name, config flag). Ask the user to verify each item or make the verification explicit in the PR before opening the integration PR.

**Stories incomplete → "in progress"**

Report progress (e.g. `5 of 8 stories closed, 2 open, 1 not started`), sync any stale body checkboxes (offer a body edit diff if drift was found), report epic-branch drift vs `main`, and identify the next unblocked story candidate (the first open story with no open dependencies in the body order). **Stop there** — do not start implementation work on a child story unless the user explicitly redirects to it.

**Body references issues that don't exist or aren't labeled `story`** — flag the inconsistency before doing anything else.

**The epic-as-target run never produces a feature PR.** It produces a status report, optionally a body-checkbox sync edit, optionally an integration-branch bootstrap (push + baseline + comment) when the branch is missing or the baseline comment is absent, optionally an integration PR with its own review loop, and eventually a body-tick + close. Skip the "create a feature branch, do the work, open a story PR" parts of the standard flow entirely.

---

## If the issue is a Story

**Find the parent epic.** Search for an open or closed epic whose body contains a reference to this story number:

```bash
gh issue list --repo <owner/repo> --label epic --state all \
  --search "#<story-number> in:body" \
  --json number,title,body,labels,state,url
```

- **No parent epic found** → proceed as a regular feature/bug (PR base is `main`). Note this in the state summary so the user can decide whether to retroactively add this story to an epic.
- **Multiple matches** → flag the ambiguity and ask which epic applies before continuing.
- **Parent epic found** → read its `## Goal` and `## Background` sections. These provide the strategic grounding for why this story exists — use them alongside step 6's PRD/Architecture/CLAUDE.md docs. Cite the parent epic in the PR body's `## Doc grounding` section (e.g. `Parent epic #22 — Goal: …`).

**Determine the PR base.** Resolve `<branch>` per "Resolving the epic branch name" in the Epic section above (discover by prefix; if multiple matches, stop and ask). The story flow never computes a fresh slug — that path lives only in the epic-as-target bootstrap. Treat the discovery result as one of three outcomes:

- **One match (branch exists)** → evaluate the epic-level baseline trust state before creating the story worktree. Fetch the epic issue's comments and work through the trust checks from step 7:
  1. Find the most recent `Baseline established` comment. **If none exists** (epic predates this rule, or the bootstrap comment was never posted), **stop** and direct the user to run this skill on epic #`<N>` first — the epic-as-target run handles the legacy "branch exists, comment missing" recovery in the same place as first-time bootstrap. Do not silently establish a baseline from the story flow; see the "Zero matches and the parent epic is open" branch below for the same reasoning.
  2. Compute `git merge-base origin/main origin/epic/<N>-<slug>`. If it differs from the `Main SHA` in the baseline comment, `main` has been merged into the epic branch since that baseline — re-run the baseline on the epic branch HEAD and post a fresh comment.
  3. If a `Baseline override` comment exists dated after the latest baseline comment, re-run the baseline on the epic branch HEAD and post a fresh comment.
  4. Otherwise, skip the baseline. Record the inheritance in the state summary and proceed.

  In all cases, also check drift. If `origin/main` is ahead of `origin/epic/<N>-<slug>`, rectify it **now — before creating the story worktree** — by rebasing the epic branch onto `main` using the same procedure described in the Epic section above. A story worktree branched off a stale epic branch inherits the drift and makes the integration PR harder to merge.

- **Zero matches and the parent epic is open** → the epic's integration branch has not been bootstrapped yet. **Stop.** Tell the user, in roughly these words:

  > Epic #`<N>` has no integration branch on origin and no `Baseline established` comment. Run this skill on epic #`<N>` first — the epic-as-target run will execute the green baseline, push `epic/<N>-<slug>`, and post the baseline comment. Then re-run me on this story.

  Do not silently bootstrap from the story flow. The epic-as-target run is the canonical place for this work, and bootstrapping here would mask a missing step in the user's workflow — the next story would face the same situation, the user would never learn the intended sequence, and the epic issue's comment thread would lose the chronological story of when the integration branch came into being.

- **Zero matches and the parent epic is already closed** → the integration PR has already merged; use `main` as the PR base (the epic completed normally) and note this in the state summary.

**Create the story worktree off the epic branch** (not off `main`):

```bash
git worktree add -b issue-<story-number>-<slug> \
  .worktrees/issue-<story-number>-<slug> \
  origin/epic/<N>-<slug>
```

Follow all the same worktree rules (nesting guard, `.gitignore` check, reuse rule) as in the main worktree section. If a fresh worktree was created (not reused), run the project's worktree-setup commands per "Worktree setup & teardown commands" above before continuing.

**Open the PR with `--base epic/<N>-<slug>`**, not `--base main`. The PR body must include a line:

> This story targets the `epic/<N>-<slug>` integration branch and will reach `main` via the integration PR for epic #<N>.

This prevents reviewers from expecting a direct `main` merge.

**Drift check before pushing.** Drift was already addressed before the story worktree was created (see above). If for some reason `origin/main` has advanced again between worktree creation and push (e.g., a concurrent merge), surface this to the user — re-run the rebase on the epic branch before pushing the story branch.

**After the story PR merges.** The parent epic's body still shows `- [ ]` for this story — GitHub task lists don't auto-tick on PR merge. Flag this in step 11's summary so the user or a future epic-targeted run can sync the checkbox.

---

### 5. Check for existing work on this issue

Before creating any branch, decide what to do based on what's already in flight:

| Situation | What to do |
|---|---|
| **Open PR you authored, branch is yours** | Set up a worktree on the existing branch (see "Setting up the worktree" below), read the full PR context (see below), and continue from there. Skip the "create a branch" part of step 8. |
| **Open PR by someone else, actively being worked on** | **Do not open a competing PR.** Surface this to the user with the PR link and the latest activity. Offer to review the existing PR, leave a constructive comment, or wait — let the user decide. |
| **Open PR by someone else, gone stale (no recent activity, requested changes unaddressed for a long time)** | Still don't trample silently. Tell the user, link the stale PR, and ask whether to take it over (set up a worktree branched off the stale PR's branch with a new local branch, see "Setting up the worktree" below) or start fresh. |
| **Draft PR** | Treat the same as an open PR by the same author. Drafts are still claimed work. |
| **Closed PR that resolved the issue** | The issue should already be closed. If it isn't, something's odd — flag it to the user before doing anything else. |
| **Closed/merged PR that did *not* resolve the issue** (partial fix, reverted, abandoned) | Note this in the state summary, read the PR's full context (see below) to learn what was tried and why it didn't land, then proceed as the no-prior-PR case (a fresh worktree off default, per step 8). |
| **No prior PR** | Proceed normally to step 8. |

**Setting up the worktree.** When step 5 directs you to check out an existing PR's branch — your own open PR, or a takeover of a stale one — set it up as a worktree rather than `gh pr checkout` in the main tree:

1. Get the branch name: `gh pr view <pr-number> --repo <owner/repo> --json headRefName -q .headRefName`.
2. Run `git worktree list --porcelain` and check whether the target branch already has a worktree. If yes, `cd` to that path and stop here — reuse it.
3. Otherwise, fetch the branch (`git fetch origin <branch>`), then add the worktree:
   - **Continuing your own PR**: `git worktree add .worktrees/<branch> <branch>`.
   - **Taking over a stale PR**: pick a new local branch name (e.g. `issue-<N>-takeover`) and run `git worktree add -b <new-branch> .worktrees/<new-branch> <stale-pr-branch>`.
4. `cd .worktrees/<dir>` — every subsequent command in this run is from there. Announce the path to the user.
5. Run the project's worktree-setup commands per "Worktree setup & teardown commands" above. Step 2's reuse exit skips this — those commands already ran when the worktree was first created.

If the skill is invoked from inside another worktree, locate the main working tree first (`git worktree list --porcelain`, take the first `worktree` entry) and run `git worktree add` with paths relative to that main tree's root — don't nest.

Before the first worktree is created in a repo, ensure `.gitignore` contains a `.worktrees/` entry; append it if missing.

**Reading the full PR context.** Whenever you're continuing, taking over, or learning from an existing PR, read it as carefully as you read the issue — the PR thread is where implementation decisions actually got made:

```bash
# PR metadata, body, and the issue-style comment thread
gh pr view <pr-number> --repo <owner/repo> --comments --json number,title,body,state,isDraft,author,headRefName,baseRefName,createdAt,updatedAt,comments,url

# Code review threads (line-level review comments are NOT in the above — they live separately)
gh api repos/<owner>/<repo>/pulls/<pr-number>/reviews
gh api repos/<owner>/<repo>/pulls/<pr-number>/comments

# The diff itself
gh pr diff <pr-number> --repo <owner/repo>
```

When you read PR context, apply the same state-assessment lens as in step 3: what's the latest decision, what's been tried and rejected, what review feedback is unaddressed, who's blocked on what. Don't re-propose approaches that were already tried, and don't contradict a direction the PR has already converged on.

When in doubt, surface what you found and ask. Stepping on someone else's in-progress work is worse than pausing for one clarifying message.

## Where comments go: issue vs. PR

Throughout the rest of the workflow you may need to post comments — clarifying questions, scope concerns, status updates, review responses. Route each comment based on what it's about, not based on which step you're in:

| Comment is about… | Goes on… |
|---|---|
| The problem itself — clarifying the bug, the scope, the requirements | **Issue** |
| The fix's design or implementation — approach, tradeoffs, code-level questions | **PR** |
| Status updates on work in progress | **PR** if one exists, otherwise **issue** |
| Review feedback or responses to review | **PR** |
| "This is a duplicate of #X" / "this is already fixed in #Y" | **Issue** |
| Asking a maintainer to weigh in on a decision | Wherever the decision lives — design questions on the PR, scope questions on the issue |

The principle: **issues are about the problem, PRs are about the solution.** If a future contributor were trying to understand the problem, they'd want it on the issue. If they were trying to understand why this particular fix looks the way it does, they'd want it on the PR.

A single thought sometimes needs both — e.g., "this fix only handles case A, case B is out of scope" warrants a brief note on the PR (explaining the boundary of *this* fix) and may also warrant a follow-up issue or comment on the original issue (flagging that case B remains unresolved). Don't cross-post the same comment to both places.

## Comments persist as context

Every comment the skill posts becomes part of the thread on future runs. Step 2 and step 5 will surface them again next time. That means:

- **No local notes file is needed** — GitHub is the durable record. Don't try to maintain a parallel local cache; it'll drift.
- **On a re-invocation**, comments you posted previously will appear in the issue and PR comment threads alongside everyone else's. Read them as **prior context**, not as fresh requests to act on. They tell you what was already said, asked, or promised.
- **Write comments as if a future invocation will read them.** Be specific about what was decided, what's still open, and what the next step is. "Going with approach B per @maintainer's suggestion above; will add tests for the null-token case next" is more useful to future-you than "ok will fix."

### 6. Ground the implementation in project docs

**When this step applies.** Any code change beyond a one-line fix — features, refactors, and non-trivial bug fixes. Skip for: comment-only responses (questions, blocked issues, duplicates), one-line bug fixes, and pure doc/typo changes.

**Check which docs are present:**

```bash
ls docs/prd.md docs/architecture.md CLAUDE.md 2>/dev/null
```

Read each one that exists. `CLAUDE.md` often `@`-references additional docs (e.g., `@docs/constitution.md`); follow those references and read the linked files too.

**Cite what informed the approach.** Identify the specific sections of the PRD / Architecture / CLAUDE.md / any referenced constitution that constrain or shape the implementation. Write a brief grounding statement before step 8 — for example:

> PRD §3 defines natural-language entry as the only input method. Architecture §2 layer rules require Stores to import only Foundation/SwiftData/Services/Models. Constitution §4 forbids `UserDefaults` — all settings must be on `UserProfile`. Therefore the approach is …

This grounding statement is the output of this step. State it before writing any code so the user can correct the framing if it's wrong. The PR body MUST cite these sections (see step 9).

**Surface tensions before proceeding.** Three patterns to watch for:

- **The issue contradicts a doc.** E.g., the issue requests behaviour the constitution forbids (a banned API, a forbidden architectural pattern, a capability the PRD explicitly excludes). **Stop.** Surface the conflict to the user and ask how to proceed: update the doc, reshape the issue, or override with a documented reason. Do not silently work around it.
- **The issue extends the docs into territory they don't cover.** Note this to the user and proceed unless they want to update the docs first.
- **The issue describes a gap between built behaviour and what a doc specifies.** Cite the relevant section in the grounding statement — this reframes "feature X is incomplete" as "feature X doesn't match PRD §Y," which is more actionable.

**If no docs are present.** Skip this step silently. No warning, no prompt — many repos won't have these files.

### 7. Establish a green baseline

Before changing any code, verify the project's static toolchain is in good standing — codegen succeeds, dependencies resolve, lints pass, layer-import boundaries hold. Otherwise you risk a costly diversion mid-task: a failing lint you assume your change broke turns out to have been red on the base branch the whole time, and you've burned an hour "fixing" something that was never yours.

**When this step applies.** Any work that involves code changes — bug fixes, features, refactors. Skip for comment-only responses (questions, blocked issues, duplicates) and pure documentation/typo edits.

**What to run.** The static-checks list from the `<!-- issue-resolver-fast-checks -->` block. **No tests run at the baseline gate** — there's no diff yet vs the integration target, so test selection (§10.6) would be a no-op. This skill doesn't run the full canonical suite at any gate; the CI on the integration branch is the authoritative answer to "is `main` green?", and the baseline gate's job is narrower: confirm the *toolchain* is healthy on this developer's machine before code changes start.

If neither `issue-resolver-fast-checks` nor `pr-evaluator-static-checks` exists in the project's `COMMANDS.md` / `CLAUDE.md`, fall back to running the legacy `<!-- pr-evaluator-health-checks -->` block (the canonical suite) inline — accept the cost on a project that hasn't declared a static-checks subset. If no block at all is found, ask the user; don't invent commands.

**Subagent delegation.** Static-checks commands are typically lints and codegen — small outputs, run inline. If any command in the block begins with `xcodebuild` (rare for static-only blocks, but possible), delegate to `apple-platform-build-tools:builder` per the convention in "Test selection during iteration" above.

**Sync the integration target first.** Whenever the baseline runs against `main` in the main checkout (regular issues only — epic bootstrap and legacy recovery use a worktree), fast-forward local `main` to `origin/main` before doing anything else — the SHA you baseline must be the SHA you build on. Otherwise the baseline result and the SHA your work is based on can disagree.

```bash
git fetch origin main
git checkout main
git merge --ff-only origin/main
MAIN_SHA=$(git rev-parse HEAD)
```

If the fast-forward fails (local `main` has diverged from `origin/main`, or has unpushed commits), stop and surface this to the user — do not start feature work on top of a divergent local `main`. Once the fast-forward succeeds, treat the captured `MAIN_SHA` as the SHA the baseline ran on. (Epic bootstrap captures `MAIN_SHA` differently — see "If the issue is an Epic" → "If the branch does not exist on origin" — because the bootstrap branches directly off `origin/main` in a worktree and never touches local `main`.)

**Where to run it — once per integration target, not once per issue.**

The integration target is the branch the PR will eventually merge into. Each integration target needs exactly one green baseline; don't re-run it unless that baseline is invalidated.

| Issue context | Integration target | Run baseline on… |
|---|---|---|
| Regular issue (bug / feature / refactor, no parent epic) | `main` | `main`, in the main checkout, before creating the worktree |
| Epic-as-target bootstrap (no `epic/<N>-<slug>` branch on origin yet, **or** branch exists but no `Baseline established` comment) | `main` at the fork point (new branch case), or `epic/<N>-<slug>` HEAD (legacy/missing-comment recovery) | the epic worktree at `.worktrees/epic-<N>-<slug>` — branched off `origin/main` for first-time bootstrap, or checked out from `origin/epic/<N>-<slug>` for legacy recovery. Never the main checkout. See "If the issue is an Epic" → "Check the integration branch". |
| Story under an open epic | the epic integration branch | **Skip** if the epic-level baseline is still trusted (see below). Re-run on the epic branch HEAD if a trust-decay event has fired. If the epic branch or its `Baseline established` comment is missing, the story flow stops and redirects to the epic-as-target bootstrap above — it never bootstraps from the story flow. |
| Continuing / taking over an existing PR's branch | the existing PR's base | the worktree, with a base-branch run if failures appear (per step 5 guidance) |

**Trust state for the epic-level baseline.** A story under an open epic can skip its own baseline if both hold:

1. The epic issue has a "Baseline established" comment (see "Persistence" below).
2. Neither of the following events has occurred since that comment's date:
   - **`main` was merged into the epic branch** — detected by comparing `git merge-base origin/main origin/epic/<N>-<slug>` against the `Main SHA` recorded in that comment. If they differ, re-run on the epic branch HEAD.
   - **A prior story under this epic landed under a baseline override** — detected by scanning the epic issue's comments for a "Baseline override" comment (see "Persistence" below) dated after the most recent "Baseline established" comment. If found, re-run on the epic branch HEAD.

If neither event fires, skip the baseline and record in the state summary: `Inherited epic baseline established <date> at main@<sha> — green.`

If there is no `Baseline established` comment on the epic issue (the epic predates this rule, or the comment was never posted), the epic infrastructure has not been bootstrapped. Stop and direct the user to run the skill on the epic ticket — the epic-as-target run handles both the first-time bootstrap (push branch + run baseline + post comment) and the legacy "branch exists, comment missing" recovery in one place. Bootstrapping from the story flow is deliberately not allowed; see "If the issue is a Story" → "Branch does not exist and the parent epic is open" for the exact stop-and-redirect message.

**Persistence — two comment formats posted on the epic issue.** Post both after user confirmation (same "show before posting" rule that applies to all GitHub writes in this skill).

*Baseline established* — posted whenever the skill runs a green baseline for this epic. Normally posted by the epic-as-target bootstrap (first run on the epic ticket); also re-posted from the story flow when a trust-decay event invalidates the inherited baseline (see "Trust state" above):

```
🤖 Baseline established
- Epic branch SHA: <sha>
- Main SHA: <sha>
- Result: green
- Date: <iso-date>
```

*Baseline override* — posted when the user explicitly overrides a baseline failure on a story PR under this epic (in addition to recording the override in that PR body's out-of-scope notes):

```
🤖 Baseline override
- Story PR: #M
- Reason: <user-provided one-liner>
- Date: <iso-date>
```

These two comment types are the only state needed to evaluate trust across story runs. Both live on the epic issue — durable, visible to humans, and consistent with the skill's existing principle that GitHub is the durable record.

**Interpret the results.**

- **All green.** Note this in your state summary and proceed to step 8. Now any failure that appears after your changes is attributable to your changes.
- **Pre-existing failures unrelated to the issue.** Stop and surface to the user with the specific failures. Do not proceed on a red base. The point of the baseline is to attribute later failures correctly; that attribution falls apart the moment unrelated red is left in the tree, and it lets a PR ship over a broken codebase. Acceptable next moves, all chosen by the user: (a) detour first — open a separate issue/PR that turns the suite green, then resume; (b) explicit user override with a documented reason recorded in the PR body's out-of-scope notes. If this is a story under an open epic, also post a "Baseline override" comment on the epic issue (see "Persistence" in "Where to run it" above) so the next story under this epic knows to re-establish the baseline. Do not silently fix unrelated failures — that scope-creeps the PR and obscures what your change actually did.
- **Pre-existing failures that overlap with the issue.** These may be the bug itself, or a symptom. Note them in the state summary — they likely become the test cases your fix needs to turn green.
- **Base branch is broken.** Stop and surface to the user. There's no useful "green baseline" to compare against, and feature work on top of a broken base will compound the problem.

Record the baseline result before doing any work. The point is twofold: you can attribute later failures correctly, and the user gets early warning if the project is in a worse state than expected.

### 8. Do the work

For code changes:
- Confirm the approach respects the doc grounding from step 6 — if implementation reveals a constraint conflict not visible at planning time, stop and surface it instead of working around it silently.
- If step 5 directed you to continue an existing PR's branch, you're already in its worktree — skip worktree creation.
- Otherwise (fresh branch), create the worktree off the default branch:
  - Pick a slug: `issue-<number>-<short-slug>` (e.g. `issue-423-fix-null-token`).
  - Ensure `.gitignore` contains `.worktrees/` (append if missing) before the first worktree is added.
  - From the main working tree, run `git worktree add -b issue-<number>-<short-slug> .worktrees/issue-<number>-<short-slug>`.
  - `cd .worktrees/issue-<number>-<short-slug>` — every subsequent command runs from there. Announce the path to the user.
  - Run the project's worktree-setup commands per "Worktree setup & teardown commands" above before any code edits or test runs.
- Make the changes.
- **Run the pre-push verification gate before §9 push.** Three steps in this order, per "Test selection during iteration" above:
  1. **Static checks** — run the `<!-- issue-resolver-fast-checks -->` block inline, fail-fast in declaration order. Outputs are small (lints, codegen, layer-import boundary checks); no need to delegate.
  2. **Test selection** — spawn an `Explore` sub-agent with the prompt template from "Test-selection sub-agent." Substitute the worktree path, the integration target, and the project's `<!-- issue-resolver-test-target -->` block. The sub-agent returns `COMMAND:` (a ready-to-run shell command, or `(none)`) and `RATIONALE:` (one or two sentences). Print the rationale to the user as the gate's status line.
  3. **Test execution** — if `COMMAND:` is `(none)`, skip execution. Otherwise run the command; if it begins with `xcodebuild` (or invokes a wrapper that runs `xcodebuild`), delegate to `apple-platform-build-tools:builder`.

  Tests must be green before §9. Don't push red, and don't fall back to "no tests" when the sub-agent's heuristics could have widened — re-spawn the sub-agent if the rationale looks wrong. **Do not skip this gate on the assumption that §10.6 will catch regressions** — §10.6 only fires when the review loop iterates (i.e., review requests changes). On a clean first-pass approval the workflow goes §8 → §9 → §10 (approves) → §11 with no §10.6 — so the gate at §8 is the only test invocation that runs before the PR is opened.
- Keep the diff focused on the issue — don't drive-by-fix unrelated things.

For comment-only responses (questions, blocked issues, duplicates):
- Draft the comment as a markdown file in the working directory so the user can review before posting

### 9. Report back to GitHub

**Always show the user what you're about to post and get confirmation before posting.** Posting is one-way and visible to everyone watching the issue.

For a comment-only response:
```bash
gh issue comment <number> --repo <owner/repo> --body-file comment.md
```

For code changes (all `git push` and `gh pr create` commands run from inside the worktree — same syntax, just a different cwd):

- **If you're continuing an existing PR** (per step 5): just push the new commits to that branch. The PR updates automatically. Don't open a new one.
- **If this is a fresh PR**: push the branch and open a PR:

  ```bash
  gh pr create --repo <owner/repo> --title "Fix: <summary> (#<issue-number>)" --body-file pr-body.md --base <default-branch>
  ```

  PR body must include `Fixes #<number>` (or `Closes #<number>`) so GitHub auto-links and auto-closes on merge. It must also include a `## Doc grounding` section near the top listing the PRD/Architecture/CLAUDE.md sections that informed the approach (per step 6). Omit this section only if no project docs were present.

In both cases, capture the PR number/URL — you'll need it for the review loop.

### 10. Run the review loop (PRs only)

**This step is mandatory for any issue resolved with code changes. Do not skip it, do not merge, and do not consider the work done until review approves the PR.**

After the PR is opened, invoke the **`review` skill** to evaluate the PR. The `review` skill decides what's in scope for review and whether the PR is ready to merge — don't second-guess it. If the skill is re-invoked later to address review comments, step 5's reuse rule will land you back in the existing worktree — don't create a parallel one.

Loop:

1. **Re-read accumulated PR feedback first.** Before invoking `review` again on later iterations, pull the latest PR comments and code review threads (using the same `gh pr view --comments`, `gh api .../reviews`, and `gh api .../comments` commands from step 5). Human reviewers may have weighed in between iterations, and their feedback should be addressed alongside whatever `review` reports.
2. **Invoke the `review` skill** on the open PR (pass the PR number/URL).
3. **Post the review feedback as a comment on the PR** (not the issue):
   ```bash
   gh pr comment <pr-number> --repo <owner/repo> --body-file review-feedback.md
   ```
   Show the user the feedback before posting, same as any other GitHub write.
4. **Check the verdict, and extract any actionable items.** "Approved" alone is not the exit condition — reviewers routinely approve with non-blocking suggestions (`Medium —`, `Low —`, `Nitpick —`, "Approved with minor fixes") that they still expect fixed before merge. Walk the review body and classify each suggestion:

   - **Actionable now** — the reviewer named a concrete change and did not route it elsewhere. Severity label is informational, not gating; what matters is whether a fix is expected on this PR.
   - **Explicitly deferred** — the reviewer used language like "fast-follow", "follow-up", "out of scope", "future PR", "could be a separate change", "not blocking", or otherwise routed the item elsewhere.
   - **Decision required** — the suggestion touches architecture, breaks an API, or carries a tradeoff the user should weigh in on. (Stop and ask, per the loop guard rail below.)

   Exit the loop and go to step 11 only when **both** are true: (a) the verdict is approved, **and** (b) zero actionable-now items remain. If actionable-now items exist on an "approved" verdict, fall through to step 5 and address them — the user opted into the loop by invoking the skill, and a verdict like "approved with minor fixes" is the loop telling you it isn't done yet, not a green light to exit. Bouncing those items back as a fresh user prompt forces the user to manually re-invoke an "address feedback" pass and undoes the loop's value.

   When you do exit, carry the explicitly-deferred items into step 11's summary so the user can decide whether to file follow-up issues.

   The full canonical suite will run once at PR-readiness time inside `github-pr-evaluator` — there's no in-loop final gate here.

   Otherwise, continue.
5. **Address the feedback** — both `review`'s and any unaddressed human reviewer feedback. Make the requested changes on the same branch.
6. **Run the pre-push verification gate** before pushing — same three steps as §8, per "Test selection during iteration" above:
   1. **Static checks** — run the `<!-- issue-resolver-fast-checks -->` block inline, fail-fast in declaration order. Outputs are small (lints, codegen, layer-import boundary checks); no need to delegate.
   2. **Test selection** — spawn an `Explore` sub-agent with the prompt template from "Test-selection sub-agent" above. Substitute the worktree path, integration target, and the project's `<!-- issue-resolver-test-target -->` block. The sub-agent reads the diff, lists each declared target's directory, applies the heuristics, and returns two sections: `COMMAND:` (a ready-to-run shell command, or `(none)`) and `RATIONALE:` (one or two sentences). Print the rationale to the user as the iteration's status line — that's how the user audits the selection.
   3. **Test execution** — if `COMMAND:` is `(none)`, skip execution and continue. Otherwise, run the command. If it begins with `xcodebuild` (or invokes a wrapper that runs `xcodebuild`), delegate to `apple-platform-build-tools:builder`; otherwise run inline.

   Tests must be green. If new failures appear, fix them in the same iteration — do not push red tests on the theory that you'll catch it next round. If `COMMAND:` was `(none)` (e.g., docs-only iteration), there's nothing to be green or red — `github-pr-evaluator`'s full canonical run will exercise the change at PR-readiness time. Don't push red tests under any circumstance, and don't fall back to "run zero tests" when the sub-agent's heuristics could have widened — re-spawn the sub-agent if the rationale looks wrong.
7. **Commit and push.** Reply on the PR (briefly) describing what changed in response to which points of feedback.
8. **Go back to step 1.** Re-read accumulated feedback, re-invoke `review` on the updated PR.

Guard rails for the loop:

- If the same feedback recurs across iterations without progress (you've tried twice and `review` is still flagging the same thing), stop and surface the disagreement to the user — don't spin indefinitely.
- If `review` flags something that requires a decision the user should make (architectural choice, scope change, breaking-change tradeoff), stop and ask the user instead of guessing.
- Cap the loop at a reasonable number of iterations (e.g., 5) before checking in with the user, even if progress is being made.

Only after `review` reports approval should the PR be considered ready to merge. Merging itself is the user's call unless they've explicitly told you to merge.

### 11. Summarise for the user

The summary MUST include a clearly-labeled **Iteration test status** line that names the result of the most recent pre-push verification gate (§8 on a clean first-pass approval, §10.6 on the last iteration when the review loop ran): green, skipped (no tests selected — name the rationale), or red (a list of failing tests with their failure mode). If anything is red at this point, fix it before pushing — don't bury it in follow-up notes. The skill does not run a final canonical-suite gate at this step; the comprehensive run happens once at PR-readiness time inside `github-pr-evaluator`. State this explicitly in the summary so the user knows what's still ahead: e.g. *"Iteration test status: green at <SHA> (selected ProposalServiceTests, run at §8 pre-push). The full unit + UI suite will run in github-pr-evaluator before merge."*

Then: a short summary of what you did, what you posted (if anything), and any remaining open questions or follow-up work. If you created or reused a worktree, include its path and the manual cleanup sequence. The `github-pr-evaluator` skill runs both phases automatically after a green merge (its §14); the manual form below is for runs that don't go through the evaluator (declined merge, manual close, abandoned issue):

1. From inside the worktree, run the project's worktree-teardown commands (see "Worktree setup & teardown commands"). If `COMMANDS.md` declares no `<!-- worktree-teardown -->` block, skip this step.
2. From the main checkout, run `git worktree remove .worktrees/<branch-name>`.

Don't run cleanup yourself: a worktree may hold unpushed work, and teardown may release resources still useful for debugging.

If the resolved issue was a **story** under an open epic, include two additional reminders:
- The parent epic's `## Stories` checkbox for this story is still `- [ ]` — it won't auto-tick on PR merge. A future epic-targeted run (or the user manually) needs to sync it.
- The change has landed on the epic integration branch, not `main`. It will reach `main` via the integration PR for epic #N once all stories under that epic are complete.

## Common pitfalls

- **Don't ignore in-progress PRs.** Always check for an existing open or draft PR before creating a branch. Opening a duplicate PR wastes everyone's time and is rude.
- **Don't take over someone else's PR silently.** If a PR by another author exists for this issue, surface it to the user before doing anything that would compete with or supersede it.
- **Don't implement code without grounding in project docs.** If `docs/prd.md`, `docs/architecture.md`, or `CLAUDE.md` exists, read it before designing the change and cite the relevant sections in the PR. Skipping this leads to implementations that violate non-negotiable project rules (layer boundaries, banned APIs, naming, scope) that the docs encode.
- **Don't skip the green-baseline check for the integration target.** The integration target is `main` for regular issues and the epic integration branch for stories under an open epic. A story under an open epic *inherits* the epic-level baseline and shouldn't re-run it — unless `main` has been merged into the epic branch since that baseline, or a prior story under the epic landed under an explicit baseline override. The point of the gate is correct failure attribution and not shipping over a broken codebase, not running tests for their own sake. If the baseline is red, stop and surface every failing test — silent fixes scope-creep the PR. Acceptable next moves are the same as in step 7: detour first, or explicit user override with a documented reason.
- **Don't silently fix unrelated pre-existing failures.** If the baseline reveals broken tests outside the scope of this issue, surface them — don't fold the fix in without telling the user. It scope-creeps the PR and obscures what your change actually did.
- **Don't push code without running the §8 pre-push verification gate.** The test gate runs at §8 (before the first push) AND at §10.6 (after addressing review feedback). Both are mandatory pre-push gates. On a clean first-pass review approval, §10.6 never fires — the §8 gate is the only test invocation that runs before the PR is opened. Skipping §8's tests on the assumption that "review will catch it" or "pr-evaluator will catch it" is a bug: the `review` skill is a code-quality reviewer that does not run tests, and `pr-evaluator` runs at PR-readiness time *after* the PR is already open with possibly-broken code on the branch.
- **Don't run the full unit + UI suite inside this skill.** This skill runs targeted tests at every gate; the full canonical suite runs in `github-pr-evaluator` (for epic-integration and labelled PRs) and on CI. Reproducing the full suite here defeats the targeted-tests strategy and re-imposes the cost-per-iteration this design exists to avoid. If you find yourself reaching for `<!-- pr-evaluator-static-checks -->` or `<!-- pr-evaluator-test-target -->` from inside this skill, you've drifted off the path.
- **Don't fall back to zero tests when uncertain.** "Zero tests" is reserved for empty-diff and pure-docs paths. Any code change that the sub-agent can't narrow with confidence should hit the project's `broad-change-fallback` (typically "all unit tests, no UI") for the unit target. UI uncertainty defers to pr-evaluator (the `none` broad-change-fallback path) — that's intentional. But never push code with zero tests run on the theory that "pr-evaluator will catch it" when widening was the right call.
- **Don't inline the test-selection reasoning in main context.** The diff hunks, directory listings, and grep output stay inside the `Explore` sub-agent. Main context sees only the resolved `COMMAND:` and the one-line `RATIONALE:`. Inlining the reasoning regresses on token cost and clutters the conversation; pulling diff content into main context is exactly what the sub-agent indirection prevents.
- **Don't skip the rationale audit.** Print the sub-agent's `RATIONALE:` line to the user verbatim before executing the command. The user must see what was selected and why; silent selection is a regression even when correct, and bad selections are how this design fails — make them visible so they can be corrected.
- **Don't let the build subagent become a coder.** When delegating to `apple-platform-build-tools:builder`, the prompt MUST scope the subagent to "run the command and report result" only. No code edits, no failure-investigation expansion, no automatic re-runs with different flags. A subagent that silently turns a 30-second test run into a 55-minute diagnose-edit-rebuild loop hides changes from your commit history and the user's audit trail, and breaks the review-loop's contract that you control when code changes happen. If the build subagent reports a failure, surface it; don't hand it carte blanche to fix things.
- **Don't read only the PR diff.** PR comments and code review threads (especially line-level review comments, which require a separate API call) are where decisions actually got made. Skipping them leads to redoing rejected work or contradicting settled directions.
- **Don't trust the issue title alone.** The title often reflects the original report; the actual problem may have shifted in the comments.
- **Don't re-litigate decided questions.** If a maintainer said "let's go with approach B" three comments ago, go with approach B.
- **Don't post without showing the user first.** Comments and PRs are public and notify subscribers.
- **Don't open a PR for a question.** Some issues are resolved by an answer, not a code change.
- **Don't skip the review loop.** For any PR, `review` must approve before the work is considered done. No exceptions, no "this change is too small to review."
- **Don't exit the loop just because the verdict says "approved".** Reviews routinely approve with `Medium`, `Low`, or `Nitpick` items the reviewer still expects fixed (e.g., "Approved with minor fixes"). Per §10.4, exit only when the verdict is approved **and** zero actionable-now items remain. Items tagged "fast-follow", "follow-up", or "out of scope" are deferred — list them in §11's summary, don't fix them. Items without that routing are addressable in this PR — fix them in-loop, push, and let the next review confirm. Bouncing minor fixes back as a fresh user prompt forces the user to manually re-invoke "address feedback" and defeats the loop's purpose.
- **Don't post review feedback on the issue.** Review feedback on a PR goes on the PR, not on the originating issue.
- **Don't mis-route comments between issue and PR.** Use the rubric in "Where comments go" — problem questions go on the issue, solution questions go on the PR. Cross-posting or wrong-routing fragments the discussion and leaves future contributors hunting.
- **Don't assume the issue is still relevant.** If the thread has gone quiet for a long time, flag this and ask whether to proceed.
- **Don't `git worktree add` a branch that's already checked out.** Git will error. Always run `git worktree list --porcelain` first and reuse the existing worktree if found.
- **Don't nest worktrees.** If you're already inside `.worktrees/foo`, locate the main working tree first (the first `worktree` entry in `git worktree list --porcelain`) and create the new worktree relative to that.
- **Don't forget `.worktrees/` in `.gitignore`.** Without it, every worktree's files show up as untracked in the main checkout's `git status`.
- **Don't auto-clean worktrees.** A worktree may contain unpushed commits or in-flight edits. Cleanup is the user's call.
- **Don't open a single feature PR for an epic.** Epics are containers; child stories are where code lands. Opening a monolithic PR for an epic conflates resolution with implementation and makes the PR unreviewable.
- **Don't target `main` for a story under an open epic.** The whole point of the integration branch is to keep `main` stable while the epic is in flight. If a story PR points at `main`, that defeats the model. The base must be `epic/<N>-<slug>` while the epic is open.
- **Don't let the epic branch drift silently.** Check epic-branch drift on every epic-context run and rebase immediately when drift is found — before any story worktree is created or implementation begins. Use `--force-with-lease` when pushing the rebased epic branch. Long-lived branches that aren't rebased periodically become unmergeable.
- **Don't recompute the epic branch slug — discover it.** The slug rule is deterministic for the bootstrap path, but the epic title can change *after* a branch is created, and a stricter or shorter informal slug rule on a future run silently fails to match. This is exactly how issue #102 was hit: run 1 created `epic/102-visual-redesign`, run 2 computed `epic/102-daily-journal-visual-redesign`, and an exact-match existence check would have orphaned all the story commits already on the original branch. Always discover by prefix (`git ls-remote --heads origin "epic/<N>-*"`) and use whatever name comes back. Recompute only when discovery returns zero matches and you're on the bootstrap path.
- **Don't run epic baseline in the main checkout.** Both bootstrap (first-time creation of `epic/<N>-<slug>`) and legacy recovery (branch exists but no `Baseline established` comment) use a worktree at `.worktrees/epic-<N>-<slug>`. Running the canonical suite in the main checkout would force a `git checkout main`, prevent the user from using the main checkout for unrelated work during the long suite run, and contradict the skill's "main checkout stays untouched" invariant that every other epic and story flow already respects.
- **Don't merge the integration PR without running the review loop.** The integration PR lands the entire epic on `main` at once — it carries more risk than a single story PR. Apply step 10 to it just as you would any story PR.
- **Don't ignore the body checkboxes when closing an epic.** Body checkboxes don't auto-sync. A `- [ ]` next to a closed story is stale and misleads the next person who reads the epic. Always tick them before (or as part of) closing.
- **Don't restructure the epic body template.** The `## Goal` / `## Background` / `## Stories` / `## Definition of done` section names are load-bearing for traceability from `docs/prd.md`. Preserve them exactly.
- **Don't edit a parent epic's body from inside a story-target run.** The epic's body is authoritative state; it should only be updated from an epic-target run where you can see the full story-reconciliation picture.
- **Don't push within the review loop without re-running the full suite.** Same reason as the baseline: the only way to attribute new failures to the right commit is to keep the suite green at every push. Skipping the test run between feedback rounds defeats the green-baseline gate retroactively.
- **Don't skip worktree-setup on the create arm.** A worktree without its setup commands run is in a partially-initialised state — tests may run against missing resources (a simulator that doesn't exist, a port that's already in use, a database that wasn't seeded). Run setup immediately after every `git worktree add` succeeds, before any test, lint, or build.
- **Don't run worktree-setup on the reuse arm.** A reused worktree already has its resources from the original create event. Re-running setup risks double-provisioning: a second simulator alongside the first, a port collision, a fresh database that wipes the worktree's existing state. The reuse arm is a "skip setup" arm by design.
- **Don't auto-clean a worktree without running teardown first.** Teardown releases the resources setup created — orphan simulators, orphan containers, leaked ports — so skipping it leaks them silently. The skill never auto-removes worktrees in any case (manual cleanup is the user's call), but when the user does cleanup, the sequence matters: teardown first, then `git worktree remove`. The §11 reminder names both.

## When to ask the user

Ask before doing significant work when:
- The repo or issue number is ambiguous
- The issue type is genuinely unclear (e.g., "is this a bug or a feature request?")
- The thread shows disagreement between maintainers and you'd be picking a side
- The fix would touch a lot of files or change a public API
- The issue is stale (no activity for a long time) and you're unsure if it's still wanted
- The issue conflicts with the PRD, Architecture doc, or CLAUDE.md (e.g., requests behaviour the constitution forbids or scope the PRD rules out)
- An existing worktree for the target branch is in an unexpected state (uncommitted changes, on a different branch, or otherwise not a clean reuse). A clean tree on the right branch is fine to proceed on without asking.
- A story issue matches multiple parent epics, and it's unclear which one applies.
- A story has no parent epic and you're about to create it as a standalone PR to `main` — surface this so the user can confirm it's not meant to be under an open epic.
- The epic integration branch is significantly behind `main` (enough that a merge conflict is likely) — surface this before creating a new story worktree off the stale epic branch.

Otherwise, proceed and let the user review at the "ready to post" gate.
