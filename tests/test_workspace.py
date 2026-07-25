"""Unit tests for scripts/workspace.py — the S4 workspace-lifecycle owner (architecture.md §6, §3,
§12; docs/implementation.md S4).

``workspace.py`` shells out only to real ``git`` (an allowed spawnable, architecture.md §1) against
a temp origin+clone built by ``tests/support/gitsandbox.py`` — per architecture.md §10, "Git
sandbox: ... no shim needed," these tests never touch ``tests/shim/gh`` and never invoke ``gh`` at
all. Hook-execution tests additionally author a small ``CLAUDE.md`` with
``<!-- worktree-setup/teardown -->`` marker blocks directly in the sandboxed clone (config-block
fixtures, per the S4 DoD's "hook cases use config-block fixtures" — authored inline here rather
than reusing the S21 interior-only fixture bodies, since every test already builds a full repo
root via gitsandbox and a marker block is a two-line addition to that same root).

Every subprocess invocation of ``workspace.py`` itself goes through :func:`_run_cli`, mirroring
``tests/test_config_block.py``'s ``_run_cli`` exactly (real subprocess, explicit UTF-8 decoding,
inherited environment) — the end-to-end path a caller (a v2 prep script, S6+) actually uses.

Design notes these tests pin down (see the implementor report's "Notes for the reviewer" for the
full rationale):

- ``remove --work``'s "never pushed at all" unpushed-count fallback is ``origin/main`` (the
  subcommand has no ``--base``), not the worktree's original base — this can OVER-count for a
  story branch off an unmerged epic branch, never UNDER-count.
- The dirty/unpushed ``remove --work`` refusal uses the closed-set ``AMBIGUOUS`` code (no bespoke
  code exists for this hazard; prd.md itself groups "a dirty root" under "ambiguous state" as a
  mechanical blocker).
"""

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
WORKSPACE_PY = SCRIPTS_DIR / "workspace.py"

sys.path.insert(0, str(SCRIPTS_DIR))

import workspace  # noqa: E402  (import after sys.path setup, by necessity)
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR  # noqa: E402
from tests.support import envelope_asserts, gitsandbox  # noqa: E402


def _run_cli(args, cwd=None):
    """Invoke ``workspace.py`` as a real subprocess. Returns ``(returncode, stdout_text,
    stderr_text)`` — mirrors ``tests/test_config_block.py``'s ``_run_cli`` exactly."""
    completed = subprocess.run(
        [sys.executable, str(WORKSPACE_PY)] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(os.environ),
    )
    return (
        completed.returncode,
        completed.stdout.decode("utf-8"),
        completed.stderr.decode("utf-8"),
    )


def _parse_one_envelope(stdout_text):
    """Parse exactly one JSON object from ``stdout_text`` (architecture.md §3's "exactly one JSON
    envelope on stdout"). Fails the test if it isn't exactly one non-blank line of valid JSON."""
    lines = [line for line in stdout_text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise AssertionError(
            "expected exactly one non-blank stdout line (the envelope), got %d: %r"
            % (len(lines), lines)
        )
    return json.loads(lines[0])


def _git(args, cwd):
    result = subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, encoding="utf-8", check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("git %s (cwd=%s) failed: %s" % (" ".join(args), cwd, result.stderr))
    return result.stdout.strip()


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


class WorkspaceHelperUnitTests(unittest.TestCase):
    """Direct, in-process tests of workspace's pure helper functions — no git, no subprocess."""

    def test_slugify_ref_collapses_slashes(self):
        self.assertEqual(workspace._slugify_ref("epic/42-journal"), "epic-42-journal")

    def test_slugify_ref_leaves_simple_name_untouched(self):
        self.assertEqual(workspace._slugify_ref("main"), "main")

    def test_slugify_ref_replaces_other_unsafe_characters(self):
        self.assertEqual(workspace._slugify_ref("feature@x!y"), "feature-x-y")

    def test_work_path_is_dot_worktrees_branch(self):
        path = workspace._work_path("/repo", "feature-x")
        self.assertEqual(path, Path("/repo/.worktrees/feature-x").resolve())

    def test_read_path_is_dot_worktrees_ro_prefixed_slug(self):
        path = workspace._read_path("/repo", "epic/42-journal")
        self.assertEqual(path, Path("/repo/.worktrees/ro-epic-42-journal").resolve())

    def test_parse_command_list_extracts_backtick_span_ignoring_description(self):
        lines = [
            "- `echo one` — does a thing",
            "- `echo two` — does another thing",
            "not a list item",
        ]
        self.assertEqual(workspace._parse_command_list(lines), ["echo one", "echo two"])

    def test_parse_command_list_empty_interior_yields_empty_list(self):
        self.assertEqual(workspace._parse_command_list([]), [])

    def test_find_includes_matches_path_like_at_tokens_only(self):
        # @anthropic has no slash and no dotted extension, so it must NOT be treated as an
        # include (v1's find_includes: excludes bare @mentions).
        text = "See @docs/COMMANDS.md and @anthropic and also @CONTRIBUTING.md for more."
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "f.md"
            _write(f, text)
            includes = workspace._find_includes(f)
        self.assertEqual(includes, ["docs/COMMANDS.md", "CONTRIBUTING.md"])

    def test_find_includes_nonexistent_file_returns_empty(self):
        self.assertEqual(workspace._find_includes(Path("/no/such/file.md")), [])

    def test_tail_lines_keeps_only_last_n(self):
        text = "\n".join("line%d" % i for i in range(1, 101))
        result = workspace._tail_lines(text, 50)
        self.assertEqual(result.splitlines()[0], "line51")
        self.assertEqual(result.splitlines()[-1], "line100")

    def test_tail_lines_handles_empty_text(self):
        self.assertEqual(workspace._tail_lines("", 50), "")

    def test_tail_lines_handles_none(self):
        self.assertEqual(workspace._tail_lines(None, 50), "")


class WorktreesExcludeMaintenanceTests(unittest.TestCase):
    """`.worktrees/` idempotent exclude maintenance (architecture.md §6, D6 fix: this now writes
    the repo's `info/exclude` — resolved via `git rev-parse --git-common-dir`, never
    `<root>/.gitignore` — so the write can never appear in `git status --porcelain` and can never
    trip root-freshness's `ROOT_DIRTY` check on its own idempotent bootstrap write (the D6 defect:
    a prep script calling `ensure` more than once in one clone, e.g. the planner's composite
    epic+story session, fell off prep mid-run). `_ensure_worktrees_excluded` needs a real git repo
    (it shells out to `git rev-parse`), so `setUp` runs a plain `git init` — no origin/clone needed
    for these pure exclude-mechanics tests."""

    def setUp(self):
        import tempfile
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_ctx.name).resolve()
        self.addCleanup(self._tmp_ctx.cleanup)
        _git(["init", "-q"], self.tmp)
        self.exclude_path = self.tmp / ".git" / "info" / "exclude"

    def test_creates_exclude_from_scratch_when_info_dir_present(self):
        # `git init` already creates `.git/info/exclude` (with template comments) by default —
        # this asserts the append path, not the from-scratch-file-creation path (covered below by
        # deleting it first).
        changed = workspace._ensure_worktrees_excluded(self.tmp)
        self.assertTrue(changed)
        self.assertIn(".worktrees/\n", self.exclude_path.read_text(encoding="utf-8"))

    def test_creates_exclude_and_info_dir_from_scratch_when_both_absent(self):
        import shutil
        shutil.rmtree(self.tmp / ".git" / "info")
        self.assertFalse(self.exclude_path.exists())
        changed = workspace._ensure_worktrees_excluded(self.tmp)
        self.assertTrue(changed)
        self.assertEqual(self.exclude_path.read_text(encoding="utf-8"), ".worktrees/\n")

    def test_appends_to_existing_exclude_missing_the_entry(self):
        _write(self.exclude_path, "*.pyc\n")
        changed = workspace._ensure_worktrees_excluded(self.tmp)
        self.assertTrue(changed)
        self.assertEqual(self.exclude_path.read_text(encoding="utf-8"), "*.pyc\n.worktrees/\n")

    def test_appends_newline_first_when_file_has_no_trailing_newline(self):
        _write(self.exclude_path, "*.pyc")
        workspace._ensure_worktrees_excluded(self.tmp)
        self.assertEqual(self.exclude_path.read_text(encoding="utf-8"), "*.pyc\n.worktrees/\n")

    def test_second_call_is_a_byte_level_noop_and_leaves_mtime_untouched(self):
        workspace._ensure_worktrees_excluded(self.tmp)
        mtime_before = self.exclude_path.stat().st_mtime_ns

        changed = workspace._ensure_worktrees_excluded(self.tmp)
        self.assertFalse(changed)
        mtime_after = self.exclude_path.stat().st_mtime_ns
        self.assertEqual(
            mtime_before, mtime_after,
            "an already-present entry must leave the file byte-for-byte untouched (not even mtime)",
        )

    def test_entry_present_anywhere_in_file_is_recognized_not_just_at_end(self):
        _write(self.exclude_path, ".worktrees/\n*.pyc\n")
        changed = workspace._ensure_worktrees_excluded(self.tmp)
        self.assertFalse(changed)
        self.assertEqual(self.exclude_path.read_text(encoding="utf-8"), ".worktrees/\n*.pyc\n")

    def test_tolerates_surrounding_whitespace_on_the_existing_line(self):
        _write(self.exclude_path, "  .worktrees/  \n")
        changed = workspace._ensure_worktrees_excluded(self.tmp)
        self.assertFalse(changed)

    def test_never_touches_gitignore_working_tree_file(self):
        # D6's own regression: the write must land ONLY in info/exclude, never in a working-tree
        # .gitignore this function could see or create.
        changed = workspace._ensure_worktrees_excluded(self.tmp)
        self.assertTrue(changed)
        self.assertFalse((self.tmp / ".gitignore").exists())

    def test_leaves_a_pre_existing_gitignore_bootstrap_line_untouched(self):
        # A .gitignore an earlier (pre-fix) v2 run left behind is harmless dead weight — this
        # function must not migrate, rewrite, or remove it (D6 fix constraint 2).
        _write(self.tmp / ".gitignore", ".worktrees/\n")
        changed = workspace._ensure_worktrees_excluded(self.tmp)
        self.assertTrue(changed)  # info/exclude still gets its own entry
        self.assertEqual(
            (self.tmp / ".gitignore").read_text(encoding="utf-8"), ".worktrees/\n",
            "a pre-existing .gitignore bootstrap line must be left byte-for-byte alone",
        )

    def test_git_common_dir_resolves_correctly_from_inside_a_linked_worktree(self):
        # Verified live against real git behavior (not assumed): --git-common-dir from INSIDE a
        # linked worktree resolves to the MAIN repo's shared .git dir (never the worktree's own
        # private per-worktree admin dir, which --git-dir would return instead) — the property
        # this fix relies on for "applies to all linked worktrees."
        _git(["config", "user.email", "test@test.com"], self.tmp)
        _git(["config", "user.name", "test"], self.tmp)
        _write(self.tmp / "README.md", "seed\n")
        _git(["add", "README.md"], self.tmp)
        _git(["commit", "-q", "-m", "seed"], self.tmp)
        wt_path = self.tmp / "wt"
        _git(["worktree", "add", "-q", "-b", "feature-x", str(wt_path)], self.tmp)
        self.addCleanup(lambda: _git(["worktree", "remove", "-f", str(wt_path)], self.tmp))

        common_from_root = workspace._git_common_dir(self.tmp)
        common_from_worktree = workspace._git_common_dir(wt_path)
        self.assertEqual(common_from_root, common_from_worktree)
        self.assertEqual(common_from_root, (self.tmp / ".git").resolve())

        # A write from inside the worktree's context must land in the SAME shared file.
        changed = workspace._ensure_worktrees_excluded(wt_path)
        self.assertTrue(changed)
        self.assertIn(".worktrees/\n", self.exclude_path.read_text(encoding="utf-8"))


def _seed_repo_with_hooks(seed_dir, setup_block=None, teardown_block=None, in_file="CLAUDE.md"):
    """Write a small ``CLAUDE.md`` (or ``COMMANDS.md``) with the given marker blocks into an
    already-cloned seed working directory, then commit + push it — a config-block fixture built
    inline (S4 DoD: "hook cases use config-block fixtures ... or author small ones")."""
    lines = []
    if setup_block is not None:
        lines.append("<!-- worktree-setup -->")
        lines.extend(setup_block)
        lines.append("<!-- /worktree-setup -->")
        lines.append("")
    if teardown_block is not None:
        lines.append("<!-- worktree-teardown -->")
        lines.extend(teardown_block)
        lines.append("<!-- /worktree-teardown -->")
        lines.append("")
    _write(Path(seed_dir) / in_file, "\n".join(lines) + "\n")
    _git(["add", in_file], seed_dir)
    _git(["commit", "-m", "add worktree hook blocks"], seed_dir)
    _git(["push", "origin", "HEAD:main"], seed_dir)


class WorkspaceGitSandboxTestCase(unittest.TestCase):
    """Shared setup for every test below that needs a real temp origin+clone."""

    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path
        # No .gitignore pre-seed needed (D6 fix): the `.worktrees/` exclusion now lands in
        # info/exclude, outside the working tree, so it can never appear in `git status
        # --porcelain` and can never trip ROOT_DIRTY on its own idempotent write — a fresh clone's
        # very first ensure/root-freshness check is clean with no bootstrap workaround required.

    def _run(self, args):
        rc, out, err = _run_cli(args + ["--root", str(self.root)])
        return rc, out, err

    def _envelope(self, args):
        rc, out, err = self._run(args)
        self.assertEqual(rc, EXIT_OK, "stderr: %s" % err)
        envelope = _parse_one_envelope(out)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        return envelope


class EnsureWorkTests(WorkspaceGitSandboxTestCase):
    def test_create_reports_facts_and_is_not_reused(self):
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["op"], "ensure")
        self.assertEqual(envelope["kind"], "work")
        self.assertEqual(envelope["branch"], "feature-x")
        self.assertEqual(envelope["base_ref"], "main")
        self.assertFalse(envelope["reused"])
        self.assertFalse(envelope["dirty"])
        self.assertEqual(envelope["unpushed_commits"], 0)
        self.assertTrue((self.root / ".worktrees" / "feature-x").is_dir())
        self.assertEqual(len(envelope["sha"]), 40)

    def test_reuse_of_existing_worktree_reports_reused_true(self):
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertTrue(envelope["reused"])

    def test_existing_origin_branch_checks_out_at_the_branch_head_not_base(self):
        # The regression test (S6-pilot fixup): an EXISTING branch on origin (e.g. a PR head) with
        # no worktree yet and no local ref in this clone — the exact cross-compat/fresh-clone shape
        # an evaluator hits. Before the fix this unconditionally created the worktree at
        # origin/main's head; it must land at origin/feature-x's head instead.
        other_clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(other_clone.cleanup)
        _git(["checkout", "-b", "feature-x"], other_clone.path)
        _write(other_clone.path / "pr-only.txt", "content only on the PR branch\n")
        _git(["add", "pr-only.txt"], other_clone.path)
        _git(["commit", "-m", "PR branch commit main does not have"], other_clone.path)
        _git(["push", "origin", "feature-x"], other_clone.path)
        expected_sha = _git(["rev-parse", "feature-x"], other_clone.path)
        main_sha = _git(["rev-parse", "origin/main"], self.root)
        self.assertNotEqual(expected_sha, main_sha, "the fixture must actually diverge from main")

        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["status"], "ok")
        self.assertFalse(envelope["reused"])
        self.assertEqual(envelope["base_ref"], "main", "base_ref stays the PR base for unpushed-count semantics")
        self.assertEqual(
            envelope["sha"], expected_sha,
            "worktree HEAD must be origin/feature-x's head, not origin/main's",
        )
        wt = self.root / ".worktrees" / "feature-x"
        self.assertEqual(_git(["rev-parse", "HEAD"], wt), expected_sha)
        self.assertTrue((wt / "pr-only.txt").exists(), "must have the PR branch's actual content")
        self.assertEqual(envelope["unpushed_commits"], 0, "worktree HEAD == origin/feature-x, nothing unpushed")

    def test_existing_local_branch_with_no_worktree_is_attached_not_recreated(self):
        # A local `feature-x` ref exists (e.g. left behind by a worktree removed earlier) but no
        # worktree currently has it checked out. `git worktree add -b` would fail with "branch
        # already exists"; the fix must attach the existing branch instead of crashing, and still
        # land it at origin/feature-x's head (not leave it at whatever stale commit the local ref
        # pointed to).
        other_clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(other_clone.cleanup)
        _git(["checkout", "-b", "feature-x"], other_clone.path)
        _write(other_clone.path / "pr-only.txt", "content only on the PR branch\n")
        _git(["add", "pr-only.txt"], other_clone.path)
        _git(["commit", "-m", "PR branch commit main does not have"], other_clone.path)
        _git(["push", "origin", "feature-x"], other_clone.path)
        expected_sha = _git(["rev-parse", "feature-x"], other_clone.path)

        # Create a LOCAL branch ref in self.root pointing at the stale pre-push main tip, with no
        # worktree attached to it (plain `git branch`, not `checkout -b`, never attaches HEAD).
        stale_sha = _git(["rev-parse", "origin/main"], self.root)
        _git(["branch", "feature-x", stale_sha], self.root)
        self.assertNotEqual(stale_sha, expected_sha)

        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["status"], "ok")
        self.assertFalse(envelope["reused"])
        self.assertEqual(
            envelope["sha"], expected_sha,
            "must fast-forward/reset the pre-existing local branch to origin/feature-x's head",
        )
        wt = self.root / ".worktrees" / "feature-x"
        self.assertEqual(_git(["rev-parse", "HEAD"], wt), expected_sha)
        self.assertTrue((wt / "pr-only.txt").exists())

    def test_reused_worktree_reports_dirty_true_when_it_has_uncommitted_changes(self):
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        _write(self.root / ".worktrees" / "feature-x" / "scratch.txt", "uncommitted\n")
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertTrue(envelope["reused"])
        self.assertTrue(envelope["dirty"])

    def test_reports_unpushed_commit_count_relative_to_base_when_never_pushed(self):
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        wt = self.root / ".worktrees" / "feature-x"
        _write(wt / "new.txt", "content\n")
        _git(["add", "new.txt"], wt)
        _git(["commit", "-m", "one new commit"], wt)
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["unpushed_commits"], 1)

    def test_unpushed_count_relative_to_remote_branch_once_pushed(self):
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        wt = self.root / ".worktrees" / "feature-x"
        _write(wt / "new.txt", "content\n")
        _git(["add", "new.txt"], wt)
        _git(["commit", "-m", "first commit"], wt)
        _git(["push", "origin", "feature-x"], wt)
        _write(wt / "new2.txt", "content2\n")
        _git(["add", "new2.txt"], wt)
        _git(["commit", "-m", "second commit, not pushed"], wt)
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["unpushed_commits"], 1)

    def test_branch_in_use_elsewhere_returns_decision_and_creates_nothing(self):
        import tempfile
        elsewhere = Path(tempfile.mkdtemp(prefix="gh-pipeline-test-elsewhere-")).resolve()
        self.addCleanup(lambda: __import__("shutil").rmtree(elsewhere, ignore_errors=True))
        _git(["worktree", "add", str(elsewhere), "-b", "feature-y"], self.root)

        envelope = self._envelope(["ensure", "--work", "feature-y", "--base", "main"])
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "BRANCH_IN_USE")
        self.assertEqual(envelope["decision"]["context"]["existing_path"], str(elsewhere))
        self.assertFalse((self.root / ".worktrees" / "feature-y").exists())

    def test_ensures_worktrees_excluded_via_info_exclude_after_create(self):
        # D6 fix: the exclusion lands in info/exclude, never <root>/.gitignore. Two ensures in a
        # row (D6's own regression) must not duplicate the entry, and — the core of D6 — must not
        # leave the working tree dirty (the self-inflicted-ROOT_DIRTY bug this replaces).
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self._envelope(["ensure", "--work", "feature-y", "--base", "main"])
        text = (self.root / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertEqual(text.count(".worktrees/"), 1)
        self.assertFalse((self.root / ".gitignore").exists())
        self.assertEqual(_git(["status", "--porcelain"], self.root), "", "root must stay clean")

    def test_root_not_on_main_short_circuits_before_any_worktree_op(self):
        _git(["checkout", "-b", "not-main"], self.root)
        self.addCleanup(lambda: _git(["checkout", "main"], self.root))
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "ROOT_NOT_ON_MAIN")
        self.assertFalse((self.root / ".worktrees").exists())

    def test_root_dirty_short_circuits_before_any_worktree_op(self):
        _write(self.root / "dirty.txt", "uncommitted\n")
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "ROOT_DIRTY")
        self.assertFalse((self.root / ".worktrees").exists())

    def test_root_diverged_short_circuits_before_any_worktree_op(self):
        # Diverge the ORIGIN ahead of root, then commit something local to root too, so a plain
        # fetch + ff-only cannot reconcile them.
        other_clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(other_clone.cleanup)
        _write(other_clone.path / "origin-side.txt", "origin moved\n")
        _git(["add", "origin-side.txt"], other_clone.path)
        _git(["commit", "-m", "origin-side commit"], other_clone.path)
        _git(["push", "origin", "HEAD:main"], other_clone.path)

        _write(self.root / "root-side.txt", "root moved locally\n")
        _git(["add", "root-side.txt"], self.root)
        _git(["commit", "-m", "root-side local commit"], self.root)

        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "ROOT_DIVERGED")
        self.assertFalse((self.root / ".worktrees").exists())

    def test_root_freshness_happy_path_ff_updates_and_records_sha(self):
        other_clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(other_clone.cleanup)
        _write(other_clone.path / "origin-side.txt", "origin moved\n")
        _git(["add", "origin-side.txt"], other_clone.path)
        _git(["commit", "-m", "origin-side commit"], other_clone.path)
        _git(["push", "origin", "HEAD:main"], other_clone.path)
        expected_sha = _git(["rev-parse", "HEAD"], other_clone.path)

        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["sha"], expected_sha, "root must have fast-forwarded to origin's new HEAD")
        self.assertEqual(_git(["rev-parse", "HEAD"], self.root), expected_sha)

    def test_missing_base_flag_is_a_usage_error(self):
        rc, out, err = self._run(["ensure", "--work", "feature-x"])
        self.assertEqual(rc, EXIT_USAGE_ERROR)
        self.assertEqual(out, "")


class EnsureReadTests(WorkspaceGitSandboxTestCase):
    def test_create_is_detached_at_origin_ref_and_reports_sha(self):
        expected_sha = _git(["rev-parse", "origin/main"], self.root)
        envelope = self._envelope(["ensure", "--read", "main"])
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["kind"], "read")
        self.assertEqual(envelope["ref"], "main")
        self.assertFalse(envelope["reused"])
        self.assertEqual(envelope["sha"], expected_sha)
        path = Path(envelope["path"])
        self.assertTrue(path.is_dir())
        # `rev-parse --abbrev-ref HEAD` returns the literal string "HEAD" for a detached
        # checkout (unlike `symbolic-ref`, it does not fail, so no non-zero-exit special-casing
        # is needed here).
        head_ref = _git(["rev-parse", "--abbrev-ref", "HEAD"], path)
        self.assertEqual(head_ref, "HEAD", "a read workspace must be detached, not on a branch")

    def test_path_uses_ro_prefixed_slug(self):
        envelope = self._envelope(["ensure", "--read", "main"])
        self.assertTrue(Path(envelope["path"]).name, "ro-main")

    def test_reensure_resets_to_current_origin_sha_discarding_local_changes(self):
        first = self._envelope(["ensure", "--read", "main"])
        read_path = Path(first["path"])
        _write(read_path / "local-scratch.txt", "will be discarded\n")

        other_clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(other_clone.cleanup)
        _write(other_clone.path / "moved.txt", "origin moved on\n")
        _git(["add", "moved.txt"], other_clone.path)
        _git(["commit", "-m", "origin advances"], other_clone.path)
        _git(["push", "origin", "HEAD:main"], other_clone.path)
        expected_sha = _git(["rev-parse", "HEAD"], other_clone.path)

        second = self._envelope(["ensure", "--read", "main"])
        self.assertTrue(second["reused"])
        self.assertEqual(second["sha"], expected_sha)
        self.assertFalse((read_path / "local-scratch.txt").exists(), "reset --hard must discard local changes")
        self.assertTrue((read_path / "moved.txt").exists(), "must reflect origin's new content")

    def test_ensure_read_does_not_require_root_freshness(self):
        # Root is dirty/off-main; ensure --read must still succeed (architecture.md §6 scoping:
        # read grounds directly at a fetched origin ref, not off root's own HEAD).
        _git(["checkout", "-b", "not-main"], self.root)
        self.addCleanup(lambda: _git(["checkout", "main"], self.root))
        envelope = self._envelope(["ensure", "--read", "main"])
        self.assertEqual(envelope["status"], "ok")

    def test_ensure_read_also_maintains_worktrees_exclude(self):
        self._envelope(["ensure", "--read", "main"])
        text = (self.root / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertIn(".worktrees/", text)
        self.assertFalse((self.root / ".gitignore").exists())

    def test_ensure_read_root_freshness_check_survives_a_prior_ensure_in_the_same_clone(self):
        # D6's own regression, at the ensure --read call site: `ensure --read` writes info/exclude
        # (no root-freshness gate of its own), but a LATER `ensure --work`/`root-status` call in
        # the SAME clone must not see that prior write as ROOT_DIRTY -- the exact composite-session
        # symptom (a second prep call fell off prep onto gh_gather mid-run).
        self._envelope(["ensure", "--read", "main"])
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["status"], "ok")
        root_status = self._envelope(["root-status"])
        self.assertEqual(root_status["status"], "ok")

    def test_root_dirty_guard_keeps_its_teeth_after_info_exclude_write(self):
        # The D6 fix must not weaken ROOT_DIRTY into a no-op: after a prior ensure --read has
        # written info/exclude (which must NOT dirty root), a genuine USER-authored uncommitted
        # working-tree file must still trip ROOT_DIRTY on the next freshness check.
        self._envelope(["ensure", "--read", "main"])
        _write(self.root / "user-dirty.txt", "a real uncommitted change\n")
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "ROOT_DIRTY")


class RemoveWorkTests(WorkspaceGitSandboxTestCase):
    def test_not_found_is_a_clean_noop(self):
        envelope = self._envelope(["remove", "--work", "never-created"])
        self.assertEqual(envelope["status"], "ok")
        self.assertFalse(envelope["removed"])
        self.assertEqual(envelope["reason"], "not_found")

    def test_clean_worktree_runs_teardown_then_removes(self):
        _seed_repo_with_hooks(
            self.clone.path,
            teardown_block=["- `echo teardown-ran` — best-effort marker"],
        )
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        envelope = self._envelope(["remove", "--work", "feature-x"])
        self.assertEqual(envelope["status"], "ok")
        self.assertTrue(envelope["removed"])
        self.assertEqual(envelope["teardown"]["commands_run"], 1)
        self.assertTrue(envelope["teardown"]["succeeded"])
        self.assertFalse((self.root / ".worktrees" / "feature-x").exists())
        worktrees_after = _git(["worktree", "list"], self.root)
        self.assertNotIn("feature-x", worktrees_after)

    def test_dirty_worktree_returns_ambiguous_decision_and_does_not_remove(self):
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        _write(self.root / ".worktrees" / "feature-x" / "dirty.txt", "uncommitted\n")
        envelope = self._envelope(["remove", "--work", "feature-x"])
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertTrue(envelope["decision"]["context"]["dirty"])
        self.assertTrue((self.root / ".worktrees" / "feature-x").exists(), "must not remove on a dirty refusal")

    def test_unpushed_worktree_returns_ambiguous_decision_and_does_not_remove(self):
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        wt = self.root / ".worktrees" / "feature-x"
        _write(wt / "new.txt", "content\n")
        _git(["add", "new.txt"], wt)
        _git(["commit", "-m", "unpushed commit"], wt)
        envelope = self._envelope(["remove", "--work", "feature-x"])
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertEqual(envelope["decision"]["context"]["unpushed_commits"], 1)
        self.assertTrue(wt.exists(), "must not remove on an unpushed refusal")

    def test_clean_and_pushed_worktree_with_zero_unpushed_removes_successfully(self):
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        wt = self.root / ".worktrees" / "feature-x"
        _write(wt / "new.txt", "content\n")
        _git(["add", "new.txt"], wt)
        _git(["commit", "-m", "a commit"], wt)
        _git(["push", "origin", "feature-x"], wt)
        envelope = self._envelope(["remove", "--work", "feature-x"])
        self.assertEqual(envelope["status"], "ok")
        self.assertTrue(envelope["removed"])

    def test_teardown_failure_is_best_effort_and_does_not_block_removal(self):
        _seed_repo_with_hooks(
            self.clone.path,
            teardown_block=[
                "- `exit 7` — always fails",
                "- `echo second-step-still-ran` — must still run",
            ],
        )
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        envelope = self._envelope(["remove", "--work", "feature-x"])
        self.assertEqual(envelope["status"], "ok")
        self.assertTrue(envelope["removed"])
        self.assertTrue(envelope["teardown"]["succeeded"], "teardown always reports succeeded=true")
        self.assertEqual(envelope["teardown"]["commands_run"], 2, "best-effort continues past a failure")
        self.assertEqual(len(envelope["teardown"]["failures"]), 1)
        self.assertFalse((self.root / ".worktrees" / "feature-x").exists())


class SetupHookExecutionTests(WorkspaceGitSandboxTestCase):
    """`ensure --work`'s fail-fast setup-hook execution, via config-block fixtures."""

    def test_no_block_present_is_a_clean_noop(self):
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertFalse(envelope["setup"]["phase_present"])
        self.assertEqual(envelope["setup"]["commands_run"], 0)
        self.assertTrue(envelope["setup"]["succeeded"])

    def test_all_commands_succeed_and_run_in_declared_order(self):
        _seed_repo_with_hooks(
            self.clone.path,
            setup_block=[
                "- `echo one >> order.txt` — first",
                "- `echo two >> order.txt` — second",
            ],
        )
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertTrue(envelope["setup"]["phase_present"])
        self.assertEqual(envelope["setup"]["commands_run"], 2)
        self.assertTrue(envelope["setup"]["succeeded"])
        order_file = Path(envelope["path"]) / "order.txt"
        self.assertEqual(order_file.read_text(encoding="utf-8"), "one\ntwo\n")

    def test_failure_stops_before_later_commands_and_reports_first_failure(self):
        _seed_repo_with_hooks(
            self.clone.path,
            setup_block=[
                "- `echo before-fail` — runs",
                "- `exit 9` — fails",
                "- `echo should-not-run > should-not-exist.txt` — must never run",
            ],
        )
        rc, out, err = self._run(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertEqual(rc, 1, "a failing setup hook is a hard error, matching v1 exit 1")
        envelope = _parse_one_envelope(out)
        self.assertFalse(envelope["setup"]["succeeded"])
        self.assertEqual(envelope["setup"]["commands_run"], 2)
        self.assertEqual(envelope["setup"]["first_failure"]["step"], 2)
        self.assertEqual(envelope["setup"]["first_failure"]["command"], "exit 9")
        self.assertFalse((Path(envelope["path"]) / "should-not-exist.txt").exists())
        # The worktree itself is NOT auto-removed on a failed setup — matching v1: the caller
        # decides what to do with a worktree that exists but isn't ready.
        self.assertTrue(Path(envelope["path"]).is_dir())

    def test_setup_reruns_on_every_reuse_idempotently(self):
        _seed_repo_with_hooks(
            self.clone.path,
            setup_block=["- `echo ran >> marker.txt` — appends every entry"],
        )
        self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertTrue(envelope["reused"])
        self.assertTrue(envelope["setup"]["phase_present"])
        self.assertEqual(envelope["setup"]["commands_run"], 1)
        marker = Path(envelope["path"]) / "marker.txt"
        self.assertEqual(marker.read_text(encoding="utf-8"), "ran\nran\n")

    def test_block_discovered_via_commands_md_takes_priority_over_claude_md(self):
        _seed_repo_with_hooks(
            self.clone.path,
            setup_block=["- `echo from-claude-md >> which.txt` — should be shadowed"],
            in_file="CLAUDE.md",
        )
        _seed_repo_with_hooks(
            self.clone.path,
            setup_block=["- `echo from-commands-md >> which.txt` — should win"],
            in_file="COMMANDS.md",
        )
        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        which = Path(envelope["path"]) / "which.txt"
        self.assertEqual(which.read_text(encoding="utf-8"), "from-commands-md\n")

    def test_block_discovered_via_at_include_from_claude_md(self):
        _write(
            self.clone.path / "CLAUDE.md",
            "See @docs/HOOKS.md for the worktree hook configuration.\n",
        )
        (self.clone.path / "docs").mkdir(exist_ok=True)
        _write(
            self.clone.path / "docs" / "HOOKS.md",
            "<!-- worktree-setup -->\n- `echo from-include >> which.txt` — via @include\n"
            "<!-- /worktree-setup -->\n",
        )
        _git(["add", "CLAUDE.md", "docs/HOOKS.md"], self.clone.path)
        _git(["commit", "-m", "hooks via include"], self.clone.path)
        _git(["push", "origin", "HEAD:main"], self.clone.path)

        envelope = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self.assertTrue(envelope["setup"]["phase_present"])
        which = Path(envelope["path"]) / "which.txt"
        self.assertEqual(which.read_text(encoding="utf-8"), "from-include\n")


class GcTests(WorkspaceGitSandboxTestCase):
    def _backdate(self, path, days):
        old = time.time() - days * 86400
        os.utime(str(path), (old, old))

    def test_removes_only_aged_ro_star_worktrees(self):
        young = self._envelope(["ensure", "--read", "main"])
        self.assertTrue(True)  # young stays default-age (just created)
        # Create a second, distinct ref-slug so we have two ro-* worktrees to distinguish.
        other_clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(other_clone.cleanup)
        _git(["branch", "other-ref"], other_clone.path)
        _git(["push", "origin", "other-ref"], other_clone.path)
        old = self._envelope(["ensure", "--read", "other-ref"])

        self._backdate(old["path"], 10)

        envelope = self._envelope(["gc"])
        self.assertEqual(envelope["removed"], [old["path"]])
        self.assertEqual(envelope["skipped"], [young["path"]])
        self.assertFalse(Path(old["path"]).exists())
        self.assertTrue(Path(young["path"]).exists())

    def test_adversarial_aged_work_worktree_survives_gc(self):
        work = self._envelope(["ensure", "--work", "feature-x", "--base", "main"])
        self._backdate(work["path"], 30)
        envelope = self._envelope(["gc", "--max-age", "0"])
        self.assertNotIn(work["path"], envelope["removed"])
        self.assertTrue(Path(work["path"]).is_dir(), "a work worktree must survive gc regardless of age")

    def test_max_age_zero_removes_a_freshly_created_ro_worktree(self):
        read = self._envelope(["ensure", "--read", "main"])
        envelope = self._envelope(["gc", "--max-age", "0"])
        self.assertIn(read["path"], envelope["removed"])
        self.assertFalse(Path(read["path"]).exists())

    def test_fresh_ro_worktree_survives_default_max_age(self):
        read = self._envelope(["ensure", "--read", "main"])
        envelope = self._envelope(["gc"])
        self.assertEqual(envelope["removed"], [])
        self.assertIn(read["path"], envelope["skipped"])
        self.assertTrue(Path(read["path"]).exists())


class RootStatusTests(WorkspaceGitSandboxTestCase):
    def test_happy_path_reports_branch_and_sha(self):
        envelope = self._envelope(["root-status"])
        self.assertEqual(envelope["op"], "root-status")
        self.assertEqual(envelope["branch"], "main")
        self.assertEqual(envelope["sha"], _git(["rev-parse", "HEAD"], self.root))

    def test_root_not_on_main(self):
        _git(["checkout", "-b", "not-main"], self.root)
        self.addCleanup(lambda: _git(["checkout", "main"], self.root))
        envelope = self._envelope(["root-status"])
        self.assertEqual(envelope["decision"]["code"], "ROOT_NOT_ON_MAIN")

    def test_root_dirty(self):
        _write(self.root / "dirty.txt", "x\n")
        envelope = self._envelope(["root-status"])
        self.assertEqual(envelope["decision"]["code"], "ROOT_DIRTY")

    def test_root_diverged(self):
        other_clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(other_clone.cleanup)
        _write(other_clone.path / "origin-side.txt", "x\n")
        _git(["add", "origin-side.txt"], other_clone.path)
        _git(["commit", "-m", "origin moves"], other_clone.path)
        _git(["push", "origin", "HEAD:main"], other_clone.path)
        _write(self.root / "root-side.txt", "y\n")
        _git(["add", "root-side.txt"], self.root)
        _git(["commit", "-m", "root moves locally"], self.root)
        envelope = self._envelope(["root-status"])
        self.assertEqual(envelope["decision"]["code"], "ROOT_DIVERGED")


class LintTests(WorkspaceGitSandboxTestCase):
    def test_lint_setup_no_block_present(self):
        envelope = self._envelope(["lint", "setup"])
        self.assertEqual(envelope["op"], "lint")
        self.assertEqual(envelope["phase"], "setup")
        self.assertFalse(envelope["phase_present"])
        self.assertEqual(envelope["command_count"], 0)
        self.assertEqual(envelope["would_run"], [])

    def test_lint_setup_reports_discovered_commands_without_running_them(self):
        _seed_repo_with_hooks(
            self.clone.path,
            setup_block=["- `echo would-run-1` — one", "- `echo would-run-2` — two"],
        )
        envelope = self._envelope(["lint", "setup"])
        self.assertTrue(envelope["phase_present"])
        self.assertEqual(envelope["command_count"], 2)
        self.assertEqual(envelope["would_run"], ["echo would-run-1", "echo would-run-2"])
        # lint performs NO worktree operation and runs NOTHING.
        self.assertFalse((self.root / ".worktrees").exists())

    def test_lint_teardown_independent_of_setup_block(self):
        _seed_repo_with_hooks(
            self.clone.path,
            setup_block=["- `echo s` — setup"],
            teardown_block=["- `echo t` — teardown"],
        )
        setup_lint = self._envelope(["lint", "setup"])
        teardown_lint = self._envelope(["lint", "teardown"])
        self.assertEqual(setup_lint["would_run"], ["echo s"])
        self.assertEqual(teardown_lint["would_run"], ["echo t"])

    def test_lint_invalid_phase_is_a_usage_error(self):
        rc, out, err = self._run(["lint", "bogus"])
        self.assertEqual(rc, EXIT_USAGE_ERROR)
        self.assertEqual(out, "")


class UsageErrorTests(unittest.TestCase):
    """Bare usage-error paths not requiring a git sandbox."""

    def test_no_args_exits_2_with_no_envelope(self):
        rc, out, err = _run_cli([])
        self.assertEqual(rc, EXIT_USAGE_ERROR)
        self.assertEqual(out, "")

    def test_unknown_subcommand_exits_2_with_no_envelope(self):
        rc, out, err = _run_cli(["bogus"])
        self.assertEqual(rc, EXIT_USAGE_ERROR)
        self.assertEqual(out, "")

    def test_ensure_without_work_or_read_is_a_usage_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, err = _run_cli(["ensure", "--root", tmp])
        self.assertEqual(rc, EXIT_USAGE_ERROR)
        self.assertEqual(out, "")

    def test_ensure_with_both_work_and_read_is_a_usage_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, err = _run_cli(
                ["ensure", "--work", "x", "--read", "y", "--base", "main", "--root", tmp]
            )
        self.assertEqual(rc, EXIT_USAGE_ERROR)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
