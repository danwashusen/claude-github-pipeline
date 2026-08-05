#!/usr/bin/env python3
"""prep_slicer.py — the slicer's complete facts block in one call (architecture.md §4; #17, #16).
Assembles the session's entire starting state — the target issue + thread, its type, the **altitude**
the cut runs at, the **refusal** set (the conditions under which decomposing would be wrong), the
existing child set (so a re-run resumes instead of duplicating), the consuming repo's declared
grounding docs, and `suggested_playbook` — as ONE JSON envelope on stdout, so the slicer session's
startup is one Python process, never a subprocess chain.

The slicer cuts one filed issue into ordered children and files them as native sub-issues
(`skills/_shared/epic-story-hierarchy.md`). **One operation, two altitudes** (#16), differing in
exactly one parameter — the independence bar each child must clear, set by whether the child gets its
own branch and PR:

  - ``story`` altitude — a story or standalone issue cut into **deliverable slices**. A slice is a
    *phase marker*: the resolver ships it as a phase on the parent's branch and closes it as that
    phase lands, so its bar is independently *demonstrable*.
  - ``epic`` altitude — an epic cut into **stories**. Each story gets its own branch, PR, review and
    merge, so its bar is independently *shippable*.

Either way the point of filing children as issues is that GitHub's rollup then tracks delivery
progress at parent altitude. `vector.altitude` is the fact the flow reads; the bar itself is stated
once, in `skills/slicer/references/slicing-method.md` §1.

Composition (architecture.md §2 "compose the executors in-process"; §1 "the only external
processes any script may spawn are git/gh")::

    gh_gather.run(..., stream=)      -- the target's body/thread + native blocked_by/blocking + the
                                        native parent/sub_issues relation + the research-dossier
                                        marker, in ONE round-trip
    branching.detect_type            -- the shared epic/story/standard core (import-only), with a
                                        local `question` arm layered on (prep_drafter's precedent)
    doc_catalogue.read_catalogue     -- the consuming repo's `<!-- doc-catalogue -->` grounding docs
    parse.parse_oq_links             -- the target's `## Open questions` section, for the
                                        `in-scope (blocked)` disposition

Plus ONE direct `gh issue view <parent> --json state,title,labels` — and only when the target
actually has a parent — because the sub-issue/parent node shape carries **no labels**
(`epic-story-hierarchy.md` "The facts"), so the parent cannot be typed from the gather alone. Same
shape and the same `AUTH_REQUIRED` handling as `prep_planner._fetch_story_state` /
`prep_drafter`'s equivalent; architecture.md §1 permits a prep to spawn `gh` directly. Two further
`gh` calls are made only when the epic-altitude paths need them: one per FILED `## Stories` checklist
entry on a legacy epic (the relocated epic-revise read, below), and one per `--adopt` candidate.

Usage::

    prep_slicer.py <issue> <owner/repo> [--root PATH] [--scratch-dir PATH] [--cwd PATH]
                                        [--promote] [--adopt N]...
    prep_slicer.py <owner/repo> --adopt-check N [--adopt-check N]... [--cwd PATH]

``--promote`` and ``--adopt`` are passed by the **router**, which can read the operator's invocation
prose; prep cannot. ``--promote`` says "the operator asked for this standard issue to become an Epic"
(the planner's seam-gate off-ramp A), so the altitude is forced to ``epic`` and `facts.promotion` is
true — the flow then rewrites the target as an Epic behind its own diff-and-confirm gate before
cutting. ``--adopt N`` names an ALREADY-FILED issue to adopt as a child; `facts.adoption_candidates`
carries each one's live state so the flow can present it, and the write itself is
`gh_persist.py add-parent`. ``--adopt-check`` is the one-shot mode for candidates the operator names
mid-session (the `prep_drafter --oq-query` precedent): it emits only the candidates, no facts block,
so a mid-flow lookup never re-runs the whole gather.

**No workspace — the slicer grounds on the CURRENT checkout**, the same root-only vantage
`prep_drafter.py` and `prep_researcher.py` take, and for the same threat-model reason: the slicer
reads no PR head and gates no merge, so architecture.md §6's "a PR must not weaken its own gates"
cannot apply. It runs *before* a workspace exists (its whole output is the input to planning, which
precedes `workspace-open`). `root` therefore carries only `{path, sha}` — informational, never
enforced — and the doc catalogue is read at that same working vantage, deliberately NOT through
`refblocks`: a catalogue names no gate (`skills/_shared/doc-catalogue.md` "Where the catalogue is
read from"), and an uncommitted catalogue edit should count for a decomposition the operator is
running right now.

**Refusals are facts, not decision codes.** `vector.refusals` is a list of reason tokens from a
closed set; the router renders the matching refusal handoff and stops. They are deliberately NOT
`needs_decision` codes: a refusal is not an ambiguity for the operator to resolve with one answer —
it is a *routing outcome* with its own handoff (to `setup`, to the question-resolver, or terminal),
and architecture.md §3's decision set is for genuine one-card decisions. Adding four codes to a
closed set to express "this stage does not apply here" would be a contract change that buys nothing.

An **epic target is no longer refused** (#16): it is the epic-altitude happy path.

  - ``slice-target``   — the target is itself a slice (it has a parent, and that parent is not an
                         epic). **A slice is never sliced**: it has no branch of its own, so a
                         sub-slice could not ship, and a fourth level would break the
                         by-construction identification every reader relies on.
  - ``question-target`` — a `question` issue is answered by a human in its thread; there is no
                         buildable scope to cut.
  - ``closed-target``  — decomposing delivered work files slices nothing will ever close, leaving a
                         permanently false rollup.
  - ``blocked``        — an OPEN native blocker, or an `in-scope (blocked)` open-question entry.
                         Slicing against an unanswered question produces slices the answer may
                         invalidate. Read from LIVE state (`blocked_by`, and the tracker for OQ
                         entries), never from a prose claim in the body — a recorded blocker line is
                         a claim made at authoring time, not a fact.

`DOC_CATALOGUE_ABSENT` stays a **notice**, not a refusal, even though the grounding gate is a hard
refusal in the playbook. The distinction is load-bearing: prep cannot see whether the operator named
grounding sources at invocation, so only the flow can decide that the gate fails. Prep reports the
absence loudly and lets the playbook refuse.

**`vector.mode` — the two-value closed set ``"fresh"`` / ``"resume"``.** Derived from one
script-visible signal: whether the target already has children. `resume` is what makes a re-run after
a partial failure safe — the flow reports what exists and cuts only the remainder, rather than
re-filing.

**`facts.children` — one key, both altitudes**, with `kind` naming which (`"slices"` / `"stories"`):

  - Story altitude reads the native sub-issue set only. `children.next_index` is parsed best-effort
    from the existing `<N>/S<K>` designator titles so a resumed run continues the numbering instead
    of colliding; `source` is null (slices postdate the native relation, so they have no fallback —
    `epic-story-hierarchy.md`'s "The slice edge has no checklist fallback and never will").
  - Epic altitude reads through the **two-tier read** that contract defines, and `source` reports
    which tier answered: `sub-issues` (native), `checklist` (the legacy `## Stories` section on an
    epic filed before the relation existed, or on a host that doesn't serve it), or `mixed` (both,
    unioned by number with native state winning — never one half dropped, which would silently lose
    stories). This is v1's epic-revise gather, relocated here from `prep_drafter.py` with #16: the
    drafter no longer decomposes epics, so the read belongs where the reconciliation now happens.
    Stories are titled plainly, so `next_index` is null.

Exit codes (architecture.md §3): 0 with the facts-block envelope present (``status`` is ``"ok"`` or
``"needs_decision"``); 2 on a usage error (no envelope). Any other non-zero is an unclassified hard
`gh`/`git` failure surfaced by the composed gather — stderr carries the faithful error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import branching  # noqa: E402  (import after sys.path setup, by necessity; shared type-detection core)
import doc_catalogue  # noqa: E402  (the consuming repo's declared grounding docs)
import gh_gather  # noqa: E402
import parse  # noqa: E402  (the `## Open questions` parse for the in-scope-blocked refusal)
from pipelib import process  # noqa: E402
from pipelib.decisions import (  # noqa: E402
    AUTH_REQUIRED,
    DOC_CATALOGUE_ABSENT,
    SUBISSUES_UNSUPPORTED,
    needs_decision,
)
from pipelib.envelope import emit_needs_decision, emit_ok  # noqa: E402

# The research-dossier marker (`skills/researcher/references/dossier-schema.md`). The slicer treats a
# dossier as an OPTIONAL grounding input — current external truth the cut may cite — never a
# requirement, and never a mode signal the way it is for the researcher.
RESEARCH_MARKER = "<!-- issue-research:v1 -->"

# The `question` label arm `branching.detect_type` doesn't carry (it returns epic/story/standard
# only). Layered locally, exactly as `prep_drafter.py` does for its own four-way type space — see
# `prep_planner.py`'s module docstring for the "no prep-to-prep imports" convention that keeps this a
# local arm over the shared core rather than a fourth copy of the whole rule.
_QUESTION_LABEL = "question"

# The slice title designator: `<parent#>/S<K> — <behaviour>` (recorded on #17). Parsed best-effort to
# resume numbering; a child whose title doesn't match simply doesn't contribute an index, which is
# why `next_index` falls back to "one past the child count".
_SLICE_DESIGNATOR_RE = re.compile(r"^\s*(\d+)\s*/\s*S(\d+)\b")

# The legacy `## Stories` checklist grammar — byte-identical to `prep_planner.py`'s (and to the copy
# `prep_drafter.py` carried until #16 moved epic decomposition here), restated locally per
# `prep_planner.py`'s "no prep-to-prep imports" convention. No shared `parse.py` subcommand covers
# this grammar (only `dod`/`oq-links`/`phases` are named in architecture.md §3's decision-code table),
# so the scan is best-effort and non-raising like every other block-scan without a decision code.
_STORY_FILED_RE = re.compile(r"^-\s*\[( |x|X)\]\s*#(\d+)\s*(?:—|-)\s*(.+)$")
_STORY_PLAIN_RE = re.compile(r"^-\s*\[( |x|X)\]\s*(.+)$")
_SECTION_HEADING_RE = re.compile(r"^##(?!#)")

# The closed refusal set (see the module docstring for each token's rationale). There is deliberately
# no `epic-target`: #16 made an epic the epic-altitude happy path.
REFUSAL_SLICE_TARGET = "slice-target"
REFUSAL_QUESTION_TARGET = "question-target"
REFUSAL_CLOSED_TARGET = "closed-target"
REFUSAL_BLOCKED = "blocked"


class _DiscardStream:
    """A minimal write-sink for `gh_gather.run(stream=...)` — see `prep_researcher._DiscardStream` /
    `prep_evaluator._DiscardStream` for the full rationale (restated locally per those modules' own
    note: sharing a two-method sink across prep modules is not the in-process composition
    architecture.md §2 asks for)."""

    def write(self, _data):
        return None

    def flush(self):
        return None


def _forward_decision(decision, notices=None):
    """Emit a composed core's returned `decision` AS-IS on prep's own stdout and return `True` when a
    decision was present. Mirrors `prep_researcher._forward_decision` exactly."""
    if decision is not None:
        emit_needs_decision(decision, notices=notices)
        return True
    return False


def _root_sha(root):
    result = process.run(["git", "rev-parse", "HEAD"], cwd=root)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Type detection (shared core + the local `question` arm).
# ---------------------------------------------------------------------------


def _detect_type(labels, title):
    """`branching.detect_type` widened by one arm. The shared core answers epic/story/standard; a
    `question` label wins over the `standard` fallback but never over `epic`/`story` (a
    pathologically double-labelled issue keeps the core's documented precedence)."""
    core = branching.detect_type(labels, title)
    if core == "standard" and _QUESTION_LABEL in {
        (label or "").strip().lower() for label in labels or []
    }:
        return "question"
    return core


def _fetch_parent_state(parent_number, repo, cwd=None):
    """The parent's `state,title,labels` — the ONE extra `gh` call this prep makes, and only when the
    target has a parent. Needed because the native relation's node shape carries no labels, so the
    parent cannot be typed from the gather. Returns `(state_dict, decision_or_none)`, the same shape
    (and the same `AUTH_REQUIRED` handling) as `prep_planner._fetch_story_state`."""
    result = process.run(
        ["gh", "issue", "view", str(parent_number), "--repo", repo, "--json", "state,title,labels"],
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
    data = json.loads(result.stdout or "{}")
    labels = [label.get("name") for label in data.get("labels") or []]
    return {
        "number": int(parent_number),
        "state": data.get("state"),
        "title": data.get("title"),
        "labels": labels,
        "type": _detect_type(labels, data.get("title") or ""),
    }, None


def _fetch_story_state(repo, story_number, cwd=None):
    """`gh issue view <NN> --json state,title,labels` for one FILED `## Stories` checklist entry — the
    per-story live-state read a legacy epic needs, since a checklist bullet carries no state of its
    own. Relocated from `prep_drafter.py` with #16 (same shape, same `AUTH_REQUIRED` handling).
    Returns `(state_dict, decision_or_none)`."""
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
    data = json.loads(result.stdout or "{}")
    return {
        "state": data.get("state"),
        "title": data.get("title"),
        "labels": [label.get("name") for label in data.get("labels") or []],
    }, None


def _fetch_adoption_candidate(repo, number, cwd=None):
    """One `--adopt` candidate's live state, including its CURRENT parent — the field that decides
    whether adopting it would steal another parent's child. `parent` is capability-gated exactly as
    the gather's ladder gates it, so a host that doesn't serve the relation degrades to
    `parent: None` + a `SUBISSUES_UNSUPPORTED` notice rather than failing the whole prep.

    Returns `(candidate_dict, notices, decision_or_none)`."""
    notices = []
    fields = "state,title,labels,parent"
    result = process.run(
        ["gh", "issue", "view", str(number), "--repo", repo, "--json", fields], cwd=cwd
    )
    if result.returncode != 0 and not result.auth_required and gh_gather._is_unknown_field_error(
        result.stderr
    ):
        notices.append(SUBISSUES_UNSUPPORTED)
        result = process.run(
            ["gh", "issue", "view", str(number), "--repo", repo, "--json", "state,title,labels"],
            cwd=cwd,
        )
    if result.auth_required:
        return None, notices, needs_decision(
            AUTH_REQUIRED,
            summary="gh authentication required",
            context={"stderr": result.stderr, "returncode": result.returncode},
            options=["run: gh auth login"],
        )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    data = json.loads(result.stdout or "{}")
    labels = [label.get("name") for label in data.get("labels") or []]
    parent_node = data.get("parent")
    return (
        {
            "number": int(number),
            "state": data.get("state"),
            "title": data.get("title"),
            "labels": labels,
            "type": _detect_type(labels, data.get("title") or ""),
            "parent": (parent_node or {}).get("number") if parent_node else None,
            "already_parented": bool(parent_node),
        },
        notices,
        None,
    )


def _build_adoption_candidates(numbers, repo, cwd=None):
    """Every `--adopt` candidate, in the order the operator named them (which becomes their panel
    order if approved). Returns `(candidates, notices, decision_or_none)`."""
    candidates = []
    notices = []
    for number in numbers or []:
        candidate, candidate_notices, decision = _fetch_adoption_candidate(repo, number, cwd=cwd)
        for notice in candidate_notices:
            if notice not in notices:
                notices.append(notice)
        if decision is not None:
            return None, notices, decision
        candidates.append(candidate)
    return candidates, notices, None


# ---------------------------------------------------------------------------
# Altitude + the child set (resume, don't duplicate).
# ---------------------------------------------------------------------------


def _detect_altitude(target_type, promote=False):
    """Which bar this cut runs at (module docstring). An epic's children are stories (*shippable*);
    everything else's are deliverable slices (*demonstrable*). `--promote` forces epic altitude
    because the target BECOMES an epic before the cut — the flow rewrites it behind its own gate."""
    return "epic" if (target_type == "epic" or promote) else "story"


def _parse_stories_section(issue_body):
    """The legacy `## Stories` checklist entries of an epic body — the `checklist` tier of
    `epic-story-hierarchy.md`'s two-tier read. A FILED bullet (`- [ ] #NN — <title>`) yields its
    number; a PLACEHOLDER bullet yields `number: None`. Relocated from `prep_drafter.py` with #16."""
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
                {
                    "number": None,
                    "title": plain_match.group(2).strip(),
                    "checked": plain_match.group(1) in ("x", "X"),
                }
            )
    return entries


def _build_story_set(sub_issues, issue_body, repo, cwd=None):
    """The epic's existing story set through `epic-story-hierarchy.md`'s two-tier read, with `source`
    reporting which tier answered so the flow knows whether there are checkboxes to reconcile at all.

    A checkbox/live-state MISMATCH surfaces in `attention` rather than being reconciled here:
    reconciling the body text is a write the flow proposes at its gate, not a fact this script
    computes. Returns `(children_dict, attention_lines, decision_or_none)`.
    """
    attention = []

    native = []
    for node in sub_issues or []:
        live_state = node.get("state")
        native.append(
            {
                "number": node.get("number"),
                "title": node.get("title"),
                "state": live_state,
                "checked": (live_state or "").upper() == "CLOSED",
                "live_title": node.get("title"),
            }
        )

    checklist_entries = _parse_stories_section(issue_body)
    if native and not checklist_entries:
        return _children("stories", native, source="sub-issues"), attention, None
    if not native and not checklist_entries:
        return _children("stories", [], source=None), attention, None

    native_numbers = {entry["number"] for entry in native}
    from_checklist = []
    for entry in checklist_entries:
        if entry["number"] is not None and entry["number"] in native_numbers:
            # Already carried by the native half of a `mixed` epic, with authoritative live state.
            continue
        if entry["number"] is None:
            from_checklist.append(
                {
                    "number": None,
                    "title": entry["title"],
                    "state": None,
                    "checked": entry["checked"],
                    "live_title": None,
                }
            )
            continue
        state_fact, decision = _fetch_story_state(repo, entry["number"], cwd=cwd)
        if decision is not None:
            return None, None, decision
        live_state = state_fact["state"]
        if entry["checked"] != ((live_state or "").upper() == "CLOSED"):
            attention.append(
                "story #%s checkbox is %s but live state is %s"
                % (entry["number"], "checked" if entry["checked"] else "unchecked", live_state)
            )
        from_checklist.append(
            {
                "number": entry["number"],
                "title": entry["title"],
                "state": live_state,
                "checked": entry["checked"],
                "live_title": state_fact["title"],
            }
        )
    return (
        _children(
            "stories",
            native + from_checklist,
            source="mixed" if native else "checklist",
        ),
        attention,
        None,
    )


def _children(kind, entries, source=None, next_index=None):
    """The one `facts.children` shape both altitudes fill (module docstring)."""
    return {
        "kind": kind,
        "entries": entries,
        "count": len(entries),
        "open_count": sum(1 for e in entries if (e.get("state") or "").upper() == "OPEN"),
        "next_index": next_index,
        "source": source,
    }


def _build_slice_set(sub_issues, target_number):
    """The existing slice set — one entry per live sub-issue in the sub-issue panel's own order (which
    IS delivery order, since `addSubIssue` appends).

    `next_index` is the numbering a resumed run continues from: one past **whichever is greater** of
    the highest `S<K>` parsed out of the children's titles and the child count. Taking the max (not
    just the parsed highest) is what makes a hand-retitled child safe: if someone renamed `103/S3`,
    its index is unparseable, and continuing from the parsed highest alone would re-issue S3.
    Over-counting collides with nothing; under-counting collides with a live slice.
    """
    entries = []
    highest = 0
    for child in sub_issues or []:
        title = child.get("title") or ""
        match = _SLICE_DESIGNATOR_RE.match(title)
        index = None
        if match is not None and int(match.group(1)) == int(target_number):
            index = int(match.group(2))
            highest = max(highest, index)
        entries.append(
            {
                "number": child.get("number"),
                "title": title,
                "state": child.get("state"),
                "designator_index": index,
            }
        )
    return _children(
        "slices", entries, source=None, next_index=max(highest, len(entries)) + 1
    )


# ---------------------------------------------------------------------------
# Refusals + attention
# ---------------------------------------------------------------------------


def _build_refusals(target_type, target_state, parent, blocked_by, oq_blocked):
    """The closed refusal set (module docstring). Order is stable so the router's rendering choice is
    deterministic when more than one applies — the router renders the FIRST."""
    refusals = []
    if target_type == "question":
        refusals.append(REFUSAL_QUESTION_TARGET)
    # A parent that is not an epic means the target is itself a slice (epic -> story -> slice, and
    # the relation has exactly three levels), so slicing it would create a fourth. Skipped for an
    # epic target: an epic is the top of the hierarchy, so a parent on it is malformed data, not
    # evidence that the epic is a slice — misreading it that way would refuse the epic-altitude
    # happy path for the one shape it can never legitimately be.
    if target_type != "epic" and parent is not None and parent.get("type") != "epic":
        refusals.append(REFUSAL_SLICE_TARGET)
    if (target_state or "").upper() == "CLOSED":
        refusals.append(REFUSAL_CLOSED_TARGET)
    if blocked_by or oq_blocked:
        refusals.append(REFUSAL_BLOCKED)
    return refusals


def _open_blockers(blocked_by):
    """The OPEN entries of the native `blocked_by` set. A closed blocker is stale, not a gate — the
    live state decides, every time, never the body's recorded line."""
    return [
        {"number": node.get("number"), "title": node.get("title"), "url": node.get("url")}
        for node in blocked_by or []
        if (node.get("state") or "").upper() == "OPEN"
    ]


def _in_scope_blocked_oqs(oq_entries):
    """The `## Open questions` entries whose disposition is `in-scope (blocked)`
    (`skills/_shared/open-question-links.md`). These gate the cut for the same reason an open native
    blocker does; the section is a tracked-dependency registry, not buildable scope."""
    blocked = []
    for entry in oq_entries or []:
        disposition = (entry.get("disposition") or "").strip().lower()
        if disposition.startswith("in-scope"):
            blocked.append(
                {
                    "oq_id": entry.get("oq_id"),
                    "question": entry.get("question"),
                    "disposition": entry.get("disposition"),
                }
            )
    return blocked


def _build_attention(
    target,
    refusals,
    children,
    grounding_docs,
    catalogue_absent,
    open_blockers,
    altitude="story",
    promotion=False,
    promote_requested=False,
    adoption_candidates=None,
):
    """Script-detectable conditions worth surfacing with evidence (architecture.md §4)."""
    attention = []
    for token in refusals:
        if token == REFUSAL_SLICE_TARGET:
            attention.append(
                "target #%s is itself a deliverable slice (its parent is not an epic) — a slice is "
                "never sliced" % target["number"]
            )
        elif token == REFUSAL_QUESTION_TARGET:
            attention.append(
                "target #%s is a question issue — it carries no buildable scope to cut"
                % target["number"]
            )
        elif token == REFUSAL_CLOSED_TARGET:
            attention.append("target #%s is closed — nothing would ever close its slices" % target["number"])
        elif token == REFUSAL_BLOCKED:
            attention.append(
                "target #%s has an open blocker (%s) — slicing against an unanswered question "
                "produces slices the answer may invalidate"
                % (
                    target["number"],
                    ", ".join(
                        ["#%s" % b["number"] for b in open_blockers]
                        or ["an in-scope (blocked) open question"]
                    ),
                )
            )
    if catalogue_absent:
        attention.append(
            "no doc catalogue — the grounding gate will refuse unless the operator names sources; "
            "run /github-pipeline:setup to declare this repo's grounding docs in docs/README.md"
        )
    elif not grounding_docs:
        attention.append("doc catalogue declares no documents — the grounding gate has nothing to read")
    for missing in doc_catalogue.missing_entry_paths(grounding_docs):
        attention.append(
            "doc catalogue names '%s', absent in this checkout — a stale entry, or a doc this branch "
            "has not merged yet" % missing
        )
    if children["count"] and not refusals:
        attention.append(
            "target #%s already has %d %s — resume mode: report them and cut only the remainder, "
            "never re-file" % (target["number"], children["count"], children["kind"])
        )
    if children.get("source") in ("checklist", "mixed"):
        attention.append(
            "epic #%s carries a legacy `## Stories` checklist (stories_source: %s) — it has no native "
            "relation for those entries, so the checklist is still their only record"
            % (target["number"], children["source"])
        )
    if promotion:
        attention.append(
            "promotion requested: #%s is a %s issue that becomes an Epic before the cut — the body "
            "rewrite and label swap ride their own confirm gate, ahead of the cut's write gate"
            % (target["number"], target["type"])
        )
        if children["count"]:
            # Its existing children are slices by construction, so promoting reinterprets them as
            # stories. Loud, and left to the gate: the operator can drop the promotion or accept a
            # hierarchy that no longer reads the way it was filed.
            attention.append(
                "#%s already has %d sub-issue(s), which are deliverable slices by construction — "
                "promoting it to an Epic reinterprets them as stories; confirm that is intended"
                % (target["number"], children["count"])
            )
    elif promote_requested and altitude == "epic":
        attention.append(
            "promotion requested but #%s is already an epic — nothing to promote; cutting at epic "
            "altitude as usual" % target["number"]
        )
    for candidate in adoption_candidates or []:
        if candidate.get("already_parented"):
            attention.append(
                "adoption candidate #%s already has parent #%s — adopting it would move it out of "
                "that parent; confirm before the write" % (candidate["number"], candidate["parent"])
            )
        if (candidate.get("state") or "").upper() == "CLOSED":
            attention.append(
                "adoption candidate #%s is closed — legitimate for already-shipped scope an epic "
                "collects, but it will never contribute open progress to the rollup"
                % candidate["number"]
            )
        if candidate.get("type") == "epic":
            attention.append(
                "adoption candidate #%s is itself an epic — an epic is never another epic's child "
                "(the hierarchy has exactly three levels)" % candidate["number"]
            )
    return attention


def _suggested_playbook(refusals):
    """One playbook (`cut.md`); `fresh` and `resume` differ only in VALUES, never in actions taken
    (CLAUDE.md's "parameterize before you playbook"). A refusal routes to no playbook at all — the
    router renders the matching refusal handoff and stops — so this returns `None`."""
    return None if refusals else "cut.md"


# ---------------------------------------------------------------------------
# Facts-block assembly
# ---------------------------------------------------------------------------


def build_facts(issue, repo, root=".", scratch_dir=None, cwd=None, promote=False, adopt=None):
    """Assemble the slicer's complete facts block and return the envelope dict WITHOUT printing it
    (the testable core, mirroring `prep_researcher.build_facts`). Returns `None` after a
    `needs_decision` envelope has already been emitted on stdout."""
    root = str(Path(root).resolve())
    if scratch_dir is None:
        scratch_dir = "/tmp/gh-slicer-%s" % issue
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    # Every composed core's non-blocking degradations accumulate here and ride out in the envelope's
    # own `notices` (architecture.md §3) — including on the `needs_decision` paths below, since a
    # decision emitted without them would silently drop the fact that this repo declares no
    # grounding docs at all.
    notices = []

    root_sha = _root_sha(root)

    # 1) The target — one round-trip: body, thread, native deps, the parent/sub-issue relation, and
    #    the optional research-dossier marker.
    exit_code, issue_envelope = gh_gather.run(
        str(issue),
        repo,
        marker_prefix=RESEARCH_MARKER,
        scratch_dir=scratch_dir,
        env=None,
        stream=_DiscardStream(),
    )
    if issue_envelope is not None and issue_envelope.get("status") == "needs_decision":
        if _forward_decision(
            issue_envelope["decision"],
            notices=notices + list(issue_envelope.get("notices") or []),
        ):
            return None
    if exit_code != 0:
        sys.stderr.write("prep_slicer: gh_gather on issue #%s failed (exit %d)\n" % (issue, exit_code))
        sys.exit(1)
    notices.extend(issue_envelope.get("notices") or [])

    issue_labels = [label.get("name") for label in issue_envelope.get("labels") or []]
    issue_title = issue_envelope["title"]
    target_type = _detect_type(issue_labels, issue_title)

    # 2) The parent, typed — the one extra gh call, made only when a parent exists.
    parent_node = issue_envelope.get("parent")
    parent = None
    if parent_node:
        parent, parent_decision = _fetch_parent_state(parent_node.get("number"), repo, cwd=cwd)
        if _forward_decision(parent_decision, notices=notices):
            return None

    # 3) Grounding — the consuming repo's declared docs, read at the ambient checkout (the same
    #    vantage as the docs themselves; see the module docstring).
    grounding_docs, catalogue_notices = doc_catalogue.read_catalogue(root)
    notices.extend(catalogue_notices)

    # 4) Blockers — live native state plus the `in-scope (blocked)` OQ entries. Best-effort on the OQ
    #    parse: a malformed `## Open questions` section is not this stage's to repair, and the native
    #    `blocked_by` set already carries the load-bearing half.
    issue_body = _extract_body(issue_envelope)
    try:
        oq_entries = parse.parse_oq_links(issue_body)
    except Exception:  # noqa: BLE001  (best-effort; see above)
        oq_entries = []
    open_blockers = _open_blockers(issue_envelope.get("blocked_by"))
    oq_blocked = _in_scope_blocked_oqs(oq_entries)

    # 5) The altitude, then the child set through the read that altitude's contract defines.
    altitude = _detect_altitude(target_type, promote=promote)
    promotion = bool(promote and target_type != "epic")
    child_attention = []
    if altitude == "epic":
        children, child_attention, children_decision = _build_story_set(
            issue_envelope.get("sub_issues"), issue_body, repo, cwd=cwd
        )
        if _forward_decision(children_decision, notices=notices):
            return None
    else:
        children = _build_slice_set(issue_envelope.get("sub_issues"), issue_envelope["number"])

    # 6) Adoption candidates — only when the router named some.
    adoption_candidates, adoption_notices, adoption_decision = _build_adoption_candidates(
        adopt, repo, cwd=cwd
    )
    notices.extend(n for n in adoption_notices if n not in notices)
    if _forward_decision(adoption_decision, notices=notices):
        return None

    target = {
        "kind": "issue",
        "number": issue_envelope["number"],
        "title": issue_title,
        "state": issue_envelope["state"],
        "labels": issue_labels,
        "type": target_type,
        "parent": parent,
        "blocked_by": open_blockers,
        "deps_available": issue_envelope.get("deps_available"),
        "subissues_available": issue_envelope.get("subissues_available"),
    }

    refusals = _build_refusals(
        target_type, issue_envelope["state"], parent, open_blockers, oq_blocked
    )
    mode = "resume" if children["count"] else "fresh"

    sections = {
        key: value
        for key, value in issue_envelope.items()
        if key.startswith(("issue_body", "thread", "marker_comment"))
    }

    facts = {
        "repo": repo,
        "scratch": scratch_dir,
        "root": {"path": root, "sha": root_sha},
        "target": target,
        "vector": {
            "type": target_type,
            "altitude": altitude,
            "mode": mode,
            "refusals": refusals,
        },
        "suggested_playbook": _suggested_playbook(refusals),
        "promotion": promotion,
        "children": children,
        "adoption_candidates": adoption_candidates,
        "grounding_docs": grounding_docs,
        "research": {"present": bool(issue_envelope.get("marker_comment_present"))},
        "open_questions": oq_blocked,
        "sections": sections,
        "attention": child_attention
        + _build_attention(
            target,
            refusals,
            children,
            grounding_docs,
            DOC_CATALOGUE_ABSENT in notices,
            open_blockers,
            altitude=altitude,
            promotion=promotion,
            promote_requested=bool(promote),
            adoption_candidates=adoption_candidates,
        ),
        "notices": notices,
    }
    return facts


def _extract_body(envelope):
    """The issue body, whether the gather kept it inline or spilled it to the scratch dir (spill
    routing, architecture.md §3). Mirrors `prep_planner._extract_body`."""
    body = envelope.get("issue_body")
    if body is None and envelope.get("issue_body_mode") == "path":
        body = Path(envelope["issue_body_path"]).read_text(encoding="utf-8")
    return body or ""


def main(argv):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "issue",
        nargs="?",
        default=None,
        help="issue number to decompose (into deliverable slices, or into stories when it is an "
        "epic); omitted in --adopt-check mode",
    )
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("--root", default=".", help="project root (the grounding vantage)")
    parser.add_argument(
        "--scratch-dir",
        default=None,
        help="scratch dir for spilled sections + the flow's staged slice bodies "
        "(default: /tmp/gh-slicer-<issue>)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="explicit working directory for the underlying gh calls (cwd discipline: never rely on "
        "ambient cwd)",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="the operator asked for this issue to become an Epic before it is cut (router-passed: "
        "prep cannot read the invocation prose). Forces epic altitude",
    )
    parser.add_argument(
        "--adopt",
        action="append",
        default=[],
        metavar="N",
        help="an already-filed issue to adopt as a child (repeatable, in the order named)",
    )
    parser.add_argument(
        "--adopt-check",
        action="append",
        default=[],
        metavar="N",
        help="one-shot mode: report only these adoption candidates' live state, no facts block "
        "(repeatable; for candidates the operator names mid-session)",
    )
    args = parser.parse_args(argv)

    # One-shot adoption lookup — deliberately before the facts path so a mid-flow check costs one
    # `gh` call per candidate instead of a whole re-gather (the `prep_drafter --oq-query` precedent).
    if args.adopt_check:
        candidates, notices, decision = _build_adoption_candidates(
            args.adopt_check, args.repo, cwd=args.cwd
        )
        if decision is not None:
            emit_needs_decision(decision, notices=notices)
            return 0
        emit_ok(payload={"adoption_candidates": candidates}, notices=notices)
        return 0

    if args.issue is None:
        parser.error("issue is required unless --adopt-check is given")

    facts = build_facts(
        args.issue,
        args.repo,
        root=args.root,
        scratch_dir=args.scratch_dir,
        cwd=args.cwd,
        promote=args.promote,
        adopt=args.adopt,
    )
    if facts is None:
        return 0
    notices = facts.pop("notices", [])
    emit_ok(payload=facts, notices=notices)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
