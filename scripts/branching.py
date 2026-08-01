"""branching.py — shared branch-naming, type-detection, and prior-PR classification cores.

Import-only module (no shebang, no ``main`` — like ``oq_tracker.py`` it is composed in-process by
the preps, never dispatched). Extracted verbatim from ``prep_resolver.py`` at the v3
workspace-model inversion so that ``prep_workspace_open.py`` (which now owns branch creation) and
``prep_resolver.py`` (which now only *asserts* the ambient branch) derive branch names, issue
types, epic-branch discovery, and prior-PR rows from ONE implementation. ``prep_resolver.py``
keeps module-level aliases to every extracted name (the ``build_oq_query = oq_tracker.build_oq_query``
precedent in ``prep_planner.py``), so its public surface — and the direct-call tests against it —
are unchanged.

Everything here is a pure derivation over ``git ls-remote`` / ``gh`` list queries: no worktree
side effects, no GitHub writes. The behavioral contracts (the 7-row prior-PR table, the 6-step
fresh-slug derivation, `-vN` collision suffixing, epic-branch discovery) are specified in
``docs/specs/resolver.md`` and were not altered by the extraction.
"""

import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gh_gather  # noqa: E402  (in-process composition — the reference-filter fix lives there)
from pipelib import process  # noqa: E402
from pipelib.decisions import AMBIGUOUS, AUTH_REQUIRED, needs_decision  # noqa: E402

# State-vector `type` detection (docs/specs/resolver.md "State-vector derivation: labels -> type";
# the spec's "Epic-branch discovery" row): case-insensitive `epic`/`story` label match, OR a
# title `Epic:` prefix (case-insensitive) for the epic arm — the fresh-slug derivation uses the
# identical prefix test, so the type-detection prefix check mirrors it exactly.
EPIC_TITLE_PREFIX_RE = re.compile(r"^\s*epic\s*:", re.IGNORECASE)

# Epic branch pattern: `epic/<N>-<slug>` (docs/specs/resolver.md "Epic-branch discovery").
EPIC_BRANCH_LS_REMOTE_PATTERN = "epic/%s-*"
EPIC_BRANCH_NAME_RE = re.compile(r"^epic/(\d+)-(.+)$")

# Branch-collision suffixing: `<issue>-<slug>` optionally followed by `-v<N>`
# (docs/specs/resolver.md's "Branch-collision suffixing (`-vN`)" row; unsuffixed counts as v1).
BRANCH_VERSION_SUFFIX_RE = re.compile(r"^-v(\d+)$")


# ---------------------------------------------------------------------------
# git ls-remote — no existing executor core covers this query shape (architecture.md §1 permits
# any script to spawn git/gh directly via pipelib.process.run).
# ---------------------------------------------------------------------------


def list_remote_branches(root, pattern):
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


def detect_type(labels, title):
    """Case-insensitive `epic`/`story` label match, or a title `Epic:` prefix (docs/specs/
    resolver.md "State-vector derivation: labels -> type"). `epic` takes precedence over `story`
    if (pathologically) both labels are present, matching the spec's listed priority order.
    """
    lowered_labels = {(label or "").strip().lower() for label in labels or []}
    if "epic" in lowered_labels or EPIC_TITLE_PREFIX_RE.match(title or ""):
        return "epic"
    if "story" in lowered_labels:
        return "story"
    return "standard"


# The v1 step-5 prior-PR state table (docs/specs/resolver.md "Fresh/continue mode from the
# prior-PR state table" — its seven rows), carried as the row name -> mode mapping. See
# prep_resolver.py's vector assembly for the mode semantics (`continue` / `gated` / `fresh`) and
# why a gated row is still an `ok` envelope (a flow gate the router raises, not a prep failure).
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

CONTINUE_ROWS = frozenset({PRIOR_PR_ROW_OPEN_YOURS, PRIOR_PR_ROW_DRAFT})
GATED_ROWS = frozenset({PRIOR_PR_ROW_OPEN_OTHER_ACTIVE, PRIOR_PR_ROW_OPEN_OTHER_STALE})

# Per-gated-row AskUserQuestion shape the resolver's router renders (the exact headers/options in
# docs/specs/resolver.md "Operator gates"), carried as a fact so the router never re-derives which
# card goes with which row. A foreign draft reuses whichever of the two "someone else" rows its
# activity classifies as (see classify_prior_pr_row) — there is no third, draft-specific card.
GATE_CARDS = {
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
# activity ... for a long time") — this is a CHOSEN deterministic default needed to classify
# open-other PRs at all, not a value derived from any other doc in this repo. Surfaced as
# `prior_pr.stale_cutoff_days` (see classify_prior_pr_row) so the operator/router can see the
# exact driver rather than trust an opaque classification. Active vs stale changes ONLY which gate
# card is shown (GATE_CARDS) — both rows are `mode: "gated"`.
STALE_ACTIVITY_DAYS = 14


def search_closed_prs(repo, issue_number, cwd=None):
    """Targeted closed/merged-PR search referencing this issue (docs/specs/resolver.md step-5
    table's two "closed" rows; mirrors the spec's own predecessor-PR-detection search convention:
    `gh pr list --state closed --search "<N> in:body"`). Returns `(prs, decision_or_none)`; each
    PR dict carries `number`/`state`/`mergedAt` (`state == "MERGED"` classifies resolved, since a
    merged PR referencing the issue closed it — v1's "closed PR that resolved the issue" row).

    The raw search result is filtered through `gh_gather.references_issue` (via
    `_filter_and_strip_reference_fields`) — `--search "<N> in:body"` is a GitHub full-text search,
    not a literal-string containment check; see `gh_gather.py`'s module docstring "Open-PR search
    false-positive fix" for the evidence.
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


def classify_prior_pr_row(open_prs, current_user, closed_prs, issue_state):
    """Classify the issue's prior-PR state into exactly one of the 7 named rows, returning
    ``(row_name, prior_pr_fact_or_none)``. ``open_prs`` is `gh_gather`'s `open_prs` list (from the
    `gh pr list ... "<N> in:body"` search); ``closed_prs`` is :func:`search_closed_prs`'s result
    (only consulted when no open PR exists); ``issue_state`` (`OPEN`/`CLOSED`) disambiguates the
    two closed-PR rows exactly as docs/specs/resolver.md's table does ("closed PR that resolved
    the issue" implies the issue itself is closed; a merged PR against a still-open issue is the
    partial-fix/abandoned case).

    Authorship is decided BEFORE draft state: the prior-PR table's "Draft PR" row explicitly
    scopes to "the same author" — it is not a draft-vs-ready split independent of who owns the PR.
    So an open PR by someone else classifies via :func:`classify_open_other_activity` regardless
    of its draft state; only YOUR own open PR can ever land on `open-pr-yours` or `draft`.
    """
    if open_prs:
        # Prefer a PR by the current user (matches v1's per-row priority: "yours" outranks
        # "other's" when the caller happens to own more than one referencing PR).
        yours = [pr for pr in open_prs if (pr.get("author") or {}).get("login") == current_user]
        chosen = yours[0] if yours else open_prs[0]
        if yours:
            row = PRIOR_PR_ROW_DRAFT if chosen.get("isDraft") else PRIOR_PR_ROW_OPEN_YOURS
        else:
            # Someone else's PR — draft or not, it's still claimed work someone else owns; a
            # foreign draft therefore gates exactly like a foreign ready PR, classified by the
            # same activity check.
            row = classify_open_other_activity(chosen)
        fact = {
            "number": chosen.get("number"),
            "author": (chosen.get("author") or {}).get("login"),
            "isDraft": chosen.get("isDraft"),
            "headRefName": chosen.get("headRefName"),
            "updatedAt": chosen.get("updatedAt"),
            "url": chosen.get("url"),
            "stale_cutoff_days": STALE_ACTIVITY_DAYS,
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


def classify_open_other_activity(pr):
    """Active vs stale for an open PR authored by someone else, including a foreign draft
    (docs/specs/resolver.md step-5 table's two "someone else" rows) — `updatedAt` age vs
    :data:`STALE_ACTIVITY_DAYS` (a chosen default, not a derived one — see that constant's
    comment). Missing `updatedAt` defaults to "active" (never silently downgrade a PR to stale
    on absent data). Both outcomes are `mode: "gated"` (see `GATED_ROWS`) — this only decides
    WHICH `AskUserQuestion` card the router shows (`GATE_CARDS`), never whether the row gates."""
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
    if age.days >= STALE_ACTIVITY_DAYS:
        return PRIOR_PR_ROW_OPEN_OTHER_STALE
    return PRIOR_PR_ROW_OPEN_OTHER_ACTIVE


# ---------------------------------------------------------------------------
# Fresh-slug computation (bootstrap only) — the spec's 6-step derivation, verbatim.
# ---------------------------------------------------------------------------

SLUG_STRIP_EPIC_PREFIX_RE = re.compile(r"^\s*epic\s*:\s*", re.IGNORECASE)
SLUG_NON_ALNUM_RUN_RE = re.compile(r"[^a-z0-9]+")
SLUG_MAX_LENGTH = 50


def compute_fresh_slug(title):
    """The 6-step epic-title -> slug derivation (docs/specs/resolver.md "Fresh-slug computation
    (bootstrap only)"):
    strip an `Epic:` prefix, lowercase, replace non-`[a-z0-9]` runs with `-`, strip leading/
    trailing `-`, truncate to <=50 chars on a `-` boundary. Used ONLY on the bootstrap path (zero
    `git ls-remote` matches) — an existing branch's slug is always taken from the discovered
    branch name verbatim, never recomputed (the spec's "Discover the epic branch slug by prefix;
    only compute fresh on bootstrap" invariant).
    """
    stripped = SLUG_STRIP_EPIC_PREFIX_RE.sub("", title or "").strip()
    lowered = stripped.lower()
    collapsed = SLUG_NON_ALNUM_RUN_RE.sub("-", lowered)
    trimmed = collapsed.strip("-")
    if len(trimmed) <= SLUG_MAX_LENGTH:
        return trimmed
    truncated = trimmed[:SLUG_MAX_LENGTH]
    # "if the truncation would land mid-word ... keep truncating back to the previous '-'."
    if len(trimmed) > SLUG_MAX_LENGTH and trimmed[SLUG_MAX_LENGTH] not in ("-",):
        last_dash = truncated.rfind("-")
        if last_dash != -1:
            truncated = truncated[:last_dash]
    return truncated.rstrip("-")


# ---------------------------------------------------------------------------
# Epic-branch discovery (zero/one/multiple) + story parent-epic search
# ---------------------------------------------------------------------------


def discover_epic_branch(root, epic_number, epic_title):
    """Discover `epic/<epic_number>-*` on origin (docs/specs/resolver.md "Epic-branch discovery").
    Returns `(facts_dict, decision_or_none)`:
      - zero matches -> `{"match_count": 0, "branch": None, "bootstrap_slug": <computed>}`.
      - one match -> `{"match_count": 1, "branch": <name>}`.
      - multiple matches -> `(None, AMBIGUOUS decision)` (context lists every candidate).
    """
    matches, _ = list_remote_branches(root, EPIC_BRANCH_LS_REMOTE_PATTERN % epic_number)
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


def search_parent_epic(repo, story_number, cwd=None):
    """Story parent-epic search (docs/specs/resolver.md "Epic-branch discovery"; the
    `gh issue list --label epic --state all --search '#<N> in:body'` query). Returns
    `(matches, decision_or_none)` where `matches` is the `gh issue list` result list, filtered
    (empty on zero genuine matches).

    Filtered through `gh_gather.references_issue` — GitHub's server-side full-text search does not
    use `#` as an anchor, so the hash-prefixed form has the same false-positive exposure as the
    bare-digit PR searches (see `gh_gather.py`'s module docstring).
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

    v3 caution (the `-vN` recompute drift): this collision logic is for MINTING a new branch —
    `prep_workspace_open.py`'s fresh path. A prep that merely *asserts* an ambient branch (the
    resolver) must never re-run this against a branch workspace-open already pushed: the pushed
    branch itself would count as the collision and yield `-v2`, a guaranteed self-mismatch.
    """
    base = "%s-%s" % (issue_number, slug)
    matches, _ = list_remote_branches(root, base + "*")
    # Only exact-base or exact-base+`-vN` count as a real collision — a match that merely starts
    # with the same prefix by coincidence (e.g. "<N>-<slug>-extra-words") is not a versioned
    # sibling of this branch and must not perturb the version count.
    relevant = [m for m in matches if m == base or BRANCH_VERSION_SUFFIX_RE.match(m[len(base) :])]
    if not relevant:
        return base, None
    highest = 1
    for match in relevant:
        if match == base:
            highest = max(highest, 1)
            continue
        suffix_match = BRANCH_VERSION_SUFFIX_RE.match(match[len(base) :])
        if suffix_match:
            highest = max(highest, int(suffix_match.group(1)))
    return "%s-v%d" % (base, highest + 1), sorted(relevant)
