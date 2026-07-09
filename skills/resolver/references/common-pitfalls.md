# Common pitfalls

The resolver's anti-patterns, extracted here so they don't consume the load budget. The spine's S5 reads
this file before any code or review-loop work begins. Each bullet is the full text of one pitfall; the
`§N` references name the v2 flow points (the spine's §8 pre-push gate, its §10.6 review-loop re-push gate,
its §review-loop, its S6 DoD projection) that carry the same numbering v1 used, so cross-references from
`retry-ladder.md` / `review-loop-sub-agent.md` still resolve.

- **Don't ignore in-progress PRs.** Prep classifies the prior-PR state; a gated row means another author's
  PR already exists — never fall through to opening a duplicate. Opening a duplicate PR wastes everyone's
  time and is rude.
- **Don't take over someone else's PR silently.** If a PR by another author exists for this issue (a gated
  row), the router renders the gate before doing anything that would compete with or supersede it.
- **Don't implement code without grounding in project docs.** If `docs/prd.md`, `docs/architecture.md`, or
  `CLAUDE.md` exists, read it (from the read workspace) before designing the change and cite the relevant
  sections in the PR. Skipping this leads to implementations that violate non-negotiable project rules
  (layer boundaries, banned APIs, naming, scope) that the docs encode.
- **Don't start non-trivial code work without a finalized plan.** The plan gate stops on a
  `<!-- implementation-plan:v1 -->` plan comment. Missing on a non-trivial issue → stop and ask for one
  (or take the user's explicit `proceed without a plan` override, recorded in the PR body). The plan is
  where the approach was researched and verified; improvising past a missing plan throws that away.
  Trivial fixes and comment-only flows are exempt — the gate doesn't fire for them.
- **Don't re-plan when a plan exists.** When the plan gate finds a plan, consume it — lift its grounding
  and implement its locked decisions. Re-deriving the approach in the main conversation duplicates the
  planner's verified work and risks diverging from the artifact the evaluator will check against. The
  exception is the plan-currency check: if the code or issue body drifted since the plan's SHA, route back
  to the planner in revise mode rather than patching around the staleness.
- **Don't silently deviate from a locked plan decision.** Implementing freely *within* the plan's
  decisions is expected; reversing one (a planned API, layer assignment, or data-model shape that turns out
  wrong) is not — stop and route back to the planner in revise mode with evidence. A quiet workaround
  diverges the diff from the plan, breaks the evaluator's adherence check, and loses the decision's
  provenance.
- **Don't skip the green-baseline check for the integration target.** The integration target is `main` for
  regular issues and the epic integration branch for stories under an open epic. A story under an open epic
  *inherits* the epic-level baseline and shouldn't re-run it — unless `main` has been merged into the epic
  branch since that baseline, or a prior story under the epic landed under an explicit baseline override.
  The point of the gate is correct failure attribution and not shipping over a broken codebase, not running
  tests for their own sake. If the baseline is red, stop and surface every failing test — silent fixes
  scope-creep the PR. Acceptable next moves are detour first, or explicit user override with a documented
  reason.
- **Don't silently fix unrelated pre-existing failures.** If the baseline reveals broken tests outside the
  scope of this issue, surface them — don't fold the fix in without telling the user. It scope-creeps the
  PR and obscures what your change actually did.
- **Don't push code without running the §8 pre-push verification gate.** The test gate runs at §8 (before
  the first push) AND at §10.6 (after addressing review feedback). Both are mandatory pre-push gates. On a
  clean first-pass review approval, §10.6 never fires — the §8 gate is the only test invocation that runs
  before the PR is opened. Skipping §8's tests on the assumption that "review will catch it" or "the
  evaluator will catch it" is a bug: the `review` skill is a code-quality reviewer that does not run tests,
  and the evaluator runs at PR-readiness time *after* the PR is already open with possibly-broken code on
  the branch.
- **Don't run the full unit + integration suite at the §8/§10.6 story gates.** Those gates run targeted
  tests; the full canonical suite runs in the evaluator (for epic-integration and labelled PRs) and on CI.
  Reproducing the full suite at a story gate defeats the targeted-tests strategy and re-imposes the
  cost-per-iteration this design exists to avoid. If you find yourself reaching for
  `<!-- pr-evaluator-static-checks -->` or `<!-- pr-evaluator-test-target -->` at a story gate, you've
  drifted off the path. (The epic-baseline / bootstrap / post-rectification flow *does* run the full
  canonical suite — that is the documented exception; see `epic-flow.md`'s "Running the full canonical
  suite".)
- **Don't fall back to zero tests when uncertain.** "Zero tests" is reserved for empty-diff and pure-docs
  paths. Any code change that the sub-agent can't narrow with confidence should hit the project's
  `broad-change-fallback` (typically "all unit tests, no UI") for the unit target. UI uncertainty defers to
  the evaluator (the `none` broad-change-fallback path) — that's intentional. But never push code with zero
  tests run on the theory that "the evaluator will catch it" when widening was the right call.
- **Don't inline the test-selection reasoning in main context.** The diff hunks, directory listings, and
  grep output stay inside the `Explore` sub-agent. Main context sees only the resolved `COMMAND:` and the
  one-line `RATIONALE:`. Inlining the reasoning regresses on token cost and clutters the conversation;
  pulling diff content into main context is exactly what the sub-agent indirection prevents.
- **Don't skip the rationale audit.** Print the sub-agent's `RATIONALE:` line to the user verbatim before
  executing the command. The user must see what was selected and why; silent selection is a regression even
  when correct, and bad selections are how this design fails — make them visible so they can be corrected.
- **Don't let the build subagent become a coder.** When delegating to `apple-platform-build-tools:builder`,
  the prompt must scope the subagent to "run the command and report result" only. No code edits, no
  failure-investigation expansion, no automatic re-runs with different flags. A subagent that silently
  turns a 30-second test run into a 55-minute diagnose-edit-rebuild loop hides changes from your commit
  history and the user's audit trail, and breaks the review-loop's contract that you control when code
  changes happen. If the build subagent reports a failure, surface it; don't hand it carte blanche to fix
  things.
- **Don't iterate small fixes when failures are sticky.** Two §8 (or §10.6) runs with the same failing
  test means the underlying understanding is wrong, not the patch. Take the research breakpoint per
  `retry-ladder.md` — read the full failure output, capture the stack's richest failure context for
  integration tests (e.g. XCUITest `app.debugDescription`, a Capybara `page.html`/screenshot), spawn an
  `Explore` sub-agent for structural read of the failure. Continuing to tweak burns 10–20 minutes per
  attempt with no information gain, and the same loop bounded by the **Don't let the build subagent become
  a coder** pitfall applies one layer up: the *parent* model running tweak → re-run → tweak → re-run is the
  same anti-pattern, just at a different layer.
- **Don't `rm` snapshot/golden files to force regeneration.** A failing snapshot test means recorded
  output changed in a way that needs human eyes — a pixel-level visual diff, a serialized-output change, an
  approved-file mismatch — and surfacing that is the whole point of the test category. Surface the diff to
  the user and ask before deleting. Auto-regenerating goldens silently accepts the regression and defeats
  the test's purpose. If the user confirms the change is intended, *then* delete and regenerate; record the
  confirmation in the PR body so reviewers can audit.
- **§8 is the pre-push gate, not the dev inner loop.** Iterate at unit-test granularity locally first —
  most wrappers support targeted single-suite runs (e.g. `xcodebuild -only-testing <Suite>`,
  `bin/rails test path/to/foo_test.rb`, `pytest tests/x.py::TestY`), which typically run in well under a
  minute. Reserve the §8 invocation (which legitimately includes integration tests via the test-selection
  sub-agent's widening rules) for the once-before-push integration check. Treating every code change as
  "make change → §8 → react" turns a 30-second feedback cycle into a 20-minute one and is the most direct
  cause of the small-fix spiral.
- **Don't read only the PR diff.** PR comments and code review threads (especially line-level review
  comments, which require a separate API call) are where decisions actually got made. Skipping them leads
  to redoing rejected work or contradicting settled directions.
- **Don't trust the issue title alone.** The title often reflects the original report; the actual problem
  may have shifted in the comments.
- **Don't re-litigate decided questions.** If a maintainer said "let's go with approach B" three comments
  ago, go with approach B.
- **Don't open a PR for a question.** Some issues are resolved by an answer, not a code change (the
  comment-only route).
- **Don't skip the review loop.** For any PR, `review` must approve before the work is considered done. No
  exceptions, no "this change is too small to review."
- **Don't exit the loop just because the verdict says "approved".** Reviews routinely approve with
  `Medium`, `Low`, or `Nitpick` items — issues *and* suggestions — that the reviewer still expects fixed
  (e.g., "Approved with minor fixes"). Exit only when `review`'s verdict is approved **and** the sub-agent's
  re-classification finds zero Addressable or Cheap-fix-override items in that verdict. Items the reviewer
  routes elsewhere with a **concrete tracking target** (filed as #N, depends on un-landed sibling, citable
  PRD/scope exclusion) are deferred and filed as follow-ups. Soft politeness alone ("could be fast-follow",
  "not blocking", "deferrable", "informational only", "future PR", "consider for a future change") is
  **not** sufficient — the sub-agent re-classifies per the rubric, and the **default for any
  concretely-named change is Addressable**. The Cheap-fix override addresses ≤ ~20-line fixes on
  already-modified files even when the reviewer defers them. The sub-agent boundary enforces this
  structurally for the *body* of an iteration (classify + act), and the main loop's tight "read JSON →
  re-invoke `review` or proceed to the handoff" sequencing protects the outer loop's exit decision — but the
  rubric still governs whether the loop should exit at all, so the hazard this bullet exists for hasn't gone
  away.
- **Don't drive `review` from inside the review sub-agent.** The `review` command (and the bundled
  `code-review` skill) is not reachable from inside an `Agent`-dispatched sub-agent — the `Skill` tool
  inside a sub-agent only reaches *project, user, and plugin* skills (per the sub-agents reference). Putting
  `Skill(skill="review")` inside the review sub-agent prompt was the original design and it consistently
  failed: the sub-agent had no path to the actual review and was forced to improvise a manual one, returning
  prose instead of the JSON envelope (PR #607). The fix is structural — `review` runs in the main
  conversation per the spine's review-loop control; the sub-agent classifies + addresses the verdict the
  main loop hands it. Don't reintroduce the `review` invocation into the sub-agent prompt thinking "this
  time stronger emphasis will work" — the constraint is the harness, not the model.
- **Don't stop at either turn-boundary beat in the review loop.** The review loop has two beats where the
  model can summarize-and-stop before the run finishes; both are the *PR #416 failure mode* and the *#653
  missing-handoff failure mode* re-imported one layer up. (a) **After `Skill(review)` returns** — the
  verdict text reads like a finished deliverable, but `/review`'s job is only to emit the verdict, not to
  close the loop. Your next tool calls in the same turn are `Write` the verdict file and the `Agent`
  dispatch — even when the verdict says "approved, zero open suggestions" (the sub-agent's step 6 handles
  that path with an early return). (b) **After the review sub-agent returns** — the next beat is either
  re-invoking `Skill(skill="review")` for another iteration, rendering a `needs_decision` via
  `AskUserQuestion`, or proceeding to the handoff if the exit condition holds. Treat reading the JSON as a
  step inside an iteration, not the end of one.
- **Don't post review feedback on the issue.** Review feedback on a PR goes on the PR, not on the
  originating issue.
- **Don't mis-route comments between issue and PR.** Problem questions go on the issue, solution questions
  go on the PR. Cross-posting or wrong-routing fragments the discussion and leaves future contributors
  hunting.
- **Don't assume the issue is still relevant.** If the thread has gone quiet for a long time, flag this and
  ask whether to proceed.
- **Don't nest worktrees or write the root.** The root is the read-only `main` vantage — never branch,
  commit, stash, or test there. All code work happens in `facts.workspace.path` (prep ensured it); when a
  second view is needed, read `facts.read_workspaces.audit.path`. Prep + `workspace.py` own worktree
  creation, reuse, and the `.gitignore` entry — the prompt never runs `git worktree add`.
- **Don't auto-clean worktrees.** A worktree may contain unpushed commits or in-flight edits. Cleanup is
  the evaluator's job (the only automatic remover) or the user's manual call — the resolver creates
  worktrees and never removes them.
- **Don't open a single feature PR for an epic.** Epics are containers; child stories are where code lands.
  Opening a monolithic PR for an epic conflates resolution with implementation and makes the PR
  unreviewable.
- **Don't target `main` for a story under an open epic.** The whole point of the integration branch is to
  keep `main` stable while the epic is in flight. If a story PR points at `main`, that defeats the model.
  The base must be `epic/<N>-<slug>` while the epic is open (the story route bases on `facts.audit_ref`,
  the parent epic branch).
- **Don't let the epic branch drift silently — but only act from epic-as-target runs.** Check epic-vs-main
  drift on every epic-as-target run and rectify when drift is found, choosing rebase or merge per
  `epic-flow.md`'s strategy table. When rebasing, push with `--force-with-lease` (never bare `--force`);
  when merging, push normally. Story runs surface epic-vs-main drift as an informational note only — they
  never rectify the epic branch, because the rectification crosses responsibility boundaries and a
  story-flow rebase would force-push under sibling story PRs. Long-lived branches that aren't periodically
  synced with main become unmergeable, but the rectification belongs to the epic owner.
- **Don't recompute the epic branch slug — discover it.** The slug rule is deterministic for the bootstrap
  path, but the epic title can change *after* a branch is created, and a stricter or shorter informal slug
  rule on a future run silently fails to match. This is exactly how issue #102 was hit: run 1 created
  `epic/102-visual-redesign`, run 2 computed `epic/102-daily-journal-visual-redesign`, and an exact-match
  existence check would have orphaned all the story commits already on the original branch. Prep discovers
  by prefix (`git ls-remote --heads origin "epic/<N>-*"`) and reports `facts.epic.branch`; recompute only
  on the bootstrap path (`facts.epic.bootstrap_slug`, zero matches).
- **Don't run epic baseline in the root.** Both bootstrap and legacy recovery use the work worktree prep
  ensured. Running the canonical suite in the root would force a checkout, prevent the user from using the
  root for unrelated work during the long suite run, and contradict the "root stays untouched" invariant.
- **Don't cold-rebuild the canonical suite on every re-run, and don't background it with a relative `cd`.**
  Re-issuing `full-suite` on a re-run re-pays the cold build that dominates wall time (what turned one
  re-baseline into a multi-hour hang), and a relative `cd .worktrees/<branch> && …` `&&`-short-circuits to
  a false "exit 0" with no tests run when the shell is already in the worktree. The full `full-suite` /
  `build-once` / `retry-without-rebuild` re-run discipline, the main-loop-background-bash rule (never a
  sub-agent, which can end its turn mid-build and lose the tally), and the absolute-path rule are specified
  once in `epic-flow.md`'s "Running the full canonical suite" — follow them there.
- **Don't merge the integration PR without running the review loop.** The integration PR lands the entire
  epic on `main` at once — it carries more risk than a single story PR. Apply the review loop to it just as
  you would any story PR.
- **Don't ignore the body checkboxes when closing an epic.** Body checkboxes don't auto-sync. A `- [ ]`
  next to a closed story is stale and misleads the next person who reads the epic. Always tick them before
  (or as part of) closing.
- **Don't restructure the epic body template.** The `## Goal` / `## Background` / `## Stories` /
  `## Definition of done` section names are load-bearing for traceability from `docs/prd.md`. Preserve them
  exactly.
- **Don't edit a parent epic's body from inside a story-target run.** The epic's body is authoritative
  state; it should only be updated from an epic-target run where you can see the full story-reconciliation
  picture.
- **Don't hand-craft follow-up issue bodies.** Every follow-up that warrants an issue goes through the
  sub-agent protocol in `follow-up-tracking.md`. Hand-crafting (writing the body inline, running
  `gh issue create` directly) bypasses the drafter's PRD-grounded review loop and produces issues with
  inconsistent format, missing parent references, and unvalidated framing against the project's
  architecture / constitution. The drafter exists exactly for this. Use it.
- **Don't conflate filing with capturing.** Procedural reminders (drift, epic-checkbox sync, "watch out
  for X in the next iteration") belong in the PR body or the handoff, not as filed issues. Issues are for
  trackable work that needs a separate place to discuss, plan, or assign; PR-body notes are for
  informational caveats a future contributor can act on with the PR context alone. Use the
  filing-vs-capturing criterion in `follow-up-tracking.md`.
- **Don't omit the evaluator handoff on PR outcomes.** The handoff's `Next:` line is the resolver's
  explicit handoff to the merge-readiness gate. Without it, users finish a resolution thinking the work is
  done — but the resolver has only run `/review` for code quality and targeted tests for verification;
  issue-fit against the originating issue, full canonical-suite execution, and merge-strategy selection
  happen inside the evaluator. Emit it on every PR outcome, including epic-integration PRs (where the merge
  risk is higher and the handoff matters more, not less).
- **Don't hand off to the evaluator until the plan's last phase has shipped.** On a multi-phase issue, the
  PR must not be evaluator-bound while phases in the plan's `## Phases` are still unshipped. Emitting the
  evaluator handoff after a non-final phase invites merging a partial implementation — which is exactly how
  Phase 1 of #640 landed on `main` as #648 before any DoD item was satisfied. Re-route to the resolver (for
  the next code phase) or surface the operator action verbatim (for the next non-code phase) instead. Only
  the *last planned phase shipped* row fires the evaluator handoff.
- **Don't mark a multi-phase PR ready, and don't add `Closes #N` in reaction to shipping the last phase.**
  A multi-phase PR opens as draft and stays draft through every phase the resolver pushes — including the
  last one, until you flip it draft→ready immediately before the last-phase handoff. Fiddling with the
  `Closes` directive in the title or body is judgment that belongs to the evaluator: it owns the DoD check
  that decides whether the shipped phases actually satisfy the issue.
- **Don't tick DoD bullets the phase's `closes-dod` doesn't claim.** The resolver projects the planner's
  declaration onto the issue body; it doesn't infer. If a phase's `closes-dod` lists bullets `[1, 3]`,
  those are the only bullets that flip on this push — even if the diff happens to also satisfy bullet 2.
  Bullet 2 is claimed by a different phase (per the planner's dimension-7 exact-coverage invariant), and
  ticking it here would mis-attribute the closure. If you believe the plan is wrong, route back to the
  planner in revise mode; never silently tick beyond the declaration.
- **Don't re-tick DoD bullets the evaluator has rejected.** A bullet annotated `- [ ] <text> (resolver
  claimed phase <N>, ...; evaluator rejected: ...)` is the evaluator's sticky veto — the diff in the
  attributed commit(s) didn't actually satisfy the bullet. Projection logic treats annotated-as-rejected
  bullets as not-projected even when `Phase tracker × closes-dod` would tick them. The disagreement is
  resolved by re-planning, by a new code phase whose diff actually satisfies the bullet, or by user
  intervention — not by silent re-ticking on the next push. Re-ticking would clobber the evaluator's
  evidence and re-introduce the silent rubber-stamping failure mode the per-phase verification exists to
  prevent.
