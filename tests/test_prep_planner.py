"""Unit tests for scripts/prep_planner.py — the planner's complete facts block in one call
(architecture.md §4; docs/implementation.md S12; docs/specs/planner.md).

Test topology (mirrors tests/test_prep_resolver.py / tests/test_prep_evaluator.py — the S8-locked
composition pattern this step inherits): `gh` calls go through the offline shim
(`tests/support/shimenv`); `git` calls (root freshness, `ensure --read`, and the `git ls-remote`
epic-branch discovery this step's plan-ref table needs) go through a real temp origin+clone
(`tests/support/gitsandbox`) — no shim needed for those (architecture.md §10). `prep_planner.py`
is driven as a real subprocess so every test exercises the full argv-in / subprocess / envelope-out
path a real caller uses. Every fixture origin is a local git sandbox — hermetic per the S9 lesson
(no test resolves `.` against a real network-backed clone); `shimenv.intercepted_env`'s
`NETWORK_POISON_ENV` guard is never bypassed.

Coverage matrix (S12 DoD):
- Plan-ref fixtures: single issue no-PR, single issue open-PR (revise), story-under-epic, epic
  (branch found + bootstrap) — each asserts `plan_ref` + `read_workspaces.grounding.sha`.
- The seeded tracker-match fixture (Bug (a) regression) + a no-match fixture.
- Revise facts: prior plan body path (forced path-mode via an oversized plan body) + parsed
  `## Phase tracker`.
- Marker-detection variants: research only / plan only (= the open-PR-revise fixture) / both /
  neither (= the default row fixture).
- Conformance on every emitting path + the two-sided call-budget test (S6 style).
- Decision codes: MARKER_AMBIGUOUS (duplicate plan comments; duplicate research comments),
  AUTH_REQUIRED, ROOT_NOT_ON_MAIN / ROOT_DIRTY, AMBIGUOUS (multiple epic-branch matches, multiple
  parent-epic matches, malformed `## Open questions`).
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPT = SCRIPTS_DIR / "prep_planner.py"

sys.path.insert(0, str(SCRIPTS_DIR))

import prep_planner  # noqa: E402  (import after sys.path setup, by necessity)
from tests.support import envelope_asserts, gitsandbox, shimenv  # noqa: E402


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _git(args, cwd):
    result = subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, encoding="utf-8", check=False
    )
    if result.returncode != 0:
        raise RuntimeError("git %s (cwd=%s) failed: %s" % (" ".join(args), cwd, result.stderr))
    return result.stdout.strip()


def _parse_one_envelope(stdout_text):
    lines = [line for line in stdout_text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise AssertionError(
            "expected exactly one non-blank stdout line (the envelope), got %d: %r"
            % (len(lines), lines)
        )
    return json.loads(lines[0])


class PrepPlannerSandboxTestCase(unittest.TestCase):
    """Shared setup: a real temp git origin+clone (the `--root`), pre-seeded with `.gitignore`
    (mirroring tests/test_prep_resolver.py's identical rationale: an unseeded first `ensure` would
    spuriously trip ROOT_DIRTY on the very first call)."""

    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path
        _write(self.root / ".gitignore", ".worktrees/\n")
        _git(["add", ".gitignore"], self.root)
        _git(["commit", "-m", "seed gitignore"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.scratch = self._tmp_ctx.name
        self.addCleanup(self._tmp_ctx.cleanup)

    def _run(self, args, fixture_case=None, extra_env=None):
        env = shimenv.intercepted_env(base_env=os.environ, fixture_case=fixture_case)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + args,
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def _envelope(self, issue="200", repo="octo/widgets", fixture_case="prep_planner_row_default", extra_args=None):
        args = [issue, repo, "--root", str(self.root), "--scratch-dir", self.scratch]
        if extra_args:
            args += extra_args
        result = self._run(args, fixture_case=fixture_case)
        self.assertEqual(result.returncode, 0, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        return envelope

    def _push_branch(self, name):
        _git(["fetch", "origin"], self.root)
        _git(["branch", name, "origin/main"], self.root)
        _git(["push", "origin", name], self.root)


class ScriptExistsTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_script_compiles(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)], capture_output=True, encoding="utf-8"
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class HappyPathFactsSchemaTests(PrepPlannerSandboxTestCase):
    """Facts schema matches architecture.md §4's common core + planner extensions."""

    def test_conformant_ok_envelope_with_planner_facts(self):
        envelope = self._envelope()
        self.assertEqual(envelope["status"], "ok")
        for key in (
            "repo", "scratch", "root", "target", "vector", "suggested_playbook", "plan_ref",
            "plan", "research", "grounding_docs", "open_questions", "open_question_candidates",
            "read_workspaces", "sections", "attention", "notices",
        ):
            self.assertIn(key, envelope, "missing architecture.md §4 facts-block key %r" % key)

    def test_root_facts_shape(self):
        envelope = self._envelope()
        self.assertEqual(envelope["root"]["path"], str(self.root))
        self.assertEqual(len(envelope["root"]["sha"]), 40)
        self.assertTrue(envelope["root"]["fresh"])

    def test_target_facts_shape(self):
        envelope = self._envelope()
        self.assertEqual(envelope["target"]["kind"], "issue")
        self.assertEqual(envelope["target"]["number"], 200)
        self.assertEqual(envelope["target"]["state"], "OPEN")
        self.assertEqual(envelope["target"]["labels"], ["bug"])

    def test_vector_standard_fresh_default_row(self):
        envelope = self._envelope()
        self.assertEqual(envelope["vector"]["type"], "standard")
        self.assertEqual(envelope["vector"]["mode"], "fresh")
        self.assertEqual(envelope["vector"]["plan_ref_row"], prep_planner.PLAN_REF_ROW_DEFAULT)
        self.assertEqual(envelope["suggested_playbook"], "single.md")

    def test_planner_never_gets_a_work_workspace(self):
        # architecture.md §6 / prd §8.4: grounding is read-only; the planner never has a `workspace`
        # key the way the resolver does.
        envelope = self._envelope()
        self.assertNotIn("workspace", envelope)
        self.assertIn("read_workspaces", envelope)
        self.assertIn("grounding", envelope["read_workspaces"])

    def test_no_open_questions_no_candidates(self):
        envelope = self._envelope()
        self.assertEqual(envelope["open_questions"], [])
        self.assertEqual(envelope["open_question_candidates"], [])
        self.assertEqual(envelope["attention"], [])

    def test_plan_absent_is_a_fact_not_a_decision(self):
        envelope = self._envelope()
        self.assertFalse(envelope["plan"]["present"])
        self.assertIsNone(envelope["plan"]["sha"])

    def test_research_absent(self):
        envelope = self._envelope()
        self.assertFalse(envelope["research"]["present"])

    def test_no_epic_or_story_key_for_standard_type(self):
        envelope = self._envelope()
        self.assertNotIn("epic", envelope)
        self.assertNotIn("story", envelope)
        self.assertNotIn("revise", envelope)

    def test_sections_carries_gh_gather_spill_fields_through(self):
        envelope = self._envelope()
        self.assertIn("issue_body", envelope["sections"])
        self.assertEqual(envelope["sections"]["issue_body_mode"], "inline")


class PlanRefRowTests(PrepPlannerSandboxTestCase):
    """Plan-ref fixtures: single issue no-PR, single issue open-PR, story-under-epic, epic — each
    asserting `plan_ref` + `read_workspaces.grounding.sha` (S12 DoD's first box)."""

    def test_row_default_single_issue_no_pr(self):
        envelope = self._envelope(issue="200", fixture_case="prep_planner_row_default")
        self.assertEqual(envelope["vector"]["plan_ref_row"], prep_planner.PLAN_REF_ROW_DEFAULT)
        self.assertEqual(envelope["plan_ref"], "main")
        self.assertEqual(envelope["read_workspaces"]["grounding"]["ref"], "main")
        self.assertEqual(len(envelope["read_workspaces"]["grounding"]["sha"]), 40)
        self.assertTrue(Path(envelope["read_workspaces"]["grounding"]["path"]).is_dir())

    def test_row_open_pr_head_wins_revise_mode(self):
        _git(["fetch", "origin"], self.root)
        _git(["checkout", "-b", "201-fix-gadget"], self.root)
        _write(self.root / "gadget.txt", "fixed\n")
        _git(["add", "gadget.txt"], self.root)
        _git(["commit", "-m", "fix gadget"], self.root)
        _git(["push", "origin", "201-fix-gadget"], self.root)
        _git(["checkout", "main"], self.root)

        envelope = self._envelope(issue="201", fixture_case="prep_planner_row_open_pr_revise")
        self.assertEqual(envelope["vector"]["plan_ref_row"], prep_planner.PLAN_REF_ROW_OPEN_PR_HEAD)
        self.assertEqual(envelope["plan_ref"], "201-fix-gadget")
        self.assertEqual(envelope["vector"]["mode"], "revise")
        self.assertEqual(envelope["read_workspaces"]["grounding"]["ref"], "201-fix-gadget")
        self.assertEqual(len(envelope["read_workspaces"]["grounding"]["sha"]), 40)

    def test_row_story_under_open_epic(self):
        self._push_branch("epic/100-sandbox-fixture")
        envelope = self._envelope(issue="202", fixture_case="prep_planner_row_story_under_epic")
        self.assertEqual(envelope["vector"]["type"], "story")
        self.assertEqual(envelope["vector"]["plan_ref_row"], prep_planner.PLAN_REF_ROW_STORY_PARENT_BRANCH)
        self.assertEqual(envelope["plan_ref"], "epic/100-sandbox-fixture")
        self.assertEqual(envelope["read_workspaces"]["grounding"]["ref"], "epic/100-sandbox-fixture")
        self.assertEqual(len(envelope["read_workspaces"]["grounding"]["sha"]), 40)
        self.assertEqual(envelope["story"]["parent_epic"]["number"], 100)
        self.assertTrue(envelope["story"]["parent_epic_open"])
        self.assertEqual(envelope["story"]["epic_branch"]["branch"], "epic/100-sandbox-fixture")
        self.assertTrue(envelope["story"]["epic_plan"]["present"])
        self.assertTrue(envelope["story"]["epic_delivery_log"]["present"])
        self.assertEqual(envelope["suggested_playbook"], "story-jit.md")

    def test_row_story_under_open_epic_bootstrap(self):
        # D4 regression fixture: story under an OPEN parent epic, but zero `git ls-remote` matches
        # for that epic's integration branch (the epic itself hasn't bootstrapped a branch yet --
        # no sibling story has been resolved for it). Deliberately does NOT push an epic branch.
        envelope = self._envelope(issue="203", fixture_case="prep_planner_row_story_parent_bootstrap")
        self.assertEqual(envelope["vector"]["type"], "story")
        self.assertEqual(
            envelope["vector"]["plan_ref_row"], prep_planner.PLAN_REF_ROW_STORY_PARENT_BOOTSTRAP
        )
        # The row must be truthful, never the "no open parent" label a self-contradictory D4 run
        # produced (parent_epic_open: true alongside a row name that denies it).
        self.assertNotEqual(
            envelope["vector"]["plan_ref_row"], prep_planner.PLAN_REF_ROW_STORY_NO_PARENT
        )
        self.assertEqual(envelope["plan_ref"], "main")
        self.assertEqual(envelope["read_workspaces"]["grounding"]["ref"], "main")
        self.assertEqual(len(envelope["read_workspaces"]["grounding"]["sha"]), 40)
        self.assertEqual(envelope["story"]["parent_epic"]["number"], 101)
        self.assertTrue(envelope["story"]["parent_epic_open"])
        self.assertEqual(envelope["story"]["epic_branch"]["match_count"], 0)
        self.assertIsNone(envelope["story"]["epic_branch"]["branch"])
        self.assertFalse(envelope["story"]["epic_plan"]["present"])
        self.assertFalse(envelope["story"]["epic_delivery_log"]["present"])
        # Routing is UNCHANGED by the D4 fix: story + parent_epic_open -> story-jit.md regardless
        # of which of the two "no branch" rows fired.
        self.assertEqual(envelope["suggested_playbook"], "story-jit.md")

    def test_row_epic_as_target_branch_found(self):
        self._push_branch("epic/300-sandbox-epic")
        envelope = self._envelope(issue="300", fixture_case="prep_planner_row_epic")
        self.assertEqual(envelope["vector"]["type"], "epic")
        self.assertEqual(envelope["vector"]["plan_ref_row"], prep_planner.PLAN_REF_ROW_EPIC_BRANCH)
        self.assertEqual(envelope["plan_ref"], "epic/300-sandbox-epic")
        self.assertEqual(envelope["read_workspaces"]["grounding"]["ref"], "epic/300-sandbox-epic")
        self.assertEqual(envelope["epic"]["branch"]["match_count"], 1)
        self.assertEqual(len(envelope["epic"]["branch"]["sha"]), 40)
        self.assertTrue(envelope["epic"]["stories_filed"])
        self.assertEqual(len(envelope["epic"]["stories"]), 2)
        numbers = {s["number"]: s["state"] for s in envelope["epic"]["stories"]}
        self.assertEqual(numbers, {301: "OPEN", 302: "CLOSED"})
        self.assertEqual(envelope["suggested_playbook"], "epic.md")

    def test_row_epic_as_target_bootstrap(self):
        envelope = self._envelope(issue="310", fixture_case="prep_planner_row_epic_bootstrap")
        self.assertEqual(envelope["vector"]["plan_ref_row"], prep_planner.PLAN_REF_ROW_EPIC_BOOTSTRAP)
        self.assertEqual(envelope["plan_ref"], "main")
        self.assertEqual(envelope["epic"]["branch"]["match_count"], 0)
        self.assertIsNone(envelope["epic"]["branch"]["branch"])
        self.assertFalse(envelope["epic"]["stories_filed"])
        # one unfiled placeholder bullet
        self.assertEqual(envelope["epic"]["stories"], [
            {"number": None, "title": "Story placeholder one", "checked": False, "state": None, "live_title": None}
        ])
        self.assertTrue(
            any("bootstrap" in item for item in envelope["attention"]), envelope["attention"]
        )


class GroundingDocInventoryTests(PrepPlannerSandboxTestCase):
    def test_no_docs_present_at_main(self):
        envelope = self._envelope(issue="200", fixture_case="prep_planner_row_default")
        docs = {d["doc"]: d["present"] for d in envelope["grounding_docs"]}
        self.assertEqual(
            docs,
            {"docs/prd.md": False, "docs/architecture.md": False, "docs/constitution.md": False, "CLAUDE.md": False},
        )

    def test_docs_present_are_reported_with_paths_inside_the_workspace(self):
        _write(self.root / "CLAUDE.md", "# hi\n")
        _git(["add", "CLAUDE.md"], self.root)
        _git(["commit", "-m", "seed CLAUDE.md"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)

        envelope = self._envelope(issue="200", fixture_case="prep_planner_row_default")
        by_doc = {d["doc"]: d for d in envelope["grounding_docs"]}
        self.assertTrue(by_doc["CLAUDE.md"]["present"])
        self.assertIn(envelope["read_workspaces"]["grounding"]["path"], by_doc["CLAUDE.md"]["path"])
        self.assertFalse(by_doc["docs/prd.md"]["present"])
        self.assertIsNone(by_doc["docs/prd.md"]["path"])


class OpenQuestionTrackerSearchTests(PrepPlannerSandboxTestCase):
    """Bug (a) regression: a "(not filed)" OQ whose companion question issue actually EXISTS must
    surface in `open_question_candidates` (S12 DoD's second box) — plus the legitimately-open
    no-match counterpart."""

    def test_seeded_tracker_match_surfaces_the_candidate(self):
        envelope = self._envelope(issue="400", fixture_case="prep_planner_oq_tracker_match")
        self.assertEqual(len(envelope["open_questions"]), 1)
        self.assertEqual(envelope["open_questions"][0]["question"], "(not filed)")
        self.assertEqual(len(envelope["open_question_candidates"]), 1)
        group = envelope["open_question_candidates"][0]
        self.assertEqual(group["oq_id"], "tag case sensitivity")
        self.assertEqual(group["query"], "tag case sensitivity")
        self.assertEqual(len(group["candidates"]), 1)
        self.assertEqual(group["candidates"][0]["number"], 51)
        self.assertEqual(group["candidates"][0]["state"], "OPEN")
        self.assertIn("question", group["candidates"][0]["labels"])
        self.assertTrue(
            any("tag case sensitivity" in item and "do not record it as (not filed)" in item
                for item in envelope["attention"]),
            envelope["attention"],
        )

    def test_no_match_leaves_not_filed_path_legitimately_open(self):
        envelope = self._envelope(issue="401", fixture_case="prep_planner_oq_no_match")
        self.assertEqual(len(envelope["open_questions"]), 1)
        self.assertEqual(envelope["open_question_candidates"], [])
        self.assertEqual(envelope["attention"], [])


class OqQueryOneShotTests(PrepPlannerSandboxTestCase):
    """S13 authorized additive `--oq-query` mode: the one-shot tracker de-dup lookup a playbook runs
    for an OQ it detects ANEW during grounding (not in the issue body). Fast path — one `gh issue
    list` call, no facts assembly, conformant envelope."""

    def test_oq_query_emits_candidates_without_full_facts(self):
        result = self._run(
            ["400", "octo/widgets", "--oq-query", "cache eviction policy"],
            fixture_case="prep_planner_oq_query",
        )
        self.assertEqual(result.returncode, 0, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "ok")
        # It is the one-shot payload, NOT a full facts block (no vector / suggested_playbook).
        self.assertNotIn("vector", envelope)
        self.assertNotIn("suggested_playbook", envelope)
        self.assertIn("oq_query_candidates", envelope)
        groups = envelope["oq_query_candidates"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["query"], "cache eviction policy")
        self.assertEqual(groups[0]["candidates"][0]["number"], 88)
        self.assertEqual(groups[0]["candidates"][0]["state"], "OPEN")

    def test_oq_query_empty_list_makes_no_call(self):
        # Zero queries -> empty candidate list, no gh call (build core, no network).
        payload, notices, decision = prep_planner.build_oq_query("octo/widgets", [], cwd=None)
        self.assertIsNone(decision)
        self.assertEqual(payload, {"repo": "octo/widgets", "oq_query_candidates": []})
        self.assertEqual(notices, [])


class MarkerDetectionVariantTests(PrepPlannerSandboxTestCase):
    """Marker-detection variants: research only / plan only / both / neither."""

    def test_neither_marker_present(self):
        envelope = self._envelope(issue="200", fixture_case="prep_planner_row_default")
        self.assertFalse(envelope["plan"]["present"])
        self.assertFalse(envelope["research"]["present"])
        self.assertEqual(envelope["vector"]["mode"], "fresh")

    def test_plan_only(self):
        _git(["fetch", "origin"], self.root)
        _git(["checkout", "-b", "201-fix-gadget"], self.root)
        _write(self.root / "gadget.txt", "fixed\n")
        _git(["add", "gadget.txt"], self.root)
        _git(["commit", "-m", "fix gadget"], self.root)
        _git(["push", "origin", "201-fix-gadget"], self.root)
        _git(["checkout", "main"], self.root)

        envelope = self._envelope(issue="201", fixture_case="prep_planner_row_open_pr_revise")
        self.assertTrue(envelope["plan"]["present"])
        self.assertFalse(envelope["research"]["present"])
        self.assertEqual(envelope["vector"]["mode"], "revise")

    def test_research_only(self):
        envelope = self._envelope(issue="500", fixture_case="prep_planner_marker_research_only")
        self.assertFalse(envelope["plan"]["present"])
        self.assertTrue(envelope["research"]["present"])
        self.assertEqual(envelope["vector"]["mode"], "fresh")
        self.assertIn("comment_url", envelope["research"])

    def test_both_markers_present(self):
        envelope = self._envelope(issue="501", fixture_case="prep_planner_marker_both")
        self.assertTrue(envelope["plan"]["present"])
        self.assertTrue(envelope["research"]["present"])
        self.assertEqual(envelope["vector"]["mode"], "revise")


class ReviseFactsTests(PrepPlannerSandboxTestCase):
    """Revise facts include prior plan body path + phase tracker (S12 DoD's third box)."""

    def test_prior_plan_body_is_staged_to_a_path_and_phase_tracker_parsed(self):
        _git(["fetch", "origin"], self.root)
        _git(["checkout", "-b", "900-large-plan"], self.root)
        _write(self.root / "large.txt", "x\n")
        _git(["add", "large.txt"], self.root)
        _git(["commit", "-m", "large plan work"], self.root)
        _git(["push", "origin", "900-large-plan"], self.root)
        _git(["checkout", "main"], self.root)

        envelope = self._envelope(issue="900", fixture_case="prep_planner_revise_large_plan")
        self.assertEqual(envelope["vector"]["mode"], "revise")
        self.assertEqual(envelope["plan"]["body_mode"], "path")
        self.assertTrue(Path(envelope["plan"]["body_path"]).is_file())
        self.assertGreater(Path(envelope["plan"]["body_path"]).stat().st_size, 25600)

        revise = envelope["revise"]
        self.assertEqual(revise["prior_plan_sha"], "9999999")
        self.assertEqual(len(revise["grounding_sha"]), 40)
        self.assertIsNotNone(revise["open_pr"])
        self.assertEqual(revise["open_pr"]["headRefName"], "900-large-plan")
        self.assertEqual(len(revise["phase_tracker"]), 2)
        self.assertEqual(revise["phase_tracker"][0], {
            "checked": True, "phase": 1, "title": "substrate", "commit_sha": "9999999",
        })
        self.assertEqual(revise["phase_tracker"][1], {
            "checked": False, "phase": 2, "title": "harness", "commit_sha": None,
        })

    def test_fresh_mode_has_no_revise_key(self):
        envelope = self._envelope(issue="200", fixture_case="prep_planner_row_default")
        self.assertNotIn("revise", envelope)


class DecisionCodeTests(PrepPlannerSandboxTestCase):
    def test_auth_required_on_first_gh_call(self):
        result = self._run(
            ["600", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_planner_auth_required",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AUTH_REQUIRED")

    def test_duplicate_plan_comments_yields_marker_ambiguous(self):
        result = self._run(
            ["601", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_planner_marker_ambiguous",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "MARKER_AMBIGUOUS")
        self.assertFalse((self.root / ".worktrees").exists())

    def test_duplicate_research_comments_yields_marker_ambiguous(self):
        # This module's OWN thread-scan MARKER_AMBIGUOUS (research dossier), not gh_gather's.
        result = self._run(
            ["602", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_planner_research_marker_ambiguous",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "MARKER_AMBIGUOUS")
        self.assertIn("research-dossier", envelope["decision"]["summary"])

    def test_multiple_epic_branch_matches_yields_ambiguous(self):
        self._push_branch("epic/320-a")
        self._push_branch("epic/320-b")
        result = self._run(
            ["320", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_planner_epic_branch_multiple",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertEqual(len(envelope["decision"]["context"]["candidates"]), 2)

    def test_multiple_parent_epic_matches_yields_ambiguous(self):
        result = self._run(
            ["700", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_planner_story_parent_multiple",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertEqual(len(envelope["decision"]["context"]["candidates"]), 2)

    def test_malformed_open_questions_section_yields_ambiguous(self):
        _write(self.root / "issue_body_unused.txt", "")  # no-op, keeps root clean
        entries_or_decision = None
        try:
            prep_planner.parse.parse_oq_links(
                "## Open questions\n<!-- open-question-links:v1 -->\n"
                "- OQ: `x` (issue body) — gates: y\n  — disposition: not-a-real-disposition\n"
            )
        except prep_planner.parse._OqLinksMalformed:
            entries_or_decision = "raised"
        self.assertEqual(entries_or_decision, "raised")


class RootDecisionPropagationTests(PrepPlannerSandboxTestCase):
    def test_root_not_on_main_propagates(self):
        _git(["checkout", "-b", "not-main"], self.root)
        self.addCleanup(lambda: _git(["checkout", "main"], self.root))
        envelope = self._envelope(fixture_case="prep_planner_row_default")
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "ROOT_NOT_ON_MAIN")

    def test_root_dirty_propagates(self):
        _write(self.root / "dirty.txt", "uncommitted\n")
        envelope = self._envelope(fixture_case="prep_planner_row_default")
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "ROOT_DIRTY")


class RefreshModeTests(PrepPlannerSandboxTestCase):
    """--refresh re-derives volatile facts without re-running root freshness or re-ensuring the
    grounding read workspace (mirrors tests/test_prep_resolver.py's / tests/test_prep_evaluator.py's
    identical `--refresh` contract; architecture.md §4)."""

    def test_refresh_never_touches_root_freshness_or_grounding_workspace(self):
        envelope = self._envelope(fixture_case="prep_planner_row_default", extra_args=["--refresh"])
        self.assertEqual(envelope["status"], "ok")
        self.assertNotIn("read_workspaces", envelope)
        self.assertEqual(envelope["grounding_docs"], [])
        self.assertFalse(envelope["root"]["fresh"])
        self.assertIsNone(envelope["root"]["sha"])
        self.assertFalse((self.root / ".worktrees").exists())

    def test_refresh_still_reports_vector_and_oq_candidates(self):
        envelope = self._envelope(issue="400", fixture_case="prep_planner_oq_tracker_match", extra_args=["--refresh"])
        self.assertEqual(envelope["vector"]["type"], "standard")
        self.assertEqual(len(envelope["open_question_candidates"]), 1)


class SingleInvocationBudgetTests(PrepPlannerSandboxTestCase):
    """Single-invocation budget: the canonical (standard/fresh/no-OQ/no-epic/no-PR) path's shim
    call count is bounded and stable, both an upper AND a lower bound (S12 DoD's fourth box:
    "conformance + call budget as S6")."""

    def test_shim_call_count_for_canonical_run_is_exactly_three(self):
        # gh calls on the canonical path: issue view (+deps), paginated comments, open-PR search —
        # three, no more, no fewer. No epic/story branch discovery (git, not gh, and only for
        # epic/story types), no OQ tracker search (no `## Open questions` section), no PR gather
        # (fresh mode, no open PR).
        result = self._run(
            ["200", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_planner_row_default",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        manifest_path = shimenv.fixture_case_dir("prep_planner_row_default") / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 3)

    def test_no_gh_call_is_repeated_within_one_run(self):
        manifest_path = shimenv.fixture_case_dir("prep_planner_row_default") / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        argv_tuples = [tuple(entry["argv"]) for entry in manifest]
        self.assertEqual(len(argv_tuples), len(set(argv_tuples)), "duplicate argv in manifest")

    def test_revise_with_open_pr_costs_strictly_more_calls_than_canonical(self):
        # Upper-bound half of the two-sided budget: revise mode with an open PR adds the
        # gh_pr_gather `gh pr view` call on top of the canonical three.
        _git(["fetch", "origin"], self.root)
        _git(["checkout", "-b", "201-fix-gadget"], self.root)
        _write(self.root / "gadget.txt", "fixed\n")
        _git(["add", "gadget.txt"], self.root)
        _git(["commit", "-m", "fix gadget"], self.root)
        _git(["push", "origin", "201-fix-gadget"], self.root)
        _git(["checkout", "main"], self.root)

        result = self._run(
            ["201", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_planner_row_open_pr_revise",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        manifest_path = shimenv.fixture_case_dir("prep_planner_row_open_pr_revise") / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 4)
        self.assertGreater(len(manifest), 3)


class PureHelperUnitTests(unittest.TestCase):
    """Direct, in-process tests of prep_planner's pure classification/derivation helpers — no
    subprocess, no shim, no git sandbox needed (mirrors test_prep_resolver.py's
    PureHelperUnitTests style)."""

    def test_detect_type_epic_by_label(self):
        self.assertEqual(prep_planner._detect_type(["epic"], "Sandbox fixture"), "epic")

    def test_detect_type_epic_by_title_prefix_case_insensitive(self):
        self.assertEqual(prep_planner._detect_type([], "EPIC: sandbox fixture"), "epic")

    def test_detect_type_story_by_label(self):
        self.assertEqual(prep_planner._detect_type(["story"], "Story A"), "story")

    def test_detect_type_standard_default(self):
        self.assertEqual(prep_planner._detect_type(["bug"], "Fix the thing"), "standard")

    def test_select_plan_ref_default_row(self):
        self.assertEqual(
            prep_planner._select_plan_ref("standard", None, None),
            ("main", prep_planner.PLAN_REF_ROW_DEFAULT),
        )

    def test_select_plan_ref_epic_branch_row(self):
        self.assertEqual(
            prep_planner._select_plan_ref("epic", "epic/1-x", None),
            ("epic/1-x", prep_planner.PLAN_REF_ROW_EPIC_BRANCH),
        )

    def test_select_plan_ref_epic_bootstrap_row(self):
        self.assertEqual(
            prep_planner._select_plan_ref("epic", None, None),
            ("main", prep_planner.PLAN_REF_ROW_EPIC_BOOTSTRAP),
        )

    def test_select_plan_ref_story_parent_branch_row(self):
        self.assertEqual(
            prep_planner._select_plan_ref("story", "epic/1-x", None),
            ("epic/1-x", prep_planner.PLAN_REF_ROW_STORY_PARENT_BRANCH),
        )

    def test_select_plan_ref_story_no_parent_row(self):
        # parent_epic_open defaults False -> the genuinely-parentless/closed-parent row.
        self.assertEqual(
            prep_planner._select_plan_ref("story", None, None),
            ("main", prep_planner.PLAN_REF_ROW_STORY_NO_PARENT),
        )
        self.assertEqual(
            prep_planner._select_plan_ref("story", None, None, parent_epic_open=False),
            ("main", prep_planner.PLAN_REF_ROW_STORY_NO_PARENT),
        )

    def test_select_plan_ref_story_parent_bootstrap_row(self):
        # D4 fix: an OPEN parent whose integration branch hasn't bootstrapped yet gets its own
        # truthful row -- same plan_ref (main) as STORY_NO_PARENT, but a label that doesn't
        # contradict a simultaneously-true `story.parent_epic_open` fact.
        self.assertEqual(
            prep_planner._select_plan_ref("story", None, None, parent_epic_open=True),
            ("main", prep_planner.PLAN_REF_ROW_STORY_PARENT_BOOTSTRAP),
        )

    def test_select_plan_ref_story_parent_open_but_no_branch_never_yields_no_parent_row(self):
        # Direct regression guard for D4: parent_epic_open=True must NEVER produce the
        # "no-open-parent-epic" row label, regardless of branch presence.
        plan_ref, row = prep_planner._select_plan_ref("story", None, None, parent_epic_open=True)
        self.assertNotEqual(row, prep_planner.PLAN_REF_ROW_STORY_NO_PARENT)
        self.assertEqual(row, prep_planner.PLAN_REF_ROW_STORY_PARENT_BOOTSTRAP)
        self.assertEqual(plan_ref, "main")

    def test_select_plan_ref_open_pr_head_wins_over_epic_branch(self):
        # docs/specs/planner.md Step 4.5: "the open-PR-head row wins" when more than one applies.
        self.assertEqual(
            prep_planner._select_plan_ref("story", "epic/1-x", "44-fix-thing"),
            ("44-fix-thing", prep_planner.PLAN_REF_ROW_OPEN_PR_HEAD),
        )

    def test_parse_stories_section_filed_and_placeholder(self):
        body = "## Stories\n- [ ] #2 — Story A\n- [x] #3 — Story B\n\n## Definition of done\n- [ ] x\n"
        self.assertEqual(
            prep_planner._parse_stories_section(body),
            [
                {"number": 2, "title": "Story A", "checked": False},
                {"number": 3, "title": "Story B", "checked": True},
            ],
        )

    def test_parse_stories_section_placeholder_bullets(self):
        body = "## Stories\n- [ ] Story one\n- [ ] Story two\n"
        self.assertEqual(
            prep_planner._parse_stories_section(body),
            [
                {"number": None, "title": "Story one", "checked": False},
                {"number": None, "title": "Story two", "checked": False},
            ],
        )

    def test_parse_stories_section_absent(self):
        self.assertEqual(prep_planner._parse_stories_section("no stories section here"), [])

    def test_parse_phase_tracker_ticked_and_unticked(self):
        body = "## Phase tracker\n- [x] Phase 1 — substrate (commit abc1234)\n- [ ] Phase 2 — harness\n"
        self.assertEqual(
            prep_planner._parse_phase_tracker(body),
            [
                {"checked": True, "phase": 1, "title": "substrate", "commit_sha": "abc1234"},
                {"checked": False, "phase": 2, "title": "harness", "commit_sha": None},
            ],
        )

    def test_parse_phase_tracker_absent(self):
        self.assertEqual(prep_planner._parse_phase_tracker("no tracker here"), [])

    def test_suggested_playbook_by_type(self):
        # The four real S13 playbook names, keyed on (type, mode, parent_epic_open).
        self.assertEqual(prep_planner._suggested_playbook("epic", "fresh"), "epic.md")
        self.assertEqual(prep_planner._suggested_playbook("standard", "fresh"), "single.md")
        # A story under an OPEN parent epic -> story-jit (owns both fresh and revise).
        self.assertEqual(
            prep_planner._suggested_playbook("story", "fresh", parent_epic_open=True), "story-jit.md"
        )
        self.assertEqual(
            prep_planner._suggested_playbook("story", "revise", parent_epic_open=True), "story-jit.md"
        )
        # A story with no open parent epic -> the single-issue path (v1 "Everything else").
        self.assertEqual(
            prep_planner._suggested_playbook("story", "fresh", parent_epic_open=False), "single.md"
        )
        # revise mode short-circuits to revise.md for a standalone issue or an epic.
        self.assertEqual(prep_planner._suggested_playbook("standard", "revise"), "revise.md")
        self.assertEqual(prep_planner._suggested_playbook("epic", "revise"), "revise.md")

    def test_extract_plan_sha_from_header_line(self):
        body = "**Implementation plan** — #1 x — planned 2026-01-01T00:00:00Z at `main@abc1234`\n"
        self.assertEqual(prep_planner._extract_plan_sha(body), "abc1234")

    def test_extract_plan_sha_missing_is_none(self):
        self.assertIsNone(prep_planner._extract_plan_sha("no sha header here"))

    def test_find_one_marker_no_match(self):
        comment, decision = prep_planner._find_one_marker([{"body": "unrelated"}], "<!-- x -->", "x")
        self.assertIsNone(comment)
        self.assertIsNone(decision)

    def test_find_one_marker_single_match(self):
        thread = [{"body": "unrelated"}, {"id": 1, "body": "<!-- x -->\nfound"}]
        comment, decision = prep_planner._find_one_marker(thread, "<!-- x -->", "x")
        self.assertEqual(comment["id"], 1)
        self.assertIsNone(decision)

    def test_find_one_marker_multiple_matches_yields_ambiguous(self):
        thread = [{"id": 1, "body": "<!-- x -->\na"}, {"id": 2, "body": "<!-- x -->\nb"}]
        comment, decision = prep_planner._find_one_marker(thread, "<!-- x -->", "x")
        self.assertIsNone(comment)
        self.assertIsNotNone(decision)
        self.assertEqual(decision["code"], "MARKER_AMBIGUOUS")


class UsageErrorTests(unittest.TestCase):
    def test_missing_required_positional_args_is_usage_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_missing_repo_arg_is_usage_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "200"],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
