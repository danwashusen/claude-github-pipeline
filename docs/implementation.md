# github-pipeline v2 — Implementation Plan

Step-by-step migration from v1 to the [architecture.md](architecture.md) design, preserving the
[prd.md](prd.md) product truth. Steps have stable IDs (`S1`–`S21`) — cite them, never renumber
(IDs are labels, not positions: `S21` was added after initial authoring and runs in Phase 0).
Each step is sized to be one issue and one PR.

## How to use this plan

- One step → one GitHub issue (drafted via the pipeline's own `drafter` where practical) → one
  PR into this repo's `main`. This repo runs the same write-protected-`main` model the plugin
  assumes ([prd.md §8](prd.md)); nothing lands without a PR.
- A step is done only when every DoD box is ticked; DoD is verified in PR review, not assumed.
- **v2 is written from scratch, never edited down from v1.** v1 skill directories and scripts
  are frozen once S1 captures them — read-only behavioral references until S20 deletes them (a
  v1 hotfix, if ever needed, is its own PR and triggers an S1 spec refresh). A cutover step
  authors `skills/<name>/` fresh from its S1 spec, the PRD, and
  [architecture.md §9](architecture.md); copying v1 `SKILL.md` prose into the new directory and
  whittling it down is the failure mode this plan exists to avoid. Only two classes of v1 text
  are carried verbatim: the [prd.md §7](prd.md)-frozen artifact renderings (byte-compatible by
  requirement) and the reference prompts a step explicitly marks as carried (e.g. S10's
  sub-agent prompts, S16's web-research loop).
- **Global DoD** (applies to every step, in addition to its own): `python3 -m compileall -q
  scripts/` succeeds; `python3 tests/run.py` green from S2 onward — for steps that touch
  scripts, on **both macOS and Linux** (container invocation documented in `tests/README.md`);
  `shellcheck` clean for any v1 `*.sh` still present; `.claude-plugin/*.json` parses
  (`python3 -m json.tool`); for skill-cutover steps (S7, S10, S13, S15–S19) the contract-token
  census is re-run against the S1 baseline and any count drop is accounted for on a
  deliberate-retirement note in the PR; [architecture.md](architecture.md) / [prd.md](prd.md)
  amended in the same PR when the step legitimately changed a contract (content edits only —
  §-anchors are stable).
- **Order:** the table below. After S8 (pattern lock) the remaining tracks are parallelizable;
  before it, everything is deliberately serial so the shared patterns are corrected while only
  one skill uses them.

| Step | After | Step | After |
|---|---|---|---|
| S1 baseline & specs | — | S11 sub-agent exceptions | S10 |
| S2 test harness | — | S12 prep-planner | S8 |
| S3 lib + envelope | S2 | S13 planner skill | S12, S11 |
| S4 workspace.py | S21 | S14 prep-drafter | S8 |
| S5 parse.py | S3 | S15 drafter skill | S14 |
| S6 prep-evaluator | S4, S5 | S16 researcher | S8 |
| S7 evaluator skill | S6, S1 | S17 setup | S8, S4 |
| S8 pilot retro & lock | S7 | S18 question pair | S8, S5 |
| S9 prep-resolver | S8 | S19 doc-reviewer | S8 |
| S10 resolver skill | S9 | S20 retirement | all other steps |
| S21 executor ports | S3 | — | — |

## The sandbox repo

Live smoke and parity runs use a disposable consuming repo (**the sandbox**) — a real GitHub
repository seeded with: the pipeline labels (`epic`, `story`, `question`, `planned`,
`researched`, `audience:*`), one epic with two stories, one plain bug issue, one question issue,
grounding docs (`docs/prd.md`, `docs/architecture.md`), the config marker blocks, and a minimal
CI workflow whose pass/fail is controllable per branch (e.g. it fails when a marker filename is
present). S2 authors `tests/SANDBOX.md` with the exact creation (`gh repo create … --private`)
and seeding steps, creates the repo, and records its URL there. Offline tests never touch it;
parity runs always do.

## The parity protocol

Referenced by every skill-cutover step as "parity run", recorded per skill in
`docs/specs/parity/<skill>.md`:

1. Construct the target state in the sandbox (issue/PR in the shape the skill expects), or use
   twin targets for destructive flows. For flows that mutate a shared parent (epic checkbox,
   delivery log, sandbox `main`), twin the parent subtree too (e.g. two single-story epics), not
   just the target PR/issue.
2. Run the **v1** skill in one session. Capture: every GitHub write (fetch bodies afterward),
   every gate asked, the handoff text, and the session's rough turn count.
3. Reset (or switch to the twin) and run the **v2** skill on the same state.
4. Compare: persisted artifacts are **schema-identical** — same marker line, same
   section/heading set and order, same structured fields; free prose may differ; confirmed by
   cross-consumption (a v1 reader consumes the v2 artifact and vice versa, [prd.md §7](prd.md)).
   The same genuine decisions were gated; the handoff validates against the shared schema;
   startup performed at most one state-assembly call ([prd.md §9.2](prd.md)).
5. Divergences are listed; each must trace to a PRD requirement (e.g. the §5.3 planner fixes) or
   be filed as a defect. Unexplained divergence fails the run.

---

## Phase 0 — Foundations

### S1 — Baseline capture & per-skill functional specs

**Goal:** freeze what v1 does, as the measurable spec for parity ([prd.md §9.5, §10](prd.md)).

**Work:** For each of the nine skills, extract `docs/specs/<skill>.md` from the v1 `SKILL.md` +
references: artifacts written/read, operator gates, judgment steps, deterministic steps
(candidate script work), invariants with their *why*, and known bugs. Record
`docs/specs/baseline.md`: v1 line counts and the contract-token census output (command +
verbatim result); capture each persisted-artifact example **verbatim** under
`docs/specs/examples/` (with its source link), including one sample v1 handoff per pipeline
skill. Fold in the two known planner
bugs as falsifiable spec lines: (a) an open question with an existing tracker issue must never be
recorded as "(not filed)"; (b) the handoff's open-questions line must render in combined
epic + story sessions.

**DoD**
- [x] `docs/specs/` contains nine per-skill specs plus `baseline.md`.
- [x] Every [prd.md §7](prd.md) artifact has at least one spec naming it as writer and one as
      reader (cross-reference table in `baseline.md`).
- [x] Census command and verbatim output committed.
- [x] Every [prd.md §7](prd.md) artifact has a verbatim example under `docs/specs/examples/`,
      including one v1 handoff per pipeline skill.
- [x] Both planner bugs appear as falsifiable requirements in `specs/planner.md`.
- [x] Each spec was adversarially re-read against its source `SKILL.md` in an isolated session
      or sub-agent; misses were folded in and noted.

**Testing:** documentation step — validation is the census run plus the adversarial re-read; no
harness involvement.

### S2 — Offline test harness

**Goal:** the [architecture.md §10](architecture.md) harness exists and provably intercepts.

**Work:** `tests/run.py` (stdlib `unittest` discovery — no third-party framework, nothing to
vendor or install); `tests/shim/gh` (a Python executable named `gh`) replaying fixtures from
`tests/fixtures/<case>/` keyed on exact argv (helpful diff on miss); a git-sandbox helper
(`mk_origin` / `mk_clone` in temp dirs with cleanup); `tests/README.md` (fixture layout, adding
a case, and the Linux container invocation for dual-platform runs); `tests/SANDBOX.md` (live
sandbox seeding).

**DoD**
- [x] `python3 tests/run.py` discovers and runs all `test_*.py`, exits non-zero on any failure.
- [x] Shim self-test proves interception: a probe calling `gh` receives fixture bytes;
      un-fixtured argv fails the test loudly.
- [x] Runs make no network calls and never invoke the real `gh` (asserted, e.g. via a poisoned
      `PATH` sentinel).
- [x] Git-sandbox helper creates origin + clone and cleans up on exit, pass or fail.
- [x] The suite passes on macOS and on Linux (container or host), per the documented invocation.
- [x] `tests/README.md` and `tests/SANDBOX.md` exist and suffice to add a case / seed the
      sandbox / run on Linux without reading harness source.
- [x] The sandbox repo exists, seeded per `tests/SANDBOX.md`, and its URL is recorded there.

**Testing:** the harness tests itself: shim hit/miss cases, sandbox create/teardown, run.py
failure propagation.

### S3 — `scripts/pipelib/` + the envelope

**Goal:** the [architecture.md §3](architecture.md) primitives every script shares.

**Work:** a stdlib-only package: envelope emit (`ok` / `needs_decision` / `notice`), spill
helper (threshold env: new name honored, legacy `GH_OPS_INLINE_THRESHOLD_BYTES` fallback,
default 25600), sha256 helper, the closed decision-code constants, and the portable subprocess
runner (argument lists only, never `shell=True`; `encoding="utf-8"` pinned; `git`/`gh` the only
spawnable binaries — [architecture.md §1](architecture.md)) and the separate hook executor only
`workspace.py` imports (the §1 carve-out); plus reusable unittest assertion helpers for envelope
conformance (status validity, decision payload shape, `*_mode`/`*_path`
pairing, exit-code contract) that all later suites import.

**DoD**
- [x] Every pipelib function has a unit test.
- [x] The subprocess runner refuses string commands and non-`git`/`gh` binaries by construction
      and pins UTF-8; the hook executor is a separate, explicitly-named entry point (tested).
- [x] A `gh` authentication failure surfaces as an `AUTH_REQUIRED` decision (fixture).
- [x] Conformance assertions exist and are importable by other suites (used by a toy script
      end-to-end test).
- [x] Threshold precedence tested: new var, legacy var, default.
- [x] Decision-code constants exactly match [architecture.md §3](architecture.md); a drift-check
      test compares the doc list to the lib list.

**Testing:** `tests/test_pipelib.py` + the toy-script end-to-end envelope emission case.

### S21 — GitHub executor ports (runs in Phase 0)

**Goal:** the four v1 bash executors become Python modules under the §3 envelope
([architecture.md §7](architecture.md)); the v1 `.sh` files stay untouched for v1 callers until
S20.

**Work:** port `gh-gather.sh` → `gh_gather.py`, `gh-pr-gather.sh` → `gh_pr_gather.py`,
`gh-persist.sh` → `gh_persist.py`, `config-block.sh` → `config_block.py`, preserving each
behavior contract exactly, re-expressed in §3 envelope terms: thread pagination, marker
discovery + `marker_comment_count`, threshold spill, dependency capability-gating
(`DEPS_UNSUPPORTED` notice + retry-without), the empty-body gate, post-new-before-delete-old,
close/reopen idempotency, `body_sha256` receipts, canonical config-block forms and statuses.

**DoD**
- [x] Each port emits a conformant envelope for its happy path and every decision/notice it can
      produce (fixture per case).
- [x] Invariant tests: empty staged file → `EMPTY_BODY_FILE`; duplicate markers surfaced per
      contract; deps-unsupported → notice + retry-without; comment replacement posts before
      delete.
- [x] `config_block.py` round-trips the v1 canonical block forms byte-identically
      (`read`/`list`/`upsert`/`remove` semantics preserved; fixtures lifted from v1 examples).
- [x] v1 `.sh` files untouched and still shellcheck-clean.

**Testing:** shim-backed unit tests per the DoD matrix; one documented read-only live smoke for
the two gathers.

### S4 — `workspace.py`

**Goal:** the [architecture.md §6](architecture.md) lifecycle owner.

**Work:** subcommands `ensure --work <branch> --base <ref>` / `ensure --read <ref>` /
`remove --work <branch>` (teardown hooks best-effort, then `git worktree remove`; dirty or
unpushed state → decision) / `gc [--max-age]` / `root-status` / `lint <setup|teardown>`;
root-freshness protocol (on-`main` + clean → fetch → `--ff-only` → SHA; `ROOT_NOT_ON_MAIN` /
`ROOT_DIRTY` / `ROOT_DIVERGED` decisions); hook execution absorbed from `worktree-hooks.sh`
(setup fail-fast, teardown best-effort, `lint`), discovered via `config_block.py`; fetch +
reset-on-ensure for `ro-*`; `BRANCH_IN_USE` when the branch is checked out elsewhere;
`.gitignore` maintenance. `worktree-hooks.sh` itself stays untouched for v1 callers
until S20.

**DoD**
- [x] `ensure --work`: creates from `origin/<base>`, reuses an existing worktree, runs setup
      hooks on every entry, reports `reused` / dirty / unpushed facts.
- [x] `ensure --read`: detached at `origin/<ref>`, fetches then resets to current origin SHA on
      re-ensure, reports the SHA.
- [x] `remove --work`: runs teardown hooks, then removes; dirty or unpushed state returns a
      decision instead of removing (both cases tested).
- [x] Each root-freshness failure mode returns its decision code (three cases), and the happy
      path ff-updates and records the SHA.
- [x] `gc` removes only `ro-*` older than max-age (default 7 days); an adversarial case proves an
      aged **work** worktree survives.
- [x] Hook semantics match v1 `worktree-hooks.sh` (fail-fast / best-effort / lint; result-key
      mapping documented).
- [x] `.gitignore` entry idempotent.

**Testing:** git-sandbox unit tests covering every subcommand and decision code; hook cases use
config-block fixtures; manual smoke: `ensure --read` against this repo, then `gc --max-age 0`.

### S5 — `parse.py`

**Goal:** one parser for the shared body grammars, ending per-skill prompt parsing.

**Work:** subcommands over a file path, envelope out: `dod` (issue body → indexed bullets with
checkbox state + annotation per the `_shared/dod-annotations.md` closed set), `oq-links` (body →
`open-question-links:v1` entries with dispositions per `_shared/open-question-links.md`),
`phases` (plan body → phase list with kinds). Plus a render mode (`dod --render`) that re-emits
the bullets byte-identically from the parsed form — the round-trip DoD exercises it.

**DoD**
- [x] `dod` parses every annotation form in the shared contract (one fixture per form);
      parse → re-render round-trips byte-identically.
- [x] Unknown or stacked annotations return `DOD_MALFORMED` (never a crash or a guess).
- [x] `oq-links` parses the shared contract's examples including all three dispositions; a body
      without the section returns `ok` with an empty list.
- [x] `phases` parses well-formed lists and returns `PHASES_MALFORMED` on the malformed fixtures.

**Testing:** fixture bodies lifted from the `_shared` examples plus adversarial mutations;
envelope conformance on every output.

---

## Phase 1 — Evaluator pilot

### S6 — `prep_evaluator.py`

**Goal:** the evaluator's complete facts block in one call ([architecture.md §4](architecture.md)).

**Work:** compose `gh_pr_gather.py`, `gh_gather.py` (each closing issue), `workspace.py` (root
freshness + work ensure on the PR branch), `parse.py dod`; pin gate config at the root SHA
(static-checks, test-target, escalation-labels, merge-policy); classify the CI rollup
(green / red / pending / none); compare the health-cache marker SHA; detect PR type
(epic-integration / story / standard) from base/head patterns; fetch repo merge config; surface
the self-review fact (PR author vs current user); emit `suggested_playbook`, `attention`,
`notices`; support `--refresh` (re-derives volatile facts without re-running hooks).

**DoD**
- [x] Facts schema matches the [architecture.md §4](architecture.md) example (kept in sync in the
      same PR) and passes conformance.
- [x] Fixtures: four CI states; cache hit and miss; merge-policy present and absent; story, epic
      and standard detection; closing-issue DoD parsed.
- [x] Decision paths tested: `MARKER_AMBIGUOUS` (duplicate cache comments), `ROOT_*` propagation,
      `BRANCH_IN_USE`.
- [x] `--refresh` re-derives PR state and CI without hook re-runs.
- [x] Single-invocation budget asserted via shim call counts ([prd.md §9.2](prd.md)).

**Testing:** shim-backed unit tests per the DoD matrix; one documented **read-only** live smoke
against a real PR.

### S7 — Evaluator skill rewrite

**Goal:** `skills/evaluator/` replaces `github-pr-evaluator` behavior ([prd.md §5.5](prd.md)).

**Work:** router per [architecture.md §9](architecture.md); playbooks split per the §5 bar (an
evaluate spine plus merge/completion variants is the expectation — the final split is decided
against the facts and recorded in the PR); preserve renderings byte-compatibly: health-cache
comment, review comment, delivery-log append, handoff; all I/O via scripts directly.

**DoD**
- [x] Router ≤ 150 lines, contains the visible routing table; playbook bodies contain no
      PR-type conditionals.
- [x] Every artifact this skill writes diffs clean against the S1-captured v1 examples (schema
      level).
- [x] Grep gates: zero `github-ops`, raw `gh` writes, `git show`, or old skill names under
      `skills/evaluator/`.
- [x] Frontmatter model/effort pins carried verbatim from v1.
- [x] Every operator gate in `specs/evaluator.md` is present, or its absence traces to a PRD §.
- [x] Parity run recorded in `docs/specs/parity/evaluator.md`: standard approve + merge; story
      merge (delivery-log append + epic checkbox); red-CI rejection; `ask`-policy gate.
- [x] Router + largest playbook line count recorded there and is at most half the v1 `SKILL.md`
      count in `baseline.md` ([prd.md §10](prd.md)).

**Testing:** offline — routing-table fixtures (vector → playbook) and `--dry-run` persist
envelopes; live — the four parity scenarios on the sandbox.

### S8 — Pilot retro & pattern lock

**Goal:** correct the shared patterns while exactly one skill uses them.

**Work:** retro over S6/S7 — facts-schema gaps, envelope friction, playbook-granularity calls;
amend [architecture.md](architecture.md) §3–§5 content where the pilot contradicted it (anchors
stable); record the go/no-go decision.

**DoD**
- [x] Retro appended to `docs/specs/baseline.md`.
- [x] Architecture amendments landed; validators and census still green.
- [x] Operator go/no-go recorded with criteria — **go** requires the S7 parity run recorded
      with zero unexplained divergences, architecture amendments landed, and validators + census
      green; **no-go** names the blocking finding and its remediation step.

**Testing:** process step — re-run validators only.

---

## Phase 2 — Resolver

### S9 — `prep_resolver.py`

**Goal:** resolver startup — v1's ~130 lines of prompt-side state assembly — in one call.

**Work:** state vector (labels → type; plan marker + SHA; fresh/continue mode from the prior-PR
state table as captured in `specs/resolver.md`); epic branch discovery + slug computation; story parent-epic search; branch
collision suffixing (`-vN`); phase facts via `parse.py phases` + `dod`; open-question facts
(`parse.py oq-links` joined with tracker states and native `blocked_by`) including the
in-scope-blocked hard-gate fact; audit read-workspace + work-workspace ensure per mode; test and
fast-check config pinned at root SHA; distiller input bundle staged to scratch; `suggested_playbook`;
`attention` (dirty, unpushed, ambiguous branch matches).

**DoD**
- [x] One fixture per row of the v1 prior-PR table (as captured in `specs/resolver.md`),
      proving mode/vector derivation.
- [x] Epic-branch discovery fixtures: zero, one, multiple matches (multiple → `AMBIGUOUS`).
- [x] Collision fixture: existing `-v2` branch yields `-v3`.
- [x] Blocked-OQ fixtures both ways: open tracker + `in-scope (blocked)` sets the hard-gate fact;
      a `question-decision:v1` comment (Tier 1) clears it.
- [x] Distiller bundle is staged paths, never above-threshold inline bytes.
- [x] Conformance + single-invocation call budget as S6.

**Testing:** shim-backed unit tests per the matrix; read-only live smoke on a real epic and story issue.

### S10 — Resolver skill rewrite

**Goal:** `skills/resolver/` replaces `github-issue-resolver` behavior ([prd.md §5.4](prd.md)).

**Work:** router + playbooks `standard` / `epic` / `story` / `comment-only`, continue-mode
parameterized via facts; preserve DoD projection renderings, the review loop (review-loop
sub-agent), the retry ladder, state-distiller and fitness-audit dispatches (inputs are facts
paths/workspaces); multi-phase flow; re-route handoffs with `Why:`. The `§P-ID` scheme and
forced-read workaround are retired.

**DoD**
- [x] Router ≤ 150 lines; exactly four playbooks; zero epic/story interleaving in any playbook
      (pattern grep committed as a validator).
- [x] DoD projection annotations diff clean against S1 captures.
- [x] A seeded in-scope-blocked issue is refused with the gate (live).
- [x] Every gate/judgment step in `specs/resolver.md` present or PRD-justified.
- [x] Grep gates and pins as S7.
- [x] Parity runs recorded: fresh bug-fix end-to-end; continue-mode re-entry; comment-only;
      multi-phase tick projection.
- [x] Router + largest playbook line count recorded in `docs/specs/parity/resolver.md` and is
      at most half the v1 `SKILL.md` count in `baseline.md` ([prd.md §10](prd.md)).

**Testing:** offline routing + dry-run suites; the four live parity scenarios on the sandbox.

### S11 — Sub-agent exception unification

**Goal:** one typed-exception vocabulary across scripts and judgment sub-agents
([architecture.md §3, §8](architecture.md)).

**Work:** converge the resolver-family sub-agent prompts (state-distiller, fitness audit,
test-selection, review-loop) on the §3 return vocabulary — path inputs landed in S10; mark
`_shared/subagent-decision-signal.md` superseded-for-v2 (v1 planner/drafter still cite it —
removal happens in S20). The question-status reader converges in S18 with the rest of the
question pair.

**DoD**
- [x] No v2 sub-agent prompt takes a ref as input or cites the old signal doc.
- [x] A drift-check validator compares prompt code sets to
      [architecture.md §3](architecture.md); this committed validator binds later prompt authors
      (S13, S15, S16, S18).
- [x] Old signal doc carries the superseded breadcrumb; v1 callers still function.
- [x] Resolver live smoke re-run green (distiller + audit round-trip).

**Testing:** prompt validators + the smoke re-run.

---

## Phase 3 — Planner & drafter

### S12 — `prep_planner.py`

**Goal:** planner facts with read-workspace grounding ([prd.md §5.3, §8.4](prd.md)).

**Work:** gather issue + research/plan markers (revise detection); the plan-ref selection table
moves into the script (default branch / epic branch / PR head) with a read-workspace ensure at
the result; epic facts (story list + states, delivery-log and epic-plan staging); JIT-story
facts; revise facts (PR phase tracker); **the deterministic question-registry search** (label +
keyword candidates in facts — the S1 bug (a) fix); grounding-doc inventory at the pinned SHA.

**DoD**
- [x] Plan-ref fixtures: single issue no-PR, single issue open-PR, story-under-epic, epic — each
      yields the expected ref and workspace SHA fact.
- [x] The seeded tracker-match fixture returns the matching question issue in
      `open_question_candidates` (bug (a) regression).
- [x] Revise facts include prior plan body path + phase tracker.
- [x] Conformance + call budget as S6.

**Testing:** shim-backed unit tests including the seeded OQ case; read-only live smoke on an epic story.

### S13 — Planner skill rewrite

**Goal:** `skills/planner/` replaces `github-issue-planner` behavior ([prd.md §5.3](prd.md)).

**Work:** router + playbooks `single` / `epic` / `story-jit` / `revise`; all grounding reads are
ordinary Read/Grep in the read workspace; plan schema and reviewer references carried; handoff
renderings gain the combined epic + story open-questions worked example (bug (b) fix); the plan
comment's planned-at SHA is the workspace SHA fact.

**DoD**
- [x] Plan comment diffs clean against S1 captures; planned-at SHA equals the facts workspace SHA
      in parity runs.
- [x] Zero ref arithmetic in prompts (grep).
- [x] Open-question lines render in every handoff shape; the exact bug-(b) composite scenario has
      a rendering example and a parity check.
- [x] Playbook rule (falsifiable): an OQ may be recorded "(not filed)" only when the facts
      candidate list is empty or each candidate was explicitly rejected; parity-checked (bug (a)).
- [x] Gates from `specs/planner.md` present; grep gates + pins; parity recorded: plan-new
      single issue, plan-new epic, JIT story, revise.
- [x] Router + largest playbook line count recorded in `docs/specs/parity/planner.md` and is at
      most half the v1 `SKILL.md` count in `baseline.md` ([prd.md §10](prd.md)).

**Testing:** offline routing + rendering fixtures; the four live parity scenarios.

### S14 — `prep_drafter.py`

**Goal:** drafter facts.

**Work:** repo context (issue templates, labels, PRD/doc presence); OQ marker config block +
heuristic cue list; revise-mode gather (issue + plan pointer + PR list); epic-revise gather
(stories + states); question-registry candidate search for detected OQs (search-before-file);
staging conventions.

**DoD**
- [x] Fixtures derive the vector for new, revise, and epic-revise correctly.
- [x] OQ candidate search fixtures: match and no-match.
- [x] Template/label inventory correct on present/absent fixtures.
- [x] Conformance + call budget.

**Testing:** shim-backed unit tests; read-only live smoke.

### S15 — Drafter skill rewrite

**Goal:** `skills/drafter/` replaces `github-issue-drafter` behavior ([prd.md §5.1](prd.md)).

**Work:** router + playbooks `new` / `revise` / `epic-split` / `question`; judgment content
carried (classification cues, PRD tension detection, adversarial review loop, story coalescing);
open-question dispositions per `_shared`; filing via `gh_persist.py` with native dependencies.

**DoD**
- [x] Filed bodies are template-conformant; `open-question-links:v1` sections diff clean against
      S1 captures.
- [x] Epic split files stories and patches the epic's links (parity).
- [x] Falsifiable playbook rule: an unresolved source-doc OQ is never absorbed without a filed or
      matched tracker issue + disposition; parity-checked with a seeded doc OQ.
- [x] Gates from `specs/drafter.md` present; grep gates + pins; parity recorded: new bug draft,
      epic split, revise, question.
- [x] Router + largest playbook line count recorded in `docs/specs/parity/drafter.md` and is at
      most half the v1 `SKILL.md` count in `baseline.md` ([prd.md §10](prd.md)).

**Testing:** offline routing + dry-run suites; the four live parity scenarios.

---

## Phase 4 — Researcher

### S16 — Researcher rewrite

**Goal:** `skills/researcher/` — the thinnest cutover ([prd.md §5.2](prd.md)).

**Work:** `prep_researcher.py` (gather + dossier-marker detection + manifest/doc inventory
list); router with broad/targeted/revise as facts-selected modes (single playbook unless the §5
bar says otherwise — decided at build); web-research loop and validator carried unchanged.

**DoD**
- [x] Dossier comment diffs clean against S1 captures; the decline gate is preserved (parity: a
      no-currency-risk issue declines).
- [x] Prep fixtures: marker present/absent; manifests found/missing.
- [x] Grep gates + pins; parity recorded: broad run on a currency-risky issue, decline case,
      revise of an existing dossier.
- [x] Router + largest playbook line count recorded in `docs/specs/parity/researcher.md` and is
      at most half the v1 `SKILL.md` count in `baseline.md` ([prd.md §10](prd.md)).

**Testing:** shim-backed unit tests; the three live parity scenarios.

---

## Phase 5 — Standalone tools

### S17 — Setup rewrite

**Goal:** `skills/setup/` with operator-gated PR landing ([prd.md §6.1, §8.2](prd.md)).

**Work:** rename from `github-pipeline-setup`; inventory/detect/propose/validate flows carried
(all block I/O via `config_block.py`); writes are staged in a work workspace, with the landing
(commit + push + PR whose body summarizes the block diffs) offered as an explicit final gate per
[prd.md §8.2](prd.md); merge-policy proposal includes a `docs: auto` style option; worktree
hook-block authoring retained, linted via `workspace.py lint`.

**DoD**
- [x] Written blocks are byte-identical to v1 canonical forms (fixture diff).
- [x] Live sandbox run (landing approved): PR opened with the block-diff summary;
      `git -C <root> status` clean throughout. — PASS 2026-07-20, PR #91 (parity/setup.md Scenario 1).
- [x] Live sandbox run (landing declined): no commit/push/PR occurs; the summary reports the
      workspace path and ready-to-run landing commands. — PASS 2026-07-22 (parity/setup.md Scenario 2).
- [x] Legacy `pr-evaluator-health-checks` split/migration preserved (fixture).
- [x] `disable-model-invocation: true` retained; grep gates; parity recorded. — adjudicated: setup
      stays model-invocable (no key; v1 never had it — parity/setup.md "ADJUDICATION RECORD"); grep
      gates + both live parity legs recorded.

**Testing:** offline config-block fixtures; one live sandbox run.

### S18 — Question pair rewrite

**Goal:** `skills/question-sweep/` (renamed from `open-questions`) + `skills/question-resolver/`
([prd.md §6.2, §6.3](prd.md)).

**Work:** `prep_question_sweep.py` (question-issue registry gather with Tier-1 status join; doc
candidate list from config block + heuristic cues); `prep_question_resolver.py` (gather +
decision marker + native `blocking` list); sweep apply-mode doc edits are staged in a work
workspace with the landing offered per [prd.md §8.2](prd.md); decision recording and
close/reopen stay on `gh_persist.py` with reentrancy preserved; the question-status reader's
return vocabulary converges on the §3 codes here (`AMBIGUOUS`), completing S11's sweep.

**DoD**
- [x] Tier-1 status join fixtures: closed / decision-marker present / still open (→ Tier-2
      needed flag).
- [x] Sweep apply (landing approved): PR opened; root clean throughout.
- [x] Sweep apply (landing declined): no git actions; summary reports workspace + landing
      commands.
- [x] `question-decision:v1` comment diffs clean against S1 captures; reentrant revise
      (post-new-then-delete-old) parity-tested.
- [x] New names used throughout the new dirs; `disable-model-invocation` retained; grep gates;
      parity recorded: sweep report-only, sweep apply, resolve + close.

**Testing:** shim-backed unit tests for both preps; the three live parity scenarios.

### S19 — Doc-reviewer rewrite

**Goal:** `skills/doc-reviewer/` aligned to the router shape ([prd.md §6.4](prd.md)).

**Work:** name unchanged; guide resolution and review lenses carried; apply mode stages edits in
a work workspace and offers the landing per [prd.md §8.2](prd.md); no prep script (nothing to
gather — assert that stays true).

**DoD**
- [x] Review report structure preserved (parity on one sandbox doc).
- [x] Apply mode (landing approved): PR opened; root clean throughout.
- [ ] Apply mode (landing declined): no git actions; summary reports workspace + landing
      commands.
- [x] `disable-model-invocation` retained; grep gates.

**Testing:** live parity on one doc; offline n/a beyond validators.

---

## Phase 6 — Retirement

### S20 — v1 removal & repo truth

**Goal:** delete what the cutovers obsoleted; make the repo describe v2.

**Work:** remove `agents/github-ops.md`, every v1 `scripts/*.sh` (gh-gather, gh-pr-gather,
gh-persist, config-block, worktree-hooks), all v1 skill directories, and the superseded internal
`_shared` docs (`subagent-decision-signal.md`; the mechanics half of `worktree-lifecycle.md` —
external block formats stay); sweep old names and stale
`/github-pipeline:<old-name>` strings; update `README.md`, `plugin.json`, `marketplace.json`
(version bump), the authoring guides where they name old skills, and this repo's `CLAUDE.md`
(rewritten for v2, including the extended validator greps: old names, `git show` in `skills/`,
raw `gh` writes in `skills/`); record the final census diff against the S1 baseline in
`docs/specs/baseline.md` with every dropped token accounted for.

**DoD**
- [ ] Zero grep hits under `skills/`, `agents/`, `scripts/`, `tests/`, `README.md`,
      `.claude-plugin/`, and `CLAUDE.md` for: old skill names, `github-ops`, `worktree-hooks`
      (`docs/specs/**` and `docs/implementation.md` are exempt as the historical record); no
      `*.sh` remains under `scripts/`.
- [ ] Census diff reviewed; every removed token is on the deliberate-retirement list.
- [ ] Full offline suite green on macOS and Linux; manifests parse; version bumped; the
      runtime-dependency docs list only `python3` / `git` / `gh` (`jq` and `bash` dropped).
- [ ] Fresh end-to-end conveyor run on the sandbox — draft → research (decline acceptable) →
      plan → resolve → evaluate → merge — with every handoff schema-valid.
- [ ] `CLAUDE.md` describes only the v2 architecture; guides name only new skills.

**Testing:** the end-to-end sandbox run is the test; all validators re-run and recorded.
