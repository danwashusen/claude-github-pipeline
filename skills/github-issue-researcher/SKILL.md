---
name: github-issue-researcher
model: opus
effort: medium
description: You're prepping a filed GitHub issue for planning and it hinges on something the model may not recall accurately — a dependency/SDK/framework/platform version, a migration path, breaking changes, current API behavior or defaults, or vendor guidance. Use this skill to look it up on the web, verify it against authoritative/official sources, and post a dated, cited research summary as a comment on that issue. Trigger on requests to pull a current migration guide or breaking changes for #N, check the latest behavior of a named technology, verify a claim against official docs, or re-ground research a planner flagged as stale — then write it onto the ticket. Common framing is "my memory/training is out of date, ground this in real docs before we plan #N"; even so, the goal is gathering external truth, not designing. Do NOT use for: filing a new issue (github-issue-drafter); settling the approach or architecture or file changes (github-issue-planner); writing or fixing code (github-issue-resolver); reviewing or merging a PR (github-pr-evaluator); the project's own internal code; or quick questions with no issue and no currency risk.
---

# GitHub Issue Researcher

Turn a filed GitHub issue into a verified, durable **research dossier** of current external truth that the planner ingests before it designs the approach. The drafter answers *what* to build; the planner answers *how*; the resolver *builds* it; this skill answers a narrower, upstream question: **"what does whoever plans this need to know from the outside world that the model can't reliably recall?"** — and captures that answer as a cited, dated, fetched-not-recalled artifact on the issue.

A model's training knowledge has a cutoff. Framework versions, library APIs, vendor guidance, and standards move faster than that cutoff, and a plan grounded in stale recall is confidently wrong in a way that looks authoritative. This skill's whole reason to exist is to replace recall with **fetched, attributed current truth** for the parts of an issue where that matters — and to make the provenance auditable, so the planner (and a future reader) can see which source informed which decision and re-check it when the source moves.

## The contract — research is input, never authority

This skill produces an *input to planning*, not a plan. The boundary is load-bearing:

- The dossier reports **external truth, its implications, and any tensions it surfaces**. It may offer a clearly-marked strawman, but it **never** posts an implementation plan, **never** declares an architecture decision settled, and **never** edits code.
- The dossier flows **through** the planner: the planner reads it, records each source in its plan's `## External sources consulted`, and lets findings inform its decisions — but the planner owns every decision. The resolver trusts only the planner's `<!-- implementation-plan:v1 -->` comment; it never reads this dossier directly. That keeps the resolver's "the plan is the single source of truth" invariant intact while adding durable external grounding.

Overstepping into plan-authority is the dominant failure mode of a research skill, and the validation loop (step 8) treats it as a blocker.

## Project-agnostic by design

This skill names **no** language, framework, or vendor. It works unchanged on any project — web, mobile, backend, library — because it **discovers** the project's stack and conventions at runtime (step 3) rather than assuming them. Every example below uses neutral placeholders (`<dependency>`, `<official-docs-url>`). When you run it, "the project's stack" and "the project's governing docs" mean whatever this particular repo actually uses and ships. Do not hard-code knowledge of any specific ecosystem into a dossier; derive it.

## Asking the user a decision

When you need a decision from the user — the confirm gate on the derived questions, or a disambiguation — ask it through the `AskUserQuestion` tool, not as freeform prose. The tool renders the same multiple-choice card every time, so the user pattern-matches the decision at a glance.

Shape every ask the same way:
- One decision per question. `header` ≤ 12 chars (e.g. "Questions", "Sources", "Scope").
- 2–4 options. Each `label` is the action in imperative form; each `description` says what that choice does and its consequence.
- The tool always appends an "Other" free-text choice, so don't pad to four options — leave room for the user to type a custom answer.
- When the answer is inherently open-ended (e.g. "add any questions of your own"), a prose ask is fine — don't force it into options.

`AskUserQuestion` is **not** available inside a sub-agent spawned via the `Agent` tool. The validation sub-agent (step 8) and any research sub-agent surface a decision by returning a structured "decision needed" signal to this main loop, which asks the user and re-dispatches. Never tell a sub-agent to call `AskUserQuestion` itself.

## Delegating mechanical work to `github-ops`

This skill runs on a high-effort model, but only the *research judgment* — deriving questions, weighing sources, synthesizing, holding the input-not-authority boundary — is worth that. The judgment-free GitHub I/O (fetching the issue + thread, looking up an existing dossier, posting/editing the comment) does not need it.

Delegate that I/O to the **`github-ops`** sub-agent (`subagent_type: "github-pipeline:github-ops"`, pinned to Sonnet + medium effort — spawn it with **no `model` override**). It runs the named operation and returns faithful structured results: `GATHER_ISSUE` and `PERSIST_COMMENT` are the two this skill uses (see `${CLAUDE_PLUGIN_ROOT}/agents/github-ops.md` for the full contract). It returns issue bodies and threads **verbatim** — never summarized — so every judgment stays yours. Web research does **not** go through `github-ops` — it is the GitHub-I/O executor only; you run `WebSearch`/`WebFetch` (and the `deep-research` escalation) yourself.

Like the validator, `github-ops` cannot call `AskUserQuestion`. If it hits an ambiguity or a write conflict it returns `DECISION_NEEDED: <…>` and performs no write; surface that to the user and re-dispatch with the answer. You only hand it a `PERSIST_*` after the user has cleared step 5's gate.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status`). If it isn't, stop and tell the user — don't work around it.
- `WebSearch` / `WebFetch` available. If web access is unavailable in this environment, stop and say so — this skill cannot do its job from memory, and pretending to would defeat its entire purpose.
- Working directory is the repo the issue belongs to, OR the user supplied `--repo owner/name` context.
- The issue already exists (this skill researches filed issues; it does not file them). If the work isn't filed, route to `github-issue-drafter` first.

## Modes

- **Broad** (`/github-pipeline:github-issue-researcher #N`) — derive the research questions from the issue + the project's stack, confirm them, gather, synthesize, post the dossier. The default first run.
- **Targeted** (`/github-pipeline:github-issue-researcher #N — <question>`) — the questions are given (typically because the planner hit a specific knowledge gap and routed here). Skip derivation and the confirm gate; gather + validate + update the relevant dossier section; post.
- **Revise** — an `<!-- issue-research:v1 -->` dossier already exists. Refresh what changed (re-fetch sources that may have moved, add answers to new questions, re-date claims) and delete-and-repost. Don't re-research untouched sections from scratch; show the user a diff.

## The core loop

1. **Identify** the issue — parse the number/URL.
2. **Fetch** the issue, its thread, and any existing dossier. An existing dossier ⇒ **revise mode**.
3. **Discover** the project's stack and governing docs (runtime, language-agnostic).
4. **Derive** the research questions and **scale to the work** — decline cleanly when there's nothing to research.
5. **Confirm** the question list and source plan with the user (broad mode only).
6. **Gather** current truth from credibility-tiered sources; escalate the deep ones to `deep-research`.
7. **Synthesize** the dossier against the schema.
8. **Validate** with the isolated validation sub-agent (≤3 passes).
9. **Persist** the dossier as a marker comment.
10. **Handoff** to the planner.

Never skip step 5's confirm gate in broad mode (it's cheap and keeps you from researching the wrong thing), step 6's fetch-don't-recall discipline (the skill's whole value), or step 8 (an unverified dossier carries the authority of a posted artifact while potentially being recalled fiction).

## Step 1–2: Identify and fetch

Parse the issue number/URL the same way the planner does. Then fetch the issue, its full thread, and any existing dossier in one pass — delegate to `github-ops`:

> `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- issue-research:v1 -->", scratch_dir=/tmp/gh-researcher-<N>/)`

`Read` the body and thread from the returned paths. If `marker_comment_present` is true, `Read` the existing dossier from `marker_comment_path` and go to **revise mode** — its `id` is what step 9 deletes (if `marker_comment_count > 1`, `github-ops` returns `DECISION_NEEDED`; disambiguate with the user). Reuse the same `scratch_dir` for every subsequent dispatch this run.

If a planner dossier-consumer or a maintainer in the thread already named specific questions, capture them — they feed step 4.

## Step 3: Discover the project's stack and governing docs

You can't filter research against "the project's actual stack" without learning what that stack is — and you must learn it from the repo, not assume it. This is what makes the skill portable.

- **Dependency / build manifests** — read whatever the repo actually has. The names below are **examples, not a checklist** — find this repo's real manifest, which may be a lockfile, a build-config file, or a project-generator manifest you don't recognise: `package.json`, `Gemfile`/`Gemfile.lock`, `go.mod`, `Cargo.toml`, `pyproject.toml`/`requirements.txt`, `*.csproj`, `pom.xml`/`build.gradle`, `composer.json`, `Package.swift`, and project-generation/build configs (`project.yml`, `Project.swift`, `*.bazel`, etc.). These name the dependencies and, crucially, their **pinned versions** — the single most important signal for "is my recall current?" If the obvious manifest isn't where you expect, grep for version pins rather than assuming the repo has none.
- **Governing docs** — read the README, `CONTRIBUTING`, anything under `docs/`, and `CLAUDE.md` plus the files it `@`-references. These define the project's constraints, conventions, and any non-negotiable rules. A research finding that contradicts one of these is a *tension to surface*, not a recommendation to make (step 8, dimension 5).
- **The issue's own surface** — the files, components, and dependencies the issue body and thread name.

From these, write a one-line **stack context** summary you'll put verbatim in the dossier (e.g. *"`<framework>` `<version>` via `<package-manager>`; `<service>` accessed through `<client-lib>` `<version>`; CI on `<platform>`"*). This is the lens every research question is filtered through.

## Step 4: Derive the research questions and scale to the work

This is the crux: what an issue needs researched depends entirely on the issue. Derive the questions; don't guess at a fixed checklist.

**First, the decline gate — is there anything here with currency risk at all?** This is a real fork, not a footnote: most of this step assumes you'll go on to derive questions, so a top-to-bottom reader drifts toward "produce some." Resist that. A surface earns a research question only when at least one of these holds:
- the dependency is **pinned to a version at or past the model's training cutoff** (recall is likely stale or absent);
- the area is **fast-moving** (vendor APIs, security guidance, deprecation timelines, platform policies);
- the issue hinges on **behaviour the model would otherwise assert from memory** (default values, rate limits, breaking changes, recommended patterns) where being wrong sends the plan down the wrong path;
- the issue **explicitly asks** for current best practice / official guidance / a standards baseline.

If you walk all four against the issue and **none fire**, there is nothing to research. Say so plainly, post nothing, and route to the planner — go straight to the Step 10 "nothing to research" handoff. A clean "no research needed here" is a correct and valuable outcome, not a failure. To decline well, state which of the four conditions you checked and why each is absent (a one-line-per-condition verdict) — that makes the decline auditable and resists both a lazy decline and an over-eager dossier.

**The design-choice trap.** The single most common false-positive route into a thin dossier is an open *design* question that masquerades as a research question. "Which pattern should we use for X?" is a **planner** decision answerable from the project's own conventions, precedent, and governing docs — it is *not* a question about external current truth, and you must not convert it into a dossier. Research questions are about what's true in the outside world (an API, a version, a deprecation, a vendor default); design questions are about what this project should do. Only the former belong here.

**Then, for the surfaces that did fire**, phrase each question so it's **answerable from a source** (e.g. *"As of `<version>`, what is the supported way to do X — and was the pre-`<version>` approach deprecated?"*), not as an open musing. Merge in any questions the user or the thread supplied.

**Scale to the work.** Over-researching is a real failure mode too — it burns time and produces a dossier of noise the planner has to wade through.
- A small, well-bounded currency question → a one- or two-question dossier.
- A version migration, a new external integration, a "current best practice" issue → the full set.

## Step 5: Confirm the questions and source plan (broad mode only)

Before spending fetches, show the user the derived question list and the **source tiers** you intend to consult, through `AskUserQuestion` (header `"Questions"`). Offer: **Proceed** (research these), **Edit** (the user adds/drops/reword — handle via the free-text "Other" or a follow-up prose ask), **Nothing to research** (when you've judged it empty, confirm and exit to the planner). This gate is cheap and stops you from authoritatively researching the wrong question.

In **targeted mode**, skip this gate — the questions are already given. In a **sub-agent context** you cannot ask; return the derived list as a structured "decision needed" signal to the caller.

## Step 6: Gather current truth (fetch, don't recall)

For each question, search then fetch. **Every claim that lands in the dossier must come from a page you fetched this run, with the fetch date recorded.** If you catch yourself writing a fact you "just know," stop and go find the source — or mark the question "no authoritative source found." Recall dressed up as research is the one thing this skill must never ship.

**Source credibility tiers** (prefer higher; label every source with its tier):
1. **Primary / official** — the maintainer's own documentation, API reference, release notes, changelog, or specification for the project's actual dependency at its pinned version. This is the strongest evidence and the default target.
2. **Standards-body / academic baseline** — recognised standards organisations, specifications, and peer-reviewed or widely-cited literature, when the question is about a cross-cutting practice rather than one library.
3. **Reputable secondary** — well-regarded community references, maintainer blog posts, conference talks. Usable for orientation and to find primary sources, but **flagged as secondary** and never presented as authoritative on its own. Prefer to trace a secondary claim back to its primary source and cite that.

Reject low-credibility sources (anonymous blogs, undated tutorials, content-farm pages, unattributed answers). When sources disagree, say so and weight by tier and date. When a question has a dedicated skill that owns it better than a generic search (e.g. a vendor-specific reference skill), prefer routing the question there.

**Hybrid depth.** Run the scoped `WebSearch`/`WebFetch` loop yourself for most questions. **Escalate to the `deep-research` skill** only for a genuinely deep or contested question — one where sources conflict, the answer is multi-part, or adversarial cross-checking across many sources is warranted. Distil its report into dossier findings (with the underlying primary citations), don't paste it wholesale.

Record for every claim: the source URL, its tier, the **fetch date**, and (for version-specific facts) the version it applies to.

**Fetch tactic — JS-rendered docs.** A primary doc site can return a title-only shell when its content is rendered client-side, which looks like a successful fetch but carries no facts. If a page you expect to be rich comes back near-empty, don't give up on the source: retry its underlying data endpoint or a server-rendered variant (many doc sites expose a `.../data/....json` or print/raw URL alongside the HTML), or fall back to an equally-primary companion (a release-notes page, a recorded session transcript). Note in the source line which form you actually read.

## Step 7: Synthesize the dossier

Use this schema. The marker is **always the first line** — any character before it makes the dossier undiscoverable to the planner's `startswith` lookup, and a consumer that can't find it behaves exactly as if no research exists. Omit optional sections when empty; never pad.

```
<!-- issue-research:v1 -->
**Research dossier** — #<N> <title> — researched <ISO-8601 UTC>, sources fetched <date(s)>

**What this is:** research input for whoever plans/implements this issue — current guidance from
the listed sources, collected and synthesized against this project's actual stack. Every cited page
was fetched on the dates shown; nothing here is from model memory. This is **not** an implementation
plan; `github-issue-planner` consumes it and owns the design decisions.

**Stack context the research was filtered against:** <the one-line stack summary from step 3>

## Questions researched
- <question> — <answered | partial | no authoritative source found>

## Consensus across sources
<what the credible sources agree on — the durable, low-risk findings>

## Findings by source
### <source name> — <primary/official | standards baseline | secondary (flagged)>
<the specific claim, the version it applies to, and the fetch date>

## Implications mapped to the issue's Definition of Done      (omit if the issue has no DoD)
- <DoD bullet> → <what the research means for satisfying it>

## Tensions for the planner to resolve
<open tensions / tradeoffs / conflicts the research surfaces — stated as questions for the planner,
 NOT decided here. A finding that contradicts the project's governing docs goes here, framed as a
 tension, never as a recommendation to override the docs.>

## Strawman draft (NOT final — planner/implementer owns the real call)      (optional)
<a concrete starting point a reader can react to, explicitly marked non-binding>

## Sources
- <url> — <tier> — fetched <date> — <what it informed>

_Authored by `github-issue-researcher`. Re-run that skill to refresh — do not hand-edit. The planner
records the provenance above in its plan's `## External sources consulted`._
```

The `researched` header takes an ISO-8601 stamp; if only the date is available, a date-only stamp (`<date>T00:00Z`) is fine — the fetch dates on the sources are what carry the currency guarantee.

Keep findings tight and attributed. The reader is the planner, who needs *facts with provenance*, not prose. Hold the boundary: implications and tensions, yes; settled decisions and code, no.

## Step 8: Validate the dossier (isolated review loop)

Before showing the dossier, hand it to an isolated validation sub-agent — the same pattern the planner and drafter use, for the same reason: you synthesized this holding the conversation and your search notes, none of which appear in the posted comment, so you can't tell whether it stands on its own. The sub-agent simulates the planner reading only the dossier + the issue + the project docs.

**Invocation.** Spawn an `Explore` sub-agent with the prompt template at `${CLAUDE_PLUGIN_ROOT}/skills/github-pipeline:github-issue-researcher/references/research-validator-prompt.md`, filling the `<<placeholders>>`: the dossier body, `mode`, `issue_number`, `repo_owner`/`repo_name`, `repo_root`, and `dimensions`. It runs **without** the conversation history — that isolation is what makes the check meaningful. It may re-fetch a cited URL to confirm the dossier represents it faithfully.

**Dimensions** (defined in the prompt): 1 citation integrity, 2 source credibility, 3 currency, 4 scope discipline (input-not-authority), 5 governing-doc conflict surfaced-not-decided, 6 answer coverage. Pass all six on a normal run.

**Loop control** — same shape as the planner's:

```
prev_findings = []
for pass in 1..3:
  findings = validator.run(dossier, mode, dimensions)
  drop_findings_without_evidence(findings)
  if findings is empty: exit_clean(); break
  if same_finding_repeated_with_no_progress(findings, prev_findings): exit_circular(findings); break
  dossier = apply(findings, dossier)   # blockers always; suggestions by default; nits skipped
  prev_findings = findings
else:
  exit_cap_reached(findings)
```

Apply findings to your own dossier directly — it's this skill's artifact to fix. A citation-integrity or scope-discipline BLOCKER that you can't resolve by fetching a real source or trimming overreach means the claim shouldn't be in the dossier — drop it or downgrade the question to "no authoritative source found." On a cap/circular exit, show the user the dossier plus a short "Validation notes" block listing the unresolved findings before posting.

## Step 9: Persist the dossier

On a clean validation exit, show the user the dossier (full body in broad/fresh mode; a diff in revise mode), then **stage it to disk and post it.** Write the full dossier (starting with the `<!-- issue-research:v1 -->` marker line) to `/tmp/gh-researcher-<N>/research.md`, then:

> `PERSIST_COMMENT(target=issue, id=<N>, repo=<owner/repo>, body_path=/tmp/gh-researcher-<N>/research.md, delete_marker_id=<OLD_DOSSIER_COMMENT_ID if revising>)`

Staging to disk (not inlining the body into the sub-agent prompt) is deliberate — it's how the other skills avoid the empty-body / truncation race. `github-ops` returns the comment URL plus `body_sha256`; capture the URL. If the empty-body guard fires (`EMPTY_BODY_FILE`), re-write `research.md` and re-dispatch.

Optionally apply a `researched` label (idempotent; mirrors the planner's `planned` label) so the issue list shows at a glance which issues carry current external grounding:

```bash
gh issue edit <N> --repo <owner/repo> --add-label researched
```

If the label doesn't exist, create it once (`gh label create researched --repo <owner/repo> --color 1D76DB --description "Research dossier posted by github-issue-researcher"`) and re-run. This is low-stakes — if it fails, log it and move on; the dossier is already posted.

A user who wants to review before posting can say "research but don't post yet"; honour that and pause here.

## Step 10: Handoff

End every clean run with a single `## Handoff` block — the schema, omission rules, and state-marker vocabulary live in [`${CLAUDE_PLUGIN_ROOT}/skills/_shared/handoff-format.md`](${CLAUDE_PLUGIN_ROOT}/skills/_shared/handoff-format.md). The forward route is to the planner: research is the planner's input.

**Dossier posted.** Forward to the planner.

```
## Handoff

**Issue:** #142 — Migrate to <dependency> v<X> · open · feature · research: ✓ (https://github.com/owner/repo/issues/142#issuecomment-XXXXX)

**Next:** plan the approach in a fresh session; the planner ingests the dossier.

    /github-pipeline:github-issue-planner #142

**Why:** the dossier captures the current, fetched behaviour of <dependency> v<X> with provenance. The planner grounds its decisions in it and records the sources in its plan's `## External sources consulted`.
```

**Nothing to research (step 4 declined).** Forward straight to the planner; no dossier exists.

```
## Handoff

**Issue:** #142 — Rename config key · open · bug · research: ✗

**Next:** plan the approach in a fresh session.

    /github-pipeline:github-issue-planner #142

**Why:** this issue touches nothing with currency risk — the model's knowledge is sufficient, so no dossier was posted. The planner proceeds directly.
```

**Targeted refresh for the planner (revise or targeted mode driven by a planner gap).** Same forward shape; `research: ✓` carries the *new* dossier URL. The `Why:` quotes the specific gap the refresh closed so the re-run planner can act without re-investigating.

## Project-agnostic discipline (hold this line)

- Never name a specific language, framework, library, or vendor in this skill's own reasoning *as an assumption*. The dossier's **content** will of course name the project's real dependencies — that's the point — but you learn those from step 3's discovery, never from a baked-in assumption about what kind of project this is.
- The skill must read identically useful on a web, mobile, backend, data, or library project. If you ever find yourself reaching for ecosystem-specific knowledge before step 3 has run, stop and discover first.

## Common pitfalls

- **Don't research what isn't filed.** This skill researches existing issues. If the work isn't filed, route to `github-issue-drafter`.
- **Don't manufacture research for a trivial issue.** "Nothing to research here, go straight to the planner" is the right answer for a typo or a pure-internal change — not a thin dossier posted for form's sake.
- **Don't recall and call it research.** Every claim cites a page fetched this run, with a date. An uncited assertion is the failure mode the whole skill exists to prevent — the validator treats it as a BLOCKER.
- **Don't overstep into planning.** Implications and tensions, yes; settled architecture decisions, file-level changes, and code, no. A strawman must be explicitly marked non-binding. The planner owns the design; this dossier is its input.
- **Don't let the dossier become a second authority for the resolver.** It flows through the planner into the locked plan. The resolver reads only the plan. Never write the dossier as if the resolver will execute it.
- **Don't trust a single secondary source.** Trace it to its primary and cite that, or flag it as secondary. Don't present community lore as official guidance.
- **Don't override the project's governing docs from the outside.** A finding that contradicts a governing doc is a *tension to surface* for the planner and user to resolve — not a recommendation to ignore the doc.
- **Don't re-research from scratch in revise mode.** Refresh what changed — re-fetch sources that may have moved, re-date claims, answer new questions — and show a diff.
- **Don't hand-edit a posted dossier.** Re-run the skill so the artifact stays attributable and the marker/lookup invariants hold.

## When to ask the user

- The repo or issue number is ambiguous.
- The derived question list is non-obvious or could go several ways (the step-5 confirm gate).
- A credible source directly contradicts the project's governing docs (surface the tension; let the planner/user resolve it — don't pick a side in the dossier).
- Web access is unavailable (stop — don't fall back to recall).
- The validation loop ends in cap/circular with an unresolved citation-integrity or scope BLOCKER.

## Why this matters

A plan grounded in stale recall fails in the most expensive way: it looks authoritative, so the resolver builds on it, the PR evaluator checks against it, and the wrongness only surfaces when the code meets the real, current API. Catching it here — as a cited, dated, verified dossier the planner ingests before it commits a single decision — is where a currency mistake is cheapest to prevent. Replacing recall with fetched truth, and making the provenance auditable, is the difference between a plan that happens to be right and one that's grounded in the world as it is today.
