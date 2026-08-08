"""Unit tests for scripts/prep_slicer.py — the slicer's facts block in one call (#17;
architecture.md §4).

Two strategies, matching the sibling prep suites:

  - **Pure-core unit tests** call the module's own non-emitting helpers directly (type detection,
    the slice set, the refusal set, the blocker filters) — fast, and they pin the exact arithmetic
    without a subprocess.
  - **Subprocess tests** drive `prep_slicer.py` as a real process against the fixture-replaying `gh`
    shim, proving the envelope contract and the one-round-trip budget end to end.

What this suite exists to protect:

  - **The refusal set is a fact, not a decision code.** Five conditions must land in
    `vector.refusals` with `suggested_playbook: None`, never as a `needs_decision` — a refusal is a
    routing outcome with its own handoff, not a one-card question.
  - **Resume, don't duplicate.** `next_index` must OVER-count rather than risk re-issuing a live
    designator, including when a child was hand-retitled out of the `<N>/S<K>` form.
  - **The slice-target guard.** The by-construction identification rule (a non-epic's sub-issues are
    slices) only holds if nothing ever slices a slice, so the parent-type check is load-bearing.
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
SCRIPT = SCRIPTS_DIR / "prep_slicer.py"

sys.path.insert(0, str(SCRIPTS_DIR))

import prep_slicer  # noqa: E402  (import after sys.path setup, by necessity)
from pipelib.decisions import DOC_CATALOGUE_ABSENT  # noqa: E402
from tests.support import envelope_asserts, gitsandbox, shimenv  # noqa: E402

CATALOGUE_INTERIOR = "- `docs/prd.md` — prd — binding — What the product is.\n"


def _write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _parse_one_envelope(stdout_text):
    lines = [line for line in stdout_text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise AssertionError(
            "expected exactly one non-blank stdout line (the envelope), got %d: %r"
            % (len(lines), lines)
        )
    return json.loads(lines[0])


# ---------------------------------------------------------------------------
# Pure cores
# ---------------------------------------------------------------------------


class TypeDetectionTests(unittest.TestCase):
    """`branching.detect_type` widened by one `question` arm — the shared core keeps its precedence."""

    def test_shared_core_arms_pass_through(self):
        self.assertEqual(prep_slicer._detect_type(["epic"], "x"), "epic")
        self.assertEqual(prep_slicer._detect_type(["story"], "x"), "story")
        self.assertEqual(prep_slicer._detect_type([], "Epic: onboarding"), "epic")
        self.assertEqual(prep_slicer._detect_type([], "plain title"), "standard")

    def test_question_label_wins_over_the_standard_fallback_only(self):
        self.assertEqual(prep_slicer._detect_type(["question"], "x"), "question")
        # A pathologically double-labelled issue keeps the shared core's documented precedence.
        self.assertEqual(prep_slicer._detect_type(["epic", "question"], "x"), "epic")
        self.assertEqual(prep_slicer._detect_type(["story", "question"], "x"), "story")


class SliceSetTests(unittest.TestCase):
    def test_empty_child_set_starts_at_one(self):
        result = prep_slicer._build_slice_set([], 103)
        self.assertEqual(result, {"entries": [], "count": 0, "open_count": 0, "next_index": 1})

    def test_designators_parsed_and_open_count_derived(self):
        subs = [
            {"number": 104, "title": "103/S1 — first login", "state": "CLOSED"},
            {"number": 105, "title": "103/S2 — password reset", "state": "OPEN"},
        ]
        result = prep_slicer._build_slice_set(subs, 103)
        self.assertEqual([e["designator_index"] for e in result["entries"]], [1, 2])
        self.assertEqual(result["open_count"], 1)
        self.assertEqual(result["next_index"], 3)

    def test_next_index_over_counts_when_a_child_was_hand_retitled(self):
        """The trap: with 3 children whose highest PARSED index is 2, continuing from the parsed
        highest alone would re-issue S3 — which may be exactly the renamed child."""
        subs = [
            {"number": 104, "title": "103/S1 — a", "state": "CLOSED"},
            {"number": 105, "title": "103/S2 — b", "state": "OPEN"},
            {"number": 106, "title": "renamed, was 103/S3", "state": "OPEN"},
        ]
        self.assertEqual(prep_slicer._build_slice_set(subs, 103)["next_index"], 4)

    def test_a_designator_naming_another_parent_is_not_counted(self):
        subs = [{"number": 9, "title": "999/S9 — someone else's slice", "state": "OPEN"}]
        result = prep_slicer._build_slice_set(subs, 103)
        self.assertIsNone(result["entries"][0]["designator_index"])
        self.assertEqual(result["next_index"], 2)

    def test_panel_order_is_preserved(self):
        """Creation order IS delivery order, so the entry list must not be re-sorted."""
        subs = [
            {"number": 106, "title": "103/S3 — c", "state": "OPEN"},
            {"number": 104, "title": "103/S1 — a", "state": "OPEN"},
        ]
        result = prep_slicer._build_slice_set(subs, 103)
        self.assertEqual([e["number"] for e in result["entries"]], [106, 104])


class RefusalTests(unittest.TestCase):
    def test_no_refusal_for_a_story_under_an_epic(self):
        self.assertEqual(
            prep_slicer._build_refusals("story", "OPEN", {"type": "epic"}, [], []), []
        )

    def test_no_refusal_for_a_standalone_non_epic_issue(self):
        self.assertEqual(prep_slicer._build_refusals("standard", "OPEN", None, [], []), [])

    def test_epic_target_refused(self):
        self.assertEqual(
            prep_slicer._build_refusals("epic", "OPEN", None, [], []),
            [prep_slicer.REFUSAL_EPIC_TARGET],
        )

    def test_slice_target_refused_when_the_parent_is_not_an_epic(self):
        """Never slice a slice — the guard the by-construction identification rule depends on."""
        for parent_type in ("story", "standard"):
            self.assertEqual(
                prep_slicer._build_refusals("standard", "OPEN", {"type": parent_type}, [], []),
                [prep_slicer.REFUSAL_SLICE_TARGET],
                parent_type,
            )

    def test_question_and_closed_targets_refused(self):
        self.assertIn(
            prep_slicer.REFUSAL_QUESTION_TARGET,
            prep_slicer._build_refusals("question", "OPEN", None, [], []),
        )
        self.assertIn(
            prep_slicer.REFUSAL_CLOSED_TARGET,
            prep_slicer._build_refusals("standard", "CLOSED", None, [], []),
        )

    def test_blocked_from_either_a_native_blocker_or_an_in_scope_oq(self):
        self.assertEqual(
            prep_slicer._build_refusals("standard", "OPEN", None, [{"number": 61}], []),
            [prep_slicer.REFUSAL_BLOCKED],
        )
        self.assertEqual(
            prep_slicer._build_refusals("standard", "OPEN", None, [], [{"oq_id": "OQ-1"}]),
            [prep_slicer.REFUSAL_BLOCKED],
        )

    def test_refusal_order_is_stable_for_deterministic_rendering(self):
        refusals = prep_slicer._build_refusals(
            "epic", "CLOSED", {"type": "story"}, [{"number": 61}], []
        )
        self.assertEqual(
            refusals,
            [
                prep_slicer.REFUSAL_EPIC_TARGET,
                prep_slicer.REFUSAL_SLICE_TARGET,
                prep_slicer.REFUSAL_CLOSED_TARGET,
                prep_slicer.REFUSAL_BLOCKED,
            ],
        )


class BlockerFilterTests(unittest.TestCase):
    def test_only_open_native_blockers_gate(self):
        """A closed blocker is a stale recorded claim, not a gate — live state decides."""
        nodes = [
            {"number": 61, "state": "OPEN", "title": "Which PSP?", "url": "u1"},
            {"number": 62, "state": "CLOSED", "title": "Answered", "url": "u2"},
        ]
        self.assertEqual([b["number"] for b in prep_slicer._open_blockers(nodes)], [61])

    def test_only_in_scope_blocked_oq_entries_gate(self):
        entries = [
            {"oq_id": "OQ-1", "disposition": "in-scope (blocked)", "question": "#61"},
            {"oq_id": "OQ-2", "disposition": "scoped-out", "question": "#62"},
            {"oq_id": "OQ-3", "disposition": "provisional-default", "question": "#63"},
        ]
        self.assertEqual(
            [e["oq_id"] for e in prep_slicer._in_scope_blocked_oqs(entries)], ["OQ-1"]
        )


class SuggestedPlaybookTests(unittest.TestCase):
    def test_one_playbook_when_nothing_is_refused(self):
        self.assertEqual(prep_slicer._suggested_playbook([]), "cut.md")

    def test_a_refusal_routes_to_no_playbook(self):
        self.assertIsNone(prep_slicer._suggested_playbook([prep_slicer.REFUSAL_EPIC_TARGET]))


# ---------------------------------------------------------------------------
# Subprocess / envelope
# ---------------------------------------------------------------------------


class PrepSlicerSandboxTestCase(unittest.TestCase):
    """A real temp git origin+clone as `--root` (needed for `git rev-parse HEAD`), pre-seeded with a
    doc catalogue so the grounding dimension is neutral in tests that aren't about grounding."""

    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path
        self._seed_catalogue()
        _write(self.root / "docs" / "prd.md", "# PRD\n")
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.scratch = self._tmp_ctx.name
        self.addCleanup(self._tmp_ctx.cleanup)

    def _seed_catalogue(self, interior=CATALOGUE_INTERIOR):
        _write(
            self.root / "docs" / "README.md",
            "# Docs\n\n<!-- doc-catalogue -->\n%s<!-- /doc-catalogue -->\n" % interior,
        )

    def _remove_catalogue(self):
        (self.root / "docs" / "README.md").unlink()

    def _run(self, args, fixture_case=None):
        env = shimenv.intercepted_env(base_env=os.environ, fixture_case=fixture_case)
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + args,
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def _envelope(self, issue, fixture_case, repo="octo/widgets", extra_args=None):
        args = [str(issue), repo, "--root", str(self.root), "--scratch-dir", self.scratch]
        if extra_args:
            args += extra_args
        result = self._run(args, fixture_case=fixture_case)
        self.assertEqual(result.returncode, 0, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        return envelope


class ScriptShapeTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(str(SCRIPT), os.X_OK), "a 0644 prep exits 126 at dispatch")

    def test_usage_error_exits_two_with_no_envelope(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, encoding="utf-8", check=False
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")


class FreshHappyPathTests(PrepSlicerSandboxTestCase):
    def test_facts_schema(self):
        envelope = self._envelope(103, "prep_slicer_fresh")
        for key in (
            "repo",
            "scratch",
            "root",
            "target",
            "vector",
            "suggested_playbook",
            "slices",
            "grounding_docs",
            "research",
            "open_questions",
            "sections",
            "attention",
        ):
            self.assertIn(key, envelope, key)
        self.assertEqual(envelope["vector"], {"type": "story", "mode": "fresh", "refusals": []})
        self.assertEqual(envelope["suggested_playbook"], "cut.md")
        self.assertEqual(envelope["slices"]["count"], 0)
        self.assertEqual(envelope["slices"]["next_index"], 1)
        self.assertEqual(envelope["attention"], [])
        self.assertEqual(envelope["notices"], [])

    def test_parent_epic_is_typed_from_its_own_labels(self):
        """The relation's node shape carries no labels, so the parent needs its own lookup."""
        envelope = self._envelope(103, "prep_slicer_fresh")
        self.assertEqual(envelope["target"]["parent"]["number"], 150)
        self.assertEqual(envelope["target"]["parent"]["type"], "epic")

    def test_catalogue_entries_land_as_grounding_docs(self):
        envelope = self._envelope(103, "prep_slicer_fresh")
        self.assertEqual([e["path"] for e in envelope["grounding_docs"]], ["docs/prd.md"])
        self.assertTrue(envelope["grounding_docs"][0]["present"])

    def test_body_and_thread_are_spilled_into_sections(self):
        envelope = self._envelope(103, "prep_slicer_fresh")
        self.assertTrue(
            any(k.startswith("issue_body") for k in envelope["sections"]), envelope["sections"]
        )


class StandaloneTargetTests(PrepSlicerSandboxTestCase):
    def test_a_parentless_non_epic_issue_is_sliceable_with_no_parent_lookup(self):
        envelope = self._envelope(200, "prep_slicer_standalone")
        self.assertEqual(envelope["vector"]["refusals"], [])
        self.assertEqual(envelope["vector"]["type"], "standard")
        self.assertIsNone(envelope["target"]["parent"])


class ResumeModeTests(PrepSlicerSandboxTestCase):
    def test_existing_sub_issues_switch_the_mode_and_carry_the_numbering(self):
        envelope = self._envelope(103, "prep_slicer_resume")
        self.assertEqual(envelope["vector"]["mode"], "resume")
        self.assertEqual(envelope["suggested_playbook"], "cut.md")
        self.assertEqual(envelope["slices"]["count"], 2)
        self.assertEqual(envelope["slices"]["open_count"], 1)
        self.assertEqual(envelope["slices"]["next_index"], 3)

    def test_resume_raises_an_attention_line_so_nothing_re_files_silently(self):
        envelope = self._envelope(103, "prep_slicer_resume")
        self.assertTrue(
            any("resume mode" in item for item in envelope["attention"]), envelope["attention"]
        )


class RefusalFactTests(PrepSlicerSandboxTestCase):
    """Every refusal is an `ok` envelope carrying a fact — never a `needs_decision`."""

    def _refusal(self, issue, fixture_case):
        envelope = self._envelope(issue, fixture_case)
        self.assertEqual(envelope["status"], "ok")
        self.assertIsNone(envelope["suggested_playbook"])
        return envelope

    def test_epic_target(self):
        envelope = self._refusal(150, "prep_slicer_epic_target")
        self.assertEqual(envelope["vector"]["refusals"], [prep_slicer.REFUSAL_EPIC_TARGET])
        self.assertTrue(any("is an epic" in i for i in envelope["attention"]))

    def test_slice_target(self):
        envelope = self._refusal(105, "prep_slicer_slice_target")
        self.assertEqual(envelope["vector"]["refusals"], [prep_slicer.REFUSAL_SLICE_TARGET])
        self.assertEqual(envelope["target"]["parent"]["type"], "story")
        self.assertTrue(any("never sliced" in i for i in envelope["attention"]))

    def test_question_target(self):
        envelope = self._refusal(202, "prep_slicer_question")
        self.assertEqual(envelope["vector"]["refusals"], [prep_slicer.REFUSAL_QUESTION_TARGET])

    def test_closed_target(self):
        envelope = self._refusal(203, "prep_slicer_closed")
        self.assertEqual(envelope["vector"]["refusals"], [prep_slicer.REFUSAL_CLOSED_TARGET])

    def test_blocked_target_names_the_open_blocker(self):
        envelope = self._refusal(201, "prep_slicer_blocked")
        self.assertEqual(envelope["vector"]["refusals"], [prep_slicer.REFUSAL_BLOCKED])
        self.assertEqual([b["number"] for b in envelope["target"]["blocked_by"]], [61])
        self.assertTrue(any("#61" in i for i in envelope["attention"]), envelope["attention"])


class GroundingTests(PrepSlicerSandboxTestCase):
    def test_absent_catalogue_is_a_notice_and_an_attention_line_never_a_refusal(self):
        """Prep cannot see operator-named sources, so only the flow may refuse on grounding."""
        self._remove_catalogue()
        envelope = self._envelope(103, "prep_slicer_fresh")
        self.assertEqual(envelope["grounding_docs"], [])
        self.assertIn(DOC_CATALOGUE_ABSENT, envelope["notices"])
        self.assertEqual(envelope["vector"]["refusals"], [])
        self.assertEqual(envelope["suggested_playbook"], "cut.md")
        self.assertTrue(
            any("no doc catalogue" in i for i in envelope["attention"]), envelope["attention"]
        )

    def test_empty_catalogue_is_not_the_absent_notice(self):
        self._seed_catalogue("")
        envelope = self._envelope(103, "prep_slicer_fresh")
        self.assertEqual(envelope["notices"], [])
        self.assertTrue(any("declares no documents" in i for i in envelope["attention"]))

    def test_declared_but_missing_doc_is_surfaced(self):
        self._seed_catalogue(
            "- `docs/prd.md` — prd — binding — What the product is.\n"
            "- `docs/ui-design.md` — ui-design — binding — Not on this ref.\n"
        )
        envelope = self._envelope(103, "prep_slicer_fresh")
        self.assertTrue(
            any("docs/ui-design.md" in i for i in envelope["attention"]), envelope["attention"]
        )


class SingleInvocationBudgetTests(PrepSlicerSandboxTestCase):
    """architecture.md §9.2: one state-assembly invocation per session. The fixture manifest is
    exact-argv matched, so an unexpected extra `gh` call fails the shim loudly — these bounds pin
    that the parent lookup happens exactly once, and only when a parent exists."""

    def test_a_parentless_target_makes_no_parent_lookup(self):
        # `prep_slicer_standalone`'s manifest carries NO parent-view entry; a lookup would miss and
        # the shim would exit 2.
        envelope = self._envelope(200, "prep_slicer_standalone")
        self.assertIsNone(envelope["target"]["parent"])

    def test_a_parented_target_makes_exactly_one_parent_lookup(self):
        envelope = self._envelope(103, "prep_slicer_fresh")
        self.assertEqual(envelope["target"]["parent"]["number"], 150)


class ScratchDirTests(PrepSlicerSandboxTestCase):
    def test_default_scratch_dir_follows_the_house_convention(self):
        """`/tmp/gh-<skill>-<N>/` (architecture.md §9). Asserted on the emitted fact rather than by
        creating the real directory."""
        result = self._run(
            ["103", "octo/widgets", "--root", str(self.root)], fixture_case="prep_slicer_fresh"
        )
        self.assertEqual(result.returncode, 0, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        self.assertEqual(envelope["scratch"], "/tmp/gh-slicer-103")


if __name__ == "__main__":
    unittest.main()
