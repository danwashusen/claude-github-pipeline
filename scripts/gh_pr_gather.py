#!/usr/bin/env python3
"""gh_pr_gather.py — the ``GATHER_PR`` envelope (architecture.md §7): a from-scratch Python port
of ``scripts/gh-pr-gather.sh`` under the architecture.md §3 envelope, using the S3 ``pipelib``
primitives. ``gh-pr-gather.sh`` is the frozen v1 behavioral reference this preserves — the
contract below is re-expressed in envelope terms, not transliterated line-by-line, and the v1
``.sh`` stays untouched for v1 callers until S20.

One round-trip PR fetch: PR metadata (body, thread, labels, state, base/head refs, review/CI
fields) + labels + state, plus optional diff / line-level review comments — the same "one
round-trip, not three" property ``gh-gather.sh``/``gh_gather.py`` gives issues, so the caller never
has to hold a multi-KB payload in its own context while waiting on several separate ``gh`` calls.

Usage::

    gh_pr_gather.py <pr-number> <owner/repo> [--marker-prefix PREFIX] [--scratch-dir DIR]
                     [--with-diff] [--with-line-comments]

``<pr-number>`` and ``<owner/repo>`` are required positional arguments. ``--scratch-dir`` is
required whenever ``--with-diff`` or ``--with-line-comments`` is given (this script refuses to
spill a multi-KB diff/line-comments payload through the envelope with nowhere to write it — same
refusal v1 enforced) and is otherwise optional (legacy inline-only mode when omitted, matching
v1's "no-scratch-dir mode: legacy inline envelope").

Preserved from v1, re-expressed as a §3 envelope:

- **One round-trip PR fetch** — ``gh pr view`` for metadata + body + thread + reviews, plus (when
  a marker prefix is given) a marker-comment lookup over the PR's issue-comments thread (PR
  comments are issue comments under the hood, exactly as in ``gh-gather.sh``). Preserves the exact
  v1 field set the evaluator keys on: ``number``, ``title``, ``state``, ``isDraft``, ``author``,
  ``baseRefName``, ``headRefName``, ``headRefOid``, ``additions``, ``deletions``, ``changedFiles``,
  ``commit_count`` (derived from ``commits`` length, as v1 does), ``mergeStateStatus``,
  ``mergeable``, ``reviewDecision``, ``statusCheckRollup``, ``closingIssuesReferences``, ``url``,
  ``latestReviews``.
- **Marker discovery + ``marker_comment_count``** — a marker-prefix match against the PR's
  issue-comments thread. Unlike v1 (which silently picks ``.[0]`` on a duplicate), a duplicate
  match is a **new v2 behavior**: ``MARKER_AMBIGUOUS`` (architecture.md §3: "more than one
  candidate marker comment/block where the contract expects one; the gathers + config_block.py")
  — the DoD's own contract-tightening ask, not a transliteration bug.
- **Threshold spill** (``pipelib.spill.spill_bytes``) on body/thread/reviews/marker-comment
  sections — inline when small, written to ``scratch_dir`` when large, per architecture.md §3.
- **Optional ``--with-diff`` / ``--with-line-comments``** — fetched only when requested, and
  **always** spilled to a path (``force_path=True``) regardless of size, per architecture.md §3:
  "Diffs and line-comment sets are always `path`." Exact v1 flag names preserved.

Exit codes (architecture.md §3): 0 with an envelope present (``status`` is ``"ok"`` or
``"needs_decision"``); 2 on a usage error (malformed invocation, no envelope). Any other non-zero
is a hard `gh`/`git` failure — stderr carries the faithful error; no envelope guaranteed.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipelib import process  # noqa: E402  (import after sys.path setup, by necessity)
from pipelib.decisions import AUTH_REQUIRED, MARKER_AMBIGUOUS, needs_decision  # noqa: E402
from pipelib.envelope import (  # noqa: E402
    EXIT_OK,
    EXIT_USAGE_ERROR,
    emit_needs_decision,
    emit_ok,
)
from pipelib.spill import spill_bytes  # noqa: E402

# Exactly the v1 --json field list (gh-pr-gather.sh's `gh pr view --json ...`) — the evaluator
# keys on this field set; do not add/drop/rename a field without a matching evaluator-spec change.
_VIEW_JSON_FIELDS = ",".join(
    [
        "number",
        "title",
        "body",
        "state",
        "isDraft",
        "author",
        "baseRefName",
        "headRefName",
        "commits",
        "additions",
        "deletions",
        "changedFiles",
        "closingIssuesReferences",
        "comments",
        "reviews",
        "latestReviews",
        "reviewDecision",
        "mergeStateStatus",
        "mergeable",
        "statusCheckRollup",
        "headRefOid",
        "url",
    ]
)

# PR comments are issue comments under the hood (same endpoint shape gh-gather.sh uses for issue
# marker lookups) — v1's comment on this is load-bearing: it's *why* one marker-lookup shape
# covers both issue and PR gathers.
_ISSUE_COMMENTS_ENDPOINT = "repos/%s/issues/%s/comments"
_LINE_COMMENTS_ENDPOINT = "repos/%s/pulls/%s/comments"


def _auth_required_decision(result):
    return needs_decision(
        AUTH_REQUIRED,
        summary="gh authentication required",
        context={"stderr": result.stderr, "returncode": result.returncode},
        options=["run: gh auth login"],
    )


def _fetch_view(pr, repo, cwd):
    """One ``gh pr view`` call covering everything except the diff and line-comments (which use
    different endpoints) — mirrors v1's fetch #1 exactly (same ``--json`` field list, same repo
    scoping via ``--repo`` rather than ambient cwd).
    """
    return process.run(
        ["gh", "pr", "view", str(pr), "--repo", repo, "--json", _VIEW_JSON_FIELDS], cwd=cwd
    )


def _fetch_markers(pr, repo, marker, cwd):
    """Marker-comment lookup over the PR's issue-comments thread — mirrors v1's fetch #2. Returns
    the full comments list (not jq-filtered server-side, unlike v1's ``--jq`` filter expression)
    so the filtering logic — and any future contract check on it — lives in this Python module,
    testable directly, rather than inside an opaque jq string.
    """
    return process.run(
        ["gh", "api", _ISSUE_COMMENTS_ENDPOINT % (repo, pr)],
        cwd=cwd,
    )


def _fetch_diff(pr, repo, cwd):
    """PR diff — mirrors v1's fetch #3 (``gh pr diff``)."""
    return process.run(["gh", "pr", "diff", str(pr), "--repo", repo], cwd=cwd)


def _fetch_line_comments(pr, repo, cwd):
    """Line-level review comments JSON — mirrors v1's fetch #4 (``gh api .../pulls/<pr>/comments``)."""
    return process.run(["gh", "api", _LINE_COMMENTS_ENDPOINT % (repo, pr)], cwd=cwd)


def _matching_markers(comments, marker):
    """Filter ``comments`` (the parsed ``gh api .../comments`` list) to those whose ``body``
    starts with ``marker`` — the Python equivalent of v1's
    ``select(.body | startswith($m))`` jq filter, preserved exactly (a prefix match, not a
    substring match).
    """
    return [c for c in comments if isinstance(c.get("body"), str) and c["body"].startswith(marker)]


def run(pr, repo, marker=None, scratch_dir=None, with_diff=False, with_line_comments=False, cwd=None):
    """Perform the GATHER_PR fetch and return the built envelope dict (does not emit/exit) — the
    testable core, separated from ``main``'s argv/exit-code plumbing so unit tests can call this
    directly when they don't need a full subprocess round-trip.

    ``cwd`` is the explicit working directory passed to every ``gh`` call (per the S21 brief's cwd
    discipline: never rely on ambient cwd — every subprocess call is scoped by an explicit ``cwd``
    and/or ``--repo``).
    """
    view_result = _fetch_view(pr, repo, cwd)
    if view_result.auth_required:
        return emit_needs_decision(_auth_required_decision(view_result))
    if view_result.returncode != 0:
        sys.stderr.write(view_result.stderr)
        sys.exit(1)
    view = json.loads(view_result.stdout)

    matched_markers = []
    if marker:
        markers_result = _fetch_markers(pr, repo, marker, cwd)
        if markers_result.auth_required:
            return emit_needs_decision(_auth_required_decision(markers_result))
        if markers_result.returncode != 0:
            sys.stderr.write(markers_result.stderr)
            sys.exit(1)
        all_comments = json.loads(markers_result.stdout)
        matched_markers = _matching_markers(all_comments, marker)

    # Duplicate marker → MARKER_AMBIGUOUS (architecture.md §3; the DoD's contract-tightening ask —
    # v1 silently picked .[0] here). Detected before any diff/line-comments fetch or spill, so an
    # ambiguous state never partially spills scratch files the caller then has to clean up.
    if len(matched_markers) > 1:
        return emit_needs_decision(
            needs_decision(
                MARKER_AMBIGUOUS,
                summary="more than one PR comment matches marker prefix %r" % marker,
                context={
                    "pr": pr,
                    "repo": repo,
                    "marker_prefix": marker,
                    "candidates": [
                        {"id": c.get("id"), "url": c.get("html_url")} for c in matched_markers
                    ],
                },
                options=["delete the stale duplicate", "pick the candidate to treat as canonical"],
            )
        )

    diff_bytes = 0
    diff_line_count = 0
    diff_fields = {}
    if with_diff:
        diff_result = _fetch_diff(pr, repo, cwd)
        if diff_result.auth_required:
            return emit_needs_decision(_auth_required_decision(diff_result))
        if diff_result.returncode != 0:
            sys.stderr.write(diff_result.stderr)
            sys.exit(1)
        diff_data = diff_result.stdout.encode("utf-8")
        diff_bytes = len(diff_data)
        diff_line_count = diff_data.count(b"\n")
        # force_path=True: diffs are always path mode regardless of size (architecture.md §3).
        diff_spill = spill_bytes(
            diff_data, "diff", scratch_dir, force_path=True, filename="pr-%s-diff.patch" % pr
        )
        diff_fields = {
            "diff_path": diff_spill["diff_path"],
            "diff_bytes": diff_bytes,
            "diff_line_count": diff_line_count,
        }

    line_comments_fields = {}
    if with_line_comments:
        lc_result = _fetch_line_comments(pr, repo, cwd)
        if lc_result.auth_required:
            return emit_needs_decision(_auth_required_decision(lc_result))
        if lc_result.returncode != 0:
            sys.stderr.write(lc_result.stderr)
            sys.exit(1)
        lc_data = lc_result.stdout.encode("utf-8")
        lc_count = len(json.loads(lc_result.stdout))
        # force_path=True: line-comment sets are always path mode regardless of size, same rule
        # as the diff above.
        lc_spill = spill_bytes(
            lc_data,
            "line_comments",
            scratch_dir,
            force_path=True,
            filename="pr-%s-line-comments.json" % pr,
        )
        line_comments_fields = {
            "line_comments_path": lc_spill["line_comments_path"],
            "line_comments_bytes": len(lc_data),
            "line_comments_count": lc_count,
        }

    payload = {
        "number": view["number"],
        "title": view["title"],
        "state": view["state"],
        "isDraft": view["isDraft"],
        "author": view["author"],
        "baseRefName": view["baseRefName"],
        "headRefName": view["headRefName"],
        "headRefOid": view["headRefOid"],
        "additions": view["additions"],
        "deletions": view["deletions"],
        "changedFiles": view["changedFiles"],
        "commit_count": len(view["commits"]),
        "mergeStateStatus": view["mergeStateStatus"],
        "mergeable": view["mergeable"],
        "reviewDecision": view["reviewDecision"],
        "statusCheckRollup": view["statusCheckRollup"],
        "closingIssuesReferences": view["closingIssuesReferences"],
        "url": view["url"],
        "latestReviews": view["latestReviews"],
    }

    if scratch_dir is not None:
        # Scratch-dir mode: route body/thread/reviews/marker through the inline-vs-path threshold
        # (pipelib.spill), mirroring v1's threshold-routed envelope exactly.
        # architecture.md §3 names "thread" (alongside body/diff/marker comment) as one of the
        # canonical verbatim sections, and §4/spill.py's own contract is that an inline bare field
        # is decoded UTF-8 *text* — so `thread`/`reviews` are spilled as their JSON-serialized text
        # form (a string), same as every other spill_bytes section, NOT re-parsed back to a
        # structured array. A caller reading an inline `thread`/`reviews` field does its own
        # `json.loads` on the string, exactly as it would on a spilled file's contents — this
        # keeps every spilled section uniformly "text in, text out" regardless of mode, matching
        # tests/support/envelope_asserts.py's conformance rule (the shared, frozen-for-S21 helper
        # every later suite validates against).
        body_fields = spill_bytes((view.get("body") or "").encode("utf-8"), "body", scratch_dir)
        thread_bytes_data = json.dumps(view["comments"], ensure_ascii=False).encode("utf-8")
        thread_fields = spill_bytes(thread_bytes_data, "thread", scratch_dir)
        thread_fields["thread_comment_count"] = len(view["comments"])
        reviews_bytes_data = json.dumps(view["reviews"], ensure_ascii=False).encode("utf-8")
        reviews_fields = spill_bytes(reviews_bytes_data, "reviews", scratch_dir)
        reviews_fields["reviews_count"] = len(view["reviews"])

        payload["inline_threshold_bytes"] = _resolve_threshold_for_report()
        payload.update(body_fields)
        payload.update(thread_fields)
        payload.update(reviews_fields)

        payload["marker_comment_present"] = len(matched_markers) > 0
        payload["marker_comment_count"] = len(matched_markers)
        if matched_markers:
            marker_comment = matched_markers[0]
            marker_str = marker_comment.get("body") or ""
            marker_fields = spill_bytes(marker_str.encode("utf-8"), "marker_comment", scratch_dir)
            payload["marker_comment_id"] = marker_comment.get("id")
            payload["marker_comment_url"] = marker_comment.get("html_url")
            payload.update(marker_fields)

        payload.update(diff_fields)
        payload.update(line_comments_fields)
    else:
        # Legacy inline-only mode (no scratch_dir): v1's "legacy inline envelope" — body, thread,
        # reviews all inline regardless of size (v1 refuses --with-diff/--with-line-comments in
        # this mode; that refusal is enforced by main()'s argument validation before run() is
        # ever called, mirroring v1's own upfront usage-error check).
        payload["body"] = view.get("body") or ""
        payload["thread"] = view["comments"]
        payload["reviews"] = view["reviews"]
        payload["marker_comment"] = (
            {
                "id": matched_markers[0].get("id"),
                "url": matched_markers[0].get("html_url"),
                "body": matched_markers[0].get("body"),
            }
            if matched_markers
            else None
        )
        payload["marker_comment_count"] = len(matched_markers)

    return emit_ok(payload=payload)


def _resolve_threshold_for_report():
    # Local import to avoid a hard dependency ordering surprise at module load time; mirrors the
    # v1 envelope's `inline_threshold_bytes` scalar (the threshold value actually in effect for
    # this run, so a caller can tell whether an env override was active).
    from pipelib.spill import resolve_threshold

    return resolve_threshold()


def main(argv):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pr", help="PR number")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("--marker-prefix", default="", help="marker comment prefix to search for")
    parser.add_argument("--scratch-dir", default="", help="scratch dir for spilled sections")
    parser.add_argument("--with-diff", action="store_true", help="fetch the PR diff (always path mode)")
    parser.add_argument(
        "--with-line-comments",
        action="store_true",
        help="fetch line-level review comments (always path mode)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="explicit working directory for gh calls (optional; --repo already scopes every "
        "gh call to the target repo regardless of cwd, so this is for a caller that also wants "
        "process.run's cwd pinned explicitly rather than inherited)",
    )
    args = parser.parse_args(argv)

    if (args.with_diff or args.with_line_comments) and not args.scratch_dir:
        sys.stderr.write(
            "gh_pr_gather.py: --with-diff / --with-line-comments require --scratch-dir\n"
        )
        return EXIT_USAGE_ERROR

    scratch_dir = args.scratch_dir if args.scratch_dir else None
    if scratch_dir is not None:
        Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    run(
        args.pr,
        args.repo,
        marker=args.marker_prefix if args.marker_prefix else None,
        scratch_dir=scratch_dir,
        with_diff=args.with_diff,
        with_line_comments=args.with_line_comments,
        cwd=args.cwd,
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
