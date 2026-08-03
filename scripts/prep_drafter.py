#!/usr/bin/env python3
"""prep_drafter.py — the drafter's complete facts block in one call (architecture.md §4;
docs/implementation.md S14; docs/specs/drafter.md). Assembles the session's entire starting
state — the three-way vector (new / revise / epic-revise), repo-context inventory (issue
templates, labels, grounding-doc presence), the `<!-- drafter-open-question-markers -->` config
block (or the heuristic-cue fallback signal), revise-mode facts (plan-marker presence, open-PR
list, closed-by-PR/project references), epic-revise facts (`## Stories` entries reconciled against
live state), and the search-before-file open-question tracker de-dup — as ONE JSON envelope on
stdout, so the drafter session's startup is one Python process, never a subprocess chain.

Composition (architecture.md §2 "compose the executors in-process"; §1 "the only external
processes any script may spawn are git/gh")::

    gh_gather.run(..., stream=)                    -- the target issue's body/thread/plan-marker/
                                                       native-deps/open-PR envelope (one round-trip);
                                                       revise/epic-revise modes ONLY — `new` mode has
                                                       no target issue yet, so this call is skipped
                                                       entirely
    config_block.read_block_anywhere                -- the OQ-marker config block
                                                       (`<!-- drafter-open-question-markers -->`)
    oq_tracker.build_open_question_candidates        -- the target issue body's `## Open questions`
                                                       section, search-before-file de-dup (S14
                                                       promotion of prep_planner's Bug (a) mechanism —
                                                       see that module's docstring)
    oq_tracker.build_oq_query                        -- the one-shot `--oq-query` lookup `new` mode
                                                       uses for an OQ the operator names from the
                                                       feedback/doc text itself (no issue body to scan)

Every executor composed here exposes a **pure, non-emitting core** — ``build_*(...) -> (payload,
notices, decision|None)`` (docs/specs/baseline.md §5, the S8 pattern lock). This prep calls those
cores **directly** and forwards each core's returned ``decision`` verbatim (:func:`_forward_decision`),
emitting exactly one envelope of its own. No ``redirect_stdout``/``io.StringIO`` capture of another
script's stdout is used anywhere in this module (S9-on rule; docs/specs/baseline.md §5).

``git rev-parse HEAD`` (root's own SHA, informational only) and ``gh label list`` / ``gh issue
view <NN> --json state,title,labels`` (per-story live-state fetch, mirroring `prep_planner.py`'s
identical `GATHER_EPIC`-reconciliation precedent) have no existing executor core — architecture.md
§1 permits any script to spawn `git`/`gh` directly via `pipelib.process.run`, the same precedent
`prep_planner.py`/`prep_resolver.py`/`prep_evaluator.py` already established for their own
prep-owned direct calls.

Usage::

    prep_drafter.py <owner/repo> [--issue N] [--root PATH] [--scratch-dir PATH] [--cwd PATH]
    prep_drafter.py <owner/repo> --oq-query "<topic>" [--oq-query "<topic>" ...]

``--root`` defaults to ``.`` (the project root — architecture.md §6's read-only trust vantage).
``--issue`` selects revise mode (a standalone/story/question target) or epic-revise mode (an Epic
target) — mechanically, from the target's own labels/title, never from operator intent; omitting it
selects new mode. ``--scratch-dir`` defaults to ``/tmp/gh-drafter-<issue-or-"new">`` (CLAUDE.md's
``/tmp/gh-<skill>-<N>/`` convention) when omitted — this IS "staging conventions" from this step's
Work list: prep establishes and creates the directory every staged draft/revised body gets written
under at flow time (docs/specs/drafter.md "Artifacts written"); prep itself stages nothing, since no draft exists
yet at session start. ``--oq-query`` mirrors `prep_planner.py`'s identical one-shot flag (see
`oq_tracker.build_oq_query`'s docstring) and, when given, short-circuits to that one-shot payload —
no full facts assembly, matching planner's own CLI contract.

No ``--refresh`` flag: unlike the planner/resolver/evaluator, this prep runs no root-freshness
protocol and ensures no read/work workspace (see the "No workspace" paragraph below) — every fact
this script derives is already re-derived fresh on every invocation, so there is no expensive
one-time setup step for a `--refresh` flag to skip; adding one would be dead surface with no
distinguishable behavior.

**No workspace — the drafter grounds on the CURRENT checkout, not a pinned ref (docs/specs/drafter.md
"Repo context probe").** v1 drafts from wherever the operator's working tree
happens to be — `ls .github/ISSUE_TEMPLATE/`, `gh label list`, `ls docs/prd.md ...` all run inline,
with no requirement that the tree be clean or on `main` (the skill's own primary trigger is "the user
is mid-development ... notices things," i.e. very plausibly *while* the tree is dirty on a feature
branch). Unlike the resolver/evaluator (whose gate config — test-target/checks/merge-policy — would weaken
a real merge gate if read from an untrusted ref, which is why their preps read those blocks from
the `origin/main` pin via `refblocks`, never any working tree), the drafter's OQ-marker block only
informs a **detection hint** for drafting, never a merge/build gate — so reading the ambient
checkout "as-is" carries no gate-weakening exposure, and asserting or pinning anything here would
make this prep fail on the exact mid-feature-branch working tree its most common real trigger
describes. `root` therefore carries only `{path, sha}` (a plain,
non-gating `git rev-parse HEAD` — informational, never enforced) — no `workspace.py` import, no
`fresh` key (there is no freshness protocol here for that key to describe). Flagged for reviewer
scrutiny in the implementor report; not a defect if the reviewer weighs the threat model the same way.

Exit codes (architecture.md §3): 0 with the facts-block envelope present (``status`` is ``"ok"``
or ``"needs_decision"``); 2 on a usage error (no envelope). Any other non-zero is an unclassified
hard `gh`/`git` failure surfaced by a composed executor — stderr carries the faithful error.

**``vector.mode`` — the THREE-value closed set ``"new"`` / ``"revise"`` / ``"epic-revise"``**
(docs/implementation.md S14 DoD's own wording). Derived purely mechanically, never from operator
intent the script can't see:

  - no ``--issue`` -> ``"new"`` (``vector.type`` is ``None`` — Step 1's bug/incomplete/feature/
    epic/question classification is judgment over freeform feedback text; a script has no target
    issue to inspect yet, so it cannot and does not predict it — architecture.md §5: the router
    overrides `suggested_playbook` post-classification "on evidence the script cannot see").
  - ``--issue`` given, target's type (labels/title, same deterministic rule docs/specs/resolver.md
    names) is ``"epic"`` -> ``"epic-revise"`` (docs/specs/drafter.md's "Special case — revising an
    Epic" rows:
    reconcile `## Stories` against live per-story state, re-run ordering/sizing).
  - ``--issue`` given, any other type (``"standard"`` / ``"story"`` / ``"question"``) -> ``"revise"``
    (docs/specs/drafter.md's core revise-mode rows; a Story revise additionally verifies its Epic backlink line
    at flow time — Steps R1-R6 apply uniformly regardless of sub-type, so this prep does not fork a
    fourth mode for it).

**``suggested_playbook``** (architecture.md §5 "Prep proposes; the router confirms") maps onto the
four S15 playbook names (`docs/implementation.md` S15's Work list: `new` / `revise` / `epic-split` /
`question`) — mirroring `prep_planner.py`'s identical `_suggested_playbook` precedent:

  - ``mode == "new"`` -> ``"new.md"`` (the router may override to ``question.md``/``epic-split.md``
    post-classification — evidence this script cannot see ahead of reading the feedback text).
  - ``mode == "epic-revise"`` -> ``"epic-split.md"`` (the one epic playbook, shared by fresh-epic
    filing and epic-revise, the same way `prep_planner.py`'s ``story-jit.md`` "owns BOTH the fresh
    and the revise path").
  - ``mode == "revise"``, ``vector.type == "question"`` -> ``"question.md"``.
  - ``mode == "revise"``, any other type -> ``"revise.md"``.

**The shared question-tracker search-before-file mechanism (S14 promotion; see `oq_tracker.py`'s own
module docstring for the full rationale).** `prep_planner.py`'s `_search_question_tracker` /
`_build_open_question_candidates` / `build_oq_query` — authored for S12/S13 as that module's own
local helpers — are now `oq_tracker.py`, a new single-purpose module, because this step needs the
byte-identical mechanism for its own search-before-file companion-question de-dup
(docs/specs/drafter.md Step 3.5/R4). `prep_planner.py` was refactored to call `oq_tracker`
in-process instead of carrying its own copy; its own test suite (`tests/test_prep_planner.py`) is
unmodified and green (verified). This module composes `oq_tracker.build_open_question_candidates`
(revise/epic-revise modes — the target issue body IS the source to scan) and `oq_tracker.build_oq_query`
(new mode's ``--oq-query`` one-shot — there is no issue body yet, so the operator names the topic
directly, mirroring `prep_planner.py`'s identical additive extension for a plan-time-detected OQ).

**Repo-context inventory (docs/specs/drafter.md "Repo context probe").** Issue templates
(`.github/ISSUE_TEMPLATE/*` — a plain filesystem listing at `root`, no `git`/`gh` call needed, since
`root` IS the drafter's grounding vantage per the "No workspace" note above), `gh label list` (repo
labels, live GitHub state, independent of `root`'s own git state), and grounding-doc presence: PRD
specifically checks the FOUR v1-documented candidate paths (`docs/prd.md` / `docs/PRD.md` / `PRD.md`
/ `prd.md` — docs/specs/drafter.md "Repo context probe"), first match wins; `docs/architecture.md` / `docs/constitution.md` /
`CLAUDE.md` each check their own single canonical path (CLAUDE.md's "Optional grounding docs read if
present" convention, matching `prep_planner.py`'s `_GROUNDING_DOC_PATHS`).

**Referenced-issue lookup, epic-backlink-open check: deliberately out of scope for this step.**
docs/specs/drafter.md's "Deterministic steps" table also names a referenced-issue lookup (`gh issue
view <N> --json title,state,body,labels`, for issue numbers the OPERATOR'S FEEDBACK TEXT names) and
docs/specs/drafter.md's "Epic closed (revising a Story)" gate — the epic-backlink-open check. Both depend on text the model
reads (the feedback, or the target's own body) that prep cannot see ahead of a session starting — the
router/playbook reads that text directly and, per architecture.md §1's "any script may spawn git/gh
directly," calls `gh issue view` itself at flow time for either case; this step's Build list (per the
implementor brief) does not name either as a facts-block field, so no dedicated one-shot CLI mode is
added here for them (unlike `--oq-query`, which the brief DOES name explicitly). Recorded here, not
silently dropped.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_block  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
import gh_gather  # noqa: E402
import oq_tracker  # noqa: E402
from pipelib import process  # noqa: E402
from pipelib.decisions import AUTH_REQUIRED, needs_decision  # noqa: E402
from pipelib.envelope import EXIT_OK, emit_needs_decision, emit_ok  # noqa: E402

# The implementation-plan marker (skills/planner/references/plan-schema.md;
# docs/specs/drafter.md "Artifacts read" (plan-comment row) — revise mode fetches it to ground the
# revise against the planner's own approach, and to know whether Step R6's staleness flag applies).
# Same constant as `prep_planner.py`'s `PLAN_MARKER` — restated locally per this codebase's
# "no prep-to-prep imports" design convention (see `prep_planner.py`'s module docstring).
PLAN_MARKER = "<!-- implementation-plan:v1 -->"

# The OQ-marker config block name (skills/_shared/open-question-detection.md; docs/specs/drafter.md
# "OQ marker config read") — read
# via `config_block.read_block_anywhere` from CLAUDE.md/COMMANDS.md (its default candidate set
# already includes CLAUDE.md, the block's documented home).
OQ_MARKER_CONFIG_BLOCK = "drafter-open-question-markers"

# Revise-mode's extra `--json` fields (docs/specs/drafter.md "Artifacts read", closed-by-PR row):
# surfaced before editing so the operator can
# coordinate around an in-flight PR or a project-board placement, per docs/specs/drafter.md
# "Artifacts read"'s "Closed-by-PR / project references" row.
REVISE_EXTRA_JSON = "closedByPullRequestsReferences,projectItems"

# State-vector `type` detection (docs/specs/resolver.md's identical epic/story rule, restated here
# per the "no prep-to-prep imports" convention `prep_planner.py`'s module docstring names) PLUS a
# `question` branch `prep_planner.py` doesn't need (the planner never targets a question issue) —
# the drafter's revise-mode type space is `standard` / `story` / `epic` / `question`, all four
# label/title-derivable without any judgment call.
_EPIC_TITLE_PREFIX_RE = re.compile(r"^\s*epic\s*:", re.IGNORECASE)

# PRD candidate paths (docs/specs/drafter.md "Repo context probe"'s exact list) — first match wins.
_PRD_CANDIDATE_PATHS = ("docs/prd.md", "docs/PRD.md", "PRD.md", "prd.md")
_ARCHITECTURE_PATH = "docs/architecture.md"
_CONSTITUTION_PATH = "docs/constitution.md"
_CLAUDE_MD_PATH = "CLAUDE.md"

# `## Stories` bullet grammar (skills/drafter/references/issue-templates.md;
# docs/specs/drafter.md "Artifacts written", Epic `## Stories` row) — byte-identical regexes to
# `prep_planner.py`'s (restated locally; see the
# module docstring's "no prep-to-prep imports" note).
_STORY_FILED_RE = re.compile(r"^-\s*\[( |x|X)\]\s*#(\d+)\s*(?:—|-)\s*(.+)$")
_STORY_PLAIN_RE = re.compile(r"^-\s*\[( |x|X)\]\s*(.+)$")
_SECTION_HEADING_RE = re.compile(r"^##(?!#)")


# ---------------------------------------------------------------------------
# _DiscardStream / _forward_decision — identical pattern to prep_planner.py / prep_resolver.py /
# prep_evaluator.py (S8 retro §5's accepted-reference emit-through-a-stream shape).
# ---------------------------------------------------------------------------


class _DiscardStream:
    """A minimal write-sink for `gh_gather.run(stream=...)` — see `prep_evaluator._DiscardStream`
    for the full rationale (restated locally per that module's own note: sharing a two-method sink
    across prep modules is not the in-process composition architecture.md §2 asks for)."""

    def write(self, _data):
        return None

    def flush(self):
        return None


def _forward_decision(decision, notices=None):
    """Emit a composed core's returned `decision` AS-IS on prep's own stdout and return `True` when
    a decision was present. Mirrors `prep_planner._forward_decision` / `prep_resolver._forward_decision`
    exactly."""
    if decision is not None:
        emit_needs_decision(decision, notices=notices)
        return True
    return False


# ---------------------------------------------------------------------------
# State-vector type detection (docs/specs/drafter.md "Overview" + the two "Special case" rows).
# ---------------------------------------------------------------------------


def _detect_type(labels, title):
    lowered_labels = {(label or "").strip().lower() for label in labels or []}
    if "epic" in lowered_labels or _EPIC_TITLE_PREFIX_RE.match(title or ""):
        return "epic"
    if "story" in lowered_labels:
        return "story"
    if "question" in lowered_labels:
        return "question"
    return "standard"


def _suggested_playbook(mode, issue_type):
    """Map `(mode, issue_type)` to the suggested S15 playbook filename (see module docstring's
    `suggested_playbook` paragraph for the full rationale)."""
    if mode == "new":
        return "new.md"
    if mode == "epic-revise":
        return "epic-split.md"
    if issue_type == "question":
        return "question.md"
    return "revise.md"


# ---------------------------------------------------------------------------
# git rev-parse HEAD — root's own SHA (informational only; see module docstring's "No workspace").
# ---------------------------------------------------------------------------


def _root_sha(root):
    result = process.run(["git", "rev-parse", "HEAD"], cwd=root)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Repo-context inventory (docs/specs/drafter.md "Repo context probe").
# ---------------------------------------------------------------------------


def _template_inventory(root):
    """`.github/ISSUE_TEMPLATE/*` listing at `root` (docs/specs/drafter.md "Repo context probe") — a
    plain filesystem read,
    no `git`/`gh` call (root IS the drafter's grounding vantage; see module docstring). `present`
    means "at least one template file exists"; an empty (or absent) directory both report
    `present: False` so the router falls back to the built-in templates identically either way.
    """
    dir_path = Path(root) / ".github" / "ISSUE_TEMPLATE"
    if not dir_path.is_dir():
        return {"present": False, "dir": str(dir_path), "files": []}
    files = sorted(entry.name for entry in dir_path.iterdir() if entry.is_file())
    return {"present": len(files) > 0, "dir": str(dir_path), "files": files}


def _doc_presence(root, rel_path):
    doc_path = Path(root) / rel_path
    present = doc_path.is_file()
    return {"present": present, "path": str(doc_path) if present else None}


def _prd_presence(root):
    """PRD presence across the four v1-documented candidate paths (docs/specs/drafter.md
    "Repo context probe") — first match
    wins; `candidates_checked` rides along so a caller can see the exact search order without
    re-deriving it."""
    for rel in _PRD_CANDIDATE_PATHS:
        doc_path = Path(root) / rel
        if doc_path.is_file():
            return {
                "present": True,
                "path": str(doc_path),
                "candidates_checked": list(_PRD_CANDIDATE_PATHS),
            }
    return {"present": False, "path": None, "candidates_checked": list(_PRD_CANDIDATE_PATHS)}


def _grounding_docs(root):
    return {
        "prd": _prd_presence(root),
        "architecture": _doc_presence(root, _ARCHITECTURE_PATH),
        "constitution": _doc_presence(root, _CONSTITUTION_PATH),
        "claude_md": _doc_presence(root, _CLAUDE_MD_PATH),
    }


def _fetch_labels(repo, cwd=None):
    """`gh label list --repo <repo> --limit 100 --json name,description,color` (docs/specs/drafter.md
    "Repo context probe"
    `gh label list --limit 100`) — so the router maps feedback to existing labels rather than
    inventing new ones (docs/specs/drafter.md "Artifacts read", existing-labels row), and so it can
    tell whether a needed `audience:*` label
    already exists before offering to create it (`_shared/question-issue.md`). Returns
    `(labels, decision_or_none)`.
    """
    result = process.run(
        ["gh", "label", "list", "--repo", repo, "--limit", "100", "--json", "name,description,color"],
        cwd=cwd,
    )
    if result.auth_required:
        return None, needs_decision(
            AUTH_REQUIRED,
            summary="gh authentication required",
            context={"stderr": result.stderr, "returncode": result.returncode},
            options=["run: gh auth login"],
        )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    raw = json.loads(result.stdout)
    return [
        {"name": item.get("name"), "description": item.get("description"), "color": item.get("color")}
        for item in raw
    ], None


def _read_oq_marker_config(root):
    """The `<!-- drafter-open-question-markers -->` config block (docs/specs/drafter.md
    "OQ marker config read";
    `_shared/open-question-detection.md`'s "Config block (preferred hint)") — raw interior text,
    never interpreted here (facts by script, meaning by model: the register-location/inline-pattern/
    open-status-rule prose is the router's own reading job). Absent -> `heuristics_active: True`,
    the signal to fall back to the built-in heuristic cue list (`open-question-detection.md`'s
    "Heuristic fallback" cues — also not enumerated here; they are prompt-side prose, not a fact a
    script derives).
    """
    present, lines, source = config_block.read_block_anywhere(root, OQ_MARKER_CONFIG_BLOCK)
    return {
        "oq_markers": {
            "present": present,
            "raw": "\n".join(lines) if present else None,
            "source": source,
        },
        "heuristics_active": not present,
    }


# ---------------------------------------------------------------------------
# `## Stories` section parsing + per-story live-state fetch (epic-revise mode only) — byte-identical
# grammar to `prep_planner.py`'s (restated locally; see module docstring's "no prep-to-prep imports"
# note). No shared `parse.py` subcommand covers this grammar (only `dod`/`oq-links`/`phases` are
# named in architecture.md §3's decision-code table) — best-effort, non-raising, matching every
# other "no dedicated decision code" block-scan in this codebase.
# ---------------------------------------------------------------------------


def _parse_stories_section(issue_body):
    lines = (issue_body or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Stories\s*$", line, re.IGNORECASE):
            start = i + 1
            break
    if start is None:
        return []
    end = len(lines)
    for j in range(start, len(lines)):
        if _SECTION_HEADING_RE.match(lines[j]):
            end = j
            break

    entries = []
    for raw_line in lines[start:end]:
        stripped = raw_line.strip()
        filed_match = _STORY_FILED_RE.match(stripped)
        if filed_match:
            entries.append(
                {
                    "number": int(filed_match.group(2)),
                    "title": filed_match.group(3).strip(),
                    "checked": filed_match.group(1) in ("x", "X"),
                }
            )
            continue
        plain_match = _STORY_PLAIN_RE.match(stripped)
        if plain_match:
            entries.append(
                {"number": None, "title": plain_match.group(2).strip(), "checked": plain_match.group(1) in ("x", "X")}
            )
    return entries


def _fetch_story_state(repo, story_number, cwd=None):
    """`gh issue view <NN> --json state,title,labels` — the per-filed-story live-state fetch v1's
    `GATHER_EPIC` performs so the caller can reconcile body checkboxes against reality
    (the v1 executor agent's `GATHER_EPIC` description; docs/specs/drafter.md "Epic-revise gather").
    Returns `(state_dict,
    decision_or_none)`."""
    result = process.run(
        ["gh", "issue", "view", str(story_number), "--repo", repo, "--json", "state,title,labels"],
        cwd=cwd,
    )
    if result.auth_required:
        return None, needs_decision(
            AUTH_REQUIRED,
            summary="gh authentication required",
            context={"stderr": result.stderr, "returncode": result.returncode},
            options=["run: gh auth login"],
        )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    data = json.loads(result.stdout)
    return {
        "state": data.get("state"),
        "title": data.get("title"),
        "labels": [label.get("name") for label in data.get("labels") or []],
    }, None


def _build_epic_revise_facts(issue_body, repo, sub_issues=None, cwd=None):
    """Epic-revise mode's facts: the epic's story set, reconciled against live state.

    The story set resolves through the sources of `skills/_shared/epic-story-hierarchy.md`, and
    `stories_source` reports which one answered so the router knows whether there are checkboxes
    to reconcile at all:

    - **`sub-issues`** — `sub_issues` (GitHub's native relation) is non-empty and the body has no
      `## Stories` section. Every entry is filed by construction, `state`/`live_title` come from the
      relation itself (**no per-story round-trip** — the gather already carried them), and `checked`
      mirrors live state, so a checkbox/live-state mismatch is unrepresentable.
    - **`checklist`** — the legacy `## Stories` fallback for an epic filed before the native
      relation was written, or on a host that doesn't serve it. A FILED story
      (`- [ ] #NN — <title>`) gets its live `state`/`live_title` via :func:`_fetch_story_state`; a
      PLACEHOLDER bullet (not yet filed) rides with both `None` — mirroring `prep_planner.py`'s
      identical shape. A MISMATCH (checked but still OPEN, or unchecked but already CLOSED) surfaces
      in `attention` rather than being silently reconciled here (architecture.md §4: "the router
      reconciles the checkboxes ... surface it with evidence" — reconciling the BODY TEXT is the
      router's write, not a fact this script computes).
    - **`mixed`** — both, unioned by issue number with native state winning on overlap. Reachable
      without anyone erring: epic-revise files a NEW story under a legacy epic with `--parent`, so
      that story is native while its siblings stay checklist bullets. Returning only one half here
      would silently drop the other half's stories from the reconciliation.

    Returns `(epic_revise_facts, attention_lines, decision_or_none)`.
    """
    stories = []
    attention = []

    native_stories = []
    for node in sub_issues or []:
        live_state = node.get("state")
        native_stories.append(
            {
                "number": node.get("number"),
                "title": node.get("title"),
                "checked": (live_state or "").upper() == "CLOSED",
                "state": live_state,
                "live_title": node.get("title"),
            }
        )

    checklist_entries = _parse_stories_section(issue_body)
    if native_stories and not checklist_entries:
        return {"stories": native_stories, "stories_source": "sub-issues"}, attention, None

    native_numbers = {s["number"] for s in native_stories}

    for entry in checklist_entries:
        if entry["number"] is not None and entry["number"] in native_numbers:
            # Already carried by the native half of a `mixed` epic, with authoritative live state.
            continue
        if entry["number"] is None:
            stories.append(
                {"number": None, "title": entry["title"], "checked": entry["checked"], "state": None, "live_title": None}
            )
            continue
        state_fact, decision = _fetch_story_state(repo, entry["number"], cwd=cwd)
        if decision is not None:
            return None, None, decision
        live_state = state_fact["state"]
        live_closed = (live_state or "").upper() == "CLOSED"
        if entry["checked"] != live_closed:
            attention.append(
                "story #%s checkbox is %s but live state is %s"
                % (entry["number"], "checked" if entry["checked"] else "unchecked", live_state)
            )
        stories.append(
            {
                "number": entry["number"],
                "title": entry["title"],
                "checked": entry["checked"],
                "state": live_state,
                "live_title": state_fact["title"],
            }
        )
    # `mixed` when both halves contributed — the union, native state winning on overlap. Taking one
    # half and dropping the other would silently lose stories (skills/_shared/epic-story-hierarchy.md).
    return {
        "stories": native_stories + stories,
        "stories_source": "mixed" if native_stories else "checklist",
    }, attention, None


# ---------------------------------------------------------------------------
# Revise facts (mode == "revise" only).
# ---------------------------------------------------------------------------


def _extract_body(envelope, key):
    body = envelope.get(key)
    if body is None and envelope.get("%s_mode" % key) == "path":
        body = Path(envelope["%s_path" % key]).read_text(encoding="utf-8")
    return body or ""


def _build_revise_facts(issue_envelope):
    """Assemble revise-mode-only facts (docs/specs/drafter.md "Revise-mode gather"): the plan-marker's presence + staged
    body (grounds the revise against the planner's approach; lets the router decide whether Step
    R6's staleness flag applies), the open-PR list (already filtered by `gh_gather.references_issue`
    — surfaced so the router can coordinate before editing, docs/specs/drafter.md "Artifacts read"),
    and the
    closed-by-PR/project references `--extra-json` folded in (same row).
    """
    plan_present = bool(issue_envelope.get("marker_comment_present"))
    plan_facts = {
        "present": plan_present,
        "comment_id": issue_envelope.get("marker_comment_id"),
        "comment_url": issue_envelope.get("marker_comment_url"),
    }
    if plan_present:
        plan_facts["body_mode"] = issue_envelope.get("marker_comment_mode")
        if issue_envelope.get("marker_comment_mode") == "path":
            plan_facts["body_path"] = issue_envelope.get("marker_comment_path")
        else:
            plan_facts["body"] = issue_envelope.get("marker_comment_body")

    return {
        "plan": plan_facts,
        "open_prs": issue_envelope.get("open_prs") or [],
        "closed_by_pull_requests_references": issue_envelope.get("closedByPullRequestsReferences"),
        "project_items": issue_envelope.get("projectItems"),
    }


# ---------------------------------------------------------------------------
# attention
# ---------------------------------------------------------------------------


def _build_attention(open_question_candidates, target, mode, extra=None):
    attention = []
    for group in open_question_candidates or []:
        attention.append(
            "open question '%s' has %d tracker candidate(s) — do not record it as (not filed)"
            % (group["oq_id"], len(group["candidates"]))
        )
    if target is not None and mode in ("revise", "epic-revise") and (target.get("state") or "").upper() == "CLOSED":
        attention.append(
            "target issue #%s is closed — resolve the 'Closed issue' gate before revising"
            % target["number"]
        )
    if extra:
        attention.extend(extra)
    return attention


# ---------------------------------------------------------------------------
# Facts-block assembly
# ---------------------------------------------------------------------------


def build_facts(repo, issue=None, root=".", scratch_dir=None, cwd=None):
    """Assemble the drafter's complete facts block and return the envelope dict WITHOUT printing
    it (the testable core, mirroring `prep_planner.build_facts` / `prep_resolver.build_facts` /
    `prep_evaluator.build_facts`). Returns `None` after a `needs_decision` envelope has already
    been emitted on stdout.
    """
    root = str(Path(root).resolve())
    if scratch_dir is None:
        scratch_dir = "/tmp/gh-drafter-%s" % (issue if issue else "new")
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    root_sha = _root_sha(root)

    # 1) Repo-context inventory (common core — every mode gets it; docs/specs/drafter.md "Repo
    #    context probe"). Templates/docs are local filesystem reads; labels is the one gh call every
    #    invocation makes.
    config = _read_oq_marker_config(root)
    repo_context = {
        "templates": _template_inventory(root),
        "docs": _grounding_docs(root),
    }
    labels, labels_decision = _fetch_labels(repo, cwd=cwd)
    if _forward_decision(labels_decision):
        return None
    repo_context["labels"] = labels

    target = None
    vector_type = None
    mode = "new"
    open_questions = []
    open_question_candidates = []
    revise_facts = None
    epic_revise_facts = None
    extra_attention = []
    sections = {}

    # 2) Target-issue gather — revise/epic-revise modes ONLY (`--issue` given). `new` mode has no
    #    target yet, so this whole block (and its 3-4 gh calls) is skipped entirely.
    if issue:
        exit_code, issue_envelope = gh_gather.run(
            str(issue),
            repo,
            marker_prefix=PLAN_MARKER,
            scratch_dir=scratch_dir,
            extra_json=REVISE_EXTRA_JSON,
            env=None,
            stream=_DiscardStream(),
        )
        if issue_envelope is not None and issue_envelope.get("status") == "needs_decision":
            if _forward_decision(issue_envelope["decision"], notices=issue_envelope.get("notices")):
                return None
        if exit_code != 0:
            sys.stderr.write(
                "prep_drafter: gh_gather on issue #%s failed (exit %d)\n" % (issue, exit_code)
            )
            sys.exit(1)

        issue_body = _extract_body(issue_envelope, "issue_body")
        issue_labels = [label.get("name") for label in issue_envelope.get("labels") or []]
        issue_title = issue_envelope.get("title") or ""
        vector_type = _detect_type(issue_labels, issue_title)
        mode = "epic-revise" if vector_type == "epic" else "revise"

        target = {
            "kind": "issue",
            "number": issue_envelope["number"],
            "title": issue_envelope["title"],
            "state": issue_envelope["state"],
            "labels": issue_labels,
            "blocked_by": issue_envelope.get("blocked_by") or [],
            "blocking": issue_envelope.get("blocking") or [],
            "deps_available": issue_envelope.get("deps_available"),
            "parent": issue_envelope.get("parent"),
            "sub_issues": issue_envelope.get("sub_issues") or [],
            "sub_issues_summary": issue_envelope.get("sub_issues_summary") or {},
            "subissues_available": issue_envelope.get("subissues_available"),
        }

        # 3) Search-before-file open-question candidates — the target body IS the source to scan
        #    (S14-promoted oq_tracker.build_open_question_candidates; see module docstring).
        open_questions, open_question_candidates, oq_decision = oq_tracker.build_open_question_candidates(
            issue_body, repo, cwd=cwd
        )
        if _forward_decision(oq_decision):
            return None

        # 4) Mode-specific facts.
        if mode == "epic-revise":
            epic_revise_facts, epic_attention, epic_decision = _build_epic_revise_facts(
                issue_body,
                repo,
                sub_issues=issue_envelope.get("sub_issues") or [],
                cwd=cwd,
            )
            if _forward_decision(epic_decision):
                return None
            extra_attention.extend(epic_attention)
        else:
            revise_facts = _build_revise_facts(issue_envelope)

        sections = {
            key: value
            for key, value in issue_envelope.items()
            if key.startswith(("issue_body", "thread", "marker_comment"))
        }

    suggested_playbook = _suggested_playbook(mode, vector_type)
    vector = {"mode": mode, "type": vector_type}

    facts = {
        "repo": repo,
        "scratch": scratch_dir,
        "root": {"path": root, "sha": root_sha},
        "target": target,
        "vector": vector,
        "suggested_playbook": suggested_playbook,
        "config": config,
        "repo_context": repo_context,
        "open_questions": open_questions,
        "open_question_candidates": open_question_candidates,
        "attention": _build_attention(open_question_candidates, target, mode, extra=extra_attention),
        "notices": [],
    }
    if revise_facts is not None:
        facts["revise"] = revise_facts
    if epic_revise_facts is not None:
        facts["epic_revise"] = epic_revise_facts
    if sections:
        facts["sections"] = sections

    return facts


def main(argv):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument(
        "--issue",
        default=None,
        help="target issue number — selects revise/epic-revise mode; omit for new-issue mode",
    )
    parser.add_argument("--root", default=".", help="project root (architecture.md §6 vantage)")
    parser.add_argument(
        "--scratch-dir",
        default=None,
        help="scratch dir for spilled sections (default: /tmp/gh-drafter-<issue-or-\"new\">)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="explicit working directory for the gh calls that have no --repo scoping of their "
        "own (per-story state fetch, OQ tracker search); optional in normal use, provided for "
        "test-injection — mirrors prep_planner.py's/prep_resolver.py's identical --cwd knob",
    )
    parser.add_argument(
        "--oq-query",
        action="append",
        default=None,
        metavar="TEXT",
        help="one-shot tracker de-dup lookup for an open-question topic named directly (repeatable) "
        "— mirrors prep_planner.py's identical flag (oq_tracker.build_oq_query); short-circuits to "
        "the one-shot payload, no full facts assembly, regardless of --issue",
    )
    args = parser.parse_args(argv)

    if args.oq_query:
        payload, notices, decision = oq_tracker.build_oq_query(args.repo, args.oq_query, cwd=args.cwd)
        if decision is not None:
            emit_needs_decision(decision, notices=notices)
            return EXIT_OK
        emit_ok(payload=payload, notices=notices)
        return EXIT_OK

    facts = build_facts(
        args.repo, issue=args.issue, root=args.root, scratch_dir=args.scratch_dir, cwd=args.cwd
    )
    if facts is None:
        return EXIT_OK
    notices = facts.pop("notices", [])
    emit_ok(payload=facts, notices=notices)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
