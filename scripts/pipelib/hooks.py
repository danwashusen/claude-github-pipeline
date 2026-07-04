"""The hook executor — the ONE explicit carve-out from the "only git/gh, argument lists only"
subprocess rule (architecture.md §1): "the sole carve-out is `workspace.py`'s hook runner, which
executes the consuming repo's `<!-- worktree-setup/teardown -->` commands verbatim as repo-owned
opaque shell commands, cwd'd to the workspace; no other script spawns anything else."

This module exists **separately** from :mod:`pipelib.process` on purpose: keeping the carve-out in
its own, explicitly-named module means :func:`pipelib.process.run`'s allowlist
(``{"git", "gh"}``) and hard ``shell=False`` stay simple and unconditionally true — nothing in
that module ever needs an "unless it's a hook" exception. Only ``workspace.py`` (S4) is meant to
import this module; every other script's shell-out goes through :mod:`pipelib.process` instead.

The command string executed here is **repo-owned, not user/operator-typed** — it comes from the
consuming repo's own ``<!-- worktree-setup -->`` / ``<!-- worktree-teardown -->`` marker-comment
block (discovered via ``config_block.py``), the same trust boundary v1's ``worktree-hooks.sh``
already operated under. This module does not change that trust boundary; it only relocates the
carve-out into the new stdlib-Python layer, unconditionally as shell text (never as an argument
list), because a setup/teardown block is authored as a shell command line, not as a pre-tokenized
argv.
"""

import subprocess


class HookResult:
    """The result of a single hook-command run: ``returncode``, ``stdout``, ``stderr``."""

    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self):
        return "HookResult(returncode=%r, stdout=%r, stderr=%r)" % (
            self.returncode,
            self.stdout,
            self.stderr,
        )


def run_repo_owned_hook_command(command_text, cwd, env=None):
    """Execute ``command_text`` (a shell command **string**, not an argument list) via the
    system shell, with the working directory pinned to ``cwd`` (the workspace the hook is
    scoped to — architecture.md §6: "the commands inside the worktree").

    This is the **only** function in ``pipelib`` (and, by convention, in the whole ``scripts/``
    tree outside this module) permitted to pass ``shell=True`` to ``subprocess`` — its name says
    so explicitly (``run_repo_owned_hook_command``, not a generic ``run``) precisely so a reviewer
    grepping for ``shell=True`` finds one intentional, well-documented call site, never an
    accidental one hiding in a general-purpose helper.

    ``command_text`` must be a non-empty ``str`` — passing a list raises ``TypeError``, the mirror
    image of :func:`pipelib.process.run`'s guarantee: that function refuses a string and demands a
    list; this one refuses a list and demands a string, because a hook line is inherently
    shell-syntax text (pipes, redirects, `&&`), not a single argv-tokenizable command.

    ``cwd`` is required (not optional) — a hook always runs cwd'd to a specific workspace path
    (architecture.md §6's "no ambient cwd" rule applies here too: the caller names the workspace
    absolutely, this function does not default to the calling process's own cwd).

    ``encoding="utf-8"`` is pinned per architecture.md §1. Does not raise on a non-zero exit
    (``check=False``) — callers implement their own fail-fast (setup) or best-effort (teardown)
    policy (architecture.md §6) by inspecting ``HookResult.returncode`` themselves; this function
    only executes and reports, it does not decide.
    """
    if isinstance(command_text, (list, tuple)):
        raise TypeError(
            "pipelib.hooks.run_repo_owned_hook_command: command_text must be a shell command "
            "string, not an argument list (got %r) — this is the opaque-shell carve-out; use "
            "pipelib.process.run for an argument-list git/gh call" % (command_text,)
        )
    if not isinstance(command_text, str) or not command_text.strip():
        raise ValueError(
            "pipelib.hooks.run_repo_owned_hook_command: command_text must be a non-empty string"
        )
    if cwd is None:
        raise ValueError(
            "pipelib.hooks.run_repo_owned_hook_command: cwd is required — a hook always runs "
            "cwd'd to an explicit workspace path (architecture.md §6, no ambient cwd)"
        )

    completed = subprocess.run(
        command_text,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        encoding="utf-8",
        shell=True,  # nosec — the one documented, named carve-out (architecture.md §1)
        check=False,
    )
    return HookResult(
        returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr
    )


__all__ = ["HookResult", "run_repo_owned_hook_command"]
