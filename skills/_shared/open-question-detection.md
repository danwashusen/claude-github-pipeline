# Open-question detection + matching — shared contract

How to **find** an open question (OQ) in a project's docs and **match** it to a tracker issue. The
registry of record is the set of GitHub `question`-type issues (see [`open-question-links.md`](open-question-links.md));
docs are the *sources* that seed it. This file is the single source of truth for detection + the
de-dup/matching discipline; every consumer cites it rather than restating.

Consumers and their scope:
- **`open-questions` sweep** — project-wide: **every** OQ in the doc set is a candidate (it owns the
  registry).
- **`github-issue-drafter`** (thin) — issue-scoped: only OQs that gate the build issue being drafted.
- **`github-issue-planner`** — grounding: OQs that gate the issue being planned.

## Detection

Two paths (stack-agnostic — the marker syntax is the *repo's*, never baked in here):

- **Config block (preferred hint).** Read the consuming repo's `<!-- drafter-open-question-markers -->`
  block from `CLAUDE.md` (via `${CLAUDE_PLUGIN_ROOT}/scripts/config-block.sh read CLAUDE.md
  drafter-open-question-markers`, or a plain read). It declares this repo's register location(s), the
  inline-marker pattern, and how the register marks an entry still open. Use it to locate candidate
  OQs. The block's "still open" rule is a **detection hint, not the status authority** — an OQ's real
  resolution is the tracker's (see the tiered read in [`open-question-links.md`](open-question-links.md)),
  because a doc marker can lag a decision made in the question's thread.
- **Heuristic fallback (no block).** Scan for stack-neutral cues: `PROVISIONAL`, `TBD`, "open
  question", "to be decided", or a heading matching `open[- ]questions?`. These are illustrative
  English/markdown patterns — don't hard-code one repo's id syntax as *the* format.
- **Neither hits →** no OQ handling. An absent-config repo is unaffected.

OQs aren't centralized — they live inline in *any* doc, not one register. Detect them as a lens over
the docs actually read, not a single-file lookup. Example id shapes across stacks: a Rails/healthcare
repo's `PRD-OQ-05` (in `docs/prd.md`); a Swift repo's `OQ-12` or `DESIGN-Q-3` (in `docs/ui-design.md`
or a design note). For a large doc set, grep-prefilter for the cues above, then confirm real OQs by
reading only the candidate files.

Per detected OQ, capture: `{source doc + location, topic/text, native id (if any), inline "tracked in
#N" link (if any), gated scope}`.

## Matching (de-dup before filing)

Before proposing to file a companion `question` for an OQ, **search the tracker first** — proposing a
file before checking is how you offer to duplicate a question that already exists:

```bash
gh issue list --repo <owner/repo> --state all --label question --search "<query>"
```

`<query>` is the OQ's tracker id when it has one (`PRD-OQ-06b`), or its distinctive topic keywords
when detection was heuristic and there's no formal id (e.g. `tag case sensitivity`). When a candidate
comes back, `Read` its body to confirm it's the **same** question, not just a keyword hit. A confirmed
match is **reused** (link it), never re-filed. An ambiguous match is never auto-resolved — surface it
for confirmation.

Scope only: this file covers *finding and matching*. The `## Open questions` section schema,
dispositions, and native-`blocked by` rule live in [`open-question-links.md`](open-question-links.md);
the question-issue body contract lives in [`question-issue.md`](question-issue.md).
