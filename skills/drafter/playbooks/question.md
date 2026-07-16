# Question issue — file or revise

Route for a `question`-type issue: a new-mode session the router overrode after classifying the feedback
as a **question** (SKILL.md §2), or a `vector.mode: revise`, `vector.type: question` session revising an
existing one. A question is a request for a human decision, not a unit of work — *no code follows from
filing it*, so its handoff is **terminal** and it never enters research/plan.

## Step 1 — Draft the question

Use the `question`-issue body schema — `## Question` / `## Audience` / `## Constraints` / `## Context` /
`## References` / `## Why this matters` / `## Tracked in` — owned verbatim by
[`../../_shared/question-issue.md`](../../_shared/question-issue.md) (the single source of truth; don't
restate it). A question carries **no** Definition of done or Acceptance criteria — `## Context` +
`## References` exist to make it *answerable*, the only bar that matters. Don't invent context, options, or
a recommended answer the user didn't give. Title: `<tracker-id> — <question topic>` when a tracker id
exists, else the topic phrased as a question.

**Audience labels.** One `audience:*` label per audience named (or clearly implicated) — off the
three-label cap, priority omitted unless the question is blocking, per `../../_shared/question-issue.md`.
Flag any audience label that doesn't exist yet at the gate (`audience:business (will be created)`);
approving "File it" approves creating it.

## Step 2 — Run the spine

Read [`draft-spine.md`](draft-spine.md) and execute its review → show + gate → staged filing steps (the
Step-3.5 open-question resolution does **not** apply — a question *is* the open question). The deltas:

- **Reviewer dimensions.** `1, 3, 6` — and `2` **only** when the body cites code, APIs, or file paths
  (most business questions cite none). Dimension 3 carries the question's quality bar (answerable +
  phrased for the labeled audience); 5/7 never apply.
- **Filing.** Create each missing `audience:*` label inline (`gh label create "audience:<x>" …`) right
  before filing, then one `create` with `--label question --label audience:<x> …`.

For a `revise` on a filed question, apply the edit with `gh_persist.py edit-body` (label deltas via
`edit-labels`) after the diff-show + explicit confirmation — same terminal shape below.

## Step 3 — Paste-ready snippet, then the terminal handoff

A question exists to be referenced from wherever it was raised, so after filing print a **paste-ready
snippet** for the source doc (the skill prints it; the user pastes it — it does not edit the doc):

```
- PRD-OQ-06b: Which billing model for v1? — tracked in #210
```

Match the snippet to the doc's list style; drop the `PRD-OQ-06b:` prefix when no tracker id exists. This is
the only post-file output before the handoff.

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md): the **terminal question**
shape — `Issue:` line `#N — <title> · <state> · question` (the `research:`/`plan:` markers omitted), an
`**Audience:**` line listing the `audience:*` labels, the fenced next-action replaced with
`(terminal — no follow-up skill)`, and a `Why:` that explains it awaits a human answer and what to do once
it lands (revise the tracking doc; file any resulting work as its own issue). Nothing follows the handoff.
