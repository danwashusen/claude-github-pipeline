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

    gh_pr_gather.build_pr_facts(...)      -- PR facts + thread + the health-cache marker comment
    gh_gather.run(..., stream=)           -- the closing issue's body + thread (per issue)
    workspace._build_attach(...)          -- assert the AMBIENT checkout IS the PR-head worktree
                                             (v3: the operator opened it via workspace-open and
                                             started this session inside it; ambient HEAD must
                                             equal pr.headRefOid — never health-check or cache
                                             against code the checkout doesn't contain)
    parse.parse_dod_bullets(...)          -- the closing issue's ## Definition of done, parsed
    refblocks.fetch_pin / read_block_at_ref
                                          -- the origin/main pin + the four gate-config blocks,
                                             read from the pinned BLOBS — never any working tree,
                                             so a PR cannot weaken its own gates

Every executor exposes a **pure, non-emitting core** — ``build_*(...) -> (payload, notices,
decision|None)`` — as of the S8 pattern lock (docs/specs/baseline.md §5): ``gh_pr_gather``,
``workspace`` (per subcommand), and ``config_block`` were retrofitted alongside the already-pure
``parse.py`` / ``gh_gather.run(stream=)`` references. This prep composes those cores **directly**
and acts on each core's returned ``decision`` channel (:func:`_forward_decision`),
emitting exactly one envelope of its own. The S6 pilot's ``contextlib.redirect_stdout`` capture
bridge — needed only because those executors used to emit-and-exit with no returnable core — is
**retired**: no prep captures another script's stdout, and no later prep may reintroduce it (§5
retro's rule for S9+).

Usage::

    prep_evaluator.py <pr-number> <owner/repo> [--root PATH] [--scratch-dir DIR] [--refresh]

``--root`` defaults to ``.`` and is normalized to the MAIN checkout via
``workspace._resolve_main_root`` — under v3 the session (and therefore the ambient cwd) sits
INSIDE the PR-head worktree. ``--scratch-dir`` defaults to ``/tmp/gh-evaluator-<pr-number>``
(CLAUDE.md's ``/tmp/gh-<skill>-<N>/`` convention) when omitted. ``--refresh`` re-derives the
volatile facts (PR state, CI rollup class, health-cache hit/miss) without re-asserting the
workspace, re-running the setup hooks, or re-reading the gate config — architecture.md §4: "prep
supports --refresh and is re-run at the points where currency matters."

Exit codes (architecture.md §3): 0 with the facts-block envelope present (``status`` is ``"ok"``
or ``"needs_decision"``); 2 on a usage error (no envelope). Any other non-zero is an unclassified
hard `gh`/`git` failure surfaced by a composed executor — stderr carries the faithful error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_block  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
import gh_gather  # noqa: E402
import gh_pr_gather  # noqa: E402
import parse  # noqa: E402
import refblocks  # noqa: E402  (origin/main pin + at-ref gate-config reads)
import workspace  # noqa: E402
from pipelib import process  # noqa: E402
from pipelib.decisions import AMBIGUOUS, needs_decision  # noqa: E402
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR, emit_needs_decision, emit_ok  # noqa: E402

# Health-cache marker comment prefix (docs/specs/evaluator.md "Artifacts written") — self-read by
# gh_pr_gather's marker-comment lookup so the health check needs no second fetch.
HEALTH_CACHE_MARKER = "<!-- pr-evaluator-health-cache:v1 -->"

# The four gate-config marker names (docs/specs/evaluator.md), read at the root `main` SHA
# (architecture.md §6/§12: "gate config is pinned to trust ... never from a PR head").
_STATIC_CHECKS_MARKER = "pr-evaluator-static-checks"
_TEST_TARGET_MARKER = "pr-evaluator-test-target"
_ESCALATION_LABELS_MARKER = "pr-evaluator-escalation-labels"
_MERGE_POLICY_MARKER = "pr-evaluator-merge-policy"
# Legacy single-block backward-compat marker (docs/specs/evaluator.md "Known bugs/gaps",
# docs/specs/evaluator.md "Legacy config: health checks") — read alongside static-checks/test-target
# so prep surfaces both arms and lets
# the evaluator playbook (not this script) decide which to honor.
_LEGACY_HEALTH_CHECKS_MARKER = "pr-evaluator-health-checks"

# Candidate config files, in priority order — same discovery list workspace.py's
# `_candidate_hook_files` already uses for the worktree-setup/teardown blocks (COMMANDS.md,
# CLAUDE.md, then one level of `@`-include from either) — the docs/specs/evaluator.md config
# blocks are discovered identically ("Scan COMMANDS.md and CLAUDE.md ... and any file either
# @-includes"). `config_block.read_block_anywhere` (S12 promotion) defaults to this exact tuple, so
# this module no longer needs its own copy of the discovery loop — see the "Gate-config discovery"
# section below.

# CI rollup classification terminal-state vocabulary (docs/specs/evaluator.md §5.3, preserved
# verbatim from v1's classification rule).
_CI_RUNNING_CHECK_STATUSES = frozenset({"QUEUED", "IN_PROGRESS"})
_CI_RUNNING_CONTEXT_STATE = "PENDING"
_CI_SUCCESS_EQUIVALENT = frozenset({"SUCCESS", "SKIPPED", "NEUTRAL"})
_CI_FAILURE_EQUIVALENT = frozenset(
    {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE", "STALE"}
)

# PR-type detection patterns (docs/specs/evaluator.md "PR-type classification"):
# `epic-integration` if headRefName matches `epic/<N>-<slug>` AND baseRefName == main; `story` if
# baseRefName matches `epic/<N>-<slug>`; `standard` otherwise (v1 names this bucket `regular`; the
# v2 architecture.md §4 vocabulary and this step's brief both name it `standard`).
_EPIC_BRANCH_RE = re.compile(r"^epic/\d+-.+$")

ROOT_MAIN_BRANCH = "main"


# ---------------------------------------------------------------------------
# In-process composition (architecture.md §2 "compose the executors in-process"; §1: only git/gh
# may be spawned as external processes — a `python3 <executor>.py` subprocess would be an unlisted
# third spawned binary). As of the S8 pattern lock (docs/specs/baseline.md §5) every executor
# exposes a pure, non-emitting `build_*(...) -> (payload, notices, decision|None)` core, so this
# prep calls those cores DIRECTLY and forwards a returned decision to its own single envelope —
# the S6 `redirect_stdout`/`io.StringIO` capture bridge is retired.
# ---------------------------------------------------------------------------


class _DiscardStream:
    """A minimal write-sink for ``gh_gather.run(stream=...)`` — the one remaining executor prep
    composes that emits-through-a-``stream=`` (its accepted-reference shape, S8 retro §5) while
    ALSO returning ``(exit, envelope)``. prep consumes only the returned envelope, so the emit is
    routed here and discarded rather than captured into a buffer — no ``io.StringIO``, no
    ``redirect_stdout``. Implements just the ``write``/``flush`` surface
    :func:`pipelib.envelope.emit` touches on a stream without a ``.buffer`` attribute."""

    def write(self, _data):
        return None

    def flush(self):
        return None


def _forward_decision(decision, notices=None):
    """Emit a composed core's returned ``decision`` (a ``pipelib.decisions`` code dict) AS-IS on
    prep's own stdout — this is prep's one and only envelope for the run — and return ``True`` when
    a decision was present, else ``False`` so the caller continues assembling facts.

    This is how ``MARKER_AMBIGUOUS`` (gh_pr_gather / gh_gather), ``AUTH_REQUIRED`` (any gh call),
    ``ROOT_NOT_ON_MAIN``/``ROOT_DIRTY``/``ROOT_DIVERGED``/``BRANCH_IN_USE`` (workspace.py), and
    ``DOD_MALFORMED`` (parse.py, raised in-process — see :func:`_parse_closing_issue_dod`)
    propagate through prep untouched, per architecture.md §3's closed decision-code set: a composed
    core's decision IS prep's decision, verbatim, never re-derived or reworded.
    """
    if decision is not None:
        emit_needs_decision(decision, notices=notices)
        return True
    return False


# ---------------------------------------------------------------------------
# Gate-config discovery at the root `main` SHA (architecture.md §6/§12 "gate config is pinned to
# trust"). `--root` IS already the root main checkout (architecture.md §6: "project root ...
# always clean main"); prep reads these blocks directly from the root working tree rather than
# from any PR-head copy, and records the root SHA the read was pinned at.
#
# The multi-file candidate-discovery loop itself (COMMANDS.md, CLAUDE.md, one-level `@`-include,
# first well-formed block wins) is `config_block.read_block_anywhere` (S12 promotion) — this module
# used to carry its own copy (byte-identical to prep_resolver.py's), duplicated a third time by
# prep_planner.py; both preps now compose the shared, tested helper directly (architecture.md §2's
# in-process composition) instead.
# ---------------------------------------------------------------------------

_COMMAND_LIST_ITEM_RE = re.compile(r"^\s*-\s*`([^`]*)`")
_MERGE_POLICY_LINE_RE = re.compile(r"^\s*-\s*([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(ask|auto)\s*$")


def _parse_backtick_command_list(interior_lines):
    """One backtick-quoted command per Markdown list item — the shared shape
    ``pr-evaluator-static-checks``, ``pr-evaluator-escalation-labels``, and the legacy
    ``pr-evaluator-health-checks`` block all use (docs/specs/evaluator.md "Legacy config: health
    checks"), the
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
    """``- <pr-type>: ask|auto`` per line (docs/specs/evaluator.md "Config: merge policy"). Returns a
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


def _read_gate_config(root, pin_sha):
    """Read all four gate-config blocks (plus the legacy single-block fallback) once, at the
    ``origin/main`` pin (v3: refblocks blob reads — never any working tree, so a PR-branch
    session cannot weaken the gates that judge it). Returns the ``config`` facts-block sub-object
    (without ``sha``, added by the caller from the same pin) plus a ``notices`` list for
    graceful-degradation cases the evaluator playbook should know about (e.g. "legacy block
    only") — mirroring architecture.md §3's ``notices: []`` channel for non-blocking
    degradations. Never itself asks the operator anything (gates-only-for-decisions,
    architecture.md §9); an absent test-target or static-checks block is a fact for the
    evaluator playbook to gate on, not a prep-time decision.
    """
    notices = []

    static_present, static_lines, static_source = refblocks.read_block_at_ref(
        root, pin_sha, _STATIC_CHECKS_MARKER
    )
    test_target_present, test_target_lines, test_target_source = refblocks.read_block_at_ref(
        root, pin_sha, _TEST_TARGET_MARKER
    )
    escalation_present, escalation_lines, _escalation_source = refblocks.read_block_at_ref(
        root, pin_sha, _ESCALATION_LABELS_MARKER
    )
    merge_policy_present, merge_policy_lines, _merge_policy_source = refblocks.read_block_at_ref(
        root, pin_sha, _MERGE_POLICY_MARKER
    )
    legacy_present, legacy_lines, legacy_source = refblocks.read_block_at_ref(
        root, pin_sha, _LEGACY_HEALTH_CHECKS_MARKER
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
    "Do NOT route this through the executor sub-agent ... run it from the main loop" — the v2 analogue is
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
# PR-type detection (docs/specs/evaluator.md "PR-type classification").
# ---------------------------------------------------------------------------


def _detect_pr_type(base_ref_name, head_ref_name):
    if _EPIC_BRANCH_RE.match(head_ref_name or "") and base_ref_name == ROOT_MAIN_BRANCH:
        return "epic-integration"
    if _EPIC_BRANCH_RE.match(base_ref_name or ""):
        return "story"
    return "standard"


# ---------------------------------------------------------------------------
# Health-cache marker SHA compare (docs/specs/evaluator.md "Health-cache marker (self-read)").
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
    """``gh api repos/<owner>/<repo>`` — the five merge-capability booleans
    (docs/specs/evaluator.md "Repo merge config").
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
    """``gh api user`` -> login (docs/specs/evaluator.md "Self-approval pre-check").
    Returns ``(login_or_none, decision_or_none)``."""
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
    # Normalize to the MAIN checkout: under v3 the session — and therefore any relative --root —
    # sits inside the PR-head worktree. NOT on --refresh: that path touches no git at all (its
    # contract is "never requires a root"), so it must not spawn the normalizing rev-parse either.
    root = str(Path(root).resolve()) if refresh else str(workspace._resolve_main_root(root))
    if scratch_dir is None:
        scratch_dir = "/tmp/gh-evaluator-%s" % pr_number
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    # 1) PR facts (+ thread + the health-cache marker) — compose gh_pr_gather's pure core
    #    directly; its returned decision (AUTH_REQUIRED / MARKER_AMBIGUOUS) becomes prep's own.
    pr_envelope, _pr_notices, pr_decision = gh_pr_gather.build_pr_facts(
        pr_number,
        repo,
        marker=HEALTH_CACHE_MARKER,
        scratch_dir=scratch_dir,
        cwd=cwd,
    )
    if _forward_decision(pr_decision):
        return None  # already emitted — main() reads EXIT_OK regardless (needs_decision is exit 0)

    # 2) Workspace ASSERTION on the PR head branch (v3) — the operator opened the worktree
    #    (workspace-open) and started this session inside it; prep verifies the ambient checkout
    #    IS that worktree, at exactly the PR's head OID (require_exact: the evaluator must never
    #    health-check, diff-read, or cache against code the checkout doesn't contain — a stale or
    #    diverged checkout is WORKSPACE_MISMATCH(stale_checkout), a decision, never a silent
    #    proceed), and re-runs the setup hooks from the same origin/main pin the gate config
    #    reads (pin once, read many).
    if not refresh:
        pin_sha = refblocks.fetch_pin(root)

        workspace_envelope, _ws_notices, ws_decision = workspace._build_attach(
            cwd if cwd is not None else ".",
            pr_envelope["headRefName"],
            base_for_unpushed=pr_envelope["baseRefName"],
            run_hooks=True,
            pin_sha=pin_sha,
            expected_remote_sha=pr_envelope["headRefOid"],
            require_exact_remote_sha=True,
        )
        if _forward_decision(ws_decision):
            return None
        # A setup-hook failure is a partial-but-honest payload (setup.succeeded == False) that the
        # evaluator playbook reads off `workspace.setup` + an `attention` line — never a hard exit.
        # A hard git failure already sys.exit(1)'d inside the core with faithful stderr and no
        # envelope (§3), so there is nothing to guard for here anymore.

        # 3) Gate config, read at the origin/main pin just fetched.
        gate_config, config_notices = _read_gate_config(root, pin_sha)
        gate_config["sha"] = pin_sha
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
    #    closingIssuesReferences. gh_gather.run is the accepted-reference emit-through-a-stream
    #    executor (S8 retro §5): it returns (exit, envelope) and emits into a discard sink so its
    #    envelope never reaches prep's own stdout — no io.StringIO/redirect_stdout capture.
    closing_issues = pr_envelope.get("closingIssuesReferences") or []
    dod_by_issue = {}
    blocked_by_by_issue = {}
    deps_available_by_issue = {}
    issue_gather_notices = []
    for closing_issue in closing_issues:
        issue_number = closing_issue.get("number")
        if issue_number is None:
            continue
        issue_exit, issue_envelope = gh_gather.run(
            str(issue_number), repo, scratch_dir=scratch_dir, stream=_DiscardStream()
        )
        if issue_envelope is not None and issue_envelope.get("status") == "needs_decision":
            if _forward_decision(issue_envelope["decision"], notices=issue_envelope.get("notices")):
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
        "root": {"path": root, "sha": gate_config.get("sha"), "source": "origin/main", "fresh": not refresh},
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
        # v3: the OBSERVED ambient checkout (attach), asserted at exactly pr.headRefOid.
        # `base_ref` is the PR's own baseRefName — a derived fact (attach cannot observe a base).
        facts["workspace"] = {
            "path": workspace_envelope["path"],
            "branch": workspace_envelope["branch"],
            "expected_branch": workspace_envelope.get("expected_branch"),
            "base_ref": pr_envelope["baseRefName"],
            "sha": workspace_envelope.get("sha"),
            "dirty": workspace_envelope.get("dirty"),
            "unpushed_commits": workspace_envelope.get("unpushed_commits"),
            "source": "ambient",
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
