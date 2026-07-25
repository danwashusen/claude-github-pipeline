# Gather tactics — source tiering, depth escalation, fetch tactics

Read at the playbook's Step 6 ("Gather current truth"). The rule above these tactics is absolute:
**every claim that lands in the dossier comes from a page fetched *this run*, with the fetch date
recorded.** If you catch yourself writing a fact you "just know," stop and go find the source — or mark
the question "no authoritative source found." Recall dressed up as research is the one thing this skill
must never ship.

## Source credibility tiers (prefer higher; label every source with its tier)

1. **Primary / official** — the maintainer's own documentation, API reference, release notes, changelog,
   or specification for the project's actual dependency at its pinned version. The strongest evidence and
   the default target.
2. **Standards-body / academic baseline** — recognised standards organisations, specifications, and
   peer-reviewed or widely-cited literature, when the question is a cross-cutting practice rather than one
   library.
3. **Reputable secondary** — well-regarded community references, maintainer blog posts, conference talks.
   Usable for orientation and to *find* primary sources, but **flagged as secondary** and never
   authoritative on its own. Prefer to trace a secondary claim back to its primary and cite that.

Reject low-credibility sources (anonymous blogs, undated tutorials, content-farm pages, unattributed
answers). When sources disagree, say so and weight by tier and date. When a question has a dedicated
skill that owns it better than a generic search (a vendor-specific reference skill), prefer routing it
there. Record for every claim: the source URL, its tier, the **fetch date**, and (for version-specific
facts) the version it applies to.

## Hybrid depth

Run the scoped `WebSearch`/`WebFetch` loop yourself for most questions. **Escalate to the `deep-research`
skill** only for a genuinely deep or contested question — one where sources conflict, the answer is
multi-part, or adversarial cross-checking across many sources is warranted. Distil its report into
dossier findings (with the underlying primary citations); don't paste it wholesale.

## Fetch tactic — JS-rendered docs

A primary doc site can return a title-only shell when its content is rendered client-side — a
successful-looking fetch that carries no facts. If a page you expect to be rich comes back near-empty,
don't give up on the source: retry its underlying data endpoint or a server-rendered variant (many doc
sites expose a `.../data/….json` or print/raw URL alongside the HTML), or fall back to an equally-primary
companion (a release-notes page, a recorded-session transcript). Note in the source line which form you
actually read.
