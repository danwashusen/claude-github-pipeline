# Validators

Objective gates run at step 6, after the adversarial loop converges. There is no build/test in
this repo, so these greps are the validator. All three must pass before you propose the rewrite.

Stage the candidate to a temp file first so you can grep it:

```bash
# write the proposed section to /tmp/css-rewrite.md (the orchestrator does this)
REWRITE=/tmp/css-rewrite.md
FILE=skills/<target>/SKILL.md   # the file the section lives in
```

## A — Contract-token superset

The set of contract tokens in the rewrite must be a **superset** of the set in the original
section: nothing parsed got dropped or renamed. Compare multisets.

```bash
TOK='<!-- [a-z0-9:-]+ -->|§P?[0-9]+(\.[0-9]+)?|GATHER_[A-Z]+|PERSIST_[A-Z]+|LIST_OPEN|STATUS|github-pipeline:[a-z-]+|apple-platform-build-tools:builder|review_action|pr-review|DECISION_NEEDED|AskUserQuestion|Explore|/tmp/gh-[a-z]+-|epic/<[A-Z]>-<slug>'

# ORIGINAL section staged to /tmp/css-original.md, REWRITE to /tmp/css-rewrite.md.
# Use -h, NOT -r: -r/-R prefixes every match with the filename, so the diff ALWAYS differs
# (it compares "css-original.md:GATHER_PR" vs "css-rewrite.md:GATHER_PR"). -hoE strips the
# filename so the diff compares only the tokens.
diff \
  <(grep -hoE "$TOK" /tmp/css-original.md | sort | uniq -c) \
  <(grep -hoE "$TOK" /tmp/css-rewrite.md  | sort | uniq -c)
```

**Pass** = no token shows a *lower* count on the rewrite side. Additions (a token used more often,
or a new one) are fine; only a decreased count is a drop — and a drop is a blocker unless you
deliberately removed that capability and noted it in the changelog. Extend `$TOK` with any
contract token specific to the section you're compressing.

## B — No banned shorthand

```bash
grep -nE '\bw/|[^-]-> | & ' /tmp/css-rewrite.md
```

**Pass** = no output, OR every hit is a legitimate flow arrow in a list / a literal code token (a
`&&` in a shell snippet, a real CLI flag) rather than word-substitution in prose. Review each hit;
do not auto-accept.

## C — §-anchor integrity

The rewrite must not introduce a dangling cross-reference (cite a `§N` that doesn't exist) nor drop
a `§`-anchor that other sections cite. Two checks — run C1 always, C2 only where it applies.

**C1 — file-agnostic (always run).** The rewrite must cite the same §-anchor set as the original
section — no anchor silently added or dropped:

```bash
diff \
  <(grep -oE '§P?[0-9]+(\.[0-9]+)?' /tmp/css-original.md | sort -u) \
  <(grep -oE '§P?[0-9]+(\.[0-9]+)?' /tmp/css-rewrite.md  | sort -u)
```

**Pass** = empty diff. A new anchor on the rewrite side may be a fabricated reference; a missing one
may have dropped a cross-link — investigate either.

**C2 — whole-file subset (only when the file numbers its step headings as `## §N`).** Where the
heading itself carries the anchor (the resolver's convention), confirm referenced ⊆ defined across
the whole file:

```bash
comm -23 \
  <(grep -oE '§P?[0-9]+(\.[0-9]+)?' "$FILE" | sort -u) \
  <(grep -nE '^#+ .*§P?[0-9]' "$FILE" | grep -oE '§P?[0-9]+(\.[0-9]+)?' | sort -u)
```

**Pass** = empty output. **Skip C2** for files that number steps as `## N.` and cross-ref them as
`§N` (e.g. `github-pr-evaluator`, `agents/*.md`) — there the "defined-in-heading" set is empty by
construction, so C2 is meaningless and C1 is the check that matters. The `§P-ID` branch is
resolver-local; elsewhere it simply matches nothing.
