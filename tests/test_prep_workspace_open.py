"""Unit tests for scripts/prep_workspace_open.py — the v3 operator-side workspace opener.

Topology mirrors tests/test_prep_resolver.py: `gh` through the offline shim, `git` through a real
temp origin+clone, the prep driven as a real subprocess. The opener's contract under test:
linked-first branch derivation (adopt, never re-mint), `gh issue develop` create with the
ISSUE_LINK_UNSUPPORTED degradation, the gated-row zero-side-effect rule, epic bootstrap ownership,
the continue row's no-link rule, and ROOT_*/BRANCH_IN_USE propagation from the composed ensure.
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
SCRIPT = SCRIPTS_DIR / "prep_workspace_open.py"

sys.path.insert(0, str(SCRIPTS_DIR))

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


class PrepWorkspaceOpenSandboxTestCase(unittest.TestCase):
    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.scratch = self._tmp_ctx.name
        self.addCleanup(self._tmp_ctx.cleanup)

    def _run(self, args, fixture_case=None, cwd=None):
        env = shimenv.intercepted_env(base_env=os.environ, fixture_case=fixture_case)
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + args,
            env=env,
            cwd=cwd,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def _envelope(self, issue="100", fixture_case="prep_workspace_open_fresh", expect_rc=0, cwd=None):
        result = self._run(
            [issue, "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case=fixture_case,
            cwd=cwd,
        )
        self.assertEqual(result.returncode, expect_rc, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        return envelope


class ScriptExistsTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))


class FreshOpenTests(PrepWorkspaceOpenSandboxTestCase):
    def test_fresh_create_links_and_opens_the_worktree(self):
        envelope = self._envelope()
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["branch"]["name"], "100-fix-the-widget")
        self.assertEqual(envelope["branch"]["base"], "main")
        self.assertEqual(envelope["branch"]["source"], "computed")
        self.assertTrue(envelope["link"]["attempted"])
        self.assertTrue(envelope["link"]["created"])
        wt = Path(envelope["workspace"]["path"])
        self.assertTrue(wt.is_dir())
        self.assertEqual(
            wt, (self.root / ".worktrees" / "100-fix-the-widget").resolve()
        )
        self.assertEqual(envelope["workspace"]["branch"], "100-fix-the-widget")
        self.assertFalse(envelope["workspace"]["reused"])
        self.assertIn("start the next session", envelope["next_step"])

    def test_plan_absence_is_a_fact_for_the_summary_routing(self):
        envelope = self._envelope()
        self.assertFalse(envelope["plan"]["present"])

    def test_reopen_is_idempotent_and_reports_reused(self):
        self._envelope()
        envelope = self._envelope()
        self.assertTrue(envelope["workspace"]["reused"])

    def test_setup_hooks_run_at_open(self):
        _write(
            self.root / "CLAUDE.md",
            "<!-- worktree-setup -->\n- `echo ran >> .hook-log`\n<!-- /worktree-setup -->\n",
        )
        _git(["add", "CLAUDE.md"], self.root)
        _git(["commit", "-m", "add setup hook block"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)
        envelope = self._envelope()
        self.assertTrue(envelope["workspace"]["setup"]["succeeded"])
        wt = Path(envelope["workspace"]["path"])
        self.assertIn("ran", (wt / ".hook-log").read_text(encoding="utf-8"))

    def test_hooks_come_from_the_worktree_the_operator_invoked_from(self):
        """The invoker's checkout supplies the hook block even when that checkout is a DIFFERENT
        worktree from the main one. `build_facts` normalizes `root` to the main checkout on its
        first line, so without threading the pre-normalization cwd through to `ensure --work` this
        silently falls back to the main checkout's version — the opposite of the documented rule
        that the operator picks the supplying branch by choosing where they stand."""
        _write(
            self.root / "CLAUDE.md",
            "<!-- worktree-setup -->\n- `echo main-checkout >> .hook-log`\n<!-- /worktree-setup -->\n",
        )
        _git(["add", "CLAUDE.md"], self.root)
        _git(["commit", "-m", "default-branch setup hook"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)

        other = self.root / ".worktrees" / "hook-experiment"
        other.parent.mkdir(parents=True, exist_ok=True)
        _git(["worktree", "add", "-b", "hook-experiment", str(other), "origin/main"], self.root)
        _write(
            other / "CLAUDE.md",
            "<!-- worktree-setup -->\n- `echo other-worktree >> .hook-log`\n<!-- /worktree-setup -->\n",
        )

        envelope = self._envelope(cwd=str(other))
        wt = Path(envelope["workspace"]["path"])
        log = (wt / ".hook-log").read_text(encoding="utf-8")
        self.assertIn("other-worktree", log)
        self.assertNotIn("main-checkout", log)
        self.assertEqual(envelope["workspace"]["setup"]["source"]["branch"], "hook-experiment")


class LinkedBranchTests(PrepWorkspaceOpenSandboxTestCase):
    def test_existing_linked_branch_is_adopted_verbatim(self):
        envelope = self._envelope(fixture_case="prep_workspace_open_adopt_linked")
        self.assertEqual(envelope["branch"]["name"], "100-custom-linked")
        self.assertEqual(envelope["branch"]["source"], "linked")
        self.assertEqual(envelope["link"]["existing"], ["100-custom-linked"])
        self.assertFalse(envelope["link"]["created"])
        self.assertIsNone(envelope["branch"]["collided_with"])
        self.assertEqual(envelope["workspace"]["branch"], "100-custom-linked")

    def test_multiple_linked_branches_is_ambiguous_with_no_side_effect(self):
        envelope = self._envelope(fixture_case="prep_workspace_open_multi_linked")
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertEqual(len(envelope["decision"]["context"]["candidates"]), 2)
        self.assertFalse((self.root / ".worktrees").exists())

    def test_link_unsupported_degrades_to_a_local_branch_with_a_notice(self):
        envelope = self._envelope(fixture_case="prep_workspace_open_link_unsupported")
        self.assertEqual(envelope["status"], "ok")
        self.assertIn("ISSUE_LINK_UNSUPPORTED", envelope["notices"])
        self.assertEqual(envelope["branch"]["name"], "100-fix-the-widget")
        self.assertFalse(envelope["link"]["created"])
        self.assertTrue(Path(envelope["workspace"]["path"]).is_dir())


class GatedRowTests(PrepWorkspaceOpenSandboxTestCase):
    def test_foreign_pr_row_reports_the_gate_with_zero_side_effects(self):
        envelope = self._envelope(fixture_case="prep_workspace_open_gated")
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["vector"]["mode"], "gated")
        gate = envelope["vector"]["gate"]
        self.assertEqual(gate["header"], "Stale PR")
        self.assertEqual(gate["options"], ["Take it over", "Start fresh"])
        self.assertNotIn("workspace", envelope)
        self.assertNotIn("branch", envelope)
        self.assertNotIn("link", envelope)
        self.assertFalse((self.root / ".worktrees").exists())


class ContinueRowTests(PrepWorkspaceOpenSandboxTestCase):
    def test_own_open_pr_reuses_its_head_branch_without_linking(self):
        # The manifest carries NO `gh issue develop` entries — the shim exits loudly on any
        # un-fixtured argv, so passing at all proves the continue row never touches linking.
        envelope = self._envelope(fixture_case="prep_workspace_open_continue")
        self.assertEqual(envelope["vector"]["mode"], "continue")
        self.assertEqual(envelope["branch"]["name"], "100-fix-the-widget")
        self.assertEqual(envelope["branch"]["source"], "pr-head")
        self.assertFalse(envelope["link"]["attempted"])
        self.assertTrue(Path(envelope["workspace"]["path"]).is_dir())


class EpicBootstrapTests(PrepWorkspaceOpenSandboxTestCase):
    def test_epic_bootstrap_creates_the_integration_branch(self):
        # v3: workspace-open owns epic integration-branch creation.
        envelope = self._envelope(fixture_case="prep_workspace_open_epic_bootstrap")
        self.assertEqual(envelope["vector"]["type"], "epic")
        self.assertEqual(envelope["branch"]["name"], "epic/100-sandbox-fixture")
        self.assertEqual(envelope["branch"]["source"], "epic-bootstrap")
        self.assertEqual(envelope["branch"]["base"], "main")
        self.assertTrue(Path(envelope["workspace"]["path"]).is_dir())


class StoryBaseTests(PrepWorkspaceOpenSandboxTestCase):
    def test_story_under_open_epic_bases_on_the_epic_branch(self):
        _git(["fetch", "origin"], self.root)
        _git(["branch", "epic/100-sandbox-fixture", "origin/main"], self.root)
        _git(["push", "origin", "epic/100-sandbox-fixture"], self.root)
        envelope = self._envelope(issue="101", fixture_case="prep_workspace_open_story_adopt")
        self.assertEqual(envelope["vector"]["type"], "story")
        self.assertEqual(envelope["branch"]["base"], "epic/100-sandbox-fixture")
        self.assertEqual(envelope["branch"]["name"], "101-linked-story")
        self.assertEqual(envelope["branch"]["source"], "linked")
        self.assertEqual(envelope["workspace"]["base_ref"], "epic/100-sandbox-fixture")


class EnsureGatePropagationTests(PrepWorkspaceOpenSandboxTestCase):
    def test_a_dirty_invoker_opens_and_the_notice_is_forwarded(self):
        """v3.x: ROOT_DIRTY is retired, and the ensure core's HOOK_SOURCE_DIRTY notice must reach
        the prep's own envelope — this prep used to discard the composed core's notices, which
        would have made the dirty-source report invisible to the operator."""
        _write(self.root / "dirty.txt", "uncommitted\n")
        envelope = self._envelope()
        self.assertEqual(envelope["status"], "ok")
        self.assertIn("HOOK_SOURCE_DIRTY", envelope["notices"])

    def test_branch_in_use_propagates(self):
        elsewhere_ctx = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere_ctx.cleanup)
        elsewhere = Path(elsewhere_ctx.name) / "elsewhere-wt"
        _git(["worktree", "add", str(elsewhere), "-b", "100-fix-the-widget"], self.root)
        envelope = self._envelope()
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "BRANCH_IN_USE")


if __name__ == "__main__":
    unittest.main()
