# Adaptive chunking

Turn a target file into an ordered list of chunks, each a tractable unit of compression (~40–120
lines), each tagged with an action. Top-level `##` sections are **not** uniform units — in this repo
a single `## Workflow` can be 240 lines while another file has 29 sections averaging 10 — so chunk
by **size**, descending or batching as needed.

## Procedure

1. **Map the structure.** List every heading with its line range and level: H1 title, `## ` (L2),
   `### ` (L3), `#### ` (L4), plus resolver-style `§N` / `§P` anchored headings. A section's size =
   lines from its heading to the next heading of the same or higher level.

2. **Walk top-level (`##`) sections in order. For each, by size:**
   - **~15–120 lines →** one chunk.
   - **> ~120 lines →** descend: split into its `###` (then `####`/§N) subsections; each becomes a
     chunk. Recurse on any subsection still > ~120 lines. The parent heading + its lead-in prose
     (before the first subheading) is its own small chunk or batches with the first subsection.
     **If an oversized section has no subheadings to descend into** (e.g. the resolver's `## If the
     issue is an Epic`, ~130 lines of bare numbered steps), split it by internal logical breaks —
     top-level numbered/bulleted list items, or blank-line-separated paragraph groups — at ~target
     size, never bisecting a code block, table, or example.
   - **< ~15 lines →** mark **small**: batch contiguous small sections under the same parent into one
     chunk, or **skip** if trivial/structural (see below).

3. **Skip (never compress), regardless of size:**
   - YAML frontmatter and the H1 title.
   - **Precision-critical** per `compression-rules.md`: closed-set vocabulary definitions, worked
     examples / few-shot, pure-data or contract tables, and fenced code blocks. Also **output-format
     templates, dossier/report schemas, and handoff renderings** (e.g. the researcher's
     `## Questions researched … ## Sources` dossier template and the `## Handoff` blocks) — these are
     consumed structurally by downstream steps, so treat them like closed-set vocab and leave intact.
   - **Already-minimal** sections — mostly identifiers, links, short bullets, little compressible
     prose. Compressing these churns tokens for ~0 gain and risks precision.

4. **Never bisect a construct.** A chunk boundary must not split a fenced code block, a table, or a
   worked example. If a size cut would land mid-construct, extend the chunk to the construct's end.

## Thresholds are heuristics

40–120 is a guide, not a law — the user approves the plan, so err toward *showing* a borderline
section as `compress` and letting them downgrade it. Bias the skip list toward caution: when unsure
whether a section is precision-critical, mark it `skip:review` and surface it for the user to decide.

## Heading level ≠ semantic nesting

Some files place continuation `###` steps after intervening `##` sections — e.g. the resolver's
`### 5.`–`### 12.` follow `## If the issue is an Epic` / `## If the issue is a Story`. Chunk by
heading boundary and size regardless of the apparent parent; the `heading path` column is a cosmetic
label, not a structural claim. Measuring a section's span "to the next heading of the same or higher
level" still works (you descend into children anyway) — just don't trust the path to reflect meaning.

## Output — the chunk plan

A table the user approves before any compression runs:

| # | heading path | lines | size | action |
|---|---|---|---|---|
| 1 | `## Prerequisites` | 52–59 | 8 | skip:already-minimal |
| 2 | `## Procedures → ### §P1 Working in a worktree` | 64–75 | 12 | batch→3 |
| 3 | `## Workflow → ### 2. Fetch the full issue context` | 199–205 | 7 | compress |
| … | | | | |

Also report a one-line **budget estimate**: number of `compress` chunks × (draft + 4 lenses ×
rounds + fix) ≈ rough agent-call count, so the user can trim scope before approving.
