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
- **Result:** **PASS on the machine-relevant broad/currency-risk parity; three explained divergences (boxes
  left unticked — operator owns the tick + go/no-go).** Run 2026-07-18, branch `rewrite/v2-implementation`
  (headless `claude -p --plugin-dir … --model opus --permission-mode bypassPermissions --output-format
  stream-json --verbose`, fresh sandbox clone per leg, operator-launched via `!`; live web + sandbox `gh`
  both up). **Fixture (identical both twins):** an *"Adopt Pydantic v2 for the report data models
  (`src/formatter_a.py`)"* build issue — a genuine currency risk (the exact v2 field/model-validator
  decorator API, the v1→v2 breaking changes, and the `.dict()`/`.json()`→`model_dump()` serialization API
  are precisely what a model would misremember; the DoD explicitly demands official-doc confirmation with
  fetch dates), no dossier, no `— <question>` → **broad** (prep confirmed `vector.mode: broad`,
  `suggested_playbook: broad.md`). The sandbox carries **no dependency manifest** (pure-Python
  `src/`), so the currency risk lives in the issue text, not a pin — both legs discovered "no Pydantic pin
  today" as the stack context. **Hands-free confirm-gate technique:** the invocation pre-authorized
  "Proceed" (identical text on both legs, so any authoring effect is symmetric) so broad's `AskUserQuestion`
  "Questions" gate never stalled the headless run. Twin A (#87) → v1
  `/github-pipeline:github-issue-researcher`; Twin B (#88) → v2 `/github-pipeline:researcher`. **Dossiers
  left in place** (Scenario 3 revises them). Logs: `scratchpad/s16-scen1/{v1,v2}.jsonl`; captured dossiers:
  `scratchpad/s16-scen1/{v1,v2}-dossier.md` + `{v1,v2}-comments.json`.
  - **Clean (machine-relevant, both legs):** **D1** — both posted a **marker-first** `<!-- issue-research:v1 -->`
    dossier (`#87` comment `5010186027`, `#88` comment `5010200097`) with the **identical section set in the
    identical order**: `## Questions researched` → `## Consensus across sources` → `## Findings by source`
    (4 `### <source>` **primary/official** subsections each) → `## Implications mapped to the issue's Definition
    of Done` → `## Tensions for the planner to resolve` → `## Sources` (both omit the optional `## Strawman
    draft` — no synthetic call to make). **Every source + finding carries fetch date 2026-07-18; no uncited
    recall** (both state verbatim "nothing here is from model memory"). Both **fired the decline gate
    explicitly** (v1 "research clearly fired"; v2 "fired on all four criteria") and derived a **4-question**
    set, and both **independently converged on the same live external truth — Pydantic 2.13.4, released
    2026-05-06** (*past* the Jan-2026 training cutoff, so recall could not have produced it — proof the web
    research genuinely ran on both legs). The **frozen provenance strings are byte-identical** v1↔v2 (the
    footer `_Authored by \`github-issue-researcher\`. Re-run that skill to refresh …_` + the body
    `\`github-issue-planner\` consumes it and owns the design decisions.`), so the dossiers are
    **schema-identical** — a v1 planner reading v2's #88 dossier (and vice versa) parses the same marker,
    section set, and `## External sources consulted` fold-back (parity-protocol §4 cross-consumption holds).
    **D2** — both `## Handoff` blocks are **schema-perfect**: `**Issue:** #N — … · open · enhancement ·
    research: ✓ (<dossier-url>)`, a fenced `**Next:**` planner command, real `**Why:**`; **v2 forwards to the
    v2-renamed `/github-pipeline:planner #88`**, v1 to `/github-pipeline:github-issue-planner #87` — each its
    own generation's planner. The **`researched` label is applied on both** (`[enhancement, researched]`).
    **The S15 handoff-rendering-drift fix holds live here too** — v2 emitted `**Issue:**` (not `**Filed:**`),
    the `· open ·` state segment intact, and a fenced `Next:`; **none** of the four drift forms appeared
    (0/1 on this route). **D3 (v2 process):** startup = **exactly one `prep_researcher.py 88` call**; write
    path = **`gh_persist.py comment` + `gh_persist.py edit-labels`** (0 raw-`gh` *writes*, **0 `github-ops`**);
    sub-agents = **exactly one `Explore` validator** (returned 0 blockers, 1 suggestion + 1 nit, both applied
    via 2 `Edit`s to the staged `research.md`). v1's contrasting profile is the expected v1 executor-delegation
    shape: **2× `github-ops`** (GATHER + POST) **+ 1× `Explore`** validator, plus `gh-gather.sh`/`gh-persist.sh`
    and raw `gh issue view`/`gh issue edit --add-label` in the main loop. v2 ran leaner overall (7 Bash vs 10;
    1 sub-agent vs 3).
  - **Div-1 (D3 — v2 made one redundant raw `gh issue view` READ; not v2-specific).** After the validator
    returned, v2 ran a single `gh issue view 88 --comments --json …` (transcript step 11) to firm up the
    "Implications mapped to DoD" section, instead of re-reading prep's already-staged `facts.sections`
    (`issue_body*`/`thread*`). It is **read-only** — not a write, not an executor bypass; **the write path and
    sub-agent profile are exactly as D3 specifies** (all writes went through `gh_persist.py`, no `github-ops`).
    v1 *also* made a raw `gh issue view` read (plus more), so this is not a v2 regression — a minor process
    redundancy against what prep had already gathered, visible to no downstream consumer. Operator owns whether
    D3's literal "0 raw `gh`" is read as "0 raw-`gh` *writes*" (met) or "0 raw `gh` anywhere" (one read on each
    leg).
  - **Div-2 (findings-prose / source-count / tension-count authoring latitude; both legs valid).** The
    **section set + order are identical**; only prose and subsection cardinality differ. v1 cited **4** sources
    and surfaced **1** tension (the `architecture.md` §3 "no classes, no framework" rule vs Pydantic
    `BaseModel` classes); v2 cited **5** (it additionally cited the **GitHub releases** page to date the
    2.13.4 release) and surfaced **3** tensions (the §3 rule + first-dependency/manifest choice + the
    validate-vs-format boundary). Both cite the **same core official sources** (PyPI + the Pydantic migration /
    validators / serialization concept docs) and converged on the same version. Same class as the S10/S15
    "v1/v2 opus authoring latitude" precedent — neither a schema regression nor a fabrication.
  - **Div-3 (D1 — one-character frozen-template nit, v1-side; v2 byte-faithful).** In the fixed "What this is:"
    block, v1 rendered "fetched on the **date** shown" (singular) where the schema's frozen text (and v2) reads
    "fetched on the **dates** shown". All sources were fetched on the single date 2026-07-18, so v1's singular
    is arguably more accurate — but it is a one-word drift from the template. It is **not a contract-token
    break**: the *named* byte-compat tokens (the marker, the footer, and the `\`github-issue-planner\` consumes
    it` phrase the planner's lookup/fold-back key on) are byte-identical on both legs. Non-contract prose
    latitude, v1-side.

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
- **Result:** **PASS on the machine-relevant decline-gate parity; one explained divergence (boxes left
  unticked — operator owns the tick + go/no-go).** Run 2026-07-18, branch `rewrite/v2-implementation`
  (headless `claude -p --plugin-dir … --model opus --permission-mode bypassPermissions --output-format
  stream-json --verbose`, fresh sandbox clone per leg, operator-launched via `!`; live web + sandbox `gh`
  both up). **Fixture (identical both twins):** a *"Refactor `src/formatter_a.py`: extract a shared
  input-normalization helper"* build issue — a **pure internal, behaviour-preserving refactor** (extract a
  private `_coerce(...)` over the three formatter stubs, stdlib-only, no new dependency), deliberately
  engineered so **none of the four currency-risk conditions fire**: no manifest/pin (stdlib-only, DoD
  forbids a new dep), not a fast-moving area (decades-stable stdlib string/number/date formatting), the
  behaviour is fully pinned by in-repo docstring contracts (not model recall), and the DoD explicitly frames
  naming/placement as *"a local judgment, not an external standard"* (a textbook **design-choice trap**, not
  research). No dossier, no `— <question>` → **broad** → **decline**. Twin A (#89) → v1
  `/github-pipeline:github-issue-researcher`; Twin B (#90) → v2 `/github-pipeline:researcher`. **Neutral
  pre-auth** (identical both legs): authorize headless proceed and make the decline judgment *honestly* —
  "do not manufacture research where there is none, and do not skip the gate" — so neither leg was biased
  toward posting. Logs: `scratchpad/s16-scen2/{v1,v2}.jsonl`; snapshots: `scratchpad/s16-scen2/{v1,v2}-comments.json`.
  - **Clean (machine-relevant, both legs):** **D1** — **both declined and posted NOTHING**: each issue ends
    with **0 comments, 0 `<!-- issue-research:v1 -->` markers**, and **labels == `[enhancement]`** (no
    `researched`) — the decline-gate must-post-nothing bar met on both. Both **stated the four-condition
    verdict for auditability**: v1 as a four-row table, v2 as a numbered one-line-per-condition list; on both
    legs **all four conditions "do not fire"** with the same reasoning (no pin, stdlib-stable, in-repo
    docstring contracts, explicitly-local naming), and both explicitly named the **design-choice trap** (the
    helper-naming call is the planner's from in-repo precedent — `helpers_a.py`, `_`-prefixed privates — not
    external truth). **D2** — both `## Handoff` blocks are schema-perfect for the decline shape: `**Issue:**
    #N — … · open · <type> · research: ✗` (**no URL**, correct for a decline), a `**Next:**` planner command,
    real `**Why:**`; **v2 forwards to the v2-renamed `/github-pipeline:planner #90`**, v1 to
    `/github-pipeline:github-issue-planner #89`. **No `researched` label on either.** **The S15
    handoff-rendering-drift fix holds live here too** — v2 emitted `**Issue:**` (not `**Filed:**`), the
    `· open ·` state segment intact, `research: ✗` (no URL), a code-block `Next:`; **none** of the four drift
    forms appeared (**0/1** on this route). **D3 (v2 process):** startup = **exactly one `prep_researcher.py 90`
    call**; **0 `gh_persist.py` writes** (a decline writes nothing — the must-not-write bar met), **0 raw-`gh`
    writes, 0 `github-ops`, 0 sub-agents** (no `Explore` validator — nothing was synthesized to validate).
    v1's contrasting profile is the expected v1 executor-delegation shape: **1× `github-ops`** (GATHER) via
    `gh-gather.sh`, then declined — also 0 writes, 0 label. v2 read two grounding docs (`architecture.md`/`prd.md`)
    inline to confirm the design-choice-trap read; v1 inspected the tree via a raw `ls`/`cat` Bash step.
  - **Div-1 (D2 — `<type>` segment: v2 mapped `enhancement`→closed-set `feature`; v1 kept the literal label;
    v2 arguably the more schema-faithful).** Both issues carry the GitHub `enhancement` label. v2 rendered the
    `<type>` segment as `· feature ·` — mapping the label onto the **closed-set `<type>` vocabulary**
    (`handoff-format.md`:51 — `bug, feature, incomplete, story, epic, question`; `enhancement` is *not* a
    member), while v1 rendered the raw label `· enhancement ·` (as *both* legs did in Scenario 1). Neither
    affects the decline-gate parity (the load-bearing decline markers are `· open ·` and `research: ✗`, both
    byte-correct on each leg); the `<type>` token is descriptive, and if anything v2's closed-set mapping is
    the stricter reading. Non-load-bearing rendering latitude on a non-currency-risk segment; operator owns
    the tick. (v2 also kept the `[S16 scenario 2 twin-B]` title suffix verbatim in the Issue line where v1
    dropped its `[twin-A]` suffix — title-verbatim vs cleaned, cosmetic.)

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
