# resolver — v1 functional spec (baseline)

> Source: `skills/github-issue-resolver/SKILL.md` (1169 lines) + references: `common-pitfalls.md`,
> `dod-projection-rule.md`, `epic-flow.md`, `follow-up-tracking.md`, `handoff-renderings.md`,
> `issue-audit-prompt.md`, `retry-ladder.md`, `review-loop-sub-agent.md`, `state-distiller-prompt.md`,
> `test-selection-sub-agent.md`.
> Captures v1 behavior as the parity baseline for [implementation.md](../implementation.md) S-cutover.
> v1 skill name: `github-issue-resolver`; v2 name: `resolver`.

## Overview

The resolver is the **implementation stage** of the pipeline: it takes a filed, planned issue and
executes it end-to-end — reading the issue and its full thread, auditing the issue body for
fitness-to-implement, consuming a verified `github-issue-planner` plan as the binding approach,
doing the code (or comment-only) work in a git worktree, looping with the `review` skill until
approved, and reporting back to GitHub. Session shape: one Claude Code session per issue-resolution
attempt (fresh session on every re-entry — no state survives between runs except what's persisted
to GitHub). Inputs: an issue number/URL, the issue's thread, an optional `<!-- implementation-plan:v1
-->` comment, project config marker blocks, and (for Epics/Stories) the epic branch and sibling
issues. Outputs: either a PR (draft or ready) with code changes plus a `## Handoff`, or a posted
comment plus a terminal `## Handoff` — no code path exists without a PR.

## Artifacts written

| Artifact | Marker / schema | Where it lives | Section + heading order | Trigger |
|---|---|---|---|---|
| DoD checkbox projection | `- [x] <text> (closed by phase <N>, commit <short-sha>)` / `(closed by phase <N>, operator action <ISO-date>)` / `(closed by commit <short-sha>)` — see `dod-projection-rule.md:21-27` | issue body, `## Definition of done` bullets | top-level bullets, 1-based index | On every push that ships a phase (§9, both existing-PR-continuation and fresh-PR-open paths) and on re-entry reconciliation (§4.7) |
| `## Phase tracker` | plain Markdown checklist, e.g. `- [x] Phase 1 — substrate (commit abc1234)` (SKILL.md:900-906) | PR body | own section, added at fresh-PR-open for multi-phase issues | Fresh PR open (§9) when §4.7 identified multi-phase; updated via `gh pr edit` on every subsequent phase push |
| `## Handoff` | schema in `_shared/handoff-format.md` | session's final chat output (not persisted to GitHub) | `Issue:`/`Story:`+`Epic:` → `PR:` → `Next:` → `Why:` (omission rules per shared doc) | End of every clean run (§12), one of 9 renderings in `references/handoff-renderings.md` (SKILL.md:1017 and that file's own intro both self-describe this as "seven rendering shapes" — a source miscount; see "Known bugs / gaps") |
| Closing keyword (standard/story fresh PR) | `Fixes #<number>` (or `Closes #<number>`) — "PR body must include `Fixes #<number>` (or `Closes #<number>`) so GitHub auto-links and auto-closes on merge." (SKILL.md:888) | PR body, near top (title line: `gh pr create --title "Fix: <summary> (#<issue-number>)" …`, SKILL.md:885) | first substantive line of the body | Fresh PR open (§9), every standard/story fresh PR — mandatory, not conditional (this row was missing from the S1 capture; the table's only pre-existing closing-keyword mention was folded into the Epic-integration PR row below, which is a *different* trigger — added here to close that capture gap against v1's actual text) |
| `## Doc grounding` (PR body section) | plain prose citing PRD/Architecture/CLAUDE.md sections, or lifted from the plan | PR body, near top | before `## Changes`-equivalent content | Fresh PR open (§9), when step 6 ran (plan-present lift or no-plan re-derivation) |
| `## Plan` link | `Implements the plan on #<N>: <plan-comment-url>` | PR body, near top | after `## Doc grounding` | Fresh PR open (§9), when a plan was consumed at §4.6 |
| `## Audit override` | quotes the §4.5 `Audit override: <reason>` (or "Audit skipped by user override") verbatim | PR body | its own section | Fresh PR open (§9), only when §4.5 ended in an override/skip |
| `## Plan override` | quotes the §4.6 `Plan override: <reason>` verbatim | PR body | its own section | Fresh PR open (§9), only when §4.6 ended in a user override |
| `## Predecessor` | links the closed predecessor PR + branch, reminder to delete old branch | PR body | own section, mirrors the plan's `## Predecessor` | Fresh PR open on a `-vN` branch (predecessor-PR detection, SKILL.md:871-880) |
| `## Follow-ups` | list of filed-issue URLs | PR body | own section, appended via `gh pr edit` | Whenever a follow-up is filed via §P5 / §10.4 (URL weaving, `follow-up-tracking.md:56-63`) |
| `## Known failures` | list of red tests + reproduction signal + issue link | PR body | own section | Retry-ladder escalation choice 1 ("Push with reds") or a confirmed-known pre-existing failure at triage (`retry-ladder.md:36`) |
| Epic issue comment — `Baseline established` | ```🤖 Baseline established\n- Epic branch SHA: <sha>\n- Main SHA: <sha>\n- Result: green\n- Date: <iso-date>``` (SKILL.md:797-803) | epic issue comment | fixed 4-line body | Bootstrap, legacy recovery, or post-rectification (epic-flow.md) |
| Epic issue comment — `Baseline override` | ```🤖 Baseline override\n- Story PR: #M\n- Reason: <reason>\n- Date: <iso-date>``` (SKILL.md:807-812) | epic issue comment | fixed 3-line body | User overrides a red baseline on a story PR under an open epic |
| Epic body batch-tick | flips every `- [ ]` → `- [x]` in `## Stories` and `## Definition of done` | epic issue body | existing section order, unchanged | Epic-as-target run, after the integration PR merges ("ready to integrate then close", SKILL.md:565-569) |
| Epic-integration PR | title `Epic #<N>: <title>`, body cites `## Goal` + DoD checklist + `Fixes #<epic-number>` | new PR, `epic/<N>-<slug>` → `main` | — | Epic-as-target run, all stories closed + DoD verifiable |
| Story PR base note | `This story targets the \`epic/<N>-<slug>\`` integration branch and will reach \`main\` via the integration PR for epic #<N>.` (SKILL.md:631) | story PR body | inline sentence | Story-flow PR open, when a parent epic is open |

**Not written by the resolver, for clarity:** the `<!-- implementation-plan:v1 -->` comment
(planner), the `<!-- epic-delivery-log:v1 -->` comment (evaluator), the
`<!-- pr-evaluator-health-cache:v1 -->` comment (evaluator), the `<!-- open-question-links:v1 -->`
section (drafter). See "Artifacts read" below for what the resolver consumes from each.

## Artifacts read

| Artifact | Marker | Where | What's extracted |
|---|---|---|---|
| Implementation plan | `<!-- implementation-plan:v1 -->` | issue comment | `## Doc grounding`, `## Architecture decisions`, `## Changes`, `## Data model / schema impact`, `## Test plan`, `## Phases` (structured bullets), the SHA the plan was built against — fetched by `GATHER_ISSUE`'s `marker_prefix` lookup (step 2), parsed by the state-distiller (§P6) |
| Open-question links | `<!-- open-question-links:v1 -->` | build-issue body, `## Open questions` section | Per-entry disposition (`scoped-out` / `in-scope (blocked)` / `provisional-default`); read for context only — never implemented as scope or DoD (step 3's "Native `blocked by` is a hard gate" paragraph) |
| Native issue dependency | `blocked_by` list on the issue (GitHub native) | issue metadata, from `GATHER_ISSUE` | If any blocker is **open**, the issue is hard-gated to the `blocked` classification (step 3) |
| DoD checkbox annotations | closed set in `_shared/dod-annotations.md` | issue body, `## Definition of done` bullets | All five forms, read to detect prior rejections/predecessors before projecting (§9, §4.7 reconciliation) |
| Worktree setup/teardown blocks | `<!-- worktree-setup -->` / `<!-- worktree-teardown -->` | consuming repo `COMMANDS.md`/`CLAUDE.md` (+ `@`-includes) | List of commands run in declaration order (via `worktree-hooks.sh`); resolver only runs `setup` |
| Resolver-side config blocks | `<!-- issue-resolver-fast-checks -->`, `<!-- issue-resolver-test-target -->`, `<!-- issue-resolver-canonical-suite -->` | consuming repo `COMMANDS.md`/`CLAUDE.md` | Static-checks list, test-selection sub-agent config, full-canonical-suite commands (§P3.1) |
| Fallback config blocks | `<!-- pr-evaluator-static-checks -->`, `<!-- pr-evaluator-health-checks -->`, `<!-- pr-evaluator-test-target -->` | consuming repo `COMMANDS.md`/`CLAUDE.md` | Used only when the resolver-side blocks are absent (§P3.1 fallback chain) |
| Epic branch | `epic/<N>-<slug>` (git ref, discovered by prefix) | consuming repo branches | Existence + name, via `git ls-remote --heads origin "epic/<N>-*"` |
| Epic issue body | `## Goal`, `## Background`, `## Stories`, `## Definition of done` | epic issue body | Story checklist state, DoD checklist state, strategic grounding for child stories |
| Epic delivery log | `<!-- epic-delivery-log:v1 -->` | epic issue comment | **Not consumed by the resolver in v1** — it is evaluator-written, planner-read per `_shared/epic-delivery-log.md`. No resolver `SKILL.md` line or reference file reads this comment; row included here for completeness against the contract this file participates in adjacently (see "Known bugs / gaps"). |
| Prior handoff timestamp + operator marker | `<!-- operator-phase-complete: <N> -->` | issue comment, posted after the prior handoff | Deterministic signal that an operator/decision-only phase completed (`dod-projection-rule.md:16-19`) |
| PR review threads | `gh api .../pulls/<N>/reviews` and `.../comments` | PR | Line-level review comments, read alongside `gh pr view --comments` ("Reading the full PR context", SKILL.md:677-693) |
| Known-issue triage search | `gh issue list --search "<test> OR <suite> OR <keyword>"` | consuming repo issues | Candidate pre-existing-failure trackers (`retry-ladder.md:26-36`) |

## Operator gates

Every explicit `AskUserQuestion` decision point, exhaustively:

| Gate | Header | Options | What each does |
|---|---|---|---|
| Ambiguous issue/repo (step 1) | (freeform, "ask once") | — | Disambiguates issue number / repo before any fetch |
| Epic branch, multiple matches | "Epic branch" | one per candidate branch (label = branch name, description = last-commit date/author) | Picks which orphaned/hand-created branch is canonical; stops until resolved |
| Parent epic, multiple matches (Story flow) | "Parent epic" | one per candidate epic (label = `#<N>`, description = title) | Picks which epic this story belongs to |
| §4.5 audit BLOCKER exit | "Audit" | **Revise via drafter** (default) / **Override with reason** / **Abort** | Routes body fix to drafter revise-loop / records override + carries to PR / stops the run entirely |
| §4.6 missing plan on non-trivial issue | (freeform stop-and-ask) | run the planner, or reply `proceed without a plan` | Gates on a finalized plan existing before code work starts |
| §6 doc-conflict | "Doc conflict" | **Update the doc** / **Reshape issue** / **Override with reason** | Changes the doc / routes back to drafter / proceeds against the doc with a recorded reason |
| Step 5 — open PR by someone else, actively worked | "Open PR" | **Review it** / **Leave a comment** / **Wait** | Decides how to interact with a competing in-flight PR without trampling it |
| Step 5 — stale PR by someone else | "Stale PR" | **Take it over** / **Start fresh** | Branches off the stale PR vs. starts a clean branch |
| Conflict handling (epic rectification) | "Rectify epic" | **Apply all** / **Apply some** / **Abort — manual** | Applies the conflict-resolution sub-agent's proposal in full, in part, or not at all |
| Retry-ladder escalation (§P4, from main loop at §8) | "Tests red" | **Push with reds** / **Defer the tests** / **Restructure** | Ships with documented reds / files follow-up issues and skips them / abandons the approach for re-planning |
| §10 iteration cap reached | "Iter cap" | **Continue** (free-text count) / **Accept current** / **Abort** | Extends the review loop / stops at current state / gives up |
| §10 sub-agent `deadlock` guard rail | "Review loop" | **Try another angle** / **Accept + defer** / **Abort loop** | Tries a different fix / exits and files a deferred follow-up / stops |
| §10 sub-agent `architectural` guard rail | "Decision" | one option per candidate path the reviewer named | Resolves an architecture/API/scope tradeoff the sub-agent can't guess |
| §10 sub-agent `verification_failure` guard rail | "Tests red" | same three as retry-ladder escalation | Same semantics, raised from inside the review sub-agent (which can't call `AskUserQuestion` itself) |
| §10 sub-agent `grounding_violation` guard rail | "Grounding" | **Re-plan** / **Abort** | Routes an unfixable in-scope constraint violation to the planner, or stops (no defer/ship option) |
| §4.7's operator-phase-complete fallback | "Op phase `<N>` done?" | **Yes — apply** / **No — re-show handoff** / **Other** | Confirms an operator phase completed when no deterministic marker comment was found |
| End-of-§10 follow-up checkpoint (§P5) | (freeform batch-approval prompt) | approve / edit list / drop items | Batch-files `file-at-checkpoint` follow-ups before §11 |

## Judgment steps (model reasoning — stays in the prompt)

| Step | What it decides | Isolated sub-agent? |
|---|---|---|
| §3 current-state determination | Latest decision vs. stale discussion, superseded approaches, blocked-on, effective plan | Yes — **state-distiller** (`Explore`, `references/state-distiller-prompt.md`) |
| §4 response-type classification | bug / feature / question / refactor / blocked / duplicate / epic / story | Main loop (consumes distiller's `## Classification`) |
| §4.5 fitness-to-implement audit | Doc coherence, codebase coherence, internal coherence, latest-decisions, cross-issue drift, implementation readiness, plan-vs-code currency | Yes — **fitness audit** (`Explore`, `references/issue-audit-prompt.md`) |
| §4.6 plan-gate materiality judgment | Whether thread-supersedes-plan / plan-vs-code drift is material enough to re-route | Main loop (on sub-agent exception/finding) |
| §4.7 multi-phase detection | Single-phase vs. multi-phase; current-phase selection | Main loop (consumes distiller's parsed `## Phases`) |
| Step 6 doc grounding | Which PRD/Architecture/CLAUDE.md sections constrain the implementation (no-plan path only) | Main loop |
| Step 8 "stick to the plan" gap-filling | Below-plan-altitude vs. genuine-open-decision vs. reversal | Main loop, mini "Step 7.5" |
| Epic conflict resolution proposal | Coherent cross-file conflict resolution, clustering large conflict sets | Yes — `general-purpose` sub-agent (epic-flow.md "Spawn the sub-agent") |
| §8/§10.6 test selection | Which test suites the diff requires | Yes — **test-selection** (`Explore`, `references/test-selection-sub-agent.md`) |
| Retry-ladder research breakpoint | Structural understanding of a sticky test failure | Yes — `Explore` sub-agent (ad hoc, per `retry-ladder.md` "Research breakpoint requirements") |
| §10 review-verdict classification + action | Addressable / Explicitly-deferred / Cheap-fix-override / Decision-required / Grounding-violation | Yes — **review-loop sub-agent** (`general-purpose`, `references/review-loop-sub-agent.md`); the `review` skill invocation itself runs in the main loop, not the sub-agent |
| §11 outcome-rubric classification | Which of the 13 outcome-rubric rows applies, and thus which of the 9 handoff renderings fires | Main loop |
| §12 handoff `Why:` authorship | Judgment prose naming the specific evidence | Main loop |
| Follow-up filing type/urgency classification | `bug` / `incomplete-feature` / `deferred-test` / `revise-existing`; `file-now` / `file-at-checkpoint` | Main loop populates the registry; a `general-purpose` proxy sub-agent files via the drafter (`_shared/follow-up-filing.md`) |

## Deterministic steps (candidate script work — moves to a prep/executor script)

| Step | Input → Output |
|---|---|
| Issue-number/repo extraction | User text (`#423`, URL, `--repo`) → issue number + owner/repo |
| State-vector derivation: labels → type | Issue `labels` list → epic/story/none signal (case-insensitive `epic`/`story` match, or title `Epic:` prefix) |
| Plan marker + SHA detection | `GATHER_ISSUE`'s `marker_comment_path`/`marker_comment_body` → plan-present boolean + recorded SHA |
| Fresh/continue mode from the prior-PR state table | Existing-PR signals (open/draft/closed, author, resolved-or-not) → one of 7 rows in the step-5 table (SKILL.md:645-651): Open-PR-yours, Open-PR-other-active, Open-PR-other-stale, Draft, Closed-resolved, Closed-not-resolved, No-prior-PR |
| Epic-branch discovery | `git ls-remote --heads origin "epic/<N>-*"` → zero/one/multiple match classification |
| Fresh-slug computation (bootstrap only) | Epic issue title → `epic/<N>-<slug>` via the 6-step derivation (strip `Epic:` prefix, lowercase, `[^a-z0-9]`→`-`, strip leading/trailing `-`, truncate ≤50 chars on a `-` boundary) |
| Story parent-epic search | `gh issue list --label epic --state all --search "#<N> in:body"` → zero/one/multiple match |
| Branch-collision suffixing (`-vN`) | `git ls-remote --heads origin "<issue>-<slug>*"` → highest existing `-vN` suffix + 1 (unsuffixed = `v1`) |
| Audit-ref derivation | Issue context (bug/feature/refactor vs. Epic-as-target vs. Story-under-epic) → `origin/main` or `origin/<epic-branch>` (4-row table, §4.5) |
| Phase-facts parsing | Plan's `## Phases` section → structured list: `number`, `title`, `kind` (`code-shipping`\|`operator`\|`decision-only`), `ships`, `closes-dod`, `deliverable`, `depends-on` |
| Open-question facts extraction | `## Open questions` body section + native `blocked_by` → gated-scope list + hard-gate boolean |
| Workspace ensure per mode | Existing-work-check outcome (the step-5 prior-PR state table, above) → `git worktree add`/reuse decision + path |
| Test/fast-check config pinning | `<!-- issue-resolver-fast-checks -->` / `-test-target` / `-canonical-suite` blocks (or fallback chain) → resolved command set for the run |
| DoD-projection diff computation | `## Phase tracker` ticked entries × captured phase list's `closes-dod` → expected-ticked-bullet set minus current-ticked-set minus rejected-set |
| DoD re-plan drift detection | Ticked-bullet annotations vs. captured phase list → drift flag (phase renumbered/reassigned) |
| Trust-state computation (epic baseline inheritance) | `Baseline established` comment date + `merge-base` SHA comparison + `Baseline override` comment scan → skip/re-run baseline decision |
| Epic-vs-main drift assessment | `git rev-list --count` both directions + `git merge-base` + prior-main-merges count + open-story-PR count + file-overlap count → rebase/merge strategy selection (4-rule decision table) |
| Story-branch drift check | `git rev-list --count <story-branch>..origin/<base-branch>` → merge-vs-rebase-vs-nothing recommendation |
| Known-issue triage partition | Failing-test set × selection sub-agent's own diff-transiting rationale → diff-transiting vs. seemingly-unrelated partition |
| Adaptive cheap-fix rule | Failing-test sets across two runs → strictly-changed vs. sticky classification |
| Predecessor-PR detection | `gh pr list --state closed --search "<N> in:body"` filtered to `Re-plan superseded this PR` bodies → predecessor branch name (for `-vN` suffixing) |

## Invariants (with the WHY)

- **Post setup on every worktree entry, including reuse.** A worktree whose per-worktree state is
  missing (create-arm run missed it, sibling tool deleted it, prior invocation skipped it) silently
  falls back to a shared global resource, defeating per-worktree isolation and making both
  pass/fail results untrustworthy (`_shared/worktree-lifecycle.md:49-55`).
- **The resolver creates worktrees and runs setup; it never removes.** A worktree may hold
  unpushed commits or in-flight edits — silent teardown would lose work. Removal is the evaluator's
  job (the only automatic remover) or the user's manual call (SKILL.md:77, `_shared/worktree-lifecycle.md:146-153`).
- **Discover the epic branch slug by prefix; only compute fresh on bootstrap.** Two independent
  runs computing a slug from the title can diverge — issue #102 produced `visual-redesign` (run 1)
  vs. `daily-journal-visual-redesign` (run 2); an exact-match check would have orphaned the original
  branch's commits (SKILL.md:459, common-pitfalls.md:40).
- **Rebase force-pushes the epic branch; merge doesn't.** Choosing rebase when open story PRs exist
  against the epic branch rewrites their base and forces every story author to fetch+reset — the
  4-rule strategy table exists to avoid disrupting in-flight sibling work (SKILL.md:542-546).
- **Story runs surface epic-vs-main drift but never rectify it.** A story-flow rebase would
  force-push under sibling story PRs — rectification crosses a responsibility boundary that belongs
  to the epic owner (common-pitfalls.md:39).
- **Run the epic canonical suite as a harness-tracked background bash owned by the main loop, never
  delegated to a sub-agent.** A sub-agent can end its turn while `xcodebuild` (or equivalent) is
  still running and have its session torn down, orphaning the process and losing the final tally —
  this already happened once (`epic-flow.md:18`).
- **Use absolute paths for the backgrounded canonical-suite command; never chain behind a relative
  `cd … &&`.** If the shell cwd is already the worktree, a relative `cd .worktrees/<branch> && …`
  fails and `&&` short-circuits to a false `exit 0` — the suite silently "passes" having run nothing
  (`epic-flow.md:22`, common-pitfalls.md:42).
- **Never re-issue `full-suite` on a retry; use `build-once` once then `retry-without-rebuild`.** A
  plain `<wrapper> test` cold-rebuilds the whole app target on every invocation on a compiled stack;
  repeatedly paying that cost is what turned one re-baseline into a multi-hour hang (`epic-flow.md:11-16`).
- **§8 is mandatory before the first push, even though §10.6 also runs tests.** On a clean
  first-pass review approval, §10.6 never fires — §8 is the *only* test invocation that runs before
  the PR exists. Skipping it on the theory that "review will catch it" or "pr-evaluator will catch
  it" is a documented bug class: `review` doesn't run tests, and pr-evaluator runs after the PR is
  already open with possibly-broken code (SKILL.md:850, common-pitfalls.md:13).
- **Never run the full canonical suite at the §8/§10.6 story gates.** Targeted selection is the
  entire point of those gates' cost model; reproducing the full suite there defeats it. The full
  suite runs only in the epic-baseline/bootstrap/post-rectification flow, in CI, and in
  `github-pr-evaluator` (common-pitfalls.md:14).
- **Cap the pre-push verification gate at 3 runs with a forced research breakpoint.** Without a
  cap, a complex failure spirals into tweak→re-run→tweak, re-paying the suite's fixed setup cost
  each time and producing nothing review couldn't have caught (`retry-ladder.md:3`).
- **Force the research breakpoint on sticky failures, not just after 2 runs.** The small-fix
  spiral's signature is sticky failures with shrinking patches — each iteration tweaks the same
  path on the same wrong hypothesis; detecting non-progress at run 2 cuts the spiral off early
  (`retry-ladder.md:44-47`).
- **Triage unrelated failures against known open issues before spending the fix budget.** Reverting
  the diff to check if a failure predates the change works, but re-pays the suite's setup cost to
  answer a question GitHub may already answer for free via a search (`retry-ladder.md:19`).
- **`review` (the built-in `/review` command) must run in the main conversation, never inside an
  `Agent`-dispatched sub-agent.** Sub-agents can only reach project/user/plugin skills via `Skill` —
  bundled skills and built-in commands are unreachable one layer in, and sub-agents cannot spawn
  further sub-agents either. Putting the review invocation inside the §10 sub-agent was the
  original design and it consistently failed, forcing the sub-agent to improvise a manual review
  and return prose instead of a real verdict (PR #607, common-pitfalls.md:28, SKILL.md:930).
- **After `/review`'s verdict text lands, the model's next emissions must be operational tool
  calls, not more prose.** The verdict text reads like a finished deliverable, and stopping there
  is the documented PR #416 / #653 failure mode: a session ends without ever emitting the handoff,
  which is indistinguishable from "work is done" (SKILL.md:922, common-pitfalls.md:29).
- **"Approved" is not the exit condition; re-classify every listed item per §10.4 regardless of the
  reviewer's summary framing.** Reviewers routinely approve with non-blocking items they still
  expect fixed ("approved with minor fixes"); soft politeness ("could be fast-follow", "not
  blocking") does not by itself move an item out of Addressable (SKILL.md:962-964, common-pitfalls.md:27).
- **A Grounding-violation item is never filed as a follow-up.** A follow-up tracks debt that
  *shipped*; the hard-block exists precisely to stop the ship, so filing one would launder the exact
  merge the block disallows (SKILL.md:983).
- **Never tick a DoD bullet the shipped phase's `closes-dod` doesn't claim, even if the diff happens
  to also satisfy it.** The resolver projects the planner's declaration; it doesn't infer. Ticking
  beyond the declaration mis-attributes closure and defeats the planner's exact-coverage invariant
  (common-pitfalls.md:56).
- **Never re-tick a bullet the evaluator has rejected (sticky veto).** Re-ticking would clobber the
  evaluator's evidence and reintroduce the silent rubber-stamping the per-phase verification exists
  to prevent; the disagreement is resolved by re-planning or a new phase, not by silent re-ticking
  (`dod-projection-rule.md:29`, common-pitfalls.md:57).
- **Never mark a multi-phase PR ready except at the last-planned-phase-shipped handoff, and never
  add `Closes #N` in reaction to shipping a phase.** Marking ready or touching the close directive
  is the evaluator's DoD-verification judgment to make, not the resolver's mechanical projection
  (common-pitfalls.md:55).
- **On the last-planned-phase-shipped handoff, flip the PR draft→ready immediately before emitting
  the handoff.** Without the flip, the evaluator's own draft-PR guard deadlocks the handoff — this
  was an observed failure (`handoff-renderings.md:68`, transcript `/tmp/671-resolver.md` +
  `/tmp/671-evaluator.md`).
- **Never hand off to the evaluator until the plan's last phase has shipped.** Emitting the
  evaluator handoff after a non-final phase invites merging a partial implementation — exactly how
  Phase 1 of #640 landed on `main` as #648 before any DoD item was satisfied (common-pitfalls.md:54).
- **Re-routes never cross the session boundary — the handoff is the only signal.** Session-per-skill
  is the deliberate architectural choice that keeps each skill's context clean; calling the `Skill`
  tool from inside a re-route would silently defeat that isolation (SKILL.md:1071,
  `_shared/handoff-format.md:122`, `_shared/subagent-decision-signal.md:33`).
- **The audit sub-agent must read code/docs at an explicit `audit_ref`, never the orchestrator's
  cwd.** Without an explicit ref, the audit reads whatever the working tree happens to hold and
  fabricates BLOCKERs against symbols that exist only on the actual integration branch — this
  already happened on Epic #154 (audit grepped `main`, missed every epic-branch symbol)
  (SKILL.md:285, issue-audit-prompt.md:23-24).
- **The state-distiller and the fitness audit split reading along a strict read-type seam — the
  distiller never reads code, the audit never reads the raw thread as its primary input.** Neither
  sub-agent's output straddles the other's domain, which keeps each isolated dispatch narrowly
  scoped and its conclusions independently auditable (SKILL.md:49-51, state-distiller-prompt.md:5,9).
- **Every finding from an isolated sub-agent must cite evidence (a quote, a `file:line`, a dated
  comment); an uncited finding is dropped.** Vague-but-honest is better than confidently-wrong —
  this is the same evidence bar the drafter's reviewer uses (issue-audit-prompt.md:102-110,
  state-distiller-prompt.md:38-40).
- **Follow-ups always route through the drafter's proxy-confirm protocol; never hand-craft a `gh
  issue create` body.** Hand-crafting bypasses the drafter's PRD-grounded review loop and produces
  issues with inconsistent format and missing parent references (common-pitfalls.md:51,
  `_shared/follow-up-filing.md`).
- **Comment-only responses are staged to a scratch file and posted via `github-ops`'s
  `PERSIST_COMMENT`, never assembled inline.** Staging the body to
  `/tmp/gh-resolver-<issue-number>/comment.md` and passing the path means the body never
  re-serializes across the prompt boundary, so prompt compaction can't abbreviate it and the
  in-agent Write/Bash race that filed empty bodies on the drafter's #626/#627 has nothing to race
  on (SKILL.md:858-860). **Note:** this staging discipline applies only to the comment-only path —
  see "Known bugs / gaps" for the resolver's issue/PR **body** writes, which do not go through
  `github-ops` at all.

## Sub-agents dispatched

| Sub-agent | Reference prompt file | Consumes | Returns |
|---|---|---|---|
| state-distiller | `references/state-distiller-prompt.md` | Issue body, full thread, plan marker (each inline or scratch-path), labels, integration-target ref — never the conversation history | `## Current state` + `## Effective plan` + `## Classification` (normal), or `## Exception` with code `THREAD_SUPERSEDED_PLAN` \| `PHASES_MALFORMED` \| `AMBIGUOUS` (per `_shared/subagent-decision-signal.md`) |
| fitness audit | `references/issue-audit-prompt.md` | Issue number/type, repo root, dimensions subset (1-7), related-issue numbers, `audit_ref`, `plan_sha` — self-fetches the issue, siblings, and plan via `gh` | `## Audit summary` + `## Findings` (severity BLOCKER/SUGGESTION/NIT per finding, each with evidence) |
| test-selection | `references/test-selection-sub-agent.md` | Worktree path, integration target, `<!-- issue-resolver-test-target -->` block contents | `COMMAND:` (shell command or `(none)`) + `RATIONALE:` (one or two sentences) |
| review-loop sub-agent | `references/review-loop-sub-agent.md` | PR number/URL, repo, worktree path, originating issue/epic, integration target, iteration index, verdict-file path, doc-grounding statement, audit-override text, test-config blocks, prior-addressed-items, prior-decisions, resume hint | JSON: `status` (`iteration_complete`\|`needs_decision`\|`aborted`), `decision_request`, `final_pushed_sha`, `iteration_test_status`, `items_addressed`, `items_filed_as_followups`, `items_carried_as_procedural_notes`, `user_decisions` |
| epic-conflict-resolution proposer | inline prompt in `references/epic-flow.md` ("Conflict handling" step 3) | Conflicted files with markers, epic-side + main-side commit context, epic Goal/Stories excerpt, main merged-PR list | Text-only proposal: per-file final contents/diff + rationale; never writes |
| research breakpoint reader | ad hoc, per `references/retry-ladder.md` | Failing test files, source they exercise, recent diff | What's actually failing, what code paths it transits, what structural change is implied |
| follow-up drafter-proxy | `_shared/follow-up-filing.md` | Type/title-hint/description/parent-reference/repo for one follow-up item | Filed issue URL (or `error: <reason>`), the drafter's final type, an optional correction note |

## Known bugs / gaps

- **Fallback commands can be invented rather than declared.** If neither `issue-resolver-canonical-suite`
  nor `pr-evaluator-test-target`'s `full-suite-command` exists, the skill falls back to "ask the user
  for the command rather than inventing a plain `test`-action invocation" — but this is a documented
  worst-case path, not a hard block; a project that has declared neither block gets a materially worse
  experience (re-cold-rebuilds on every retry) with only a warning, not a stop (SKILL.md:136,
  `epic-flow.md:16`).
- **Issue/PR body writes bypass `github-ops` entirely, diverging from CLAUDE.md's repo-wide Rule
  7.** The resolver's *only* `github-ops` op is `PERSIST_COMMENT`, and it fires solely on the
  comment-only response path (SKILL.md:26,55,860 — three mentions total, zero for any other op).
  Every issue-body or PR-body write — DoD projection (`gh issue edit --body-file`, SKILL.md:443,868,910),
  fresh PR creation (`gh pr create --body-file`, SKILL.md:885), the epic integration PR
  (SKILL.md:563), the epic body-tick close-out (SKILL.md:567), and Phase-tracker updates
  (`gh pr edit`, SKILL.md:866,908) — is a direct, hand-rolled `gh ... --body-file <scratch-path>`
  call that never routes through `github-ops`, despite `agents/github-ops.md` defining a
  `PERSIST_BODY(mode=replace)` op for exactly this staged-replace shape, gated by the same
  `test -s <body_path>` empty-body check CLAUDE.md's Rule 7 exists to enforce ("Every op with a
  script MUST go through it... Hand-rolled `gh issue view`/`mktemp + Write + gh ... --body-file`
  re-opens the empty-body race"). Each of these calls does stage its body to a scratch file first
  (so the acute empty-body race is independently mitigated), but the *contract* — one execution
  path per CLAUDE.md — is not honored for body writes the way it is for the comment path.
- **The epic delivery log (`<!-- epic-delivery-log:v1 -->`) is never read by the resolver in v1**,
  despite being named in this spec's assignment as a contract the resolver participates in. Per
  `_shared/epic-delivery-log.md`, the evaluator is the sole writer and the planner is the sole
  reader; no resolver `SKILL.md` line or reference file fetches or parses this comment. This is not
  a defect (ownership is correctly scoped elsewhere) but is recorded here since a spec reader might
  otherwise assume the resolver consumes it.
- **`handoff-renderings.md` and SKILL.md both self-describe "seven rendering shapes," but the file
  actually contains nine** (`SKILL.md:1017,1077`; `references/handoff-renderings.md:3` say
  "seven"; the file has 9 `## <name>` rendering headings, each followed by its own `## Handoff`
  example — confirmed by `grep -c '^## ' references/handoff-renderings.md` = 18, i.e. 9 rendering
  headings + 9 `## Handoff` example headings). This is a pre-existing miscount in the v1 source
  itself, not a spec transcription error — flagged here so a v2 implementer counting "seven"
  against the actual file doesn't silently drop two renderings.
- **Resolver step-6 doc-read vs. guides — checked, not present in this source.** A prior-session
  memory note flags a possible "resolver step-6 doc-read vs. guides" concern (guide docs at
  `docs/guides/*` being authoritative over a stale in-code doc-read). This resolver's actual step 6
  (SKILL.md:720-746) reads `docs/prd.md`, `docs/architecture.md`, `CLAUDE.md`, and any
  `@`-included constitution file — there is no `docs/guides/*` convention referenced anywhere in
  `SKILL.md` or its references, and no line resembles the described bug. Per this spec's brief
  instruction to "only record it if the v1 SKILL.md actually exhibits it," it is **not** recorded
  as a bug here; the memory note likely refers to a different resolver revision, a different repo's
  convention, or a fix already landed upstream of this snapshot.
- **The §4.7 phase-exhaustion check and the multi-phase draft→ready flip depend on the resolver
  correctly re-deriving "last planned phase shipped" from the plan's `## Phases` on every re-entry**
  (SKILL.md:1039-1046). If a prior run's `gh pr edit` to the `## Phase tracker` silently failed (the
  §9 push path explicitly tolerates this — "Do not abort the resolver run on projection failure"),
  a later re-entry's reconciliation is the only backstop; the failure mode where reconciliation
  itself never runs (e.g., the run crashes before §4.7 re-fires) is not explicitly handled — SKILL.md
  states the reconciliation happens "on every re-entry" but does not describe recovery if a re-entry
  is itself skipped by direct continuation into §8 for some other reason. Not observed as an actual
  incident in the source; flagged as a structural gap in the self-healing story.
- **The retry-ladder's "unrelated failure" triage relies on the test-selection sub-agent's own
  stated rationale to partition diff-transiting vs. seemingly-unrelated failures** (`retry-ladder.md:21-24`).
  If the sub-agent's rationale is imprecise or the heuristic mis-attributes a failure's category,
  the triage can search for (or skip searching for) the wrong bucket of tests. This is inherent to
  the design (the ladder trusts the selection sub-agent's own accounting) rather than a discrete
  reported incident, but is worth flagging as a latent precision dependency.
- **Bare-digit `in:body` search false-positives (newly discovered, not captured at S1 freeze).**
  Requirement: the step-5 prior-PR table's `gh pr list --search "<N> in:body"` search (SKILL.md's
  documented convention, also `_search_closed_prs`'s identical construction) must only surface a PR
  that genuinely references issue `<N>` — never a stranger PR whose body merely contains the digit
  `<N>` as unrelated prose. Falsifiable test: given an issue with no PR referencing it but another
  open PR whose body contains `<N>` incidentally (e.g. a `## Phase tracker` entry reading "Phase
  2"), the prior-PR row must classify as `no-prior-pr`, never treat that stranger PR as the row.
  Real occurrence (live, read-only, against the sandbox repo, 2026-07-11, discovered while
  live-smoking S12's `prep_planner.py`): `gh pr list --search "2 in:body"` returned four open PRs
  referencing issues #35/#36/#43/#44, **none** referencing issue #2 — each merely contains the
  literal text `"Phase 2"` in its `## Phase tracker` section. A control run with the hash-prefixed
  form, `gh pr list --search "#2 in:body"` (the form `_search_parent_epic` already uses), returned
  the **identical** false-positive set — GitHub's server-side full-text search does not anchor on
  `#`, so the query form itself is not a mitigation; a client-side filter is required. Scope: this
  construction is shared by `gh_gather.py`'s `_fetch_open_prs` (this resolver's prior-PR row AND
  `github-issue-planner`'s `plan_ref` open-PR-head row — see `docs/specs/planner.md`'s "Known
  bugs/gaps" Bug (c) for the full evidence and root-cause writeup), `prep_resolver.py`'s
  `_search_closed_prs`, and both skills' `_search_parent_epic`. v1's `gh-gather.sh` carries the
  identical exposure and is not fixed by this record — v2 fixes it via
  `gh_gather.references_issue` (a digit-boundary-guarded `#<N>` match, or `closingIssuesReferences`
  membership, applied as a client-side post-filter). This is therefore an **expected, explained
  parity divergence**: a parity run against a repo state with an incidental digit collision will
  legitimately see v2 route differently (correctly) from v1 (which inherits the false positive) —
  not a v2 regression.
