---
name: github-issue-planner
model: opus
effort: xhigh
description: Plan *how* to build an already-filed GitHub issue (or an entire Epic and its stories) before any code is written, and post a durable, verified implementation plan onto the issue via the `gh` CLI. This is a specialized multi-step workflow that writes to GitHub — not a quick inline answer: it researches the approach, grounds every decision in codebase precedent and the project docs (`docs/prd.md`, `docs/architecture.md`, `docs/architecture-notes.md`, `docs/ui-design.md`, `docs/constitution.md`, `CLAUDE.md`), surfaces any deviation for the user to approve, optionally ingests updated external docs the user supplies, validates the plan with an isolated review sub-agent, then posts it as an `<!-- implementation-plan:v1 -->` comment. It is the dedicated planning step **between** `github-issue-drafter` (files the issue) and `github-issue-resolver` (writes the code). Trigger whenever someone, referencing an issue number, wants the design / approach / architecture / layering / file-level changes / test strategy / sequencing settled and verified up front — e.g. "develop an implementation plan for #N", "research the best approach for #N", "work out the layering and file changes for #N", "how should we implement/build #N — figure out the design first", "before anyone writes code for #N, write the approach up on the issue", "plan this epic and its stories", or revising/refreshing a stale plan ("update the plan on #N", "re-plan #N against the new docs"). Treat phrasing like "implement", "build", or "step-by-step" as planning when the goal is settling strategy ahead of coding, not coding now; trigger even when the user doesn't say the word "plan". Do NOT use for: filing a new issue (that's `github-issue-drafter`), actually writing or fixing the code (that's `github-issue-resolver`), reviewing a diff or PR, choosing a merge strategy (that's `github-pr-evaluator`), or answering a documentation question.
---

# GitHub Issue Planner

Turn a filed GitHub issue into a verified, best-practice **implementation plan** that the resolver can execute and the PR evaluator can verify against. The drafter answers *what* to build; the resolver answers by *building* it; this skill answers *how* it should be built — and captures that answer as a durable, reviewed artifact on the issue so the thinking isn't lost in an ephemeral planning session.

The plan's job is to **lock the decisions** an implementer would otherwise have to re-derive: the architectural approach, layer assignments, file-level changes, data-model/schema impact, the test strategy, and (for multi-part work) sequencing. It deliberately does *not* spell out every line — see "Lock decisions, not lines" below. The resolver treats those locked decisions as binding; if implementation reveals one of them is wrong, the resolver routes back here in revise mode rather than silently working around it. This mirrors the existing drafter↔resolver audit loop: the issue body is the drafter's artifact, the plan is this skill's artifact, and both can be sent back for revision when reality diverges.

### Asking the user a decision

When you need a decision from the user — an approval gate, a disambiguation, or a confirmation before a GitHub write — follow the shared contract in [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md): one decision per `AskUserQuestion` card, `header` ≤ 12 chars, imperative `label`s with consequence-bearing `description`s, options generated dynamically when the candidates aren't fixed, and the rule that a sub-agent never calls `AskUserQuestion` itself but surfaces a "decision needed" signal back to this main loop. That file is the single source of truth for every gate in this skill.

### Delegating mechanical work to `github-ops`

This skill is meant to run on a high-effort model — but only the *planning* is
worth that: classification, grounding, deviation calls, drafting, applying
review findings. The judgment-free I/O (fetching the issue + thread, looking up
the plan comment, checking open PRs, reconciling the epic + its branch, locating
precedent in the codebase, and posting/editing on GitHub) does not need it, and
running it on the expensive model is most of what makes this skill feel slow.

Delegate that I/O to the **`github-ops`** sub-agent (`subagent_type: "github-pipeline:github-ops"`,
pinned to Sonnet + medium effort — spawn it with **no `model` override** so the
pinned tier applies). It runs the named operation and returns faithful structured
results: `GATHER_ISSUE`, `GATHER_EPIC`, `PERSIST_COMMENT`, `PERSIST_BODY`
(see `../../agents/github-ops.md` for the contract). It returns issue
bodies and threads **verbatim** — never summarized — so every judgment below
stays yours. Codebase-precedent searches do **not** go through `github-ops`
— it's for GitHub I/O only; see Step 5 for how those are run.

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
11. **Epic plan (then just-in-time stories)** — for an Epic, post the high-level epic plan (cross-story contracts + sequencing); a separate `<!-- epic-delivery-log:v1 -->` comment (evaluator-maintained) tracks deliveries. Each child story is planned just-in-time later, not fanned out.

Never skip step 6 or 6.5 (user-owned calls), step 7.5 (the cheap in-loop self-check that prevents the planner→resolver→planner round-trip), or step 8 (an unverified plan is worse than no plan — it looks authoritative while being wrong).

## Step 1–2: Identify and fetch

Parse the issue number/URL the same way the resolver does. Then fetch everything in one pass before forming any opinion — the original body is often outdated by the time someone asks for a plan. Delegate the fetch to `github-ops`:

> `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- implementation-plan:v1 -->", scratch_dir=/tmp/gh-planner-<N>/)`

The `## RESULT` envelope returns the issue metadata as scalars, the path references `issue_body_path` / `thread_path`, and — when a prior plan exists — `marker_comment_id` / `marker_comment_url` / `marker_comment_path` (`marker_comment_present: false` if not). `Read` the body and the thread from their paths. The marker lookup doubles as the **revise-mode trigger**: if `marker_comment_present` is true, `Read` the existing plan from `marker_comment_path`, then go to **Revise mode** below (its `id` is what step 10 deletes; if `github-ops` reports more than one plan comment via `marker_comment_count > 1`, it returns `DECISION_NEEDED` — disambiguate with the user). **Exception:** if the issue is a story under an open epic, don't branch to Revise mode here — it's handled by **Just-in-time story planning** (Step 3's "Route by shape"), which owns both the fresh and revise paths. If an open PR exists in `open_prs`, surface it before planning — the user may want to wait for it to land, or coordinate the plan with in-flight work. Reuse the same `scratch_dir` for every subsequent `github-ops` dispatch this run.

## Step 3: Classify and scale to the work

Classify the issue the same way the drafter does — bug, incomplete feature, feature, epic, or story (read the `labels` array and the body shape). Then walk the comment thread for the **latest decision direction**: the substantive direction-setting may have happened several comments down, and earlier proposals are superseded once a maintainer or the author agreed to a different approach. Write a one-line state summary the user can correct before you do any research:

> "Body proposes X; @maintainer on 2026-05-10 settled on approach W — I'll plan toward W. Correct?"

**If the issue is a bug, the plan must also close the coverage gap that let it escape.** Beyond fixing the defect, identify which existing test(s) *should* have caught it and why they didn't — the path/state/input the root cause exercises that no current test reaches, established by reading the existing tests at `plan_ref` (Step 5) — and lock a regression test that fails against the pre-fix code. The analysis goes in `## Coverage gap`; the test goes in `## Test plan`. Dimension 9 (Step 8) verifies both. This is what makes the bug *covered going forward*, not merely fixed.

**Also classify whether the work is multi-phase.** Beyond the drafter's bug/feature/etc. axis, decide whether the implementation will fan out across **two or more phases that share one issue and one PR**. The canonical case is a measurement spike (substrate → harness → operator measurement → decision write-up), but any feature whose DoD reads as "first land X, then run Y, then post Z, then maybe ship code Q" is multi-phase. The rule of thumb that distinguishes it from an Epic:

- **Multi-phase issue** — one issue, one branch, one accumulating PR; phases live as ticked entries in the PR body's `## Phase tracker`. The plan describes the phases via the `## Phases` section in Step 7's schema. The resolver opens the PR in draft and re-enters once per phase.
- **Epic** — one parent issue, multiple child story issues, a long-lived integration branch, one PR per story. The planner posts a high-level **epic plan** (cross-story contracts + sequencing) up front — with a separate `<!-- epic-delivery-log:v1 -->` comment tracking deliveries — and plans each child story **just-in-time** as it becomes the next to build (Step 11 + "Just-in-time story planning"); it does **not** fan out every story's full plan in advance. Multi-phase work does **not** fan out into child issues at all.

When in doubt: if the phases produce distinct trackable user-facing deliverables that a maintainer would want to triage / assign separately, it's an Epic with child stories; if the phases are sequential beats of one indivisible piece of work that all land together, it's multi-phase. Spike-style issues (substrate → measurement → decision) are almost always multi-phase. The classification influences which sections of the plan schema below you fill (`## Phases` for multi-phase; `## Story breakdown` + `## Story contracts` + `## Integration strategy` for an epic) and which verify-loop dimensions fire (Dimension 7 for multi-phase; Dimension 5 for the epic-level plan and Dimension 8 for each just-in-time story plan; none of these for single-phase).

**Route by shape.** Before the standard Steps 4–10, branch on the classification — two shapes leave this linear flow:
- **Epic** (epic-as-target) → go to **Step 11** (author the epic plan, then stop; stories are planned just-in-time, not fanned out).
- **Story under an open epic** — detected by a `**Epic:** #<N>` backlink in the body, or a `story` label plus a parent-epic search (`gh issue list --label epic --state all --search "#<N> in:body"`) that finds an **open** epic → go to **Just-in-time story planning**. This is the primary path for a story under an epic, and it owns both the fresh-plan and the revise case (taking precedence over Step 2's generic revise dispatch for these issues).
- **Everything else** (standalone bug / feature / incomplete / a story with no parent epic / multi-phase issue) → continue with Steps 4–10 below.

**Scale to the work.** Planning has a cost, and over-planning a trivial change is its own failure mode. Judge honestly:

- **One-line bug fix / typo / pure doc edit** → no plan needed. Say so and route the user straight to the resolver. Don't manufacture a plan just to have one.
- **Small, well-understood bug** → a short plan (Approach + Changes + Test plan + Coverage gap) is enough; skip the sections that would be empty. The `## Coverage gap` analysis (Dimension 9) is not optional for a bug — even a small fix must say what test gap let it ship.
- **Feature, incomplete feature, standalone story, multi-phase issue** → the full machinery below. (An epic uses Step 11; a story under an open epic uses Just-in-time story planning — see "Route by shape" above.) These are where a captured, verified plan earns its keep.

## Step 4: Ingest research (the dossier) and external sources

Your training knowledge has a cutoff, and the project may depend on framework versions or APIs newer than that. Two things feed this step: a research dossier, if one was posted, and any sources the user hands you directly.

**First, ingest the research dossier if it exists.** `github-issue-researcher` posts a durable, cited `<!-- issue-research:v1 -->` comment of current, *fetched* external truth for exactly this purpose. Look it up and stage it to disk — you already have the thread from Step 2, so this is a targeted single-comment fetch, not a re-gather:

```bash
gh api "repos/<owner/repo>/issues/<N>/comments" \
  --jq 'first(.[] | select(.body | startswith("<!-- issue-research:v1 -->")) | .body) // ""' \
  > /tmp/gh-planner-<N>/research.md
```

If `research.md` is non-empty, `Read` it. It carries current guidance *with provenance* — each claim cites a source and a fetch date — and it is **input, not authority**: it informs your `## Doc grounding` and `## Architecture decisions`, but you own every decision. Treat its `## Tensions for the planner to resolve` as questions to settle (from precedent, the docs, or the step-6.5 gate), never as instructions. Record each source it used in the plan's `## External sources consulted` with its fetch date and tier, so the resolver and evaluator see the provenance and can re-check it if the source moves. A dossier finding that contradicts the project docs is a **deviation** (step 6) or a tension you resolve *toward* the docs — the dossier never overrides `docs/constitution.md`.

**Then ask once for anything the dossier didn't cover:**

> "Any updated external docs or links I should consult beyond the research dossier — a newer API reference, a design spec? Paste URLs or file paths and I'll treat them as authoritative over my own knowledge for the relevant tech."

Pull what they give you (`WebFetch` for URLs, `Read` for files), trust the source over stale recall, and record it in `## External sources consulted` alongside the dossier's entries.

**If no dossier exists and the issue clearly turns on current external truth you can't reliably recall** (a dependency/API/version at or past your training cutoff), don't guess — handle it via the knowledge-gap path in Step 5.

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

Then **find the codebase precedent.** The strongest plans extend patterns that already exist. `github-ops` does **not** do codebase searches — it's the GitHub-I/O executor — so run the search yourself. For broad sweeps that span more than a couple of files or symbols, spawn an `Explore` sub-agent (`subagent_type: "Explore"`) with a focused prompt that names the symbols/patterns/doc sections of interest and asks for `path:line-start–line-end` pointers (plus the git `ref` to search under when the working tree isn't on the right branch — e.g. the epic branch for a story under an open epic, so `git grep <pattern> <ref>` is what reaches it). For narrow single-symbol lookups (one identifier, one obvious file), use `Grep`/`Glob` directly — spinning up `Explore` for a one-shot pattern is wasted overhead.

Whichever route you take, the result is the same shape: a manifest of `path:line-start–line-end` pointers, optionally with short excerpts for orientation. **You then `Read` the cited source ranges yourself** — the interpretation, the layer call, and every `[precedent: …]` citation are yours, grounded in source you actually read (not in the excerpt). With the candidate sites in hand:
- Find the types, stores, services, and views the change touches; confirm the layer each belongs to (constitution §2).
- Find a sibling feature that solved an analogous problem and mirror its structure.
- Identify the concrete symbols, file paths, and signatures the implementation will add or modify — these become the `## Changes` section.

**Every architectural decision in the plan must cite codebase precedent or an `architecture.md` / `architecture-notes.md` section. Every UI decision must cite `ui-design.md` precedent.** A decision with no cited grounding is either a deviation (surface it — step 6) or under-researched (keep digging).

**Knowledge-gap handling (current external truth).** Grounding above is about *internal* precedent — the codebase and docs. When it instead surfaces a gap in *external* truth you can't reliably recall — the current behaviour of a dependency/API at or past your training cutoff, a version-specific default, a deprecation timeline — do not ground the plan on a guess. Match the mechanism to the gap's depth:

- **A single quick fact** → spawn a focused web-research sub-agent inline (`subagent_type: "Explore"` or `"general-purpose"`) with a tight prompt: the exact question, the dependency and its pinned version (from the manifest), and the instruction to answer **only** from a fetched primary source and return the claim with its URL + fetch date — no recall. Fold the verified fact in, cite it in `## External sources consulted`, and continue planning.
- **Anything broad** — several questions, conflicting sources, or a whole surface you're unsure of → stop and route to `github-issue-researcher`, which gathers and verifies it into a durable, ingestible dossier. Emit the planner→researcher re-route handoff (Step 12) naming the specific ungroundable fact; the user runs `/github-pipeline:github-issue-researcher #N — <questions>`, then re-runs you, and Step 4 ingests the refreshed dossier.

This is the same "lock decisions from grounded truth, never a guess" discipline that Step 7.5 enforces for internal decisions, extended to the external facts the plan rests on. A step-7.5 hedge that turns out to be an *external* knowledge gap (not an internal design choice) resolves here — inline fact-check or researcher route — before you consider the Decision gate or a watchpoint.

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

**See [`references/plan-schema.md`](references/plan-schema.md) for the verbatim `<!-- implementation-plan:v1 -->` schema** — the ordered section headings the resolver and pr-evaluator parse (`## Approach`, `## Doc grounding`, `## Architecture decisions`, `## UI decisions`, `## Changes`, `## Data model / schema impact`, `## Test plan`, `## Coverage gap`, `## Phases`, `## External sources consulted`, `## Deviations from project docs`, `## Risks & watchpoints`) and the closing provenance footer. Use it verbatim; omit optional sections when empty, never pad. The `## Phases` per-key semantics (`kind` / `ships` / `closes-dod` / `deliverable` / `depends-on`) are detailed below.

For a **multi-phase issue** (Step 3's classification), the `## Phases` section above is **load-bearing for the resolver and the evaluator** — its structured bullets are how both consumers route work without re-parsing prose. Required keys per phase:

- `kind` — closed enum: `code-shipping` | `operator` | `decision-only`. Drives the resolver's §11 outcome rubric. `code-shipping` produces a diff; `operator` produces a comment containing the result of an operator action (e.g. measurement output); `decision-only` produces a comment containing a written decision (e.g. a chosen path with rationale). A phase that produces both code and a comment is `code-shipping` — the code is the load-bearing artifact; the comment is collateral.
- `ships` — what artifact lands at the end of this phase. One of: `PR commits to the issue branch`, `comment on the issue`, `external follow-up issue` (used when the phase explicitly fans out into a new issue — rare; usually reserved for "if Path X ships code, file a separate implementation issue and PR" style decisions).
- `closes-dod` — explicit DoD-bullet references (1-indexed against the issue body's DoD checklist), or `(none)` when the phase only enables later phases (substrate, harness infrastructure). The resolver projects this mapping onto the issue body's `## Definition of done` at the moment each phase ships (`github-issue-resolver` §9's "DoD projection rule" ticks the named bullets with `(closed by phase <N>, commit <sha>)` attribution), and the evaluator's per-phase DoD verification (`github-pr-evaluator` §6) checks each projected tick against the attributed phase's diff. Naming the wrong phase here causes the issue body to mis-record which phase satisfied which bullet; the evaluator's verification will catch it and un-tick with a sticky-veto annotation, but the audit cost falls on the next PR review — see the "wrong-phase `closes-dod`" pitfall below.
- `deliverable` — one-line concrete artifact. For `operator` and `decision-only` phases the resolver quotes this verbatim in the user-facing handoff (the user runs the operator action or writes the decision based on this line), so write it as actionable prose: *"run `./scripts/spike-640.sh`, post the per-cell table from `build/spike-640-*.log` to #640"* rather than *"the measurement run"*.
- `depends-on` — phase numbers, or `(none)` for the head phase. Drives the resolver's "can this phase start now?" gate when it re-enters mid-multi-phase. No forward references, no cycles — both are dimension-7 BLOCKERs (see Step 8).

The keys carry weight in two different places. The **resolver** reads `kind`, `deliverable`, and `depends-on` for routing. The **evaluator** reads `closes-dod` for its DoD mapping. Missing keys are a dimension-7 BLOCKER regardless of which consumer notices first.

For an **epic**, add these sections after `## Approach` (see `references/plan-schema.md` for the verbatim shapes): `## Story breakdown` (an ordered `- #<story> "<title>" — <one-line scope>` list reconciled against the epic body's `## Stories`; this order is the sibling-sequencing source of truth), `## Story contracts` (the cross-story seams — per story, what it `delivers` vs `consumes`; Dimension 5 reads this, and each just-in-time story plan is checked against it by Dimension 8), and `## Integration strategy` (how the stories converge on `epic/<N>-<slug>` and reach `main`). A separate `<!-- epic-delivery-log:v1 -->` comment — maintained by the evaluator on each story merge, not part of this verified plan — records what each story actually delivered (see "Just-in-time story planning"). Epics use these sections rather than `## Phases` because each child story is independently filed, planned just-in-time, and shipped through its own PR — the `## Phases` shape is for **single-issue, single-PR** work where the phases share one branch.

Per-story plans use the same schema on the story issue, with the `**Epic:** #<epic-#> — <epic title>` backlink as the **first line after** the `<!-- implementation-plan:v1 -->` marker — never above it, so the marker stays at the start of the comment body and every consumer's `startswith` lookup resolves it (see the marker-first invariant in Step 7). A story plan therefore opens:

```
<!-- implementation-plan:v1 -->
**Epic:** #<epic-#> — <epic title>
**Implementation plan** — #<N> <title> — planned <ISO-8601 UTC> at `epic/<epic-#>-<slug>@<short-sha>`
```

A story under an epic also carries a `## Epic contract` section — what it `Delivers` (matching the epic plan's `## Story contracts` entry for it) and what it `Consumes` (each already recorded in the epic's `<!-- epic-delivery-log:v1 -->` comment), every line `[epic-plan: #<N>]`-cited. Dimension 8 checks it against the epic plan. Story plans are authored **just-in-time** against current epic HEAD, not up front — see "Just-in-time story planning".

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
- every new field's type, nullability, units, initial value, and relationship shape (for model/schema fields — e.g. a SwiftData `@Relationship`, a Rails association / foreign key)
- the **file path and layer** each new symbol lives in (per constitution §2)
- the **choice between competing implementation patterns** when more than one is plausible — name the rejected alternatives and why, so a future reader doesn't re-open the question
- the file path of every new test file; the suite/`// MARK: -` section for every new test added to an existing file
- the **assertion intent** of each new test (what it asserts, not its exact code)
- for a **bug fix**, the regression test that closes the coverage gap — its assertion must target the path the root cause exercises (named in `## Coverage gap`) and must be one the pre-fix code fails; a test that only asserts the fixed behavior in isolation is not a regression test
- control-flow at every non-obvious branch point (e.g. *"on `.sessionCompleteIntent`, the switch arm is `case .sessionCompleteIntent: break`"*) — not the surrounding code, but the decision the branch encodes

The test for whether something belongs in the plan: *would a competent implementer reading the plan cold have to pause and decide?* If yes, the plan decides it first. The earlier *"would re-litigation in review"* bar is too lax — by the time review fires, the round-trip cost is already paid.

**When a decision nonetheless slips through unlocked** — Step 7.5's sweep and the reviewer's dimension-4 check exist to stop this, but one occasionally survives — the resolver does *not* get blanket license to improvise. Its contract (`github-issue-resolver` §8 "Stick to the plan") is a mini Step 7.5 at the seam: it settles the gap from precedent when precedent decides it unambiguously — recording the call in the PR body so you see it on the next revise — and otherwise routes back to you in revise mode when the choice carries a user-visible consequence. The resolver fills what you left open, plus the mechanics *entailed* by a locked decision, freely (locked decisions are a floor, not a ceiling — an additive test or an entailed call-site edit is not a deviation); it never silently *reverses* what you locked. The asymmetry is the point — it may fill gaps, never overturn decisions — so under-specification still costs a round-trip and remains the failure mode this section exists to prevent.

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

1. **Resolve from precedent.** Re-read the actual code at `<plan_ref>` with `git show <plan_ref>:<path>` (and `git grep` for the sibling pattern). Pin the decision by rewriting the bullet with a concrete answer and a `[precedent: path/to/file:NN]` citation. Most hedges dissolve here — the planner already knows what to do, it just hasn't committed to it yet.

2. **Surface as a Decision gate (step 6.5).** Used only when step 1 genuinely cannot decide — two approaches are equally grounded and the choice has a user-visible consequence. Loop back to step 6.5, get the user's call, fold the answer into `## Architecture decisions` with `[user decision <date>]`.

3. **Demote to a watchpoint** under `## Risks & watchpoints` — legal **only** when the item is not a design decision. *"Floating-point drift on macro scaling: acceptable per PRD §10.3"* is a watchpoint (an accepted runtime trade-off with named rationale). *"Resolver picks the shape"* is a design decision and cannot be demoted.

**Exit gate.** After the sweep, no hedge phrasing may remain anywhere in the plan body. The phrasings that may legitimately survive are: concrete decisions with precedent citations, deviations recorded in `## Deviations from project docs` with their agreed date, user-locked decisions with `[user decision <date>]`, and watchpoints in `## Risks & watchpoints`. If a hedge slips through, the dimension-4 reviewer will catch it at step 8 — but that's a passive backstop, not a substitute for this sweep.

**Why this step exists.** The dominant failure mode of this skill is letting `Resolver picks the shape; both are acceptable` survive to the posted plan. The resolver's audit (its dimension 4) catches it, the user routes back here in revise mode, and the planner resolves the choice — by reading the same code at the same ref it could have read on the first pass. Step 7.5 closes the gap in-loop. The cost is one focused grep + a few targeted `git show` reads; the saving is a full plan round-trip and a delayed implementation.

## Step 8: Verify the plan (isolated review loop)

Before showing the plan to the user, hand it to an isolated review sub-agent — the same pattern the drafter and resolver use, for the same reason: you drafted the plan holding the conversation, the user's framing, and your research notes, none of which appear in the posted comment. From that vantage you can't tell whether the plan stands on its own. The sub-agent simulates a fresh implementer reading only the plan + the issue + the docs + the codebase. If it can't tell whether the plan is executable from those inputs alone, neither can the resolver.

**Invocation.** Spawn an `Explore` sub-agent with the prompt template at `references/plan-reviewer-prompt.md`, filling the `<<placeholders>>`: the plan body, `mode` (`draft` or `revise <N>`), `issue_number`, `repo_owner`/`repo_name`, `repo_root`, `plan_ref` (the git ref the plan was built against — `origin/main`, or the epic branch HEAD for a story under an open epic), `dimensions`, `external_sources`, `epic_plan` (for a just-in-time story-under-epic review, the parent epic's plan body — for Dimension 8; empty otherwise), and `epic_delivery_log` (that review's parent-epic `<!-- epic-delivery-log:v1 -->` comment, or `(none yet)`). The sub-agent runs **without** the conversation history — that isolation is what makes the review meaningful.

**Dimensions.** Nine, defined in the prompt. Pass the subset that applies:

| Type | Dimensions passed |
|---|---|
| Bug (single-phase) | 1, 2, 3, 4, 6, 9 |
| Feature / incomplete / standalone story (single-phase) | 1, 2, 3, 4, 6 |
| Story under an epic (just-in-time plan) | 1, 2, 3, 4, 6, 8 |
| Multi-phase issue (Step 3 classification) | 1, 2, 3, 4, 6, 7 |
| Epic-level plan | 1, 2, 3, 5, 6 |

Dimensions: 1 doc/constitution coherence, 2 codebase coherence, 3 goal coherence (the changes + tests actually satisfy the issue's acceptance criteria / DoD), 4 implementation readiness, 5 **sequencing** (epic-level plan only — reads the epic plan's own `## Story contracts` to topologically check the `## Story breakdown` order; no longer needs every story planned), 6 precedent grounding, 7 **phase coherence** (multi-phase only — see below), 8 **epic-story coherence** (a just-in-time story plan checked against the parent epic plan's contracts — see below), 9 **coverage-gap closure** (bug fixes only — see below).

**Dimension 7 — phase coherence.** Fires when the plan has a `## Phases` section (multi-phase issues only — an epic uses `## Story contracts` with Dimensions 5/8 instead). The reviewer checks:

- Every phase has all required keys (`kind`, `ships`, `closes-dod`, `deliverable`, `depends-on`). A missing key is a BLOCKER — the resolver depends on each key for routing, and an absent key forces the resolver to either hand-wave a default or stop and route back here.
- The union of all phases' `closes-dod` references covers every DoD bullet in the issue body **exactly once** (no gaps, no duplicates). A DoD bullet not closed by any phase is a BLOCKER: the planner would have filed a plan that leaves work unaccounted for, and the evaluator's DoD check on the final PR would surface that gap only after implementation is done. A DoD bullet claimed by two phases is a SUGGESTION (clarify which phase actually delivers it) unless both phases are `code-shipping` and ship overlapping diffs — then it's a BLOCKER.
- Every `depends-on` reference resolves to an earlier-numbered phase (no cycles, no forward references). Cycle and forward-reference are BLOCKERs.
- At least one phase is `kind: code-shipping`. A plan with only `operator` / `decision-only` phases doesn't need this skill — it's a discussion, not an implementation; flag as BLOCKER and route back to the user to reclassify.
- Each `operator` / `decision-only` phase's `deliverable` reads as actionable prose a human can execute without re-deriving context (the resolver quotes it verbatim into the user-facing handoff). A `deliverable: "the measurement run"` is too vague — BLOCKER; `deliverable: "run ./scripts/spike-640.sh, post the per-cell table from build/spike-640-*.log to #640"` is correct.

**Dimension 8 — epic-story coherence.** Fires on a just-in-time story-under-epic review (the parent epic plan is passed as `<<epic_plan>>`, its delivery log as `<<epic_delivery_log>>`). The reviewer checks the story plan's `## Epic contract`: it delivers every contract the epic's `## Story contracts` assigns it (matching shape — BLOCKER on a miss); it consumes only contracts already recorded in the epic's `<!-- epic-delivery-log:v1 -->` comment **and with a shape matching what the log records as delivered** (out-of-sequence consumption, or a consumed shape that doesn't match the delivered shape, is a BLOCKER; a `Consumes: (none)` is always fine); and it doesn't contradict the epic `## Approach`. A Dimension-8 BLOCKER that traces to a wrong *epic* contract is remediated by the epic-plan **feedback edge** — stop and re-route to the planner on the epic in revise mode (don't reshape the story to fit a wrong contract, and don't run the epic revise inline mid-story-session); see "Just-in-time story planning".

**Dimension 9 — coverage-gap closure.** Fires on a bug fix (the `Bug (single-phase)` row). The reviewer reads the plan's `## Coverage gap` against the root cause, the existing tests, and the regression test in `## Test plan`, all at `plan_ref`, and BLOCKs when: the named escape isn't real (a cited test already covers the path, or the escape is vague); the `Closed by:` regression test wouldn't have caught the bug (its assertion already holds against the pre-fix code, or it only asserts the fix in isolation); or an `Escape:` entry has no matching `Closed by:` (a named regression test, or a sanctioned `Closed by: (none)`). The full check is in `references/plan-reviewer-prompt.md`.

Pass the dimensions list to the reviewer prompt as the `<<dimensions>>` placeholder; its `Dimensions to check` line accepts `{1..9}`. For an epic-level review, pass the epic plan as `<<plan_body>>` (Dimension 5 reads its `## Story contracts`); for a just-in-time story-under-epic review, also fill `<<epic_plan>>` with the parent epic plan and `<<epic_delivery_log>>` with its `<!-- epic-delivery-log:v1 -->` comment so Dimension 8 can check the story's `## Epic contract` against the epic's `## Story contracts` and the delivery log.

**Loop control** — same shape as the drafter/resolver loops:

```
prev_findings = []
for pass in 1..3:
  findings = plan_reviewer.run(plan, mode, plan_ref, dimensions, epic_plan, epic_delivery_log)
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

This call is idempotent — re-running on an already-labelled issue is a no-op, so it's safe in revise mode and across just-in-time story planning (where every story passes back through this step). If the label doesn't yet exist in the repo, the first call fails with `could not add label: 'planned' not found`; create it once with:

```bash
gh label create planned --repo <owner/repo> --color FBCA04 --description "Implementation plan posted by github-issue-planner"
```

then re-run the `gh issue edit` call. The trivial-skip branch at step 3 never reaches step 10, so it correctly never applies the label — the planner deliberately declined to author one, so the issue is not planned. The label is a low-stakes signal: if the call fails (network blip, permissions), log it and move on rather than blocking the handoff. The plan comment is already posted; the label is a convenience for issue-list scanning, not part of the audit trail.

## Step 11: Epic plan (then just-in-time stories)

When the target is an **epic**, author the high-level epic plan and stop — do **not** fan out every story's full plan up front. Per-story plans grounded against one epic-branch snapshot go stale the moment a predecessor story lands (the resolver then re-plans each one anyway); the durable up-front artifact is the epic plan, and each story is planned just-in-time against current epic HEAD (see "Just-in-time story planning").

1. **Plan the epic itself.** Author the epic-level `## Approach`, `## Story breakdown`, `## Story contracts` (the cross-story seams — per story, what it `delivers` / `consumes`), `## Integration strategy`, and the `## Definition of done` grounding. Verify with dimensions **1, 2, 3, 5, 6** — Dimension 5 fires here, topologically checking the `## Story breakdown` order against the `## Story contracts` graph (no sibling plans needed). Post it, ensure the issue-body pointer, and apply the `planned` label (Step 10). The `<!-- epic-delivery-log:v1 -->` comment is **not** created here — the evaluator creates it lazily when the first story merges.
2. **Check whether the child stories are filed as issues.** Get the reconnaissance from `github-ops` — `GATHER_EPIC(epic=<N>, repo=<owner/repo>, dependency=<commit/file/PR a story depends on, if relevant>, scratch_dir=/tmp/gh-planner-<N>/)` returns `epic_body_path` (`Read` it from disk — the epic body is the one verbatim payload here), the parsed `## Stories` list (each `{number, title, checked, state}`, or a flag that they're plain bullets with no `#NN`), the resolved `epic/<N>-<slug>` branch (local + remote), and whether the named dependency has landed. From that list:
   - **Stories are filed** (`- [ ] #NN — title` lines) → **stop after the epic plan.** Hand off (Step 12) to plan the **first** story in `## Story breakdown` order just-in-time (`/github-pipeline:github-issue-planner #<first-story>`); each subsequent story is planned just-in-time as it becomes the next to build. Don't author the per-story plans now.
   - **Stories are not filed** (plain bullets, no `#NN`) → **stop after the epic plan.** Tell the user: "The child stories aren't filed yet. Run `github-issue-drafter` to file them (it owns issue creation), then re-run me on each story just-in-time as you build it." Filing issues is the drafter's job, not the planner's — don't create them here.

## Just-in-time story planning

Triggered when this skill is invoked on an issue that is a **story under an open epic** — detected the same way the resolver detects it: a `**Epic:** #<N>` backlink in the issue body, or a `story` label plus a parent-epic search (`gh issue list --label epic --state all --search "#<story-number> in:body"`). This is the per-story counterpart to Step 11: the epic plan is already posted with its `## Story contracts`; this mode authors *this* story's plan against the codebase as it exists now, then hands off to the resolver.

Planning the story now — rather than up front with its siblings — is what keeps it current: it grounds against the epic branch HEAD *after* every predecessor story has landed, so it never plans on code that's since moved.

1. **Fetch the story + the epic plan + the delivery log.** `GATHER_ISSUE` for the story (body, thread, any existing story plan → revise within this mode if present). Then fetch the parent epic's `<!-- implementation-plan:v1 -->` comment and `Read` its `## Approach`, this story's `## Story contracts` entry (what it must deliver / may consume), and `## Story breakdown`. Also fetch the epic's `<!-- epic-delivery-log:v1 -->` comment — the evaluator's record of what predecessor stories actually delivered (`(none yet)` if no story has merged; format + writer/reader contract in [`../_shared/epic-delivery-log.md`](../_shared/epic-delivery-log.md)).
2. **Resolve the integration target.** Discover the `epic/<N>-<slug>` branch (`git ls-remote --heads origin "epic/<N>-*"`) and capture its **current HEAD** — that `epic/<N>-<slug>@<short-sha>` is this story's `plan_ref`.
3. **Reconcile contracts against what actually shipped.** Compare the delivery log's recorded shapes (from step 1) against what the epic plan's `## Story contracts` pinned for those predecessors. If a predecessor delivered a *different* shape than pinned, the epic plan is stale — **stop and re-route to the planner on the epic in revise mode** via the Step 12 re-route handoff (`/github-pipeline:github-issue-planner #<epic> — re-plan: #<pred> shipped <actual> but the contract pinned <pinned>`). Don't run the epic revise inline mid-story-session and don't ground this story on a stale contract; once the epic is re-planned (its `## Story contracts` corrected and Dimension 5 re-run — which may reorder `## Story breakdown`), the user re-runs the planner on whatever story is now next. The planner only **reads** the delivery log — the evaluator is its sole writer (it appends each story at merge, `github-pr-evaluator` §13); never write it here.
4. **Ground and draft this story.** Run Steps 5–7 against `plan_ref` (the epic branch HEAD): read code at that ref, ground every decision, and draft the story plan with the standard schema, the `**Epic:** #<N>` backlink first after the marker, and a `## Epic contract` section naming what it `Delivers` (matching the epic's `## Story contracts`) and `Consumes` (each already recorded in the epic's `<!-- epic-delivery-log:v1 -->` comment), `[epic-plan: #<N>]`-cited.
5. **Verify (Step 8) with dimensions 1, 2, 3, 4, 6, 8** — pass the parent epic plan as `<<epic_plan>>` and its delivery-log comment as `<<epic_delivery_log>>` so Dimension 8 checks this story's contract against the epic's `## Story contracts` and the delivery log. A Dimension-8 BLOCKER that traces to a wrong *epic* contract is the same **feedback edge** as step 3 — stop and re-route to the planner on the epic in revise mode (don't reshape this story to fit a wrong contract, and don't run the epic revise inline).
6. **Show, persist, label, hand off.** Auto-post on a clean verify exit (Step 9 → Step 10: post the story plan, apply the `planned` label to the story). Then emit the Step 12 handoff forward to the resolver on this story.

Revise mode applies here too: if this story already has a plan, refresh it against today's epic HEAD per Revise mode, with the same Dimension-8 check.

## Step 12: Handoff

Every clean run ends with a single `## Handoff` block — the schema, omission rules, and state-marker vocabulary live in [`../_shared/handoff-format.md`](../_shared/handoff-format.md). The handoff bridges this session and the next: the user will copy the fenced command into a fresh Claude Code session. Don't skip it on a clean exit; don't add anything after it.

This step fires at the end of every clean exit path: after Step 10 (single-issue plan posted), after Step 11 (epic plan posted), after a Just-in-time story plan is posted, and from the trivial-skip branch at Step 3 where the planner declined to author a plan. Revise mode (below) routes through the same step.

The snapshot lines are mechanical — the issue/Epic number and title are already in hand from Step 2's `GATHER_ISSUE`, the plan-comment URL was captured at Step 10, and child-story state for an Epic is from Step 11's `GATHER_EPIC`. When Step 4 ingested a research dossier, the `Issue:` / `Story:` line also carries `research: ✓ (<dossier-url>)` (omitted when no dossier exists), per `../_shared/handoff-format.md`. The `Why:` line is judgment — describe what the next session will do.

**Before composing the handoff, `Read references/handoff-renderings.md`** — it holds the worked `## Handoff` shapes the planner emits: single-issue plan posted, epic plan posted (contracts pinned; stories planned just-in-time), just-in-time story plan posted, epic plan with stories not yet filed (route to the drafter), trivial change (no plan), knowledge-gap re-route to the researcher, and revise-mode refreshed. It's a progressively-disclosed reference — not auto-loaded with this skill — so the forced Read is what guarantees the shapes are in your working context before you emit; without it the handoff may be written from memory and drift from the closed-set shapes. Each carries the closed-set state-marker vocabulary from [`../_shared/handoff-format.md`](../_shared/handoff-format.md); fill the snapshot from the data Step 12 lists above.

## Revise mode

Triggered when a plan comment already exists (step 2) or the user asks to update/refresh a plan. Plans go stale: the codebase moves, the issue body gets revised, external docs change, the comment thread settles on a new direction. This mode refreshes the plan against today's reality.

When the issue already has work in flight (a draft PR with shipped phases on its `## Phase tracker`), revising the plan can also disturb already-projected DoD ticks on the issue body (see `github-issue-resolver` §9's "DoD projection rule" and [`../_shared/dod-annotations.md`](../_shared/dod-annotations.md) for the projection contract). The planner is the deliberate owner of the reconciliation between the old plan, the new plan, and the body's ticks — see "Re-plan reconciliation" below.

1. **Fetch the existing plan + downstream state.** Fetch the existing plan comment (step 2) and the issue + thread (note the plan's recorded SHA). Also check whether a draft PR exists for this issue (`gh pr list --search "linked:#<N>" --json number,state,isDraft,body,headRefName`) — if so, fetch its body and parse the `## Phase tracker`. Fetch the issue body to capture the current state of its `## Definition of done` annotations. Hold all four (old plan, issue body, PR body+tracker, captured annotations) in working context for the diff.
2. **Identify what changed since the plan was written** — re-walk the thread for newer decisions, re-grep the codebase for symbols the plan names that may have drifted, re-read any external sources.
3. **Re-run steps 5–8** focused on what changed (don't re-derive untouched sections from scratch).
4. **Compute reconciliation.** Diff the old plan against the new plan, classify the revise as SOFT or HARD per "Re-plan reconciliation" below, and compute the body-edit diff (which body annotations to re-attribute, un-tick with predecessor annotation, or preserve). When no draft PR exists yet (resolver hasn't started), step 4 is a no-op — the body has no projected ticks to reconcile.
5. **Show + confirm (step 9 variant) + persist.** Show the diff-style plan update (step 9) **and** the proposed body-edit diff together. For SOFT, the confirm is **Apply** / **Cancel**. For HARD, the confirm is **Start fresh (recommended)** / **Apply in place anyway** / **Cancel**. On Apply (any path): delete-and-repost the plan comment (step 10) and refresh the body pointer's URL. SOFT-Apply also `gh issue edit`s the body with the reconciled DoD. HARD-Start-fresh additionally closes the existing PR with a re-plan note, un-ticks the body's DoD with predecessor annotations, and records a `## Predecessor` section on the new plan (see below).

**Revising an epic plan** re-checks the cross-story contracts against reality: reconcile `## Story breakdown` + `## Story contracts` against each story's current state and the `<!-- epic-delivery-log:v1 -->` comment, and re-run Dimension 5 (sequencing on the contracts). Surface any re-ordering or contract change with evidence; don't silently swap. Already-posted story plans are revised individually via "Just-in-time story planning" revise, not from here.

## Re-plan reconciliation

**See [`references/revise-reconciliation.md`](references/revise-reconciliation.md)** for the full re-plan reconciliation procedure — the SOFT vs HARD classification rules, the SOFT-path body-annotation reconciliation, the HARD-path "Start fresh" sequence (close the PR, predecessor-annotate the DoD bullets, add a `## Predecessor` section), and two worked examples. Annotation shapes and the parser are in [`../_shared/dod-annotations.md`](../_shared/dod-annotations.md).

## Common pitfalls

- **Don't plan an issue that isn't filed.** This skill plans existing issues. If the work isn't filed yet, route to `github-issue-drafter` first.
- **Don't manufacture a plan for a trivial change.** A one-line fix doesn't need a plan; saying "this is trivial, go straight to the resolver" is the right answer, not a thin plan posted for form's sake.
- **Don't fix a bug without closing the test gap that let it ship.** Repairing the defect and stopping leaves the same blind spot that hid it — the next regression on that path is just as invisible. For every bug, `## Coverage gap` must name which existing test should have caught it and why it didn't, and `## Test plan` must lock a regression test that fails against the pre-fix code (or, when the defect can't be reproduced in an automated test, `Closed by: (none)` naming that reason). "Add a regression test" deferred to the resolver with no gap analysis is the failure mode this prevents; Dimension 9 enforces it.
- **Don't over-specify.** Lock decisions, not lines. A plan that transcribes the diff is brittle and wastes the resolver's judgment. Bind what would send implementation down the wrong path; leave the rest.
- **Don't punt design decisions to the implementer.** Phrasings like "Resolver picks the shape", "either approach is acceptable", "we could go with X or Y", "TBD", "recommend X" leak into the plan when the planner is unsure but doesn't want to dig. The cost is a full plan round-trip: the resolver's audit catches the hedge as a dimension-4 BLOCKER, the user routes back to the planner, and the planner resolves the decision anyway — by reading the same code at the same ref it could have read the first time. Step 7.5's sweep exists to prevent exactly this. Either resolve the decision from precedent (read the file, cite the pattern), or surface it as a Decision gate (step 6.5). Never both leave it open and post.
- **Don't deviate silently.** Any departure from architecture / architecture-notes / ui-design / precedent goes through the step-6 user gate and is recorded in `## Deviations`. A constitution violation isn't a deviation — reshape the plan or surface that the issue can't be built as written.
- **Don't skip the verify loop.** An unverified plan is more dangerous than no plan: it carries the authority of a posted artifact while potentially referencing APIs that don't exist or contradicting the constitution. The isolated reviewer is the cheap guard against that.
- **Don't leak conversation context into the reviewer.** The sub-agent must read only the plan + issue + docs + codebase. Injecting your framing defeats the fresh-reader test.
- **Don't store the plan in the issue body.** The body is the drafter's artifact and gets repainted in its revise mode; a plan there would be clobbered. The marker comment is the durable home; the body only gets a one-line pointer.
- **Don't file child stories from the planner.** When an epic's stories aren't filed, route to the drafter. Creating issues here blurs the boundary and skips the drafter's review loop.
- **Don't fan out full per-story plans up front for an epic.** Authoring every story's detailed plan in one run grounds them all against one epic-branch snapshot; the moment a predecessor story lands, the later plans reference code that moved, and the resolver re-plans each one anyway. Post the epic plan (`## Story contracts` + sequencing) up front and plan each story just-in-time against current epic HEAD (Step 11 + "Just-in-time story planning"). The cross-story rigor lives in the epic plan's contracts (Dimension 5) and the per-story Dimension-8 check, not in a batch of stale full plans.
- **Don't fabricate citations or symbols.** Every `[precedent: …]` must point at a real file/section. If you can't cite it, it's a deviation or under-researched — handle it as one, don't invent a reference.
- **Don't re-plan from scratch in revise mode.** Refresh what changed; leave untouched sections alone. Show the user a diff, not a wall.
- **Don't author free-form sequencing for multi-phase work.** Multi-phase issues use the structured `## Phases` section (Step 7's schema) with the fixed `kind` / `ships` / `closes-dod` / `deliverable` / `depends-on` keys per phase. Prose like *"Phase 1 ships X, then Phase 2 measures, then Phase 3 writes up the decision"* reads correctly to a human but the resolver parses `## Phases` deterministically to route each phase — it cannot grep loose prose for a `closes-dod` mapping or a `kind` enum, and silently falls back to hand-waving (which is exactly the regression mode this whole change was made to prevent — #640's Phase 1 PR shipped to `main` partway through the DoD because the prior `## Sequencing` section gave the resolver no way to recognise that more phases were due). If a phase doesn't fit the structured keys, that's a signal the phasing itself is unclear and needs re-thinking — not a signal to relax the format.
- **Don't write a `closes-dod` bullet for the wrong phase.** The evaluator uses `closes-dod` to map shipped phases to satisfied DoD bullets on its final acceptance-criteria check. A substrate phase that claims it closes a measurement DoD bullet (on the grounds that "my code is *needed* for the measurement to run") will cause the evaluator to score the PR as satisfying that bullet before the measurement has actually been performed. `closes-dod` names the phase whose **deliverable satisfies the DoD bullet**, not the phase whose code enables it. Substrate and infrastructure phases that only enable later phases use `closes-dod: (none)`; the bullet they enable is claimed by the phase whose `deliverable` is the actual artifact the DoD asks for.
- **Don't apply SOFT reconciliation when classification reads HARD.** The body-edit diff for HARD often deletes ticks the user expects to see (un-ticks bullets attributed to phases whose `ships` field changed); the right response is starting fresh, not papering over the divergence with un-ticks on a PR whose existing commits no longer match the new plan. The evaluator's per-phase verification would catch the same divergence at PR-readiness time and un-tick anyway — making the resolver run on an in-place reconciled PR mostly wasted work. When the classification is genuinely ambiguous, surface the three-way confirm and let the user decide.
- **Don't auto-clear evaluator-rejection annotations during revise.** A bullet annotated `(resolver claimed phase X, ...; evaluator rejected: ...)` is the evaluator's hard signal that the prior code didn't satisfy the bullet. The temptation during a SOFT-path reassignment is to swap the annotation for the new phase attribution and let the projection rebuild from scratch — but doing so silently removes the evaluator's evidence and re-introduces the silent rubber-stamping failure mode the per-phase verification exists to prevent. Always surface evaluator-rejected bullets to the user at step 9 and confirm the new plan's approach addresses each rejection. If the user confirms, the rejection annotation transitions to either the new attribution (SOFT reassignment they explicitly accepted) or the predecessor annotation (HARD "Start fresh"). Without that confirmation, preserve verbatim.

## When to ask the user

- The repo or issue number is ambiguous.
- The best approach deviates from the docs or precedent (always — step 6).
- The thread shows unresolved disagreement between maintainers about the approach.
- An epic's stories aren't filed yet (stop and route to the drafter).
- An external source the user provided contradicts the project docs (whose intent wins?).
- The verify loop ends in cap/circular with a blocker that needs a human decision.

## Why this matters

Planning is where the expensive mistakes are cheapest to prevent. A wrong architectural decision caught in a plan costs a paragraph to fix; the same decision caught in review costs a re-implementation, and caught at integration costs a re-integration. Capturing the plan as a verified, durable artifact — rather than letting it evaporate in a manual planning session — means the resolver executes a vetted approach, the PR evaluator can check the result against it, and the next person to touch the issue sees *how* it was meant to be built, not just *what*.

For an epic, this is why the durable artifact is the epic plan's pinned cross-story contracts rather than a batch of per-story plans: the contracts are what stay true as stories land, so each story can be planned fresh against real code yet still fit the whole — eliminating the staleness that made up-front per-story fan-out a wasted, re-planned-anyway round-trip.
