# researcher — v1 functional spec (baseline)

> Source: `skills/github-issue-researcher/SKILL.md` (289 lines) + references
> (`references/research-validator-prompt.md`, 128 lines).
> Captures v1 behavior as the parity baseline for [implementation.md](../implementation.md) S16.
> v1 skill name: `github-issue-researcher`; v2 name: `researcher`.

## Overview

The researcher turns a filed GitHub issue into a verified, durable **research dossier** of
current external truth — a fetched-not-recalled artifact that the planner ingests before it
designs the approach (`skills/github-issue-researcher/SKILL.md:10`). It answers one narrow,
upstream question — "what does whoever plans this need to know from the outside world that the
model can't reliably recall?" — and never itself decides architecture, drafts a plan, or edits
code (`SKILL.md:10-18`). Session shape: single Claude Code session, triggered on an already-filed
issue (`/github-pipeline:github-issue-researcher #N [— <question>]`); inputs are the issue + its
thread + an optional existing dossier + the project's own stack/docs; output is a single marker
comment on the issue plus a `## Handoff` pointing at the planner (`SKILL.md:228-260`). It is
explicitly the **thinnest cutover candidate** for S16 — one main loop, one sub-agent reference
file, three modes, no epic/story branching, no worktree involvement.

## Artifacts written

| Artifact | Marker | Location | Section/heading set (verbatim, in order) | Trigger |
|---|---|---|---|---|
| Research dossier | `<!-- issue-research:v1 -->` (first line, always — `SKILL.md:140,143`) | Issue comment | `**Research dossier** — #<N> <title> — researched <ISO-8601 UTC>, sources fetched <date(s)>` / `**What this is:** …` / `**Stack context the research was filtered against:** …` / `## Questions researched` / `## Consensus across sources` / `## Findings by source` (with `### <source name> — <tier>` sub-headings) / `## Implications mapped to the issue's Definition of Done` (omit if issue has no DoD) / `## Tensions for the planner to resolve` / `## Strawman draft (NOT final — planner/implementer owns the real call)` (optional) / `## Sources` / trailing italic attribution line `_Authored by \`github-issue-researcher\`. Re-run that skill to refresh — do not hand-edit. The planner records the provenance above in its plan's \`## External sources consulted\`._` (`SKILL.md:142-179`) | Step 9, on a clean validation exit (step 8), after user sees the dossier (full body fresh, diff on revise) (`SKILL.md:210-212`) |
| `researched` label | n/a (plain GitHub label, not a marker) | Issue label | — | Step 9, optional, idempotent; applied via `gh issue edit <N> --repo <owner/repo> --add-label researched` after the comment posts; created once with `gh label create researched --repo <owner/repo> --color 1D76DB --description "Research dossier posted by github-issue-researcher"` if absent (`SKILL.md:218-224`) |
| `## Handoff` block | n/a (shared schema, see `handoff-format.md`) | Session output (chat, not persisted to GitHub) | Per `skills/_shared/handoff-format.md` schema | Step 10, end of every clean run (`SKILL.md:228-230`) |

Revise mode **replaces** the dossier comment: the new comment is posted, then the old one deleted
via the same `PERSIST_COMMENT` call's `delete_marker_id` parameter
(`SKILL.md:212-216`) — see Invariants for the post-then-delete ordering and its *why*.

## Artifacts read

| Artifact | Marker | Where | What's extracted |
|---|---|---|---|
| Issue body + full comment thread | n/a | Issue | The problem statement, any maintainer-named research questions, and (via `marker_comment_present`) whether a dossier already exists (`SKILL.md:75-84`) |
| Existing research dossier (self, prior run) | `<!-- issue-research:v1 -->` | Issue comment | Whole body, read via `marker_comment_path` when `GATHER_ISSUE`'s `marker_comment_present` is true — triggers revise mode; its `id` is what step 9 later deletes (`SKILL.md:81`) |
| Project dependency/build manifests | n/a | Repo working tree | Pinned dependency versions — the primary signal for "is recall stale?" (`SKILL.md:89`) |
| Project governing docs (README, CONTRIBUTING, `docs/`, `CLAUDE.md` + its `@`-references) | n/a | Repo working tree | Project constraints/conventions; a research finding that contradicts one is surfaced as a tension, never silently followed (`SKILL.md:90`) |
| The issue's own named files/components/dependencies | n/a | Issue body/thread | Narrows which stack surfaces are actually in play (`SKILL.md:91`) |

The researcher does **not** read the planner's `<!-- implementation-plan:v1 -->` comment, the
epic delivery log, or any other pipeline artifact — its only GitHub-side inputs are the issue and
its own prior dossier.

## Operator gates

| Gate | Asked via | Options | Consequence of each |
|---|---|---|---|
| **Confirm question list + source plan** (broad mode only, step 5) | `AskUserQuestion`, header `"Questions"` (`SKILL.md:117`) | **Proceed** (research these questions as derived) / **Edit** (user adds/drops/rewords, handled via free-text "Other" or a follow-up prose ask) / **Nothing to research** (confirms the skill's own empty judgment and exits straight to the planner handoff) | Gates step 6's fetch spend on the right question set; skipped entirely in targeted mode since the questions are already given (`SKILL.md:115-119`) |
| **Decline gate** (step 4) | Not literally an `AskUserQuestion` card — a self-check the skill states plainly to the user, then routes to the planner without posting | Implicit binary: research proceeds, or the skill declines and hands off with `research: ✗` | Declining is a **correct, valued outcome**, not a failure; the four currency-risk conditions and a one-line-per-condition verdict must be stated for auditability (`SKILL.md:99-105`) |
| **"Research but don't post yet"** (step 9, user-initiated) | User's own prose request, honoured by pausing after showing the dossier | Pause before `PERSIST_COMMENT` | Lets a user review before the comment lands on GitHub (`SKILL.md:226`) |
| **Ambiguous marker-comment count** (`github-ops` `DECISION_NEEDED`, step 1-2) | Surfaced to the user by the main loop (sub-agents can't call `AskUserQuestion`) | Disambiguate which comment is the live dossier | Determines which comment ID revise mode targets/deletes (`SKILL.md:81`) |
| **Validation loop cap/circular exit** (step 8) | Shown to the user as the dossier plus a "Validation notes" block before posting | Implicit: user decides whether to post with unresolved findings or intervene | Surfaces unresolved BLOCKER/SUGGESTION findings rather than silently posting or silently failing (`SKILL.md:208`) |

Per the "When to ask the user" list (`SKILL.md:279-285`): repo/issue ambiguity, a non-obvious
derived question list, a credible source directly contradicting governing docs (surfaced, not
decided), web access being unavailable (hard stop, no recall fallback), and a cap/circular
validation exit with an unresolved citation-integrity or scope BLOCKER.

## Judgment steps (model reasoning — stays in the prompt)

- **Currency-risk assessment / decline gate** (step 4) — walks four fixed conditions (version at
  or past training cutoff, fast-moving vendor/security/deprecation area, a fact the model would
  otherwise assert from memory, or an explicit ask for current best practice) against the issue;
  declines cleanly if none fire (`SKILL.md:99-105`). Main loop, not delegated.
- **The design-choice trap discrimination** (step 4) — distinguishing a genuine external-truth
  research question from a design question the planner should own ("which pattern should we use
  for X?" is *not* research) (`SKILL.md:107`). Main loop.
- **Research-question derivation and scaling** (step 4, broad mode) — phrasing each surviving
  surface as a source-answerable question, merging in user/thread-supplied questions, and scaling
  dossier size to the work (one-two questions for a small currency check vs. the full set for a
  migration) (`SKILL.md:109-114`). Main loop.
- **Stack/doc discovery** (step 3) — reading manifests and governing docs at runtime to derive a
  one-line stack-context summary; explicitly *not* assumed, must be discovered fresh every run
  (`SKILL.md:85-93`). Main loop.
- **Source tiering and credibility judgment** (step 6) — classifying each source into
  primary/official, standards-body/academic, or reputable-secondary; rejecting low-credibility
  sources; weighting disagreements by tier and date; tracing a secondary claim back to its primary
  when possible (`SKILL.md:125-130`). Main loop.
- **Hybrid depth escalation decision** (step 6) — judging whether a question is a scoped
  `WebSearch`/`WebFetch` loop or warrants escalating to the `deep-research` skill (contested
  sources, multi-part answer, adversarial cross-check warranted) (`SKILL.md:132`). Main loop.
- **JS-rendered-doc fetch tactic** (step 6) — recognizing a title-only/empty shell response and
  retrying a data endpoint, print/raw variant, or an equally-primary companion source rather than
  giving up (`SKILL.md:136`). Main loop.
- **Dossier synthesis against the schema** (step 7) — writing the tiered findings, consensus,
  implications-to-DoD mapping, tensions, and optional strawman while holding the
  input-not-authority boundary (`SKILL.md:138-183`). Main loop.
- **Dossier validation** (step 8) — the six-dimension adversarial check (citation integrity,
  source credibility, currency, scope discipline, governing-doc conflict surfaced-not-decided,
  answer coverage). **Delegated to an isolated `Explore` sub-agent** — see Sub-agents dispatched.
  The main loop applies findings (blockers always, suggestions by default, nits skipped) and
  controls the ≤3-pass loop itself (`SKILL.md:185-208`).
- **Governing-doc conflict handling** (steps 6, 8, dimension 5) — a finding that contradicts a
  governing doc is *surfaced as a tension for the planner/user*, never turned into a recommendation
  to override the doc (`SKILL.md:90,169,275`). Main loop authors it; the sub-agent audits it.

## Deterministic steps (candidate script work — moves to a prep/executor script)

- **Issue-number/URL parsing** (step 1) — same parsing convention as the planner
  (`SKILL.md:62,75`). Input: raw arg string. Output: `(issue_number, owner/repo)`.
- **Gather issue + thread + dossier-marker detection** (step 2) — one `github-ops`
  (`subagent_type: "github-pipeline:github-ops"`, `SKILL.md:43`) round-trip:
  `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- issue-research:v1 -->",
  scratch_dir=/tmp/gh-researcher-<N>/)` (`SKILL.md:79`). Input: issue number, repo, marker prefix,
  scratch dir. Output: issue body path, thread path, `marker_comment_present` bool,
  `marker_comment_path` (if present), `marker_comment_count`, comment `id`.
- **Manifest/doc inventory list** (step 3) — walking the repo tree for whichever dependency
  manifest and governing-doc files actually exist (no fixed checklist — `package.json` /
  `Gemfile(.lock)` / `go.mod` / `Cargo.toml` / `pyproject.toml`/`requirements.txt` / `*.csproj` /
  `pom.xml`/`build.gradle` / `composer.json` / `Package.swift` / project-generator configs, plus
  README/CONTRIBUTING/`docs/`/`CLAUDE.md`) (`SKILL.md:89-90`). Input: repo root. Output: list of
  present manifest/doc paths for the model to then read and reason over (the *reading and
  synthesizing* into a stack-context line stays judgment; the *inventory* is deterministic).
- **Stage dossier to disk** (step 9) — writing the full dossier body (marker-first) to
  `/tmp/gh-researcher-<N>/research.md` before persisting (`SKILL.md:212`). Input: dossier text.
  Output: file path.
- **Persist the comment** (step 9) — `PERSIST_COMMENT(target=issue, id=<N>, repo=<owner/repo>,
  body_path=/tmp/gh-researcher-<N>/research.md, delete_marker_id=<OLD_ID if revising>)`
  (`SKILL.md:214`). Input: staged body path, optional old comment ID to delete. Output: new comment
  URL, `body_sha256`.
- **Apply/create the `researched` label** (step 9) — `gh issue edit <N> --repo <owner/repo>
  --add-label researched`, with a one-time `gh label create researched --repo <owner/repo> --color
  1D76DB --description "Research dossier posted by github-issue-researcher"` fallback if the label
  doesn't exist (`SKILL.md:220-224`). Low-stakes: log-and-continue on failure.

Everything else in steps 4, 6, 7, and 8's fetch/synthesis/judgment work is **not** a deterministic
candidate — it's exactly the research judgment the skill exists to apply.

## Invariants (with the WHY)

- **Research is input, never authority** — the dossier reports external truth, implications, and
  tensions; it never posts an implementation plan, never declares an architecture decision
  settled, never edits code (`SKILL.md:16-18`). WHY: overstepping into plan-authority is called
  out as "the dominant failure mode of a research skill" — if the dossier decided things, the
  planner's single-decision-authority invariant (and the resolver's "the plan is the sole source
  of truth") would fracture, since two artifacts could then disagree about the design.
- **The dossier flows *through* the planner, never directly to the resolver** — the resolver
  trusts only the planner's `<!-- implementation-plan:v1 -->` comment and never reads the dossier
  itself (`SKILL.md:19`). WHY: keeps the resolver's "the plan is the single source of truth"
  invariant intact while still adding durable external grounding — a second authority for the
  resolver would create a two-source-of-truth race.
- **Every claim traces to a page fetched *this run*, with the fetch date recorded** — "the single
  most common false-positive route into a thin dossier" note aside, the operative rule is: if you
  catch yourself writing a fact you "just know," stop and go find the source, or mark the question
  "no authoritative source found" (`SKILL.md:123`). WHY: recall dressed up as research is "the one
  thing this skill must never ship" — the whole reason the skill exists is to replace stale/absent
  training-data recall with current, attributed truth; an uncited claim silently defeats that
  purpose while looking identically authoritative.
- **The marker `<!-- issue-research:v1 -->` must be the literal first line of the comment**
  (`SKILL.md:140`). WHY: any character before it makes the dossier undiscoverable to the planner's
  `startswith` lookup, and a consumer that can't find the marker behaves exactly as if no research
  exists — a silent, hard-to-diagnose data loss rather than a visible error.
- **Revise mode posts the new comment before deleting the old one** (`PERSIST_COMMENT`'s
  `delete_marker_id` parameter runs both in the persist call, new-first) (`SKILL.md:212-216`). WHY:
  staging to disk and posting via the marker-aware persist path — rather than a hand-rolled
  mktemp+delete — is "how the other skills avoid the empty-body / truncation race"; this is the
  same post-new-before-delete-old discipline the shared conventions attribute to the historical
  #626/#627 incident elsewhere in the pipeline — a crash between delete and post must never leave
  the issue with zero dossiers.
- **The decline gate is a first-class, correct outcome, not a fallback** (`SKILL.md:99,105`). WHY:
  without an explicit decline path the skill drifts toward always producing *something*, which
  manufactures noise (a thin dossier "for form's sake") the planner then has to wade through and
  which dilutes the signal value of a dossier that *does* exist.
- **The design-choice trap is guarded against as "the single most common false-positive route into
  a thin dossier," not treated as an edge case** (`SKILL.md:107`). WHY: a design question wearing research
  clothing is the single most tempting shortcut — it feels like due diligence but actually usurps
  the planner's job and produces a dossier that looks like grounding while carrying an undisclosed
  opinion.
- **Web-access unavailability is a hard stop, never a silent fallback to recall**
  (`SKILL.md:50,284`). WHY: "pretending to would defeat this skill's entire purpose" — a
  dossier synthesized from memory when fetching failed is indistinguishable in form from a real
  one, so the failure must be loud rather than silently degrading trust.
- **Never re-research untouched sections from scratch in revise mode** — refresh what changed,
  show a diff (`SKILL.md:58,276`). WHY: wasteful and noisy otherwise; a diff also lets the user
  (and the planner) see exactly what changed rather than re-reading the whole dossier for drift.
- **Governing-doc conflicts are surfaced as tensions, never resolved by picking the external
  source over the doc** (`SKILL.md:90,169,275,283`). WHY: the dossier doesn't own that decision —
  it belongs to the planner/user; unilaterally overriding a project's own governing doc from an
  external finding would make the dossier a second, uncoordinated decision-maker.
- **The dossier must never be hand-edited post-posting** — re-run the skill instead
  (`SKILL.md:177,277`). WHY: keeps the artifact attributable (its trailing authorship line is then
  trustworthy) and keeps the marker/lookup invariants intact across edits.
- **`github-ops` handles GitHub I/O only; web research (`WebSearch`/`WebFetch`/`deep-research`)
  never routes through it** (`SKILL.md:43`). WHY: `github-ops` is the judgment-free GitHub/git
  executor across the whole pipeline — routing web-fetch judgment through it would either force it
  to make research-tiering judgment calls (breaking its judgment-free contract) or force verbatim
  web content through an extra hop for no benefit.
- **A sub-agent (the validator) can never call `AskUserQuestion`; it returns a structured
  decision-needed signal instead** (`SKILL.md:37,45`). WHY: `AskUserQuestion` is unavailable inside
  `Agent`-spawned sub-agents by platform constraint; without a substitute signal a blocked
  sub-agent would either silently guess or hang, so the shared contract gives it a typed exception
  to hand back to the main loop instead.

## Sub-agents dispatched

| Sub-agent | Reference prompt file | Consumes | Returns |
|---|---|---|---|
| Research validator (`Explore`-type) | `skills/github-issue-researcher/references/research-validator-prompt.md` | Filled `<<placeholders>>`: `dossier_body`, `mode` (`broad`/`targeted`/`revise N`), `issue_number`, `repo_owner`/`repo_name`, `repo_root`, `dimensions` (subset of 1-6). Explicitly **not** the conversation history, user framing, or the orchestrator's search notes — isolation is the point (`SKILL.md:189`, `research-validator-prompt.md:3,11`). May itself re-fetch a cited URL and read the repo's governing docs/manifests. | A single deterministic Markdown block: `## Research validation summary` (issue, mode, dimensions checked, findings count by severity) + `## Findings` (each with Severity BLOCKER\|SUGGESTION\|NIT, Dimension number+name, Evidence — quote/URL/`path:section`/`comment by @author on date` — mandatory, What's wrong, Remediation), or the literal `Findings: 0` / `None.` empty form (`research-validator-prompt.md:85-120`). Cannot call `AskUserQuestion`. |

The six dimensions (verbatim names): 1 citation integrity, 2 source credibility, 3 currency, 4
scope discipline (input-not-authority), 5 governing-doc conflict surfaced-not-decided, 6 answer
coverage (`SKILL.md:191`, `research-validator-prompt.md:40-66`). Severity bar: BLOCKER = concretely
unsafe to feed a planner (must-fix before posting); SUGGESTION = would improve trust/clarity but
not unsafe; NIT = polish, never gates (`research-validator-prompt.md:68-72`). A finding with no
quotable evidence must be **dropped**, not softened (`research-validator-prompt.md:74-83`). Loop
control mirrors the planner's reviewer loop: up to 3 passes; drop evidence-less findings; exit
clean on zero findings; exit circular if a finding repeats with no progress; apply blockers always,
suggestions by default, nits never; exit at the pass cap otherwise (`SKILL.md:193-206`). This
validator prompt is explicitly the "researcher-side sibling" of
`github-issue-planner/references/plan-reviewer-prompt.md`, reusing its Severity/Evidence/Output
conventions verbatim while differing in subject (a dossier's fetched-truth-and-scope, not a plan's
executability) (`research-validator-prompt.md:5`).

## Known bugs / gaps

None identified specific to the researcher skill's own text. (The two known planner bugs recorded
per the S1 brief — an open question with an existing tracker issue wrongly filed as "(not filed)",
and the handoff's open-questions line silently dropping in combined epic+story sessions — belong
to `github-issue-planner` and are recorded as falsifiable requirements in `docs/specs/planner.md`,
per that skill's addendum; they do not originate in or apply to the researcher's own artifacts or
flow.)
