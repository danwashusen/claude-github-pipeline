"""Offline tests for the planner skill (docs/implementation.md S13).

The offline surfaces the S13 DoD / Testing section names:

1. **Routing-table fixtures** (`vector` → `playbooks/<file>`). The router's visible routing table
   (`skills/planner/SKILL.md` §2) maps a prep-derived `vector` to the one playbook a session reads.
   These parse that table, assert it covers exactly the four routable playbooks
   (single / epic / story-jit / revise), that each points at a real `playbooks/<file>`, and that the
   type→playbook mapping is byte-consistent with `prep_planner._suggested_playbook` (architecture.md §5
   "prep proposes; the router confirms").

2. **The interleaving pattern-grep, committed as a validator** (S13 DoD box: playbooks are
   type-conditional-free by construction). Greps the four routable playbooks and the shared spine for
   cross-route conditionals and fails on a hit (both `if … <route> … else …` and "when the issue is a
   <route>" prose branches). Patterns broadened per the S10 carried advisory to the planner's route set.

3. **`--dry-run` persist envelopes.** Every GitHub write the playbooks specify goes through
   `gh_persist.py` (SKILL.md §3; the planner has no scriptless raw-gh executor). These run each such
   invocation with `--dry-run` against the offline shim and assert a conformant envelope.

4. **Rendering fixtures** — the plan-comment schema byte-compat against the S1 capture; the footer rule
   (origin/main vs bare-branch + short-SHA); the `**Open questions:**` line in every handoff shape that
   has OQs; the bug-(b) composite epic+story worked example; the bug-(a) falsifiable "(not filed)" rule.

Plus the structural bar (router ≤150, router+largest playbook ≤251 = half of v1's 503) and the operator
gate/pins coverage.

No network: gh_persist.py's `gh` calls resolve to the offline shim via tests/run.py's PATH wiring; the
dry-run path performs no gh call at all (asserted).
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
SKILL_DIR = REPO_ROOT / "skills" / "planner"
ROUTER = SKILL_DIR / "SKILL.md"
PLAYBOOKS_DIR = SKILL_DIR / "playbooks"
REFERENCES_DIR = SKILL_DIR / "references"
GH_PERSIST = SCRIPTS_DIR / "gh_persist.py"
S1_PLAN_CAPTURE = REPO_ROOT / "docs" / "specs" / "examples" / "implementation-plan.md"

# The four routable playbooks (the spine is a shared file, not a routable route).
ROUTABLE_PLAYBOOKS = {"single.md", "epic.md", "story-jit.md", "revise.md"}
SPINE = "plan-spine.md"

# Half of the v1 planner SKILL.md (503 lines, docs/specs/baseline.md §1) = 251 (floor).
V1_HALF_BAR = 503 // 2

sys.path.insert(0, str(SCRIPTS_DIR))

import prep_planner  # noqa: E402  (import after sys.path setup, by necessity)
from tests.support import envelope_asserts, shimenv  # noqa: E402
from tests.support.retired_tokens import FORBIDDEN_CONTRACT_TOKENS  # noqa: E402


# ---------------------------------------------------------------------------
# Router routing-table parse
# ---------------------------------------------------------------------------

_ROUTE_ROW_RE = re.compile(
    r"^\|\s*(?P<vector>[^|]+?)\s*\|\s*`(?P<playbook>playbooks/[a-z0-9-]+\.md)`\s*\|"
)


def _parse_router_routing_table(router_text):
    rows = []
    for line in router_text.splitlines():
        match = _ROUTE_ROW_RE.match(line)
        if match:
            rows.append((match.group("vector").strip(), match.group("playbook")))
    return rows


def _fence_stripped_lines(path):
    in_fence = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            yield i, line, in_fence
            continue
        yield i, line, in_fence


def _iter_md(dir_path):
    yield from sorted(dir_path.rglob("*.md"))


def _first_fenced_block(text):
    out, in_fence = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if in_fence:
                out.append(line)
                break
            in_fence = True
        if in_fence:
            out.append(line)
    return "\n".join(out)


class RouterRoutingTableTests(unittest.TestCase):
    def setUp(self):
        self.router_text = ROUTER.read_text(encoding="utf-8")
        self.rows = _parse_router_routing_table(self.router_text)
        self.playbooks = [pb for _, pb in self.rows]

    def test_router_exists_and_has_no_model_effort_pins(self):
        # Model/effort are not pinned — skills inherit the invoking session's model and effort.
        self.assertTrue(ROUTER.is_file(), "router SKILL.md must exist")
        head = "\n".join(self.router_text.splitlines()[:8])
        self.assertIn("name: planner", head)
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

    def test_table_matches_prep_suggested_playbook(self):
        # architecture.md §5: prep proposes `suggested_playbook`; the router confirms against the table.
        # (type, mode, parent_epic_open) -> playbook.
        cases = [
            ("standard", "fresh", False, "single.md"),
            ("story", "fresh", False, "single.md"),   # standalone story = single-issue path
            ("story", "fresh", True, "story-jit.md"),
            ("story", "revise", True, "story-jit.md"),  # story-jit owns fresh AND revise
            ("epic", "fresh", False, "epic.md"),
            ("standard", "revise", False, "revise.md"),
            ("epic", "revise", False, "revise.md"),
        ]
        table_basenames = {Path(pb).name for pb in self.playbooks}
        for issue_type, mode, parent_open, expected in cases:
            self.assertEqual(
                prep_planner._suggested_playbook(issue_type, mode, parent_open),
                expected,
                "prep _suggested_playbook(%r, %r, %r) should be %r"
                % (issue_type, mode, parent_open, expected),
            )
            self.assertIn(
                expected, table_basenames, "the router table must route to %s" % expected
            )

    def test_all_four_playbooks_read_the_shared_spine(self):
        # For the planner, author-and-verify-a-plan is shared across every route; each routed playbook
        # reads the one shared spine (architecture.md §5).
        self.assertTrue((PLAYBOOKS_DIR / SPINE).is_file())
        for name in ROUTABLE_PLAYBOOKS:
            text = (PLAYBOOKS_DIR / name).read_text(encoding="utf-8")
            self.assertIn(SPINE, text, "%s must read the shared spine %s" % (name, SPINE))


# ---------------------------------------------------------------------------
# Router structural bar
# ---------------------------------------------------------------------------


class RouterStructuralBarTests(unittest.TestCase):
    def test_router_at_most_150_lines(self):
        n = len(ROUTER.read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(n, 150, "router SKILL.md is %d lines (bar: <= 150)" % n)

    def test_router_plus_largest_playbook_at_most_half_v1(self):
        router_lines = len(ROUTER.read_text(encoding="utf-8").splitlines())
        playbook_lines = {
            p.name: len(p.read_text(encoding="utf-8").splitlines())
            for p in PLAYBOOKS_DIR.glob("*.md")
        }
        largest = max(playbook_lines.values())
        self.assertLessEqual(
            router_lines + largest,
            V1_HALF_BAR,
            "router (%d) + largest playbook (%d) = %d exceeds %d (half of v1's 503): %r"
            % (router_lines, largest, router_lines + largest, V1_HALF_BAR, playbook_lines),
        )


class SubIssueReconciliationRuleTests(unittest.TestCase):
    """#18: the phase→sub-issue contract, pinned where prose has no compiler.

    The cardinality rule is stated ONCE (the issue's "stated once wherever it lands"), the grammar is
    documented OUTSIDE plan-schema.md's frozen first fence, the gate offers exactly the three recorded
    operator options and never silently re-cuts, and the two hard limits (no writes to a sub-issue, a
    one-way plan→sub-issue pointer) are on the page.
    """

    RECONCILIATION = REFERENCES_DIR / "sub-issue-reconciliation.md"
    SCHEMA = REFERENCES_DIR / "plan-schema.md"
    REVIEWER = REFERENCES_DIR / "plan-reviewer-prompt.md"
    REVISE = REFERENCES_DIR / "revise-reconciliation.md"
    # Every route that can face a pre-sliced target: fresh standalone (`single.md`), a story under an
    # open epic in either mode (`story-jit.md`), and a standalone revise (`revise.md` — the route where
    # the diff is richest, since a prior plan exists). An epic's sub-issues are STORIES, so `epic.md`
    # stays out; an epic revise reaches `revise.md` but never carries `facts.slices`, so its
    # fact-keyed bullet correctly no-ops.
    SLICE_ROUTES = ("single.md", "story-jit.md", "revise.md")

    def test_reference_exists_and_is_read_by_both_non_epic_routes(self):
        self.assertTrue(self.RECONCILIATION.is_file())
        for name in self.SLICE_ROUTES:
            text = (PLAYBOOKS_DIR / name).read_text(encoding="utf-8")
            self.assertIn("sub-issue-reconciliation.md", text, name)

    def test_epic_playbook_does_not_read_it(self):
        # The mechanical encoding of "an epic's sub-issues are stories, not slices".
        text = (PLAYBOOKS_DIR / "epic.md").read_text(encoding="utf-8")
        self.assertNotIn("sub-issue-reconciliation.md", text)

    def test_playbooks_key_on_the_fact_not_the_type(self):
        # `facts.slices` presence is the trigger; a type branch here would trip the interleaving grep
        # and would also be the wrong contract (prd/architecture: parameterize before you playbook).
        for name in self.SLICE_ROUTES:
            text = (PLAYBOOKS_DIR / name).read_text(encoding="utf-8")
            self.assertIn("facts.slices", text, name)

    def test_cardinality_rule_is_stated_exactly_once(self):
        # Whitespace-normalized: these files hard-wrap, so a line-sensitive search would silently
        # miss a real third copy that happens to wrap differently (and would fail on a harmless
        # re-wrap of the reference itself).
        needle = "N:1 and total over the OPEN"
        hits = [
            p.name
            for p in _iter_md(SKILL_DIR)
            if needle in re.sub(r"\s+", " ", p.read_text(encoding="utf-8"))
        ]
        # plan-schema.md states the GRAMMAR and defers the rule. The reviewer prompt restates it for
        # its own isolated context — a context-blind sub-agent prompt cannot follow a link, so that
        # copy is a rendering, not a second authority.
        self.assertIn("plan-reviewer-prompt.md", hits, "expected the reviewer's own rendering: %r" % hits)
        self.assertEqual(
            [n for n in hits if n != "plan-reviewer-prompt.md"],
            ["sub-issue-reconciliation.md"],
            "the cardinality rule must be stated once, in the reconciliation reference: %r" % hits,
        )

    def test_substrate_case_is_named_explicitly(self):
        for path in (self.RECONCILIATION, self.SCHEMA):
            text = path.read_text(encoding="utf-8")
            self.assertIn("sub-issue: (none)", text, path.name)
            self.assertIn("substrate", text, path.name)

    def test_grammar_is_documented_outside_the_frozen_first_fence(self):
        # PlanSchemaByteCompatTests pins the first fence byte-identical to the S1 capture; documenting
        # the key inside it would force an edit to the frozen v1 record and hollow out that assertion.
        text = self.SCHEMA.read_text(encoding="utf-8")
        self.assertIn("sub-issue:", text)
        self.assertNotIn("sub-issue", _first_fenced_block(text))

    def test_gate_offers_the_three_options_and_never_silently_re_cuts(self):
        text = self.RECONCILIATION.read_text(encoding="utf-8")
        self.assertIn("never silently re-cuts", text)
        for option in (
            "Re-cut the phases to cover the change",
            "Record the sub-issue as out-of-scope, with a disposition",
            "Stop and route the sub-issue set back to whoever authors sub-issues",
        ):
            self.assertIn(option, text)

    def test_no_writes_and_one_way_pointer_are_stated(self):
        text = self.RECONCILIATION.read_text(encoding="utf-8")
        self.assertIn("writes nothing to a sub-issue", text)
        self.assertIn("one-way", text)
        self.assertIn("never cites a phase number", text)

    def test_rescope_is_described_as_a_suspicion_not_proof(self):
        text = self.RECONCILIATION.read_text(encoding="utf-8")
        self.assertIn("not proof", text)
        self.assertIn("over-reports", text)

    def test_reviewer_carries_live_slices_and_the_n_to_one_carve_out(self):
        text = self.REVIEWER.read_text(encoding="utf-8")
        self.assertIn("<<live_slices>>", text)
        self.assertIn("open sub-issue no phase names", text)
        # The single most important sentence in the amendment: without it a reviewer imports
        # `closes-dod`'s exactly-once rule by analogy and BLOCKERs every legal N:1 plan.
        self.assertIn("never a finding", text)
        self.assertIn('do not import the `closes-dod` "exactly once" rule here', text)

    def test_both_slice_routes_pass_live_slices_to_the_reviewer(self):
        for name in self.SLICE_ROUTES:
            text = (PLAYBOOKS_DIR / name).read_text(encoding="utf-8")
            self.assertIn("<<live_slices>>", text, name)

    def test_closed_sub_issue_defers_to_the_shipped_phase_rules(self):
        text = self.REVISE.read_text(encoding="utf-8")
        self.assertIn("behaves like a **shipped phase**", text)
        self.assertIn("no second, parallel rule set", text)

    def test_router_lists_the_slices_fact_and_the_new_gate(self):
        text = ROUTER.read_text(encoding="utf-8")
        self.assertIn("`slices`", text)
        self.assertIn("sub-issue reconciliation", text)

    def test_spine_is_unchanged_at_its_recorded_length(self):
        # The 251 bar is a knife edge (router 123 + spine 128). Fail at the CAUSE — a spine edit —
        # rather than only at the sum, whose message implicates whichever file was touched last.
        n = len((PLAYBOOKS_DIR / SPINE).read_text(encoding="utf-8").splitlines())
        self.assertEqual(n, 128, "plan-spine.md is %d lines; the 251 bar assumes 128" % n)


class ShapeTriageOffRampTests(unittest.TestCase):
    """The seam gate's shape triage offers TWO off-ramps, selected by the independence bar the seams
    clear (#17): shippable-independent → the epic split; demonstrable-independent → the slicer.

    The asymmetry between them is the load-bearing part: off-ramp A posts a seam-analysis comment the
    drafter splits *per*, while off-ramp B posts **nothing**, because the slicer re-derives its cut from
    the repo's grounding docs and a planner-authored proposal would compete with it. An editor who
    "harmonizes" the two by adding a comment to B creates exactly the stale second decomposition #18's
    one-way-pointer rule exists to prevent.
    """

    def setUp(self):
        raw = (REFERENCES_DIR / "seam-dispositions.md").read_text(encoding="utf-8")
        self.seams = re.sub(r"\s+", " ", raw.replace("**", ""))
        self.renderings = re.sub(
            r"\s+", " ", (REFERENCES_DIR / "handoff-renderings.md").read_text(encoding="utf-8")
        )

    def test_triage_selects_on_the_independence_bar(self):
        self.assertIn("Shape triage", self.seams)
        self.assertIn("demonstrable", self.seams)
        self.assertIn("shippable", self.seams)
        self.assertRegex(self.seams, r"Slice first")
        self.assertRegex(self.seams, r"Split as epic")

    def test_both_off_ramp_flows_exist_and_are_distinguished(self):
        self.assertIn("Off-ramp A", self.seams)
        self.assertIn("Off-ramp B", self.seams)

    def test_off_ramp_b_posts_nothing(self):
        self.assertRegex(self.seams, r"On \"Slice first\": post nothing at all")
        self.assertRegex(self.seams, r"asymmetry with off-ramp A is deliberate")

    def test_off_ramp_b_is_a_round_trip_back_through_reconciliation(self):
        self.assertRegex(self.seams, r"slicer hands back here")
        self.assertIn("sub-issue-reconciliation.md", self.seams)

    def test_rendering_exists_and_routes_to_the_slicer(self):
        self.assertIn("Too large to plan as one unit", self.renderings)
        self.assertIn("/github-pipeline:slicer", self.renderings)

    def test_single_offers_both_off_ramps_and_story_jit_only_the_slicer(self):
        single = (PLAYBOOKS_DIR / "single.md").read_text(encoding="utf-8")
        story_jit = (PLAYBOOKS_DIR / "story-jit.md").read_text(encoding="utf-8")
        self.assertIn("`off-ramp: epic + slicer offered`", single)
        self.assertIn("`off-ramp: slicer offered — epic not offered`", story_jit)
        # A story is never promoted to an epic — that stays an epic-contract re-route.
        self.assertRegex(
            re.sub(r"\s+", " ", story_jit), r"never promote a story to an epic"
        )


class PlaybookInterleavingGrepTests(unittest.TestCase):
    """A playbook is a linear narrative for exactly one route — zero cross-route conditionals. Fails on
    either an `if … <route> … else …` construct or a `when the issue/type is a <route>` prose branch, over
    the four routable playbooks and the shared spine. Patterns broadened (S10 carried advisory) to the
    planner's route set — the routing types are single/epic/story-jit/revise plus the facts type names
    standard/story; the scale-to-work sub-classes (bug/feature/multi-phase) are legitimately named within
    single.md and are NOT routes, so they are not interleaving."""

    _ROUTES = r"(single|epic|story-jit|revise|standard|story)"
    _IF_ELSE = re.compile(r"\bif\b[^.\n]{0,50}\b" + _ROUTES + r"\b[^.\n]{0,50}\belse\b", re.IGNORECASE)
    _WHEN_TYPE = re.compile(
        r"\bwhen (the (issue|type) is|it.?s)\s+(a |an )?" + _ROUTES + r"\b", re.IGNORECASE
    )

    def test_playbooks_have_no_cross_route_conditionals(self):
        for playbook in PLAYBOOKS_DIR.glob("*.md"):
            text = playbook.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                self.assertIsNone(
                    self._IF_ELSE.search(line),
                    "playbook %s:%d looks like a cross-route conditional: %r" % (playbook.name, i, line),
                )
                self.assertIsNone(
                    self._WHEN_TYPE.search(line),
                    "playbook %s:%d looks like a when-<route> prose branch: %r" % (playbook.name, i, line),
                )


class ContractTokenGateTests(unittest.TestCase):
    """Grep gates over skills/planner/ — zero retired-executor tokens, zero v1 skill-invocation namespace strings,
    zero GATHER_/PERSIST_ op names, zero §P IDs, zero raw persist/gather WRITES in fences, zero
    ref-arithmetic in fences, zero w/ shorthand. The `planned` label and the HARD-revise PR-close (both
    write-path gaps at S13's first pass) are now real `gh_persist.py edit-labels`/`close-pr` ops
    (authorized in-step), so no raw-`gh` prose workaround remains anywhere in skills/planner/."""

    def test_no_github_ops_or_old_names_or_op_names_or_pids(self):
        forbidden = FORBIDDEN_CONTRACT_TOKENS
        for path in _iter_md(SKILL_DIR):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                hit = forbidden.search(line)
                self.assertIsNone(
                    hit,
                    "forbidden contract token under skills/planner/ at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )

    def test_no_raw_persist_or_gather_writes_in_code_fences(self):
        # A persist/gather WRITE bypassing gh_persist.py. `gh_persist.py edit-body`/`edit-labels`/
        # `close-pr` are NOT matches (they are `gh_persist.py`, not `gh issue|pr`). The reviewer
        # prompt's `gh issue view` self-fetch is a READ, not a write, and doesn't match. Every write
        # skills/planner/ specifies now routes through gh_persist.py — zero raw `gh` writes anywhere,
        # fenced or not.
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


class PlaybookPersistDryRunTests(unittest.TestCase):
    """Each GitHub write the planner playbooks specify (spine S8 plan-comment post + issue-body pointer;
    revise-reconciliation.md DoD body reconciliation), run with --dry-run: a conformant envelope, status
    ok, `would_run` present, exit 0, no live gh call."""

    def _assert_dry_run_ok(self, proc, envelope, expected_op):
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        self.assertIsNotNone(envelope, "expected exactly one envelope on stdout")
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope.get("status"), "ok")
        self.assertEqual(envelope.get("op"), expected_op)
        self.assertTrue(envelope.get("dry_run"))
        self.assertIn("would_run", envelope)

    def test_plan_comment_post_fresh_dry_run(self):
        # spine S8 fresh post: gh_persist.py comment <repo> issue <N> <plan.md>
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "142", "@BODY@", "--dry-run"],
            body_text="<!-- implementation-plan:v1 -->\n**Implementation plan** — #142 x — planned "
            "2026-07-11T00:00:00Z at `origin/main@a1b2c3d`\n\n## Approach\nDo the thing.\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_plan_comment_repost_revise_with_delete_marker_dry_run(self):
        # spine S8 revise: --delete-marker-id deletes the stale plan comment (post-new-before-delete-old).
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "142", "@BODY@", "--delete-marker-id", "998877", "--dry-run"],
            body_text="<!-- implementation-plan:v1 -->\n**Implementation plan** — #142 x — planned "
            "2026-07-11T00:00:00Z at `origin/main@b2c3d4e`\n\n## Approach\nRevised.\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_issue_body_pointer_edit_body_dry_run(self):
        # spine S8 pointer upsert: gh_persist.py edit-body <repo> <issue> <issue-body-pointer.md>
        proc, env = _run_persist(
            ["edit-body", "octo/widgets", "142", "@BODY@", "--dry-run"],
            body_text="## Summary\nx\n\n> 📋 **Implementation plan:** see [the implementation-plan "
            "comment](https://github.com/octo/widgets/issues/142#issuecomment-1) — authored by "
            "`github-issue-planner`; re-run that skill to revise.\n",
        )
        self._assert_dry_run_ok(proc, env, "edit-body")

    def test_revise_dod_reconciliation_edit_body_dry_run(self):
        # revise-reconciliation.md SOFT/HARD path: gh_persist.py edit-body on the reconciled body.
        proc, env = _run_persist(
            ["edit-body", "octo/widgets", "142", "@BODY@", "--dry-run"],
            body_text="## Definition of done\n- [ ] Document the export format (previously claimed by "
            "phase 1, commit abc1234 on closed PR #287)\n",
        )
        self._assert_dry_run_ok(proc, env, "edit-body")

    def test_planned_label_apply_edit_labels_dry_run(self):
        # spine S8: gh_persist.py edit-labels <repo> <issue> --add planned (bodyless, no @BODY@).
        proc, env = _run_persist(
            ["edit-labels", "octo/widgets", "142", "--add", "planned", "--dry-run"]
        )
        self._assert_dry_run_ok(proc, env, "edit-labels")
        self.assertEqual(env.get("added"), ["planned"])

    def test_hard_revise_close_pr_with_supersession_marker_dry_run(self):
        # revise.md / revise-reconciliation.md HARD "Start fresh": gh_persist.py close-pr with the
        # byte-faithful `Re-plan superseded this PR` marker the resolver's predecessor-PR detection
        # greps for (docs/specs/resolver.md "Deterministic steps").
        proc, env = _run_persist(
            ["close-pr", "octo/widgets", "287", "--comment-file", "@BODY@", "--dry-run"],
            body_text="Re-plan superseded this PR. See updated plan at "
            "https://github.com/octo/widgets/issues/142#issuecomment-999. A new branch and PR will "
            "open at the next `/github-pipeline:resolver #142` run.\n",
        )
        self._assert_dry_run_ok(proc, env, "close-pr")
        self.assertIn("Re-plan superseded this PR", env.get("would_run", ""))

    def test_dry_run_makes_no_live_gh_call(self):
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "142", "@BODY@", "--dry-run"],
            body_text="<!-- implementation-plan:v1 -->\nx\n",
        )
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        self.assertTrue(env.get("dry_run"))
        self.assertNotIn("url", env, "a dry-run must not carry a live-write url")


# ---------------------------------------------------------------------------
# Rendering fixtures — plan schema byte-compat, footer rule, OQ line, bug (a)/(b)
# ---------------------------------------------------------------------------


class PlanSchemaByteCompatTests(unittest.TestCase):
    """S13 DoD box 1 (offline half): the carried plan-schema rendering must diff clean against the S1
    capture (prd.md §7 row 1, frozen artifact). The main schema fenced block is byte-identical."""

    def test_plan_schema_reference_exists(self):
        self.assertTrue((REFERENCES_DIR / "plan-schema.md").is_file())

    def test_main_schema_block_byte_identical_to_s1_capture(self):
        ours = _first_fenced_block((REFERENCES_DIR / "plan-schema.md").read_text(encoding="utf-8"))
        s1 = _first_fenced_block(S1_PLAN_CAPTURE.read_text(encoding="utf-8"))
        self.assertEqual(ours, s1, "carried plan-schema block drifted from the S1 capture")

    def test_frozen_provenance_footer_preserved(self):
        # S7 adjudication (a): the artifact-footer provenance keeps the literal v1 skill name verbatim
        # (a byte-compat contract token, NOT renamed to the v2 `planner`).
        text = (REFERENCES_DIR / "plan-schema.md").read_text(encoding="utf-8")
        self.assertIn("_Authored by `github-issue-planner` and verified in", text)

    def test_marker_is_first_line_of_the_schema_block(self):
        block = _first_fenced_block((REFERENCES_DIR / "plan-schema.md").read_text(encoding="utf-8"))
        body_lines = block.splitlines()[1:]  # drop the opening ```
        self.assertEqual(body_lines[0], "<!-- implementation-plan:v1 -->")


class FooterRuleTests(unittest.TestCase):
    """S13: the footer rendering rule (origin/main-prefixed default branch, bare epic/PR branch
    otherwise, @ the grounding workspace short-SHA) is stated as rendering logic."""

    def setUp(self):
        self.renderings = (REFERENCES_DIR / "handoff-renderings.md").read_text(encoding="utf-8")
        self.spine = (PLAYBOOKS_DIR / SPINE).read_text(encoding="utf-8")

    def test_footer_rule_states_origin_main_vs_bare_branch(self):
        self.assertIn("origin/main", self.renderings)
        self.assertIn("epic/<N>-<slug>", self.renderings)
        self.assertRegex(
            self.renderings,
            r"[Nn]ever\s+emit\s+a\s+bare\s+`?main@",
            "the footer rule must forbid a bare main@<sha> form",
        )

    def test_short_sha_bound_to_grounding_workspace(self):
        # v3: the footer SHA binds to the ambient grounding fact (the asserted checkout's HEAD),
        # not the retired read_workspaces.grounding ro-* view.
        self.assertIn("facts.grounding.sha", self.renderings + self.spine)
        self.assertNotIn("facts.read_workspaces.grounding", self.renderings + self.spine)

    def test_spine_states_the_footer_rendering_rule(self):
        self.assertIn("origin/main", self.spine)
        self.assertIn("never a bare `main@<sha>`", self.spine)


class OpenQuestionLineCoverageTests(unittest.TestCase):
    """S13 DoD box 3 (offline half): the `**Open questions:**` line renders in every handoff shape that
    has OQs, and the bug-(b) composite epic+story worked example is present with the line."""

    def setUp(self):
        self.renderings = (REFERENCES_DIR / "handoff-renderings.md").read_text(encoding="utf-8")

    def test_open_questions_line_present_as_always_checked_condition(self):
        self.assertIn("**Open questions:**", self.renderings)
        # The rule must be expressed as an always-checked condition, not example-dependent.
        self.assertRegex(
            self.renderings,
            r"whenever any plan body posted this session carries an `## Open questions`",
            "the OQ-line rule must be stated as an always-checked condition (bug (b) residual)",
        )

    def test_planner_treatment_vocabulary_only(self):
        # The planner uses its plan-level treatment set, never the drafter's build-issue set.
        for token in ("planned-around", "recorded-blocked", "provisional-default"):
            self.assertIn(token, self.renderings, "planner OQ vocabulary %r missing" % token)

    def test_bug_b_composite_epic_plus_story_example_present_with_oq_line(self):
        # The composite epic+story hybrid shape (the 2026-07-01 drop) must have a worked example whose
        # emitted handoff carries the **Open questions:** line.
        self.assertRegex(
            self.renderings,
            r"[Cc]omposite.*epic.*story|epic.*plus.*story|[Ee]pic-plus-story",
            "the bug-(b) composite epic+story worked example must be present",
        )
        # Locate the composite worked-example section (its bold heading, not the intro mention) and
        # assert its emitted ## Handoff carries a (not filed) provisional-default OQ line.
        idx = self.renderings.find("**Epic-plus-story composite")
        self.assertNotEqual(idx, -1, "the composite worked example must have its own heading")
        window = self.renderings[idx: idx + 2500]
        self.assertIn("**Open questions:** (not filed) (audience:developer) provisional-default", window,
                      "the composite example's handoff must carry the (not filed) OQ line (bug (b))")

    def test_every_handoff_block_that_gates_oqs_shows_the_line(self):
        # Structural: every fenced ## Handoff block that mentions an OQ disposition token must also carry
        # a **Open questions:** line (no shape silently drops it).
        blocks = re.findall(r"```\n(## Handoff.*?)```", self.renderings, re.DOTALL)
        self.assertTrue(blocks, "no ## Handoff blocks parsed from renderings")
        treatments = ("planned-around", "recorded-blocked", "provisional-default")
        gated = [b for b in blocks if any(t in b for t in treatments)]
        self.assertTrue(gated, "expected at least one handoff block exercising an OQ treatment")
        for b in gated:
            self.assertIn(
                "**Open questions:**", b,
                "a handoff block names an OQ treatment but drops the **Open questions:** line:\n%s" % b,
            )


class BugARuleTests(unittest.TestCase):
    """S13 DoD box 4 (offline half): the falsifiable "(not filed)" rule is written as an instruction and
    pinned by a grep."""

    def setUp(self):
        self.spine = (PLAYBOOKS_DIR / SPINE).read_text(encoding="utf-8")

    def test_not_filed_rule_is_falsifiable_and_names_both_search_paths(self):
        self.assertIn("Falsifiable", self.spine)
        # Only-when: candidate set empty OR each candidate explicitly rejected.
        self.assertRegex(
            self.spine,
            r"`?question: \(not filed\)`?.*only.*when",
            "the (not filed) rule must be gated (only when …)",
        )
        # Body-recorded OQ → prep's open_question_candidates.
        self.assertIn("facts.open_question_candidates", self.spine)
        # Newly-detected OQ → the --oq-query one-shot lookup (mechanism ii).
        self.assertIn("--oq-query", self.spine)

    def test_prep_oq_query_flag_exists(self):
        # The authorized additive prep extension backing the newly-detected-OQ search.
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "prep_planner.py"), "--help"],
            capture_output=True, encoding="utf-8", check=False,
        )
        self.assertIn("--oq-query", proc.stdout + proc.stderr)


class CitationCompletenessRuleTests(unittest.TestCase):
    """Scenario-3 D8 operator adjudication (docs/specs/parity/planner.md): v2 must never silently
    resolve a genuine design decision on a partial citation. Falsifiable rule, same register as
    bug (a): a citation pins a choice only when it covers the WHOLE choice; genuinely-silent or
    partial-only grounding routes to the S4 Decision gate or an explicit provisional pin naming the
    rejected alternative(s) — binding to the EXISTING `## Architecture decisions` citation/"name the
    rejected one" grammar (plan-schema.md), never a new schema section."""

    def setUp(self):
        self.spine = (PLAYBOOKS_DIR / SPINE).read_text(encoding="utf-8")

    def test_rule_is_falsifiable_and_fence_scoped(self):
        self.assertRegex(self.spine, r"Falsifiable\s+citation-completeness rule")
        # Prose, not a code sample: the rule text must sit outside every ``` fence.
        for i, line, in_fence in _fence_stripped_lines(PLAYBOOKS_DIR / SPINE):
            if in_fence:
                self.assertNotIn(
                    "citation-completeness", line,
                    "the citation-completeness rule must be prose, not inside a code fence (%d)" % i,
                )

    def test_rule_names_the_whole_choice_condition(self):
        self.assertRegex(
            self.spine, r"covers the WHOLE\s+choice",
            "the rule must require the citation to cover the WHOLE choice, not one facet",
        )
        self.assertIn("facet", self.spine)

    def test_rule_names_the_gate_or_provisional_pin_alternatives(self):
        self.assertRegex(
            self.spine, r"Decision gate .*or a provisional pin",
            "silent/partial grounding must route to the Decision gate OR a provisional pin",
        )

    def test_rule_binds_to_the_existing_architecture_decisions_grammar_not_a_new_section(self):
        self.assertRegex(
            self.spine, r"`## Architecture decisions`\s+rationale names the rejected alternative"
        )
        self.assertIn("no new schema field", self.spine)
        # The "name the rejected one" convention this rule cites must actually exist in S5, so the
        # binding is to real prose, not an invented cross-reference.
        self.assertIn("name the rejected one", self.spine)

    def test_rule_is_checkable_post_hoc(self):
        self.assertRegex(
            self.spine, r"partial citation.*no named alternative.*(is a )?defect",
            "a pinned choice with a partial citation and no named alternative must be a named defect",
        )


class OperatorGateCoverageTests(unittest.TestCase):
    """S13 DoD box 5 (offline half): the spec's operator gates are present in the v2 skill."""

    def setUp(self):
        self.spine = (PLAYBOOKS_DIR / SPINE).read_text(encoding="utf-8")
        self.revise = (PLAYBOOKS_DIR / "revise.md").read_text(encoding="utf-8")

    def test_deviation_and_decision_gates_present(self):
        self.assertIn('header: "Deviation"', self.spine)
        self.assertIn('header: "Decision"', self.spine)

    def test_review_notes_gate_present_with_dim4_carveout(self):
        self.assertIn('header: "Review notes"', self.spine)
        self.assertRegex(self.spine, r'dimension-4 BLOCKER.*"Post as-is" is not offered')

    def test_revise_reconciliation_confirm_soft_and_hard(self):
        self.assertIn("**Apply** / **Cancel**", self.revise)
        self.assertIn("Start fresh (recommended)", self.revise)


class HardReviseSequenceTests(unittest.TestCase):
    """S13 scenario-4 D4 fix: on HARD "Start fresh", grounding must follow the close decision, never
    precede it — a HARD-revised plan posted while still grounded at the open-PR-head row (selected
    before the close) would cite a branch nothing can read once it's gone. Structural (line-order)
    asserts over skills/planner/playbooks/revise.md + its reconciliation reference, pinning: close-pr
    precedes the re-prep call precedes the repost; the re-selected-row language is present; the old
    (closed) PR-head ref is explicitly ruled out as the HARD footer's ground."""

    def setUp(self):
        self.revise_path = PLAYBOOKS_DIR / "revise.md"
        self.revise = self.revise_path.read_text(encoding="utf-8")
        self.reconciliation_path = REFERENCES_DIR / "revise-reconciliation.md"
        self.reconciliation = self.reconciliation_path.read_text(encoding="utf-8")

    def _first_fenced_line_containing(self, text, needle):
        """Return the 1-based line number of the first line inside a ``` fence containing `needle`,
        or None."""
        in_fence = False
        for i, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence and needle in line:
                return i
        return None

    def _first_line_containing(self, text, needle):
        for i, line in enumerate(text.splitlines(), 1):
            if needle in line:
                return i
        return None

    def test_close_pr_precedes_the_stop_handoff_precedes_the_fresh_run_post(self):
        # v3 sequence: close-pr -> STOP (this session's ambient checkout is the superseded PR's
        # worktree; a re-prep would refuse with WORKSPACE_MISMATCH; hand off with the target
        # checkout on a Workspace: line) -> the FRESH planner run (in the right checkout) grounds
        # and posts. The v2 in-session re-prep + repost is retired by design (review B1).
        post_needle_by_label = {
            "revise.md": "The fresh planner run",
            "revise-reconciliation.md": "The fresh planner run",
        }
        for text, label, path in (
            (self.revise, "revise.md", self.revise_path),
            (self.reconciliation, "revise-reconciliation.md", self.reconciliation_path),
        ):
            close_line = self._first_fenced_line_containing(text, "close-pr")
            stop_line = self._first_line_containing(text, "WORKSPACE_MISMATCH")
            post_line = self._first_line_containing(text, post_needle_by_label[label])
            self.assertIsNotNone(close_line, "%s: no fenced close-pr command found" % label)
            self.assertIsNotNone(stop_line, "%s: no stop-with-WORKSPACE_MISMATCH rationale" % label)
            self.assertIsNotNone(post_line, "%s: no fresh-run post step found" % label)
            self.assertLess(
                close_line, stop_line,
                "%s:%d close-pr must precede the stop/handoff at :%d" % (label, close_line, stop_line),
            )
            self.assertLess(
                stop_line, post_line,
                "%s:%d the stop/handoff must precede the fresh-run post at :%d"
                % (label, stop_line, post_line),
            )

    def test_soft_persist_runs_immediately_hard_persist_is_deferred(self):
        self.assertIn("SOFT-Apply", self.revise)
        self.assertRegex(self.revise, r"SOFT-Apply.*runs the spine's persist immediately")
        self.assertRegex(
            self.revise, r"HARD-Start-fresh does NOT run the spine's persist"
        )

    def test_hard_revise_hands_off_with_a_workspace_line_never_re_grounds_in_session(self):
        # v3 replacement for the retired D6-citation test (no second in-session prep exists to be
        # made safe): both files must carry the cannot-re-ground rule and the Workspace: carrier.
        for text, label in (
            (self.revise, "revise.md"),
            (self.reconciliation, "revise-reconciliation.md"),
        ):
            self.assertIn("Workspace:", text, "%s must carry the handoff Workspace: line" % label)
            self.assertIn("WORKSPACE_MISMATCH", text, "%s must state why re-grounding here refuses" % label)
        self.assertRegex(self.revise, r"cannot re-ground itself")

    def test_plan_ref_re_selection_is_row_table_driven_never_hardcoded(self):
        for text, label in (
            (self.revise, "revise.md"),
            (self.reconciliation, "revise-reconciliation.md"),
        ):
            self.assertRegex(
                text, r"re-select(s|ed)?\s*\*{0,2}deterministically",
                "%s must state plan_ref re-selects off the row table" % label,
            )
            self.assertIn(
                "never hardcode", text.lower().replace("hardcoded", "hardcode"),
                "%s must explicitly rule out hardcoding main" % label,
            )

    def test_hard_footer_explicitly_rules_out_the_closed_prs_head(self):
        # The exact regression this fix closes: the HARD-revised plan's footer/Grounding must never
        # cite the (about-to-be/now-)closed PR's branch.
        self.assertRegex(
            self.revise,
            r"grounded on a branch this decision is closing|posting it as-is would leave the footer",
        )
        renderings = (REFERENCES_DIR / "handoff-renderings.md").read_text(encoding="utf-8")
        self.assertRegex(
            renderings, r"never\s+the closed branch",
            "handoff-renderings.md must explicitly rule out the closed PR's branch as the HARD ground",
        )

    def test_predecessor_facts_captured_before_reprep_replaces_facts(self):
        # Step 1's "capture before re-prep" ordering (## Predecessor / DoD un-tick need the OLD
        # envelope's facts.plan / facts.revise, which a second prep_planner.py call replaces).
        self.assertRegex(self.revise, r"[Cc]apture what `## Predecessor`")
        self.assertRegex(self.revise, r"before\s+step 2 replaces `facts`")
        self.assertIn("facts.revise.open_pr", self.revise)
        self.assertIn("facts.plan", self.revise)


if __name__ == "__main__":
    unittest.main()
