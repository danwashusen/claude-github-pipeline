#!/usr/bin/env python3
"""Cross-consumer contract for the `## Phases` grammar (#18).

`parse.parse_phases` is ONE parser with TWO consumers that must behave DIFFERENTLY on a malformed
`## Phases` section, and the difference is deliberate:

  * **prep_resolver hard-fails** with `PHASES_MALFORMED`. It *executes* the plan — it cannot ship
    phase N it cannot read — and its documented remedy is to re-route to the planner.
  * **prep_planner stays best-effort**: `status: ok`, `slices.diff.prior_phases_parsed: false`, an
    `attention` line, and no decision. A revise run exists to *repair* a bad plan; hard-failing
    would mean the only tool that can rewrite the section refuses to start because the section is
    broken — and the plan footer forbids hand-editing it.

Safety is not weakened by the planner's leniency: the resolver still refuses the identical body, so
a malformed plan stays re-plannable but never executable. This file pins the asymmetry on
byte-identical input so nobody "unifies" the two paths later.

Test topology matches tests/test_prep_planner.py / tests/test_prep_resolver.py: `gh` is the offline
fixture shim, `git` is a real temp sandbox, both preps run as real subprocesses.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import parse  # noqa: E402
from tests.support import gitsandbox, shimenv  # noqa: E402

PLANNER = REPO_ROOT / "scripts" / "prep_planner.py"
RESOLVER = REPO_ROOT / "scripts" / "prep_resolver.py"

# The exact malformed section both fixtures carry — the #640 free-form-sequencing regression shape.
MALFORMED_SECTION = "## Phases\nFirst the writer, then the flag. Ship them in that order.\n"


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=str(cwd), check=True, capture_output=True)


def _one_envelope(stdout):
    envelopes = [
        json.loads(line) for line in stdout.splitlines() if line.strip().startswith("{")
    ]
    assert len(envelopes) == 1, "expected exactly one envelope, got %d" % len(envelopes)
    return envelopes[0]


class MalformedPhasesAsymmetryTests(unittest.TestCase):
    def setUp(self):
        self.origin = gitsandbox.mk_origin()
        self.addCleanup(self.origin.cleanup)
        self.clone = gitsandbox.mk_clone(self.origin)
        self.addCleanup(self.clone.cleanup)
        self.root = self.clone.path
        (self.root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
        _git(["add", ".gitignore"], self.root)
        _git(["commit", "-m", "seed gitignore"], self.root)
        _git(["push", "origin", "HEAD:main"], self.root)
        self.scratch = str(self.root / ".scratch")
        Path(self.scratch).mkdir(parents=True, exist_ok=True)

    def _run(self, script, args, fixture_case, cwd):
        return subprocess.run(
            [sys.executable, str(script)] + args,
            env=shimenv.intercepted_env(base_env=os.environ, fixture_case=fixture_case),
            cwd=str(cwd),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_both_fixtures_carry_the_same_malformed_section(self):
        """The comparison is only meaningful on byte-identical input."""
        for case, filename in (
            ("prep_planner_slices_prior_plan_malformed", "comments.json"),
            ("prep_resolver_plan_phases_malformed", "comments_with_plan.json"),
        ):
            comments = json.loads(
                (shimenv.fixture_case_dir(case) / filename).read_text(encoding="utf-8")
            )
            plans = [
                c["body"]
                for c in comments
                if (c.get("body") or "").startswith("<!-- implementation-plan:v1 -->")
            ]
            self.assertEqual(len(plans), 1, case)
            self.assertTrue(plans[0].endswith(MALFORMED_SECTION), case)

    def test_the_shared_parser_does_raise_on_it(self):
        with self.assertRaises(parse._PhasesMalformed):  # noqa: SLF001
            parse.parse_phases(MALFORMED_SECTION)

    def test_resolver_hard_fails_with_phases_malformed(self):
        # The resolver asserts an ambient work checkout, so run from inside it.
        branch = "100-fix-the-widget"
        worktree = self.root / ".worktrees" / branch
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _git(["worktree", "add", "-b", branch, str(worktree), "origin/main"], self.root)

        result = self._run(
            RESOLVER,
            ["100", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            "prep_resolver_plan_phases_malformed",
            worktree,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _one_envelope(result.stdout)
        self.assertEqual(envelope["status"], "needs_decision")
        self.assertEqual(envelope["decision"]["code"], "PHASES_MALFORMED")

    def test_planner_stays_ok_and_reports_the_parse_failure_as_a_fact(self):
        result = self._run(
            PLANNER,
            ["250", "octo/widgets", "--root", str(self.root), "--scratch-dir", self.scratch],
            "prep_planner_slices_prior_plan_malformed",
            self.root,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        envelope = _one_envelope(result.stdout)
        self.assertEqual(envelope["status"], "ok")
        self.assertNotIn("decision", envelope)
        diff = envelope["slices"]["diff"]
        self.assertFalse(diff["prior_phases_parsed"])
        self.assertFalse(diff["computed"])
        self.assertIn("line_number", diff["prior_phases_error"])


if __name__ == "__main__":
    unittest.main()
