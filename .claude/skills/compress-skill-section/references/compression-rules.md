# Compression rules (the advice)

The rules a rewrite must follow. Derived from Anthropic, OpenAI, and Google prompt guidance, then
specialised to this repo's Opus instruction prompts. The principle behind all of it:

> Aim for the **smallest set of high-signal tokens that fully specifies the behaviour — not the
> shortest text.** (Anthropic: "minimal does not necessarily mean short"; echoed by OpenAI
> "prefer concise, information-dense writing" and Google "be concise yet specific".)

This is load-bearing because **Opus 4.8 follows instructions literally** at the effort levels
these skills run (`high`/`xhigh`): it will not silently generalise a scope you trimmed or re-infer
an intent you dropped. Cut low-signal prose; keep every token that carries **scope, intent, or
contract**.

## Compress — token wins with no precision cost

- **Delete filler and hedging** — "in order to", "it's worth noting that", "please", restated
  context, sign-posting that adds no constraint.
- **De-duplicate against the point-of-use copy** — an intro may lean on a fact restated at its
  `§N`, *but only when that copy is actually present* in the document. Verify before cutting.
- **Imperative + action verbs** — "Delegate X", "Read from the path" — not "you should consider
  delegating".
- **Delimited structure** — Markdown headers, labelled blocks, bullet/numbered lists where order
  or completeness matters. Endorsed by all three vendors as an aid to parsing.
- **Positive form** — state what to do, not a list of what not to do.

## Do NOT — looks like compression, costs precision

- **Word-for-symbol shorthand** — `w/`→"with", `&`→"and", `->`→"leads to" *in prose*. No vendor
  endorses it; the token saving is ~zero (these don't reliably tokenise smaller) and it reads
  ambiguously next to `gh` flags and code. Two symbols are *not* banned because they are already
  established house style here: a flow arrow inside a structured list (`Broad search → spawn
  Explore`), and `+` as a compact list-join (`PR + diff + linked issues`, `Sonnet + medium`). The
  ban targets word-substitution in running prose — `w/`, `&`-for-"and", `->`-for-"leads to".
- **Paraphrasing a contract token** — a synonym for a parsed identifier is a contract break, not a
  compression. See "Preserve verbatim" below.
- **Dropping the "why"** — a rationale clause (`#626/#627 race`, "cwd-stateful", "single source of
  truth") is high-signal: it is what stops a later editor reintroducing the bug. Compressing an
  explained invariant down to a bare command is the exact failure Anthropic warns against.
- **Collapsing a scope qualifier** — "on every dispatch", "across GATHER calls", "first phase
  only", "before any code work begins". These are the words Opus 4.8 will not re-infer.

## Preserve verbatim (the contract tokens)

If another skill or a script parses it, it is contract; the prose around it is compressible.

- **Operation names** — `GATHER_ISSUE`, `GATHER_PR`, `GATHER_EPIC`, `LIST_OPEN`, `STATUS`,
  `PERSIST_CREATE`, `PERSIST_BODY`, `PERSIST_COMMENT`.
- **`subagent_type` strings** — `github-pipeline:github-ops`.
- **The model pin** — "no `model` override" (the Sonnet pin on `github-ops` is intentional).
- **Marker comments** — `<!-- implementation-plan:v1 -->`, `<!-- issue-research:v1 -->`,
  `<!-- issue-resolver-test-target -->`, `<!-- pr-evaluator-merge-policy -->`, and every other
  `<!-- … -->` block.
- **§-anchors and §P-IDs** — `§10.6`, `§4.7`, `§P2`, etc.
- **Path / scratch-dir conventions** — `/tmp/gh-resolver-<N>/`, `.worktrees/<branch>/`,
  `epic/<N>-<slug>`.
- **Closed-set vocabularies** — the state markers in `skills/_shared/handoff-format.md` and the
  annotation forms in `skills/_shared/dod-annotations.md` (`open`/`closed`, `APPROVE`/`COMMENT`,
  `squash`/`merge`, the DoD annotation strings). Never invent a synonym.

## Phrasing

- Prefer plain imperatives over `CRITICAL` / `MUST` / ALL-CAPS — on current models the aggressive
  form over-triggers. Reserve **bold** for genuinely load-bearing invariants, not default emphasis.
- Do not add a blanket "be concise" directive to a body — the models are already terse; put the
  concision where you want it.

## Precision-critical by construction — leave intact

- Closed-set vocabulary definitions.
- Few-shot examples / worked examples and their exact formatting (Google: keep exemplars and their
  structure uniform).
- Anything a downstream parser or sibling skill consumes literally.
