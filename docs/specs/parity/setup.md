# Parity — setup (v1 `github-pipeline-setup` → v2 `setup`)

> Records the [implementation.md](../../implementation.md) **S17** parity run per the
> [parity protocol](../../implementation.md) (`## The parity protocol`) and [prd.md §9.5](../../prd.md).
> The offline work (router + the one flow + `references/block-authoring.md` + `prep_setup.py` + tests)
> landed in S17's implementor pass; the **two live landing scenarios below are operator-gated** — the
> §8.2 landing gate is interactive, so an operator runs them on the sandbox
> ([SANDBOX.md](../../../tests/SANDBOX.md)) and fills each result section. A v1 skill directory is
> deleted only after its v2 replacement passes this protocol (S20).

## Line-count metric ([prd.md §10](../../prd.md); S17 DoD)

The success metric: the prompt a session loads (router + the one playbook it executes) is **at most
half** the v1 `SKILL.md` line count. v1 `github-pipeline-setup/SKILL.md` = **338 lines**
([baseline.md](../baseline.md) §1) → bar = **169** (floor of 338/2).

| File | Lines |
|---|---:|
| `skills/setup/SKILL.md` (router) | 83 |
| `skills/setup/playbooks/setup-flow.md` (the one flow) | 85 |
| **router + playbook (the loaded set)** | **168** |

**168 ≤ 169** ✅ — **1 line of headroom, test-enforced**
(`RouterStructureTests::test_router_plus_playbook_at_most_half_v1` fails the moment router + playbook
exceeds 169). Per the S13/S16 precedent (`docs/specs/parity/planner.md` / `researcher.md`): **any future
addition to `SKILL.md` or `setup-flow.md` must be offset elsewhere** (trim a line, or move content to
`block-authoring.md`, which is read on demand and not counted). Router **83 ≤ 150** ✅ (architecture.md
§9 size bar). References are on-demand and not part of the loaded-prompt metric; recorded for
completeness: `references/block-authoring.md` 495 (the carried authoring spec — canonical block forms
byte-identical to `docs/specs/examples/config-blocks.md`, plus the detection heuristics, stack-profile
scope, legacy mapping, and the labeled Swift+Rails worked examples).

## The prep decision (the §9 house-default call the Work records)

**`prep_setup.py` — the house default (a small prep), not direct composition.** Setup does **no** `gh`
gather (its subject is local Markdown, not GitHub state), so its prep is thinner than the five pipeline
preps — but the inventory is still a genuine **one-call, multi-source** assembly (§9.2): two candidate
files' `config_block.build_list`, the per-marker present/legacy/malformed/missing classification, the
legacy `pr-evaluator-health-checks` signal, the user-owned `claude-code-stack-profile` interior staged
for re-ingest, the same-marker-in-both-files ambiguity, the target-file suggestion, the tool-presence
preflight, and `root.sha`. Composing that inline in the router body would be exactly the multi-subprocess
chain (~5+ `config_block.py list`/`read` calls + `shutil.which` probes + the classification) the prep
pattern (S8 §5.1) exists to keep out of the router — so a prep is the correct call even without a routing
decision to compute. It composes `config_block.py`'s `build_list` / `build_read` cores **in-process**
(architecture.md §2; S8 pattern lock), runs `shutil.which` (pure Python — hermetic, no subprocess) for
tool presence, and makes the one prep-owned direct `git rev-parse` call every prep already establishes.

**The one place setup's prep differs from the pipeline preps:** it computes **no `suggested_playbook`**
(setup has a single linear flow — no mode fork), and it emits **no `needs_decision`** — it makes no `gh`
call (so no `AUTH_REQUIRED`), and a malformed (`dup`/`open`) block is reported as an inventory **fact**
(`class: "malformed"` + an `attention` line) the router surfaces via `AskUserQuestion`, matching v1's
"malformed input is refused, not guessed" (the router asks; prep never guesses). The report-only
`gh auth status` readiness line stays a router-level environment probe (a live `gh` call, never a
block-authoring gate), keeping the prep free of any `gh` call and therefore hermetically testable.

## The playbook-split decision (the §5-bar decision the Work records)

architecture.md §5 "parameterize before you playbook": a playbook exists only for flows that differ in
**actions taken**, not values. Setup is a **single linear flow** — inventory → detect → propose → stage
→ validate → land → summary — with **no mode fork** (no broad/targeted/revise, no epic/story). The two
apparent branches are **not** routes:

- **Legacy migration** is a *fact gate* inside step 5 (`facts.inventory.legacy_health_checks.present` +
  the operator's opt-in), not a mode — the same flow, one extra conditional step.
- **Landing approve/decline** is a *runtime gate* inside step 7, not a route.

So the split is **router + one playbook** (`setup-flow.md`), with the heavy per-block authoring detail
(shapes, detection heuristics, the merge-policy interview, the worktree/stack-profile research-and-propose
lanes, the legacy mapping, the two worked examples) in the on-demand `references/block-authoring.md` — the
reference read is *forced* at step 3 (the v1 forced-Read discipline preserved), so the per-block shapes
are in context before anything is proposed, without loading them into every session's base prompt. A
spine+variants decomposition (the researcher/planner shape) would be inventing a mode fork setup does not
have — it would fail §5's "parameterize before you playbook."

## The disable-model-invocation frontmatter — ADJUDICATION RECORD (S17, post-review correction)

**Ruling: `skills/setup/SKILL.md` carries NO `disable-model-invocation` key. Setup stays
model-invocable.** The implementor's first pass added the key, reading the plan step's "DoD"
(`disable-model-invocation: true retained; grep gates; parity recorded`) at face value; review caught
that the correct adjudication runs the other way, on three independent grounds:

1. **v1 never had the key.** [`docs/specs/setup.md`'s "Known bugs" §1](../setup.md) already
   pre-analyzed this: `skills/github-pipeline-setup/SKILL.md` frontmatter carries only `name`/`model`/
   `effort` — no `disable-model-invocation` — so there is nothing to "retain." The DoD clause's
   "retained" wording is the party in error, a documented over-generalization to **correct**, not to
   perpetuate into the v2 file.
2. **CLAUDE.md:73 deliberately excludes setup from the standalone-tools' `disable-model-invocation`
   list.** `CLAUDE.md`'s "Four skills sit outside the pipeline conveyor" paragraph names all four
   non-pipeline tools (`github-pipeline-setup`, `doc-reviewer`, `open-questions`, `question-resolver`)
   in one sentence, but its `disable-model-invocation: true` parenthetical (line 73) names only
   `doc-reviewer`, `open-questions`, and `question-resolver` — `setup` is conspicuously absent from
   that list, matching its actual v1 frontmatter. This is not an oversight CLAUDE.md needs fixing for;
   per this repo's editing conventions, CLAUDE.md is authoritative over a step's DoD prose when the two
   conflict.
3. **Setup's own design is trigger-heavy, not report-then-apply-only.** Its `description` carries a
   long list of natural-language trigger phrases ("set up the pipeline", "the resolver doesn't know
   how to run my tests", "migrate my health-checks block", …) specifically so a session or another
   skill's failure mode can route here automatically — disabling model-invocation would silently break
   that surface for no v1-parity or safety gain. The DoD clause's "retained" wording is satisfied under
   this corrected interpretation: v1 never had the key, so **not adding it** is what "retained"
   (v1-parity) actually means for this field.

**Setup is the exception, not the template — a rule for S18/S19.** The **other three** standalone
tools — `doc-reviewer`, `open-questions` (`question-sweep`), `question-resolver` — DO carry
`disable-model-invocation: true` in both v1 and their v2 renderings, and their future v2 cutovers (if
still pending) must keep that key. Setup's `disable-model-invocation`-free frontmatter is not a
precedent to copy onto them; it is specific to setup's trigger-heavy, always-safe-to-invoke design and
its explicit CLAUDE.md:73 carve-out. The §8.2 landing gate is setup's actual safety guard against its
new PR-opening power (operator-gated, offer-once, decline leaves zero git actions) — that gate, not a
disabled auto-trigger, is what keeps an automatically-invoked setup run safe.

Pinned by `tests/test_setup_routing.py::RouterStructureTests::test_router_exists_and_frontmatter_pins`
(asserts the key is **absent**, with the same citations inline so a future author doesn't "fix" it
back).

## Byte-identity + carried-fidelity (DoD boxes 1 + 4, offline half)

- **Box 1 — block byte-identity.** Every marker setup writes (the 9 machine-parsed blocks + the
  `github-pipeline-config` header + `claude-code-stack-profile` + the `worktree-setup`/`-teardown` pair),
  written via the skill's prescribed `config_block.py upsert` invocation, reproduces its canonical form
  **byte-for-byte** against `docs/specs/examples/config-blocks.md` (prd.md §7, row 11) —
  `BlockByteIdentityTests::test_config_block_upsert_reproduces_each_canonical_form`. Separately, the
  skill's own `references/block-authoring.md` schema fences are byte-identical to that S1 capture (never
  restated divergently) — `test_reference_schema_fences_match_the_s1_capture`. `block-authoring.md` is
  **carried** from v1 with exactly two adaptations, no fence touched: (1) the source-of-truth line's v1
  `§P3.1`/`§P2` anchors (resolver-local, forbidden under `skills/setup/`) replaced by the v2 skills'
  named surfaces; (2) the merge-policy "Not detected" bullet extended with the `docs: auto`-style option
  (below).
- **Box 4 — legacy health-checks split.** The `pr-evaluator-health-checks` → `pr-evaluator-static-checks`
  + `pr-evaluator-test-target` split, then `remove`, reproduced deterministically through
  `config_block.py` (the single write path) —
  `LegacyHealthChecksMigrationTests::test_split_migration_mechanics`. `prep_setup` detects the legacy
  block in the inventory (`test_prep_setup.LegacyHealthChecksMigrationTests` covers the detection half).
- **The merge-policy `docs: auto`-style option.** The DoD's "merge-policy proposal includes a `docs: auto`
  style option" is implemented as an **interview framing over the canonical `standard`/`story` keys** (a
  doc/config PR — including the ones `setup`/`question-sweep`/`doc-reviewer` land — classifies as
  `standard`; there is no distinct evaluator `docs` PR-type). A literal `docs:` block key would (a)
  diverge from the S1-frozen `pr-evaluator-merge-policy` shape (breaking box 1) and (b) require an
  evaluator change (out of scope; the evaluator only classifies `standard`/`story`/`epic-integration`).
  So `block-authoring.md` names the `docs: auto`-style option and holds the block keys to
  `standard`/`story` — `MergePolicyDocsAutoTests`. **Flagged for the orchestrator** as a resolved
  spec-ambiguity: if a literal new `docs` merge-policy key was intended, it needs an evaluator-cutover
  authorization + an S1-capture amendment, neither in S17's scope.

## Offline validators (S17 DoD, implementor half)

- `python3 -m unittest tests.test_prep_setup` — 11 tests: marker classification ×4 (present / legacy /
  malformed / missing); legacy-block detection; the stack-profile re-ingest `base_path`; same-marker-both-
  files + the split target suggestion; preflight tool presence + `root.sha`; the non-git-repo degradation;
  envelope conformance on the (only, no-decision) emitting path.
- `python3 -m unittest tests.test_setup_routing` — 23 tests: the structural bars (router ≤ 150; router +
  playbook ≤ 169; one playbook); frontmatter pins carried verbatim from v1 (opus / medium, **no**
  `disable-model-invocation` key — the adjudication above); the
  contract-token gate (0 `github-ops`, 0 `github-pipeline:github-`, 0 `GATHER_`/`PERSIST_`, 0 `§P`, 0 raw
  gh writes in fences, 0 `w/`); the v2 forward pointers (`github-pipeline:drafter`/`:resolver`); box-1
  byte-identity (upsert-reproduces + reference-matches-S1); box-4 legacy split mechanics; the §8.2 landing
  gate language (offer-once; decline → 0 git actions + workspace path + ready-to-run commands); the
  `docs: auto`-style option + canonical keys; the `--dry-run` create-pr envelope; stack-agnostic loaded
  prompt + the labeled ≥2-stack reference.
- Contract-token census: re-run of the S1 baseline command shows **zero cross-skill drops** (the frozen
  v1 `skills/github-pipeline-setup/` rows are all intact); every delta is a **list addition** under
  `skills/setup/` (all 11 config-block markers preserved verbatim; the v2 forward routes
  `github-pipeline:drafter`/`:resolver`; the `§8.1`/`§8.2` prd anchors). Distinct-token count: **85 → 87**
  (+2, exactly `§8.1`/`§8.2` — verified by re-running the census with and without `skills/setup/`). The
  true pre-S17 baseline is **85**, not the `docs/specs/baseline.md` §5.3 figure of 81 recorded at S7 —
  that number is the count as of S7's own cutover and does not reflect the additions every cutover from
  S9 through S16 made since; 85 is what the census command actually returns against the tree immediately
  before this step's changes. The v1-only `§P2`/`§P3.1` rows survive in the frozen v1 dir and are
  intentionally absent from the v2 `block-authoring.md` (resolver-local anchors, retired per the census's
  "v1-only tokens expected to retire" bucket).

## Live parity scenarios (operator-gated — fill each result)

Run v1 `github-pipeline-setup` and v2 `setup` on identical starting state in the sandbox, then diff the
written config blocks (and, for v2, the landing outcome). **The §8.2 landing gate is interactive**
(`AskUserQuestion`), so these are operator-run. Harness note: headless `claude -p --plugin-dir` (the
operator runs via `!`; auto-mode blocks `AskUserQuestion`) with 0-gate fixtures where a gate would
otherwise stall. **Sandbox hygiene:** the sandbox `CLAUDE.md` has been canonical since `6c5f669`, so a
plain setup run proposes few/no diffs — **each scenario deliberately seeds a drift** (below) so the
proposal set is non-trivial; the SANDBOX config-block incident (`ae283af`, bare forms parse empty) is the
cautionary tale for the seed. Don't pre-run `prep_setup.py` in a run clone (S13/S15 learning — a pre-run
prep can dirty the root and change what the run sees). Reset the seeded drift between the two legs.

### Scenario 1 — landing approved

Seed a non-trivial drift in the sandbox (e.g. **remove** the `<!-- issue-resolver-fast-checks -->` block
and **stale** one command in `<!-- pr-evaluator-static-checks -->`, or add a legacy
`<!-- pr-evaluator-health-checks -->` block), so setup detects real work. Run v2 `setup`, approve every
per-block confirm, and **approve the landing gate**. Expect: the reconciled blocks staged in a work
workspace, then a PR opened whose **body summarizes the block diffs**; the project root stays clean and
on `main` throughout.

- [ ] **D1 (binds parity: written blocks)** — the blocks setup writes are byte-identical to the v1
  canonical forms (`docs/specs/examples/config-blocks.md`); v1 and v2 produce the same reconciled block
  bodies for the seeded drift.
- [ ] **D2 (binds parity: the §8.2 landing)** — on approve, a PR is opened with a body summarizing the
  block diffs (which markers written / reconciled / migrated, in which file); the PR head is
  `setup/config-<slug>`, base `main`.
- [ ] **D3 (root hygiene)** — `git -C <root> status` is clean and on `main` **throughout** the run (all
  writes happened in the workspace, never the root — prd.md §8.1/§8.2).
- [ ] **D4 (v2 process)** — v2 startup = exactly one `prep_setup.py` call; block I/O = `config_block.py`
  only (0 hand-rolled `sed`/`Edit`/`Write` on a marker block); the landing = `workspace.py ensure --work`
  + `gh_persist.py create-pr`; 0 `github-ops`.
- **Result: PASS** (v2 leg, 2026-07-20). Run interactively (`claude --plugin-dir <this branch> --model
  opus`, cwd = a fresh sandbox clone) — the §8.2 gate is a real `AskUserQuestion` card, so this leg was
  operator-driven end to end, not headless. Session transcript:
  `~/.claude/projects/…-scratchpad-s17-scen1-clone/31c3eb73-….jsonl`.

  **Fixture / seeded drift** — sandbox `main` moved `6c5f669 → 1b048ba` (`seed(S17-parity-scen1)`,
  **pushed**): `<!-- issue-resolver-fast-checks -->` removed entirely; `<!-- pr-evaluator-static-checks -->`
  staled to `python3 -m flake8 --max-line-length 100 .` (ungroundable — no manifest declares it). The
  baseline's legacy `<!-- pr-evaluator-health-checks -->` and the absent `claude-code-stack-profile` came
  along for free, so the run exercised all four dispositions: **written / reconciled / migrated+removed /
  seeded**. The drift must be **pushed**, not just committed locally: `workspace.py ensure --work` forks at
  `origin/<base>` and gates on `merge --ff-only origin/main`, so a local-only drift commit yields
  `ROOT_DIVERGED` *and* a workspace without the drift. Per-block confirms: all four answered with the
  recommended option; landing gate: **approved**.

  - **D1 — PASS (byte-identity half).** All three written blocks parse via `config_block.py read`, and
    `pr-evaluator-health-checks` is correctly absent (exit 3). Both command blocks reproduce the frozen
    `- \`<command>\` — <description>` form from `docs/specs/examples/config-blocks.md` §
    `issue-resolver-fast-checks` / `pr-evaluator-static-checks` byte-for-byte; delimiters one per line.
    The **v1-vs-v2 half was not exercised** — this leg was v2-only per the operator's PASS definition
    (a real PR opens / root stays clean / blocks parse canonically). Note for a future v1 leg: v1
    `github-pipeline-setup` has no landing step at all, so only the *block bodies* are comparable.
  - **D2 — PASS.** [PR #91](https://github.com/danwashusen/gh-pipeline-sandbox/pull/91), head
    `setup/config-sandbox`, base `main`, workspace commit `09cecd3`. The body summarizes the block diffs
    exactly as specified: a `## Block diffs` marker/file/disposition table (written / reconciled / removed
    / seeded), a per-marker rationale section each, `## Untouched` naming the eight already-correct
    markers and why no `github-pipeline-config` header was proposed (target file is `CLAUDE.md`, not
    `COMMANDS.md`), `## Validation`, and `## Known gaps`.
  - **D3 — PASS at every phase boundary, with one transient (Div-2).** `git -C <root> status` clean and
    on `main` at every checkpoint — before the run, after workspace creation, and after the PR opened
    (root HEAD never left `1b048ba`). All edits landed in `.worktrees/setup/config-sandbox`.
  - **D4 — PASS.** 13 Bash calls total, **0** `Task`/`Agent` sub-agents, **0** `Edit`/`Write`/
    `NotebookEdit` tool calls, **0** `sed -i`, **0** `github-ops` (the single transcript hit is the agent
    roster in the system prompt, not an invocation). Startup = **one** `prep_setup.py` (two attempts —
    see Div-1). Block I/O = `config_block.py` only (3 `upsert` + 1 `remove`, the remove issued only after
    both replacements were written). Landing = `workspace.py ensure --work setup/config-sandbox --base
    main --root <root>` → `gh_persist.py create-pr`. The one live `gh` call before the landing was the
    report-only `gh auth status` readiness probe (router-level environment probe, not a block gate) —
    prep itself made no `gh` call, as designed.

  **4 divergences (none blocks the scenario; Div-1 is a real defect to fix):**
  1. **Div-1 — `scripts/prep_setup.py` and `scripts/workspace.py` are missing the executable bit.** The
     skill's prescribed `${CLAUDE_PLUGIN_ROOT}/scripts/prep_setup.py` invocation exits **126**
     (`permission denied`); the session self-recovered with `python3 <path>`. Every other prep
     (`prep_drafter/evaluator/planner/researcher/resolver.py`) is `0755` — these two are `0644`. A real
     S17 packaging defect, **TO FIX** (`chmod +x`); deliberately *not* fixed in this commit so Scenario 2
     runs under identical conditions.
  2. **Div-2 — the run briefly dirtied the root itself.** A step-3 grounding command
     (`python3 -m compileall -q .`, run to prove the candidate command is viable) wrote `src/__pycache__/`
     into the read-only root. The session **detected and removed it unprompted** in the very next call,
     before any workspace op, so `workspace.py ensure` returned `ok` rather than `ROOT_DIRTY`. Root
     hygiene held at every phase boundary but not literally every instant. Worth a playbook note that
     step-3 grounding is inference from repo evidence, not command execution in the root.
  3. **Div-3 — confirm/diff ordering.** Playbook §4 specifies *show the diff, then gate*. The run gated
     **first** (one 4-question `AskUserQuestion` card, each option carrying the exact proposed block
     bytes as a preview), then rendered the full diffs and proceeded to stage without a second card.
     "Nothing is written silently" is satisfied in substance — the operator approved exact bytes — but
     the order is inverted relative to §4.
  4. **Div-4 — re-added block position.** `issue-resolver-fast-checks` was re-appended at the **end** of
     `CLAUDE.md` rather than restored to its original slot after `issue-resolver-test-target` — the
     `config_block.py upsert` append semantics for a missing marker. Cosmetic; parse is unaffected.

### Scenario 2 — landing declined

Same seeded drift as Scenario 1 (reset first). **State Scenario 1 left behind:** the drift commit
`1b048ba` is still on sandbox `main` (so the drift needs no re-seeding) and PR #91 / branch
`setup/config-sandbox` are **open** — close the PR and delete that remote branch before this leg, or
`gh_persist.py create-pr` has nothing to prove when it is *not* called. Use a **fresh clone** (Scenario 1's
carries a `.worktrees/setup/config-sandbox` workspace and a local branch of the same name, which would let
`ensure` reuse instead of create). Run v2 `setup`, approve the per-block confirms, but
**decline the landing gate**. Expect: the reconciled blocks are staged in the workspace, but **no commit,
no push, no PR** occurs; the summary reports the **workspace path** and the **ready-to-run landing
commands** so the operator can land by hand later.

- [x] **D1 (binds parity: decline path)** — no commit, no push, no PR is created on this leg (verify:
  no new branch on the remote, no open PR, no new commit in the workspace's log beyond what the operator
  would add by hand).
- [x] **D2** — the summary reports the workspace path (`.worktrees/setup/config-<slug>`) and the exact
  ready-to-run landing commands (`git -C <workspace> add`/`commit`, `git -C <workspace> push -u origin
  <branch>`, then the `create-pr` command).
- [x] **D3 (root hygiene)** — `git -C <root> status` clean and on `main` throughout.
- [x] **D4 (v2 process)** — the staged blocks are byte-identical to Scenario 1's; the only difference is
  the landing outcome (0 git actions vs the PR). 0 `github-ops`.
- **Result: PASS** (v2 leg, 2026-07-22). Run interactively (`claude --plugin-dir <this branch> --model
  opus`, cwd = a **fresh** sandbox clone — Scenario 1's carried a `.worktrees/setup/config-sandbox`
  workspace `ensure` would have reused) via the tmux harness ([[s17-scenario1-landing-approved]] recipe),
  so the §8.2 gate was a real `AskUserQuestion` card answered by hand. Session transcript:
  `~/.claude/projects/…-scratchpad-s17-scen2-clone/c314f37d-….jsonl`.

  **Prep / fixture** — the drift commit `1b048ba` is still on sandbox `main`, so no re-seeding; **PR #91
  and its `setup/config-sandbox` branch were closed/deleted first** (`gh pr close 91 --delete-branch`)
  so `gh_persist.py create-pr` had nothing to prove when *not* called. Fresh clone at `1b048ba`, no
  worktrees. Same four dispositions as Scenario 1 (fast-checks missing / static-checks staled to
  `flake8` / legacy `health-checks` present / `stack-profile` absent). Per-block confirms: all three
  answered with the recommended option; landing gate: **declined** (option 2 "No, leave staged").

  - **D1 — PASS.** Transcript grep: **0** `git commit`/`git push`/`gh pr create`/`create-pr` in any
    Bash tool-use, **0** `gh_persist.py`. Workspace branch `setup/config-s17-scen2` sits at `1b048ba`
    (= main HEAD, **no commit on top**); `git status` shows only `M CLAUDE.md` (staged edits in the
    working tree, never committed). No `setup/config-*` ref on the remote; no open `setup/config` PR.
  - **D2 — PASS.** The closing summary states "Landing outcome: declined — nothing committed, pushed, or
    opened," reports **Workspace: `.worktrees/setup/config-s17-scen2` (branch setup/config-s17-scen2,
    based on main)**, and lists the exact ready-to-run commands: `git -C "$WS" add CLAUDE.md` →
    `git -C "$WS" commit -m "…"` → `git -C "$WS" push -u origin setup/config-s17-scen2` → the
    `gh_persist.py create-pr … --base main --head setup/config-s17-scen2` invocation.
  - **D3 — PASS.** Clone root stayed on `main` at HEAD `1b048ba` with a clean `git status` throughout;
    every write landed in `.worktrees/setup/config-s17-scen2`.
  - **D4 — PASS.** Staged machine-parsed blocks reproduce Scenario 1's reconciled forms byte-for-byte:
    `pr-evaluator-static-checks` = `compileall` prepended ahead of `flake8` (fail-fast order),
    `issue-resolver-fast-checks` written as its mirror, legacy `pr-evaluator-health-checks` removed
    (0 occurrences), `claude-code-stack-profile` seeded. Block I/O = `config_block.py` only (3 `upsert`
    + 1 `remove`, in one compound Bash call); **0** `sed -i`, **0** `Edit`, **0** marker-file `Write`.
    **0** `github-ops` / `Task` sub-agents (the 2 `github-pipeline:github-ops` transcript hits are the
    system-prompt agent roster, not invocations). 10 Bash calls total; startup = 1 `prep_setup` (2
    attempts — Div-1); `workspace.py ensure` + `lint setup`/`lint teardown`; 1 report-only `gh auth
    status`.

  **Divergences (none blocks the scenario):**
  1. **Div-1 — SAME defect as Scenario 1, still unfixed:** `scripts/prep_setup.py` (and `workspace.py`)
     lack the executable bit, so the prescribed `${CLAUDE_PLUGIN_ROOT}/scripts/prep_setup.py` exits
     **126**; the session self-recovered with `python3 <path>`. Reproduced identically — left unfixed
     for this leg by design. **TO FIX now** (`chmod +x` both) — both landing scenarios are complete.
  2. **Div-2 (positive) — diff→gate order correct.** Unlike Scenario 1's Div-3 (gated before rendering
     diffs), this run rendered the full per-block diffs **first**, then presented the confirm card, and
     likewise rendered the staged `git diff` before the landing gate — matching `setup-flow.md` §4's
     specified diff→gate order. Scenario 1's Div-3 did **not** reproduce.
  3. **Div-3 — scratch staged via the `Write` tool.** The three block bodies were staged to
     `/tmp/gh-setup-s17-scen2-clone/*.md` with the `Write` tool (Scenario 1 used bash heredocs). Benign:
     the discipline forbids `Write`/`Edit` on a *marker block*, not on a scratch file (0 marker-file
     writes confirmed); the bodies still reach `CLAUDE.md` only through `config_block.py upsert`.
  4. **Div-4 — branch slug from clone dir.** Head branch is `setup/config-s17-scen2` (slug derived from
     the `s17-scen2-clone` dir) vs Scenario 1's `setup/config-sandbox`. Cosmetic; the decline path opens
     no PR/branch regardless. The `stack-profile` prose is model-authored (SANDBOX.md: no parity check
     depends on its exact content), so its exact wording may differ from Scenario 1's — expected, not a
     parity break.

## Go/no-go (operator)

- [x] Both landing scenarios PASS (or every divergence is adjudicated as an explained v1 defect / fixture
  artifact / v2 enrichment, recorded above). — **Scenario 1 (approved) PASS** 2026-07-20 (PR #91);
  **Scenario 2 (declined) PASS** 2026-07-22 (0 git actions; workspace + landing commands reported). Every
  divergence is adjudicated above: Div-1 (missing `+x` on `prep_setup.py`/`workspace.py`) is a real S17
  packaging defect reproduced on both legs, now fixable; the rest are fixture/method/cosmetic (Scenario
  1's diff-order Div-3 did not even recur).
- **Recommendation: GO.** The offline half (boxes 1 + 4 + the structural/frontmatter/grep gates + the
  scaffold) is implementor-complete and green, and both live landing legs pass on machine-relevant
  parity — approve opens a block-diff PR with the root clean throughout; decline takes **zero** git
  actions and hands back the workspace path + ready-to-run landing commands. The one true defect (Div-1,
  the executable bit) is a one-line `chmod +x` fix that does not affect the skill's behavior or parity.
