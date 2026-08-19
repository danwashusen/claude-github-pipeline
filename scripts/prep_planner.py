#!/usr/bin/env python3
"""prep_planner.py — the planner's complete facts block in one call (architecture.md §4;
docs/implementation.md S12; docs/specs/planner.md). Assembles the session's entire starting
state — revise detection, the `plan_ref` selection table moved into code, epic/JIT-story facts,
revise facts, the deterministic open-question tracker de-dup search (the frozen Bug (a) fix), and
the catalogue-declared grounding docs at the pinned `plan_ref` SHA — as ONE JSON envelope on stdout, so the
planner session's startup is one Python process, never a subprocess chain.

Composition (architecture.md §2 "compose the executors in-process"; §1 "the only external
processes any script may spawn are git/gh")::

    gh_gather.run(..., stream=)            -- the target issue's body/thread/plan-marker/native
                                               deps envelope (one round-trip); reused a SECOND time
                                               (still in-process) on the parent epic's issue number
                                               for "Just-in-time story planning" facts
    gh_pr_gather.build_pr_facts(...)       -- the open PR's body, ONLY in revise mode with an open
                                               PR (for the `## Phase tracker` parse/stage)
    workspace._build_root_status / _build_ensure_read
                                            -- root freshness and the ONE read workspace this skill
                                               ever gets, grounded at `plan_ref` (§6/prd §8.4: the
                                               planner is read-only — it never gets a work
                                               workspace)
    parse.parse_oq_links                    -- the issue's `## Open questions` section (the Bug (a)
                                               tracker de-dup search's input)
    parse.parse_phases                      -- the PRIOR plan's `## Phases`, for the sub-issue
                                               plan-versus-live diff. BEST-EFFORT: a malformed
                                               section is reported as a fact, never as
                                               `PHASES_MALFORMED` (step 4.5)
    doc_catalogue.read_catalogue            -- the CONSUMING repo's `<!-- doc-catalogue -->` block
                                               (its declared grounding docs), read at the grounding
                                               checkout. Replaces this module's former hardcoded
                                               four-path tuple; composes
                                               `config_block.read_block_anywhere` internally with a
                                               `docs/README.md` candidate list.
    config_block.read_block_anywhere        -- not called directly (no gate-config block the planner
                                               reads is named yet); reached through
                                               `doc_catalogue` above, and kept imported for parity
                                               with the sibling preps' composition style.

Every executor composed here exposes a **pure, non-emitting core** — ``build_*(...) -> (payload,
notices, decision|None)`` (docs/specs/baseline.md §5, the S8 pattern lock). This prep calls those
cores **directly** and forwards each core's returned ``decision`` verbatim (:func:`_forward_decision`),
emitting exactly one envelope of its own. No ``redirect_stdout``/``io.StringIO`` capture of another
script's stdout is used anywhere in this module (S9-on rule; docs/specs/baseline.md §5).

``git ls-remote --heads origin <pattern>`` (epic-branch discovery), ``gh issue list --label epic
...`` (story parent-epic search), ``gh issue view <NN> --json state,title,labels`` (per-story
live-state fetch, mirroring v1's ``GATHER_EPIC`` reconciliation), and ``gh api --paginate
repos/<owner>/<repo>/issues/<N>/sub_issues`` (the deliverable-sub-issue detail fetch, step 4.5 —
kept HERE rather than in ``gh_gather`` because six preps compose that module and only the planner
reads this fact) have no existing executor core —
architecture.md §1 permits any script to spawn `git`/`gh` directly via `pipelib.process.run`, the
same precedent `prep_resolver.py` and `prep_evaluator.py` already established for their own
prep-owned direct calls.

Usage::

    prep_planner.py <issue-number> <owner/repo> [--root PATH] [--scratch-dir PATH] [--refresh]
    prep_planner.py <issue-number> <owner/repo> --oq-query "<topic>" [--oq-query "<topic>" ...]

``--root`` defaults to ``.`` (the project root — architecture.md §6's read-only trust vantage).
``--scratch-dir`` defaults to ``/tmp/gh-planner-<issue-number>`` (CLAUDE.md's ``/tmp/gh-<skill>-
<N>/`` convention) when omitted. ``--refresh`` re-derives the volatile facts (issue/PR state,
marker detection, the open-question tracker search) without re-running root freshness or
re-ensuring the grounding read workspace — mirroring `prep_resolver.py`'s / `prep_evaluator.py`'s
identical `--refresh` contract (architecture.md §4).

Exit codes (architecture.md §3): 0 with the facts-block envelope present (``status`` is ``"ok"``
or ``"needs_decision"``); 2 on a usage error (no envelope). Any other non-zero is an unclassified
hard `gh`/`git` failure surfaced by a composed executor — stderr carries the faithful error.

``vector.mode`` is the TWO-value closed set ``"fresh"`` / ``"revise"`` (docs/specs/planner.md
"Artifacts read": "the presence of a plan comment switches you to revise mode") — derived purely
from whether the TARGET issue's own `<!-- implementation-plan:v1 -->` marker comment is present
(the same `GATHER_ISSUE` marker lookup v1's Step 2 documents). There is no third value analogous
to the resolver's ``"gated"``: the planner never withholds its one grounding read workspace behind
an operator gate — grounding is always safe (a detached, read-only view), unlike the resolver's
work worktree, which can impersonate another author's in-flight branch.

**`plan_ref` selection — the FULL v1 table (docs/specs/planner.md Step 4.5), moved into code.**
Six distinct facts (:func:`_select_plan_ref`), collapsing to the same v1 table (whose row 5
bundles two cases this module reports as two distinct, independently-testable facts) — precedence
is fixed: when more than one row applies (a story under an open epic that ALSO has an open PR),
the open-PR-head row always wins (v1's documented rationale: that head is a strict superset of the
epic branch, and is what the resolver actually continues on):

  1. ``PLAN_REF_ROW_OPEN_PR_HEAD`` — an open PR already exists for this issue -> that PR's
     `headRefName`. Checked FIRST, unconditionally, so it wins the precedence rule for free.
  2. ``PLAN_REF_ROW_EPIC_BRANCH`` — epic-as-target, `epic/<N>-<slug>` branch discovered -> that
     branch.
  3. ``PLAN_REF_ROW_EPIC_BOOTSTRAP`` — epic-as-target, zero `git ls-remote` matches -> `main`.
  4. ``PLAN_REF_ROW_STORY_PARENT_BRANCH`` — story under an OPEN parent epic, `epic/<N>-<slug>`
     branch discovered -> that branch.
  5. ``PLAN_REF_ROW_STORY_PARENT_BOOTSTRAP`` — story under an OPEN parent epic, zero
     `git ls-remote` matches (the parent epic itself hasn't bootstrapped its integration branch
     yet — no story has been resolved for it) -> `main`. **Added post-S13 (D4 fix):** the story
     branch of :func:`_select_plan_ref` previously collapsed this case into row 6 below by keying
     on branch ABSENCE alone (`epic_branch_name is None`), which is truthful for `plan_ref` itself
     (both rows fall back to `main`) but produces a self-contradictory `vector.plan_ref_row` label
     when `story.parent_epic_open` is simultaneously `true` — a fact the row name flatly denies
     ("story-no-open-parent-epic" while the parent IS open). `plan_ref`/routing behavior is
     UNCHANGED by this fix (`main`; `_suggested_playbook` keys on `parent_epic_open`, never on the
     row name — see that function); only the row's truthfulness is fixed, per architecture.md §4's
     "facts are data, never re-derived" invariant applied to the row label itself.
  6. ``PLAN_REF_ROW_STORY_NO_PARENT`` — story with NO parent epic found, or a CLOSED one -> `main`.
     Distinguished from row 5 by `parent_epic_open` (`False` here, `True` there) — both still ride
     the same `plan_ref` (`main`), but the row now says which reality produced it.
  7. ``PLAN_REF_ROW_DEFAULT`` — everything else (standalone bug/feature/incomplete/multi-phase,
     no open PR) -> `main`.

Every row (:func:`build_facts`) ends the same way regardless of which fired: an unconditional
``workspace._build_ensure_read(root, plan_ref)`` — the plan's (and eventually the handoff's)
`<plan-ref>@<short-sha>` footer sha comes from THIS read workspace's own head, never a second,
independently-derived sha. ``plan_ref`` itself always rides as a BARE branch name (`"main"` /
`"epic/1-x"` / a PR's `headRefName`), matching `prep_resolver.py`'s `audit_ref` convention — the
`origin/`-prefixed read form lives only inside `workspace.py`'s own internals, and the footer's
"`origin/main` for the default branch, bare branch name otherwise" RENDERING split is explicitly
S13's job (docs/specs/planner.md's "Read ref vs recorded ref"), not a fact this prep computes.

**Bug (a) — the deterministic open-question tracker de-dup search
(now `oq_tracker.build_open_question_candidates`; see the "S14 promotion" paragraph below).**
docs/specs/planner.md's frozen falsifiable requirement: a genuinely-filed `question` issue must
NEVER be recorded "(not filed)" in a posted plan. `open-question-detection.md` §Matching names the
exact mechanism and its query-derivation rule: run `gh issue list --repo <owner/repo> --state all
--label question --search "<query>"` for every entry the issue's own `## Open questions` section
(`parse.parse_oq_links`) currently records as `question: (not filed)` — `<query>` is
deterministically the entry's own `oq_id` (the backtick-quoted id/topic-phrase every `- OQ: `<id>`
...` line already carries; per the shared contract this is "the OQ's tracker id when it has one
... or its distinctive topic keywords when detection was heuristic" — either way, the SAME field,
no separate keyword-extraction heuristic needed). Entries whose `question` field is already `#N`
are NOT re-searched (already resolved; no "(not filed)" claim is being made). A repo/issue with no
`## Open questions` section makes ZERO `gh` calls for this fact (this step's canonical call-budget
fixture has none). Results ride verbatim as `open_question_candidates: [{"oq_id", "query",
"candidates": [{"number","title","state","labels"}, ...]}, ...]` — the planner's own prompt can
therefore never silently record "(not filed)" for an entry this fact lists without first consulting
it; :func:`_build_attention` also surfaces an unmissable `attention` line per non-empty candidate
group. For an OQ the plan detects **anew during grounding** (never in the issue body, so absent
from the body-driven search above), the ``--oq-query`` one-shot mode (now
`oq_tracker.build_oq_query`, aliased below as :func:`build_oq_query`) runs the identical search on
demand — the S13-authorized additive extension that keeps the raw `gh issue list` out of the
playbook prompt.

**Deliverable sub-issues (#18) — `slices`.** A NON-EPIC target's sub-issues are its deliverable
slices by construction (the hierarchy is epic → story → slice), so no label and no per-child
classification fetch is involved. When the target is non-epic AND has sub-issues, `facts.slices`
carries the live set (`number`, `title`, `state`, `position` — the sub-issue panel's own order, the
sequencing source of truth — `updated_at`, `maybe_rescoped`, and the body staged to a path) plus
`slices.diff`, the plan-versus-live diff computed HERE and never re-derived in a prompt:
`uncovered_open` / `closed` / `removed` / `rescoped` / `order_changed`, alongside the map facts
`mapped` / `substrate_phases` / `unmapped_phases`. Each non-empty case also surfaces an `attention`
line (:func:`_slice_attention`). `rescoped` is a SUSPICION — an issue's `updated_at` bumps on comments
and labels too, so it over-reports — with two carve-outs that stop it lying in the other direction: a
CLOSED sub-issue is excluded (closing bumps the timestamp, and closure has its own disposition), and a
served sub-issue with no usable timestamp is named in `attention` as uncovered by the comparison.
`rescope_basis` distinguishes `updated_at` (it ran) from `no_prior_plan` (nothing to compare against)
and `unavailable` (this host cannot answer). A childless target and an epic target both cost ZERO
extra `gh` calls, which is what keeps the canonical call budget unchanged.

**S14 promotion.** `_search_question_tracker` / `_build_open_question_candidates` / `build_oq_query`
were this module's own S12/S13 helpers until S14's `prep_drafter.py` needed the byte-identical
mechanism for its own search-before-file companion-question de-dup (docs/specs/drafter.md Step
3.5/R4 — the SAME deterministic query rule, not a similarly-shaped-but-distinct local `gh` call).
Unlike this module's epic-branch/parent-epic/story-state helpers (which stay local per-prep because
their shapes only coincidentally rhyme with a sibling prep's), this one **is** the literal same
algorithm serving the same shared contract (`open-question-detection.md` §Matching, named by both
`docs/specs/planner.md` and `docs/specs/drafter.md`) — so it is now `oq_tracker.py` (a new,
single-purpose module; `scripts/pipelib/` is the wrong layer, since `pipelib` must never import a
`scripts/*.py` sibling and this mechanism itself composes `parse.parse_oq_links`). This module was
refactored to call `oq_tracker.build_open_question_candidates` in-process instead of carrying its
own copy — its envelope is byte-identical (verified: `tests/test_prep_planner.py` is unmodified and
green). `build_oq_query` is kept as a module-level alias (`build_oq_query = oq_tracker.build_oq_query`)
so the one direct-call test line (`prep_planner.build_oq_query(...)`) and this module's own CLI
`--oq-query` call site keep working unchanged.

**The shared config-block reader promotion (S9-carried advisory, authorized for S12).**
`_read_block_anywhere` (plus its `_candidate_config_files`/`_find_includes_one_level` helpers) was
duplicated byte-for-byte in `prep_evaluator.py` and `prep_resolver.py`; this module would have been
the third copy. It is now `config_block.read_block_anywhere` (a public function on the ONE existing
script that already owns the config-block-reading domain — `scripts/pipelib/` is the wrong layer,
since `pipelib` must never import a `scripts/*.py` sibling), and both existing preps were refactored
to call it in-process instead of carrying their own copy — their envelopes are byte-identical
(verified: their own test suites are unmodified and green). This module imports `config_block` for
composition-style parity with the sibling preps even though it has no gate-config block of its own
to read today.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import branching  # noqa: E402  (import-only: the issue's-own-PR narrowing)
import config_block  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
import doc_catalogue  # noqa: E402  (the consuming repo's declared grounding docs)
import gh_gather  # noqa: E402
import gh_pr_gather  # noqa: E402
import oq_tracker  # noqa: E402
import parse  # noqa: E402  (the prior plan's `## Phases` parse for the sub-issue diff — best-effort,
# see step 4.5; also keeps `prep_planner.parse` resolving for tests/test_prep_planner.py's direct
# `prep_planner.parse.parse_oq_links(...)` call, per the S14-promotion's "tests unmodified" bar.
# `oq_tracker.py` is this module's OQ-search composition path)
import workspace  # noqa: E402
from pipelib import process  # noqa: E402
from pipelib.decisions import (  # noqa: E402
    AMBIGUOUS,
    AUTH_REQUIRED,
    DOC_CATALOGUE_ABSENT,
    MARKER_AMBIGUOUS,
    needs_decision,
)
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR, emit_needs_decision, emit_ok  # noqa: E402
from pipelib.spill import spill_bytes  # noqa: E402

# The implementation-plan marker (skills/planner/references/plan-schema.md;
# docs/specs/planner.md "Artifacts read") — GATHER_ISSUE's marker_prefix on both the TARGET issue
# (the revise-mode trigger) and, for a story under an open epic, the parent epic (the JIT epic
# plan the story grounds on).
PLAN_MARKER = "<!-- implementation-plan:v1 -->"

# The research-dossier marker (docs/specs/planner.md Step 4; the researcher's dossier schema).
# Detected by scanning the TARGET issue's own thread (already fully paginated by GATHER_ISSUE) —
# never a second `gh api` round-trip the way v1's Step 4 targeted fetch needed, since v2's thread
# fetch is already complete.
RESEARCH_MARKER = "<!-- issue-research:v1 -->"

# The epic-delivery-log marker (skills/_shared/epic-delivery-log.md) — read (never written) by the
# planner, staged for both an epic-as-target run (its OWN delivery log, informational) and a
# story-under-epic JIT run (the reconciliation input against the epic plan's pinned contracts).
DELIVERY_LOG_MARKER = "<!-- epic-delivery-log:v1 -->"

# Grounding docs come from the CONSUMING repo's `<!-- doc-catalogue -->` block, not from any path
# list here (`skills/_shared/doc-catalogue.md`; `scripts/doc_catalogue.py`). This prep previously
# carried a hardcoded four-path tuple, which asserted a doc layout on a repo that never agreed to
# one and disagreed with both `prep_drafter.py`'s own copy and the prompts (which name two further
# docs neither prep inventoried). The read happens INSIDE the already-ensured grounding checkout
# (a real directory at `plan_ref`) rather than via `git ls-tree -r --name-only <ref>` against a ref
# pointer — architecture.md §6's "no ref arithmetic" principle extended: once the workspace is
# ensured, a plain filesystem read is simpler and needs no second git invocation.

# State-vector `type` detection (docs/specs/resolver.md's identical rule, restated here rather than
# imported cross-prep — see the module docstring's "no prep-to-prep imports" design note in the
# implementor report): case-insensitive `epic`/`story` label match, OR a title `Epic:` prefix.
_EPIC_TITLE_PREFIX_RE = re.compile(r"^\s*epic\s*:", re.IGNORECASE)

# Epic branch pattern: `epic/<N>-<slug>` (docs/specs/planner.md Step 4.5's table).
_EPIC_BRANCH_LS_REMOTE_PATTERN = "epic/%s-*"

# `## Stories` bullet grammar (skills/drafter/references/issue-templates.md;
# docs/specs/drafter.md "Artifacts written", Epic `## Stories` row): a FILED story is
# `- [ ] #NN — <title>` / `- [x] #NN — <title>`; a PLACEHOLDER
# (not yet filed) is a plain `- [ ] <title>` bullet with no `#NN`. No shared `parse.py` subcommand
# covers this grammar (only `dod`/`oq-links`/`phases` are named in architecture.md §3's decision-
# code table) — best-effort, non-raising: a line that matches neither shape is simply not a story
# entry (a stray blank line or prose), matching every other "no dedicated decision code" block-scan
# in this codebase (workspace.py's hook blocks, this module's own `## Phase tracker` parse below).
_STORY_FILED_RE = re.compile(r"^-\s*\[( |x|X)\]\s*#(\d+)\s*(?:—|-)\s*(.+)$")
_STORY_PLAIN_RE = re.compile(r"^-\s*\[( |x|X)\]\s*(.+)$")
_SECTION_HEADING_RE = re.compile(r"^##(?!#)")

# `## Phase tracker` bullet grammar (docs/specs/resolver.md "Artifacts written"): `- [x] Phase N —
# <title> (commit <sha>)` / `- [ ] Phase N — <title>` (unshipped). Same "no dedicated decision
# code, best-effort" rationale as `_STORY_FILED_RE` above — the resolver's own §4.7 reads this
# section as prose, not through a script; this module's parse is a convenience fact, not a gate.
_PHASE_TRACKER_ROW_RE = re.compile(
    r"^-\s*\[( |x|X)\]\s*Phase\s+(\d+)\s*(?:—|-)\s*(.+?)(?:\s*\(commit\s+([0-9a-f]{7,40})\))?$"
)


# ---------------------------------------------------------------------------
# _DiscardStream / _forward_decision — identical pattern to prep_resolver.py / prep_evaluator.py
# (S8 retro §5's accepted-reference emit-through-a-stream shape for gh_gather.run).
# ---------------------------------------------------------------------------


class _DiscardStream:
    """A minimal write-sink for `gh_gather.run(stream=...)` — see `prep_evaluator._DiscardStream`
    for the full rationale (restated locally per that module's own note: sharing a two-method sink
    across prep modules is not the in-process composition architecture.md §2 asks for)."""

    def write(self, _data):
        return None

    def flush(self):
        return None


def _forward_decision(decision, notices=None):
    """Emit a composed core's returned `decision` AS-IS on prep's own stdout and return `True` when
    a decision was present. Mirrors `prep_resolver._forward_decision` / `prep_evaluator._forward_decision`
    exactly."""
    if decision is not None:
        emit_needs_decision(decision, notices=notices)
        return True
    return False


def _merge_notices(accumulated, more):
    """Append a composed core's notices to prep's own list, in first-seen order and without
    duplicates (both gh_gather calls degrade identically on a host that doesn't serve a relation, so
    the same code arrives twice).

    A prep that drops its cores' notices reports the degraded read as if it were the full one: on a
    host without the native parent/sub-issue relation, `SUBISSUES_UNSUPPORTED` is the ONLY signal
    that an empty sub-issue set means "unavailable" rather than "no children", and the planner's
    sub-issue reconciliation would otherwise skip silently.
    """
    for notice in more or []:
        if notice not in accumulated:
            accumulated.append(notice)
    return accumulated


# ---------------------------------------------------------------------------
# State-vector type detection (docs/specs/planner.md "Route by shape").
# ---------------------------------------------------------------------------


def _detect_type(labels, title):
    lowered_labels = {(label or "").strip().lower() for label in labels or []}
    if "epic" in lowered_labels or _EPIC_TITLE_PREFIX_RE.match(title or ""):
        return "epic"
    if "story" in lowered_labels:
        return "story"
    return "standard"


# ---------------------------------------------------------------------------
# git ls-remote — epic-branch discovery (no existing executor core covers this query shape;
# architecture.md §1 permits any script to spawn git/gh directly via pipelib.process.run).
# ---------------------------------------------------------------------------


def _list_remote_branches_with_sha(root, pattern):
    """`git ls-remote --heads origin <pattern>` -> sorted list of `{"branch", "sha"}` dicts (the
    `refs/heads/` prefix stripped from the branch name). Unlike `prep_resolver._list_remote_branches`
    (which discards the sha), this module needs the epic branch's head sha as a first-class fact
    ("epic branch + its head SHA" — this step's Work list) — `git ls-remote` already reports it, so
    no second call/workspace-ensure is needed just to learn it.
    """
    result = process.run(["git", "ls-remote", "--heads", "origin", pattern], cwd=str(root))
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(1)
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        sha, ref = parts
        if ref.startswith("refs/heads/"):
            entries.append({"branch": ref[len("refs/heads/") :], "sha": sha})
    return sorted(entries, key=lambda e: e["branch"])


def _discover_epic_branch(root, epic_number):
    """Discover `epic/<epic_number>-*` on origin. Returns `(facts_dict, decision_or_none)`:
      - zero matches -> `{"match_count": 0, "branch": None, "sha": None}` (bootstrap — the planner
        never creates the branch itself, so no bootstrap-slug fact is needed here the way
        `prep_resolver.py`'s identical helper computes one for branch NAMING).
      - one match -> `{"match_count": 1, "branch": <name>, "sha": <head-sha>}`.
      - multiple matches -> `(None, AMBIGUOUS decision)` (context lists every candidate).
    """
    matches = _list_remote_branches_with_sha(root, _EPIC_BRANCH_LS_REMOTE_PATTERN % epic_number)
    if len(matches) == 0:
        return {"match_count": 0, "branch": None, "sha": None}, None
    if len(matches) == 1:
        return {"match_count": 1, "branch": matches[0]["branch"], "sha": matches[0]["sha"]}, None
    return None, needs_decision(
        AMBIGUOUS,
        summary="%d candidate epic branches match 'epic/%s-*' on origin — expected at most one"
        % (len(matches), epic_number),
        context={"epic_number": epic_number, "candidates": [m["branch"] for m in matches]},
        options=[
            "pick the canonical branch and re-run with it recorded",
            "delete or rename the orphaned/duplicate branch, then re-run",
        ],
    )


def _search_parent_epic(repo, story_number, native_parent=None, cwd=None):
    """Story parent-epic lookup (docs/specs/planner.md "Route by shape"). Returns
    `(matches, decision_or_none)` where `matches` is a `gh issue list`-shaped result list (empty on
    zero genuine matches).

    Tier 1 is the native `parent` relation the caller's gather already carried — exact and
    single-valued, so it short-circuits with no round-trip and no `AMBIGUOUS` exposure
    (`skills/_shared/epic-story-hierarchy.md`).

    Tier 2 is the legacy `gh issue list --label epic --state all --search '#<N> in:body'` search,
    for a story filed before the relation was written. Filtered through
    `gh_gather.references_issue` — live evidence (see `gh_gather.py`'s module
    docstring "Open-PR search false-positive fix") showed `--search "#<N> in:body"` (the
    hash-prefixed form this call already uses) returns the SAME false-positive set as the
    bare-digit form on a `gh pr list` search; GitHub's server-side full-text search does not use
    `#` as an anchor either way, so the same client-side reference filter applies here (this
    step's live-smoke finding, recorded in docs/specs/planner.md's "Known bugs/gaps").
    """
    if native_parent:
        return [
            {
                "number": native_parent.get("number"),
                "title": native_parent.get("title"),
                "state": native_parent.get("state"),
            }
        ], None

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


def _fetch_story_state(repo, story_number, cwd=None):
    """`gh issue view <NN> --json state,title,labels` — the per-filed-story live-state fetch v1's
    `GATHER_EPIC` performs so the caller can reconcile body checkboxes against reality
    (the v1 executor agent's `GATHER_EPIC` description). Returns `(state_dict, decision_or_none)`."""
    result = process.run(
        ["gh", "issue", "view", str(story_number), "--repo", repo, "--json", "state,title,labels"],
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
    data = json.loads(result.stdout)
    return {
        "state": data.get("state"),
        "title": data.get("title"),
        "labels": [label.get("name") for label in data.get("labels") or []],
    }, None


# ---------------------------------------------------------------------------
# Deliverable sub-issues (#18) — the live slice set and the plan-versus-live diff.
#
# A NON-EPIC target's sub-issues are its deliverable slices by construction: the hierarchy is
# epic -> story -> slice, so no label and no per-child classification fetch is needed (an epic's
# sub-issues are stories, and an epic plan carries no `## Phases` at all).
#
# `gh issue view --json subIssues` serializes a FIXED node shape (`{id, number, state, title,
# url}`) with no sub-selection syntax, so it can supply neither a per-child timestamp nor a body.
# The REST list-sub-issues endpoint returns full Issue objects instead — one paginated call for the
# whole set rather than one call per child, and it carries the bodies the rescope prompt needs to
# be actionable (the planner has no scriptless raw-`gh` executor, so a "re-read it" note the prompt
# cannot act on would be useless).
# ---------------------------------------------------------------------------


# Non-blocking: the REST list-sub-issues endpoint is unavailable on this host, so the fixed
# `subIssues` node data already in hand is the fallback — numbers/titles/states survive, per-child
# timestamps and bodies do not (notices are open by contract, pipelib/decisions.py).
SUBISSUE_DETAIL_UNSUPPORTED = "SUBISSUE_DETAIL_UNSUPPORTED"


def _fetch_sub_issue_details(repo, issue_number, env=None, cwd=None):
    """`gh api --paginate repos/<owner>/<repo>/issues/<N>/sub_issues` — the full Issue object for
    every sub-issue in ONE call. Returns `(objects, notices, decision_or_none)`; `objects` is
    `None` when the endpoint is unavailable, which is a degradation (notice), not a failure.
    """
    result = process.run(
        ["gh", "api", "--paginate", "repos/%s/issues/%s/sub_issues" % (repo, issue_number)],
        env=env,
        cwd=cwd,
    )
    if result.auth_required:
        return None, [], needs_decision(
            AUTH_REQUIRED,
            summary="gh authentication required",
            context={"stderr": result.stderr, "returncode": result.returncode},
            options=["run: gh auth login"],
        )
    if result.returncode != 0:
        # A host that doesn't serve the endpoint (older GHES, a token without the scope) answers
        # 404/410 — degrade to the node data rather than failing a planning session over a fact
        # that only enriches the reconciliation. Anything else is still a hard failure. Matched on
        # the HTTP status only: bare "not found"/"gone" prose would also swallow a wrong-repo or
        # revoked-scope failure, and the caller has already read this very issue through gh_gather,
        # so a status here really does mean the endpoint.
        stderr = (result.stderr or "")
        if "404" in stderr or "410" in stderr:
            return None, [SUBISSUE_DETAIL_UNSUPPORTED], None
        sys.stderr.write(result.stderr)
        sys.exit(1)

    # Same one-or-more-concatenated-top-level-arrays tolerance as
    # gh_gather._fetch_paginated_comments: `gh api --paginate` merges pages in the common case, but
    # its documented contract is one array per page.
    decoder = json.JSONDecoder()
    text = result.stdout
    pos, length, objects = 0, len(result.stdout), []
    while pos < length:
        while pos < length and text[pos] in " \t\r\n":
            pos += 1
        if pos >= length:
            break
        page, pos = decoder.raw_decode(text, pos)
        objects.extend(page)
    return objects, [], None


def _parse_iso8601(text):
    """Parse a GitHub timestamp into a comparable `datetime`, or `None`. Compared as *datetimes*, not
    strings: github.com always emits `…Z`, but a GHES or proxy emitting `+00:00` would invert a raw
    string comparison silently (`"+"` sorts below `"Z"`), turning rescope detection off with no
    signal at all."""
    if not text:
        return None
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_slice_set(sub_issue_nodes, detail_objects, plan_updated_at, scratch_dir):
    """Assemble `slices.set` — one entry per live sub-issue, in the sub-issue panel's own order
    (`position`, the sequencing source of truth). `detail_objects` is the REST enrichment or `None`
    when unavailable, in which case the node data alone is carried.

    `maybe_rescoped` is a SUSPICION, never proof: an issue's `updated_at` bumps on comments, labels
    and assignment as well as a body rewrite, so it over-reports — and never under-reports while the
    timestamp is present and parseable. Tightening the comparison is not a fix; the prompt wording
    ("may have changed — re-read it") is what carries the uncertainty.
    """
    by_number = {}
    for obj in detail_objects or []:
        if obj.get("number") is not None:
            by_number[int(obj["number"])] = obj

    plan_stamp = _parse_iso8601(plan_updated_at)
    entries = []
    position = -1
    for node in sub_issue_nodes or []:
        number = node.get("number")
        if number is None:
            continue
        # Position is assigned over the KEPT entries: a node with no number cannot appear in a
        # phase map at all, and consuming its index would leave a hole in the very ordering
        # `order_changed` compares against.
        position += 1
        number = int(number)
        detail = by_number.get(number) or {}
        # REST states are lowercase (`open`), the GraphQL node's are upper (`OPEN`). Normalize to
        # the node spelling, which is what every other fact in this block already carries.
        state = detail.get("state") or node.get("state") or ""
        updated_at = detail.get("updated_at")
        stamp = _parse_iso8601(updated_at)
        entry = {
            "number": number,
            "title": detail.get("title") or node.get("title"),
            "state": (state or "").upper(),
            "position": position,
            "url": node.get("url") or detail.get("html_url"),
            "updated_at": updated_at,
            "maybe_rescoped": bool(stamp and plan_stamp and stamp > plan_stamp),
        }
        if detail_objects is not None:
            # force_path: a target with ten small sub-issues would otherwise put ten inline bodies
            # in the envelope. Uniform paths keep the envelope's size independent of child count.
            entry.update(
                spill_bytes(
                    (detail.get("body") or "").encode("utf-8"),
                    "body",
                    scratch_dir,
                    filename="slice-%d-body.md" % number,
                    force_path=True,
                )
            )
        entries.append(entry)
    return entries


def _build_slice_diff(slice_set, prior_phases, prior_phases_parsed, rescope_basis):
    """Compute the plan-versus-live diff from the live slice set and the PRIOR plan's parsed
    `## Phases`. Pure — no I/O, no gh, no git.

    Three states leave `computed: False` with every case list empty, because a finding *about a phase
    map* cannot exist before one does — each is reported as its own fact so a consumer never has to
    guess which it is: no prior plan at all (`prior_phases is None`, the fresh path), a prior plan
    whose `## Phases` did not parse (`prior_phases_parsed: False`), and a prior plan that carries no
    `## Phases` section (`prior_phases_present: False` — a legitimate single-phase plan; reporting
    every open sub-issue as "unserved" against a plan that has no phases would gate on a shape the
    reviewer is never asked to check). The coverage obligation itself still binds in all three — it is
    carried by the playbook and reviewer Dimension 7, not by this diff.
    """
    diff = {
        "computed": False,
        "prior_phases_parsed": prior_phases_parsed,
        "prior_phases_present": bool(prior_phases),
        "rescope_basis": rescope_basis,
        "mapped": [],
        "substrate_phases": [],
        "unmapped_phases": [],
        "closed": [],
        "removed": [],
        "rescoped": [],
        "order_changed": [],
        "uncovered_open": [],
    }
    if not prior_phases:
        return diff
    diff["computed"] = True

    live_by_number = {entry["number"]: entry for entry in slice_set}
    # Not-CLOSED rather than == OPEN: an unknown state (a node the detail fetch didn't cover, a host
    # spelling it differently) must fail SAFE — surfaced as uncovered, never silently dropped from
    # the set the map has to cover.
    open_numbers = [e["number"] for e in slice_set if e["state"] != "CLOSED"]
    position = {e["number"]: e["position"] for e in slice_set}

    served = []
    for phase in prior_phases:
        sub_issue = phase.get("sub_issue")
        if sub_issue == "(none)":
            diff["substrate_phases"].append(phase["number"])
        elif sub_issue is None:
            diff["unmapped_phases"].append(phase["number"])
        else:
            diff["mapped"].append({"phase": phase["number"], "sub_issue": sub_issue})
            served.append(sub_issue)

    served_set = set(served)
    # ONE key for one fact. A genuinely *newly added* sub-issue is indistinguishable from one the
    # plan simply never mapped: no prior snapshot of the set exists anywhere, so "open and unserved"
    # is the whole observable truth. Two keys carrying it would invite a consumer to double-report.
    diff["uncovered_open"] = [n for n in open_numbers if n not in served_set]
    diff["closed"] = sorted(
        {n for n in served_set if (live_by_number.get(n) or {}).get("state") == "CLOSED"}
    )
    diff["removed"] = sorted(n for n in served_set if n not in live_by_number)
    # A CLOSED sub-issue is excluded from `rescoped` deliberately: closing an issue bumps its
    # `updated_at`, so without this every closure would ALSO read as a rescope — and since `rescoped`
    # gates while `closed` does not, the non-gating case would be unreachable in production. A closed
    # sub-issue is governed by the shipped-phase rules, one disposition per event.
    diff["rescoped"] = sorted(
        n
        for n in served_set
        if (live_by_number.get(n) or {}).get("maybe_rescoped")
        and (live_by_number.get(n) or {}).get("state") != "CLOSED"
    )

    # `depends-on` versus the panel order. Surfaced, never corrected: disagreeing with the panel can
    # be a deliberate call (an ordering-only dependency), so it is the operator's finding to judge.
    by_phase_number = {p["number"]: p for p in prior_phases}
    seen_pairs = set()
    for phase in prior_phases:
        later = phase.get("sub_issue")
        if not isinstance(later, int) or later not in position:
            continue
        depends_on = phase.get("depends_on")
        if not isinstance(depends_on, list):
            continue
        for earlier_phase_number in depends_on:
            earlier_phase = by_phase_number.get(earlier_phase_number)
            if earlier_phase is None:
                continue
            earlier = earlier_phase.get("sub_issue")
            if not isinstance(earlier, int) or earlier not in position or earlier == later:
                continue
            if position[later] < position[earlier]:
                # One row per disagreeing sub-issue PAIR, not per dependency edge: two phases both
                # serving the earlier sub-issue would otherwise emit two rows — and two near-identical
                # attention lines — for one panel-order disagreement.
                if (later, earlier) in seen_pairs:
                    continue
                seen_pairs.add((later, earlier))
                diff["order_changed"].append(
                    {
                        "phase": phase["number"],
                        "depends_on_phase": earlier_phase_number,
                        "sub_issue": later,
                        "after_sub_issue": earlier,
                        # The panel's actual order for the disagreeing pair. Reaching here MEANS
                        # `later` sits first, so that is the order — stated as data so the prompt
                        # quotes it rather than re-deriving it from `position`.
                        "live_order": [later, earlier],
                    }
                )
    return diff


def _slice_attention(slices_facts, target_number):
    """The `attention` lines for the slice facts — one per non-empty diff case, plus the availability
    degradations. Findings ride in facts + `attention`; nothing is re-derived in a prompt."""
    lines = []
    diff = slices_facts["diff"]
    by_number = {e["number"]: e for e in slices_facts["set"]}

    if not slices_facts["detail_available"]:
        lines.append(
            "sub-issue detail is unavailable on this host (%s) — numbers, titles and states are "
            "from the sub-issue nodes; no bodies and no rescope detection"
            % SUBISSUE_DETAIL_UNSUPPORTED
        )
    if not diff["prior_phases_parsed"]:
        lines.append(
            "the prior plan's '## Phases' section does not parse — no plan-versus-live sub-issue "
            "diff was computed; this revise re-authors that section, which repairs it"
        )
    elif slices_facts["rescope_basis"] == "no_prior_plan":
        lines.append(
            "no prior plan, so there is no plan-versus-live sub-issue diff — cut '## Phases' against "
            "the live set from the start; the coverage rule still binds"
        )
    elif not diff["prior_phases_present"]:
        lines.append(
            "the prior plan carries no '## Phases' section while %d sub-issue(s) are open — a sliced "
            "target needs a phase map; no diff was computed against a plan that has no phases"
            % slices_facts["open_count"]
        )
    if slices_facts["rescope_basis"] == "unavailable" and diff["prior_phases_present"]:
        lines.append(
            "rescope detection is unavailable — a sub-issue body rewritten since the plan was posted "
            "will NOT be flagged; re-read any sub-issue whose scope you rely on"
        )
    # A served sub-issue with no usable timestamp is a hole in an otherwise-working comparison: the
    # basis says `updated_at`, so silence would read as "nothing changed" (the one thing the
    # suspicion signal must never do).
    if slices_facts["rescope_basis"] == "updated_at":
        served = {row["sub_issue"] for row in diff["mapped"]}
        blind = sorted(
            n
            for n in served
            if n in by_number and not _parse_iso8601(by_number[n].get("updated_at"))
        )
        if blind:
            lines.append(
                "no usable timestamp for sub-issue(s) %s — they are NOT covered by rescope "
                "detection even though the rest of the set is; re-read them"
                % ", ".join("#%d" % n for n in blind)
            )

    for number in diff["uncovered_open"]:
        lines.append(
            "sub-issue #%d is open and no phase in the prior plan serves it — re-cut phases to "
            "cover it, record it out-of-scope with a disposition, or route the sub-issue set back "
            "to whoever authors it" % number
        )
    for number in diff["removed"]:
        lines.append(
            "sub-issue #%d is no longer a sub-issue of #%s (removed or re-parented) but a prior "
            "phase serves it" % (number, target_number)
        )
    for number in diff["rescoped"]:
        entry = by_number.get(number) or {}
        lines.append(
            "sub-issue #%d may have changed since the plan was posted (updated %s) — re-read it at "
            "%s; an issue's timestamp also bumps on comments and labels, so this is a prompt to "
            "look, not proof"
            % (number, entry.get("updated_at"), entry.get("body_path") or "its body")
        )
    for number in diff["closed"]:
        lines.append(
            "sub-issue #%d is CLOSED — the phase serving it behaves like a shipped phase (the "
            "shipped-phase rules in references/revise-reconciliation.md govern; there is no second "
            "rule set)" % number
        )
    for row in diff["order_changed"]:
        lines.append(
            "phase %d (sub-issue #%d) depends on phase %d (sub-issue #%d), but the sub-issue panel "
            "lists them in the order %s — surfaced, not corrected: an ordering-only dependency can "
            "be a deliberate call"
            % (
                row["phase"],
                row["sub_issue"],
                row["depends_on_phase"],
                row["after_sub_issue"],
                ", ".join("#%d" % n for n in row["live_order"]),
            )
        )
    return lines


# ---------------------------------------------------------------------------
# `## Stories` section parsing (epic body) — no shared parse.py subcommand covers this grammar.
# ---------------------------------------------------------------------------


def _parse_stories_section(issue_body):
    """Parse the epic body's `## Stories` checklist. Returns a list of `{"number", "title",
    "checked"}` dicts, in source order — `number` is `None` for a placeholder bullet (the stories
    aren't filed yet). No `## Stories` section: returns `[]` (not itself a malformed-input signal
    — an epic freshly drafted without stories yet, or a non-epic body, both legitimately lack it).
    """
    lines = (issue_body or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Stories\s*$", line, re.IGNORECASE):
            start = i + 1
            break
    if start is None:
        return []
    end = len(lines)
    for j in range(start, len(lines)):
        if _SECTION_HEADING_RE.match(lines[j]):
            end = j
            break

    entries = []
    for raw_line in lines[start:end]:
        stripped = raw_line.strip()
        filed_match = _STORY_FILED_RE.match(stripped)
        if filed_match:
            entries.append(
                {
                    "number": int(filed_match.group(2)),
                    "title": filed_match.group(3).strip(),
                    "checked": filed_match.group(1) in ("x", "X"),
                }
            )
            continue
        plain_match = _STORY_PLAIN_RE.match(stripped)
        if plain_match:
            entries.append(
                {"number": None, "title": plain_match.group(2).strip(), "checked": plain_match.group(1) in ("x", "X")}
            )
    return entries


# ---------------------------------------------------------------------------
# `## Phase tracker` section parsing (PR body, revise mode only) — same "best-effort, no dedicated
# decision code" rationale as `_parse_stories_section` above.
# ---------------------------------------------------------------------------


def _parse_phase_tracker(pr_body_text):
    """Parse the open PR body's `## Phase tracker` checklist. Returns a list of `{"phase",
    "title", "checked", "commit_sha"}` dicts, in source order. `commit_sha` is `None` for an
    unshipped (`- [ ]`) row, or a shipped `operator`/`decision-only` row that records a date rather
    than a commit (this parser only extracts the `(commit <sha>)` form; a non-code-shipping
    ticked row's own annotation shape is read by the model directly from the staged PR body, not
    re-derived here). No `## Phase tracker` section: returns `[]`.
    """
    lines = (pr_body_text or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Phase tracker\s*$", line, re.IGNORECASE):
            start = i + 1
            break
    if start is None:
        return []
    end = len(lines)
    for j in range(start, len(lines)):
        if _SECTION_HEADING_RE.match(lines[j]):
            end = j
            break

    entries = []
    for raw_line in lines[start:end]:
        match = _PHASE_TRACKER_ROW_RE.match(raw_line.strip())
        if match:
            entries.append(
                {
                    "checked": match.group(1) in ("x", "X"),
                    "phase": int(match.group(2)),
                    "title": match.group(3).strip(),
                    "commit_sha": match.group(4),
                }
            )
    return entries


# ---------------------------------------------------------------------------
# Thread scanning — research dossier + epic delivery log are both located by scanning the ALREADY-
# fetched thread from a `gh_gather.run` call, never a second `gh api` round-trip (architecture.md
# §2's in-process composition applied to "read what you already fetched", not just "call the pure
# core").
# ---------------------------------------------------------------------------


def _load_thread(envelope):
    """Parse `envelope`'s `thread` field (inline text or path-mode file) back into the list of
    normalized comment dicts `gh_gather.run` produced. Never re-fetches."""
    if envelope.get("thread_mode") == "path":
        text = Path(envelope["thread_path"]).read_text(encoding="utf-8")
    else:
        text = envelope.get("thread")
    if not text:
        return []
    return json.loads(text)


def _find_one_marker(thread_list, prefix, context_label):
    """Locate the (at most one) comment in `thread_list` whose body starts with `prefix`. Returns
    `(comment_or_none, decision_or_none)` — more than one match is `MARKER_AMBIGUOUS`
    (architecture.md §3: "the gathers + config_block.py" are its CANONICAL emitters, but the code's
    own meaning — "more than one candidate marker comment ... where the contract expects one" —
    applies identically to a marker this module locates via its own thread scan rather than through
    `gh_gather`'s own single-`marker_prefix` lookup; `gh_pr_gather.py` independently applies the
    same code to its own thread scan, so this is an established pattern, not a novel one).
    """
    matches = [c for c in thread_list if (c.get("body") or "").startswith(prefix)]
    if len(matches) > 1:
        return None, needs_decision(
            MARKER_AMBIGUOUS,
            summary="%d comments match the %s marker prefix %r — expected at most one"
            % (len(matches), context_label, prefix),
            context={
                "marker_prefix": prefix,
                "comment_ids": [m.get("id") for m in matches],
                "comment_urls": [m.get("url") for m in matches],
            },
            options=[
                "inspect each comment and pick the one to treat as current",
                "delete the stale duplicate comment(s), then re-run",
            ],
        )
    return (matches[0] if matches else None), None


def _stage_comment_body(comment, scratch_dir, filename):
    """Stage `comment`'s body through the standard inline-vs-path threshold (`pipelib.spill`),
    using section name `"body"` so the returned keys (`body_mode`/`body_bytes`/`body_path`/`body`)
    match the naming convention this module's `plan`/`research`/`epic_plan` sub-objects already use
    for their own staged bodies — a caller reads `<fact>.body_mode` uniformly regardless of which
    section it is."""
    body = (comment.get("body") or "") if comment is not None else ""
    return spill_bytes(body.encode("utf-8"), "body", scratch_dir, filename=filename)


# ---------------------------------------------------------------------------
# Grounding-doc inventory (docs/specs/planner.md Step 5's read set, now declared by the consuming
# repo rather than assumed here) — read INSIDE the already-ensured grounding workspace, never via
# `git ls-tree -r --name-only <ref>` against a bare ref (architecture.md §6/§10's ref-arithmetic
# discipline; the workspace is already checked out at the right ref, so a plain filesystem read is
# both simpler and needs no second git invocation).
# ---------------------------------------------------------------------------


def _grounding_doc_inventory(grounding_path):
    """The catalogue-declared docs at `grounding_path`, plus this read's own notices. A thin
    delegation to `doc_catalogue.read_catalogue` — kept as a named function so the call site reads
    the same as it did before the migration and so the module's own tests have a seam."""
    return doc_catalogue.read_catalogue(grounding_path)


# ---------------------------------------------------------------------------
# `plan_ref` selection — docs/specs/planner.md Step 4.5's table, moved into code (see the module
# docstring for the full row-by-row mapping and the precedence rule).
# ---------------------------------------------------------------------------

PLAN_REF_ROW_OPEN_PR_HEAD = "open-pr-head"
PLAN_REF_ROW_EPIC_BRANCH = "epic-as-target"
PLAN_REF_ROW_EPIC_BOOTSTRAP = "epic-as-target-bootstrap"
PLAN_REF_ROW_STORY_PARENT_BRANCH = "story-under-open-epic"
PLAN_REF_ROW_STORY_PARENT_BOOTSTRAP = "story-parent-epic-bootstrap"
PLAN_REF_ROW_STORY_NO_PARENT = "story-no-open-parent-epic"
PLAN_REF_ROW_DEFAULT = "no-open-pr-default-branch"


def _select_plan_ref(issue_type, epic_branch_name, open_pr_headref, root_branch, parent_epic_open=False):
    """Pure lookup table: `(issue_type, epic_branch_name, open_pr_headref, parent_epic_open)` ->
    `(plan_ref, plan_ref_row)`. `epic_branch_name` is the discovered branch (or `None` on
    bootstrap/no-parent); `open_pr_headref` is the target issue's own first open PR's
    `headRefName`, or `None`; `parent_epic_open` (story only — ignored for every other
    `issue_type`) distinguishes row 5 (D4 fix: an open parent whose branch hasn't bootstrapped yet)
    from row 6 (no parent, or a closed one) — both still resolve `plan_ref` to the default
    branch (`root_branch`, derived — never a hardcoded `main`), but the row
    LABEL must say which reality produced it (architecture.md §4: facts are data, never
    re-derived — including the row name itself, not just the ref value). Checked in table order —
    the open-PR-head check runs FIRST and unconditionally, so the "open-PR-head wins when more than
    one row applies" precedence rule (docs/specs/planner.md Step 4.5) falls out of the ordering
    rather than needing a separate conflict check.
    """
    if open_pr_headref:
        return open_pr_headref, PLAN_REF_ROW_OPEN_PR_HEAD
    if issue_type == "epic":
        if epic_branch_name:
            return epic_branch_name, PLAN_REF_ROW_EPIC_BRANCH
        return root_branch, PLAN_REF_ROW_EPIC_BOOTSTRAP
    # Keyed on the epic-context facts, not the `story` label (#31): an untyped sub-issue of an open
    # epic reaches here with the same two facts set, and rows 4-6 describe its grounding exactly.
    if issue_type == "story" or epic_branch_name or parent_epic_open:
        if epic_branch_name:
            return epic_branch_name, PLAN_REF_ROW_STORY_PARENT_BRANCH
        if parent_epic_open:
            return root_branch, PLAN_REF_ROW_STORY_PARENT_BOOTSTRAP
        return root_branch, PLAN_REF_ROW_STORY_NO_PARENT
    return root_branch, PLAN_REF_ROW_DEFAULT


# ---------------------------------------------------------------------------
# Bug (a) — the deterministic open-question tracker de-dup search. S14-promoted to `oq_tracker.py`
# (see the module docstring's "S14 promotion" paragraph) — `build_oq_query` is kept as a
# module-level alias so `prep_planner.build_oq_query(...)` (this module's own CLI `--oq-query` call
# site, and tests/test_prep_planner.py's one direct-call test line) keeps working unchanged.
# ---------------------------------------------------------------------------

build_oq_query = oq_tracker.build_oq_query


# ---------------------------------------------------------------------------
# Revise facts (mode == "revise")
# ---------------------------------------------------------------------------


def _extract_plan_sha(plan_body):
    """Extract the short/long SHA from the plan's header line: '... planned <ISO> at
    `<plan-ref>@<short-sha>`' (skills/planner/references/plan-schema.md). Returns
    `None` if the header doesn't match the documented shape rather than guessing."""
    match = re.search(r"@`?([0-9a-f]{7,40})`?", plan_body or "")
    return match.group(1) if match else None


def _build_revise_facts(issue_envelope, open_prs, plan_sha, grounding_sha, repo, scratch_dir, cwd=None):
    """Assemble the revise-mode-only facts (docs/specs/planner.md Revise mode step 1): the prior
    plan body's already-staged path (reused from the target's own `GATHER_ISSUE` marker fetch — no
    second read), the prior plan's SHA and the current grounding sha side by side (BOTH raw facts,
    no drift judgment computed here — the spec's own words: "no judgment, just both SHAs"), and,
    when an open PR exists, that PR's body + its parsed `## Phase tracker`. Returns `(revise_facts,
    notices, decision_or_none)`.
    """
    revise = {"prior_plan_sha": plan_sha, "grounding_sha": grounding_sha}
    notices = []

    if open_prs:
        pr = open_prs[0]
        pr_facts, pr_notices, decision = gh_pr_gather.build_pr_facts(
            pr["number"], repo, scratch_dir=scratch_dir, cwd=cwd
        )
        if decision is not None:
            return None, notices, decision
        _merge_notices(notices, pr_notices)
        pr_body = pr_facts.get("body")
        if pr_body is None and pr_facts.get("body_mode") == "path":
            pr_body = Path(pr_facts["body_path"]).read_text(encoding="utf-8")
        open_pr_fact = {
            "number": pr_facts["number"],
            "headRefName": pr_facts["headRefName"],
            "url": pr_facts.get("url"),
            "isDraft": pr_facts.get("isDraft"),
            "body_mode": pr_facts.get("body_mode"),
        }
        if pr_facts.get("body_mode") == "path":
            open_pr_fact["body_path"] = pr_facts.get("body_path")
        revise["open_pr"] = open_pr_fact
        revise["phase_tracker"] = _parse_phase_tracker(pr_body)
    else:
        revise["open_pr"] = None
        revise["phase_tracker"] = []

    return revise, notices, None


# ---------------------------------------------------------------------------
# suggested_playbook / attention
# ---------------------------------------------------------------------------


def _suggested_playbook(issue_type, mode, parent_epic_open=False):
    """Map `(issue_type, mode, parent_epic_open)` to the suggested playbook filename
    (architecture.md §5: "Prep proposes; the router confirms"). The four real S13 playbook names
    (`docs/specs/planner.md`; `skills/planner/SKILL.md` §2's routing table):

      - ``revise.md`` — ``mode == "revise"`` (a prior plan comment on the TARGET issue), for a
        standalone issue OR an epic; revise is its own flow parameterized by the type FACTS
        (architecture.md §5 "revise is a distinct action flow: reconcile old-vs-new plan +
        projected-DoD, diff-show, SOFT/HARD gate, ## Predecessor").
      - ``story-jit.md`` — a story under an OPEN parent epic. Owns BOTH the fresh and the revise
        path for such a story (v1's "don't branch to Revise mode here — it's handled
        by Just-in-time story planning"), so it wins over `revise.md` even when the story already
        has a plan.
      - ``epic.md`` — a fresh epic-as-target run.
      - ``single.md`` — everything else fresh: a standalone bug/feature/incomplete/multi-phase
        issue, or a story with no open parent epic (v1's "Everything else …
        continue with Steps 4–10").

    ``mode`` is the `fresh`/`revise` value `build_facts` already derived; ``parent_epic_open`` is
    whether a story's parent epic was found OPEN (``False`` for every non-story type). The
    ordering encodes the precedence: the story-under-open-epic short-circuit runs before the
    revise check, matching v1's Step-2 exception.
    """
    # `parent_epic_open` alone (#31): it is set only by the parent-lookup arm, which now admits an
    # untyped sub-issue of an open epic — and that target wants the same just-in-time plan against
    # current epic HEAD as its `story`-labelled siblings.
    if parent_epic_open:
        return "story-jit.md"
    if mode == "revise":
        return "revise.md"
    if issue_type == "epic":
        return "epic.md"
    return "single.md"


def _build_attention(
    open_question_candidates,
    epic_facts,
    story_facts,
    grounding_docs=None,
    catalogue_absent=False,
):
    """`grounding_docs` is `None` when the catalogue was never read (`--refresh`, which skips the
    whole grounding assertion), `[]` when it was read and declared nothing, and a list otherwise —
    three distinct states, because "we didn't look" must not render as "the repo declared nothing".
    """
    attention = []
    if grounding_docs is not None:
        if catalogue_absent:
            attention.append(
                "no doc catalogue at the grounding ref — planning ungrounded; run "
                "/github-pipeline:setup to declare this repo's grounding docs in docs/README.md"
            )
        elif not grounding_docs:
            attention.append(
                "doc catalogue declares no documents — planning ungrounded until it names some"
            )
        for missing in doc_catalogue.missing_entry_paths(grounding_docs):
            attention.append(
                "doc catalogue names '%s', absent at the grounding ref — a stale entry, or a doc "
                "this branch has not merged yet" % missing
            )
    for group in open_question_candidates or []:
        attention.append(
            "open question '%s' has %d tracker candidate(s) — do not record it as (not filed)"
            % (group["oq_id"], len(group["candidates"]))
        )
    if epic_facts is not None:
        branch = epic_facts.get("branch") or {}
        if branch.get("match_count", 0) == 0:
            attention.append(
                "no epic integration branch exists yet on origin — grounding at main until bootstrap"
            )
        if not (epic_facts.get("delivery_log") or {}).get("present", False):
            attention.append("no epic delivery-log comment yet — no story has merged")
    if story_facts is not None:
        if story_facts.get("parent_epic") is None:
            attention.append("no parent epic found referencing this story — grounding at main")
        elif not story_facts.get("parent_epic_open"):
            attention.append("parent epic is closed — grounding at main, not the epic branch")
    return attention


# ---------------------------------------------------------------------------
# Facts-block assembly
# ---------------------------------------------------------------------------


def _extract_body(envelope, key):
    body = envelope.get(key)
    if body is None and envelope.get("%s_mode" % key) == "path":
        body = Path(envelope["%s_path" % key]).read_text(encoding="utf-8")
    return body or ""


def build_facts(issue_number, repo, root=".", scratch_dir=None, refresh=False, cwd=None):
    """Assemble the planner's complete facts block and return the envelope dict WITHOUT printing
    it (the testable core, mirroring `prep_resolver.build_facts` / `prep_evaluator.build_facts`).
    Returns `None` after a `needs_decision` envelope has already been emitted on stdout.
    """
    # Normalize to the MAIN checkout (v3): the session may sit inside a worktree (epic-branch
    # grounding for a story, a plan-PR head on the revise row); ls-remote discovery and the
    # origin/main pin key off the main checkout regardless.
    root = str(workspace._resolve_main_root(root))
    root_branch = workspace.default_branch(root)
    if scratch_dir is None:
        scratch_dir = "/tmp/gh-planner-%s" % issue_number
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    # Every composed core's non-blocking degradations accumulate here and ride out in the envelope's
    # own `notices` (architecture.md §3) — see `_merge_notices`.
    notices = []

    # 1) The target issue — one round-trip gh_gather.run() call: body/thread/plan-marker/native
    #    deps + the open-PR search already folded in.
    exit_code, issue_envelope = gh_gather.run(
        str(issue_number),
        repo,
        marker_prefix=PLAN_MARKER,
        scratch_dir=scratch_dir,
        env=None,
        stream=_DiscardStream(),
    )
    if issue_envelope is not None and issue_envelope.get("status") == "needs_decision":
        _merge_notices(notices, issue_envelope.get("notices"))
        if _forward_decision(issue_envelope["decision"], notices=notices):
            return None
    if exit_code != 0:
        sys.stderr.write(
            "prep_planner: gh_gather on issue #%s failed (exit %d)\n" % (issue_number, exit_code)
        )
        sys.exit(1)
    _merge_notices(notices, issue_envelope.get("notices"))

    issue_body = _extract_body(issue_envelope, "issue_body")
    labels = [label.get("name") for label in issue_envelope.get("labels") or []]
    issue_title = issue_envelope.get("title") or ""
    issue_type = _detect_type(labels, issue_title)

    # 2) Marker detection -> revise-mode trigger (docs/specs/planner.md "Artifacts read").
    plan_present = bool(issue_envelope.get("marker_comment_present"))
    mode = "revise" if plan_present else "fresh"

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
        # The left-hand side of the sub-issue rescope comparison: "was this sub-issue edited since
        # the plan was posted?" (#18). Free from the marker fetch — no extra round-trip.
        "updated_at": issue_envelope.get("marker_comment_updated_at"),
    }
    if plan_present:
        plan_facts["body_mode"] = issue_envelope.get("marker_comment_mode")
        if issue_envelope.get("marker_comment_mode") == "path":
            plan_facts["body_path"] = issue_envelope.get("marker_comment_path")

    # 3) Research dossier — scan the ALREADY-fetched thread (no second gh call).
    thread_list = _load_thread(issue_envelope)
    research_comment, research_decision = _find_one_marker(thread_list, RESEARCH_MARKER, "research-dossier")
    if _forward_decision(research_decision, notices=notices):
        return None
    research_facts = {"present": research_comment is not None}
    if research_comment is not None:
        research_facts["comment_id"] = research_comment.get("id")
        research_facts["comment_url"] = research_comment.get("url")
        research_facts.update(
            _stage_comment_body(research_comment, scratch_dir, "issue-%s-research.md" % issue_number)
        )

    # 4) Epic / story facts + epic-branch discovery (feeds plan_ref selection).
    # This issue's OWN open PRs (branching.prior_prs_for_issue), not every PR that mentions it: an
    # epic integration PR lists every story by number, and taking its head here would ground a
    # story's plan on the epic's ref AND feed the epic's `## Phase tracker` into that story's
    # revise facts via `_build_revise_facts` below.
    open_prs = branching.prior_prs_for_issue(issue_envelope.get("open_prs"), issue_number)
    open_pr_headref = open_prs[0]["headRefName"] if open_prs else None

    epic_branch_name = None
    epic_facts = None
    story_facts = None
    parent_epic_open = False

    if issue_type == "epic":
        epic_branch_facts, decision = _discover_epic_branch(root, issue_number)
        if _forward_decision(decision, notices=notices):
            return None
        epic_branch_name = epic_branch_facts.get("branch")

        # The epic's story set, per skills/_shared/epic-story-hierarchy.md. The native source
        # is the native sub-issue relation: every entry is filed by construction and its live state
        # rides along, so no per-story round-trip is needed. Tier 2 parses a legacy epic's
        # `## Stories` section and fetches each filed story's state. A fresh epic has NO `## Stories`
        # section at all, so reading only the body would report `stories_filed: false` for an epic
        # whose stories are filed — routing the planner's handoff to the drafter to file stories that
        # already exist.
        story_entries = []
        for node in issue_envelope.get("sub_issues") or []:
            live_state = node.get("state")
            story_entries.append(
                {
                    "number": node.get("number"),
                    "title": node.get("title"),
                    "checked": (live_state or "").upper() == "CLOSED",
                    "state": live_state,
                    "live_title": node.get("title"),
                }
            )
        native_numbers = {e["number"] for e in story_entries}

        checklist_entries = _parse_stories_section(issue_body)
        for entry in checklist_entries:
            if entry["number"] is not None and entry["number"] in native_numbers:
                # Already carried natively, with authoritative live state.
                continue
            if entry["number"] is not None:
                state_fact, decision = _fetch_story_state(repo, entry["number"], cwd=cwd)
                if _forward_decision(decision, notices=notices):
                    return None
                story_entries.append(
                    {
                        "number": entry["number"],
                        "title": entry["title"],
                        "checked": entry["checked"],
                        "state": state_fact["state"],
                        "live_title": state_fact["title"],
                    }
                )
            else:
                story_entries.append(
                    {"number": None, "title": entry["title"], "checked": entry["checked"], "state": None, "live_title": None}
                )

        if native_numbers and checklist_entries:
            stories_source = "mixed"
        elif native_numbers:
            stories_source = "sub-issues"
        else:
            stories_source = "checklist"

        delivery_log_comment, dl_decision = _find_one_marker(thread_list, DELIVERY_LOG_MARKER, "epic-delivery-log")
        if _forward_decision(dl_decision, notices=notices):
            return None
        delivery_log_facts = {"present": delivery_log_comment is not None}
        if delivery_log_comment is not None:
            delivery_log_facts["comment_id"] = delivery_log_comment.get("id")
            delivery_log_facts["comment_url"] = delivery_log_comment.get("url")
            delivery_log_facts.update(
                _stage_comment_body(
                    delivery_log_comment, scratch_dir, "epic-%s-delivery-log.md" % issue_number
                )
            )

        epic_facts = {
            "branch": epic_branch_facts,
            "stories_filed": any(e["number"] is not None for e in story_entries),
            "stories_source": stories_source,
            "stories": story_entries,
            "delivery_log": delivery_log_facts,
        }

    elif issue_type == "story" or issue_envelope.get("parent"):
        # Gated on HAVING a parent, not on the lexical type (#31) — the same gate move as
        # prep_workspace_open's and prep_resolver's. Grounding a plan on the default branch while
        # the resolver builds it on `epic/<N>-<slug>` plans against a tree missing every predecessor
        # story's merged work. Tier rule identical to the other two preps: native `parent` first
        # (exact, no round-trip), and the legacy `#<N> in:body` full-text search ONLY for a `story`
        # filed before the relation was written (skills/_shared/epic-story-hierarchy.md) — an
        # untyped target gets the exact native answer or no lookup at all.
        matches, decision = _search_parent_epic(
            repo, issue_number, native_parent=issue_envelope.get("parent"), cwd=cwd
        )
        if _forward_decision(decision, notices=notices):
            return None
        parent_epic = matches[0] if len(matches) == 1 else None
        parent_open = parent_epic is not None and (parent_epic.get("state") or "").upper() == "OPEN"

        epic_branch_facts = None
        jit_epic_plan = None
        jit_delivery_log = None
        if parent_open:
            epic_branch_facts, decision = _discover_epic_branch(root, parent_epic["number"])
            if _forward_decision(decision, notices=notices):
                return None
            epic_branch_name = epic_branch_facts.get("branch")

        # An UNTYPED target enters the story-JIT machinery only on the branch-existence oracle: an
        # `epic/<parent>-*` branch on origin is the evidence that the parent really is an epic with
        # work in flight. The `parent` node carries no labels, so without that branch a parent epic
        # whose workspace is not open yet is indistinguishable from a STORY parent — which would
        # make this target a deliverable slice, and slices are planned as their parent's phases, not
        # as just-in-time stories (skills/_shared/epic-story-hierarchy.md). Unproven, it grounds on
        # the default branch exactly as before, and says so.
        if issue_type != "story" and not epic_branch_name:
            if parent_epic is not None:
                notices.append(
                    branching.PARENT_CLOSED
                    if not parent_open
                    else branching.PARENT_HAS_NO_INTEGRATION_BRANCH
                )
            epic_branch_facts = None
        else:
            parent_epic_open = parent_open
            if parent_open:
                epic_exit, epic_envelope = gh_gather.run(
                    str(parent_epic["number"]),
                    repo,
                    marker_prefix=PLAN_MARKER,
                    scratch_dir=scratch_dir,
                    env=None,
                    stream=_DiscardStream(),
                )
                if epic_envelope is not None and epic_envelope.get("status") == "needs_decision":
                    _merge_notices(notices, epic_envelope.get("notices"))
                    if _forward_decision(epic_envelope["decision"], notices=notices):
                        return None
                if epic_exit != 0:
                    sys.stderr.write(
                        "prep_planner: gh_gather on parent epic #%s failed (exit %d)\n"
                        % (parent_epic["number"], epic_exit)
                    )
                    sys.exit(1)
                _merge_notices(notices, epic_envelope.get("notices"))

                jit_epic_plan = {"present": bool(epic_envelope.get("marker_comment_present"))}
                if jit_epic_plan["present"]:
                    jit_epic_plan["body_mode"] = epic_envelope.get("marker_comment_mode")
                    if epic_envelope.get("marker_comment_mode") == "path":
                        jit_epic_plan["body_path"] = epic_envelope.get("marker_comment_path")
                    else:
                        jit_epic_plan["body"] = epic_envelope.get("marker_comment_body")

                epic_thread = _load_thread(epic_envelope)
                dl_comment, dl_decision = _find_one_marker(epic_thread, DELIVERY_LOG_MARKER, "epic-delivery-log")
                if _forward_decision(dl_decision, notices=notices):
                    return None
                jit_delivery_log = {"present": dl_comment is not None}
                if dl_comment is not None:
                    jit_delivery_log["comment_id"] = dl_comment.get("id")
                    jit_delivery_log["comment_url"] = dl_comment.get("url")
                    jit_delivery_log.update(
                        _stage_comment_body(
                            dl_comment, scratch_dir, "epic-%s-delivery-log.md" % parent_epic["number"]
                        )
                    )

            story_facts = {
                "parent_epic": parent_epic,
                "parent_epic_open": parent_open,
                "epic_branch": epic_branch_facts,
                "epic_plan": jit_epic_plan,
                "epic_delivery_log": jit_delivery_log,
            }

    # 4.5) Deliverable sub-issues (#18) — a NON-EPIC target's sub-issues are its slices by
    #      construction, so the gate is the target's type plus a non-empty node list already in
    #      hand: an epic's children are stories, and a childless target costs zero extra gh calls
    #      (which is what keeps the canonical call budget unchanged).
    slices_facts = None
    sub_issue_nodes = issue_envelope.get("sub_issues") or []
    if issue_type != "epic" and sub_issue_nodes:
        detail_objects, detail_notices, detail_decision = _fetch_sub_issue_details(
            repo, issue_number, cwd=cwd
        )
        if _forward_decision(detail_decision, notices=notices):
            return None
        _merge_notices(notices, detail_notices)

        plan_updated_at = plan_facts.get("updated_at")
        slice_set = _build_slice_set(
            sub_issue_nodes, detail_objects, plan_updated_at, scratch_dir
        )
        # Three distinguishable states, so the fact never contradicts itself: `unavailable` means
        # THIS HOST cannot answer (the endpoint degraded), `no_prior_plan` means there is nothing to
        # compare against yet, and `updated_at` means the comparison actually ran.
        detail_available = detail_objects is not None
        if not detail_available:
            rescope_basis = "unavailable"
        elif not plan_updated_at:
            rescope_basis = "no_prior_plan"
        else:
            rescope_basis = "updated_at"

        # The prior plan's `## Phases` is parsed BEST-EFFORT — never `PHASES_MALFORMED`. A revise
        # run exists to *repair* a bad plan, so hard-failing here would mean the one tool that can
        # rewrite the section refuses to start because the section is broken, and the plan footer
        # forbids hand-editing. prep_resolver DOES hard-fail on the identical body (it executes the
        # plan and cannot ship a phase it cannot read), so a malformed plan stays re-plannable but
        # never executable. Same best-effort posture as `_parse_phase_tracker`.
        prior_phases = None
        prior_phases_parsed = True
        prior_phases_error = None
        if plan_present and plan_body:
            try:
                prior_phases = parse.parse_phases(plan_body)
            except parse._PhasesMalformed as exc:  # noqa: SLF001 (mirrors prep_resolver's use)
                prior_phases = None
                prior_phases_parsed = False
                prior_phases_error = {
                    "reason": exc.reason,
                    "line_number": exc.line_number,
                    "raw_line": exc.raw_line,
                }

        slices_facts = {
            "detail_available": detail_available,
            "source": "sub_issues_rest" if detail_available else "sub_issues_node",
            "open_count": sum(1 for e in slice_set if e["state"] == "OPEN"),
            "rescope_basis": rescope_basis,
            "set": slice_set,
            "diff": _build_slice_diff(
                slice_set, prior_phases, prior_phases_parsed, rescope_basis
            ),
        }
        slices_facts["diff"]["prior_phases_error"] = prior_phases_error

    # 5) plan_ref selection (docs/specs/planner.md Step 4.5's FULL table — see module docstring).
    plan_ref, plan_ref_row = _select_plan_ref(
        issue_type, epic_branch_name, open_pr_headref, root_branch,
        parent_epic_open=parent_epic_open,
    )

    # 6) Ambient grounding (v3): the planner grounds on the CHECKOUT THE SESSION WAS STARTED IN,
    #    asserted against the selected plan_ref — never a script-created read worktree. For a
    #    default-branch plan_ref (the fresh-standard default), any up-to-date checkout of it —
    #    including the project root — passes (`allow_main_root`; plan-before-open is the canonical
    #    posture). For a non-main plan_ref (the parent-epic branch for a story, an open plan-PR's
    #    head on the revise row, the epic branch for epic-level planning) the operator must sit
    #    inside the matching worktree, or the assertion is a WORKSPACE_MISMATCH decision. A
    #    checkout strictly behind origin/<plan_ref> is WORKSPACE_MISMATCH(stale_checkout) — a
    #    stale footer SHA would be an immediate `plan: stale` downstream. No hooks (grounding is
    #    read-only; unchanged from the read-workspace era). Skipped on --refresh, mirroring
    #    prep_resolver.py's / prep_evaluator.py's identical contract. `root` reports the main
    #    checkout's path and the derived default branch — uniform across the three stage preps;
    #    the grounding SHA a plan footer renders is `grounding.sha`, this checkout's own HEAD.
    if not refresh:
        grounding_envelope, gw_notices, gw_decision = workspace._build_attach(
            cwd if cwd is not None else ".",
            plan_ref,
            run_hooks=False,
            allow_main_root=(plan_ref == root_branch),
            check_remote_staleness=True,
        )
        if _forward_decision(gw_decision, notices=notices):
            return None
        _merge_notices(notices, gw_notices)
        grounding_docs, catalogue_notices = _grounding_doc_inventory(grounding_envelope["path"])
        _merge_notices(notices, catalogue_notices)
    else:
        grounding_envelope = None
        grounding_docs = []

    # 7) Bug (a) — the deterministic open-question tracker de-dup search (S14-promoted; see module
    #    docstring's "S14 promotion" paragraph).
    open_question_entries, open_question_candidates, oq_decision = (
        oq_tracker.build_open_question_candidates(issue_body, repo, cwd=cwd)
    )
    if _forward_decision(oq_decision, notices=notices):
        return None

    # 8) Revise facts (mode == "revise" only).
    revise_facts = None
    if mode == "revise":
        revise_facts, revise_notices, revise_decision = _build_revise_facts(
            issue_envelope,
            open_prs,
            plan_sha,
            grounding_envelope.get("sha") if grounding_envelope is not None else None,
            repo,
            scratch_dir,
            cwd=cwd,
        )
        if _forward_decision(revise_decision, notices=notices):
            return None
        _merge_notices(notices, revise_notices)

    suggested_playbook = _suggested_playbook(issue_type, mode, parent_epic_open)
    vector = {"type": issue_type, "mode": mode, "plan_ref_row": plan_ref_row}

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
            "blocked_by": issue_envelope.get("blocked_by") or [],
            "blocking": issue_envelope.get("blocking") or [],
            "deps_available": issue_envelope.get("deps_available"),
            # Native epic↔story hierarchy (skills/_shared/epic-story-hierarchy.md): `parent` names
            # the epic a story belongs to, `sub_issues` the epic's story set, `sub_issues_summary`
            # its progress rollup. Tier 1 of the story-set read; the `## Stories` checklist in the
            # body is the `checklist` source for epics filed before the relation was written.
            "parent": issue_envelope.get("parent"),
            "sub_issues": issue_envelope.get("sub_issues") or [],
            "sub_issues_summary": issue_envelope.get("sub_issues_summary") or {},
            "subissues_available": issue_envelope.get("subissues_available"),
        },
        "vector": vector,
        "plan_ref": plan_ref,
        "suggested_playbook": suggested_playbook,
        "plan": plan_facts,
        "research": research_facts,
        "grounding_docs": grounding_docs,
        "open_questions": open_question_entries,
        "open_question_candidates": open_question_candidates,
        "attention": _build_attention(
            open_question_candidates,
            epic_facts,
            story_facts,
            grounding_docs=None if refresh else grounding_docs,
            catalogue_absent=DOC_CATALOGUE_ABSENT in notices,
        ),
        "notices": notices,
    }
    if epic_facts is not None:
        facts["epic"] = epic_facts
    if story_facts is not None:
        facts["story"] = story_facts
    if revise_facts is not None:
        facts["revise"] = revise_facts
    if slices_facts is not None:
        # Named `slices`, not `sub_issues`: `target.sub_issues` already carries the raw relation
        # nodes, and a second top-level key by that name would be a genuine confusion hazard. A
        # playbook keys on this key's PRESENCE — never on the target's type.
        facts["slices"] = slices_facts
        facts["attention"].extend(_slice_attention(slices_facts, issue_envelope["number"]))
    if grounding_envelope is not None:
        # v3: the OBSERVED ambient checkout, asserted against plan_ref — replaces the
        # read_workspaces.grounding ro-* view. `grounding.sha` feeds the plan footer's
        # `@<short-sha>` and `revise.grounding_sha`.
        facts["grounding"] = {
            "path": grounding_envelope["path"],
            "ref": plan_ref,
            "branch": grounding_envelope.get("branch"),
            "sha": grounding_envelope.get("sha"),
            "dirty": grounding_envelope.get("dirty"),
        }
        if grounding_envelope.get("dirty"):
            facts["attention"].append(
                "grounding checkout has uncommitted changes — the plan footer SHA may not "
                "reflect the files read"
            )

    sections = {}
    for key, value in issue_envelope.items():
        if key.startswith(("issue_body", "thread", "marker_comment")):
            sections[key] = value
    facts["sections"] = sections

    return facts


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
        help="scratch dir for spilled sections (default: /tmp/gh-planner-<issue>)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-derive volatile facts (issue/PR state, marker detection, OQ tracker search) "
        "without re-running root freshness or re-ensuring the grounding read workspace",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="explicit working directory for the gh calls that have no --repo scoping of their "
        "own (parent-epic search, per-story state fetch, OQ tracker search); optional in normal "
        "use, provided for test-injection — mirrors prep_resolver.py's / prep_evaluator.py's "
        "identical --cwd knob",
    )
    parser.add_argument(
        "--oq-query",
        action="append",
        default=None,
        metavar="TEXT",
        help="one-shot tracker de-dup lookup for a newly-detected open-question topic (repeatable) "
        "— runs the deterministic question-tracker search and emits `oq_query_candidates`, without "
        "assembling the full facts block; the playbook consults it before recording a NEWLY-"
        "detected OQ as (not filed) (docs/specs/planner.md Bug (a))",
    )
    args = parser.parse_args(argv)

    if args.oq_query:
        payload, notices, decision = build_oq_query(args.repo, args.oq_query, cwd=args.cwd)
        if decision is not None:
            emit_needs_decision(decision, notices=notices)
            return EXIT_OK
        emit_ok(payload=payload, notices=notices)
        return EXIT_OK

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
