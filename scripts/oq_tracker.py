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

import parse  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
from pipelib import process  # noqa: E402
from pipelib.decisions import AMBIGUOUS, AUTH_REQUIRED, needs_decision  # noqa: E402

# The `question`-issue label (skills/_shared/question-issue.md) — the tracker search's `--label`
# filter; the ONE name both consumers (planner, drafter) filter on.
QUESTION_LABEL = "question"


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
