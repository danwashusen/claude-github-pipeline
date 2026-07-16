# Parity — planner (v1 `github-issue-planner` → v2 `planner`)

> Records the [implementation.md](../../implementation.md) **S13** parity run per the
> [parity protocol](../../implementation.md) (`## The parity protocol`) and [prd.md §9.5](../../prd.md).
> The offline work (router + four playbooks + spine + references + tests + the `prep_planner`
> alignment) landed in S13's implementor pass; the **four live scenarios below are operator-gated** —
> run them on the sandbox ([SANDBOX.md](../../../tests/SANDBOX.md)) and fill each result section. A v1
> skill directory is deleted only after its v2 replacement passes this protocol (S20).

## Line-count metric ([prd.md §10](../../prd.md); S13 DoD box 6)

The success metric: the prompt a session loads (router + the one playbook it executes) is **at most
half** the v1 `SKILL.md` line count. v1 `github-issue-planner/SKILL.md` = **503 lines**
([baseline.md](../baseline.md) §1) → bar = **251**.

| File | Lines |
|---|---:|
| `skills/planner/SKILL.md` (router) | 129 |
| `skills/planner/playbooks/plan-spine.md` (the shared spine — largest playbook) | 122 |
| `skills/planner/playbooks/revise.md` | 67 |
| `skills/planner/playbooks/story-jit.md` | 48 |
| `skills/planner/playbooks/epic.md` | 40 |
| `skills/planner/playbooks/single.md` | 37 |
| **router + largest playbook (the loaded set)** | **251** |

**251 ≤ 251** ✅ (exactly at the bar — `revise.md` grew when the S13 second pass wired the `edit-labels`/
`close-pr` ops in place of the write-path-gap prose notes; the spine was trimmed to hold the line).
Router **129 ≤ 150** ✅ (architecture.md §9 size bar). References are read on demand and are not part of
the loaded-prompt metric; recorded for completeness: `plan-reviewer-prompt.md` 263 (carried logic,
tool-use rewritten for the read workspace), `handoff-renderings.md` 215, `revise-reconciliation.md` 124,
`plan-schema.md` 139 (carried verbatim — the frozen prd §7 artifact).

Every routed session loads the router (129) + the spine (122) + exactly one thin routed playbook
(37–67). The DoD's metric is *router + largest playbook* = 251; each individual document still fits one
default `Read`.

## Playbook split (the §5-bar decision the Work records)

architecture.md §5 "parameterize before you playbook": a playbook exists only for flows that differ in
**actions taken**, not in values. For the planner the ground→draft→verify→persist flow is identical
across every shape *up to facts* (which `plan_ref`, which schema sections, which reviewer dimension
set); only the **pre-draft reconnaissance and the post-persist handoff actions** diverge. The split:

- **`playbooks/plan-spine.md`** — the author-and-verify-a-plan flow every route runs (classify → ground
  at the read workspace → deviation/decision gates → draft against the schema → pre-flight hedge sweep →
  verify loop → show → persist plan + pointer). Type is a fact here, never a branch. All four routes
  open by reading it.
- **`playbooks/single.md`** — a standalone issue: standard schema, `## Coverage gap` for a bug, `## Phases`
  when multi-phase (a fact); dimensions 1,2,3,4,6 (+9 bug, +7 multi-phase); forward handoff to the resolver.
- **`playbooks/epic.md`** — the epic-level plan: `## Story breakdown`/`## Story contracts`/`##
  Integration strategy` instead of `## Phases`; Dimension 5; **stop before per-story fan-out**; route to
  the planner on the first story, or the drafter when stories aren't filed.
- **`playbooks/story-jit.md`** — a story under an open epic: **inline epic-plan bootstrap** when absent
  (the composite epic+story session), delivery-log-vs-contract reconciliation (the epic-plan feedback
  edge), `## Epic contract` + the `**Epic:**` backlink, Dimension 8; story handoff (the bug-(b)
  composite OQ line).
- **`playbooks/revise.md`** — the reconcile-old-vs-new-plan flow: SOFT/HARD classification + DoD-tick
  reconciliation, diff-show, `## Predecessor`; parameterized by the type facts, not a type branch.

Why a spine + four thin variants rather than one self-contained file per route (which would each restate
the whole author-verify flow) or a single file with `if epic … else …` (banned by §5)? The
author-verify flow is identical across shapes up to *facts*; only the reconnaissance and handoff diverge.
The four variants contain **zero cross-route conditionals** — the route *is* the branch — verified by
`tests/test_planner_routing.py::PlaybookInterleavingGrepTests` (patterns broadened to the planner's route
set per the S10 carried advisory).

## The `prep_planner._suggested_playbook` alignment (authorized script touch)

S12 shipped `prep_planner._suggested_playbook` proposing the three placeholder names
`standard`/`epic`/`story` (its own docstring flagged this as the "S13 contract proposal" to be
finalized here). S13 aligned it to the four real playbook names, keyed on `(issue_type, mode,
parent_epic_open)`:

- `story` + open parent epic (any mode) → `story-jit.md` (owns fresh **and** revise for such a story —
  v1 SKILL.md:72's Step-2 exception; the short-circuit runs before the revise check).
- `mode: revise` (standalone issue or epic) → `revise.md`.
- `epic` fresh → `epic.md`.
- everything else fresh (`standard`, or a `story` with no open parent epic) → `single.md`.

The S12 reviewer pre-ruled these names non-contractual, so this is a surgical rename + a new
`parent_epic_open` argument (threaded from the already-computed `parent_open` fact), plus updated
fixtures/tests (`tests/test_prep_planner.py`). **Note the one parenthetical deviation from the brief's
"mode revise → revise.md regardless of type; else type→name":** a story under an open epic in revise
mode routes to `story-jit.md`, not `revise.md`, because v1's Step-2 exception makes just-in-time story
planning own both modes; and a parentless/closed-parent story routes to `single.md` per v1's "Everything
else" path rather than `story-jit.md`. Both are spec-faithful refinements of the brief's shorthand.

**The `plan_ref_row` table — 6 → 7 rows (D4 fix, landed post-scenario-2).** `_select_plan_ref`'s row
constants are a *separate* fact from `suggested_playbook` (above) — `plan_ref_row` records **why**
`plan_ref` resolved the way it did, purely as data; no consumer keys routing on it. Scenario 2's live
parity run filed **D4**: a story under an OPEN parent epic whose integration branch hadn't bootstrapped
yet reported the self-contradictory pair `story.parent_epic_open: true` +
`vector.plan_ref_row: "story-no-open-parent-epic"` — a truthful `plan_ref` (`main`) wearing a label that
denies the parent is open. Fixed by splitting what was one row (keyed on branch absence alone) into two
(keyed on branch absence **and** the parent's open-ness), both still resolving to `main`:

| # | `plan_ref_row` | Fires when | `plan_ref` |
|---|---|---|---|
| 1 | `open-pr-head` | an open PR already exists for this issue | that PR's `headRefName` |
| 2 | `epic-as-target` | epic-as-target, `epic/<N>-<slug>` branch discovered | that branch |
| 3 | `epic-as-target-bootstrap` | epic-as-target, zero `git ls-remote` matches | `main` |
| 4 | `story-under-open-epic` | story, OPEN parent epic, its branch discovered | that branch |
| 5 | `story-parent-epic-bootstrap` **(new, D4)** | story, OPEN parent epic, zero `git ls-remote` matches for its branch | `main` |
| 6 | `story-no-open-parent-epic` | story, no parent found, or a CLOSED one | `main` |
| 7 | `no-open-pr-default-branch` | everything else (standalone, no open PR) | `main` |

Rows 5 and 6 are the split: row 5 is new; row 6's semantics narrowed to exactly what its name always
claimed (the module docstring's pre-fix row-5 gloss — "story with no parent epic, or a closed one" — the
code just didn't implement it). Neither `suggested_playbook` (which keys on `(issue_type, mode,
parent_epic_open)`) nor any playbook keys on the row name, so routing is unaffected by the split — see
the D4 resolution note under scenario 2 below for the full fix + test citations.

## The newly-detected-OQ search mechanism (option ii — the authorized additive `--oq-query` flag)

Bug (a)'s frozen requirement is that a genuinely-filed `question` issue is never recorded `(not
filed)`. Prep's `open_question_candidates` pre-searches only the entries the **issue body** already
records. For an OQ the plan detects **anew during grounding** (never in the body), the playbook needs the
same tracker search — but a raw `gh issue list` in a playbook is banned (architecture.md §7). Of the two
clean options the brief names, S13 chose **(ii): an additive `prep_planner.py --oq-query "<topic>"`
one-shot lookup** — option (i) (write the new OQ into the issue body first, then `--refresh`) was
rejected because the planner must **not** rewrite the body's `## Open questions` section (v1 SKILL.md:100
"you never rewrite the body section" — that is the drafter's / open-questions sweep's artifact). The
`--oq-query` flag runs the identical deterministic search, emits `oq_query_candidates`, assembles no
facts, and is additive (never on the default path). Covered by
`tests/test_prep_planner.py::OqQueryOneShotTests` and the routing test's `BugARuleTests`.

## Contract-token census ([global DoD](../../implementation.md) skill-cutover clause)

The S1 baseline census ([baseline.md](../baseline.md) §2) was re-run against the identical command after
this cutover. Result: **zero drops vs baseline**; every addition is a legitimate `skills/planner/`
contract token — the markers the skill reads/writes (`<!-- implementation-plan:v1 -->`,
`<!-- epic-delivery-log:v1 -->`, `<!-- issue-research:v1 -->`, `<!-- open-question-links:v1 -->`,
`<!-- question-decision:v1 -->`) plus the v2 handoff namespace strings `github-pipeline:planner` /
`github-pipeline:resolver` / `github-pipeline:drafter` / `github-pipeline:researcher` and the skill's own
`§`-anchors / doc-section refs. New `skills/planner/` files introduce **no** `github-ops`, **no**
`GATHER_*`/`PERSIST_*` op names, **no** `github-pipeline:github-*` v1 namespace strings, and **no** `§P`
IDs.

**Deliberate-retirement note (deferred to S20).** No v1 token retires at S13 — the v1
`skills/github-issue-planner/` directory is untouched and still contributes all its baseline census rows
(`GATHER_ISSUE`/`GATHER_EPIC`/`PERSIST_COMMENT`/`PERSIST_BODY`, `github-pipeline:github-ops`, its
`§`-anchors, the `github-pipeline:github-issue-*` handoff strings). Those retire when S20 deletes the v1
directory after this v2 replacement passes the live parity below.

## Grep gates (S13 DoD box 2) — recorded green

Run over `skills/planner/`:
- `github-ops` — **0 hits**.
- Old skill-invocation namespace (`github-pipeline:github-*`) — **0 hits**.
- v1 op names (`GATHER_*` / `PERSIST_*`) — **0 hits**.
- Ref arithmetic in code fences (`git show <ref>:<path>` / `git grep <ref>`) — **0 hits**
  (`ContractTokenGateTests::test_no_ref_arithmetic_in_code_fences`; the reviewer prompt reads the
  grounding read workspace by path, never a ref).
- Raw `gh` persist/gather writes, fenced or not (`gh issue|pr create|edit|comment|review|close|reopen`)
  — **0 hits, anywhere in `skills/planner/`.** The reviewer prompt's `gh issue view` is a read
  (self-fetch, not a write) and does not match. Both v1 write-path gaps below are now real
  `gh_persist.py` ops — no raw-`gh` prose workaround remains.
- `§P` IDs (resolver-local; must not appear) — **0 hits**.

**Two v1 write-path gaps — resolved in-step, not deferred.** The two v1 writes flagged in this step's
first implementor pass as having no authorized v2 script op are now real, additive `gh_persist.py`
subcommands (S13 second pass, authorized per architecture.md §2 "if a needed operation has no script,
extend a script" — the same precedent S10's `create-pr` established). Every pre-existing `gh_persist.py`
op's argv shape and envelope are byte-identical; the S21-ported test suite (`tests/test_gh_persist.py`'s
67 pre-existing tests) is unmodified and green.

- **The `planned` label** (v1 SKILL.md:402) → **`gh_persist.py edit-labels <repo> <issue> --add
  planned`** — a new, bodyless (no empty-body gate), additive op. `--add`/`--remove` are each
  repeatable; at least one is required. No client-side idempotency special-casing: an already-present
  add / an absent remove are `gh`'s own no-op successes, matching the `close`/`reopen` discipline.
  Wired into `plan-spine.md` S8, replacing the v1-pass gap note. Tests: `tests/test_gh_persist.py::
  EditLabelsTests` (8 cases — happy path add/remove/combined, usage error, add-present and
  remove-absent idempotency, dry-run, AUTH_REQUIRED) +
  `tests/test_planner_routing.py::PlaybookPersistDryRunTests::test_planned_label_apply_edit_labels_dry_run`.
  Known future consumers (not this step's callers, recorded in the script's own docstring): S15
  (drafter) and S16 (researcher, the `researched` label).
- **The HARD-revise PR-close** (v1 `revise-reconciliation.md`, `gh pr close --comment "Re-plan superseded
  this PR. …"`) → **`gh_persist.py close-pr <repo> <pr> [--comment-file <path>]`** — a new op that closes
  a PR with an *optional* staged comment. `gh pr close` has no `--body-file` of its own, so the script
  reads the staged `--comment-file` itself and forwards its bytes as `gh pr close`'s `--comment <text>`
  value — the comment still crosses the *prompt* boundary as a path; the empty-body gate applies only
  when `--comment-file` is given. **Cross-skill contract, byte-faithful:** the resolver's predecessor-PR
  detection (`docs/specs/resolver.md` "Deterministic steps": "Predecessor-PR detection … filtered to
  `Re-plan superseded this PR` bodies") greps a closed PR's **close comment** for the literal phrase
  `Re-plan superseded this PR` for its `-vN` fresh-branch suffixing (`gh pr close --comment` posts a
  genuine PR comment, never the PR body/description — the op's own staged text IS that close comment) —
  `revise.md`'s HARD "Start fresh" path (and `revise-reconciliation.md`'s worked example) now stage that
  exact phrase, byte-faithful, before calling `close-pr`. **The gate is unchanged**: the close runs only
  after the user has already picked **Start fresh** at the S8 three-way confirm (`Start fresh
  (recommended)` / `Apply in place anyway` / `Cancel`) — the op executes the already-gated decision, it
  adds no new gate and removes none. Tests: `tests/test_gh_persist.py::ClosePrTests` (8 cases — bodyless
  close, close-with-comment write-receipt + marker-text forwarding, missing/empty `--comment-file` →
  `EMPTY_BODY_FILE`, dry-run with/without comment, AUTH_REQUIRED) +
  `tests/test_planner_routing.py::PlaybookPersistDryRunTests::test_hard_revise_close_pr_with_supersession_marker_dry_run`.

  **Finding — v1's own predecessor-PR detection reads the wrong field (latent v1 bug, not a v2
  regression).** `docs/specs/resolver.md`'s "Deterministic steps" row phrases the target as "…filtered
  to `Re-plan superseded this PR` **bodies**" — but v1's actual implementation
  (`skills/github-issue-resolver/SKILL.md:873-878`) fetches `gh pr list … --json
  number,headRefName,closedAt,body` (the PR's **body**/description field only) and then greps that
  fetched `body` for the marker. The marker itself, however, is posted by the planner's HARD-revise as a
  **close comment** (`skills/github-issue-planner/references/revise-reconciliation.md:49`, `gh pr close
  --comment "Re-plan superseded this PR. …"` — `--comment` posts a genuine PR comment, it does not edit
  the PR's body/description). So v1's own filter greps a field the marker was never written into: **v1's
  predecessor-PR detection is latently broken** (marker lives in a close comment; v1's filter reads only
  the body) — it would never actually find a predecessor PR, silently falling through to the "no
  predecessor" branch (unsuffixed `<issue>-<slug>` branch name) even after a genuine HARD re-plan. v2's
  `close-pr` posts the byte-faithful marker to the close comment as specified (correct per the marker's
  actual home); a future v2 consumer of this detection (not built this step — no v2 resolver code reads
  it yet) must read PR **comments**, not `--json body`, to actually find it. Not fixed here — `docs/
  specs/resolver.md` is out of scope for this step's authorization; recorded for the orchestrator to
  authorize a spec addendum at acceptance if this reading is confirmed a genuine defect.

## Operator-gate coverage (S13 DoD box 5)

Every operator gate in [planner.md](../planner.md) "## Operator gates" is present in the v2 skill:

| S1-spec gate | v2 home |
|---|---|
| Latest-decision-direction confirmation | spine S1 (freeform) |
| External sources | spine S2 (freeform) |
| Deviation from docs/precedent | spine S4 (`header: "Deviation"`) |
| Genuine design decision (Decision gate) | spine S4 (`header: "Decision"`) |
| Review-notes disposition (dim-4 BLOCKER → no "Post as-is") | spine S7 (`header: "Review notes"`) |
| Review-notes disposition (dims 1/2/3/5/6 only) | spine S7 (`header: "Review notes"`) |
| Show plan before posting (opt-in) | spine S8 ("unless the user said don't post yet") |
| Revise reconciliation confirm (SOFT) | `revise.md` (**Apply** / **Cancel**) |
| Revise reconciliation confirm (HARD) | `revise.md` (**Start fresh (recommended)** / **Apply in place anyway** / **Cancel**) |

Verified by `tests/test_planner_routing.py::OperatorGateCoverageTests`. No gate's absence traces to a
PRD § — all present.

## Sandbox seeding notes (read before running the scenarios)

- **The seeded epic needs a `## Stories` section AND the epic body must reference each story `#N`.**
  S12's live smoke found the base-seed epic (`SANDBOX.md` §5) has only `## Summary` + `## Definition of
  done` and never lists or references its stories — so `prep_planner._parse_stories_section` returns `[]`
  (breaking the epic scenario's `## Story breakdown` reconciliation) and `_search_parent_epic` (which
  looks for the epic whose **body** contains `#<story> in:body`) finds no parent (breaking the JIT-story
  scenario's routing to `story-jit.md`). For the epic + JIT scenarios, seed a **properly-shaped epic**
  on a throwaway fixture for the run: give the epic body a `## Stories` section listing each filed story
  as `- [ ] #<S> — <title>` (which both makes `stories_filed` true **and** puts each `#<S>` in the epic
  body so the parent-epic search resolves), e.g.:

  ```
  ## Summary
  Parity-fixture epic with two stories.

  ## Stories
  - [ ] #<S1> — First slice
  - [ ] #<S2> — Second slice

  ## Definition of done
  - [ ] Story A ships
  - [ ] Story B ships
  ```

  This keeps the base seed minimal (per SANDBOX.md's "constructed for the run, not folded back") while
  giving the epic/JIT scenarios a parent the planner can actually discover.
- **Never pre-check `prep_planner.py` inside a leg's run clone — it dirties the root and the real run
  then hits `ROOT_DIRTY`.** A `prep_planner.py` call builds its read workspace under the root's
  `.worktrees/` and writes a `.gitignore` containing `.worktrees/`, leaving the clone with an untracked
  file. The v2 leg's own prep then exits `needs_decision`/`ROOT_DIRTY` and the run stalls before any
  write (the planner treats the root as a read-only `main` vantage and won't commit/stash/discard it) —
  cost S13 scenario 2 a wasted v2 leg. Fixture pre-checks are worth running (they catch a mis-seeded
  epic before ~$5–10 of live run), but run each in its **own throwaway clone**, one call per clone: a
  second `prep_planner.py` call in the same clone hits `ROOT_DIRTY` from the first call's artifacts.
  Same rule for cross-consumption checks after a run.
- **Bug (c) is an expected v1↔v2 divergence, not a regression.** v2's `gh_gather.references_issue`
  digit-boundary reference filter (landed in S12's round) means a `plan_ref` open-PR-head row only fires
  for a PR that genuinely references the target issue. v1's `gh-gather.sh` inherits the bare-digit
  `in:body` false-positive. On a sandbox state where a stranger PR's incidental digit collides with the
  target, v1 will route `plan_ref_row: open-pr-head` at that stranger's branch while v2 routes correctly
  — **the divergence is the fix working, not a v2 regression to chase.**
- **The `planned` label + HARD-revise PR-close are both real v2 writes now** (resolved in-step, above)
  — v1 and v2 both apply the label and close the superseded PR; no divergence to record for either.

---

## Live parity scenarios (operator-gated — TODO)

Run each per the [parity protocol](../../implementation.md) steps 1–5 on the sandbox: construct the
target state, run **v1** `github-issue-planner` capturing every GitHub write / gate / handoff / turn
count, reset (or use a twin — the epic/JIT flows mutate a shared parent, so **twin the epic subtree**),
run **v2** `planner` on the same state, then compare: the persisted **plan comment** schema-identical
(same marker first line, section/heading set + order, structured fields, footer — confirmed by
cross-consumption with the resolver/evaluator readers); planned-at SHA equals the facts grounding
workspace SHA (box 1); the bug-(a) candidate consultation observed (box 4); the bug-(b) composite OQ line
rendered (box 3); same genuine decisions gated; handoff validates against the shared schema; startup ≤
one state-assembly call. List divergences; each must trace to a PRD requirement, an explained gap above,
or be a filed defect. **Unexplained divergence fails the run.**

### Scenario 1 — Plan-new, single issue (bug or feature)

Target: a standalone `bug` issue (base `main`, no open PR, no prior plan). Expected v2: one
`prep_planner.py` call, grounding at `origin/main@<sha>`, plan posted via `gh_persist.py comment` with
the marker first line and the `origin/main@<sha>` footer (`<sha>` = `read_workspaces.grounding.sha`),
issue-body pointer via `edit-body`, forward handoff to `/github-pipeline:resolver #<N>`. For a bug, a
`## Coverage gap` section + Dimension 9. Box-1 check: the footer's `@<short-sha>` == the facts grounding
SHA.

**Run (2026-07-11).** Twin fixture: one shared groundable bug seeded on `main` — `src/initials.py`'s
`initials(full_name)` returns `full_name` unchanged instead of the uppercase initials its docstring
promises (`initials("Ada Lovelace") -> "AL"`). Seeded onto sandbox `main` at **`12fa50d`** (commit
`12fa50de6a93a27f1656a7deb2c063d7fb6912f4`), the grounding base for both legs. Two equivalent unplanned
`bug` issues (identical bodies, `bug` label only): **#47** (twin-A → v1 `github-issue-planner`) and
**#48** (twin-B → v2 `planner`). Headless recipe as S7/S10 (`claude -p "/github-pipeline:<skill>
<issue>" --plugin-dir <this branch> --model opus --permission-mode bypassPermissions`, **fresh sandbox
clone per leg**). Neither leg touches code or `main`, so `main` stayed `12fa50d` across both sessions.

- [ ] v1 run captured (writes / gates / handoff / turns) — #47 grounded at `origin/main@12fa50d`; plan
      posted as [comment `4941018980`](https://github.com/danwashusen/gh-pipeline-sandbox/issues/47#issuecomment-4941018980)
      (byte-for-byte self-confirmed), issue-body pointer added, **`planned` label applied** (final labels
      `bug,planned`). **0 operator gates** (`AskUserQuestion` ×0 — "no deviation gate and no
      design-decision gate fired"); verify loop **1 pass** (0 blockers, 0 suggestions, 1 silently-folded
      NIT). Reproduced the buggy output during grounding (Dimension 9). Sub-agents: `github-ops` ×3
      (`GATHER_ISSUE` "Gather issue #47" = the sole **state-assembly** call, `PERSIST_COMMENT` "Post plan
      comment", `PERSIST_BODY` "Ensure body plan pointer") + one `Explore` reviewer ("Plan review pass 1").
      Forward `## Handoff` → `/github-pipeline:github-issue-resolver #47` (Issue / Grounding / Next / Why;
      no `## Open questions` line — none present). ~53 assistant turns.
- [ ] v2 run captured (state-assembly call count = 1) — **exactly one** real `prep_planner.py 48
      danwashusen/gh-pipeline-sandbox` invocation (the router's sole state-assembly call; the other
      `prep_planner.py` strings in the transcript are the router-prose `--oq-query`/usage examples loaded
      into context, not calls). Facts: `vector.type=standard · mode=fresh · plan_ref_row=no-open-pr-default-branch`,
      `plan_ref=main`, `suggested_playbook=single.md`, `plan.present=false`, `open_question_candidates=[]`
      (no OQ → no `--oq-query`, bug-(a) path not exercised this scenario). Routed `single.md` via the
      shared spine. Writes = `gh_persist.py comment` + `edit-body` + `edit-labels` (the three writes;
      `planned` label via `edit-labels` — final labels `bug,planned`). **0 operator gates**
      (`AskUserQuestion` ×0); reviewer (one isolated `Explore`, "Plan reviewer for issue 48") cleared
      dimensions **1,2,3,4,6,9** (0 blockers, 1 applied nit). Forward `## Handoff` →
      `/github-pipeline:resolver #48`. ~54 assistant turns.
- [ ] Plan comment schema-identical (marker line, heading set + order, footer); cross-consumed by the
      resolver/evaluator plan readers — **YES.** Both open `<!-- implementation-plan:v1 -->` then the
      planned-at line `**Implementation plan** — #<N> … — planned <ts> at `origin/main@12fa50d``, then the
      **identical section set in identical order**: `## Approach` · `## Doc grounding` · `## Architecture
      decisions` · `## Changes (file-level)` · `## Test plan` · **`## Coverage gap`** (the bug section) ·
      `## Risks & watchpoints`, and close with an italic `_Authored by … verified in 1 review pass_`
      footer — a normalized skeleton diff (twin title / timestamp / short-sha masked) is **empty**. Only
      free prose differs. *Cross-consumption:* the resolver's plan reader (`prep_resolver.py`, fresh clone
      per issue) parses **both** comments identically — `plan.present=true`, `plan.sha=12fa50d`,
      `comment_id` = 4941018980 (v1) / 4941083907 (v2) — and routes `standard/fresh → standard.md`, i.e. the
      downstream resolver consumes the v2 artifact byte-for-byte as it does the v1.
- [ ] **Box 1 parity:** planned-at SHA == `read_workspaces.grounding.sha` — **YES, exact.** The v2 facts'
      `read_workspaces.grounding.sha` = `12fa50de6a93a27f1656a7deb2c063d7fb6912f4`; the plan footer records
      `origin/main@12fa50d`; `12fa50d` is the 7-hex prefix. (v1's footer records the same `12fa50d`, its own
      grounding SHA.)
- [ ] Gates match; handoff schema-valid — **YES.** **0 = 0** operator gates (both `AskUserQuestion` ×0; a
      clean bug with no deviation and no genuine design decision). Both handoffs are valid forward-planner
      `## Handoff` blocks (Issue / Grounding / Next / Why; `## Open questions` line correctly omitted — no
      OQ). The `Next:` command differs **by design** (v1 → `/github-pipeline:github-issue-resolver`, v2 →
      `/github-pipeline:resolver`) — each routes to its own generation's resolver (see D2).
- [ ] Divergences (each traced to a PRD § / an explained gap above / a filed defect):
      - **D1 — state-assembly + write mechanism (EXPLAINED; the documented v1→v2 cutover).** v1 assembles
        state via the `github-ops` `GATHER_ISSUE` sub-agent and writes via `PERSIST_COMMENT` / `PERSIST_BODY`
        + a `planned`-label apply; v2 assembles via one deterministic `prep_planner.py` facts block and writes
        via `gh_persist.py comment` / `edit-body` / **`edit-labels`**. Same three persisted artifacts (plan
        comment, body pointer, `planned` label). The `planned`-label-via-`edit-labels` mechanism swap is the
        divergence pre-recorded in this doc ("v2 applies the `planned` label via `edit-labels` — same
        artifact, new mechanism") and the S13 handback. Not a defect.
      - **D2 — handoff `Next:` namespace (EXPLAINED; by design).** v1 hands to
        `/github-pipeline:github-issue-resolver #47`; v2 to `/github-pipeline:resolver #48`. Each generation
        routes to its own resolver skill; the v2 namespace is correct per the plugin's baked-in naming. Not a
        divergence to chase.
      - **D3 — footer/pointer author self-attribution reads `github-issue-planner` on *both* legs
        (COSMETIC; identical, no parser reads it).** v2's italic plan footer and the issue-body pointer both
        emit "Authored by `github-issue-planner`" (the v1 skill name) rather than `planner`. Because v1 emits
        the identical string, this is **not** a v1↔v2 schema divergence — the skeletons match — and no
        consumer parses the author label (the resolver plan reader keys on the marker + `comment_id`, not the
        attribution). Recorded only as an optional future v2 self-attribution cleanup; not run-failing.

**Verdict: PASS (both legs) — zero unexplained divergences.** Both ground a standalone unplanned bug at
`origin/main@12fa50d`, post a schema-identical `<!-- implementation-plan:v1 -->` plan (same marker,
planned-at line, seven-section set + order incl. `## Coverage gap`, footer) with the byte-exact
`origin/main@12fa50d` footer, add the body pointer, apply the `planned` label, gate **0** decisions, and
emit a valid forward handoff to the resolver. **Box 1** holds exactly (footer `12fa50d` ==
`read_workspaces.grounding.sha` `12fa50de6…`); **v2 startup = 1** `prep_planner.py` state-assembly call;
the resolver plan reader cross-consumes both artifacts identically. D1–D3 are cutover / by-design /
cosmetic, each explained. (Boxes left unticked — operator-owned.)

### Scenario 2 — Plan-new epic

Target: a properly-seeded epic (see the seeding note — `## Stories` present, story `#N`s in the body).
Expected v2: grounding at the `epic/<N>-<slug>` branch (or `origin/main` on bootstrap), the epic plan
with `## Story breakdown` / `## Story contracts` / `## Integration strategy` (no `## Phases`), Dimension
5, **no per-story fan-out**, forward handoff to `/github-pipeline:planner #<first-story>` (stories filed)
or `/github-pipeline:drafter` (stories not filed).

**Run (2026-07-15).** Twin fixture: two independent epic subtrees seeded per the seeding note — each
epic body carries a `## Stories` section (`- [ ] #<S> — <title>`), which both makes `stories_filed` true
and puts each `#<S>` in the epic body. Both epics propose the same work against the sandbox's existing
`src/` helpers: a `src/salutations.py` facade (`register`/`render`) that the six in-scope greeting
helpers then delegate to — story A delivers the facade, story B consumes it (a real cross-story seam for
`## Story contracts` + Dimension 5). **Twin-C** → v1 `github-issue-planner`: epic **#55**, stories
**#56**/**#57**. **Twin-D** → v2 `planner`: epic **#58**, stories **#59**/**#60**. Neither epic has an
`epic/<N>-<slug>` branch, so **both legs took the bootstrap row** (`vector.plan_ref_row:
epic-as-target-bootstrap`, `plan_ref: main`) and grounded at **`origin/main@12fa50d`** — `main` was
untouched by both sessions (neither leg writes code). Headless recipe as S7/S10/S13-scenario-1 (`claude
-p "/github-pipeline:<skill> <epic>" --plugin-dir <this branch> --model opus --permission-mode
bypassPermissions`, **fresh sandbox clone per leg**).

- [ ] v1 run captured — #55 grounded at `origin/main@12fa50d`; epic plan posted as [comment
      `4976042286`](https://github.com/danwashusen/gh-pipeline-sandbox/issues/55#issuecomment-4976042286),
      issue-body pointer added, **`planned` label applied** (final labels `epic,planned`). **0 operator
      gates** (`AskUserQuestion` ×0); verify loop **3 passes**. Sub-agents ×7: `github-ops` ×4
      (`GATHER_ISSUE` "Gather issue 55" = the sole state-assembly call, `GATHER_EPIC` "Gather epic 55
      stories", `PERSIST_COMMENT` "Post epic plan to issue 55", `PERSIST_BODY` "Add plan pointer to issue
      55 body") + 3 `Explore` reviewers. The `planned` label went via a **raw `gh issue edit 55
      --add-label planned`** in the main loop — v1's documented write-path gap. Forward `## Handoff` →
      `/github-pipeline:github-issue-planner #56`. ~184 assistant turns, $9.94.
- [ ] v2 run captured (epic sections present; no per-story plans authored) — **exactly one**
      `prep_planner.py 58 danwashusen/gh-pipeline-sandbox` invocation (the router's sole state-assembly
      call). Facts: `vector.type=epic · mode=fresh · plan_ref_row=epic-as-target-bootstrap`,
      `plan_ref=main`, `suggested_playbook=epic.md`, `plan.present=false`, `epic.stories_filed=true`,
      `epic.stories=[#59 OPEN, #60 OPEN]` (both `live_title`-resolved), `epic.branch.match_count=0`,
      `epic.delivery_log.present=false`, `open_question_candidates=[]`. Routed `epic.md` via the shared
      spine. Writes = `gh_persist.py comment` + `edit-body` + `edit-labels --add planned` (final labels
      `epic,planned`). **0 operator gates**; 3 `Explore` reviewer passes, **0** gather/persist sub-agents
      (scripts called directly). Forward `## Handoff` → `/github-pipeline:planner #59`. ~118 assistant
      turns, $5.42. **No per-story fan-out on either leg** — stories #56/#57 and #59/#60 all carry **0**
      `<!-- implementation-plan:v1 -->` comments.
- [ ] Plan comment schema-identical (epic sections + footer) — **YES.** Both open `<!-- implementation-plan:v1 -->`
      then the planned-at line ``**Implementation plan** — #<N> … — planned <ts> at `origin/main@12fa50d` ``,
      then the **identical section set in identical order**: `## Approach` · **`## Story breakdown`** ·
      **`## Story contracts`** · **`## Integration strategy`** · `## Doc grounding` · `## Architecture
      decisions` · `## Changes (file-level)` · `## Test plan` · `## Risks & watchpoints`, closing with the
      italic `_Authored by … verified in 3 review pass(es)_` footer. **No `## Phases` on either leg**
      (correct for an epic). A normalized skeleton diff (twin title / timestamp / short-sha / issue
      numbers masked) is **empty** but for free footer prose ("3 review passes" vs "3 review pass(es)").
      `## Story breakdown` renders the `- #<story> "<title>" — <scope>` grammar and `## Story contracts`
      the `- #<story> — delivers: … — consumes: …` grammar on both, each dependency-ordered facade→
      migration with the head story's `consumes: (none)`. *Cross-consumption:* `prep_planner.py` run on
      each twin's head story (fresh clone per call) reads **both** epic plans identically —
      `story.parent_epic={number: 55|58, state: OPEN}`, `parent_epic_open=true`,
      `story.epic_plan.present=true` (body inline), `epic_branch.match_count=0` → routes `story-jit.md`,
      i.e. the downstream just-in-time story reader consumes the v2 epic artifact as it does the v1.
- [ ] **Box 1 parity:** planned-at SHA == the grounding SHA — **YES, exact.** The v2 facts'
      `read_workspaces.grounding.sha` = `12fa50de6a93a27f1656a7deb2c063d7fb6912f4`; the plan footer records
      `origin/main@12fa50d`; `12fa50d` is the 7-hex prefix. (v1's footer records the same `12fa50d`, its own
      grounding SHA.) **Row recorded: bootstrap** (`epic-as-target-bootstrap`) — no `epic/55-*` or
      `epic/58-*` branch existed, so `plan_ref` fell back to `main` on both legs.
- [ ] Handoff routes to the first story / the drafter per `stories_filed` — **YES.** `stories_filed=true`
      on both, so both take the stories-filed branch and route to the **head of `## Story breakdown`**:
      v1 → `/github-pipeline:github-issue-planner #56`, v2 → `/github-pipeline:planner #59` (namespace by
      design, D2). Both handoffs are valid epic-plan `## Handoff` blocks with the `Epic:` line (`plan: ✓`
      + comment URL), the `Stories:` line (`#56, #57` / `#59, #60` — "2 filed, dependency-ordered,
      contracts pinned · plans authored just-in-time"), `Grounding:` (`read at origin/main@12fa50d` + the
      grounding-doc detail), `Next:`, and a `Why:` that both independently name just-in-time planning
      against epic HEAD. `**Open questions:**` correctly omitted on both (no OQ; neither plan carries an
      `## Open questions` section).
- [ ] Divergences (each traced to a PRD § / an explained gap above / a filed defect):
      - **D1 — state-assembly + write mechanism (EXPLAINED; the documented v1→v2 cutover).** v1 assembles
        state via the `github-ops` `GATHER_ISSUE` + `GATHER_EPIC` sub-agents and writes via
        `PERSIST_COMMENT` / `PERSIST_BODY` + a **raw `gh issue edit --add-label planned`**; v2 assembles via
        one deterministic `prep_planner.py` facts block and writes via `gh_persist.py comment` / `edit-body`
        / **`edit-labels`**. Same three persisted artifacts (plan comment, body pointer, `planned` label).
        This is the same pre-recorded mechanism swap as scenario 1's D1; the v1 leg's raw-`gh` label call is
        the v1 write-path gap this step's `edit-labels` op closes. Not a defect.
      - **D2 — handoff `Next:` namespace (EXPLAINED; by design).** v1 → `/github-pipeline:github-issue-planner
        #56`; v2 → `/github-pipeline:planner #59`. Each generation routes to its own planner skill. Not a
        divergence to chase.
      - **D3 — footer/pointer author self-attribution reads `github-issue-planner` on *both* legs
        (COSMETIC; identical, no parser reads it).** Reproduces scenario 1's D3 verbatim on the epic route:
        v2's italic footer and body pointer emit "Authored by `github-issue-planner`" rather than `planner`.
        Identical on both legs ⇒ not a v1↔v2 schema divergence; no consumer parses the attribution. Same
        optional future v2 self-attribution cleanup; not run-failing.
      - **D4 — `prep_planner` `plan_ref_row` mislabels a bootstrap story (FILED DEFECT; v2-only fact, no
        artifact divergence).** Surfaced by this scenario's cross-consumption check, not by either leg's
        artifact. For a story under an **open** parent epic that has **no epic branch yet**, the same facts
        block reports `parent_epic.state: OPEN` + `parent_epic_open: true` **and**
        `vector.plan_ref_row: "story-no-open-parent-epic"` — self-contradictory. Root cause:
        `scripts/prep_planner.py`'s `_select_plan_ref` keys its `PLAN_REF_ROW_STORY_NO_PARENT` row on
        `epic_branch_name` being falsy,
        not on the parent's open-ness, so the bootstrap case (open parent, `match_count == 0`) falls into the
        row whose constant is named for the *closed/absent*-parent case; the module docstring's row 5 gloss
        ("story with no parent epic, or a closed one") documents the intended semantics, which the code does
        not implement. **Behaviour is correct today** — `plan_ref: main` is right for a bootstrap story, and
        `_suggested_playbook` keys on `(issue_type, mode, parent_epic_open)` rather than the row, so routing
        still lands `story-jit.md` (live-confirmed on **both** twins, #56 and #59). The defect is the label:
        the router's own invariant is "consume every fact as **data** — never re-derive", so a skill reading
        the row name literally would conclude there is no open parent epic. Reproduces identically on both
        twins ⇒ parity-neutral for this scenario. Needs either a row-name split (a distinct
        `story-under-open-epic-bootstrap` row) or a docstring/semantics correction — **scenario 3 (JIT story)
        runs straight through this row**, so resolve before that run.

        **RESOLVED (post-scenario-2, pre-scenario-3).** Row-name split, per the row-name-split option this
        bullet named: `scripts/prep_planner.py` gained `PLAN_REF_ROW_STORY_PARENT_BOOTSTRAP =
        "story-parent-epic-bootstrap"` (mirrors the epic-bootstrap naming), and `_select_plan_ref` now
        takes `parent_epic_open` as an explicit input so the story branch picks this row (not
        `PLAN_REF_ROW_STORY_NO_PARENT`) whenever `epic_branch_name` is absent AND the parent is open —
        `PLAN_REF_ROW_STORY_NO_PARENT` now fires only for the genuinely-parentless/closed-parent case,
        matching the module docstring's row-5 gloss the code previously didn't implement. `plan_ref`
        (`main`) and routing (`story-jit.md`, keyed on `parent_epic_open` alone, never on the row name —
        confirmed unaffected) are unchanged; only the label's truthfulness is fixed. See "The
        `prep_planner._suggested_playbook` alignment" section above for the full row table (now 6 → 7
        rows) and both the pure-function unit tests
        (`tests/test_prep_planner.py::PureHelperUnitTests::test_select_plan_ref_story_parent_bootstrap_row`,
        `::test_select_plan_ref_story_parent_open_but_no_branch_never_yields_no_parent_row`) and the new
        live-fixture regression
        (`tests/test_prep_planner.py::PlanRefRowTests::test_row_story_under_open_epic_bootstrap` — story
        under an open parent, zero `git ls-remote` matches for the epic branch, asserting the new row
        label + `plan_ref: main` + `read_workspaces.grounding` at `main` + `suggested_playbook:
        story-jit.md`). This entry records the fix landing, not a self-certification of scenario 3 — the
        operator still runs and records that scenario's live parity separately.

**Verdict: PASS (both legs) — zero unexplained divergences.** Both ground a properly-seeded, unplanned
epic at `origin/main@12fa50d` on the **bootstrap row**, post a schema-identical
`<!-- implementation-plan:v1 -->` epic plan (same marker, planned-at line, nine-section set + order incl.
`## Story breakdown` / `## Story contracts` / `## Integration strategy`, no `## Phases`, footer) with the
byte-exact `origin/main@12fa50d` footer, add the body pointer, apply the `planned` label, **stop before
per-story fan-out**, gate **0** decisions, run 3 reviewer passes, and emit a valid epic `## Handoff`
routing to the head story per `stories_filed`. **Box 1** holds exactly (footer `12fa50d` ==
`read_workspaces.grounding.sha` `12fa50de6…`); **v2 startup = 1** `prep_planner.py` state-assembly call;
the just-in-time story reader cross-consumes both epic artifacts identically. D1–D3 are cutover /
by-design / cosmetic; **D4 is a filed prep_planner defect to resolve before scenario 3**. (Boxes left
unticked — operator-owned.)

**Harness finding — operator gates are not exercisable headlessly (affects this scenario's gate check).**
The first attempt at this scenario (2026-07-15, twins A/B: epics #49/#52, stories #50/#51 and #53/#54)
seeded an epic whose DoD bullet 3 ("No caller constructs a greeting string outside `src/salutations.py`")
was unsatisfiable by its own stories — `src/salute_c.py`/`salute_d.py` (S10 scenario-1 fixtures left on
`main`) also build greeting strings and no story migrated them. **Both legs independently detected the
identical scope gap** (strong judgment parity), but diverged on what to do without a gate tool: v1
**stalled**, ending its turn asking the question in prose after 37 turns with **zero writes**; v2 recorded
the call in the plan and proceeded to post, stating outright that "`AskUserQuestion` isn't available in
this session, so the `salute_c`/`salute_d` scope call is recorded in the plan as a reversible decision
rather than gated to you up front." Cause: **`claude -p` exposes no `AskUserQuestion` tool**, so any
fixture that fires a genuine decision gate cannot be compared this way — v1 blocks, v2 routes around.
Every scenario passed so far (S7/S10/S13-1) happened to be 0-gate, which is why this never surfaced. The
protocol's "same genuine decisions gated" check is therefore **only meaningful on a 0-gate fixture** under
this harness; **gate parity for the planner (the nine gates in the coverage table above) needs a different
harness or an interactive run** and is *not* evidenced by any headless scenario. The re-seeded twins C/D
pin the scope explicitly (in-scope helpers named; `salute_c`/`salute_d` declared out of scope in both the
epic and story bodies), which is what makes the recorded run gate-free. Twins A/B are left in the sandbox
as-is; #52 carries v2's posted plan from the aborted attempt.

### Scenario 3 — JIT story (composite epic+story; bug-(b) check)

Target: a `story` under an **open** epic that has **no** plan yet (the composite case), whose story plan
carries an `## Open questions` entry with a `(not filed)` companion. Expected v2: routes to
`story-jit.md`, bootstraps the epic plan inline (both grounded at `origin/main`), posts the story plan
with the `**Epic:**` backlink first after the marker + a `## Epic contract` section, Dimension 8, and a
**story handoff whose `**Open questions:**` line renders** `(not filed) (audience:…) provisional-default`
(bug (b) — the line is not dropped despite the composite shape).

**Run (2026-07-16).** Twin fixture: two independent epic subtrees, **neither with a plan nor an
`epic/<N>-<slug>` branch** — the composite case. Each epic proposes `src/audit_log.py`, an append-only
trail, with two dependency-ordered stories: story A delivers `record(event, payload)` / `entries()`,
story B instruments `src/greeter_a.py` + `src/initials.py` to consume it (a real cross-story seam for
`## Story contracts` + Dimension 8). **Twin-E** → v1 `github-issue-planner`: epic **#62**, stories
**#63**/**#64**. **Twin-F** → v2 `planner`: epic **#65**, stories **#66**/**#67**. Both legs invoked on
**story A** (#63 / #66).

Shared grounding seeded onto sandbox `main` at **`46888c2`** (`12fa50d..46888c2`): `docs/open-questions.md`
— the register the sandbox's `<!-- drafter-open-question-markers -->` block has always named but which
never existed — plus `docs/prd.md` §2 (audit trail) and `docs/architecture.md` §3 (module layout). Neither
leg writes code, so `main` stayed `46888c2` across both. Headless recipe as S7/S10/S13-1/S13-2 (**fresh
sandbox clone per leg**).

**The OQ fixture (drives boxes 3 + 4).** Story A's body carries an `<!-- open-question-links:v1 -->`
section with **two** `provisional-default` entries, both recorded `question: (not filed)`:
- `SBX-OQ-21` (audience:developer) — **genuinely unfiled**. The tracker search returns nothing, so
  `(not filed)` is truthful. This is the entry box 3 expects in the handoff line.
- `SBX-OQ-22` (audience:architect) — **the bug-(a) trap**: the body's `(not filed)` is *stale*, because
  question **#61** ("does the audit trail cap retention…", open, `question` + `audience:architect`)
  genuinely exists and names it. A correct planner must cite `#61`, never `(not filed)`. Without this
  trap the candidate list is empty either way and box 4 is unfalsifiable — an empty list cannot
  distinguish "searched and found nothing" from "never searched".

Pre-run verification (throwaway clone, one prep call): `vector.type=story · mode=fresh ·
plan_ref_row=story-parent-epic-bootstrap`, `plan_ref=main`, `suggested_playbook=story-jit.md`,
`story.parent_epic={65, OPEN}`, `parent_epic_open=true`, `story.epic_plan.present=false`,
`epic_branch.match_count=0`, `epic_delivery_log.present=false`,
`read_workspaces.grounding.sha=46888c28c…`, `open_question_candidates=[{oq_id: SBX-OQ-22 → [#61 OPEN]}]`,
`attention=["open question 'SBX-OQ-22' has 1 tracker candidate(s) — do not record it as (not filed)"]`.
**This is the first live sighting of the D4 row-split fix**: `plan_ref_row: story-parent-epic-bootstrap`
now sits alongside `parent_epic_open: true` without contradicting it — the exact self-contradiction
scenario 2 filed, and the precondition that entry set for this run.

- [ ] v1 run captured — **required two operator answers to complete; see D5.** Ran in three segments:
      the initial invocation **stalled at 36 turns / $1.36 with zero writes**, ending its turn asking in
      prose which of three options to take, because epic #62 has no plan and v1's "Just-in-time story
      planning" (SKILL.md:433) opens *"the epic plan is already posted with its `## Story contracts`"* —
      it has **no routing-time path for the composite case**. Answered **"C"** (v1's own third option:
      plan the epic and this story in one session). It then stalled a **second** time (13 turns / $1.17)
      on a genuine §6.5 design-decision gate — the audit **entry shape**, tuple vs dict — which v2 never
      fired (D5). Answered **"1"** (v1's own recommendation, tuple — deliberately *not* v2's dict, which
      would have steered the comparison). It then ran clean: 141 turns / $8.04, both plans posted —
      epic [comment `4988682690`](https://github.com/danwashusen/gh-pipeline-sandbox/issues/62#issuecomment-4988682690)
      (3 verify passes), story [comment `4988736290`](https://github.com/danwashusen/gh-pipeline-sandbox/issues/63#issuecomment-4988736290)
      (2 passes), both body pointers added, **`planned` applied via a raw `gh issue edit --add-label
      planned`** ×2 (v1's documented write-path gap). Both grounded `origin/main@46888c2`. Sub-agents ×12:
      `github-ops` ×7 (`GATHER_ISSUE` "Gather issue 63", `GATHER_EPIC` "Gather epic 62", "Gather question
      61", `PERSIST_COMMENT` ×2, `PERSIST_BODY` ×2) + `Explore` ×5 reviewers. **Totals: ~190 assistant
      turns, $10.57, 2 prose-gates.** No per-story fan-out (#64 carries 0 plan comments).
- [ ] v2 run captured (epic plan bootstrapped inline; story plan posted) — **completed unaided, 0 gates.**
      **One** `prep_planner.py 66 danwashusen/gh-pipeline-sandbox` state-assembly call; routed
      `story-jit.md` via the shared spine, bootstrapped epic #65's plan inline, and continued to #66's
      story plan in the same session. Both posted: epic [comment `4987685061`](https://github.com/danwashusen/gh-pipeline-sandbox/issues/65#issuecomment-4987685061),
      story [comment `4987685385`](https://github.com/danwashusen/gh-pipeline-sandbox/issues/66#issuecomment-4987685385),
      3 verify passes each. Writes = `gh_persist.py comment` ×2 + `edit-body` ×2 + `edit-labels --add
      planned` ×2. Sub-agents ×6 — **all `Explore` reviewers, zero gather/persist** (scripts called
      directly). Consulted `prep_planner.py … --oq-query "SBX-OQ-21"` (box 4). **~213 assistant messages
      (`result.num_turns`=68), $10.40.** No per-story fan-out (#67 carries 0 plan comments).
- [ ] **Box 3 parity:** the composite handoff carries the `**Open questions:**` line (bug (b)) —
      **YES on BOTH legs; bug (b) did not reproduce.** v2:
      `**Open questions:** (not filed) (audience:developer) provisional-default, #61 (audience:architect)
      provisional-default — see the plan's ## Open questions`. v1:
      `**Open questions:** #61 (audience:architect) provisional-default, (not filed) (audience:developer)
      provisional-default — see the plan's ## Open questions`. Both match `handoff-renderings.md`'s
      format (`#<N> | (not filed) (audience:…) <treatment>, … — <trailing summary>`), both in the
      planner's own treatment vocabulary (`provisional-default`, never the drafter's set), both with the
      trailing pointer. **Why v1 passed:** `9e4222e` had already landed the composite worked example in
      v1's own `references/handoff-renderings.md:56` — the fix the
      [[planner-handoff-oq-composite-gap]] note recorded as the "worked-example half". Entry **order**
      differs (v1 `#61` first, v2 body-order) — the line is explicitly free-form, order is not
      contractual. **Not an explained divergence — a clean parity pass.**
- [ ] **Box 4 parity:** the `(not filed)` claim was checked against the tracker before it was recorded
      (`--oq-query` for the newly-detected OQ, or `open_question_candidates` for a body-recorded one);
      a genuinely-filed companion is cited by `#N`, never `(not filed)` (bug (a)) — **YES on BOTH legs;
      the trap was defeated twice.** Both cite `question: #61` for `SBX-OQ-22` and explicitly flag the
      body's claim as stale; both keep `SBX-OQ-21` at `(not filed)`. **v2's evidence:** prep's
      `open_question_candidates` surfaced the #61 group (forbidding `(not filed)` per spine S6) **and**
      it ran `--oq-query "SBX-OQ-21"` for the entry prep reported no group for; its plan records *"a
      tracker de-dup search for `SBX-OQ-21` returned no candidate on 2026-07-16"*. **v1's evidence:** it
      named #61 in its **first** stall message, before any resume — i.e. it ran the SKILL.md:102 mandated
      re-search unaided. Both also keep each `## Open questions` treatment consistent with its
      `## Risks & watchpoints` entry (v2 says so per-entry), avoiding the secondary label-mismatch defect
      [[planner-oq-tracker-search-miss]] recorded.
- [ ] Plan comment(s) schema-identical; `## Epic contract` cross-consumed by the evaluator/Dimension-8 —
      **YES.** A normalized skeleton diff (twin titles / timestamps / short-sha / issue numbers masked) is
      **empty** for *both* pairs. Epic #62 vs #65 — identical ten-section set in identical order:
      `## Approach` · **`## Story breakdown`** · **`## Story contracts`** · **`## Integration strategy`** ·
      `## Doc grounding` · `## Architecture decisions` · `## Changes (file-level)` · `## Test plan` ·
      `## Risks & watchpoints` · `## Open questions`; **no `## Phases`** on either (correct for an epic).
      Story #63 vs #66 — identical eight-section set in identical order: `## Approach` ·
      **`## Epic contract`** · `## Doc grounding` · `## Architecture decisions` · `## Changes (file-level)` ·
      `## Test plan` · `## Risks & watchpoints` · `## Open questions`. Both stories put the
      `**Epic:** #<N> — <title>` backlink as the **first line after the marker** (never above it), then
      the planned-at line; both `## Epic contract`s are `[epic-plan: #<N>]`-cited with `Delivers` +
      `Consumes: (none)` (head story, no delivery log yet). Footers are byte-identical but for the
      review-pass count (v1 story 2, v2 story 3) — free prose. *Cross-consumption:* `prep_resolver.py`
      (fresh clone per issue) parses **both** story plans identically — `plan.present=true`,
      `plan.sha=46888c2`, `comment_id` = 4988736290 (v1) / 4987685385 (v2) — and routes `story/fresh →
      story.md` on each, i.e. the downstream resolver consumes the v2 artifact as it does the v1.
- [ ] **Box 1 parity** (not a listed box; recorded for completeness): planned-at SHA == the grounding SHA
      — **YES, exact, on all four plans.** v2's `read_workspaces.grounding.sha` =
      `46888c28c0921c1e4c0ce31b7938af96218115c0`; every footer (both legs, epic + story) records
      `origin/main@46888c2`, the 7-hex prefix. **Row recorded: `story-parent-epic-bootstrap`** — no
      `epic/62-*` or `epic/65-*` branch existed, so `plan_ref` fell back to `main` on both legs.
- [ ] Divergences (each traced to a PRD § / an explained gap above / a filed defect):
      - **D1 — state-assembly + write mechanism (EXPLAINED; the documented v1→v2 cutover).** Reproduces
        scenarios 1/2's D1 verbatim on the composite route: v1 assembles via `github-ops` `GATHER_ISSUE` +
        `GATHER_EPIC` and writes via `PERSIST_COMMENT` / `PERSIST_BODY` + a **raw `gh issue edit
        --add-label planned`**; v2 assembles via one `prep_planner.py` facts block and writes via
        `gh_persist.py comment` / `edit-body` / **`edit-labels`**. Same persisted artifacts. Not a defect.
      - **D2 — handoff `Next:` namespace (EXPLAINED; by design).** v1 → `/github-pipeline:github-issue-resolver
        #63`; v2 → `/github-pipeline:resolver #66`. Each generation routes to its own resolver. Not a
        divergence to chase.
      - **D3 — footer/pointer author self-attribution reads `github-issue-planner` on *both* legs
        (COSMETIC; identical, no parser reads it).** Reproduces scenarios 1/2's D3 on the composite route.
        Identical on both ⇒ not a v1↔v2 schema divergence. Same optional future cleanup; not run-failing.
      - **D5 — v1 has no *routing-time* composite path: 2 prose-gates vs v2's 0 (EXPLAINED by the v2
        playbook split; the gate check is NOT comparable under this harness).** v1's composite guidance
        **does exist** — `references/handoff-renderings.md:56` states the inline epic-plan bootstrap
        verbatim ("a reasonable judgment call, not a documented default path"). But SKILL.md:450 force-reads
        that file only *"before composing the handoff"* (Step 12), so the instruction cannot inform the
        **Step-3 routing decision it describes**: at routing time v1 has no guidance in context, so it
        stops and asks. v2 fixed exactly this by placing the bootstrap in `story-jit.md` — the playbook
        read *at route time* — which is why v2 routed unaided. This is the architecture change working, not
        a v2 regression. **Consequence for the protocol's "same genuine decisions gated" check: 0 vs 2 is
        not a comparable result.** Per scenario 2's harness finding, `claude -p` exposes no
        `AskUserQuestion` (both legs' tool-call count is literally 0), so a v1 gate manifests as a
        turn-ending prose question while v2 routes around — and here v1's *first* stall is **structural,
        not fixture-induced**, so no 0-gate fixture can remove it. The v1 artifacts above exist only
        because the operator supplied two answers v2 never needed; they are sound for the **schema/box-3/
        box-4 comparisons** but they are **not** evidence of gate parity.
      - **D6 — `prep_planner` is not re-runnable within one clone: its own `.gitignore` write trips its own
        `ROOT_DIRTY` guard (FILED DEFECT; v2-side, hit the live leg).** `scripts/workspace.py`'s
        `_ensure_gitignore_entry` (called at `workspace.py:579`/`:649`) creates `<root>/.gitignore`
        containing `.worktrees/`; `workspace.py:281` then raises `ROOT_DIRTY` because `git status
        --porcelain` is non-empty. So the **second** `prep_planner.py` call in a clone fails on dirt the
        **first** call created. This is not just an operator gotcha (it is the one
        [[s13-scenario2-epic-parity]] recorded) — **it changed a live leg's behaviour**: the v2 session
        tried to prep epic #65 during the composite bootstrap, hit `ROOT_DIRTY`, and fell back to
        `gh_gather.py` + raw `gh issue view` reads, reporting the cause itself in its handback. Verified
        post-run: `clone-v2` still shows `?? .gitignore` containing `.worktrees/`. **Scope:** only bites a
        consuming repo with no committed `.gitignore` (the sandbox has none). **Not run-failing** — v2's
        artifacts are correct and the router's *sole* state-assembly call is still the one prep on the
        story (the epic prep was an extra the playbook doesn't ask for; `story-jit.md` says to bootstrap
        "inline against `facts.story`"). Needs either an ignore of self-authored `.gitignore` dirt in the
        root check, a `.gitignore` write deferred out of the root, or an explicit re-runnable contract.
      - **D7 — `open_question_candidates` omits empty groups, so absence is ambiguous (RECORDED; no
        artifact divergence).** `_build_open_question_candidates` appends a group **only** when the search
        returns matches, so a body-recorded OQ with no candidate is indistinguishable in the facts block
        from one never searched. Spine S6 tells the playbook to consult `facts.open_question_candidates`
        for body-recorded entries and `--oq-query` only for **newly-detected** ones — but v2, unable to
        prove the empty case from the facts alone, ran `--oq-query "SBX-OQ-21"` for a **body-recorded**
        entry anyway. That is defensively correct and satisfies the bug-(a) rule (which permits
        `(not filed)` only on a search that returned nothing), but it is an extra call the spine's own
        division of labour doesn't predict. Consider emitting empty groups (`candidates: []`) so
        "searched, none found" is a positive fact.
      - **D8 — entry shape tuple (v1) vs dict (v2) (BY CONSTRUCTION, operator-supplied; not a schema
        divergence).** v1's plans pin the entry as a tuple `(event, payload)` because the operator answered
        its gate with **"1"**, v1's own recommendation; v2's pin the dict `{"event": …, "payload": …}`,
        chosen unaided. Free-prose content, identical schema — the skeleton diffs are empty. **The
        underlying judgment divergence is the open question D5 leaves behind:** v1 held that precedent
        cannot settle dict-vs-tuple and the choice is gate-worthy (factually right that precedent is
        silent — no `src/*.py` module has module-level state, and `architecture.md` §3 fixes the module
        shape but not the data shape); v2 pinned it and cited `[prd.md §2]`, but that citation supports
        only the *no-timestamp* half and, unlike every other decision in the same section, names **no
        rejected alternative**. Whether that is v2 correctly declining to gate an internal choice (spine S4
        gates only a decision with a **user-visible** consequence; S5 makes pinning field shapes the
        planner's job) or v2 silently resolving a genuine design decision (the mirror of Dimension 10's own
        check) **cannot be settled headlessly** — v1 blocks and v2 proceeds either way. Flagged for the
        operator, not resolved here.

**Verdict: recorded, not decided — the operator owns the go/no-go on D5/D8.** What is established: both
legs, on the composite case, ground at `origin/main@46888c2` on the **`story-parent-epic-bootstrap` row**,
bootstrap the epic plan inline, post **schema-identical** epic + story plans (empty skeleton diffs, both
pairs; `## Epic contract` + `**Epic:**` backlink correct; no `## Phases`; no per-story fan-out), add body
pointers, apply `planned`, and emit a valid story `## Handoff`. **Box 3 passes on both** — bug (b) did not
reproduce, `9e4222e` having already fixed v1's worked-example half. **Box 4 passes on both** — the
bug-(a) trap was defeated twice, each citing `#61` over the body's stale `(not filed)`, v2 via
`open_question_candidates` + `--oq-query` and v1 via its own mandated re-search. **Box 1** holds exactly on
all four plans; **v2 startup = 1** `prep_planner.py` state-assembly call; the resolver reader
cross-consumes both story artifacts identically. D1/D2/D3 are the familiar cutover / by-design / cosmetic
trio. **Two items need an operator call before this scenario is called clean: D6** (a real, live-confirmed
`prep_planner` defect) and **D5/D8** (gate parity is 0 vs 2 and *not comparable under this harness*, and
the entry-shape judgment divergence it exposes is unfalsifiable headlessly). (Boxes left unticked —
operator-owned.)

### Scenario 4 — Revise

Target: an issue with a prior `<!-- implementation-plan:v1 -->` plan (a SOFT case: only doc-grounding /
un-shipped phases changed; and, if a draft PR with shipped phases exists, a HARD case for the reconcile
path). Expected v2: `mode: revise` → `revise.md`, re-ground focused on what changed, reconcile the DoD
ticks against `facts.revise.phase_tracker`, diff-show + the SOFT (**Apply** / **Cancel**) or HARD
(**Start fresh** / **Apply in place anyway** / **Cancel**) gate, repost via `--delete-marker-id`, refresh
the pointer URL. On HARD Start-fresh: `## Predecessor` posted, DoD un-ticked to the predecessor form, and
the superseded PR closed via `gh_persist.py close-pr` with the staged `Re-plan superseded this PR` marker
comment (the S13 second-pass op — the gate already fired at the three-way confirm above; this executes
the already-gated decision).

- [ ] v1 run captured (SOFT and/or HARD).
- [ ] v2 run captured (reconciliation diff computed; correct SOFT/HARD gate offered).
- [ ] Reposted plan schema-identical; stale comment deleted via `--delete-marker-id`; pointer URL
      refreshed.
- [ ] **Box 1 parity:** the refreshed plan's planned-at SHA == the new grounding SHA.
- [ ] HARD path (if exercised): `## Predecessor` + predecessor-annotated DoD; superseded PR closed with
      the byte-exact `Re-plan superseded this PR` marker, posted as the PR's **close comment** (confirm
      via `gh pr view <PR#> --json comments` or the GitHub UI — not `--json body`, per the latent-v1-bug
      finding above; no v2 resolver code reads this detection yet, so there is nothing to cross-consume
      here this step — the check is that `close-pr` posted the marker to the right field).
- [ ] Divergences.

## Go/no-go (recorded, not decided)

To be filled by the operator after the four scenarios run. Go criteria: (1) all four scenarios recorded
with zero unexplained divergences; (2) validators + census green (compileall, `tests/run.py`,
shellcheck, the contract-token census, `tests/test_subagent_prompts.py`); (3) the offline halves of
boxes 1/3/4 met (plan schema byte-clean, the bug-(b) example present, the bug-(a) rule written +
grep-tested).
