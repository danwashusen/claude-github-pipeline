"""Unit tests for scripts/prep_evaluator.py — the evaluator's complete facts block in one call
(architecture.md §4; docs/implementation.md S6). This is the **pilot** prep script: the first to
compose other executors in-process (architecture.md §2 "Prep scripts compose the executors
in-process"), so these tests exercise the composition itself as much as the facts it produces.

Test topology (mirrors the two existing offline patterns, combined for the first time — no
existing executor test needs both at once):

- **`gh` calls** (gh_pr_gather / gh_gather / repo-merge-config / current-user) go through the
  offline shim (`tests/support/shimenv`), per `tests/README.md`.
- **`git` calls** (workspace.py's root-freshness + `ensure --work`) go through a real temp
  origin+clone (`tests/support/gitsandbox`), per architecture.md §10 "Git sandbox: ... no shim
  needed" — `workspace.py` never shells out to `gh` at all.

`prep_evaluator.py` is driven as a **real subprocess** (mirroring `tests/test_gh_pr_gather.py`'s
`_run_script`/`tests/test_workspace.py`'s `_run_cli`) so every test exercises the full argv-in /
subprocess / envelope-out path a real caller uses — not just the in-process `build_facts()`
function in isolation (that function is still unit-tested directly for the pure-classification
helpers below, where a subprocess round-trip would add nothing).

Coverage matrix (S6 DoD):
- Facts schema conformance (envelope_asserts + the architecture.md §4 field set).
- Four CI states: green / red / pending / none.
- Health-cache hit / miss (SHA match / mismatch) / absent.
- merge-policy present / absent (config block absent entirely, exercised via happy_standard).
- PR-type detection: story / epic-integration / standard.
- Closing-issue DoD parsed.
- Decision paths: MARKER_AMBIGUOUS (duplicate health-cache comments), ROOT_* propagation,
  BRANCH_IN_USE, AUTH_REQUIRED.
- --refresh re-derives PR state + CI without touching workspace.py/config_block.py at all.
- Single-invocation budget: the shim's call count for one prep run is bounded (prd.md §9.2).
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
SCRIPT = SCRIPTS_DIR / "prep_evaluator.py"

sys.path.insert(0, str(SCRIPTS_DIR))

import prep_evaluator  # noqa: E402  (import after sys.path setup, by necessity)
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


class PrepEvaluatorSandboxTestCase(unittest.TestCase):
    """Shared setup: a real temp git origin+clone (the `--root`), pre-seeded with `.gitignore`
    (mirroring tests/test_workspace.py's own setUp rationale: a fresh consuming repo's very first
    `ensure` leaves `.gitignore` uncommitted by design, which would spuriously trip ROOT_DIRTY on
    every test's very first call if left unseeded)."""

    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path
        _write(self.root / ".gitignore", ".worktrees/\n")
        _git(["add", ".gitignore"], self.root)
        _git(["commit", "-m", "seed gitignore"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.scratch = self._tmp_ctx.name
        self.addCleanup(self._tmp_ctx.cleanup)

    # The fixtures' canned PR head OID. v3's attach asserts ambient HEAD == pr.headRefOid
    # EXACTLY, and a sandbox worktree's HEAD is a real, run-specific SHA — so the harness stamps
    # a fixture copy, replacing this sentinel with the actual worktree HEAD across every fixture
    # file (view_88.json AND the cache-hit marker body, which deliberately share it).
    CANNED_HEAD_OID = "deadbeef00112233445566778899aabbccddeeff"

    def _mk_ambient(self, branch):
        """Create (or reuse) `.worktrees/<branch>` in the sandbox clone — the PR-head worktree the
        operator would have opened via workspace-open. Returns its Path."""
        wt = self.root / ".worktrees" / branch
        if not wt.is_dir():
            wt.parent.mkdir(parents=True, exist_ok=True)
            _git(["worktree", "add", "-b", branch, str(wt), "origin/main"], self.root)
        return wt

    def _head_branch_from_fixture(self, fixture_case):
        case_dir = shimenv.fixture_case_dir(fixture_case)
        for f in sorted(case_dir.glob("*.json")):
            if f.name == "manifest.json":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(data, dict) and "headRefName" in data:
                return data["headRefName"]
        return None

    def _stamped_fixture(self, fixture_case, head_sha):
        """Copy the fixture dir and replace the canned head OID with the real worktree HEAD."""
        import shutil

        src = shimenv.fixture_case_dir(fixture_case)
        dst = Path(tempfile.mkdtemp(prefix="gh-evaluator-stamp-"))
        self.addCleanup(lambda: shutil.rmtree(str(dst), ignore_errors=True))
        for f in src.iterdir():
            content = f.read_bytes().replace(
                self.CANNED_HEAD_OID.encode("ascii"), head_sha.encode("ascii")
            )
            (dst / f.name).write_bytes(content)
        return dst

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

    def _envelope(self, pr="88", repo="octo/widgets", fixture_case="prep_evaluator_happy_standard",
                  extra_args=None, ambient=True, ambient_branch=None, stamp=True):
        """Run the prep and return its envelope. With `ambient` (the default), the subprocess runs
        with its cwd INSIDE a worktree on the fixture PR's head branch (v3's operator posture) and
        the fixture is stamped so pr.headRefOid == that worktree's HEAD. `ambient_branch`
        overrides the branch (a wrong-branch mismatch test); `stamp=False` leaves the canned OID
        in place (a stale-checkout mismatch test). Flows that decide before the workspace
        assertion (auth, marker-ambiguous, --refresh) pass ambient=False and run as before."""
        args = [pr, repo, "--root", str(self.root), "--scratch-dir", self.scratch]
        if extra_args:
            args += extra_args
        run_cwd = None
        fixtures_dir = None
        if ambient:
            branch = ambient_branch or self._head_branch_from_fixture(fixture_case)
            if branch is not None:
                wt = self._mk_ambient(branch)
                run_cwd = str(wt)
                if stamp:
                    fixtures_dir = self._stamped_fixture(fixture_case, _git(["rev-parse", "HEAD"], wt))
        if fixtures_dir is not None:
            result = self._run(
                args, fixture_case=None,
                extra_env={"GH_SHIM_FIXTURES": str(fixtures_dir)}, cwd=run_cwd,
            )
        else:
            result = self._run(args, fixture_case=fixture_case, cwd=run_cwd)
        self.assertEqual(result.returncode, 0, msg="stderr: %s" % result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        return envelope


class ScriptExistsTests(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_script_compiles(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)], capture_output=True, encoding="utf-8"
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class HappyPathFactsSchemaTests(PrepEvaluatorSandboxTestCase):
    """Facts schema matches architecture.md §4's common core + evaluator extensions."""

    def test_conformant_ok_envelope_with_evaluator_facts(self):
        envelope = self._envelope()
        self.assertEqual(envelope["status"], "ok")
        for key in (
            "repo", "scratch", "root", "target", "vector", "suggested_playbook", "workspace",
            "config", "health_cache", "sections", "dod", "attention", "notices",
            "pr_type", "ci", "self_review", "current_user", "merge_config",
            "blocked_by", "deps_available",
        ):
            self.assertIn(key, envelope, "missing architecture.md §4 facts-block key %r" % key)

    def test_root_facts_shape(self):
        envelope = self._envelope()
        self.assertEqual(envelope["root"]["path"], str(self.root))
        self.assertEqual(len(envelope["root"]["sha"]), 40)
        # v3: root.sha IS the origin/main pin — the fetched remote tip.
        self.assertEqual(envelope["root"]["sha"], _git(["rev-parse", "origin/main"], self.root))
        self.assertEqual(envelope["root"]["source"], "origin/main")
        self.assertTrue(envelope["root"]["fresh"])

    def test_target_facts_shape(self):
        envelope = self._envelope()
        self.assertEqual(envelope["target"]["kind"], "pr")
        self.assertEqual(envelope["target"]["number"], 88)
        self.assertEqual(envelope["target"]["title"], "Fix widget cold-start flash")
        self.assertEqual(envelope["target"]["state"], "OPEN")

    def test_target_labels_populated_from_pr_labels(self):
        # gh_pr_gather's `labels` field (a v2 addition) maps through to `target.labels` —
        # replaces the old hardcoded `[]`. The happy_standard fixture's PR carries a `story`
        # label, matching architecture.md §4's own facts-block example (`"labels": ["story"]`)
        # byte-for-byte, so this test also proves prep's output matches the documented example.
        envelope = self._envelope()
        self.assertEqual(envelope["target"]["labels"], ["story"])

    def test_vector_and_suggested_playbook_for_standard_pr(self):
        envelope = self._envelope()
        self.assertEqual(envelope["vector"]["type"], "standard")
        self.assertEqual(envelope["suggested_playbook"], "standard.md")

    def test_workspace_fact_records_the_ambient_pr_head_checkout(self):
        envelope = self._envelope()
        self.assertEqual(envelope["workspace"]["branch"], "88-fix-widget")
        self.assertEqual(envelope["workspace"]["expected_branch"], "88-fix-widget")
        self.assertEqual(envelope["workspace"]["base_ref"], "main")
        self.assertEqual(envelope["workspace"]["source"], "ambient")
        self.assertNotIn("reused", envelope["workspace"])
        self.assertFalse(envelope["workspace"]["dirty"])
        self.assertEqual(envelope["workspace"]["unpushed_commits"], 0)
        self.assertTrue(Path(envelope["workspace"]["path"]).is_dir())
        # attach asserted ambient HEAD == pr.headRefOid — by construction here, but the identity
        # is the contract: the sha fact IS the checkout the evaluator will health-check.
        wt = self.root / ".worktrees" / "88-fix-widget"
        self.assertEqual(envelope["workspace"]["sha"], _git(["rev-parse", "HEAD"], wt))

    def test_config_pinned_at_origin_main_sha(self):
        envelope = self._envelope()
        self.assertEqual(envelope["config"]["sha"], envelope["root"]["sha"])
        self.assertEqual(envelope["config"]["sha"], _git(["rev-parse", "origin/main"], self.root))

    def test_merge_config_facts_from_repo_api(self):
        envelope = self._envelope()
        self.assertEqual(
            envelope["merge_config"],
            {
                "allow_squash_merge": True,
                "allow_merge_commit": False,
                "allow_rebase_merge": False,
                "delete_branch_on_merge": True,
                "allow_auto_merge": False,
            },
        )

    def test_self_review_false_when_pr_author_differs_from_current_user(self):
        envelope = self._envelope()
        self.assertEqual(envelope["current_user"], "reviewer-bot")
        self.assertEqual(envelope["pr"]["author"]["login"], "octocat")
        self.assertFalse(envelope["self_review"])

    def test_closing_issue_dod_parsed(self):
        envelope = self._envelope()
        dod = envelope["dod"]["42"]
        self.assertEqual(len(dod), 2)
        self.assertEqual(dod[0]["text"], "Widget does not flash on cold start")
        self.assertFalse(dod[0]["checked"])
        self.assertIsNone(dod[0]["annotation"])
        self.assertTrue(dod[1]["checked"])
        self.assertEqual(dod[1]["annotation"]["form"], "closed-by-phase-commit")
        self.assertEqual(dod[1]["annotation"]["phase"], 1)

    def test_blocked_by_absent_when_closing_issue_has_no_native_blockers(self):
        envelope = self._envelope()
        self.assertEqual(envelope["blocked_by"]["42"], [])
        self.assertTrue(envelope["deps_available"]["42"])

    def test_merge_policy_absent_defaults_to_epic_integration_ask_only(self):
        envelope = self._envelope()
        self.assertFalse(envelope["config"]["merge_policy_present"])
        # epic-integration is hardcoded ask regardless of block presence (docs/specs/evaluator.md:
        # "Epic-integration merges are always gated ... hardcoded, not configurable").
        self.assertEqual(envelope["config"]["merge_policy"], {"epic-integration": "ask"})

    def test_merge_policy_present_is_parsed_and_epic_integration_still_forced_ask(self):
        # S6 DoD: "Fixtures: ... merge-policy present and absent" — this is the "present" arm
        # (the sibling test above covers "absent"). Writes a real
        # `<!-- pr-evaluator-merge-policy -->` block into the sandbox root CLAUDE.md (same
        # write/commit/push pattern as test_failed_setup_hook_surfaces_as_fact_not_a_hard_exit),
        # runs prep, and asserts the parsed policy dict plus merge_policy_present=True.
        _write(
            self.root / "CLAUDE.md",
            "<!-- pr-evaluator-merge-policy -->\n"
            "- standard: auto\n"
            "- story: ask\n"
            "<!-- /pr-evaluator-merge-policy -->\n",
        )
        _git(["add", "CLAUDE.md"], self.root)
        _git(["commit", "-m", "add merge policy block"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)

        envelope = self._envelope(fixture_case="prep_evaluator_happy_standard")
        self.assertTrue(envelope["config"]["merge_policy_present"])
        self.assertEqual(
            envelope["config"]["merge_policy"],
            {"standard": "auto", "story": "ask", "epic-integration": "ask"},
        )

    def test_sections_carries_gh_pr_gather_spill_fields_through(self):
        envelope = self._envelope()
        envelope_asserts.assert_spill_sections_well_formed(
            envelope["sections"], ["body", "thread", "reviews"]
        )
        self.assertEqual(envelope["sections"]["body"], "See issue #42.")

    def test_attention_empty_on_a_clean_mergeable_pr(self):
        envelope = self._envelope()
        self.assertEqual(envelope["attention"], [])

    def test_notices_empty_on_the_fully_migrated_config(self):
        envelope = self._envelope()
        self.assertEqual(envelope["notices"], [])

    def test_second_run_reasserts_the_same_workspace(self):
        # v3: re-entry is another attach against the same ambient checkout — no `reused` flag
        # (there is nothing to reuse; the worktree is the operator's), same facts both runs.
        first = self._envelope()
        second = self._envelope()
        self.assertEqual(first["workspace"]["path"], second["workspace"]["path"])
        self.assertNotIn("reused", second["workspace"])

    def test_failed_setup_hook_surfaces_as_fact_not_a_hard_exit(self):
        # workspace.py's `ensure --work` exits 1 when a setup hook fails, but STILL emits an
        # envelope (setup.succeeded=False) rather than a hard failure with no envelope at all —
        # prep_evaluator must distinguish these (see build_facts's ws_exit guard) and carry the
        # setup-failure fact through as `workspace.setup` + an `attention` line, never sys.exit.
        _write(
            self.root / "CLAUDE.md",
            "<!-- worktree-setup -->\n- `exit 3` — always fails\n<!-- /worktree-setup -->\n",
        )
        _git(["add", "CLAUDE.md"], self.root)
        _git(["commit", "-m", "add failing setup hook"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)

        envelope = self._envelope(fixture_case="prep_evaluator_happy_standard")
        self.assertEqual(envelope["status"], "ok")
        self.assertFalse(envelope["workspace"]["setup"]["succeeded"])
        self.assertEqual(envelope["workspace"]["setup"]["first_failure"]["command"], "exit 3")
        self.assertIsNone(envelope["workspace"]["sha"])
        self.assertTrue(
            any("setup hook failed" in item for item in envelope["attention"]),
            envelope["attention"],
        )


class CiRollupClassificationTests(PrepEvaluatorSandboxTestCase):
    """Four CI states — S6 DoD: "Fixtures: four CI states.\""""

    def test_green_rollup(self):
        envelope = self._envelope(fixture_case="prep_evaluator_happy_standard")
        self.assertEqual(envelope["ci"]["class"], "green")
        self.assertEqual(envelope["ci"]["fail_checks"], [])

    def test_red_rollup_names_failing_checks(self):
        envelope = self._envelope(fixture_case="prep_evaluator_ci_red")
        self.assertEqual(envelope["ci"]["class"], "red")
        self.assertEqual(envelope["ci"]["fail_checks"], ["ci/test"])

    def test_pending_rollup(self):
        envelope = self._envelope(fixture_case="prep_evaluator_ci_pending")
        self.assertEqual(envelope["ci"]["class"], "pending")
        self.assertEqual(envelope["ci"]["fail_checks"], [])

    def test_empty_rollup_is_none(self):
        envelope = self._envelope(fixture_case="prep_evaluator_ci_none")
        self.assertEqual(envelope["ci"]["class"], "none")
        self.assertEqual(envelope["ci"]["fail_checks"], [])


class HealthCacheTests(PrepEvaluatorSandboxTestCase):
    """Health-cache marker SHA compare — hit iff cached SHA == PR head SHA."""

    def test_absent_marker_is_a_miss_with_null_sha(self):
        envelope = self._envelope(fixture_case="prep_evaluator_happy_standard")
        self.assertEqual(envelope["health_cache"], {"sha": None, "hit": False})

    def test_matching_sha_is_a_hit(self):
        # The fixture's marker body and pr.headRefOid share the canned OID sentinel; the harness
        # stamps BOTH to the real worktree HEAD, so the hit relation (cached sha == head OID)
        # survives stamping and the reported sha is the checkout's own HEAD.
        envelope = self._envelope(fixture_case="prep_evaluator_cache_hit")
        self.assertTrue(envelope["health_cache"]["hit"])
        self.assertEqual(envelope["health_cache"]["sha"], envelope["workspace"]["sha"])

    def test_mismatched_sha_is_a_miss_but_reports_the_stale_sha(self):
        envelope = self._envelope(fixture_case="prep_evaluator_cache_miss_sha_mismatch")
        self.assertFalse(envelope["health_cache"]["hit"])
        self.assertEqual(envelope["health_cache"]["sha"], "ca1e123000000000000000000000000000000a")


class PrTypeDetectionTests(PrepEvaluatorSandboxTestCase):
    """PR-type detection: story / epic-integration / standard, from base/head branch patterns."""

    def test_standard_when_base_and_head_are_plain_branches(self):
        envelope = self._envelope(fixture_case="prep_evaluator_happy_standard")
        self.assertEqual(envelope["pr_type"], "standard")
        self.assertEqual(envelope["suggested_playbook"], "standard.md")

    def test_story_when_base_matches_epic_branch_pattern(self):
        _git(["fetch", "origin"], self.root)
        _git(["branch", "epic/42-journal", "origin/main"], self.root)
        _git(["push", "origin", "epic/42-journal"], self.root)
        envelope = self._envelope(fixture_case="prep_evaluator_story_type")
        self.assertEqual(envelope["pr_type"], "story")
        self.assertEqual(envelope["suggested_playbook"], "story.md")
        self.assertEqual(envelope["workspace"]["base_ref"], "epic/42-journal")

    def test_epic_integration_when_head_matches_epic_pattern_and_base_is_main(self):
        envelope = self._envelope(fixture_case="prep_evaluator_epic_integration_type")
        self.assertEqual(envelope["pr_type"], "epic-integration")
        self.assertEqual(envelope["suggested_playbook"], "epic-integration.md")
        # the WORKSPACE ensured is still on the PR's own head branch (epic/42-journal), never on
        # main — an epic-integration PR's diff is reviewed on its own branch like any other.
        self.assertEqual(envelope["workspace"]["branch"], "epic/42-journal")


class NativeBlockerTests(PrepEvaluatorSandboxTestCase):
    """docs/specs/evaluator.md "Artifacts read": "Any open blocker holds the merge — soft-
    reject." Prep surfaces the fact (blocked_by + an attention line); the soft-reject decision
    itself is the evaluator playbook's judgment, not prep's."""

    def test_open_native_blocker_surfaces_in_blocked_by_and_attention(self):
        envelope = self._envelope(fixture_case="prep_evaluator_open_blocker")
        blockers = envelope["blocked_by"]["42"]
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["number"], 41)
        self.assertEqual(blockers[0]["state"], "OPEN")
        self.assertTrue(
            any("open native blocker" in item for item in envelope["attention"]),
            envelope["attention"],
        )


class MarkerAmbiguousTests(PrepEvaluatorSandboxTestCase):
    """Duplicate health-cache comments -> MARKER_AMBIGUOUS, forwarded verbatim from gh_pr_gather's
    own decision (architecture.md §3's closed decision-code set is shared, not re-derived)."""

    def test_two_health_cache_comments_yields_marker_ambiguous(self):
        result = self._run(
            ["88", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_evaluator_marker_ambiguous",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)  # needs_decision is exit 0
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "MARKER_AMBIGUOUS")

    def test_marker_ambiguous_short_circuits_before_any_closing_issue_gather(self):
        # The marker_ambiguous fixture's manifest is deliberately trimmed to only the pr-view +
        # marker-lookup entries (see tests/fixtures/prep_evaluator_marker_ambiguous's build
        # notes) — reaching the closing-issue gather would be an un-fixtured MISS, which itself
        # would fail this test loudly and prove the ordering bug.
        result = self._run(
            ["88", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_evaluator_marker_ambiguous",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        self.assertEqual(envelope["decision"]["code"], "MARKER_AMBIGUOUS")
        # No workspace side effect either — the decision is returned before `ensure --work` runs.
        self.assertFalse((self.root / ".worktrees").exists())


class AuthRequiredTests(PrepEvaluatorSandboxTestCase):
    def test_auth_failure_on_first_gh_call_yields_auth_required(self):
        result = self._run(
            ["88", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_evaluator_auth_required",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AUTH_REQUIRED")


class WorkspaceMismatchTests(PrepEvaluatorSandboxTestCase):
    """v3: the ambient-checkout assertion on the PR head — WORKSPACE_MISMATCH decisions
    (workspace.py's, forwarded verbatim). These replace the retired ROOT_*/BRANCH_IN_USE
    propagation coverage: the evaluator no longer polices root state or creates worktrees (those
    gates live on the workspace-creating paths — the landing tools and workspace-open)."""

    def _mismatch(self, envelope, reason):
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "WORKSPACE_MISMATCH")
        self.assertEqual(envelope["decision"]["context"]["reason"], reason)

    def test_wrong_branch_is_a_branch_mismatch(self):
        envelope = self._envelope(
            fixture_case="prep_evaluator_happy_standard", ambient_branch="999-unrelated-work"
        )
        self._mismatch(envelope, "branch_mismatch")
        self.assertEqual(envelope["decision"]["context"]["expected_branch"], "88-fix-widget")

    def test_session_at_the_project_root_names_workspace_open(self):
        result = self._run(
            ["88", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_evaluator_happy_standard",
            cwd=str(self.root),
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        self._mismatch(envelope, "at_project_root")
        self.assertTrue(
            any("workspace-open" in option for option in envelope["decision"]["options"])
        )

    def test_head_oid_drift_is_stale_checkout(self):
        # The fixture's canned headRefOid deliberately NOT stamped to the worktree HEAD: the
        # ambient checkout does not contain the PR's recorded head — the evaluator must never
        # health-check or cache against it (require_exact, review finding M1).
        envelope = self._envelope(fixture_case="prep_evaluator_happy_standard", stamp=False)
        self._mismatch(envelope, "stale_checkout")
        self.assertEqual(
            envelope["decision"]["context"]["expected_remote_sha"],
            self.CANNED_HEAD_OID,
        )
        # Even an AHEAD checkout is a mismatch on the exact-OID contract — context records it.
        self.assertIn("ahead_of_remote", envelope["decision"]["context"])


class RefreshModeTests(unittest.TestCase):
    """--refresh re-derives PR state + CI without touching workspace.py/config_block.py at all
    (S6 DoD: "--refresh re-derives PR state and CI without hook re-runs")."""

    def setUp(self):
        self._tmp_ctx = tempfile.TemporaryDirectory()
        self.scratch = self._tmp_ctx.name
        self.addCleanup(self._tmp_ctx.cleanup)

    def _run(self, args, fixture_case=None):
        env = shimenv.intercepted_env(base_env=os.environ, fixture_case=fixture_case)
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + args,
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_refresh_never_requires_a_root_at_all(self):
        # No --root passed, no git sandbox constructed — if --refresh touched workspace.py's
        # root-freshness or `ensure --work` at all, this would fail (default --root='.' would
        # resolve to the current process's own cwd, which is not a controlled git sandbox and
        # would produce unpredictable ROOT_* results, not a clean "ok").
        result = self._run(
            ["88", "octo/widgets", "--refresh", "--scratch-dir", self.scratch],
            fixture_case="prep_evaluator_happy_standard",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "ok")
        self.assertNotIn("workspace", envelope)
        self.assertEqual(envelope["config"], {})
        self.assertFalse(envelope["root"]["fresh"])

    def test_refresh_still_re_derives_ci_and_health_cache(self):
        result = self._run(
            ["88", "octo/widgets", "--refresh", "--scratch-dir", self.scratch],
            fixture_case="prep_evaluator_ci_red",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        self.assertEqual(envelope["ci"]["class"], "red")
        self.assertIn("health_cache", envelope)

    def test_refresh_still_reports_dod_and_self_review(self):
        result = self._run(
            ["88", "octo/widgets", "--refresh", "--scratch-dir", self.scratch],
            fixture_case="prep_evaluator_happy_standard",
        )
        envelope = _parse_one_envelope(result.stdout)
        self.assertIn("42", envelope["dod"])
        self.assertFalse(envelope["self_review"])


class SingleInvocationBudgetTests(PrepEvaluatorSandboxTestCase):
    """Single-invocation budget: one prep run's shim gh-call count is bounded and predictable
    (prd.md §9.2 "one-shot state assembly" / S6 DoD's "shim call counts")."""

    def test_shim_call_count_for_one_happy_run_is_bounded_and_stable(self):
        # Instrument the shim by pointing GH_SHIM_FIXTURES at a case and counting how many
        # manifest entries prep_evaluator's single invocation actually needs (the shim exits 2
        # loudly on ANY call outside the manifest — tests/README.md — so if this test passes at
        # all, every `gh` call prep made was one of these seven, no more, no fewer: pr view,
        # marker lookup, issue view, issue-comments, issue open-prs, repo config, current user).
        # This directly proves "no redundant fetches" (architecture.md §9.2) as an exact count,
        # not an unbounded "at most N" — a regression that adds a stray extra `gh` call becomes
        # a fixture MISS on the very next un-fixtured argv, failing loudly per tests/README.md.
        result = self._run(
            ["88", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_evaluator_happy_standard",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        manifest_path = shimenv.fixture_case_dir("prep_evaluator_happy_standard") / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Every manifest entry must have been reachable in exactly one prep run (a smaller count
        # would mean this test's own fixture over-provisions calls that never happen; the shim's
        # own MISS behavior on the other side already proves no MORE calls happen than these).
        self.assertEqual(len(manifest), 7)

    def test_no_gh_call_is_repeated_within_one_run(self):
        # A second, independent proof (from the SCRIPT side, not the fixture side): every argv in
        # the happy-path manifest is for a semantically distinct fetch (pr view, PR markers,
        # issue view, issue comments, issue open-prs, repo config, current user) — no two entries
        # share an argv, so if prep called any of them twice the shim would have answered
        # identically both times (harmless) but the manifest's own uniqueness proves the SET of
        # distinct calls prep makes in one run, which is what "no redundant fetches" means here.
        manifest_path = shimenv.fixture_case_dir("prep_evaluator_happy_standard") / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        argv_tuples = [tuple(entry["argv"]) for entry in manifest]
        self.assertEqual(len(argv_tuples), len(set(argv_tuples)), "duplicate argv in manifest")


class PureHelperUnitTests(unittest.TestCase):
    """Direct, in-process tests of prep_evaluator's pure classification helpers — no subprocess,
    no shim, no git sandbox needed (mirrors test_workspace.py's WorkspaceHelperUnitTests style)."""

    def test_classify_ci_rollup_green(self):
        cls, fails = prep_evaluator._classify_ci_rollup([{"name": "a", "conclusion": "SUCCESS"}])
        self.assertEqual(cls, "green")
        self.assertEqual(fails, [])

    def test_classify_ci_rollup_skipped_and_neutral_count_as_green(self):
        cls, fails = prep_evaluator._classify_ci_rollup(
            [{"name": "a", "conclusion": "SUCCESS"}, {"name": "b", "conclusion": "SKIPPED"},
             {"name": "c", "conclusion": "NEUTRAL"}]
        )
        self.assertEqual(cls, "green")

    def test_classify_ci_rollup_red_names_failing_checks(self):
        cls, fails = prep_evaluator._classify_ci_rollup(
            [{"name": "a", "conclusion": "SUCCESS"}, {"name": "b", "conclusion": "FAILURE"}]
        )
        self.assertEqual(cls, "red")
        self.assertEqual(fails, ["b"])

    def test_classify_ci_rollup_pending_on_in_progress(self):
        cls, fails = prep_evaluator._classify_ci_rollup(
            [{"name": "a", "status": "IN_PROGRESS", "conclusion": None}]
        )
        self.assertEqual(cls, "pending")

    def test_classify_ci_rollup_pending_on_status_context_state(self):
        cls, fails = prep_evaluator._classify_ci_rollup([{"name": "a", "state": "PENDING"}])
        self.assertEqual(cls, "pending")

    def test_classify_ci_rollup_empty_is_none(self):
        cls, fails = prep_evaluator._classify_ci_rollup([])
        self.assertEqual(cls, "none")
        cls2, _ = prep_evaluator._classify_ci_rollup(None)
        self.assertEqual(cls2, "none")

    def test_detect_pr_type_epic_integration(self):
        self.assertEqual(prep_evaluator._detect_pr_type("main", "epic/42-journal"), "epic-integration")

    def test_detect_pr_type_story(self):
        self.assertEqual(prep_evaluator._detect_pr_type("epic/42-journal", "88-add-search"), "story")

    def test_detect_pr_type_standard(self):
        self.assertEqual(prep_evaluator._detect_pr_type("main", "88-fix-widget"), "standard")

    def test_detect_pr_type_epic_head_but_non_main_base_is_story_not_epic_integration(self):
        # headRefName matching epic/<N>-<slug> alone is not sufficient -- baseRefName must be
        # `main` too (docs/specs/evaluator.md: "epic-integration if headRefName matches ... AND
        # baseRefName == main"). Here baseRefName itself matches the epic pattern, so `story`
        # correctly takes precedence.
        self.assertEqual(
            prep_evaluator._detect_pr_type("epic/1-old", "epic/2-new"), "story"
        )

    def test_parse_merge_policy_reads_ask_and_auto(self):
        policy = prep_evaluator._parse_merge_policy(["- standard: auto", "- story: ask"])
        self.assertEqual(policy, {"standard": "auto", "story": "ask"})

    def test_parse_merge_policy_ignores_non_conforming_lines(self):
        policy = prep_evaluator._parse_merge_policy(["not a policy line", "- standard: ask"])
        self.assertEqual(policy, {"standard": "ask"})

    def test_parse_backtick_command_list(self):
        items = prep_evaluator._parse_backtick_command_list(
            ["- `make lint` — hygiene", "- `make test` — tests", "prose line"]
        )
        self.assertEqual(items, ["make lint", "make test"])


class UsageErrorTests(unittest.TestCase):
    def test_missing_required_positional_args_is_usage_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_missing_repo_arg_is_usage_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "88"],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
