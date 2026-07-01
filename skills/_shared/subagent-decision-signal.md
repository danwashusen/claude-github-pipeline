# Sub-agent decision signal — shared reference

A judgment sub-agent (one spawned via the `Agent` tool) cannot call `AskUserQuestion` — see [`asking-the-user.md`](asking-the-user.md). When a gate, ambiguity, or blocker arises during its work, it must return a structured **decision-needed signal** to the calling skill's main loop, which renders the gate (or emits a re-route handoff) and, where applicable, re-dispatches with the answer. This file is the single source of truth for that signal's closed-set vocabulary.

## The signal

A sub-agent emits at most one decision-needed signal, as a terminal block that *replaces* its normal output:

```
## Exception
code: <one closed-set code below>
evidence: <the specific quote / comment / file:line that forces it>
```

The `code` is parsed by the main loop; `evidence` is the load-bearing carrier that lets the main loop act (render a question, or compose a re-route `Why:` line) without re-investigating.

## Closed-set codes

Use these exact tokens — no synonyms. The closed-set discipline that governs the handoff vocabulary in [`handoff-format.md`](handoff-format.md) applies here too. Each maps to exactly one main-loop action.

| Code | Origin | Main-loop action |
|---|---|---|
| `PLAN_MISSING` | main-loop-derived (from a sub-agent's `plan: absent` report) | §4.6 missing-plan gate — `AskUserQuestion` (run the planner / `proceed without a plan`). Not raised on trivial / comment-only flows where no plan is expected. |
| `THREAD_SUPERSEDED_PLAN` | state-distiller (§P6) | Confirm materiality with the user, then emit the §12 re-route handoff `re-plan #N — thread superseded the plan: <evidence>` to `github-issue-planner` (revise). Never reconcile in-session. |
| `PHASES_MALFORMED` | state-distiller (§P6) | Emit the §12 re-route handoff to `github-issue-planner` (revise), quoting the malformation (resolver §4.7). |
| `BLOCKED_ON_USER` | main-loop-derived (from a sub-agent's `Blocked on:` report) | Render the blocking question via `AskUserQuestion`; the issue can't proceed until it's answered. |
| `AMBIGUOUS` | state-distiller (§P6); `open-questions` question-status reader | Surface the conflict; fall back to the main loop re-reading the raw artifact (e.g. `thread_path`) the sub-agent couldn't resolve. |

**Sub-agent-raised vs main-loop-derived.** `THREAD_SUPERSEDED_PLAN`, `PHASES_MALFORMED`, and `AMBIGUOUS` are raised by the sub-agent as a mutually-exclusive `## Exception` block — they mean it cannot produce trustworthy normal output. `PLAN_MISSING` and `BLOCKED_ON_USER` are **not** sub-agent exceptions: the sub-agent reports a fact in its normal output (`plan: absent`, `Blocked on: …`) and the main loop maps it to the gate, because whether the fact is actionable (is the issue trivial? is the block real?) is a judgment the sub-agent deliberately doesn't make.

## Re-route codes never cross the session boundary

`THREAD_SUPERSEDED_PLAN` and `PHASES_MALFORMED` resolve to a **re-route**, not an in-session fix. The main loop emits the handoff and the user re-runs the prior skill in a fresh session — see the re-route rules in [`handoff-format.md`](handoff-format.md) and resolver §12. The main loop must not call the `Skill` tool to invoke the prior skill.
