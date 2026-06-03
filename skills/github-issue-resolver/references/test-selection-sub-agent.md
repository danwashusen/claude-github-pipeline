# Test-selection sub-agent

The §8 and §10.6 pre-push verification gates each spawn a read-only `Explore` agent to pick which test suites to run for the cumulative diff. Reasoning happens entirely inside the sub-agent so the main conversation never sees the diff hunks, the test directory listings, or the grep output — only the sub-agent's two-section verdict.

## Prompt template

Substitute the placeholders (`<absolute path to .worktrees/<branch>>`, `<integration-target>`, and the project's `<!-- issue-resolver-test-target -->` block contents) at call time.

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
