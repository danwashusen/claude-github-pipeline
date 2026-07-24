#!/usr/bin/env python3
"""prep_resolver.py — the resolver's complete facts block in one call (architecture.md §4;
docs/implementation.md S9; docs/specs/resolver.md). v1's ~130 lines of prompt-side state
assembly — state-vector derivation, epic-branch discovery, branch naming/collision suffixing,
phase/DoD/open-question parsing, and workspace setup — collapse into ONE JSON envelope on stdout,
so the resolver session's startup is one Python process, never a subprocess chain.

Composition (architecture.md §2 "compose the executors in-process"; §1 "the only external
processes any script may spawn are git/gh")::

    gh_gather.run(..., stream=)                    -- the target issue's body/thread/plan-marker/
                                                       native deps envelope (one round-trip)
    gh_gather.run(..., stream=)                    -- per open-question tracker issue, for the
                                                       Tier 1 status read (state + decision marker)
    workspace._build_root_status / _build_ensure_work / _build_ensure_read
                                                    -- root freshness, the work worktree, and (for
                                                       Epic/Story) the audit read workspace
    parse.parse_phases / parse.parse_dod_bullets / parse.parse_oq_links
                                                    -- the plan's ## Phases, the issue's
                                                       ## Definition of done, and its
                                                       ## Open questions section
    config_block._read_lines_or_empty / _scan_marker
                                                    -- the three resolver-side gate-config blocks
                                                       (+ pr-evaluator fallback chain), read at the
                                                       root main SHA

Every executor composed here exposes a **pure, non-emitting core** — ``build_*(...) -> (payload,
notices, decision|None)`` (docs/specs/baseline.md §5, the S8 pattern lock). This prep calls those
cores **directly** and forwards each core's returned ``decision`` verbatim
(:func:`_forward_decision`), emitting exactly one envelope of its own. No ``redirect_stdout`` /
``io.StringIO`` capture of another script's stdout is used anywhere in this module — that bridge
was S6-pilot-only and is retired for every prep from S9 on (docs/specs/baseline.md §5's "Rule for
S9+").

`git ls-remote --heads origin <pattern>` (epic-branch discovery, story parent-epic branch lookup,
and branch-collision suffixing), `gh issue list --label epic ...` (story parent-epic search), and
`gh pr list --state closed ...` (the closed-PR half of the prior-PR state table) have no existing
executor core — architecture.md §1 permits any script to spawn `git`/`gh` directly via
`pipelib.process.run`, so this module calls them directly (:func:`_list_remote_branches`,
:func:`_search_parent_epic`, :func:`_search_closed_prs`), the same way `prep_evaluator.py` calls
`gh api repos/<owner>/<repo>` directly for repo-merge-config (no existing executor covers it
either).

Usage::

    prep_resolver.py <issue-number> <owner/repo> [--root PATH] [--scratch-dir PATH] [--refresh]

``--root`` defaults to ``.`` (the project root — architecture.md §6's read-only trust vantage).
``--scratch-dir`` defaults to ``/tmp/gh-resolver-<issue-number>`` (CLAUDE.md's ``/tmp/gh-<skill>-
<N>/`` convention) when omitted. ``--refresh`` re-derives the volatile facts (issue/PR state,
branch discovery) without re-running ``ensure --work``/``ensure --read``'s setup hooks or
re-reading the three gate-config blocks — mirroring ``prep_evaluator.py``'s ``--refresh``
contract (architecture.md §4: "prep supports --refresh and is re-run at the points where
currency matters").

Exit codes (architecture.md §3): 0 with the facts-block envelope present (``status`` is ``"ok"``
or ``"needs_decision"``); 2 on a usage error (no envelope). Any other non-zero is an unclassified
hard `gh`/`git` failure surfaced by a composed executor — stderr carries the faithful error.

``vector.mode`` is a THREE-value closed set — ``"continue"`` / ``"gated"`` / ``"fresh"`` — not the
two-value fresh/continue an earlier revision of this module used. ``"gated"`` is a deliberate
distinct value (never an overload of ``"fresh"``): docs/specs/resolver.md's prior-PR state table
("Fresh/continue mode from the prior-PR state table") makes an open PR by ANOTHER author (active
or stale) — and a DRAFT PR by another author, which that table's Draft row scopes to "the same
author," not any draft — operator-gated
via `AskUserQuestion` with NO worktree until the operator decides. This prep therefore reports
``mode: "gated"`` plus a ``vector.gate`` fact block (``reason``, the exact `AskUserQuestion`
``header``/``options`` S10 renders verbatim, and the driving ``prior_pr`` fact) and does **not**
ensure a work workspace or fabricate a branch name for that row — S10's router must render the
gate on ``mode == "gated"`` and must never fall through to the fresh-branch or continue-on-existing
flow. Prep still emits ``status: "ok"`` on a gated row (this is a flow gate, not an assembly
failure — identical reasoning to the ``open_questions_gate`` hard gate below). A **read** workspace
(the audit ref) may still be assembled on a gated row since it never touches the other author's
branch; only the WORK workspace is withheld.

``audit_ref`` is always a BARE branch name (``"main"`` / ``"epic/42-journal"``), never
`origin/`-prefixed — see :func:`_audit_ref`'s docstring. The origin-prefixed form (what a read
workspace actually checked out) rides on ``read_workspaces.audit.ref`` instead once that workspace
is ensured; a consumer must not assume one prefixing convention for both fields.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_block  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
import gh_gather  # noqa: E402
import parse  # noqa: E402
import workspace  # noqa: E402
from pipelib import process  # noqa: E402
from pipelib.decisions import AMBIGUOUS, PLAN_MISSING, needs_decision  # noqa: E402
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR, emit_needs_decision, emit_ok  # noqa: E402

# The implementation-plan marker (skills/planner/references/plan-schema.md;
# docs/specs/resolver.md "Artifacts read") — the plan comment is always the first marker_prefix
# lookup GATHER_ISSUE performs, exactly as v1's step 2 documents.
PLAN_MARKER = "<!-- implementation-plan:v1 -->"

# The question-decision marker (skills/_shared/open-question-links.md "Status is the tracker's",
# Tier 1) — read per open-question tracker issue to detect a recorded operator decision.
QUESTION_DECISION_MARKER = "<!-- question-decision:v1 -->"

# The three resolver-side gate-config marker names (docs/specs/resolver.md §P3.1), read at the
# root `main` SHA (architecture.md §6/§12: "gate config is pinned to trust ... never from a PR
# head"). Each has a pr-evaluator-side fallback per the spec's documented fallback chain.
_FAST_CHECKS_MARKER = "issue-resolver-fast-checks"
_TEST_TARGET_MARKER = "issue-resolver-test-target"
_CANONICAL_SUITE_MARKER = "issue-resolver-canonical-suite"
_FALLBACK_STATIC_CHECKS_MARKER = "pr-evaluator-static-checks"
_FALLBACK_HEALTH_CHECKS_MARKER = "pr-evaluator-health-checks"
_FALLBACK_TEST_TARGET_MARKER = "pr-evaluator-test-target"

# Candidate config files, in priority order — same discovery list prep_evaluator.py /
# workspace.py's `_candidate_hook_files` already use (COMMANDS.md, CLAUDE.md, then one level of
# `@`-include from either). `config_block.read_block_anywhere` (S12 promotion) defaults to this
# exact tuple, so this module no longer carries its own copy of the discovery loop — see
# "Gate-config discovery" below.

ROOT_MAIN_BRANCH = "main"

# State-vector `type` detection (docs/specs/resolver.md "State-vector derivation: labels -> type";
# the spec's "Epic-branch discovery" row): case-insensitive `epic`/`story` label match, OR a
# title `Epic:` prefix (case-insensitive) for the epic arm — the fresh-slug derivation uses the
# identical prefix test, so the type-detection prefix check mirrors it exactly.
_EPIC_TITLE_PREFIX_RE = re.compile(r"^\s*epic\s*:", re.IGNORECASE)

# Epic branch pattern: `epic/<N>-<slug>` (docs/specs/resolver.md "Epic-branch discovery").
_EPIC_BRANCH_LS_REMOTE_PATTERN = "epic/%s-*"
_EPIC_BRANCH_NAME_RE = re.compile(r"^epic/(\d+)-(.+)$")

# Branch-collision suffixing: `<issue>-<slug>` optionally followed by `-v<N>`
# (docs/specs/resolver.md's "Branch-collision suffixing (`-vN`)" row; unsuffixed counts as v1).
_BRANCH_VERSION_SUFFIX_RE = re.compile(r"^-v(\d+)$")


# ---------------------------------------------------------------------------
# git ls-remote — no existing executor core covers this query shape (architecture.md §1 permits
# any script to spawn git/gh directly via pipelib.process.run; prep_evaluator.py's repo-merge-
# config gh call is the precedent for "a prep-owned direct call when no executor covers it").
# ---------------------------------------------------------------------------


def _list_remote_branches(root, pattern):
    """`git ls-remote --heads origin <pattern>` -> sorted list of bare branch names (the
    `refs/heads/` prefix stripped). Returns `(names, decision_or_none)` — a hard git failure other
    than "no matches" still `sys.exit(1)`s with faithful stderr (§3, unchanged); "no matches" is
    `git ls-remote`'s own exit 0 with empty stdout, not a failure.
    """
    result = process.run(["git", "ls-remote", "--heads", "origin", pattern], cwd=str(root))
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    names = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        ref = parts[-1]
        if ref.startswith("refs/heads/"):
            names.append(ref[len("refs/heads/") :])
    return sorted(names), None


# ---------------------------------------------------------------------------
# State-vector: type detection, prior-PR-row -> mode (docs/specs/resolver.md's 7-row table)
# ---------------------------------------------------------------------------


def _detect_type(labels, title):
    """Case-insensitive `epic`/`story` label match, or a title `Epic:` prefix (docs/specs/
    resolver.md "State-vector derivation: labels -> type"). `epic` takes precedence over `story`
    if (pathologically) both labels are present, matching the spec's listed priority order.
    """
    lowered_labels = {(label or "").strip().lower() for label in labels or []}
    if "epic" in lowered_labels or _EPIC_TITLE_PREFIX_RE.match(title or ""):
        return "epic"
    if "story" in lowered_labels:
        return "story"
    return "standard"


# The v1 step-5 prior-PR state table (docs/specs/resolver.md "Fresh/continue mode from the
# prior-PR state table" — its seven rows), carried as the row name -> mode mapping.
#
# `mode` is one of three values — NOT the two-value fresh/continue this prep started with:
#   - `continue` — a worktree is safe to ensure NOW, no operator input needed first:
#     open-pr-yours, and draft-by-the-SAME-author ("Treat the same as an open PR by the same
#     author" — the table's "Draft PR" row is scoped to your own draft, not any draft).
#   - `gated` — an operator decision is required BEFORE any work-workspace side effect:
#     open-pr-other-active, open-pr-other-stale, and draft-by-ANOTHER-author (the table's "Open PR
#     by someone else" rows, both gated via AskUserQuestion — "Review it"/"Leave a comment"/"Wait"
#     for active, "Take it over"/"Start fresh" for stale; a foreign draft is still claimed work
#     someone else owns, so it gates the same way, never silently treated as available to continue
#     on). `mode: "gated"` is a deliberate THIRD value, not an overload of `fresh` — S10's router
#     must render the operator gate on `gated` and must NOT fall through to the fresh-branch flow,
#     which is exactly the failure `fresh` would silently invite (a bare boolean would also lose
#     the case distinction the router needs to pick which AskUserQuestion card to render — active
#     vs stale vs foreign-draft each has its own header/options in the spec's "Operator gates"
#     table, so `prior_pr_row`
#     plus `vector.gate` below carry that distinction, not `mode` alone).
#   - `fresh` — no usable prior work exists to continue or gate on: no-prior-pr, and (mirroring
#     v1's own "proceed as the no-prior-PR case") closed-not-resolved. closed-resolved never
#     reaches mode derivation as a real branch decision — the issue is already closed — but is
#     still reported as `fresh` for schema uniformity (`comment_only`/`suggested_playbook` already
#     drive the actual behavior for a closed issue via the router, not `mode`).
#
# Assembly still emits `status: "ok"` on a `gated` row — this is a flow gate S10's router must
# raise, not an assembly failure this prep should short-circuit on (identical reasoning to the
# `open_questions_gate` hard gate below: prep's job is to make the gate an unmissable FACT, never
# to pre-empt it with a side effect).
PRIOR_PR_ROW_OPEN_YOURS = "open-pr-yours"
PRIOR_PR_ROW_OPEN_OTHER_ACTIVE = "open-pr-other-active"
PRIOR_PR_ROW_OPEN_OTHER_STALE = "open-pr-other-stale"
PRIOR_PR_ROW_DRAFT = "draft"
PRIOR_PR_ROW_CLOSED_RESOLVED = "closed-resolved"
PRIOR_PR_ROW_CLOSED_NOT_RESOLVED = "closed-not-resolved"
PRIOR_PR_ROW_NONE = "no-prior-pr"

MODE_CONTINUE = "continue"
MODE_GATED = "gated"
MODE_FRESH = "fresh"

_CONTINUE_ROWS = frozenset({PRIOR_PR_ROW_OPEN_YOURS, PRIOR_PR_ROW_DRAFT})
_GATED_ROWS = frozenset({PRIOR_PR_ROW_OPEN_OTHER_ACTIVE, PRIOR_PR_ROW_OPEN_OTHER_STALE})

# Per-gated-row AskUserQuestion shape S10's router renders (the exact headers/options in
# docs/specs/resolver.md "Operator gates"),
# carried as a fact so the router never re-derives which card goes with which row. A foreign draft
# reuses whichever of the two "someone else" rows its activity classifies as (see
# _classify_prior_pr_row) — there is no third, draft-specific card in v1.
_GATE_CARDS = {
    PRIOR_PR_ROW_OPEN_OTHER_ACTIVE: {
        "header": "Open PR",
        "options": ["Review it", "Leave a comment", "Wait"],
    },
    PRIOR_PR_ROW_OPEN_OTHER_STALE: {
        "header": "Stale PR",
        "options": ["Take it over", "Start fresh"],
    },
}

# "Stale" activity threshold in days. The spec row's text is deliberately unquantified ("no recent
# activity ... for a long time") — this is a CHOSEN deterministic default this prep needs in order
# to classify open-other PRs at all, not a value derived from any other doc in this repo (no
# retry-ladder/epic-flow inactivity window exists at this order of magnitude; an earlier revision
# of this comment claimed one and was wrong). Surfaced as `prior_pr.stale_cutoff_days` (see
# _classify_prior_pr_row) so the operator/router can see the exact driver rather than trust an
# opaque classification. With the mode fix above, active vs stale changes ONLY which gate card is
# shown (_GATE_CARDS) — both rows are `mode: "gated"`; the cutoff no longer decides
# continue-vs-not, only the gate's framing.
_STALE_ACTIVITY_DAYS = 14


def _search_closed_prs(repo, issue_number, cwd=None):
    """Targeted closed/merged-PR search referencing this issue (docs/specs/resolver.md step-5
    table's two "closed" rows; mirrors the spec's own predecessor-PR-detection search convention:
    `gh pr list --state closed --search "<N> in:body"`). Returns `(prs, decision_or_none)`; each
    PR dict carries `number`/`state`/`mergedAt` (`state == "MERGED"` classifies resolved, since a
    merged PR referencing the issue closed it — v1's "closed PR that resolved the issue" row).

    The raw search result is filtered through `gh_gather.references_issue` before being returned
    (a fix authorized/scoped alongside S12: `--search "<N> in:body"` is a GitHub full-text search,
    not a literal-string containment check — live evidence against the sandbox repo showed it
    returning PRs whose body merely contains the digit `<N>` in unrelated prose, e.g. "Phase 2",
    never referencing issue `#<N>` at all; see `gh_gather.py`'s module docstring "Open-PR search
    false-positive fix" for the full evidence and `docs/specs/resolver.md`'s "Known bugs/gaps" for
    the newly-discovered v1-inherited defect this closes).
    """
    result = process.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "closed",
            "--search",
            "%s in:body" % issue_number,
            "--json",
            "number,title,author,state,mergedAt,headRefName,url,updatedAt,body,closingIssuesReferences",
        ],
        cwd=cwd,
    )
    if result.auth_required:
        from pipelib.decisions import AUTH_REQUIRED

        return None, needs_decision(
            AUTH_REQUIRED,
            summary="gh authentication required",
            context={"stderr": result.stderr, "returncode": result.returncode},
            options=["run: gh auth login"],
        )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    return gh_gather._filter_and_strip_reference_fields(json.loads(result.stdout), issue_number), None


def _classify_prior_pr_row(open_prs, current_user, closed_prs, issue_state):
    """Classify the issue's prior-PR state into exactly one of the 7 named rows, returning
    ``(row_name, prior_pr_fact_or_none)``. ``open_prs`` is `gh_gather`'s `open_prs` list (from the
    `gh pr list ... "<N> in:body"` search); ``closed_prs`` is :func:`_search_closed_prs`'s result
    (only consulted when no open PR exists); ``issue_state`` (`OPEN`/`CLOSED`) disambiguates the
    two closed-PR rows exactly as docs/specs/resolver.md's table does ("closed PR that resolved
    the issue" implies the issue itself is closed; a merged PR against a still-open issue is the
    partial-fix/abandoned case).

    Authorship is decided BEFORE draft state (the ordering bug this function was previously
    written with, fixed here): the prior-PR table's "Draft PR" row explicitly scopes to "the same
    author" — it is not a draft-vs-ready split independent of who owns the PR. So an open PR by
    someone else classifies via :func:`_classify_open_other_activity` regardless of its draft
    state; only YOUR own open PR can ever land on `open-pr-yours` or `draft`.
    """
    if open_prs:
        # Prefer a PR by the current user (matches v1's per-row priority: "yours" outranks
        # "other's" when the caller happens to own more than one referencing PR).
        yours = [pr for pr in open_prs if (pr.get("author") or {}).get("login") == current_user]
        chosen = yours[0] if yours else open_prs[0]
        if yours:
            row = PRIOR_PR_ROW_DRAFT if chosen.get("isDraft") else PRIOR_PR_ROW_OPEN_YOURS
        else:
            # Someone else's PR — draft or not, it's still claimed work someone else owns
            # ("Drafts are still claimed work" — that rule is about protecting
            # ANY author's draft, not just your own; a foreign draft therefore gates exactly like
            # a foreign ready PR, classified by the same activity check).
            row = _classify_open_other_activity(chosen)
        fact = {
            "number": chosen.get("number"),
            "author": (chosen.get("author") or {}).get("login"),
            "isDraft": chosen.get("isDraft"),
            "headRefName": chosen.get("headRefName"),
            "updatedAt": chosen.get("updatedAt"),
            "url": chosen.get("url"),
            "stale_cutoff_days": _STALE_ACTIVITY_DAYS,
        }
        return row, fact

    if closed_prs:
        chosen = closed_prs[0]
        merged = (chosen.get("state") or "").upper() == "MERGED" or bool(chosen.get("mergedAt"))
        # "Resolved" per the spec's row split: a merged PR against an issue GitHub itself now
        # shows closed is the "closed PR that resolved the issue" row; anything else (merged PR
        # but the issue is still open, or a closed-without-merge/abandoned PR) is the
        # "closed/merged PR that did NOT resolve the issue" row (partial fix, reverted, abandoned).
        resolved = merged and (issue_state or "").upper() == "CLOSED"
        row = PRIOR_PR_ROW_CLOSED_RESOLVED if resolved else PRIOR_PR_ROW_CLOSED_NOT_RESOLVED
        fact = {
            "number": chosen.get("number"),
            "author": (chosen.get("author") or {}).get("login"),
            "headRefName": chosen.get("headRefName"),
            "merged": merged,
            "resolved": resolved,
            "url": chosen.get("url"),
        }
        return row, fact

    return PRIOR_PR_ROW_NONE, None


def _classify_open_other_activity(pr):
    """Active vs stale for an open PR authored by someone else, including a foreign draft
    (docs/specs/resolver.md step-5 table's two "someone else" rows) — `updatedAt` age vs
    :data:`_STALE_ACTIVITY_DAYS` (a chosen default, not a derived one — see that constant's
    docstring). Missing `updatedAt` defaults to "active" (never silently downgrade a PR to stale
    on absent data). Both outcomes are `mode: "gated"` (see `_GATED_ROWS`) — this only decides
    WHICH `AskUserQuestion` card the router shows (`_GATE_CARDS`), never whether the row gates."""
    import datetime

    updated_at = pr.get("updatedAt")
    if not updated_at:
        return PRIOR_PR_ROW_OPEN_OTHER_ACTIVE
    try:
        updated = datetime.datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        return PRIOR_PR_ROW_OPEN_OTHER_ACTIVE
    age = datetime.datetime.now(datetime.timezone.utc) - updated
    if age.days >= _STALE_ACTIVITY_DAYS:
        return PRIOR_PR_ROW_OPEN_OTHER_STALE
    return PRIOR_PR_ROW_OPEN_OTHER_ACTIVE


# ---------------------------------------------------------------------------
# Fresh-slug computation (bootstrap only) — the spec's 6-step derivation, verbatim.
# ---------------------------------------------------------------------------

_SLUG_STRIP_EPIC_PREFIX_RE = re.compile(r"^\s*epic\s*:\s*", re.IGNORECASE)
_SLUG_NON_ALNUM_RUN_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MAX_LENGTH = 50


def compute_fresh_slug(title):
    """The 6-step epic-title -> slug derivation (docs/specs/resolver.md "Fresh-slug computation
    (bootstrap only)"):
    strip an `Epic:` prefix, lowercase, replace non-`[a-z0-9]` runs with `-`, strip leading/
    trailing `-`, truncate to <=50 chars on a `-` boundary. Used ONLY on the bootstrap path (zero
    `git ls-remote` matches) — an existing branch's slug is always taken from the discovered
    branch name verbatim, never recomputed (the spec's "Discover the epic branch slug by prefix;
    only compute fresh on bootstrap" invariant).
    """
    stripped = _SLUG_STRIP_EPIC_PREFIX_RE.sub("", title or "").strip()
    lowered = stripped.lower()
    collapsed = _SLUG_NON_ALNUM_RUN_RE.sub("-", lowered)
    trimmed = collapsed.strip("-")
    if len(trimmed) <= _SLUG_MAX_LENGTH:
        return trimmed
    truncated = trimmed[:_SLUG_MAX_LENGTH]
    # "if the truncation would land mid-word ... keep truncating back to the previous '-'."
    if len(trimmed) > _SLUG_MAX_LENGTH and trimmed[_SLUG_MAX_LENGTH] not in ("-",):
        last_dash = truncated.rfind("-")
        if last_dash != -1:
            truncated = truncated[:last_dash]
    return truncated.rstrip("-")


# ---------------------------------------------------------------------------
# Epic-branch discovery (zero/one/multiple) + story parent-epic search
# ---------------------------------------------------------------------------


def _discover_epic_branch(root, epic_number, epic_title):
    """Discover `epic/<epic_number>-*` on origin (docs/specs/resolver.md "Epic-branch discovery").
    Returns `(facts_dict, decision_or_none)`:
      - zero matches -> `{"match_count": 0, "branch": None, "bootstrap_slug": <computed>}`.
      - one match -> `{"match_count": 1, "branch": <name>}`.
      - multiple matches -> `(None, AMBIGUOUS decision)` (context lists every candidate).
    """
    matches, _ = _list_remote_branches(root, _EPIC_BRANCH_LS_REMOTE_PATTERN % epic_number)
    if len(matches) == 0:
        return {
            "match_count": 0,
            "branch": None,
            "bootstrap_slug": compute_fresh_slug(epic_title),
        }, None
    if len(matches) == 1:
        return {"match_count": 1, "branch": matches[0]}, None
    return None, needs_decision(
        AMBIGUOUS,
        summary="%d candidate epic branches match 'epic/%s-*' on origin — expected at most one"
        % (len(matches), epic_number),
        context={"epic_number": epic_number, "candidates": matches},
        options=[
            "pick the canonical branch and re-run with it recorded",
            "delete or rename the orphaned/duplicate branch, then re-run",
        ],
    )


def _search_parent_epic(repo, story_number, cwd=None):
    """Story parent-epic search (docs/specs/resolver.md "Epic-branch discovery"; the "gh issue list --label epic
    --state all --search '#<N> in:body'"). Returns `(matches, decision_or_none)` where `matches`
    is the `gh issue list` result list, filtered (empty on zero genuine matches).

    Filtered through `gh_gather.references_issue` — live evidence (see `gh_gather.py`'s module
    docstring) showed `--search "#<N> in:body"` (the hash-prefixed form this call already uses)
    returns the SAME false-positive set as the bare-digit form on a `gh pr list` search; GitHub's
    server-side full-text search does not use `#` as an anchor either way. This repo's current
    sandbox data never manifested a false positive here only because it has a single epic-labelled
    issue whose body happens to contain no stray digits — the underlying exposure is identical to
    the PR searches, so the same client-side filter applies here too (docs/specs/resolver.md's
    "Known bugs/gaps").
    """
    result = process.run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            "epic",
            "--state",
            "all",
            "--search",
            "#%s in:body" % story_number,
            "--json",
            "number,title,state,body",
        ],
        cwd=cwd,
    )
    if result.auth_required:
        from pipelib.decisions import AUTH_REQUIRED

        return None, needs_decision(
            AUTH_REQUIRED,
            summary="gh authentication required",
            context={"stderr": result.stderr, "returncode": result.returncode},
            options=["run: gh auth login"],
        )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    matches = gh_gather._filter_and_strip_reference_fields(json.loads(result.stdout), story_number)
    if len(matches) <= 1:
        return matches, None
    return None, needs_decision(
        AMBIGUOUS,
        summary="%d candidate parent epics reference story #%s — expected at most one"
        % (len(matches), story_number),
        context={"story_number": story_number, "candidates": matches},
        options=[
            "pick the canonical parent epic and re-run",
            "correct the sibling issue bodies so only one epic references this story",
        ],
    )


# ---------------------------------------------------------------------------
# Branch naming + collision suffixing
# ---------------------------------------------------------------------------


def compute_branch_name(root, issue_number, slug):
    """`<issue>-<slug>` with collision suffixing (docs/specs/resolver.md "Branch-collision
    suffixing"; the spec's branch-creation convention): inspect
    `git ls-remote --heads origin "<issue>-<slug>*"`, take the highest existing `-vN` suffix + 1
    (an unsuffixed match counts as v1 — the first collision yields `-v2`). Returns
    `(branch_name, collided_with_or_none)`.
    """
    base = "%s-%s" % (issue_number, slug)
    matches, _ = _list_remote_branches(root, base + "*")
    # Only exact-base or exact-base+`-vN` count as a real collision — a match that merely starts
    # with the same prefix by coincidence (e.g. "<N>-<slug>-extra-words") is not a versioned
    # sibling of this branch and must not perturb the version count.
    relevant = [m for m in matches if m == base or _BRANCH_VERSION_SUFFIX_RE.match(m[len(base) :])]
    if not relevant:
        return base, None
    highest = 1
    for match in relevant:
        if match == base:
            highest = max(highest, 1)
            continue
        suffix_match = _BRANCH_VERSION_SUFFIX_RE.match(match[len(base) :])
        if suffix_match:
            highest = max(highest, int(suffix_match.group(1)))
    return "%s-v%d" % (base, highest + 1), sorted(relevant)


# ---------------------------------------------------------------------------
# Gate-config discovery at the root `main` SHA (mirrors prep_evaluator's _read_gate_config shape,
# resolver-side marker names + fallback chain per docs/specs/resolver.md §P3.1).
# ---------------------------------------------------------------------------


def _read_gate_config(root):
    """Read the resolver's three gate-config blocks, applying the spec's fallback chain
    (docs/specs/resolver.md §P3.1): `issue-resolver-fast-checks` -> (no fallback; static checks
    only); `issue-resolver-test-target` -> `pr-evaluator-test-target`; `issue-resolver-canonical-
    suite` -> `pr-evaluator-test-target`'s full-suite-command (approximated here as its raw text,
    since prep surfaces facts, not judgment about which sub-line is the full-suite command —
    the resolver playbook parses the fallback block's prose itself, matching v1's own "read
    it as natural language; don't try to parse it" instruction for `issue-resolver-test-target`).
    Absent both `issue-resolver-fast-checks` and `pr-evaluator-static-checks`, falls back once
    more to the legacy `pr-evaluator-health-checks` block (docs/specs/resolver.md "Fallback config
    blocks"'s documented worst-case
    chain). Returns `(config_dict_without_sha, notices)`.
    """
    notices = []

    fast_present, fast_lines, fast_source = config_block.read_block_anywhere(
        root, _FAST_CHECKS_MARKER
    )
    if not fast_present:
        fast_present, fast_lines, fast_source = config_block.read_block_anywhere(
            root, _FALLBACK_STATIC_CHECKS_MARKER
        )
        if fast_present:
            notices.append("FAST_CHECKS_FALLBACK_STATIC_CHECKS")
    if not fast_present:
        fast_present, fast_lines, fast_source = config_block.read_block_anywhere(
            root, _FALLBACK_HEALTH_CHECKS_MARKER
        )
        if fast_present:
            notices.append("FAST_CHECKS_FALLBACK_LEGACY_HEALTH_CHECKS")

    test_target_present, test_target_lines, test_target_source = config_block.read_block_anywhere(
        root, _TEST_TARGET_MARKER
    )
    if not test_target_present:
        test_target_present, test_target_lines, test_target_source = config_block.read_block_anywhere(
            root, _FALLBACK_TEST_TARGET_MARKER
        )
        if test_target_present:
            notices.append("TEST_TARGET_FALLBACK_PR_EVALUATOR")

    canonical_present, canonical_lines, canonical_source = config_block.read_block_anywhere(
        root, _CANONICAL_SUITE_MARKER
    )
    if not canonical_present:
        # Fallback chain per docs/specs/resolver.md "Fallback config blocks":
        # pr-evaluator-test-target's full-suite-command line —
        # prep surfaces the raw fallback block for the playbook to extract the labelled line from
        # (this module does not parse `full-suite-command:` out of free-form prose; see the
        # function docstring).
        canonical_present, canonical_lines, canonical_source = config_block.read_block_anywhere(
            root, _FALLBACK_TEST_TARGET_MARKER
        )
        if canonical_present:
            notices.append("CANONICAL_SUITE_FALLBACK_PR_EVALUATOR_TEST_TARGET")

    config = {
        "static_checks": _parse_backtick_command_list(fast_lines) if fast_present else [],
        "static_checks_present": fast_present,
        "static_checks_source": fast_source,
        "test_target_present": test_target_present,
        "test_target_raw": "\n".join(test_target_lines) if test_target_present else None,
        "test_target_source": test_target_source,
        "canonical_suite_present": canonical_present,
        "canonical_suite_raw": "\n".join(canonical_lines) if canonical_present else None,
        "canonical_suite_source": canonical_source,
    }
    return config, notices


_COMMAND_LIST_ITEM_RE = re.compile(r"^\s*-\s*`([^`]*)`")


def _parse_backtick_command_list(interior_lines):
    items = []
    for line in interior_lines:
        match = _COMMAND_LIST_ITEM_RE.match(line)
        if match:
            items.append(match.group(1))
    return items


# ---------------------------------------------------------------------------
# Open-question facts: parse.parse_oq_links joined with tracker state + native blocked_by.
# ---------------------------------------------------------------------------


def _oq_tracker_status(repo, question_number, scratch_dir, cwd=None):
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
            "prep_resolver: gh_gather on question tracker #%s failed (exit %d)\n"
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


class _DiscardStream:
    """A minimal write-sink for `gh_gather.run(stream=...)` — the one remaining executor prep
    composes that emits-through-a-`stream=` while ALSO returning `(exit, envelope)`. Identical in
    shape to `prep_evaluator._DiscardStream`; restated locally rather than imported across module
    boundaries for a two-method sink (architecture.md §2's composition guidance is about calling
    another script's *pure core* directly, not about sharing tiny private test-doubles)."""

    def write(self, _data):
        return None

    def flush(self):
        return None


def _build_open_question_facts(issue_body, repo, blocked_by, scratch_dir, cwd=None):
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
        tracker_status, decision = _oq_tracker_status(repo, question_number, scratch_dir, cwd=cwd)
        if decision is not None:
            return None, None, decision
        joined_entry["tracker"] = tracker_status
        joined_entry["native_blocked"] = question_number in open_blocker_numbers

        if entry.get("disposition") == "in-scope (blocked)" and not tracker_status["resolved"]:
            joined_entry["status"] = "blocked"
            blocked = True
        else:
            joined_entry["status"] = "clear"
        joined.append(joined_entry)

    return joined, blocked, None


# ---------------------------------------------------------------------------
# Audit-ref derivation (docs/specs/resolver.md §4.5's 4-row table) + suggested_playbook
# ---------------------------------------------------------------------------


def _audit_ref(issue_type, epic_branch_name):
    """docs/specs/resolver.md §4.5's 4-row audit-ref table: bug/feature/refactor/standard ->
    `main`; Epic-as-target -> the discovered/bootstrap epic branch; Story under an open parent
    epic -> the parent epic's branch; Story with no parent epic (or a closed one) -> `main`.
    `epic_branch_name` is `None` for "no epic context" (standard type, or a story with no open
    parent) — in which case the ref is always `main`, matching the bootstrap-path rule that the
    zero-match Epic-as-target audit still runs against the main branch (the bootstrap branch would
    fork from main anyway).

    Returns a BARE branch name (`"main"` / `"epic/42-journal"`), never an `origin/`-prefixed ref
    — this is the facts-block `audit_ref` value verbatim. `workspace._build_ensure_read` is what
    prepends `origin/` internally (its own `git fetch origin <ref>` / `git worktree add --detach
    ... origin/<ref>` calls); the resulting **origin-prefixed** ref rides separately on
    `read_workspaces.audit.ref` once a read workspace is ensured (§6 below), since that workspace
    really did check out `origin/<ref>`, not the bare name. **S10's router/playbooks must read
    `audit_ref` as bare and never hand it to `git`/the state-distiller with an assumed `origin/`
    prefix themselves** (v1 passed an `origin/`-prefixed `audit_ref`/
    `integration_target_ref` to the sub-agents directly — v2 does not carry that prefixing
    convention on THIS field; consumers needing the prefixed form read
    `read_workspaces.audit.ref` instead).
    """
    if issue_type in ("standard",) or epic_branch_name is None:
        return ROOT_MAIN_BRANCH
    return epic_branch_name


def _suggested_playbook(issue_type, comment_only):
    """Map `(type, comment_only)` to the suggested playbook filename (architecture.md §5: "Prep
    proposes; the router confirms"). `comment_only` per the spec's routing signal: a `blocked`
    hard-gate state, or (should a future fact source detect it) any other no-code-work
    classification — named `comment-only.md` per this step's Work list.
    """
    if comment_only:
        return "comment-only.md"
    if issue_type == "epic":
        return "epic.md"
    if issue_type == "story":
        return "story.md"
    return "standard.md"


# ---------------------------------------------------------------------------
# attention
# ---------------------------------------------------------------------------


def _build_attention(work_workspace_envelope, prior_pr_row, epic_facts, story_epic_matches):
    attention = []
    if work_workspace_envelope is not None:
        setup = work_workspace_envelope.get("setup") or {}
        if setup.get("succeeded") is False:
            first_failure = setup.get("first_failure") or {}
            attention.append(
                "work worktree setup hook failed at step %s (`%s`) — worktree exists but is not "
                "ready" % (first_failure.get("step"), first_failure.get("command"))
            )
        if work_workspace_envelope.get("dirty"):
            attention.append("work worktree has uncommitted changes")
        unpushed = work_workspace_envelope.get("unpushed_commits") or 0
        if unpushed:
            attention.append("work worktree has %d unpushed commit(s)" % unpushed)
    if prior_pr_row == PRIOR_PR_ROW_OPEN_OTHER_ACTIVE:
        attention.append("an open PR by another author already references this issue and is actively worked")
    if prior_pr_row == PRIOR_PR_ROW_OPEN_OTHER_STALE:
        attention.append("an open PR by another author references this issue but looks stale")
    if prior_pr_row == PRIOR_PR_ROW_CLOSED_NOT_RESOLVED:
        attention.append("a closed/merged PR references this issue but did not resolve it")
    if epic_facts and epic_facts.get("match_count", 0) == 0 and "bootstrap_slug" in epic_facts:
        attention.append("no epic integration branch exists yet on origin — bootstrap required")
    return attention


# ---------------------------------------------------------------------------
# Facts-block assembly
# ---------------------------------------------------------------------------


def _forward_decision(decision, notices=None):
    """Emit a composed core's returned `decision` (or a directly-raised one) AS-IS on prep's own
    stdout and return `True` when a decision was present. Mirrors `prep_evaluator._forward_decision`
    exactly — see that function's docstring for the full rationale."""
    if decision is not None:
        emit_needs_decision(decision, notices=notices)
        return True
    return False


def build_facts(issue_number, repo, root=".", scratch_dir=None, refresh=False, cwd=None):
    """Assemble the resolver's complete facts block and return the envelope dict WITHOUT printing
    it (the testable core, mirroring `prep_evaluator.build_facts`'s split). Returns `None` after a
    `needs_decision` envelope has already been emitted on `stream` (the caller's `main()` reads
    `EXIT_OK` regardless — `needs_decision` is exit 0 per architecture.md §3).
    """
    root = str(Path(root).resolve())
    if scratch_dir is None:
        scratch_dir = "/tmp/gh-resolver-%s" % issue_number
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    # 1) The target issue — one round-trip gh_gather.run() call: body/thread/plan-marker/native
    #    deps + the open-PR search already folded in (architecture.md §7's GATHER_ISSUE contract).
    exit_code, issue_envelope = gh_gather.run(
        str(issue_number),
        repo,
        marker_prefix=PLAN_MARKER,
        scratch_dir=scratch_dir,
        env=None,
        stream=_DiscardStream(),
    )
    if issue_envelope is not None and issue_envelope.get("status") == "needs_decision":
        if _forward_decision(issue_envelope["decision"], notices=issue_envelope.get("notices")):
            return None
    if exit_code != 0:
        sys.stderr.write(
            "prep_resolver: gh_gather on issue #%s failed (exit %d)\n" % (issue_number, exit_code)
        )
        sys.exit(1)

    issue_body = issue_envelope.get("issue_body")
    if issue_body is None and issue_envelope.get("issue_body_mode") == "path":
        issue_body = Path(issue_envelope["issue_body_path"]).read_text(encoding="utf-8")
    issue_body = issue_body or ""

    labels = [label.get("name") for label in issue_envelope.get("labels") or []]
    issue_title = issue_envelope.get("title") or ""
    issue_type = _detect_type(labels, issue_title)

    # 2) State vector: prior-PR row -> mode.
    current_user_login, user_decision = _fetch_current_user(cwd)
    if user_decision is not None:
        emit_needs_decision(user_decision)
        return None
    open_prs = issue_envelope.get("open_prs") or []
    closed_prs = None
    if not open_prs:
        # Only searched when no open PR exists (docs/specs/resolver.md step-5 table's rows are
        # mutually exclusive; an open PR always wins) — keeps the canonical no-prior-PR/open-PR
        # paths at their minimal call count, per this step's call-budget DoD box.
        closed_prs, closed_pr_decision = _search_closed_prs(repo, issue_number, cwd=cwd)
        if _forward_decision(closed_pr_decision):
            return None
    prior_pr_row, prior_pr_fact = _classify_prior_pr_row(
        open_prs, current_user_login, closed_prs, issue_envelope.get("state")
    )
    if prior_pr_row in _CONTINUE_ROWS:
        mode = MODE_CONTINUE
    elif prior_pr_row in _GATED_ROWS:
        mode = MODE_GATED
    else:
        mode = MODE_FRESH
    gate = None
    if mode == MODE_GATED:
        # An unmissable gate fact, never a pre-empting side effect — mirrors the open-question
        # hard gate below. S10's router renders this AskUserQuestion card verbatim; prep does not
        # ensure a work worktree, does not fabricate a branch name, and does not otherwise act on
        # this issue's code until the operator answers.
        card = _GATE_CARDS[prior_pr_row]
        gate = {
            "reason": prior_pr_row,
            "header": card["header"],
            "options": card["options"],
            "prior_pr": prior_pr_fact,
        }

    # 3) Plan facts (marker present/absent, SHA parsed from its "planned <ISO> at `<ref>@<sha>`"
    #    header line, comment id, body staged to scratch).
    plan_present = bool(issue_envelope.get("marker_comment_present"))
    plan_body = None
    if plan_present:
        plan_body = issue_envelope.get("marker_comment_body")
        if plan_body is None and issue_envelope.get("marker_comment_mode") == "path":
            plan_body = Path(issue_envelope["marker_comment_path"]).read_text(encoding="utf-8")
    plan_sha = _extract_plan_sha(plan_body) if plan_body else None
    plan_facts = {
        "present": plan_present,
        "sha": plan_sha,
        "comment_id": issue_envelope.get("marker_comment_id"),
        "comment_url": issue_envelope.get("marker_comment_url"),
    }
    if plan_present:
        plan_facts["body_mode"] = issue_envelope.get("marker_comment_mode")
        if issue_envelope.get("marker_comment_mode") == "path":
            plan_facts["body_path"] = issue_envelope.get("marker_comment_path")

    # 4) Phase facts (parse.parse_phases, pure core) — only when a plan exists.
    phases = []
    if plan_present and plan_body:
        try:
            phases = parse.parse_phases(plan_body)
        except parse._PhasesMalformed as exc:  # noqa: SLF001
            from pipelib.decisions import PHASES_MALFORMED

            emit_needs_decision(
                needs_decision(
                    PHASES_MALFORMED,
                    summary=exc.reason,
                    context={"issue": issue_number, "line_number": exc.line_number, "raw_line": exc.raw_line},
                    options=[
                        "fix the '## Phases' section by hand to match the structured-key grammar "
                        "in skills/planner/references/plan-schema.md, then re-run"
                    ],
                )
            )
            return None

    # 5) DoD facts (parse.parse_dod_bullets, pure core) — over the ISSUE body (the resolver
    #    projects ticks onto the issue's own DoD, distinct from prep_evaluator's per-closing-issue
    #    keying since the resolver has exactly one target issue, not a PR's closing-issue set).
    try:
        dod = parse.parse_dod_bullets(issue_body)
    except parse._DodMalformed as exc:  # noqa: SLF001
        from pipelib.decisions import DOD_MALFORMED

        emit_needs_decision(
            needs_decision(
                DOD_MALFORMED,
                summary=exc.reason,
                context={"issue": issue_number, "line_number": exc.line_number, "raw_line": exc.raw_line},
                options=[
                    "fix the bullet's annotation by hand to match one of the closed-set forms in "
                    "skills/_shared/dod-annotations.md, then re-run"
                ],
            )
        )
        return None

    # 6) Open-question facts (parse.parse_oq_links joined with tracker state + native blocked_by).
    blocked_by = issue_envelope.get("blocked_by") or []
    open_questions, oq_blocked, oq_decision = _build_open_question_facts(
        issue_body, repo, blocked_by, scratch_dir, cwd=cwd
    )
    if _forward_decision(oq_decision):
        return None

    # Native `blocked by` is ALSO a hard gate independent of the OQ-links section (docs/specs/
    # resolver.md step 3: "if any blocker is open ... the issue is blocked"), so the comment-only
    # classification fires on either signal.
    any_open_native_blocker = any((b.get("state") or "").upper() == "OPEN" for b in blocked_by)
    comment_only = bool(oq_blocked) or any_open_native_blocker

    # 7) Epic / story facts + audit-ref derivation.
    epic_facts = None
    story_epic_matches = None
    epic_branch_for_audit = None
    if issue_type == "epic":
        epic_facts, epic_decision = _discover_epic_branch(root, issue_number, issue_title)
        if _forward_decision(epic_decision):
            return None
        epic_branch_for_audit = epic_facts.get("branch")
    elif issue_type == "story":
        story_epic_matches, epic_decision = _search_parent_epic(repo, issue_number, cwd=cwd)
        if _forward_decision(epic_decision):
            return None
        if len(story_epic_matches) == 1:
            parent_epic = story_epic_matches[0]
            if (parent_epic.get("state") or "").upper() == "OPEN":
                branch_facts, branch_decision = _discover_epic_branch(
                    root, parent_epic["number"], parent_epic.get("title") or ""
                )
                if _forward_decision(branch_decision):
                    return None
                epic_branch_for_audit = branch_facts.get("branch")
                epic_facts = {"parent_epic": parent_epic, "branch_facts": branch_facts}
            else:
                epic_facts = {"parent_epic": parent_epic, "branch_facts": None}
        else:
            epic_facts = {"parent_epic": None, "branch_facts": None}

    audit_ref = _audit_ref(issue_type, epic_branch_for_audit)

    # 8) Branch naming — MODE_FRESH only. MODE_GATED must not fabricate a branch name (there is
    #    nothing to name yet: the operator hasn't decided whether to take over the other author's
    #    branch or start fresh), and MODE_CONTINUE reuses the existing PR's own branch instead.
    branch_name = None
    branch_collision_with = None
    if mode == MODE_FRESH and not comment_only:
        slug = compute_fresh_slug(issue_title) if issue_type != "epic" else None
        if issue_type != "epic":
            branch_name, branch_collision_with = compute_branch_name(root, issue_number, slug)

    # A gated row is a flow gate, not an assembly blocker (identical reasoning to comment_only /
    # the open-question hard gate) — prep still completes and reports `status: ok`, it just never
    # ensures (or names a branch for) a WORK workspace impersonating someone else's in-flight PR.
    # `read_workspaces.audit` may still be assembled below (it's a detached, reused-by-ref view of
    # the audit target, never a branch checkout of the other author's own work).
    skip_work_workspace = comment_only or mode == MODE_GATED

    # 9) Workspaces + config, per mode (skipped on --refresh, same contract as prep_evaluator's).
    if not refresh:
        root_status, _rs_notices, root_status_decision = workspace._build_root_status(root)
        if _forward_decision(root_status_decision):
            return None
        root_sha = root_status["sha"]

        work_workspace_envelope = None
        if not skip_work_workspace:
            if mode == MODE_CONTINUE and prior_pr_fact and prior_pr_fact.get("headRefName"):
                work_branch = prior_pr_fact["headRefName"]
                work_base = ROOT_MAIN_BRANCH if audit_ref == ROOT_MAIN_BRANCH else audit_ref
            elif issue_type == "epic":
                work_branch = epic_branch_for_audit or (
                    "epic/%s-%s" % (issue_number, epic_facts.get("bootstrap_slug"))
                    if epic_facts
                    else None
                )
                work_base = ROOT_MAIN_BRANCH
            else:
                work_branch = branch_name
                work_base = ROOT_MAIN_BRANCH if audit_ref == ROOT_MAIN_BRANCH else audit_ref

            if work_branch:
                work_workspace_envelope, _ws_notices, ws_decision = workspace._build_ensure_work(
                    root, work_branch, work_base
                )
                if _forward_decision(ws_decision):
                    return None

        read_workspace_envelope = None
        if not comment_only and audit_ref != ROOT_MAIN_BRANCH:
            # Epic-as-target / story-under-open-epic: a genuinely second ref from the work
            # workspace's own branch, so a dedicated read workspace is ensured (architecture.md
            # §6: "a skill with no second view omits the key entirely" — the standard/no-epic path
            # never reaches this branch, since audit_ref == 'main' there).
            read_workspace_envelope, _rw_notices, rw_decision = workspace._build_ensure_read(
                root, audit_ref
            )
            if _forward_decision(rw_decision):
                return None

        gate_config, config_notices = _read_gate_config(root)
        gate_config["sha"] = root_sha
    else:
        work_workspace_envelope = None
        read_workspace_envelope = None
        gate_config, config_notices = {}, []
        root_sha = None

    # 10) Distiller input bundle — staged PATHS only (never above-threshold inline bytes; this
    #     step's DoD box). Reuses gh_gather's own spill files rather than re-writing copies.
    distiller_bundle = _build_distiller_bundle(issue_envelope, scratch_dir, issue_number)

    suggested_playbook = _suggested_playbook(issue_type, comment_only)

    vector = {
        "type": issue_type,
        "mode": mode,
        "prior_pr_row": prior_pr_row,
        "comment_only": comment_only,
    }
    if gate is not None:
        vector["gate"] = gate

    # One unmissable top-level boolean for the open-question hard gate (S10 should not have to
    # derive it from a conjunction of comment_only + per-entry statuses) — mirrors the prior-PR
    # gate fact above: a fact the router reads directly, never re-derives.
    blocking_oq_entries = [
        entry for entry in (open_questions or []) if entry.get("status") == "blocked"
    ]
    open_questions_gate = {"blocked": bool(blocking_oq_entries), "blocking": blocking_oq_entries}

    facts = {
        "repo": repo,
        "scratch": scratch_dir,
        "root": {"path": root, "sha": root_sha, "fresh": not refresh},
        "target": {
            "kind": "issue",
            "number": issue_envelope["number"],
            "title": issue_envelope["title"],
            "state": issue_envelope["state"],
            "labels": labels,
            "blocked_by": blocked_by,
            "blocking": issue_envelope.get("blocking") or [],
            "deps_available": issue_envelope.get("deps_available"),
        },
        "vector": vector,
        "prior_pr": prior_pr_fact,
        "plan": plan_facts,
        "phases": phases,
        "dod": dod,
        "open_questions": open_questions,
        "open_questions_gate": open_questions_gate,
        "audit_ref": audit_ref,
        "branch": {"name": branch_name, "collided_with": branch_collision_with} if branch_name else None,
        "suggested_playbook": suggested_playbook,
        "config": gate_config,
        "distiller_bundle": distiller_bundle,
        "attention": _build_attention(
            work_workspace_envelope, prior_pr_row, epic_facts, story_epic_matches
        ),
        "notices": list(config_notices),
    }
    if issue_type == "epic":
        facts["epic"] = epic_facts
    elif issue_type == "story":
        facts["story"] = epic_facts

    if work_workspace_envelope is not None:
        facts["workspace"] = {
            "path": work_workspace_envelope["path"],
            "branch": work_workspace_envelope["branch"],
            "base_ref": work_workspace_envelope["base_ref"],
            "sha": work_workspace_envelope.get("sha"),
            "reused": work_workspace_envelope.get("reused"),
            "dirty": work_workspace_envelope.get("dirty"),
            "unpushed_commits": work_workspace_envelope.get("unpushed_commits"),
            "setup": work_workspace_envelope.get("setup"),
        }
    if read_workspace_envelope is not None:
        facts["read_workspaces"] = {
            "audit": {
                "path": read_workspace_envelope["path"],
                "ref": read_workspace_envelope["ref"],
                "sha": read_workspace_envelope.get("sha"),
            }
        }

    sections = {}
    for key, value in issue_envelope.items():
        if key.startswith(("issue_body", "thread", "marker_comment")):
            sections[key] = value
    facts["sections"] = sections

    return facts


def _extract_plan_sha(plan_body):
    """Extract the short/long SHA from the plan's header line: '... planned <ISO> at
    `<plan-ref>@<short-sha>`' (skills/planner/references/plan-schema.md). Returns
    `None` if the header doesn't match the documented shape rather than guessing."""
    match = re.search(r"@`?([0-9a-f]{7,40})`?", plan_body or "")
    return match.group(1) if match else None


def _build_distiller_bundle(issue_envelope, scratch_dir, issue_number):
    """Stage the state-distiller's three inputs (docs/specs/resolver.md §P6: issue body, full
    comment thread, plan marker body) as PATHS, always — never above-threshold inline bytes (this
    step's DoD box). Reuses `gh_gather`'s own spill files when a section already spilled there
    rather than re-writing a copy; an inline (small) section is written out once here so the
    bundle's contract ("staged paths, always") holds regardless of the section's own threshold
    outcome.
    """

    def _stage(mode_key, path_key, bare_key, filename):
        mode = issue_envelope.get(mode_key)
        if mode == "path":
            return issue_envelope.get(path_key)
        content = issue_envelope.get(bare_key)
        if content is None:
            return None
        target = Path(scratch_dir) / filename
        target.write_text(content, encoding="utf-8")
        return str(target)

    return {
        "issue_body_path": _stage(
            "issue_body_mode", "issue_body_path", "issue_body", "issue-%s-body.md" % issue_number
        ),
        "thread_path": _stage(
            "thread_mode", "thread_path", "thread", "issue-%s-thread.json" % issue_number
        ),
        "plan_marker_path": _stage(
            "marker_comment_mode",
            "marker_comment_path",
            "marker_comment_body",
            "issue-%s-marker.md" % issue_number,
        )
        if issue_envelope.get("marker_comment_present")
        else None,
    }


def _fetch_current_user(cwd):
    result = process.run(["gh", "api", "user"], cwd=cwd)
    if result.auth_required:
        from pipelib.decisions import AUTH_REQUIRED

        return None, needs_decision(
            AUTH_REQUIRED,
            summary="gh authentication required",
            context={"stderr": result.stderr, "returncode": result.returncode},
            options=["run: gh auth login"],
        )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    return json.loads(result.stdout).get("login"), None


def main(argv):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("issue", help="issue number")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("--root", default=".", help="project root (architecture.md §6 vantage)")
    parser.add_argument(
        "--scratch-dir",
        default=None,
        help="scratch dir for spilled sections (default: /tmp/gh-resolver-<issue>)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-derive volatile facts (issue/PR state, branch discovery) without re-running hooks",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="explicit working directory for the gh calls that have no --repo scoping of their "
        "own (current-user, parent-epic search, closed-PR search, per-OQ tracker reads); optional "
        "in normal use (those calls don't depend on cwd), provided for test-injection — mirrors "
        "prep_evaluator.py's / gh_pr_gather.py's identical --cwd knob",
    )
    args = parser.parse_args(argv)

    facts = build_facts(
        args.issue,
        args.repo,
        root=args.root,
        scratch_dir=args.scratch_dir,
        refresh=args.refresh,
        cwd=args.cwd,
    )
    if facts is None:
        return EXIT_OK
    notices = facts.pop("notices", [])
    emit_ok(payload=facts, notices=notices)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
