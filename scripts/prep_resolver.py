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
    workspace._build_attach / _build_ensure_read   -- assert the AMBIENT checkout is the expected
                                                       work worktree (v3: the operator opened it
                                                       via workspace-open and started this session
                                                       inside it; prep observes + asserts, never
                                                       creates) and, for Epic/Story, the audit
                                                       read workspace
    config_block.read_block_anywhere               -- the three resolver-side gate-config blocks
                                                       (+ the pr-evaluator fallback chain), read
                                                       from the asserted work workspace's WORKING
                                                       TREE — the operator's checkout is the
                                                       trusted source (architecture.md §6)
    parse.parse_phases / parse.parse_dod_bullets / parse.parse_oq_links
                                                    -- the plan's ## Phases, the issue's
                                                       ## Definition of done, and its
                                                       ## Open questions section

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

``--root`` defaults to ``.`` and is normalized to the MAIN checkout via
``workspace._resolve_main_root`` — under v3 the session (and therefore the ambient cwd) sits
INSIDE the work worktree, and every derived path (the audit ``ro-*`` view, scratch staging) must
land relative to the main checkout regardless. ``--scratch-dir`` defaults to
``/tmp/gh-resolver-<issue-number>`` (CLAUDE.md's ``/tmp/gh-<skill>-<N>/`` convention) when
omitted. ``--refresh`` re-derives the volatile facts (issue/PR state, branch discovery) without
re-asserting the workspace, re-running the setup hooks, or re-reading the three gate-config
blocks — mirroring ``prep_evaluator.py``'s ``--refresh`` contract (architecture.md §4: "prep
supports --refresh and is re-run at the points where currency matters").

Exit codes (architecture.md §3): 0 with the facts-block envelope present (``status`` is ``"ok"``
or ``"needs_decision"``); 2 on a usage error (no envelope). Any other non-zero is an unclassified
hard `gh`/`git` failure surfaced by a composed executor — stderr carries the faithful error.

``vector.mode`` is a THREE-value closed set — ``"continue"`` / ``"gated"`` / ``"fresh"`` — not the
two-value fresh/continue an earlier revision of this module used. ``"gated"`` is a deliberate
distinct value (never an overload of ``"fresh"``): docs/specs/resolver.md's prior-PR state table
("Fresh/continue mode from the prior-PR state table") makes an open PR by ANOTHER author (active
or stale) — and a DRAFT PR by another author, which that table's Draft row scopes to "the same
author," not any draft — operator-gated
via `AskUserQuestion` with NO work in the checkout until the operator decides. This prep therefore
reports ``mode: "gated"`` plus a ``vector.gate`` fact block (``reason``, the exact
`AskUserQuestion` ``header``/``options`` S10 renders verbatim, and the driving ``prior_pr`` fact)
and does **not** assert the ambient workspace or derive an expected branch for that row — S10's
router must render the gate on ``mode == "gated"`` and must never fall through to the
fresh-branch or continue-on-existing flow. Prep still emits ``status: "ok"`` on a gated row (this
is a flow gate, not an assembly failure — identical reasoning to the ``open_questions_gate`` hard
gate below). A **read** workspace (the audit ref) may still be assembled on a gated row since it
never touches the other author's branch; only the WORK-workspace assertion is withheld.

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
import branching  # noqa: E402  (shared branch/type/prior-PR cores; aliased below)
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

# ---------------------------------------------------------------------------
# Branch naming, type detection, epic discovery, prior-PR classification — extracted to
# `branching.py` at the v3 workspace-model inversion so `prep_workspace_open.py` (which owns
# branch creation) and this prep (which asserts the ambient branch) share ONE implementation.
# Module-level aliases keep this prep's public surface — and the direct-call tests against it —
# unchanged (the `build_oq_query = oq_tracker.build_oq_query` precedent in prep_planner.py).
# ---------------------------------------------------------------------------

_EPIC_TITLE_PREFIX_RE = branching.EPIC_TITLE_PREFIX_RE
_EPIC_BRANCH_LS_REMOTE_PATTERN = branching.EPIC_BRANCH_LS_REMOTE_PATTERN
_EPIC_BRANCH_NAME_RE = branching.EPIC_BRANCH_NAME_RE
_BRANCH_VERSION_SUFFIX_RE = branching.BRANCH_VERSION_SUFFIX_RE

_list_remote_branches = branching.list_remote_branches
_detect_type = branching.detect_type

PRIOR_PR_ROW_OPEN_YOURS = branching.PRIOR_PR_ROW_OPEN_YOURS
PRIOR_PR_ROW_OPEN_OTHER_ACTIVE = branching.PRIOR_PR_ROW_OPEN_OTHER_ACTIVE
PRIOR_PR_ROW_OPEN_OTHER_STALE = branching.PRIOR_PR_ROW_OPEN_OTHER_STALE
PRIOR_PR_ROW_DRAFT = branching.PRIOR_PR_ROW_DRAFT
PRIOR_PR_ROW_CLOSED_RESOLVED = branching.PRIOR_PR_ROW_CLOSED_RESOLVED
PRIOR_PR_ROW_CLOSED_NOT_RESOLVED = branching.PRIOR_PR_ROW_CLOSED_NOT_RESOLVED
PRIOR_PR_ROW_NONE = branching.PRIOR_PR_ROW_NONE

MODE_CONTINUE = branching.MODE_CONTINUE
MODE_GATED = branching.MODE_GATED
MODE_FRESH = branching.MODE_FRESH

_CONTINUE_ROWS = branching.CONTINUE_ROWS
_GATED_ROWS = branching.GATED_ROWS
_GATE_CARDS = branching.GATE_CARDS
_STALE_ACTIVITY_DAYS = branching.STALE_ACTIVITY_DAYS

_search_closed_prs = branching.search_closed_prs
_classify_prior_pr_row = branching.classify_prior_pr_row
_classify_open_other_activity = branching.classify_open_other_activity
compute_fresh_slug = branching.compute_fresh_slug
_discover_epic_branch = branching.discover_epic_branch
_search_parent_epic = branching.search_parent_epic
compute_branch_name = branching.compute_branch_name


# ---------------------------------------------------------------------------
# Gate-config discovery in the ambient workspace's WORKING TREE (v3.x: the origin/main pin is
# retired — the operator's checkout supplies gate config, uncommitted edits included; mirrors
# prep_evaluator's _read_gate_config shape, resolver-side marker names + fallback chain per
# docs/specs/resolver.md §P3.1).
# ---------------------------------------------------------------------------


def _read_gate_config(gate_root):
    """Read the resolver's three gate-config blocks from ``gate_root``'s working tree (the asserted
    work workspace, or the invoking checkout when no workspace was asserted), applying the
    spec's fallback chain (docs/specs/resolver.md §P3.1): `issue-resolver-fast-checks` -> (no
    fallback; static checks only); `issue-resolver-test-target` -> `pr-evaluator-test-target`;
    `issue-resolver-canonical-suite` -> `pr-evaluator-test-target`'s full-suite-command
    (approximated here as its raw text, since prep surfaces facts, not judgment about which
    sub-line is the full-suite command — the resolver playbook parses the fallback block's prose
    itself, matching v1's own "read it as natural language; don't try to parse it" instruction
    for `issue-resolver-test-target`). Absent both `issue-resolver-fast-checks` and
    `pr-evaluator-static-checks`, falls back once more to the legacy `pr-evaluator-health-checks`
    block (docs/specs/resolver.md "Fallback config blocks"'s documented worst-case chain).
    Returns `(config_dict_without_source, notices)`; each `*_source` is the absolute path of the
    file the block was read from (until v3.x these were `<sha7>:<rel_path>` at-ref strings —
    there is no ref to name any more, and the file path is what a reader can go open).
    """
    notices = []

    fast_present, fast_lines, fast_source = config_block.read_block_anywhere(gate_root, _FAST_CHECKS_MARKER)
    if not fast_present:
        fast_present, fast_lines, fast_source = config_block.read_block_anywhere(gate_root, _FALLBACK_STATIC_CHECKS_MARKER)
        if fast_present:
            notices.append("FAST_CHECKS_FALLBACK_STATIC_CHECKS")
    if not fast_present:
        fast_present, fast_lines, fast_source = config_block.read_block_anywhere(gate_root, _FALLBACK_HEALTH_CHECKS_MARKER)
        if fast_present:
            notices.append("FAST_CHECKS_FALLBACK_LEGACY_HEALTH_CHECKS")

    test_target_present, test_target_lines, test_target_source = config_block.read_block_anywhere(gate_root, _TEST_TARGET_MARKER)
    if not test_target_present:
        test_target_present, test_target_lines, test_target_source = config_block.read_block_anywhere(gate_root, _FALLBACK_TEST_TARGET_MARKER)
        if test_target_present:
            notices.append("TEST_TARGET_FALLBACK_PR_EVALUATOR")

    canonical_present, canonical_lines, canonical_source = config_block.read_block_anywhere(gate_root, _CANONICAL_SUITE_MARKER)
    if not canonical_present:
        # Fallback chain per docs/specs/resolver.md "Fallback config blocks":
        # pr-evaluator-test-target's full-suite-command line —
        # prep surfaces the raw fallback block for the playbook to extract the labelled line from
        # (this module does not parse `full-suite-command:` out of free-form prose; see the
        # function docstring).
        canonical_present, canonical_lines, canonical_source = config_block.read_block_anywhere(gate_root, _FALLBACK_TEST_TARGET_MARKER)
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


def _audit_ref(issue_type, epic_branch_name, root_branch):
    """docs/specs/resolver.md §4.5's 4-row audit-ref table: bug/feature/refactor/standard ->
    the repo's default branch; Epic-as-target -> the discovered/bootstrap epic branch; Story under
    an open parent epic -> the parent epic's branch; Story with no parent epic (or a closed one) ->
    the default branch. `epic_branch_name` is `None` for "no epic context" (standard type, or a
    story with no open parent) — in which case the ref is always the default branch, matching the
    bootstrap-path rule that the zero-match Epic-as-target audit still runs against it (the
    bootstrap branch would fork from it anyway). `root_branch` is the derived default branch
    (`workspace.default_branch`), never a hardcoded `main`.

    Returns a BARE branch name (the default branch / `"epic/42-journal"`), never an `origin/`-prefixed ref
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
        return root_branch
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
    # Normalize to the MAIN checkout: under v3 the session — and therefore any relative --root —
    # sits inside the work worktree; the audit ro-* view and the ls-remote queries key off the main
    # checkout regardless.
    root = str(workspace._resolve_main_root(root))
    root_branch = workspace.default_branch(root)
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
        # Native `parent` first (exact, no round-trip); the full-text search is the fallback for a
        # story filed before the relation was written (skills/_shared/epic-story-hierarchy.md).
        story_epic_matches, epic_decision = _search_parent_epic(
            repo, issue_number, native_parent=issue_envelope.get("parent"), cwd=cwd
        )
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

    audit_ref = _audit_ref(issue_type, epic_branch_for_audit, root_branch)

    # A gated row is a flow gate, not an assembly blocker (identical reasoning to comment_only /
    # the open-question hard gate) — prep still completes and reports `status: ok`, it just never
    # asserts (or derives an expected branch for) a WORK workspace impersonating someone else's
    # in-flight PR. `read_workspaces.audit` may still be assembled below (it's a detached,
    # reused-by-ref view of the audit target, never a branch checkout of the other author's own
    # work).
    skip_work_workspace = comment_only or mode == MODE_GATED

    # 8) Expected-branch ladder (v3) — the session runs INSIDE the worktree the operator opened
    #    (workspace-open); prep no longer mints a branch, it derives what the ambient checkout is
    #    EXPECTED to be on, then asserts it (step 9's attach). Linked-branch first: once
    #    workspace-open has pushed the branch, re-running collision naming would count that very
    #    branch via ls-remote and yield `-v2` — a guaranteed self-mismatch — so the ladder adopts
    #    existing state and only ever *words* a computed name into the mismatch card.
    expected_branch = None
    accept_branch_pattern = None
    link_notices = []
    if not refresh and not skip_work_workspace:
        if mode == MODE_CONTINUE and prior_pr_fact and prior_pr_fact.get("headRefName"):
            # (1) Continue: the prior PR's own head branch, exact.
            expected_branch = prior_pr_fact["headRefName"]
        else:
            # (2) The issue's GitHub-linked branch (gh issue develop), exact — adopt, never
            #     re-derive. Degrades with a notice where linking is unsupported.
            linked, link_notice, link_decision = branching.list_linked_branches(
                repo, issue_number, cwd=cwd
            )
            if _forward_decision(link_decision):
                return None
            if link_notice:
                link_notices.append(link_notice)
            if linked and len(linked) > 1:
                emit_needs_decision(
                    needs_decision(
                        AMBIGUOUS,
                        summary="%d GitHub-linked branches exist for issue #%s — expected at most one"
                        % (len(linked), issue_number),
                        context={"issue": issue_number, "candidates": linked},
                        options=[
                            "unlink or delete the stray branch(es), then re-run",
                            "start the session in the worktree of the branch you mean, and re-run "
                            "against the issue it belongs to",
                        ],
                    )
                )
                return None
            if linked:
                expected_branch = linked[0]
            elif issue_type == "epic":
                # (3) Epic: the discovered integration branch, exact; on bootstrap (zero matches,
                #     e.g. linking unsupported when workspace-open created it locally), accept any
                #     ambient `epic/<N>-…` — the number is the invariant.
                if epic_branch_for_audit:
                    expected_branch = epic_branch_for_audit
                else:
                    bootstrap_slug = (epic_facts or {}).get("bootstrap_slug") or ""
                    expected_branch = "epic/%s-%s" % (issue_number, bootstrap_slug)
                    accept_branch_pattern = r"^epic/%s-" % issue_number
            else:
                # (4) Standard/story: accept any ambient `<N>-…` branch — never recompute the
                #     `-vN` suffix against a branch workspace-open already pushed; the computed
                #     name is derived only to word the mismatch card.
                worded_name, _collided = compute_branch_name(
                    root, issue_number, compute_fresh_slug(issue_title)
                )
                expected_branch = worded_name
                accept_branch_pattern = r"^%s-" % issue_number

    # 9) Workspace assertion + audit view + config, per mode (skipped on --refresh, same contract
    #    as prep_evaluator's). Gate config and the attach's hook discovery both read the ambient
    #    work workspace's working tree — the same checkout the session runs in, so what the
    #    operator sees is what gates them.
    config_attention = []
    if not refresh:
        work_workspace_envelope = None
        work_base = None
        if not skip_work_workspace and expected_branch:
            work_base = (
                root_branch
                if (issue_type == "epic" or audit_ref == root_branch)
                else audit_ref
            )
            work_workspace_envelope, _ws_notices, ws_decision = workspace._build_attach(
                cwd if cwd is not None else ".",
                expected_branch,
                base_for_unpushed=work_base,
                run_hooks=True,
                accept_branch_pattern=accept_branch_pattern,
                check_remote_staleness=True,
            )
            if _forward_decision(ws_decision):
                return None

        read_workspace_envelope = None
        if not comment_only and audit_ref != root_branch:
            # Epic-as-target / story-under-open-epic: a genuinely second ref from the work
            # workspace's own branch, so a dedicated read workspace is ensured (architecture.md
            # §6: "a skill with no second view omits the key entirely" — the standard/no-epic path
            # never reaches this branch, since audit_ref == 'main' there). Script-internal ro-*
            # plumbing: the operator never opens or sees this view.
            read_workspace_envelope, _rw_notices, rw_decision = workspace._build_ensure_read(
                root, audit_ref
            )
            if _forward_decision(rw_decision):
                return None

        # The gate-config vantage: the asserted work workspace when there is one, else the
        # invoking checkout (comment-only and gated rows never assert a workspace).
        gate_root = (
            work_workspace_envelope["path"]
            if work_workspace_envelope is not None
            else workspace._toplevel_of(cwd if cwd is not None else ".")
        )
        gate_config, config_notices = _read_gate_config(gate_root)
        gate_config["source"] = workspace._hook_source_facts(gate_root, None)
        gate_config["source"].pop("file", None)  # per-block *_source names the file; this is the tree
        if gate_config["source"].get("dirty"):
            config_attention.append(
                "gate config was read from a checkout with uncommitted changes (%s) — the checks "
                "that judge this work are the ones in your working tree" % gate_root
            )
    else:
        work_workspace_envelope = None
        read_workspace_envelope = None
        work_base = None
        gate_config, config_notices = {}, []

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
        "root": {"path": root, "default_branch": root_branch, "fresh": not refresh},
        "target": {
            "kind": "issue",
            "number": issue_envelope["number"],
            "title": issue_envelope["title"],
            "state": issue_envelope["state"],
            "labels": labels,
            "blocked_by": blocked_by,
            "blocking": issue_envelope.get("blocking") or [],
            "deps_available": issue_envelope.get("deps_available"),
            # Native epic↔story hierarchy (skills/_shared/epic-story-hierarchy.md): the native source of the
            # story-set / parent-epic read the epic flow and the audit's dimension 5 consume.
            "parent": issue_envelope.get("parent"),
            "sub_issues": issue_envelope.get("sub_issues") or [],
            "sub_issues_summary": issue_envelope.get("sub_issues_summary") or {},
            "subissues_available": issue_envelope.get("subissues_available"),
        },
        "vector": vector,
        "prior_pr": prior_pr_fact,
        "plan": plan_facts,
        "phases": phases,
        "dod": dod,
        "open_questions": open_questions,
        "open_questions_gate": open_questions_gate,
        "audit_ref": audit_ref,
        "suggested_playbook": suggested_playbook,
        "config": gate_config,
        "distiller_bundle": distiller_bundle,
        "attention": _build_attention(
            work_workspace_envelope, prior_pr_row, epic_facts, story_epic_matches
        ) + config_attention,
        "notices": list(config_notices) + link_notices,
    }
    if issue_type == "epic":
        facts["epic"] = epic_facts
    elif issue_type == "story":
        facts["story"] = epic_facts

    if work_workspace_envelope is not None:
        # v3: the OBSERVED ambient checkout (attach), not a constructed worktree. `base_ref` is a
        # DERIVED fact (continue -> the audit-ref formula; story -> the epic branch; else main) —
        # attach cannot observe a base, and the create-pr step's `--base` slot consumes this.
        facts["workspace"] = {
            "path": work_workspace_envelope["path"],
            "branch": work_workspace_envelope["branch"],
            "expected_branch": work_workspace_envelope.get("expected_branch"),
            "base_ref": work_base,
            "sha": work_workspace_envelope.get("sha"),
            "dirty": work_workspace_envelope.get("dirty"),
            "unpushed_commits": work_workspace_envelope.get("unpushed_commits"),
            "source": "ambient",
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
