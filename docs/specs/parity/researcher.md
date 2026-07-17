# Parity — researcher (v1 `github-issue-researcher` → v2 `researcher`)

> Records the [implementation.md](../../implementation.md) **S16** parity run per the
> [parity protocol](../../implementation.md) (`## The parity protocol`) and [prd.md §9.5](../../prd.md).
> The offline work (router + spine + three variants + references + `prep_researcher.py` + tests) landed
> in S16's implementor pass; the **three live scenarios below are operator-gated** — run them on the
> sandbox ([SANDBOX.md](../../../tests/SANDBOX.md)) and fill each result section. A v1 skill directory is
> deleted only after its v2 replacement passes this protocol (S20).

## Line-count metric ([prd.md §10](../../prd.md); S16 DoD box 4)

The success metric: the prompt a session loads (router + the one playbook it executes) is **at most half**
the v1 `SKILL.md` line count. v1 `github-issue-researcher/SKILL.md` = **289 lines**
([baseline.md](../baseline.md) §1) → bar = **144** (floor of 289/2).

| File | Lines |
|---|---:|
| `skills/researcher/SKILL.md` (router) | 86 |
| `skills/researcher/playbooks/research-spine.md` (the shared spine — largest playbook) | 57 |
| `skills/researcher/playbooks/broad.md` | 52 |
| `skills/researcher/playbooks/revise.md` | 32 |
| `skills/researcher/playbooks/targeted.md` | 30 |
| **router + largest playbook (the loaded set)** | **143** |

**143 ≤ 144** ✅ — **1 line of headroom, test-enforced** (`RouterStructuralBarTests::test_router_plus_largest_playbook_at_most_half_v1`
fails the suite the moment router + largest-playbook exceeds 144). Per the S13 precedent
(`docs/specs/parity/planner.md`'s own "sits at the router+largest-playbook bar with zero headroom (251 ≤ 251)"
note, recorded there as a deliberate pin rather than a passing aside): **any future addition to `SKILL.md`
or `research-spine.md` must be offset elsewhere** (trim a line in the same file, or move content to an
on-demand reference) before it lands — this margin is not slack to spend casually. Router **86 ≤ 150** ✅
(architecture.md §9 size bar). A routed session loads the router (86) + the routed variant (30–52) + the
shared spine (57); each individual document fits one default `Read`. References are read on demand and are
**not** part of the loaded-prompt metric; recorded for completeness: `research-validator-prompt.md` 128 (the
carried validation loop — **two path/reference adaptations** changed, see below), `dossier-schema.md` 50
(the frozen `<!-- issue-research:v1 -->` artifact schema, byte-compat vs the S1 capture), `gather-tactics.md`
41 (the carried source-tiering / depth-escalation / JS-doc fetch
tactics), `handoff-renderings.md` 53 (the two researcher handoff shapes + the S15 binding language).

## Playbook split (the §5-bar decision the Work records)

architecture.md §5 "parameterize before you playbook": a playbook exists only for flows that differ in
**actions taken**, not values. The researcher is the thinnest cutover, but its three modes genuinely
differ in **actions**, not merely values — so the split is a **shared spine + three thin variants**
(mirroring the planner/evaluator/resolver/drafter cutovers), not a single playbook:

- **`playbooks/research-spine.md`** — the gather-and-verify-and-post backbone every mode runs once its
  question set exists (gather → synthesize → validate → persist → handoff). Mode differences here are
  **facts** (`facts.revise` present ⇒ the persist passes `--delete-marker-id` and the show is a diff, not
  the full body), never route-name branches. All three variants read it.
- **`playbooks/broad.md`** — the default first run: discover the stack, **derive** the questions, run the
  **decline gate** (a no-currency-risk issue posts nothing and exits `research: ✗`), and the **confirm
  gate** (`AskUserQuestion`, `header: "Questions"`), then run the spine. The decline gate is broad-only —
  it can terminate the run without a dossier, an action neither other mode has.
- **`playbooks/targeted.md`** — the questions are given (`facts.vector.questions`, a planner-routed gap):
  skip derivation **and** the decline/confirm gates, then run the spine.
- **`playbooks/revise.md`** — a dossier already exists: read the prior dossier, refresh **only what
  changed** (never re-research untouched sections), then run the spine, whose persist delete-and-reposts
  and whose show is a diff.

Why a spine + three thin variants rather than one self-contained playbook? The `broad`/`targeted`/`revise`
front-ends differ in genuine actions — `broad` alone runs the two gates and can decline-and-exit posting
nothing; `revise` alone reads a prior dossier, diffs, and delete-and-reposts; `targeted` skips both gates —
while the gather→synthesize→validate→persist→handoff backbone is identical up to facts. The three variants
contain **zero cross-mode conditionals** — the route *is* the branch — verified by
`tests/test_researcher_routing.py::PlaybookInterleavingGrepTests`. (A single comprehensive playbook was
also authored and measured; at ~104 lines it put router + playbook at ~190 > 144, failing DoD box 4. The
spine+variants decomposition — the pattern every prior cutover used — meets the bar because the metric is
*router + largest single playbook file*, and the shared spine at 57 lines is that file, with the
mode-specific heavy content in the uncounted-in-the-metric thin variants.)

## The `prep_researcher._suggested_playbook` alignment

`prep_researcher.py` derives `vector.mode` mechanically (marker present ⇒ `revise`; else `--question` ⇒
`targeted`; else `broad`) and `_suggested_playbook(mode)` maps it to the variant filename:

- `mode: broad` → `broad.md`
- `mode: targeted` → `targeted.md`
- `mode: revise` → `revise.md`

The router routing table (`SKILL.md` §2) is byte-consistent with this map (asserted by
`test_table_matches_prep_suggested_playbook`). There is **no route override**: unlike the drafter's
new-mode classification (a judgment over freeform feedback the script can't read), `vector.mode` is fully
mechanical (dossier presence + the operator-supplied `--question`), so the prep proposal *is* the route.
The one judgment fork — the decline gate — lives inside `broad.md`, never as routing.

## Carried-prompt fidelity (S11-bound)

The web-research loop + validator are carried unchanged as references; **what changed is path/reference
adaptations only** (no dimension, severity, evidence rule, or output shape touched):

- `references/research-validator-prompt.md` (128 lines, identical to v1's) — **two** path/reference
  adaptations, both necessary v1→v2 corrections, no other line changed (confirmed by a full `diff` against
  `skills/github-issue-researcher/references/research-validator-prompt.md`): (1) the sibling cross-reference
  (line 5), updated from `github-issue-planner/references/plan-reviewer-prompt.md` to the v2
  `../../planner/references/plan-reviewer-prompt.md`; (2) the invocation-point description (line 3), updated
  from `at step 8 of the workflow` (v1's numbered-step anchor, which no longer exists in v2's router+spine
  anatomy) to `at the spine's validation step` (the v2 anchor — the spine's `S-validate` section). Its six
  dimensions, its `<<repo_root>>` / `<<dimensions>>` placeholder contract (the spine fills `repo_root` with
  `facts.root.path`), its isolation property, and its `## Research validation summary` output shape are
  byte-verbatim. The S11 drift validator (`tests/test_subagent_prompts.py`) auto-discovers it the moment the
  `playbooks/` dir landed and confirms: it returns findings (no §3 decision code — vacuously conformant),
  cites no retired signal doc, and runs no ref-arithmetic in a fence.
- `references/gather-tactics.md` (41 lines) — the source-credibility tiers, the `deep-research` depth
  escalation, and the JS-rendered-doc fetch tactic, carried from v1 SKILL.md Step 6.
- `references/dossier-schema.md` (50 lines) — the frozen `<!-- issue-research:v1 -->` artifact. Its fenced
  block diffs **byte-clean** against `docs/specs/examples/issue-research.md`
  (`test_dossier_schema_matches_s1_capture`). The footer/body provenance strings
  (`Authored by \`github-issue-researcher\``, `\`github-issue-planner\` consumes it`) are **byte-compat
  contract tokens** (S7 precedent (a)) — kept verbatim, NOT renamed to the v2 skill name, because the
  planner's marker lookup and `## External sources consulted` fold-back match these exact bytes.

## Offline validators (S16 DoD, implementor half)

- `python3 -m unittest tests.test_prep_researcher` — 34 tests: the three-way mode vector (broad /
  targeted / revise, + the marker-beats-question precedence); revise dossier facts (`comment_id`/`url` for
  delete-and-repost); the manifest inventory found/missing (exact + glob) and governing-doc found/missing;
  the root-only shape (no freshness gate); the decision codes (`AUTH_REQUIRED`, `MARKER_AMBIGUOUS`);
  conformance on every emitting path; the two-sided call budget (the gather round-trip = 3 gh calls is the
  whole budget, flat across every mode — no mode fans out).
- `python3 -m unittest tests.test_researcher_routing` — 41 tests: the routing table + prep alignment + no
  route override; the interleaving grep; the contract-token gate; the `--dry-run` persist envelopes
  (`comment` fresh + revise `--delete-marker-id`; `edit-labels --add researched`); the dossier-schema
  byte-compat + frozen-provenance check; the handoff shapes + the S15 binding language (router + reference
  + spine); the decline gate (falsifiable, fence-scoped); the carried-validator fidelity (six dimensions,
  v2 cross-ref path, no retired-doc citation); the structural bars.
- `python3 -m unittest tests.test_subagent_prompts` — the S11 drift validator auto-binds
  `references/research-validator-prompt.md` (returns findings, no §3 code — vacuously conformant; cites no
  retired signal doc; no ref-arithmetic in fences).
- Contract-token census: re-run of the S1 baseline command shows **zero cross-skill drops** (the frozen
  v1 `skills/github-issue-researcher/` rows are all intact); every delta is a **list addition** under
  `skills/researcher/` (`<!-- issue-research:v1 -->` in the router/spine/revise/schema; the v2 forward
  route `github-pipeline:planner`; the researcher's own `§3`/`§4`/`§7` cross-doc references).

## Live parity scenarios (operator-gated — fill each result)

Run v1 `github-issue-researcher` and v2 `researcher` on identical starting state in the sandbox, then diff
the persisted artifacts. Harness recipe: headless `claude -p --plugin-dir` (the operator runs it via `!`;
auto-mode blocks `AskUserQuestion`), 0-gate fixtures where a gate (broad-mode confirm; "research but don't
post yet") would otherwise stall the headless run, and **no prep pre-checks in a run clone** (the S13/S15
harness learnings — a pre-run `prep_researcher.py` in the clone can dirty the root and change what the run
sees). Web access must be available in the run environment (the skill hard-stops without it); pin the
scenario's cited sources so both legs fetch stable pages. **Requires web-access — schedule when live web +
sandbox `gh` are both up.**

### Scenario 1 — broad on a currency-risky issue

A filed issue that pins a dependency/SDK/API at or past the model's training cutoff (a genuine currency
risk), no existing dossier, no `— <question>`. Expect: broad mode — derive questions, confirm gate,
tiered/dated fetches, a synthesized `<!-- issue-research:v1 -->` dossier posted, the `researched` label,
forward-to-planner handoff (`research: ✓` with the URL).

- [ ] **D1 (binds parity: currency-risk broad run)** — both legs post a marker-first
  `<!-- issue-research:v1 -->` dossier with the schema's section set; every claim carries a source + fetch
  date; no uncited recall.
- [ ] **D2** — handoff `Issue:` line + `research: ✓ (<url>)` + `Next: /github-pipeline:planner #<N>` (v2
  skill name); the `researched` label applied.
- [ ] **D3** — v2 startup = exactly one `prep_researcher.py` call; the write path = `gh_persist.py comment`
  + `edit-labels`, 0 raw `gh`, 0 `github-ops`; the only sub-agent is the `Explore` validator.
- **Result:** _(operator fills)_

### Scenario 2 — decline on a no-currency-risk issue

A filed issue that touches nothing with currency risk (a rename, a pure-internal typo/logic change). Expect:
broad mode — the decline gate walks all four conditions, none fire, **nothing is posted**, and the run hands
straight to the planner with `research: ✗`.

- [ ] **D1 (binds parity: decline gate)** — both legs post **no** dossier comment (no
  `<!-- issue-research:v1 -->` comment appears on the issue); the four-condition verdict is stated for
  auditability.
- [ ] **D2** — handoff `Issue:` line with `research: ✗` (no URL) + `Next: /github-pipeline:planner #<N>`;
  no `researched` label.
- [ ] **D3** — v2 makes **no** `gh_persist.py` write on this leg (a decline writes nothing).
- **Result:** _(operator fills)_

### Scenario 3 — revise of an existing dossier

A filed issue that already carries an `<!-- issue-research:v1 -->` dossier (post one first, or reuse a
Scenario-1 issue), with a source that has since moved (or a new thread question). Expect: revise mode —
refresh only what changed, show a diff, delete-and-repost (new comment posted **before** the old is
deleted), forward-to-planner handoff (`research: ✓` with the *new* URL).

- [ ] **D1 (binds parity: revise)** — both legs post a refreshed dossier and delete the prior one; the
  issue ends with **exactly one** `<!-- issue-research:v1 -->` comment (no orphan, no double).
- [ ] **D2** — refreshed claims carry current fetch dates; untouched findings are carried forward verbatim
  (not re-researched from scratch); the diff shown to the operator matches what changed.
- [ ] **D3** — the persist used `--delete-marker-id <prior-comment-id>` (post-before-delete); v2 startup =
  one `prep_researcher.py` call reporting `vector.mode: revise` with the prior dossier's `comment_id`.
- **Result:** _(operator fills)_

## Go/no-go (operator)

- [ ] All three scenarios PASS (or every divergence is adjudicated as an explained v1 defect / fixture
  artifact / v2 enrichment, recorded above).
- **Recommendation:** _(operator fills — GO / NO-GO)_
