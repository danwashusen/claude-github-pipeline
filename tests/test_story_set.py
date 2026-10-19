"""Unit tests for scripts/story_set.py — an epic's story set through
``skills/_shared/epic-story-hierarchy.md``'s two-tier read.

This module is **pure** — sub-issue nodes and a body string in, a value out; the one live read is
injected as ``fetch_state`` — so every test drives it in-process with no `gh`, no shim and no
sandbox. Four preps compose it (planner, slicer, evaluator, coordinator), each projecting the result
onto the facts shape it already reported; their own suites pin those projections.

What this suite exists to protect:

  - **The union.** Native first, in panel order (delivery order); the checklist's bullets after, in
    source order; a bullet for an already-native story dropped as a stale duplicate, native state
    winning. Taking one tier and dropping the other silently loses stories.
  - **Placeholders survive the read.** An unfiled bullet is a cut's input, so ``read`` keeps it and
    only :func:`story_set.filed` / :func:`story_set.closed_view` drop it.
  - **The fetch is the caller's.** Only filed checklist-only stories are fetched, never a native
    one, and the first decision comes back as-is with no story set.
  - **``source`` is the contract's vocabulary**, with no default of its own for an empty set.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

import story_set  # noqa: E402


def node(number, state="OPEN", title=None):
    return {"number": number, "title": title or "Story %d" % number, "state": state}


class ReadTests(unittest.TestCase):
    def test_native_entries_mirror_live_state_in_panel_order(self):
        result, decision = story_set.read([node(153, "CLOSED"), node(151)], "")
        self.assertIsNone(decision)
        self.assertEqual(
            result["native"],
            [
                {"number": 153, "title": "Story 153", "state": "CLOSED", "checked": True, "live_title": "Story 153"},
                {"number": 151, "title": "Story 151", "state": "OPEN", "checked": False, "live_title": "Story 151"},
            ],
        )
        self.assertEqual(result["checklist"], [])
        self.assertEqual(result["checklist_raw"], [])

    def test_a_checklist_bullet_for_a_native_story_is_dropped_native_state_winning(self):
        body = "## Stories\n- [x] #11 — Stale title\n- [ ] #12 — B\n"
        result, _decision = story_set.read([node(11, "OPEN", "A")], body)
        self.assertEqual([e["number"] for e in result["native"]], [11])
        self.assertFalse(result["native"][0]["checked"], "the stale checkbox never overrides live state")
        self.assertEqual([e["number"] for e in result["checklist"]], [12])
        self.assertEqual([e["number"] for e in result["checklist_raw"]], [11, 12])

    def test_placeholders_are_kept_in_source_order(self):
        body = "## Stories\n- [ ] Login\n- [x] #4 — D\n- [x] Signup\n"
        result, _decision = story_set.read([], body)
        self.assertEqual(
            [(e["number"], e["title"], e["checked"]) for e in result["checklist"]],
            [(None, "Login", False), (4, "D", True), (None, "Signup", True)],
        )

    def test_without_a_fetch_checklist_state_is_unknown(self):
        result, _decision = story_set.read([], "## Stories\n- [x] #4 — D\n")
        self.assertIsNone(result["checklist"][0]["state"])
        self.assertIsNone(result["checklist"][0]["live_title"])

    def test_the_fetch_runs_only_for_filed_checklist_only_stories(self):
        fetched = []

        def fetch(number):
            fetched.append(number)
            return {"state": "CLOSED", "title": "Live %d" % number}, None

        body = "## Stories\n- [ ] #11 — A\n- [ ] Later\n- [ ] #12 — B\n"
        result, decision = story_set.read([node(11)], body, fetch_state=fetch)
        self.assertIsNone(decision)
        self.assertEqual(fetched, [12])
        self.assertEqual(
            result["checklist"],
            [
                {"number": None, "title": "Later", "state": None, "checked": False, "live_title": None},
                {"number": 12, "title": "B", "state": "CLOSED", "checked": False, "live_title": "Live 12"},
            ],
        )

    def test_the_first_fetch_decision_comes_back_as_is(self):
        sentinel = {"code": "AUTH_REQUIRED"}
        calls = []

        def fetch(number):
            calls.append(number)
            return None, sentinel

        result, decision = story_set.read([], "## Stories\n- [ ] #3 — C\n- [ ] #4 — D\n", fetch_state=fetch)
        self.assertIsNone(result)
        self.assertIs(decision, sentinel)
        self.assertEqual(calls, [3], "nothing is fetched after a decision")

    def test_no_section_and_no_sub_issues_is_empty_not_an_error(self):
        for body in ("", None, "## Goal\nx\n"):
            result, decision = story_set.read(None, body)
            self.assertIsNone(decision)
            self.assertEqual(result, {"native": [], "checklist": [], "checklist_raw": []})


class SourceTests(unittest.TestCase):
    def test_the_closed_vocabulary(self):
        self.assertEqual(story_set.source([1], [2]), "mixed")
        self.assertEqual(story_set.source([1], []), "sub-issues")
        self.assertEqual(story_set.source([], [2]), "checklist")

    def test_no_stories_has_no_source_of_its_own(self):
        self.assertIsNone(story_set.source([], []))

    def test_a_checklist_wholly_covered_natively_is_not_mixed_on_the_deduped_half(self):
        result, _decision = story_set.read([node(11)], "## Stories\n- [ ] #11 — A\n")
        self.assertEqual(story_set.source(result["native"], result["checklist"]), "sub-issues")
        self.assertEqual(story_set.source(result["native"], result["checklist_raw"]), "mixed")


class ViewTests(unittest.TestCase):
    def test_filed_drops_placeholders(self):
        result, _decision = story_set.read([], "## Stories\n- [ ] Login\n- [ ] #4 — D\n")
        self.assertEqual([e["number"] for e in story_set.filed(result["checklist"])], [4])

    def test_closed_view_unions_filed_stories_with_the_checkbox_as_closed(self):
        body = "## Stories\n- [ ] #11 — A\n- [x] #4 — D\n- [ ] Later\n"
        result, _decision = story_set.read([node(11, "CLOSED", "A")], body)
        self.assertEqual(
            story_set.closed_view(result),
            [
                {"number": 11, "title": "A", "state": "CLOSED", "closed": True},
                {"number": 4, "title": "D", "state": None, "closed": True},
            ],
        )


if __name__ == "__main__":
    unittest.main()
