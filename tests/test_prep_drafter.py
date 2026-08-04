"""Unit tests for scripts/prep_drafter.py — the drafter's complete facts block in one call
(architecture.md §4; docs/implementation.md S14; docs/specs/drafter.md).

Test topology (mirrors tests/test_prep_planner.py — the S8-locked composition pattern this step
inherits): `gh` calls go through the offline shim (`tests/support/shimenv`); `git` calls (this
step needs exactly one — `git rev-parse HEAD` for the informational `root.sha` fact; see
`prep_drafter.py`'s module docstring's "No workspace" paragraph for why there is no root-freshness
protocol here) go through a real temp origin+clone (`tests/support/gitsandbox`) — no shim needed
for those (architecture.md §10). `prep_drafter.py` is driven as a real subprocess so every test
exercises the full argv-in / subprocess / envelope-out path a real caller uses. Every fixture
origin is a local git sandbox — hermetic per the S9 lesson (no test resolves `.` against a real
network-backed clone); `shimenv.intercepted_env`'s `NETWORK_POISON_ENV` guard is never bypassed.

Coverage matrix (S14 DoD):
- Vector derivation ×3: new (no --issue), revise (standalone/story/question target), epic-revise
  (Epic-labeled target).
- OQ candidate search fixtures: match (a genuinely-filed companion) and no-match (legitimately
  still "(not filed)").
- Template/label inventory: present/absent fixtures for `.github/ISSUE_TEMPLATE/` and `gh label
  list`, plus grounding-doc presence (PRD's 4-candidate-path search, architecture/constitution/
  CLAUDE.md).
- Conformance on every emitting path + the two-sided call-budget test (S6/S12 style).
- Decision codes: AUTH_REQUIRED (the labels call; the epic-revise per-story state fetch),
  MARKER_AMBIGUOUS (gh_gather's own duplicate-plan-comment forwarding), AMBIGUOUS (malformed
  `## Open questions` section, forwarded from the S14-promoted `oq_tracker.py`).
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
SCRIPT = SCRIPTS_DIR / "prep_drafter.py"

sys.path.insert(0, str(SCRIPTS_DIR))

import prep_drafter  # noqa: E402  (import after sys.path setup, by necessity)
from tests.support import envelope_asserts, gitsandbox, shimenv  # noqa: E402


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
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


class PrepDrafterSandboxTestCase(unittest.TestCase):
    """Shared setup: a real temp git origin+clone (the `--root`) — no push/fetch is needed (this
    prep runs no root-freshness protocol; see `prep_drafter.py`'s "No workspace" docstring note),
    but a real git repo with a commit is needed for `git rev-parse HEAD` (`root.sha`)."""

    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.scratch = self._tmp_ctx.name
        self.addCleanup(self._tmp_ctx.cleanup)

    def _run(self, args, fixture_case=None):
        env = shimenv.intercepted_env(base_env=os.environ, fixture_case=fixture_case)
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + args,
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def _envelope(self, repo="octo/widgets", issue=None, fixture_case=None, extra_args=None):
        args = [repo, "--root", str(self.root), "--scratch-dir", self.scratch]
        if issue is not None:
            args += ["--issue", str(issue)]
        if extra_args:
            args += extra_args
        result = self._run(args, fixture_case=fixture_case)
        self.assertEqual(result.returncode, 0, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        return envelope


class ScriptExistsTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_script_compiles(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)], capture_output=True, encoding="utf-8"
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


# ---------------------------------------------------------------------------
# DoD box 1: fixtures derive the vector for new, revise, and epic-revise correctly.
# ---------------------------------------------------------------------------


class NewModeVectorTests(PrepDrafterSandboxTestCase):
    def test_new_mode_vector_and_playbook(self):
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        self.assertEqual(envelope["vector"], {"mode": "new", "type": None})
        self.assertEqual(envelope["suggested_playbook"], "new.md")

    def test_new_mode_has_no_target_and_no_revise_epic_keys(self):
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        self.assertIsNone(envelope["target"])
        self.assertNotIn("revise", envelope)
        self.assertNotIn("epic_revise", envelope)
        self.assertNotIn("sections", envelope)
        self.assertEqual(envelope["open_questions"], [])
        self.assertEqual(envelope["open_question_candidates"], [])


class ReviseModeVectorTests(PrepDrafterSandboxTestCase):
    def test_revise_mode_vector_standard_type(self):
        envelope = self._envelope(issue=300, fixture_case="prep_drafter_revise_standard")
        self.assertEqual(envelope["vector"], {"mode": "revise", "type": "standard"})
        self.assertEqual(envelope["suggested_playbook"], "revise.md")

    def test_revise_mode_vector_question_type(self):
        envelope = self._envelope(issue=301, fixture_case="prep_drafter_revise_question")
        self.assertEqual(envelope["vector"], {"mode": "revise", "type": "question"})
        self.assertEqual(envelope["suggested_playbook"], "question.md")

    def test_revise_mode_target_facts_shape(self):
        envelope = self._envelope(issue=300, fixture_case="prep_drafter_revise_standard")
        target = envelope["target"]
        self.assertEqual(target["kind"], "issue")
        self.assertEqual(target["number"], 300)
        self.assertEqual(target["state"], "OPEN")
        self.assertEqual(target["labels"], ["bug"])
        self.assertNotIn("epic_revise", envelope)

    def test_revise_mode_has_revise_key_with_plan_absent_and_no_open_prs(self):
        envelope = self._envelope(issue=300, fixture_case="prep_drafter_revise_standard")
        self.assertIn("revise", envelope)
        self.assertFalse(envelope["revise"]["plan"]["present"])
        self.assertEqual(envelope["revise"]["open_prs"], [])
        self.assertEqual(envelope["revise"]["closed_by_pull_requests_references"], [])
        self.assertEqual(envelope["revise"]["project_items"], [])


class EpicReviseModeVectorTests(PrepDrafterSandboxTestCase):
    def test_epic_revise_vector_and_playbook(self):
        envelope = self._envelope(issue=100, fixture_case="prep_drafter_epic_revise")
        self.assertEqual(envelope["vector"], {"mode": "epic-revise", "type": "epic"})
        self.assertEqual(envelope["suggested_playbook"], "epic-split.md")

    def test_epic_revise_has_no_revise_key(self):
        envelope = self._envelope(issue=100, fixture_case="prep_drafter_epic_revise")
        self.assertNotIn("revise", envelope)
        self.assertIn("epic_revise", envelope)

    def test_epic_revise_stories_reconciled_against_live_state(self):
        envelope = self._envelope(issue=100, fixture_case="prep_drafter_epic_revise")
        stories = {s["number"]: s for s in envelope["epic_revise"]["stories"] if s["number"] is not None}
        self.assertEqual(stories[101]["state"], "CLOSED")
        self.assertTrue(stories[101]["checked"])
        self.assertEqual(stories[102]["state"], "OPEN")
        self.assertFalse(stories[102]["checked"])
        placeholders = [s for s in envelope["epic_revise"]["stories"] if s["number"] is None]
        self.assertEqual(len(placeholders), 1)
        self.assertEqual(placeholders[0]["title"], "Story D placeholder (not filed)")

    def test_epic_revise_legacy_epic_reports_checklist_source(self):
        """This fixture's epic predates the native relation (empty `sub_issues`, a `## Stories`
        section), so the read falls to tier 2 and says so — that's what tells the router there are
        checkboxes to reconcile (skills/_shared/epic-story-hierarchy.md)."""
        envelope = self._envelope(issue=100, fixture_case="prep_drafter_epic_revise")
        self.assertEqual(envelope["epic_revise"]["stories_source"], "checklist")

    def test_epic_revise_native_relation_reports_sub_issues_source(self):
        """An epic carrying the native relation: the story set comes from `sub_issues`, live state
        rides along with it, and `checked` mirrors that state so a checkbox/live-state mismatch is
        unrepresentable. The fixture omits the per-story `gh issue view` entries entirely, so a
        regression into per-story fetching fails as a shim MISS rather than passing quietly."""
        envelope = self._envelope(issue=100, fixture_case="prep_drafter_epic_revise_native")
        self.assertEqual(envelope["epic_revise"]["stories_source"], "sub-issues")
        stories = {s["number"]: s for s in envelope["epic_revise"]["stories"]}
        self.assertEqual(sorted(stories), [101, 102])
        self.assertEqual(stories[101]["state"], "CLOSED")
        self.assertTrue(stories[101]["checked"])
        self.assertEqual(stories[102]["state"], "OPEN")
        self.assertFalse(stories[102]["checked"])
        # Nothing to reconcile, so no mismatch lines.
        self.assertFalse([line for line in envelope["attention"] if "checkbox" in line])

    def test_epic_revise_checkbox_live_state_mismatch_surfaces_attention(self):
        envelope = self._envelope(issue=100, fixture_case="prep_drafter_epic_revise")
        self.assertTrue(
            any("story #103" in line and "checked" in line and "OPEN" in line for line in envelope["attention"]),
            envelope["attention"],
        )
        # #101/#102 agree with live state — no mismatch line for either.
        self.assertFalse(any("story #101" in line for line in envelope["attention"]))
        self.assertFalse(any("story #102" in line for line in envelope["attention"]))


# ---------------------------------------------------------------------------
# Revise facts: plan presence, open-PR wiring, extra-json fold-in, closed-target attention.
# ---------------------------------------------------------------------------


class ReviseFactsTests(PrepDrafterSandboxTestCase):
    def test_plan_present_is_staged_and_flagged(self):
        envelope = self._envelope(issue=304, fixture_case="prep_drafter_revise_plan_present")
        plan = envelope["revise"]["plan"]
        self.assertTrue(plan["present"])
        self.assertIsNotNone(plan.get("comment_url"))
        self.assertIn("implementation-plan:v1", plan.get("body") or (plan.get("body_mode") and ""))

    def test_open_pr_and_extra_json_surface_in_revise_facts(self):
        envelope = self._envelope(issue=302, fixture_case="prep_drafter_revise_with_open_pr")
        open_prs = envelope["revise"]["open_prs"]
        self.assertEqual(len(open_prs), 1)
        self.assertEqual(open_prs[0]["number"], 303)
        self.assertEqual(open_prs[0]["headRefName"], "302-feature")
        self.assertEqual(envelope["revise"]["project_items"], [{"id": "PVTI_1"}])

    def test_closed_target_surfaces_attention(self):
        envelope = self._envelope(issue=305, fixture_case="prep_drafter_revise_closed_target")
        self.assertEqual(envelope["target"]["state"], "CLOSED")
        self.assertTrue(
            any("#305" in line and "closed" in line for line in envelope["attention"]), envelope["attention"]
        )


# ---------------------------------------------------------------------------
# DoD box 2: OQ candidate search fixtures — match and no-match.
# ---------------------------------------------------------------------------


class OpenQuestionTrackerSearchTests(PrepDrafterSandboxTestCase):
    def test_seeded_tracker_match_surfaces_the_candidate(self):
        envelope = self._envelope(issue=500, fixture_case="prep_drafter_oq_match")
        self.assertEqual(len(envelope["open_questions"]), 1)
        self.assertEqual(envelope["open_questions"][0]["question"], "(not filed)")
        self.assertEqual(len(envelope["open_question_candidates"]), 1)
        group = envelope["open_question_candidates"][0]
        self.assertEqual(group["oq_id"], "tag case sensitivity")
        self.assertEqual(group["candidates"][0]["number"], 51)
        self.assertTrue(
            any("tag case sensitivity" in line and "do not record it as (not filed)" in line
                for line in envelope["attention"]),
            envelope["attention"],
        )

    def test_no_match_leaves_not_filed_path_legitimately_open(self):
        envelope = self._envelope(issue=501, fixture_case="prep_drafter_oq_no_match")
        self.assertEqual(len(envelope["open_questions"]), 1)
        self.assertEqual(envelope["open_question_candidates"], [])
        self.assertEqual(envelope["attention"], [])


class OqQueryOneShotTests(PrepDrafterSandboxTestCase):
    """The `new`-mode one-shot `--oq-query` lookup (mirrors prep_planner.py's identical mechanism,
    now shared via oq_tracker.build_oq_query)."""

    def test_oq_query_emits_candidates_without_full_facts(self):
        result = self._run(
            ["octo/widgets", "--oq-query", "cache eviction policy"],
            fixture_case="prep_drafter_oq_query",
        )
        self.assertEqual(result.returncode, 0, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "ok")
        self.assertNotIn("vector", envelope)
        self.assertNotIn("suggested_playbook", envelope)
        self.assertIn("oq_query_candidates", envelope)
        groups = envelope["oq_query_candidates"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["query"], "cache eviction policy")
        self.assertEqual(groups[0]["candidates"][0]["number"], 88)

    def test_oq_query_ignores_issue_when_both_given(self):
        # --oq-query short-circuits regardless of --issue, mirroring prep_planner.py's contract.
        result = self._run(
            ["octo/widgets", "--issue", "999", "--oq-query", "cache eviction policy"],
            fixture_case="prep_drafter_oq_query",
        )
        self.assertEqual(result.returncode, 0, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        self.assertIn("oq_query_candidates", envelope)

    def test_oq_query_empty_list_makes_no_call(self):
        payload, notices, decision = prep_drafter.oq_tracker.build_oq_query("octo/widgets", [], cwd=None)
        self.assertIsNone(decision)
        self.assertEqual(payload, {"repo": "octo/widgets", "oq_query_candidates": []})
        self.assertEqual(notices, [])


# ---------------------------------------------------------------------------
# DoD box 3: template/label inventory correct on present/absent fixtures.
# ---------------------------------------------------------------------------


class TemplateInventoryTests(PrepDrafterSandboxTestCase):
    def test_templates_absent(self):
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        templates = envelope["repo_context"]["templates"]
        self.assertFalse(templates["present"])
        self.assertEqual(templates["files"], [])

    def test_templates_present(self):
        _write(self.root / ".github" / "ISSUE_TEMPLATE" / "bug.md", "# Bug template\n")
        _write(self.root / ".github" / "ISSUE_TEMPLATE" / "story.md", "# Story template\n")
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        templates = envelope["repo_context"]["templates"]
        self.assertTrue(templates["present"])
        self.assertEqual(templates["files"], ["bug.md", "story.md"])
        self.assertIn(str(self.root), templates["dir"])


class LabelInventoryTests(PrepDrafterSandboxTestCase):
    def test_labels_present_are_reported_verbatim(self):
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        names = {label["name"] for label in envelope["repo_context"]["labels"]}
        self.assertEqual(names, {"bug", "question", "audience:developer"})

    def test_labels_absent_reports_empty_list(self):
        # An empty `gh label list` result is a legitimate "no labels yet" repo, not an error.
        envelope = self._envelope(fixture_case="prep_drafter_labels_absent")
        self.assertEqual(envelope["repo_context"]["labels"], [])


class GroundingDocInventoryTests(PrepDrafterSandboxTestCase):
    def test_no_docs_present(self):
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        docs = envelope["repo_context"]["docs"]
        self.assertFalse(docs["prd"]["present"])
        self.assertEqual(
            docs["prd"]["candidates_checked"], ["docs/prd.md", "docs/PRD.md", "PRD.md", "prd.md"]
        )
        self.assertFalse(docs["architecture"]["present"])
        self.assertFalse(docs["constitution"]["present"])
        self.assertFalse(docs["claude_md"]["present"])

    def test_prd_variant_path_first_match_wins(self):
        _write(self.root / "PRD.md", "# PRD\n")
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        prd = envelope["repo_context"]["docs"]["prd"]
        self.assertTrue(prd["present"])
        self.assertTrue(prd["path"].endswith("PRD.md"))

    def test_canonical_prd_path_wins_over_a_later_candidate(self):
        _write(self.root / "docs" / "prd.md", "# canonical PRD\n")
        _write(self.root / "PRD.md", "# should not win\n")
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        prd = envelope["repo_context"]["docs"]["prd"]
        self.assertTrue(prd["path"].endswith("docs/prd.md"))

    def test_architecture_constitution_claude_md_present(self):
        _write(self.root / "docs" / "architecture.md", "# Architecture\n")
        _write(self.root / "docs" / "constitution.md", "# Constitution\n")
        _write(self.root / "CLAUDE.md", "# hi\n")
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        docs = envelope["repo_context"]["docs"]
        self.assertTrue(docs["architecture"]["present"])
        self.assertTrue(docs["constitution"]["present"])
        self.assertTrue(docs["claude_md"]["present"])


# ---------------------------------------------------------------------------
# OQ marker config block (present / absent -> heuristics fallback).
# ---------------------------------------------------------------------------


class OqMarkerConfigBlockTests(PrepDrafterSandboxTestCase):
    def test_absent_activates_heuristics(self):
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        self.assertFalse(envelope["config"]["oq_markers"]["present"])
        self.assertIsNone(envelope["config"]["oq_markers"]["raw"])
        self.assertTrue(envelope["config"]["heuristics_active"])

    def test_present_surfaces_raw_block_and_disables_heuristics(self):
        _write(
            self.root / "CLAUDE.md",
            "\n<!-- drafter-open-question-markers -->\n"
            "- register: `docs/open-questions.md`\n"
            "- inline-pattern: `\\[OPEN QUESTION\\]`\n"
            "- open-status: unresolved\n"
            "<!-- /drafter-open-question-markers -->\n",
        )
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        config = envelope["config"]
        self.assertTrue(config["oq_markers"]["present"])
        self.assertIn("docs/open-questions.md", config["oq_markers"]["raw"])
        self.assertFalse(config["heuristics_active"])
        self.assertIn(str(self.root), config["oq_markers"]["source"])


# ---------------------------------------------------------------------------
# root facts.
# ---------------------------------------------------------------------------


class RootFactsTests(PrepDrafterSandboxTestCase):
    def test_root_facts_shape_has_no_freshness_gate(self):
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        root = envelope["root"]
        self.assertEqual(set(root.keys()), {"path", "sha"})
        self.assertEqual(len(root["sha"]), 40)

    def test_root_sha_reflects_the_actual_head_no_fetch_no_ff_merge(self):
        # Unlike prep_planner.py / prep_resolver.py / prep_evaluator.py, this prep never fetches
        # or fast-forwards root — a commit made AFTER clone (never pushed) is what `root.sha`
        # reports, proving no root-freshness protocol runs here.
        _write(self.root / "local-only.txt", "not pushed anywhere\n")
        _git(["add", "local-only.txt"], self.root)
        _git(["commit", "-m", "local-only commit"], self.root)
        local_sha = _git(["rev-parse", "HEAD"], self.root)
        envelope = self._envelope(fixture_case="prep_drafter_new_happy")
        self.assertEqual(envelope["root"]["sha"], local_sha)


# ---------------------------------------------------------------------------
# DoD box 4a: decision codes.
# ---------------------------------------------------------------------------


class DecisionCodeTests(PrepDrafterSandboxTestCase):
    def test_auth_required_on_labels_call(self):
        result = self._run(["octo/widgets"], fixture_case="prep_drafter_auth_required_labels")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AUTH_REQUIRED")

    def test_auth_required_on_epic_revise_story_state_fetch(self):
        result = self._run(
            ["octo/widgets", "--issue", "200"], fixture_case="prep_drafter_auth_required_story_state"
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AUTH_REQUIRED")

    def test_duplicate_plan_comments_yields_marker_ambiguous(self):
        result = self._run(
            ["octo/widgets", "--issue", "601"], fixture_case="prep_drafter_marker_ambiguous"
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "MARKER_AMBIGUOUS")

    def test_malformed_open_questions_section_yields_ambiguous(self):
        result = self._run(
            ["octo/widgets", "--issue", "502"], fixture_case="prep_drafter_oq_malformed"
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")


# ---------------------------------------------------------------------------
# DoD box 4b: conformance + call budget (two-sided: new mode is a strict lower bound, epic-revise
# with N filed stories is a strict upper bound relative to the standalone-revise canonical path).
# ---------------------------------------------------------------------------


class SingleInvocationBudgetTests(PrepDrafterSandboxTestCase):
    def test_new_mode_call_count_is_exactly_one(self):
        result = self._run(["octo/widgets"], fixture_case="prep_drafter_new_happy")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        manifest = json.loads(
            (shimenv.fixture_case_dir("prep_drafter_new_happy") / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(manifest), 1)

    def test_revise_mode_call_count_is_exactly_five(self):
        result = self._run(
            ["octo/widgets", "--issue", "300"], fixture_case="prep_drafter_revise_standard"
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        manifest = json.loads(
            (shimenv.fixture_case_dir("prep_drafter_revise_standard") / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(manifest), 5)
        self.assertGreater(len(manifest), 1, "revise mode must cost strictly more than new mode")

    def test_epic_revise_with_filed_stories_costs_strictly_more_than_standalone_revise(self):
        result = self._run(
            ["octo/widgets", "--issue", "100"], fixture_case="prep_drafter_epic_revise"
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        manifest = json.loads(
            (shimenv.fixture_case_dir("prep_drafter_epic_revise") / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        # 5 (gather + labels) + 3 filed-story state fetches (#101/#102/#103) = 8.
        self.assertEqual(len(manifest), 8)
        self.assertGreater(len(manifest), 5)

    def test_no_gh_call_is_repeated_within_one_run(self):
        for case in ("prep_drafter_new_happy", "prep_drafter_revise_standard", "prep_drafter_epic_revise"):
            manifest = json.loads(
                (shimenv.fixture_case_dir(case) / "manifest.json").read_text(encoding="utf-8")
            )
            argv_tuples = [tuple(entry["argv"]) for entry in manifest]
            self.assertEqual(
                len(argv_tuples), len(set(argv_tuples)), "duplicate argv in manifest for %s" % case
            )


# ---------------------------------------------------------------------------
# Pure-helper unit tests — no subprocess, no shim, no git sandbox needed.
# ---------------------------------------------------------------------------


class PureHelperUnitTests(unittest.TestCase):
    def test_detect_type_epic_by_label(self):
        self.assertEqual(prep_drafter._detect_type(["epic"], "Epic: x"), "epic")

    def test_detect_type_epic_by_title_prefix_case_insensitive(self):
        self.assertEqual(prep_drafter._detect_type([], "EPIC: something big"), "epic")

    def test_detect_type_story_by_label(self):
        self.assertEqual(prep_drafter._detect_type(["story"], "Add a thing"), "story")

    def test_detect_type_question_by_label(self):
        self.assertEqual(prep_drafter._detect_type(["question", "audience:business"], "Q?"), "question")

    def test_detect_type_standard_default(self):
        self.assertEqual(prep_drafter._detect_type(["bug"], "Fix the thing"), "standard")

    def test_suggested_playbook_new(self):
        self.assertEqual(prep_drafter._suggested_playbook("new", None), "new.md")

    def test_suggested_playbook_epic_revise(self):
        self.assertEqual(prep_drafter._suggested_playbook("epic-revise", "epic"), "epic-split.md")

    def test_suggested_playbook_revise_question(self):
        self.assertEqual(prep_drafter._suggested_playbook("revise", "question"), "question.md")

    def test_suggested_playbook_revise_standard(self):
        self.assertEqual(prep_drafter._suggested_playbook("revise", "standard"), "revise.md")

    def test_suggested_playbook_revise_story(self):
        # Story revise shares the standalone revise flow (SKILL.md's "Special case — revising a
        # Story" is a special case WITHIN Revise mode, not its own playbook).
        self.assertEqual(prep_drafter._suggested_playbook("revise", "story"), "revise.md")

    def test_parse_stories_section_filed_and_placeholder(self):
        body = (
            "## Stories\n- [x] #1 — Story A\n- [ ] #2 — Story B\n- [ ] Story C placeholder\n"
        )
        entries = prep_drafter._parse_stories_section(body)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0], {"number": 1, "title": "Story A", "checked": True})
        self.assertEqual(entries[1], {"number": 2, "title": "Story B", "checked": False})
        self.assertEqual(entries[2], {"number": None, "title": "Story C placeholder", "checked": False})

    def test_parse_stories_section_absent(self):
        self.assertEqual(prep_drafter._parse_stories_section("no stories section here"), [])

    def test_parse_stories_section_stops_at_next_heading(self):
        body = "## Stories\n- [ ] #1 — Story A\n\n## Definition of done\n- [ ] Not a story\n"
        entries = prep_drafter._parse_stories_section(body)
        self.assertEqual(len(entries), 1)

    def test_prd_presence_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = prep_drafter._prd_presence(tmp)
            self.assertFalse(result["present"])
            self.assertIsNone(result["path"])

    def test_prd_presence_canonical_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(Path(tmp) / "docs" / "prd.md", "# PRD\n")
            result = prep_drafter._prd_presence(tmp)
            self.assertTrue(result["present"])
            self.assertTrue(result["path"].endswith("docs/prd.md"))

    def test_template_inventory_absent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = prep_drafter._template_inventory(tmp)
            self.assertFalse(result["present"])
            self.assertEqual(result["files"], [])

    def test_template_inventory_empty_dir_reports_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
            result = prep_drafter._template_inventory(tmp)
            self.assertFalse(result["present"])

    def test_build_attention_closed_target_only_for_revise_modes(self):
        target = {"number": 9, "state": "CLOSED"}
        self.assertEqual(prep_drafter._build_attention([], target, "revise"), [
            "target issue #9 is closed — resolve the 'Closed issue' gate before revising"
        ])
        self.assertEqual(prep_drafter._build_attention([], target, "new"), [])


class UsageErrorTests(unittest.TestCase):
    def test_missing_repo_arg_is_usage_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, encoding="utf-8", check=False
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
