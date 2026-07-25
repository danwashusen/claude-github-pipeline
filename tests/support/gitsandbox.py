"""Ephemeral git origin + clone for offline workspace/lifecycle tests.

Provides ``mk_origin()`` and ``mk_clone(origin)`` for building a temp **bare** origin repo and a
working clone of it, each in its own ``tempfile``-managed directory, with guaranteed cleanup —
pass or fail — via ``unittest.TestCase.addCleanup`` or the ``git_sandbox()`` context manager
below.

No shim is involved here (per architecture.md §10, "Git sandbox: ... no shim needed") — this
module shells out to the real ``git`` binary, which is an allowed spawnable per architecture.md
§1. It never touches the network (everything happens between two local temp directories) and
never invokes ``gh``.

All temp paths are resolved through ``Path.resolve()`` before being handed back, because on
macOS ``/tmp`` is a symlink to ``/private/tmp`` — comparing an un-resolved path against a
resolved one elsewhere in the codebase would spuriously mismatch. Paths are built with
``pathlib.Path`` per architecture.md §1; ``str()`` is applied only at the boundary where
``subprocess`` needs a plain string argument.
"""

import contextlib
import shutil
import subprocess
import tempfile
from pathlib import Path

_GIT = shutil.which("git")
if _GIT is None:  # pragma: no cover - environment precondition, not exercised in CI
    raise RuntimeError("gitsandbox: `git` was not found on PATH; the offline harness needs it")


def _run_git(args, cwd, env=None):
    """Run `git <args>` in `cwd`, argument-list only, UTF-8 pinned. Raises on nonzero exit."""
    result = subprocess.run(
        [_GIT] + args,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "gitsandbox: `git %s` (cwd=%s) failed with exit %d\nstdout:\n%s\nstderr:\n%s"
            % (" ".join(args), cwd, result.returncode, result.stdout, result.stderr)
        )
    return result


class Origin:
    """A temp bare origin repository."""

    def __init__(self, path):
        self.path = path  # resolved absolute Path to the bare repo directory

    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)


class Clone:
    """A temp working clone of an Origin."""

    def __init__(self, path, origin):
        self.path = path  # resolved absolute Path to the clone's working directory
        self.origin = origin

    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)


def mk_origin(initial_branch="main"):
    """Create a temp bare origin repo, seeded with one commit on ``initial_branch``.

    A bare repo alone has no commits and no default branch until something pushes to it, so this
    seeds it via a throwaway seed clone (created and discarded internally) — callers get back an
    ``Origin`` that already has history to clone from, which is what every real caller needs.
    Returns an ``Origin`` whose ``.path`` is a resolved ``Path``. Caller is responsible for
    calling ``.cleanup()`` (or use the ``git_sandbox()`` context manager / ``addCleanup`` below).
    """
    bare_dir = Path(tempfile.mkdtemp(prefix="gh-pipeline-test-origin-")).resolve()
    _run_git(["init", "--bare", "--initial-branch=" + initial_branch, str(bare_dir)], cwd=None)

    seed_dir = Path(tempfile.mkdtemp(prefix="gh-pipeline-test-origin-seed-"))
    try:
        _run_git(["clone", str(bare_dir), str(seed_dir)], cwd=None)
        _run_git(["config", "user.email", "sandbox@example.invalid"], cwd=seed_dir)
        _run_git(["config", "user.name", "gh-pipeline sandbox"], cwd=seed_dir)
        readme = seed_dir / "README.md"
        readme.write_text("gh-pipeline offline test sandbox origin\n", encoding="utf-8")
        _run_git(["add", "README.md"], cwd=seed_dir)
        _run_git(["commit", "-m", "seed commit"], cwd=seed_dir)
        _run_git(["push", "origin", "HEAD:" + initial_branch], cwd=seed_dir)
    finally:
        shutil.rmtree(seed_dir, ignore_errors=True)

    return Origin(bare_dir)


def mk_clone(origin):
    """Clone ``origin`` (an ``Origin``) into a fresh temp working directory.

    Returns a ``Clone`` whose ``.path`` is a resolved ``Path``, with a configured throwaway
    ``user.name``/``user.email`` so commits made against it don't depend on ambient git config.
    Caller is responsible for calling ``.cleanup()`` (or use ``git_sandbox()`` / ``addCleanup``).
    """
    clone_dir = Path(tempfile.mkdtemp(prefix="gh-pipeline-test-clone-")).resolve()
    # tempfile.mkdtemp already created clone_dir; `git clone` is fine cloning into an *empty*
    # pre-existing directory (it only refuses a non-empty one), so this is not a conflict.
    _run_git(["clone", str(origin.path), str(clone_dir)], cwd=None)
    _run_git(["config", "user.email", "sandbox@example.invalid"], cwd=clone_dir)
    _run_git(["config", "user.name", "gh-pipeline sandbox"], cwd=clone_dir)
    return Clone(clone_dir, origin)


@contextlib.contextmanager
def git_sandbox(initial_branch="main"):
    """Context manager yielding ``(origin, clone)``; cleans both up on exit, pass or fail.

    Usage::

        with git_sandbox() as (origin, clone):
            ...

    Equivalent to calling ``mk_origin()`` / ``mk_clone()`` directly and registering cleanup via
    ``addCleanup`` in a ``unittest.TestCase`` — this form is for use outside a TestCase (or when a
    test wants scoped cleanup instead of end-of-test cleanup).
    """
    origin = mk_origin(initial_branch=initial_branch)
    try:
        clone = mk_clone(origin)
        try:
            yield origin, clone
        finally:
            clone.cleanup()
    finally:
        origin.cleanup()
