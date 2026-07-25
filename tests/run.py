#!/usr/bin/env python3
"""Offline test harness entry point for github-pipeline v2.

Discovers and runs every ``tests/test_*.py`` via stdlib ``unittest`` (no third-party test
framework — nothing to vendor or install), after wiring the process environment so that:

- ``tests/shim/gh`` (a fixture-replaying stand-in) is first on ``PATH`` — any code under test
  that shells out to `gh` reaches the shim, never the real CLI.
- ``tests/support/poison/gh`` (a tripwire that always fails loudly) sits second on ``PATH``, so
  if the shim were ever missing/skipped, the *next* thing PATH resolution would find is a
  sentinel that screams, not a real `gh` making a live network call.
- Startup asserts ``shutil.which("gh")`` resolves to exactly the shim path — a static self-check
  that fails the whole run immediately, before any test executes, if PATH wiring is ever wrong.

Exit code is non-zero on any test failure or error (``sys.exit(not result.wasSuccessful())``),
so this composes with CI / the global DoD gate (``python3 tests/run.py`` must exit 0).

No network calls are made by this script itself. Individual tests are responsible for not making
any either (the shim + poison sentinel is what makes that enforceable rather than just claimed).

Usage:
    python3 tests/run.py              # discover + run every test_*.py under tests/
    python3 tests/run.py -v           # verbose (per-test) output
See tests/README.md for the Linux container invocation and for adding a new fixture case.
"""

import os
import shutil
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = _THIS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Make `tests` (and `from tests.support import ...`) importable regardless of the invoking cwd,
# and ahead of any same-named package that might otherwise shadow it. Also put `scripts/` on
# sys.path so `pipelib` (scripts/pipelib/, from S3 onward) and later top-level script modules
# (workspace.py, parse.py, gh_gather.py, ...) are importable by tests the same way a script
# invoked directly (its own directory on sys.path[0]) already resolves them — this is the one
# place that equivalence needs to be established for the *test* side, not per test file.
for _extra_path in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if _extra_path not in sys.path:
        sys.path.insert(0, _extra_path)

from tests.support import shimenv  # noqa: E402  (import after sys.path setup, by necessity)


def _wire_intercepted_environment():
    """Mutate this process's own environment so every subprocess it spawns inherits the
    intercepted PATH (shim first, poison second) with no fixture case selected by default —
    individual tests set ``GH_SHIM_FIXTURES`` themselves for the case they need.
    """
    intercepted = shimenv.intercepted_env(base_env=os.environ, fixture_case=None)
    os.environ["PATH"] = intercepted["PATH"]
    os.environ.pop("GH_SHIM_FIXTURES", None)


def _assert_gh_resolves_to_shim():
    resolved = shutil.which("gh")
    expected = shimenv.SHIM_GH_PATH.resolve()
    resolved_real = Path(resolved).resolve() if resolved else None
    if resolved_real != expected:
        sys.stderr.write(
            "run.py: FATAL — `gh` on PATH does not resolve to the offline shim.\n"
            "  resolved to : %r\n"
            "  expected    : %r\n"
            "This harness refuses to run any test until `gh` is guaranteed to be the shim — "
            "otherwise a test could silently reach the real `gh` and make a network call.\n"
            % (resolved, str(expected))
        )
        sys.exit(1)


def main(argv):
    _wire_intercepted_environment()
    _assert_gh_resolves_to_shim()

    verbosity = 2 if ("-v" in argv or "--verbose" in argv) else 1

    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(_THIS_DIR), pattern="test_*.py", top_level_dir=str(REPO_ROOT)
    )

    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
