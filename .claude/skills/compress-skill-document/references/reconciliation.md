# Whole-document reconciliation

The per-chunk panels each saw only the document *as it was when that chunk ran*. Sequential
compression catches backward dependencies (earlier chunks already compressed), but not **forward**
ones — chunk 2 was finalized before chunk 8 changed. This pass reads the fully assembled document
once and catches what no single chunk could.

## Reconciler agent (read-only)

Spawn one (or, for a large file, a small parallel panel split by concern). Inputs:

- `<ORIGINAL_PATH>` — the original file.
- `<PROPOSED_PATH>` — the assembled working copy (all compressed chunks spliced in).
- `<RULES_PATH>` — `.claude/skills/compress-skill-section/references/compression-rules.md`.

Prompt:

```
You are the whole-document reconciliation reviewer. Read <RULES_PATH>, then read BOTH full files:
ORIGINAL at <ORIGINAL_PATH> and PROPOSED at <PROPOSED_PATH>. The PROPOSED file is the ORIGINAL with
many sections compressed independently. Find anything the independent compressions broke ACROSS
sections:

- Dangling cross-reference: a `§N` / "per §N" / "see <section name>" / a term defined in one section
  and used in another — that no longer resolves because the target was renamed, dropped, or its
  defining sentence was compressed away. grep PROPOSED for each cross-reference and confirm its
  target still exists.
- Lost definition: something a later section assumes an earlier section defines, now compressed out.
- Cross-section duplication: two sections that, after compression, now say the same thing — flag the
  pair (both locations) as a dedup opportunity, with which one should become the canonical statement.
- Broken transition: adjacent sections whose connective tissue no longer reads (a "this" with no
  antecedent, a setup sentence removed from one section that the next relied on).
- Contract / precision drift introduced doc-wide: a parsed token, scope qualifier, or closed-set
  term preserved within its own chunk but now inconsistent with how another section uses it.

Return structured findings (same format as the review lenses):
VERDICT: clean | findings
FINDINGS:
- severity: blocker | major | minor
  evidence: "<verbatim quote + the two locations if cross-section>"
  issue: <one line>
  fix: <one line>
```

Apply blocker/major fixes to the working copy and re-run the reconciler until a clean round (or 2
rounds). Minors are judgement.

## Document-level validators

**Calibrate against the original.** Run each validator on BOTH the ORIGINAL and the PROPOSED file and
compare — only a violation in PROPOSED that is *not* already in ORIGINAL counts. At document scale an
absolute check is all false positives: real skill docs carry pre-existing `&` labels
(`**Existing work & PRs**`) and heading conventions the naive check misflags (the resolver references
`§4.7` but its heading is `### 4.7`, not `### §4.7`). Diffing against the original's own validator
output cancels that noise and flags only what the compression *introduced*.

- **A — contract-token superset:** the PROPOSED contract-token multiset must not drop below
  ORIGINAL's (a before/after diff already). A dropped token anywhere is a blocker unless a section was
  deliberately removed.
- **B — no NEW banned shorthand:** diff `grep -nE '\bw/|[^-]-> | & '` of PROPOSED against ORIGINAL; a
  hit present only in PROPOSED is a regression. Pre-existing `&` labels, `+` joins, and `→` flow
  arrows are allowed house style and cancel out.
- **C — §-anchor integrity:** C1 = PROPOSED's anchor set vs ORIGINAL's — no anchor added (possible
  fabricated reference) or dropped (possible deleted cross-link). The absolute "referenced ⊆ defined"
  check (C2) is fragile because heading conventions vary (`### §N` vs `### N.`); run it only if it's
  already clean on the ORIGINAL, otherwise rely on C1.

All must pass before proposing. A failure that can't be fixed without losing meaning is reported, not
hidden.
