"""Offline tests for the evaluator skill (docs/implementation.md S7).

Two offline surfaces the S7 DoD/Testing section names:

1. **Routing-table fixtures** (`vector` → `playbooks/<file>`). The router's visible routing table
   (`skills/evaluator/SKILL.md` §2) is the contract that maps a prep-derived `vector.type` to the
   one playbook a session reads. These tests PARSE that table out of the router markdown and assert
   the mapping is (a) exactly the three PR types the vector can take, (b) each pointing at a real
   `playbooks/<file>` that exists on disk, and (c) byte-consistent with what
   `prep_evaluator._suggested_playbook` proposes for the same PR type — since the router "confirms
   `suggested_playbook` against the table" (architecture.md §5), a divergence between the table and
   the script would silently break routing with no offline harness to catch it otherwise.

2. **`--dry-run` persist envelopes.** Every GitHub write the playbooks specify goes through
   `gh_persist.py` (SKILL.md §3). These tests run each such invocation with `--dry-run` against the
   offline shim and assert the envelope is conformant (status ok, `would_run` present, no live gh
   call) — proving the exact persist invocations the playbooks name are well-formed, without a live
   repo. The merge executor (`gh pr merge`) and the draft-flip (`gh pr ready --undo`) are NOT
   gh_persist ops (no persist subcommand covers them — see the module's raw-gh note below), so they
   are not dry-run-tested here; they are covered by the parity protocol's live scenarios.

Structural router assertions (line counts, no PR-type conditionals, grep gates) live alongside the
routing-table parse so a single `python3 tests/run.py` catches a router that drifts out of the S7
size/shape bar.

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
SKILL_DIR = REPO_ROOT / "skills" / "evaluator"
ROUTER = SKILL_DIR / "SKILL.md"
PLAYBOOKS_DIR = SKILL_DIR / "playbooks"
GH_PERSIST = SCRIPTS_DIR / "gh_persist.py"

sys.path.insert(0, str(SCRIPTS_DIR))

import prep_evaluator  # noqa: E402  (import after sys.path setup, by necessity)
from tests.support import envelope_asserts, shimenv  # noqa: E402
from tests.support.retired_tokens import FORBIDDEN_CONTRACT_TOKENS  # noqa: E402


# ---------------------------------------------------------------------------
# Router routing-table parse
# ---------------------------------------------------------------------------

# The router's §2 table rows look like:  | `standard` | `playbooks/standard.md` | ... |
# First cell = a backticked vector.type; second cell = a backticked playbooks/<file>.
_ROUTE_ROW_RE = re.compile(
    r"^\|\s*`(?P<vector>[a-z-]+)`\s*\|\s*`(?P<playbook>playbooks/[a-z0-9-]+\.md)`\s*\|"
)


def _parse_router_routing_table(router_text):
    """Return an ordered dict {vector.type: playbooks/<file>} parsed from the router's routing
    table. Only rows whose first two cells are a backticked vector type and a backticked
    `playbooks/<file>` path count — the header row (`| `vector.type` | Playbook | … |`) and the
    separator row don't match, so the parse is robust to table position."""
    mapping = {}
    for line in router_text.splitlines():
        match = _ROUTE_ROW_RE.match(line)
        if match:
            mapping[match.group("vector")] = match.group("playbook")
    return mapping


class RouterRoutingTableTests(unittest.TestCase):
    def setUp(self):
        self.router_text = ROUTER.read_text(encoding="utf-8")
        self.table = _parse_router_routing_table(self.router_text)

    def test_router_exists_and_has_no_model_effort_pins(self):
        # Model/effort are not pinned — skills inherit the invoking session's model and effort.
        self.assertTrue(ROUTER.is_file(), "router SKILL.md must exist")
        head = "\n".join(self.router_text.splitlines()[:8])
        self.assertIn("name: evaluator", head)
        self.assertNotIn("model:", head)
        self.assertNotIn("effort:", head)

    def test_routing_table_covers_exactly_the_three_pr_types(self):
        # The vector.type set the evaluator can see is exactly {standard, story, epic-integration}
        # (prep_evaluator._detect_pr_type). The visible table must map each, and only these.
        self.assertEqual(
            set(self.table.keys()),
            {"standard", "story", "epic-integration"},
            "router routing table vectors must be exactly the three prep pr_types, got %r"
            % (sorted(self.table.keys()),),
        )

    def test_every_routed_playbook_file_exists(self):
        for vector, playbook in self.table.items():
            target = SKILL_DIR / playbook
            self.assertTrue(
                target.is_file(),
                "routing table maps %r -> %r but %s does not exist" % (vector, playbook, target),
            )

    def test_table_matches_prep_suggested_playbook_for_each_type(self):
        # architecture.md §5: prep proposes `suggested_playbook`; the router confirms it against the
        # table. A divergence would silently mis-route. Assert byte-consistency: for each PR type,
        # the table's target basename == prep's proposed basename.
        for pr_type, playbook in self.table.items():
            proposed = prep_evaluator._suggested_playbook(pr_type, "OPEN")
            self.assertEqual(
                Path(playbook).name,
                proposed,
                "router table maps %r -> %r but prep proposes %r"
                % (pr_type, Path(playbook).name, proposed),
            )

    def test_prep_suggested_playbook_only_targets_files_the_table_lists(self):
        # The reverse direction: every basename prep can propose is a file the table routes to (so
        # prep never suggests a playbook the router has no row for).
        table_basenames = {Path(p).name for p in self.table.values()}
        for pr_type in ("standard", "story", "epic-integration"):
            self.assertIn(prep_evaluator._suggested_playbook(pr_type, "OPEN"), table_basenames)

    def test_evaluate_spine_exists_and_is_referenced_by_every_routed_playbook(self):
        # architecture.md §5: a playbook may pull in its skill's single shared spine and nothing
        # else. Every routed playbook must reference evaluate-spine.md (they open by reading it).
        spine = PLAYBOOKS_DIR / "evaluate-spine.md"
        self.assertTrue(spine.is_file(), "the shared spine evaluate-spine.md must exist")
        for playbook in self.table.values():
            text = (SKILL_DIR / playbook).read_text(encoding="utf-8")
            self.assertIn(
                "evaluate-spine.md",
                text,
                "routed playbook %s must reference the shared spine evaluate-spine.md" % playbook,
            )


# ---------------------------------------------------------------------------
# Router structural bar (S7 DoD boxes 1 & 3)
# ---------------------------------------------------------------------------


class RouterStructuralBarTests(unittest.TestCase):
    def test_router_at_most_150_lines(self):
        n = len(ROUTER.read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(n, 150, "router SKILL.md is %d lines (bar: <= 150)" % n)

    def test_router_plus_largest_playbook_at_most_485(self):
        # S7 DoD box 7 / prd.md §10: router + largest playbook <= half of v1's 971 = 485.
        router_lines = len(ROUTER.read_text(encoding="utf-8").splitlines())
        playbook_lines = {
            p.name: len(p.read_text(encoding="utf-8").splitlines())
            for p in PLAYBOOKS_DIR.glob("*.md")
        }
        largest = max(playbook_lines.values())
        self.assertLessEqual(
            router_lines + largest,
            485,
            "router (%d) + largest playbook (%d) = %d exceeds 485 (half of v1's 971): %r"
            % (router_lines, largest, router_lines + largest, playbook_lines),
        )

    def test_playbook_bodies_have_no_pr_type_conditionals(self):
        # S7 DoD box 1: playbook bodies contain no PR-type conditionals (no `if story … else …`).
        # The route IS the branch; a playbook is a linear narrative. Flag any `if <pr-type> …`
        # branching construct in a body.
        banned = re.compile(
            r"\bif\b[^.\n]{0,40}\b(story|standard|epic-integration|epic integration)\b"
            r"[^.\n]{0,40}\belse\b",
            re.IGNORECASE,
        )
        for playbook in PLAYBOOKS_DIR.glob("*.md"):
            for i, line in enumerate(playbook.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(
                    banned.search(line),
                    "playbook %s:%d looks like a PR-type conditional: %r"
                    % (playbook.name, i, line),
                )

    def test_no_forbidden_tokens_under_skill_dir(self):
        # S7 DoD box 3: zero retired-executor tokens, zero old skill-invocation namespace strings, zero v1
        # GATHER_/PERSIST_ op names anywhere under skills/evaluator/.
        forbidden = FORBIDDEN_CONTRACT_TOKENS
        for path in SKILL_DIR.rglob("*.md"):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                hit = forbidden.search(line)
                self.assertIsNone(
                    hit,
                    "forbidden contract token under skills/evaluator/ at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )

    def test_no_raw_gh_persist_or_gather_writes(self):
        # S7 DoD box 3: no raw `gh` writes that BYPASS gh_persist.py / gh_gather.py. The persist/
        # gather ops are gh issue|pr create/edit/comment/review/close/reopen and gh api ... DELETE.
        # The only raw `gh` commands allowed are the merge executor (`gh pr merge` — no persist op
        # exists for it) and the PR-state toggles (`gh pr ready --undo`, the read `gh pr view` /
        # `gh pr checks --watch`). Assert no persist-op-bypassing raw write appears.
        raw_write = re.compile(
            r"\bgh\s+(issue|pr)\s+(create|edit|comment|review|close|reopen)\b"
            r"|\bgh\s+api\b[^\n]*\bDELETE\b"
        )
        for path in SKILL_DIR.rglob("*.md"):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                # Allow the frozen `gh pr view … --json mergeStateStatus` read that appears in a
                # handoff Why example (a read, not a write) — it doesn't match raw_write anyway.
                hit = raw_write.search(line)
                self.assertIsNone(
                    hit,
                    "raw gh persist/gather WRITE bypassing a script at %s:%d — %r"
                    % (path.relative_to(REPO_ROOT), i, hit.group(0) if hit else None),
                )


# ---------------------------------------------------------------------------
# --dry-run persist envelopes for the writes the playbooks specify
# ---------------------------------------------------------------------------


def _run_persist(args, body_text=None):
    """Run gh_persist.py <args> as a real subprocess under the offline shim. When body_text is
    given, write it to a temp file and substitute the placeholder token @BODY@ in args with the
    path (so callers name the body inline). Returns (completed_process, parsed_envelope_or_None)."""
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
    """Each GitHub write the evaluator playbooks specify, run with --dry-run: a conformant envelope,
    status ok, `would_run` present, exit 0, no live gh call. These are the exact gh_persist
    invocation SHAPES the playbooks name (SKILL.md §3 / spine S3.5, S4-untick, S7-post; story route
    Actions 1-3; residual follow-up comment)."""

    def _assert_dry_run_ok(self, proc, envelope, expected_op):
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        self.assertIsNotNone(envelope, "expected exactly one envelope on stdout")
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope.get("status"), "ok")
        self.assertEqual(envelope.get("op"), expected_op)
        self.assertTrue(envelope.get("dry_run"))
        self.assertIn("would_run", envelope)

    def test_health_cache_comment_dry_run(self):
        # spine S3.5: gh_persist.py comment <repo> pr <PR> <health-cache.md> [--delete-marker-id …]
        proc, env = _run_persist(
            ["comment", "octo/widgets", "pr", "287", "@BODY@", "--delete-marker-id", "9911", "--dry-run"],
            body_text="<!-- pr-evaluator-health-cache:v1 -->\nbody\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_review_comment_dry_run_approve(self):
        # spine S7-post: gh_persist.py comment <repo> pr-review <PR> <review.md> --review-action approve
        proc, env = _run_persist(
            ["comment", "octo/widgets", "pr-review", "287", "@BODY@", "--review-action", "approve", "--dry-run"],
            body_text="APPROVE review body\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_review_comment_dry_run_soft_reject(self):
        # spine S7-post soft-reject: --review-action comment
        proc, env = _run_persist(
            ["comment", "octo/widgets", "pr-review", "287", "@BODY@", "--review-action", "comment", "--dry-run"],
            body_text="COMMENT soft-reject body\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_dod_untick_edit_body_dry_run(self):
        # spine S4-untick: gh_persist.py edit-body <repo> <issue> <issue-body-corrected.md>
        proc, env = _run_persist(
            ["edit-body", "octo/widgets", "101", "@BODY@", "--dry-run"],
            body_text="## Definition of done\n- [ ] X (resolver claimed phase 2, commit abc1234; evaluator rejected: mismatch)\n",
        )
        self._assert_dry_run_ok(proc, env, "edit-body")

    def test_story_close_dry_run(self):
        # story route Action 1: gh_persist.py close <repo> <story> --reason completed
        proc, env = _run_persist(
            ["close", "octo/widgets", "151", "--reason", "completed", "--dry-run"]
        )
        self._assert_dry_run_ok(proc, env, "close")

    def test_epic_checkbox_edit_body_dry_run(self):
        # story route Action 2: gh_persist.py edit-body <repo> <epic> <epic-body-updated.md>
        proc, env = _run_persist(
            ["edit-body", "octo/widgets", "150", "@BODY@", "--dry-run"],
            body_text="## Stories\n- [x] #151\n",
        )
        self._assert_dry_run_ok(proc, env, "edit-body")

    def test_delivery_log_comment_dry_run(self):
        # story route Action 3: gh_persist.py comment <repo> issue <epic> <delivery-log.md> [--delete-marker-id …]
        proc, env = _run_persist(
            ["comment", "octo/widgets", "issue", "150", "@BODY@", "--delete-marker-id", "7722", "--dry-run"],
            body_text="<!-- epic-delivery-log:v1 -->\n**Epic delivery log** — #150 Title\n- #151 — delivered: X @ `abc1234` (PR #287, merged 2026-07-04)\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_followups_pr_comment_dry_run(self):
        # standard/story/epic-integration residual filing: gh_persist.py comment <repo> pr <PR> <followups.md>
        proc, env = _run_persist(
            ["comment", "octo/widgets", "pr", "287", "@BODY@", "--dry-run"],
            body_text="Filed follow-ups:\n- #310\n",
        )
        self._assert_dry_run_ok(proc, env, "comment")

    def test_dry_run_makes_no_live_gh_call(self):
        # Belt-and-braces: the dry-run path must not touch gh at all. If it did, the offline shim
        # (with no fixture case set) would fail loudly on an unexpected argv, so a clean exit 0 with
        # a would_run envelope IS the proof no gh call fired — assert both here explicitly.
        proc, env = _run_persist(
            ["close", "octo/widgets", "151", "--reason", "completed", "--dry-run"]
        )
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        self.assertTrue(env.get("dry_run"))
        self.assertNotIn("url", env, "a dry-run must not carry a live-write url")


class SliceBackstopTests(unittest.TestCase):
    """The merge-time slice-closing backstop (#17). The resolver owns closing a slice as its last
    serving phase ships; the evaluator only catches slices an interrupted run left open, because a
    slice still open behind a merged parent leaves the rollup permanently short."""

    def setUp(self):
        self.story = re.sub(
            r"\s+", " ", (PLAYBOOKS_DIR / "story.md").read_text(encoding="utf-8").replace("**", "")
        )
        self.standard = re.sub(
            r"\s+", " ", (PLAYBOOKS_DIR / "standard.md").read_text(encoding="utf-8").replace("**", "")
        )
        self.epic = (PLAYBOOKS_DIR / "epic-integration.md").read_text(encoding="utf-8")

    def test_story_route_closes_the_stories_own_slices(self):
        self.assertRegex(self.story, r"close any of the story's own open sub-issues")
        self.assertIn("epic-story-hierarchy.md", self.story)

    def test_standard_route_closes_the_issues_slices_since_auto_close_does_not(self):
        """The parent auto-closes on merge into `main`; its sub-issues never do."""
        self.assertRegex(self.standard, r"its sub-issues do not")
        self.assertRegex(self.standard, r"close any remaining deliverable slices")

    def test_both_routes_frame_it_as_a_backstop_not_the_owner(self):
        for text, name in ((self.story, "story.md"), (self.standard, "standard.md")):
            self.assertRegex(text, r"backstop only", name)
            self.assertRegex(text, r"resolver normally closes each as its last serving phase ships", name)

    def test_neither_route_ticks_acceptance_criteria(self):
        """Two writers for one projection is the defect this avoids."""
        for text, name in ((self.story, "story.md"), (self.standard, "standard.md")):
            self.assertRegex(text, r"Don't tick the slices' `## Acceptance criteria` here", name)

    def test_epic_integration_is_untouched(self):
        """An epic's sub-issues are STORIES, not slices, and this route explicitly files no story
        bookkeeping — adding a slice sweep here would contradict that sentence."""
        self.assertIn("files no story bookkeeping", self.epic)
        self.assertNotIn("deliverable slice", self.epic)

    def test_slice_close_dry_run(self):
        proc, envelope = _run_persist(
            ["close", "octo/widgets", "104", "--reason", "completed", "--dry-run"]
        )
        self.assertEqual(proc.returncode, 0, msg="stderr: %s" % proc.stderr)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope.get("op"), "close")
        self.assertTrue(envelope.get("dry_run"))


class ArtifactRenderingByteCompatTests(unittest.TestCase):
    """The artifact renderings this skill writes must diff clean against the S1-captured v1 examples
    (S7 DoD box 2). Parses the fenced template block out of each reference and the matching example
    and asserts byte-equality of the template body."""

    EXAMPLES_DIR = REPO_ROOT / "docs" / "specs" / "examples"
    REFERENCES_DIR = SKILL_DIR / "references"

    @staticmethod
    def _fenced_blocks(path, fence):
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

    def test_health_cache_template_byte_compatible(self):
        mine = self._fenced_blocks(self.REFERENCES_DIR / "health-cache-comment.md", "````")[0]
        example = self._fenced_blocks(self.EXAMPLES_DIR / "pr-evaluator-health-cache.md", "````")[0]
        self.assertEqual(mine, example, "health-cache rendering diverges from the S1 example")

    def test_delivery_log_template_byte_compatible(self):
        mine = self._fenced_blocks(self.REFERENCES_DIR / "epic-delivery-log.md", "```")[0]
        example = self._fenced_blocks(self.EXAMPLES_DIR / "epic-delivery-log.md", "```")[0]
        self.assertEqual(mine, example, "delivery-log rendering diverges from the S1 example")

    def test_handoff_standard_terminal_byte_compatible(self):
        # v3: pinned against handoff-evaluator-v3.md (the operator-owned-workspace rendering,
        # which supersedes the S1 capture; that file stays unedited as the v2 historical record).
        example = self._fenced_blocks(self.EXAMPLES_DIR / "handoff-evaluator-v3.md", "```")[0]
        mine_blocks = self._fenced_blocks(self.REFERENCES_DIR / "handoff-renderings.md", "```")
        match = next(
            (b for b in mine_blocks if b.startswith("## Handoff") and "Add CSV export (#142) · merged" in b),
            None,
        )
        self.assertIsNotNone(match, "the standard-terminal handoff shape must be present")
        self.assertEqual(match, example, "standard-terminal handoff diverges from the S1 example")


class WorkspaceModelV3Tests(unittest.TestCase):
    """v3 workspace-model pins: no cleanup fence removes the worktree (the evaluator runs inside
    it), and the terminal/cleanup language hands the operator workspace-close."""

    def test_no_remove_work_invocation_anywhere(self):
        skill_dir = REPO_ROOT / "skills" / "evaluator"
        for path in sorted(skill_dir.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "remove --work", text,
                "%s still invokes worktree removal — that is workspace-close's, exclusively"
                % path.name,
            )

    def test_terminal_and_cleanup_language_hand_off_workspace_close(self):
        renderings = (REPO_ROOT / "skills" / "evaluator" / "references" / "handoff-renderings.md").read_text(encoding="utf-8")
        self.assertIn("worktree retained — release with workspace-close", renderings)
        self.assertIn("/github-pipeline:workspace-close", renderings)

    def test_router_names_workspace_mismatch(self):
        router = (REPO_ROOT / "skills" / "evaluator" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("WORKSPACE_MISMATCH", router)


if __name__ == "__main__":
    unittest.main()
