# Retry ladder for the verification gate

The pre-push verification gate (§8 before the first push, §10.6 after each round of review feedback) treats "tests must be green before push" as a goal, not a license to retry indefinitely. Without a cap, a complex UI-test failure can spiral into a sequence of small fixes — tweak, re-run a 10–20 minute UI suite, tweak, re-run, repeat — that burns hours of wall-clock time and produces nothing the review loop couldn't have surfaced in the first place. The cost compounds because each iteration re-pays the cold-build and simulator-boot overhead, and small fixes on a shallow read of a failure usually don't help anyway.

The ladder below caps a single visit to the gate at **3 test runs total** before escalation, and forces a research breakpoint between cheap fixes and any deep fix. It applies identically at §8 and §10.6.

## The ladder

| Run | Trigger | Allowed action after |
|---|---|---|
| 1 (initial) | First invocation of the gate this visit | If green → §9 (or §10.7 from §10.6). If red → **run the unrelated-failure triage first** ("Triage unrelated failures" below); then 1 cheap fix on any *remaining* diff-transiting failure. |
| 2 | After cheap fix #1 | If green → §9. If red AND the failing-test set strictly changed (some original failures resolved) → 1 more cheap fix allowed. If red AND the failing-test set is sticky (same set or grew) → **research breakpoint, mandatory**, even though only 2 runs have happened. |
| 3 (deep) | After research-informed fix | If green → §9. If red → **escalate to user** per "Escalation" below. No further runs this visit. |

A "cheap fix" is a small, narrowly-targeted edit (typo, missing accessibilityIdentifier, off-by-one, obvious binding mistake) on the immediate failure mode. A "deep fix" is a structural change informed by the research breakpoint — restructuring a gesture, lifting state, changing a focus model, etc.

## Triage unrelated failures: check for a known issue before spending the fix budget

A red gate run does not always mean *your change* broke something. Targeted selection deliberately widens beyond the diff — the UI blast-radius rules and the broad-change-fallback pull in tests that don't transit your edit at all — and those tests can be red for reasons that predate this branch: a flaky UI interaction, an environmental timing bug, a genuinely separate defect someone has already filed. The expensive way to find that out is to revert your diff and re-run; it works, but it re-pays the cold-build and simulator-boot cost to answer a question GitHub may already answer for free. So triage cheaply first, before the ladder spends a single fix attempt.

**When the triage fires.** On the *first* red run only. Partition the failing tests using the selection sub-agent's own rationale from this gate:

- **Diff-transiting failures** — selected by a direct filename/symbol match (heuristics 3a–3d): the test exercises code your diff touched. A known issue does *not* excuse these — your change could break the same path the issue describes in a new way. Hand them straight to the ladder.
- **Seemingly-unrelated failures** — pulled in only by widening (UI blast-radius rule 5, broad-change-fallback) and referencing no symbol or file in your diff. These, and only these, are the triage candidates.

**The check.** For each seemingly-unrelated failing test, search the repo's open issues for the test and its symptom — one `gh` call, no revert:

```bash
gh issue list --repo <owner/repo> --state open \
  --search "<failing test method> OR <failing suite name> OR <distinctive assertion keyword>" \
  --json number,title,url
```

Read the candidate titles (and the body of any plausible hit) and decide whether one genuinely describes *this* failure — same test, same symptom — not a keyword collision.

**On a confirmed match.** Treat the failure as a known pre-existing red: exclude it from this gate's pass/fail, record `Known pre-existing failure: <Suite>/<test> — tracked by #<NNN>` in the state summary, and add it to the PR body's `## Known failures` section with the issue link. Do **not** file a duplicate follow-up (the matched issue is the tracker), do **not** spend a cheap fix on it, and do **not** revert to confirm — the open issue plus the absent diff-relationship is sufficient evidence. If every red test this run matched a known issue, the gate passes for your diff → proceed to §9 (or §10.7). If diff-transiting failures remain, run the ladder for those only.

**On no match.** The seemingly-unrelated failure has no tracker, so the shortcut doesn't apply — fall back to the ladder's normal path. The research breakpoint may revert the diff / re-run without your changes to settle whether the failure is pre-existing (still valid — just no longer the *first* thing tried). If the revert confirms it is pre-existing and untracked, that's a defer-by-retry follow-up: file it per "Follow-up issue tracking" (urgency `file-now`, type `bug` or `deferred-test`) so the next run's triage finds it.

## The adaptive cheap-fix rule

Whether the second cheap fix is allowed depends on whether the first cheap fix made *any* of the originally-failing tests pass. Compare the failing-test sets across runs:

- **Strictly changed** (e.g., run 1 fails {A, B}; run 2 fails {B, C}): at least one originally-failing test newly passed. The first fix worked on something; the new failure is plausibly a separately-trivial issue. One more cheap fix is allowed.
- **Sticky** (run 2 fails {A, B} again, or {A, B, C}): no originally-failing test resolved. The model's read of the failure is wrong. Force the research breakpoint immediately.

This rule exists because the small-fix spiral's signature is exactly *sticky failures with shrinking patches*: each iteration tweaks the same code path on the same wrong hypothesis. Detecting non-progress at run 2 cuts off the spiral before it doubles.

## Test selection on retry

Run 1 and run 3 use the test-selection sub-agent's full verdict on the cumulative diff. Run 2 does **not** — it skips the sub-agent and re-runs only the tests that failed in run 1.

| Run | Selection mechanism |
|---|---|
| 1 | Full sub-agent verdict on cumulative diff (per "Test selection during iteration" in SKILL.md). |
| 2 | **Skip the sub-agent.** Build the command directly: `<wrapper> test -only-testing <Suite>/<TestMethod>` for each test that failed in run 1, joined into a single invocation. Use the failing tests' fully-qualified identifiers as reported by the previous run. |
| 3 | Full sub-agent verdict on cumulative diff. The deep fix may have changed the blast radius (lifted state, restructured a view tree, modified a root-reachable view), so the sub-agent's heuristics — especially the UI blast-radius rules at step 5 of the prompt template — need a fresh look. |

The narrowing at run 2 is a deliberate departure from "trust the sub-agent on every gate visit." The justification: the sub-agent's job is selecting tests *given a diff*; on a cheap-fix retry the only new information is which specific tests failed, and the parent already has that. Re-running the sub-agent would either re-derive the same broad selection (no win) or narrow incorrectly without seeing the failure list (worse). Bypassing it on run 2 is faster and more correct for the cheap-fix case.

A previously-passing test that the cheap fix breaks will not be caught at run 2 — it will surface at run 3 (where the sub-agent's full verdict runs again on the now-larger diff) or, failing that, in `github-pr-evaluator`'s full canonical run at PR-readiness time. That gap is acceptable: the cheap fix is by definition small, and the safety net at pr-evaluator is exactly the reason this skill runs targeted tests rather than the canonical suite. The alternative — re-running the broad selection on every retry — is what produced the small-fix spiral this ladder exists to prevent.

## Research breakpoint requirements

When the ladder forces a research breakpoint (run 2 was sticky, or run 2 was a second cheap fix that also failed), the next step is **not** a code change. It's a forced, structured information-gathering pass. The point is to replace the model's shallow read of the failure — which has now demonstrably failed twice — with a real understanding before any deep fix is attempted.

During the breakpoint:

1. **Read each failing test's full output** — the assertion message, the stack frame, and the relevant simulator log lines. Not just the one-line summary the test runner prints.
2. **For UI tests, capture `app.debugDescription`** from inside the failing test and read the dump. CLAUDE.md mandates this on element-lookup timeouts; restate the mandate here. The accessibility tree usually points at the cause directly (collapsed parent, hidden element, identifier dropped, glass surface absorbing children).
3. **Spawn one `Explore` sub-agent** with: the failing test files, the source they exercise, the recent diff (`git diff <integration-target>...HEAD`). Have it return three things, in order:
   - What is *actually* failing (not what the test name suggests, not what the assertion line says — what's happening in the code paths the test transits)
   - What code paths the failing tests transit, including any indirection (gesture → focus → state → view re-render)
   - What structural change is implied by (a) and (b) — explicitly *not* a tweak

No code edits during the breakpoint. The deep fix happens only after the sub-agent returns and the model has internalised its findings.

## Escalation

When run 3 (the research-informed deep fix) is also red, stop. Do not run §8/§10.6 a fourth time. Surface the failure analysis, then ask the user to choose among three equally-weighted paths forward — no default — via `AskUserQuestion` (`header: "Tests red"`, options **Push with reds** / **Defer the tests** / **Restructure**, each described by the matching path below):

1. **Push with documented reds.** Open the PR (or push to the existing branch) with a `## Known failures` section in the PR body listing each red test, the reproduction signal, and what was tried. Let `review` decide whether any of the reds are blocking. Best when the failures look like CI/timing flakiness or genuinely separate edge cases that don't block the headline change.
2. **Defer the failing tests with linked issues.** File one follow-up issue per failure (or one umbrella issue if the failures share a root cause) via the sub-agent protocol in "Follow-up issue tracking" — urgency `file-now`, type `deferred-test`. The filed URLs become `// TODO(#NNN)` markers and `XCTSkip("Deferred to #NNN — <reason>")` reasons before push. Push the rest green. Best when the failure is a real structural problem that needs more design than fits this PR.
3. **Restructure.** Abandon the current approach. Return to a planning conversation, with the research-breakpoint findings as input, and propose a different shape. Best when the deep fix revealed that the original approach itself was wrong (e.g., a gesture that fundamentally fights the parent's gesture system).

The summary at §11 records which path was taken and why. The user picks; the skill does not pick a default. When you reach this gate from §8 you are the main loop — ask via `AskUserQuestion` directly. When you reach it from §10.6 you are inside the review sub-agent, where `AskUserQuestion` is unavailable — return `status: "needs_decision"` with `kind: "verification_failure"` and these three options instead, and the main loop asks.

## What the ladder is and isn't

It **is** a cap on retries within a single visit to the gate. Each entry to §8 starts a fresh ladder (run 1 again). Each entry to §10.6 (one per review-loop iteration) starts a fresh ladder. The §10 sub-agent's 5-iteration outer-loop cap governs how many times `review` can flag changes; this ladder governs how many times the model may re-run tests within one of those iterations.

It **isn't** a license to give up after one failure. Run 1 failing is normal — that's why the gate exists. The ladder activates when the model is about to enter a small-fix spiral, not on every red run.
