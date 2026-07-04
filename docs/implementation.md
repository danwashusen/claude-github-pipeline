# github-pipeline v2 — Implementation Plan

Step-by-step migration from v1 to the [architecture.md](architecture.md) design, preserving the
[prd.md](prd.md) product truth. Steps have stable IDs (`S1`–`S20`) — cite them, never renumber.
Each step is sized to be one issue and one PR.

## How to use this plan

- One step → one GitHub issue (drafted via the pipeline's own `drafter` where practical) → one
  PR into this repo's `main`. This repo runs the same write-protected-`main` model the plugin
  assumes ([prd.md §8](prd.md)); nothing lands without a PR.
- A step is done only when every DoD box is ticked; DoD is verified in PR review, not assumed.
- **Global DoD** (applies to every step, in addition to its own): `shellcheck scripts/*.sh`
  clean; `tests/run.sh` green; `jq . .claude-plugin/*.json` parses; [architecture.md](architecture.md)
  / [prd.md](prd.md) amended in the same PR when the step legitimately changed a contract
  (content edits only — §-anchors are stable).
- **Order:** the table below. After S8 (pattern lock) the remaining tracks are parallelizable;
  before it, everything is deliberately serial so the shared patterns are corrected while only
  one skill uses them.

| Step | After | Step | After |
|---|---|---|---|
| S1 baseline & specs | — | S11 sub-agent exceptions | S10 |
| S2 test harness | — | S12 prep-planner | S8 |
| S3 lib + envelope | S2 | S13 planner skill | S12, S11 |
| S4 workspace.sh | S3 | S14 prep-drafter | S8 |
| S5 parse.sh | S3 | S15 drafter skill | S14 |
| S6 prep-evaluator | S4, S5 | S16 researcher | S8 |
| S7 evaluator skill | S6, S1 | S17 setup | S8, S4 |
| S8 pilot retro & lock | S7 | S18 question pair | S8, S5 |
| S9 prep-resolver | S8 | S19 doc-reviewer | S8 |
| S10 resolver skill | S9 | S20 retirement | S9–S19 all |

## The sandbox repo

Live smoke and parity runs use a disposable consuming repo (**the sandbox**) — a real GitHub
repository seeded with: the pipeline labels (`epic`, `story`, `question`, `planned`,
`researched`, `audience:*`), one epic with two stories, one plain bug issue, one question issue,
grounding docs (`docs/prd.md`, `docs/architecture.md`), and the config marker blocks. S2 authors
`tests/SANDBOX.md` with the exact seeding steps. Offline tests never touch it; parity runs always
do.

## The parity protocol

Referenced by every skill-cutover step as "parity run", recorded per skill in
`docs/specs/parity/<skill>.md`:

1. Construct the target state in the sandbox (issue/PR in the shape the skill expects), or use
   twin targets for destructive flows.
2. Run the **v1** skill in one session. Capture: every GitHub write (fetch bodies afterward),
   every gate asked, the handoff text, and the session's rough turn count.
3. Reset (or switch to the twin) and run the **v2** skill on the same state.
4. Compare: persisted artifacts are schema-identical ([prd.md §7](prd.md)); the same genuine
   decisions were gated; the handoff validates against the shared schema; startup performed one
   state-assembly call ([prd.md §9.2](prd.md)).
5. Divergences are listed; each must trace to a PRD requirement (e.g. the §5.3 planner fixes) or
   be filed as a defect. Unexplained divergence fails the run.

---

## Phase 0 — Foundations

### S1 — Baseline capture & per-skill functional specs

**Goal:** freeze what v1 does, as the measurable spec for parity ([prd.md §9.5, §10](prd.md)).

**Work:** For each of the nine skills, extract `docs/specs/<skill>.md` from the v1 `SKILL.md` +
references: artifacts written/read, operator gates, judgment steps, deterministic steps
(candidate script work), invariants with their *why*, and known bugs. Record
`docs/specs/baseline.md`: v1 line counts, the contract-token census output (command + verbatim
result), and links to live examples of each persisted artifact. Fold in the two known planner
bugs as falsifiable spec lines: (a) an open question with an existing tracker issue must never be
recorded as "(not filed)"; (b) the handoff's open-questions line must render in combined
epic + story sessions.

**DoD**
- [ ] `docs/specs/` contains nine per-skill specs plus `baseline.md`.
- [ ] Every [prd.md §7](prd.md) artifact has at least one spec naming it as writer and one as
      reader (cross-reference table in `baseline.md`).
- [ ] Census command and verbatim output committed.
- [ ] Both planner bugs appear as falsifiable requirements in `specs/planner.md`.
- [ ] Each spec was adversarially re-read against its source `SKILL.md` in an isolated session
      or sub-agent; misses were folded in and noted.

**Testing:** documentation step — validation is the census run plus the adversarial re-read; no
harness involvement.

### S2 — Offline test harness

**Goal:** the [architecture.md §10](architecture.md) harness exists and provably intercepts.

**Work:** `tests/run.sh`; vendor bats-core under `tests/vendor/`; `tests/shim/gh` replaying
fixtures from `tests/fixtures/<case>/` keyed on exact argv (helpful diff on miss); a git-sandbox
helper (`mk_origin` / `mk_clone` in temp dirs with cleanup); `tests/README.md` (fixture layout,
adding a case); `tests/SANDBOX.md` (live sandbox seeding).

**DoD**
- [ ] `tests/run.sh` discovers and runs all `*.bats`, exits non-zero on any failure.
- [ ] Shim self-test proves interception: a probe script calling `gh` receives fixture bytes;
      un-fixtured argv fails the test loudly.
- [ ] Runs make no network calls and never invoke the real `gh` (asserted, e.g. via a poisoned
      `PATH` sentinel).
- [ ] Git-sandbox helper creates origin + clone and cleans up on exit, pass or fail.
- [ ] `tests/README.md` and `tests/SANDBOX.md` exist and suffice to add a case / seed the
      sandbox without reading harness source.

**Testing:** the harness tests itself: shim hit/miss cases, sandbox create/teardown, run.sh
failure propagation.

### S3 — `scripts/lib.sh` + the envelope

**Goal:** the [architecture.md §3](architecture.md) primitives every script shares.

**Work:** emit helpers (`ok` / `needs_decision` / `notice`), spill helper (threshold env: new
name honored, legacy `GH_OPS_INLINE_THRESHOLD_BYTES` fallback, default 25600), sha256 helper,
jq-safe JSON assembly, the closed decision-code constants; plus reusable bats assertions for
envelope conformance (status validity, decision payload shape, `*_mode`/`*_path` pairing,
exit-code contract) that all later suites import.

**DoD**
- [ ] Every lib function has a unit bats case.
- [ ] Conformance assertions exist and are importable by other suites (used by a toy script
      end-to-end test).
- [ ] Threshold precedence tested: new var, legacy var, default.
- [ ] Decision-code constants exactly match [architecture.md §3](architecture.md); a drift-check
      test compares the doc list to the lib list.

**Testing:** `tests/lib.bats` + the toy-script end-to-end envelope emission case.

### S4 — `workspace.sh`

**Goal:** the [architecture.md §6](architecture.md) lifecycle owner.

**Work:** subcommands `ensure --work <branch> --base <ref>` / `ensure --read <ref>` / `gc
[--max-age]` / `root-status`; root-freshness protocol (on-`main` + clean → fetch → `--ff-only` →
SHA; `ROOT_NOT_ON_MAIN` / `ROOT_DIRTY` / `ROOT_DIVERGED` decisions); hook execution absorbed from
`worktree-hooks.sh` (setup fail-fast, teardown best-effort, `lint`), discovered via
`config-block.sh`; reset-on-ensure for `ro-*`; `BRANCH_IN_USE` when the branch is checked out
elsewhere; `.gitignore` maintenance. `worktree-hooks.sh` itself stays untouched for v1 callers
until S20.

**DoD**
- [ ] `ensure --work`: creates from `origin/<base>`, reuses an existing worktree, runs setup
      hooks on every entry, reports `reused` / dirty / unpushed facts.
- [ ] `ensure --read`: detached at `origin/<ref>`, resets to current origin SHA on re-ensure,
      reports the SHA.
- [ ] Each root-freshness failure mode returns its decision code (three cases), and the happy
      path ff-updates and records the SHA.
- [ ] `gc` removes only `ro-*` older than max-age (default 7 days); an adversarial case proves an
      aged **work** worktree survives.
- [ ] Hook semantics match v1 `worktree-hooks.sh` (fail-fast / best-effort / lint; result-key
      mapping documented).
- [ ] `.gitignore` entry idempotent.

**Testing:** git-sandbox bats covering every subcommand and decision code; hook cases use
config-block fixtures; manual smoke: `ensure --read` against this repo, then `gc --max-age 0`.

### S5 — `parse.sh`

**Goal:** one parser for the shared body grammars, ending per-skill prompt parsing.

**Work:** subcommands over a file path, envelope out: `dod` (issue body → indexed bullets with
checkbox state + annotation per the `_shared/dod-annotations.md` closed set), `oq-links` (body →
`open-question-links:v1` entries with dispositions per `_shared/open-question-links.md`),
`phases` (plan body → phase list with kinds).

**DoD**
- [ ] `dod` parses every annotation form in the shared contract (one fixture per form);
      parse → re-render round-trips byte-identically.
- [ ] Unknown or stacked annotations return `DOD_MALFORMED` (never a crash or a guess).
- [ ] `oq-links` parses the shared contract's examples including all three dispositions; a body
      without the section returns `ok` with an empty list.
- [ ] `phases` parses well-formed lists and returns `PHASES_MALFORMED` on the malformed fixtures.

**Testing:** fixture bodies lifted from the `_shared` examples plus adversarial mutations;
envelope conformance on every output.

---

## Phase 1 — Evaluator pilot

### S6 — `prep-evaluator.sh`

**Goal:** the evaluator's complete facts block in one call ([architecture.md §4](architecture.md)).

**Work:** compose `gh-pr-gather.sh`, `gh-gather.sh` (each closing issue), `workspace.sh` (root
freshness + work ensure on the PR branch), `parse.sh dod`; pin gate config at the root SHA
(static-checks, test-target, escalation-labels, merge-policy); classify the CI rollup
(green / red / pending / none); compare the health-cache marker SHA; detect PR type
(epic-integration / story / standard) from base/head patterns; fetch repo merge config; surface
the self-review fact (PR author vs current user); emit `suggested_playbook`, `attention`,
`notices`; support `--refresh` (re-derives volatile facts without re-running hooks).

**DoD**
- [ ] Facts schema matches the [architecture.md §4](architecture.md) example (kept in sync in the
      same PR) and passes conformance.
- [ ] Fixtures: four CI states; cache hit and miss; merge-policy present and absent; story, epic
      and standard detection; closing-issue DoD parsed.
- [ ] Decision paths tested: `MARKER_AMBIGUOUS` (duplicate cache comments), `ROOT_*` propagation,
      `BRANCH_IN_USE`.
- [ ] `--refresh` re-derives PR state and CI without hook re-runs.
- [ ] Single-invocation budget asserted via shim call counts ([prd.md §9.2](prd.md)).

**Testing:** bats with shim fixtures per the DoD matrix; one documented **read-only** live smoke
against a real PR.

### S7 — Evaluator skill rewrite

**Goal:** `skills/evaluator/` replaces `github-pr-evaluator` behavior ([prd.md §5.5](prd.md)).

**Work:** router per [architecture.md §9](architecture.md); playbooks split per the §5 bar (an
evaluate spine plus merge/completion variants is the expectation — the final split is decided
against the facts and recorded in the PR); preserve renderings byte-compatibly: health-cache
comment, review comment, delivery-log append, handoff; all I/O via scripts directly.

**DoD**
- [ ] Router ≤ 150 lines, contains the visible routing table; playbook bodies contain no
      PR-type conditionals.
- [ ] Every artifact this skill writes diffs clean against the S1-captured v1 examples (schema
      level).
- [ ] Grep gates: zero `github-ops`, raw `gh` writes, `git show`, or old skill names under
      `skills/evaluator/`.
- [ ] Frontmatter model/effort pins carried verbatim from v1.
- [ ] Every operator gate in `specs/evaluator.md` is present, or its absence traces to a PRD §.
- [ ] Parity run recorded in `docs/specs/parity/evaluator.md`: standard approve + merge; story
      merge (delivery-log append + epic checkbox); red-CI rejection; `ask`-policy gate.

**Testing:** offline — routing-table fixtures (vector → playbook) and `--dry-run` persist
envelopes; live — the four parity scenarios on the sandbox.

### S8 — Pilot retro & pattern lock

**Goal:** correct the shared patterns while exactly one skill uses them.

**Work:** retro over S6/S7 — facts-schema gaps, envelope friction, playbook-granularity calls;
amend [architecture.md](architecture.md) §3–§5 content where the pilot contradicted it (anchors
stable); record the scale/no-scale decision.

**DoD**
- [ ] Retro appended to `docs/specs/baseline.md`.
- [ ] Architecture amendments landed; validators and census still green.
- [ ] Explicit operator go/no-go recorded for the remaining phases.

**Testing:** process step — re-run validators only.

---

## Phase 2 — Resolver

### S9 — `prep-resolver.sh`

**Goal:** resolver startup — v1's ~130 lines of prompt-side state assembly — in one call.

**Work:** state vector (labels → type; plan marker + SHA; fresh/continue mode from the six-row
prior-PR table); epic branch discovery + slug computation; story parent-epic search; branch
collision suffixing (`-vN`); phase facts via `parse.sh phases` + `dod`; open-question facts
(`parse.sh oq-links` joined with tracker states and native `blocked_by`) including the
in-scope-blocked hard-gate fact; audit read-workspace + work-workspace ensure per mode; test and
fast-check config pinned at root SHA; distiller input bundle staged to scratch; `suggested_playbook`;
`attention` (dirty, unpushed, ambiguous branch matches).

**DoD**
- [ ] One fixture per prior-PR state row (six) proving mode/vector derivation.
- [ ] Epic-branch discovery fixtures: zero, one, multiple matches (multiple → `AMBIGUOUS`).
- [ ] Collision fixture: existing `-v2` branch yields `-v3`.
- [ ] Blocked-OQ fixtures both ways: open tracker + `in-scope (blocked)` sets the hard-gate fact;
      a `question-decision:v1` comment (Tier 1) clears it.
- [ ] Distiller bundle is staged paths, never above-threshold inline bytes.
- [ ] Conformance + single-invocation call budget as S6.

**Testing:** shim bats per the matrix; read-only live smoke on a real epic and story issue.

### S10 — Resolver skill rewrite

**Goal:** `skills/resolver/` replaces `github-issue-resolver` behavior ([prd.md §5.4](prd.md)).

**Work:** router + playbooks `standard` / `epic` / `story` / `comment-only`, continue-mode
parameterized via facts; preserve DoD projection renderings, the review loop (review-loop
sub-agent), the retry ladder, state-distiller and fitness-audit dispatches (inputs are facts
paths/workspaces); multi-phase flow; re-route handoffs with `Why:`. The `§P-ID` scheme and
forced-read workaround are retired.

**DoD**
- [ ] Router ≤ 150 lines; exactly four playbooks; zero epic/story interleaving in any playbook
      (pattern grep committed as a validator).
- [ ] DoD projection annotations diff clean against S1 captures.
- [ ] A seeded in-scope-blocked issue is refused with the gate (live).
- [ ] Every gate/judgment step in `specs/resolver.md` present or PRD-justified.
- [ ] Grep gates and pins as S7.
- [ ] Parity runs recorded: fresh bug-fix end-to-end; continue-mode re-entry; comment-only;
      multi-phase tick projection.

**Testing:** offline routing + dry-run suites; the four live parity scenarios on the sandbox.

### S11 — Sub-agent exception unification

**Goal:** one typed-exception vocabulary across scripts and judgment sub-agents
([architecture.md §3, §8](architecture.md)).

**Work:** update the resolver-family sub-agent prompts (state-distiller, fitness audit,
test-selection, review-loop) to take workspace paths + staged files and return §3 codes; mark
`_shared/subagent-decision-signal.md` superseded-for-v2 (v1 planner/drafter still cite it —
removal happens in S20); align the question-status reader's `AMBIGUOUS`.

**DoD**
- [ ] No v2 sub-agent prompt takes a ref as input or cites the old signal doc.
- [ ] A drift-check validator compares prompt code sets to [architecture.md §3](architecture.md).
- [ ] Old signal doc carries the superseded breadcrumb; v1 callers still function.
- [ ] Resolver live smoke re-run green (distiller + audit round-trip).

**Testing:** prompt validators + the smoke re-run.

---

## Phase 3 — Planner & drafter

### S12 — `prep-planner.sh`

**Goal:** planner facts with read-workspace grounding ([prd.md §5.3, §8.4](prd.md)).

**Work:** gather issue + research/plan markers (revise detection); the plan-ref selection table
moves into the script (default branch / epic branch / PR head) with a read-workspace ensure at
the result; epic facts (story list + states, delivery-log and epic-plan staging); JIT-story
facts; revise facts (PR phase tracker); **the deterministic question-registry search** (label +
keyword candidates in facts — the S1 bug (a) fix); grounding-doc inventory at the pinned SHA.

**DoD**
- [ ] Plan-ref fixtures: single issue no-PR, single issue open-PR, story-under-epic, epic — each
      yields the expected ref and workspace SHA fact.
- [ ] The seeded tracker-match fixture returns the matching question issue in
      `open_question_candidates` (bug (a) regression).
- [ ] Revise facts include prior plan body path + phase tracker.
- [ ] Conformance + call budget as S6.

**Testing:** shim bats including the seeded OQ case; read-only live smoke on an epic story.

### S13 — Planner skill rewrite

**Goal:** `skills/planner/` replaces `github-issue-planner` behavior ([prd.md §5.3](prd.md)).

**Work:** router + playbooks `single` / `epic` / `story-jit` / `revise`; all grounding reads are
ordinary Read/Grep in the read workspace; plan schema and reviewer references carried; handoff
renderings gain the combined epic + story open-questions worked example (bug (b) fix); the plan
comment's planned-at SHA is the workspace SHA fact.

**DoD**
- [ ] Plan comment diffs clean against S1 captures; planned-at SHA equals the facts workspace SHA
      in parity runs.
- [ ] Zero ref arithmetic in prompts (grep).
- [ ] Open-question lines render in every handoff shape; the exact bug-(b) composite scenario has
      a rendering example and a parity check.
- [ ] Playbook rule (falsifiable): an OQ may be recorded "(not filed)" only when the facts
      candidate list is empty or each candidate was explicitly rejected; parity-checked (bug (a)).
- [ ] Gates from `specs/planner.md` present; grep gates + pins; parity recorded: plan-new epic,
      JIT story, revise.

**Testing:** offline routing + rendering fixtures; the three live parity scenarios.

### S14 — `prep-drafter.sh`

**Goal:** drafter facts.

**Work:** repo context (issue templates, labels, PRD/doc presence); OQ marker config block +
heuristic cue list; revise-mode gather (issue + plan pointer + PR list); epic-revise gather
(stories + states); question-registry candidate search for detected OQs (search-before-file);
staging conventions.

**DoD**
- [ ] Fixtures derive the vector for new, revise, and epic-revise correctly.
- [ ] OQ candidate search fixtures: match and no-match.
- [ ] Template/label inventory correct on present/absent fixtures.
- [ ] Conformance + call budget.

**Testing:** shim bats; read-only live smoke.

### S15 — Drafter skill rewrite

**Goal:** `skills/drafter/` replaces `github-issue-drafter` behavior ([prd.md §5.1](prd.md)).

**Work:** router + playbooks `new` / `revise` / `epic-split` / `question`; judgment content
carried (classification cues, PRD tension detection, adversarial review loop, story coalescing);
open-question dispositions per `_shared`; filing via `gh-persist.sh` with native dependencies.

**DoD**
- [ ] Filed bodies are template-conformant; `open-question-links:v1` sections diff clean against
      S1 captures.
- [ ] Epic split files stories and patches the epic's links (parity).
- [ ] Falsifiable playbook rule: an unresolved source-doc OQ is never absorbed without a filed or
      matched tracker issue + disposition; parity-checked with a seeded doc OQ.
- [ ] Gates from `specs/drafter.md` present; grep gates + pins; parity recorded: new bug draft,
      epic split, revise, question.

**Testing:** offline routing + dry-run suites; the four live parity scenarios.

---

## Phase 4 — Researcher

### S16 — Researcher rewrite

**Goal:** `skills/researcher/` — the thinnest cutover ([prd.md §5.2](prd.md)).

**Work:** `prep-researcher.sh` (gather + dossier-marker detection + manifest/doc inventory
list); router with broad/targeted/revise as facts-selected modes (single playbook unless the §5
bar says otherwise — decided at build); web-research loop and validator carried unchanged.

**DoD**
- [ ] Dossier comment diffs clean against S1 captures; the decline gate is preserved (parity: a
      no-currency-risk issue declines).
- [ ] Prep fixtures: marker present/absent; manifests found/missing.
- [ ] Grep gates + pins; parity recorded: broad run on a currency-risky issue, decline case.

**Testing:** shim bats; the two live parity scenarios.

---

## Phase 5 — Standalone tools

### S17 — Setup rewrite

**Goal:** `skills/setup/` with PR landing ([prd.md §6.1, §8.2](prd.md)).

**Work:** rename from `github-pipeline-setup`; inventory/detect/propose/validate flows carried
(all block I/O via `config-block.sh`); writes happen in a work workspace and land as a PR whose
body summarizes the block diffs; merge-policy proposal includes a `docs: auto` style option;
worktree hook-block authoring retained, linted via `workspace.sh lint`.

**DoD**
- [ ] Written blocks are byte-identical to v1 canonical forms (fixture diff).
- [ ] Live sandbox run: setup produces a PR; `git -C <root> status` stays clean throughout.
- [ ] Legacy `pr-evaluator-health-checks` split/migration preserved (fixture).
- [ ] `disable-model-invocation: true` retained; grep gates; parity recorded.

**Testing:** offline config-block fixtures; one live sandbox run.

### S18 — Question pair rewrite

**Goal:** `skills/question-sweep/` (renamed from `open-questions`) + `skills/question-resolver/`
([prd.md §6.2, §6.3](prd.md)).

**Work:** `prep-question-sweep.sh` (question-issue registry gather with Tier-1 status join; doc
candidate list from config block + heuristic cues); `prep-question-resolver.sh` (gather +
decision marker + native `blocking` list); sweep apply-mode doc edits land via PR; decision
recording and close/reopen stay on `gh-persist.sh` with reentrancy preserved.

**DoD**
- [ ] Tier-1 status join fixtures: closed / decision-marker present / still open (→ Tier-2
      needed flag).
- [ ] Sweep apply mode produces a PR; root stays clean.
- [ ] `question-decision:v1` comment diffs clean against S1 captures; reentrant revise
      (post-new-then-delete-old) parity-tested.
- [ ] New names used throughout the new dirs; `disable-model-invocation` retained; grep gates;
      parity recorded: sweep report-only, sweep apply, resolve + close.

**Testing:** shim bats for both preps; the three live parity scenarios.

### S19 — Doc-reviewer rewrite

**Goal:** `skills/doc-reviewer/` aligned to the router shape ([prd.md §6.4](prd.md)).

**Work:** name unchanged; guide resolution and review lenses carried; apply mode edits in a work
workspace and lands via PR; no prep script (nothing to gather — assert that stays true).

**DoD**
- [ ] Review report structure preserved (parity on one sandbox doc).
- [ ] Apply mode produces a PR; root stays clean.
- [ ] `disable-model-invocation` retained; grep gates.

**Testing:** live parity on one doc; offline n/a beyond validators.

---

## Phase 6 — Retirement

### S20 — v1 removal & repo truth

**Goal:** delete what the cutovers obsoleted; make the repo describe v2.

**Work:** remove `agents/github-ops.md`, `scripts/worktree-hooks.sh`, all v1 skill directories,
and the superseded internal `_shared` docs (`subagent-decision-signal.md`; the mechanics half of
`worktree-lifecycle.md` — external block formats stay); sweep old names and stale
`/github-pipeline:<old-name>` strings; update `README.md`, `plugin.json`, `marketplace.json`
(version bump), the authoring guides where they name old skills, and this repo's `CLAUDE.md`
(rewritten for v2, including the extended validator greps: old names, `git show` in `skills/`,
raw `gh` writes in `skills/`); record the final census diff against the S1 baseline in
`docs/specs/baseline.md` with every dropped token accounted for.

**DoD**
- [ ] Zero grep hits repo-wide for: old skill names, `github-ops`, `worktree-hooks`.
- [ ] Census diff reviewed; every removed token is on the deliberate-retirement list.
- [ ] Full offline suite green; shellcheck clean; manifests parse; version bumped.
- [ ] Fresh end-to-end conveyor run on the sandbox — draft → research (decline acceptable) →
      plan → resolve → evaluate → merge — with every handoff schema-valid.
- [ ] `CLAUDE.md` describes only the v2 architecture; guides name only new skills.

**Testing:** the end-to-end sandbox run is the test; all validators re-run and recorded.
