#!/usr/bin/env python3
"""gh_persist.py — the single write path for GitHub issue/PR persistence (architecture.md §7),
ported from ``gh-persist.sh`` (v1) under the architecture.md §3 envelope.

Subcommands (unchanged surface from v1 — same names, same flags, same positional order):

    gh_persist.py create     <repo> <body_path> --title <title> [--label L]...
                              [--blocked-by <nums/urls>] [--blocking <nums/urls>] [--dry-run]
    gh_persist.py edit-body  <repo> <issue>     <body_path>                      [--dry-run]
    gh_persist.py link       <repo> <issue>
                              [--add-blocked-by N]... [--remove-blocked-by N]...
                              [--add-blocking N]...   [--remove-blocking N]...     [--dry-run]
    gh_persist.py comment    <repo> <target> <id> <body_path>
                              [--review-action approve|comment|request-changes]
                              [--delete-marker-id <id>]                            [--dry-run]
    gh_persist.py close      <repo> <issue> [--reason completed|"not planned"]     [--dry-run]
    gh_persist.py reopen     <repo> <issue>                                        [--dry-run]

``<target>`` for ``comment`` is one of: issue | pr | pr-review. ``--review-action`` is required
when target=pr-review and forbidden otherwise.

The body the script posts is the byte stream the *caller* already staged to its own scratch dir
(the drafter's ``/tmp/gh-drafter-<slug>/story-N.md``, the planner's ``/tmp/gh-planner-<N>/plan.md``,
etc. — v2: prep-script / playbook scratch dirs, same convention). Nothing re-serializes the body
across a prompt boundary — this closes the #626/#627 empty-body race (see ``_verify_body_file``
below) exactly as v1's leading ``test -s`` did; the only change here is that failing the gate is
now a ``needs_decision`` envelope (architecture.md §3: "needs_decision is a valid outcome, not an
error") rather than v1's bare ``exit 2`` + stderr line, because ``EMPTY_BODY_FILE`` is a §3 closed
decision code with a canonical emitter of this script.

``create --blocked-by/--blocking`` and ``link`` set GitHub's NATIVE issue dependencies (gh >= 2.95
+ the repo feature enabled). They are capability-gated by ATTEMPTING the real write and classifying
its stderr (see ``_is_deps_error``) — not a ``--help`` probe, which can't tell a repo with the
feature disabled from one that has it, nor a broken gh from an unsupported one. On a
deps-capability failure the dependency is dropped with a ``DEPS_UNSUPPORTED`` notice (create
retries without it — a failed create is atomic, so no double-file) and the caller links via prose
(``Blocked by #N`` in the body) as the always-available fallback. Any OTHER failure surfaces via
the pipelib runner's ``AUTH_REQUIRED`` classification or a hard failure (non-zero exit, no
envelope). ``link`` changes relationships only; it writes no body, so it has no empty-body gate.

Exit codes (architecture.md §3 — the only two forms this script uses):
    0   envelope present on stdout; consult ``status`` (``ok`` or ``needs_decision`` — both are
        exit 0; ``needs_decision`` is not an error).
    2   usage error (malformed invocation) — no envelope; argparse's own ``error()`` path.

A hard `gh` failure that is not itself classified into a decision code (not auth, not a deps
capability miss) propagates as this script's own non-zero, non-0/2 exit with `gh`'s stderr
forwarded verbatim and no envelope guaranteed — architecture.md §3's "any other non-zero: hard
failure; stderr carries the faithful error; no envelope is guaranteed."
"""

import argparse
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipelib import process  # noqa: E402  (import after sys.path setup, by necessity)
from pipelib.decisions import AUTH_REQUIRED, DEPS_UNSUPPORTED, EMPTY_BODY_FILE, needs_decision  # noqa: E402
from pipelib.envelope import EXIT_OK, emit_needs_decision, emit_ok  # noqa: E402
from pipelib.hashing import sha256_hex_file  # noqa: E402

# Precise capability signature for a deps-unsupported `gh` failure — ported verbatim from v1's
# is_deps_error (gh-persist.sh: `grep -qiE 'unknown (flag|json field)|issue[ -]?dependenc'`). The
# installed gh predates the --blocked-by/--blocking/--add-* flags, OR the repo hasn't enabled the
# issue-dependencies feature. A real `re` pattern (not a substring-marker approximation) so the
# separator-optional `issue[ -]?dependenc` clause (space, hyphen, OR no separator at all) is
# matched exactly the same as the bash regex would, not just the two spellings that happen to look
# likely. Match ONLY these two forms — err toward SURFACING: a real error we don't match fails
# loudly (safe, self-explanatory), whereas a non-deps error we wrongly match would be silently
# swallowed as a benign "use prose" (dangerous — a caller never learns the write failed).
# Deliberately does NOT match bare "blocking"/"dependency"/"blocked-by" — those appear in
# unrelated relationship-integrity errors (e.g. "#5 is already blocking this issue") that MUST
# surface.
_DEPS_ERROR_PATTERN = re.compile(r"unknown (flag|json field)|issue[ -]?dependenc", re.IGNORECASE)


def _is_deps_error(stderr_text):
    return bool(_DEPS_ERROR_PATTERN.search(stderr_text or ""))


def _quote_cmd(argv):
    """Shell-quote each arg for a faithfully-reproducible --dry-run preview string. shlex.quote
    is the POSIX-portable stdlib equivalent of v1's `printf '%q'` (bash-specific) — this must run
    identically on macOS and Linux (architecture.md §1).
    """
    return " ".join(shlex.quote(a) for a in argv)


class _OrderedLinkFlagAction(argparse.Action):
    """Records every --add/remove-blocked-by/blocking occurrence, in the exact interleaved order
    the caller passed them on the command line, into a single shared ``args.link_edit_flags``
    list of ``(flag, value)`` pairs.

    v1 (gh-persist.sh's cmd_link) accumulates all four relationship flags into ONE bash array via
    a single ``while`` loop over the remaining args, so a caller's exact interleaving (e.g.
    ``--add-blocked-by 9 --remove-blocking 3 --add-blocking 7``) is preserved verbatim into the
    ``gh issue edit`` argv. argparse's ordinary per-destination ``action="append"`` cannot express
    this — four separate list destinations lose the *relative* order across different flag names,
    even though each destination's own internal order is fine. This action is the fix: every one
    of the four flags in the parser (below) points at this SAME action/dest, so occurrences land
    in one list in true CLI order regardless of which of the four flag names each one used.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        if not hasattr(namespace, self.dest) or getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, [])
        getattr(namespace, self.dest).append((option_string, values))


def _verify_body_file(body_path):
    """The empty-body gate (architecture.md §12, #626/#627 empty-body race): the caller stages the
    verbatim body to ``body_path`` and passes only the path — never the bytes — across the prompt
    boundary. This check runs *before* any `gh` call, so the failure mode that bit #626/#627 (an
    in-agent Write-vs-Bash race landing an empty body on `gh issue create --body-file`) is
    unrepresentable here: there is no intermediate file this script populates, only one the caller
    already wrote.

    Returns ``None`` when the file exists and is non-empty. Returns the ``needs_decision`` payload
    (``EMPTY_BODY_FILE``) otherwise — the caller emits it and returns EXIT_OK without touching
    `gh`. (v1 exited 2 with a bare stderr line here; §3 makes EMPTY_BODY_FILE a proper decision
    code, so v2 emits it as a normal needs_decision envelope at exit 0 instead.)
    """
    path = Path(body_path)
    if not path.is_file():
        return needs_decision(
            EMPTY_BODY_FILE,
            summary="staged body file not found: %s" % body_path,
            context={"body_path": str(body_path), "reason": "not found"},
            options=["re-stage the verbatim body to %s and retry" % body_path],
        )
    if path.stat().st_size == 0:
        return needs_decision(
            EMPTY_BODY_FILE,
            summary="staged body file is empty: %s" % body_path,
            context={"body_path": str(body_path), "reason": "zero bytes"},
            options=["re-stage the verbatim body to %s and retry" % body_path],
        )
    return None


def _write_receipt_fields(body_path):
    """Byte-fidelity fields for a body-bearing write (architecture.md §3/§12): ``body_bytes`` +
    ``body_sha256`` computed directly from the staged file on disk — the same bytes `gh` was
    handed via ``--body-file`` — so a caller can verify byte-for-byte without re-reading GitHub's
    copy back (§12: "a zero exit with a URL is authoritative and is never re-read to verify").
    """
    data = Path(body_path).read_bytes()
    return {"body_bytes": len(data), "body_sha256": sha256_hex_file(body_path)}


def _auth_decision(result):
    return needs_decision(
        AUTH_REQUIRED,
        summary="gh authentication required",
        context={"stderr": result.stderr, "returncode": result.returncode},
        options=["run: gh auth login"],
    )


# ---- create ----


def _cmd_create(args):
    gate = _verify_body_file(args.body_path)
    if gate is not None:
        emit_needs_decision(gate)
        return EXIT_OK

    cmd = ["gh", "issue", "create", "--repo", args.repo, "--title", args.title,
           "--body-file", args.body_path]
    for label in args.label or []:
        cmd += ["--label", label]

    dep_flags = []
    if args.blocked_by:
        dep_flags += ["--blocked-by", args.blocked_by]
    if args.blocking:
        dep_flags += ["--blocking", args.blocking]

    if args.dry_run:
        preview = cmd + dep_flags
        # v1's emit_envelope computes body_bytes/body_sha256 unconditionally, dry-run or not (it
        # hashes the caller-staged file directly — no `gh` round-trip needed for that, since
        # there's nothing to verify a write against yet). Preserved here: a dry-run preview still
        # reports what WOULD be posted, byte-for-byte, not just the command line.
        payload = {"op": "create", "dry_run": True, "would_run": _quote_cmd(preview)}
        payload.update(_write_receipt_fields(args.body_path))
        emit_ok(payload=payload)
        return EXIT_OK

    notices = []
    if not dep_flags:
        result = process.run(cmd, cwd=args.cwd)
        if result.auth_required:
            emit_needs_decision(_auth_decision(result))
            return EXIT_OK
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            return 1
        url = result.stdout.strip()
    else:
        # Attempt WITH native dependencies first; on a deps-capability failure (old gh, or the
        # repo hasn't enabled the feature) retry WITHOUT them and signal DEPS_UNSUPPORTED so the
        # caller links via prose. A failed create is atomic (nothing is filed), so the retry
        # can't double-file — ported verbatim from v1's cmd_create.
        attempt = process.run(cmd + dep_flags, cwd=args.cwd)
        if attempt.auth_required:
            emit_needs_decision(_auth_decision(attempt))
            return EXIT_OK
        if attempt.returncode == 0:
            url = attempt.stdout.strip()
        elif _is_deps_error(attempt.stderr):
            # Retry without deps. If THIS fails (a new, non-deps reason), surface it — never claim
            # "created without them" ahead of a create that didn't actually happen.
            retry = process.run(cmd, cwd=args.cwd)
            if retry.auth_required:
                emit_needs_decision(_auth_decision(retry))
                return EXIT_OK
            if retry.returncode != 0:
                sys.stderr.write(retry.stderr)
                return 1
            url = retry.stdout.strip()
            notices.append(DEPS_UNSUPPORTED)
        else:
            sys.stderr.write(attempt.stderr)
            return 1

    payload = {"op": "create", "dry_run": False, "url": url}
    payload.update(_write_receipt_fields(args.body_path))
    emit_ok(payload=payload, notices=notices)
    return EXIT_OK


# ---- edit-body ----


def _cmd_edit_body(args):
    gate = _verify_body_file(args.body_path)
    if gate is not None:
        emit_needs_decision(gate)
        return EXIT_OK

    cmd = ["gh", "issue", "edit", args.issue, "--repo", args.repo, "--body-file", args.body_path]

    if args.dry_run:
        # See _cmd_create's matching comment: v1's emit_envelope reports body_bytes/body_sha256
        # unconditionally, dry-run or not.
        payload = {"op": "edit-body", "dry_run": True, "would_run": _quote_cmd(cmd)}
        payload.update(_write_receipt_fields(args.body_path))
        emit_ok(payload=payload)
        return EXIT_OK

    result = process.run(cmd, cwd=args.cwd)
    if result.auth_required:
        emit_needs_decision(_auth_decision(result))
        return EXIT_OK
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return 1

    payload = {"op": "edit-body", "dry_run": False, "url": result.stdout.strip()}
    payload.update(_write_receipt_fields(args.body_path))
    emit_ok(payload=payload)
    return EXIT_OK


# ---- link ----


def _cmd_link(args, parser):
    # args.link_edit_flags is a list of (flag, value) pairs in the exact interleaved order the
    # caller passed them (see _OrderedLinkFlagAction) — flatten to a plain argv tail, preserving
    # that order exactly as v1's single bash while-loop did.
    edit_flags = []
    for flag, value in args.link_edit_flags or []:
        edit_flags += [flag, value]

    # A link with no relationship flags is a caller error (a dropped/empty flag list upstream) —
    # fail loudly (usage error) rather than return a silent no-op success that looks like the
    # relationship was set. Ported verbatim from v1's cmd_link.
    if not edit_flags:
        parser.error("link requires at least one --add/remove-blocked-by/blocking flag")

    cmd = ["gh", "issue", "edit", args.issue, "--repo", args.repo] + edit_flags

    if args.dry_run:
        emit_ok(payload={
            "op": "link",
            "issue": args.issue,
            "dry_run": True,
            "changed": True,
            "deps_unsupported": False,
            "would_run": _quote_cmd(cmd),
        })
        return EXIT_OK

    result = process.run(cmd, cwd=args.cwd)
    if result.auth_required:
        emit_needs_decision(_auth_decision(result))
        return EXIT_OK
    if result.returncode == 0:
        emit_ok(payload={
            "op": "link",
            "issue": args.issue,
            "dry_run": False,
            "changed": True,
            "deps_unsupported": False,
            "url": result.stdout.strip(),
        })
        return EXIT_OK

    if _is_deps_error(result.stderr):
        # `link` writes no body, so a rejected attempt changes nothing — nothing to roll back
        # (unlike create, there is no without-deps retry: relationship-only, so "without deps"
        # would be an empty edit). Reported as a no-op success + notice, mirroring v1's cmd_link.
        emit_ok(payload={
            "op": "link",
            "issue": args.issue,
            "dry_run": False,
            "changed": False,
            "deps_unsupported": True,
        }, notices=[DEPS_UNSUPPORTED])
        return EXIT_OK

    sys.stderr.write(result.stderr)
    return 1


# ---- comment ----


def _cmd_comment(args, parser):
    if args.target in ("issue", "pr") and args.review_action:
        parser.error("--review-action is forbidden when target is '%s'" % args.target)
    if args.target == "pr-review" and not args.review_action:
        parser.error("--review-action is required when target is 'pr-review'")

    gate = _verify_body_file(args.body_path)
    if gate is not None:
        emit_needs_decision(gate)
        return EXIT_OK

    if args.target == "issue":
        cmd = ["gh", "issue", "comment", args.id, "--repo", args.repo, "--body-file", args.body_path]
    elif args.target == "pr":
        cmd = ["gh", "pr", "comment", args.id, "--repo", args.repo, "--body-file", args.body_path]
    else:  # pr-review
        cmd = ["gh", "pr", "review", args.id, "--repo", args.repo,
               "--%s" % args.review_action, "--body-file", args.body_path]

    if args.dry_run:
        # See _cmd_create's matching comment: v1's emit_envelope reports body_bytes/body_sha256
        # unconditionally, dry-run or not.
        payload = {"op": "comment", "dry_run": True, "would_run": _quote_cmd(cmd)}
        payload.update(_write_receipt_fields(args.body_path))
        emit_ok(payload=payload)
        return EXIT_OK

    # POST the new comment first, THEN delete the old marker (post-then-delete). If the post
    # fails, we return before ever attempting the delete — the prior marker comment is left
    # intact, so a failed revise never destroys the existing decision/plan comment with no
    # replacement. This ordering is the invariant (architecture.md §12: "a crash must not lose the
    # marker") — ported verbatim from v1's cmd_comment; do not reorder these two calls.
    result = process.run(cmd, cwd=args.cwd)
    if result.auth_required:
        emit_needs_decision(_auth_decision(result))
        return EXIT_OK
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return 1
    url = result.stdout.strip()

    notices = []
    if args.delete_marker_id:
        delete_cmd = ["gh", "api", "-X", "DELETE",
                      "repos/%s/issues/comments/%s" % (args.repo, args.delete_marker_id)]
        delete_result = process.run(delete_cmd, cwd=args.cwd)
        if delete_result.returncode != 0:
            # Best-effort: the new comment already posted (see above), so a delete failure here
            # never loses the record — the stale duplicate surfaces as marker_comment_count > 1 on
            # the next gather (recoverable), strictly safer than losing the marker. Surfaced as a
            # notice, not a decision or a hard failure — ported from v1's stderr WARN line.
            notices.append(
                "WARN: posted new comment but could not delete prior marker comment %s "
                "(a stale duplicate may remain)" % args.delete_marker_id
            )

    payload = {"op": "comment", "dry_run": False, "url": url}
    payload.update(_write_receipt_fields(args.body_path))
    emit_ok(payload=payload, notices=notices)
    return EXIT_OK


# ---- close / reopen ----


def _cmd_close(args):
    # Bodyless state change — no empty-body gate (architecture.md §7: "close/reopen idempotency").
    # `close` on an already-closed issue is a `gh` no-op, which is what makes this safe for a
    # reentrant caller (e.g. question-resolver re-running after an interrupted session).
    cmd = ["gh", "issue", "close", args.issue, "--repo", args.repo]
    if args.reason:
        cmd += ["--reason", args.reason]

    if args.dry_run:
        emit_ok(payload={"op": "close", "issue": args.issue, "dry_run": True,
                          "would_run": _quote_cmd(cmd)})
        return EXIT_OK

    result = process.run(cmd, cwd=args.cwd)
    if result.auth_required:
        emit_needs_decision(_auth_decision(result))
        return EXIT_OK
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return 1

    emit_ok(payload={"op": "close", "issue": args.issue, "dry_run": False, "closed": True})
    return EXIT_OK


def _cmd_reopen(args):
    # Sibling of _cmd_close for the reentrant case where a prematurely-closed question must be
    # reopened before its decision is revised. No --reason, no empty-body gate.
    cmd = ["gh", "issue", "reopen", args.issue, "--repo", args.repo]

    if args.dry_run:
        emit_ok(payload={"op": "reopen", "issue": args.issue, "dry_run": True,
                          "would_run": _quote_cmd(cmd)})
        return EXIT_OK

    result = process.run(cmd, cwd=args.cwd)
    if result.auth_required:
        emit_needs_decision(_auth_decision(result))
        return EXIT_OK
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return 1

    emit_ok(payload={"op": "reopen", "issue": args.issue, "dry_run": False, "reopened": True})
    return EXIT_OK


# ---- argument parsing ----


def _build_parser():
    """Returns ``(parser, subparsers_by_name)`` — the second element lets ``main()`` pass a
    subcommand's OWN parser (not the top-level one) to ``_cmd_link``/``_cmd_comment`` for their
    ``.error()`` calls, so a usage error reports that subcommand's specific usage line rather than
    the generic top-level one listing all six subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="gh_persist.py",
        description="Single write path for GitHub issue/PR persistence (architecture.md §7).",
    )
    parser.add_argument(
        "--cwd", default=None,
        help="working directory for the underlying git/gh calls (cwd discipline: never rely on "
             "ambient cwd; callers pass this explicitly derived from their own arguments)",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)
    subparsers_by_name = {}

    p_create = sub.add_parser("create")
    p_create.add_argument("repo")
    p_create.add_argument("body_path")
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--label", action="append", default=[])
    p_create.add_argument("--blocked-by", default="")
    p_create.add_argument("--blocking", default="")
    p_create.add_argument("--dry-run", action="store_true")

    p_edit = sub.add_parser("edit-body")
    p_edit.add_argument("repo")
    p_edit.add_argument("issue")
    p_edit.add_argument("body_path")
    p_edit.add_argument("--dry-run", action="store_true")

    p_link = sub.add_parser("link")
    p_link.add_argument("repo")
    p_link.add_argument("issue")
    # All four relationship flags share one dest/action (_OrderedLinkFlagAction) so their
    # occurrences land in a single list in true CLI order — see that class's docstring for why
    # this must not be four separate action="append" destinations.
    for flag in ("--add-blocked-by", "--remove-blocked-by", "--add-blocking", "--remove-blocking"):
        p_link.add_argument(flag, dest="link_edit_flags", action=_OrderedLinkFlagAction, metavar="N")
    p_link.add_argument("--dry-run", action="store_true")

    p_comment = sub.add_parser("comment")
    p_comment.add_argument("repo")
    p_comment.add_argument("target", choices=["issue", "pr", "pr-review"])
    p_comment.add_argument("id")
    p_comment.add_argument("body_path")
    p_comment.add_argument("--review-action", choices=["approve", "comment", "request-changes"],
                            default=None)
    p_comment.add_argument("--delete-marker-id", default=None)
    p_comment.add_argument("--dry-run", action="store_true")

    p_close = sub.add_parser("close")
    p_close.add_argument("repo")
    p_close.add_argument("issue")
    p_close.add_argument("--reason", choices=["completed", "not planned"], default=None)
    p_close.add_argument("--dry-run", action="store_true")

    p_reopen = sub.add_parser("reopen")
    p_reopen.add_argument("repo")
    p_reopen.add_argument("issue")
    p_reopen.add_argument("--dry-run", action="store_true")

    subparsers_by_name.update(
        {
            "create": p_create,
            "edit-body": p_edit,
            "link": p_link,
            "comment": p_comment,
            "close": p_close,
            "reopen": p_reopen,
        }
    )
    return parser, subparsers_by_name


def main(argv):
    parser, subparsers_by_name = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "create":
        return _cmd_create(args)
    if args.subcommand == "edit-body":
        return _cmd_edit_body(args)
    if args.subcommand == "link":
        # Pass the link sub-parser (not the top-level one) for its .error() calls, so a usage
        # error (e.g. "no relationship flags given") reports link's own usage line, not the
        # generic top-level one listing all six subcommands.
        return _cmd_link(args, subparsers_by_name["link"])
    if args.subcommand == "comment":
        return _cmd_comment(args, subparsers_by_name["comment"])
    if args.subcommand == "close":
        return _cmd_close(args)
    return _cmd_reopen(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
