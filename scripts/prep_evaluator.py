#!/usr/bin/env python3
"""prep_evaluator.py — the evaluator's complete facts block in one call (architecture.md §4;
docs/implementation.md S6). This is the **first prep script** — it pioneers the "compose the
executors in-process, one facts block" pattern S8 locks for every later prep script.

From-scratch v2 script (architecture.md §2/§9.2, docs/specs/evaluator.md): assembles the
evaluator's entire starting state — PR facts, the closing issue's DoD, gate config pinned at the
root ``main`` SHA, the CI rollup class, the health-cache hit/miss, PR-type detection, repo merge
config, and the self-review fact — as ONE JSON envelope on stdout, so the evaluator session's
state assembly is one Python process, never a subprocess chain and never more than one
model-mediated round-trip (prd.md §9.2).

Composition (architecture.md §2 "compose the executors in-process"; architecture.md §1 "the only
external processes any script may spawn are git/gh")::

    gh_pr_gather.run(...)         -- PR facts + thread + the health-cache marker comment
    gh_gather.run(..., stream=)   -- the closing issue's body + thread (per issue)
    workspace.main([...])         -- root-freshness (via "root-status") + "ensure --work" on the
                                     PR head branch
    parse.parse_dod_bullets(...)  -- the closing issue's ## Definition of done, parsed
    config_block._read_lines_or_empty / _scan_marker
                                   -- the four gate-config blocks, read at the root main SHA

The executors have an uneven composition surface (see the implementor report's "S8 retro input"
section for the write-up this uneveness produced): ``gh_gather.run`` and ``parse.py``'s functions
are clean return-a-value calls; ``gh_pr_gather.run`` and every ``workspace.py`` subcommand build
their own envelope and print it via ``pipelib.envelope.emit_ok``/``emit_needs_decision`` with NO
``stream=`` passthrough, so composing them in-process means their emit would otherwise land on
THIS script's own stdout — breaking the "exactly one JSON envelope" invariant (architecture.md
§3). ``contextlib.redirect_stdout`` around each such call captures that emit into an
``io.StringIO`` buffer instead, which this script then parses as a plain in-memory result and
never re-emits — see :func:`_capture_stdout_json` and :func:`_run_workspace_subcommand`. No
executor is modified; every composition here is capture-based (S6 brief: "Do NOT edit the
executors if capture-based in-process composition works — it does").

Usage::

    prep_evaluator.py <pr-number> <owner/repo> [--root PATH] [--scratch-dir DIR] [--refresh]

``--root`` defaults to ``.`` (the project root — architecture.md §6's read-only trust vantage).
``--scratch-dir`` defaults to ``/tmp/gh-evaluator-<pr-number>`` (CLAUDE.md's ``/tmp/gh-<skill>-
<N>/`` convention) when omitted. ``--refresh`` re-derives the volatile facts (PR state, CI rollup
class, health-cache hit/miss) without re-running ``ensure --work``'s setup hooks or re-fetching
the closing issue/gate config — architecture.md §4: "prep supports --refresh and is re-run at the
points where currency matters."

Exit codes (architecture.md §3): 0 with the facts-block envelope present (``status`` is ``"ok"``
or ``"needs_decision"``); 2 on a usage error (no envelope). Any other non-zero is an unclassified
hard `gh`/`git` failure surfaced by a composed executor — stderr carries the faithful error.
"""

import argparse
import contextlib
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_block  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
import gh_gather  # noqa: E402
import gh_pr_gather  # noqa: E402
import parse  # noqa: E402
import workspace  # noqa: E402
from pipelib import process  # noqa: E402
from pipelib.decisions import AMBIGUOUS, needs_decision  # noqa: E402
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR, emit_needs_decision, emit_ok  # noqa: E402

# Health-cache marker comment prefix (docs/specs/evaluator.md, SKILL.md:300) — self-read by
# gh_pr_gather's marker-comment lookup so the health check needs no second fetch.
HEALTH_CACHE_MARKER = "<!-- pr-evaluator-health-cache:v1 -->"

# The four gate-config marker names (docs/specs/evaluator.md), read at the root `main` SHA
# (architecture.md §6/§12: "gate config is pinned to trust ... never from a PR head").
_STATIC_CHECKS_MARKER = "pr-evaluator-static-checks"
_TEST_TARGET_MARKER = "pr-evaluator-test-target"
_ESCALATION_LABELS_MARKER = "pr-evaluator-escalation-labels"
_MERGE_POLICY_MARKER = "pr-evaluator-merge-policy"
# Legacy single-block backward-compat marker (docs/specs/evaluator.md "Known bugs/gaps",
# SKILL.md §5.4) — read alongside static-checks/test-target so prep surfaces both arms and lets
# the evaluator playbook (not this script) decide which to honor.
_LEGACY_HEALTH_CHECKS_MARKER = "pr-evaluator-health-checks"

# Candidate config files, in priority order — same discovery list workspace.py's
# `_candidate_hook_files` already uses for the worktree-setup/teardown blocks (COMMANDS.md,
# CLAUDE.md, then one level of `@`-include from either) — the docs/specs/evaluator.md config
# blocks are discovered identically ("Scan COMMANDS.md and CLAUDE.md ... and any file either
# @-includes").
_CONFIG_CANDIDATE_FILES = ("COMMANDS.md", "CLAUDE.md")

# CI rollup classification terminal-state vocabulary (docs/specs/evaluator.md §5.3, preserved
# verbatim from v1's classification rule).
_CI_RUNNING_CHECK_STATUSES = frozenset({"QUEUED", "IN_PROGRESS"})
_CI_RUNNING_CONTEXT_STATE = "PENDING"
_CI_SUCCESS_EQUIVALENT = frozenset({"SUCCESS", "SKIPPED", "NEUTRAL"})
_CI_FAILURE_EQUIVALENT = frozenset(
    {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE", "STALE"}
)

# PR-type detection patterns (docs/specs/evaluator.md §"5.5.2 test selection" / SKILL.md:254-256):
# `epic-integration` if headRefName matches `epic/<N>-<slug>` AND baseRefName == main; `story` if
# baseRefName matches `epic/<N>-<slug>`; `standard` otherwise (v1 names this bucket `regular`; the
# v2 architecture.md §4 vocabulary and this step's brief both name it `standard`).
_EPIC_BRANCH_RE = re.compile(r"^epic/\d+-.+$")

ROOT_MAIN_BRANCH = "main"


# ---------------------------------------------------------------------------
# In-process composition helpers — capture an emit-and-print executor's stdout instead of
# subprocessing it (architecture.md §1: only git/gh may be spawned as external processes; a
# `python3 <executor>.py` subprocess would be an unlisted third spawned binary).
# ---------------------------------------------------------------------------


def _capture_stdout_json(callable_with_no_return_value):
    """Run ``callable_with_no_return_value`` with stdout redirected to an in-memory buffer, then
    parse and return the single JSON envelope it printed (or ``None`` if it printed nothing).

    This is the capture technique the S6 brief names explicitly for composing an
    "emit-and-return-the-dict-but-also-print-to-real-stdout" executor
    (``gh_pr_gather.run``, whose ``emit_ok``/``emit_needs_decision`` calls carry no ``stream=``)
    without leaking its envelope onto THIS script's own stdout. Raises ``AssertionError`` if more
    than one non-blank line was printed — every composed executor's contract is "exactly one
    envelope," so more than one line means something upstream broke that contract, and prep must
    not silently swallow the extra line(s).
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        callable_with_no_return_value()
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    if not lines:
        return None
    assert len(lines) == 1, (
        "prep_evaluator: composed executor printed %d lines, expected exactly one envelope: %r"
        % (len(lines), lines)
    )
    return json.loads(lines[0])


def _run_workspace_subcommand(argv):
    """Compose ``workspace.py`` in-process: call ``workspace.main(argv)`` under stdout capture and
    return ``(exit_code, envelope_or_none)``. ``workspace.py`` has no clean testable-core /
    ``stream=`` split (unlike ``gh_gather.run``), so its CLI entrypoint is composed directly —
    this exercises the exact same argument-parsing + dispatch path a real subprocess invocation
    would use, just without the second Python process (architecture.md §2/§9.2).
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = workspace.main(argv)
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    if not lines:
        return exit_code, None
    assert len(lines) == 1, (
        "prep_evaluator: workspace.py %r printed %d lines, expected exactly one envelope: %r"
        % (argv, len(lines), lines)
    )
    return exit_code, json.loads(lines[0])


def _forward_decision_if_present(envelope):
    """If ``envelope`` (from a composed executor) is a ``needs_decision`` envelope, emit it
    AS-IS on prep's own stdout (this is prep's one and only envelope for this run) and return
    ``True``. Otherwise return ``False`` so the caller continues assembling facts.

    This is how ``MARKER_AMBIGUOUS`` (gh_pr_gather / gh_gather), ``AUTH_REQUIRED`` (any gh call),
    ``ROOT_NOT_ON_MAIN``/``ROOT_DIRTY``/``ROOT_DIVERGED``/``BRANCH_IN_USE`` (workspace.py), and
    ``DOD_MALFORMED`` (parse.py, raised in-process — see :func:`_parse_closing_issue_dod`)
    propagate through prep untouched, per architecture.md §3's closed decision-code set: a
    composed executor's decision IS prep's decision, verbatim, never re-derived or reworded.
    """
    if envelope is not None and envelope.get("status") == "needs_decision":
        emit_needs_decision(envelope["decision"], notices=envelope.get("notices"))
        return True
    return False


# ---------------------------------------------------------------------------
# Gate-config discovery at the root `main` SHA (architecture.md §6/§12 "gate config is pinned to
# trust"). `--root` IS already the root main checkout (architecture.md §6: "project root ...
# always clean main"); prep reads these blocks directly from the root working tree rather than
# from any PR-head copy, and records the root SHA the read was pinned at.
# ---------------------------------------------------------------------------


def _find_includes_one_level(file_path):
    """One-level `@`-include scan, matching workspace.py's `_find_includes` (module-private there,
    re-derived here as a tiny local helper rather than importing a private function across module
    boundaries for a two-line regex scan)."""
    path = Path(file_path)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    return [
        tok
        for tok in re.findall(r"@([A-Za-z0-9._/-]+)", text)
        if re.search(r"(/|\.[A-Za-z0-9]+$)", tok)
    ]


def _candidate_config_files(root):
    root_path = Path(root)
    candidates = [root_path / name for name in _CONFIG_CANDIDATE_FILES]
    for root_file in list(candidates):
        for inc in _find_includes_one_level(root_file):
            inc_path = Path(inc)
            candidates.append(inc_path if inc_path.is_absolute() else root_path / inc)
    return candidates


def _read_block_anywhere(root, marker_name):
    """Read the first well-formed ``<!-- marker_name -->`` block across the candidate config
    files (same discover-first-match-wins rule workspace.py's hook blocks use). Composes
    ``config_block``'s own non-emitting scan primitives directly — never its CLI/``sys.exit``
    surface (``run_read``) and never re-implements the marker scan (S6 brief: "you may also call
    their non-emitting helper functions directly, as workspace.py already composes config_block's
    _scan_marker in-process").

    Returns ``(present, interior_lines, source_file_or_none)``.
    """
    for candidate in _candidate_config_files(root):
        lines = config_block._read_lines_or_empty(str(candidate))
        open_count, close_count, open_index, close_index = config_block._scan_marker(
            lines, marker_name
        )
        if open_count == 0:
            continue
        if open_count > 1 or close_count > 1:
            continue  # ambiguous in this file — try the next candidate, matching workspace.py's rule
        if open_count != close_count or close_index < open_index:
            continue  # unterminated/inverted in this file — try the next candidate
        interior = lines[open_index:close_index - 1]
        return True, interior, str(candidate)
    return False, [], None


_COMMAND_LIST_ITEM_RE = re.compile(r"^\s*-\s*`([^`]*)`")
_MERGE_POLICY_LINE_RE = re.compile(r"^\s*-\s*([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(ask|auto)\s*$")


def _parse_backtick_command_list(interior_lines):
    """One backtick-quoted command per Markdown list item — the shared shape
    ``pr-evaluator-static-checks``, ``pr-evaluator-escalation-labels``, and the legacy
    ``pr-evaluator-health-checks`` block all use (docs/specs/evaluator.md; SKILL.md §5.4), the
    exact same per-line grammar ``workspace.py``'s ``_parse_command_list`` already applies to
    worktree-hook blocks — restated locally so this module has no cross-module dependency on a
    workspace.py private helper for an unrelated block family."""
    items = []
    for line in interior_lines:
        match = _COMMAND_LIST_ITEM_RE.match(line)
        if match:
            items.append(match.group(1))
    return items


def _parse_merge_policy(interior_lines):
    """``- <pr-type>: ask|auto`` per line (docs/specs/evaluator.md; SKILL.md:479-483). Returns a
    dict keyed by PR type. Unparseable lines (blank, prose) are skipped, not fatal — the merge
    policy block has no closed decision-code the way ``dod``/``phases`` do (architecture.md §3
    names no MERGE_POLICY_MALFORMED code), so a stray non-conforming line is simply not a policy
    entry, matching v1's own tolerant Markdown-list reading rather than a strict grammar.
    """
    policy = {}
    for line in interior_lines:
        match = _MERGE_POLICY_LINE_RE.match(line)
        if match:
            policy[match.group(1)] = match.group(2)
    return policy


def _read_gate_config(root):
    """Read all four gate-config blocks (plus the legacy single-block fallback) once, at the
    caller-verified root `main` SHA. Returns the ``config`` facts-block sub-object (without
    ``sha``, added by the caller once the root SHA is known) plus a ``notices`` list for
    graceful-degradation cases the evaluator playbook should know about (e.g. "legacy block
    only") — mirroring architecture.md §3's ``notices: []`` channel for non-blocking
    degradations. Never itself asks the operator anything (gates-only-for-decisions,
    architecture.md §9); an absent test-target or static-checks block is a fact for the
    evaluator playbook to gate on, not a prep-time decision.
    """
    notices = []

    static_present, static_lines, static_source = _read_block_anywhere(root, _STATIC_CHECKS_MARKER)
    test_target_present, test_target_lines, test_target_source = _read_block_anywhere(
        root, _TEST_TARGET_MARKER
    )
    escalation_present, escalation_lines, _escalation_source = _read_block_anywhere(
        root, _ESCALATION_LABELS_MARKER
    )
    merge_policy_present, merge_policy_lines, _merge_policy_source = _read_block_anywhere(
        root, _MERGE_POLICY_MARKER
    )
    legacy_present, legacy_lines, legacy_source = _read_block_anywhere(
        root, _LEGACY_HEALTH_CHECKS_MARKER
    )

    if not static_present and legacy_present:
        # Backward-compat: treat the legacy flat list as the static-checks list and note the
        # degradation (docs/specs/evaluator.md "Known bugs/gaps": "legacy single-block path
        # always runs the full command list") — the evaluator playbook, not prep, decides whether
        # to skip test-selection on this arm; prep only surfaces the fact + notice.
        notices.append("LEGACY_HEALTH_CHECKS_BLOCK")

    static_checks = _parse_backtick_command_list(static_lines) if static_present else (
        _parse_backtick_command_list(legacy_lines) if legacy_present else []
    )
    escalation_labels = _parse_backtick_command_list(escalation_lines) if escalation_present else []
    merge_policy = _parse_merge_policy(merge_policy_lines) if merge_policy_present else {}
    # epic-integration is never configurable — always "ask" regardless of block content
    # (docs/specs/evaluator.md: "Epic-integration merges are always gated ... hardcoded, not
    # configurable"). Set unconditionally, after parsing, so a stray `epic-integration:` line in
    # the block can never override it.
    merge_policy["epic-integration"] = "ask"

    config = {
        "static_checks": static_checks,
        "static_checks_present": static_present,
        "test_target_present": test_target_present,
        "test_target_raw": "\n".join(test_target_lines) if test_target_present else None,
        "test_target_source": test_target_source,
        "escalation_labels": escalation_labels,
        "merge_policy": merge_policy,
        "merge_policy_present": merge_policy_present,
        "legacy_health_checks_present": legacy_present,
        "legacy_health_checks_source": legacy_source,
    }
    return config, notices


# ---------------------------------------------------------------------------
# CI rollup classification (docs/specs/evaluator.md §5.3) — green / red / pending / none.
# ---------------------------------------------------------------------------


def _classify_ci_rollup(status_check_rollup):
    """Classify ``statusCheckRollup`` (the raw list from gh_pr_gather's PR fetch) into exactly one
    of ``green`` / ``red`` / ``pending`` / ``none``, plus the failing-check-name list when red.
    Preserves v1's exact terminal-state vocabulary (docs/specs/evaluator.md §5.3) — this is a
    CLASSIFICATION only; prep never blocks/watches a pending rollup to settle it (v1's own rule:
    "Do NOT route this through github-ops ... run it from the main loop" — the v2 analogue is
    "not synchronously inside a one-shot prep script"; the evaluator playbook is what decides
    whether/how to wait, using this fact as its starting point).
    """
    if not status_check_rollup:
        return "none", []

    has_running = False
    has_failing = False
    fail_checks = []
    for entry in status_check_rollup:
        status = entry.get("status")
        conclusion = entry.get("conclusion")
        state = entry.get("state")  # status-context shape uses `state` instead of `status`/`conclusion`
        if (status is not None and status in _CI_RUNNING_CHECK_STATUSES) or (
            state == _CI_RUNNING_CONTEXT_STATE
        ) or (status == "COMPLETED" and conclusion is None and state is None):
            has_running = True
            continue
        terminal_value = conclusion if conclusion is not None else state
        if terminal_value in _CI_FAILURE_EQUIVALENT:
            has_failing = True
            fail_checks.append(entry.get("name") or entry.get("context") or "(unnamed check)")
        elif terminal_value in _CI_SUCCESS_EQUIVALENT:
            continue
        else:
            # An unrecognized terminal value defaults to "still settling" rather than silently
            # counting as green or red — matching the spirit of v1's exhaustive enumeration
            # (docs/specs/evaluator.md §5.3 names every value explicitly; an unnamed value is
            # never assumed success-equivalent).
            has_running = True

    if has_running:
        return "pending", []
    if has_failing:
        return "red", fail_checks
    return "green", []


# ---------------------------------------------------------------------------
# PR-type detection (docs/specs/evaluator.md; SKILL.md:254-256).
# ---------------------------------------------------------------------------


def _detect_pr_type(base_ref_name, head_ref_name):
    if _EPIC_BRANCH_RE.match(head_ref_name or "") and base_ref_name == ROOT_MAIN_BRANCH:
        return "epic-integration"
    if _EPIC_BRANCH_RE.match(base_ref_name or ""):
        return "story"
    return "standard"


# ---------------------------------------------------------------------------
# Health-cache marker SHA compare (docs/specs/evaluator.md; SKILL.md:131-134).
# ---------------------------------------------------------------------------

_CACHE_SHA_LINE_RE = re.compile(r"^SHA:\s*([0-9a-f]+)\s*$", re.MULTILINE)


def _health_cache_fact(pr_envelope, head_sha):
    """Build the ``health_cache`` fact from the PR envelope's marker-comment fields (populated by
    ``gh_pr_gather.run`` when called with ``marker=HEALTH_CACHE_MARKER``). ``hit`` iff a marker
    comment is present and its embedded ``SHA:`` line equals the current PR head SHA
    (architecture.md §4: "hit iff the cached SHA == PR head SHA").
    """
    if not pr_envelope.get("marker_comment_present"):
        return {"sha": None, "hit": False}

    marker_body = pr_envelope.get("marker_comment") or pr_envelope.get("marker_comment_body")
    if marker_body is None and pr_envelope.get("marker_comment_mode") == "path":
        marker_body = Path(pr_envelope["marker_comment_path"]).read_text(encoding="utf-8")
    match = _CACHE_SHA_LINE_RE.search(marker_body or "")
    cached_sha = match.group(1) if match else None
    return {"sha": cached_sha, "hit": cached_sha is not None and cached_sha == head_sha}


# ---------------------------------------------------------------------------
# Repo merge config + self-review (new prep-owned gh calls — no existing executor covers these;
# architecture.md §1 permits any script to spawn `git`/`gh` directly via pipelib.process.run).
# ---------------------------------------------------------------------------

_AUTH_REQUIRED_OPTIONS = ["run: gh auth login"]


def _auth_decision(result):
    from pipelib.decisions import AUTH_REQUIRED

    return needs_decision(
        AUTH_REQUIRED,
        summary="gh authentication required",
        context={"stderr": result.stderr, "returncode": result.returncode},
        options=_AUTH_REQUIRED_OPTIONS,
    )


def _fetch_repo_merge_config(repo, cwd):
    """``gh api repos/<owner>/<repo>`` — the five merge-capability booleans (SKILL.md:454-455).
    Returns ``(config_dict_or_none, decision_or_none)``."""
    result = process.run(["gh", "api", "repos/%s" % repo], cwd=cwd)
    if result.auth_required:
        return None, _auth_decision(result)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    data = json.loads(result.stdout)
    return {
        "allow_squash_merge": data.get("allow_squash_merge"),
        "allow_merge_commit": data.get("allow_merge_commit"),
        "allow_rebase_merge": data.get("allow_rebase_merge"),
        "delete_branch_on_merge": data.get("delete_branch_on_merge"),
        "allow_auto_merge": data.get("allow_auto_merge"),
    }, None


def _fetch_current_user(cwd):
    """``gh api user`` -> login (SKILL.md:73). Returns ``(login_or_none, decision_or_none)``."""
    result = process.run(["gh", "api", "user"], cwd=cwd)
    if result.auth_required:
        return None, _auth_decision(result)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    return json.loads(result.stdout).get("login"), None


# ---------------------------------------------------------------------------
# Closing-issue DoD (parse.py dod — a pure function; no redirect_stdout needed).
# ---------------------------------------------------------------------------


def _parse_closing_issue_dod(body_text, issue_number):
    """Compose ``parse.parse_dod_bullets`` directly (a pure function — architecture.md §2's
    cleanest composition case). Returns ``(dod_list, decision_or_none)`` — a
    ``parse._DodMalformed`` is caught here and turned into the same ``DOD_MALFORMED`` decision
    ``parse.py dod`` itself would emit as a subprocess, so composing in-process changes nothing
    about what the caller observes (S6 brief's single-envelope invariant: this decision, if any,
    becomes prep's own envelope, verbatim).
    """
    try:
        return parse.parse_dod_bullets(body_text), None
    except parse._DodMalformed as exc:
        from pipelib.decisions import DOD_MALFORMED

        decision = needs_decision(
            DOD_MALFORMED,
            summary=exc.reason,
            context={"issue": issue_number, "line_number": exc.line_number, "raw_line": exc.raw_line},
            options=[
                "fix the bullet's annotation by hand to match one of the closed-set forms in "
                "skills/_shared/dod-annotations.md, then re-run"
            ],
        )
        return None, decision


# ---------------------------------------------------------------------------
# suggested_playbook / attention / notices
# ---------------------------------------------------------------------------


def _suggested_playbook(pr_type, pr_state):
    """Map ``(pr_type, pr_state)`` to the suggested playbook filename (architecture.md §5: "Prep
    proposes (suggested_playbook); the router confirms against the table"). A closed/merged PR
    still gets a playbook name — the router, not prep, decides whether re-running evaluate on an
    already-closed PR makes sense; prep states the fact (`target.state`) and proposes the playbook
    matching what the PR type *would* need, since architecture.md §5's override rule exists
    precisely for "the router may override only on evidence the script cannot see."""
    if pr_type == "epic-integration":
        return "epic-integration.md"
    if pr_type == "story":
        return "story.md"
    return "standard.md"


def _build_attention(workspace_envelope, pr_envelope, blocked_by_by_issue=None):
    attention = []
    if workspace_envelope is not None:
        setup = workspace_envelope.get("setup") or {}
        if setup.get("succeeded") is False:
            first_failure = setup.get("first_failure") or {}
            attention.append(
                "work worktree setup hook failed at step %s (`%s`) — worktree exists but is not "
                "ready" % (first_failure.get("step"), first_failure.get("command"))
            )
        if workspace_envelope.get("dirty"):
            attention.append("work worktree has uncommitted changes")
        unpushed = workspace_envelope.get("unpushed_commits") or 0
        if unpushed:
            attention.append("work worktree has %d unpushed commit(s)" % unpushed)
    if pr_envelope.get("mergeStateStatus") == "BEHIND":
        attention.append("Branch is behind base — rebase or merge base before merging.")
    if pr_envelope.get("mergeStateStatus") == "DIRTY":
        attention.append("Branch has conflicts — resolve before merging.")
    if pr_envelope.get("mergeStateStatus") == "BLOCKED":
        attention.append("Merge blocked by branch protection — check status checks.")
    if pr_envelope.get("reviewDecision") == "REVIEW_REQUIRED":
        attention.append("Awaiting review from another reviewer — approval will still post, but merge may be gated.")
    if pr_envelope.get("isDraft"):
        attention.append("PR is a draft — the evaluator does not evaluate a DRAFT-state PR.")
    for issue_number, blockers in (blocked_by_by_issue or {}).items():
        open_blockers = [b for b in blockers if (b.get("state") or "").upper() == "OPEN"]
        if open_blockers:
            attention.append(
                "closing issue #%s has %d open native blocker(s) — docs/specs/evaluator.md: "
                "any open blocker holds the merge" % (issue_number, len(open_blockers))
            )
    return attention


# ---------------------------------------------------------------------------
# Facts-block assembly
# ---------------------------------------------------------------------------


def build_facts(pr_number, repo, root=".", scratch_dir=None, refresh=False, cwd=None):
    """Assemble the evaluator's complete facts block and return the envelope dict WITHOUT
    printing it (the testable core, mirroring gh_gather.run's split — main() does the printing).
    ``refresh`` re-derives PR state + CI classification + health-cache hit/miss without
    re-`ensure`-ing the work worktree (so setup hooks are not re-run) and without re-reading gate
    config (config is pinned at the root SHA already recorded on a prior run's facts, per
    architecture.md §4: "prep supports --refresh and is re-run at the points where currency
    matters" — the "matters" set for the evaluator is PR state and CI, not the gate config or
    workspace setup, per this step's Work list: "--refresh re-derives volatile facts without
    re-running hooks").
    """
    root = str(Path(root).resolve())
    if scratch_dir is None:
        scratch_dir = "/tmp/gh-evaluator-%s" % pr_number
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    # 1) PR facts (+ thread + the health-cache marker) — gh_pr_gather has no stream= passthrough,
    #    so its emit is captured via redirect_stdout rather than leaked onto our own stdout.
    pr_envelope = _capture_stdout_json(
        lambda: gh_pr_gather.run(
            pr_number,
            repo,
            marker=HEALTH_CACHE_MARKER,
            scratch_dir=scratch_dir,
            cwd=cwd,
        )
    )
    if _forward_decision_if_present(pr_envelope):
        return None  # already emitted — main() reads EXIT_OK regardless (needs_decision is exit 0)

    # 2) Root freshness + "ensure --work" on the PR head branch. workspace.py's CLI is composed
    #    directly (no testable-core split exists there) via _run_workspace_subcommand.
    #    "root-status" alone performs the freshness protocol without creating anything, so a
    #    ROOT_* decision surfaces before any worktree side effect — matching workspace.py's own
    #    "freshness failure short-circuits the whole subcommand" contract, now short-circuiting
    #    prep's own assembly the same way.
    if not refresh:
        _root_exit, root_status_envelope = _run_workspace_subcommand(
            ["root-status", "--root", root]
        )
        if _forward_decision_if_present(root_status_envelope):
            return None
        root_sha = root_status_envelope["sha"]

        ws_exit, workspace_envelope = _run_workspace_subcommand(
            [
                "ensure",
                "--work",
                pr_envelope["headRefName"],
                "--base",
                pr_envelope["baseRefName"],
                "--root",
                root,
            ]
        )
        if _forward_decision_if_present(workspace_envelope):
            return None
        if ws_exit != 0 and (workspace_envelope is None or workspace_envelope.get("setup", {}).get("succeeded", True)):
            # A hard workspace failure with no envelope at all (e.g. `git fetch`/`worktree add`
            # itself failed) — surfaced faithfully rather than silently assembling partial facts.
            sys.stderr.write(
                "prep_evaluator: workspace ensure --work failed (exit %d) with no recoverable "
                "envelope\n" % ws_exit
            )
            sys.exit(1)

        # 3) Gate config, pinned at the root main SHA just recorded.
        gate_config, config_notices = _read_gate_config(root)
        gate_config["sha"] = root_sha
    else:
        # --refresh: re-derive only PR state + CI + health-cache hit/miss. Root freshness,
        # workspace ensure (and its setup hooks), and gate config are NOT re-run/re-read — the S6
        # brief and this step's DoD are explicit that --refresh must not re-run hooks. A caller
        # that needs a workspace/config fact on a --refresh run is expected to hold onto the
        # prior full run's facts block (this is what "the router confirms against the table"
        # sessions already do — the facts block from the first prep call stays in context).
        workspace_envelope = None
        gate_config, config_notices = {}, []

    # 4) The closing issue's DoD (parse.py dod, composed as a pure function) — for each issue in
    #    closingIssuesReferences. gh_gather.run has a stream= passthrough, so no redirect needed.
    closing_issues = pr_envelope.get("closingIssuesReferences") or []
    dod_by_issue = {}
    blocked_by_by_issue = {}
    deps_available_by_issue = {}
    issue_gather_notices = []
    for closing_issue in closing_issues:
        issue_number = closing_issue.get("number")
        if issue_number is None:
            continue
        issue_stream = io.StringIO()
        issue_exit, issue_envelope = gh_gather.run(
            str(issue_number), repo, scratch_dir=scratch_dir, stream=issue_stream
        )
        if _forward_decision_if_present(issue_envelope):
            return None
        if issue_exit != 0:
            sys.stderr.write(
                "prep_evaluator: gh_gather on closing issue #%s failed (exit %d)\n"
                % (issue_number, issue_exit)
            )
            sys.exit(1)
        issue_gather_notices.extend(issue_envelope.get("notices") or [])
        issue_body = issue_envelope.get("issue_body")
        if issue_body is None and issue_envelope.get("issue_body_mode") == "path":
            issue_body = Path(issue_envelope["issue_body_path"]).read_text(encoding="utf-8")
        dod_list, dod_decision = _parse_closing_issue_dod(issue_body or "", issue_number)
        if dod_decision is not None:
            emit_needs_decision(dod_decision)
            return None
        dod_by_issue[str(issue_number)] = dod_list
        # Native issue dependencies (docs/specs/evaluator.md "Artifacts read": "Any open blocker
        # holds the merge — soft-reject") — gh_gather's base payload already carries these; the
        # evaluator playbook (not prep) decides the soft-reject, prep only surfaces the fact.
        blocked_by_by_issue[str(issue_number)] = issue_envelope.get("blocked_by") or []
        deps_available_by_issue[str(issue_number)] = issue_envelope.get("deps_available")

    # 5) Repo merge config + self-review (new prep-owned gh calls).
    merge_config, merge_decision = _fetch_repo_merge_config(repo, cwd)
    if merge_decision is not None:
        emit_needs_decision(merge_decision)
        return None
    current_user, user_decision = _fetch_current_user(cwd)
    if user_decision is not None:
        emit_needs_decision(user_decision)
        return None
    pr_author_login = (pr_envelope.get("author") or {}).get("login")
    self_review = pr_author_login is not None and pr_author_login == current_user

    # 6) CI rollup classification, PR-type detection, health-cache SHA compare.
    ci_class, ci_fail_checks = _classify_ci_rollup(pr_envelope.get("statusCheckRollup"))
    pr_type = _detect_pr_type(pr_envelope.get("baseRefName"), pr_envelope.get("headRefName"))
    health_cache = _health_cache_fact(pr_envelope, pr_envelope.get("headRefOid"))

    # 7) Assemble the facts block (architecture.md §4 common core + evaluator extensions).
    vector = {"type": pr_type, "mode": "continue", "pr_state": "open-by-you" if self_review else "open"}
    if pr_envelope.get("state") != "OPEN":
        vector["pr_state"] = pr_envelope.get("state", "unknown").lower()

    facts = {
        "repo": repo,
        "scratch": scratch_dir,
        "root": {"path": root, "sha": gate_config.get("sha"), "fresh": not refresh},
        "target": {
            "kind": "pr",
            "number": pr_envelope["number"],
            "title": pr_envelope["title"],
            "state": pr_envelope["state"],
            "labels": pr_envelope.get("labels") or [],
        },
        "vector": vector,
        "suggested_playbook": _suggested_playbook(pr_type, pr_envelope["state"]),
        "pr": {
            "headRefName": pr_envelope["headRefName"],
            "baseRefName": pr_envelope["baseRefName"],
            "headRefOid": pr_envelope["headRefOid"],
            "isDraft": pr_envelope["isDraft"],
            "author": pr_envelope.get("author"),
            "additions": pr_envelope.get("additions"),
            "deletions": pr_envelope.get("deletions"),
            "changedFiles": pr_envelope.get("changedFiles"),
            "commit_count": pr_envelope.get("commit_count"),
            "mergeStateStatus": pr_envelope.get("mergeStateStatus"),
            "mergeable": pr_envelope.get("mergeable"),
            "reviewDecision": pr_envelope.get("reviewDecision"),
            "url": pr_envelope.get("url"),
            "closingIssuesReferences": closing_issues,
        },
        "pr_type": pr_type,
        "ci": {"class": ci_class, "fail_checks": ci_fail_checks},
        "health_cache": health_cache,
        "self_review": self_review,
        "current_user": current_user,
        "config": gate_config,
        "merge_config": merge_config,
        "dod": dod_by_issue,
        "blocked_by": blocked_by_by_issue,
        "deps_available": deps_available_by_issue,
        "attention": _build_attention(workspace_envelope, pr_envelope, blocked_by_by_issue),
        "notices": list(config_notices) + list(issue_gather_notices),
    }
    if workspace_envelope is not None:
        facts["workspace"] = {
            "path": workspace_envelope["path"],
            "branch": workspace_envelope["branch"],
            "base_ref": workspace_envelope["base_ref"],
            "sha": workspace_envelope.get("sha"),
            "reused": workspace_envelope.get("reused"),
            "dirty": workspace_envelope.get("dirty"),
            "unpushed_commits": workspace_envelope.get("unpushed_commits"),
            # Carried through so a failed setup hook is visible to the evaluator playbook (also
            # surfaced as an `attention` line, per _build_attention) rather than silently
            # dropped — `sha`/`dirty`/`unpushed_commits` are null on this path (workspace.py
            # itself skips computing them when setup fails, since they describe a workspace
            # ready for use).
            "setup": workspace_envelope.get("setup"),
        }

    # Threshold-spill sections gh_pr_gather already staged (body/thread/reviews/marker_comment)
    # are surfaced by field name pass-through, per architecture.md §4's "sections{...}" example —
    # every *_mode/*_bytes/*_path (or bare inline field) gh_pr_gather produced rides through
    # unchanged, so the evaluator playbook reads them exactly as gh_pr_gather itself documents.
    sections = {}
    for key, value in pr_envelope.items():
        if key.startswith(("body", "thread", "reviews", "marker_comment", "diff", "line_comments")):
            sections[key] = value
    facts["sections"] = sections

    return facts


def main(argv):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pr", help="PR number")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("--root", default=".", help="project root (architecture.md §6 vantage)")
    parser.add_argument(
        "--scratch-dir",
        default=None,
        help="scratch dir for spilled sections (default: /tmp/gh-evaluator-<pr>)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-derive volatile facts (PR state, CI, health-cache hit) without re-running hooks",
    )
    parser.add_argument("--cwd", default=None, help="explicit cwd for the repo-merge-config/user gh calls")
    args = parser.parse_args(argv)

    facts = build_facts(
        args.pr,
        args.repo,
        root=args.root,
        scratch_dir=args.scratch_dir,
        refresh=args.refresh,
        cwd=args.cwd,
    )
    if facts is None:
        # A needs_decision envelope was already emitted by build_facts (via a composed executor's
        # forwarded decision, or a directly-raised one) — nothing left to print.
        return EXIT_OK
    # pipelib.envelope.build_ok reserves "notices" as its own top-level envelope key (populated
    # via emit_ok's notices= kwarg, never inside payload) — pop it out of the logical facts dict
    # build_facts assembled so the wire shape stays architecture.md §4's flat
    # {"status": ..., ...facts-fields..., "notices": [...]}, not a nested "notices" collision.
    notices = facts.pop("notices", [])
    emit_ok(payload=facts, notices=notices)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
