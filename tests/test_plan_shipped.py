"""Unit tests for scripts/plan_shipped.py — the shipped-phase records' read model and the planner's
staging check (``skills/_shared/plan-shipped-phases.md``).

The read model is pure (literal comment dicts in, a value out); ``check`` is driven both in-process
and once through its CLI so the envelope shape is pinned too.

What this suite protects:

  - **The marker never collides with the plan's.** Every plan lookup is a ``startswith`` on
    ``<!-- implementation-plan:v1 -->``; a record marker that matched it would make the plan itself
    ``MARKER_AMBIGUOUS`` on every issue that has a record.
  - **The (PR, phase) key.** A record belongs to the PR its phase shipped on. A Start-fresh closes
    that PR, and its records must go inert without a delete — so a reader for the new PR must never
    see them.
  - **Verbatim, moved, pointed-to.** ``check`` is the only thing standing between a relocation and a
    silent re-author of already-verified text, so each of its findings gets a case.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

import plan_shipped  # noqa: E402
from pipelib.limits import BODY_CHAR_LIMIT  # noqa: E402

PLAN_MARKER = "<!-- implementation-plan:v1 -->"


def comment(comment_id, body, url=None):
    """A thread comment as ``gh_gather._normalize_comment`` produces it (``id`` = node id,
    ``databaseId`` = the REST numeric id every comment endpoint needs — #34)."""
    return {
        "id": "IC_kwDO%s" % comment_id,
        "databaseId": comment_id,
        "body": body,
        "url": url or "https://github.com/octo/widgets/issues/42#issuecomment-%s" % comment_id,
    }


def record(phase, pr=903, title="Title", changes=("- `a.rb` — adds A",), tests=()):
    lines = [plan_shipped.entry_marker(phase), "**Shipped on:** #%d · Phase %d — %s" % (pr, phase, title), ""]
    if changes:
        lines += ["## Changes (file-level)"] + list(changes) + [""]
    if tests:
        lines += ["## Test plan"] + list(tests) + [""]
    return "\n".join(lines)


PRIOR = "\n".join(
    [
        PLAN_MARKER,
        "**Implementation plan** — #42",
        "",
        "## Architecture decisions",
        "- Decision one.",
        "",
        "## Changes (file-level)",
        "- `a.rb` — adds A",
        "  continuing the A entry",
        "- `b.rb` — adds B",
        "- `c.rb` — adds C",
        "",
        "## Test plan",
        "- Unit:",
        "  - `a_spec.rb` — A works",
        "  - `c_spec.rb` — C works",
        "",
        "## Phases",
        "1. **Phase 1 — A**",
        "   - kind: code-shipping",
    ]
)


def main_after(changes, tests, pointer="- Phase 1 shipped on #903: entries in the shipped-phase records."):
    return "\n".join(
        [PLAN_MARKER, "", "## Changes (file-level)", pointer] + changes
        + ["", "## Test plan", pointer] + tests + [""]
    )


class MarkerTests(unittest.TestCase):
    def test_record_marker_never_starts_with_the_plan_marker(self):
        self.assertFalse(plan_shipped.entry_marker(1).startswith(PLAN_MARKER))
        self.assertFalse(PLAN_MARKER.startswith(plan_shipped.entry_marker(1)))

    def test_no_phase_marker_is_a_prefix_of_another(self):
        self.assertFalse(plan_shipped.entry_marker(10).startswith(plan_shipped.entry_marker(1)))

    def test_head_parses_phase_pr_and_title(self):
        self.assertEqual(plan_shipped.parse_head(record(3, title="Schema")), (3, 903, "Schema"))

    def test_a_marker_below_the_first_line_is_not_a_record(self):
        self.assertIsNone(plan_shipped.parse_head("quoted:\n" + record(3)))

    def test_ascii_separators_still_key(self):
        body = record(3, title="Schema").replace(" · ", " - ").replace(" — ", " - ")
        self.assertEqual(plan_shipped.parse_head(body), (3, 903, "Schema"))

    def test_line_two_naming_another_phase_is_unkeyed(self):
        body = record(3).replace("Phase 3 —", "Phase 4 —")
        self.assertEqual(plan_shipped.parse_head(body), (3, None, None))


class PointerTests(unittest.TestCase):
    """The plan's pointer bullets name whose records hold its missing entries — the authority a
    reader uses once the PR that shipped them has closed. Read leniently (a reworded pointer must not
    hide a closed PR's records), written strictly (`check`'s `malformed_pointer`)."""

    POINTED = "## Changes (file-level)\n- Phases 1–6 shipped on #903: entries in the shipped-phase records.\n"

    def thread(self):
        return [
            comment(11, record(1, pr=903)),
            comment(12, record(2, pr=903)),
            comment(13, record(4, pr=950)),
        ]

    def test_pointer_prs(self):
        self.assertEqual(plan_shipped.pointer_prs(self.POINTED), [903])
        self.assertEqual(plan_shipped.pointer_prs(PRIOR), [])

    def test_a_reworded_pointer_still_resolves(self):
        body = "- Phases 1–3 shipped on #40; see the shipped-phase records for them.\n"
        self.assertEqual(plan_shipped.pointer_prs(body), [40])

    def test_agreeing_pointer_reads_the_open_pr_quietly(self):
        records, notes, decision = plan_shipped.read_pointed(self.thread(), self.POINTED, 903)
        self.assertEqual(records["phases"], [1, 2])
        self.assertEqual(records["foreign_prs"], [])
        self.assertEqual((notes, decision), ([], None))

    def test_a_closed_prs_records_are_still_read(self):
        records, notes, _ = plan_shipped.read_pointed(self.thread(), self.POINTED, None)
        self.assertEqual(records["pr"], 903)
        self.assertEqual(records["foreign_prs"], [903])
        self.assertIn("only copy", notes[0])

    def test_no_pointer_falls_back_to_the_open_pr(self):
        records, notes, _ = plan_shipped.read_pointed(self.thread(), PRIOR, 950)
        self.assertEqual(records["phases"], [4])
        self.assertEqual(notes, [])

    def test_every_pointed_pr_is_read(self):
        # A half-restored plan naming a closed PR and the open one needs both, never one of them.
        body = self.POINTED + self.POINTED.replace("#903", "#950")
        records, notes, _ = plan_shipped.read_pointed(self.thread(), body, 950)
        self.assertEqual(sorted((e["pr"], e["phase"]) for e in records["entries"]), [(903, 1), (903, 2), (950, 4)])
        self.assertIsNone(records["pr"])
        self.assertEqual(records["foreign_prs"], [903])
        self.assertIn("#903", notes[0])

    def test_unkeyed_records_are_noted_even_with_no_open_pr(self):
        thread = self.thread() + [comment(14, record(5).replace("**Shipped on:**", "Shipped:"))]
        records, notes, _ = plan_shipped.read_pointed(thread, self.POINTED, None)
        self.assertEqual(records["unkeyed"][0]["comment_id"], 14)
        self.assertTrue(any("cannot be keyed" in note for note in notes))


class CollectTests(unittest.TestCase):
    def test_reads_this_prs_records_in_phase_order(self):
        thread = [comment(1, PRIOR), comment(12, record(2)), comment(11, record(1))]
        records, decision = plan_shipped.collect(thread, 903)
        self.assertIsNone(decision)
        self.assertEqual(records["phases"], [1, 2])
        self.assertTrue(records["text"].startswith(plan_shipped.entry_marker(1)))

    def test_another_prs_records_are_counted_never_returned(self):
        thread = [comment(11, record(1, pr=800)), comment(12, record(1, pr=903))]
        records, _ = plan_shipped.collect(thread, 903)
        self.assertEqual(records["phases"], [1])
        self.assertEqual(records["other_pr_entries"], 1)

    def test_no_pr_reads_nothing(self):
        records, decision = plan_shipped.collect([comment(11, record(1))], None)
        self.assertFalse(records["present"])
        self.assertIsNone(decision)

    def test_duplicate_phase_is_marker_ambiguous_and_omitted(self):
        thread = [comment(11, record(1)), comment(12, record(1)), comment(13, record(2))]
        records, decision = plan_shipped.collect(thread, 903)
        self.assertEqual(decision["code"], "MARKER_AMBIGUOUS")
        self.assertEqual(decision["context"]["comment_ids"], [11, 12])
        self.assertEqual(records["phases"], [2])

    def test_rest_numeric_id_never_the_graphql_node_id(self):
        records, _ = plan_shipped.collect([comment(11, record(1))], 903)
        self.assertEqual(records["entries"][0]["comment_id"], 11)

    def test_unkeyed_record_is_reported(self):
        body = record(1).replace("**Shipped on:**", "Shipped:")
        records, _ = plan_shipped.collect([comment(11, body)], 903)
        self.assertEqual(records["unkeyed"][0]["comment_id"], 11)
        self.assertFalse(records["present"])


class ToRelocateTests(unittest.TestCase):
    PHASES = [
        {"number": 1, "kind": "code-shipping"},
        {"number": 2, "kind": "operator"},
        {"number": 3, "kind": "code-shipping"},
        {"number": 4, "kind": "code-shipping"},
    ]

    def rows(self, *ticked):
        return [
            {"phase": n, "checked": n in ticked, "sub_label": None} for n in range(1, 5)
        ] + [{"phase": 4, "checked": True, "sub_label": "fix"}]

    def test_ticked_code_shipping_without_a_record(self):
        self.assertEqual(plan_shipped.to_relocate(self.PHASES, self.rows(1, 2, 3), [1]), [3])

    def test_operator_phase_is_never_proposed(self):
        self.assertNotIn(2, plan_shipped.to_relocate(self.PHASES, self.rows(1, 2), []))

    def test_a_ticked_sub_row_is_not_a_tick_of_its_phase(self):
        self.assertNotIn(4, plan_shipped.to_relocate(self.PHASES, self.rows(1), []))

    def test_unparsed_prior_plan_proposes_nothing(self):
        self.assertEqual(plan_shipped.to_relocate(None, self.rows(1, 3), []), [])


class CheckTests(unittest.TestCase):
    def good(self):
        rec = record(
            1,
            changes=("- `a.rb` — adds A", "  continuing the A entry"),
            tests=("- Unit:", "  - `a_spec.rb` — A works"),
        )
        main = main_after(
            ["- `b.rb` — adds B", "- `c.rb` — adds C"],
            ["- Unit:", "  - `c_spec.rb` — C works"],
        )
        return main, rec

    def test_a_clean_relocation(self):
        main, rec = self.good()
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)], pr=903)
        self.assertTrue(payload["clean"], payload["findings"])
        self.assertEqual(payload["main"]["headroom_chars"], BODY_CHAR_LIMIT - len(main))
        self.assertEqual(payload["records"][0]["phase"], 1)

    def test_a_reworded_entry_is_not_verbatim(self):
        main, rec = self.good()
        rec = rec.replace("adds A", "adds the A")
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)])
        self.assertEqual(payload["findings"]["not_verbatim"][0]["section"], "changes")
        self.assertFalse(payload["clean"])

    def test_a_copied_entry_still_in_main(self):
        _, rec = self.good()
        main = main_after(
            ["- `a.rb` — adds A", "  continuing the A entry", "- `b.rb` — adds B"],
            ["- Unit:", "  - `c_spec.rb` — C works"],
        )
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)])
        self.assertEqual(payload["findings"]["still_in_main"][0]["section"], "changes")

    def test_a_test_plan_kind_line_may_stay_in_main(self):
        main, rec = self.good()
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)])
        self.assertEqual(payload["findings"]["still_in_main"], [])

    def test_a_split_changes_entry_is_still_in_main(self):
        # The parent line stayed in main while one sub-bullet moved: the shared-entry rule's
        # forbidden split. Only a `## Test plan` kind line may stay behind its moved children.
        prior = PRIOR.replace("- `b.rb` — adds B", "- `b.rb` — adds B\n  - B's first half\n  - B's second half")
        rec = record(1, changes=("- `b.rb` — adds B", "  - B's first half"))
        main = main_after(
            ["- `b.rb` — adds B", "  - B's second half", "- `c.rb` — adds C"],
            ["- Unit:", "  - `c_spec.rb` — C works"],
        )
        payload = plan_shipped.check(prior, main, [("r1.md", rec)])
        self.assertEqual(payload["findings"]["still_in_main"][0]["line"], "- `b.rb` — adds B")

    def test_missing_pointer(self):
        main, rec = self.good()
        main = main.replace("- Phase 1 shipped on #903: entries in the shipped-phase records.\n", "", 1)
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)])
        self.assertEqual(payload["findings"]["missing_pointer"], ["changes"])

    def test_pointer_naming_another_pr_is_missing(self):
        main, rec = self.good()
        main = main.replace("#903", "#800")
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)])
        self.assertEqual(sorted(payload["findings"]["missing_pointer"]), ["changes", "test_plan"])

    def test_malformed_head_and_unexpected_section(self):
        main, rec = self.good()
        rec = rec.replace("**Shipped on:**", "Shipped:") + "\n## Architecture decisions\n- Decision one.\n"
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)])
        self.assertEqual(payload["findings"]["malformed_head"], ["r1.md"])
        self.assertEqual(payload["findings"]["unexpected_sections"][0]["heading"], "## Architecture decisions")

    def test_over_cap_main_is_not_clean(self):
        main, rec = self.good()
        main += "x" * BODY_CHAR_LIMIT
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)])
        self.assertTrue(payload["main"]["over_limit"])
        self.assertFalse(payload["clean"])

    def test_a_pointer_to_a_pr_that_is_not_open_is_foreign(self):
        # After a Start-fresh there is no open PR: a surviving pointer names records nobody reads
        # for the new PR, so the restore step must have removed it.
        main, rec = self.good()
        self.assertEqual(plan_shipped.check(PRIOR, main, [("r1.md", rec)])["findings"]["foreign_pointer"], [903])
        self.assertEqual(
            plan_shipped.check(PRIOR, main, [("r1.md", rec)], pr=950)["findings"]["foreign_pointer"], [903]
        )

    def test_a_drifted_pointer_is_malformed(self):
        main, rec = self.good()
        main = main.replace(": entries in the shipped-phase records.", "; see the shipped-phase records.", 1)
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)], pr=903)
        self.assertEqual(len(payload["findings"]["malformed_pointer"]), 1)

    def test_restored_entries_are_a_verbatim_source(self):
        # Restored from a closed PR's record and relocated again in the same revise: still a move.
        restored = record(1, pr=800, changes=("- `a.rb` — adds A", "  continuing the A entry"))
        prior = PRIOR.replace("- `a.rb` — adds A\n  continuing the A entry\n", "")
        main, rec = self.good()
        payload = plan_shipped.check(prior, main, [("r1.md", rec)], pr=903, restored=[("old.md", restored)])
        self.assertEqual(payload["findings"]["not_verbatim"], [])
        self.assertEqual(payload["findings"]["not_restored"], [])

    def test_a_dropped_restored_entry_is_not_restored(self):
        restored = record(1, pr=800, changes=("- `z.rb` — adds Z",))
        main, rec = self.good()
        payload = plan_shipped.check(PRIOR, main, [("r1.md", rec)], pr=903, restored=[("old.md", restored)])
        self.assertEqual(payload["findings"]["not_restored"][0]["line"], "- `z.rb` — adds Z")

    def test_no_records_reports_size_only(self):
        payload = plan_shipped.check(PRIOR, PRIOR, [])
        self.assertTrue(payload["clean"])
        self.assertEqual(payload["main"]["chars"], len(PRIOR))

    def test_cli_emits_one_ok_envelope(self):
        main, rec = self.good()
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, text in (("prior.md", PRIOR), ("plan.md", main), ("shipped-phase-1.md", rec)):
                path = Path(tmp) / name
                path.write_text(text, encoding="utf-8")
                paths.append(str(path))
            result = subprocess.run(
                [str(SCRIPTS_DIR / "plan_shipped.py"), "check"] + paths + ["--pr", "903"],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertTrue(envelope["clean"])

    def test_cli_usage_error_exits_2(self):
        result = subprocess.run(
            [str(SCRIPTS_DIR / "plan_shipped.py")], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
