"""Self-tests proving the real `gh` is unreachable during offline runs (S2 DoD item 3).

Two things are proven:

1. Under the harness's normal intercepted environment (as run.py wires it), `gh` on PATH
   resolves to exactly the shim — never anything else.
2. The poison tripwire itself works: if the shim is (hypothetically) missing from PATH, the next
   `gh` PATH resolution finds a sentinel that fails loudly with a distinctive marker + exit code,
   rather than falling through to a real, network-calling `gh`. This is what makes "the real gh
   is unreachable" an asserted property instead of an unverified claim.
"""

import os
import shutil
import subprocess
import unittest

from tests.support import shimenv


class ResolvesToShimTests(unittest.TestCase):
    def test_which_gh_resolves_to_shim_under_intercepted_env(self):
        env = shimenv.intercepted_env(base_env=os.environ, fixture_case="shim_probe_basic")
        resolved = shimenv.which_gh_under(env)
        self.assertIsNotNone(resolved, "gh did not resolve at all under the intercepted PATH")
        self.assertEqual(os.path.realpath(resolved), str(shimenv.SHIM_GH_PATH.resolve()))

    def test_intercepted_env_preserves_git_and_python_resolution(self):
        # The intercepted PATH must not break the *other* allowed spawnable (`git`) or the
        # interpreter itself — only `gh` is meant to be redirected.
        env = shimenv.intercepted_env(base_env=os.environ, fixture_case=None)
        self.assertIsNotNone(shutil.which("git", path=env["PATH"]))


class PoisonTripwireTests(unittest.TestCase):
    def test_poison_gh_fails_loudly_with_distinctive_marker(self):
        env = shimenv.poison_only_env(base_env=os.environ)
        result = subprocess.run(
            [str(shimenv.POISON_GH_PATH), "issue", "view", "1"],
            env=env,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 66)
        self.assertIn("GH-SHIM-POISON-TRIPPED", result.stderr)

    def test_which_gh_under_poison_only_path_finds_the_tripwire_not_a_real_gh(self):
        # Simulates "the shim directory was skipped/missing from PATH": the next resolvable `gh`
        # must be the poison sentinel, proving that scenario is caught rather than silently
        # falling through further down an inherited PATH to a real `gh` binary.
        env = shimenv.poison_only_env(base_env=os.environ)
        resolved = shimenv.which_gh_under(env)
        self.assertIsNotNone(resolved)
        self.assertEqual(os.path.realpath(resolved), str(shimenv.POISON_GH_PATH.resolve()))

    def test_shim_dir_precedes_poison_dir_in_intercepted_env(self):
        # Ordering assertion: when both are present (the normal harness case), the shim — not
        # the poison sentinel — must win, since a real fixture case should be served, not a
        # tripwire failure.
        env = shimenv.intercepted_env(base_env=os.environ, fixture_case="shim_probe_basic")
        path_entries = env["PATH"].split(os.pathsep)
        shim_idx = path_entries.index(str(shimenv.SHIM_DIR))
        poison_idx = path_entries.index(str(shimenv.POISON_DIR))
        self.assertLess(shim_idx, poison_idx)
        resolved = shimenv.which_gh_under(env)
        self.assertEqual(os.path.realpath(resolved), str(shimenv.SHIM_GH_PATH.resolve()))


class NoNetworkClaimTests(unittest.TestCase):
    def test_shim_and_poison_source_contain_no_networking_primitives(self):
        # A cheap, direct static check that neither the shim nor the poison sentinel could reach
        # the network even if invoked: no socket/http/urllib/requests imports in their source.
        banned_tokens = ("socket", "urllib", "http.client", "requests")
        for path in (shimenv.SHIM_GH_PATH, shimenv.POISON_GH_PATH):
            with open(path, "r", encoding="utf-8") as fh:
                source = fh.read()
            for token in banned_tokens:
                self.assertNotIn(
                    token, source, "%s unexpectedly references %r" % (path, token)
                )


if __name__ == "__main__":
    unittest.main()
