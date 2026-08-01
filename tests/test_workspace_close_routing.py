"""Offline tests for the workspace-close skill (the v3 workspace-model inversion).

Shape-B standalone-tool gates: router structure + frontmatter pins
(`disable-model-invocation: true`), the contract-token grep set, the prep-invocation fence, and
the gated-removal language pins — dirty/unpushed is a decision card, never `--force` /
`git branch -D`; the tool refuses from inside the target; teardown is best-effort and never
blocks removal. No `references/` dir exists, so the fence-scoped gates below are this skill's
only prose regression net.
"""

import re
import unittest
from pathlib import Path

from tests.support.retired_tokens import FORBIDDEN_CONTRACT_TOKENS, retired_name_hits

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "workspace-close"
ROUTER = SKILL_DIR / "SKILL.md"
PLAYBOOKS_DIR = SKILL_DIR / "playbooks"
FLOW = "close-flow.md"

# A new v3 tool — no v1 counterpart, no ≤half-v1 metric (prd §10 is a pipeline-stage bar).
LOADED_SET_CEILING = 130


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


class RouterStructureTests(unittest.TestCase):
    def setUp(self):
        self.router_text = ROUTER.read_text(encoding="utf-8")

    def test_router_exists_and_frontmatter(self):
        self.assertTrue(ROUTER.is_file())
        head = "\n".join(self.router_text.splitlines()[:8])
        self.assertIn("name: workspace-close", head)
        self.assertNotIn("model:", head)
        self.assertNotIn("effort:", head)
        self.assertIn("disable-model-invocation: true", head)

    def test_exactly_one_playbook_on_disk(self):
        on_disk = {p.name for p in PLAYBOOKS_DIR.glob("*.md")}
        self.assertEqual(on_disk, {FLOW})

    def test_router_points_at_the_single_flow(self):
        self.assertIn("playbooks/close-flow.md", self.router_text)
        self.assertRegex(self.router_text, r"[Nn]o mode fork")

    def test_router_at_most_150_lines(self):
        n = len(self.router_text.splitlines())
        self.assertLessEqual(n, 150)

    def test_loaded_set_under_ceiling(self):
        total = len(self.router_text.splitlines()) + len(
            (PLAYBOOKS_DIR / FLOW).read_text(encoding="utf-8").splitlines()
        )
        self.assertLessEqual(total, LOADED_SET_CEILING)

    def test_prep_invocation_fence(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/prep_workspace_close.py", self.router_text)


class ContractTokenGateTests(unittest.TestCase):
    def test_no_forbidden_contract_tokens(self):
        for path in _iter_md(SKILL_DIR):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                hit = FORBIDDEN_CONTRACT_TOKENS.search(line)
                self.assertIsNone(
                    hit,
                    "forbidden token at %s:%d — %r"
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
                self.assertIsNone(
                    raw_write.search(line),
                    "raw gh write in a code fence at %s:%d" % (path.relative_to(REPO_ROOT), i),
                )

    def test_no_ref_arithmetic_in_fences(self):
        ref_arith = re.compile(r"git\s+show\s+[^\s]+:|git\s+grep\s+[^-]")
        for path in _iter_md(SKILL_DIR):
            for i, line, in_fence in _fence_stripped_lines(path):
                if in_fence:
                    self.assertIsNone(
                        ref_arith.search(line),
                        "ref arithmetic in a fence at %s:%d" % (path.relative_to(REPO_ROOT), i),
                    )

    def test_no_w_slash_shorthand(self):
        w_shorthand = re.compile(r"\bw/")
        for path in _iter_md(SKILL_DIR):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(w_shorthand.search(line))


class GatedRemovalLanguageTests(unittest.TestCase):
    """The safety language that must survive any edit: gating is the script's, never bypassed."""

    def setUp(self):
        self.router = ROUTER.read_text(encoding="utf-8")
        self.flow = (PLAYBOOKS_DIR / FLOW).read_text(encoding="utf-8")
        self.combined = re.sub(r"\s+", " ", self.router + " " + self.flow)

    def test_never_a_silent_discard(self):
        self.assertRegex(self.combined, r"[Nn]ever a silent discard")

    def test_force_bypass_is_banned_by_name(self):
        self.assertIn("git worktree remove --force", self.combined)
        self.assertIn("git branch -D", self.combined)
        self.assertRegex(self.combined, r"[Nn]ever bypass the gate")

    def test_refuses_from_inside_the_target(self):
        self.assertIn("cwd_inside_target", self.combined)

    def test_teardown_never_blocks_removal(self):
        self.assertRegex(self.combined, r"best-effort and never blocks removal")

    def test_merged_pr_card_language(self):
        self.assertRegex(self.combined, r"merged-specific card|merged head")

    def test_remote_branch_deletion_is_out_of_scope(self):
        self.assertIn("delete_branch_on_merge", self.combined)

    def test_summary_not_a_handoff(self):
        self.assertIn("Summary — not a `## Handoff`", self.router)


class StackAgnosticTests(unittest.TestCase):
    def test_no_stack_assumptions(self):
        stack = re.compile(r"swift|xcode|xcb\.sh|foodjournal|rails|rspec|pytest", re.IGNORECASE)
        for path in _iter_md(SKILL_DIR):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(
                    stack.search(line),
                    "stack assumption at %s:%d — %r" % (path.relative_to(REPO_ROOT), i, line),
                )


if __name__ == "__main__":
    unittest.main()
