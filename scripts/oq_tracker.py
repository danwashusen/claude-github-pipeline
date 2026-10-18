#!/usr/bin/env python3
"""oq_tracker.py — the open-question tracker de-dup search (architecture.md §2, §7;
``skills/_shared/open-question-detection.md`` §Matching; docs/specs/planner.md's frozen "Bug (a)";
docs/implementation.md S14). One deterministic mechanism, one home: "search the tracker before
proposing to file a companion question" — ``gh issue list --repo <owner/repo> --state all --label
question --search "<query>"`` — plus the two ways a prep script drives it: **body-driven**
(scan an issue's own ``## Open questions`` section for entries already recorded ``question: (not
filed)`` and re-search each) and **one-shot** (search a caller-named query directly, for an OQ a
session detects fresh — never yet recorded in any issue body).

**S14 promotion (prep_planner.py's third-copy-avoidance precedent, S12-style).** This module did
not exist before S14. Its three functions were previously :func:`prep_planner._search_question_tracker`
/ :func:`prep_planner._build_open_question_candidates` / :func:`prep_planner.build_oq_query` —
authored for S12 as the planner's own local helpers. S14's `prep_drafter.py` needs the byte-identical
mechanism (its own "search-before-file" companion-question de-dup, `docs/specs/drafter.md` Step 3.5 /
R4) — a second, independently-real consumer of the exact same deterministic query rule, not a
similarly-shaped-but-distinct local `gh` call the way each prep's epic-branch/parent-epic/story-state
helpers remain (those stay local per-prep because their SHAPE only coincidentally rhymes; this one is
the literal same algorithm serving the same shared contract, `open-question-detection.md` §Matching,
named by BOTH `docs/specs/planner.md` and `docs/specs/drafter.md`). Promoted here — the same
verified-byte-identical-refactor bar `config_block.read_block_anywhere` set at S12:
``prep_planner.py`` now calls these three functions instead of carrying its own copies, and
``tests/test_prep_planner.py`` is unmodified and green (only ``prep_planner.build_oq_query`` is kept
as a module-level alias so its one direct-call test line keeps working unchanged).

Every function here is a pure, non-emitting core (architecture.md §2's pure-core pattern, S8 lock):
``(payload_or_list, decision_or_none)`` / ``(payload, notices, decision_or_none)`` — never prints,
never exits. A prep script composes these in-process and forwards the returned ``decision`` itself
(the `_forward_decision` pattern every prep already uses for `gh_gather.run` / `workspace.py` /
`config_block.py` cores).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gh_gather  # noqa: E402  (the Tier-1 tracker read is one gather of the question issue)
import parse  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
from pipelib import process  # noqa: E402
from pipelib.decisions import AMBIGUOUS, AUTH_REQUIRED, needs_decision  # noqa: E402

# The `question`-issue label (skills/_shared/question-issue.md) — the tracker search's `--label`
# filter; the ONE name both consumers (planner, drafter) filter on.
QUESTION_LABEL = "question"

# The question-resolver's durable decision marker — the Tier-1 "resolved" signal beside a CLOSED
# state (skills/_shared/open-question-links.md "Status is the tracker's").
QUESTION_DECISION_MARKER = "<!-- question-decision:v1 -->"


def search_question_tracker(repo, query, cwd=None, env=None):
    """``gh issue list --repo <repo> --state all --label question --search "<query>"`` — the exact
    mechanism ``skills/_shared/open-question-detection.md`` §Matching names. Returns ``(candidates,
    decision_or_none)``; each candidate carries ``number``/``title``/``state``/``labels``.
    """
    result = process.run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--label",
            QUESTION_LABEL,
            "--search",
            query,
            "--json",
            "number,title,state,labels",
        ],
        cwd=cwd,
        env=env,
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
        {
            "number": item.get("number"),
            "title": item.get("title"),
            "state": item.get("state"),
            "labels": [label.get("name") for label in item.get("labels") or []],
        }
        for item in raw
    ], None


def build_open_question_candidates(issue_body, repo, cwd=None, env=None):
    """Parse ``issue_body``'s ``## Open questions`` section (:func:`parse.parse_oq_links`) and, for
    every entry currently recorded ``question: (not filed)``, run the deterministic tracker de-dup
    search (:func:`search_question_tracker`) — the body-driven half of the search-before-file
    contract (docs/specs/planner.md's "Bug (a)"; docs/specs/drafter.md Step 3.5/R4's identical
    reconciliation need). Entries already carrying ``question: #N`` are not re-searched (no
    "(not filed)" claim is being made about them). Returns ``(entries, candidates,
    decision_or_none)`` — ``entries`` is the raw parsed list (every OQ, regardless of question-field
    state); ``candidates`` is only the non-empty tracker-match groups, keyed by ``oq_id``.
    """
    try:
        entries = parse.parse_oq_links(issue_body)
    except parse._OqLinksMalformed as exc:  # noqa: SLF001 — same internal-signal reuse parse.py's
        # own run_oq_links does; forwards the identical AMBIGUOUS decision rather than re-deriving
        # it (parse.py names no dedicated OQ_LINKS_MALFORMED code).
        return None, None, needs_decision(
            AMBIGUOUS,
            summary=exc.reason,
            context={"line_number": exc.line_number, "raw_line": exc.raw_line},
            options=[
                "fix the entry by hand to match the schema in "
                "skills/_shared/open-question-links.md, then re-run"
            ],
        )

    candidates = []
    for entry in entries:
        if entry.get("question") != "(not filed)":
            continue
        query = entry["oq_id"]
        matches, decision = search_question_tracker(repo, query, cwd=cwd, env=env)
        if decision is not None:
            return None, None, decision
        if matches:
            candidates.append({"oq_id": entry["oq_id"], "query": query, "candidates": matches})

    return entries, candidates, None


def build_oq_query(repo, queries, cwd=None, env=None):
    """One-shot tracker de-dup lookup for open-question topics a session **newly detects** — OQs
    that are NOT already recorded in some issue body's ``## Open questions`` section (so
    :func:`build_open_question_candidates` never searched them): the planner's plan-time discovery
    (docs/specs/planner.md's Bug (a) `--oq-query` extension) and the drafter's Step 2/3.5 source-doc
    detection alike (docs/specs/drafter.md — a fresh feedback-only ``new`` session with no issue body
    at all to scan). Runs the identical deterministic
    ``gh issue list --state all --label question --search "<query>"`` search, once per query text.
    Additive: never runs on a caller's own main facts-assembly path. Returns ``(payload, notices,
    decision_or_none)``.
    """
    results = []
    for query in queries:
        matches, decision = search_question_tracker(repo, query, cwd=cwd, env=env)
        if decision is not None:
            return None, [], decision
        results.append({"query": query, "candidates": matches})
    return {"repo": repo, "oq_query_candidates": results}, [], None


# ---------------------------------------------------------------------------
# The open-question gate: the body's `## Open questions` entries joined with each tracker's live
# state. Promoted from prep_resolver.py (where it was `_build_open_question_facts` /
# `_oq_tracker_status`) when the coordinator became its second consumer — the resolver's
# semantics are the canonical ones, so both callers share this one copy.
# ---------------------------------------------------------------------------


class _DiscardStream:
    """Write-sink for `gh_gather.run(stream=...)` — the same two-method shape every prep keeps."""

    def write(self, _data):
        return None

    def flush(self):
        return None


def tracker_status(repo, question_number, scratch_dir, cwd=None):
    """Tier 1 tracker read for one `question` issue number (skills/_shared/open-question-links.md
    "Status is the tracker's"): resolved iff `state == CLOSED` OR a `<!-- question-decision:v1
    -->` comment is present. Composes `gh_gather.run` in-process (per architecture.md §2), routing
    its own envelope to a discard sink (the S8-retro accepted-reference emit-through-a-stream
    pattern — see `prep_evaluator._DiscardStream`). Returns `(status_dict, decision_or_none)`.
    """
    exit_code, envelope = gh_gather.run(
        str(question_number),
        repo,
        marker_prefix=QUESTION_DECISION_MARKER,
        scratch_dir=scratch_dir,
        env=None,
        stream=_DiscardStream(),
    )
    if envelope is not None and envelope.get("status") == "needs_decision":
        return None, envelope["decision"]
    if exit_code != 0:
        sys.stderr.write(
            "oq_tracker: gh_gather on question tracker #%s failed (exit %d)\n"
            % (question_number, exit_code)
        )
        sys.exit(1)
    resolved = envelope.get("state") == "CLOSED" or bool(envelope.get("marker_comment_present"))
    return {
        "number": question_number,
        "state": envelope.get("state"),
        "decision_recorded": bool(envelope.get("marker_comment_present")),
        "resolved": resolved,
    }, None


def build_open_question_facts(issue_body, repo, blocked_by, scratch_dir, cwd=None):
    """Parse `## Open questions` (parse.parse_oq_links) and join each entry with its tracker's
    live state + the issue's native `blocked_by` set (docs/specs/resolver.md step 3's "Native
    `blocked by` is a hard gate"; skills/_shared/open-question-links.md). Returns
    `(open_questions_list, blocked_bool, decision_or_none)`.

    The hard-gate fact: any `in-scope (blocked)` entry whose tracker question is still open with
    no Tier-1 resolution -> `blocked: true`. An entry whose `question:` field is `(not filed)` has
    no tracker to join against and is surfaced with `status: unresolved-ambiguous` — Tier 2 (the
    ambiguous-thread judgment read) is the router's job, never prep's (spec step 3 / open-question-
    links.md's tiered read).
    """
    try:
        entries = parse.parse_oq_links(issue_body)
    except parse._OqLinksMalformed as exc:  # noqa: SLF001 — same internal-signal reuse parse.py's
        # own run_oq_links does; prep forwards the identical AMBIGUOUS decision rather than
        # re-deriving it (parse.py names no dedicated OQ_LINKS_MALFORMED code — see parse.py's
        # `_OqLinksMalformed` docstring).
        return None, None, needs_decision(
            AMBIGUOUS,
            summary=exc.reason,
            context={"line_number": exc.line_number, "raw_line": exc.raw_line},
            options=[
                "fix the entry by hand to match the schema in "
                "skills/_shared/open-question-links.md, then re-run"
            ],
        )

    open_blocker_numbers = {
        blocker.get("number")
        for blocker in (blocked_by or [])
        if (blocker.get("state") or "").upper() == "OPEN"
    }

    joined = []
    blocked = False
    for entry in entries:
        joined_entry = dict(entry)
        question_field = entry.get("question")
        if question_field == "(not filed)":
            joined_entry["tracker"] = None
            joined_entry["status"] = "unresolved-ambiguous"
            joined.append(joined_entry)
            continue

        question_number = int(question_field.lstrip("#"))
        status, decision = tracker_status(repo, question_number, scratch_dir, cwd=cwd)
        if decision is not None:
            return None, None, decision
        joined_entry["tracker"] = status
        joined_entry["native_blocked"] = question_number in open_blocker_numbers

        if entry.get("disposition") == "in-scope (blocked)" and not status["resolved"]:
            joined_entry["status"] = "blocked"
            blocked = True
        else:
            joined_entry["status"] = "clear"
        joined.append(joined_entry)

    return joined, blocked, None
