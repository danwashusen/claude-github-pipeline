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
      renamed in the diff (types, functions, identifiers, error
      cases, i18n/string keys). For renames, search both old and new names.
      `grep -l` across each target's directory; include any test file that
      mentions any matching symbol.
   d. Test-time import tracking — a test file that imports a sub-module
      touched by the diff is a candidate even if no explicit symbol matches (a Swift
      `@testable import`, a Ruby `require`/autoload).
4. Apply per-target widening rules from the config:
   - Helpers-fallback triggers when a test-side helper changes.
   - Broad-change-fallback triggers when the diff changes a widely-referenced
     type (>5 test files mention it), a persistence-model schema, generated
     config, or any change you cannot narrow with confidence.
   - If a target declares a fallback as `none`, do not widen for that target.
5. Integration blast-radius exploration. Name/symbol proximity is fine for unit
   tests but a poor proxy for *integration tests* (UI, system, feature, or
   request tests), which exercise shared application surface that a symbol-grep
   won't connect back to the diff. A small change to a **high-fanout
   integration-surface file** — one many parts of the app route through — can
   break integration tests that never mention the changed symbol, and step 3's
   symbol-grep won't catch it. Before finalising the integration-test set, do a
   focused exploration pass:

   a. For each modified source file, decide whether it is a high-fanout
      integration-surface file: one that a large share of the app's integration
      tests transit, directly or indirectly. What that looks like depends on the
      stack — infer it from the wrapper command and the source layout:
      - **SwiftUI / XCUITest** — a view (declares `: View`, or matches the
        project's view-naming convention, e.g. `*View.swift`); the app entry
        point (`@main`); a top-level navigation container or a view that gates
        the rest of the UI behind a sheet.
      - **Rails / system specs** — a shared layout (`app/views/layouts/*`),
        `ApplicationController` or a broadly-applied `before_action`, a shared
        partial / concern / helper, or routing (`config/routes.rb`).

   b. For each such file, trace its consumers: `grep -rln "<TypeName>("` (or the
      stack's equivalent reference — a rendered partial, a route helper) across
      the app tree, excluding tests. Build a small list of "files that use this
      one." If any consumer has integration tests (by symbol grep or name
      proximity), those tests are candidates regardless of whether they
      reference the diff directly.

   c. Treat the change as broad integration impact — and widen the integration
      selection to the per-target broad-change-fallback (or, if that is `none`,
      to the union of every integration-test file that transits the affected
      surface) — when the diff touches a root-reachable, high-fanout surface:

      - **SwiftUI / XCUITest** — the diff modifies the app entry point (`@main`)
        or the top-level body composition reachable from it; modifies a View
        instantiated in another View's `body` that is reached by existing UI
        tests; adds/removes/modifies a presentation modifier on a root-reachable
        View (`.sheet`, `.fullScreenCover`, `.alert`, `.confirmationDialog`,
        `.popover`, `.overlay`) — these insert global UI surface that intercepts
        unrelated tests; or changes `@Environment` / `.environment(...)`
        injection at or near the app root, or launch-environment / initial-state
        gating logic.
      - **Rails / system specs** — the diff modifies the application layout or a
        layout most pages render; changes `ApplicationController` or a
        broadly-applied `before_action` / authentication filter; changes routing
        many specs traverse; or modifies a partial / concern rendered across many
        views. These sit on the path most system/feature specs walk.

   d. When uncertain about a file's blast radius, widen rather than narrow. The
      targeted-selection win on integration tests is bounded (they're already
      expensive per case); the cost of merging a root-surface regression
      masquerading as a leaf change is the entire next baseline, plus the
      diagnostic cost. The asymmetry strongly favours widening.

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
