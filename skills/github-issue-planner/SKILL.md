---
name: github-issue-planner
description: Plan *how* to build an already-filed GitHub issue (or an entire Epic and its stories) before any code is written, and post a durable, verified implementation plan onto the issue via the `gh` CLI. This is a specialized multi-step workflow that writes to GitHub — not a quick inline answer: it researches the approach, grounds every decision in codebase precedent and the project docs (`docs/prd.md`, `docs/architecture.md`, `docs/architecture-notes.md`, `docs/ui-design.md`, `docs/constitution.md`, `CLAUDE.md`), surfaces any deviation for the user to approve, optionally ingests updated external docs the user supplies, validates the plan with an isolated review sub-agent, then posts it as an `<!-- implementation-plan:v1 -->` comment. It is the dedicated planning step **between** `github-issue-drafter` (files the issue) and `github-issue-resolver` (writes the code). Trigger whenever someone, referencing an issue number, wants the design / approach / architecture / layering / file-level changes / test strategy / sequencing settled and verified up front — e.g. "develop an implementation plan for #N", "research the best approach for #N", "work out the layering and file changes for #N", "how should we implement/build #N — figure out the design first", "before anyone writes code for #N, write the approach up on the issue", "plan this epic and its stories", or revising/refreshing a stale plan ("update the plan on #N", "re-plan #N against the new docs"). Treat phrasing like "implement", "build", or "step-by-step" as planning when the goal is settling strategy ahead of coding, not coding now; trigger even when the user doesn't say the word "plan". Do NOT use for: filing a new issue (that's `github-issue-drafter`), actually writing or fixing the code (that's `github-issue-resolver`), reviewing a diff or PR, choosing a merge strategy (that's `github-pr-evaluator`), or answering a documentation question.
---

# GitHub Issue Planner

Turn a filed GitHub issue into a verified, best-practice **implementation plan** that the resolver can execute and the PR evaluator can verify against. The drafter answers *what* to build; the resolver answers by *building* it; this skill answers *how* it should be built — and captures that answer as a durable, reviewed artifact on the issue so the thinking isn't lost in an ephemeral planning session.

The plan's job is to **lock the decisions** an implementer would otherwise have to re-derive: the architectural approach, layer assignments, file-level changes, data-model/schema impact, the test strategy, and (for multi-part work) sequencing. It deliberately does *not* spell out every line — see "Lock decisions, not lines" below. The resolver treats those locked decisions as binding; if implementation reveals one of them is wrong, the resolver routes back here in revise mode rather than silently working around it. This mirrors the existing drafter↔resolver audit loop: the issue body is the drafter's artifact, the plan is this skill's artifact, and both can be sent back for revision when reality diverges.

### Asking the user a decision

When you need a decision from the user — an approval gate, a choice between named
paths, or a confirmation before a GitHub write — ask it through the `AskUserQuestion`
tool, not as freeform prose. The tool renders the same multiple-choice card every
time, so the user pattern-matches the decision at a glance instead of re-parsing a
differently-worded question on each run.

Shape every ask the same way:
- One decision per question. `header` ≤ 12 chars (e.g. "Post plan", "Merge mode").
  The `question` field carries the full prose you'd otherwise have typed.
- 2–4 options. Each `label` is the action in imperative form ("Post it", "Squash",
  "Approve"); each `description` says what that choice does and its consequence.
- The tool always appends an "Other" free-text choice, so don't pad to four options
  with a catch-all — leave room for the user to type a custom answer.
- `multiSelect: true` only when the choices genuinely combine (rare here).
- Ask once, act on the answer. Don't re-state the same gate in prose afterwards.

When the candidate paths aren't fixed (e.g. "which of these issues did you mean?"),
generate the options dynamically from what you found. When the answer is inherently
open-ended (e.g. "paste any external doc URLs"), a prose ask is still fine — don't
force it into options.

`AskUserQuestion` is not available inside a sub-agent spawned via the `Agent` tool.
Any gate that arises during sub-agent work must be surfaced by the sub-agent
returning a structured "decision needed" signal to this main loop, which asks the
user and re-dispatches with the answer. Never tell a sub-agent to call
`AskUserQuestion` itself.

### Delegating mechanical work to `github-ops`

This skill is meant to run on a high-effort model — but only the *planning* is
worth that: classification, grounding, deviation calls, drafting, applying
review findings. The judgment-free I/O (fetching the issue + thread, looking up
the plan comment, checking open PRs, reconciling the epic + its branch, locating
precedent in the codebase, and posting/editing on GitHub) does not need it, and
running it on the expensive model is most of what makes this skill feel slow.

Delegate that I/O to the **`github-ops`** sub-agent (`subagent_type: "github-ops"`,
pinned to Sonnet + medium effort — spawn it with **no `model` override** so the
pinned tier applies). It runs the named operation and returns faithful structured
results: `GATHER_ISSUE`, `GATHER_EPIC`, `LOCATE`, `PERSIST_COMMENT`,
`PERSIST_BODY` (see `.claude/agents/github-ops.md` for the contract). It returns
issue bodies and threads **verbatim** — never summarized — so every judgment
below stays yours; `LOCATE` returns only `path:line` pointers, and you still
`Read` the cited ranges yourself so the plan's citations are grounded in context
you actually read.

Like the reviewer, `github-ops` cannot call `AskUserQuestion`. If it hits an
ambiguity or a write conflict it returns `DECISION_NEEDED: <…>` and performs no
write; surface that to the user here and re-dispatch with the answer. And you
only ever hand it a `PERSIST_*` after the user has cleared the step-9 gate — it
posts the approved body verbatim, it never authors anything.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status` to check). If it isn't, stop and tell the user — don't work around it.
- Working directory is the repo the issue belongs to, OR the user supplied `--repo owner/name` context.
- The issue already exists (this skill plans filed issues; it does not file them). If the user is describing something not yet filed, route them to `github-issue-drafter` first.

## The core loop

1. **Identify** the issue or epic — parse the number/URL.
2. **Fetch** the issue, its full comment thread, and any existing plan comment. The presence of a plan comment switches you to **revise mode**.
3. **Classify** the type (bug / incomplete / feature / epic / story) and **scale to the work** — a trivial fix doesn't need a full plan.
4. **Ingest external sources** the user offers (your training knowledge may be stale).
5. **Research and ground** the approach in codebase precedent and the project docs.
6. **Surface deviations** from the docs and get the user's sign-off *before* finalising.
6.5. **Surface genuine design decisions** the planner can't pin from precedent — get the user's call via the Decision gate, before drafting.
7. **Draft** the plan against the schema below.
7.5. **Pre-flight** — sweep the draft for hedge phrasings and resolve each one before invoking the reviewer.
8. **Verify** the plan with the isolated review sub-agent loop (up to 3 passes).
9. **Show** the plan (diff-style in revise mode); auto-post on a clean verify exit.
10. **Persist** the plan as a marker comment + ensure the issue body's plan pointer.
11. **Epic fan-out** — plan each filed child story and run a sequencing pass.

Never skip step 6 or 6.5 (user-owned calls), step 7.5 (the cheap in-loop self-check that prevents the planner→resolver→planner round-trip), or step 8 (an unverified plan is worse than no plan — it looks authoritative while being wrong).

## Step 1–2: Identify and fetch

Parse the issue number/URL the same way the resolver does. Then fetch everything in one pass before forming any opinion — the original body is often outdated by the time someone asks for a plan. Delegate the fetch to `github-ops`:

> `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- implementation-plan:v1 -->", scratch_dir=/tmp/gh-planner-<N>/)`

The `## RESULT` envelope returns the issue metadata as scalars, the path references `issue_body_path` / `thread_path`, and — when a prior plan exists — `marker_comment_id` / `marker_comment_url` / `marker_comment_path` (`marker_comment_present: false` if not). `Read` the body and the thread from their paths. The marker lookup doubles as the **revise-mode trigger**: if `marker_comment_present` is true, `Read` the existing plan from `marker_comment_path`, then go to **Revise mode** below (its `id` is what step 10 deletes; if `github-ops` reports more than one plan comment via `marker_comment_count > 1`, it returns `DECISION_NEEDED` — disambiguate with the user). If an open PR exists in `open_prs`, surface it before planning — the user may want to wait for it to land, or coordinate the plan with in-flight work. Reuse the same `scratch_dir` for every subsequent `github-ops` dispatch this run.

## Step 3: Classify and scale to the work

Classify the issue the same way the drafter does — bug, incomplete feature, feature, epic, or story (read the `labels` array and the body shape). Then walk the comment thread for the **latest decision direction**: the substantive direction-setting may have happened several comments down, and earlier proposals are superseded once a maintainer or the author agreed to a different approach. Write a one-line state summary the user can correct before you do any research:

> "Body proposes X; @maintainer on 2026-05-10 settled on approach W — I'll plan toward W. Correct?"

**Also classify whether the work is multi-phase.** Beyond the drafter's bug/feature/etc. axis, decide whether the implementation will fan out across **two or more phases that share one issue and one PR**. The canonical case is a measurement spike (substrate → harness → operator measurement → decision write-up), but any feature whose DoD reads as "first land X, then run Y, then post Z, then maybe ship code Q" is multi-phase. The rule of thumb that distinguishes it from an Epic:

- **Multi-phase issue** — one issue, one branch, one accumulating PR; phases live as ticked entries in the PR body's `## Phase tracker`. The plan describes the phases via the `## Phases` section in Step 7's schema. The resolver opens the PR in draft and re-enters once per phase.
- **Epic** — one parent issue, multiple child story issues, a long-lived integration branch, one PR per story. The planner's Step 11 fan-out covers Epics; multi-phase work does **not** fan out into child issues.

When in doubt: if the phases produce distinct trackable user-facing deliverables that a maintainer would want to triage / assign separately, it's an Epic with child stories; if the phases are sequential beats of one indivisible piece of work that all land together, it's multi-phase. Spike-style issues (substrate → measurement → decision) are almost always multi-phase. The classification influences which sections of the plan schema below you fill (`## Phases` for multi-phase, `## Story breakdown` + `## Integration strategy` for epic) and which verify-loop dimensions fire (Dimension 7 below for multi-phase and epic, neither for single-phase).

**Scale to the work.** Planning has a cost, and over-planning a trivial change is its own failure mode. Judge honestly:

- **One-line bug fix / typo / pure doc edit** → no plan needed. Say so and route the user straight to the resolver. Don't manufacture a plan just to have one.
- **Small, well-understood bug** → a short plan (Approach + Changes + Test plan) is enough; skip the sections that would be empty.
- **Feature, incomplete feature, story, epic, multi-phase issue** → the full machinery below. These are where a captured, verified plan earns its keep.

## Step 4: Ingest external documentation sources

Your training knowledge has a cutoff and the project may depend on framework versions or APIs newer than that. Before researching, ask once:

> "Any updated external docs or links I should consult — new framework docs, an API reference, a design spec? Paste URLs or file paths and I'll treat them as authoritative over my own knowledge for the relevant tech."

Pull what they give you (`WebFetch` for URLs, `Read` for files). When a provided source contradicts your prior knowledge about a library or API, **trust the source** — that's why the user gave it to you. Record which source informed which decision in the plan's `## External sources consulted` section so the resolver and evaluator can see the provenance (and re-check it if the source later changes).

## Step 5: Research and ground the approach

Read the project docs that constrain the work — don't plan against memory:

```bash
ls docs/prd.md docs/architecture.md docs/architecture-notes.md docs/ui-design.md docs/constitution.md CLAUDE.md 2>/dev/null
```

Read each that exists; follow `@`-references (`CLAUDE.md` pulls in `docs/constitution.md`). The split matters:

- **`docs/architecture.md`** — *what* the architecture is (prescriptive: layer rules, decisions, APIs). Cite it for the shape of the solution.
- **`docs/architecture-notes.md`** — *why* those decisions were made (Q&A rationale). Read this when you're tempted to deviate; the rationale often already addresses your case, and citing it keeps the plan aligned with intent rather than just letter.
- **`docs/ui-design.md`** — the authority for any UI surface. Ground UI decisions in named components, sizes, and patterns it defines (e.g. `SectionCard`, the chat-size model) rather than inventing new ones.
- **`docs/constitution.md`** — non-negotiable rules. A plan that proposes a constitution violation is a blocker, not a deviation to negotiate.

Then **find the codebase precedent.** The strongest plans extend patterns that already exist. Delegate the *locating* to `github-ops` — it greps fast and cheap and hands back pointers, not conclusions:

> `LOCATE(terms=<symbols/patterns/doc sections>, roots=<dirs>, ref=<epic branch if the working tree isn't on it>, scratch_dir=/tmp/gh-planner-<N>/)`

The `## RESULT` envelope returns `manifest_path` + `hit_count` + the terms. `Read` the manifest file to walk the hits — for each entry, `path:line-start–line-end` plus a short excerpt. **You then `Read` the cited source ranges yourself** — the interpretation, the layer call, and every `[precedent: …]` citation are yours, grounded in source you actually read (not in the excerpt). With the candidate sites in hand:
- Find the types, stores, services, and views the change touches; confirm the layer each belongs to (constitution §2).
- Find a sibling feature that solved an analogous problem and mirror its structure.
- Identify the concrete symbols, file paths, and signatures the implementation will add or modify — these become the `## Changes` section.

**Every architectural decision in the plan must cite codebase precedent or an `architecture.md` / `architecture-notes.md` section. Every UI decision must cite `ui-design.md` precedent.** A decision with no cited grounding is either a deviation (surface it — step 6) or under-researched (keep digging).

## Step 6: Surface deviations before finalising (interactive gate)

If the best approach genuinely departs from the documented architecture, architecture-notes, ui-design, or established codebase precedent, **stop and raise it with the user before writing the plan**. Don't silently deviate, and don't bury the deviation in the plan hoping it slides through review.

Present it plainly: what the docs/precedent say, what you propose instead, and why the deviation is worth it. Then ask the decision through `AskUserQuestion` (header `"Deviation"`), with the prose framing in the `question` field and these three options:
- **Approve** — accept the deviation; record it in `## Deviations from project docs` with the agreement date, and consider whether the doc itself should be updated (mention it; the user may want a follow-up).
- **Reject — re-plan** — drop the deviation and re-plan within the documented approach.
- **Update doc first** — the deviation becomes the new norm; the doc edit becomes a prerequisite, noted in the plan.

A constitution violation is **not** a deviation to negotiate here — reshape the plan so it complies, or surface that the issue itself can't be built as specified (which may route back to the drafter in revise mode).

## Step 6.5: Surface genuine design decisions (interactive gate)

Step 6 handles *deviations from the docs* — binary, about compliance ("docs say X, plan wants Y, approve?"). Step 6.5 handles *genuine design decisions* — open-ended, about tradeoff resolution between two approaches that both comply ("approaches X and Y both work; pick one").

The default at this skill is that the planner resolves design questions **autonomously from precedent**: re-read the relevant code with `git show <plan_ref>:<path>`, find how a sibling feature settled the same shape, pin the choice with a `[precedent: …]` citation. Most "open" questions evaporate once you actually read the call site. Exhaust that path first — the round-trip cost of a user gate is real, and a precedent-grounded decision is more durable than a user picked one.

Surface to the user **only** when:

- Two approaches are equally grounded in precedent (no sibling pattern picks between them), AND
- The choice has a user-visible consequence — UX, performance, future optionality, or a layer assignment that pulls one direction or the other.

When both conditions hold, present the question through `AskUserQuestion` with `header: "Decision"`, the prose framing (issue context, candidate approaches, planner's recommendation as option 1) in `question`, and 2–4 concrete options as named approaches. Each option's `label` is the imperative ("Use trigger discriminator", "Add sibling method"); the `description` is one line on what that choice does and its consequence.

The user's answer becomes a **locked decision** recorded in `## Architecture decisions` with `[user decision <date>]` as its citation source — that line carries the same binding weight as a `[precedent: …]` citation. The planner does not revisit it without a step-9 revise.

If the planner is tempted to surface a design question that fails *either* gate above (precedent could decide it, or the consequence is invisible to the user), the question goes in `## Architecture decisions` with a precedent citation. Not in `## Risks & watchpoints`. Not deferred to the resolver.

## Step 7: Draft the plan

Use this schema verbatim — the resolver and pr-evaluator parse these section headings. Omit sections marked optional when they'd be empty; never pad.

**The `<!-- implementation-plan:v1 -->` marker is always the first line of the comment body.** The resolver (step 4.6), the drafter (revise mode), and this skill's own revise-mode lookup all locate the plan by matching that marker with `startswith` — so any character placed before it makes the plan undiscoverable, and a consumer that can't find the plan behaves exactly as if none exists (the resolver stops and asks the user to "run the planner first" even though it already ran). For a story under an epic the `**Epic:**` backlink goes on the line *immediately after* the marker, never above it — see the epic/story note below the schema.

`<plan-ref>@<short-sha>` records the integration target the plan was built against, giving the resolver's step-4.6 currency check both the branch and the commit: `origin/main` for a regular issue, or the **full, un-truncated** `epic/<N>-<slug>` branch for an epic or a story under an epic. Don't elide the branch to `epic/<N>-…` — it is also the resolver's PR base.

```
<!-- implementation-plan:v1 -->
**Implementation plan** — #<N> <title> — planned <ISO-8601 UTC> at `<plan-ref>@<short-sha>`

## Approach
<1–3 paragraphs: the strategy and why it's the right shape for this codebase>

## Doc grounding
<the PRD / architecture / architecture-notes / ui-design / constitution sections that
constrain this, with §refs — the citations, not a restatement of the approach>

## Architecture decisions
- <decision> — <rationale> — [precedent: `path/to/File.swift:NN` | architecture.md §X | architecture-notes §Y | user decision <date> | DEVIATION (agreed <date>) → see Deviations]
- ...

## UI decisions                  (omit if no UI surface)
- <decision> — [precedent: ui-design §X | DEVIATION (agreed <date>)]

## Changes (file-level)
- `path/to/File.swift` — <what changes; new/modified types, methods, signatures; layer>
- ...

## Data model / schema impact     (omit if none)
- <new/changed @Model fields, relationships, migration considerations per constitution §8>

## Test plan
- Unit: <suites to add/extend, per constitution §5 coverage targets>
- UI: <XCUITest flows, accessibility identifiers, USE_MOCK_LLM expectations>

## Phases                         (multi-phase issues only — omit for single-phase; epics use the dedicated ## Story breakdown / ## Integration strategy sections)
1. **Phase 1 — <short title>**
   - kind: code-shipping | operator | decision-only
   - ships: PR commits to the issue branch | comment on the issue | external follow-up issue
   - closes-dod: <1-indexed DoD-bullet refs against the issue body — `(none)` when this phase only enables later phases (substrate, harness infrastructure)>
   - deliverable: <one-line concrete artifact this phase produces — quoted verbatim by the resolver's handoff for operator/decision-only phases>
   - depends-on: <earlier phase numbers, or `(none)` for the head phase>
2. **Phase 2 — <short title>**
   - kind: ...
   - ...

## External sources consulted     (omit if none)
- <url or path> — <what decision it informed>

## Deviations from project docs    (omit if none)
- <what deviates> — <why> — agreed with user <date>

## Risks & watchpoints
- <runtime invariant the resolver must preserve while implementing
  (e.g. "keep the trigger gated on the empty-chat invariant so the
  worst case is a single no-op, not a spurious bubble")>
- <false-positive trap from a shim or dual-emit, with the named
  retirement condition: a target that still resolves through a
  temporary shim or dual-emit, so a green run is not proof the change
  is complete — name the shim, the file/line, and the condition that
  retires it (e.g. "`chatSurface.history` still emits via a shim until
  #563; a test using it passes today but the migration is incomplete
  — assert against the new identifier")>
- <edge-case behaviour the plan has *already decided* how to handle,
  surfaced so the resolver doesn't second-guess it (e.g. "cross-day
  completion: no special handling needed because the Finalise button
  isn't surfaced on a past day anyway")>

**This section does not carry open design decisions.** Phrasings that
defer a choice ("Resolver picks", "either approach is acceptable",
"option A or option B", "TBD", "recommend", "could", "might",
"consider", "evaluate during implementation", "implementer decides")
do not belong here. They go in `## Architecture decisions` (pinned
from precedent — see step 7.5) or surface to the user via the
Decision gate at step 6.5 — never here.

_Authored by `github-issue-planner` and verified in <N> review pass(es). The resolver treats
the decisions above as binding; a plan-invalidating discovery routes back here in revise mode.
Re-run this skill to revise — do not hand-edit._
```

For a **multi-phase issue** (Step 3's classification), the `## Phases` section above is **load-bearing for the resolver and the evaluator** — its structured bullets are how both consumers route work without re-parsing prose. Required keys per phase:

- `kind` — closed enum: `code-shipping` | `operator` | `decision-only`. Drives the resolver's §11 outcome rubric. `code-shipping` produces a diff; `operator` produces a comment containing the result of an operator action (e.g. measurement output); `decision-only` produces a comment containing a written decision (e.g. a chosen path with rationale). A phase that produces both code and a comment is `code-shipping` — the code is the load-bearing artifact; the comment is collateral.
- `ships` — what artifact lands at the end of this phase. One of: `PR commits to the issue branch`, `comment on the issue`, `external follow-up issue` (used when the phase explicitly fans out into a new issue — rare; usually reserved for "if Path X ships code, file a separate implementation issue and PR" style decisions).
- `closes-dod` — explicit DoD-bullet references (1-indexed against the issue body's DoD checklist), or `(none)` when the phase only enables later phases (substrate, harness infrastructure). The evaluator uses this to map shipped phases to satisfied DoD bullets on its final acceptance-criteria check. Naming the wrong phase here causes the evaluator to score a DoD bullet as satisfied before the deliverable that actually satisfies it has shipped — see the "wrong-phase `closes-dod`" pitfall below.
- `deliverable` — one-line concrete artifact. For `operator` and `decision-only` phases the resolver quotes this verbatim in the user-facing handoff (the user runs the operator action or writes the decision based on this line), so write it as actionable prose: *"run `./scripts/spike-640.sh`, post the per-cell table from `build/spike-640-*.log` to #640"* rather than *"the measurement run"*.
- `depends-on` — phase numbers, or `(none)` for the head phase. Drives the resolver's "can this phase start now?" gate when it re-enters mid-multi-phase. No forward references, no cycles — both are dimension-7 BLOCKERs (see Step 8).

The keys carry weight in two different places. The **resolver** reads `kind`, `deliverable`, and `depends-on` for routing. The **evaluator** reads `closes-dod` for its DoD mapping. Missing keys are a dimension-7 BLOCKER regardless of which consumer notices first.

For an **epic**, add two sections after `## Approach`: `## Story breakdown` (an ordered list of `- <story title> — <one-line scope>` entries reconciled against the epic body's `## Stories` list) and `## Integration strategy` (how the stories converge on the `epic/<N>-<slug>` branch and reach `main`). Epics use `## Story breakdown` rather than `## Phases` because each child story is independently filed, planned, and shipped through its own PR — the `## Phases` shape is for **single-issue, single-PR** work where the phases share one branch.

Per-story plans use the same schema on the story issue, with the `**Epic:** #<epic-#> — <epic title>` backlink as the **first line after** the `<!-- implementation-plan:v1 -->` marker — never above it, so the marker stays at the start of the comment body and every consumer's `startswith` lookup resolves it (see the marker-first invariant in Step 7). A story plan therefore opens:

```
<!-- implementation-plan:v1 -->
**Epic:** #<epic-#> — <epic title>
**Implementation plan** — #<N> <title> — planned <ISO-8601 UTC> at `epic/<epic-#>-<slug>@<short-sha>`
```

### Lock decisions, not lines

The plan binds *decisions*. Under-specification is the dominant failure mode at the planner→resolver seam — when the plan leaves a choice open, the resolver's audit catches it as a dimension-4 BLOCKER, the user routes back here in revise mode, and the planner ends up resolving the decision anyway by reading the same code it could have read on the first pass. Over-specification is real but secondary: a plan that transcribes the diff is brittle, but a plan that hedges on the diff *shape* is broken.

What the resolver may decide on its own is narrow — strictly line-level mechanics with no observable interface:

- local variable naming inside a single method
- code formatting and brace style
- the exact form of a helper that lives inside one function and is not called from elsewhere
- the textual wording of log messages and error strings (subject to the localisation and logging rules in `docs/constitution.md` §6 and §10)

Everything else gets pinned in the plan:

- every new symbol's **type signature** — name, parameter labels, return type, throws/async, generics
- every new enum case's name, raw value, associated payload (or explicit "no payload"), and ordering/priority
- every new field's type, nullability, units, initial value, and `@Relationship` shape (for `@Model` fields)
- the **file path and layer** each new symbol lives in (per constitution §2)
- the **choice between competing implementation patterns** when more than one is plausible — name the rejected alternatives and why, so a future reader doesn't re-open the question
- the file path of every new test file; the suite/`// MARK: -` section for every new test added to an existing file
- the **assertion intent** of each new test (what it asserts, not its exact code)
- control-flow at every non-obvious branch point (e.g. *"on `.sessionCompleteIntent`, the switch arm is `case .sessionCompleteIntent: break`"*) — not the surrounding code, but the decision the branch encodes

The test for whether something belongs in the plan: *would a competent implementer reading the plan cold have to pause and decide?* If yes, the plan decides it first. The earlier *"would re-litigation in review"* bar is too lax — by the time review fires, the round-trip cost is already paid.

## Step 7.5: Pre-flight — resolve every open decision

Before invoking the reviewer, sweep the draft yourself. The reviewer is expensive (a fresh sub-agent re-reading docs and codebase at `<plan_ref>`); catching hedges in-loop costs almost nothing. The reviewer should be the second line of defence, not the first.

**Sweep for hedge phrasings.** Grep the draft for these (case-insensitive, regex-friendly):

```
resolver picks | implementer (picks|decides) | either approach | both are acceptable
option \([ab]\) | option [AB] | TBD | to be decided | we'll figure out
recommend(s|ed)? | could (go|use|be) | might (go|use|be) | consider (using|adding)
evaluate during implementation | leave to (the )?resolver | (depends on|figure out) during
```

For each hit, choose **one** of the following — in this priority order, do not skip ahead:

1. **Resolve from precedent.** Re-read the actual code at `<plan_ref>` with `git show <plan_ref>:<path>` (and `git grep` for the sibling pattern). Pin the decision by rewriting the bullet with a concrete answer and a `[precedent: path/to/File.swift:NN]` citation. Most hedges dissolve here — the planner already knows what to do, it just hasn't committed to it yet.

2. **Surface as a Decision gate (step 6.5).** Used only when step 1 genuinely cannot decide — two approaches are equally grounded and the choice has a user-visible consequence. Loop back to step 6.5, get the user's call, fold the answer into `## Architecture decisions` with `[user decision <date>]`.

3. **Demote to a watchpoint** under `## Risks & watchpoints` — legal **only** when the item is not a design decision. *"Floating-point drift on macro scaling: acceptable per PRD §10.3"* is a watchpoint (an accepted runtime trade-off with named rationale). *"Resolver picks the shape"* is a design decision and cannot be demoted.

**Exit gate.** After the sweep, no hedge phrasing may remain anywhere in the plan body. The phrasings that may legitimately survive are: concrete decisions with precedent citations, deviations recorded in `## Deviations from project docs` with their agreed date, user-locked decisions with `[user decision <date>]`, and watchpoints in `## Risks & watchpoints`. If a hedge slips through, the dimension-4 reviewer will catch it at step 8 — but that's a passive backstop, not a substitute for this sweep.

**Why this step exists.** The dominant failure mode of this skill is letting `Resolver picks the shape; both are acceptable` survive to the posted plan. The resolver's audit (its dimension 4) catches it, the user routes back here in revise mode, and the planner resolves the choice — by reading the same code at the same ref it could have read on the first pass. Step 7.5 closes the gap in-loop. The cost is one focused grep + a few targeted `git show` reads; the saving is a full plan round-trip and a delayed implementation.

## Step 8: Verify the plan (isolated review loop)

Before showing the plan to the user, hand it to an isolated review sub-agent — the same pattern the drafter and resolver use, for the same reason: you drafted the plan holding the conversation, the user's framing, and your research notes, none of which appear in the posted comment. From that vantage you can't tell whether the plan stands on its own. The sub-agent simulates a fresh implementer reading only the plan + the issue + the docs + the codebase. If it can't tell whether the plan is executable from those inputs alone, neither can the resolver.

**Invocation.** Spawn an `Explore` sub-agent with the prompt template at `references/plan-reviewer-prompt.md`, filling the `<<placeholders>>`: the plan body, `mode` (`draft` or `revise <N>`), `issue_number`, `repo_owner`/`repo_name`, `repo_root`, `plan_ref` (the git ref the plan was built against — `origin/main`, or the epic branch for a story under an open epic), `dimensions`, `external_sources`, and `sibling_plans` (for an epic, each sibling story's plan). The sub-agent runs **without** the conversation history — that isolation is what makes the review meaningful.

**Dimensions.** Seven, defined in the prompt. Pass the subset that applies:

| Type | Dimensions passed |
|---|---|
| Bug / feature / incomplete / story (single-phase) | 1, 2, 3, 4, 6 |
| Multi-phase issue (Step 3 classification) | 1, 2, 3, 4, 6, 7 |
| Epic (with sibling story plans) | 1, 2, 3, 4, 5, 6, 7 |

Dimensions: 1 doc/constitution coherence, 2 codebase coherence, 3 goal coherence (the changes + tests actually satisfy the issue's acceptance criteria / DoD), 4 implementation readiness, 5 sequencing across sibling story plans (epic-only — fires only when `<<sibling_plans>>` is non-empty), 6 precedent grounding, 7 **phase coherence** (multi-phase and epic — see below).

**Dimension 7 — phase coherence.** Fires when the plan has a `## Phases` section (multi-phase issues) or the epic-mode equivalent. The reviewer checks:

- Every phase has all required keys (`kind`, `ships`, `closes-dod`, `deliverable`, `depends-on`). A missing key is a BLOCKER — the resolver depends on each key for routing, and an absent key forces the resolver to either hand-wave a default or stop and route back here.
- The union of all phases' `closes-dod` references covers every DoD bullet in the issue body **exactly once** (no gaps, no duplicates). A DoD bullet not closed by any phase is a BLOCKER: the planner would have filed a plan that leaves work unaccounted for, and the evaluator's DoD check on the final PR would surface that gap only after implementation is done. A DoD bullet claimed by two phases is a SUGGESTION (clarify which phase actually delivers it) unless both phases are `code-shipping` and ship overlapping diffs — then it's a BLOCKER.
- Every `depends-on` reference resolves to an earlier-numbered phase (no cycles, no forward references). Cycle and forward-reference are BLOCKERs.
- At least one phase is `kind: code-shipping`. A plan with only `operator` / `decision-only` phases doesn't need this skill — it's a discussion, not an implementation; flag as BLOCKER and route back to the user to reclassify.
- Each `operator` / `decision-only` phase's `deliverable` reads as actionable prose a human can execute without re-deriving context (the resolver quotes it verbatim into the user-facing handoff). A `deliverable: "the measurement run"` is too vague — BLOCKER; `deliverable: "run ./scripts/spike-640.sh, post the per-cell table from build/spike-640-*.log to #640"` is correct.

Pass the dimensions list to the reviewer prompt as the `<<dimensions>>` placeholder. When you add Dimension 7 to the call, also update `references/plan-reviewer-prompt.md` so its `## Dimensions` section defines what 7 checks (the bullets above are the spec) and its `Dimensions to check` line accepts the value — the prompt currently enumerates `{1, 2, 3, 4, 5, 6}` and would treat `7` as out-of-set otherwise.

**Loop control** — same shape as the drafter/resolver loops:

```
prev_findings = []
for pass in 1..3:
  findings = plan_reviewer.run(plan, mode, plan_ref, dimensions, sibling_plans)
  drop_findings_without_evidence(findings)
  if findings is empty:
    exit_clean(); break
  if same_finding_repeated_with_no_progress(findings, prev_findings):
    exit_circular(findings); break
  plan = apply(findings, plan)   # blockers always; suggestions by default; nits silently or skipped
  prev_findings = findings
else:
  exit_cap_reached(findings)
```

Unlike the resolver's audit (which routes issue-body findings to the drafter), the planner **applies findings to its own plan directly** — the plan is this skill's artifact to fix. Blockers must be folded or the deviation surfaced to the user; a blocker that can't be resolved without a decision the user owns gets surfaced at step 9.

**What the user sees at step 9:**
- **Clean exit** → show the plan, optionally noting `(verified in N pass(es))`.
- **Cap / circular exit** → show the plan AND a "Review notes" block listing each unresolved finding (severity, dimension, evidence, recommended remediation). The next move depends on the **dimension** of the unresolved findings:
  - **If any unresolved finding is a dimension-4 (implementation readiness) BLOCKER**, "Post as-is" is **not** an option — a dimension-4 BLOCKER is by definition an open design decision, and posting it would reintroduce the planner→resolver→planner round-trip this skill exists to prevent. Ask the decision through `AskUserQuestion` (header `"Review notes"`) with these options: **Surface as decision gate** (route through step 6.5 to pin the choice with `AskUserQuestion`, fold the answer into `## Architecture decisions`, then re-verify), **Fix manually** (hold off posting while you resolve the findings by hand), **Push back on reviewer** (challenge the findings as wrong — used when the reviewer mis-read a precedent or fabricated a contradiction).
  - **If the unresolved findings are only dimensions 1, 2, 3, 5, or 6** (e.g. a doc gap the user is willing to accept, an under-grounded SUGGESTION the user judges acceptable), ask through `AskUserQuestion` (header `"Review notes"`) with: **Post as-is** (post the plan; non-dimension-4 findings may carry as watchpoints in `## Risks & watchpoints` *only if* they meet that section's "not a design decision" bar — otherwise they go in `## Deviations from project docs` with the user's agreement), **Fix manually**, **Push back on reviewer**.

## Step 9: Show the plan (auto-post on clean exit)

On a **clean verify exit**, show the user the plan and proceed directly to step 10 — no confirmation gate on the common path. The verification loop is the quality gate; layering a confirmation on top is redundant and adds latency. If the posted plan turns out to need changes, the user re-runs this skill in revise mode (cheap — only changed sections refresh).

For a **fresh plan**, show the full plan body inline (title + body), note `(verified in N pass(es))`, and proceed to step 10.

For a **revise**, show a diff-style update — only what changed — so the user doesn't re-read the whole thing, then proceed to step 10:

```
## <section> (changed)
<old> → <new>

## <section> (added / removed)
...
(other sections unchanged)
```

On a **cap / circular exit**, the gate at the end of step 8 already handles the user's decision — **Surface as decision gate**, **Fix manually**, **Push back on reviewer**, or (only when no unresolved finding is a dimension-4 BLOCKER) **Post as-is**. Honour that decision; don't ask again here.

A user who wants to review before posting can say so in the prompt ("draft the plan, but don't post yet"); honour that intent and pause here for confirmation instead of auto-posting.

## Step 10: Persist the plan

Reach this step on a clean verify exit (after step 9's inline show) or after the cap/circular decision at the end of step 8. **Stage the approved plan body to disk before dispatching** — write the full plan (starting with the `<!-- implementation-plan:v1 -->` marker line and ending with whatever your final paragraph is) to `/tmp/gh-planner-<N>/plan.md`, then pass that path. `github-ops` reads the bytes through `gh-persist.sh` and posts them directly; the body never gets re-serialized into the sub-agent prompt, so prompt compaction can't abbreviate it and an in-agent Write/Bash race can't lose it (the same surface that filed empty bodies on the drafter's #626/#627 incident).

> `PERSIST_COMMENT(target=issue, id=<N>, repo=<owner/repo>, body_path=/tmp/gh-planner-<N>/plan.md, delete_marker_id=<OLD_PLAN_COMMENT_ID if revising>)`

In revise mode, pass the stale plan comment's `id` (captured in step 2) as `delete_marker_id` so it's deleted before the repost. `github-ops` returns the new comment **URL** plus `body_bytes` / `body_sha256` for the bytes that posted — capture the URL. If you want a byte-for-byte close, compare `body_sha256` against `shasum -a 256 /tmp/gh-planner-<N>/plan.md`. If the empty-body guard fires (`EMPTY_BODY_FILE: <path>`), the staged file is missing or empty — re-write `plan.md` and re-dispatch the same path.

Then **ensure the issue body carries a plan pointer** so a human (and the drafter's revise mode) can see a plan exists. This pointer line:

```
> 📋 **Implementation plan:** see [the implementation-plan comment](<plan-comment-url>) — authored by `github-issue-planner`; re-run that skill to revise.
```

> `PERSIST_BODY(issue=<N>, repo=<owner/repo>, mode=pointer, pointer_line=<the line above with the captured URL>)`

`mode=pointer` is idempotent: it adds the line only if absent and updates the URL in place if the plan comment was reposted — never a second pointer. If the body looks mid-edit (a drafter revise in flight), `github-ops` returns `DECISION_NEEDED` rather than racing; the pointer is low-stakes, so skip it and tell the user.

Finally, **apply the `planned` label to the issue** so the repo's issue list shows at a glance which issues have a verified, durable plan and are ready for the resolver, versus which are still waiting on planning. After `PERSIST_COMMENT` succeeds, run:

```bash
gh issue edit <N> --repo <owner/repo> --add-label planned
```

This call is idempotent — re-running on an already-labelled issue is a no-op, so it's safe in revise mode and across the epic fan-out (where every story passes back through this step). If the label doesn't yet exist in the repo, the first call fails with `could not add label: 'planned' not found`; create it once with:

```bash
gh label create planned --repo <owner/repo> --color FBCA04 --description "Implementation plan posted by github-issue-planner"
```

then re-run the `gh issue edit` call. The trivial-skip branch at step 3 never reaches step 10, so it correctly never applies the label — the planner deliberately declined to author one, so the issue is not planned. The label is a low-stakes signal: if the call fails (network blip, permissions), log it and move on rather than blocking the handoff. The plan comment is already posted; the label is a convenience for issue-list scanning, not part of the audit trail.

## Step 11: Epic fan-out

When the target is an **epic**:

1. Plan the epic itself first (epic-level `## Approach`, `## Story breakdown`, `## Integration strategy`, `## Definition of done` grounding). Verify it with dimensions 1, 2, 3, 6 (sequencing can't fire yet if stories aren't planned). Post it.
2. **Check whether the child stories are filed as issues.** Get the reconnaissance from `github-ops` rather than running the `gh`/`git` yourself — `GATHER_EPIC(epic=<N>, repo=<owner/repo>, dependency=<commit/file/PR a story depends on, if relevant>, scratch_dir=/tmp/gh-planner-<N>/)` returns `epic_body_path` (write `Read` it from disk — the epic body is the one verbatim payload here), the parsed `## Stories` list (each `{number, title, checked, state}`, or a flag that they're plain bullets with no `#NN`), the resolved `epic/<N>-<slug>` branch (local + remote — this is the `plan_ref` for each story), and whether the named dependency has landed on that branch. Per-story scalars stay inline in `## RESULT`. From that list:
   - **Stories are filed** (`- [ ] #NN — title` lines) → plan each one (story schema with the `**Epic:** #N` backlink), each going through its own verify loop. Auto-post each story on its clean verify exit per step 9; a story whose verify loop ends in cap/circular falls through that path's gate at step 8 — handle that story's decision before moving on. Then run the verify loop's **dimension 5 (sequencing)** across the full set of sibling plans; fold any re-ordering into the epic plan's `## Story breakdown` order (the ordered list is the source of truth for sibling sequencing now that `## Sequencing` is retired in favour of `## Phases` for multi-phase single-issue work) and re-verify in revise mode (auto-posts on clean exit).
   - **Stories are not filed** (plain bullets, no `#NN`) → **stop after the epic-level plan.** Tell the user: "The child stories aren't filed yet. Run `github-issue-drafter` to file them (it owns issue creation), then re-run me on the epic and I'll plan each story and sequence them." Filing issues is the drafter's job, not the planner's — don't create them here.

## Step 12: Handoff

Every clean run ends with a single `## Handoff` block — the schema, omission rules, and state-marker vocabulary live in [`../_shared/handoff-format.md`](../_shared/handoff-format.md). The handoff bridges this session and the next: the user will copy the fenced command into a fresh Claude Code session. Don't skip it on a clean exit; don't add anything after it.

This step fires at the end of every clean exit path: after Step 10 (single-issue plan posted), after Step 11 (Epic fan-out complete), and from the trivial-skip branch at Step 3 where the planner declined to author a plan. Revise mode (below) routes through the same step.

The snapshot lines are mechanical — the issue/Epic number and title are already in hand from Step 2's `GATHER_ISSUE`, the plan-comment URL was captured at Step 10, and child-story state for an Epic is from Step 11's `GATHER_EPIC`. The `Why:` line is judgment — describe what the next session will do.

### Renderings

**Single-issue plan posted.** Forward to the resolver.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓ (https://github.com/owner/repo/issues/142#issuecomment-XXXXX)

**Next:** implement the plan in a fresh session.

    /github-issue-resolver #142

**Why:** the plan locks architecture, file-level changes, layer assignments, and test strategy. The resolver executes against it and opens the PR; if implementation reveals a locked decision is wrong, it will re-route back here in revise mode.
```

**Epic plan + all child story plans posted.** Forward to the resolver on the first story in dependency order. The Epic's `## Story breakdown` section names the order (top-to-bottom); pick the head of it.

```
## Handoff

**Epic:** #150 — Chat & session UX polish · open · epic · plan: ✓
**Stories:** #151 ✓, #152 ✓, #153 ✓, #154 ✓, #155 ✓ (5 plans posted, sequenced)

**Next:** start the first story in dependency order in a fresh session.

    /github-issue-resolver #151

**Why:** stories build on each other in the order planned (#151 → #152 → #153 → #154 → #155). The resolver will open a PR targeting the `epic/150-chat-ux` integration branch.
```

If the Epic ran but the child stories weren't filed yet (Step 11's "stop after the epic-level plan" branch), the next step is the drafter — that's a forward route to file the stories, then the user re-runs the planner on the Epic:

```
## Handoff

**Epic:** #150 — Chat & session UX polish · open · epic · plan: ✓ (https://github.com/owner/repo/issues/150#issuecomment-XXXXX)
**Stories:** plain bullets (not yet filed as issues)

**Next:** file the child stories in a fresh session, then re-run the planner on the Epic.

    /github-issue-drafter

**Why:** the planner doesn't file issues — that's the drafter's job. Once the stories are filed (each with the `**Epic:** #150` backlink), re-run `/github-issue-planner #150` and Step 11 will fan out and plan each story.
```

**Trivial change — planner declined to author a plan.** Forward straight to the resolver.

```
## Handoff

**Issue:** #142 — Fix typo in onboarding copy · open · bug · plan: ✗

**Next:** implement the fix in a fresh session.

    /github-issue-resolver #142

**Why:** this issue is a one-line copy fix — no implementation plan is warranted (the planner's Step 3 scale-to-work judgment). The resolver opens the PR directly.
```

**Revise mode — plan refreshed.** Same forward shape; the plan URL in the `Issue:` line is the *new* comment URL captured at Step 10 (the stale one was deleted via `delete_marker_id`).

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓ (https://github.com/owner/repo/issues/142#issuecomment-YYYYY)

**Next:** resume implementation in a fresh session.

    /github-issue-resolver continue #287

**Why:** the plan was refreshed against today's codebase (the `<X>` symbol the previous plan named was renamed to `<Y>` at `<path:line>`). PR #287 is still open on the same branch; the resolver continues from there with the updated locked decisions.
```

If no PR exists yet (the resolver hasn't started), drop the `continue #287` and use `/github-issue-resolver #142` instead.

## Revise mode

Triggered when a plan comment already exists (step 2) or the user asks to update/refresh a plan. Plans go stale: the codebase moves, the issue body gets revised, external docs change, the comment thread settles on a new direction. This mode refreshes the plan against today's reality.

1. Fetch the existing plan comment (step 2) and the issue + thread. Note the plan's recorded SHA.
2. Identify what changed since the plan was written — re-walk the thread for newer decisions, re-grep the codebase for symbols the plan names that may have drifted, re-read any external sources.
3. Re-run steps 5–8 focused on what changed (don't re-derive untouched sections from scratch).
4. Show a diff-style update (step 9), confirm, then delete-and-repost the comment (step 10) and refresh the body pointer's URL.

**Revising an epic plan** also re-audits child story plans: reconcile the `## Story breakdown` against each story's current state and re-run the sequencing check. Surface re-ordering with evidence; don't silently swap.

## Common pitfalls

- **Don't plan an issue that isn't filed.** This skill plans existing issues. If the work isn't filed yet, route to `github-issue-drafter` first.
- **Don't manufacture a plan for a trivial change.** A one-line fix doesn't need a plan; saying "this is trivial, go straight to the resolver" is the right answer, not a thin plan posted for form's sake.
- **Don't over-specify.** Lock decisions, not lines. A plan that transcribes the diff is brittle and wastes the resolver's judgment. Bind what would send implementation down the wrong path; leave the rest.
- **Don't punt design decisions to the implementer.** Phrasings like "Resolver picks the shape", "either approach is acceptable", "we could go with X or Y", "TBD", "recommend X" leak into the plan when the planner is unsure but doesn't want to dig. The cost is a full plan round-trip: the resolver's audit catches the hedge as a dimension-4 BLOCKER, the user routes back to the planner, and the planner resolves the decision anyway — by reading the same code at the same ref it could have read the first time. Step 7.5's sweep exists to prevent exactly this. Either resolve the decision from precedent (read the file, cite the pattern), or surface it as a Decision gate (step 6.5). Never both leave it open and post.
- **Don't deviate silently.** Any departure from architecture / architecture-notes / ui-design / precedent goes through the step-6 user gate and is recorded in `## Deviations`. A constitution violation isn't a deviation — reshape the plan or surface that the issue can't be built as written.
- **Don't skip the verify loop.** An unverified plan is more dangerous than no plan: it carries the authority of a posted artifact while potentially referencing APIs that don't exist or contradicting the constitution. The isolated reviewer is the cheap guard against that.
- **Don't leak conversation context into the reviewer.** The sub-agent must read only the plan + issue + docs + codebase. Injecting your framing defeats the fresh-reader test.
- **Don't store the plan in the issue body.** The body is the drafter's artifact and gets repainted in its revise mode; a plan there would be clobbered. The marker comment is the durable home; the body only gets a one-line pointer.
- **Don't file child stories from the planner.** When an epic's stories aren't filed, route to the drafter. Creating issues here blurs the boundary and skips the drafter's review loop.
- **Don't fabricate citations or symbols.** Every `[precedent: …]` must point at a real file/section. If you can't cite it, it's a deviation or under-researched — handle it as one, don't invent a reference.
- **Don't re-plan from scratch in revise mode.** Refresh what changed; leave untouched sections alone. Show the user a diff, not a wall.
- **Don't author free-form sequencing for multi-phase work.** Multi-phase issues use the structured `## Phases` section (Step 7's schema) with the fixed `kind` / `ships` / `closes-dod` / `deliverable` / `depends-on` keys per phase. Prose like *"Phase 1 ships X, then Phase 2 measures, then Phase 3 writes up the decision"* reads correctly to a human but the resolver parses `## Phases` deterministically to route each phase — it cannot grep loose prose for a `closes-dod` mapping or a `kind` enum, and silently falls back to hand-waving (which is exactly the regression mode this whole change was made to prevent — #640's Phase 1 PR shipped to `main` partway through the DoD because the prior `## Sequencing` section gave the resolver no way to recognise that more phases were due). If a phase doesn't fit the structured keys, that's a signal the phasing itself is unclear and needs re-thinking — not a signal to relax the format.
- **Don't write a `closes-dod` bullet for the wrong phase.** The evaluator uses `closes-dod` to map shipped phases to satisfied DoD bullets on its final acceptance-criteria check. A substrate phase that claims it closes a measurement DoD bullet (on the grounds that "my code is *needed* for the measurement to run") will cause the evaluator to score the PR as satisfying that bullet before the measurement has actually been performed. `closes-dod` names the phase whose **deliverable satisfies the DoD bullet**, not the phase whose code enables it. Substrate and infrastructure phases that only enable later phases use `closes-dod: (none)`; the bullet they enable is claimed by the phase whose `deliverable` is the actual artifact the DoD asks for.

## When to ask the user

- The repo or issue number is ambiguous.
- The best approach deviates from the docs or precedent (always — step 6).
- The thread shows unresolved disagreement between maintainers about the approach.
- An epic's stories aren't filed yet (stop and route to the drafter).
- An external source the user provided contradicts the project docs (whose intent wins?).
- The verify loop ends in cap/circular with a blocker that needs a human decision.

## Why this matters

Planning is where the expensive mistakes are cheapest to prevent. A wrong architectural decision caught in a plan costs a paragraph to fix; the same decision caught in review costs a re-implementation, and caught at integration costs a re-integration. Capturing the plan as a verified, durable artifact — rather than letting it evaporate in a manual planning session — means the resolver executes a vetted approach, the PR evaluator can check the result against it, and the next person to touch the issue sees *how* it was meant to be built, not just *what*.
