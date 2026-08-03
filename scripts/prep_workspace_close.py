#!/usr/bin/env python3
"""prep_workspace_close.py — release an issue/PR work workspace, in one call (the v3
workspace-model inversion's operator-side closer; architecture.md §6).

This prep IS the workspace-close tool's action: it resolves the target branch (a branch name
verbatim, or an issue number via the GitHub-linked branch / the issue's PR head), then composes
``workspace._build_remove_work`` — teardown hooks best-effort, then the gated ``git worktree
remove``. Dirty or unpushed state is a decision (``AMBIGUOUS``), never a silent discard; removal
attempted from INSIDE the target worktree is ``WORKSPACE_MISMATCH`` (``cwd_inside_target``).

The routine post-merge path (the review-M2 fix, generalized): squash-merge +
delete-branch-on-merge makes a merged branch's commits count "unpushed" against the ``origin/main``
fallback, so the remove core needs the merged PR's ``{number, head_oid}`` to clear a clean worktree
sitting exactly at the merged head (and to give a merged-specific card, never the nonsensical "push
first" wording, when EXTRA local commits sit past it). That lookup is **lazy and argument-form
agnostic**: the remove core runs first, and only a "clean but unpushed" ``AMBIGUOUS`` — the one
outcome a merged PR can change — triggers ``branching.find_merged_pr_for_head`` and a re-run. The
earlier version derived it only on the numeric path, which left the merged case unreachable from a
branch name — the form every evaluator merge terminal hands the operator. Laziness also keeps the
gh-free property that makes this tool the offline reclamation path for an abandoned workspace: a
clean, dirty, ``not_found``, or ``cwd_inside_target`` close from a branch name still calls no `gh`
at all, and a failed lookup degrades to the generic gate with a
``MERGED_PR_LOOKUP_UNAVAILABLE`` notice.

Branch resolution for a numeric argument, in order: (1) exactly one GitHub-linked branch
(`gh issue develop --list`) — >1 is ``AMBIGUOUS``; (2) exactly one **local work worktree** whose
branch belongs to the issue (`<N>-<slug>` / `epic/<N>-<slug>`) — >1 is ``AMBIGUOUS``; (3) the head
of the issue's most recent **open** PR, else of its most recent **closed/merged** PR — accepted
**only** when that head belongs to the issue by the same naming convention, with the open tier
consulted first (`-vN` suffixing means one issue legitimately owns both a closed `<N>-<slug>` and
an open `<N>-<slug>-v2`) and >1 belonging head WITHIN a tier ``AMBIGUOUS``; (4) none
found -> ``AMBIGUOUS`` listing what was tried, including the heads rejected by the convention. The
rung-3 guard is load-bearing: `open_prs`/`closed_prs` come from a `#<N> in:body` full-text search,
so a sibling story's PR that merely *mentions* this issue is in the candidate set, and taking
``[0]`` of it resolved (live) issue #93 to another story's branch. A non-numeric argument is taken
as the branch name verbatim, with no lookups at all.

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


def _resolve_branch_for_issue(issue_number, repo, root, scratch_dir, cwd=None):
    """Issue number -> ``(branch, via, decision_or_none, notices)`` — the four-rung ladder in the
    module docstring (`linked` / `worktree` / `pr-head`, else ``AMBIGUOUS``)."""
    notices = []
    exit_code, issue_envelope = gh_gather.run(
        str(issue_number), repo, scratch_dir=scratch_dir, env=None, stream=_DiscardStream()
    )
    if issue_envelope is not None and issue_envelope.get("status") == "needs_decision":
        return None, None, issue_envelope["decision"], notices
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
        return None, None, link_decision, notices
    if link_notice:
        notices.append(link_notice)
        linked = []

    # Rung 1: the GitHub-linked branch — the association workspace-open itself created.
    if len(linked) > 1:
        return None, None, _resolution_ambiguous(
            issue_number,
            "%d GitHub-linked branches exist for issue #%s — name the branch explicitly"
            % (len(linked), issue_number),
            candidates=linked,
        ), notices
    if linked:
        return linked[0], "linked", None, notices

    # Rung 2: local work-worktree evidence. Close is a local operation, so a worktree that exists
    # for this issue is stronger evidence than any remote search — and it needs no `gh` call.
    worktree_matches = [
        b for b in workspace.list_work_branches(root)
        if branching.branch_belongs_to_issue(b, issue_number)
    ]
    if len(worktree_matches) > 1:
        return None, None, _resolution_ambiguous(
            issue_number,
            "%d open work worktrees belong to issue #%s — name the branch explicitly"
            % (len(worktree_matches), issue_number),
            candidates=worktree_matches,
        ), notices
    if worktree_matches:
        return worktree_matches[0], "worktree", None, notices

    # Rung 3: PR heads, guarded by the naming convention. The candidate sets come from a
    # `#<N> in:body` full-text search, so a sibling story's PR mentioning this issue is in them;
    # only a head that BELONGS to the issue is evidence about it.
    open_prs = issue_envelope.get("open_prs") or []
    closed_prs, closed_decision = branching.search_closed_prs(repo, issue_number, cwd=cwd)
    if closed_decision is not None:
        return None, None, closed_decision, notices

    # Open PRs are a tier ABOVE closed/merged ones, not one pool: `-vN` collision suffixing means
    # one issue legitimately owns both a closed `<N>-<slug>` and an open `<N>-<slug>-v2`, and the
    # live PR is the one whose worktree is still in play. Ambiguity is judged WITHIN a tier — two
    # belonging heads at the same tier is a genuine "which one" only the operator can settle.
    open_heads, rejected = _split_pr_heads(open_prs, issue_number)
    if len(open_heads) > 1:
        return None, None, _resolution_ambiguous(
            issue_number,
            "%d open PR head branches belong to issue #%s — name the branch explicitly"
            % (len(open_heads), issue_number),
            candidates=open_heads,
            rejected_pr_heads=rejected,
        ), notices
    if open_heads:
        return open_heads[0], "pr-head", None, notices

    closed_heads, closed_rejected = _split_pr_heads(closed_prs, issue_number)
    rejected += [head for head in closed_rejected if head not in rejected]
    if len(closed_heads) > 1:
        return None, None, _resolution_ambiguous(
            issue_number,
            "%d closed/merged PR head branches belong to issue #%s — name the branch explicitly"
            % (len(closed_heads), issue_number),
            candidates=closed_heads,
            rejected_pr_heads=rejected,
        ), notices
    if closed_heads:
        return closed_heads[0], "pr-head", None, notices

    # Rung 4: nothing resolvable. `rejected` is surfaced so the operator sees the sibling-PR heads
    # that were deliberately NOT used, rather than wondering why a PR that mentions the issue
    # produced no branch.
    return None, None, _resolution_ambiguous(
        issue_number,
        "no branch could be resolved for issue #%s (no linked branch, no work worktree, no PR head "
        "matching `<issue>-<slug>` or `epic/<issue>-<slug>`)" % issue_number,
        rejected_pr_heads=rejected,
    ), notices


def _split_pr_heads(prs, issue_number):
    """Distinct ``headRefName``s in ``prs``, in list order, split into
    ``(belonging, rejected)`` by :func:`branching.branch_belongs_to_issue`. `prs` order is `gh`'s
    own (most recently updated first), so ``belonging[0]`` is the most recent one — the "most
    recent PR's head" the ladder promises."""
    belonging = []
    rejected = []
    for pr in prs or []:
        head = pr.get("headRefName")
        if not head:
            continue
        target = belonging if branching.branch_belongs_to_issue(head, issue_number) else rejected
        if head not in target:
            target.append(head)
    return belonging, rejected


def _resolution_ambiguous(issue_number, summary, candidates=None, rejected_pr_heads=None):
    """The one branch-resolution ``AMBIGUOUS`` shape — every rung's failure renders the same card
    (architecture.md §3's closed code set has no resolution-specific code, and this hazard is
    exactly §3's "residual, listable-options blocker")."""
    context = {"issue": issue_number}
    if candidates:
        context["candidates"] = candidates
    if rejected_pr_heads:
        context["rejected_pr_heads"] = rejected_pr_heads
    return needs_decision(
        AMBIGUOUS,
        summary=summary,
        context=context,
        options=["re-run with the branch name instead of the issue number"],
    )


def _is_clean_but_unpushed(decision):
    """True for the remove core's "clean worktree, N unpushed commits" ``AMBIGUOUS`` — the only
    gate a merged PR can clear (a dirty worktree gates regardless, and no other decision is about
    commit reachability at all)."""
    if decision is None or decision.get("code") != AMBIGUOUS:
        return False
    context = decision.get("context") or {}
    return not context.get("dirty") and (context.get("unpushed_commits") or 0) > 0


def build_facts(branch_or_issue, repo, root=".", scratch_dir=None, cwd=None):
    """Assemble the close receipt and return the envelope dict WITHOUT printing it. Returns
    ``None`` after a ``needs_decision`` envelope has already been emitted."""
    root = str(workspace._resolve_main_root(root))
    if scratch_dir is None:
        scratch_dir = "/tmp/gh-workspace-close-%s" % branch_or_issue.replace("/", "-")
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    notices = []
    if branch_or_issue.isdigit():
        branch, via, decision, notices = _resolve_branch_for_issue(
            branch_or_issue, repo, root, scratch_dir, cwd=cwd
        )
        if _forward_decision(decision, notices=notices):
            return None
    else:
        branch, via = branch_or_issue, "arg"

    invoker_cwd = Path.cwd()
    payload, _rm_notices, rm_decision = workspace._build_remove_work(
        root, branch, invoker_cwd=invoker_cwd, merged_pr=None
    )
    if _is_clean_but_unpushed(rm_decision):
        # The one outcome merged-PR context can change. Retrying is safe: the remove core returns
        # every decision BEFORE running teardown or removal, deliberately leaving the workspace
        # intact for recovery, so nothing has happened yet.
        merged_pr, merged_notice = branching.find_merged_pr_for_head(repo, branch, cwd=cwd)
        if merged_notice:
            notices.append(merged_notice)
        if merged_pr is not None:
            payload, _rm_notices, rm_decision = workspace._build_remove_work(
                root, branch, invoker_cwd=invoker_cwd, merged_pr=merged_pr
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
