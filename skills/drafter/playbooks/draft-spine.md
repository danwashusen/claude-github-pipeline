# Draft spine — shared across new / revise / epic-split / question

The draft-and-verify-and-file backbone every route runs: gather the missing context → resolve open
questions → draft against the template → run the adversarial review loop → show + filing gate → stage
the body and file through the single write path → hand back to the routed playbook for its handoff. Type
differences here are **facts** (which template, which reviewer dimensions, single-vs-batch filing), never
branches — the routed playbook reads this spine first, then supplies its deltas. All facts come from the
prep facts block (SKILL.md §1); all GitHub writes go through
`${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py` with a staged body path in `facts.scratch`.

## Gather missing context

Ask only what's needed — the user is mid-flow; a 10-question interrogation is worse than a slightly
thinner issue. The per-type minimum-viable set is a **fact of the classification**, not a branch:

- **Bug** — what happened, what was expected, and repro (or at least what they were doing); ask about
  environment only when it could plausibly matter.
- **Incomplete feature** — what works today, what's missing, what "done" looks like.
- **New feature** — the persona, the goal, and the underlying motivation (the "so that"); acceptance
  criteria are a stretch, not a gate.
- **Question** — the question, the audience(s), enough context to answer it cold, the grounding
  references, what the answer unblocks, and any **hard external constraints** (regulation, legal, SLA,
  platform limits) each paired with the force that fixes it (`../_shared/question-issue.md` `## Constraints`).

Never invent reproduction steps, error messages, or behavior the user didn't describe — say
`[to be filled in]` or ask.

## Resolving open questions (Step 3.5) — build issues only

Runs when the source (feedback, PRD, a design/architecture doc) carries an **unresolved open question**
(OQ) that gates the scope you're drafting. Detect and match per
[`../../_shared/open-question-detection.md`](../../_shared/open-question-detection.md) (the
`config.oq_markers` hint or the heuristic cues + the tracker de-dup search). Scope is **this issue** — only
the OQs that gate what you're drafting, not a project-wide sweep (that's `/github-pipeline:question-sweep`).

**Match first.** Before proposing to file a companion, consult the tracker de-dup search: for an OQ the
issue body already carried, `facts.open_question_candidates`; for one you spotted anew in the feedback or a
grounding doc, run `prep_drafter.py … --oq-query "<topic>"` (SKILL.md §1). Proposing a file before checking
is how you offer to duplicate a question that already exists.

Then get the user's **disposition** per OQ — one `AskUserQuestion` card (`header: "OQ <id>"`), the closed
set from [`../../_shared/open-question-links.md`](../../_shared/open-question-links.md):

- **Scope it out** *(default)* — the gated part leaves this issue's scope: a `## Out of scope` line names
  the OQ; nothing undecided lands in the DoD. No native dependency.
- **Keep in-scope (blocked)** — the gated part stays in the DoD; the build issue is set natively
  `blocked by` the companion question (which holds the resolver/evaluator until it answers — warn the user).
- **Build on a provisional default** — build now on a named provisional choice; record `default:` +
  `retires-when:` so the planner carries it as a watchpoint.

**Companion — reuse, file, or defer.** A match exists → default to **reusing** it (reach for
`AskUserQuestion` only for genuine ambiguity: **Reuse #N** / **File a new one**); a reused companion is
not re-filed — you post a lightweight `comment` on it cross-linking this build issue, and set this issue's
`blocked by` / `## Open questions` reference. No match → offer to **file** a companion now (a normal
`question` draft per `../../_shared/question-issue.md`, reusing this spine's review + gate) or **defer to
the sweep**. Either way, record the OQ at Step 4.

**Falsifiable rule.** Absorbing an untracked OQ silently is a defect. An unresolved source-doc OQ is
never absorbed into a build issue without **(i)** a tracked companion — a matched tracker issue (the
`facts.open_question_candidates` / `--oq-query` search consulted and a candidate `#N` adopted) **or** a
freshly **filed** `question` issue — **and (ii)** an explicit disposition from the closed set
(`scoped-out` / `in-scope (blocked)` / `provisional-default`). `question: (not filed)` is written **only
when** the tracker de-dup search returned no candidate, or every returned candidate was explicitly rejected
(with a reason) as not-the-same-question — a `(not filed)` written with an unconsulted or non-empty
candidate set is the bug-(a) defect. `in-scope (blocked)` additionally **requires** a companion to exist
and sets the native `blocked by` on it; if the user picks it but declines to file and none matches, fall
back to `scoped-out` or a **prose-only** blocker (`question: (not filed)`, no native block) — never emit a
`--blocked-by` with no `#N`.

## Draft against the template

Follow the repo's own issue template verbatim when one exists (`facts.repo_context.templates.present`) —
templates encode the team's expectations. Otherwise use the built-in fallbacks in
[`../references/issue-templates.md`](../references/issue-templates.md). Map the feedback to the repo's
**existing** labels (`facts.repo_context.labels`) — don't invent `bug` when the repo uses `kind/bug`, or
`priority:high` when it uses `P1`. Three labels max unless asked. Title conventions and the routed
playbook's schema sections (`## Open questions`, `## Related issues`, `## PRD impact`, the Story
`**Epic:**` backlink) are named by the routed playbook.

**PRD tension → `## PRD impact`.** When a PRD exists (`facts.repo_context.docs.prd`), ground language in
its personas/terminology and watch for tension — the feedback **contradicts** the PRD, **extends** it into
uncovered territory, or an incomplete-feature report describes a **gap** against a PRD section. On genuine
tension, add a `## PRD impact` note and gate (`header: "PRD conflict"`): **File to update PRD** / **File
the feature** / **Flag for discussion** — the user decides whether the PRD or the feedback is stale. No
tension → omit the section; don't add it just to show you read the PRD.

**Related issues → `## Related issues` + native dep.** When the user referenced other issues, read them
(`gh issue view <N> --json title,state,body,labels`) and classify the relationship, mirroring the user's
hedging (`May be resolved by #21`, `Related to #12`, `Blocked by #50`, `Duplicate of #99`,
`Expected behavior is described in #78`, `Closes #5`). **Never** use an auto-close keyword
(`closes`/`fixes`/`resolves`) unless the user explicitly said this issue resolves another. A `Blocked by
#N` line also sets a native `blocked by` (below); the prose line is the always-present fallback.

**Recording open questions.** For each Step-3.5 disposition write the `## Open questions` section per
[`../../_shared/open-question-links.md`](../../_shared/open-question-links.md) (marker
`<!-- open-question-links:v1 -->` on the first line inside the section), plus: a `## Out of scope` line
per `scoped-out` OQ naming it; the native `blocked by` per filed-companion `in-scope (blocked)` OQ; and a
`Related to #N` line in `## Related issues` for every filed companion `question: #N`. Don't fabricate OQs
the source didn't mark.

## Review loop

Before showing the draft, hand it to the isolated review sub-agent
[`../references/issue-reviewer-prompt.md`](../references/issue-reviewer-prompt.md) — it runs **without the
conversation history**, so it tests whether the issue stands on its own the way a teammate reading it cold
would. Dispatch an `Explore` sub-agent, inlining the draft (title/body/labels/priority/type), the `mode`
(`draft` / `revise <N>` / `split`), `facts.root.path` (its sole code/doc source — the current checkout,
never a ref), `facts.config.oq_markers`, the **dimension set the routed playbook names**, and (Epic) the
sibling drafts. It returns findings by dimension with mandatory evidence — findings without evidence are
dropped. Loop up to **3 passes**: drop unevidenced findings; empty findings → exit clean; a finding
repeated across two passes with no progress → **circular** exit; three passes with findings left → **cap**
exit. On a cap/circular exit, show the draft + a "Review notes" block and gate (`header: "Review loop"`):
**It's real, keep fixing** / **Override and file**. Apply blockers always, suggestions by default, nits
silently. The review loop runs for both new drafts and revisions — don't skip it.

## Show + filing gate

Present the full draft (title, labels, priority, body between `---` fences), plus any unresolved review
findings. **Before asking, stage the approved body to disk** — write the exact rendered body to
`<facts.scratch>/<name>.md`; the staged file *is* the body. Then gate (`header: "File issue?"`): **File
it** / **Keep iterating**. Treat anything other than an explicit "File it" as keep-iterating — never file
without that go-ahead. (The Epic one-shot batch is the sole exception — `epic-split.md` files autonomously
on a clean E1+E2 pass.)

## Staged filing — the single write path

File through `gh_persist.py` by passing the staged **path**, never re-inlining the body:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py create <owner/repo> "<facts.scratch>/<name>.md" \
  --title "<approved title>" --label <type> [--label <priority> …] \
  [--blocked-by <companion #N for each filed-companion in-scope-blocked OQ, plus any user-stated blocker>]
```

`create` returns the new issue URL, `#NN`, `body_bytes`, and `body_sha256` (cross-check against
`shasum -a 256 <path>` if you want a byte-for-byte close). An empty/missing staged file exits with
`EMPTY_BODY_FILE` and posts nothing — re-stage and re-run with the same path. Native deps are
**capability-gated**: on a repo/gh without the feature `create` files the issue and returns a
`DEPS_UNSUPPORTED` notice instead of failing — the prose `Blocked by #N.` / `## Open questions` /
`Related to #N` links are the always-present fallback, so keep them regardless. `scoped-out`,
`provisional-default`, and prose-only `in-scope (blocked)` OQs contribute **no** `--blocked-by` element.

Audience labels (questions) are created just before filing (`gh label create "audience:<x>" …` inline,
per `../../_shared/question-issue.md`) so `--label audience:<x>` doesn't fail on a missing label. A
label-only delta on an existing issue (revise mode) uses `gh_persist.py edit-labels <repo> <issue> --add
… --remove …`; a body edit uses `edit-body`; a post-file native-dep add/remove uses `link`. Return to the
routed playbook for its `## Handoff`.
