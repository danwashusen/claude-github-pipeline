# Asking the user a decision — shared reference

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
