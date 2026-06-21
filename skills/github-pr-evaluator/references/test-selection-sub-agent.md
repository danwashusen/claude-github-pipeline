# Test-selection sub-agent

The §5.5.2 pre-merge health gate spawns a read-only `Explore` sub-agent to pick which test suites to run for the PR's cumulative diff. Reasoning happens entirely inside the sub-agent so the main conversation never sees the diff hunks, the test directory listings, or the grep output — only the sub-agent's two-section verdict.

## Prompt template

Substitute the placeholders (worktree path, PR base branch, HEAD SHA, `pr_type`, the matched escalation label, and the project's `<!-- pr-evaluator-test-target -->` block contents) at call time.

```
You are selecting which test suites to run for a Claude Code github-pr-evaluator
gate against an open PR. Your output drives the next test command; the rest of the
workflow does not see your reasoning, so be explicit in your rationale.

Inputs:
- Worktree path: <absolute path to .worktrees/<branch>>
- PR base branch (diff base): <baseRefName>
- PR HEAD SHA: <headRefOid>
- PR type: <regular | story | epic-integration>
- Escalation label matched (if any): <label name, or empty>
- Test-target config (verbatim from the project's COMMANDS.md / CLAUDE.md):
  <contents of the <!-- pr-evaluator-test-target --> block>

Escalation rules — apply in this order, BEFORE running heuristics:

1. If PR type is `epic-integration` → return the full-suite command from the
   config's `full-suite-command` line. The whole point of an epic-integration
   PR is verifying that all child stories integrate cleanly against `main` —
   targeted selection on the merged diff would defeat the purpose of this gate.
2. If an escalation label matched → return the full-suite command. The user has
   explicitly asked for the canonical run on this PR.

Otherwise, apply the heuristics below.

Steps for the heuristic path:

1. Compute the diff: `git diff origin/<base>...HEAD` from the worktree (where
   <base> is the PR base branch from the inputs above). Read both file paths
   and hunk contents — don't decide based on paths alone. If empty, return
   COMMAND: (none) and a one-line rationale.
2. List each declared target's directory: `ls <target>/` for each target.
3. Apply these heuristics in order, building a union of suite identifiers
   across all declared targets:
   a. Direct filename mapping per the target's `naming` rule.
   b. Test files modified directly → include their suite.
   c. Symbol references — identify symbols introduced, modified, removed, or
      renamed in the diff (types, functions, accessibility identifiers, error
      cases, string-catalog keys). For renames, search both old and new names.
      `grep -l` across each target's directory; include any test file that
      mentions any matching symbol.
   d. `@testable import` tracking — a test file that imports a sub-module
      touched by the diff is a candidate even if no explicit symbol matches.
4. Apply per-target widening rules from the config:
   - Helpers-fallback triggers when a test-side helper changes.
   - Broad-change-fallback triggers when the diff changes a widely-referenced
     type (>5 test files mention it), a persistence-model schema, generated
     config, or any change you cannot narrow with confidence.
   - If a target declares a fallback as `none`, do not widen for that target.
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
6. Pure-docs / comment-only diffs → COMMAND: (none).

Output exactly two sections, in this order, with these literal headers:

COMMAND:
<single shell command using the wrapper from the config plus -only-testing
flags for each selected suite, OR the full-suite-command from the config when
an escalation rule fired, OR one of the per-target fallback commands, OR the
literal string `(none)` if zero suites selected>

RATIONALE:
<one or two sentences. If an escalation rule fired, name it explicitly:
"Escalation: epic-integration PR → full-suite-command." or "Escalation: PR
label `full-suite-required` matched → full-suite-command." Otherwise name
the selected suites and the heuristic that produced them.>
```
