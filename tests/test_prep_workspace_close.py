"""Unit tests for scripts/prep_workspace_close.py — the v3 operator-side workspace closer.

Topology mirrors the other prep tests. Contract under test: branch-arg and issue-number
resolution (the linked / worktree / guarded-PR-head ladder), the teardown-then-gated-removal
receipt, the dirty/unpushed `AMBIGUOUS` gate, the `cwd_inside_target` refusal, and the review-M2
merged-PR semantics (a clean worktree at exactly the merged head is removable; extra post-merge
commits get the merged-specific card, never the generic push-first wording) — which must hold for
BOTH argument forms, since a branch name is the form every evaluator merge terminal hands over.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPT = SCRIPTS_DIR / "prep_workspace_close.py"

sys.path.insert(0, str(SCRIPTS_DIR))

import branching  # noqa: E402  (import after sys.path setup, by necessity)
from tests.support import envelope_asserts, gitsandbox, shimenv  # noqa: E402

CANNED_HEAD_OID = "deadbeef00112233445566778899aabbccddeeff"

# The live-reported branch/issue pair (issue #93, whose sibling story is #92) — the fixtures for the
# branch-argument merged close and the sibling-PR mis-resolution are both keyed on it.
MERGED_BRANCH = "93-a1-2-patient-onboard-pay"


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


class PrepWorkspaceCloseSandboxTestCase(unittest.TestCase):
    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.scratch = self._tmp_ctx.name
        self.addCleanup(self._tmp_ctx.cleanup)

    def _mk_worktree(self, branch):
        wt = self.root / ".worktrees" / branch
        wt.parent.mkdir(parents=True, exist_ok=True)
        _git(["worktree", "add", "-b", branch, str(wt), "origin/main"], self.root)
        return wt

    def _run(self, args, fixture_case=None, extra_env=None, cwd=None):
        env = shimenv.intercepted_env(base_env=os.environ, fixture_case=fixture_case)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + args,
            env=env,
            cwd=cwd,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def _envelope(self, target, fixture_case=None, fixtures_dir=None, cwd=None):
        args = [target, "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch]
        if fixtures_dir is not None:
            result = self._run(
                args, extra_env={"GH_SHIM_FIXTURES": str(fixtures_dir)}, cwd=cwd
            )
        else:
            result = self._run(args, fixture_case=fixture_case, cwd=cwd)
        self.assertEqual(result.returncode, 0, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        return envelope


class ScriptExistsTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))


class BranchArgTests(PrepWorkspaceCloseSandboxTestCase):
    def test_clean_worktree_is_torn_down_and_removed_no_gh_calls(self):
        # A branch-name argument needs no gh at all — no fixture case is set, and the shim exits
        # loudly on any call, so passing proves the zero-gh path.
        wt = self._mk_worktree("42-fix-thing")
        # The teardown command must not leave files INSIDE the worktree (git worktree remove
        # refuses on untracked leftovers — same discipline as test_workspace.py's teardown case).
        marker = Path(self.scratch) / "teardown-ran.txt"
        _write(
            self.root / "CLAUDE.md",
            "<!-- worktree-teardown -->\n- `touch %s`\n<!-- /worktree-teardown -->\n" % marker,
        )
        envelope = self._envelope("42-fix-thing")
        self.assertEqual(envelope["status"], "ok")
        self.assertTrue(envelope["removed"])
        self.assertEqual(envelope["branch_resolution"], {
            "input": "42-fix-thing", "branch": "42-fix-thing", "via": "arg",
        })
        self.assertEqual(envelope["teardown"]["commands_run"], 1)
        self.assertFalse(wt.is_dir())

    def test_not_found_is_a_safe_no_op(self):
        envelope = self._envelope("42-never-opened")
        self.assertEqual(envelope["status"], "ok")
        self.assertFalse(envelope["removed"])
        self.assertEqual(envelope["reason"], "not_found")

    def test_dirty_worktree_is_gated_and_retained(self):
        wt = self._mk_worktree("42-fix-thing")
        _write(wt / "uncommitted.txt", "dirt\n")
        envelope = self._envelope("42-fix-thing")
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertTrue(wt.is_dir(), "the worktree must be left in place")

    def test_close_from_inside_the_target_is_a_workspace_mismatch(self):
        wt = self._mk_worktree("42-fix-thing")
        envelope = self._envelope("42-fix-thing", cwd=str(wt))
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "WORKSPACE_MISMATCH")
        self.assertEqual(envelope["decision"]["context"]["reason"], "cwd_inside_target")
        self.assertTrue(wt.is_dir())


class IssueResolutionTests(PrepWorkspaceCloseSandboxTestCase):
    def test_issue_number_resolves_via_the_linked_branch(self):
        wt = self._mk_worktree("100-custom-linked")
        envelope = self._envelope("100", fixture_case="prep_workspace_close_issue_linked")
        self.assertEqual(envelope["branch_resolution"]["branch"], "100-custom-linked")
        self.assertEqual(envelope["branch_resolution"]["via"], "linked")
        self.assertTrue(envelope["removed"])
        self.assertFalse(wt.is_dir())


class MergedPrTests(PrepWorkspaceCloseSandboxTestCase):
    """Review M2: routine post-merge close. A squash-merged branch's commits count 'unpushed'
    against the origin/main fallback — the merged-PR context must make the clean-at-merged-head
    case removable, and give the extra-commits case a merged-specific card."""

    def _stamped_fixture(self, head_sha, case="prep_workspace_close_merged"):
        src = shimenv.fixture_case_dir(case)
        dst = Path(tempfile.mkdtemp(prefix="gh-close-stamp-"))
        self.addCleanup(lambda: shutil.rmtree(str(dst), ignore_errors=True))
        for f in src.iterdir():
            (dst / f.name).write_bytes(
                f.read_bytes().replace(CANNED_HEAD_OID.encode("ascii"), head_sha.encode("ascii"))
            )
        return dst

    def _mk_squash_merged_worktree(self, branch="100-custom-linked"):
        """A worktree whose commits were 'squash-merged': the branch has real local commits that
        are NOT ancestors of origin/main (so the unpushed fallback counts them), and its PR is
        recorded MERGED with head_oid == the worktree HEAD."""
        wt = self._mk_worktree(branch)
        _write(wt / "feature.txt", "the change\n")
        _git(["add", "feature.txt"], wt)
        _git(["commit", "-m", "the squashed work"], wt)
        return wt, _git(["rev-parse", "HEAD"], wt)

    def test_clean_worktree_at_the_merged_head_is_removable(self):
        wt, head = self._mk_squash_merged_worktree()
        envelope = self._envelope("100", fixtures_dir=self._stamped_fixture(head))
        self.assertEqual(envelope["status"], "ok", envelope)
        self.assertTrue(envelope["removed"])
        self.assertFalse(wt.is_dir())

    def test_extra_post_merge_commits_get_the_merged_specific_card(self):
        wt, head = self._mk_squash_merged_worktree()
        fixtures = self._stamped_fixture(head)
        _write(wt / "extra.txt", "post-merge work\n")
        _git(["add", "extra.txt"], wt)
        _git(["commit", "-m", "post-merge local commit"], wt)
        envelope = self._envelope("100", fixtures_dir=fixtures)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertIn("merged", envelope["decision"]["summary"])
        self.assertNotIn("push the branch", " ".join(envelope["decision"]["options"]))
        self.assertTrue(wt.is_dir())

    # --- the branch-ARGUMENT form: what the evaluator's merge terminal actually hands over ------
    # The merged-PR lookup used to be derived only on the numeric path, so this whole leg was
    # unreachable and every routine post-merge close by branch name hit the generic push-first card.

    def test_branch_arg_at_the_merged_head_is_removable(self):
        wt, head = self._mk_squash_merged_worktree(branch=MERGED_BRANCH)
        envelope = self._envelope(
            MERGED_BRANCH,
            fixtures_dir=self._stamped_fixture(head, case="prep_workspace_close_merged_head"),
        )
        self.assertEqual(envelope["status"], "ok", envelope)
        self.assertTrue(envelope["removed"])
        self.assertEqual(envelope["branch_resolution"]["via"], "arg")
        self.assertFalse(wt.is_dir())

    def test_branch_arg_lookup_failure_degrades_to_the_generic_gate(self):
        """No auth, no network, an older `gh` — the lookup is non-fatal: today's card plus a
        notice, never an AUTH_REQUIRED that would block reclaiming an abandoned workspace."""
        wt, _head = self._mk_squash_merged_worktree(branch=MERGED_BRANCH)
        envelope = self._envelope(
            MERGED_BRANCH, fixture_case="prep_workspace_close_head_lookup_unavailable"
        )
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertIn("MERGED_PR_LOOKUP_UNAVAILABLE", envelope["notices"])
        self.assertTrue(wt.is_dir())


class BranchBelongsToIssueTests(unittest.TestCase):
    """The convention test the ladder's rungs 2/3 filter on — every branch this pipeline mints goes
    through `compute_branch_name` or the `epic/<N>-<slug>` form, so this is what separates "this
    issue's branch" from a sibling's."""

    def test_accepts_the_minted_forms(self):
        for branch in (MERGED_BRANCH, "93-a1-2-patient-onboard-pay-v2", "epic/93-a1-onboarding"):
            self.assertTrue(branching.branch_belongs_to_issue(branch, 93), branch)

    def test_rejects_another_issues_branch_and_digit_prefix_collisions(self):
        for branch in (
            "92-a1-1-patient-discover-land",  # the live mis-resolution
            "930-other-story",  # a longer number sharing the leading digits
            "epic/92-a1-onboarding",
            "93",  # the bare number is not a `<N>-<slug>` branch
            "",
            None,
        ):
            self.assertFalse(branching.branch_belongs_to_issue(branch, 93), branch)


class SiblingPrMentionTests(PrepWorkspaceCloseSandboxTestCase):
    """The live #93 mis-resolution: `open_prs`/`closed_prs` come from a `#<N> in:body` full-text
    search, so a sibling story's PR that merely mentions this issue is in the candidate set. Taking
    `[0]` of it resolved issue #93 to `92-a1-1-patient-discover-land` — another story's branch."""

    FIXTURE = "prep_workspace_close_sibling_pr_mention"

    def test_local_worktree_wins_over_a_sibling_prs_head(self):
        wt = self._mk_worktree(MERGED_BRANCH)
        envelope = self._envelope("93", fixture_case=self.FIXTURE)
        self.assertEqual(envelope["branch_resolution"]["branch"], MERGED_BRANCH)
        self.assertEqual(envelope["branch_resolution"]["via"], "worktree")
        self.assertTrue(envelope["removed"])
        self.assertFalse(wt.is_dir())

    def test_a_mention_only_head_never_resolves(self):
        envelope = self._envelope("93", fixture_case=self.FIXTURE)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertEqual(
            envelope["decision"]["context"]["rejected_pr_heads"],
            ["92-a1-1-patient-discover-land"],
        )
        self.assertNotIn("92-a1-1-patient-discover-land", json.dumps(envelope["decision"]["summary"]))

    def test_two_worktrees_for_one_issue_are_ambiguous(self):
        first = self._mk_worktree(MERGED_BRANCH)
        second = self._mk_worktree("93-a1-2-patient-onboard-pay-v2")
        envelope = self._envelope("93", fixture_case=self.FIXTURE)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertEqual(
            envelope["decision"]["context"]["candidates"],
            [MERGED_BRANCH, "93-a1-2-patient-onboard-pay-v2"],
        )
        self.assertTrue(first.is_dir())
        self.assertTrue(second.is_dir())


if __name__ == "__main__":
    unittest.main()
