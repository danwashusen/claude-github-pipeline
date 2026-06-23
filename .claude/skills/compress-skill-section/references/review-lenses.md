# Adversarial review lenses

Spawn these four as **parallel `general-purpose` subagents** each round (step 3). They are
read-only critics — they return findings, they do not edit anything. Each lens hunts a distinct
failure mode; run all four every round.

## What every lens receives

Fill the placeholders before dispatch:

- `<ORIGINAL>` — the section's current text in the file (pre-rewrite).
- `<REWRITE>` — the candidate compressed version under review.
- `<FILE_PATH>` — the target file, so the lens can `grep`/`Read` the rest of the document.
- `<RULES_PATH>` — absolute path to `compression-rules.md`.

## Return format (every lens, every round)

```
VERDICT: clean | findings
FINDINGS:
- severity: blocker | major | minor
  evidence: "<short verbatim quote from ORIGINAL or REWRITE>"
  issue: <one line — what was lost / broken / violated>
  fix: <one line — concrete suggested change>
```

- `blocker` = precision or contract lost / document broken; must fix before shipping.
- `major` = real degradation; fix unless justified false positive.
- `minor` = style/polish; optional.

A lens that finds nothing returns `VERDICT: clean` with an empty `FINDINGS`. Reviewers should bias
toward reporting: a false positive costs one triage line; a missed regression ships silently.

---

## L1 — Precision & scope-loss

```
You are an adversarial reviewer. Read <RULES_PATH> first.

A section of an Opus instruction prompt was compressed. Your job: prove the REWRITE changed what
the model will DO, under a LITERAL reading (Opus 4.8 does not infer dropped intent).

ORIGINAL:
<ORIGINAL>

REWRITE:
<REWRITE>

Check every instruction in ORIGINAL against REWRITE:
- Did any scope qualifier vanish or weaken? ("every", "only", "before X", "on each", "first
  phase") — a dropped qualifier silently broadens or narrows behaviour.
- Did a conditional, gate, ordering, or exception get lost or merged?
- Did a rationale clause ("because…", an incident reference) disappear, removing the reason a
  future editor needs?
- Did a precise verb soften ("post only after the gate" → "post after the gate")?

Report per the return format. Quote the exact ORIGINAL phrase that lost meaning. Do not comment on
style — that is another reviewer's job.
```

## L2 — Contract-token integrity

```
You are an adversarial reviewer. Read <RULES_PATH> first ("Preserve verbatim").

Verify the REWRITE preserves every contract token from ORIGINAL verbatim — no paraphrase, no
rename, no dropped token. Contract tokens: operation names (GATHER_*, PERSIST_*, LIST_OPEN,
STATUS), subagent_type strings, the "no model override" pin, <!-- … --> marker comments,
§-anchors / §P-IDs, path & scratch-dir conventions, and the closed-set vocabularies
(open/closed, APPROVE/COMMENT, squash/merge, DoD annotation forms).

ORIGINAL:
<ORIGINAL>

REWRITE:
<REWRITE>

Method: extract the contract-token set from ORIGINAL and from REWRITE, then diff. Any token in
ORIGINAL but absent (or altered/paraphrased) in REWRITE is a blocker unless ORIGINAL was clearly
removing that capability on purpose. Also flag any NEW token the rewrite invented that no parser
defines. Report per the return format with the exact token.
```

## L3 — Whole-document coherence

```
You are an adversarial reviewer. The file at <FILE_PATH> contains a section that was compressed.

ORIGINAL section:
<ORIGINAL>

REWRITE (proposed replacement):
<REWRITE>

Read the FULL file at <FILE_PATH>. Then check the REWRITE in context:
- Does any other part of the document reference this section (by §-anchor, by "per §N", by name,
  by a term this section defines)? If the rewrite renamed/dropped that anchor or term, the
  reference now dangles — blocker. grep the file for the section's heading, its §-anchors, and any
  distinctive term it introduces.
- Does the rewrite still define everything later sections assume it defines?
- Does the surrounding prose (the paragraph before/after) still read correctly given the new
  wording — no broken transition, no duplicated-then-removed setup?
- If this is a _shared contract or sibling-mirrored section, does the rewrite stay consistent with
  what the contract requires?

Report per the return format, quoting the cross-reference or surrounding line that breaks.
```

## L4 — Rule-compliance & readability

```
You are an adversarial reviewer. Read <RULES_PATH> first.

Judge the REWRITE against the compression rules AND for genuine improvement.

ORIGINAL:
<ORIGINAL>

REWRITE:
<REWRITE>

Check:
- Banned shorthand present? (w/ , & for "and", -> for "leads to" in prose) — blocker.
- Aggressive intensifiers added or left (CRITICAL/MUST/ALL-CAPS) where a plain imperative works?
- Is it actually DENSER, or just reordered with similar token count? Estimate words before/after.
- Did compression introduce ambiguity a literal reader could misparse?
- Is structure (imperative, delimited, positive form) applied where it helps?

Report per the return format. If the rewrite is sound and rule-compliant, return VERDICT: clean.
```
