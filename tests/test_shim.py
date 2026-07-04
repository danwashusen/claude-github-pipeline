"""Self-tests for tests/shim/gh: prove fixture interception actually works.

These invoke the shim binary directly as a subprocess (not through the harness-wide PATH wiring
run.py does) so each test controls its own `GH_SHIM_FIXTURES` case independently and the
hit/miss behavior is exercised in isolation.
"""

import json
import os
import subprocess
import unittest

from tests.support import shimenv


def _run_shim(args, fixture_case, env_overrides=None):
    env = dict(os.environ)
    env["PATH"] = str(shimenv.SHIM_DIR) + os.pathsep + env.get("PATH", "")
    if fixture_case is not None:
        env["GH_SHIM_FIXTURES"] = str(shimenv.fixture_case_dir(fixture_case))
    else:
        env.pop("GH_SHIM_FIXTURES", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(shimenv.SHIM_GH_PATH)] + args,
        env=env,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


class ShimHitTests(unittest.TestCase):
    """A probe calling `gh` with fixtured argv receives the fixture's bytes + exit code."""

    def test_hit_returns_fixture_stdout_and_exit_code(self):
        result = _run_shim(
            ["issue", "view", "123", "--json", "body,title"],
            fixture_case="shim_probe_basic",
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload, {"body": "fixture body text", "title": "fixture issue title"})
        self.assertEqual(result.stderr, "")

    def test_hit_replays_nonzero_exit_code_and_stdout(self):
        result = _run_shim(["auth", "status"], fixture_case="shim_probe_basic")
        self.assertEqual(result.returncode, 1)
        self.assertIn("authentication check failed", result.stdout)

    def test_hit_is_exact_argv_match_not_prefix(self):
        # A near-miss (extra trailing arg) must NOT match the fixtured entry for the shorter argv.
        result = _run_shim(
            ["issue", "view", "123", "--json", "body,title", "--extra"],
            fixture_case="shim_probe_basic",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISS", result.stderr)


class ShimMissTests(unittest.TestCase):
    """Un-fixtured argv fails loudly with a helpful diff, never hangs or silently no-ops."""

    def test_miss_unfixtured_argv_exits_nonzero_with_diff(self):
        result = _run_shim(
            ["pr", "view", "999", "--json", "body"],
            fixture_case="shim_probe_basic",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISS", result.stderr)
        # The diff must show both what was received and what was available, so a future author
        # can fix the mismatch without reading shim source.
        self.assertIn("pr", result.stderr)
        self.assertIn("view", result.stderr)
        self.assertIn("issue", result.stderr)  # one of the available fixture keys
        self.assertEqual(result.stdout, "")

    def test_miss_on_empty_manifest(self):
        result = _run_shim(["issue", "view", "1"], fixture_case="shim_probe_empty")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISS", result.stderr)
        self.assertIn("empty list", result.stderr)

    def test_miss_when_fixtures_env_unset(self):
        result = _run_shim(["issue", "view", "1"], fixture_case=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISS", result.stderr)

    def test_miss_when_fixtures_dir_has_no_manifest(self):
        # GH_SHIM_FIXTURES pointing at a real but manifest-less directory is also a clean miss,
        # not a crash.
        result = _run_shim(["issue", "view", "1"], fixture_case=None, env_overrides={
            "GH_SHIM_FIXTURES": str(shimenv.TESTS_DIR),  # exists, has no manifest.json at root
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISS", result.stderr)


if __name__ == "__main__":
    unittest.main()
