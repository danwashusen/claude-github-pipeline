"""Offline tests for the resolver skill (docs/implementation.md S10).

Three offline surfaces the S10 DoD / Testing section names:

1. **Routing-table fixtures** (`vector` → `playbooks/<file>`). The router's visible routing table
   (`skills/resolver/SKILL.md` §2) maps a prep-derived `vector` to the one playbook a session reads.
   These tests parse that table, assert it covers exactly the four routable playbooks
   (standard / story / epic / comment-only), that each points at a real `playbooks/<file>`, and that
   the type→playbook mapping is byte-consistent with `prep_resolver._suggested_playbook` (the router
   "confirms `suggested_playbook` against the table", architecture.md §5).

2. **The interleaving pattern-grep, committed as a validator** (S10 DoD box 1). A test that greps the
   four routable playbooks (and the shared spine) for cross-type conditionals and fails on a hit —
   both `if … (epic|story|standard|comment-only) … else …` constructs AND "when the issue is a
   <type>"-style prose branches. The route IS the branch; a playbook is a linear narrative.

3. **`--dry-run` persist envelopes.** Every GitHub write the playbooks specify goes through
   `gh_persist.py` (SKILL.md §3; the resolver has no scriptless raw-gh executor). These run each such
   invocation with `--dry-run` against the offline shim and assert a conformant envelope (status ok,
   `would_run` present, no live gh call).

Plus the structural bar (router ≤150, router+largest playbook ≤584 = half of v1's 1169) and the
DoD-annotation byte-compat check against the S1 capture (S10 DoD box 2, offline half).

No network: gh_persist.py's `gh` calls resolve to the offline shim via tests/run.py's PATH wiring;
the dry-run path performs no gh call at all (asserted).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SKILL_DIR = REPO_ROOT / "skills" / "resolver"
ROUTER = SKILL_DIR / "SKILL.md"
PLAYBOOKS_DIR = SKILL_DIR / "playbooks"
REFERENCES_DIR = SKILL_DIR / "references"
GH_PERSIST = SCRIPTS_DIR / "gh_persist.py"

# The four routable playbooks (the spine is a shared file, not a routable route).
ROUTABLE_PLAYBOOKS = {"standard.md", "story.md", "epic.md", "comment-only.md"}
SPINE = "resolve-spine.md"

# Half of the v1 resolver SKILL.md (1169 lines, docs/specs/baseline.md §1) = 584 (floor).
V1_HALF_BAR = 1169 // 2

sys.path.insert(0, str(SCRIPTS_DIR))

import prep_resolver  # noqa: E402  (import after sys.path setup, by necessity)
from tests.support import envelope_asserts, shimenv  # noqa: E402
from tests.support.retired_tokens import FORBIDDEN_CONTRACT_TOKENS  # noqa: E402


# ---------------------------------------------------------------------------
# Router routing-table parse
# ---------------------------------------------------------------------------

# The router's §2 table rows carry a backticked `playbooks/<file>` in the SECOND cell. The first cell
# is a free-form vector description (e.g. `comment_only: true (…)` or `type: standard`), so we key the
# parse off the playbook cell and pull the driving token from the first cell.
_ROUTE_ROW_RE = re.compile(
    r"^\|\s*(?P<vector>[^|]+?)\s*\|\s*`(?P<playbook>playbooks/[a-z0-9-]+\.md)`\s*\|"
)


def _parse_router_routing_table(router_text):
    """Return an ordered list of (vector_cell, playbooks/<file>) parsed from the router's routing
    table. Rows whose second cell isn't a backticked `playbooks/<file>` path (the header and
    separator rows) don't match."""
    rows = []
    for line in router_text.splitlines():
        match = _ROUTE_ROW_RE.match(line)
        if match:
            rows.append((match.group("vector").strip(), match.group("playbook")))
    return rows


class RouterRoutingTableTests(unittest.TestCase):
    def setUp(self):
        self.router_text = ROUTER.read_text(encoding="utf-8")
        self.rows = _parse_router_routing_table(self.router_text)
        self.playbooks = [pb for _, pb in self.rows]

    def test_router_exists_and_has_no_model_effort_pins(self):
        # Model/effort are not pinned — skills inherit the invoking session's model and effort.
        self.assertTrue(ROUTER.is_file(), "router SKILL.md must exist")
        head = "\n".join(self.router_text.splitlines()[:8])
        self.assertIn("name: resolver", head)
        self.assertNotIn("model:", head)
        self.assertNotIn("effort:", head)

    def test_routing_table_covers_exactly_the_four_routable_playbooks(self):
        self.assertEqual(
            {Path(pb).name for pb in self.playbooks},
            ROUTABLE_PLAYBOOKS,
            "router routing table must map exactly the four routable playbooks, got %r"
            % (sorted(Path(pb).name for pb in self.playbooks),),
        )

    def test_exactly_four_routable_playbooks_plus_one_spine_on_disk(self):
        # S10 DoD box 1: exactly four playbooks. The playbooks/ dir holds the four routable playbooks
        # plus the single shared spine (architecture.md §5: "a playbook may additionally pull in its
        # skill's single shared spine file").
        on_disk = {p.name for p in PLAYBOOKS_DIR.glob("*.md")}
        self.assertEqual(
            on_disk,
            ROUTABLE_PLAYBOOKS | {SPINE},
            "playbooks/ must be exactly the four routable playbooks + the one shared spine, got %r"
            % (sorted(on_disk),),
        )

    def test_every_routed_playbook_file_exists(self):
        for vector, playbook in self.rows:
            target = SKILL_DIR / playbook
            self.assertTrue(
                target.is_file(),
                "routing table maps %r -> %r but %s does not exist" % (vector, playbook, target),
            )

    def test_table_matches_prep_suggested_playbook_for_each_type(self):
        # architecture.md §5: prep proposes `suggested_playbook`; the router confirms it against the
        # table. Assert byte-consistency for each (type, comment_only) the vector can take.
        cases = [
            ("standard", False, "standard.md"),
            ("story", False, "story.md"),
            ("epic", False, "epic.md"),
            ("standard", True, "comment-only.md"),  # comment_only overrides type in prep
        ]
        for issue_type, comment_only, expected in cases:
            self.assertEqual(
                prep_resolver._suggested_playbook(issue_type, comment_only),
                expected,
                "prep _suggested_playbook(%r, %r) should be %r" % (issue_type, comment_only, expected),
            )
            self.assertIn(
                "playbooks/" + expected,
                self.playbooks,
                "the router table must route to playbooks/%s (prep proposes it)" % expected,
            )

    def test_prep_suggested_playbook_only_targets_files_the_table_lists(self):
        table_basenames = {Path(pb).name for pb in self.playbooks}
        for issue_type in ("standard", "story", "epic"):
            self.assertIn(prep_resolver._suggested_playbook(issue_type, False), table_basenames)
        self.assertIn(prep_resolver._suggested_playbook("standard", True), table_basenames)

    def test_spine_referenced_by_standard_and_story_only(self):
        # The shared spine (resolve-spine.md) is read by the two code-shipping routes; comment-only.md
        # and epic.md are distinct action flows that do NOT read the spine (architecture.md §5).
        spine_path = PLAYBOOKS_DIR / SPINE
        self.assertTrue(spine_path.is_file(), "the shared spine resolve-spine.md must exist")
        for name in ("standard.md", "story.md"):
            text = (PLAYBOOKS_DIR / name).read_text(encoding="utf-8")
            self.assertIn(SPINE, text, "%s must read the shared spine" % name)
        for name in ("comment-only.md", "epic.md"):
            text = (PLAYBOOKS_DIR / name).read_text(encoding="utf-8")
            self.assertNotIn(
                "resolve-spine.md](resolve-spine.md",
                text,
                "%s must NOT pull in the code-shipping spine (it is a distinct action flow)" % name,
            )


# ---------------------------------------------------------------------------
# Router structural bar (S10 DoD boxes 1, 5, 7)
# ---------------------------------------------------------------------------


def _iter_md(dir_path):
    yield from sorted(dir_path.rglob("*.md"))


def _fence_stripped_lines(path):
    """Yield (lineno, line, in_fence) for a markdown file, tracking ``` fenced code blocks so a
    prose mention of a banned command (describing what NOT to do) is distinguishable from an actual
    command in a code block."""
    in_fence = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            yield i, line, in_fence
            continue
        yield i, line, in_fence


class RouterStructuralBarTests(unittest.TestCase):
    def test_router_at_most_150_lines(self):
        n = len(ROUTER.read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(n, 150, "router SKILL.md is %d lines (bar: <= 150)" % n)

    def test_router_plus_largest_playbook_at_most_half_v1(self):
        # S10 DoD box 7 / prd.md §10: router + largest playbook <= half of v1's 1169 = 584.
        router_lines = len(ROUTER.read_text(encoding="utf-8").splitlines())
        playbook_lines = {
            p.name: len(p.read_text(encoding="utf-8").splitlines())
            for p in PLAYBOOKS_DIR.glob("*.md")
        }
        largest = max(playbook_lines.values())
        self.assertLessEqual(
            router_lines + largest,
            V1_HALF_BAR,
            "router (%d) + largest playbook (%d) = %d exceeds %d (half of v1's 1169): %r"
            % (router_lines, largest, router_lines + largest, V1_HALF_BAR, playbook_lines),
        )


class PlaybookInterleavingGrepTests(unittest.TestCase):
    """S10 DoD box 1: the interleaving pattern-grep, committed as a validator. A playbook is a linear
    narrative for exactly one route — zero cross-type conditionals. This fails on either form of
    type-interleaving in any playbook (routable or the spine):

      - an `if … <type> … else …` conditional construct, and
      - a `when the issue/PR/type is a <type>` prose branch.

    Both are the constructs a v1-to-v2 whittle would leave behind; the route IS the branch, so a
    playbook that switches on the type has drifted off the §5 bar.
    """

    # Conditional construct: `if <...> (type) <...> else`.
    _IF_ELSE = re.compile(
        r"\bif\b[^.\n]{0,50}\b(story|standard|epic|comment-only)\b[^.\n]{0,50}\belse\b",
        re.IGNORECASE,
    )
    # Prose branch: `when (the issue|the pr|the type|it's) [is] (a|an) <type>`.
    _WHEN_TYPE = re.compile(
        r"\bwhen (the (issue|pr|type) is|it.?s)\s+(a |an )?(story|standard|epic|comment-only)\b",
        re.IGNORECASE,
    )

    def test_playbooks_have_no_cross_type_conditionals(self):
        for playbook in PLAYBOOKS_DIR.glob("*.md"):
            text = playbook.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                self.assertIsNone(
                    self._IF_ELSE.search(line),
                    "playbook %s:%d looks like a cross-type conditional: %r"
                    % (playbook.name, i, line),
                )
                self.assertIsNone(
                    self._WHEN_TYPE.search(line),
                    "playbook %s:%d looks like a when-<type> prose branch: %r"
                    % (playbook.name, i, line),
                )


class ContractTokenGateTests(unittest.TestCase):
    """S10 DoD box 5: grep gates over skills/resolver/ — zero retired-executor tokens, zero v1 skill-invocation
    namespace strings, zero GATHER_/PERSIST_ op names, zero §P IDs, zero raw persist/gather writes,
    zero ref-arithmetic. Prose that *describes* a banned form (a pitfall telling you NOT to hand-roll
    `gh issue create`, or the audit note explaining the v1 `git show <ref>:` reads it replaced) is
    allowed OUTSIDE a code fence; an actual command inside a ``` fence is a violation."""

    def test_no_github_ops_or_old_names_or_op_names_or_pids(self):
        forbidden = FORBIDDEN_CONTRACT_TOKENS
        for path in _iter_md(SKILL_DIR):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                hit = forbidden.search(line)
                self.assertIsNone(
                    hit,
                    "forbidden contract token under skills/resolver/ at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )

    def test_no_raw_persist_or_gather_writes_in_code_fences(self):
        # A persist/gather WRITE that bypasses gh_persist.py: gh issue|pr create/edit/comment/review/
        # close/reopen, or gh api ... DELETE. Only flag inside a ``` code fence (a real command); the
        # resolver has no scriptless raw-gh executor (merge is the evaluator's), so any such command
        # is a violation. Sub-agent self-fetch READS (gh issue view / gh api ...comments) are not
        # writes and don't match.
        raw_write = re.compile(
            r"\bgh\s+(issue|pr)\s+(create|edit|comment|review|close|reopen)\b"
            r"|\bgh\s+api\b[^\n]*\bDELETE\b"
        )
        for path in _iter_md(SKILL_DIR):
            for i, line, in_fence in _fence_stripped_lines(path):
                if not in_fence:
                    continue
                hit = raw_write.search(line)
                self.assertIsNone(
                    hit,
                    "raw gh persist/gather WRITE in a code fence at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )

    def test_no_ref_arithmetic_in_code_fences(self):
        # Banned ref-arithmetic (architecture.md §6/§10): git show <ref>:<path> and git grep <ref>.
        # A bare `git show <commit>` single-commit view is permitted; only <ref>:<path> extraction and
        # `git grep <ref>` are banned. Flag only inside a code fence.
        ref_arith = re.compile(r"\bgit\s+show\s+\S+:\S|\bgit\s+grep\b[^\n]*\s+[a-z]+/[^\s-]")
        for path in _iter_md(SKILL_DIR):
            for i, line, in_fence in _fence_stripped_lines(path):
                if not in_fence:
                    continue
                hit = ref_arith.search(line)
                self.assertIsNone(
                    hit,
                    "ref-arithmetic in a code fence at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )

    def test_no_w_slash_shorthand(self):
        # CLAUDE.md's banned-shorthand validator is `grep -rnE '\bw/'` (word-boundary), so "review/"
        # (w preceded by a word char) is not a hit — only a standalone "w/" abbreviation is.
        w_shorthand = re.compile(r"\bw/")
        for path in _iter_md(SKILL_DIR):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(
                    w_shorthand.search(line),
                    "banned w/ shorthand at %s:%d — %r" % (path.relative_to(REPO_ROOT), i, line),
                )


# ---------------------------------------------------------------------------
# --dry-run persist envelopes for the writes the playbooks specify
# ---------------------------------------------------------------------------


def _run_persist(args, body_text=None):
    """Run gh_persist.py <args> as a real subprocess under the offline shim. When body_text is given,
    write it to a temp file and substitute @BODY@ in args with the path. Returns
    (completed_process, parsed_envelope_or_None)."""
    env = shimenv.intercepted_env(base_env=os.environ, fixture_case=None)
    ctx = None
    if body_text is not None:
        ctx = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        ctx.write(body_text)
        ctx.close()
        args = [a.replace("@BODY@", ctx.name) for a in args]
    try:
        proc = subprocess.run(
            [sys.executable, str(GH_PERSIST)] + args,
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
    finally:
        if ctx is not None:
            os.unlink(ctx.name)
    envelope = None
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if len(lines) == 1:
        envelope = json.loads(lines[0])
    return proc, envelope


class SliceClosingRungTests(unittest.TestCase):
    """S6's slice-closing rung (#17). Slices exist so GitHub's rollup tracks delivery progress, so a
    slice set that never closes leaves a permanent `0/N` — worse than filing none. These pin the three
    things that make the rung correct rather than merely present."""

    def setUp(self):
        raw = (PLAYBOOKS_DIR / SPINE).read_text(encoding="utf-8")
        self.spine = re.sub(r"\s+", " ", raw.replace("**", ""))
        self.rule = re.sub(
            r"\s+",
            " ",
            (REFERENCES_DIR / "dod-projection-rule.md").read_text(encoding="utf-8").replace("**", ""),
        )

    def test_the_rung_keys_off_the_phase_sub_issue_field(self):
        self.assertIn("sub_issue", self.spine)
        self.assertIn("facts.phases", self.spine)

    def test_it_closes_on_the_last_serving_phase_not_the_first(self):
        """N:1 — several phases may serve one slice. Closing on the first would report an increment
        complete while part of it is still unbuilt."""
        self.assertRegex(self.spine, r"closes on the last of the phases serving it, never the first")
        self.assertRegex(self.rule, r"Close only when every phase naming it is ticked")

    def test_substrate_and_unmapped_phases_close_nothing(self):
        self.assertRegex(self.spine, r"\(none\).{0,20}is substrate")
        self.assertRegex(self.spine, r"is unmapped; both close nothing")
        self.assertRegex(self.rule, r"close nothing")

    def test_closing_before_merge_is_justified_by_the_demonstrable_bar(self):
        """The objection this pre-empts: "you closed an issue whose code isn't on main"."""
        self.assertRegex(self.spine, r"bar is .demonstrable.")
        self.assertRegex(self.spine, r"not that its code is on the default branch")

    def test_tier_1_ticks_the_acceptance_criteria_not_a_dod(self):
        self.assertIn("## Acceptance criteria", self.spine)
        self.assertRegex(self.rule, r"DoD contract above applies to the parent")

    def test_both_writes_are_idempotent_so_the_backstop_can_re_run(self):
        self.assertRegex(self.spine, r"[Bb]oth are idempotent")
        self.assertRegex(self.rule, r"Already-closed slice.*no-op")

    def test_slice_close_dry_run(self):
        proc, env = _run_persist(["close", "octo/widgets", "104", "--reason", "completed", "--dry-run"])
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        envelope_asserts.assert_full_envelope_conformance(env)
        self.assertEqual(env.get("op"), "close")
        self.assertTrue(env.get("dry_run"))
        self.assertIn("would_run", env)


class TrackerReconciliationTests(unittest.TestCase):
    """#46: the PR's `## Phase tracker` is reconciled against the plan before the cursor is read.

    The tracker and the plan's `## Phases` are two artifacts keyed by the same integer phase numbers,
    written by different sessions. A planner revise may insert a phase and renumber the unshipped tail,
    which changes the row set — and continue mode selects its next phase by ROW NUMBER. Unreconciled,
    the cursor silently points at different work, and a tracker with fewer rows than the plan reads as
    complete and flips the PR draft → ready early.
    """

    def setUp(self):
        self.spine_path = PLAYBOOKS_DIR / SPINE
        self.spine = self.spine_path.read_text(encoding="utf-8")
        self.flat = " ".join(self.spine.split())
        self.renderings = (REFERENCES_DIR / "handoff-renderings.md").read_text(encoding="utf-8")

    def test_the_tracker_is_a_prep_fact_not_a_model_re_read(self):
        self.assertIn("parsed by prep into `facts.tracker.rows`, never re-fetched", self.flat)
        self.assertNotIn("re-read from the existing PR body", self.flat)

    def test_authority_is_split_between_tick_state_and_row_set(self):
        # The un-qualified "authoritative record" is why nothing rebuilt the rows.
        self.assertIn("authoritative record of which phases **shipped**", self.flat)
        self.assertIn("not authoritative for which phases *exist*", self.flat)
        self.assertIn("(`facts.phases`) owns the row set", self.flat)

    def test_reconciliation_precedes_cursor_selection(self):
        self.assertLess(
            self.flat.index("Reconcile the tracker before you read that cursor"),
            self.flat.index("Write the reconciled tracker"),
        )
        self.assertIn("then select the cursor from it", self.flat)
        self.assertIn("Never select a phase by row title", self.flat)

    def test_the_three_silent_rebuild_classes_are_named_with_their_disposition(self):
        for key in ("`missing`", "`dropped`", "`retitled`"):
            self.assertIn(key, self.flat, key)
        self.assertIn("All three are a silent rebuild: no tick's meaning changes", self.flat)

    def test_unticked_rows_are_rebuilt_wholesale_including_their_title(self):
        # The common post-insert shape: the tail row keeps its number and takes the NEW phase's title,
        # and the displaced phase arrives as a `missing` row. Prep reports no drift for it (there is no
        # tick or commit to preserve), so the spine must say what to do without a diff entry to key on
        # — otherwise the resolver builds the inserted work under the displaced phase's title.
        self.assertIn("Every **unticked** row is rewritten from its plan phase wholesale", self.flat)
        self.assertIn("takes the new phase's title", self.flat)

    def test_a_sub_row_is_carried_through_rather_than_reconciled(self):
        # #51: the spine must say what to do with a `Phase <N>-<label>` row, or a rebuild drops the
        # operator annotation that is the only record the phase landed.
        self.assertIn("`diff.sub_rows`", self.flat)
        self.assertIn("carry it through verbatim", self.flat)
        self.assertIn("bound to phase `<N>`", self.flat)

    def test_the_two_unknowable_state_classes_gate_for_their_own_reason(self):
        # #48 review: `unparsed` (rows prep could not read) and `duplicated` (two rows for one phase)
        # gate because the tick state is unknowable, not because work moved. Rebuilding under either
        # would guess what shipped.
        self.assertIn("`unparsed`", self.flat)
        self.assertIn("`duplicated`", self.flat)
        self.assertIn("The tick state is\n  unknowable", self.spine.replace("\r\n", "\n"))
        self.assertIn("mean guessing what shipped", self.flat)

    def test_the_rebuild_preserves_an_operator_annotation_not_just_a_commit(self):
        # An operator row's `(operator action <ISO-date>)` is the only record that phase landed, so a
        # rebuild that preserved only `(commit <sha>)` would erase it.
        self.assertIn("`(commit <sha>)` or `annotation`", self.flat)
        self.assertIn("the only record that phase landed", self.flat)

    def test_conflict_is_a_gate_with_its_three_recorded_options(self):
        self.assertIn('header: "Tracker drift"', self.flat)
        for option in ("**Re-plan**", "**Rebuild un-ticked**", "**Abort**"):
            self.assertIn(option, self.flat, option)
        self.assertIn("`diff.conflict`", self.flat)

    def test_the_conflict_classes_are_named_and_defined(self):
        self.assertIn("`shifted` (a ticked row whose work now sits at a different phase number)", self.flat)
        self.assertIn("`removed_shipped` (a ticked row whose phase is gone)", self.flat)

    def test_the_override_never_carries_a_tick_onto_work_it_did_not_ship(self):
        self.assertIn("never carry a tick onto work it did not ship", self.flat)
        self.assertIn("## Tracker reconciliation", self.flat)
        self.assertIn("displaced", self.flat)

    def test_the_gate_names_the_planner_rule_it_is_downstream_of(self):
        self.assertIn("revise-reconciliation.md", self.flat)
        self.assertIn("classifies HARD at the planner", self.flat)

    def test_s6_writes_the_reconciled_row_set(self):
        self.assertIn("the **reconciled** row set from S4, never the rows a prior session wrote", self.flat)

    def test_completion_condition_runs_against_the_reconciled_tracker(self):
        flat_renderings = " ".join(self.renderings.split())
        self.assertIn("ticked in the **reconciled** `## Phase tracker` (spine S4)", flat_renderings)
        self.assertIn("*unshipped*, never not-applicable", flat_renderings)

    def test_router_lists_the_tracker_fact(self):
        router = " ".join(ROUTER.read_text(encoding="utf-8").split())
        self.assertIn("`tracker`", router)
        self.assertIn("`diff.conflict` the gate", router)

    def test_prep_owns_the_pr_fetch_no_raw_gh_pr_view_in_a_fence(self):
        # facts-by-script: the body comes from prep_resolver's gh_pr_gather call, never a fenced
        # `gh pr view` the model runs itself.
        for lineno, line, in_fence in _fence_stripped_lines(self.spine_path):
            if in_fence:
                self.assertNotIn("gh pr view", line, "%s:%d" % (SPINE, lineno))

    def test_structural_bar_still_holds(self):
        router_lines = len(ROUTER.read_text(encoding="utf-8").splitlines())
        playbooks = {
            path.name: len(path.read_text(encoding="utf-8").splitlines())
            for path in PLAYBOOKS_DIR.glob("*.md")
        }
        self.assertLessEqual(
            router_lines + max(playbooks.values()),
            V1_HALF_BAR,
            "#46 added the S4 reconciliation step: %r" % playbooks,
        )


class PlaybookPersistDryRunTests(unittest.TestCase):
    """Each GitHub write the resolver playbooks specify, run with --dry-run: a conformant envelope,
    status ok, `would_run` present, exit 0, no live gh call. These are the exact gh_persist invocation
    SHAPES the playbooks name (spine S5 PR create; S6 issue-body DoD projection + Phase tracker;
    comment-only S2; epic.md S4 integration PR + S5 body-tick + the baseline comments)."""

    def _assert_dry_run_ok(self, proc, envelope, expected_op):
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        self.assertIsNotNone(envelope, "expected exactly one envelope on stdout")
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope.get("status"), "ok")
        self.assertEqual(envelope.get("op"), expected_op)
        self.assertTrue(envelope.get("dry_run"))
        self.assertIn("would_run", envelope)

    def test_dod_projection_edit_body_dry_run(self):
        # spine S6: gh_persist.py edit-body <repo> <issue> <issue-body-projected.md>
        proc, env = _run_persist(
            ["edit-body", "octo/widgets", "142", "@BODY@", "--dry-run"],
            body_text="## Definition of done\n- [x] Export CSV (closed by phase 2, commit abc1234)\n",
        )
        self._assert_dry_run_ok(proc, env, "edit-body")

    def test_comment_only_answer_dry_run(self):
        # comment-only.md S2: gh_persist.py comment <repo> issue <issue> <comment.md>
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "142", "@BODY@", "--dry-run"],
            body_text="This issue is blocked by the open question in #77.\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_epic_baseline_comment_dry_run(self):
        # epic.md S3 / epic-flow.md: gh_persist.py comment <repo> issue <epic> <baseline.md>
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "150", "@BODY@", "--dry-run"],
            body_text="🤖 Baseline established\n- Epic branch SHA: abc1234\n- Main SHA: abc1234\n- Result: green\n- Date: 2026-07-09\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_epic_body_tick_edit_body_dry_run(self):
        # epic.md S5: gh_persist.py edit-body <repo> <epic> <epic-body-closed.md>
        proc, env = _run_persist(
            ["edit-body", "octo/widgets", "150", "@BODY@", "--dry-run"],
            body_text="## Stories\n- [x] #151\n## Definition of done\n- [x] all shipped\n",
        )
        self._assert_dry_run_ok(proc, env, "edit-body")

    def test_dry_run_makes_no_live_gh_call(self):
        # Belt-and-braces: the dry-run path must not touch gh at all. A clean exit 0 with a would_run
        # envelope (and no url) IS the proof no gh call fired.
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "142", "@BODY@", "--dry-run"],
            body_text="answer\n",
        )
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        self.assertTrue(env.get("dry_run"))
        self.assertNotIn("url", env, "a dry-run must not carry a live-write url")


class PrCreateContractTests(unittest.TestCase):
    """The PR-open write-path gap this step originally reported is CLOSED: the coordinator
    authorized an additive `create-pr` op on `gh_persist.py` within S10 (architecture.md §2 "if a
    needed operation has no script, extend a script"), landed alongside this skill cutover. These
    tests assert the op's existence + contract (the resolver playbooks' actual invocation shape) at
    the resolver-cutover layer; the op's own exhaustive coverage (happy path, --draft, EMPTY_BODY_FILE,
    AUTH_REQUIRED, dry-run, usage errors, receipts) lives in
    `tests/test_gh_persist.py::CreatePrHappyPathTests`."""

    def test_gh_persist_has_create_pr_subcommand_with_required_flags(self):
        proc = subprocess.run(
            [sys.executable, str(GH_PERSIST), "create-pr", "--help"],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        help_text = proc.stdout + proc.stderr
        for flag in ("--title", "--base", "--head", "--draft", "--dry-run"):
            self.assertIn(flag, help_text, "gh_persist.py create-pr must accept %s" % flag)

    def test_standard_route_pr_open_dry_run(self):
        # spine S5 fresh-mode first push, standard route: base main, ready (no --draft).
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@", "--title", "Add CSV export (#142)",
                "--base", "main", "--head", "142-add-csv-export", "--dry-run",
            ],
            body_text="## Doc grounding\ncites architecture.md §3\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        envelope_asserts.assert_full_envelope_conformance(env)
        self.assertEqual(env.get("op"), "create-pr")
        self.assertTrue(env.get("dry_run"))
        self.assertIn("would_run", env)
        self.assertNotIn("--draft", env["would_run"])

    def test_story_route_pr_open_dry_run_bases_on_epic_branch(self):
        # story.md: base is the parent epic's integration branch, never main.
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@", "--title", "Add export service (#151)",
                "--base", "epic/150-chat-session-ux-polish", "--head", "151-add-export-service",
                "--dry-run",
            ],
            body_text="This story targets the `epic/150-chat-session-ux-polish` integration branch.\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(env.get("op"), "create-pr")
        self.assertIn("epic/150-chat-session-ux-polish", env["would_run"])

    def test_multi_phase_pr_open_dry_run_carries_draft_flag(self):
        # spine S4/S5: a multi-phase issue opens the PR as draft; the last-phase handoff later
        # flips it ready via the sanctioned `gh pr ready` toggle (architecture.md §10), unaffected
        # by this op.
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@", "--title", "feat(llm): #640 spike harness",
                "--base", "main", "--head", "640-spike", "--draft", "--dry-run",
            ],
            body_text="## Phase tracker\n- [ ] Phase 1 — substrate\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("--draft", env["would_run"])

    def test_epic_integration_pr_open_dry_run_carries_draft_flag(self):
        # epic.md S4.1: base main, head the epic integration branch, and ALWAYS --draft. The PR
        # opens early (as soon as the branch is ahead of main) so a human can review overall epic
        # progress; draft is what keeps it out of the evaluator's reach until S4.4's ready flip.
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@", "--title", "Epic #150: Chat & session UX polish",
                "--base", "main", "--head", "epic/150-chat-session-ux-polish", "--draft", "--dry-run",
            ],
            body_text="## Goal\n…\nFixes #150\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(env.get("op"), "create-pr")
        self.assertIn("--draft", env["would_run"])

    def test_epic_integration_pr_body_refresh_routes_through_edit_pr_body(self):
        # epic.md S4.2: the draft PR's body is refreshed on every epic run. `edit-body` is
        # `gh issue edit` and rejects a PR number, so this is a distinct op, not a reuse.
        proc, env = _run_persist(
            ["edit-pr-body", "octo/widgets", "300", "@BODY@", "--dry-run"],
            body_text="## Goal\n…\n3 of 5 stories closed\nFixes #150\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(env.get("op"), "edit-pr-body")
        self.assertIn("pr edit", env["would_run"])
        self.assertNotIn("issue edit", env["would_run"])

    def test_epic_playbook_parameterises_the_pr_steps_on_prep_facts(self):
        # facts-by-script: the early-open trigger and the idempotency guard are prep facts the
        # playbook consumes as data. A rewrite that drops these names has re-derived one of them
        # in prose (a hand-counted "is it ahead of main" or a hand-searched "is a PR already
        # open" is exactly the duplicate-PR hazard these facts exist to remove).
        text = (PLAYBOOKS_DIR / "epic.md").read_text(encoding="utf-8")
        for fact in ("commits_ahead", "commits_ahead_base", "integration_pr", "edit-pr-body"):
            self.assertIn(fact, text, "epic.md must name %s" % fact)
        self.assertIn(
            "OPEN_PR_LOOKUP_UNAVAILABLE",
            text,
            "epic.md must gate its PR-open on the lookup notice's absence — a null "
            "integration_pr carried by that notice is UNKNOWN, not ABSENT, and opening on an "
            "unknown files a second integration PR",
        )

    def test_playbooks_route_pr_open_through_create_pr_not_a_fabricated_flag_set(self):
        # The resolve-spine.md / epic.md prose must name the real op (create-pr), not the
        # non-existent `create --base/--head` shape this step originally (wrongly) drafted.
        for playbook in ("resolve-spine.md", "epic.md"):
            text = (PLAYBOOKS_DIR / playbook).read_text(encoding="utf-8")
            self.assertIn(
                "create-pr",
                text,
                "%s must route PR-open through gh_persist.py create-pr" % playbook,
            )

    def test_spine_mandates_the_closing_keyword_on_fresh_pr_open(self):
        # Filed defect (S10 live parity, scenario 1 D2 — docs/specs/parity/resolver.md): v1
        # (SKILL.md:888) mandates the PR body carry `Fixes #<number>` (or `Closes #<number>`) so
        # GitHub auto-links and auto-closes on merge; v2's spine had listed every OTHER PR-body
        # section (Doc grounding / Plan / Audit override / Plan override / Phase tracker /
        # Predecessor) but omitted this mandate, so v2 PRs never auto-closed. Regression guard: the
        # spine's fresh-mode PR-open prose must state the mandate.
        text = (PLAYBOOKS_DIR / "resolve-spine.md").read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"Fixes #<issue-number>.{0,40}Closes\s*\n?\s*#<issue-number>",
            "resolve-spine.md must mandate the closing keyword (Fixes/Closes #<issue-number>) on "
            "fresh-PR open, per v1 SKILL.md:888",
        )
        self.assertIn(
            "must be `Fixes #<issue-number>`",
            text,
            "the closing keyword must be stated as mandatory, not optional prose",
        )

    def test_spine_mandates_the_v1_fresh_pr_title_shape(self):
        # D4 (checked, ruled MANDATED): v1 SKILL.md:885 passes a literal --title "Fix: <summary>
        # (#<issue-number>)" to `gh pr create` -- not free prose, a command-line argument every
        # fresh-PR-open takes. The spine must be faithful to that shape (it also feeds the
        # evaluator's squash-subject derivation, which reads a Conventional-Commits-prefixed title).
        text = (PLAYBOOKS_DIR / "resolve-spine.md").read_text(encoding="utf-8")
        self.assertIn(
            'Fix: <summary> (#<issue-number>)',
            text,
            "resolve-spine.md must mandate the v1 fresh-PR title shape, per SKILL.md:885",
        )

    def test_create_pr_dry_run_with_closing_keyword_and_mandated_title(self):
        # End-to-end dry-run proof: the exact title shape + a body whose first line is the closing
        # keyword round-trips cleanly through gh_persist.py create-pr.
        proc, env = _run_persist(
            [
                "create-pr", "octo/widgets", "@BODY@",
                "--title", "Fix: greet() returns a personalized greeting (#142)",
                "--base", "main", "--head", "142-add-csv-export", "--dry-run",
            ],
            body_text="Fixes #142\n\n## Doc grounding\ncites architecture.md §3\n",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertEqual(env.get("op"), "create-pr")
        self.assertIn("Fix: greet() returns a personalized greeting (#142)", env["would_run"])


class ArtifactRenderingByteCompatTests(unittest.TestCase):
    """S10 DoD box 2 (offline half): the DoD-projection annotation forms the resolver writes must diff
    clean against the S1-captured closed set (docs/specs/examples/dod-annotations.md). The three
    resolver-authored ticked forms are contract tokens (the evaluator + planner parse them verbatim),
    so each must appear byte-for-byte in the resolver's dod-projection-rule.md."""

    EXAMPLES_DIR = REPO_ROOT / "docs" / "specs" / "examples"

    # The three ticked forms the resolver authors (dod-annotations.md capture rows for "resolver §9").
    RESOLVER_FORMS = (
        "- [x] <text> (closed by phase <N>, commit <short-sha>)",
        "- [x] <text> (closed by phase <N>, operator action <ISO-date>)",
        "- [x] <text> (closed by commit <short-sha>)",
    )

    def test_resolver_annotation_forms_present_in_s1_capture(self):
        # Guard the source: each resolver-authored form must be a row in the S1 capture verbatim, so
        # the byte-compat check below is anchored to the frozen contract, not a moving target.
        capture = (self.EXAMPLES_DIR / "dod-annotations.md").read_text(encoding="utf-8")
        for form in self.RESOLVER_FORMS:
            self.assertIn(form, capture, "S1 dod-annotations capture must carry %r" % form)

    def test_projection_rule_renders_each_resolver_form_byte_compatible(self):
        rule = (REFERENCES_DIR / "dod-projection-rule.md").read_text(encoding="utf-8")
        for form in self.RESOLVER_FORMS:
            self.assertIn(
                form,
                rule,
                "dod-projection-rule.md must render the annotation form %r byte-for-byte (it "
                "diverges from the S1 capture otherwise — box 2)" % form,
            )


class QuestionTypeHandoffVariantTests(unittest.TestCase):
    """Filed defect (S10 live parity, scenario 3 D1 — docs/specs/parity/resolver.md): a `question`-type
    issue's terminal handoff must follow skills/_shared/handoff-format.md's question-type rule (omit
    research:/plan: entirely, add an Audience: line) — v2 had rendered `· plan: ✗` and dropped
    Audience:. Fixed in comment-only.md's Handoff section (dispatches by the issue's own type) +
    handoff-renderings.md (a dedicated "Terminal — question-type issue" shape). These tests assert the
    fix without editing _shared (render, don't restate)."""

    RENDERINGS = REFERENCES_DIR / "handoff-renderings.md"
    COMMENT_ONLY = PLAYBOOKS_DIR / "comment-only.md"

    @staticmethod
    def _fenced_blocks(path, fence="```"):
        text = path.read_text(encoding="utf-8")
        blocks, cur, inb = [], [], False
        for line in text.splitlines():
            if line.strip() == fence:
                if inb:
                    blocks.append("\n".join(cur))
                    cur = []
                    inb = False
                else:
                    inb = True
                continue
            if inb:
                cur.append(line)
        return blocks

    def test_question_type_variant_present_and_shaped_per_shared_contract(self):
        text = self.RENDERINGS.read_text(encoding="utf-8")
        self.assertIn(
            "## Terminal — question-type issue",
            text,
            "handoff-renderings.md must carry a dedicated question-type terminal shape",
        )
        # Isolate the actual RENDERED example (the fenced ## Handoff block) -- the surrounding prose
        # legitimately explains the rule by naming the forbidden marker ("do not render `plan: ✗`
        # here"), which must not itself trip a naive whole-section grep (same fence-scoping
        # discipline as ContractTokenGateTests' raw-gh / ref-arithmetic checks).
        rendered_blocks = [b for b in self._fenced_blocks(self.RENDERINGS) if "## Handoff" in b]
        question_rendering = next(
            (b for b in rendered_blocks if "· question" in b and "**Audience:**" in b), None
        )
        self.assertIsNotNone(
            question_rendering, "the question-type section must contain a rendered ## Handoff example"
        )
        # The Issue: line for this shape must end at the type marker `· question` -- no plan:/research:
        # segment at all (handoff-format.md:33: "the research: and plan: markers omitted").
        self.assertRegex(
            question_rendering,
            r"\*\*Issue:\*\* #\d+ — [^\n]+ · open · question\s*\n",
            "the question-type Issue: line must end at '· question' with no plan:/research: marker",
        )
        self.assertNotRegex(
            question_rendering,
            r"plan:\s*[✓✗]",
            "the RENDERED question-type shape must never carry a plan: marker (handoff-format.md's "
            "rule) -- prose explaining the rule is fine; the example itself must not regress",
        )
        self.assertIn(
            "**Audience:**",
            question_rendering,
            "the question-type shape must carry the Audience: line per handoff-format.md",
        )

    def test_non_pr_resolution_shape_unchanged_for_build_types(self):
        # The pre-existing "Terminal — non-PR resolution" shape (OQ refusal / triage / decline on a
        # build-type issue) still renders its plan: marker -- only the question-type issue's own
        # handoff omits it.
        text = self.RENDERINGS.read_text(encoding="utf-8")
        self.assertIn("## Terminal — non-PR resolution", text)
        section = text.split("## Terminal — non-PR resolution", 1)[1].split(
            "## Terminal — question-type issue", 1
        )[0]
        self.assertIn("plan:", section)

    def test_comment_only_playbook_dispatches_by_issue_type(self):
        text = self.COMMENT_ONLY.read_text(encoding="utf-8")
        self.assertIn(
            "question-type issue",
            text,
            "comment-only.md's Handoff section must route a genuine question-type issue to the "
            "dedicated rendering, not the build-type Terminal — non-PR resolution shape",
        )
        self.assertIn("non-PR resolution", text)


class ReRouteHandoffMarkerTests(unittest.TestCase):
    """Filed defect (S10 live parity, scenario 2 D1 — docs/specs/parity/resolver.md): the multi-phase
    re-route worked example (and two siblings) carried an off-closed-set `✓` glyph on the PR-line
    `review:`/`health:` markers, contradicting the reference's own forward-scoped intro. RULING (per
    _shared/handoff-format.md's actual field definitions, evaluator-owned — see the D1 annotation):
    `not run` is the conformant value on EVERY resolver-authored handoff, forward or re-route alike,
    because those two fields denote the evaluator's posted verdict / health-cache result, never "the
    resolver's own /review loop or §8 gate ran." These tests assert every rendered PR-line in
    handoff-renderings.md stays on the closed set, and that the intro states the unconditional scope."""

    RENDERINGS = REFERENCES_DIR / "handoff-renderings.md"
    STANDARD = PLAYBOOKS_DIR / "standard.md"

    @staticmethod
    def _fenced_blocks(path, fence="```"):
        text = path.read_text(encoding="utf-8")
        blocks, cur, inb = [], [], False
        for line in text.splitlines():
            if line.strip() == fence:
                if inb:
                    blocks.append("\n".join(cur))
                    cur = []
                    inb = False
                else:
                    inb = True
                continue
            if inb:
                cur.append(line)
        return blocks

    def test_epic_draft_pr_handoff_never_points_at_the_evaluator(self):
        # The load-bearing guard for the early-open change: the evaluator refuses a DRAFT PR
        # (skills/evaluator/SKILL.md's draft-PR guard), so a handoff that points there while the
        # integration PR is still a draft deadlocks the operator. The in-progress shape's Next: is
        # the epic cadence's next step instead.
        text = self.RENDERINGS.read_text(encoding="utf-8")
        self.assertIn(
            "## In progress — Epic integration draft PR open",
            text,
            "handoff-renderings.md must carry the draft-integration-PR in-progress shape",
        )
        draft_rendering = next(
            (
                block
                for block in self._fenced_blocks(self.RENDERINGS)
                if "## Handoff" in block and "**PR:**" in block and "· draft ·" in block
                and "**Epic:**" in block
            ),
            None,
        )
        self.assertIsNotNone(
            draft_rendering,
            "the in-progress section must contain a rendered ## Handoff example whose PR: line "
            "carries the closed-set `draft` state marker",
        )
        self.assertNotIn(
            "github-pipeline:evaluator",
            draft_rendering,
            "a draft epic integration PR must never hand off to the evaluator — its draft guard "
            "would stop the session with nothing to do",
        )

    def test_no_pr_line_carries_an_off_closed_set_review_or_health_glyph(self):
        # The closed set has no bare-checkmark value for either field (handoff-format.md:52-53) --
        # every rendered PR: line's review:/health: segment must be one of the defined values, never
        # a raw ✓/✗ glyph standing in for "ran, no formal verdict."
        off_vocab = re.compile(r"\b(review|health):\s*[✓✗]")
        for block in self._fenced_blocks(self.RENDERINGS):
            if "**PR:**" not in block:
                continue
            self.assertNotRegex(
                block,
                off_vocab,
                "an off-closed-set ✓/✗ glyph on review:/health: survives in a rendered PR: line: %r"
                % block,
            )

    def test_every_resolver_authored_pr_line_before_evaluator_action_is_not_run(self):
        # Every PR: line rendered by a shape that fires BEFORE the evaluator has acted (forward opens,
        # every re-route) must carry review: not run / health: not run. The two shapes that legitimately
        # carry an evaluator-populated value (the plan-currency re-route, which CAN carry a value the
        # evaluator posted on a PRIOR pass) are the only exception, and even there review: stays not run
        # in the frozen worked example -- so this asserts the floor: review: not run appears on every
        # PR: line in the file (a stricter, always-true invariant this reference's worked examples
        # satisfy today).
        text = self.RENDERINGS.read_text(encoding="utf-8")
        pr_lines = [
            line for block in self._fenced_blocks(self.RENDERINGS)
            for line in block.splitlines() if line.strip().startswith("**PR:**")
        ]
        self.assertTrue(pr_lines, "expected at least one rendered PR: line")
        for line in pr_lines:
            self.assertIn(
                "review: not run",
                line,
                "every resolver-authored PR: line must carry review: not run (the evaluator hasn't "
                "acted yet on any resolver exit): %r" % line,
            )
        self.assertIn(
            "not run",
            text,
            "handoff-renderings.md must still document the not-run rule",
        )

    def test_intro_states_the_unconditional_not_run_scope(self):
        # Regression guard for the root cause: the intro must not scope the not-run rule to forward
        # exits only -- it must explicitly cover every re-route too (including mid-phases continue).
        text = self.RENDERINGS.read_text(encoding="utf-8")
        self.assertIn(
            "every resolver-authored handoff",
            text,
            "the intro must state the not-run rule unconditionally, not forward-exit-scoped",
        )
        self.assertIn(
            "AND every re-route",
            text,
            "the intro must explicitly cover re-routes, including the mid-phases continue-mode case",
        )
        self.assertNotIn(
            'on a resolver forward exit because the resolver never runs',
            text,
            "the old forward-scoped phrasing (the root-cause ambiguity) must not survive",
        )

    def test_standard_playbook_states_the_rule_inline_for_multiphase_shapes(self):
        # The routed playbook must not depend entirely on the reference getting the rule right --
        # restate it inline for the multi-phase bullet, where the D1 defect actually surfaced.
        text = self.STANDARD.read_text(encoding="utf-8")
        self.assertIn(
            "review: not run · health: not run",
            text,
            "standard.md's multi-phase bullet must restate the not-run rule inline",
        )


class WorkspaceModelV3Tests(unittest.TestCase):
    """v3 workspace-model pins: the router names WORKSPACE_MISMATCH (the ambient-assertion
    decision), and no resolver prose or fence invokes worktree removal — every removal is the
    operator's workspace-close."""

    def test_router_names_workspace_mismatch(self):
        router = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("WORKSPACE_MISMATCH", router)
        self.assertIn("workspace-open", router)

    def test_no_remove_work_invocation_anywhere(self):
        for path in sorted(SKILL_DIR.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "remove --work", text,
                "%s still invokes worktree removal — that is workspace-close's, exclusively"
                % path.name,
            )


class MainLoopReviewFixRoundTests(unittest.TestCase):
    """4.11.0: the per-iteration fix sub-agent is retired — the fix round runs in the main
    conversation, and exactly one cold-read audit sub-agent runs after `review` settles.

    The sub-agent's per-iteration cold start plus its JSON -> card -> re-dispatch serialization was
    the loop's dominant latency, and its tool calls never streamed, so the operator could not see
    what was being fixed. Everything the prompt encoded (rubric, disciplines, injection, gate,
    deadlock check, guard rails) survives in `review-fix-round.md`; only the dispatch is gone. The
    convergence machinery that chose WHEN to cold-read goes with it: the read is now unconditional
    within a phase — once per phase at a given HEAD (4.13.0), never gated on a provenance count.
    """

    def setUp(self):
        self.spine = (PLAYBOOKS_DIR / SPINE).read_text(encoding="utf-8")
        self.flat = " ".join(self.spine.split())
        self.reference = REFERENCES_DIR / "review-fix-round.md"

    def test_the_fix_round_reference_exists_and_is_not_a_sub_agent_prompt(self):
        self.assertTrue(self.reference.is_file(), "review-fix-round.md must exist")
        for pattern in ("*-prompt*.md", "*-sub-agent*.md"):
            self.assertNotIn(
                self.reference,
                set(REFERENCES_DIR.glob(pattern)),
                "the main-loop fix round must not match the sub-agent-prompt discovery glob",
            )

    def test_the_spine_reads_the_fix_round_reference_and_dispatches_only_the_cold_read(self):
        self.assertIn("review-fix-round.md", self.flat)
        self.assertIn("cold-read-audit-prompt.md", self.flat)
        self.assertIn("Run one **fix round** on it per the reference, in this conversation", self.flat)
        self.assertIn("Cold-read audit — once per phase, after settle", self.flat)

    def test_the_iter_cap_card_lost_its_cold_read_option(self):
        self.assertIn('header: "Iter cap"', self.flat)
        for option in ("**Continue**", "**Accept current**", "**Abort**"):
            self.assertIn(option, self.flat)
        self.assertNotIn("**Cold-read audit** /", self.flat)

    def test_the_fix_round_carries_the_rubric_and_the_guard_rail_cards(self):
        text = self.reference.read_text(encoding="utf-8")
        for bucket in (
            "Addressable",
            "Cheap-fix-override",
            "Explicitly-deferred",
            "Decision-required",
            "Grounding-violation",
            "Plan-settled",
            "Deferred-by-plan",
        ):
            self.assertIn(bucket, text, "the classification rubric must survive the move")
        for header in ('"Review loop"', '"Decision"', '"Tests red"', '"Grounding"'):
            self.assertIn(header, text, "guard rail %s must survive as a direct card" % header)
        self.assertIn("AskUserQuestion", text)
        self.assertNotIn("needs_decision", text)

    def test_settle_covers_a_verdict_that_never_approves(self):
        """A reviewer that requests changes but names only deferrable items addresses nothing.

        Keying the exit on the approval line alone spins the loop on an unchanged PR until the cap;
        the retired sub-agent's exit keyed on "no items", which handled it.
        """
        self.assertIn("The round addressed nothing", self.flat)
        self.assertIn("a non-approving verdict whose every item classified as Explicitly-deferred", self.flat)

    def test_the_cold_read_is_dispatched_at_most_once(self):
        self.assertIn("the cold read has **not** run this run", self.flat)
        self.assertIn("Settled and it **has** → S5.1 is done; go to S6", self.flat)
        self.assertIn("never dispatched twice in one run", self.flat)

    def test_terminating_guard_rail_answers_leave_the_loop(self):
        for text in (self.flat, " ".join(self.reference.read_text(encoding="utf-8").split())):
            self.assertIn("Re-plan", text)
            self.assertIn("Restructure", text)
        self.assertIn("leaves S5.1 immediately", self.flat)
        self.assertIn(
            "ends the round *and* S5.1 on the spot",
            " ".join(self.reference.read_text(encoding="utf-8").split()),
        )

    def test_settled_buckets_do_not_count_as_addressed(self):
        # A verdict whose every item is Plan-settled / Deferred-by-plan addresses nothing, so the
        # loop settles instead of spinning an unchanged PR.
        self.assertIn(
            "a non-approving verdict whose every item classified as Explicitly-deferred (filed), "
            "Plan-settled, or Deferred-by-plan",
            self.flat,
        )
        text = " ".join(self.reference.read_text(encoding="utf-8").split())
        self.assertIn("refuted-items list", text)
        self.assertIn("Settled (not addressed):", text)
        # The citation requirement is what stops the bucket dismissing genuine findings.
        self.assertIn("No citation → the item is not plan-settled", text)
        # A refuted repeat re-settles silently; the deadlock card is for ADDRESSED repeats only.
        self.assertIn("re-settled silently on its second occurrence: no card, no second reply", text)
        # Deferred-by-plan files nothing (Explicitly-deferred is the bucket that files).
        self.assertIn("file nothing", text)

    def test_the_fix_round_plans_its_edits_as_a_set_before_the_first_one(self):
        """4.16.0: step 4 lists every intended change and checks the set before editing.

        A real run had three of eleven findings introduced by the loop's own fixes: step 4 was a
        single imperative, so a literal reader started editing item one with no view of how the
        fixes interact or whether one reverses a locked plan decision.
        """
        raw = self.reference.read_text(encoding="utf-8")
        reference = " ".join(raw.split())
        pitfalls = " ".join(
            (REFERENCES_DIR / "common-pitfalls.md").read_text(encoding="utf-8").split()
        )
        self.assertIn(
            "Before the first edit, list every Addressable and Cheap-fix-override item's intended change",
            reference,
        )
        self.assertIn("check the list as a set, and only then edit", reference)
        # A fix that undoes a locked decision re-enters step 2's card; it is never edited in.
        self.assertIn("reclassify it Decision-required and render step 2's `Decision` card", reference)
        # The three descriptions of the round name the beat the same way.
        for text, where in ((self.flat, "spine"), (reference, "reference"), (pitfalls, "pitfalls")):
            self.assertIn("fix plan", text, "%s must name the fix plan beat" % where)
        # The beat is prose, so the turn-boundary rule must not read as forbidding it.
        self.assertNotIn("operational tool calls", self.flat)
        self.assertIn("the classification, the fix plan, the edits, the gate", self.flat)
        # Steps 5-9 are cross-referenced by number from the spine and the pitfalls: no renumbering.
        steps = re.findall(r"^\d+\. \*\*", raw, flags=re.MULTILINE)
        self.assertEqual(len(steps), 9, "review-fix-round.md must keep exactly steps 1-9")


class PhaseScopedReviewTests(unittest.TestCase):
    """4.13.0: a non-final phase reviews its own delta at `medium`; the final phase reviews the
    cumulative diff at `high`; the outer cap has numbers; the cold read is once per PHASE, recorded on
    the PR so a re-entered session does not re-run it (#448: one session re-entered three times ran
    three cold reads under the once-per-run rule).
    """

    def setUp(self):
        self.spine = (PLAYBOOKS_DIR / SPINE).read_text(encoding="utf-8")
        self.flat = " ".join(self.spine.split())
        self.cold_read = " ".join(
            (REFERENCES_DIR / "cold-read-audit-prompt.md").read_text(encoding="utf-8").split()
        )

    def test_the_scope_rule_keeps_the_cumulative_diff_on_the_final_phase(self):
        self.assertIn("Final → `review`'s target is the PR's **cumulative diff**", self.flat)
        self.assertIn("Non-final → the **phase delta**", self.flat)
        self.assertIn("`facts.tracker.last_shipped", self.flat)
        # The fallback when nothing shipped or the SHA was force-pushed away.
        self.assertIn("else `facts.workspace.base_ref`", self.flat)

    def test_the_effort_level_is_passed_per_scope(self):
        self.assertIn("level `medium` on a non-final phase, `high` on the final one", self.flat)
        self.assertIn('Skill(skill="review", args=', self.flat)

    def test_the_cap_has_numbers(self):
        self.assertIn(
            "`review` runs at most **2** times on a non-final phase and **4** times on the final phase "
            "before the cold read; step 4 owns what follows it",
            self.flat,
        )
        self.assertIn('header: "Iter cap"', self.flat)
        # The confirming review after the cold read classifies but never pushes: a push there would
        # demand a review the cap forbids, with no card to land on.
        self.assertIn("That round classifies but does not fix", self.flat)

    def test_review_fixes_from_pr_55(self):
        # Finding 1: a trailing operator/decision-only phase must not steal "final" from the last
        # code-shipping phase, or the PR ships with no cumulative pass at all.
        self.assertIn("last unshipped `kind: code-shipping` entry of `facts.phases`", self.flat)
        # Finding 4: the base can be a branch name (base_ref fallback), so the range is three-dot.
        self.assertIn('args="<level> [<base>...HEAD] <context>"', self.flat)
        self.assertNotIn("<base>..HEAD", self.flat)
        self.assertIn("the fix round's settled buckets are the floor", self.flat)
        # Finding 6: last_shipped is computed before S4 can un-tick a row.
        self.assertIn("after an S4 **Rebuild un-ticked**, treat `last_shipped` as unreachable", self.flat)
        # Finding 3: the skip compares the recorded sha to HEAD; an ancestor re-bases the read.
        self.assertIn("whose `<sha>` **is** HEAD", self.flat)
        self.assertIn("run the cold read with `<base>` = that sha", self.flat)
        # Finding 9: the single-phase record has a defined phase number.
        self.assertIn("`1` for a single-phase issue", self.flat)
        # Finding 7: the plan-section token sits on one line.
        self.assertIn("`## Deviations from project docs`", self.spine)
        # Below-cap: context assembled once.
        self.assertIn("Assemble `<context>` once at loop entry", self.flat)
        reference = " ".join((REFERENCES_DIR / "review-fix-round.md").read_text(encoding="utf-8").split())
        # Finding 2: a seeded deferral expires when its phase comes due.
        self.assertIn("**except** a `deferred-by-plan` entry whose phase is the current phase", reference)
        # Below-cap: a refuted repeat has a bounded escape.
        self.assertIn("On its **third** occurrence in one run render the `Review loop` card", reference)
        pitfalls = " ".join((REFERENCES_DIR / "common-pitfalls.md").read_text(encoding="utf-8").split())
        # Finding 5: the turn-boundary pitfall cites step 4 instead of restating a stale mechanism.
        self.assertNotIn("staging the cumulative diff", pitfalls)
        self.assertIn("staging the scope diff and dispatching the cold read per S5.1 step 4", pitfalls)

    def test_verification_does_not_scale_with_scope(self):
        self.assertIn(
            "the §8 / §10.6 gates and defect injection run at full strength on every phase", self.flat
        )

    def test_the_cold_read_is_once_per_phase_and_recorded_on_the_pr(self):
        self.assertIn("Cold read: phase <N> @ <sha>", self.flat)
        self.assertIn("skip it, S5.1 is done", self.flat)
        self.assertIn("<<phase_context>>", self.flat)
        self.assertIn("<<phase_context>>", self.cold_read)
        self.assertIn("deferred to phase <N>", self.cold_read)

    def test_the_prep_fact_exists(self):
        # The fact the spine names must be a real fact.
        self.assertTrue(callable(prep_resolver.last_shipped_phase))
        self.assertIsNone(prep_resolver._absent_tracker()["last_shipped"])

    def test_the_retired_sub_agent_and_its_convergence_machinery_are_gone(self):
        for path in sorted(SKILL_DIR.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            for token in (
                "review-loop-sub-agent",
                "finding_provenance",
                "max_severity",
                "prior_decisions",
                "prior_audit_findings",
                "review-verdict.md",
            ):
                self.assertNotIn(
                    token,
                    text,
                    "%s still names the retired fix sub-agent contract %r" % (path.name, token),
                )

class ChangesLinkHandoffTests(unittest.TestCase):
    """The resolver pushes once per phase (plus one commit per review-loop iteration), so its handoff
    is the operator's entry point for reviewing what the run shipped. The `Changes:` line carries that
    link. It is defined in _shared/handoff-format.md (schema fence + omission rule) and only RENDERED
    here, per CLAUDE.md's render-don't-restate rule. Two URL forms, both verified live against a real
    PR: `<pr-url>/files/<a>..<b>` resolves only when the left SHA is a commit IN the PR (continue
    mode); the PR's base commit 404s, so a fresh run — where the whole PR is the run's changes — links
    the plain `<pr-url>/files`. These tests pin the definition, the per-shape presence/absence, and the
    two link forms."""

    RENDERINGS = REFERENCES_DIR / "handoff-renderings.md"
    HANDOFF_FORMAT = REPO_ROOT / "skills" / "_shared" / "handoff-format.md"
    SPINE = PLAYBOOKS_DIR / "resolve-spine.md"

    # Section heading -> does that shape's run push commits?
    SHAPES_WITH_PUSH = (
        "## Forward — standard or story PR opened / updated",
        "## Re-route — multi-phase, non-final code phase pushed",
        "## Terminal-with-action — multi-phase, next phase is operator / decision-only",
        "## Forward — multi-phase, last planned phase shipped",
        "## In progress — Epic integration draft PR open (stories remain)",
        "## Forward — Epic integration PR",
        "## Re-route → planner",
    )
    SHAPES_WITHOUT_PUSH = (
        "## Re-route → drafter (fitness audit)",
        "## Re-route → drafter (doc conflict)",
        "## Terminal — non-PR resolution",
        "## Terminal — question-type issue",
    )

    def _sections(self):
        """Split the reference into its `## ` shapes. Headings INSIDE a fence don't count — every
        worked shape opens with a fenced `## Handoff` line of its own."""
        lines = self.RENDERINGS.read_text(encoding="utf-8").splitlines()
        out, head, buf, in_fence = {}, None, [], False
        for line in lines:
            if line.startswith("```"):
                in_fence = not in_fence
            elif not in_fence and line.startswith("## "):
                if head is not None:
                    out[head] = "\n".join(buf)
                head, buf = line.strip(), []
                continue
            buf.append(line)
        if head is not None:
            out[head] = "\n".join(buf)
        return out

    def test_shared_owns_the_definition(self):
        text = self.HANDOFF_FORMAT.read_text(encoding="utf-8")
        self.assertIn(
            "**Changes:**", text,
            "_shared/handoff-format.md's schema fence must carry the Changes: line",
        )
        self.assertIn(
            "- **`Changes:`**", text,
            "_shared/handoff-format.md must carry the Changes: omission rule",
        )
        rule = text.split("- **`Changes:`**", 1)[1].split("\n", 1)[0]
        self.assertIn(
            "resolver-only", rule,
            "the Changes: rule must scope the line to the resolver, as Cleanup: is to the evaluator",
        )
        self.assertIn(
            "not a state marker", rule,
            "the Changes: payload is free-form text — it must be excluded from the closed sets",
        )
        # Free-form payload => no closed-set table row (the table rows are `| Field | Values |`).
        self.assertNotIn(
            "| Issue `changes`", text,
            "Changes: must not gain a closed-set vocabulary row",
        )

    def test_every_pushing_shape_carries_the_line(self):
        sections = self._sections()
        for head in self.SHAPES_WITH_PUSH:
            self.assertIn(head, sections, "handoff-renderings.md must carry the %r shape" % head)
            self.assertIn(
                "**Changes:**", sections[head],
                "%r pushed commits — its shape must render the Changes: review link" % head,
            )

    def test_no_push_shapes_omit_the_line(self):
        sections = self._sections()
        for head in self.SHAPES_WITHOUT_PUSH:
            self.assertIn(head, sections, "handoff-renderings.md must carry the %r shape" % head)
            self.assertNotIn(
                "**Changes:**", sections[head],
                "%r opened no PR and pushed nothing — a Changes: link would be a dangling URL" % head,
            )

    def test_rendered_links_use_a_verified_url_form(self):
        text = self.RENDERINGS.read_text(encoding="utf-8")
        rendered = [ln for ln in text.splitlines() if ln.startswith("**Changes:**")]
        self.assertTrue(rendered, "no Changes: line is actually rendered in a worked shape")
        range_form = re.compile(r"/pull/\d+/files/[0-9a-f]{7}\.\.[0-9a-f]{7}$")
        whole_form = re.compile(r"/pull/\d+/files$")
        for line in rendered:
            url = line.rsplit(" ", 1)[-1]
            self.assertTrue(
                range_form.search(url) or whole_form.search(url),
                "%r is neither verified form: <pr-url>/files/<a>..<b> (continue mode) nor "
                "<pr-url>/files (fresh run / post-rebase). A compare/ link or a bare PR url "
                "does not land the reader on the PR's reviewable diff." % url,
            )
            if range_form.search(url):
                lo, hi = url.rsplit("/", 1)[-1].split("..")
                self.assertIn(
                    "%s..%s" % (lo, hi), line,
                    "the rendered SHA range and the link's range must agree",
                )

    def test_spine_names_the_range_source(self):
        text = self.SPINE.read_text(encoding="utf-8")
        self.assertIn(
            "facts.workspace.sha", text,
            "the spine must name the session-entry SHA as the range's left side",
        )
        self.assertIn(
            "after** the review loop settles", text,
            "the spine must place the HEAD read after the loop settles — its fix rounds push commits, "
            "so an earlier read names a range that stops short of what the run shipped. (4.11.0 "
            "retired the review-loop sub-agent, so there is no final_pushed_sha to warn off any more.)",
        )



if __name__ == "__main__":
    unittest.main()
