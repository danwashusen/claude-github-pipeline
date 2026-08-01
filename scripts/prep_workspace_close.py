#!/usr/bin/env python3
"""prep_workspace_close.py — release an issue/PR work workspace, in one call (the v3
workspace-model inversion's operator-side closer; architecture.md §6).

This prep IS the workspace-close tool's action: it resolves the target branch (a branch name
verbatim, or an issue number via the GitHub-linked branch / the issue's PR head), then composes
``workspace._build_remove_work`` — teardown hooks best-effort, then the gated ``git worktree
remove``. Dirty or unpushed state is a decision (``AMBIGUOUS``), never a silent discard; removal
attempted from INSIDE the target worktree is ``WORKSPACE_MISMATCH`` (``cwd_inside_target``).

The routine post-merge path (the review-M2 fix): when the resolved source is a MERGED PR, its
``{number, head_oid}`` is threaded into the remove core — a clean worktree sitting exactly at the
merged head is removable even though squash-merge + delete-branch-on-merge makes its commits
count "unpushed" against the ``origin/main`` fallback; a merged branch with EXTRA local commits
gets a merged-specific card, never the nonsensical "push first" wording.

Branch resolution for a numeric argument, in order: (1) exactly one GitHub-linked branch
(`gh issue develop --list`) — >1 is ``AMBIGUOUS``; (2) the issue's open PR's head; (3) the
issue's most recent closed/merged PR's head; (4) none found -> ``AMBIGUOUS`` listing what was
tried. A non-numeric argument is taken as the branch name verbatim (linked/PR facts are still
looked up when they resolve cleanly, purely to enable the merged-PR path).

Usage::

    prep_workspace_close.py <branch-or-issue> <owner/repo> [--root PATH]

Exit codes (architecture.md §3): 0 with the envelope present (``ok`` or ``needs_decision``); 2 on
a usage error; any other non-zero is a hard `gh`/`git` failure with faithful stderr.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import branching  # noqa: E402
import gh_gather  # noqa: E402
import workspace  # noqa: E402
from pipelib.decisions import AMBIGUOUS, needs_decision  # noqa: E402
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR, emit_needs_decision, emit_ok  # noqa: E402


class _DiscardStream:
    def write(self, _data):
        return 0

    def flush(self):
        return None


def _forward_decision(decision, notices=None):
    if decision is not None:
        emit_needs_decision(decision, notices=notices)
        return True
    return False


def _resolve_branch_for_issue(issue_number, repo, scratch_dir, cwd=None):
    """Issue number -> ``(branch, via, merged_pr_or_none, decision_or_none, notices)``.
    ``merged_pr`` is ``{"number": N, "head_oid": sha}`` when the resolution came from (or also
    found) a MERGED PR for the branch — the remove core's post-merge context."""
    notices = []
    exit_code, issue_envelope = gh_gather.run(
        str(issue_number), repo, scratch_dir=scratch_dir, env=None, stream=_DiscardStream()
    )
    if issue_envelope is not None and issue_envelope.get("status") == "needs_decision":
        return None, None, None, issue_envelope["decision"], notices
    if exit_code != 0:
        sys.stderr.write(
            "prep_workspace_close: gh_gather on issue #%s failed (exit %d)\n"
            % (issue_number, exit_code)
        )
        sys.exit(1)

    linked, link_notice, link_decision = branching.list_linked_branches(
        repo, issue_number, cwd=cwd
    )
    if link_decision is not None:
        return None, None, None, link_decision, notices
    if link_notice:
        notices.append(link_notice)
        linked = []
    if linked and len(linked) > 1:
        return None, None, None, needs_decision(
            AMBIGUOUS,
            summary="%d GitHub-linked branches exist for issue #%s — name the branch explicitly"
            % (len(linked), issue_number),
            context={"issue": issue_number, "candidates": linked},
            options=["re-run with the branch name instead of the issue number"],
        ), notices

    open_prs = issue_envelope.get("open_prs") or []
    closed_prs, closed_decision = branching.search_closed_prs(repo, issue_number, cwd=cwd)
    if closed_decision is not None:
        return None, None, None, closed_decision, notices

    branch = None
    via = None
    if linked:
        branch, via = linked[0], "linked"
    elif open_prs:
        branch, via = open_prs[0].get("headRefName"), "pr-head"
    elif closed_prs:
        branch, via = closed_prs[0].get("headRefName"), "pr-head"

    if branch is None:
        return None, None, None, needs_decision(
            AMBIGUOUS,
            summary="no branch could be resolved for issue #%s (no linked branch, no PR)"
            % issue_number,
            context={"issue": issue_number},
            options=["re-run with the branch name instead of the issue number"],
        ), notices

    merged_pr = _merged_pr_for_branch(branch, open_prs, closed_prs)
    return branch, via, merged_pr, None, notices


def _merged_pr_for_branch(branch, open_prs, closed_prs):
    """The MERGED PR whose head is ``branch``, as the remove core's ``{number, head_oid}``
    context — ``None`` when the branch has no merged PR. ``headRefOid`` is not in the closed-PR
    search's field set, so the head OID rides as ``None`` there and the remove core falls back to
    the generic gate; the caller may enrich it when it fetched the PR another way."""
    for pr in closed_prs or []:
        merged = (pr.get("state") or "").upper() == "MERGED" or bool(pr.get("mergedAt"))
        if merged and pr.get("headRefName") == branch:
            return {"number": pr.get("number"), "head_oid": pr.get("headRefOid")}
    return None


def build_facts(branch_or_issue, repo, root=".", scratch_dir=None, cwd=None):
    """Assemble the close receipt and return the envelope dict WITHOUT printing it. Returns
    ``None`` after a ``needs_decision`` envelope has already been emitted."""
    root = str(workspace._resolve_main_root(root))
    if scratch_dir is None:
        scratch_dir = "/tmp/gh-workspace-close-%s" % branch_or_issue.replace("/", "-")
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    notices = []
    if branch_or_issue.isdigit():
        branch, via, merged_pr, decision, notices = _resolve_branch_for_issue(
            branch_or_issue, repo, scratch_dir, cwd=cwd
        )
        if _forward_decision(decision, notices=notices):
            return None
    else:
        branch, via, merged_pr = branch_or_issue, "arg", None

    payload, _rm_notices, rm_decision = workspace._build_remove_work(
        root, branch, invoker_cwd=Path.cwd(), merged_pr=merged_pr
    )
    if _forward_decision(rm_decision, notices=notices):
        return None

    facts = {
        "repo": repo,
        "scratch": scratch_dir,
        "root": {"path": root},
        "branch_resolution": {"input": branch_or_issue, "branch": branch, "via": via},
        "notices": notices,
    }
    facts.update(payload)  # the remove receipt verbatim: op/kind/branch/path/removed/teardown
    return facts


def main(argv):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("branch_or_issue", help="branch name, or issue number to resolve")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("--root", default=".", help="any checkout of the repo (normalized to the main checkout)")
    parser.add_argument("--scratch-dir", dest="scratch_dir", default=None)
    parser.add_argument("--cwd", default=None, help="explicit cwd for the gh calls (test injection)")
    args = parser.parse_args(argv)

    facts = build_facts(
        args.branch_or_issue, args.repo, root=args.root, scratch_dir=args.scratch_dir, cwd=args.cwd
    )
    if facts is None:
        return EXIT_OK
    notices = facts.pop("notices", [])
    emit_ok(payload=facts, notices=notices)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
