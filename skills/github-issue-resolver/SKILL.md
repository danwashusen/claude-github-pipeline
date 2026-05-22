---
name: github-issue-resolver
description: Investigate and resolve a specific GitHub issue end-to-end via the `gh` CLI. Trigger when the user gives an issue number/URL or asks to "look at", "work on", "fix", "implement", "resolve", "triage", or "respond to" an issue — bugs, features, questions, or refactors. Reads the issue and its full comment thread (separating stale early discussion from latest decisions), on a fresh implementation start audits the issue body for fitness-to-implement (doc tensions, cross-issue contract drift, underspecified contracts) and routes blocker findings to `github-issue-drafter` in revise mode before any code work begins, skips the audit when continuing an in-flight PR, checks for existing open/draft/prior PRs to avoid trampling in-progress work, decides the response type, does the work, and posts a comment or opens a PR. For code changes, opens or continues a PR and loops with the `review` skill until approved. Reads `docs/prd.md`, `docs/architecture.md`, and `CLAUDE.md` to ground implementations. Recognises epics (long-lived `epic/<N>-<slug>` integration branch, child-story audit, integration PR) and stories under an open epic (PR base = epic branch). Use even on casual mentions ("look at #423?", "what is left in the auth epic?") — don't handle GitHub issues without it.
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

## Retry ladder for the verification gate

The pre-push verification gate (§8 before the first push, §10.6 after each round of review feedback) treats "tests must be green before push" as a goal, not a license to retry indefinitely. Without a cap, a complex UI-test failure can spiral into a sequence of small fixes — tweak, re-run a 10–20 minute UI suite, tweak, re-run, repeat — that burns hours of wall-clock time and produces nothing the review loop couldn't have surfaced in the first place. The cost compounds because each iteration re-pays the cold-build and simulator-boot overhead, and small fixes on a shallow read of a failure usually don't help anyway.

The ladder below caps a single visit to the gate at **3 test runs total** before escalation, and forces a research breakpoint between cheap fixes and any deep fix. It applies identically at §8 and §10.6.

### The ladder

| Run | Trigger | Allowed action after |
|---|---|---|
| 1 (initial) | First invocation of the gate this visit | If green → §9 (or §10.7 from §10.6). If red → 1 cheap fix. |
| 2 | After cheap fix #1 | If green → §9. If red AND the failing-test set strictly changed (some original failures resolved) → 1 more cheap fix allowed. If red AND the failing-test set is sticky (same set or grew) → **research breakpoint, mandatory**, even though only 2 runs have happened. |
| 3 (deep) | After research-informed fix | If green → §9. If red → **escalate to user** per "Escalation" below. No further runs this visit. |

A "cheap fix" is a small, narrowly-targeted edit (typo, missing accessibilityIdentifier, off-by-one, obvious binding mistake) on the immediate failure mode. A "deep fix" is a structural change informed by the research breakpoint — restructuring a gesture, lifting state, changing a focus model, etc.

### The adaptive cheap-fix rule

Whether the second cheap fix is allowed depends on whether the first cheap fix made *any* of the originally-failing tests pass. Compare the failing-test sets across runs:

- **Strictly changed** (e.g., run 1 fails {A, B}; run 2 fails {B, C}): at least one originally-failing test newly passed. The first fix worked on something; the new failure is plausibly a separately-trivial issue. One more cheap fix is allowed.
- **Sticky** (run 2 fails {A, B} again, or {A, B, C}): no originally-failing test resolved. The model's read of the failure is wrong. Force the research breakpoint immediately.

This rule exists because the small-fix spiral's signature is exactly *sticky failures with shrinking patches*: each iteration tweaks the same code path on the same wrong hypothesis. Detecting non-progress at run 2 cuts off the spiral before it doubles.

### Test selection on retry

Run 1 and run 3 use the test-selection sub-agent's full verdict on the cumulative diff. Run 2 does **not** — it skips the sub-agent and re-runs only the tests that failed in run 1.

| Run | Selection mechanism |
|---|---|
| 1 | Full sub-agent verdict on cumulative diff (per "Test selection during iteration" above). |
| 2 | **Skip the sub-agent.** Build the command directly: `<wrapper> test -only-testing <Suite>/<TestMethod>` for each test that failed in run 1, joined into a single invocation. Use the failing tests' fully-qualified identifiers as reported by the previous run. |
| 3 | Full sub-agent verdict on cumulative diff. The deep fix may have changed the blast radius (lifted state, restructured a view tree, modified a root-reachable view), so the sub-agent's heuristics — especially the UI blast-radius rules at step 5 of the prompt template — need a fresh look. |

The narrowing at run 2 is a deliberate departure from "trust the sub-agent on every gate visit." The justification: the sub-agent's job is selecting tests *given a diff*; on a cheap-fix retry the only new information is which specific tests failed, and the parent already has that. Re-running the sub-agent would either re-derive the same broad selection (no win) or narrow incorrectly without seeing the failure list (worse). Bypassing it on run 2 is faster and more correct for the cheap-fix case.

A previously-passing test that the cheap fix breaks will not be caught at run 2 — it will surface at run 3 (where the sub-agent's full verdict runs again on the now-larger diff) or, failing that, in `github-pr-evaluator`'s full canonical run at PR-readiness time. That gap is acceptable: the cheap fix is by definition small, and the safety net at pr-evaluator is exactly the reason this skill runs targeted tests rather than the canonical suite. The alternative — re-running the broad selection on every retry — is what produced the small-fix spiral this ladder exists to prevent.

### Research breakpoint requirements

When the ladder forces a research breakpoint (run 2 was sticky, or run 2 was a second cheap fix that also failed), the next step is **not** a code change. It's a forced, structured information-gathering pass. The point is to replace the model's shallow read of the failure — which has now demonstrably failed twice — with a real understanding before any deep fix is attempted.

During the breakpoint:

1. **Read each failing test's full output** — the assertion message, the stack frame, and the relevant simulator log lines. Not just the one-line summary the test runner prints.
2. **For UI tests, capture `app.debugDescription`** from inside the failing test and read the dump. CLAUDE.md mandates this on element-lookup timeouts; restate the mandate here. The accessibility tree usually points at the cause directly (collapsed parent, hidden element, identifier dropped, glass surface absorbing children).
3. **Spawn one `Explore` sub-agent** with: the failing test files, the source they exercise, the recent diff (`git diff <integration-target>...HEAD`). Have it return three things, in order:
   - What is *actually* failing (not what the test name suggests, not what the assertion line says — what's happening in the code paths the test transits)
   - What code paths the failing tests transit, including any indirection (gesture → focus → state → view re-render)
   - What structural change is implied by (a) and (b) — explicitly *not* a tweak

No code edits during the breakpoint. The deep fix happens only after the sub-agent returns and the model has internalised its findings.

### Escalation

When run 3 (the research-informed deep fix) is also red, stop. Do not run §8/§10.6 a fourth time. Surface to the user the failure analysis and three equally-weighted paths forward, with no default:

1. **Push with documented reds.** Open the PR (or push to the existing branch) with a `## Known failures` section in the PR body listing each red test, the reproduction signal, and what was tried. Let `review` decide whether any of the reds are blocking. Best when the failures look like CI/timing flakiness or genuinely separate edge cases that don't block the headline change.
2. **Defer the failing tests with linked issues.** File one follow-up issue per failure (or one umbrella issue if the failures share a root cause) via the sub-agent protocol in "Follow-up issue tracking" above — urgency `file-now`, type `deferred-test`. The filed URLs become `// TODO(#NNN)` markers and `XCTSkip("Deferred to #NNN — <reason>")` reasons before push. Push the rest green. Best when the failure is a real structural problem that needs more design than fits this PR.
3. **Restructure.** Abandon the current approach. Return to a planning conversation, with the research-breakpoint findings as input, and propose a different shape. Best when the deep fix revealed that the original approach itself was wrong (e.g., a gesture that fundamentally fights the parent's gesture system).

The summary at §11 records which path was taken and why. The user picks; the skill does not pick a default.

### What the ladder is and isn't

It **is** a cap on retries within a single visit to the gate. Each entry to §8 starts a fresh ladder (run 1 again). Each entry to §10.6 (one per review-loop iteration) starts a fresh ladder. The §10 sub-agent's 5-iteration outer-loop cap governs how many times `review` can flag changes; this ladder governs how many times the model may re-run tests within one of those iterations.

It **isn't** a license to give up after one failure. Run 1 failing is normal — that's why the gate exists. The ladder activates when the model is about to enter a small-fix spiral, not on every red run.

## Follow-up issue tracking

Follow-up items — adjacent bugs noticed during planning, incomplete features the diff exposed, deferred tests the retry-ladder or review loop punted, baseline detours that need their own PR — surface at four moments in this workflow: §7 baseline (pre-existing failures need a detour), the retry-ladder's escalation option 2 (defer failing tests), §10.4 (reviewer routes items to follow-up), and §11 summary (post-merge cleanup). Historically each moment improvised its own filing: some items got captured in PR-body lines that aged out of memory, others got hand-crafted `gh issue create` bodies that bypassed the project's `github-issue-drafter` skill and ended up with inconsistent format and missing parent references. The point of this section is to make filing follow-ups a single, predictable protocol that reuses the drafter's structure (PRD-grounded, sub-agent-reviewed, type-specific sections) rather than re-inventing it in each touch point.

### The follow-up registry

Maintain a working list — kept in your own conversation context, no file persistence needed — of follow-up items as they surface. Each entry has five fields:

- **Type** — `bug` | `incomplete-feature` | `deferred-test` | `revise-existing`. The drafter has a section template for each; classification matters because it determines the body structure.
- **Title hint** — one-line summary, drafter-style (e.g. *"Conflict prompt UI tests deferred under predictive-bar occlusion on .expanded × .session"*).
- **Description** — 2–5 sentences naming what's wrong / what's needed / why deferred. The drafter takes this as the informal feedback and shapes the body around it.
- **Parent reference** — the current PR URL or issue #, plus the parent epic # if applicable. Without this, the filed issue is orphaned.
- **Urgency** — `file-now` or `file-at-checkpoint` (see "Hybrid timing" below).

### Filing vs. capturing — the decision rule

Not every observation deserves a filed issue. Distinguish:

- **File as issue** when the follow-up represents distinct trackable work: a bug to fix, an incomplete feature to finish, a deferred test to re-enable, or a revision to an existing issue body.
- **Capture in PR body / §11 summary** when the follow-up is procedural / informational only: drift notes ("epic-203 is behind main by 16 commits"), epic checkbox-sync reminders, "watch out for X in the next iteration."

Criterion: would a future contributor, reading the PR body alone, have all they need to act? If yes, PR-body note suffices. If they'd need a separate place to discuss, plan, or assign — file an issue. Conflating the two is how trackable work gets lost: a one-line PR-body bullet is invisible the moment the PR merges.

### Hybrid timing

When each touch point files matters because some items need a real issue number in the same iteration's commits (TODO markers, XCTSkip reasons, PR-body cross-links).

| Source of follow-up | Urgency | When to file |
|---|---|---|
| Defer-by-retry (retry-ladder escalation option 2) | `file-now` | Before pushing the iteration's commits — the `// TODO(#NNN)` markers and `XCTSkip("Deferred to #NNN — …")` reasons need real issue numbers in the same push. Filing after-the-fact and amending the markers in a follow-up commit clutters history and risks the markers being missed. |
| Defer-by-review (§10.4 deferred items) | `file-now` | Same reason — review-deferred items often include test changes that need real issue numbers before the iteration's commit. |
| §7 baseline-failure detour (option a) | `file-now` | Before resuming the original work — the detour PR resolves the filed issue, and the original PR's body will cite the detour. |
| Planning-time discoveries (§6 doc grounding turned up adjacent work) | `file-at-checkpoint` | End of §10, after review approval, before §11 — batched. These don't gate any commit, so deferring to one moment is cleaner than interrupting the planning phase. |
| Implementation-time discoveries (mid-§8, the model notices a related bug) | `file-at-checkpoint` | Same checkpoint. Note them in the registry as they surface; file at end-of-§10. |

### The end-of-§10 checkpoint

After §10's review loop reports approval and before §11's summary, present the `file-at-checkpoint` items in the registry to the user:

> *"These follow-ups surfaced during this resolution but weren't filed in-flight. File them?"*
>
> *[list each item: title hint, type, one-sentence description]*

The user batch-approves, edits the list, or drops items. Only after batch approval do you spawn the sub-agents (one per item). Then weave URLs back into §11's summary.

### Filing protocol — sub-agent proxy-confirms via the drafter

For each item that the user has approved for filing, spawn a `general-purpose` sub-agent with this prompt (substitute the placeholders at call time):

```
You are filing one GitHub follow-up issue on behalf of the
github-issue-resolver skill. Invoke the `github-issue-drafter` skill,
proxy-confirm the draft, and return the filed issue URL.

Item to file:
- Type: <bug | incomplete-feature | deferred-test | revise-existing>
- Title hint: <one-line summary>
- Description: <2–5 sentences explaining the follow-up>
- Parent reference: PR <URL>, issue #<N>, epic #<E> (if applicable)
- Repository: <owner/repo>

Steps:

1. Invoke the github-issue-drafter skill, passing the description above as
   the informal feedback. State the type hint, title hint, and parent
   reference clearly so the drafter has them at classification time.

2. The drafter will run its own sub-agent review loop (it validates against
   the project's PRD, architecture, constitution, and current code state).
   Let it complete its review-loop passes — don't try to shortcut them.

3. The drafter will reach its step-6 user-confirmation gate ("Show the
   draft and wait for confirmation"). You act as the user at this gate.
   Run three checks:

   a. Type — does the drafter's chosen type match the hint? If the drafter
      decided differently (e.g., classified as `incomplete-feature` when
      you hinted `bug`), accept the drafter's call IF its rationale is
      sound. The drafter sees the description directly and may classify
      better than the hint; only override if the drafter has clearly
      misread the description.

   b. Parent reference — is the parent PR/issue/epic preserved in the
      body's Related-issues section? The drafter's bug, story, feature,
      and incomplete-feature formats all have this section. Without it
      the filed issue is orphaned. If missing, reply to the drafter:
      "Please add the parent reference (PR <URL>, parent issue #<N>) to
      the Related-issues section."

   c. Substance — does the body's What's-wrong / What's-missing /
      Definition-of-done content match the description? If the drafter
      hallucinated detail the description doesn't support, reply with a
      one-sentence correction.

4. Approve if all three checks pass. If any check fails, reply with the
   correction and let the drafter iterate. Cap at 2 correction rounds —
   if the third draft still fails any check, stop and return an error to
   the parent with the latest draft inline so the parent can decide.

5. After approval, the drafter runs `gh issue create` (or `gh issue edit`
   in revise mode) and returns the URL. Capture that URL.

Return only:
- The filed URL (or "error: <reason>" if you stopped at step 4's cap)
- The drafter's final type (in case it overrode the hint)
- A one-line note if you raised any correction before approving

Do NOT file an issue yourself with `gh issue create`. The drafter does
this inside its own flow. Your role is to invoke, proxy-confirm, return.
```

The sub-agent isolates the drafter's verbose work (PRD reading, classification questioning, nested sub-agent review loop) from the resolver's main context. The resolver sees one round-trip per item: input brief → output URL.

### URL weaving — close the loop

Once an item is filed, the resolver does three things with the URL:

1. **Replace temporary `// TODO(?)` markers** in code with `// TODO(#NNN)` referencing the filed issue. Same for `XCTSkip("Deferred to ?…")` — rewrite to `XCTSkip("Deferred to #NNN — <reason>")`. Don't push the iteration without this rewrite; markers without real numbers age into noise.
2. **Update the PR body's `## Follow-ups` section** with a list item per filed issue (use `gh pr edit --body-file` or a one-shot append). Add the section if it doesn't exist. Putting follow-up links in the body (not a comment) makes them durable: comments scroll, the body persists.
3. **Thread the URLs into §11's summary** under a "Follow-ups filed" bullet, separate from the "Procedural notes" bullet that holds the capture-in-PR-body items.

A filed follow-up isn't complete until all three weaves are done.

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
- **One or more BLOCKERs** — **stop**. Print every finding with severity, dimension, the affected issue number (for Epic / Story modes, dimension 5 findings name the sibling issue where the conflict lives), evidence, and recommended remediation. Then offer three named choices:

  1. **Revise via drafter** *(default)*. Invoke the sister skill `github-issue-drafter` via the `Skill` tool with arguments shaped like `revise #N — apply these audit findings: <evidence block>`. The drafter runs its own review loop on the proposed revision, shows the user a diff, files `gh issue edit` on approval, and returns. Then refetch the issue (`gh issue view <N> --comments --json …`) and run the audit again from pass 1. If the audit was on an Epic and dimension 5 found drift across multiple sibling Stories, route the drafter sequentially per affected issue — Epic body first if its contract is the source of truth, then each affected Story — so each drafter handoff is one issue at a time (mirrors how the user-led workshop session for Epic #119 proceeded: one `gh issue edit` per issue, in topological order). After all handoffs land, refetch every affected issue and re-audit.

  2. **Override and proceed.** The user states a one-sentence reason. Record the override in the state summary as `Audit override: <reason>`. Append the same line to the eventual PR body in step 9 under an `## Audit override` section so the override is visible to reviewers in the PR. Blockers don't disappear with this option — they become documented technical debt routed through PR review.

  3. **Abort.** The resolver stops. No worktree is created. No code work begins. Tell the user the audit's findings are the artifact of this run.

**The user-override skip.** For trivial issues (a one-line typo fix, a small bug fix where the user has confidence the body is fine), the audit is overhead. If the user replies `skip audit` (or `bypass audit`) at the gate prompt — or has said as much before this point — record `Audit skipped by user override` in the state summary, surface it in the step 11 summary so it lands in the PR body alongside any other overrides, and continue. The skip is durable for this run only; a re-invocation re-runs the audit from scratch.

**Cap-reached exit handling.** If three passes complete and findings remain (some types of drift are hard to fully express in body text — they may need a code-side decision before the body can be specified), surface the remaining findings to the user the same way as a blocker exit. The same three choices apply.

**Where the audit ends and step 5 begins.** A clean audit (or a recorded override / skip) is the precondition for everything after this point. Step 5 (existing-work check) and step 6 (doc grounding) inherit the post-audit issue body — step 6 in particular cites the doc sections that informed the approach, which is a different artifact from the audit's findings table. The work is sequential: audit catches drift, step 6 writes the doc-grounding statement for the PR body. Do not skip step 6 on the assumption that the audit's dimension-1 findings already cover doc grounding — they cover *tensions*, not *citations*.

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

1. **Capture the conflict set.**
   ```bash
   git diff --name-only --diff-filter=U > /tmp/conflict-files.txt
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

4. **Review and apply.** Show the user the whole proposal in one go (or grouped, for large sets). Ask for approval — wholesale ("apply all"), group-level ("apply rename group, skip schema group"), or rejection ("abort, I'll resolve manually"). On approval, **the skill** applies the proposed edits via the `Edit` tool — the sub-agent only proposes; the skill never lets the sub-agent write. On rejection, `git rebase --abort` or `git merge --abort` and stop.

5. **Continue.** After edits are applied, stage and continue: `git add <files>` then `git rebase --continue` (Path A) or `git commit` to finalise the merge commit (Path B). If a second conflict round fires (e.g., rebase replaying the next commit hits new conflicts), re-enter conflict handling with the new conflict set.

**Post-rectification.** The epic HEAD has changed; the prior baseline (if any) is no longer trusted. Run the project's full canonical suite in the worktree. On green, post a fresh `Baseline established` comment on the epic issue, recording the new `Epic branch SHA` (the post-rectification HEAD) and the new `Main SHA` (`git merge-base origin/main HEAD` — equals `origin/main`'s current tip for the rebase path; equals the `main` SHA that was merged in for the merge path). Without this, story-flow trust checks will detect the divergence and stop every subsequent story run. On red, handle per step 7's standard red-baseline procedure (detour-first or explicit override).

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
3. If the suite is green, draft an integration PR body (`epic/<N>-<slug>` → `main`) listing every story PR that landed in it, citing the epic's `## Goal` and DoD checklist, and including `Fixes #<epic-number>` so GitHub auto-closes the epic on merge. Then open the PR:
   ```bash
   gh pr create --repo <owner/repo> --base main --head epic/<N>-<slug> --title "Epic #<N>: <title>" --body-file integration-pr.md
   ```
4. Run the review loop (step 10) on the integration PR. After it merges, draft the body-tick diff (flip every `- [ ]` → `- [x]` in Stories and DoD, including stretch items marked as "deferred"), and a closing summary comment. Then run:
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

  **Carry forward step 4.5's audit overrides.** If step 4.5 was run and ended in an `Audit override: <reason>` (or `Audit skipped by user override`) recorded in the state summary, include a `## Audit override` section in the PR body quoting the override line verbatim. Reviewers see the override the same way they see scope decisions — visible and challengeable in PR review. If the audit ran clean (or was a comment-only flow where it didn't apply), omit this section.

In both cases, capture the PR number/URL — you'll need it for the review loop.

### 10. Run the review loop (PRs only)

**This step is mandatory for any issue resolved with code changes. Do not skip it, do not merge, and do not consider the work done until review approves the PR.**

After the PR is opened, the resolver **dispatches a single sub-agent** that drives the `review` skill through the loop until the exit condition holds. The sub-agent invokes `review`, applies the §10.4 classification rubric, addresses feedback, runs the §10.6 pre-push verification gate, commits, pushes, and re-iterates — entirely within its own execution scope. If the skill is re-invoked later (a human reviewer commented, the previous run was interrupted), step 5's reuse rule lands you back in the existing worktree and the sub-agent dispatch happens again — the sub-agent's prompt is told it may be picking up mid-flow.

**Why a sub-agent.** In-conversation loops have an unavoidable pull toward turn boundaries after long sub-tasks. The `review` invocation routinely runs 10–20 minutes; when it returns a verdict — even one that correctly names Addressable items per §10.4 — the model's next natural beat is "summarize what just happened and stop" rather than "loop back and address the items." Three rounds of tightening §10.4's rubric prose and adding Common-pitfall warnings did not fix this; the prose was correct and the model still stopped at the verdict (the `/tmp/review-loop.md` transcript on PR #416 is the exemplar — a review that explicitly cited the §10.4 rubric and recommended "address item 1" still landed at a turn boundary). Sub-agents are goal-directed by construction: they run to completion within their tool budget and don't share the interactive session's pull toward natural pauses. The dispatch boundary is the structural fix; the prose remains the contract the sub-agent works against.

**Spawn the sub-agent.** Use the `Agent` tool with `subagent_type: "general-purpose"`, `description: "Drive PR #<N> through the review loop"`, and the prompt template below. Inline every input placeholder at dispatch time. The sub-agent has full tool access — `Skill` for invoking `review`, `Bash` + `Read` + `Edit` + `Write` for code changes, `Agent` for nested test-selection and build delegations, `AskUserQuestion` for guard-rail decisions. **Do not invoke `review` directly from the main conversation** — the dispatch boundary is what prevents the failure mode this section exists to fix.

**Sub-agent prompt template** (substitute placeholders at dispatch time):

```
You are running the github-issue-resolver §10 review loop for PR #<N>. The
resolver has dispatched you because in-conversation loops do not reliably
exit on "approved with N Addressable items" — they stop at the turn
boundary instead. Your job is to drive this PR through the loop until the
exit condition holds, then return a structured summary.

Inputs:
- PR number: #<N>
- PR URL: <url>
- Repo: <owner/repo>
- Worktree path: <absolute path> — cwd for every tool call you make
- Originating issue: #<ISSUE>
- Parent epic: #<EPIC>  (or "none")
- Integration target branch: <branch>
- Doc-grounding statement (from §6, use when defending implementation
  choices in review responses): <statement>
- §4.5 audit overrides carried into the PR body (if any): <text or "none">
- Project test-config blocks (issue-resolver-fast-checks, issue-resolver-
  test-target): inline contents, or "read from COMMANDS.md / CLAUDE.md in
  the worktree".
- Resume hint: this loop may be picking up mid-flow (an earlier sub-agent
  run was interrupted, or a human reviewer commented between invocations).
  Re-read PR comments + reviews on the first iteration before classifying.

Read SKILL.md for §10.4 (the classification rubric), §10.6 (the pre-push
verification gate), the "Retry ladder for the verification gate" section,
and the "Follow-up issue tracking" section. Apply them as written.

Each iteration:

1. Re-read accumulated PR feedback. Use the gh commands documented in
   step 5 (`gh pr view --comments`, `gh api .../reviews`,
   `gh api .../comments`, `gh pr diff`). Include comments from human
   reviewers that arrived since the previous iteration.
2. Invoke the `review` skill via the Skill tool on PR #<N>.
3. Post `review`'s feedback as a PR comment:
   `gh pr comment <N> --body-file review-feedback.md`. Review feedback
   goes on the PR, not on the originating issue.
4. Classify every issue and suggestion per §10.4. The reviewer's own
   "approved" verdict line is NOT the exit condition — re-classify each
   listed item using the rubric's Addressable / Explicitly-deferred /
   Cheap-fix-override / Decision-required buckets. The cheap-fix override
   applies to ≤ ~20-line fixes on already-modified files even when the
   reviewer offered to defer.
5. Address every Addressable and Cheap-fix-override item. File every
   Explicitly-deferred item via the "Follow-up issue tracking" sub-agent
   protocol (urgency `file-now`, type per the reviewer's framing) and
   capture the returned URLs for the return summary.
6. Run the pre-push verification gate per §10.6 (static checks →
   test-selection sub-agent → test execution). The retry ladder per the
   "Retry ladder for the verification gate" section caps a single visit
   at 3 runs with a forced research breakpoint between cheap and deep
   fixes.
7. Commit. Push. Reply on the PR briefly describing what changed in
   response to which points of feedback. This per-iteration comment is
   how the user follows the loop on GitHub even though the parent
   conversation isn't streaming your tool calls.
8. Loop back to step 1.

Exit condition — both must hold:
- The `review` verdict is approved.
- After your own re-classification per §10.4, zero Addressable or
  Cheap-fix-override items remain.

Guard rails — invoke AskUserQuestion directly when any of these fire,
then use the user's answer in this same run and continue. Do not return
early on a guard-rail decision.

- Same-feedback-twice deadlock. You addressed a flagged item; the next
  iteration's review flags the same item with no acknowledgement of your
  fix. Don't iterate a third time on the same disagreement. Ask: continue
  with a different angle (and which angle), accept current state and exit
  with the item filed as a deferred follow-up, or abort the loop.
- Decision required. `review` flags an architectural choice, an API
  break, or a scope-change tradeoff. Don't guess. Present the decision
  to the user with the reviewer's framing and the candidate paths.
- 5-iteration cap. After the 5th iteration without an exit, ask whether
  to continue (and for how many more), accept current state, or abort.
  Don't loop silently past the cap.

Return ONLY this JSON (no prose around it):

{
  "status": "approved" | "capped" | "aborted",
  "iterations": <int>,
  "final_pushed_sha": "<sha>",
  "final_iteration_test_status": "green at <sha> (selected ...)"
    | "skipped (no tests selected — <rationale>)"
    | "red — <list of failing tests>",
  "items_addressed": [
    {"severity": "Medium" | "Low" | "Nitpick" | "...",
     "summary": "one-line description of what was changed"}
  ],
  "items_filed_as_followups": [
    {"url": "<filed issue URL>",
     "type": "bug" | "incomplete-feature" | "deferred-test"
       | "revise-existing",
     "summary": "one-line description"}
  ],
  "items_carried_as_procedural_notes": [
    {"summary": "one-line note for the resolver to capture in §11"}
  ],
  "user_decisions": [
    {"trigger": "same-feedback-twice" | "decision-required"
       | "5-iteration-cap",
     "prompt": "the question text the user saw",
     "answer": "the user's selected option / free-text"}
  ]
}
```

**Consume the return summary.** Parse the JSON the sub-agent returns and use it to drive §11 directly — do not re-derive any of these values from the PR or the worktree:

- `final_iteration_test_status` feeds §11's `Iteration test status` line verbatim.
- `items_filed_as_followups` feeds §11's *Follow-ups → Filed* bullets (one bullet per entry, with URL).
- `items_carried_as_procedural_notes` feeds §11's *Follow-ups → Procedural notes* bullets.
- Each entry in `user_decisions` adds one line to *Procedural notes* naming the trigger and the user's choice, so any guard rail that fired stays visible to the user reading §11.
- `status` and `final_pushed_sha` drive §11's outcome rubric. A non-empty `final_pushed_sha` means a PR was opened or updated, which fires the pr-evaluator handoff per the rubric in §11.

**Resume contract.** A re-invocation of the resolver while a PR is still open and under review (the existing step 5 reuse path) dispatches a *fresh* sub-agent — sub-agents don't persist state across runs. The prompt's "Resume hint" line tells the sub-agent it may be picking up mid-flow; it re-reads PR comments and reviews on the first iteration before classifying, which surfaces any human reviewer activity that landed between invocations. A run that exited via the guard-rail's "abort" path leaves the loop in a known stop-state; re-invoking re-dispatches the sub-agent, which sees the prior abort in the PR comment history and decides whether the original blocker is now resolvable.

#### §10.4 — Classification rubric

The sub-agent applies this rubric on every iteration. The rubric is documented at the section level so a reader can audit a sub-agent return against it and so the sub-agent prompt above can reference it by anchor.

"Approved" alone is not the exit condition — reviewers routinely approve with non-blocking suggestions (`Medium —`, `Low —`, `Nitpick —`, "Approved with minor fixes") that they still expect fixed before merge. Issues (defects the reviewer flagged) and suggestions (improvements the reviewer recommended) are gated identically; what matters is whether the item is **addressable on this PR**. Walk the review body and classify each item:

- **Addressable actionable (default).** Any concrete change the reviewer named falls here **unless** it satisfies one of the explicit deferral triggers below. Severity labels (`Medium —`, `Low —`, `Nitpick —`) and reviewer politeness ("could be a fast-follow", "not blocking if you prefer", "consider for a future PR", "deferrable", "informational only") do **not** by themselves move an item out of this bucket. The reviewer flagged it; address it.
- **Explicitly deferred** — reserved for items meeting **at least one** of these objective triggers. The reviewer's prose is evidence; the sub-agent re-checks. Soft framing alone never qualifies:
  - **Concrete routing target.** The reviewer cites a specific issue/PR number that already exists or is filed as part of this resolution (`#N`, "tracked in #M", "filed as follow-up below"). A vague "future PR" or "a separate change" without a number is *not* a concrete target.
  - **Structural blocker.** The fix can't ship in this PR — depends on a sibling story not yet merged; requires an API break whose consumers are outside this PR's scope; requires a schema migration the PR's scope excludes.
  - **PRD / scope explicit exclusion.** The item is outside the issue's stated scope as documented in the issue body, the parent epic's DoD, `docs/prd.md`, `docs/architecture.md`, `docs/constitution.md`, or `CLAUDE.md`. Soft scope arguments ("keeps the PR scope pure") don't qualify — the exclusion must be citable.
- **Cheap-fix override.** If an item meets a deferral trigger above but the fix is **≤ ~20 lines of edits on files this PR already modifies** and doesn't require new tests, new files in the diff, or scope expansion — address it in-loop anyway. Deferral exists to keep PR scope tight; trivial doc, comment, identifier, or formatting fixes aren't scope creep. The override does *not* apply to code changes that pull new files into the diff or that need a fresh test.
- **Decision required** — the suggestion touches architecture, breaks an API, or carries a tradeoff the user should weigh in on. Fire the sub-agent's "Decision required" guard rail (see the prompt above): present the choice via `AskUserQuestion`, use the user's answer, continue.

Worked examples (verbatim review snippets the rubric has to handle correctly — these come from the failure mode this rubric was tightened to fix):

- **Example A — soft defer is Addressable.** Review text: *"Defer to story #403 if you prefer to keep this PR scope-pure — docs-first ambiguity is fine and the mapping is obvious to a reader who has the enum in hand."* → **Addressable**. The reviewer offered deferral as an option ("if you prefer"), did not file a concrete tracking issue for the fix itself, and the item is a 1-line doc clarification on a file the PR already changes.
- **Example B — concrete routing is deferred.** Review text: *"Variant-B's mixed-mode UX is design work that belongs in story #403's UX brief — filing as follow-up issue #N."* → **Explicitly deferred**. Concrete tracking issue (`#N`) plus a citable structural rationale (the parent epic's story breakdown).
- **Example C — "future doc-amend" triggers Cheap-fix override.** Review text: *"The single paragraph packs four rules … a future doc-amend (or this PR if you'd like) could break it into bullets."* → **Cheap-fix override**. "Future doc-amend" matches deferral language, but the fix is ~5 lines on a file the PR already modifies — address in-loop.

Exit the loop only when **both** are true: (a) the verdict is approved, **and** (b) zero Addressable or Cheap-fix-override items remain after the sub-agent's re-classification. The reviewer's own summary ("zero blocking", "all deferrable", "nothing addressable", "fast-follow only") does **not** make (b) true on its own — re-classify every listed item against the rubric above before exiting. The reviewer can frame items politely; the sub-agent decides whether they're addressable on this PR. If the re-classification finds any Addressable or Cheap-fix-override item, the loop continues — even when the reviewer's verdict line says "approved with zero blocking". A verdict like "approved with minor fixes" or "approved, with these nits" is the loop telling you it isn't done yet, not a green light to exit.

When you do exit, file each explicitly-deferred item as a follow-up issue per "Follow-up issue tracking" above — urgency `file-now`, type chosen per the reviewer's framing (`bug` if the deferred item is a real defect, `incomplete-feature` if it's a half-built capability the reviewer flagged, `deferred-test` if it's a test the reviewer accepted should be skipped). The filed URLs land in this iteration's PR body `## Follow-ups` section before push and in the sub-agent's `items_filed_as_followups` return field. Procedural-only items (informational caveats with no tracked work) are not filed — emit them in `items_carried_as_procedural_notes` for §11's summary.

The full canonical suite will run once at PR-readiness time inside `github-pr-evaluator` — there's no in-loop final gate here.

#### §10.6 — Pre-push verification gate

Run inside the sub-agent's loop on every iteration that produced code changes (per the sub-agent prompt's step 6). Same three-step gate as §8, per "Test selection during iteration" above:

1. **Static checks** — run the `<!-- issue-resolver-fast-checks -->` block inline, fail-fast in declaration order. Outputs are small (lints, codegen, layer-import boundary checks); no need to delegate.
2. **Test selection** — spawn an `Explore` sub-agent with the prompt template from "Test-selection sub-agent" above. Substitute the worktree path, integration target, and the project's `<!-- issue-resolver-test-target -->` block. The sub-agent reads the diff, lists each declared target's directory, applies the heuristics, and returns two sections: `COMMAND:` (a ready-to-run shell command, or `(none)`) and `RATIONALE:` (one or two sentences). Capture the rationale in the iteration's PR-status comment so the user can audit the selection.
3. **Test execution** — if `COMMAND:` is `(none)`, skip execution and continue. Otherwise, run the command. If it begins with `xcodebuild` (or invokes a wrapper that runs `xcodebuild`), delegate to `apple-platform-build-tools:builder`; otherwise run inline.

If run 1 is green, proceed to the sub-agent's step 7 (commit and push). If run 1 is red, follow the ladder in "Retry ladder for the verification gate" above — at most 3 runs this visit, with a forced research breakpoint between cheap and deep fixes, escalating to the user via the sub-agent's `AskUserQuestion` if the deep fix also fails. (Each entry to §10.6 starts a fresh ladder; the §10 5-iteration outer-loop cap governs how many times this whole gate can repeat.) If `COMMAND:` was `(none)` (e.g., docs-only iteration), there's nothing to be green or red — `github-pr-evaluator`'s full canonical run will exercise the change at PR-readiness time. Don't fall back to "run zero tests" when the sub-agent's heuristics could have widened — re-spawn the sub-agent if the rationale looks wrong.

### 11. Summarise for the user

**Outcome rubric — does this resolution end with a pr-evaluator handoff?**

Classify the run's outcome before writing the summary; it determines whether the closing **Next step** line in this section fires.

| Outcome | Closing pr-evaluator handoff |
|---|---|
| Story / bug-fix / refactor PR opened or updated (§8 or §10 paths reached push) | **Emit.** This is the default code-change outcome and the case the handoff exists for. |
| Epic-integration PR opened or updated (epic-target run finishing an epic) | **Emit, explicitly.** The integration PR carries more merge risk than any single story PR — pr-evaluator runs the full canonical suite, evaluates the change against the epic's `## Definition of done`, and recommends a merge strategy. The handoff matters more here, not less. |
| Comment-only answer (question, clarification, decision capture; no diff, no PR) | **Skip.** There is no PR for pr-evaluator to evaluate; mentioning it would confuse the user. |
| Triage / classification only (relabel, retitle, link to a duplicate; no PR) | **Skip.** Same reason. |
| Abandoned / declined / stale-issue close (user opted out of opening a PR) | **Skip.** Same reason. |

If the run produced *both* a comment and a PR (e.g., posted a "starting work" comment then opened the PR), treat it as a PR outcome — the PR is what pr-evaluator acts on.

**Before writing the summary, run the end-of-§10 follow-up checkpoint.** Per "Follow-up issue tracking" above, present the registry's `file-at-checkpoint` items (planning-time and implementation-time discoveries that weren't filed in-flight) to the user for batch approval, file via the sub-agent protocol, weave URLs into TODO markers and the PR body's `## Follow-ups` section. This is the resolution's last chance to convert trackable observations into filed issues before §11 closes things out; observations that aren't filed here become PR-body lines that age into noise.

The summary MUST include a clearly-labeled **Iteration test status** line that names the result of the most recent pre-push verification gate (§8 on a clean first-pass approval, §10.6 on the last iteration when the review loop ran): green, skipped (no tests selected — name the rationale), or red (a list of failing tests with their failure mode). When the run went through §10's review loop, **read this from the sub-agent return's `final_iteration_test_status` field** verbatim — do not re-derive it from the worktree or the PR. If anything is red at this point, fix it before pushing — don't bury it in follow-up notes. The skill does not run a final canonical-suite gate at this step; the comprehensive run happens once at PR-readiness time inside `github-pr-evaluator`. State this explicitly in the summary so the user knows what's still ahead: e.g. *"Iteration test status: green at <SHA> (selected ProposalServiceTests, run at §8 pre-push). The full unit + UI suite will run in github-pr-evaluator before merge."*

Then: a short summary of what you did, what you posted (if anything), and a **Follow-ups** section split into two bullets — *Filed* (URLs of issues filed via the protocol, both `file-now` and `file-at-checkpoint`) and *Procedural notes* (informational items captured in the PR body, not filed as issues per the filing-vs-capturing criterion). When the run went through §10's review loop, the sub-agent return populates both bullets directly: `items_filed_as_followups` provides the *Filed* entries (one bullet per URL), `items_carried_as_procedural_notes` provides the *Procedural notes* entries, and each `user_decisions` entry adds one additional *Procedural notes* line naming the guard rail that fired and the user's choice (so any same-feedback-twice, decision-required, or 5-iteration-cap intervention stays visible). If you created or reused a worktree, include its path and the manual cleanup sequence. The `github-pr-evaluator` skill runs both phases automatically after a green merge (its §14); the manual form below is for runs that don't go through the evaluator (declined merge, manual close, abandoned issue):

1. From inside the worktree, run the project's worktree-teardown commands (see "Worktree setup & teardown commands"). If `COMMANDS.md` declares no `<!-- worktree-teardown -->` block, skip this step.
2. From the main checkout, run `git worktree remove .worktrees/<branch-name>`.

Don't run cleanup yourself: a worktree may hold unpushed work, and teardown may release resources still useful for debugging.

If the resolved issue was a **story** under an open epic, include two additional reminders:
- The parent epic's `## Stories` checkbox for this story is still `- [ ]` — it won't auto-tick on PR merge. A future epic-targeted run (or the user manually) needs to sync it.
- The change has landed on the epic integration branch, not `main`. It will reach `main` via the integration PR for epic #N once all stories under that epic are complete.

**Next step (PR outcomes only — per the rubric above).** Append the line below as the final entry in the §11 summary, after all other content. Skip it entirely for comment-only, triage-only, and abandoned-issue outcomes — those have no PR for pr-evaluator to evaluate.

> **Next step.** Run the `github-pr-evaluator` skill against PR #<N> (<URL>) to evaluate issue-fit against the originating issue (#<ISSUE>) and recommend the right merge strategy. The resolver leaves the PR reviewed-by-`/review` for code quality and verified by targeted tests at §8/§10.6, but the canonical-suite run, issue-fit evaluation, and merge-strategy selection happen inside `github-pr-evaluator` — that's the gate between "reviewed" and "merged cleanly".

Substitute `<N>`, `<URL>`, and `<ISSUE>` with the actual PR number, URL, and originating issue number from this run. For an epic-integration PR, `<ISSUE>` is the epic issue number; pr-evaluator handles both story and integration PRs. If the PR closes multiple issues (e.g., `Fixes #A, Closes #B`), substitute the issue number the resolver was invoked with — that's the issue whose intent the resolver tracked through implementation.

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
- **Don't iterate small fixes when failures are sticky.** Two §8 (or §10.6) runs with the same failing test means the underlying understanding is wrong, not the patch. Take the research breakpoint per "Retry ladder for the verification gate" — read the full failure output, capture `app.debugDescription` for UI tests, spawn an `Explore` sub-agent for structural read of the failure. Continuing to tweak burns 10–20 minutes per attempt with no information gain, and the same loop bounded by the build subagent's pitfall above applies one layer up: the *parent* model running tweak → re-run → tweak → re-run is the same anti-pattern, just at a different layer.
- **Don't `rm` snapshot goldens to force regeneration.** A failing snapshot test means a pixel-level visual change that needs human eyes — the whole point of snapshot tests is to surface those. Surface the diff to the user and ask before deleting. Auto-regenerating goldens silently accepts visual regressions and defeats the test category's purpose. If the user confirms the visual change is intended, *then* delete and regenerate; record the confirmation in the PR body so reviewers can audit.
- **§8 is the pre-push gate, not the dev inner loop.** Iterate at unit-test granularity locally first — the project's wrapper supports `-only-testing FoodJournalTests/<SuiteName>` and Swift Testing suites typically run in well under a minute. Reserve the §8 invocation (which legitimately includes UI tests via the test-selection sub-agent's widening rules) for the once-before-push integration check. Treating every code change as "make change → §8 → react" turns a 30-second feedback cycle into a 20-minute one and is the most direct cause of the small-fix spiral.
- **Don't read only the PR diff.** PR comments and code review threads (especially line-level review comments, which require a separate API call) are where decisions actually got made. Skipping them leads to redoing rejected work or contradicting settled directions.
- **Don't trust the issue title alone.** The title often reflects the original report; the actual problem may have shifted in the comments.
- **Don't re-litigate decided questions.** If a maintainer said "let's go with approach B" three comments ago, go with approach B.
- **Don't open a PR for a question.** Some issues are resolved by an answer, not a code change.
- **Don't skip the review loop.** For any PR, `review` must approve before the work is considered done. No exceptions, no "this change is too small to review."
- **Don't exit the loop just because the verdict says "approved".** Reviews routinely approve with `Medium`, `Low`, or `Nitpick` items — issues *and* suggestions — that the reviewer still expects fixed (e.g., "Approved with minor fixes"). Per §10.4, exit only when the verdict is approved **and** zero Addressable or Cheap-fix-override items remain after the sub-agent's own re-classification. Items the reviewer routes elsewhere with a **concrete tracking target** (filed as #N, depends on un-landed sibling, citable PRD/scope exclusion) are deferred and filed as follow-ups. Soft politeness alone ("could be fast-follow", "not blocking", "deferrable", "informational only", "future PR", "consider for a future change") is **not** sufficient — the sub-agent re-classifies per §10.4's rubric before exiting, and the **default for any concretely-named change is Addressable**. The Cheap-fix override addresses ≤ ~20-line fixes on already-modified files even when the reviewer defers them. The §10 sub-agent boundary now structurally enforces this — there is no main-conversation step where the model could "approve and stop"; the sub-agent runs to completion against its own exit condition — but the rubric still governs the sub-agent's classification, so the hazard this bullet exists for hasn't gone away, it just moved one layer in.
- **Don't drive the review loop in the main conversation.** §10 dispatches a `general-purpose` sub-agent specifically because in-conversation loops have an unavoidable pull toward turn boundaries after long sub-tasks. The transcript at `/tmp/review-loop.md` (PR #416) is the exemplar: `review` correctly classified one Medium item as Addressable per §10.4 and even printed a "Recommended next step: address item 1" line, and the model still stopped at that turn boundary rather than looping back. The fix is structural, not prose — invoking `review` directly from the main conversation and trying to loop yourself reintroduces exactly the failure mode the sub-agent boundary exists to prevent. Always dispatch the sub-agent per the §10 "Spawn the sub-agent" instruction; never inline the loop's steps in the resolver's main flow.
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
