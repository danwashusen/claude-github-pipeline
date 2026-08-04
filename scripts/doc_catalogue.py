"""doc_catalogue.py — the consuming repo's grounding-doc catalogue (architecture.md §2, §7;
``skills/_shared/doc-catalogue.md``). One deterministic mechanism, one home: read the
``<!-- doc-catalogue -->`` block from the consuming repo's ``docs/README.md`` and hand back the
declared documents, so no prompt and no prep asserts a doc layout of its own.

**Why this module exists.** Before it, doc grounding was a hardcoded path list in two places —
``prep_planner._GROUNDING_DOC_PATHS`` (``docs/prd.md`` / ``docs/architecture.md`` /
``docs/constitution.md`` / ``CLAUDE.md``) and ``prep_drafter``'s four
``_PRD_CANDIDATE_PATHS``/``_ARCHITECTURE_PATH``/``_CONSTITUTION_PATH``/``_CLAUDE_MD_PATH``
constants, which disagreed with each other on the PRD's spelling and with the prompts, which named
two further docs (``docs/ui-design.md``, ``docs/architecture-notes.md``) neither prep inventoried.
A path list in the plugin is an assumption about a *consuming* repo's layout — the thing the
convention-driven coupling rule (CLAUDE.md "Coupling to a consuming repo is convention-driven")
exists to forbid. Both preps now call this module; it is the ``oq_tracker.py`` promotion pattern
(one literal algorithm serving one shared contract named by two real consumers, not two
similarly-shaped local helpers).

**No fallback, no walk.** When the catalogue is absent the answer is an empty set plus the
``DOC_CATALOGUE_ABSENT`` notice — never a built-in path list, and never a filesystem search for
doc-looking files. A guessed doc layout is what the block replaces, and a silent guess is worse than
a loud gap: it grounds a plan on a document the repo never nominated. What a consumer *does* about
the gap differs by consumer (planner/drafter proceed ungrounded; a documents-derived consumer
refuses) and that asymmetry lives in the shared contract, not here.

Every function is a pure, non-emitting core (architecture.md §2's pure-core pattern, the S8 lock):
``(value, notices)`` — never prints, never exits, never raises on malformed input. A prep composes
these in-process and merges the returned notices into its own envelope. There is no CLI surface (no
shebang, no ``main()``): the only callers are prep scripts, exactly like ``refblocks.py`` and
``branching.py``.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_block  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
from pipelib.decisions import DOC_CATALOGUE_ABSENT  # noqa: E402

# The block name and its fixed home (skills/_shared/doc-catalogue.md §Home). `docs/README.md` is a
# FIXED single candidate, not a search list: the catalogue belongs beside the documents it names, and
# a repo's own docs index is a file it maintains for its own sake. This is the first caller in the
# repo to override `config_block.read_block_anywhere`'s `candidate_filenames` — the override the
# module anticipated (config_block.py's DEFAULT_CONFIG_CANDIDATE_FILES comment) — because the
# COMMANDS.md/CLAUDE.md default is deliberately wrong here.
CATALOGUE_MARKER = "doc-catalogue"
CATALOGUE_FILE = "docs/README.md"

# `authority` is a CLOSED pair (skills/_shared/doc-catalogue.md §"Entry grammar"): `binding` means a
# conflict is a blocker, `informative` means a conflict is a judgment call. An entry whose authority
# is neither is skipped rather than coerced — silently defaulting an unrecognized value either
# invents a blocker or discards one, and both are worse than a skipped line setup will flag.
AUTHORITY_BINDING = "binding"
AUTHORITY_INFORMATIVE = "informative"
AUTHORITY_VALUES = (AUTHORITY_BINDING, AUTHORITY_INFORMATIVE)

# `role` is an OPEN set — these are the slugs a reader recognizes and can route on ("which document
# says what the architecture is"); any other slug is carried through untouched and its `summary` and
# `authority` still apply in full. Exported so a prompt-facing consumer can name the recognized set
# without re-deriving it; never used to filter or reject an entry.
RECOGNIZED_ROLES = (
    "prd",
    "architecture",
    "constitution",
    "ui-design",
    "conventions",
    "guide",
)

# Entry grammar (skills/_shared/doc-catalogue.md): `- ` then a backtick-quoted path, then three
# ` — `-separated fields. The separator is the em dash with a space on each side, matching every
# other list-style block in the plugin; the split is capped at 3 so the FINAL field (the summary)
# may contain its own em dashes.
_BULLET_RE = re.compile(r"^-\s+(.*)$")
_BACKTICK_SPAN_RE = re.compile(r"`([^`]+)`")
_FIELD_SEPARATOR = " — "
_FIELD_SPLIT_MAXSPLIT = 3


def _is_safe_relative_path(raw_path):
    """Reject a catalogue path that is absolute or climbs out of the vantage with ``..``.

    The catalogue is the consuming repo's own confirmed config, so this is not a trust boundary in
    the security sense — but an entry is handed to sub-agents and read verbatim, and a path escaping
    the checkout would point a reader at a file outside the tree it is supposed to be grounding on
    (the exact failure the workspace-path discipline in architecture.md §6 exists to prevent). Such
    an entry is skipped like any other malformed line.
    """
    if not raw_path or raw_path.startswith("/") or raw_path.startswith("~"):
        return False
    if Path(raw_path).is_absolute():
        return False
    return ".." not in Path(raw_path).parts


def parse_catalogue_entries(interior_lines):
    """Pure text -> entries. ``interior_lines`` is the block interior as a list of lines (exactly
    what ``config_block.read_block_anywhere`` returns); no filesystem access happens here, so this
    is unit-testable against literal text and reusable by any future at-ref reader.

    Returns a list of ``{"path", "role", "authority", "summary"}`` dicts, in declaration order.
    A line that is blank, is not a ``- `` bullet, carries no backtick-quoted path, yields fewer than
    four fields, names an unsafe path, or whose ``authority`` is outside the closed pair is
    **skipped** — best-effort, non-raising, the posture every block scan in the plugin shares (a
    malformed block has no decision code). Skipping is why ``setup`` re-checks every line it writes:
    a skipped entry is a document that silently stops grounding anything.
    """
    entries = []
    for raw_line in interior_lines:
        bullet = _BULLET_RE.match(raw_line.strip())
        if bullet is None:
            continue
        parts = bullet.group(1).split(_FIELD_SEPARATOR, _FIELD_SPLIT_MAXSPLIT)
        if len(parts) < 4:
            continue
        span = _BACKTICK_SPAN_RE.search(parts[0])
        if span is None:
            continue
        rel_path = span.group(1).strip()
        if not _is_safe_relative_path(rel_path):
            continue
        authority = parts[2].strip().lower()
        if authority not in AUTHORITY_VALUES:
            continue
        entries.append(
            {
                "path": rel_path,
                "role": parts[1].strip().lower(),
                "authority": authority,
                "summary": parts[3].strip(),
            }
        )
    return entries


def read_catalogue(vantage_path):
    """Read the catalogue from ``vantage_path`` and resolve each entry's presence there.

    ``vantage_path`` is the checkout the documents are read at — **the same vantage as the documents
    themselves** (the planner's asserted grounding checkout at its ``plan_ref``; the drafter's
    ambient root), never a pinned ref. The catalogue is *grounding* config, not *gate* config: the
    ``origin/main`` pin in ``refblocks.py`` exists so a PR cannot weaken the gates that judge it, and
    a catalogue names no gate. Reading at the working vantage is also the coherent choice — a branch
    that adds a document *and* its catalogue entry must ground on both.

    Returns ``(entries, notices)``:

    - ``entries`` — the parsed entries, each additionally carrying ``present`` (the file exists at
      this vantage) and ``abs_path`` (absolute path when present, else ``None``). A declared-but-
      missing document is **reported, not dropped**: the caller raises it as an attention line, since
      a stale entry and legitimate branch drift look identical from here and only the operator can
      tell them apart.
    - ``notices`` — ``[DOC_CATALOGUE_ABSENT]`` when no well-formed block was found (no
      ``docs/README.md``, no block in it, or a malformed one — ``read_block_anywhere`` already treats
      malformed as absent), else ``[]``. A block that is *present but empty* is a repo explicitly
      declaring no grounding documents, which is not the same fact as no declaration at all, so it
      yields ``([], [])``; a caller wanting "nothing to read" keys off ``entries``, and one wanting
      "tell the operator to author a catalogue" keys off the notice.
    """
    present, interior_lines, _source_file = config_block.read_block_anywhere(
        vantage_path, CATALOGUE_MARKER, candidate_filenames=(CATALOGUE_FILE,)
    )
    if not present:
        return [], [DOC_CATALOGUE_ABSENT]

    entries = parse_catalogue_entries(interior_lines)
    vantage = Path(vantage_path)
    for entry in entries:
        doc_path = vantage / entry["path"]
        is_file = doc_path.is_file()
        entry["present"] = is_file
        entry["abs_path"] = str(doc_path) if is_file else None
    return entries, []


def entry_for_role(entries, role):
    """The first entry whose ``role`` matches, or ``None``.

    Role order is the repo's declaration order, so "first" is the repo's own preference when it
    declares two documents in one role (two guides, a PRD and a legacy PRD). Used by
    ``prep_drafter`` to keep its long-standing ``facts.repo_context.docs.prd`` fact stable across the
    migration off hardcoded PRD candidate paths.
    """
    for entry in entries:
        if entry.get("role") == role:
            return entry
    return None


def missing_entry_paths(entries):
    """The declared paths that do not exist at the vantage — the caller's attention-line input."""
    return [entry["path"] for entry in entries if not entry.get("present")]
