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
| `skills/drafter/SKILL.md` (router) | 123 |
| `skills/drafter/playbooks/draft-spine.md` (the shared spine — largest playbook) | 147 |
| `skills/drafter/playbooks/epic-split.md` | 82 |
| `skills/drafter/playbooks/revise.md` | 70 |
| `skills/drafter/playbooks/question.md` | 55 |
| `skills/drafter/playbooks/new.md` | 54 |
| **router + largest playbook (the loaded set)** | **270** |

**270 ≤ 288** ✅. Router **123 ≤ 150** ✅ (architecture.md §9 size bar). References are read on demand and
are not part of the loaded-prompt metric; recorded for completeness: `issue-reviewer-prompt.md` 213
(carried adversarial review loop, tool-use rewritten for the drafter's current-checkout grounding vantage),
`issue-templates.md` 143 (carried built-in fallback templates), `handoff-renderings.md` 118 (drafter
handoff shapes, next-commands renamed to the v2 skills). Every routed session loads the router (123) + the
spine (147) + exactly one thin routed playbook (54–82); each individual document fits one default `Read`.

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

### Scenario 2 — epic split (twins, since it patches the epic)

Feedback describing a multi-capability Epic. Expect: one Epic + child stories filed in one batch (hands-off
on a clean E1+E2), stories in dependency order with `**Epic:**` backlinks, the Epic's `## Stories`
placeholders patched to `- [ ] #NN — <title>` links via `edit-body`, epic-batch handoff.

- [ ] **D1** — v1 and v2 file the same story set (post-coalescing) in the same dependency order.
- [ ] **D2 (binds parity: epic-split link patching)** — both patch the Epic `## Stories` bullets to real
  `#NN` links; the patched epic body diffs clean.
- [ ] **D3** — each Story body carries the `**Epic:** #<epic-#> — <title>` backlink on its first line.
- **Result:** _TODO (operator)_

### Scenario 3 — revise

An existing filed issue with a superseding thread comment (and, ideally, a `<!-- implementation-plan:v1 -->`
plan pointer). Expect: latest-direction confirm, diff-show, `edit-body` apply with the plan pointer
preserved verbatim, stale-plan flag when the revise is material, correct author/refresh/terminal handoff.

- [ ] **D1 (binds parity: template-conformance)** — the revised body is template-conformant and preserves
  every untouched section; the `> 📋 **Implementation plan:**` pointer survives byte-for-byte.
- [ ] **D2** — the plan comment itself is never edited or deleted.
- [ ] **D3** — handoff resolves to `plan: stale` (material) / current (cosmetic) matching v1.
- **Result:** _TODO (operator)_

### Scenario 4 — question (with a seeded source-doc OQ)

Two legs. **(a) Direct question:** "file a question for the architect about X" → a `question`-type issue
(schema per `_shared/question-issue.md`), audience label created + applied, paste-ready snippet, terminal
handoff. **(b) The falsifiable OQ-absorption check (binds parity: seeded-doc-OQ absorption):** draft a
*build* issue from a source carrying a seeded unresolved OQ (the sandbox `drafter-open-question-markers`
register + inline pattern). Expect: the OQ is **never** absorbed silently — it gets a Step-3.5 disposition,
a tracked companion (a matched tracker issue via the de-dup search, or a freshly filed `question`), and an
`## Open questions` (`<!-- open-question-links:v1 -->`) entry; `in-scope (blocked)` also sets the native
`blocked by`; the handoff carries the `**Open questions:**` line.

- [ ] **D1** — leg (a): v1 and v2 file the same question schema + audience label; both terminal handoffs
  carry the `**Audience:**` line and `(terminal — no follow-up skill)`.
- [ ] **D2 (binds DoD box 3)** — leg (b): neither v1 nor v2 freezes the seeded OQ silently; both record an
  `## Open questions` entry with a tracked companion + a closed-set disposition. A `question: (not filed)`
  appears only when the de-dup search returned no candidate.
- [ ] **D3** — leg (b): an `in-scope (blocked)` disposition sets the native `blocked by`; on a
  deps-unsupported sandbox the `DEPS_UNSUPPORTED` prose fallback (`Blocked by #N` / `## Open questions` /
  `Related to #N`) is present.
- **Result:** _TODO (operator)_

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

## Go/no-go (operator)

- [ ] All four scenarios PASS (or every divergence is adjudicated as an explained v1 defect / fixture
  artifact, recorded above).
- **Recommendation:** _TODO (operator)_

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
