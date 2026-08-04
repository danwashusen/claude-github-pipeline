#!/usr/bin/env python3
"""gh_persist.py — the single write path for GitHub issue/PR persistence (architecture.md §7),
ported from ``gh-persist.sh`` (v1) under the architecture.md §3 envelope.

Subcommands (unchanged surface from v1 — same names, same flags, same positional order — plus
``create-pr``/``edit-labels``/``close-pr``, additive-only v2 extensions, see below):

    gh_persist.py create      <repo> <body_path> --title <title> [--label L]...
                               [--blocked-by <nums/urls>] [--blocking <nums/urls>]
                               [--parent <num/url>]                                 [--dry-run]
    gh_persist.py create-pr   <repo> <body_path> --title <title> --base <ref> --head <ref>
                               [--draft]                                        [--dry-run]
    gh_persist.py edit-body   <repo> <issue>     <body_path>                      [--dry-run]
    gh_persist.py edit-labels <repo> <issue>     [--add L]... [--remove L]...     [--dry-run]
    gh_persist.py link        <repo> <issue>
                               [--add-blocked-by N]... [--remove-blocked-by N]...
                               [--add-blocking N]...   [--remove-blocking N]...     [--dry-run]
    gh_persist.py comment     <repo> <target> <id> <body_path>
                               [--review-action approve|comment|request-changes]
                               [--delete-marker-id <id>]                            [--dry-run]
    gh_persist.py close       <repo> <issue> [--reason completed|"not planned"]     [--dry-run]
    gh_persist.py close-pr    <repo> <pr>     [--comment-file <path>]               [--dry-run]
    gh_persist.py reopen      <repo> <issue>                                        [--dry-run]

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

``create-pr`` (added S10, additive-only — architecture.md §2's "if a needed operation has no
script, extend a script") is the resolver's PR-open write path — the one persisted-artifact write
the v1-ported six subcommands never covered (v1's own ``gh-persist.sh create`` was ``gh issue
create`` only; the v1 resolver hand-rolled a raw ``gh pr create``, the exact Rule-7 divergence
``docs/specs/resolver.md``'s "Known bugs / gaps" flags). It mirrors ``create``'s body-bearing-write
shape exactly: the same staged-file-path convention, the same leading ``_verify_body_file`` empty-
body gate, the same unconditional ``body_bytes``/``body_sha256`` receipt (dry-run or not), the same
``--dry-run`` preview convention, and the same ``AUTH_REQUIRED`` classification via the pipelib
runner. ``--base``/``--head`` are **required and explicit** — no ambient-cwd branch inference
(architecture.md §6 "No ambient cwd"): the caller (a prep-derived fact, e.g. the work workspace's
`base_ref`) always names both ends. ``--draft`` is optional and capability-universal (every ``gh``
version /repo supports it — no capability gate needed, unlike the native-dependency flags below);
it exists because the v1 resolver's multi-phase fresh-PR-open path passes ``--draft`` and flips
draft→ready via a separate ``gh pr ready`` once every planned phase has shipped
(``docs/specs/resolver.md`` "On the last-planned-
phase-shipped handoff, flip the PR draft→ready" invariant) — that flip is the pre-existing
sanctioned raw-``gh`` PR-state toggle (architecture.md §10), unaffected by this op. No native-
dependency support (``--blocked-by``/``--blocking``) is added to ``create-pr``: GitHub's issue-
dependency feature is a construct on **issues**, not PRs — the resolver's PR-open write never sets
one.

``edit-labels`` and ``close-pr`` (added S13, additive-only — the same architecture.md §2 "if a
needed operation has no script, extend a script" precedent ``create-pr`` established at S10) close
the two v1-write-path gaps the planner cutover surfaced: v1's ``planned``-label apply
(``docs/specs/planner.md``, ``gh issue edit --add-label``) and the HARD-revise
predecessor-PR close (``skills/planner/references/revise-reconciliation.md``'s "Start
fresh", ``gh pr close --comment``). Both are additive: every existing op's behavior, argv shape, and
envelope are byte-identical, and no existing test changed.

- ``edit-labels`` is **bodyless** (no ``--body-file``, no empty-body gate — mirrors
  ``close``/``reopen``, not ``comment``): a label add/remove is a relationship edit, not a body
  write. ``--add``/``--remove`` are each repeatable; at least one of the two is required (a usage
  error otherwise, mirroring ``link``'s "at least one relationship flag" rule) so a caller can never
  mistake a no-op invocation for a successful edit. No client-side idempotency special-casing —
  same discipline as ``close``/``reopen``: ``gh issue edit --add-label`` on an already-present label,
  and ``--remove-label`` on a label the issue doesn't carry, are themselves ``gh``/GitHub-API no-op
  successes (this script performs no "is it already set" pre-check), so a re-run of a partially-
  applied edit is always safe. Known future consumers (not this step's callers): S15 (drafter) and
  S16 (researcher, the ``researched`` label) — recorded here so a later cutover doesn't re-propose
  this op from scratch.
- ``close-pr`` closes a PR with an **optional** staged comment. ``gh pr close`` has no
  ``--body-file``/``--comment-file`` flag of its own (unlike every body-bearing op above) — the
  script reads the staged ``--comment-file`` itself and forwards its bytes as ``gh pr close``'s
  ``--comment <text>`` value, so the comment still crosses the *prompt* boundary as a path (the
  #626/#627 discipline), even though it crosses the *gh-argv* boundary as text (`gh` has no file
  form here to delegate to). The empty-body gate applies **only when** ``--comment-file`` is given
  (an included comment must be non-empty); omitting the flag is a bodyless close, exactly like
  ``close``. **The comment text is a cross-skill contract, not free prose**: this op's staged text
  becomes the PR's **close comment** (``gh pr close --comment``, a genuine comment, never the PR
  body/description) — the resolver's predecessor-PR detection greps a closed PR's close comment for
  the literal phrase ``Re-plan superseded this PR`` to find the branch a HARD re-plan superseded, for
  its ``-vN`` fresh-branch suffixing (``docs/specs/resolver.md`` "Deterministic steps": "Predecessor-PR
  detection"). The planner's HARD-revise flow (``skills/planner/playbooks/revise.md``) stages that
  exact phrase, byte-faithful, before calling this op — this script does not itself construct or
  validate the phrase (it is a generic bodyless-optional-comment PR close), the same way ``comment``
  does not validate marker-prefix conventions on the bodies it posts.

``create --blocked-by/--blocking`` and ``link`` set GitHub's NATIVE issue dependencies (gh >= 2.95
+ the repo feature enabled). They are capability-gated by ATTEMPTING the real write and classifying
its stderr (see ``_is_deps_error``) — not a ``--help`` probe, which can't tell a repo with the
feature disabled from one that has it, nor a broken gh from an unsupported one. On a
deps-capability failure the dependency is dropped with a ``DEPS_UNSUPPORTED`` notice (create
retries without it — a failed create is atomic, so no double-file) and the caller links via prose
(``Blocked by #N`` in the body) as the always-available fallback. Any OTHER failure surfaces via
the pipelib runner's ``AUTH_REQUIRED`` classification or a hard failure (non-zero exit, no
envelope). ``link`` changes relationships only; it writes no body, so it has no empty-body gate.

``create --parent`` sets GitHub's NATIVE parent/sub-issue relation, so an epic's stories become
real sub-issues — the epic's sub-issue panel and its ``subIssuesSummary`` progress rollup (and the
Sub-issues progress field on a GitHub Project) are then driven by issue state itself, rather than by
a hand-maintained markdown checklist that can't self-tick. It is capability-gated the same
attempt-and-classify way (see ``_is_subissues_error``), reporting ``SUBISSUES_UNSUPPORTED`` when
dropped. Dependencies and hierarchy are INDEPENDENT relations with independent gates, so a create
carrying both descends the ``_create_flag_ladder`` rungs and names exactly which one degraded — a
reader that sees ``SUBISSUES_UNSUPPORTED`` falls back to the legacy ``## Stories`` checklist
(``skills/_shared/epic-story-hierarchy.md``), which is a different fallback from prose dependency
linking.

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
from pipelib.decisions import (  # noqa: E402
    AUTH_REQUIRED,
    DEPS_UNSUPPORTED,
    EMPTY_BODY_FILE,
    SUBISSUES_UNSUPPORTED,
    needs_decision,
)
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


# Capability signature for a sub-issue-unsupported `gh` failure — the installed gh predates
# `--parent` (added well after the >= 2.40 floor this plugin declares), or the host doesn't serve
# the parent/sub-issue relation. Same "match only these forms, err toward SURFACING" discipline as
# _DEPS_ERROR_PATTERN: a real error we don't match fails loudly; a non-capability error we wrongly
# matched would be silently swallowed as a benign "filed without the parent".
# Deliberately does NOT match a bare "parent": that word appears in ordinary relationship-integrity
# and validation errors ("the parent issue is closed", "cannot add a parent to itself") which MUST
# surface — matching it would file the story unparented while reporting a benign capability notice,
# so the caller never learns its real parenting attempt failed. An old gh rejects the flag itself
# with "unknown flag", which the first alternative already covers.
_SUBISSUES_ERROR_PATTERN = re.compile(r"unknown (flag|json field)|sub[ -]?issue", re.IGNORECASE)


def _is_subissues_error(stderr_text):
    return bool(_SUBISSUES_ERROR_PATTERN.search(stderr_text or ""))


def _create_flag_ladder(dep_flags, parent_flags):
    """The ordered ``(extra_flags, notices_for_what_was_dropped)`` attempts a `create` walks, most
    complete first.

    Native dependencies (``--blocked-by``/``--blocking``) and the native parent/sub-issue relation
    (``--parent``) gate INDEPENDENTLY — different GitHub relations, different gh versions — and
    gh's "unknown flag" phrasing doesn't reliably say which one it rejected when a create carries
    both. Rather than guess from the stderr text, descend a ladder: each rung drops one relation
    and reports exactly what it dropped. Every failed `create` is atomic (nothing is filed), so
    descending can't double-file — the same property v1's single-rung deps retry relied on.

    With no extras the ladder is a single bare attempt with no notices, so the common case stays
    one `gh` call.
    """
    ladder = [(dep_flags + parent_flags, [])]
    if dep_flags and parent_flags:
        # Can't tell which relation gh rejected — try each alone before giving up on both.
        ladder.append((dep_flags, [SUBISSUES_UNSUPPORTED]))
        ladder.append((parent_flags, [DEPS_UNSUPPORTED]))
    if dep_flags or parent_flags:
        dropped = ([DEPS_UNSUPPORTED] if dep_flags else []) + (
            [SUBISSUES_UNSUPPORTED] if parent_flags else []
        )
        ladder.append(([], dropped))
    return ladder


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

    # Native parent/sub-issue relation: files the new issue as a sub-issue of `--parent` in the SAME
    # round-trip, so an epic batch establishes the hierarchy without a follow-up write. addSubIssue
    # appends, so filing in dependency order gives the epic's sub-issue panel that order for free.
    parent_flags = ["--parent", str(args.parent)] if args.parent else []

    if args.dry_run:
        preview = cmd + dep_flags + parent_flags
        # v1's emit_envelope computes body_bytes/body_sha256 unconditionally, dry-run or not (it
        # hashes the caller-staged file directly — no `gh` round-trip needed for that, since
        # there's nothing to verify a write against yet). Preserved here: a dry-run preview still
        # reports what WOULD be posted, byte-for-byte, not just the command line.
        payload = {"op": "create", "dry_run": True, "would_run": _quote_cmd(preview)}
        payload.update(_write_receipt_fields(args.body_path))
        emit_ok(payload=payload)
        return EXIT_OK

    # Attempt WITH every native relation first; on a capability failure (old gh, or the host
    # doesn't serve that relation) descend the ladder, dropping one relation per rung and
    # signalling what was dropped so the caller falls back — prose linking for dependencies, the
    # legacy `## Stories` checklist for hierarchy. A failed create is atomic (nothing is filed), so
    # descending can't double-file — v1's cmd_create relied on the same property for its single
    # deps retry. If a rung fails for a NEW, non-capability reason, surface that instead: never
    # claim "created without them" ahead of a create that didn't actually happen.
    notices = []
    url = None
    ladder = _create_flag_ladder(dep_flags, parent_flags)
    for index, (extra_flags, dropped_notices) in enumerate(ladder):
        attempt = process.run(cmd + extra_flags, cwd=args.cwd)
        if attempt.auth_required:
            emit_needs_decision(_auth_decision(attempt))
            return EXIT_OK
        if attempt.returncode == 0:
            url = attempt.stdout.strip()
            notices = dropped_notices
            break
        is_last_rung = index == len(ladder) - 1
        capability_miss = (dep_flags and _is_deps_error(attempt.stderr)) or (
            parent_flags and _is_subissues_error(attempt.stderr)
        )
        if is_last_rung or not capability_miss:
            sys.stderr.write(attempt.stderr)
            return 1

    payload = {"op": "create", "dry_run": False, "url": url}
    payload.update(_write_receipt_fields(args.body_path))
    emit_ok(payload=payload, notices=notices)
    return EXIT_OK


# ---- create-pr ----


def _cmd_create_pr(args):
    gate = _verify_body_file(args.body_path)
    if gate is not None:
        emit_needs_decision(gate)
        return EXIT_OK

    cmd = ["gh", "pr", "create", "--repo", args.repo, "--title", args.title,
           "--body-file", args.body_path, "--base", args.base, "--head", args.head]
    if args.draft:
        cmd.append("--draft")

    if args.dry_run:
        # Same convention as every other body-bearing op: body_bytes/body_sha256 are hashed
        # straight from the staged file, so a dry-run preview reports the write receipt without a
        # live `gh` round-trip.
        payload = {"op": "create-pr", "dry_run": True, "would_run": _quote_cmd(cmd)}
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

    payload = {"op": "create-pr", "dry_run": False, "url": result.stdout.strip()}
    payload.update(_write_receipt_fields(args.body_path))
    emit_ok(payload=payload)
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


# ---- edit-labels ----


def _cmd_edit_labels(args, parser):
    # Bodyless relationship edit — no empty-body gate (mirrors close/reopen, not comment/edit-body:
    # see the module docstring's edit-labels paragraph). At least one of --add/--remove is required,
    # the same "don't silently no-op" usage-error rule `link` applies to its own relationship flags.
    if not args.add and not args.remove:
        parser.error("edit-labels requires at least one --add/--remove flag")

    cmd = ["gh", "issue", "edit", args.issue, "--repo", args.repo]
    for label in args.add or []:
        cmd += ["--add-label", label]
    for label in args.remove or []:
        cmd += ["--remove-label", label]

    if args.dry_run:
        emit_ok(payload={
            "op": "edit-labels", "issue": args.issue, "dry_run": True,
            "added": list(args.add or []), "removed": list(args.remove or []),
            "would_run": _quote_cmd(cmd),
        })
        return EXIT_OK

    result = process.run(cmd, cwd=args.cwd)
    if result.auth_required:
        emit_needs_decision(_auth_decision(result))
        return EXIT_OK
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return 1

    emit_ok(payload={
        "op": "edit-labels", "issue": args.issue, "dry_run": False,
        "added": list(args.add or []), "removed": list(args.remove or []),
        "url": result.stdout.strip(),
    })
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


# ---- close-pr ----


def _cmd_close_pr(args):
    # The comment is OPTIONAL: --comment-file given -> the empty-body gate applies to that staged
    # file (an included comment must be non-empty, per the standard body-bearing-write discipline);
    # --comment-file omitted -> bodyless close, exactly like `close` (module docstring: "close-pr
    # closes a PR with an optional staged comment").
    comment_text = None
    if args.comment_file:
        gate = _verify_body_file(args.comment_file)
        if gate is not None:
            emit_needs_decision(gate)
            return EXIT_OK
        comment_text = Path(args.comment_file).read_text(encoding="utf-8")

    cmd = ["gh", "pr", "close", args.pr, "--repo", args.repo]
    if comment_text is not None:
        # `gh pr close` has no --body-file of its own; the staged comment crosses the gh-argv
        # boundary as text (it already crossed the prompt boundary as a path — see module
        # docstring). The caller is responsible for staging the exact byte-faithful text a
        # downstream reader (e.g. the resolver's predecessor-PR detection) may grep for.
        cmd += ["--comment", comment_text]

    if args.dry_run:
        payload = {"op": "close-pr", "pr": args.pr, "dry_run": True, "would_run": _quote_cmd(cmd)}
        if args.comment_file:
            payload.update(_write_receipt_fields(args.comment_file))
        emit_ok(payload=payload)
        return EXIT_OK

    result = process.run(cmd, cwd=args.cwd)
    if result.auth_required:
        emit_needs_decision(_auth_decision(result))
        return EXIT_OK
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return 1

    payload = {
        "op": "close-pr", "pr": args.pr, "dry_run": False, "closed": True,
        "commented": comment_text is not None,
    }
    if args.comment_file:
        payload.update(_write_receipt_fields(args.comment_file))
    emit_ok(payload=payload)
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
    p_create.add_argument("--parent", default="")
    p_create.add_argument("--dry-run", action="store_true")

    p_create_pr = sub.add_parser("create-pr")
    p_create_pr.add_argument("repo")
    p_create_pr.add_argument("body_path")
    p_create_pr.add_argument("--title", required=True)
    p_create_pr.add_argument("--base", required=True)
    p_create_pr.add_argument("--head", required=True)
    p_create_pr.add_argument("--draft", action="store_true")
    p_create_pr.add_argument("--dry-run", action="store_true")

    p_edit = sub.add_parser("edit-body")
    p_edit.add_argument("repo")
    p_edit.add_argument("issue")
    p_edit.add_argument("body_path")
    p_edit.add_argument("--dry-run", action="store_true")

    p_edit_labels = sub.add_parser("edit-labels")
    p_edit_labels.add_argument("repo")
    p_edit_labels.add_argument("issue")
    p_edit_labels.add_argument("--add", action="append", default=[])
    p_edit_labels.add_argument("--remove", action="append", default=[])
    p_edit_labels.add_argument("--dry-run", action="store_true")

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

    p_close_pr = sub.add_parser("close-pr")
    p_close_pr.add_argument("repo")
    p_close_pr.add_argument("pr")
    p_close_pr.add_argument("--comment-file", default=None)
    p_close_pr.add_argument("--dry-run", action="store_true")

    p_reopen = sub.add_parser("reopen")
    p_reopen.add_argument("repo")
    p_reopen.add_argument("issue")
    p_reopen.add_argument("--dry-run", action="store_true")

    subparsers_by_name.update(
        {
            "create": p_create,
            "create-pr": p_create_pr,
            "edit-body": p_edit,
            "edit-labels": p_edit_labels,
            "link": p_link,
            "comment": p_comment,
            "close": p_close,
            "close-pr": p_close_pr,
            "reopen": p_reopen,
        }
    )
    return parser, subparsers_by_name


def main(argv):
    parser, subparsers_by_name = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "create":
        return _cmd_create(args)
    if args.subcommand == "create-pr":
        return _cmd_create_pr(args)
    if args.subcommand == "edit-body":
        return _cmd_edit_body(args)
    if args.subcommand == "edit-labels":
        # Pass edit-labels' own sub-parser for its .error() call, same rationale as link below.
        return _cmd_edit_labels(args, subparsers_by_name["edit-labels"])
    if args.subcommand == "link":
        # Pass the link sub-parser (not the top-level one) for its .error() calls, so a usage
        # error (e.g. "no relationship flags given") reports link's own usage line, not the
        # generic top-level one listing all six subcommands.
        return _cmd_link(args, subparsers_by_name["link"])
    if args.subcommand == "comment":
        return _cmd_comment(args, subparsers_by_name["comment"])
    if args.subcommand == "close":
        return _cmd_close(args)
    if args.subcommand == "close-pr":
        return _cmd_close_pr(args)
    return _cmd_reopen(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
