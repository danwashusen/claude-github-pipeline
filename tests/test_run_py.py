"""Self-tests for tests/run.py itself: discovery, exit-code propagation, PATH self-check.

A deliberately-failing test cannot live in this repo's real tests/test_*.py tree (run.py would
then always exit non-zero). Instead these tests build a *throwaway nested copy* of the harness
layout — its own ``tests/`` package (named exactly ``tests``, since run.py's own
``from tests.support import shimenv`` requires that literal package name) inside a fresh temp
parent directory, with its own single test_*.py — and run that nested harness's run.py in a
subprocess, asserting on its exit code and output. This proves failure propagation without
poisoning this suite's own green run.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
RUN_PY_NAME = "run.py"


class DiscoveryAndSuccessTests(unittest.TestCase):
    def test_run_py_exits_zero_on_a_passing_nested_suite(self):
        with _NestedHarness(
            {
                "test_passing.py": (
                    "import unittest\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_ok(self):\n"
                    "        self.assertEqual(1, 1)\n"
                )
            }
        ) as nested:
            result = nested.run()
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_run_py_discovers_multiple_test_files(self):
        with _NestedHarness(
            {
                "test_a.py": (
                    "import unittest\n"
                    "class A(unittest.TestCase):\n"
                    "    def test_a(self):\n"
                    "        print('RAN_A')\n"
                ),
                "test_b.py": (
                    "import unittest\n"
                    "class B(unittest.TestCase):\n"
                    "    def test_b(self):\n"
                    "        print('RAN_B')\n"
                ),
            }
        ) as nested:
            result = nested.run(extra_args=["-v"])
            combined = result.stdout + result.stderr
            self.assertIn("RAN_A", combined)
            self.assertIn("RAN_B", combined)
            self.assertEqual(result.returncode, 0)


class FailurePropagationTests(unittest.TestCase):
    def test_run_py_exits_nonzero_on_a_failing_nested_test(self):
        with _NestedHarness(
            {
                "test_failing.py": (
                    "import unittest\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_deliberately_fails(self):\n"
                    "        self.assertEqual(1, 2, 'deliberate failure for run.py self-test')\n"
                )
            }
        ) as nested:
            result = nested.run()
            self.assertNotEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_run_py_exits_nonzero_on_a_nested_error_not_just_assertion_failure(self):
        with _NestedHarness(
            {
                "test_erroring.py": (
                    "import unittest\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_raises(self):\n"
                    "        raise RuntimeError('deliberate error for run.py self-test')\n"
                )
            }
        ) as nested:
            result = nested.run()
            self.assertNotEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_one_failure_among_passes_still_fails_the_whole_run(self):
        with _NestedHarness(
            {
                "test_mixed.py": (
                    "import unittest\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_pass_one(self):\n"
                    "        self.assertTrue(True)\n"
                    "    def test_pass_two(self):\n"
                    "        self.assertTrue(True)\n"
                    "    def test_the_one_that_fails(self):\n"
                    "        self.fail('deliberate')\n"
                )
            }
        ) as nested:
            result = nested.run()
            self.assertNotEqual(result.returncode, 0, msg=result.stdout + result.stderr)


class PathSelfCheckTests(unittest.TestCase):
    def test_run_py_fails_fast_if_gh_would_not_resolve_to_shim(self):
        # Simplest reliable offline way to simulate "shim missing/broken": strip the execute bit
        # from the nested copy's own shim binary so PATH lookup skips it as non-executable, and
        # confirm run.py's startup self-check catches that before running any test.
        with _NestedHarness(
            {
                "test_passing.py": (
                    "import unittest\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_ok(self):\n"
                    "        pass\n"
                )
            }
        ) as nested:
            shim_gh = nested.tests_dir / "shim" / "gh"
            shim_gh.chmod(0o644)
            result = nested.run()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FATAL", result.stdout + result.stderr)


class _NestedHarness:
    """Builds `<tmp>/tests/{run.py,shim/,support/,__init__.py,<given test files>}` and runs the
    nested run.py as `python3 tests/run.py` with cwd=<tmp>, so the nested process's own
    `sys.path.insert(0, REPO_ROOT)` + `from tests.support import shimenv` resolve against the
    nested tree, completely isolated from this real suite.
    """

    def __init__(self, test_files):
        self._test_files = test_files
        self._parent = None
        self.tests_dir = None

    def __enter__(self):
        self._parent = Path(tempfile.mkdtemp(prefix="gh-pipeline-nested-harness-")).resolve()
        self.tests_dir = self._parent / "tests"
        self.tests_dir.mkdir()

        shutil.copy2(_THIS_DIR / RUN_PY_NAME, self.tests_dir / RUN_PY_NAME)
        shutil.copytree(_THIS_DIR / "shim", self.tests_dir / "shim")
        shutil.copytree(_THIS_DIR / "support", self.tests_dir / "support")
        shutil.copy2(_THIS_DIR / "__init__.py", self.tests_dir / "__init__.py")

        for name, source in self._test_files.items():
            (self.tests_dir / name).write_text(source, encoding="utf-8")

        return self

    def __exit__(self, exc_type, exc, tb):
        shutil.rmtree(self._parent, ignore_errors=True)
        return False

    def run(self, extra_args=None):
        args = ["python3", str(self.tests_dir / RUN_PY_NAME)] + (extra_args or [])
        return subprocess.run(
            args,
            cwd=str(self._parent),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
