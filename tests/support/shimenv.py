"""Builds the intercepted-PATH environment the offline harness runs under.

Centralizes the answer to "how does `gh` resolve to the shim, and how do we prove the real `gh`
is unreachable" so both ``tests/run.py`` (whole-suite wiring) and individual tests (which may
spawn a subprocess that itself calls `gh`, e.g. a script-under-test or a direct shim probe) share
one implementation instead of re-deriving PATH logic per test file.

Layout on disk this module depends on (paths are relative to the repo root, computed from this
file's own location so it works regardless of cwd):

    tests/shim/gh              the fixture-replaying shim (first on PATH — real interception)
    tests/support/poison/gh    the tripwire sentinel (never placed ahead of the shim in normal
                                use; a test may build a PATH containing *only* the poison dir to
                                simulate "shim missing" and confirm the tripwire itself works)

``GH_SHIM_FIXTURES`` selects which fixture case (a directory under ``tests/fixtures/``) the shim
reads from; it is not set by this module — callers set it per-test to the fixture case they want.

Paths are built with ``pathlib.Path`` per architecture.md §1, and converted to ``str`` only at
the boundary where one is required (environment variable values and PATH entries must be `str`,
not `Path`, when handed to `os.environ` / `subprocess`).
"""

import os
import shutil
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
TESTS_DIR = _THIS_DIR.parent
REPO_ROOT = TESTS_DIR.parent

SHIM_DIR = TESTS_DIR / "shim"
POISON_DIR = _THIS_DIR / "poison"
FIXTURES_DIR = TESTS_DIR / "fixtures"

SHIM_GH_PATH = SHIM_DIR / "gh"
POISON_GH_PATH = POISON_DIR / "gh"


def fixture_case_dir(case_name):
    """Absolute path to ``tests/fixtures/<case_name>``, for setting ``GH_SHIM_FIXTURES``."""
    return FIXTURES_DIR / case_name


def intercepted_env(base_env=None, fixture_case=None, extra=None):
    """Return a fresh env dict wired so any ``gh`` lookup on PATH resolves to the shim.

    - ``PATH`` is rebuilt as ``[SHIM_DIR, POISON_DIR] + inherited PATH entries``: the shim comes
      first (so it — and only it — answers for `gh`), the poison dir comes second as a tripwire
      in case something on the *inherited* PATH also has a `gh` and the shim dir were ever
      skipped, and the rest of the inherited PATH is preserved so `git`, `python3`, and other
      real tooling the harness itself needs still resolve normally.
    - ``GH_SHIM_FIXTURES`` is set to ``str(fixture_case_dir(fixture_case))`` when ``fixture_case``
      is given; otherwise left unset (any `gh` call in that subprocess is an un-fixtured miss).
    - ``base_env`` defaults to a copy of ``os.environ``; ``extra`` (a dict) is applied last and
      wins over everything else, for test-specific overrides.
    """
    env = dict(base_env if base_env is not None else os.environ)
    inherited_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(
        [str(SHIM_DIR), str(POISON_DIR)] + ([inherited_path] if inherited_path else [])
    )
    if fixture_case is not None:
        env["GH_SHIM_FIXTURES"] = str(fixture_case_dir(fixture_case))
    else:
        env.pop("GH_SHIM_FIXTURES", None)
    if extra:
        env.update(extra)
    return env


def poison_only_env(base_env=None):
    """Return an env whose PATH puts the poison dir first, with **no shim dir** — for
    self-testing the tripwire in isolation, simulating "what if the shim were absent from PATH".

    This deliberately excludes ``SHIM_DIR`` (so a `gh` PATH lookup cannot reach the shim) but
    keeps the rest of the inherited PATH *after* the poison dir — not stripped to only the
    poison dir — because the poison script's own ``#!/usr/bin/env python3`` shebang needs `env`
    and `python3` resolvable to even launch; a fully-starved PATH would fail with a shebang
    "command not found" (exit 127) before the poison sentinel's own code ever runs, which would
    silently defeat the very check this env is for. `gh` PATH lookups still resolve to the
    poison first, since it precedes the rest of PATH — that ordering is the property under test.
    """
    env = dict(base_env if base_env is not None else os.environ)
    inherited_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join([str(POISON_DIR)] + ([inherited_path] if inherited_path else []))
    env.pop("GH_SHIM_FIXTURES", None)
    return env


def which_gh_under(env):
    """Resolve `gh` using ``env["PATH"]`` the way a real subprocess lookup would.

    ``shutil.which`` consults the *current* process's PATH unless told otherwise via its ``path``
    kwarg, so this wraps that to resolve against an arbitrary candidate env's PATH instead of
    this process's own.
    """
    return shutil.which("gh", path=env.get("PATH"))
