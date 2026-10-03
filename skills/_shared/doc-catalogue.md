# Doc catalogue — shared reference

The consuming repo's **`<!-- doc-catalogue -->` block**: the external contract
([prd.md §7](../../docs/prd.md) "Config marker blocks") by which a repo declares **which documents
ground pipeline work and how much authority each carries**. A repo names its own docs; the plugin
never assumes a doc layout.

**Scope of this file.** The block's home, its format and per-field semantics, and what an absent
catalogue means to each reader. The *read mechanics* — candidate discovery, the best-effort line
scan, the `DOC_CATALOGUE_ABSENT` notice — belong to `scripts/doc_catalogue.py`; the *authoring* flow
belongs to `skills/setup/references/block-authoring.md`. This file does not restate either.

## Home

The block lives in the consuming repo's **`docs/README.md`**, always — the fixed-home rule
`claude-code-stack-profile` also has (it always lives in `CLAUDE.md`). Two reasons it is `docs/README.md`
and not a plugin-owned file: a catalogue of documents belongs beside the documents, where a human
maintaining the docs will see it drift; and `docs/README.md` is a file a repo maintains for its own
sake, so the catalogue rides along on upkeep that already happens. A plugin-only file rots unread.

## The block a consuming repo declares

```markdown
<!-- doc-catalogue -->
- `<path>` — <role> — <binding | informative> — <one-line summary>
<!-- /doc-catalogue -->
```

One Markdown list item per document or document set, in the repo's own preferred reading order. The
shape rhymes with the command-list blocks (`issue-resolver-fast-checks`, `worktree-setup`) —
backtick-quoted value, then ` — `, then fields — but carries three fields instead of one description.

## Entry grammar

Each entry is **one line**; a reader strips the leading `- ` and splits the remainder on ` — `
(space, em dash, space) into **at most four** parts:

| Field | Form | Meaning |
| --- | --- | --- |
| `path` | the line's first backtick-quoted span, repo-root-relative | the document, or a directory naming a document set |
| `role` | short lowercase slug | what kind of document this is |
| `authority` | `binding` or `informative` — the closed pair | how a reader must treat a conflict |
| `summary` | free text, one line | what is in it, so a reader can judge relevance unopened |

**`authority` is the load-bearing field.** `binding` means a session must not contradict the
document: a conflict is a **blocker**, raised rather than designed around. `informative` means
context — read it, cite it, but a tension with it is a judgment call, not a stop. A repo that marks
everything `binding` gets a pipeline that stops constantly; one that marks nothing `binding` gets no
safeguards at all. Choose per document.

**`role` is an open set** — a reader recognizes `prd`, `architecture`, `constitution`, `ui-design`,
`conventions`, `guide`, and treats any other slug as an unrecognized kind whose `summary` and
`authority` still apply in full. Roles are a routing hint for the reader ("which doc answers *what*
the architecture is"), never a gate: no reader refuses to work because a role it wanted is missing.

Splitting on **at most** four parts is what lets a summary contain its own em dashes. A line that
yields fewer than four parts, or an `authority` outside the closed pair, is **skipped** by readers
(best-effort, the posture every block scan in the plugin shares) — which is why `setup` re-checks
every line it writes: a silently skipped entry is a document that silently stops grounding anything.

## Directory entries

A `path` naming a directory declares a **document set**: the documents directly inside it, all under
the one `role`, `authority`, and `summary` the line carries — an architecture hub's spokes, a folder of
per-feature specs. Write it with a trailing `/` so a human reads it as a set; readers resolve file
versus directory from the checkout, not from the spelling. The set is **one level**: a nested
directory that grounds work is declared as its own entry. When members need different authority,
declare them one per line instead.

A reader treats the set as the documents it lists — the read mechanics report them as the entry's
members — reads the ones the work at hand touches, and **cites the member file**, never the directory.
Listing a directory the repo declared is not the walk the absent-catalogue rule forbids: the repo
nominated it, and nothing outside it is searched.

## Handing the catalogue to a sub-agent

A context-blind sub-agent that checks work against the docs (the plan reviewer, the resolver's fitness
audit, the drafter's issue reviewer, the question-resolver's constraint audit) receives the entries as a
`<<catalogue_entries>>` placeholder, filled from the prep's `grounding_docs` fact: one line per entry as
`<path> — <role> — <binding|informative> — <summary>`, a directory entry's `members` following it as
indented `- <path>` lines, and an entry whose `present` is false **omitted** (prep already raised it as
attention; a sub-agent handed a dead path would report the absence as a finding about the work). An empty
placeholder means the repo declares no grounding docs, and the sub-agent says so rather than inventing a
path. Each prompt restates this shape at its input, because the sub-agent never reads this file.

## Ownership — user-owned

The catalogue is **user-owned**, the `claude-code-stack-profile` posture: `setup` seeds it when
absent, and on re-run **re-ingests the existing interior as the authoritative base**, proposing only
refinements (a path that no longer exists, a document the index names that the catalogue lacks, a
line that does not parse). It never rewords a summary a human wrote. Hand-edits are expected; the
only ask is that the `<!-- … -->` marker pair stays intact.

It differs from the stack profile in one way: this block **is machine-parsed**, so entries must hold
the one-line grammar above. `setup` is the sole writer; the planner, drafter, slicer,
requirements-gatherer, resolver, evaluator, and question-resolver preps are the readers.

## When the catalogue is absent

An absent `docs/README.md`, an absent block, or a malformed one (duplicate or unterminated markers —
treated exactly like absent) all mean the same thing: **there is no declared grounding set.** No
reader walks the filesystem hunting for documents, and no reader falls back to a built-in list of
paths — a guessed doc layout is what this block exists to remove. Readers emit the
`DOC_CATALOGUE_ABSENT` notice so the gap is loud rather than silent, and the consequence differs by
consumer:

- **Planner, drafter, resolver, evaluator, question-resolver** — proceed **ungrounded**, exactly as
  they did when a hardcoded path happened not to exist. The absence is recorded, not fatal. Each of
  these judges work whose substance comes from somewhere else — an issue, a diff, an operator's
  decision — and uses the docs to check it; the question-resolver's constraint audit falls back to the
  docs the question itself cites.
- **A consumer whose whole output is derived from documents** — refuse, and say what would fix it.
  Decomposing or specifying against nothing invents scope, and invented scope becomes real issues.

That asymmetry is deliberate: one identical fact, two correct responses. Do not "fix" a refusing
consumer to match a proceeding one.

## Where the catalogue is read from

The catalogue is read from **the same vantage as the documents it names** — the planner's asserted
grounding checkout at its `plan_ref`; the resolver's audit view (its audit read workspace, else its
work worktree — reported as `grounding_path`); the evaluator's PR-head worktree, so a PR that edits a
doc or its entry is judged against its own copy; the drafter's, slicer's, requirements-gatherer's, and
question-resolver's ambient checkout. A branch that adds a document
*and* its catalogue entry must ground on both, and a branch that has not yet merged its entry must
not. (Through v3 this was a deliberate exception: gate config was pinned to `origin/main` so a PR
could not weaken the gates judging it, and the catalogue was called out as *grounding* config that
names no gate. That pin is retired — every config family now reads at the working vantage
([architecture.md §6](../../docs/architecture.md)) — so this is the ordinary rule, not an exception.)
