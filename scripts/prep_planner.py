#!/usr/bin/env python3
"""prep_planner.py — the planner's complete facts block in one call (architecture.md §4;
docs/implementation.md S12; docs/specs/planner.md). Assembles the session's entire starting
state — revise detection, the `plan_ref` selection table moved into code, epic/JIT-story facts,
revise facts, the deterministic open-question tracker de-dup search (the frozen Bug (a) fix), and
the grounding-doc inventory at the pinned `plan_ref` SHA — as ONE JSON envelope on stdout, so the
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
    config_block.read_block_anywhere        -- NOT used by this module directly today (no gate-
                                               config block the planner reads is named yet), but the
                                               S12-promoted shared reader (see the "Promotion"
                                               paragraph below) is imported for parity with the
                                               sibling preps' composition style, ready for a future
                                               planner-side config block.

Every executor composed here exposes a **pure, non-emitting core** — ``build_*(...) -> (payload,
notices, decision|None)`` (docs/specs/baseline.md §5, the S8 pattern lock). This prep calls those
cores **directly** and forwards each core's returned ``decision`` verbatim (:func:`_forward_decision`),
emitting exactly one envelope of its own. No ``redirect_stdout``/``io.StringIO`` capture of another
script's stdout is used anywhere in this module (S9-on rule; docs/specs/baseline.md §5).

``git ls-remote --heads origin <pattern>`` (epic-branch discovery), ``gh issue list --label epic
...`` (story parent-epic search), and ``gh issue view <NN> --json state,title,labels`` (per-story
live-state fetch, mirroring v1's ``GATHER_EPIC`` reconciliation) have no existing executor core —
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_block  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
import gh_gather  # noqa: E402
import gh_pr_gather  # noqa: E402
import oq_tracker  # noqa: E402
import refblocks  # noqa: E402  (the origin/main pin — root.sha provenance, uniform across preps)
import parse  # noqa: E402  (no longer called directly by this module's own code — kept as an
# import so `prep_planner.parse` still resolves for tests/test_prep_planner.py's one direct
# `prep_planner.parse.parse_oq_links(...)` call, matching the S14-promotion's "tests unmodified"
# bar; `oq_tracker.py` is this module's own OQ-search composition path now)
import workspace  # noqa: E402
from pipelib import process  # noqa: E402
from pipelib.decisions import AMBIGUOUS, AUTH_REQUIRED, MARKER_AMBIGUOUS, needs_decision  # noqa: E402
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

ROOT_MAIN_BRANCH = "main"

# Grounding-doc read set (CLAUDE.md's "Optional grounding docs read if present" — the v2-generic
# set, NOT v1's food-journal-specific superset which also names `docs/architecture-notes.md` /
# `docs/ui-design.md`; those are stack-specific artifacts, not part of the stack-agnostic v2
# contract). Existence is checked INSIDE the read workspace (a real, already-checked-out-at-
# `plan_ref` directory) rather than via `git ls-tree -r --name-only <ref>` against a ref pointer —
# architecture.md §6's "no ref arithmetic in prompts" principle extended here: once the workspace
# is ensured, a plain filesystem check is simpler and needs no second git invocation.
_GROUNDING_DOC_PATHS = ("docs/prd.md", "docs/architecture.md", "docs/constitution.md", "CLAUDE.md")

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
# Grounding-doc inventory (docs/specs/planner.md Step 5's read set, narrowed to CLAUDE.md's
# v2-generic "Optional grounding docs" list) — checked INSIDE the already-ensured read workspace,
# never via `git ls-tree -r --name-only <ref>` against a bare ref (architecture.md §6/§10's
# ref-arithmetic discipline; the workspace is already checked out at the right ref, so a plain
# filesystem check is both simpler and needs no second git invocation).
# ---------------------------------------------------------------------------


def _grounding_doc_inventory(grounding_path):
    inventory = []
    for rel in _GROUNDING_DOC_PATHS:
        doc_path = Path(grounding_path) / rel
        present = doc_path.is_file()
        inventory.append({"doc": rel, "present": present, "path": str(doc_path) if present else None})
    return inventory


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


def _select_plan_ref(issue_type, epic_branch_name, open_pr_headref, parent_epic_open=False):
    """Pure lookup table: `(issue_type, epic_branch_name, open_pr_headref, parent_epic_open)` ->
    `(plan_ref, plan_ref_row)`. `epic_branch_name` is the discovered branch (or `None` on
    bootstrap/no-parent); `open_pr_headref` is the target issue's own first open PR's
    `headRefName`, or `None`; `parent_epic_open` (story only — ignored for every other
    `issue_type`) distinguishes row 5 (D4 fix: an open parent whose branch hasn't bootstrapped yet)
    from row 6 (no parent, or a closed one) — both still resolve `plan_ref` to `main`, but the row
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
        return ROOT_MAIN_BRANCH, PLAN_REF_ROW_EPIC_BOOTSTRAP
    if issue_type == "story":
        if epic_branch_name:
            return epic_branch_name, PLAN_REF_ROW_STORY_PARENT_BRANCH
        if parent_epic_open:
            return ROOT_MAIN_BRANCH, PLAN_REF_ROW_STORY_PARENT_BOOTSTRAP
        return ROOT_MAIN_BRANCH, PLAN_REF_ROW_STORY_NO_PARENT
    return ROOT_MAIN_BRANCH, PLAN_REF_ROW_DEFAULT


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
    decision_or_none)`.
    """
    revise = {"prior_plan_sha": plan_sha, "grounding_sha": grounding_sha}

    if open_prs:
        pr = open_prs[0]
        pr_facts, _notices, decision = gh_pr_gather.build_pr_facts(
            pr["number"], repo, scratch_dir=scratch_dir, cwd=cwd
        )
        if decision is not None:
            return None, decision
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

    return revise, None


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
    if issue_type == "story" and parent_epic_open:
        return "story-jit.md"
    if mode == "revise":
        return "revise.md"
    if issue_type == "epic":
        return "epic.md"
    return "single.md"


def _build_attention(open_question_candidates, epic_facts, story_facts):
    attention = []
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
    if scratch_dir is None:
        scratch_dir = "/tmp/gh-planner-%s" % issue_number
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)

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
        if _forward_decision(issue_envelope["decision"], notices=issue_envelope.get("notices")):
            return None
    if exit_code != 0:
        sys.stderr.write(
            "prep_planner: gh_gather on issue #%s failed (exit %d)\n" % (issue_number, exit_code)
        )
        sys.exit(1)

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
    }
    if plan_present:
        plan_facts["body_mode"] = issue_envelope.get("marker_comment_mode")
        if issue_envelope.get("marker_comment_mode") == "path":
            plan_facts["body_path"] = issue_envelope.get("marker_comment_path")

    # 3) Research dossier — scan the ALREADY-fetched thread (no second gh call).
    thread_list = _load_thread(issue_envelope)
    research_comment, research_decision = _find_one_marker(thread_list, RESEARCH_MARKER, "research-dossier")
    if _forward_decision(research_decision):
        return None
    research_facts = {"present": research_comment is not None}
    if research_comment is not None:
        research_facts["comment_id"] = research_comment.get("id")
        research_facts["comment_url"] = research_comment.get("url")
        research_facts.update(
            _stage_comment_body(research_comment, scratch_dir, "issue-%s-research.md" % issue_number)
        )

    # 4) Epic / story facts + epic-branch discovery (feeds plan_ref selection).
    open_prs = issue_envelope.get("open_prs") or []
    open_pr_headref = open_prs[0]["headRefName"] if open_prs else None

    epic_branch_name = None
    epic_facts = None
    story_facts = None
    parent_epic_open = False

    if issue_type == "epic":
        epic_branch_facts, decision = _discover_epic_branch(root, issue_number)
        if _forward_decision(decision):
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
                if _forward_decision(decision):
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
        if _forward_decision(dl_decision):
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

    elif issue_type == "story":
        # Native `parent` first (exact, no round-trip); the full-text search is the fallback for a
        # story filed before the relation was written (skills/_shared/epic-story-hierarchy.md).
        matches, decision = _search_parent_epic(
            repo, issue_number, native_parent=issue_envelope.get("parent"), cwd=cwd
        )
        if _forward_decision(decision):
            return None
        parent_epic = matches[0] if len(matches) == 1 else None
        parent_open = parent_epic is not None and (parent_epic.get("state") or "").upper() == "OPEN"
        parent_epic_open = parent_open

        epic_branch_facts = None
        jit_epic_plan = None
        jit_delivery_log = None
        if parent_open:
            epic_branch_facts, decision = _discover_epic_branch(root, parent_epic["number"])
            if _forward_decision(decision):
                return None
            epic_branch_name = epic_branch_facts.get("branch")

            epic_exit, epic_envelope = gh_gather.run(
                str(parent_epic["number"]),
                repo,
                marker_prefix=PLAN_MARKER,
                scratch_dir=scratch_dir,
                env=None,
                stream=_DiscardStream(),
            )
            if epic_envelope is not None and epic_envelope.get("status") == "needs_decision":
                if _forward_decision(epic_envelope["decision"], notices=epic_envelope.get("notices")):
                    return None
            if epic_exit != 0:
                sys.stderr.write(
                    "prep_planner: gh_gather on parent epic #%s failed (exit %d)\n"
                    % (parent_epic["number"], epic_exit)
                )
                sys.exit(1)

            jit_epic_plan = {"present": bool(epic_envelope.get("marker_comment_present"))}
            if jit_epic_plan["present"]:
                jit_epic_plan["body_mode"] = epic_envelope.get("marker_comment_mode")
                if epic_envelope.get("marker_comment_mode") == "path":
                    jit_epic_plan["body_path"] = epic_envelope.get("marker_comment_path")
                else:
                    jit_epic_plan["body"] = epic_envelope.get("marker_comment_body")

            epic_thread = _load_thread(epic_envelope)
            dl_comment, dl_decision = _find_one_marker(epic_thread, DELIVERY_LOG_MARKER, "epic-delivery-log")
            if _forward_decision(dl_decision):
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

    # 5) plan_ref selection (docs/specs/planner.md Step 4.5's FULL table — see module docstring).
    plan_ref, plan_ref_row = _select_plan_ref(
        issue_type, epic_branch_name, open_pr_headref, parent_epic_open=parent_epic_open
    )

    # 6) Ambient grounding (v3): the planner grounds on the CHECKOUT THE SESSION WAS STARTED IN,
    #    asserted against the selected plan_ref — never a script-created read worktree. For a
    #    `main` plan_ref (the fresh-standard default), any clean up-to-date `main` checkout —
    #    including the project root — passes (`allow_main_root`; plan-before-open is the canonical
    #    posture). For a non-main plan_ref (the parent-epic branch for a story, an open plan-PR's
    #    head on the revise row, the epic branch for epic-level planning) the operator must sit
    #    inside the matching worktree, or the assertion is a WORKSPACE_MISMATCH decision. A
    #    checkout strictly behind origin/<plan_ref> is WORKSPACE_MISMATCH(stale_checkout) — a
    #    stale footer SHA would be an immediate `plan: stale` downstream. No hooks (grounding is
    #    read-only; unchanged from the read-workspace era). Skipped on --refresh, mirroring
    #    prep_resolver.py's / prep_evaluator.py's identical contract. `root.sha` is the
    #    origin/main pin (refblocks), keeping the root fact's provenance uniform across the three
    #    stage preps even though the planner reads no gate config.
    if not refresh:
        root_sha = refblocks.fetch_pin(root)

        grounding_envelope, _gw_notices, gw_decision = workspace._build_attach(
            cwd if cwd is not None else ".",
            plan_ref,
            run_hooks=False,
            allow_main_root=(plan_ref == ROOT_MAIN_BRANCH),
            check_remote_staleness=True,
        )
        if _forward_decision(gw_decision):
            return None
        grounding_docs = _grounding_doc_inventory(grounding_envelope["path"])
    else:
        root_sha = None
        grounding_envelope = None
        grounding_docs = []

    # 7) Bug (a) — the deterministic open-question tracker de-dup search (S14-promoted; see module
    #    docstring's "S14 promotion" paragraph).
    open_question_entries, open_question_candidates, oq_decision = (
        oq_tracker.build_open_question_candidates(issue_body, repo, cwd=cwd)
    )
    if _forward_decision(oq_decision):
        return None

    # 8) Revise facts (mode == "revise" only).
    revise_facts = None
    if mode == "revise":
        revise_facts, revise_decision = _build_revise_facts(
            issue_envelope,
            open_prs,
            plan_sha,
            grounding_envelope.get("sha") if grounding_envelope is not None else None,
            repo,
            scratch_dir,
            cwd=cwd,
        )
        if _forward_decision(revise_decision):
            return None

    suggested_playbook = _suggested_playbook(issue_type, mode, parent_epic_open)
    vector = {"type": issue_type, "mode": mode, "plan_ref_row": plan_ref_row}

    facts = {
        "repo": repo,
        "scratch": scratch_dir,
        "root": {"path": root, "sha": root_sha, "source": "origin/main", "fresh": not refresh},
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
        "attention": _build_attention(open_question_candidates, epic_facts, story_facts),
        "notices": [],
    }
    if epic_facts is not None:
        facts["epic"] = epic_facts
    if story_facts is not None:
        facts["story"] = story_facts
    if revise_facts is not None:
        facts["revise"] = revise_facts
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
