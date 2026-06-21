---
name: github-issue-resolver
model: opus
effort: xhigh
description: Investigate and resolve a specific GitHub issue end-to-end via the `gh` CLI. Trigger when the user gives an issue number/URL or asks to "look at", "work on", "fix", "implement", "resolve", "triage", or "respond to" an issue — bugs, features, questions, or refactors. Reads the issue and its full comment thread (separating stale early discussion from latest decisions), on a fresh implementation start audits the issue body for fitness-to-implement (doc tensions, cross-issue contract drift, underspecified contracts) and routes blocker findings to `github-issue-drafter` in revise mode before any code work begins, skips the audit when continuing an in-flight PR, checks for existing open/draft/prior PRs to avoid trampling in-progress work, decides the response type, does the work, and posts a comment or opens a PR. For code changes, opens or continues a PR and loops with the `review` skill until approved. Reads `docs/prd.md`, `docs/architecture.md`, and `CLAUDE.md` to ground implementations. Recognises epics (long-lived `epic/<N>-<slug>` integration branch, child-story audit, integration PR) and stories under an open epic (PR base = epic branch). Use even on casual mentions ("look at #423?", "what is left in the auth epic?") — don't handle GitHub issues without it.
---

# GitHub Issue Resolver

Resolve a GitHub issue by reading it carefully, doing the right kind of work for the issue type, and reporting back.

This skill is the implementation stage of a pipeline: `github-issue-drafter` files the issue, `github-issue-planner` researches and verifies an implementation plan stored as a comment on it, and this skill *executes* that plan. For a non-trivial issue the resolver expects a finalized plan to exist (step 4.6) and treats its decisions as binding — see "Stick to the plan" in step 8. The planner replaces the manual plan-mode step; the resolver no longer re-derives the approach when a plan is present.

### Asking the user a decision

When you need a decision from the user — an approval gate, a choice between named
paths, or a confirmation before a GitHub write — ask it through the `AskUserQuestion`
tool, not as freeform prose. The tool renders the same multiple-choice card every
time, so the user pattern-matches the decision at a glance instead of re-parsing a
differently-worded question on each run.

Shape every ask the same way:
- One decision per question. `header` ≤ 12 chars (e.g. "Post plan", "Merge mode").
  The `question` field carries the full prose you'd otherwise have typed.
- 2–4 options. Each `label` is the action in imperative form ("Post it", "Squash",
  "Approve"); each `description` says what that choice does and its consequence.
- The tool always appends an "Other" free-text choice, so don't pad to four options
  with a catch-all — leave room for the user to type a custom answer.
- `multiSelect: true` only when the choices genuinely combine (rare here).
- Ask once, act on the answer. Don't re-state the same gate in prose afterwards.

When the candidate paths aren't fixed (e.g. "which of these issues did you mean?"),
generate the options dynamically from what you found. When the answer is inherently
open-ended (e.g. "paste any external doc URLs"), a prose ask is still fine — don't
force it into options.

`AskUserQuestion` is not available inside a sub-agent spawned via the `Agent` tool.
Any gate that arises during sub-agent work must be surfaced by the sub-agent
returning a structured "decision needed" signal to this main loop, which asks the
user and re-dispatches with the answer. Never tell a sub-agent to call
`AskUserQuestion` itself.

### Delegating mechanical work to `github-ops`

The expensive model is worth it for the implementation: reading the thread for
the latest decision, the issue audit, writing code, applying review feedback.
The judgment-free GitHub I/O is not — fetching the issue + thread, the open-PR
check, the known-issue triage search, and posting result comments. Delegate
that to the **`github-ops`** sub-agent (`subagent_type: "github-pipeline:github-ops"`,
Sonnet + medium effort — spawn with **no `model` override**): `GATHER_ISSUE`,
`PERSIST_COMMENT` (see `../../agents/github-ops.md`). It writes issue
bodies, threads, and plan-marker bodies **verbatim to per-run scratch files**
and returns `## RESULT` scalars with `*_path` references — `Read` from those
paths to get content. Pass `scratch_dir=/tmp/gh-resolver-<N>/` to every
dispatch so this run's artifacts share a per-issue dir, and reuse the same
dir across the GATHER calls so the resolver can find earlier-fetched content
without re-fetching.

Codebase-precedent searches do **not** go through `github-ops` — it's the
GitHub-I/O executor. For broad searches over the working tree (or an epic
branch via `git grep <pattern> <ref>`), spawn an `Explore` sub-agent with a
focused prompt asking for `path:line-start–line-end` pointers; for narrow
single-symbol lookups, use `Grep`/`Glob` directly.

**What does *not* delegate to `github-ops`:** the `git worktree` lifecycle and all
local `git` work (add/commit/push, diffs, branch resolution) — that is cwd-stateful
and belongs to this skill's main loop. And the existing judgment sub-agents — the
issue **audit**, the **test-selection** `Explore` agent, the
`apple-platform-build-tools:builder` delegation, and the drafter-proxy for
follow-ups — stay exactly as they are; `github-ops` is only for the mechanical
GitHub-API work above.

Like the other sub-agents, `github-ops` cannot call `AskUserQuestion`; on any
ambiguity it returns `DECISION_NEEDED: <…>` and writes nothing — surface it here.
`PERSIST_COMMENT` posts only the body you pass it, after your own gate.

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

**Setup hook on worktree entry.** After every `git worktree add` *and* on every reuse of an existing worktree, run the project's worktree-setup commands (see "Worktree setup & teardown commands" below). Setup must be idempotent by the convention documented in that section; re-running on a healthy worktree is a near-no-op (e.g., reuse the existing simulator UDID when it still resolves, otherwise discard stale state and re-provision). Running on every entry protects against the case where the original create-arm run missed the discovery (a recurring failure mode) or where the worktree's per-worktree state has been lost.

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

**When setup runs.** Immediately after a `git worktree add` returns success **and** immediately after entering a reused worktree at any worktree decision in this skill (§5 takeover, §8 fresh branch, the epic-bootstrap and legacy-recovery flows in "If the issue is an Epic", and the story-worktree creation in "If the issue is a Story"). Setup is idempotent by contract (see "What setup commands typically do" below), so re-entering a healthy worktree costs only the idempotency check. The cost of skipping setup on reuse is far higher: a worktree whose state file is missing for any reason (the original create-arm run missed discovery, a sibling tool deleted it, the user wiped `.worktree-state/`) will silently fall back to whatever global resource the test wrapper's defaults pick, which defeats the per-worktree isolation the hook exists to provide. Run each setup command from inside the worktree (`cd .worktrees/<branch>` first), in declaration order, fail-fast. On failure, surface the failing command and the last 50 lines of its output and stop the workflow — the worktree exists but isn't ready for tests, and silently proceeding would mean running against a missing resource.

**When teardown runs.** This skill never removes worktrees, so it never runs teardown directly. The hook is documented here for symmetry; the executor is `github-pr-evaluator` §14 (the only place a worktree is removed automatically). Step 11's manual-cleanup reminder names the teardown commands and `git worktree remove` together so users running cleanup outside the evaluator know the sequence.

**What setup commands typically do.** Provision per-worktree resources and persist any state the rest of the workflow needs. The skill does not interpret that state — projects use whatever mechanism fits. Common patterns: write a `<worktree>/.worktree-state/<key>` file the project's other commands read; allocate a free port and export it via a `.envrc`; provision a scratch container and record its name. Make setup idempotent against a half-failed prior run so the user can re-trigger without orphan resources.

**What teardown commands typically do.** Release the resources setup created. Read the same state and tear them down. Idempotent and tolerant of missing state — teardown may run on a worktree whose setup partially failed, or which the user has already cleaned up manually.

**Status line announcements.** Setup on a fresh worktree: *"Running worktree setup (N command(s))…"* before the first command; *"Worktree setup complete."* on full pass; *"Worktree setup failed at step i: `<command>`"* with the output tail on failure. Setup on a reused worktree: print *"Running worktree setup (N command(s))… (worktree reused; setup is idempotent)"* before the first command, then the same complete / failure lines as the fresh-worktree case. The reuse variant fires even when setup is a true no-op on a healthy worktree, so users learn that setup ran defensively rather than wondering whether it was skipped. Teardown (executed by the evaluator, but the convention is shared): *"Running worktree teardown (N command(s))…"* / *"Worktree teardown complete."* / *"Worktree teardown step i failed: `<command>`"* — log and continue to the next command.

**No stamp file needed.** The skill ties setup to the worktree-creation event, not to a persistent stamp on disk. If the user manually re-runs setup on a reused worktree (e.g., to recover a lost resource), that's their call — the skill doesn't track it.

## Test selection during iteration

§7 baseline runs the project's static-checks block. **§8 (after the first round of code changes, before the first push) and every §10.6 iteration (after addressing review feedback, before the next push)** run the static-checks block followed by a Claude-selected set of test suites scoped to the diff vs the integration target — this is the **pre-push verification gate** described below. Both gates are mandatory before a push; never push code without one of them having run green. The full canonical suite (every unit test + every UI test) is **not** run inside this skill at any gate. The point of this design is fast feedback during development: a one-Service edit should run that Service's tests, not a 10-minute UI suite.

The full canonical suite still runs in two places outside this skill: **CI on the integration target** (the authoritative answer to "is `main` / the epic branch green?") and **`github-pr-evaluator`** for epic-integration PRs and PRs flagged by the project's escalation-labels block. Pr-evaluator now also runs targeted selection for ordinary story and bug-fix PRs — so don't assume "pr-evaluator will catch it" for cross-cutting changes; CI is the broader safety net.

The bug this design avoids: if the test gate lived only inside §10.6, a clean first-pass review approval (review approves without requesting changes) would skip §10.6 entirely and a PR would land with zero tests run beyond static checks. §8 closes that gap.

**These conventions apply only when step 7 applies.** Comment-only flows (questions, blocked issues, duplicates, doc/typo edits) skip steps 7/8/10/11 entirely and use none of this.

### Project-side blocks the skill reads

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

<!-- issue-resolver-canonical-suite -->
- full-suite: `<one-shot canonical command>`
- build-once: `<compile-the-test-bundle-once command>`
- retry-without-rebuild: `<re-run-without-recompile command>`
<!-- /issue-resolver-canonical-suite -->
```

All three blocks are delimited by HTML comments (invisible in rendered Markdown) and are discovered by scanning `COMMANDS.md` and `CLAUDE.md` at the repo root, plus any file `@`-included from either.

- **`issue-resolver-fast-checks`** = a fail-fast list of static commands (codegen, dependency resolution, lints, layer-import boundary checks, etc.). One Markdown list entry per command, backtick-quoted, followed by ` — ` and a short description. **No test invocations belong in this block** — tests are handled separately by the test-target block below.
- **`issue-resolver-test-target`** = configuration for the test-selection sub-agent (see next section). Prose-structured Markdown — read it as natural language; don't try to parse it. Used at the §8/§10.6 *story* gates for **targeted** selection only.
- **`issue-resolver-canonical-suite`** = the **full** canonical-suite commands, read by the epic-baseline / bootstrap / post-rectification flow only (see "Running the full canonical suite" below). Three labelled commands: `full-suite` (one-shot, single cold build), `build-once` (compile the test bundle once), `retry-without-rebuild` (re-run after `build-once` with no recompile). **Fallback if absent:** use `pr-evaluator-test-target`'s `full-suite-command` for the one-shot run; if that is also absent, fall back to the bare-prose "run the project's full canonical suite" and ask the user for the command rather than inventing a plain `test`-action invocation (a plain `<wrapper> test` cold-rebuilds the app target on every run). Without this block there is no declared `build-once`/`retry-without-rebuild` command, so re-runs will cold-rebuild — note this to the user so the project knows to declare the block.

Read these blocks once at the start of step 7 and remember them for the rest of the run.

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

**See [`references/test-selection-sub-agent.md`](references/test-selection-sub-agent.md) for the full prompt template** (inputs schema, heuristic steps 1–6, the UI blast-radius rules at step 5, and worked-example output shapes). Substitute the worktree path, integration target, and the `<!-- issue-resolver-test-target -->` block contents at dispatch time. The sub-agent returns two sections with literal headers `COMMAND:` and `RATIONALE:`.

The skill parses these two sections and proceeds:
- `COMMAND: (none)` → skip test execution entirely; print the rationale to the user; mark the iteration's test status as "skipped (no tests selected)" and continue.
- `COMMAND: <shell command>` → print the rationale to the user; delegate execution per the next section.

### Test execution — Apple-platform subagent delegation

If the resolved command begins with `xcodebuild` (or invokes a wrapper that runs `xcodebuild`, like `./scripts/xcb.sh`), delegate execution to the `apple-platform-build-tools:builder` subagent. The subagent absorbs the verbose build log and returns terse pass/fail plus the first error if any — keeping conversation context clean. Non-xcodebuild commands (e.g., `pytest`, `go test`) run inline. **Exception:** the *full* canonical suite in the epic-baseline / bootstrap / post-rectification flow is **not** delegated to the builder — it is a 15–30 min run owned by the main loop; see "Running the full canonical suite" below.

**Bound the subagent's scope explicitly when invoking it.** The subagent is a build-runner, not an autonomous coder. Its job for this delegation is narrow and one-shot: run the command exactly as given, capture the result, and return pass/fail plus the first error if any. It must not edit code, "fix" failures it diagnoses, re-run with different flags, or expand scope. Build/test failures bubble back to this skill — the calling workflow decides next steps. A silent diagnose-and-fix loop inside the subagent breaks the review-loop's visibility into what changed and why, hides edits from the user's audit trail, and uncaps the wall-clock cost of a single delegation. State the constraint in the prompt you hand to the subagent; don't assume it.

Concretely, the prompt should look like: *"Run this exact command from this exact directory: `<command>` (cwd: `<worktree path>`). Absorb the log. Return pass/fail plus, on fail, the first error and the failing test name(s). Do not edit any source files. Do not re-run with modified flags. Do not investigate failures beyond identifying them. If the test fails, the calling skill will handle next steps."*

This mirrors `github-pr-evaluator` §5.5.3. The targeted-tests strategy means each invocation runs only the selected suites, so the build log per iteration is much shorter than a full-suite run anyway — but the delegation layer is still useful and keeps the convention consistent across both skills.

### Running the full canonical suite (epic baseline / bootstrap / post-rectification)

This subsection applies **only** to the epic-baseline, bootstrap, and post-rectification flows in "If the issue is an Epic" — the places that legitimately run the project's *full* canonical suite (every unit + UI test) in a worktree. It does **not** loosen the §8/§10.6 story gates, which stay targeted-only (see "Don't run the full unit + UI suite inside this skill" in Common pitfalls). It exists because a full-suite run is a 15–30 minute, cold-build-bearing operation, and three foot-guns turned one such run into a multi-hour hang in the past.

**1. Which command — never improvise it, and never cold-rebuild on every attempt.** Read the project's `issue-resolver-canonical-suite` block (per "Project-side blocks the skill reads" above) and use its labelled commands:

- **First attempt** → `full-suite` (one cold build + every suite).
- **Any re-run** (the first run's result was lost or partial, or you're re-running specific failures) → `build-once` **once**, then `retry-without-rebuild` (append `-only-testing <Suite>/<test>` to re-run only the failures). Do **not** re-issue `full-suite`.

The reason is wall-clock: a plain `<wrapper> test` recompiles the whole app target on every invocation, and that cold build — not the tests — dominates the time. Re-paying it on each retry is what produced the past hang. If the block is absent, fall back as described in "Project-side blocks" (pr-evaluator `full-suite-command`, then prose + ask) and tell the user retries will cold-rebuild until the block is declared.

**2. Make it survive across turns — own it from the main loop.** A 15–30 min suite must be run as a **harness-tracked background bash** (`run_in_background: true`) owned by *this* main loop, not delegated to the `apple-platform-build-tools:builder` sub-agent. A sub-agent can end its turn while `xcodebuild` is still running and then have its session torn down, orphaning the process and losing the final tally (this is exactly what happened — the builder returned a partial snapshot and the run was lost). The harness auto-notifies you when a background bash completes, and the process survives across turns because the parent owns it. Keep the builder delegation (line ~332) for the *short targeted* suites at §8/§10.6 only — the full canonical suite is the documented exception.

**3. cwd / command hygiene for the backgrounded command.** Two rules, both learned the hard way:

- **Use absolute paths; never chain the real command behind a relative `cd … &&`.** The skill's shell cwd may already be the worktree (cwd persists between Bash calls), so a relative `cd .worktrees/<branch> && …` *fails* — and `&&` then silently short-circuits the whole command to a no-op that exits `0`, so it looks like the suite passed when nothing ran. Resolve an absolute worktree path into a variable and `cd "$WT"` on its own line, or pass the command's directory explicitly.
- **Capture to files and read the file — don't re-run to see output.** Tee the full log to one file and a one-line pass/fail summary to another; on the completion notification, read the summary file. Re-running a 15–30 min suite just to see scrolled-off output is the same wasted cost the build-once rule exists to avoid (mirrors `COMMANDS.md`'s live-test "always re-read the log; never re-run" guidance).

## Retry ladder for the verification gate

The pre-push verification gate (§8 before the first push, §10.6 after each round of review feedback) caps a single visit at **3 test runs total** with a forced research breakpoint between cheap fixes and any deep fix. Run 1 includes the unrelated-failure triage (cheap `gh issue list` lookup before spending the fix budget); run 2 enforces the adaptive cheap-fix rule (sticky failures force the breakpoint immediately); run 3 is the research-informed deep fix. When run 3 is also red, escalate via `AskUserQuestion` (`header: "Tests red"`) with three options: **Push with reds** / **Defer the tests** / **Restructure**. Each entry to §8 or §10.6 starts a fresh ladder.

**See [`references/retry-ladder.md`](references/retry-ladder.md) for the full ladder, triage rules, adaptive-fix rule, research breakpoint, and escalation rubric.**

## Follow-up issue tracking

Follow-up items surface at four moments — §7 baseline detours, the retry-ladder's escalation option 2, §10.4 reviewer-routed deferrals, and §11 summary cleanup. The registry has five fields (`type`, `title hint`, `description`, `parent reference`, `urgency`). Filing decision rule: trackable work → file as an issue via the drafter-proxy sub-agent protocol; procedural / informational notes → capture in the PR body or §11 summary instead. Urgency `file-now` items must land before the iteration's push (so `// TODO(#NNN)` markers and `XCTSkip("Deferred to #NNN — …")` reasons reference real issue numbers); urgency `file-at-checkpoint` items batch at end-of-§10 before §11 fires. Every filed issue routes through `github-issue-drafter` (PRD-grounded, sub-agent-reviewed) — no hand-crafted `gh issue create` bodies. After filing, weave the URL into the code's TODO/XCTSkip markers, the PR body's `## Follow-ups` section, and §11's summary.

**See [`references/follow-up-tracking.md`](references/follow-up-tracking.md) for the full registry schema, filing-vs-capturing rule, hybrid timing table, end-of-§10 checkpoint, and the drafter-proxy sub-agent prompt.**

## Workflow

### 1. Identify the issue

The user will give you an issue number (`#423`), a URL (`https://github.com/owner/repo/issues/423`), or both. Extract:
- The issue number
- The repo (from URL, current git remote, or user-supplied `--repo`)

If ambiguous (e.g., they said "issue 42" but you're in a monorepo or there's no obvious repo context), ask once before proceeding.

### 2. Fetch the full issue context

Delegate the fetch to `github-ops` so you pull the issue, all comments, the linked/closing PR references, and any open PR in one pass:

> `GATHER_ISSUE(issue=<number>, repo=<owner/repo>, marker_prefix="<!-- implementation-plan:v1 -->", extra_json="closedByPullRequestsReferences,projectItems", scratch_dir=/tmp/gh-resolver-<number>/)`

`scratch_dir` is the per-run dir convention from commit 567e829 — routing the body / thread / plan-marker through it is what keeps large issues (epics, long-marker stories) from burning minutes in spill-and-reread on the github-ops side. The `## RESULT` envelope carries scalars + path references — `issue_body_path`, `thread_path`, `marker_comment_path` (when a plan marker exists) — plus `closingIssuesReferences`, the open-PR list, and any `extra_json` fields. **Read the body and the thread from the returned paths** when you need their content; github-ops doesn't echo them inline.

The marker_prefix lookup matters here too: the plan comment is the canonical source for the implementation approach. Read it (via `marker_comment_path`) before forming any opinion on what "resolving" the issue means. The explicit open-PR search matters because `closedByPullRequestsReferences` only covers PRs that *would close* the issue (and only when the linkage syntax was used) — open/in-progress PRs by other contributors often won't appear there, so `github-ops` runs the `gh pr list … "<number> in:body"` search alongside it.

Read everything before forming an opinion. Long threads matter — the original post is often outdated by the time someone asks you to work on it.

### 3. Determine the current state

This is the most important step. After reading the thread, explicitly identify:

- **Latest decision or direction** — what's the most recent substantive comment that shifts the plan? Treat earlier proposals as superseded if a maintainer or the OP has agreed to a different approach.
- **Open questions** — anything the thread is waiting on (clarification, design decision, third-party action).
- **Already-tried approaches** — work that's been attempted and rejected. Don't re-propose these.
- **Who's blocked on what** — is the issue blocked on the user, on a maintainer review, on an upstream dependency, or ready to be worked?
- **Issue type** — bug / feature / question / refactor / discussion / duplicate / **epic** / **story**. This determines what "resolved" means.
- **Epic / Story detection.** Check the issue's `labels` array:
  - Label includes `epic` (case-insensitive) → or title starts with `Epic:` → treat as an Epic; run step 4.5 (audit) first, then skip to the "If the issue is an Epic" section.
  - Label includes `story` → treat as a Story; run step 4.5 (audit) first, then skip to the "If the issue is a Story" section.
  - Neither → continue with the standard workflow.
- **Early branch discovery.** §4.5's audit sub-agent reads code and docs from a specific git ref (see "Audit ref derivation" in §4.5), and that ref needs to be known *before* the audit fires. The discovery calls that historically lived inside the Epic / Story sections — `git ls-remote --heads origin "epic/<N>-*"` for Epic-as-target, and the parent-epic search (`gh issue list --label epic --state all --search "#<N> in:body"`) followed by `git ls-remote` for Story under-an-open-Epic — run here, at issue-type determination time, so §4.5 has the branch name in hand. The downstream "If the issue is an Epic" / "If the issue is a Story" sections continue to reference the discovery rules ("Resolving the epic branch name", parent-epic search) — when discovery has already run here, those become no-ops that reuse the recorded name. Multi-match clarification prompts and zero-match handling stay exactly where they're documented in those sections; the only change is *when* discovery executes.

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

### 4.5 Audit the issue is fit to implement

Before any worktree is created, any baseline is run, or any code is written, audit the issue body for fitness-to-implement. The drafter's review loop catches incoherent issues at filing time; this audit catches the analogous problems that accumulate **after** an issue is filed — doc drift, code drift, the latest comment-thread direction not folded back into the body, and (for Epics) sibling stories that have drifted away from each other on field names, signatures, and contract surfaces. Catching these before a worktree exists is dramatically cheaper than catching them mid-implementation, mid-review, or at integration time.

The motivating case that triggered this gate: a workshop session on Epic #119 surfaced 8 cross-issue contract drifts (field-name mismatches, signature disagreements, missing entries in a closed-set enumeration) plus 3 doc tensions plus 4 underspecified contracts — all in issue bodies that looked filed-and-ready until read side-by-side against the project's docs and the sibling stories. If the resolver had started implementation work on any of those stories without the audit, the drifts would have surfaced as confused review comments or a broken integration — at a much higher per-finding cost than fixing the bodies up front.

**The audit only fires on a fresh implementation start.** Once a PR is open against this issue, the issue body is no longer the document being acted on — the PR is. Re-invocations of the resolver during the review loop, pushes addressing review feedback, and other continuations of in-flight work skip the audit entirely. The gate below uses the existing-PR signals step 2 already fetched (`closedByPullRequestsReferences` and the `gh pr list ... in:body` result) to decide — no new `gh` calls. Each decision is logged to the state summary so a future invocation can see why the audit ran or didn't.

| Pre-audit signal (from step 2's already-fetched data) | Audit fires? | State-summary line |
|---|---|---|
| Issue is an Epic (any label match per step 3's Epic/Story detection) | **Yes** | `Audit: firing (Epic-as-target run); audit_ref=<ref>` — Epic bodies + sibling Story bodies drift constantly between visits; dimension 5 is the value-add on every Epic visit. |
| No open or draft PR references the issue, and `closedByPullRequestsReferences` is empty or holds only closed/abandoned PRs | **Yes** | `Audit: firing (no prior PR); audit_ref=<ref>` — fresh implementation start. |
| Closed/merged PR exists but did **not** resolve the issue (partial fix, reverted, abandoned, per step 5's table) | **Yes** | `Audit: firing (fresh attempt over abandoned PR #M); audit_ref=<ref>` — treat as fresh. |
| Open or draft PR by **you**, referencing this issue | **No** | `Audit: skipped (continuing PR #M)` — step 5 will route to "continue existing PR" → worktree reuse. |
| Open or draft PR by **someone else**, referencing this issue | **No** | `Audit: skipped (competing PR #M by @other)` — step 5 will surface the PR to the user; no implementation will start in this run. |

If the gate skips, fall through to step 5 immediately — do not show the user any audit-related prompt (no "skip audit" question, no findings, no override choice). The gate's decision is the answer. If the user explicitly asks for an audit anyway (e.g., "audit #N even though there's an open PR"), re-fire by hand using the same prompt template; that's an explicit user request, not the default flow.

**When this step applies (after the gate fires).** Code-change response types only — bug / feature / refactor / Epic / Story. Skip for comment-only responses (question, blocked-on-info, duplicate, already-fixed); there is no implementation to be unfit for.

**Audit ref derivation.** The audit sub-agent reads code and docs from one specific git ref — not from the orchestrator's working tree. The orchestrator's cwd is typically the main checkout sitting on `main`, but the issue's *integration target* may be a different branch (an epic branch, for example). Without an explicit ref, the audit reads from whatever the working tree happens to hold and fabricates BLOCKERs against symbols that exist on the actual integration branch — exactly the failure mode the Epic #154 run surfaced (audit grepped `main`, missed every epic-branch symbol). Derive `audit_ref` from issue context already known at this point:

| Issue context | `audit_ref` |
|---|---|
| Bug / feature / refactor, no Epic context | `origin/main` |
| Epic-as-target | `origin/<branch>` — the name discovered in step 3's "Early branch discovery" via `git ls-remote --heads origin "epic/<N>-*"` |
| Story under an open parent Epic | `origin/<parent-epic-branch>` — the parent Epic's branch, discovered in step 3 alongside the story-type determination |
| Story with no parent Epic, or parent Epic is closed | `origin/main` |

If step 3's discovery hit the zero-match path for an Epic-as-target run (no `epic/<N>-*` branch on origin yet — bootstrap path), the audit still runs, with `audit_ref=origin/main`: the bootstrap epic branch would be created off `origin/main` anyway (per "If the branch does not exist on origin"), so the integration target is `main` at the time the audit fires.

**Pre-dispatch fetch.** `git show <ref>` and `git grep … <ref>` require the ref locally. Before spawning the sub-agent, fetch the chosen branch:

```bash
git fetch --quiet origin <branch-from-audit-ref>
```

A failed fetch (network unavailable, ref doesn't exist on origin) is surfaced to the user and aborts the audit — the same shape as the existing `git fetch` calls in the Epic flow. Don't fall back to a stale local ref silently; the audit's correctness depends on reading the tip of the integration target.

**Sub-agent invocation.** Spawn an `Explore` sub-agent with the prompt template at `references/issue-audit-prompt.md`. Inline the placeholders:

```
Agent({
  subagent_type: "Explore",
  description: "Audit issue fitness-to-implement before code work",
  prompt: <contents of references/issue-audit-prompt.md
           with placeholders filled: issue_number, issue_type, repo_owner,
           repo_name, repo_root, dimensions, related_issues, audit_ref>
})
```

The sub-agent runs **without** the conversation history, the user's task description, or the state summary from step 3 — same isolation rule the drafter uses, same justification: if the sub-agent can't tell whether the issue is implementable using only the body + docs + codebase + sibling-issue content, neither can a developer picking it up cold. Leaking conversation context into the audit defeats the gate's purpose.

**Dimensions to pass.** Six are defined in the prompt; pass the subset that applies to the issue type:

| Type | Dimensions passed |
|---|---|
| Bug | 1, 2, 3, 4, 6 |
| Feature / refactor | 1, 2, 3, 4, 6 |
| Epic | 1, 2, 3, 4, 5, 6 (with every child Story body in `related_issues`) |
| Story under open Epic | 1, 2, 3, 4, 5, 6 (with parent Epic + every sibling Story body in `related_issues`) |
| Story with no parent Epic | 1, 2, 3, 4, 6 |

Dimension 5 (cross-issue contract drift) only fires when sibling content is passed in — it's the dimension the drafter's reviewer doesn't carry, because at draft time siblings don't exist yet. Dimension 6 (implementation readiness) flags vague placeholders, undefined field shapes, undefined enum cases, and missing layer-boundary assignments — the bar is *implementable*, not just *file-able*.

**Loop control.** Same shape as the drafter's review loop:

```
prev_findings = []
for pass in 1..3:
  findings = audit_sub_agent.run(issue_number, type, dimensions, related_issues)
  drop_findings_without_evidence(findings)
  if findings is empty:
    exit_clean()
    break
  if same_finding_repeated_with_no_progress(findings, prev_findings):
    exit_circular(findings)
    break
  # Unlike the drafter, the resolver does NOT apply findings itself.
  # Surface them to the user and route to the drafter (see "Surfacing findings" below).
  remediation_result = route_to_user(findings)
  if remediation_result == "drafter_completed":
    # Drafter has filed gh issue edit; refetch and re-audit
    prev_findings = findings
    continue
  else:
    break  # user overrode, aborted, or chose "proceed with these findings"
else:
  exit_cap_reached(findings)
```

The cap and circular guard exist for the same reason as in the drafter: don't iterate forever on a finding that's either wrong, unactionable, or needs human judgment.

**Surfacing findings.** Classify the audit run before deciding what to do:

- **Gated off** — the pre-audit gate above decided not to fire (continuing your own PR, competing PR by another author, or comment-only response type). The state-summary line was already recorded by the gate. Continue to the original fork (step 5 / Epic flow / Story flow) without prompting the user about the audit.
- **Clean** — audit fired and returned zero findings after evidence-filtering. Print one line in the state summary: `Audit: clean (N pass(es))`. Continue to the original fork (step 5 / Epic flow / Story flow).
- **Suggestions / nits only** — print the findings inline (severity, dimension, evidence, recommended remediation) but continue without stopping. The user can interrupt the run if any look load-bearing on second read.
- **One or more BLOCKERs** — **stop**. Print every finding with severity, dimension, the affected issue number (for Epic / Story modes, dimension 5 findings name the sibling issue where the conflict lives), evidence, and recommended remediation. Then ask via `AskUserQuestion` (header "Audit"; present the default option first): **Revise via drafter** / **Override w/ reason** / **Abort** — each detailed below:

  1. **Revise via drafter** *(default)*. Invoke the sister skill `github-issue-drafter` via the `Skill` tool with arguments shaped like `revise #N — apply these audit findings: <evidence block>`. The drafter runs its own review loop on the proposed revision, shows the user a diff, files `gh issue edit` on approval, and returns. Then refetch the issue (`gh issue view <N> --comments --json …`) and run the audit again from pass 1. If the audit was on an Epic and dimension 5 found drift across multiple sibling Stories, route the drafter sequentially per affected issue — Epic body first if its contract is the source of truth, then each affected Story — so each drafter handoff is one issue at a time (mirrors how the user-led workshop session for Epic #119 proceeded: one `gh issue edit` per issue, in topological order). After all handoffs land, refetch every affected issue and re-audit.

  2. **Override and proceed.** The user states a one-sentence reason. Record the override in the state summary as `Audit override: <reason>`. Append the same line to the eventual PR body in step 9 under an `## Audit override` section so the override is visible to reviewers in the PR. Blockers don't disappear with this option — they become documented technical debt routed through PR review.

  3. **Abort.** The resolver stops. No worktree is created. No code work begins. Tell the user the audit's findings are the artifact of this run.

**The user-override skip.** For trivial issues (a one-line typo fix, a small bug fix where the user has confidence the body is fine), the audit is overhead. If the user replies `skip audit` (or `bypass audit`) at the gate prompt — or has said as much before this point — record `Audit skipped by user override` in the state summary, surface it in the step 11 summary so it lands in the PR body alongside any other overrides, and continue. The skip is durable for this run only; a re-invocation re-runs the audit from scratch.

**Cap-reached exit handling.** If three passes complete and findings remain (some types of drift are hard to fully express in body text — they may need a code-side decision before the body can be specified), surface the remaining findings to the user the same way as a blocker exit. The same three choices apply.

**Where the audit ends and step 4.6 begins.** A clean audit (or a recorded override / skip) is the precondition for everything after this point. Next, step 4.6 requires a finalized implementation plan on the issue. Step 5 (existing-work check) and step 6 (doc grounding) then inherit the post-audit issue body — step 6 in particular cites the doc sections that informed the approach, which is a different artifact from the audit's findings table. The work is sequential: audit catches drift, the plan gate confirms a vetted approach exists, step 6 writes the doc-grounding statement for the PR body. Do not skip step 6 on the assumption that the audit's dimension-1 findings already cover doc grounding — they cover *tensions*, not *citations*.

### 4.6 Require a finalized implementation plan

The approach for a non-trivial issue should be worked out and verified *before* code work begins, not improvised mid-implementation. That planning is owned by the sister skill `github-issue-planner`, which researches the approach, grounds it in the docs and codebase precedent, verifies it with an isolated reviewer, and stores it as a durable comment on the issue. This gate makes the resolver **consume** that plan rather than re-derive the approach itself — the planner replaces the manual planning step. When a plan exists, you execute it; when it's missing on a non-trivial issue, you stop and ask for one.

**When this gate fires.** Same shape as the §4.5 audit gate, using the existing-PR signals step 2 already fetched — no new `gh` calls:

| Pre-gate signal | Gate fires? |
|---|---|
| Fresh implementation start (no prior PR, or only closed/abandoned PRs) | **Yes** |
| Epic-as-target, or Story under an open Epic | **Yes** — consume the epic-level plan and/or this story's plan |
| Open/draft PR by **you** (continuing) | **No** — the plan was consumed when work began; the PR is the artifact now |
| Open/draft PR by **someone else** | **No** — step 5 surfaces it; no implementation starts this run |
| Comment-only response (question, blocked, duplicate) | **No** — nothing to plan |
| Trivial change (one-line fix, typo, pure doc edit) | **No** — these legitimately need no plan |

**Fetch the plan comment** by its marker:

```bash
gh api "repos/<owner>/<repo>/issues/<N>/comments" \
  --jq '.[] | select(.body | startswith("<!-- implementation-plan:v1 -->")) | {id: .id, url: .html_url, body: .body}'
```

**If a plan is present.** Parse it. The plan's `## Doc grounding` and `## Architecture decisions` are the design authority for this issue and **supersede** step 6's re-derivation — lift the grounding statement from the plan instead of re-deriving it (step 6 becomes "confirm and cite the plan's grounding," not "plan from scratch"). The plan's `## Architecture decisions`, `## Changes`, `## Data model / schema impact`, and `## Test plan` are the **locked decisions** you implement against. Record in the state summary: `Plan: present (<plan-comment-url>), planned at <sha>`.

Then run a **plan-currency check** before trusting it. The plan records the SHA it was built against; the code may have moved since:
- Compare the plan's recorded SHA to the current integration-target HEAD (`main`, or the epic branch for a story).
- Spot-check that the files/symbols the plan's `## Changes` names still exist and still have the shape the plan assumes (`git grep`/`git show` against the integration target).

If the plan is materially stale (the code it depends on has drifted, or the issue body has been revised in a way the plan predates), **don't silently proceed** — surface the drift and offer to route back to the planner in revise mode (invoke `github-issue-planner` via the `Skill` tool with `re-plan #N — the codebase/issue moved since the plan: <evidence>`), then re-fetch the refreshed plan. A clean currency check → proceed to step 5.

**If a plan is missing on a non-trivial issue.** Stop. Tell the user:

> "No finalized implementation plan on #N. Run `github-issue-planner` first and I'll execute it — or reply `proceed without a plan` to skip planning for this run."

- **User runs the planner** → re-fetch the plan comment and continue.
- **User overrides** (`proceed without a plan`) → record `Plan override: <reason>` in the state summary and carry it into the PR body under a `## Plan override` section in step 9 (mirrors the §4.5 audit-override mechanic), so the missing-plan decision is visible to reviewers. Then fall through to step 6's full doc-grounding re-derivation, since there's no plan to lift it from.

Don't apply this gate to comment-only flows or trivial fixes — there's nothing to plan, and a forced gate there is pure friction.

### 4.7 Detect a multi-phase issue from the plan

Some non-trivial issues split into a sequence of phases that share one issue and one branch — the canonical case is a measurement spike (substrate → harness → operator measurement → decision write-up), but any issue whose DoD takes several distinct deliverables shaped like "first land X, then run Y, then post Z" lives here. Multi-phase work is **not** an Epic (Epics fan out into child story issues; the integration branch is long-lived; one PR per story); it is a single issue whose work accumulates on **one PR**, in **draft**, until the planned phases are exhausted. The pattern emerges from the plan, not from the issue body's shape or labels — so this gate runs only after step 4.6 has consumed the plan.

**When this gate fires.** Same plan-presence shape as §4.6: it runs only when a plan was consumed (skipped on `Plan override`, trivial flows, comment-only responses, continuations of an existing PR — the plan was already classified when that PR's first phase opened).

**Detection.** Read the plan's `## Phases` section (the structured-bullet shape defined by `github-issue-planner` Step 7's schema):

- **`## Phases` is absent** → single-phase issue. Continue with the standard flow; nothing in §5/§8/§9/§11/§12 changes for this run.
- **`## Phases` is present and contains a single phase** → also single-phase. The planner emitted the section but the work doesn't actually fan out. Continue with the standard flow.
- **`## Phases` is present with two or more phases, of which at least two are `kind: code-shipping`** → **multi-phase issue.** Parse the section into the in-memory phase list described below and proceed; the multi-phase branches in §5/§8/§9/§11/§12 fire from here on.
- **`## Phases` is present but malformed** (missing required keys, free-form prose under the header instead of structured bullets, `closes-dod` references that don't resolve to issue-body DoD bullets) → stop and route back to `github-issue-planner` in revise mode, the same way §4.6 routes plan-currency drift. The resolver depends on the structured shape to route phases; hand-waving past a malformed `## Phases` re-introduces exactly the silent-misrouting failure mode this gate exists to prevent.

**Phase list captured.** When the gate identifies a multi-phase issue, capture the parsed list once and carry it through the rest of the run. Each entry holds: `number` (1-based), `title`, `kind` (closed enum: `code-shipping` | `operator` | `decision-only`), `ships`, `closes-dod` (list of DoD-bullet indexes), `deliverable`, `depends-on`. Record the multi-phase mode in the state summary: `Multi-phase: <N> phases (<code-count> code-shipping, <op-count> operator/decision)` and name which phase this run will execute (the lowest-numbered phase whose `depends-on` is satisfied and whose deliverable hasn't shipped — read the existing PR's `## Phase tracker` if a draft PR exists from a prior phase).

**The current-phase decision is yours, not the planner's.** The plan declares the phase **menu**; the resolver picks the next item off it based on what's actually shipped. A re-invocation of the resolver on a multi-phase issue with an existing draft PR re-reads `## Phase tracker` to decide where to resume — see §5's branch-reuse rule below.

**Re-entry DoD-projection reconciliation.** On every re-entry where a prior phase has shipped (multi-phase) — or a single-phase PR was previously opened (re-invocation) — reconcile the issue body's `## Definition of done` ticks against the authoritative state before continuing. This catches `gh issue edit` failures from prior runs and applies missing ticks idempotently.

1. Enumerate ticked phases from the PR's `## Phase tracker` (already cached from step 2's open-PR check). For each `- [x]` row, record its phase number and either its commit SHA (code-shipping) or its operator-action date (operator/decision-only).
2. Compute the expected DoD-bullet set: union of `closes-dod` indexes across every ticked code-shipping or operator phase. When the plan has no `## Phases` (single-phase) or a single entry that already shipped, the expected set is **every** top-level DoD bullet (single-phase fallback).
3. Read the issue body's `## Definition of done` from `GATHER_ISSUE`'s `issue_body_path`. Parse top-level checkbox bullets (1-based; sub-bullets are detail, not DoD items). For each expected bullet currently `- [ ]` **and** not carrying an evaluator-rejection annotation `(resolver claimed phase <N>, ...; evaluator rejected: ...)`, this is reconcilable drift — the prior phase's projection failed to land.
4. If any drift exists, write the projected body to `/tmp/gh-resolver-<N>/issue-body-projected.md` and apply via `gh issue edit <N> --repo <owner/repo> --body-file /tmp/gh-resolver-<N>/issue-body-projected.md`. Record in the state summary: `DoD reconciliation: applied <K> missing tick(s) from prior phase(s)`.
5. If no drift, record `DoD reconciliation: in sync`. **Never un-tick.** Bullets that are `- [x]` but not in the expected set are left alone (likely a human edit or plan-revision residue) and flagged as `DoD reconciliation: unexpected tick on bullet <N> (<text excerpt>) — left as-is`.

**Defensive re-plan drift detection.** After step 5, walk currently-ticked bullets one more time and compare each annotation's phase reference against the captured phase list (see [`../_shared/dod-annotations.md`](../_shared/dod-annotations.md) for the annotation parser). For each `(closed by phase <N>, ...)` annotation: if the captured phase list contains a phase numbered `<N>` and its `closes-dod` includes this bullet's index → consistent. Otherwise → drift. Drift cases:

- The annotated phase number doesn't exist in the captured phase list (phase removed or renumbered by a prior re-plan).
- The annotated phase exists but its current `closes-dod` no longer includes this bullet's index (reassignment).

Record drift in the state summary as `DoD re-plan drift: <K> annotation(s) reference phases the current plan no longer claims this bullet for — re-run \`github-issue-planner revise\` to reconcile`. **Do not auto-mutate the body.** The deliberate reconciliation path is the planner's "Re-plan reconciliation" (it handles the user-engaged classification + apply at step 9); this defensive layer is a backstop that catches cases where the planner's body-edit failed or where the user bypassed the planner by hand-editing. If drift is present, continue with the run — projection of the current phase still applies — but the user sees the flag and knows to re-run the planner.

Reconciliation is read-only on routing — it never influences which phase ships next. The Phase tracker remains the single source of truth for "where to resume." See "DoD projection rule" in §9 for the projection mechanism that fires on each new push, and the boundary statement near §11 for the resolver/evaluator split.

## If the issue is an Epic

Epics use a consistent body template: `## Goal`, `## Background`, `## Stories` (a markdown task list of `- [ ] #NN — description` lines), `## Definition of done` (a second task list), and occasionally `## PRD impact`. There are no native GitHub sub-issues — child relationships exist only as `#N` references inside these task lists.

**Resolving the epic branch name.** Both the epic-as-target flow and the story flow need to refer to the integration branch by name. The branch follows the pattern `epic/<N>-<slug>`, but the slug is derived from the epic title — and titles can shift, slugging conventions can be ambiguous, and two runs computing slugs independently have already produced divergent names (issue #102: run 1 picked `visual-redesign`, run 2 picked `daily-journal-visual-redesign`, which would have orphaned the original branch). To prevent that class of bug, **discover the existing branch by prefix; only compute a fresh slug on the bootstrap path.**

**Discovering an existing epic branch.** Run:

```bash
git ls-remote --heads origin "epic/<N>-*"
```

- **One match** → use that branch name verbatim for every subsequent command in this run (worktree paths, fetch targets, push targets, `--base`, PR body references, the legacy-recovery worktree). If you need a slug for a worktree directory, extract it from the actual branch name. **Do not recompute it from the title.**
- **Zero matches** → the integration branch hasn't been bootstrapped. Continue per "If the branch does not exist on origin" below (epic flow) or the existing stop-and-redirect message (story flow).
- **Multiple matches** → ask via `AskUserQuestion` (header "Epic branch") which is canonical, with one option per candidate branch (label = the branch name, description = its last-commit date and author so the user can tell them apart). Multiple matches usually indicate an orphaned bootstrap or a hand-created branch; silently picking one risks landing work on the wrong branch. Stop until the user resolves it.

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

This is the only path in the skill that rectifies epic-vs-main drift (by rebase or by merge — see "Choose strategy" below). Story runs under this epic surface drift as an informational state-summary note but never act on it (see "If the issue is a Story" → "Determine the PR base").

If the epic branch is behind `main`, rectify this before proceeding — story work landing on a stale epic branch will inherit the drift and make the integration PR harder to merge. The procedure is **assess → choose strategy → execute**. Rebase and merge are both first-class strategies; the choice is rule-driven with the user able to override.

**Assess before rectifying.** Gather the signals that decide between rebase and merge:

```bash
# Commits the epic is behind main by (already computed above; reuse).
COMMITS_BEHIND=$(git rev-list --count origin/epic/<N>-<slug>..origin/main)

# Fork point.
FORK_POINT=$(git merge-base origin/main origin/epic/<N>-<slug>)

# Has main been merged into the epic before? (Consistency signal.)
PRIOR_MAIN_MERGES=$(git log --merges "$FORK_POINT"..origin/epic/<N>-<slug> \
  --grep="Merge.*main\|Merge branch 'main'" --oneline | wc -l | tr -d ' ')

# Open story PRs against this epic — rebasing force-pushes the base they target.
OPEN_STORY_PRS=$(gh pr list --repo <owner/repo> --base epic/<N>-<slug> \
  --state open --json number,headRefName,author,url)

# File overlap between the two diverged diffs (predicts conflict surface).
EPIC_FILES=$(git diff --name-only "$FORK_POINT"..origin/epic/<N>-<slug>)
MAIN_FILES=$(git diff --name-only "$FORK_POINT"..origin/main)
OVERLAP=$(comm -12 <(echo "$EPIC_FILES" | sort) <(echo "$MAIN_FILES" | sort) | wc -l | tr -d ' ')
```

Print the signals to the user as a table — `commits behind`, `prior main-merges`, `open story PRs` (with numbers + authors if non-empty), `overlapping files`. This is the audit trail for the strategy choice below.

**Choose strategy.** Apply the decision rule top to bottom; first match wins:

1. **`OPEN_STORY_PRS` non-empty** → **merge**. Rationale: rebase force-pushes `epic/<N>-<slug>`, which rewrites every story PR's base and forces each story author to fetch + reset. Merge preserves the existing epic commits and lets story PRs continue without disruption.
2. **`PRIOR_MAIN_MERGES` ≥ 1** → **merge**. Rationale: history consistency. Once an epic has received merges from `main`, switching back to rebase makes the history harder to read for the integration reviewer.
3. **`OVERLAP` ≥ 5** → **merge**. Rationale: rebase replays each epic commit individually, so each overlapping file is potentially resolved N times (once per epic commit that touches it). Merge resolves each overlapping file exactly once.
4. **Otherwise** → **rebase**. Rationale: small, clean drift — preserve linear history.

State the chosen strategy and the one-sentence rationale to the user. **Proceed unless the user overrides.** Overriding is a one-word reply (`rebase` or `merge`); record the override in the state summary so the eventual integration-PR description mentions which path was taken and why.

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

If the rebase produces conflicts, follow the **Conflict handling** procedure below — do not `git rebase --abort` yet.

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

If the merge produces conflicts, follow the **Conflict handling** procedure below — do not `git merge --abort` yet.

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
   - **Main-side commit context.** Same as above for `"$FORK_POINT"..origin/main`.
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

**Post-rectification.** The epic HEAD has changed; the prior baseline (if any) is no longer trusted. Run the project's full canonical suite in the worktree — use the `issue-resolver-canonical-suite` commands per "Running the full canonical suite" above (one-shot `full-suite`; `build-once` + `retry-without-rebuild` on any re-run; main-loop background bash, absolute paths). On green, post a fresh `Baseline established` comment on the epic issue, recording the new `Epic branch SHA` (the post-rectification HEAD) and the new `Main SHA` (`git merge-base origin/main HEAD` — equals `origin/main`'s current tip for the rebase path; equals the `main` SHA that was merged in for the merge path). Without this, story-flow trust checks will detect the divergence and stop every subsequent story run. On red, handle per step 7's standard red-baseline procedure (detour-first or explicit override).

**If the branch does not exist on origin** → the epic infrastructure hasn't been bootstrapped yet. The epic-as-target run is the canonical place to do this — story runs deliberately stop and redirect here rather than bootstrap silently, so a missing step in the user's workflow stays visible. Bootstrap now (this includes a remote write).

Before the numbered steps below, derive the slug per "Computing a fresh slug" in the "Resolving the epic branch name" section above; the resulting `epic/<N>-<slug>` is the `<branch>` for the rest of this bootstrap.

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
3. Run the project's full canonical suite *in the worktree* — use the `issue-resolver-canonical-suite` commands per "Running the full canonical suite" above (one-shot `full-suite`; `build-once` + `retry-without-rebuild` on any re-run; main-loop background bash, absolute paths). This is the green baseline — it will be inherited by every story under this epic until invalidated. If red, follow step 7's standard handling (detour-first or explicit override). If overridden, post a `Baseline override` comment on this epic issue before proceeding so any later story re-establishes the baseline.
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

If a fresh worktree was created (not reused), run the project's worktree-setup commands per "Worktree setup & teardown commands" above before the canonical suite. Run the canonical suite *in the worktree* (per "Running the full canonical suite" above — the `issue-resolver-canonical-suite` commands, run as a main-loop background bash with absolute paths), and on green post the comment with the current epic-branch SHA and the current `git merge-base origin/main origin/epic/<N>-<slug>` as `Main SHA`. Without this comment, every story under the epic would otherwise stop and redirect back here — establishing it once unblocks the whole epic.

**Classify the situation and act accordingly:**

**All stories closed + all DoD items verifiable → "ready to integrate then close"**

1. Confirm the integration branch exists. Verify that every story's PR has merged into it by checking each story PR's `baseRefName` via `gh pr list --search "closes #<N> OR fixes #<N>"` and inspecting `--json baseRefName`. Flag any story whose PR targeted `main` directly.
2. Set up a worktree on the epic branch (follow the worktree rules in the section above), merge `origin/main` into it if drift exists, run the full canonical suite (per "Running the full canonical suite" above), and report results.
3. If the suite is green, draft an integration PR body (`epic/<N>-<slug>` → `main`) listing every story PR that landed in it, citing the epic's `## Goal` and DoD checklist, and including `Fixes #<epic-number>` so GitHub auto-closes the epic on merge. Write it to `/tmp/gh-resolver-<N>/integration-pr.md` (run `mkdir -p "/tmp/gh-resolver-<N>"` first), then open the PR:
   ```bash
   gh pr create --repo <owner/repo> --base main --head epic/<N>-<slug> --title "Epic #<N>: <title>" --body-file /tmp/gh-resolver-<N>/integration-pr.md
   ```
4. Run the review loop (step 10) on the integration PR. After it merges, draft the body-tick diff (flip every `- [ ]` → `- [x]` in Stories and DoD, including stretch items marked as "deferred") to `/tmp/gh-resolver-<N>/updated-body.md`, and a closing summary comment. Then run:
   ```bash
   gh issue edit <N> --repo <owner/repo> --body-file /tmp/gh-resolver-<N>/updated-body.md
   ```
   GitHub auto-closes the epic via the `Fixes` linkage on integration-PR merge; if it didn't, fall back to `gh issue close <N> --reason completed`.

   This batch flip is the **epic-level final reconciliation** and is distinct from the per-phase DoD projection in §9. By the time the integration PR merges, most of the epic body's `## Definition of done` bullets are already ticked by each child story's resolver run (each story's own per-phase projection lands on the **story** issue body, not the epic). The epic body's DoD typically tracks epic-level outcomes (a deliverable shipped, a metric moved, a stretch item taken or deferred) rather than per-phase artifacts, so the batch flip is the canonical close-out at integration time. The batch flip does **not** carry per-phase / commit attribution — at integration time the granularity is per-story, not per-phase. Stretch items marked as "deferred" still flip per the existing rule.

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
- **Multiple matches** → ask via `AskUserQuestion` (header "Parent epic") which epic applies, one option per candidate epic (label = `#<N>`, description = the epic title), before continuing.
- **Parent epic found** → read its `## Goal` and `## Background` sections. These provide the strategic grounding for why this story exists — use them alongside step 6's PRD/Architecture/CLAUDE.md docs. Cite the parent epic in the PR body's `## Doc grounding` section (e.g. `Parent epic #22 — Goal: …`).

**Determine the PR base.** Resolve `<branch>` per "Resolving the epic branch name" in the Epic section above (discover by prefix; if multiple matches, stop and ask). The story flow never computes a fresh slug — that path lives only in the epic-as-target bootstrap. Treat the discovery result as one of three outcomes:

- **One match (branch exists)** → evaluate the epic-level baseline trust state before creating the story worktree. Fetch the epic issue's comments and work through the trust checks from step 7:
  1. Find the most recent `Baseline established` comment. **If none exists** (epic predates this rule, or the bootstrap comment was never posted), **stop** and direct the user to run this skill on epic #`<N>` first — the epic-as-target run handles the legacy "branch exists, comment missing" recovery in the same place as first-time bootstrap. Do not silently establish a baseline from the story flow; see the "Zero matches and the parent epic is open" branch below for the same reasoning.
  2. Compute `git merge-base origin/main origin/epic/<N>-<slug>`. If it differs from the `Main SHA` in the baseline comment, the epic has moved since that baseline (rebase or merge). The epic-as-target run posts a fresh `Baseline established` comment after rectifying drift per phase E of "Check the integration branch" — if such a newer comment exists with matching SHAs, use it. Otherwise re-run the baseline on the epic branch HEAD and post a fresh comment.
  3. If a `Baseline override` comment exists dated after the latest baseline comment, re-run the baseline on the epic branch HEAD and post a fresh comment.
  4. Otherwise, skip the baseline. Record the inheritance in the state summary and proceed.

  In all cases, also compute epic-vs-main drift once for visibility — `git rev-list --count origin/epic/<N>-<slug>..origin/main` (commits the epic is behind `main` by). If non-zero, record this in the state summary as a drift note (e.g. `Epic branch is N commits behind main — rectify by running this skill on epic #<N>`). **Do not rebase the epic branch from the story flow.** Epic-vs-main drift is owned by the epic-as-target run; from the story flow it is informational only. The §11 summary's drift-note guidance (see "Filing vs. capturing — the decision rule") covers the same shape of note.

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

**After the story PR merges.** The parent epic's body still shows `- [ ]` for this story — GitHub task lists don't auto-tick on PR merge. Flag this in step 11's summary so the user or a future epic-targeted run can sync the checkbox.

---

### 5. Check for existing work on this issue

Before creating any branch, decide what to do based on what's already in flight:

| Situation | What to do |
|---|---|
| **Open PR you authored, branch is yours** | Set up a worktree on the existing branch (see "Setting up the worktree" below), read the full PR context (see below), and continue from there. Skip the "create a branch" part of step 8. |
| **Open PR by someone else, actively being worked on** | **Do not open a competing PR.** Surface this to the user with the PR link and the latest activity, then ask via `AskUserQuestion` (header "Open PR"): **Review it** — run a review of the existing PR; **Leave a comment** — post a constructive comment; **Wait** — take no action for now. |
| **Open PR by someone else, gone stale (no recent activity, requested changes unaddressed for a long time)** | Still don't trample silently. Tell the user and link the stale PR, then ask via `AskUserQuestion` (header "Stale PR"): **Take it over** — set up a worktree branched off the stale PR's branch with a new local branch (see "Setting up the worktree" below); **Start fresh** — branch off default per step 8. |
| **Draft PR** | Treat the same as an open PR by the same author. Drafts are still claimed work. |
| **Closed PR that resolved the issue** | The issue should already be closed. If it isn't, something's odd — flag it to the user before doing anything else. |
| **Closed/merged PR that did *not* resolve the issue** (partial fix, reverted, abandoned) | Note this in the state summary, read the PR's full context (see below) to learn what was tried and why it didn't land, then proceed as the no-prior-PR case (a fresh worktree off default, per step 8). |
| **No prior PR** | Proceed normally to step 8. |

**Multi-phase issues reuse the same draft PR across phases.** When §4.7 identified a multi-phase issue and an open *draft* PR by you already exists, the "Open PR you authored" row above applies as-is — set up a worktree on the existing branch, read PR context, continue. The draft state with prior phase commits is the **expected** mid-run state for a multi-phase issue, not a sign of abandoned work: every phase the resolver has already executed lives as a ticked entry in the PR body's `## Phase tracker`, and your job is to ship the next unshipped phase from §4.7's captured phase list onto the same branch. Do not open a second PR for "this phase"; the single accumulating PR is the whole point. (If the existing PR is marked ready rather than draft *while phases remain unshipped in `## Phases`*, treat that as drift — surface it to the user. The resolver only flips a multi-phase PR ready at the §11 *last planned phase shipped* row, immediately before handoff; a mid-phase ready usually means the evaluator approved-and-merged a prior phase by mistake, or someone marked ready by hand. Re-entering on the soft-reject path is *not* drift — the evaluator flips the PR back to draft on a COMMENT verdict per `github-pr-evaluator` §11, and the resolver picks up on that draft to address the gaps.)

**Setting up the worktree.** When step 5 directs you to check out an existing PR's branch — your own open PR, or a takeover of a stale one — set it up as a worktree rather than `gh pr checkout` in the main tree:

1. Get the branch name: `gh pr view <pr-number> --repo <owner/repo> --json headRefName -q .headRefName`.
2. Run `git worktree list --porcelain` and check whether the target branch already has a worktree. If yes, `cd` to that path and stop here — reuse it.
3. Otherwise, fetch the branch (`git fetch origin <branch>`), then add the worktree:
   - **Continuing your own PR**: `git worktree add .worktrees/<branch> <branch>`.
   - **Taking over a stale PR**: pick a new local branch name (e.g. `issue-<N>-takeover`) and run `git worktree add -b <new-branch> .worktrees/<new-branch> <stale-pr-branch>`.
4. `cd .worktrees/<dir>` — every subsequent command in this run is from there. Announce the path to the user.
5. Run the project's worktree-setup commands per "Worktree setup & teardown commands" above. Step 2's reuse exit skips this — those commands already ran when the worktree was first created.
6. **Check the story branch for drift against its base.** The story branch's integration target is the epic branch (or `main`, for stories with no open parent epic). Compute:

   ```bash
   git fetch origin <base-branch>
   git rev-list --count <story-branch>..origin/<base-branch>
   ```

   If non-zero, surface to the user before continuing — the story branch is behind its base, and any new commits will land on stale ground. Offer to merge the base into the story branch (preferred for an open PR — keeps the PR's commit history intact for reviewers) or to rebase (only if the user prefers and the PR review state allows it). Do not auto-rebase a branch with an open PR.

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

**If a plan was consumed at step 4.6, lift the grounding from it.** A finalized `github-issue-planner` plan already did this research and verified it — its `## Doc grounding` and `## Architecture decisions` are the grounding statement. Restate (and cite) them as this step's output rather than re-deriving from scratch; you may still spot-check that the cited sections say what the plan claims. The rest of this step's full re-derivation applies only when step 4.6 ended in a `Plan override` (no plan to lift from) or the issue is trivial (gate didn't fire).

**Check which docs are present:**

```bash
ls docs/prd.md docs/architecture.md CLAUDE.md 2>/dev/null
```

Read each one that exists. `CLAUDE.md` often `@`-references additional docs (e.g., `@docs/constitution.md`); follow those references and read the linked files too.

**Cite what informed the approach.** Identify the specific sections of the PRD / Architecture / CLAUDE.md / any referenced constitution that constrain or shape the implementation. Write a brief grounding statement before step 8 — for example:

> PRD §3 defines natural-language entry as the only input method. Architecture §2 layer rules require Stores to import only Foundation/SwiftData/Services/Models. Constitution §4 forbids `UserDefaults` — all settings must be on `UserProfile`. Therefore the approach is …

This grounding statement is the output of this step. State it before writing any code so the user can correct the framing if it's wrong. The PR body MUST cite these sections (see step 9).

**Surface tensions before proceeding.** Three patterns to watch for:

- **The issue contradicts a doc.** E.g., the issue requests behaviour the constitution forbids (a banned API, a forbidden architectural pattern, a capability the PRD explicitly excludes). **Stop.** Surface the conflict and ask via `AskUserQuestion` (header "Doc conflict"): **Update the doc** — change the doc so the issue becomes buildable; **Reshape issue** — route back to `github-issue-drafter` to fit the docs; **Override w/ reason** — proceed against the doc with a one-line reason recorded in the PR body. Do not silently work around it.
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

**Persistence — two comment formats posted on the epic issue.** Post both.

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
- **Pre-existing failures unrelated to the issue.** Stop and surface to the user with the specific failures. Do not proceed on a red base. The point of the baseline is to attribute later failures correctly; that attribution falls apart the moment unrelated red is left in the tree, and it lets a PR ship over a broken codebase. Acceptable next moves, all chosen by the user: (a) detour first — file a follow-up issue per "Follow-up issue tracking" above (urgency: `file-now`, type: `bug`), then open a separate detour PR that resolves it; resume this resolution once the detour merges and the baseline turns green; (b) explicit user override with a documented reason recorded in the PR body's out-of-scope notes. If this is a story under an open epic, also post a "Baseline override" comment on the epic issue (see "Persistence" in "Where to run it" above) so the next story under this epic knows to re-establish the baseline. Do not silently fix unrelated failures — that scope-creeps the PR and obscures what your change actually did.
- **Pre-existing failures that overlap with the issue.** These may be the bug itself, or a symptom. Note them in the state summary — they likely become the test cases your fix needs to turn green.
- **Base branch is broken.** Stop and surface to the user. There's no useful "green baseline" to compare against, and feature work on top of a broken base will compound the problem.

Record the baseline result before doing any work. The point is twofold: you can attribute later failures correctly, and the user gets early warning if the project is in a worse state than expected.

### 8. Do the work

For code changes:
- Confirm the approach respects the doc grounding from step 6 — if implementation reveals a constraint conflict not visible at planning time, stop and surface it instead of working around it silently.
- **Stick to the plan; route plan-invalidating discoveries back, don't work around them.** When a plan was consumed at step 4.6, its locked decisions (`## Architecture decisions`, `## Changes`, `## Data model / schema impact`, `## Test plan`) are binding. The plan locks *decisions*, not every line — implement freely within them. But if implementation reveals a locked decision is wrong or unbuildable (a planned API doesn't behave as assumed, a layer assignment can't hold, a data-model shape won't work), **stop and route back to `github-issue-planner` in revise mode** (invoke it via the `Skill` tool with `re-plan #N — implementation invalidated a locked decision: <evidence>`) rather than silently substituting your own approach. This mirrors how the §4.5 audit routes body problems back to the drafter: the plan is a verified, durable artifact, and a quiet workaround diverges the code from it, defeats the pr-evaluator's plan-adherence check, and loses the decision's provenance. A small, in-spirit detail the plan didn't anticipate is fine to settle yourself; a reversal of a locked decision is not.
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

  If run 1 is green, proceed to §9. If run 1 is red, follow the ladder in "Retry ladder for the verification gate" above — at most 3 runs this visit, with a forced research breakpoint between cheap and deep fixes, escalating to the user if the deep fix also fails. Don't fall back to "no tests" when the sub-agent's heuristics could have widened — re-spawn the sub-agent if the rationale looks wrong. **Do not skip this gate on the assumption that §10.6 will catch regressions** — §10.6 only fires when the review loop iterates (i.e., review requests changes). On a clean first-pass approval the workflow goes §8 → §9 → §10 (approves) → §11 with no §10.6 — so the gate at §8 is the only test invocation that runs before the PR is opened.
- Keep the diff focused on the issue — don't drive-by-fix unrelated things.

For comment-only responses (questions, blocked issues, duplicates):
- Draft the comment as a markdown file in the working directory, then post it

### 9. Report back to GitHub

For a comment-only response, stage the drafted comment to disk first — write it to `/tmp/gh-resolver-<issue-number>/comment.md`, then pass the path. `github-ops` reads the bytes through `gh-persist.sh` and posts them directly; the body never gets re-serialized into the sub-agent prompt, so prompt compaction can't abbreviate it and the in-agent Write/Bash race that filed empty bodies on the drafter's #626/#627 has nothing to race on.

> `PERSIST_COMMENT(target=issue, id=<number>, repo=<owner/repo>, body_path=/tmp/gh-resolver-<issue-number>/comment.md)`

It returns the comment URL plus `body_bytes` / `body_sha256`. If the empty-body guard fires (`EMPTY_BODY_FILE: <path>`), the staged file is missing or empty — re-write it and re-dispatch the same path.

For code changes (all `git push` and `gh pr create` commands run from inside the worktree — same syntax, just a different cwd; PR creation stays here in the main loop, coupled to the worktree push):

- **If you're continuing an existing PR** (per step 5): just push the new commits to that branch. The PR updates automatically. Don't open a new one. **If this is a multi-phase issue and the push just shipped a phase** (per §4.7), also tick that phase off the PR body's `## Phase tracker` via `gh pr edit <PR#> --body-file <updated-body>` — write the updated body to `/tmp/gh-resolver-<issue-number>/pr-body.md`, flipping only the just-shipped phase's `- [ ]` to `- [x] (commit <sha>)` and leaving the rest as-is. The tracker is the evaluator's input on its final DoD check and a human-readable map of progress; an unticked tracker on a pushed phase will read as in-flight work to the next reader.

  **Then project the phase's `closes-dod` onto the issue body's `## Definition of done`.** Read the current issue body (re-`Read` `/tmp/gh-resolver-<issue-number>/issue-<N>-body.md` from §2's `GATHER_ISSUE`, or refresh via `gh issue view <N> --json body -q .body > /tmp/gh-resolver-<issue-number>/issue-<N>-body.md` if it's stale). Apply the "DoD projection rule" below to compute the projection diff (which bullets should flip `- [ ]` → `- [x]` with what annotation), stage the projected body to `/tmp/gh-resolver-<issue-number>/issue-body-projected.md`, and apply via `gh issue edit <N> --repo <owner/repo> --body-file /tmp/gh-resolver-<issue-number>/issue-body-projected.md`. **Do not abort the resolver run on projection failure** — commits and Phase tracker ticks are preserved; the next re-entrant run's §4.7 reconciliation re-derives the missing ticks from `Phase tracker × closes-dod` and re-applies them. Surface the failure in the §11 summary so the user can see what didn't land.
- **If this is a fresh PR**: push the branch and open a PR.

  **Fresh-PR branch detection on re-entry (predecessor PR).** Before computing the branch name, check whether a closed PR exists on this issue from a prior HARD-path "Start fresh" revise (see `github-issue-planner`'s "Re-plan reconciliation"). Detect via:

  ```bash
  gh pr list --repo <owner/repo> --state closed --search "<issue-number> in:body" \
    --json number,headRefName,closedAt,body --limit 5
  ```

  Filter to PRs whose body references this issue's number and was closed with a re-plan note (the planner's close comment contains the literal text `Re-plan superseded this PR`). If one or more matches exist, the new branch must not collide with the predecessor's. Use the `-vN` convention: scan existing branches with `git ls-remote --heads origin "<issue>-<slug>*"`, find the highest existing `-vN` suffix (the unsuffixed `<issue>-<slug>` is `v1`), and increment. Example: predecessor branch `142-add-csv-export` → new branch `142-add-csv-export-v2`. A subsequent fresh-start would pick `-v3`. When no predecessor PR exists, use the unsuffixed `<issue>-<slug>` as today.

  When opening on a `-vN` branch, mirror the new plan's `## Predecessor` section (the planner authored it during the HARD revise) into the PR body as a `## Predecessor` section — link the closed PR, link the predecessor branch, repeat the reminder to delete the old branch after this PR lands. The plan's `## Predecessor` and the PR's `## Predecessor` carry identical content; both exist so a reader on either surface sees the audit trail without cross-referencing.

  Write the PR body to `/tmp/gh-resolver-<issue-number>/pr-body.md` (a per-run scratch dir keyed on the issue number, so concurrent resolver runs don't clobber it, and the body never lands in the worktree where it could be committed), then:

  ```bash
  gh pr create --repo <owner/repo> --title "Fix: <summary> (#<issue-number>)" --body-file /tmp/gh-resolver-<issue-number>/pr-body.md --base <default-branch>
  ```

  PR body must include `Fixes #<number>` (or `Closes #<number>`) so GitHub auto-links and auto-closes on merge. It must also include a `## Doc grounding` section near the top listing the PRD/Architecture/CLAUDE.md sections that informed the approach (per step 6). Omit this section only if no project docs were present.

  **Link the plan.** If a plan was consumed at step 4.6, add a `## Plan` line near the top of the PR body linking the plan comment — e.g. `Implements the plan on #<N>: <plan-comment-url>`. This lets `github-pr-evaluator` find the plan to check adherence, and tells reviewers the diff was built to a vetted design. When the plan was lifted into `## Doc grounding`, the `## Plan` link is the provenance for that grounding.

  **Carry forward step 4.5's audit overrides and step 4.6's plan override.** If step 4.5 ended in an `Audit override: <reason>` (or `Audit skipped by user override`), include a `## Audit override` section quoting it verbatim. If step 4.6 ended in a `Plan override: <reason>` (the user chose to proceed without a plan), include a `## Plan override` section quoting it verbatim. Reviewers see overrides the same way they see scope decisions — visible and challengeable in PR review. Omit either section when the corresponding gate ran clean or didn't apply.

  **Multi-phase issues open as draft and carry a `## Phase tracker` block.** When §4.7 identified this as a multi-phase issue, two things change about the fresh-PR open:

  - Pass `--draft` to `gh pr create`. The PR stays in draft while phases remain unshipped in `## Phases`. **On the §11 outcome-rubric's *last planned phase shipped* row**, the resolver flips draft → ready via `gh pr ready <N> --repo <owner/repo>` immediately before emitting the handoff. Without that flip, the evaluator's §3 draft-PR guard would deadlock the handoff. (The handoff's PR-line `state:` marker reflects the post-flip state — `state: open` — and overrides pr-state.json's pre-flip `isDraft: true` for this row; see `references/handoff-renderings.md` "Forward — multi-phase, last planned phase shipped".) If the evaluator soft-rejects (COMMENT verdict), it flips the PR back to draft per `github-pr-evaluator` §11 and the resolver re-enters in continue mode against the now-draft PR. `Closes #<number>` in the body is unchanged — `Closes` only fires on merge, and a draft PR cannot merge, so the draft state during phase-by-phase work is itself the auto-close guard.

  - Add a `## Phase tracker` block to the body mirroring the plan's `## Phases`, with this phase already ticked (every later phase still `- [ ]`):

    ```
    ## Phase tracker
    - [x] Phase 1 — substrate (commit abc1234)
    - [ ] Phase 2 — harness
    - [ ] Phase 2-measurement (operator)
    - [ ] Phase 3 — decision write-up
    ```

  The tracker exists for the evaluator's eventual DoD check (it lets the evaluator see at a glance which phases shipped) and for human reviewers — the resolver itself only reads the plan's `## Phases` to decide routing in §11. On subsequent phases the existing-PR continuation path above updates this block via `gh pr edit`.

  **Then project DoD onto the issue body, same as the existing-PR path above.** Phase 1's `closes-dod` projects onto the issue's `## Definition of done` alongside the fresh PR's `## Phase tracker` initialisation. For a single-phase fresh PR, the single-phase fallback (see "DoD projection rule" below) ticks every top-level DoD bullet at this point. Same `gh issue edit --body-file` mechanism; same don't-abort-on-failure rule.

In both cases, capture the PR number/URL — you'll need it for the review loop.

#### DoD projection rule

Both push paths above (existing-PR continuation, fresh-PR open) project the just-shipped phase's `closes-dod` onto the issue body. The rule below specifies what to project and how to compose the annotation. Reconciliation on re-entry (§4.7) follows the same rule with the same inputs.

**Annotation shapes and parser:** see [`../_shared/dod-annotations.md`](../_shared/dod-annotations.md) for the closed set of annotation forms (code-phase / operator / single-phase / evaluator-rejected / predecessor), the 1-based top-level-bullet indexing rule, the recognition regex, and the invariants every reader must respect. This skill writes the three `closed by ...` ticked forms — the rest are written by `github-pr-evaluator` (sticky-veto un-ticks) and `github-issue-planner` (revise-mode predecessor un-ticks); they are read here to respect existing annotations during projection.

**Reconciliation source.** The projection's expected DoD-bullet set is computed from two inputs only:

- The PR's `## Phase tracker` (ticked entries only) — the authoritative record of which phases have shipped on this branch.
- The captured phase list from §4.7 — each ticked phase's `closes-dod` indexes.

The union of `closes-dod` across all ticked code-shipping and operator phases is the expected ticked set on the issue body's `## Definition of done`. The resolver never reads the issue body's DoD ticks to decide routing — only to compute the diff between expected and current state.

**Single-phase fallback.** When the plan has no `## Phases` section (single-phase issue per §4.7), or `## Phases` contains a single entry with no `closes-dod`, fall back to "tick every top-level DoD bullet" on the **first push of the run** only. Subsequent §10.6 re-pushes within the same run do not re-tick (the projection has already landed). Re-entry reconciliation (§4.7) re-applies if the first push's `gh issue edit` failed.

**Operator-phase hybrid detection.** Operator and decision-only phases (`kind: operator` | `decision-only`) ship no commits — the resolver doesn't run them. On a re-entry where the next phase is unticked but its `depends-on` is satisfied:

1. **Marker scrape (deterministic).** Look in the issue's comment thread for a comment posted after the prior handoff's timestamp containing `<!-- operator-phase-complete: <N> -->` (where `<N>` is the phase number) on its own line. If exactly one unambiguous match is found, treat the phase as complete — tick the PR's `## Phase tracker` entry as `- [x] (operator phase <N>, applied <ISO-date from the marker comment>)` and project its `closes-dod` onto the issue body using the operator-phase annotation form below.
2. **`AskUserQuestion` fallback.** If no marker is found, or the match is ambiguous (multiple markers for the same phase, marker for a phase that isn't the next expected), present the prior handoff's operator action verbatim and ask: header **"Op phase <N> done?"**, options: **Yes — apply** (tick + project), **No — re-show handoff** (re-emit the operator handoff verbatim and stop the run), **Other** (user explains). Do not silently scrape prose; the marker-or-ask gate is the only deterministic path.

**Annotation format.** Each projection edit replaces the bullet's `- [ ] <text>` with one of:

- Code-shipping phase: `- [x] <text> (closed by phase <N>, commit <short-sha>)`
- Operator / decision-only phase: `- [x] <text> (closed by phase <N>, operator action <ISO-date>)`
- Single-phase fallback (no `## Phases`): `- [x] <text> (closed by commit <short-sha>)`

Use 7-char short SHAs (matching `## Phase tracker` and `../_shared/handoff-format.md`). The bullet text itself is preserved verbatim; the annotation is appended after the existing text. When a bullet already carries a prior annotation (rare — typically only on plan-revision mid-flight, see "Edge cases" below), replace the prior annotation in full rather than appending a second.

**Respect the evaluator's sticky veto.** A bullet annotated `- [ ] <text> (resolver claimed phase <N>, commit <sha>; evaluator rejected: <reason>)` is the evaluator's rejection of a prior projection — the diff in the attributed commit(s) didn't satisfy the bullet. Treat such bullets as **not projected**, even when `Phase tracker × closes-dod` would tick them. The disagreement is resolved by re-planning (the planner reassigns the bullet to a different phase), by a new code phase whose diff actually satisfies the bullet, or by user intervention — never by silent re-ticking on the next push.

**Idempotent diff-only application.** Projection is computed as `expected_set − (currently_ticked_set ∪ rejected_set)`. Only the diff is applied to the body. Never blindly re-tick bullets that are already `- [x]` (clobbering attribution annotations is a regression).

**Worked examples.**

*Example A — multi-phase code phase with `closes-dod: [1, 3]`:*
Plan's Phase 2 carries `closes-dod: 1, 3`. Phase 2's commits land at SHA `abc1234`. After the push, `## Phase tracker` is updated to `- [x] Phase 2 — harness (commit abc1234)`. Then the issue body's `- [ ] First bullet text` becomes `- [x] First bullet text (closed by phase 2, commit abc1234)` and the third bullet flips the same way. Bullet 2 (claimed by Phase 1 if Phase 1 already ticked it, or still `- [ ]` if Phase 4 will close it later) is untouched.

*Example B — single-phase fallback:*
Plan has no `## Phases`. The fresh-PR open pushes the single phase's commits at SHA `def5678`. Single-phase fallback fires: every top-level `- [ ]` under `## Definition of done` flips to `- [x] <text> (closed by commit def5678)`. Subsequent §10.6 re-pushes during review-loop iterations do not re-tick.

*Example C — operator phase with `closes-dod: (none)`:*
Phase 2-measurement is `kind: operator` with `closes-dod: (none)`. On the next re-entry, the marker scrape finds `<!-- operator-phase-complete: 2 -->` posted at `2026-06-04`. The Phase tracker entry becomes `- [x] Phase 2-measurement (operator phase 2, applied 2026-06-04)`. No `gh issue edit` against the issue body — `(none)` means zero bullets to project. The next code phase ships and projects its own `closes-dod`.

**Edge cases.**

- *Plan revision mid-flight* (resolver shipped Phase 1, ticked bullet 3; plan revised so bullet 3 is now claimed by Phase 4): reconciliation never auto-un-ticks. The bullet stays `- [x] <text> (closed by phase 1, commit abc1234)` until Phase 4 ships, at which point projection replaces the annotation with `(closed by phase 4, commit <newer-sha>)`. State summary records `DoD plan-revision drift: bullet 3 was ticked by phase 1 under the prior plan; current plan reassigns to phase 4.`
- *Bullet count drift* (issue body has more or fewer top-level DoD bullets than the plan's max-referenced index): block projection this run, surface in state summary, route back to the planner via the existing `Re-route → planner` handoff (the bullet shift breaks the planner's Dimension-7 invariant).
- *`closes-dod: (none)` phase*: PR Phase tracker still ticks normally; zero `gh issue edit` calls. Log `DoD projection: phase <N> closes (none) — no DoD edits.`
- *Issue with no `## Definition of done` section*: skip projection silently with state-summary line `DoD projection: issue has no \`## Definition of done\` section — projection skipped.` (Multi-phase issues without a DoD section are impossible past planner Dimension-7 review; if detected, treat as bullet-count drift and re-route to planner.)

### 10. Run the review loop (PRs only)

**Step 10 → Step 10.7 → Step 11 → Step 12 chain.** When the review loop exits cleanly (verdict approved + zero classified items), your next emissions in the same run are: (a) §10.7's operational state-refresh (`gh pr view <N> --json …` — mandatory, not advisory), (b) §11's summary block, (c) §12's `## Handoff`. All three are unconditional. The PR #416 / no-handoff #653 failure mode is: `Skill(review)` returns approved prose, the model treats that prose as a deliverable, and the turn ends. The primary structural anti-stop is §10.7's operational anchor below — every sibling skill (pr-evaluator, drafter, planner) survives the same turn-boundary risk because they have operational tool calls between verdict and handoff. The two turn-boundary beats in §10 that require this protection: **after `Skill(review)` returns** (before step 2's sub-agent dispatch) and **after the §10 sub-agent returns** (before step 1 of the next iteration *or* before §10.7 / §11).

**This step is mandatory for any issue resolved with code changes. Do not skip it, do not merge, and do not consider the work done until review approves the PR.**

**Multi-phase issues run §10 on every phase's push, unchanged.** `review` is a per-push code-quality gate; it has no awareness of phases and shouldn't. The loop's exit condition stays the same — verdict approved + zero classified items per §10.4 — and what changes is only what happens *after* the loop exits: §11's outcome rubric decides whether the next step is "back to the resolver for the next phase" (more phases remain in `## Phases`) or "forward to the evaluator" (last phase shipped). Treat §10 as scoped to "is this push reviewable code?" and §11 as scoped to "is the plan exhausted?" — the two decisions are independent. Before emitting §11, re-confirm the §4.7 captured phase list is in your working context. The multi-phase renderings in `references/handoff-renderings.md` require the next phase's title verbatim from the plan's `## Phases` — if you can't quote it, you've dropped §4.7's state and need to re-read the plan-marker comment from `/tmp/gh-resolver-<ISSUE>/issue-<N>-plan.md` (the `github-ops` GATHER scratch file).

After the PR is opened, the resolver runs an **outer loop in the main conversation** that, on each iteration, invokes the `review` skill once and then dispatches a single sub-agent to act on the verdict. The sub-agent applies the §10.4 classification rubric, addresses feedback, runs the §10.6 pre-push verification gate, commits, pushes, and returns a structured JSON summary — entirely within its own execution scope. The main loop reads the JSON, decides whether to loop again, and re-invokes `review` on the new SHA. If the skill is re-invoked later (a human reviewer commented, the previous run was interrupted), step 5's reuse rule lands you back in the existing worktree and the outer loop runs again from the top — the sub-agent's prompt is told it may be picking up mid-flow.

**Why this shape — and the constraint that forces it.** Two structural facts from the [Claude Code sub-agents reference](https://code.claude.com/docs/en/sub-agents) determine where `review` has to run. First, sub-agents spawned via the `Agent` tool can only invoke **project, user, and plugin skills** through the `Skill` tool — *bundled* skills (`/code-review`) and *built-in* commands (`/review`) are not reachable from inside a sub-agent. Second, sub-agents cannot spawn sub-agents, so even if `/code-review` were reachable, its own internal fan-out (it orchestrates parallel Sonnet sub-agents) would be blocked one layer in. The `review` invocation therefore has to happen in the main conversation; trying to do it from inside an `Agent`-dispatched sub-agent forces the sub-agent to improvise a manual review and return prose, which is exactly the failure observed on PR #607 (chat log captured at `/tmp/review-skill.md`).

**The earlier shape and why it had to change.** Previous revisions of this section put the entire review loop — `review` invocation included — inside a single sub-agent, because in-conversation loops have an unavoidable pull toward turn boundaries after long sub-tasks (e.g., the `/tmp/review-loop.md` transcript on PR #416, where the main loop classified items correctly and then stopped at the verdict). The sub-agent boundary was the structural fix. That fix is no longer available now that the bundled-skill constraint is documented; the compromise is to keep the goal-directed sub-agent for the *loop body* (classification, edits, §10.6 gate, push) where its goal-directedness matters most, while accepting the narrower turn-boundary risk between sub-agent return and the next `review` call. Mitigations: the main loop's only natural beat after reading the sub-agent's JSON is the next tool call (re-invoke `review` if more iterations needed, or proceed to §11) — see also the "Don't stop after the sub-agent returns" pitfall added below.

**Outer-loop control (main conversation).** One iteration of the loop is:

1. **Invoke `review`** via the `Skill` tool: `Skill(skill="review", args="<PR#>")`. The skill runs in the main conversation; its findings land in your context as the skill completes. **After `/review`'s verdict text is in the conversation, your next emissions in the same turn are operational only** — `Write` the verdict file at `/tmp/gh-resolver-<ISSUE>/review-verdict.md` (`mkdir -p` first), `gh pr comment <N> --body-file …` (only if `/review` did not already post a PR comment itself — check via `gh pr view <N> --comments`), then `Agent` dispatch per step 2. **No additional prose between the verdict text and the `Write` call.** The verdict text is `/review`'s legitimate output; what's forbidden is *further* prose that paraphrases, summarises, or interprets the verdict before the operational steps fire. The PR comment is how the user follows the loop on GitHub; the verdict file is what the sub-agent classifies.
2. **Dispatch the sub-agent** immediately. Use the `Agent` tool with `subagent_type: "general-purpose"`, `description: "Act on review verdict for PR #<N>"`, and the prompt template referenced below. Inline every input placeholder at dispatch time. The sub-agent has full tool access — `Bash` + `Read` + `Edit` + `Write` for code changes, `Agent` for nested test-selection and build delegations. `Skill` is in its toolset for invoking `github-issue-drafter` follow-ups, but never for `review`/`code-review` (which it cannot reach anyway). `AskUserQuestion` is deliberately **not** available inside a sub-agent. When a guard rail fires, the sub-agent returns a `needs_decision` payload and this main loop renders the question. **Even when `/review` returned "approved, zero open suggestions", step 2 is still mandatory.** The sub-agent's step 6 (see `references/review-loop-sub-agent.md`) handles the zero-items path with an early return; the dispatch itself is the structural beat that protects against turn-boundary stops. Skipping it because the verdict "looks clean" is the documented `/tmp/no-handoff.md` failure mode.
3. **Read the JSON return.** Parse the sub-agent's terminal status:
   - `iteration_complete` with empty `items_addressed` → **Exit branch — §10.7 then §11 then §12 fire immediately.** The verdict had no Addressable / Cheap-fix-override items (everything was Explicitly-deferred or there were no items at all). Combined with `review`'s approved verdict on this iteration, the loop's exit condition holds. Your next emissions in the same run are: (a) §10.7's mandatory `gh pr view <N> --json …` state refresh, (b) §11's summary block, (c) §12's `## Handoff`. No-stop rule applies — read the JSON, fire §10.7, compose §11, emit §12 in one continuous turn.
   - `iteration_complete` with non-empty `items_addressed` → the sub-agent committed and pushed fixes. The verdict reviewed an older SHA; loop back to step 1 to re-review the new SHA.
   - `needs_decision` → render `decision_request` through `AskUserQuestion`, record the answer, re-dispatch a fresh sub-agent with the same verdict file plus the answer appended to its `prior_decisions` input. Do **not** re-invoke `review` for a decision-resume — the verdict file is still current.
   - `aborted` → exit to §11 with the aborted outcome. The sub-agent has already filed any follow-ups it needed to.
4. **Iteration cap.** Track an iteration counter in the main loop, starting at 1, incremented after every full step-1-through-3 cycle. If it reaches 6 before exit, surface via `AskUserQuestion` (`header: "Iter cap"`, options: **Continue** (free-text count in "Other"), **Accept current** (exit with current state), **Abort**). Iteration capping is no longer a sub-agent guard rail — the sub-agent doesn't own the outer loop any more.
5. **Deadlock detection.** Maintain `prior_addressed_items` in the main loop as the union of every `items_addressed` summary across the iterations so far. Pass it into the sub-agent's input on each dispatch. The sub-agent compares the new verdict against this list and trips its `deadlock` guard rail if any prior-addressed item appears in the new verdict with no acknowledgement of the prior fix.

The prompt template below covers what the sub-agent does once dispatched. The outer loop is yours to drive.

**See [`references/review-loop-sub-agent.md`](references/review-loop-sub-agent.md) for the full sub-agent prompt template, JSON return schema, and the three guard-rail definitions** (`deadlock`, `architectural`, `verification_failure`). Substitute every placeholder (PR number/URL, repo, worktree path, originating issue, parent epic, integration target, iteration index, verdict file path, doc-grounding statement, audit-override block, test-config blocks, prior addressed items, prior decisions, resume hint, and the resolver skill directory `<RESOLVER_DIR>` = `${CLAUDE_PLUGIN_ROOT}/skills/github-issue-resolver`) at dispatch time. Key invariants the outer loop relies on: the sub-agent does **not** invoke `review` itself (it's the built-in not reachable from `Agent`-dispatched sub-agents); the sub-agent's **step 6** is an early return with `status: "iteration_complete"` and empty `items_addressed` when classification finds zero Addressable / Cheap-fix-override items — this is the documented zero-items path, dispatched even on "approved with zero suggestions" verdicts; guard-rail firings return `needs_decision` and never call `AskUserQuestion`.

**Consume the return summary.** Parse the JSON the sub-agent returns on every iteration. The outer loop control above already names the four branch-on-status arms (`iteration_complete` with/without addressed items, `needs_decision`, `aborted`); the rules below say what to *carry forward* into §11 once the loop has exited.

- `needs_decision` is not terminal — render `decision_request` through `AskUserQuestion`, append the answer to the running `user_decisions` list, and re-dispatch a fresh sub-agent with the same verdict file path plus the answer in `prior_decisions`. Do **not** re-invoke `review`; the verdict file is still current. Each answer becomes one *Procedural notes* line in §11.
- On every terminal sub-agent return, accumulate its `items_addressed` into the main loop's running `prior_addressed_items` list (for the next iteration's deadlock check), and its `items_filed_as_followups` + `items_carried_as_procedural_notes` into running lists for §11.
- When the loop exits (zero-edits iteration with an approved verdict, iteration cap accepted, or user-aborted), the §11 inputs are: the final iteration's `final_pushed_sha` (or the prior iteration's, if the final iteration produced zero edits), the final iteration's `iteration_test_status` (mapped to §11's `Iteration test status` line verbatim — when the final iteration was a zero-edits exit, use the *prior* iteration's status since that's the test signal that gated the most recent push), the accumulated `items_filed_as_followups` (§11's *Follow-ups → Filed* bullets), the accumulated `items_carried_as_procedural_notes` (§11's *Follow-ups → Procedural notes* bullets), and the accumulated `user_decisions` (each adds one *Procedural notes* line naming the trigger and the user's choice). A non-empty `final_pushed_sha` (in any iteration of the loop) means a PR was updated, which fires the pr-evaluator handoff per the rubric in §11.

**Resume contract.** A re-invocation of the resolver while a PR is still open and under review (the existing step 5 reuse path) restarts the outer loop from iteration 1 — `review` is invoked, the verdict file is rewritten, a fresh sub-agent dispatches. Sub-agents don't persist state across runs and neither does the main loop's iteration counter. The sub-agent's "Resume hint" input tells it to re-read accumulated PR comments and reviews on iteration 1, which surfaces any human reviewer activity that landed between invocations. A prior run that exited via the guard-rail's "abort" path leaves the loop in a known stop-state; re-invoking starts the loop fresh, the sub-agent sees the prior abort in the PR comment history, and decides whether the original blocker is now resolvable.

#### §10.4 — Classification rubric

The sub-agent applies this rubric on every iteration. The rubric is documented at the section level so a reader can audit a sub-agent return against it and so the sub-agent prompt above can reference it by anchor.

"Approved" alone is not the exit condition — reviewers routinely approve with non-blocking suggestions (`Medium —`, `Low —`, `Nitpick —`, "Approved with minor fixes") that they still expect fixed before merge. Issues (defects the reviewer flagged) and suggestions (improvements the reviewer recommended) are gated identically; what matters is whether the item is **addressable on this PR**. Walk the review body and classify each item:

- **Addressable actionable (default).** Any concrete change the reviewer named falls here **unless** it satisfies one of the explicit deferral triggers below. Severity labels (`Medium —`, `Low —`, `Nitpick —`) and reviewer politeness ("could be a fast-follow", "not blocking if you prefer", "consider for a future PR", "deferrable", "informational only") do **not** by themselves move an item out of this bucket. The reviewer flagged it; address it.
- **Explicitly deferred** — reserved for items meeting **at least one** of these objective triggers. The reviewer's prose is evidence; the sub-agent re-checks. Soft framing alone never qualifies:
  - **Concrete routing target.** The reviewer cites a specific issue/PR number that already exists or is filed as part of this resolution (`#N`, "tracked in #M", "filed as follow-up below"). A vague "future PR" or "a separate change" without a number is *not* a concrete target.
  - **Structural blocker.** The fix can't ship in this PR — depends on a sibling story not yet merged; requires an API break whose consumers are outside this PR's scope; requires a schema migration the PR's scope excludes.
  - **PRD / scope explicit exclusion.** The item is outside the issue's stated scope as documented in the issue body, the parent epic's DoD, `docs/prd.md`, `docs/architecture.md`, `docs/constitution.md`, or `CLAUDE.md`. Soft scope arguments ("keeps the PR scope pure") don't qualify — the exclusion must be citable.
- **Cheap-fix override.** If an item meets a deferral trigger above but the fix is **≤ ~20 lines of edits on files this PR already modifies** and doesn't require new tests, new files in the diff, or scope expansion — address it in-loop anyway. Deferral exists to keep PR scope tight; trivial doc, comment, identifier, or formatting fixes aren't scope creep. The override does *not* apply to code changes that pull new files into the diff or that need a fresh test.
- **Decision required** — the suggestion touches architecture, breaks an API, or carries a tradeoff the user should weigh in on. Don't guess. Trip the sub-agent's "Decision required" guard rail (see the prompt above): the sub-agent returns a `needs_decision` payload, the main loop asks the user via `AskUserQuestion`, and a fresh sub-agent resumes with the answer.

Worked examples (verbatim review snippets the rubric has to handle correctly — these come from the failure mode this rubric was tightened to fix):

- **Example A — soft defer is Addressable.** Review text: *"Defer to story #403 if you prefer to keep this PR scope-pure — docs-first ambiguity is fine and the mapping is obvious to a reader who has the enum in hand."* → **Addressable**. The reviewer offered deferral as an option ("if you prefer"), did not file a concrete tracking issue for the fix itself, and the item is a 1-line doc clarification on a file the PR already changes.
- **Example B — concrete routing is deferred.** Review text: *"Variant-B's mixed-mode UX is design work that belongs in story #403's UX brief — filing as follow-up issue #N."* → **Explicitly deferred**. Concrete tracking issue (`#N`) plus a citable structural rationale (the parent epic's story breakdown).
- **Example C — "future doc-amend" triggers Cheap-fix override.** Review text: *"The single paragraph packs four rules … a future doc-amend (or this PR if you'd like) could break it into bullets."* → **Cheap-fix override**. "Future doc-amend" matches deferral language, but the fix is ~5 lines on a file the PR already modifies — address in-loop.

Exit the loop only when **both** are true: (a) the verdict is approved, **and** (b) zero Addressable or Cheap-fix-override items remain after the sub-agent's re-classification. The reviewer's own summary ("zero blocking", "all deferrable", "nothing addressable", "fast-follow only") does **not** make (b) true on its own — re-classify every listed item against the rubric above before exiting. The reviewer can frame items politely; the sub-agent decides whether they're addressable on this PR. If the re-classification finds any Addressable or Cheap-fix-override item, the loop continues — even when the reviewer's verdict line says "approved with zero blocking". A verdict like "approved with minor fixes" or "approved, with these nits" is the loop telling you it isn't done yet, not a green light to exit.

When you do exit, file each explicitly-deferred item as a follow-up issue per "Follow-up issue tracking" above — urgency `file-now`, type chosen per the reviewer's framing (`bug` if the deferred item is a real defect, `incomplete-feature` if it's a half-built capability the reviewer flagged, `deferred-test` if it's a test the reviewer accepted should be skipped). The filed URLs land in this iteration's PR body `## Follow-ups` section before push and in the sub-agent's `items_filed_as_followups` return field. Procedural-only items (informational caveats with no tracked work) are not filed — emit them in `items_carried_as_procedural_notes` for §11's summary.

The full canonical suite will run once at PR-readiness time inside `github-pr-evaluator` — there's no in-loop final gate here.

#### §10.6 — Pre-push verification gate

Run inside the sub-agent on every iteration that produced code changes (per the sub-agent prompt's step 7). Same three-step gate as §8, per "Test selection during iteration" above:

1. **Static checks** — run the `<!-- issue-resolver-fast-checks -->` block inline, fail-fast in declaration order. Outputs are small (lints, codegen, layer-import boundary checks); no need to delegate.
2. **Test selection** — spawn an `Explore` sub-agent with the prompt template from "Test-selection sub-agent" above. Substitute the worktree path, integration target, and the project's `<!-- issue-resolver-test-target -->` block. The sub-agent reads the diff, lists each declared target's directory, applies the heuristics, and returns two sections: `COMMAND:` (a ready-to-run shell command, or `(none)`) and `RATIONALE:` (one or two sentences). Capture the rationale in the iteration's PR-status comment so the user can audit the selection.
3. **Test execution** — if `COMMAND:` is `(none)`, skip execution and continue. Otherwise, run the command. If it begins with `xcodebuild` (or invokes a wrapper that runs `xcodebuild`), delegate to `apple-platform-build-tools:builder`; otherwise run inline.

If run 1 is green, proceed to the sub-agent's step 8 (commit and push). If run 1 is red, follow the ladder in "Retry ladder for the verification gate" above — at most 3 runs this visit, with a forced research breakpoint between cheap and deep fixes, escalating if the deep fix also fails — per the retry ladder's "Escalation" section, you return `status: "needs_decision"` with `kind: "verification_failure"` and the main loop asks the user (you cannot call `AskUserQuestion` from inside the sub-agent). (Each entry to §10.6 starts a fresh ladder; the main loop's 5-iteration outer-loop cap governs how many times this whole gate can repeat across iterations.) If `COMMAND:` was `(none)` (e.g., docs-only iteration), there's nothing to be green or red — `github-pr-evaluator`'s full canonical run will exercise the change at PR-readiness time. Don't fall back to "run zero tests" when the sub-agent's heuristics could have widened — re-spawn the sub-agent if the rationale looks wrong.

#### §10.7 — Pre-summary state refresh (mandatory)

Between the §10 outer-loop exit and the §11 summary, run:

```bash
gh pr view <N> --repo <owner/repo> \
  --json state,reviewDecision,headRefOid,isDraft,baseRefName,headRefName,title \
  > /tmp/gh-resolver-<ISSUE>/pr-state.json
```

This is a **mandatory** tool call, not advisory. It serves three purposes simultaneously: (a) refreshes the PR state markers (`review: APPROVE at <sha>`, `state: draft`, `base: <branch>`, etc.) that §12's renderings consume — `../_shared/handoff-format.md` enumerates the closed-set marker vocabulary; (b) breaks the prose-emission momentum from `/review`'s verdict (the same operational-anchor pattern that makes `github-pr-evaluator` immune to the turn-boundary failure on its own verdict-to-handoff path — pr-evaluator's §7→§15 chain runs through acceptance-criteria check, branch-health gate, merge action, each a forced `gh` call); (c) gives §11/§12 a single canonical input file rather than relying on in-conversation state that may have rolled out of focus. **Read the file's content** into the summary's PR-line markers; do not re-derive from earlier conversation memory.

### 11. Summarise for the user

§11 fires on every clean exit from §10. Do not skip it on an approved + zero-items iteration. Do not summarize-and-stop after the loop. The Step 12 `## Handoff` at the end of §11 is the only bridge to the next session — its absence is indistinguishable from "work is done", which on a multi-phase issue is wrong.

**Before composing the summary, `Read references/handoff-renderings.md`** — this is the file that holds the seven rendering shapes you'll match the outcome against. Forced into the chain here so that the renderings are in your working context regardless of where SKILL.md was truncated on initial load (SKILL.md exceeds the default Read cap; the forced Read is load-bearing for §12's emission). Also read §10.7's `/tmp/gh-resolver-<ISSUE>/pr-state.json` — that file is the canonical source for §12's PR-line state markers (`review: APPROVE at <sha>`, `state: draft`, etc.).

**Outcome rubric — what shape does the Step 12 handoff take?**

Classify the run's outcome before writing the summary; it determines which Step 12 rendering fires. The handoff fires on every clean exit (forward, terminal, or re-route) — only the shape differs.

| Outcome | Step 12 rendering |
|---|---|
| Story / bug-fix / refactor PR opened or updated (§8 or §10 paths reached push), single-phase | **Forward → `github-pr-evaluator`.** The default code-change outcome. |
| Multi-phase issue: **non-final** code phase pushed; later phases remain in the plan's `## Phases` | **Re-route → `github-issue-resolver` (continue).** Handoff names the next phase by title (read verbatim from the plan's `## Phases`) and points the user at `/github-pipeline:github-issue-resolver #N` in a fresh session. PR stays in draft. |
| Multi-phase issue: **next phase is operator / decision-only** (current phase's depends-on is now satisfied but the next phase ships no code) | **Terminal-with-action.** Handoff names the operator action verbatim from the plan's `deliverable` field (e.g. *"run `./scripts/spike-640.sh`, post the per-cell table to #640"*). A `Then:` line points back to `/github-pipeline:github-issue-resolver #N` for the phase that follows the operator action. |
| Multi-phase issue: **last planned phase shipped** (every phase in `## Phases` now ticked in `## Phase tracker`) | **Forward → `github-pr-evaluator`.** Immediately before emitting the handoff, flip the PR draft → ready via `gh pr ready <N> --repo <owner/repo>` so the evaluator's §3 draft-PR guard doesn't deadlock it; the rendering's `state: open` marker reflects the post-flip state. On a soft-reject the evaluator flips back to draft (`github-pr-evaluator` §11) and the resolver re-enters in continue mode. |
| Epic-integration PR opened or updated (epic-target run finishing an epic) | **Forward → `github-pr-evaluator`.** The integration PR carries more merge risk than any single story PR; the handoff calls this out so the user knows pr-evaluator will run the full canonical suite, evaluate against the epic's `## Definition of done`, and ask for the merge mode. |
| Comment-only answer (question, clarification, decision capture; no diff, no PR) | **Terminal.** No PR for pr-evaluator to evaluate; the handoff names the issue's current state and closes the pipeline for this run. |
| Triage / classification only (relabel, retitle, link to a duplicate; no PR) | **Terminal.** Same shape as comment-only. |
| Abandoned / declined / stale-issue close (user opted out of opening a PR) | **Terminal.** Same shape — name the close reason in the `Why:` line. |
| §4.5 fitness audit blocked the run (issue body fails fitness-to-implement) | **Re-route → `github-issue-drafter` (revise).** The handoff names the failing audit dimension and the specific evidence so the drafter's revise loop can act without re-investigating. |
| §4.6 plan-currency drift or §8 plan-invalidation surfaced mid-work | **Re-route → `github-issue-planner` (revise).** The handoff quotes the locked decision verbatim and cites the `file:line` where the contradiction surfaced. |
| §4.7 malformed `## Phases` blocked the run (planner emitted unparseable phase shape) | **Re-route → `github-issue-planner` (revise).** The handoff quotes the specific malformation (missing key, unresolved `closes-dod` reference, etc.). |
| §6 doc-conflict that can't be reconciled in-skill | **Re-route → `github-issue-drafter` (revise).** The handoff names the doc citation and the body claim that contradicts it. |

**Phase-exhaustion check (multi-phase issues only).** Before deciding which multi-phase row above fires, check whether the plan's phases are exhausted:

1. Re-read the plan comment's `## Phases` section (captured at §4.7).
2. Cross-reference the PR's `## Phase tracker` checkboxes plus the just-pushed phase to determine which phases have shipped.
3. If unshipped phases remain, classify the run per the *non-final code phase* or *operator / decision-only* row depending on the next phase's `kind`.
4. If every phase in `## Phases` is now ticked in `## Phase tracker`, fire the *last planned phase shipped* row.

This is intentionally narrower than a DoD check. The resolver records a **mechanical projection** of the planner's `closes-dod` declaration onto the issue body — ticking exactly the bullets the plan claims, attributing each to the phase + commit that shipped (see §9's "DoD projection rule"). The evaluator owns the **semantic judgment** — verifying each projected claim against the per-phase diff at PR-readiness time, and un-ticking with a rejection annotation when the diff doesn't actually satisfy the bullet (`github-pr-evaluator` §6). The PR's `## Phase tracker` remains the **primary routing signal**; issue-body DoD ticks are a downstream projection, never read for routing. The resolver reads the Phase tracker on every run (routing) and on every re-entry (DoD reconciliation per §4.7); it reads the issue-body DoD ticks only to compute the projection diff for the next `gh issue edit`. A misjudged `closes-dod` mapping in the plan surfaces at the evaluator's per-phase verification rather than being silently rubber-stamped by the resolver.

If the run produced *both* a comment and a PR (e.g., posted a "starting work" comment then opened the PR), treat it as a PR outcome — the PR is what pr-evaluator acts on. If a re-route fired *after* a draft PR was opened (the resolver started work, hit a plan-invalidation, and stopped), the draft PR stays open and the handoff's PR line carries `state: draft`; the user re-runs the resolver in continue mode after the prior skill's revise lands.

**Before writing the summary, run the end-of-§10 follow-up checkpoint.** Per "Follow-up issue tracking" above, present the registry's `file-at-checkpoint` items (planning-time and implementation-time discoveries that weren't filed in-flight) to the user for batch approval, file via the sub-agent protocol, weave URLs into TODO markers and the PR body's `## Follow-ups` section. This is the resolution's last chance to convert trackable observations into filed issues before §11 closes things out; observations that aren't filed here become PR-body lines that age into noise.

The summary MUST include a clearly-labeled **Iteration test status** line that names the result of the most recent pre-push verification gate (§8 on a clean first-pass approval, §10.6 on the last iteration when the review loop ran): green, skipped (no tests selected — name the rationale), or red (a list of failing tests with their failure mode). When the run went through §10's review loop, **read this from the last sub-agent iteration's `iteration_test_status` field** verbatim — do not re-derive it from the worktree or the PR. If the final iteration was a zero-edits exit (no push), use the *prior* iteration's `iteration_test_status` since that's the test signal that gated the most recent push. If anything is red at this point, fix it before pushing — don't bury it in follow-up notes. The skill does not run a final canonical-suite gate at this step; the comprehensive run happens once at PR-readiness time inside `github-pr-evaluator`. State this explicitly in the summary so the user knows what's still ahead: e.g. *"Iteration test status: green at <SHA> (selected ProposalServiceTests, run at §8 pre-push). The full unit + UI suite will run in github-pr-evaluator before merge."*

Then: a short summary of what you did, what you posted (if anything), and a **Follow-ups** section split into two bullets — *Filed* (URLs of issues filed via the protocol, both `file-now` and `file-at-checkpoint`) and *Procedural notes* (informational items captured in the PR body, not filed as issues per the filing-vs-capturing criterion). When the run went through §10's review loop, the main loop's accumulated lists populate both bullets directly: the union of every iteration's `items_filed_as_followups` provides the *Filed* entries (one bullet per URL), the union of every iteration's `items_carried_as_procedural_notes` provides the *Procedural notes* entries, and each `user_decisions` entry across the run adds one additional *Procedural notes* line naming the guard rail that fired and the user's choice (so any deadlock, architectural-decision, verification-failure, or iteration-cap intervention stays visible). If you created or reused a worktree, include its path and the manual cleanup sequence. The `github-pr-evaluator` skill runs both phases automatically after a green merge (its §14); the manual form below is for runs that don't go through the evaluator (declined merge, manual close, abandoned issue):

1. From inside the worktree, run the project's worktree-teardown commands (see "Worktree setup & teardown commands"). If `COMMANDS.md` declares no `<!-- worktree-teardown -->` block, skip this step.
2. From the main checkout, run `git worktree remove .worktrees/<branch-name>`.

Don't run cleanup yourself: a worktree may hold unpushed work, and teardown may release resources still useful for debugging.

If the resolved issue was a **story** under an open epic, include two additional reminders:
- The parent epic's `## Stories` checkbox for this story is still `- [ ]` — it won't auto-tick on PR merge. A future epic-targeted run (or the user manually) needs to sync it.
- The change has landed on the epic integration branch, not `main`. It will reach `main` via the integration PR for epic #N once all stories under that epic are complete.

**Close with the Step 12 Handoff.** After everything else in §11 has been emitted (Iteration test status, summary, Follow-ups split, worktree cleanup notes, story / epic reminders), end the run with the Step 12 handoff block defined in the next section. Don't author a separate "Next step" line — the handoff *is* the next-step signal, and the rubric above already classifies which rendering fires.

### 12. Handoff

Every clean run of the resolver ends with a single `## Handoff` block — the schema, omission rules, and state-marker vocabulary live in [`../_shared/handoff-format.md`](../_shared/handoff-format.md). The handoff is the only bridge between this session and the next: the user copies the fenced command into a fresh Claude Code session.

**Re-route rule.** When the outcome is a re-route (§4.5 fitness audit, §4.6 plan-currency, §6 doc-conflict, §8 plan-invalidation), the handoff is the **only** form of next-step communication. **Do not** invoke the prior skill via the `Skill` tool — that would cross a session boundary silently and defeat the session-per-skill design. The handoff names the revise command; the user runs it in a fresh session.

Pull the snapshot from data already in hand: the issue/plan state from §2's `GATHER_ISSUE` (plus any re-fetch from §4.6's currency check), the PR number/URL/state from §9's `gh pr create` / §10's continuation, the review-loop state from §10's last iteration (`iteration_test_status` already feeds §11's summary), and the originating epic data when the resolver ran in story or epic mode. The `Why:` line is judgment — for forward routes, describe what the next session will do; for re-routes, quote the specific finding (locked decision, doc citation, audit dimension + evidence) so the prior skill's revise loop can ground in it without re-investigating.

#### Renderings

**See [`references/handoff-renderings.md`](references/handoff-renderings.md) for the seven rendering shapes** the resolver emits — forward (standard / story), re-route (multi-phase non-final, multi-phase operator-action, multi-phase last shipped, planner-revise, drafter-revise-fitness, drafter-revise-doc-conflict), forward (epic-integration), and terminal (non-PR). The §11 forced `Read` of that file ensures every shape is in your working context before composing the summary. Each rendering carries the closed-set state-marker vocabulary from `../_shared/handoff-format.md` (`plan: ✓ | ✗ | stale`, `review: APPROVE | COMMENT | not run`, `health: ✓ at <sha> | ❌ at <sha> | not run`, `merge: not run`); §10.7's `pr-state.json` refresh feeds those markers their current values.

## Common pitfalls

- **Don't ignore in-progress PRs.** Always check for an existing open or draft PR before creating a branch. Opening a duplicate PR wastes everyone's time and is rude.
- **Don't take over someone else's PR silently.** If a PR by another author exists for this issue, surface it to the user before doing anything that would compete with or supersede it.
- **Don't implement code without grounding in project docs.** If `docs/prd.md`, `docs/architecture.md`, or `CLAUDE.md` exists, read it before designing the change and cite the relevant sections in the PR. Skipping this leads to implementations that violate non-negotiable project rules (layer boundaries, banned APIs, naming, scope) that the docs encode.
- **Don't start non-trivial code work without a finalized plan.** Step 4.6 gates on a `github-issue-planner` plan comment. Missing on a non-trivial issue → stop and ask for one (or take the user's explicit `proceed without a plan` override, recorded in the PR body). The plan is where the approach was researched and verified; improvising past a missing plan throws that away. Trivial fixes and comment-only flows are exempt — the gate doesn't fire for them.
- **Don't re-plan when a plan exists.** When step 4.6 finds a plan, consume it — lift its grounding and implement its locked decisions. Re-deriving the approach in the main conversation duplicates the planner's verified work and risks diverging from the artifact the pr-evaluator will check against. The exception is the plan-currency check: if the code or issue body drifted since the plan's SHA, route back to the planner in revise mode rather than patching around the staleness.
- **Don't silently deviate from a locked plan decision.** Implementing freely *within* the plan's decisions is expected; reversing one (a planned API, layer assignment, or data-model shape that turns out wrong) is not — stop and route back to `github-issue-planner` in revise mode with evidence. A quiet workaround diverges the diff from the plan, breaks pr-evaluator's adherence check, and loses the decision's provenance.
- **Don't skip the green-baseline check for the integration target.** The integration target is `main` for regular issues and the epic integration branch for stories under an open epic. A story under an open epic *inherits* the epic-level baseline and shouldn't re-run it — unless `main` has been merged into the epic branch since that baseline, or a prior story under the epic landed under an explicit baseline override. The point of the gate is correct failure attribution and not shipping over a broken codebase, not running tests for their own sake. If the baseline is red, stop and surface every failing test — silent fixes scope-creep the PR. Acceptable next moves are the same as in step 7: detour first, or explicit user override with a documented reason.
- **Don't silently fix unrelated pre-existing failures.** If the baseline reveals broken tests outside the scope of this issue, surface them — don't fold the fix in without telling the user. It scope-creeps the PR and obscures what your change actually did.
- **Don't push code without running the §8 pre-push verification gate.** The test gate runs at §8 (before the first push) AND at §10.6 (after addressing review feedback). Both are mandatory pre-push gates. On a clean first-pass review approval, §10.6 never fires — the §8 gate is the only test invocation that runs before the PR is opened. Skipping §8's tests on the assumption that "review will catch it" or "pr-evaluator will catch it" is a bug: the `review` skill is a code-quality reviewer that does not run tests, and `pr-evaluator` runs at PR-readiness time *after* the PR is already open with possibly-broken code on the branch.
- **Don't run the full unit + UI suite at the §8/§10.6 story gates.** Those gates run targeted tests; the full canonical suite runs in `github-pr-evaluator` (for epic-integration and labelled PRs) and on CI. Reproducing the full suite at a story gate defeats the targeted-tests strategy and re-imposes the cost-per-iteration this design exists to avoid. If you find yourself reaching for `<!-- pr-evaluator-static-checks -->` or `<!-- pr-evaluator-test-target -->` at a story gate, you've drifted off the path. (The epic-baseline / bootstrap / post-rectification flow *does* run the full canonical suite — that is the documented exception; see "Running the full canonical suite".)
- **Don't fall back to zero tests when uncertain.** "Zero tests" is reserved for empty-diff and pure-docs paths. Any code change that the sub-agent can't narrow with confidence should hit the project's `broad-change-fallback` (typically "all unit tests, no UI") for the unit target. UI uncertainty defers to pr-evaluator (the `none` broad-change-fallback path) — that's intentional. But never push code with zero tests run on the theory that "pr-evaluator will catch it" when widening was the right call.
- **Don't inline the test-selection reasoning in main context.** The diff hunks, directory listings, and grep output stay inside the `Explore` sub-agent. Main context sees only the resolved `COMMAND:` and the one-line `RATIONALE:`. Inlining the reasoning regresses on token cost and clutters the conversation; pulling diff content into main context is exactly what the sub-agent indirection prevents.
- **Don't skip the rationale audit.** Print the sub-agent's `RATIONALE:` line to the user verbatim before executing the command. The user must see what was selected and why; silent selection is a regression even when correct, and bad selections are how this design fails — make them visible so they can be corrected.
- **Don't let the build subagent become a coder.** When delegating to `apple-platform-build-tools:builder`, the prompt MUST scope the subagent to "run the command and report result" only. No code edits, no failure-investigation expansion, no automatic re-runs with different flags. A subagent that silently turns a 30-second test run into a 55-minute diagnose-edit-rebuild loop hides changes from your commit history and the user's audit trail, and breaks the review-loop's contract that you control when code changes happen. If the build subagent reports a failure, surface it; don't hand it carte blanche to fix things.
- **Don't iterate small fixes when failures are sticky.** Two §8 (or §10.6) runs with the same failing test means the underlying understanding is wrong, not the patch. Take the research breakpoint per "Retry ladder for the verification gate" — read the full failure output, capture `app.debugDescription` for UI tests, spawn an `Explore` sub-agent for structural read of the failure. Continuing to tweak burns 10–20 minutes per attempt with no information gain, and the same loop bounded by the build subagent's pitfall above applies one layer up: the *parent* model running tweak → re-run → tweak → re-run is the same anti-pattern, just at a different layer.
- **Don't `rm` snapshot goldens to force regeneration.** A failing snapshot test means a pixel-level visual change that needs human eyes — the whole point of snapshot tests is to surface those. Surface the diff to the user and ask before deleting. Auto-regenerating goldens silently accepts visual regressions and defeats the test category's purpose. If the user confirms the visual change is intended, *then* delete and regenerate; record the confirmation in the PR body so reviewers can audit.
- **§8 is the pre-push gate, not the dev inner loop.** Iterate at unit-test granularity locally first — the project's wrapper supports `-only-testing FoodJournalTests/<SuiteName>` and Swift Testing suites typically run in well under a minute. Reserve the §8 invocation (which legitimately includes UI tests via the test-selection sub-agent's widening rules) for the once-before-push integration check. Treating every code change as "make change → §8 → react" turns a 30-second feedback cycle into a 20-minute one and is the most direct cause of the small-fix spiral.
- **Don't read only the PR diff.** PR comments and code review threads (especially line-level review comments, which require a separate API call) are where decisions actually got made. Skipping them leads to redoing rejected work or contradicting settled directions.
- **Don't trust the issue title alone.** The title often reflects the original report; the actual problem may have shifted in the comments.
- **Don't re-litigate decided questions.** If a maintainer said "let's go with approach B" three comments ago, go with approach B.
- **Don't open a PR for a question.** Some issues are resolved by an answer, not a code change.
- **Don't skip the review loop.** For any PR, `review` must approve before the work is considered done. No exceptions, no "this change is too small to review."
- **Don't exit the loop just because the verdict says "approved".** Reviews routinely approve with `Medium`, `Low`, or `Nitpick` items — issues *and* suggestions — that the reviewer still expects fixed (e.g., "Approved with minor fixes"). Per §10.4, exit only when `review`'s verdict is approved **and** the sub-agent's re-classification finds zero Addressable or Cheap-fix-override items in that verdict. Items the reviewer routes elsewhere with a **concrete tracking target** (filed as #N, depends on un-landed sibling, citable PRD/scope exclusion) are deferred and filed as follow-ups. Soft politeness alone ("could be fast-follow", "not blocking", "deferrable", "informational only", "future PR", "consider for a future change") is **not** sufficient — the sub-agent re-classifies per §10.4's rubric, and the **default for any concretely-named change is Addressable**. The Cheap-fix override addresses ≤ ~20-line fixes on already-modified files even when the reviewer defers them. The sub-agent boundary enforces this structurally for the *body* of an iteration (classify + act), and the main loop's tight "read JSON → re-invoke `review` or proceed to §11" sequencing protects the outer loop's exit decision — but the rubric still governs whether the loop should exit at all, so the hazard this bullet exists for hasn't gone away.
- **Don't drive `review` from inside the §10 sub-agent.** The `review` command (and the bundled `code-review` skill) is not reachable from inside an `Agent`-dispatched sub-agent — the `Skill` tool inside a sub-agent only reaches *project, user, and plugin* skills (per the [sub-agents reference](https://code.claude.com/docs/en/sub-agents)). Putting `Skill(skill="review")` inside the §10 sub-agent prompt was the original design and it consistently failed: the sub-agent had no path to the actual review and was forced to improvise a manual one, returning prose instead of the JSON envelope (PR #607, chat log at `/tmp/review-skill.md`). The fix is structural — `review` runs in the main conversation per §10's outer-loop control; the sub-agent classifies + addresses the verdict the main loop hands it. Don't reintroduce the `review` invocation into the sub-agent prompt thinking "this time stronger emphasis will work" — the constraint is the harness, not the model.
- **Don't stop at either turn-boundary beat in §10.** §10 has two beats where the model can summarize-and-stop before the run finishes; both are the *PR #416 failure mode (`/tmp/review-loop.md`)* and the *#653 missing-handoff failure mode (`/tmp/no-handoff.md`)* re-imported one layer up. The primary anti-stop in §10 is the operational anchor at §10.7 (refresh PR state via `gh pr view <N> --json …`); this pitfall is the backup. (a) **After `Skill(review)` returns** — the verdict text reads like a finished deliverable, but `/review`'s job is only to emit the verdict, not to close the loop. Your next tool calls in the same turn are `Write` the verdict file, `gh pr comment` (if `/review` did not already post one), and `Agent` dispatch — even when the verdict says "approved, zero open suggestions" (the sub-agent's step 6 handles that path with an early return). (b) **After the §10 sub-agent returns** — the next beat is either re-invoking `Skill(skill="review")` for another iteration, rendering a `needs_decision` via `AskUserQuestion`, or proceeding to §10.7 / §11 / §12 if the exit condition holds. Treat reading the JSON as a step inside an iteration, not the end of one.
- **Don't post review feedback on the issue.** Review feedback on a PR goes on the PR, not on the originating issue.
- **Don't mis-route comments between issue and PR.** Use the rubric in "Where comments go" — problem questions go on the issue, solution questions go on the PR. Cross-posting or wrong-routing fragments the discussion and leaves future contributors hunting.
- **Don't assume the issue is still relevant.** If the thread has gone quiet for a long time, flag this and ask whether to proceed.
- **Don't `git worktree add` a branch that's already checked out.** Git will error. Always run `git worktree list --porcelain` first and reuse the existing worktree if found.
- **Don't nest worktrees.** If you're already inside `.worktrees/foo`, locate the main working tree first (the first `worktree` entry in `git worktree list --porcelain`) and create the new worktree relative to that.
- **Don't forget `.worktrees/` in `.gitignore`.** Without it, every worktree's files show up as untracked in the main checkout's `git status`.
- **Don't auto-clean worktrees.** A worktree may contain unpushed commits or in-flight edits. Cleanup is the user's call.
- **Don't open a single feature PR for an epic.** Epics are containers; child stories are where code lands. Opening a monolithic PR for an epic conflates resolution with implementation and makes the PR unreviewable.
- **Don't target `main` for a story under an open epic.** The whole point of the integration branch is to keep `main` stable while the epic is in flight. If a story PR points at `main`, that defeats the model. The base must be `epic/<N>-<slug>` while the epic is open.
- **Don't let the epic branch drift silently — but only act from epic-as-target runs.** Check epic-vs-main drift on every epic-as-target run and rectify when drift is found, choosing rebase or merge per the rule in "Check the integration branch" → "Choose strategy". When rebasing, push with `--force-with-lease` (never bare `--force`); when merging, push normally. Story runs surface epic-vs-main drift as an informational state-summary note only — they never rectify the epic branch, because the rectification crosses responsibility boundaries and a story-flow rebase would force-push under sibling story PRs. Long-lived branches that aren't periodically synced with main become unmergeable, but the rectification belongs to the epic owner.
- **Don't recompute the epic branch slug — discover it.** The slug rule is deterministic for the bootstrap path, but the epic title can change *after* a branch is created, and a stricter or shorter informal slug rule on a future run silently fails to match. This is exactly how issue #102 was hit: run 1 created `epic/102-visual-redesign`, run 2 computed `epic/102-daily-journal-visual-redesign`, and an exact-match existence check would have orphaned all the story commits already on the original branch. Always discover by prefix (`git ls-remote --heads origin "epic/<N>-*"`) and use whatever name comes back. Recompute only when discovery returns zero matches and you're on the bootstrap path.
- **Don't run epic baseline in the main checkout.** Both bootstrap (first-time creation of `epic/<N>-<slug>`) and legacy recovery (branch exists but no `Baseline established` comment) use a worktree at `.worktrees/epic-<N>-<slug>`. Running the canonical suite in the main checkout would force a `git checkout main`, prevent the user from using the main checkout for unrelated work during the long suite run, and contradict the skill's "main checkout stays untouched" invariant that every other epic and story flow already respects.
- **Don't cold-rebuild the canonical suite on every re-run, and don't background it with a relative `cd`.** For the epic-baseline suite, the first attempt is the `issue-resolver-canonical-suite` `full-suite` command; any re-run is `build-once` then `retry-without-rebuild` — re-issuing `full-suite` re-pays the cold build that dominates wall time (this is what turned one re-baseline into a multi-hour hang). Run it as a main-loop background bash with absolute paths: a relative `cd .worktrees/<branch> && …` no-ops when the shell is already in the worktree and `&&`-short-circuits to a false "exit 0" with no tests run, and a sub-agent delegation can end its turn mid-build and lose the tally. See "Running the full canonical suite".
- **Don't merge the integration PR without running the review loop.** The integration PR lands the entire epic on `main` at once — it carries more risk than a single story PR. Apply step 10 to it just as you would any story PR.
- **Don't ignore the body checkboxes when closing an epic.** Body checkboxes don't auto-sync. A `- [ ]` next to a closed story is stale and misleads the next person who reads the epic. Always tick them before (or as part of) closing.
- **Don't restructure the epic body template.** The `## Goal` / `## Background` / `## Stories` / `## Definition of done` section names are load-bearing for traceability from `docs/prd.md`. Preserve them exactly.
- **Don't edit a parent epic's body from inside a story-target run.** The epic's body is authoritative state; it should only be updated from an epic-target run where you can see the full story-reconciliation picture.
- **Don't push within the review loop without re-running the full suite.** Same reason as the baseline: the only way to attribute new failures to the right commit is to keep the suite green at every push. Skipping the test run between feedback rounds defeats the green-baseline gate retroactively.
- **Don't skip worktree-setup on the create arm.** A worktree without its setup commands run is in a partially-initialised state — tests may run against missing resources (a simulator that doesn't exist, a port that's already in use, a database that wasn't seeded). Run setup immediately after every `git worktree add` succeeds, before any test, lint, or build.
- **Don't run worktree-setup on the reuse arm.** A reused worktree already has its resources from the original create event. Re-running setup risks double-provisioning: a second simulator alongside the first, a port collision, a fresh database that wipes the worktree's existing state. The reuse arm is a "skip setup" arm by design.
- **Don't auto-clean a worktree without running teardown first.** Teardown releases the resources setup created — orphan simulators, orphan containers, leaked ports — so skipping it leaks them silently. The skill never auto-removes worktrees in any case (manual cleanup is the user's call), but when the user does cleanup, the sequence matters: teardown first, then `git worktree remove`. The §11 reminder names both.
- **Don't hand-craft follow-up issue bodies.** Every follow-up that warrants an issue goes through the sub-agent protocol in "Follow-up issue tracking". Hand-crafting (writing the body inline, running `gh issue create` directly) bypasses the drafter's PRD-grounded review loop and produces issues with inconsistent format, missing parent references, and unvalidated framing against the project's architecture / constitution. The drafter exists exactly for this — its classification, body templates, and sub-agent review are what make filed issues consistent across the repo. Use it.
- **Don't conflate filing with capturing.** Procedural reminders (drift, epic-checkbox sync, "watch out for X in the next iteration") belong in the PR body or §11 notes, not as filed issues. Issues are for trackable work that needs a separate place to discuss, plan, or assign; PR-body notes are for informational caveats a future contributor can act on with the PR context alone. Filing both as issues clutters the backlog; capturing both as PR-body notes loses the trackable ones. Use the filing-vs-capturing criterion in "Follow-up issue tracking".
- **Don't omit the pr-evaluator handoff on PR outcomes.** §11's closing **Next step** line is the resolver's explicit handoff to the merge-readiness gate. Without it, users finish a resolution thinking the work is done — but the resolver has only run `/review` for code quality and targeted tests for verification; issue-fit against the originating issue, full canonical-suite execution, and merge-strategy selection happen inside `github-pr-evaluator`. Dropping the line leaves the user to remember on their own that pr-evaluator exists, which is exactly the dropoff this handoff is designed to prevent. Emit it on every PR outcome, including epic-integration PRs (where the merge risk is higher and the handoff matters more, not less).
- **Don't hand off to `github-pr-evaluator` until the plan's last phase has shipped.** On a multi-phase issue (per §4.7), the PR must not be evaluator-bound while phases in the plan's `## Phases` are still unshipped. Emitting the evaluator handoff after a non-final phase invites the evaluator to merge a partial implementation — which is exactly how Phase 1 of #640 landed on `main` as #648 before any DoD item was satisfied. Re-route to the resolver (for the next code phase) or surface the operator action verbatim (for the next non-code phase) instead, per the §11 outcome rubric. Only the *last planned phase shipped* row fires the evaluator handoff.
- **Don't mark a multi-phase PR ready, and don't add `Closes #N` in reaction to shipping the last phase.** A multi-phase PR opens as draft at §9 and stays draft through every phase the resolver pushes — including the last one. Marking it ready or fiddling with the `Closes` directive in the title or body is judgment that belongs to the evaluator: it owns the DoD check that decides whether the shipped phases actually satisfy the issue. The resolver's only signal that "the planned phases are done" is the forward handoff to the evaluator; the evaluator does everything downstream of that — including, on a clean DoD pass, marking the PR ready and merging.
- **Don't tick DoD bullets the phase's `closes-dod` doesn't claim.** The resolver projects the planner's declaration onto the issue body; it doesn't infer. If a phase's `closes-dod` lists bullets `[1, 3]`, those are the only bullets that flip on this push — even if the diff happens to also satisfy bullet 2. Bullet 2 is claimed by a different phase (per the planner's Dimension-7 exact-coverage invariant), and ticking it here would mis-attribute the closure on the issue body. If you believe the plan is wrong, route back to the planner in revise mode; never silently tick beyond the declaration.
- **Don't re-tick DoD bullets the evaluator has rejected.** A bullet annotated `- [ ] <text> (resolver claimed phase <N>, ...; evaluator rejected: ...)` is the evaluator's sticky veto — the diff in the attributed commit(s) didn't actually satisfy the bullet. Projection logic treats annotated-as-rejected bullets as not-projected even when `Phase tracker × closes-dod` would tick them. The disagreement is resolved by re-planning, by a new code phase whose diff actually satisfies the bullet, or by user intervention — not by silent re-ticking on the next push. Re-ticking would clobber the evaluator's evidence and re-introduce the silent rubber-stamping failure mode the per-phase verification exists to prevent.

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

Otherwise, proceed.
