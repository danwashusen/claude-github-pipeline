# Comment-only

Route for `vector.comment_only == true`: no code path exists this run. Prep sets it on two signals —
the **OQ hard gate** (`open_questions_gate.blocked`, or an open native `blocked_by`) and any answer-only
classification (a question the thread resolves with an answer, triage-only relabelling, or
declined/abandoned work the distiller surfaces). This flow stages **one** comment, posts it, and emits a
terminal handoff. It does **not** read the spine and opens no PR.

All facts come from the prep facts block (SKILL.md §1); the write goes through
`${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py` with a staged body path (SKILL.md §3); the scratch dir is
`facts.scratch`.

## S1 — Determine the answer

Read the distilled state ([`../references/state-distiller-prompt.md`](../references/state-distiller-prompt.md)
dispatch, inputs = `facts.distiller_bundle` paths) to ground the comment in the thread's latest
direction.

- **OQ hard refusal** (`open_questions_gate.blocked`): the answer is a refusal-with-reason. For each
  entry in `open_questions_gate.blocking`, name the `in-scope (blocked)` open question, its `question`
  tracker `#<N>`, and that the in-scope work it gates can't be implemented until the question is
  answered. Do **not** implement the gated scope or tick any DoD bullet — an
  `<!-- open-question-links:v1 -->` `## Open questions` section is read for context only, never as
  buildable scope (per [`../../_shared/open-question-links.md`](../../_shared/open-question-links.md)).
- **Native `blocked_by`** (an open blocker on `facts.target.blocked_by`): same refusal shape, naming the
  open blocker `#<N>`.
- **Answer / triage / declined**: a plain clarifying answer, a triage note, or a "no code change
  warranted / duplicate of #<M> / declined" note, grounded in the distilled latest decision.

## S2 — Stage and post the comment

Stage the verbatim body to `<facts.scratch>/comment.md`, then post it (never assemble inline — staging
means the body never re-serializes across the prompt boundary, so compaction can't abbreviate it and the
#626/#627 empty-body race has nothing to race on):

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py comment <owner/repo> issue <issue> \
  "<facts.scratch>/comment.md"
```

## Handoff

Read [`../references/handoff-renderings.md`](../references/handoff-renderings.md) and emit the
**Terminal — non-PR resolution** shape: the `Issue:` line naming the issue's current state (no `PR:`
line — none was opened, so it is omitted), `Next: (terminal — no follow-up skill)`, and a load-bearing
`Why:` that states what was posted and why no code change was warranted. For an OQ / native-blocked
refusal, the `Why:` names the blocking question `#<N>` and that resolving it (via the
`question`-tracker path) unblocks a future resolver run. For a decline/duplicate close, name the reason.
