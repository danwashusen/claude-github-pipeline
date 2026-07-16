# New-issue draft

Route for a **new-issue** session (`vector.mode: new`, no target issue). Classify the feedback, then
draft-review-gate-file a **single** build issue (bug / incomplete feature / new feature / story).

## Step 1 — Classify the feedback

The type sets the template, the gather set, and the reviewer dimensions. Cue-match:

- **Bug** — something is broken. Cues: "X is broken," "throws an error," "Y doesn't work when Z,"
  past-tense problem reports, error messages, unexpected behavior.
- **Incomplete feature** — half-built, noticed in passing. Cues: "I never finished," "only works for X
  but not Y," "the empty state isn't handled," "TODO," "we stubbed this out."
- **New feature / enhancement** — a capability that doesn't exist yet. Cues: "users should be able to,"
  "it would be nice if," "we need a way to," "I want to add."
- **Epic** — a multi-capability initiative too big for one PR; decomposes into stories. Cues: several
  distinct capabilities in one breath, scope crossing layers, "big one," "multi-phase," "initiative," or
  "epic." Heuristic: if the acceptance criteria won't fit one shippable PR, it's likely an Epic.
- **Question** — a request for a human decision, not a unit of work. The tell: *no code follows from
  filing it* — someone has to answer first.

**Feature vs. Epic — ask, don't promote.** When Epic signals fire but scope is genuinely the user's call,
gate (`header: "Issue size"`): **One feature** / **Epic + child stories**. If genuinely ambiguous between
bug / feature / epic, ask — don't guess.

An **Epic** or **question** classification is the router's new-mode override signal (SKILL.md §2): stop
here and return to the router — it reads `epic-split.md` or `question.md` instead. State the override
reason. Everything below runs for a single build issue (bug / incomplete / feature / story).

## Step 2 — Run the spine

Read [`draft-spine.md`](draft-spine.md) and execute it end to end (gather → resolve open questions → draft
→ review → show + gate → file). The deltas this route supplies:

- **Template + title.** The classification's built-in template ([`../references/issue-templates.md`](../references/issue-templates.md))
  when the repo has none. Titles: `[Bug] <component>: <what's wrong>`, `[Incomplete] <component>: <what's
  missing>`, `<verb> <object>` (feature/story). Drop the prefix when the repo labels type.
- **Reviewer dimensions (spine review loop).** `1, 2, 3, 6` (`draft` mode). Dimension 1 carries the PRD
  contradicts/extends/gap + frozen-undecided check; dimension 3 the internal + `## Open questions`
  consistency check.
- **Filing.** One `create` with the type + priority labels and any `--blocked-by` from a filed-companion
  `in-scope (blocked)` OQ or a user-stated `Blocked by #N`.

Everything below runs only after the spine returns.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md) and match the outcome:

- **Single issue filed** (default): `Issue:` line (`plan: ✗`) + `Next: /github-pipeline:planner #<N>`;
  `Why:` names what the planner will do.
- **Single issue filed with open questions**: same shape + the `**Open questions:**` line (companion
  `question` issues + a disposition tally covering every OQ); `Why:` notes the planner plans only the
  decided scope.
