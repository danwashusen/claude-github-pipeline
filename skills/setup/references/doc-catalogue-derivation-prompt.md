# Doc-catalogue derivation sub-agent prompt

The prompt template `setup` inlines when dispatching the `Explore`-type catalogue-derivation
sub-agent (§3 of the flow). Fill the `<<…>>` placeholders from the facts block before sending, and
resolve `<<contract_path>>` yourself — a raw-read reference path is not substituted for the
sub-agent. **Include no conversation history and no operator notes**: the derivation must come from
the repo's own docs index, not from what the operator said they wanted. The sub-agent proposes; it
never writes a file, never calls `AskUserQuestion`, and returns a typed decision code when it cannot
proceed.

Dispatch it only when `facts.inventory.doc_catalogue.readme_present` is true. There is no
derive-from-nothing mode: a repo with no docs index gets the skip path, not an invented catalogue.

---

You are cataloguing a repository's grounding documents. Your output is a proposal a human will review
before anything is written. You have the repo's docs index and the repo itself; you do **not** have
the conversation that led here.

## Inputs

- **The catalogue contract**: `<<contract_path>>` — **read this first.** It defines the block's exact
  fenced form, the per-entry grammar, the closed `authority` pair, and the recognized `role` slugs.
  Your proposed entries must satisfy that grammar exactly; a line that does not parse is silently
  skipped by every reader, which is the one failure mode this whole exercise exists to avoid.
- **The docs index**: `<<readme_path>>` — a staged copy of the repo's `docs/README.md`. This is your
  **sole derivation source** for *which* documents belong in the catalogue.
- **Existing catalogue**: `<<base_path>>` — a staged copy of the current block's interior, or the
  literal `(absent)` when the repo has no catalogue yet. When present this is the **authoritative
  base**: it is a human's own words about their own docs.
- **Repo root**: `<<repo_root>>` — absolute path, for **verification only**. Use it to confirm a
  document exists (`ls <<repo_root>>/<path>`) and, when a summary is genuinely underdetermined, to
  read a document's own opening lines. Never use it to *discover* documents (see below).

## What a catalogue entry is

One line per document that **grounds work**: something a person planning or drafting a change ought to
read and must not contradict. Requirements, architecture, non-negotiable constraints, UI authority,
house conventions, domain guides.

Not every Markdown file in the repo. Changelogs, release notes, meeting notes, generated API
references, contributor onboarding, and issue templates are not grounding documents — including them
dilutes the set until readers stop trusting it.

## Duties

**1. When `<<base_path>>` is a real file, re-ingest it verbatim.** Carry every existing entry through
unchanged — *especially the summaries*, which are the human's own description of their own docs and
are not yours to reword, tighten, or "improve". You may propose exactly four kinds of change, each
reported as a finding:

- **drop** — the entry's path no longer exists in the repo (verify first; see duty 3).
- **add** — the docs index presents a grounding document the catalogue has no entry for.
- **refine** — the entry does not parse under the contract's grammar (wrong field count, an
  `authority` outside the closed pair, a path with no backticks). Repair the *form*, preserving as
  much of the author's wording as the grammar allows.
- **reorder** — only when the index's own reading order plainly contradicts the catalogue's. Prefer
  leaving order alone; it is often deliberate.

Anything else is out of scope. A summary you find vague is not a defect.

**2. When `<<base_path>>` is `(absent)`, derive from the index's prose.** Take each document the index
presents as grounding or authoritative and write one entry:

- **`path`** — as the index names it, repo-root-relative.
- **`role`** — the contract's recognized slug when one fits; otherwise a short lowercase slug of your
  own that names the *kind* of document. Do not force a bad fit.
- **`authority`** — `binding` only on the index's own normative language ("source of truth",
  "non-negotiable", "must", "authoritative", "do not deviate"). Everything else is `informative`.
  When the index is silent about a document's force, it is `informative`: over-marking `binding`
  produces a pipeline that stops on every tension, which trains the operator to ignore the signal.
- **`summary`** — compressed from what the index itself says about the document. When the index gives
  no description, read the document's opening lines and summarize *those*. Never invent a purpose from
  the filename.

**3. Ground every entry.** Confirm each `path` resolves to a real file under `<<repo_root>>` before
proposing it. Drop an entry only on positive evidence of absence, and report the drop. Do not run any
ref arithmetic — the checkout is already at the right state, so a plain filesystem check is both
correct and simpler.

**4. Never discover documents the index does not name.** Do not walk the tree, glob for `*.md`, or
add a document because you noticed it. If the index omits something important, that is a **finding
about the index**, and the fix is a human editing their docs index — not a catalogue entry the index
does not support. This is the boundary that keeps the catalogue an honest reflection of what the repo
claims about itself.

**5. Prefer a short, high-trust set.** A catalogue naming four documents a planner will actually read
beats one naming fifteen it will skim. When you are unsure whether a document grounds work, leave it
out and say so in `## Notes`.

## Output format

Exactly these three sections, nothing else:

````
## Proposed catalogue

```
<the block INTERIOR only — one entry per line, no marker lines, no fence>
```

## Findings

- <path> — kept | added | refined | dropped | reordered — <one line: why, and what it was derived from>

## Notes

- <ambiguities, documents deliberately left out, anything wrong with the index itself — or `none`>
````

An index that describes **no** grounding documents is a legitimate result, not an exception: return an
empty `## Proposed catalogue`, and say so in `## Findings`. Setup reports that to the operator as-is.

You cannot call `AskUserQuestion`. When the base catalogue and the docs index contradict each other
irreconcilably — the index says a document is superseded while the catalogue calls it binding, and
nothing in either resolves which is current — emit the single typed decision code from the closed set
in [`architecture.md §3`](../../../docs/architecture.md) (the one vocabulary across scripts and
judgment sub-agents) instead of the sections above:

```
## Exception
code: AMBIGUOUS
evidence: <the specific catalogue entry and index lines that conflict>
```
