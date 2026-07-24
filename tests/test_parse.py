"""Unit tests for scripts/parse.py — the S5 shared-body-grammar parser (architecture.md §2, §3;
docs/implementation.md S5).

This is a **from-scratch v2 script** — there is no v1 `parse.py` to port from; v1 skills parsed
the `## Definition of done` / `## Open questions` / `## Phases` grammars inline in each
`SKILL.md`'s prose. This suite validates the Python re-implementation directly against the
`_shared` contract files it is authored from (`skills/_shared/dod-annotations.md`,
`skills/_shared/open-question-links.md`,
`skills/planner/references/plan-schema.md`), using fixtures lifted from those
contracts' own worked examples (`docs/specs/examples/dod-annotations.md`,
`docs/specs/examples/open-question-links.md`) plus adversarial mutations authored for this suite.

`parse.py` is file I/O only (no `gh`, no network, no shim needed — like `config_block.py`'s S21
port), so every test here drives either the module's own functions in-process or the real
`python3 scripts/parse.py ...` subprocess against real fixture files on disk.

Two complementary strategies, matching `tests/test_config_block.py`'s own two-tier pattern:

  - **In-process unit tests** (`*ModuleTests`) call `parse`'s own `parse_dod_bullets` /
    `parse_oq_links` / `parse_phases` / `render_dod_bullets` functions directly — fast, and pins
    the exact field-extraction behavior against fixtures and hand-constructed edge cases.
  - **Subprocess/CLI tests** (`*CliTests`) invoke `python3 scripts/parse.py ...` as a real
    subprocess against the fixture files — the end-to-end path a caller (a prep script, a
    playbook) actually uses, proving the exit-code contract and the envelope shape via
    `tests/support/envelope_asserts`.

Fixtures live under `tests/fixtures/parse_dod/`, `tests/fixtures/parse_oq_links/`,
`tests/fixtures/parse_phases/` — one file per annotation form / disposition / phase-kind
combination (happy path) plus one file per adversarial mutation (malformed path), each fixture's
own docstring-equivalent comment block explaining which shared-contract example it lifts from or
which invariant its mutation targets.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
PARSE_PY = SCRIPTS_DIR / "parse.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DOD_FIXTURES_DIR = FIXTURES_DIR / "parse_dod"
OQ_FIXTURES_DIR = FIXTURES_DIR / "parse_oq_links"
PHASES_FIXTURES_DIR = FIXTURES_DIR / "parse_phases"

sys.path.insert(0, str(SCRIPTS_DIR))

import parse  # noqa: E402  (import after sys.path setup, by necessity)
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR  # noqa: E402
from tests.support import envelope_asserts  # noqa: E402


def _run_cli(args):
    """Invoke ``parse.py`` as a real subprocess. Returns ``(returncode, stdout_text,
    stderr_text)``. UTF-8 decoding is explicit, matching architecture.md §1's encoding pin on the
    test side too (`tests/test_config_block.py`'s own `_run_cli` convention).
    """
    completed = subprocess.run(
        [sys.executable, str(PARSE_PY)] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return (
        completed.returncode,
        completed.stdout.decode("utf-8"),
        completed.stderr.decode("utf-8"),
    )


def _parse_one_envelope(stdout_text):
    """Parse exactly one JSON object from ``stdout_text`` — architecture.md §3's "exactly one
    JSON envelope on stdout" contract (identical helper to `tests/test_config_block.py`'s own).
    """
    lines = [line for line in stdout_text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise AssertionError(
            "expected exactly one non-blank stdout line (the envelope), got %d: %r"
            % (len(lines), lines)
        )
    return json.loads(lines[0])


def _fixture_text(directory, name):
    with open(directory / name, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _extract_original_top_level_dod_lines(body_text):
    """Pull just the original top-level DoD checkbox-bullet lines out of a fixture body's ``##
    Definition of done`` section — the exact substring `render_dod_bullets` is meant to reproduce
    byte-for-byte, independent of whatever prose/heading/sub-bullet lines surround them in the
    fixture (those are not part of what `parse_dod_bullets` captures, so are correctly excluded
    from the round-trip comparison rather than causing a spurious mismatch).
    """
    lines = body_text.splitlines()
    section = parse._find_section(lines, r"Definition of done")
    assert section is not None, "fixture must have a '## Definition of done' section"
    start, end = section
    out = []
    for i in range(start, end):
        match = parse._DOD_BULLET_RE.match(lines[i])
        if match and parse._TOP_LEVEL_INDENT_RE.match(match.group(1)):
            out.append(lines[i])
    return "\n".join(out) + ("\n" if out else "")


# ============================================================================================
# `dod` — in-process module tests
# ============================================================================================


class ParseDodModuleTests(unittest.TestCase):
    """One test per closed-set annotation form (dod-annotations.md's "Annotation shapes (closed
    set)" table, lifted verbatim into `docs/specs/examples/dod-annotations.md`), each asserting
    the parsed fields AND the byte-identical round-trip through `render_dod_bullets` — this dual
    assertion per fixture is what proves S5's first DoD box ("`dod` parses every annotation form
    in the shared contract (one fixture per form); parse -> re-render round-trips
    byte-identically").
    """

    def _assert_round_trips(self, fixture_name):
        text = _fixture_text(DOD_FIXTURES_DIR, fixture_name)
        bullets = parse.parse_dod_bullets(text)
        rendered = parse.render_dod_bullets(bullets)
        original = _extract_original_top_level_dod_lines(text)
        self.assertEqual(
            rendered,
            original,
            "round-trip mismatch for %s:\n  original: %r\n  rendered: %r"
            % (fixture_name, original, rendered),
        )
        return bullets

    def test_bare_no_annotation_form(self):
        bullets = self._assert_round_trips("bare_no_annotation.md")
        self.assertEqual(len(bullets), 2)
        self.assertEqual(bullets[0]["index"], 1)
        self.assertFalse(bullets[0]["checked"])
        self.assertIsNone(bullets[0]["annotation"])
        self.assertEqual(bullets[0]["text"], "Clicking the save button persists the draft")

    def test_closed_by_phase_commit_form(self):
        bullets = self._assert_round_trips("closed_by_phase_commit.md")
        annotated = bullets[0]
        self.assertTrue(annotated["checked"])
        self.assertEqual(
            annotated["annotation"],
            {"form": "closed-by-phase-commit", "phase": 1, "sha": "abc1234"},
        )

    def test_closed_by_phase_operator_form(self):
        bullets = self._assert_round_trips("closed_by_phase_operator.md")
        annotated = bullets[0]
        self.assertTrue(annotated["checked"])
        self.assertEqual(
            annotated["annotation"],
            {"form": "closed-by-phase-operator", "phase": 2, "date": "2026-06-30"},
        )

    def test_closed_by_commit_single_phase_fallback_form(self):
        bullets = self._assert_round_trips("closed_by_commit_single_phase.md")
        annotated = bullets[0]
        self.assertTrue(annotated["checked"])
        self.assertEqual(annotated["annotation"], {"form": "closed-by-commit", "sha": "9f8e7d6"})

    def test_resolver_claimed_evaluator_rejected_form(self):
        bullets = self._assert_round_trips("resolver_claimed_evaluator_rejected.md")
        rejected = bullets[0]
        self.assertFalse(rejected["checked"])  # sticky veto: un-ticked
        self.assertEqual(
            rejected["annotation"],
            {
                "form": "resolver-claimed-evaluator-rejected",
                "phase": 3,
                "sha": "1a2b3c4",
                "reason": "streaming path still buffers the whole file in memory",
            },
        )

    def test_previously_claimed_on_closed_pr_form(self):
        bullets = self._assert_round_trips("previously_claimed_on_closed_pr.md")
        predecessor = bullets[0]
        self.assertFalse(predecessor["checked"])  # un-ticked predecessor annotation
        self.assertEqual(
            predecessor["annotation"],
            {
                "form": "previously-claimed-on-closed-pr",
                "phase": 2,
                "sha": "4d5e6f7",
                "pr": 612,
            },
        )

    def test_mixed_realistic_body_excludes_sub_bullet_and_indexes_top_level_only(self):
        bullets = self._assert_round_trips("mixed_realistic.md")
        # 3 top-level DoD bullets; the indented sub-bullet detail line and the unrelated
        # '## Out of scope' section's own bullet must not be counted (dod-annotations.md's
        # "Top-level bullets only" + "Section finder" rules).
        self.assertEqual([b["index"] for b in bullets], [1, 2, 3])
        self.assertEqual(bullets[1]["text"], "Search results are keyboard-navigable")

    def test_no_definition_of_done_section_returns_empty_list_silently(self):
        text = "## Summary\nJust a summary, no DoD section at all.\n"
        self.assertEqual(parse.parse_dod_bullets(text), [])

    def test_free_text_trailing_parenthetical_is_not_mistaken_for_an_annotation(self):
        # Negative control for the `_ANNOTATION_LOOKALIKE_RE` heuristic: an ordinary bullet whose
        # free text happens to end in an unrelated parenthetical (a scope/stretch-goal note) must
        # parse as a bare, unannotated bullet — never DOD_MALFORMED. False positives here would
        # block ordinary authoring on every rewrite pass.
        text = "## Definition of done\n- [ ] Support CSV export (stretch goal)\n"
        bullets = parse.parse_dod_bullets(text)
        self.assertEqual(len(bullets), 1)
        self.assertIsNone(bullets[0]["annotation"])
        self.assertEqual(bullets[0]["text"], "Support CSV export (stretch goal)")


class ParseDodMalformedModuleTests(unittest.TestCase):
    """S5 DoD box 2: 'Unknown or stacked annotations return DOD_MALFORMED (never a crash or a
    guess).' One test per distinct way that can happen, each an adversarial mutation authored for
    this suite (not present verbatim in the shared contract, which only documents the well-formed
    shapes).
    """

    def test_unknown_annotation_prefix_raises(self):
        text = _fixture_text(DOD_FIXTURES_DIR, "malformed_unknown_prefix.md")
        with self.assertRaises(parse._DodMalformed) as ctx:
            parse.parse_dod_bullets(text)
        self.assertIn("fixed by", ctx.exception.reason)

    def test_stacked_annotations_both_closed_by_raises(self):
        text = _fixture_text(DOD_FIXTURES_DIR, "malformed_stacked_annotations.md")
        with self.assertRaises(parse._DodMalformed):
            parse.parse_dod_bullets(text)

    def test_recognized_prefix_with_unparseable_tail_raises(self):
        text = _fixture_text(DOD_FIXTURES_DIR, "malformed_bad_tail_shape.md")
        with self.assertRaises(parse._DodMalformed):
            parse.parse_dod_bullets(text)

    def test_stacked_annotation_smuggled_inside_rejection_reason_raises(self):
        # The evaluator-rejection form's `reason` field is free text, so a stacked second
        # annotation folded into it (via the outer regex's greedy tail capture) could otherwise
        # silently pass through as "reason text" rather than being caught — this is the one
        # sub-shape needing its own dedicated stacking guard (`_REASON_CONTAINS_PAREN_RE`).
        text = _fixture_text(DOD_FIXTURES_DIR, "malformed_stacked_rejection_then_closed.md")
        with self.assertRaises(parse._DodMalformed):
            parse.parse_dod_bullets(text)

    def test_never_crashes_with_an_unhandled_exception_on_malformed_input(self):
        # "Never a crash" — assert the only exception type that can escape is the module's own
        # typed `_DodMalformed`, not e.g. an IndexError/AttributeError from a regex assumption
        # that didn't hold.
        for fixture_name in (
            "malformed_unknown_prefix.md",
            "malformed_stacked_annotations.md",
            "malformed_bad_tail_shape.md",
            "malformed_stacked_rejection_then_closed.md",
        ):
            text = _fixture_text(DOD_FIXTURES_DIR, fixture_name)
            try:
                parse.parse_dod_bullets(text)
                self.fail("%s: expected _DodMalformed, got a clean parse" % fixture_name)
            except parse._DodMalformed:
                pass  # exactly the expected typed signal


# ============================================================================================
# `dod` — CLI tests (envelope conformance, exit codes, --render)
# ============================================================================================


class ParseDodCliTests(unittest.TestCase):
    def test_dod_happy_path_envelope_conformance(self):
        rc, out, err = _run_cli(["dod", str(DOD_FIXTURES_DIR / "closed_by_phase_commit.md")])
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        envelope_asserts.assert_exit_code_contract(rc, envelope_present=True)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(len(envelope["dod"]), 2)
        self.assertEqual(envelope["dod"][0]["annotation"]["form"], "closed-by-phase-commit")

    def test_dod_render_mode_byte_identical_round_trip_via_cli(self):
        fixture_path = DOD_FIXTURES_DIR / "mixed_realistic.md"
        rc, out, err = _run_cli(["dod", str(fixture_path), "--render"])
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        original = _extract_original_top_level_dod_lines(
            _fixture_text(DOD_FIXTURES_DIR, "mixed_realistic.md")
        )
        self.assertEqual(envelope["rendered"], original)

    def test_dod_render_on_malformed_body_still_returns_dod_malformed_not_a_guess(self):
        # "--render still parses first: a malformed body still returns DOD_MALFORMED under
        # --render, it does not silently render a best-effort guess" (module docstring).
        rc, out, err = _run_cli(
            ["dod", str(DOD_FIXTURES_DIR / "malformed_unknown_prefix.md"), "--render"]
        )
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "DOD_MALFORMED")
        self.assertNotIn("rendered", envelope)

    def test_dod_malformed_emits_dod_malformed_decision_with_evidence(self):
        rc, out, err = _run_cli(["dod", str(DOD_FIXTURES_DIR / "malformed_bad_tail_shape.md")])
        self.assertEqual(rc, EXIT_OK)  # needs_decision is exit 0 (architecture.md §3)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        envelope_asserts.assert_decision_payload_shape(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "DOD_MALFORMED")
        self.assertIn("body_file", envelope["decision"]["context"])
        self.assertIn("line_number", envelope["decision"]["context"])
        self.assertIn("raw_line", envelope["decision"]["context"])

    def test_dod_no_section_ok_empty_list_via_cli(self):
        # `no_section_single_phase.md` (a `parse_phases` fixture) carries no `## Definition of
        # done` heading at all — genuinely exercises the "section absent" path, distinct from the
        # `parse_oq_links/no_section.md` fixture, which is about the `## Open questions` section
        # and in fact carries its own `## Definition of done` section (used by the `oq-links`
        # tests, not this one).
        rc, out, err = _run_cli(
            ["dod", str(PHASES_FIXTURES_DIR / "no_section_single_phase.md")]
        )
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["dod"], [])

    def test_dod_nonexistent_file_exits_usage_error_no_envelope(self):
        rc, out, err = _run_cli(["dod", "/nonexistent/path/does-not-exist.md"])
        self.assertEqual(rc, EXIT_USAGE_ERROR)
        self.assertEqual(out, "")
        self.assertIn("PARSE_FILE_UNREADABLE", err)
        envelope_asserts.assert_exit_code_contract(rc, envelope_present=False)


# ============================================================================================
# `oq-links` — in-process module tests
# ============================================================================================


class ParseOqLinksModuleTests(unittest.TestCase):
    """S5 DoD box 3: 'oq-links parses the shared contract's examples including all three
    dispositions; a body without the section returns ok with an empty list.'
    """

    def test_all_three_dispositions_parse_from_the_shared_worked_example(self):
        text = _fixture_text(OQ_FIXTURES_DIR, "all_three_dispositions.md")
        entries = parse.parse_oq_links(text)
        self.assertEqual(len(entries), 3)
        dispositions = [e["disposition"] for e in entries]
        self.assertEqual(dispositions, ["scoped-out", "in-scope (blocked)", "provisional-default"])

    def test_scoped_out_entry_fields(self):
        text = _fixture_text(OQ_FIXTURES_DIR, "all_three_dispositions.md")
        entry = parse.parse_oq_links(text)[0]
        self.assertEqual(entry["oq_id"], "PRD-OQ-05")
        self.assertEqual(entry["source"], "docs/prd.md §12 Open questions")
        self.assertEqual(entry["gates"], "which payment methods ship at launch")
        self.assertEqual(entry["question"], "#211")
        self.assertEqual(entry["audience"], "audience:business, audience:developer")
        self.assertIsNone(entry["default"])
        self.assertIsNone(entry["retires_when"])

    def test_in_scope_blocked_entry_fields(self):
        text = _fixture_text(OQ_FIXTURES_DIR, "all_three_dispositions.md")
        entry = parse.parse_oq_links(text)[1]
        self.assertEqual(entry["oq_id"], "OQ-08")
        self.assertEqual(entry["disposition"], "in-scope (blocked)")
        self.assertEqual(entry["question"], "#212")
        self.assertEqual(entry["audience"], "audience:clinical")

    def test_provisional_default_entry_carries_default_and_retires_when(self):
        text = _fixture_text(OQ_FIXTURES_DIR, "all_three_dispositions.md")
        entry = parse.parse_oq_links(text)[2]
        self.assertEqual(entry["oq_id"], "DESIGN-Q-3")
        self.assertEqual(entry["disposition"], "provisional-default")
        self.assertEqual(entry["default"], "newest-first")
        self.assertEqual(entry["retires_when"], "#213 answered")

    def test_not_filed_question_value_parses(self):
        text = _fixture_text(OQ_FIXTURES_DIR, "not_filed_question.md")
        entries = parse.parse_oq_links(text)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["question"], "(not filed)")
        self.assertEqual(entries[0]["audience"], "(unknown)")

    def test_no_open_questions_section_returns_empty_list(self):
        text = _fixture_text(OQ_FIXTURES_DIR, "no_section.md")
        self.assertEqual(parse.parse_oq_links(text), [])

    def test_section_present_without_marker_returns_empty_list_not_malformed(self):
        # open-question-links.md: readers locate the registry via a `startswith` match on the
        # marker line; a section lacking it is not this registry at all — degrade to empty, never
        # raise (a heading name collision with an unrelated "Open questions" prose section must
        # not become an operator-blocking decision).
        text = _fixture_text(OQ_FIXTURES_DIR, "malformed_missing_marker.md")
        self.assertEqual(parse.parse_oq_links(text), [])

    def test_bare_body_with_no_sections_at_all_returns_empty_list(self):
        self.assertEqual(parse.parse_oq_links("no headings here at all\n"), [])


class ParseOqLinksMalformedModuleTests(unittest.TestCase):
    def test_unknown_disposition_raises(self):
        text = _fixture_text(OQ_FIXTURES_DIR, "malformed_unknown_disposition.md")
        with self.assertRaises(parse._OqLinksMalformed) as ctx:
            parse.parse_oq_links(text)
        self.assertIn("disposition", ctx.exception.reason)

    def test_provisional_default_missing_required_fields_raises(self):
        text = _fixture_text(OQ_FIXTURES_DIR, "malformed_provisional_missing_default.md")
        with self.assertRaises(parse._OqLinksMalformed) as ctx:
            parse.parse_oq_links(text)
        self.assertIn("provisional-default", ctx.exception.reason)

    def test_missing_required_question_field_raises(self):
        text = _fixture_text(OQ_FIXTURES_DIR, "malformed_missing_question_field.md")
        with self.assertRaises(parse._OqLinksMalformed):
            parse.parse_oq_links(text)

    def test_default_field_on_non_provisional_disposition_raises(self):
        # open-question-links.md: "default:"/"retires-when:" are "[provisional-default only]" —
        # present on a scoped-out/in-scope-blocked entry is itself a schema violation, not a
        # harmless extra field to silently accept.
        text = (
            "## Open questions\n"
            "<!-- open-question-links:v1 -->\n"
            "- OQ: `OQ-99` (docs/prd.md §1) — gates: something\n"
            "  — disposition: scoped-out — question: #400 — audience: audience:business\n"
            "  — default: something — retires-when: #400 answered\n"
        )
        with self.assertRaises(parse._OqLinksMalformed) as ctx:
            parse.parse_oq_links(text)
        self.assertIn("scoped-out", ctx.exception.reason)


# ============================================================================================
# `oq-links` — CLI tests
# ============================================================================================


class ParseOqLinksCliTests(unittest.TestCase):
    def test_oq_links_happy_path_envelope_conformance(self):
        rc, out, err = _run_cli(
            ["oq-links", str(OQ_FIXTURES_DIR / "all_three_dispositions.md")]
        )
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(len(envelope["open_questions"]), 3)

    def test_oq_links_no_section_ok_empty_list_via_cli(self):
        rc, out, err = _run_cli(["oq-links", str(OQ_FIXTURES_DIR / "no_section.md")])
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["open_questions"], [])

    def test_oq_links_malformed_emits_needs_decision(self):
        rc, out, err = _run_cli(
            ["oq-links", str(OQ_FIXTURES_DIR / "malformed_unknown_disposition.md")]
        )
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        envelope_asserts.assert_decision_payload_shape(envelope)
        self.assertEqual(envelope["status"], "needs_decision")


# ============================================================================================
# `phases` — in-process module tests
# ============================================================================================


class ParsePhasesModuleTests(unittest.TestCase):
    """S5 DoD box 4: 'phases parses well-formed lists and returns PHASES_MALFORMED on the
    malformed fixtures.'
    """

    def test_well_formed_four_phase_plan_all_three_kinds(self):
        text = _fixture_text(PHASES_FIXTURES_DIR, "well_formed_multi_phase.md")
        phases = parse.parse_phases(text)
        self.assertEqual([p["number"] for p in phases], [1, 2, 3, 4])
        self.assertEqual(
            [p["kind"] for p in phases],
            ["code-shipping", "code-shipping", "operator", "decision-only"],
        )

    def test_closes_dod_none_parses_as_literal_string(self):
        text = _fixture_text(PHASES_FIXTURES_DIR, "well_formed_multi_phase.md")
        phases = parse.parse_phases(text)
        self.assertEqual(phases[0]["closes_dod"], "(none)")
        self.assertEqual(phases[0]["depends_on"], "(none)")

    def test_closes_dod_multi_value_list_parses_as_ints(self):
        text = _fixture_text(PHASES_FIXTURES_DIR, "well_formed_multi_phase.md")
        phases = parse.parse_phases(text)
        self.assertEqual(phases[1]["closes_dod"], [1, 2])
        self.assertEqual(phases[1]["depends_on"], [1])

    def test_titles_and_ships_and_deliverable_fields(self):
        text = _fixture_text(PHASES_FIXTURES_DIR, "well_formed_multi_phase.md")
        phases = parse.parse_phases(text)
        self.assertEqual(phases[0]["title"], "substrate")
        self.assertEqual(phases[0]["ships"], "PR commits to the issue branch")
        self.assertEqual(
            phases[2]["deliverable"],
            "the operator's recorded go/no-go on the harness's first measurement run",
        )

    def test_no_phases_section_returns_empty_list_not_malformed(self):
        # plan-schema.md: single-phase issues and epics correctly omit '## Phases' entirely — an
        # absent section is a legitimate shape, never PHASES_MALFORMED on its own.
        text = _fixture_text(PHASES_FIXTURES_DIR, "no_section_single_phase.md")
        self.assertEqual(parse.parse_phases(text), [])

    def test_bare_body_with_no_sections_at_all_returns_empty_list(self):
        self.assertEqual(parse.parse_phases("no headings here at all\n"), [])


class ParsePhasesMalformedModuleTests(unittest.TestCase):
    def test_missing_required_key_raises(self):
        text = _fixture_text(PHASES_FIXTURES_DIR, "malformed_missing_key.md")
        with self.assertRaises(parse._PhasesMalformed) as ctx:
            parse.parse_phases(text)
        self.assertIn("deliverable", ctx.exception.reason)

    def test_kind_outside_closed_set_raises(self):
        text = _fixture_text(PHASES_FIXTURES_DIR, "malformed_bad_kind.md")
        with self.assertRaises(parse._PhasesMalformed) as ctx:
            parse.parse_phases(text)
        self.assertIn("kind", ctx.exception.reason)

    def test_nonsequential_phase_numbers_raise(self):
        text = _fixture_text(PHASES_FIXTURES_DIR, "malformed_nonsequential_numbers.md")
        with self.assertRaises(parse._PhasesMalformed) as ctx:
            parse.parse_phases(text)
        self.assertIn("sequential", ctx.exception.reason)

    def test_ordinal_label_mismatch_raises(self):
        text = _fixture_text(PHASES_FIXTURES_DIR, "malformed_ordinal_label_mismatch.md")
        with self.assertRaises(parse._PhasesMalformed) as ctx:
            parse.parse_phases(text)
        self.assertIn("label", ctx.exception.reason)

    def test_bad_closes_dod_value_raises(self):
        text = _fixture_text(PHASES_FIXTURES_DIR, "malformed_bad_closes_dod_value.md")
        with self.assertRaises(parse._PhasesMalformed) as ctx:
            parse.parse_phases(text)
        self.assertIn("closes-dod", ctx.exception.reason)

    def test_free_form_sequencing_prose_raises(self):
        # The named regression (architecture.md/resolver.md, issue #640): free-form '## Sequencing'
        # prose instead of the fixed structured-key grammar gave the resolver no way to recognize
        # more phases were due. A '## Phases' heading over unstructured prose must raise, not
        # silently return an empty/partial phase list.
        text = _fixture_text(PHASES_FIXTURES_DIR, "malformed_free_form_sequencing.md")
        with self.assertRaises(parse._PhasesMalformed):
            parse.parse_phases(text)

    def test_duplicate_phase_number_raises(self):
        text = (
            "## Phases\n"
            "1. **Phase 1 — a**\n"
            "   - kind: code-shipping\n"
            "   - ships: PR commits to the issue branch\n"
            "   - closes-dod: (none)\n"
            "   - deliverable: x\n"
            "   - depends-on: (none)\n"
            "1. **Phase 1 — b**\n"
            "   - kind: code-shipping\n"
            "   - ships: PR commits to the issue branch\n"
            "   - closes-dod: (none)\n"
            "   - deliverable: y\n"
            "   - depends-on: 1\n"
        )
        with self.assertRaises(parse._PhasesMalformed) as ctx:
            parse.parse_phases(text)
        self.assertIn("more than once", ctx.exception.reason)

    def test_never_crashes_with_an_unhandled_exception_on_malformed_input(self):
        for fixture_name in (
            "malformed_missing_key.md",
            "malformed_bad_kind.md",
            "malformed_nonsequential_numbers.md",
            "malformed_ordinal_label_mismatch.md",
            "malformed_bad_closes_dod_value.md",
            "malformed_free_form_sequencing.md",
        ):
            text = _fixture_text(PHASES_FIXTURES_DIR, fixture_name)
            try:
                parse.parse_phases(text)
                self.fail("%s: expected _PhasesMalformed, got a clean parse" % fixture_name)
            except parse._PhasesMalformed:
                pass


# ============================================================================================
# `phases` — CLI tests
# ============================================================================================


class ParsePhasesCliTests(unittest.TestCase):
    def test_phases_happy_path_envelope_conformance(self):
        rc, out, err = _run_cli(
            ["phases", str(PHASES_FIXTURES_DIR / "well_formed_multi_phase.md")]
        )
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(len(envelope["phases"]), 4)

    def test_phases_no_section_ok_empty_list_via_cli(self):
        rc, out, err = _run_cli(
            ["phases", str(PHASES_FIXTURES_DIR / "no_section_single_phase.md")]
        )
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["phases"], [])

    def test_phases_malformed_emits_phases_malformed_decision(self):
        rc, out, err = _run_cli(
            ["phases", str(PHASES_FIXTURES_DIR / "malformed_free_form_sequencing.md")]
        )
        self.assertEqual(rc, EXIT_OK)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        envelope_asserts.assert_decision_payload_shape(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "PHASES_MALFORMED")


# ============================================================================================
# Cross-cutting: usage errors, subcommand dispatch
# ============================================================================================


class ParseCliUsageTests(unittest.TestCase):
    def test_no_args_exits_usage_error_no_envelope(self):
        rc, out, err = _run_cli([])
        self.assertEqual(rc, EXIT_USAGE_ERROR)
        self.assertEqual(out, "")

    def test_unknown_subcommand_exits_usage_error(self):
        rc, out, err = _run_cli(["bogus-subcommand", "x"])
        self.assertEqual(rc, EXIT_USAGE_ERROR)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
