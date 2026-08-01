"""Offline tests for the question-resolver skill (docs/implementation.md S18).

Surfaces the S18 DoD / Testing names for the resolver half:

1. **Structural bars.** Router ≤ 150 (architecture.md §9 — the bar the brief binds S18 to; the DoD has NO
   line-count box). The ≤half-v1 metric (floor(185/2) = 92) is **recorded, not enforced** (the loaded set
   carries the frozen decision-comment + fold-back renderings) — see docs/specs/parity/question-pair.md; a
   ceiling test guards growth.
2. **Frontmatter pins.** name: question-resolver / opus / high / **`disable-model-invocation: true`** (the
   S18 rule — one of the three standalone tools that keep the key).
3. **Contract-token grep gates** over skills/question-resolver/: zero retired-executor tokens, zero
   `github-pipeline:github-`, zero `GATHER_`/`PERSIST_` op names, zero `§P` IDs, zero raw gh WRITES in
   fences, zero `w/`.
4. **`question-decision:v1` byte-identity (DoD box 4 offline half).** The decision-comment schema fence in
   the resolve flow is byte-for-byte the frozen S1 capture (`docs/specs/examples/question-decision.md`).
5. **Reentrancy mechanics (DoD box 4).** The revise path passes `--delete-marker-id` (replace, not
   duplicate); close is a no-op on an already-closed issue; reopen is offered in the reentrant case.
6. **The constraint-audit reference is carried** (S11-clean — no retired-doc citation) and returns findings.
7. **Stack-agnostic**; the reader is reached at its question-sweep home.
"""

import re
import sys
import unittest
from pathlib import Path

from tests.support.retired_tokens import FORBIDDEN_CONTRACT_TOKENS, retired_name_hits

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SKILL_DIR = REPO_ROOT / "skills" / "question-resolver"
ROUTER = SKILL_DIR / "SKILL.md"
PLAYBOOKS_DIR = SKILL_DIR / "playbooks"
REFERENCES_DIR = SKILL_DIR / "references"
FLOW = "resolve-flow.md"
CONSTRAINT_AUDIT = REFERENCES_DIR / "constraint-audit-prompt.md"
QUESTION_DECISION_EXAMPLE = REPO_ROOT / "docs" / "specs" / "examples" / "question-decision.md"

# floor(v1 question-resolver/SKILL.md 185 lines, docs/specs/baseline.md §1) / 2 = 92 — the RECORDED metric.
V1_HALF_BAR = 185 // 2
LOADED_SET_CEILING = 175

sys.path.insert(0, str(SCRIPTS_DIR))


def _iter_md(dir_path):
    yield from sorted(dir_path.rglob("*.md"))


def _fence_stripped_lines(path):
    in_fence = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            yield i, line, in_fence
            continue
        yield i, line, in_fence


def _extract_marked_fence(text, marker):
    """The interior of the first ``` fence whose first content line is `marker`. Returns the interior
    text (no fence delimiters) or None."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("```"):
            # collect until the closing fence
            body = []
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                body.append(lines[j])
                j += 1
            if body and body[0].strip() == marker:
                return "\n".join(body)
            i = j + 1
            continue
        i += 1
    return None


class RouterStructureTests(unittest.TestCase):
    def setUp(self):
        self.router_text = ROUTER.read_text(encoding="utf-8")

    def test_router_exists_and_frontmatter(self):
        self.assertTrue(ROUTER.is_file())
        head = "\n".join(self.router_text.splitlines()[:8])
        self.assertIn("name: question-resolver", head)
        self.assertNotIn("model:", head)
        self.assertNotIn("effort:", head)
        self.assertIn("disable-model-invocation: true", head)

    def test_exactly_one_playbook_on_disk(self):
        on_disk = {p.name for p in PLAYBOOKS_DIR.glob("*.md")}
        self.assertEqual(on_disk, {FLOW}, "the resolver has one linear flow — one playbook, got %r" % on_disk)

    def test_router_points_at_the_single_flow(self):
        self.assertIn("playbooks/resolve-flow.md", self.router_text)
        self.assertRegex(self.router_text, r"[Nn]o mode fork")

    def test_router_at_most_150_lines(self):
        n = len(self.router_text.splitlines())
        self.assertLessEqual(n, 150, "router is %d lines (architecture.md §9 bar <= 150)" % n)

    def test_loaded_set_under_ceiling_and_half_metric_recorded(self):
        router = len(self.router_text.splitlines())
        playbook = len((PLAYBOOKS_DIR / FLOW).read_text(encoding="utf-8").splitlines())
        total = router + playbook
        self.assertLessEqual(
            total, LOADED_SET_CEILING,
            "router (%d) + playbook (%d) = %d exceeds the growth ceiling %d"
            % (router, playbook, total, LOADED_SET_CEILING),
        )
        self.assertGreater(
            total, V1_HALF_BAR,
            "loaded set now fits the ≤half bar (%d) — promote it to an enforced test" % V1_HALF_BAR,
        )


class ContractTokenGateTests(unittest.TestCase):
    def test_no_github_ops_or_old_namespace_or_op_names_or_pids(self):
        forbidden = FORBIDDEN_CONTRACT_TOKENS
        for path in _iter_md(SKILL_DIR):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                hit = forbidden.search(line)
                self.assertIsNone(
                    hit,
                    "forbidden token under skills/question-resolver/ at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )

    def test_no_v1_skill_names(self):
        for path in _iter_md(SKILL_DIR):
            hits = retired_name_hits(path.read_text(encoding="utf-8"))
            self.assertEqual(hits, [], "%s names a retired v1 skill" % path.name)

    def test_no_raw_persist_or_gather_writes_in_fences(self):
        raw_write = re.compile(
            r"\bgh\s+(issue|pr)\s+(create|edit|comment|review|close|reopen|merge)\b"
            r"|\bgh\s+api\b[^\n]*\bDELETE\b"
        )
        for path in _iter_md(SKILL_DIR):
            for i, line, in_fence in _fence_stripped_lines(path):
                if not in_fence:
                    continue
                hit = raw_write.search(line)
                self.assertIsNone(
                    hit,
                    "raw gh write in a code fence at %s:%d — %r"
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


class QuestionDecisionByteIdentityTests(unittest.TestCase):
    """DoD box 4 offline half: the `<!-- question-decision:v1 -->` decision-comment schema the resolve
    flow renders is byte-for-byte the frozen S1 capture (prd.md §7, row 4)."""

    MARKER = "<!-- question-decision:v1 -->"

    def test_flow_decision_fence_matches_the_s1_capture(self):
        flow_text = (PLAYBOOKS_DIR / FLOW).read_text(encoding="utf-8")
        example_text = QUESTION_DECISION_EXAMPLE.read_text(encoding="utf-8")
        flow_fence = _extract_marked_fence(flow_text, self.MARKER)
        example_fence = _extract_marked_fence(example_text, self.MARKER)
        self.assertIsNotNone(flow_fence, "resolve-flow.md has no `<!-- question-decision:v1 -->` fence")
        self.assertIsNotNone(example_fence, "the S1 capture has no `<!-- question-decision:v1 -->` fence")
        self.assertEqual(
            flow_fence, example_fence,
            "the resolve flow restates the decision-comment schema divergently from the S1 capture",
        )


class ReentrancyMechanicsTests(unittest.TestCase):
    """DoD box 4: revise replaces (never duplicates); close is a re-run-safe no-op; reopen offered."""

    def setUp(self):
        self.flow = (PLAYBOOKS_DIR / FLOW).read_text(encoding="utf-8")
        self.router = ROUTER.read_text(encoding="utf-8")

    def test_revise_passes_delete_marker_id_to_replace(self):
        self.assertIn("--delete-marker-id", self.flow)
        self.assertRegex(self.flow, r"replaced, not duplicated")

    def test_close_is_a_no_op_on_already_closed(self):
        # tolerant of the flow's line-wrap between "issue" and "is a no-op".
        combined = re.sub(r"\s+", " ", self.flow + " " + self.router)
        self.assertRegex(combined, r"already-closed issue is a no-op|no-op on an already-closed issue")

    def test_reopen_is_offered_in_the_reentrant_case(self):
        self.assertIn("gh_persist.py reopen", self.flow)

    def test_close_uses_gh_persist(self):
        self.assertIn("gh_persist.py close", self.flow)
        self.assertIn("--reason completed", self.flow)


class ConstraintAuditCarryTests(unittest.TestCase):
    """The constraint-audit sub-agent prompt is carried (architecture.md §9 authorship rule allows carrying
    a judgment sub-agent prompt a cutover names) — S11-clean (no retired-doc citation) and returns findings."""

    def setUp(self):
        self.text = CONSTRAINT_AUDIT.read_text(encoding="utf-8")

    def test_reference_exists_and_returns_findings(self):
        self.assertTrue(CONSTRAINT_AUDIT.is_file())
        self.assertIn("## Constraint audit", self.text)
        self.assertRegex(self.text, r"Findings:")

    def test_no_retired_signal_doc_citation(self):
        self.assertNotIn("subagent-decision-signal", self.text)

    def test_flow_dispatches_the_constraint_audit_before_recording(self):
        flow = (PLAYBOOKS_DIR / FLOW).read_text(encoding="utf-8")
        self.assertIn("references/constraint-audit-prompt.md", flow)
        self.assertRegex(flow, r"BLOCKER")


class ReaderAndStackTests(unittest.TestCase):
    _BARE_STACK = re.compile(r"\b(swift|xcode|xcb\.sh|foodjournal|rails|rspec|pytest)\b", re.IGNORECASE)

    def test_reader_reached_at_the_sweep_home(self):
        flow = (PLAYBOOKS_DIR / FLOW).read_text(encoding="utf-8")
        self.assertIn("skills/question-sweep/references/question-status-reader-prompt.md", flow)

    def test_loaded_prompt_has_no_bare_stack_token(self):
        for path in (ROUTER, PLAYBOOKS_DIR / FLOW):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                hit = self._BARE_STACK.search(line)
                self.assertIsNone(
                    hit,
                    "bare stack token in the loaded prompt at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )


if __name__ == "__main__":
    unittest.main()
