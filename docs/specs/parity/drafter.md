# Parity — drafter (v1 `github-issue-drafter` → v2 `drafter`)

> Records the [implementation.md](../../implementation.md) **S15** parity run per the
> [parity protocol](../../implementation.md) (`## The parity protocol`) and [prd.md §9.5](../../prd.md).
> The offline work (router + four playbooks + spine + references + tests + the `prep_drafter` alignment)
> landed in S15's implementor pass; the **four live scenarios below are operator-gated** — run them on the
> sandbox ([SANDBOX.md](../../../tests/SANDBOX.md)) and fill each result section. A v1 skill directory is
> deleted only after its v2 replacement passes this protocol (S20).

## Line-count metric ([prd.md §10](../../prd.md); S15 DoD box 5)

The success metric: the prompt a session loads (router + the one playbook it executes) is **at most half**
the v1 `SKILL.md` line count. v1 `github-issue-drafter/SKILL.md` = **576 lines**
([baseline.md](../baseline.md) §1) → bar = **288**.

| File | Lines |
|---|---:|
| `skills/drafter/SKILL.md` (router) | 130 |
| `skills/drafter/playbooks/draft-spine.md` (the shared spine — largest playbook) | 147 |
| `skills/drafter/playbooks/epic-split.md` | 84 |
| `skills/drafter/playbooks/revise.md` | 72 |
| `skills/drafter/playbooks/question.md` | 57 |
| `skills/drafter/playbooks/new.md` | 56 |
| **router + largest playbook (the loaded set)** | **277** |

**277 ≤ 288** ✅ (11 lines of margin). Router **130 ≤ 150** ✅ (architecture.md §9 size bar). Router grew
123 → 130 (+7) and each playbook +2 in the post-scenario-2 handoff-binding fix below (the shared spine,
already the largest file, was untouched, so the loaded-set sum grew only by the router's +7). References
are read on demand and are not part of the loaded-prompt metric; recorded for completeness:
`issue-reviewer-prompt.md` 213 (carried adversarial review loop, tool-use rewritten for the drafter's
current-checkout grounding vantage), `issue-templates.md` 143 (carried built-in fallback templates),
`handoff-renderings.md` 123 (drafter handoff shapes, next-commands renamed to the v2 skills, +5 for the
binding-language fix below). Every routed session loads the router (130) + the spine (147) + exactly one
thin routed playbook (56–84); each individual document fits one default `Read`.

## Playbook split (the §5-bar decision the Work records)

architecture.md §5 "parameterize before you playbook": a playbook exists only for flows that differ in
**actions taken**, not values. For the drafter the draft→review→gate→file backbone is identical across
every mode *up to facts* (which template, which reviewer dimensions, single-vs-batch filing); only the
**pre-review reconnaissance, the filing sequence, and the handoff** diverge. The split:

- **`playbooks/draft-spine.md`** — the draft-and-verify-and-file backbone every route runs (gather missing
  context → resolve open questions → draft against the template → adversarial review loop → show + filing
  gate → staged filing through `gh_persist.py`). Type is a fact here, never a branch; it carries the
  falsifiable OQ-absorption rule, the review loop, and the capability-gated `DEPS_UNSUPPORTED` prose
  fallback. All four routes open by reading it.
- **`playbooks/new.md`** — a fresh single build issue: Step-1 classification cues (the one place the mode
  is chosen), the built-in template + title convention, dimensions `1,2,3,6`; the new-mode override
  hand-back to the router. Forward handoff to the planner.
- **`playbooks/revise.md`** — refresh a filed standalone/story issue: latest-direction confirm, dimensions
  `1,2,3,6,+4`, tiered OQ reconciliation, diff-show, `edit-body` + `edit-labels`, plan-pointer
  preservation, story epic-backlink check. Author/refresh/terminal handoff.
- **`playbooks/epic-split.md`** — the Epic shape (fresh batch **and** epic-revise, the one epic playbook):
  the coalescing pass + adversarial split loop (dimensions `5,7`), body review (`1,2,3,6` + re-confirm
  `5,7`), the hands-off E3 batch file (epic → stories → `edit-body` link patch), and the epic-revise
  `## Stories` reconciliation. Epic-batch handoff to the planner.
- **`playbooks/question.md`** — a `question`-type issue (a new-mode override, or a question revise):
  the `_shared/question-issue.md` schema, audience labels, dimensions `1,3,6 (+2 if code cited)`,
  paste-ready snippet, terminal handoff.

Why a spine + four thin variants rather than one self-contained file per route (each restating the whole
review/file backbone) or a single file with `if new … else …` (banned by §5)? The backbone is identical up
to *facts*; only the reconnaissance, the filing sequence, and the handoff diverge. The four variants
contain **zero cross-route conditionals** — the route *is* the branch — verified by
`tests/test_drafter_routing.py::PlaybookInterleavingGrepTests` (patterns broadened to the drafter's route
set per the S10 carried advisory).

## The new-mode classification override rule (as authored)

`prep_drafter.py` cannot read the freeform feedback text, so for **every** new-mode session it proposes
`new.md` (`vector.type` is `null` — architecture.md §5 "prep proposes; the router confirms"). `new.md`'s
Step 1 classifies the feedback (bug / incomplete / new feature / Epic / question). When that classification
is **Epic** or **question**, the router **overrides** `suggested_playbook` and reads `epic-split.md` or
`question.md` instead — evidence the script could not see ahead of the read. The router logs the override
reason. This is the **S13-scenario-3 precedent** (a route the classification, not the label, selects)
applied to the drafter's new-mode entry: prep's `suggested_playbook` is a proposal keyed on mechanically
derivable facts, and the classification is the one judgment that can supersede it. The feature-vs-Epic
`AskUserQuestion` gate (`header: "Issue size"`) runs *before* the override so scope stays the user's call.

The rule is stated in the router (`SKILL.md` §2) and asserted by
`tests/test_drafter_routing.py::RouterRoutingTableTests::test_new_mode_classification_override_rule_is_visible_in_router`.

## The `prep_drafter._suggested_playbook` alignment

S14 shipped `prep_drafter._suggested_playbook(mode, issue_type)` proposing exactly the four S15 playbook
names, keyed on `(mode, issue_type)`:

- `mode: new` → `new.md` (the router may override to `epic-split.md`/`question.md` post-classification).
- `mode: epic-revise` → `epic-split.md` (the one epic playbook, fresh Epic **and** epic-revise).
- `mode: revise`, `type: question` → `question.md`.
- `mode: revise`, any other type → `revise.md`.

The router routing table is byte-consistent with this map (asserted by
`test_table_matches_prep_suggested_playbook`). No script change was needed in S15 — S14's function already
proposed the final four names (`config.oq_markers` is an ambient-detection hint, never a gate; the
epic-revise checkbox/live-state `attention` line is report-only, the router owns the body write).

## Offline validators (S15 DoD, implementor half)

- `python3 -m unittest tests.test_drafter_routing` — 43 tests: routing table + prep alignment + the
  new-mode override rule; the interleaving grep; the contract-token gate; `--dry-run` envelopes for every
  write (create + labels + native deps, the `DEPS_UNSUPPORTED` prose fallback exercised in-process, the
  epic `## Stories` `edit-body` patch, `edit-labels`, the reused-companion cross-link `comment`, the revise
  native-dep `link` removal); rendering byte-compat vs the S1 captures (question-issue schema,
  `open-question-links:v1` section, handoff shapes); the falsifiable OQ-absorption rule (fence-scoped);
  the structural bars.
- `python3 -m unittest tests.test_subagent_prompts` — the S11 drift validator auto-binds
  `references/issue-reviewer-prompt.md` (it returns findings, no §3 decision code — vacuously conformant;
  cites no retired signal doc; no ref-arithmetic in fences).
- Contract-token census: re-run of the S1 baseline command shows **zero cross-skill drops**; every delta
  is a **list addition** under `skills/drafter/`. The authorized `_shared/handoff-format.md` relabel
  (`(drafter only)` → `(drafter and resolver)`) changes prose only — no census token.

## Live parity scenarios (operator-gated — fill each result)

Run v1 `github-issue-drafter` and v2 `drafter` on identical starting state in the sandbox, then diff the
persisted artifacts. Twin the sandbox subtree for the epic-split scenario (it patches the epic body).
Harness recipe: headless `claude -p --plugin-dir` (the operator runs it via `!`; auto-mode blocks
`AskUserQuestion`), 0-gate fixtures where a gate would otherwise stall the headless run, and **no prep
pre-checks in a run clone** (the S13 harness learnings — a pre-run `prep_drafter.py` in the clone can dirty
the root and change what the run sees).

### Scenario 1 — new bug draft

Feedback describing a bug, no repo issue template (built-in fallback path). Expect: one filed `bug` issue,
template-conformant (built-in Bug template: Description / Steps / Expected / Actual / Environment), title
`[Bug] …` (or unprefixed if the sandbox labels type), forward-to-planner handoff (`plan: ✗`).

- [ ] **D1** — v1 and v2 file the same issue type + labels; both bodies template-conformant.
- [ ] **D2** — handoff `Issue:` line + `Next: /github-pipeline:planner #<N>` (v2 skill name).
- [ ] **D3** — no `## Open questions` section (no OQ in the source), no fabricated sections.
- **Result:** **PASS on the machine-relevant parity; two explained authoring divergences (boxes left
  unticked — operator owns the tick + go/no-go).** Run 2026-07-17, branch `rewrite/v2-implementation`
  (headless `claude -p --plugin-dir`, fresh clone per leg, operator-launched via `!`; GitHub was mid
  "Partially Degraded Service" incident but every endpoint the new-mode path uses — `gh label list`,
  `gh issue create/view`, `contents/*` — was live). **Fixture (identical both legs):** informal feedback
  reporting a real defect — the `src/formatter_a.py` helpers (`format_currency`/`format_percent`/
  `format_date`) are stub bodies returning raw input (`src/formatter_a.py:11,16,21`), no repo issue
  template → built-in Bug fallback; the prompt pre-authorized filing so no gate stalls the headless run.
  Twin A → v1 `/github-pipeline:github-issue-drafter` filed **#68**; Twin B → v2 `/github-pipeline:drafter`
  filed **#69**. Logs: `scratchpad/v1.log`, `scratchpad/v2.log`.
  - **Clean (machine-relevant):** same type + single label (`bug`/`bug`) — **D1 first half**. **v2 startup =
    exactly one `prep_drafter.py` call** (the two `--oq-query` hits in the log are quoted skill text, not
    invocations); **gates 0=0** both legs; v2's only sub-agent is the `Explore` reviewer (state-assembly is
    the prep call, not a sub-agent). Forward route `Next: /github-pipeline:planner #69` with the v2 skill
    rename and `plan: ✗` — **D2 substance**. No `## Open questions` section and no `**Open questions:**`
    handoff line on either leg; no fabricated sections; **v2 correctly declined to absorb the register's
    unrelated OQs** (`SBX-OQ-21/22` concern `audit_log.py`, not the formatter) — **D3**.
  - **Div-1 (D1 — v1-side; v2 is the faithful leg).** Bodies are **not** section-set-identical. v2 #69
    conforms to the shared built-in Bug template (`references/issue-templates.md`: Description / Steps /
    Expected / Actual / Additional context; Environment omitted as N/A for a pure logic bug). v1 #68
    embellished beyond it — renamed Description→`## Summary`, reordered, and added `## Root cause` +
    `## Definition of done` (neither a Bug-template section). Both legs cite the same template; the
    divergence is v1 opus authoring latitude, mirroring the S10-scenario-1 D1 "v1 opus diverged from its
    own spec" precedent. Both issues are valid, cold-readable, identical type+label, no fabrication — no v2
    regression.
  - **Div-2 (D2 — v2-side rendering latitude against a correct prompt).** v1's handoff is schema-perfect
    (`**Issue:** #68 — … · open · bug · plan: ✗` + indented fenced next-command). v2's deviates from the
    shared handoff schema (`_shared/handoff-format.md`): heading `**Filed:**` (schema mandates one of
    `Issue:`/`Epic:`/`Story:`), dropped the `open` state marker, added a `**Snapshot:**` block, and inlined
    the `Next:` command instead of the fenced block. The v2 prompt (`references/handoff-renderings.md`)
    prescribes the correct shape, so this is rendering-time non-determinism, not a prompt bug; the routing
    substance (correct v2 skill name, copy-pasteable, `plan: ✗`) is intact. **A cheap v2-only re-run would
    confirm reproducibility vs a systematic regression** before the operator ticks D2.
    **RESOLVED-live-confirmed** (2026-07-18, by Scenario 3) — see "Handoff-rendering drift — diagnosis +
    fix" below. The router/reference binding was tightened after this recurred 2/2 with Scenario-2 Div-4;
    **Scenario 3's v2 leg then emitted the corrected shape live** (schema-perfect `**Issue:**` handoff, no
    drift form present), so this is no longer pending. Operator still owns the D2 tick.

### Scenario 2 — epic split (twins, since it patches the epic)

Feedback describing a multi-capability Epic. Expect: one Epic + child stories filed in one batch (hands-off
on a clean E1+E2), stories in dependency order with `**Epic:**` backlinks, the Epic's `## Stories`
placeholders patched to `- [ ] #NN — <title>` links via `edit-body`, epic-batch handoff.

- [ ] **D1** — v1 and v2 file the same story set (post-coalescing) in the same dependency order.
- [ ] **D2 (binds parity: epic-split link patching)** — both patch the Epic `## Stories` bullets to real
  `#NN` links; the patched epic body diffs clean.
- [ ] **D3** — each Story body carries the `**Epic:** #<epic-#> — <title>` backlink on its first line.
- **Result:** **PASS on the machine-relevant epic-split parity; four explained divergences (boxes left
  unticked — operator owns the tick + go/no-go).** Run 2026-07-17, branch `rewrite/v2-implementation`
  (headless `claude -p --plugin-dir`, fresh clone per leg, operator-launched via `!`). **Fixture
  (identical both legs):** informal feedback that *explicitly asks for an epic with child stories* for a
  report-generation capability (reporting-core → locale/formatting-profile → CSV/JSON export →
  personalized greeting header), grounded on the existing `src/` formatter + greeter helpers. Making the
  Epic scope the user's own stated call is the **0-gate design** — it keeps the `Issue size` gate from
  stalling the headless run while leaving the split / coalescing / ordering judgment to the skill. Twin A
  → v1 `/github-pipeline:github-issue-drafter` filed **Epic #70 + stories #71–#75** (5); Twin B → v2
  `/github-pipeline:drafter` filed **Epic #76 + stories #77–#80** (4). Logs: `scratchpad/v1.log`,
  `scratchpad/v2.log`.
  - **Clean (machine-relevant, holds both legs):** each leg filed **one `epic`-labelled Epic + N
    `story`-labelled child stories in one hands-off batch** (gates **0=0** both legs — the split loop +
    per-story body review stand in for the confirmation, per E3). Both **patched the Epic's `## Stories`
    placeholders to real `- [ ] #NN — <title>` links** (v2 via one `gh_persist.py edit-body`); both
    patched bodies diff **clean** — no placeholder bullet survives on either (**D2**). Every Story carries
    the `**Epic:** #<epic-#> — <Epic title>` backlink on its **first line** (**D3**). **v2 startup =
    exactly one `prep_drafter.py` call** (0 `--oq-query`); v2's write path = **5 `gh_persist.py create` +
    1 `edit-body`, 0 raw `gh`, 0 `link`**; v2's only sub-agents are **2× `Explore`** (the `split`-mode
    reviewer + the body reviewer) — no `github-ops`. The router logged the **new-mode classification
    override** (`suggested_playbook` `new.md` → `epic-split.md`, "No size gate needed: the user has
    already made the Epic call"), i.e. the **epic-split single-playbook routing** (S13-scenario-3
    precedent). No filed body carries an `## Open questions` section and no `**Open questions:**` handoff
    line on either leg — the register's `SBX-OQ-21/22` gate `src/audit_log.py`, not this reporting work,
    so both correctly declined to absorb them; no fabrication.
  - **Div-1 (D1 — split judgment latitude; both legs valid).** The story **sets differ**: v1 = 5, v2 = 4,
    so D1's literal "same story set post-coalescing in same dependency order" does not hold. Two causes,
    both authoring judgment on a correct prompt, neither a schema regression: **(i)** v1 grepped the
    codebase, found `src/formatter_a.py`'s three formatters are stubs returning raw input, and filed a
    separate **prerequisite `#71 "Fix formatter_a stubs"`** foundation story; the feedback never stated
    the formatters were broken, so this is codebase-grounding depth — v2 folded formatter usage into the
    reporting-core (`#77`) without a standalone stub-fix story. **(ii)** Ordering differs: v1 =
    stub-fix → assemble → locale → export → header; v2 = core → locale → header → **export last** (v2's
    `split`-mode reviewer flagged that export-before-header would serialize a header-less structure and
    reordered). Both are dependency-valid foundation-then-fan-out shapes. Same class as Scenario-1 Div-1
    and the S10-scenario-1 "v1 opus diverged from its own spec" precedent — operator owns whether the
    split-cardinality difference is acceptable.
  - **Div-2 (native dependency graph — v2 the richer/correct-er leg).** v2 set the **native `blocked by
    #77`** GitHub dependency on `#78/#79/#80` (`create --blocked-by`, capability-gated; the sandbox
    reports `deps_available: true`, so no `DEPS_UNSUPPORTED` fallback was needed) **and** the prose note in
    the Epic `## Stories`. v1 set **no** native deps — it expressed the same ordering via the `## Stories`
    list order + prose only. This is a v2 enrichment consistent with the drafter's native-deps capability
    (the task's "native deps set where the schema calls for them" is satisfied on the v2 leg), not a
    regression: every downstream reader keying on native `blocked_by` (planner Dimension 10, resolver /
    evaluator hard-gate) gets a real graph from v2.
  - **Div-3 (Epic body section set — authoring latitude).** v1's Epic added a `## PRD impact` note
    (reporting is new territory vs the PRD's audit-trail-only coverage — no contradiction); v2's Epic is
    `## Goal / ## Background / ## Stories / ## Definition of done` with no `## PRD impact`. The spine adds
    `## PRD impact` only on genuine PRD **tension** (contradiction / gap), and *extending* into uncovered
    territory without conflict is a judgment call — v2 declined, v1 added it as informational. Built-in
    Epic template is the floor; same class as Scenario-1 Div-1. No fabrication either way.
  - **Div-4 (D-adjacent — handoff rendering latitude; corroborates Scenario-1 Div-2).** v1's handoff is
    schema-perfect (`**Epic:** #70 — … · open · epic · plan: ✗` + flat `**Stories:** #71, …, #75 (5
    filed, dependency-ordered)` + fenced `/github-pipeline:github-issue-planner #70`). v2's again
    **deviates from the `handoff-renderings.md` Epic-batch shape**: a `**Filed — Epic + 4 stories**`
    header, the `**Epic:**` line **dropped the `open` state marker** (rendered `· label \`epic\`` not
    `· open · epic`), `Stories` rendered as a nested bulleted list rather than the flat `**Stories:**`
    line, and the `Next:` command inlined rather than fenced. The **routing substance is intact** (Epic
    #76, `plan: ✗`, dependency order conveyed, correct v2-renamed `/github-pipeline:planner #76`). This is
    the **same rendering-time latitude against a correct prompt** flagged as Scenario-1 Div-2 — and its
    recurrence here (**dropped `open` marker + restructured block on 2 of 2 scenarios**) is the
    reproducibility data point Scenario-1 called for: it reads as an opus handoff-rendering tendency, not a
    fixture artifact. Operator call whether `references/handoff-renderings.md` needs tightening vs
    accepting it as rendering non-determinism (the substance has never regressed).
    **RESOLVED-live-confirmed** (2026-07-18, by Scenario 3) — the 2/2 recurrence (this + Scenario-1 Div-2)
    was ruled a real v2 authoring-compliance defect and fixed; see "Handoff-rendering drift — diagnosis +
    fix" below. **Scenario 3's v2 leg emitted the corrected Epic-adjacent shape's sibling — a schema-perfect
    single-issue `**Issue:**` handoff with no drift form present**, the live confirmation this box needed.
    Operator still owns the D4 tick.

## Handoff-rendering drift — diagnosis + fix (post-Scenario-2)

Scenario-1 Div-2 and Scenario-2 Div-4 are the **same** live-observed rendering defect, reproduced 2/2:
v2's emitted `## Handoff` renamed `**Issue:**`/`**Epic:**` to `**Filed:**` (or `**Filed — Epic + N
stories**`), dropped the `· <state> ·` segment, added an invented `**Snapshot:**` block or a nested bullet
list where the schema has a flat `**Stories:**` line, and inlined the fenced `Next:` command into prose.
Routing *substance* was intact both times (correct next-skill, correct numbers, `plan: ✗`), but the
*shape* diverged from `references/handoff-renderings.md`, which already prescribed the correct form —
2/2 rules this an authoring-compliance failure at emission time, not fixture noise.

**Diagnosis.** Compared the drafter's handoff-emission binding against the three skills whose parities
show zero such drift across 9+ scenarios (resolver, planner, evaluator):

- **The forced point-of-use `Read`** ("Read `references/handoff-renderings.md` … before composing the
  handoff") is present in the drafter at both the router (`SKILL.md` §4) and every playbook's own
  `## Handoff` section — structurally identical to the other three skills. **Not the delta.**
- **The verb strength differs.** Resolver's and evaluator's playbooks predominantly instruct **"emit the
  matching shape"** (a copy-literally verb), and resolver's reference-file intro is explicit: "Pick the one
  that matches the run's outcome, **copy the shape**, and **substitute** the … placeholders." The drafter's
  playbooks and reference-file intro instead said "**match** the run's outcome to a shape and **fill** the
  snapshot" — a softer framing that reads as "compose something equivalent," not "reproduce this literally."
- **No skill — including the three drift-free ones — names the field names (`**Issue:**`, `**Next:**`,
  `**Why:**`, block structure) as fixed contract text**, distinct from `_shared/handoff-format.md`'s closed
  **value** vocabulary ("Use these exact words. Don't invent synonyms." — a table of marker *values*:
  `open`/`closed`, `✓`/`✗`/`stale`, `APPROVE`/`COMMENT`, never the field *names* or the block *shape*).
  None of the observed drift forms (`**Filed:**`, dropped state, an invented `Snapshot` block, an inlined
  `Next:`) were named anywhere as an explicit prohibition, on any of the four skills. This is a real,
  previously-latent gap the other three skills simply hadn't hit yet — the drafter's 2/2 is the first
  reproduction, and the fix closes the gap everywhere it's applied rather than assuming the others are
  immune by luck alone.

**Fix (mirrors the drift-free skills' phrasing; no new wording invented where theirs already worked).**

1. `skills/drafter/SKILL.md` §4 — replaced "Read that reference before composing the handoff and match the
   run's outcome to a shape" with "Read that reference **immediately before composing the handoff — not
   earlier in the session** — then **emit the matching shape verbatim**," plus a new binding sentence
   naming the field names/block structure/closed-set markers as **contract, not prose to summarize**, and
   naming the four observed drift forms as concrete prohibitions (`**Filed:**` for `**Issue:**`; dropping
   the `· <state> ·` segment; an invented `Snapshot` block; an inlined `Next:` command).
2. `skills/drafter/references/handoff-renderings.md` — the point-of-use file actually read right before
   emission — got the same "copy the shape, substitute the … values" phrasing (mirroring resolver's intro
   verbatim in spirit) plus the same four named prohibitions, so the binding is present at the surface the
   model reads last before rendering.
3. Every playbook's `## Handoff` section (`new.md`, `revise.md`, `epic-split.md`, `question.md`) — the
   "Read X and match the outcome" line became "Read X immediately before composing this and emit the
   matching shape verbatim — copy it, substitute only the data below, never rename a field or restructure
   it," mirroring resolver's/evaluator's "emit the matching shape" playbook phrasing exactly.

**Budget.** Router 123 → 130 (+7, still ≤150). Each playbook +2 lines (the one added instruction line
wraps to two). `handoff-renderings.md` 118 → 123 (+5). The shared spine (`draft-spine.md`, the largest
playbook at 147, untouched) still sets the "largest playbook" term, so **router + largest playbook = 130 +
147 = 277 ≤ 288** (11 lines of margin) — the fix does not threaten the S15 DoD box-5 bar. Full arithmetic
recorded in the "Line-count metric" table above (now current).

**Tests.** `tests/test_drafter_routing.py::HandoffBindingLanguageTests` (new) pins: the forced-read-at-
emission instruction ("immediately before composing"); the verbatim/copy-the-shape binding verb in the
router, the reference intro, and every playbook's `## Handoff` section; the four named prohibitions present
verbatim in both the router and the reference intro; and that the binding text sits outside code fences
(prose, not sample output). `tests/run.py` was **not** re-run in full for this fix — only prose in three
already-tested files changed (no fenced/tested content, no script, no schema); the targeted routing suite
+ the S11 subagent-prompt validator were re-run instead (see Validator output in the report).

**Live confirmation — CONFIRMED by Scenario 3 (2026-07-18).** This fix was offline-verified (the binding
text exists and is pinned by a test); the live proof it needed is now in. **Scenario 3's v2 leg emitted a
schema-perfect `## Handoff`** — `**Issue:** #82 — … · open · bug · plan: stale`, fenced `Next:` on its own
line, real `**Why:**`; **none** of the four drift forms (`**Filed:**`, dropped `· <state> ·`, invented
`Snapshot`, inlined `Next:`) appeared. Pre-fix reproduction was 2/2 (Scenario-1 Div-2 + Scenario-2 Div-4);
post-fix it is **0/1** — the binding tightening holds at emission time on a live headless run, not just in
the pinned test. Scenario-1 D2 / Scenario-2 D4 are therefore **RESOLVED-live-confirmed** (a cheap v2-only
re-run of Scenario 1 is now optional corroboration, no longer required); the operator still owns the D2/D4
ticks on those scenarios' own result sections.

### Scenario 3 — revise

An existing filed issue with a superseding thread comment (and, ideally, a `<!-- implementation-plan:v1 -->`
plan pointer). Expect: latest-direction confirm, diff-show, `edit-body` apply with the plan pointer
preserved verbatim, stale-plan flag when the revise is material, correct author/refresh/terminal handoff.

- [ ] **D1 (binds parity: template-conformance)** — the revised body is template-conformant and preserves
  every untouched section; the `> 📋 **Implementation plan:**` pointer survives byte-for-byte.
- [ ] **D2** — the plan comment itself is never edited or deleted.
- [ ] **D3** — handoff resolves to `plan: stale` (material) / current (cosmetic) matching v1.
- **Result:** **PASS — all three D-checks hold on both legs; the only divergences are prose/DoD-split
  authoring latitude (boxes left unticked — operator owns the tick + go/no-go). This is also the live
  run that confirms the handoff-rendering-drift fix (see below).** Run 2026-07-18, branch
  `rewrite/v2-implementation` (headless `claude -p --plugin-dir`, fresh clone per leg, operator-launched
  via `!`; `--output-format` default, tool-call census recovered from the two session transcripts).
  **Fixture (identical both legs):** a filed standalone `bug` build issue on `src/welcome_a.py`'s
  `welcome()` (built-in Bug template: Description / Steps / Expected / Actual / Additional context /
  Definition of done), carrying the canonical `> 📋 **Implementation plan:**` pointer (planner's exact
  form) linking a `<!-- implementation-plan:v1 -->` plan comment, plus a **superseding thread comment**
  that materially grows scope (empty-name guard → also whitespace-trim + empty-after-trim fallback) and
  the DoD (dedicated per-case unit tests). The comment pre-authorizes the apply (0-gate design — the diff
  gate is a freeform prose confirm, no `AskUserQuestion`, so a pre-authorized headless run proceeds). Twin
  A → v1 `/github-pipeline:github-issue-drafter` revised **#81**; Twin B → v2 `/github-pipeline:drafter`
  revised **#82**. Both twins byte-identical at seed (modulo the per-issue plan-comment URL). Logs:
  `scratchpad/v1.log`, `scratchpad/v2.log`; transcripts: `scratchpad/transcript-{v1,v2}.jsonl`.
  - **Clean (machine-relevant, both legs):** **D1** — both revised bodies stay template-conformant, keep
    the **full Bug section set** (Description / Steps / Expected / Actual / Additional context / Definition
    of done — none dropped, none fabricated), and the section sets are **identical v1↔v2** (`diff` clean);
    the `> 📋 **Implementation plan:**` pointer **survived byte-for-byte** on both (`head -1` pre == post).
    **D2** — the `<!-- implementation-plan:v1 -->` comment is **untouched** on both (comment `id` **and**
    body SHA-256 identical pre/post: `#81` `IC_kwDOTNKca88AAAABKg32YQ`, `#82` `IC_kwDOTNKca88AAAABKg357w`).
    **D3** — both handoffs resolve to **`plan: stale`** (material revise) and forward to the planner in
    revise mode, matching each other. Labels identical both legs (`bug, planned`, unchanged). No
    `## Open questions` section and no `**Open questions:**` handoff line on either leg (the revise opened
    no new OQ). **v2 process profile:** startup = **exactly one `prep_drafter.py … --issue 82` call**
    (`vector.mode: revise`, `type: standard`, `suggested_playbook: revise.md`, `plan.present: true` — the
    "vector.mode=revise from prep"); write path = **1 `gh_persist.py edit-body` (staged
    `/tmp/gh-drafter-82/revised.md`), 0 raw `gh`, 0 `github-ops`**; sub-agents = **1× `Explore`** (the
    `revise <N>` reviewer, dims `1,2,3,6,+4`). v1's profile = `github-ops` GATHER → `Explore` review →
    `github-ops` PERSIST_BODY (+ one raw `gh issue view … | head -1` pointer spot-check) — the expected
    v1 executor-delegation shape.
  - **Live confirmation — handoff-rendering drift did NOT reproduce (the box this run was for).** v2's
    emitted `## Handoff` is **schema-perfect**: `**Issue:** #82 — … · open · bug · plan: stale` (correct
    `**Issue:**` field, `· <state> ·` segment intact — **not** `**Filed:**`, **not** dropped), the
    `Next:` command in its **own indented fenced line** (`/github-pipeline:planner revise #82`, v2 rename),
    and a real `**Why:**`. **None** of the four drift forms flagged at Scenario-1 Div-2 / Scenario-2 Div-4
    (`**Filed:**`; dropped `· <state> ·`; invented `Snapshot` block; inlined `Next:`) is present. v1's
    handoff is likewise schema-perfect (`**Issue:** #81 — … · open · bug · plan: stale`). After 2/2
    reproduction pre-fix, this is **0/1 post-fix** — the `handoff-format.md`/router/reference binding
    tightening (commits `d349622`, `61c8229`) holds live. This is the confirmation Scenario-1 D2 /
    Scenario-2 D4 and the "Handoff-rendering drift" section below were waiting on.
  - **Div-1 (D1 — DoD-split + prose authoring latitude; both legs valid).** The bodies are section-set-
    identical but **not word-for-word**: each leg rewrote every touched section in its own prose (expected
    opus latitude, same class as Scenario-1/2 Div-1), and the **Definition of done split differs** — v1
    grew the DoD to **6** checkboxes, v2 to **5**, but both cover the identical case set (empty / `None` /
    whitespace-only / whitespace-trim / normal-name / dedicated per-case unit tests in
    `tests/test_welcome_a.py`); v1 gave "trim" and "normal name still greeted" their own boxes where v2
    folded them. No case is dropped or fabricated on either leg. Operator owns whether the split-count
    difference matters (it changes no downstream contract — the `## Definition of done` annotation forms
    the resolver/evaluator parse are unaffected by checkbox cardinality).

### Scenario 4 — question (with a seeded source-doc OQ)

Two legs. **(a) Direct question:** "file a question for the architect about X" → a `question`-type issue
(schema per `_shared/question-issue.md`), audience label created + applied, paste-ready snippet, terminal
handoff. **(b) The falsifiable OQ-absorption check (binds parity: seeded-doc-OQ absorption):** draft a
*build* issue from a source carrying a seeded unresolved OQ (the sandbox `drafter-open-question-markers`
register + inline pattern). Expect: the OQ is **never** absorbed silently — it gets a Step-3.5 disposition,
a tracked companion (a matched tracker issue via the de-dup search, or a freshly filed `question`), and an
`## Open questions` (`<!-- open-question-links:v1 -->`) entry; `in-scope (blocked)` also sets the native
`blocked by`; the handoff carries the `**Open questions:**` line.

- [x] **D1** — leg (a): v1 and v2 file the same question schema + audience label; both terminal handoffs
  carry the `**Audience:**` line and `(terminal — no follow-up skill)`.
- [x] **D2 (binds DoD box 3)** — leg (b): neither v1 nor v2 freezes the seeded OQ silently; both record an
  `## Open questions` entry with a tracked companion + a closed-set disposition. A `question: (not filed)`
  appears only when the de-dup search returned no candidate.
- [x] **D3** — leg (b): an `in-scope (blocked)` disposition sets the native `blocked by`; on a
  deps-unsupported sandbox the `DEPS_UNSUPPORTED` prose fallback (`Blocked by #N` / `## Open questions` /
  `Related to #N`) is present.
- **Result:** **PASS — all three D-checks hold on both legs; the falsifiable bug-3 OQ-absorption trap is
  defeated on both legs. The only divergences are prose/section-split authoring latitude, plus one
  *narrower-than-predicted* companion-back-link divergence recorded below (boxes ticked — operator
  authorized the tick + go/no-go in this run).** Run 2026-07-18, branch `rewrite/v2-implementation`
  (headless `claude -p --plugin-dir … --model opus --permission-mode bypassPermissions --output-format
  stream-json --verbose`, fresh clone per leg, operator-launched via `!`). **Seeded fixture (identical both
  legs within each sub-leg, 0-gate / pre-authorized so no `AskUserQuestion` stalls the headless run):**
  the sandbox's existing `docs/open-questions.md` register carries `SBX-OQ-22` (retention cap,
  `audience:architect`) with a **matching open companion question #61**; `docs/prd.md` §2 describes the
  audit trail and names both `SBX-OQ-21`/`SBX-OQ-22` as tracked, so the build issue *extends* the PRD (no
  `## PRD impact` tension). **Leg (a):** a direct architect question about the trail's *structure/ownership*
  (single global trail vs. per-module trails merged on read) — a deliberately **distinct, untracked** topic
  (not the retention or repeat-name OQs). **Leg (b):** a build issue for the *retention cap*, the feedback
  pre-stating **in-scope (blocked)** + **reuse the matching tracked question**. Pre-run baseline: #61 body
  sha `03233c73…`, `## Tracked in` = `` `docs/open-questions.md` → SBX-OQ-22 ``, 0 comments; highest issue
  #82. Twin A → v1 `/github-pipeline:github-issue-drafter`; Twin B → v2 `/github-pipeline:drafter`. Logs +
  transcripts: `scratchpad/s15-scen4/*.jsonl`; captured artifacts: `scratchpad/s15-scen4/{v1,v2}-issue-*.json`.
  - **Leg (a) — D1 (both legs pass; one authoring divergence).** v1 → **#83**, v2 → **#84** — both filed a
    single `question` issue with the **identical label set** (`question` + `audience:architect`; the label
    pre-existed, so **0 label-create** on either), both conform to the `_shared/question-issue.md` schema
    (`## Question` / `## Audience` / `## Context` / `## References` / `## Why this matters`, `## Constraints`
    correctly omitted — an unconstrained structural decision), and **both `## Handoff` blocks are
    schema-perfect terminal-question shape**: `**Issue:** #N — … · open · question`, a `**Audience:**
    architect` line, `**Next:** (terminal — no follow-up skill)`, real `**Why:**` — no drift form, **0
    `AskUserQuestion`** either leg. **v2 process:** exactly **1 `prep_drafter.py` + 1 `gh_persist.py create`,
    0 `github-ops`, 0 sub-agent besides the `Explore` reviewer**; v1's = `github-ops` + raw `gh` (the
    expected v1 executor-delegation shape).
    - **Div-a1 (D1 — tracker-id authoring latitude; both valid).** v2 (#84) **proactively minted a new
      register id `SBX-OQ-23`**, titled the issue `SBX-OQ-23 — …`, and added a `## Tracked in` pointer
      (`SBX-OQ-23`, to be added to the register); v1 (#83) filed the same structure question **bare** — no
      id, no `## Tracked in` — and proposed an *untitled* register block in its paste-ready snippet. Both are
      schema-conformant (`## Tracked in` is schema-optional, present only when a tracker id exists — v2
      created one, v1 declined to). Same class as Scenario-1/2/3 Div-1 opus authoring latitude; no regression
      — both are valid, cold-readable `audience:architect` questions.
  - **Leg (b) — D2 + D3 (both legs pass; bug-3 trap defeated on both).** v2 → **#85**, v1 → **#86**. Because
    both sub-legs file a build issue into the *same* repo and the drafter's de-dup search is `--state all`,
    the two legs **collide** unless isolated — the first harness ran v2 first, so v1 correctly declined to
    file a near-duplicate of v2's #85 (a *correct* drafter guardrail, and its transcript independently
    confirmed #85's `blocked_by #61`). The standard **reset-between-legs** technique was applied: v2's #85 +
    its #61 cross-link comment were captured to disk and deleted, restoring #61 to the pristine `03233c73…`
    baseline, and **b-v1 was re-run in isolation** against that same clean slate. Both legs then:
    - wrote the **`## Open questions` section byte-identically** (`diff` clean v1↔v2):
      `<!-- open-question-links:v1 -->` + `- OQ: \`SBX-OQ-22\` (docs/open-questions.md register) — gates:
      whether the audit trail caps retention and at what N — disposition: in-scope (blocked) — question: #61
      — audience: audience:architect`. The companion is recorded as **`question: #61`, never `(not filed)`**,
      even though the `prep_drafter.py … --oq-query` de-dup search **returned #61 as a live candidate on both
      legs** — i.e. the **bug-(a)/bug-3 falsifiable trap** (a `(not filed)` written against a non-empty
      candidate set) **is defeated on both legs** (**D2**, binds DoD box 3).
    - set the **native `blocked by #61`** dependency (the sandbox reports deps supported — **no
      `DEPS_UNSUPPORTED` fallback needed**), **and** carried the always-present prose fallback in
      `## Related issues` (v2 `Related to #61`, v1 `Blocked by #61`) (**D3**).
    - emitted a **schema-perfect `## Handoff`** carrying the `**Open questions:** #61 (audience:architect) —
      1 blocked-by` line + forward-to-planner (`plan: ✗`); v2's `Next:` is the v2-renamed
      `/github-pipeline:planner #85`, v1's the v1-name `/github-pipeline:github-issue-planner #86` — each
      points at its own generation's planner, no drift form on either.
    **v2 process:** **2 `prep_drafter.py` (startup + the `--oq-query` de-dup, confirming the candidate
    consultation ran) + 3 `gh_persist.py`, 0 `github-ops`, 0 `AskUserQuestion`**, plus the `Explore` review
    pass; v1's = `github-ops` GATHER/de-dup + `gh-persist create` + review — the expected v1 shape.
    - **Div-b1 (D-adjacent — DoD-section-split authoring latitude; both valid).** v1 (#86) placed the
      contingent retention criteria under an explicit `## Definition of done` header (3 checkboxes); v2 (#85)
      folded the same contingent checkboxes into `## Background` and omitted a standalone `## Definition of
      done` header. Both keep the identical criteria set (cap → last-N; oldest-evicted-first; append-order
      preserved; both halves come from #61), both correctly frame every criterion as contingent on #61
      resolving in favor of a cap. Authoring latitude, same class as Scenario-3 Div-1; the downstream
      contract the resolver/evaluator parse is the `## Open questions` / native `blocked_by` (byte-identical
      here), not the checkbox layout.
  - **Expected-divergence axis — companion `## Tracked in` back-linking: predicted v1 body-patch did NOT
    reproduce (recorded honestly; not a v2 defect).** The section below predicted v1 would *body-patch* #61's
    `## Tracked in` (per v1 `SKILL.md:517` step 3) while v2 posts only a cross-link comment. **Observed:**
    **v2 (#85)** posted the `Related to #85` **cross-link comment** on reused #61 (the interim breadcrumb —
    **CONFIRMED present**) and left #61's body **byte-unchanged** (sha `03233c73…` across pre-b / post-b-v2)
    — exactly the `draft-spine.md` Step-3.5 behavior. **v1 (#86)** left #61 **entirely untouched** — **no
    `## Tracked in` patch *and* no comment** (sha `03233c73…` unchanged, 0 comments post-run): the headless
    opus v1 run filed → byte-checked → handed off and **skipped its own §517 companion-patch step**. So the
    anticipated divergence **narrowed**: not "v1 patches, v2 comments" but "**v2 leaves a cross-link comment
    breadcrumb; v1 leaves nothing on the companion.**" This is v1 authoring-latitude non-reproduction (same
    class as Scenario-1 Div-1, "v1 opus diverged from its own spec"), and it means the operator's diff will
    show **no** v1 `## Tracked in` line to mis-read as a defect. **No v2 regression:** every machine consumer
    keys on the **build** issue's native `blocked_by` + its own `## Open questions` (set **identically**
    v1↔v2), never on the companion's `## Tracked in` (`open-question-links.md:32`) — and v2's breadcrumb
    comment, the one thing the task asked to confirm, is present. **Sandbox end-state:** #83/#84 (questions)
    + #86 (v1 build issue, `blocked by #61`) live; #85 (v2 build issue) deleted post-capture (evidence in
    `scratchpad/s15-scen4/v2-issue-85.json` + the captured #61 cross-link comment); #61 body pristine, now
    `blocking #86`.

**Expected divergence — companion `## Tracked in` back-linking (read this before diffing leg (b)).** v1
patches the companion question's `## Tracked in` section with the build issue's `#` at filing time
(`SKILL.md:517`, "Filing a build issue that has open questions" step 3: stage the updated companion body,
`PERSIST_BODY(mode=replace, …)`). v2 does **not** — for either sub-case. A **reused** companion gets only
the non-destructive `Related to #<build>` cross-link `comment` (`draft-spine.md` Step 3.5:
"post a lightweight `comment` on it cross-linking this build issue"); a **newly-filed** companion gets no
back-link write at all in this run. This is a deliberate role-split correction, not an omission: v2 assigns
*all* companion `## Tracked in` back-linking — reused or newly-filed — to the `open-questions` sweep, per
`skills/_shared/open-question-links.md:32` ("Thin writer… links the companion question — reusing an
existing one, or filing when untracked (safety net)… Does **not** own cross-doc detection, registry
reconciliation, or doc back-linking — those are the sweep's"). v1's body-patch of the companion was outside
that role split — the sweep didn't exist as a separate skill in v1's design, so the drafter over-reached
into doc-back-link territory the v2 architecture deliberately moved off it. Every machine reader of the
dependency (the resolver/evaluator's hard-gate, the planner's Dimension 10 read) keys on the **build**
issue's native `blocked_by` + its own `## Open questions` section — both of which v2 sets identically to
v1 — not on the companion's `## Tracked in` line, so no consumer-visible behavior regresses. **When D2/D3
diff leg (b), expect v1's companion body to gain a `## Tracked in #<build>` line that v2's companion body
does not; record this as the expected, explained divergence above — not a defect** — and confirm instead
that v2's `Related to #<build>` comment is present on the companion as the interim breadcrumb until the
sweep runs.

> **Observed at the 2026-07-18 run (see Scenario 4 Result, "Expected-divergence axis"):** the prediction
> **narrowed** — v2 posted the `Related to #<build>` cross-link comment on reused #61 (breadcrumb confirmed)
> and left the companion body byte-unchanged **as expected**, but v1 **did not** body-patch #61's
> `## Tracked in` this run (the headless opus v1 run skipped its own §517 companion-patch step), leaving #61
> entirely untouched. So the actual divergence is "v2 leaves a comment breadcrumb; v1 leaves nothing on the
> companion," not "v1 patches, v2 comments." Still not a v2 defect — no machine consumer keys on the
> companion's `## Tracked in`, and both build issues set the native `blocked_by` + `## Open questions`
> identically.

## Go/no-go (operator)

- [x] All four scenarios PASS (or every divergence is adjudicated as an explained v1 defect / fixture
  artifact, recorded above). Scenario 1 (new bug draft), 2 (epic split), 3 (revise), 4 (question + seeded
  doc-OQ absorption) all PASS on the machine-relevant parity; every divergence is recorded above as v1
  authoring latitude, a v2 enrichment, a harness-ordering artifact (leg-b de-dup collision, resolved by
  reset-between-legs), or a narrowed-and-explained expected divergence — none a v2 regression. The
  handoff-rendering-drift fix is now live-confirmed **0/6 legs** across Scenario 3 (both legs) + Scenario 4
  (all four legs emitted schema-perfect `## Handoff` blocks, no drift form).
- **Recommendation: GO.** v2 `drafter` reproduces v1 `github-issue-drafter`'s machine-relevant behavior
  across all four routes (new / epic-split / revise / question) with a leaner process profile (1 prep +
  direct `gh_persist.py`, no `github-ops`) and a real native-dependency graph. The falsifiable
  OQ-absorption rule (DoD box 3) is defeated live on both legs. Remaining differences are authoring latitude
  or deliberate v2 architecture (companion back-linking deferred to the sweep). Ready for S20 v1 removal.

## Seeding-fix record (S15, sandbox writes authorized)

Two `tests/SANDBOX.md` recipe defects, queued from S13, were fixed and the live sandbox re-seeded:

1. **Unit-target naming path.** Both `issue-resolver-test-target` and `pr-evaluator-test-target` blocks
   described the test/source mapping as `tests/test_<module>.py mirrors scripts/<module>.py`, but the
   sandbox has **no `scripts/` dir** — every module lives in `src/` (verified:
   `gh api repos/danwashusen/gh-pipeline-sandbox/contents/src` lists `salute_*.py`, `helpers_*.py`, …).
   Corrected both occurrences to `src/<module>.py`.
2. **The "duplicated" content.** The same `naming:` line lands at CLAUDE.md **lines 9 and 37** — i.e. the
   (wrong) `scripts/<module>.py` path was duplicated across the two test-target blocks. Fixing both to
   `src/` de-duplicates the stale path. **No whole-block duplication existed** in the live sandbox:
   `config_block.read_block_anywhere` returned exactly **one** block per marker for all 11 markers before
   and after (11 blocks / 22 `<!--` lines, unchanged) — verified with the real parser, not by eye.

**Live re-seed.** The corrected CLAUDE.md was extracted from the fixed recipe's config-block heredoc (no
hand transcription — the S7-era `ae283af` precedent), preserving the sandbox's own title header, and pushed
to `danwashusen/gh-pipeline-sandbox` only (commit `6c5f669`). Post-push verification: each of the 11 markers
returns exactly one block; the two test-target blocks now read `src/<module>.py` at live lines 9 and 37.
