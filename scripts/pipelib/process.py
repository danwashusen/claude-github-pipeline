"""The locked-down subprocess runner (architecture.md §1, §3): the only sanctioned way a v2
script spawns an external process — everything except the §1 carve-out (:mod:`pipelib.hooks`)
goes through here.

Guarantees, by construction, not by convention:

- Accepts an **argument list only** — a ``str`` command raises ``TypeError`` before any process is
  spawned, rather than being silently handed to a shell.
- Refuses any ``argv[0]`` that isn't exactly ``"git"`` or ``"gh"`` — raises ``ValueError`` before
  spawning. These are the only two external processes architecture.md §1 permits a script to
  spawn.
- Never passes ``shell=True`` to ``subprocess`` — there is no code path in this module that can
  set it, since the ``subprocess.run`` call site hard-codes ``shell=False``.
- Pins ``encoding="utf-8"`` on the call, so stdout/stderr always decode as ``str`` the same way on
  macOS and Linux regardless of locale.

A `gh` invocation that fails with `gh`'s own "authentication required" signature is classified
into the ``AUTH_REQUIRED`` decision code (architecture.md §3: "detected by the pipelib runner, any
script") rather than left as an undifferentiated non-zero exit, so every calling script gets the
same detection for free instead of re-implementing it.
"""

import subprocess

from pipelib.decisions import AUTH_REQUIRED

# The only two binaries this runner will spawn (architecture.md §1). Exact names, not paths —
# resolution against PATH is subprocess's/the OS's job, same as any other command lookup; the
# test harness's shim (tests/shim/gh) relies on ordinary PATH resolution to intercept `gh` calls,
# so this module must not hard-code an absolute path here.
ALLOWED_BINARIES = frozenset({"git", "gh"})

# `gh`'s own documented exit-code contract (`gh help exit-codes`): exit code 4 means "the command
# requires authentication." This is the primary, version-stable signal — an exact integer, not a
# stderr string that varies by gh version or locale.
GH_AUTH_REQUIRED_EXIT_CODE = 4

# Defensive secondary signal for older/nonstandard `gh` builds that might not use exit 4
# consistently: a case-insensitive substring match against stderr for gh's well-known
# authentication-failure phrasing. Kept narrow (three specific, stable phrases) so a match here
# is never a false positive on an unrelated permission-flavored error message.
_GH_AUTH_STDERR_MARKERS = (
    "gh auth login",
    "bad credentials",
    "http 401",
)


class CommandResult:
    """The result of a runner call: ``returncode``, ``stdout``, ``stderr`` (all present), plus
    ``auth_required`` — ``True`` iff this was a `gh` invocation classified as an authentication
    failure per :data:`GH_AUTH_REQUIRED_EXIT_CODE` or the stderr markers above.

    A plain, attribute-access object (not a dict) so call sites read ``result.stdout`` rather than
    ``result["stdout"]`` — this mirrors the ``subprocess.CompletedProcess`` shape this module
    wraps, minimizing surprise for anyone who already knows that stdlib API.
    """

    def __init__(self, returncode, stdout, stderr, auth_required=False):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.auth_required = auth_required

    def __repr__(self):
        return (
            "CommandResult(returncode=%r, auth_required=%r, stdout=%r, stderr=%r)"
            % (self.returncode, self.auth_required, self.stdout, self.stderr)
        )


def _is_gh_auth_failure(binary, returncode, stderr):
    if binary != "gh" or returncode == 0:
        return False
    if returncode == GH_AUTH_REQUIRED_EXIT_CODE:
        return True
    lowered = (stderr or "").lower()
    return any(marker in lowered for marker in _GH_AUTH_STDERR_MARKERS)


def run(argv, cwd=None, env=None, input_text=None, check=False):
    """Run ``argv`` (a list, ``argv[0]`` in {"git", "gh"}) and return a :class:`CommandResult`.

    - ``argv`` must be a ``list`` or ``tuple`` of strings, never a ``str`` — passing a ``str``
      raises ``TypeError`` immediately (this is the "refuses string commands by construction"
      guarantee; there is no shell-interpretation code path to fall into).
    - ``argv[0]`` must be exactly ``"git"`` or ``"gh"`` — anything else raises ``ValueError``
      immediately, before ``subprocess.run`` is ever called.
    - ``cwd`` / ``env`` are forwarded to ``subprocess.run`` unchanged (``env=None`` inherits the
      calling process's environment, matching ``subprocess`` defaults — callers that need PATH
      interception, as the test harness does, pass an explicit ``env``).
    - ``input_text`` (a ``str`` or ``None``) is piped to stdin — for a `gh` call that reads a body
      via ``--body-file -`` semantics, for example.
    - ``check=True`` raises ``subprocess.CalledProcessError`` on a non-zero exit **unless** the
      call was classified as a `gh` auth failure — an auth failure is a decision-worthy outcome
      the caller is expected to branch on (via ``result.auth_required``), not an exception to
      catch, so it is deliberately exempted from ``check``'s raise even when ``check=True``.
    - ``shell=True`` is never passed; there is no parameter that could result in it being set.
    - ``encoding="utf-8"`` is always pinned.
    """
    if isinstance(argv, str):
        raise TypeError(
            "pipelib.process.run: argv must be a list/tuple of strings, not a str "
            "(refusing to shell-interpret a command string) — got %r" % (argv,)
        )
    if not isinstance(argv, (list, tuple)) or not argv:
        raise TypeError(
            "pipelib.process.run: argv must be a non-empty list/tuple of strings, got %r"
            % (argv,)
        )
    binary = argv[0]
    if binary not in ALLOWED_BINARIES:
        raise ValueError(
            "pipelib.process.run: argv[0] must be one of %r, got %r — only git/gh may be "
            "spawned by a v2 script (architecture.md §1)" % (sorted(ALLOWED_BINARIES), binary)
        )

    completed = subprocess.run(
        list(argv),
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        input=input_text,
        capture_output=True,
        encoding="utf-8",
        shell=False,
        check=False,
    )

    auth_required = _is_gh_auth_failure(binary, completed.returncode, completed.stderr)

    if check and completed.returncode != 0 and not auth_required:
        raise subprocess.CalledProcessError(
            completed.returncode, list(argv), output=completed.stdout, stderr=completed.stderr
        )

    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        auth_required=auth_required,
    )


__all__ = [
    "ALLOWED_BINARIES",
    "GH_AUTH_REQUIRED_EXIT_CODE",
    "CommandResult",
    "run",
    "AUTH_REQUIRED",
]
