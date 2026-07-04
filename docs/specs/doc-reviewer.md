# doc-reviewer — v1 functional spec (baseline)

> Source: `skills/doc-reviewer/SKILL.md` (144 lines). No `references/` directory — confirmed absent
> (`ls skills/doc-reviewer/` shows only `SKILL.md`); there is nothing to gather via a sub-agent or
> prep script for this skill.
> Captures v1 behavior as the parity baseline for [implementation.md](../implementation.md) S<cutover>.
> v1 skill name: `github-pipeline:doc-reviewer` (name appears verbatim in its own frontmatter
> `description`, `skills/doc-reviewer/SKILL.md:6`); v2 name: `doc-reviewer`.

## Overview

Reviews **one** of five bundled-guide-covered project docs (`docs/constitution.md`, `docs/prd.md`,
`docs/architecture.md`, `docs/architecture-notes.md`, `docs/ui-design.md`) against its bundled
**authoring guide**, and reports concrete, guide-cited findings to bring the doc into alignment
(`skills/doc-reviewer/SKILL.md:11-14`). Session shape: single standalone session,
explicit-invocation only (`disable-model-invocation: true`, `SKILL.md:5`), run as
`/github-pipeline:doc-reviewer <doc-path>` with an optional `--guide <type>` override for an
oddly-named doc (`SKILL.md:6`). Input: a doc path (matched by basename against the five-doc
table) and an optional guide override. Output: a single structured review report, then — only on
request — direct `Edit`-applied fixes to the doc itself (`SKILL.md:124-137`). It writes nothing to
GitHub; this is a local-file review/edit tool only. No sub-agent is dispatched anywhere in this
skill — review and any subsequent edit both run in the main loop.

## Artifacts written

This skill writes no persisted GitHub artifact (no issue, PR, or comment) — its only output
surfaces are the review report (below) and, gated on operator "yes," direct edits to the reviewed
doc file (`SKILL.md:124-137`). Per S19 of the v2 plan this apply-mode edit becomes operator-gated
staged-landing behavior (see Known bugs/gaps — v2 delta); v1 applies the edit **directly** with
`Edit`, no workspace/landing step.

| Artifact | Schema | Lives in | Trigger |
|---|---|---|---|
| Review report | Fixed structure — quoted verbatim below | Session output (not persisted) | Step 4, after Steps 1–3 complete |
| Doc edit (apply mode) | The accepted findings, applied via `Edit` in place; anchors preserved | The reviewed doc file, in the working tree | Step 5, only for findings the operator explicitly accepts, only after the report is shown |

Review report format, quoted verbatim (`SKILL.md:98-119`):

```
# Doc review — <doc path>   (guide: <guide basename>)

Verdict: <Aligned | Minor drift | Significant drift> — <one-line rationale>

## What's working
- <strength> — <guide ref>

## Findings
### 🔴 Blocker — <title>    guide: <section/heading>  ·  doc: <§ or lines>
<what's off, why it violates the guide, and the concrete fix/rewrite>

### 🟡 Should-fix — <title>    guide: <…>  ·  doc: <…>
<…>

### 🟢 Consider — <title>    guide: <…>  ·  doc: <…>
<…>

## Guide checklist
- [x] <checklist item> — <evidence it passes>
- [ ] <checklist item> — <what's missing>
```

Findings are ordered Blocker → Should-fix → Consider; a section with no findings says so rather
than being padded (`SKILL.md:121-122`).

## Artifacts read

| Artifact | Marker / location | What's extracted |
|---|---|---|
| The reviewed doc, in full | Path given by the user (matched by basename to the guide table) | The doc's complete content — Step 2 requires reading the **whole** doc, continuing past any truncation (`SKILL.md:47-50`) |
| The bundled authoring guide, in full | `${CLAUDE_PLUGIN_ROOT}/docs/guides/<basename>.md` — the guide always comes from the plugin bundle, never the consuming repo, "so a consuming repo cannot drift the rubric out from under itself" (`SKILL.md:26-30`, `SKILL.md:37-38`) | *Authoring principles*, *what belongs here vs. sibling docs*, *anti-patterns*, *authoring checklist*, *recommended shape* — all five review lenses walked in that fixed order (`SKILL.md:55-67`); the guide is read-only, **never edited** (`SKILL.md:50`) |

The guide-resolution table, quoted verbatim (`SKILL.md:24-30`):

| Doc | Bundled guide |
|---|---|
| `prd.md` | `${CLAUDE_PLUGIN_ROOT}/docs/guides/prd.md` |
| `architecture.md` | `${CLAUDE_PLUGIN_ROOT}/docs/guides/architecture.md` |
| `architecture-notes.md` | `${CLAUDE_PLUGIN_ROOT}/docs/guides/architecture-notes.md` |
| `ui-design.md` | `${CLAUDE_PLUGIN_ROOT}/docs/guides/ui-design.md` |
| `constitution.md` | `${CLAUDE_PLUGIN_ROOT}/docs/guides/constitution.md` |

## Operator gates

| Gate | Options | Effect |
|---|---|---|
| Step 1 — no basename match | Told which docs are reviewable; offered `--guide <type>` to force a guide (`SKILL.md:39-41`) | The skill does not guess a guide for an unmatched doc — it stops and asks the user to disambiguate |
| Step 1 — no path given | Asked which of the five docs to review, or shown the ones present under `docs/` (`SKILL.md:42`) | Blocks until a doc is named |
| Step 5 — apply the edits | Yes / no, after the report is shown (`SKILL.md:124-126`) | "Yes" applies only the **accepted** findings via `Edit`; "no" ends the session with the report standing on its own (`SKILL.md:137`) |
| Step 5 — moving content to a sibling doc | Separate offer, not assumed | Removing misplaced content from the reviewed doc is in scope on "yes"; **writing** it into the sibling doc is offered separately, never assumed (`SKILL.md:132-133`) |

## Judgment steps (model reasoning — stays in the prompt)

- **Basename matching + guide resolution** (Step 1) — matches the doc path's basename against the
  five-doc table regardless of where it sits in the repo (`SKILL.md:22-36`). Main-loop reasoning.
- **Five-lens review walk** (Step 3) — walks *authoring principles*, *what belongs here vs. sibling
  docs*, *anti-patterns*, *authoring checklist*, *recommended shape*, in that fixed order, grounding
  every finding in the guide text (`SKILL.md:52-67`). Main-loop reasoning; no sub-agent.
- **Severity calibration** (Step 3) — assigns 🔴 Blocker / 🟡 Should-fix / 🟢 Consider per the
  guide's own stakes, not the model's taste, with worked criteria for what counts as each for a
  concrete example (a miscategorized rule, an uncheckable rule, dangling `§N` renumbering as
  Blocker-tier for the constitution guide specifically) (`SKILL.md:82-91`). Main-loop reasoning.
- **Three honesty rules applied throughout the review** (Step 3) — only reviewing against what the
  guide actually says (no imported generic opinions), treating a guide's worked example as
  illustration-not-template (never faulting a doc for using a different stack or not resembling the
  sample), and crediting what the doc does right (`SKILL.md:69-80`). Main-loop reasoning.
- **Report composition** (Step 4) — assembles the fixed-shape report, ordering findings by severity
  and stating explicitly when a section has none rather than padding (`SKILL.md:93-122`).
  Main-loop reasoning.
- **Applying accepted edits** (Step 5) — applies only accepted findings via `Edit`, preserves stable
  `§N` anchors, re-checks that the edit didn't introduce a *new* anti-pattern (e.g. trimming a rule
  into something uncheckable) (`SKILL.md:124-136`). Main-loop reasoning; no sub-agent.

## Deterministic steps (candidate script work — moves to a prep/executor script)

- **Basename-to-guide table lookup** — a fixed five-row mapping from doc basename to
  `${CLAUDE_PLUGIN_ROOT}/docs/guides/<basename>.md` (`SKILL.md:24-30`). Input: doc path. Output:
  resolved guide path or no-match.
- **Doc-existence check** — confirm the named doc file exists before proceeding; if missing, say so
  and stop (`SKILL.md:43`). Input: doc path. Output: exists/missing boolean.
- **Full-file reads of the doc and the guide** — mechanical file reads (with a continuation loop if
  the guide's initial read truncates before its *Authoring checklist*/*Anti-patterns* sections)
  (`SKILL.md:47-50`). Input: two file paths. Output: complete text of each.

This is the shortest deterministic-candidate list of the three specs in this file, and the S1
addendum for this skill explicitly notes there is "no prep script (nothing to gather)"
(`skills/doc-reviewer/SKILL.md` has no `github-ops` dispatch, no `gh` invocation anywhere in the
144-line source — confirmed by inspection: no `GATHER_`/`PERSIST_`/`gh ` token appears in the
file). The table above is genuinely all there is; everything else is judgment.

## Invariants (with the WHY)

- **Reports first, applies only on request.** Explicit lead invariant (`SKILL.md:16-19`). WHY: "a
  doc like the constitution is loaded into context on every pipeline run, and bad edits are
  expensive" — the review must be shown before anything touches the file.
- **The guide always comes from the plugin bundle, never the consuming repo.**
  (`SKILL.md:27-30`). WHY: "so a consuming repo cannot drift the rubric out from under itself" —
  if the guide could live in the consuming repo, a repo could edit its own rubric to always pass.
- **Only review against what the guide says; a guide's silence is not a finding.**
  (`SKILL.md:71-73`). WHY: keeps the review grounded in a citable standard rather than the model's
  generic doc-writing taste, so every finding is independently re-derivable from guide text.
- **The worked example is an illustration, not a template.** (`SKILL.md:74-77`). WHY: guides
  include a full worked sample (often Rails); faulting a Swift or Python doc for "not looking like
  the Rails example" is a **false positive** — conformance is to the *principles*, not the sample's
  surface form. This directly serves the plugin-wide stack-agnostic requirement.
- **Credit what's right, not just what's wrong.** (`SKILL.md:78-80`). WHY: "the output is an
  editor's review, not a lint dump" — telling the user what's already correct also tells them what
  *not* to touch.
- **Severity is calibrated to the guide's own stakes, not the model's taste.**
  (`SKILL.md:82-83`). WHY: keeps Blocker-tier findings reserved for genuinely load-bearing
  violations (the constitution examples given: a deviable default mis-stated as inviolable law, an
  uncheckable rule, or a renumbering that dangles existing `§N` citations already posted elsewhere)
  rather than inflating minor nits.
- **Stable `§N` anchors are never renumbered, even during apply.** (`SKILL.md:129-131`). WHY:
  "renumbering dangles citations already posted in plans and reviews; it is itself a guide
  anti-pattern" — the same anchor-stability discipline the rest of the plugin depends on for
  cross-references.
- **Moving content to a sibling doc is never assumed on the reviewed doc's own apply gate.**
  (`SKILL.md:132-133`). WHY: removing misplaced content from *this* doc and writing it into the
  sibling doc are two separate actions with two separate consequences — bundling them would let an
  "apply the fix" yes silently create content the operator didn't explicitly approve.
- **Re-check after apply for newly introduced anti-patterns.** (`SKILL.md:134-135`). WHY: names a
  concrete regression risk — "trimming a rule into something uncheckable" — i.e., the edit itself
  can violate the very guide it was meant to satisfy.
- **A finding must trace to a principle, anti-pattern, or checklist item — never to "this isn't
  how the example does it."** (`SKILL.md:139-144`, restating `SKILL.md:74-77` as the closing
  stack-agnostic guardrail). WHY: the doc under review may target any stack; this is the mechanism
  that keeps the review itself stack-neutral even though the guides' worked examples are not.

## Sub-agents dispatched

None. This skill dispatches no sub-agent anywhere in its flow — detection, review, and apply are
all main-loop work (confirmed: no `Agent(subagent_type: …)` invocation appears in
`skills/doc-reviewer/SKILL.md`).

## Known bugs / gaps

- **v2 delta, not a v1 bug:** v1's apply step (Step 5) edits the doc **directly** in the working
  tree via `Edit` with no workspace or landing gate (`SKILL.md:124-137` contains no `git`/worktree/
  branch step). The v2 architecture's S19 changes this to a **staged, operator-gated landing** (per
  `docs/prd.md §8.2`: tracked-file edits from a standalone tool are staged in a workspace and the
  commit+push+PR landing is offered as one explicit final gate, on decline performing no git
  actions). This spec records it as a known **behavior delta to design for**, not a v1 defect —
  v1's direct-edit behavior is faithfully what the skill does today; the parity target for v2 is
  the S19-gated version, not a literal replay of the direct edit.
