#!/usr/bin/env python3
"""workspace.py — the workspace-lifecycle owner (architecture.md §6): ``ensure``/``remove``/``gc``
for the two-tier trust topology (project root = read-only vantage, always clean ``main``;
``.worktrees/`` = all mutable and pinned-ref state), plus root-freshness, ``root-status``, and
``lint``. This is authored from scratch against architecture.md §6/§3/§12 and the
``skills/_shared/worktree-lifecycle.md`` contract — not a transliteration of the v1 hook-runner
script (retired at S20; the v1 tree is in git history).

What this absorbs from v1, and what's new
------------------------------------------
The v1 hook runner only ran a consuming repo's ``<!-- worktree-setup/teardown -->``
commands inside an *already-existing* worktree (fail-fast setup, best-effort teardown, plus
``lint``) — creation/removal/reuse were the calling skill's own cwd-stateful ``git worktree``
calls. This script absorbs **both**: the hook execution (preserving v1's exact fail-fast /
best-effort / lint semantics — see :func:`_run_setup_hooks` for the full v1-key correspondence
table and the MALFORMED-block divergence note) *and* the work/read workspace lifecycle those v1
skill bodies used to hand-roll (create, reuse, remove, gc, root-freshness) — all now one
deterministic script per architecture.md §2's "facts by script, meaning by model."

Subcommands
-----------
    workspace.py ensure --work <branch> --base <ref> [--root <path>]
    workspace.py ensure --read <ref>                 [--root <path>]
    workspace.py remove --work <branch>              [--root <path>]
    workspace.py gc [--max-age <days>]               [--root <path>]
    workspace.py root-status                         [--root <path>]
    workspace.py lint <setup|teardown>               [--root <path>]

``--root`` defaults to ``.`` purely so a caller already sitting at the project root doesn't have
to repeat the obvious — every internal git call is still scoped with an explicit ``cwd`` derived
from the resolved ``--root`` or a resolved workspace path, never from the invoking process's
ambient cwd (architecture.md §6, "no ambient cwd").

Path conventions (architecture.md §6)
--------------------------------------
    work workspace : <root>/.worktrees/<branch>
    read workspace : <root>/.worktrees/ro-<ref-slug>

``<ref-slug>`` replaces every character unsafe in a single path segment (starting with ``/``, so a
multi-segment ref like ``epic/42-journal`` collapses to one segment) with ``-`` — one worktree
directory per logical ref regardless of how many slashes its name has.

Root-freshness protocol (architecture.md §6, §12)
---------------------------------------------------
Verify root is on ``main`` and clean, then ``git fetch`` then ``git merge --ff-only`` and record
the resulting SHA. Failures are §3 decisions, **never auto-fixed** (§12: "root is never written"):
``ROOT_NOT_ON_MAIN`` (HEAD isn't ``main``), ``ROOT_DIRTY`` (``git status --porcelain`` is
non-empty), ``ROOT_DIVERGED`` (``git merge --ff-only`` refuses — local root history has commits
``origin/main`` doesn't). Run before ``ensure --work``, ``remove --work``, and ``root-status`` — a
freshness failure short-circuits the whole subcommand as a ``needs_decision`` envelope with no
worktree side effect. ``ensure --read`` and ``gc`` do not require root freshness: neither forks off
the root's own HEAD (``ensure --read`` grounds directly at a freshly fetched ``origin/<ref>``, so
root-on-main+clean is irrelevant to it; ``gc`` only ages/removes already-detached ``ro-*``
workspaces by mtime, independent of root state), and ``lint`` performs no worktree operation at
all. So root-freshness applies only to the subcommands that create/remove a work worktree or
explicitly report root status — not to the three that never touch root's own checkout.

Hook execution (the §1 carve-out)
-----------------------------------
Setup (fail-fast) and teardown (best-effort) commands come from the consuming repo's
``<!-- worktree-setup -->`` / ``<!-- worktree-teardown -->`` marker blocks (discovery: scan
``COMMANDS.md`` then ``CLAUDE.md``, then any file either ``@``-includes one level, for the first
non-empty block — matching v1's ``discover_and_parse``/``find_includes`` exactly). Each candidate
file's block is read via ``config_block.py``'s own line-scan/parse primitives — imported and
called in-process (module import + function call), never subprocess-invoked, because
architecture.md §1 permits a script to spawn only ``git``/``gh`` as *external processes*;
spawning a second ``python3 config_block.py ...`` process would be an unlisted second carve-out.
Calling its module-level scan functions directly is "delegate the block read — don't re-parse"
without re-implementing the marker-scan algorithm — see :func:`_read_hook_block_from_file`. The
extracted commands then run through :mod:`pipelib.hooks`, the ONE other explicit carve-out (a
repo-owned opaque shell string, cwd'd to the workspace); this module is its only importer, per
that module's own docstring.
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_block  # noqa: E402  (import after sys.path setup, by necessity; in-process composition)
from pipelib import hooks, process  # noqa: E402
from pipelib.decisions import (  # noqa: E402
    AMBIGUOUS,
    BRANCH_IN_USE,
    ROOT_DIRTY,
    ROOT_DIVERGED,
    ROOT_NOT_ON_MAIN,
    needs_decision,
)
from pipelib.envelope import EXIT_OK, emit_needs_decision, emit_ok  # noqa: E402

ROOT_BRANCH = "main"
DEFAULT_MAX_AGE_DAYS = 7
WORKTREES_EXCLUDE_ENTRY = ".worktrees/"
READ_WORKTREE_PREFIX = "ro-"

# ---------------------------------------------------------------------------
# git helpers — every call takes an explicit cwd; nothing relies on ambient cwd
# (architecture.md §6 "no ambient cwd"). All spawns go through pipelib.process.run, the
# locked-down git/gh-only, argument-list-only, shell=False runner.
# ---------------------------------------------------------------------------


def _git(argv, cwd):
    """Run ``git <argv>`` cwd'd to ``cwd`` via the locked-down runner. Returns the
    :class:`pipelib.process.CommandResult`. Never raises on a non-zero exit — callers branch on
    ``returncode`` themselves, since "the git command failed" means different things in different
    contexts here (a ``merge --ff-only`` failure IS the ``ROOT_DIVERGED`` signal, not an error to
    bubble up)."""
    return process.run(["git"] + list(argv), cwd=str(cwd))


def _git_stdout(argv, cwd):
    """Run ``git <argv>`` and return stripped stdout, or raise ``RuntimeError`` with the faithful
    stderr on a non-zero exit — for calls this module treats as "must succeed or something is
    fundamentally wrong with the repo/workspace," not a decision-worthy outcome (e.g.
    ``rev-parse HEAD`` on a workspace this same call just created/reused)."""
    result = _git(argv, cwd)
    if result.returncode != 0:
        raise RuntimeError("git %s (cwd=%s) failed: %s" % (" ".join(argv), cwd, result.stderr))
    return result.stdout.strip()


def _is_dirty(cwd):
    return _git_stdout(["status", "--porcelain"], cwd) != ""


def _current_branch(cwd):
    return _git_stdout(["rev-parse", "--abbrev-ref", "HEAD"], cwd)


def _current_sha(cwd):
    return _git_stdout(["rev-parse", "HEAD"], cwd)


def _remote_branch_exists(cwd, branch):
    """True iff ``origin/<branch>`` exists on the remote — a live probe via ``git ls-remote``, not
    a local remote-tracking-ref lookup. A freshly created local branch has no remote-tracking ref
    yet even when the remote branch already exists (e.g. pushed from another workspace since this
    one last fetched), so a local-only check would be a false negative."""
    result = _git(["ls-remote", "--exit-code", "--heads", "origin", branch], cwd)
    return result.returncode == 0


def _local_branch_exists(cwd, branch):
    """True iff a local branch named ``<branch>`` exists in ``cwd``'s repo (``refs/heads/<branch>``),
    regardless of whether any worktree currently has it checked out. Used only when no worktree is
    already attached to ``<branch>`` (that case is handled earlier by ``_find_worktree_for_branch``)
    — e.g. a clone that once had a worktree for this branch, removed it, but kept the local branch
    ref. A plain ``git worktree add -b <branch> ...`` would fail with "branch already exists" in
    that case, so callers must check this first and attach rather than create."""
    result = _git(["show-ref", "--verify", "--quiet", "refs/heads/%s" % branch], cwd)
    return result.returncode == 0


def _unpushed_commits(cwd, branch, base_ref):
    """Count commits on ``HEAD`` not yet on the remote. If ``origin/<branch>`` exists, count
    relative to it (the true "not yet pushed" count for a branch with some history already
    published). Otherwise the branch has never been pushed — count relative to
    ``origin/<base_ref>`` instead, so a freshly created worktree with zero new commits reports 0,
    not the entire base branch's history."""
    upstream = "origin/%s" % (branch if _remote_branch_exists(cwd, branch) else base_ref)
    return int(_git_stdout(["rev-list", "--count", "%s..HEAD" % upstream], cwd))


def _list_worktrees(root):
    """Parse ``git worktree list --porcelain`` into a list of dicts:
    ``{"path": <resolved Path>, "sha": <str>, "branch": <str|None>, "detached": <bool>}``.
    ``branch`` is the bare branch name (``refs/heads/`` stripped) or ``None`` for a detached
    worktree. Blocks are separated by a blank line; each has a ``worktree <path>`` line, a
    ``HEAD <sha>`` line, then either ``branch refs/heads/<name>`` or the literal ``detached``."""
    stdout = _git_stdout(["worktree", "list", "--porcelain"], root)
    entries = []
    current = None
    for line in stdout.splitlines():
        if line.startswith("worktree "):
            current = {
                "path": Path(line[len("worktree "):]).resolve(),
                "sha": None,
                "branch": None,
                "detached": False,
            }
            entries.append(current)
        elif line.startswith("HEAD ") and current is not None:
            current["sha"] = line[len("HEAD "):]
        elif line.startswith("branch ") and current is not None:
            ref = line[len("branch "):]
            current["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif line == "detached" and current is not None:
            current["detached"] = True
    return entries


def _find_worktree_for_branch(worktrees, branch):
    for entry in worktrees:
        if entry["branch"] == branch:
            return entry
    return None


def _find_worktree_at_path(worktrees, path):
    resolved = Path(path).resolve()
    for entry in worktrees:
        if entry["path"] == resolved:
            return entry
    return None


def _slugify_ref(ref):
    """Replace every character unsafe in a single filesystem path segment with ``-`` (this
    includes ``/``, so a multi-segment ref collapses to one segment) — the result is always one
    path-segment-safe string, matching architecture.md §6's ``ro-<ref-slug>`` convention."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", ref)


def _work_path(root, branch):
    return (Path(root) / ".worktrees" / branch).resolve()


def _read_path(root, ref):
    return (Path(root) / ".worktrees" / (READ_WORKTREE_PREFIX + _slugify_ref(ref))).resolve()


# ---------------------------------------------------------------------------
# `.worktrees/` exclusion — idempotent single-line append to the repo's `info/exclude`
# (architecture.md §6). D4/D6 fix (docs/specs/parity/planner.md): this used to write
# `<root>/.gitignore` — a WORKING-TREE file, so `git status --porcelain` at root reported it as a
# new untracked/modified file the instant it was written, and the NEXT root-freshness check (the
# very next `ensure`/`root-status` call in the same clone/session) read that self-inflicted dirt as
# `ROOT_DIRTY` — making a prep script that calls `ensure` more than once in one clone (e.g. the
# planner's just-in-time composite epic+story session, which grounds twice) non-re-runnable, and
# forcing the consuming repo to commit a plugin-authored `.gitignore` edit it never asked for.
# `.git/info/exclude` has the identical ignore semantics as `.gitignore` (both are gitignore-syntax
# pattern files git consults when computing untracked status) but lives OUTSIDE the working tree —
# under the git directory itself — so writing to it can never appear in `git status --porcelain`
# and root-freshness can never trip on our own write. It also already exists as the repo's own
# "local, un-shared exclude list" convention (`git help gitignore`), so this isn't a novel
# mechanism, just the correct one for a tool-authored exclusion no consuming repo should have to
# commit.
# ---------------------------------------------------------------------------


def _git_common_dir(root):
    """Resolve the repo's COMMON git directory (`git rev-parse --git-common-dir`), never
    `--git-dir` — the two differ the moment `root` is itself a linked worktree (verified directly
    against real `git` behavior, not assumed): `--git-dir` from inside a worktree resolves to that
    worktree's PRIVATE per-worktree admin dir (`<main-repo>/.git/worktrees/<name>`), which has no
    `info/exclude` of its own; `--git-common-dir` resolves to the ONE shared dir every linked
    worktree (and the main checkout) points back at, so a write there is visible from all of them —
    exactly the "applies to all linked worktrees" property this fix needs, since `.worktrees/`
    itself lives under the MAIN checkout, not under any of the worktrees it names. The result may
    be relative (bare `.git` when `root` is a plain, non-worktree clone) or absolute (when `root`
    is itself a worktree) — `(Path(root) / result).resolve()` handles both: joining a `Path` with
    an absolute second operand discards the first per POSIX path-join semantics, so the relative
    case resolves against `root` and the absolute case passes through unchanged.
    """
    common_dir = _git_stdout(["rev-parse", "--git-common-dir"], root)
    return (Path(root) / common_dir).resolve()


def _ensure_worktrees_excluded(root):
    """Ensure the repo's `info/exclude` (resolved via :func:`_git_common_dir`, never a hardcoded
    `.git/info/exclude`) contains a line exactly `.worktrees/`. Idempotent: if already present, the
    file is left byte-for-byte untouched (not even rewritten) — the same "changed:false means
    untouched on disk" discipline `config_block.py` uses for its own idempotent writes. Creates
    `info/exclude` (and its parent `info/` dir) from scratch if absent. Returns `True` iff a write
    happened. Deliberately does NOT touch any `.gitignore` the consuming repo already carries
    (including a pre-existing `.worktrees/` bootstrap line an earlier v2 run may have left there —
    that line is harmless dead weight, not migrated or removed; this function only ever reads
    `info/exclude`, never `.gitignore`, on the write path or the idempotency check)."""
    path = _git_common_dir(root) / "info" / "exclude"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(WORKTREES_EXCLUDE_ENTRY + "\n", encoding="utf-8")
        return True

    text = path.read_text(encoding="utf-8")
    if any(line.strip() == WORKTREES_EXCLUDE_ENTRY.rstrip("/") + "/" for line in text.splitlines()):
        return False  # already present — file left byte-for-byte untouched

    if text and not text.endswith("\n"):
        text += "\n"
    text += WORKTREES_EXCLUDE_ENTRY + "\n"
    path.write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Root-freshness protocol (architecture.md §6, §12) — never auto-fixed.
# ---------------------------------------------------------------------------


def _root_freshness(root):
    """Verify root is on ``main`` and clean, fetch, fast-forward, and record the SHA.

    Returns either ``("ok", sha)`` on success, or a §3 decision dict (one of
    ``ROOT_NOT_ON_MAIN`` / ``ROOT_DIRTY`` / ``ROOT_DIVERGED``) — never raises, and never mutates
    root beyond the ``fetch``/``--ff-only merge`` the protocol itself performs. The caller
    distinguishes the two return shapes (tuple vs dict): each pure ``_build_*`` core that gates on
    freshness (``_build_ensure_work``, ``_build_root_status``) returns the dict as its own
    ``decision`` channel, and its thin emit wrapper turns that into a ``needs_decision`` envelope
    without proceeding further.
    """
    branch = _current_branch(root)
    if branch != ROOT_BRANCH:
        return needs_decision(
            ROOT_NOT_ON_MAIN,
            summary="project root is on branch %r, not %r" % (branch, ROOT_BRANCH),
            context={"root": str(root), "current_branch": branch, "expected_branch": ROOT_BRANCH},
            options=["checkout %s manually in the project root, then re-run" % ROOT_BRANCH],
        )

    if _is_dirty(root):
        return needs_decision(
            ROOT_DIRTY,
            summary="project root has uncommitted changes",
            context={"root": str(root)},
            options=["commit, stash, or discard the root's local changes manually, then re-run"],
        )

    fetch_result = _git(["fetch", "origin", ROOT_BRANCH], root)
    if fetch_result.returncode != 0:
        raise RuntimeError(
            "git fetch origin %s (cwd=%s) failed: %s" % (ROOT_BRANCH, root, fetch_result.stderr)
        )

    merge_result = _git(["merge", "--ff-only", "origin/%s" % ROOT_BRANCH], root)
    if merge_result.returncode != 0:
        return needs_decision(
            ROOT_DIVERGED,
            summary=(
                "project root has local commits origin/%s does not — cannot fast-forward"
                % ROOT_BRANCH
            ),
            context={"root": str(root), "merge_stderr": merge_result.stderr},
            options=["resolve the divergence manually (rebase/reset) in the project root, then re-run"],
        )

    return "ok", _current_sha(root)


# ---------------------------------------------------------------------------
# Hook discovery + execution — the §1 carve-out. workspace.py is pipelib.hooks's only importer.
# ---------------------------------------------------------------------------

_INCLUDE_TOKEN_RE = re.compile(r"@([A-Za-z0-9._/-]+)")
_INCLUDE_LOOKS_LIKE_PATH_RE = re.compile(r"(/|\.[A-Za-z0-9]+$)")
_LIST_ITEM_COMMAND_RE = re.compile(r"^\s*-\s*`([^`]*)`")


def _find_includes(file_path):
    """Return the ``@``-included paths (one level) found in ``file_path`` — v1's
    ``find_includes``, re-expressed: matches an ``@``-prefixed token that looks like a file path
    (has a slash or a dotted extension), which excludes bare ``@mentions``. Existence is
    re-checked by the caller, so a stray match is harmless."""
    path = Path(file_path)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    return [tok for tok in _INCLUDE_TOKEN_RE.findall(text) if _INCLUDE_LOOKS_LIKE_PATH_RE.search(tok)]


def _candidate_hook_files(root):
    """Ordered candidate list for hook-block discovery: ``COMMANDS.md``, ``CLAUDE.md``, then every
    file either ``@``-includes (one level) — matching v1's ``discover_and_parse`` candidate list
    exactly (architecture.md §6, ``skills/_shared/worktree-lifecycle.md``)."""
    root_path = Path(root)
    candidates = [root_path / "COMMANDS.md", root_path / "CLAUDE.md"]
    for root_file in (root_path / "COMMANDS.md", root_path / "CLAUDE.md"):
        for inc in _find_includes(root_file):
            inc_path = Path(inc)
            candidates.append(inc_path if inc_path.is_absolute() else root_path / inc)
    return candidates


def _read_hook_block_from_file(file_path, marker_name):
    """Read the named marker block's interior lines from ``file_path`` by calling
    ``config_block``'s own line-scan primitives directly (in-process module import + function
    call — architecture.md §2's "compose in-process," and the only viable form here, since
    architecture.md §1 permits a script to spawn only ``git``/``gh`` as external processes, so a
    second ``python3 config_block.py`` subprocess is not an option). This calls exactly the two
    functions ``config_block.py``'s own ``run_read`` composes — ``_read_lines_or_empty`` then
    ``_scan_marker`` — never its CLI/argparse/``sys.exit`` surface, and never re-implements the
    scan itself ("delegate the block read — don't re-parse").

    Returns ``(present, interior_lines)``. ``present`` is ``False`` when the marker doesn't open
    in this file at all, or is malformed there (duplicate/unterminated) — matching the v1 hook
    runner's own candidate-file loop, which treats both "absent in this file" and
    "malformed in this file" as "try the next candidate," reserving a hard failure only for when
    NO candidate file yields a well-formed block (this module's caller reports that as
    ``phase_present=False`` after exhausting every candidate — the same "no usable block found"
    outcome, without inventing a new decision code for a case architecture.md §3's closed set does
    not name)."""
    lines = config_block._read_lines_or_empty(str(file_path))
    open_count, close_count, open_index, close_index = config_block._scan_marker(lines, marker_name)
    if open_count == 0:
        return False, []
    if open_count > 1 or close_count > 1:
        return False, []
    if open_count != close_count or close_index < open_index:
        return False, []
    interior = lines[open_index:close_index - 1]
    return True, interior


def _parse_command_list(interior_lines):
    """Extract one backtick-quoted command per Markdown list item — v1's
    ``sed -n 's/^[[:space:]]*-[[:space:]]*`\\([^`]*\\)`.*/\\1/p'``, re-expressed: a line is
    ``- `<command>` — <description>``; the description is ignored, matching
    ``skills/_shared/worktree-lifecycle.md``'s documented block format."""
    commands = []
    for line in interior_lines:
        match = _LIST_ITEM_COMMAND_RE.match(line)
        if match:
            commands.append(match.group(1))
    return commands


def _discover_hook_commands(root, phase):
    """Discover the ``<!-- worktree-<phase> -->`` block across the ordered candidate files
    (:func:`_candidate_hook_files`) — first present block wins. Returns
    ``(phase_present, commands)``."""
    marker_name = "worktree-%s" % phase
    for candidate in _candidate_hook_files(root):
        present, interior = _read_hook_block_from_file(candidate, marker_name)
        if present:
            return True, _parse_command_list(interior)
    return False, []


def _tail_lines(text, n):
    lines = (text or "").splitlines()
    return "\n".join(lines[-n:])


def _run_setup_hooks(root, workspace_path):
    """Fail-fast: run every discovered setup command inside ``workspace_path`` in declaration
    order; stop at the first non-zero exit. Returns ``{"phase_present", "commands_run",
    "succeeded", "first_failure"?}``.

    Hook result-key mapping (v1 hook runner -> v2 ``workspace.py``)
    ---------------------------------------------------------------------
    Preserved verbatim (same key, same meaning, same shape) across both setup and teardown:
    ``phase_present``, ``commands_run``, ``succeeded``, ``first_failure`` (``{step, command,
    output_tail}``, setup only), ``failures`` (list of that same shape, teardown only). ``step`` is
    1-based; ``output_tail`` is the last 50 lines of the failing command's combined stdout+stderr.

    Dropped from v1, and why:
      - ``dry_run`` — v1's ``setup``/``teardown`` subcommands had a ``--dry-run`` flag that ran the
        discover/parse step but skipped execution. v2's ``ensure``/``remove`` have no dry-run mode
        at all (nothing to opt out of mid-envelope); ``lint`` is v2's non-executing preview instead,
        used standalone rather than as a flag on the executing subcommand.
      - ``reused`` (setup) / ``op`` — v1 put these on the hook-result object itself because
        ``setup``/``teardown`` were the whole CLI surface. v2 hoists both up a level: ``reused``
        lives on the parent ``ensure --work`` envelope's own payload (alongside ``path``, ``branch``,
        ``sha``, etc.), and ``op`` is likewise the parent envelope's field (``"ensure"``/``"remove"``)
        — the hook result itself is just one nested value under that envelope's ``"setup"``/
        ``"teardown"`` key, not a top-level, self-describing result.

    ``lint`` (a separate subcommand here, see :func:`_cmd_lint`) reports ``{"phase",
    "phase_present", "command_count", "would_run"}`` — this is v2's rendering of v1's
    ``lint``/``--dry-run`` preview shape (discover + parse, no execution, no worktree needed).

    Deliberate v1 divergence: a MALFORMED block. The v1 hook runner's ``discover_and_parse``
    hard-exits 2 with ``MALFORMED_BLOCK: ...`` the moment a candidate file's block is malformed
    (duplicate/unterminated), even though earlier or later candidates might still yield a good one.
    v2's :func:`_read_hook_block_from_file` instead treats a malformed block in one candidate file
    exactly like an absent one — ``phase_present=False`` for that file, try the next candidate — and
    only reports no-block-found after exhausting every candidate. This is intentional, not an
    oversight: the closed decision-code set (architecture.md §3, ``pipelib/decisions.py``) has no
    malformed-block code, so degrading gracefully to "try the next candidate" is safer than
    inventing a new code or hard-blocking the whole ``ensure``/``remove`` envelope over one
    malformed candidate file when a later candidate (or "no block at all") would have been fine.
    """
    phase_present, commands = _discover_hook_commands(root, "setup")
    result = {"phase_present": phase_present, "commands_run": 0, "succeeded": True}
    for step, command_text in enumerate(commands, start=1):
        hook_result = hooks.run_repo_owned_hook_command(command_text, cwd=workspace_path)
        result["commands_run"] += 1
        if hook_result.returncode != 0:
            result["succeeded"] = False
            result["first_failure"] = {
                "step": step,
                "command": command_text,
                "output_tail": _tail_lines(hook_result.stdout + (hook_result.stderr or ""), 50),
            }
            break
    return result


def _run_teardown_hooks(root, workspace_path):
    """Best-effort: run every discovered teardown command inside ``workspace_path`` in order,
    logging (never stopping on) each failure. Always reports ``succeeded: True`` (v1's own
    contract: teardown always exits 0). Returns ``{"phase_present", "commands_run", "succeeded"
    (always True), "failures": [...]}`` — see :func:`_run_setup_hooks` for the full v1-key
    correspondence table (shared by both hook runners) and the MALFORMED-block divergence note."""
    phase_present, commands = _discover_hook_commands(root, "teardown")
    result = {"phase_present": phase_present, "commands_run": 0, "succeeded": True, "failures": []}
    for step, command_text in enumerate(commands, start=1):
        hook_result = hooks.run_repo_owned_hook_command(command_text, cwd=workspace_path)
        result["commands_run"] += 1
        if hook_result.returncode != 0:
            result["failures"].append({
                "step": step,
                "command": command_text,
                "output_tail": _tail_lines(hook_result.stdout + (hook_result.stderr or ""), 50),
            })
    return result


# ---------------------------------------------------------------------------
# ensure --work
# ---------------------------------------------------------------------------


def _build_ensure_work(root, branch, base):
    """Pure ``ensure --work`` core (architecture.md §2's pure-core pattern, S8 pattern lock):
    create/reuse the work worktree on ``branch`` (checked out at its own head when it exists, else
    forked at ``origin/<base>``), run setup hooks, and return ``(payload, notices, decision)`` —
    **never emits** (no ``print``/``emit_ok``/``emit_needs_decision``). ``prep_evaluator`` calls
    this directly, retiring the S6 ``redirect_stdout`` bridge.

    Return contract (the type-level distinction the S8 retro asks for):
      - ``decision is not None`` → a ``needs_decision`` (``ROOT_*`` from freshness, or
        ``BRANCH_IN_USE``); ``payload`` is ``None`` and the caller propagates the decision.
      - ``decision is None`` → success or a *setup-hook failure*: both carry a ``payload``. A
        setup-hook failure is a **partial-but-honest** envelope (``payload["setup"]["succeeded"]``
        is ``False`` and ``sha``/``dirty``/``unpushed_commits`` are absent), rides in ``payload``
        exactly as v1 emitted it, and the emit wrapper maps it to process exit 1 by inspecting
        ``setup.succeeded`` — the caller (prep) likewise reads ``setup.succeeded`` rather than a
        process exit code, so nothing about the observed behavior changes.
      - a hard `git` failure still ``sys.exit(1)`` with faithful stderr and no envelope (§3
        exit-code contract — unchanged), not a returnable decision.
    """
    root = str(Path(root).resolve())
    freshness = _root_freshness(root)
    if isinstance(freshness, dict):
        return None, [], freshness

    fetch_result = _git(["fetch", "origin", base], root)
    if fetch_result.returncode != 0:
        sys.stderr.write(fetch_result.stderr)
        sys.exit(1)

    target_path = _work_path(root, branch)
    worktrees = _list_worktrees(root)

    existing_for_branch = _find_worktree_for_branch(worktrees, branch)
    if existing_for_branch is not None and existing_for_branch["path"] != target_path:
        return None, [], needs_decision(
            BRANCH_IN_USE,
            summary="branch %r is already checked out at %s" % (branch, existing_for_branch["path"]),
            context={
                "branch": branch,
                "existing_path": str(existing_for_branch["path"]),
                "requested_path": str(target_path),
            },
            options=[
                "use the existing worktree at %s" % existing_for_branch["path"],
                "remove that worktree first, then re-run",
            ],
        )

    reused = target_path.is_dir() and _find_worktree_at_path(worktrees, target_path) is not None
    if not reused:
        # No worktree to reuse — pick the checkout source by branch existence, so an EXISTING
        # branch (e.g. a PR head an evaluator must check out) lands the worktree at that branch's
        # actual head, never silently at --base (architecture.md §6's "SHA" fact must be the
        # branch's own head, not main's).
        branch_on_remote = _remote_branch_exists(root, branch)
        if branch_on_remote:
            fetch_branch_result = _git(["fetch", "origin", branch], root)
            if fetch_branch_result.returncode != 0:
                sys.stderr.write(fetch_branch_result.stderr)
                sys.exit(1)

        if branch_on_remote and _local_branch_exists(root, branch):
            # Local branch ref exists (e.g. left behind by a worktree removed earlier) but no
            # worktree currently has it checked out (ruled out above) — attach it, then fast-
            # forward/reset it to origin/<branch>'s head so a stale local ref never wins over the
            # remote's actual head.
            add_result = _git(["worktree", "add", str(target_path), branch], root)
            if add_result.returncode != 0:
                sys.stderr.write(add_result.stderr)
                sys.exit(1)
            reset_result = _git(
                ["reset", "--hard", "origin/%s" % branch], str(target_path),
            )
            if reset_result.returncode != 0:
                sys.stderr.write(reset_result.stderr)
                sys.exit(1)
        elif branch_on_remote:
            # No local branch at all — create one tracking origin/<branch>, checked out at its
            # head, in the same worktree-add call.
            add_result = _git(
                ["worktree", "add", "-b", branch, str(target_path), "origin/%s" % branch],
                root,
            )
            if add_result.returncode != 0:
                sys.stderr.write(add_result.stderr)
                sys.exit(1)
        else:
            # Neither a worktree nor an origin branch — the resolver's fresh-work case: create a
            # new branch at origin/<base> (unchanged from prior behavior).
            add_result = _git(
                ["worktree", "add", "-b", branch, str(target_path), "origin/%s" % base],
                root,
            )
            if add_result.returncode != 0:
                sys.stderr.write(add_result.stderr)
                sys.exit(1)

    _ensure_worktrees_excluded(root)

    hook_result = _run_setup_hooks(root, str(target_path))
    if not hook_result["succeeded"]:
        # Fail-fast (matching v1's setup exit 1): the worktree exists but isn't ready — report the
        # failure with as much fact context as we already have, but do NOT compute/report
        # dirty/unpushed/sha, since those facts are about a workspace ready for use. This is the
        # partial-but-honest payload the emit wrapper maps to exit 1 (setup.succeeded == False).
        return {
            "op": "ensure",
            "kind": "work",
            "path": str(target_path),
            "branch": branch,
            "base_ref": base,
            "reused": reused,
            "setup": hook_result,
        }, [], None

    dirty = _is_dirty(str(target_path))
    unpushed = _unpushed_commits(str(target_path), branch, base)
    sha = _current_sha(str(target_path))

    return {
        "op": "ensure",
        "kind": "work",
        "path": str(target_path),
        "branch": branch,
        "base_ref": base,
        "reused": reused,
        "dirty": dirty,
        "unpushed_commits": unpushed,
        "sha": sha,
        "setup": hook_result,
    }, [], None


def _cmd_ensure_work(args):
    payload, notices, decision = _build_ensure_work(args.root, args.branch, args.base)
    if decision is not None:
        emit_needs_decision(decision, notices=notices)
        return EXIT_OK
    emit_ok(payload=payload, notices=notices)
    # A setup-hook failure is an ok envelope but a non-zero process exit (v1's fail-fast exit 1).
    if not (payload.get("setup") or {}).get("succeeded", True):
        return 1
    return EXIT_OK


# ---------------------------------------------------------------------------
# ensure --read
# ---------------------------------------------------------------------------


def _build_ensure_read(root, ref):
    """Pure ``ensure --read`` core (S8 pattern lock): create/refresh the detached read workspace at
    ``origin/<ref>`` and return ``(payload, notices, decision)`` — **never emits**. ``ensure
    --read`` has no root-freshness gate and no ``needs_decision`` path (it grounds directly at a
    freshly fetched ``origin/<ref>``), so ``decision`` is always ``None`` here; the tuple shape is
    kept uniform with every other retrofitted core. A hard `git` failure still ``sys.exit(1)`` with
    faithful stderr and no envelope (§3 — unchanged)."""
    root = str(Path(root).resolve())

    fetch_result = _git(["fetch", "origin", ref], root)
    if fetch_result.returncode != 0:
        sys.stderr.write(fetch_result.stderr)
        sys.exit(1)

    target_path = _read_path(root, ref)
    remote_ref = "origin/%s" % ref

    _ensure_worktrees_excluded(root)

    if target_path.is_dir():
        reset_result = _git(["reset", "--hard", remote_ref], str(target_path))
        if reset_result.returncode != 0:
            sys.stderr.write(reset_result.stderr)
            sys.exit(1)
        # `reset --hard` only rewrites tracked content; it leaves untracked files (e.g. scratch
        # output a prior grounding read left behind) in place. A read workspace must be a pristine
        # view of exactly origin/<ref> on every ensure, so also discard untracked files/dirs.
        clean_result = _git(["clean", "-fd"], str(target_path))
        if clean_result.returncode != 0:
            sys.stderr.write(clean_result.stderr)
            sys.exit(1)
        reused = True
    else:
        add_result = _git(["worktree", "add", "--detach", str(target_path), remote_ref], root)
        if add_result.returncode != 0:
            sys.stderr.write(add_result.stderr)
            sys.exit(1)
        reused = False

    sha = _current_sha(str(target_path))
    return {
        "op": "ensure",
        "kind": "read",
        "path": str(target_path),
        "ref": ref,
        "reused": reused,
        "sha": sha,
    }, [], None


def _cmd_ensure_read(args):
    payload, notices, decision = _build_ensure_read(args.root, args.ref)
    if decision is not None:  # pragma: no cover — ensure --read has no decision path today
        emit_needs_decision(decision, notices=notices)
        return EXIT_OK
    emit_ok(payload=payload, notices=notices)
    return EXIT_OK


# ---------------------------------------------------------------------------
# remove --work
# ---------------------------------------------------------------------------


def _build_remove_work(root, branch):
    """Pure ``remove --work`` core (S8 pattern lock): tear down and remove the work worktree for
    ``branch`` and return ``(payload, notices, decision)`` — **never emits**.

    Return contract (the type-level distinction the S8 retro asks for):
      - ``decision is not None`` → ``AMBIGUOUS`` when the worktree is dirty or has unpushed commits
        (architecture.md §6: "dirty or unpushed state is a decision, never a silent discard");
        ``payload`` is ``None`` and the worktree is left in place.
      - ``decision is None`` → success, carrying the removal receipt (or the ``removed: False,
        reason: not_found`` no-op when nothing is there to remove).
      - a hard `git` failure still ``sys.exit(1)`` with faithful stderr and no envelope (§3 —
        unchanged).
    """
    root = str(Path(root).resolve())

    target_path = _work_path(root, branch)
    worktrees = _list_worktrees(root)
    entry = _find_worktree_at_path(worktrees, target_path)
    if entry is None:
        return {
            "op": "remove",
            "kind": "work",
            "branch": branch,
            "path": str(target_path),
            "removed": False,
            "reason": "not_found",
        }, [], None

    dirty = _is_dirty(str(target_path))
    # remove --work has no --base (the subcommand signature is `remove --work <branch>` only), so
    # the fallback reference for "never pushed at all" is ROOT_BRANCH (origin/main) rather than
    # the worktree's original --base — every work worktree ultimately traces back through the
    # trust topology's root branch (architecture.md §6), so this never UNDER-counts risk. It can
    # OVER-count for a story branch created off an unmerged epic branch that is itself ahead of
    # main (that epic's own commits would be included too) — a known, accepted narrow edge case,
    # since remove's CLI has no --base to give a tighter answer.
    unpushed = _unpushed_commits(str(target_path), branch, ROOT_BRANCH)

    if dirty or unpushed > 0:
        # architecture.md §6: "dirty or unpushed state is a decision, never a silent discard." The
        # closed decision-code set (architecture.md §3) has no bespoke code for this hazard; per
        # prd.md's own framing ("a dirty root" is grouped under "ambiguous state" as a mechanical
        # blocker), AMBIGUOUS is the closed-set code for a residual, listable-options blocker that
        # isn't one of the twelve narrowly-named codes. Teardown is intentionally NOT run here: a
        # failing or resource-releasing teardown must not run against a workspace we are about to
        # leave in place specifically so the operator can recover its uncommitted/unpushed state.
        hazard = "uncommitted changes" if dirty else "%d unpushed commit(s)" % unpushed
        return None, [], needs_decision(
            AMBIGUOUS,
            summary="work worktree for branch %r has %s — refusing to remove" % (branch, hazard),
            context={
                "branch": branch,
                "path": str(target_path),
                "dirty": dirty,
                "unpushed_commits": unpushed,
            },
            options=[
                "push the branch, then re-run remove --work",
                "commit or discard the uncommitted changes, then re-run remove --work",
                "remove the worktree manually if the state is intentionally being discarded",
            ],
        )

    teardown_result = _run_teardown_hooks(root, str(target_path))

    remove_result = _git(["worktree", "remove", str(target_path)], root)
    if remove_result.returncode != 0:
        sys.stderr.write(remove_result.stderr)
        sys.exit(1)

    return {
        "op": "remove",
        "kind": "work",
        "branch": branch,
        "path": str(target_path),
        "removed": True,
        "teardown": teardown_result,
    }, [], None


def _cmd_remove_work(args):
    payload, notices, decision = _build_remove_work(args.root, args.branch)
    if decision is not None:
        emit_needs_decision(decision, notices=notices)
        return EXIT_OK
    emit_ok(payload=payload, notices=notices)
    return EXIT_OK


# ---------------------------------------------------------------------------
# gc — removes only aged ro-* worktrees; work worktrees are never touched regardless of age.
# ---------------------------------------------------------------------------


def _build_gc(root, max_age):
    """Pure ``gc`` core (S8 pattern lock): age out ``ro-*`` read workspaces older than ``max_age``
    days (work worktrees are never touched) and return ``(payload, notices, decision)`` — **never
    emits**. ``gc`` has no ``needs_decision`` path, so ``decision`` is always ``None`` here."""
    root = str(Path(root).resolve())
    max_age_seconds = max_age * 86400
    now = time.time()

    worktrees = _list_worktrees(root)
    removed = []
    skipped = []
    for entry in worktrees:
        basename = entry["path"].name
        if not basename.startswith(READ_WORKTREE_PREFIX):
            continue  # never touch a work worktree, regardless of age (architecture.md §6)
        try:
            age_seconds = now - entry["path"].stat().st_mtime
        except OSError:
            continue  # listed by git but missing on disk — nothing for gc to remove
        if age_seconds < max_age_seconds:
            skipped.append(str(entry["path"]))
            continue
        remove_result = _git(["worktree", "remove", "--force", str(entry["path"])], root)
        if remove_result.returncode == 0:
            removed.append(str(entry["path"]))
        else:
            skipped.append(str(entry["path"]))

    return {
        "op": "gc",
        "max_age_days": max_age,
        "removed": removed,
        "skipped": skipped,
    }, [], None


def _cmd_gc(args):
    payload, notices, _decision = _build_gc(args.root, args.max_age)
    emit_ok(payload=payload, notices=notices)
    return EXIT_OK


# ---------------------------------------------------------------------------
# root-status
# ---------------------------------------------------------------------------


def _build_root_status(root):
    """Pure ``root-status`` core (S8 pattern lock): run the root-freshness protocol and return
    ``(payload, notices, decision)`` — **never emits**. On a freshness failure the ``ROOT_*``
    decision rides in ``decision`` (``payload`` is ``None``); on success the fresh-SHA status rides
    in ``payload``. A hard `git` failure (e.g. ``fetch`` itself failing) still raises out of
    ``_root_freshness`` (§3 — unchanged)."""
    root = str(Path(root).resolve())
    outcome = _root_freshness(root)
    if isinstance(outcome, dict):
        return None, [], outcome
    _, sha = outcome
    return {"op": "root-status", "root": root, "branch": ROOT_BRANCH, "sha": sha}, [], None


def _cmd_root_status(args):
    payload, notices, decision = _build_root_status(args.root)
    if decision is not None:
        emit_needs_decision(decision, notices=notices)
        return EXIT_OK
    emit_ok(payload=payload, notices=notices)
    return EXIT_OK


# ---------------------------------------------------------------------------
# lint <setup|teardown>
# ---------------------------------------------------------------------------


def _build_lint(root, phase):
    """Pure ``lint`` core (S8 pattern lock): discover the ``<!-- worktree-<phase> -->`` block's
    commands (no execution, no worktree) and return ``(payload, notices, decision)`` — **never
    emits**. ``lint`` has no ``needs_decision`` path, so ``decision`` is always ``None`` here."""
    root = str(Path(root).resolve())
    phase_present, commands = _discover_hook_commands(root, phase)
    return {
        "op": "lint",
        "phase": phase,
        "phase_present": phase_present,
        "command_count": len(commands),
        "would_run": commands,
    }, [], None


def _cmd_lint(args):
    payload, notices, _decision = _build_lint(args.root, args.phase)
    emit_ok(payload=payload, notices=notices)
    return EXIT_OK


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="workspace.py",
        description="The workspace-lifecycle owner (architecture.md §6).",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_ensure = sub.add_parser("ensure")
    p_ensure.add_argument("--root", default=".")
    group = p_ensure.add_mutually_exclusive_group(required=True)
    group.add_argument("--work", dest="branch", metavar="BRANCH")
    group.add_argument("--read", dest="ref", metavar="REF")
    p_ensure.add_argument("--base", default=None, help="required with --work")

    p_remove = sub.add_parser("remove")
    p_remove.add_argument("--root", default=".")
    p_remove.add_argument("--work", dest="branch", metavar="BRANCH", required=True)

    p_gc = sub.add_parser("gc")
    p_gc.add_argument("--root", default=".")
    p_gc.add_argument("--max-age", dest="max_age", type=int, default=DEFAULT_MAX_AGE_DAYS)

    p_root_status = sub.add_parser("root-status")
    p_root_status.add_argument("--root", default=".")

    p_lint = sub.add_parser("lint")
    p_lint.add_argument("phase", choices=["setup", "teardown"])
    p_lint.add_argument("--root", default=".")

    return parser, {"ensure": p_ensure, "remove": p_remove}


def main(argv):
    parser, subparsers_by_name = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "ensure":
        if args.branch is not None:
            if not args.base:
                subparsers_by_name["ensure"].error("--work requires --base <ref>")
            return _cmd_ensure_work(args)
        return _cmd_ensure_read(args)
    if args.subcommand == "remove":
        return _cmd_remove_work(args)
    if args.subcommand == "gc":
        return _cmd_gc(args)
    if args.subcommand == "root-status":
        return _cmd_root_status(args)
    return _cmd_lint(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
