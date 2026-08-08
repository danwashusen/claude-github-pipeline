"""Unit tests for scripts/prep_resolver.py — the resolver's complete facts block in one call
(architecture.md §4; docs/implementation.md S9; docs/specs/resolver.md).

Test topology (mirrors tests/test_prep_evaluator.py — the S8-locked composition pattern this step
inherits): `gh` calls go through the offline shim (`tests/support/shimenv`); `git` calls (root
freshness, `ensure --work`/`ensure --read`, and the `git ls-remote` epic-branch/collision
discovery this step adds) go through a real temp origin+clone (`tests/support/gitsandbox`) — no
shim needed for those (architecture.md §10). `prep_resolver.py` is driven as a real subprocess so
every test exercises the full argv-in / subprocess / envelope-out path a real caller uses.

Coverage matrix (S9 DoD):
- One fixture per row of the v1 prior-PR table (7 rows) -> mode/vector derivation.
- Epic-branch discovery: zero / one / multiple matches (multiple -> AMBIGUOUS).
- Branch-collision suffixing: existing -v2 yields -v3 (exercised directly against a git sandbox,
  since the row fixtures' canonical path already covers the zero-collision case).
- Story parent-epic search: one match.
- Blocked-OQ both ways: open tracker + in-scope (blocked) sets the hard-gate; a
  question-decision:v1 comment clears it.
- Distiller bundle is staged paths, never above-threshold inline bytes.
- Envelope conformance + the single-invocation call-budget test (two-sided, as S6).
- Decision codes: AMBIGUOUS (epic-branch/story-parent multiplicity), AUTH_REQUIRED,
  MARKER_AMBIGUOUS (duplicate plan-marker comments), PHASES_MALFORMED, DOD_MALFORMED.
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
SCRIPT = SCRIPTS_DIR / "prep_resolver.py"

sys.path.insert(0, str(SCRIPTS_DIR))

import prep_resolver  # noqa: E402  (import after sys.path setup, by necessity)
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


class PrepResolverSandboxTestCase(unittest.TestCase):
    """Shared setup: a real temp git origin+clone (the `--root`), pre-seeded with `.gitignore`
    (mirroring tests/test_prep_evaluator.py's identical rationale: an unseeded first `ensure`
    would spuriously trip ROOT_DIRTY on the very first call)."""

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

    # v3 harness: a test whose flow reaches the workspace ASSERTION (fresh/continue rows) must run
    # the prep subprocess with its cwd INSIDE an ambient worktree — the operator posture the
    # inversion introduces. A class sets `ambient_default` (or a test passes `ambient=`) to the
    # branch name the worktree should be on; None (the base default) runs from the test process's
    # own cwd, which only flows that never reach the assertion (gated, comment-only, --refresh,
    # early decisions) may use.
    ambient_default = None

    def _mk_ambient(self, branch):
        """Create (or reuse) `.worktrees/<branch>` in the sandbox clone, forked at origin/main —
        the worktree the operator would have opened via workspace-open. Returns its Path."""
        wt = self.root / ".worktrees" / branch
        if not wt.is_dir():
            wt.parent.mkdir(parents=True, exist_ok=True)
            has_local = (
                subprocess.run(
                    ["git", "show-ref", "--verify", "--quiet", "refs/heads/%s" % branch],
                    cwd=str(self.root),
                ).returncode
                == 0
            )
            if has_local:
                _git(["worktree", "add", str(wt), branch], self.root)
            else:
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

    _AMBIENT_UNSET = object()

    def _envelope(self, issue="100", repo="octo/widgets", fixture_case="prep_resolver_row_no_prior_pr", extra_args=None, fixtures_dir=None, ambient=_AMBIENT_UNSET):
        args = [issue, repo, "--root", str(self.root), "--scratch-dir", self.scratch]
        if extra_args:
            args += extra_args
        if ambient is self._AMBIENT_UNSET:
            ambient = self.ambient_default
        run_cwd = str(self._mk_ambient(ambient)) if ambient is not None else None
        # A `fixtures_dir` overrides the named case with an explicit (e.g. run-time-stamped) fixture dir
        # via GH_SHIM_FIXTURES — see PriorPrRowTests._stamped_active_fixture (the time-bomb fix).
        if fixtures_dir is not None:
            result = self._run(args, fixture_case=None, extra_env={"GH_SHIM_FIXTURES": str(fixtures_dir)}, cwd=run_cwd)
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


class HappyPathFactsSchemaTests(PrepResolverSandboxTestCase):
    """Facts schema matches architecture.md §4's common core + resolver extensions (v3: the
    workspace fact is the OBSERVED ambient checkout, asserted — not an ensured worktree)."""

    ambient_default = "100-fix-the-widget"

    def test_conformant_ok_envelope_with_resolver_facts(self):
        envelope = self._envelope()
        self.assertEqual(envelope["status"], "ok")
        for key in (
            "repo", "scratch", "root", "target", "vector", "suggested_playbook", "workspace",
            "config", "sections", "attention", "notices", "plan", "phases", "dod",
            "open_questions", "open_questions_gate", "audit_ref", "distiller_bundle",
        ):
            self.assertIn(key, envelope, "missing architecture.md §4 facts-block key %r" % key)

    def test_root_facts_shape(self):
        # v3.x: root carries the main checkout's path and the DERIVED default branch. It used to
        # carry `sha`/`source: "origin/main"` — the retired pin; the SHA that matters now is
        # `config.source.sha`, the checkout the gate blocks were actually read from.
        envelope = self._envelope()
        self.assertEqual(envelope["root"]["path"], str(self.root))
        self.assertEqual(envelope["root"]["default_branch"], "main")
        self.assertNotIn("sha", envelope["root"])
        self.assertNotIn("source", envelope["root"])
        self.assertTrue(envelope["root"]["fresh"])

    def test_target_facts_shape(self):
        envelope = self._envelope()
        self.assertEqual(envelope["target"]["kind"], "issue")
        self.assertEqual(envelope["target"]["number"], 100)
        self.assertEqual(envelope["target"]["state"], "OPEN")
        self.assertEqual(envelope["target"]["labels"], ["bug"])

    def test_vector_type_standard_for_bug_labeled_issue(self):
        envelope = self._envelope()
        self.assertEqual(envelope["vector"]["type"], "standard")
        self.assertEqual(envelope["suggested_playbook"], "standard.md")

    def test_workspace_fact_records_the_ambient_checkout(self):
        envelope = self._envelope()
        self.assertEqual(envelope["workspace"]["branch"], "100-fix-the-widget")
        self.assertEqual(envelope["workspace"]["base_ref"], "main")
        self.assertEqual(envelope["workspace"]["source"], "ambient")
        self.assertEqual(
            Path(envelope["workspace"]["path"]),
            (self.root / ".worktrees" / "100-fix-the-widget").resolve(),
        )
        self.assertFalse(envelope["workspace"]["dirty"])
        self.assertEqual(envelope["workspace"]["unpushed_commits"], 0)
        self.assertNotIn("reused", envelope["workspace"])
        self.assertNotIn("branch", envelope)  # the minted-branch fact is retired with the ladder

    def test_audit_ref_is_main_for_standard_type(self):
        envelope = self._envelope()
        self.assertEqual(envelope["audit_ref"], "main")
        self.assertNotIn("read_workspaces", envelope)

    def test_config_source_is_the_ambient_workspace(self):
        envelope = self._envelope()
        source = envelope["config"]["source"]
        self.assertEqual(source["path"], envelope["workspace"]["path"])
        self.assertEqual(source["branch"], envelope["workspace"]["branch"])
        self.assertEqual(len(source["sha"]), 40)
        self.assertFalse(source["dirty"])

    def test_config_reads_the_ambient_worktree_including_uncommitted_edits(self):
        # v3.x inversion, and the deliberate security trade the operator chose: a committed gate
        # block on the default branch + an UNCOMMITTED weakening in the work worktree. Through v3
        # the pinned blob won and the weakening was invisible ("a PR cannot weaken its own
        # gates"); now the working tree wins, and the compensating control is that
        # `config.source.dirty` says so and an attention line surfaces it.
        _write(
            self.root / "COMMANDS.md",
            "<!-- issue-resolver-fast-checks -->\n- `make lint` — hygiene\n<!-- /issue-resolver-fast-checks -->\n",
        )
        _git(["add", "COMMANDS.md"], self.root)
        _git(["commit", "-m", "add committed gate block"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)

        wt = self._mk_ambient("100-fix-the-widget")
        _write(
            wt / "COMMANDS.md",
            "<!-- issue-resolver-fast-checks -->\n- `true` — weakened\n<!-- /issue-resolver-fast-checks -->\n",
        )
        envelope = self._envelope(ambient="100-fix-the-widget")
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["config"]["static_checks"], ["true"])
        self.assertEqual(
            envelope["config"]["static_checks_source"], str(wt / "COMMANDS.md")
        )
        self.assertTrue(envelope["config"]["source"]["dirty"])
        self.assertTrue(
            any("uncommitted changes" in line for line in envelope["attention"]),
            "a dirty gate-config source must be surfaced, never silent: %r" % envelope["attention"],
        )

    def test_config_fallback_chain_reads_pr_evaluator_blocks_when_resolver_blocks_absent(self):
        _write(
            self.root / "CLAUDE.md",
            "<!-- pr-evaluator-static-checks -->\n"
            "- `make lint` — hygiene\n"
            "<!-- /pr-evaluator-static-checks -->\n"
            "<!-- pr-evaluator-test-target -->\n"
            "- wrapper: `make test`\n"
            "<!-- /pr-evaluator-test-target -->\n",
        )
        _git(["add", "CLAUDE.md"], self.root)
        _git(["commit", "-m", "add pr-evaluator fallback blocks"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)

        envelope = self._envelope()
        self.assertTrue(envelope["config"]["static_checks_present"])
        self.assertEqual(envelope["config"]["static_checks"], ["make lint"])
        self.assertTrue(envelope["config"]["test_target_present"])
        self.assertTrue(envelope["config"]["canonical_suite_present"])
        self.assertIn("FAST_CHECKS_FALLBACK_STATIC_CHECKS", envelope["notices"])
        self.assertIn("TEST_TARGET_FALLBACK_PR_EVALUATOR", envelope["notices"])
        self.assertIn("CANONICAL_SUITE_FALLBACK_PR_EVALUATOR_TEST_TARGET", envelope["notices"])

    def test_sections_carries_gh_gather_spill_fields_through(self):
        envelope = self._envelope()
        self.assertIn("issue_body", envelope["sections"])
        self.assertEqual(envelope["sections"]["issue_body_mode"], "inline")

    def test_dod_parsed_from_issue_body(self):
        envelope = self._envelope()
        self.assertEqual(len(envelope["dod"]), 1)
        self.assertEqual(envelope["dod"][0]["text"], "Widget fixed")
        self.assertFalse(envelope["dod"][0]["checked"])

    def test_plan_absent_is_a_fact_not_a_decision(self):
        envelope = self._envelope()
        self.assertFalse(envelope["plan"]["present"])
        self.assertIsNone(envelope["plan"]["sha"])
        self.assertEqual(envelope["phases"], [])

    def test_distiller_bundle_paths_present(self):
        envelope = self._envelope()
        self.assertTrue(Path(envelope["distiller_bundle"]["issue_body_path"]).is_file())
        self.assertTrue(Path(envelope["distiller_bundle"]["thread_path"]).is_file())
        self.assertIsNone(envelope["distiller_bundle"]["plan_marker_path"])

    def test_attention_empty_on_a_clean_fresh_start(self):
        envelope = self._envelope()
        self.assertEqual(envelope["attention"], [])

    def test_setup_hooks_rerun_on_every_session_entry(self):
        # The hook cadence worktree-lifecycle.md requires: the setup hooks run on EVERY session
        # start (attach), fresh and re-entry alike — two prep runs, two hook executions. The block
        # must be committed+pushed: attach discovers hooks at the origin/main pin (blob reads).
        _write(
            self.root / "CLAUDE.md",
            "<!-- worktree-setup -->\n- `echo ran >> .hook-log`\n<!-- /worktree-setup -->\n",
        )
        _git(["add", "CLAUDE.md"], self.root)
        _git(["commit", "-m", "add setup hook block"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)
        self._envelope()
        envelope = self._envelope()
        self.assertEqual(envelope["status"], "ok")
        wt = self.root / ".worktrees" / "100-fix-the-widget"
        log = (wt / ".hook-log").read_text(encoding="utf-8")
        self.assertEqual(log.count("ran"), 2)
        self.assertTrue(envelope["workspace"]["setup"]["succeeded"])


class PriorPrRowTests(PrepResolverSandboxTestCase):
    """One fixture per row of the v1 prior-PR table (docs/specs/resolver.md's 7-row table) —
    S9 DoD's first box."""

    def _stamped_active_fixture(self, source_case):
        """Copy a foreign-open-PR row fixture into a per-test temp fixture dir and re-stamp its open
        PR's `updatedAt` to `now(utc) - 2 days`, so the active/stale classification
        (`prep_resolver._classify_open_other_activity`, `_STALE_ACTIVITY_DAYS = 14`) is **time-
        invariant**. Returns the temp dir for `_envelope(fixtures_dir=...)`.

        Regression (fixed-date-rot across the stale boundary): the original row fixtures carried a
        static `updatedAt` (~2026-07-08, "recent" at S9 authoring) that aged past the 14-day cutoff on
        2026-07-23, flipping `open-pr-other-active` -> `open-pr-other-stale`. S9 made the BOUNDARY tests
        run-time-relative (`timedelta` at call time) but these subprocess-level row fixtures kept fixed
        dates. Rule: an **active-classified** fixture MUST be stamped at run time; the stale-row
        fixture's 18-month-old date (`2025-01-01`) is safe forever and stays static."""
        import datetime
        import shutil

        src = shimenv.fixture_case_dir(source_case)
        dst = Path(tempfile.mkdtemp(prefix="gh-resolver-stamp-"))
        self.addCleanup(lambda: shutil.rmtree(dst, ignore_errors=True))
        for f in src.iterdir():
            (dst / f.name).write_bytes(f.read_bytes())
        fresh = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        prs_path = dst / "open_prs.json"
        prs = json.loads(prs_path.read_text(encoding="utf-8"))
        for pr in prs:
            if "updatedAt" in pr:
                pr["updatedAt"] = fresh
        prs_path.write_text(json.dumps(prs), encoding="utf-8")
        return dst

    def test_open_pr_yours(self):
        envelope = self._envelope(
            fixture_case="prep_resolver_row_open_yours", ambient="100-fix-the-widget"
        )
        self.assertEqual(envelope["vector"]["prior_pr_row"], "open-pr-yours")
        self.assertEqual(envelope["vector"]["mode"], "continue")
        self.assertEqual(envelope["prior_pr"]["number"], 55)
        # continue mode asserts the ambient checkout is on the prior PR's own head branch.
        self.assertEqual(envelope["workspace"]["branch"], "100-fix-the-widget")
        self.assertEqual(envelope["workspace"]["expected_branch"], "100-fix-the-widget")

    def test_open_pr_other_active(self):
        # An open PR by ANOTHER author, actively worked, is operator-gated — SKILL.md:646:
        # "Do not open a competing PR" / "AskUserQuestion (header 'Open PR')". Prep must NOT
        # pre-empt that gate with mode: continue or a work-worktree side effect impersonating
        # carol's branch (S9 review finding).
        envelope = self._envelope(
            fixtures_dir=self._stamped_active_fixture("prep_resolver_row_open_other_active")
        )
        self.assertEqual(envelope["vector"]["prior_pr_row"], "open-pr-other-active")
        self.assertEqual(envelope["vector"]["mode"], "gated")
        self.assertNotEqual(envelope["vector"]["mode"], "continue")
        gate = envelope["vector"]["gate"]
        self.assertEqual(gate["reason"], "open-pr-other-active")
        self.assertEqual(gate["header"], "Open PR")
        self.assertEqual(gate["options"], ["Review it", "Leave a comment", "Wait"])
        # The gate-driving prior-PR facts are unmissable, both under vector.gate.prior_pr and the
        # top-level prior_pr fact.
        self.assertEqual(envelope["prior_pr"]["author"], "carol")
        self.assertEqual(envelope["prior_pr"]["headRefName"], "carol-fix-widget")
        self.assertFalse(envelope["prior_pr"]["isDraft"])
        self.assertIn("stale_cutoff_days", envelope["prior_pr"])
        self.assertEqual(gate["prior_pr"], envelope["prior_pr"])
        # No work-workspace side effect — never a worktree impersonating carol's branch.
        self.assertNotIn("workspace", envelope)
        self.assertFalse((self.root / ".worktrees").exists())
        self.assertNotIn("branch", envelope)
        self.assertTrue(
            any("actively worked" in item for item in envelope["attention"]), envelope["attention"]
        )

    def test_open_pr_other_stale(self):
        # Same gate discipline as the active row, but the "Stale PR" card (SKILL.md:647:
        # "Take it over" / "Start fresh") — still no worktree until the operator picks one.
        envelope = self._envelope(fixture_case="prep_resolver_row_open_other_stale")
        self.assertEqual(envelope["vector"]["prior_pr_row"], "open-pr-other-stale")
        self.assertEqual(envelope["vector"]["mode"], "gated")
        gate = envelope["vector"]["gate"]
        self.assertEqual(gate["reason"], "open-pr-other-stale")
        self.assertEqual(gate["header"], "Stale PR")
        self.assertEqual(gate["options"], ["Take it over", "Start fresh"])
        self.assertNotIn("workspace", envelope)
        self.assertFalse((self.root / ".worktrees").exists())
        self.assertNotIn("branch", envelope)
        self.assertTrue(
            any("stale" in item for item in envelope["attention"]), envelope["attention"]
        )

    def test_draft_by_same_author_is_continue(self):
        # v1 SKILL.md:648: "Draft PR ... Treat the same as an open PR by the same author" — this
        # row is scoped to YOUR OWN draft. Authorship assertion added per the S9 review finding so
        # the isDraft-first ordering bug (which routed ANY draft into continue) cannot regress.
        envelope = self._envelope(
            fixture_case="prep_resolver_row_draft", ambient="100-fix-the-widget"
        )
        self.assertEqual(envelope["vector"]["prior_pr_row"], "draft")
        self.assertEqual(envelope["vector"]["mode"], "continue")
        self.assertNotIn("gate", envelope["vector"])
        self.assertEqual(envelope["prior_pr"]["author"], "reviewer-bot")  # the fixture's current_user
        self.assertTrue(envelope["prior_pr"]["isDraft"])
        # continue mode DOES assert the ambient workspace, on the draft PR's own branch.
        self.assertEqual(envelope["workspace"]["branch"], "100-fix-the-widget")

    def test_draft_by_another_author_is_gated_not_continue(self):
        # The ordering-bug regression case itself: a FOREIGN draft must classify via the same
        # activity check as a foreign ready PR (SKILL.md:648's "Drafts are still claimed work" is
        # about protecting another author's draft, not a license to treat it as available).
        envelope = self._envelope(
            fixtures_dir=self._stamped_active_fixture("prep_resolver_row_draft_other_author")
        )
        self.assertEqual(envelope["vector"]["prior_pr_row"], "open-pr-other-active")
        self.assertEqual(envelope["vector"]["mode"], "gated")
        self.assertTrue(envelope["prior_pr"]["isDraft"])
        self.assertEqual(envelope["prior_pr"]["author"], "carol")
        self.assertNotIn("workspace", envelope)
        self.assertFalse((self.root / ".worktrees").exists())

    def test_closed_resolved(self):
        envelope = self._envelope(
            fixture_case="prep_resolver_row_closed_resolved", ambient="100-fix-the-widget"
        )
        self.assertEqual(envelope["vector"]["prior_pr_row"], "closed-resolved")
        self.assertEqual(envelope["vector"]["mode"], "fresh")
        self.assertTrue(envelope["prior_pr"]["resolved"])

    def test_closed_not_resolved(self):
        envelope = self._envelope(
            fixture_case="prep_resolver_row_closed_not_resolved", ambient="100-fix-the-widget"
        )
        self.assertEqual(envelope["vector"]["prior_pr_row"], "closed-not-resolved")
        self.assertEqual(envelope["vector"]["mode"], "fresh")
        self.assertFalse(envelope["prior_pr"]["resolved"])
        self.assertTrue(
            any("did not resolve it" in item for item in envelope["attention"]), envelope["attention"]
        )

    def test_no_prior_pr(self):
        envelope = self._envelope(
            fixture_case="prep_resolver_row_no_prior_pr", ambient="100-fix-the-widget"
        )
        self.assertEqual(envelope["vector"]["prior_pr_row"], "no-prior-pr")
        self.assertEqual(envelope["vector"]["mode"], "fresh")
        self.assertIsNone(envelope["prior_pr"])


class EpicBranchDiscoveryTests(PrepResolverSandboxTestCase):
    """Epic-branch discovery: zero / one / multiple matches (S9 DoD's second box)."""

    def test_zero_matches_computes_bootstrap_slug(self):
        envelope = self._envelope(
            issue="100", fixture_case="prep_resolver_epic_zero",
            ambient="epic/100-sandbox-fixture",
        )
        self.assertEqual(envelope["vector"]["type"], "epic")
        self.assertEqual(envelope["epic"]["match_count"], 0)
        self.assertEqual(envelope["epic"]["bootstrap_slug"], "sandbox-fixture")
        self.assertEqual(envelope["audit_ref"], "main")
        self.assertEqual(envelope["suggested_playbook"], "epic.md")

    def test_one_match_uses_discovered_branch_verbatim(self):
        _git(["fetch", "origin"], self.root)
        _git(["branch", "epic/100-sandbox-fixture", "origin/main"], self.root)
        _git(["push", "origin", "epic/100-sandbox-fixture"], self.root)

        envelope = self._envelope(
            issue="100", fixture_case="prep_resolver_epic_one",
            ambient="epic/100-sandbox-fixture",
        )
        self.assertEqual(envelope["epic"]["match_count"], 1)
        self.assertEqual(envelope["epic"]["branch"], "epic/100-sandbox-fixture")
        self.assertEqual(envelope["audit_ref"], "epic/100-sandbox-fixture")
        self.assertIn("read_workspaces", envelope)
        self.assertEqual(envelope["read_workspaces"]["audit"]["ref"], "epic/100-sandbox-fixture")

    def test_multiple_matches_yields_ambiguous(self):
        _git(["fetch", "origin"], self.root)
        _git(["branch", "epic/100-sandbox-fixture", "origin/main"], self.root)
        _git(["push", "origin", "epic/100-sandbox-fixture"], self.root)
        _git(["branch", "epic/100-alt-name", "origin/main"], self.root)
        _git(["push", "origin", "epic/100-alt-name"], self.root)

        result = self._run(
            ["100", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_resolver_epic_multiple",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AMBIGUOUS")
        self.assertEqual(len(envelope["decision"]["context"]["candidates"]), 2)
        # No workspace side effect either — the decision is returned before any ensure runs.
        self.assertFalse((self.root / ".worktrees").exists())


class BranchCollisionSuffixTests(unittest.TestCase):
    """Collision fixture: existing -v2 branch yields -v3 (S9 DoD's third box) — exercised directly
    against `compute_branch_name` + a real git sandbox (the row fixtures' canonical path already
    covers the zero-collision case end-to-end)."""

    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path

    def test_no_collision_is_unsuffixed(self):
        name, collided = prep_resolver.compute_branch_name(self.root, 42, "fix-thing")
        self.assertEqual(name, "42-fix-thing")
        self.assertIsNone(collided)

    def test_one_existing_branch_yields_v2(self):
        _git(["checkout", "-b", "42-fix-thing"], self.root)
        _git(["push", "origin", "42-fix-thing"], self.root)
        _git(["checkout", "main"], self.root)
        name, collided = prep_resolver.compute_branch_name(self.root, 42, "fix-thing")
        self.assertEqual(name, "42-fix-thing-v2")
        self.assertEqual(collided, ["42-fix-thing"])

    def test_existing_v2_yields_v3(self):
        _git(["checkout", "-b", "42-fix-thing"], self.root)
        _git(["push", "origin", "42-fix-thing"], self.root)
        _git(["checkout", "-b", "42-fix-thing-v2", "main"], self.root)
        _git(["push", "origin", "42-fix-thing-v2"], self.root)
        _git(["checkout", "main"], self.root)
        name, collided = prep_resolver.compute_branch_name(self.root, 42, "fix-thing")
        self.assertEqual(name, "42-fix-thing-v3")
        self.assertEqual(sorted(collided), ["42-fix-thing", "42-fix-thing-v2"])


class StoryParentEpicSearchTests(PrepResolverSandboxTestCase):
    def test_one_match_open_epic_ensures_read_workspace_on_its_branch(self):
        _git(["fetch", "origin"], self.root)
        _git(["branch", "epic/100-sandbox-fixture", "origin/main"], self.root)
        _git(["push", "origin", "epic/100-sandbox-fixture"], self.root)

        envelope = self._envelope(
            issue="101", fixture_case="prep_resolver_story_parent_search",
            ambient="101-story-work",
        )
        self.assertEqual(envelope["vector"]["type"], "story")
        self.assertEqual(envelope["story"]["parent_epic"]["number"], 100)
        self.assertEqual(envelope["audit_ref"], "epic/100-sandbox-fixture")
        self.assertEqual(envelope["suggested_playbook"], "story.md")
        self.assertIn("read_workspaces", envelope)


class OpenQuestionHardGateTests(PrepResolverSandboxTestCase):
    """Blocked-OQ fixtures both ways (S9 DoD's fourth box): open tracker + in-scope (blocked)
    sets the hard-gate fact; a question-decision:v1 comment (Tier 1) clears it."""

    def test_open_tracker_in_scope_blocked_sets_hard_gate(self):
        envelope = self._envelope(fixture_case="prep_resolver_oq_blocked_open")
        self.assertEqual(len(envelope["open_questions"]), 1)
        entry = envelope["open_questions"][0]
        self.assertEqual(entry["disposition"], "in-scope (blocked)")
        self.assertEqual(entry["status"], "blocked")
        self.assertFalse(entry["tracker"]["resolved"])
        self.assertTrue(envelope["vector"]["comment_only"])
        self.assertEqual(envelope["suggested_playbook"], "comment-only.md")
        # One unmissable top-level boolean — S10 must not have to derive the gate from a
        # conjunction of comment_only + per-entry statuses (S9 review advisory #2).
        self.assertTrue(envelope["open_questions_gate"]["blocked"])
        self.assertEqual(len(envelope["open_questions_gate"]["blocking"]), 1)
        self.assertEqual(envelope["open_questions_gate"]["blocking"][0]["oq_id"], entry["oq_id"])

    def test_question_decision_comment_clears_the_gate(self):
        envelope = self._envelope(
            fixture_case="prep_resolver_oq_blocked_cleared", ambient="100-fix-the-widget"
        )
        entry = envelope["open_questions"][0]
        self.assertEqual(entry["disposition"], "in-scope (blocked)")
        self.assertEqual(entry["status"], "clear")
        self.assertTrue(entry["tracker"]["resolved"])
        self.assertTrue(entry["tracker"]["decision_recorded"])
        self.assertFalse(envelope["vector"]["comment_only"])
        self.assertEqual(envelope["suggested_playbook"], "standard.md")
        self.assertFalse(envelope["open_questions_gate"]["blocked"])
        self.assertEqual(envelope["open_questions_gate"]["blocking"], [])


class DistillerBundleThresholdTests(PrepResolverSandboxTestCase):
    """Distiller bundle is staged paths, never above-threshold inline bytes (S9 DoD's fifth box)."""

    ambient_default = "100-fix-the-widget"

    def test_above_threshold_body_is_staged_as_a_path_not_inline_bytes(self):
        envelope = self._envelope(fixture_case="prep_resolver_distiller_spilled")
        self.assertEqual(envelope["sections"]["issue_body_mode"], "path")
        self.assertNotIn("issue_body", envelope["sections"])
        bundle_path = envelope["distiller_bundle"]["issue_body_path"]
        self.assertTrue(Path(bundle_path).is_file())
        self.assertGreater(Path(bundle_path).stat().st_size, 25600)
        # Reuses gh_gather's own spilled file rather than writing a second copy.
        self.assertEqual(bundle_path, envelope["sections"]["issue_body_path"])


class PhasesParsingTests(PrepResolverSandboxTestCase):
    ambient_default = "100-fix-the-widget"

    def test_plan_with_phases_is_parsed_and_sha_extracted(self):
        envelope = self._envelope(fixture_case="prep_resolver_plan_with_phases")
        self.assertTrue(envelope["plan"]["present"])
        self.assertEqual(envelope["plan"]["sha"], "1a2b3c4")
        self.assertEqual(len(envelope["phases"]), 2)
        self.assertEqual(envelope["phases"][0]["kind"], "code-shipping")
        self.assertEqual(envelope["phases"][1]["depends_on"], [1])
        self.assertIsNotNone(envelope["distiller_bundle"]["plan_marker_path"])
        self.assertTrue(Path(envelope["distiller_bundle"]["plan_marker_path"]).is_file())


class MarkerAmbiguousTests(PrepResolverSandboxTestCase):
    """Duplicate plan-marker comments -> MARKER_AMBIGUOUS, forwarded verbatim from gh_gather's own
    decision (architecture.md §3's closed decision-code set is shared, not re-derived)."""

    def test_two_plan_marker_comments_yields_marker_ambiguous(self):
        result = self._run(
            ["100", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_resolver_marker_ambiguous",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "MARKER_AMBIGUOUS")
        # No workspace side effect either — the decision short-circuits before any ensure runs.
        self.assertFalse((self.root / ".worktrees").exists())


class TargetIsPrTests(PrepResolverSandboxTestCase):
    """A PR number given as the issue target -> TARGET_IS_PR, forwarded verbatim from gh_gather's
    own decision BEFORE any workspace ensure (the live-incident regression: prep reported
    `target.kind: "issue"`, derived a fresh vector, and ensured a work worktree + branch for a
    target that doesn't exist as an issue — the operator had to diagnose it from the body text
    and a stray worktree was left on disk)."""

    def test_pr_number_yields_target_is_pr_with_no_workspace_side_effect(self):
        result = self._run(
            ["89", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_resolver_target_is_pr",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "TARGET_IS_PR")
        # The load-bearing half of the fix: NO worktree, NO branch — the decision fires before
        # any workspace side effect (the fixture manifest carries only the single `issue view`
        # entry, so any later gh call would be a loud shim miss too).
        self.assertFalse((self.root / ".worktrees").exists())

    def test_decision_context_offers_the_linked_origin_issue(self):
        result = self._run(
            ["89", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_resolver_target_is_pr",
        )
        envelope = _parse_one_envelope(result.stdout)
        context = envelope["decision"]["context"]
        self.assertEqual(context["number"], 89)
        self.assertEqual(context["linked_issues"], [62])
        self.assertTrue(
            any("#62" in option for option in envelope["decision"]["options"]),
            envelope["decision"]["options"],
        )


class AuthRequiredTests(PrepResolverSandboxTestCase):
    def test_auth_failure_on_first_gh_call_yields_auth_required(self):
        result = self._run(
            ["100", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_resolver_auth_required",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        envelope_asserts.assert_full_envelope_conformance(envelope)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "AUTH_REQUIRED")


class WorkspaceMismatchTests(PrepResolverSandboxTestCase):
    """v3: the ambient-checkout assertion — WORKSPACE_MISMATCH decisions (workspace.py's, forwarded
    verbatim through prep's composition), the linked-branch adoption rung, and the `-vN`
    no-recompute acceptance. These replace the retired ROOT_* propagation coverage: stage preps no
    longer police root state (that gate lives on the workspace-creating paths only)."""

    def _mismatch(self, envelope, reason):
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "WORKSPACE_MISMATCH")
        self.assertEqual(envelope["decision"]["context"]["reason"], reason)

    def test_wrong_branch_is_a_branch_mismatch(self):
        envelope = self._envelope(
            fixture_case="prep_resolver_row_no_prior_pr", ambient="999-unrelated-work"
        )
        self._mismatch(envelope, "branch_mismatch")
        self.assertEqual(envelope["decision"]["context"]["actual_branch"], "999-unrelated-work")

    def test_session_at_the_project_root_names_workspace_open(self):
        # The "operator forgot workspace-open" surface: prep run with the session sitting at the
        # main checkout itself.
        result = self._run(
            ["100", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_resolver_row_no_prior_pr",
            cwd=str(self.root),
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        self._mismatch(envelope, "at_project_root")
        self.assertTrue(
            any("workspace-open" in option for option in envelope["decision"]["options"])
        )

    def test_detached_head_is_a_mismatch(self):
        detached = self.root / ".worktrees" / "detached-view"
        detached.parent.mkdir(parents=True, exist_ok=True)
        _git(["worktree", "add", "--detach", str(detached), "origin/main"], self.root)
        result = self._run(
            ["100", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_resolver_row_no_prior_pr",
            cwd=str(detached),
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _parse_one_envelope(result.stdout)
        self._mismatch(envelope, "detached_head")

    def test_linked_branch_is_adopted_verbatim(self):
        # gh issue develop --list reports one linked branch whose name no slug computation would
        # ever produce — the ladder adopts it, and an ambient checkout on it passes exactly.
        envelope = self._envelope(
            fixture_case="prep_resolver_linked_adoption", ambient="100-custom-linked"
        )
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["workspace"]["branch"], "100-custom-linked")
        self.assertEqual(envelope["workspace"]["expected_branch"], "100-custom-linked")

    def test_vn_suffix_is_never_recomputed_against_the_pushed_branch(self):
        # The self-mismatch drift: the ambient branch already exists on origin (workspace-open
        # pushed it). Re-running collision naming would count it and expect `-v2`; the ladder's
        # pattern acceptance (`^100-`) must pass the ambient branch as-is instead.
        wt = self._mk_ambient("100-fix-the-widget")
        _git(["push", "-u", "origin", "100-fix-the-widget"], wt)
        envelope = self._envelope(
            fixture_case="prep_resolver_row_no_prior_pr", ambient="100-fix-the-widget"
        )
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["workspace"]["branch"], "100-fix-the-widget")

    def test_checkout_behind_the_remote_branch_is_stale(self):
        wt = self._mk_ambient("100-fix-the-widget")
        _git(["push", "-u", "origin", "100-fix-the-widget"], wt)
        other = gitsandbox.mk_clone(self.origin)
        self.addCleanup(other.cleanup)
        _git(["fetch", "origin", "100-fix-the-widget"], other.path)
        _git(["checkout", "100-fix-the-widget"], other.path)
        _write(Path(other.path) / "pushed.txt", "newer\n")
        _git(["add", "pushed.txt"], other.path)
        _git(["commit", "-m", "pushed elsewhere"], other.path)
        _git(["push", "origin", "100-fix-the-widget"], other.path)
        envelope = self._envelope(
            fixture_case="prep_resolver_row_no_prior_pr", ambient="100-fix-the-widget"
        )
        self._mismatch(envelope, "stale_checkout")

    def test_gh_linking_unsupported_degrades_with_a_notice(self):
        # The default row fixture's shim has no `gh issue develop` entry in older harness runs —
        # this fixture-level MISS (non-zero exit, no auth signature) must degrade to the computed
        # rung with the ISSUE_LINK_UNSUPPORTED notice, never crash. Simulated by pointing at a
        # fixture copy whose develop entry is a non-zero exit.
        import shutil

        src = shimenv.fixture_case_dir("prep_resolver_row_no_prior_pr")
        dst = Path(tempfile.mkdtemp(prefix="gh-resolver-nolink-"))
        self.addCleanup(lambda: shutil.rmtree(dst, ignore_errors=True))
        for f in src.iterdir():
            (dst / f.name).write_bytes(f.read_bytes())
        manifest = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
        for entry in manifest:
            if entry["argv"][:3] == ["issue", "develop", "--list"]:
                entry["exit_code"] = 1
                entry.pop("stdout_file", None)
        (dst / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        envelope = self._envelope(fixtures_dir=dst, ambient="100-fix-the-widget")
        self.assertEqual(envelope["status"], "ok")
        self.assertIn("ISSUE_LINK_UNSUPPORTED", envelope["notices"])
        self.assertEqual(envelope["workspace"]["branch"], "100-fix-the-widget")


class RefreshModeTests(PrepResolverSandboxTestCase):
    """--refresh re-derives volatile facts without re-running workspace-ensure hooks or
    re-reading gate config (mirrors tests/test_prep_evaluator.py's RefreshModeTests contract) —
    but UNLIKE prep_evaluator, prep_resolver's --refresh path still shells out to `git ls-remote`
    for epic-branch discovery / branch-collision suffixing (docs/specs/resolver.md names these as
    volatile facts a re-entrant run must re-derive, e.g. a branch collision that appeared since
    the first run). That means these tests need a REAL local git sandbox `--root` — passing none
    (prep_resolver.py defaults `--root` to `.`) would run those `git` calls against this test
    process's own cwd, which on a real contributor checkout is a clone of the actual GitHub
    remote: a live-network call the offline harness must never make (architecture.md §10; the
    orchestrator's Linux-container sanity check caught exactly this — `git ls-remote` inside the
    live repo checkout fails hard with no network, and silently succeeds instead of failing the
    test on a machine that does have network access to that remote, which is the worse failure
    mode). `PrepResolverSandboxTestCase.setUp` gives every test here the same local
    origin+clone every other test in this suite uses — never a real URL.
    """

    def test_refresh_never_touches_workspace_hooks_or_gate_config(self):
        envelope = self._envelope(fixture_case="prep_resolver_row_no_prior_pr", extra_args=["--refresh"])
        self.assertEqual(envelope["status"], "ok")
        self.assertNotIn("workspace", envelope)
        self.assertEqual(envelope["config"], {})
        self.assertFalse(envelope["root"]["fresh"])
        # No worktree was created — the workspace-ensure step (the part --refresh skips) never ran.
        self.assertFalse((self.root / ".worktrees").exists())

    def test_refresh_still_reports_vector_and_dod(self):
        envelope = self._envelope(fixture_case="prep_resolver_row_no_prior_pr", extra_args=["--refresh"])
        self.assertEqual(envelope["vector"]["type"], "standard")
        self.assertEqual(len(envelope["dod"]), 1)

    def test_refresh_skips_the_expected_branch_ladder_entirely(self):
        # v3: --refresh omits the workspace assertion, so the ladder (and its gh issue develop
        # lookup / ls-remote naming calls) never runs — the branch already exists and is the
        # ambient checkout's own state, not a volatile fact to re-derive. The retired v2 test here
        # asserted --refresh re-ran branch-collision naming; the minted-branch fact is gone.
        envelope = self._envelope(fixture_case="prep_resolver_row_no_prior_pr", extra_args=["--refresh"])
        self.assertNotIn("branch", envelope)
        self.assertNotIn("workspace", envelope)


class SingleInvocationBudgetTests(PrepResolverSandboxTestCase):
    """Single-invocation budget: the canonical (standard/fresh/no-OQ/no-epic) path's shim call
    count is bounded and stable, both an upper AND a lower bound (S9 DoD's "conformance + call
    budget as S6")."""

    def test_shim_call_count_for_one_happy_run_is_exactly_six(self):
        # gh calls on the canonical no-prior-PR path: issue view (+deps), paginated comments,
        # open-PR search, current-user, closed-PR search (only reached because open_prs was
        # empty), and the linked-branch lookup (`gh issue develop --list`, v3's ladder rung 2) —
        # six, no more, no fewer. The shim exits 2 loudly on any un-fixtured argv
        # (tests/README.md), so if this test passes at all, every gh call prep made was one of
        # these six.
        result = self._run(
            ["100", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_resolver_row_no_prior_pr",
            cwd=str(self._mk_ambient("100-fix-the-widget")),
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        manifest_path = shimenv.fixture_case_dir("prep_resolver_row_no_prior_pr") / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 6)

    def test_no_gh_call_is_repeated_within_one_run(self):
        manifest_path = shimenv.fixture_case_dir("prep_resolver_row_no_prior_pr") / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        argv_tuples = [tuple(entry["argv"]) for entry in manifest]
        self.assertEqual(len(argv_tuples), len(set(argv_tuples)), "duplicate argv in manifest")

    def test_open_pr_row_short_circuits_the_closed_pr_search(self):
        # When an open PR already exists, the closed-PR search must NOT run at all (mode
        # derivation is mutually exclusive across rows), and continue mode's ladder rung 1 means
        # the linked-branch lookup is skipped too — a strictly SMALLER manifest than the
        # no-prior-PR case proves the lower bound half of the two-sided budget.
        result = self._run(
            ["100", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            fixture_case="prep_resolver_row_open_yours",
            cwd=str(self._mk_ambient("100-fix-the-widget")),
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        manifest_path = shimenv.fixture_case_dir("prep_resolver_row_open_yours") / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 4)


class PureHelperUnitTests(unittest.TestCase):
    """Direct, in-process tests of prep_resolver's pure classification/derivation helpers — no
    subprocess, no shim, no git sandbox needed (mirrors test_prep_evaluator.py's
    PureHelperUnitTests style)."""

    def test_detect_type_epic_by_label(self):
        self.assertEqual(prep_resolver._detect_type(["epic"], "Sandbox fixture"), "epic")

    def test_detect_type_epic_by_title_prefix_case_insensitive(self):
        self.assertEqual(prep_resolver._detect_type([], "EPIC: sandbox fixture"), "epic")

    def test_detect_type_story_by_label(self):
        self.assertEqual(prep_resolver._detect_type(["story"], "Story A"), "story")

    def test_detect_type_standard_default(self):
        self.assertEqual(prep_resolver._detect_type(["bug"], "Fix the thing"), "standard")

    def test_compute_fresh_slug_worked_examples_from_the_spec(self):
        self.assertEqual(
            prep_resolver.compute_fresh_slug("Daily Journal Visual Redesign"),
            "daily-journal-visual-redesign",
        )
        self.assertEqual(
            prep_resolver.compute_fresh_slug("Epic: Macro Radials Data"), "macro-radials-data"
        )
        self.assertEqual(
            prep_resolver.compute_fresh_slug("Auth/Token Refresh (Phase 2)"),
            "auth-token-refresh-phase-2",
        )

    def test_compute_fresh_slug_truncates_on_a_dash_boundary(self):
        title = "A " * 40  # produces a long run of "a-a-a-..." past the 50-char cap
        slug = prep_resolver.compute_fresh_slug(title)
        self.assertLessEqual(len(slug), 50)
        self.assertFalse(slug.endswith("-"))

    def test_audit_ref_standard_is_main(self):
        self.assertEqual(prep_resolver._audit_ref("standard", None, "main"), "main")

    def test_audit_ref_epic_uses_the_epic_branch(self):
        self.assertEqual(prep_resolver._audit_ref("epic", "epic/1-x", "main"), "epic/1-x")

    def test_audit_ref_story_with_no_parent_is_main(self):
        self.assertEqual(prep_resolver._audit_ref("story", None, "main"), "main")

    def test_suggested_playbook_comment_only_wins_over_type(self):
        self.assertEqual(prep_resolver._suggested_playbook("epic", True), "comment-only.md")

    def test_suggested_playbook_by_type(self):
        self.assertEqual(prep_resolver._suggested_playbook("epic", False), "epic.md")
        self.assertEqual(prep_resolver._suggested_playbook("story", False), "story.md")
        self.assertEqual(prep_resolver._suggested_playbook("standard", False), "standard.md")

    def test_extract_plan_sha_from_header_line(self):
        body = "**Implementation plan** — #1 x — planned 2026-01-01 at `main@abc1234`\n"
        self.assertEqual(prep_resolver._extract_plan_sha(body), "abc1234")

    def test_extract_plan_sha_missing_is_none(self):
        self.assertIsNone(prep_resolver._extract_plan_sha("no sha header here"))

    def test_stale_cutoff_boundary_just_under_is_active(self):
        # Computed relative to `datetime.now()` AT TEST-RUN TIME (never a fixture file with a
        # baked-in calendar date, which would silently drift wrong as real time passes) — the S9
        # review's "current fixture only tests 18 months" finding, closed with an exact boundary
        # pair rather than a value deep in one side's territory.
        import datetime

        just_under = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=prep_resolver._STALE_ACTIVITY_DAYS - 1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        pr = {"updatedAt": just_under}
        self.assertEqual(
            prep_resolver._classify_open_other_activity(pr),
            prep_resolver.PRIOR_PR_ROW_OPEN_OTHER_ACTIVE,
        )

    def test_stale_cutoff_boundary_just_over_is_stale(self):
        import datetime

        just_over = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=prep_resolver._STALE_ACTIVITY_DAYS + 1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        pr = {"updatedAt": just_over}
        self.assertEqual(
            prep_resolver._classify_open_other_activity(pr),
            prep_resolver.PRIOR_PR_ROW_OPEN_OTHER_STALE,
        )

    def test_stale_cutoff_days_fact_is_surfaced_on_the_prior_pr_fact(self):
        # docs/specs/resolver.md advisory: the operator/router must be able to see the exact
        # driver, not trust an opaque classification.
        open_prs = [{"number": 1, "author": {"login": "carol"}, "isDraft": False,
                     "headRefName": "carol-x", "url": "u", "updatedAt": "2026-01-01T00:00:00Z"}]
        _row, fact = prep_resolver._classify_prior_pr_row(open_prs, "reviewer-bot", None, "OPEN")
        self.assertEqual(fact["stale_cutoff_days"], prep_resolver._STALE_ACTIVITY_DAYS)

    def test_draft_authorship_ordering_foreign_draft_is_not_the_draft_row(self):
        # The exact ordering-bug regression, isolated to the pure classifier: a draft PR by
        # someone else must classify via _classify_open_other_activity (gated), never
        # PRIOR_PR_ROW_DRAFT (continue) — authorship is checked BEFORE draft state.
        foreign_draft = [{"number": 58, "author": {"login": "carol"}, "isDraft": True,
                           "headRefName": "carol-wip", "url": "u", "updatedAt": "2026-07-08T00:00:00Z"}]
        row, _fact = prep_resolver._classify_prior_pr_row(foreign_draft, "reviewer-bot", None, "OPEN")
        self.assertNotEqual(row, prep_resolver.PRIOR_PR_ROW_DRAFT)
        self.assertIn(row, prep_resolver._GATED_ROWS)

    def test_own_draft_is_still_the_draft_row(self):
        own_draft = [{"number": 58, "author": {"login": "reviewer-bot"}, "isDraft": True,
                      "headRefName": "100-x", "url": "u", "updatedAt": "2026-07-08T00:00:00Z"}]
        row, _fact = prep_resolver._classify_prior_pr_row(own_draft, "reviewer-bot", None, "OPEN")
        self.assertEqual(row, prep_resolver.PRIOR_PR_ROW_DRAFT)
        self.assertIn(row, prep_resolver._CONTINUE_ROWS)


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
            [sys.executable, str(SCRIPT), "100"],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
